// SPDX-License-Identifier: MIT
import type { DatabaseSync } from 'node:sqlite';
import type { EvidenceCommand, EvidenceReservation, EvidenceResults } from './contracts.ts';
import { exact, integer, reject, text } from '../../storage/contracts.ts';
import { canonical, digest, one, rows } from '../../storage/schema.ts';
import { requireAssistance } from '../../storage/conversation.ts';
import { effectiveKnowledgeMetadata, samePublication } from '../knowledge/source-status.ts';
import type { Json, Metadata, Rights } from '../knowledge/contracts.ts';
export function isEvidenceCommand(v: unknown): v is EvidenceCommand {
  return !!v && typeof v === 'object' && 'type' in v && ['evidence.reserve', 'evidence.settle', 'evidence.check', 'evidence.current'].includes(String(v.type));
}
export function validateEvidenceCommand(c: EvidenceCommand): void {
  if (c.type === 'evidence.current') {
    exact(c, ['type', 'stamp']); if (!/^[a-f0-9]{64}$/.test(c.stamp)) reject('evidence_invalid_stamp'); return;
  }
  if (c.type === 'evidence.check') {
    exact(c, ['type', 'passages']);
    if (!Array.isArray(c.passages) || c.passages.length > 20 || Buffer.byteLength(JSON.stringify(c.passages)) > 1024 * 1024) reject('evidence_invalid_passages');
    for (const p of c.passages) {
      text(p.id, 1, 256); text(p.text, 1, 16000); text(p.canonical_url, 1, 4096);
      if (!p.metadata || !p.rights || !Array.isArray(p.locators)) reject('evidence_invalid_passages');
    }
    return;
  }
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
export function executeEvidenceCommand<C extends EvidenceCommand>(db: DatabaseSync, c: C): EvidenceResults[C['type']];
export function executeEvidenceCommand(db: DatabaseSync, c: EvidenceCommand): EvidenceResults[EvidenceCommand['type']] {
  validateEvidenceCommand(c); if (!db.isTransaction) reject('evidence_transaction_required');
  if (c.type === 'evidence.check' || c.type === 'evidence.current') {
    requireAssistance(db);
    const documents = rows(db, 'SELECT d.id,d.reserved,d.deleted_at,r.sha256,r.metadata_json,r.rights_json FROM knowledge_documents d JOIN knowledge_revisions r ON r.document_id=d.id ORDER BY d.id,r.id');
    const catalogue = rows(db, 'SELECT id,reserved,eligibility,expected_sha256,metadata_json,rights_json FROM knowledge_catalogue ORDER BY id');
    const reserved = rows(db, 'SELECT p.text FROM knowledge_passages p JOIN knowledge_revisions r ON r.id=p.revision_id JOIN knowledge_documents d ON d.id=r.document_id WHERE d.reserved=1 ORDER BY p.id');
    const questions = rows(db, "SELECT body_json FROM content_question_versions WHERE json_extract(body_json,'$.usage')='assessment_reserved' ORDER BY question_id,version");
    const stamp = digest(canonical({ documents, catalogue, reserved, questions, day: new Date().toISOString().slice(0,10),
      events: rows(db, 'SELECT id,request_hash FROM knowledge_source_status_events ORDER BY created_at,rowid') }));
    if (c.type === 'evidence.current') {
      if (c.stamp !== stamp) reject('source_evidence_changed');
      return { stamp };
    }
    const reservedHashes = new Set(reserved.map(row => digest(String(row.text))));
    for (const row of questions) {
      const question = JSON.parse(String(row.body_json));
      for (const field of ['stem', 'prompt', 'text', 'rationale']) if (typeof question[field] === 'string') reservedHashes.add(digest(question[field]));
    }
    const passages = c.passages.flatMap(p => {
      const metadata = p.metadata, rights = p.rights;
      if (p.source_kind !== 'public-article' || metadata.source_id !== 'L03' || typeof metadata.pmcid !== 'string' ||
        !/^PMC[1-9][0-9]*$/.test(metadata.pmcid) || metadata.canonical_url !== 'https://europepmc.org/articles/' + metadata.pmcid ||
        p.canonical_url !== metadata.canonical_url || p.publication_date !== metadata.publication_date || !metadata.original_sha256 ||
        !metadata.publication_date || !p.locators.length || !['display','cache','model_input','derivation'].every(key => rights[key as keyof Rights] === true) ||
        !['CC-BY-2.0','CC-BY-3.0','CC-BY-4.0','CC0-1.0'].includes(rights.licence) || reservedHashes.has(digest(p.text))) return [];
      const effective = effectiveKnowledgeMetadata(db, metadata);
      if (excluded(effective)) return [];
      for (const row of [...documents, ...catalogue]) {
        const other = JSON.parse(String(row.metadata_json)) as Metadata;
        const matches = samePublication(metadata, { source_id: metadata.source_id, identity: other as Record<string, Json>, changes: {} }) ||
          metadata.original_sha256 === (row.sha256 ?? row.expected_sha256 ?? other.original_sha256);
        if (!matches) continue;
        const permissions = JSON.parse(String(row.rights_json)) as Rights;
        if (row.reserved || row.deleted_at || row.eligibility && row.eligibility !== 'eligible' || excluded(effectiveKnowledgeMetadata(db, other)) ||
          !['display','cache','model_input','derivation'].every(key => permissions[key as keyof Rights] === true)) return [];
      }
      return [{ ...p, metadata: effective }];
    });
    return { passages, stamp };
  }
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
function excluded(metadata: Metadata) {
  return metadata.retracted || metadata.superseded || metadata.repository_removed || metadata.access_changed ||
    (metadata.replaced_topics as unknown[] | undefined)?.length || ['draft','preprint'].includes(String(metadata.publication_status)) ||
    metadata.correction && !metadata.content_reviewed || metadata.review_due && String(metadata.review_due).slice(0,10) < new Date().toISOString().slice(0,10);
}
