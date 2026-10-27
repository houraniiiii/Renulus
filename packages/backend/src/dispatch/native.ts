// SPDX-License-Identifier: MIT
/** In-process model callbacks for the parent's real DomainClient protocol pump.
 * No replacement client/bus, agent loop, serializer, credential access or production transport. */
import { randomUUID } from 'node:crypto';
import { exact, integer, reject } from '../storage/contracts.ts';
import { canonical, digest } from '../storage/schema.ts';
import { id, validateQualification } from './policy.ts';
import type { DispatchCommand, DispatchResults, Fence, Permit, Qualification, RequestProof, Route, Run } from './contracts.ts';
import { base64, verifyWire } from './wire.ts';
import type { NativeManifest, SerializedRequest } from './wire.ts';

export interface NativeBinding { operation_id: string; attempt_id: string; session_id: string; input_id: string; cancellation_id: string }
export type ModelCommand = 'model.prepare' | 'model.manifest' | 'model.dispatch';
export type CallbackOutcome = { outcome: 'committed_reference'; result: Record<string, unknown> } |
  { outcome: 'rejected_before_admission' | 'cancelled_settled' | 'uncertain_after_disconnect'; error: { code: string; status: number; retryable: false } };
export interface DispatchStorage {
  command<C extends DispatchCommand>(command: C): Promise<DispatchResults[C['type']]>;
}
export interface DeploymentEvidence {
  readonly metadata: Qualification;
  /** Must include native framing/system/history/tool schema/results/media for this exact route.
   * A character estimate/raw JSON tokenization is not a qualified implementation. */
  readonly count: (body: Uint8Array, manifest: Readonly<NativeManifest>, signal: AbortSignal) => Promise<number | null>;
}
export interface NativeTransport {
  /** Set only by the app-owned authenticated worker adapter. */
  readonly authority?: 'authenticated-worker';
  /** Isolated tests may supply a transport without account access. */
  readonly fixtureOnly?: true;
  send(input: Readonly<{ permit: Permit; route: Route; serialized: SerializedRequest; proof: RequestProof; signal: AbortSignal }>): Promise<{
    status: number; headers: Record<string, string>; body_base64: string; result_reference: string;
  }>;
}
export interface NativeDispatchOptions {
  storage: DispatchStorage;
  /** The parent resolves authenticated native bindings, never request payload claims. */
  resolve(binding: Readonly<NativeBinding>): Promise<{ runId: string; fence: Fence }>;
  /** Check operation/attempt/session, actual input, cancellation and current owner/domain epochs.
   * The parent's final publication transaction must also check domain-specific deletion/assessment. */
  checkCurrent(binding: Readonly<NativeBinding>, run: Readonly<Run>): Promise<void>;
  /** Return the same host-owned immutable evidence object throughout a prepared plan. */
  evidence(route: Readonly<Route>): DeploymentEvidence | undefined;
  transport: NativeTransport;
}
type Plan = { id: string; step: string; run: Run; evidence: DeploymentEvidence; metadata: Qualification;
  kind: 'primary' | 'child' | 'tool-continuation'; previous: string | null; manifest?: NativeManifest;
  phase: 'prepared' | 'manifest' | 'sending' | 'confirmed' | 'failed'; permit?: Permit };
type OwnedRun = { binding: NativeBinding; runId: string; fence: Fence; plans: Plan[]; busy: boolean };
const bindingKeys = ['operation_id', 'attempt_id', 'session_id', 'input_id', 'cancellation_id'] as const;
const bounds = Object.freeze({ max_request_bytes: 512 * 1024, max_response_bytes: 512 * 1024, max_frame_bytes: 1048576 });
function freeze<T>(value: T): T {
  if (value && typeof value === 'object') { for (const v of Object.values(value)) freeze(v); Object.freeze(value); } return value;
}
function boundedClone<T>(value: T, bytes: number): T {
  const json = JSON.stringify(value);
  if (typeof json !== 'string' || Buffer.byteLength(json) > bytes) reject('model_registry_capacity');
  return freeze(structuredClone(value));
}
function safeCode(error: unknown): string {
  const code = error && typeof error === 'object' && 'code' in error ? error.code : null;
  return typeof code === 'string' && /^[A-Za-z0-9_-]{1,128}$/.test(code) ? code : 'model_dispatch_unavailable';
}
export function createNativeDispatchCallbacks(options: NativeDispatchOptions) {
  if ((options.transport.fixtureOnly !== true && options.transport.authority !== 'authenticated-worker') ||
      typeof options.transport.send !== 'function') reject('protected_transport_required');
  const runs = new Map<string, OwnedRun>(), controllers = new Set<AbortController>(), pending = new Set<Promise<unknown>>();
  let closing = false;
  const keyFor = (binding: NativeBinding) => canonical(binding);
  async function owner(binding: NativeBinding): Promise<OwnedRun> {
    exact(binding, bindingKeys); for (const k of bindingKeys) id(binding[k]);
    const resolved = await options.resolve(binding), known = runs.get(keyFor(binding));
    if (resolved.runId !== binding.operation_id) reject('model_registry_authority_unbound');
    if (known) { if (resolved.runId !== known.runId || canonical(resolved.fence) !== canonical(known.fence)) reject('model_registry_authority_changed'); return known; }
    if (runs.size >= 16 || [...runs.values()].some(r => r.runId === resolved.runId)) reject('model_registry_capacity');
    const result: OwnedRun = { binding: freeze({ ...binding }), runId: resolved.runId, fence: freeze(structuredClone(resolved.fence)), plans: [], busy: false };
    runs.set(keyFor(binding), result); return result;
  }
  async function current(owned: OwnedRun, plan?: Plan, signal?: AbortSignal) {
    if (closing || signal?.aborted) reject('domain_cancelled');
    const run = await options.storage.command({ type: 'dispatch.current', runId: owned.runId, fence: owned.fence,
      requiredCapabilities: plan?.run.effective_capabilities ?? [], permitId: plan?.permit?.state === 'confirmed' ? plan.permit.permit_id : null });
    await options.checkCurrent(owned.binding, run);
    if (plan && (options.evidence(plan.run.route) !== plan.evidence || canonical(plan.evidence.metadata) !== canonical(plan.metadata))) reject('deployment_evidence_stale');
    if (closing || signal?.aborted) reject('domain_cancelled'); return run;
  }
  async function handle(owned: OwnedRun, command: ModelCommand, payload: Readonly<Record<string, unknown>>, signal: AbortSignal): Promise<CallbackOutcome> {
    let active: Plan | undefined;
    try {
      const run = await current(owned, undefined, signal);
      if (command === 'model.prepare') {
        exact(payload, []);
        const previous = owned.plans.at(-1);
        if (previous && previous.phase !== 'confirmed') reject('model_registry_phase_invalid');
        if (previous) await current(owned, previous, signal);
        if (owned.plans.length >= Math.min(run.dispatch_limit, 128)) reject('model_registry_capacity');
        const evidence = options.evidence(run.route);
        if (!evidence || typeof evidence.count !== 'function') reject('deployment_counter_unknown');
        validateQualification(evidence.metadata, run.route, run.effective_capabilities);
        const metadata = boundedClone(evidence.metadata, 16384);
        const plan: Plan = { id: randomUUID().replaceAll('-', ''), step: randomUUID().replaceAll('-', ''), run: freeze(run), evidence, metadata,
          kind: previous ? 'tool-continuation' : run.parent_id ? 'child' : 'primary', previous: previous?.permit?.permit_id ?? null, phase: 'prepared' };
        await current(owned, plan, signal); owned.plans.push(plan);
        const result: Record<string, unknown> = { dispatch_id: plan.id, binding: owned.binding,
          role: { version: run.version, purpose: run.purpose, model_id: run.route.catalog_model_id,
            output_tokens: Math.min(metadata.limits.output_tokens, run.output_tokens), dispatch_limit: run.dispatch_limit },
          request_kind: plan.kind, route: run.route, limits: metadata.limits, required_capabilities: run.effective_capabilities,
          native_capabilities: { tools: run.effective_capabilities.includes('tools'), input: ['text', ...(run.effective_capabilities.includes('image') ? ['image'] : [])], output: ['text'] }, bounds };
        if (plan.previous) result.continuation_of = plan.previous;
        return { outcome: 'committed_reference', result };
      }
      const plan = owned.plans.at(-1); if (!plan) reject('model_registry_phase_invalid'); active = plan;
      await current(owned, plan, signal);
      if (command === 'model.manifest') {
        exact(payload, ['manifest']); if (plan.phase !== 'prepared') reject('model_registry_phase_invalid');
        plan.manifest = boundedClone(payload.manifest as NativeManifest, bounds.max_frame_bytes / 2); plan.phase = 'manifest';
        return { outcome: 'committed_reference', result: { registered: true } };
      }
      if (command !== 'model.dispatch') reject('model_registry_command_invalid');
      exact(payload, ['dispatch_id', 'serialized_request']);
      if (plan.phase !== 'manifest' || payload.dispatch_id !== plan.id || !plan.manifest) reject('model_registry_phase_invalid');
      plan.phase = 'sending';
      const serialized = boundedClone(payload.serialized_request as SerializedRequest, bounds.max_frame_bytes - 1024);
      for (const [name, value] of Object.entries(serialized.headers ?? {})) {
        if (name.toLowerCase() === 'x-opencode-session' && value !== owned.binding.session_id) reject('deployment_request_invalid');
      }
      const wire = verifyWire(serialized, plan.manifest, plan.run.route, bounds.max_request_bytes, Math.min(plan.run.output_tokens, plan.metadata.limits.output_tokens));
      if (!wire.features.every(c => plan.run.effective_capabilities.includes(c))) reject('deployment_capability_unprepared');
      const tokens = await plan.evidence.count(Uint8Array.from(wire.body), plan.manifest, signal);
      await current(owned, plan, signal); integer(tokens);
      const proof: RequestProof = { qualification: plan.metadata, payload_hash: wire.body_sha256, wire_sha256: digest(canonical(serialized)), input_manifest_sha256: wire.input_manifest_sha256,
        body_bytes: wire.body_bytes, input_tokens: tokens, output_tokens: wire.output_tokens };
      plan.permit = await options.storage.command({ type: 'dispatch.reserve', runId: run.run_id, stepId: plan.step, requestKind: plan.kind,
        continuationOf: plan.previous, requiredCapabilities: plan.run.effective_capabilities, fence: owned.fence, proof });
      if (plan.permit.state !== 'reserved') reject('dispatch_already_admitted');
      await current(owned, plan, signal);
      plan.permit = await options.storage.command({ type: 'dispatch.admit', permitId: plan.permit.permit_id, fence: owned.fence, proof });
      if (!plan.permit.dispatch_allowed) reject('dispatch_already_admitted');
      // No awaits between the committed one-use admission and starting transport. Abort remains best effort.
      const response = await options.transport.send({ permit: plan.permit, route: plan.run.route, serialized, proof, signal });
      if (response.status !== 200) {
        const code = response.status === 401 || response.status === 403 ? 'authentication_required' : response.status === 429 ? 'subscription_limit' : 'transport_unavailable';
        await options.storage.command({ type: 'dispatch.complete', permitId: plan.permit.permit_id, outcome: 'failed', resultReference: null, failureCode: code });
        reject(code);
      }
      exact(response, ['status', 'headers', 'body_base64', 'result_reference']); id(response.result_reference);
      exact(response.headers, ['content-type']); if (response.headers['content-type'] !== 'text/event-stream') reject('provider_stream_failed');
      base64(response.body_base64, bounds.max_response_bytes);
      plan.permit = await options.storage.command({ type: 'dispatch.complete', permitId: plan.permit.permit_id, outcome: 'confirmed', resultReference: response.result_reference, failureCode: null });
      // A received response does not grant publication after Stop, deletion, assessment or revocation.
      await current(owned, plan, signal); plan.phase = 'confirmed'; plan.manifest = undefined;
      return { outcome: 'committed_reference', result: { permit_id: plan.permit.permit_id, status: 200, headers: response.headers, body_base64: response.body_base64 } };
    } catch (error) {
      let uncertain = false;
      if (active?.permit) {
        // Query after an ACK loss: do not guess that the final admission rolled back.
        try {
          const p = await options.storage.command({ type: 'dispatch.permit', permitId: active.permit.permit_id });
          if (p.state === 'dispatched' || p.state === 'reserved') {
            uncertain = p.state === 'dispatched';
            await options.storage.command({ type: 'dispatch.complete', permitId: p.permit_id, outcome: uncertain ? 'uncertain' : 'cancelled_before_send', resultReference: null, failureCode: uncertain ? 'transport_unavailable' : null });
          } else uncertain = p.state === 'uncertain';
        } catch { uncertain = true; }
      }
      if (active?.phase === 'sending') { active.phase = 'failed'; active.manifest = undefined; }
      const code = safeCode(error);
      return { outcome: uncertain ? 'uncertain_after_disconnect' : code === 'domain_cancelled' ? 'cancelled_settled' : 'rejected_before_admission',
        error: { code, status: code === 'authentication_required' ? 401 : code === 'subscription_limit' ? 429 : 409, retryable: false } };
    }
  }
  return {
    /** The parent adds the existing DomainOutcome identity/callback fields via DomainClient.receive. */
    async handle(binding: NativeBinding, command: ModelCommand, payload: Readonly<Record<string, unknown>>, optionsForCall: { signal?: AbortSignal } = {}): Promise<CallbackOutcome> {
      let owned: OwnedRun;
      try {
        if (closing) reject('domain_cancelled'); owned = await owner(binding);
        if (owned.busy || pending.size >= 4) reject('model_registry_capacity');
      } catch (error) { return { outcome: 'rejected_before_admission', error: { code: safeCode(error), status: 409, retryable: false } }; }
      owned.busy = true; const controller = new AbortController(); controllers.add(controller);
      const abort = () => controller.abort(); optionsForCall.signal?.addEventListener('abort', abort, { once: true }); if (optionsForCall.signal?.aborted) abort();
      const promise = handle(owned, command, payload, controller.signal); pending.add(promise);
      try { return await promise; } finally { pending.delete(promise); controllers.delete(controller); optionsForCall.signal?.removeEventListener('abort', abort); owned.busy = false; }
    },
    async release(binding: NativeBinding) {
      const known = runs.get(keyFor(binding)); if (!known) return;
      if (known.busy || (await options.storage.command({ type: 'dispatch.run', runId: known.runId })).state !== 'settled') reject('model_registry_settlement_pending');
      runs.delete(keyFor(binding));
    },
    status() { return { closing, runs: runs.size, active: pending.size }; },
    async close() { closing = true; for (const c of controllers) c.abort(); await Promise.allSettled([...pending]); },
  };
}
