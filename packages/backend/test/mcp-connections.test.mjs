// SPDX-License-Identifier: MIT
await import('../../harness/test/owned-environment.mjs');
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { spawnSync } from 'node:child_process';
import { Readable } from 'node:stream';
import { mkdtempSync, writeFileSync, readdirSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { openIsolatedStorage, previewStorage, loadMigrationInventory, MARKER, SELECTOR } from '../src/storage/index.ts';
import { createMcpBroker } from '../src/domain/capabilities/mcp-broker.ts';
import { createMcp, createStoredMcpSettings, mcpSchemaHash } from '../src/domain/capabilities/mcp.ts';
import { mcpCommand } from '../src/http/mcp-commands.ts';

const python = process.env.RENULUS_BACKEND_TEST_PYTHON || 'C:/Renulus/dev/python/Scripts/python.exe';
const repository = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const TOKEN = 'MCP_CONNECTION_TOKEN_SENTINEL';
const turn = () => new Promise(resolve => setImmediate(resolve));
function scan(root) {
  for (const entry of readdirSync(root, { withFileTypes: true })) {
    const target = join(root, entry.name);
    if (entry.isDirectory()) scan(target);
    else assert.equal(readFileSync(target).includes(Buffer.from(TOKEN)), false, `credential leak: ${target}`);
  }
}

test('MCP connections: save → approve → call → edit/revoke refuse → reopen persists → remove forgets credential', { timeout: 90_000 }, async () => {
  const profile = mkdtempSync(join(resolve(tmpdir()), 'renulus-mcp-connections-'));
  const prepared = spawnSync(python, ['-I', '-B', '-X', 'utf8', '-c', `
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'runtime'))
from renulus.server import create_app
print(json.dumps({'database':str(create_app(sys.argv[2]).state.services.paths.database)}))
`, repository, profile], { encoding: 'utf8', windowsHide: true, timeout: 45000,
    env: { SystemRoot: process.env.SystemRoot, WINDIR: process.env.WINDIR, TEMP: profile, TMP: profile, PATH: dirname(python) } });
  assert.equal(prepared.status, 0, prepared.stderr);
  const databasePath = JSON.parse(prepared.stdout).database, migrations = loadMigrationInventory(repository);
  const preview = await previewStorage({ databasePath, migrations });
  const selection = { contract: 'renulus-storage-selector/1', isolation: 'synthetic', profileId: 'mcp_connections_synthetic', generation: 1,
    authorityEpoch: 1, writer: 'ts', state: 'active', ownerId: 'mcp_connections_owner', database: 'state/renulus.sqlite3' };
  writeFileSync(join(profile, MARKER), JSON.stringify({ contract: 'renulus-synthetic-storage/1', profileId: selection.profileId }));
  writeFileSync(join(profile, SELECTOR), JSON.stringify(selection));
  const open = () => openIsolatedStorage({ profileRoot: profile, selection, migrations, expectedSchemaHash: preview.schemaHash });

  let calls = 0;
  const server = createServer(async (request, response) => {
    const body = Buffer.concat(await Array.fromAsync(request));
    if (request.headers.authorization !== 'Bearer ' + TOKEN) { response.writeHead(401); response.end('{}'); return; }
    calls++; response.writeHead(200, { 'content-type': 'application/json' });
    response.end(JSON.stringify({ jsonrpc: '2.0', id: JSON.parse(body).id, result: { content: [{ type: 'text', text: 'synthetic reply' }] } }));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}`, endpoint = base + '/mcp';
  const descriptor = { server: 'synthetic', name: 'echo', inputSchema: { type: 'object', properties: {} } };
  const config = url => ({ type: 'remote', url });
  const envelope = { run_id: 'run', root_id: 'root', session_id: 'session', call_id: 'call', configuration: 'configuration',
    grant_epoch: 0, fence: {}, retention: 'saved', mode: 'doctor', depth: 0 };
  const signal = new AbortController().signal;
  const setting = url => ({ connected: true, endpoint: url, issuer: base, credentialRef: 'synthetic-ref', credentialRevision: 1,
    schemas: { echo: mcpSchemaHash(descriptor) }, privateNetwork: true, lifetimeMs: 60_000, maxBytes: 1024 * 1024, retryBudget: 5 });
  const credential = { resource: endpoint, client_id: 'synthetic', access_token: TOKEN, refresh_token: null, expires_at: Date.now() / 1000 + 3600, token_endpoint: null };
  const command = (method, path, body = {}) => mcpCommand(Object.assign(Readable.from([Buffer.from(JSON.stringify(body))]), { method, headers: {} }),
    new URL('http://localhost/api/v1/mcp/connections' + path), mcps);
  const call = async connection => {
    const reply = await connection.fetch(endpoint, { method: 'POST', headers: { 'content-type': 'application/json', accept: 'application/json' },
      body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call' }) });
    return (await reply.json()).result.content[0].text;
  };

  let storage = await open(), settings = await createStoredMcpSettings(storage), mcp, mcps;
  const bridge = () => createMcp({ settings, open: async () => !(await storage.command({ type: 'dispatch.snapshot' })).revoked.includes('renulus.mcp'),
    broker: createMcpBroker({ python, sourceRoot: repository, profile, state: join(profile, 'state') }) });
  try {
    mcp = bridge(); mcps = { settings, admin: mcp.admin };
    await assert.rejects(command('PUT', '/synthetic', { ...setting(endpoint), approved: true }), /storage_invalid_command/);
    assert.equal((await command('PUT', '/synthetic', { ...setting(endpoint), credential })).value.approved, false);
    await assert.rejects(mcp.port.mcp('synthetic', config(endpoint)), /stale/);

    assert.equal((await command('POST', '/synthetic/approve')).value.approved, true);
    const connection = await mcp.port.mcp('synthetic', config(endpoint));
    assert.equal(await call(connection), 'synthetic reply'); assert.equal(calls, 1);
    await connection.close();

    const approving = mcp.approveMcpTool(descriptor, envelope, signal);
    while (!mcp.admin.pending().length) await turn();
    await mcp.admin.answer(mcp.admin.pending()[0].id, 'once'); await approving;
    assert.equal((await mcp.permission({ action: 'synthetic_echo', source: { id: 'call' } }, envelope, signal)).metadata.approved, true);
    const edited = (await command('PUT', '/synthetic', setting(endpoint + '/v2'))).value;
    assert.equal(edited.setting.endpointRevision, 2); assert.equal(edited.approved, false);
    await assert.rejects(mcp.permission({ action: 'synthetic_echo', source: { id: 'call' } }, envelope, signal), /stale/);

    await command('POST', '/synthetic/approve');
    await command('PUT', '/independent', { ...setting(endpoint), credentialRef: 'independent-ref', credential });
    await command('POST', '/independent/approve');
    const independent = await mcp.port.mcp('independent', config(endpoint));
    const beforeRevoke = settings.connection('synthetic').grantedEpoch;
    const active = await mcp.port.mcp('synthetic', config(endpoint + '/v2'));
    const second = mcp.approveMcpTool(descriptor, { ...envelope, call_id: 'second' }, signal), refused = assert.rejects(second, /stale/);
    while (!mcp.admin.pending().length) await turn();
    const pending = mcp.admin.pending()[0].id;
    assert.equal((await command('POST', '/synthetic/revoke')).value.approved, false);
    await assert.rejects(mcp.admin.answer(pending, 'always'), /stale/); await refused;
    await assert.rejects(mcp.port.mcp('synthetic', config(endpoint + '/v2')), /stale/);
    await assert.rejects(active.fetch(endpoint + '/v2', { method: 'POST', body: '{}' }), /stale/);
    assert.equal(await call(independent), 'synthetic reply');
    assert.equal(settings.connection('synthetic').grantedEpoch, beforeRevoke + 1);
    await command('POST', '/synthetic/approve');
    assert.equal(settings.connection('synthetic').grantedEpoch, beforeRevoke + 2);
    const reapproved = await mcp.port.mcp('synthetic', config(endpoint + '/v2'));
    const renewedReply = await reapproved.fetch(endpoint + '/v2', { method: 'POST', body: JSON.stringify({ id: 2 }) });
    assert.equal((await renewedReply.json()).result.content[0].text, 'synthetic reply');
    await reapproved.close();
    await assert.rejects(mcp.admin.answer(pending, 'always'), /stale/);
    const renewedApproval = mcp.approveMcpTool(descriptor, { ...envelope, call_id: 'renewed' }, signal);
    while (!mcp.admin.pending().length) await turn();
    await mcp.admin.answer(mcp.admin.pending()[0].id, 'once'); await renewedApproval;
    await command('POST', '/synthetic/revoke');
    assert.equal(await call(independent), 'synthetic reply');

    await mcp.admin.close(); await storage.close();
    storage = await open(); settings = await createStoredMcpSettings(storage); mcp = bridge(); mcps = { settings, admin: mcp.admin };
    const persisted = (await command('GET', '/synthetic')).value;
    assert.equal(persisted.approved, false); assert.equal(persisted.setting.endpointRevision, 2);
    await assert.rejects(mcp.port.mcp('synthetic', config(endpoint + '/v2')), /stale/);

    await command('DELETE', '/synthetic');
    assert.deepEqual((await command('GET', '')).value.map(item => item.setting.name), ['independent']);
    const surviving = await mcp.port.mcp('independent', config(endpoint));
    assert.equal(await call(surviving), 'synthetic reply'); await surviving.close();
    // A revision-1 handoff only succeeds once the removed reference was really forgotten.
    await command('PUT', '/synthetic', { ...setting(endpoint), credential });
    await mcp.admin.close(); await storage.close(); scan(profile);
  } finally { await mcp?.admin.close(); await storage.close().catch(() => {}); server.closeAllConnections(); server.close(); }
});
