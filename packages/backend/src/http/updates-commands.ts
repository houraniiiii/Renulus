// SPDX-License-Identifier: MIT
import type { IncomingMessage } from 'node:http';
import { randomUUID } from 'node:crypto';
import type { UpdatesStorage, Review, CheckRoute, ObjectValue } from '../domain/updates/contracts.ts';
import type { UpdatesCoordinator } from '../domain/updates/coordinator.ts';
import { exact, reject, StorageError } from '../storage/contracts.ts';
import { readJsonObject } from './body.ts';
import { withOwnerStatus } from './study-commands.ts';
const INVALID = new Set(['review_source_mismatch', 'review_publication_mismatch', 'corrected_copy_review_required', 'publication_not_registered', 'publication_tracking_limit', 'source_host_blocked', 'schedule_selection_invalid', 'schedule_selection_required', 'schedule_cadence_invalid', 'review_evidence_required', 'review_target_required', 'dismissed_status_change', 'retraction_identity_required', 'replacement_scope_mismatch', 'review_identity_invalid']);
export async function updatesCommand(request: IncomingMessage, url: URL, storage: UpdatesStorage, coordinator: UpdatesCoordinator): Promise<{ status: number; value: unknown } | undefined> {
  if (!url.pathname.startsWith('/api/v1/updates/')) return;
  return withOwnerStatus(async () => {
    try { return await route(request, url, storage, coordinator); }
    catch (error) {
      if (!(error instanceof StorageError) || !INVALID.has(error.code)) throw error;
      return { status: 422, value: { error: { code: error.code, message: error.message, retryable: false } } };
    }
  });
}
async function route(request: IncomingMessage, url: URL, storage: UpdatesStorage, coordinator: UpdatesCoordinator): Promise<{ status: number; value: unknown } | undefined> {
  const path = url.pathname.slice('/api/v1/updates/'.length), method = request.method, query = url.searchParams;
  const result = (value: unknown, status = 200) => ({ status, value });
  const body = () => readJsonObject(request, 128_000);
  const key = () => { const value = request.headers['idempotency-key']; if (value !== undefined && typeof value !== 'string') reject('invalid_request'); return value ?? 'updates-' + randomUUID(); };
  async function shapeCheck(route: CheckRoute, checked: ObjectValue): Promise<ObjectValue> {
    if (route.kind === 'publication') {
      const row = (await storage.command({ type: 'updates.publications' })).publications.find((row: ObjectValue) => row.id === route.id);
      return { ...row, ...(checked.cached ? { cached: true } : {}), ...(checked.state === 'failed' && !checked.cached ? { error: { code: checked.error_code, message: 'Publication check failed. The previous digest and last successful check are retained.' } } : { review_required: checked.state === 'changed' }) };
    }
    if (route.kind === 'literature') return { topic_id: route.id, state: checked.state === 'failed' ? 'failed' : 'checked', discovered: checked.entries?.length ?? 0, records_checked: checked.records_checked ?? 0,
      ...(checked.state === 'failed' ? { error_code: checked.error_code } : { hit_count: checked.hit_count, truncated: Number.isInteger(checked.hit_count) && checked.hit_count > checked.records_checked }) };
    return { source_id: route.id, state: checked.state, ...(checked.cached ? { cached: true } : { checked_at: checked.checked_at }),
      ...(checked.state === 'failed' ? { error: { code: checked.error_code, message: checked.cached ? 'The previous check failed. Its last successful check has not advanced.' : 'The official source could not be checked. Its last successful check remains visible.' } } : checked.cached ? {} : { links: checked.links, review_required: checked.state === 'changed' }) };
  }
  const check = async (route: CheckRoute, force: boolean) => shapeCheck(route, await coordinator.check(route, force));
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
      if (e[2] === 'refresh') { const entry = await storage.command({ type: 'updates.entry', id: e[1] }); return result({ ...await check({ kind: entry.source_metadata.publication_id ? 'publication' : 'source', id: entry.source_metadata.publication_id ?? entry.source_id }, true), entry: await storage.command({ type: 'updates.entry', id: e[1] }) }); }
      if (e[2] === 'review') { const b = await body(); const expectedRevision = (b.expected_revision ?? (await storage.command({ type: 'updates.entry', id: e[1] })).revision) as string; const { expected_revision: _, ...fields } = b; const review = { topic_ids: [], reviewer: 'learner', evidence: [], target: null, changes: {}, ...fields } as unknown as Review; return result(await storage.command({ type: 'updates.review', id: e[1], review, expectedRevision, idempotencyKey: key() })); }
    }
  }
  const source = /^sources\/([A-Z]\d{2})\/(check|status|publications)$/.exec(path);
  if (source) {
    if (method === 'GET' && source[2] === 'status') return result(await storage.command({ type: 'updates.statuses', sourceId: source[1] }));
    if (method === 'POST' && source[2] === 'check') return result(await check({ kind: 'source', id: source[1] }, query.get('force') === 'true'));
    if (method === 'GET' && source[2] === 'publications') { const value = await storage.command({ type: 'updates.sources' }); return result({ candidates: value.sources.find((s: any) => s.source_id === source[1])?.links ?? [] }); }
  }
  if (path === 'publications' && method === 'POST') { const b = await body(); exact(b, ['source_id', 'url', 'permission_reference', ...('max_bytes' in b ? ['max_bytes'] : [])]); return result(await storage.command({ type: 'updates.publications.track', sourceId: b.source_id as string, url: b.url as string, permissionReference: b.permission_reference as string, maxBytes: (b.max_bytes ?? 16_000_000) as number, idempotencyKey: key() }), 201); }
  const pub = /^publications\/([A-Za-z0-9_.:-]+)(\/check)?$/.exec(path);
  if (pub && method === 'POST' && pub[2]) return result(await check({ kind: 'publication', id: pub[1] }, query.get('force') === 'true'));
  if (pub && method === 'DELETE' && !pub[2]) return result(await storage.command({ type: 'updates.publications.stop', id: pub[1] }));
  if (path === 'literature/check' && method === 'POST') {
    const b = await body(); exact(b, ['topic_ids', ...('days' in b ? ['days'] : [])]); if (!Array.isArray(b.topic_ids) || !b.topic_ids.length || b.topic_ids.length > 5 || b.days !== undefined && b.days !== 7) reject('invalid_request');
    const checked_at = new Date().toISOString(), checks: ObjectValue[] = []; for (const id of new Set(b.topic_ids)) checks.push(await check({ kind: 'literature', id: id as string }, true));
    const discovered = checks.reduce((n, item) => n + item.discovered, 0);
    return result({ discovered, checked_at, checks, state: checks.every(item => item.state === 'checked') ? 'checked' : discovered || checks.some(item => item.state === 'checked') ? 'partial' : 'failed', review_state: 'pending', source: 'Europe PMC publication metadata', max_records_per_topic: 25 });
  }
  if (path === 'schedule' && method === 'PUT') { const b = await body(); exact(b, ['enabled', 'cadence_hours', 'selection', ...('expected_revision' in b ? ['expected_revision'] : [])]); const previous = await storage.command({ type: 'updates.schedule.read' }); const value = await storage.command({ type: 'updates.schedule.write', enabled: b.enabled as boolean, cadenceHours: b.cadence_hours as number, selection: b.selection as CheckRoute[], expectedRevision: (b.expected_revision ?? previous.revision) as number, idempotencyKey: key() }); await coordinator.cancel(); return result(value); }
  if (path === 'schedule/check' && method === 'POST') return result(await coordinator.tick(true));
  if (path === 'schedule/cancel' && method === 'POST') return result(await coordinator.cancel());
  if (path === 'digest' && method === 'POST') return result(await coordinator.digest());
  const affected = /^affected\/(question|case)\/([A-Za-z0-9_.:-]+)\/versions\/(\d+)$/.exec(path);
  if (affected && method === 'GET') return result(await storage.command({ type: 'updates.annotations', kind: affected[1] as 'question' | 'case', id: affected[2], version: Number(affected[3]) }));
}
export const handleUpdatesCommand = updatesCommand;
