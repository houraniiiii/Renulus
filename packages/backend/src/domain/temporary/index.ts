// SPDX-License-Identifier: MIT
/** One retained family controller linearises Save activation and owner disconnect. */
import { randomUUID } from 'node:crypto';
import type { VolatileHarness, NativeGraph } from '../../../../harness/src/volatile-host.ts';
import { exportVolatileFamily, remapVolatileFamily } from '../../../../harness/src/volatile-host.ts';
import type { PromotedExchange, PromotionPlan, PromotionReceipt, TemporaryStorage } from './contracts.ts';
import { nativeText, type NativeMessage } from '../learning/history.ts';
import { canonical, digest } from '../../storage/schema.ts';
import { reject } from '../../storage/contracts.ts';

/** Only completed, error-free answers become visible saved history; anything else stays unreferenced. */
function completedExchanges(root: NativeGraph[number]): PromotedExchange[] {
  const result: (PromotedExchange & { text: string; valid: boolean })[] = [];
  for (const message of root.messages as unknown as NativeMessage[]) {
    if (message.type === 'user') result.push({ runId: 'run_' + randomUUID().replaceAll('-', ''), inputId: message.id, messageIds: [], sha256: '', text: '', valid: true });
    else if (message.type === 'assistant' && result.length) {
      const exchange = result.at(-1)!;
      exchange.messageIds.push(message.id); exchange.text += nativeText(message);
      if (message.error || !message.time?.completed) exchange.valid = false;
    }
  }
  return result.filter(e => e.valid && e.messageIds.length && e.text).map(({ text, valid: _valid, ...e }) => ({ ...e, sha256: digest(text) }));
}

const missing = (error: unknown) => !!error && typeof error === 'object' && '_tag' in error && (error._tag === 'SessionNotFoundError' || error._tag === 'Session.NotFoundError');
type SavedNative = Pick<VolatileHarness, 'importSession' | 'exportSession' | 'removeSession'>;
export interface TemporaryFamilyOptions {
  host: VolatileHarness; rootSessionId: string; storage: TemporaryStorage; saved: SavedNative;
  identity: { profileId: string; storeId: string };
  /** Current canonical assessment/context epochs and original-use rights, rechecked at activation. */
  current(): Promise<{ contextEpoch: number; policyRevision: number }>;
  /** Stop/signal native children, RAM dispatcher and every temporary worker/transport lease. */
  settle(reason: 'save' | 'disconnect'): Promise<'settled' | 'held'>;
  /** Optional RAM native spill/media adapter, mandatory when the graph has spills. */
  stageFiles?(promotionId: string, files: ReturnType<VolatileHarness['files']>): Promise<{ replacements: Record<string, string>; rollback(): Promise<void> }>;
}
export function createTemporaryFamily(options: TemporaryFamilyOptions) {
  let state: 'open' | 'save-failed' | 'saving' | 'saved' | 'discarding' | 'discarded' | 'held' = 'open';
  let cancellationEpoch = 0, receipt: PromotionReceipt | undefined, plan: PromotionPlan | undefined;
  let transferred: NativeGraph | undefined, saving: Promise<PromotionReceipt> | undefined;
  let control: Promise<unknown> = Promise.resolve(), pending = new Set<Promise<unknown>>();
  const serial = <T>(fn: () => Promise<T>) => { const next = control.then(fn); control = next.catch(() => {}); return next; };
  async function nativeSettlement() {
    const visit = async (id: string) => {
      for (const child of await options.host.listChildren(id)) await visit(child.id);
      await options.host.cancel(id);
    };
    await visit(options.rootSessionId);
    await Promise.allSettled([...pending]);
  }
  async function discardRAM() {
    const closed = await options.host.close({ timeoutMs: 30_000 });
    if (closed.state !== 'closed') { state = 'held'; reject('temporary_settlement_held'); }
  }
  async function retireStaging(retire = true) {
    if (!plan || !receipt || receipt.state === 'active') return;
    for (const id of [...plan.sessionIds].reverse()) {
      try { await options.saved.removeSession(id); }
      catch (error) { if (!missing(error)) throw error; }
    }
    if (retire) receipt = await options.storage.command({ type: 'temporary.save.retire', id: plan.id, expectedEpoch: receipt.cancellationEpoch });
  }
  async function promote(title: string, idempotencyKey: string) {
    await serial(async () => {
      if (state === 'saved') return;
      if (state !== 'open' && state !== 'save-failed') reject('temporary_family_unavailable'); state = 'saving';
    });
    if (receipt?.state === 'active') return receipt;
    let stagedFiles: Awaited<ReturnType<NonNullable<TemporaryFamilyOptions['stageFiles']>>> | undefined;
    try {
      const [settlement] = await Promise.all([options.settle('save'), nativeSettlement()]);
      if (settlement !== 'settled') reject('temporary_settlement_held');
      const current = await options.current();
      const graph = await exportVolatileFamily(options.host, options.rootSessionId);
      if (!plan) {
        const id = 'promotion_' + randomUUID().replaceAll('-', '');
        const remapped = remapVolatileFamily(graph, { ...options.identity, promotionId: id });
        transferred = remapped.graph;
        plan = { id, threadId: 'thread_' + randomUUID().replaceAll('-', ''), title, ...options.identity,
          rootSessionId: transferred[0].info.id, sessionIds: transferred.map(data => data.info.id), exchanges: completedExchanges(transferred[0]),
          cancellationEpoch, ...current, idempotencyKey };
      } else if (plan.idempotencyKey !== idempotencyKey || plan.title !== title) reject('idempotency_conflict');
      await serial(async () => {
        if (state !== 'saving' || plan!.cancellationEpoch !== cancellationEpoch) reject('temporary_cancelled');
        receipt = await options.storage.command({ type: 'temporary.save.begin', plan: plan! });
        if (receipt.state === 'cancelled' || receipt.state === 'retired') reject('temporary_cancelled');
      });
      const files = options.host.files();
      if (files.length) {
        if (!options.stageFiles) reject('temporary_spill_transfer_unavailable');
        stagedFiles = await options.stageFiles(plan.id, files);
        const replace = (v: unknown): unknown => typeof v === 'string' ? stagedFiles!.replacements[v] ?? v : Array.isArray(v) ? v.map(replace)
          : v && typeof v === 'object' ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, replace(x)])) : v;
        transferred = replace(transferred) as NativeGraph;
      }
      for (const data of transferred!) {
        if (state !== 'saving') reject('temporary_cancelled');
        try { await options.saved.importSession(data); }
        catch (error) {
          // Lost acknowledgement retries reconcile this exact fresh target.
          const existing = await options.saved.exportSession(data.info.id).catch(() => undefined);
          if (!existing || canonical(existing.messages) !== canonical(data.messages) || existing.info.metadata?.promotionId !== plan.id) throw error;
        }
        const copied = await options.saved.exportSession(data.info.id);
        if (canonical(copied.messages) !== canonical(data.messages) || copied.info.metadata?.promotionId !== plan.id) reject('temporary_copy_unverified');
      }
      await options.current();
      await serial(async () => {
        if (state !== 'saving' || cancellationEpoch !== plan!.cancellationEpoch) reject('temporary_cancelled');
        receipt = await options.storage.command({ type: 'temporary.save.copied', id: plan!.id, expectedEpoch: cancellationEpoch,
          graphDigest: digest(canonical(transferred)) });
        receipt = await options.storage.command({ type: 'temporary.save.activate', id: plan!.id, expectedEpoch: cancellationEpoch });
        if (receipt.state !== 'active') reject('temporary_save_inactive'); state = 'saved';
      });
      await discardRAM(); transferred = undefined; return receipt!;
    } catch (error) {
      if ((receipt as PromotionReceipt | undefined)?.state === 'active') { state = 'saved'; return receipt!; }
      // Copy/import/worker work has settled before hidden staging is removed.
      await retireStaging(state !== 'saving'); await stagedFiles?.rollback();
      await serial(async () => { if (state === 'saving') state = 'save-failed'; });
      throw error;
    }
  }
  return {
    status: () => ({ state, cancellationEpoch, saved: receipt?.state === 'active' ? receipt : null }),
    async send(input: { text: string; images?: unknown }) {
      const task = await serial(async () => {
        if (state !== 'open') reject('temporary_family_unavailable');
        const operationId = 'temporary_' + randomUUID().replaceAll('-', '');
        const task = (async () => {
          const result = await options.host.submit({ sessionId: options.rootSessionId, operationId, attemptId: '1', ...input });
          await options.host.wait(options.rootSessionId); return result;
        })(); pending.add(task); void task.finally(() => pending.delete(task)).catch(() => {}); return { task };
      });
      return task.task;
    },
    range: (input?: Parameters<VolatileHarness['observe']>[1]) => {
      if (['discarded', 'discarding', 'held'].includes(state)) reject('temporary_family_unavailable');
      return options.host.observe(options.rootSessionId, input);
    },
    save(title: string, idempotencyKey: string) {
      if (receipt?.state === 'active') return Promise.resolve(receipt);
      if (!saving) { saving = promote(title, idempotencyKey); void saving.finally(() => { saving = undefined; }).catch(() => {}); }
      return saving;
    },
    /** Successful terminal stream closure only detaches; abnormal owner loss calls this. */
    async disconnect() {
      const selected = await serial(async () => {
        if (receipt?.state === 'active') return receipt;
        if (state === 'discarded') return null;
        state = 'discarding'; cancellationEpoch++;
        if (plan && receipt) receipt = await options.storage.command({ type: 'temporary.save.cancel', id: plan.id, expectedEpoch: receipt.cancellationEpoch });
        return null;
      });
      if (selected) return { state: 'detached' as const, saved: selected };
      if (state === 'discarded') return { state: 'discarded' as const };
      const [settlement] = await Promise.all([options.settle('disconnect'), nativeSettlement()]);
      if (settlement !== 'settled') { state = 'held'; reject('temporary_settlement_held'); }
      await saving?.catch(() => {}); await retireStaging(); await discardRAM();
      transferred = undefined; state = 'discarded'; return { state: 'discarded' as const };
    },
  };
}

/** Startup runs before any public reads/Finder/export; no temporary input is reconstructed. */
export async function reconcileTemporarySaves(storage: TemporaryStorage, saved: Pick<SavedNative, 'removeSession'>) {
  for (const pending of await storage.command({ type: 'temporary.save.pending' })) {
    for (const id of [...pending.sessionIds].reverse()) {
      try { await saved.removeSession(id); } catch (error) {
        if (!missing(error)) throw error;
      }
    }
    await storage.command({ type: 'temporary.save.retire', id: pending.id, expectedEpoch: pending.cancellationEpoch });
  }
}
