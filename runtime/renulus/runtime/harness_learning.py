# SPDX-License-Identifier: MIT
"""Canonical learning authority composed with the owned native transcript."""
import asyncio
import json

from renulus.contracts import ApiError
from renulus.design_c_contracts import Dependency, Identity, canonical_digest
from renulus.learn.harness_bridge import HarnessLearningBridge
from renulus.storage import utc_now
from .harness_activation import HarnessProfileActivation
from .harness_domain import DomainGrant
from .harness_library import HarnessLibrary, LibraryAuthority
from .harness_process import ManagedHarnessProcess
from .harness_profile import load_harness_profile


class HarnessLearningOwner:
    def __init__(self, services, config, *, configuration_id, memory=None):
        self.services, self.db, self.config = services, services.db, config
        self.configuration_id, self.memory = configuration_id, memory
        self.repo = services.get('conversations')
        self.library = HarnessLibrary(services.get('knowledge'))
        self.process = ManagedHarnessProcess(domain_authority=self.authorize)
        self.activation = HarnessProfileActivation(self.db, self.process, config)
        self.bindings = {}
        self.bridge = HarnessLearningBridge(self.repo, self.process,
            active_manifest=self.manifest, configuration_id=configuration_id,
            publish_answer_in=self.publish_answer_in, check_dependencies_in=self.check_dependencies_in)
        self._starting = None

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
        self.services.on_startup.append(self.start)
        self.services.on_shutdown_dependencies.append(self.close)

    async def start(self):
        if self._starting is None:
            self._starting = asyncio.create_task(self._start(), name='renulus-learning-harness-start')
        return await asyncio.shield(self._starting)

    async def _start(self):
        await self.process.start(self.config)
        await self.activation.activate()
        outcome = await self.process.request('host.activate',
            {'configuration_id': self.configuration_id}, 'configuration-activation', '1', 5)
        if outcome['outcome'] != 'committed_reference':
            raise ApiError('harness_configuration_unavailable', 'The learning runtime did not activate.', 409)

    async def close(self):
        for entry in tuple(self.repo.streaming.active.values()):
            if entry.get('harness_revisions') is not None:
                entry['run'].cancelled.set()
        while (await self.process.close(1))['state'] != 'closed':
            if (await self.process.settlement(1))['state'] == 'settled':
                break

    def _entry(self, binding, *, admitting=False, conn=None):
        self.bridge.check(binding.operation_id, conn=conn)
        entry = self.repo.streaming.active[binding.operation_id]
        runtime = entry.get('harness_runtime')
        if (binding.attempt_id != '1' or binding.cancellation_id != binding.operation_id
                or runtime is None or binding.session_id != runtime.session_id
                or not admitting and self.bindings.get(binding.operation_id) != binding):
            raise ApiError('harness_callback_identity', 'The callback is outside its admitted learning input.', 409)
        return entry

    def _current(self, binding, *, admitting=False):
        try:
            self._entry(binding, admitting=admitting)
            return True
        except ApiError:
            return False

    async def authorize(self, request):
        if request.command not in {'learning.admit_input', 'learning.authority',
                'learning.check', 'learning.context', 'library.retrieve', 'library.citation'}:
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
            if current.command in {'learning.authority', 'learning.check'}:
                if current.payload:
                    raise ApiError('harness_callback_payload', 'Authority checks take no model arguments.', 422)
                return self.envelope(entry) if current.command == 'learning.authority' else {'current': True}
            if current.command == 'learning.context':
                if not hasattr(self.bridge, 'select_context'):
                    raise ApiError('harness_history_requires_lineage', 'Native history selection is not ready.', 409)
                if set(current.payload) != {'messages'}:
                    raise ApiError('harness_callback_payload', 'Use native message identity descriptors.', 422)
                return {'message_ids': self.bridge.select_context(current.binding.operation_id,
                    messages=current.payload['messages'])}
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
                content_ref = {'target': identity.model_dump(mode='json')}
                citations.append({'content_ref': content_ref, 'document_id': reference['document_id'],
                    'revision_id': reference['document_revision'], 'passage_id': reference['passage_id']})
        self.bridge.record_consumed(entry['run'].id, dependencies=tuple(dependencies), citations=tuple(citations))

    def check_dependencies_in(self, conn, *, inputs, dependencies):
        for dependency in dependencies:
            if dependency.target.type != 'library_revision':
                raise ApiError('harness_dependencies_unavailable', 'This dependency needs its registered domain validator.', 409)
            # Resolve within the active canonical operation, without recursion.
            entries = [entry for entry in self.repo.streaming.active.values()
                if entry.get('harness_revisions') is not None]
            if len(entries) != 1:
                raise ApiError('harness_dependencies_unavailable', 'Dependency validation requires its exact operation.', 409)
            entry = entries[0]
            if self.library.resolve_dependency(conn, dependency.target,
                    authority=self.authority(entry)) != dependency.expected_revision:
                raise ApiError('memory_dependency_revoked', 'The consumed Library revision changed.', 409)
        if inputs:
            raise ApiError('harness_history_requires_lineage', 'Historical inputs require the completed lineage adapter.', 409)

    def publish_answer_in(self, conn, answer, entry):
        self.bridge.check(answer.run_id, conn=conn)
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
