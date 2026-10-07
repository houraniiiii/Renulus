import json

import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.memory.models import ManualFact
from renulus.memory.repository import MemoryRepository
from renulus.storage import utc_now

from .conftest import evidence


def manual(text='Study glomerular filtration mechanisms.', key='add-1', **kwargs):
    return ManualFact(text=text, idempotency_key=key, scope=ContextScope(kind=Scope.STUDY), **kwargs)


def test_idempotence_conflict_and_distinct_learning(repository):
    first = repository.add(manual(topic_id='physiology'))
    assert repository.add(manual(topic_id='physiology'))['id'] == first['id']
    assert repository.add(manual(text='  study glomerular filtration mechanisms.  ',
                                 key='normalised', topic_id='physiology'))['id'] == first['id']
    with pytest.raises(ApiError, match='request key'):
        repository.add(manual(text='Another note', topic_id='physiology'))
    contextual = repository.add(manual(key='different-context', topic_id='ckd'))
    assert contextual['id'] != first['id']
    assert len(repository.list()) == 2


def test_edit_revision_history_purge_and_delete(repository, services):
    fact = repository.add(manual())
    edited = repository.edit(fact['id'], 'Use the corrected educational note.', 1)
    assert edited['revision'] == 2
    assert [x['text'] for x in repository.history(fact['id'])] == [fact['text'], edited['text']]
    with pytest.raises(ApiError) as error:
        repository.edit(fact['id'], 'Late summary must not replace a correction.', 1)
    assert error.value.code == 'memory_revision_conflict'
    assert repository.purge_history(fact['id']) == {'purged': True}
    assert repository.history(fact['id']) == []
    assert repository.get(fact['id'])['text'] == edited['text']
    with pytest.raises(ApiError):
        repository.delete(fact['id'], 1)
    assert repository.delete(fact['id'], 2)['deleted']
    assert repository.delete(fact['id'], 2)['deleted']
    assert services.db.is_deleted('memory_fact', fact['id'])
    assert repository.list() == []
    assert services.db.fetch_all('SELECT * FROM memory_history') == []
    with pytest.raises(ApiError):
        repository.add(manual())


@pytest.mark.parametrize('kind', [Scope.TEMPORARY_CASE, Scope.UNCLASSIFIED, Scope.SAVED_CASE])
def test_excluded_scope_does_not_write_payload_or_operation(repository, services, kind):
    sentinel = 'SYNTHETIC_TEMPORARY_CASE_MUST_NEVER_TOUCH_MEMORY_3820'
    request = ManualFact(text=sentinel, idempotency_key=sentinel, scope=ContextScope(kind=kind))
    for action in (lambda: repository.add(request),
                   lambda: repository.enqueue(sentinel, request.scope)):
        with pytest.raises(ApiError) as error:
            action()
        assert error.value.code == 'memory_scope_excluded'
    for table in ('memory_facts', 'memory_history', 'memory_requests', 'memory_jobs', 'memory_sources'):
        assert services.db.fetch_all('SELECT * FROM ' + table) == []
    assert not (services.paths.state / 'memory-engine-bootstrap').exists()
    assert all(sentinel.encode() not in path.read_bytes() for path in services.paths.root.rglob('*') if path.is_file())


def test_durable_jobs_restart_cancel_and_source_revision_guard(repository, services):
    scope = evidence(services)
    job = repository.enqueue('evidence-1', scope)
    assert repository.enqueue('evidence-1', scope)['id'] == job['id']
    claimed = repository.claim(job['id'])
    assert claimed['state'] == 'running'
    restarted = MemoryRepository(services)
    assert restarted.job(job['id'])['state'] == 'queued'
    claimed = restarted.claim(job['id'])
    payload = {'scope': scope.model_dump(mode='json'), 'general_learning': True, 'text': 'Newer source revision.'}
    services.db.execute('UPDATE learning_evidence SET payload_json=? WHERE id=?',
                        (json.dumps(payload), 'evidence-1'))
    assert not restarted.current(claimed)
    assert restarted.commit_capture(claimed, {'unused': True}, ['late old result']) == []
    assert restarted.job(job['id'])['state'] == 'cancelled'
    assert restarted.list() == []


def test_capture_dedup_delete_suppresses_the_same_evidence(repository, services):
    scope = evidence(services)
    job = repository.claim(repository.enqueue('evidence-1', scope)['id'])
    material = repository.material('evidence-1', scope)
    identifiers = repository.commit_capture(job, material, [material['text'], material['text']])
    assert len(set(identifiers)) == 1
    assert len(repository.list()) == 1
    identifier = identifiers[0]
    repository.delete(identifier, 1)
    with pytest.raises(ApiError) as error:
        repository.enqueue('evidence-1', scope)
    assert error.value.code == 'memory_capture_suppressed'
    assert repository.commit_capture(job, material, ['resurrected deleted text']) == []
    assert repository.list() == []


def test_observed_assessment_and_study_interest_producers_without_bank_payload(repository, services):
    scope = ContextScope(kind=Scope.REVIEWED_ASSESSMENT, entity_id='assessment-1')
    payload = {'scope': scope.model_dump(mode='json'), 'mode': 'reviewed', 'correct': False,
               'score_bucket': 'fresh', 'objective_id': 'transplant:rejection', 'question_id': 'bank-private-key'}
    services.db.execute('INSERT INTO learning_evidence VALUES(?,?,?,?,?,?)',
                        ('attempt-1', 'assessment-answer', 'transplant', 'attempt-1', json.dumps(payload), utc_now()))
    material = repository.material('attempt-1', scope)
    assert material['kind'] == 'mistake' and material['infer'] is False
    assert 'transplant:rejection' in material['text']
    assert 'bank-private-key' not in material['text']
    assert 'fresh' in material['text']
    services.db.execute('INSERT INTO learning_evidence VALUES(?,?,?,?,?,?)',
        ('learn:run-1', 'study-interest', 'ckd', 'thread-1',
         json.dumps({'topic_id': 'ckd', 'activity': 'explain'}), utc_now()))
    study = repository.material('learn:run-1', ContextScope(kind=Scope.STUDY, entity_id='thread-1'))
    assert study['kind'] == 'study-interest' and 'ckd' in study['text']
    services.db.mark_deleted('learn_thread', 'thread-1')
    with pytest.raises(ApiError):
        repository.material('learn:run-1', ContextScope(kind=Scope.STUDY, entity_id='thread-1'))


def test_scope_cannot_be_relabelled_or_inferred_from_a_case(repository, services):
    temporary = ContextScope(kind=Scope.TEMPORARY_CASE, entity_id='temporary-1')
    evidence(services, scope=temporary)
    with pytest.raises(ApiError) as error:
        repository.enqueue('evidence-1', ContextScope(kind=Scope.STUDY, entity_id='temporary-1'))
    assert error.value.code == 'memory_scope_excluded'
    assert repository.jobs() == []
    assert repository.list() == []


@pytest.mark.parametrize('declared', ['temporary-case', 'saved-case', 'unclassified', None])
def test_ineligible_classification_is_rejected_before_reading_producer_text(repository, services, monkeypatch, declared):
    payload = {'general_learning': True, 'text': 'SYNTHETIC_INELIGIBLE_PRODUCER_5291'}
    if declared is not None:
        payload['scope'] = {'kind': declared}
    services.db.execute('INSERT INTO learning_evidence VALUES(?,?,?,?,?,?)',
        ('excluded-evidence', 'learning-point', None, None, json.dumps(payload), utc_now()))
    fetch_one = services.db.fetch_one
    def classified_reads(sql, parameters=()):
        assert 'SELECT * FROM learning_evidence' not in sql
        return fetch_one(sql, parameters)
    monkeypatch.setattr(services.db, 'fetch_one', classified_reads)
    with pytest.raises(ApiError):
        repository.enqueue('excluded-evidence', ContextScope(kind=Scope.STUDY))
    assert repository.jobs() == []
    assert repository.list() == []


def test_scan_reaches_eligible_evidence_beyond_invalid_page_without_copying_cases(repository, services):
    # More than one scan page of invalid but declared input must not starve a
    # later valid record. Malformed JSON and case scopes are excluded too.
    for number in range(105):
        evidence(services, f'invalid-{number:03}', text='   ')
    services.db.execute('INSERT INTO learning_evidence VALUES(?,?,?,?,?,?)',
        ('malformed-1', 'learning-point', None, None, '{broken', utc_now()))
    evidence(services, 'temporary-1', scope=ContextScope(kind=Scope.TEMPORARY_CASE))
    evidence(services, 'saved-1', scope=ContextScope(kind=Scope.SAVED_CASE))
    evidence(services, 'unclassified-1', scope=ContextScope(kind=Scope.UNCLASSIFIED))
    evidence(services, 'valid-last')
    repository.scan()
    assert [job['evidence_id'] for job in repository.jobs()] == ['valid-last']
    assert repository.list() == []
    repository.scan()
    assert len(repository.jobs()) == 1
