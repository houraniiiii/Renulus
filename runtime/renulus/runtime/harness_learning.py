# SPDX-License-Identifier: MIT
"""Canonical learning authority composed with the owned native transcript."""
import asyncio
import json
import math

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.design_c_contracts import Dependency, EligibleInput, Identity, canonical_digest
from renulus.learn.harness_bridge import HarnessLearningBridge
from renulus.learn.memory_context import MemoryContext
from renulus.memory.lineage import INELIGIBLE_LINEAGE_CODES
from renulus.storage import utc_now
from .harness_activation import HarnessProfileActivation
from .harness_configuration import Candidate
from .harness_configuration_controller import RegistryHealth
from .harness_domain import DomainCancellation, DomainCancelled, DomainGrant
from .harness_library import HarnessLibrary, LibraryAuthority
from .harness_model_registry import HarnessModelRegistry, ModelRunAuthority
from .harness_memory_capture import HarnessMemoryCaptures
from .harness_process import ManagedHarnessProcess, NativeProcessIdentity, OBSERVATION_COMMANDS
from .harness_profile import load_harness_profile
from .harness_profile_owner import ProfileOwnerLease, ProfileOwnerScope


_STALE_LEARNING_AUTHORITY_CODES = INELIGIBLE_LINEAGE_CODES | frozenset({
    'harness_run_unavailable', 'harness_cancelled', 'harness_callback_identity',
    'conversation_missing', 'conversation_revision_conflict',
    'assistance_restricted', 'assistance_changed', 'dependency_changed',
})


class _LearningRootSeal:
    def __init__(self, owner):
        self.owner = owner

    def release(self):
        if self.owner._root_seal is self:
            self.owner._root_seal = None


class HarnessLearningOwner:
    def __init__(self, services, config, *, configuration_id, memory=None, context_filtering=False,
                 configuration_authority=None, model_registry_factory=None, profile_owner=None):
        self.services, self.db, self.config = services, services.db, config
        self.configuration_id, self.memory = configuration_id, memory
        self.profile_owner = profile_owner
        self.require_profile_owner()
        if configuration_authority is not None and configuration_authority.db is not self.db:
            raise ApiError('harness_owner_conflict', 'Configuration belongs to another profile.', 409)
        self.configuration_authority = configuration_authority
        self.configuration_spec = (configuration_authority.configuration(configuration_id)
            if configuration_authority is not None else None)
        self._root_seal = None
        self._closing = False
        self.repo = services.get('conversations')
        self.library = services.registry.get('harness_library') or HarnessLibrary(services.get('knowledge'))
        self.process = ManagedHarnessProcess(domain_authority=self.authorize)
        self.activation = HarnessProfileActivation(self.db, self.process, config)
        self.bindings = {}
        self.model_bindings = {}
        self._settlements = {}
        self.model_registry_factory = model_registry_factory
        self.model_registry = self._make_model_registry()
        self.memory_captures = HarnessMemoryCaptures(self)
        self.bridge = HarnessLearningBridge(self.repo, self.process,
            active_manifest=self.manifest, configuration_id=configuration_id,
            publish_answer_in=self.publish_answer_in, check_run_dependencies_in=self.check_run_dependencies_in,
            eligible_history_in=self.eligible_history_in, context_filtering=context_filtering,
            check_new_run_in=self.check_new_run_in, admit_run_in=self.admit_run_in,
            settle_run=self.settle_run if configuration_authority is not None else None,
            cancel_run=self.cancel_run)
        self._starting = None
        self._starting_candidate = None
        self._close_task = None

    def _make_model_registry(self, *, previous=None):
        if self.model_registry_factory is None:
            return None
        if self.configuration_authority is None or not callable(self.model_registry_factory):
            raise ApiError('harness_owner_conflict', 'A model registry requires the canonical authority.', 409)
        registry = self.model_registry_factory(self.resolve_model_run)
        if (not isinstance(registry, HarnessModelRegistry)
                or registry.authority is not self.configuration_authority or registry is previous):
            raise ApiError('harness_owner_conflict', 'The model registry belongs to another authority.', 409)
        status = registry.status()
        if status.state != 'open' or status.runs or status.owned or status.retained_bytes:
            raise ApiError('harness_owner_conflict', 'Each generation requires a fresh model registry.', 409)
        return registry

    def manifest(self):
        return load_harness_profile(self.config.profile_root, profile_id=self.config.profile_id,
            domain_store_id=self.config.domain_store_id, runtime_store_id=self.config.store_id,
            domain_path=self.config.domain_path).model_dump(mode='json')

    def install(self):
        if self.services.registry.get('learning_harness') not in (None, self.bridge):
            raise ApiError('harness_owner_conflict', 'A learning harness already owns this profile.', 409)
        if self.services.registry.get('learning_harness') is self.bridge:
            return
        self.services.registry['learning_harness'] = self.bridge
        self.services.registry['harness_learning'] = self
        self.services.registry['harness_library'] = self.library
        self.services.registry['completed_answer_resolver'] = self
        if self.memory is not None and self.model_registry is not None:
            self.memory.bind_committed_answer_extractor(self.memory_captures.prepare)
        self.services.on_startup.append(self.start)
        self.services.on_shutdown_dependencies.append(self.close)

    async def start(self):
        if self._closing:
            raise ApiError('runtime_stopping', 'The learning runtime is closing.', 503, True)
        if self._starting is None:
            self._starting = asyncio.create_task(self._start(), name='renulus-learning-harness-start')
        return await asyncio.shield(self._starting)

    def _require_gated_candidate(self, candidate):
        if self._closing:
            raise ApiError('runtime_stopping', 'The learning runtime is closing.', 503, True)
        if (type(candidate) is not Candidate or self.configuration_authority is None
                or candidate.version != self.configuration_id or type(candidate.grant_epoch) is not int
                or any(value is not False for value in (candidate.generation_open,
                    candidate.recovery_open, candidate.package_acquisition_open,
                    candidate.mcp_startup_open, candidate.live_store_writer))):
            raise ApiError('candidate_authority_stale', 'The gated startup candidate is unavailable.', 409, True)
        snapshot = self.configuration_authority.activation_snapshot()
        if (snapshot['effective'] != candidate.version or snapshot['configuration'] != candidate.spec
                or self.configuration_spec != candidate.spec or snapshot['admission_open']
                or snapshot['grant_epoch'] != candidate.grant_epoch or snapshot['pinned_runs']):
            raise ApiError('candidate_authority_stale', 'The gated startup authority changed.', 409, True)

    async def start_gated(self, candidate: Candidate) -> RegistryHealth:
        """Inspect the initial live registry before arming it under closed admission."""
        self._require_gated_candidate(candidate)
        if self._starting is None:
            self._starting_candidate = candidate
            self._starting = asyncio.create_task(self._start(candidate),
                name='renulus-learning-harness-gated-start')
        elif self._starting_candidate != candidate:
            raise ApiError('activation_conflict', 'The native startup already has another owner.', 409, True)
        return await asyncio.shield(self._starting)

    async def _startup_command(self, command, payload):
        deadline = asyncio.get_running_loop().time() + 5
        response = await self.process.request(command, payload, 'configuration-activation', '1', 5)
        while response['outcome'] == 'accepted_pending':
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise ApiError('harness_configuration_unavailable',
                    'The startup operation is pending; its owner is retained.', 503, True)
            await asyncio.sleep(min(.02, remaining))
            response = await self.process.query_result(response['request_id'])
            if response is None:
                raise ApiError('harness_configuration_unavailable',
                    'The startup observation is unavailable.', 503, True)
        if command in OBSERVATION_COMMANDS:
            try:
                await asyncio.wait_for(self.process.release_observation(response['request_id']),
                    max(0, deadline - asyncio.get_running_loop().time()))
            except TimeoutError:
                raise ApiError('harness_configuration_unavailable',
                    'The startup observation remains owned.', 503, True) from None
        if response['outcome'] != 'committed_reference':
            raise ApiError('harness_configuration_unavailable', 'The learning runtime did not activate.', 409)
        return response['result']

    async def _start(self, candidate=None):
        if self._closing:
            raise ApiError('runtime_stopping', 'The learning runtime is closing.', 503, True)
        if candidate is not None:
            self._require_gated_candidate(candidate)
        self.require_profile_owner()
        await self.process.start(self.config)
        self.register_process(self.process, self.config)
        if self._closing:
            raise ApiError('runtime_stopping', 'The learning runtime is closing.', 503, True)
        if candidate is not None:
            self._require_gated_candidate(candidate)
        await self.activation.activate()
        if self._closing:
            raise ApiError('runtime_stopping', 'The learning runtime is closing.', 503, True)
        if candidate is not None:
            self._require_gated_candidate(candidate)
            registry = await self._startup_command('host.inspect', {})
            self._require_gated_candidate(candidate)
            if (registry.get('state') != 'policy_blocked' or registry.get('live_store_writer') is not True
                    or registry.get('registry_hash') != candidate.spec.registry_hash
                    or any(registry.get(key) is not False for key in ('generation_open',
                        'recovery_open', 'package_acquisition_open', 'mcp_startup_open'))):
                raise ApiError('registry_mismatch', 'The gated live registry differs from the candidate.', 409, True)
        ready = await self._startup_command('host.activate', {'configuration_id': self.configuration_id})
        if candidate is not None:
            self._require_gated_candidate(candidate)
            if ready.get('state') != 'ready' or ready.get('configurationId') != candidate.version:
                raise ApiError('harness_configuration_unavailable', 'The gated runtime did not arm this configuration.', 409)
            return RegistryHealth(configuration_version=candidate.version,
                grant_epoch=candidate.grant_epoch, registry_hash=registry['registry_hash'])

    def require_profile_owner(self):
        """Opt-in assembly requires the actual current process's issuer-bound lease."""
        lease = self.profile_owner
        if lease is None:
            return
        expected = ProfileOwnerScope(self.config.profile_root, self.config.profile_id,
            self.config.domain_store_id, self.config.store_id)
        if (type(lease) is not ProfileOwnerLease or lease.scope != expected
                or self.services.paths.root != expected.root):
            raise ApiError('harness_owner_conflict', 'The profile process owner does not match.', 409)
        lease.require_predecessor(lease.predecessor)

    def register_process(self, process, config):
        """Register live or isolated native identity before activation or commands."""
        self.require_profile_owner()
        if self.profile_owner is None:
            return
        identity = process.native_identity()
        if (type(identity) is not NativeProcessIdentity
                or identity.profile_id != config.profile_id or identity.store_id != config.store_id):
            raise ApiError('harness_owner_conflict', 'The native process identity does not match.', 409)
        self.profile_owner.register_native(identity.pid, generation=identity.generation)

    async def close(self):
        self._closing = True
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._close(), name='renulus-learning-harness-close')
        await asyncio.shield(self._close_task)

    async def _close(self):
        if self._starting is not None:
            await asyncio.gather(asyncio.shield(self._starting), return_exceptions=True)
        for entry in tuple(self.repo.streaming.active.values()):
            if entry.get('harness_revisions') is not None:
                entry['run'].cancelled.set()
                self.cancel_run(entry)
                await self.settle_run(entry, timeout=0)
        await self.memory_captures.close()
        if self.model_registry is not None:
            await self.model_registry.close(0)
        while (await self.process.close(1))['state'] != 'closed':
            if (await self.process.settlement(1))['state'] == 'settled':
                break
        if self._settlements:
            await asyncio.gather(*(asyncio.shield(task) for task in tuple(self._settlements.values())))
        if self.model_registry is not None:
            while (await self.model_registry.settlement(1)).owned:
                pass

    async def settle_run(self, entry, *, timeout=5):
        """Bounded observation; retained cleanup owns the canonical pin until proof."""
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 <= timeout <= 300:
            raise ApiError('harness_settlement_timeout', 'Use a bounded settlement observation.', 422)
        if self.configuration_authority is None:
            return {'state': 'settled'}
        run_id = entry['run'].id
        if entry.get('harness_settled'):
            return {'state': 'settled'}
        task = self._settlements.get(run_id)
        if task is None:
            task = asyncio.create_task(self._settle_run(entry, self.process, self.model_registry),
                name='renulus-learning-settlement-' + run_id)
            self._settlements[run_id] = task
            task.add_done_callback(lambda finished: self._settlement_finished(run_id, finished))
        done, _ = await asyncio.wait({task}, timeout=timeout)
        if not done:
            return {'state': 'pending'}
        if task.cancelled():
            return {'state': 'blocked', 'code': 'harness_settlement_cancelled'}
        error = task.exception()
        if error is not None:
            return {'state': 'blocked', 'code': error.code if isinstance(error, ApiError)
                else 'harness_settlement_failed'}
        return {'state': 'settled'}

    def _settlement_finished(self, run_id, task):
        if not task.cancelled():
            error = task.exception()
            if error is None and self._settlements.get(run_id) is task:
                self._settlements.pop(run_id)
            # Failed cleanup remains owned; retrieving its cause avoids losing it.

    async def _settle_run(self, entry, process, registry):
        run_id = entry['run'].id
        runtime = entry.get('harness_runtime')
        binding = self.bindings.get(run_id)
        observation = None
        while True:
            native_settled = not entry.get('harness_native_started')
            if not native_settled and (await process.settlement(0))['state'] == 'settled':
                native_settled = True
            if not native_settled and runtime is not None:
                response = (await process.query_result(observation) if observation is not None else
                    await process.request('session.get', {'session_id': runtime.session_id}, run_id, '1', 1))
                if response is None:
                    raise ApiError('harness_settlement_unavailable', 'The retained native observation is unavailable.', 503, True)
                observation = response.get('request_id') if response.get('outcome') == 'accepted_pending' else None
                release = getattr(process, 'release_observation', None)
                if observation is None and release is not None:
                    await release(response['request_id'])
                observed = response.get('result', {})
                native_settled = (response.get('outcome') == 'committed_reference'
                    and observed.get('session', {}).get('id') == runtime.session_id
                    and observed.get('execution') == 'settled')
            registry_status = registry.status(binding) if registry is not None and binding is not None else None
            if (native_settled and process.domain_status(operation_id=run_id)['active'] == 0
                    and (registry_status is None or registry_status.owned == 0)):
                self.configuration_authority.settle_run(run_id)
                if registry_status is not None and registry_status.runs:
                    registry.release(binding)
                self.bindings.pop(run_id, None)
                self.model_bindings.pop(run_id, None)
                entry['harness_settled'] = True
                return
            await asyncio.sleep(.02)

    def cancel_run(self, entry):
        """Seal publication immediately without cancelling owned workers."""
        entry['run'].cancelled.set()
        run_id = entry['run'].id
        model = self.model_bindings.get(run_id)
        if model is not None:
            model.cancellation.cancel()
        binding = self.bindings.get(run_id)
        if self.model_registry is not None and binding is not None and self.model_registry.status(binding).runs:
            self.model_registry.cancel(binding)
        cancel_domain = getattr(self.process, 'cancel_domain', None)
        if cancel_domain is not None:
            cancel_domain(run_id)

    def check_new_run_in(self, conn):
        if self._closing:
            raise ApiError('runtime_stopping', 'The learning runtime is closing.', 503, True)
        if self._root_seal is not None:
            raise ApiError('harness_configuration_busy',
                'Configuration is changing. New learning runs are sealed.', 409, True)

    def admit_run_in(self, conn, run, request):
        if self.configuration_authority is None:
            if request.images:
                raise ApiError('harness_configuration_unavailable',
                    'Inline images require current configuration authority.', 409, True)
            return
        pinned = self.configuration_authority.begin_run_in(conn, run.id, 'explain',
            expected_version=self.configuration_id,
            capability_scope=self.configuration_spec.capabilities, operation_model=request.model)
        if request.images:
            self.configuration_authority.require_current(run.id,
                required_capabilities=('image',), conn=conn)
        run.harness_configuration_version = pinned['version']
        run.harness_model_id = pinned['route']['model_id']
        run.harness_capabilities = tuple(pinned['effective_capabilities'])

    def seal_new_runs(self, *, expected_effective):
        """Failure-atomic root gate sharing the canonical admission transaction."""
        seal = _LearningRootSeal(self)
        try:
            with self.db.transaction() as conn:
                if self._root_seal is not None or self.configuration_id != expected_effective:
                    raise ApiError('activation_conflict', 'The live configuration changed.', 409, True)
                if (self.memory_captures.retained() or any(entry.get('harness_revisions') is not None
                        for entry in tuple(self.repo.streaming.active.values())) or conn.execute(
                    "SELECT 1 FROM learn_harness_answers a JOIN learn_runs r ON r.id=a.run_id "
                    "WHERE r.state IS NULL OR r.state='running' OR a.state IS NULL "
                    "OR a.state IN ('reserved','uncertain','submitted') LIMIT 1").fetchone()):
                    raise ApiError('harness_configuration_busy',
                        'Finish or stop the native learning runs before changing configuration.', 409, True)
                self._root_seal = seal
        except BaseException:
            seal.release()
            raise
        return seal

    def require_root_seal(self, seal):
        if seal is None or self._root_seal is not seal:
            raise ApiError('activation_conflict', 'The root admission lease changed.', 409, True)

    def replace_process(self, process, *, configuration_id, seal):
        """Lifecycle owner calls only after observing actual old settlement."""
        self.require_root_seal(seal)
        if self._closing:
            raise ApiError('runtime_stopping', 'The learning runtime is closing.', 503, True)
        if self.memory_captures.retained() or self._settlements or (self.model_registry is not None and (
                self.model_registry.status().owned or self.model_registry.status().runs)):
            raise ApiError('harness_settlement_pending', 'The previous model owner is still retained.', 409, True)
        registry = self._make_model_registry(previous=self.model_registry)
        self.process = process
        self.configuration_id = self.bridge.configuration_id = configuration_id
        if self.configuration_authority is not None:
            self.configuration_spec = self.configuration_authority.configuration(configuration_id)
        self.bridge.transport = process
        self.bindings.clear()
        self.model_bindings.clear()
        self.model_registry = registry
        self.activation = HarnessProfileActivation(self.db, process, self.config)
        self._starting = None
        self._starting_candidate = None

    def _entry(self, binding, *, admitting=False, conn=None):
        self.bridge.check(binding.operation_id, conn=conn)
        if self.configuration_authority is not None:
            run = self.repo.streaming.active[binding.operation_id]['run']
            self.configuration_authority.require_current(binding.operation_id,
                required_capabilities=run.harness_capabilities, conn=conn)
        entry = self.repo.streaming.active[binding.operation_id]
        runtime = entry.get('harness_runtime')
        if (binding.attempt_id != '1' or binding.cancellation_id != binding.operation_id
                or runtime is None or binding.session_id != runtime.session_id
                or not admitting and self.bindings.get(binding.operation_id) != binding):
            raise ApiError('harness_callback_identity', 'The callback is outside its admitted learning input.', 409)
        return entry

    def resolve_model_run(self, binding):
        """Trusted local pins exist only after native input admission."""
        capture = self.memory_captures.resolve_model_run(binding)
        if capture is not None:
            return capture
        if self.configuration_authority is None or self.bindings.get(binding.operation_id) != binding:
            return None
        entry = self._entry(binding)
        retained = self.model_bindings.get(binding.operation_id)
        if retained is not None:
            return retained if retained.binding == binding else None
        run, process = entry['run'], self.process
        cancellation = DomainCancellation()

        def current(*, conn=None):
            if run.cancelled.is_set():
                cancellation.cancel()
                raise DomainCancelled('domain_cancelled')
            if self.process is not process:
                raise ApiError('harness_callback_identity', 'The native generation changed.', 409)
            self._entry(binding, conn=conn)

        retained = ModelRunAuthority(binding, run.harness_configuration_version, 'explain',
            run.harness_model_id, run.harness_capabilities, cancellation, current)
        self.model_bindings[binding.operation_id] = retained
        return retained

    def _current(self, binding, *, admitting=False):
        try:
            self._entry(binding, admitting=admitting)
            return True
        except ApiError as error:
            if error.code in _STALE_LEARNING_AUTHORITY_CODES:
                return False
            raise

    async def authorize(self, request):
        if request.command in {'model.prepare', 'model.manifest', 'model.dispatch'}:
            if self.model_registry is None:
                return None
            return await self.model_registry.authorize(request)
        if request.command not in {'learning.admit_input', 'learning.authority',
                'learning.check', 'learning.context', 'learning.validate_images', 'library.retrieve', 'library.citation'}:
            return None
        admitting = request.command == 'learning.admit_input'
        self._entry(request.binding, admitting=admitting)

        async def handle(current, cancellation):
            entry = self._entry(current.binding, admitting=admitting)
            cancellation.check_current()
            if admitting:
                if current.payload:
                    raise ApiError('harness_callback_payload', 'Input admission takes no model arguments.', 422)
                prior = self.bindings.get(current.binding.operation_id)
                if prior is not None and prior != current.binding:
                    raise ApiError('harness_input_conflict', 'This operation already has its native input.', 409)
                bind = getattr(self.bridge, 'bind_input', None)
                if bind is not None:
                    bind(current.binding.operation_id, session_id=current.binding.session_id,
                        input_id=current.binding.input_id, attempt_id=current.binding.attempt_id)
                else:
                    # Local pre-dispatch pin for the existing H02 bridge.
                    with self.db.transaction() as conn:
                        self.bridge.check(current.binding.operation_id, conn=conn)
                        row = conn.execute('SELECT input_id,state FROM learn_harness_answers WHERE run_id=?',
                            (current.binding.operation_id,)).fetchone()
                        if row['state'] != 'uncertain' or row['input_id'] not in (None, current.binding.input_id):
                            raise ApiError('harness_input_conflict', 'The native input receipt changed.', 409)
                        conn.execute('UPDATE learn_harness_answers SET input_id=? WHERE run_id=?',
                            (current.binding.input_id, current.binding.operation_id))
                self.bindings[current.binding.operation_id] = current.binding
                return {'admitted': True}
            if current.command == 'learning.validate_images':
                if set(current.payload) != {'images'}:
                    raise ApiError('harness_callback_payload', 'Use typed inline image validation.', 422)
                from .provider_adapter import validate_harness_images
                # Local in-memory parser: no SQL transaction, path or network read.
                validate_harness_images(current.payload['images'])
                self._entry(current.binding)
                cancellation.check_current()
                return {'validated': True}
            if current.command in {'learning.authority', 'learning.check'}:
                if current.payload:
                    raise ApiError('harness_callback_payload', 'Authority checks take no model arguments.', 422)
                return self.envelope(entry) if current.command == 'learning.authority' else {'current': True}
            if current.command == 'learning.context':
                if not hasattr(self.bridge, 'select_context'):
                    raise ApiError('harness_history_requires_lineage', 'Native history selection is not ready.', 409)
                if set(current.payload) != {'messages'}:
                    raise ApiError('harness_callback_payload', 'Use native message identity descriptors.', 422)
                context = entry.get('harness_memory_context')
                if context is None:
                    context = MemoryContext()
                    if self.memory is not None:
                        recalled = await asyncio.to_thread(self.memory.retrieve, entry['request'].text,
                            scope=entry['run'].scope, limit=6, budget_chars=3000,
                            topic_id=entry['request'].topic_id, project_id=entry['run'].project_id)
                        self._entry(current.binding)
                        cancellation.check_current()
                        context = MemoryContext.capture(self.db, recalled, entry['request'].topic_id)
                        self.bridge.record_consumed(current.binding.operation_id, inputs=tuple(
                            EligibleInput(kind='memory', dependency=Dependency(
                                target=Identity(type='memory_revision', id=f'{pin[0]}:{pin[1]}'),
                                expected_revision=str(pin[1]))) for pin in context.pins))
                    entry['harness_memory_context'] = context
                context.check(self.db)
                return {'message_ids': self.bridge.select_context(current.binding.operation_id,
                    messages=current.payload['messages']), 'learner_context': context.context}
            if set(current.payload) != {'command', 'arguments', 'envelope'} or current.payload['command'] != current.command:
                raise ApiError('harness_callback_payload', 'Use the registered Library command.', 422)
            # The envelope is observation only; canonical entry supplies authority.
            trusted = self.authority(entry, cancellation=cancellation)
            return await self.library.execute(current.command, current.payload['arguments'], trusted)

        return DomainGrant(request.binding, handle,
            lambda: self._current(request.binding, admitting=admitting))

    def envelope(self, entry):
        run = entry['run']
        return {'sessionId': entry['harness_runtime'].session_id, 'operationId': run.id, 'attemptId': '1',
            'scope': run.scope.model_dump(mode='json'), 'revisionIds': getattr(run, 'revision_ids', None),
            'policyRevision': run.policy_revision, 'contextEpoch': run.context_epoch, 'cancellationEpoch': 0}

    def authority(self, entry, *, cancellation=None):
        run = entry['run']
        binding = self.bindings.get(run.id)
        def guard(conn):
            if binding is None or cancellation is not None and cancellation.cancelled:
                raise ApiError('harness_tool_cancelled', 'The admitted Library operation is unavailable.', 409)
            # The full DomainGrant predicate opens its own snapshot. Within a
            # canonical transaction, recheck that authority in this connection.
            self._entry(binding, conn=conn)
        return LibraryAuthority(scope=run.scope, revision_ids=getattr(run, 'revision_ids', None),
            policy_revision=run.policy_revision, context_epoch=run.context_epoch,
            cancelled=lambda: run.cancelled.is_set() or bool(cancellation and cancellation.cancelled),
            guard=guard, record_dependencies=lambda references: self.record_dependencies(entry, references),
            topic_id=entry['request'].topic_id)

    def record_dependencies(self, entry, references):
        dependencies, citations = [], []
        with self.db.transaction() as conn:
            self.bridge.check(entry['run'].id, conn=conn)
            for reference in references:
                identity = Identity(type='library_revision', id=reference['document_revision'])
                revision = self.library.resolve_dependency(conn, identity, authority=self.authority(entry))
                if revision is None:
                    raise ApiError('harness_sources_changed', 'The consumed Library source changed.', 409)
                dependencies.append(Dependency(target=identity, expected_revision=revision))
                citations.append(self.library.project_content_reference(conn, reference, authority=self.authority(entry)))
        self.bridge.record_consumed(entry['run'].id, dependencies=tuple(dependencies), citations=tuple(citations))

    def _dependency_scope_in(self, conn, run_id):
        row = conn.execute('SELECT thread_id,reference_json FROM learn_harness_answers WHERE run_id=?',
            (run_id,)).fetchone()
        if row is None:
            raise ApiError('harness_run_unavailable', 'The learning dependency owner is unavailable.', 409)
        projects = self.services.registry.get('projects')
        project = projects.context_in(conn, 'learning', row['thread_id']) if projects else None
        entry = self.repo.streaming.active.get(run_id)
        if entry is not None:
            if entry['id'] != row['thread_id'] or entry.get('project') != project:
                raise ApiError('harness_dependencies_unavailable', 'The learning dependency scope changed.', 409)
            return self.authority(entry), entry['run'].project_id
        snapshot = json.loads(row['reference_json'] or '{}')
        if snapshot.get('kind') != 'pending' or canonical_digest(project) != snapshot.get('project_digest'):
            raise ApiError('harness_dependencies_unavailable', 'The original learning dependency scope is unavailable.', 409)
        authority = LibraryAuthority(scope=ContextScope(kind=Scope.STUDY, entity_id=row['thread_id']),
            revision_ids=tuple(project['revision_ids']) if project and project['project_id'] else None,
            policy_revision=snapshot['policy'], context_epoch=snapshot['epoch'],
            cancelled=lambda: False, guard=lambda conn: None, record_dependencies=lambda references: None,
            topic_id=snapshot['request_fields'].get('topic_id'))
        return authority, project['project_id'] if project else None

    def check_run_dependencies_in(self, conn, *, run_id, inputs, dependencies):
        authority, project_id = self._dependency_scope_in(conn, run_id)
        for dependency in dependencies:
            if dependency.target.type != 'library_revision':
                continue
            if self.library.resolve_dependency(conn, dependency.target, authority=authority) != dependency.expected_revision:
                raise ApiError('memory_dependency_revoked', 'The consumed Library revision changed.', 409)
        if self.memory is not None:
            self.memory.check_answer_inputs_in(conn, inputs=inputs,
                dependencies=dependencies, project_id=project_id)
        elif inputs or any(dependency.target.type != 'library_revision' for dependency in dependencies):
            raise ApiError('harness_history_requires_lineage', 'Historical inputs require the completed lineage adapter.', 409)

    def eligible_history_in(self, conn, *, references, project_id):
        if self.memory is None:
            return ()
        exact = tuple({key: value for key, value in reference.items() if key != 'publication_digest'}
            for reference in references)
        return self.memory.eligible_answer_references_in(conn, exact, project_id=project_id)

    def _answer_resolution_in(self, conn, reference):
        from renulus.memory.lineage import AnswerInputs
        from renulus.memory.study_answers import answer_reference_in
        evidence_id = 'learn-answer:' + reference['run_id']
        evidence = conn.execute('SELECT * FROM learning_evidence WHERE id=?', (evidence_id,)).fetchone()
        lineage = conn.execute('SELECT * FROM memory_answer_lineage WHERE evidence_id=?', (evidence_id,)).fetchone()
        if self.memory is None or evidence is None or lineage is None or lineage['state'] != 'active':
            raise ApiError('memory_answer_unavailable', 'The completed answer support is unavailable.', 409)
        payload = json.loads(evidence['payload_json'])
        scope = ContextScope.model_validate(payload['scope'])
        if answer_reference_in(conn, evidence, payload, scope) != reference:
            raise ApiError('memory_answer_reference', 'The completed answer reference changed.', 409)
        manifest = AnswerInputs.model_validate_json(lineage['manifest_json'])
        self.memory.check_answer_inputs_in(conn, inputs=manifest.inputs,
            dependencies=manifest.dependencies, project_id=lineage['project_id'])
        return dict(evidence), payload, scope, lineage['publication_digest'], manifest

    async def resolve_completed_answer(self, reference):
        """Resolve exact native or retained legacy bytes with canonical writers free."""
        with self.db.transaction() as conn:
            snapshot = self._answer_resolution_in(conn, reference)
        if 'runtime' in reference:
            answer = await self.bridge.resolve_completed(reference['run_id'])
            if answer.reference() != reference:
                raise ApiError('memory_answer_reference', 'The completed native answer changed.', 409)
            text, digest = answer.text, answer.sha256
        else:
            from renulus.memory.study_answers import answer_text
            text = await asyncio.to_thread(answer_text, self.db, *snapshot[:3])
            digest = reference['sha256']
        with self.db.transaction() as conn:
            if self._answer_resolution_in(conn, reference) != snapshot:
                raise ApiError('memory_answer_version', 'The completed answer publication changed.', 409)
        return {'text': text, 'digest': digest, 'publication_digest': snapshot[3],
            'input': snapshot[4].model_dump(mode='json')}

    def publish_answer_in(self, conn, answer, entry):
        self.bridge.check(answer.run_id, conn=conn)
        if self.configuration_authority is not None:
            self.configuration_authority.require_current(answer.run_id,
                required_capabilities=entry['run'].harness_capabilities, conn=conn)
        if self.model_registry is not None:
            binding = self.bindings.get(answer.run_id)
            if binding is None:
                raise ApiError('harness_callback_identity', 'The publication has no admitted native input.', 409)
            self.model_registry.require_publication(binding, conn=conn)
        passages = [{'id': citation['passage_id'], 'document_id': citation['document_id'],
            'document_revision': citation['revision_id']} for citation in answer.citations]
        self.library.validate_publication(passages, self.authority(entry), conn=conn)
        reference = answer.reference()
        conn.execute('INSERT INTO learning_evidence VALUES(?,?,?,?,?,?)',
            ('learn:' + answer.run_id, 'study-interest', entry['request'].topic_id, entry['id'],
                json.dumps({'activity': 'explain', 'scope': entry['run'].scope.model_dump(mode='json')}), utc_now()))
        if self.memory is None:
            return canonical_digest(reference)
        evidence_id = 'learn-answer:' + answer.run_id
        conn.execute('INSERT INTO learning_evidence VALUES(?,?,?,?,?,?)',
            (evidence_id, 'study-answer', entry['request'].topic_id, entry['id'],
                json.dumps({'scope': entry['run'].scope.model_dump(mode='json'), 'answer_reference': reference}), utc_now()))
        return self.memory.publish_answer_lineage_in(conn, evidence_id, inputs=answer.inputs,
            dependencies=answer.dependencies, project_id=entry['run'].project_id)
