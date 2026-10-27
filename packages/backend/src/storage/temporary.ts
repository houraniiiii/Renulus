// SPDX-License-Identifier: MIT
/** Sync canonical publication only; invoked by the one existing storage worker. */
import type { DatabaseSync } from 'node:sqlite';
import type { PromotionPlan, PromotionReceipt, TemporaryCommand, TemporaryResults } from '../domain/temporary/contracts.ts';
import { exact, integer, reject, text } from './contracts.ts';
import { canonical, digest, one, rows } from './schema.ts';
import { requireAssistance } from './conversation.ts';

export const TEMPORARY_SCHEMA = `CREATE TABLE temporary_save_intents(
 id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE, request_hash TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('staged','copied','active','cancelled','retired')),
 cancellation_epoch INTEGER NOT NULL, plan_json TEXT NOT NULL CHECK(json_valid(plan_json)), graph_digest TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL);`;
const commands = new Set(['temporary.save.begin', 'temporary.save.copied', 'temporary.save.activate', 'temporary.save.cancel', 'temporary.save.retire', 'temporary.save.pending']);
export function isTemporaryCommand(value: unknown): value is TemporaryCommand {
  return !!value && typeof value === 'object' && 'type' in value && commands.has(String(value.type));
}
const identifier = (value: unknown) => { text(value, 1, 256); if (!/^[A-Za-z0-9][A-Za-z0-9._:-]*$/.test(value)) reject('temporary_invalid_id'); };
export function validateTemporaryCommand(c: TemporaryCommand) {
  if (c.type === 'temporary.save.pending') { exact(c, ['type']); return; }
  if (c.type === 'temporary.save.begin') {
    exact(c, ['type', 'plan']); const p = c.plan;
    exact(p, ['id', 'threadId', 'title', 'profileId', 'storeId', 'rootSessionId', 'sessionIds', 'cancellationEpoch', 'contextEpoch', 'policyRevision', 'idempotencyKey']);
    for (const v of [p.id, p.threadId, p.profileId, p.storeId, p.rootSessionId, p.idempotencyKey]) identifier(v);
    text(p.title, 1, 200); integer(p.cancellationEpoch); integer(p.contextEpoch); integer(p.policyRevision);
    if (!Array.isArray(p.sessionIds) || !p.sessionIds.length || p.sessionIds.length > 64 || new Set(p.sessionIds).size !== p.sessionIds.length || p.sessionIds[0] !== p.rootSessionId) reject('temporary_invalid_family');
    for (const id of p.sessionIds) identifier(id); return;
  }
  exact(c, c.type === 'temporary.save.copied' ? ['type', 'id', 'expectedEpoch', 'graphDigest'] : ['type', 'id', 'expectedEpoch']);
  identifier(c.id); integer(c.expectedEpoch);
  if (c.type === 'temporary.save.copied' && !/^[a-f0-9]{64}$/.test(c.graphDigest)) reject('temporary_invalid_digest');
}
function receipt(db: DatabaseSync, id: string): PromotionReceipt {
  const row = one(db, 'SELECT * FROM temporary_save_intents WHERE id=?', id); if (!row) reject('temporary_save_missing');
  const plan = JSON.parse(String(row.plan_json)) as PromotionPlan;
  return { id, state: row.state as PromotionReceipt['state'], cancellationEpoch: Number(row.cancellation_epoch),
    threadId: plan.threadId, rootSessionId: plan.rootSessionId, sessionIds: plan.sessionIds };
}
function current(db: DatabaseSync, p: PromotionPlan) {
  requireAssistance(db);
  if (Number(one(db, "SELECT value FROM preferences WHERE key='design_c.context_epoch'")?.value ?? 0) !== p.contextEpoch ||
      Number(one(db, "SELECT value FROM preferences WHERE key='design_c.assessment_policy_revision'")?.value ?? 1) !== p.policyRevision) reject('temporary_context_changed');
  if (one(db, "SELECT 1 FROM deletion_ledger WHERE entity_type='learn_thread' AND entity_id=?", p.threadId)) reject('conversation_missing');
}
export function executeTemporary<C extends TemporaryCommand>(db: DatabaseSync, c: C): TemporaryResults[C['type']] {
  if (!db.isTransaction) reject('temporary_transaction_required'); validateTemporaryCommand(c);
  const now = new Date().toISOString(); let result: PromotionReceipt | PromotionReceipt[];
  if (c.type === 'temporary.save.pending') {
    result = rows(db, "SELECT id FROM temporary_save_intents WHERE state IN ('staged','copied','cancelled') ORDER BY created_at").map(r => receipt(db, String(r.id)));
  } else if (c.type === 'temporary.save.begin') {
    current(db, c.plan); const hash = digest(canonical(c.plan));
    const prior = one(db, 'SELECT id,request_hash FROM temporary_save_intents WHERE idempotency_key=? OR id=?', c.plan.idempotencyKey, c.plan.id);
    if (prior) { if (prior.request_hash !== hash || prior.id !== c.plan.id) reject('idempotency_conflict'); }
    else db.prepare("INSERT INTO temporary_save_intents VALUES(?,?,?,'staged',?,?,NULL,?,?)").run(c.plan.id, c.plan.idempotencyKey, hash, c.plan.cancellationEpoch, canonical(c.plan), now, now);
    result = receipt(db, c.plan.id);
  } else {
    const before = receipt(db, c.id);
    const row = one(db, 'SELECT * FROM temporary_save_intents WHERE id=?', c.id)!;
    const plan = JSON.parse(String(row.plan_json)) as PromotionPlan;
    if (before.state === 'active') result = before;
    else {
      if (before.cancellationEpoch !== c.expectedEpoch) reject('temporary_cancelled');
      if (c.type === 'temporary.save.cancel') {
        if (before.state !== 'retired' && before.state !== 'cancelled') db.prepare("UPDATE temporary_save_intents SET state='cancelled',cancellation_epoch=cancellation_epoch+1,updated_at=? WHERE id=?").run(now, c.id);
      } else if (c.type === 'temporary.save.retire') {
        db.prepare("UPDATE temporary_save_intents SET state='retired',graph_digest=NULL,updated_at=? WHERE id=?").run(now, c.id);
      } else {
        current(db, plan);
        if (!['staged', 'copied'].includes(before.state)) reject('temporary_cancelled');
        if (c.type === 'temporary.save.copied') {
          if (row.graph_digest !== null && row.graph_digest !== c.graphDigest) reject('temporary_graph_conflict');
          db.prepare("UPDATE temporary_save_intents SET state='copied',graph_digest=?,updated_at=? WHERE id=?").run(c.graphDigest, now, c.id);
        } else {
          if (before.state !== 'copied' || !row.graph_digest) reject('temporary_graph_not_verified');
          const mapping = { contract_version: 'harness/1', conversation: { type: 'learn_thread', id: plan.threadId }, retention: 'saved',
            runtime: { contract_version: 'harness/1', profile_id: plan.profileId, store_id: plan.storeId,
              engine: { name: 'opencode', version: '2.0.26', source_commit: '4b6fea2875e4f2e3e8a8fee181803e54f7056845' }, session_id: plan.rootSessionId } };
          db.prepare("INSERT INTO learn_threads VALUES(?,?,NULL,'direct',?,?)").run(plan.threadId, plan.title, now, now);
          db.prepare('INSERT INTO learn_conversations(thread_id,updated_at) VALUES(?,?)').run(plan.threadId, now);
          db.prepare('INSERT INTO learn_harness_mappings(thread_id,profile_id,store_id,session_id,mapping_json) VALUES(?,?,?,?,?)').run(plan.threadId, plan.profileId, plan.storeId, plan.rootSessionId, canonical(mapping));
          db.prepare("UPDATE temporary_save_intents SET state='active',updated_at=? WHERE id=?").run(now, c.id);
        }
      }
      result = receipt(db, c.id);
    }
  }
  return result as TemporaryResults[C['type']];
}
