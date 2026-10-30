// SPDX-License-Identifier: MIT
import type { IncomingMessage } from 'node:http';
import type { MemoryStorage, MemoryScope } from '../domain/memory/contracts.ts';
import type { MemoryHost } from '../host/memory.ts';
import { exact, reject } from '../storage/contracts.ts';
import { readJsonObject } from './body.ts';

/** Existing /api/v1/memory facade, with cleanup awaited for correction/delete. */
export async function memoryCommand(request: IncomingMessage, url: URL, storage: MemoryStorage, host?: MemoryHost): Promise<{ status: number; value: unknown } | undefined> {
  const result = (value: unknown, status = 200) => ({ status, value });
  const native = () => { if (!host) reject('memory_host_unavailable'); return host; };
  const path = url.pathname;
  if (!path.startsWith('/api/v1/memory/')) return undefined;
  if (path === '/api/v1/memory/status' && request.method === 'GET') {
    const status = await storage.command({ type: 'memory.status' });
    return result({ index: { ready: status.state === 'ready', state: status.state, error_code: status.error_code }, pending_jobs: status.pending, producer: 'mem0-oss', automatic_capture: true });
  }
  if (path === '/api/v1/memory/facts') {
    if (request.method === 'GET') return result(await storage.command({ type: 'memory.list', offset: Number(url.searchParams.get('offset') ?? 0), limit: Number(url.searchParams.get('limit') ?? 100) }));
    if (request.method === 'POST') {
      const body = await readJsonObject(request, 16384);
      const input = { kind: 'learning-point', topic_id: null, scope: { kind: 'study' }, ...body };
      exact(input, ['text', 'kind', 'topic_id', 'scope', 'idempotency_key']);
      return result(await native().add(input as Parameters<MemoryHost['add']>[0]), 201);
    }
  }
  if (path === '/api/v1/memory/export' && request.method === 'GET') return result(await storage.command({ type: 'memory.export' }));
  if (path === '/api/v1/memory/jobs' && request.method === 'GET') return result({ jobs: await storage.command({ type: 'memory.jobs', recover: false }) });
  if (path === '/api/v1/memory/captures' && request.method === 'POST') {
    const body = await readJsonObject(request, 4096); exact(body, ['evidence_id', 'scope']);
    if ((body.scope as MemoryScope)?.kind !== 'study') reject('memory_scope_excluded');
    await native().captureEvidence(body.evidence_id as string, true, true);
    const jobs = await storage.command({ type: 'memory.jobs', recover: false });
    return result(jobs.filter(j => j.evidence_id === body.evidence_id).at(-1), 202);
  }
  if (path === '/api/v1/memory/search' && request.method === 'POST') {
    const body = await readJsonObject(request, 16384);
    const input = { limit: 10, budget_chars: 4000, ...body }; exact(input, ['query', 'scope', 'limit', 'budget_chars']);
    return result(await native().recall(input as Parameters<MemoryHost['recall']>[0]));
  }
  if (path === '/api/v1/memory/retry' && request.method === 'POST') return result(await native().retry());
  if (path === '/api/v1/memory/reindex' && request.method === 'POST') {
    await native().rebuild(); return result({ ready: true, count: (await storage.command({ type: 'memory.export' })).records.length });
  }
  const job = /^\/api\/v1\/memory\/jobs\/([A-Za-z0-9_-]{1,120})\/cancel$/.exec(path);
  if (job && request.method === 'POST') {
    await native().cancel(job[1]);
    return result((await storage.command({ type: 'memory.jobs', recover: false })).find(j => j.id === job[1]));
  }
  const match = /^\/api\/v1\/memory\/facts\/([A-Za-z0-9_-]{1,120})(\/history)?$/.exec(path);
  if (!match) return undefined;
  const id = match[1];
  if (request.method === 'GET') {
    const record = await storage.command({ type: 'memory.inspect', id });
    return result(match[2] ? { history: record.history } : record);
  }
  if (request.method === 'DELETE') return result(match[2] ? await native().purgeHistory(id) : await native().delete(id, Number(url.searchParams.get('expected_revision'))));
  if (!match[2] && request.method === 'PATCH') {
    const body = await readJsonObject(request, 16384); exact(body, ['text', 'expected_revision']);
    return result(await native().correct(id, body.text as string, body.expected_revision as number));
  }
  return undefined;
}
