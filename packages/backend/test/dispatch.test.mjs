// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import { after, test } from 'node:test';
import { DatabaseSync } from 'node:sqlite';
import { mkdtempSync, readFileSync, rmSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, basename, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { executeDispatch } from '../src/storage/dispatch.ts';
import { defaultConfiguration, ALLOWED_MODELS } from '../src/dispatch/policy.ts';
import { PURPOSES } from '../src/dispatch/contracts.ts';
import { canonical, digest } from '../src/storage/schema.ts';
import { createNativeDispatchCallbacks } from '../src/dispatch/native.ts';
import { verifyWire, parseJson } from '../src/dispatch/wire.ts';

const tempRoot = resolve(tmpdir());
const root = mkdtempSync(join(tempRoot, 'renulus-dispatch-bf01-'));
const repository = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const fence = { profile_id: 'synthetic_profile', domain_store_id: 'domain_a', runtime_store_id: 'native_a', authority_epoch: 1,
  process_generation: 'process_a', context_epoch: 0, deletion_epoch: 0, cancellation_epoch: 0 };
let sequence = 0;
const databases = new Set();
function fixture(provider = 'codex', patch = s => s) {
  assert.equal(process.versions.node, '26.4.0');
  const path = join(root, 'dispatch-' + (++sequence) + '.sqlite3');
  let db = new DatabaseSync(path, { enableForeignKeyConstraints: true }); databases.add(db);
  for (const name of ['002-harness-configuration.sql', '004-harness-dispatch-purpose.sql']) db.exec(readFileSync(join(repository, 'runtime/renulus/runtime/migrations', name), 'utf8'));
  db.exec("CREATE TABLE preferences(key TEXT PRIMARY KEY,value TEXT,updated_at TEXT); CREATE TABLE assessment_test_attempts(id TEXT,mode TEXT,status TEXT);");
  const spec = patch(defaultConfiguration({ provider, credential_reference: 'protected_reference_only', credential_revision: 1,
    selected_model: ALLOWED_MODELS[provider][0] }, digest('synthetic-registry')));
  function command(c) {
    db.exec('BEGIN IMMEDIATE');
    try { const result = executeDispatch(db, c); assert.equal(typeof result?.then, 'undefined'); db.exec('COMMIT'); return result; }
    catch (e) { db.exec('ROLLBACK'); throw e; }
  }
  const { version } = command({ type: 'dispatch.stage', spec, expectedEffective: null, expectedRequested: null, grantEpoch: 0 });
  const inspection = inspectionFor(spec, version);
  const settle = { configuration_version: version, grant_epoch: 0, admission_closed: true, runtime_stopped: true, domain_settled: true };
  function activate() {
    assert.deepEqual(command({ type: 'dispatch.inspect', inspection }), { ready: true });
    command({ type: 'dispatch.close', version, expectedEffective: null, grantEpoch: 0 });
    command({ type: 'dispatch.activate', version, expectedEffective: null, settlement: settle });
    command({ type: 'dispatch.open', inspection });
  }
  function begin(runId = 'run_a', purpose = 'explain', capabilities = ['text'], batchSize = null) {
    return command({ type: 'dispatch.begin', runId, purpose, expectedVersion: version, capabilities, availableModels: [...ALLOWED_MODELS[provider]],
      operationModel: null, fence, batchSize });
  }
  function close() { db.close(); databases.delete(db); }
  function reopen() { close(); db = new DatabaseSync(path, { enableForeignKeyConstraints: true }); databases.add(db); }
  return { command, spec, version, inspection, settle, activate, begin, path, reopen, close, db: () => db };
}
function inspectionFor(spec, version, epoch = 0) {
  return { configuration_version: version, grant_epoch: epoch, registry_hash: spec.registry_hash, loaded_inputs: spec.inputs, healthy: true,
    generation_open: false, recovery_open: false, package_acquisition_open: false, mcp_startup_open: false, live_store_writer: false };
}
function qualification(route, caps = ['text']) {
  return { id: 'synthetic_qualification', route, limits: { input_tokens: 49152, output_tokens: 4096, window_tokens: 57344 }, capabilities: caps,
    limits_revision: 'synthetic_limits', capabilities_revision: 'synthetic_entitlement', counter_revision: 'synthetic_counter_fixture_v1' };
}
function proof(run, patch = {}) {
  return { qualification: qualification(run.route, run.effective_capabilities), payload_hash: digest('synthetic-body'), wire_sha256: digest('synthetic-wire'),
    input_manifest_sha256: digest('synthetic-manifest'), body_bytes: 128, input_tokens: 16, output_tokens: 64, ...patch };
}
function reserve(f, run, stepId = 'step_a', requestKind = run.parent_id ? 'child' : 'primary', patch = {}) {
  return f.command({ type: 'dispatch.reserve', runId: run.run_id, stepId, requestKind, continuationOf: null,
    requiredCapabilities: run.effective_capabilities, fence, proof: proof(run), ...patch });
}
function admit(f, p, run, value = proof(run)) { return f.command({ type: 'dispatch.admit', permitId: p.permit_id, fence, proof: value }); }
function complete(f, p, outcome = 'confirmed', failureCode = null) {
  return f.command({ type: 'dispatch.complete', permitId: p.permit_id, outcome, resultReference: outcome === 'confirmed' ? 'result_reference' : null, failureCode });
}
after(() => {
  for (const db of databases) db.close();
  assert.equal(dirname(root), tempRoot); assert.match(basename(root), /^renulus-dispatch-bf01-/); rmSync(root, { recursive: true, force: true });
});

test('exact candidate inspection, stopped-host selection and post-restart inspection keep mismatched bytes closed', () => {
  const f = fixture('codex', s => ({ ...s, inputs: [{ kind: 'artifact', name: 'library_plugin', sha256: digest('actual-loaded-bytes') }] }));
  assert.throws(() => f.begin(), { code: 'configuration_not_active' });
  const wrong = { ...f.inspection, loaded_inputs: [{ ...f.spec.inputs[0], sha256: digest('restored-old-bytes') }] };
  assert.deepEqual(f.command({ type: 'dispatch.inspect', inspection: wrong }), { ready: false });
  assert.equal(f.command({ type: 'dispatch.snapshot' }).failed, f.version);
  assert.throws(() => f.command({ type: 'dispatch.activate', version: f.version, expectedEffective: null, settlement: { ...f.settle, runtime_stopped: false } }), { code: 'restart_boundary_required' });
  f.command({ type: 'dispatch.inspect', inspection: f.inspection });
  f.command({ type: 'dispatch.activate', version: f.version, expectedEffective: null, settlement: f.settle });
  assert.throws(() => f.command({ type: 'dispatch.open', inspection: wrong }), { code: 'registry_mismatch' });
  assert.equal(f.command({ type: 'dispatch.snapshot' }).admission_open, false);
  f.command({ type: 'dispatch.open', inspection: f.inspection });
  assert.equal(f.begin().route.catalog_model_id, 'gpt-6.1-sol');
  assert.throws(() => executeDispatch(f.db(), { type: 'dispatch.snapshot' }), { code: 'configuration_transaction_required' });
});

test('all mandatory purposes have positive bounded defaults; exact 5/10/20 generation budgets and optional title', () => {
  for (const p of PURPOSES.filter(p => p !== 'title')) {
    const f = fixture(); f.activate(); const r = f.begin('run_' + p.replaceAll('-', '_'), p, ['text'], ['generated-practice', 'test-import', 'fictional-test'].includes(p) ? 20 : null);
    assert.ok(r.dispatch_limit > 0 && r.dispatch_limit <= 32, p);
    if (['generated-practice', 'test-import', 'fictional-test'].includes(p)) assert.equal(r.dispatch_limit, 24);
    assert.equal(reserve(f, r).dispatch_purpose, p);
  }
  const f = fixture(); f.activate();
  assert.throws(() => f.begin('title', 'title'), { code: 'role_disabled' });
  assert.throws(() => f.begin('generate', 'generated-practice'), { code: 'generation_batch_required' });
  for (const [n, limit] of [[5, 6], [10, 12], [20, 24]]) assert.equal(f.begin('batch_' + n, 'generated-practice', ['text'], n).dispatch_limit, limit);
});

test('exact subscription/model selection and unavailable override refuse without a fallback', () => {
  const f = fixture('opencode-go'); f.activate(); const run = f.begin();
  assert.equal(run.route.endpoint, 'https://opencode.ai/zen/go/v1/chat/completions');
  const c = { type: 'dispatch.begin', runId: 'bad', purpose: 'explain', expectedVersion: f.version, capabilities: ['text'], availableModels: ['deepseek-v4.1-flash'],
    operationModel: null, fence, batchSize: null };
  assert.throws(() => f.command(c), { code: 'model_unavailable' });
  assert.throws(() => f.command({ ...c, operationModel: 'gpt-6.1-sol' }), { code: 'model_not_allowed' });
  const spec = structuredClone(f.spec); spec.connection.secret = 'SYNTHETIC_SECRET';
  assert.throws(() => f.command({ type: 'dispatch.stage', spec, expectedEffective: f.version, expectedRequested: f.version, grantEpoch: 0 }), { code: 'storage_invalid_command' });
});

test('reserve/admit split, exact proof, revoke linearization and publication fence survive SQLite reopen', () => {
  const f = fixture('codex', s => ({ ...s, capabilities: ['text', 'tools'] })); f.activate(); const run = f.begin('run_a', 'explain', ['text', 'tools']);
  const p = reserve(f, run); assert.equal(p.state, 'reserved'); assert.equal(p.dispatch_allowed, false);
  assert.equal(reserve(f, run).permit_id, p.permit_id);
  assert.throws(() => admit(f, p, run, { ...proof(run), input_tokens: 17 }), { code: 'deployment_proof_changed' });
  f.command({ type: 'dispatch.revoke', capability: 'tools' });
  assert.throws(() => admit(f, p, run), { code: 'capability_revoked' });
  f.reopen(); assert.equal(f.command({ type: 'dispatch.permit', permitId: p.permit_id }).state, 'reserved');
  complete(f, p, 'cancelled_before_send');
  const f2 = fixture(); f2.activate(); const r2 = f2.begin(); const p2 = reserve(f2, r2); admit(f2, p2, r2);
  f2.command({ type: 'dispatch.revoke', capability: 'purpose:summary' }); complete(f2, p2);
  assert.throws(() => f2.command({ type: 'dispatch.current', runId: r2.run_id, fence, requiredCapabilities: [], permitId: p2.permit_id }), { code: 'grant_epoch_changed' });
  assert.throws(() => admit(f2, p2, r2), { code: 'dispatch_already_admitted' });
});

test('timeout retains debit, holds capacity, cannot resend, and late known receipt only reconciles', () => {
  const f = fixture(); f.activate(); const run = f.begin(); const p = reserve(f, run); admit(f, p, run); complete(f, p, 'uncertain', 'transport_timeout');
  f.reopen(); assert.throws(() => reserve(f, run), { code: 'dispatch_uncertain' });
  assert.throws(() => reserve(f, run, 'new_step'), { code: 'dispatch_uncertain' });
  assert.throws(() => complete(f, p, 'failed', 'transport_unavailable'), { code: 'receipt_conflict' });
  complete(f, p); assert.equal(complete(f, p).state, 'confirmed');
  assert.equal(reserve(f, run).dispatch_allowed, false);
  assert.equal(f.db().prepare('SELECT count(*) AS n FROM harness_configuration_attempts').get().n, 1);
});

test('final admission fences queued permits across the same run and both parent/child directions', () => {
  for (const ordering of ['same-run', 'parent-first', 'child-first']) {
    const f = fixture(); f.activate(); const parent = f.begin('root');
    const child = ordering === 'same-run' ? parent : f.command({ type: 'dispatch.child', runId: 'child', parentId: parent.run_id,
      purpose: 'evidence-review', capabilities: ['text'], operationModel: null, fence });
    const [firstRun, waitingRun] = ordering === 'child-first' ? [child, parent] : [parent, child];
    const first = reserve(f, firstRun, 'first'), waiting = reserve(f, waitingRun, 'waiting');
    admit(f, first, firstRun);
    assert.throws(() => admit(f, waiting, waitingRun), { code: 'dispatch_uncertain' }, ordering + ': dispatched');
    complete(f, first, 'uncertain', 'transport_timeout');
    assert.throws(() => admit(f, waiting, waitingRun), { code: 'dispatch_uncertain' }, ordering + ': uncertain');
    f.reopen();
    assert.throws(() => admit(f, waiting, waitingRun), { code: 'dispatch_uncertain' }, ordering + ': reopened');
    assert.equal(f.command({ type: 'dispatch.permit', permitId: waiting.permit_id }).state, 'reserved');
    assert.equal(f.db().prepare('SELECT count(*) AS n FROM harness_configuration_attempts').get().n, 2);
    complete(f, first); // A known late receipt releases the hold without another attempt/debit.
    assert.equal(admit(f, waiting, waitingRun).dispatch_allowed, true);
    complete(f, waiting);
  }
});

test('children narrow grants, share root budget, allow one depth/concurrent child, and settlement requires children', () => {
  const f = fixture('codex', s => ({ ...s, capabilities: ['text', 'tools'] })); f.activate(); const parent = f.begin('root', 'explain', ['text', 'tools']);
  const c = { type: 'dispatch.child', runId: 'child', parentId: 'root', purpose: 'evidence-review', capabilities: ['text'], operationModel: null, fence };
  const child = f.command(c);
  assert.equal(child.root_id, 'root');
  assert.throws(() => f.command({ ...c, runId: 'second' }), { code: 'child_concurrency_exhausted' });
  assert.throws(() => f.command({ ...c, runId: 'grandchild', parentId: 'child' }), { code: 'child_depth_exhausted' });
  const p = reserve(f, child); admit(f, p, child); complete(f, p);
  assert.throws(() => f.command({ type: 'dispatch.settle', runId: 'root', settlement: f.settle }), { code: 'run_not_settled' });
  f.command({ type: 'dispatch.settle', runId: 'child', settlement: f.settle });
  for (let i = 0; i < 7; i++) { const a = reserve(f, parent, 'step_' + i, i ? 'tool-continuation' : 'primary', i ? { continuationOf: parent.last } : {}); admit(f, a, parent); complete(f, a); parent.last = a.permit_id; }
  assert.throws(() => reserve(f, parent, 'exhausted', 'tool-continuation', { continuationOf: parent.last }), { code: 'dispatch_budget_exhausted' });
});

test('two remote profile slots include uncertain effects; request qualification and window limits fail closed', () => {
  const f = fixture(); f.activate(); const r1 = f.begin('one'), r2 = f.begin('two'), r3 = f.begin('three');
  reserve(f, r1); reserve(f, r2); assert.throws(() => reserve(f, r3), { code: 'dispatch_concurrency_exhausted' });
  const g = fixture(); g.activate(); const r = g.begin();
  for (const patch of [{ input_tokens: 55000 }, { output_tokens: 32768 }, { qualification: { ...qualification(r.route), limits: { input_tokens: 100, output_tokens: 64, window_tokens: 100 } } },
    { qualification: { ...qualification(r.route), counter_revision: '' } }]) assert.throws(() => reserve(g, r, 'invalid', 'primary', { proof: proof(r, patch) }));
  g.db().prepare("INSERT INTO assessment_test_attempts VALUES('test','test','active')").run();
  assert.throws(() => reserve(g, r), { code: 'assistance_restricted' });
  g.db().exec('DELETE FROM assessment_test_attempts');
  assert.throws(() => g.command({ type: 'dispatch.current', runId: r.run_id, fence: { ...fence, deletion_epoch: 1 }, requiredCapabilities: [], permitId: null }), { code: 'run_unavailable' });
});

test('summary repair shares compaction pool; opaque fallback/recovery and stale continuation refuse', () => {
  const f = fixture(); f.activate(); const r = f.begin();
  const first = reserve(f, r, 'compact', 'compaction'); admit(f, first, r); complete(f, first, 'failed', 'summary_invalid');
  const repair = reserve(f, r, 'repair', 'summary-repair'); assert.equal(repair.dispatch_purpose, 'compaction'); admit(f, repair, r); complete(f, repair, 'failed', 'summary_invalid');
  assert.throws(() => reserve(f, r, 'another_repair', 'summary-repair'), { code: 'dispatch_budget_exhausted' });
  assert.throws(() => reserve(f, r, 'fallback', 'transport-fallback'), { code: 'transport_fallback_unavailable' });
  assert.throws(() => reserve(f, r, 'recovery', 'recovery'), { code: 'dispatch_recovery_unavailable' });
  assert.throws(() => reserve(f, r, 'continuation', 'tool-continuation', { continuationOf: repair.permit_id }), { code: 'continuation_not_confirmed' });
});

test('stopped-host crash reconciliation preserves uncertainty and revoked overlay, never reopens admission', () => {
  const f = fixture(); f.activate(); const run = f.begin(); const a = reserve(f, run); admit(f, a, run);
  const second = f.begin('queued'); const b = reserve(f, second);
  f.command({ type: 'dispatch.close', version: f.version, expectedEffective: f.version, grantEpoch: 0 });
  f.command({ type: 'dispatch.reconcile', settlement: f.settle }); f.reopen();
  assert.equal(f.command({ type: 'dispatch.permit', permitId: a.permit_id }).state, 'uncertain');
  assert.equal(f.command({ type: 'dispatch.permit', permitId: b.permit_id }).state, 'cancelled_before_send');
  assert.equal(f.command({ type: 'dispatch.snapshot' }).admission_open, false);
});

test('uncertain attempts from a dead process generation keep their debit and root block but free the concurrency slots', () => {
  const f = fixture(); f.activate(); const r1 = f.begin('one'), r2 = f.begin('two');
  const a = reserve(f, r1); admit(f, a, r1); const b = reserve(f, r2); admit(f, b, r2);
  f.command({ type: 'dispatch.close', version: f.version, expectedEffective: f.version, grantEpoch: 0 });
  f.command({ type: 'dispatch.reconcile', settlement: f.settle }); f.reopen();
  f.db().prepare('UPDATE harness_configuration_pointer SET admission_open=1 WHERE id=1').run();
  const next = { ...fence, process_generation: 'process_b' };
  const beginNext = runId => f.command({ type: 'dispatch.begin', runId, purpose: 'explain', expectedVersion: f.version, capabilities: ['text'],
    availableModels: [...ALLOWED_MODELS.codex], operationModel: null, fence: next, batchSize: null });
  const [r3, r4, r5] = ['three', 'four', 'five'].map(beginNext);
  assert.equal(reserve(f, r3, 'step_a', 'primary', { fence: next }).state, 'reserved');
  assert.equal(reserve(f, r4, 'step_a', 'primary', { fence: next }).state, 'reserved');
  assert.throws(() => reserve(f, r5, 'step_a', 'primary', { fence: next }), { code: 'dispatch_concurrency_exhausted' });
  assert.equal(f.command({ type: 'dispatch.permit', permitId: a.permit_id }).state, 'uncertain');
  assert.equal(f.db().prepare("SELECT count(*) AS n FROM harness_configuration_attempts WHERE state='uncertain'").get().n, 2);
});

test('strict wire parser rejects duplicate JSON keys, extra history, dropped native inputs and auth headers', () => {
  assert.throws(() => parseJson('{"model":"a","model":"b"}'));
  const f = fixture(); f.activate(); const run = f.begin();
  const manifest = { version: 1, system: 'Synthetic teaching', messages: [{ role: 'user', content: [{ type: 'text', text: 'Synthetic CKD' }] }], tools: [] };
  const body = { model: run.route.wire_model_id, stream: true, instructions: manifest.system, input: [{ role: 'user', content: [{ type: 'input_text', text: 'Synthetic CKD' }] }], max_output_tokens: 64 };
  const serialized = { method: 'POST', url: run.route.endpoint, headers: { 'content-type': 'application/json' }, body_base64: Buffer.from(JSON.stringify(body)).toString('base64') };
  assert.equal(verifyWire(serialized, manifest, run.route, 8192, 64).body_sha256, digest(JSON.stringify(body)));
  for (const payload of [{ ...body, instructions: 'DROPPED' }, { ...body, previous_response_id: 'opaque_history' }, { ...body, input: [] }, { ...body, model: 'gpt-6-luna' }]) {
    assert.throws(() => verifyWire({ ...serialized, body_base64: Buffer.from(JSON.stringify(payload)).toString('base64') }, manifest, run.route, 8192, 64));
  }
  assert.throws(() => verifyWire({ ...serialized, headers: { authorization: 'SYNTHETIC_CANARY' } }, manifest, run.route, 8192, 64));
});

test('real native serializer → typed callbacks → SQLite reserve/admit → counting fixture transport (both subscriptions, tools)', async () => {
  // SDK configuration, caches and temp all belong to this disposable synthetic test.
  for (const name of ['OPENCODE_TEST_HOME', 'APPDATA', 'LOCALAPPDATA', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME', 'XDG_STATE_HOME', 'XDG_RUNTIME_DIR', 'TEMP', 'TMP']) {
    process.env[name] = join(root, 'sdk', name); mkdirSync(process.env[name], { recursive: true });
  }
  const { Effect } = await import('effect');
  const { HttpClientResponse } = await import('effect/http');
  const { LLMRequest, Message, SystemPart, ToolDefinition } = await import('@opencode/ai');
  const { createSubscriptionAdapter } = await import('../../harness/src/provider-adapter.ts');
  const { captureNativeManifest } = await import('../../harness/src/native-manifest.ts');
  for (const provider of ['opencode-go', 'codex']) {
    const f = fixture(provider, s => ({ ...s, capabilities: ['text', 'tools'] })); f.activate(); const run = f.begin('native_' + provider.replaceAll('-', '_'), 'explain', ['text', 'tools']);
    const binding = { operation_id: run.run_id, attempt_id: 'attempt', session_id: 'native_session', input_id: 'input', cancellation_id: 'cancel' };
    let sends = 0, counts = 0, latest;
    const evidence = Object.freeze({ metadata: qualification(run.route, ['text', 'tools']), count: async (bytes, manifest) => {
      counts++; assert.ok(manifest.tools.length); assert.ok(Buffer.from(bytes).includes(Buffer.from('Synthetic passage'))); return 256;
    } });
    const callbacks = createNativeDispatchCallbacks({ storage: { command: async c => f.command(c) }, resolve: async () => ({ runId: run.run_id, fence }), checkCurrent: async () => {},
      evidence: () => evidence, transport: { fixtureOnly: true, send: async ({ permit, serialized }) => {
        sends++; assert.equal(permit.dispatch_allowed, true); assert.equal(f.command({ type: 'dispatch.permit', permitId: permit.permit_id }).state, 'dispatched');
        latest = serialized; const model = run.route.wire_model_id;
        const events = provider === 'codex' ? [
          { type: 'response.output_item.added', item: { type: 'message', id: 'message' } },
          { type: 'response.output_text.delta', item_id: 'message', delta: 'Synthetic answer' },
          { type: 'response.output_item.done', item: { type: 'message', id: 'message', content: [{ type: 'output_text', text: 'Synthetic answer' }] } },
          { type: 'response.completed', response: { id: 'response', model, status: 'completed' } },
        ] : [{ content: 'Synthetic answer' }, {}].map((delta, i) => ({ id: 'response', model, choices: [{ index: 0, delta, finish_reason: i ? 'stop' : null }] }));
        return { status: 200, headers: { 'content-type': 'text/event-stream' }, result_reference: 'native_receipt',
          body_base64: Buffer.from(events.map(e => 'data: ' + JSON.stringify(e) + '\n\n').join('') + (provider === 'codex' ? '' : 'data: [DONE]\n\n')).toString('base64') };
      } } });
    let plan, callbackFailure;
    const adapter = await createSubscriptionAdapter({ route: run.route, sessionId: binding.session_id, dispatch: (_r, http) => Effect.tryPromise({ try: async () => {
      const outcome = await callbacks.handle(binding, 'model.dispatch', { dispatch_id: plan.result.dispatch_id,
        serialized_request: { method: 'POST', url: http.url, headers: http.headers, body_base64: Buffer.from(http.body.body).toString('base64') } });
      assert.equal(outcome.outcome, 'committed_reference', JSON.stringify({ outcome, headers: http.headers, url: http.url, body: JSON.parse(Buffer.from(http.body.body)) }));
      return HttpClientResponse.fromWeb(http, new Response(Buffer.from(outcome.result.body_base64, 'base64'), { headers: outcome.result.headers }));
    }, catch: e => { callbackFailure = e; return e; } }) });
    try {
      plan = await callbacks.handle(binding, 'model.prepare', {}); assert.equal(plan.outcome, 'committed_reference');
      const request = new LLMRequest({ model: adapter.model, system: [SystemPart.make('Synthetic teaching')], generation: { maxTokens: 64 },
        messages: [Message.user('Synthetic AKI'), Message.assistant([{ type: 'tool-call', id: 'call_1', name: 'renulus_library_retrieve', input: { q: 'AKI' } }]),
          Message.make({ role: 'tool', content: [{ type: 'tool-result', id: 'call_1', name: 'renulus_library_retrieve', result: { type: 'text', value: 'Synthetic passage' } }] })],
        tools: [ToolDefinition.make({ name: 'renulus_library_retrieve', description: 'Synthetic library', inputSchema: { type: 'object', properties: { q: { type: 'string' } } } })] });
      assert.equal((await callbacks.handle(binding, 'model.manifest', { manifest: captureNativeManifest(request) })).outcome, 'committed_reference');
      let response;
      try { response = await Effect.runPromise(adapter.client.generate(request)); } catch (error) { throw callbackFailure ?? error; }
      assert.equal(response.text, 'Synthetic answer');
      assert.deepEqual([sends, counts], [1, 1]);
      assert.equal((await callbacks.handle(binding, 'model.dispatch', { dispatch_id: plan.result.dispatch_id, serialized_request: latest })).outcome, 'rejected_before_admission');
      assert.equal(sends, 1); f.reopen();
      assert.equal(f.db().prepare('SELECT state FROM harness_configuration_attempts').get().state, 'confirmed');
    } finally { await adapter.close(); await callbacks.close(); }
  }
});
