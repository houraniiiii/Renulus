# SPDX-License-Identifier: MIT
"""Canonical-only disk snapshots and SQL deletion/merge for segmented recovery.

Archive SQL is never accepted. Tables, constraints, indexes and triggers come
from the installed app. Cursors carry one bounded row; identity/descendant sets
live in SQLite, not Python collections. No provider/native database is copied.
"""
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import sqlite3

from ..contracts import ApiError
from .backup import (SAFE_PREFERENCES, eligible_table, portable_records,
                     validate_record_row)
from .recovery_archive import canonical_json, owned_path


def quoted(value):
    # All names originate in trusted installed schemas, never archive values.
    return '"' + value.replace('"', '""') + '"'


@dataclass
class Table:
    sql: str
    info: list

    @property
    def columns(self):
        return [column["name"] for column in self.info]

    @property
    def keys(self):
        return [column["name"] for column in sorted(self.info, key=lambda column: column["pk"]) if column["pk"]]

    @property
    def references(self):
        return [name for name in self.columns if name == "id" or name.endswith("_id")]


def installed_schema(conn, limits):
    result = {}
    for row in conn.execute("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name"):
        if eligible_table(row["name"]):
            definition = Table(row["sql"], [dict(column) for column in conn.execute(f'PRAGMA table_info({quoted(row["name"])})')])
            if not definition.keys:
                raise ApiError("backup_schema", "A canonical table has no bounded recovery identity")
            result[row["name"]] = definition
    if len(result) > limits.tables:
        raise ApiError("backup_limit", "The installed canonical table inventory exceeds format 2", 413)
    return result


def scratch(path, definitions, limits):
    path.open("xb").close()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("PRAGMA cache_size=-2048")
    conn.execute("PRAGMA temp_store=FILE")
    conn.execute(f"PRAGMA max_page_count={limits.scratch_database_bytes // conn.execute('PRAGMA page_size').fetchone()[0]}")
    for table in definitions.values():
        conn.execute(table.sql)
    conn.commit()
    return conn


def check_workspace(directory, limits):
    total = 0
    for item in directory.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
            if total > limits.workspace_bytes:
                raise ApiError("backup_limit", "Recovery scratch files exceed the bounded disk workspace", 413)


def validate_stream_row(name, row, table, limits, *, portable=False):
    validate_record_row(name, row, table.info)
    for key in set(table.keys) | set(table.references) | ({"entity_id"} if name == "deletion_ledger" else set()):
        value = row[key]
        if isinstance(value, str) and len(value.encode("utf-8")) > limits.identifier_bytes:
            raise ApiError("backup_limit", "A canonical identity/reference exceeds the format-2 graph bound", 413)
    if portable:
        for key, value in row.items():
            if key.endswith("_path") and not (name == "knowledge_revisions" and key == "original_path") and value not in (None, ""):
                raise ApiError("backup_path", "The backup contains a nonportable acquisition or engine path")
        if name == "knowledge_revisions" and row["extraction_json"] is not None:
            raise ApiError("backup_format", "Format 2 excludes derived structured extraction documents")


def line_for(row, limits):
    try:
        line = canonical_json(row) + b"\n"
    except (ValueError, TypeError, UnicodeError):
        raise ApiError("backup_records", "Canonical records contain unsupported scalar values") from None
    if len(line) > limits.row_bytes:
        raise ApiError("backup_limit", "A canonical JSONL row exceeds the format-2 row budget", 413)
    return line


def _select(table, name):
    projection = ["NULL AS " + quoted(column) if column.endswith("_path") and not
                  (name == "knowledge_revisions" and column == "original_path") or
                  name == "knowledge_revisions" and column == "extraction_json" else quoted(column)
                  for column in table.columns]
    where, parameters = "", ()
    if name == "preferences":
        where = " WHERE key IN (" + ",".join("?" for _ in SAFE_PREFERENCES) + ")"
        parameters = tuple(sorted(SAFE_PREFERENCES))
    return projection, where, parameters


def preflight(conn, definitions, limits):
    """Refuse large scalar payloads before fetching them into Python."""
    count = 0
    for name, table in definitions.items():
        projection, where, parameters = _select(table, name)
        count += conn.execute(f'SELECT COUNT(*) FROM {quoted(name)}{where}', parameters).fetchone()[0]
        if count > limits.records:
            raise ApiError("backup_limit", "Canonical records exceed the format-2 record budget", 413)
        lengths = ["0" if item.startswith("NULL AS ") else f"COALESCE(length(CAST({item} AS BLOB)),0)" for item in projection]
        largest = conn.execute(f'SELECT MAX({"+".join(lengths)}) FROM {quoted(name)}{where}', parameters).fetchone()[0] or 0
        if largest > limits.row_bytes:
            raise ApiError("backup_limit", "A projected canonical scalar/row exceeds format 2 before reading", 413)
        for column in set(table.keys) | set(table.references):
            largest_id = conn.execute(f'SELECT MAX(length(CAST({quoted(column)} AS BLOB))) FROM {quoted(name)}{where}', parameters).fetchone()[0] or 0
            if largest_id > limits.identifier_bytes:
                raise ApiError("backup_limit", "A canonical identity/reference exceeds the format-2 graph bound", 413)
    return count


def snapshot_rows(conn, definitions, limits, *, paths=None):
    preflight(conn, definitions, limits)
    for name, table in definitions.items():
        projection, where, parameters = _select(table, name)
        # Journal ties retain source insertion order. Readers use recorded time
        # before rowid; all other identities/active slots keep normal merge policy.
        for row in conn.execute(f'SELECT {",".join(projection)} FROM {quoted(name)}{where} ORDER BY rowid', parameters):
            copied = portable_records({name: [dict(row)]}, originals=True)[name][0]
            if paths and name == "knowledge_revisions" and copied["original_path"]:
                try:
                    copied["original_path"] = Path(copied["original_path"]).relative_to(paths.root).as_posix()
                except ValueError:
                    raise ApiError("backup_path", "An original is not app-owned; select a records-only export", 409) from None
            validate_stream_row(name, copied, table, limits)
            yield name, copied


def insert_row(conn, name, row, table):
    columns = table.columns
    try:
        conn.execute(f'INSERT INTO {quoted(name)}({",".join(map(quoted, columns))}) VALUES({",".join("?" for _ in columns)})',
                     [row[column] for column in columns])
    except sqlite3.IntegrityError as error:
        code = "backup_duplicates" if getattr(error, "sqlite_errorcode", None) in (
            sqlite3.SQLITE_CONSTRAINT_PRIMARYKEY, sqlite3.SQLITE_CONSTRAINT_UNIQUE) else "backup_records"
        raise ApiError(code, "Canonical records violate the installed schema or repeat an identity") from None


def copy_snapshot(source, destination, definitions, limits, *, paths=None):
    size = 0
    destination.execute("BEGIN")
    try:
        for name, row in snapshot_rows(source, definitions, limits, paths=paths):
            size += len(line_for(row, limits))
            if size > limits.canonical_bytes:
                raise ApiError("backup_limit", "Canonical data exceeds the format-2 expanded budget", 413)
            insert_row(destination, name, row, definitions[name])
        destination.commit()
    except BaseException:
        destination.rollback()
        raise


def blocked_condition(table, alias=""):
    prefix = alias + "." if alias else ""
    return "(" + " OR ".join(f"(typeof({prefix}{quoted(column)})='text' AND {prefix}{quoted(column)} IN (SELECT id FROM temp.recovery_blocked))"
                              for column in table.references) + ")" if table.references else "0"


def build_blocked(conn, definitions, limits, *, incoming=False):
    conn.execute("CREATE TEMP TABLE recovery_edges(source TEXT NOT NULL,destination TEXT NOT NULL,PRIMARY KEY(source,destination)) WITHOUT ROWID")
    conn.execute("CREATE TEMP TABLE recovery_blocked(id TEXT PRIMARY KEY) WITHOUT ROWID")
    conn.execute("PRAGMA temp.cache_size=-2048")
    conn.execute(f"PRAGMA temp.max_page_count={limits.scratch_database_bytes // conn.execute('PRAGMA temp.page_size').fetchone()[0]}")
    edges = 0
    for database in (("main", "recovery_incoming") if incoming else ("main",)):
        for name, table in definitions.items():
            if name == "deletion_ledger":
                continue
            for reference in table.references:
                for key in table.keys:
                    if reference == key:
                        continue  # Self edges add no descendants.
                    before = conn.total_changes
                    conn.execute(f'INSERT OR IGNORE INTO temp.recovery_edges SELECT {quoted(reference)},{quoted(key)} FROM {database}.{quoted(name)} '
                                 f'WHERE typeof({quoted(reference)})=\'text\' AND typeof({quoted(key)})=\'text\'')
                    edges += conn.total_changes - before
                    if edges > limits.graph_edges:
                        raise ApiError("backup_limit", "Deletion reconciliation exceeds the format-2 graph budget", 413)
    conn.execute("WITH RECURSIVE descendants(id) AS (SELECT entity_id FROM main.deletion_ledger UNION "
                 "SELECT e.destination FROM temp.recovery_edges e JOIN descendants d ON e.source=d.id) "
                 "INSERT INTO temp.recovery_blocked SELECT id FROM descendants")


def prune_deleted(conn, definitions, limits):
    build_blocked(conn, definitions, limits)
    for name, table in definitions.items():
        if name != "deletion_ledger":
            conn.execute(f'DELETE FROM {quoted(name)} WHERE {blocked_condition(table)}')
    conn.commit()


def apply_staged(conn, stage, definitions, limits, exported_at):
    """Atomic SQL merge; deletions precede incoming rows and original promotion."""
    preflight(conn, definitions, limits)
    conn.execute("PRAGMA defer_foreign_keys=ON")
    # Database.connect() intentionally does not enable SQLite URI filenames.
    # This is an app-created, reverified canonical scratch DB, never a SQLite
    # member from the archive. All SQL below reads only the attached database.
    conn.execute("ATTACH DATABASE ? AS recovery_incoming", (str(stage),))
    conn.execute("PRAGMA recovery_incoming.cache_size=-2048")
    conn.execute("INSERT INTO main.deletion_ledger SELECT * FROM recovery_incoming.deletion_ledger WHERE 1 "
                 "ON CONFLICT(entity_type,entity_id) DO UPDATE SET deleted_at=MAX(deletion_ledger.deleted_at,excluded.deleted_at)")
    build_blocked(conn, definitions, limits, incoming=True)
    # Only the small original descriptor columns are retained, never revision
    # extraction/rights/passage payloads or the entire current profile.
    removed_originals = []
    if "knowledge_revisions" in definitions:
        columns = "id,document_id,original_path,bytes,sha256,media_type"
        for row in conn.execute(f'SELECT {columns} FROM main.knowledge_revisions WHERE original_path IS NOT NULL AND {blocked_condition(definitions["knowledge_revisions"])}'):
            removed_originals.append(dict(row))
            if len(removed_originals) > limits.originals:
                raise ApiError("backup_limit", "Deleted target originals exceed the recovery file-count budget", 413)
    removed, inserted, excluded = 0, 0, 0
    for name, table in definitions.items():
        if name == "deletion_ledger":
            continue
        removed += conn.execute(f'DELETE FROM main.{quoted(name)} WHERE {blocked_condition(table)}').rowcount
    for name, table in definitions.items():
        if name == "deletion_ledger":
            continue
        match = " AND ".join(f'target.{quoted(key)} IS source.{quoted(key)}' for key in table.keys)
        allowed = f'NOT {blocked_condition(table, "source")}'
        excluded += conn.execute(f'SELECT COUNT(*) FROM recovery_incoming.{quoted(name)} AS source WHERE NOT ({allowed})').fetchone()[0]
        conflicts = []
        code = "backup_content_conflict"
        if name.startswith("content_") and "sha256" in table.columns:
            conflicts = [column for column in table.columns if column != "installed_at"]
        if name == "knowledge_revisions":
            conflicts, code = ["document_id", "sha256", "bytes", "media_type"], "backup_original_conflict"
        if name in ('case_attachments', 'case_attachment_parts'):
            conflicts, code = list(table.columns), 'backup_case_original_conflict'
        if conflicts:
            changed = " OR ".join(f'target.{quoted(column)} IS NOT source.{quoted(column)}' for column in conflicts)
            if conn.execute(f'SELECT 1 FROM recovery_incoming.{quoted(name)} AS source JOIN main.{quoted(name)} AS target ON {match} '
                            f'WHERE {allowed} AND ({changed}) LIMIT 1').fetchone():
                raise ApiError(code, "A canonical published version or original revision differs; no records were restored", 409)
        columns = ",".join(map(quoted, table.columns))
        # Verified descriptors supply rebased original paths in the promotion
        # transaction. Portable archive paths are never installed as live paths.
        selected = ",".join("NULL" if name == "knowledge_revisions" and column == "original_path"
                            else "source." + quoted(column) for column in table.columns)
        # Existing identities always win, including the target active bank slot.
        # INSERT OR IGNORE would conceal CHECK/NOT NULL/secondary-key corruption.
        inserted += conn.execute(f'INSERT INTO main.{quoted(name)}({columns}) SELECT {selected} FROM recovery_incoming.{quoted(name)} AS source '
                                 f'WHERE {allowed} AND NOT EXISTS(SELECT 1 FROM main.{quoted(name)} AS target WHERE {match}) ORDER BY source.rowid').rowcount
    if conn.execute("PRAGMA main.foreign_key_check").fetchone():
        raise ApiError("backup_references", "The backup has incomplete linked canonical records")
    # A union larger than the finite profile budget is refused while writes are
    # still uncommitted. The check streams projected rows; no full snapshot dict.
    size = 0
    for _, row in snapshot_rows(conn, definitions, limits):
        size += len(line_for(row, limits))
        if size > limits.canonical_bytes:
            raise ApiError("backup_limit", "The merged canonical profile exceeds format 2", 413)
    return {"restored_records": inserted, "excluded_by_deletion": excluded,
            "removed_by_deletion": removed, "exported_at": exported_at,
            "indexes": "rebuild-required"}, removed_originals


def validate_staged_merge(services, stage, definitions, directory, limits, exported_at):
    candidate_path = owned_path(services.paths, (directory / "merge.sqlite3").relative_to(services.paths.root).as_posix())
    with closing(services.db.connect()) as source, closing(scratch(candidate_path, definitions, limits)) as candidate:
        source.execute("BEGIN")
        copy_snapshot(source, candidate, definitions, limits)
        # Preserve the actual target schema's canonical triggers and indexes.
        for item in source.execute("SELECT tbl_name,sql FROM sqlite_master WHERE type IN ('trigger','index') AND sql IS NOT NULL"):
            if item["tbl_name"] in definitions:
                candidate.execute(item["sql"])
        candidate.commit()
        candidate.execute("PRAGMA foreign_keys=ON")
        candidate.execute("BEGIN")
        apply_staged(candidate, stage, definitions, limits, exported_at)
        candidate.rollback()
        source.rollback()
    candidate_path.unlink()
    check_workspace(directory, limits)
