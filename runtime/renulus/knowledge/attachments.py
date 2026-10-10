# SPDX-License-Identifier: MIT
"""Ordinary attachments; canonical conversation metadata decides retention.

The narrow adapter uses the ConversationRepository's existing locks and command
seams. Case originals are never adopted or copied into this owner.
"""
from contextlib import closing, contextmanager
from copy import deepcopy
import hashlib
import json

from ..contracts import ApiError, durable_id
from ..design_c_contracts import canonical_digest
from ..learn.conversation_repository import command
from ..storage.assessment_policy import require_assistance
from ..storage import attachment_cleanup
from ..storage.database import utc_now
from ..storage.invalidation import context_epoch_in
from .attachment_access import KnowledgeAttachmentAccess, denied
from .attachment_files import ATTACHMENT_ID, admit, remove_folder, write_original
from .attachment_models import UploadIdentity
from .engines import MAX_BYTES, TEMP_MAX_BYTES

MAX_CHAT_ATTACHMENTS = 20
MAX_VOLATILE_CHAT_BYTES = 32 * 1024 * 1024
MAX_VOLATILE_BYTES = 128 * 1024 * 1024


class AttachmentPromotion:
    """Caller acknowledges its transaction; this helper never commits SQLite."""
    def __init__(self, repository, identifiers):
        self.repository, self.identifiers = repository, identifiers

    def commit(self):
        # Call after the conversation transaction commits, with owner locks
        # retained. No volatile original is discarded while the save can fail.
        for identifier in self.identifiers:
            if not self.repository.db.fetch_one("SELECT id FROM knowledge_attachments WHERE id=?", (identifier,)):
                raise ApiError("attachment_promotion_uncommitted", "The attachment save did not commit", 409)
        for identifier in self.identifiers:
            self.repository._volatile.pop(identifier, None)

    def rollback(self):
        # Call after rollback. Never remove a folder whose row actually committed.
        for identifier in self.identifiers:
            if not self.repository.db.fetch_one("SELECT id FROM knowledge_attachments WHERE id=?", (identifier,)):
                remove_folder(self.repository.paths, identifier)


class KnowledgeAttachments(KnowledgeAttachmentAccess):
    def __init__(self, services):
        super().__init__(services)
        self.db = services.db
        self._volatile = {}
        self._volatile_commands = {}

    @property
    def conversations(self):
        owner = self.services.registry.get("conversations")
        if owner is None:
            raise ApiError("attachment_owner_unavailable", "Conversation attachments are not connected", 503, True)
        return owner

    @staticmethod
    def kind(identity):
        return "case" if identity.type == "case" else "learning"

    def _guard(self, conn, request):
        require_assistance(conn, expected_revision=request.expected_policy_revision)
        if context_epoch_in(conn) != request.expected_context_epoch:
            raise ApiError("attachment_context_changed", "The learning context changed; reopen this chat", 409, True)

    @contextmanager
    def promotion_guard(self):
        """Caller takes this before conversation locks and before SQLite."""
        with self.services.get("knowledge")._ingest_lock:
            yield

    @contextmanager
    def _locked(self):
        # Recovery takes the Knowledge ingestion lock before SQLite. Reuse it;
        # attachment originals must not publish across media restoration.
        owner = self.conversations
        with self.promotion_guard(), owner._lock, owner.cases._lock:
            yield owner

    def prepare_promotion_in(self, conn, kind, chat_id):
        """Caller holds promotion_guard/owner locks and its transaction.

        Stage before Chat validates draft references. Call lease.commit() after
        commit or lease.rollback() after rollback. Legacy Case originals are not
        included; their existing owner already promotes those bytes.
        """
        require_assistance(conn)
        if not conn.in_transaction:
            raise ValueError("Attachment promotion needs the caller transaction")
        state = self.conversations._temporary.get((kind, chat_id))
        if state is None:
            raise ApiError("attachment_context_changed", "This temporary chat is unavailable", 409)
        records = [record for record in self._volatile.values()
            if (record["chat_kind"], record["chat_id"]) == (kind, chat_id)]
        for record in records:
            if not record["rights"]["display"] or not record["rights"]["cache"]:
                raise ApiError("attachment_cache_denied", "Local caching permission is required before saving this chat", 403)
            if record["epoch"] != context_epoch_in(conn):
                raise ApiError("attachment_context_changed", "Reopen this chat before saving its attachments", 409, True)
            if hashlib.sha256(record["data"]).hexdigest() != record["sha256"]:
                raise ApiError("attachment_hash_mismatch", "A temporary original changed before saving", 409)
        lease = AttachmentPromotion(self, [])
        try:
            for record in records:
                path = write_original(self.paths, record["id"], record["media_type"], record["data"])
                lease.identifiers.append(record["id"])
                self._insert_in(conn, record, path)
        except BaseException:
            # Rows are still uncommitted in the caller transaction. Remove only
            # files this staging attempt created; caller will roll back its rows.
            for identifier in lease.identifiers:
                remove_folder(self.paths, identifier)
            raise
        return lease

    def delete_chat_in(self, conn, kind, chat_id):
        """Return an inert file-cleanup plan; the caller owns commit and journal.

        Never delete bytes here. The FK cascade clears originals and processing
        sidecars atomically with the tombstones. Case bytes remain Case authority.
        """
        require_assistance(conn)
        if not conn.in_transaction:
            raise ValueError("Attachment removal needs the caller transaction")
        if kind not in {"learning", "case"}:
            raise ValueError("Unregistered conversation kind")
        rows = conn.execute("SELECT id FROM knowledge_attachments WHERE chat_kind=? AND chat_id=? LIMIT 201", (kind, chat_id)).fetchall()
        if len(rows) > 200:
            raise ApiError("attachment_cleanup_limit", "This chat needs a bounded attachment cleanup", 409)
        # Validate the complete plan before changing any canonical authority.
        if any(not ATTACHMENT_ID.fullmatch(row["id"]) for row in rows):
            raise ApiError("attachment_id_invalid", "The attachment cleanup identifier is invalid", 409)
        plan = [{"attachment_id": row["id"], "relative_directory": "library/attachments/" + row["id"]} for row in rows]
        for row in rows:
            identifier = row["id"]
            self.db.mark_deleted("attachment", identifier, conn)
            for original in conn.execute("SELECT id FROM knowledge_attachment_originals WHERE attachment_id=?", (identifier,)):
                self.db.mark_deleted("attachment_original", original["id"], conn)
        conn.execute("DELETE FROM knowledge_attachments WHERE chat_kind=? AND chat_id=?", (kind, chat_id))
        return plan

    def cleanup_deleted(self, identifiers):
        """After caller commit; retryable cleanup remains in the owned folder."""
        with self.promotion_guard():
            for identifier in identifiers:
                if self.db.is_deleted("attachment", identifier):
                    remove_folder(self.paths, identifier)

    def discard_volatile(self, kind, chat_id):
        """Chat invokes after successful temporary deletion, under its lock."""
        with self.conversations._lock:
            removed = set()
            for identifier, record in list(self._volatile.items()):
                if (record["chat_kind"], record["chat_id"]) == (kind, chat_id):
                    del self._volatile[identifier]
                    removed.add(identifier)
            for key, (_, receipt) in list(self._volatile_commands.items()):
                context = receipt.get("conversation", {})
                if (receipt.get("id") in removed or (context.get("id") == chat_id
                        and context.get("type") == ("case" if kind == "case" else "learn_thread"))):
                    del self._volatile_commands[key]

    def preflight(self, request):
        with self._locked() as owner, self.db.transaction() as conn:
            self._guard(conn, request)
            summary, _ = owner._get(conn, self.kind(request.conversation), request.conversation.id)
            if summary["lifecycle"] != "active":
                raise ApiError("attachment_chat_archived", "Restore this chat before adding attachments", 409)
            if not request.rights.display:
                raise ApiError("attachment_display_denied", "Display permission is required for this attachment", 403)
            if summary["retention"] == "saved" and not request.rights.cache:
                raise ApiError("attachment_cache_denied", "Local caching permission is required for a saved attachment", 403)
            return TEMP_MAX_BYTES if summary["retention"] == "temporary" else MAX_BYTES

    @staticmethod
    def _public(record, summary):
        return {"reference": {"target": {"type": "attachment", "id": record["id"]}, "locator": None},
            "id": record["id"], "title": record["title"], "filename": record["filename"],
            "media_type": record["media_type"], "revision": record["revision"],
            "original": {"id": record["original_id"], "bytes": record["bytes"], "sha256": record["sha256"]},
            "preview_state": record.get("preview_state", "not_requested"),
            "extraction_state": record.get("extraction_state", "not_requested"),
            "index_state": record.get("index_state", "not_requested"),
            "conversation": summary["identity"], "retention": summary["retention"],
            "conversation_revision": summary["revision"]}

    def _insert_in(self, conn, record, path):
        now = record["created_at"]
        conn.execute("INSERT INTO knowledge_attachments(id,chat_kind,chat_id,title,media_type,revision,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?)", (record["id"], record["chat_kind"], record["chat_id"], record["title"],
                record["media_type"], record["revision"], now, now))
        conn.execute("INSERT INTO knowledge_attachment_originals(id,attachment_id,role,original_path,sha256,bytes,created_at) "
            "VALUES(?,?,'original',?,?,?,?)", (record["original_id"], record["id"], str(path), record["sha256"], record["bytes"], now))
        conn.execute("INSERT INTO knowledge_attachment_metadata(attachment_id,filename,source_id,metadata_json,rights_json) "
            "VALUES(?,?,?,?,?)", (record["id"], record["filename"], record["metadata"]["source_id"],
                json.dumps(record["metadata"]), json.dumps(record["rights"])))

    def _bump(self, conn, owner, summary, state):
        now = utc_now()
        if summary["retention"] == "temporary":
            state["summary"]["revision"] += 1
            state["summary"]["updated_at"] = now
            return deepcopy(state["summary"])
        _, sidecar, column, _ = owner._owner(summary["kind"])
        conn.execute(f"UPDATE {sidecar} SET revision=revision+1,updated_at=? WHERE {column}=?", (now, summary["identity"]["id"]))
        return owner._saved(conn, summary["kind"], summary["identity"]["id"])[0]

    def upload(self, request, data):
        media_type = admit(request.filename, data, max_bytes=self.preflight(request))
        digest = hashlib.sha256(data).hexdigest()
        if request.metadata.original_sha256 not in {None, digest}:
            raise ApiError("attachment_hash_mismatch", "The selected bytes disagree with their source metadata", 409)
        identity = UploadIdentity(command=request, sha256=digest, bytes=len(data), media_type=media_type)
        created, pending, before, state = [], None, None, None
        with self._locked() as owner:
            try:
                with self.db.transaction() as conn:
                    self._guard(conn, request)
                    kind, identifier = self.kind(request.conversation), request.conversation.id
                    summary, state = owner._get(conn, kind, identifier)
                    temporary = summary["retention"] == "temporary"
                    if temporary:
                        before = deepcopy(state["summary"])
                    def save():
                        nonlocal pending
                        owner._expected(summary, request.expected_conversation_revision)
                        if summary["lifecycle"] != "active":
                            raise ApiError("attachment_chat_archived", "Restore this chat before adding attachments", 409)
                        if len(data) > (TEMP_MAX_BYTES if temporary else MAX_BYTES):
                            raise ApiError("attachment_limit", "The selected file exceeds this conversation's attachment limit", 413)
                        if not request.rights.display or (not temporary and not request.rights.cache):
                            raise ApiError("attachment_rights_denied", "Confirm display and saved caching permissions", 403)
                        if temporary:
                            entries = [record for record in self._volatile.values()
                                if (record["chat_kind"], record["chat_id"]) == (kind, identifier)]
                            if (len(entries) >= MAX_CHAT_ATTACHMENTS
                                    or sum(record["bytes"] for record in entries) + len(data) > MAX_VOLATILE_CHAT_BYTES
                                    or sum(record["bytes"] for record in self._volatile.values()) + len(data) > MAX_VOLATILE_BYTES):
                                raise ApiError("attachment_capacity", "Remove an attachment before adding another file", 413)
                        elif conn.execute("SELECT COUNT(*) FROM knowledge_attachments WHERE chat_kind=? AND chat_id=?",
                                (kind, identifier)).fetchone()[0] >= MAX_CHAT_ATTACHMENTS:
                            raise ApiError("attachment_capacity", "A chat supports up to 20 attachments", 413)
                        record = {"id": durable_id("attachment"), "original_id": durable_id("original"),
                            "chat_kind": kind, "chat_id": identifier, "title": request.title, "filename": request.filename,
                            "media_type": media_type, "revision": 1, "created_at": utc_now(), "sha256": digest, "bytes": len(data),
                            "metadata": request.metadata.model_copy(update={"original_sha256": digest}).model_dump(),
                            "rights": request.rights.model_dump(), "epoch": context_epoch_in(conn)}
                        if temporary:
                            pending = {**record, "data": data}
                        else:
                            path = write_original(self.paths, record["id"], media_type, data)
                            created.append(record["id"])
                            self._insert_in(conn, record, path)
                        updated = self._bump(conn, owner, summary, state)
                        self._guard(conn, request)
                        return self._public(record, updated)
                    if temporary:
                        hash_value = canonical_digest(identity.model_dump(mode="json"))
                        previous = self._volatile_commands.get(request.idempotency_key)
                        if previous:
                            if previous[0] != hash_value:
                                raise ApiError("idempotency_conflict", "This request key was already used for different work", 409)
                            result = deepcopy(previous[1])
                            access = self._volatile_snapshot(conn, result["id"], request.conversation)
                            if not access or not access.get("allowed"):
                                raise ApiError("attachment_missing", "The original attachment is no longer available", 404)
                            return result
                        result = save()
                    else:
                        result = command(conn, "conversation_commands", request.idempotency_key, "attach",
                            request.conversation.type, identifier, identity, save)
                        if not self.authorize_in(conn, result["id"], context=request.conversation)["allowed"]:
                            raise ApiError("attachment_missing", "The original attachment is no longer available", 404)
                # Retain the owner locks across commit and memory publication.
                if pending:
                    self._volatile[pending["id"]] = pending
                    self._volatile_commands[request.idempotency_key] = (hash_value, deepcopy(result))
                return result
            except BaseException:
                if before is not None:
                    state["summary"] = before
                for attachment_id in created:
                    remove_folder(self.paths, attachment_id)
                raise

    def _volatile_snapshot(self, conn, attachment_id, context, *, data=False):
        # The committed row decides retention, including the brief interval
        # before promotion drops its volatile copy. Never acquire an owner lock
        # (or return stale volatile bytes) for an ordinary saved attachment.
        if self._saved_row(conn, attachment_id) is not None:
            return None
        owner = self.services.registry.get("conversations")
        if owner is None:
            return None
        # authorize_in is called with SQLite held. Never wait for owner locks
        # that upload/delete acquire before their database transaction.
        if not owner._lock.acquire(blocking=False):
            return denied("unavailable")
        try:
            record = self._volatile.get(attachment_id)
            if record is None:
                return None
            if context is None or self.kind(context) != record["chat_kind"] or context.id != record["chat_id"]:
                return denied("not_found")
            if owner._temporary.get((record["chat_kind"], record["chat_id"])) is None:
                return denied("not_found")
            if record["epoch"] != context_epoch_in(conn):
                return denied("unavailable")
            if not record["rights"]["display"]:
                return denied("access_denied")
            return dict(record) if data else {"allowed": True}
        finally:
            owner._lock.release()

    def volatile_original(self, attachment_id, *, context):
        with closing(self.db.connect()) as conn:
            conn.execute("BEGIN")
            require_assistance(conn)
            result = self._volatile_snapshot(conn, attachment_id, context, data=True)
            if result is not None and "allowed" in result:
                raise ApiError("attachment_missing", "The temporary original is unavailable", 404)
            return result

    def list(self, conversation):
        with self._locked() as owner, self.db.transaction() as conn:
            policy_revision = require_assistance(conn)
            epoch = context_epoch_in(conn)
            kind, identifier = self.kind(conversation), conversation.id
            summary, _ = owner._get(conn, kind, identifier)
            if summary["retention"] == "temporary":
                records = [record for record in self._volatile.values()
                    if (record["chat_kind"], record["chat_id"]) == (kind, identifier)]
            else:
                rows = conn.execute("SELECT a.*,m.filename,o.id original_id,o.bytes,o.sha256 FROM knowledge_attachments a "
                    "LEFT JOIN knowledge_attachment_metadata m ON m.attachment_id=a.id "
                    "LEFT JOIN knowledge_attachment_originals o ON o.attachment_id=a.id AND o.role='original' "
                    "WHERE a.chat_kind=? AND a.chat_id=? ORDER BY a.created_at,a.id LIMIT 20", (kind, identifier))
                records = [dict(row) for row in rows]
            return {"conversation": summary["identity"], "conversation_revision": summary["revision"],
                "policy_revision": policy_revision, "context_epoch": epoch,
                "items": [{**self._public(record, summary), "access": self.authorize_in(conn, record["id"], context=conversation)}
                    for record in records]}

    def remove(self, attachment_id, request):
        removed, before, state = False, None, None
        with self._locked() as owner:
            try:
                with self.db.transaction() as conn:
                    self._guard(conn, request)
                    kind, identifier = self.kind(request.conversation), request.conversation.id
                    summary, state = owner._get(conn, kind, identifier)
                    temporary = summary["retention"] == "temporary"
                    if temporary:
                        before = deepcopy(state["summary"])
                    def remove():
                        nonlocal removed
                        owner._expected(summary, request.expected_conversation_revision)
                        if temporary:
                            record = self._volatile.get(attachment_id)
                        else:
                            row = conn.execute("SELECT * FROM knowledge_attachments WHERE id=?", (attachment_id,)).fetchone()
                            record = dict(row) if row else None
                        if not record or (record["chat_kind"], record["chat_id"]) != (kind, identifier):
                            raise ApiError("attachment_missing", "This attachment is unavailable in this chat", 404)
                        if record["revision"] != request.expected_attachment_revision:
                            raise ApiError("attachment_revision_conflict", "Reopen this attachment before removing it", 409, True)
                        if not temporary:
                            self.db.mark_deleted("attachment", attachment_id, conn)
                            for row in conn.execute("SELECT id FROM knowledge_attachment_originals WHERE attachment_id=?", (attachment_id,)):
                                self.db.mark_deleted("attachment_original", row["id"], conn)
                            conn.execute("DELETE FROM knowledge_attachments WHERE id=?", (attachment_id,))
                        removed = True
                        updated = self._bump(conn, owner, summary, state)
                        return {"id": attachment_id, "deleted": True, "conversation_revision": updated["revision"]}
                    if temporary:
                        result = owner._volatile_command(request.idempotency_key, "attachment_remove:" + attachment_id,
                            kind, identifier, request, remove)
                    else:
                        result = command(conn, "conversation_commands", request.idempotency_key, "attachment_remove",
                            "attachment", attachment_id, request, remove)
                        # Journal in the same transaction as revocation. Replay
                        # also repairs a pending cleanup from an older runtime.
                        attachment_cleanup.enqueue_in(conn, [{"attachment_id": attachment_id,
                            "relative_directory": "library/attachments/" + attachment_id}])
                if removed:
                    self._volatile.pop(attachment_id, None)
                    if temporary:
                        for key, (_, receipt) in list(self._volatile_commands.items()):
                            if receipt.get("id") == attachment_id:
                                del self._volatile_commands[key]
            except BaseException:
                if before is not None:
                    state["summary"] = before
                raise
            # Parent-owned drain operates only after authoritative commit;
            # locked/interrupted files remain journalled for normal startup.
            if not temporary:
                attachment_cleanup.drain(self.services)
            return result
