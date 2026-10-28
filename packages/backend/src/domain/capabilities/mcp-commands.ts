// SPDX-License-Identifier: MIT
import type { DatabaseSync } from 'node:sqlite';
import type { McpSetting } from './mcp.ts';
import { exact, integer, reject, text } from '../../storage/contracts.ts';
import { canonical, digest, one, rows } from '../../storage/schema.ts';

export interface McpConnection { setting: McpSetting; approved: boolean; grantedEpoch: number }
export type McpConnectionCommand =
  | { type: 'mcp.connection.save'; setting: McpSetting; idempotencyKey: string }
  | { type: 'mcp.connection.get'; name: string }
  | { type: 'mcp.connection.list' }
  | { type: 'mcp.connection.approve' | 'mcp.connection.revoke' | 'mcp.connection.remove'; name: string; idempotencyKey: string };
export interface McpConnectionResults {
  'mcp.connection.save': McpConnection;
  'mcp.connection.get': McpConnection | null;
  'mcp.connection.list': McpConnection[];
  'mcp.connection.approve': McpConnection;
  'mcp.connection.revoke': McpConnection;
  'mcp.connection.remove': { credentialRef: string };
}
export const isMcpConnectionCommand = (v: unknown): v is McpConnectionCommand => !!v && typeof v === 'object' &&
  'type' in v && ['save','get','list','approve','revoke','remove'].some(op => v.type === 'mcp.connection.' + op);
export function validateMcpConnectionCommand(c: McpConnectionCommand) {
  if (c.type === 'mcp.connection.list') { exact(c, ['type']); return; }
  if (c.type === 'mcp.connection.get') exact(c, ['type','name']);
  else { exact(c, c.type === 'mcp.connection.save' ? ['type','setting','idempotencyKey'] : ['type','name','idempotencyKey']); text(c.idempotencyKey,8,128); }
  const name = c.type === 'mcp.connection.save' ? c.setting?.name : c.name;
  text(name,1,128); if (!/^[A-Za-z0-9_-]+$/.test(name)) reject('storage_invalid_command');
  if (c.type !== 'mcp.connection.save') return;
  const s = c.setting;
  exact(s,['name','connected','endpoint','issuer','endpointRevision','credentialRef','credentialRevision','configurationRevision','schemas','privateNetwork','lifetimeMs','maxBytes','retryBudget']);
  for (const value of [s.endpoint,s.issuer]) {
    text(value,1,2048);
    let url: URL; try { url = new URL(value); } catch { reject('mcp_endpoint_invalid'); }
    if (!['http:','https:'].includes(url.protocol) || url.username || url.password || url.hash || url.search) reject('mcp_endpoint_invalid');
  }
  text(s.credentialRef,1,256);
  [s.endpointRevision,s.credentialRevision,s.configurationRevision].forEach(v => integer(v,1));
  integer(s.lifetimeMs,1,300000); integer(s.maxBytes,1,100*1024*1024); integer(s.retryBudget,0,100);
  if (typeof s.connected !== 'boolean' || typeof s.privateNetwork !== 'boolean' || !s.schemas || typeof s.schemas !== 'object' || Array.isArray(s.schemas)) reject('storage_invalid_command');
  for (const [name,hash] of Object.entries(s.schemas)) { text(name,1,128); text(hash,64,64); if (!/^[a-f0-9]{64}$/.test(hash)) reject('storage_invalid_command'); }
}
function read(db: DatabaseSync, name: string): McpConnection | null {
  const r = one(db,'SELECT * FROM mcp_connections WHERE name=?',name);
  return r ? { setting: { ...JSON.parse(String(r.settings_json)), endpoint: String(r.endpoint), credentialRef: String(r.credential_ref),
    endpointRevision: Number(r.endpoint_revision), credentialRevision: Number(r.credential_revision), connected: !!r.enabled },
    approved: !!r.approved, grantedEpoch: Number(r.granted_epoch) } : null;
}
export function executeMcpConnectionCommand<C extends McpConnectionCommand>(db: DatabaseSync,c:C): McpConnectionResults[C['type']] {
  validateMcpConnectionCommand(c); if (!db.isTransaction) reject('mcp_transaction_required');
  if (c.type === 'mcp.connection.list') return rows(db,'SELECT name FROM mcp_connections ORDER BY name').map(r => read(db,String(r.name))!) as McpConnectionResults[C['type']];
  if (c.type === 'mcp.connection.get') return read(db,c.name) as McpConnectionResults[C['type']];
  const hash = digest(canonical(c)), receipt = one(db,'SELECT * FROM mcp_connection_commands WHERE idempotency_key=?',c.idempotencyKey);
  if (receipt) { if (receipt.request_hash !== hash) reject('idempotency_conflict'); return JSON.parse(String(receipt.result_json)); }
  const name = c.type === 'mcp.connection.save' ? c.setting.name : c.name, old = read(db,name), now = new Date().toISOString();
  let result: unknown;
  if (c.type === 'mcp.connection.save') {
    const setting = { ...c.setting,
      endpointRevision: old ? old.setting.endpointRevision + Number(old.setting.endpoint !== c.setting.endpoint || old.setting.issuer !== c.setting.issuer) : 1,
      credentialRevision: old ? Math.max(c.setting.credentialRevision, old.setting.credentialRevision + Number(old.setting.credentialRef !== c.setting.credentialRef)) : 1,
      configurationRevision: (old?.setting.configurationRevision ?? 0) + 1 };
    db.prepare(`INSERT INTO mcp_connections VALUES(?,?,?,?,?,?,?,0,?,?,?) ON CONFLICT(name) DO UPDATE SET
      endpoint=excluded.endpoint,credential_ref=excluded.credential_ref,endpoint_revision=excluded.endpoint_revision,
      credential_revision=excluded.credential_revision,enabled=excluded.enabled,approved=0,settings_json=excluded.settings_json,updated_at=excluded.updated_at`)
      .run(name,setting.endpoint,setting.credentialRef,setting.endpointRevision,setting.credentialRevision,Number(setting.connected),old?.grantedEpoch ?? 0,canonical(setting),now,now);
    result = read(db,name);
  } else {
    if (!old) reject('mcp_server_unknown');
    if (c.type === 'mcp.connection.revoke' || c.type === 'mcp.connection.remove') {
      db.prepare('UPDATE mcp_connections SET approved=0,granted_epoch=granted_epoch+1,updated_at=? WHERE name=?').run(now,name);
    }
    if (c.type === 'mcp.connection.approve') db.prepare('UPDATE mcp_connections SET approved=1,granted_epoch=granted_epoch+1,updated_at=? WHERE name=?').run(now,name);
    result = read(db,name);
    if (c.type === 'mcp.connection.remove') { db.prepare('DELETE FROM mcp_connections WHERE name=?').run(name); result = {credentialRef:old.setting.credentialRef}; }
  }
  db.prepare('INSERT INTO mcp_connection_commands VALUES(?,?,?)').run(c.idempotencyKey,hash,canonical(result));
  return result as McpConnectionResults[C['type']];
}
