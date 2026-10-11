# SPDX-License-Identifier: MIT
"""Public history adapts read pages to the owned IPC byte limit."""
import json

from fastapi.testclient import TestClient

from renulus.learn.harness_bridge import HarnessLearningBridge
from renulus.server import create_app
from test_harness_bridge import ScriptedTransport, active_shape, payloads


class FrameBoundedTransport(ScriptedTransport):
    def __init__(self):
        super().__init__()
        self.max_frame_bytes = 2 * 1048576
        self.read_pages = []
        self.read_error = None

    async def request(self, command, payload, operation_id, *args):
        response = await super().request(command, payload, operation_id, *args)
        if command == 'session.get':
            response['result']['session']['time'] = {'idle': 1791676800164}
        elif command == 'session.messages':
            start = int(payload.get('cursor', '0'))
            limit = payload['limit']
            self.read_pages.append((start, limit))
            messages = [response['result']['messages'][0]] + [
                {'id': 'msg_answer_' + str(index), 'type': 'assistant', 'finish': 'stop',
                 'content': [{'type': 'text', 'text': 'A' * 16384}],
                 'time': {'created': 1791676800001 + index, 'completed': 1791676800100 + index}}
                for index in range(64)]
            end = min(start + limit, len(messages))
            response['result'] = {'messages': messages[start:end],
                'cursor': {'next': str(end)} if end < len(messages) else {}}
            if self.read_error or len(json.dumps(response, ensure_ascii=False, separators=(',', ':')).encode('utf-8')) + 1 > self.max_frame_bytes:
                return {key: value for key, value in {**response, 'outcome': 'uncertain_after_disconnect',
                    'error': {'code': self.read_error or 'reply_too_large'}}.items() if key != 'result'}
        return response


def test_public_messages_limit_one_reads_large_native_history_without_repeating_writes(tmp_path):
    app = create_app(tmp_path / 'synthetic-bounded-history')
    transport = FrameBoundedTransport()
    bridge = HarnessLearningBridge(app.state.services.get('conversations'), transport,
        active_manifest=active_shape, configuration_id='synthetic-policy-v1')
    app.state.services.registry['learning_harness'] = bridge
    with TestClient(app) as client:
        chat = client.post('/api/v1/conversations', json={}).json()
        route = '/api/v1/conversations/learning/' + chat['identity']['id']
        events = payloads(client.post(route + '/messages', json={
            'expected_revision': chat['revision'], 'text': 'A synthetic retained large explanation.',
            'request_id': 'synthetic-large-history-request'}))
        assert events[-1]['type'] == 'completed', events[-1]
        # A reopened transport may have a smaller reviewed frame capacity.
        transport.max_frame_bytes = 1048576
        transport.read_pages.clear()
        first = client.get(route + '/messages', params={'limit': 1})
        assert first.status_code == 200, first.text
        assert [item['id'] for item in first.json()['items']] == ['msg_user']
        assert first.json()['next_cursor']
        assert transport.read_pages == [(0, 200), (0, 100), (0, 50), (50, 50)]
        second = client.get(route + '/messages', params={'limit': 1, 'cursor': first.json()['next_cursor']})
        assert second.status_code == 200, second.text
        assert second.json()['items'][0]['id'] == 'msg_answer_0'
        assert second.json()['items'][0]['content'] == 'A' * 16384
    assert transport.calls.count('session.create') == 1
    assert len(transport.prompts) == 1
    assert 'session.cancel' not in transport.calls


def test_public_history_stops_at_one_oversized_message_and_does_not_resize_other_errors(tmp_path):
    app = create_app(tmp_path / 'synthetic-unreadable-message')
    transport = FrameBoundedTransport()
    bridge = HarnessLearningBridge(app.state.services.get('conversations'), transport,
        active_manifest=active_shape, configuration_id='synthetic-policy-v1')
    app.state.services.registry['learning_harness'] = bridge
    with TestClient(app) as client:
        chat = client.post('/api/v1/conversations', json={}).json()
        route = '/api/v1/conversations/learning/' + chat['identity']['id']
        events = payloads(client.post(route + '/messages', json={
            'expected_revision': chat['revision'], 'text': 'Synthetic bounded failure.',
            'request_id': 'synthetic-unreadable-history'}))
        assert events[-1]['type'] == 'completed'
        original = bridge.completed(events[-1]['run_id'])
        transport.max_frame_bytes = 1024
        transport.read_pages.clear()
        oversized = client.get(route + '/messages', params={'limit': 1})
        assert oversized.status_code == 409
        assert oversized.json()['error']['code'] == 'harness_history_reply_too_large'
        assert transport.read_pages == [(0, size) for size in (200, 100, 50, 25, 12, 6, 3, 1)] + [(1, 1)]
        transport.max_frame_bytes = 2 * 1048576
        transport.read_error = 'synthetic_observation_disconnected'
        transport.read_pages.clear()
        failed = client.get(route + '/messages', params={'limit': 1})
        assert failed.status_code == 409
        assert failed.json()['error']['code'] == 'harness_command_uncertain'
        assert transport.read_pages == [(0, 200)]
        assert bridge.completed(events[-1]['run_id']) == original
    assert transport.calls.count('session.create') == 1
    assert len(transport.prompts) == 1
    assert 'session.cancel' not in transport.calls
