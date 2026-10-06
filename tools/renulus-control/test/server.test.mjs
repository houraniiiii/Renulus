import test from 'node:test';
import assert from 'node:assert/strict';
import { PassThrough } from 'node:stream';
import { EventEmitter } from 'node:events';
import { createServer, bindLifecycle, toolDefinitions, locatorSchema } from '../server.mjs';

test('bounded tool schemas reject endpoint/executable/eval/profile parameters and nonexact locators', () => {
  assert.equal(toolDefinitions.length, 11);
  for (const name of ['renulus_start', 'renulus_restart', 'renulus_close', 'renulus_snapshot']) {
    const schema = toolDefinitions.find(definition => definition[0] === name)[2];
    assert.equal(schema.safeParse({}).success, true);
    for (const param of ['endpoint', 'profile', 'executable', 'code', 'token']) assert.equal(schema.safeParse({ [param]: 'synthetic' }).success, false);
  }
  assert.equal(locatorSchema.safeParse({ role: 'button', name: 'Cases' }).success, true);
  assert.equal(locatorSchema.safeParse({ role: 'button', name: 'Cases', exact: false }).success, false);
  assert.equal(locatorSchema.safeParse({ css: 'button', role: 'button', name: 'Cases' }).success, false);
  const select = toolDefinitions.find(definition => definition[0] === 'renulus_select')[2];
  assert.equal(select.safeParse({ locator: { role: 'combobox', name: 'Topic' }, value: 'ckd', label: 'CKD' }).success, false);
  const wait = toolDefinitions.find(definition => definition[0] === 'renulus_wait')[2];
  assert.equal(wait.safeParse({ locator: { role: 'heading', name: 'Case' }, timeoutMs: 12001 }).success, false);
});

test('SDK registration works with the pinned Zod object schemas without launching any app', async () => {
  const controller = { run: async () => ({ synthetic: true }), shutdown: async () => {}, filled: [] };
  const server = createServer(controller);
  assert.equal(server.isConnected(), false);
  await server.close();
});

for (const event of ['EOF', 'SIGTERM', 'MCP disconnect']) {
  test(event + ' closes only the owned lifecycle once and detaches hooks', async () => {
    const input = new PassThrough(), output = new PassThrough(), signals = new EventEmitter(), reasons = [];
    let serverCloses = 0;
    const server = { server: {}, close: async () => { serverCloses++; server.server.onclose(); } };
    const controller = { shutdown: async reason => { reasons.push(reason); }, filled: [] };
    const hooks = bindLifecycle(server, controller, { input, output, signals, diagnostic: () => {} });
    if (event === 'EOF') input.emit('end');
    else if (event === 'SIGTERM') signals.emit('SIGTERM');
    else server.server.onclose();
    await hooks.stop('duplicate');
    assert.equal(reasons.length, 1); assert.equal(serverCloses, 1); assert.equal(signals.listenerCount('SIGTERM'), 0); assert.equal(input.listenerCount('end'), 0);
  });
}

test('shutdown failure remains a failure diagnostic and exit status; server still closes', async () => {
  const signals = new EventEmitter(), diagnostics = []; let closed = false;
  const hooks = bindLifecycle({ server: {}, close: async () => { closed = true; } }, { filled: [], shutdown: async () => { throw new Error('Owned backend survived'); } }, { input: new PassThrough(), output: new PassThrough(), signals, diagnostic: message => diagnostics.push(message) });
  await hooks.stop('mcp-disconnect'); assert.equal(signals.exitCode, 1); assert.equal(closed, true); assert.equal(diagnostics.length, 1);
});
