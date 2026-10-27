// SPDX-License-Identifier: MIT
import type { IncomingMessage } from 'node:http';
import type { StudyStorage, StudyGoals, LocalClock, Activity } from '../domain/study/contracts.ts';
import type { StudyCoordinator } from '../domain/study/coordinator.ts';
import { systemLocalClock } from '../domain/study/coordinator.ts';
import { exact, reject } from '../storage/contracts.ts';
import { readJsonObject } from './body.ts';
export async function studyCommand(request: IncomingMessage, url: URL, storage: StudyStorage, coordinator: StudyCoordinator, clock: () => LocalClock = systemLocalClock): Promise<{ status: number; value: unknown } | undefined> {
  const path = url.pathname.replace(/^\/api\/v1\//, ''), method = request.method;
  if (!/^(home|nightly|study)(\/|$)/.test(path)) return;
  const result = (value: unknown, status = 200) => ({ status, value });
  const body = () => readJsonObject(request, 32_768);
  const key = () => { const value = request.headers['idempotency-key']; if (typeof value !== 'string') reject('invalid_request'); return value; };
  if (method === 'GET') {
    if (path === 'home' || path === 'study/home') return result(await storage.command({ type: 'study.home.read', clock: clock() }));
    if (path === 'home/preferences') return result(await storage.command({ type: 'study.preferences.read' }));
    if (path === 'nightly') return result(await storage.command({ type: 'study.nightly.read' }));
    if (path === 'nightly/preferences') return result((await storage.command({ type: 'study.nightly.read' })).preferences);
    if (path === 'study/goals') return result(await storage.command({ type: 'study.goals.read' }));
    if (path === 'study/plan' || path === 'study/progress') return result(await storage.command({ type: 'study.plan.read', clock: clock() }));
  }
  if (method === 'PUT' && path === 'home/preferences') { const b = await body(); exact(b, ['doctor_name', 'expected_revision']); return result(await storage.command({ type: 'study.preferences.write', doctorName: b.doctor_name as string | null, expectedRevision: b.expected_revision as number, idempotencyKey: key() })); }
  if (method === 'PUT' && path === 'study/goals') { const b = await body(); const revision = b.expected_revision ?? (await storage.command({ type: 'study.goals.read' })).revision; const { expected_revision: _, ...goals } = b; return result(await storage.command({ type: 'study.goals.write', goals: goals as unknown as StudyGoals, expectedRevision: revision as number, idempotencyKey: key() })); }
  if (method === 'PUT' && path === 'nightly/preferences') { const b = await body(); exact(b, ['enabled', 'local_time', 'question_count', 'expected_revision']); return result(await coordinator.updateNightly({ type: 'study.nightly.preferences', enabled: b.enabled as boolean, localTime: b.local_time as string, count: b.question_count as 5 | 10 | 20, expectedRevision: b.expected_revision as number, clock: clock(), idempotencyKey: key() })); }
  if (method === 'POST' && path === 'home/suggestions/refresh') { key(); return result(await coordinator.refresh(), 202); }
  const stop = /^(?:nightly|home)\/jobs\/([A-Za-z0-9_.:-]+)\/cancel$/.exec(path);
  if (method === 'POST' && stop) { key(); return result(await coordinator.stop(stop[1])); }
  if (method === 'POST' && path === 'study/plan/propose') { const b = await body(); exact(b, [...('stamp' in b ? ['stamp'] : [])]); const plan = await storage.command({ type: 'study.plan.read', clock: clock() }); return result(await storage.command({ type: 'study.plan.accept', clock: clock(), stamp: (b.stamp ?? plan.stamp) as string, idempotencyKey: key() })); }
  const activity = /^study\/plan\/([A-Za-z0-9_.:-]+)$/.exec(path);
  if (method === 'PATCH' && activity) { const b = await body(); exact(b, ['expected_revision', ...('state' in b ? ['state'] : []), ...('due_date' in b ? ['due_date'] : [])]); return result(await storage.command({ type: 'study.activity.change', id: activity[1], expectedRevision: b.expected_revision as string, dueDate: (b.due_date ?? null) as string | null, state: (b.state ?? null) as Activity['state'] | null, idempotencyKey: key() })); }
}
export const handleStudyCommand = studyCommand;
