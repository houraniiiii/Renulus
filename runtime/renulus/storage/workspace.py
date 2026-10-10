# SPDX-License-Identifier: MIT
"""Local Workspace references, with canonical ownership and display checks."""
import json

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from renulus.contracts import ApiError
from renulus.design_c_contracts import ContentReference, WorkspaceTab
from .assessment_policy import require_assistance
from .database import utc_now

PREFERENCE = "design_c.workspace"


class WorkspacePreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    width: int = Field(default=480, ge=360, le=640, strict=True)
    tabs: list[WorkspaceTab] = Field(default_factory=list, max_length=100)


def context_exists(conn, identity):
    if identity.type == "learn_thread":
        return conn.execute("SELECT 1 FROM learn_threads WHERE id=? AND NOT EXISTS "
            "(SELECT 1 FROM deletion_ledger WHERE entity_type='learn_thread' AND entity_id=?)",
            (identity.id, identity.id)).fetchone() is not None
    if identity.type == "case":
        return conn.execute("SELECT 1 FROM case_sessions WHERE id=? AND NOT EXISTS "
            "(SELECT 1 FROM deletion_ledger WHERE entity_type='case' AND entity_id=?)",
            (identity.id, identity.id)).fetchone() is not None
    if identity.type == "project":
        return conn.execute("SELECT 1 FROM study_projects WHERE id=? AND lifecycle!='deleted' AND NOT EXISTS "
            "(SELECT 1 FROM deletion_ledger WHERE entity_type='project' AND entity_id=?)",
            (identity.id, identity.id)).fetchone() is not None
    return False


class WorkspaceRepository:
    def __init__(self, services):
        self.services, self.db = services, services.db

    def _preferences(self, conn):
        row = conn.execute("SELECT value FROM preferences WHERE key=?", (PREFERENCE,)).fetchone()
        try:
            value = WorkspacePreferences.model_validate_json(row[0]) if row else WorkspacePreferences()
        except (ValidationError, ValueError, TypeError):
            value = WorkspacePreferences()
        value.tabs = [tab for tab in value.tabs if context_exists(conn, tab.context)]
        return value

    def preferences(self):
        with self.db.transaction() as conn:
            require_assistance(conn)
            return self._preferences(conn).model_dump(mode="json")

    def save_preferences(self, value):
        with self.db.transaction() as conn:
            require_assistance(conn)
            previous = self._preferences(conn)
            prior = {(tab.context.key, tab.content.target.key) for tab in previous.tabs}
            tabs = []
            for tab in value.tabs:
                if not context_exists(conn, tab.context):
                    raise ApiError("workspace_context_missing", "Workspace tabs require an existing saved chat or project", 409)
                access = self._content(conn, tab.content, tab.context)
                # Existing unavailable references keep their place. New references
                # must resolve to canonical content, never an in-memory attachment.
                if not access["allowed"] and (tab.context.key, tab.content.target.key) not in prior:
                    raise ApiError("workspace_content_unavailable", "Open this item from its current chat, project or Library", 409)
                tabs.append(tab)
            safe = WorkspacePreferences(width=value.width, tabs=tabs)
            conn.execute("INSERT INTO preferences VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET "
                "value=excluded.value,updated_at=excluded.updated_at",
                (PREFERENCE, safe.model_dump_json(), utc_now()))
            return safe.model_dump(mode="json")

    def _content(self, conn, reference, context):
        target = reference.target
        denied = {"allowed": False, "reason": "not_found"}
        if target.type in ("library_revision", "note_revision"):
            row = conn.execute("SELECT r.rights_json,d.deleted_at,d.scope_kind,d.scope_entity "
                "FROM knowledge_revisions r JOIN knowledge_documents d ON d.id=r.document_id WHERE r.id=? "
                "AND r.status!='deleted' AND NOT EXISTS (SELECT 1 FROM deletion_ledger WHERE "
                "(entity_type IN ('knowledge-document','document') AND entity_id=d.id) OR "
                "(entity_type IN ('knowledge-revision','revision') AND entity_id=r.id))",
                (target.id,)).fetchone()
            if not row or row["deleted_at"]:
                return denied
            if row["scope_kind"] in ("temporary-case", "unclassified"):
                return {"allowed": False, "reason": "access_denied"}
            if row["scope_kind"] == "saved-case" and (context is None or context.type != "case" or context.id != row["scope_entity"]):
                return {"allowed": False, "reason": "access_denied"}
            try:
                display = json.loads(row["rights_json"]).get("display") is True
            except (ValueError, AttributeError):
                display = False
            return {"allowed": True} if display else {"allowed": False, "reason": "access_denied"}
        if target.type == "saved_test_version":
            row = conn.execute("SELECT 1 FROM assessment_test_versions v JOIN assessment_tests t ON t.id=v.test_id "
                "WHERE v.id=? AND t.lifecycle!='deleted' AND NOT EXISTS(SELECT 1 FROM deletion_ledger "
                "WHERE (entity_type='saved_test' AND entity_id=t.id) OR (entity_type='saved_test_version' AND entity_id=v.id))",
                (target.id,)).fetchone()
            return {"allowed": True} if row else denied
        # Attachment rights/original authority are owned by Knowledge. The same
        # resolver is used for temporary attachments without persisting metadata.
        owner = self.services.registry.get("knowledge_attachments")
        if owner is not None and hasattr(owner, "authorize_in"):
            return owner.authorize_in(conn, target.id, context=context)
        return {"allowed": False, "reason": "unavailable"}

    def authorize(self, request):
        with self.db.transaction() as conn:
            require_assistance(conn, expected_revision=request.policy.revision)
            context = request.context.identity if request.context else None
            if request.context and request.context.retention == "saved" and not context_exists(conn, context):
                return {"allowed": False, "reason": "not_found"}
            if request.kind == "section":
                return {"allowed": True}
            return self._content(conn, request.reference, context)

    def titles(self, request):
        """Volatile display metadata, resolved under the same access/policy gate."""
        with self.db.transaction() as conn:
            require_assistance(conn, expected_revision=request.policy.revision)
            context = request.context.identity if request.context else None
            if request.context and request.context.retention == "saved" and not context_exists(conn, context):
                return {"items": []}
            items = []
            for reference in request.references:
                if not self._content(conn, reference, context)["allowed"]:
                    continue
                target = reference.target
                if target.type in ("library_revision", "note_revision"):
                    row = conn.execute("SELECT d.title FROM knowledge_revisions r JOIN knowledge_documents d "
                        "ON d.id=r.document_id WHERE r.id=?", (target.id,)).fetchone()
                elif target.type == "saved_test_version":
                    row = conn.execute("SELECT t.title FROM assessment_test_versions v JOIN assessment_tests t "
                        "ON t.id=v.test_id WHERE v.id=?", (target.id,)).fetchone()
                else:
                    row = conn.execute("SELECT title FROM knowledge_attachments WHERE id=?", (target.id,)).fetchone()
                    if row is None:
                        row = conn.execute("SELECT filename AS title FROM case_attachments WHERE id=?", (target.id,)).fetchone()
                if row and isinstance(row["title"], str) and row["title"].strip():
                    items.append({"target": target.model_dump(mode="json"), "title": row["title"][:240]})
            return {"items": items}

    def entries(self, section, context=None):
        with self.db.transaction() as conn:
            require_assistance(conn)
            if context is not None and not context_exists(conn, context):
                raise ApiError("workspace_context_missing", "This saved context is unavailable", 404)
            if section == "Goals":
                if context is None or context.type != "project":
                    return {"items": [], "message": "Open a project to see its study goals."}
                return {"items": [dict(row) for row in conn.execute("SELECT id,title,status,target_date,progress_json "
                    "FROM study_project_goals WHERE project_id=? ORDER BY created_at,id LIMIT 100", (context.id,))]}
            parameters = []
            where = "d.deleted_at IS NULL AND d.scope_kind NOT IN ('temporary-case','unclassified','saved-case')"
            if context is not None and context.type == "project":
                where += " AND r.id IN (SELECT revision_id FROM study_project_documents WHERE project_id=?)"
                parameters.append(context.id)
            elif context is not None and context.type == "case":
                where = "d.deleted_at IS NULL AND (d.scope_kind NOT IN ('temporary-case','unclassified','saved-case') OR (d.scope_kind='saved-case' AND d.scope_entity=?))"
                parameters.append(context.id)
            if context is None or context.type != "project":
                where += " AND r.id=d.latest_revision"
            rows = conn.execute("SELECT r.id,r.status,r.media_type,r.metadata_json,r.rights_json,d.title FROM knowledge_revisions r "
                "JOIN knowledge_documents d ON d.id=r.document_id WHERE " + where +
                " ORDER BY d.updated_at DESC,d.id LIMIT 100", parameters).fetchall()
            items = []
            for row in rows:
                try:
                    metadata, rights = json.loads(row["metadata_json"]), json.loads(row["rights_json"])
                    note = "study-note" in metadata.get("asset_role", [])
                    if rights.get("display") is not True or (section == "Notes" and not note):
                        continue
                except (ValueError, AttributeError, TypeError):
                    continue
                items.append({"title": row["title"], "status": row["status"], "media_type": row["media_type"],
                    "reference": ContentReference(target={"type": "note_revision" if note else "library_revision", "id": row["id"]}).model_dump(mode="json")})
            if section == "Files" and context is not None and context.type in {"learn_thread", "case"}:
                owner = self.services.registry.get("knowledge_attachments")
                if owner is not None:
                    kind = "case" if context.type == "case" else "learning"
                    # Metadata-only enumeration in the same canonical transaction.
                    # The owner decides live display/original availability; do not
                    # call its locking inventory method while holding SQLite.
                    for row in conn.execute("SELECT id,title,media_type FROM knowledge_attachments "
                            "WHERE chat_kind=? AND chat_id=? ORDER BY created_at,id LIMIT 100", (kind, context.id)):
                        if owner.authorize_in(conn, row["id"], context=context).get("allowed"):
                            items.append({"title": row["title"], "status": "Saved attachment", "media_type": row["media_type"],
                                "reference": ContentReference(target={"type": "attachment", "id": row["id"]}).model_dump(mode="json")})
                    if kind == "case":
                        for row in conn.execute("SELECT id,filename,media_type FROM case_attachments WHERE case_id=? ORDER BY id LIMIT 100", (context.id,)):
                            if owner.authorize_in(conn, row["id"], context=context).get("allowed"):
                                items.append({"title": row["filename"], "status": "Saved case attachment", "media_type": row["media_type"],
                                    "reference": ContentReference(target={"type": "attachment", "id": row["id"]}).model_dump(mode="json")})
            return {"items": items}
