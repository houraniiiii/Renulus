// SPDX-License-Identifier: MIT
// The pinned LayerNode compiles overrides into a Map keyed by node: a second
// replacement of one node silently wins. This host enables every native
// override at once and checks that each party's behaviour is still live.
await import('./owned-environment.mjs');
await import('./capability-patch-loader.mjs');
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { mkdtemp, mkdir, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { Effect, ManagedRuntime } from 'effect';
const { TestLLM } = await import('@opencode/ai/testing');
const { LLMEvent } = await import('@opencode/ai');
const { openHarness } = await import('../src/host.ts');
const { createNativeCapabilityPlugin } = await import('../src/native-capability-plugin.ts');
const { createDeveloperRuntime } = await import('../src/developer-plugin.ts');

test('child authority, MCP mediation, developer tools and host captures compose in one native host', { timeout: 60_000 }, async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'renulus-override-composition-'));
  const workspace = path.join(root, 'harness-workspace');
  await mkdir(workspace, { recursive: true });
  const manifest = JSON.parse(await readFile(new URL('../../contracts/fixtures/harness/paired-store-prepared.json', import.meta.url), 'utf8'));
  manifest.runtime_store.store_id = 'synthetic-store';
  manifest.runtime_store.path = 'state/harness/opencode.sqlite';
  await mkdir(path.join(root, 'state', 'harness'), { recursive: true });
  await writeFile(path.join(root, 'state', 'harness', 'manifest.json'), JSON.stringify(manifest));

  const modes = new Map(), permissions = [], prepared = [];
  let gate = Promise.resolve(), host;
  const envelope = (sessionID, call) => Promise.resolve({ run_id: 'run', root_id: 'root', session_id: sessionID, call_id: String(call),
    configuration: 'configuration', grant_epoch: 0, fence: {}, retention: 'saved', mode: modes.get(sessionID) ?? 'doctor', depth: 0 });
  const developer = createDeveloperRuntime({ resources: { python: 'unused', sourceRoot: root }, configuration: { enabled: true, workspace,
    actions: ['developer.files.write'], roots: [{ path: workspace, read: true, write: true, execute: false }], executables: {}, endpoints: [] } });
  const authority = {
    invoke: async (owner, action, _input, execute) => execute({ id: 'lease', envelope: owner, action, payload_sha256: '', state: 'admitted',
      used_bytes: 0, effect_reference: null, grant: action.startsWith('developer.') ? developer.grant(action)
        : { actions: [action], roots: [], endpoints: [], skills: [], max_bytes: 0, expires_at_ms: Date.now() + 60_000 } }, new AbortController().signal),
    stop: async () => {}, close: async () => {}, status: () => ({}),
  };
  const native = await createNativeCapabilityPlugin({ authority, resolve: context => envelope(context.sessionID, context.id), localCurrent: () => true,
    // Production wires commands.permission to mcp.permission (plugins/native.ts).
    commands: { permission: async (input, owner) => { permissions.push({ action: input.action, session: owner.session_id });
      return { content: '', metadata: { approved: true } }; } },
    skills: [], mcp: async () => { throw new Error('unexpected_mcp_connection'); }, approveMcpTool: async () => {},
    developer: developer.ports(authority, envelope),
    children: { resolveParent: context => host.binding(context.sessionID), localCurrent: () => true,
      bindInput: child => host.bindChild(child), request: () => Effect.die(new Error('unexpected_child_request')) } });
  const modelRuntime = ManagedRuntime.make(TestLLM.testLayer());
  const client = await modelRuntime.runPromise(TestLLM.Test);
  const push = (...responses) => modelRuntime.runPromise(client.push(...responses));
  const requests = async () => (await modelRuntime.runPromise(client.requests())).length;
  const model = { providerId: 'synthetic', modelId: 'composition', client,
    configuration: { model: 'synthetic/composition', providers: { synthetic: { package: '@opencode/ai/providers/openai-compatible',
      settings: { baseURL: 'https://synthetic.invalid/v1', apiKey: 'synthetic-unused' },
      models: { composition: { limit: { context: 128000, output: 4096 } } } } } },
    // A prepared primary requires the host's session.context snapshot (S7).
    preparePrimary: (binding, resolved) => Effect.promise(() => gate).pipe(Effect.map(() => {
      prepared.push(binding.session_id);
      return { resolved: { ...resolved }, prepare: request => Effect.succeed(request) };
    })) };
  const turn = async (session, operationId, text) => {
    await host.submit({ sessionId: session.id, operationId, attemptId: '1', text });
    await host.wait(session.id);
    return JSON.stringify((await host.observe(session.id, { order: 'asc', limit: 200 })).messages);
  };
  try {
    // Startup reads jobs.pendingBackground: the host's Job/SessionExecution captures (S0).
    host = await openHarness({ root, profileId: 'synthetic-profile', storeId: 'synthetic-store', domainStoreId: 'synthetic-domain-store',
      domainPath: 'domain/renulus.sqlite3', model, nativeCapabilities: native,
      capabilityPermissions: ['developer.files.write', 'renulus.child', 'subagent'] });
    await host.activate('composition');
    assert.deepEqual((await host.status()).activeSessionIds, []);

    // Developer session: a normal send admits, then the stock write tool's
    // permission request is mediated to commands.permission (S12).
    const builder = await host.createSession({ operationId: 'developer_op', title: 'Synthetic developer' });
    modes.set(builder.id, 'developer');
    await push(TestLLM.text('Synthetic renal answer', 'answer'));
    assert.match(await turn(builder, 'developer_op', 'Explain tubular sodium handling'), /Synthetic renal answer/);
    assert.deepEqual(prepared, [builder.id]);
    await push(TestLLM.tool('write_synthetic', 'write', { path: 'note.txt', content: 'SYNTHETIC composed write' }), TestLLM.text('Written', 'answer'));
    await turn(builder, 'developer_op_2', 'Write the synthetic note');
    assert.equal(await readFile(path.join(workspace, 'note.txt'), 'utf8'), 'SYNTHETIC composed write');
    assert.ok(permissions.length > 0 && permissions.every(item => item.session === builder.id), JSON.stringify(permissions));

    // Doctor session: developer tools deny; raw child work with a selector is
    // refused by the child guard composed into the host's PluginHooks wrapper.
    const doctor = await host.createSession({ operationId: 'doctor_op', title: 'Synthetic doctor' });
    const mediated = permissions.length;
    await push(TestLLM.toolCalls(
      LLMEvent.toolCall({ id: 'doctor_write', name: 'write', input: { path: 'doctor.txt', content: 'SYNTHETIC' } }),
      LLMEvent.toolCall({ id: 'invalid_child', name: 'subagent', input: { description: 'Review synthetic evidence',
        prompt: 'Review it', background: false, model: 'SYNTHETIC_SELECTOR' } })), TestLLM.text('Refused', 'answer'));
    const refused = await turn(doctor, 'doctor_op', 'Try the refused tools');
    assert.match(refused, /developer_profile_required/);
    assert.match(refused, /child_invalid_work/);
    assert.equal(permissions.length, mediated);
    assert.equal((await host.listChildren(doctor.id)).length, 0);

    // An un-admitted request never reaches the model: admission closes while
    // the primary is being prepared.
    const before = await requests();
    let release;
    gate = new Promise(resolve => { release = resolve; });
    const late = await host.createSession({ operationId: 'late_op', title: 'Synthetic late' });
    await push(TestLLM.text('Must not be served', 'answer'));
    await host.submit({ sessionId: late.id, operationId: 'late_op', attemptId: '1', text: 'Late request' });
    await assert.rejects(host.holdRecovery(), /recovery_requires_quiescence/);
    release();
    await host.wait(late.id);
    assert.equal(await requests(), before);
  } finally {
    await host?.close({ timeoutMs: 10_000 });
    await native.close();
    await modelRuntime.dispose();
  }
});
