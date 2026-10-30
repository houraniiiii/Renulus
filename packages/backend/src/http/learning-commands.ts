// SPDX-License-Identifier: MIT
import type { IncomingMessage } from 'node:http';
import type { StorageClient } from '../storage/index.ts';
import type { openSavedLearningTarget } from '../host/learning.ts';
import type { SavedLearningCreate } from '../domain/learning/metadata-contracts.ts';
import { exact, reject } from '../storage/contracts.ts';
import { readJsonObject } from './body.ts';

export type SavedLearning = Awaited<ReturnType<typeof openSavedLearningTarget>>;
type Response = { status: number; value: unknown };
function number(url: URL, name: string, fallback: number) {
  const value = url.searchParams.get(name);
  if (value === null) return fallback;
  if (!/^[0-9]{1,12}$/.test(value)) reject('storage_invalid_command');
  return Number(value);
}
function idempotency(request: IncomingMessage) {
  const value = request.headers['idempotency-key'];
  if (Array.isArray(value)) reject('storage_invalid_command');
  return value ?? null;
}
function native(learning?: SavedLearning) {
  if (!learning) reject('learning_host_unavailable');
  return learning;
}
/** Existing public saved-learning JSON commands, on the same canonical worker.
 * Streaming sends are composed by the facade with their retained native owner.
 */
export async function learningCommand(request: IncomingMessage, url: URL, storage: StorageClient,
  learning?: SavedLearning): Promise<Response | undefined> {
  const result = (value: unknown, status = 200) => ({ status, value });
  const path = url.pathname;
  if (path === '/api/v1/conversations') {
    if (request.method === 'GET') return result(await storage.command({ type: 'learning.list',
      limit: number(url, 'limit', 50), cursor: url.searchParams.get('cursor'),
      lifecycle: (url.searchParams.get('lifecycle') ?? 'active') as 'active' | 'archived', projectId: url.searchParams.get('project_id') }));
    if (request.method === 'POST') {
      const body = await readJsonObject(request, 65536);
      const normalized: SavedLearningCreate = { kind: 'learning', title: 'New chat', temporary: false,
        project_id: null, topic_id: null, teaching_style: 'direct', text: '', teaching_case_id: null,
        ...body } as SavedLearningCreate;
      return result(await storage.command({ type: 'learning.create', request: normalized, idempotencyKey: idempotency(request) }), 201);
    }
  }
  const match = /^\/api\/v1\/conversations\/learning\/([A-Za-z0-9_-]{1,120})(?:\/(.*))?$/.exec(path);
  if (!match) return undefined;
  const threadId = match[1], action = match[2] ?? '';
  if (!action && request.method === 'GET') return result(await storage.command({ type: 'learning.get', threadId }));
  if (!action && request.method === 'DELETE') return result(await native(learning).delete({ type: 'learning.delete', threadId,
    expectedRevision: number(url, 'expected_revision', 0), idempotencyKey: idempotency(request) ?? '' }));
  if (action === 'draft') {
    if (request.method === 'GET') return result(await storage.command({ type: 'learning.draft.get', threadId }));
    if (request.method === 'PUT') {
      const body = await readJsonObject(request, 128 * 1024);
      const normalized = { content_refs: [], ...body };
      return result(await storage.command({ type: 'learning.draft.save', threadId,
        request: normalized as never, idempotencyKey: idempotency(request) }));
    }
  }
  if (['archive', 'restore'].includes(action) && request.method === 'POST') {
    const body = await readJsonObject(request, 4096); exact(body, ['expected_revision']);
    return result(await native(learning).change({ type: 'learning.lifecycle', threadId,
      lifecycle: action === 'archive' ? 'archived' : 'active', expectedRevision: body.expected_revision as number,
      idempotencyKey: idempotency(request) ?? '' }));
  }
  if (action === 'project' && request.method === 'PUT') {
    const body = await readJsonObject(request, 4096);
    exact(body, ['expected_revision', 'project_id']);
    return result(await native(learning).change({ type: 'learning.project', threadId,
      expectedRevision: body.expected_revision as number, projectId: body.project_id as string | null, expectedProjectRevision: null,
      idempotencyKey: idempotency(request) ?? '' }));
  }
  if (action === 'messages' && request.method === 'GET') return result(await native(learning).messages(threadId,
    { limit: number(url, 'limit', 50), ...(url.searchParams.has('cursor') ? { cursor: url.searchParams.get('cursor')! } : {}) }));
  if (action === 'runs' && request.method === 'GET') return result(await storage.command({ type: 'learning.runs.list',
    threadId, limit: number(url, 'limit', 20), cursor: url.searchParams.get('cursor') }));
  const run = /^runs\/([A-Za-z0-9_-]{1,128})(\/cancel)?$/.exec(action);
  if (run && request.method === 'GET' && !run[2]) return result(await storage.command({ type: 'learning.run.status',
    threadId, runId: run[1], neutral: url.searchParams.get('neutral') === 'true' }));
  if (run?.[2] && request.method === 'POST') {
    await storage.command({ type: 'learning.run.status', threadId, runId: run[1], neutral: true });
    await native(learning).cancel(run[1]);
    return result(await storage.command({ type: 'learning.run.status', threadId, runId: run[1], neutral: true }));
  }
  return undefined;
}
