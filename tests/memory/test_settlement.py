"""Public memory/recovery lifetime checks with SQLite and a bounded extractor."""
import asyncio
import threading
from types import SimpleNamespace

import pytest
from tokenizers import Tokenizer, models

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.memory.models import ManualFact
from renulus.memory.api import create_router

from .conftest import evidence


@pytest.fixture
async def settling_memory(services):
    control = SimpleNamespace(
        entered=threading.Event(), release=threading.Event(),
        finalizing=threading.Event(), finish=threading.Event(),
        settled=threading.Event(), cancel_requested=asyncio.Event(),
        close_needs_reply=False, close_reply=asyncio.Event(),
        pause_index=False, index_entered=threading.Event(), index_release=threading.Event(),
        provider_admission=[],
    )
    tokenizer = services.paths.helpers / 'synthetic-tokenizer.json'
    tokenizer.parent.mkdir(parents=True, exist_ok=True)
    Tokenizer(models.WordLevel({'[UNK]': 0}, unk_token='[UNK]')).save(str(tokenizer))
    config = {
        'model_id': 'BAAI/bge-small-en-v1.5', 'dimensions': 384, 'max_tokens': 512,
        'local_files_only': True, 'cpu_threads': 2, 'fingerprint': 'synthetic-helper',
        'model_path': services.paths.helpers / 'unused-model',
        'tokenizer_path': tokenizer, 'cache_dir': services.paths.cache / 'embedding',
    }
    services.registry['helpers'] = SimpleNamespace(embedding_config=lambda: config)
    loop = asyncio.get_running_loop()

    class Extractor:
        def __init__(self, services, path, embedding, *, transient=False):
            self.path, self.transient = path, transient
            self.rows = []
            path.mkdir(parents=True, exist_ok=True)

        def extract(self, text, binding):
            control.entered.set()
            assert control.release.wait(10), 'Test did not release extraction'
            control.provider_admission.append(binding['current']())
            return ['Synthetic learning point: compare dialysis modalities.']

        def close(self):
            if self.transient:
                control.finalizing.set()
                try:
                    assert control.finish.wait(10), 'Test did not release finalization'
                finally:
                    control.settled.set()
            elif control.close_needs_reply:
                async def reply():
                    control.close_reply.set()
                # Models the provider/IPC callback needed by a finalizer.
                asyncio.run_coroutine_threadsafe(reply(), loop).result(timeout=1)

        def add(self, record):
            if control.pause_index:
                control.index_entered.set()
                assert control.index_release.wait(5), 'Test did not release indexing'
            self.rows.append(record)
            return record['id']

        def search(self, query, limit):
            return [{'id': row['id']} for row in self.rows[:limit]]

        def purge_history(self):
            pass

    class Provider:
        async def cancel(self, identifier):
            control.cancel_requested.set()
            return True

    services.registry['provider'] = Provider()
    create_router(services)
    memory = services.get('memory')
    memory.index_factory = Extractor
    try:
        # Import/initialization time is outside the event-controlled interval.
        await asyncio.to_thread(memory.reindex)
        yield memory, control
    finally:
        control.release.set()
        control.finish.set()
        control.index_release.set()
        if control.entered.is_set():
            assert await asyncio.to_thread(control.settled.wait, 5)
        await memory.close()


def recovery_is_busy(memory):
    with pytest.raises(ApiError) as caught:
        with memory.recovery_guard():
            pytest.fail('Recovery acquired a profile with unsettled memory work')
    assert caught.value.code == 'recovery_busy'


@pytest.mark.asyncio
async def test_provider_dispatch_rechecks_cancellation_on_the_reply_loop(settling_memory, services):
    from renulus.memory.providers import ApprovedLLM, generation_binding

    loop = asyncio.get_running_loop()
    revoked = asyncio.Event()
    streams = []

    class Provider:
        async def stream(self, *args, **kwargs):
            streams.append(kwargs['run_id'])
            yield '{"memory": []}'

    services.registry['provider'] = Provider()

    def current():
        if revoked.is_set():
            return False
        async def cancel_before_dispatch():
            revoked.set()
        # The worker's earlier check can complete just before the loop handles
        # Stop. The actual outbound dispatch must check its own admission.
        asyncio.run_coroutine_threadsafe(cancel_before_dispatch(), loop).result(timeout=1)
        return True

    def extract():
        token = generation_binding.set({'services': services, 'loop': loop,
            'scope': ContextScope(kind=Scope.STUDY), 'run_id': 'cancelled-dispatch', 'current': current})
        try:
            return ApprovedLLM().generate_response([{'role': 'user', 'content': 'Synthetic learning point'}])
        finally:
            generation_binding.reset(token)

    with pytest.raises(ApiError) as caught:
        await asyncio.wait_for(asyncio.to_thread(extract), 3)
    assert caught.value.code == 'memory_capture_cancelled'
    assert streams == []


@pytest.mark.asyncio
async def test_public_reindex_fails_closed_during_cancelled_extraction(settling_memory, services):
    memory, control = settling_memory
    memory.enqueue('evidence-1', evidence(services))
    capture = asyncio.create_task(memory.process_pending())
    try:
        assert await asyncio.to_thread(control.entered.wait, 3)
        capture.cancel()
        with pytest.raises(asyncio.CancelledError):
            await capture
        with pytest.raises(ApiError) as caught:
            await asyncio.wait_for(asyncio.to_thread(memory.reindex), .5)
        assert caught.value.code == 'recovery_busy'
        assert caught.value.retryable
        control.release.set()
        assert await asyncio.to_thread(control.finalizing.wait, 3)
        with pytest.raises(ApiError) as finalizing:
            memory.reindex()
        assert finalizing.value.code == 'recovery_busy'
    finally:
        control.release.set()
        control.finish.set()
        await asyncio.gather(capture, return_exceptions=True)


@pytest.mark.asyncio
async def test_cancelled_capture_keeps_recovery_blocked_through_extractor_cleanup(settling_memory, services):
    memory, control = settling_memory
    memory.enqueue('evidence-1', evidence(services))
    capture = asyncio.create_task(memory.process_pending())
    try:
        assert await asyncio.to_thread(control.entered.wait, 3)
        capture.cancel()
        with pytest.raises(asyncio.CancelledError):
            await capture
        assert control.cancel_requested.is_set()
        recovery_is_busy(memory)
        control.release.set()
        assert await asyncio.to_thread(control.finalizing.wait, 3)
        recovery_is_busy(memory)
    finally:
        control.release.set()
        control.finish.set()
        await asyncio.gather(capture, return_exceptions=True)
    await memory.close()
    with memory.recovery_guard():
        assert memory.repository.list() == []


@pytest.mark.asyncio
async def test_close_keeps_event_loop_available_to_engine_finalizers(settling_memory):
    memory, control = settling_memory
    control.close_needs_reply = True
    await memory.close(timeout=3)
    assert control.close_reply.is_set()
    with memory.recovery_guard():
        assert memory.repository.list() == []


@pytest.mark.asyncio
async def test_close_seals_capture_admission_while_draining(settling_memory, services):
    memory, control = settling_memory
    memory.enqueue('evidence-1', evidence(services))
    await memory.start()
    closing = None
    try:
        assert await asyncio.to_thread(control.entered.wait, 3)
        closing = asyncio.create_task(memory.close())
        await asyncio.wait_for(control.cancel_requested.wait(), 3)
        assert not closing.done()
        scope = evidence(services, 'evidence-2')
        with pytest.raises(ApiError) as caught:
            memory.enqueue('evidence-2', scope)
        assert caught.value.code == 'memory_stopping'
        assert len(memory.repository.jobs()) == 1
    finally:
        control.release.set()
        control.finish.set()
        if closing:
            await closing
    assert memory.repository.list() == []


@pytest.mark.asyncio
async def test_application_shutdown_defers_cancellation_until_thread_finalizers_settle(settling_memory, services):
    memory, control = settling_memory
    memory.enqueue('evidence-1', evidence(services))
    control.close_needs_reply = True
    await memory.start()
    shutdown = None
    try:
        assert await asyncio.to_thread(control.entered.wait, 3)
        shutdown = asyncio.create_task(memory.shutdown())
        await asyncio.wait_for(control.cancel_requested.wait(), 1)
        shutdown.cancel()
        done, _ = await asyncio.wait({shutdown}, timeout=.05)
        assert not done, 'Cancelled teardown released its application owner before settlement'
        recovery_is_busy(memory)
    finally:
        control.release.set()
        control.finish.set()
        if shutdown:
            await asyncio.gather(shutdown, return_exceptions=True)
    assert not shutdown.cancelled()
    assert control.close_reply.is_set()
    assert memory.repository.list() == []


@pytest.mark.asyncio
async def test_close_cancels_a_public_retry_and_drains_before_returning(settling_memory, services):
    memory, control = settling_memory
    memory.enqueue('evidence-1', evidence(services))
    capture = asyncio.create_task(memory.process_pending(retry=True))
    closing = None
    try:
        assert await asyncio.to_thread(control.entered.wait, 3)
        closing = asyncio.create_task(memory.close())
        await asyncio.wait_for(control.cancel_requested.wait(), 1)
        control.release.set()
        assert await asyncio.to_thread(control.finalizing.wait, 3)
        assert not closing.done()
        recovery_is_busy(memory)
    finally:
        control.release.set()
        control.finish.set()
        if closing:
            await closing
        await asyncio.gather(capture, return_exceptions=True)
    assert capture.cancelled()
    with memory.recovery_guard():
        assert memory.repository.list() == []


@pytest.mark.asyncio
async def test_observer_timeout_does_not_cancel_settlement(settling_memory, services):
    memory, control = settling_memory
    memory.enqueue('evidence-1', evidence(services))
    await memory.start()
    try:
        assert await asyncio.to_thread(control.entered.wait, 3)
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(memory.close(), .05)
        recovery_is_busy(memory)
        control.release.set()
        assert await asyncio.to_thread(control.finalizing.wait, 3)
        recovery_is_busy(memory)
    finally:
        control.release.set()
        control.finish.set()
    # Retrying close must observe real settlement, even after its first observer
    # stopped waiting. In particular, no cancelled lease may masquerade as done.
    await asyncio.wait_for(memory.close(), 3)
    with memory.recovery_guard():
        assert memory.repository.list() == []


@pytest.mark.asyncio
async def test_close_timeout_reports_unsettled_work_and_retry_drains_it(settling_memory, services):
    memory, control = settling_memory
    memory.enqueue('evidence-1', evidence(services))
    await memory.start()
    try:
        assert await asyncio.to_thread(control.entered.wait, 3)
        with pytest.raises(ApiError) as caught:
            await asyncio.wait_for(memory.close(timeout=.05), 1)
        assert caught.value.code == 'memory_close_timeout'
        assert not control.settled.is_set()
        recovery_is_busy(memory)
        control.release.set()
        assert await asyncio.to_thread(control.finalizing.wait, 3)
        with pytest.raises(ApiError) as caught:
            await asyncio.wait_for(memory.close(timeout=.05), 1)
        assert caught.value.code == 'memory_close_timeout'
        recovery_is_busy(memory)
    finally:
        control.release.set()
        control.finish.set()
    await memory.close(timeout=3)
    with memory.recovery_guard():
        assert memory.repository.list() == []


@pytest.mark.asyncio
async def test_cancelled_rebuild_keeps_recovery_blocked_until_the_thread_settles(settling_memory):
    memory, control = settling_memory
    memory.add(ManualFact(text='Synthetic CKD learning preference.',
        idempotency_key='index-1', scope=ContextScope(kind=Scope.STUDY)))
    control.pause_index = True
    processing = asyncio.create_task(memory.process_pending())
    try:
        assert await asyncio.to_thread(control.index_entered.wait, 3)
        processing.cancel()
        with pytest.raises(asyncio.CancelledError):
            await processing
        recovery_is_busy(memory)
    finally:
        control.index_release.set()
        await asyncio.gather(processing, return_exceptions=True)
    await memory.close()
    with memory.recovery_guard():
        assert len(memory.repository.list()) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('operation', ['start', 'retry', 'reindex', 'retrieve'])
async def test_closed_memory_refuses_new_worker_and_engine_use(settling_memory, operation):
    memory, control = settling_memory
    await memory.close()
    with pytest.raises(ApiError) as caught:
        if operation == 'start':
            await memory.start()
        elif operation == 'retry':
            await memory.process_pending(retry=True)
        elif operation == 'reindex':
            memory.reindex()
        else:
            memory.retrieve('dialysis', scope=ContextScope(kind=Scope.STUDY))
    assert caught.value.code == 'memory_stopping'


@pytest.mark.asyncio
async def test_cancelled_caller_revokes_further_extractor_provider_work(settling_memory, services):
    memory, control = settling_memory
    memory.enqueue('evidence-1', evidence(services))
    capture = asyncio.create_task(memory.process_pending())
    try:
        assert await asyncio.to_thread(control.entered.wait, 3)
        capture.cancel()
        with pytest.raises(asyncio.CancelledError):
            await capture
        control.release.set()
        assert await asyncio.to_thread(control.finalizing.wait, 3)
        # The real ApprovedLLM consults this binding before another request.
        assert control.provider_admission == [False]
    finally:
        control.release.set()
        control.finish.set()
        await asyncio.gather(capture, return_exceptions=True)
    await memory.close()


@pytest.mark.asyncio
async def test_retry_waits_for_the_previous_cancelled_extractor_to_settle(settling_memory, services):
    memory, control = settling_memory
    memory.enqueue('evidence-1', evidence(services))
    capture = asyncio.create_task(memory.process_pending())
    try:
        assert await asyncio.to_thread(control.entered.wait, 3)
        capture.cancel()
        with pytest.raises(asyncio.CancelledError):
            await capture
        following = memory.enqueue('evidence-2', evidence(services, 'evidence-2'))
        assert await asyncio.wait_for(memory.process_pending(retry=True), .1) == {'processed': 0}
        assert memory.repository.job(following['id'])['state'] == 'queued'
        assert memory.repository.job(following['id'])['attempts'] == 0
    finally:
        control.release.set()
        control.finish.set()
        await asyncio.gather(capture, return_exceptions=True)
    await memory.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('stop', [False, True], ids=['normal-completion', 'public-stop'])
async def test_capture_publishes_only_after_settlement_and_only_if_not_stopped(settling_memory, services, stop):
    memory, control = settling_memory
    job = memory.enqueue('evidence-1', evidence(services))
    capture = asyncio.create_task(memory.process_pending())
    try:
        assert await asyncio.to_thread(control.entered.wait, 3)
        if stop:
            assert (await memory.cancel(job['id']))['state'] == 'cancelled'
        control.release.set()
        assert await asyncio.to_thread(control.finalizing.wait, 3)
        recovery_is_busy(memory)
        assert memory.repository.list() == []
        assert not capture.done()
    finally:
        control.release.set()
        control.finish.set()
    assert await capture == {'processed': 0 if stop else 1}
    if not stop:
        assert (await memory.cancel(job['id']))['state'] == 'completed'
    with memory.recovery_guard():
        if stop:
            assert memory.repository.job(job['id'])['state'] == 'cancelled'
            assert memory.repository.list() == []
        else:
            assert [record['text'] for record in memory.repository.list()] == [
                'Synthetic learning point: compare dialysis modalities.']


@pytest.mark.asyncio
async def test_application_shutdown_keeps_reply_capacity_after_a_bounded_close_timeout(settling_memory, services):
    memory, control = settling_memory
    memory.enqueue('evidence-1', evidence(services))
    downstream_released = asyncio.Event()

    async def release_downstream():
        downstream_released.set()

    services.on_shutdown.insert(0, release_downstream)

    async def teardown():
        for callback in reversed(services.on_shutdown):
            await callback()

    await services.on_startup[0]()
    shutdown = None
    try:
        assert await asyncio.to_thread(control.entered.wait, 3)
        with pytest.raises(ApiError) as caught:
            await memory.close(timeout=.05)
        assert caught.value.code == 'memory_close_timeout'
        shutdown = asyncio.create_task(teardown())
        done, _ = await asyncio.wait({shutdown}, timeout=5.1)
        assert not done, 'Application teardown escaped while extraction still owned the profile'
        assert not downstream_released.is_set()
        recovery_is_busy(memory)
    finally:
        control.release.set()
        control.finish.set()
        if shutdown:
            await asyncio.gather(shutdown, return_exceptions=True)
    assert shutdown.result() is None
    assert downstream_released.is_set()
    assert memory.repository.list() == []
