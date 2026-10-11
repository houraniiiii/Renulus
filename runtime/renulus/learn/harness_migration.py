# SPDX-License-Identifier: MIT
"""Saved-history transfer coordination; canonical adapters own persistence.

The snapshot/current/journal callbacks are local and share the supplied canonical
transaction. The transfer adapter uses supported SDK import/readback without a
prompt, and reports absence only for the specific native not-found outcome.
Legacy bytes remain in the read-only canonical history, never in this journal.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
import hashlib
import json
import sqlite3
from typing import Literal, Protocol

from renulus.contracts import ApiError
from renulus.design_c_contracts import Conversation, ConversationIdentity, canonical_digest
from renulus.harness_contracts import (HarnessEngineReference, PairedStoreManifest,
    SavedConversationMapping, map_saved_conversation)
from renulus.storage.database import Database

MAX_BUNDLE_BYTES = 8 * 1024 * 1024
MAX_MESSAGES = 4096


@dataclass(frozen=True)
class MigrationPins:
    owner_revision: int
    draft_revision: int
    project_id: str | None
    project_revision: int | None
    policy_revision: int
    context_epoch: int
    deletion_frontier: str


@dataclass(frozen=True)
class LegacyMessage:
    message_id: str
    run_id: str | None
    role: Literal["user", "assistant"]
    text: str
    created_at: str
    completed_at: str | None = None
    citations_json: str = "[]"
    run_outcome: Literal["completed", "cancelled", "failed", "interrupted"] | None = None


@dataclass(frozen=True)
class SavedHistory:
    conversation: Conversation
    manifest: PairedStoreManifest
    pins: MigrationPins
    messages: tuple[LegacyMessage, ...]


@dataclass(frozen=True)
class MessageReference:
    legacy_id: str
    native_id: str
    run_id: str | None
    role: Literal["user", "assistant"]
    ordinal: int
    lineage: Literal["unknown"] = "unknown"
    context_eligible: Literal[False] = False
    capture_eligible: Literal[False] = False


@dataclass(frozen=True)
class MigrationRecord:
    migration_id: str
    thread_id: str
    source_revision: int
    manifest_json: str
    pins: MigrationPins
    session_id: str
    source_digest: str
    message_refs: tuple[MessageReference, ...]
    state: Literal["reserved", "transferring", "active"] = "reserved"
    readback_digest: str | None = None


@dataclass(frozen=True)
class TransferRequest:
    migration_id: str
    profile_id: str
    store_id: str
    session_id: str
    bundle_digest: str


@dataclass(frozen=True)
class NativeReadback:
    request: TransferRequest
    native_message_ids: tuple[str, ...]
    message_count: int
    user_count: int
    assistant_count: int
    execution: Literal["settled", "active"]


@dataclass(frozen=True)
class MigrationResult:
    migration_id: str
    state: Literal["active", "pending"]
    mapping: SavedConversationMapping | None
    message_refs: tuple[MessageReference, ...]
    source_digest: str
    retirement: Literal["pending", "retired"] | None = None


class MigrationJournal(Protocol):
    """Learn004 adapter; all methods require the caller's active transaction.

    reserve_in atomically inserts a unique thread journal AND pending native
    ownership (existing Learn003 mapping guard). start_in claims reserved once.
    activate_in compare-and-sets the same reservation, writes mapping+readback
    digest together, and keeps the legacy rows frozen. No method stores bytes.
    Conflicting owners/records must raise; they cannot overwrite a reservation.
    """
    def find_in(self, conn: sqlite3.Connection, *, thread_id: str | None = None,
                migration_id: str | None = None) -> MigrationRecord | None: ...

    def reserve_in(self, conn: sqlite3.Connection, record: MigrationRecord) -> None: ...

    def start_in(self, conn: sqlite3.Connection, record: MigrationRecord) -> bool: ...

    def activate_in(self, conn: sqlite3.Connection, record: MigrationRecord, *,
                    mapping: SavedConversationMapping, readback_digest: str) -> None: ...


class SnapshotIn(Protocol):
    def __call__(self, conn: sqlite3.Connection, thread_id: str, *,
                 expected_revision: int) -> SavedHistory: ...


class NativeTransfer(Protocol):
    """Tracked store-ready transfer; no generative route/grant is accepted.

    stage binds the trusted parent frame to the exact UTF-8 document and uses
    the accepted bounded chunk protocol; identical staging may replay. commit
    runs supported SDK import; it is never retried after the journal claims it.
    inspect reports references/counts ONLY after native digest AND exact export
    verification, or None only on typed exact-session absence. Other faults
    propagate. Execution settlement includes the real transfer command, not
    timestamp/outcome inference. The adapter retains actual task/pipe ownership.
    Neither stage nor commit may prompt or grant generation. Required structural
    legacy fields do not prove historical cost or M5 publication/lineage.
    """
    async def inspect(self, request: TransferRequest) -> NativeReadback | None: ...

    async def stage(self, request: TransferRequest, *, document: bytes) -> None: ...

    async def commit(self, request: TransferRequest) -> None: ...

    async def retire(self, request: TransferRequest) -> Literal["pending", "retired"]: ...


class HarnessSavedMigration:
    def __init__(self, database: Database, *,
                 snapshot_in: SnapshotIn,
                 check_current_in: Callable[[sqlite3.Connection, SavedHistory], None],
                 journal: MigrationJournal, transfer: NativeTransfer):
        self.db = database
        self.snapshot_in = snapshot_in
        self.check_current_in = check_current_in
        self.journal = journal
        self.transfer = transfer

    async def migrate_saved(self, thread_id: str, *, expected_revision: int) -> MigrationResult:
        with self.db.transaction() as conn:
            snapshot = self.snapshot_in(conn, thread_id, expected_revision=expected_revision)
            self.check_current_in(conn, snapshot)
            if (snapshot.conversation.identity.id != thread_id or
                    snapshot.conversation.revision != expected_revision):
                raise ApiError("harness_migration_conflict", "The snapshot does not match the requested saved owner revision.", 409)
            candidate = self._record(snapshot)
            record = self.journal.find_in(conn, thread_id=thread_id)
            if record is None:
                self.journal.reserve_in(conn, candidate)
                record = candidate
            else:
                self._same_source(record, candidate)
        return await self._resume(record)

    async def reconcile_migration(self, migration_id: str) -> MigrationResult:
        with self.db.transaction() as conn:
            record = self.journal.find_in(conn, migration_id=migration_id)
            if record is None:
                raise ApiError("harness_migration_unavailable", "Saved migration unavailable.", 404)
            self._current_in(conn, record)
        return await self._resume(record)

    def _record(self, snapshot):
        manifest, conversation = snapshot.manifest, snapshot.conversation
        if manifest.state != "active":
            raise ApiError("harness_not_active", "Activate validated paired stores first.", 409)
        if (conversation.retention != "saved" or conversation.kind != "learning" or
                conversation.lifecycle == "deleted"):
            raise ApiError("harness_migration_owner", "Migration requires a retained saved learning owner.", 409)
        document = self._document(snapshot)
        token = canonical_digest(["renulus-h06-session-v1", manifest.profile_id,
            manifest.runtime_store.store_id, conversation.identity.id])
        session_id = "ses_" + token
        refs = tuple(MessageReference(message.message_id,
            "msg_" + canonical_digest(["renulus-h06-message-v1", session_id, message.message_id]), message.run_id,
            message.role, index) for index, message in enumerate(snapshot.messages))
        source_digest = hashlib.sha256(document).hexdigest()
        return MigrationRecord("migration_" + token, conversation.identity.id,
            conversation.revision, manifest.model_dump_json(), snapshot.pins, session_id,
            source_digest, refs)

    @staticmethod
    def _same_source(record, candidate):
        if (record.state not in {"reserved", "transferring", "active"} or
                (record.state == "active" and record.readback_digest != record.source_digest) or
                (record.state != "active" and record.readback_digest is not None)):
            raise ApiError("harness_migration_conflict", "The migration has no valid committed readback receipt.", 409)
        if replace(record, state="reserved", readback_digest=None) != candidate:
            raise ApiError("harness_migration_conflict", "The frozen migration source or authority changed.", 409)

    def _current_in(self, conn, record):
        snapshot = self.snapshot_in(conn, record.thread_id, expected_revision=record.source_revision)
        self.check_current_in(conn, snapshot)
        self._same_source(record, self._record(snapshot))
        return snapshot

    @staticmethod
    def _request(record):
        manifest = PairedStoreManifest.model_validate_json(record.manifest_json)
        return TransferRequest(record.migration_id, manifest.profile_id,
            manifest.runtime_store.store_id, record.session_id, record.source_digest)

    @staticmethod
    def _document(snapshot):
        if len(snapshot.messages) > MAX_MESSAGES:
            raise ApiError("harness_migration_budget", "Saved history exceeds the native message transfer bound.", 409)
        messages = []
        identifiers = set()
        try:
            for message in snapshot.messages:
                if (not isinstance(message.message_id, str) or not message.message_id or
                        message.message_id in identifiers or message.role not in {"user", "assistant"} or
                        not isinstance(message.text, str) or
                        (message.run_id is not None and not isinstance(message.run_id, str))):
                    raise ValueError("invalid legacy message")
                identifiers.add(message.message_id)
                created = datetime.fromisoformat(message.created_at)
                if created.utcoffset() is None:
                    raise ValueError("legacy timestamp needs timezone")
                if message.role == "assistant":
                    if not message.completed_at:
                        raise ValueError("unresolved legacy completion")
                    completed = datetime.fromisoformat(message.completed_at)
                    if completed.utcoffset() is None or completed < created:
                        raise ValueError("invalid legacy completion")
                    if message.run_outcome not in {"completed", "cancelled", "failed", "interrupted"}:
                        raise ApiError("harness_migration_outcome_unsupported",
                            "Saved history requires a known legacy terminal outcome before conversion.", 409)
                citations = json.loads(message.citations_json)
                if not isinstance(citations, list) or any(not isinstance(item, dict) for item in citations):
                    raise ValueError("invalid legacy citations")
                messages.append({"id": message.message_id, "role": message.role,
                    "content": message.text, "runId": message.run_id, "createdAt": message.created_at,
                    **({"completedAt": message.completed_at, "legacyOutcome": message.run_outcome}
                       if message.role == "assistant" else {}),
                    "citations": citations})
            document = json.dumps({"format": "renulus.saved-session/1",
                "conversationId": snapshot.conversation.identity.id,
                "title": snapshot.conversation.title, "messages": messages},
                sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                allow_nan=False).encode("utf-8")
        except (ValueError, TypeError):
            raise ApiError("harness_migration_source", "Legacy history needs exact identities, citations and settled timestamps.", 409) from None
        if len(document) > MAX_BUNDLE_BYTES:
            raise ApiError("harness_migration_budget", "Saved history exceeds the native byte transfer bound.", 409)
        return document

    @staticmethod
    def _result(record):
        mapping = None
        if record.state == "active":
            manifest = PairedStoreManifest.model_validate_json(record.manifest_json)
            runtime = HarnessEngineReference(contract_version="harness/1",
                profile_id=manifest.profile_id, store_id=manifest.runtime_store.store_id,
                engine=manifest.runtime_store.engine, session_id=record.session_id)
            mapping = SavedConversationMapping(contract_version="harness/1",
                conversation=ConversationIdentity(type="learn_thread", id=record.thread_id),
                retention="saved", runtime=runtime)
        return MigrationResult(record.migration_id, "active" if mapping else "pending",
            mapping, record.message_refs, record.source_digest)

    async def _resume(self, record):
        if record.state == "active":
            return await self._retire(record)
        request = self._request(record)
        with self.db.transaction() as conn:
            snapshot = self._current_in(conn, record)
        # A replacement process has no staging memory. Restage the same bundle
        # before inspection; this grants no permission to repeat its import.
        await self.transfer.stage(request, document=self._document(snapshot))
        observed = await self.transfer.inspect(request)
        if observed is None:
            with self.db.transaction() as conn:
                current = self.journal.find_in(conn, migration_id=record.migration_id)
                if current is None:
                    raise ApiError("harness_migration_unavailable", "Saved migration unavailable.", 404)
                snapshot = self._current_in(conn, current)
                claimed = self.journal.start_in(conn, current)
                record = replace(current, state="transferring") if claimed else current
            if not claimed:
                # Once transfer may have started, absence cannot authorize replay.
                return await self._retire(record) if record.state == "active" else self._result(record)
            await self.transfer.commit(request)
            observed = await self.transfer.inspect(request)
        if observed is None:
            return self._result(record)
        if not isinstance(observed, NativeReadback) or observed.request != request:
            raise ApiError("harness_migration_readback", "Native migration identity changed.", 409)
        if observed.execution == "active":
            return self._result(record)
        if observed.execution != "settled":
            raise ApiError("harness_migration_readback", "Native transfer settlement is unavailable.", 409)
        with self.db.transaction() as conn:
            current = self.journal.find_in(conn, migration_id=record.migration_id)
            if current is None:
                raise ApiError("harness_migration_unavailable", "Saved migration unavailable.", 404)
            self._same_source(current, replace(record, state="reserved", readback_digest=None))
            snapshot = self._current_in(conn, current)
            refs = tuple(reference.native_id for reference in current.message_refs)
            user_count = sum(message.role == "user" for message in snapshot.messages)
            if (observed.native_message_ids != refs or
                    any(type(count) is not int for count in (observed.message_count,
                        observed.user_count, observed.assistant_count)) or
                    (observed.message_count, observed.user_count, observed.assistant_count) !=
                    (len(refs), user_count, len(refs) - user_count)):
                raise ApiError("harness_migration_readback", "Native retained history differs from the frozen source.", 409)
            if current.state != "active":
                manifest = snapshot.manifest
                runtime = HarnessEngineReference(contract_version="harness/1",
                    profile_id=manifest.profile_id, store_id=manifest.runtime_store.store_id,
                    engine=manifest.runtime_store.engine, session_id=current.session_id)
                mapping = map_saved_conversation(snapshot.conversation, runtime, manifest=manifest)
                self.journal.activate_in(conn, current, mapping=mapping, readback_digest=request.bundle_digest)
                current = replace(current, state="active", readback_digest=request.bundle_digest)
        return await self._retire(current)

    async def _retire(self, record):
        # Cleanup cannot roll back a committed owner. An active journal lets
        # restart retry this idempotent control without staging/importing again.
        retirement = await self.transfer.retire(self._request(record))
        if retirement not in {"pending", "retired"}:
            raise ApiError("harness_migration_retirement", "Native stage retirement is unavailable.", 409)
        return replace(self._result(record), retirement=retirement)
