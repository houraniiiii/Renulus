// SPDX-License-Identifier: MIT
import type { UpdatesStorage, UpdatesNativePort, CheckRoute, ObjectValue } from './contracts.ts';
import { reject, text } from '../../storage/contracts.ts';
export function createUpdatesCoordinator(options: { storage: UpdatesStorage; native: UpdatesNativePort }) {
  const { storage, native } = options;
  const active = new Set<AbortController>();
  let closed = false, timer: ReturnType<typeof setInterval> | undefined, running: Promise<ObjectValue> | undefined;
  async function check(route: CheckRoute, force = false) {
    if (closed) reject('updates_closed');
    const controller = new AbortController(); active.add(controller);
    try {
      const started = await storage.command({ type: 'updates.check.begin', route, force });
      if (!started.input) return started;
      try {
        controller.signal.throwIfAborted();
        const observation = await native.check(started.input, controller.signal);
        controller.signal.throwIfAborted();
        return await storage.command({ type: 'updates.check.finish', input: started.input, observation, errorCode: null });
      } catch (error) {
        const raw = controller.signal.aborted ? 'cancelled' : error && typeof error === 'object' && 'code' in error ? String(error.code) : 'source_fetch_failed';
        const errorCode = /^[a-z][a-z0-9_]{0,79}$/.test(raw) ? raw : 'source_fetch_failed';
        // A revoked/stale check cannot publish even a failure over newer state.
        try { return await storage.command({ type: 'updates.check.finish', input: started.input, observation: null, errorCode }); }
        catch { return { state: controller.signal.aborted ? 'cancelled' : 'failed', error_code: errorCode }; }
      }
    } finally { active.delete(controller); }
  }
  async function tickOnce(manual: boolean) {
    if (closed) reject('updates_closed');
    const run = await storage.command({ type: 'updates.schedule.claim', manual });
    if (!run.id) return storage.command({ type: 'updates.schedule.read' });
    let checked = 0, failed = 0;
    for (const route of run.selection) {
      if (closed) break;
      const result = await check(route); checked++; if (['failed', 'cancelled'].includes(result.state)) failed++;
    }
    return storage.command({ type: 'updates.schedule.finish', id: run.id, checked, failed, errorCode: closed ? 'cancelled' : failed ? 'check_failed' : null });
  }
  function tick(manual = false) { return running ??= tickOnce(manual).finally(() => { running = undefined; }); }
  async function cancel() {
    await storage.command({ type: 'updates.schedule.stop' });
    for (const controller of active) controller.abort();
    return storage.command({ type: 'updates.schedule.read' });
  }
  return {
    check, tick, cancel,
    async digest(limit = 20, signal?: AbortSignal) {
      if (closed) reject('updates_closed');
      const controller = new AbortController(), abort = () => controller.abort(); active.add(controller);
      signal?.addEventListener('abort', abort, { once: true }); if (signal?.aborted) abort();
      try {
        const input = await storage.command({ type: 'updates.digest.input', limit });
        controller.signal.throwIfAborted(); const output = await native.digest(input, controller.signal); controller.signal.throwIfAborted(); text(output, 1, 16_000);
        await storage.command({ type: 'updates.digest.current', stamp: input.stamp, limit });
        // Narrative output cannot enter any check/review/currentness command.
        return { text: output, entries: input.entries.map(e => ({ id: e.id, url: e.url, review_state: e.review_state })), checked_at: input.checked_at };
      } finally { active.delete(controller); signal?.removeEventListener('abort', abort); }
    },
    async start(intervalMs = 60_000) { if (timer) return; closed = false; await storage.command({ type: 'updates.recover' }); timer = setInterval(() => { tick().catch(() => {}); }, Math.max(1000, intervalMs)); timer.unref(); },
    async close() { closed = true; if (timer) clearInterval(timer); timer = undefined; await cancel(); await running?.catch(() => {}); },
  };
}
export type UpdatesCoordinator = ReturnType<typeof createUpdatesCoordinator>;
