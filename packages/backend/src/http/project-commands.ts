// SPDX-License-Identifier: MIT
import type { IncomingMessage } from 'node:http';
import { randomUUID } from 'node:crypto';
import { exact, reject } from '../storage/contracts.ts';
import { readJsonObject } from './body.ts';
import type { GoalInput, ProjectStorage } from '../domain/projects/contracts.ts';

export function commandNumber(url: URL, name: string, fallback: number) {
  const value = url.searchParams.get(name); if (value === null) return fallback;
  if (!/^[0-9]{1,12}$/.test(value)) reject('storage_invalid_command'); return Number(value);
}
export function commandKey(request: IncomingMessage) {
  const key = request.headers['idempotency-key']; if (Array.isArray(key)) reject('storage_invalid_command'); return key ?? randomUUID();
}
export async function projectCommand(request: IncomingMessage, url: URL, storage: ProjectStorage): Promise<{ status: number; value: unknown } | undefined> {
  const path = url.pathname, result = (value: unknown, status = 200) => ({ status, value });
  if (path === '/api/v1/study/projects') {
    if (request.method === 'GET') return result(await storage.command({ type: 'project.list', limit: commandNumber(url, 'limit', 50), cursor: url.searchParams.get('cursor'), lifecycle: (url.searchParams.get('lifecycle') ?? 'active') as 'active' | 'archived' }));
    if (request.method === 'POST') { const body = await readJsonObject(request, 4096); exact(body, ['title']);
      return result(await storage.command({ type: 'project.create', title: body.title as string, idempotencyKey: commandKey(request) }), 201); }
  }
  const match = /^\/api\/v1\/study\/projects\/([A-Za-z0-9_-]{1,128})(?:\/(.*))?$/.exec(path); if (!match) return undefined;
  const projectId = match[1], action = match[2] ?? '', idempotencyKey = commandKey(request);
  if (!action && request.method === 'GET') return result(await storage.command({ type: 'project.get', projectId }));
  if (!action && request.method === 'DELETE') return result(await storage.command({ type: 'project.change', projectId, expectedRevision: commandNumber(url, 'expected_revision', 0), action: 'delete', title: null, idempotencyKey }));
  if (!action && request.method === 'PATCH' || ['archive', 'restore'].includes(action) && request.method === 'POST') {
    const body = await readJsonObject(request, 4096); exact(body, action ? ['expected_revision'] : ['expected_revision', 'title']);
    return result(await storage.command({ type: 'project.change', projectId, expectedRevision: body.expected_revision as number, action: action ? action as 'archive' | 'restore' : 'rename', title: action ? null : body.title as string, idempotencyKey }));
  }
  if (action === 'documents' && request.method === 'PUT') {
    const body: Record<string, unknown> = { position: 0, ...await readJsonObject(request, 4096) }; exact(body, ['expected_revision', 'revision_id', 'position']);
    return result(await storage.command({ type: 'project.document', projectId, expectedRevision: body.expected_revision as number, revisionId: body.revision_id as string, position: body.position as number, action: 'link', idempotencyKey }));
  }
  const doc = /^documents\/([A-Za-z0-9_-]{1,128})$/.exec(action);
  if (doc && request.method === 'DELETE') return result(await storage.command({ type: 'project.document', projectId, expectedRevision: commandNumber(url, 'expected_revision', 0), revisionId: doc[1], position: 0, action: 'unlink', idempotencyKey }));
  const goal = /^goals(?:\/([A-Za-z0-9_-]{1,128}))?$/.exec(action);
  if (goal) {
    const goalId = goal[1] ?? null;
    if (goalId && request.method === 'DELETE') return result(await storage.command({ type: 'project.goal', projectId, expectedRevision: commandNumber(url, 'expected_revision', 0), goalId,
      goalRevision: commandNumber(url, 'goal_revision', 0), action: 'delete', input: null, idempotencyKey }));
    if (!goalId && request.method === 'POST' || goalId && request.method === 'PUT') {
      const body: Record<string, unknown> = { topic_id: null, target_date: null, status: 'active', progress: {}, ...await readJsonObject(request, 32768) };
      exact(body, ['expected_revision', 'title', 'topic_id', 'target_date', 'status', 'progress', ...(goalId ? ['goal_revision'] : [])]);
      if (!body.progress || typeof body.progress !== 'object' || Array.isArray(body.progress)) reject('storage_invalid_command');
      const progress = { evidence_ids: [], manual_intent: null, ...body.progress }; exact(progress, ['evidence_ids', 'manual_intent']);
      const input = { title: body.title, topic_id: body.topic_id, target_date: body.target_date, status: body.status, progress } as GoalInput;
      return result(await storage.command({ type: 'project.goal', projectId, expectedRevision: body.expected_revision as number, goalId,
        goalRevision: goalId ? body.goal_revision as number : null, action: 'save', input, idempotencyKey }), goalId ? 200 : 201);
    }
  }
  return undefined;
}
