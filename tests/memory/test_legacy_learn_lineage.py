"""Real legacy Learn hooks; only generation and CPU vectors are synthetic."""
import asyncio
import importlib.util
from pathlib import Path
import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.design_c_contracts import Dependency, EligibleInput, Identity
from renulus.memory.models import ManualFact
from renulus.runtime.manager import ProviderManager

from .test_study_answer_capture import ANSWERS, POINTS, study_capture
from .legacy_source_fixture import source_fixture


async def explain_with_real_hook(learn, *, question=POINTS['ckd'], thread_id=None,
                                 key='real-answer'):
    _, run = learn.prepare(question, ContextScope(kind=Scope.STUDY), thread_id,
        'ckd', 'direct', key)
    assert run.publication is None
    flow = [event async for event in learn.answer(run, question, 'direct', 'ckd')]
    return run, flow


@pytest.mark.asyncio
@pytest.mark.parametrize('mutation', ['edit', 'delete'])
async def test_queued_answer_cannot_recapture_memory_mutated_after_real_publication(study_capture, mutation):
    learn, memory, control = study_capture
    try:
        original = memory.add(ManualFact(text=POINTS['ckd'], topic_id='ckd',
            scope=ContextScope(kind=Scope.STUDY), idempotency_key='real-root'))
        run, flow = await explain_with_real_hook(learn)
        assert flow[-1].type == 'completed'
        assert next(event for event in flow if event.type == 'memory').payload['count'] == 1
        assert memory.enqueue('learn-answer:' + run.id, ContextScope(
            kind=Scope.STUDY, entity_id=run.thread_id))['state'] == 'queued'
        if mutation == 'edit':
            memory.edit(original['id'], 'Authoritative learner correction.', original['revision'])
        else:
            memory.delete(original['id'], original['revision'])
        await memory.process_pending(retry=True)
        assert POINTS['ckd'] not in [row['text'] for row in memory.repository.list()]
        if mutation == 'edit':
            assert memory.repository.get(original['id'])['text'] == 'Authoritative learner correction.'
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_internal_recall_error_is_not_downgraded_to_independent_publication(study_capture, monkeypatch):
    learn, memory, control = study_capture
    try:
        def broken_recall(*args, **kwargs):
            raise ApiError('synthetic_internal_resolver', 'Synthetic internal resolver failure', 503, True)
        monkeypatch.setattr(memory, 'retrieve', broken_recall)
        run, flow = await explain_with_real_hook(learn)
        assert flow[-1].type == 'error'
        assert flow[-1].payload['code'] == 'synthetic_internal_resolver'
        assert not [call for call in control.calls if call['purpose'] == 'explain']
        assert not [message for message in learn.get_thread(run.thread_id)['messages'] if message['role'] == 'assistant']
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_real_legacy_source_digest_revocation_blocks_completed_answer_capture(study_capture, monkeypatch):
    learn, memory, control = study_capture
    try:
        revision_id, digest, adapter = source_fixture(learn.services, monkeypatch)
        memory.register_dependency_resolver('library_revision', adapter)
        run, flow = await explain_with_real_hook(learn)
        assert flow[-1].type == 'completed'
        assert len(memory.eligible_history(learn.get_thread(run.thread_id)['messages'])[1]) == 1
        memory.db.execute("UPDATE knowledge_revisions SET status='failed' WHERE id=?", (revision_id,))
        assert memory.eligible_history(learn.get_thread(run.thread_id)['messages'])[1] == ()
        await memory.process_pending(retry=True)
        assert POINTS['ckd'] not in [row['text'] for row in memory.repository.list()]
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_direct_legacy_prepare_derives_project_and_recall_from_saved_membership(study_capture):
    from renulus.study.project_models import NewProject
    from renulus.study.project_repository import ProjectRepository
    from renulus.storage import utc_now

    learn, memory, control = study_capture
    try:
        source = learn.services.paths.source_root / 'runtime/renulus'
        for module, filename, name in [('study', 'schema.sql', 'study-project-test'),
                ('study', 'migrations/002.sql', 'study-projects-test'),
                ('knowledge', 'schema.sql', 'knowledge-project-test')]:
            memory.db.apply_migration(name, (source / module / filename).read_text(encoding='utf-8'))
        projects = ProjectRepository(learn.services)
        learn.services.registry['projects'] = projects
        project = projects.create(NewProject(title='Synthetic project CKD study'), 'project-test')
        thread = learn.create_thread('Synthetic linked legacy chat', 'ckd')
        # Explicit synthetic membership fixture; real context_in resolves it.
        memory.db.execute('INSERT INTO study_project_chats VALUES(?,?,?,?,?,?,?)',
            ('synthetic_membership', project['id'], 'learning', thread['id'], 0, 1, utc_now()))
        root = memory.add(ManualFact(text=POINTS['ckd'], topic_id='ckd',
            scope=ContextScope(kind=Scope.STUDY), idempotency_key='project-root'), project_id=project['id'])
        run, flow = await explain_with_real_hook(learn, thread_id=thread['id'])
        assert run.project_id == project['id']
        assert flow[-1].type == 'completed'
        assert next(event for event in flow if event.type == 'memory').payload['count'] == 1
        assert memory.eligible_history(learn.get_thread(thread['id'])['messages'])[1] == ()
        assert len(memory.eligible_history(learn.get_thread(thread['id'])['messages'], project_id=project['id'])[1]) == 1
        memory.edit(root['id'], 'Project-owned corrected point.', root['revision'])
        await memory.process_pending(retry=True)
        assert [row['text'] for row in memory.repository.list() if row['kind'] == 'learning-point'] == ['Project-owned corrected point.']
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_ordinary_conversation_finalizer_still_publishes_real_memory_lineage(study_capture):
    learn, memory, control = study_capture
    callbacks = []
    try:
        _, run = learn.prepare('Explain CKD.', ContextScope(kind=Scope.STUDY),
            None, 'ckd', 'direct', 'ordinary-finalizer')
        def ordinary_finalizer(conn):
            callbacks.append(run.id)
            return {'run_id': run.id, 'state': 'completed'}
        run.publication = ordinary_finalizer
        flow = [event async for event in learn.answer(run, 'Explain CKD.', 'direct', 'ckd')]
        assert flow[-1].type == 'completed'
        eligible, pins = memory.eligible_history(learn.get_thread(run.thread_id)['messages'])
        assert [message['content'] for message in eligible if message['role'] == 'assistant'] == [ANSWERS['ckd']]
        assert len(pins) == 1
        assert callbacks == [run.id]
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_history_only_revocation_during_awaited_compaction_blocks_primary_dispatch(study_capture):
    # Mem0 and full pytest collection can expose another top-level tests package.
    # Resolve these public controlled doubles by their owned source path.
    fixture_path = Path(__file__).resolve().parents[1] / 'learn/test_memory_context.py'
    spec = importlib.util.spec_from_file_location('h05_compaction_fixture', fixture_path)
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    ControlledContext, ControlledTransport, MODEL = fixture.ControlledContext, fixture.ControlledTransport, fixture.MODEL

    learn, memory, control = study_capture
    task = None
    transport = ControlledTransport('compaction')
    try:
        root = memory.add(ManualFact(text=POINTS['ckd'], topic_id='ckd',
            scope=ContextScope(kind=Scope.STUDY), idempotency_key='compaction-root'))
        first, flow = await explain_with_real_hook(learn)
        assert flow[-1].type == 'completed'
        manager = ProviderManager(learn.services.paths, transport=transport)
        class HistoryContext(ControlledContext):
            def plan(self, messages, **kwargs):
                plan = super().plan(messages, **kwargs)
                plan.turns = messages[1:-1]
                return plan
        manager._context = HistoryContext(compact=True)
        manager._settings['selected_provider'] = 'codex'
        manager._settings['connections']['codex'] = {'synthetic': True}
        manager._catalogs['codex'] = {MODEL}
        async def synthetic_token(provider):
            return 'synthetic-token'
        manager._access_token = synthetic_token
        learn.services.registry['provider'] = manager
        # Query has no matching vector. Only the eligible prior assistant carries
        # the root into this continuation and its runtime compaction.
        task = asyncio.create_task(explain_with_real_hook(learn, question='Continue a neutral explanation.',
            thread_id=first.thread_id, key='history-compaction'))
        await asyncio.wait_for(transport.entered.wait(), 5)
        assert transport.calls[0][0] == 'compaction'
        assert ANSWERS['ckd'] in [item['content'] for item in transport.calls[0][1]]
        memory.delete(root['id'], root['revision'])
        transport.release.set()
        _, flow = await task
        assert flow[-1].type == 'error'
        assert flow[-1].payload['code'] == 'memory_dependency_revoked'
        assert [purpose for purpose, messages in transport.calls] == ['compaction']
        assert next(event for event in flow if event.type == 'memory').payload['count'] == 0
    finally:
        transport.release.set()
        if task:
            await asyncio.gather(task, return_exceptions=True)
        await memory.close()


def test_local_answer_input_check_uses_supplied_snapshot_and_rejects_revoked_revision(study_capture):
    learn, memory, control = study_capture
    root = memory.add(ManualFact(text='Local validation learner preference.',
        scope=ContextScope(kind=Scope.STUDY), idempotency_key='snapshot-root'))
    inputs = (EligibleInput(kind='memory', dependency=Dependency(
        target=Identity(type='memory_revision', id=root['id'] + ':1'), expected_revision='1')),)
    with memory.db.transaction() as conn:
        memory.check_answer_inputs_in(conn, inputs=inputs)
        # One synthetic same-snapshot edit proves the seam observes its caller's
        # uncommitted canonical state, without opening another writer/reader.
        conn.execute('UPDATE memory_facts SET revision=2 WHERE id=?', (root['id'],))
        with pytest.raises(ApiError) as caught:
            memory.check_answer_inputs_in(conn, inputs=inputs)
        assert caught.value.code == 'memory_dependency_revoked'


@pytest.mark.asyncio
@pytest.mark.parametrize('mutation', ['edit', 'delete'])
async def test_completed_capture_mutation_omits_revoked_assistant_from_real_followup(study_capture, mutation):
    learn, memory, control = study_capture
    try:
        original = memory.add(ManualFact(text=POINTS['ckd'], topic_id='ckd',
            scope=ContextScope(kind=Scope.STUDY), idempotency_key='followup-root'))
        run, flow = await explain_with_real_hook(learn)
        assert flow[-1].type == 'completed'
        await memory.process_pending()
        if mutation == 'edit':
            memory.edit(original['id'], 'Authoritative learner correction.', original['revision'])
        else:
            memory.delete(original['id'], original['revision'])
        control.answer = ANSWERS['transplant']
        _, followup = await explain_with_real_hook(learn, question='Continue the explanation.',
            thread_id=run.thread_id, key='real-followup')
        assert followup[-1].type == 'completed'
        sent = next(call for call in reversed(control.calls) if call['purpose'] == 'explain')
        assert ANSWERS['ckd'] not in [message['content'] for message in sent['messages']]
        # The original display history remains available after context exclusion.
        assert ANSWERS['ckd'] in [message['content'] for message in learn.get_thread(run.thread_id)['messages']]
        await memory.process_pending(retry=True)
        assert POINTS['ckd'] not in [row['text'] for row in memory.repository.list()]
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_valid_history_only_followup_inherits_root_and_never_gains_independence(study_capture):
    learn, memory, control = study_capture
    try:
        root = memory.add(ManualFact(text=POINTS['ckd'], topic_id='ckd',
            scope=ContextScope(kind=Scope.STUDY), idempotency_key='inherited-root'))
        first, flow = await explain_with_real_hook(learn)
        assert flow[-1].type == 'completed'
        second, flow = await explain_with_real_hook(learn, question='Continue a neutral explanation.',
            thread_id=first.thread_id, key='inherited-followup')
        assert flow[-1].type == 'completed'
        assert next(event for event in flow if event.type == 'memory').payload['count'] == 0
        sent = next(call for call in reversed(control.calls) if call['purpose'] == 'explain')
        assert ANSWERS['ckd'] in [message['content'] for message in sent['messages']]
        assert len(memory.eligible_history(learn.get_thread(first.thread_id)['messages'])[1]) == 2
        memory.delete(root['id'], root['revision'])
        with pytest.raises(ApiError) as caught:
            memory.enqueue('learn-answer:' + second.id, ContextScope(kind=Scope.STUDY, entity_id=first.thread_id))
        assert caught.value.code in ('memory_dependency_revoked', 'memory_capture_suppressed')
        await memory.process_pending(retry=True)
        await memory.process_pending(retry=True)
        assert memory.eligible_history(learn.get_thread(first.thread_id)['messages'])[1] == ()
        assert POINTS['ckd'] not in [row['text'] for row in memory.repository.list()]
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_legacy_unknown_answer_stays_visible_but_never_enters_real_followup(study_capture):
    learn, memory, control = study_capture
    try:
        learn.services.registry['memory'] = None
        first, flow = await explain_with_real_hook(learn)
        assert flow[-1].type == 'completed'
        learn.services.registry['memory'] = memory
        control.answer = ANSWERS['transplant']
        _, flow = await explain_with_real_hook(learn, question='Continue a neutral explanation.',
            thread_id=first.thread_id, key='unknown-followup')
        assert flow[-1].type == 'completed'
        sent = next(call for call in reversed(control.calls) if call['purpose'] == 'explain')
        assert ANSWERS['ckd'] not in [message['content'] for message in sent['messages']]
        assert ANSWERS['ckd'] in [message['content'] for message in learn.get_thread(first.thread_id)['messages']]
    finally:
        await memory.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('missing', ['library', 'persistent-resolver', 'revision'])
async def test_missing_source_binding_or_noncanonical_reference_fails_closed_before_dispatch(study_capture, monkeypatch, missing):
    learn, memory, control = study_capture
    try:
        revision_id, digest, adapter = source_fixture(learn.services, monkeypatch)
        if missing != 'persistent-resolver':
            memory.register_dependency_resolver('library_revision', adapter)
        if missing == 'library':
            del learn.services.registry['harness_library']
        if missing == 'revision':
            original = learn.services.registry['knowledge'].retrieve
            def noncanonical(*args, **kwargs):
                result = original(*args, **kwargs)
                result['passages'][0].pop('document_revision')
                return result
            monkeypatch.setattr(learn.services.registry['knowledge'], 'retrieve', noncanonical)
        run, flow = await explain_with_real_hook(learn)
        assert flow[-1].type == 'error'
        assert flow[-1].payload['code'] in ('memory_dependency_unknown', 'harness_sources_changed')
        assert not [call for call in control.calls if call['purpose'] == 'explain']
        assert not [message for message in learn.get_thread(run.thread_id)['messages'] if message['role'] == 'assistant']
    finally:
        await memory.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('callback', ['false-digest', 'internal-error'])
async def test_invalid_publication_callback_rolls_back_answer_without_terminalizing_support(study_capture, callback):
    learn, memory, control = study_capture
    try:
        _, run = learn.prepare('Explain CKD.', ContextScope(kind=Scope.STUDY),
            None, 'ckd', 'direct', 'invalid-callback')
        def publication(conn):
            if callback == 'internal-error':
                raise ApiError('synthetic_internal_publication', 'Synthetic internal callback failure', 503, True)
            return 'f' * 64
        run.publication = publication
        flow = [event async for event in learn.answer(run, 'Explain CKD.', 'direct', 'ckd')]
        assert flow[-1].type == 'error'
        assert flow[-1].payload['code'] == ('synthetic_internal_publication' if callback == 'internal-error' else 'memory_lineage_conflict')
        assert not [message for message in learn.get_thread(run.thread_id)['messages'] if message['role'] == 'assistant']
        assert memory.eligible_history(learn.get_thread(run.thread_id)['messages'])[1] == ()
    finally:
        await memory.close()
