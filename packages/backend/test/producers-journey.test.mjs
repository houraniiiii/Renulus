// SPDX-License-Identifier: MIT
import '../../harness/test/owned-environment.mjs';
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { spawnSync } from 'node:child_process';
import { DatabaseSync } from 'node:sqlite';
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { ManagedRuntime } from 'effect';
import { TestLLM } from '@opencode/ai/testing';
import { openIsolatedStorage, loadMigrationInventory, MARKER, SELECTOR } from '../src/storage/index.ts';
import { inventory } from '../src/storage/schema.ts';
import { openConnectedTarget } from '../src/host/composition.ts';
import { defaultConfiguration } from '../src/dispatch/policy.ts';
import { syntheticEvidence, scriptedTransport } from './support/synthetic-route.mjs';

const repository = fileURLToPath(new URL('../../..', import.meta.url));
const python = 'C:/Renulus/dev/python/Scripts/python.exe';
const helpersRoot = 'C:/Renulus/dev/helper-assets';
const MODEL = 'gpt-6.1-sol', CONNECTION = { provider: 'codex', credential_reference: 'synthetic-unused', credential_revision: 0, selected_model: MODEL };

/** Synthetic profile with one pending Updates entry (same shape as study-updates-target.test.mjs). */
function fixture() {
  const root = mkdtempSync(path.join(tmpdir(), 'renulus-producers-'));
  const script = `
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'runtime'))
from renulus.server import create_app
s=create_app(Path(sys.argv[2])).state.services
with s.db.transaction() as c:
 c.execute("INSERT OR REPLACE INTO harness_store_identity VALUES(1,'synthetic-profile','synthetic-domain',1,'4b6fea2875e4f2e3e8a8fee181803e54f7056845')")
 c.execute("INSERT OR IGNORE INTO update_source_checks(source_id,title,url,snapshot_status) VALUES(?,?,?,?)",('S99','SYNTHETIC official source','https://synthetic.invalid/source','Synthetic'))
 c.execute("INSERT INTO update_entries VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",('synthetic_update','S99','synthetic:entry','SYNTHETIC correction','https://synthetic.invalid/article','publication-change',None,'2026-10-27T00:00:00Z',None,None,'pending','Inspect','[]',json.dumps({'canonical_url':'https://synthetic.invalid/article'}),None))
print(str(s.paths.database))
`;
  const environment = Object.fromEntries(['SystemRoot', 'WINDIR', 'TEMP', 'TMP'].filter(k => process.env[k]).map(k => [k, process.env[k]]));
  environment.PATH = path.dirname(python);
  const result = spawnSync(python, ['-I', '-X', 'utf8', '-c', script, repository, root], { env: environment, encoding: 'utf8', timeout: 60000 });
  assert.equal(result.status, 0, result.stderr || result.error?.message);
  const selection = { contract: 'renulus-storage-selector/1', isolation: 'synthetic', profileId: 'synthetic-profile', generation: 1,
    authorityEpoch: 1, writer: 'ts', state: 'active', ownerId: 'synthetic-producers-owner', database: 'state/renulus.sqlite3' };
  writeFileSync(path.join(root, MARKER), JSON.stringify({ contract: 'renulus-synthetic-storage/1', profileId: selection.profileId }));
  writeFileSync(path.join(root, SELECTOR), JSON.stringify(selection));
  mkdirSync(path.join(root, 'state/harness'), { recursive: true });
  const manifest = JSON.parse(readFileSync(path.join(repository, 'packages/contracts/fixtures/harness/paired-store-prepared.json'), 'utf8'));
  manifest.profile_id = selection.profileId; manifest.domain_store.store_id = 'synthetic-domain';
  manifest.domain_store.path = selection.database; manifest.runtime_store.store_id = 'synthetic-runtime'; manifest.runtime_store.path = 'state/harness/opencode.sqlite';
  writeFileSync(path.join(root, 'state/harness/manifest.json'), JSON.stringify(manifest));
  const migrations = loadMigrationInventory(repository), db = new DatabaseSync(result.stdout.trim());
  const expectedSchemaHash = inventory(db, migrations).schemaHash; db.close();
  return { root, writer: { profileRoot: root, selection, migrations, expectedSchemaHash },
    identity: { profile_id: selection.profileId, domain_store_id: 'synthetic-domain', runtime_store_id: 'synthetic-runtime', authority_epoch: 1, process_generation: 'synthetic-producers' } };
}
const savedModel = async () => {
  const runtime = ManagedRuntime.make(TestLLM.testLayer()), client = await runtime.runPromise(TestLLM.Test);
  return { runtime, requests: () => runtime.runPromise(client.requests()), model: { providerId: 'synthetic', modelId: 'scripted', client,
    configuration: { model: 'synthetic/scripted', providers: { synthetic: { package: '@opencode/ai/providers/openai-compatible',
      settings: { baseURL: 'https://synthetic.invalid/v1' }, models: { scripted: { limit: { context: 128000, output: 4096 } } } } } } } };
};
const practice = { items: Array.from({ length: 5 }, (_, i) => ({ stem: 'SYNTHETIC ' + ['AKI', 'CKD', 'glomerular disease', 'dialysis', 'transplant'][i] + ' question',
  options: [{ id: 'a', text: 'Synthetic option A' }, { id: 'b', text: 'Synthetic option B' }], correct_option_id: 'a', explanation: 'Synthetic teaching rationale.', hint: null, source_indices: [] })) };
const bundle = Object.fromEntries(['explain', 'case', 'practice'].map(k => [k, Array.from({ length: 5 }, (_, i) => `SYNTHETIC ${k} suggestion ${i}`)]));
const signal = () => new AbortController().signal;

test('standalone producers run through the connected target, native dispatch and the canonical dispatch tables', { timeout: 240000 }, async () => {
  const f = fixture(), m = await savedModel(), storage = await openIsolatedStorage(f.writer);
  const { evidence, calls } = syntheticEvidence(CONNECTION, MODEL), scripted = scriptedTransport(MODEL);
  const connected = await openConnectedTarget({ profileRoot: f.root, storage, identity: f.identity, availableModels: [MODEL], evidence: [evidence],
    testing: { model: async () => m.model, transport: scripted.transport },
    resources: { python, sourceRoot: repository, helpers: { helpers_root: helpersRoot, source_root: repository, cache_root: path.join(f.root, 'cache') },
      derived: { root: path.join(f.root, 'derived'), namespace: 'synthetic-producers', library_tombstones: [], memory_tombstones: [] },
      broker: { profile_root: path.join(f.root, 'broker'), state_root: path.join(f.root, 'broker/state') } } });
  try {
    const registry = await connected.inspect();
    await connected.configuration.activate(defaultConfiguration(CONNECTION, registry.registry_hash));

    // (a) generated practice batch of 5 -> immutable Ready saved version.
    scripted.push(JSON.stringify(practice));
    const job = await connected.assessment.create({ title: 'SYNTHETIC saved practice', count: 5, topic_id: null, inputs: [], source_refs: [], idempotencyKey: 'producers-generated' });
    const published = await connected.assessment.settled(job.id);
    assert.equal(published.state, 'published'); assert.equal(published.accepted_count, 5);
    const setup = await storage.command({ type: 'assessment.tests.setup', versionId: published.published_version_id });
    assert.equal(setup.version.status, 'ready'); assert.equal(setup.version.origin, 'generated'); assert.equal(setup.version.item_count, 5);

    // (b) personal-import refinement keeps the original and publishes nothing by itself.
    const text = '1. SYNTHETIC unfamiliar question\na. Alpha option\nb. Beta option\nAnswer: a';
    const imported = await storage.command({ type: 'assessment.import.create', title: 'SYNTHETIC refined import',
      original: { kind: 'paste', text, terms: 'SYNTHETIC owner permission', permission_confirmed: true }, idempotencyKey: 'producers-import' });
    const at = s => ({ start: text.indexOf(s), end: text.indexOf(s) + s.length });
    scripted.push(JSON.stringify({ candidates: [{ span: { start: 0, end: text.length }, stem_span: at('SYNTHETIC unfamiliar question'), stem: 'SYNTHETIC unfamiliar question',
      options: [{ id: 'a', text: 'Alpha option', span: at('Alpha option') }, { id: 'b', text: 'Beta option', span: at('Beta option') }], explanation: '', explanation_span: null }] }));
    const normalized = await connected.assessment.normalize(imported.id, imported.revision, signal());
    assert.equal(normalized.candidates[0].stem, 'SYNTHETIC unfamiliar question'); assert.equal(normalized.result, null);
    assert.equal((await storage.command({ type: 'assessment.import.get', importId: imported.id, original: true })).text, text);

    // (c) result narrative sees only the committed result and cannot change scores.
    const test = await storage.command({ type: 'assessment.attempts.start', versionId: published.published_version_id, mode: 'test',
      timing: { kind: 'untimed', duration_seconds: null }, idempotencyKey: 'producers-test' });
    const scored = await storage.command({ type: 'assessment.attempts.submit', attemptId: test.id, expectedRevision: 0, latestDraft: null, idempotencyKey: 'producers-submit' });
    scripted.push('SYNTHETIC narrative of the committed result.');
    const narrated = await connected.assessment.narrative(test.id, signal());
    assert.equal(narrated.text, 'SYNTHETIC narrative of the committed result.');
    assert.ok(!JSON.stringify(scripted.sent.at(-1).request).includes('correct_option_ids'));
    assert.deepEqual((await storage.command({ type: 'assessment.attempts.get', attemptId: test.id })).result, scored.result);

    // (d) Home suggestions: three categories x five.
    scripted.push(JSON.stringify(bundle));
    const home = await connected.study.refresh();
    assert.deepEqual((await connected.study.settled(home.job_id)).suggestions, bundle);

    // (e) Updates digest keeps provenance and marks nothing reviewed or current.
    const before = await storage.command({ type: 'updates.entry', id: 'synthetic_update' });
    scripted.push('SYNTHETIC digest of dated update entries.');
    const digest = await connected.updates.digest(20, signal());
    assert.equal(digest.text, 'SYNTHETIC digest of dated update entries.');
    assert.deepEqual(digest.entries, [{ id: 'synthetic_update', url: 'https://synthetic.invalid/article', review_state: 'pending' }]);
    const after = await storage.command({ type: 'updates.entry', id: 'synthetic_update' });
    assert.equal(after.review_state, 'pending'); assert.equal(after.revision, before.revision);

    assert.equal(scripted.sent.length, 5); assert.equal(calls.counted, 5); assert.equal((await m.requests()).length, 0);
  } finally { await connected.close(); await storage.close(); await m.runtime.dispose(); }

  // Every model call was one admitted, confirmed attempt of a role-bounded run in the canonical dispatch tables.
  const db = new DatabaseSync(path.join(f.root, 'state/renulus.sqlite3'), { readOnly: true });
  try {
    const runs = db.prepare(`SELECT r.purpose, r.dispatch_limit, r.state, COUNT(a.permit_id) AS attempts, MIN(a.state) AS attempt_state
      FROM harness_configuration_runs r LEFT JOIN harness_configuration_attempts a ON a.run_id = r.run_id GROUP BY r.run_id ORDER BY r.created_at, r.rowid`).all()
      .map(r => ({ ...r }));
    assert.deepEqual(runs, [
      { purpose: 'generated-practice', dispatch_limit: 6, state: 'settled', attempts: 1, attempt_state: 'confirmed' },
      { purpose: 'test-import', dispatch_limit: 6, state: 'settled', attempts: 1, attempt_state: 'confirmed' },
      { purpose: 'test-result-narrative', dispatch_limit: 1, state: 'settled', attempts: 1, attempt_state: 'confirmed' },
      { purpose: 'daily_suggestions', dispatch_limit: 2, state: 'settled', attempts: 1, attempt_state: 'confirmed' },
      { purpose: 'updates-digest', dispatch_limit: 2, state: 'settled', attempts: 1, attempt_state: 'confirmed' },
    ]);
    assert.equal(db.prepare('SELECT COUNT(*) AS n FROM harness_configuration_attempts').get().n, 5);
  } finally { db.close(); }
});

test('a generation job left running by a killed host reopens, keeps its uncertain debit and resumes only the missing batch', { timeout: 240000 }, async () => {
  const f = fixture(), m = await savedModel(), { evidence, calls } = syntheticEvidence(CONNECTION, MODEL), scripted = scriptedTransport(MODEL);
  const open = async (storage, first) => {
    const connected = await openConnectedTarget({ profileRoot: f.root, storage, identity: f.identity, availableModels: [MODEL], evidence: [evidence],
      testing: { model: async () => m.model, transport: scripted.transport },
      resources: { python, sourceRoot: repository, helpers: { helpers_root: helpersRoot, source_root: repository, cache_root: path.join(f.root, 'cache') },
        derived: { root: path.join(f.root, 'derived'), namespace: 'synthetic-producers', library_tombstones: [], memory_tombstones: [] },
        broker: { profile_root: path.join(f.root, 'broker'), state_root: path.join(f.root, 'broker/state') } } });
    if (first) await connected.configuration.activate(defaultConfiguration(CONNECTION, (await connected.inspect()).registry_hash));
    return connected;
  };
  const second = { items: practice.items.map((q, i) => ({ ...q, stem: 'SYNTHETIC second batch ' + ['renal tubular acidosis', 'nephrotic syndrome', 'hyponatraemia', 'hyperkalaemia', 'lupus nephritis'][i] })) };
  let job, storage = await openIsolatedStorage(f.writer), connected = await open(storage, true);
  try {
    // First batch is answered; the second call is the one the host dies in.
    scripted.push(JSON.stringify(practice));
    job = await connected.assessment.create({ title: 'SYNTHETIC interrupted ten', count: 10, topic_id: null, inputs: [], source_refs: [], idempotencyKey: 'producers-interrupted' });
    assert.equal((await connected.assessment.settled(job.id)).validated_count, 5);
  } finally { await connected.close(); await storage.close(); }
  // The state a killed host leaves: job still running, the last model call dispatched but never answered.
  const killed = new DatabaseSync(path.join(f.root, 'state/renulus.sqlite3'));
  try {
    killed.prepare("UPDATE assessment_test_jobs SET state='running',error_code=NULL WHERE id=?").run(job.id);
    const run = killed.prepare("SELECT run_id FROM harness_configuration_runs WHERE purpose='generated-practice' ORDER BY created_at DESC, rowid DESC LIMIT 1").get().run_id;
    killed.prepare("UPDATE harness_configuration_runs SET state='active' WHERE run_id=?").run(run);
    killed.prepare("UPDATE harness_configuration_attempts SET state='dispatched',result_reference=NULL,failure_code=NULL WHERE run_id=?").run(run);
  } finally { killed.close(); }

  storage = await openIsolatedStorage(f.writer); connected = await open(storage, false);
  const sentBefore = scripted.sent.length;
  try {
    // The restart recovers the persisted configuration; the killed host's debris must not hold it.
    assert.deepEqual({ ...connected.status(), worker: undefined }, { admission: 'open', recovery_error: null, worker: undefined });
    const view = await connected.assessment.read(job.id);
    assert.equal(view.state, 'running'); assert.equal(view.validated_count, 5);
    scripted.push(JSON.stringify(second));
    await connected.assessment.resume(job.id);
    const done = await connected.assessment.settled(job.id);
    assert.equal(done.state, 'published'); assert.equal(done.accepted_count, 10);
    assert.equal(scripted.sent.length - sentBefore, 1, 'only the missing batch is sent');
    assert.deepEqual(done.checkpoint.batches[0].map(q => q.stem), practice.items.map(q => q.stem), 'the retained first batch is not regenerated');
    assert.equal((await storage.command({ type: 'assessment.tests.setup', versionId: done.published_version_id })).version.item_count, 10);
    assert.equal(new Set(done.checkpoint.batches.flat().map(q => q.stem)).size, 10, 'no item is published twice');
  } finally { await connected.close(); await storage.close(); await m.runtime.dispose(); }
  const db = new DatabaseSync(path.join(f.root, 'state/renulus.sqlite3'), { readOnly: true });
  try {
    const attempts = db.prepare("SELECT r.state AS run, a.state, a.failure_code FROM harness_configuration_attempts a JOIN harness_configuration_runs r USING(run_id) WHERE r.purpose='generated-practice' ORDER BY a.created_at, a.rowid").all().map(r => ({ ...r }));
    assert.deepEqual(attempts, [{ run: 'settled', state: 'confirmed', failure_code: null }, { run: 'settled', state: 'uncertain', failure_code: 'broker_lost' }, { run: 'settled', state: 'confirmed', failure_code: null }]);
  } finally { db.close(); }
});
