// SPDX-License-Identifier: MIT
import { randomUUID } from 'node:crypto';
import type { CapturePlan, GenerationRequest } from '../../../contracts/worker.ts';
import type { WorkerChannel, WorkerGenerationHandler, WorkerGenerationResult } from '../workers/channel.ts';
import { createEngineArtifacts } from '../workers/artifacts.ts';
import { canonical, digest } from '../storage/schema.ts';
import { exact, reject, text } from '../storage/contracts.ts';
import { memoryEngineId } from '../domain/memory/contracts.ts';
import type { CaptureTicket, FactKind, MemoryCommand, MemoryEngine, MemoryRecord, MemoryScope, MemoryStorage, MemoryVector } from '../domain/memory/contracts.ts';

/** Adapter to the selected Mem0/Qdrant worker. Worker text is never authority:
 * recall returns immutable references which the writer re-resolves afresh. */
export function createWorkerMemory(channel: WorkerChannel, maxChunkBytes: number): MemoryEngine {
  const artifacts = createEngineArtifacts(channel, maxChunkBytes);
  const binding = () => ({ operation_id: 'memory_' + randomUUID().replaceAll('-', ''), attempt_id: 'attempt_' + randomUUID().replaceAll('-', '') });
  async function output(command: 'memory.recall' | 'memory.purge' | 'memory.reconcile' | 'memory.extract', input: Record<string, unknown>, b: ReturnType<typeof binding>, signal?: AbortSignal) {
    const grant = artifacts.output(512 * 1024, Date.now() + 120_000);
    try {
      const ref = await artifacts.run(command, { ...input, output: grant } as never, b, signal);
      return JSON.parse((await artifacts.read(ref, grant.max_bytes, b, signal)).toString('utf8')) as Record<string, unknown>;
    } finally { await artifacts.release(grant.artifact_handle, b); }
  }
  async function body(command: 'memory.extract' | 'memory.reconcile', bytes: Buffer, input: Record<string, unknown>, b: ReturnType<typeof binding>, signal?: AbortSignal) {
    const grant = await artifacts.upload(bytes, b, ['read'], Date.now() + 120_000, signal);
    try { return await output(command, { ...input, artifact_handle: grant.artifact_handle, artifact_revision: grant.artifact_revision, offset: 0, length: bytes.length }, b, signal); }
    finally { await artifacts.release(grant.artifact_handle, b); }
  }
  return {
    async extract(input) {
      const result = await body('memory.extract', Buffer.from(input.text), { capture_plan: input.plan }, { operation_id: input.operationId, attempt_id: input.attemptId }, input.signal);
      exact(result, ['tag', 'facts', 'capture_plan', 'eligible']);
      if (result.tag !== 'memory_extracted' || result.eligible !== false || canonical(result.capture_plan) !== canonical(input.plan) || !Array.isArray(result.facts) || result.facts.length > 12) reject('memory_engine_result_invalid');
      result.facts.forEach(f => text(f, 1, 2000)); return result.facts as string[];
    },
    async reconcile(records, signal) {
      const references: MemoryVector[] = [];
      for (let offset = 0; offset < records.length; offset += 128) {
        const batch = records.slice(offset, offset + 128), physical = batch.map(r => ({ ...r, id: memoryEngineId(r.id, r.revision) }));
        const result = await body('memory.reconcile', Buffer.from(canonical({ records: physical })), {}, binding(), signal);
        exact(result, ['tag', 'references', 'eligible']);
        if (result.tag !== 'memory_reconciled' || result.eligible !== false || !Array.isArray(result.references) || result.references.length !== batch.length) reject('memory_engine_result_invalid');
        for (const ref of result.references) {
          exact(ref, ['canonical_id', 'canonical_revision', 'engine_id']);
          const canonicalRecord = batch.find(r => memoryEngineId(r.id, r.revision) === ref.canonical_id && r.revision === ref.canonical_revision);
          if (!canonicalRecord) reject('memory_engine_result_invalid'); text(ref.engine_id, 1, 256);
          references.push({ canonical_id: canonicalRecord.id, canonical_revision: canonicalRecord.revision, engine_id: ref.engine_id });
        }
      }
      return references;
    },
    async recall(query, accepted, limit, signal) {
      if (accepted.length > 256) reject('memory_scope_capacity');
      const result = await output('memory.recall', { query, accepted: accepted.map(r => ({ ...r, canonical_id: memoryEngineId(r.canonical_id, r.canonical_revision) })), limit }, binding(), signal);
      exact(result, ['tag', 'rows']);
      if (result.tag !== 'memory_candidates' || !Array.isArray(result.rows) || result.rows.length > limit) reject('memory_engine_result_invalid');
      return result.rows.map(row => {
        exact(row, ['engine_id', 'canonical_id', 'canonical_revision', 'text']);
        const ref = accepted.find(r => memoryEngineId(r.canonical_id, r.canonical_revision) === row.canonical_id && r.canonical_revision === row.canonical_revision && r.engine_id === row.engine_id);
        if (!ref) reject('memory_engine_result_stale'); return ref;
      });
    },
    async purge(ids) {
      for (let offset = 0; offset < ids.length; offset += 256) {
        const result = await output('memory.purge', { canonical_ids: ids.slice(offset, offset + 256) }, binding());
        exact(result, ['tag', 'removed', 'tombstones_applied']);
        if (result.tag !== 'memory_purged' || result.tombstones_applied !== true) reject('memory_purge_pending');
      }
    },
  };
}

export interface MemoryHostOptions {
  storage: MemoryStorage;
  engine: MemoryEngine;
  /** Exact immutable native answer resolution, without canonical DB/lock held. */
  resolveAnswer: (reference: CaptureTicket['reference']) => Promise<string>;
  /** Composition owns native standalone memory-extraction and selected models.
   * Promise settles only after native finalizers, including cancellation. */
  generate?: WorkerGenerationHandler;
}
const opaque = (prefix: string) => prefix + randomUUID().replaceAll('-', '');
const codeOf = (error: unknown) => error && typeof error === 'object' && 'code' in error && /^[a-z0-9_]{1,100}$/.test(String(error.code)) ? String(error.code) : 'memory_capture_failed';

/** Canonical admission -> byte resolution -> immutable CapturePlan -> selected
 * engine -> fresh canonical publication. No custom agent loop or direct inference. */
export function createMemoryHost(options: MemoryHostOptions) {
  const { storage, engine } = options;
  const active = new Map<string, { controller: AbortController; promise: Promise<unknown> }>();
  const plans = new Map<string, { ticket: CaptureTicket; plan: CapturePlan; used: boolean }>();
  let closing = false;
  let maintenance = Promise.resolve();
  async function flushPurges() {
    const work = maintenance.then(async () => {
      for (const intent of await storage.command({ type: 'memory.purge.pending' })) {
        await engine.purge(intent.ids);
        await storage.command({ type: 'memory.purge.ack', intentId: intent.intentId });
      }
    });
    maintenance = work.catch(() => {}); return work;
  }
  async function rebuild(signal?: AbortSignal, projectId?: string | null): Promise<{ ready: true }> {
    if (projectId === undefined) {
      const all = await storage.command({ type: 'memory.export' });
      for (const scope of new Set([null, ...all.records.map(r => r.project_id)])) await rebuild(signal, scope);
      return { ready: true };
    }
    await flushPurges();
    const snapshot = await storage.command({ type: 'memory.snapshot', projectId });
    const references = await engine.reconcile(snapshot.records, signal);
    return storage.command({ type: 'memory.index.accept', snapshot, references, generation: opaque('generation_') });
  }
  async function generation(request: GenerationRequest, signal: AbortSignal): Promise<WorkerGenerationResult> {
    const retained = plans.get(request.capture_plan.plan_id);
    if (!retained || retained.used || canonical(retained.plan) !== canonical(request.capture_plan) || signal.aborted || retained.plan.expires_at_ms <= Date.now()) return { status: 'cancelled', output: null };
    retained.used = true;
    try {
      await storage.command({ type: 'memory.capture.check', ticket: retained.ticket });
      if (!options.generate) reject('memory_generation_unavailable');
      const result = await options.generate(request, signal);
      await storage.command({ type: 'memory.capture.check', ticket: retained.ticket });
      return signal.aborted ? { status: 'cancelled', output: null } : result;
    } catch { return { status: signal.aborted ? 'cancelled' : 'failed', output: null }; }
  }
  async function captureEvidence(evidenceId: string, retry = false, explicit = false) {
    if (closing) reject('memory_closed');
    if (active.has(evidenceId)) return active.get(evidenceId)!.promise;
    const controller = new AbortController();
    const promise = (async () => {
      const ticket = await storage.command(explicit ? { type: 'memory.capture.explicit', evidenceId } : { type: 'memory.capture.claim', evidenceId, retry });
      if (!ticket) return { captured: false };
      let planId: string | undefined;
      try {
        const source = ticket.sourceText ?? await options.resolveAnswer(ticket.reference);
        text(source, 1, 16000);
        if (!source.trim() || digest(source) !== ticket.reference.sha256) reject('memory_answer_version');
        await storage.command({ type: 'memory.capture.check', ticket });
        const plan: CapturePlan = Object.freeze({ plan_id: opaque('captureplan_'), evidence_receipt: ticket.publicationDigest,
          support_sha256: ticket.supportSha256, source_sha256: digest(source), expires_at_ms: Date.now() + 120_000, max_calls: 1 });
        planId = plan.plan_id; plans.set(planId, { ticket, plan, used: false });
        const facts = await engine.extract({ text: source, plan, operationId: ticket.jobId, attemptId: 'captureattempt_' + ticket.attempt, signal: controller.signal });
        if (controller.signal.aborted) reject('memory_cancelled');
        const result = await storage.command({ type: 'memory.capture.complete', ticket, facts });
        await rebuild(undefined, ticket.projectId);
        return { captured: true, ...result };
      } catch (error) {
        await storage.command({ type: 'memory.capture.fail', ticket, cancelled: controller.signal.aborted, code: codeOf(error) });
        throw error;
      } finally { if (planId) plans.delete(planId); }
    })();
    active.set(evidenceId, { controller, promise });
    try { return await promise; } finally { active.delete(evidenceId); }
  }
  async function mutation(command: Extract<MemoryCommand, { type: 'memory.correct' | 'memory.delete' | 'memory.history.purge' }>) {
    // Persist revocation/intent BEFORE touching/cancelling derived work.
    const result = await storage.command(command);
    for (const running of active.values()) running.controller.abort();
    await flushPurges();
    if (!result.deleted) await rebuild();
    return command.type === 'memory.delete' ? { deleted: true, purge_pending: false } : command.type === 'memory.history.purge' ? { purged: true, purge_pending: false } : { ...await storage.command({ type: 'memory.inspect', id: command.id }), purge_pending: false };
  }
  async function recall(input: { query: string; scope: MemoryScope; projectId?: string | null; limit?: number; budget_chars?: number; signal?: AbortSignal }) {
    if (!['study', 'personal-library', 'generated-practice', 'reviewed-assessment'].includes(input.scope.kind)) reject('memory_scope_excluded');
    text(input.query, 1, 2000);
    await flushPurges();
    const snapshot = await storage.command({ type: 'memory.snapshot', projectId: input.projectId ?? null });
    const candidates = await engine.recall(input.query, snapshot.accepted, input.limit ?? 10, input.signal);
    return storage.command({ type: 'memory.recall.resolve', snapshot, candidates, budgetChars: input.budget_chars ?? 4000 });
  }
  return {
    generation, captureEvidence, flushPurges, rebuild, recall,
    async start() {
      await flushPurges();
      const jobs = await storage.command({ type: 'memory.jobs', recover: true });
      // Reopen only resumes already admitted queued work; failures require Retry.
      for (const job of jobs.filter(j => j.state === 'queued')) await captureEvidence(job.evidence_id, true).catch(() => {});
      // Existing Python mappings used logical engine IDs. Reconciliation adopts
      // immutable revision IDs before the migrated host serves its first recall.
      await rebuild();
    },
    async add(input: { text: string; kind?: FactKind; topic_id?: string | null; project_id?: string | null; idempotency_key: string; scope: MemoryScope }) {
      if (input.scope.kind !== 'study') reject('memory_scope_excluded');
      const record = await storage.command({ type: 'memory.add', text: input.text, kind: input.kind ?? 'learning-point', topicId: input.topic_id ?? null, projectId: input.project_id ?? null, idempotencyKey: input.idempotency_key });
      await rebuild(undefined, input.project_id ?? null); return storage.command({ type: 'memory.inspect', id: record.id });
    },
    correct: (id: string, text: string, expectedRevision: number) => mutation({ type: 'memory.correct', id, text, expectedRevision }),
    delete: (id: string, expectedRevision: number) => mutation({ type: 'memory.delete', id, expectedRevision }),
    purgeHistory: (id: string) => mutation({ type: 'memory.history.purge', id }),
    async cancel(jobId: string) {
      const jobs = await storage.command({ type: 'memory.jobs', recover: false });
      await storage.command({ type: 'memory.job.cancel', jobId });
      const job = jobs.find(j => j.id === jobId), running = job && active.get(job.evidence_id);
      if (running) { running.controller.abort(); await running.promise.catch(() => {}); }
      return { cancelled: true };
    },
    async retry() {
      await flushPurges(); const jobs = await storage.command({ type: 'memory.jobs', recover: false });
      const results = [];
      for (const job of jobs.filter(j => ['failed', 'queued'].includes(j.state))) results.push(await captureEvidence(job.evidence_id, true));
      await rebuild(); return { processed: results.length, results };
    },
    /** BF04 owns the volatile graph. This helper retains candidates in RAM only. */
    temporaryCandidates: (records: readonly MemoryRecord[], projectId: string | null = null) => Object.freeze(records.map(r => Object.freeze({ ...r, project_id: projectId }))),
    async close() {
      closing = true; for (const item of active.values()) item.controller.abort();
      await Promise.allSettled([...active.values()].map(item => item.promise)); await maintenance;
    },
  };
}
export type MemoryHost = ReturnType<typeof createMemoryHost>;
