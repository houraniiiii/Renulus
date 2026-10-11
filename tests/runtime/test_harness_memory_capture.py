"""Canonical capture ownership. Source callbacks here are explicitly synthetic."""
from pathlib import Path
import asyncio
import base64
import json
from uuid import uuid4

import httpx

import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.design_c_contracts import Dependency, EligibleInput, Identity
from renulus.memory.capture import CommittedCapture
from renulus.runtime.harness_configuration import (
    CandidateHealth, ConfigurationAuthority, ConfigurationSpec, ConnectionReference,
    RestartBoundary, RolePolicy, RouteLimits,
)
from renulus.runtime.harness_deployment import DeploymentEvidence
from renulus.runtime.harness_domain import DomainBinding, DomainCancellation, DomainRequest
from renulus.runtime.harness_gateway import GatewayBounds
from renulus.runtime.harness_learning import HarnessLearningOwner
from renulus.runtime.harness_model_registry import HarnessModelRegistry, ModelRegistryBounds
from renulus.runtime.harness_process import HarnessProcessConfig, ManagedHarnessProcess
from renulus.server import create_app


SOURCE = Path(__file__).resolve().parents[2]
NODE = Path('C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe')


@pytest.fixture
async def capture_owner(tmp_path):
    services = create_app(tmp_path / 'profile', source_root=SOURCE, provider_http_transport=
        httpx.MockTransport(lambda request: httpx.Response(200, json={'data': [{'id': 'mimo-v2.6-pro'}]}))).state.services
    manager = services.get('provider')
    await manager.connect_go('synthetic-capture-account', select=True)
    manager.select('opencode-go', 'mimo-v2.6-pro')
    route = await manager.prepare_harness_route()
    authority = ConfigurationAuthority(services.db)
    spec = ConfigurationSpec(connection=ConnectionReference(provider=route.provider_id,
        credential_reference=route.credential_ref, credential_revision=route.credential_epoch,
        selected_model=route.catalog_model_id), registry_hash='a' * 64, capabilities=('text',),
        roles=(RolePolicy(purpose='memory-extraction', output_tokens=32, dispatch_limit=1),))
    version = authority.stage(spec)
    assert authority.validate(version, lambda candidate: CandidateHealth(
        configuration_version=candidate.version, grant_epoch=candidate.grant_epoch,
        registry_hash=spec.registry_hash))
    authority.activate(version, RestartBoundary(admission_closed=True, runtime_stopped=True,
        domain_settled=True), expected_effective=None)
    authority.open_admission(version, registry_hash=spec.registry_hash, grant_epoch=0)
    config = HarnessProcessConfig(node_executable=NODE, host_entry=SOURCE / 'packages/harness/src/main.mjs',
        profile_root=services.paths.root, profile_id='synthetic-capture-owner',
        store_id='synthetic-capture-runtime', domain_store_id='synthetic-capture-domain',
        domain_path='state/renulus.sqlite3')
    async def counter(body, manifest):
        return 20  # Explicit synthetic inclusive evidence.
    sse = 'data: ' + json.dumps({'choices': [{'delta': {'content': 'Synthetic fact'}}]}) + chr(10)*2 + 'data: [DONE]' + chr(10)*2
    evidence = DeploymentEvidence('synthetic-capture-evidence', route,
        RouteLimits(input_tokens=100, output_tokens=32, window_tokens=150), ('text',),
        'synthetic-limits', 'synthetic-caps', 'synthetic-counter', counter)
    def factory(resolve_run):
        return HarnessModelRegistry(manager, authority, resolve_run=resolve_run, evidence=lambda route: evidence,
            http_transport=lambda route: httpx.MockTransport(lambda request: httpx.Response(200,
                headers={'content-type': 'text/event-stream'}, content=sse.encode())),
            gateway_bounds=GatewayBounds(max_request_bytes=8192, max_response_bytes=8192, timeout_seconds=2),
            bounds=ModelRegistryBounds(max_runs=2, max_plans_per_run=1, max_owned=1,
                max_retained_bytes=200000, max_manifest_bytes=32768, max_frame_bytes=65536))
    owner = HarnessLearningOwner(services, config, configuration_id=version,
        configuration_authority=authority, memory=services.get('memory'), model_registry_factory=factory)
    yield owner, authority, version
    # A broken cleanup regression must produce a bounded red receipt. It may
    # not pretend settlement or tear down dependencies while the owner is held.
    await asyncio.wait_for(owner.close(), 1)
    await services.get('memory').close()
    services.get('helpers').startup.close()
    await manager.close()


def source():
    return CommittedCapture(job_id='synthetic-claimed-job', attempt=1, fingerprint='synthetic-fingerprint',
        scope_json=ContextScope(kind=Scope.STUDY, entity_id='synthetic-thread').model_dump_json(),
        project_id=None, input=EligibleInput(kind='committed_evidence', dependency=Dependency(
            target=Identity(type='learning_evidence', id='learn-answer:synthetic-completed-run'),
            expected_revision='b' * 64)))


async def test_prepared_capture_blocks_configuration_replacement_until_cpu_owner_releases(capture_owner):
    owner, authority, version = capture_owner
    capture = owner.memory_captures.prepare(source(), current=lambda *, conn=None: None)
    with pytest.raises(ApiError) as refused:
        owner.seal_new_runs(expected_effective=version)
    assert refused.value.code == 'harness_configuration_busy'
    assert authority.activation_snapshot()['pinned_runs'] == []  # No generation yet.
    await capture.settle()
    # Native settlement cannot release the CPU owner's interval before commit.
    with pytest.raises(ApiError) as still_owned:
        owner.seal_new_runs(expected_effective=version)
    assert still_owned.value.code == 'harness_configuration_busy'
    capture.release()
    seal = owner.seal_new_runs(expected_effective=version)
    seal.release()


class ScriptedExtractionProcess(ManagedHarnessProcess):
    """Only the native process seam is scripted; canonical dispatch is real."""
    def __init__(self, owner):
        super().__init__(domain_authority=owner.authorize)
        self.owner = owner
        self.commands = []
        self.completed = False

    async def release_observation(self, request_id):
        return True  # This public process seam has no actual IPC receipt store.

    async def request(self, command, payload, operation_id, attempt_id, timeout):
        self.commands.append(command)
        if command == 'model.extract':
            binding = DomainBinding(**payload['binding'])
            async def invoke(name, arguments):
                request = DomainRequest(uuid4().hex, binding, name, arguments)
                grant = await self.owner.authorize(request)
                assert grant is not None and grant.check_current()
                return await grant.handler(request, DomainCancellation())
            plan = await invoke('model.prepare', {})
            await invoke('model.manifest', {'manifest': {'version': 1, 'system': payload['system'],
                'messages': [{'role': 'user', 'content': [{'type': 'text', 'text': payload['user']}]}], 'tools': []}})
            body = json.dumps({'model': 'mimo-v2.6-pro', 'stream': True, 'max_completion_tokens': 32,
                'messages': [{'role': 'system', 'content': payload['system']},
                    {'role': 'user', 'content': payload['user']}]}).encode()
            result = await invoke('model.dispatch', {'dispatch_id': plan['dispatch_id'],
                'serialized_request': {'method': 'POST', 'url': plan['route']['endpoint'],
                    'headers': {'content-type': 'application/json'},
                    'body_base64': base64.b64encode(body).decode()}})
            self.completed = True
            result = {'text': 'Synthetic fact', 'receipt': {'dispatch_id': plan['dispatch_id'], 'permit_id': result['permit_id']}}
        elif command == 'model.extract.status':
            result = {'state': 'settled' if self.completed else 'active'}
        elif command == 'model.extract.release':
            assert self.completed
            result = {'released': True}
        else:
            raise AssertionError(command)
        return {'outcome': 'committed_reference', 'request_id': uuid4().hex, 'result': result}


async def test_stateless_capture_publishes_only_consumed_permit_then_releases_canonical_pin(capture_owner):
    owner, authority, version = capture_owner
    process = ScriptedExtractionProcess(owner)
    seal = owner.seal_new_runs(expected_effective=version)
    owner.replace_process(process, configuration_id=version, seal=seal)
    seal.release()
    supplied = []
    def current(*, conn=None):
        supplied.append(conn)
    capture = owner.memory_captures.prepare(source(), current=current)
    try:
        assert await capture.generate((('system', 'Extract eligible facts.'), ('user', 'Synthetic learning answer.'))) == 'Synthetic fact'
        pins = authority.activation_snapshot()['pinned_runs']
        assert len(pins) == 1 and pins[0]['purpose'] == 'memory-extraction'
        run_id = pins[0]['run_id']
        assert authority.run(run_id)['spent_dispatches'] == 1
        await capture.settle()
        with owner.db.transaction() as conn:
            capture.require_publication_in(conn)
            assert supplied[-1] is conn
        capture.release()
        assert authority.run(run_id)['state'] == 'settled'
        assert owner.model_registry.status().runs == 0
        assert process.commands.count('model.extract') == 1
        assert not any(name.startswith('session.') for name in process.commands)
    finally:
        if owner.memory_captures.retained():
            await capture.settle()
            capture.release()


class HeldExtractionProcess(ScriptedExtractionProcess):
    def __init__(self, owner):
        super().__init__(owner)
        self.entered, self.gate, self.cancelled = (asyncio.Event() for _ in range(3))

    async def request(self, command, payload, operation_id, attempt_id, timeout):
        if command == 'model.extract':
            self.commands.append(command)
            self.entered.set()
            await self.gate.wait()
            self.completed = True
            return {'outcome': 'committed_reference', 'request_id': uuid4().hex,
                'result': {'failure': {'code': 'memory_capture_cancelled', 'status': 409, 'retryable': False}}}
        if command == 'model.extract.cancel':
            self.commands.append(command)
            self.cancelled.set()
            await self.gate.wait()
            return {'outcome': 'committed_reference', 'request_id': uuid4().hex, 'result': {'state': 'settled'}}
        return await super().request(command, payload, operation_id, attempt_id, timeout)

    async def settlement(self, timeout):
        return {'state': 'pending'}  # Scripted live native process, independent invocation state.


async def test_capture_stop_signals_reserved_control_and_retains_owner_until_finalizer(capture_owner):
    owner, authority, version = capture_owner
    process = HeldExtractionProcess(owner)
    seal = owner.seal_new_runs(expected_effective=version)
    owner.replace_process(process, configuration_id=version, seal=seal)
    seal.release()
    capture = owner.memory_captures.prepare(source(), current=lambda *, conn=None: None)
    generating = asyncio.create_task(capture.generate((('system', 'Extract facts.'), ('user', 'Synthetic answer.'))))
    try:
        await asyncio.wait_for(process.entered.wait(), 2)
        capture.cancel()
        await asyncio.wait_for(process.cancelled.wait(), .5)
        settlement = asyncio.create_task(capture.settle())
        await asyncio.sleep(.02)
        assert not settlement.done()
        assert authority.activation_snapshot()['pinned_runs'][0]['purpose'] == 'memory-extraction'
        assert owner.memory_captures.retained() == 1
        process.gate.set()
        with pytest.raises(ApiError) as refused:
            await generating
        assert refused.value.code == 'memory_capture_cancelled'
        await asyncio.wait_for(settlement, 2)
        capture.release()
        assert authority.activation_snapshot()['pinned_runs'] == []
    finally:
        process.gate.set()
        await asyncio.gather(generating, return_exceptions=True)
        if owner.memory_captures.retained():
            await capture.settle()
            capture.release()


class LostExtractionAck(HeldExtractionProcess):
    async def request(self, command, payload, operation_id, attempt_id, timeout):
        if command == 'model.extract':
            self.commands.append(command)
            raise OSError('Synthetic pipe disconnected after native admission')
        if command == 'model.extract.status':
            self.completed = self.gate.is_set()
        return await super().request(command, payload, operation_id, attempt_id, timeout)


class TimedStatusOnce(LostExtractionAck):
    def __init__(self, owner):
        super().__init__(owner)
        self.timed_out = asyncio.Event()

    async def request(self, command, payload, operation_id, attempt_id, timeout):
        if command == "model.extract.status" and not self.timed_out.is_set():
            self.timed_out.set()
            raise TimeoutError("Synthetic bounded status observation expired")
        return await super().request(command, payload, operation_id, attempt_id, timeout)


async def test_expired_status_observation_preserves_a_recoverable_settlement_owner(capture_owner):
    owner, authority, version = capture_owner
    process = TimedStatusOnce(owner)
    seal = owner.seal_new_runs(expected_effective=version)
    owner.replace_process(process, configuration_id=version, seal=seal)
    seal.release()
    capture = owner.memory_captures.prepare(source(), current=lambda *, conn=None: None)
    await asyncio.gather(capture.generate((("system", "Extract facts."), ("user", "Synthetic answer."))),
        return_exceptions=True)
    settling = asyncio.create_task(capture.settle())
    try:
        await asyncio.wait_for(process.timed_out.wait(), 1)
        await asyncio.sleep(.04)
        assert not settling.done(), "A read timeout must not permanently poison the cleanup owner"
        assert authority.activation_snapshot()["pinned_runs"]
        process.gate.set()
        await asyncio.wait_for(asyncio.shield(settling), 1)
        capture.release()
        assert authority.activation_snapshot()["pinned_runs"] == []
    finally:
        process.gate.set()
        await asyncio.gather(settling, return_exceptions=True)
        if owner.memory_captures.retained():
            await capture.settle()
            capture.release()


class LateRejectedExtraction(HeldExtractionProcess):
    def __init__(self, owner):
        super().__init__(owner)
        self.exited = False

    async def request(self, command, payload, operation_id, attempt_id, timeout):
        self.commands.append(command)
        if command == "model.extract":
            return {"outcome": "accepted_pending", "request_id": "synthetic-late-rejection"}
        if command == "model.extract.status":
            return {"outcome": "committed_reference", "request_id": uuid4().hex,
                "result": {"state": "unavailable"}}
        if command == "model.extract.cancel":
            return {"outcome": "committed_reference", "request_id": uuid4().hex,
                "result": {"state": "unavailable"}}
        raise AssertionError(command)

    async def query_result(self, request_id):
        assert request_id == "synthetic-late-rejection"
        return {"outcome": "rejected_before_admission", "request_id": request_id,
            "error": {"code": "harness_policy_blocked"}}

    async def settlement(self, timeout):
        return {"state": "settled" if self.exited else "pending"}


async def test_late_authenticated_admission_rejection_needs_no_native_invocation_drain(capture_owner):
    owner, authority, version = capture_owner
    process = LateRejectedExtraction(owner)
    seal = owner.seal_new_runs(expected_effective=version)
    owner.replace_process(process, configuration_id=version, seal=seal)
    seal.release()
    capture = owner.memory_captures.prepare(source(), current=lambda *, conn=None: None)
    await asyncio.gather(capture.generate((("system", "Extract facts."), ("user", "Synthetic answer."))),
        return_exceptions=True)
    settling = asyncio.create_task(capture.settle())
    try:
        done, _ = await asyncio.wait({settling}, timeout=.08)
        assert done, "The final authenticated pre-admission rejection proves no native invocation"
        await settling
        capture.release()
        assert authority.activation_snapshot()["pinned_runs"] == []
        assert process.commands == ["model.extract"]
    finally:
        process.exited = True
        await asyncio.wait_for(asyncio.shield(settling), 1)
        if owner.memory_captures.retained():
            capture.release()


class BusyReadRelease(LostExtractionAck):
    def __init__(self, owner):
        super().__init__(owner)
        self.release_gate = asyncio.Event()
        self.read_entered = asyncio.Event()
        self.reads = []
        self.release_ids = []

    async def request(self, command, payload, operation_id, attempt_id, timeout):
        response = await super().request(command, payload, operation_id, attempt_id, timeout)
        if command == "model.extract.status":
            self.reads.append(response["request_id"])
            self.read_entered.set()
        return response

    async def release_observation(self, request_id):
        self.release_ids.append(request_id)
        return self.release_gate.is_set()


async def test_busy_read_release_reuses_one_retained_observation_before_polling_again(capture_owner):
    owner, authority, version = capture_owner
    process = BusyReadRelease(owner)
    seal = owner.seal_new_runs(expected_effective=version)
    owner.replace_process(process, configuration_id=version, seal=seal)
    seal.release()
    capture = owner.memory_captures.prepare(source(), current=lambda *, conn=None: None)
    await asyncio.gather(capture.generate((("system", "Extract facts."), ("user", "Synthetic answer."))),
        return_exceptions=True)
    settling = asyncio.create_task(capture.settle())
    try:
        await asyncio.wait_for(process.read_entered.wait(), 1)
        await asyncio.sleep(.065)
        assert len(process.reads) == 1, "Busy release must not leak new terminal control receipts"
        assert set(process.release_ids) == set(process.reads)
        assert not settling.done()
        process.gate.set()
        process.release_gate.set()
        await asyncio.wait_for(asyncio.shield(settling), 1)
        capture.release()
        assert authority.activation_snapshot()["pinned_runs"] == []
    finally:
        process.gate.set()
        process.release_gate.set()
        await asyncio.wait_for(asyncio.shield(settling), 1)
        if owner.memory_captures.retained():
            capture.release()


class ShutdownOnlySettles(LateRejectedExtraction):
    def __init__(self, owner):
        super().__init__(owner)
        self.close_entered = asyncio.Event()

    async def request(self, command, payload, operation_id, attempt_id, timeout):
        if command == "model.extract":
            self.commands.append(command)
            raise OSError("Synthetic lost acknowledgement with no observable invocation")
        return await super().request(command, payload, operation_id, attempt_id, timeout)

    async def close(self, timeout=5):
        self.close_entered.set()
        self.exited = True
        return {"state": "closed"}


async def test_profile_shutdown_initiates_native_close_while_capture_producer_needs_exit_proof(capture_owner):
    owner, authority, version = capture_owner
    process = ShutdownOnlySettles(owner)
    seal = owner.seal_new_runs(expected_effective=version)
    owner.replace_process(process, configuration_id=version, seal=seal)
    seal.release()
    owner.install()
    capture = owner.memory_captures.prepare(source(), current=lambda *, conn=None: None)
    await asyncio.gather(capture.generate((("system", "Extract facts."), ("user", "Synthetic answer."))),
        return_exceptions=True)

    async def finish_capture_producer():
        # Explicit synthetic producer finalizer; native exit remains a separate
        # public process proof and canonical release follows it.
        await capture.settle()
        capture.release()

    owner.services.on_shutdown.append(finish_capture_producer)
    shutdown = asyncio.create_task(owner.services.shutdown())
    try:
        await asyncio.sleep(.08)
        assert process.close_entered.is_set(), "Shutdown must initiate the proof needed by its retained producer"
        await asyncio.wait_for(asyncio.shield(shutdown), 1)
        assert owner.memory_captures.retained() == 0
        assert authority.activation_snapshot()["pinned_runs"] == []
        assert process.commands.count("model.extract") == 1
    finally:
        await process.close(0)
        await asyncio.wait_for(asyncio.shield(shutdown), 1)


async def test_lost_extract_ack_keeps_possible_native_invocation_owned_without_resending(capture_owner):
    owner, authority, version = capture_owner
    process = LostExtractionAck(owner)
    seal = owner.seal_new_runs(expected_effective=version)
    owner.replace_process(process, configuration_id=version, seal=seal)
    seal.release()
    capture = owner.memory_captures.prepare(source(), current=lambda *, conn=None: None)
    try:
        await asyncio.gather(capture.generate((('system', 'Extract facts.'), ('user', 'Synthetic answer.'))),
            return_exceptions=True)
        settlement = asyncio.create_task(capture.settle())
        await asyncio.sleep(.04)
        assert not settlement.done(), 'A pipe exception cannot prove native invocation settlement'
        assert len(authority.activation_snapshot()['pinned_runs']) == 1
        process.gate.set()
        await asyncio.wait_for(settlement, 2)
        capture.release()
        assert process.commands.count('model.extract') == 1
        assert authority.activation_snapshot()['pinned_runs'] == []
    finally:
        process.gate.set()
        if owner.memory_captures.retained():
            await capture.settle()
            capture.release()


@pytest.mark.parametrize("code,status,retryable", [
    ("memory_dependency_revoked", 409, False),
    ("memory_answer_resolver_unavailable", 503, True),
])
async def test_final_capture_guard_preserves_source_failure_and_settled_owner_can_release(
        capture_owner, code, status, retryable):
    owner, authority, version = capture_owner
    process = ScriptedExtractionProcess(owner)
    seal = owner.seal_new_runs(expected_effective=version)
    owner.replace_process(process, configuration_id=version, seal=seal)
    seal.release()
    fault = False
    checked_connections = []

    def current(*, conn=None):
        checked_connections.append(conn)
        if fault:
            raise ApiError(code, "Synthetic local source failure", status, retryable)

    capture = owner.memory_captures.prepare(source(), current=current)
    try:
        await capture.generate((("system", "Extract facts."), ("user", "Synthetic answer.")))
        await capture.settle()
        run_id = authority.activation_snapshot()["pinned_runs"][0]["run_id"]
        fault = True
        with owner.db.transaction() as conn:
            with pytest.raises(ApiError) as refused:
                capture.require_publication_in(conn)
            assert checked_connections[-1] is conn
        assert (refused.value.code, refused.value.status, refused.value.retryable) == (code, status, retryable)
        assert authority.run(run_id)["state"] == "active"
        # Once Memory records its durable rejection, revocation cannot block
        # cleanup of the independently settled inference/CPU owner.
        capture.release()
        assert authority.run(run_id)["state"] == "settled"
        assert owner.memory_captures.retained() == 0
        assert owner.model_registry.status().runs == 0
        assert process.commands.count("model.extract") == 1
    finally:
        if owner.memory_captures.retained():
            await capture.settle()
            capture.release()
