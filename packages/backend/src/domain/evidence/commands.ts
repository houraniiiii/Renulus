// SPDX-License-Identifier: MIT
import type { DatabaseSync } from 'node:sqlite';
import type { EvidenceCommand, EvidenceReservation, EvidenceResults } from './contracts.ts';
import { exact, integer, reject, text } from '../../storage/contracts.ts';
import { one } from '../../storage/schema.ts';
export function isEvidenceCommand(v: unknown): v is EvidenceCommand {
  return !!v && typeof v === 'object' && 'type' in v && ['evidence.reserve', 'evidence.settle'].includes(String(v.type));
}
export function validateEvidenceCommand(c: EvidenceCommand): void {
  if (c.type === 'evidence.reserve') {
    exact(c, ['type','id','operation_id','provider','day','requests','credits','request_limit','credit_limit']);
    text(c.operation_id, 1, 256); text(c.day, 10, 10);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(c.day) || !['europe-pmc','pubmed','brave','tavily','exa'].includes(c.provider)) reject('evidence_invalid_reservation');
    integer(c.requests, 1, 4); integer(c.credits, 0, 1); integer(c.request_limit, 0, 10000); integer(c.credit_limit, 0, 10000);
  } else {
    exact(c, ['type','id','requests_started','effect']); integer(c.requests_started, 0, 4);
    if (!['not_sent','response_received','uncertain'].includes(c.effect)) reject('evidence_invalid_settlement');
    if (c.effect === 'not_sent' && c.requests_started !== 0) reject('evidence_invalid_settlement');
  }
  text(c.id, 1, 256);
}
export function executeEvidenceCommand<C extends EvidenceCommand>(db: DatabaseSync, c: C): EvidenceResults[C['type']] {
  validateEvidenceCommand(c); if (!db.isTransaction) reject('evidence_transaction_required');
  const old = one(db, 'SELECT * FROM evidence_reservations WHERE id=?', c.id) as EvidenceReservation | undefined;
  if (c.type === 'evidence.reserve') {
    if (old) {
      if (old.operation_id !== c.operation_id || old.provider !== c.provider || old.day !== c.day || old.requests !== c.requests || old.credits !== c.credits) reject('idempotency_conflict');
      return old;
    }
    const usage = one(db, 'SELECT requests,credits FROM retrieval_usage WHERE provider=? AND day=?', c.provider, c.day);
    if (Number(usage?.requests ?? 0) + c.requests > c.request_limit || Number(usage?.credits ?? 0) + c.credits > c.credit_limit) reject('retrieval_daily_limit');
    db.prepare('INSERT INTO retrieval_usage VALUES(?,?,?,?) ON CONFLICT(provider,day) DO UPDATE SET requests=requests+excluded.requests,credits=credits+excluded.credits').run(c.provider,c.day,c.requests,c.credits);
    db.prepare("INSERT INTO evidence_reservations VALUES(?,?,?,?,?,?,0,'reserved')").run(c.id,c.operation_id,c.provider,c.day,c.requests,c.credits);
  } else {
    if (!old) reject('evidence_reservation_missing');
    const state = c.effect === 'uncertain' ? 'uncertain' : 'settled';
    if (c.requests_started > old.requests) reject('evidence_invalid_settlement');
    if (old.state !== 'reserved') {
      if (old.state !== state || old.started !== c.requests_started) reject('evidence_settlement_conflict');
      return old;
    }
    if (state !== 'uncertain') db.prepare('UPDATE retrieval_usage SET requests=requests-?,credits=credits-? WHERE provider=? AND day=?').run(
      old.requests-c.requests_started, c.requests_started === 0 ? old.credits : 0, old.provider, old.day);
    db.prepare('UPDATE evidence_reservations SET started=?,state=? WHERE id=?').run(c.requests_started,state,c.id);
  }
  return one(db, 'SELECT * FROM evidence_reservations WHERE id=?', c.id) as unknown as EvidenceReservation;
}
