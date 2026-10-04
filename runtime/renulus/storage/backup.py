"""Versioned canonical export; credentials and derived indexes are never exported."""
from collections import defaultdict
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import re
import sqlite3
import zipfile

from renulus.contracts import ApiError
from .database import SUPPORTED_SCHEMA, utc_now

FORMAT_VERSION = 1
SAFE_PREFIXES = ("content_", "learn_", "case_", "cases_", "assessment_",
                 "memory_", "study_", "knowledge_", "library_", "update_")
COMMON_TABLES = {"learning_evidence", "deletion_ledger", "preferences"}
SAFE_PREFERENCES = {"study.goals", "memory.enabled", "learn.teaching_style"}


def eligible_table(name):
    return bool(re.fullmatch(r"[a-z][a-z0-9_]*", name)) and (
        name in COMMON_TABLES or name.startswith(SAFE_PREFIXES))


def primary_keys(conn, table):
    return [row["name"] for row in conn.execute(f'PRAGMA table_info("{table}")') if row["pk"]]


def export_records(services):
    conn = services.db.connect()
    try:
        conn.execute("BEGIN")
        names = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                 if eligible_table(row[0])]
        records = {}
        for name in names:
            rows = [dict(row) for row in conn.execute(f'SELECT * FROM "{name}"')]
            if name == "preferences":
                rows = [row for row in rows if row["key"] in SAFE_PREFERENCES]
            records[name] = rows
        return {"format": "renulus-canonical-export", "format_version": FORMAT_VERSION,
                "schema_version": SUPPORTED_SCHEMA, "exported_at": utc_now(),
                "records": records, "artifacts": {},
                "limits": "A backup carries only deletion markers known at its export date. On a new installation it cannot know later deletions. Derived indexes must be regenerated with the recorded helper configuration."}
    finally:
        conn.rollback()
        conn.close()


def restore_records(services, bundle, *, confirm_older=False):
    if bundle.get("format") != "renulus-canonical-export" or bundle.get("format_version") != FORMAT_VERSION:
        raise ApiError("backup_format", "This is not a supported Renulus export")
    if bundle.get("schema_version") != SUPPORTED_SCHEMA:
        raise ApiError("backup_schema", "Install a compatible app version before restoring this export")
    if not confirm_older:
        raise ApiError("restore_confirmation", "Confirm the backup date and its deletion limits before restoring", 409)
    records = bundle.get("records")
    if not isinstance(records, dict):
        raise ApiError("backup_records", "The export has invalid canonical records")
    with services.db.transaction() as conn:
        available = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for name, rows in records.items():
            if not eligible_table(name) or name not in available or not isinstance(rows, list):
                raise ApiError("backup_table", "The export contains an unsupported record type")
            columns = {row["name"] for row in conn.execute(f'PRAGMA table_info("{name}")')}
            if any(not isinstance(row, dict) or set(row) != columns for row in rows):
                raise ApiError("backup_columns", "The export record schema does not match this app")
        # Reconcile markers from the existing profile and imported snapshot before inserting facts.
        for row in records.get("deletion_ledger", []):
            conn.execute("INSERT INTO deletion_ledger VALUES(?,?,?) ON CONFLICT(entity_type,entity_id) DO UPDATE SET deleted_at=MAX(deletion_ledger.deleted_at,excluded.deleted_at)",
                         (row["entity_type"], row["entity_id"], row["deleted_at"]))
        deletions = {(row["entity_type"], row["entity_id"]) for row in conn.execute("SELECT * FROM deletion_ledger")}
        deleted_ids = {identifier for _, identifier in deletions}
        # Deferred FK validation permits snapshots without dependence on alphabetical table ordering.
        conn.execute("PRAGMA defer_foreign_keys=ON")
        # Include indirect descendants: document -> revision -> passage/job,
        # thread -> run/message, and memory fact -> history/index work.
        current = {name: [dict(row) for row in conn.execute(f'SELECT * FROM "{name}"')]
                   for name in available if eligible_table(name) and name != "deletion_ledger"}
        blocked = set(deleted_ids)
        expanded = True
        while expanded:
            expanded = False
            for name in set(current) | set(records):
                if name == "deletion_ledger":
                    continue
                keys = primary_keys(conn, name)
                for row in [*current.get(name, []), *records.get(name, [])]:
                    references = [value for key, value in row.items()
                                  if (key == "id" or key.endswith("_id")) and isinstance(value, str)]
                    if any(value in blocked for value in references):
                        for key in keys:
                            value = row.get(key)
                            if isinstance(value, str) and value not in blocked:
                                blocked.add(value)
                                expanded = True
        removed = 0
        for name, rows in current.items():
            keys = primary_keys(conn, name)
            for row in rows:
                references = [value for key, value in row.items()
                              if (key == "id" or key.endswith("_id")) and isinstance(value, str)]
                if keys and any(value in blocked for value in references):
                    where = " AND ".join(f'"{key}"=?' for key in keys)
                    removed += conn.execute(f'DELETE FROM "{name}" WHERE {where}',
                                            tuple(row[key] for key in keys)).rowcount
        inserted, excluded = 0, 0
        for name, rows in records.items():
            if name == "deletion_ledger":
                continue
            for row in rows:
                if name == "preferences" and row["key"] not in SAFE_PREFERENCES:
                    raise ApiError("backup_preference", "Connection settings and credentials cannot be restored from learning exports")
                # IDs are globally prefixed; references to deleted entities suppress all derivatives.
                identifiers = [value for key, value in row.items() if (key == "id" or key.endswith("_id")) and isinstance(value, str)]
                if any(value in blocked for value in identifiers):
                    excluded += 1
                    continue
                if name.startswith("content_") and "sha256" in row:
                    keys = primary_keys(conn, name)
                    where = " AND ".join(f'"{key}"=?' for key in keys)
                    existing = conn.execute(f'SELECT sha256 FROM "{name}" WHERE {where}',
                                            tuple(row[key] for key in keys)).fetchone()
                    if existing and existing["sha256"] != row["sha256"]:
                        raise ApiError("backup_content_conflict", "A published content version differs from this installation; no records were restored")
                names = list(row)
                columns_sql = ",".join(f'"{column}"' for column in names)
                placeholders = ",".join("?" for _ in names)
                count = conn.execute(f'INSERT OR IGNORE INTO "{name}" ({columns_sql}) VALUES({placeholders})',
                                     tuple(row[column] for column in names)).rowcount
                inserted += count
        failures = conn.execute("PRAGMA foreign_key_check").fetchall()
        if failures:
            raise ApiError("backup_references", "The export has incomplete linked records; no records were restored")
    # Never recreate indexes over stale/deleted rows as part of the restore transaction.
    conn = services.db.connect()
    try:
        purge_pending = bool(conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0])
    finally:
        conn.close()
    return {"restored_records": inserted, "excluded_by_deletion": excluded,
            "removed_by_deletion": removed, "purge_pending": purge_pending,
            "exported_at": bundle.get("exported_at"), "indexes": "rebuild-required"}
