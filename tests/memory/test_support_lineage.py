"""Learning and memory behavior under inherited support revocation."""
import asyncio
import hashlib
import json

import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.memory.models import ManualFact
from renulus.memory.service import MemoryService
try:
    from renulus.memory.lineage import AnswerInputs
except ModuleNotFoundError as error:
    # Only the four research cases are also runnable against the source-only
    # baseline export. It predates this type and receives no synthetic receipt.
    if error.name != 'renulus.memory.lineage':
        raise
    AnswerInputs = None
from renulus.design_c_contracts import Dependency, EligibleInput, Identity

from .test_study_answer_capture import POINTS, explain, study_capture


def memory_input(record):
    return EligibleInput(kind="memory", dependency=Dependency(
        target=Identity(type="memory_revision", id=f"{record['id']}:{record['revision']}"),
        expected_revision=str(record["revision"])))


async def published_explanation(learn, memory, control, *, inputs=(), dependencies=(), thread_id=None, key="answer", completed=True, project_id=None):
    """Synthetic trusted manifest publisher at the existing Learn publication seam.

    Production Learn publication belongs to the integrating owner. This fixture
    supplies explicit consumed references and does not claim that integration.
    """
    pinned_memory = next((item for item in inputs if item.kind == "memory"), None)
    question = (memory.repository.get(pinned_memory.dependency.target.id.rpartition(":")[0])["text"]
                if pinned_memory else "Explain CKD mechanisms.")
    _, run = learn.prepare(question, ContextScope(kind=Scope.STUDY), thread_id, "ckd", "direct", key)
    if hasattr(memory, "publish_answer_lineage_in"):
        run.publication = lambda conn: memory.publish_answer_lineage_in(
            conn, "learn-answer:" + run.id, inputs=inputs, dependencies=dependencies, project_id=project_id)
    flow = [event async for event in learn.answer(run, question, "direct", "ckd")]
    if completed:
        assert flow[-1].type == "completed"
    return run, flow


@pytest.mark.asyncio
async def test_edit_after_answer_before_capture_cannot_recreate_consumed_fact(study_capture):
    learn, memory, control = study_capture
    try:
        original = memory.add(ManualFact(text=POINTS["ckd"], topic_id="ckd",
            scope=ContextScope(kind=Scope.STUDY), idempotency_key="original"))
        _, flow = await published_explanation(learn, memory, control, inputs=(memory_input(original),))
        assert flow[-1].type == "completed"
        memory.edit(original["id"], "Corrected CKD learning point.", original["revision"])
        await memory.process_pending()
        assert POINTS["ckd"] not in [row["text"] for row in memory.repository.list()]
        assert memory.repository.get(original["id"])["text"] == "Corrected CKD learning point."
    finally:
        await memory.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("destination", [None, "project_beta"])
@pytest.mark.parametrize("historical", [False, True])
async def test_project_support_cannot_publish_global_or_other_project_memory(study_capture, destination, historical):
    learn, memory, control = study_capture
    try:
        root = memory.add(ManualFact(text="Private synthetic project learning preference.",
            scope=ContextScope(kind=Scope.STUDY), idempotency_key="project-root"), project_id="project_alpha")
        inputs = (memory_input(root),)
        if historical:
            run, _ = await published_explanation(learn, memory, control, inputs=inputs, project_id="project_alpha")
            _, inputs = memory.eligible_history(learn.get_thread(run.thread_id)["messages"], project_id="project_alpha")
            assert inputs
        _, flow = await published_explanation(learn, memory, control, inputs=inputs,
            project_id=destination, key="cross-project", completed=False)
        assert flow[-1].type == "error"
        await memory.process_pending()
        assert all(row["project_id"] == "project_alpha" for row in memory.repository.list()
                   if row["kind"] == "learning-point")
    finally:
        await memory.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("interval", ["queued", "completed-followup"])
@pytest.mark.parametrize("mutation", ["edit", "delete"])
async def test_four_research_regressions_cannot_recapture_a_consumed_fact(study_capture, interval, mutation):
    learn, memory, control = study_capture
    try:
        original = memory.add(ManualFact(text=POINTS["ckd"], topic_id="ckd",
            scope=ContextScope(kind=Scope.STUDY), idempotency_key="research-root"))
        run, _ = await published_explanation(learn, memory, control, inputs=(memory_input(original),))
        if interval == "completed-followup":
            await memory.process_pending()
        if mutation == "edit":
            memory.edit(original["id"], "Authoritative user correction.", 1)
        else:
            memory.delete(original["id"], 1)
        if interval == "completed-followup":
            # The synthetic harness declares exactly the historical answer it
            # consumed. A new answer identity must not erase this dependence.
            prior = memory.db.fetch_one("SELECT publication_digest FROM memory_answer_lineage WHERE evidence_id=?",
                ("learn-answer:" + run.id,))
            inherited = (EligibleInput(kind="committed_evidence", dependency=Dependency(
                target=Identity(type="learning_evidence", id="learn-answer:" + run.id),
                expected_revision=prior["publication_digest"])),) if prior else ()
            await published_explanation(learn, memory, control, inputs=inherited,
                thread_id=run.thread_id, key="historical-followup", completed=False)
        await memory.process_pending(retry=True)
        assert POINTS["ckd"] not in [row["text"] for row in memory.repository.list()]
        if mutation == "edit":
            assert memory.repository.get(original["id"])["text"] == "Authoritative user correction."
        else:
            with pytest.raises(ApiError, match="removed"):
                memory.repository.get(original["id"])
        await memory.process_pending(retry=True)
        assert POINTS["ckd"] not in [row["text"] for row in memory.repository.list()]
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_completed_answer_resolver_can_receive_replies_and_write_before_local_commit(study_capture, services):
    learn, memory, control = study_capture
    calls = []
    try:
        run, _ = await published_explanation(learn, memory, control)
        publication = services.db.fetch_one("SELECT * FROM memory_answer_lineage WHERE evidence_id=?",
            ("learn-answer:" + run.id,))

        class Resolver:
            async def resolve_completed_answer(self, reference):
                calls.append(reference)
                # The resolver represents remote host work. Its reply pump must
                # remain live while a separate public local writer can progress.
                await asyncio.wait_for(asyncio.to_thread(memory.add, ManualFact(
                    text="Independent dialysis learning preference.", scope=ContextScope(kind=Scope.STUDY),
                    idempotency_key="resolver-writer")), 2)
                return {"text": control.answer, "digest": hashlib.sha256(control.answer.encode()).hexdigest(),
                    "publication_digest": publication["publication_digest"], "input": {"version": 1, "inputs": [], "dependencies": []}}

        services.registry["completed_answer_resolver"] = Resolver()
        await memory.process_pending()
        assert len(calls) == 1
        assert POINTS["ckd"] in [row["text"] for row in memory.repository.list()]
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_correcting_root_removes_a_completed_fact_with_only_inherited_support(study_capture):
    learn, memory, control = study_capture
    try:
        root = memory.add(ManualFact(text="Synthetic root CKD observation.", topic_id="ckd",
            scope=ContextScope(kind=Scope.STUDY), idempotency_key="root"))
        await published_explanation(learn, memory, control, inputs=(memory_input(root),))
        await memory.process_pending()
        assert POINTS["ckd"] in [row["text"] for row in memory.repository.list()]
        memory.edit(root["id"], "User corrected the root observation.", 1)
        assert POINTS["ckd"] not in [row["text"] for row in memory.repository.list()]
        await memory.process_pending(retry=True)
        assert POINTS["ckd"] not in [row["text"] for row in memory.repository.list()]
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_corrected_generated_fact_excludes_its_original_history_from_followup(study_capture):
    learn, memory, control = study_capture
    try:
        run, _ = await published_explanation(learn, memory, control)
        await memory.process_pending()
        fact = next(row for row in memory.repository.list() if row["kind"] == "learning-point")
        memory.edit(fact["id"], "Explicit user correction of generated teaching.", 1)
        retained = learn.get_thread(run.thread_id)["messages"]
        eligible, inherited = memory.eligible_history(retained)
        assert any(row["role"] == "assistant" for row in retained)
        assert all(row["role"] != "assistant" for row in eligible)
        assert inherited == ()
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_explicit_project_memory_has_distinct_identity_and_recall_visibility(study_capture):
    _, memory, _ = study_capture
    try:
        note = ManualFact(text="Scope-specific dialysis study goal.",
            scope=ContextScope(kind=Scope.STUDY), idempotency_key="global-note")
        global_fact = memory.add(note)
        local_fact = memory.add(note.model_copy(update={"idempotency_key": "project-note"}), project_id="project_alpha")
        assert global_fact["id"] != local_fact["id"]
        memory.reindex()
        assert {r["id"] for r in memory.retrieve(note.text, scope=note.scope)["records"]} == {global_fact["id"]}
        assert {r["id"] for r in memory.retrieve(note.text, scope=note.scope, project_id="project_alpha")["records"]} == {global_fact["id"], local_fact["id"]}
        assert {r["id"] for r in memory.retrieve(note.text, scope=note.scope, project_id="project_beta")["records"]} == {global_fact["id"]}
        memory.edit(local_fact["id"], "Explicit correction within the same project.", 1)
        assert memory.repository.get(local_fact["id"])["project_id"] == "project_alpha"
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_changed_local_publication_cannot_reuse_an_old_lineage_receipt(study_capture, services):
    learn, memory, control = study_capture
    try:
        run, _ = await published_explanation(learn, memory, control)
        services.db.execute("UPDATE learning_evidence SET topic_id='transplant' WHERE id=?",
                            ("learn-answer:" + run.id,))
        await memory.process_pending()
        assert not [row for row in memory.repository.list() if row["kind"] == "learning-point"]
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_project_answer_history_requires_the_same_explicit_project(study_capture):
    learn, memory, control = study_capture
    try:
        run, _ = await published_explanation(learn, memory, control, project_id="project_alpha")
        messages = learn.get_thread(run.thread_id)["messages"]
        eligible, inputs = memory.eligible_history(messages)
        assert all(message["role"] != "assistant" for message in eligible)
        assert inputs == ()
        eligible, inputs = memory.eligible_history(messages, project_id="project_alpha")
        assert any(message["role"] == "assistant" for message in eligible) and len(inputs) == 1
        eligible, inputs = memory.eligible_history(messages, project_id="project_beta")
        assert all(message["role"] != "assistant" for message in eligible) and not inputs
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_independent_support_survives_one_root_but_echoes_do_not_survive_the_last(study_capture, services):
    learn, memory, control = study_capture
    try:
        roots = [memory.add(ManualFact(text=f"Synthetic independent {name} CKD observation.", topic_id="ckd",
            scope=ContextScope(kind=Scope.STUDY), idempotency_key=name)) for name in ("first", "second")]
        for index, root in enumerate(roots):
            await published_explanation(learn, memory, control, inputs=(memory_input(root),), key=f"root-{index}")
        await memory.process_pending()
        descendant = next(row for row in memory.repository.list() if row["text"] == POINTS["ckd"])
        # A new answer echoes the retained fact. It must keep both alternative
        # roots rather than establish fresh independent authority.
        await published_explanation(learn, memory, control, inputs=(memory_input(descendant),), key="echo")
        await memory.process_pending()
        memory.delete(roots[0]["id"], 1)
        assert memory.repository.get(descendant["id"])["text"] == POINTS["ckd"]
        memory.delete(roots[1]["id"], 1)
        assert POINTS["ckd"] not in [row["text"] for row in memory.repository.list()]
        await memory.close()
        memory = MemoryService(services)
        await memory.process_pending(retry=True)
        await memory.process_pending(retry=True)
        assert POINTS["ckd"] not in [row["text"] for row in memory.repository.list()]
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_deleted_chat_keeps_retained_learning_but_cannot_supply_future_answer_history(study_capture, services):
    learn, memory, control = study_capture
    try:
        run, _ = await published_explanation(learn, memory, control)
        retained_messages = learn.get_thread(run.thread_id)["messages"]
        _, prior_inputs = memory.eligible_history(retained_messages)
        await memory.process_pending()
        fact = next(row for row in memory.repository.list() if row["text"] == POINTS["ckd"])
        await learn.delete_thread(run.thread_id)
        # Synthetic recovery fixture for unavailable provenance. Lineage is
        # retained reference support, not storage-owned by deleted evidence;
        # persisted groups must still retain/check roots if a receipt is absent.
        services.db.execute("DELETE FROM memory_answer_lineage WHERE evidence_id=?", ("learn-answer:" + run.id,))
        eligible, inputs = memory.eligible_history(retained_messages)
        assert all(message["role"] != "assistant" for message in eligible) and not inputs
        _, flow = await published_explanation(learn, memory, control, inputs=prior_inputs, key="deleted-history", completed=False)
        assert flow[-1].type == "error"
        assert memory.repository.get(fact["id"])["text"] == POINTS["ckd"]
        await memory.close()
        memory = MemoryService(services)
        await memory.process_pending(retry=True)
        assert memory.repository.get(fact["id"])["text"] == POINTS["ckd"]
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_local_dependency_resolver_propagates_native_history_roots_and_rechecks_sources(study_capture, services):
    learn, memory, control = study_capture
    validations = []
    try:
        root = memory.add(ManualFact(text="Synthetic dialysis root preference.",
            scope=ContextScope(kind=Scope.STUDY), idempotency_key="native-root"))
        native = Dependency(target=Identity(type="message", id="native_message_1"), expected_revision="native_publication_1")

        class LocalNativePublication:
            def resolve_dependency_in(self, conn, dependency, *, project_id, for_support):
                # Explicit synthetic trusted receipt. Integration binds actual
                # Library/native receipts, never remote IPC from this callback.
                assert conn.in_transaction and dependency == native and project_id is None
                validations.append(for_support)
                return AnswerInputs(inputs=(memory_input(root),))

        memory.register_dependency_resolver("message", LocalNativePublication())
        await published_explanation(learn, memory, control, dependencies=(native,))
        await memory.process_pending()
        assert POINTS["ckd"] in [row["text"] for row in memory.repository.list()]
        assert False in validations
        await memory.close()
        memory = MemoryService(services)
        assert True in validations
        memory.edit(root["id"], "Explicit dialysis correction.", 1)
        assert POINTS["ckd"] not in [row["text"] for row in memory.repository.list()]
        await memory.process_pending(retry=True)
        assert POINTS["ckd"] not in [row["text"] for row in memory.repository.list()]
    finally:
        await memory.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("completed", [False, True])
async def test_registered_source_revocation_is_terminal_across_boundary_scans(study_capture, completed):
    learn, memory, control = study_capture
    class SyntheticLibraryRevision:
        eligible = True
        def resolve_dependency_in(self, conn, dependency, *, project_id, for_support):
            if not self.eligible:
                raise ApiError("memory_dependency_revoked", "Synthetic source revision was revoked", 409)
            return AnswerInputs()
    source = SyntheticLibraryRevision()
    try:
        memory.register_dependency_resolver("library_revision", source)
        pin = Dependency(target=Identity(type="library_revision", id="synthetic_library_revision_1"), expected_revision="1")
        await published_explanation(learn, memory, control, dependencies=(pin,))
        if completed:
            await memory.process_pending()
            assert POINTS["ckd"] in [row["text"] for row in memory.repository.list()]
        source.eligible = False
        await memory.process_pending(retry=True)
        assert POINTS["ckd"] not in [row["text"] for row in memory.repository.list()]
        source.eligible = True  # A later boundary cannot revive the old receipt.
        await memory.process_pending(retry=True)
        assert POINTS["ckd"] not in [row["text"] for row in memory.repository.list()]
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_joint_inputs_require_every_root_and_manual_correction_remains_independent(study_capture):
    learn, memory, control = study_capture
    try:
        roots = [memory.add(ManualFact(text=f"Synthetic joint {name} transplant observation.",
            scope=ContextScope(kind=Scope.STUDY), idempotency_key=name)) for name in ("left", "right")]
        await published_explanation(learn, memory, control, inputs=tuple(memory_input(root) for root in roots))
        await memory.process_pending()
        fact = next(row for row in memory.repository.list() if row["text"] == POINTS["ckd"])
        memory.edit(fact["id"], "Explicit user-owned transplant correction.", 1)
        memory.delete(roots[0]["id"], 1)
        assert memory.repository.get(fact["id"])["text"] == "Explicit user-owned transplant correction."
        await memory.process_pending(retry=True)
        assert POINTS["ckd"] not in [row["text"] for row in memory.repository.list()]
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_joint_support_without_a_manual_correction_dies_when_one_root_is_removed(study_capture):
    learn, memory, control = study_capture
    try:
        roots = [memory.add(ManualFact(text=f"Synthetic joint {name} dialysis observation.",
            scope=ContextScope(kind=Scope.STUDY), idempotency_key=name)) for name in ("left", "right")]
        await published_explanation(learn, memory, control, inputs=tuple(memory_input(root) for root in roots))
        await memory.process_pending()
        assert POINTS["ckd"] in [row["text"] for row in memory.repository.list()]
        memory.delete(roots[0]["id"], 1)
        assert POINTS["ckd"] not in [row["text"] for row in memory.repository.list()]
        assert memory.repository.get(roots[1]["id"])["revision"] == 1
    finally:
        await memory.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("forgery", ["text", "digest", "publication_digest", "input"])
async def test_completed_answer_resolver_rejects_forged_material_before_extraction(study_capture, services, forgery):
    learn, memory, control = study_capture
    try:
        run, _ = await published_explanation(learn, memory, control)
        publication = services.db.fetch_one("SELECT * FROM memory_answer_lineage WHERE evidence_id=?",
            ("learn-answer:" + run.id,))
        class ForgedResolver:
            async def resolve_completed_answer(self, reference):
                resolved = {"text": control.answer, "digest": hashlib.sha256(control.answer.encode()).hexdigest(),
                    "publication_digest": publication["publication_digest"], "input": json.loads(publication["manifest_json"])}
                resolved[forgery] = ({"version": 1, "dependencies": [{"target": {"type": "message", "id": "forged"},
                    "expected_revision": "1"}], "inputs": []} if forgery == "input" else "FORGED")
                return resolved
        services.registry["completed_answer_resolver"] = ForgedResolver()
        await memory.process_pending()
        assert not [call for call in control.calls if call["purpose"] == "memory-extraction"]
        assert not [row for row in memory.repository.list() if row["kind"] == "learning-point"]
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_legacy_answer_without_known_manifest_is_readable_but_ineligible_for_capture(study_capture):
    learn, memory, control = study_capture
    try:
        question = "Synthetic legacy CKD question."
        _, run = learn.prepare(question, ContextScope(kind=Scope.STUDY), None, "ckd", "direct", "legacy")
        # Produce a genuine unknown-lineage legacy answer before the memory hook
        # is composed. Current Learn with Memory now publishes known lineage.
        learn.services.registry['memory'] = None
        flow = [event async for event in learn.answer(run, question, "direct", "ckd")]
        learn.services.registry['memory'] = memory
        assert flow[-1].type == "completed"
        retained = learn.get_thread(run.thread_id)["messages"]
        assert any(message["role"] == "assistant" for message in retained)
        eligible, inputs = memory.eligible_history(retained)
        assert all(message["role"] != "assistant" for message in eligible) and not inputs
        await memory.process_pending(retry=True)
        assert not [call for call in control.calls if call["purpose"] == "memory-extraction"]
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_registered_dependency_ancestry_has_a_bounded_publication_budget(study_capture):
    learn, memory, control = study_capture
    class SyntheticLongHistory:
        def resolve_dependency_in(self, conn, dependency, *, project_id, for_support):
            position = int(dependency.target.id.split('_')[-1])
            return AnswerInputs(dependencies=(Dependency(target=Identity(type='message',
                id=f'synthetic_history_{position + 1}'), expected_revision='1'),)) if position < 120 else AnswerInputs()
    try:
        memory.register_dependency_resolver('message', SyntheticLongHistory())
        _, flow = await published_explanation(learn, memory, control, dependencies=(Dependency(
            target=Identity(type='message', id='synthetic_history_0'), expected_revision='1'),), completed=False)
        assert flow[-1].type == 'error' and flow[-1].payload['code'] == 'memory_support_budget'
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_source_revocation_is_checked_before_recall_and_dependent_publication(study_capture):
    learn, memory, control = study_capture
    class SyntheticSource:
        eligible = True
        def resolve_dependency_in(self, conn, dependency, *, project_id, for_support):
            if not self.eligible:
                raise ApiError('memory_dependency_revoked', 'Synthetic revoked Library source', 409)
            return AnswerInputs()
    source = SyntheticSource()
    try:
        memory.register_dependency_resolver('library_revision', source)
        dependency = Dependency(target=Identity(type='library_revision', id='synthetic_source'), expected_revision='1')
        await published_explanation(learn, memory, control, dependencies=(dependency,))
        await memory.process_pending()
        fact = next(row for row in memory.repository.list() if row['text'] == POINTS['ckd'])
        source.eligible = False
        # Publication must validate existing groups before the worker can scan.
        _, flow = await published_explanation(learn, memory, control, inputs=(memory_input(fact),),
            key='revoked-source-followup', completed=False)
        assert flow[-1].type == 'error'
        assert POINTS['ckd'] not in [row['text'] for row in memory.retrieve(POINTS['ckd'],
            scope=ContextScope(kind=Scope.STUDY))['records']]
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_internal_dependency_callback_errors_do_not_silently_revoke_known_learning(study_capture):
    learn, memory, control = study_capture
    class SyntheticSource:
        broken = False
        def resolve_dependency_in(self, conn, dependency, *, project_id, for_support):
            if self.broken:
                raise ApiError('synthetic_internal_failure', 'Synthetic internal callback failure', 503)
            return AnswerInputs()
    source = SyntheticSource()
    try:
        memory.register_dependency_resolver('library_revision', source)
        run, _ = await published_explanation(learn, memory, control, dependencies=(Dependency(
            target=Identity(type='library_revision', id='synthetic_source'), expected_revision='1'),))
        await memory.process_pending()
        messages = learn.get_thread(run.thread_id)['messages']
        source.broken = True
        with pytest.raises(ApiError) as error:
            memory.eligible_history(messages)
        assert error.value.code == 'synthetic_internal_failure'
        with pytest.raises(ApiError) as error:
            await memory.process_pending()
        assert error.value.code == 'synthetic_internal_failure'
        source.broken = False
        await memory.process_pending()
        assert POINTS['ckd'] in [row['text'] for row in memory.repository.list()]
        assert memory.eligible_history(messages)[1]
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_internal_dependency_callback_error_cannot_cancel_a_current_capture(study_capture):
    learn, memory, control = study_capture
    class SyntheticSource:
        broken = False
        def resolve_dependency_in(self, conn, dependency, *, project_id, for_support):
            if self.broken:
                raise ApiError('synthetic_internal_failure', 'Synthetic internal callback failure', 503)
            return AnswerInputs()
    source = SyntheticSource()
    try:
        memory.register_dependency_resolver('library_revision', source)
        run, _ = await published_explanation(learn, memory, control, dependencies=(Dependency(
            target=Identity(type='library_revision', id='synthetic_source'), expected_revision='1'),))
        queued = memory.repository.enqueue('learn-answer:' + run.id,
            ContextScope(kind=Scope.STUDY, entity_id=run.thread_id))
        job = memory.repository.claim(queued['id'])
        source.broken = True
        with pytest.raises(ApiError) as error:
            memory.repository.cancel_stale(job)
        assert error.value.code == 'synthetic_internal_failure'
        assert memory.repository.job(job['id'])['state'] == 'running'
        source.broken = False
        assert memory.repository.current(job)
    finally:
        await memory.close()
