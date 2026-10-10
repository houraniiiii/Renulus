# SPDX-License-Identifier: MIT
"""Typed chat metadata adapts Learn and Cases; it never duplicates transcripts."""
import base64
from copy import deepcopy
import hmac
import json
import secrets
from threading import RLock

from renulus.contracts import ApiError, durable_id
from renulus.design_c_contracts import ConversationDraft, canonical_digest
from renulus.storage.database import utc_now
from renulus.storage.invalidation import bump_context_epoch

from .conversation_models import Mutation, NewConversation


OWNERS = {"learning": ("learn_threads", "learn_conversations", "thread_id", "learn_thread"),
          "case": ("case_sessions", "case_conversations", "case_id", "case")}


def require_assistance(conn, expected_revision=None):
    from renulus.storage.assessment_policy import require_assistance as check
    return check(conn, expected_revision=expected_revision)


def command(conn, table, key, operation, target_type, target_id, request, action):
    """Two installed ledgers share this small saved-only transaction boundary."""
    require_assistance(conn)  # A stored result never bypasses present policy.
    if table not in ("conversation_commands", "study_project_commands"):
        raise ValueError("Unregistered command owner")
    if key is None:
        return action()
    if not 8 <= len(key) <= 128:
        raise ApiError("invalid_idempotency_key", "Use a request key between 8 and 128 characters", 422)
    digest = canonical_digest({"operation": operation, "target_type": target_type,
        "target_id": target_id, "request": request.model_dump(mode="json")})
    row = conn.execute(f"SELECT * FROM {table} WHERE idempotency_key=?", (key,)).fetchone()
    if row:
        if row["request_hash"] != digest:
            raise ApiError("idempotency_conflict", "This request key was already used for different work", 409)
        return json.loads(row["result_json"])
    result = action()
    conn.execute(f"INSERT INTO {table} VALUES(?,?,?,?,?,?,?)",
        (key, operation, target_type, target_id, digest, json.dumps(result, ensure_ascii=False), utc_now()))
    return result


class ConversationRepository:
    def __init__(self, services):
        self.services, self.db = services, services.db
        self.learn, self.cases = services.get("learn"), services.get("cases")
        self._lock = RLock()
        self._temporary = {}
        self._temporary_commands = {}
        self._cursor_key = secrets.token_bytes(32)

    def _owner(self, kind):
        if kind not in OWNERS:
            raise ApiError("conversation_kind", "Choose Learning or Case", 422)
        return OWNERS[kind]

    def _insert_sidecar(self, conn, kind, identifier):
        _, sidecar, column, _ = self._owner(kind)
        conn.execute(f"INSERT OR IGNORE INTO {sidecar}({column},lifecycle,revision,draft_text,draft_refs_json,draft_revision,updated_at) "
            "VALUES(?,'active',1,'','[]',0,?)", (identifier, utc_now()))

    def _saved(self, conn, kind, identifier):
        table, sidecar, column, target_type = self._owner(kind)
        row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (identifier,)).fetchone()
        if row is None or conn.execute("SELECT 1 FROM deletion_ledger WHERE entity_type=? AND entity_id=?",
                (target_type, identifier)).fetchone():
            raise ApiError("conversation_missing", "This conversation is no longer available", 404)
        self._insert_sidecar(conn, kind, identifier)
        metadata = dict(conn.execute(f"SELECT * FROM {sidecar} WHERE {column}=?", (identifier,)).fetchone())
        membership = conn.execute("SELECT project_id FROM study_project_chats WHERE chat_kind=? AND chat_id=?",
                                  (kind, identifier)).fetchone()
        summary = {"identity": {"type": target_type, "id": identifier}, "kind": kind,
            "retention": "saved", "lifecycle": metadata["lifecycle"], "revision": metadata["revision"],
            "title": row["title"], "project_id": membership["project_id"] if membership else None,
            "created_at": row["created_at"], "updated_at": max(row["updated_at"], metadata["updated_at"])}
        return summary, metadata

    def _get(self, conn, kind, identifier):
        self._owner(kind)
        temporary = self._temporary.get((kind, identifier))
        if temporary:
            return deepcopy(temporary["summary"]), temporary
        return self._saved(conn, kind, identifier)

    def _expected(self, summary, revision):
        if summary["revision"] != revision:
            raise ApiError("conversation_revision_conflict", "Reload this conversation before saving", 409, True)

    def create(self, request: NewConversation, idempotency_key=None):
        created_case = None
        with self._lock, self.cases._lock, self.db.transaction() as conn:
            require_assistance(conn)
            if request.temporary:
                digest = canonical_digest(request.model_dump(mode="json"))
                previous = self._temporary_commands.get(idempotency_key) if idempotency_key else None
                if previous:
                    if previous[0] != digest:
                        raise ApiError("idempotency_conflict", "This request key was already used", 409)
                    return deepcopy(previous[1])
                now = utc_now()
                if request.kind == "case":
                    owner = self.cases.start_conversation(request.title, request.text, request.teaching_case_id)
                    identifier, title = owner["id"], owner["title"]
                else:
                    identifier, title = durable_id("thread"), request.title
                summary = {"identity": {"type": self._owner(request.kind)[3], "id": identifier},
                    "kind": request.kind, "retention": "temporary", "lifecycle": "active",
                    "revision": 1, "title": title, "project_id": None, "created_at": now, "updated_at": now}
                self._temporary[(request.kind, identifier)] = {"summary": summary, "draft_text": "",
                    "draft_refs_json": "[]", "draft_revision": 0, "messages": [], "runs": {}}
                if idempotency_key:
                    self._temporary_commands[idempotency_key] = (digest, deepcopy(summary))
                return deepcopy(summary)
            def save():
                nonlocal created_case
                if request.kind == "learning":
                    owner = self.learn.create_thread(request.title, request.topic_id, request.teaching_style, conn=conn)
                else:
                    owner = self.cases.start_conversation(request.title, request.text, request.teaching_case_id)
                    created_case = owner["id"]
                    owner = self.cases.save(owner["id"], owner["revision"], conn=conn)
                self._insert_sidecar(conn, request.kind, owner["id"])
                if request.project_id:
                    self.services.get("projects").move_chat_in(conn, request.kind, owner["id"], request.project_id)
                return self._saved(conn, request.kind, owner["id"])[0]
            try:
                return command(conn, "conversation_commands", idempotency_key, "create",
                    self._owner(request.kind)[3], "new", request, save)
            except BaseException:
                if created_case:
                    self.cases._sessions.pop(created_case, None)
                raise

    def get(self, kind, identifier):
        with self._lock, self.cases._lock, self.db.transaction() as conn:
            require_assistance(conn)
            return self._get(conn, kind, identifier)[0]

    def draft(self, kind, identifier):
        with self._lock, self.cases._lock, self.db.transaction() as conn:
            require_assistance(conn)
            summary, row = self._get(conn, kind, identifier)
            return {"text": row["draft_text"], "content_refs": json.loads(row["draft_refs_json"]),
                "revision": row["draft_revision"], "conversation_revision": summary["revision"]}

    def validate_refs(self, conn, refs):
        for reference in refs:
            target = reference.target
            if target.type in ("library_revision", "note_revision"):
                row = conn.execute("SELECT d.scope_kind,d.deleted_at,r.status FROM knowledge_revisions r "
                    "JOIN knowledge_documents d ON d.id=r.document_id WHERE r.id=?", (target.id,)).fetchone()
                valid = row and not row["deleted_at"] and row["scope_kind"] not in ("temporary-case", "unclassified")
            elif target.type == "saved_test_version":
                valid = conn.execute("SELECT 1 FROM assessment_test_versions WHERE id=?", (target.id,)).fetchone()
            else:
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                valid = conn.execute("SELECT 1 FROM case_attachments WHERE id=?", (target.id,)).fetchone()
                if not valid and "knowledge_attachments" in tables:
                    valid = conn.execute("SELECT 1 FROM knowledge_attachments WHERE id=?", (target.id,)).fetchone()
            if not valid:
                raise ApiError("content_unavailable", "A referenced saved item is no longer available", 409)

    def save_draft(self, kind, identifier, request: ConversationDraft, idempotency_key=None):
        with self._lock, self.cases._lock, self.db.transaction() as conn:
            require_assistance(conn)
            summary, row = self._get(conn, kind, identifier)
            if summary["retention"] == "temporary":
                self._expected(summary, request.expected_revision)
                row["draft_text"] = request.text
                row["draft_refs_json"] = json.dumps([ref.model_dump(mode="json") for ref in request.content_refs])
                row["draft_revision"] += 1
                row["summary"]["revision"] += 1
                row["summary"]["updated_at"] = utc_now()
                return {"text": row["draft_text"], "content_refs": json.loads(row["draft_refs_json"]),
                    "revision": row["draft_revision"], "conversation_revision": row["summary"]["revision"]}
            def save():
                self._expected(summary, request.expected_revision)
                self.validate_refs(conn, request.content_refs)
                _, table, column, _ = self._owner(kind)
                conn.execute(f"UPDATE {table} SET draft_text=?,draft_refs_json=?,draft_revision=draft_revision+1,"
                    f"revision=revision+1,updated_at=? WHERE {column}=?",
                    (request.text, json.dumps([ref.model_dump(mode="json") for ref in request.content_refs]), utc_now(), identifier))
                updated = conn.execute(f"SELECT * FROM {table} WHERE {column}=?", (identifier,)).fetchone()
                return {"text": updated["draft_text"], "content_refs": json.loads(updated["draft_refs_json"]),
                    "revision": updated["draft_revision"], "conversation_revision": updated["revision"]}
            return command(conn, "conversation_commands", idempotency_key, "draft", summary["identity"]["type"], identifier, request, save)

    def _cursor(self, value):
        raw = json.dumps(value, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw + hmac.digest(self._cursor_key, raw, "sha256")).decode()

    def _uncursor(self, token, scope):
        try:
            data = base64.b64decode(token, altchars=b"-_", validate=True)
            raw, signature = data[:-32], data[-32:]
            if not hmac.compare_digest(signature, hmac.digest(self._cursor_key, raw, "sha256")):
                raise ValueError
            value = json.loads(raw)
            if value["scope"] != scope:
                raise ValueError
            return value
        except (ValueError, KeyError, TypeError):
            raise ApiError("invalid_cursor", "Reload this conversation history", 422) from None

    def messages(self, kind, identifier, limit=50, cursor=None):
        if not 1 <= limit <= 100:
            raise ApiError("invalid_page", "Use a page size between 1 and 100", 422)
        with self._lock, self.cases._lock, self.db.transaction() as conn:
            require_assistance(conn)
            summary, metadata = self._get(conn, kind, identifier)
            scope = ["messages", kind, identifier]
            page = self._uncursor(cursor, scope) if cursor else {}
            after = page.get("after")
            if kind == "learning" and summary["retention"] == "saved":
                boundary = page.get("boundary")
                if boundary is None:
                    last = conn.execute("SELECT created_at,id FROM learn_messages WHERE thread_id=? ORDER BY created_at DESC,id DESC LIMIT 1", (identifier,)).fetchone()
                    boundary = list(last) if last else ["", ""]
                where, args = "thread_id=? AND (created_at,id)<=(?,?)", [identifier, *boundary]
                if after:
                    where += " AND (created_at,id)>(?,?)"
                    args += after
                rows = [dict(row) for row in conn.execute(f"SELECT * FROM learn_messages WHERE {where} ORDER BY created_at,id LIMIT ?", (*args, limit + 1))]
                for row in rows:
                    row["content_refs"] = [entry["content_ref"] for entry in json.loads(row.pop("citations_json")) if "content_ref" in entry]
                    row.pop("thread_id", None)
            else:
                if kind == "case":
                    source = (self.cases.get(identifier)["messages"] if summary["retention"] == "temporary"
                        else json.loads(conn.execute("SELECT messages_json FROM case_sessions WHERE id=?", (identifier,)).fetchone()[0]))
                else:
                    source = metadata["messages"]
                rows = sorted(deepcopy(source), key=lambda row: (row["created_at"], row["id"]))
                boundary = page.get("boundary") or ([rows[-1]["created_at"], rows[-1]["id"]] if rows else ["", ""])
                rows = [row for row in rows if [row["created_at"], row["id"]] <= boundary and (not after or [row["created_at"], row["id"]] > after)][:limit + 1]
                for row in rows:
                    row.setdefault("run_id", row["id"])
                    row.setdefault("content_refs", [])
            next_cursor = self._cursor({"scope": scope, "boundary": boundary, "after": [rows[limit - 1]["created_at"], rows[limit - 1]["id"]]}) if len(rows) > limit else None
            return {"conversation": summary["identity"], "items": rows[:limit], "next_cursor": next_cursor}

    def list(self, limit=50, cursor=None, lifecycle="active", project_id=None):
        if not 1 <= limit <= 100:
            raise ApiError("invalid_page", "Use a page size between 1 and 100", 422)
        with self._lock, self.cases._lock, self.db.transaction() as conn:
            require_assistance(conn)
            scope = ["conversations", lifecycle, project_id]
            page = self._uncursor(cursor, scope) if cursor else {}
            after = page.get("after")
            parts = []
            for kind, (table, sidecar, column, target_type) in OWNERS.items():
                parts.append(f"SELECT c.id,c.title,c.created_at,max(c.updated_at,s.updated_at) updated_at,"
                    f"s.lifecycle,s.revision,'{kind}' kind,'{target_type}' target_type,p.project_id FROM {table} c "
                    f"JOIN {sidecar} s ON s.{column}=c.id LEFT JOIN study_project_chats p "
                    f"ON p.chat_kind='{kind}' AND p.chat_id=c.id WHERE NOT EXISTS (SELECT 1 FROM deletion_ledger d "
                    f"WHERE d.entity_type='{target_type}' AND d.entity_id=c.id)")
            boundary = page.get("boundary") or utc_now()
            where, args = "lifecycle=? AND updated_at<=?", [lifecycle, boundary]
            if project_id:
                where += " AND project_id=?"
                args.append(project_id)
            if after:
                where += " AND (updated_at,kind,id)<(?,?,?)"
                args += after
            candidates = []
            for row in conn.execute("SELECT * FROM (" + " UNION ALL ".join(parts) + ") WHERE " + where +
                    " ORDER BY updated_at DESC,kind DESC,id DESC LIMIT ?", (*args, limit + 1)):
                value = dict(row)
                value["identity"] = {"type": value.pop("target_type"), "id": value.pop("id")}
                value["retention"] = "saved"
                candidates.append(value)
            if len(candidates) > limit:
                last = candidates[limit - 1]
                next_cursor = self._cursor({"scope": scope, "boundary": boundary, "after": [last["updated_at"], last["kind"], last["identity"]["id"]]})
            else:
                next_cursor = None
            return {"items": candidates[:limit], "next_cursor": next_cursor}

    def _volatile_command(self, key, operation, kind, identifier, request, action):
        if key is None:
            return action()
        digest = canonical_digest({"operation": operation, "target_type": self._owner(kind)[3],
            "target_id": identifier, "request": request.model_dump(mode="json")})
        previous = self._temporary_commands.get(key)
        if previous:
            if previous[0] != digest:
                raise ApiError("idempotency_conflict", "This request key was already used", 409)
            return deepcopy(previous[1])
        result = action()
        self._temporary_commands[key] = (digest, deepcopy(result))
        return result

    def change(self, kind, identifier, request, operation, idempotency_key=None):
        with self._lock, self.cases._lock, self.db.transaction() as conn:
            require_assistance(conn)
            self._owner(kind)
            temporary = self._temporary.get((kind, identifier))
            def change():
                summary, metadata = self._get(conn, kind, identifier)
                self._expected(summary, request.expected_revision)
                if summary["retention"] == "temporary":
                    if operation != "rename":
                        raise ApiError("temporary_archive_unavailable", "Save this conversation before archiving it", 409)
                    metadata["summary"]["title"] = request.title
                    metadata["summary"]["revision"] += 1
                    metadata["summary"]["updated_at"] = utc_now()
                    if kind == "case":
                        self.cases._sessions[identifier].title = request.title
                    return deepcopy(metadata["summary"])
                table, sidecar, column, _ = self._owner(kind)
                if operation == "rename":
                    if kind == "case":
                        from renulus.cases.models import EditCase
                        state = self.cases.get(identifier)
                        updated = self.cases.edit(identifier, EditCase(revision=state["revision"], title=request.title))
                        self.cases.save(identifier, updated["revision"], conn=conn)
                    else:
                        conn.execute(f"UPDATE {table} SET title=?,updated_at=? WHERE id=?", (request.title, utc_now(), identifier))
                else:
                    conn.execute(f"UPDATE {sidecar} SET lifecycle=? WHERE {column}=?",
                                 ("archived" if operation == "archive" else "active", identifier))
                conn.execute(f"UPDATE {sidecar} SET revision=revision+1,updated_at=? WHERE {column}=?", (utc_now(), identifier))
                bump_context_epoch(conn)
                return self._saved(conn, kind, identifier)[0]
            if temporary:
                return self._volatile_command(idempotency_key, operation, kind, identifier, request, change)
            return command(conn, "conversation_commands", idempotency_key, operation, self._owner(kind)[3], identifier, request, change)

    async def delete(self, kind, identifier, request: Mutation, idempotency_key=None):
        self._owner(kind)
        # Stop local runs before deleting their canonical authority. No provider
        # is called in a SQLite transaction or while a synchronous lock is held.
        if kind == "learning":
            for run in list(self.learn.active.values()):
                if run.thread_id == identifier:
                    await self.learn.cancel(run.id)
        with self._lock, self.cases._lock, self.db.transaction() as conn:
            require_assistance(conn)
            temporary = self._temporary.get((kind, identifier))
            def remove():
                summary, _ = self._get(conn, kind, identifier)
                self._expected(summary, request.expected_revision)
                if temporary:
                    if kind == "case":
                        state = self.cases.get(identifier)
                        self.cases.close(identifier, state["revision"])
                    self._temporary.pop((kind, identifier))
                    return {"identity": summary["identity"], "deleted": True}
                table, _, _, target_type = self._owner(kind)
                self.owner_removed(conn, kind, identifier)
                if kind == "case":
                    session = self.cases._sessions.pop(identifier, None)
                    if session:
                        self.cases._invalidate_runs(session)
                        self.cases._changed_scope(session)
                    self.cases._deleted.add(identifier)
                conn.execute(f"DELETE FROM {table} WHERE id=?", (identifier,))
                self.db.mark_deleted(target_type, identifier, conn)
                bump_context_epoch(conn)
                return {"identity": summary["identity"], "deleted": True}
            if temporary:
                return self._volatile_command(idempotency_key, "delete", kind, identifier, request, remove)
            return command(conn, "conversation_commands", idempotency_key, "delete", self._owner(kind)[3], identifier, request, remove)

    def owner_removed(self, conn, kind, identifier):
        for row in conn.execute("SELECT id FROM study_project_chats WHERE chat_kind=? AND chat_id=?", (kind, identifier)):
            self.db.mark_deleted("project_chat", row["id"], conn)
        conn.execute("DELETE FROM study_project_chats WHERE chat_kind=? AND chat_id=?", (kind, identifier))
