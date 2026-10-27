"""Bounded admission and actual settlement, independent of the pipe reader.

Native engine calls cannot be interrupted safely. Cancel suppresses publication;
the lease remains pending until the function has returned and artifacts unpinned.
"""
from __future__ import annotations

from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import asyncio
from threading import Event, RLock, Thread
import time
import uuid

from renulus.worker_contracts import (CancelledResult, Capacity,
    ErrorResult, LaunchConfig, PendingResult, Reply, Revisions, Settlement,
    StateResult, SUPPORTED_COMMANDS, GenerationRequest, GenerationMessage, SettleTarget,
    command_identity, command_revisions, payload_digest)
from .artifacts import Artifacts, Refused
from .engines import SelectedEngines
from .derived import DerivedEngines, UnsettledEngine
from .broker_models import BrokerLaunch, TransportResult, HttpResult


class Capture:
    """One host-admitted reverse dispatch; cancellation is not settlement."""
    def __init__(self, worker, job):
        self.worker, self.job = worker, job
        self.loop = asyncio.new_event_loop()
        self.thread = Thread(target=self.loop.run_forever, name="renulus-callback", daemon=True)
        self.thread.start()
        self.request = self.response = None
        self.used = False

    def binding(self):
        return {"capture": self, "loop": self.loop}

    def current(self):
        if not self.worker._current(self.job):
            raise Refused("stale_revision")

    def reject(self, error):
        return error

    def cancel(self):
        self.job.cancelled = True

    async def generate(self, messages):
        self.current()
        if self.used:
            raise Refused("invalid_command")
        self.used = True
        command = self.job.command
        request = GenerationRequest(target=SettleTarget(identity=self.job.identity,
            request_sha256=self.job.digest, worker_lease=self.job.lease),
            revisions=command_revisions(command), retention=command.retention, capture_plan=command.input.capture_plan,
            callback_id="callback_" + uuid.uuid4().hex, generation_sha256="0" * 64,
            messages=[GenerationMessage(role=role, content=content) for role, content in messages], action="generate")
        digest = payload_digest(request.model_dump(exclude={"generation_sha256", "callback_id", "action"}))
        request = request.model_copy(update={"generation_sha256": digest})
        if len(request.model_dump_json().encode("utf-8")) + 1 > self.worker.capacity.max_frame_bytes:
            raise Refused("artifact_limit")
        # Publish the binding before sending; a prompt host reply cannot race it.
        with self.worker.lock:
            self.current()
            self.request = request
        self.worker.emit(request)
        cancelled = False
        while self.response is None:
            if self.worker.disconnected:
                self.job.uncertain = True
                raise Refused("worker_closed")
            if not self.worker._current(self.job) and not cancelled:
                cancelled = True
                self.worker.emit(request.model_copy(update={"action": "cancel", "messages": []}))
            await asyncio.sleep(0.01)
        if self.response.status != "completed" or cancelled or not self.worker._current(self.job):
            raise Refused("stale_revision")
        return self.response.output

    def close(self):
        # ApprovedLLM's initiating timeout does not join reverse dispatch. Keep
        # the owning memory thread/lane until its actual host settlement arrives.
        if self.request is not None and self.response is None:
            self.job.cancelled = True
            while self.response is None and not self.worker.disconnected:
                time.sleep(0.01)
            if self.worker.disconnected:
                self.job.uncertain = True
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join()
        self.loop.close()


@dataclass
class Job:
    command: object
    lease: str
    cancelled: bool = False
    settled: bool = False
    started: bool = False
    output: object = None
    input_artifact: object = None
    deadline: float = 0
    identity: object = None
    digest: str = ""
    capture: object = None
    uncertain: bool = False
    broker: object = None
    cancel_signal: object = None


class Worker:
    def __init__(self, config: LaunchConfig, capacity: Capacity, emit, *, engines=None,
                 broker_factory=None, secret_reader=None, native_io=None):
        self.config, self.capacity, self.emit = config, capacity, emit
        self.revisions = config.revisions
        self.artifacts = Artifacts(capacity)
        self.engines = engines if engines is not None else SelectedEngines(config.helpers)
        self.lock = RLock()
        self.closing = False
        self.disconnected = False
        self.derived = DerivedEngines(config, self.engines)
        self.native_io = native_io
        # Python-only protected/test handoffs; neither is a launch/command field.
        # No broker, ProviderManager, DPAPI record or event loop is opened here.
        self.broker_factory, self.secret_reader = broker_factory, secret_reader
        self.credential_broker = self.provider_manager = None
        self.credential_loop = self.credential_thread = self.credential_cleanup = None
        self.brokers = set()
        self.jobs: dict[str, Job] = {}
        self.completed: dict[str, tuple] = {}
        self.seen: set[str] = set()
        self.control_seen = deque(maxlen=capacity.control_slots * 16)
        self.queue = deque()
        self.running = {"document": 0, "embedding": 0, "library": 0, "memory": 0,
                        "transport": 0, "credential": 0}
        self.pool = ThreadPoolExecutor(max_workers=capacity.document_tasks + 2,
                                       thread_name_prefix="renulus-engine")
        self.memory_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="renulus-memory")
        self.broker_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="renulus-broker")

    def _reply(self, command, result, *, outcome="committed_reference", lease=None, state="settled"):
        reply = Reply(identity=command_identity(command), request_sha256=command.payload_sha256,
            revisions=command_revisions(command), outcome=outcome, result=result,
            settlement=Settlement(worker_lease=lease or "lease_" + uuid.uuid4().hex, state=state))
        self.emit(reply)

    def _reject(self, command, code):
        self._reply(command, ErrorResult(code=code, retryable=code in ("overloaded", "helper_unavailable")),
                    outcome="rejected_before_admission")

    def _identity_matches(self, command):
        return all(getattr(command, key) == value
                   for key, value in self.config.identity.model_dump().items())

    def handle(self, command, raw_input):
        """Already schema-validated command. All rejection checks precede effects."""
        with self.lock:
            if not self._identity_matches(command) or command.retention != self.config.retention:
                return self._reject(command, "stale_identity")
            if command_revisions(command) != self.revisions:
                return self._reject(command, "stale_revision")
            if payload_digest(raw_input) != command.payload_sha256:
                return self._reject(command, "digest_mismatch")
            if command.request_id in self.seen or command.request_id in self.control_seen:
                return self._reject(command, "duplicate_request")
            if command.command == "worker.settle":
                self.control_seen.append(command.request_id)
                return self._control(command)
            if len(self.seen) >= self.capacity.request_count:
                return self._reject(command, "overloaded")
            self.seen.add(command.request_id)
            if command.command not in SUPPORTED_COMMANDS:
                return self._reject(command, "unsupported_command")
            if self.closing:
                return self._reject(command, "worker_closed")
            try:
                if command.command == "artifact.upload":
                    result = self.artifacts.upload(command.input, self.revisions)
                    return self._reply(command, result)
                if command.command == "artifact.read":
                    result = self.artifacts.read(command.input, self.revisions,
                                                 command.limits.result_page_bytes)
                    return self._reply(command, result)
                self._admit_engine(command)
            except Refused as error:
                self._reject(command, error.code)

    def _lane(self, job):
        name = job.command.command
        if name.startswith("evidence."):
            return "transport"
        return name.split(".")[0] if name.startswith(("embedding.", "library.", "memory.",
            "transport.", "credential.")) else "document"

    def _lane_available(self, job):
        lane = self._lane(job)
        limit = self.capacity.document_tasks if lane == "document" else 1
        return self.running[lane] < limit and sum(self.running.values()) < self.capacity.data_in_flight

    def _admit_engine(self, command):
        if command.command == 'native.io' and (self.config.native is None or command.retention != 'saved'):
            raise Refused('artifact_denied')
        if command.command in ("transport.execute", "transport.http", "evidence.run"):
            plan = command.input
            if (plan.identity != command_identity(command) or plan.revisions != self.revisions
                    or plan.retention != command.retention):
                raise Refused("stale_identity")
            if self.config.broker is None:
                raise Refused("broker_unavailable")
        elif command.command.startswith("credential.") and self.config.broker is None:
            raise Refused("broker_unavailable")
        job = Job(command, "lease_" + uuid.uuid4().hex,
                  deadline=time.monotonic() + command.limits.cpu_seconds,
                  identity=command_identity(command), digest=command.payload_sha256,
                  cancel_signal=Event())
        # Enforce queue limits before pinning inputs or reserving output bytes.
        active = sum(not value.settled for value in self.jobs.values())
        if (active >= self.capacity.data_in_flight + self.capacity.data_queued
                or (not self._lane_available(job) and len(self.queue) >= self.capacity.data_queued)):
            raise Refused("overloaded")
        # expected_revision belongs to the host's canonical domain. This worker
        # checks explicit artifact_revision pins and never opens that domain DB.
        if (command.command in ("document.extract", "document.chunk", "library.stage", "memory.reconcile", "memory.extract")
                or command.command == 'native.io' and command.input.action in ('publish', 'payload', 'asset')):
            i = command.input
            job.input_artifact = self.artifacts.pin(i.artifact_handle, i.artifact_revision,
                i.offset, i.length, "extract" if command.command == "document.extract" else
                "chunk" if command.command == "document.chunk" else "read",
                self.revisions)
        try:
            if not command.command.startswith("credential."):
                job.output = self.artifacts.reserve_output(command.input.output, self.revisions)
        except Exception:
            if job.input_artifact:
                self.artifacts.unpin(job.input_artifact)
            raise
        self.jobs[command.request_id] = job
        self._reply(command, PendingResult(), outcome="accepted_pending", lease=job.lease, state="pending")
        self.queue.append(job)
        self._schedule()

    def _current(self, job):
        command = job.command
        return (not job.cancelled and not self.closing and time.monotonic() <= job.deadline
            and command is not None and command_revisions(command) == self.revisions
            and (command.command.startswith("credential.") or
                 (job.output is not None and not job.output.retiring
                  and job.output.grant.expires_at_ms > int(time.time() * 1000)))
            and (job.input_artifact is None or (not job.input_artifact.retiring
                 and job.input_artifact.grant.expires_at_ms > int(time.time() * 1000)))
            and (not hasattr(command.input, "capture_plan") or
                 command.input.capture_plan.expires_at_ms > int(time.time() * 1000))
            and (command.command not in ("transport.execute", "transport.http", "evidence.run") or
                 command.input.expires_at_ms > int(time.time() * 1000)))

    def _schedule(self):
        for job in list(self.queue):
            if not self._lane_available(job):
                continue
            self.queue.remove(job)
            job.started = True
            self.running[self._lane(job)] += 1
            lane = self._lane(job)
            pool = (self.memory_pool if lane == "memory" else
                    self.broker_pool if lane in ("transport", "credential") else self.pool)
            pool.submit(self._run, job)

    def _broker(self, plan=None):
        from .broker import ProtectedBroker
        paths = self.config.broker
        if paths is None:
            raise Refused("broker_unavailable")
        launch = BrokerLaunch(identity=self.config.identity, revisions=self.revisions,
            retention=self.config.retention, profile_root=paths.profile_root,
            state_root=paths.state_root, bounds=paths.bounds,
            native_manifest_sha256=plan.native_manifest_sha256 if plan else "0" * 64,
            registry_sha256=plan.registry_sha256 if plan else "0" * 64)
        broker = (self.broker_factory or ProtectedBroker)(launch, manager=self.provider_manager)
        self.brokers.add(broker)
        return broker

    async def _credential(self, job):
        from .broker import BrokerRefused
        command = job.command
        with self.lock:
            if not self._current(job):
                raise Refused("stale_revision")
            if self.credential_broker is None:
                self.credential_broker = self._broker()
            broker = job.broker = self.credential_broker
        current = lambda: self._current(job)
        try:
            if command.command == "credential.activate":
                self.provider_manager = broker.activate_credentials(check_current=current)
                return broker.credential_metadata()
            if self.provider_manager is None:
                raise Refused("broker_not_activated")
            if command.command == "credential.metadata":
                return broker.credential_metadata()
            i = command.input
            authority = i.authority
            if (authority.identity != command_identity(command)
                    or authority.revisions != command_revisions(command)
                    or authority.retention != command.retention):
                raise Refused("credential_authority_invalid")
            # Captured immutable host authority, independent of this command's
            # Job, which is erased after the connect reply. Callback lifetime
            # ends on host revoke/close/expiry or actual listener settlement.
            def login_current():
                with self.lock:
                    return (not self.closing and not self.disconnected
                        and authority.revisions == self.revisions)
            secret_reader = self.secret_reader
            if secret_reader is None:
                from .native_secret import read_go_secret
                secret_reader = read_go_secret
            return await broker.credential_command(command.command.split(".", 1)[1], i.provider_id,
                authority=authority, check_current=current, login_current=login_current,
                publication_lock=self.lock, login_id=getattr(i, "login_id", None),
                secret_reader=secret_reader if command.command == "credential.connect"
                    and i.provider_id == "opencode-go" else None)
        except BrokerRefused as error:
            code = error.code if error.code in ErrorResult.model_fields["code"].annotation.__args__ else "credential_command_failed"
            raise Refused(code) from None

    def _credentials(self, job):
        # Login listeners and credential locks belong to one persistent loop.
        # A new asyncio.run per command would kill the explicit OAuth callback.
        with self.lock:
            if self.credential_loop is None:
                self.credential_loop = asyncio.new_event_loop()
                self.credential_thread = Thread(target=self.credential_loop.run_forever,
                    name="renulus-credentials", daemon=True)
                self.credential_thread.start()
        return asyncio.run_coroutine_threadsafe(self._credential(job), self.credential_loop).result()

    def _transport(self, job):
        plan = job.command.input
        with self.lock:
            if not self._current(job):
                raise Refused("stale_revision")
            broker = job.broker = self._broker(plan)
        execution = broker.execute_sync(plan, check_current=lambda: self._current(job),
                                        cancel=job.cancel_signal)
        result = execution.result
        # Exact broker metadata binds the admitted plan and existing reservation.
        # Never put execution.body or HTTP headers into the reply JSON.
        if (not isinstance(result, TransportResult) or result.identity != plan.identity
                or result.revisions != plan.revisions or result.request_sha256 != plan.request_sha256
                or result.admission_receipt != plan.admission_receipt):
            raise Refused("engine_failed")
        if result.outcome == "committed_reference":
            with self.lock:
                if not self._current(job):
                    return self._fence_transport(result)
                if len(execution.body) > job.output.reservation:
                    raise Refused("artifact_limit")
                with self.artifacts.lock:
                    job.output.body.extend(execution.body)
                    job.output.engine = "protected-http:1"
                    if self.artifacts.reference(job.output) != result.artifact:
                        raise Refused("artifact_invalid")
        elif execution.body or result.artifact is not None:
            raise Refused("artifact_invalid")
        return result

    def _capability(self, job):
        plan = job.command.input
        with self.lock:
            if not self._current(job):
                raise Refused("stale_revision")
            broker = job.broker = self._broker()
        execute = broker.execute_http if job.command.command == "transport.http" else broker.execute_evidence
        execution = asyncio.run(execute(plan, check_current=lambda: self._current(job), cancel=job.cancel_signal))
        result = execution.result
        if (not isinstance(result, HttpResult) or result.identity != plan.identity
                or result.revisions != plan.revisions or result.admission_receipt != plan.admission_receipt):
            raise Refused("engine_failed")
        if result.outcome == "committed_reference":
            with self.lock:
                if not self._current(job):
                    return self._fence_transport(result)
                if len(execution.body) > job.output.reservation:
                    raise Refused("artifact_limit")
                with self.artifacts.lock:
                    job.output.body.extend(execution.body)
                    job.output.engine = "protected-http:1"
                    if self.artifacts.reference(job.output) != result.artifact:
                        raise Refused("artifact_invalid")
        elif execution.body or result.artifact is not None:
            raise Refused("artifact_invalid")
        return result

    def _fence_transport(self, result):
        if isinstance(result, HttpResult):
            return result.model_copy(update={"outcome": "cancelled_settled", "artifact": None,
                "headers": (), "code": "stale_revision"})
        return result.model_copy(update={"outcome": "cancelled_settled", "artifact": None,
            "content_type": None, "code": "stale_revision"})

    def _active(self):
        return max(sum(not j.settled for j in self.jobs.values()), int(
            self.credential_cleanup is not None and not self.credential_cleanup.done()))

    def _close_credentials(self):
        if self.credential_loop is not None and self.provider_manager is not None:
            if self.credential_cleanup is None or self.credential_cleanup.done():
                async def cleanup():
                    owner = getattr(self.provider_manager, "_worker_credential_owner", None)
                    if owner is not None:
                        await owner.close()
                    await self.provider_manager.close()
                self.credential_cleanup = asyncio.run_coroutine_threadsafe(cleanup(), self.credential_loop)

    def _run(self, job):
        command = job.command
        result, failure = None, None
        try:
            if not job.cancelled and time.monotonic() <= job.deadline:
                i = command.input
                if command.command == "transport.execute":
                    result = self._transport(job)
                elif command.command in ("transport.http", "evidence.run"):
                    result = self._capability(job)
                elif command.command.startswith("credential."):
                    result = self._credentials(job)
                elif command.command == 'native.io':
                    if self.native_io is None:
                        from .knowledge_io import KnowledgeIO
                        # Native initialization is lazy, serialized by the worker
                        # lock; it creates no canonical connection or services.
                        with self.lock:
                            if self.native_io is None:
                                self.native_io = KnowledgeIO(self.config.native)
                    body = bytes(job.input_artifact.body[i.offset:i.offset + i.length]) if job.input_artifact else None
                    value = self.native_io.execute(i, body, lambda: self._current(job), self.lock)
                    engine = 'windows-knowledge-io:1'
                    if isinstance(value, bytes):
                        if len(value) > job.output.reservation:
                            raise Refused('artifact_limit')
                        job.output.body.extend(value)
                        job.output.engine = engine
                        result = self.artifacts.reference(job.output)
                elif command.command == "embedding.embed":
                    value = self.engines.embed(i.texts, query=i.query)
                    engine = "fastembed:0.8.1"
                elif command.command.startswith(("library.", "memory.")):
                    body = bytes(job.input_artifact.body[i.offset:i.offset + i.length]) if job.input_artifact else None
                    if command.command == "memory.extract":
                        job.capture = Capture(self, job)
                    value = self.derived.execute(command, body, lambda: self._current(job), job.capture)
                    engine = "lancedb:0.39.0" if command.command.startswith("library.") else "mem0ai:2.2.1/qdrant-client:1.19.1"
                else:
                    body = bytes(job.input_artifact.body[i.offset:i.offset + i.length])
                    if command.command == "document.extract":
                        value = self.engines.extract(body, format=i.format, title=i.title,
                                                     retention=command.retention)
                    else:
                        value = self.engines.chunk(body)
                    engine = "docling:2.133.0/docling-core:2.99.0"
                # Serialization is outside the control lock. Output remains invisible
                # to read until completion and the final authority/cancel checks.
                if not command.command.startswith(("transport.", "evidence.", "credential.")) and result is None:
                    result = self.artifacts.publish(job.output, value, engine=engine)
        except Refused as error:
            failure = error.code
        except UnsettledEngine:
            # A failed native constructor leaves this lane/lease owned. Only
            # process teardown can establish native death for the host; Stop is
            # not a false successful close acknowledgement.
            job.uncertain = True
            while not self.disconnected:
                time.sleep(0.05)
            failure = "engine_failed"
        except Exception as error:
            # Never reflect dependency messages, paths, source contents or traceback.
            code = getattr(error, "code", "")
            failure = "helper_unavailable" if code.startswith(("helper_", "unsafe_helper", "incompatible_embedding")) else "engine_failed"
        finally:
            if job.capture:
                job.capture.close()
                job.capture = None
            with self.lock:
                expired = time.monotonic() > job.deadline
                stale = command_revisions(command) != self.revisions
                cancelled = job.cancelled or stale or self.closing or not self._current(job)
                if job.input_artifact is not None:
                    self.artifacts.unpin(job.input_artifact)
                    job.input_artifact = None
                if isinstance(result, (TransportResult, HttpResult)):
                    if cancelled and result.outcome == "committed_reference":
                        result = self._fence_transport(result)
                    if result.outcome == "committed_reference":
                        job.output.complete = True
                        self.artifacts.unpin(job.output)
                    else:
                        self._release_output(job)
                    # The broker reports actual local settlement even when a
                    # remote effect/debit remains uncertain. Preserve that fact.
                    self._reply(command, result, outcome=result.outcome, lease=job.lease)
                elif cancelled or expired or failure or result is None:
                    self._release_output(job)
                    final = ErrorResult(code=failure or "deadline_exceeded") if failure or expired else CancelledResult()
                    self._reply(command, final,
                        outcome="uncertain_after_disconnect" if job.uncertain else "cancelled_settled",
                        state="uncertain" if job.uncertain else "settled", lease=job.lease)
                else:
                    if job.output is not None:
                        job.output.complete = True
                        self.artifacts.unpin(job.output)
                    self._reply(command, result, lease=job.lease)
                if job.broker is not None and command.command in ("transport.execute", "transport.http", "evidence.run"):
                    job.broker.close()
                    self.brokers.discard(job.broker)
                    job.broker = None
                if command.command.startswith("credential.") and (cancelled or failure):
                    self._close_credentials()
                job.settled = True
                self.running[self._lane(job)] -= 1
                self._forget_job(job)
                self._schedule()

    def _release_output(self, job):
        if job.output is not None:
            try:
                self.artifacts.release(job.output.grant.artifact_handle)
                self.artifacts.unpin(job.output)
            except Refused:
                pass
            job.output = None

    def _target(self, target):
        if target is None:
            raise Refused("stale_target")
        job = self.jobs.get(target.identity.request_id)
        if job is None:
            completed = self.completed.get(target.identity.request_id)
            if completed == (target.identity, target.request_sha256, target.worker_lease):
                return None  # Exact settled lease, with no retained payload.
        if (job is None or command_identity(job.command) != target.identity
                or job.command.payload_sha256 != target.request_sha256 or job.lease != target.worker_lease):
            raise Refused("stale_target")
        return job

    def _cancel(self, job):
        if job is None:
            return
        job.cancelled = True
        if job.cancel_signal is not None:
            job.cancel_signal.set()
        if job.broker is not None and job.command.command in ("transport.execute", "transport.http", "evidence.run"):
            job.broker.cancel(job.command.input.permit_id)
        elif job.command.command.startswith("credential."):
            self._close_credentials()
        if not job.started and not job.settled:
            self.queue.remove(job)
            if job.input_artifact:
                self.artifacts.unpin(job.input_artifact)
                job.input_artifact = None
            self._release_output(job)
            job.settled = True
            self._reply(job.command, CancelledResult(), outcome="cancelled_settled", lease=job.lease)
            self._forget_job(job)

    def _forget_job(self, job):
        self.completed[job.identity.request_id] = (job.identity, job.digest, job.lease)
        self.jobs.pop(job.identity.request_id)
        job.command = None  # No completed command text/input retained in lease history.
        job.output = None
        job.broker = None

    def _control(self, command):
        i = command.input
        try:
            if i.action == "generation":
                if i.revisions is not None or i.artifact_handle is not None or i.generation is None:
                    raise Refused("invalid_command")
                job = self._target(i.target)
                capture = job.capture if job else None
                request = capture.request if capture else None
                response = i.generation
                if (request is None or capture.response is not None
                        or response.callback_id != request.callback_id
                        or response.plan_id != request.capture_plan.plan_id
                        or response.generation_sha256 != request.generation_sha256):
                    raise Refused("stale_target")
                if ((response.status == "completed") != (response.output is not None)):
                    raise Refused("invalid_command")
                capture.response = response
                return self._reply(command, StateResult(active=len(self.jobs), closing=self.closing),
                    outcome="accepted_pending", lease=job.lease, state="pending")
            if i.generation is not None:
                raise Refused("invalid_command")
            # Control slots are reserved by the dedicated reader and priority writer;
            # control never queues behind the engine thread pool.
            if i.action in ("query", "cancel"):
                if i.revisions is not None or i.artifact_handle is not None:
                    raise Refused("invalid_command")
                if i.target is None and i.action == "query":
                    job = None
                else:
                    job = self._target(i.target)
                if i.action == "cancel":
                    self._cancel(job)
                active = self._active()
                pending = (job is not None and not job.settled) or (i.target is None and active > 0)
                return self._reply(command, StateResult(active=active,
                    closing=self.closing), outcome="accepted_pending" if pending else "committed_reference",
                    lease=job.lease if job else (i.target.worker_lease if i.target else None),
                    state="pending" if pending else "settled")
            if i.target is not None:
                raise Refused("invalid_command")
            if i.action == "revoke":
                if i.revisions is None or i.artifact_handle is not None:
                    raise Refused("invalid_command")
                if any(getattr(i.revisions, k) < getattr(self.revisions, k) for k in Revisions.model_fields):
                    raise Refused("stale_revision")
                self.revisions = i.revisions
                for broker in self.brokers:
                    broker.revoke(i.revisions)
                for job in list(self.jobs.values()):
                    if not job.settled:
                        self._cancel(job)
                self.artifacts.discard()
                self._close_credentials()
            elif i.action == "release":
                if i.artifact_handle is None or i.revisions is not None:
                    raise Refused("invalid_command")
                self.artifacts.release(i.artifact_handle)
            elif i.action == "close":
                if i.revisions is not None or i.artifact_handle is not None:
                    raise Refused("invalid_command")
                self.closing = True
                for broker in self.brokers:
                    broker.close()
                for job in list(self.jobs.values()):
                    if not job.settled:
                        self._cancel(job)
                self.artifacts.discard()
                self._close_credentials()
            active = self._active()
            self._reply(command, StateResult(active=active, closing=self.closing),
                outcome="accepted_pending" if active else "committed_reference",
                state="pending" if active else "settled")
        except Refused as error:
            self._reject(command, error.code)

    def disconnect(self):
        with self.lock:
            self.closing = True
            self.disconnected = True
            for broker in self.brokers:
                broker.close()
            # EOF means the owning host died, not a saved renderer observer detach.
            for job in list(self.jobs.values()):
                if not job.settled:
                    self._cancel(job)
            self.artifacts.discard()
            self._close_credentials()
        self.pool.shutdown(wait=True, cancel_futures=False)
        self.memory_pool.shutdown(wait=True, cancel_futures=False)
        self.broker_pool.shutdown(wait=True, cancel_futures=False)
        if self.native_io is not None:
            self.native_io.close()
        # Explicit login listeners and background expiry tasks share this scope;
        # release their loop only after credential jobs and real cleanup return.
        self._close_credentials()
        if self.credential_cleanup is not None:
            self.credential_cleanup.result()
        if self.credential_loop is not None:
            self.credential_loop.call_soon_threadsafe(self.credential_loop.stop)
            self.credential_thread.join()
            self.credential_loop.close()
            self.credential_loop = self.credential_thread = None
        self.brokers.clear()
        self.artifacts.discard()
