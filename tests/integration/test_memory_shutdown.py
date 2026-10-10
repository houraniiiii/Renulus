"""Authenticated app shutdown with synthetic canonical state and real lifetimes."""
import asyncio
import json
import threading
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from tokenizers import Tokenizer, models

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.memory.models import ManualFact
from renulus.server import create_app
from renulus.storage import utc_now

from test_design_c_policy import start_test


def test_settled_shutdown_replays_on_a_new_loop_without_reopening_admission(tmp_path):
    app = create_app(tmp_path / 'repeated-shutdown-profile', token='synthetic-session')
    releases = []
    app.state.services.on_shutdown.append(lambda: releases.append('settled'))

    async def observe():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                base_url='http://testserver', headers={'x-renulus-token': 'synthetic-session'}) as client:
            result = await client.post('/api/v1/runtime/shutdown', json={'timeout_seconds': 1})
            assert result.status_code == 200, result.text
            assert result.json() == {'state': 'settled', 'api_version': 1}
            refused = await client.post('/api/v1/memory/facts', json={
                'text': 'Synthetic late note.', 'scope': {'kind': 'study'},
                'idempotency_key': 'repeated-shutdown-late'})
            assert refused.status_code == 503
            assert refused.json()['error']['code'] == 'runtime_stopping'

    asyncio.run(observe())
    asyncio.run(observe())
    assert releases == ['settled']


@pytest.fixture
async def extracting_app(tmp_path, monkeypatch):
    app = create_app(tmp_path / 'extracting-profile', token='synthetic-session')
    services = app.state.services
    control = SimpleNamespace(entered=threading.Event(), release=threading.Event(),
        finalizing=threading.Event(), finish=threading.Event(), settled=threading.Event(),
        replied=asyncio.Event(), provider_closed=asyncio.Event(), dispatch_provider=False, outbound=[])
    tokenizer = services.paths.helpers / 'synthetic-tokenizer.json'
    tokenizer.parent.mkdir(parents=True, exist_ok=True)
    Tokenizer(models.WordLevel({'[UNK]': 0}, unk_token='[UNK]')).save(str(tokenizer))
    monkeypatch.setattr(services.get('helpers'), 'embedding_config', lambda: {
        'model_id': 'BAAI/bge-small-en-v1.5', 'dimensions': 384, 'max_tokens': 512,
        'local_files_only': True, 'cpu_threads': 2, 'fingerprint': 'synthetic-helper',
        'model_path': services.paths.helpers / 'unused-model', 'tokenizer_path': tokenizer,
        'cache_dir': services.paths.cache / 'embedding'})
    loop = asyncio.get_running_loop()

    class Extractor:
        def __init__(self, services, path, embedding, *, transient=False):
            self.path, self.transient = path, transient
            path.mkdir(parents=True, exist_ok=True)

        def extract(self, text, binding):
            control.entered.set()
            assert control.release.wait(10)
            if control.dispatch_provider:
                from renulus.memory.providers import ApprovedLLM, generation_binding
                token = generation_binding.set(binding)
                try:
                    ApprovedLLM().generate_response([{'role': 'user', 'content': text}])
                finally:
                    generation_binding.reset(token)
            return ['Synthetic dialysis learning point']

        def close(self):
            if self.transient:
                control.finalizing.set()
                assert control.finish.wait(10)
                async def reply():
                    assert not control.provider_closed.is_set()
                    control.replied.set()
                asyncio.run_coroutine_threadsafe(reply(), loop).result(timeout=1)
                control.settled.set()

        def purge_history(self):
            pass

    memory = services.get('memory')
    memory.index_factory = Extractor
    await asyncio.to_thread(memory.reindex)
    scope = ContextScope(kind=Scope.STUDY, entity_id='synthetic-study')
    services.db.execute('INSERT INTO learning_evidence VALUES(?,?,?,?,?,?)', (
        'synthetic-evidence', 'learning-point', 'dialysis', scope.entity_id,
        json.dumps({'scope': scope.model_dump(mode='json'), 'general_learning': True,
                    'text': 'Synthetic dialysis learning point'}), utc_now()))
    memory.enqueue('synthetic-evidence', scope)
    # This dependency is released after memory in the actual callback order.
    services.on_shutdown_dependencies.insert(0, control.provider_closed.set)
    try:
        yield app, control
    finally:
        control.release.set()
        control.finish.set()
        await services.shutdown()


@pytest.mark.asyncio
async def test_authenticated_shutdown_is_neutral_during_test_and_closes_admission(tmp_path):
    app = create_app(tmp_path / 'shutdown-profile', token='synthetic-session')
    start_test(app.state.services)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                base_url='http://testserver') as client:
        assert (await client.post('/api/v1/runtime/shutdown', json={})).status_code == 401
        client.headers['x-renulus-token'] = 'synthetic-session'
        result = await client.post('/api/v1/runtime/shutdown', json={'timeout_seconds': 1})
        assert result.status_code == 200, result.text
        assert result.json() == {'state': 'settled', 'api_version': 1}
        status = await client.get('/api/v1/runtime/shutdown')
        assert status.json() == {'state': 'settled', 'api_version': 1}
        assert (await client.get('/api/v1/runtime/status')).status_code == 200
        refused = await client.post('/api/v1/memory/facts', json={
            'text': 'Synthetic late note.', 'scope': {'kind': 'study'}, 'idempotency_key': 'late'})
        assert refused.status_code == 503
        assert refused.json()['error']['code'] == 'runtime_stopping'
        assert app.state.services.get('memory').repository.list() == []


@pytest.mark.asyncio
async def test_shutdown_acknowledgement_also_stops_the_registered_library_worker(tmp_path):
    app = create_app(tmp_path / 'library-profile', token='synthetic-session')
    async with app.router.lifespan_context(app):
        worker = app.state.services.get('knowledge_worker')
        assert worker.status()['running']
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                base_url='http://testserver', headers={'x-renulus-token': 'synthetic-session'}) as client:
            result = await client.post('/api/v1/runtime/shutdown', json={'timeout_seconds': 1})
            assert result.json() == {'state': 'settled', 'api_version': 1}
            assert not worker.status()['running'], 'The profile acknowledged shutdown before its library worker stopped'


@pytest.mark.asyncio
async def test_shutdown_requires_a_configured_session_even_in_an_unlocked_test_app(tmp_path):
    app = create_app(tmp_path / 'unlocked-profile')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
            base_url='http://testserver') as client:
        result = await client.post('/api/v1/runtime/shutdown', json={})
        assert result.status_code == 401
        assert result.json()['error']['code'] == 'invalid_session'
        assert app.state.services.shutdown_status()['state'] == 'open'
    await app.state.services.shutdown()


@pytest.mark.asyncio
async def test_blocked_library_join_cannot_delay_memory_or_provider_admission_closure(extracting_app, monkeypatch):
    app, control = extracting_app
    services = app.state.services
    memory, worker = services.get('memory'), services.get('knowledge_worker')
    joined, release_library = threading.Event(), threading.Event()
    original_stop = worker.stop

    def held_stop(timeout=5):
        if timeout is None:
            joined.set()
            assert release_library.wait(10)
        original_stop(timeout)

    class Provider:
        async def cancel(self, identifier):
            return True
        def status(self):
            return {'active_runs': []}
        async def stream(self, *args, **kwargs):
            control.outbound.append(kwargs['run_id'])
            yield '{"memory": []}'

    services.registry['provider'] = Provider()
    monkeypatch.setattr(worker, 'stop', held_stop)
    control.dispatch_provider = True
    await memory.start()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
            base_url='http://testserver', headers={'x-renulus-token': 'synthetic-session'}) as client:
        try:
            assert await asyncio.to_thread(control.entered.wait, 3)
            response = await client.post('/api/v1/runtime/shutdown', json={'timeout_seconds': .05})
            assert response.status_code == 503
            assert joined.is_set()
            control.release.set()
            assert await asyncio.to_thread(control.finalizing.wait, 3)
            assert control.outbound == [], 'An earlier library join left memory provider admission open'
            with pytest.raises(ApiError) as caught:
                memory.add(ManualFact(text='Synthetic late point', scope=ContextScope(kind=Scope.STUDY),
                                     idempotency_key='blocked-library-late'))
            assert caught.value.code == 'memory_stopping'
        finally:
            control.release.set()
            control.finish.set()
            release_library.set()
        assert (await client.post('/api/v1/runtime/shutdown', json={'timeout_seconds': 1})).json()['state'] == 'settled'
        assert memory.repository.list() == []


@pytest.mark.asyncio
async def test_shutdown_cancels_the_registered_provider_owner_after_a_consumer_adapter_is_replaced(tmp_path):
    app = create_app(tmp_path / 'registered-provider-profile', token='synthetic-session')

    class ConsumerAdapter:
        def status(self):
            return {'test_adapter': True, 'live_provider_verified': False}

    app.state.services.registry['provider'] = ConsumerAdapter()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
            base_url='http://testserver', headers={'x-renulus-token': 'synthetic-session'}) as client:
        result = await client.post('/api/v1/runtime/shutdown', json={'timeout_seconds': 1})
        assert result.status_code == 200, result.text
        assert result.json() == {'state': 'settled', 'api_version': 1}


@pytest.mark.asyncio
async def test_failed_drain_is_explicit_and_never_reopens_admission(tmp_path):
    app = create_app(tmp_path / 'failed-drain-profile', token='synthetic-session')
    def unavailable_finalizer():
        raise OSError('Synthetic cleanup failure')
    app.state.services.on_shutdown.append(unavailable_finalizer)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url='http://testserver', headers={'x-renulus-token': 'synthetic-session'}) as client:
        result = await client.post('/api/v1/runtime/shutdown', json={'timeout_seconds': .05})
        assert result.status_code == 503
        assert result.json()['error']['code'] == 'runtime_shutdown_failed'
        assert (await client.get('/api/v1/runtime/shutdown')).json()['state'] == 'failed'
        assert (await client.post('/api/v1/memory/retry')).status_code == 503
        assert (await client.post('/api/v1/runtime/shutdown', json={})).status_code == 503


@pytest.mark.asyncio
@pytest.mark.parametrize('disconnect', [False, True], ids=['connected', 'cancelled-client'])
async def test_shutdown_retains_an_admitted_library_writer_until_it_really_finishes(tmp_path, monkeypatch, disconnect):
    app = create_app(tmp_path / 'admitted-import-profile', token='synthetic-session')
    services = app.state.services
    entered, release = threading.Event(), threading.Event()
    dependencies_released = asyncio.Event()
    services.on_shutdown_dependencies.insert(0, dependencies_released.set)
    original_write = Path.write_bytes

    def write(path, data):
        if path.name == 'original.txt' and path.is_relative_to(services.paths.library):
            entered.set()
            assert release.wait(10), 'Test did not release the actual Library original writer'
        return original_write(path, data)

    monkeypatch.setattr(Path, 'write_bytes', write)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
            base_url='http://testserver', headers={'x-renulus-token': 'synthetic-session'}) as client:
        request = asyncio.create_task(client.post('/api/v1/library/import/text', json={
            'text': 'Synthetic dialysis study note', 'scope': {'kind': Scope.LIBRARY.value},
            'idempotency_key': 'held-original'}))
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            if disconnect:
                request.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await request
            result = await client.post('/api/v1/runtime/shutdown', json={'timeout_seconds': .05})
            assert result.status_code == 503, result.text
            assert result.json()['error']['code'] == 'runtime_shutdown_pending'
            assert not dependencies_released.is_set()
            assert (await client.get('/api/v1/runtime/shutdown')).json()['state'] == 'draining'
        finally:
            release.set()
            response, = await asyncio.gather(request, return_exceptions=True)
        if not disconnect:
            assert response.status_code == 202, response.text
        assert (await client.post('/api/v1/runtime/shutdown', json={'timeout_seconds': 1})).json()['state'] == 'settled'
        assert dependencies_released.is_set()
        assert services.db.fetch_one('SELECT COUNT(*) n FROM knowledge_documents')['n'] == 1


@pytest.mark.asyncio
async def test_shutdown_timeout_keeps_status_reply_loop_and_retry_owned(extracting_app):
    app, control = extracting_app
    memory = app.state.services.get('memory')
    async with app.router.lifespan_context(app):
        assert await asyncio.to_thread(control.entered.wait, 3)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                base_url='http://testserver', headers={'x-renulus-token': 'synthetic-session'}) as client:
            try:
                pending = await asyncio.wait_for(client.post('/api/v1/runtime/shutdown',
                    json={'timeout_seconds': .05}), 1)
                assert pending.status_code == 503, pending.text
                assert pending.json()['error']['code'] == 'runtime_shutdown_pending'
                assert (await client.get('/api/v1/runtime/shutdown')).json()['state'] == 'draining'
                assert (await client.get('/api/v1/runtime/status')).status_code == 200
                assert (await client.post('/api/v1/memory/retry')).status_code == 503
                assert not control.provider_closed.is_set()
                control.release.set()
                assert await asyncio.to_thread(control.finalizing.wait, 3)
                again = await client.post('/api/v1/runtime/shutdown', json={'timeout_seconds': .05})
                assert again.status_code == 503
                assert memory.repository.list() == []
            finally:
                control.release.set()
                control.finish.set()
            settled = await client.post('/api/v1/runtime/shutdown', json={'timeout_seconds': 1})
            assert settled.json() == {'state': 'settled', 'api_version': 1}
            assert control.settled.is_set() and control.replied.is_set()
            assert control.provider_closed.is_set()
            assert memory.repository.list() == []


@pytest.mark.asyncio
async def test_cancelled_application_lifespan_waits_for_actual_memory_settlement(extracting_app):
    app, control = extracting_app
    exit_requested = asyncio.Event()

    async def application():
        async with app.router.lifespan_context(app):
            await exit_requested.wait()

    lifetime = asyncio.create_task(application())
    try:
        assert await asyncio.to_thread(control.entered.wait, 3)
        exit_requested.set()
        async with asyncio.timeout(3):
            while app.state.services.shutdown_status()['state'] == 'open':
                await asyncio.sleep(0)
        lifetime.cancel()
        done, _ = await asyncio.wait({lifetime}, timeout=.05)
        assert not done, 'Lifespan exited while a memory worker still needed its reply loop'
        assert not control.provider_closed.is_set()
    finally:
        exit_requested.set()
        control.release.set()
        control.finish.set()
        await asyncio.gather(lifetime, return_exceptions=True)
    assert control.settled.is_set() and control.replied.is_set()
    assert control.provider_closed.is_set()
