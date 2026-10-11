# SPDX-License-Identifier: MIT
"""Saved callback authority distinguishes revoked support from resolver faults.

Canonical admission and lineage checks are real. Only the injected native IPC
transport and local dependency resolver are synthetic; no process or model starts.
"""
import json
from pathlib import Path

import pytest

from renulus.contracts import ApiError
from renulus.design_c_contracts import ConversationDraft, Dependency, Identity
from renulus.learn.conversation_models import NewConversation, Send
from renulus.learn.harness_bridge import HarnessLearningBridge
from renulus.memory.lineage import AnswerInputs
from renulus.runtime.harness_domain import DomainBinding, DomainCancellation, DomainRequest
from renulus.runtime.harness_learning import HarnessLearningOwner
from renulus.runtime.harness_process import HarnessProcessConfig
from renulus.server import create_app


class LocalSupportResolver:
    """Public local resolver fault injection, after an eligible admission."""
    def __init__(self):
        self.error = None

    def resolve_dependency_in(self, conn, dependency, *, project_id, for_support):
        if self.error is not None:
            raise self.error
        return AnswerInputs()


class AdmissionTransport:
    """Pin the native input through the public callback before prompt returns."""
    def __init__(self, owner):
        self.owner = owner
        self.binding = None
        self.sequence = 0

    async def request(self, command, payload, operation_id, attempt_id, timeout):
        if command == 'session.create':
            result = {'session': {'id': 'ses_synthetic_current'}}
        elif command == 'session.prompt':
            self.binding = DomainBinding(operation_id, attempt_id, payload['session_id'],
                'msg_synthetic_current', operation_id)
            request = DomainRequest('synthetic-input-admission', self.binding,
                'learning.admit_input', {})
            grant = await self.owner.authorize(request)
            assert grant is not None and grant.check_current() is True
            assert await grant.handler(request, DomainCancellation()) == {'admitted': True}
            result = {'sessionId': self.binding.session_id, 'inputId': self.binding.input_id,
                'operationId': operation_id, 'attemptId': attempt_id}
        elif command == 'session.cancel':
            result = {'outcome': 'cancelled_settled', 'interrupted': True}
        else:
            raise AssertionError(f'Unexpected native observation or generation: {command}')
        self.sequence += 1
        return {'protocol': 'renulus-harness/1', 'profile_id': 'synthetic-profile',
            'store_id': 'synthetic-runtime', 'generation': 'synthetic-process',
            'operation_id': operation_id, 'attempt_id': attempt_id,
            'request_id': f'synthetic-request-{self.sequence}', 'kind': 'reply',
            'outcome': 'committed_reference', 'result': result}


def scripted_manifest():
    manifest = json.loads((Path(__file__).resolve().parents[2] /
        'packages/contracts/fixtures/harness/paired-store-prepared.json').read_text())
    manifest['state'] = 'active'
    manifest['domain_store']['validation'] = manifest['runtime_store']['validation'] = 'valid'
    manifest['domain_store']['store_id'] = 'synthetic-domain'
    manifest['runtime_store']['store_id'] = 'synthetic-runtime'
    return manifest


@pytest.fixture
async def saved_callback(tmp_path):
    root = tmp_path / 'synthetic-current-profile'
    services = create_app(root).state.services
    memory = services.get('memory')
    resolver = LocalSupportResolver()
    memory.register_dependency_resolver('message', resolver)
    config = HarnessProcessConfig(node_executable=root / 'unused-node.exe',
        host_entry=root / 'unused-host.mjs', profile_root=root, profile_id='synthetic-profile',
        store_id='synthetic-runtime', domain_store_id='synthetic-domain',
        domain_path='state/renulus.sqlite3')
    owner = HarnessLearningOwner(services, config, configuration_id='synthetic-current-v1',
        memory=memory)
    transport = AdmissionTransport(owner)
    owner.bridge = HarnessLearningBridge(owner.repo, transport, active_manifest=scripted_manifest,
        configuration_id=owner.configuration_id, publish_answer_in=owner.publish_answer_in,
        check_run_dependencies_in=owner.check_run_dependencies_in)
    owner.install()
    chat = owner.repo.create(NewConversation())
    entry, receipt = owner.repo.streaming.begin('learning', chat['identity']['id'],
        Send(expected_revision=chat['revision'], text='Explain synthetic CKD.',
            request_id='synthetic-current-request'))
    stream = owner.bridge.answer(entry)
    try:
        assert (await anext(stream)).type == 'started'
        progress = await anext(stream)
        assert (progress.type, progress.payload) == ('progress', {'stage': 'native-execution'})
        owner.bridge.record_consumed(receipt['run_id'], dependencies=(Dependency(
            target=Identity(type='message', id='msg_synthetic_support'),
            expected_revision='synthetic-support-v1'),))
        grant = await owner.authorize(DomainRequest('synthetic-current-check', transport.binding,
            'learning.check', {}))
        assert grant is not None and grant.check_current() is True
        yield grant, resolver, owner.repo, chat
    finally:
        resolver.error = None
        await owner.bridge.cancel(receipt['run_id'])
        await stream.aclose()
        await owner.repo.streaming.close()
        services.get('helpers').startup.close()


async def test_saved_current_grant_preserves_memory_support_budget_fault(saved_callback):
    grant, resolver, _, _ = saved_callback
    fault = ApiError('memory_support_budget', 'Synthetic support closure exceeds budget.', 409)
    resolver.error = fault

    with pytest.raises(ApiError) as observed:
        grant.check_current()

    assert observed.value is fault
    assert (observed.value.code, observed.value.status, observed.value.retryable) == (
        'memory_support_budget', 409, False)


async def test_saved_current_grant_preserves_retryable_resolver_failure(saved_callback):
    grant, resolver, _, _ = saved_callback
    fault = ApiError('memory_answer_resolver_unavailable',
        'Synthetic local answer resolver is unavailable.', 503, True)
    resolver.error = fault

    with pytest.raises(ApiError) as observed:
        grant.check_current()

    assert observed.value is fault
    assert (observed.value.code, observed.value.status, observed.value.retryable) == (
        'memory_answer_resolver_unavailable', 503, True)
    resolver.error = None
    assert grant.check_current() is True


async def test_saved_current_grant_rejects_revoked_consumed_dependency(saved_callback):
    grant, resolver, _, _ = saved_callback
    resolver.error = ApiError('memory_dependency_revoked',
        'Synthetic consumed support was revoked.', 409)

    assert grant.check_current() is False


async def test_saved_current_grant_rejects_later_draft_revision(saved_callback):
    grant, _, repo, chat = saved_callback
    identifier = chat['identity']['id']
    current = repo.get('learning', identifier)
    saved = repo.save_draft('learning', identifier, ConversationDraft(
        expected_revision=current['revision'], text='A newer unsent draft.'))
    assert saved['text'] == 'A newer unsent draft.'

    assert grant.check_current() is False
