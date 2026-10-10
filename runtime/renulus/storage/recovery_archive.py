"""Bounded ZIP format: canonical JSON and explicitly referenced library originals.

No extractall, directory discovery, provider configuration or engine files.
Every member is consumed and checked before any profile record is changed.
"""
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import zipfile
import zlib

from ..contracts import ApiError
from .backup import (DELETION_NOTICE, FORMAT_VERSION, MAX_JSON_BYTES, blocked_ids, portable_records,
                     record_references, snapshot_in, validate_merge, validate_records)
from .database import SUPPORTED_SCHEMA
from .compatibility import readable_schema
from .relations import allow_row

MIB = 1024 * 1024
BLOCK = MIB
FULL_FORMAT = "renulus-full-backup"
EXTENSIONS = r"pdf|png|jpg|jpeg|tif|tiff|txt|md|pptx|docx|xlsx|csv|html|xml"
LIBRARY_ORIGINAL = re.compile(r"library/knowledge/(doc_[a-zA-Z0-9_-]{1,100})/(rev_[a-zA-Z0-9_-]{1,100})/original\.(" + EXTENSIONS + r")")
ATTACHMENT_ORIGINAL = re.compile(r"library/attachments/([a-zA-Z0-9_-]{1,128})/(original|preview)\.(" + EXTENSIONS + r")")
ORIGINAL = re.compile(r"(?:" + LIBRARY_ORIGINAL.pattern + "|" + ATTACHMENT_ORIGINAL.pattern + r")")
ORIGINAL_TABLES = {"knowledge_revisions", "knowledge_attachment_originals"}
MEDIA = {"pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg",
         "jpeg": "image/jpeg", "tif": "image/tiff", "tiff": "image/tiff",
         "txt": "text/plain", "md": "text/markdown", "csv": "text/csv",
         "html": "text/html", "xml": "application/xml",
         "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
         "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
         "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}


@dataclass(frozen=True)
class BackupLimits:
    archive_bytes: int = 288 * MIB
    json_bytes: int = MAX_JSON_BYTES
    original_bytes: int = 64 * MIB
    total_original_bytes: int = 256 * MIB
    originals: int = 1000
    manifest_bytes: int = MIB

    def public(self):
        return asdict(self)


DEFAULT_LIMITS = BackupLimits()


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def strict_json(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate field")
            result[key] = value
        return result
    try:
        return json.loads(data, object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ApiError("backup_json", "The backup contains invalid or duplicate JSON fields") from None


def owned_path(paths, relative):
    """Check lexical ownership and every existing component before resolving."""
    if not isinstance(relative, str) or "\\" in relative or ":" in relative or "\0" in relative:
        raise ApiError("backup_path", "The backup contains an unsafe file path")
    parts = relative.split("/")
    if any(not part or part in (".", "..") or part.endswith((".", " ")) for part in parts):
        raise ApiError("backup_path", "The backup contains an unsafe file path")
    candidate = paths.root
    for part in parts:
        candidate = candidate / part
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ApiError("backup_path", "Recovery does not follow symbolic links or Windows junctions", 409)
    if not candidate.resolve().is_relative_to(paths.root):
        raise ApiError("backup_path", "The backup file path leaves this profile")
    return candidate


def original_path(paths, descriptor):
    if not isinstance(descriptor, dict) or not isinstance(descriptor.get("path"), str):
        raise ApiError("backup_path", "An original needs a safe relative library path")
    if descriptor.get("kind") == "chat-attachment":
        match = ATTACHMENT_ORIGINAL.fullmatch(descriptor["path"])
        if not match or descriptor.get("attachment_id") != match[1]:
            raise ApiError("backup_path", "An original is outside its attachment library")
    else:
        match = LIBRARY_ORIGINAL.fullmatch(descriptor["path"])
        if not match or descriptor.get("document_id") != match[1] or descriptor.get("revision_id") != match[2]:
            raise ApiError("backup_path", "An original is outside its document revision library")
    return owned_path(paths, descriptor["path"])


def verify_file(path, descriptor, *, unique=True):
    try:
        lexical = path.lstat()
        if not stat.S_ISREG(lexical.st_mode) or getattr(lexical, "st_file_attributes", 0) & 0x400:
            raise ApiError("backup_path", "Recovery does not follow linked original files")
        with path.open("rb") as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or (unique and info.st_nlink != 1):
                raise ApiError("backup_path", "Recovery requires app-owned regular original files")
            if info.st_size != descriptor["bytes"]:
                raise ApiError("backup_integrity", "An original's exact size does not match its canonical record")
            digest, size = hashlib.sha256(), 0
            while block := source.read(BLOCK):
                size += len(block)
                if size > descriptor["bytes"]:
                    raise ApiError("backup_integrity", "An original changed while it was being verified")
                digest.update(block)
            if size != descriptor["bytes"] or digest.hexdigest() != descriptor["sha256"]:
                raise ApiError("backup_integrity", "An original's SHA-256 does not match its canonical record")
    except OSError:
        raise ApiError("backup_file", "An app-owned original cannot be read; no recovery changes were made", 409, True) from None


def descriptor_for(row, relative, limits=DEFAULT_LIMITS):
    if "attachment_id" in row.keys():
        match = ATTACHMENT_ORIGINAL.fullmatch(relative) if isinstance(relative, str) else None
        if not match or row["attachment_id"] != match[1] or row["role"] != match[2] or \
                (row["role"] == "original" and row["media_type"] != MEDIA[match[3]]):
            raise ApiError("backup_path", "The original path does not match its canonical attachment and media type")
        result = {"kind": "chat-attachment", "path": relative, "original_id": row["id"],
                  "attachment_id": row["attachment_id"], "chat_kind": row["chat_kind"], "chat_id": row["chat_id"]}
    else:
        match = LIBRARY_ORIGINAL.fullmatch(relative) if isinstance(relative, str) else None
        if not match or row["document_id"] != match[1] or row["id"] != match[2] or \
                row["media_type"] != MEDIA[match[3]]:
            raise ApiError("backup_path", "The original path does not match its canonical document and media type")
        result = {"path": relative, "revision_id": row["id"], "document_id": row["document_id"]}
    if type(row["bytes"]) is not int or not 0 <= row["bytes"] <= limits.original_bytes:
        raise ApiError("backup_limit", "An original exceeds the backup file size limit", 413)
    if not isinstance(row["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
        raise ApiError("backup_integrity", "An original needs an exact canonical SHA-256")
    return {**result, "bytes": row["bytes"], "sha256": row["sha256"]}


def descriptor_keys(entry):
    return ({"kind", "path", "original_id", "attachment_id", "chat_kind", "chat_id", "bytes", "sha256"}
            if entry.get("kind") == "chat-attachment" else {"path", "revision_id", "document_id", "bytes", "sha256"})


def validate_descriptor(entry):
    if not isinstance(entry, dict) or set(entry) != descriptor_keys(entry) or \
            any(not isinstance(value, str) for key, value in entry.items() if key != "bytes") or \
            type(entry["bytes"]) is not int:
        raise ApiError("backup_manifest", "An original descriptor has an invalid format")
    if entry.get("kind") == "chat-attachment" and entry["chat_kind"] not in {"learning", "case"}:
        raise ApiError("backup_scope", "An attachment needs a canonical conversation owner")


def original_identity(entry):
    return (("knowledge_attachment_originals", entry["original_id"]) if entry.get("kind") == "chat-attachment"
            else ("knowledge_revisions", entry["revision_id"]))


def original_rows(records):
    documents = {row["id"]: row for row in records.get("knowledge_documents", [])}
    for row in records.get("knowledge_revisions", []):
        document = documents.get(row["document_id"], {})
        yield {**row, "scope_kind": document.get("scope_kind"), "deleted_at": document.get("deleted_at")}
    attachments = {row["id"]: row for row in records.get("knowledge_attachments", [])}
    metadata = {row["attachment_id"]: row for row in records.get("knowledge_attachment_metadata", [])}
    owners = {"learning": {row["id"] for row in records.get("learn_threads", [])},
              "case": {row["id"] for row in records.get("case_sessions", [])}}
    for row in records.get("knowledge_attachment_originals", []):
        parent, meta = attachments.get(row["attachment_id"], {}), metadata.get(row["attachment_id"], {})
        yield {**row, "chat_kind": parent.get("chat_kind"), "chat_id": parent.get("chat_id"),
               "media_type": parent.get("media_type"), "rights_json": meta.get("rights_json"),
               "owner_exists": parent.get("chat_id") in owners.get(parent.get("chat_kind"), set())}


def original_rows_in(conn):
    yield from conn.execute("SELECT r.*,d.scope_kind,d.deleted_at FROM knowledge_revisions r "
                           "JOIN knowledge_documents d ON d.id=r.document_id WHERE r.original_path IS NOT NULL")
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='knowledge_attachment_originals'").fetchone():
        yield from conn.execute("SELECT o.*,a.chat_kind,a.chat_id,a.media_type,m.rights_json,"
            "CASE a.chat_kind WHEN 'learning' THEN EXISTS(SELECT 1 FROM learn_threads WHERE id=a.chat_id) "
            "WHEN 'case' THEN EXISTS(SELECT 1 FROM case_sessions WHERE id=a.chat_id) ELSE 0 END AS owner_exists "
            "FROM knowledge_attachment_originals o JOIN knowledge_attachments a ON a.id=o.attachment_id "
            "LEFT JOIN knowledge_attachment_metadata m ON m.attachment_id=a.id WHERE o.original_path IS NOT NULL")


def original_row_in(conn, entry):
    table, identifier = original_identity(entry)
    if table == "knowledge_revisions":
        return conn.execute("SELECT r.*,d.scope_kind,d.deleted_at FROM knowledge_revisions r "
            "JOIN knowledge_documents d ON d.id=r.document_id WHERE r.id=?", (identifier,)).fetchone()
    return conn.execute("SELECT o.*,a.chat_kind,a.chat_id,a.media_type,m.rights_json,"
        "CASE a.chat_kind WHEN 'learning' THEN EXISTS(SELECT 1 FROM learn_threads WHERE id=a.chat_id) "
        "WHEN 'case' THEN EXISTS(SELECT 1 FROM case_sessions WHERE id=a.chat_id) ELSE 0 END AS owner_exists "
        "FROM knowledge_attachment_originals o JOIN knowledge_attachments a ON a.id=o.attachment_id "
        "LEFT JOIN knowledge_attachment_metadata m ON m.attachment_id=a.id WHERE o.id=?", (identifier,)).fetchone()


def require_original_rights(row, *, code="backup_scope"):
    if "attachment_id" in row.keys():
        retained = row["chat_kind"] in {"learning", "case"} and row["owner_exists"]
    else:
        retained = row["scope_kind"] == "personal-library" and not row["deleted_at"]
    rights = strict_json(row["rights_json"]) if row["rights_json"] else None
    if not retained or not isinstance(rights, dict) or rights.get("cache") is not True or rights.get("display") is not True:
        raise ApiError(code, "Original backup/restore requires a saved owner and local caching/display permission", 409)


def validate_original_row(row, entry, limits):
    validate_descriptor(entry)
    if not row or descriptor_for(row, entry["path"], limits) != entry or row["original_path"] != entry["path"]:
        raise ApiError("backup_manifest", "An original descriptor differs from its canonical owner and bytes")
    require_original_rights(row)


def backup_to(services, output, limits=DEFAULT_LIMITS):
    owned_path(services.paths, output.relative_to(services.paths.root).as_posix())
    conn = services.db.connect()
    try:
        conn.execute("BEGIN")
        bundle = snapshot_in(conn)
        validate_records(conn, bundle)
        records = portable_records(bundle["records"], originals=True)
        deleted = records.get("deletion_ledger", [])
        blocked = blocked_ids(conn, {}, records, deleted)
        # Deleted/indirect records must not carry source contents in a new backup.
        for name, rows in records.items():
            if name != "deletion_ledger":
                from .backup import primary_keys
                keys = primary_keys(conn, name)
                records[name] = [row for row in rows if allow_row(name, row, keys, blocked)]
        originals, total = [], 0
        paths_by_identity = {}
        for row in original_rows(records):
            if not row["original_path"]:
                continue
            require_original_rights(row, code="backup_rights")
            source_path = Path(row["original_path"])
            try:
                relative = source_path.relative_to(services.paths.root).as_posix()
            except ValueError:
                raise ApiError("backup_path", "An original is not app-owned; select a records-only export instead", 409) from None
            descriptor = descriptor_for(row, relative, limits)
            source_path = original_path(services.paths, descriptor)
            verify_file(source_path, descriptor)
            paths_by_identity[original_identity(descriptor)] = relative
            originals.append(descriptor)
            total += descriptor["bytes"]
        for table in ORIGINAL_TABLES:
            for row in records.get(table, []):
                row["original_path"] = paths_by_identity.get((table, row["id"]))
        if len(originals) > limits.originals or total > limits.total_original_bytes:
            raise ApiError("backup_limit", "The original count or expanded backup size exceeds this bounded backup", 413)
        bundle["records"], bundle["data_kind"] = records, "full-backup"
        data = canonical_json(bundle)
        if len(data) > limits.json_bytes:
            raise ApiError("backup_limit", "Canonical JSON exceeds the bounded backup size", 413)
        manifest = {"format": FULL_FORMAT, "format_version": FORMAT_VERSION,
                    "schema_version": SUPPORTED_SCHEMA, "exported_at": bundle["exported_at"],
                    "records": {"path": "records.json", "bytes": len(data),
                                "sha256": hashlib.sha256(data).hexdigest()}, "originals": originals}
        manifest_data = canonical_json(manifest)
        if len(manifest_data) > limits.manifest_bytes:
            raise ApiError("backup_limit", "The backup manifest exceeds its size limit", 413)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6,
                             allowZip64=False) as archive:
            archive.writestr("manifest.json", manifest_data)
            archive.writestr("records.json", data)
            for descriptor in originals:
                path = original_path(services.paths, descriptor)
                digest, size = hashlib.sha256(), 0
                with path.open("rb") as source, archive.open(descriptor["path"], "w") as destination:
                    while block := source.read(BLOCK):
                        size += len(block)
                        if size > descriptor["bytes"]:
                            raise ApiError("backup_integrity", "An original changed during backup; retry")
                        digest.update(block)
                        destination.write(block)
                if size != descriptor["bytes"] or digest.hexdigest() != descriptor["sha256"]:
                    raise ApiError("backup_integrity", "An original changed during backup; retry")
        if output.stat().st_size > limits.archive_bytes:
            raise ApiError("backup_limit", "The ZIP exceeds the bounded archive size", 413)
        return manifest
    except OSError:
        raise ApiError("backup_file", "The backup could not be written; check available disk space", 409, True) from None
    finally:
        conn.rollback()
        conn.close()


def _zip_directory(path, limits):
    """Bound the central directory before ZipFile allocates its member inventory."""
    size = path.stat().st_size
    if not 22 <= size <= limits.archive_bytes:
        raise ApiError("backup_limit", "The ZIP is empty, truncated or exceeds the archive size limit", 413)
    with path.open("rb") as source:
        source.seek(max(0, size - 65557))
        tail = source.read(65557)
    offset = tail.rfind(b"PK\x05\x06")
    if offset < 0 or len(tail) - offset != 22:
        raise ApiError("backup_zip", "Choose a complete Renulus ZIP without trailing data or an archive comment")
    _, disk, directory_disk, disk_count, count, directory_size, directory_offset, comment = struct.unpack(
        "<4s4H2LH", tail[offset:offset + 22])
    eocd = size - len(tail) + offset
    if disk or directory_disk or disk_count != count or comment or count == 65535 or \
            directory_offset + directory_size != eocd:
        raise ApiError("backup_zip", "Split, ZIP64 or inconsistent ZIP directories are not supported")
    if count > limits.originals + 2 or directory_size > 2 * limits.manifest_bytes:
        raise ApiError("backup_limit", "The ZIP has too many members or an oversized directory", 413)
    return directory_offset


def _inventory(archive, path, directory_offset, limits):
    infos = archive.infolist()
    if len(infos) > limits.originals + 2:
        raise ApiError("backup_limit", "The ZIP has too many members", 413)
    seen, total, end = set(), 0, 0
    with path.open("rb") as source:
        for info in sorted(infos, key=lambda item: item.header_offset):
            name = info.filename
            if info.orig_filename != name or name.casefold() in seen:
                raise ApiError("backup_duplicates", "The ZIP contains duplicate or aliased member names")
            seen.add(name.casefold())
            if name not in ("manifest.json", "records.json") and not ORIGINAL.fullmatch(name):
                raise ApiError("backup_path", "The ZIP contains unexpected files or an unsafe member path")
            if info.flag_bits & 0x41:
                raise ApiError("backup_encrypted", "Encrypted backups are not supported; no data was restored")
            mode = stat.S_IFMT(info.external_attr >> 16)
            if info.is_dir() or mode not in (0, stat.S_IFREG):
                raise ApiError("backup_path", "The ZIP cannot contain links, devices or directories")
            if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                raise ApiError("backup_zip", "This ZIP compression method is not supported")
            bound = limits.manifest_bytes if name == "manifest.json" else (
                limits.json_bytes if name == "records.json" else limits.original_bytes)
            if info.file_size > bound or info.compress_size > limits.archive_bytes:
                raise ApiError("backup_limit", "A ZIP member exceeds its expanded size limit", 413)
            if ORIGINAL.fullmatch(name):
                total += info.file_size
                if total > limits.total_original_bytes:
                    raise ApiError("backup_limit", "Expanded originals exceed the backup size limit", 413)
            if info.header_offset != end:
                raise ApiError("backup_zip", "The ZIP has overlapping members or unaccounted data")
            source.seek(info.header_offset)
            header = source.read(30)
            if len(header) != 30:
                raise ApiError("backup_zip", "A ZIP member header is truncated")
            signature, _, flags, method, _, _, crc, compressed, expanded, namesize, extrasize = struct.unpack("<4s5H3L2H", header)
            if signature != b"PK\x03\x04" or flags != info.flag_bits or method != info.compress_type:
                raise ApiError("backup_zip", "Local and central ZIP headers disagree")
            if flags & 0x41:
                raise ApiError("backup_encrypted", "Encrypted backups are not supported")
            if not flags & 8 and (crc, compressed, expanded) != (info.CRC, info.compress_size, info.file_size):
                raise ApiError("backup_zip", "A ZIP member has inconsistent size or CRC headers")
            end = info.header_offset + 30 + namesize + extrasize + info.compress_size
            if flags & 8:
                source.seek(end)
                descriptor = source.read(16)
                if descriptor[:4] == b"PK\x07\x08":
                    values, length = struct.unpack("<3L", descriptor[4:]), 16
                else:
                    values, length = struct.unpack("<3L", descriptor[:12]), 12
                if values != (info.CRC, info.compress_size, info.file_size):
                    raise ApiError("backup_zip", "A ZIP data descriptor is inconsistent")
                end += length
            if end > directory_offset:
                raise ApiError("backup_zip", "A ZIP member overlaps the central directory")
    if end != directory_offset or "manifest.json" not in seen or "records.json" not in seen:
        raise ApiError("backup_zip", "The ZIP is missing its manifest or canonical records")
    return {info.filename: info for info in infos}


def _read_member(archive, info, limit, destination=None, expected=None):
    digest, size, blocks = hashlib.sha256(), 0, []
    with archive.open(info) as source:
        while block := source.read(BLOCK):
            size += len(block)
            if size > limit or size > info.file_size:
                raise ApiError("backup_limit", "A member expands beyond its declared size", 413)
            digest.update(block)
            if destination is None:
                blocks.append(block)
            else:
                destination.write(block)
    if size != info.file_size or (expected and (size != expected["bytes"] or digest.hexdigest() != expected["sha256"])):
        raise ApiError("backup_integrity", "A ZIP member's exact hash or size does not match the manifest")
    return b"".join(blocks) if destination is None else None


@dataclass
class ValidatedArchive:
    directory: Path
    bundle: dict
    originals: list[dict]

    def iter_records(self, services, *, tables=None):
        """Uniform packaging seam; legacy records retain the 16-MiB bound."""
        available = self.bundle["records"]
        names = set(available) if tables is None else set(tables)
        if not names.issubset(available):
            raise ApiError("backup_table", "Select only tables present in the validated canonical preview")
        for name in sorted(names):
            for row in available[name]:
                yield name, dict(row)

    def public(self):
        return {"format": FULL_FORMAT, "exported_at": self.bundle["exported_at"],
                "record_count": sum(len(rows) for rows in self.bundle["records"].values()),
                "original_count": len(self.originals),
                "original_bytes": sum(item["bytes"] for item in self.originals),
                "deletion_notice": DELETION_NOTICE, "omissions": self.bundle.get("omissions", {})}


def validate_archive(services, directory, limits=DEFAULT_LIMITS, *, merge_validator=validate_merge):
    path = directory / "input.zip"
    try:
        owned_path(services.paths, path.relative_to(services.paths.root).as_posix())
        directory_offset = _zip_directory(path, limits)
        with zipfile.ZipFile(path, "r", allowZip64=False) as archive:
            infos = _inventory(archive, path, directory_offset, limits)
            manifest = strict_json(_read_member(archive, infos["manifest.json"], limits.manifest_bytes))
            if not isinstance(manifest, dict) or set(manifest) != {
                    "format", "format_version", "schema_version", "exported_at", "records", "originals"} or \
                    manifest["format"] != FULL_FORMAT or type(manifest["format_version"]) is not int or manifest["format_version"] != FORMAT_VERSION or \
                    not readable_schema(manifest["schema_version"]):
                raise ApiError("backup_format", "This is not a supported full Renulus backup")
            record_entry = manifest["records"]
            if not isinstance(record_entry, dict) or set(record_entry) != {"path", "bytes", "sha256"} or \
                    record_entry["path"] != "records.json" or type(record_entry["bytes"]) is not int or \
                    not isinstance(record_entry["sha256"], str):
                raise ApiError("backup_manifest", "The canonical-record manifest is invalid")
            bundle = strict_json(_read_member(archive, infos["records.json"], limits.json_bytes, expected=record_entry))
            if not isinstance(bundle, dict) or bundle.get("exported_at") != manifest["exported_at"] or \
                    bundle.get("schema_version") != manifest["schema_version"] or bundle.get("data_kind") != "full-backup":
                raise ApiError("backup_manifest", "The manifest and canonical export do not describe the same backup")
            merge_validator(services, bundle)
            entries = manifest["originals"]
            if not isinstance(entries, list) or len(entries) > limits.originals:
                raise ApiError("backup_limit", "The backup has too many original files", 413)
            rows_by_identity = {}
            for row in original_rows(bundle["records"]):
                table = "knowledge_attachment_originals" if "attachment_id" in row else "knowledge_revisions"
                rows_by_identity[(table, row["id"])] = row
            declared, originals, total = {"manifest.json", "records.json"}, [], 0
            verified = directory / "verified"
            verified.mkdir()
            for index, entry in enumerate(entries):
                validate_descriptor(entry)
                validate_original_row(rows_by_identity.get(original_identity(entry)), entry, limits)
                original_path(services.paths, entry)
                if entry["path"] in declared or entry["path"] not in infos:
                    raise ApiError("backup_duplicates", "An original is duplicated or missing from this ZIP")
                declared.add(entry["path"])
                total += entry["bytes"]
                if total > limits.total_original_bytes:
                    raise ApiError("backup_limit", "Expanded originals exceed the backup size limit", 413)
                staged = verified / str(index)
                with staged.open("xb") as destination:
                    _read_member(archive, infos[entry["path"]], limits.original_bytes, destination, entry)
                    destination.flush()
                    os.fsync(destination.fileno())
                originals.append({**entry, "staged": staged})
            if declared != set(infos):
                raise ApiError("backup_manifest", "The ZIP contains files not declared by its manifest")
            if {row["original_path"] for row in rows_by_identity.values() if row["original_path"]} != declared - {"manifest.json", "records.json"}:
                raise ApiError("backup_manifest", "Canonical originals are missing from the backup manifest")
            for name, rows in bundle["records"].items():
                for row in rows:
                    if any(value not in (None, "") for key, value in row.items() if key.endswith("_path")
                           and not (name in ORIGINAL_TABLES and key == "original_path")):
                        raise ApiError("backup_path", "The backup contains a nonportable acquisition or engine path")
            return ValidatedArchive(directory, bundle, originals)
    except (zipfile.BadZipFile, EOFError, zlib.error, struct.error, RuntimeError, NotImplementedError):
        raise ApiError("backup_zip", "The ZIP is corrupt or unsupported; no data was restored") from None
    except OSError:
        raise ApiError("backup_file", "The backup cannot be staged; check disk space and retry", 409, True) from None
