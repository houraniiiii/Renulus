// SPDX-License-Identifier: MIT
import { createHash, randomUUID } from 'node:crypto';
import { Effect } from 'effect';
import type { Plugin } from '@opencode/plugin/effect/plugin';
import type { Tool } from '@opencode/schema/tool';
import type { NativeCapabilityPorts } from '../../../../harness/src/capability-authority.ts';
import type { CapabilityEnvelope } from './contracts.ts';
import type { McpBrokerPort } from './mcp-broker.ts';
import type { McpConnection } from './mcp-commands.ts';
import type { StorageClient } from '../../storage/index.ts';

export interface McpSetting {
  name: string; connected: boolean; endpoint: string; issuer: string;
  endpointRevision: number; credentialRef: string; credentialRevision: number; configurationRevision: number;
  schemas: Readonly<Record<string, string>>;
  privateNetwork: boolean; lifetimeMs: number; maxBytes: number; retryBudget: number;
}
export interface McpSettingsPort {
  get(name: string): McpSetting | undefined;
  list(): readonly McpSetting[];
  grantEpoch(name: string, advance?: true): number;
}
export function createMcpSettings(initial: readonly McpSetting[] = []) {
  const settings = new Map(initial.map(item => [item.name, structuredClone(item)])), epochs = new Map<string, number>();
  return {
    get: (name: string) => { const item = settings.get(name); return item && structuredClone(item); },
    list: () => [...settings.values()].map(item => structuredClone(item)),
    grantEpoch(name: string, advance?: true) { const epoch = (epochs.get(name) ?? 0) + (advance ? 1 : 0); epochs.set(name, epoch); return epoch; },
    put(item: McpSetting) { settings.set(item.name, structuredClone(item)); },
  } satisfies McpSettingsPort & { put(item: McpSetting): void };
}
/** Canonical `mcp_connections` behind the same port; the cache is written through only after storage commits. */
export async function createStoredMcpSettings(storage: Pick<StorageClient, 'command'>) {
  const items = new Map<string, McpConnection>(), epochs = new Map<string, number>();
  const sync = (item: McpConnection) => {
    items.set(item.setting.name, item); epochs.set(item.setting.name, Math.max(epochs.get(item.setting.name) ?? 0, item.grantedEpoch)); return item;
  };
  const visible = ({ setting, approved }: McpConnection) => structuredClone({ ...setting, connected: setting.connected && approved });
  for (const item of await storage.command({ type: 'mcp.connection.list' })) sync(item);
  return {
    get: (name: string) => { const item = items.get(name); return item && visible(item); },
    list: () => [...items.values()].map(visible),
    grantEpoch(name: string, advance?: true) { const epoch = (epochs.get(name) ?? 0) + (advance ? 1 : 0); epochs.set(name, epoch); return epoch; },
    connection: (name: string) => items.get(name),
    connections: () => [...items.values()],
    async save(setting: McpSetting, idempotencyKey: string) { return sync(await storage.command({ type: 'mcp.connection.save', setting, idempotencyKey })); },
    async approve(name: string, idempotencyKey: string) { return sync(await storage.command({ type: 'mcp.connection.approve', name, idempotencyKey })); },
    async revoke(name: string, idempotencyKey: string) { return sync(await storage.command({ type: 'mcp.connection.revoke', name, idempotencyKey })); },
    async remove(name: string, idempotencyKey: string) { const result = await storage.command({ type: 'mcp.connection.remove', name, idempotencyKey }); items.delete(name); return result; },
  };
}
export type StoredMcpSettings = Awaited<ReturnType<typeof createStoredMcpSettings>>;
type Descriptor = Parameters<NonNullable<NativeCapabilityPorts['approveMcpTool']>>[0];
export const mcpSchemaHash = (descriptor: Pick<Descriptor, 'inputSchema' | 'outputSchema'>) =>
  createHash('sha256').update(JSON.stringify([descriptor.inputSchema ?? null, descriptor.outputSchema ?? null])).digest('hex');
const refused = (code = 'mcp_authority_stale'): never => { throw new Error(code); };
const namespace = (name: string) => name.replace(/[^a-zA-Z0-9_-]/g, '_');
const endpointOf = (url: string, private_network: boolean) => {
  const value = new URL(url);
  if (!['http:', 'https:'].includes(value.protocol) || value.username || value.password || value.hash) refused('mcp_endpoint_invalid');
  return { host: value.hostname, port: Number(value.port || (value.protocol === 'https:' ? 443 : 80)), private_network };
};

export function createMcp(options: { settings: McpSettingsPort; broker: McpBrokerPort; developer?: { workspace: string };
  open(envelope?: CapabilityEnvelope): boolean | Promise<boolean> }) {
  const { settings, broker } = options;
  const connections = new Map<string, { name: string; fingerprint: string; expires: number; bytes: number; maxBytes: number;
    closed: boolean; cleanupActive: boolean; cleanupExpires: number; cleanupBytes: number; close(revoked?: boolean): Promise<void> }>();
  const pending = new Map<string, { id: string; server: string; tool: string; fingerprint: string; settle(error?: Error): void; current(): Promise<void> }>();
  const approved = new Map<string, { fingerprint: string; action: string; envelope: CapabilityEnvelope; server: string }>();
  const always = new Set<string>();
  const revoked = new Set<string>(), invalidCalls = new Set<string>();
  const uncertain: { connection?: string; call?: string; reason: string }[] = [];
  const fingerprint = (item: McpSetting) => JSON.stringify([item, settings.grantEpoch(item.name)]);
  async function current(name: string, expected: string, envelope?: CapabilityEnvelope) {
    if (!await options.open(envelope)) refused();
    const item = settings.get(name);
    if (revoked.has(name) || !item?.connected || fingerprint(item) !== expected) refused();
    return item!;
  }
  const key = (envelope: CapabilityEnvelope) => JSON.stringify([envelope.session_id, envelope.call_id]);
  broker.current(async (id, lease, bytes) => {
    const conn = connections.get(id);
    if (!conn || !Number.isSafeInteger(bytes) || bytes < 0) return false;
    if (lease === id + ':cleanup') {
      if (!conn.cleanupActive || Date.now() >= conn.cleanupExpires || conn.cleanupBytes + bytes > 65536) return false;
      conn.cleanupBytes += bytes; return true;
    }
    if (lease !== id || conn.closed || Date.now() >= conn.expires || conn.bytes + bytes > conn.maxBytes) return false;
    try { await current(conn.name, conn.fingerprint); } catch { return false; }
    // Revocation can occur while the async application check was in flight.
    if (conn.closed) return false;
    conn.bytes += bytes; return true;
  });
  const port = {
    async mcp(name: string, configuration: unknown) {
      const setting = settings.get(name) ?? refused('mcp_server_unknown');
      const config = configuration as { type?: string; url?: string };
      if (config.url !== setting.endpoint) refused('mcp_endpoint_mismatch');
      const expected = fingerprint(setting);
      await current(name, expected);
      const endpoint = endpointOf(setting.endpoint, setting.privateNetwork), issuer = endpointOf(setting.issuer, setting.privateNetwork);
      if (!Number.isSafeInteger(setting.retryBudget) || setting.retryBudget < 0 || setting.lifetimeMs <= 0 || setting.lifetimeMs > 300_000 || setting.maxBytes <= 0) refused('mcp_budget_invalid');
      const conn = randomUUID(), expires = Date.now() + setting.lifetimeMs;
      let session: string | undefined, cleanupSent = false, attempts = 0, closure: Promise<void> | undefined;
      const binding = { conn, credential_ref: setting.credentialRef, credential_revision: setting.credentialRevision };
      const state = { name, fingerprint: expected, expires, bytes: 0, maxBytes: setting.maxBytes, closed: false,
        cleanupActive: false, cleanupExpires: 0, cleanupBytes: 0, close: (revoked?: boolean) => close(revoked) };
      connections.set(conn, state);
      async function admit() {
        if (state.closed || Date.now() >= expires) refused();
        await current(name, expected);
        if (state.closed) refused();
      }
      async function cleanup() {
        if (!session || cleanupSent) return;
        cleanupSent = true; state.cleanupActive = true; state.cleanupExpires = Date.now() + 10_000;
        try {
          const result = await broker.request<{ status: number }>('cleanup', { ...binding, endpoint, url: setting.endpoint, session_id: session });
          if (result.status < 200 || result.status >= 300) throw new Error('mcp_cleanup_unknown');
        } catch { uncertain.push({ connection: conn, reason: 'cleanup_unknown' }); }
        finally { state.cleanupActive = false; }
      }
      function close(revoked = false) {
        return closure ??= (async () => {
          state.closed = true;
          if (!revoked) await cleanup();
          try { await broker.request('connection.close', { conn }); }
          catch (error) { uncertain.push({ connection: conn, reason: 'connection_close_unknown' }); throw error; }
          finally { if (revoked) await cleanup(); }
        })();
      }
      try {
        await broker.request('connection.open', { conn, endpoints: [endpoint, issuer], expires_at_ms: expires, max_bytes: setting.maxBytes });
        await admit();
      } catch (error) { await close(); throw error; }
      return {
        async fetch(input: string | URL | Request, init?: RequestInit): Promise<Response> {
          const request = new Request(input, init);
          if (request.url !== setting.endpoint) refused('mcp_endpoint_mismatch');
          if (request.method === 'DELETE') { await cleanup(); return new Response(null, { status: 204 }); }
          const headers: Record<string, string> = {};
          for (const [header, value] of request.headers) {
            if (!['accept', 'content-type', 'mcp-session-id', 'mcp-protocol-version', 'last-event-id'].includes(header)) refused('mcp_header_refused');
            headers[header] = value;
          }
          const body = Buffer.from(await request.arrayBuffer());
          const payload = { ...binding, url: request.url, method: request.method, headers,
            body_base64: body.toString('base64'), body_sha256: createHash('sha256').update(body).digest('hex') };
          const abort = () => { void close().catch(() => {}); };
          request.signal.throwIfAborted(); request.signal.addEventListener('abort', abort, { once: true });
          let finished = false;
          const detach = () => { if (!finished) { finished = true; request.signal.removeEventListener('abort', abort); } };
          try {
            let reply!: { stream: string; status: number; headers: Record<string, string> };
            for (let retry = 0; retry < 2; retry++) {
              await admit(); request.signal.throwIfAborted();
              if (++attempts > setting.retryBudget + 1) refused('mcp_retry_budget');
              reply = await broker.request('http', payload);
              if (reply.headers['mcp-session-id']) {
                if (session && session !== reply.headers['mcp-session-id']) refused('mcp_session_changed');
                session = reply.headers['mcp-session-id'];
              }
              await admit();
              if (reply.status >= 300 && reply.status < 400) { await broker.request('http.close', { conn, stream: reply.stream }); refused('mcp_redirect_refused'); }
              if (reply.status !== 401 || retry === 1) break;
              await broker.request('http.close', { conn, stream: reply.stream });
              await admit();
              await broker.request('credential.refresh', { conn, ref: setting.credentialRef, revision: setting.credentialRevision });
            }
            const stream = reply.stream;
            const drop = async () => { detach(); if (!state.closed) await broker.request('http.close', { conn, stream }); };
            if ([204, 205, 304].includes(reply.status)) { await drop(); return new Response(null, { status: reply.status, headers: reply.headers }); }
            return new Response(new ReadableStream<Uint8Array>({
              async pull(controller) {
                try {
                  await admit(); request.signal.throwIfAborted();
                  const chunk = await broker.request<{ data_base64: string | null }>('http.read', { conn, stream });
                  await admit(); request.signal.throwIfAborted();
                  if (chunk.data_base64 === null) { await drop(); controller.close(); }
                  else controller.enqueue(Buffer.from(chunk.data_base64, 'base64'));
                } catch (error) { controller.error(error); await drop().catch(() => {}); }
              }, cancel: drop,
            }, { highWaterMark: 0 }), { status: reply.status, headers: reply.headers });
          } catch (error) { detach(); throw error; }
        },
        localTransport(input: unknown) {
          if (!options.developer) refused('mcp_local_developer_only');
          const local = input as { command: string; args: string[]; cwd: string };
          let server: string | undefined, stopped = false;
          const transport: { onmessage?: (message: unknown) => void; onerror?: (error: Error) => void; onclose?: () => void;
            start(): Promise<void>; send(message: unknown): Promise<void>; close(): Promise<void> } = {
            async start() {
              await admit();
              const opened = await broker.request<{ server: string }>('stdio.open', { conn, argv: [local.command, ...local.args], cwd: local.cwd });
              server = opened.server;
              void (async () => {
                while (!stopped) {
                  await admit();
                  const frame = await broker.request<{ frame_base64: string | null }>('stdio.read', { conn, server });
                  await admit();
                  if (frame.frame_base64 === null) { stopped = true; transport.onclose?.(); return; }
                  transport.onmessage?.(JSON.parse(Buffer.from(frame.frame_base64, 'base64').toString('utf8')));
                }
              })().catch(error => { if (!stopped) transport.onerror?.(error); });
            },
            async send(message) { await admit(); if (!server || stopped) refused('mcp_stdio_closed');
              await broker.request('stdio.write', { conn, server, frame_base64: Buffer.from(JSON.stringify(message)).toString('base64') }); },
            async close() { if (stopped) return; stopped = true;
              if (server && !state.closed) await broker.request('stdio.close', { conn, server }); transport.onclose?.(); },
          };
          return Effect.succeed(transport);
        }, close,
      };
    },
  } satisfies Pick<NativeCapabilityPorts, 'mcp'>;
  const approveMcpTool: NonNullable<NativeCapabilityPorts['approveMcpTool']> = async (descriptor, envelope, signal) => {
    signal.throwIfAborted();
    const setting = settings.get(descriptor.server) ?? refused('mcp_server_unknown');
    const expected = fingerprint(setting), schema = mcpSchemaHash(descriptor);
    if (setting.schemas[descriptor.name] !== schema) refused('mcp_schema_changed');
    await current(descriptor.server, expected, envelope);
    const id = key(envelope), action = `${namespace(descriptor.server)}_${namespace(descriptor.name)}`;
    if (invalidCalls.has(id)) refused();
    const existing = approved.get(id);
    if (existing) {
      if (existing.fingerprint !== expected || existing.action !== action) refused();
      approved.delete(id); return;
    }
    if (!always.has(expected + action)) {
      if (pending.has(id)) refused('mcp_approval_pending');
      await new Promise<void>((resolve, reject) => {
        const cancel = () => settle(new Error('mcp_approval_cancelled'));
        const settle = (error?: Error) => { pending.delete(id); signal.removeEventListener('abort', cancel); error ? reject(error) : resolve(); };
        pending.set(id, { id, server: descriptor.server, tool: descriptor.name, fingerprint: expected, settle,
          current: async () => { signal.throwIfAborted(); await current(descriptor.server, expected, envelope); } });
        signal.addEventListener('abort', cancel, { once: true }); if (signal.aborted) cancel();
      });
    }
    await current(descriptor.server, expected, envelope); signal.throwIfAborted();
    approved.set(id, { fingerprint: expected, action, envelope, server: descriptor.server });
  };
  const permission = async (input: unknown, envelope: CapabilityEnvelope, signal: AbortSignal): Promise<Tool.Result> => {
    signal.throwIfAborted();
    const call = approved.get(key(envelope)), value = input as { action?: string; source?: { id?: string } };
    let allowed = false;
    if (call && value.source?.id === envelope.call_id && JSON.stringify(call.envelope) === JSON.stringify(envelope) &&
      (value.action === call.action || ['opencode_list_mcp_resources', 'opencode_read_mcp_resource'].includes(value.action ?? ''))) {
      await current(call.server, call.fingerprint, envelope); allowed = true;
    }
    return { content: '', metadata: { approved: allowed } };
  };
  const plugin: Plugin = { id: 'renulus-mcp', effect: ctx => ctx.mcp.transform(editor => {
    for (const [name] of editor.list()) editor.remove(name);
    for (const item of settings.list()) if (item.connected) editor.set(item.name, { type: 'remote', url: item.endpoint, oauth: false, codemode: false });
  }) };
  const admin = {
    pending: () => [...pending.values()].map(({ id, server, tool }) => ({ id, server, tool })),
    async answer(id: string, answer: 'once' | 'always' | 'deny') {
      const item = pending.get(id) ?? refused('mcp_approval_stale');
      try { await item.current(); }
      catch (error) { item.settle(new Error('mcp_approval_stale')); throw error; }
      if (fingerprint(settings.get(item.server) ?? refused()) !== item.fingerprint || revoked.has(item.server)) {
        item.settle(new Error('mcp_approval_stale')); refused();
      }
      if (answer === 'deny') { item.settle(new Error('mcp_approval_denied')); return; }
      if (answer === 'always') always.add(item.fingerprint + `${namespace(item.server)}_${namespace(item.tool)}`);
      item.settle();
    },
    /** Only an explicit owner approval lifts a revocation. */
    regrant: (name: string) => { revoked.delete(name); },
    async revoke(name: string) {
      settings.grantEpoch(name, true);
      revoked.add(name);
      for (const [id, call] of approved) if (call.server === name) { approved.delete(id); invalidCalls.add(id); uncertain.push({ call: id, reason: 'revoked_effect_unknown' }); }
      for (const [id, conn] of connections) if (conn.name === name && !conn.closed) {
        uncertain.push({ reason: 'revoked_connection', connection: id });
        await conn.close(true);
      }
    },
    credential: {
      put: (input: { ref: string; revision: number; resource: string; client_id: string; access_token: string;
        refresh_token?: string; expires_at: number; token_endpoint?: string }) => broker.request('credential.put', input),
      forget: (ref: string) => broker.request('credential.forget', { ref }),
    },
    uncertainty: () => [...uncertain],
    async close() {
      for (const item of pending.values()) item.settle(new Error('mcp_closed'));
      for (const conn of connections.values()) await conn.close();
      await broker.close();
    },
  };
  return { port, approveMcpTool, permission, plugin, admin };
}
export type McpBridge = ReturnType<typeof createMcp>;
