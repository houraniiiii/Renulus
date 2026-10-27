// SPDX-License-Identifier: MIT
/** Local functions for the ONE canonical writer. The caller owns the transaction.
 * Reuses memory-001/002, including support groups, suppression and capture jobs.
 * Engine cleanup intents contain IDs only and live in the existing preferences
 * ledger; no schema/writer/provider ownership is introduced here. */
import type { DatabaseSync } from 'node:sqlite';
import { randomUUID } from 'node:crypto';
import { exact, integer, reject, text } from './contracts.ts';
import { requireAssistance } from './conversation.ts';
import { canonical, digest, one, rows } from './schema.ts';
import type { CaptureTicket, FactKind, MemoryCommand, MemoryDependency, MemoryFact, MemoryManifest,
  MemoryMutation, MemoryPurge, MemoryResults, MemorySnapshot, MemoryVector } from '../domain/memory/contracts.ts';
import { memoryEngineId } from '../domain/memory/contracts.ts';
import { effectiveKnowledgeMetadata } from '../domain/knowledge/source-status.ts';
import type { Metadata } from '../domain/knowledge/contracts.ts';

const now = () => new Date().toISOString();
const sha = (v: unknown) => digest(canonical(v));
const parse = <T>(v: unknown): T => JSON.parse(String(v));
const kinds: FactKind[] = ['learning-point', 'preference', 'goal', 'study-interest', 'mistake'];
const PURGE = 'memory.cleanup.';
const RESTORE = 'memory.restore_barrier:';
const restoreBarrier = (db: DatabaseSync, evidenceId: string) => one(db, 'SELECT value FROM preferences WHERE key=?', RESTORE + evidenceId);
const id = (v: unknown) => text(v, 1, 256);
const deleted = (db: DatabaseSync, type: string, value: string) => !!one(db, 'SELECT 1 FROM deletion_ledger WHERE entity_type=? AND entity_id=?', type, value);
function clean(v: string) { text(v, 1, 2000); if (!v.trim()) reject('invalid_memory_text'); return v.trim(); }
function epoch(db: DatabaseSync) { return Number(one(db, 'SELECT epoch FROM memory_index_state WHERE singleton=1')!.epoch); }
function context(db: DatabaseSync) { return Number(one(db, "SELECT value FROM preferences WHERE key='design_c.context_epoch'")?.value ?? 0); }
function policy(db: DatabaseSync) { requireAssistance(db); return Number(one(db, "SELECT value FROM preferences WHERE key='design_c.assessment_policy_revision'")?.value ?? 1); }
function invalidate(db: DatabaseSync) {
  db.prepare("UPDATE memory_index_state SET epoch=epoch+1,state='dirty',error_code=NULL WHERE singleton=1").run();
  db.prepare("INSERT INTO preferences VALUES('design_c.context_epoch','1',?) ON CONFLICT(key) DO UPDATE SET value=CAST(CAST(preferences.value AS INTEGER)+1 AS TEXT),updated_at=excluded.updated_at").run(now());
}
function project(db: DatabaseSync, value: string | null) {
  if (value !== null && (deleted(db, 'project', value) || !one(db, "SELECT 1 FROM study_projects WHERE id=? AND lifecycle!='deleted'", value))) reject('memory_project_scope');
}
function owner(db: DatabaseSync, value: string) { return (one(db, 'SELECT project_id FROM memory_support_groups WHERE record_id=? LIMIT 1', value)?.project_id ?? null) as string | null; }
function fact(db: DatabaseSync, value: string) {
  const row = one(db, 'SELECT * FROM memory_facts WHERE id=?', value);
  if (!row || deleted(db, 'memory_fact', value)) reject('memory_missing'); return row;
}
function view(db: DatabaseSync, value: string): MemoryFact {
  const row = fact(db, value), { text_hash: _, ...record } = row, projectId = owner(db, value);
  const entry = one(db, 'SELECT revision FROM memory_index_entries WHERE record_id=?', value);
  return { ...record, project_id: projectId, visibility: projectId ? 'project' : 'profile-global',
    index_state: entry?.revision === row.revision ? 'ready' : 'pending',
    sources: rows(db, 'SELECT source_key FROM memory_sources WHERE record_id=? ORDER BY source_key', value) } as unknown as MemoryFact;
}
function manifestDependencies(manifest: MemoryManifest) {
  if (!manifest || manifest.version !== 1 || !Array.isArray(manifest.inputs) || !Array.isArray(manifest.dependencies) || manifest.inputs.length + manifest.dependencies.length > 100) reject('memory_lineage_unknown');
  return [...manifest.inputs.map(i => i.dependency), ...manifest.dependencies];
}
const stale = new Set(['memory_dependency_revoked', 'memory_lineage_unknown', 'memory_project_scope', 'memory_capture_suppressed', 'memory_evidence_missing', 'memory_evidence_invalid', 'memory_restore_explicit_capture']);
function eligible(action: () => void) { try { action(); return true; } catch (error) { if (error && typeof error === 'object' && 'code' in error && stale.has(String(error.code))) return false; throw error; } }

/** Exported for native context/publication: these are eligibility pins, never
 * model-write authority. Every dependency is checked inside the current writer. */
export function checkMemoryDependency(db: DatabaseSync, dependency: MemoryDependency, projectId: string | null, seen = new Set<string>()): void {
  const { target, expected_revision: revision } = dependency;
  if (!target || typeof revision !== 'string') reject('memory_lineage_unknown');
  const key = target.type + ':' + target.id;
  if (seen.has(key) || seen.size >= 100) reject('memory_dependency_revoked');
  const next = new Set(seen).add(key);
  if (target.type === 'memory_revision') {
    const split = target.id.lastIndexOf(':'), identifier = target.id.slice(0, split), version = target.id.slice(split + 1);
    const row = one(db, 'SELECT revision FROM memory_facts WHERE id=?', identifier);
    if (split < 1 || !row || String(row.revision) !== version || version !== revision || deleted(db, 'memory_fact', identifier)) reject('memory_dependency_revoked');
    const ownership = owner(db, identifier); if (ownership !== null && ownership !== projectId) reject('memory_project_scope'); project(db, ownership);
    const groups = rows(db, "SELECT * FROM memory_support_groups WHERE record_id=? AND state='active'", identifier);
    if (!groups.some(group => eligible(() => checkGroup(db, group, next)))) reject('memory_dependency_revoked');
  } else if (target.type === 'learning_evidence') {
    const lineage = lineageRow(db, target.id, projectId, false, next);
    if (lineage.publication_digest !== revision) reject('memory_dependency_revoked');
  } else if (target.type === 'library_revision') {
    // Same immutable canonical fingerprint as the saved-learning source seam.
    const row = one(db, "SELECT r.*,d.title,d.source_id,d.scope_entity FROM knowledge_revisions r JOIN knowledge_documents d ON d.active_revision=r.id WHERE r.id=? AND r.status='ready' AND d.deleted_at IS NULL AND d.reserved=0 AND d.scope_kind='personal-library'", target.id);
    if (!row || row.scope_entity !== null && row.scope_entity !== projectId || ['knowledge-revision', 'revision'].some(t => deleted(db, t, target.id)) || ['knowledge-document', 'document'].some(t => deleted(db, t, String(row.document_id)))) reject('memory_dependency_revoked');
    const rights = parse<Record<string, unknown>>(row.rights_json), metadata = effectiveKnowledgeMetadata(db, parse<Metadata>(row.metadata_json));
    if (!['display', 'cache', 'index', 'embedding', 'model_input', 'derivation'].every(k => rights[k] === true) ||
      ['retracted', 'superseded', 'access_changed', 'repository_removed'].some(k => metadata[k]) ||
      ['draft', 'preprint'].includes(String(metadata.publication_status)) || Array.isArray(metadata.replaced_topics) && metadata.replaced_topics.length || metadata.correction && !metadata.content_reviewed) reject('memory_dependency_revoked');
    const representative = rows(db, 'SELECT id,locators_json FROM knowledge_passages WHERE revision_id=? ORDER BY ordinal LIMIT 4096', target.id)
      .find(p => !parse<{ page?: number }[]>(p.locators_json).some(l => l.page !== undefined && Array.isArray(metadata.excluded_pages) && metadata.excluded_pages.includes(l.page)));
    if (!representative || sha({ identity: target, document_id: row.document_id, sha256: row.sha256, title: row.title, source_id: row.source_id,
      metadata, rights, passage_id: representative.id, locators: parse(representative.locators_json) }) !== revision) reject('memory_dependency_revoked');
  } else reject('memory_lineage_unknown');
}
function lineageRow(db: DatabaseSync, evidenceId: string, projectId: string | null, admission: boolean, seen = new Set<string>(), explicitRestore = false) {
  if (!explicitRestore && restoreBarrier(db, evidenceId)) reject('memory_restore_explicit_capture');
  if (one(db, 'SELECT 1 FROM memory_suppression WHERE source_key=?', 'evidence:' + evidenceId)) reject('memory_capture_suppressed');
  const lineage = one(db, 'SELECT * FROM memory_answer_lineage WHERE evidence_id=?', evidenceId);
  if (!lineage || lineage.state !== 'active') reject('memory_lineage_unknown');
  if (lineage.project_id !== null && lineage.project_id !== projectId) reject('memory_project_scope'); project(db, lineage.project_id as string | null);
  const manifest = parse<MemoryManifest>(lineage.manifest_json), evidence = one(db, 'SELECT * FROM learning_evidence WHERE id=?', evidenceId);
  if (evidence && sha({ evidence, manifest, project_id: lineage.project_id }) !== lineage.publication_digest) reject('memory_dependency_revoked');
  if (admission) {
    if (!evidence || evidence.kind !== 'study-answer' || deleted(db, 'learning_evidence', evidenceId)) reject('memory_evidence_missing');
    const payload = parse<{ scope: { kind: string; entity_id: string }; answer_reference: CaptureTicket['reference'] }>(evidence.payload_json);
    if (payload.scope?.kind !== 'study' || payload.scope.entity_id !== evidence.entity_id || Object.keys(payload).sort().join(',') !== 'answer_reference,scope') reject('memory_evidence_invalid');
    const ref = payload.answer_reference;
    if (!ref || ref.version !== 1 || evidenceId !== 'learn-answer:' + ref.run_id || deleted(db, 'learn_run', ref.run_id) || deleted(db, 'learn_thread', String(evidence.entity_id))) reject('memory_evidence_invalid');
    const run = one(db, 'SELECT * FROM learn_runs WHERE id=?', ref.run_id);
    if (!run || run.state !== 'completed' || run.thread_id !== evidence.entity_id) reject('memory_evidence_invalid');
    if ('runtime' in ref) {
      const answer = one(db, 'SELECT * FROM learn_harness_answers WHERE run_id=?', ref.run_id), mapping = one(db, 'SELECT * FROM learn_harness_mappings WHERE thread_id=?', ref.thread_id);
      if (!answer || answer.state !== 'completed' || answer.publication_digest !== lineage.publication_digest || canonical(parse(answer.reference_json)) !== canonical(ref) ||
        !mapping || mapping.session_id !== ref.runtime.session_id || mapping.profile_id !== ref.runtime.profile_id || mapping.store_id !== ref.runtime.store_id ||
        ref.message_ids.some(m => deleted(db, 'learn_message', m))) reject('memory_evidence_invalid');
    } else {
      const message = one(db, 'SELECT thread_id,run_id,role,content FROM learn_messages WHERE id=?', ref.message_id);
      if (!message || message.role !== 'assistant' || message.run_id !== ref.run_id || message.thread_id !== evidence.entity_id || deleted(db, 'learn_message', ref.message_id) || digest(String(message.content)) !== ref.sha256) reject('memory_evidence_invalid');
    }
  }
  for (const dependency of manifestDependencies(manifest)) checkMemoryDependency(db, dependency, lineage.project_id as string | null, seen);
  return lineage;
}
function groupInputs(db: DatabaseSync, groupId: string): MemoryDependency[] {
  return rows(db, 'SELECT * FROM memory_support_inputs WHERE group_id=? ORDER BY target_type,target_id,expected_revision', groupId)
    .map(r => ({ target: { type: r.target_type, id: r.target_id }, expected_revision: r.expected_revision })) as MemoryDependency[];
}
function checkGroup(db: DatabaseSync, group: ReturnType<typeof rows>[number], seen = new Set<string>()) {
  project(db, group.project_id as string | null);
  for (const dependency of groupInputs(db, String(group.group_id))) checkMemoryDependency(db, dependency, group.project_id as string | null, seen);
  if (group.support_kind === 'generated') lineageRow(db, String(group.source_key).slice(9), group.project_id as string | null, false, seen);
}
function support(db: DatabaseSync, recordId: string, sourceKey: string, projectId: string | null, dependencies: MemoryDependency[] = [], kind = 'manual') {
  if (dependencies.some(d => d.target.type === 'memory_revision' && d.target.id.slice(0, d.target.id.lastIndexOf(':')) === recordId)) return;
  const unique = [...new Map(dependencies.map(d => [canonical(d), d])).values()].sort((a, b) => canonical(a).localeCompare(canonical(b)));
  const groupId = 'support:' + sha({ record: recordId, revision: fact(db, recordId).revision, source: sourceKey, inputs: unique, project_id: projectId });
  db.prepare("INSERT OR IGNORE INTO memory_support_groups VALUES(?,?,?,?, 'active',?)").run(groupId, recordId, sourceKey, kind, projectId);
  for (const d of unique) db.prepare('INSERT OR IGNORE INTO memory_support_inputs VALUES(?,?,?,?)').run(groupId, d.target.type, d.target.id, d.expected_revision);
}
function roots(db: DatabaseSync, manifest: MemoryManifest, seen = new Set<string>()): MemoryDependency[][] {
  let groups: MemoryDependency[][] = [[]];
  for (const d of manifestDependencies(manifest)) {
    const key = d.target.type + ':' + d.target.id; if (seen.has(key) || seen.size >= 100) reject('memory_dependency_revoked');
    let alternatives: MemoryDependency[][] = [[]];
    if (d.target.type === 'memory_revision') {
      const recordId = d.target.id.slice(0, d.target.id.lastIndexOf(':'));
      alternatives = rows(db, "SELECT group_id FROM memory_support_groups WHERE record_id=? AND state='active'", recordId).map(g => groupInputs(db, String(g.group_id)));
    } else if (d.target.type === 'learning_evidence') {
      const l = one(db, "SELECT manifest_json FROM memory_answer_lineage WHERE evidence_id=? AND state='active'", d.target.id);
      if (!l) reject('memory_lineage_unknown'); alternatives = roots(db, parse(l.manifest_json), new Set(seen).add(key));
    }
    groups = groups.flatMap(g => alternatives.map(branch => [...g, d, ...branch]));
    if (groups.length > 100 || groups.some(g => g.length > 100)) reject('memory_support_budget');
  }
  return groups;
}
function suppress(db: DatabaseSync, recordId: string, restoring = false) {
  for (const r of rows(db, 'SELECT source_key FROM memory_sources WHERE record_id=?', recordId)) {
    // Restore quarantine is recoverable by an explicit Capture. User correction
    // and deletion still create terminal suppression even while quarantined.
    if (restoring && String(r.source_key).startsWith('evidence:') && restoreBarrier(db, String(r.source_key).slice(9))) continue;
    db.prepare('INSERT OR IGNORE INTO memory_suppression VALUES(?,?)').run(r.source_key, now());
    if (String(r.source_key).startsWith('evidence:')) db.prepare("UPDATE memory_jobs SET state='cancelled',error_code='memory_capture_suppressed',updated_at=? WHERE evidence_id=? AND state IN ('queued','running','failed')").run(now(), String(r.source_key).slice(9));
  }
}
function remove(db: DatabaseSync, recordId: string, restoring = false) {
  purgeIntent(db, physicalIds(db, recordId));
  suppress(db, recordId, restoring); db.prepare("INSERT OR IGNORE INTO deletion_ledger VALUES('memory_fact',?,?)").run(recordId, now());
  db.prepare('DELETE FROM memory_facts WHERE id=?').run(recordId);
}
function physicalIds(db: DatabaseSync, identifier: string): string[] {
  const revision = Number(one(db, 'SELECT revision FROM memory_facts WHERE id=?', identifier)?.revision ?? 0);
  if (revision > 10000) reject('memory_cleanup_budget');
  return [identifier, ...Array.from({ length: revision }, (_, i) => memoryEngineId(identifier, i + 1))];
}
function purgeIntent(db: DatabaseSync, identifiers: string[]): MemoryPurge | null {
  const ids = [...new Set(identifiers)]; if (!ids.length) return null;
  const intentId = 'cleanup_' + randomUUID().replaceAll('-', '');
  db.prepare('INSERT INTO preferences VALUES(?,?,?)').run(PURGE + intentId, canonical({ ids }), now());
  return { intentId, ids };
}
/** Fixed point revocation keeps independent support alternatives alive. */
export function reconcileMemorySupport(db: DatabaseSync): MemoryPurge | null {
  const removed: string[] = []; let changed = true;
  while (changed) {
    changed = false;
    for (const l of rows(db, "SELECT * FROM memory_answer_lineage WHERE state='active'")) {
      if (eligible(() => { lineageRow(db, String(l.evidence_id), l.project_id as string | null, false); })) continue;
      db.prepare("UPDATE memory_answer_lineage SET state='revoked' WHERE evidence_id=?").run(l.evidence_id);
      if (!restoreBarrier(db, String(l.evidence_id))) db.prepare('INSERT OR IGNORE INTO memory_suppression VALUES(?,?)').run('evidence:' + l.evidence_id, now());
      db.prepare("UPDATE memory_jobs SET state='cancelled',error_code='memory_dependency_revoked',updated_at=? WHERE evidence_id=? AND state IN ('queued','running','failed')").run(now(), l.evidence_id); changed = true;
    }
    for (const group of rows(db, "SELECT * FROM memory_support_groups WHERE state='active'")) {
      if (eligible(() => checkGroup(db, group))) continue;
      db.prepare("UPDATE memory_support_groups SET state='revoked' WHERE group_id=?").run(group.group_id); changed = true;
    }
    for (const f of rows(db, "SELECT id FROM memory_facts f WHERE EXISTS(SELECT 1 FROM memory_support_groups g WHERE g.record_id=f.id) AND NOT EXISTS(SELECT 1 FROM memory_support_groups g WHERE g.record_id=f.id AND g.state='active')")) {
      remove(db, String(f.id), true); removed.push(String(f.id)); changed = true;
    }
    // Restored facts may coexist with later deletion markers.
    for (const f of rows(db, "SELECT f.id FROM memory_facts f JOIN deletion_ledger d ON d.entity_id=f.id AND d.entity_type='memory_fact'")) {
      remove(db, String(f.id)); removed.push(String(f.id)); changed = true;
    }
  }
  if (removed.length) invalidate(db); return purgeIntent(db, removed);
}
function insert(db: DatabaseSync, body: string, kind: FactKind, topic: string | null, scope: string, sourceKind: string, sourceId: string | null, sourceKey: string, projectId: string | null) {
  const value = clean(body), hash = sha(value.toLocaleLowerCase('en').replace(/\s+/g, ' '));
  const existing = db.prepare('SELECT id FROM memory_facts WHERE text_hash=? AND kind=? AND topic_id IS ?').all(hash, kind, topic).find(f => owner(db, String(f.id)) === projectId && !deleted(db, 'memory_fact', String(f.id)));
  const identifier = existing ? String(existing.id) : 'memory_' + randomUUID().replaceAll('-', '');
  if (!existing) {
    db.prepare('INSERT INTO memory_facts VALUES(?,?,?,?,?,?,1,?,?,?,?)').run(identifier, value, hash, kind, topic, scope, sourceKind, sourceId, now(), now());
    db.prepare("INSERT INTO memory_history VALUES(?,1,?,'added',?)").run(identifier, value, now()); invalidate(db);
  }
  db.prepare('INSERT OR IGNORE INTO memory_sources VALUES(?,?)').run(sourceKey, identifier); return identifier;
}
function fingerprint(db: DatabaseSync, evidenceId: string, explicitRestore = false) {
  const l = one(db, 'SELECT project_id FROM memory_answer_lineage WHERE evidence_id=?', evidenceId);
  const lineage = lineageRow(db, evidenceId, (l?.project_id ?? null) as string | null, true, new Set(), explicitRestore);
  return { lineage, value: 'memory-ts/1:' + sha({ publication: lineage.publication_digest, support: parse(lineage.manifest_json), policy: policy(db), context: context(db) }) };
}
/** Call after committed evidence+lineage publication in the shared transaction.
 * Positive default capture is a durable job; failed jobs never spin on reopen. */
export function queueMemoryCapture(db: DatabaseSync, evidenceId: string): void {
  if (restoreBarrier(db, evidenceId)) return;
  if (one(db, 'SELECT 1 FROM memory_jobs WHERE evidence_id=?', evidenceId) || one(db, 'SELECT 1 FROM memory_sources WHERE source_key=?', 'evidence:' + evidenceId)) return;
  const current = fingerprint(db, evidenceId);
  const evidence = one(db, 'SELECT payload_json FROM learning_evidence WHERE id=?', evidenceId)!;
  const scope = parse<{ scope: CaptureTicket['scope'] }>(evidence.payload_json).scope;
  db.prepare("INSERT INTO memory_jobs VALUES(?,?,?,?,'queued',0,NULL,?,?)").run('capture_' + randomUUID().replaceAll('-', ''), evidenceId, current.value, canonical(scope), now(), now());
}
function checkTicket(db: DatabaseSync, ticket: CaptureTicket) {
  const job = one(db, 'SELECT * FROM memory_jobs WHERE id=?', ticket.jobId);
  if (!job || job.state !== 'running' || job.evidence_id !== ticket.evidenceId || job.attempts !== ticket.attempt || job.evidence_hash !== ticket.fingerprint) reject('memory_dependency_revoked');
  const current = fingerprint(db, ticket.evidenceId);
  if (current.value !== ticket.fingerprint || current.lineage.publication_digest !== ticket.publicationDigest || sha(parse(current.lineage.manifest_json)) !== ticket.supportSha256 || current.lineage.project_id !== ticket.projectId) reject('memory_dependency_revoked');
  const evidence = one(db, 'SELECT payload_json,topic_id FROM learning_evidence WHERE id=?', ticket.evidenceId)!;
  const payload = parse<{ scope: CaptureTicket['scope']; answer_reference: CaptureTicket['reference'] }>(evidence.payload_json);
  if (canonical(payload.scope) !== canonical(ticket.scope) || canonical(payload.answer_reference) !== canonical(ticket.reference) || evidence.topic_id !== ticket.topicId ||
    ('runtime' in payload.answer_reference ? ticket.sourceText !== null : ticket.sourceText === null || digest(ticket.sourceText) !== payload.answer_reference.sha256)) reject('memory_dependency_revoked');
  return current.lineage;
}
function snapshot(db: DatabaseSync, projectId: string | null): MemorySnapshot {
  policy(db); project(db, projectId); reconcileMemorySupport(db);
  const records = rows(db, 'SELECT id,revision,text,scope,topic_id,kind FROM memory_facts ORDER BY id').filter(r => owner(db, String(r.id)) === null || owner(db, String(r.id)) === projectId);
  const accepted = rows(db, 'SELECT record_id AS canonical_id,revision AS canonical_revision,engine_id FROM memory_index_entries ORDER BY record_id')
    .filter(e => records.some(r => r.id === e.canonical_id && r.revision === e.canonical_revision));
  return { epoch: epoch(db), records, accepted, projectId, stamp: sha({ records, accepted, projectId, policy: policy(db), context: context(db) }) } as unknown as MemorySnapshot;
}
function checkSnapshot(db: DatabaseSync, previous: MemorySnapshot) {
  const current = snapshot(db, previous.projectId);
  if (current.epoch !== previous.epoch || current.stamp !== previous.stamp) reject('memory_dependency_revoked'); return current;
}
export function isMemoryCommand(v: unknown): v is MemoryCommand { return !!v && typeof v === 'object' && 'type' in v && typeof v.type === 'string' && v.type.startsWith('memory.'); }
export function validateMemoryCommand(c: MemoryCommand): void {
  const v = c as unknown as Record<string, unknown>;
  switch (c.type) {
    case 'memory.status': case 'memory.export': case 'memory.purge.pending': exact(v, ['type']); break;
    case 'memory.list': exact(v, ['type', 'offset', 'limit']); integer(c.offset); integer(c.limit, 1, 100); break;
    case 'memory.inspect': case 'memory.history.purge': exact(v, ['type', 'id']); id(c.id); break;
    case 'memory.add': exact(v, ['type', 'text', 'kind', 'topicId', 'projectId', 'idempotencyKey']); clean(c.text); if (!kinds.includes(c.kind)) reject('storage_invalid_command'); if (c.topicId !== null) id(c.topicId); if (c.projectId !== null) id(c.projectId); text(c.idempotencyKey, 1, 128); break;
    case 'memory.correct': exact(v, ['type', 'id', 'expectedRevision', 'text']); clean(c.text); id(c.id); integer(c.expectedRevision, 1); break;
    case 'memory.delete': exact(v, ['type', 'id', 'expectedRevision']); id(c.id); integer(c.expectedRevision, 1); break;
    case 'memory.capture.claim': exact(v, ['type', 'evidenceId', 'retry']); id(c.evidenceId); if (typeof c.retry !== 'boolean') reject('storage_invalid_command'); break;
    case 'memory.capture.explicit': exact(v, ['type', 'evidenceId']); id(c.evidenceId); break;
    case 'memory.capture.check': case 'memory.capture.complete': case 'memory.capture.fail': {
      exact(v, ['type', 'ticket', ...(c.type === 'memory.capture.complete' ? ['facts'] : c.type === 'memory.capture.fail' ? ['cancelled', 'code'] : [])]);
      exact(c.ticket, ['jobId', 'evidenceId', 'attempt', 'fingerprint', 'publicationDigest', 'supportSha256', 'projectId', 'scope', 'topicId', 'reference', 'sourceText']);
      id(c.ticket.jobId); id(c.ticket.evidenceId); integer(c.ticket.attempt, 1); text(c.ticket.fingerprint, 1, 256);
      if (c.type === 'memory.capture.complete') { if (!Array.isArray(c.facts) || c.facts.length > 12) reject('storage_invalid_command'); c.facts.forEach(clean); }
      if (c.type === 'memory.capture.fail') { if (typeof c.cancelled !== 'boolean' || !/^[a-z0-9_]{1,100}$/.test(c.code)) reject('storage_invalid_command'); } break;
    }
    case 'memory.jobs': exact(v, ['type', 'recover']); if (typeof c.recover !== 'boolean') reject('storage_invalid_command'); break;
    case 'memory.job.cancel': exact(v, ['type', 'jobId']); id(c.jobId); break;
    case 'memory.purge.ack': exact(v, ['type', 'intentId']); id(c.intentId); break;
    case 'memory.snapshot': exact(v, ['type', 'projectId']); if (c.projectId !== null) id(c.projectId); break;
    case 'memory.index.accept': case 'memory.recall.resolve':
      exact(v, ['type', 'snapshot', ...(c.type === 'memory.index.accept' ? ['references', 'generation'] : ['candidates', 'budgetChars'])]);
      exact(c.snapshot, ['epoch', 'records', 'accepted', 'stamp', 'projectId']); integer(c.snapshot.epoch); text(c.snapshot.stamp, 64, 64);
      if (c.snapshot.projectId !== null) id(c.snapshot.projectId);
      { const refs = c.type === 'memory.index.accept' ? c.references : c.candidates; if (!Array.isArray(refs) || refs.length > 10000) reject('storage_invalid_command');
        refs.forEach(r => { exact(r, ['canonical_id', 'canonical_revision', 'engine_id']); id(r.canonical_id); integer(r.canonical_revision, 1); id(r.engine_id); }); }
      if (c.type === 'memory.index.accept') id(c.generation); else integer(c.budgetChars, 0, 12000); break;
    default: reject('storage_invalid_command');
  }
}
export function executeMemoryCommand<C extends MemoryCommand>(db: DatabaseSync, command: C): MemoryResults[C['type']] {
  validateMemoryCommand(command); return execute(db, command) as MemoryResults[C['type']];
}
function execute(db: DatabaseSync, c: MemoryCommand): unknown {
  switch (c.type) {
    case 'memory.status': return { ...one(db, 'SELECT state,epoch,generation,error_code FROM memory_index_state WHERE singleton=1'), pending: Number(one(db, "SELECT count(*) AS n FROM memory_jobs WHERE state IN ('queued','running','failed')")!.n) };
    case 'memory.list': { policy(db); reconcileMemorySupport(db); const records = rows(db, 'SELECT id FROM memory_facts ORDER BY updated_at DESC,id LIMIT ? OFFSET ?', c.limit + 1, c.offset); return { records: records.slice(0, c.limit).map(r => view(db, String(r.id))), nextOffset: records.length > c.limit ? c.offset + c.limit : null }; }
    case 'memory.inspect': policy(db); reconcileMemorySupport(db); return { ...view(db, c.id), history: rows(db, 'SELECT revision,text,event,created_at FROM memory_history WHERE record_id=? ORDER BY revision', c.id) };
    case 'memory.export': { policy(db); reconcileMemorySupport(db); return { format: 'renulus-memory', version: 1, records: rows(db, 'SELECT id FROM memory_facts ORDER BY id').map(r => view(db, String(r.id))) }; }
    case 'memory.add': {
      policy(db); project(db, c.projectId); const requestHash = sha({ text: clean(c.text), kind: c.kind, topicId: c.topicId, projectId: c.projectId });
      const previous = one(db, 'SELECT * FROM memory_requests WHERE idempotency_key=?', c.idempotencyKey);
      if (previous) { if (previous.request_hash !== requestHash) reject('idempotency_conflict'); return view(db, String(previous.record_id)); }
      const identifier = insert(db, c.text, c.kind, c.topicId, 'study', 'manual', null, 'manual:' + c.idempotencyKey, c.projectId);
      support(db, identifier, 'manual:' + c.idempotencyKey, c.projectId); db.prepare('INSERT INTO memory_requests VALUES(?,?,?)').run(c.idempotencyKey, requestHash, identifier); return view(db, identifier);
    }
    case 'memory.correct': case 'memory.delete': case 'memory.history.purge': {
      if (c.type === 'memory.delete' && deleted(db, 'memory_fact', c.id)) return { record: null, deleted: true, purge: null };
      const old = fact(db, c.id), projectId = owner(db, c.id);
      if (c.type !== 'memory.history.purge' && old.revision !== c.expectedRevision) reject('memory_revision_conflict');
      const ids = physicalIds(db, c.id);
      if (c.type === 'memory.correct') {
        if (old.text === clean(c.text)) return { record: view(db, c.id), deleted: false, purge: null };
        suppress(db, c.id); db.prepare("UPDATE memory_support_groups SET state='revoked' WHERE record_id=?").run(c.id);
        db.prepare('UPDATE memory_facts SET text=?,text_hash=?,revision=revision+1,updated_at=? WHERE id=?').run(clean(c.text), sha(clean(c.text).toLocaleLowerCase('en').replace(/\s+/g, ' ')), now(), c.id);
        // Correction removes superseded canonical text as well as all derived history.
        db.prepare('DELETE FROM memory_history WHERE record_id=?').run(c.id);
        db.prepare("INSERT INTO memory_history VALUES(?,?,?,'edited',?)").run(c.id, Number(old.revision) + 1, clean(c.text), now());
        support(db, c.id, `edited:${c.id}:${Number(old.revision) + 1}`, projectId);
      } else if (c.type === 'memory.delete') remove(db, c.id);
      else {
        db.prepare('DELETE FROM memory_history WHERE record_id=?').run(c.id);
        // The purge worker tombstones immutable vector revisions. Keep the same
        // fact body under a fresh revision so history cleanup cannot revive one.
        db.prepare('UPDATE memory_facts SET revision=revision+1,updated_at=? WHERE id=?').run(now(), c.id);
      }
      db.prepare('DELETE FROM memory_index_entries WHERE record_id=?').run(c.id); invalidate(db);
      reconcileMemorySupport(db); const purge = purgeIntent(db, ids);
      return { record: c.type === 'memory.delete' ? null : view(db, c.id), deleted: c.type === 'memory.delete', purge } satisfies MemoryMutation;
    }
    case 'memory.purge.pending': reconcileMemorySupport(db); return rows(db, 'SELECT key,value FROM preferences WHERE key LIKE ? ORDER BY key', PURGE + '%').map(r => ({ intentId: String(r.key).slice(PURGE.length), ...parse<{ ids: string[] }>(r.value) }));
    case 'memory.purge.ack': db.prepare('DELETE FROM preferences WHERE key=?').run(PURGE + c.intentId); return { purged: true };
    case 'memory.jobs': if (c.recover) db.prepare("UPDATE memory_jobs SET state='queued',updated_at=? WHERE state='running'").run(now()); return rows(db, 'SELECT id,evidence_id,scope,state,error_code FROM memory_jobs ORDER BY created_at,id');
    case 'memory.job.cancel': db.prepare("UPDATE memory_jobs SET state='cancelled',error_code='memory_cancelled',updated_at=? WHERE id=? AND state IN ('queued','running','failed')").run(now(), c.jobId); return { cancelled: true };
    case 'memory.capture.claim': case 'memory.capture.explicit': {
      const explicit = c.type === 'memory.capture.explicit', retry = explicit || c.retry;
      const barrier = restoreBarrier(db, c.evidenceId);
      if (barrier && !explicit) return null;
      if (barrier) {
        if (barrier.value !== 'explicit-capture-required') reject('memory_restore_explicit_capture');
        // The shared writer rolls back reactivation if any evidence, receipt,
        // native mapping, digest, project, policy or support check below fails.
        db.prepare("UPDATE memory_answer_lineage SET state='active' WHERE evidence_id=? AND state='revoked'").run(c.evidenceId);
      }
      const current = fingerprint(db, c.evidenceId, !!barrier && explicit), previous = one(db, 'SELECT * FROM memory_jobs WHERE evidence_id=? AND evidence_hash=?', c.evidenceId, current.value) ??
        one(db, "SELECT * FROM memory_jobs WHERE evidence_id=? AND (state='queued' OR ?=1 AND (state='failed' OR ?=1 AND state='cancelled' AND error_code IN ('restore_interrupted','restore_explicit_capture'))) ORDER BY created_at LIMIT 1", c.evidenceId, retry ? 1 : 0, explicit ? 1 : 0);
      const restored = explicit && previous?.state === 'cancelled' && ['restore_interrupted', 'restore_explicit_capture'].includes(String(previous.error_code));
      if (previous && (['running', 'completed', 'cancelled'].includes(String(previous.state)) && !restored || previous.state === 'failed' && !retry)) return null;
      // A changed boundary cannot silently revive a previously completed/suppressed source.
      if (!retry && one(db, "SELECT 1 FROM memory_jobs WHERE evidence_id=? AND state IN ('completed','cancelled','failed','running')", c.evidenceId)) return null;
      const jobId = previous ? String(previous.id) : 'capture_' + randomUUID().replaceAll('-', ''), attempt = Number(previous?.attempts ?? 0) + 1;
      const evidence = one(db, 'SELECT * FROM learning_evidence WHERE id=?', c.evidenceId)!, payload = parse<{ scope: CaptureTicket['scope']; answer_reference: CaptureTicket['reference'] }>(evidence.payload_json);
      if (previous) db.prepare("UPDATE memory_jobs SET state='running',evidence_hash=?,attempts=?,error_code=NULL,updated_at=? WHERE id=?").run(current.value, attempt, now(), jobId);
      else db.prepare("INSERT INTO memory_jobs VALUES(?,?,?,?,'running',?,NULL,?,?)").run(jobId, c.evidenceId, current.value, canonical(payload.scope), attempt, now(), now());
      if (barrier) db.prepare('DELETE FROM preferences WHERE key=?').run(RESTORE + c.evidenceId);
      const sourceText = 'message_id' in payload.answer_reference ? String(one(db, 'SELECT content FROM learn_messages WHERE id=?', payload.answer_reference.message_id)!.content) : null;
      return { jobId, evidenceId: c.evidenceId, attempt, fingerprint: current.value, publicationDigest: String(current.lineage.publication_digest), supportSha256: sha(parse(current.lineage.manifest_json)),
        scope: payload.scope, topicId: evidence.topic_id === null ? null : String(evidence.topic_id), reference: payload.answer_reference, sourceText, projectId: current.lineage.project_id === null ? null : String(current.lineage.project_id) };
    }
    case 'memory.capture.check': checkTicket(db, c.ticket); return { current: true };
    case 'memory.capture.complete': {
      const lineage = checkTicket(db, c.ticket), manifest = parse<MemoryManifest>(lineage.manifest_json), groups = roots(db, manifest);
      const identifiers = new Set<string>(), sourceKey = 'evidence:' + c.ticket.evidenceId;
      for (const value of c.facts) {
        const identifier = insert(db, value, 'learning-point', c.ticket.topicId, c.ticket.scope.kind, 'evidence', c.ticket.evidenceId, sourceKey, c.ticket.projectId);
        for (const inputs of groups) support(db, identifier, sourceKey, c.ticket.projectId, inputs, 'generated'); identifiers.add(identifier);
      }
      db.prepare("UPDATE memory_jobs SET state='completed',error_code=NULL,updated_at=? WHERE id=?").run(now(), c.ticket.jobId);
      return { records: [...identifiers].map(value => view(db, value)) };
    }
    case 'memory.capture.fail': db.prepare("UPDATE memory_jobs SET state=?,error_code=?,updated_at=? WHERE id=? AND attempts=? AND state='running'").run(c.cancelled ? 'cancelled' : 'failed', c.code, now(), c.ticket.jobId, c.ticket.attempt); return { settled: true };
    case 'memory.snapshot': return snapshot(db, c.projectId);
    case 'memory.index.accept': {
      const current = checkSnapshot(db, c.snapshot);
      if (c.references.length !== current.records.length || new Set(c.references.map(r => r.canonical_id)).size !== c.references.length || c.references.some(r => !current.records.some(f => f.id === r.canonical_id && f.revision === r.canonical_revision))) reject('memory_index_result_invalid');
      for (const ref of c.references) db.prepare('INSERT INTO memory_index_entries VALUES(?,?,?,?) ON CONFLICT(record_id) DO UPDATE SET revision=excluded.revision,engine_id=excluded.engine_id,generation=excluded.generation').run(ref.canonical_id, ref.canonical_revision, ref.engine_id, c.generation);
      db.prepare("UPDATE memory_index_state SET state='ready',generation=?,fingerprint=?,error_code=NULL WHERE singleton=1").run(c.generation, current.stamp); return { ready: true };
    }
    case 'memory.recall.resolve': {
      const current = checkSnapshot(db, c.snapshot), records: MemoryFact[] = []; let length = 0;
      for (const candidate of c.candidates) {
        if (!current.accepted.some(r => canonical(r) === canonical(candidate))) reject('memory_index_result_stale');
        const record = view(db, candidate.canonical_id); if (records.some(r => r.id === record.id)) continue;
        if (length + record.text.length + 3 > c.budgetChars) continue; length += record.text.length + 3; records.push(record);
      }
      return { records, dependencies: records.map(r => ({ target: { type: 'memory_revision', id: `${r.id}:${r.revision}` }, expected_revision: String(r.revision) })), context: records.map(r => '- ' + r.text).join('\n') };
    }
  }
}
