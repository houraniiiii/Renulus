# SPDX-License-Identifier: MIT
"""Public saved learning reopens exact actual SDK effects after a lost reply."""
import asyncio
import os
from pathlib import Path

import httpx
import pytest

from renulus.learn.harness_bridge import HarnessLearningBridge
from renulus.runtime.harness_activation import HarnessProfileActivation
from renulus.runtime.harness_process import HarnessProcessConfig, ManagedHarnessProcess
from renulus.server import create_app
from test_harness_bridge import payloads

REPO = Path(__file__).resolve().parents[2]
NODE = Path(os.environ.get('RENULUS_HARNESS_NODE', ''))
pytestmark = pytest.mark.skipif(
    not os.environ.get('RENULUS_HARNESS_NODE') or not NODE.is_file() or
    not (REPO / 'packages/harness/node_modules/@opencode/sdk/package.json').is_file(),
    reason='Requires pinned managed Node 26.4.0 and the source-built cohort.')


async def settled(process, command, payload, operation_id):
    result = await process.request(command, payload, operation_id, '1', 1)
    async with asyncio.timeout(30):
        while result['outcome'] == 'accepted_pending':
            await asyncio.sleep(0.02)
            result = await process.query_result(result['request_id'])
    return result


class LoseActualReply:
    """Lose an acknowledgement after a real effect; never simulate native execution."""
    def __init__(self, process, command):
        self.process, self.lost_command = process, command
        self.calls, self.effect = [], None

    async def request(self, command, payload, operation_id, attempt_id, timeout):
        self.calls.append(command)
        result = await settled(self.process, command, payload, operation_id)
        if command == self.lost_command:
            assert result['outcome'] == 'committed_reference', result
            self.effect, self.lost_command = result['result'], None
            if command == 'session.prompt':
                async with asyncio.timeout(30):
                    while True:
                        observed = await settled(self.process, 'session.get',
                            {'session_id': payload['session_id']}, 'synthetic-settlement-observer')
                        if observed['result']['session'].get('outcome') == 'succeeded':
                            break
                        await asyncio.sleep(0.02)
            return {key: value for key, value in {**result, 'outcome': 'uncertain_after_disconnect',
                'error': {'code': 'synthetic_reply_lost'}}.items() if key != 'result'}
        return result

    async def query_result(self, request_id):
        return await self.process.query_result(request_id)


@pytest.mark.parametrize('lost_command', ['session.create', 'session.prompt'])
async def test_public_saved_bridge_recovers_actual_native_store_after_restart(tmp_path, lost_command):
    profile = tmp_path / 'synthetic-native-recovery'
    config = HarnessProcessConfig(node_executable=NODE,
        host_entry=REPO / 'packages/harness/test/fixtures/scripted-host.mjs',
        profile_root=profile, profile_id='synthetic-profile', store_id='synthetic-runtime',
        domain_store_id='synthetic-domain', domain_path='state/renulus.sqlite3', start_timeout=30)
    app = create_app(profile)
    process = ManagedHarnessProcess()
    transport = LoseActualReply(process, lost_command)
    try:
        await process.start(config)
        manifest = await HarnessProfileActivation(app.state.services.db, process, config).activate()
        ready = await settled(process, 'host.activate', {'configuration_id': 'synthetic-policy-v1'}, 'synthetic-configuration')
        assert ready['result']['state'] == 'ready'
        repo = app.state.services.get('conversations')
        bridge = HarnessLearningBridge(repo, transport, active_manifest=lambda: manifest,
            configuration_id='synthetic-policy-v1')
        app.state.services.registry['learning_harness'] = bridge
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://testserver') as client:
            created = await client.post('/api/v1/conversations', json={})
            assert created.status_code == 201, created.text
            chat = created.json()
            route = '/api/v1/conversations/learning/' + chat['identity']['id']
            request = {'expected_revision': chat['revision'], 'text': 'Explain synthetic CKD.',
                'request_id': 'synthetic-native-lost-reply'}
            events = payloads(await client.post(route + '/messages', json=request))
            assert events[-1]['payload']['code'] == 'harness_command_uncertain', events
            run_id = events[-1]['run_id']
            mapped = bridge.mapping(chat['identity']['id'])
        assert (await process.close(15))['state'] == 'closed'
        await app.state.services.shutdown()
        app = create_app(profile)
        process = ManagedHarnessProcess()
        transport.process = process
        await process.start(config)
        reopened = await HarnessProfileActivation(app.state.services.db, process, config).activate()
        assert reopened == manifest
        bridge = HarnessLearningBridge(app.state.services.get('conversations'), transport,
            active_manifest=lambda: reopened, configuration_id='synthetic-policy-v1')
        app.state.services.registry['learning_harness'] = bridge
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://testserver') as client:
            history = await client.get(route + '/messages')
            assert history.status_code == 200, history.text
            mapping = bridge.mapping(chat['identity']['id'])
            if lost_command == 'session.create':
                assert mapped is None
                assert mapping['runtime']['session_id'] == transport.effect['session']['id']
                assert history.json()['items'] == []
                assert (await client.get(route + '/draft')).json()['text'] == request['text']
                assert 'session.prompt' not in transport.calls
                assert transport.calls.count('session.find') == 1
            else:
                assert mapping == mapped
                assert history.json()['items'][0]['id'] == transport.effect['inputId']
                assert history.json()['items'][1]['content'] == 'Synthetic CKD learning answer.'
                answer = bridge.completed(run_id)
                assert answer['message_ids'] == [history.json()['items'][1]['id']]
                assert (await client.get(route + '/runs/' + run_id)).json()['state'] == 'completed'
                assert payloads(await client.post(route + '/messages', json=request))[-1]['payload']['replayed']
                assert transport.calls.count('session.prompt') == 1
            assert transport.calls.count('session.create') == 1
            assert 'session.cancel' not in transport.calls
            assert (await settled(process, 'host.status', {}, 'synthetic-reopened-status'))['result']['modelCalls'] == 0
    finally:
        assert (await process.close(15))['state'] == 'closed'
        await app.state.services.shutdown()
