# SPDX-License-Identifier: MIT
"""Saved learning uses the same public conversations and owned host transport."""
import json
import asyncio
from pathlib import Path
import pytest

from fastapi.testclient import TestClient

from renulus.contracts import ApiError, Event
from renulus.server import create_app
from renulus.learn.conversation_models import NewConversation, Send


class LegacyProvider:
    async def stream(self, messages, **options):
        yield 'Legacy explanation must not be used by an admitted native chat.'

    async def cancel(self, run_id):
        return True


class UnavailableHarness:
    async def answer(self, entry):
        yield Event(run_id=entry['run'].id, sequence=1, type='error',
            payload={'code': 'harness_not_active', 'message': 'Activate the validated store pair.',
                     'retryable': True})


class ScriptedTransport:
    """An IPC adapter only; real native SDK coverage is a separate opt-in test."""
    def __init__(self):
        self.calls = []
        self.prompts = []
        self.prompt_metadata = {}
        self.responses = {}
        self.answer_text = 'Synthetic CKD explanation.'

    async def request(self, command, payload, operation_id, attempt_id, timeout):
        self.calls.append(command)
        if command == 'session.create':
            result = {'session': {'id': 'ses_synthetic'}}
        elif command == 'session.prompt':
            self.prompts.append(payload['text'])
            self.prompt_metadata = {'operationId': operation_id, 'attemptId': attempt_id,
                'configurationId': payload['configuration_id']}
            result = {'sessionId': 'ses_synthetic', 'inputId': 'msg_user',
                'operationId': operation_id, 'attemptId': attempt_id}
        elif command == 'session.get':
            result = {'session': {'id': 'ses_synthetic', 'outcome': 'succeeded',
                'time': {'idle': 1791676800003}}, 'execution': 'settled'}
        elif command == 'session.messages':
            result = {'messages': [
                {'id': 'msg_user', 'type': 'user', 'text': self.prompts[-1],
                 'metadata': dict(self.prompt_metadata), 'time': {'created': 1791676800000}},
                {'id': 'msg_answer', 'type': 'assistant', 'finish': 'stop',
                 'content': [{'type': 'text', 'text': self.answer_text}],
                 'time': {'created': 1791676800001, 'completed': 1791676800002}}], 'cursor': None}
        elif command == 'session.cancel':
            result = {'outcome': 'cancelled_settled', 'interrupted': True}
        else:
            raise AssertionError(command)
        response = {'protocol': 'renulus-harness/1', 'profile_id': 'synthetic-profile',
            'store_id': 'synthetic-runtime', 'generation': 'synthetic-process',
            'operation_id': operation_id, 'attempt_id': attempt_id,
            'request_id': 'request-' + str(len(self.calls)), 'kind': 'reply',
            'outcome': 'committed_reference', 'result': result}
        self.responses[response['request_id']] = response
        return response

    async def query_result(self, request_id):
        return self.responses[request_id]


def active_shape():
    # This is scripted active-selection data, not proof of actual store validation.
    value = json.loads((Path(__file__).resolve().parents[2] /
        'packages/contracts/fixtures/harness/paired-store-prepared.json').read_text())
    value['state'] = 'active'
    value['domain_store']['validation'] = value['runtime_store']['validation'] = 'valid'
    value['domain_store']['store_id'] = 'synthetic-domain'
    value['runtime_store']['store_id'] = 'synthetic-runtime'
    return value


async def collect(streams, entry, receipt):
    return [json.loads(encoded.split('data: ', 1)[1])
            async for encoded in streams.events(entry, receipt)]


def payloads(response):
    assert response.status_code == 200, response.text
    return [json.loads(line[6:]) for line in response.text.splitlines()
            if line.startswith('data: ')]


def test_saved_learning_uses_injected_harness_without_falling_back_to_legacy(tmp_path):
    app = create_app(tmp_path / 'synthetic-selection')
    app.state.services.registry['provider'] = LegacyProvider()
    app.state.services.registry['learning_harness'] = UnavailableHarness()
    with TestClient(app) as client:
        chat = client.post('/api/v1/conversations', json={}).json()
        route = '/api/v1/conversations/learning/' + chat['identity']['id']
        events = payloads(client.post(route + '/messages', json={
            'expected_revision': chat['revision'], 'text': 'Synthetic CKD explanation',
            'request_id': 'native-selection-request'}))
        assert events[-1]['type'] == 'error'
        assert events[-1]['payload']['code'] == 'harness_not_active'
        assert client.get(route + '/draft').json()['text'] == 'Synthetic CKD explanation'


async def test_native_answer_is_read_through_one_mapping_and_reference_only_receipt(tmp_path):
    from renulus.learn.harness_bridge import HarnessLearningBridge

    app = create_app(tmp_path / 'synthetic-native-answer')
    services = app.state.services
    repo = services.get('conversations')
    transport = ScriptedTransport()
    bridge = HarnessLearningBridge(repo, transport, active_manifest=active_shape,
        configuration_id='synthetic-policy-v1')
    services.registry['learning_harness'] = bridge
    chat = repo.create(NewConversation())
    identifier = chat['identity']['id']
    request = Send(expected_revision=chat['revision'], text='Explain synthetic CKD.',
        request_id='one-native-request')
    entry, receipt = repo.streaming.begin('learning', identifier, request)
    events = await collect(repo.streaming, entry, receipt)
    assert events[-1]['type'] == 'completed', events
    assert [event['sequence'] for event in events] == list(range(1, len(events) + 1))
    messages = await bridge.messages(identifier)
    assert [(item['id'], item['content']) for item in messages['items']] == [
        ('msg_user', 'Explain synthetic CKD.'), ('msg_answer', 'Synthetic CKD explanation.')]
    completed = bridge.completed(receipt['run_id'])
    assert isinstance(completed['publication_digest'], str) and len(completed['publication_digest']) == 64
    assert completed['sha256'] == 'fbfd8a8a69fc78b7e5a1b42e61ee34be0e7a60549de6b12aad3e2c9cc46a5256'
    assert completed['message_ids'] == ['msg_answer']
    assert 'Synthetic CKD explanation.' not in json.dumps(completed)
    assert repo.learn.get_thread(identifier)['messages'] == []
    assert repo.draft('learning', identifier)['text'] == ''
    assert bridge.mapping(identifier)['runtime']['session_id'] == 'ses_synthetic'
    replay_entry, replay_receipt = repo.streaming.begin('learning', identifier, request)
    replay = await collect(repo.streaming, replay_entry, replay_receipt)
    assert replay[-1]['payload']['replayed'] is True
    assert transport.prompts == ['Explain synthetic CKD.']


def native_at(tmp_path, transport=None, **options):
    from renulus.learn.harness_bridge import HarnessLearningBridge
    app = create_app(tmp_path / 'synthetic-bridge')
    services = app.state.services
    repository = services.get('conversations')
    transport = transport or ScriptedTransport()
    bridge = HarnessLearningBridge(repository, transport,
        active_manifest=options.pop('active_manifest', active_shape),
        configuration_id='synthetic-policy-v1', **options)
    services.registry['learning_harness'] = bridge
    chat = repository.create(NewConversation())
    identifier = chat['identity']['id']
    request = Send(expected_revision=chat['revision'], text='Explain synthetic CKD.',
        request_id='native-fixture-request')
    return services, repository, bridge, transport, identifier, request


async def test_completed_resolution_rejects_changed_native_answer_bytes(tmp_path):
    _, repo, bridge, transport, identifier, request = native_at(tmp_path)
    entry, receipt = repo.streaming.begin('learning', identifier, request)
    assert (await collect(repo.streaming, entry, receipt))[-1]['type'] == 'completed'
    answer = await bridge.resolve_completed(receipt['run_id'])
    assert answer.text == 'Synthetic CKD explanation.'
    assert answer.message_ids == ('msg_answer',)
    transport.answer_text = 'Altered native explanation.'
    with pytest.raises(ApiError) as rejected:
        await bridge.resolve_completed(receipt['run_id'])
    assert rejected.value.code == 'harness_answer_conflict'


async def test_pending_prompt_acknowledgement_is_observed_without_resubmission(tmp_path):
    class PendingTransport(ScriptedTransport):
        async def request(self, command, *args):
            result = await super().request(command, *args)
            if command == 'session.prompt':
                return {key: value for key, value in {**result, 'outcome': 'accepted_pending'}.items() if key != 'result'}
            return result
    _, repo, bridge, transport, identifier, request = native_at(tmp_path, PendingTransport())
    entry, receipt = repo.streaming.begin('learning', identifier, request)
    events = await collect(repo.streaming, entry, receipt)
    assert events[-1]['type'] == 'completed', events
    assert transport.prompts == ['Explain synthetic CKD.']
    assert bridge.completed(receipt['run_id'])['input_id'] == 'msg_user'


async def test_saved_observation_disconnect_still_commits_native_answer(tmp_path):
    _, repo, bridge, transport, identifier, request = native_at(tmp_path)
    entry, receipt = repo.streaming.begin('learning', identifier, request)
    observer = repo.streaming.events(entry, receipt)
    await anext(observer)
    await observer.aclose()
    task = repo.streaming.tasks.get(receipt['run_id'])
    if task is not None:
        await asyncio.wait_for(asyncio.shield(task), timeout=5)
    assert repo.streaming.status('learning', identifier, receipt['run_id'], neutral=True)['state'] == 'completed'
    assert bridge.completed(receipt['run_id'])['message_ids'] == ['msg_answer']
    assert transport.calls.count('session.cancel') == 0


@pytest.mark.parametrize('changed', ['draft', 'context', 'policy'])
async def test_changed_admission_revisions_block_native_disclosure_and_publication(tmp_path, changed):
    from renulus.design_c_contracts import ConversationDraft
    from renulus.storage.invalidation import bump_context_epoch
    class ChangedTransport(ScriptedTransport):
        async def request(self, command, *args):
            response = await super().request(command, *args)
            if command == 'session.get':
                if changed == 'draft':
                    current = repo.get('learning', identifier)
                    repo.save_draft('learning', identifier, ConversationDraft(expected_revision=current['revision'], text='A newer unsent draft.'))
                elif changed == 'context':
                    with services.db.transaction() as conn:
                        bump_context_epoch(conn)
                else:
                    services.db.execute("INSERT INTO assessment_test_attempts(id,version_id,version_snapshot_json,mode,clock_high_water_at,created_at,updated_at) VALUES('synthetic-active-test','unavailable','{}','test',?,?,?)", (utc_now(),) * 3)
            return response
    from renulus.storage import utc_now
    services, repo, bridge, transport, identifier, request = native_at(tmp_path, ChangedTransport())
    entry, receipt = repo.streaming.begin('learning', identifier, request)
    events = await collect(repo.streaming, entry, receipt)
    assert events[-1]['type'] == 'error', events
    assert not any(event['type'] == 'delta' for event in events)
    assert repo.streaming.status('learning', identifier, receipt['run_id'], neutral=True)['state'] != 'completed'
    if changed != 'policy':
        assert bridge.completed(receipt['run_id']) is None


def test_prepared_selection_refuses_saved_admission_without_creating_native_mapping(tmp_path):
    value = active_shape()
    value['state'] = 'prepared'
    value['domain_store']['validation'] = value['runtime_store']['validation'] = 'pending'
    _, repo, bridge, transport, identifier, request = native_at(tmp_path, active_manifest=lambda: value)
    with pytest.raises(ApiError) as rejected:
        repo.streaming.begin('learning', identifier, request)
    assert rejected.value.code == 'harness_not_active'
    assert bridge.mapping(identifier) is None
    assert transport.calls == []


async def test_native_history_requires_verified_inherited_lineage_before_another_turn(tmp_path):
    _, repo, bridge, transport, identifier, request = native_at(tmp_path)
    entry, receipt = repo.streaming.begin('learning', identifier, request)
    assert (await collect(repo.streaming, entry, receipt))[-1]['type'] == 'completed'
    current = repo.get('learning', identifier)
    followup = request.model_copy(update={'expected_revision': current['revision'], 'request_id': 'native-followup-request'})
    with pytest.raises(ApiError) as rejected:
        repo.streaming.begin('learning', identifier, followup)
    assert rejected.value.code == 'harness_history_requires_lineage'
    assert transport.prompts == ['Explain synthetic CKD.']


async def test_trusted_tool_receipt_publishes_exact_native_ids_and_dependency_closure(tmp_path):
    from renulus.design_c_contracts import Dependency, EligibleInput
    published = []
    memory = EligibleInput(kind='memory', dependency=Dependency(
        target={'type': 'memory_revision', 'id': 'synthetic-fact:2'}, expected_revision='2'))
    passage = Dependency(target={'type': 'library_revision', 'id': 'synthetic-revision'}, expected_revision='1')
    citation = {'content_ref': {'target': {'type': 'library_revision', 'id': 'synthetic-revision'},
        'locator': {'kind': 'pdf', 'physical_page': 3}}, 'passage_id': 'synthetic-passage',
        'text': 'SYNTHETIC_TOOL_PAYLOAD_MUST_NOT_BE_A_CANONICAL_TRANSCRIPT'}
    def validate(conn, *, inputs, dependencies):
        assert conn.in_transaction
        assert inputs == (memory,)
        assert passage in dependencies
    def publish(conn, answer, entry):
        assert conn.in_transaction
        published.append(answer)
        return 'a' * 64
    class ToolTransport(ScriptedTransport):
        async def request(self, command, payload, operation_id, *args):
            response = await super().request(command, payload, operation_id, *args)
            if command == 'session.messages':
                bridge.record_consumed(operation_id, inputs=(memory,), dependencies=(passage,), citations=(citation,))
                response['result']['messages'][-1]['content'].insert(0, {
                    'type': 'tool', 'id': 'tool_synthetic', 'name': 'library.retrieve',
                    'state': {'status': 'completed', 'content': [{'type': 'text', 'text': 'Synthetic eligible passage'}]}})
            return response
    _, repo, bridge, transport, identifier, request = native_at(tmp_path, ToolTransport(),
        check_dependencies_in=validate, publish_answer_in=publish)
    entry, receipt = repo.streaming.begin('learning', identifier, request)
    events = await collect(repo.streaming, entry, receipt)
    assert events[-1]['type'] == 'completed', events
    assert any(event['type'] == 'tool' and event['payload']['state'] == 'completed' for event in events)
    assert published[0].message_ids == ('msg_answer',)
    assert published[0].inputs == (memory,)
    assert published[0].citations == [citation]
    assert published[0].dependencies == (passage, memory.dependency)
    assert bridge.completed(receipt['run_id'])['publication_digest'] == 'a' * 64
    assert citation['text'] not in json.dumps(bridge.completed(receipt['run_id']))


async def test_public_send_rejects_conflicting_replay_without_native_dispatch(tmp_path):
    _, repo, bridge, transport, identifier, request = native_at(tmp_path)
    entry, receipt = repo.streaming.begin('learning', identifier, request)
    assert (await collect(repo.streaming, entry, receipt))[-1]['type'] == 'completed'
    with pytest.raises(ApiError) as conflict:
        repo.streaming.begin('learning', identifier, request.model_copy(update={'text': 'A different question.'}))
    assert conflict.value.code == 'idempotency_conflict'
    assert transport.prompts == ['Explain synthetic CKD.']


def test_public_native_history_reopens_with_reference_citations_and_stable_pagination(tmp_path):
    from renulus.learn.harness_bridge import HarnessLearningBridge
    from renulus.design_c_contracts import Dependency
    profile = tmp_path / 'synthetic-public-reopen'
    app = create_app(profile)
    repo = app.state.services.get('conversations')
    reference = {'target': {'type': 'library_revision', 'id': 'synthetic-source'},
        'locator': {'kind': 'pdf', 'physical_page': 4}}
    dependency = Dependency(target=reference['target'], expected_revision='1')
    class ToolTransport(ScriptedTransport):
        async def request(self, command, payload, operation_id, *args):
            result = await super().request(command, payload, operation_id, *args)
            if command == 'session.messages' and operation_id in repo.streaming.active:
                bridge.record_consumed(operation_id, dependencies=(dependency,),
                    citations=({'content_ref': reference, 'passage_id': 'synthetic-passage'},))
            return result
    transport = ToolTransport()
    bridge = HarnessLearningBridge(repo, transport, active_manifest=active_shape,
        configuration_id='synthetic-policy-v1',
        check_dependencies_in=lambda conn, **closure: None)
    app.state.services.registry['learning_harness'] = bridge
    with TestClient(app) as client:
        chat = client.post('/api/v1/conversations', json={}).json()
        route = '/api/v1/conversations/learning/' + chat['identity']['id']
        request = {'expected_revision': chat['revision'], 'text': 'Synthetic public question.',
            'request_id': 'synthetic-public-reopen-request'}
        events = payloads(client.post(route + '/messages', json=request))
        assert events[-1]['type'] == 'completed', events
    reopened = create_app(profile)
    reopened_repo = reopened.state.services.get('conversations')
    reopened.state.services.registry['learning_harness'] = HarnessLearningBridge(
        reopened_repo, transport, active_manifest=active_shape, configuration_id='synthetic-policy-v1')
    with TestClient(reopened) as client:
        first = client.get(route + '/messages', params={'limit': 1}).json()
        assert first['items'][0]['id'] == 'msg_user'
        assert first['next_cursor']
        second = client.get(route + '/messages', params={'limit': 1, 'cursor': first['next_cursor']}).json()
        assert second['items'][0]['id'] == 'msg_answer'
        assert second['items'][0]['content_refs'] == [reference]
        assert second['next_cursor'] is None
        assert payloads(client.post(route + '/messages', json=request))[-1]['payload']['replayed']
        assert transport.calls.count('session.create') == 1
        assert transport.prompts == ['Synthetic public question.']
        transport.answer_text = 'Native bytes changed after publication.'
        rejected = client.get(route + '/messages')
        assert rejected.status_code == 409
        assert rejected.json()['error']['code'] == 'harness_answer_conflict'


async def test_explicit_stop_settles_native_once_and_retains_draft_without_publication(tmp_path):
    class WaitingTransport(ScriptedTransport):
        def __init__(self):
            super().__init__()
            self.observing, self.released = asyncio.Event(), asyncio.Event()
        async def request(self, command, *args):
            if command == 'session.get':
                self.observing.set()
                await self.released.wait()
            response = await super().request(command, *args)
            if command == 'session.cancel':
                self.released.set()
            return response
    _, repo, bridge, transport, identifier, request = native_at(tmp_path, WaitingTransport())
    entry, receipt = repo.streaming.begin('learning', identifier, request)
    repo.streaming.launch(entry)
    await asyncio.wait_for(transport.observing.wait(), timeout=5)
    stopped = await repo.streaming.cancel('learning', identifier, receipt['run_id'])
    assert stopped['state'] == 'cancelled'
    assert transport.calls.count('session.cancel') == 1
    assert bridge.completed(receipt['run_id']) is None
    assert repo.draft('learning', identifier)['text'] == request.text
    with repo.db.transaction() as conn:
        assert conn.execute('SELECT state FROM learn_harness_answers WHERE run_id=?',
            (receipt['run_id'],)).fetchone()['state'] == 'cancelled'
    assert (await repo.streaming.cancel('learning', identifier, receipt['run_id']))['state'] == 'cancelled'
    assert transport.calls.count('session.cancel') == 1


async def test_publication_failure_rolls_back_receipt_and_keeps_current_draft(tmp_path):
    def reject(conn, answer, entry):
        conn.execute("UPDATE learn_threads SET title='Uncommitted publication' WHERE id=?", (answer.thread_id,))
        raise ApiError('synthetic_publication_rejected', 'The trusted publication was rejected.', 409)
    _, repo, bridge, transport, identifier, request = native_at(tmp_path, publish_answer_in=reject)
    original_title = repo.get('learning', identifier)['title']
    entry, receipt = repo.streaming.begin('learning', identifier, request)
    events = await collect(repo.streaming, entry, receipt)
    assert events[-1]['type'] == 'error'
    assert events[-1]['payload']['code'] == 'synthetic_publication_rejected'
    assert bridge.completed(receipt['run_id']) is None
    assert repo.get('learning', identifier)['title'] == original_title
    assert repo.draft('learning', identifier)['text'] == request.text
    assert transport.prompts == [request.text]


async def test_stop_after_canonical_publication_returns_completed_without_native_cancel(tmp_path):
    _, repo, bridge, transport, identifier, request = native_at(tmp_path)
    entry, receipt = repo.streaming.begin('learning', identifier, request)
    assert (await collect(repo.streaming, entry, receipt))[-1]['type'] == 'completed'
    stopped = await repo.streaming.cancel('learning', identifier, receipt['run_id'])
    assert stopped['state'] == 'completed'
    assert bridge.completed(receipt['run_id'])['message_ids'] == ['msg_answer']
    assert 'session.cancel' not in transport.calls


def test_saved_learning_run_pins_host_resolved_project_for_trusted_composition(tmp_path):
    from renulus.study.project_models import NewProject
    services, repo, bridge, transport, _, _ = native_at(tmp_path)
    project = services.get('projects').create(NewProject(title='Synthetic project scope'))
    chat = repo.create(NewConversation(project_id=project['id']))
    entry, receipt = repo.streaming.begin('learning', chat['identity']['id'], Send(
        expected_revision=chat['revision'], text='Synthetic scoped question.',
        request_id='synthetic-project-scope-request'))
    assert entry['run'].project_id == entry['project']['project_id'] == project['id']
    assert transport.calls == []
