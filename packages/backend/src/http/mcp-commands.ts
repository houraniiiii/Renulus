// SPDX-License-Identifier: MIT
import type { IncomingMessage } from 'node:http';
import type { McpBridge, McpSetting, StoredMcpSettings } from '../domain/capabilities/mcp.ts';
import { exact, reject } from '../storage/contracts.ts';
import { readJsonObject } from './body.ts';
import { commandKey } from './project-commands.ts';

export interface McpCommands { settings: StoredMcpSettings; admin: Pick<McpBridge['admin'], 'revoke' | 'regrant' | 'credential'> }
const SETTING = ['connected', 'endpoint', 'issuer', 'credentialRef', 'credentialRevision', 'schemas', 'privateNetwork', 'lifetimeMs', 'maxBytes', 'retryBudget'];
/** Explicit token handoff; `refresh_token` and `token_endpoint` may be null. */
const TOKENS = ['resource', 'client_id', 'access_token', 'refresh_token', 'expires_at', 'token_endpoint'];

/** Authenticated user commands only. Approval and revocation are never reachable from a model call. */
export async function mcpCommand(request: IncomingMessage, url: URL, mcp?: McpCommands): Promise<{ status: number; value: unknown } | undefined> {
  const match = /^\/api\/v1\/mcp\/connections(?:\/([A-Za-z0-9_-]{1,128})(?:\/(approve|revoke))?)?$/.exec(url.pathname);
  if (!match) return undefined;
  if (!mcp) reject('mcp_host_unavailable');
  const { settings, admin } = mcp, [, name, action] = match, key = commandKey(request);
  if (!name) { if (request.method !== 'GET') reject('storage_invalid_command'); return { status: 200, value: settings.connections() }; }
  if (!action && request.method === 'GET') return { status: 200, value: settings.connection(name) ?? null };
  if (!action && request.method === 'PUT') {
    const body = await readJsonObject(request, 65536), { credential, ...rest } = body;
    exact(rest, SETTING);
    const saved = (await settings.save({ ...rest, name, endpointRevision: 1, configurationRevision: 1 } as McpSetting, key)).setting;
    if (credential !== undefined) {
      exact(credential, TOKENS);
      await admin.credential.put({ ref: saved.credentialRef, revision: saved.credentialRevision, ...credential } as Parameters<typeof admin.credential.put>[0]);
    }
    return { status: 200, value: settings.connection(name) };
  }
  if (!action && request.method === 'DELETE') {
    const { credentialRef } = await settings.remove(name, key);
    await admin.revoke(name); await admin.credential.forget(credentialRef);
    return { status: 200, value: { removed: name } };
  }
  if (action === 'approve' && request.method === 'POST') {
    exact(await readJsonObject(request, 4096), []);
    const value = await settings.approve(name, key); admin.regrant(name); return { status: 200, value };
  }
  if (action === 'revoke' && request.method === 'POST') {
    exact(await readJsonObject(request, 4096), []);
    const value = await settings.revoke(name, key); await admin.revoke(name); return { status: 200, value };
  }
  reject('storage_invalid_command');
}
