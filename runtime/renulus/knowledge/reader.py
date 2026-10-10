# SPDX-License-Identifier: MIT
"""Canonical-reference reader; originals do not depend on an index or model."""
from dataclasses import dataclass
from contextlib import closing
import hashlib
import json
from pathlib import Path

from ..contracts import ApiError
from ..cases.originals import load_metadata, read_original
from ..storage.assessment_policy import policy_snapshot, require_assistance
from ..storage.invalidation import context_epoch_in
from .models import Rights
from .reader_binary import binary_asset, docx_payload, image_payload, pdf_payload, xlsx_payload
from .reader_models import ReaderRequest
from .reader_text import text_payload

MEDIA_SUFFIX = {
    "application/pdf": ".pdf", "text/plain": ".txt", "text/markdown": ".md",
    "text/csv": ".csv", "text/html": ".html", "application/xml": ".xml", "text/xml": ".xml",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "image/png": ".png", "image/jpeg": ".jpg", "image/tiff": ".tiff",
}
MAX_ORIGINAL_BYTES = 64 * 1024 * 1024


@dataclass
class Original:
    authority: str
    id: str
    title: str
    filename: str
    media_type: str
    sha256: str
    size: int
    rights: dict
    data: bytes | None = None
    path: Path | None = None
    revision: int | None = None
    metadata: dict | None = None
    policy_revision: int | None = None
    context_epoch: int | None = None


class ReaderRepository:
    def __init__(self, services):
        self.services, self.db, self.paths = services, services.db, services.paths
        self._policy_snapshot = policy_snapshot
        self._require_assistance = require_assistance
        self._context_epoch_in = context_epoch_in

    def _policy(self, request, operation):
        if self._policy_snapshot is None:
            if operation == "passage":
                raise ApiError("reader_policy_unavailable", "The shared source-use policy is not connected", 503, True)
            return None, None
        with closing(self.db.connect()) as conn:
            conn.execute("BEGIN")
            snapshot = self._policy_snapshot(conn)
            expected = request.expected_policy_revision if operation == "passage" else None
            if operation == "passage" and (expected is None or request.expected_context_epoch is None):
                raise ApiError("reader_revision_conflict", "Reopen the source before selecting a passage", 409, True)
            self._require_assistance(conn, expected_revision=expected)
            epoch = self._context_epoch_in(conn)
            if operation == "passage" and request.expected_context_epoch != epoch:
                raise ApiError("reader_context_changed", "The learning context changed; reopen this source", 409, True)
            return snapshot["revision"], epoch

    def _owned_path(self, value, folder):
        if not value:
            raise ApiError("original_missing", "Restore a full backup containing this original", 404)
        folder = folder.resolve()
        path = Path(value).resolve()
        if not folder.is_relative_to(self.paths.library.resolve()) or not path.is_relative_to(folder) or not path.is_file():
            raise ApiError("original_missing", "The retained original is unavailable", 404)
        return path

    def _library(self, target):
        row = self.db.fetch_one(
            "SELECT r.*,d.title,d.deleted_at,d.scope_kind,d.scope_entity FROM knowledge_revisions r "
            "JOIN knowledge_documents d ON d.id=r.document_id WHERE r.id=?", (target.id,))
        if not row or row["deleted_at"] or row["status"] == "deleted":
            raise ApiError("reader_content_missing", "This source revision is unavailable", 404)
        if row["scope_kind"] in {"temporary-case", "unclassified"}:
            raise ApiError("reader_scope_denied", "This source cannot enter a saved reader", 403)
        path = self._owned_path(row["original_path"],
            self.paths.library / "knowledge" / row["document_id"] / row["id"])
        return Original("knowledge", row["id"], row["title"], path.name, row["media_type"],
            row["sha256"], row["bytes"], json.loads(row["rights_json"]), path=path,
            metadata=json.loads(row["metadata_json"]))

    def _attachment(self, request):
        target, conversation = request.reference.target, request.conversation
        legacy = self.db.fetch_one("SELECT * FROM case_attachments WHERE id=?", (target.id,))
        access = self.services.registry.get("knowledge_attachments")
        if access is None:
            raise ApiError("reader_access_unavailable", "Attachment access is not connected", 503, True)
        with closing(self.db.connect()) as conn:
            conn.execute("BEGIN")
            authorization = access.authorize_in(conn, target.id, context=conversation)
            if not authorization["allowed"]:
                reason = authorization["reason"]
                if reason == "restricted":
                    self._require_assistance(conn)
                if reason == "access_denied":
                    raise ApiError("reader_context_mismatch", "This attachment is not available in this context", 403)
                if reason == "not_found":
                    raise ApiError("reader_content_missing", "This attachment is unavailable", 404)
                columns = {row["name"] for row in conn.execute("PRAGMA table_info(knowledge_attachments)")}
                if not legacy and conversation is None and "rights_json" not in columns:
                    raise ApiError("reader_schema_unavailable", "The attachment storage update is not installed", 503, True)
                raise ApiError("reader_original_unavailable", "The attachment original is currently unavailable", 409, True)
        if legacy:
            if conversation and (conversation.type != "case" or conversation.id != legacy["case_id"]):
                raise ApiError("reader_context_mismatch", "This original belongs to another conversation", 403)
            metadata = next((item for item in load_metadata(self.db, legacy["case_id"])
                             if item["id"] == target.id), None)
            if not metadata or not self.db.fetch_one("SELECT id FROM case_sessions WHERE id=?", (legacy["case_id"],)):
                raise ApiError("reader_content_missing", "The saved Case original is unavailable", 404)
            # Legacy Case bytes and integrity checking remain in their original owner.
            data = read_original(self.db, metadata)
            return Original("case", metadata["id"], metadata["title"], metadata["filename"],
                metadata["media_type"], metadata["sha256"], metadata["bytes"],
                Rights(display=True).model_dump(), data=data)
        if conversation and conversation.type == "case" and "cases" in self.services.registry:
            # Existing unsaved Case originals remain in its volatile session.
            try:
                metadata, data = self.services.get("cases").original(conversation.id, target.id)
                return Original("case", metadata["id"], metadata["title"], metadata["filename"],
                    metadata["media_type"], metadata["sha256"], metadata["bytes"],
                    Rights(display=True).model_dump(), data=data)
            except ApiError as error:
                if error.status not in {404, 410}:
                    raise
        required = {"rights_json", "metadata_json", "filename"}
        columns = {row["name"] for row in self.db.fetch_all("PRAGMA table_info(knowledge_attachments)")}
        if not required <= columns:
            raise ApiError("reader_schema_unavailable", "The attachment storage update is not installed", 503, True)
        row = self.db.fetch_one("SELECT * FROM knowledge_attachments WHERE id=?", (target.id,))
        if not row:
            raise ApiError("reader_content_missing", "This attachment is unavailable", 404)
        expected_type = "case" if row["chat_kind"] == "case" else "learn_thread"
        if conversation and (conversation.type != expected_type or conversation.id != row["chat_id"]):
            raise ApiError("reader_context_mismatch", "This attachment belongs to another conversation", 403)
        parent = "case_sessions" if row["chat_kind"] == "case" else "learn_threads"
        if not self.db.fetch_one(f"SELECT id FROM {parent} WHERE id=?", (row["chat_id"],)):
            raise ApiError("reader_content_missing", "The attachment's conversation is unavailable", 404)
        originals = self.db.fetch_all("SELECT * FROM knowledge_attachment_originals WHERE attachment_id=? AND role='original'", (target.id,))
        if len(originals) != 1:
            raise ApiError("original_missing", "The attachment has no unique retained original", 404)
        original = originals[0]
        path = self._owned_path(original["original_path"], self.paths.library / "attachments" / row["id"])
        return Original("knowledge", original["id"], row["title"], row["filename"], row["media_type"],
            original["sha256"], original["bytes"], json.loads(row["rights_json"]), path=path,
            revision=row["revision"], metadata=json.loads(row["metadata_json"]))

    def original(self, request, operation="read"):
        policy_revision, context_epoch = self._policy(request, operation)
        target = request.reference.target
        if target.type in {"library_revision", "note_revision"}:
            original = self._library(target)
        elif target.type == "attachment":
            original = self._attachment(request)
        else:
            raise ApiError("reader_target_unsupported", "This reference belongs to a different workspace viewer", 422)
        if not original.rights.get("display"):
            raise ApiError("display_denied", "Display permission is unavailable for this original", 403)
        original.policy_revision, original.context_epoch = policy_revision, context_epoch
        if not 0 < original.size <= MAX_ORIGINAL_BYTES:
            raise ApiError("reader_original_limit", "The original exceeds the 64 MiB reader limit", 413)
        if original.path:
            with original.path.open("rb") as source:
                original.data = source.read(MAX_ORIGINAL_BYTES + 1)
        if len(original.data or b"") != original.size or hashlib.sha256(original.data).hexdigest() != original.sha256:
            raise ApiError("reader_original_integrity", "The retained bytes do not match this original", 409)
        return original

    def _request_position(self, request):
        locator = request.reference.locator
        updates = {}
        if locator and locator.kind == "pdf" and "page" not in request.model_fields_set:
            updates["page"] = locator.physical_page
        elif locator and locator.kind == "image" and "page" not in request.model_fields_set:
            updates["page"] = locator.frame
        elif locator and locator.kind == "table":
            if "sheet" not in request.model_fields_set:
                updates["sheet"] = locator.sheet_name
            if "first_row" not in request.model_fields_set:
                updates["first_row"] = locator.first_row
        elif locator and locator.kind == "text" and locator.item_ref.startswith("reader-v1:pdf:") and "page" not in request.model_fields_set:
            try:
                updates["page"] = int(locator.item_ref.rsplit(":", 1)[1])
            except ValueError:
                raise ApiError("reader_selection_unavailable", "The PDF text location is invalid", 422) from None
        return request.model_copy(update=updates)

    def payload(self, original, request):
        request = self._request_position(request)
        suffix = MEDIA_SUFFIX.get(original.media_type.split(";")[0].strip().lower())
        try:
            if suffix == ".pdf":
                return pdf_payload(original.data, request)
            if suffix == ".docx":
                return docx_payload(original.data, request)
            if suffix == ".xlsx":
                return xlsx_payload(original.data, request)
            if suffix in {".png", ".jpg", ".tiff"}:
                return image_payload(original.data, request)
            if suffix in {".txt", ".md", ".csv", ".html", ".xml"}:
                return text_payload(original.data, suffix, request)
        except ImportError:
            raise ApiError("reader_helper_unavailable", "The selected local parser is not installed", 503, True) from None
        except ApiError:
            raise
        except Exception:
            raise ApiError("reader_parse_failed", "The original could not be parsed safely", 422) from None
        raise ApiError("reader_format_unsupported", "This format has no in-app reader yet", 422)

    def _check_current(self, request, original, operation="read"):
        current = self.original(request, operation)
        if (current.id, current.sha256, current.revision, current.rights, current.metadata, current.policy_revision, current.context_epoch) != (original.id, original.sha256, original.revision, original.rights, original.metadata, original.policy_revision, original.context_epoch):
            raise ApiError("reader_revision_conflict", "The source changed while it was being read; reopen it", 409, True)

    def resolve(self, request):
        original = self.original(request)
        try:
            payload = self.payload(original, request)
            state, error = "ready", None
        except ApiError as caught:
            payload, state = None, "unsupported" if caught.code == "reader_format_unsupported" else "failed"
            error = {"code": caught.code, "message": caught.message}
        self._check_current(request, original)
        return {"schema_version": "reader/1", "reference": request.reference.model_dump(mode="json"),
            "title": original.title, "media_type": original.media_type, "authority": original.authority,
            "original": {"id": original.id, "sha256": original.sha256, "bytes": original.size,
                         "filename": original.filename, "available": True},
            "attachment_revision": original.revision, "preview_state": state,
            "policy_revision": original.policy_revision, "context_epoch": original.context_epoch,
            "extraction_state": "ready" if payload and (payload.blocks or payload.table) else "unavailable",
            "capabilities": {"read": state == "ready", "original": True,
                             "passage": bool(self._policy_snapshot and original.rights.get("model_input") and payload and (payload.blocks or payload.table)),
                             "ocr": False, "model_image": False},
            "payload": payload.model_dump(mode="json") if payload else None, "error": error}

    def asset(self, request):
        original = self.original(request)
        if original.sha256 != request.original_sha256:
            raise ApiError("reader_revision_conflict", "The original changed; reopen it", 409)
        # No caller-supplied URLs/paths: the parser interprets a bounded asset ID.
        data = binary_asset(original.data, MEDIA_SUFFIX.get(original.media_type), request.asset_id)
        self._check_current(request, original)
        return data

    def download(self, request):
        original = self.original(request)
        self._check_current(request, original)
        return original

    def passage(self, request):
        original = self.original(request, "passage")
        if original.sha256 != request.original_sha256:
            raise ApiError("reader_revision_conflict", "The original changed; select the passage again", 409)
        metadata = original.metadata or {}
        if not original.rights.get("model_input") or any(metadata.get(key) for key in ("retracted", "superseded", "access_changed")):
            raise ApiError("reader_passage_denied", "This source is not eligible for model input", 403)
        selected = request.model_copy(update={"reference": request.reference.model_copy(update={"locator": request.locator})})
        payload = self.payload(original, selected)
        locator = request.locator
        text = None
        if locator.kind == "text":
            item = next((item for item in payload.blocks if item.item_ref == locator.item_ref), None)
            if item and 0 <= locator.start < locator.end <= len(item.text):
                text = item.text[locator.start:locator.end]
        elif locator.kind == "pdf" and payload.kind == "pdf":
            text = "\n".join(item.text for item in payload.blocks)
        elif locator.kind == "table" and payload.table:
            table = payload.table
            if (table.format == locator.format and table.sheet_name == locator.sheet_name
                    and locator.last_row < table.first_row + len(table.rows)
                    and locator.last_column <= table.total_columns):
                offset = locator.first_row - table.first_row
                text = "\n".join("\t".join(cell.display for cell in row[locator.first_column - 1:locator.last_column])
                    for row in table.rows[offset:offset + locator.last_row - locator.first_row + 1])
        if not text or not text.strip() or len(text) > 8000:
            raise ApiError("reader_selection_unavailable", "Select a nonempty passage up to 8,000 characters", 422)
        self._check_current(request, original, "passage")
        return {"text": text, "reference": selected.reference.model_dump(mode="json"), "title": original.title}
