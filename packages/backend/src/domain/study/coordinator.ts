// SPDX-License-Identifier: MIT
import type { StudyStorage, StudyNativePort, StudyAssessmentPort, LocalClock, StudyCommand } from './contracts.ts';
import { reject } from '../../storage/contracts.ts';

export const systemLocalClock = (): LocalClock => ({ now: new Date().toISOString(), timezone: Intl.DateTimeFormat().resolvedOptions().timeZone });
/** App-owned polling and bounded role calls. Claims and publication stay in the canonical worker. */
export function createStudyCoordinator(options: { storage: StudyStorage; native: StudyNativePort; assessment: StudyAssessmentPort; clock?: () => LocalClock }) {
  const { storage, native, assessment } = options, clock = options.clock ?? systemLocalClock;
  const active = new Map<string, { controller: AbortController; promise: Promise<void> }>();
  let closed = false, timer: ReturnType<typeof setInterval> | undefined, ticking: Promise<unknown> | undefined;
  async function refresh() {
    if (closed) reject('study_closed');
    const job = await storage.command({ type: 'study.home.begin', clock: clock() });
    if (job.fresh) {
      const controller = new AbortController();
      const promise = Promise.resolve().then(async () => {
        try {
          controller.signal.throwIfAborted();
          const bundle = await native.suggestions(job.context, controller.signal);
          controller.signal.throwIfAborted();
          await storage.command({ type: 'study.home.publish', jobId: job.job_id, bundle, clock: clock() });
        } catch (error) {
          const code = error && typeof error === 'object' && 'code' in error ? String(error.code) : 'suggestions_failed';
          await storage.command({ type: 'study.job.stop', jobId: job.job_id, operation: 'daily_suggestions', state: controller.signal.aborted ? 'cancelled' : 'failed', errorCode: /^[a-z][a-z0-9_]{0,79}$/.test(code) ? code : 'suggestions_failed' });
        }
      }).finally(() => active.delete(job.job_id));
      promise.catch(() => {}); active.set(job.job_id, { controller, promise });
    }
    return { job_id: job.job_id, ...await storage.command({ type: 'study.home.read', clock: clock() }) };
  }
  async function stop(id: string, operation: 'daily_suggestions' | 'nightly_test') {
    // Commit the late-publication fence before requesting native cancellation.
    await storage.command({ type: 'study.job.stop', jobId: id, operation, state: 'cancelled', errorCode: 'cancelled' });
    active.get(id)?.controller.abort();
    const status = await storage.command({ type: 'study.nightly.read' });
    if ((status.last_job as { id?: string } | null)?.id === id) await assessment.cancel(id);
    return { id, state: 'cancelled' };
  }
  async function tickOnce() {
    if (closed) return;
    const claimed = await storage.command({ type: 'study.nightly.claim', clock: clock() });
    if (!claimed.request) return storage.command({ type: 'study.nightly.read' });
    const request = claimed.request, controller = new AbortController();
    let id: string | undefined;
    try {
      await storage.command({ type: 'study.nightly.guard', schedule: request.nightly! });
      const job = await assessment.generate(request, controller.signal); id = job.id;
      if (closed) { await stop(id, 'nightly_test'); return; }
      await storage.command({ type: 'study.nightly.attach', schedule: request.nightly!, jobId: id });
    } catch (error) {
      controller.abort(); if (id) await stop(id, 'nightly_test');
      throw error;
    }
    return storage.command({ type: 'study.nightly.read' });
  }
  function tick() {
    if (!ticking) ticking = tickOnce().finally(() => { ticking = undefined; });
    return ticking;
  }
  async function updateNightly(command: Extract<StudyCommand, { type: 'study.nightly.preferences' }>) {
    const before = await storage.command({ type: 'study.nightly.read' });
    const result = await storage.command(command);
    const job = before.last_job as { id: string; state: string } | null;
    if (job && ['queued', 'running'].includes(job.state)) await stop(job.id, 'nightly_test');
    return result;
  }
  return {
    refresh, tick, stop, updateNightly,
    async settled(id: string) { await active.get(id)?.promise; return storage.command({ type: 'study.home.read', clock: clock() }); },
    async start(intervalMs = 30_000) {
      if (timer) return;
      closed = false;
      // Restart invalidates interrupted work; it never replays model inference.
      await storage.command({ type: 'study.nightly.recover', clock: clock() });
      timer = setInterval(() => { tick().catch(() => {}); }, Math.max(1000, intervalMs)); timer.unref();
    },
    async close() {
      closed = true; if (timer) clearInterval(timer); timer = undefined;
      const status = await storage.command({ type: 'study.nightly.read' });
      const job = status.last_job as { id: string; state: string } | null;
      if (job && ['queued', 'running'].includes(job.state)) await stop(job.id, 'nightly_test');
      for (const id of active.keys()) await stop(id, 'daily_suggestions');
      await Promise.allSettled([...active.values()].map(item => item.promise));
      await ticking?.catch(() => {});
    },
  };
}
export type StudyCoordinator = ReturnType<typeof createStudyCoordinator>;
