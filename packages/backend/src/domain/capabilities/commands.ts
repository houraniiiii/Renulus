// SPDX-License-Identifier: MIT
import type { DatabaseSync } from 'node:sqlite';
import type { CapabilityCommand, CapabilityEnvelope, CapabilityGrant, CapabilityLease, CapabilityResults } from './contracts.ts';
import { exact, integer, reject, text } from '../../storage/contracts.ts';
import { canonical, one, rows } from '../../storage/schema.ts';
import { executeDispatch } from '../../storage/dispatch.ts';
import { requireAssistance } from '../../storage/conversation.ts';

/** Integrator installs this additive migration while admission is closed. */
export const CAPABILITY_SCHEMA = `CREATE TABLE IF NOT EXISTS capability_effects (
 id TEXT PRIMARY KEY, root_id TEXT NOT NULL, run_id TEXT NOT NULL, call_id TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL, envelope_json TEXT NOT NULL, action TEXT NOT NULL, grant_json TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('admitted','closed','settled','uncertain')),
 used_bytes INTEGER NOT NULL DEFAULT 0 CHECK(used_bytes>=0), effect_reference TEXT);
 CREATE INDEX IF NOT EXISTS capability_effects_root ON capability_effects(root_id,state);
 CREATE TABLE IF NOT EXISTS capability_closed_roots(root_id TEXT PRIMARY KEY);`;
const types = new Set(['capability.admit', 'capability.current', 'capability.close', 'capability.settle', 'capability.pending']);
const id = (v: unknown) => { text(v, 1, 256); if (!/^[A-Za-z0-9][A-Za-z0-9._:-]*$/.test(v)) reject('capability_invalid_identity'); };
const sha = (v: unknown) => { text(v, 64, 64); if (!/^[a-f0-9]{64}$/.test(v)) reject('capability_invalid_digest'); };
export function validateEnvelope(e: CapabilityEnvelope): void {
  exact(e, ['run_id', 'root_id', 'session_id', 'call_id', 'configuration', 'grant_epoch', 'fence', 'retention', 'mode', 'depth']);
  [e.run_id,e.root_id,e.session_id,e.call_id,e.configuration].forEach(id); integer(e.grant_epoch); integer(e.depth, 0, 1);
  if (!['doctor','developer'].includes(e.mode) || !['saved','temporary'].includes(e.retention)) reject('capability_invalid_envelope');
  exact(e.fence, ['profile_id','domain_store_id','runtime_store_id','authority_epoch','process_generation','context_epoch','deletion_epoch','cancellation_epoch']);
  [e.fence.profile_id,e.fence.domain_store_id,e.fence.runtime_store_id,e.fence.process_generation].forEach(id);
  [e.fence.authority_epoch,e.fence.context_epoch,e.fence.deletion_epoch,e.fence.cancellation_epoch].forEach(v => integer(v));
}
export function validateGrant(g: CapabilityGrant): void {
  exact(g, ['actions','roots','endpoints','skills','max_bytes','expires_at_ms']); integer(g.max_bytes, 1, 100*1024*1024); integer(g.expires_at_ms, 1);
  for (const values of [g.actions,g.skills]) { if (!Array.isArray(values) || values.length > 128) reject('capability_invalid_grant'); values.forEach(id); }
  if (!Array.isArray(g.roots) || g.roots.length > 16 || !Array.isArray(g.endpoints) || g.endpoints.length > 32) reject('capability_invalid_grant');
  for (const root of g.roots) { exact(root, ['path','read','write','execute']); text(root.path,1,1024);
    if ([root.read,root.write,root.execute].some(v=>typeof v !== 'boolean')) reject('capability_invalid_grant'); }
  for (const target of g.endpoints) { exact(target,['host','port','private_network']); text(target.host,1,253); integer(target.port,1,65535);
    if (typeof target.private_network !== 'boolean' || !/^[a-zA-Z0-9.:_-]+$/.test(target.host)) reject('capability_invalid_grant'); }
}
export function isCapabilityCommand(v: unknown): v is CapabilityCommand {
  return !!v && typeof v === 'object' && 'type' in v && types.has(String(v.type));
}
export function validateCapabilityCommand(c: CapabilityCommand): void {
  switch(c.type) {
    case 'capability.admit': exact(c,['type','id','envelope','action','payload_sha256','grant']); id(c.id); validateEnvelope(c.envelope); id(c.action); sha(c.payload_sha256); validateGrant(c.grant); break;
    case 'capability.current': exact(c,['type','id','envelope','bytes','now_ms']); id(c.id); validateEnvelope(c.envelope); integer(c.bytes,0,100*1024*1024); integer(c.now_ms,1); break;
    case 'capability.close': case 'capability.pending': exact(c,['type','root_id']); id(c.root_id); break;
    case 'capability.settle': exact(c,['type','id','outcome','effect_reference']); id(c.id); if(!['settled','uncertain'].includes(c.outcome)) reject('capability_invalid_outcome'); if(c.effect_reference !== null) text(c.effect_reference,1,512); break;
    default: reject('storage_invalid_command');
  }
}
function read(db: DatabaseSync, id: string): CapabilityLease {
  const row = one(db,'SELECT * FROM capability_effects WHERE id=?',id); if(!row) reject('capability_missing');
  return {id:String(row.id),envelope:JSON.parse(String(row.envelope_json)),action:String(row.action),payload_sha256:String(row.payload_sha256),
    grant:JSON.parse(String(row.grant_json)),state:row.state as CapabilityLease['state'],used_bytes:Number(row.used_bytes),effect_reference:row.effect_reference as string|null};
}
function current(db: DatabaseSync, e: CapabilityEnvelope, action: string): void {
  requireAssistance(db);
  const snapshot = executeDispatch(db,{type:'dispatch.snapshot'});
  if(snapshot.effective !== e.configuration || snapshot.grant_epoch !== e.grant_epoch ||
      one(db,'SELECT 1 FROM capability_closed_roots WHERE root_id=?',e.root_id)) reject('capability_stale');
  const run = executeDispatch(db,{type:'dispatch.current',runId:e.run_id,fence:e.fence,requiredCapabilities:[action],permitId:null});
  if(run.root_id !== e.root_id || (e.depth === 0) !== (run.parent_id === null)) reject('capability_parent_conflict');
  if(action.startsWith('developer.') && (e.mode !== 'developer' || e.retention !== 'saved' || e.depth !== 0)) reject('developer_profile_required');
}
/** Called inside the ONE storage worker's local transaction. No I/O or async work. */
export function executeCapabilityCommand<C extends CapabilityCommand>(db: DatabaseSync,c:C): CapabilityResults[C['type']] {
  validateCapabilityCommand(c); if(!db.isTransaction) reject('capability_transaction_required');
  let result: unknown;
  switch(c.type) {
    case 'capability.admit': {
      current(db,c.envelope,c.action);
      if(!c.grant.actions.includes(c.action) || c.grant.expires_at_ms <= Date.now() || c.grant.expires_at_ms > Date.now()+300_000) reject('capability_grant_denied');
      const old=one(db,'SELECT id FROM capability_effects WHERE id=?',c.id);
      if(old) { const lease=read(db,String(old.id)); if(lease.id!==c.id || lease.payload_sha256!==c.payload_sha256 || canonical(lease.envelope)!==canonical(c.envelope) || canonical(lease.grant)!==canonical(c.grant)) reject('idempotency_conflict'); reject('capability_already_admitted'); }
      db.prepare("INSERT INTO capability_effects VALUES(?,?,?,?,?,?,?,?,'admitted',0,NULL)").run(c.id,c.envelope.root_id,c.envelope.run_id,c.envelope.call_id,c.payload_sha256,canonical(c.envelope),c.action,canonical(c.grant));
      result=read(db,c.id); break;
    }
    case 'capability.current': {
      const lease=read(db,c.id); if(lease.state!=='admitted' || canonical(lease.envelope)!==canonical(c.envelope)) reject('capability_stale');
      current(db,c.envelope,lease.action);
      if(lease.grant.expires_at_ms<=Math.max(Date.now(),c.now_ms) || lease.used_bytes+c.bytes>lease.grant.max_bytes) reject('capability_limit');
      db.prepare('UPDATE capability_effects SET used_bytes=used_bytes+? WHERE id=?').run(c.bytes,c.id); result=read(db,c.id); break;
    }
    case 'capability.close': db.prepare('INSERT OR IGNORE INTO capability_closed_roots VALUES(?)').run(c.root_id);
      result={closed:Number(db.prepare("UPDATE capability_effects SET state='closed' WHERE root_id=? AND state='admitted'").run(c.root_id).changes)}; break;
    case 'capability.settle': { const old=read(db,c.id); if(old.state==='settled'||old.state==='uncertain') {
      if(old.state!==c.outcome||old.effect_reference!==c.effect_reference) reject('capability_settlement_conflict'); result=old; break; }
      db.prepare('UPDATE capability_effects SET state=?,effect_reference=? WHERE id=?').run(c.outcome,c.effect_reference,c.id); result=read(db,c.id); break; }
    case 'capability.pending': result=rows(db,"SELECT id FROM capability_effects WHERE root_id=? AND state IN ('admitted','closed','uncertain') ORDER BY id",c.root_id).map(r=>read(db,String(r.id))); break;
  }
  return result as CapabilityResults[C['type']];
}
