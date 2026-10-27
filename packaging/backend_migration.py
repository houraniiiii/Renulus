# SPDX-License-Identifier: MIT
"""Closed-generation migration tool. Never assemble services or open a provider.

Preview uses immutable read-only SQLite. Apply backs up into a NEW prepared
generation, then uses the existing registered migration implementation there.
The original profile is never upgraded in place.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

MODULES = ("runtime", "content", "knowledge", "retrieval", "learn", "cases",
           "assessment", "memory", "study", "updates")


def scripts(source: Path):
    root = source / "runtime/renulus"
    result = {"storage-recovery-001": (root / "storage/recovery_schema.sql").read_text(encoding="utf-8")}
    for name in MODULES:
        if (root / name / "schema.sql").is_file():
            result[name + "-001"] = (root / name / "schema.sql").read_text(encoding="utf-8")
        for file in sorted((root / name / "migrations").glob("*.sql")):
            result[name + "-" + file.stem] = file.read_text(encoding="utf-8")
    return result


def preview(database: Path, source: Path):
    if any((Path(str(database) + suffix).exists() and Path(str(database) + suffix).stat().st_size)
           for suffix in ("-wal", "-journal")):
        raise ValueError("migration_source_not_checkpointed")
    conn = sqlite3.connect(database.as_uri() + "?mode=ro&immutable=1", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version not in (1, 2):
            raise ValueError("migration_schema_unsupported")
        schema = [dict(row) for row in conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name")]
        inventory = scripts(source)
        ledger = [dict(row) for row in conn.execute("SELECT name,checksum FROM migration_ledger ORDER BY name")] if any(row["name"] == "migration_ledger" for row in schema) else []
        for item in ledger:
            if item["name"] not in inventory or hashlib.sha256(inventory[item["name"]].encode()).hexdigest() != item["checksum"]:
                raise ValueError("migration_inventory_unknown_or_changed")
        if version == 1:
            legacy = json.loads((source / "runtime/renulus/storage/legacy_schema_1.json").read_text())
            for item in schema:
                if item["type"] != "table" or item["name"] == "migration_ledger":
                    continue
                name = item["name"]
                if name not in legacy or [dict(r) for r in conn.execute('PRAGMA table_info("' + name + '")')] != legacy[name]:
                    raise ValueError("migration_schema1_inventory_unknown")
        if conn.execute("PRAGMA quick_check").fetchall()[0][0] != "ok" or conn.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("migration_integrity_failed")
        counts = {item["name"]: conn.execute('SELECT COUNT(*) FROM "' + item["name"].replace('"', '""') + '"').fetchone()[0]
                  for item in schema if item["type"] == "table"}
        return {"schemaVersion": version, "tables": counts, "migrations": ledger,
                "pendingMigrations": [name for name in inventory if name not in {r["name"] for r in ledger}],
                "sourceSha256": hashlib.sha256(database.read_bytes()).hexdigest()}
    finally:
        conn.close()


def apply(database: Path, target: Path, source: Path, expected_sha256: str):
    observed = preview(database, source)
    if observed["sourceSha256"] != expected_sha256 or target.exists() or target == database:
        raise ValueError("migration_prepared_generation_required")
    target.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive file creation precedes SQLite; do not overwrite a previous candidate.
    with target.open("xb"):
        pass
    current = sqlite3.connect(database.as_uri() + "?mode=ro&immutable=1", uri=True)
    candidate = sqlite3.connect(target)
    try:
        current.backup(candidate)
    finally:
        candidate.close()
        current.close()
    sys.path.insert(0, str(source / "runtime"))
    from renulus.storage.database import Database
    inventory = scripts(source)
    db = Database(target, migration_inventory=inventory)
    for name, script in inventory.items():
        db.apply_migration(name, script)
    with db.connect() as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    result = preview(target, source)
    if result["pendingMigrations"]:
        raise ValueError("migration_incomplete")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--target", type=Path)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    if any(not p.is_absolute() or p.resolve() != p for p in (args.source, args.database)):
        raise ValueError("migration_absolute_paths_required")
    result = apply(args.database, args.target, args.source, args.expected_sha256) if args.target else preview(args.database, args.source)
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
