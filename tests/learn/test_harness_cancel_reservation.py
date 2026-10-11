# SPDX-License-Identifier: MIT
"""Lost-create cancellation keeps the public configuration fence closed.

IPC and active-store selection are explicitly scripted, not native store proof.
The canonical owner supplies admission and its public root seal only; its real
process is never started. Parent Settings receipts cover the real restart flow.
"""
import asyncio
from pathlib import Path

import pytest

from renulus.contracts import ApiError
from renulus.learn.conversation_models import NewConversation, Send
from renulus.learn.harness_bridge import HarnessLearningBridge
from renulus.runtime.harness_configuration import (
    CandidateHealth, ConfigurationAuthority, ConfigurationSpec, ConnectionReference,
    RestartBoundary, RolePolicy,
)
from renulus.runtime.harness_learning import HarnessLearningOwner
from renulus.runtime.harness_process import HarnessProcessConfig
from renulus.server import create_app
from tests.learn.test_harness_bridge import ScriptedTransport, active_shape, collect


class LostCreateAcknowledgement(ScriptedTransport):
    def __init__(self):
        super().__init__()
        self.create_pending = asyncio.Event()
        self.pending_observed = asyncio.Event()
        self.create_reply = None

    async def request(self, command, *args):
        response = await super().request(command, *args)
        if command != 'session.create':
            return response
        self.create_reply = response
        pending = {key: value for key, value in response.items() if key != 'result'}
        pending['outcome'] = 'accepted_pending'
        self.responses[response['request_id']] = pending
        self.create_pending.set()
        return pending

    async def query_result(self, request_id):
        response = await super().query_result(request_id)
        if response['outcome'] == 'accepted_pending':
            self.pending_observed.set()
        return response

    def acknowledge_create(self):
        self.responses[self.create_reply['request_id']] = self.create_reply


async def test_stop_with_lost_create_ack_keeps_native_reservation_and_root_fence(tmp_path):
    services = create_app(tmp_path / 'synthetic-lost-create').state.services
    authority = ConfigurationAuthority(services.db)
    spec = ConfigurationSpec(connection=ConnectionReference(provider='opencode-go',
        credential_reference='synthetic-cancel-connection', credential_revision=1,
        selected_model='mimo-v2.6-pro'), registry_hash='a' * 64,
        roles=(RolePolicy(purpose='explain', model_id='mimo-v2.6-pro'),),
        capabilities=('text', 'tools'))
    version = authority.stage(spec)
    # Synthetic policy bootstrap for this scripted IPC test, not a healthy
    # native observer or account/activation evidence.
    assert authority.validate(version, lambda candidate: CandidateHealth(
        configuration_version=candidate.version, grant_epoch=candidate.grant_epoch,
        registry_hash=spec.registry_hash))
    authority.activate(version, RestartBoundary(admission_closed=True,
        runtime_stopped=True, domain_settled=True), expected_effective=None)
    authority.open_admission(version, registry_hash=spec.registry_hash, grant_epoch=0)
    owner = HarnessLearningOwner(services, HarnessProcessConfig(
        node_executable=Path('G:/unused-cancel-node.exe'), host_entry=Path('G:/unused-cancel-host.mjs'),
        profile_root=services.paths.root, profile_id='synthetic-profile',
        store_id='synthetic-runtime', domain_store_id='synthetic-domain',
        domain_path='state/renulus.sqlite3'), configuration_id=version,
        configuration_authority=authority)
    transport = LostCreateAcknowledgement()
    repo = services.get('conversations')
    bridge = HarnessLearningBridge(repo, transport, active_manifest=active_shape,
        configuration_id=version, check_new_run_in=owner.check_new_run_in,
        admit_run_in=owner.admit_run_in)
    services.registry['learning_harness'] = bridge
    chat = repo.create(NewConversation())
    identifier = chat['identity']['id']
    request = Send(expected_revision=chat['revision'],
        text='Explain synthetic glomerular proteinuria mechanisms.',
        request_id='synthetic-lost-create-stop')
    producer = None
    try:
        entry, receipt = repo.streaming.begin('learning', identifier, request)
        run_id = receipt['run_id']
        producer = asyncio.create_task(collect(repo.streaming, entry, receipt))
        async with asyncio.timeout(5):
            await transport.create_pending.wait()
            await transport.pending_observed.wait()
        # Arrival at session.create proves the producer crossed the native-start
        # boundary. The withheld reply has not supplied a usable runtime mapping.
        assert bridge.mapping(identifier) is None
        assert (await repo.streaming.cancel('learning', identifier, run_id))['state'] == 'cancelled'
        events = await asyncio.wait_for(asyncio.shield(producer), timeout=5)
        assert [event['type'] for event in events] == ['started', 'cancelled']
        assert repo.streaming.status('learning', identifier, run_id, neutral=True)['state'] == 'cancelled'
        assert bridge.completed(run_id) is None
        assert repo.draft('learning', identifier)['text'] == request.text
        replay_entry, replay_receipt = repo.streaming.begin('learning', identifier, request)
        assert replay_entry is None and replay_receipt['state'] == 'cancelled'

        with pytest.raises(ApiError) as blocked:
            seal = owner.seal_new_runs(expected_effective=version)
            seal.release()  # A regression must not leak the accidentally acquired seal.
        assert blocked.value.code == 'harness_configuration_busy'

        transport.acknowledge_create()
        assert (await bridge.reconcile(run_id))['state'] == 'unchanged'
        assert bridge.mapping(identifier) is None
        with pytest.raises(ApiError) as still_blocked:
            seal = owner.seal_new_runs(expected_effective=version)
            seal.release()
        assert still_blocked.value.code == 'harness_configuration_busy'
        assert authority.run(run_id)['state'] == 'active'
        assert authority.run(run_id)['spent_dispatches'] == 0
        assert transport.calls == ['session.create']
        assert transport.prompts == []
    finally:
        if producer is not None and not producer.done():
            producer.cancel()
            await asyncio.gather(producer, return_exceptions=True)
        assert (await services.shutdown(timeout=5))['state'] == 'settled'
        services.get('helpers').startup.close()
