// SPDX-License-Identifier: MIT
/** Sync canonical publication only; invoked by the one existing storage worker. */
import type { DatabaseSync } from 'node:sqlite';
import type { PromotionPlan, PromotionReceipt, TemporaryCommand, TemporaryResults } from '../domain/temporary/contracts.ts';
import { exact, integer, reject, text } from './contracts.ts';
import { canonical, digest, one, rows } from './schema.ts';
import { requireAssistance } from './conversation.ts';

/** Table: runtime/migrations/009-temporary-save-intents.sql. No payload, hash of content or export prefix. */
const commands = new Set(['temporary.save.begin', 'temporary.save.copied', 'temporary.save.activate', 'temporary.save.cancel', 'temporary.save.retire', 'temporary.save.pending', 'temporary.save.committed']);
export function isTemporaryCommand(value: unknown): value is TemporaryCommand {
  return !!value && typeof value === 'object' && 'type' in value && commands.has(String(value.type));
}
const identifier = (value: unknown) => { text(value, 1, 256); if (!/^[A-Za-z0-9][A-Za-z0-9._:-]*$/.test(value)) reject('temporary_invalid_id'); };
export function validateTemporaryCommand(c: TemporaryCommand) {
  if (c.type === 'temporary.save.pending') { exact(c, ['type']); return; }
  if (c.type === 'temporary.save.committed') { exact(c, ['type', 'idempotencyKey']); identifier(c.idempotencyKey); return; }
  if (c.type === 'temporary.save.begin') {
    exact(c, ['type', 'plan']); const p = c.plan;
    exact(p, ['id', 'threadId', 'title', 'profileId', 'storeId', 'exchanges', 'rootSessionId', 'sessionIds', 'cancellationEpoch', 'contextEpoch', 'policyRevision', 'idempotencyKey']);
    if (!Array.isArray(p.exchanges) || p.exchanges.length > 100) reject('temporary_invalid_family');
    for (const e of p.exchanges) {
      exact(e, ['runId', 'inputId', 'messageIds', 'sha256']); identifier(e.runId); identifier(e.inputId);
      if (!Array.isArray(e.messageIds) || !e.messageIds.length || e.messageIds.length > 100) reject('temporary_invalid_family');
      e.messageIds.forEach(identifier); if (!/^[a-f0-9]{64}$/.test(e.sha256)) reject('temporary_invalid_digest');
    }
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
  const now = new Date().toISOString(); let result: PromotionReceipt | PromotionReceipt[] | null;
  if (c.type === 'temporary.save.pending') {
    result = rows(db, "SELECT id FROM temporary_save_intents WHERE state IN ('staged','copied','cancelled') ORDER BY created_at").map(r => receipt(db, String(r.id)));
  } else if (c.type === 'temporary.save.committed') {
    const row = one(db, "SELECT id FROM temporary_save_intents WHERE idempotency_key=? AND state='active'", c.idempotencyKey);
    result = row ? receipt(db, String(row.id)) : null;
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
        // A retired attempt keeps identities only: no title, message identities or content hashes remain.
        const identities = canonical({ id: plan.id, threadId: plan.threadId, rootSessionId: plan.rootSessionId, sessionIds: plan.sessionIds });
        db.prepare("UPDATE temporary_save_intents SET state='retired',graph_digest=NULL,plan_json=?,updated_at=? WHERE id=?").run(identities, now, c.id);
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
          // Exact visible history. Promoted exchanges carry no lineage/evidence rows, so they are readable
          // and findable but neither inference context nor memory capture until the learner asks again.
          for (const e of plan.exchanges) {
            const reference = { version: 1, run_id: e.runId, thread_id: plan.threadId, runtime: mapping.runtime, input_id: e.inputId,
              message_ids: e.messageIds, sha256: e.sha256, citations: [], inputs: [], dependencies: [] };
            db.prepare("INSERT INTO learn_runs VALUES(?,?,?,'completed',NULL,?,?)").run(e.runId, plan.threadId, 'temporary-save:' + plan.id + ':' + e.runId, now, now);
            db.prepare("INSERT INTO learn_harness_answers(run_id,thread_id,request_digest,state,input_id,reference_json,publication_digest,command_request_id,process_generation) VALUES(?,?,?,'completed',?,?,?,?,NULL)")
              .run(e.runId, plan.threadId, digest(canonical(reference)), e.inputId, canonical(reference), digest(canonical(reference)), plan.idempotencyKey);
          }
          db.prepare("UPDATE temporary_save_intents SET state='active',updated_at=? WHERE id=?").run(now, c.id);
        }
      }
      result = receipt(db, c.id);
    }
  }
  return result as TemporaryResults[C['type']];
}
