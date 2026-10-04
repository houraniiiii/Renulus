"""Synthetic controlled engines for commit races/failures, not producer proof."""
import asyncio
import json
import threading
from types import SimpleNamespace

import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.memory.models import ManualFact
from renulus.memory.service import MemoryService

from .conftest import evidence


@pytest.fixture
def controlled_memory(services):
    controller = SimpleNamespace(entered=threading.Event(), release=threading.Event(),
        pause_extract=False, pause_index=False, fail_extract=False, fail_index=False,
        cancelled=[], response=['Synthetic late generated learning point.'])
    config = {'model_id': 'BAAI/bge-small-en-v1.5', 'dimensions': 384, 'max_tokens': 512,
              'local_files_only': True, 'cpu_threads': 2, 'fingerprint': 'synthetic-helper',
              'model_path': services.paths.helpers / 'model',
              'tokenizer_path': services.paths.helpers / 'model/tokenizer.json',
              'cache_dir': services.paths.cache / 'embedding'}
    services.registry['helpers'] = SimpleNamespace(embedding_config=lambda: config)

    class ControlledIndex:
        def __init__(self, services, path, embedding, *, transient=False):
            self.path, self.rows, self.transient = path, [], transient
            if not transient:
                path.mkdir(parents=True)

        def add(self, record):
            if controller.fail_index:
                raise ApiError('synthetic_index_failure', 'Synthetic indexing failed', 503)
            if controller.pause_index:
                controller.entered.set()
                assert controller.release.wait(5)
            self.rows.append(record.copy())
            (self.path / 'synthetic-index.json').write_text(json.dumps(self.rows))
            return record['id']

        def search(self, query, limit):
            return [{'id': row['id'], 'memory': 'DERIVED_TEXT_MUST_NOT_REPLACE_CANONICAL'} for row in self.rows[:limit]]

        def extract(self, text, binding):
            if controller.fail_extract:
                raise ApiError('synthetic_provider_failure', 'Synthetic provider failed', 503)
            if controller.pause_extract:
                controller.entered.set()
                assert controller.release.wait(5)
            return controller.response

        def purge_history(self):
            pass

        def close(self):
            pass

    class ControlledProvider:
        async def cancel(self, run_id):
            controller.cancelled.append(run_id)
            return True

    services.registry['provider'] = ControlledProvider()
    memory = MemoryService(services, index_factory=ControlledIndex)
    memory._get_embedding = lambda: SimpleNamespace(config=config)
    return memory, controller


def add(memory, text='Synthetic canonical note.', key='controlled-1'):
    return memory.add(ManualFact(text=text, idempotency_key=key, scope=ContextScope(kind=Scope.STUDY)))


@pytest.mark.asyncio
async def test_cancel_during_extraction_and_commit_winner(controlled_memory, services):
    memory, controller = controlled_memory
    scope = evidence(services)
    job = memory.enqueue('evidence-1', scope)
    controller.pause_extract = True
    task = asyncio.create_task(memory.process_pending())
    assert await asyncio.to_thread(controller.entered.wait, 3)
    cancelled = await memory.cancel(job['id'])
    assert cancelled['state'] == 'cancelled'
    controller.release.set()
    await task
    assert memory.repository.list() == []
    assert controller.cancelled == [job['id']]
    # A completed capture wins over a later cancel; cancellation does not lie.
    scope = evidence(services, 'evidence-2')
    next_job = memory.enqueue('evidence-2', scope)
    await memory.process_pending()
    outcome = await memory.cancel(next_job['id'])
    assert outcome['state'] == 'completed'
    assert len(memory.repository.list()) == 1
    await memory.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ['edit', 'delete'])
async def test_edit_or_delete_during_generation_suppresses_late_result(controlled_memory, services, action):
    memory, controller = controlled_memory
    scope = evidence(services)
    first_job = memory.repository.claim(memory.enqueue('evidence-1', scope)['id'])
    material = memory.repository.material('evidence-1', scope)
    record_id = memory.repository.commit_capture(first_job, material, [material['text']])[0]
    newer = {'scope': scope.model_dump(mode='json'), 'general_learning': True, 'text': 'New source version.'}
    services.db.execute('UPDATE learning_evidence SET payload_json=? WHERE id=?',
                        (json.dumps(newer), 'evidence-1'))
    new_job = memory.enqueue('evidence-1', scope)
    controller.pause_extract = True
    task = asyncio.create_task(memory.process_pending())
    assert await asyncio.to_thread(controller.entered.wait, 3)
    if action == 'edit':
        memory.edit(record_id, 'The learner correction owns this revision.', 1)
    else:
        memory.delete(record_id, 1)
    controller.release.set()
    await task
    assert memory.repository.job(new_job['id'])['state'] == 'cancelled'
    await asyncio.sleep(0)
    assert new_job['id'] in controller.cancelled
    records = memory.repository.list()
    if action == 'edit':
        assert len(records) == 1 and records[0]['revision'] == 2
        assert records[0]['text'] == 'The learner correction owns this revision.'
    else:
        assert records == [] and services.db.is_deleted('memory_fact', record_id)
    assert all('late generated' not in row['text'] for row in records)
    await memory.close()


@pytest.mark.asyncio
async def test_epoch_guard_prevents_stale_index_activation(controlled_memory):
    memory, controller = controlled_memory
    first = add(memory)
    memory.reindex()
    original_generation = memory._engine.path
    controller.pause_index = True
    task = asyncio.create_task(asyncio.to_thread(memory.reindex))
    assert await asyncio.to_thread(controller.entered.wait, 3)
    second = add(memory, 'A second canonical revision arrived during rebuild.', 'controlled-2')
    controller.release.set()
    with pytest.raises(ApiError) as error:
        await task
    assert error.value.code == 'memory_reindex_superseded'
    assert memory._engine.path == original_generation
    controller.pause_index = False
    memory.reindex()
    found = memory.retrieve('synthetic', scope=ContextScope(kind=Scope.STUDY))
    assert {row['id'] for row in found['records']} == {first['id'], second['id']}
    assert 'DERIVED_TEXT_MUST_NOT_REPLACE_CANONICAL' not in found['context']
    assert not original_generation.exists()
    await memory.close()


@pytest.mark.asyncio
async def test_provider_and_index_failure_keep_canonical_work_retryable(controlled_memory, services):
    memory, controller = controlled_memory
    scope = evidence(services)
    job = memory.enqueue('evidence-1', scope)
    controller.fail_extract = True
    await memory.process_pending()
    assert memory.repository.job(job['id'])['state'] == 'failed'
    assert memory.repository.list() == []
    controller.fail_extract = False
    controller.fail_index = True
    await memory.process_pending(retry=True)
    assert memory.repository.job(job['id'])['state'] == 'completed'
    assert len(memory.repository.list()) == 1
    assert memory.status()['index']['state'] == 'failed'
    assert memory.repository.list()[0]['index_state'] == 'failed'
    controller.fail_index = False
    await memory.process_pending(retry=True)
    assert len(memory.repository.list()) == 1
    assert memory.status()['index']['ready']
    assert memory.repository.job(job['id'])['attempts'] == 2
    await memory.close()


@pytest.mark.asyncio
async def test_newer_deletion_marker_reconciles_restored_canonical_rows(controlled_memory, services):
    memory, controller = controlled_memory
    scope = evidence(services)
    job = memory.repository.claim(memory.enqueue('evidence-1', scope)['id'])
    material = memory.repository.material('evidence-1', scope)
    identifier = memory.repository.commit_capture(job, material, [material['text']])[0]
    services.db.mark_deleted('memory_fact', identifier)
    memory.repository.reconcile_deletions()
    assert services.db.fetch_all('SELECT * FROM memory_facts') == []
    assert services.db.fetch_all('SELECT * FROM memory_history') == []
    with pytest.raises(ApiError) as error:
        memory.enqueue('evidence-1', scope)
    assert error.value.code == 'memory_capture_suppressed'
    assert memory.reindex()['count'] == 0
    await memory.close()


def test_missing_helpers_do_not_block_manual_correction_removal(services):
    memory = MemoryService(services)
    fact = add(memory)
    assert not memory.status()['index']['helper_ready']
    with pytest.raises(ApiError) as error:
        memory.reindex()
    assert error.value.code == 'helper_assets_missing'
    updated = memory.edit(fact['id'], 'Canonical manual correction still works offline.', 1)
    assert updated['revision'] == 2
    assert memory.delete(fact['id'], 2)['deleted']


@pytest.mark.asyncio
async def test_failed_physical_purge_excludes_fact_and_rebuild_finishes_cleanup(controlled_memory, monkeypatch):
    memory, controller = controlled_memory
    fact = add(memory)
    memory.reindex()
    old_generation = memory._engine.path
    remove = memory._remove
    def locked_generation(path):
        if path == old_generation:
            raise PermissionError('Synthetic Windows file lock')
        remove(path)
    monkeypatch.setattr(memory, '_remove', locked_generation)
    result = memory.delete(fact['id'], 1)
    assert result == {'deleted': True, 'purge_pending': True}
    assert memory.repository.list() == []
    assert memory.status()['index']['error_code'] == 'memory_purge_pending'
    assert old_generation.exists()
    monkeypatch.setattr(memory, '_remove', remove)
    assert memory.reindex()['count'] == 0
    assert not old_generation.exists()
    assert memory.retrieve('synthetic', scope=ContextScope(kind=Scope.STUDY))['records'] == []
    await memory.close()


@pytest.mark.asyncio
async def test_active_sqlite_reader_reports_pending_wal_cleanup(controlled_memory, services, monkeypatch):
    memory, controller = controlled_memory
    fact = add(memory)
    connect = services.db.connect
    def short_busy_connection():
        connection = connect()
        connection.execute('PRAGMA busy_timeout=100')
        return connection
    monkeypatch.setattr(services.db, 'connect', short_busy_connection)
    reader = services.db.connect()
    try:
        reader.execute('BEGIN')
        assert reader.execute('SELECT text FROM memory_facts WHERE id=?', (fact['id'],)).fetchone()
        result = memory.delete(fact['id'], 1)
        assert result == {'deleted': True, 'purge_pending': True}
        assert memory.repository.list() == []
        assert memory.status()['index']['error_code'] == 'memory_purge_pending'
    finally:
        reader.rollback()
        reader.close()
    assert memory.delete(fact['id'], 1)['purge_pending'] is False
    await memory.close()
