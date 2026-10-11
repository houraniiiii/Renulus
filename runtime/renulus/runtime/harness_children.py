# SPDX-License-Identifier: MIT
"""Bounded child authority for the existing native execution owner.

The parent supplies its frozen authority, canonical journal and actual native
stop/finalizer ports. This module has no schema, transcript, model scheduler or
Memory producer. Journal callbacks run locally in the supplied connection.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field, replace
import hashlib
import inspect
import json
import math
from pathlib import Path
import re
import sqlite3
from typing import Protocol
from uuid import uuid4

from renulus.contracts import ApiError
from renulus.design_c_contracts import Dependency, Identity, canonical_digest
from .harness_domain import DomainBinding, DomainCancellation, DomainCancelled, DomainGrant, DomainRequest
from .harness_library import LibraryAuthority
from .harness_model_registry import ModelRunAuthority


_STAGES = frozenset({'after_permission', 'before_create', 'before_prompt',
    'before_result', 'before_detached', 'before_wake'})
_SHAPES = {
    'child.prepare': {'invocation', 'work'},
    'child.admit_input': {'reservation_id'},
    'child.check': {'reservation_id', 'stage'},
    'child.observe_job': {'reservation_id', 'job_id', 'started_at', 'notification_id'},
    'child.report': {'reservation_id', 'notification_id', 'report_digest', 'output'},
    'child.consume_report': {'report_id'},
    'library.retrieve': {'command', 'arguments', 'envelope'},
    'library.citation': {'command', 'arguments', 'envelope'},
}


def _deny(code, status=409):
    raise ApiError(code, 'The bounded child operation is unavailable.', status)


def _json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':'))


def _local(callback, *args, **kwargs):
    value = callback(*args, **kwargs)
    if inspect.isawaitable(value):
        if inspect.iscoroutine(value):
            value.close()
        _deny('child_local_callback_required', 422)
    return value


def _identifier(value):
    if type(value) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,255}', value) is None:
        _deny('child_identity_invalid', 422)
    return value


def _binding(value):
    if type(value) is not DomainBinding:
        _deny('child_identity_invalid', 422)
    for item in asdict(value).values():
        _identifier(item)
    return value


class ParentCurrent(Protocol):
    def __call__(self, *, conn: sqlite3.Connection | None = None) -> None: ...


@dataclass(frozen=True)
class ParentChildAuthority:
    binding: DomainBinding
    profile_id: str
    store_id: str
    process_generation: str
    root_id: str
    configuration_version: str
    grant_epoch: int
    cancellation: DomainCancellation = field(repr=False, compare=False)
    current: ParentCurrent = field(repr=False, compare=False)
    library: LibraryAuthority = field(repr=False, compare=False)


@dataclass(frozen=True)
class ChildBounds:
    max_depth: int
    concurrency: int
    max_families: int
    max_records: int
    max_owned: int
    max_work_bytes: int
    max_report_bytes: int
    max_sources: int
    max_source_bytes: int
    max_retained_bytes: int
    max_settlement_seconds: int

    def __post_init__(self):
        if (any(type(value) is not int or value <= 0 for value in asdict(self).values())
                or self.max_depth != 1 or self.concurrency > 2):
            _deny('child_bounds_invalid', 422)


@dataclass(frozen=True)
class ChildReservation:
    reservation_id: str
    operation_id: str
    attempt_id: str
    cancellation_id: str
    grant_epoch: int


@dataclass(frozen=True)
class ChildAdmission:
    admitted: bool = True


@dataclass(frozen=True)
class ChildReport:
    report_id: str


@dataclass(frozen=True)
class ChildFamily:
    root_id: str
    root_binding: DomainBinding
    profile_id: str
    store_id: str
    process_generation: str
    configuration_version: str
    grant_epoch: int
    family_epoch: int = 0
    state: str = 'open'

    def to_json(self):
        return _json(asdict(self))

    @classmethod
    def from_json(cls, text):
        value = json.loads(text)
        value['root_binding'] = DomainBinding(**value['root_binding'])
        return cls(**value)


@dataclass(frozen=True)
class ChildRecord:
    reservation_id: str
    root_id: str
    parent_binding: DomainBinding
    invocation_key: str
    message_id: str
    tool_call_id: str
    work_digest: str
    work_bytes: int
    background: bool
    family_epoch: int
    state: str = 'reserved'
    binding: DomainBinding | None = None
    job_id: str | None = None
    started_at: int | None = None
    notification_id: str | None = None
    report_id: str | None = None
    report_digest: str | None = None
    sources_json: str = '[]'

    def to_json(self):
        return _json(asdict(self))

    @classmethod
    def from_json(cls, text):
        value = json.loads(text)
        value['parent_binding'] = DomainBinding(**value['parent_binding'])
        if value['binding'] is not None:
            value['binding'] = DomainBinding(**value['binding'])
        return cls(**value)


class ChildJournal(Protocol):
    """Parent-owned persistent metadata, never work/report/transcript bytes.

    family root_id and reservation_id are globally unique. Enforce an additional
    UNIQUE(root_id, invocation_key), and unique native child/input/report IDs.
    Every mutation participates in the caller's transaction and rollback.
    """
    def families_in(self, conn) -> tuple[ChildFamily, ...]: ...
    def family_in(self, conn, root_id: str) -> ChildFamily | None: ...
    def put_family_in(self, conn, family: ChildFamily) -> None: ...
    def children_in(self, conn, root_id: str) -> tuple[ChildRecord, ...]: ...
    def child_in(self, conn, reservation_id: str) -> ChildRecord | None: ...
    def put_child_in(self, conn, child: ChildRecord) -> None: ...


@dataclass(frozen=True)
class FamilySnapshot:
    family: ChildFamily
    children: tuple[ChildRecord, ...]


@dataclass(frozen=True)
class ChildStatus:
    families: tuple[FamilySnapshot, ...]
    reserved: int
    admitted: int
    reported: int
    consumed: int
    owned: int
    cleanup_pending: int
    max_depth: int
    concurrency: int


class HarnessChildren:
    def __init__(self, db, *, resolve_parent, journal: ChildJournal, configuration_authority,
                 library, record_consumed_in, require_publication, stop_family, settle_family,
                 seal_root_in, release_family_in, bounds: ChildBounds):
        if type(bounds) is not ChildBounds:
            _deny('child_bounds_invalid', 422)
        self.db, self.resolve_parent, self.journal = db, resolve_parent, journal
        self.configuration = configuration_authority
        self.library, self.record_consumed_in = library, record_consumed_in
        self.require_publication = require_publication
        self.stop_family, self.settle_family = stop_family, settle_family
        self.seal_root_in = seal_root_in
        self.release_family_in, self.bounds = release_family_in, bounds
        self._tokens = {}
        self._models = {}
        self._owned = {}
        self._drains = {}
        self._live = set()

    def _connection(self, conn):
        if not conn.in_transaction:
            _deny('child_transaction_required')
        path = next((row[2] for row in conn.execute('PRAGMA database_list') if row[1] == 'main'), None)
        if not path or Path(path).resolve() != self.db.path:
            _deny('child_connection_mismatch')

    def _parent(self, binding, conn):
        _binding(binding)
        parent = _local(self.resolve_parent, binding)
        if (type(parent) is not ParentChildAuthority or parent.binding != binding
                or parent.root_id != binding.operation_id):
            _deny('child_parent_unavailable')
        if parent.cancellation.cancelled:
            raise DomainCancelled('domain_cancelled')
        _local(parent.current, conn=conn)
        if self.configuration.revocation_overlay(conn=conn)['epoch'] != parent.grant_epoch:
            _deny('child_grant_epoch_changed')
        return parent

    def _family(self, parent):
        return ChildFamily(parent.root_id, parent.binding, parent.profile_id, parent.store_id,
            parent.process_generation, parent.configuration_version, parent.grant_epoch)

    def prepare(self, parent_binding, native_invocation, work) -> ChildReservation:
        if (type(native_invocation) is not dict or set(native_invocation) != {'message_id', 'tool_call_id'}
                or type(work) is not dict or set(work) != {'description', 'prompt', 'background'}
                or type(work['background']) is not bool
                or any(type(work[key]) is not str or not work[key].strip()
                    for key in ('description', 'prompt'))):
            _deny('child_payload_invalid', 422)
        for value in native_invocation.values():
            _identifier(value)
        encoded = _json(work).encode('utf-8')
        if len(encoded) > self.bounds.max_work_bytes:
            _deny('child_work_limit', 422)
        digest, key = hashlib.sha256(encoded).hexdigest(), canonical_digest(native_invocation)
        with self.db.transaction() as conn:
            parent = self._parent(parent_binding, conn)
            family = self.journal.family_in(conn, parent.root_id)
            expected = self._family(parent)
            if family is None:
                families = self.journal.families_in(conn)
                if len(families) >= self.bounds.max_families:
                    _deny('child_family_capacity')
                family = expected
                self.journal.put_family_in(conn, family)
            if family != expected:
                _deny('child_family_sealed')
            children = self.journal.children_in(conn, family.root_id)
            prior = next((child for child in children if child.invocation_key == key), None)
            if prior is not None:
                if prior.work_digest != digest:
                    _deny('child_invocation_conflict')
                self._check_child(conn, prior)
                return ChildReservation(prior.reservation_id, prior.reservation_id, '1',
                    prior.reservation_id, family.grant_epoch)
            if len(children) >= self.bounds.concurrency:
                _deny('child_concurrency_exhausted')
            if sum(len(self.journal.children_in(conn, item.root_id))
                    for item in self.journal.families_in(conn)) >= self.bounds.max_records:
                _deny('child_record_capacity')
            root = self.configuration.require_current(parent.binding.operation_id, conn=conn)
            if root['version'] != parent.configuration_version:
                _deny('child_configuration_mismatch')
            child_id = 'child_' + uuid4().hex
            child = self.configuration.begin_child_in(conn, child_id, parent.binding.operation_id,
                'evidence-review',
                capability_scope=tuple(root['effective_capabilities']))
            if child['version'] != family.configuration_version or child['root_id'] != family.root_id:
                _deny('child_configuration_mismatch')
            record = ChildRecord(child_id, family.root_id, parent.binding, key,
                native_invocation['message_id'], native_invocation['tool_call_id'], digest,
                len(encoded), work['background'], family.family_epoch)
            self.journal.put_child_in(conn, record)
            self._parent(parent_binding, conn)
        self._live.add(child_id)
        return ChildReservation(child_id, child_id, '1', child_id, family.grant_epoch)

    def _check_child_current(self, conn, record):
        if record is None:
            _deny('child_reservation_unavailable')
        if record.reservation_id not in self._live:
            _deny('child_recovery_required')
        parent = self._parent(record.parent_binding, conn)
        family = self.journal.family_in(conn, record.root_id)
        if (family != self._family(parent) or record.family_epoch != family.family_epoch
                or record.state not in {'reserved', 'admitted', 'reported', 'consumed'}):
            _deny('child_family_sealed')
        pins = self.configuration.require_current(record.reservation_id, conn=conn)
        if pins['version'] != family.configuration_version:
            _deny('child_configuration_mismatch')
        return parent, family

    def _check_child(self, conn, record):
        parent, family = self._check_child_current(conn, record)
        self._check_sources(conn, record, parent)
        return parent, family

    def _library_current(self, conn, record, cancellation):
        if cancellation.cancelled:
            raise DomainCancelled('domain_cancelled')
        started = not conn.in_transaction
        if started:
            # Journal reads need a snapshot, without another canonical writer.
            conn.execute('BEGIN')
        try:
            self._connection(conn)
            row = self.journal.child_in(conn, record.reservation_id)
            if row is None or row.binding != record.binding:
                _deny('child_family_sealed')
            parent, _ = self._check_child_current(conn, row)
            if row.state != 'admitted':
                _deny('child_report_closed')
            if cancellation.cancelled:
                raise DomainCancelled('domain_cancelled')
            return row, parent
        finally:
            if started:
                conn.rollback()

    def _library_authority(self, record, parent, cancellation):
        def guard(conn):
            self._library_current(conn, record, cancellation)
        return replace(parent.library, guard=guard,
            cancelled=lambda: cancellation.cancelled or parent.cancellation.cancelled,
            record_dependencies=lambda references: self._record_sources(record, references, cancellation))

    def _check_sources(self, conn, record, parent):
        sources = json.loads(record.sources_json)
        if not sources:
            return
        if self.library is None:
            _deny('child_library_unavailable')
        for source in sources:
            dependency = Dependency.model_validate(source['dependency'])
            revision = self.library.resolve_dependency(conn, dependency.target, authority=parent.library)
            if revision != dependency.expected_revision:
                _deny('harness_sources_changed')
            citation = source['citation']
            self.library.validate_publication([{'document_id': citation['document_id'],
                'document_revision': citation['revision_id'], 'passage_id': citation['passage_id'],
                'locators': citation['locators']}], parent.library, conn=conn)

    def _record_sources(self, record, references, cancellation):
        cancellation.check_current()
        with self.db.transaction() as conn:
            row, parent = self._library_current(conn, record, cancellation)
            self._check_sources(conn, row, parent)
            trusted = self._library_authority(row, parent, cancellation)
            sources = json.loads(row.sources_json)
            for reference in references:
                identity = Identity(type='library_revision', id=reference['document_revision'])
                revision = self.library.resolve_dependency(conn, identity, authority=trusted)
                if revision is None:
                    _deny('harness_sources_changed')
                citation = self.library.project_content_reference(conn, reference, authority=trusted)
                source = {'dependency': Dependency(target=identity, expected_revision=revision).model_dump(mode='json'),
                    'citation': citation}
                prior = next((item for item in sources if item['citation']['passage_id'] == citation['passage_id']), None)
                if prior is not None and prior != source:
                    _deny('harness_sources_changed')
                if prior is None:
                    sources.append(source)
            encoded = _json(sources)
            if len(sources) > self.bounds.max_sources or len(encoded.encode()) > self.bounds.max_source_bytes:
                _deny('child_source_capacity')
            retained = sum(len(child.sources_json.encode()) for family in self.journal.families_in(conn)
                for child in self.journal.children_in(conn, family.root_id))
            if retained - len(row.sources_json.encode()) + len(encoded.encode()) > self.bounds.max_retained_bytes:
                _deny('child_source_capacity')
            self._library_current(conn, record, cancellation)
            self.journal.put_child_in(conn, replace(row, sources_json=encoded))
            self._check_child(conn, self.journal.child_in(conn, record.reservation_id))
            if cancellation.cancelled:
                raise DomainCancelled('domain_cancelled')

    def admit_input(self, reservation_id, actual_child_binding) -> ChildAdmission:
        _identifier(reservation_id)
        binding = _binding(actual_child_binding)
        if (binding.operation_id != reservation_id or binding.attempt_id != '1'
                or binding.cancellation_id != reservation_id):
            _deny('child_binding_conflict')
        with self.db.transaction() as conn:
            record = self.journal.child_in(conn, reservation_id)
            if record is None:
                _deny('child_reservation_unavailable')
            _, family = self._check_child(conn, record)
            if record.binding is not None:
                if record.binding != binding:
                    _deny('child_binding_conflict')
                return ChildAdmission()
            for item in self.journal.children_in(conn, family.root_id):
                if item.binding is not None and (item.binding.session_id == binding.session_id
                        or item.binding.input_id == binding.input_id):
                    _deny('child_binding_conflict')
            if binding.session_id == record.parent_binding.session_id:
                _deny('child_binding_conflict')
            self.journal.put_child_in(conn, replace(record, binding=binding, state='admitted'))
            self._check_child(conn, record)
        return ChildAdmission()

    def resolve_model_run(self, binding):
        _binding(binding)
        with self.db.transaction() as conn:
            record = self.journal.child_in(conn, binding.operation_id)
            if record is None or record.binding != binding:
                return None
            parent, family = self._check_child(conn, record)
            pins = self.configuration.require_current(record.reservation_id, conn=conn)
        cached = self._models.get(record.reservation_id)
        if cached is not None:
            return cached
        cancellation = self._tokens.get(record.reservation_id)
        if cancellation is None:
            cancellation = DomainCancellation()
            cancellation._parent = parent.cancellation
            self._tokens[record.reservation_id] = cancellation

        def current(*, conn=None):
            cancellation.check_current()
            if conn is None:
                with self.db.transaction() as transaction:
                    current(conn=transaction)
                return
            self._connection(conn)
            row = self.journal.child_in(conn, record.reservation_id)
            if row is None or row.binding != binding:
                _deny('child_binding_conflict')
            self._check_child(conn, row)
            cancellation.check_current()

        cached = ModelRunAuthority(binding, family.configuration_version, 'evidence-review',
            pins['route']['model_id'], tuple(pins['effective_capabilities']), cancellation, current)
        self._models[record.reservation_id] = cached
        return cached

    def check(self, reservation_id, binding, stage):
        _identifier(reservation_id)
        _binding(binding)
        if type(stage) is not str or stage not in _STAGES:
            _deny('child_payload_invalid', 422)
        with self.db.transaction() as conn:
            record = self.journal.child_in(conn, reservation_id)
            if record is None:
                _deny('child_reservation_unavailable')
            _, family = self._check_child(conn, record)
            if binding not in (record.parent_binding, record.binding):
                _deny('child_binding_conflict')
        return {'current': True, 'grant_epoch': family.grant_epoch}

    def _report_record_in(self, conn, report_id):
        for family in self.journal.families_in(conn):
            for child in self.journal.children_in(conn, family.root_id):
                if child.report_id == report_id:
                    return child
        _deny('child_report_unavailable')

    def _request_current(self, request):
        with self.db.transaction() as conn:
            if request.command == 'child.prepare':
                parent = self._parent(request.binding, conn)
                family = self.journal.family_in(conn, parent.root_id)
                if family is not None and family.state != 'open':
                    _deny('child_family_sealed')
                return parent.cancellation
            if request.command == 'child.consume_report':
                record = self._report_record_in(conn, request.payload['report_id'])
                if request.binding != record.parent_binding:
                    _deny('child_binding_conflict')
            else:
                reservation_id = request.payload.get('reservation_id', request.binding.operation_id)
                record = self.journal.child_in(conn, reservation_id)
                if record is None:
                    _deny('child_reservation_unavailable')
                if request.command == 'child.admit_input':
                    if (request.binding.operation_id != record.reservation_id
                            or request.binding.attempt_id != '1'
                            or request.binding.cancellation_id != record.reservation_id):
                        _deny('child_binding_conflict')
                elif request.command == 'child.check':
                    if request.binding not in (record.parent_binding, record.binding):
                        _deny('child_binding_conflict')
                elif record.binding != request.binding:
                    _deny('child_binding_conflict')
            parent, _ = self._check_child(conn, record)
            if (record.background and request.command in {'child.observe_job', 'child.report'}
                    and request.payload['notification_id'] is None):
                _deny('child_job_conflict')
            if request.command.startswith('library.') and record.state != 'admitted':
                _deny('child_report_closed')
        token = self._tokens.get(record.reservation_id)
        if token is None:
            token = DomainCancellation()
            token._parent = parent.cancellation
            self._tokens[record.reservation_id] = token
        token.check_current()
        return token

    def _payload(self, request):
        shape = _SHAPES[request.command]
        if type(request.payload) is not dict or set(request.payload) != shape:
            _deny('child_payload_invalid', 422)
        payload = request.payload
        if 'reservation_id' in payload:
            _identifier(payload['reservation_id'])
        if request.command == 'child.check' and (type(payload['stage']) is not str or payload['stage'] not in _STAGES):
            _deny('child_payload_invalid', 422)
        if request.command == 'child.observe_job':
            _identifier(payload['job_id'])
            if payload['notification_id'] is not None:
                _identifier(payload['notification_id'])
            if type(payload['started_at']) is not int or not 0 <= payload['started_at'] <= 9007199254740991:
                _deny('child_payload_invalid', 422)
        if request.command == 'child.report':
            if payload['notification_id'] is not None:
                _identifier(payload['notification_id'])
            output, digest = payload['output'], payload['report_digest']
            if (type(output) is not str or type(digest) is not str
                    or re.fullmatch('[0-9a-f]{64}', digest) is None
                    or len(output.encode('utf-8')) > self.bounds.max_report_bytes
                    or hashlib.sha256(output.encode('utf-8')).hexdigest() != digest):
                _deny('child_payload_invalid', 422)
        if request.command == 'child.consume_report':
            _identifier(payload['report_id'])
        if request.command.startswith('library.') and (payload['command'] != request.command
                or type(payload['arguments']) is not dict or type(payload['envelope']) is not dict):
            _deny('child_payload_invalid', 422)
        encoded = _json(payload)
        if len(encoded.encode()) > self.bounds.max_work_bytes + self.bounds.max_report_bytes + 4096:
            _deny('child_payload_invalid', 422)
        return json.loads(encoded)

    async def authorize(self, request: DomainRequest):
        if request.command not in _SHAPES:
            return None
        _binding(request.binding)
        payload = self._payload(request)
        captured = DomainRequest(request.callback_id, request.binding, request.command, payload)
        token = self._request_current(captured)

        def current():
            self._request_current(captured)
            return True

        async def handle(supplied, cancellation):
            if supplied != captured:
                _deny('child_callback_conflict')
            cancellation.check_current()
            self._request_current(captured)
            if len(self._owned) >= self.bounds.max_owned:
                _deny('child_callback_capacity')
            root_id = captured.binding.operation_id
            with self.db.transaction() as conn:
                record = self.journal.child_in(conn, root_id)
                if record is not None:
                    root_id = record.root_id
            task = asyncio.create_task(self._dispatch(captured, cancellation))
            self._owned[task] = root_id

            def finished(owned):
                self._owned.pop(owned, None)
                if not owned.cancelled():
                    owned.exception()
            task.add_done_callback(finished)
            return await asyncio.shield(task)

        return DomainGrant(request.binding, handle, current, token)

    async def _dispatch(self, request, cancellation):
        command, payload, binding = request.command, request.payload, request.binding
        cancellation.check_current()
        if command == 'child.prepare':
            return asdict(self.prepare(binding, payload['invocation'], payload['work']))
        if command == 'child.admit_input':
            return asdict(self.admit_input(payload['reservation_id'], binding))
        if command == 'child.check':
            return self.check(payload['reservation_id'], binding, payload['stage'])
        if command == 'child.consume_report':
            with self.db.transaction() as conn:
                row = self._report_record_in(conn, payload['report_id'])
                return self.consume_report_in(conn, root_binding=binding,
                    child_binding=row.binding, report_digest=row.report_digest)
        if command.startswith('library.'):
            if self.library is None:
                _deny('child_library_unavailable')
            with self.db.transaction() as conn:
                row = self.journal.child_in(conn, binding.operation_id)
                parent, _ = self._check_child(conn, row)
                trusted = self._library_authority(row, parent, cancellation)
            result = await self.library.execute(command, payload['arguments'], trusted)
            cancellation.check_current()
            self._request_current(request)
            return result
        with self.db.transaction() as conn:
            row = self.journal.child_in(conn, payload['reservation_id'])
            self._check_child(conn, row)
            if command == 'child.observe_job':
                metadata = (payload['job_id'], payload['started_at'], payload['notification_id'])
                if row.job_id is not None and (row.job_id, row.started_at, row.notification_id) != metadata:
                    _deny('child_job_conflict')
                for family in self.journal.families_in(conn):
                    for other in self.journal.children_in(conn, family.root_id):
                        if other.reservation_id != row.reservation_id and (
                                other.job_id == payload['job_id'] or (payload['notification_id'] is not None
                                and other.notification_id == payload['notification_id'])):
                            _deny('child_job_conflict')
                self.journal.put_child_in(conn, replace(row, job_id=metadata[0],
                    started_at=metadata[1], notification_id=metadata[2]))
                return {'observed': True}
            if row.binding != binding or row.job_id is None or row.notification_id != payload['notification_id']:
                _deny('child_job_conflict')
            if row.report_digest is not None and row.report_digest != payload['report_digest']:
                _deny('child_report_conflict')
            report_id = row.report_id or 'report_' + uuid4().hex
            state = 'consumed' if row.state == 'consumed' else 'reported'
            self.journal.put_child_in(conn, replace(row, state=state,
                report_id=report_id, report_digest=payload['report_digest']))
            return asdict(ChildReport(report_id))

    def consume_report_in(self, conn, *, root_binding, child_binding, report_digest):
        self._connection(conn)
        _binding(root_binding)
        _binding(child_binding)
        row = self.journal.child_in(conn, child_binding.operation_id)
        if (row is None or row.binding != child_binding or row.parent_binding != root_binding
                or row.report_id is None or row.report_digest != report_digest):
            _deny('child_report_unavailable')
        self._check_child(conn, row)
        _local(self.require_publication, child_binding, conn=conn)
        sources = json.loads(row.sources_json)
        dependencies = tuple(Dependency.model_validate(item['dependency']) for item in sources)
        citations = tuple(item['citation'] for item in sources)
        if row.state != 'consumed':
            _local(self.record_consumed_in, conn, root_binding.operation_id,
                inputs=(), dependencies=dependencies, citations=citations)
            self.journal.put_child_in(conn, replace(row, state='consumed'))
        self._check_child(conn, row)
        _local(self.require_publication, child_binding, conn=conn)
        return {'consumed': True}

    def require_publication_in(self, conn, *, root_binding):
        """Revalidate used child closure/permits in the root's final transaction."""
        self._connection(conn)
        parent = self._parent(root_binding, conn)
        for child in self.journal.children_in(conn, parent.root_id):
            if child.state == 'consumed':
                self._check_child(conn, child)
                _local(self.require_publication, child.binding, conn=conn)
        self._parent(root_binding, conn)

    def seal(self, root_binding):
        """Canonical root/family seal commits before starting native controls."""
        _binding(root_binding)
        with self.db.transaction() as conn:
            family = self.journal.family_in(conn, root_binding.operation_id)
            if family is not None and family.root_binding != root_binding:
                _deny('child_binding_conflict')
            if family is None:
                _local(self.seal_root_in, conn, root_binding)
                return
            if family.state == 'settled':
                return
            if family.state == 'open':
                _local(self.seal_root_in, conn, root_binding)
                family = replace(family, state='sealed', family_epoch=family.family_epoch + 1)
                self.journal.put_family_in(conn, family)
                for child in self.journal.children_in(conn, family.root_id):
                    self.journal.put_child_in(conn, replace(child, state='sealed'))
            snapshot = FamilySnapshot(family, self.journal.children_in(conn, family.root_id))
        for child in snapshot.children:
            token = self._tokens.get(child.reservation_id)
            if token is not None:
                token.cancel()
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return  # A synchronous caller must subsequently observe settlement.
        self._start_drain(snapshot)

    def _start_drain(self, snapshot):
        return self._retain_drain(snapshot.family.root_id, lambda: self._drain(snapshot))

    def _retain_drain(self, root_id, drain):
        if root_id not in self._drains:
            task = asyncio.create_task(drain(), name='renulus-child-family-drain')
            self._drains[root_id] = task
            task.add_done_callback(lambda done: done.exception() if not done.cancelled() else None)
        return self._drains[root_id]

    async def _join_owned(self, root_id):
        while True:
            tasks = tuple(task for task, root in self._owned.items()
                if root == root_id and not task.done())
            if not tasks:
                return
            await asyncio.gather(*(asyncio.shield(task) for task in tasks), return_exceptions=True)

    async def _drain(self, snapshot):
        # Neither receipt state nor Job terminal metadata can replace these
        # actual scoped-owner effects. Retain each task until its own completion.
        stop = asyncio.create_task(self.stop_family(snapshot))
        native = asyncio.create_task(self.settle_family(snapshot))
        results = await asyncio.gather(asyncio.shield(stop), asyncio.shield(native),
            return_exceptions=True)
        await self._join_owned(snapshot.family.root_id)
        for result in results:
            if isinstance(result, BaseException):
                raise result
        with self.db.transaction() as conn:
            family = self.journal.family_in(conn, snapshot.family.root_id)
            if family != snapshot.family:
                _deny('child_family_conflict')
            _local(self.release_family_in, conn, snapshot)
            for child in self.journal.children_in(conn, family.root_id):
                self.journal.put_child_in(conn, replace(child, state='settled'))
            self.journal.put_family_in(conn, replace(family, state='settled'))
        for child in snapshot.children:
            self._models.pop(child.reservation_id, None)
            self._tokens.pop(child.reservation_id, None)

    async def settlement(self, root_binding, timeout):
        if (type(timeout) not in (int, float) or not math.isfinite(timeout)
                or not 0 < timeout <= self.bounds.max_settlement_seconds):
            _deny('child_settlement_timeout', 422)
        self.seal(root_binding)
        with self.db.transaction() as conn:
            family = self.journal.family_in(conn, root_binding.operation_id)
            if family is not None and family.state == 'settled':
                return {'state': 'settled', 'owned': 0}
            snapshot = (FamilySnapshot(family, self.journal.children_in(conn, family.root_id))
                if family is not None else None)
        if snapshot is None:
            root_id = root_binding.operation_id
            if not any(root == root_id and not owned.done() for owned, root in self._owned.items()):
                return {'state': 'settled', 'owned': 0}
            task = self._retain_drain(root_id, lambda: self._join_owned(root_id))
            def release_empty_drain(done):
                if not done.cancelled() and done.exception() is None and self._drains.get(root_id) is done:
                    self._drains.pop(root_id)
            task.add_done_callback(release_empty_drain)
        else:
            task = self._start_drain(snapshot)
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout)
        except TimeoutError:
            return {'state': 'pending', 'owned': self.status(root_binding).owned + 1}
        except asyncio.CancelledError:
            raise
        except Exception as error:
            return {'state': 'blocked', 'owned': self.status(root_binding).owned + 1,
                'code': error.code if isinstance(error, ApiError) else 'child_settlement_failed'}
        return {'state': 'settled', 'owned': 0}

    def status(self, root_binding=None) -> ChildStatus:
        with self.db.transaction() as conn:
            families = self.journal.families_in(conn)
            if root_binding is not None:
                _binding(root_binding)
                families = tuple(item for item in families if item.root_binding == root_binding)
            snapshots = tuple(FamilySnapshot(item, self.journal.children_in(conn, item.root_id))
                for item in families)
        children = tuple(child for snapshot in snapshots for child in snapshot.children)
        roots = ({root_binding.operation_id} if root_binding is not None else
            {snapshot.family.root_id for snapshot in snapshots} | set(self._owned.values()) | set(self._drains))
        return ChildStatus(snapshots, *(sum(child.state == state for child in children)
            for state in ('reserved', 'admitted', 'reported', 'consumed')),
            sum(root in roots and not task.done() for task, root in self._owned.items()),
            sum(root in roots and not task.done() for root, task in self._drains.items()),
            self.bounds.max_depth, self.bounds.concurrency)
