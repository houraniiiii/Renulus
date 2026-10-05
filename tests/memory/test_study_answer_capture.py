"""Real Learn producer and Mem0 OSS; controlled subscription and vector boundaries."""
import asyncio
import hashlib
import json
import socket
from types import SimpleNamespace

import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.learn.service import LearnService
from renulus.memory.service import MemoryService


ANSWERS = {
    'ckd': 'CKD_STUDY_REPLY: Albuminuria and eGFR describe complementary aspects of kidney disease.',
    'transplant': 'TRANSPLANT_STUDY_REPLY: Cellular and antibody-mediated rejection involve different immune mechanisms.',
}
POINTS = {
    'ckd': 'Albuminuria and eGFR describe complementary aspects of kidney disease.',
    'transplant': 'Cellular and antibody-mediated rejection involve different immune mechanisms.',
}


@pytest.fixture
def study_capture(services, monkeypatch):
    services.db.apply_migration('learn-capture-test',
        (services.paths.source_root / 'runtime/renulus/learn/schema.sql').read_text(encoding='utf-8'))
    learn = LearnService(services)
    services.registry['learn'] = learn
    control = SimpleNamespace(calls=[], fail=False, cancel_explain=False, pause=False,
        entered=asyncio.Event(), release=asyncio.Event(), cancelled=[], answer=ANSWERS['ckd'])

    class Provider:
        async def stream(self, messages, **kwargs):
            control.calls.append({'messages': messages, **kwargs})
            if kwargs['purpose'] == 'memory-extraction':
                control.entered.set()
                if control.pause:
                    await asyncio.wait_for(control.release.wait(), 5)
                combined = json.dumps(messages)
                topic = 'transplant' if 'TRANSPLANT_STUDY_REPLY' in combined else 'ckd'
                yield json.dumps({'memory': [{'text': POINTS[topic]}]})
            else:
                if control.fail:
                    raise ApiError('synthetic_explain_failure', 'Synthetic failure', 503)
                yield control.answer
                if control.cancel_explain:
                    await learn.cancel(kwargs['run_id'])
                    yield 'LATE_CANCELLED_ANSWER_MUST_NOT_CAPTURE'

        async def cancel(self, identifier):
            control.cancelled.append(identifier)
            return True

    config = {'model_id': 'BAAI/bge-small-en-v1.5', 'dimensions': 384, 'max_tokens': 512,
        'local_files_only': True, 'cpu_threads': 2, 'fingerprint': 'controlled-study-capture',
        'model_path': services.paths.helpers / 'model',
        'tokenizer_path': services.paths.helpers / 'model/tokenizer.json',
        'cache_dir': services.paths.cache / 'embedding'}
    services.registry['helpers'] = SimpleNamespace(embedding_config=lambda: config)

    class Embedding:
        def __init__(self):
            self.config = config
        def embed(self, text, memory_action='add'):
            if len(text.split()) > 512:
                raise ApiError('memory_embedding_budget', 'Controlled selected-helper token limit', 422)
            vector = [0.0] * 384
            vector[int(hashlib.sha256(text.encode()).hexdigest()[:4], 16) % 384] = 1.0
            return vector
        def embed_batch(self, texts, memory_action='add'):
            return [self.embed(text, memory_action) for text in texts]

    connect = socket.socket.connect
    def local_only(sock, address):
        if isinstance(address, tuple) and address[0] in ('127.0.0.1', '::1', 'localhost'):
            return connect(sock, address)
        raise AssertionError('Study capture attempted a remote provider/model call')
    monkeypatch.setattr(socket.socket, 'connect', local_only)
    services.registry['provider'] = Provider()
    memory = MemoryService(services)
    monkeypatch.setattr(memory, '_get_embedding', lambda: Embedding())
    services.registry['memory'] = memory
    return learn, memory, control


async def explain(learn, control, topic='ckd', key='ordinary-1', scope=None):
    control.answer = ANSWERS[topic]
    question = ('RAW_CASE_SENTINEL_NEVER_MEMORY: ' if scope and scope.kind != Scope.STUDY
                else 'USER_PROMPT_NEVER_MEMORY: Explain ') + topic
    replay, run = learn.prepare(question, scope or ContextScope(kind=Scope.STUDY),
        None, topic, 'direct', key)
    if replay:
        return replay, []
    flow = [event async for event in learn.answer(run, question, 'direct', topic)]
    return run, flow


@pytest.mark.asyncio
async def test_completed_study_replies_produce_general_mem0_points_across_topics(study_capture, services):
    learn, memory, control = study_capture
    try:
        for topic in ('ckd', 'transplant'):
            _, flow = await explain(learn, control, topic, 'answer-' + topic)
            assert flow[-1].type == 'completed'
        await memory.process_pending()
        points = [row for row in memory.repository.list() if row['kind'] == 'learning-point']
        assert {(row['topic_id'], row['text']) for row in points} == set(POINTS.items())
        assert memory._engine.memory.__class__.__module__ == 'mem0.memory.main'
        calls = [row for row in control.calls if row['purpose'] == 'memory-extraction']
        assert len(calls) == 2
        assert all('USER_PROMPT_NEVER_MEMORY' not in json.dumps(row['messages']) + row['system'] for row in calls)
        assert all('model' not in row and row['scope'].kind == Scope.STUDY for row in calls)
        evidence = services.db.fetch_all("SELECT payload_json FROM learning_evidence WHERE kind='study-answer'")
        assert len(evidence) == 2
        assert all('STUDY_REPLY' not in row['payload_json'] and 'USER_PROMPT' not in row['payload_json'] for row in evidence)
        await explain(learn, control, 'ckd', 'answer-ckd')
        await memory.process_pending()
        assert len([row for row in control.calls if row['purpose'] == 'memory-extraction']) == 2
        assert len([row for row in memory.repository.list() if row['kind'] == 'learning-point']) == 2
    finally:
        await memory.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['failed', 'cancelled', 'temporary-case', 'unclassified'])
async def test_failed_cancelled_and_case_explanations_never_produce_answer_capture(study_capture, services, mode):
    learn, memory, control = study_capture
    try:
        control.fail = mode == 'failed'
        control.cancel_explain = mode == 'cancelled'
        scope = ContextScope(kind=mode) if mode in ('temporary-case', 'unclassified') else None
        _, flow = await explain(learn, control, key='excluded-' + mode, scope=scope)
        assert flow[-1].type == ('error' if mode == 'failed' else 'cancelled' if mode == 'cancelled' else 'completed')
        await memory.process_pending()
        assert services.db.fetch_all("SELECT id FROM learning_evidence WHERE kind='study-answer'") == []
        assert not [row for row in control.calls if row['purpose'] == 'memory-extraction']
        assert memory.repository.list() == []
    finally:
        await memory.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ['thread-delete', 'answer-version-change', 'capture-cancel'])
async def test_late_delete_version_change_or_capture_cancel_blocks_mem0_commit(study_capture, services, action):
    learn, memory, control = study_capture
    task = None
    try:
        run, _ = await explain(learn, control)
        control.pause = True
        task = asyncio.create_task(memory.process_pending())
        await asyncio.wait_for(control.entered.wait(), 5)
        job = next(row for row in memory.repository.jobs() if row['evidence_id'] == 'learn-answer:' + run.id)
        if action == 'thread-delete':
            await learn.delete_thread(run.thread_id)
        elif action == 'answer-version-change':
            services.db.execute("UPDATE learn_messages SET content='SYNTHETIC_CHANGED_ANSWER_VERSION' WHERE run_id=? AND role='assistant'", (run.id,))
        else:
            assert (await memory.cancel(job['id']))['state'] == 'cancelled'
        control.release.set()
        await task
        assert memory.repository.job(job['id'])['state'] == 'cancelled'
        assert [row for row in memory.repository.list() if row['kind'] == 'learning-point'] == []
    finally:
        control.release.set()
        if task:
            await task
        await memory.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ['edit', 'delete'])
async def test_corrected_or_deleted_auto_point_cannot_be_recaptured(study_capture, action):
    learn, memory, control = study_capture
    try:
        run, _ = await explain(learn, control)
        await memory.process_pending()
        point = next(row for row in memory.repository.list() if row['kind'] == 'learning-point')
        if action == 'edit':
            changed = memory.edit(point['id'], 'Learner correction owns this learning point.', point['revision'])
            assert changed['revision'] == 2
        else:
            assert memory.delete(point['id'], point['revision'])['deleted']
        with pytest.raises(ApiError) as caught:
            memory.enqueue('learn-answer:' + run.id, ContextScope(kind=Scope.STUDY, entity_id=run.thread_id))
        assert caught.value.code == 'memory_capture_suppressed'
        await memory.process_pending(retry=True)
        assert len([row for row in control.calls if row['purpose'] == 'memory-extraction']) == 1
        remaining = [row for row in memory.repository.list() if row['kind'] == 'learning-point']
        assert [row['text'] for row in remaining] == (['Learner correction owns this learning point.'] if action == 'edit' else [])
    finally:
        await memory.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('guard', ['user-reference', 'case-reference', 'failed-run', 'deleted-thread', 'temporary-case', 'saved-case', 'unclassified'])
async def test_reference_eligibility_and_deletion_are_checked_before_any_body_read(study_capture, services, monkeypatch, guard):
    import sqlite3
    learn, memory, control = study_capture
    try:
        run, _ = await explain(learn, control)
        identifier = 'learn-answer:' + run.id
        row = services.db.fetch_one('SELECT payload_json FROM learning_evidence WHERE id=?', (identifier,))
        payload = json.loads(row['payload_json'])
        if guard == 'user-reference':
            user = services.db.fetch_one("SELECT id FROM learn_messages WHERE run_id=? AND role='user'", (run.id,))
            payload['answer_reference']['message_id'] = user['id']
        elif guard == 'case-reference':
            from renulus.storage import utc_now
            services.db.apply_migration('saved-case-reference-test',
                (services.paths.source_root / 'runtime/renulus/cases/schema.sql').read_text(encoding='utf-8'))
            now = utc_now()
            messages = [{'id': 'message_case_reference', 'role': 'assistant',
                         'content': 'CASE_BODY_SENTINEL_MUST_NOT_FETCH_OR_CAPTURE', 'created_at': now}]
            services.db.execute('INSERT INTO case_sessions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                ('case_reference', 1, 'daily', 'Synthetic case', 'RAW_CASE_SENTINEL',
                 json.dumps(messages), None, 0, 0, now, now, now))
            # A forged ordinary Study label must not redirect resolution to Case.
            payload['answer_reference']['message_id'] = 'message_case_reference'
        elif guard == 'failed-run':
            services.db.execute("UPDATE learn_runs SET state='failed' WHERE id=?", (run.id,))
        elif guard == 'deleted-thread':
            services.db.mark_deleted('learn_thread', run.thread_id)
        else:
            payload['scope']['kind'] = guard
            payload['text'] = 'CASE_BODY_SENTINEL_MUST_NOT_FETCH_OR_CAPTURE'
        services.db.execute('UPDATE learning_evidence SET payload_json=? WHERE id=?', (json.dumps(payload), identifier))
        connect = services.db.connect
        def metadata_only_connection():
            conn = connect()
            def authorize(action, table, column, *_):
                if action == sqlite3.SQLITE_READ and (table.startswith('case') or (table == 'learn_messages' and column == 'content')):
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK
            conn.set_authorizer(authorize)
            return conn
        monkeypatch.setattr(services.db, 'connect', metadata_only_connection)
        with pytest.raises(ApiError) as caught:
            memory.repository.material(identifier, ContextScope(kind=Scope.STUDY, entity_id=run.thread_id))
        expected = 'memory_answer_unavailable' if guard in ('user-reference', 'case-reference', 'failed-run') else 'memory_evidence_deleted' if guard == 'deleted-thread' else 'memory_scope_excluded'
        assert caught.value.code == expected
        assert not [row for row in control.calls if row['purpose'] == 'memory-extraction']
    finally:
        monkeypatch.undo()
        await memory.close()


@pytest.mark.asyncio
async def test_source_reply_deleted_after_inference_fences_canonical_commit(study_capture, services, monkeypatch):
    learn, memory, control = study_capture
    commit = memory.repository.commit_capture
    try:
        run, _ = await explain(learn, control)
        reply = services.db.fetch_one("SELECT id FROM learn_messages WHERE run_id=? AND role='assistant'", (run.id,))
        def delete_before_commit(job, material, texts):
            if material['infer']:
                assert texts == [POINTS['ckd']]
                with services.db.transaction() as conn:
                    conn.execute('DELETE FROM learn_messages WHERE id=?', (reply['id'],))
                    services.db.mark_deleted('learn_message', reply['id'], conn)
            return commit(job, material, texts)
        monkeypatch.setattr(memory.repository, 'commit_capture', delete_before_commit)
        await memory.process_pending()
        job = next(row for row in memory.repository.jobs() if row['evidence_id'] == 'learn-answer:' + run.id)
        assert job['state'] == 'cancelled'
        assert not [row for row in memory.repository.list() if row['kind'] == 'learning-point']
        assert len([row for row in control.calls if row['purpose'] == 'memory-extraction']) == 1
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_long_completed_reply_reaches_mem0_intact_without_embedding_whole_reply(study_capture):
    learn, memory, control = study_capture
    reply = 'CKD_STUDY_REPLY: ' + 'Synthetic general kidney physiology explanation. ' * 180
    assert len(reply.split()) > 512 and len(reply) < 16000
    control.answer = reply
    try:
        question = 'USER_PROMPT_NEVER_MEMORY: Explain a longer ordinary study topic'
        _, run = learn.prepare(question, ContextScope(kind=Scope.STUDY), None, 'ckd', 'direct', 'long-reply')
        flow = [event async for event in learn.answer(run, question, 'direct', 'ckd')]
        assert flow[-1].type == 'completed'
        await memory.process_pending()
        points = [row for row in memory.repository.list() if row['kind'] == 'learning-point']
        assert [row['text'] for row in points] == [POINTS['ckd']]
        call = next(row for row in control.calls if row['purpose'] == 'memory-extraction')
        assert reply in call['messages'][0]['content']
        assert 'USER_PROMPT_NEVER_MEMORY' not in call['messages'][0]['content']
    finally:
        await memory.close()
