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
