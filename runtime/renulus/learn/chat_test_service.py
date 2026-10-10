# SPDX-License-Identifier: MIT
"""Raw Chat/Home input remains memory-only until the trusted fictional boundary."""
import asyncio
import json
from contextlib import closing
from dataclasses import dataclass, field
from time import monotonic

from renulus.contracts import ApiError, durable_id
from renulus.design_c_contracts import canonical_digest
from renulus.storage.assessment_policy import require_assistance
from renulus.storage.invalidation import context_epoch_in

from .chat_test_models import ChatTestRun, ChatTestResult, PublishedChatTest

MAX_RUNS = 40
MAX_ACTIVE = 3
MAX_SOURCE = 32000
RECEIPT_SECONDS = 1800


@dataclass
class VolatileTestRun:
    id: str
    request_id: str = field(repr=False)
    request_hash: str = field(repr=False)
    source_text: str = field(repr=False)
    instruction: str = field(repr=False)
    count: int
    policy: int
    epoch: int
    source: tuple | None = field(default=None, repr=False)
    case_revision: int | None = field(default=None, repr=False)
    state: str = 'queued'
    result: PublishedChatTest | None = None
    error_code: str | None = None
    guard_failed: bool = False
    cancel: asyncio.Event = field(default_factory=asyncio.Event, repr=False)
    expires: float = field(default_factory=lambda: monotonic() + RECEIPT_SECONDS)


class ChatTestService:
    def __init__(self, services):
        self.services, self.db = services, services.db
        self.runs, self.requests, self.tasks = {}, {}, {}
        services.on_shutdown.append(self.close)

    @staticmethod
    def _view(run):
        return ChatTestRun(run_id=run.id, state=run.state).model_dump(mode='json')

    @staticmethod
    def _erase(run):
        run.source_text = run.instruction = ''
        run.source = run.case_revision = None

    def _expire(self):
        for identifier, run in list(self.runs.items()):
            if run.expires <= monotonic():
                run.cancel.set()
                task = self.tasks.get(identifier)
                if task:
                    task.cancel()
                self._erase(run)
                self.requests.pop(run.request_id, None)
                del self.runs[identifier]

    def _replay(self, request_id, digest):
        self._expire()
        identifier = self.requests.get(request_id)
        if identifier:
            run = self.runs[identifier]
            if run.request_hash != digest:
                raise ApiError('idempotency_conflict', 'Use a new request ID for a changed test request', 409)
            return self._view(run)
        return None

    def _start(self, request, digest, text, policy, epoch, *, source=None, case_revision=None):
        if not text.strip():
            raise ApiError('chat_test_input_empty', 'Add learning content before creating a test', 422)
        if len(text) > MAX_SOURCE:
            raise ApiError('chat_test_input_limit', 'This conversation is too long for one test request', 413)
        if len(self.runs) >= MAX_RUNS or len(self.tasks) >= MAX_ACTIVE:
            raise ApiError('chat_test_capacity', 'Finish or cancel an active test request before starting another', 429, True)
        run = VolatileTestRun(durable_id('chat_test_run'), request.request_id, digest, text,
            getattr(request, 'instruction', ''), request.count, policy, epoch, source, case_revision)
        self.runs[run.id] = run
        self.requests[request.request_id] = run.id
        self.tasks[run.id] = asyncio.create_task(self._produce(run))
        return self._view(run)

    def start_draft(self, request):
        with closing(self.db.connect()) as conn:
            policy, epoch = require_assistance(conn), context_epoch_in(conn)
        digest = canonical_digest({'operation': 'quick_practice', 'request': request.model_dump(mode='json')})
        replay = self._replay(request.request_id, digest)
        return replay or self._start(request, digest, request.text, policy, epoch)

    def start_chat(self, kind, identifier, request):
        conversations = self.services.get('conversations')
        with conversations._lock, conversations.cases._lock, self.db.transaction() as conn:
            policy, epoch = require_assistance(conn), context_epoch_in(conn)
            digest = canonical_digest({'operation': 'chat_test', 'kind': kind, 'id': identifier, 'request': request.model_dump(mode='json')})
            replay = self._replay(request.request_id, digest)
            if replay:
                return replay
            summary, metadata = conversations._get(conn, kind, identifier)
            conversations._expected(summary, request.expected_revision)
            if summary['lifecycle'] != 'active':
                raise ApiError('conversation_archived', 'Restore this conversation before creating a test', 409)
            case_revision = None
            if kind == 'case':
                session = conversations.cases._load(identifier)
                conversations.cases._check_idle(session)
                case_revision = session.revision
                messages = conversations.cases._context(session)
            elif summary['retention'] == 'temporary':
                messages = metadata['messages']
            else:
                messages = conn.execute('SELECT role,content FROM learn_messages WHERE thread_id=? ORDER BY created_at,id', (identifier,))
            # Content references, IDs, hidden teaching stages and unsent drafts
            # are not source text. Home raw drafts have their separate typed intent.
            text = '\n\n'.join(message['content'] for message in messages if message['role'] in ('user', 'assistant'))
            return self._start(request, digest, text, policy, epoch,
                source=(kind, identifier, request.expected_revision), case_revision=case_revision)

    def _guard(self, run):
        if run.cancel.is_set():
            raise ApiError('chat_test_cancelled', 'This test request was stopped', 409)
        if run.source:
            conversations = self.services.get('conversations')
            with conversations._lock, conversations.cases._lock, self.db.transaction() as conn:
                require_assistance(conn, expected_revision=run.policy)
                if context_epoch_in(conn) != run.epoch:
                    raise ApiError('dependency_changed', 'The learning context changed. Start a new test request.', 409)
                kind, identifier, revision = run.source
                summary, _ = conversations._get(conn, kind, identifier)
                conversations._expected(summary, revision)
                if kind == 'case':
                    conversations.cases._check_revision(conversations.cases._load(identifier), run.case_revision)
        else:
            with closing(self.db.connect()) as conn:
                require_assistance(conn, expected_revision=run.policy)
                if context_epoch_in(conn) != run.epoch:
                    raise ApiError('dependency_changed', 'The learning context changed. Start a new test request.', 409)

    async def _fictionalise(self, run):
        try:
            from renulus.assessment.fictionalisation import fictionalise_test
        except ImportError:
            raise ApiError('chat_test_unavailable', 'The trusted test preparation service is not ready', 503, True) from None
        return await fictionalise_test(self.services, source_text=run.source_text,
            instruction=run.instruction, count=run.count, cancel=run.cancel,
            expected_policy_revision=run.policy, expected_context_epoch=run.epoch)

    async def _produce(self, run):
        watcher = None
        try:
            self._guard(run)
            run.state = 'running'
            watcher = asyncio.create_task(self._watch_guard(run))
            artifact = await self._fictionalise(run)
            watcher.cancel()
            self._guard(run)
            if len(artifact.questions) != run.count:
                raise ApiError('chat_test_count_mismatch', 'The fictional set does not match the requested count', 409)
            publisher = self.services.get('saved_generation')
            publish = getattr(publisher, 'publish_fictional_artifact', None)
            if not callable(publish):
                raise ApiError('chat_test_unavailable', 'The trusted test publication service is not ready', 503, True)
            # The frozen async publisher commits atomically without yielding
            # between its final guard, durable commit and winning result.
            value = await publish(artifact, expected_policy_revision=run.policy, expected_context_epoch=run.epoch)
            result = PublishedChatTest.model_validate(value)
            if result.item_count != run.count:
                raise ApiError('chat_test_count_mismatch', 'The published set does not match the requested count', 409)
            run.result, run.state = result, 'published'
        except asyncio.CancelledError:
            run.cancel.set()
            run.state = 'failed' if run.guard_failed else 'cancelled'
            if run.guard_failed:
                run.error_code = 'chat_test_failed'
        except Exception as error:
            run.state = 'cancelled' if run.cancel.is_set() and not run.guard_failed else 'failed'
            run.error_code = 'chat_test_unavailable' if isinstance(error, ApiError) and error.code == 'chat_test_unavailable' else 'chat_test_failed'
        finally:
            if watcher:
                watcher.cancel()
                await asyncio.gather(watcher, return_exceptions=True)
            self._erase(run)
            self.tasks.pop(run.id, None)

    async def _watch_guard(self, run):
        while not run.cancel.is_set():
            await asyncio.sleep(0.1)
            try:
                self._guard(run)
            except ApiError:
                # The trusted helper holds this exact event in its opaque
                # receipt. Source loss revokes authority while it is waiting.
                run.guard_failed = True
                run.cancel.set()
                task = self.tasks.get(run.id)
                if task:
                    task.cancel()
                return

    def _run(self, identifier):
        self._expire()
        run = self.runs.get(identifier)
        if run is None:
            raise ApiError('chat_test_run_missing', 'This temporary test request is unavailable. Start a new request.', 404)
        return run

    def status(self, identifier):
        return self._view(self._run(identifier))

    def result(self, identifier):
        run = self._run(identifier)
        with self.db.transaction() as conn:
            require_assistance(conn)
            if run.state != 'published' or run.result is None:
                code = run.error_code or 'chat_test_not_ready'
                raise ApiError(code, 'The fictional test is not ready. Your source has not been saved by this request.', 409, run.state == 'failed')
            value = run.result
            row = conn.execute("SELECT v.test_id,v.items_json FROM assessment_test_versions v JOIN assessment_tests t ON t.id=v.test_id "
                "WHERE v.id=? AND t.lifecycle!='deleted' AND NOT EXISTS(SELECT 1 FROM deletion_ledger d WHERE "
                "(d.entity_type='saved_test_version' AND d.entity_id=v.id) OR (d.entity_type='saved_test' AND d.entity_id=t.id))", (value.version_id,)).fetchone()
            if row is None or row['test_id'] != value.test_id or len(json.loads(row['items_json'])) != run.count:
                raise ApiError('chat_test_result_unavailable', 'The saved fictional test is no longer available', 410)
            return ChatTestResult.model_validate({**value.model_dump(mode='json'), 'study_start': {
                'version': {'type': 'saved_test_version', 'id': value.version_id},
                'mode': 'study', 'timing': {'kind': 'untimed'},
                'idempotency_key': 'chat-test-study-' + canonical_digest({'version': value.version_id})[:48],
            }}).model_dump(mode='json')

    async def cancel(self, identifier):
        run = self._run(identifier)
        if run.state in ('queued', 'running'):
            run.cancel.set()
            run.state = 'cancelled'
            task = self.tasks.get(identifier)
            if task:
                task.cancel()
                await asyncio.wait([task], timeout=2)
            self._erase(run)
        return self._view(run)

    async def close(self):
        tasks = list(self.tasks.values())
        for run in self.runs.values():
            run.cancel.set()
            self._erase(run)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.wait(tasks, timeout=2)
        self.runs.clear()
        self.requests.clear()
