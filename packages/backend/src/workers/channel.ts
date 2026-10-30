// SPDX-License-Identifier: MIT
import { createHash, randomUUID } from "node:crypto";
import type { Readable, Writable } from "node:stream";
import { canonicalJson, decodeWorkerFrame } from "../contracts/worker-codec.ts";
import type { Capacity, GenerationRequest, Identity, ProcessIdentity, Ready, Reply, Revisions, WorkerCommand } from "../../../contracts/worker.ts";

export type WorkerGenerationResult = { readonly status: "completed"; readonly output: string } |
  { readonly status: "cancelled" | "failed"; readonly output: null };
/** Trusted host dispatch only. Resolve/reject after actual generation settlement,
 * including after signal abort; abort acceptance alone must not settle this promise.
 * The host checks current dispatch/evidence authority before admitting inference.
 */
export type WorkerGenerationHandler = (request: GenerationRequest, signal: AbortSignal) => Promise<WorkerGenerationResult>;

type Generation = {
  request: GenerationRequest; controller: AbortController; started: boolean;
  result?: WorkerGenerationResult; delivering: boolean;
};

export interface WorkerObservation { readonly reply: Reply; readonly current: boolean }
export interface WorkerCall {
  readonly requestId: string;
  readonly admission: Promise<WorkerObservation>;
  /** Data engine settlement, not an observer timeout or cancel acknowledgement. */
  readonly terminal: Promise<WorkerObservation>;
}
type Pending = {
  command: WorkerCommand; control: boolean;
  first: (reply: WorkerObservation) => void; finish: (reply: WorkerObservation) => void;
  rejectFirst: (error: Error) => void; rejectTerminal: (error: Error) => void;
  admission: Promise<WorkerObservation>; terminal: Promise<WorkerObservation>;
  observed?: Reply; settled: boolean; generation?: Generation;
};
const identityKeys = ["profile_id", "domain_store_id", "runtime_store_id", "authority_epoch", "process_generation"] as const;
const requestIdentityKeys = [...identityKeys, "operation_id", "attempt_id", "request_id"] as const;
const revisionsOf = (command: WorkerCommand): Revisions => ({ configuration: command.configuration_revision,
  grant: command.grant_revision, context: command.context_epoch, deletion: command.deletion_epoch,
  cancellation: command.cancellation_epoch });

/** Private inherited-pipe client. Callers supply host-resolved identity/epochs.
 * The same generated JSON Schema validates commands and replies in Python/TS.
 */
export class WorkerChannel {
  private buffer = Buffer.alloc(0);
  private readonly pending = new Map<string, Pending>();
  private readonly readyPromise: Promise<Ready>;
  private acceptReady!: (ready: Ready) => void;
  private rejectReady!: (error: Error) => void;
  private readyValue?: Ready & { capacity: Required<Capacity> };
  private failure?: Error;
  private workerRevisions: Revisions;
  private closed = false;
  private dataCount = 0;
  private readonly onData = (chunk: Buffer) => this.receive(chunk);
  private readonly onEnd = () => this.disconnect("worker_disconnected_uncertain");
  private readonly read: Readable;
  private readonly write: Writable;
  private readonly identity: ProcessIdentity;
  private readonly pid: number;
  private readonly requested: Required<Capacity>;
  private readonly current: () => Revisions;
  private readonly retention: "saved" | "temporary";
  private readonly generate?: WorkerGenerationHandler;

  constructor(read: Readable, write: Writable, identity: ProcessIdentity, pid: number,
    requested: Required<Capacity>, current: () => Revisions, retention: "saved" | "temporary",
    generate?: WorkerGenerationHandler) {
    this.read = read; this.write = write; this.identity = identity; this.pid = pid;
    this.requested = requested; this.current = current; this.retention = retention;
    this.generate = generate;
    this.workerRevisions = structuredClone(current());
    this.readyPromise = new Promise((resolve, reject) => { this.acceptReady = resolve; this.rejectReady = reject; });
    void this.readyPromise.catch(() => {});
    read.on("data", this.onData); read.once("end", this.onEnd); read.once("error", this.onEnd);
    write.once("error", this.onEnd);
  }

  async hello(token: string): Promise<Ready> {
    const frame = decodeWorkerFrame({ protocol: "renulus-worker/1", kind: "hello", launch_token: token,
      expected_launcher_pid: this.pid, identity: this.identity, capacity: this.requested });
    await this.send(frame);
    return this.readyPromise;
  }

  private async send(value: unknown) {
    if (this.failure || this.closed) throw this.failure ?? new Error("worker_closed");
    const bytes = Buffer.from(canonicalJson(value) + "\n");
    if (bytes.length > this.requested.max_frame_bytes) throw new Error("worker_frame_too_large");
    await new Promise<void>((resolve, reject) => this.write.write(bytes, error => error ? reject(error) : resolve()));
  }

  submit(command: WorkerCommand["command"], input: unknown, binding: Pick<Identity, "operation_id" | "attempt_id">,
    expectedRevision: string | null = null): WorkerCall {
    return this.submitBound(command, () => input, binding, expectedRevision);
  }

  /** Trusted application seam for plans bound to the channel-minted request.
   * Factories receive identity/revision snapshots before digesting and validation;
   * callers cannot supply or replace a wire request ID.
   */
  submitBound(command: WorkerCommand["command"], factory: (identity: Identity, revisions: Revisions) => unknown,
    binding: Pick<Identity, "operation_id" | "attempt_id">, expectedRevision: string | null = null): WorkerCall {
    if (!this.readyValue || this.failure || this.closed) throw this.failure ?? new Error("worker_not_ready");
    if (command === "memory.extract" && !this.generate) throw new Error("worker_generation_handler_required");
    const control = command === "worker.settle";
    if (!control && canonicalJson(this.workerRevisions) !== canonicalJson(this.current())) throw new Error("worker_revocation_pending");
    const revision = structuredClone(control ? this.workerRevisions : this.current());
    const active = [...this.pending.values()].filter(entry => !entry.settled && entry.control === control).length;
    const capacity = this.readyValue.capacity;
    if (active >= (control ? capacity.control_slots : capacity.data_in_flight + capacity.data_queued) ||
        !control && this.dataCount >= capacity.request_count ||
        this.pending.size >= capacity.request_count + capacity.control_slots) throw new Error("worker_overloaded");
    const requestId = "request_" + randomUUID().replaceAll("-", "");
    const identity = { ...this.identity, ...binding, request_id: requestId };
    const input = factory(structuredClone(identity), structuredClone(revision));
    const frame = decodeWorkerFrame({ ...identity,
      protocol: "renulus-worker/1", kind: "command", command, input, expected_revision: expectedRevision,
      payload_sha256: createHash("sha256").update(canonicalJson(input)).digest("hex"),
      configuration_revision: revision.configuration, grant_revision: revision.grant, context_epoch: revision.context,
      deletion_epoch: revision.deletion, cancellation_epoch: revision.cancellation, retention: this.retention,
      limits: { result_page_bytes: capacity.max_chunk_bytes, cpu_seconds: 120 } }) as WorkerCommand;
    let first!: Pending["first"], finish!: Pending["finish"], rejectFirst!: Pending["rejectFirst"], rejectTerminal!: Pending["rejectTerminal"];
    const admission = new Promise<WorkerObservation>((resolve, reject) => { first = resolve; rejectFirst = reject; });
    const terminal = new Promise<WorkerObservation>((resolve, reject) => { finish = resolve; rejectTerminal = reject; });
    // A caller may observe only admission. Unobserved settlement failure is still
    // retained in state, without an unhandled rejection or implicit retry.
    void admission.catch(() => {}); void terminal.catch(() => {});
    this.pending.set(requestId, { command: frame, control, first, finish, rejectFirst, rejectTerminal,
      admission, terminal, settled: false });
    if (!control) this.dataCount++;
    void this.send(frame).catch(() => this.disconnect("worker_send_uncertain"));
    return { requestId, admission, terminal };
  }

  private receive(chunk: Buffer) {
    if (this.failure || this.closed) return;
    // Consume complete frames before retaining the final bounded partial frame.
    // A chunk can contain several valid frames, so limit each frame, not chunk.
    let start = 0;
    for (;;) {
      const end = chunk.indexOf(10, start);
      const bytes = chunk.subarray(start, end < 0 ? chunk.length : end + 1);
      if (this.buffer.length + bytes.length > this.requested.max_frame_bytes) return this.disconnect("worker_frame_too_large");
      this.buffer = Buffer.concat([this.buffer, bytes]);
      if (end < 0) return;
      let frame;
      try { frame = decodeWorkerFrame(JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(this.buffer))); }
      catch { return this.disconnect("worker_invalid_frame"); }
      this.buffer = Buffer.alloc(0);
      if (frame.protocol !== "renulus-worker/1") return this.disconnect("worker_protocol_mismatch");
      if (frame.kind === "ready") {
        if (this.readyValue || frame.process.launcher_pid !== this.pid || frame.process.actual_pid !== frame.pid ||
            (frame.pid === this.pid ? frame.process.ancestry_depth !== 0 : frame.process.ancestry_depth < 1) ||
            BigInt(frame.process.launcher_creation_filetime) <= 0n ||
            BigInt(frame.process.actual_creation_filetime) < BigInt(frame.process.launcher_creation_filetime) ||
            !identityKeys.every(key => frame.identity[key] === this.identity[key]) ||
            !Object.keys(this.requested).every(key => typeof frame.capacity[key as keyof Capacity] === "number") ||
            Object.entries(frame.capacity).some(([key, value]) => value > this.requested[key as keyof Capacity]))
          return this.disconnect("worker_handshake_mismatch");
        this.readyValue = frame as Ready & { capacity: Required<Capacity> }; this.acceptReady(frame);
      } else if (frame.kind === "generation_request" && this.readyValue) {
        if (!this.receiveGeneration(frame)) return this.disconnect("worker_generation_mismatch");
      } else if (frame.kind === "reply" && this.readyValue) {
        const pending = this.pending.get(frame.identity.request_id);
        if (!pending || pending.settled || frame.request_sha256 !== pending.command.payload_sha256 ||
            pending.observed && frame.settlement.worker_lease !== pending.observed.settlement.worker_lease ||
            !requestIdentityKeys.every(key =>
              frame.identity[key as keyof Identity] === pending.command[key as keyof WorkerCommand]) ||
            canonicalJson(frame.revisions) !== canonicalJson(revisionsOf(pending.command)) ||
            pending.generation && (frame.settlement.worker_lease !== pending.generation.request.target.worker_lease ||
              frame.settlement.state === "settled" && !pending.generation.delivering))
          return this.disconnect("worker_reply_mismatch");
        const observation = { reply: frame, current: canonicalJson(frame.revisions) === canonicalJson(this.current()) };
        pending.first(observation); pending.observed = frame;
        if (frame.settlement.state === "settled" || pending.control) {
          pending.settled = true; pending.finish(observation);
        }
        if (pending.generation) this.startGeneration(pending);
        this.pumpGenerations();
      } else return this.disconnect("worker_unexpected_frame");
      start = end + 1;
      if (start === chunk.length) return;
    }
  }

  private receiveGeneration(frame: GenerationRequest): boolean {
    const pending = this.pending.get(frame.target.identity.request_id);
    if (!pending || pending.settled || pending.command.command !== "memory.extract" || !this.generate ||
        !requestIdentityKeys.every(key => frame.target.identity[key] === pending.command[key]) ||
        frame.target.request_sha256 !== pending.command.payload_sha256 || frame.retention !== pending.command.retention ||
        canonicalJson(frame.revisions) !== canonicalJson(revisionsOf(pending.command)) ||
        canonicalJson(frame.capture_plan) !== canonicalJson(pending.command.input.capture_plan) ||
        pending.observed && (pending.observed.outcome !== "accepted_pending" || pending.observed.settlement.state !== "pending" ||
          pending.observed.settlement.worker_lease !== frame.target.worker_lease)) return false;
    if (frame.action === "cancel") {
      const generation = pending.generation;
      if (!generation || canonicalJson(frame) !== canonicalJson({ ...generation.request, action: "cancel", messages: [] })) return false;
      // Signal cancellation independently; keep the original promise and lease
      // until the host reports actual closure, even if cancellation is immediate.
      generation.controller.abort();
      return true;
    }
    const { generation_sha256, callback_id: _callback, action: _action, ...payload } = frame;
    if (pending.generation || createHash("sha256").update(canonicalJson(payload)).digest("hex") !== generation_sha256) return false;
    pending.generation = { request: frame, controller: new AbortController(), started: false, delivering: false };
    // The reserved reverse lane can overtake the data admission reply. Retain
    // one request, but do not dispatch until that reply proves the exact lease.
    this.startGeneration(pending);
    return true;
  }

  private startGeneration(pending: Pending) {
    const generation = pending.generation!;
    if (generation.started || !pending.observed || this.failure) return;
    generation.started = true;
    void Promise.resolve().then(() => {
      if (generation.controller.signal.aborted || generation.request.capture_plan.expires_at_ms <= Date.now() ||
          canonicalJson(generation.request.revisions) !== canonicalJson(this.current()))
        return { status: "cancelled", output: null } as const;
      // Give the host its own copy; callback code cannot rewrite the retained
      // target, plan or digest used to deliver settlement.
      return this.generate!(structuredClone(generation.request), generation.controller.signal);
    }).catch(() => ({ status: "failed", output: null }) as const).then(result => {
      generation.result = result;
      this.pumpGenerations();
    });
  }

  /** Bounded reverse settlements share reserved controls, never the data budget.
   * Full controls or an unacknowledged revocation defer delivery, not ownership.
   */
  private pumpGenerations() {
    if (this.failure || !this.readyValue || canonicalJson(this.workerRevisions) !== canonicalJson(this.current())) return;
    for (const pending of this.pending.values()) {
      const generation = pending.generation;
      if (!generation?.result || generation.delivering) continue;
      let call: WorkerCall;
      try {
        const request = generation.request;
        const result = generation.result;
        if (result.status !== "completed" && result.status !== "cancelled" && result.status !== "failed" ||
            (result.status === "completed" ? typeof result.output !== "string" : result.output !== null))
          throw new Error("worker_generation_result_invalid");
        call = this.submit("worker.settle", { action: "generation", target: request.target, generation: {
          callback_id: request.callback_id, plan_id: request.capture_plan.plan_id,
          generation_sha256: request.generation_sha256, status: result.status, output: result.output,
        } }, { operation_id: pending.command.operation_id, attempt_id: pending.command.attempt_id });
      } catch (error) {
        if (error instanceof Error && error.message === "worker_overloaded") return;
        this.disconnect("worker_generation_settlement_uncertain"); return;
      }
      generation.delivering = true;
      void call.admission.then(observation => {
        if (observation.reply.outcome !== "accepted_pending" && observation.reply.outcome !== "committed_reference") {
          this.disconnect("worker_generation_settlement_held"); return;
        }
        this.release(call.requestId);
      }, () => {});
    }
  }

  observe(requestId: string): WorkerObservation | undefined {
    const reply = this.pending.get(requestId)?.observed;
    return reply ? { reply, current: canonicalJson(reply.revisions) === canonicalJson(this.current()) } : undefined;
  }

  /** Propagate already-committed host revocation using the worker's old control
   * epoch. New data stays closed until this acknowledgement; old results remain
   * observable for settlement but are marked ineligible for publication.
   */
  async revoke(binding: Pick<Identity, "operation_id" | "attempt_id">) {
    const revisions = structuredClone(this.current());
    const call = this.submit("worker.settle", { action: "revoke", target: null,
      revisions, artifact_handle: null }, binding);
    const result = await call.admission;
    if (result.reply.outcome !== "committed_reference" && result.reply.outcome !== "accepted_pending")
      throw new Error("worker_revocation_held");
    this.workerRevisions = revisions;
    this.release(call.requestId);
    return result;
  }

  release(requestId: string) {
    const pending = this.pending.get(requestId);
    if (!pending?.settled) throw new Error("worker_settlement_pending");
    this.pending.delete(requestId);
    this.pumpGenerations();
  }

  /** Close admission in the worker first. No EOF while an engine or its host
   * callback still owns work: EOF during reverse inference means host death.
   */
  async drain() {
    await Promise.all([...this.pending.values()].filter(entry => !entry.control).map(entry => entry.terminal));
  }

  state() { return { connected: !this.failure && !this.closed, retained: this.pending.size,
    unsettled: [...this.pending.values()].filter(entry => !entry.settled).length,
    uncertainty: this.failure?.message ?? null }; }

  disconnect(code = "worker_disconnected_uncertain") {
    if (this.failure) return;
    this.failure = new Error(code); this.rejectReady(this.failure);
    for (const pending of this.pending.values()) if (!pending.settled) {
      pending.generation?.controller.abort();
      pending.rejectFirst(this.failure); pending.rejectTerminal(this.failure);
    }
    // Outstanding leases remain in pending; process death/worker settlement is a
    // separate owned-process decision. Disconnection never releases those leases.
    this.read.off("data", this.onData); this.buffer = Buffer.alloc(0);
  }
}
