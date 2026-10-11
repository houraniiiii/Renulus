# SPDX-License-Identifier: MIT
"""Canonical reference-only child metadata in the caller's transaction.

This journal never grants authority or restores live child ownership on reopen.
The execution owner supplies frozen records and owns all commit/rollback work.
Source and retained-byte budgets remain the execution owner's explicit ChildBounds;
validating reference shapes here never establishes Library eligibility.
"""
from dataclasses import asdict, replace
from pathlib import Path
import json
import re
import sqlite3

from pydantic import ValidationError

from renulus.contracts import ApiError
from renulus.design_c_contracts import ContentReference, Dependency, canonical_digest
from renulus.knowledge.provenance import valid_source_provenance
from renulus.storage import Database

from .harness_children import ChildFamily, ChildRecord
from .harness_domain import DomainBinding


def _deny(code, status=409):
    raise ApiError(code, 'The canonical child journal operation is unavailable.', status)


def _write(conn, sql, parameters):
    # Each public mutation is one SQLite ABORT statement: a caught uniqueness
    # conflict cannot leave partial journal writes in the caller's transaction.
    try:
        conn.execute(sql, parameters)
    except sqlite3.IntegrityError:
        _deny('child_journal_conflict')


def _identifier(value):
    if type(value) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,255}', value) is None:
        _deny('child_journal_invalid', 422)


def _digest(value):
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}', value) is None:
        _deny('child_journal_invalid', 422)


def _integer(value, minimum=0):
    if type(value) is not int or not minimum <= value <= 9007199254740991:
        _deny('child_journal_invalid', 422)


def _binding(value):
    if type(value) is not DomainBinding:
        _deny('child_journal_invalid', 422)
    for identifier in asdict(value).values():
        _identifier(identifier)


def _family_metadata(family):
    if type(family) is not ChildFamily:
        _deny('child_journal_invalid', 422)
    for field in ('root_id', 'profile_id', 'store_id', 'process_generation', 'configuration_version'):
        _identifier(getattr(family, field))
    _binding(family.root_binding)
    _integer(family.grant_epoch)
    _integer(family.family_epoch)
    if (family.root_id != family.root_binding.operation_id or type(family.state) is not str
            or family.state not in {'open', 'sealed', 'settled'}):
        _deny('child_journal_invalid', 422)


def _child_metadata(child):
    if type(child) is not ChildRecord:
        _deny('child_journal_invalid', 422)
    for field in ('reservation_id', 'root_id', 'message_id', 'tool_call_id'):
        _identifier(getattr(child, field))
    _binding(child.parent_binding)
    if child.binding is not None:
        _binding(child.binding)
    _digest(child.invocation_key)
    _digest(child.work_digest)
    _integer(child.work_bytes, 1)
    _integer(child.family_epoch)
    for value in (child.job_id, child.notification_id, child.report_id):
        if value is not None:
            _identifier(value)
    if child.started_at is not None:
        _integer(child.started_at)
    if child.report_digest is not None:
        _digest(child.report_digest)
    if (type(child.background) is not bool or type(child.state) is not str
            or child.state not in {'reserved', 'admitted', 'reported', 'consumed', 'sealed', 'settled'}
            or child.root_id != child.parent_binding.operation_id
            or child.invocation_key != canonical_digest({
                'message_id': child.message_id, 'tool_call_id': child.tool_call_id})):
        _deny('child_journal_invalid', 422)


def _read(text, record_type, validate):
    try:
        record = record_type.from_json(text)
        canonical = record.to_json()
    except (ValueError, TypeError, KeyError, RecursionError):
        _deny('child_journal_invalid', 422)
    if canonical != text:
        _deny('child_journal_invalid', 422)
    validate(record)
    if record_type is ChildRecord:
        _sources(record.sources_json)
    return record


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate metadata key')
        value[key] = item
    return value


def _nonfinite(value):
    raise ValueError('Nonfinite metadata')


def _sources(text):
    if type(text) is not str:
        _deny('child_journal_invalid', 422)
    try:
        sources = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_nonfinite)
    except (ValueError, RecursionError):
        _deny('child_journal_invalid', 422)
    if type(sources) is not list:
        _deny('child_journal_invalid', 422)
    passages = set()
    for source in sources:
        if type(source) is not dict or set(source) != {'dependency', 'citation'}:
            _deny('child_journal_invalid', 422)
        citation = source['citation']
        if type(citation) is not dict or set(citation) != {
                'content_ref', 'document_id', 'revision_id', 'passage_id', 'locators'}:
            _deny('child_journal_invalid', 422)
        for key in ('document_id', 'revision_id', 'passage_id'):
            _identifier(citation[key])
        if not valid_source_provenance(citation['locators']) or citation['passage_id'] in passages:
            _deny('child_journal_invalid', 422)
        passages.add(citation['passage_id'])
        try:
            dependency = Dependency.model_validate(source['dependency'], strict=True)
            reference = ContentReference.model_validate_json(json.dumps(citation['content_ref'],
                allow_nan=False), strict=True)
        except (ValidationError, ValueError, TypeError):
            _deny('child_journal_invalid', 422)
        _digest(dependency.expected_revision)
        if (dependency.target.type != 'library_revision'
                or dependency.target.id != citation['revision_id']
                or reference.target.key != dependency.target.key):
            _deny('child_journal_invalid', 422)
    return sources


class HarnessChildrenJournal:
    """The frozen ChildJournal ports, with no authorization or native lifetime state.

    Every port requires this Database's active supplied connection. A mutation is
    one atomic statement; the caller owns any larger transaction. Family sealing
    advances its epoch once while each child retains its captured preparation epoch.
    Consumed reports still hold permits and are sealed before actual settlement.
    """
    def __init__(self, db: Database):
        self.db = db
        script = Path(__file__).with_name('migrations').joinpath('005-harness-children.sql').read_text(
            encoding='utf-8')
        db.apply_migration('runtime-005-harness-children', script)

    def _connection(self, conn):
        if not isinstance(conn, sqlite3.Connection):
            _deny('child_transaction_required')
        try:
            active = conn.in_transaction
        except sqlite3.ProgrammingError:
            active = False
        if not active:
            _deny('child_transaction_required')
        path = next((row[2] for row in conn.execute('PRAGMA database_list')
            if row[1] == 'main'), None)
        if not path or Path(path).resolve() != self.db.path:
            _deny('child_connection_mismatch')

    def families_in(self, conn: sqlite3.Connection) -> tuple[ChildFamily, ...]:
        self._connection(conn)
        return tuple(_read(row[0], ChildFamily, _family_metadata) for row in conn.execute(
            'SELECT metadata_json FROM harness_child_families ORDER BY root_id'))

    def family_in(self, conn: sqlite3.Connection, root_id: str) -> ChildFamily | None:
        self._connection(conn)
        _identifier(root_id)
        row = conn.execute('SELECT metadata_json FROM harness_child_families WHERE root_id=?',
            (root_id,)).fetchone()
        return _read(row[0], ChildFamily, _family_metadata) if row else None

    def put_family_in(self, conn: sqlite3.Connection, family: ChildFamily) -> None:
        self._connection(conn)
        _family_metadata(family)
        prior = self.family_in(conn, family.root_id)
        if prior is not None and replace(prior, state=family.state,
                family_epoch=family.family_epoch) != family:
            _deny('child_journal_conflict')
        if prior is None:
            if family.state != 'open' or family.family_epoch != 0:
                _deny('child_journal_conflict')
        elif prior != family:
            expected = ({'open': ('sealed', prior.family_epoch + 1),
                'sealed': ('settled', prior.family_epoch)}).get(prior.state)
            if (family.state, family.family_epoch) != expected:
                _deny('child_journal_conflict')
        if family.state == 'settled' and any(child.state != 'settled'
                for child in self.children_in(conn, family.root_id)):
            _deny('child_journal_conflict')
        _write(conn, 'INSERT INTO harness_child_families VALUES(?,?,?,?,?,?,?,?,?) '
            'ON CONFLICT(root_id) DO UPDATE SET family_epoch=excluded.family_epoch, '
            'state=excluded.state, metadata_json=excluded.metadata_json',
            (family.root_id, family.profile_id, family.store_id, family.process_generation,
                family.configuration_version, family.grant_epoch, family.family_epoch,
                family.state, family.to_json()))

    def children_in(self, conn: sqlite3.Connection, root_id: str) -> tuple[ChildRecord, ...]:
        self._connection(conn)
        _identifier(root_id)
        return tuple(_read(row[0], ChildRecord, _child_metadata) for row in conn.execute(
            'SELECT metadata_json FROM harness_child_records WHERE root_id=? ORDER BY reservation_id',
            (root_id,)))

    def child_in(self, conn: sqlite3.Connection, reservation_id: str) -> ChildRecord | None:
        self._connection(conn)
        _identifier(reservation_id)
        row = conn.execute('SELECT metadata_json FROM harness_child_records WHERE reservation_id=?',
            (reservation_id,)).fetchone()
        return _read(row[0], ChildRecord, _child_metadata) if row else None

    def put_child_in(self, conn: sqlite3.Connection, child: ChildRecord) -> None:
        self._connection(conn)
        _child_metadata(child)
        prior = self.child_in(conn, child.reservation_id)
        family = self.family_in(conn, child.root_id)
        if family is None or family.root_binding != child.parent_binding:
            _deny('child_journal_conflict')
        if prior is None and (family.state != 'open' or child.family_epoch != family.family_epoch
                or child.state != 'reserved' or child.binding is not None
                or child.job_id is not None or child.started_at is not None
                or child.notification_id is not None or child.report_id is not None
                or child.report_digest is not None or child.sources_json != '[]'):
            _deny('child_journal_conflict')
        if prior is not None and replace(prior, state=child.state, binding=child.binding,
                job_id=child.job_id, started_at=child.started_at, notification_id=child.notification_id,
                report_id=child.report_id, report_digest=child.report_digest,
                sources_json=child.sources_json) != child:
            _deny('child_journal_conflict')
        sources = _sources(child.sources_json)
        if prior is not None:
            transitions = {'reserved': {'reserved', 'admitted', 'sealed'},
                'admitted': {'admitted', 'reported', 'sealed'},
                'reported': {'reported', 'consumed', 'sealed'},
                'consumed': {'consumed', 'sealed'}, 'sealed': {'sealed', 'settled'},
                'settled': {'settled'}}
            if child.state not in transitions[prior.state]:
                _deny('child_journal_conflict')
            if child.state in {'sealed', 'settled'}:
                if family.state == 'open' or replace(prior, state=child.state) != child:
                    _deny('child_journal_conflict')
            elif family.state != 'open' or child.family_epoch != family.family_epoch:
                _deny('child_journal_conflict')
        if child.state == 'reserved' and child.binding is not None:
            _deny('child_journal_conflict')
        if child.state in {'admitted', 'reported', 'consumed'} and child.binding is None:
            _deny('child_journal_conflict')
        if child.state in {'reported', 'consumed'} and (child.job_id is None
                or child.started_at is None or child.notification_id is None
                or child.report_id is None or child.report_digest is None):
            _deny('child_journal_conflict')
        binding = child.binding
        if binding is not None and (binding.operation_id != child.reservation_id
                or binding.attempt_id != '1' or binding.cancellation_id != child.reservation_id
                or binding.session_id == family.root_binding.session_id
                or binding.input_id == family.root_binding.input_id):
            _deny('child_journal_conflict')
        if prior is not None and prior.binding is not None and prior.binding != binding:
            _deny('child_journal_conflict')
        job = (child.job_id, child.started_at, child.notification_id)
        report = (child.report_id, child.report_digest)
        if any(value is not None for value in job) and (binding is None
                or any(value is None for value in job)):
            _deny('child_journal_conflict')
        if any(value is not None for value in report) and (child.job_id is None
                or any(value is None for value in report)
                or child.state not in {'reported', 'consumed', 'sealed', 'settled'}):
            _deny('child_journal_conflict')
        if prior is not None:
            prior_job = (prior.job_id, prior.started_at, prior.notification_id)
            prior_report = (prior.report_id, prior.report_digest)
            if prior_job != job and (prior.job_id is not None
                    or prior.state != 'admitted' or child.state != 'admitted'):
                _deny('child_journal_conflict')
            if prior_report != report and (prior.report_id is not None
                    or prior.state != 'admitted' or child.state != 'reported'):
                _deny('child_journal_conflict')
            if prior.sources_json != child.sources_json:
                before, after = _sources(prior.sources_json), sources
                if (prior.state != 'admitted' or child.state != 'admitted'
                        or len(after) < len(before) or after[:len(before)] != before):
                    _deny('child_journal_conflict')
        _write(conn, 'INSERT INTO harness_child_records VALUES(?,?,?,?,?,?,?,?,?,?,?) '
            'ON CONFLICT(reservation_id) DO UPDATE SET state=excluded.state, '
            'operation_id=excluded.operation_id, session_id=excluded.session_id, '
            'input_id=excluded.input_id, job_id=excluded.job_id, '
            'notification_id=excluded.notification_id, report_id=excluded.report_id, '
            'metadata_json=excluded.metadata_json',
            (child.reservation_id, child.root_id, child.invocation_key, child.state,
                binding.operation_id if binding else None, binding.session_id if binding else None,
                binding.input_id if binding else None, child.job_id, child.notification_id,
                child.report_id, child.to_json()))
