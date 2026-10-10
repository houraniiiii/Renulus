"""Actual producers into canonical Memory; only remote transport is synthetic."""
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket

from fastapi.testclient import TestClient
import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.design_c_contracts import SavedTestVersion
from renulus.memory.models import digest
from renulus.memory.service import MemoryService
from renulus.server import create_app
from renulus.storage.backup import export_records
from renulus.storage.invalidation import (MEMORY_RESTORE_CAPTURE_PREFIX, bump_context_epoch,
    context_epoch_in)
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


@pytest.fixture
def ordinary_capture(whole_memory, monkeypatch):
    """Real Learn, ProviderManager, Mem0 and pinned public CPU helpers, offline."""
    _, services, _, _ = whole_memory
    helper_root = os.environ.get('RENULUS_MEMORY_HELPERS')
    if not helper_root or not (Path(helper_root) / 'manifest.json').is_file():
        pytest.skip('Explicit offline helper path was not supplied')
    helper_root = Path(helper_root)
    manifest = json.loads((helper_root / 'manifest.json').read_text(encoding='utf-8'))
    for record in manifest['groups']['embedding']['files']:
        source = helper_root / record['path']
        assert source.stat().st_size == record['size']
        assert hashlib.sha256(source.read_bytes()).hexdigest() == record['sha256']
        target = services.paths.helpers / record['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (services.paths.helpers / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    for operation in ('connect', 'connect_ex'):
        original = getattr(socket.socket, operation)
        def local_only(original):
            def guarded(sock, address):
                if isinstance(address, tuple) and address[0] in ('127.0.0.1', '::1', 'localhost'):
                    return original(sock, address)
                raise AssertionError('C5 capture attempted an external connection')
            return guarded
        monkeypatch.setattr(socket.socket, operation, local_only(original))
    provider = services.get('provider')
    provider._settings['connections']['codex'] = {
        'access_token': 'synthetic-c5-transport', 'expires_at': 9999999999}
    provider._settings['selected_provider'] = 'codex'
    provider._settings.setdefault('selected_models', {})['codex'] = 'gpt-6.1-sol'
    calls = []

    class SyntheticTransport:
        fail_inference = False

        async def stream(self, selected, model, token, messages):
            assert token == 'synthetic-c5-transport'
            inference = 'SYNTHETIC_C5_STUDY_REPLY' in json.dumps(messages)
            calls.append({'inference': inference, 'messages': messages})
            if inference and self.fail_inference:
                raise ApiError('synthetic_c5_provider_failure', 'Synthetic transport failure', 503, True)
            text = (json.dumps({'memory': [{'text': 'SYNTHETIC C5: compare albuminuria and eGFR.'}]})
                    if inference else 'SYNTHETIC_C5_STUDY_REPLY: Albuminuria and eGFR complement each other.')
            yield {'type': 'delta', 'text': text}
            yield {'type': 'completed', 'response_model': model}

    provider._transport = SyntheticTransport()
    # No optional external/source context is needed for this ordinary producer.
    services.registry.pop('retrieval', None)
    services.registry.pop('knowledge', None)
    return whole_memory, calls


async def ordinary_answer(services, key):
    learn = services.get('learn')
    question = 'SYNTHETIC C5 ordinary learning: explain albuminuria and eGFR.'
    _, run = learn.prepare(question, ContextScope(kind=Scope.STUDY), None, 'ckd', 'direct', key)
    events = [event async for event in learn.answer(run, question, 'direct', 'ckd')]
    assert events[-1].type == 'completed', [(event.type, event.data) for event in events]
    return 'learn-answer:' + run.id, ContextScope(kind=Scope.STUDY, entity_id=run.thread_id)


@pytest.mark.asyncio
@pytest.mark.parametrize('history', ['queued', 'no-job', 'restart'])
async def test_restore_blocks_ordinary_worker_until_explicit_capture_and_allows_new_learning(ordinary_capture, history):
    whole, calls = ordinary_capture
    client, services, repository, _ = whole
    memory = services.get('memory')
    try:
        evidence_id, scope = await ordinary_answer(services, 'c5-before-restore')
        assert repository.material(evidence_id, scope)['infer'] is True
        queued = repository.enqueue(evidence_id, scope) if history != 'no-job' else None
        before = len(calls)
        async with memory._process_lock:
            await memory.start()
            await asyncio.sleep(0)
            services.get('data_recovery').restore_json(export_records(services), confirm_backup_date=True)
            assert len(calls) == before
            if queued:
                interrupted = repository.job(queued['id'])
                assert (interrupted['state'], interrupted['error_code']) == ('cancelled', 'restore_interrupted')
            marker = services.db.fetch_one('SELECT value FROM preferences WHERE key=?',
                (MEMORY_RESTORE_CAPTURE_PREFIX + evidence_id,))
            assert marker is not None
        if history == 'restart':
            await memory.close()
            memory = MemoryService(services)
            services.registry['memory'] = memory
            repository = memory.repository
            await memory.start()
        # Join the real worker's pending processing, then perform another normal
        # pass: restored evidence must never reach extraction or a fresh job.
        assert (await memory.process_pending())['processed'] >= 0
        assert (await memory.process_pending())['processed'] == 0
        assert not [call for call in calls if call['inference']]
        assert not [job for job in repository.jobs() if job['evidence_id'] == evidence_id and job['state'] != 'cancelled']
        assert not [fact for fact in repository.list() if fact['source_id'] == evidence_id]
        if history == 'queued':
            active = start(whole, mode='test', key='c5-explicit-policy-start')
            denied = client.post('/api/v1/memory/captures', json={
                'evidence_id': evidence_id, 'scope': scope.model_dump(mode='json')})
            assert denied.status_code == 409 and denied.json()['error']['code'] == 'assistance_restricted'
            assert services.db.fetch_one('SELECT value FROM preferences WHERE key=?',
                (MEMORY_RESTORE_CAPTURE_PREFIX + evidence_id,)) == marker
            submitted = client.post(BASE + '/' + active['id'] + '/submit',
                headers={'Idempotency-Key': 'c5-explicit-policy-submit'},
                json={'expected_draft_revision': active['draft_revision']})
            assert submitted.status_code == 200, submitted.text
            wrong_scope = ContextScope(kind=Scope.STUDY, entity_id='c5-forged-source')
            refused = client.post('/api/v1/memory/captures', json={
                'evidence_id': evidence_id, 'scope': wrong_scope.model_dump(mode='json')})
            assert refused.status_code == 409 and refused.json()['error']['code'] == 'memory_evidence_scope'
            assert services.db.fetch_one('SELECT value FROM preferences WHERE key=?',
                (MEMORY_RESTORE_CAPTURE_PREFIX + evidence_id,)) == marker
        response = client.post('/api/v1/memory/captures', json={
            'evidence_id': evidence_id, 'scope': scope.model_dump(mode='json')})
        assert response.status_code == 202, response.text
        explicit = response.json()
        assert explicit['state'] == 'queued'
        assert services.db.fetch_one('SELECT value FROM preferences WHERE key=?',
            (MEMORY_RESTORE_CAPTURE_PREFIX + evidence_id,)) is None
        await memory.process_pending()
        assert repository.job(explicit['id'])['state'] == 'completed'
        assert len([call for call in calls if call['inference']]) == 1
        assert memory._engine.memory.__class__.__module__ == 'mem0.memory.main'
        assert memory._engine.memory.embedding_model.delegate.model.__class__.__module__.startswith('fastembed')
        assert memory._engine.memory.vector_store.client._client.__class__.__name__ == 'QdrantLocal'
        new_id, new_scope = await ordinary_answer(services, 'c5-after-restore')
        assert new_id != evidence_id
        assert services.db.fetch_one('SELECT value FROM preferences WHERE key=?',
            (MEMORY_RESTORE_CAPTURE_PREFIX + new_id,)) is None
        await memory.process_pending()
        fresh = [job for job in repository.jobs() if job['evidence_id'] == new_id]
        assert len(fresh) == 1 and fresh[0]['state'] == 'completed'
        assert len([call for call in calls if call['inference']]) == 2
    finally:
        await memory.close()
        await services.get('conversations').streaming.close()
        await services.get('provider').close()


@pytest.mark.asyncio
async def test_policy_only_interruption_still_recaptures_ordinary_inferred_material(ordinary_capture):
    whole, calls = ordinary_capture
    client, services, repository, _ = whole
    memory = services.get('memory')
    try:
        evidence_id, scope = await ordinary_answer(services, 'c5-policy-only')
        job = repository.claim(repository.enqueue(evidence_id, scope)['id'])
        material = repository.material(evidence_id, scope)
        active = start(whole, mode='test', key='c5-policy-start')
        assert repository.commit_capture(job, material, ['STALE_INFERENCE']) == []
        assert repository.job(job['id'])['error_code'] == 'boundary_policy_changed'
        assert (await memory.process_pending())['processed'] == 0
        assert not [call for call in calls if call['inference']]
        submitted = client.post(BASE + '/' + active['id'] + '/submit',
            headers={'Idempotency-Key': 'c5-policy-submit'},
            json={'expected_draft_revision': active['draft_revision']})
        assert submitted.status_code == 200, submitted.text
        assert (await memory.process_pending())['processed'] >= 1
        assert len([call for call in calls if call['inference']]) == 1
        assert len([row for row in repository.jobs() if row['evidence_id'] == evidence_id]) == 2
    finally:
        await memory.close()
        await services.get('conversations').streaming.close()
        await services.get('provider').close()


@pytest.mark.asyncio
async def test_actual_failed_foreign_job_global_retry_refuses_inference_until_explicit_post(ordinary_capture):
    whole, calls = ordinary_capture
    client, services, repository, _ = whole
    memory = services.get('memory')
    transport = services.get('provider')._transport
    try:
        evidence_id, scope = await ordinary_answer(services, 'c5-real-failed-retry')
        queued = repository.enqueue(evidence_id, scope)
        transport.fail_inference = True
        assert (await memory.process_pending())['processed'] >= 0
        assert repository.job(queued['id'])['state'] == 'failed'
        before = len([call for call in calls if call['inference']])
        assert before == 1
        # Simulate an imported failed execution with the destination's next
        # integer epoch, then run the actual restore and global Retry endpoint.
        with services.db.transaction() as conn:
            parts = queued['evidence_hash'].split(':')
            parts[-1] = str(context_epoch_in(conn) + 1)
            conn.execute('UPDATE memory_jobs SET evidence_hash=? WHERE id=?', (':'.join(parts), queued['id']))
        services.get('data_recovery').restore_json(export_records(services), confirm_backup_date=True)
        assert repository.job(queued['id'])['evidence_hash'] == repository.material(evidence_id, scope)['fingerprint']
        transport.fail_inference = False
        response = client.post('/api/v1/memory/retry')
        assert response.status_code == 200 and response.json()['processed'] == 0, response.text
        assert len([call for call in calls if call['inference']]) == before
        assert repository.job(queued['id'])['error_code'] == 'restore_interrupted'
        assert not [fact for fact in repository.list() if fact['source_id'] == evidence_id]
        key = MEMORY_RESTORE_CAPTURE_PREFIX + evidence_id
        assert services.db.fetch_one('SELECT value FROM preferences WHERE key=?', (key,)) is not None
        explicit = client.post('/api/v1/memory/captures', json={
            'evidence_id': evidence_id, 'scope': scope.model_dump(mode='json')})
        assert explicit.status_code == 202 and explicit.json()['state'] == 'queued', explicit.text
        assert explicit.json()['id'] == queued['id']
        await memory.process_pending()
        assert repository.job(queued['id'])['state'] == 'completed'
        assert len([call for call in calls if call['inference']]) == before + 1
        assert services.db.fetch_one('SELECT value FROM preferences WHERE key=?', (key,)) is None
        assert len([fact for fact in repository.list() if fact['source_id'] == evidence_id]) == 1
    finally:
        await memory.close()
        await services.get('conversations').streaming.close()
        await services.get('provider').close()


def test_equal_foreign_restore_fingerprint_requires_explicit_same_row_requeue_and_fences_old_execution(whole_memory):
    client, services, repository, _ = whole_memory
    attempt = start(whole_memory, key='c5-foreign-attempt')
    evidence_id = commit(whole_memory, attempt, key='c5-foreign-answer')
    scope = ContextScope(kind=Scope.REVIEWED_ASSESSMENT, entity_id=attempt['id'])
    queued = repository.enqueue(evidence_id, scope)
    # An imported profile may already have the destination's next integer epoch.
    with services.db.transaction() as conn:
        parts = queued['evidence_hash'].split(':')
        parts[-1] = str(context_epoch_in(conn) + 1)
        conn.execute('UPDATE memory_jobs SET evidence_hash=? WHERE id=?', (':'.join(parts), queued['id']))
    foreign = repository.claim(queued['id'])
    services.get('data_recovery').restore_json(export_records(services), confirm_backup_date=True)
    assert foreign['evidence_hash'] == repository.material(evidence_id, scope)['fingerprint']
    assert repository.enqueue(evidence_id, scope, automatic=True) is None
    assert repository.job(queued['id'])['state'] == 'cancelled'
    response = client.post('/api/v1/memory/captures', json={
        'evidence_id': evidence_id, 'scope': scope.model_dump(mode='json')})
    assert response.status_code == 202, response.text
    restored = response.json()
    assert restored['id'] == foreign['id'] and restored['state'] == 'queued'
    assert restored['attempts'] == foreign['attempts']
    fresh = repository.claim(restored['id'])
    assert fresh['attempts'] == foreign['attempts'] + 1
    material = repository.material(evidence_id, scope)
    assert repository.commit_capture(foreign, material, ['FOREIGN_OLD_EXECUTION']) == []
    assert repository.job(fresh['id'])['state'] == 'running'
    assert len(repository.commit_capture(fresh, material, ['FORGED_KEY_TEXT'])) == 1
    assert repository.list()[0]['text'] == material['text']


@pytest.mark.parametrize('invalid', ['deleted-source', 'forged-payload'])
def test_explicit_capture_rechecks_restored_whole_source_and_retains_marker_on_refusal(whole_memory, invalid):
    client, services, repository, _ = whole_memory
    attempt = start(whole_memory, key='c5-explicit-invalid-attempt')
    evidence_id = commit(whole_memory, attempt, key='c5-explicit-invalid-answer')
    services.get('data_recovery').restore_json(export_records(services), confirm_backup_date=True)
    key = MEMORY_RESTORE_CAPTURE_PREFIX + evidence_id
    before = services.db.fetch_one('SELECT * FROM preferences WHERE key=?', (key,))
    if invalid == 'deleted-source':
        services.db.mark_deleted('test_attempt', attempt['id'])
    else:
        services.db.execute('UPDATE learning_evidence SET payload_json=? WHERE id=?',
            (json.dumps({'correct': True, 'bank_cohort_eligible': True}), evidence_id))
    response = client.post('/api/v1/memory/captures', json={'evidence_id': evidence_id,
        'scope': {'kind': 'reviewed-assessment', 'entity_id': attempt['id']}})
    assert response.status_code == 409 and response.json()['error']['code'] == 'memory_evidence_invalid'
    assert services.db.fetch_one('SELECT * FROM preferences WHERE key=?', (key,)) == before
    assert repository.jobs() == [] and repository.list() == []


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


@pytest.mark.asyncio
@pytest.mark.parametrize('boundary', ['policy_cycle', 'epoch', 'restore'])
async def test_boundary_interruption_requeues_one_fresh_canonical_scalar_capture(whole_memory, boundary):
    client, services, repository, _ = whole_memory
    attempt = start(whole_memory)
    evidence_id = commit(whole_memory, attempt)
    scope = ContextScope(kind=Scope.REVIEWED_ASSESSMENT, entity_id=attempt['id'])
    job = repository.claim(repository.enqueue(evidence_id, scope)['id'])
    material = repository.material(evidence_id, scope)
    if boundary == 'policy_cycle':
        active = start(whole_memory, mode='test', key='memory-recovery-policy-test')
        assert repository.commit_capture(job, material, ['PRIVATE_LATE_OUTPUT']) == []
        repository.scan()
        assert len(repository.jobs()) == 1 and repository.list() == []
        submitted = client.post(BASE + '/' + active['id'] + '/submit',
            headers={'Idempotency-Key': 'memory-recovery-policy-submit'},
            json={'expected_draft_revision': active['draft_revision']})
        assert submitted.status_code == 200, submitted.text
        expected_error = 'boundary_policy_changed'
    elif boundary == 'epoch':
        with services.db.transaction() as conn:
            bump_context_epoch(conn)
        expected_error = 'boundary_context_changed'
    else:
        bundle = export_records(services)
        services.get('data_recovery').restore_json(bundle, confirm_backup_date=True)
        expected_error = 'restore_interrupted'
    assert not repository.current(job)
    assert repository.commit_capture(job, material, ['PRIVATE_LATE_OUTPUT']) == []
    stale = repository.job(job['id'])
    assert stale['state'] == 'cancelled' and stale['error_code'] == expected_error
    assert repository.list() == []
    repository.scan()
    repository.scan()
    fresh = [row for row in repository.jobs() if row['id'] != job['id']]
    assert len(fresh) == 1 and fresh[0]['state'] == 'queued'
    assert fresh[0]['evidence_hash'] != job['evidence_hash']
    memory = services.get('memory')
    assert (await memory.process_pending())['processed'] == 1
    facts = repository.list()
    assert len(facts) == 1 and facts[0]['source_id'] == evidence_id
    assert facts[0]['text'] == repository.material(evidence_id, scope)['text']
    assert 'PRIVATE_' not in facts[0]['text']
    assert repository.job(job['id'])['error_code'] == expected_error
    with services.db.transaction() as conn:
        bump_context_epoch(conn)
    repository.scan()
    assert len(repository.jobs()) == 2
    assert (await memory.process_pending())['processed'] == 0
    await memory.close()


@pytest.mark.parametrize('terminal', ['explicit_cancel', 'explicit_after_restore', 'suppressed',
    'forged', 'evidence_deleted', 'version_deleted', 'source_changed', 'failed'])
def test_scan_never_requeues_terminal_capture_after_boundary(whole_memory, terminal):
    _, services, repository, version_id = whole_memory
    attempt = start(whole_memory)
    evidence_id = commit(whole_memory, attempt)
    scope = ContextScope(kind=Scope.REVIEWED_ASSESSMENT, entity_id=attempt['id'])
    job = repository.claim(repository.enqueue(evidence_id, scope)['id'])
    material = repository.material(evidence_id, scope)
    if terminal == 'explicit_after_restore':
        services.get('data_recovery').restore_json(export_records(services), confirm_backup_date=True)
        repository.cancel(job['id'])
    elif terminal == 'explicit_cancel':
        repository.cancel(job['id'])
    elif terminal == 'failed':
        repository.fail(job['id'], 'memory_capture_failed')
    with services.db.transaction() as conn:
        bump_context_epoch(conn)
        if terminal == 'suppressed':
            conn.execute('INSERT INTO memory_suppression VALUES(?,?)',
                ('evidence:' + evidence_id, '2026-10-10T12:00:00Z'))
        elif terminal == 'forged':
            conn.execute('UPDATE learning_evidence SET payload_json=? WHERE id=?',
                (json.dumps({'reviewed': True, 'private_key': 'PRIVATE_FORGED'}), evidence_id))
        elif terminal == 'evidence_deleted':
            services.db.mark_deleted('learning_evidence', evidence_id, conn)
        elif terminal == 'version_deleted':
            conn.execute('DELETE FROM assessment_test_versions WHERE id=?', (version_id,))
            reconcile_unavailable_references(conn)
        elif terminal == 'source_changed':
            # Even a canonical scalar row change must not masquerade as an epoch-only retry.
            conn.execute('UPDATE learning_evidence SET created_at=? WHERE id=?',
                ('2026-10-10T12:00:00Z', evidence_id))
    assert repository.commit_capture(job, material, ['PRIVATE_LATE_OUTPUT']) == []
    repository.scan()
    repository.scan()
    assert len(repository.jobs()) == 1 and repository.list() == []
    if terminal.startswith('explicit'):
        assert repository.job(job['id'])['error_code'] == 'explicit_cancelled'


@pytest.mark.asyncio
async def test_worker_queued_before_test_waits_then_recovers_without_inference(whole_memory):
    client, services, repository, _ = whole_memory
    attempt = start(whole_memory)
    evidence_id = commit(whole_memory, attempt)
    scope = ContextScope(kind=Scope.REVIEWED_ASSESSMENT, entity_id=attempt['id'])
    job = repository.enqueue(evidence_id, scope)
    active = start(whole_memory, mode='test', key='memory-queued-test')
    memory = services.get('memory')
    assert (await memory.process_pending())['processed'] == 0
    assert repository.job(job['id'])['error_code'] == 'boundary_policy_changed'
    assert repository.list() == []
    assert (await memory.process_pending())['processed'] == 0
    assert len(repository.jobs()) == 1
    response = client.post(BASE + '/' + active['id'] + '/submit',
        headers={'Idempotency-Key': 'memory-queued-submit'},
        json={'expected_draft_revision': active['draft_revision']})
    assert response.status_code == 200, response.text
    assert (await memory.process_pending())['processed'] == 1
    assert len(repository.jobs()) == 2 and len(repository.list()) == 1
    assert (await memory.process_pending())['processed'] == 0
    await memory.close()


def test_invalid_source_after_restore_is_terminal_not_polled_again(whole_memory):
    _, services, repository, _ = whole_memory
    attempt = start(whole_memory)
    evidence_id = commit(whole_memory, attempt)
    scope = ContextScope(kind=Scope.REVIEWED_ASSESSMENT, entity_id=attempt['id'])
    job = repository.enqueue(evidence_id, scope)
    services.get('data_recovery').restore_json(export_records(services), confirm_backup_date=True)
    services.db.execute('UPDATE learning_evidence SET payload_json=? WHERE id=?',
        (json.dumps({'reviewed': True, 'private_key': 'PRIVATE_FORGED'}), evidence_id))
    repository.scan()
    assert repository.job(job['id'])['error_code'] == 'memory_evidence_invalid'
    services.db.execute('DELETE FROM learning_evidence WHERE id=?', (evidence_id,))
    repository.scan()
    assert len(repository.jobs()) == 1 and repository.list() == []


def test_existing_whole_capture_hash_is_accepted_only_at_exact_original_boundary(whole_memory):
    _, services, repository, _ = whole_memory
    attempt = start(whole_memory)
    evidence_id = commit(whole_memory, attempt)
    scope = ContextScope(kind=Scope.REVIEWED_ASSESSMENT, entity_id=attempt['id'])
    queued = repository.enqueue(evidence_id, scope)
    with services.db.transaction() as conn:
        scalar = services.get('whole_attempts').committed_evidence_in(conn, evidence_id)
    previous_hash = digest({'evidence': scalar['revision'], 'policy_revision': 1, 'context_epoch': 0})
    services.db.execute('UPDATE memory_jobs SET evidence_hash=? WHERE id=?', (previous_hash, queued['id']))
    job = repository.claim(queued['id'])
    assert repository.current(job)
    with services.db.transaction() as conn:
        bump_context_epoch(conn)
    assert not repository.current(job)
    assert repository.commit_capture(job, {}, ['PRIVATE_LATE_OLD_JOB']) == []
    repository.scan()
    assert repository.job(job['id'])['error_code'] == 'memory_fingerprint_unversioned'
    assert len(repository.jobs()) == 1 and repository.list() == []
