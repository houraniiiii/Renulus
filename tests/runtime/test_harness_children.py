# SPDX-License-Identifier: MIT
"""H07 public family seam; journal/native ports are explicitly synthetic.

Uses the actual canonical Database and supplied-connection child configuration
authority. The parent owns production journal DDL; this provisional SQLite
fixture does not establish native child or H07 acceptance.
"""
from dataclasses import replace
import asyncio
import json

import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.runtime.harness_children import (
    HarnessChildren, ParentChildAuthority, ChildFamily, ChildRecord, ChildBounds,
)
from renulus.runtime.harness_configuration import (
    ConfigurationAuthority, ConfigurationSpec, ConnectionReference,
)
from renulus.runtime.harness_domain import DomainBinding, DomainCancellation, DomainRequest
from renulus.runtime.harness_library import LibraryAuthority
from renulus.storage import Database, utc_now
from tests.runtime.test_harness_configuration import activate
from tests.runtime.test_harness_library import library, note


BOUNDS = ChildBounds(max_depth=1, concurrency=2, max_families=16, max_records=64,
    max_owned=8, max_work_bytes=65536, max_report_bytes=65536, max_sources=128,
    max_source_bytes=65536, max_retained_bytes=4194304, max_settlement_seconds=30)


class SyntheticJournal:
    """Provisional metadata-only SQL journal, never a module migration."""
    def __init__(self, db):
        db.apply_migration('synthetic-h07-journal', '''
            CREATE TABLE synthetic_child_families(root_id TEXT PRIMARY KEY, value_json TEXT NOT NULL);
            CREATE TABLE synthetic_child_records(reservation_id TEXT PRIMARY KEY, root_id TEXT NOT NULL,
                invocation_key TEXT NOT NULL, value_json TEXT NOT NULL, UNIQUE(root_id,invocation_key));
        ''')

    def families_in(self, conn):
        return tuple(ChildFamily.from_json(row[0]) for row in conn.execute(
            'SELECT value_json FROM synthetic_child_families ORDER BY root_id'))

    def family_in(self, conn, root_id):
        row = conn.execute('SELECT value_json FROM synthetic_child_families WHERE root_id=?',
            (root_id,)).fetchone()
        return ChildFamily.from_json(row[0]) if row else None

    def put_family_in(self, conn, family):
        conn.execute('INSERT INTO synthetic_child_families VALUES(?,?) ON CONFLICT(root_id) '
            'DO UPDATE SET value_json=excluded.value_json', (family.root_id, family.to_json()))

    def children_in(self, conn, root_id):
        return tuple(ChildRecord.from_json(row[0]) for row in conn.execute(
            'SELECT value_json FROM synthetic_child_records WHERE root_id=? ORDER BY reservation_id',
            (root_id,)))

    def child_in(self, conn, reservation_id):
        row = conn.execute('SELECT value_json FROM synthetic_child_records WHERE reservation_id=?',
            (reservation_id,)).fetchone()
        return ChildRecord.from_json(row[0]) if row else None

    def put_child_in(self, conn, child):
        conn.execute('INSERT INTO synthetic_child_records VALUES(?,?,?,?) '
            'ON CONFLICT(reservation_id) DO UPDATE SET value_json=excluded.value_json',
            (child.reservation_id, child.root_id, child.invocation_key, child.to_json()))


@pytest.fixture
def family(tmp_path):
    db = Database(tmp_path / 'canonical.sqlite')
    return make_family(db)


def make_family(db, library=None, controls=None, publication_check=None, extra_current=None):
    authority = ConfigurationAuthority(db)
    version = activate(authority, ConfigurationSpec(connection=ConnectionReference(
        provider='opencode-go', credential_reference='synthetic-go', credential_revision=1,
        selected_model='mimo-v2.6-pro'), registry_hash='a' * 64,
        capabilities=('tools', 'library-read')))
    authority.begin_run('root-1', 'explain', capability_scope=('tools', 'library-read'))
    binding = DomainBinding('root-1', '1', 'ses_root', 'msg_root', 'root-1')
    token = DomainCancellation()
    calls = []

    def current(*, conn=None):
        token.check_current()
        authority.require_current('root-1', required_capabilities=('tools', 'library-read'), conn=conn)
        if extra_current is not None:
            extra_current(conn)

    library_authority = LibraryAuthority(ContextScope(kind=Scope.STUDY), None, 1, 0,
        lambda: token.cancelled, lambda conn: current(conn=conn), lambda refs: None)
    parent = ParentChildAuthority(binding, 'synthetic-profile', 'synthetic-store', 'generation-1',
        'root-1', version, authority.revocation_overlay()['epoch'], token, current, library_authority)

    async def stop(snapshot):
        calls.append('stop')

    async def settled(snapshot):
        calls.append('settled')

    children = HarnessChildren(db, resolve_parent=lambda supplied: parent if supplied == binding else None,
        journal=SyntheticJournal(db), configuration_authority=authority,
        library=library, record_consumed_in=lambda conn, run_id, **closure: calls.append(closure),
        require_publication=publication_check or (lambda supplied, conn: None),
        stop_family=controls.stop if controls else stop,
        settle_family=controls.settled if controls else settled,
        seal_root_in=lambda conn, root: calls.append('root-sealed'),
        release_family_in=lambda conn, snapshot: calls.append('released'), bounds=BOUNDS)
    return children, parent, authority, calls


def invocation(call='call-1'):
    return {'message_id': 'msg_assistant', 'tool_call_id': call}


def work(prompt='Review dialysis access evidence.'):
    return {'description': 'Bounded evidence review', 'prompt': prompt, 'background': False}


def test_trusted_reservation_is_atomic_and_retains_canonical_intersection(family):
    children, parent, authority, _ = family
    reservation = children.prepare(parent.binding, invocation(), work())
    assert reservation.attempt_id == '1' and reservation.cancellation_id == reservation.operation_id
    assert reservation.grant_epoch == parent.grant_epoch
    status = children.status(parent.binding)
    assert status.reserved == 1 and status.admitted == 0 and status.max_depth == 1
    assert status.concurrency == 2
    child = authority.run(reservation.operation_id)
    assert child['root_id'] == parent.root_id and child['parent_id'] == parent.binding.operation_id
    assert child['purpose'] == 'evidence-review' and child['route']['model_id'] == 'mimo-v2.6-pro'
    assert child['effective_capabilities'] == ['library-read', 'tools']


def test_actual_child_input_binds_once_and_supplies_existing_model_authority(family):
    children, parent, _, _ = family
    reservation = children.prepare(parent.binding, invocation(), work())
    binding = DomainBinding(reservation.operation_id, '1', 'ses_child', 'msg_actual_user',
        reservation.cancellation_id)
    assert children.resolve_model_run(binding) is None
    assert children.admit_input(reservation.reservation_id, binding).admitted is True
    assert children.admit_input(reservation.reservation_id, binding).admitted is True
    with pytest.raises(ApiError) as failure:
        children.admit_input(reservation.reservation_id, replace(binding, input_id='msg_other_user'))
    assert failure.value.code == 'child_binding_conflict'
    model = children.resolve_model_run(binding)
    assert model.binding == binding and model.purpose == 'evidence-review'
    assert model.operation_model == 'mimo-v2.6-pro'
    assert model.required_capabilities == ('library-read', 'tools')
    assert children.resolve_model_run(binding).cancellation is model.cancellation
    with children.db.transaction() as conn:
        assert model.current(conn=conn) is None
    assert children.status(parent.binding).admitted == 1


async def test_native_mutation_check_uses_only_the_exact_reservation_and_stage(family):
    children, parent, _, _ = family
    reservation = children.prepare(parent.binding, invocation(), work())
    request = DomainRequest('cb-check', parent.binding, 'child.check',
        {'reservation_id': reservation.reservation_id, 'stage': 'after_permission'})
    grant = await children.authorize(request)
    assert grant.binding == parent.binding and grant.check_current() is True
    assert await grant.handler(request, DomainCancellation()) == {
        'current': True, 'grant_epoch': parent.grant_epoch}
    with pytest.raises(ApiError) as failure:
        await children.authorize(replace(request, payload={**request.payload, 'stage': 'anything'}))
    assert failure.value.code == 'child_payload_invalid'
    assert children.status(parent.binding).reserved == 1


async def callback(children, binding, command, payload):
    request = DomainRequest('cb-' + command, binding, command, payload)
    grant = await children.authorize(request)
    assert grant is not None
    return await grant.handler(request, DomainCancellation())


async def test_report_consumption_uses_actual_library_receipts_and_retains_child_policy(library):
    import hashlib
    repo, adapter = library
    source = note(repo, 'Synthetic dialysis access surveillance assesses fistula flow and stenosis.')
    children, parent, authority, calls = make_family(repo.db, adapter)
    reservation = await callback(children, parent.binding, 'child.prepare',
        {'invocation': invocation(), 'work': work()})
    binding = DomainBinding(reservation['operation_id'], reservation['attempt_id'],
        'ses_actual_child', 'msg_actual_child_user', reservation['cancellation_id'])
    assert await callback(children, binding, 'child.admit_input',
        {'reservation_id': reservation['reservation_id']}) == {'admitted': True}
    retrieved = await callback(children, binding, 'library.retrieve',
        {'command': 'library.retrieve', 'arguments': {'query': 'fistula stenosis', 'limit': 1},
            'envelope': {}})
    assert retrieved['passages'][0]['document_revision'] == source['revision_id']
    assert await callback(children, binding, 'child.observe_job',
        {'reservation_id': reservation['reservation_id'], 'job_id': 'job_actual',
            'started_at': 1000, 'notification_id': 'notification_actual'}) == {'observed': True}
    output = 'Synthetic review: source supports surveillance. doc_forged is not a source grant.'
    digest = hashlib.sha256(output.encode()).hexdigest()
    report = await callback(children, binding, 'child.report',
        {'reservation_id': reservation['reservation_id'], 'notification_id': 'notification_actual',
            'report_digest': digest, 'output': output})
    with children.db.transaction() as conn:
        assert children.consume_report_in(conn, root_binding=parent.binding,
            child_binding=binding, report_digest=digest) == {'consumed': True}
    closure = next(item for item in calls if isinstance(item, dict))
    assert closure['inputs'] == ()
    assert closure['dependencies'][0].target.id == source['revision_id']
    assert closure['citations'][0]['document_id'] == source['document_id']
    assert closure['citations'][0]['passage_id'] == retrieved['passages'][0]['id']
    snapshot = children.status(parent.binding).families[0]
    assert output not in snapshot.children[0].to_json()
    assert 'Review dialysis access evidence.' not in snapshot.children[0].to_json()
    assert authority.run(binding.operation_id)['state'] == 'active'
    assert await callback(children, parent.binding, 'child.consume_report',
        {'report_id': report['report_id']}) == {'consumed': True}
    assert children.status(parent.binding).consumed == 1
    repo.delete_document(source['document_id'])
    with children.db.transaction() as conn:
        with pytest.raises(ApiError) as changed:
            children.require_publication_in(conn, root_binding=parent.binding)
    assert changed.value.code == 'harness_sources_changed'
    assert authority.run(binding.operation_id)['state'] == 'active'


class HeldLibrary:
    """Synthetic public latency port; no source or engine success claimed."""
    def __init__(self):
        self.entered, self.finish, self.finalizing, self.release = (asyncio.Event() for _ in range(4))

    async def execute(self, command, arguments, authority):
        self.entered.set()
        try:
            await self.finish.wait()
            return {'passages': []}
        finally:
            self.finalizing.set()
            await self.release.wait()


class HeldNative:
    """Terminal metadata is deliberately insufficient until this finalizer exits."""
    def __init__(self):
        self.stopped, self.release = asyncio.Event(), asyncio.Event()

    async def stop(self, snapshot):
        assert snapshot.family.state == 'sealed'
        self.stopped.set()

    async def settled(self, snapshot):
        await self.release.wait()


async def test_stop_retains_actual_domain_and_native_finalizers_after_observer_cancellation(tmp_path):
    held, native = HeldLibrary(), HeldNative()
    children, parent, _, calls = make_family(Database(tmp_path / 'held.sqlite'), held, native)
    reservation = children.prepare(parent.binding, invocation(), work())
    binding = DomainBinding(reservation.operation_id, '1', 'ses_held', 'msg_held', reservation.cancellation_id)
    children.admit_input(reservation.reservation_id, binding)
    observer = asyncio.create_task(callback(children, binding, 'library.retrieve',
        {'command': 'library.retrieve', 'arguments': {'query': 'access'}, 'envelope': {}}))
    try:
        await asyncio.wait_for(held.entered.wait(), 2)
        observer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await observer
        assert children.status(parent.binding).owned == 1
        children.seal(parent.binding)
        await asyncio.wait_for(native.stopped.wait(), 2)
        assert (await children.settlement(parent.binding, .02))['state'] == 'pending'
        with pytest.raises(ApiError) as failure:
            children.prepare(parent.binding, invocation('late-call'), work())
        assert failure.value.code == 'child_family_sealed'
        held.finish.set()
        await asyncio.wait_for(held.finalizing.wait(), 2)
        assert (await children.settlement(parent.binding, .02))['state'] == 'pending'
        native.release.set()
        assert (await children.settlement(parent.binding, .02))['state'] == 'pending'
        assert 'released' not in calls
        held.release.set()
        assert (await children.settlement(parent.binding, 2))['state'] == 'settled'
        assert calls.count('released') == 1 and children.status(parent.binding).owned == 0
    finally:
        held.finish.set()
        held.release.set()
        native.release.set()
        if not observer.done():
            observer.cancel()
        await asyncio.gather(observer, return_exceptions=True)


async def reported(family):
    import hashlib
    children, parent, _, _ = family
    reservation = children.prepare(parent.binding, invocation(), work())
    binding = DomainBinding(reservation.operation_id, '1', 'ses_report', 'msg_report', reservation.cancellation_id)
    children.admit_input(reservation.reservation_id, binding)
    await callback(children, binding, 'child.observe_job',
        {'reservation_id': reservation.reservation_id, 'job_id': 'job_report',
            'started_at': 1000, 'notification_id': 'notification_report'})
    output = 'Synthetic bounded report without a source claim.'
    payload = {'reservation_id': reservation.reservation_id, 'notification_id': 'notification_report',
        'report_digest': hashlib.sha256(output.encode()).hexdigest(), 'output': output}
    report = await callback(children, binding, 'child.report', payload)
    return reservation, binding, payload, report


async def test_report_replay_preserves_one_root_consumption_and_never_reuses_a_child_slot(family):
    children, parent, authority, calls = family
    _, binding, payload, report = await reported(family)
    consume = {'report_id': report['report_id']}
    await callback(children, parent.binding, 'child.consume_report', consume)
    assert await callback(children, binding, 'child.report', payload) == report
    await callback(children, parent.binding, 'child.consume_report', consume)
    assert len([call for call in calls if isinstance(call, dict)]) == 1
    assert children.status(parent.binding).consumed == 1
    children.prepare(parent.binding, invocation('call-2'), work())
    with pytest.raises(ApiError) as failure:
        children.prepare(parent.binding, invocation('call-3'), work())
    assert failure.value.code == 'child_concurrency_exhausted'
    assert authority.run(binding.operation_id)['state'] == 'active'


async def test_root_final_transaction_rechecks_consumed_child_permits_and_revocations(tmp_path):
    supplied = []

    def require_publication(binding, *, conn):
        assert conn.in_transaction
        supplied.append(conn)

    family = make_family(Database(tmp_path / 'publication.sqlite'), publication_check=require_publication)
    children, parent, authority, _ = family
    _, binding, _, report = await reported(family)
    await callback(children, parent.binding, 'child.consume_report', {'report_id': report['report_id']})
    with children.db.transaction() as conn:
        assert children.require_publication_in(conn, root_binding=parent.binding) is None
        assert supplied[-1] is conn
    authority.revoke('purpose:evidence-review')
    with children.db.transaction() as conn:
        with pytest.raises(ApiError) as failure:
            children.require_publication_in(conn, root_binding=parent.binding)
    assert failure.value.code == 'child_grant_epoch_changed'
    assert children.status(parent.binding).consumed == 1


async def test_repeated_settlement_does_not_reseal_or_release_the_root_again(family):
    children, parent, _, calls = family
    children.prepare(parent.binding, invocation(), work())
    children.seal(parent.binding)
    assert (await children.settlement(parent.binding, 2))['state'] == 'settled'
    assert (await children.settlement(parent.binding, 2))['state'] == 'settled'
    assert calls.count('root-sealed') == 1
    assert calls.count('released') == 1


async def test_report_freezes_library_receipts_before_any_late_effect(tmp_path):
    class CountingLibrary:
        """Synthetic effect counter, no source retrieval success claimed."""
        calls = 0

        async def execute(self, command, arguments, authority):
            self.calls += 1
            return {'passages': []}

    library = CountingLibrary()
    family = make_family(Database(tmp_path / 'closed-report.sqlite'), library)
    children, parent, _, _ = family
    _, binding, _, _ = await reported(family)
    with pytest.raises(ApiError) as failure:
        await callback(children, binding, 'library.retrieve',
            {'command': 'library.retrieve', 'arguments': {'query': 'late'}, 'envelope': {}})
    assert failure.value.code == 'child_report_closed'
    assert library.calls == 0 and children.status(parent.binding).reported == 1


def test_reopened_journal_inspects_but_never_restores_live_child_authority(family):
    children, parent, _, _ = family
    reservation = children.prepare(parent.binding, invocation(), work())
    binding = DomainBinding(reservation.operation_id, '1', 'ses_reopen', 'msg_reopen',
        reservation.cancellation_id)
    children.admit_input(reservation.reservation_id, binding)
    reopened = HarnessChildren(children.db, resolve_parent=children.resolve_parent,
        journal=children.journal, configuration_authority=children.configuration,
        library=children.library, record_consumed_in=children.record_consumed_in,
        require_publication=children.require_publication, stop_family=children.stop_family,
        settle_family=children.settle_family, seal_root_in=children.seal_root_in,
        release_family_in=children.release_family_in, bounds=BOUNDS)
    assert reopened.status(parent.binding).admitted == 1
    with pytest.raises(ApiError) as failure:
        reopened.resolve_model_run(binding)
    assert failure.value.code == 'child_recovery_required'
    with pytest.raises(ApiError) as replay:
        reopened.prepare(parent.binding, invocation(), work())
    assert replay.value.code == 'child_recovery_required'


def test_reservation_rolls_back_canonical_policy_and_journal_on_internal_guard_failure(tmp_path):
    initiating = ApiError('synthetic_internal_guard_failure', 'Synthetic local guard failure.', 500)
    checks = []

    def guard(conn):
        assert conn.in_transaction
        checks.append(conn)
        if len(checks) == 2:
            raise initiating

    children, parent, _, _ = make_family(Database(tmp_path / 'rollback.sqlite'), extra_current=guard)
    with pytest.raises(ApiError) as failure:
        children.prepare(parent.binding, invocation(), work())
    assert failure.value is initiating and checks[0] is checks[1]
    assert children.status().families == ()
    with children.db.transaction() as conn:
        assert conn.execute('SELECT COUNT(*) FROM harness_configuration_runs').fetchone()[0] == 1


async def test_untrusted_payload_cannot_override_grants_or_reserve_a_grandchild(family):
    children, parent, _, _ = family
    with pytest.raises(ApiError) as failure:
        await callback(children, parent.binding, 'child.prepare',
            {'invocation': invocation(), 'work': work(), 'model': 'untrusted-model'})
    assert failure.value.code == 'child_payload_invalid'
    with pytest.raises(ApiError):
        children.prepare(parent.binding, invocation(), {**work(), 'capabilities': ['untrusted-grant']})
    assert children.status().families == ()
    reservation = children.prepare(parent.binding, invocation(), work())
    binding = DomainBinding(reservation.operation_id, '1', 'ses_leaf', 'msg_leaf', reservation.cancellation_id)
    children.admit_input(reservation.reservation_id, binding)
    with pytest.raises(ApiError) as descendant:
        children.prepare(binding, invocation('grandchild'), work())
    assert descendant.value.code == 'child_parent_unavailable'
    assert children.status(parent.binding).admitted == 1


@pytest.mark.parametrize('code,status', [('synthetic_internal_current', 500), ('harness_sources_changed', 409)])
def test_existing_model_current_preserves_exact_local_authority_failure(tmp_path, code, status):
    failure = ApiError(code, 'Synthetic local current failure.', status)
    changed = False

    def guard(conn):
        if changed:
            raise failure

    children, parent, _, _ = make_family(Database(tmp_path / 'current.sqlite'), extra_current=guard)
    reservation = children.prepare(parent.binding, invocation(), work())
    binding = DomainBinding(reservation.operation_id, '1', 'ses_guard', 'msg_guard', reservation.cancellation_id)
    children.admit_input(reservation.reservation_id, binding)
    model = children.resolve_model_run(binding)
    changed = True
    with children.db.transaction() as conn:
        with pytest.raises(ApiError) as caught:
            model.current(conn=conn)
    assert caught.value is failure


def test_parent_cancellation_invalidates_retained_child_model_authority(family):
    from renulus.runtime.harness_domain import DomainCancelled
    children, parent, _, _ = family
    reservation = children.prepare(parent.binding, invocation(), work())
    binding = DomainBinding(reservation.operation_id, '1', 'ses_cancelled', 'msg_cancelled',
        reservation.cancellation_id)
    children.admit_input(reservation.reservation_id, binding)
    model = children.resolve_model_run(binding)
    parent.cancellation.cancel()
    with pytest.raises(DomainCancelled):
        model.current()
    assert model.cancellation.cancelled and children.status(parent.binding).admitted == 1


@pytest.mark.parametrize('changes', [{'max_depth': 2}, {'concurrency': 3},
    {'max_owned': True}, {'max_source_bytes': 0}])
def test_explicit_bounds_reject_depth_capacity_and_noninteger_widening(changes):
    with pytest.raises(ApiError) as failure:
        replace(BOUNDS, **changes)
    assert failure.value.code == 'child_bounds_invalid'


async def test_native_settlement_error_retains_the_sealed_family_and_original_code(tmp_path):
    class FailedNative:
        calls = 0

        async def stop(self, snapshot):
            self.calls += 1

        async def settled(self, snapshot):
            raise ApiError('synthetic_native_finalizer_failed', 'Synthetic native failure.', 500)

    controls = FailedNative()
    children, parent, _, calls = make_family(Database(tmp_path / 'blocked.sqlite'), controls=controls)
    children.prepare(parent.binding, invocation(), work())
    for _ in range(2):
        result = await children.settlement(parent.binding, 2)
        assert result['state'] == 'blocked' and result['code'] == 'synthetic_native_finalizer_failed'
    assert children.status(parent.binding).families[0].family.state == 'sealed'
    assert controls.calls == 1 and 'released' not in calls


async def test_stop_retains_a_queued_prepare_handler_before_family_creation(family):
    from renulus.runtime.harness_domain import DomainCancelled
    children, parent, _, _ = family
    children.seal_root_in = lambda conn, binding: parent.cancellation.cancel()
    observer = asyncio.create_task(callback(children, parent.binding, 'child.prepare',
        {'invocation': invocation(), 'work': work()}))
    try:
        await asyncio.sleep(0)  # handler owns its queued task; no family exists yet
        children.seal(parent.binding)
        assert children.status(parent.binding).owned == 1
        assert (await children.settlement(parent.binding, 2))['state'] == 'settled'
        assert children.status(parent.binding).owned == 0
        with pytest.raises(DomainCancelled):
            await observer
        assert children.status().families == ()
    finally:
        await asyncio.gather(observer, return_exceptions=True)
