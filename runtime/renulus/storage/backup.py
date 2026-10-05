"""Canonical record snapshots and transactional deletion reconciliation.

The JSON route deliberately has no original files. The ZIP adapter supplies
verified, rebased original paths to the same reconciliation code.
"""
from collections import defaultdict, deque
from datetime import datetime
import json
import math
import re
import sqlite3

from renulus.contracts import ApiError
from .database import SUPPORTED_SCHEMA, utc_now

FORMAT_VERSION = 1
MAX_RECORDS = 100_000
MAX_JSON_BYTES = 16 * 1024 * 1024
SAFE_PREFIXES = ("content_", "learn_", "case_", "cases_", "assessment_",
                 "memory_", "study_", "knowledge_", "library_", "update_")
COMMON_TABLES = {"learning_evidence", "deletion_ledger", "preferences"}
SAFE_PREFERENCES = {"study.goals", "memory.enabled", "learn.teaching_style"}
CATALOGUE_OMISSION = (
    "Acquisition catalogue is input metadata tied to external collection paths; "
    "retained library metadata remains in knowledge_documents and knowledge_revisions."
)
EXTRACTION_OMISSION = (
    "Structured extraction documents are rebuildable from retained originals; "
    "canonical passage text, headings and physical source locators are retained."
)
DELETION_NOTICE = (
    "This backup carries only deletion markers known at its export date. "
    "On a new installation it cannot know later deletions. Restoring merges "
    "records and preserves newer deletion markers available in this profile. "
    "Derived indexes must be rebuilt using installed offline helpers."
)


def eligible_table(name):
    return isinstance(name, str) and bool(re.fullmatch(r"[a-z][a-z0-9_]*", name)) and (
        name in COMMON_TABLES or name.startswith(SAFE_PREFIXES)) and name != "knowledge_catalogue" and not re.search(
            r"(?:^|_)(?:credentials?|secrets?|connections?|provider_settings|index(?:es)?)(?:_|$)", name)


def primary_keys(conn, table):
    return [row["name"] for row in sorted(
        conn.execute(f'PRAGMA table_info("{table}")'), key=lambda row: row["pk"])
        if row["pk"]]


def record_references(row):
    return [value for key, value in row.items()
            if (key == "id" or key.endswith("_id")) and isinstance(value, str)]


def snapshot_in(conn, *, originals=True):
    """Read only canonical tables; never read provider settings or credentials."""
    names = [row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        if eligible_table(row[0])]
    records, count, size = {}, 0, 0
    for name in names:
        if name == 'case_attachment_parts' and not originals:
            records[name] = []
            continue
        if name == "preferences":
            placeholders = ",".join("?" for _ in SAFE_PREFERENCES)
            rows = conn.execute(f'SELECT * FROM preferences WHERE key IN ({placeholders})',
                                tuple(sorted(SAFE_PREFERENCES)))
        else:
            available = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            if available > MAX_RECORDS - count:
                raise ApiError("backup_limit", "Canonical learning records exceed the bounded 100,000-record recovery scope", 413)
            order = " ORDER BY rowid" if name == "knowledge_source_status_events" else ""
            projection = "*"
            if name == "knowledge_revisions":
                projection = ",".join('NULL AS extraction_json' if row["name"] == "extraction_json"
                    else '"' + row["name"] + '"' for row in conn.execute(f'PRAGMA table_info("{name}")'))
            rows = conn.execute(f'SELECT {projection} FROM "{name}"{order}')
        records[name] = []
        for row in rows:
            count += 1
            copied = dict(row)
            try:
                size += len(json.dumps(copied, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")) + 1
            except (ValueError, TypeError, UnicodeError):
                raise ApiError("backup_records", "Canonical learning records contain unsupported scalar values") from None
            if count > MAX_RECORDS or size > MAX_JSON_BYTES:
                raise ApiError("backup_limit", "Canonical learning records exceed this bounded recovery's JSON or record limit", 413)
            records[name].append(copied)
    return {"format": "renulus-canonical-export", "format_version": FORMAT_VERSION,
            "schema_version": SUPPORTED_SCHEMA, "exported_at": utc_now(),
            "data_kind": "records-only", "records": records, "artifacts": {},
            "limits": DELETION_NOTICE, "omissions": snapshot_omissions(conn, originals=originals)}


def snapshot_omissions(conn, *, originals=True):
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='knowledge_catalogue'").fetchone()
    count = conn.execute("SELECT COUNT(*) FROM knowledge_catalogue").fetchone()[0] if exists else 0
    result = {"knowledge_catalogue": {"records": count, "reason": CATALOGUE_OMISSION}}
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='knowledge_revisions'").fetchone()
    if exists:
        count = conn.execute("SELECT COUNT(*) FROM knowledge_revisions WHERE extraction_json IS NOT NULL").fetchone()[0]
        result["knowledge_extractions"] = {"records": count, "reason": EXTRACTION_OMISSION}
    if not originals:
        exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='case_attachments'").fetchone()
        if exists:
            count = conn.execute('SELECT COUNT(*) FROM case_attachments').fetchone()[0]
            result['case_originals'] = {'records': count,
                'reason': 'Records-only export retains case attachment metadata. Original bytes require a full backup including originals.'}
    return result


def portable_records(records, *, originals=False):
    """Drop acquisition paths and all unattached/records-only file references."""
    result = {}
    for name, rows in records.items():
        result[name] = []
        if name == 'case_attachment_parts' and not originals:
            continue
        for row in rows:
            copied = dict(row)
            if name == "knowledge_revisions" and "extraction_json" in copied:
                copied["extraction_json"] = None
            for key in copied:
                if key.endswith("_path"):
                    if originals and name == "knowledge_revisions" and key == "original_path":
                        continue
                    copied[key] = "" if name == "knowledge_catalogue" else None
            result[name].append(copied)
    return result


def export_records(services):
    conn = services.db.connect()
    try:
        conn.execute("BEGIN")
        bundle = snapshot_in(conn, originals=False)
        bundle["records"] = portable_records(bundle["records"])
        return bundle
    finally:
        conn.rollback()
        conn.close()


def records_only_bundle(bundle):
    """Accept earlier JSON exports while explicitly omitting acquisition input."""
    if not isinstance(bundle, dict) or not isinstance(bundle.get("records"), dict):
        return bundle
    records = dict(bundle["records"])
    catalogue = records.pop("knowledge_catalogue", None)
    if catalogue is not None and not isinstance(catalogue, list):
        raise ApiError("backup_table", "The acquisition catalogue must be a record list")
    omissions = bundle.get("omissions", {})
    if catalogue is not None:
        if not isinstance(omissions, dict):
            raise ApiError("backup_format", "The export has invalid omission metadata")
        omissions = {**omissions, "knowledge_catalogue": {"records": len(catalogue), "reason": CATALOGUE_OMISSION}}
    return {**bundle, "records": records, "omissions": omissions}


def validate_date(value):
    try:
        if not isinstance(value, str) or len(value) > 64:
            raise ValueError
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError
    except (ValueError, TypeError):
        raise ApiError("backup_date", "The backup needs a valid dated export with a time zone") from None
    return value


def validate_record_row(name, row, info):
    """Shared scalar/scope contract; callers bound rows and enforce identities."""
    if not isinstance(row, dict) or set(row) != {column["name"] for column in info}:
        raise ApiError("backup_columns", "The export record schema does not match this app")
    if any(type(value) not in (str, int, float, type(None)) or
           (isinstance(value, float) and not math.isfinite(value)) or
           (type(value) is int and not -(2**63) <= value < 2**63) for value in row.values()):
        raise ApiError("backup_records", "Canonical record values must be finite SQLite scalars")
    for column in info:
        value = row[column["name"]]
        if value is None and (column["notnull"] or column["pk"]):
            raise ApiError("backup_records", "A required canonical field is missing")
        if value is not None and column["type"].upper() == "INTEGER" and type(value) is not int:
            raise ApiError("backup_records", "An integer canonical field has an invalid value")
        if value is not None and column["type"].upper() == "TEXT" and not isinstance(value, str):
            raise ApiError("backup_records", "A text canonical field has an invalid value")
    if name == "preferences" and row["key"] not in SAFE_PREFERENCES:
        raise ApiError("backup_preference", "Connection settings and credentials cannot be restored from learning exports")
    if row.get("scope_kind") in ("temporary-case", "unclassified") or row.get("scope") in ("temporary-case", "unclassified"):
        raise ApiError("backup_scope", "Temporary and unclassified data cannot be restored")


def validate_records(conn, bundle):
    if not isinstance(bundle, dict) or bundle.get("format") != "renulus-canonical-export" or \
            type(bundle.get("format_version")) is not int or bundle["format_version"] != FORMAT_VERSION:
        raise ApiError("backup_format", "This is not a supported Renulus export")
    if type(bundle.get("schema_version")) is not int or bundle["schema_version"] != SUPPORTED_SCHEMA:
        raise ApiError("backup_schema", "Install a compatible app version before restoring this export")
    validate_date(bundle.get("exported_at"))
    if set(bundle) - {"format", "format_version", "schema_version", "exported_at", "data_kind",
                      "records", "artifacts", "limits", "omissions"} or bundle.get("artifacts", {}) != {}:
        raise ApiError("backup_format", "The export contains unsupported data outside canonical records")
    records = bundle.get("records")
    if not isinstance(records, dict):
        raise ApiError("backup_records", "The export has invalid canonical records")
    if bundle.get("data_kind", "records-only") not in ("records-only", "full-backup"):
        raise ApiError("backup_format", "The canonical export has an unsupported data kind")
    omissions = bundle.get("omissions", {})
    reasons = {"knowledge_catalogue": CATALOGUE_OMISSION, "knowledge_extractions": EXTRACTION_OMISSION}
    if not isinstance(omissions, dict) or set(omissions) - set(reasons):
        raise ApiError("backup_format", "The export has unsupported omission metadata")
    for name, omitted in omissions.items():
        if not isinstance(omitted, dict) or set(omitted) != {"records", "reason"} or \
                type(omitted["records"]) is not int or omitted["records"] < 0 or omitted["reason"] != reasons[name]:
            raise ApiError("backup_format", "The export has invalid omitted-data metadata")
    available = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    count = 0
    for name, rows in records.items():
        if not eligible_table(name) or name not in available or not isinstance(rows, list):
            raise ApiError("backup_table", "The export contains an unsupported record type")
        count += len(rows)
        if count > MAX_RECORDS:
            raise ApiError("backup_limit", "The maximum canonical record count is 100,000", 413)
        info = list(conn.execute(f'PRAGMA table_info("{name}")'))
        keys = primary_keys(conn, name)
        seen = set()
        for row in rows:
            validate_record_row(name, row, info)
            identity = tuple(row[key] for key in keys)
            if keys and identity in seen:
                raise ApiError("backup_duplicates", "The export contains duplicate canonical identities")
            seen.add(identity)
    return records


def blocked_ids(conn, current, incoming, deleted_ids):
    """Traverse descendants once, including indirect revisions, jobs and history."""
    edges = defaultdict(set)
    for name in set(current) | set(incoming):
        if name == "deletion_ledger":
            continue
        keys = primary_keys(conn, name)
        for row in [*current.get(name, []), *incoming.get(name, [])]:
            identifiers = {row[key] for key in keys if isinstance(row.get(key), str)}
            for reference in record_references(row):
                edges[reference].update(identifiers)
    blocked, pending = set(deleted_ids), deque(deleted_ids)
    while pending:
        for identifier in edges[pending.popleft()] - blocked:
            blocked.add(identifier)
            pending.append(identifier)
    return blocked


def apply_records(conn, bundle):
    """Caller owns the SQLite transaction and any original-file promotion."""
    records = validate_records(conn, bundle)
    current = snapshot_in(conn)["records"]
    conn.execute("PRAGMA defer_foreign_keys=ON")
    for row in records.get("deletion_ledger", []):
        conn.execute("INSERT INTO deletion_ledger VALUES(?,?,?) ON CONFLICT(entity_type,entity_id) "
                     "DO UPDATE SET deleted_at=MAX(deletion_ledger.deleted_at,excluded.deleted_at)",
                     (row["entity_type"], row["entity_id"], row["deleted_at"]))
    deleted = {row[0] for row in conn.execute("SELECT entity_id FROM deletion_ledger")}
    blocked = blocked_ids(conn, current, records, deleted)
    removed = 0
    for name, rows in current.items():
        if name == "deletion_ledger":
            continue
        keys = primary_keys(conn, name)
        for row in rows:
            if keys and blocked.intersection(record_references(row)):
                where = " AND ".join(f'"{key}"=?' for key in keys)
                removed += conn.execute(f'DELETE FROM "{name}" WHERE {where}',
                                        tuple(row[key] for key in keys)).rowcount
    inserted, excluded = 0, 0
    for name, rows in records.items():
        if name == "deletion_ledger":
            continue
        keys = primary_keys(conn, name)
        where = " AND ".join(f'"{key}"=?' for key in keys)
        for row in rows:
            if blocked.intersection(record_references(row)):
                excluded += 1
                continue
            existing = conn.execute(f'SELECT * FROM "{name}" WHERE {where}',
                                    tuple(row[key] for key in keys)).fetchone() if keys else None
            if existing and name.startswith("content_") and "sha256" in row:
                if any(existing[key] != value for key, value in row.items() if key != "installed_at"):
                    raise ApiError("backup_content_conflict", "A published content version differs from this installation; no records were restored")
            if existing and name == "knowledge_revisions" and any(
                    existing[key] != row[key] for key in ("document_id", "sha256", "bytes", "media_type")):
                raise ApiError("backup_original_conflict", "A document revision differs from this profile; no records were restored", 409)
            if existing and name in ('case_attachments', 'case_attachment_parts') and any(
                    existing[key] != value for key, value in row.items()):
                raise ApiError('backup_case_original_conflict', 'A saved case original differs from this profile; no records were restored', 409)
            if existing:
                continue
            names = list(row)
            columns_sql = ",".join(f'"{column}"' for column in names)
            placeholders = ",".join("?" for _ in names)
            # OR IGNORE would silently discard invalid CHECK/NOT NULL rows.
            inserted += conn.execute(f'INSERT INTO "{name}" ({columns_sql}) VALUES({placeholders})',
                                     tuple(row[column] for column in names)).rowcount
    if conn.execute("PRAGMA foreign_key_check").fetchall():
        raise ApiError("backup_references", "The export has incomplete linked records; no records were restored")
    return {"restored_records": inserted, "excluded_by_deletion": excluded,
            "removed_by_deletion": removed, "exported_at": bundle["exported_at"],
            "indexes": "rebuild-required"}, blocked, current


def validate_merge(services, bundle):
    """Validate against a read-only snapshot of canonical data, never copy secrets."""
    source, candidate = services.db.connect(), sqlite3.connect(":memory:")
    candidate.row_factory = sqlite3.Row
    try:
        source.execute("BEGIN")
        current = snapshot_in(source)["records"]
        for name in current:
            sql = source.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()[0]
            candidate.execute(sql)
        for name, rows in current.items():
            for row in rows:
                names = ",".join(f'"{key}"' for key in row)
                placeholders = ",".join("?" for _ in row)
                candidate.execute(f'INSERT INTO "{name}" ({names}) VALUES({placeholders})', tuple(row.values()))
        for trigger in source.execute("SELECT tbl_name,sql FROM sqlite_master WHERE type='trigger'"):
            if trigger[0] in current:
                candidate.execute(trigger[1])
        candidate.commit()
        candidate.execute("PRAGMA foreign_keys=ON")
        candidate.execute("BEGIN")
        return apply_records(candidate, bundle)[0]
    except sqlite3.DatabaseError:
        raise ApiError("backup_references", "The export has invalid or incomplete linked records; no records were restored") from None
    finally:
        candidate.rollback()
        candidate.close()
        source.rollback()
        source.close()


def restore_records(services, bundle, *, confirm_older=False):
    if not confirm_older:
        raise ApiError("restore_confirmation", "Confirm the backup date and its deletion limits before restoring", 409)
    bundle = records_only_bundle(bundle)
    with services.db.transaction() as conn:
        records = validate_records(conn, bundle)
        safe = {**bundle, "records": portable_records(records)}
        try:
            result, _, _ = apply_records(conn, safe)
        except sqlite3.DatabaseError:
            raise ApiError("backup_references", "The export has invalid or incomplete linked records; no records were restored") from None
    conn = services.db.connect()
    try:
        result["purge_pending"] = bool(conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0])
    finally:
        conn.close()
    return result
