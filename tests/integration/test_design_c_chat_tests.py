# SPDX-License-Identifier: MIT
"""Volatile lifecycle checks; only the real helper can prove artifact publication."""
import asyncio
import json
from threading import Event
from time import monotonic

from fastapi.testclient import TestClient
import pytest

from renulus.contracts import ApiError
from renulus.learn.chat_test_api import create_router
from renulus.learn.chat_test_models import QuickPracticeDraftRequest
from renulus.server import create_app
from renulus.storage.backup import export_records

RAW = 'FICTIONAL_VOLATILE_TEST_SOURCE_1CC70'
REQUEST = 'fictional_volatile_request_1cc70'


def app_at(profile):
    app = create_app(profile)
    if 'chat_tests' not in app.state.services.registry:
        app.include_router(create_router(app.state.services), prefix='/api/v1')
    return app


def no_durable_input(services):
    exported = json.dumps(export_records(services))
    assert RAW not in exported and REQUEST not in exported
    assert services.db.fetch_all('SELECT * FROM assessment_test_jobs') == []
    assert services.db.fetch_all('SELECT * FROM assessment_test_versions') == []
    for path in services.paths.root.rglob('*'):
        if path.is_file():
            content = path.read_bytes()
            assert RAW.encode() not in content and REQUEST.encode() not in content


def wait_terminal(client, run_id):
    deadline = monotonic() + 3
    while monotonic() < deadline:
        value = client.get('/api/v1/conversations/test-drafts/runs/' + run_id).json()
        if value['state'] not in ('queued', 'running'):
            return value
    raise AssertionError('The volatile test request did not finish')


def test_quick_practice_lost_ack_replays_one_volatile_task_and_cancellation_is_neutral(tmp_path, monkeypatch):
    app = app_at(tmp_path / 'quick-practice-replay')
    service = app.state.services.get('chat_tests')
    entered = Event()
    calls = []
    async def preparing(run):
        calls.append(run.id)
        entered.set()
        await asyncio.Event().wait()
    monkeypatch.setattr(service, '_fictionalise', preparing)
    body = {'intent': 'quick_practice', 'text': RAW, 'request_id': REQUEST, 'count': 5}
    with TestClient(app) as client:
        first = client.post('/api/v1/conversations/test-drafts', json=body)
        assert first.status_code == 202 and set(first.json()) == {'run_id', 'state'}
        run_id = first.json()['run_id']
        assert entered.wait(2)
        replay = client.post('/api/v1/conversations/test-drafts', json=body)
        assert replay.json()['run_id'] == run_id and calls == [run_id]
        changed = client.post('/api/v1/conversations/test-drafts', json={**body, 'text': RAW + ' changed'})
        assert changed.status_code == 409 and changed.json()['error']['code'] == 'idempotency_conflict'
        neutral = client.get('/api/v1/conversations/test-drafts/runs/' + run_id)
        assert set(neutral.json()) == {'run_id', 'state'} and RAW not in neutral.text
        cancelled = client.post('/api/v1/conversations/test-drafts/runs/' + run_id + '/cancel')
        assert cancelled.json() == {'run_id': run_id, 'state': 'cancelled'}
        assert client.post('/api/v1/conversations/test-drafts/runs/' + run_id + '/cancel').json() == cancelled.json()
        assert service.runs[run_id].source_text == ''
        no_durable_input(app.state.services)


def test_volatile_preparation_error_is_safe_and_never_creates_a_job_or_saved_artifact(tmp_path, monkeypatch):
    app = app_at(tmp_path / 'quick-practice-error')
    service = app.state.services.get('chat_tests')
    async def refuse(run):
        raise RuntimeError(RAW + REQUEST)
    monkeypatch.setattr(service, '_fictionalise', refuse)
    with TestClient(app) as client:
        started = client.post('/api/v1/conversations/test-drafts', json={
            'intent': 'quick_practice', 'text': RAW, 'request_id': REQUEST}).json()
        run_id = started['run_id']
        assert wait_terminal(client, run_id) == {'run_id': run_id, 'state': 'failed'}
        refused = client.get('/api/v1/conversations/test-drafts/runs/' + run_id + '/result')
        assert refused.status_code == 409 and RAW not in refused.text and REQUEST not in refused.text
        assert service.runs[run_id].source_text == '' and service.runs[run_id].source is None
        no_durable_input(app.state.services)
    with TestClient(app_at(app.state.services.paths.root)) as restarted:
        assert restarted.get('/api/v1/conversations/test-drafts/runs/' + run_id).status_code == 404


@pytest.mark.parametrize('extra', [{'count': 10}, {'count': 20}, {'artifact': {}}, {'privacy_reviewed': True}, {'scope': 'study'}, {'text': ''}])
def test_quick_practice_rejects_non_five_counts_and_public_attestation(tmp_path, extra):
    app = app_at(tmp_path / 'invalid-quick-intent')
    with TestClient(app) as client:
        body = {'intent': 'quick_practice', 'text': RAW, 'request_id': REQUEST, 'count': 5}
        response = client.post('/api/v1/conversations/test-drafts', json={**body, **extra})
        assert response.status_code == 422
        assert app.state.services.get('chat_tests').runs == {}
        no_durable_input(app.state.services)


@pytest.mark.parametrize('change', ['delete', 'revision', 'epoch', 'policy'])
def test_chat_producer_captures_real_source_and_final_guard_refuses_change(tmp_path, monkeypatch, change):
    from renulus.storage.invalidation import bump_context_epoch
    app = app_at(tmp_path / 'chat-test-guard')
    service = app.state.services.get('chat_tests')
    entered, release, seen = Event(), Event(), []
    async def guarded_preparation(run):
        seen.append(run.source_text)
        entered.set()
        while not release.is_set():
            await asyncio.sleep(0.01)
        service._guard(run)
        raise AssertionError('A changed source must never reach artifact publication')
    monkeypatch.setattr(service, '_fictionalise', guarded_preparation)
    with TestClient(app) as client:
        chat = client.post('/api/v1/conversations', json={'kind': 'case', 'temporary': True, 'text': RAW}).json()
        route = '/api/v1/conversations/case/' + chat['identity']['id']
        started = client.post(route + '/tests', json={'expected_revision': chat['revision'], 'request_id': REQUEST, 'count': 5})
        assert started.status_code == 202, started.text
        run_id = started.json()['run_id']
        assert entered.wait(2) and RAW in seen[0]
        if change == 'delete':
            assert client.delete(route, params={'expected_revision': chat['revision']}).status_code == 200
        elif change == 'revision':
            context = client.get(route + '/context').json()
            assert client.patch(route + '/context', json={'expected_revision': chat['revision'],
                'case_revision': context['revision'], 'text': 'Changed fictional source'}).status_code == 200
        elif change == 'epoch':
            with app.state.services.db.transaction() as conn:
                bump_context_epoch(conn)
        else:
            app.state.services.db.execute("INSERT INTO assessment_test_attempts(id,version_id,version_snapshot_json,mode,clock_high_water_at,created_at,updated_at) VALUES('volatile-active-test','absent','{}','test',?,?,?)", (chat['created_at'],) * 3)
        # The active guard must revoke preparation while the helper is still
        # waiting; releasing it is not required to observe source invalidation.
        deadline = monotonic() + 3
        # Status is a neutral service operation even before parent mounts its
        # active-Test HTTP exemption; this is not a middleware acceptance claim.
        while service.status(run_id)['state'] in ('queued', 'running') and monotonic() < deadline:
            Event().wait(0.01)
        assert service.status(run_id) == {'run_id': run_id, 'state': 'failed'}
        assert service.runs[run_id].cancel.is_set()
        no_durable_input(app.state.services)


def test_policy_is_checked_before_replaying_a_volatile_request(tmp_path, monkeypatch):
    app = app_at(tmp_path / 'volatile-policy-replay')
    service = app.state.services.get('chat_tests')
    async def refuse(run):
        raise ApiError('fictional_privacy_refused', 'Synthetic refusal', 409)
    monkeypatch.setattr(service, '_fictionalise', refuse)
    with TestClient(app) as client:
        body = {'intent': 'quick_practice', 'text': RAW, 'request_id': REQUEST, 'count': 5}
        run_id = client.post('/api/v1/conversations/test-drafts', json=body).json()['run_id']
        wait_terminal(client, run_id)
        app.state.services.db.execute("INSERT INTO assessment_test_attempts(id,version_id,version_snapshot_json,mode,clock_high_water_at,created_at,updated_at) VALUES('replay-active-test','absent','{}','test',?,?,?)", ('2026-10-10T00:00:00Z',) * 3)
        with pytest.raises(ApiError) as error:
            service.start_draft(QuickPracticeDraftRequest.model_validate(body))
        assert error.value.code == 'assistance_restricted'
        no_durable_input(app.state.services)


class FictionalTransport:
    """Only the external subscription transport is synthetic; authority is real."""
    def __init__(self):
        self.calls = []

    async def stream(self, provider, model, token, messages):
        assert token == 'synthetic-chat-test-token'
        payload = json.loads(messages[-1]['content'])
        self.calls.append(payload)
        if 'artifact_sha256' in payload:
            output = {'schema': 'fictional-test-review/1', 'artifact_sha256': payload['artifact_sha256'],
                'source_identity_removed': True, 'clinical_details_generalised': True,
                'no_source_links': True, 'issues': []}
        else:
            start = len(payload['prior_fictional_stems'])
            domains = ['transplant immunology', 'electrolyte physiology', 'glomerular inflammation',
                'dialysis clearance', 'chronic kidney adaptation']
            output = {'items': [{'stem': f'Independent conceptual {domains[index % 5]} question {index}',
                'options': [{'id': 'a', 'text': 'First fictional interpretation'},
                    {'id': 'b', 'text': 'Second fictional interpretation'}],
                'correct_option_id': 'a', 'explanation': 'An independent educational rationale.',
                'hint': None, 'source_indices': []} for index in range(start, start + 5)]}
        yield {'type': 'delta', 'text': json.dumps(output)}
        yield {'type': 'completed', 'response_model': model}


@pytest.mark.parametrize('count', [5, 10, 20])
def test_real_private_producer_saves_exact_version_and_starts_actual_study_once(tmp_path, count):
    app = app_at(tmp_path / 'real-chat-test')
    services = app.state.services
    provider = services.get('provider')
    provider._settings['connections']['codex'] = {'access_token': 'synthetic-chat-test-token', 'expires_at': 9999999999}
    provider._settings['selected_provider'] = 'codex'
    provider._settings.setdefault('selected_models', {})['codex'] = 'gpt-6.1-sol'
    provider._transport = transport = FictionalTransport()
    with TestClient(app) as client:
        if count == 5:
            route = '/api/v1/conversations/test-drafts'
            body = {'intent': 'quick_practice', 'text': RAW, 'request_id': REQUEST, 'count': 5}
            temporary_id = None
        else:
            chat = client.post('/api/v1/conversations', json={'kind': 'case', 'temporary': True, 'text': RAW}).json()
            temporary_id = chat['identity']['id']
            route = '/api/v1/conversations/case/' + temporary_id + '/tests'
            body = {'expected_revision': chat['revision'], 'request_id': REQUEST, 'count': count}
        response = client.post(route, json=body)
        assert response.status_code == 202, response.text
        run_id = response.json()['run_id']
        assert wait_terminal(client, run_id) == {'run_id': run_id, 'state': 'published'}
        assert client.post(route, json=body).json()['run_id'] == run_id
        assert len(transport.calls) == count // 5 + 1
        result = client.get('/api/v1/conversations/test-drafts/runs/' + run_id + '/result')
        assert result.status_code == 200, result.text
        saved = result.json()
        assert set(saved) == {'test_id', 'version_id', 'item_count', 'study_start'}
        assert saved['item_count'] == count
        descriptor = saved['study_start']
        assert descriptor['version'] == {'type': 'saved_test_version', 'id': saved['version_id']}
        assert descriptor['mode'] == 'study' and descriptor['timing'] == {'kind': 'untimed'}
        assert descriptor['idempotency_key'].startswith('chat-test-study-')
        start_body = {key: descriptor[key] for key in ('version', 'mode', 'timing')}
        headers = {'Idempotency-Key': descriptor['idempotency_key']}
        started = client.post('/api/v1/assessment/test-attempts', json=start_body, headers=headers)
        assert started.status_code == 201, started.text
        attempt = started.json()
        assert attempt['version_id'] == saved['version_id'] and attempt['item_count'] == count
        assert attempt['mode'] == 'study' and attempt['status'] == 'active'
        assert attempt['timing']['kind'] == 'untimed' and attempt['timing']['deadline_at'] is None
        assert attempt['origin'] == 'generated' and attempt['review_quality'] == 'personal'
        assert attempt['committed'] == [] and attempt['result'] is None
        assert 'correct_option_ids' not in json.dumps(attempt['current_item'])
        assert client.post('/api/v1/assessment/test-attempts', json=start_body, headers=headers).json()['id'] == attempt['id']
        assert len(services.db.fetch_all('SELECT * FROM assessment_test_versions')) == 1
        assert len(services.db.fetch_all('SELECT * FROM assessment_test_attempts')) == 1
        assert services.db.fetch_all('SELECT * FROM assessment_test_jobs') == []
        assert services.db.fetch_all('SELECT * FROM memory_jobs') == []
        exported = json.dumps(export_records(services))
        for forbidden in (RAW, REQUEST, temporary_id):
            if forbidden:
                assert forbidden not in exported
                assert all(forbidden.encode() not in path.read_bytes() for path in services.paths.root.rglob('*') if path.is_file())
        assert services.get('chat_tests').runs[run_id].source_text == ''
    # The volatile run disappears, while the real immutable version and durable
    # Study command replay survive reopening without provider work.
    with TestClient(app_at(services.paths.root)) as reopened:
        assert reopened.get('/api/v1/conversations/test-drafts/runs/' + run_id).status_code == 404
        replay = reopened.post('/api/v1/assessment/test-attempts', json=start_body, headers=headers)
        assert replay.status_code == 201 and replay.json()['id'] == attempt['id']
        assert len(transport.calls) == count // 5 + 1
