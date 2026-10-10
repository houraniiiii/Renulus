"""Actual collection/attempt producers into canonical Memory; no inference or fixture DDL."""
import importlib.util
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.design_c_contracts import SavedTestVersion
from renulus.server import create_app
from renulus.storage.invalidation import bump_context_epoch
from renulus.storage.relations import reconcile_unavailable_references

BASE = '/api/v1/assessment/test-attempts'
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def whole_memory(tmp_path, monkeypatch):
    monkeypatch.setenv('HF_HUB_OFFLINE', '1')
    monkeypatch.setenv('TRANSFORMERS_OFFLINE', '1')
    monkeypatch.setenv('HF_HOME', str(tmp_path / 'offline-helper-cache'))
    monkeypatch.setattr('renulus.server.MODULE_ORDER', ('runtime', 'content', 'knowledge', 'retrieval',
        'learn', 'cases', 'assessment', 'memory', 'study', 'updates'))
    spec = importlib.util.spec_from_file_location('whole_memory_synthetic_content', ROOT / 'tests/assessment/conftest.py')
    fixtures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures)
    app = create_app(tmp_path / 'whole-memory-profile')
    services = app.state.services
    services.registry['content'] = fixtures.SyntheticContentRepository()
    # Request the actual assembled HTTP app without starting helper/index workers.
    # Capture below executes the real canonical repository transaction directly.
    client = TestClient(app)
    published = client.post('/api/v1/assessment/tests/reviewed', json={
        'idempotency_key': 'memory-reviewed-version', 'title': 'Original synthetic Memory practice', 'count': 3})
    assert published.status_code == 200, published.text
    yield client, services, services.get('memory').repository, published.json()['version_id']
    client.close()


def start(whole, *, version_id=None, mode='study', key='memory-start-study'):
    client, _, _, default = whole
    response = client.post(BASE, headers={'Idempotency-Key': key}, json={
        'version': {'type': 'saved_test_version', 'id': version_id or default},
        'mode': mode, 'timing': {'kind': 'untimed'}})
    assert response.status_code == 201, response.text
    return response.json()


def commit(whole, attempt, *, option='a', key='memory-answer'):
    response = whole[0].post(BASE + '/' + attempt['id'] + '/submit-answer',
        headers={'Idempotency-Key': key}, json={'expected_revision': attempt['draft_revision'],
            'item_id': attempt['current_item']['item_id'], 'option_ids': [option]})
    assert response.status_code == 200, response.text
    return response.json()['committed'][0]['evidence_id']


def capture(whole, evidence_id, scope):
    repository = whole[2]
    queued = repository.enqueue(evidence_id, scope)
    claimed = repository.claim(queued['id'])
    assert claimed is not None
    material = repository.material(evidence_id, scope)
    assert material['infer'] is False
    identifiers = repository.commit_capture(claimed, material, ['PRIVATE_FORGED_CONSUMER_TEXT'])
    assert len(identifiers) == 1
    return repository.get(identifiers[0]), material


def test_actual_study_commit_auto_scan_captures_safe_scalar_metadata_and_ignores_draft(whole_memory):
    client, services, repository, _ = whole_memory
    attempt = start(whole_memory)
    response = client.put(BASE + '/' + attempt['id'] + '/draft', headers={'Idempotency-Key': 'memory-draft'},
        json={'expected_revision': 0, 'position': 0, 'answers': [
            {**answer, 'option_ids': ['a'] if index == 0 else []} for index, answer in enumerate(attempt['answers'])]})
    assert response.status_code == 200, response.text
    repository.scan()
    assert repository.jobs() == []
    evidence_id = commit(whole_memory, response.json())
    repository.scan()
    queued = repository.jobs()
    assert len(queued) == 1 and queued[0]['evidence_id'] == evidence_id
    scope = ContextScope(kind=Scope.REVIEWED_ASSESSMENT, entity_id=attempt['id'])
    fact, material = capture(whole_memory, evidence_id, scope)
    assert fact['text'] == material['text'] and fact['scope'] == 'reviewed-assessment'
    assert material['assessment']['score_bucket'] == 'fresh' and material['assessment']['reviewed']
    assert fact['source_id'] == evidence_id and fact['source_kind'] == 'learning-evidence'
    rows = services.db.fetch_all('SELECT text FROM memory_history')
    assert all('PRIVATE_' not in row['text'] and 'Token a' not in row['text'] for row in rows)
    packet = json.dumps({**material, 'scope': scope.model_dump(mode='json')})
    assert all(word not in packet for word in ('correct_option_ids', 'selected_option_ids', 'explanation', 'stem'))
    repository.scan()
    assert len(repository.jobs()) == 1


@pytest.mark.parametrize('origin,method', [('generated', 'generation'), ('imported', 'import'),
                                        ('nightly', 'nightly'), ('reviewed_bank', 'reviewed_pack')])
def test_personal_origins_never_become_reviewed_memory_or_mastery(whole_memory, origin, method):
    _, services, repository, source_id = whole_memory
    saved = services.get('saved_tests')
    with services.db.transaction() as conn:
        raw = saved.pinned_version(conn, source_id).model_dump(mode='json')
        raw.update(id='memory_personal_' + origin, test_id='memory_personal_test_' + origin,
                   origin=origin, review_quality='personal', provenance={'method': method})
        for index, item in enumerate(raw['items']):
            item.update(item_id='memory_item_' + str(index), question_id='memory_question_' + str(index),
                        family_id='memory_family_' + str(index), stem='Original synthetic personal Memory question')
        version = SavedTestVersion.model_validate(raw)
        saved.publish_version(conn, version, title='Original synthetic personal Memory',
                              provenance={'schema': 'saved-test-provenance/1', 'consumer_fixture': origin},
                              idempotency_key='memory-publish-' + origin)
    attempt = start(whole_memory, version_id=version.id)
    evidence_id = commit(whole_memory, attempt, option='b')
    repository.scan()
    scope = ContextScope(kind=Scope.GENERATED_PRACTICE, entity_id=attempt['id'])
    fact, material = capture(whole_memory, evidence_id, scope)
    assert material['assessment']['origin'] == origin and material['assessment']['review_quality'] == 'personal'
    assert not material['assessment']['reviewed'] and not material['assessment']['bank_cohort_eligible']
    assert material['assessment']['score_bucket'] == 'personal' and fact['kind'] == 'study-interest'
    assert 'unreviewed' in fact['text'] and 'saved key' in fact['text'] and 'mastery' not in fact['text']
    assert fact['scope'] == 'generated-practice'
    with pytest.raises(ApiError) as mismatch:
        repository.material(evidence_id, ContextScope(kind=Scope.REVIEWED_ASSESSMENT, entity_id=attempt['id']))
    assert mismatch.value.code == 'memory_evidence_scope'


def test_assistance_and_repeat_remain_independent_in_memory(whole_memory):
    client, _, _, _ = whole_memory
    start(whole_memory)
    repeated = start(whole_memory, key='memory-repeat')
    help_response = client.post(BASE + '/' + repeated['id'] + '/help', headers={'Idempotency-Key': 'memory-help'}, json={
        'expected_revision': 0, 'expected_policy_revision': repeated['policy']['revision'],
        'item_id': repeated['current_item']['item_id'], 'kind': 'sources'})
    assert help_response.status_code == 200, help_response.text
    evidence_id = commit(whole_memory, repeated)
    fact, material = capture(whole_memory, evidence_id, ContextScope(kind=Scope.REVIEWED_ASSESSMENT, entity_id=repeated['id']))
    assert material['assessment']['assisted'] and material['assessment']['repeat']
    assert material['assessment']['score_bucket'] == 'repeat'
    assert 'assisted: yes' in fact['text'] and 'repeat: yes' in fact['text']


@pytest.mark.parametrize('change', ['payload', 'evidence_deleted', 'attempt_deleted', 'version_deleted', 'suppressed', 'active_test', 'epoch'])
def test_late_capture_refuses_invalidated_source_and_writes_no_fact(whole_memory, change):
    _, services, repository, version_id = whole_memory
    attempt = start(whole_memory)
    evidence_id = commit(whole_memory, attempt)
    scope = ContextScope(kind=Scope.REVIEWED_ASSESSMENT, entity_id=attempt['id'])
    job = repository.claim(repository.enqueue(evidence_id, scope)['id'])
    material = repository.material(evidence_id, scope)
    with services.db.transaction() as conn:
        if change == 'payload':
            conn.execute('UPDATE learning_evidence SET payload_json=? WHERE id=?',
                         (json.dumps({'scope': {'kind': 'reviewed-assessment'}, 'explanation': 'PRIVATE_FORGED'}), evidence_id))
        elif change in ('evidence_deleted', 'attempt_deleted'):
            kind, identifier = ('learning_evidence', evidence_id) if change == 'evidence_deleted' else ('test_attempt', attempt['id'])
            services.db.mark_deleted(kind, identifier, conn)
        elif change == 'version_deleted':
            conn.execute('DELETE FROM assessment_test_versions WHERE id=?', (version_id,))
            reconcile_unavailable_references(conn)
        elif change == 'suppressed':
            conn.execute('INSERT INTO memory_suppression VALUES(?,?)', ('evidence:' + evidence_id, '2026-10-10T12:00:00Z'))
        elif change == 'epoch':
            bump_context_epoch(conn)
    if change == 'active_test':
        start(whole_memory, mode='test', key='memory-policy-test')
    assert repository.current(job) is False
    assert repository.commit_capture(job, material, ['PRIVATE_LATE_OUTPUT']) == []
    assert repository.list() == [] and services.db.fetch_all('SELECT * FROM memory_history') == []
    assert repository.job(job['id'])['state'] == 'cancelled'


def test_completed_test_policy_change_still_invalidates_earlier_memory_job(whole_memory):
    client, _, repository, _ = whole_memory
    study = start(whole_memory)
    evidence_id = commit(whole_memory, study)
    scope = ContextScope(kind=Scope.REVIEWED_ASSESSMENT, entity_id=study['id'])
    job = repository.claim(repository.enqueue(evidence_id, scope)['id'])
    material = repository.material(evidence_id, scope)
    active = start(whole_memory, mode='test', key='memory-policy-cycle')
    submitted = client.post(BASE + '/' + active['id'] + '/submit', headers={'Idempotency-Key': 'memory-submit-test'},
                            json={'expected_draft_revision': active['draft_revision']})
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()['policy']['assistance_allowed']
    assert repository.current(job) is False and repository.commit_capture(job, material, [material['text']]) == []


def test_capture_rejects_a_job_with_forged_source_hash_or_scope(whole_memory):
    _, _, repository, _ = whole_memory
    attempt = start(whole_memory)
    evidence_id = commit(whole_memory, attempt)
    scope = ContextScope(kind=Scope.REVIEWED_ASSESSMENT, entity_id=attempt['id'])
    job = repository.claim(repository.enqueue(evidence_id, scope)['id'])
    material = repository.material(evidence_id, scope)
    assert repository.current(job)
    for field, value in (('evidence_id', 'forged_evidence'), ('evidence_hash', '0' * 64),
                         ('scope', ContextScope(kind=Scope.GENERATED_PRACTICE, entity_id=attempt['id']).model_dump_json())):
        assert repository.current({**job, field: value}) is False
    assert repository.commit_capture({**job, 'evidence_hash': '0' * 64}, material, ['PRIVATE_FORGED']) == []
    assert repository.list() == []


def test_blanks_exclusions_and_forged_duplicate_evidence_never_enqueue(whole_memory):
    client, services, repository, _ = whole_memory
    active = start(whole_memory, mode='test')
    services.get('content').withdraw(active['current_item']['question_id'])
    result = client.post(BASE + '/' + active['id'] + '/submit', headers={'Idempotency-Key': 'memory-test-blanks'},
                         json={'expected_draft_revision': active['draft_revision']})
    assert result.status_code == 200, result.text
    assert result.json()['result']['excluded'] == 1 and result.json()['result']['unanswered'] == 2
    repository.scan()
    assert repository.jobs() == []
    original = services.db.fetch_one('SELECT * FROM learning_evidence LIMIT 1')
    services.db.execute('INSERT INTO learning_evidence VALUES(?,?,?,?,?,?)',
        ('forged_duplicate', original['kind'], original['topic_id'], original['entity_id'], original['payload_json'], original['created_at']))
    repository.scan()
    assert repository.jobs() == []


def test_typed_attempt_authority_ignores_overlapping_learn_tombstone_and_memory_delete_suppresses(whole_memory):
    _, services, repository, _ = whole_memory
    attempt = start(whole_memory)
    evidence_id = commit(whole_memory, attempt)
    services.db.mark_deleted('learn_thread', attempt['id'])
    scope = ContextScope(kind=Scope.REVIEWED_ASSESSMENT, entity_id=attempt['id'])
    fact, _ = capture(whole_memory, evidence_id, scope)
    assert repository.delete(fact['id'], fact['revision'])['deleted']
    repository.scan()
    with pytest.raises(ApiError) as suppressed:
        repository.material(evidence_id, scope)
    assert suppressed.value.code == 'memory_capture_suppressed' and repository.list() == []
