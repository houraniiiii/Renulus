"""Synthetic trusted native receipts; no second transcript or remote transport.

The exact shared 003 DDL comes from the integrating owner's 845c1f0c source when
it has not yet been composed into this lane. No parallel schema is defined here.
Production bridge publication and host/IPC acceptance belong to integration.
"""
from copy import deepcopy
import asyncio
import hashlib
import json
import subprocess
import sqlite3

import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.design_c_contracts import Dependency, EligibleInput, Identity
from renulus.harness_contracts import HarnessEngineReference, SavedConversationMapping, OPENCODE_SOURCE
from renulus.memory.lineage import AnswerInputs
from renulus.memory.models import ManualFact
from renulus.storage import utc_now

from .test_study_answer_capture import study_capture


@pytest.fixture
def native_receipt(study_capture, services):
    learn, memory, control = study_capture
    path = 'runtime/renulus/learn/migrations/003-harness-bridge.sql'
    source = services.paths.source_root / path
    sql = (source.read_text(encoding='utf-8') if source.is_file() else
        subprocess.check_output(['git', 'show', '845c1f0c:' + path],
            cwd=services.paths.source_root, encoding='utf-8'))
    services.db.apply_migration('learn-harness-memory-fixture-003', sql)
    _, run = learn.prepare('Synthetic native CKD question.', ContextScope(kind=Scope.STUDY),
        None, 'ckd', 'direct', 'synthetic-native-receipt')
    runtime = HarnessEngineReference(contract_version='harness/1', profile_id='synthetic-profile',
        store_id='synthetic-runtime', engine={'name': 'opencode', 'version': '2.0.26',
            'source_commit': OPENCODE_SOURCE}, session_id='ses_synthetic')
    mapping = SavedConversationMapping(contract_version='harness/1',
        conversation={'type': 'learn_thread', 'id': run.thread_id}, retention='saved', runtime=runtime)
    reference = {'version': 1, 'run_id': run.id, 'thread_id': run.thread_id,
        'runtime': runtime.model_dump(mode='json'), 'input_id': 'msg_user_native',
        'message_ids': ['msg_assistant_native'],
        'sha256': hashlib.sha256(control.answer.encode()).hexdigest(),
        'citations': [], 'inputs': [], 'dependencies': []}
    scope = ContextScope(kind=Scope.STUDY, entity_id=run.thread_id)
    evidence_id = 'learn-answer:' + run.id
    with services.db.transaction() as conn:
        conn.execute('INSERT INTO learn_harness_mappings(thread_id,profile_id,store_id,session_id,mapping_json) VALUES(?,?,?,?,?)',
            (run.thread_id, runtime.profile_id, runtime.store_id, runtime.session_id, mapping.model_dump_json()))
        conn.execute("INSERT INTO learn_harness_answers(run_id,thread_id,request_digest,state,input_id) VALUES(?,?,?,'submitted',?)",
            (run.id, run.thread_id, 'a' * 64, reference['input_id']))
        conn.execute('INSERT INTO learning_evidence VALUES(?,?,?,?,?,?)', (evidence_id, 'study-answer',
            'ckd', run.thread_id, json.dumps({'scope': scope.model_dump(mode='json'),
                'answer_reference': reference}), utc_now()))
    return learn, memory, control, run, reference, evidence_id, scope


def stage_and_publish(conn, memory, run, reference, evidence_id):
    # Explicit synthetic trusted bridge callback: same transaction as final
    # completion, exact staged immutable reference before M5 publication.
    conn.execute('UPDATE learn_harness_answers SET reference_json=? WHERE run_id=?',
        (json.dumps(reference), run.id))
    return memory.publish_answer_lineage_in(conn, evidence_id,
        inputs=tuple(EligibleInput.model_validate(value) for value in reference['inputs']),
        dependencies=tuple(Dependency.model_validate(value) for value in reference['dependencies']))


def finalize(conn, run, publication):
    conn.execute("UPDATE learn_harness_answers SET state='completed',publication_digest=? WHERE run_id=?",
        (publication, run.id))
    conn.execute("UPDATE learn_runs SET state='completed' WHERE id=?", (run.id,))


@pytest.mark.asyncio
async def test_staged_native_publication_finalizes_atomically_and_supplies_exact_history_pins(native_receipt, services):
    learn, memory, control, run, reference, evidence_id, scope = native_receipt
    try:
        with services.db.transaction() as conn:
            publication = stage_and_publish(conn, memory, run, reference, evidence_id)
            with pytest.raises(ApiError):
                memory.repository.lineage.check_in(conn, evidence_id)
            finalize(conn, run, publication)
        messages = [{'id': reference['message_ids'][0], 'run_id': run.id,
            'role': 'assistant', 'content': control.answer}]
        eligible, pins = memory.eligible_history(messages)
        assert eligible == messages and pins == (EligibleInput(kind='committed_evidence',
            dependency=Dependency(target=Identity(type='learning_evidence', id=evidence_id),
                expected_revision=publication)),)
        with services.db.transaction() as conn:
            assert memory.eligible_answer_references_in(conn, (reference,)) == pins
        assert not any(message['role'] == 'assistant' for message in learn.get_thread(run.thread_id)['messages'])
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_committed_native_receipt_scan_queues_once(native_receipt, services):
    _, memory, _, run, reference, evidence_id, scope = native_receipt
    try:
        memory.repository.scan()
        assert memory.repository.jobs() == []
        with services.db.transaction() as conn:
            publication = stage_and_publish(conn, memory, run, reference, evidence_id)
            finalize(conn, run, publication)
        memory.repository.scan()
        jobs = memory.repository.jobs()
        assert len(jobs) == 1
        assert jobs[0]['evidence_id'] == evidence_id
        assert ContextScope.model_validate_json(jobs[0]['scope']) == scope
        assert jobs[0]['state'] == 'queued' and jobs[0]['attempts'] == 0
        assert memory.repository.enqueue(evidence_id, scope, automatic=True) is None
        memory.repository.scan()
        assert memory.repository.jobs() == jobs
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_explicit_native_capture_resolves_without_physical_locks_and_commits_only_local_receipts(native_receipt, services, monkeypatch):
    _, memory, control, run, reference, evidence_id, scope = native_receipt
    resolutions, transcript_reads = [], []
    try:
        with services.db.transaction() as conn:
            publication = stage_and_publish(conn, memory, run, reference, evidence_id)
            finalize(conn, run, publication)
        connect = services.db.connect
        def tracked_connect():
            conn = connect()
            def authorizer(operation, table, column, database, trigger):
                if operation == sqlite3.SQLITE_READ and table == 'learn_messages' and column == 'content':
                    transcript_reads.append(column)
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK
            conn.set_authorizer(authorizer)
            return conn
        monkeypatch.setattr(services.db, 'connect', tracked_connect)

        class SyntheticCompletedResolver:
            async def resolve_completed_answer(self, supplied):
                assert supplied == reference
                assert not memory._lock._is_owned() and not memory._capture_state._is_owned()
                # A public writer must progress while the resolver's async
                # receive path runs. No canonical transaction spans this await.
                await asyncio.wait_for(asyncio.to_thread(memory.add, ManualFact(
                    text='Synthetic independent dialysis preference.', scope=ContextScope(kind=Scope.STUDY),
                    idempotency_key='native-resolver-writer')), 2)
                resolutions.append(supplied)
                return {'text': control.answer, 'digest': reference['sha256'],
                    'publication_digest': publication, 'input': AnswerInputs().model_dump(mode='json')}

        services.registry['completed_answer_resolver'] = SyntheticCompletedResolver()
        queued = memory.enqueue(evidence_id, scope)
        await memory.process_pending()
        assert resolutions == [reference] and transcript_reads == []
        assert memory.repository.job(queued['id'])['state'] == 'completed'
        assert any(row['source_id'] == evidence_id for row in memory.repository.list())
    finally:
        await memory.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('forgery', ['unstaged', 'input', 'mapping', 'version', 'empty-messages',
    'duplicate-messages', 'input-as-answer', 'raw-text', 'raw-citation', 'unknown-input'])
async def test_native_publication_rejects_unmatched_or_unbounded_reference_only_receipts(native_receipt, services, forgery):
    _, memory, _, run, reference, evidence_id, scope = native_receipt
    forged = deepcopy(reference)
    try:
        with pytest.raises(ApiError) as error:
            with services.db.transaction() as conn:
                if forgery == 'unstaged':
                    memory.publish_answer_lineage_in(conn, evidence_id, inputs=())
                else:
                    if forgery == 'input':
                        conn.execute("UPDATE learn_harness_answers SET input_id='another_input' WHERE run_id=?", (run.id,))
                    elif forgery == 'mapping':
                        conn.execute("UPDATE learn_harness_mappings SET session_id='another_session' WHERE thread_id=?", (run.thread_id,))
                    elif forgery == 'version':
                        forged['version'] = True
                    elif forgery == 'empty-messages':
                        forged['message_ids'] = []
                    elif forgery == 'duplicate-messages':
                        forged['message_ids'] *= 2
                    elif forgery == 'input-as-answer':
                        forged['message_ids'] = [forged['input_id']]
                    elif forgery == 'raw-text':
                        forged['text'] = 'Arbitrary text cannot become a reference receipt.'
                    elif forgery == 'raw-citation':
                        forged['citations'] = [{'text': 'Arbitrary raw source text.'}]
                    elif forgery == 'unknown-input':
                        forged['dependencies'] = [{'target': {'type': 'message', 'id': 'unknown_native'},
                            'expected_revision': 'unknown_publication'}]
                    conn.execute('UPDATE learning_evidence SET payload_json=? WHERE id=?',
                        (json.dumps({'scope': scope.model_dump(mode='json'), 'answer_reference': forged}), evidence_id))
                    stage_and_publish(conn, memory, run, forged, evidence_id)
        assert error.value.code in {'memory_answer_reference', 'memory_answer_unavailable', 'memory_dependency_unknown'}
        assert services.db.fetch_one('SELECT 1 FROM memory_answer_lineage WHERE evidence_id=?', (evidence_id,)) is None
        assert services.db.fetch_one('SELECT state FROM learn_harness_answers WHERE run_id=?', (run.id,))['state'] == 'submitted'
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_publication_callback_failure_rolls_back_staging_and_lineage(native_receipt, services):
    _, memory, _, run, reference, evidence_id, _ = native_receipt
    try:
        with pytest.raises(RuntimeError, match='callback failure'):
            with services.db.transaction() as conn:
                stage_and_publish(conn, memory, run, reference, evidence_id)
                raise RuntimeError('Synthetic final publication callback failure')
        receipt = services.db.fetch_one('SELECT state,reference_json,publication_digest FROM learn_harness_answers WHERE run_id=?', (run.id,))
        assert receipt == {'state': 'submitted', 'reference_json': None, 'publication_digest': None}
        assert services.db.fetch_one('SELECT 1 FROM memory_answer_lineage WHERE evidence_id=?', (evidence_id,)) is None
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_completed_native_reference_requires_exact_publication_digest_and_reference_for_history(native_receipt, services):
    _, memory, _, run, reference, evidence_id, _ = native_receipt
    try:
        with services.db.transaction() as conn:
            publication = stage_and_publish(conn, memory, run, reference, evidence_id)
            finalize(conn, run, publication)
            assert memory.eligible_answer_references_in(conn, (reference,))
            forged = deepcopy(reference)
            forged['message_ids'] = ['a_different_native_answer']
            assert memory.eligible_answer_references_in(conn, (forged,)) == ()
            conn.execute("UPDATE learn_harness_answers SET publication_digest=? WHERE run_id=?", ('f' * 64, run.id))
            assert memory.eligible_answer_references_in(conn, (reference,)) == ()
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_an_arbitrary_message_cannot_borrow_a_known_native_run_lineage(native_receipt, services):
    _, memory, _, run, reference, evidence_id, _ = native_receipt
    try:
        with services.db.transaction() as conn:
            publication = stage_and_publish(conn, memory, run, reference, evidence_id)
            finalize(conn, run, publication)
        messages = [{'id': 'not_the_published_native_message', 'run_id': run.id,
            'role': 'assistant', 'content': 'Arbitrary unrelated raw message content.'}]
        assert memory.eligible_history(messages) == ([], ())
    finally:
        await memory.close()
