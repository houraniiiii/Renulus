# SPDX-License-Identifier: MIT
"""Additive full ZIP format 2: table JSONL segments and canonical disk staging."""
from contextlib import closing, ExitStack
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import sqlite3
import struct
import zipfile
import zlib

from ..contracts import ApiError
from .backup import (DELETION_NOTICE, portable_records, snapshot_omissions, validate_records)
from .database import SUPPORTED_SCHEMA, utc_now
from .recovery_archive import (BLOCK, FULL_FORMAT, _read_member, canonical_json,
                               descriptor_for, original_path, owned_path,
                               strict_json, validate_archive, verify_file)
from .recovery_limits import SEGMENTED_LIMITS
from .recovery_records import (check_workspace, copy_snapshot, insert_row,
                               installed_schema, line_for, prune_deleted, quoted,
                               scratch, validate_staged_merge, validate_stream_row)
from .recovery_files import STAGED
from .recovery_zip import SEGMENT, directory as zip_directory, zip_infos

VERSION = 2
SHA256 = re.compile(r"[0-9a-f]{64}")


def file_digest(path):
    digest, size = hashlib.sha256(), 0
    with path.open("rb") as source:
        while block := source.read(BLOCK):
            size += len(block)
            digest.update(block)
    return {"bytes": size, "sha256": digest.hexdigest()}


def _originals(conn, services, limits):
    entries, total = [], 0
    for row in conn.execute("SELECT r.*,d.scope_kind,d.deleted_at FROM knowledge_revisions r JOIN knowledge_documents d ON d.id=r.document_id WHERE r.original_path IS NOT NULL"):
        if row["scope_kind"] != "personal-library" or row["deleted_at"]:
            raise ApiError("backup_scope", "Only retained personal-library originals can be backed up")
        entry = descriptor_for(row, row["original_path"], limits)
        rights = strict_json(row["rights_json"])
        if not isinstance(rights, dict) or rights.get("cache") is not True or rights.get("display") is not True:
            raise ApiError("backup_rights", "Original backup requires local caching and display permission", 403)
        original_path(services.paths, entry)
        total += entry["bytes"]
        entries.append(entry)
        if len(entries) > limits.originals or total > limits.total_original_bytes:
            raise ApiError("backup_limit", "Originals exceed the format-2 count or expanded-byte budget", 413)
    return entries


def _write_original(archive, paths, entry):
    path = original_path(paths, entry)
    verify_file(path, entry)
    info = zipfile.ZipInfo(entry["path"])
    info.compress_type, info.file_size = zipfile.ZIP_DEFLATED, entry["bytes"]
    digest, size = hashlib.sha256(), 0
    with path.open("rb") as source, archive.open(info, "w") as destination:
        while block := source.read(BLOCK):
            size += len(block)
            if size > entry["bytes"]:
                raise ApiError("backup_integrity", "An original changed during backup; retry")
            digest.update(block)
            destination.write(block)
    if size != entry["bytes"] or digest.hexdigest() != entry["sha256"]:
        raise ApiError("backup_integrity", "An original changed during backup; retry")


def backup_segmented_to(services, output, limits=SEGMENTED_LIMITS):
    """Stream to an owned fresh directory while holding Recovery.mutation()."""
    owned_path(services.paths, output.relative_to(services.paths.root).as_posix())
    stage_path = output.parent / "snapshot.sqlite3"
    try:
        with closing(services.db.connect()) as source:
            source.execute("BEGIN")  # One consistent WAL snapshot, under owner guards.
            definitions = installed_schema(source, limits)
            exported_at, omissions = utc_now(), snapshot_omissions(source)
            with closing(scratch(stage_path, definitions, limits)) as stage:
                copy_snapshot(source, stage, definitions, limits, paths=services.paths)
                # Transitive deletion filtering also happens before exporting files.
                prune_deleted(stage, definitions, limits)
                originals = _originals(stage, services, limits)
                counts, segments, canonical_bytes = {}, [], 0
                with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED,
                                     compresslevel=6, allowZip64=True) as archive:
                    for name, table in definitions.items():
                        counts[name] = 0
                        destination, entry, digest, number = None, None, None, 0
                        try:
                            for row in stage.execute(f'SELECT * FROM {quoted(name)} ORDER BY rowid'):
                                line = line_for(dict(row), limits)
                                if destination is None or entry["bytes"] + len(line) > limits.segment_bytes:
                                    if destination is not None:
                                        destination.close()
                                        entry["sha256"] = digest.hexdigest()
                                        segments.append(entry)
                                    if len(segments) >= limits.segments:
                                        raise ApiError("backup_limit", "Canonical segment inventory exceeds format 2", 413)
                                    entry = {"path": f"canonical/{name}/{number:06d}.jsonl", "table": name,
                                             "bytes": 0, "records": 0}
                                    info = zipfile.ZipInfo(entry["path"])
                                    info.compress_type = zipfile.ZIP_DEFLATED
                                    destination = archive.open(info, "w")
                                    digest = hashlib.sha256()
                                    number += 1
                                destination.write(line)
                                digest.update(line)
                                entry["bytes"] += len(line)
                                entry["records"] += 1
                                counts[name] += 1
                                canonical_bytes += len(line)
                                if canonical_bytes > limits.canonical_bytes or sum(counts.values()) > limits.records:
                                    raise ApiError("backup_limit", "Canonical data exceeds the format-2 aggregate budget", 413)
                            if destination is not None:
                                destination.close()
                                destination = None
                                entry["sha256"] = digest.hexdigest()
                                segments.append(entry)
                        finally:
                            if destination is not None:
                                destination.close()
                        if output.stat().st_size > limits.archive_bytes:
                            raise ApiError("backup_limit", "The compressed archive exceeds format 2", 413)
                        check_workspace(output.parent, limits)
                    canonical = {"bytes": canonical_bytes, "records": sum(counts.values()),
                                 "tables": counts, "segments": segments}
                    manifest = {"format": FULL_FORMAT, "format_version": VERSION,
                                "schema_version": SUPPORTED_SCHEMA, "exported_at": exported_at,
                                "canonical": canonical, "originals": originals, "omissions": omissions}
                    manifest_data = canonical_json(manifest)
                    if len(manifest_data) > limits.manifest_bytes:
                        raise ApiError("backup_limit", "The format-2 manifest exceeds its metadata budget", 413)
                    if canonical_bytes + sum(entry["bytes"] for entry in originals) + len(manifest_data) > limits.expanded_bytes:
                        raise ApiError("backup_limit", "Canonical data and originals exceed the format-2 expanded archive budget", 413)
                    for entry in originals:
                        _write_original(archive, services.paths, entry)
                        if output.stat().st_size > limits.archive_bytes:
                            raise ApiError("backup_limit", "The compressed archive exceeds format 2", 413)
                    archive.writestr("manifest.json", manifest_data)
            source.rollback()
        stage_path.unlink()
        # Validate our ZIP64/header envelope too, including final central metadata.
        zip_directory(output, limits)
        check_workspace(output.parent, limits)
        return manifest
    except sqlite3.DatabaseError:
        raise ApiError("backup_records", "Canonical disk staging failed or exceeded its finite database budget", 409, True) from None
    except OSError:
        raise ApiError("backup_file", "Backup disk staging failed; check available space and retry", 409, True) from None


def _metadata(manifest, definitions, limits):
    if not isinstance(manifest, dict) or set(manifest) != {
            "format", "format_version", "schema_version", "exported_at", "canonical", "originals", "omissions"} or \
            manifest["format"] != FULL_FORMAT or type(manifest["format_version"]) is not int or manifest["format_version"] != VERSION:
        raise ApiError("backup_format", "This is not a supported segmented Renulus backup")
    bundle = {"format": "renulus-canonical-export", "format_version": 1,
              "schema_version": manifest["schema_version"], "exported_at": manifest["exported_at"],
              "data_kind": "full-backup", "records": {}, "artifacts": {}, "omissions": manifest["omissions"]}
    # Reuse the legacy public date/schema/omission contract without reading rows.
    # A trusted schema-only scratch connection validates this below in the caller.
    canonical = manifest["canonical"]
    if not isinstance(canonical, dict) or set(canonical) != {"bytes", "records", "tables", "segments"} or \
            type(canonical["bytes"]) is not int or not 0 <= canonical["bytes"] <= limits.canonical_bytes or \
            type(canonical["records"]) is not int or not 0 <= canonical["records"] <= limits.records:
        raise ApiError("backup_limit", "The canonical declaration exceeds format-2 budgets", 413)
    tables, segments = canonical["tables"], canonical["segments"]
    if not isinstance(tables, dict) or len(tables) > limits.tables or any(name not in definitions or type(count) is not int or not 0 <= count <= limits.records for name, count in tables.items()):
        raise ApiError("backup_table", "The backup contains an unsupported canonical table/count")
    if sum(tables.values()) != canonical["records"] or not isinstance(segments, list) or len(segments) > limits.segments:
        raise ApiError("backup_manifest", "Canonical table/segment counts disagree")
    counts, total, sequences, previous = {name: 0 for name in tables}, 0, {}, None
    for entry in segments:
        if not isinstance(entry, dict) or set(entry) != {"path", "table", "bytes", "records", "sha256"} or \
                not isinstance(entry["table"], str) or entry["table"] not in tables or not isinstance(entry["path"], str) or \
                type(entry["bytes"]) is not int or not 0 < entry["bytes"] <= limits.segment_bytes or \
                type(entry["records"]) is not int or not 0 < entry["records"] <= limits.records or \
                not isinstance(entry["sha256"], str) or not SHA256.fullmatch(entry["sha256"]):
            raise ApiError("backup_manifest", "A canonical segment descriptor is invalid or oversized")
        name = entry["table"]
        sequence = sequences.get(name, 0)
        if entry["path"] != f"canonical/{name}/{sequence:06d}.jsonl" or previous is not None and name < previous:
            raise ApiError("backup_path", "Canonical segment paths must have ordered, unique table identities")
        previous, sequences[name] = name, sequence + 1
        counts[name] += entry["records"]
        total += entry["bytes"]
    if counts != tables or total != canonical["bytes"]:
        raise ApiError("backup_manifest", "Canonical segment totals disagree with their table manifest")
    return bundle


@dataclass
class ValidatedSegmentedArchive:
    directory: Path
    bundle: dict
    originals: list[dict]
    stage: Path
    stage_identity: dict
    manifest: dict
    limits: object

    def public(self):
        return {"format": FULL_FORMAT, "format_version": VERSION,
                "exported_at": self.bundle["exported_at"],
                "record_count": self.manifest["canonical"]["records"],
                "canonical_bytes": self.manifest["canonical"]["bytes"],
                "original_count": len(self.originals), "original_bytes": sum(entry["bytes"] for entry in self.originals),
                "deletion_notice": DELETION_NOTICE, "omissions": self.bundle["omissions"]}

    def verify_stage(self, paths):
        owned_path(paths, self.stage.relative_to(paths.root).as_posix())
        verify_file(self.stage, self.stage_identity)

    def iter_records(self, services, *, tables=None):
        """One validated portable row at a time; no original or provider scan."""
        yield from _iter_stage(self, services, self.manifest["canonical"]["tables"], tables)


def _iter_stage(validated, services, available, selected):
    validated.verify_stage(services.paths)
    names = set(available) if selected is None else set(selected)
    if not names.issubset(available):
        raise ApiError("backup_table", "Select only tables present in the validated canonical stage")
    with closing(sqlite3.connect(validated.stage)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        conn.execute("PRAGMA cache_size=-2048")
        for name in sorted(names):
            for row in conn.execute(f'SELECT * FROM {quoted(name)} ORDER BY rowid'):
                yield name, dict(row)


@dataclass
class ValidatedRecordStage:
    """Local iterable-record staging; not an archive or external API protocol."""
    directory: Path
    bundle: dict
    originals: list[dict]
    stage: Path
    stage_identity: dict
    tables: dict
    canonical_bytes: int
    limits: object
    archive_version: int = VERSION
    data_format: str = "renulus-canonical-record-stage"

    def verify_stage(self, paths):
        owned_path(paths, self.stage.relative_to(paths.root).as_posix())
        verify_file(self.stage, self.stage_identity)

    def iter_records(self, services, *, tables=None):
        yield from _iter_stage(self, services, self.tables, tables)

    def public(self):
        result = {"format": self.data_format,
                "exported_at": self.bundle["exported_at"], "record_count": sum(self.tables.values()),
                "original_count": len(self.originals),
                "original_bytes": sum(entry["bytes"] for entry in self.originals),
                "deletion_notice": DELETION_NOTICE, "omissions": self.bundle["omissions"]}
        if self.archive_version == VERSION:
            result.update(format_version=VERSION, canonical_bytes=self.canonical_bytes)
        return result


def stage_legacy_bundle(services, directory, bundle, limits=SEGMENTED_LIMITS):
    """Keep legacy incoming bounds while merging into a bounded disk target."""
    owned_path(services.paths, directory.relative_to(services.paths.root).as_posix())
    try:
        with closing(services.db.connect()) as source:
            records = validate_records(source, bundle)
            definitions = installed_schema(source, limits)
        path = directory / "records.sqlite3"
        size, counts = 0, {name: 0 for name in definitions}
        with closing(scratch(path, definitions, limits)) as stage:
            stage.execute("BEGIN")
            for name, rows in records.items():
                for row in rows:
                    portable = portable_records({name: [row]}, originals=bundle.get("data_kind") == "full-backup")[name][0]
                    validate_stream_row(name, portable, definitions[name], limits, portable=True)
                    size += len(line_for(portable, limits))
                    if size > limits.canonical_bytes:
                        raise ApiError("backup_limit", "Canonical legacy input exceeds the bounded disk stage", 413)
                    insert_row(stage, name, portable, definitions[name])
                    counts[name] += 1
            stage.commit()
        validate_staged_merge(services, path, definitions, directory, limits, bundle["exported_at"])
        metadata = {**bundle, "records": {}, "omissions": bundle.get("omissions", {})}
        return ValidatedRecordStage(directory, metadata, [], path, file_digest(path), counts, size, limits,
            archive_version=1, data_format=FULL_FORMAT)
    except sqlite3.DatabaseError:
        raise ApiError("backup_references", "Legacy canonical records have invalid links or cannot be staged; no records were restored") from None
    except OSError:
        raise ApiError("backup_file", "Legacy backup disk staging failed; check available space and retry", 409, True) from None


def stage_record_rows(services, directory, records, *, exported_at, omissions=None, originals=(), limits=SEGMENTED_LIMITS):
    """Validate an iterable selection and verified original copies before restore.

    Use Recovery.preview_records() to own the directory/token lifecycle. Originals
    must come from a verified preview under the SAME services profile. Selection
    policy belongs to the caller; all canonical constraints/quotas still apply.
    Input iterators are consumed and closed, including on validation failure.
    """
    try:
        with ExitStack() as iterators:
            records, originals = iter(records), iter(originals)
            for iterator in (records, originals):
                close = getattr(iterator, "close", None)
                if callable(close):
                    iterators.callback(close)
            return _stage_record_rows(services, directory, records, exported_at=exported_at,
                omissions=omissions, originals=originals, limits=limits)
    except sqlite3.DatabaseError:
        raise ApiError("backup_references", "The selected canonical records have invalid links or cannot be staged; no records were restored") from None
    except OSError:
        raise ApiError("backup_file", "Selected records/originals cannot be staged; check disk space and retry", 409, True) from None


def _stage_record_rows(services, directory, records, *, exported_at, omissions, originals, limits):
    owned_path(services.paths, directory.relative_to(services.paths.root).as_posix())
    with closing(services.db.connect()) as source:
        definitions = installed_schema(source, limits)
    stage_path = directory / "records.sqlite3"
    bundle = {"format": "renulus-canonical-export", "format_version": 1, "schema_version": SUPPORTED_SCHEMA,
              "exported_at": exported_at, "data_kind": "full-backup", "records": {}, "artifacts": {},
              "omissions": {} if omissions is None else omissions}
    counts, size, originals_size, selected = {name: 0 for name in definitions}, 0, 0, []
    with closing(scratch(stage_path, definitions, limits)) as stage:
        validate_records(stage, bundle)
        stage.execute("BEGIN")
        try:
            count = 0
            for name, row in records:
                if name not in definitions:
                    raise ApiError("backup_table", "The selected records contain an unsupported canonical table")
                validate_stream_row(name, row, definitions[name], limits, portable=True)
                size += len(line_for(row, limits))
                count += 1
                if count > limits.records or size > limits.canonical_bytes:
                    raise ApiError("backup_limit", "The selected canonical records exceed format 2", 413)
                insert_row(stage, name, row, definitions[name])
                counts[name] += 1
            stage.commit()
        except BaseException:
            stage.rollback()
            raise
        verified = directory / "verified"
        verified.mkdir()
        declared = set()
        for number, source_entry in enumerate(originals):
            if number >= limits.originals:
                raise ApiError("backup_limit", "Selected originals exceed the format-2 count budget", 413)
            if not isinstance(source_entry, dict) or set(source_entry) != {"path", "document_id", "revision_id", "bytes", "sha256", "staged"}:
                raise ApiError("backup_manifest", "Select verified original descriptors with their owned staged paths")
            entry = {key: value for key, value in source_entry.items() if key != "staged"}
            if any(not isinstance(entry[key], str) for key in ("path", "document_id", "revision_id", "sha256")) or type(entry["bytes"]) is not int:
                raise ApiError("backup_manifest", "A selected original has invalid field types")
            row = stage.execute("SELECT r.*,d.scope_kind,d.deleted_at FROM knowledge_revisions r JOIN knowledge_documents d ON d.id=r.document_id WHERE r.id=?", (entry["revision_id"],)).fetchone()
            if not row or descriptor_for(row, entry["path"], limits) != entry or row["original_path"] != entry["path"]:
                raise ApiError("backup_manifest", "A selected original is not bound to a retained canonical revision")
            rights = strict_json(row["rights_json"])
            if row["scope_kind"] != "personal-library" or row["deleted_at"] or not isinstance(rights, dict) or rights.get("cache") is not True or rights.get("display") is not True:
                raise ApiError("backup_scope", "A selected original lacks retained Library scope or caching/display permission")
            original_path(services.paths, entry)
            if entry["path"] in declared:
                raise ApiError("backup_duplicates", "Selected originals repeat a canonical file identity")
            declared.add(entry["path"])
            if not isinstance(source_entry["staged"], Path):
                raise ApiError("backup_path", "A selected original must use its verified owned preview path")
            try:
                relative = source_entry["staged"].relative_to(services.paths.root).as_posix()
            except ValueError:
                raise ApiError("backup_path", "Selected original bytes must remain inside this scratch profile's verified previews") from None
            if not STAGED.fullmatch(relative):
                raise ApiError("backup_path", "A selected original is outside verified preview staging")
            source_path = owned_path(services.paths, relative)
            verify_file(source_path, entry)
            originals_size += entry["bytes"]
            if originals_size > limits.total_original_bytes or originals_size + size > limits.expanded_bytes:
                raise ApiError("backup_limit", "Selected originals/canonical data exceed format 2", 413)
            destination_path = verified / str(number)
            digest, copied = hashlib.sha256(), 0
            with source_path.open("rb") as source, destination_path.open("xb") as destination:
                while block := source.read(BLOCK):
                    copied += len(block)
                    if copied > entry["bytes"]:
                        raise ApiError("backup_integrity", "A selected original changed while it was copied")
                    digest.update(block)
                    destination.write(block)
                destination.flush()
                os.fsync(destination.fileno())
            if copied != entry["bytes"] or digest.hexdigest() != entry["sha256"]:
                raise ApiError("backup_integrity", "A selected original changed while it was copied")
            selected.append({**entry, "staged": destination_path})
            if number % 32 == 0:
                check_workspace(directory, limits)
        if stage.execute("SELECT COUNT(*) FROM knowledge_revisions WHERE original_path IS NOT NULL").fetchone()[0] != len(selected):
            raise ApiError("backup_manifest", "Selected canonical originals are missing their verified bytes")
    validate_staged_merge(services, stage_path, definitions, directory, limits, exported_at)
    return ValidatedRecordStage(directory, bundle, selected, stage_path, file_digest(stage_path), counts, size, limits)


def _stage_segments(archive, infos, manifest, stage, definitions, limits, directory):
    counts, total = {name: 0 for name in manifest["canonical"]["tables"]}, 0
    stage.execute("BEGIN")
    try:
        for entry in manifest["canonical"]["segments"]:
            digest, size, records = hashlib.sha256(), 0, 0
            info = infos.get(entry["path"])
            if not info or info.file_size != entry["bytes"]:
                raise ApiError("backup_integrity", "A canonical segment is missing or has a different exact size")
            with archive.open(info) as source:
                while line := source.readline(limits.row_bytes + 1):
                    size += len(line)
                    if not line.endswith(b"\n") or len(line) > limits.row_bytes or size > entry["bytes"] or records >= entry["records"]:
                        raise ApiError("backup_limit", "A canonical segment exceeds its bounded row/record/byte declaration", 413)
                    row = strict_json(line)
                    validate_stream_row(entry["table"], row, definitions[entry["table"]], limits, portable=True)
                    insert_row(stage, entry["table"], row, definitions[entry["table"]])
                    digest.update(line)
                    records += 1
                    if records % 512 == 0:
                        check_workspace(directory, limits)
            if size != entry["bytes"] or records != entry["records"] or digest.hexdigest() != entry["sha256"]:
                raise ApiError("backup_integrity", "A canonical segment's exact hash, bytes or record count differs")
            total += size
            counts[entry["table"]] += records
        if counts != manifest["canonical"]["tables"] or total != manifest["canonical"]["bytes"]:
            raise ApiError("backup_integrity", "Canonical staged totals differ from the manifest")
        stage.commit()
    except BaseException:
        stage.rollback()
        raise


def _stage_originals(services, archive, infos, manifest, stage, directory, limits):
    entries = manifest["originals"]
    if not isinstance(entries, list) or len(entries) > limits.originals:
        raise ApiError("backup_limit", "The backup exceeds the format-2 original-count budget", 413)
    declared = {"manifest.json", *(entry["path"] for entry in manifest["canonical"]["segments"])}
    verified = directory / "verified"
    verified.mkdir()
    originals, total = [], 0
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) != {"path", "document_id", "revision_id", "bytes", "sha256"} or \
                any(not isinstance(entry[key], str) for key in ("path", "document_id", "revision_id", "sha256")) or type(entry["bytes"]) is not int:
            raise ApiError("backup_manifest", "An original descriptor has an invalid format")
        row = stage.execute("SELECT r.*,d.scope_kind,d.deleted_at FROM knowledge_revisions r JOIN knowledge_documents d ON d.id=r.document_id WHERE r.id=?", (entry["revision_id"],)).fetchone()
        if not row or descriptor_for(row, entry["path"], limits) != entry or row["original_path"] != entry["path"]:
            raise ApiError("backup_manifest", "An original descriptor differs from its canonical revision")
        rights = strict_json(row["rights_json"])
        if row["scope_kind"] != "personal-library" or row["deleted_at"] or not isinstance(rights, dict) or rights.get("cache") is not True or rights.get("display") is not True:
            raise ApiError("backup_scope", "An original lacks retained Library scope or caching/display permission")
        original_path(services.paths, entry)
        if entry["path"] in declared or entry["path"] not in infos:
            raise ApiError("backup_duplicates", "An original is duplicated or missing from the ZIP")
        declared.add(entry["path"])
        total += entry["bytes"]
        if total > limits.total_original_bytes:
            raise ApiError("backup_limit", "Expanded originals exceed the format-2 total budget", 413)
        staged = verified / str(index)
        with staged.open("xb") as destination:
            _read_member(archive, infos[entry["path"]], limits.original_bytes, destination, entry)
            destination.flush()
            os.fsync(destination.fileno())
        originals.append({**entry, "staged": staged})
        if index % 32 == 0 or index + 1 == len(entries):
            check_workspace(directory, limits)
    if declared != set(infos):
        raise ApiError("backup_manifest", "The ZIP contains files not bound by its manifest")
    if stage.execute("SELECT COUNT(*) FROM knowledge_revisions WHERE original_path IS NOT NULL").fetchone()[0] != len(entries):
        raise ApiError("backup_manifest", "Canonical originals are missing from the manifest")
    return originals


def validate_archive_auto(services, directory, legacy_limits, limits=SEGMENTED_LIMITS):
    path = owned_path(services.paths, (directory / "input.zip").relative_to(services.paths.root).as_posix())
    try:
        inventory = zip_directory(path, limits)
        with zipfile.ZipFile(path, "r", allowZip64=True) as archive:
            infos = zip_infos(archive, inventory)
            manifest = strict_json(_read_member(archive, infos["manifest.json"], limits.manifest_bytes))
            if isinstance(manifest, dict) and type(manifest.get("format_version")) is int and manifest["format_version"] == 1:
                # Format 1 still enforces its own unchanged JSON/ZIP/header caps.
                staged = None
                def validate_legacy(services, bundle):
                    nonlocal staged
                    staged = stage_legacy_bundle(services, directory, bundle, limits)
                validated = validate_archive(services, directory, legacy_limits, merge_validator=validate_legacy)
                staged.originals = validated.originals
                return staged
            with closing(services.db.connect()) as source:
                definitions = installed_schema(source, limits)
            bundle = _metadata(manifest, definitions, limits)
            stage_path = directory / "records.sqlite3"
            with closing(scratch(stage_path, definitions, limits)) as stage:
                validate_records(stage, bundle)
                _stage_segments(archive, infos, manifest, stage, definitions, limits, directory)
                originals = _stage_originals(services, archive, infos, manifest, stage, directory, limits)
        validate_staged_merge(services, stage_path, definitions, directory, limits, bundle["exported_at"])
        return ValidatedSegmentedArchive(directory, bundle, originals, stage_path, file_digest(stage_path), manifest, limits)
    except sqlite3.DatabaseError:
        raise ApiError("backup_references", "Canonical disk validation failed or has invalid linked records; no records were restored") from None
    except (zipfile.BadZipFile, EOFError, zlib.error, struct.error, RuntimeError, NotImplementedError):
        raise ApiError("backup_zip", "The ZIP is corrupt or unsupported; no data was restored") from None
    except OSError:
        raise ApiError("backup_file", "The backup cannot be staged; check disk space and retry", 409, True) from None
