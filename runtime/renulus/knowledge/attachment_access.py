# SPDX-License-Identifier: MIT
"""Metadata-only attachment access, inside the caller's canonical transaction.

Case bytes remain Case-owned. No database connection, write, original read or
model operation occurs here. Availability is independent of extraction/indexing.
"""
import json
from pathlib import Path

from ..cases.originals import CHUNK_BYTES
from ..design_c_contracts import Identity
from ..storage.assessment_policy import policy_snapshot
from .models import Rights, SourceMetadata


def denied(reason):
    return {"allowed": False, "reason": reason}


class KnowledgeAttachmentAccess:
    def __init__(self, services):
        self.services, self.paths = services, services.paths

    def _volatile_snapshot(self, conn, attachment_id, context):
        return None

    @staticmethod
    def _deleted(conn, identifier, *types):
        placeholders = ",".join("?" for _ in types)
        return conn.execute("SELECT 1 FROM deletion_ledger WHERE entity_id=? AND entity_type IN ("
            + placeholders + ")", (identifier, *types)).fetchone() is not None

    def _case_snapshot(self, case_id, attachment_id):
        owner = self.services.registry.get("cases")
        if owner is None:
            return "absent", None
        # Case Save takes its lock before SQLite. While a caller holds SQLite,
        # waiting for that lock would invert the order. A nonblocking snapshot
        # fails closed during contention and never copies original bytes. The
        # Case owner can replace this adapter with its metadata-only seam.
        if not owner._lock.acquire(blocking=False):
            return "busy", None
        try:
            if case_id in owner._deleted:
                return "deleted", None
            session = owner._sessions.get(case_id)
            if session is None:
                return "absent", None
            attachment = next((item for item in session.attachments if item["id"] == attachment_id), None)
            if attachment is None:
                return "found", None
            data = attachment.get("data")
            return "found", {"bytes": attachment["bytes"],
                "data_length": len(data) if data is not None else None,
                "saved_revision": session.saved_revision}
        finally:
            owner._lock.release()

    def authorize_in(self, conn, attachment_id: str, *, context: Identity | None = None):
        if not policy_snapshot(conn)["assistance_allowed"]:
            return denied("restricted")
        try:
            context = Identity.model_validate(context) if context is not None else None
        except ValueError:
            return denied("access_denied")
        if context is not None and context.type not in {"learn_thread", "case"}:
            return denied("access_denied")
        if self._deleted(conn, attachment_id, "attachment", "case_attachment"):
            return denied("not_found")

        ordinary = self._volatile_snapshot(conn, attachment_id, context)
        if ordinary is not None:
            return ordinary

        legacy = conn.execute("SELECT id,case_id,bytes FROM case_attachments WHERE id=?", (attachment_id,)).fetchone()
        if legacy:
            if context is not None and (context.type != "case" or context.id != legacy["case_id"]):
                return denied("access_denied")
            if (self._deleted(conn, legacy["case_id"], "case")
                    or not (saved := conn.execute("SELECT revision FROM case_sessions WHERE id=?", (legacy["case_id"],)).fetchone())):
                return denied("not_found")
            exists, attachment = self._case_snapshot(legacy["case_id"], attachment_id)
            if exists == "busy":
                return denied("unavailable")
            if exists == "deleted" or (exists == "found" and attachment is None):
                return denied("not_found")
            if attachment and attachment["saved_revision"] != saved["revision"]:
                return denied("unavailable")
            if attachment and attachment["data_length"] is not None:
                return {"allowed": True} if attachment["data_length"] == legacy["bytes"] else denied("unavailable")
            # A records-only restore has metadata but no parts. Do not read the
            # base64 payload or require extraction to determine availability.
            parts = conn.execute("SELECT COUNT(*) AS count,MIN(part) AS first,MAX(part) AS last "
                "FROM case_attachment_parts WHERE attachment_id=?", (attachment_id,)).fetchone()
            count = (legacy["bytes"] + CHUNK_BYTES - 1) // CHUNK_BYTES
            return ({"allowed": True} if count > 0 and parts["count"] == count
                    and parts["first"] == 0 and parts["last"] == count - 1 else denied("unavailable"))

        if context is not None and context.type == "case":
            if self._deleted(conn, context.id, "case"):
                return denied("not_found")
            exists, attachment = self._case_snapshot(context.id, attachment_id)
            if exists == "busy":
                return denied("unavailable")
            if exists == "deleted":
                return denied("not_found")
            if attachment is not None:
                return ({"allowed": True} if attachment["data_length"] == attachment["bytes"]
                        else denied("unavailable"))

        columns = {row["name"] for row in conn.execute("PRAGMA table_info(knowledge_attachments)")}
        if not {"id", "chat_kind", "chat_id"} <= columns:
            return denied("unavailable")
        row = conn.execute("SELECT id,chat_kind,chat_id FROM knowledge_attachments WHERE id=?",
            (attachment_id,)).fetchone()
        if row is None:
            return denied("not_found")
        if row["chat_kind"] not in {"learning", "case"}:
            return denied("unavailable")
        target_type = "case" if row["chat_kind"] == "case" else "learn_thread"
        if context is not None and (context.type != target_type or context.id != row["chat_id"]):
            return denied("access_denied")
        table = "case_sessions" if target_type == "case" else "learn_threads"
        if (self._deleted(conn, row["chat_id"], target_type)
                or not conn.execute(f"SELECT 1 FROM {table} WHERE id=?", (row["chat_id"],)).fetchone()):
            return denied("not_found")
        columns = {item["name"] for item in conn.execute("PRAGMA table_info(knowledge_attachment_metadata)")}
        if not {"attachment_id", "source_id", "metadata_json", "rights_json"} <= columns:
            return denied("unavailable")
        metadata_row = conn.execute("SELECT source_id,metadata_json,rights_json FROM knowledge_attachment_metadata "
            "WHERE attachment_id=?", (attachment_id,)).fetchone()
        if metadata_row is None:
            return denied("unavailable")
        try:
            rights = Rights.model_validate(json.loads(metadata_row["rights_json"]))
            metadata = SourceMetadata.model_validate(json.loads(metadata_row["metadata_json"]))
        except (ValueError, TypeError):
            return denied("unavailable")
        if metadata.source_id != metadata_row["source_id"]:
            return denied("unavailable")
        if not rights.display:
            return denied("access_denied")
        columns = {item["name"] for item in conn.execute("PRAGMA table_info(knowledge_attachment_originals)")}
        if not {"id", "attachment_id", "role", "original_path", "bytes"} <= columns:
            return denied("unavailable")
        originals = conn.execute("SELECT id,original_path,bytes FROM knowledge_attachment_originals "
            "WHERE attachment_id=? AND role='original'", (attachment_id,)).fetchall()
        if len(originals) != 1 or not originals[0]["original_path"]:
            return denied("unavailable")
        if self._deleted(conn, originals[0]["id"], "attachment_original"):
            return denied("not_found")
        try:
            root = self.paths.library.resolve()
            folder = (root / "attachments" / attachment_id).resolve()
            path = Path(originals[0]["original_path"]).resolve()
            available = (folder.is_relative_to(root) and path.is_relative_to(folder)
                         and path.is_file() and path.stat().st_size == originals[0]["bytes"])
        except (OSError, ValueError):
            available = False
        return {"allowed": True} if available else denied("unavailable")
