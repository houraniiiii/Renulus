# SPDX-License-Identifier: MIT
"""Postcommit cleanup of tombstoned, app-owned conversation attachment files.

The caller journals the bounded plan in its canonical deletion transaction.
Only absent, explicitly tombstoned attachment identities can be drained later.
The journal is local maintenance state and is excluded from canonical exports.
"""
import json
import re

from ..contracts import ApiError
from .database import utc_now
from .recovery_archive import owned_path, strict_json
from .recovery_files import remove_owned_tree

JOURNAL = "design_c.attachment_cleanup"
MAX_PLAN = 200
MAX_PENDING = 1000
MAX_BYTES = 512 * 1024
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,128}")


def _validate(plan, limit):
    if not isinstance(plan, list) or len(plan) > limit:
        raise ApiError("attachment_cleanup_limit", "Attachment cleanup exceeds its bounded journal. Retry pending cleanup first.", 409, True)
    entries = {}
    for entry in plan:
        if not isinstance(entry, dict) or set(entry) != {"attachment_id", "relative_directory"} or \
                not isinstance(entry["attachment_id"], str) or not IDENTIFIER.fullmatch(entry["attachment_id"]) or \
                entry["relative_directory"] != "library/attachments/" + entry["attachment_id"]:
            raise ApiError("attachment_cleanup_path", "Cleanup requires an exact app-owned attachment identity.", 409)
        entries[entry["attachment_id"]] = entry
    return entries


def _pending(conn):
    row = conn.execute("SELECT value FROM preferences WHERE key=?", (JOURNAL,)).fetchone()
    if not row:
        return {}
    if len(row["value"].encode("utf-8")) > MAX_BYTES:
        raise ApiError("attachment_cleanup_limit", "The local attachment cleanup journal exceeds its bound.", 409)
    return _validate(strict_json(row["value"]), MAX_PENDING)


def _write(conn, entries):
    if entries:
        encoded = json.dumps([entries[key] for key in sorted(entries)], separators=(",", ":"))
        if len(encoded.encode("utf-8")) > MAX_BYTES:
            raise ApiError("attachment_cleanup_limit", "The local attachment cleanup journal exceeds its bound.", 409)
        conn.execute("INSERT INTO preferences VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET "
                     "value=excluded.value,updated_at=excluded.updated_at", (JOURNAL, encoded, utc_now()))
    else:
        conn.execute("DELETE FROM preferences WHERE key=?", (JOURNAL,))


def enqueue_in(conn, plan):
    """No filesystem work: commit this with the producer's typed tombstones."""
    additions = _validate(plan, MAX_PLAN)
    if not additions:
        return
    entries = {**_pending(conn), **additions}
    if len(entries) > MAX_PENDING:
        raise ApiError("attachment_cleanup_limit", "Pending attachment cleanup must finish before deleting more originals.", 409, True)
    _write(conn, entries)


def tombstoned_in(conn, attachment_id):
    return conn.execute("SELECT 1 FROM deletion_ledger WHERE entity_type='attachment' AND entity_id=?",
                        (attachment_id,)).fetchone() is not None


def drain(services):
    """Run after commit/startup. Interrupted or locked files remain journalled."""
    with services.db.transaction() as conn:
        entries = _pending(conn)
        eligible = [entry for identifier, entry in entries.items() if
            tombstoned_in(conn, identifier) and
            not conn.execute("SELECT 1 FROM knowledge_attachments WHERE id=?", (identifier,)).fetchone() and
            not conn.execute("SELECT 1 FROM knowledge_attachment_originals WHERE attachment_id=?", (identifier,)).fetchone()]
    removed = []
    for entry in eligible:
        try:
            directory = owned_path(services.paths, entry["relative_directory"])
            remove_owned_tree(services.paths, directory)
        except (ApiError, OSError):
            continue  # A later normal startup/retry drains the same durable plan.
        removed.append(entry["attachment_id"])
    with services.db.transaction() as conn:
        remaining = _pending(conn)
        for identifier in removed:
            remaining.pop(identifier, None)
        if removed:
            _write(conn, remaining)
    return {"removed": len(removed), "pending": len(remaining)}
