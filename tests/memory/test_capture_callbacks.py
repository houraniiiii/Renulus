"""Public migrated capture callbacks; canonical receipts and no provider IO."""
import asyncio
from dataclasses import FrozenInstanceError
from contextlib import contextmanager
import json
import threading
from types import SimpleNamespace

import pytest
from renulus.contracts import ApiError
from renulus.design_c_contracts import Dependency, EligibleInput, Identity

from .test_native_answer_lineage import native_receipt, stage_and_publish, finalize
from .test_study_answer_capture import study_capture
from .conftest import evidence


@pytest.fixture
async def committed_capture(native_receipt, services, request, monkeypatch):
    _, memory, control, run, reference, evidence_id, scope = native_receipt
    if getattr(request, 'param', None) in ('held-cpu', 'failed-cpu'):
        from renulus.memory.engine import Mem0Index
        from renulus.memory.service import MemoryService
        control.cpu_entered, control.cpu_done = threading.Event(), threading.Event()
        fail_cpu = request.param == 'failed-cpu'
        if fail_cpu:
            control.cpu_done.set()
            control.expect_unsettled = True
        class HeldIndex(Mem0Index):
            def close(self):
                if self.transient:
                    control.cpu_entered.set()
                    assert control.cpu_done.wait(10), 'Test did not release CPU finalization'
                super().close()
                if self.transient and fail_cpu:
                    raise ApiError('synthetic_cpu_cleanup_unknown', 'PRIVATE_CPU_CLEANUP_TEXT', 503)
        embedding = memory._get_embedding  # Reuse the fixture's controlled vector boundary.
        await memory.close()
        memory = MemoryService(services, index_factory=HeldIndex)
        monkeypatch.setattr(memory, '_get_embedding', embedding)
        services.registry['memory'] = memory
    if getattr(request, 'param', None) == 'supported':
        from renulus.memory.models import ManualFact
        control.root = memory.add(ManualFact(text='Synthetic retained learner preference.',
            scope=scope, idempotency_key='callback-support'))
        reference['inputs'] = [EligibleInput(kind='memory', dependency=Dependency(
            target=Identity(type='memory_revision', id=control.root['id'] + ':1'),
            expected_revision='1')).model_dump(mode='json')]
        # The dedicated synthetic producer declares its exact source inputs
        # before the public staged-publication seam; no lineage state is forged.
        with services.db.transaction() as conn:
            payload = json.loads(conn.execute('SELECT payload_json FROM learning_evidence WHERE id=?',
                (evidence_id,)).fetchone()[0])
            payload['answer_reference'] = reference
            conn.execute('UPDATE learning_evidence SET payload_json=? WHERE id=?',
                (json.dumps(payload), evidence_id))
    with services.db.transaction() as conn:
        publication = stage_and_publish(conn, memory, run, reference, evidence_id)
        finalize(conn, run, publication)

    class Resolver:
        async def resolve_completed_answer(self, supplied):
            assert supplied == reference
            return {"text": control.answer, "digest": reference["sha256"],
                "publication_digest": publication,
                "input": {"version": 1, "inputs": reference['inputs'], "dependencies": []}}

    services.registry["completed_answer_resolver"] = Resolver()
    try:
        yield memory, control, evidence_id, scope, publication
    finally:
        if hasattr(control, 'cpu_done'):
            control.cpu_done.set()
        if getattr(control, 'expect_unsettled', False):
            with pytest.raises(ApiError) as pending:
                await memory.close()
            assert pending.value.code == 'memory_settlement_pending'
        else:
            await memory.close()


@pytest.mark.asyncio
async def test_native_answer_requires_trusted_extractor_without_provider_fallback(committed_capture):
    memory, control, evidence_id, scope, _ = committed_capture
    queued = memory.enqueue(evidence_id, scope)
    await memory.process_pending()
    job = memory.repository.job(queued["id"])
    assert job["state"] == "failed"
    assert job["error_code"] == "memory_generation_not_scoped"
    assert not [call for call in control.calls if call["purpose"] == "memory-extraction"]


@pytest.fixture
def callback(committed_capture):
    from renulus.memory.capture import CaptureBinding
    memory, _, _, _, _ = committed_capture
    control = SimpleNamespace(requests=[], currents=[], generated=[], cancelled=0, released=0,
        entered=asyncio.Event(), generation_done=asyncio.Event(), cancellation=asyncio.Event(),
        settling=asyncio.Event(), transport_done=asyncio.Event(),
        hold_generation=False, hold_transport=False, error=None, publication_error=None,
        guard_result=None, settlement_error=None, release_error=None, cancel_error=None,
        output='{"memory":[{"text":"Synthetic native learning fact."}]}')

    def prepare(request, *, current):
        control.requests.append(request)
        control.currents.append(current)
        async def generate(messages):
            control.generated.append(messages)
            current()
            control.entered.set()
            if control.hold_generation:
                await control.generation_done.wait()
            if control.error is not None:
                raise control.error
            return control.output
        def check(*, conn=None):
            current(conn=conn)
            return control.guard_result
        def publication(conn):
            current(conn=conn)
            if control.publication_error is not None:
                raise control.publication_error
        def cancel():
            control.cancelled += 1
            control.cancellation.set()
            if control.cancel_error is not None:
                raise control.cancel_error
        async def settle():
            control.settling.set()
            if control.hold_transport:
                await control.transport_done.wait()
            if control.settlement_error is not None:
                raise control.settlement_error
        def release():
            assert memory.repository.job(request.job_id)['state'] != 'running'
            if control.release_error is not None:
                raise control.release_error
            control.released += 1
        return CaptureBinding(generate=generate, current=check,
            require_publication_in=publication, cancel=cancel, settle=settle, release=release)

    memory.bind_committed_answer_extractor(prepare)
    return control


@pytest.mark.asyncio
async def test_cancelled_observer_retains_generation_and_transport_until_close_drains(
        committed_capture, callback):
    memory, _, evidence_id, scope, _ = committed_capture
    callback.hold_generation = callback.hold_transport = True
    job = memory.enqueue(evidence_id, scope)
    observer = asyncio.create_task(memory.process_pending())
    try:
        await asyncio.wait_for(callback.entered.wait(), 3)
        observer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await observer
        assert callback.cancelled == 1
        assert callback.released == 0
        with pytest.raises(ApiError) as stopped:
            callback.currents[0]()
        assert stopped.value.code == 'memory_capture_cancelled'
        callback.generation_done.set()
        await asyncio.wait_for(callback.settling.wait(), 3)
        assert await memory.process_pending(retry=True) == {'processed': 0}
        with pytest.raises(ApiError) as busy:
            with memory.recovery_guard():
                pass
        assert busy.value.code == 'recovery_busy'
        with pytest.raises(ApiError) as pending:
            await memory.close(timeout=0.01)
        assert pending.value.code == 'memory_close_timeout'
        assert callback.released == 0
        callback.transport_done.set()
        await memory.close()
        assert callback.cancelled == callback.released == 1
        assert memory.repository.job(job['id'])['state'] != 'completed'
        assert memory.repository.list() == []
        with memory.recovery_guard():
            pass
    finally:
        callback.generation_done.set()
        callback.transport_done.set()
        await asyncio.gather(observer, return_exceptions=True)


@pytest.mark.asyncio
async def test_async_factory_is_rejected_before_outbox_admission(committed_capture):
    memory, _, _, _, _ = committed_capture
    async def prepare(request, *, current):
        raise AssertionError('Async factory must never execute')
    with pytest.raises(ApiError) as denied:
        memory.bind_committed_answer_extractor(prepare)
    assert denied.value.code == 'memory_generation_not_scoped'


@pytest.mark.asyncio
async def test_factory_cannot_be_bound_after_capture_has_started(committed_capture):
    memory, _, _, _, _ = committed_capture
    await memory.process_pending()
    with pytest.raises(ApiError) as denied:
        memory.bind_committed_answer_extractor(lambda request, *, current: None)
    assert denied.value.code == 'memory_extractor_bound'


@pytest.mark.asyncio
async def test_commit_guard_requires_local_none_or_raise_and_rolls_back(committed_capture):
    memory, _, evidence_id, scope, _ = committed_capture
    job = memory.repository.claim(memory.enqueue(evidence_id, scope)['id'])
    material = await memory.resolve_material(job)
    with pytest.raises(ApiError) as denied:
        memory.repository.commit_capture(job, material, ['Untrusted guard must not publish.'],
            publication_guard=lambda conn: False)
    assert denied.value.code == 'memory_generation_not_scoped'
    assert memory.repository.job(job['id'])['state'] == 'running'
    assert memory.repository.list() == []


@pytest.mark.asyncio
@pytest.mark.parametrize('committed_capture', ['supported'], indirect=True)
async def test_support_edit_signals_native_binding_without_legacy_provider_cancel(
        committed_capture, callback):
    memory, control, evidence_id, scope, _ = committed_capture
    callback.hold_generation = True
    job = memory.enqueue(evidence_id, scope)
    observer = asyncio.create_task(memory.process_pending())
    try:
        await asyncio.wait_for(callback.entered.wait(), 3)
        memory.edit(control.root['id'], 'Corrected retained learner preference.', 1)
        await asyncio.wait_for(callback.cancellation.wait(), 3)
        assert callback.cancelled == 1
        assert job['id'] not in control.cancelled
        assert callback.released == 0
        callback.generation_done.set()
        assert await observer == {'processed': 0}
        assert callback.released == 1
        assert memory.repository.job(job['id'])['state'] == 'cancelled'
        assert [row['text'] for row in memory.repository.list()] == ['Corrected retained learner preference.']
    finally:
        callback.generation_done.set()
        await asyncio.gather(observer, return_exceptions=True)
    await memory.cancel(job['id'])


@pytest.mark.asyncio
async def test_non_none_current_denies_generation_and_settles_the_binding(committed_capture, callback):
    memory, _, evidence_id, scope, _ = committed_capture
    callback.guard_result = True
    job = memory.enqueue(evidence_id, scope)
    assert await memory.process_pending() == {'processed': 0}
    assert callback.generated == [] and callback.released == 1
    assert memory.repository.job(job['id'])['error_code'] == 'memory_generation_not_scoped'
    assert memory.repository.list() == []


@pytest.mark.asyncio
@pytest.mark.parametrize('committed_capture', ['failed-cpu'], indirect=True)
async def test_cpu_finalizer_failure_is_not_permission_to_release_or_recover(committed_capture, callback):
    memory, _, evidence_id, scope, _ = committed_capture
    memory.enqueue(evidence_id, scope)
    assert await memory.process_pending() == {'processed': 0}
    assert callback.settling.is_set()
    assert callback.released == 0
    assert memory.repository.list() == []
    with pytest.raises(ApiError) as busy:
        with memory.recovery_guard():
            pass
    assert busy.value.code == 'recovery_busy'


@pytest.mark.asyncio
@pytest.mark.parametrize('output', [None, 'not-json', '{"memory":"not-a-list"}',
    json.dumps({'memory': [{'text': 'fact'}] * 13}),
    json.dumps({'memory': [{'text': 'x' * 2001}]}),
    json.dumps({'memory': [{'text': 'fact'}], 'unneeded': 'x' * 16000})])
async def test_native_output_preserves_existing_json_budgets(committed_capture, callback, output):
    memory, _, evidence_id, scope, _ = committed_capture
    callback.output = output
    job = memory.enqueue(evidence_id, scope)
    assert await memory.process_pending() == {'processed': 0}
    assert len(callback.generated) == callback.released == 1
    assert memory.repository.job(job['id'])['error_code'] == 'memory_extraction_invalid'
    assert memory.repository.list() == []


@pytest.mark.asyncio
@pytest.mark.parametrize('phase', ['settle', 'release'])
async def test_unproven_finalizer_keeps_recovery_retry_and_dependency_shutdown_closed(
        committed_capture, callback, services, phase):
    memory, control, evidence_id, scope, _ = committed_capture
    control.expect_unsettled = True
    error = ApiError('synthetic_transport_unknown', 'PRIVATE_FINALIZER_TEXT_MUST_NOT_LEAK', 503)
    if phase == 'settle':
        callback.settlement_error = error
    else:
        callback.release_error = error
    dependencies = []
    services.on_shutdown.append(memory.shutdown)
    services.on_shutdown_dependencies.append(lambda: dependencies.append(True))
    memory.enqueue(evidence_id, scope)
    later = memory.enqueue('after-unproven', evidence(services, 'after-unproven'))
    assert await memory.process_pending() == {'processed': 0}
    assert callback.released == 0
    assert memory.repository.job(later['id'])['state'] == 'queued'
    assert await memory.process_pending(retry=True) == {'processed': 0}
    assert len(callback.requests) == 1
    with pytest.raises(ApiError) as busy:
        with memory.recovery_guard():
            pass
    assert busy.value.code == 'recovery_busy'
    with pytest.raises(ApiError) as pending:
        await memory.close()
    assert pending.value.code == 'memory_settlement_pending'
    with pytest.raises(ApiError) as failed:
        await services.shutdown()
    assert failed.value.code == 'runtime_shutdown_failed'
    assert dependencies == []


@pytest.mark.asyncio
@pytest.mark.parametrize('where', ['generation', 'publication'])
async def test_trusted_failure_code_survives_mem0_wrapper_and_retry_uses_new_attempt(
        committed_capture, callback, caplog, where):
    memory, legacy, evidence_id, scope, _ = committed_capture
    error = ApiError('synthetic_configuration_stale', 'PRIVATE_FAILURE_TEXT_MUST_NOT_LEAK', 409)
    if where == 'generation':
        callback.error = error
    else:
        callback.publication_error = error
    job = memory.enqueue(evidence_id, scope)
    assert await memory.process_pending() == {'processed': 0}
    failed = memory.repository.job(job['id'])
    assert failed['state'] == 'failed' and failed['error_code'] == error.code
    assert memory.repository.list() == []
    assert callback.cancelled == callback.released == 1
    assert 'PRIVATE_FAILURE_TEXT_MUST_NOT_LEAK' not in caplog.text
    callback.error = callback.publication_error = None
    assert await memory.process_pending(retry=True) == {'processed': 1}
    assert [request.attempt for request in callback.requests] == [1, 2]
    assert {request.fingerprint for request in callback.requests} == {job['evidence_hash']}
    assert len(callback.generated) == callback.released == 2
    assert not [call for call in legacy.calls if call['purpose'] == 'memory-extraction']


@pytest.mark.asyncio
async def test_settled_cleanup_signal_error_does_not_replace_publication_failure(committed_capture, callback):
    memory, _, evidence_id, scope, _ = committed_capture
    callback.publication_error = ApiError('synthetic_publication_stale', 'PRIVATE_PUBLICATION_TEXT', 409)
    callback.cancel_error = ApiError('synthetic_cancel_signal_failed', 'PRIVATE_CANCEL_TEXT', 503)
    job = memory.enqueue(evidence_id, scope)
    assert await memory.process_pending() == {'processed': 0}
    assert callback.settling.is_set() and callback.released == 1
    assert memory.repository.job(job['id'])['error_code'] == 'synthetic_publication_stale'
    assert memory.repository.list() == []


@pytest.mark.asyncio
@pytest.mark.parametrize('committed_capture', ['held-cpu'], indirect=True)
@pytest.mark.parametrize('stop', ['cancel', 'observer', 'services'])
async def test_cpu_cleanup_and_loop_finalizer_both_precede_release_and_dependency_shutdown(
        committed_capture, callback, services, stop):
    memory, cpu, evidence_id, scope, _ = committed_capture
    callback.hold_transport = True
    dependency_closed = []
    services.on_shutdown.append(memory.shutdown)
    services.on_shutdown_dependencies.append(lambda: dependency_closed.append(True))
    job = memory.enqueue(evidence_id, scope)
    observer = asyncio.create_task(memory.process_pending())
    try:
        assert await asyncio.to_thread(cpu.cpu_entered.wait, 3)
        if stop == 'cancel':
            assert (await memory.cancel(job['id']))['state'] == 'cancelled'
        elif stop == 'observer':
            observer.cancel()
            with pytest.raises(asyncio.CancelledError):
                await observer
        else:
            with pytest.raises(ApiError) as pending:
                await services.shutdown(timeout=0.01)
            assert pending.value.code == 'runtime_shutdown_pending'
        assert callback.released == 0 and not callback.settling.is_set()
        assert not dependency_closed
        with pytest.raises(ApiError) as pending:
            await memory.close(timeout=0.01)
        assert pending.value.code == 'memory_close_timeout'
        cpu.cpu_done.set()
        await asyncio.wait_for(callback.settling.wait(), 3)
        assert callback.released == 0 and not dependency_closed
        with pytest.raises(ApiError) as busy:
            with memory.recovery_guard():
                pass
        assert busy.value.code == 'recovery_busy'
        callback.transport_done.set()
        await services.shutdown(timeout=3)
        assert callback.released == callback.cancelled == 1
        assert dependency_closed == [True]
        assert memory.repository.list() == []
        assert memory.repository.job(job['id'])['state'] != 'completed'
    finally:
        cpu.cpu_done.set()
        callback.transport_done.set()
        await asyncio.gather(observer, return_exceptions=True)


@pytest.mark.asyncio
async def test_native_factory_uses_exact_frozen_pin_and_same_commit_connection(committed_capture, monkeypatch):
    memory, control, evidence_id, scope, publication = committed_capture
    loop = asyncio.get_running_loop()
    events, requests, generated = [], [], []
    pin = EligibleInput(kind="committed_evidence", dependency=Dependency(
        target=Identity(type="learning_evidence", id=evidence_id), expected_revision=publication))

    def prepare(request, *, current):
        from renulus.memory.capture import CaptureBinding
        assert asyncio.get_running_loop() is loop
        assert request.input == pin and request.attempt == 1
        assert request.scope_json == scope.model_dump_json() and request.project_id is None
        with pytest.raises(FrozenInstanceError):
            request.attempt = 2
        requests.append(request)
        events.append("prepare")
        def check(*, conn=None):
            current(conn=conn)
        async def generate(messages):
            assert asyncio.get_running_loop() is loop
            check()
            assert type(messages) is tuple and all(type(message) is tuple for message in messages)
            assert tuple(message[0] for message in messages) == ("system", "user")
            assert control.answer in messages[1][1]
            generated.append(messages)
            events.append("generate")
            return json.dumps({"memory": [{"text": "Synthetic native CKD learning point."}]})
        def publication_guard(conn):
            assert conn.in_transaction
            check(conn=conn)
            memory.check_answer_inputs_in(conn, inputs=(pin,))
            assert conn.execute("SELECT state FROM memory_jobs WHERE id=?",
                (request.job_id,)).fetchone()[0] == "running"
            events.append("publication")
        async def settle():
            events.append("settle")
        def release():
            assert memory.repository.job(request.job_id)["state"] == "completed"
            events.append("release")
        return CaptureBinding(generate=generate, current=check,
            require_publication_in=publication_guard, cancel=lambda: events.append("cancel"),
            settle=settle, release=release)

    memory.bind_committed_answer_extractor(prepare)
    transaction = memory.db.transaction
    @contextmanager
    def single_connection():
        with transaction() as conn:
            with monkeypatch.context() as guard:
                def nested_connection():
                    raise AssertionError('A local capture check opened a second connection inside its writer')
                guard.setattr(memory.db, 'connect', nested_connection)
                yield conn
    monkeypatch.setattr(memory.db, 'transaction', single_connection)
    queued = memory.enqueue(evidence_id, scope)
    assert await memory.process_pending() == {"processed": 1}
    assert requests[0].job_id == queued["id"]
    assert requests[0].fingerprint == queued["evidence_hash"]
    assert len(generated) == 1
    assert events == ["prepare", "generate", "settle", "publication", "release"]
    assert memory.repository.job(queued["id"])["state"] == "completed"
    assert any(row["text"] == "Synthetic native CKD learning point." for row in memory.repository.list())
    assert not [call for call in control.calls if call["purpose"] == "memory-extraction"]
