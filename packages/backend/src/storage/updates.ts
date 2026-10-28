// SPDX-License-Identifier: MIT
// Synchronous local functions; the integration-owned worker supplies the transaction.
import type { DatabaseSync } from 'node:sqlite';
import { randomUUID } from 'node:crypto';
import type { UpdatesCommand, UpdatesResults, ObjectValue, SourceTarget, CheckInput, CheckRoute } from '../domain/updates/contracts.ts';
import { hash, https, route, validateReview, observation, matches, article } from '../domain/updates/validation.ts';
import { canonical, digest, one, rows } from './schema.ts';
import { exact, integer, reject, text } from './contracts.ts';
import { requireAssistance } from './conversation.ts';
import { utcNow } from './export.ts';
import { studyPreference, saveStudyPreference, bumpStudyContext } from './study.ts';
import { projectKnowledgeSourceStatus } from './knowledge.ts';
import { reconcileMemorySupport } from './memory.ts';
const sha = (value: unknown) => digest(canonical(value));
const parse = (value: unknown): any => JSON.parse(String(value));
const uid = (prefix: string) => prefix + '_' + randomUUID().replaceAll('-', '');
const stamp = (db: DatabaseSync) => sha({ epoch: studyPreference(db, 'design_c.context_epoch', 0), policy: studyPreference(db, 'design_c.assessment_policy_revision', 1), cancellation: studyPreference(db, 'updates.cancel_revision', 0) });
const revision = (row: unknown) => sha(row);
function checkpoint(input: CheckInput) { exact(input, ['route', 'token', 'stamp', 'target', 'previous_digest', 'checked_at']); route(input.route); text(input.token, 1, 128); hash(input.stamp); if (input.previous_digest !== null) hash(input.previous_digest); text(input.checked_at, 20, 40); if (!Number.isFinite(Date.parse(input.checked_at)) || !input.target || typeof input.target !== 'object' || Array.isArray(input.target)) reject('updates_invalid'); }
export function isUpdatesCommand(v: unknown): v is UpdatesCommand { return !!v && typeof v === 'object' && 'type' in v && typeof v.type === 'string' && v.type.startsWith('updates.'); }
export function validateUpdatesCommand(c: UpdatesCommand): void {
  switch (c.type) {
    case 'updates.sources': case 'updates.publications': case 'updates.schedule.read': case 'updates.schedule.stop': case 'updates.literature.checks': case 'updates.recover': exact(c, ['type']); break;
    case 'updates.entry': case 'updates.read': case 'updates.sync': case 'updates.publications.stop': exact(c, ['type', 'id']); text(c.id, 1, 128); break;
    case 'updates.statuses': exact(c, ['type', 'sourceId']); text(c.sourceId, 3, 3); break;
    case 'updates.entries': exact(c, ['type', 'state', 'limit', 'offset']); if (c.state !== null && !['pending', 'reviewed', 'dismissed'].includes(c.state)) reject('updates_invalid'); integer(c.limit, 1, 250); integer(c.offset, 0); break;
    case 'updates.affected': exact(c, ['type', 'id', 'limit', 'offset']); text(c.id, 1, 128); integer(c.limit, 1, 250); integer(c.offset, 0); break;
    case 'updates.annotations': exact(c, ['type', 'kind', 'id', 'version']); if (!['question', 'case'].includes(c.kind)) reject('updates_invalid'); text(c.id, 1, 128); integer(c.version, 1); break;
    case 'updates.review': exact(c, ['type', 'id', 'review', 'expectedRevision', 'idempotencyKey']); text(c.id, 1, 128); hash(c.expectedRevision); validateReview(c.review); break;
    case 'updates.publications.track': exact(c, ['type', 'sourceId', 'url', 'permissionReference', 'maxBytes', 'idempotencyKey']); text(c.sourceId, 3, 3); https(c.url); text(c.permissionReference, 1, 1000); integer(c.maxBytes, 1024, 20_000_000); break;
    case 'updates.check.begin': exact(c, ['type', 'route', 'force']); route(c.route); if (typeof c.force !== 'boolean') reject('updates_invalid'); break;
    case 'updates.check.current': exact(c, ['type', 'input']); checkpoint(c.input); break;
    case 'updates.check.finish': exact(c, ['type', 'input', 'observation', 'errorCode']); checkpoint(c.input); if (c.observation !== null) observation(c.observation); if (c.errorCode !== null) text(c.errorCode, 1, 80); if ((c.observation === null) === (c.errorCode === null)) reject('updates_invalid'); break;
    case 'updates.schedule.write': exact(c, ['type', 'enabled', 'cadenceHours', 'selection', 'expectedRevision', 'idempotencyKey']); if (typeof c.enabled !== 'boolean' || !Array.isArray(c.selection) || c.selection.length > 20) reject('updates_invalid'); integer(c.cadenceHours, 24, 720); integer(c.expectedRevision, 1); c.selection.forEach(route); if (new Set(c.selection.map(v => v.kind + ':' + v.id)).size !== c.selection.length) reject('updates_invalid'); break;
    case 'updates.schedule.claim': exact(c, ['type', 'manual']); if (typeof c.manual !== 'boolean') reject('updates_invalid'); break;
    case 'updates.schedule.finish': exact(c, ['type', 'id', 'checked', 'failed', 'errorCode']); text(c.id, 1, 128); integer(c.checked, 0, 20); integer(c.failed, 0, 20); if (c.errorCode !== null) text(c.errorCode, 1, 80); break;
    case 'updates.digest.input': exact(c, ['type', 'limit']); integer(c.limit, 1, 50); break;
    case 'updates.digest.current': exact(c, ['type', 'stamp', 'limit']); hash(c.stamp); integer(c.limit, 1, 50); break;
    default: reject('updates_invalid');
  }
  if ('idempotencyKey' in c) text(c.idempotencyKey, 8, 128);
}
function receipt(db: DatabaseSync, c: UpdatesCommand & { idempotencyKey: string }, mutate: () => ObjectValue) {
  const { idempotencyKey, ...payload } = c, key = 'updates.receipt.' + sha(idempotencyKey), old = studyPreference<any>(db, key, null), hash = sha(payload);
  if (old) { if (old.hash !== hash) reject('idempotency_conflict'); return old.result; }
  const result = mutate(); saveStudyPreference(db, key, { hash, result }); return result;
}
function entry(db: DatabaseSync, id: string): ObjectValue {
  const row = one(db, 'SELECT * FROM update_entries WHERE id=?', id); if (!row) reject('update_missing');
  const { topic_ids_json, source_metadata_json, ...rest } = row;
  const head = one(db, 'SELECT r.* FROM update_review_heads h JOIN update_reviews r ON r.id=h.review_id WHERE h.entry_id=?', id);
  return { ...rest, topic_ids: parse(topic_ids_json), source_metadata: parse(source_metadata_json), revision: revision(row), review: head ? { id: head.id, target: parse(head.target_json), changes: parse(head.changes_json), evidence: parse(head.evidence_json), library_sync_state: head.library_sync_state, library_sync_error: head.library_sync_error } : null,
    library_changes: rows(db, 'SELECT id,state,error_code FROM update_library_changes WHERE entry_id=? ORDER BY rowid', id) };
}
function freshness(row: ObjectValue) {
  if (!row.last_success_at) return 'unchecked';
  return row.state === 'failed' || Date.now() - Date.parse(row.last_success_at) > 7 * 86400_000 ? 'stale' : 'checked-recently';
}
function target(db: DatabaseSync, r: CheckRoute): ObjectValue {
  if (r.kind === 'source') { const row = one(db, 'SELECT * FROM update_source_checks WHERE source_id=?', r.id); if (!row) reject('source_missing'); return row; }
  if (r.kind === 'publication') { const row = one(db, 'SELECT * FROM update_publications WHERE id=? AND enabled=1', r.id); if (!row) reject('publication_missing'); return row; }
  if (!one(db, 'SELECT 1 FROM content_topics WHERE topic_id=?', r.id)) reject('topic_missing');
  return one(db, 'SELECT * FROM update_literature_checks WHERE topic_id=?', r.id) ?? { topic_id: r.id };
}
const checkKey = (r: CheckRoute) => 'updates.check.' + sha(r);
function currentCheck(db: DatabaseSync, input: CheckInput) {
  requireAssistance(db); const state = studyPreference<any>(db, checkKey(input.route), null);
  if (input.stamp !== stamp(db) || !state || state.token !== input.token || state.state !== 'running' || sha(target(db, input.route)) !== sha(input.target)) reject('updates_check_invalidated');
}
function cancelChecks(db: DatabaseSync) {
  saveStudyPreference(db, 'updates.cancel_revision', studyPreference(db, 'updates.cancel_revision', 0) + 1);
  for (const r of rows(db, "SELECT key,value FROM preferences WHERE key LIKE 'updates.check.%'")) { const v = parse(r.value); if (v.state === 'running') saveStudyPreference(db, String(r.key), { ...v, state: 'cancelled' }); }
}
function enqueue(db: DatabaseSync, id: string, entryId: string, t: SourceTarget, changes: ObjectValue, evidence: unknown, reason: string) {
  const { register_id: source_id, topic_ids = [], locators = [], ...identity } = t;
  const payload = { contract_version: 1, event_id: id, source_id, identity, scope: { topic_ids, locators }, changes, evidence, reason };
  db.prepare('INSERT OR IGNORE INTO update_library_changes(id,entry_id,payload_json) VALUES(?,?,?)').run(id, entryId, canonical(payload));
}
function syncOne(db: DatabaseSync, id: string) {
  const row = one(db, 'SELECT * FROM update_library_changes WHERE id=?', id); if (!row) reject('source_change_missing');
  const payload = parse(row.payload_json), h = sha(payload), prior = one(db, 'SELECT request_hash FROM knowledge_source_status_events WHERE id=?', id);
  if (prior && prior.request_hash !== h) reject('idempotency_conflict');
  if (prior) return row.result_json ? parse(row.result_json) : { event_id: id, state: row.state };
  const now = utcNow();
  db.prepare('INSERT INTO knowledge_source_status_events(id,source_id,request_hash,payload_json,created_at) VALUES(?,?,?,?,?)').run(id, payload.source_id, h, canonical(payload), now);
  const count = projectKnowledgeSourceStatus(db, payload.source_id), result = { event_id: id, state: count ? 'applied' : 'no-match', matched: count };
  db.prepare('UPDATE update_library_changes SET state=?,last_attempt_at=?,error_code=NULL,result_json=? WHERE id=?').run(result.state, now, canonical(result), id);
  db.prepare('UPDATE update_reviews SET library_sync_state=?,library_sync_error=NULL,library_result_json=? WHERE id=?').run(result.state, canonical(result), id);
  bumpStudyContext(db); reconcileMemorySupport(db); return result;
}
function sync(db: DatabaseSync, entryId: string) {
  // Preserve journal order even when a prior Python delivery was interrupted.
  const results = rows(db, "SELECT id FROM update_library_changes WHERE rowid<=(SELECT MAX(rowid) FROM update_library_changes WHERE entry_id=?) AND state NOT IN ('applied','no-match') ORDER BY rowid", entryId).map(r => syncOne(db, String(r.id)));
  return { entry_id: entryId, results };
}
function publicationTarget(t: SourceTarget): SourceTarget { const { edition: _, original_sha256: __, ...result } = t; if (result.canonical_url || Object.keys(article(result)).length) delete result.pinned_source_id; return result; }
function invalidate(db: DatabaseSync, t: SourceTarget) {
  for (const r of rows(db, 'SELECT target_key,target_json,status_json FROM update_source_statuses')) if (matches(parse(r.target_json), publicationTarget(t))) db.prepare('UPDATE update_source_statuses SET status_json=? WHERE target_key=?').run(canonical({ ...parse(r.status_json), latest_final_verified: false, content_reviewed: false }), r.target_key);
}
function affected(db: DatabaseSync, entryId: string, t: SourceTarget, reason: string) {
  for (const [kind, table, key] of [['question', 'content_question_versions', 'question_id'], ['case', 'content_case_versions', 'case_id']]) {
    // Only source metadata projections cross the Updates boundary: no stems, cases, or keys.
    for (const r of rows(db, `SELECT ${key} AS entity_id,version,json_extract(body_json,'$.source_records') AS records,json_extract(body_json,'$.sources') AS citations,json_extract(body_json,'$.topic_id') AS topic_id,json_extract(body_json,'$.secondary_topic_ids') AS secondary,json_extract(body_json,'$.objective_ids') AS objectives,(SELECT json_group_array(json_extract(stage.value,'$.sources')) FROM json_each(body_json,'$.stages') stage) AS stages FROM ${table}`)) {
      if (t.topic_ids?.length && !t.topic_ids.some(id => [r.topic_id, ...parse(r.secondary ?? '[]')].includes(id))) continue;
      const citations = [...parse(r.citations ?? '[]'), ...parse(r.stages ?? '[]').flatMap((v: any) => typeof v === 'string' ? parse(v) : v ?? [])];
      for (const source of parse(r.records ?? '[]')) if (matches(source, t)) {
        const locators = [...new Set(citations.filter((c: any) => c.source_id === source.id && (!t.locators?.length || t.locators.includes(c.locator))).map((c: any) => c.locator))]; if (!locators.length) continue;
        db.prepare("INSERT INTO update_affected_versions(entry_id,kind,entity_id,version,pinned_source_id,register_id,locators_json,topic_id,objective_ids_json,detected_at,basis) VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(entry_id,kind,entity_id,version,pinned_source_id) DO UPDATE SET locators_json=excluded.locators_json,basis=excluded.basis,state='needs-re-review'").run(entryId, kind, r.entity_id, r.version, source.id, source.register_id, canonical(locators), r.topic_id, r.objectives ?? '[]', utcNow(), reason);
      }
    }
  }
}
function schedule(db: DatabaseSync): ObjectValue { return { ...one(db, 'SELECT * FROM update_schedule WHERE id=1'), revision: studyPreference(db, 'updates.schedule_revision', 1), selection: rows(db, 'SELECT kind,target_id AS id,next_due_at,last_attempt_at,last_success_at,state,error_code FROM update_schedule_jobs ORDER BY kind,target_id'), app_running_only: true, running: one(db, "SELECT * FROM update_schedule_runs WHERE state='running' ORDER BY started_at DESC LIMIT 1") ?? null }; }
function digestInput(db: DatabaseSync, limit: number) {
  requireAssistance(db); const entries = rows(db, 'SELECT id,title,url,review_state,summary,reviewed_at,discovered_at,source_id FROM update_entries ORDER BY discovered_at DESC,id DESC LIMIT ?', limit);
  return { stamp: sha({ context: stamp(db), entries }), entries, checked_at: utcNow(), limit };
}
export function executeUpdates<C extends UpdatesCommand>(db: DatabaseSync, c: C): UpdatesResults[C['type']] {
  validateUpdatesCommand(c); let result: ObjectValue;
  const neutral = ['updates.schedule.read', 'updates.schedule.write', 'updates.schedule.stop', 'updates.schedule.finish', 'updates.recover', 'updates.publications.stop'];
  if (!neutral.includes(c.type)) requireAssistance(db);
  switch (c.type) {
    case 'updates.sources': result = { sources: rows(db, 'SELECT * FROM update_source_checks ORDER BY source_id').map(({ links_json, ...r }) => ({ ...r, links: parse(links_json), freshness: freshness(r), currentness: 'Source snapshot and checks do not establish clinical review.' })) }; break;
    case 'updates.entries': { const counts = { pending: 0, reviewed: 0, dismissed: 0 }; for (const r of rows(db, 'SELECT review_state,COUNT(*) AS n FROM update_entries GROUP BY review_state')) counts[r.review_state as keyof typeof counts] = Number(r.n); const entries = rows(db, 'SELECT id FROM update_entries ' + (c.state ? 'WHERE review_state=? ' : '') + 'ORDER BY discovered_at DESC,id DESC LIMIT ? OFFSET ?', ...(c.state ? [c.state] : []), c.limit, c.offset).map(r => entry(db, String(r.id))); const total = c.state ? counts[c.state] : Object.values(counts).reduce((a, b) => a + b, 0); result = { entries, counts, total, limit: c.limit, offset: c.offset, next_offset: c.offset + entries.length < total ? c.offset + entries.length : null }; break; }
    case 'updates.entry': result = entry(db, c.id); break;
    case 'updates.read': entry(db, c.id); db.prepare('UPDATE update_entries SET read_at=? WHERE id=?').run(utcNow(), c.id); result = { read: true }; break;
    case 'updates.statuses': result = { statuses: rows(db, 'SELECT * FROM update_source_statuses').filter(r => parse(r.target_json).register_id === c.sourceId).map(r => ({ target: parse(r.target_json), status: parse(r.status_json), review_id: r.review_id })) }; break;
    case 'updates.affected': entry(db, c.id); result = { affected: rows(db, 'SELECT * FROM update_affected_versions WHERE entry_id=? ORDER BY kind,entity_id,version LIMIT ? OFFSET ?', c.id, c.limit, c.offset).map(r => ({ ...r, locators: parse(r.locators_json), objective_ids: parse(r.objective_ids_json) })) }; break;
    case 'updates.annotations': { const annotations = rows(db, 'SELECT a.*,e.url,e.title,e.review_state FROM update_affected_versions a JOIN update_entries e ON e.id=a.entry_id WHERE a.kind=? AND a.entity_id=? AND a.version=? ORDER BY a.detected_at,a.entry_id', c.kind, c.id, c.version); result = { kind: c.kind, id: c.id, version: c.version, needs_re_review: annotations.some(r => r.state === 'needs-re-review'), annotations }; break; }
    case 'updates.review': result = receipt(db, c, () => {
      const e = entry(db, c.id), r = c.review, now = utcNow(), reviewId = uid('review'); if (e.revision !== c.expectedRevision) reject('revision_conflict');
      let t = r.target ? { ...r.target, ...article(r.target) } : null, changes = { ...r.changes };
      if (t && (t.register_id !== e.source_id || !one(db, 'SELECT 1 FROM update_source_checks WHERE source_id=?', t.register_id))) reject('review_source_mismatch');
      if (t && e.source_metadata.publication_id && t.canonical_url !== e.source_metadata.canonical_url) reject('review_publication_mismatch');
      const invalidates = !!changes.correction || !!changes.replaced_topics?.length || !!changes.excluded_pages?.length || ['retracted', 'superseded', 'repository_removed'].some(k => changes[k] === true) || 'publication_status' in changes && changes.publication_status !== 'final';
      if (t && invalidates) { changes = { ...changes, latest_final_verified: false, content_reviewed: false }; invalidate(db, t); const broad = publicationTarget(t); if (changes.retracted || changes.repository_removed) { delete broad.topic_ids; delete broad.locators; } enqueue(db, 'invalidate:' + reviewId, c.id, broad, { latest_final_verified: false, content_reviewed: false }, r.evidence, 'Source notice invalidates prior review'); }
      if (t && !invalidates && (changes.latest_final_verified || changes.content_reviewed) && !t.edition && rows(db, 'SELECT target_json,status_json FROM update_source_statuses').some(s => matches(parse(s.target_json), publicationTarget(t!)) && parse(s.status_json).correction)) reject('corrected_copy_review_required');
      db.prepare('INSERT INTO update_reviews(id,entry_id,target_json,changes_json,evidence_json,summary,topic_ids_json,reviewer,state,reviewed_at) VALUES(?,?,?,?,?,?,?,?,?,?)').run(reviewId, c.id, canonical(t), canonical(changes), canonical(r.evidence), r.summary.trim(), canonical(r.topic_ids), r.reviewer, r.state, now);
      db.prepare('INSERT INTO update_review_heads VALUES(?,?) ON CONFLICT(entry_id) DO UPDATE SET review_id=excluded.review_id').run(c.id, reviewId);
      db.prepare('UPDATE update_entries SET summary=?,topic_ids_json=?,reviewer=?,reviewed_at=?,review_state=? WHERE id=?').run(r.summary.trim(), canonical(r.topic_ids), r.reviewer, now, r.state, c.id);
      db.prepare('UPDATE update_affected_versions SET state=? WHERE entry_id=?').run(r.state === 'dismissed' ? 'dismissed' : 'needs-re-review', c.id);
      if (t && Object.keys(changes).length) {
        if (changes.replaced_topics?.length && !t.topic_ids?.length) t.topic_ids = changes.replaced_topics;
        const { topic_ids: _, locators: __, ...identity } = t;
        const identityKey: ObjectValue = { register_id: t.register_id, ...(t.canonical_url ? { canonical_url: t.canonical_url.split('#')[0] } : Object.fromEntries(Object.entries(t).filter(([k]) => ['doi', 'pmid', 'pmcid', 'pinned_source_id'].includes(k)).slice(0, 1))), ...(t.pinned_source_id ? { pinned_source_id: t.pinned_source_id } : {}), ...(t.edition ? { edition: t.edition, original_sha256: t.original_sha256 } : {}) };
        const key = sha(identityKey), old = one(db, 'SELECT target_json,status_json FROM update_source_statuses WHERE target_key=?', key), previous = old ? parse(old.status_json) : {}, priorIdentity = old ? parse(old.target_json) : {};
        if (Object.entries(article(identity)).some(([k, v]) => priorIdentity[k] && priorIdentity[k] !== v)) reject('review_identity_conflict');
        const merged = { ...previous, ...changes }; if (merged.publication_status && merged.publication_status !== 'final' || ['retracted', 'superseded', 'repository_removed'].some(k => merged[k]) || merged.replaced_topics?.length || merged.excluded_pages?.length) { changes = { ...changes, latest_final_verified: false, content_reviewed: false }; Object.assign(merged, changes); }
        db.prepare('UPDATE update_reviews SET changes_json=? WHERE id=?').run(canonical(changes), reviewId);
        db.prepare('INSERT INTO update_source_statuses VALUES(?,?,?,?) ON CONFLICT(target_key) DO UPDATE SET target_json=excluded.target_json,status_json=excluded.status_json,review_id=excluded.review_id').run(key, canonical({ ...priorIdentity, ...identity }), canonical(merged), reviewId);
        if (t.topic_ids?.length || t.locators?.length) db.prepare("UPDATE update_affected_versions SET state='dismissed' WHERE entry_id=?").run(c.id);
        if (invalidates || e.kind === 'publication-change' || changes.latest_final_verified === false || changes.content_reviewed === false || 'access_changed' in changes) affected(db, c.id, t, 'reviewed source status changed');
        enqueue(db, reviewId, c.id, t, changes, r.evidence, r.summary.trim()); sync(db, c.id);
      }
      return entry(db, c.id);
    }); break;
    case 'updates.sync': entry(db, c.id); result = sync(db, c.id); break;
    case 'updates.publications': result = { publications: rows(db, 'SELECT * FROM update_publications ORDER BY tracked_at DESC,id') }; break;
    case 'updates.publications.track': result = receipt(db, c, () => { if (!one(db, 'SELECT 1 FROM update_source_checks WHERE source_id=?', c.sourceId)) reject('source_missing'); const id = 'publication_' + sha({ source: c.sourceId, url: c.url }).slice(0, 24); const old = one(db, 'SELECT * FROM update_publications WHERE source_id=? AND url=?', c.sourceId, c.url); if (old) return old; db.prepare('INSERT INTO update_publications(id,source_id,url,title,permission_reference,max_bytes,tracked_at) VALUES(?,?,?,?,?,?,?)').run(id, c.sourceId, c.url, c.url, c.permissionReference, c.maxBytes, utcNow()); return one(db, 'SELECT * FROM update_publications WHERE id=?', id)!; }); break;
    case 'updates.publications.stop': db.prepare('UPDATE update_publications SET enabled=0 WHERE id=?').run(c.id); cancelChecks(db); result = { stopped: true }; break;
    case 'updates.check.begin': {
      const t = target(db, c.route), now = utcNow();
      if (!c.force && t.last_checked_at && Date.now() - Date.parse(t.last_checked_at) < 6 * 3600_000) { result = { input: null, cached: true, state: t.state, error_code: t.error_code ?? null, last_success_at: t.last_success_at ?? null }; break; }
      const prior = studyPreference<any>(db, checkKey(c.route), null); if (prior?.state === 'running') reject('updates_check_busy');
      const input: CheckInput = { route: c.route, token: uid('check'), stamp: stamp(db), target: t, previous_digest: t.fingerprint ?? t.digest ?? null, checked_at: now };
      saveStudyPreference(db, checkKey(c.route), { token: input.token, state: 'running' }); result = { input, cached: false, state: 'running' }; break;
    }
    case 'updates.check.current': currentCheck(db, c.input); result = { current: true }; break;
    case 'updates.check.finish': {
      currentCheck(db, c.input); const { route: r, target: t, checked_at: now } = c.input, o = c.observation;
      const state = !o ? 'failed' : !c.input.previous_digest ? 'baseline' : c.input.previous_digest === o.digest ? 'unchanged' : 'changed';
      if (r.kind === 'source') { if (o) db.prepare('UPDATE update_source_checks SET fingerprint=?,links_json=?,last_checked_at=?,last_success_at=?,state=?,error_code=NULL WHERE source_id=?').run(o.digest, canonical(o.links), now, now, state, r.id); else db.prepare("UPDATE update_source_checks SET last_checked_at=?,state='failed',error_code=? WHERE source_id=?").run(now, c.errorCode, r.id); }
      if (r.kind === 'publication') { if (o) db.prepare('UPDATE update_publications SET digest=?,observation=observation+1,fetch_metadata_json=?,last_checked_at=?,last_success_at=?,state=?,error_code=NULL WHERE id=?').run(o.digest, canonical(o.metadata), now, now, state, r.id); else db.prepare("UPDATE update_publications SET last_checked_at=?,state='failed',error_code=? WHERE id=?").run(now, c.errorCode, r.id); }
      if (r.kind === 'literature') db.prepare('INSERT INTO update_literature_checks(topic_id,last_checked_at,last_success_at,state,error_code,result_count) VALUES(?,?,?,?,?,?) ON CONFLICT(topic_id) DO UPDATE SET last_checked_at=excluded.last_checked_at,last_success_at=COALESCE(excluded.last_success_at,update_literature_checks.last_success_at),state=excluded.state,error_code=excluded.error_code,result_count=excluded.result_count').run(r.id, now, o ? now : null, state, c.errorCode, o?.entries.length ?? null);
      const discovered: string[] = [];
      const candidates = o ? [...o.entries] : [];
      if (o && state === 'changed' && r.kind !== 'literature') candidates.push({ external_id: r.kind + ':' + r.id + ':' + o.digest, title: 'Publication ' + (r.kind === 'source' ? 'links' : 'bytes') + ' changed: ' + t.title, url: t.url, publication_date: null, metadata: { ...o.metadata, publication_id: r.kind === 'publication' ? r.id : null, canonical_url: t.url, previous_digest: c.input.previous_digest, observed_digest: o.digest, all_links: o.links } });
      for (const e of candidates) {
        const id = 'update_' + sha(e.external_id).slice(0, 24), source = t.source_id ?? 'literature';
        const inserted = db.prepare('INSERT OR IGNORE INTO update_entries VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)').run(id, source, e.external_id, e.title, e.url, r.kind === 'publication' ? 'publication-change' : r.kind === 'source' ? 'source-change' : 'literature', e.publication_date, now, null, null, 'pending', 'Inspect publication status, corrections and source evidence before review.', '[]', canonical(e.metadata), null);
        if (inserted.changes) discovered.push(id);
        if (r.kind === 'publication' && state === 'changed' && inserted.changes) { const identity: SourceTarget = { register_id: source, canonical_url: t.url }; invalidate(db, identity); affected(db, id, identity, 'publication bytes changed'); enqueue(db, 'observed:' + id, id, identity, { latest_final_verified: false, content_reviewed: false }, { previous_sha256: c.input.previous_digest, observed: o!.metadata, observed_at: now }, 'Published bytes changed; review required'); sync(db, id); }
      }
      saveStudyPreference(db, checkKey(r), { token: c.input.token, state });
      db.prepare('UPDATE update_schedule_jobs SET state=?,last_attempt_at=?,last_success_at=CASE WHEN ?=1 THEN ? ELSE last_success_at END,error_code=?,failure_count=failure_count+? WHERE kind=? AND target_id=?').run(state, now, o ? 1 : 0, now, c.errorCode, o ? 0 : 1, r.kind, r.id);
      result = { state, checked_at: now, error_code: c.errorCode, entries: discovered, last_success_at: o ? now : t.last_success_at ?? null }; break;
    }
    case 'updates.literature.checks': result = { checks: rows(db, 'SELECT * FROM update_literature_checks ORDER BY topic_id') }; break;
    case 'updates.schedule.read': result = schedule(db); break;
    case 'updates.schedule.write': result = receipt(db, c, () => { if (c.expectedRevision !== studyPreference(db, 'updates.schedule_revision', 1)) reject('revision_conflict'); c.selection.forEach(r => target(db, r)); db.prepare('UPDATE update_schedule SET enabled=?,cadence_hours=?,updated_at=? WHERE id=1').run(c.enabled ? 1 : 0, c.cadenceHours, utcNow()); db.prepare('DELETE FROM update_schedule_jobs').run(); for (const r of c.selection) db.prepare('INSERT INTO update_schedule_jobs(kind,target_id,next_due_at) VALUES(?,?,?)').run(r.kind, r.id, utcNow()); saveStudyPreference(db, 'updates.schedule_revision', c.expectedRevision + 1); cancelChecks(db); return schedule(db); }); break;
    case 'updates.schedule.claim': { requireAssistance(db); const s = schedule(db); if (s.running || !c.manual && !s.enabled) { result = { id: null, selection: [] }; break; } const due = rows(db, 'SELECT kind,target_id AS id FROM update_schedule_jobs ' + (c.manual ? '' : 'WHERE next_due_at<=? ') + 'ORDER BY next_due_at,kind,target_id LIMIT 20', ...(c.manual ? [] : [utcNow()])); if (!due.length) { result = { id: null, selection: [] }; break; } const id = uid('updates_run'), now = utcNow(), next = new Date(Date.now() + Number(s.cadence_hours) * 3600_000).toISOString(); db.prepare("INSERT INTO update_schedule_runs(id,trigger,started_at,state) VALUES(?,?,?,'running')").run(id, c.manual ? 'manual' : 'schedule', now); for (const r of due) db.prepare("UPDATE update_schedule_jobs SET next_due_at=?,last_attempt_at=?,state='running' WHERE kind=? AND target_id=?").run(next, now, r.kind, r.id); result = { id, selection: due }; break; }
    case 'updates.schedule.finish': db.prepare("UPDATE update_schedule_runs SET state=?,checked=?,failed=?,error_code=?,finished_at=? WHERE id=? AND state='running'").run(c.errorCode === 'cancelled' ? 'cancelled' : c.failed ? 'failed' : 'completed', c.checked, c.failed, c.errorCode, utcNow(), c.id); result = schedule(db); break;
    case 'updates.schedule.stop': cancelChecks(db); db.prepare("UPDATE update_schedule_runs SET state='cancelled',error_code='cancelled',finished_at=? WHERE state='running'").run(utcNow()); result = { cancelled: true }; break;
    case 'updates.recover': saveStudyPreference(db, 'updates.cancel_revision', studyPreference(db, 'updates.cancel_revision', 0) + 1); db.prepare("UPDATE update_schedule_runs SET state='failed',error_code='interrupted',finished_at=? WHERE state='running'").run(utcNow()); for (const r of rows(db, "SELECT key,value FROM preferences WHERE key LIKE 'updates.check.%'")) { const v = parse(r.value); if (v.state === 'running') saveStudyPreference(db, String(r.key), { ...v, state: 'interrupted' }); } for (const r of rows(db, "SELECT DISTINCT entry_id FROM update_library_changes WHERE state NOT IN ('applied','no-match')")) sync(db, String(r.entry_id)); result = { recovered: true }; break;
    case 'updates.digest.input': result = digestInput(db, c.limit); break;
    case 'updates.digest.current': if (digestInput(db, c.limit).stamp !== c.stamp) reject('updates_digest_invalidated'); result = { current: true }; break;
    default: reject('updates_invalid');
  }
  return result as UpdatesResults[C['type']];
}
