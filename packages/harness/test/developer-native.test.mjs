// SPDX-License-Identifier: MIT
import './owned-environment.mjs';
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { DatabaseSync } from 'node:sqlite';
import { mkdtemp, mkdir, readFile, realpath, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { Context, Effect, Layer, Logger, ManagedRuntime } from 'effect';
import { OpenCode, AbsolutePath, Location, Agent } from '@opencode/sdk/effect';
import { Tool } from '@opencode/core/tool';
import { Instance } from '@opencode/core/instance';
import { llmClient } from '@opencode/core/effect/app-node-platform';
import { LLMClient } from '@opencode/ai';
import { TestLLM } from '@opencode/ai/testing';
import { closedHarnessEnvironment } from '../src/capability-plugins.ts';
import { createNativeCapabilityPlugin } from '../src/native-capability-plugin.ts';
import { createDeveloperRuntime } from '../src/developer-plugin.ts';
import { createCapabilityAuthority } from '../../backend/src/domain/capabilities/authority.ts';
import { CAPABILITY_SCHEMA, executeCapabilityCommand } from '../../backend/src/domain/capabilities/commands.ts';
import { executeDispatch } from '../../backend/src/storage/dispatch.ts';
import { defaultConfiguration, ALLOWED_MODELS } from '../../backend/src/dispatch/policy.ts';
import { digest } from '../../backend/src/storage/schema.ts';

test('native developer Off omits all developer families; enabled TestLLM write settles with a receipt', { timeout: 60000 }, async () => {
  const root = await realpath(await mkdtemp(path.join(tmpdir(), 'renulus-developer-native-')));
  const workspace = path.join(root, 'workspace'); await mkdir(workspace);
  const db = new DatabaseSync(':memory:');
  for (const name of ['002-harness-configuration.sql', '004-harness-dispatch-purpose.sql', '005-harness-children.sql'])
    db.exec(await readFile(new URL('../../../runtime/renulus/runtime/migrations/' + name, import.meta.url), 'utf8'));
  db.exec('CREATE TABLE preferences(key TEXT PRIMARY KEY,value TEXT,updated_at TEXT); CREATE TABLE assessment_test_attempts(id TEXT,mode TEXT,status TEXT);');
  db.exec(CAPABILITY_SCHEMA);
  const command = c => { db.exec('BEGIN IMMEDIATE'); try {
    const result = c.type.startsWith('capability.') ? executeCapabilityCommand(db, c) : executeDispatch(db, c);
    db.exec('COMMIT'); return result;
  } catch (error) { db.exec('ROLLBACK'); throw error; } };
  const spec = defaultConfiguration({ provider: 'codex', credential_reference: 'synthetic', credential_revision: 1, selected_model: ALLOWED_MODELS.codex[0] }, digest('synthetic'));
  spec.capabilities = ['text', 'developer.files.write'];
  const { version } = command({ type: 'dispatch.stage', spec, expectedEffective: null, expectedRequested: null, grantEpoch: 0 });
  const inspection = { configuration_version: version, grant_epoch: 0, registry_hash: spec.registry_hash, loaded_inputs: [], healthy: true,
    generation_open: false, recovery_open: false, package_acquisition_open: false, mcp_startup_open: false, live_store_writer: false };
  command({ type: 'dispatch.inspect', inspection }); command({ type: 'dispatch.close', version, expectedEffective: null, grantEpoch: 0 });
  command({ type: 'dispatch.activate', version, expectedEffective: null, settlement: { configuration_version: version, grant_epoch: 0, admission_closed: true, runtime_stopped: true, domain_settled: true } });
  command({ type: 'dispatch.open', inspection });
  const fence = { profile_id: 'synthetic', domain_store_id: 'synthetic', runtime_store_id: 'synthetic', authority_epoch: 1, process_generation: 'synthetic', context_epoch: 0, deletion_epoch: 0, cancellation_epoch: 0 };
  const parent = command({ type: 'dispatch.begin', runId: 'native_write', purpose: 'explain', expectedVersion: version, capabilities: spec.capabilities, availableModels: [...ALLOWED_MODELS.codex], operationModel: null, batchSize: null, fence });
  const model = ManagedRuntime.make(TestLLM.testLayer()), client = await model.runPromise(TestLLM.Test);
  try {
    for (const enabled of [false, true]) {
      const developer = createDeveloperRuntime({ resources: { python: 'unused', sourceRoot: root }, configuration: enabled ? {
        enabled: true, workspace, actions: ['developer.files.write'], roots: [{ path: workspace, read: true, write: true, execute: false }], executables: {}, endpoints: [] } : undefined });
      const envelope = (sessionID, call) => Promise.resolve({ run_id: parent.run_id, root_id: parent.root_id, session_id: sessionID, call_id: call,
        configuration: version, grant_epoch: 0, fence, retention: 'saved', mode: 'developer', depth: 0 });
      const authority = createCapabilityAuthority({ storage: { execute: async c => command(c) }, current: async (_e, action) => developer.grant(action), transport: {} });
      const native = await createNativeCapabilityPlugin({ authority, resolve: c => envelope(c.sessionID, c.id), localCurrent: () => true,
        commands: { permission: async () => ({ content: '', metadata: { approved: true } }) }, skills: [], developer: developer?.ports(authority, envelope) });
      const boundary = { id: 'synthetic-stock-boundary', effect: ctx => ctx.tool.transform(editor => { for (const tool of editor.list()) editor.remove(tool.id); }) };
      const config = JSON.stringify({ model: 'synthetic/write', execute: enabled, compaction: { auto: false }, mcp: { servers: {} },
        providers: { synthetic: { package: '@opencode/ai/providers/openai-compatible', settings: { baseURL: 'https://synthetic.invalid', apiKey: 'synthetic-unused' }, models: { write: { limit: { context: 128000, output: 4096 } } } } },
        agents: { renulus: { mode: 'primary', system: 'Synthetic developer test', permissions: [{ action: '*', resource: '*', effect: 'allow' }] }, title: { disabled: true } } });
      let instances;
      const runtime = ManagedRuntime.make(Layer.effect(OpenCode.Service, native.provide(OpenCode.create({ app: { name: 'renulus-developer-test', version: 'bf03' },
        database: { path: ':memory:' }, config: { project: false, content: config }, models: { fetch: false, snapshot: false }, fs: { filewatcher: false, fff: false }, events: { persist: false },
        plugins: [native.capture, boundary, ...native.plugins] }, { overrides: [...closedHarnessEnvironment(path.join(root, String(enabled)), config), ...native.overrides,
          Instance.node.replace(Instance.node.mapLayer(original => Layer.tap(original, context => Effect.sync(() => { instances = Context.get(context, Instance.Service); })))),
          llmClient.replace(Layer.succeed(LLMClient.Service, client))] })).pipe(Layer.provideMerge(Logger.layer([], { mergeWithExisting: false }))));
      try {
        const sdk = await runtime.runPromise(OpenCode.Service);
        const session = await runtime.runPromise(sdk.sessions.create({ title: 'Synthetic write', agent: Agent.ID.make('renulus'), location: Location.Ref.make({ directory: AbsolutePath.make(workspace) }) }));
        const snapshot = await runtime.runPromise(Effect.gen(function* () { return yield* (yield* Tool.Service).snapshot(); }).pipe(instances.provide(session)));
        if (!enabled) assert.deepEqual(snapshot.definitions.filter(t => /^(read|glob|grep|edit|write|patch|shell|execute|browser\..*|opencode\.worktree_.*|opencode\.session_move)$/.test(t.name)), []);
        else {
          await model.runPromise(client.push(TestLLM.tool('write_synthetic', 'write', { path: 'note.txt', content: 'SYNTHETIC native write' }), TestLLM.text('Written', 'answer')));
          await runtime.runPromise(sdk.sessions.prompt({ sessionID: session.id, text: 'Write the synthetic note' }));
          await runtime.runPromise(sdk.sessions.wait({ sessionID: session.id }));
          assert.equal(await readFile(path.join(workspace, 'note.txt'), 'utf8'), 'SYNTHETIC native write');
          assert.equal(db.prepare("SELECT state FROM capability_effects WHERE action='developer.files.write'").get().state, 'settled');
          assert.equal(developer.receipts().length, 1); assert.equal(developer.receipts()[0].path, path.join(workspace, 'note.txt'));
        }
      } finally { await native.close(); await runtime.dispose(); }
    }
  } finally { await model.dispose(); db.close(); await rm(root, { recursive: true, force: true }); }
});
