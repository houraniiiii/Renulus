# SPDX-License-Identifier: MIT
"""Caller-transaction authorization using actual Case persistence and policy.

Knowledge003 saved uploads are tested only after the parent's migration exists.
These checks never fabricate that schema or invoke a provider.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from io import BytesIO
import sqlite3
from threading import Event

import pytest

from renulus.cases.models import StartCase
from renulus.cases.originals import accepted_original
from renulus.design_c_contracts import Identity
from renulus.knowledge.attachment_models import AttachmentUpload
from renulus.knowledge.models import own_text_rights
from renulus.learn.conversation_models import NewConversation
from renulus.server import create_app
from renulus.storage.assessment_policy import advance_policy, policy_snapshot
from renulus.storage.invalidation import context_epoch_in


@pytest.fixture
def services(tmp_path, monkeypatch):
    import socket
    def forbidden(*args, **kwargs):
        raise AssertionError("Attachment authorization cannot contact a provider or network")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    app = create_app(tmp_path / "synthetic-attachment-access")
    try:
        yield app.state.services
    finally:
        app.state.services.get("knowledge").index.close()


def case_original(services, *, saved=False):
    from PIL import Image
    cases = services.get("cases")
    case = cases.start(StartCase(text="SYNTHETIC dialysis education"))
    stream = BytesIO()
    Image.new("RGB", (20, 20), "white").save(stream, format="PNG")
    original = accepted_original("SYNTHETIC.png", "SYNTHETIC study original", "image/png", stream.getvalue())
    case = cases.attach(case["id"], case["revision"], original)
    if saved:
        case = cases.save(case["id"], case["revision"])
    return case, original


def authorize(services, attachment_id, context=None):
    with services.db.transaction() as conn:
        return services.get("knowledge_attachments").authorize_in(conn, attachment_id, context=context)


@contextmanager
def metadata_only(conn, services, monkeypatch):
    """Reject nested connections, transactions, writes and private payload reads."""
    trace = []
    changes = conn.total_changes
    def forbidden(*args, **kwargs):
        raise AssertionError("Authorization opened another database connection")
    def guard(action, table, column, *unused):
        if action in {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE,
                      sqlite3.SQLITE_TRANSACTION, sqlite3.SQLITE_SAVEPOINT}:
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_READ and (table, column) in {
            ("case_attachment_parts", "data"), ("case_sessions", "case_text"),
            ("case_sessions", "messages_json"), ("case_sessions", "teaching_json")}:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    with monkeypatch.context() as patch:
        patch.setattr(services.db, "connect", forbidden)
        conn.set_authorizer(guard)
        conn.set_trace_callback(trace.append)
        try:
            yield
            assert conn.total_changes == changes
            assert not any(sql.split()[0].upper() in {"BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT"}
                           for sql in trace)
        finally:
            conn.set_authorizer(None)
            conn.set_trace_callback(None)


def test_registered_volatile_case_access_uses_matching_owner_without_persistence(services, monkeypatch):
    case, original = case_original(services)
    context = Identity(type="case", id=case["id"])
    with services.db.transaction() as conn:
        assert not conn.execute("SELECT 1 FROM case_sessions WHERE id=?", (case["id"],)).fetchone()
        with metadata_only(conn, services, monkeypatch):
            result = services.get("knowledge_attachments").authorize_in(conn, original["id"], context=context)
        assert result == {"allowed": True}
        assert not conn.execute("SELECT 1 FROM case_attachments WHERE id=?", (original["id"],)).fetchone()
    assert authorize(services, original["id"], Identity(type="case", id="SYNTHETIC_other")) == {
        "allowed": False, "reason": "not_found"}


def test_saved_case_uses_canonical_metadata_and_parts_after_volatile_eviction(services, monkeypatch):
    case, original = case_original(services, saved=True)
    cases = services.get("cases")
    with cases._lock:
        cases._sessions.clear()
    with services.db.transaction() as conn, metadata_only(conn, services, monkeypatch):
        result = services.get("knowledge_attachments").authorize_in(conn, original["id"])
        assert result == {"allowed": True}
    assert not cases._sessions
    assert authorize(services, original["id"], Identity(type="learn_thread", id="SYNTHETIC_other")) == {
        "allowed": False, "reason": "access_denied"}
    assert authorize(services, original["id"], Identity(type="case", id="SYNTHETIC_other")) == {
        "allowed": False, "reason": "access_denied"}


def test_records_only_saved_case_is_unavailable_without_reading_parts(services, monkeypatch):
    case, original = case_original(services, saved=True)
    services.db.execute("DELETE FROM case_attachment_parts WHERE attachment_id=?", (original["id"],))
    with services.db.transaction() as conn, metadata_only(conn, services, monkeypatch):
        result = services.get("knowledge_attachments").authorize_in(conn, original["id"],
            context=Identity(type="case", id=case["id"]))
        assert result == {"allowed": False, "reason": "unavailable"}


def test_pending_and_saved_removal_revoke_original_authority(services):
    case, original = case_original(services, saved=True)
    cases = services.get("cases")
    removed = cases.remove_attachment(case["id"], original["id"], case["revision"])
    context = Identity(type="case", id=case["id"])
    assert authorize(services, original["id"], context) == {"allowed": False, "reason": "not_found"}
    cases.save(case["id"], removed["revision"])
    assert authorize(services, original["id"], context) == {"allowed": False, "reason": "not_found"}


def test_deleted_case_and_stale_saved_owner_are_refused(services):
    case, original = case_original(services, saved=True)
    services.db.execute("UPDATE case_sessions SET revision=revision+1 WHERE id=?", (case["id"],))
    assert authorize(services, original["id"]) == {"allowed": False, "reason": "unavailable"}
    services.db.mark_deleted("case", case["id"])
    assert authorize(services, original["id"]) == {"allowed": False, "reason": "not_found"}


def test_real_shared_test_policy_denies_access_before_metadata_lookup(services, monkeypatch):
    case, original = case_original(services)
    with services.db.transaction() as conn:
        conn.execute("INSERT INTO assessment_test_attempts(id,version_id,version_snapshot_json,mode,status,clock_high_water_at,created_at,updated_at) VALUES(?,?,'{}','test','active',?,?,?)",
            ("SYNTHETIC_attempt", "SYNTHETIC_version", "2026-10-10T00:00:00Z",
             "2026-10-10T00:00:00Z", "2026-10-10T00:00:00Z"))
        advance_policy(conn)
        with metadata_only(conn, services, monkeypatch):
            result = services.get("knowledge_attachments").authorize_in(conn, original["id"],
                context=Identity(type="case", id=case["id"]))
            assert result == {"allowed": False, "reason": "restricted"}


def test_project_is_not_conversation_authority_and_missing_attachment_is_explicit(services):
    case, original = case_original(services, saved=True)
    assert authorize(services, original["id"], Identity(type="project", id="SYNTHETIC_project")) == {
        "allowed": False, "reason": "access_denied"}
    assert authorize(services, "SYNTHETIC_no_attachment") == {"allowed": False, "reason": "not_found"}


def test_absent_core_schema_is_unavailable_inside_isolated_rollback(services):
    # Use the actual migrated profile, deliberately remove a table in this
    # transaction, then roll it back. No substitute schema is created.
    conn = services.db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DROP TABLE knowledge_attachments")
        assert services.get("knowledge_attachments").authorize_in(conn, "SYNTHETIC_no_attachment") == {
            "allowed": False, "reason": "unavailable"}
    finally:
        conn.rollback()
        conn.close()
    assert services.db.fetch_all("PRAGMA table_info(knowledge_attachments)")
    assert authorize(services, "SYNTHETIC_no_attachment") == {"allowed": False, "reason": "not_found"}


def test_missing_attachment_precedes_absent_metadata_inside_isolated_rollback(services):
    conn = services.db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DROP TABLE knowledge_attachment_metadata")
        assert services.get("knowledge_attachments").authorize_in(conn, "SYNTHETIC_no_attachment") == {
            "allowed": False, "reason": "not_found"}
    finally:
        conn.rollback()
        conn.close()
    assert services.db.fetch_all("PRAGMA table_info(knowledge_attachment_metadata)")


def test_contended_case_lock_fails_closed_without_waiting_in_caller_transaction(services):
    case, original = case_original(services)
    held, release = Event(), Event()
    def hold_case_lock():
        with services.get("cases")._lock:
            held.set()
            assert release.wait(5), "Authorization did not complete while Case lock was held"
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(hold_case_lock)
        try:
            assert held.wait(3)
            assert authorize(services, original["id"], Identity(type="case", id=case["id"])) == {
                "allowed": False, "reason": "unavailable"}
        finally:
            release.set()
        future.result(timeout=3)


@pytest.mark.parametrize("kind", ["learning", "case"])
def test_saved_metadata_authority_keeps_all_guards_without_chat_or_case_lock(services, monkeypatch, kind):
    conversations = services.get("conversations")
    chat = conversations.create(NewConversation(kind=kind, title="SYNTHETIC canonical attachment"))
    with services.db.transaction() as conn:
        request = AttachmentUpload(conversation=chat["identity"], expected_conversation_revision=chat["revision"],
            expected_policy_revision=policy_snapshot(conn)["revision"], expected_context_epoch=context_epoch_in(conn),
            idempotency_key="SYNTHETIC_canonical_lock_upload", filename="SYNTHETIC.md",
            title="SYNTHETIC retained source", rights=own_text_rights(), metadata={})
    access = services.get("knowledge_attachments")
    receipt = access.upload(request, b"SYNTHETIC retained source")
    context = Identity.model_validate(chat["identity"])
    held, release = Event(), Event()
    def hold_both_owners():
        with conversations._lock, services.get("cases")._lock:
            held.set()
            assert release.wait(20), "Canonical authorization waited for a volatile owner"
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(hold_both_owners)
        try:
            assert held.wait(5)
            with services.db.transaction() as conn:
                with metadata_only(conn, services, monkeypatch):
                    assert access.authorize_in(conn, receipt["id"], context=context) == {"allowed": True}
                    assert access.authorize_in(conn, receipt["id"], context=context.model_copy(update={
                        "id": "SYNTHETIC_wrong_owner"})) == {"allowed": False, "reason": "access_denied"}
                # In the same caller transaction, each independent canonical
                # revocation must still win while both volatile owners are busy.
                cases = [
                    ("UPDATE knowledge_attachment_metadata SET rights_json=? WHERE attachment_id=?",
                        (own_text_rights().model_copy(update={"display": False}).model_dump_json(), receipt["id"]), "access_denied"),
                    ("DELETE FROM knowledge_attachment_metadata WHERE attachment_id=?", (receipt["id"],), "unavailable"),
                    ("UPDATE knowledge_attachment_originals SET bytes=bytes+1 WHERE attachment_id=?", (receipt["id"],), "unavailable"),
                ]
                for sql, params, reason in cases:
                    conn.execute("SAVEPOINT refusal")
                    try:
                        conn.execute(sql, params)
                        with metadata_only(conn, services, monkeypatch):
                            assert access.authorize_in(conn, receipt["id"], context=context) == {
                                "allowed": False, "reason": reason}
                    finally:
                        conn.execute("ROLLBACK TO refusal")
                        conn.execute("RELEASE refusal")
                for entity_type, identifier in (("attachment", receipt["id"]),
                        ("attachment_original", receipt["original"]["id"]), (context.type, context.id)):
                    conn.execute("SAVEPOINT tombstone")
                    try:
                        services.db.mark_deleted(entity_type, identifier, conn)
                        with metadata_only(conn, services, monkeypatch):
                            assert access.authorize_in(conn, receipt["id"], context=context) == {
                                "allowed": False, "reason": "not_found"}
                    finally:
                        conn.execute("ROLLBACK TO tombstone")
                        conn.execute("RELEASE tombstone")
        finally:
            release.set()
            future.result(timeout=5)
