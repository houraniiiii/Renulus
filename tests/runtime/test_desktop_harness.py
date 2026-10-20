"""One connected desktop check: real Windows issuer/native host, synthetic HTTP only."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

import httpx
import pytest


REPO = Path(__file__).resolve().parents[2]
NODE = Path('C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe')
ANSWER = 'Synthetic CKD and dialysis learning answer.'


@pytest.mark.skipif(os.name != 'nt' or not NODE.is_file(), reason='Pinned Windows native runtime required')
def test_desktop_saved_chat_connection_tools_stop_reopen_and_model_change(tmp_path):
    home = tmp_path / 'synthetic-home'
    home.mkdir()
    env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
    env.update(PATH=str(NODE.parent), PYTHONPATH=str(REPO / 'runtime'),
        HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
    for key in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'TEMP', 'TMP'):
        env[key] = str(home)
    for phase in ('initial', 'reopen', 'changed'):
        result = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()),
            phase, str(tmp_path / 'profile')], cwd=REPO, env=env,
            capture_output=True, text=True, timeout=100,
            creationflags=subprocess.CREATE_NO_WINDOW)
        assert result.returncode == 0, phase + '\n' + result.stdout + '\n' + result.stderr
        assert json.loads(result.stdout.splitlines()[-1]) == {'phase': phase, 'passed': True}


async def scenario(phase, root):
    import _winapi
    import socket
    from renulus.runtime import desktop_harness as desktop

    # Fail any incidental external request, including helpers or native parent IO.
    original_connect = socket.socket.connect
    def local_only(sock, address):
        if isinstance(address, tuple) and address[0] in ('127.0.0.1', '::1', 'localhost'):
            return original_connect(sock, address)
        raise AssertionError('Synthetic desktop check attempted external networking')
    socket.socket.connect = local_only
    if phase == 'initial':
        root.mkdir(parents=True)
        _winapi.CreateJunction('C:/Renulus/dev/helper-assets', str(root / 'helpers'))

    calls = []
    holding, entered, release = False, asyncio.Event(), asyncio.Event()

    async def respond(request):
        payload = json.loads(request.content)
        assert str(request.url) == 'https://opencode.ai/zen/go/v1/chat/completions'
        assert request.headers['authorization'] == 'Bearer synthetic-desktop-test-only'
        assert payload['max_completion_tokens'] == desktop.OUTPUT_BUDGET
        assert payload['model'] == ('deepseek-v4.1-flash' if phase == 'changed' else 'mimo-v2.6-pro')
        assert {item['function']['name'] for item in payload['tools']} == {
            'renulus_library_retrieve', 'renulus_library_citation'}
        calls.append(payload)
        if holding:
            entered.set()
            await release.wait()
        if phase == 'initial' and len(calls) == 1:
            delta = {'tool_calls': [{'index': 0, 'id': 'synthetic_library_call', 'type': 'function',
                'function': {'name': 'renulus_library_retrieve',
                    'arguments': json.dumps({'query': 'synthetic CKD dialysis learning', 'limit': 1})}}]}
            finish = 'tool_calls'
        else:
            delta, finish = {'content': ANSWER}, 'stop'
        events = [{'id': 'synthetic_response', 'model': payload['model'], 'choices': [
            {'index': 0, 'delta': current, 'finish_reason': reason}]}
            for current, reason in ((delta, None), ({}, finish))]
        body = ''.join('data: ' + json.dumps(event) + '\n\n' for event in events) + 'data: [DONE]\n\n'
        return httpx.Response(200, headers={'content-type': 'text/event-stream'}, content=body.encode())

    desktop._http_transport = lambda route: httpx.MockTransport(respond)
    app = desktop.create_desktop_app(root, source_root=REPO, token='synthetic-session',
        provider_http_transport=httpx.MockTransport(lambda request: httpx.Response(200,
            json={'data': [{'id': 'mimo-v2.6-pro'}, {'id': 'deepseek-v4.1-flash'}]})))
    services, gate = app.state.services, app.state.desktop_harness
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://testserver',
                headers={'x-renulus-token': 'synthetic-session'}, timeout=90) as client:
            assert gate.task is None and 'learning_harness' not in services.registry
            if phase == 'initial':
                assert (await client.get('/api/v1/connections')).json()['selected_provider'] is None
                chat_response = await client.post('/api/v1/conversations', json={'kind': 'learning'})
                assert chat_response.status_code == 201, chat_response.text
                chat = chat_response.json()
                identifier = chat['identity']['id']
                (root.parent / 'chat-id.txt').write_text(identifier)
                denied = await client.post(f'/api/v1/conversations/learning/{identifier}/messages',
                    json={'expected_revision': chat['revision'], 'text': 'Synthetic learning', 'request_id': 'no-account'})
                assert denied.status_code == 409 and denied.json()['error']['code'] == 'connection_required', denied.text
                assert gate.task is None and 'learning_harness' not in services.registry and not calls
                connected = await client.post('/api/v1/connections/opencode-go',
                    json={'api_key': 'synthetic-desktop-test-only', 'select': True})
                assert connected.status_code == 200, connected.text
                selected = await client.post('/api/v1/connections/select',
                    json={'provider': 'opencode-go', 'model': 'mimo-v2.6-pro'})
                assert selected.status_code == 200, selected.text
                assert gate.task is None
            else:
                identifier = (root.parent / 'chat-id.txt').read_text()
                chat = (await client.get(f'/api/v1/conversations/learning/{identifier}')).json()
                history = await client.get(f'/api/v1/conversations/learning/{identifier}/messages')
                activation_error = gate.task.exception() if gate.task and gate.task.done() else None
                assert history.status_code == 200, history.text + '\nactivation: ' + str(getattr(activation_error, 'code', activation_error))
                assert any(item['content'] == ANSWER for item in history.json()['items']), history.text
                assert not calls, 'Reopening native history must not generate'

            if phase != 'reopen':
                sent = await client.post(f'/api/v1/conversations/learning/{identifier}/messages', json={
                    'expected_revision': chat['revision'], 'text': 'Explain synthetic CKD and dialysis learning.',
                    'request_id': 'synthetic-' + phase})
                activation_error = gate.task.exception() if gate.task and gate.task.done() else None
                assert sent.status_code == 200 and ANSWER in sent.text and 'event: completed' in sent.text, (
                    sent.text + '\nactivation: ' + str(getattr(activation_error, 'code', activation_error)))
                assert app.state.harness_bootstrap_result.admission_open
                history = await client.get(f'/api/v1/conversations/learning/{identifier}/messages')
                assert history.status_code == 200 and ANSWER in history.text, history.text
                if phase == 'initial':
                    assert len(calls) == 2, calls
                    assert any(message['role'] == 'tool' and message['tool_call_id'] == 'synthetic_library_call'
                        for message in calls[1]['messages']), calls[1]
                    # Stop a second actual native run while its HTTP boundary is held.
                    holding = True
                    chat = (await client.get(f'/api/v1/conversations/learning/{identifier}')).json()
                    sending = asyncio.create_task(client.post(f'/api/v1/conversations/learning/{identifier}/messages',
                        json={'expected_revision': chat['revision'], 'text': 'Synthetic stop request',
                            'request_id': 'synthetic-stop'}))
                    await asyncio.wait_for(entered.wait(), 30)
                    runs = (await client.get(f'/api/v1/conversations/learning/{identifier}/runs')).json()['items']
                    run = next(item for item in runs if item['state'] == 'running')
                    stopping = asyncio.create_task(client.post(
                        f'/api/v1/conversations/learning/{identifier}/runs/{run["run_id"]}/cancel'))
                    await asyncio.sleep(.05)
                    release.set()
                    stopped = await asyncio.wait_for(stopping, 20)
                    assert stopped.status_code == 200 and stopped.json()['state'] == 'cancelled', stopped.text
                    assert 'event: cancelled' in (await asyncio.wait_for(sending, 20)).text
            else:
                changed = await client.post('/api/v1/connections/select',
                    json={'provider': 'opencode-go', 'model': 'deepseek-v4.1-flash'})
                assert changed.status_code == 200, changed.text
                denied = await client.post(f'/api/v1/conversations/learning/{identifier}/messages',
                    json={'expected_revision': chat['revision'], 'text': 'Synthetic changed model',
                        'request_id': 'changed-model'})
                assert denied.status_code == 409, denied.text
                assert denied.json()['error']['code'] == 'desktop_harness_reconnect_required', denied.text
                assert not calls
    assert services.shutdown_status()['state'] == 'settled'
    print(json.dumps({'phase': phase, 'passed': True}))


if __name__ == '__main__':
    try:
        asyncio.run(scenario(sys.argv[1], Path(sys.argv[2]).resolve()))
    except Exception as error:
        print(getattr(error, 'code', type(error).__name__), file=sys.stderr)
        raise
