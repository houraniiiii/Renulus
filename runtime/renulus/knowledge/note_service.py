# SPDX-License-Identifier: MIT
"""Notes adapt the canonical Library owner, immutable originals and project links."""
import hashlib

from ..contracts import ApiError
from ..design_c_contracts import ContentReference
from ..storage.assessment_policy import require_assistance
from .models import Rights, SourceMetadata, own_text_rights
from .note_models import MAX_NOTE_BYTES

TITLE_PREFIX = "renulus:note-title:"


class NotesService:
    def __init__(self, services):
        self.services, self.db = services, services.db

    @property
    def knowledge(self):
        return self.services.get("knowledge")

    def _summary_in(self, conn, row):
        # The pin is assembled from canonical rows, never from note request data.
        authority = self.knowledge.require_original_display_in(conn, {
            "document_id": row["document_id"], "revision_id": row["id"],
            "original_sha256": row["sha256"]})
        metadata = SourceMetadata.model_validate(authority["metadata"])
        title = next((value[len(TITLE_PREFIX):] for value in reversed(metadata.notes)
            if value.startswith(TITLE_PREFIX)), row["title"])
        reference = ContentReference(target={"type": "note_revision", "id": row["id"]})
        return {"document_id": row["document_id"], "revision_id": row["id"],
            "ordinal": row["ordinal"], "title": title, "updated_at": row["created_at"],
            "reference": reference.model_dump(mode="json")}, authority

    def list(self, *, project_id=None, limit=100, offset=0):
        with self.knowledge._lock, self.db.transaction() as conn:
            require_assistance(conn)
            if project_id is not None:
                # The Project owner permits inspection of active/archived projects.
                self.services.get("projects")._get(conn, project_id)
            condition, args = "", []
            if project_id is not None:
                condition = (" AND EXISTS(SELECT 1 FROM study_project_documents m WHERE m.revision_id=r.id "
                    "AND m.project_id=? AND NOT EXISTS(SELECT 1 FROM deletion_ledger "
                    "WHERE entity_type='project_document' AND entity_id=m.id))")
                args.append(project_id)
            rows = conn.execute("SELECT r.id,r.document_id FROM knowledge_documents d JOIN knowledge_revisions r "
                "ON r.id=d.latest_revision WHERE d.deleted_at IS NULL AND d.scope_kind='personal-library' "
                "AND d.scope_entity IS NULL AND d.reserved=0 AND EXISTS(SELECT 1 FROM "
                "json_each(CASE WHEN json_valid(r.metadata_json) THEN r.metadata_json ELSE '{}' END,'$.asset_role') "
                "WHERE value='study-note')" + condition + " ORDER BY r.created_at DESC,r.id DESC LIMIT ? OFFSET ?",
                (*args, limit, offset)).fetchall()
            items = []
            for candidate in rows:
                try:
                    row = self.knowledge._note_row_in(conn, candidate["document_id"], candidate["id"])
                    summary, _ = self._summary_in(conn, row)
                except ApiError as error:
                    if error.status in (403, 404) and error.code != "assistance_restricted":
                        continue
                    raise
                items.append(summary)
            require_assistance(conn)
            return {"items": items}

    def get(self, document_id, *, revision_id=None):
        with self.knowledge._lock, self.db.transaction() as conn:
            require_assistance(conn)
            row = self.knowledge._note_row_in(conn, document_id, revision_id)
            summary, authority = self._summary_in(conn, row)
            original = authority["original"]
            if original["bytes"] > MAX_NOTE_BYTES:
                raise ApiError("note_limit", "This note exceeds the editable text limit", 413)
            path = self.services.paths.root / original["relative_path"]
            try:
                with path.open("rb") as source:
                    data = source.read(MAX_NOTE_BYTES + 1)
                if len(data) != original["bytes"] or hashlib.sha256(data).hexdigest() != original["sha256"]:
                    raise ValueError()
                text = data.decode("utf-8", errors="strict")
            except (OSError, ValueError):
                raise ApiError("original_missing", "The saved note original is unavailable", 404) from None
            # Recheck the original and current policy before publishing the body.
            self.knowledge.require_original_display_in(conn, {"document_id": document_id,
                "revision_id": row["id"], "original_sha256": original["sha256"]})
            require_assistance(conn)
            return {**summary, "text": text}

    def save(self, request, *, document_id=None):
        owner = self.knowledge
        expected = getattr(request, "expected_revision_id", None)
        if document_id is None:
            metadata, rights = SourceMetadata(asset_role=["study-note"]), own_text_rights()
        else:
            with owner._lock, self.db.transaction() as conn:
                require_assistance(conn)
                row = owner._note_row_in(conn, document_id, expected)
                authority = owner.require_original_display_in(conn, {"document_id": document_id,
                    "revision_id": row["id"], "original_sha256": row["sha256"]})
                metadata, rights = SourceMetadata.model_validate(authority["metadata"]), Rights.model_validate(authority["rights"])
                if metadata.access_class != "user-owned" or rights.licence != "user-owned":
                    raise ApiError("note_edit_denied", "This source is not a user-authored editable note", 403)
        metadata = metadata.model_copy(update={
            "notes": [value for value in metadata.notes if not value.startswith(TITLE_PREFIX)] + [TITLE_PREFIX + request.title],
            "original_sha256": hashlib.sha256(request.text.encode("utf-8")).hexdigest()})
        result = owner.import_text(request.text, title=request.title, metadata=metadata, rights=rights,
            document_id=document_id, idempotency_key=request.idempotency_key, process=False,
            expected_revision_id=expected, note_save=True, note_project_id=getattr(request, "project_id", None))
        worker = self.services.registry.get("knowledge_worker")
        if worker is not None and result["status"] == "queued":
            worker.prioritize(result["job"]["id"])
        return self.get(result["document_id"], revision_id=result["revision_id"])

    def delete(self, document_id, request):
        self.knowledge.delete_document(document_id, expected_revision_id=request.expected_revision_id,
            idempotency_key=request.idempotency_key, note_delete=True)
        return {"document_id": document_id, "revision_id": request.expected_revision_id, "deleted": True}
