# SPDX-License-Identifier: MIT
"""Saved public observation reconciles effects; it never repeats native work."""
import asyncio
import json
import pytest
from fastapi.testclient import TestClient

from renulus.learn.harness_bridge import HarnessLearningBridge
from renulus.contracts import ApiError
from renulus.design_c_contracts import ConversationDraft, Dependency, EligibleInput
from renulus.server import create_app
from test_harness_bridge import ScriptedTransport, active_shape, payloads, native_at, collect


class LostAcknowledgement(ScriptedTransport):
    def __init__(self, command='session.prompt'):
        super().__init__()
        self.lost_command = command
        self.operation_id = None
        self.on_input = None

    async def request(self, command, payload, operation_id, *args):
        self.operation_id = self.operation_id or operation_id
        if command == 'session.find' or (command == 'session.messages' and not self.prompts):
            self.calls.append(command)
            return {'protocol': 'renulus-harness/1', 'profile_id': 'synthetic-profile',
                'store_id': 'synthetic-runtime', 'generation': 'synthetic-reopened-process',
                'operation_id': operation_id, 'attempt_id': '1', 'request_id': 'find-reopened',
                'kind': 'reply', 'outcome': 'committed_reference', 'result': {'sessions': [{
                    'id': 'ses_synthetic', 'metadata': {'renulusProfile': 'synthetic-profile',
                        'renulusStore': 'synthetic-runtime', 'operationId': self.operation_id}}]}
                    if command == 'session.find' else {'messages': [], 'cursor': None}}
        result = await super().request(command, payload, operation_id, *args)
        if command == 'session.prompt' and self.on_input:
            self.on_input(operation_id, result['result']['inputId'])
        if command == 'session.messages':
            result['result']['messages'][0]['metadata'] = {'operationId': self.operation_id,
                'attemptId': '1', 'configurationId': 'synthetic-policy-v1'}
        if command == self.lost_command:
            self.lost_command = None
            return {key: value for key, value in {**result,
                'outcome': 'uncertain_after_disconnect', 'error': {'code': 'process_disconnected'}}.items() if key != 'result'}
        return result


def install(app, transport, **options):
    repo = app.state.services.get('conversations')
    bridge = HarnessLearningBridge(repo, transport, active_manifest=active_shape,
        configuration_id='synthetic-policy-v1', **options)
    app.state.services.registry['learning_harness'] = bridge
    return repo, bridge


def test_public_observation_recovers_lost_prompt_ack_after_reopen_without_resend(tmp_path):
    profile = tmp_path / 'synthetic-receipt-reopen'
    app = create_app(profile)
    transport = LostAcknowledgement()
    repo, bridge = install(app, transport)
    with TestClient(app) as client:
        chat = client.post('/api/v1/conversations', json={}).json()
        route = '/api/v1/conversations/learning/' + chat['identity']['id']
        request = {'expected_revision': chat['revision'], 'text': 'Synthetic saved question.',
            'request_id': 'synthetic-lost-ack-request'}
        events = payloads(client.post(route + '/messages', json=request))
        assert events[-1]['type'] == 'error'
        run_id = events[-1]['run_id']
    reopened = create_app(profile)
    reopened_repo, reopened_bridge = install(reopened, transport)
    with TestClient(reopened) as client:
        recovered = client.get(route + '/messages')
        assert recovered.status_code == 200, recovered.text
        assert [item['id'] for item in recovered.json()['items']] == ['msg_user', 'msg_answer']
        assert client.get(route + '/runs/' + run_id).json()['state'] == 'completed'
        replayed = payloads(client.post(route + '/messages', json=request))
        assert replayed[-1]['type'] == 'completed' and replayed[-1]['payload']['replayed']
        assert reopened_bridge.completed(run_id)['input_id'] == 'msg_user'
        assert reopened_bridge.mapping(chat['identity']['id'])['runtime']['session_id'] == 'ses_synthetic'
        assert client.get(route + '/draft').json()['text'] == ''
    assert transport.calls.count('session.create') == 1
    assert transport.prompts == [request['text']]
    assert 'session.cancel' not in transport.calls


@pytest.mark.parametrize('when', ['before', 'during'])
async def test_recovery_keeps_newer_draft_and_refuses_late_publication(tmp_path, when):
    class ChangedObservation(LostAcknowledgement):
        async def request(self, command, *args):
            result = await super().request(command, *args)
            if when == 'during' and command == 'session.messages':
                change_draft()
            return result
    _, repo, bridge, transport, identifier, request = native_at(tmp_path, ChangedObservation())
    def change_draft():
        repo.save_draft('learning', identifier, ConversationDraft(
            expected_revision=repo.get('learning', identifier)['revision'], text='A newer unsent draft.'))
    entry, receipt = repo.streaming.begin('learning', identifier, request)
    assert (await collect(repo.streaming, entry, receipt))[-1]['payload']['code'] == 'harness_command_uncertain'
    if when == 'before':
        change_draft()
    with pytest.raises(ApiError) as rejected:
        await bridge.messages(identifier)
    assert rejected.value.code == 'harness_reconciliation_stale'
    assert bridge.completed(receipt['run_id']) is None
    assert repo.draft('learning', identifier)['text'] == 'A newer unsent draft.'
    assert transport.prompts == [request.text]
    assert 'session.cancel' not in transport.calls


async def test_publication_callback_validates_immutable_submitted_reference_atomically(tmp_path):
    published = []
    def publish(conn, answer, entry):
        row = conn.execute('SELECT * FROM learn_harness_answers WHERE run_id=?', (answer.run_id,)).fetchone()
        assert conn.in_transaction
        assert row['state'] == 'submitted'
        assert json.loads(row['reference_json']) == answer.reference()
        published.append(answer)
        return 'b' * 64
    _, repo, bridge, _, identifier, request = native_at(tmp_path, publish_answer_in=publish)
    entry, receipt = repo.streaming.begin('learning', identifier, request)
    events = await collect(repo.streaming, entry, receipt)
    assert events[-1]['type'] == 'completed', events
    assert published[0].message_ids == ('msg_answer',)
    assert bridge.completed(receipt['run_id'])['publication_digest'] == 'b' * 64


def test_public_observation_finds_lost_create_without_ever_submitting_prompt(tmp_path):
    profile = tmp_path / 'synthetic-lost-create'
    transport = LostAcknowledgement('session.create')
    app = create_app(profile)
    install(app, transport)
    with TestClient(app) as client:
        chat = client.post('/api/v1/conversations', json={}).json()
        route = '/api/v1/conversations/learning/' + chat['identity']['id']
        request = {'expected_revision': chat['revision'], 'text': 'A retained synthetic draft.',
            'request_id': 'synthetic-lost-create-request'}
        events = payloads(client.post(route + '/messages', json=request))
        assert events[-1]['payload']['code'] == 'harness_command_uncertain'
    reopened = create_app(profile)
    _, bridge = install(reopened, transport)
    with TestClient(reopened) as client:
        for _ in range(2):
            observed = client.get(route + '/messages')
            assert observed.status_code == 200, observed.text
            assert observed.json()['items'] == []
        assert bridge.mapping(chat['identity']['id'])['runtime']['session_id'] == 'ses_synthetic'
        assert bridge.completed(events[-1]['run_id']) is None
        assert client.get(route + '/draft').json()['text'] == request['text']
        assert payloads(client.post(route + '/messages', json=request))[-1]['type'] == 'error'
    assert transport.calls.count('session.find') == 1
    assert transport.calls.count('session.create') == 1
    assert transport.prompts == []
    assert 'session.cancel' not in transport.calls


async def test_reopened_recovery_retains_trusted_closure_and_rolls_back_failed_publication(tmp_path):
    from renulus.learn.conversation_models import NewConversation, Send
    profile = tmp_path / 'synthetic-trusted-recovery'
    app = create_app(profile)
    transport = LostAcknowledgement()
    repo, bridge = install(app, transport)
    memory = EligibleInput(kind='memory', dependency=Dependency(
        target={'type': 'memory_revision', 'id': 'synthetic-fact:2'}, expected_revision='2'))
    source = Dependency(target={'type': 'library_revision', 'id': 'synthetic-source'}, expected_revision='1')
    citation = {'passage_id': 'synthetic-passage', 'text': 'Native-only synthetic tool bytes.'}
    def validate(conn, *, run_id, **closure):
        assert conn.in_transaction and closure['inputs'] == (memory,)
        assert run_id == receipt['run_id']
    bridge.check_run_dependencies_in = validate
    def admitted(run_id, input_id):
        bridge.bind_input(run_id, session_id='ses_synthetic', input_id=input_id)
        bridge.record_consumed(run_id, inputs=(memory,), dependencies=(source,), citations=(citation,))
    transport.on_input = admitted
    chat = repo.create(NewConversation())
    identifier = chat['identity']['id']
    request = Send(expected_revision=chat['revision'], text='Synthetic trusted learning.', request_id='trusted-recovery-request')
    entry, receipt = repo.streaming.begin('learning', identifier, request)
    assert (await collect(repo.streaming, entry, receipt))[-1]['type'] == 'error'
    await app.state.services.shutdown()
    reopened = create_app(profile)
    published, fail = [], True
    def publish(conn, answer, entry):
        assert answer.inputs == (memory,)
        assert answer.dependencies == (source, memory.dependency)
        assert answer.citations == [{'passage_id': 'synthetic-passage'}]
        assert json.loads(conn.execute('SELECT reference_json FROM learn_harness_answers WHERE run_id=?',
            (answer.run_id,)).fetchone()[0]) == answer.reference()
        if fail:
            conn.execute("UPDATE learn_threads SET title='Uncommitted recovered title' WHERE id=?", (identifier,))
            raise ApiError('synthetic_publication_unavailable', 'Synthetic local publication failed.', 409)
        published.append(answer)
        return 'c' * 64
    repo, recovered = install(reopened, transport, check_run_dependencies_in=validate, publish_answer_in=publish)
    with pytest.raises(ApiError) as rejected:
        await recovered.messages(identifier)
    assert rejected.value.code == 'synthetic_publication_unavailable'
    assert recovered.completed(receipt['run_id']) is None
    assert repo.get('learning', identifier)['title'] == chat['title']
    assert repo.draft('learning', identifier)['text'] == request.text
    fail = False
    histories = await asyncio.gather(recovered.messages(identifier), recovered.messages(identifier))
    assert [item['id'] for item in histories[0]['items']] == ['msg_user', 'msg_answer']
    assert histories[0] == histories[1]
    assert recovered.completed(receipt['run_id'])['publication_digest'] == 'c' * 64
    assert len(published) == 1
    assert transport.prompts == [request.text]
    assert 'session.cancel' not in transport.calls
    await reopened.state.services.shutdown()


async def test_recovery_rejects_native_input_conflicting_with_parent_pinned_identity(tmp_path):
    _, repo, bridge, transport, identifier, request = native_at(tmp_path, LostAcknowledgement())
    transport.on_input = lambda run_id, input_id: bridge.bind_input(run_id,
        session_id='ses_synthetic', input_id='different-parent-pinned-input')
    entry, receipt = repo.streaming.begin('learning', identifier, request)
    assert (await collect(repo.streaming, entry, receipt))[-1]['type'] == 'error'
    with pytest.raises(ApiError) as rejected:
        await bridge.messages(identifier)
    assert rejected.value.code == 'harness_input_conflict'
    assert bridge.completed(receipt['run_id']) is None
    assert transport.prompts == [request.text]
