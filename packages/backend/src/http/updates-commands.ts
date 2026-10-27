// SPDX-License-Identifier: MIT
import type { IncomingMessage } from 'node:http';
import type { UpdatesStorage, Review, CheckRoute } from '../domain/updates/contracts.ts';
import type { UpdatesCoordinator } from '../domain/updates/coordinator.ts';
import { exact, reject } from '../storage/contracts.ts';
import { readJsonObject } from './body.ts';
export async function updatesCommand(request: IncomingMessage, url: URL, storage: UpdatesStorage, coordinator: UpdatesCoordinator): Promise<{ status: number; value: unknown } | undefined> {
  if (!url.pathname.startsWith('/api/v1/updates/')) return;
  const path = url.pathname.slice('/api/v1/updates/'.length), method = request.method, query = url.searchParams;
  const result = (value: unknown, status = 200) => ({ status, value });
  const body = () => readJsonObject(request, 128_000);
  const key = () => { const value = request.headers['idempotency-key']; if (typeof value !== 'string') reject('invalid_request'); return value; };
  if (method === 'GET') {
    if (path === 'sources') return result(await storage.command({ type: 'updates.sources' }));
    if (path === 'entries') return result(await storage.command({ type: 'updates.entries', state: (query.get('reviewed_only') === 'true' ? 'reviewed' : query.get('state')) as 'pending' | 'reviewed' | 'dismissed' | null, limit: Number(query.get('limit') ?? 50), offset: Number(query.get('offset') ?? 0) }));
    if (path === 'publications') return result(await storage.command({ type: 'updates.publications' }));
    if (path === 'schedule') return result(await storage.command({ type: 'updates.schedule.read' }));
    if (path === 'literature/checks') return result(await storage.command({ type: 'updates.literature.checks' }));
  }
  const e = /^entries\/([A-Za-z0-9_.:-]+)(?:\/(review|read|sync|affected|refresh))?$/.exec(path);
  if (e) {
    if (method === 'GET' && !e[2]) return result(await storage.command({ type: 'updates.entry', id: e[1] }));
    if (method === 'GET' && e[2] === 'affected') return result(await storage.command({ type: 'updates.affected', id: e[1], limit: Number(query.get('limit') ?? 100), offset: Number(query.get('offset') ?? 0) }));
    if (method === 'POST') {
      if (e[2] === 'read') return result(await storage.command({ type: 'updates.read', id: e[1] }));
      if (e[2] === 'sync') return result(await storage.command({ type: 'updates.sync', id: e[1] }));
      if (e[2] === 'refresh') { const entry = await storage.command({ type: 'updates.entry', id: e[1] }); return result(await coordinator.check({ kind: entry.source_metadata.publication_id ? 'publication' : 'source', id: entry.source_metadata.publication_id ?? entry.source_id }, true)); }
      if (e[2] === 'review') { const b = await body(); const expectedRevision = (b.expected_revision ?? (await storage.command({ type: 'updates.entry', id: e[1] })).revision) as string; const { expected_revision: _, ...fields } = b; const review = { topic_ids: [], reviewer: 'learner', evidence: [], target: null, changes: {}, ...fields } as unknown as Review; return result(await storage.command({ type: 'updates.review', id: e[1], review, expectedRevision, idempotencyKey: key() })); }
    }
  }
  const source = /^sources\/([A-Z]\d{2})\/(check|status|publications)$/.exec(path);
  if (source) {
    if (method === 'GET' && source[2] === 'status') return result(await storage.command({ type: 'updates.statuses', sourceId: source[1] }));
    if (method === 'POST' && source[2] === 'check') return result(await coordinator.check({ kind: 'source', id: source[1] }, query.get('force') === 'true'));
    if (method === 'GET' && source[2] === 'publications') { const value = await storage.command({ type: 'updates.sources' }); return result({ candidates: value.sources.find((s: any) => s.source_id === source[1])?.links ?? [] }); }
  }
  if (path === 'publications' && method === 'POST') { const b = await body(); exact(b, ['source_id', 'url', 'permission_reference', ...('max_bytes' in b ? ['max_bytes'] : [])]); return result(await storage.command({ type: 'updates.publications.track', sourceId: b.source_id as string, url: b.url as string, permissionReference: b.permission_reference as string, maxBytes: (b.max_bytes ?? 16_000_000) as number, idempotencyKey: key() }), 201); }
  const pub = /^publications\/([A-Za-z0-9_.:-]+)(\/check)?$/.exec(path);
  if (pub && method === 'POST' && pub[2]) return result(await coordinator.check({ kind: 'publication', id: pub[1] }, query.get('force') === 'true'));
  if (pub && method === 'DELETE' && !pub[2]) return result(await storage.command({ type: 'updates.publications.stop', id: pub[1] }));
  if (path === 'literature/check' && method === 'POST') { const b = await body(); exact(b, ['topic_ids', ...('days' in b ? ['days'] : [])]); if (!Array.isArray(b.topic_ids) || !b.topic_ids.length || b.topic_ids.length > 5 || b.days !== undefined && b.days !== 7) reject('invalid_request'); const checks = []; for (const id of b.topic_ids) checks.push(await coordinator.check({ kind: 'literature', id: id as string }, true)); return result({ checks }); }
  if (path === 'schedule' && method === 'PUT') { const b = await body(); exact(b, ['enabled', 'cadence_hours', 'selection', ...('expected_revision' in b ? ['expected_revision'] : [])]); const previous = await storage.command({ type: 'updates.schedule.read' }); const value = await storage.command({ type: 'updates.schedule.write', enabled: b.enabled as boolean, cadenceHours: b.cadence_hours as number, selection: b.selection as CheckRoute[], expectedRevision: (b.expected_revision ?? previous.revision) as number, idempotencyKey: key() }); await coordinator.cancel(); return result(value); }
  if (path === 'schedule/check' && method === 'POST') return result(await coordinator.tick(true));
  if (path === 'schedule/cancel' && method === 'POST') return result(await coordinator.cancel());
  if (path === 'digest' && method === 'POST') return result(await coordinator.digest());
  const affected = /^affected\/(question|case)\/([A-Za-z0-9_.:-]+)\/versions\/(\d+)$/.exec(path);
  if (affected && method === 'GET') return result(await storage.command({ type: 'updates.annotations', kind: affected[1] as 'question' | 'case', id: affected[2], version: Number(affected[3]) }));
}
export const handleUpdatesCommand = updatesCommand;
