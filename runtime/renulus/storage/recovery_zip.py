# SPDX-License-Identifier: MIT
"""Strict bounded ZIP/ZIP64 inventory before allocating ZipFile metadata.

Renulus accepts contiguous single-disk archives without comments or extensible
ZIP64 trailers. Every local header, size, name and descriptor must agree with
its central entry. No extraction paths or arbitrary archive members are used.
"""
import re
import stat
import struct
import zipfile

from ..contracts import ApiError
from .recovery_archive import ORIGINAL

SEGMENT = re.compile(r"canonical/([a-z][a-z0-9_]*)/([0-9]{6})\.jsonl")


def _error(message):
    raise ApiError("backup_zip", message)


def _extras(raw):
    entries, offset = {}, 0
    while offset < len(raw):
        if len(raw) - offset < 4:
            _error("A ZIP extra field is truncated")
        key, length = struct.unpack_from("<HH", raw, offset)
        offset += 4
        if key in entries or offset + length > len(raw) or key != 1:
            _error("Unsupported or duplicate ZIP extra fields")
        entries[key] = raw[offset:offset + length]
        offset += length
    return entries


def _zip64_values(raw, required):
    extra = _extras(raw).get(1, b"")
    if len(extra) != len(required) * 8:
        _error("ZIP64 size/offset fields do not match their header")
    return dict(zip(required, struct.unpack("<" + "Q" * len(required), extra))) if required else {}


def directory(path, limits):
    size = path.stat().st_size
    if not 22 <= size <= limits.archive_bytes:
        raise ApiError("backup_limit", "The ZIP is empty, truncated or exceeds the archive budget", 413)
    with path.open("rb") as source:
        source.seek(size - 22)
        end = source.read(22)
        signature, disk, directory_disk, disk_count, count, length, start, comment = struct.unpack("<4s4H2LH", end)
        if signature != b"PK\x05\x06" or disk or directory_disk or comment or disk_count != count:
            _error("Choose a complete single-disk ZIP without trailing data or comments")
        end_offset = size - 22
        zip64 = False
        if size >= 42:
            source.seek(size - 42)
            locator = source.read(20)
            if locator[:4] == b"PK\x06\x07":
                zip64 = True
                _, locator_disk, offset, disks = struct.unpack("<4sLQL", locator)
                if locator_disk or disks != 1 or offset + 56 != size - 42:
                    _error("Split or extensible ZIP64 trailers are unsupported")
                source.seek(offset)
                record = source.read(56)
                sig, record_length, made, required, zdisk, zdir_disk, zcount_disk, zcount, zlength, zstart = struct.unpack("<4sQ2H2L4Q", record)
                if sig != b"PK\x06\x06" or record_length != 44 or required > 45 or zdisk or zdir_disk or zcount_disk != zcount:
                    _error("ZIP64 directory trailer is inconsistent")
                if count not in (65535, zcount) or disk_count not in (65535, zcount) or length not in (0xffffffff, zlength) or start not in (0xffffffff, zstart):
                    _error("Classic and ZIP64 directory trailers disagree")
                count, length, start, end_offset = zcount, zlength, zstart, offset
        if not zip64 and (count == 65535 or length == 0xffffffff or start == 0xffffffff):
            _error("The ZIP64 directory trailer is missing")
        if count > limits.originals + limits.segments + 2 or length > limits.directory_bytes:
            raise ApiError("backup_limit", "The ZIP central directory exceeds its metadata budget", 413)
        if start + length != end_offset or start < 0:
            _error("The ZIP directory is inconsistent or has unaccounted data")
        # Parse bounded central metadata before ZipFile makes its inventory.
        source.seek(start)
        consumed, inventory, names = 0, [], set()
        for _ in range(count):
            header = source.read(46)
            if len(header) != 46:
                _error("The ZIP central directory is truncated")
            fields = struct.unpack("<4s6H3L5H2L", header)
            sig, made, required, flags, method, _, _, crc, compressed, expanded, name_size, extra_size, comment_size, member_disk, _, attributes, offset = fields
            if sig != b"PK\x01\x02" or member_disk or comment_size or required > 45:
                _error("A ZIP central entry is unsupported")
            consumed += 46 + name_size + extra_size + comment_size
            if consumed > length or not 0 < name_size <= 512 or extra_size > 64:
                _error("A ZIP member's metadata is invalid or oversized")
            raw_name, extra = source.read(name_size), source.read(extra_size)
            try:
                name = raw_name.decode("ascii")
            except UnicodeError:
                _error("Renulus ZIP member paths must be canonical ASCII names")
            if name.casefold() in names:
                raise ApiError("backup_duplicates", "The ZIP contains duplicate or aliased member names")
            names.add(name.casefold())
            if name not in ("manifest.json", "records.json") and not ORIGINAL.fullmatch(name) and not SEGMENT.fullmatch(name):
                raise ApiError("backup_path", "The ZIP contains an unsafe or unexpected member path")
            if flags & 0x41:
                raise ApiError("backup_encrypted", "Encrypted backups are unsupported")
            if flags & ~(0x800 | 0x8 | 0x6) or method not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                _error("Unsupported ZIP compression or flags")
            mode = stat.S_IFMT(attributes >> 16)
            if mode not in (0, stat.S_IFREG) or attributes & 0x10:
                raise ApiError("backup_path", "The ZIP contains links, devices or directories")
            required_fields = [key for key, value in (("expanded", expanded), ("compressed", compressed), ("offset", offset)) if value == 0xffffffff]
            values = _zip64_values(extra, required_fields)
            expanded, compressed, offset = values.get("expanded", expanded), values.get("compressed", compressed), values.get("offset", offset)
            bound = limits.manifest_bytes if name == "manifest.json" else limits.row_bytes if name == "records.json" else limits.segment_bytes if SEGMENT.fullmatch(name) else limits.original_bytes
            if expanded > bound or compressed > limits.archive_bytes or offset >= start:
                raise ApiError("backup_limit", "A ZIP member exceeds its bounded size or offset", 413)
            inventory.append((name, flags, method, crc, compressed, expanded, offset))
        if consumed != length or source.tell() != end_offset:
            _error("The ZIP directory has unaccounted entries or data")
        # Entire expanded archive is bounded, including canonical and metadata.
        if sum(item[5] for item in inventory) > limits.expanded_bytes:
            raise ApiError("backup_limit", "The expanded ZIP exceeds the aggregate recovery budget", 413)
        end_offset = 0
        for name, flags, method, crc, compressed, expanded, offset in sorted(inventory, key=lambda item: item[6]):
            if offset != end_offset:
                _error("ZIP members overlap or contain unaccounted data")
            source.seek(offset)
            header = source.read(30)
            if len(header) != 30:
                _error("A local ZIP header is truncated")
            sig, required, lflags, lmethod, _, _, lcrc, lcompressed, lexpanded, name_size, extra_size = struct.unpack("<4s5H3L2H", header)
            if sig != b"PK\x03\x04" or required > 45 or (lflags, lmethod) != (flags, method) or name_size != len(name) or extra_size > 64:
                _error("Local and central ZIP headers disagree")
            if source.read(name_size) != name.encode("ascii"):
                _error("Local and central ZIP names disagree")
            required_fields = [key for key, value in (("expanded", lexpanded), ("compressed", lcompressed)) if value == 0xffffffff]
            values = _zip64_values(source.read(extra_size), required_fields)
            lexpanded, lcompressed = values.get("expanded", lexpanded), values.get("compressed", lcompressed)
            if not flags & 8 and (lcrc, lcompressed, lexpanded) != (crc, compressed, expanded):
                _error("Local and central ZIP CRC/size fields disagree")
            end_offset = offset + 30 + name_size + extra_size + compressed
            if end_offset > start:
                _error("A ZIP member overlaps the directory")
            if flags & 8:
                if end_offset + 4 > start:
                    _error("A ZIP data descriptor is truncated or overlaps the directory")
                source.seek(end_offset)
                prefix = source.read(4)
                if len(prefix) != 4:
                    _error("A ZIP data descriptor is truncated")
                signed = prefix == b"PK\x07\x08"
                if not signed:
                    source.seek(end_offset)
                width = 20 if required_fields else 12
                if end_offset + width + (4 if signed else 0) > start:
                    _error("A ZIP data descriptor overlaps the directory")
                descriptor = source.read(width)
                if len(descriptor) != width:
                    _error("A ZIP data descriptor is truncated")
                values = struct.unpack("<LQQ" if required_fields else "<3L", descriptor)
                if values != (crc, compressed, expanded):
                    _error("ZIP data descriptor disagrees with its central entry")
                end_offset += width + (4 if signed else 0)
            if end_offset > start:
                _error("A ZIP member overlaps the directory")
        if end_offset != start or "manifest.json" not in names:
            _error("The ZIP is missing its manifest or has unaccounted member data")
    return {item[0]: item[5] for item in inventory}


def zip_infos(archive, inventory):
    infos = archive.infolist()
    if len(infos) != len(inventory) or any(item.filename != item.orig_filename or item.filename not in inventory or item.file_size != inventory[item.filename] for item in infos):
        _error("The ZIP parser and bounded inventory disagree")
    return {item.filename: item for item in infos}
