"""Reviewed progress consumes actual whole-attempt commitments, with no providers."""
import importlib.util
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from renulus.server import create_app

BASE = '/api/v1/assessment/test-attempts'


@pytest.fixture
def whole(tmp_path, monkeypatch):
    monkeypatch.setattr('renulus.server.MODULE_ORDER', ('content', 'updates', 'learn', 'cases', 'assessment', 'study'))
    spec = importlib.util.spec_from_file_location('progress_content', Path(__file__).parents[1] / 'assessment/conftest.py')
    fixtures = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixtures)
    app = create_app(tmp_path / 'progress-profile')
    services = app.state.services
    services.registry['content'] = fixtures.SyntheticContentRepository()
    client = TestClient(app)
    saved = client.post('/api/v1/assessment/tests/reviewed', json={'title': 'Synthetic progress', 'count': 3, 'idempotency_key': 'progress-reviewed'})
    assert saved.status_code == 200, saved.text
    yield client, services, saved.json()
    client.close()


def start(whole, key='start-study', mode='study', version=None):
    response = whole[0].post(BASE, headers={'Idempotency-Key': key}, json={
        'version': {'type': 'saved_test_version', 'id': version or whole[2]['version_id']}, 'mode': mode, 'timing': {'kind': 'untimed'}})
    assert response.status_code == 201, response.text
    return response.json()


def answer(whole, attempt, option='a', key='commit-progress'):
    response = whole[0].post(BASE + '/' + attempt['id'] + '/submit-answer', headers={'Idempotency-Key': key}, json={
        'expected_revision': attempt['draft_revision'], 'item_id': attempt['current_item']['item_id'], 'option_ids': [option]})
    assert response.status_code == 200, response.text
    return response.json()


def groups(whole):
    response = whole[0].get('/api/v1/study/progress')
    assert response.status_code == 200, response.text
    return response.json()['groups']


def test_actual_reviewed_study_commit_counts_and_assisted_repeat_stay_separate(whole):
    first = start(whole)
    assert sum(row['answered'] for row in groups(whole).values()) == 0
    answer(whole, first)
    repeated = start(whole, key='second-study')
    help_result = whole[0].post(BASE + '/' + repeated['id'] + '/help', headers={'Idempotency-Key': 'progress-help'}, json={
        'expected_revision': repeated['draft_revision'], 'expected_policy_revision': repeated['policy']['revision'],
        'item_id': repeated['current_item']['item_id'], 'kind': 'sources'})
    assert help_result.status_code == 200, help_result.text
    result = answer(whole, repeated, 'b', 'second-commit')
    assert result['committed'][0]['assisted'] and result['committed'][0]['repeat']
    assert groups(whole) == {'fresh': {'answered': 1, 'correct': 1}, 'assisted': {'answered': 0, 'correct': 0}, 'repeat': {'answered': 1, 'correct': 0}}
    plan = whole[1].get('study').propose()
    mistake = next(row for row in plan['activities'] if row['kind'] == 'mistake-review')
    assert mistake['reason']['assisted'] and mistake['reason']['repeat']
    assert mistake['reason']['attempt_id'] == repeated['id'] and mistake['reason']['mode'] == 'study'
    assert 'PRIVATE_' not in json.dumps(plan) and 'correct_option_ids' not in json.dumps(plan)
    third = start(whole, key='third-study'); answer(whole, third, key='third-answer')
    assert not [row for row in whole[1].get('study').plan()['activities'] if row['kind'] == 'mistake-review']


def test_actual_test_only_committed_answer_counts_not_unanswered_or_draft(whole):
    attempt = start(whole, mode='test')
    assert whole[0].get('/api/v1/study/progress').status_code == 409
    answers = [{**entry, 'option_ids': ['a'] if index == 0 else []} for index, entry in enumerate(attempt['answers'])]
    final = whole[0].post(BASE + '/' + attempt['id'] + '/submit', headers={'Idempotency-Key': 'progress-submit'}, json={
        'expected_draft_revision': attempt['draft_revision'], 'latest_draft': {'position': 0, 'answers': answers}})
    assert final.status_code == 200, final.text
    assert final.json()['result']['denominator'] == 3 and final.json()['result']['unanswered'] == 2
    assert groups(whole)['fresh'] == {'answered': 1, 'correct': 1}


@pytest.mark.parametrize('change', ['forged', 'attempt_deleted', 'version_deleted', 'withdrawn'])
def test_progress_and_automatic_plan_recheck_canonical_source(whole, change):
    client, services, saved = whole
    attempt = start(whole)
    result = answer(whole, attempt, 'b')
    evidence_id = result['committed'][0]['evidence_id']
    assert groups(whole)['fresh']['answered'] == 1
    assert any(row['kind'] == 'mistake-review' for row in services.get('study').propose()['activities'])
    if change == 'forged':
        row = services.db.fetch_one('SELECT payload_json FROM learning_evidence WHERE id=?', (evidence_id,))
        payload = json.loads(row['payload_json']); payload['correct'] = True
        services.db.execute('UPDATE learning_evidence SET payload_json=? WHERE id=?', (json.dumps(payload), evidence_id))
    elif change == 'attempt_deleted': services.db.mark_deleted('test_attempt', attempt['id'])
    elif change == 'version_deleted': services.db.mark_deleted('saved_test_version', saved['version_id'])
    else: services.get('content').withdraw(result['committed'][0]['question_id'])
    assert sum(row['answered'] for row in groups(whole).values()) == 0
    assert not any(row['kind'] == 'mistake-review' for row in services.get('study').plan()['activities'])


def test_personal_edit_of_reviewed_origin_cannot_become_bank_progress(whole):
    client, services, saved = whole
    with services.db.transaction() as conn:
        version = services.get('saved_tests').pinned_version(conn, saved['version_id'])
    response = client.post('/api/v1/assessment/tests/' + saved['test_id'] + '/versions', json={
        'idempotency_key': 'progress-personal-edit', 'expected_revision': 1, 'base_version_id': version.id,
        'items': [item.model_dump(mode='json') for item in version.items]})
    assert response.status_code == 200, response.text
    attempt = start(whole, version=response.json()['version_id'])
    answer(whole, attempt)
    assert sum(row['answered'] for row in groups(whole).values()) == 0


def test_eseneph_mistake_uses_current_mapped_question_and_objective_pins(whole):
    _, services, _ = whole
    content = services.get('content')
    for topic in content.topics: topic['objectives'] = [{'id': topic['id'] + '-objective'}]
    questions = content.list_question_summaries()
    content.track_metadata = lambda: [{'id': 'general_nephrology'}, {'id': 'esen_eph', 'available': True,
        'version': 'synthetic-map-1', 'aligned_objective_ids': [q['topic_id'] + '-objective' for q in questions],
        'domains': [{'alignments': [{'objective_ids': [q['topic_id'] + '-objective'], 'questions': [{'id': q['id'], 'version': q['version']}]} for q in questions]}]}]
    answer(whole, start(whole), 'b')
    study = services.get('study'); study.save_goals({'hours_per_week': 3, 'exam_date': None, 'topic_ids': [], 'track': 'eseneph'})
    reviews = [row for row in study.propose()['activities'] if row['kind'] == 'mistake-review']
    assert len(reviews) == 1 and reviews[0]['objective_id'] == reviews[0]['topic_id'] + '-objective'
    assert reviews[0]['reason']['mapping_version'] == 'synthetic-map-1'
