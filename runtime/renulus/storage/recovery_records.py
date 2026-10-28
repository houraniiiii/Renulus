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
from .recovery_archive import canonical_json, owned_path, ORIGINAL_TABLES
from .relations import PARENTS, TOMBSTONES, reconcile_unavailable_references


def require_frontier(records):
    if not isinstance(records, dict) or not isinstance(records.get("deletion_ledger"), list):
        raise ApiError("recovery_frontier_missing",
                       "The backup has no deletion frontier; affected records are quarantined and cannot be restored", 409)


def refuse_native_links(name, rows):
    if name.startswith("learn_harness_") and rows:
        raise ApiError("recovery_native_mapping_required",
                       "Native links require the TypeScript recovery owner and its validated native graph mapping", 409)


def quoted(value):
    # All names originate in trusted installed schemas, never archive values.
    return '"' + value.replace('"', '""') + '"'


@dataclass
class Table:
    sql: str
    info: list
    name: str = ""

    @property
    def columns(self):
        return [column["name"] for column in self.info]

    @property
    def keys(self):
        return [column["name"] for column in sorted(self.info, key=lambda column: column["pk"]) if column["pk"]]

    @property
    def references(self):
        return list(dict.fromkeys([*self.keys, *(column for binding in PARENTS.get(self.name, ())
            for column in binding.columns if column in self.columns)]))


def installed_schema(conn, limits):
    result = {}
    for row in conn.execute("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name"):
        if eligible_table(row["name"]):
            definition = Table(row["sql"], [dict(column) for column in conn.execute(f'PRAGMA table_info({quoted(row["name"])})')], row["name"])
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
            if key.endswith("_path") and not (name in ORIGINAL_TABLES and key == "original_path") and value not in (None, ""):
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
                  (name in ORIGINAL_TABLES and column == "original_path") or
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
            if paths and name in ORIGINAL_TABLES and copied["original_path"]:
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
    key = "json_array(" + ",".join(prefix + quoted(column) for column in table.keys) + ")"
    # The table name originates in the installed schema, not an archive.
    name = table.name.replace("'", "''")
    return f"EXISTS(SELECT 1 FROM temp.recovery_blocked b WHERE b.table_name='{name}' AND b.identity={key})"


def build_blocked(conn, definitions, limits, *, incoming=False):
    conn.execute("CREATE TEMP TABLE recovery_edges(source_table TEXT NOT NULL,source_identity TEXT NOT NULL,destination_table TEXT NOT NULL,destination_identity TEXT NOT NULL,PRIMARY KEY(source_table,source_identity,destination_table,destination_identity)) WITHOUT ROWID")
    conn.execute("CREATE TEMP TABLE recovery_blocked(table_name TEXT NOT NULL,identity TEXT NOT NULL,PRIMARY KEY(table_name,identity)) WITHOUT ROWID")
    conn.execute("PRAGMA temp.cache_size=-2048")
    conn.execute(f"PRAGMA temp.max_page_count={limits.scratch_database_bytes // conn.execute('PRAGMA temp.page_size').fetchone()[0]}")
    edges = 0
    for database in (("main", "recovery_incoming") if incoming else ("main",)):
        for name, table in definitions.items():
            if name == "deletion_ledger":
                continue
            destination = "json_array(" + ",".join(map(quoted, table.keys)) + ")"
            for binding in PARENTS.get(name, ()):
                if any(column not in table.columns for column in binding.columns):
                    continue
                source_columns = list(map(quoted, binding.columns))
                where, parameters = [column + " IS NOT NULL" for column in source_columns], [binding.parent, name]
                if binding.discriminator:
                    column, value = binding.discriminator
                    if column not in table.columns:
                        continue
                    where.append(quoted(column) + "=?")
                    parameters.append(value)
                if binding.prefix:
                    where.append(f"substr({source_columns[0]},1,{len(binding.prefix)})=?")
                    parameters.append(binding.prefix)
                    source_columns[0] = f"substr({source_columns[0]},{len(binding.prefix) + 1})"
                source = "json_array(" + ",".join(source_columns) + ")"
                before = conn.total_changes
                conn.execute(f'INSERT OR IGNORE INTO temp.recovery_edges SELECT ?,{source},?,{destination} FROM {database}.{quoted(name)} WHERE ' + " AND ".join(where), parameters)
                edges += conn.total_changes - before
                if edges > limits.graph_edges:
                    raise ApiError("backup_limit", "Deletion reconciliation exceeds the format-2 graph budget", 413)
    conn.execute("CREATE TEMP TABLE recovery_roots(table_name TEXT NOT NULL,identity TEXT NOT NULL,PRIMARY KEY(table_name,identity)) WITHOUT ROWID")
    for alias, table in TOMBSTONES.items():
        conn.execute("INSERT OR IGNORE INTO temp.recovery_roots SELECT ?,json_array(entity_id) FROM main.deletion_ledger WHERE entity_type=?", (table, alias))
    conn.execute("WITH RECURSIVE descendants(table_name,identity) AS (SELECT table_name,identity FROM temp.recovery_roots UNION "
                 "SELECT e.destination_table,e.destination_identity FROM temp.recovery_edges e JOIN descendants d ON e.source_table=d.table_name AND e.source_identity=d.identity) "
                 "INSERT INTO temp.recovery_blocked SELECT table_name,identity FROM descendants")


def prune_deleted(conn, definitions, limits):
    build_blocked(conn, definitions, limits)
    for name, table in definitions.items():
        if name != "deletion_ledger":
            conn.execute(f'DELETE FROM {quoted(name)} WHERE {blocked_condition(table)}')
    reconcile_unavailable_references(conn)
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
    for name in definitions:
        if name.startswith("learn_harness_"):
            refuse_native_links(name, conn.execute(f'SELECT 1 FROM recovery_incoming.{quoted(name)} LIMIT 1').fetchone())
    conn.execute("INSERT INTO main.deletion_ledger SELECT * FROM recovery_incoming.deletion_ledger WHERE 1 "
                 "ON CONFLICT(entity_type,entity_id) DO UPDATE SET deleted_at=MAX(deletion_ledger.deleted_at,excluded.deleted_at)")
    if "memory_suppression" in definitions:
        conn.execute("INSERT INTO main.memory_suppression SELECT * FROM recovery_incoming.memory_suppression WHERE 1 "
                     "ON CONFLICT(source_key) DO NOTHING")
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
    if "knowledge_attachment_originals" in definitions:
        for row in conn.execute("SELECT o.id,o.attachment_id,o.role,o.original_path,o.bytes,o.sha256,o.created_at,"
                "a.chat_kind,a.chat_id,a.media_type FROM main.knowledge_attachment_originals AS o "
                "JOIN main.knowledge_attachments AS a ON a.id=o.attachment_id "
                f'WHERE o.original_path IS NOT NULL AND {blocked_condition(definitions["knowledge_attachment_originals"], "o")}'):
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
        if name == "memory_sources":
            allowed += " AND NOT EXISTS(SELECT 1 FROM main.memory_suppression s WHERE s.source_key=source.source_key)"
        if name == "memory_history":
            allowed += " AND NOT EXISTS(SELECT 1 FROM main.memory_facts f WHERE f.id=source.record_id AND f.revision>source.revision)"
        excluded += conn.execute(f'SELECT COUNT(*) FROM recovery_incoming.{quoted(name)} AS source WHERE NOT ({allowed})').fetchone()[0]
        conflicts = []
        code = "backup_content_conflict"
        if name.startswith("content_") and "sha256" in table.columns:
            conflicts = [column for column in table.columns if column != "installed_at"]
        if name == "knowledge_revisions":
            conflicts, code = ["document_id", "sha256", "bytes", "media_type"], "backup_original_conflict"
        if name == "knowledge_attachment_originals":
            conflicts, code = ["attachment_id", "role", "sha256", "bytes"], "backup_original_conflict"
        if name == "knowledge_attachments":
            conflicts, code = ["chat_kind", "chat_id", "media_type"], "backup_original_conflict"
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
        selected = ",".join("NULL" if name in ORIGINAL_TABLES and column == "original_path"
                            else "'revoked'" if name == "memory_answer_lineage" and column == "state"
                            else "source." + quoted(column) for column in table.columns)
        # Existing identities always win, including the target active bank slot.
        # INSERT OR IGNORE would conceal CHECK/NOT NULL/secondary-key corruption.
        inserted += conn.execute(f'INSERT INTO main.{quoted(name)}({columns}) SELECT {selected} FROM recovery_incoming.{quoted(name)} AS source '
                                 f'WHERE {allowed} AND NOT EXISTS(SELECT 1 FROM main.{quoted(name)} AS target WHERE {match}) ORDER BY source.rowid').rowcount
    reconcile_unavailable_references(conn)
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
