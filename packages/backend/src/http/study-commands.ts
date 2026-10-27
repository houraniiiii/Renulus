// SPDX-License-Identifier: MIT
import type { IncomingMessage } from 'node:http';
import { randomUUID } from 'node:crypto';
import type { StudyGoals, LocalClock, Activity } from '../domain/study/contracts.ts';
import type { StudyCoordinator } from '../domain/study/coordinator.ts';
import { systemLocalClock } from '../domain/study/coordinator.ts';
import type { StorageClient } from '../storage/index.ts';
import { StorageError, exact } from '../storage/contracts.ts';
import { localDay } from '../storage/study.ts';
import { readJsonObject, RequestBodyError } from './body.ts';

/** The existing Python API answered these owner codes with 404 and validation with 422. */
const MISSING = new Set(['not_found', 'activity_missing', 'update_missing', 'source_missing', 'publication_missing', 'topic_missing']);
const INVALID = new Set(['invalid_request', 'storage_invalid_command', 'updates_invalid']);
export async function withOwnerStatus(run: () => Promise<{ status: number; value: unknown } | undefined>) {
  try { return await run(); } catch (error) {
    if (!(error instanceof StorageError)) throw error;
    const status = MISSING.has(error.code) ? 404 : INVALID.has(error.code) ? 422 : 0;
    if (!status) throw error;
    return { status, value: { error: { code: error.code, message: 'The local operation could not be completed. Inspect its current state before retrying.', retryable: false } } };
  }
}
export async function studyCommand(request: IncomingMessage, url: URL, storage: StorageClient, coordinator: StudyCoordinator, clock: () => LocalClock = systemLocalClock): Promise<{ status: number; value: unknown } | undefined> {
  const path = url.pathname.replace(/^\/api\/v1\//, ''), method = request.method;
  if (!/^(home|nightly|study)(\/|$)/.test(path)) return;
  return withOwnerStatus(() => route(request, path, method, storage, coordinator, clock));
}
async function route(request: IncomingMessage, path: string, method: string | undefined, storage: StorageClient, coordinator: StudyCoordinator, clock: () => LocalClock) {
  const result = (value: unknown, status = 200) => ({ status, value });
  const body = () => readJsonObject(request, 32_768);
  const header = () => { const value = request.headers['idempotency-key']; return typeof value === 'string' ? value : undefined; };
  // Python required the header for Home/Nightly settings; plan and goals never did, so those mint a request key.
  const key = () => header() ?? (() => { throw new RequestBodyError(422); })();
  const optionalKey = () => header() ?? 'study-' + randomUUID();
  const goals = async () => (await storage.command({ type: 'study.goals.read' })).goals as StudyGoals;
  if (method === 'GET') {
    if (path === 'home') return result(await storage.command({ type: 'study.home.read', clock: clock() }));
    if (path === 'home/preferences') return result(await storage.command({ type: 'study.preferences.read' }));
    if (path === 'nightly') return result(await storage.command({ type: 'study.nightly.read' }));
    if (path === 'nightly/preferences') return result((await storage.command({ type: 'study.nightly.read' })).preferences);
    if (path === 'study/goals') return result(await goals());
    if (path === 'study/plan') return result(await storage.command({ type: 'study.plan.read' }));
    if (path === 'study/progress') return result(await storage.command({ type: 'study.progress' }));
    if (path === 'study/home') {
      const plan = await storage.command({ type: 'study.plan.read' }), today = localDay(clock());
      const planned = plan.activities.filter((a: Activity) => a.state === 'planned');
      const [resume, topics, updates, progress] = await Promise.all([
        storage.command({ type: 'learning.list', limit: 3, cursor: null, lifecycle: 'active', projectId: null }),
        storage.command({ type: 'content.topics' }), storage.command({ type: 'updates.entries', state: 'reviewed', limit: 3, offset: 0 }),
        storage.command({ type: 'study.progress' })]);
      return result({ resume: resume.items.slice(0, 3), review: planned.filter((a: Activity) => a.due_date <= today).slice(0, 3), upcoming: planned.slice(0, 5),
        topics: topics.items, goals: await goals(), tracks: plan.tracks, selection: plan.selection, progress, updates: updates.entries });
    }
  }
  if (method === 'PUT' && path === 'home/preferences') { const b = await body(); exact(b, ['expected_revision', ...('doctor_name' in b ? ['doctor_name'] : [])]); return result(await storage.command({ type: 'study.preferences.write', doctorName: (b.doctor_name ?? null) as string | null, expectedRevision: b.expected_revision as number, idempotencyKey: key() })); }
  if (method === 'PUT' && path === 'study/goals') {
    const b = await body(), { expected_revision: expected, ...values } = b;
    const next = { hours_per_week: 3, exam_date: null, topic_ids: [], track: 'general', ...values } as StudyGoals;
    const saved = await storage.command({ type: 'study.goals.write', goals: next, expectedRevision: (expected ?? (await storage.command({ type: 'study.goals.read' })).revision) as number, idempotencyKey: optionalKey() });
    return result(saved.goals);
  }
  if (method === 'PUT' && path === 'nightly/preferences') {
    const b = await body(); exact(b, ['expected_revision', ...['enabled', 'local_time', 'question_count'].filter(k => k in b)]);
    return result(await coordinator.updateNightly({ type: 'study.nightly.preferences', enabled: (b.enabled ?? false) as boolean, localTime: (b.local_time ?? '22:00') as string, count: (b.question_count ?? 5) as 5 | 10 | 20, expectedRevision: b.expected_revision as number, clock: clock(), idempotencyKey: key() }));
  }
  if (method === 'POST' && path === 'home/suggestions/refresh') { key(); return result(await coordinator.refresh(), 202); }
  const stop = /^(?:nightly|home)\/jobs\/([A-Za-z0-9_.:-]+)\/cancel$/.exec(path);
  if (method === 'POST' && stop) { key(); return result(await coordinator.stop(stop[1])); }
  if (method === 'POST' && path === 'study/plan/propose') return result(await storage.command({ type: 'study.plan.propose', clock: clock() }));
  const change = /^study\/plan\/([A-Za-z0-9_.:-]+)$/.exec(path);
  if (method === 'PATCH' && change) {
    const b = await body(); exact(b, [...['expected_revision', 'state', 'due_date'].filter(k => k in b)]);
    const current = (await storage.command({ type: 'study.plan.read' })).activities.find((a: Activity) => a.id === change[1]);
    return result(await storage.command({ type: 'study.activity.change', id: change[1], expectedRevision: (b.expected_revision ?? current?.revision ?? 'a'.repeat(64)) as string, dueDate: (b.due_date ?? null) as string | null, state: (b.state ?? null) as Activity['state'] | null, idempotencyKey: optionalKey() }));
  }
}
export const handleStudyCommand = studyCommand;
