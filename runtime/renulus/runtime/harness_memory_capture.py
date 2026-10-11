# SPDX-License-Identifier: MIT
"""Trusted stateless capture ownership, separate from saved conversation runs."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import re
from uuid import uuid4

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.memory.capture import CaptureBinding, CaptureCurrent, CommittedCapture, _local_result
from .harness_domain import DomainBinding, DomainCancellation
from .harness_model_registry import ModelRunAuthority


_MESSAGE = 'The committed-answer extraction is unavailable.'


@dataclass
class _Capture:
    source: CommittedCapture
    source_current: CaptureCurrent
    process: object
    registry: object
    version: str
    binding: DomainBinding
    loop: asyncio.AbstractEventLoop
    cancellation: DomainCancellation = field(default_factory=DomainCancellation)
    model: ModelRunAuthority | None = None
    generation: asyncio.Task | None = None
    settlement: asyncio.Task | None = None
    cancel_control: asyncio.Task | None = None
    native_started: bool = False
    native_required: bool = False
    receipt: dict | None = None
    settled: bool = False
    observations: dict = field(default_factory=dict)
    released: asyncio.Event = field(default_factory=asyncio.Event)


class HarnessMemoryCaptures:
    """Prepared CPU work holds the root gate until Memory's durable release."""
    def __init__(self, owner):
        self.owner = owner
        self._records = {}

    def retained(self) -> int:
        return len(self._records)

    def resolve_model_run(self, binding):
        record = next((record for record in self._records.values() if record.binding == binding), None)
        return record.model if record is not None else None

    def prepare(self, source: CommittedCapture, *, current: CaptureCurrent) -> CaptureBinding:
        self.owner.check_new_run_in(None)
        if (type(source) is not CommittedCapture or not callable(current)
                or type(source.attempt) is not int or source.attempt < 1
                or ContextScope.model_validate_json(source.scope_json).kind != Scope.STUDY
                or source.input.kind != 'committed_evidence'
                or source.input.dependency.target.type != 'learning_evidence'):
            raise ApiError('memory_generation_not_scoped', _MESSAGE, 503, True)
        key = (source.job_id, source.attempt)
        if key in self._records:
            raise ApiError('memory_extraction_identity_conflict', _MESSAGE, 409)
        if len(self._records) >= self.owner.config.max_result_records:
            raise ApiError('memory_extraction_capacity', _MESSAGE, 409, True)
        _local_result(current())
        operation = 'memory_extract_' + uuid4().hex
        binding = DomainBinding(operation, str(source.attempt), 'capture:' + uuid4().hex,
            'committed-input:' + uuid4().hex, operation)
        record = _Capture(source, current, self.owner.process, self.owner.model_registry,
            self.owner.configuration_id, binding, asyncio.get_running_loop())
        self._records[key] = record

        def check(*, conn=None):
            if (record.cancellation.cancelled or self.owner._closing
                    or self.owner.process is not record.process
                    or self.owner.configuration_id != record.version
                    or self._records.get(key) is not record):
                raise ApiError('memory_capture_cancelled', _MESSAGE, 409)
            self.owner.require_profile_owner()
            _local_result(record.source_current(conn=conn))
            if record.model is not None:
                self.owner.configuration_authority.require_current(record.binding.operation_id,
                    required_capabilities=('text',), conn=conn)

        async def generate(messages):
            check()
            if (record.generation is not None or record.registry is None
                    or self.owner.configuration_authority is None):
                raise ApiError('memory_generation_not_scoped', _MESSAGE, 503, True)
            if (type(messages) is not tuple or len(messages) != 2
                    or any(type(message) is not tuple or len(message) != 2 for message in messages)
                    or tuple(message[0] for message in messages) != ('system', 'user')
                    or any(type(message[1]) is not str or not message[1].strip() for message in messages)):
                raise ApiError('memory_extraction_invalid', _MESSAGE, 422)
            system, user = messages[0][1], messages[1][1]
            with self.owner.db.transaction() as conn:
                check(conn=conn)
                canonical = self.owner.configuration_authority.begin_run_in(conn,
                    binding.operation_id, 'memory-extraction', expected_version=record.version,
                    capability_scope=('text',))
                if canonical['dispatch_limit'] != 1 or canonical['effective_capabilities'] != ['text']:
                    raise ApiError('memory_generation_not_scoped', _MESSAGE, 409)
            record.model = ModelRunAuthority(binding, canonical['version'], 'memory-extraction',
                canonical['route']['model_id'], ('text',), record.cancellation, check)
            record.generation = asyncio.create_task(self._generate(record, system, user),
                name='renulus-native-memory-extraction')
            record.generation.add_done_callback(lambda done: None if done.cancelled() else done.exception())
            return await asyncio.shield(record.generation)

        def publication(conn):
            check(conn=conn)
            if not record.settled or record.receipt is None:
                raise ApiError('memory_settlement_pending', _MESSAGE, 503, True)
            self._check_receipt(record)
            record.registry.require_publication(binding, conn=conn)

        async def settle():
            if record.settlement is None:
                record.settlement = asyncio.create_task(self._settle(record),
                    name='renulus-native-memory-settlement')
            await asyncio.shield(record.settlement)

        def release():
            if not record.settled:
                raise ApiError('memory_settlement_pending', _MESSAGE, 503, True)
            if record.model is not None:
                self.owner.configuration_authority.settle_run(binding.operation_id)
                if record.registry.status(binding).runs:
                    record.registry.release(binding)
            self._records.pop(key, None)
            record.released.set()

        return CaptureBinding(generate, check, publication, lambda: self._cancel(record), settle, release)

    def _cancel(self, record):
        record.cancellation.cancel()
        record.loop.call_soon_threadsafe(self._cancel_on_loop, record)

    def _cancel_on_loop(self, record):
        if record.released.is_set():
            return
        record.process.cancel_domain(record.binding.cancellation_id)
        if record.registry is not None and record.registry.status(record.binding).runs:
            record.registry.cancel(record.binding)
        if record.native_started and record.cancel_control is None:
            record.cancel_control = asyncio.create_task(self._observe(record, 'model.extract.cancel'),
                name='renulus-native-memory-stop')
            record.cancel_control.add_done_callback(lambda done: None if done.cancelled() else done.exception())

    def _check_receipt(self, record):
        receipts = record.registry.status(record.binding).receipts
        if (record.receipt is None or len(receipts) != 1
                or receipts[0].dispatch_id != record.receipt['dispatch_id']
                or receipts[0].permit_id != record.receipt['permit_id']
                or receipts[0].request_kind != 'primary' or receipts[0].continuation_of is not None):
            raise ApiError('memory_extraction_receipt', _MESSAGE, 409)

    async def _generate(self, record, system, user):
        record.model.current()
        record.native_started = True
        # A lost acknowledgement cannot prove the write never reached native.
        record.native_required = True
        try:
            response = await record.process.request('model.extract', {'configuration_id': record.version,
                'binding': vars(record.binding), 'system': system, 'user': user},
                record.binding.operation_id, record.binding.attempt_id, 5)
        except ApiError as error:
            raise ApiError(error.code, _MESSAGE, error.status, error.retryable) from None
        except Exception:
            raise ApiError('memory_extraction_uncertain', _MESSAGE, 503, True) from None
        record.native_required = response['outcome'] != 'rejected_before_admission'
        while response['outcome'] == 'accepted_pending':
            await asyncio.sleep(.02)
            response = await record.process.query_result(response['request_id'])
            if response is None:
                raise ApiError('memory_extraction_uncertain', _MESSAGE, 503, True)
        record.native_required = response['outcome'] != 'rejected_before_admission'
        if response['outcome'] != 'committed_reference':
            raise ApiError('memory_extraction_uncertain', _MESSAGE, 503, True)
        result = response.get('result')
        if isinstance(result, dict) and set(result) == {'failure'}:
            failure = result['failure']
            if (isinstance(failure, dict) and set(failure) == {'code', 'status', 'retryable'}
                    and type(failure['code']) is str and len(failure['code']) <= 256
                    and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]*', failure['code'])
                    and type(failure['status']) is int and 100 <= failure['status'] <= 599
                    and type(failure['retryable']) is bool):
                raise ApiError(failure['code'], _MESSAGE, failure['status'], failure['retryable'])
            raise ApiError('memory_extraction_invalid', _MESSAGE, 502)
        if (not isinstance(result, dict) or set(result) != {'text', 'receipt'}
                or type(result['text']) is not str or not result['text'].strip()
                or len(result['text']) > 16000 or not isinstance(result['receipt'], dict)
                or set(result['receipt']) != {'dispatch_id', 'permit_id'}
                or any(type(value) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,255}', value)
                    for value in result['receipt'].values())):
            raise ApiError('memory_extraction_invalid', _MESSAGE, 502)
        record.receipt = dict(result['receipt'])
        self._check_receipt(record)
        with self.owner.db.transaction() as conn:
            record.model.current(conn=conn)
            record.registry.require_publication(record.binding, conn=conn)
        return result['text']

    async def _observe(self, record, command):
        loop = asyncio.get_running_loop()
        async with asyncio.timeout_at(loop.time() + 5):
            response = record.observations.get(command)
            if response is None:
                response = await record.process.request(command, {}, record.binding.operation_id,
                    record.binding.attempt_id, 5)
                record.observations[command] = response
            while response['outcome'] == 'accepted_pending':
                await asyncio.sleep(.02)
                response = await record.process.query_result(response['request_id'])
                if response is None:
                    raise ApiError('memory_settlement_pending', _MESSAGE, 503, True)
                record.observations[command] = response
            if command == 'model.extract.status':
                while not await record.process.release_observation(response['request_id']):
                    await asyncio.sleep(.02)
            record.observations.pop(command, None)
            if response['outcome'] != 'committed_reference':
                raise ApiError('memory_settlement_pending', _MESSAGE, 503, True)
            return response['result']

    async def _settle(self, record):
        if record.generation is not None:
            await asyncio.gather(asyncio.shield(record.generation), return_exceptions=True)
        native_settled = not record.native_required
        while True:
            try:
                if not native_settled:
                    if (await record.process.settlement(0))['state'] == 'settled':
                        native_settled = True
                    else:
                        native_settled = (await self._observe(record, 'model.extract.status')).get('state') == 'settled'
                registry_status = record.registry.status(record.binding) if record.registry is not None else None
                if (native_settled and record.process.domain_status(operation_id=record.binding.operation_id)['active'] == 0
                        and (registry_status is None or registry_status.owned == 0)):
                    if record.native_required and (await record.process.settlement(0))['state'] != 'settled':
                        if (await self._observe(record, 'model.extract.release')).get('released') is not True:
                            raise ApiError('memory_settlement_pending', _MESSAGE, 503, True)
                    break
            except TimeoutError:
                pass  # The bounded read expired; this retained drain still owns cleanup.
            except ApiError as error:
                if error.code != 'memory_settlement_pending':
                    raise
            await asyncio.sleep(.02)
        if record.cancel_control is not None:
            await asyncio.gather(asyncio.shield(record.cancel_control), return_exceptions=True)
        record.settled = True

    async def close(self):
        records = tuple(self._records.values())
        for record in records:
            self._cancel(record)
        if records:
            self.owner.memory.begin_shutdown()
            # Native close is also a proof source when a lost-ack invocation
            # cannot be observed. Start it while CPU/Memory owners are retained.
            native_close = asyncio.create_task(self.owner.process.close(0),
                name='renulus-memory-native-close')
            await asyncio.gather(native_close, *(record.released.wait() for record in records))
