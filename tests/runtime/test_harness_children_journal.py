# SPDX-License-Identifier: MIT
"""Public H07 journal ports on real SQLite; all identities are synthetic.

No native execution, provider, report body or authorization is established here.
"""
from dataclasses import dataclass, fields, replace
import json

import pytest

from renulus.contracts import ApiError
from renulus.design_c_contracts import canonical_digest
from renulus.runtime.harness_children import ChildFamily, ChildRecord
from renulus.runtime.harness_children_journal import HarnessChildrenJournal
from renulus.runtime.harness_domain import DomainBinding
from renulus.storage import Database


def synthetic_family(root_id='root-1'):
    return ChildFamily(root_id, DomainBinding(root_id, '1', 'session-' + root_id,
        'input-' + root_id, root_id), 'synthetic-profile', 'synthetic-store',
        'synthetic-generation', 'a' * 64, 7)


def synthetic_child(family, reservation_id='child-1', tool_call_id='tool-1'):
    invocation = {'message_id': 'assistant-' + family.root_id, 'tool_call_id': tool_call_id}
    return ChildRecord(reservation_id, family.root_id, family.root_binding,
        canonical_digest(invocation), invocation['message_id'], tool_call_id,
        'd' * 64, 45, False, family.family_epoch)


def synthetic_source(passage_id='passage-1'):
    # Trusted receipt shape only; no Library eligibility is asserted by this fixture.
    return {'dependency': {'target': {'type': 'library_revision', 'id': 'revision-1'},
        'expected_revision': 'b' * 64}, 'citation': {'document_id': 'document-1',
        'revision_id': 'revision-1', 'passage_id': passage_id,
        'content_ref': {'target': {'type': 'library_revision', 'id': 'revision-1'},
            'locator': {'kind': 'pdf', 'physical_page': 2, 'printed_label': None}},
        'locators': [{'page': 2, 'char_span': [0, 50], 'bbox': None}]}}


def sources_json(*sources):
    return json.dumps(sources, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':'))


@pytest.fixture
def journal(tmp_path):
    return HarnessChildrenJournal(Database(tmp_path / 'canonical.sqlite'))


def test_family_metadata_roundtrips_after_idempotent_migration_and_reopen(journal):
    family = synthetic_family()
    with journal.db.transaction() as conn:
        journal.put_family_in(conn, family)
        assert journal.family_in(conn, family.root_id) == family
        assert journal.families_in(conn) == (family,)
        assert journal.family_in(conn, 'missing-root') is None
    reopened = HarnessChildrenJournal(Database(journal.db.path))
    with reopened.db.transaction() as conn:
        assert reopened.families_in(conn) == (family,)


def test_family_seal_increments_epoch_once_and_settlement_is_terminal(journal):
    family = synthetic_family()
    sealed = replace(family, state='sealed', family_epoch=1)
    settled = replace(sealed, state='settled')
    with journal.db.transaction() as conn:
        journal.put_family_in(conn, family)
        for invalid in (replace(family, family_epoch=1), replace(family, state='settled'),
                replace(family, state='sealed'), replace(sealed, family_epoch=2)):
            with pytest.raises(ApiError) as failure:
                journal.put_family_in(conn, invalid)
            assert failure.value.code == 'child_journal_conflict'
        journal.put_family_in(conn, sealed)
        journal.put_family_in(conn, sealed)
        with pytest.raises(ApiError):
            journal.put_family_in(conn, replace(sealed, family_epoch=2))
        journal.put_family_in(conn, settled)
        journal.put_family_in(conn, settled)
        with pytest.raises(ApiError):
            journal.put_family_in(conn, family)
    with HarnessChildrenJournal(Database(journal.db.path)).db.transaction() as conn:
        assert journal.family_in(conn, family.root_id) == settled
        with pytest.raises(ApiError):
            journal.put_family_in(conn, replace(synthetic_family('other-root'), state='sealed'))


@pytest.mark.parametrize('port', ['families', 'family', 'put_family', 'children', 'child', 'put_child'])
def test_family_ports_require_the_same_actual_active_database_connection(journal, tmp_path, port):
    def invoke(conn):
        if port == 'families':
            return journal.families_in(conn)
        if port == 'family':
            return journal.family_in(conn, 'root-1')
        if port == 'children':
            return journal.children_in(conn, 'root-1')
        if port == 'child':
            return journal.child_in(conn, 'child-1')
        if port == 'put_child':
            return journal.put_child_in(conn, synthetic_child(synthetic_family()))
        return journal.put_family_in(conn, synthetic_family())

    conn = journal.db.connect()
    try:
        with pytest.raises(ApiError) as failure:
            invoke(conn)
        assert failure.value.code == 'child_transaction_required'
    finally:
        conn.close()
    with pytest.raises(ApiError) as failure:
        invoke(conn)
    assert failure.value.code == 'child_transaction_required'
    with Database(tmp_path / 'foreign.sqlite').transaction() as foreign:
        with pytest.raises(ApiError) as failure:
            invoke(foreign)
        assert failure.value.code == 'child_connection_mismatch'


@pytest.mark.parametrize('changes', [
    {'root_binding': DomainBinding('root-1', '1', 'other-session', 'input-root-1', 'root-1')},
    {'profile_id': 'other-profile'}, {'store_id': 'other-store'},
    {'process_generation': 'other-generation'}, {'configuration_version': 'b' * 64},
    {'grant_epoch': 8},
])
def test_family_pins_cannot_be_replaced_even_if_caller_catches_conflict(journal, changes):
    family = synthetic_family()
    with journal.db.transaction() as conn:
        journal.put_family_in(conn, family)
        with pytest.raises(ApiError) as failure:
            journal.put_family_in(conn, replace(family, **changes))
        assert failure.value.code == 'child_journal_conflict'
    with journal.db.transaction() as conn:
        assert journal.family_in(conn, family.root_id) == family


def test_reserved_child_roundtrips_in_supplied_transaction_and_after_reopen(journal):
    family = synthetic_family()
    child = synthetic_child(family)
    with journal.db.transaction() as conn:
        journal.put_family_in(conn, family)
        journal.put_child_in(conn, child)
        assert journal.child_in(conn, child.reservation_id) == child
        assert journal.children_in(conn, family.root_id) == (child,)
        assert journal.child_in(conn, 'missing-child') is None
    reopened = HarnessChildrenJournal(Database(journal.db.path))
    with reopened.db.transaction() as conn:
        assert reopened.children_in(conn, family.root_id) == (child,)


@pytest.mark.parametrize('case', ['missing', 'parent', 'epoch', 'sealed', 'preadmitted', 'presourced'])
def test_new_child_requires_exact_open_family_and_unbound_reservation(journal, case):
    family = synthetic_family()
    child = synthetic_child(family)
    with journal.db.transaction() as conn:
        if case != 'missing':
            journal.put_family_in(conn, family)
        if case == 'parent':
            child = replace(child, parent_binding=replace(family.root_binding, input_id='wrong-user'))
        elif case == 'epoch':
            child = replace(child, family_epoch=1)
        elif case == 'sealed':
            journal.put_family_in(conn, replace(family, state='sealed', family_epoch=1))
        elif case == 'preadmitted':
            child = replace(child, state='admitted', binding=DomainBinding(
                child.reservation_id, '1', 'child-session', 'child-input', child.reservation_id))
        elif case == 'presourced':
            child = replace(child, sources_json='[{}]')
        with pytest.raises(ApiError) as failure:
            journal.put_child_in(conn, child)
        assert failure.value.code == 'child_journal_conflict'
        assert journal.children_in(conn, family.root_id) == ()


@pytest.mark.parametrize('field', ['root', 'invocation', 'work_digest', 'work_bytes',
    'background', 'family_epoch'])
def test_reserved_child_pins_are_immutable(journal, field):
    family = synthetic_family()
    child = synthetic_child(family)
    changes = {'work_digest': {'work_digest': 'e' * 64}, 'work_bytes': {'work_bytes': 46},
        'background': {'background': True}, 'family_epoch': {'family_epoch': 1}}
    with journal.db.transaction() as conn:
        journal.put_family_in(conn, family)
        journal.put_child_in(conn, child)
        if field == 'root':
            other = synthetic_family('root-2')
            journal.put_family_in(conn, other)
            changed = replace(child, root_id=other.root_id, parent_binding=other.root_binding)
        elif field == 'invocation':
            changed = synthetic_child(family, child.reservation_id, 'tool-2')
        else:
            changed = replace(child, **changes[field])
        with pytest.raises(ApiError) as failure:
            journal.put_child_in(conn, changed)
        assert failure.value.code == 'child_journal_conflict'
        assert journal.child_in(conn, child.reservation_id) == child


def test_child_progress_and_seal_follow_owner_order_without_revival(journal):
    family = synthetic_family()
    child = synthetic_child(family)
    sibling = synthetic_child(family, 'child-2', 'tool-2')
    admitted = replace(child, state='admitted', binding=DomainBinding(
        child.reservation_id, '1', 'child-session', 'child-user', child.reservation_id))
    observed = replace(admitted, job_id='job-1', started_at=100, notification_id='notification-1')
    reported = replace(observed, state='reported', report_id='report-1', report_digest='f' * 64)
    consumed = replace(reported, state='consumed')
    with journal.db.transaction() as conn:
        journal.put_family_in(conn, family)
        journal.put_child_in(conn, child)
        journal.put_child_in(conn, sibling)
        with pytest.raises(ApiError) as failure:
            journal.put_child_in(conn, reported)
        assert failure.value.code == 'child_journal_conflict'
        for row in (admitted, observed, reported, consumed, consumed):
            journal.put_child_in(conn, row)
        for invalid in (child, admitted, reported, replace(consumed, state='settled')):
            with pytest.raises(ApiError):
                journal.put_child_in(conn, invalid)
        sealed_family = replace(family, state='sealed', family_epoch=1)
        journal.put_family_in(conn, sealed_family)
        for row in (consumed, sibling):
            sealed = replace(row, state='sealed')
            journal.put_child_in(conn, sealed)
            journal.put_child_in(conn, sealed)
            journal.put_child_in(conn, replace(sealed, state='settled'))
            with pytest.raises(ApiError):
                journal.put_child_in(conn, row)
        journal.put_family_in(conn, replace(sealed_family, state='settled'))
    reopened = HarnessChildrenJournal(Database(journal.db.path))
    with reopened.db.transaction() as conn:
        rows = reopened.children_in(conn, family.root_id)
        assert [row.state for row in rows] == ['settled', 'settled']
        assert [row.family_epoch for row in rows] == [0, 0]
        assert rows[0].report_id == 'report-1' and rows[1].binding is None


@pytest.mark.parametrize('case', ['rebind', 'clear', 'operation', 'attempt', 'cancellation',
    'parent_session', 'parent_input'])
def test_actual_child_binding_is_exact_and_bind_once(journal, case):
    family = synthetic_family()
    child = synthetic_child(family)
    binding = DomainBinding('child-1', '1', 'child-session', 'child-input', 'child-1')
    admitted = replace(child, state='admitted', binding=binding)
    with journal.db.transaction() as conn:
        journal.put_family_in(conn, family)
        journal.put_child_in(conn, child)
        if case in {'rebind', 'clear'}:
            journal.put_child_in(conn, admitted)
            journal.put_child_in(conn, admitted)
            changed = replace(admitted, binding=(replace(binding, input_id='other-input')
                if case == 'rebind' else None))
            expected = admitted
        else:
            updates = {'operation': {'operation_id': 'foreign-operation'},
                'attempt': {'attempt_id': '2'}, 'cancellation': {'cancellation_id': 'foreign-token'},
                'parent_session': {'session_id': family.root_binding.session_id},
                'parent_input': {'input_id': family.root_binding.input_id}}
            changed = replace(admitted, binding=replace(binding, **updates[case]))
            expected = child
        with pytest.raises(ApiError) as failure:
            journal.put_child_in(conn, changed)
        assert failure.value.code == 'child_journal_conflict'
        assert journal.child_in(conn, child.reservation_id) == expected


@pytest.mark.parametrize('case', ['partial_job', 'time_only', 'job_before_admission',
    'job_rebind', 'job_clear', 'early_report', 'partial_report', 'report_rebind', 'report_clear'])
def test_job_and_report_receipts_bind_as_complete_immutable_tuples(journal, case):
    family = synthetic_family()
    child = synthetic_child(family)
    admitted = replace(child, state='admitted', binding=DomainBinding(
        'child-1', '1', 'child-session', 'child-user', 'child-1'))
    observed = replace(admitted, job_id='job-1', started_at=100, notification_id='notification-1')
    reported = replace(observed, state='reported', report_id='report-1', report_digest='f' * 64)
    with journal.db.transaction() as conn:
        journal.put_family_in(conn, family)
        journal.put_child_in(conn, child)
        expected = child
        if case != 'job_before_admission':
            journal.put_child_in(conn, admitted)
            expected = admitted
        if case in {'job_rebind', 'job_clear', 'report_rebind', 'report_clear'}:
            journal.put_child_in(conn, observed)
            journal.put_child_in(conn, observed)
            expected = observed
        if case in {'report_rebind', 'report_clear'}:
            journal.put_child_in(conn, reported)
            journal.put_child_in(conn, reported)
            expected = reported
        invalid = {'partial_job': replace(admitted, job_id='job-1'),
            'time_only': replace(admitted, started_at=100),
            'job_before_admission': replace(child, job_id='job-1', started_at=100,
                notification_id='notification-1'),
            'job_rebind': replace(observed, started_at=101),
            'job_clear': admitted, 'early_report': replace(observed, report_id='report-1',
                report_digest='f' * 64),
            'partial_report': replace(observed, state='reported', report_id='report-1'),
            'report_rebind': replace(reported, report_digest='e' * 64),
            'report_clear': replace(reported, report_id=None, report_digest=None)}[case]
        with pytest.raises(ApiError) as failure:
            journal.put_child_in(conn, invalid)
        assert failure.value.code == 'child_journal_conflict'
        assert journal.child_in(conn, child.reservation_id) == expected


@pytest.mark.parametrize('notification_id', [None, 'notification-1'])
def test_foreground_observed_job_tuple_cannot_be_rebound_or_cleared(journal, notification_id):
    family = synthetic_family()
    child = synthetic_child(family)
    admitted = replace(child, state='admitted', binding=DomainBinding(
        'child-1', '1', 'child-session', 'child-user', 'child-1'))
    observed = replace(admitted, job_id='job-1', started_at=100, notification_id=notification_id)
    with journal.db.transaction() as conn:
        journal.put_family_in(conn, family)
        for row in (child, admitted, observed):
            journal.put_child_in(conn, row)
        for changed in (replace(observed, job_id='job-2'), replace(observed, started_at=101),
                replace(observed, notification_id='notification-2'), admitted):
            with pytest.raises(ApiError) as failure:
                journal.put_child_in(conn, changed)
            assert failure.value.code == 'child_journal_conflict'
            assert journal.child_in(conn, child.reservation_id) == observed


def test_background_job_and_report_require_a_present_notification(journal):
    family = synthetic_family()
    child = replace(synthetic_child(family), background=True)
    admitted = replace(child, state='admitted', binding=DomainBinding(
        'child-1', '1', 'child-session', 'child-user', 'child-1'))
    without_notification = replace(admitted, job_id='job-1', started_at=100)
    with journal.db.transaction() as conn:
        journal.put_family_in(conn, family)
        journal.put_child_in(conn, child)
        journal.put_child_in(conn, admitted)
        for invalid in (without_notification, replace(without_notification, state='reported',
                report_id='report-1', report_digest='f' * 64)):
            with pytest.raises(ApiError) as failure:
                journal.put_child_in(conn, invalid)
            assert failure.value.code == 'child_journal_conflict'
            assert journal.child_in(conn, child.reservation_id) == admitted


@pytest.mark.parametrize('collision', ['invocation', 'session', 'input', 'job', 'notification', 'report'])
def test_global_native_uniqueness_conflict_leaves_the_callers_transaction_usable(journal, collision):
    family = synthetic_family()
    other = synthetic_family('root-2')
    first = synthetic_child(family)
    second = synthetic_child(other, 'child-2')
    bound = replace(first, state='admitted', binding=DomainBinding(
        'child-1', '1', 'session-1', 'input-1', 'child-1'))
    job = replace(bound, job_id='job-1', started_at=100, notification_id='notification-1')
    report = replace(job, state='reported', report_id='report-1', report_digest='f' * 64)
    with journal.db.transaction() as conn:
        journal.put_family_in(conn, family)
        journal.put_family_in(conn, other)
        for row in (first, bound, job, report):
            journal.put_child_in(conn, row)
        expected = None
        if collision == 'invocation':
            invalid = replace(first, reservation_id='child-2')
        else:
            journal.put_child_in(conn, second)
            expected = second
            second_bound = replace(second, state='admitted', binding=DomainBinding('child-2', '1',
                'session-1' if collision == 'session' else 'session-2',
                'input-1' if collision == 'input' else 'input-2', 'child-2'))
            invalid = second_bound
            if collision in {'job', 'notification', 'report'}:
                journal.put_child_in(conn, second_bound)
                expected = second_bound
                second_job = replace(second_bound, started_at=101,
                    job_id='job-1' if collision == 'job' else 'job-2',
                    notification_id='notification-1' if collision == 'notification' else 'notification-2')
                invalid = second_job
                if collision == 'report':
                    journal.put_child_in(conn, second_job)
                    expected = second_job
                    invalid = replace(second_job, state='reported', report_id='report-1',
                        report_digest='e' * 64)
        with pytest.raises(ApiError) as failure:
            journal.put_child_in(conn, invalid)
        assert failure.value.code == 'child_journal_conflict'
        assert journal.child_in(conn, 'child-2') == expected
        journal.put_family_in(conn, synthetic_family('unrelated-root'))
    with journal.db.transaction() as conn:
        assert journal.child_in(conn, first.reservation_id) == report
        assert journal.child_in(conn, 'child-2') == expected
        assert journal.family_in(conn, 'unrelated-root') is not None


def test_actual_source_references_only_grow_before_report_and_freeze_through_consumption(journal):
    family = synthetic_family()
    child = synthetic_child(family)
    admitted = replace(child, state='admitted', binding=DomainBinding(
        'child-1', '1', 'child-session', 'child-user', 'child-1'))
    first = synthetic_source()
    second = synthetic_source('passage-2')
    sourced = replace(admitted, sources_json=sources_json(first))
    expanded = replace(sourced, sources_json=sources_json(first, second))
    observed = replace(expanded, job_id='job-1', started_at=100, notification_id='notification-1')
    reported = replace(observed, state='reported', report_id='report-1', report_digest='f' * 64)
    with journal.db.transaction() as conn:
        journal.put_family_in(conn, family)
        for row in (child, admitted, sourced, expanded):
            journal.put_child_in(conn, row)
        for invalid in (sourced, replace(expanded, sources_json=sources_json(second, first)),
                replace(expanded, sources_json=sources_json(
                    {**first, 'dependency': {**first['dependency'], 'expected_revision': 'c' * 64}}, second))):
            with pytest.raises(ApiError) as failure:
                journal.put_child_in(conn, invalid)
            assert failure.value.code == 'child_journal_conflict'
        journal.put_child_in(conn, observed)
        journal.put_child_in(conn, reported)
        with pytest.raises(ApiError):
            journal.put_child_in(conn, replace(reported,
                sources_json=sources_json(first, second, synthetic_source('passage-3'))))
        consumed = replace(reported, state='consumed')
        journal.put_child_in(conn, consumed)
    with HarnessChildrenJournal(Database(journal.db.path)).db.transaction() as conn:
        assert journal.child_in(conn, child.reservation_id) == consumed


@pytest.mark.parametrize('case', ['work', 'output', 'body', 'path', 'content_body', 'foreign_target',
    'foreign_revision', 'document_revision_as_pin', 'boolean_page', 'duplicate_passage',
    'duplicate_json_key', 'nonfinite', 'object_not_list'])
def test_reference_only_sources_reject_bytes_and_noncanonical_receipts(journal, case):
    source = synthetic_source()
    if case in {'work', 'output'}:
        source[case] = 'forbidden synthetic transcript'
    elif case in {'body', 'path'}:
        source['citation']['locators'][0][case] = 'forbidden synthetic body or path'
    elif case == 'content_body':
        source['citation']['content_ref']['body'] = 'forbidden synthetic source text'
    elif case == 'foreign_target':
        source['dependency']['target']['type'] = 'memory_revision'
    elif case == 'foreign_revision':
        source['citation']['content_ref']['target']['id'] = 'foreign-revision'
    elif case == 'document_revision_as_pin':
        source['dependency']['expected_revision'] = 'revision-1'
    elif case == 'boolean_page':
        source['citation']['locators'][0]['page'] = True
    encoded = sources_json(source, source) if case == 'duplicate_passage' else sources_json(source)
    if case == 'duplicate_json_key':
        encoded = encoded.replace('"document_id":"document-1"',
            '"document_id":"document-1","document_id":"document-2"')
    elif case == 'nonfinite':
        encoded = encoded.replace('"page":2', '"page":NaN')
    elif case == 'object_not_list':
        encoded = '{}'
    family = synthetic_family()
    child = synthetic_child(family)
    admitted = replace(child, state='admitted', binding=DomainBinding(
        'child-1', '1', 'child-session', 'child-user', 'child-1'))
    with journal.db.transaction() as conn:
        journal.put_family_in(conn, family)
        journal.put_child_in(conn, child)
        journal.put_child_in(conn, admitted)
        with pytest.raises(ApiError) as failure:
            journal.put_child_in(conn, replace(admitted, sources_json=encoded))
        assert failure.value.code == 'child_journal_invalid'
        assert journal.child_in(conn, child.reservation_id) == admitted


@pytest.mark.parametrize('case', ['family_epoch_bool', 'grant_float', 'profile_path', 'binding_type',
    'family_subclass', 'child_subclass', 'background_int', 'work_bytes_bool', 'digest',
    'invocation_mismatch', 'child_binding_type', 'started_bool'])
def test_only_frozen_exact_metadata_types_can_be_persisted(journal, case):
    family = synthetic_family()
    child = synthetic_child(family)

    @dataclass(frozen=True)
    class SyntheticBodyFamily(ChildFamily):
        output: str = 'forbidden synthetic report body'

    @dataclass(frozen=True)
    class SyntheticBodyChild(ChildRecord):
        work: str = 'forbidden synthetic work body'

    with journal.db.transaction() as conn:
        if case.startswith('family') or case in {'grant_float', 'profile_path', 'binding_type'}:
            invalid = {'family_epoch_bool': replace(family, family_epoch=False),
                'grant_float': replace(family, grant_epoch=7.0),
                'profile_path': replace(family, profile_id='synthetic/private/path'),
                'binding_type': replace(family, root_binding=None),
                'family_subclass': SyntheticBodyFamily(**{
                    field.name: getattr(family, field.name) for field in fields(ChildFamily)})}[case]
            with pytest.raises(ApiError) as failure:
                journal.put_family_in(conn, invalid)
            assert failure.value.code == 'child_journal_invalid'
            assert journal.families_in(conn) == ()
        else:
            journal.put_family_in(conn, family)
            if case in {'child_binding_type', 'started_bool'}:
                journal.put_child_in(conn, child)
                admitted = replace(child, state='admitted', binding=DomainBinding(
                    'child-1', '1', 'child-session', 'child-user', 'child-1'))
                journal.put_child_in(conn, admitted)
                invalid = (replace(admitted, binding={}) if case == 'child_binding_type' else
                    replace(admitted, job_id='job-1', started_at=True, notification_id='notification-1'))
                expected = admitted
            else:
                invalid = {'child_subclass': SyntheticBodyChild(**{
                        field.name: getattr(child, field.name) for field in fields(ChildRecord)}),
                    'background_int': replace(child, background=1),
                    'work_bytes_bool': replace(child, work_bytes=True),
                    'digest': replace(child, work_digest='arbitrary-work-text'),
                    'invocation_mismatch': replace(child, invocation_key='e' * 64)}[case]
                expected = None
            with pytest.raises(ApiError) as failure:
                journal.put_child_in(conn, invalid)
            assert failure.value.code == 'child_journal_invalid'
            assert journal.child_in(conn, child.reservation_id) == expected


def test_family_cannot_settle_before_all_retained_child_rows(journal):
    family = synthetic_family()
    child = synthetic_child(family)
    sealed = replace(family, state='sealed', family_epoch=1)
    with journal.db.transaction() as conn:
        journal.put_family_in(conn, family)
        journal.put_child_in(conn, child)
        journal.put_family_in(conn, sealed)
        with pytest.raises(ApiError) as failure:
            journal.put_family_in(conn, replace(sealed, state='settled'))
        assert failure.value.code == 'child_journal_conflict'
        journal.put_child_in(conn, replace(child, state='sealed'))
        with pytest.raises(ApiError):
            journal.put_family_in(conn, replace(sealed, state='settled'))
        journal.put_child_in(conn, replace(child, state='settled'))
        journal.put_family_in(conn, replace(sealed, state='settled'))


@pytest.mark.parametrize('existing', [False, True])
def test_caller_rollback_owns_all_family_and_child_changes(journal, existing):
    family = synthetic_family()
    child = synthetic_child(family)
    if existing:
        with journal.db.transaction() as conn:
            journal.put_family_in(conn, family)
            journal.put_child_in(conn, child)
    with pytest.raises(RuntimeError, match='synthetic caller rollback'):
        with journal.db.transaction() as conn:
            if not existing:
                journal.put_family_in(conn, family)
                journal.put_child_in(conn, child)
            sealed = replace(family, state='sealed', family_epoch=1)
            journal.put_family_in(conn, sealed)
            journal.put_child_in(conn, replace(child, state='sealed'))
            journal.put_child_in(conn, replace(child, state='settled'))
            journal.put_family_in(conn, replace(sealed, state='settled'))
            raise RuntimeError('synthetic caller rollback')
    reopened = HarnessChildrenJournal(Database(journal.db.path))
    with reopened.db.transaction() as conn:
        assert reopened.family_in(conn, family.root_id) == (family if existing else None)
        assert reopened.child_in(conn, child.reservation_id) == (child if existing else None)
