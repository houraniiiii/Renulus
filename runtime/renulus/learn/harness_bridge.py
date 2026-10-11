# SPDX-License-Identifier: MIT
"""Saved learning adapts the native transcript, never another execution loop.

The integration owner supplies a verified active selection and a managed process.
All transport waits happen outside canonical transactions and physical locks.
Publication receives resolved immutable bytes and performs local checks only.
"""
from __future__ import annotations

import asyncio
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json

from renulus.contracts import ApiError, ContextScope, Event, Scope, durable_id
from renulus.design_c_contracts import (Conversation, Dependency, EligibleInput,
    canonical_digest)
from renulus.harness_contracts import (HarnessCommandIdentity, HarnessEngineReference,
    PairedStoreManifest, SavedConversationMapping, map_saved_conversation, validate_command_outcome)
from renulus.storage import utc_now
from renulus.storage.assessment_policy import require_assistance
from renulus.storage.invalidation import context_epoch_in
from renulus.runtime.harness_process import OBSERVATION_COMMANDS
from .service import ActiveRun
from .conversation_models import Send


@dataclass(frozen=True)
class CompletedAnswer:
    run_id: str
    thread_id: str
    runtime: HarnessEngineReference
    input_id: str
    message_ids: tuple[str, ...]
    text: str
    sha256: str
    citations_json: str = '[]'
    inputs: tuple[EligibleInput, ...] = ()
    dependencies: tuple[Dependency, ...] = ()

    @property
    def citations(self):
        return json.loads(self.citations_json)

    def reference(self):
        return {'version': 1, 'run_id': self.run_id, 'thread_id': self.thread_id,
            'runtime': self.runtime.model_dump(mode='json'), 'input_id': self.input_id,
            'message_ids': list(self.message_ids), 'sha256': self.sha256,
            'citations': [{key: value for key, value in citation.items()
                if key in {'content_ref', 'passage_id', 'document_id', 'revision_id', 'locator', 'locators'}}
                for citation in self.citations],
            'inputs': [item.model_dump(mode='json') for item in self.inputs],
            'dependencies': [item.model_dump(mode='json') for item in self.dependencies]}


class HarnessLearningBridge:
    def __init__(self, repository, transport, *, active_manifest, configuration_id,
                 publish_answer_in=None, check_dependencies_in=None, check_run_dependencies_in=None,
                 eligible_history_in=None, context_filtering=False, check_new_run_in=None,
                 admit_run_in=None, settle_run=None, cancel_run=None, check_migration_in=None, poll_interval=0.05):
        self.repo, self.db, self.transport = repository, repository.db, transport
        self.active_manifest, self.configuration_id = active_manifest, configuration_id
        self.publish_answer_in = publish_answer_in
        self.check_dependencies_in = check_dependencies_in
        self.check_run_dependencies_in = check_run_dependencies_in
        self.eligible_history_in = eligible_history_in
        self.check_new_run_in = check_new_run_in
        self.admit_run_in = admit_run_in
        self.settle_run = settle_run
        self.cancel_run = cancel_run
        self.check_migration_in = check_migration_in
        # Trusted assembly asserts that the native per-model hook is installed.
        self.context_filtering = context_filtering
        self.poll_interval = poll_interval
        self._consumed = {}
        self._reconciling = {}

    def _manifest(self):
        try:
            manifest = PairedStoreManifest.model_validate(self.active_manifest())
            if manifest.state != 'active':
                raise ValueError('prepared')
            return manifest
        except (ValueError, TypeError):
            raise ApiError('harness_not_active', 'Activate the validated learning stores first.', 409, True) from None

    def prepare_in(self, conn, identifier, request, key):
        self._manifest()
        if self.check_new_run_in is not None:
            self.check_new_run_in(conn)
        # H02 admits new saved learning. Importing legacy text is the H06 gate.
        if conn.execute('SELECT 1 FROM learn_messages WHERE thread_id=? LIMIT 1', (identifier,)).fetchone():
            if self.check_migration_in is None:
                raise ApiError('harness_history_requires_migration',
                    'This saved history needs its verified migration before native continuation.', 409)
            self.check_migration_in(conn, identifier)
        for previous in conn.execute('SELECT a.state,r.state AS run_state FROM learn_harness_answers a '
                'JOIN learn_runs r ON r.id=a.run_id WHERE a.thread_id=?', (identifier,)):
            if (previous['state'] not in ('completed', 'failed', 'cancelled') or
                    previous['run_state'] not in ('completed', 'failed', 'cancelled', 'interrupted') or
                    self.publish_answer_in is None or
                    not (self.check_run_dependencies_in or self.check_dependencies_in) or
                    self.eligible_history_in is None or not self.context_filtering or
                    previous['state'] != 'completed' and (self.settle_run is None or self.check_new_run_in is None)):
                raise ApiError('harness_history_requires_lineage',
                    'The retained native history needs verified publication lineage before continuation.', 409)
        run = ActiveRun(durable_id('run'), identifier, ContextScope(kind=Scope.STUDY, entity_id=identifier))
        run.policy_revision, run.context_epoch = require_assistance(conn), context_epoch_in(conn)
        now = utc_now()
        conn.execute('INSERT INTO learn_runs VALUES(?,?,?,?,?,?,?)',
            (run.id, identifier, 'conversation:' + key, 'running', None, now, now))
        conn.execute('INSERT INTO learn_harness_answers(run_id,thread_id,request_digest,state) VALUES(?,?,?,?)',
            (run.id, identifier, canonical_digest(request.model_dump(mode='json')), 'reserved'))
        # Trusted local hook shares this owner transaction; no native IO or
        # in-memory run registration occurs until configuration admission passes.
        if self.admit_run_in is not None:
            self.admit_run_in(conn, run, request)
        self.repo.learn.active[run.id] = run
        self._consumed[run.id] = ((), (), '[]')
        return run

    def _check_dependencies(self, conn, run_id, inputs, dependencies):
        if not inputs and not dependencies:
            return
        if self.check_run_dependencies_in is not None:
            self.check_run_dependencies_in(conn, run_id=run_id, inputs=inputs, dependencies=dependencies)
        elif self.check_dependencies_in is not None:
            self.check_dependencies_in(conn, inputs=inputs, dependencies=dependencies)
        else:
            raise ApiError('harness_dependencies_unavailable', 'Learning dependencies need local validation.', 409)

    def check(self, run_id, *, conn=None):
        entry = self.repo.streaming.active.get(run_id)
        if entry is None:
            raise ApiError('harness_run_unavailable', 'This learning operation is no longer active.', 409)
        with nullcontext(conn) if conn is not None else self.db.transaction() as current:
            self.repo.streaming._guard(current, entry)
            if entry['run'].cancelled.is_set():
                raise ApiError('harness_cancelled', 'The learning operation was stopped.', 409)
            summary, metadata = self.repo._get(current, 'learning', entry['id'])
            if summary['lifecycle'] != 'active' or (summary['revision'], metadata['draft_revision']) != entry['harness_revisions']:
                raise ApiError('conversation_revision_conflict', 'The conversation or draft changed. Retry this request.', 409, True)
            consumed = self._consumed.get(run_id, ((), (), '[]'))
            self._check_dependencies(current, run_id, consumed[0], consumed[1])

    def select_context(self, run_id, *, messages):
        """Local native hook: select identities and consume only trusted eligible history."""
        if not self.context_filtering or self.eligible_history_in is None:
            raise ApiError('harness_history_requires_lineage', 'Native history filtering is unavailable.', 409)
        entry = self.repo.streaming.active.get(run_id)
        with self.db.transaction() as conn:
            self.check(run_id, conn=conn)
            row = conn.execute('SELECT input_id FROM learn_harness_answers WHERE run_id=?', (run_id,)).fetchone()
            current_id = row['input_id']
            if not isinstance(messages, list) or any(not isinstance(item, dict) for item in messages):
                raise ApiError('harness_context_conflict', 'The native context descriptors are invalid.', 409)
            descriptors = [(item.get('id'), item.get('role')) for item in messages
                if isinstance(item.get('id'), str) and item['id'] and item.get('role') in ('user', 'assistant', 'tool')]
            positions = [index for index, (identifier, role) in enumerate(descriptors) if identifier == current_id]
            if len(positions) != 1 or descriptors[positions[0]][1] != 'user':
                raise ApiError('harness_input_conflict', 'The pinned current native input is absent or changed.', 409)
            boundary = positions[0]
            suffix = descriptors[boundary:]
            if any(role == 'user' and identifier != current_id for identifier, role in suffix):
                raise ApiError('harness_context_conflict', 'The current native turn changed.', 409)
            references = tuple({**json.loads(previous['reference_json']), 'publication_digest': previous['publication_digest']}
                for previous in conn.execute("SELECT reference_json,publication_digest FROM learn_harness_answers "
                    "WHERE thread_id=? AND state='completed' AND run_id!=?", (entry['id'], run_id)))
            project = entry.get('project')
            pins = self.eligible_history_in(conn, references=references,
                project_id=project['project_id'] if project else None)
            by_evidence = {'learn-answer:' + reference['run_id']: reference for reference in references}
            prior_roles = {}
            for identifier, role in descriptors[:boundary]:
                prior_roles.setdefault(identifier, set()).add(role)
            allowed, inputs, dependencies = set(identifier for identifier, _ in suffix), [], []
            for value in pins:
                pin = EligibleInput.model_validate(value)
                reference = by_evidence.get(pin.dependency.target.id)
                if (pin.kind != 'committed_evidence' or pin.dependency.target.type != 'learning_evidence' or
                        reference is None or pin.dependency.expected_revision != reference['publication_digest']):
                    raise ApiError('harness_context_conflict', 'History eligibility returned an unbound receipt.', 409)
                if (prior_roles.get(reference['input_id']) != {'user'} or not reference['message_ids'] or
                        any(not prior_roles.get(identifier) or not prior_roles[identifier] <= {'assistant', 'tool'}
                            for identifier in reference['message_ids'])):
                    continue
                allowed.update((reference['input_id'], *reference['message_ids']))
                inputs.append(pin)
                inputs.extend(EligibleInput.model_validate(item) for item in reference['inputs'])
                dependencies.extend(Dependency.model_validate(item) for item in reference['dependencies'])
        self.record_consumed(run_id, inputs=inputs, dependencies=dependencies)
        return list(dict.fromkeys(identifier for identifier, _ in descriptors if identifier in allowed))

    def record_consumed(self, run_id, *, inputs=(), dependencies=(), citations=()):
        """Trusted domain callback only; model/tool argument text is never lineage."""
        self.check(run_id)
        old_inputs, old_dependencies, old_citations = self._consumed.get(run_id, ((), (), '[]'))
        inputs = tuple(EligibleInput.model_validate(value) for value in inputs)
        dependencies = tuple(Dependency.model_validate(value) for value in dependencies)
        merged = {}
        for dependency in (*old_dependencies, *dependencies,
                           *(value.dependency for value in (*old_inputs, *inputs))):
            previous = merged.get(dependency.target.key)
            if previous is not None and previous != dependency:
                raise ApiError('harness_dependency_conflict', 'A consumed dependency changed revision.', 409)
            merged[dependency.target.key] = dependency
        unique_inputs = tuple(dict.fromkeys((*old_inputs, *inputs)))
        refs = json.loads(old_citations)
        for citation in citations:
            if citation not in refs:
                refs.append(citation)
        self._consumed[run_id] = (unique_inputs, tuple(merged.values()),
            json.dumps(refs, sort_keys=True, ensure_ascii=False, allow_nan=False))
        self.check(run_id)
        self._checkpoint(self.repo.streaming.active[run_id])

    def _checkpoint(self, entry):
        """Reference-only admission and trusted closure survive lost IPC replies."""
        run_id = entry['run'].id
        inputs, dependencies, citations = self._consumed.get(run_id, ((), (), '[]'))
        snapshot = {'version': 1, 'kind': 'pending', 'configuration_id': self.configuration_id,
            'policy': entry['policy'], 'epoch': entry['epoch'],
            'revisions': list(entry['harness_revisions']), 'request_id': entry['key'],
            'request_fields': entry['request'].model_dump(mode='json', exclude={'text', 'images'}),
            'request_digest': canonical_digest(entry['request'].model_dump(mode='json')),
            'input_sha256': hashlib.sha256(entry['request'].text.encode('utf-8')).hexdigest(),
            'project_digest': canonical_digest(entry.get('project')),
            'inputs': [item.model_dump(mode='json') for item in inputs],
            'dependencies': [item.model_dump(mode='json') for item in dependencies],
            'citations': [{key: value for key, value in item.items()
                if key in {'content_ref', 'passage_id', 'document_id', 'revision_id', 'locator', 'locators'}}
                for item in json.loads(citations)]}
        with self.db.transaction() as conn:
            self.check(run_id, conn=conn)
            conn.execute("UPDATE learn_harness_answers SET reference_json=? WHERE run_id=? AND state!='completed'",
                (json.dumps(snapshot, sort_keys=True, ensure_ascii=False, allow_nan=False), run_id))

    def bind_input(self, run_id, *, session_id, input_id, attempt_id='1'):
        """Parent-only native admission callback; no transport inside this write."""
        entry = self.repo.streaming.active.get(run_id)
        if entry is None or attempt_id != '1' or entry.get('harness_runtime') is None or (
                entry['harness_runtime'].session_id != session_id):
            raise ApiError('harness_input_conflict', 'The native input belongs to different work.', 409)
        with self.db.transaction() as conn:
            self.check(run_id, conn=conn)
            row = conn.execute('SELECT input_id,state FROM learn_harness_answers WHERE run_id=?', (run_id,)).fetchone()
            if row['state'] != 'uncertain' or row['input_id'] not in (None, input_id):
                raise ApiError('harness_input_conflict', 'The admitted native input changed.', 409)
            conn.execute('UPDATE learn_harness_answers SET input_id=? WHERE run_id=?', (input_id, run_id))

    def mapping(self, identifier):
        with self.db.transaction() as conn:
            require_assistance(conn)
            summary, _ = self.repo._get(conn, 'learning', identifier)
            row = conn.execute('SELECT mapping_json FROM learn_harness_mappings WHERE thread_id=?', (identifier,)).fetchone()
            if row is None or row['mapping_json'] is None:
                return None
            mapping = SavedConversationMapping.model_validate_json(row['mapping_json'])
            checked = map_saved_conversation(Conversation.model_validate(summary), mapping.runtime, manifest=self._manifest())
            if mapping != checked:
                raise ApiError('harness_mapping_conflict', 'The saved runtime mapping changed.', 409)
            return mapping.model_dump(mode='json')

    def completed(self, run_id):
        with self.db.transaction() as conn:
            require_assistance(conn)
            row = conn.execute('SELECT * FROM learn_harness_answers WHERE run_id=?', (run_id,)).fetchone()
            if row is None or row['state'] != 'completed':
                return None
            self.repo._get(conn, 'learning', row['thread_id'])
            return {**json.loads(row['reference_json']), 'publication_digest': row['publication_digest']}

    async def _request(self, command, payload, run_id, *, pending=None, guard=True):
        if guard:
            self.check(run_id)
        manifest = self._manifest()
        response = await self.transport.request(command, payload, run_id, '1', 1)
        expected = HarnessCommandIdentity(protocol='renulus-harness/1', profile_id=manifest.profile_id,
            store_id=manifest.runtime_store.store_id, generation=response['generation'],
            operation_id=run_id, attempt_id='1', request_id=response['request_id'])
        if pending is not None:
            pending(response)  # short local write; the transport wait already finished
        while True:
            checked = validate_command_outcome({key: value for key, value in response.items()
                if key in {'kind', 'outcome', 'result', 'error', *HarnessCommandIdentity.model_fields}}, expected=expected)
            if checked.outcome != 'accepted_pending':
                break
            await asyncio.sleep(self.poll_interval)
            if guard:
                self.check(run_id)
            response = await self.transport.query_result(expected.request_id)
        release = getattr(self.transport, 'release_observation', None)
        if command in OBSERVATION_COMMANDS and release is not None:
            await release(expected.request_id)
        if guard:
            self.check(run_id)
        if checked.outcome not in ('committed_reference', 'cancelled_settled') or checked.error:
            if command == 'session.messages' and checked.error and checked.error.code == 'reply_too_large':
                raise ApiError('harness_history_reply_too_large', 'This native history page exceeds the transport frame limit.', 409, True)
            raise ApiError('harness_command_uncertain' if checked.outcome == 'uncertain_after_disconnect' else 'harness_command_rejected',
                'The native operation could not be confirmed. It will not be sent again automatically.', 409, True)
        return checked.result

    async def _session(self, entry):
        identifier, run_id = entry['id'], entry['run'].id
        mapped = self.mapping(identifier)
        if mapped is not None:
            return HarnessEngineReference.model_validate(mapped['runtime'])
        manifest = self._manifest()
        with self.db.transaction() as conn:
            self.check(run_id, conn=conn)
            if conn.execute('SELECT 1 FROM learn_harness_mappings WHERE thread_id=?', (identifier,)).fetchone():
                raise ApiError('harness_mapping_uncertain', 'Reconcile the pending native session before continuing.', 409, True)
            conn.execute('INSERT INTO learn_harness_mappings(thread_id,profile_id,store_id) VALUES(?,?,?)',
                (identifier, manifest.profile_id, manifest.runtime_store.store_id))
        def pending(response):
            self.db.execute('UPDATE learn_harness_mappings SET create_request_id=?,process_generation=? WHERE thread_id=?',
                (response['request_id'], response['generation'], identifier))
        result = await self._request('session.create', {'title': entry['receipt']['conversation']['title']}, run_id, pending=pending)
        runtime = HarnessEngineReference(contract_version='harness/1', profile_id=manifest.profile_id,
            store_id=manifest.runtime_store.store_id, engine=manifest.runtime_store.engine, session_id=result['session']['id'])
        with self.db.transaction() as conn:
            self.check(run_id, conn=conn)
            summary, _ = self.repo._get(conn, 'learning', identifier)
            mapping = map_saved_conversation(Conversation.model_validate(summary), runtime, manifest=self._manifest())
            conn.execute('UPDATE learn_harness_mappings SET session_id=?,mapping_json=? WHERE thread_id=? AND session_id IS NULL',
                (runtime.session_id, mapping.model_dump_json(), identifier))
        return runtime

    async def _native_messages(self, session_id, run_id, *, guard=True):
        messages, cursor, cursors = [], None, set()
        page_limit = 200
        while True:
            payload = {'session_id': session_id, 'limit': page_limit}
            payload.update({'cursor': cursor} if cursor else {'order': 'asc'})
            try:
                result = await self._request('session.messages', payload, run_id, guard=guard)
            except ApiError as error:
                if error.code != 'harness_history_reply_too_large' or page_limit == 1:
                    raise
                # Only an oversized read retries, at its unchanged native cursor.
                # No uncertain create/prompt is ever routed through this path.
                page_limit = max(1, page_limit // 2)
                continue
            messages.extend(result['messages'])
            cursor = result.get('cursor')
            if isinstance(cursor, dict):
                cursor = cursor.get('next')
            if not cursor:
                return messages
            if cursor in cursors or len(messages) >= 10000:
                raise ApiError('harness_history_unavailable', 'Native history could not be read completely.', 409, True)
            cursors.add(cursor)

    async def answer(self, entry):
        run_id = entry['run'].id
        sequence = 0
        def event(kind, payload=None):
            nonlocal sequence
            sequence += 1
            return Event(run_id=run_id, sequence=sequence, type=kind, payload=payload or {})
        try:
            self.check(run_id)
            self._checkpoint(entry)
            yield event('started', {'thread_id': entry['id'], 'scope': 'study'})
            entry['harness_native_started'] = True
            runtime = await self._session(entry)
            entry['harness_runtime'] = runtime
            with self.db.transaction() as conn:
                self.check(run_id, conn=conn)
                row = conn.execute('SELECT state FROM learn_harness_answers WHERE run_id=?', (run_id,)).fetchone()
                if row['state'] != 'reserved':
                    raise ApiError('harness_submission_uncertain', 'Reconcile this native input before continuing.', 409, True)
                conn.execute("UPDATE learn_harness_answers SET state='uncertain' WHERE run_id=?", (run_id,))
            def pending(response):
                self.db.execute('UPDATE learn_harness_answers SET command_request_id=?,process_generation=? WHERE run_id=?',
                    (response['request_id'], response['generation'], run_id))
            prompt = {'session_id': runtime.session_id,
                'configuration_id': self.configuration_id, 'text': entry['request'].text}
            if entry['request'].images:
                prompt['images'] = [image.model_dump(mode='json') for image in entry['request'].images]
            result = await self._request('session.prompt', prompt, run_id, pending=pending)
            if (result['sessionId'], result['operationId'], result['attemptId']) != (runtime.session_id, run_id, '1'):
                raise ApiError('harness_input_conflict', 'The native input belongs to different work.', 409)
            input_id = result['inputId']
            with self.db.transaction() as conn:
                self.check(run_id, conn=conn)
                pinned = conn.execute('SELECT input_id FROM learn_harness_answers WHERE run_id=?', (run_id,)).fetchone()[0]
                if pinned not in (None, input_id):
                    raise ApiError('harness_input_conflict', 'The admitted native input changed.', 409)
                conn.execute("UPDATE learn_harness_answers SET state='submitted',input_id=? WHERE run_id=?", (input_id, run_id))
            seen_tools = set()
            terminal_observed = False
            yield event('progress', {'stage': 'native-execution'})
            while True:
                messages = await self._native_messages(runtime.session_id, run_id)
                observed = await self._request('session.get', {'session_id': runtime.session_id}, run_id)
                selected, found = [], False
                for message in messages:
                    if message['id'] == input_id:
                        if message['type'] != 'user' or any(message.get('metadata', {}).get(key) != value
                                for key, value in {'operationId': run_id, 'attemptId': '1',
                                    'configurationId': self.configuration_id}.items()):
                            raise ApiError('harness_input_conflict', 'The delivered native input changed.', 409)
                        found = True
                        continue
                    if found and message['type'] == 'user':
                        break
                    if found and message['type'] == 'assistant':
                        selected.append(message)
                        for part in message.get('content', []):
                            if part['type'] == 'tool':
                                key = (part['id'], part['state']['status'])
                                if key not in seen_tools:
                                    self.check(run_id)
                                    seen_tools.add(key)
                                    yield event('tool', {'tool_call_id': part['id'], 'name': part['name'], 'state': part['state']['status']})
                outcome = observed['session'].get('outcome')
                # A delivered input was promoted by the native drain. Only
                # actual ownership/claim settlement can make its outcome final;
                # timestamps and completed assistant steps are not that proof.
                if outcome in ('succeeded', 'failed', 'interrupted') and found and observed.get('execution') == 'settled':
                    if terminal_observed:
                        break
                    # The message page above may predate a terminal transition
                    # observed just now. Read the final transcript after that
                    # proof before constructing its immutable reference.
                    terminal_observed = True
                else:
                    terminal_observed = False
                await asyncio.sleep(self.poll_interval)
            if outcome != 'succeeded':
                raise ApiError('harness_execution_interrupted' if outcome == 'interrupted' else 'harness_execution_failed',
                    'The native explanation did not complete.', 409, True)
            text = ''.join(part['text'] for message in selected for part in message.get('content', []) if part['type'] == 'text')
            if not text or not selected or not selected[-1].get('time', {}).get('completed') or selected[-1].get('error'):
                raise ApiError('harness_answer_incomplete', 'The native completed answer is unavailable.', 409, True)
            inputs, dependencies, citations = self._consumed.get(run_id, ((), (), '[]'))
            answer = CompletedAnswer(run_id, entry['id'], runtime, input_id,
                tuple(message['id'] for message in selected), text, hashlib.sha256(text.encode('utf-8')).hexdigest(),
                citations, inputs, dependencies)
            self.check(run_id)
            entry['harness_answer'] = answer
            yield event('sources', {'citations': answer.citations, 'verification': 'retrieved' if answer.citations else 'not-verified'})
            self.check(run_id)
            yield event('delta', {'text': answer.text})
            self.check(run_id)
            yield event('completed', {'thread_id': entry['id'], 'citations': answer.citations, 'answer_reference': answer.reference()})
        except asyncio.CancelledError:
            await self.cancel(run_id)
            raise
        except Exception as error:
            cancelled = entry['run'].cancelled.is_set()
            if isinstance(error, ApiError) and error.code in {'harness_execution_failed', 'harness_execution_interrupted'}:
                with self.db.transaction() as conn:
                    self.check(run_id, conn=conn)
                    conn.execute("UPDATE learn_harness_answers SET state=? WHERE run_id=? AND state='submitted'",
                        ('cancelled' if error.code == 'harness_execution_interrupted' else 'failed', run_id))
            elif not isinstance(error, ApiError) or error.code != 'harness_command_uncertain':
                await self.cancel(run_id)
            if cancelled:
                yield event('cancelled')
            else:
                yield event('error', {'code': error.code if isinstance(error, ApiError) else 'harness_answer_failed',
                    'message': error.message if isinstance(error, ApiError) else 'The native explanation could not finish.', 'retryable': True})
        finally:
            if self.settle_run is not None:
                await self.settle_run(entry)
            self.repo.learn.active.pop(run_id, None)
            self._consumed.pop(run_id, None)

    def publish_in(self, conn, entry):
        self.check(entry['run'].id, conn=conn)
        answer = entry['harness_answer']
        row = conn.execute('SELECT * FROM learn_harness_answers WHERE run_id=?', (answer.run_id,)).fetchone()
        reference = json.dumps(answer.reference(), sort_keys=True, ensure_ascii=False, allow_nan=False)
        if row['request_digest'] != canonical_digest(entry['request'].model_dump(mode='json')):
            raise ApiError('idempotency_conflict', 'This request key belongs to different work.', 409)
        if row['state'] == 'completed':
            if row['reference_json'] != reference:
                raise ApiError('harness_answer_conflict', 'The immutable completed answer changed.', 409)
            return json.loads(row['reference_json'])
        if row['state'] != 'submitted' or row['input_id'] != answer.input_id:
            raise ApiError('harness_answer_conflict', 'The completed input does not match its admitted receipt.', 409)
        mapping = conn.execute('SELECT mapping_json FROM learn_harness_mappings WHERE thread_id=?', (answer.thread_id,)).fetchone()
        summary, _ = self.repo._get(conn, 'learning', answer.thread_id)
        expected = map_saved_conversation(Conversation.model_validate(summary), answer.runtime, manifest=self._manifest())
        if mapping is None or mapping['mapping_json'] is None or SavedConversationMapping.model_validate_json(mapping['mapping_json']) != expected:
            raise ApiError('harness_answer_conflict', 'The completed answer belongs to another runtime.', 409)
        # Lineage sees the proved immutable native references in this same write.
        # Any callback failure rolls this staging and its local effects back.
        conn.execute('UPDATE learn_harness_answers SET reference_json=? WHERE run_id=?', (reference, answer.run_id))
        publication = self.publish_answer_in(conn, answer, entry) if self.publish_answer_in else canonical_digest(answer.reference())
        conn.execute("UPDATE learn_harness_answers SET state='completed',reference_json=?,publication_digest=? WHERE run_id=?",
            (reference, publication, answer.run_id))
        now = utc_now()
        conn.execute("UPDATE learn_runs SET state='completed',updated_at=? WHERE id=? AND state='running'", (now, answer.run_id))
        conn.execute('UPDATE learn_threads SET updated_at=? WHERE id=?', (now, answer.thread_id))
        return answer.reference()

    async def cancel(self, run_id):
        entry = self.repo.streaming.active.get(run_id)
        if entry is not None and self.cancel_run is not None:
            self.cancel_run(entry)
        if entry is not None and not entry.get('harness_native_started'):
            # This producer has not crossed the synchronous marker before
            # native session creation. Retire only its untouched reservation;
            # a lost create acknowledgement may lack a runtime, but has already
            # crossed that marker and must keep its uncertain ownership.
            with self.db.transaction() as conn:
                conn.execute("UPDATE learn_harness_answers SET state='cancelled' WHERE run_id=? "
                    "AND state='reserved' AND input_id IS NULL AND command_request_id IS NULL "
                    "AND process_generation IS NULL", (run_id,))
        if entry is None or 'harness_runtime' not in entry:
            return {'state': 'not-submitted'}
        if 'harness_cancel_task' not in entry:
            entry['harness_cancel_task'] = asyncio.create_task(self._request('session.cancel',
                {'session_id': entry['harness_runtime'].session_id}, run_id, guard=False))
        result = await asyncio.shield(entry['harness_cancel_task'])
        if entry['run'].cancelled.is_set():
            self.db.execute("UPDATE learn_harness_answers SET state='cancelled' WHERE run_id=? AND state!='completed'", (run_id,))
        return result

    async def resolve_completed(self, run_id):
        """Resolve immutable bytes before a caller enters its publication transaction."""
        reference = self.completed(run_id)
        if reference is None:
            raise ApiError('harness_answer_unavailable', 'The completed native answer is unavailable.', 409)
        mapping = self.mapping(reference['thread_id'])
        if mapping is None or mapping['runtime'] != reference['runtime']:
            raise ApiError('harness_answer_conflict', 'The completed answer belongs to another runtime.', 409)
        messages = await self._native_messages(reference['runtime']['session_id'], run_id, guard=False)
        text = self._completed_text(reference, messages)
        if self.completed(run_id) != reference:
            raise ApiError('harness_answer_conflict', 'The immutable completed answer changed.', 409)
        return CompletedAnswer(run_id, reference['thread_id'], HarnessEngineReference.model_validate(reference['runtime']),
            reference['input_id'], tuple(reference['message_ids']), text, reference['sha256'],
            json.dumps(reference['citations'], sort_keys=True, ensure_ascii=False, allow_nan=False),
            tuple(EligibleInput.model_validate(item) for item in reference['inputs']),
            tuple(Dependency.model_validate(item) for item in reference['dependencies']))

    @staticmethod
    def _completed_text(reference, messages):
        by_id = {message['id']: message for message in messages}
        selected = [by_id.get(identifier) for identifier in reference['message_ids']]
        if (reference['input_id'] not in by_id or not selected or
                any(message is None or message['type'] != 'assistant' or message.get('error') or
                    not message.get('time', {}).get('completed') for message in selected)):
            raise ApiError('harness_answer_unavailable', 'The immutable native message range is unavailable.', 409)
        text = ''.join(part['text'] for message in selected for part in message['content'] if part['type'] == 'text')
        if hashlib.sha256(text.encode('utf-8')).hexdigest() != reference['sha256']:
            raise ApiError('harness_answer_conflict', 'The immutable completed answer changed.', 409)
        return text

    def _recovery_state(self, conn, run_id):
        row = conn.execute('SELECT * FROM learn_harness_answers WHERE run_id=?', (run_id,)).fetchone()
        if row is None or row['state'] in ('completed', 'cancelled', 'failed'):
            return None
        run = conn.execute('SELECT state FROM learn_runs WHERE id=?', (run_id,)).fetchone()
        if run is None or run['state'] == 'cancelled':
            return None
        snapshot = json.loads(row['reference_json'] or '{}')
        if snapshot.get('kind') != 'pending' or snapshot.get('version') != 1:
            raise ApiError('harness_reconciliation_unavailable', 'This operation lacks trusted recovery references.', 409)
        command = conn.execute("SELECT * FROM conversation_commands WHERE operation='send' AND target_type='learn_thread' "
            "AND target_id=? AND json_extract(result_json,'$.run_id')=?", (row['thread_id'], run_id)).fetchone()
        if command is None:
            raise ApiError('harness_reconciliation_unavailable', 'The admitted command is unavailable.', 409)
        receipt = json.loads(command['result_json'])
        if receipt['state'] == 'cancelled' or command['idempotency_key'] != snapshot['request_id']:
            raise ApiError('harness_reconciliation_conflict', 'The admitted receipt changed.', 409)
        require_assistance(conn, expected_revision=snapshot['policy'])
        summary, metadata = self.repo._get(conn, 'learning', row['thread_id'])
        if (context_epoch_in(conn) != snapshot['epoch'] or summary['lifecycle'] != 'active' or
                metadata['draft_revision'] != snapshot['revisions'][1] or
                summary['revision'] != receipt['conversation']['revision'] or
                summary['revision'] not in (snapshot['revisions'][0], snapshot['revisions'][0] + 1)):
            raise ApiError('harness_reconciliation_stale', 'The original learning admission is no longer current.', 409)
        projects = self.repo.services.registry.get('projects')
        project = projects.context_in(conn, 'learning', row['thread_id']) if projects else None
        if canonical_digest(project) != snapshot['project_digest'] or row['request_digest'] != snapshot['request_digest']:
            raise ApiError('harness_reconciliation_stale', 'The original learning admission changed.', 409)
        inputs = tuple(EligibleInput.model_validate(item) for item in snapshot['inputs'])
        dependencies = tuple(Dependency.model_validate(item) for item in snapshot['dependencies'])
        self._check_dependencies(conn, run_id, inputs, dependencies)
        return dict(row), snapshot, dict(command), receipt, summary, project, inputs, dependencies

    async def reconcile_pending(self, identifier):
        with self.db.transaction() as conn:
            require_assistance(conn)
            self.repo._get(conn, 'learning', identifier)
            run_ids = [row['run_id'] for row in conn.execute(
                "SELECT run_id FROM learn_harness_answers WHERE thread_id=? AND state IN ('reserved','uncertain','submitted')", (identifier,))]
        for run_id in run_ids:
            if run_id in self.repo.streaming.active:
                continue
            task = self._reconciling.get(run_id)
            if task is None:
                task = asyncio.create_task(self.reconcile(run_id))
                self._reconciling[run_id] = task
                task.add_done_callback(lambda completed, key=run_id: self._reconciling.pop(key, None))
            await asyncio.shield(task)

    async def reconcile(self, run_id):
        """Observe an existing native effect. No create, prompt or recovery command."""
        with self.db.transaction() as conn:
            state = self._recovery_state(conn, run_id)
            if state is None or run_id in self.repo.streaming.active:
                return {'state': 'unchanged'}
            row, snapshot, command, receipt, summary, project, inputs, dependencies = state
            mapping_row = conn.execute('SELECT * FROM learn_harness_mappings WHERE thread_id=?', (row['thread_id'],)).fetchone()
            if mapping_row is None:
                raise ApiError('harness_mapping_uncertain', 'The reserved native mapping is unavailable.', 409)
            manifest = self._manifest()
            if (mapping_row['profile_id'], mapping_row['store_id']) != (manifest.profile_id, manifest.runtime_store.store_id):
                raise ApiError('harness_mapping_conflict', 'The native store selection changed.', 409)
            session_id = mapping_row['session_id']
        if session_id is None:
            result = await self._request('session.find', {}, run_id, guard=False)
            sessions = result['sessions']
            if not sessions:
                return {'state': 'not-found'}
            metadata = sessions[0].get('metadata', {})
            if len(sessions) != 1 or any(metadata.get(key) != value for key, value in {
                    'renulusProfile': manifest.profile_id, 'renulusStore': manifest.runtime_store.store_id,
                    'operationId': run_id}.items()):
                raise ApiError('harness_mapping_conflict', 'The recovered native session is ambiguous.', 409)
            session_id = sessions[0]['id']
        runtime = HarnessEngineReference(contract_version='harness/1', profile_id=manifest.profile_id,
            store_id=manifest.runtime_store.store_id, engine=manifest.runtime_store.engine, session_id=session_id)
        native = await self._native_messages(session_id, run_id, guard=False)
        observed = await self._request('session.get', {'session_id': session_id}, run_id, guard=False)
        if observed['session']['id'] != session_id:
            raise ApiError('harness_mapping_conflict', 'The observed native session changed.', 409)
        if observed.get('execution') == 'settled':
            native = await self._native_messages(session_id, run_id, guard=False)
        matching = [message for message in native if message['type'] == 'user' and
            message.get('metadata', {}).get('operationId') == run_id and
            message.get('metadata', {}).get('attemptId') == '1' and
            message.get('metadata', {}).get('configurationId') == snapshot['configuration_id']]
        if len(matching) > 1 or (matching and row['input_id'] not in (None, matching[0]['id'])):
            raise ApiError('harness_input_conflict', 'The recovered input is ambiguous or changed.', 409)
        selected = []
        if matching:
            found = False
            for message in native:
                if message['id'] == matching[0]['id']:
                    found = True
                    continue
                if found and message['type'] == 'user':
                    break
                if found and message['type'] == 'assistant':
                    selected.append(message)
            text = ''.join(part['text'] for message in selected for part in message.get('content', []) if part['type'] == 'text')
            files = matching[0].get('files') or []
            if not isinstance(files, list) or len(files) > 4 or any(
                    not isinstance(file, dict) or file.get('source') != {'type': 'inline'} for file in files):
                raise ApiError('harness_input_conflict', 'The recovered inline files changed.', 409)
            try:
                request = Send(text=matching[0]['text'], **snapshot['request_fields'],
                    **({'images': tuple({'type': 'image', 'media_type': file['mime'], 'data': file['data']}
                        for file in files)} if files else {}))
            except (KeyError, TypeError, ValueError):
                raise ApiError('harness_input_conflict', 'The recovered inline files changed.', 409) from None
            if (canonical_digest(request.model_dump(mode='json')) != row['request_digest'] or
                    hashlib.sha256(request.text.encode('utf-8')).hexdigest() != snapshot['input_sha256']):
                raise ApiError('harness_input_conflict', 'The recovered input differs from the admitted request.', 409)
        with self.db.transaction() as conn:
            current = self._recovery_state(conn, run_id)
            if current is None:
                return {'state': 'unchanged'}
            if current[:4] != state[:4] or self._manifest() != manifest or run_id in self.repo.streaming.active:
                raise ApiError('harness_reconciliation_conflict', 'The pending operation changed during lookup.', 409)
            checked_mapping = map_saved_conversation(Conversation.model_validate(current[4]), runtime, manifest=manifest)
            current_mapping = conn.execute('SELECT * FROM learn_harness_mappings WHERE thread_id=?', (row['thread_id'],)).fetchone()
            if current_mapping is None or dict(current_mapping) != dict(mapping_row):
                raise ApiError('harness_mapping_conflict', 'The native mapping changed during lookup.', 409)
            conn.execute('UPDATE learn_harness_mappings SET session_id=?,mapping_json=? WHERE thread_id=?',
                (session_id, checked_mapping.model_dump_json(), row['thread_id']))
            outcome = observed['session'].get('outcome')
            if not matching or observed.get('execution') != 'settled' or outcome not in {'succeeded', 'failed', 'interrupted'}:
                return {'state': 'not-submitted' if not matching else 'pending'}
            run = ActiveRun(run_id, row['thread_id'], ContextScope(kind=Scope.STUDY, entity_id=row['thread_id']))
            run.policy_revision, run.context_epoch = snapshot['policy'], snapshot['epoch']
            run.project_id = project['project_id'] if project else None
            entry = {'id': row['thread_id'], 'kind': 'learning', 'saved': True, 'key': snapshot['request_id'],
                'run': run, 'request': request, 'policy': snapshot['policy'], 'epoch': snapshot['epoch'],
                'harness_revisions': (current[4]['revision'], snapshot['revisions'][1]), 'project': project,
                'harness_runtime': runtime, 'receipt': receipt}
            if outcome != 'succeeded':
                error = {'code': 'harness_execution_interrupted' if outcome == 'interrupted' else 'harness_execution_failed',
                    'message': 'The native explanation did not complete.', 'retryable': True}
                conn.execute("UPDATE learn_harness_answers SET state=?,input_id=? WHERE run_id=?",
                    ('cancelled' if outcome == 'interrupted' else 'failed', matching[0]['id'], run_id))
                self.repo.streaming._finish(conn, entry, 'error', error)
                return {'state': 'error', 'error': error}
            if not text or not selected or any(message.get('error') or not message.get('time', {}).get('completed') for message in selected):
                raise ApiError('harness_answer_incomplete', 'The recovered answer is not immutable and complete.', 409)
            answer = CompletedAnswer(run_id, row['thread_id'], runtime, matching[0]['id'],
                tuple(message['id'] for message in selected), text, hashlib.sha256(text.encode('utf-8')).hexdigest(),
                json.dumps(snapshot['citations'], sort_keys=True), inputs, dependencies)
            entry['harness_answer'] = answer
            self.repo.streaming.active[run_id] = entry
            self._consumed[run_id] = (inputs, dependencies, json.dumps(snapshot['citations']))
            try:
                conn.execute("UPDATE learn_harness_answers SET state='submitted',input_id=? WHERE run_id=?", (answer.input_id, run_id))
                self.publish_in(conn, entry)
                self.repo.streaming._finish(conn, entry, 'completed')
                conn.execute("UPDATE learn_runs SET state='completed',error_code=NULL,updated_at=? WHERE id=?", (utc_now(), run_id))
            finally:
                self.repo.streaming.active.pop(run_id, None)
                self._consumed.pop(run_id, None)
        return {'state': 'completed', 'answer_reference': answer.reference()}

    async def messages(self, identifier, limit=50, cursor=None):
        await self.reconcile_pending(identifier)
        mapping = self.mapping(identifier)
        if mapping is None:
            return self.repo.messages('learning', identifier, limit, cursor)
        with self.db.transaction() as conn:
            policy, epoch = require_assistance(conn), context_epoch_in(conn)
            receipts = [dict(row) for row in conn.execute('SELECT * FROM learn_harness_answers WHERE thread_id=? AND input_id IS NOT NULL', (identifier,))]
            legacy = [dict(row) for row in conn.execute(
                'SELECT * FROM learn_messages WHERE thread_id=? ORDER BY created_at,id', (identifier,))]
            if legacy:
                if self.check_migration_in is None:
                    raise ApiError('harness_history_requires_migration',
                        'This saved history needs its verified migration before native continuation.', 409)
                self.check_migration_in(conn, identifier)
                for item in legacy:
                    item['content_refs'] = [citation['content_ref']
                        for citation in json.loads(item.pop('citations_json')) if 'content_ref' in citation]
                    item.pop('thread_id')
        native = await self._native_messages(mapping['runtime']['session_id'], 'history:' + identifier, guard=False)
        with self.db.transaction() as conn:
            require_assistance(conn, expected_revision=policy)
            if context_epoch_in(conn) != epoch:
                raise ApiError('dependency_changed', 'The learning context changed.', 409)
            self.repo._get(conn, 'learning', identifier)
            if legacy:
                self.check_migration_in(conn, identifier)
        by_id = {row['input_id']: row for row in receipts}
        for row in receipts:
            if row['state'] == 'completed':
                reference = json.loads(row['reference_json'])
                self._completed_text(reference, native)
                for message_id in reference['message_ids']:
                    by_id[message_id] = row
        # Imported aliases have unknown lineage. Show original read-only rows
        # through the saved facade; only new receipt-owned native turns append.
        items = legacy
        for message in native:
            receipt = by_id.get(message['id'])
            if receipt is None or message['type'] not in ('user', 'assistant'):
                continue
            content = message['text'] if message['type'] == 'user' else ''.join(part['text'] for part in message['content'] if part['type'] == 'text')
            reference = json.loads(receipt['reference_json']) if receipt['state'] == 'completed' else {}
            items.append({'id': message['id'], 'run_id': receipt['run_id'], 'role': message['type'],
                'content': content, 'created_at': datetime.fromtimestamp(message['time']['created'] / 1000, timezone.utc).isoformat(),
                'content_refs': [citation['content_ref'] for citation in reference.get('citations', [])
                    if message['type'] == 'assistant' and 'content_ref' in citation]})
        scope = ['harness-messages', identifier, mapping['runtime']['session_id']]
        page = self.repo._uncursor(cursor, scope) if cursor else {'after': 0, 'boundary': len(items)}
        end = min(page['after'] + limit, page['boundary'])
        return {'conversation': mapping['conversation'], 'items': items[page['after']:end],
            'next_cursor': self.repo._cursor({'scope': scope, 'after': end, 'boundary': page['boundary']}) if end < page['boundary'] else None}
