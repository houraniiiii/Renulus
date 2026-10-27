// SPDX-License-Identifier: MIT
import '../../harness/test/owned-environment.mjs';
import assert from 'node:assert/strict';
import { test, after, before } from 'node:test';
import { spawnSync } from 'node:child_process';
import { DatabaseSync } from 'node:sqlite';
import { mkdtempSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Effect, ManagedRuntime, Stream } from 'effect';
import { TestLLM } from '@opencode/ai/testing';
import { openSavedLearningTarget } from '../src/host/learning.ts';
import { createTemporaryFamily, reconcileTemporarySaves } from '../src/domain/temporary/index.ts';
import { exportVolatileFamily, openVolatileHarness, remapVolatileFamily } from '../../harness/src/volatile-host.ts';
import { openIsolatedStorage } from '../src/storage/index.ts';
import { MARKER, SELECTOR } from '../src/storage/ownership.ts';
import { inventory, loadMigrationInventory } from '../src/storage/schema.ts';

const repository = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const python = 'C:/Renulus/dev/python/Scripts/python.exe';
const sentinel = 'SYNTHETIC_TEMPORARY_CASE_bf04_5e1c77';
const identity = { profileId: 'synthetic-profile', storeId: 'synthetic-store' };
const root = mkdtempSync(join(tmpdir(), 'renulus-temporary-save-'));
const profile = join(root, 'profile');
const cleanups = [];
let storage, target, database, model;

function files(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap(item => item.isDirectory() ? files(join(directory, item.name)) : [join(directory, item.name)]);
}
const holds = (directory, text) => files(directory).some(file => readFileSync(file).includes(Buffer.from(text)));
function sql(query, ...args) {
  const db = new DatabaseSync(database, { readOnly: true });
  try { return db.prepare(query).all(...args).map(row => ({ ...row })); } finally { db.close(); }
}
async function savedModel() {
  const runtime = ManagedRuntime.make(TestLLM.testLayer()), client = await runtime.runPromise(TestLLM.Test);
  return { providerId: 'synthetic', modelId: 'saved', client, configuration: { model: 'synthetic/saved', providers: { synthetic: {
    package: '@opencode/ai/providers/openai-compatible', settings: { baseURL: 'https://synthetic.invalid/v1', apiKey: 'synthetic-unused' },
    models: { saved: { limit: { context: 128000, output: 4096 } } } } } }, count: async () => (await runtime.runPromise(client.requests())).length,
  close: () => runtime.dispose() };
}
before(async () => {
  assert.equal(process.versions.node, '26.4.0');
  const migrations = loadMigrationInventory(repository);
  const script = `
import sys
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'runtime'))
from renulus.server import create_app
s=create_app(Path(sys.argv[2])).state.services
with s.db.transaction() as c:
    c.execute("INSERT OR REPLACE INTO harness_store_identity VALUES(1,'synthetic-profile','synthetic-domain-store',1,'4b6fea2875e4f2e3e8a8fee181803e54f7056845')")
print(s.paths.database)
`;
  const env = Object.fromEntries(['SystemRoot', 'WINDIR', 'TEMP', 'TMP'].filter(k => process.env[k]).map(k => [k, process.env[k]]));
  env.PATH = dirname(python);
  const prepared = spawnSync(python, ['-I', '-X', 'utf8', '-c', script, repository, profile], { encoding: 'utf8', env, timeout: 60000 });
  assert.equal(prepared.status, 0, prepared.stderr || prepared.error?.message);
  database = prepared.stdout.trim();
  const db = new DatabaseSync(database); const expectedSchemaHash = inventory(db, migrations).schemaHash; db.close();
  const selection = { contract: 'renulus-storage-selector/1', isolation: 'synthetic', profileId: identity.profileId, generation: 1,
    authorityEpoch: 1, writer: 'ts', state: 'active', ownerId: 'synthetic-bf04-owner', database: 'state/renulus.sqlite3' };
  writeFileSync(join(profile, MARKER), JSON.stringify({ contract: 'renulus-synthetic-storage/1', profileId: identity.profileId }));
  writeFileSync(join(profile, SELECTOR), JSON.stringify(selection));
  const manifest = JSON.parse(readFileSync(join(repository, 'packages/contracts/fixtures/harness/paired-store-prepared.json'), 'utf8'));
  manifest.domain_store.path = 'state/renulus.sqlite3'; manifest.runtime_store.store_id = identity.storeId; manifest.runtime_store.path = 'state/harness/opencode.sqlite';
  mkdirSync(join(profile, 'state/harness'), { recursive: true });
  writeFileSync(join(profile, 'state/harness/manifest.json'), JSON.stringify(manifest));
  storage = await openIsolatedStorage({ profileRoot: profile, selection, migrations, expectedSchemaHash });
  model = await savedModel();
  target = await openSavedLearningTarget({ storage, model: async () => model, library: { query: async () => [] },
    harness: { root: profile, profileId: identity.profileId, storeId: identity.storeId, domainStoreId: 'synthetic-domain-store',
      domainPath: 'state/renulus.sqlite3', processGeneration: 'synthetic-process' } });
  await target.native.activateStores(); await target.native.activate('synthetic-policy-v1');
});
after(async () => {
  for (const close of cleanups.reverse()) await close();
  await target?.close(); await model?.close(); await storage?.close();
  assert.equal(dirname(root), resolve(tmpdir())); rmSync(root, { recursive: true, force: true });
});

/** A fresh RAM family whose volatile model is separate from the saved target's model. */
async function volatile(overrides = {}) {
  const volatileRoot = mkdtempSync(join(tmpdir(), 'renulus-bf04-volatile-'));
  const runtime = ManagedRuntime.make(TestLLM.testLayer()), client = await runtime.runPromise(TestLLM.Test);
  const host = await openVolatileHarness({ root: volatileRoot, profileId: identity.profileId, storeId: 'synthetic-volatile-' + Math.random().toString(16).slice(2),
    domainStoreId: 'synthetic-volatile-domain', domainPath: 'unused.sqlite', model: { providerId: 'synthetic', modelId: 'volatile', client,
      configuration: { model: 'synthetic/volatile', providers: { synthetic: { package: '@opencode/ai/providers/openai-compatible',
        settings: { baseURL: 'https://synthetic.invalid/v1' }, models: { volatile: { limit: { context: 128000, output: 4096 } } } } } } } });
  await host.activate('synthetic-bf04');
  const rootSession = await host.createSession({ operationId: 'temporary_' + Math.random().toString(16).slice(2), title: 'Temporary education' });
  const saved = overrides.saved ?? { importSession: d => target.native.importSession(d), exportSession: id => target.native.exportSession(id),
    removeSession: id => target.native.removeSession(id) };
  const family = createTemporaryFamily({ host, rootSessionId: rootSession.id, storage: overrides.storage ?? storage, saved, identity,
    async current() { const c = await storage.command({ type: 'study.context' }); return { contextEpoch: c.epoch, policyRevision: c.policyRevision }; },
    settle: async () => 'settled' });
  cleanups.push(async () => { await host.close({ timeoutMs: 10000 }); await runtime.dispose(); rmSync(volatileRoot, { recursive: true, force: true }); });
  return { host, family, client, volatileRoot, rootId: rootSession.id, push: (...r) => runtime.runPromise(client.push(...r)),
    requests: async () => (await runtime.runPromise(client.requests())).length, wait: n => runtime.runPromise(client.wait(n)) };
}
const answer = text => TestLLM.text(text, 'answer');
const key = name => 'synthetic-save-' + name;
const gate = () => { let release; const open = new Promise(resolve => { release = resolve; }); return { open, release }; };

test('Temporary exact history stays in RAM; Save activates the whole mapping once, then reopen reads and finds it without inference', { timeout: 120000 }, async () => {
  const f = await volatile();
  await f.push(answer('First synthetic answer ' + sentinel)); await f.push(answer('Second synthetic answer ' + sentinel));
  await f.family.send({ text: 'First temporary question ' + sentinel });
  // A normal terminal stream close is not an abnormal disconnect: the view stays open.
  assert.equal(f.family.status().state, 'open');
  await f.family.send({ text: 'Second temporary question ' + sentinel });
  const history = await f.family.range({ limit: 50, order: 'asc' });
  assert.equal(history.messages.filter(m => m.type === 'user').length, 2);
  assert.equal(holds(profile, sentinel), false, 'sentinel must be absent from canonical and native stores before Save');
  assert.deepEqual(files(f.volatileRoot), []);
  const threads = sql('SELECT count(*) AS n FROM learn_threads')[0].n;

  const saved = await f.family.save('Saved temporary AKI case', key('main'));
  assert.equal(saved.state, 'active'); assert.equal(f.family.status().state, 'saved');
  assert.equal(sql('SELECT count(*) AS n FROM learn_threads')[0].n, threads + 1);
  assert.deepEqual(sql("SELECT state FROM temporary_save_intents WHERE id=?", saved.id), [{ state: 'active' }]);
  assert.equal(sql('SELECT count(*) AS n FROM learn_harness_answers WHERE thread_id=? AND state=?', saved.threadId, 'completed')[0].n, 2);
  assert.equal(sql('SELECT count(*) AS n FROM learning_evidence WHERE entity_id=?', saved.threadId)[0].n, 0, 'saving never turns the exchange into a learner-memory source');
  assert.equal(holds(profile, sentinel), true, 'the promoted native graph is durable after Save');
  assert.deepEqual((await f.family.save('Saved temporary AKI case', key('main'))).id, saved.id);

  // Reopen the saved native host; the exact exchange is readable and findable. No inference occurs.
  await target.close();
  target = await openSavedLearningTarget({ storage, model: async () => model, library: { query: async () => [] },
    harness: { root: profile, profileId: identity.profileId, storeId: identity.storeId, domainStoreId: 'synthetic-domain-store',
      domainPath: 'state/renulus.sqlite3', processGeneration: 'synthetic-process-2' } });
  await target.native.activateStores(); await target.native.activate('synthetic-policy-v1');
  const page = await target.messages(saved.threadId, { limit: 50 });
  assert.deepEqual(page.items.map(m => m.role), ['user', 'assistant', 'user', 'assistant']);
  assert.ok(page.items.every(m => m.content.includes(sentinel)));
  const found = await target.find({ query: 'Second synthetic answer ' + sentinel, scope: { lifecycle: 'active', projectId: null } });
  assert.equal(found.items.length, 1); assert.equal(found.items[0].conversation.identity.id, saved.threadId);
  assert.equal(await model.count(), 0);

  // Save committed first: a later owner disconnect only detaches and returns the committed reference.
  const detached = await f.family.disconnect();
  assert.equal(detached.state, 'detached'); assert.equal(detached.saved.threadId, saved.threadId);
  assert.equal((await target.messages(saved.threadId, { limit: 50 })).items.length, 4);
});

test('Disconnect wins the serialized boundary mid-Save: no promotion, staging retired after settlement, nothing durable remains', { timeout: 120000 }, async () => {
  const entered = gate(), release = gate();
  const f = await volatile({ saved: { importSession: async d => { entered.release(); await release.open; return target.native.importSession(d); },
    exportSession: id => target.native.exportSession(id), removeSession: id => target.native.removeSession(id) } });
  const cancelled = sentinel + '_cancelled_save';
  await f.push(answer('Disconnected synthetic answer ' + cancelled));
  await f.family.send({ text: 'Disconnected temporary question ' + cancelled });
  const threads = sql('SELECT count(*) AS n FROM learn_threads')[0].n;
  const saving = f.family.save('Never promoted', key('cancel-first')); const outcome = saving.then(() => 'saved', error => error.code);
  await entered.open;
  const disconnecting = f.family.disconnect();
  release.release();
  assert.equal(await outcome, 'temporary_cancelled');
  assert.deepEqual(await disconnecting, { state: 'discarded' });
  assert.equal(sql('SELECT count(*) AS n FROM learn_threads')[0].n, threads);
  // Canonical files only: the native store's own freed SQLite pages are outside this lane's host surface.
  assert.equal(files(join(profile, 'state')).filter(file => /renulus\.sqlite3/.test(file)).some(file => readFileSync(file).includes(Buffer.from(cancelled))), false, 'retired canonical intent carries no content');
  const [row] = sql("SELECT id,state,plan_json FROM temporary_save_intents WHERE idempotency_key=?", key('cancel-first'));
  assert.equal(row.state, 'retired'); assert.equal(row.plan_json.includes('Never promoted'), false); assert.equal(row.plan_json.includes('exchanges'), false);
  await assert.rejects(target.native.exportSession(JSON.parse(row.plan_json).rootSessionId), { _tag: 'SessionNotFoundError' });
  assert.equal(sql("SELECT count(*) AS n FROM learn_harness_mappings WHERE session_id=?", JSON.parse(row.plan_json).rootSessionId)[0].n, 0);
  assert.throws(() => f.family.range(), { code: 'temporary_family_unavailable' });
  assert.deepEqual(files(f.volatileRoot), []);
});

test('Activation commits first while disconnect is in flight: the serialized boundary returns the committed reference', { timeout: 120000 }, async () => {
  const entered = gate(), release = gate();
  const held = { command: async command => {
    if (command.type === 'temporary.save.activate') { entered.release(); await release.open; }
    return storage.command(command);
  } };
  const f = await volatile({ storage: held });
  await f.push(answer('Activated synthetic answer ' + sentinel));
  await f.family.send({ text: 'Activated temporary question ' + sentinel });
  const saving = f.family.save('Promoted before disconnect', key('activate-first'));
  await entered.open;
  const disconnecting = f.family.disconnect();
  release.release();
  const saved = await saving, detached = await disconnecting;
  assert.equal(saved.state, 'active'); assert.equal(detached.state, 'detached'); assert.equal(detached.saved.threadId, saved.threadId);
  assert.equal(sql('SELECT count(*) AS n FROM learn_threads WHERE id=?', saved.threadId)[0].n, 1);
  assert.equal((await target.native.exportSession(saved.rootSessionId)).info.id, saved.rootSessionId);
});

test('A failed Save keeps the RAM family and never reports saved; the same key retries to one activation', { timeout: 120000 }, async () => {
  let failures = 1;
  const f = await volatile({ saved: { importSession: async d => {
    if (failures-- > 0) throw Object.assign(new Error('synthetic copy failure'), { code: 'synthetic_copy_failure' });
    return target.native.importSession(d);
  }, exportSession: id => target.native.exportSession(id), removeSession: id => target.native.removeSession(id) } });
  await f.push(answer('Retried synthetic answer ' + sentinel));
  await f.family.send({ text: 'Retried temporary question ' + sentinel });
  const threads = sql('SELECT count(*) AS n FROM learn_threads')[0].n;
  await assert.rejects(f.family.save('Retry me', key('retry')), { code: 'synthetic_copy_failure' });
  assert.equal(f.family.status().state, 'save-failed'); assert.equal(f.family.status().saved, null);
  assert.equal(sql('SELECT count(*) AS n FROM learn_threads')[0].n, threads);
  assert.ok((await f.family.range({ limit: 10, order: 'asc' })).messages.filter(m => m.type === 'user' || m.type === 'assistant').length === 2, 'RAM history is retained');
  await assert.rejects(f.family.save('Different title', key('retry')), { code: 'idempotency_conflict' });
  const saved = await f.family.save('Retry me', key('retry'));
  assert.equal(saved.state, 'active'); assert.equal(sql('SELECT count(*) AS n FROM learn_threads')[0].n, threads + 1);
  assert.equal(sql('SELECT count(*) AS n FROM temporary_save_intents WHERE idempotency_key=?', key('retry'))[0].n, 1);
});

test('Abnormal owner loss with live model work cancels, settles and discards; nothing reaches disk', { timeout: 120000 }, async () => {
  const f = await volatile(); const never = gate(), unsaved = sentinel + '_never_saved';
  await f.push(Stream.fromEffect(Effect.promise(() => never.open)).pipe(Stream.flatMap(() => Stream.fromIterable(answer('Never delivered ' + unsaved)))));
  const sending = f.family.send({ text: 'In-flight temporary question ' + unsaved }).then(() => 'settled', () => 'settled');
  await f.wait(1);
  assert.deepEqual(await f.family.disconnect(), { state: 'discarded' });
  assert.equal(await sending, 'settled', 'the live send is cancelled and settled, never left running');
  assert.throws(() => f.family.range(), { code: 'temporary_family_unavailable' });
  assert.equal(holds(profile, unsaved), false); assert.deepEqual(files(f.volatileRoot), []);
  never.release();
});

test('Restart reconciliation removes an orphan staged graph and its canonical intent without reconstructing temporary input', { timeout: 120000 }, async () => {
  const f = await volatile();
  await f.push(answer('Orphan synthetic answer ' + sentinel));
  await f.family.send({ text: 'Orphan temporary question ' + sentinel });
  // A crash after canonical intent + native copy, before activation.
  const graph = await exportVolatileFamily(f.host, f.rootId);
  const { graph: staged } = remapVolatileFamily(graph, { ...identity, promotionId: 'promotion_orphan' });
  const plan = { id: 'promotion_orphan', threadId: 'thread_orphan', title: 'Orphan', ...identity, exchanges: [], rootSessionId: staged[0].info.id,
    sessionIds: staged.map(s => s.info.id), cancellationEpoch: 0, contextEpoch: (await storage.command({ type: 'study.context' })).epoch,
    policyRevision: (await storage.command({ type: 'study.context' })).policyRevision, idempotencyKey: key('orphan') };
  await storage.command({ type: 'temporary.save.begin', plan });
  for (const data of staged) await target.native.importSession(data);
  assert.equal((await target.native.exportSession(plan.rootSessionId)).info.id, plan.rootSessionId);
  // The restarted process knows nothing about the RAM family; only canonical intent remains.
  await reconcileTemporarySaves(storage, target.native);
  await assert.rejects(target.native.exportSession(plan.rootSessionId), { _tag: 'SessionNotFoundError' });
  assert.deepEqual(await storage.command({ type: 'temporary.save.pending' }), []);
  assert.deepEqual(sql('SELECT state FROM temporary_save_intents WHERE id=?', plan.id), [{ state: 'retired' }]);
  assert.equal(sql('SELECT count(*) AS n FROM learn_threads WHERE id=?', plan.threadId)[0].n, 0);
  await f.family.disconnect();
});
