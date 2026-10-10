# SPDX-License-Identifier: MIT
"""Bounded canonical search. No temporary state, derived cache or model work."""
import base64
import hashlib
import json

from renulus.contracts import ApiError
from .assessment_policy import require_assistance
from .invalidation import context_epoch_in


def snippet(text, query):
    text = " ".join(str(text).split())
    at = text.casefold().find(query.casefold())
    start = max(0, at - 80)
    return ("…" if start else "") + text[start:start + 280] + ("…" if len(text) > start + 280 else "")


def location(raw):
    """Reuse the canonical Knowledge physical page or stable text item pin."""
    try:
        values = json.loads(raw)
        for value in values:
            if isinstance(value.get("page"), int) and value["page"] > 0:
                return {"kind": "pdf", "physical_page": value["page"]}
            span = value.get("char_span")
            if value.get("item_ref") and isinstance(span, list) and len(span) == 2 and all(isinstance(x, int) for x in span) and 0 <= span[0] <= span[1]:
                return {"kind": "text", "item_ref": value["item_ref"], "start": span[0], "end": span[1]}
    except (ValueError, AttributeError, TypeError):
        pass
    return None


class LocalSearch:
    def __init__(self, services):
        self.db = services.db

    def find(self, query, *, project_id=None, archived=False, limit=30, cursor=None):
        query = query.strip()
        if not query:
            return {"items": [], "next_cursor": None}
        request = hashlib.sha256(json.dumps([query, project_id, archived], ensure_ascii=False).encode()).hexdigest()
        with self.db.transaction() as conn:
            require_assistance(conn)
            epoch = context_epoch_in(conn)
            after = ""
            if cursor:
                try:
                    value = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
                    if not isinstance(value, list) or len(value) != 3 or value[0] != request or value[1] != epoch or not isinstance(value[2], str) or len(value[2]) > 400:
                        raise ValueError()
                    after = value[2]
                except (ValueError, TypeError, UnicodeError):
                    raise ApiError("search_cursor_changed", "Search changed. Start again to see current results", 409, True) from None
            if project_id and not conn.execute("SELECT 1 FROM study_projects WHERE id=? AND lifecycle='active'", (project_id,)).fetchone():
                raise ApiError("search_project_unavailable", "This project is no longer available", 404)
            results = []
            for kind, table, sidecar, owner, identity in (
                    ("learning", "learn_threads", "learn_conversations", "thread_id", "learn_thread"),
                    ("case", "case_sessions", "case_conversations", "case_id", "case")):
                content = "(SELECT m.content FROM learn_messages m WHERE m.thread_id=t.id AND instr(lower(m.content),lower(?))>0 ORDER BY m.created_at,m.id LIMIT 1)" if kind == "learning" else "COALESCE((SELECT json_extract(m.value,'$.content') FROM json_each(t.messages_json) m WHERE instr(lower(json_extract(m.value,'$.content')),lower(?))>0 LIMIT 1),t.case_text)"
                rows = conn.execute(f"SELECT t.id,t.title,COALESCE(c.lifecycle,'active') lifecycle,p.project_id,{content} matched "
                    f"FROM {table} t LEFT JOIN {sidecar} c ON c.{owner}=t.id "
                    "LEFT JOIN study_project_chats p ON p.chat_id=t.id AND p.chat_kind=? "
                    "WHERE COALESCE(c.lifecycle,'active') IN ('active','archived') AND (? OR COALESCE(c.lifecycle,'active')='active') AND (? IS NULL OR p.project_id=?) "
                    "AND ('chat:'||?||':'||t.id)>? AND (instr(lower(t.title),lower(?))>0 OR instr(lower(COALESCE(matched,'')),lower(?))>0) ORDER BY t.id LIMIT ?",
                    (query, kind, archived, project_id, project_id, kind, after, query, query, limit + 1))
                for row in rows:
                    text = row["matched"] or ""
                    if query.casefold() not in row["title"].casefold() and query.casefold() not in text.casefold():
                        continue
                    results.append({"key": "chat:" + kind + ":" + row["id"], "group": "chats", "title": row["title"],
                        "snippet": snippet(text, query), "lifecycle": row["lifecycle"], "project_id": row["project_id"],
                        "identity": {"type": identity, "id": row["id"]}})
                    if len([x for x in results if x["key"].startswith("chat:" + kind + ":")]) > limit:
                        break
            rows = conn.execute("SELECT id,title,lifecycle FROM study_projects WHERE instr(lower(title),lower(?))>0 "
                "AND lifecycle IN ('active','archived') AND (? OR lifecycle='active') AND (? IS NULL OR id=?) AND ('project:'||id)>? ORDER BY id LIMIT ?",
                (query, archived, project_id, project_id, after, limit + 1))
            results.extend({"key": "project:" + row["id"], "group": "projects", "title": row["title"],
                "snippet": "", "lifecycle": row["lifecycle"], "project_id": row["id"]} for row in rows)
            revision = "COALESCE(d.active_revision,d.latest_revision)" if project_id is None else "links.revision_id"
            link = "" if project_id is None else " JOIN study_project_documents links ON links.revision_id=r.id AND links.project_id=?"
            params = [project_id] if project_id else []
            rows = conn.execute("SELECT r.id,d.title,r.status,r.rights_json,r.metadata_json," 
                "(SELECT p.text FROM knowledge_passages p WHERE p.revision_id=r.id AND instr(lower(p.text),lower(?))>0 ORDER BY p.ordinal LIMIT 1) matched," 
                "(SELECT p.locators_json FROM knowledge_passages p WHERE p.revision_id=r.id AND instr(lower(p.text),lower(?))>0 ORDER BY p.ordinal LIMIT 1) locators "
                "FROM knowledge_documents d JOIN knowledge_revisions r ON r.document_id=d.id" + link +
                " WHERE d.deleted_at IS NULL AND d.reserved=0 AND d.scope_kind='personal-library' AND r.id=" + revision +
                " AND ('file:'||r.id)>? ORDER BY r.id", (query, query, *params, after))
            files = 0
            for row in rows:
                try:
                    rights, metadata = json.loads(row["rights_json"]), json.loads(row["metadata_json"])
                    if rights.get("display") is not True:
                        continue
                    text = row["matched"] if row["status"] == "ready" and rights.get("index") is True else ""
                    if query.casefold() not in row["title"].casefold() and query.casefold() not in (text or "").casefold():
                        continue
                    note = "study-note" in metadata.get("asset_role", [])
                except (ValueError, AttributeError, TypeError):
                    continue
                reference = {"target": {"type": "note_revision" if note else "library_revision", "id": row["id"]}}
                if text and row["locators"]:
                    reference["locator"] = location(row["locators"])
                results.append({"key": "file:" + row["id"], "group": "notes" if note else "files", "title": row["title"],
                    "snippet": snippet(text or "", query), "status": row["status"], "reference": reference})
                files += 1
                if files > limit:
                    break
            results.sort(key=lambda x: x["key"])
            page = results[:limit]
            token = base64.urlsafe_b64encode(json.dumps([request, epoch, page[-1]["key"]]).encode()).decode().rstrip("=") if len(results) > limit else None
            return {"items": page, "next_cursor": token, "context_epoch": epoch}
