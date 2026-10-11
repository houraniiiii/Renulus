# SPDX-License-Identifier: MIT
"""Canonical metadata journal; source and native readback are synthetic."""
from dataclasses import replace

import pytest

from renulus.contracts import ApiError
from renulus.harness_contracts import HarnessEngineReference, map_saved_conversation
from renulus.learn.harness_migration import MessageReference, MigrationRecord
from renulus.server import create_app
from renulus.learn.conversation_models import Mutation, NewConversation
from renulus.storage.backup import export_records
from test_harness_migration import history
from test_harness_bridge import collect, native_at


async def test_conflicting_native_session_leaves_no_partial_reservation_when_caller_commits(tmp_path):
    services, repo, bridge, _, identifier, request = native_at(tmp_path)
    entry, receipt = repo.streaming.begin('learning', identifier, request)
    assert (await collect(repo.streaming, entry, receipt))[-1]['type'] == 'completed'
    existing = bridge.mapping(identifier)
    second = repo.create(NewConversation(title='Other synthetic history'))
    record = MigrationRecord('migration_session_conflict', second['identity']['id'], 7,
        history().manifest.model_dump_json(), history().pins,
        existing['runtime']['session_id'], 'a' * 64, ())
    journal = repo.migration_journal
    with services.db.transaction() as conn:
        with pytest.raises(ApiError) as rejected:
            journal.reserve_in(conn, record)
        assert rejected.value.code == 'harness_migration_conflict'
        assert journal.find_in(conn, thread_id=record.thread_id) is None
    with services.db.transaction() as conn:
        assert journal.find_in(conn, thread_id=record.thread_id) is None
    assert bridge.mapping(identifier) == existing


def test_activation_rejects_mapping_from_another_engine_cohort(tmp_path):
    services = create_app(tmp_path / 'cohort-profile').state.services
    thread = services.get('learn').create_thread('Synthetic cohort history')
    source = history()
    conversation = source.conversation.model_copy(update={'identity':
        source.conversation.identity.model_copy(update={'id': thread['id']})})
    record = MigrationRecord('migration_cohort_conflict', thread['id'], 7,
        source.manifest.model_dump_json(), source.pins, 'ses_cohort_conflict', 'a' * 64, ())
    runtime = HarnessEngineReference(contract_version='harness/1', profile_id=source.manifest.profile_id,
        store_id=source.manifest.runtime_store.store_id, engine=source.manifest.runtime_store.engine,
        session_id=record.session_id)
    mapping = map_saved_conversation(conversation, runtime, manifest=source.manifest)
    mismatched = mapping.model_copy(update={'runtime': runtime.model_copy(update={
        'engine': runtime.engine.model_copy(update={'version': '2.0.25'})})})
    journal = services.get('conversations').migration_journal
    with services.db.transaction() as conn:
        journal.reserve_in(conn, record)
        assert journal.start_in(conn, record)
        claimed = journal.find_in(conn, migration_id=record.migration_id)
        with pytest.raises(ApiError) as rejected:
            journal.activate_in(conn, claimed, mapping=mismatched, readback_digest=record.source_digest)
        assert rejected.value.code == 'harness_migration_conflict'
        assert journal.find_in(conn, migration_id=record.migration_id).state == 'transferring'
        assert journal.mapping_in(conn, thread['id']) is None
        journal.activate_in(conn, claimed, mapping=mapping, readback_digest=record.source_digest)
        assert journal.mapping_in(conn, thread['id']) == mapping


def test_migration_journal_reserves_and_activates_in_one_canonical_transaction(tmp_path):
    from renulus.learn.harness_migration_journal import HarnessMigrationJournal

    services = create_app(tmp_path / 'profile').state.services
    thread = services.get('learn').create_thread('Synthetic transplant history')
    source = history()
    conversation = source.conversation.model_copy(update={'identity':
        source.conversation.identity.model_copy(update={'id': thread['id']})})
    source = replace(source, conversation=conversation)
    journal = HarnessMigrationJournal(services.db)
    record = MigrationRecord('migration_synthetic_journal', thread['id'], 7,
        source.manifest.model_dump_json(), source.pins, 'ses_synthetic_journal', 'a' * 64, (
            MessageReference('legacy_user', 'msg_synthetic_user', 'old_run', 'user', 0),
            MessageReference('legacy_answer', 'msg_synthetic_answer', 'old_run', 'assistant', 1)))
    runtime = HarnessEngineReference(contract_version='harness/1', profile_id=source.manifest.profile_id,
        store_id=source.manifest.runtime_store.store_id, engine=source.manifest.runtime_store.engine,
        session_id=record.session_id)
    mapping = map_saved_conversation(conversation, runtime, manifest=source.manifest)
    with pytest.raises(RuntimeError, match='rollback'):
        with services.db.transaction() as conn:
            journal.reserve_in(conn, record)
            assert journal.find_in(conn, thread_id=thread['id']) == record
            raise RuntimeError('rollback')
    with services.db.transaction() as conn:
        assert journal.find_in(conn, thread_id=thread['id']) is None
        assert journal.mapping_in(conn, thread['id']) is None
        journal.reserve_in(conn, record)
        assert journal.start_in(conn, record) is True
        assert journal.start_in(conn, record) is False
        claimed = journal.find_in(conn, migration_id=record.migration_id)
        assert claimed == replace(record, state='transferring')
        journal.activate_in(conn, claimed, mapping=mapping, readback_digest=record.source_digest)
        assert journal.mapping_in(conn, thread['id']) == mapping
    reopened = HarnessMigrationJournal(services.db)
    with services.db.transaction() as conn:
        active = reopened.find_in(conn, thread_id=thread['id'])
        assert active == replace(record, state='active', readback_digest='a' * 64)
        assert reopened.mapping_in(conn, thread['id']) == mapping


async def test_deletion_preserves_only_purge_coordinates_through_owner_cascade_and_reopen(tmp_path):
    from renulus.learn.harness_migration_journal import HarnessMigrationJournal

    profile = tmp_path / 'deleted-profile'
    services = create_app(profile).state.services
    repo = services.get('conversations')
    chat = repo.create(NewConversation(title='Synthetic migrated owner'), 'migrated-create')
    thread_id = chat['identity']['id']
    source = history()
    conversation = source.conversation.model_copy(update={'identity':
        source.conversation.identity.model_copy(update={'id': thread_id})})
    journal = HarnessMigrationJournal(services.db)
    record = MigrationRecord('migration_synthetic_delete', thread_id, 7,
        source.manifest.model_dump_json(), source.pins, 'ses_synthetic_deleted', 'a' * 64, ())
    runtime = HarnessEngineReference(contract_version='harness/1', profile_id=source.manifest.profile_id,
        store_id=source.manifest.runtime_store.store_id, engine=source.manifest.runtime_store.engine,
        session_id=record.session_id)
    mapping = map_saved_conversation(conversation, runtime, manifest=source.manifest)
    with services.db.transaction() as conn:
        journal.reserve_in(conn, record)
        assert journal.start_in(conn, record)
        claimed = journal.find_in(conn, migration_id=record.migration_id)
        journal.activate_in(conn, claimed, mapping=mapping, readback_digest=record.source_digest)
    await repo.delete('learning', thread_id, Mutation(expected_revision=chat['revision']), 'migrated-delete')
    purges = journal.pending_purges()
    assert len(purges) == 1
    assert (purges[0].profile_id, purges[0].store_id, purges[0].session_id,
        purges[0].operation_id, purges[0].attempt_id, purges[0].state) == (
        source.manifest.profile_id, source.manifest.runtime_store.store_id,
        'ses_synthetic_deleted', 'migration_synthetic_delete', '1', 'pending')
    exported = export_records(services)
    assert exported['records']['learn_harness_migrations'] == []
    assert exported['records']['learn_harness_mappings'] == []
    assert set(exported['records']['learn_harness_purges'][0]) == {
        'purge_id', 'profile_id', 'store_id', 'session_id', 'operation_id', 'attempt_id', 'state'}
    reopened = create_app(profile).state.services
    assert HarnessMigrationJournal(reopened.db).pending_purges() == purges
