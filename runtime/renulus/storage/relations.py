# SPDX-License-Identifier: MIT
"""Typed recovery identities and declared parent edges.

An edge removes its child row when a parent is unavailable. A membership row's
identity is its *entire* primary key, so deleting the row never deletes either
independently owned endpoint. Names and bindings are installed application
policy, never inferred from an archive's column suffixes.
"""
from dataclasses import dataclass
import json


@dataclass(frozen=True)
class Binding:
    parent: str
    columns: tuple[str, ...]
    kind: str = "owned"
    discriminator: tuple[str, str] | None = None
    prefix: str = ""


def own(parent, *columns):
    return Binding(parent, columns)


def link(parent, *columns):
    return Binding(parent, columns, "link")


PARENTS = {
    "learn_messages": (own("learn_threads", "thread_id"),),
    "learn_runs": (own("learn_threads", "thread_id"),),
    "learn_harness_mappings": (own("learn_threads", "thread_id"),),
    "learn_harness_answers": (own("learn_runs", "run_id"), own("learn_threads", "thread_id")),
    "learn_conversations": (own("learn_threads", "thread_id"),),
    "case_conversations": (own("case_sessions", "case_id"),),
    "case_attachments": (own("case_sessions", "case_id"),),
    "case_attachment_parts": (own("case_attachments", "attachment_id"),),
    "knowledge_revisions": (own("knowledge_documents", "document_id"),),
    "knowledge_passages": (own("knowledge_revisions", "revision_id"),),
    "knowledge_jobs": (own("knowledge_revisions", "revision_id"),),
    "knowledge_cleanup": (own("knowledge_revisions", "revision_id"),),
    "knowledge_attachments": (
        Binding("learn_threads", ("chat_id",), "owned", ("chat_kind", "learning")),
        Binding("case_sessions", ("chat_id",), "owned", ("chat_kind", "case"))),
    "knowledge_attachment_originals": (own("knowledge_attachments", "attachment_id"),),
    "knowledge_attachment_metadata": (own("knowledge_attachments", "attachment_id"),),
    "knowledge_source_status_events": (own("knowledge_documents", "document_id"),),
    "memory_history": (own("memory_facts", "record_id"),),
    "memory_requests": (own("memory_facts", "record_id"),),
    "memory_sources": (own("memory_facts", "record_id"),
        Binding("learning_evidence", ("source_key",), "link", prefix="evidence:")),
    "memory_jobs": (own("learning_evidence", "evidence_id"),),
    # Answer lineage survives ordinary chat/evidence removal. Explicit
    # delete-related-learning revokes semantic support through MemoryService.
    "memory_answer_lineage": (),
    "memory_support_groups": (own("memory_facts", "record_id"),),
    "memory_support_inputs": (own("memory_support_groups", "group_id"),),
    "assessment_items": (own("assessment_sessions", "session_id"),),
    "assessment_attempts": (own("assessment_sessions", "session_id"), own("assessment_items", "item_id")),
    "assessment_exposure": (own("assessment_items", "item_id"),),
    "assessment_generated_items": (own("assessment_generated_sessions", "session_id"),),
    "assessment_generated_attempts": (own("assessment_generated_sessions", "session_id"),
        own("assessment_generated_items", "item_id")),
    "assessment_test_versions": (own("assessment_tests", "test_id"),),
    # Attempts retain their immutable snapshots/provenance when a collection
    # entry is deleted; a saved test is a reference, not the attempt's owner.
    "assessment_attempt_drafts": (own("assessment_test_attempts", "attempt_id"),),
    "assessment_attempt_exposure": (own("assessment_test_attempts", "attempt_id"),),
    "study_project_goals": (own("study_projects", "project_id"),),
    "study_project_documents": (link("study_projects", "project_id"), link("knowledge_revisions", "revision_id")),
    "study_project_chats": (link("study_projects", "project_id"),
        Binding("learn_threads", ("chat_id",), "link", ("chat_kind", "learning")),
        Binding("case_sessions", ("chat_id",), "link", ("chat_kind", "case"))),
    "learning_evidence": tuple(Binding(parent, ("entity_id",), "owned", ("kind", kind))
        for kind, parent in (("study-interest", "learn_threads"), ("study-answer", "learn_threads"),
            ("assessment-answer", "assessment_attempts"), ("generated-answer", "assessment_generated_attempts"),
            ("assessment-test-answer", "assessment_test_attempts"))),
    "content_pack_topics": (link("content_packs", "pack_id", "pack_version"), link("content_topics", "topic_id", "topic_version")),
    "content_pack_cases": (link("content_packs", "pack_id", "pack_version"), link("content_case_versions", "case_id", "case_version")),
    "content_pack_questions": (link("content_packs", "pack_id", "pack_version"), link("content_question_versions", "question_id", "question_version")),
    "content_active_pack": (link("content_packs", "pack_id", "pack_version"),),
    "content_question_withdrawals": (link("content_question_versions", "question_id", "version"),),
    "content_pack_withdrawals": (link("content_packs", "pack_id", "version"),),
    "update_reviews": (own("update_entries", "entry_id"),),
    "update_review_heads": (link("update_entries", "entry_id"), link("update_reviews", "review_id")),
    "update_source_statuses": (link("update_reviews", "review_id"),),
    "update_affected_versions": (link("update_entries", "entry_id"),),
    "update_library_changes": (own("update_entries", "entry_id"),),
    "update_literature_records": (own("update_entries", "entry_id"),),
    "update_schedule_runs": (own("update_schedule_jobs", "job_id"),),
}

# Existing deletion producers and supported historical aliases. An unknown
# ledger type is preserved but cannot match a different record namespace.
TOMBSTONES = {
    "learn_thread": "learn_threads", "learn_message": "learn_messages", "learn_run": "learn_runs",
    "case": "case_sessions", "case_attachment": "case_attachments",
    "memory_fact": "memory_facts", "learning_evidence": "learning_evidence",
    "knowledge-document": "knowledge_documents", "document": "knowledge_documents",
    "knowledge-revision": "knowledge_revisions", "revision": "knowledge_revisions",
    "assessment_session": "assessment_sessions", "assessment_item": "assessment_items",
    "assessment_attempt": "assessment_attempts",
    "generated_session": "assessment_generated_sessions", "generated_item": "assessment_generated_items",
    "generated_attempt": "assessment_generated_attempts", "project": "study_projects",
    "test": "assessment_tests", "saved_test": "assessment_tests",
    "saved_test_version": "assessment_test_versions", "test_attempt": "assessment_test_attempts",
    "attachment": "knowledge_attachments", "attachment_original": "knowledge_attachment_originals",
    "goal": "study_project_goals", "update_entry": "update_entries",
    "project_chat": "study_project_chats", "project_document": "study_project_documents",
    "test_import": "assessment_test_imports",
}

# Historical pins remain untouched. These optional live pointers are cleared
# when their target is unavailable; their row and independently pinned snapshot
# are preserved. The installed owner must make each listed column nullable.
UNAVAILABLE_REFERENCES = {
    "assessment_test_attempts": (("live_version_id", "assessment_test_versions", "id"),),
    "assessment_question_reports": (("live_version_id", "assessment_test_versions", "id"),
        ("live_attempt_id", "assessment_test_attempts", "id")),
    "assessment_test_jobs": (("live_published_version_id", "assessment_test_versions", "id"),),
    "assessment_test_imports": (("live_source_revision_id", "knowledge_revisions", "id"),
        ("live_published_version_id", "assessment_test_versions", "id")),
    "knowledge_documents": (("active_revision", "knowledge_revisions", "id"),
        ("latest_revision", "knowledge_revisions", "id")),
}


def reconcile_unavailable_references(conn):
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for table, references in UNAVAILABLE_REFERENCES.items():
        if table not in tables:
            continue
        columns = {row["name"] for row in conn.execute(f'PRAGMA table_info("{table}")')}
        for column, target, target_column in references:
            if column in columns and target in tables:
                conn.execute(f'UPDATE "{table}" SET "{column}"=NULL WHERE "{column}" IS NOT NULL AND '
                    f'NOT EXISTS(SELECT 1 FROM "{target}" WHERE "{target}"."{target_column}"="{table}"."{column}")')


def identity(table, values):
    return (table, json.dumps(list(values), ensure_ascii=False, separators=(",", ":")))


def row_identity(table, row, keys):
    return identity(table, (row[key] for key in keys))


def row_parents(table, row):
    for binding in PARENTS.get(table, ()):
        if binding.discriminator and row.get(binding.discriminator[0]) != binding.discriminator[1]:
            continue
        values = [row.get(column) for column in binding.columns]
        if any(value is None for value in values):
            continue
        if binding.prefix:
            if not isinstance(values[0], str) or not values[0].startswith(binding.prefix):
                continue
            values[0] = values[0][len(binding.prefix):]
        yield identity(binding.parent, values)


def tombstone_identity(row):
    table = TOMBSTONES.get(row["entity_type"])
    return identity(table, (row["entity_id"],)) if table else None


def allow_row(table, row, keys, blocked):
    return row_identity(table, row, keys) not in blocked


def original_blocked(revision_id, document_id, blocked):
    return identity("knowledge_revisions", (revision_id,)) in blocked or \
        identity("knowledge_documents", (document_id,)) in blocked
