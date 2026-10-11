# SPDX-License-Identifier: MIT
"""Trusted context callbacks select native identities, never transcript claims."""
import asyncio
import copy

import pytest

from renulus.contracts import ApiError
from renulus.design_c_contracts import Dependency, EligibleInput
from test_harness_bridge import ScriptedTransport, native_at, collect


class ContextTransport(ScriptedTransport):
    """Callback/IPC fixture; actual per-model SDK hook is parent-owned evidence."""
    def __init__(self):
        super().__init__()
        self.native, self.contexts = [], []
        self.context_bridge = None
        self.before_prompt = None

    def descriptors(self):
        result = [{'id': 'unowned-system', 'role': 'system'}, {'id': 'unowned-user', 'role': 'user'}]
        for message in self.native:
            result.append({'id': message['id'], 'role': message['type']})
            if message['type'] == 'assistant':
                result.append({'id': message['id'], 'role': 'tool'})
        return result

    async def request(self, command, payload, operation_id, *args):
        response = await super().request(command, payload, operation_id, *args)
        if command == 'session.prompt':
            turn = len(self.prompts)
            input_id = 'input_' + str(turn)
            response['result']['inputId'] = input_id
            self.native.append({'id': input_id, 'type': 'user', 'text': payload['text'],
                'metadata': {'operationId': operation_id, 'attemptId': '1', 'configurationId': payload['configuration_id']},
                'time': {'created': 1791676800000 + turn * 10}})
            if self.before_prompt:
                self.before_prompt(operation_id)
            if self.context_bridge:
                self.context_bridge.bind_input(operation_id, session_id=payload['session_id'], input_id=input_id)
                self.contexts.append(self.context_bridge.select_context(operation_id, messages=self.descriptors()))
            self.native.append({'id': 'answer_' + str(turn), 'type': 'assistant',
                'content': [{'type': 'tool', 'id': 'call_' + str(turn), 'name': 'library.retrieve',
                    'state': {'status': 'completed'}}, {'type': 'text', 'text': 'Synthetic answer ' + str(turn)}],
                'time': {'created': 1791676800001 + turn * 10, 'completed': 1791676800002 + turn * 10}})
        elif command == 'session.get':
            response['result']['session']['time'] = {'idle': self.native[-1]['time']['completed'] + 1}
        elif command == 'session.messages':
            response['result'] = {'messages': copy.deepcopy(self.native), 'cursor': {}}
        return response


async def test_stale_known_answer_and_its_tool_results_are_excluded_from_next_turn(tmp_path):
    memory = EligibleInput(kind='memory', dependency=Dependency(
        target={'type': 'memory_revision', 'id': 'synthetic-fact:2'}, expected_revision='2'))
    revoked, published = False, []
    def validate(conn, *, inputs, dependencies):
        if revoked and memory in inputs:
            raise ApiError('memory_dependency_revoked', 'Synthetic memory was revoked.', 409)
    def publish(conn, answer, entry):
        published.append(answer)
        return 'a' * 64
    _, repo, bridge, transport, identifier, request = native_at(tmp_path, ContextTransport(),
        publish_answer_in=publish, check_dependencies_in=validate)
    transport.before_prompt = lambda run_id: bridge.record_consumed(run_id, inputs=(memory,))
    entry, receipt = repo.streaming.begin('learning', identifier, request)
    assert (await collect(repo.streaming, entry, receipt))[-1]['type'] == 'completed'
    assert published[0].inputs == (memory,)
    revoked = True
    eligible_calls = []
    def eligible(conn, *, references, project_id):
        eligible_calls.append((references, project_id))
        assert references[0]['run_id'] == receipt['run_id']
        # The parent adapter alone classifies the exact ineligible lineage codes.
        return ()
    bridge.eligible_history_in, bridge.context_filtering = eligible, True
    transport.context_bridge, transport.before_prompt = bridge, None
    followup = request.model_copy(update={'expected_revision': repo.get('learning', identifier)['revision'],
        'request_id': 'synthetic-followup-after-revocation'})
    next_entry, next_receipt = repo.streaming.begin('learning', identifier, followup)
    events = await collect(repo.streaming, next_entry, next_receipt)
    assert events[-1]['type'] == 'completed', events
    assert transport.contexts == [['input_2']]
    assert eligible_calls and eligible_calls[0][1] is None
    assert published[1].inputs == () and published[1].dependencies == ()
    assert bridge.completed(next_receipt['run_id'])['message_ids'] == ['answer_2']
    assert len(transport.prompts) == 2


async def test_eligible_assistant_and_tool_share_one_native_id_and_only_selected_history_is_inherited(tmp_path):
    published = []
    memory = EligibleInput(kind='memory', dependency=Dependency(
        target={'type': 'memory_revision', 'id': 'synthetic-fact:3'}, expected_revision='3'))
    def publish(conn, answer, entry):
        published.append(answer)
        return 'b' * 64
    _, repo, bridge, transport, identifier, request = native_at(tmp_path, ContextTransport(),
        publish_answer_in=publish, check_dependencies_in=lambda conn, **closure: None,
        context_filtering=True, eligible_history_in=lambda conn, **scope: tuple(
            EligibleInput(kind='committed_evidence', dependency=Dependency(
                target={'type': 'learning_evidence', 'id': 'learn-answer:' + ref['run_id']},
                expected_revision=ref['publication_digest'])) for ref in scope['references']))
    transport.before_prompt = lambda run_id: bridge.record_consumed(run_id, inputs=(memory,))
    transport.context_bridge = bridge
    first, first_receipt = repo.streaming.begin('learning', identifier, request)
    assert (await collect(repo.streaming, first, first_receipt))[-1]['type'] == 'completed'
    transport.before_prompt = None
    followup = request.model_copy(update={'expected_revision': repo.get('learning', identifier)['revision'],
        'request_id': 'synthetic-eligible-followup'})
    second, receipt = repo.streaming.begin('learning', identifier, followup)
    assert (await collect(repo.streaming, second, receipt))[-1]['type'] == 'completed'
    assert transport.contexts == [['input_1'], ['input_1', 'answer_1', 'input_2']]
    history_pin = EligibleInput(kind='committed_evidence', dependency=Dependency(
        target={'type': 'learning_evidence', 'id': 'learn-answer:' + first_receipt['run_id']}, expected_revision='b' * 64))
    assert published[1].inputs == (history_pin, memory)
    assert published[1].dependencies == (memory.dependency, history_pin.dependency)
    assert bridge.completed(receipt['run_id'])['message_ids'] == ['answer_2']


async def test_run_aware_dependency_callback_keeps_two_active_projects_distinct(tmp_path):
    from renulus.learn.conversation_models import NewConversation
    from renulus.study.project_models import NewProject
    expected, checked = {}, []
    def legacy(conn, **closure):
        raise AssertionError('The run-aware callback must take precedence.')
    def validate(conn, *, run_id, inputs, dependencies):
        assert conn.in_transaction
        assert inputs == (expected[run_id],)
        checked.append(run_id)
    services, repo, bridge, _, _, request = native_at(tmp_path, check_dependencies_in=legacy,
        check_run_dependencies_in=validate)
    entries, chats = [], []
    for index in range(2):
        project = services.get('projects').create(NewProject(title='Synthetic project ' + str(index)))
        chat = repo.create(NewConversation(project_id=project['id']))
        chats.append(chat)
    for index, chat in enumerate(chats):
        entry, receipt = repo.streaming.begin('learning', chat['identity']['id'], request.model_copy(update={
            'expected_revision': chat['revision'], 'request_id': 'synthetic-parallel-project-' + str(index)}))
        expected[receipt['run_id']] = EligibleInput(kind='memory', dependency=Dependency(
            target={'type': 'memory_revision', 'id': 'project-fact-' + str(index) + ':1'}, expected_revision='1'))
        entries.append(entry)
        assert entry['project']['project_id'] == chat['project_id']
    for entry in reversed(entries):
        bridge.record_consumed(entry['run'].id, inputs=(expected[entry['run'].id],))
        bridge.check(entry['run'].id)
    assert set(checked) == set(expected)


async def test_history_validation_fault_propagates_without_disclosing_old_or_new_answer(tmp_path):
    published = []
    def eligible(conn, *, references, project_id):
        if references:
            raise ApiError('memory_support_budget', 'Synthetic local lineage budget exhausted.', 409)
        return ()
    def publish(conn, answer, entry):
        published.append(answer)
        return 'c' * 64
    _, repo, bridge, transport, identifier, request = native_at(tmp_path, ContextTransport(),
        publish_answer_in=publish, check_dependencies_in=lambda conn, **closure: None,
        eligible_history_in=eligible, context_filtering=True)
    transport.context_bridge = bridge
    first, _ = repo.streaming.begin('learning', identifier, request)
    assert (await collect(repo.streaming, first, first['receipt']))[-1]['type'] == 'completed'
    followup = request.model_copy(update={'expected_revision': repo.get('learning', identifier)['revision'],
        'request_id': 'synthetic-lineage-fault-followup'})
    second, receipt = repo.streaming.begin('learning', identifier, followup)
    events = await collect(repo.streaming, second, receipt)
    assert events[-1]['payload']['code'] == 'memory_support_budget'
    assert not any(event['type'] == 'delta' for event in events)
    assert transport.contexts == [['input_1']]
    assert len(published) == 1
    assert bridge.completed(receipt['run_id']) is None


async def test_history_eligibility_adapter_cannot_enable_filtering_without_native_hook_assertion(tmp_path):
    _, repo, bridge, transport, identifier, request = native_at(tmp_path, ContextTransport(),
        publish_answer_in=lambda conn, answer, entry: 'd' * 64,
        check_dependencies_in=lambda conn, **closure: None,
        eligible_history_in=lambda conn, **scope: ())
    first, receipt = repo.streaming.begin('learning', identifier, request)
    assert (await collect(repo.streaming, first, receipt))[-1]['type'] == 'completed'
    followup = request.model_copy(update={'expected_revision': repo.get('learning', identifier)['revision'],
        'request_id': 'synthetic-no-native-context-hook'})
    with pytest.raises(ApiError) as rejected:
        repo.streaming.begin('learning', identifier, followup)
    assert rejected.value.code == 'harness_history_requires_lineage'
    assert len(transport.prompts) == 1


@pytest.mark.parametrize('missing', ['prior', 'current'])
async def test_native_context_requires_complete_prior_range_and_actual_current_input(tmp_path, missing):
    class PartialContext(ContextTransport):
        def descriptors(self):
            messages = super().descriptors()
            if len(self.prompts) == 2:
                missing_id = 'input_1' if missing == 'prior' else 'input_2'
                messages = [message for message in messages if message['id'] != missing_id]
            return messages
    published = []
    def publish(conn, answer, entry):
        published.append(answer)
        return 'e' * 64
    def eligible(conn, *, references, project_id):
        return tuple(EligibleInput(kind='committed_evidence', dependency=Dependency(
            target={'type': 'learning_evidence', 'id': 'learn-answer:' + ref['run_id']},
            expected_revision=ref['publication_digest'])) for ref in references)
    _, repo, bridge, transport, identifier, request = native_at(tmp_path, PartialContext(),
        publish_answer_in=publish, check_dependencies_in=lambda conn, **closure: None,
        eligible_history_in=eligible, context_filtering=True)
    transport.context_bridge = bridge
    first, receipt = repo.streaming.begin('learning', identifier, request)
    assert (await collect(repo.streaming, first, receipt))[-1]['type'] == 'completed'
    followup = request.model_copy(update={'expected_revision': repo.get('learning', identifier)['revision'],
        'request_id': 'synthetic-missing-' + missing + '-input'})
    second, receipt = repo.streaming.begin('learning', identifier, followup)
    events = await collect(repo.streaming, second, receipt)
    if missing == 'prior':
        assert events[-1]['type'] == 'completed'
        assert transport.contexts[-1] == ['input_2']
        assert published[1].inputs == () and published[1].dependencies == ()
    else:
        assert events[-1]['payload']['code'] == 'harness_input_conflict'
        assert not any(event['type'] == 'delta' for event in events)
        assert len(published) == 1
        assert bridge.completed(receipt['run_id']) is None


async def test_repeated_context_preparation_retains_current_assistant_and_idless_tool_owner(tmp_path):
    class WaitingObservation(ContextTransport):
        def __init__(self):
            super().__init__()
            self.observing, self.release = asyncio.Event(), asyncio.Event()
        async def request(self, command, *args):
            if command == 'session.get':
                self.observing.set()
                await self.release.wait()
            return await super().request(command, *args)
    _, repo, bridge, transport, identifier, request = native_at(tmp_path, WaitingObservation(),
        eligible_history_in=lambda conn, **scope: (), context_filtering=True)
    transport.context_bridge = bridge
    entry, receipt = repo.streaming.begin('learning', identifier, request)
    observer = asyncio.create_task(collect(repo.streaming, entry, receipt))
    try:
        await asyncio.wait_for(transport.observing.wait(), 5)
        selected = bridge.select_context(receipt['run_id'], messages=transport.descriptors())
        assert selected == ['input_1', 'answer_1']
        assert transport.contexts == [['input_1']]
    finally:
        transport.release.set()
    assert (await asyncio.wait_for(observer, 5))[-1]['type'] == 'completed'
