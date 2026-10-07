import asyncio
import json
import sqlite3

import pytest

from renulus.cases.models import DiscussCase, EditCase, HandoffCase, StartCase
from renulus.cases.repository import CaseRepository
from renulus.cases.streaming import discuss
from renulus.contracts import ApiError, ContextScope, Scope

from .conftest import (HIDDEN_SENTINEL, LATE_SENTINEL, SENTINEL, ProviderFixture,
                      assert_absent_from_profile, assert_terminals)


def start(repository, text=SENTINEL):
    return repository.start(StartCase(text=text))


async def collect(repository, case, provider, message="Discuss the synthetic case"):
    repository.services.registry["provider"] = provider
    run, context = repository.begin_discussion(case["id"], DiscussCase(
        revision=case["revision"], request_id="request-1", message=message))
    return run, [event async for event in discuss(repository, run, context)]


@pytest.mark.parametrize("topic", ["CKD", "dialysis", "transplantation",
                                  "glomerular disease", "electrolytes"])
async def test_discussion_is_temporary_across_domains(repository, services, topic):
    case = start(repository, f"{topic}: {SENTINEL}")
    provider = ProviderFixture([f"Synthetic discussion of {topic}"])
    _, events = await collect(repository, case, provider)
    assert_terminals(events, "completed")
    assert provider.calls[0]["scope"] == ContextScope(kind=Scope.TEMPORARY_CASE, entity_id=case["id"])
    assert provider.calls[0]["purpose"] == "case-discuss"
    assert SENTINEL in provider.calls[0]["messages"][0]["content"]
    view = repository.get(case["id"])
    assert [m["role"] for m in view["messages"]] == ["user", "assistant"]
    assert view["scope"]["kind"] == "temporary-case"
    assert services.db.fetch_all("SELECT * FROM learning_evidence") == []
    assert_absent_from_profile(services, SENTINEL)


async def test_provider_error_with_raw_prompt_is_sanitized_and_never_saved(repository, services, caplog):
    case = start(repository)
    provider = ProviderFixture(["Partial synthetic output"], RuntimeError(SENTINEL))
    run, events = await collect(repository, case, provider)
    assert_terminals(events, "failed")
    assert SENTINEL not in events[-1].model_dump_json()
    assert SENTINEL not in caplog.text
    assert [m["role"] for m in repository.get(case["id"])["messages"]] == ["user"]
    assert run.id in provider.cancelled
    assert_absent_from_profile(services, SENTINEL)
    # A process restart knows neither the temporary case nor any failed run.
    with pytest.raises(ApiError) as error:
        CaseRepository(services).get(case["id"])
    assert error.value.status == 404


async def test_missing_provider_is_an_honest_terminal_failure(repository, services):
    case = start(repository)
    run, context = repository.begin_discussion(case["id"], DiscussCase(
        revision=1, request_id="unconnected", message="Discuss"))
    events = [event async for event in discuss(repository, run, context)]
    assert_terminals(events, "failed")
    assert events[-1].payload["error"]["code"] == "capability_unavailable"
    assert_absent_from_profile(services, SENTINEL)


async def test_cancel_rejects_an_uncooperative_late_response_and_save_excludes_partial(repository, services):
    case = start(repository)
    provider = ProviderFixture(["Partial", LATE_SENTINEL], blocked=True, ignore_cancel=True)
    services.registry["provider"] = provider
    run, context = repository.begin_discussion(case["id"], DiscussCase(
        revision=1, request_id="cancel-me", message="Discuss"))
    async def consume():
        return [event async for event in discuss(repository, run, context)]
    task = asyncio.create_task(consume())
    await asyncio.wait_for(provider.started.wait(), timeout=1)
    repository.cancel(run.id)
    events = await asyncio.wait_for(task, timeout=1)
    assert_terminals(events, "cancelled")
    assert_absent_from_profile(services, SENTINEL, LATE_SENTINEL)
    current = repository.get(case["id"])
    saved = repository.save(case["id"], current["revision"])
    assert saved["saved"] and not saved["dirty"]
    provider.release.set()
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    row = services.db.fetch_one("SELECT * FROM case_sessions WHERE id=?", (case["id"],))
    assert SENTINEL in row["case_text"]
    assert LATE_SENTINEL not in repr(row)
    assert "Partial" not in row["messages_json"]
    assert [m["role"] for m in json.loads(row["messages_json"])] == ["user"]


async def test_delete_during_stream_cancels_and_tombstone_survives_restart(repository, services):
    case = start(repository)
    provider = ProviderFixture(["Partial", LATE_SENTINEL], blocked=True, ignore_cancel=True)
    services.registry["provider"] = provider
    run, context = repository.begin_discussion(case["id"], DiscussCase(
        revision=1, request_id="delete-me", message="Discuss"))
    async def consume():
        return [event async for event in discuss(repository, run, context)]
    task = asyncio.create_task(consume())
    await asyncio.wait_for(provider.started.wait(), timeout=1)
    result = repository.delete(case["id"])
    assert result == {"id": case["id"], "deleted": True, "purge_pending": False}
    events = await asyncio.wait_for(task, timeout=1)
    assert_terminals(events, "cancelled")
    provider.release.set()
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert_absent_from_profile(services, SENTINEL, LATE_SENTINEL)
    with pytest.raises(ApiError) as error:
        CaseRepository(services).get(case["id"])
    assert error.value.status == 410
    assert services.db.fetch_one("SELECT * FROM deletion_ledger WHERE entity_id=?",
                                 (case["id"],))["entity_type"] == "case"


async def test_only_save_promotes_current_snapshot_and_followups_remain_volatile(repository, services):
    case = start(repository)
    _, events = await collect(repository, case, ProviderFixture(["A permitted synthetic response"]))
    assert_terminals(events, "completed")
    current = repository.get(case["id"])
    saved = repository.save(case["id"], current["revision"])
    assert saved["scope"]["kind"] == "saved-case"
    assert repository.save(case["id"], current["revision"]) == saved
    reopened = CaseRepository(services).get(case["id"])
    assert reopened == saved
    provider = ProviderFixture([LATE_SENTINEL])
    request = DiscussCase(revision=reopened["revision"], request_id="follow-up", message=LATE_SENTINEL)
    services.registry["provider"] = provider
    run, context = repository.begin_discussion(case["id"], request)
    followup = [event async for event in discuss(repository, run, context)]
    assert_terminals(followup, "completed")
    assert provider.calls[0]["scope"].kind == Scope.TEMPORARY_CASE
    row = services.db.fetch_one("SELECT * FROM case_sessions WHERE id=?", (case["id"],))
    assert SENTINEL in row["case_text"]
    assert LATE_SENTINEL not in repr(row)
    # Saving does not create ordinary history, memory, cache or exported copies.
    assert services.db.fetch_all("SELECT * FROM learning_evidence") == []
    for root in (services.paths.cache, services.paths.indexes,
                 services.paths.root / "history", services.paths.root / "export"):
        assert list(root.rglob("*")) == []
    repository.close(case["id"], repository.get(case["id"])["revision"])
    assert repository.get(case["id"]) == saved
    deletion = repository.delete(case["id"], saved["revision"])
    assert not deletion["purge_pending"]
    assert_absent_from_profile(services, SENTINEL, LATE_SENTINEL)
    assert repository.delete(case["id"]) == deletion


def test_failed_atomic_save_does_not_promote_the_in_memory_case(repository, services):
    case = start(repository)
    services.db.execute("CREATE TRIGGER reject_save BEFORE INSERT ON case_sessions "
                        "BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        repository.save(case["id"], 1)
    assert not repository.get(case["id"])["saved"]
    assert services.db.fetch_all("SELECT * FROM case_sessions") == []
    assert_absent_from_profile(services, SENTINEL)


def test_busy_save_and_stale_revisions_do_not_persist(repository, services):
    case = start(repository)
    run, _ = repository.begin_discussion(case["id"], DiscussCase(
        revision=1, request_id="busy", message="Discuss"))
    with pytest.raises(ApiError, match="Stop or finish"):
        repository.save(case["id"], run.revision)
    with pytest.raises(ApiError) as error:
        repository.edit(case["id"], EditCase(revision=1, title="Changed"))
    assert error.value.code == "case_revision_conflict"
    assert_absent_from_profile(services, SENTINEL)


def test_two_repository_snapshots_cannot_overwrite_or_delete_a_newer_save(repository, services):
    case = start(repository)
    first = repository.save(case["id"], 1)
    second_repository = CaseRepository(services)
    second_repository.get(case["id"])
    edited = repository.edit(case["id"], EditCase(revision=1, text="A newer synthetic snapshot"))
    repository.save(case["id"], edited["revision"])
    stale = second_repository.edit(case["id"], EditCase(revision=1, title="Stale title"))
    with pytest.raises(ApiError) as error:
        second_repository.save(case["id"], stale["revision"])
    assert error.value.code == "case_revision_conflict"
    with pytest.raises(ApiError) as error:
        second_repository.delete(case["id"], stale["revision"])
    assert error.value.code == "case_revision_conflict"
    row = services.db.fetch_one("SELECT * FROM case_sessions WHERE id=?", (first["id"],))
    assert row["case_text"] == "A newer synthetic snapshot"
    assert services.db.fetch_all("SELECT * FROM deletion_ledger") == []


def test_tombstone_blocks_an_older_restore_or_resurrection(repository, services):
    case = start(repository)
    repository.save(case["id"], 1)
    row = services.db.fetch_one("SELECT * FROM case_sessions WHERE id=?", (case["id"],))
    repository.delete(case["id"], 1)
    with pytest.raises(sqlite3.IntegrityError, match="deleted cases"):
        services.db.execute("INSERT INTO case_sessions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", row.values())
    assert_absent_from_profile(services, SENTINEL)


def test_pinned_reader_delays_physical_purge_and_idempotent_retry_finishes_it(repository, services):
    case = start(repository)
    repository.save(case["id"], 1)
    reader = services.db.connect()
    try:
        reader.execute("BEGIN")
        assert reader.execute("SELECT case_text FROM case_sessions").fetchone()[0] == SENTINEL
        result = repository.delete(case["id"], 1)
        assert result["purge_pending"]
        assert services.db.fetch_all("SELECT * FROM case_sessions") == []
        # A live pinned SQLite snapshot still contains its old data; do not claim
        # a physical purge until all readers release it and the checkpoint wins.
        with pytest.raises(ApiError) as error:
            repository.get(case["id"])
        assert error.value.status == 410
    finally:
        reader.rollback()
        reader.close()
    assert not repository.delete(case["id"])["purge_pending"]
    assert_absent_from_profile(services, SENTINEL)


async def test_disconnect_cancels_locally_without_committing_a_partial_answer(repository, services):
    case = start(repository)
    provider = ProviderFixture(["Partial", LATE_SENTINEL], blocked=True)
    services.registry["provider"] = provider
    run, context = repository.begin_discussion(case["id"], DiscussCase(
        revision=1, request_id="disconnect", message="Discuss"))
    async def consume():
        return [event async for event in discuss(repository, run, context)]
    task = asyncio.create_task(consume())
    await asyncio.wait_for(provider.started.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert run.status == "cancelled"
    assert repository.get(case["id"])["active_run_id"] is None
    assert [m["role"] for m in repository.get(case["id"])["messages"]] == ["user"]
    assert run.id in provider.cancelled
    assert_absent_from_profile(services, SENTINEL, LATE_SENTINEL)


async def test_async_commit_rejects_another_repository_revision(repository, services):
    case = start(repository)
    saved = repository.save(case["id"], 1)
    other = CaseRepository(services)
    other.get(case["id"])
    provider = ProviderFixture(["Partial", LATE_SENTINEL], blocked=True)
    services.registry["provider"] = provider
    run, context = repository.begin_discussion(case["id"], DiscussCase(
        revision=1, request_id="stale-completion", message="Discuss"))
    async def consume():
        return [event async for event in discuss(repository, run, context)]
    task = asyncio.create_task(consume())
    await asyncio.wait_for(provider.started.wait(), timeout=1)
    newer = other.edit(saved["id"], EditCase(revision=1, title="Newer canonical title"))
    other.save(newer["id"], newer["revision"])
    provider.release.set()
    events = await asyncio.wait_for(task, timeout=1)
    assert_terminals(events, "failed")
    assert events[-1].payload["error"]["code"] == "case_revision_conflict"
    assert LATE_SENTINEL not in json.dumps([event.model_dump() for event in events])
    assert LATE_SENTINEL not in repr(services.db.fetch_all("SELECT * FROM case_sessions"))


async def test_idempotent_volatile_replay_does_not_infer_or_append_twice(repository, services):
    case = start(repository)
    provider = ProviderFixture()
    run, first_events = await collect(repository, case, provider)
    replay_run, context = repository.begin_discussion(case["id"], DiscussCase(
        revision=1, request_id="request-1", message="Discuss the synthetic case"))
    replay_events = [e async for e in discuss(repository, replay_run, context)]
    assert replay_run is run
    assert replay_events == first_events
    assert len(provider.calls) == 1
    assert len(repository.get(case["id"])["messages"]) == 2
    with pytest.raises(ApiError) as error:
        repository.begin_discussion(case["id"], DiscussCase(
            revision=1, request_id="request-1", message="Changed input"))
    assert error.value.code == "case_request_conflict"
    assert_absent_from_profile(services, SENTINEL)


def test_teacher_reveals_are_pinned_and_hidden_from_context(repository, services):
    case = repository.start(StartCase(kind="teaching", teaching_case_id="case-synthetic-transplant"))
    assert HIDDEN_SENTINEL not in json.dumps(case)
    assert "teaching_points" not in case["teaching"]["stages"][0]
    assert "stages" not in repository.list_teaching()[0]
    services.registry["content"].item["version"] = 2
    services.registry["content"].item["stages"][1]["narrative"] = "New pack stage"
    run, context = repository.begin_discussion(case["id"], DiscussCase(
        revision=1, request_id="first-stage", message="Discuss the presentation"))
    assert HIDDEN_SENTINEL not in json.dumps(context)
    repository.cancel(run.id)
    first_reveal = repository.reveal(case["id"], repository.get(case["id"])["revision"])
    assert first_reveal["teaching"]["version"] == 1
    assert first_reveal["teaching"]["stages"][1]["narrative"] == HIDDEN_SENTINEL
    assert "teaching_points" in first_reveal["teaching"]["stages"][0]
    assert "teaching_points" not in first_reveal["teaching"]["stages"][1]
    assert "take_home" not in first_reveal["teaching"]
    debrief = repository.reveal(case["id"], first_reveal["revision"])
    assert debrief["teaching"]["debriefed"]
    assert debrief["teaching"]["take_home"]
    saved = repository.save(case["id"], debrief["revision"])
    assert CaseRepository(services).get(case["id"]) == saved


@pytest.mark.parametrize("target", ["explain", "generated-practice"])
def test_handoff_keeps_temporary_scope_and_only_guarded_result_in_memory(repository, services, target):
    case = start(repository)
    ticket = repository.handoff(case["id"], HandoffCase(revision=1, target=target))
    assert ticket["case_text"] == SENTINEL
    assert ticket["case_handoff_id"] == ticket["id"]
    assert ticket["scope"]["kind"] == "temporary-case"
    context = repository.resolve_handoff(ticket["id"], target)
    assert context["scope"].kind == Scope.TEMPORARY_CASE
    assert SENTINEL in json.dumps(context["messages"])
    with pytest.raises(ApiError) as error:
        repository.commit_handoff(ticket["id"], target, "Synthetic response",
                                  cancel=context["cancel"], scope=ContextScope(kind=Scope.STUDY))
    assert error.value.code == "case_scope_mismatch"
    view = repository.commit_handoff(ticket["id"], target, "Synthetic response",
                                     cancel=context["cancel"], scope=context["scope"])
    assert len(view["messages"]) == 1
    assert view["scope"]["kind"] == "temporary-case"
    assert_absent_from_profile(services, SENTINEL)


async def test_saved_case_explain_handoff_stays_volatile_until_explicit_save(repository, services):
    case = start(repository)
    saved = repository.save(case["id"], 1)
    ticket = repository.handoff(case["id"], HandoffCase(
        revision=saved["revision"], target="explain", question="Explain this synthetic situation"))
    context = repository.resolve_handoff(ticket["id"], "explain")
    assert ticket["scope"]["kind"] == "temporary-case"
    assert context["scope"].kind == Scope.TEMPORARY_CASE
    assert context["question"] == ticket["question"]
    provider = ProviderFixture([LATE_SENTINEL])
    answer = "".join([text async for text in provider.stream(
        context["messages"] + [{"role": "user", "content": context["question"]}],
        scope=context["scope"], run_id="synthetic-explain", purpose="explain")])
    view = repository.commit_handoff(ticket["id"], "explain", answer,
                                     cancel=context["cancel"], scope=context["scope"])
    assert view["saved"] and view["dirty"]
    assert [m["role"] for m in view["messages"]] == ["user", "assistant"]
    assert services.db.fetch_one("SELECT messages_json FROM case_sessions WHERE id=?",
                                 (case["id"],))["messages_json"] == "[]"
    assert services.db.fetch_all("SELECT * FROM learning_evidence") == []
    assert_absent_from_profile(services, LATE_SENTINEL)
    repository.save(case["id"], view["revision"])
    reopened = CaseRepository(services).get(case["id"])
    assert reopened["messages"][-1]["content"] == LATE_SENTINEL
    repository.delete(case["id"], view["revision"])
    assert_absent_from_profile(services, SENTINEL, LATE_SENTINEL)


def test_handoff_cannot_commit_after_another_repository_changes_saved_revision(repository, services):
    case = start(repository)
    repository.save(case["id"], 1)
    ticket = repository.handoff(case["id"], HandoffCase(revision=1, target="explain"))
    context = repository.resolve_handoff(ticket["id"], "explain")
    other = CaseRepository(services)
    changed = other.edit(case["id"], EditCase(revision=1, title="Updated elsewhere"))
    other.save(case["id"], changed["revision"])
    with pytest.raises(ApiError) as error:
        repository.commit_handoff(ticket["id"], "explain", LATE_SENTINEL,
                                  cancel=context["cancel"], scope=context["scope"])
    assert error.value.code == "case_revision_conflict"
    assert context["cancel"].is_set()
    assert_absent_from_profile(services, LATE_SENTINEL)


def test_teaching_handoff_includes_only_revealed_case_material(repository, services):
    case = repository.start(StartCase(kind="teaching", teaching_case_id="case-synthetic-transplant"))
    ticket = repository.handoff(case["id"], HandoffCase(revision=1, target="explain"))
    assert "Initial synthetic presentation" in ticket["case_text"]
    assert HIDDEN_SENTINEL not in json.dumps(ticket)
    context = repository.resolve_handoff(ticket["id"], "explain")
    assert HIDDEN_SENTINEL not in json.dumps(context["messages"])
    repository.cancel_handoff(ticket["id"])
    assert context["cancel"].is_set()
    with pytest.raises(ApiError):
        repository.commit_handoff(ticket["id"], "explain", LATE_SENTINEL,
                                  cancel=context["cancel"], scope=context["scope"])
    assert_absent_from_profile(services, HIDDEN_SENTINEL, LATE_SENTINEL)


def test_invalid_handoff_answer_does_not_append_the_question(repository, services):
    case = start(repository)
    ticket = repository.handoff(case["id"], HandoffCase(
        revision=1, target="explain", question="A synthetic question"))
    context = repository.resolve_handoff(ticket["id"], "explain")
    with pytest.raises(ApiError):
        repository.commit_handoff(ticket["id"], "explain", "  ",
                                  cancel=context["cancel"], scope=context["scope"])
    assert repository.get(case["id"])["messages"] == []
    assert_absent_from_profile(services, SENTINEL)


@pytest.mark.parametrize("mutation", ["edit", "save", "delete", "cancel"])
def test_handoff_cannot_commit_after_cancel_revision_promotion_or_deletion(repository, services, mutation):
    case = start(repository)
    ticket = repository.handoff(case["id"], HandoffCase(revision=1, target="explain"))
    context = repository.resolve_handoff(ticket["id"], "explain")
    if mutation == "edit":
        repository.edit(case["id"], EditCase(revision=1, title="Changed"))
    elif mutation == "save":
        repository.save(case["id"], 1)
    elif mutation == "delete":
        repository.delete(case["id"], 1)
    else:
        context["cancel"].set()
    with pytest.raises(ApiError):
        repository.commit_handoff(ticket["id"], "explain", LATE_SENTINEL,
                                  cancel=context["cancel"], scope=context["scope"])
    if mutation != "save":
        assert_absent_from_profile(services, SENTINEL, LATE_SENTINEL)
    else:
        row = services.db.fetch_one("SELECT * FROM case_sessions WHERE id=?", (case["id"],))
        assert LATE_SENTINEL not in repr(row)
