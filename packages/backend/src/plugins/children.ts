// SPDX-License-Identifier: MIT
import { createHash, randomUUID } from 'node:crypto';
import { Effect } from 'effect';
import { Tool } from '@opencode/schema/tool';
import type { StorageClient } from '../storage/index.ts';
import { reject } from '../storage/contracts.ts';
import { canonical } from '../storage/schema.ts';
import type { NativeInputBinding } from '../../../harness/src/host.ts';
import type { ChildAuthorityBridge } from '../../../harness/src/child-authority.ts';
import type { NativeDomainReply, NativeDomainRequest } from '../host/domain-adapter.ts';
import type { Fence, Run } from '../dispatch/contracts.ts';

export interface ChildHooks {
  storage: StorageClient;
  /** Parent USER binding of the actual native session. */
  binding(sessionId: string): NativeInputBinding;
  /** Register the allocated child USER with the native host before prompt admission. */
  bindChild(binding: NativeInputBinding): void;
  /** Synchronous seal: admission is open and this grant epoch is still current. */
  current(grantEpoch: number): boolean;
  /** The child run joins the owning host's settlement; its input joins model dispatch. */
  adopt(run: Run, binding: NativeInputBinding, guard: () => Promise<void>): void;
  /** Child model dispatch of the owning host (`model.prepare|manifest|dispatch`). */
  model(request: NativeDomainRequest): Promise<NativeDomainReply>;
}
interface Reservation { parent: NativeInputBinding; run: Run; fence: Fence; epoch: number; child?: NativeInputBinding;
  report?: { id: string; digest: string; consumed: boolean } }

const text = (value: unknown, code: string) => typeof value === 'string' && value ? value : reject(code);
const exactKeys = (value: unknown, keys: string[], code = 'child_invalid_request'): Record<string, unknown> => {
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).sort().join() !== [...keys].sort().join()) reject(code);
  return value as Record<string, unknown>;
};
const committed = (result: Record<string, unknown>): NativeDomainReply => ({ outcome: 'committed_reference', result });

/** Parent-side canonical authority for the evidence-review child (spec section 4). Native H07
 * (`child-authority.ts`) owns Session/Job/permission execution; this owns claims, budgets and grants. */
export function createChildren(hooks: ChildHooks) {
  const { storage } = hooks;
  const reservations = new Map<string, Reservation>();
  const invocations = new Map<string, string>();
  const reservation = (value: unknown) => reservations.get(text(value, 'child_reservation_unknown')) ?? reject('child_reservation_unknown');

  /** Parent-intersected current authority. Any newer grant epoch, revocation, stop or context change refuses. */
  async function current(item: Reservation) {
    if (!hooks.current(item.epoch)) reject('child_authority_stale');
    await storage.command({ type: 'learning.current', runId: item.parent.operation_id, binding: item.parent });
    const parent = await storage.command({ type: 'dispatch.run', runId: item.parent.operation_id });
    if (!parent.effective_capabilities.includes('renulus.child')) reject('capability_revoked');
    await storage.command({ type: 'dispatch.current', runId: item.run.run_id, fence: item.fence, requiredCapabilities: ['text'], permitId: null });
    if ((await storage.command({ type: 'dispatch.snapshot' })).grant_epoch !== item.epoch) reject('child_authority_stale');
    if (!hooks.current(item.epoch)) reject('child_authority_stale');
  }
  async function prepare(parent: NativeInputBinding, payload: Record<string, unknown>) {
    const { invocation } = exactKeys(payload, ['invocation', 'work']) as { invocation: Record<string, unknown> };
    const key = text(exactKeys(invocation, ['message_id', 'tool_call_id']).message_id, 'child_invalid_request') + ':' + text(invocation.tool_call_id, 'child_invalid_request');
    if (invocations.has(key)) reject('child_reservation_conflict');
    const root = await storage.command({ type: 'dispatch.run', runId: parent.operation_id });
    await storage.command({ type: 'learning.current', runId: parent.operation_id, binding: parent });
    if (!root.effective_capabilities.includes('renulus.child')) reject('capability_revoked');
    const epoch = (await storage.command({ type: 'dispatch.snapshot' })).grant_epoch;
    if (!hooks.current(epoch)) reject('child_authority_stale');
    // dispatch.child enforces parent intersection, max depth and concurrency in the canonical transaction.
    const run = await storage.command({ type: 'dispatch.child', runId: 'child_' + randomUUID().replaceAll('-', ''), parentId: root.run_id,
      purpose: 'evidence-review', capabilities: root.effective_capabilities.filter(name => name === 'text' || name === 'tools'),
      operationModel: null, fence: root.fence });
    reservations.set(run.run_id, { parent, run, fence: root.fence, epoch });
    invocations.set(key, run.run_id);
    return { reservation_id: run.run_id, operation_id: run.run_id, attempt_id: '1', cancellation_id: run.run_id, grant_epoch: epoch };
  }
  async function admit(binding: NativeInputBinding, payload: Record<string, unknown>) {
    const item = reservation(exactKeys(payload, ['reservation_id']).reservation_id);
    if (item.child || binding.operation_id !== item.run.run_id) reject('child_binding_conflict');
    await current(item);
    item.child = Object.freeze({ ...binding });
    hooks.adopt(item.run, item.child, () => current(item));
    return { admitted: true };
  }
  async function request(binding: NativeInputBinding, command: string, payload: Record<string, unknown>): Promise<Record<string, unknown>> {
    if (command === 'child.prepare') return prepare(binding, payload);
    if (command === 'child.consume_report') {
      const report = text(exactKeys(payload, ['report_id']).report_id, 'child_report_unknown');
      const item = [...reservations.values()].find(entry => entry.report?.id === report);
      if (!item?.report || canonical(item.parent) !== canonical(binding)) reject('child_report_unknown');
      await current(item); item.report.consumed = true; return { consumed: true };
    }
    const item = reservation((payload as { reservation_id?: unknown }).reservation_id);
    if (command === 'child.admit_input') return admit(binding, payload);
    if (canonical(item.parent) !== canonical(binding) && (!item.child || canonical(item.child) !== canonical(binding))) reject('child_binding_conflict');
    await current(item);
    switch (command) {
      case 'child.check': return { current: true, grant_epoch: item.epoch };
      case 'child.observe_job': exactKeys(payload, ['reservation_id', 'job_id', 'started_at', 'notification_id']); return { observed: true };
      case 'child.report': {
        const body = exactKeys(payload, ['reservation_id', 'notification_id', 'report_digest', 'output']);
        if (item.report || body.report_digest !== createHash('sha256').update(text(body.output, 'child_report_invalid')).digest('hex')) reject('child_report_conflict');
        item.report = { id: 'report_' + randomUUID().replaceAll('-', ''), digest: String(body.report_digest), consumed: false };
        return { report_id: item.report.id };
      }
      default: return reject('child_command_unknown');
    }
  }
  const owned = (binding: Readonly<NativeInputBinding>) => {
    const item = reservations.get(binding.operation_id);
    return !!item?.child && canonical(item.child) === canonical(binding);
  };
  /** Child callbacks: context, authority and Library are the parent's; model dispatch is the child's own run. */
  async function handle(callback: NativeDomainRequest, root: (request: NativeDomainRequest) => Promise<NativeDomainReply>): Promise<NativeDomainReply> {
    try {
      const item = reservations.get(callback.binding.operation_id);
      if (!item?.child || canonical(item.child) !== canonical(callback.binding)) reject('child_binding_conflict');
      await current(item);
      if (callback.command.startsWith('model.')) return await hooks.model(callback);
      const parentCall = { ...callback, binding: item.parent };
      switch (callback.command) {
        case 'learning.check': return committed({ current: true });
        case 'learning.context': {
          const messages = (callback.payload.messages ?? []) as { id: string; role: string }[];
          const start = messages.findIndex(message => message.id === item.child!.input_id && message.role === 'user');
          if (start < 0 || messages.slice(start + 1).some(message => message.role === 'user')) reject('harness_context_conflict');
          const before = new Set(messages.slice(0, start).map(message => message.id));
          if (messages.slice(start).some(message => before.has(message.id))) reject('harness_context_conflict');
          return committed({ message_ids: [...new Set(messages.slice(start).map(message => message.id))], learner_context: '' });
        }
        case 'learning.authority': {
          const reply = await root(parentCall);
          return reply.result ? committed({ ...reply.result, sessionId: item.child.session_id, operationId: item.child.operation_id,
            attemptId: item.child.attempt_id }) : reply;
        }
        case 'library.retrieve': case 'library.citation': case 'learning.validate_images': return await root(parentCall);
        default: return reject('learning_callback_unknown');
      }
    } catch (error) {
      const code = error && typeof error === 'object' && 'code' in error ? String(error.code) : 'child_callback_unavailable';
      return { outcome: callback.signal.aborted ? 'cancelled_settled' : 'rejected_before_admission',
        error: { code: /^[a-z0-9_-]{1,128}$/.test(code) ? code : 'child_callback_unavailable', status: 409, retryable: false } };
    }
  }
  const bridge: ChildAuthorityBridge = {
    resolveParent: native => hooks.binding(native.sessionID),
    localCurrent: (_parent, epoch) => hooks.current(epoch),
    bindInput: child => hooks.bindChild(child),
    request: (binding, command, payload) => Effect.tryPromise({ try: () => request(binding, command, payload as Record<string, unknown>),
      catch: error => new Tool.Error({ message: error && typeof error === 'object' && 'code' in error ? String(error.code) : 'child_unavailable' }) }),
  };
  return { bridge, owns: owned, handle, status: () => ({ reservations: reservations.size,
    reports: [...reservations.values()].filter(item => item.report).length }) };
}
export type Children = ReturnType<typeof createChildren>;
