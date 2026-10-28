// SPDX-License-Identifier: MIT
/** Local canonical merge. Called synchronously inside the ONE writer transaction.
 * Typed ownership policy mirrors storage/relations.py and recovery_records.py.
 * Native graph I/O and original publication occur before this command.
 */
import type { DatabaseSync } from 'node:sqlite';
import policy from '../domain/recovery/policy.json' with {type:'json'};
import type { NativeMapping, RecoveryCommand, RecoveryMerge, RecoveryRecords, RecoverySnapshot } from '../domain/recovery/contracts.ts';
import type { RecordRow } from './contracts.ts';
import { exact, integer, reject, text } from './contracts.ts';
import { canonical, digest, inventory, one, quote, rows } from './schema.ts';
import { exportRecords } from './export.ts';
import { reconcileMemorySupport } from './memory.ts';
import { reserveStorage, reservationStatus, settleStorage } from './reservations.ts';
const hash=(v:unknown)=>digest(canonical(v));
const exists=(db:DatabaseSync,t:string)=>!!one(db,"SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",t);
const keys=(db:DatabaseSync,t:string)=>rows(db,`PRAGMA table_info(${quote(t)})`).filter(c=>Number(c.pk)>0).sort((a,b)=>Number(a.pk)-Number(b.pk)).map(c=>String(c.name));
const identity=(t:string,r:RecordRow,pk:string[])=>canonical([t,pk.map(k=>r[k])]);
type Binding={parent:string;columns:string[];kind:string;discriminator:string[]|null;prefix:string};
const parents=policy.parents as Record<string,Binding[]>;
const tombstones=policy.tombstones as Record<string,string>;
export function recoveryFrontierDigest(db:DatabaseSync):string {
  const result:Record<string,RecordRow[]>={};
  for(const t of ['deletion_ledger','memory_suppression','memory_facts','memory_answer_lineage','memory_support_groups','memory_support_inputs','knowledge_documents','knowledge_source_status_events','harness_configuration_grants','harness_configuration_pointer','preferences']) {
    if(exists(db,t))result[t]=rows(db,`SELECT * FROM ${quote(t)} ORDER BY rowid`);
  }
  return hash(result);
}
function schemaHash(db:DatabaseSync) {return inventory(db,Object.fromEntries(rows(db,'SELECT name,checksum FROM migration_ledger').map(r=>[String(r.name),String(r.checksum)]))).schemaHash;}
export function snapshotRecovery(db:DatabaseSync):RecoverySnapshot {
  const records=exportRecords(db).records;
  for(const table of ['knowledge_revisions','knowledge_attachment_originals'])for(const row of records[table]??[])
    row.original_path=one(db,`SELECT original_path FROM ${quote(table)} WHERE id=?`,String(row.id))!.original_path;
  return {records,frontierDigest:recoveryFrontierDigest(db),schemaHash:schemaHash(db)};
}
function rewrite(value:unknown,m:NativeMapping,active=false):unknown {
  if(Array.isArray(value))return value.map(v=>rewrite(v,m,active));
  if(!value||typeof value!=='object')return value;
  const input=value as Record<string,unknown>,native=active||input.store_id===m.incomingStore||!!(input.runtime&&typeof input.runtime==='object'&&(input.runtime as Record<string,unknown>).store_id===m.incomingStore);
  const output:Record<string,unknown>={};
  for(const [key,v]of Object.entries(input)) {
    if(native&&key==='store_id'&&v===m.incomingStore)output[key]=m.candidateStore;
    else if(native&&['session_id','sessionId','sessionID'].includes(key)&&typeof v==='string')output[key]=m.sessions[v]??reject('recovery_native_reference_missing');
    else if(native&&['message_id','input_id','messageId','messageID'].includes(key)&&typeof v==='string')output[key]=m.messages[v]??reject('recovery_native_reference_missing');
    else if(native&&key==='message_ids'&&Array.isArray(v))output[key]=v.map(id=>m.messages[String(id)]??reject('recovery_native_reference_missing'));
    else output[key]=rewrite(v,m,native);
  }return output;
}
export function mapRecoveryRecords(records:RecoveryRecords,m:NativeMapping):{records:RecoveryRecords;mappedReferences:number} {
  let count=0;const mapped=structuredClone(records);
  for(const [table,rr]of Object.entries(mapped))for(const row of rr) {
    const native=row.store_id===m.incomingStore;
    if(native) {row.store_id=m.candidateStore;if(typeof row.session_id==='string') {row.session_id=m.sessions[row.session_id]??reject('recovery_native_reference_missing');count++;}}
    if(table==='learn_harness_answers'&&typeof row.input_id==='string')row.input_id=m.messages[row.input_id]??reject('recovery_native_reference_missing');
    for(const [column,value]of Object.entries(row))if(column.endsWith('_json')&&typeof value==='string') {
      let parsed:unknown;try{parsed=JSON.parse(value);}catch{reject('recovery_records_invalid');}
      const next=canonical(rewrite(parsed,m,native));if(next!==canonical(parsed))count++;row[column]=next;
    }
  }return {records:mapped,mappedReferences:count};
}
function conflictColumns(table:string,row:RecordRow):string[] {
  if(table.startsWith('content_')&&'sha256'in row)return Object.keys(row).filter(k=>k!=='installed_at');
  if(table==='knowledge_revisions')return ['document_id','sha256','bytes','media_type'];
  if(table==='knowledge_attachment_originals')return ['attachment_id','role','sha256','bytes'];
  if(table==='knowledge_attachments')return ['chat_kind','chat_id','media_type'];
  if(['learn_messages','case_attachments','case_attachment_parts','assessment_test_versions','assessment_question_versions'].includes(table))return Object.keys(row);
  return [];
}
// Native links whose sessions the native owner must supply before the canonical merge can be validated.
const nativeLinks=['learn_harness_mappings','learn_harness_migrations'];
const sessionOf=(table:string,row:RecordRow)=>nativeLinks.includes(table)&&typeof row.session_id==='string'?row.session_id:null;
/** A preview has no native candidate yet: every native identity maps to itself and nothing is committed. */
const previewMapping=():NativeMapping=>({incomingStore:'',candidateStore:'',sessions:new Proxy({},{get:(_,k)=>String(k)}),messages:new Proxy({},{get:(_,k)=>String(k)})});
export function mergeRecovery(db:DatabaseSync,incoming:RecoverySnapshot,mapping:NativeMapping,currentFrontierDigest:string):RecoveryMerge {
  if(recoveryFrontierDigest(db)!==currentFrontierDigest)reject('recovery_frontier_changed');
  if(schemaHash(db)!==incoming.schemaHash)reject('recovery_schema_mismatch');
  // Without the sender's deletion frontier nothing can be proven undeleted: refuse rather than guess.
  if(!Array.isArray(incoming.records?.deletion_ledger))reject('recovery_frontier_missing');
  const current=exportRecords(db).records,added=structuredClone(incoming.records);
  const pks:Record<string,string[]>={},known=new Map<string,RecordRow>(),blocked=new Set<string>(),edges=new Map<string,Set<string>>();
  for(const table of Object.keys(current)) {
    pks[table]=keys(db,table);if(!pks[table].length)reject('recovery_schema_identity');
    for(const row of current[table])known.set(identity(table,row,pks[table]),row);
  }
  let count=0;
  for(const [table,rr]of Object.entries(added)) {
    if(!Object.hasOwn(current,table)||!Array.isArray(rr))reject('recovery_table');
    const columns=rows(db,`PRAGMA table_info(${quote(table)})`).map(c=>String(c.name));const seen=new Set<string>();
    for(const row of rr) {
      if(++count>100000||Object.keys(row).sort().join(',')!==[...columns].sort().join(',')||Object.values(row).some(v=>!(v===null||typeof v==='string'||typeof v==='number'&&Number.isFinite(v))))reject('recovery_records_invalid');
      const id=identity(table,row,pks[table]);if(seen.has(id))reject('recovery_duplicate');seen.add(id);
    }
  }
  if(Buffer.byteLength(canonical(added))>16*1024*1024)reject('recovery_limit');
  for(const records of [current,added])for(const [table,rr]of Object.entries(records))for(const row of rr) {
    if(table==='deletion_ledger') {const target=tombstones[String(row.entity_type)];if(target)blocked.add(canonical([target,[row.entity_id]]));continue;}
    for(const binding of parents[table]??[]) {
      if(binding.discriminator&&row[binding.discriminator[0]]!==binding.discriminator[1])continue;
      const values=binding.columns.map(k=>row[k]);if(values.some(v=>v===null||v===undefined))continue;
      if(binding.prefix) {if(typeof values[0]!=='string'||!values[0].startsWith(binding.prefix))continue;values[0]=values[0].slice(binding.prefix.length);}
      const parent=canonical([binding.parent,values]),children=edges.get(parent)??new Set();children.add(identity(table,row,pks[table]));edges.set(parent,children);
    }
  }
  const queue=[...blocked];for(let i=0;i<queue.length;i++)for(const child of edges.get(queue[i])??[])if(!blocked.has(child)){blocked.add(child);queue.push(child);}
  const result:RecoveryMerge={retained:0,currentOnly:0,added:0,excluded:0,conflicts:0,mappedReferences:0,captureBarriers:0,eligibleNativeSessions:[],excludedNativeSessions:[]};
  const kept=new Set<string>(),dropped=new Set<string>();
  for(const [table,rr]of Object.entries(current))for(const row of rr){const s=sessionOf(table,row);if(s)kept.add(s);}
  // Apply current + incoming deletion frontier first, before any payload can become eligible.
  db.exec('PRAGMA defer_foreign_keys=ON');
  for(const row of added.deletion_ledger??[])db.prepare('INSERT INTO deletion_ledger VALUES(?,?,?) ON CONFLICT(entity_type,entity_id) DO UPDATE SET deleted_at=MAX(deletion_ledger.deleted_at,excluded.deleted_at)').run(row.entity_type,row.entity_id,row.deleted_at);
  for(const [table,rr]of Object.entries(current))for(const row of rr)if(table!=='deletion_ledger'&&blocked.has(identity(table,row,pks[table])))db.prepare(`DELETE FROM ${quote(table)} WHERE ${pks[table].map(k=>quote(k)+' IS ?').join(' AND ')}`).run(...pks[table].map(k=>row[k]));
  const incomingIds=new Set<string>();
  const addedEvidence:string[]=[];
  for(const [table,rr]of Object.entries(added))for(const row of rr) {
    if(table==='deletion_ledger')continue;const id=identity(table,row,pks[table]);incomingIds.add(id);
    const session=sessionOf(table,row);
    if(blocked.has(id)){result.excluded++;if(session)dropped.add(session);continue;}
    const existing=known.get(id);
    if(session)kept.add(session);
    if(existing) {if(conflictColumns(table,row).some(k=>existing[k]!==row[k]))reject('recovery_immutable_conflict');result.retained++;continue;}
    // Never import runnable jobs, engine readiness or opaque summary/Finder projections.
    if(/^(memory_index_|knowledge_index_)/.test(table)||['learn_harness_purges','learn_harness_migrations'].includes(table)){result.excluded++;continue;}
    const rewritten=mapRecoveryRecords({[table]:[row]},mapping);result.mappedReferences+=rewritten.mappedReferences;
    const staged=rewritten.records[table][0];
    if(table==='memory_jobs'){staged.state='cancelled';staged.error_code='restore_explicit_capture';}
    if(table==='knowledge_jobs'){staged.state='cancelled';staged.error_code='restore_interrupted';}
    if(table==='learn_harness_answers'&&['reserved','submitted','uncertain'].includes(String(staged.state)))staged.state='cancelled';
    if(table==='memory_answer_lineage')staged.state='revoked';
    // A suppression/correction known in the current profile always wins.
    if(table==='memory_sources'&&one(db,'SELECT 1 FROM memory_suppression WHERE source_key=?',String(staged.source_key))){result.excluded++;continue;}
    if(table==='memory_history'&&one(db,'SELECT revision FROM memory_facts WHERE id=? AND revision>?',String(staged.record_id),Number(staged.revision))){result.excluded++;continue;}
    const columns=Object.keys(staged);db.prepare(`INSERT INTO ${quote(table)}(${columns.map(quote).join(',')}) VALUES(${columns.map(()=>'?').join(',')})`).run(...columns.map(k=>staged[k]));result.added++;
    if(table==='learning_evidence')addedEvidence.push(String(row.id));
  }
  for(const id of known.keys())if(!incomingIds.has(id)&&!blocked.has(id))result.currentOnly++;
  for(const id of addedEvidence) {
    // A barrier is not a suppression and is never consumed by global Retry.
    const key='memory.restore_barrier:'+id;
    db.prepare('INSERT OR IGNORE INTO preferences VALUES(?,?,?)').run(key,'explicit-capture-required',new Date().toISOString());result.captureBarriers++;
  }
  for(const [table,refs]of Object.entries(policy.unavailable))if(exists(db,table))for(const [column,target,targetColumn]of refs)if(exists(db,target))db.exec(`UPDATE ${quote(table)} SET ${quote(column)}=NULL WHERE ${quote(column)} IS NOT NULL AND NOT EXISTS(SELECT 1 FROM ${quote(target)} WHERE ${quote(target)}.${quote(targetColumn)}=${quote(table)}.${quote(column)})`);
  // Derived engine readiness is invalid after recovery. Physical purge settles outside this transaction.
  if(exists(db,'memory_index_state'))db.exec("UPDATE memory_index_state SET epoch=epoch+1,state='dirty',fingerprint=NULL,generation=NULL; DELETE FROM memory_index_entries");
  reconcileMemorySupport(db);
  if(rows(db,'PRAGMA foreign_key_check').length)reject('recovery_references');
  result.eligibleNativeSessions=[...kept].sort();result.excludedNativeSessions=[...dropped].filter(s=>!kept.has(s)).sort();
  return result;
}
/** Read-only by construction: the identical merge runs in a savepoint that is always rolled back. */
export function previewRecovery(db:DatabaseSync,incoming:RecoverySnapshot,currentFrontierDigest:string):RecoveryMerge {
  db.exec('SAVEPOINT recovery_preview');
  try {return mergeRecovery(db,incoming,previewMapping(),currentFrontierDigest);}
  finally {db.exec('ROLLBACK TO recovery_preview; RELEASE recovery_preview');}
}
function checkRollback(db:DatabaseSync,incoming:RecoverySnapshot,currentFrontierDigest:string):{compatible:true} {
  previewRecovery(db,incoming,currentFrontierDigest);
  const current=snapshotRecovery(db).records;
  for(const [table,rr]of Object.entries(current)) {
    if(['deletion_ledger','memory_suppression','preferences'].includes(table)||/^(memory_index_|knowledge_index_)/.test(table))continue;
    const pk=keys(db,table),incomingIds=new Set((incoming.records[table]??[]).map(r=>identity(table,r,pk)));
    for(const row of rr)if(!incomingIds.has(identity(table,row,pk)))reject('recovery_rollback_newer_records');
  }
  return {compatible:true};
}
/** Every canonical native link must resolve in the supplied native graph (current and incoming links alike). */
export function verifyNativeClosure(records:RecoveryRecords,native:{sessions:ReadonlySet<string>;messages:ReadonlySet<string>}) {
  for(const [table,rr]of Object.entries(records))for(const row of rr) {
    const session=sessionOf(table,row);
    if(session&&!native.sessions.has(session))reject('recovery_native_closure');
    if(table==='learn_harness_answers'&&typeof row.input_id==='string'&&!native.messages.has(row.input_id))reject('recovery_native_closure');
  }
}
export function isRecoveryCommand(v:unknown):v is RecoveryCommand {return !!v&&typeof v==='object'&&'type'in v&&typeof v.type==='string'&&['recovery.snapshot','recovery.preview','recovery.rollback','recovery.merge','recovery.originals','storage.reserve','storage.settle','storage.reservations'].includes(v.type);}
export function validateRecoveryCommand(v:RecoveryCommand) {
  switch(v.type) {
    case 'recovery.originals':exact(v,['type','originals']);if(!Array.isArray(v.originals)||v.originals.length>100000)reject('recovery_limit');for(const r of v.originals){exact(r,['table','id','handle']);if(!['knowledge_revisions','knowledge_attachment_originals'].includes(r.table))reject('recovery_table');text(r.id,1,256);if(r.handle!==null)text(r.handle,1,4096);}break;
    case 'recovery.snapshot':case 'storage.reservations':exact(v,['type']);break;
    case 'storage.reserve':exact(v,['type','request']);exact(v.request,['id','intentId','peakBytes','allocatedBytes','freeBytes','ceilingBytes']);text(v.request.id,1,128);text(v.request.intentId,1,128);for(const k of ['peakBytes','allocatedBytes','freeBytes','ceilingBytes']as const)integer(v.request[k]);integer(v.request.peakBytes,1);integer(v.request.ceilingBytes,50_000_000_000,150_000_000_000);break;
    case 'storage.settle':exact(v,['type','id','intentId','settled','cleanupDebtBytes']);text(v.id,1,128);text(v.intentId,1,128);integer(v.cleanupDebtBytes);if(typeof v.settled!=='boolean')reject('storage_invalid_command');break;
    case 'recovery.rollback':case 'recovery.preview':exact(v,['type','incoming','currentFrontierDigest']);exact(v.incoming,['records','frontierDigest','schemaHash']);for(const s of [v.currentFrontierDigest,v.incoming.frontierDigest,v.incoming.schemaHash])if(!/^[a-f0-9]{64}$/.test(s))reject('storage_invalid_command');if(Buffer.byteLength(canonical(v.incoming))>16*1024*1024)reject('recovery_limit');break;
    case 'recovery.merge':exact(v,['type','incoming','mapping','currentFrontierDigest']);exact(v.incoming,['records','frontierDigest','schemaHash']);exact(v.mapping,['incomingStore','candidateStore','sessions','messages']);for(const s of [v.currentFrontierDigest,v.incoming.frontierDigest,v.incoming.schemaHash])if(!/^[a-f0-9]{64}$/.test(s))reject('storage_invalid_command');text(v.mapping.incomingStore,1,128);text(v.mapping.candidateStore,1,128);if(Buffer.byteLength(canonical(v.incoming))>16*1024*1024)reject('recovery_limit');break;
  }
}
export function executeRecovery(db:DatabaseSync,c:RecoveryCommand) {switch(c.type){case 'recovery.rollback':return checkRollback(db,c.incoming,c.currentFrontierDigest);case 'recovery.originals':{let updated=0;for(const r of c.originals)updated+=Number(db.prepare(`UPDATE ${quote(r.table)} SET original_path=? WHERE id=?`).run(r.handle,r.id).changes);return {updated};}case 'recovery.snapshot':return snapshotRecovery(db);case 'recovery.preview':return previewRecovery(db,c.incoming,c.currentFrontierDigest);case 'recovery.merge':return mergeRecovery(db,c.incoming,c.mapping,c.currentFrontierDigest);case 'storage.reserve':return reserveStorage(db,c.request);case 'storage.settle':return settleStorage(db,c.id,c.intentId,c.settled,c.cleanupDebtBytes);case 'storage.reservations':return reservationStatus(db);}}
