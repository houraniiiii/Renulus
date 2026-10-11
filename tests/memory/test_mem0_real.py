"""Real selected engines, synthetic records; generation is explicitly mocked.

Set RENULUS_MEMORY_HELPERS to a hash-manifested public helper directory copied
with scripts/copy_helper_assets.py. Missing assets skip these producer checks;
there is no model acquisition or live subscription use in this suite.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
from types import SimpleNamespace

import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.memory.models import ManualFact
from renulus.memory.service import MemoryService
from renulus.learn.service import LearnService
from renulus.runtime.helpers import HelperAssets

from .conftest import evidence


def assert_absent(root, marker):
    for path in root.rglob('*'):
        if path.is_file():
            if path.name == '.lock':
                # Qdrant's short process marker is held with exclusive Windows
                # sharing. Its size alone proves it cannot contain this sentinel.
                assert path.stat().st_size < len(marker)
            else:
                assert marker not in path.read_bytes(), str(path.relative_to(root))


@pytest.fixture
def real_memory(services, monkeypatch):
    root = os.environ.get('RENULUS_MEMORY_HELPERS')
    if not root or not (Path(root) / 'manifest.json').is_file():
        pytest.skip('Explicit offline helper path was not supplied')
    if any(importlib.util.find_spec(name) is None for name in ('mem0', 'fastembed', 'qdrant_client')):
        pytest.skip('Selected Mem0/FastEmbed/Qdrant packages are not installed')
    root = Path(root).resolve()
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    # Only the embedding group is needed here. Preserve the central manifest,
    # verify its source and copy once; never load Docling or provision assets.
    # The shared public asset directory need not be named "helpers". Validate
    # that explicitly selected root before copying the embedding group.
    paths = SimpleNamespace(helpers=root, cache=services.paths.cache, source_root=services.paths.source_root)
    HelperAssets(paths).embedding_config()
    for record in manifest['groups']['embedding']['files']:
        target = services.paths.helpers / record['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / record['path'], target)
    (services.paths.helpers / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    services.registry['helpers'] = HelperAssets(services.paths)

    connect, create_connection = socket.socket.connect, socket.create_connection
    def offline_socket(sock, address):
        # Windows asyncio creates its self-pipe over loopback TCP. Permit that
        # local OS mechanism while refusing every remote provider/download.
        if isinstance(address, tuple) and address[0] in ('127.0.0.1', '::1', 'localhost'):
            return connect(sock, address)
        raise AssertionError('A real memory check attempted remote network access')
    def offline_connection(address, *args, **kwargs):
        if address[0] in ('127.0.0.1', '::1', 'localhost'):
            return create_connection(address, *args, **kwargs)
        raise AssertionError('A real memory check attempted remote network access')
    monkeypatch.setattr(socket.socket, 'connect', offline_socket)
    monkeypatch.setattr(socket, 'create_connection', offline_connection)
    memory = MemoryService(services)
    services.registry['memory'] = memory
    return memory


@pytest.mark.asyncio
async def test_actual_mem0_qdrant_fastembed_delete_history_restart_reindex(real_memory, services):
    memory = real_memory
    scope = ContextScope(kind=Scope.STUDY)
    original = memory.add(ManualFact(text='SYNTHETIC_OLD_NOTE_4821 Compare urinary sediment in glomerular disorders.',
        topic_id='glomerular', scope=scope, idempotency_key='real-1'))
    memory.add(ManualFact(text='CKD study preference: revisit mineral and bone disorder mechanisms.',
        topic_id='ckd', kind='preference', scope=scope, idempotency_key='real-2'))
    memory.add(ManualFact(text='Review educational concepts of transplant rejection.',
        topic_id='transplant', scope=scope, idempotency_key='real-3'))
    built = memory.reindex()
    assert built['ready'] and built['count'] == 3
    engine = memory._engine
    assert engine.memory.__class__.__module__ == 'mem0.memory.main'
    assert engine.memory.vector_store.client.__class__.__module__.startswith('qdrant_client')
    assert engine.memory.vector_store.client._client.__class__.__name__ == 'QdrantLocal'
    assert engine.memory.embedding_model.delegate.model.__class__.__module__.startswith('fastembed')
    assert engine.memory.embedding_model.delegate.config['dimensions'] == 384
    assert engine.memory.embedding_model.delegate.config['cpu_threads'] == 2
    assert engine.memory.db.connection.execute('SELECT count(*) FROM history').fetchone()[0] == 0
    found = memory.retrieve('CKD mineral bone learning preference', scope=scope, limit=1)
    assert found['records'][0]['topic_id'] == 'ckd'
    assert 'r1]' in found['context']
    assert len(memory.retrieve('transplant rejection', scope=scope, budget_chars=0)['context']) == 0
    previous_generation = engine.path
    corrected = memory.edit(original['id'], 'SYNTHETIC_CURRENT_NOTE_6742 Review proteinuria mechanisms.', 1)
    assert corrected['revision'] == 2 and not corrected['purge_pending']
    assert not previous_generation.exists()
    memory.reindex()
    assert_absent(memory.root, b'SYNTHETIC_OLD_NOTE_4821')
    memory.purge_history(original['id'])
    assert memory.repository.history(original['id']) == []
    memory.reindex()
    assert memory._engine.memory.db.connection.execute('SELECT count(*) FROM history').fetchone()[0] == 0
    deleted = memory.delete(original['id'], 2)
    assert deleted == {'deleted': True, 'purge_pending': False}
    memory.reindex()
    for marker in (b'SYNTHETIC_OLD_NOTE_4821', b'SYNTHETIC_CURRENT_NOTE_6742'):
        assert_absent(services.paths.root, marker)
    await memory.close()
    restarted = MemoryService(services)
    try:
        rebuilt = restarted.reindex()
        assert rebuilt['count'] == 2
        assert all(row['id'] != original['id'] for row in restarted.repository.list())
        result = restarted.retrieve('glomerular proteinuria', scope=scope)
        assert all(row['id'] != original['id'] for row in result['records'])
        assert services.db.is_deleted('memory_fact', original['id'])
    finally:
        await restarted.close()


@pytest.mark.asyncio
async def test_actual_mem0_extraction_uses_only_mocked_scoped_provider(real_memory, services):
    calls = []

    class SyntheticProvider:
        async def stream(self, messages, **kwargs):
            calls.append({'messages': messages, **kwargs})
            yield json.dumps({'memory': [{'text': 'Synthetic learning point: compare glomerular mechanisms.'}]})

        async def cancel(self, identifier):
            return True

    services.registry['provider'] = SyntheticProvider()
    scope = evidence(services)
    job = real_memory.enqueue('evidence-1', scope)
    try:
        await real_memory.process_pending()
        assert real_memory.repository.job(job['id'])['state'] == 'completed'
        records = real_memory.repository.list()
        assert len(records) == 1 and records[0]['source_id'] == 'evidence-1'
        assert calls[0]['scope'] == scope
        assert calls[0]['run_id'] == job['id']
        assert calls[0]['purpose'] == 'memory-extraction'
        assert 'model' not in calls[0]  # F0 owns selection; no new/default model.
        assert not any(path.name.startswith('capture_') for path in real_memory.root.iterdir())
        assert real_memory._engine.memory.db.connection.execute('SELECT count(*) FROM messages').fetchone()[0] == 0
        assert real_memory.delete(records[0]['id'], 1)['deleted']
        with pytest.raises(ApiError) as error:
            real_memory.enqueue('evidence-1', scope)
        assert error.value.code == 'memory_capture_suppressed'
    finally:
        await real_memory.close()


@pytest.mark.asyncio
async def test_actual_cpu_engine_support_revocation_after_edit_delete_reindex_reopen(real_memory, services):
    memory = real_memory
    services.db.apply_migration('learn-real-lineage-test',
        (services.paths.source_root / 'runtime/renulus/learn/schema.sql').read_text(encoding='utf-8'))
    learn = LearnService(services)
    services.registry['learn'] = learn
    old_point = 'SYNTHETIC_LINEAGE_POINT_9012 Compare glomerular mechanisms.'
    current_point = 'SYNTHETIC_LINEAGE_POINT_9013 Review dialysis mechanisms.'
    class SyntheticProvider:
        point = old_point
        async def stream(self, messages, **kwargs):
            yield json.dumps({'memory': [{'text': self.point}]}) if kwargs['purpose'] == 'memory-extraction' else self.point
        async def cancel(self, identifier):
            return True
    provider = SyntheticProvider()
    services.registry['provider'] = provider
    scope = ContextScope(kind=Scope.STUDY)
    async def publish(root, key):
        _, run = learn.prepare(root['text'], scope, None, 'glomerular', 'direct', key)
        # No trusted publisher override: Learn records the actual CPU recall pins.
        assert run.publication is None
        flow = [event async for event in learn.answer(run, root['text'], 'direct', 'glomerular')]
        assert flow[-1].type == 'completed'
        await memory.process_pending()
    try:
        root = memory.add(ManualFact(text='Synthetic glomerular study preference.', topic_id='glomerular',
            scope=scope, idempotency_key='cpu-root'))
        await publish(root, 'cpu-answer-old')
        assert old_point in [row['text'] for row in memory.repository.list()]
        assert memory._engine.memory.embedding_model.delegate.model.__class__.__module__.startswith('fastembed')
        root = memory.edit(root['id'], 'Synthetic corrected dialysis preference.', 1)
        memory.reindex()
        assert old_point not in [row['text'] for row in memory.retrieve(old_point, scope=scope)['records']]
        assert_absent(memory.root, b'SYNTHETIC_LINEAGE_POINT_9012')
        provider.point = current_point
        await publish(root, 'cpu-answer-current')
        assert current_point in [row['text'] for row in memory.repository.list()]
        memory.delete(root['id'], 2)
        memory.reindex()
        assert_absent(memory.root, b'SYNTHETIC_LINEAGE_POINT_9013')
        await memory.close()
        memory = MemoryService(services)
        services.registry['memory'] = memory
        await memory.process_pending(retry=True)
        memory.reindex()
        for point in (old_point, current_point):
            assert point not in [row['text'] for row in memory.retrieve(point, scope=scope)['records']]
    finally:
        await memory.close()
