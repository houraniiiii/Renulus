# SPDX-License-Identifier: MIT
"""Public migration ports: synthetic source/native, real SQLite transactions.

This is coordination proof, not real SDK transfer, canonical owner assembly,
lineage validation or H06 acceptance. The fixture journal is metadata-only.
"""
from contextlib import closing
from dataclasses import asdict, replace
import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from renulus.contracts import ApiError
from renulus.design_c_contracts import Conversation
from renulus.harness_contracts import PairedStoreManifest, SavedConversationMapping
from renulus.learn.harness_migration import (HarnessSavedMigration, LegacyMessage,
    MessageReference, MigrationPins, MigrationRecord, NativeReadback, SavedHistory)
from renulus.storage.database import Database


def history():
    manifest = json.loads((Path(__file__).resolve().parents[2] /
        "packages/contracts/fixtures/harness/paired-store-prepared.json").read_text())
    manifest["state"] = "active"
    manifest["domain_store"]["validation"] = manifest["runtime_store"]["validation"] = "valid"
    conversation = Conversation.model_validate({
        "identity": {"type": "learn_thread", "id": "thread_transplant"},
        "kind": "learning", "retention": "saved", "lifecycle": "archived",
        "revision": 7, "title": "Transplant rejection", "project_id": "project_nephrology",
        "created_at": "2026-10-01T12:00:00+00:00",
        "updated_at": "2026-10-10T12:00:00+00:00"})
    citation = ('[{"passage_id":"passage_7","document_id":"pdf_1","revision_id":"rev_2",'
        '"locators":[{"kind":"pdf","physical_page":7,"printed_label":"5"}]}]')
    return SavedHistory(conversation, PairedStoreManifest.model_validate(manifest),
        MigrationPins(7, 3, "project_nephrology", 2, 5, 11, "frontier_4"), (
            LegacyMessage("legacy_user", "old_run", "user", "Discuss transplant rejection.",
                "2026-10-10T12:00:00+00:00"),
            LegacyMessage("legacy_answer", "old_run", "assistant",
                "Synthetic antibody-mediated rejection explanation. α",
                "2026-10-10T12:00:01+00:00", "2026-10-10T12:00:02+00:00", citation, "completed")))


class CanonicalFixture:
    """Injected canonical/journal adapter; no production migrations are applied."""
    def __init__(self, path):
        self.db = Database(path)
        self.current = history()
        self.fail_activation = False
        with self.db.transaction() as conn:
            conn.execute("CREATE TABLE fixture_journal (thread_id TEXT UNIQUE, "
                         "migration_id TEXT PRIMARY KEY, metadata TEXT NOT NULL)")
            conn.execute("CREATE TABLE fixture_mapping (thread_id TEXT PRIMARY KEY, "
                         "mapping TEXT NOT NULL)")

    def snapshot_in(self, conn, thread_id, *, expected_revision):
        assert conn.in_transaction
        if thread_id != self.current.conversation.identity.id:
            raise ApiError("conversation_unavailable", "Saved owner unavailable.", 404)
        if expected_revision != self.current.conversation.revision:
            raise ApiError("conversation_revision_conflict", "Saved owner changed.", 409)
        return self.current

    def check_current_in(self, conn, snapshot):
        assert conn.in_transaction
        if snapshot != self.current:
            raise ApiError("migration_authority_changed", "Frozen saved authority changed.", 409)

    def find_in(self, conn, *, thread_id=None, migration_id=None):
        assert conn.in_transaction
        key, value = ("thread_id", thread_id) if thread_id is not None else ("migration_id", migration_id)
        row = conn.execute(f"SELECT metadata FROM fixture_journal WHERE {key}=?", (value,)).fetchone()
        if row is None:
            return None
        value = json.loads(row["metadata"])
        value["pins"] = MigrationPins(**value["pins"])
        value["message_refs"] = tuple(MessageReference(**item) for item in value["message_refs"])
        return MigrationRecord(**value)

    def reserve_in(self, conn, record):
        assert conn.in_transaction
        conn.execute("INSERT INTO fixture_journal VALUES(?,?,?)",
            (record.thread_id, record.migration_id, json.dumps(asdict(record))))

    def start_in(self, conn, record):
        current = self.find_in(conn, migration_id=record.migration_id)
        if current != record or current.state != "reserved":
            return False
        conn.execute("UPDATE fixture_journal SET metadata=? WHERE migration_id=?",
            (json.dumps(asdict(replace(record, state="transferring"))), record.migration_id))
        return True

    def activate_in(self, conn, record, *, mapping, readback_digest):
        assert conn.in_transaction
        assert self.find_in(conn, migration_id=record.migration_id) == record
        conn.execute("INSERT INTO fixture_mapping VALUES(?,?)",
            (record.thread_id, mapping.model_dump_json()))
        if self.fail_activation:
            raise ApiError("synthetic_commit_failure", "Injected failure before canonical commit.", 503)
        conn.execute("UPDATE fixture_journal SET metadata=? WHERE migration_id=?",
            (json.dumps(asdict(replace(record, state="active", readback_digest=readback_digest))),
             record.migration_id))

    def mapping(self):
        with closing(self.db.connect()) as conn:
            row = conn.execute("SELECT mapping FROM fixture_mapping").fetchone()
        return SavedConversationMapping.model_validate_json(row["mapping"]) if row else None

    def migration(self):
        with self.db.transaction() as conn:
            return self.find_in(conn, thread_id=self.current.conversation.identity.id)

    def legacy_read(self):
        return self.current.messages

    def append_legacy(self, message):
        with self.db.transaction() as conn:
            if self.find_in(conn, thread_id=self.current.conversation.identity.id):
                raise ApiError("harness_owned_thread", "Reserved native ownership blocks legacy writes.", 409)
            self.current = replace(self.current, messages=(*self.current.messages, message))


class TransferFixture:
    """Public transfer protocol fake; not an SDK loop or model simulation."""
    def __init__(self, canonical):
        self.canonical = canonical
        self.sessions = {}
        self.stages = {}
        self.documents = {}
        self.imports = []
        self.before_readback = None
        self.import_error = None
        self.import_started = asyncio.Event()
        self.hold_import = None
        self.hold_retirement = False

    async def inspect(self, request):
        # A native await must be possible with no canonical writer/lock held.
        with self.canonical.db.quiesce_writes():
            pass
        result = self.sessions.get(request.session_id)
        if result is not None and self.documents[request.session_id] != self.stages[request.session_id]:
            raise ApiError("harness_migration_readback", "Native export differs from staged bytes.", 409)
        if result is not None and self.before_readback is not None:
            self.before_readback()
        return result

    async def stage(self, request, *, document):
        with self.canonical.db.quiesce_writes():
            pass
        assert hashlib.sha256(document).hexdigest() == request.bundle_digest
        self.stages[request.session_id] = document

    async def commit(self, request):
        with self.canonical.db.quiesce_writes():
            pass
        assert self.canonical.mapping() is None
        with pytest.raises(ApiError, match="Reserved native ownership"):
            self.canonical.append_legacy(self.canonical.legacy_read()[0])
        self.imports.append(request)
        self.import_started.set()
        if self.hold_import is not None:
            await self.hold_import.wait()
        document = self.stages[request.session_id]
        messages = json.loads(document)["messages"]
        # This fake implements the declared alias formula; real SDK projection
        # verification is the native adapter's separate acceptance obligation.
        def alias(identifier):
            value = json.dumps(["renulus-h06-message-v1", request.session_id, identifier],
                ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            return "msg_" + hashlib.sha256(value).hexdigest()
        ids = tuple(alias(message["id"]) for message in messages)
        users = sum(message["role"] == "user" for message in messages)
        self.documents[request.session_id] = document
        self.sessions[request.session_id] = NativeReadback(request, ids,
            len(messages), users, len(messages) - users, "settled")
        if self.import_error is not None:
            raise self.import_error

    async def retire(self, request):
        with self.canonical.db.quiesce_writes():
            pass
        if self.hold_retirement:
            return "pending"
        self.stages.pop(request.session_id, None)
        return "retired"


def migration(canonical, transfer):
    return HarnessSavedMigration(canonical.db, snapshot_in=canonical.snapshot_in,
        check_current_in=canonical.check_current_in, journal=canonical, transfer=transfer)


@pytest.mark.asyncio
async def test_saved_history_maps_once_after_exact_readback_without_generation(tmp_path):
    canonical = CanonicalFixture(tmp_path / "synthetic.sqlite")
    transfer = TransferFixture(canonical)
    original = canonical.legacy_read()
    result = await migration(canonical, transfer).migrate_saved("thread_transplant", expected_revision=7)
    assert result.state == "active"
    assert result.mapping == canonical.mapping()
    assert result.mapping.conversation == canonical.current.conversation.identity
    assert result.mapping.runtime.session_id == "ses_df42e887db5046b616c5549b39e8bfa4cd0f90d56207a954c0efdea20735c5ca"
    assert result.message_refs[0].native_id == "msg_e525e63dc3c1899803a0231fdbb4ee2530033f6c24a419b33458921078e66da9"
    retained = json.loads(transfer.documents[result.mapping.runtime.session_id])["messages"]
    assert [(item["id"], item["role"], item["content"], item["citations"])
            for item in retained] == [(item.message_id, item.role, item.text, json.loads(item.citations_json))
                                     for item in original]
    assert all(item.native_id.startswith("msg_") and item.lineage == "unknown" and
               not item.context_eligible and not item.capture_eligible for item in result.message_refs)
    assert canonical.legacy_read() == original
    again = await migration(canonical, transfer).migrate_saved("thread_transplant", expected_revision=7)
    assert again == result
    assert len(transfer.imports) == 1
    metadata = json.dumps(asdict(canonical.migration()))
    assert original[0].text not in metadata and original[1].text not in metadata
    assert "physical_page" not in metadata


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["completed", "cancelled", "failed", "interrupted"])
async def test_terminal_legacy_outcomes_preserve_exact_partial_history_as_unknown(tmp_path, outcome):
    canonical = CanonicalFixture(tmp_path / "synthetic.sqlite")
    user, assistant = canonical.current.messages
    canonical.current = replace(canonical.current, messages=(
        replace(user, run_outcome=outcome),
        replace(assistant, text="Exact retained partial explanation. α\n", run_outcome=outcome)))
    original = canonical.legacy_read()
    transfer = TransferFixture(canonical)

    result = await migration(canonical, transfer).migrate_saved("thread_transplant", expected_revision=7)

    assert result.state == "active" and result.mapping == canonical.mapping()
    retained = json.loads(transfer.documents[result.mapping.runtime.session_id])["messages"]
    assert retained == [
        {"id": "legacy_user", "role": "user", "content": "Discuss transplant rejection.",
         "runId": "old_run", "createdAt": "2026-10-10T12:00:00+00:00", "citations": []},
        {"id": "legacy_answer", "role": "assistant", "content": "Exact retained partial explanation. α\n",
         "runId": "old_run", "createdAt": "2026-10-10T12:00:01+00:00",
         "completedAt": "2026-10-10T12:00:02+00:00", "legacyOutcome": outcome,
         "citations": [{"passage_id": "passage_7", "document_id": "pdf_1", "revision_id": "rev_2",
                        "locators": [{"kind": "pdf", "physical_page": 7, "printed_label": "5"}]}]}]
    assert canonical.legacy_read() == original
    assert all(reference.lineage == "unknown" and not reference.context_eligible and
               not reference.capture_eligible for reference in result.message_refs)


@pytest.mark.asyncio
async def test_commit_then_retire_stage_payload_without_repeating_transfer(tmp_path):
    canonical = CanonicalFixture(tmp_path / "synthetic.sqlite")
    transfer = TransferFixture(canonical)
    transfer.hold_retirement = True
    first = await migration(canonical, transfer).migrate_saved("thread_transplant", expected_revision=7)
    assert first.state == "active" and first.retirement == "pending"
    assert canonical.mapping() == first.mapping and transfer.stages
    transfer.hold_retirement = False
    result = await migration(canonical, transfer).reconcile_migration(first.migration_id)
    assert result.state == "active" and result.retirement == "retired"
    assert transfer.stages == {} and len(transfer.imports) == 1
    assert canonical.mapping() == result.mapping


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["completed", "cancelled", "failed", "interrupted"])
async def test_unsettled_legacy_assistant_is_not_silently_dropped_by_transfer(tmp_path, outcome):
    canonical = CanonicalFixture(tmp_path / "synthetic.sqlite")
    canonical.current = replace(canonical.current, messages=(canonical.current.messages[0],
        replace(canonical.current.messages[1], completed_at=None, run_outcome=outcome)))
    transfer = TransferFixture(canonical)
    with pytest.raises(ApiError) as refusal:
        await migration(canonical, transfer).migrate_saved("thread_transplant", expected_revision=7)
    assert refusal.value.code == "harness_migration_source"
    assert canonical.migration() is None and canonical.mapping() is None
    assert transfer.imports == []


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", [None, "running", "unknown"])
async def test_unknown_or_nonterminal_legacy_outcome_refuses_before_native_stage(tmp_path, outcome):
    canonical = CanonicalFixture(tmp_path / "synthetic.sqlite")
    canonical.current = replace(canonical.current, messages=(canonical.current.messages[0],
        replace(canonical.current.messages[1], run_outcome=outcome)))
    transfer = TransferFixture(canonical)
    with pytest.raises(ApiError) as refusal:
        await migration(canonical, transfer).migrate_saved("thread_transplant", expected_revision=7)
    assert refusal.value.code == "harness_migration_outcome_unsupported"
    assert transfer.stages == {} and transfer.imports == []
    assert canonical.migration() is None and canonical.mapping() is None


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["completed", "cancelled", "failed", "interrupted"])
async def test_lost_import_ack_restarts_with_inspection_and_original_identities(tmp_path, outcome):
    canonical = CanonicalFixture(tmp_path / "synthetic.sqlite")
    canonical.current = replace(canonical.current, messages=(canonical.current.messages[0],
        replace(canonical.current.messages[1], run_outcome=outcome)))
    transfer = TransferFixture(canonical)
    transfer.import_error = TimeoutError("Synthetic acknowledgement lost after native commit.")
    with pytest.raises(TimeoutError):
        await migration(canonical, transfer).migrate_saved("thread_transplant", expected_revision=7)
    reserved = canonical.migration()
    assert reserved.state == "transferring" and canonical.mapping() is None
    transfer.stages.clear()  # Replacement native process must restage before inspection.
    result = await migration(canonical, transfer).reconcile_migration(reserved.migration_id)
    assert result.state == "active"
    assert result.mapping.runtime.session_id == transfer.imports[0].session_id == reserved.session_id
    assert result.message_refs == reserved.message_refs
    assert result.source_digest == reserved.source_digest
    assert len(transfer.imports) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("defect", ["duplicate_id", "message_budget", "byte_budget", "timestamp", "role"])
async def test_invalid_or_over_budget_source_refuses_before_native_stage(tmp_path, defect):
    canonical = CanonicalFixture(tmp_path / "synthetic.sqlite")
    messages = canonical.current.messages
    if defect == "duplicate_id":
        messages = (messages[0], replace(messages[1], message_id=messages[0].message_id))
    elif defect == "message_budget":
        messages = tuple(replace(messages[0], message_id="legacy_" + str(index)) for index in range(4097))
    elif defect == "byte_budget":
        messages = (replace(messages[0], text="x" * (8 * 1024 * 1024)), messages[1])
    elif defect == "timestamp":
        messages = (messages[0], replace(messages[1], completed_at="unresolved"))
    elif defect == "role":
        messages = (replace(messages[0], role="tool"), messages[1])
    canonical.current = replace(canonical.current, messages=messages)
    transfer = TransferFixture(canonical)
    with pytest.raises(ApiError) as refusal:
        await migration(canonical, transfer).migrate_saved("thread_transplant", expected_revision=7)
    assert refusal.value.code == ("harness_migration_budget" if defect.endswith("budget") else "harness_migration_source")
    assert transfer.stages == {} and transfer.imports == []
    assert canonical.migration() is None and canonical.mapping() is None


@pytest.mark.asyncio
async def test_uncertain_absence_does_not_authorize_second_import(tmp_path):
    canonical = CanonicalFixture(tmp_path / "synthetic.sqlite")
    transfer = TransferFixture(canonical)
    transfer.import_error = TimeoutError("Synthetic acknowledgement lost.")
    with pytest.raises(TimeoutError):
        await migration(canonical, transfer).migrate_saved("thread_transplant", expected_revision=7)
    reserved = canonical.migration()
    transfer.sessions.clear()  # Absence observation cannot prove the original effect settled.
    result = await migration(canonical, transfer).reconcile_migration(reserved.migration_id)
    repeat = await migration(canonical, transfer).migrate_saved("thread_transplant", expected_revision=7)
    assert result == repeat and result.state == "pending"
    assert canonical.mapping() is None and canonical.migration() == reserved
    assert len(transfer.imports) == 1
    with pytest.raises(ApiError) as blocked:
        canonical.append_legacy(canonical.legacy_read()[0])
    assert blocked.value.code == "harness_owned_thread"


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [
    ("owner_revision", 8), ("draft_revision", 4),
    ("project_id", "project_changed"), ("project_revision", 3),
    ("policy_revision", 6), ("context_epoch", 12), ("deletion_frontier", "frontier_5"),
])
async def test_late_authority_change_keeps_native_stage_nonadmitted(tmp_path, field, value):
    canonical = CanonicalFixture(tmp_path / "synthetic.sqlite")
    transfer = TransferFixture(canonical)
    def change():
        canonical.current = replace(canonical.current, pins=replace(canonical.current.pins, **{field: value}))
    transfer.before_readback = change
    with pytest.raises(ApiError) as refusal:
        await migration(canonical, transfer).migrate_saved("thread_transplant", expected_revision=7)
    assert refusal.value.code == "harness_migration_conflict"
    assert canonical.mapping() is None
    assert canonical.migration().state == "transferring"
    assert len(transfer.imports) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("defect", ["text", "citation", "outcome", "missing", "order", "extra", "counts", "identity"])
async def test_readback_must_prove_exact_bytes_references_and_order(tmp_path, defect):
    canonical = CanonicalFixture(tmp_path / "synthetic.sqlite")
    transfer = TransferFixture(canonical)
    def corrupt():
        request = transfer.imports[0]
        observed = transfer.sessions[request.session_id]
        ids = observed.native_message_ids
        if defect in {"text", "citation", "outcome"}:
            document = json.loads(transfer.documents[request.session_id])
            field, value = {"text": ("content", "Wrong retained explanation."),
                            "citation": ("citations", []), "outcome": ("legacyOutcome", "failed")}[defect]
            document["messages"][1][field] = value
            transfer.documents[request.session_id] = json.dumps(document).encode("utf-8")
        elif defect == "missing":
            ids = ids[:1]
        elif defect == "order":
            ids = tuple(reversed(ids))
        elif defect == "extra":
            ids = (*ids, ids[-1])
        elif defect == "counts":
            observed = replace(observed, assistant_count=False)
        elif defect == "identity":
            request = replace(request, migration_id="different_migration")
        transfer.sessions[observed.request.session_id] = replace(observed, request=request, native_message_ids=ids)
    # Alter the exported projection before it reaches the public inspect caller.
    original_inspect = transfer.inspect
    async def inspect(request):
        if request.session_id in transfer.sessions:
            corrupt()
        return await original_inspect(request)
    transfer.inspect = inspect
    with pytest.raises(ApiError) as refusal:
        await migration(canonical, transfer).migrate_saved("thread_transplant", expected_revision=7)
    assert refusal.value.code == "harness_migration_readback"
    assert canonical.mapping() is None and canonical.migration().state == "transferring"


@pytest.mark.asyncio
async def test_competing_public_call_retains_original_inflight_import(tmp_path):
    canonical = CanonicalFixture(tmp_path / "synthetic.sqlite")
    transfer = TransferFixture(canonical)
    transfer.hold_import = asyncio.Event()
    first = asyncio.create_task(migration(canonical, transfer).migrate_saved("thread_transplant", expected_revision=7))
    await asyncio.wait_for(transfer.import_started.wait(), 1)
    try:
        second = await migration(canonical, transfer).migrate_saved("thread_transplant", expected_revision=7)
        assert second.state == "pending" and canonical.mapping() is None
        assert len(transfer.imports) == 1
    finally:
        transfer.hold_import.set()
        result = await first
    assert result.state == "active" and result.migration_id == second.migration_id


@pytest.mark.asyncio
async def test_mapping_and_readback_receipt_rollback_together_then_reconcile(tmp_path):
    canonical = CanonicalFixture(tmp_path / "synthetic.sqlite")
    transfer = TransferFixture(canonical)
    canonical.fail_activation = True
    with pytest.raises(ApiError) as error:
        await migration(canonical, transfer).migrate_saved("thread_transplant", expected_revision=7)
    assert error.value.code == "synthetic_commit_failure"
    record = canonical.migration()
    assert canonical.mapping() is None and record.state == "transferring"
    assert record.readback_digest is None
    canonical.fail_activation = False
    result = await migration(canonical, transfer).reconcile_migration(record.migration_id)
    assert result.state == "active" and canonical.mapping() == result.mapping
    assert canonical.migration().readback_digest is not None
    assert len(transfer.imports) == 1


@pytest.mark.asyncio
async def test_active_journal_without_readback_receipt_cannot_grant_mapping(tmp_path):
    canonical = CanonicalFixture(tmp_path / "synthetic.sqlite")
    transfer = TransferFixture(canonical)
    transfer.import_error = TimeoutError("Withhold native import acknowledgement.")
    with pytest.raises(TimeoutError):
        await migration(canonical, transfer).migrate_saved("thread_transplant", expected_revision=7)
    original_find = canonical.find_in
    def premature_active(conn, **identity):
        record = original_find(conn, **identity)
        return replace(record, state="active", readback_digest=None) if record is not None else None
    # A corrupted/recovery journal must not manufacture canonical admission.
    canonical.find_in = premature_active
    with pytest.raises(ApiError) as refusal:
        await migration(canonical, transfer).reconcile_migration(canonical.migration().migration_id)
    assert refusal.value.code == "harness_migration_conflict"
    assert canonical.mapping() is None
