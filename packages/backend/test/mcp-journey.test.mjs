// SPDX-License-Identifier: MIT
await import('../../harness/test/owned-environment.mjs');
await import('../../harness/test/capability-patch-loader.mjs');
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mkdtemp, mkdir, readdir, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Effect, Layer, ManagedRuntime } from 'effect';
import { createMcpBroker } from '../src/domain/capabilities/mcp-broker.ts';
import { createMcp, createMcpSettings, mcpSchemaHash } from '../src/domain/capabilities/mcp.ts';
const { connect } = await import('@opencode/core/mcp/client');
const { CapabilityBoundary } = await import('@opencode/core/renulus-boundary');
const { createNativeCapabilityPlugin } = await import('../../harness/src/native-capability-plugin.ts');
const { OpenCode, AbsolutePath, Location, Agent } = await import('@opencode/sdk/effect');
const { Permission } = await import('@opencode/core/permission');
const { Config } = await import('@opencode/core/config');
const { InstructionDiscovery } = await import('@opencode/core/instruction-discovery');
const { TestLLM } = await import('@opencode/ai/testing');
const { LLMClient } = await import('@opencode/ai');
const { llmClient } = await import('@opencode/core/effect/app-node-platform');

const python = 'C:/Renulus/dev/python/Scripts/python.exe';
const sourceRoot = fileURLToPath(new URL('../../../', import.meta.url));
const run = promisify(execFile);
const turn = () => new Promise(resolve => setImmediate(resolve));
async function pending(mcp) {
  const deadline = Date.now() + 5000;
  while (!mcp.admin.pending().length && Date.now() < deadline) await turn();
  assert.equal(mcp.admin.pending().length, 1); return mcp.admin.pending()[0].id;
}
async function scan(root, sentinels) {
  for (const entry of await readdir(root, { withFileTypes: true })) {
    const target = path.join(root, entry.name);
    if (entry.isDirectory()) await scan(target, sentinels);
    else if (entry.isFile()) {
      const bytes = await readFile(target);
      for (const token of sentinels) assert.equal(bytes.includes(Buffer.from(token)), false, `credential leak: ${target}`);
    }
  }
}

test('native MCP → authenticated Python broker: streams, approvals, refresh, revoke and termination', { timeout: 45_000 }, async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'renulus-mcp-journey-'));
  await mkdir(path.join(root, 'state'));
  const OLD = 'MCP_OLD_ACCESS_SENTINEL', REFRESH = 'MCP_REFRESH_SENTINEL', fresh = n => `MCP_NEW_ACCESS_SENTINEL_${n}`;
  let refreshes = 0, deleted = 0, calls = 0, direct = 0, unauthorized = 0, force401 = false;
  let reconnectEntered, releaseReconnect;
  const reconnect = new Promise(resolve => { reconnectEntered = resolve; });
  let stall = false;
  const seen = [], frames = [];
  const server = createServer(async (req, res) => {
    const body = Buffer.concat(await Array.fromAsync(req));
    const base = `http://127.0.0.1:${server.address().port}`;
    seen.push([req.method, req.url]);
    if (req.url === '/token') {
      assert.ok(body.toString().includes(`refresh_token=${REFRESH}`)); refreshes++;
      res.writeHead(200, { 'content-type': 'application/json' });
      res.end(JSON.stringify({ access_token: fresh(refreshes), token_type: 'Bearer', expires_in: 3600 })); return;
    }
    if (req.url === '/.well-known/oauth-protected-resource' || req.url === '/.well-known/oauth-authorization-server') {
      res.writeHead(200, { 'content-type': 'application/json' });
      res.end(JSON.stringify(req.url.endsWith('oauth-protected-resource') ? { authorization_servers: [base] } : { token_endpoint: base + '/token' })); return;
    }
    if (force401 || req.headers.authorization !== 'Bearer ' + fresh(refreshes)) {
      force401 = false; unauthorized++; res.writeHead(401, { 'content-type': 'application/json' }); res.end('{}'); return;
    }
    if (req.method === 'DELETE') { deleted++; res.writeHead(204); res.end(); return; }
    if (req.method === 'GET') { res.writeHead(405); res.end(); return; }
    const message = JSON.parse(body.toString());
    if (!('id' in message)) { res.writeHead(202); res.end(); return; }
    if (stall && message.method === 'initialize') {
      reconnectEntered(); await new Promise(resolve => { releaseReconnect = resolve; });
      if (res.destroyed) return;
    }
    let result;
    if (message.method === 'initialize') result = { protocolVersion: '2025-03-26', capabilities: { tools: {}, resources: {} }, serverInfo: { name: 'synthetic', version: '1' } };
    else if (message.method === 'tools/list') result = { tools: [{ name: 'echo', description: 'Synthetic', inputSchema: { type: 'object', properties: {} } }] };
    else if (message.method === 'resources/list') result = { resources: [] };
    else if (message.method === 'tools/call') { calls++; result = { content: [{ type: 'text', text: 'streamed synthetic reply' }] }; }
    else { res.writeHead(400); res.end(); return; }
    res.writeHead(200, { 'content-type': 'text/event-stream', 'mcp-session-id': 'session-synthetic' });
    const data = `event: message\ndata: ${JSON.stringify({ jsonrpc: '2.0', id: message.id, result })}\n\n`;
    res.write(data.slice(0, 19)); await turn(); res.end(data.slice(19));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const issuer = `http://127.0.0.1:${server.address().port}`, endpoint = issuer + '/mcp';
  await run(python, ['-B', '-c', `import sys,time\nfrom pathlib import Path\nfrom renulus.workers.mcp_tokens import McpCredentials\np=Path(sys.argv[1]); c=McpCredentials(p,p/'state')\nc.put('server-ref',revision=1,resource=sys.argv[2],client_id='synthetic',access_token='${OLD}',refresh_token='${REFRESH}',expires_at=time.time()-5,token_endpoint=sys.argv[3]+'/token')`, root, endpoint, issuer],
    { cwd: sourceRoot, windowsHide: true, env: { ...process.env, PYTHONPATH: path.join(sourceRoot, 'runtime') } });
  const descriptor = { server: 'synthetic', name: 'echo', inputSchema: { type: 'object', properties: {} } };
  const setting = { name: 'synthetic', connected: true, endpoint, issuer, endpointRevision: 1, credentialRef: 'server-ref',
    credentialRevision: 1, configurationRevision: 1, schemas: { echo: mcpSchemaHash(descriptor) }, privateNetwork: true,
    lifetimeMs: 60_000, maxBytes: 2 * 1024 * 1024, retryBudget: 40 };
  const settings = createMcpSettings([setting]);
  const realBroker = createMcpBroker({ python, sourceRoot, profile: root, state: path.join(root, 'state') });
  let authority;
  const broker = { ...realBroker,
    current(check) { authority = check; realBroker.current(check); },
    request(op, input) { frames.push({ op, ...input }); return realBroker.request(op, input); },
  };
  let applicationOpen = true;
  const mcp = createMcp({ settings, broker, open: () => applicationOpen });
  const envelope = { run_id: 'run', root_id: 'root', session_id: 'session', call_id: 'call', configuration: 'configuration',
    grant_epoch: 0, fence: {}, retention: 'saved', mode: 'doctor', depth: 0 };
  const capabilities = await createNativeCapabilityPlugin({ ...mcp.port, approveMcpTool: mcp.approveMcpTool,
    authority: { invoke: async (_e, _a, _i, execute) => execute({}, new AbortController().signal), close: async () => {}, status: () => ({}) },
    resolve: async native => ({ ...envelope, call_id: String(native.id) }), localCurrent: () => applicationOpen,
    commands: { permission: mcp.permission }, skills: [],
    children: { resolveParent() { throw new Error('unexpected_child'); }, request: () => Effect.die('unexpected_child'),
      localCurrent: () => false, bindInput() { throw new Error('unexpected_child'); } } });
  let permission;
  const nativeConfig = JSON.stringify({ model: 'synthetic/unused', compaction: { auto: false },
    providers: { synthetic: { package: '@opencode/ai/providers/openai-compatible',
      settings: { baseURL: 'https://synthetic.invalid/v1', apiKey: 'synthetic-unused' },
      models: { unused: { limit: { context: 128000, output: 4096 } } } } },
    agents: { doctor: { mode: 'primary', permissions: [{ action: '*', resource: '*', effect: 'deny' }] }, title: { disabled: true } } });
  const modelRuntime = ManagedRuntime.make(TestLLM.testLayer());
  const modelClient = await modelRuntime.runPromise(TestLLM.Test);
  const runtime = ManagedRuntime.make(Layer.effect(OpenCode.Service, OpenCode.create({
    app: { name: 'renulus-mcp-permission-test', version: 's12' }, database: { path: path.join(root, 'native.sqlite') },
    plugins: [capabilities.capture, ...capabilities.plugins, { id: 'permission-fixture', effect: ctx => ctx.command.transform(editor =>
      editor.add({ name: 'fixture_permission', execute: () => Effect.gen(function* () { permission = yield* Permission.Service; }) })) }],
    config: { directory: path.join(root, 'config'), project: false, content: nativeConfig },
    models: { fetch: false, snapshot: false }, fs: { filewatcher: false, fff: false }, events: { persist: false },
  }, { overrides: [...capabilities.overrides,
    Config.node.replace(Config.configured({ project: false, global: false, content: nativeConfig })),
    InstructionDiscovery.node.replace(InstructionDiscovery.configured({ project: false, global: false })),
    llmClient.replace(Layer.succeed(LLMClient.Service, modelClient)),
  ] })));
  const stockFetch = globalThis.fetch;
  globalThis.fetch = input => {
    if (new URL(input instanceof Request ? input.url : String(input)).origin === issuer) direct++;
    throw new Error('direct native fetch forbidden');
  };
  const config = { type: 'remote', url: endpoint, oauth: false, codemode: false, timeout: { startup: 5000, catalog: 5000, execution: 5000 } };
  try {
    const sdk = await runtime.runPromise(OpenCode.Service);
    const session = await runtime.runPromise(sdk.sessions.create({ title: 'Synthetic MCP permission', agent: Agent.ID.make('doctor'),
      location: Location.Ref.make({ directory: AbsolutePath.make(root) }) }));
    envelope.session_id = session.id;
    await runtime.runPromise(sdk.sessions.command({ sessionID: session.id, name: 'fixture_permission', text: '' }));
    await assert.rejects(Effect.runPromise(permission.assert({ sessionID: session.id, agent: Agent.ID.make('doctor'),
      action: 'synthetic_echo', resources: ['*'] })), /denied|blocked/i);
    // Real native connect, catalogue and tool client inside the patched capabilities scope.
    await Effect.runPromise(capabilities.provide(Effect.scoped(Effect.gen(function* () {
      const client = yield* connect('synthetic', config, root);
      assert.equal(refreshes, 1, 'expired token refreshed in Python');
      const tools = yield* client.tools(); assert.equal(tools[0].name, 'echo');
      force401 = true;
      yield* client.resources();
      assert.equal(refreshes, 2); assert.equal(unauthorized, 1);
      assert.equal(frames.filter(f => f.op === 'credential.refresh').length, 1);
      const boundary = yield* CapabilityBoundary;
      const native = { sessionID: session.id, messageID: 'message', id: 'call', agent: 'doctor' };
      const signal = new AbortController().signal;
      const call = Effect.runPromise(boundary.mcpTool(descriptor, {}, native, Effect.gen(function* () {
        yield* permission.assert({ sessionID: session.id, agent: Agent.ID.make('doctor'), action: 'synthetic_echo', resources: ['*'],
          source: { type: 'tool', messageID: 'message', id: 'call' } });
        return yield* client.callTool({ name: 'echo', args: {} });
      })));
      const id = yield* Effect.promise(() => pending(mcp));
      yield* Effect.promise(() => mcp.admin.answer(id, 'once'));
      assert.equal((yield* Effect.promise(() => call)).content[0].text, 'streamed synthetic reply');
      assert.equal(calls, 1);
      assert.equal((yield* Effect.promise(() => mcp.permission({ action: 'synthetic_echo', source: { id: 'call' } }, envelope, signal))).metadata.approved, false);
      const changed = { ...descriptor, inputSchema: { type: 'object', properties: { changed: { type: 'string' } } } };
      yield* Effect.promise(() => assert.rejects(mcp.approveMcpTool(changed, { ...envelope, call_id: 'schema' }, signal), /schema_changed/));
      const awaiting = mcp.approveMcpTool(descriptor, { ...envelope, call_id: 'revision' }, signal);
      const refusedApproval = assert.rejects(awaiting, /stale/);
      const revisionId = yield* Effect.promise(() => pending(mcp));
      settings.put({ ...setting, endpointRevision: 2 });
      yield* Effect.promise(() => assert.rejects(mcp.admin.answer(revisionId, 'always'), /stale/));
      yield* Effect.promise(() => refusedApproval); settings.put(setting);
    }))));
    assert.equal(deleted, 1, 'native scope finalizer sent exactly one cleanup DELETE');
    assert.equal(frames.filter(f => f.op === 'cleanup').length, 1);
    const first = frames.find(f => f.op === 'connection.open').conn;
    assert.equal(await authority(first, first + ':cleanup', 0), false, 'cleanup permit consumed');

    // Revocation while a new native initialize is waiting on the synthetic server.
    const held = mcp.approveMcpTool(descriptor, { ...envelope, call_id: 'pending-always' }, new AbortController().signal);
    const heldRejected = assert.rejects(held, /stale/);
    const heldId = await pending(mcp);
    stall = true;
    const connecting = Effect.runPromise(capabilities.provide(Effect.scoped(connect('synthetic', config, root))));
    const reconnectRejected = assert.rejects(connecting, /stale|closed|connect|cancel|interrupted/i);
    await reconnect;
    await mcp.admin.revoke('synthetic');
    releaseReconnect();
    await assert.rejects(mcp.admin.answer(heldId, 'always'), /stale/); await heldRejected; await reconnectRejected;
    await assert.rejects(mcp.port.mcp('synthetic', config), /stale/);
    for (const frame of frames.filter(f => f.op === 'connection.open')) assert.equal(await authority(frame.conn, frame.conn, 0), false);
    assert.ok(mcp.admin.uncertainty().some(item => item.reason === 'revoked_connection'));
    applicationOpen = false;
    await mcp.admin.close();
    assert.equal(direct, 0);
    assert.equal(deleted, 1, 'reconnect without a session cannot send termination');
    assert.ok(seen.some(([method]) => method === 'DELETE'));
    const serialized = JSON.stringify(frames);
    for (const secret of [OLD, REFRESH, fresh(1), fresh(2)]) assert.equal(serialized.includes(secret), false);
    await scan(root, [OLD, REFRESH, fresh(1), fresh(2)]);
    await scan(process.env.XDG_DATA_HOME, [OLD, REFRESH, fresh(1), fresh(2)]);
    await scan(process.env.XDG_STATE_HOME, [OLD, REFRESH, fresh(1), fresh(2)]);
  } finally {
    globalThis.fetch = stockFetch;
    releaseReconnect?.(); await runtime.dispose(); await modelRuntime.dispose(); await mcp.admin.close(); await capabilities.close();
    server.closeAllConnections(); await new Promise(resolve => server.close(resolve));
  }
});
