// SPDX-License-Identifier: MIT
/** Shared local predicates from test_repository.py and attempt_repository.py. */
import { randomUUID } from 'node:crypto';
import type { DatabaseSync } from 'node:sqlite';
import type { ObjectValue, Policy, Stamp, TestVersion } from './contracts.ts';
import { canonical,digest,one } from '../../storage/schema.ts';
import { reject } from '../../storage/contracts.ts';
import { utcNow } from '../../storage/export.ts';
export const uid=(prefix:string)=>prefix+'_'+randomUUID().replaceAll('-','');
export const decode=(v:unknown)=>JSON.parse(String(v));
export const deleted=(db:DatabaseSync,kind:string,id:string)=>!!one(db,'SELECT 1 FROM deletion_ledger WHERE entity_type=? AND entity_id=?',kind,id);
export function policy(db:DatabaseSync):Policy {
  const r=one(db,"SELECT value FROM preferences WHERE key='design_c.assessment_policy_revision'");
  const a=one(db,"SELECT id FROM assessment_test_attempts WHERE mode='test' AND status='active' LIMIT 1");
  return {revision:r?Number(r.value):1,active_test_id:a?String(a.id):null,assistance_allowed:!a};
}
export function bumpPolicy(db:DatabaseSync) {db.prepare("INSERT INTO preferences VALUES('design_c.assessment_policy_revision','2',?) ON CONFLICT(key) DO UPDATE SET value=CAST(CAST(preferences.value AS INTEGER)+1 AS TEXT),updated_at=excluded.updated_at").run(utcNow());}
export function stamp(db:DatabaseSync):Stamp { return {policy_revision:policy(db).revision,context_epoch:Number(one(db,"SELECT value FROM preferences WHERE key='design_c.context_epoch'")?.value??0)}; }
export function assistance(db:DatabaseSync,expected?:number) {const p=policy(db);if(!p.assistance_allowed)reject('assistance_restricted');if(expected!==undefined&&expected!==p.revision)reject('assistance_changed');return p;}
export function currentStamp(db:DatabaseSync,s:Stamp) {assistance(db,s.policy_revision);if(stamp(db).context_epoch!==s.context_epoch)reject('generation_context_changed');}
export function allowed(db:DatabaseSync,attemptId?:string) {const p=policy(db);if(p.active_test_id&&p.active_test_id!==attemptId)reject('attempt_restricted');return p;}
export function test(db:DatabaseSync,id:string):ObjectValue {const t=one(db,'SELECT * FROM assessment_tests WHERE id=?',id);if(!t||t.lifecycle==='deleted'||deleted(db,'saved_test',id))reject('not_found');return t;}
export function pinned(db:DatabaseSync,id:string):TestVersion {
  const v=one(db,'SELECT * FROM assessment_test_versions WHERE id=?',id);if(!v||deleted(db,'saved_test_version',id))reject('not_found');test(db,String(v.test_id));
  return {id:String(v.id),test_id:String(v.test_id),ordinal:Number(v.ordinal),origin:v.origin as TestVersion['origin'],review_quality:v.review_quality as TestVersion['review_quality'],status:v.status as TestVersion['status'],items:decode(v.items_json),source_refs:decode(v.source_refs_json),terms:String(v.terms),created_at:String(v.created_at),provenance:decode(v.provenance_json).producer};
}
export const bank=(v:TestVersion)=>v.origin==='reviewed_bank'&&v.review_quality==='reviewed'&&v.status==='ready';
export function replay(db:DatabaseSync,table:'assessment_test_commands'|'assessment_attempt_commands',key:string,operation:string,target:string,body:unknown):ObjectValue|null {
  const r=one(db,`SELECT * FROM ${table} WHERE idempotency_key=?`,key);if(!r)return null;
  if(r.operation!==operation||r.request_hash!==digest(canonical(body))||(target&&r.target_id!==target))reject('idempotency_conflict');
  if(table==='assessment_attempt_commands'&&deleted(db,'test_attempt',String(r.target_id)))reject('not_found');
  const out=decode(r.result_json);if(out.policy)out.policy=policy(db);return out;
}
export function record(db:DatabaseSync,table:'assessment_test_commands'|'assessment_attempt_commands',key:string,operation:string,targetType:string,target:string,body:unknown,result:ObjectValue) {
  db.prepare(`INSERT INTO ${table} VALUES(?,?,?,?,?,?,?)`).run(key,operation,targetType,target,digest(canonical(body)),canonical(result),utcNow());return result;
}
