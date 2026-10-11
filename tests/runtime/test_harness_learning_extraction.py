"""Native completed answers and real engines; extraction inference is synthetic.

The production LearningOwner/selected-answer resolver are prerequisites. This
fixture does not publish lineage, replace the memory engine, or enable migrated
automatic capture. RENULUS_LEARNING_SOURCE_ROOT can select an explicitly owned
parent checkout while those prerequisites are awaiting publication.
"""
import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess

import httpx
import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.learn.conversation_models import NewConversation, Send
from renulus.memory.models import ManualFact
from renulus.runtime.harness_process import HarnessProcessConfig
from renulus.runtime.manager import ProviderManager
from renulus.server import create_app


ANSWER = 'SYNTHETIC_NATIVE_ANSWER_7152: Compare albuminuria and filtration during CKD study.'
POINT = 'SYNTHETIC_CAPTURE_7152: Albuminuria and filtration are complementary CKD study concepts.'
CORRECTION = 'SYNTHETIC_CORRECTION_7153: Review CKD classification with current teaching sources.'
ROOT_NOTE = 'Synthetic CKD study preference: compare albuminuria with filtration.'
SOURCE_ROOT = Path(os.environ.get('RENULUS_LEARNING_SOURCE_ROOT',
    Path(__file__).resolve().parents[2])).resolve()
HOST_ENTRY = Path(__file__).resolve().parents[2] / 'packages/harness/test/fixtures/learning-extraction-host.mjs'


class SyntheticExtractionTransport:
    """Only the external inference boundary is substituted in ProviderManager."""
    def __init__(self, *, hold=False):
        self.calls = []
        self.entered, self.release, self.finalized = asyncio.Event(), asyncio.Event(), asyncio.Event()
        if not hold:
            self.release.set()

    async def stream(self, provider, model, token, messages):
        self.calls.append({'provider': provider, 'model': model, 'messages': deepcopy(messages)})
        self.entered.set()
        try:
            # Keep the actual Mem0 CPU worker waiting even after Stop requests.
            # No timeout or cancellation is treated as physical settlement.
            deadline = asyncio.get_running_loop().time() + 20
            while not self.release.is_set():
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise TimeoutError('Synthetic extraction gate was not released')
                try:
                    await asyncio.wait_for(self.release.wait(), remaining)
                except asyncio.CancelledError:
                    continue
            yield {'type': 'delta', 'text': json.dumps({'memory': [{'text': POINT}]})}
            yield {'type': 'completed', 'response_model': model}
        finally:
            self.finalized.set()


@pytest.fixture
def offline(monkeypatch):
    connect, create_connection = socket.socket.connect, socket.create_connection
    def local_connect(sock, address):
        if isinstance(address, tuple) and address[0] in ('127.0.0.1', '::1', 'localhost'):
            return connect(sock, address)
        raise AssertionError('Learning extraction attempted external network access')
    def local_connection(address, *args, **kwargs):
        if address[0] in ('127.0.0.1', '::1', 'localhost'):
            return create_connection(address, *args, **kwargs)
        raise AssertionError('Learning extraction attempted external network access')
    monkeypatch.setattr(socket.socket, 'connect', local_connect)
    monkeypatch.setattr(socket, 'create_connection', local_connection)
    monkeypatch.setenv('RENULUS_LEARNING_SOURCE_ROOT', str(SOURCE_ROOT))


async def status(owner, operation='extraction-status'):
    response = await owner.process.request('host.status', {}, operation, '1', 5)
    assert response['outcome'] == 'committed_reference', response
    return response['result']


@asynccontextmanager
async def learning_profile(root, *, hold=False):
    from renulus.runtime.harness_learning import HarnessLearningOwner

    node = Path(os.environ['RENULUS_HARNESS_NODE']).resolve()
    helpers = Path(os.environ['RENULUS_MEMORY_HELPERS']).resolve()
    assert node.is_file() and (helpers / 'manifest.json').is_file()
    if not root.exists():
        root.mkdir()
        # The selected public assets remain read-only; all indexes/state are owned.
        subprocess.run(['powershell.exe', '-NoProfile', '-Command',
            f"New-Item -ItemType Junction -Path '{root / 'helpers'}' -Target '{helpers}' | Out-Null"],
            check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    services = create_app(root, source_root=SOURCE_ROOT).state.services
    transport = SyntheticExtractionTransport(hold=hold)
    provider = ProviderManager(services.paths, transport=transport, http_transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={'data': [{'id': 'mimo-v2.6-pro'}]})))
    services.registry['provider'] = provider
    await provider.connect_go('synthetic-extraction-unused', select=True)
    memory = services.get('memory')
    config = HarnessProcessConfig(node_executable=node, host_entry=HOST_ENTRY,
        profile_root=root, profile_id='synthetic-profile', store_id='synthetic-runtime',
        domain_store_id='synthetic-domain', domain_path='state/renulus.sqlite3',
        max_inflight=1, max_domain_inflight=1, boot_settings={'synthetic_answer': ANSWER,
            'synthetic_source_root': str(SOURCE_ROOT), 'ipc': {'max_inflight': 1}})
    owner = HarnessLearningOwner(services, config, configuration_id='synthetic-extraction',
        memory=memory, context_filtering=True)
    owner.install()
    probe = root / 'cache/learning-extraction'
    probe.mkdir(exist_ok=True)
    try:
        await owner.start()
        yield services, owner, memory, transport, probe
    finally:
        (probe / 'read-release').touch()
        transport.release.set()
        await memory.shutdown()
        await owner.close()
        assert (await owner.process.settlement(5))['state'] == 'settled'
        assert owner.process.domain_status()['active'] == 0
        await provider.close()
        services.get('helpers').startup.close()


async def saved_answer(services, memory):
    root_note = await asyncio.to_thread(memory.add, ManualFact(text=ROOT_NOTE,
        scope=ContextScope(kind=Scope.STUDY), idempotency_key='native-extraction-root'))
    repo = services.get('conversations')
    chat = repo.create(NewConversation())
    entry, receipt = repo.streaming.begin('learning', chat['identity']['id'],
        Send(expected_revision=chat['revision'], text='Explain synthetic CKD learning.',
            request_id='native-extraction-answer'))
    async with asyncio.timeout(60):
        events = [json.loads(encoded.split('data: ', 1)[1])
            async for encoded in repo.streaming.events(entry, receipt)]
    assert events[-1]['type'] == 'completed', json.dumps(events, indent=2)
    reference = events[-1]['payload']['answer_reference']
    pin = {'kind': 'memory', 'dependency': {'target': {'type': 'memory_revision',
        'id': f"{root_note['id']}:1"}, 'expected_revision': '1'},
        'retention': 'saved', 'content_class': 'general_learning'}
    assert reference['inputs'] == [pin]
    assert reference['dependencies'] == [pin['dependency']]
    assert reference['runtime']['profile_id'] == 'synthetic-profile'
    assert reference['runtime']['store_id'] == 'synthetic-runtime'
    assert reference['runtime']['engine'] == {'name': 'opencode', 'version': '2.0.26',
        'source_commit': '4b6fea2875e4f2e3e8a8fee181803e54f7056845'}
    assert reference['input_id'] not in reference['message_ids']
    assert reference['sha256'] == hashlib.sha256(ANSWER.encode()).hexdigest()
    assert memory.repository.jobs() == []  # Migrated automatic capture stays off.
    return root_note, reference


async def wait_for_file(path):
    async with asyncio.timeout(10):
        while not path.is_file():
            await asyncio.sleep(0.01)


async def test_native_answer_real_extraction_correction_delete_and_reopen(tmp_path, offline):
    root = tmp_path / 'profile'
    async with learning_profile(root) as (services, owner, memory, transport, probe):
        root_note, reference = await saved_answer(services, memory)
        resolver = services.get('completed_answer_resolver')
        (probe / 'read-hold').touch()
        resolution = asyncio.create_task(resolver.resolve_completed_answer(reference))
        try:
            await wait_for_file(probe / 'read-entered')
            # This must work while the actual SDK observation occupies the sole
            # data slot: logical quiescence plus a real SQLite writer transaction.
            with services.db.quiesce_writes():
                pass
            with services.db.transaction() as conn:
                conn.execute('SELECT 1')
            observed = await status(owner, 'writer-free-proof')
            assert observed['heldReads'] == 1 and observed['modelCalls'] == 1
            assert not resolution.done()
        finally:
            (probe / 'read-release').touch()
        resolved = await resolution
        assert resolved['text'] == ANSWER and resolved['digest'] == reference['sha256']
        assert resolved['input'] == {'version': 1, 'inputs': reference['inputs'],
            'dependencies': reference['dependencies']}
        assert len(resolved['publication_digest']) == 64
        wrong = deepcopy(reference)
        wrong['runtime']['store_id'] = 'synthetic-other-store'
        with pytest.raises(ApiError) as denied:
            await resolver.resolve_completed_answer(wrong)
        assert denied.value.code == 'memory_answer_reference'

        scope = ContextScope(kind=Scope.STUDY, entity_id=reference['thread_id'])
        evidence_id = 'learn-answer:' + reference['run_id']
        job = memory.enqueue(evidence_id, scope)
        result = await memory.process_pending()
        assert result['processed'] >= 1
        assert memory.repository.job(job['id'])['state'] == 'completed'
        found = await asyncio.to_thread(memory.retrieve, POINT, scope=scope)
        capture = next(record for record in found['records'] if record['source_id'] == evidence_id)
        assert capture['text'] == POINT and capture['revision'] == 1
        assert capture['sources'] == [{'source_key': 'evidence:' + evidence_id}]
        assert capture['visibility'] == 'profile-global' and capture['index_state'] == 'ready'
        assert memory.status()['producer'] == 'mem0-oss' and memory.status()['index']['ready']
        assert len(transport.calls) == 1
        sent = json.dumps(transport.calls[0]['messages'])
        assert ANSWER in sent and 'Explain synthetic CKD learning.' not in sent
        assert transport.calls[0]['provider'] == 'opencode-go'
        assert transport.calls[0]['model'] == 'mimo-v2.6-pro'
        assert transport.finalized.is_set()
        completed = services.get('provider').status()['completed_requests']
        assert completed == [{'run_id': job['id'], 'purpose': 'memory-extraction',
            'provider': 'opencode-go', 'model': 'mimo-v2.6-pro', 'response_model': 'mimo-v2.6-pro'}]
        assert not services.get('provider').status()['live_provider_verified']
        assert (await status(owner))['modelCalls'] == 1

        edited = await asyncio.to_thread(memory.edit, capture['id'], CORRECTION, 1)
        assert edited['revision'] == 2 and not edited['purge_pending']
        corrected = await asyncio.to_thread(memory.retrieve, CORRECTION, scope=scope)
        assert next(record for record in corrected['records'] if record['id'] == capture['id'])['text'] == CORRECTION
        assert POINT not in corrected['context']
        deleted = await asyncio.to_thread(memory.delete, capture['id'], 2)
        assert deleted == {'deleted': True, 'purge_pending': False}
        with pytest.raises(ApiError) as suppressed:
            memory.enqueue(evidence_id, scope)
        assert suppressed.value.code == 'memory_capture_suppressed'

    async with learning_profile(root) as (services, owner, memory, transport, probe):
        # Historical reading remains available; corrected/deleted source support
        # never makes this completed answer eligible for extraction again.
        history = await owner.bridge.messages(reference['thread_id'])
        selected = [item for item in history['items'] if item['id'] in reference['message_ids']]
        assert [item['id'] for item in selected] == reference['message_ids']
        assert ''.join(item['content'] for item in selected) == ANSWER
        with pytest.raises(ApiError) as revoked:
            await services.get('completed_answer_resolver').resolve_completed_answer(reference)
        assert revoked.value.code == 'memory_answer_unavailable'
        recalled = await asyncio.to_thread(memory.retrieve, 'CKD albuminuria', scope=scope)
        assert capture['id'] not in {record['id'] for record in recalled['records']}
        assert POINT not in recalled['context'] and CORRECTION not in recalled['context']
        assert root_note['id'] in {record['id'] for record in recalled['records']}
        with pytest.raises(ApiError) as suppressed:
            memory.enqueue(evidence_id, scope)
        assert suppressed.value.code == 'memory_capture_suppressed'
        await memory.process_pending(retry=True)
        assert not transport.calls and (await status(owner))['modelCalls'] == 0


async def test_revoked_native_answer_cannot_publish_from_a_cpu_worker_or_recapture_on_reopen(tmp_path, offline):
    root = tmp_path / 'profile'
    async with learning_profile(root, hold=True) as (services, owner, memory, transport, probe):
        root_note, reference = await saved_answer(services, memory)
        scope = ContextScope(kind=Scope.STUDY, entity_id=reference['thread_id'])
        evidence_id = 'learn-answer:' + reference['run_id']
        job = memory.enqueue(evidence_id, scope)
        capture = asyncio.create_task(memory.process_pending())
        try:
            await asyncio.wait_for(transport.entered.wait(), 10)
            # Change the exact support revision after the native bytes have been
            # resolved and the real Mem0 worker is waiting on external inference.
            corrected = await asyncio.to_thread(memory.edit, root_note['id'],
                'Synthetic corrected CKD preference: review current teaching sources.', 1)
            assert corrected['revision'] == 2 and not corrected['purge_pending']
            retired = memory.repository.job(job['id'])
            assert retired['state'] == 'cancelled'
            assert retired['error_code'] == 'memory_dependency_revoked'
            with pytest.raises(ApiError) as blocked:
                await memory.close(timeout=0.05)
            assert blocked.value.code == 'memory_close_timeout'
            assert not transport.finalized.is_set()
            with pytest.raises(ApiError) as recovery:
                with memory.recovery_guard():
                    pass
            assert recovery.value.code == 'recovery_busy'
            assert (await status(owner, 'cpu-settlement-proof'))['modelCalls'] == 1
            assert POINT not in {record['text'] for record in memory.repository.list()}
        finally:
            transport.release.set()
            await memory.close(timeout=10)
            await asyncio.gather(capture, return_exceptions=True)
        assert transport.finalized.is_set() and len(transport.calls) == 1
        assert memory.repository.job(job['id'])['state'] == 'cancelled'
        assert POINT not in {record['text'] for record in memory.repository.list()}

    async with learning_profile(root) as (services, owner, memory, transport, probe):
        with pytest.raises(ApiError) as denied:
            await services.get('completed_answer_resolver').resolve_completed_answer(reference)
        assert denied.value.code == 'memory_answer_unavailable'
        with pytest.raises(ApiError) as suppressed:
            memory.enqueue(evidence_id, scope)
        assert suppressed.value.code == 'memory_capture_suppressed'
        await memory.process_pending(retry=True)
        recalled = await asyncio.to_thread(memory.retrieve, 'CKD learning', scope=scope)
        assert POINT not in recalled['context']
        assert next(record for record in recalled['records'] if record['id'] == root_note['id'])['revision'] == 2
        assert memory.repository.job(job['id'])['state'] == 'cancelled'
        assert not transport.calls and (await status(owner))['modelCalls'] == 0
