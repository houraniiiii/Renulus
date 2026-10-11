# SPDX-License-Identifier: MIT
"""Public child learning routing on real Children/journal/configuration ports.

All root, Library and native callbacks below are explicitly synthetic. These
tests establish no native execution, provider, publication or H07 acceptance.
"""
import asyncio
import hashlib
from dataclasses import replace
from types import SimpleNamespace

import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.runtime.harness_children import ChildBounds, HarnessChildren, ParentChildAuthority
from renulus.runtime.harness_children_journal import HarnessChildrenJournal
from renulus.runtime.harness_configuration import (
    ConfigurationAuthority, ConfigurationSpec, ConnectionReference,
)
from renulus.runtime.harness_domain import DomainBinding, DomainCancellation, DomainCancelled, DomainRequest
from renulus.runtime.harness_learning_children import HarnessLearningChildren
from renulus.runtime.harness_library import LibraryAuthority
from renulus.storage import Database
from tests.runtime.test_harness_configuration import activate


BOUNDS = ChildBounds(max_depth=1, concurrency=2, max_families=16, max_records=64,
    max_owned=8, max_work_bytes=65536, max_report_bytes=65536, max_sources=128,
    max_source_bytes=65536, max_retained_bytes=4194304, max_settlement_seconds=30)


class SyntheticLibrary:
    """Public Library IO stand-in: no engines, provenance or eligibility claims."""
    def __init__(self, db):
        self.db = db
        self.entered = self.finish = self.finalizing = self.release = None

    async def execute(self, command, arguments, authority):
        with self.db.transaction() as conn:
            authority.guard(conn)
        assert authority.scope.model_dump(mode="json") == {"kind": "study", "entity_id": "synthetic-topic"}
        assert authority.revision_ids == ("synthetic-revision",)
        if self.entered is not None:
            self.entered.set()
            try:
                await self.finish.wait()
                return {"passages": []}
            finally:
                self.finalizing.set()
                await self.release.wait()
        return {"passages": []} if command == "library.retrieve" else {"synthetic_reference": True}


@pytest.fixture
def family(tmp_path):
    db = Database(tmp_path / "canonical.sqlite")
    authority = ConfigurationAuthority(db)
    version = activate(authority, ConfigurationSpec(connection=ConnectionReference(
        provider="opencode-go", credential_reference="synthetic-go", credential_revision=1,
        selected_model="mimo-v2.6-pro"), registry_hash="a" * 64,
        capabilities=("tools", "library-read")))
    authority.begin_run("root-1", "explain", capability_scope=("tools", "library-read"))
    binding = DomainBinding("root-1", "1", "ses_root", "msg_root", "root-1")
    token = DomainCancellation()
    state = SimpleNamespace(context="Synthetic pinned learner preference.", fault=None,
        context_effect=None, stop_release=None, native_release=None, closures=[], publications=[],
        publication_conn=None)
    state.library = SyntheticLibrary(db)

    def current(*, conn=None):
        token.check_current()
        authority.require_current("root-1", required_capabilities=("tools", "library-read"), conn=conn)
        if state.fault is not None:
            raise state.fault

    library = LibraryAuthority(ContextScope(kind=Scope.STUDY, entity_id="synthetic-topic"),
        ("synthetic-revision",), 11, 8, lambda: token.cancelled,
        lambda conn: current(conn=conn), lambda references: None)
    parent = ParentChildAuthority(binding, "synthetic-profile", "synthetic-store",
        "synthetic-generation", "root-1", version, authority.revocation_overlay()["epoch"],
        token, current, library)

    async def stop(snapshot):
        if state.stop_release is not None:
            await state.stop_release.wait()

    async def settle(snapshot):
        if state.native_release is not None:
            await state.native_release.wait()

    def context(root):
        assert root == binding
        if state.context_effect is not None:
            state.context_effect()
        return state.context

    journal = HarnessChildrenJournal(db)
    def publication(supplied, *, conn):
        assert conn.in_transaction
        state.publications.append(supplied)
        state.publication_conn = conn

    children = HarnessChildren(db, resolve_parent=lambda supplied: parent if supplied == binding else None,
        journal=journal, configuration_authority=authority, library=state.library,
        record_consumed_in=lambda conn, run_id, **closure: state.closures.append(closure),
        require_publication=publication,
        stop_family=stop, settle_family=settle, seal_root_in=lambda conn, root: None,
        release_family_in=lambda conn, snapshot: None, bounds=BOUNDS)
    helper = HarnessLearningChildren(children, learner_context=context)
    return SimpleNamespace(db=db, authority=authority, parent=parent, children=children,
        journal=journal, helper=helper, state=state)


def admit(family, call="call-1", session="ses_child", user="msg_child_user"):
    reservation = family.children.prepare(family.parent.binding,
        {"message_id": "msg_root_assistant", "tool_call_id": call},
        {"description": "Synthetic review", "prompt": "Review synthetic dialysis access.", "background": False})
    binding = DomainBinding(reservation.operation_id, "1", session, user, reservation.cancellation_id)
    family.children.admit_input(reservation.reservation_id, binding)
    return reservation, binding


async def callback(helper, binding, command, payload):
    request = DomainRequest("cb-" + command, binding, command, payload)
    grant = await helper.authorize(request)
    assert grant is not None and grant.binding == binding
    assert grant.check_current() is True
    return await grant.handler(request, DomainCancellation())


async def test_admitted_child_authority_uses_original_root_scope_and_child_identity(family):
    _, binding = admit(family)
    assert await callback(family.helper, binding, "learning.authority", {}) == {
        "sessionId": "ses_child", "operationId": binding.operation_id, "attemptId": "1",
        "scope": {"kind": "study", "entity_id": "synthetic-topic"},
        "revisionIds": ("synthetic-revision",), "policyRevision": 11,
        "contextEpoch": 8, "cancellationEpoch": 0,
    }


async def test_six_native_callbacks_keep_reported_distinct_until_explicit_consumption(family):
    reservation = await callback(family.helper, family.parent.binding, "child.prepare", {
        "invocation": {"message_id": "msg_root_assistant", "tool_call_id": "call-1"},
        "work": {"description": "Synthetic review", "prompt": "Review dialysis access.", "background": True},
    })
    binding = DomainBinding(reservation["operation_id"], "1", "ses_child", "msg_child_user",
        reservation["cancellation_id"])
    assert await callback(family.helper, binding, "child.admit_input",
        {"reservation_id": reservation["reservation_id"]}) == {"admitted": True}
    assert await callback(family.helper, family.parent.binding, "child.check", {
        "reservation_id": reservation["reservation_id"], "stage": "before_prompt",
    }) == {"current": True, "grant_epoch": family.parent.grant_epoch}
    assert await callback(family.helper, binding, "child.observe_job", {
        "reservation_id": reservation["reservation_id"], "job_id": "synthetic-job",
        "started_at": 1000, "notification_id": "synthetic-notification",
    }) == {"observed": True}
    output = "Synthetic report; no evidence is inferred from this text."
    report = await callback(family.helper, binding, "child.report", {
        "reservation_id": reservation["reservation_id"], "notification_id": "synthetic-notification",
        "report_digest": hashlib.sha256(output.encode()).hexdigest(), "output": output,
    })
    assert family.children.status(family.parent.binding).reported == 1
    assert family.children.status(family.parent.binding).consumed == 0
    assert await callback(family.helper, family.parent.binding, "child.consume_report",
        {"report_id": report["report_id"]}) == {"consumed": True}
    assert family.children.status(family.parent.binding).consumed == 1
    assert family.state.closures == [{"inputs": (), "dependencies": (), "citations": ()}]


async def test_child_context_selects_current_origin_groups_and_pinned_root_context(family):
    _, binding = admit(family)
    result = await callback(family.helper, binding, "learning.context", {"messages": [
        {"id": "msg_previous_user", "role": "user"},
        {"id": "msg_previous_answer", "role": "assistant"},
        {"id": "msg_previous_answer", "role": "tool"},
        {"id": "msg_root", "role": "user"},
        {"id": "msg_root_answer", "role": "assistant"},
        {"id": "msg_root_answer", "role": "tool"},
        {"id": "msg_child_user", "role": "user"},
        {"id": "msg_child_answer", "role": "assistant"},
        {"id": "msg_child_answer", "role": "tool"},
        {"id": "msg_child_answer", "role": "tool"},
        {"id": "msg_child_continuation", "role": "assistant"},
    ]})
    assert result == {"message_ids": ["msg_child_user", "msg_child_answer", "msg_child_continuation"],
        "learner_context": "Synthetic pinned learner preference."}
    assert family.children.status(family.parent.binding).admitted == 1
    assert family.state.closures == []


@pytest.mark.parametrize("messages", [
    None, {}, [],
    [{"id": "msg_wrong_user", "role": "user"}],
    [{"id": "msg_child_user", "role": "assistant"}],
    [{"id": "msg_child_user", "role": "user"}, {"id": "msg_other", "role": "user"}],
    [{"id": "msg_child_user", "role": "user"}, {"id": "msg_child_user", "role": "user"}],
    [{"id": "msg_child_user", "role": "user"}, {"id": "msg_child_user", "role": "tool"}],
    [{"id": "msg_child_user", "role": "user"}, {"id": "msg_unknown", "role": "tool"}],
    [{"id": "msg_old", "role": "assistant"}, {"id": "msg_child_user", "role": "user"},
        {"id": "msg_old", "role": "tool"}],
    [{"id": "msg_child_user", "role": "user"}, {"id": "msg_answer", "role": "assistant"},
        {"id": "msg_answer", "role": "assistant"}],
    [{"id": "msg_child_user", "role": "user", "text": "Raw content is not lineage."}],
    [{"id": "msg_child_user", "role": "user"}, {"id": "msg_system", "role": "system"}],
    [{"id": True, "role": "user"}], ["msg_child_user"],
    [{"id": "msg_child_user", "role": "user"}, {"id": "", "role": "assistant"}],
])
async def test_unverifiable_context_descriptors_fail_closed(family, messages):
    _, binding = admit(family)
    with pytest.raises(ApiError) as failure:
        await callback(family.helper, binding, "learning.context", {"messages": messages})
    assert failure.value.code in {"harness_context_conflict", "harness_input_conflict"}


async def test_captured_context_grant_cannot_be_repurposed_after_authorization(family):
    _, binding = admit(family)
    request = DomainRequest("cb-context", binding, "learning.context", {"messages": [
        {"id": "msg_child_user", "role": "user"},
    ]})
    grant = await family.helper.authorize(request)
    request.payload["messages"].append({"id": "msg_added_after_grant", "role": "assistant"})
    with pytest.raises(ApiError) as failure:
        await grant.handler(request, DomainCancellation())
    assert failure.value.code == "child_callback_conflict"


@pytest.mark.parametrize("payload", [
    None, {},
    {"messages": [{"id": "msg_child_user", "role": "user"}], "scope": "widened"},
    {"messages": [{"id": "msg_child_user", "role": "user"}] +
        [{"id": "msg_answer_" + str(index), "role": "assistant"} for index in range(3000)]},
])
async def test_context_payload_is_bounded_metadata_without_authority_overrides(family, payload):
    _, binding = admit(family)
    with pytest.raises(ApiError) as failure:
        await callback(family.helper, binding, "learning.context", payload)
    assert failure.value.code == "harness_callback_payload"


def test_child_model_resolver_reuses_existing_stable_authority_and_local_current(family):
    _, binding = admit(family)
    original = family.children.resolve_model_run(binding)
    assert family.helper.resolve_model_run(binding) is original
    assert family.helper.resolve_model_run(binding) is original
    assert original.purpose == "evidence-review"
    assert original.required_capabilities == ("library-read", "tools")
    assert family.helper.resolve_model_run(family.parent.binding) is None
    with family.db.transaction() as conn:
        assert original.current(conn=conn) is None
    family.authority.revoke("tools")
    with pytest.raises(ApiError) as failure:
        original.current()
    assert failure.value.code == "capability_revoked"


@pytest.mark.parametrize("change,code", [
    ("capability", "capability_revoked"), ("epoch", "child_grant_epoch_changed"),
    ("cancel", None), ("internal", "synthetic_internal_fault"),
])
async def test_child_check_grant_preserves_exact_current_failure_after_authorization(family, change, code):
    _, binding = admit(family)
    request = DomainRequest("cb-check", binding, "learning.check", {})
    grant = await family.helper.authorize(request)
    assert grant is not None
    assert await grant.handler(request, DomainCancellation()) == {"current": True}
    if change == "capability":
        family.authority.revoke("tools")
    elif change == "epoch":
        family.authority.revoke("synthetic-unrelated")
    elif change == "cancel":
        family.parent.cancellation.cancel()
    else:
        family.state.fault = ApiError(code, "Synthetic initiating fault.", 503, True)
    for invoke in (grant.check_current, lambda: grant.handler(request, DomainCancellation())):
        with pytest.raises(DomainCancelled if change == "cancel" else ApiError) as failure:
            value = invoke()
            if asyncio.iscoroutine(value):
                await value
        if code is not None:
            assert failure.value.code == code
        if change == "internal":
            assert failure.value is family.state.fault


@pytest.mark.parametrize("command,expected", [
    ("library.retrieve", {"passages": []}), ("library.citation", {"synthetic_reference": True}),
])
async def test_child_library_routes_to_existing_scoped_family_grant(family, command, expected):
    _, binding = admit(family)
    payload = {"command": command, "arguments": {"query": "synthetic access"},
        "envelope": {"scope": "untrusted-observation", "model": "not-a-grant"}}
    assert await callback(family.helper, binding, command, payload) == expected
    root_request = DomainRequest("cb-root", family.parent.binding, command, payload)
    assert await family.helper.authorize(root_request) is None
    assert family.children.status(family.parent.binding).owned == 0


async def report_child(family, binding):
    await callback(family.helper, binding, "child.observe_job", {
        "reservation_id": binding.operation_id, "job_id": "synthetic-job",
        "started_at": 1000, "notification_id": "synthetic-notification",
    })
    output = "Synthetic report; no source is inferred."
    return await callback(family.helper, binding, "child.report", {
        "reservation_id": binding.operation_id, "notification_id": "synthetic-notification",
        "report_digest": hashlib.sha256(output.encode()).hexdigest(), "output": output,
    })


@pytest.mark.parametrize("command", ["learning.authority", "learning.check", "learning.context"])
async def test_reported_child_keeps_publication_pins_but_cannot_reopen_learning_callbacks(family, command):
    _, binding = admit(family)
    payload = {"messages": [{"id": "msg_child_user", "role": "user"}]} if command == "learning.context" else {}
    request = DomainRequest("cb-closed", binding, command, payload)
    grant = await family.helper.authorize(request)
    model = family.helper.resolve_model_run(binding)
    await report_child(family, binding)
    with family.db.transaction() as conn:
        assert model.current(conn=conn) is None
    with pytest.raises(ApiError) as failure:
        grant.check_current()
    assert failure.value.code == "child_report_closed"
    with pytest.raises(ApiError) as failure:
        await family.helper.authorize(request)
    assert failure.value.code == "child_report_closed"


@pytest.mark.parametrize("value,code", [
    (None, "harness_context_conflict"), (123, "harness_context_conflict"),
    ({"text": "untyped"}, "harness_context_conflict"),
    ("x" * 3001, "harness_context_conflict"),
    ("\U0001f9ec" * 1501, "harness_context_conflict"),
    ("\ud800", "harness_context_conflict"),
    ("coroutine", "child_local_callback_required"),
    ("future", "child_local_callback_required"),
], ids=["none", "integer", "mapping", "ascii-overbound", "utf16-overbound",
    "surrogate", "coroutine", "future"])
async def test_pinned_learner_context_is_synchronous_bounded_native_text(family, value, code):
    _, binding = admit(family)
    if value == "coroutine":
        value = asyncio.sleep(0)
    elif value == "future":
        value = asyncio.get_running_loop().create_future()
    family.state.context = value
    try:
        with pytest.raises(ApiError) as failure:
            await callback(family.helper, binding, "learning.context",
                {"messages": [{"id": "msg_child_user", "role": "user"}]})
        assert failure.value.code == code
        if asyncio.isfuture(value):
            assert not value.done()
    finally:
        if asyncio.iscoroutine(value):
            value.close()
        elif asyncio.isfuture(value):
            value.cancel()


async def test_root_publication_rechecks_consumed_child_permits_in_supplied_connection(family, tmp_path):
    _, binding = admit(family)
    report = await report_child(family, binding)
    await callback(family.helper, family.parent.binding, "child.consume_report",
        {"report_id": report["report_id"]})
    family.state.publication_conn = None
    model = family.helper.resolve_model_run(binding)
    with family.db.transaction() as conn:
        assert family.helper.require_publication_in(conn, root_binding=family.parent.binding) is None
        assert family.state.publication_conn is conn
        assert model.current(conn=conn) is None
    assert family.authority.run(binding.operation_id)["state"] == "active"
    assert family.children.status(family.parent.binding).consumed == 1
    with Database(tmp_path / "foreign.sqlite").transaction() as foreign:
        with pytest.raises(ApiError) as failure:
            family.helper.require_publication_in(foreign, root_binding=family.parent.binding)
        assert failure.value.code == "child_connection_mismatch"
    family.authority.revoke("tools")
    with family.db.transaction() as conn:
        with pytest.raises(ApiError) as failure:
            family.helper.require_publication_in(conn, root_binding=family.parent.binding)
        assert failure.value.code == "capability_revoked"


async def test_family_ports_retain_library_and_native_tasks_after_observer_cancellation(family):
    _, binding = admit(family)
    held = family.state.library
    held.entered, held.finish, held.finalizing, held.release = (asyncio.Event() for _ in range(4))
    family.state.native_release = asyncio.Event()
    observer = asyncio.create_task(callback(family.helper, binding, "library.retrieve",
        {"command": "library.retrieve", "arguments": {"query": "synthetic access"}, "envelope": {}}))
    try:
        await asyncio.wait_for(held.entered.wait(), 2)
        observer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await observer
        assert family.helper.status(family.parent.binding).owned == 1
        assert family.helper.seal(family.parent.binding) is None
        assert (await family.helper.settlement(family.parent.binding, .02))["state"] == "pending"
        held.finish.set()
        await asyncio.wait_for(held.finalizing.wait(), 2)
        family.state.native_release.set()
        assert (await family.helper.settlement(family.parent.binding, .02))["state"] == "pending"
        held.release.set()
        assert await family.helper.settlement(family.parent.binding, 2) == {"state": "settled", "owned": 0}
        status = family.helper.status(family.parent.binding)
        assert status.owned == status.cleanup_pending == 0
        assert status.families[0].family.state == "settled"
        assert status.families[0].children[0].state == "settled"
    finally:
        held.finish.set()
        held.release.set()
        family.state.native_release.set()
        if not observer.done():
            observer.cancel()
        await asyncio.gather(observer, return_exceptions=True)
        await family.children.settlement(family.parent.binding, 2)


@pytest.mark.parametrize("parent_id", ["msg_root", "msg_root_assistant"])
async def test_parent_user_and_invocation_origins_cannot_enter_child_suffix(family, parent_id):
    _, binding = admit(family)
    with pytest.raises(ApiError) as failure:
        await callback(family.helper, binding, "learning.context", {"messages": [
            {"id": "msg_child_user", "role": "user"}, {"id": parent_id, "role": "assistant"},
        ]})
    assert failure.value.code == "harness_context_conflict"


@pytest.mark.parametrize("field,value", [
    ("session_id", "ses_other"), ("input_id", "msg_other"),
    ("attempt_id", "2"), ("cancellation_id", "other-cancellation"),
])
async def test_known_child_with_changed_binding_never_falls_back_to_root(family, field, value):
    _, binding = admit(family)
    changed = replace(binding, **{field: value})
    with pytest.raises(ApiError) as failure:
        await family.helper.authorize(DomainRequest("cb-wrong", changed, "learning.check", {}))
    assert failure.value.code == "child_binding_conflict"


@pytest.mark.parametrize("command", ["learning.authority", "learning.check", "learning.context",
    "library.retrieve", "library.citation", "model.prepare", "child.unrecognized"])
async def test_root_and_unclaimed_commands_remain_with_the_original_owner(family, command):
    request = DomainRequest("cb-root", family.parent.binding, command, {})
    assert await family.helper.authorize(request) is None


@pytest.mark.parametrize("context", ["", "\U0001f9ec" * 1500], ids=["empty", "utf16-exact-bound"])
async def test_valid_retained_context_preserves_exact_bytes(family, context):
    _, binding = admit(family)
    family.state.context = context
    result = await callback(family.helper, binding, "learning.context",
        {"messages": [{"id": "msg_child_user", "role": "user"}]})
    assert result == {"message_ids": ["msg_child_user"], "learner_context": context}


@pytest.mark.parametrize("effect", ["cancel", "internal-failure"])
async def test_current_and_initiating_failure_are_preserved_during_local_context_callback(family, effect):
    _, binding = admit(family)
    initiating = ApiError("synthetic_context_fault", "Synthetic initiating failure.", 503, True)
    def fault():
        raise initiating
    family.state.context_effect = family.parent.cancellation.cancel if effect == "cancel" else fault
    with pytest.raises(DomainCancelled if effect == "cancel" else ApiError) as failure:
        await callback(family.helper, binding, "learning.context",
            {"messages": [{"id": "msg_child_user", "role": "user"}]})
    if effect == "internal-failure":
        assert failure.value is initiating


async def test_reopened_journal_is_inspectable_without_reauthorizing_old_child(family):
    _, binding = admit(family)
    children = HarnessChildren(family.db, resolve_parent=lambda supplied: family.parent,
        journal=HarnessChildrenJournal(family.db), configuration_authority=family.authority,
        library=family.state.library, record_consumed_in=lambda conn, run_id, **closure: None,
        require_publication=lambda supplied, conn: None,
        stop_family=family.children.stop_family, settle_family=family.children.settle_family,
        seal_root_in=lambda conn, root: None, release_family_in=lambda conn, snapshot: None, bounds=BOUNDS)
    helper = HarnessLearningChildren(children, learner_context=lambda root: family.state.context)
    assert helper.status(family.parent.binding).admitted == 1
    with pytest.raises(ApiError) as failure:
        await helper.authorize(DomainRequest("cb-reopened", binding, "learning.check", {}))
    assert failure.value.code == "child_recovery_required"
