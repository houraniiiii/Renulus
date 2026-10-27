// SPDX-License-Identifier: MIT
import '../../harness/test/owned-environment.mjs';
import assert from 'node:assert/strict';
import { test, after } from 'node:test';
import { spawnSync } from 'node:child_process';
import { DatabaseSync } from 'node:sqlite';
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { basename, dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Effect, ManagedRuntime } from 'effect';
import { TestLLM } from '@opencode/ai/testing';
import { openSavedLearningTarget } from '../src/host/learning.ts';
import { createLearningCallbacks } from '../src/domain/learning/callbacks.ts';
import { createLearningHistory } from '../src/domain/learning/history.ts';
import { executeLearning } from '../src/storage/learning.ts';
import { openIsolatedStorage } from '../src/storage/index.ts';
import { acquireOwner, MARKER, SELECTOR } from '../src/storage/ownership.ts';
import { canonical, digest, inventory, loadMigrationInventory } from '../src/storage/schema.ts';
import { checkMemoryDependency } from '../src/storage/memory.ts';

const repository = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const python = 'C:/Renulus/dev/python/Scripts/python.exe';
const root = mkdtempSync(join(tmpdir(), 'renulus-learning-bf02-'));
const identity = { profileId: 'synthetic-profile', storeId: 'synthetic-store', generation: 'synthetic-process' };
const cleanups = [];
const DOC = 'doc_' + '1'.repeat(32), REV = 'rev_' + '2'.repeat(32), PASSAGE = 'passage_' + '3'.repeat(32);
const phrase = 'SYNTHETIC native-only AKI [literal.*%_needle]';
let serial = 0;

function fixture() {
  assert.equal(process.versions.node, '26.4.0');
  // Other lanes may finish migrations between cases in this shared checkout.
  // Pin each synthetic generation before Python preparation; changes during
  // preparation still fail the exact writer/inventory checks below.
  const migrations = loadMigrationInventory(repository);
  const profile = join(root, 'profile-' + (++serial));
  const script = `
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'runtime'))
from renulus.server import create_app
from renulus.learn.conversation_models import NewConversation
s=create_app(Path(sys.argv[2])).state.services
threads=[s.registry['conversations'].create(NewConversation(kind='learning',title='SYNTHETIC '+topic),'bf02-create-'+str(i)) for i,topic in enumerate(['AKI','CKD','Transplant','Glomerular','Electrolytes','Dialysis'])]
with s.db.transaction() as c:
    c.execute("INSERT OR REPLACE INTO harness_store_identity VALUES(1,'synthetic-profile','synthetic-domain-store',1,'4b6fea2875e4f2e3e8a8fee181803e54f7056845')")
    c.execute("INSERT INTO study_projects VALUES('project_a','SYNTHETIC project','active',1,'2026-10-27T00:00:00Z','2026-10-27T00:00:00Z')")
    rights={key:True for key in ['display','cache','index','embedding','model_input','derivation']}
    rights.update(licence='CC-BY-4.0',permission_reference='SYNTHETIC',attribution='Synthetic test author')
    metadata={'source_id':'SYNTHETIC','publication_status':'final','content_reviewed':True,'latest_final_verified':True,'excluded_pages':[]}
    c.execute("INSERT INTO knowledge_documents VALUES(?,?,?,'personal-library',NULL,0,?,?,NULL,?,?)",(sys.argv[3],'SYNTHETIC Library','SYNTHETIC',sys.argv[4],sys.argv[4],'2026-10-27T00:00:00Z','2026-10-27T00:00:00Z'))
    c.execute("INSERT INTO knowledge_revisions VALUES(?,?,1,'ready',?,'text/plain',40,NULL,?,?,NULL,NULL,NULL,?,?)",(sys.argv[4],sys.argv[3],'1'*64,json.dumps(metadata),json.dumps(rights),'2026-10-27T00:00:00Z','2026-10-27T00:00:00Z'))
    c.execute("INSERT INTO knowledge_passages VALUES(?,?,0,?,?,?,'[]')",(sys.argv[5],sys.argv[4],'SYNTHETIC canonical Library AKI passage','SYNTHETIC canonical Library AKI passage',json.dumps([{'page':1,'char_span':[0,40]}])))
print(json.dumps({'database':str(s.paths.database),'threads':threads}))
`;
  const environment = Object.fromEntries(['SystemRoot', 'WINDIR', 'TEMP', 'TMP'].filter(k => process.env[k]).map(k => [k, process.env[k]]));
  environment.PATH = dirname(python);
  const result = spawnSync(python, ['-I', '-X', 'utf8', '-c', script, repository, profile, DOC, REV, PASSAGE], { encoding: 'utf8', env: environment, timeout: 60000 });
  assert.equal(result.status, 0, result.stderr || result.error?.message);
  const prepared = JSON.parse(result.stdout);
  const selection = { contract: 'renulus-storage-selector/1', isolation: 'synthetic', profileId: identity.profileId,
    generation: 1, authorityEpoch: 1, writer: 'ts', state: 'active', ownerId: 'synthetic-bf02-owner', database: 'state/renulus.sqlite3' };
  writeFileSync(join(profile, MARKER), JSON.stringify({ contract: 'renulus-synthetic-storage/1', profileId: identity.profileId }));
  writeFileSync(join(profile, SELECTOR), JSON.stringify(selection));
  let owner, db;
  function open() {
    owner = acquireOwner({ profileRoot: profile, selection, migrations, expectedSchemaHash: '' });
    db = new DatabaseSync(prepared.database, { enableForeignKeyConstraints: true });
    db.exec('PRAGMA secure_delete=ON; PRAGMA journal_mode=WAL;');
  }
  open();
  const schemaHash = inventory(db, migrations).schemaHash;
  const manifest = JSON.parse(readFileSync(join(repository, 'packages/contracts/fixtures/harness/paired-store-prepared.json'), 'utf8'));
  manifest.domain_store.path = 'state/renulus.sqlite3'; manifest.runtime_store.store_id = identity.storeId;
  manifest.runtime_store.path = 'state/harness/opencode.sqlite';
  mkdirSync(join(profile, 'state/harness'), { recursive: true });
  writeFileSync(join(profile, 'state/harness/manifest.json'), JSON.stringify(manifest));
  // Test-local integration adapter: the real single-owner local functions, with no await
  // in a transaction. The connected worker test below uses the parent's integrated worker.
  const command = async c => {
    owner.check(); db.exec('BEGIN IMMEDIATE');
    try { const r = executeLearning(db, c); assert.equal(typeof r?.then, 'undefined'); owner.check(); db.exec('COMMIT'); return r; }
    catch (e) { db.exec('ROLLBACK'); throw e; }
  };
  const storage = { command };
  const harness = { root: profile, profileId: identity.profileId, storeId: identity.storeId,
    domainStoreId: 'synthetic-domain-store', domainPath: 'state/renulus.sqlite3', processGeneration: identity.generation };
  const close = () => { if (db) { db.close(); db = undefined; owner.release(); } };
  cleanups.push(close);
  return { profile, database: prepared.database, harness, storage, threads: prepared.threads, db: () => db, close,
    writerOptions: { profileRoot: profile, selection, migrations, expectedSchemaHash: schemaHash },
    reopen() { close(); open(); assert.equal(inventory(db, migrations).schemaHash, schemaHash); },
    input(index = 0, overrides = {}) { return { threadId: prepared.threads[index].identity.id, expectedRevision: 1,
      expectedDraftRevision: 0, text: 'Explain SYNTHETIC AKI.', idempotencyKey: 'synthetic-send-' + serial + '-' + index, ...overrides }; },
    begin(index = 0, overrides = {}) { return command({ type: 'learning.begin', ...this.input(index, overrides), runId: 'synthetic_run_' + serial + '_' + index, attemptId: '1', identity }); },
  };
}
async function model(sequence) {
  const runtime = ManagedRuntime.make(TestLLM.testLayer()), client = await runtime.runPromise(TestLLM.Test);
  for (const item of sequence) await runtime.runPromise(client.push(typeof item === 'string' ? TestLLM.text(item, 'answer') : TestLLM.tool(item.id, item.name, item.input)));
  return { providerId: 'synthetic', modelId: 'counted-learning', client,
    configuration: { model: 'synthetic/counted-learning', providers: { synthetic: { package: '@opencode/ai/providers/openai-compatible',
      settings: { baseURL: 'https://synthetic.invalid/v1', apiKey: 'synthetic-unused' }, models: { 'counted-learning': { limit: { context: 128000, output: 4096 } } } } } },
    count: async () => (await runtime.runPromise(client.requests())).length,
    respond: text => runtime.runPromise(client.push(TestLLM.text(text, 'answer'))), close: () => runtime.dispose() };
}
const bridge = { async query(input) { assert.deepEqual(input.revisionIds, [REV]); return [{ passage_id: PASSAGE, revision_id: REV }]; } };
const scope = { lifecycle: 'active', projectId: null };
async function findAll(target, input) {
  const items = []; let cursor;
  for (let i = 0; i < 40; i++) {
    const page = await target.find({ ...input, ...(cursor ? { cursor } : {}) }); items.push(...page.items);
    cursor = page.next_cursor; if (!cursor) return { items };
  }
  assert.fail('bounded synthetic Finder must finish');
}
after(() => {
  cleanups.forEach(close => close());
  assert.equal(dirname(root), resolve(tmpdir())); assert.match(basename(root), /^renulus-learning-bf02-/);
  rmSync(root, { recursive: true, force: true });
});

test('Python schema2 → native retrieve/citation lifecycle → canonical reference receipt → native-only literal Finder after reopen, without inference', { timeout: 60000 }, async () => {
  const f = fixture();
  const m = await model([{ id: 'retrieve-native', name: 'renulus_library_retrieve', input: { query: 'AKI', limit: 1 } },
    { id: 'citation-native', name: 'renulus_library_citation', input: { document_id: DOC, document_revision: REV, passage_id: PASSAGE, page: 1 } }, phrase]);
  let target;
  try {
    target = await openSavedLearningTarget({ storage: f.storage, harness: f.harness, model: async () => m, library: bridge });
    await target.native.activateStores(); await target.native.activate('synthetic-policy-v1');
    const sent = await target.send(f.input());
    assert.equal(sent.state, 'completed'); assert.equal(sent.replayed, false); assert.equal(await m.count(), 3);
    const ref = sent.answer_reference;
    assert.equal(ref.message_ids.length, 3); assert.equal(ref.citations[0].revision_id, REV); assert.equal(ref.citations[0].passage_id, PASSAGE);
    assert.equal(ref.dependencies[0].target.type, 'library_revision');
    const history = await target.range(f.input().threadId);
    const tools = history.messages.flatMap(message => message.content ?? []).filter(part => part.type === 'tool');
    assert.deepEqual(tools.map(t => [t.name, t.state.status]), [['renulus_library_retrieve', 'completed'], ['renulus_library_citation', 'completed']]);
    const retrieved = JSON.parse(tools[0].state.content.filter(p => p.type === 'text').map(p => p.text).join(''));
    assert.equal(retrieved.passages[0].text, 'SYNTHETIC canonical Library AKI passage');
    assert.equal(f.db().prepare('SELECT count(*) AS n FROM learn_messages').get().n, 0);
    assert.deepEqual({ ...f.db().prepare('SELECT draft_text,draft_revision FROM learn_conversations WHERE thread_id=?').get(f.input().threadId) }, { draft_text: '', draft_revision: 1 });
    for (const table of ['conversation_commands', 'learn_harness_answers', 'learning_evidence', 'memory_answer_lineage']) {
      assert.equal(JSON.stringify(f.db().prepare('SELECT * FROM ' + table).all()).includes(phrase), false, table + ' must contain references only');
    }
    const replayed = await target.send(f.input());
    assert.equal(replayed.replayed, true); assert.equal(replayed.run_id, sent.run_id); assert.equal(await m.count(), 3);
    await assert.rejects(target.send(f.input(0, { text: 'different' })), { code: 'idempotency_conflict' });
    await m.respond('SYNTHETIC follow-up on the same Library evidence.');
    const followup = await target.send(f.input(0, { expectedRevision: sent.conversation.revision, expectedDraftRevision: 1,
      idempotencyKey: 'synthetic-followup', text: 'Give a SYNTHETIC follow-up.' }));
    assert.equal(followup.state, 'completed'); assert.equal(await m.count(), 4);
    assert.ok(followup.answer_reference.inputs.some(i => i.dependency.target.id === 'learn-answer:' + sent.run_id));
    assert.ok(followup.answer_reference.dependencies.some(d => d.target.id === REV));
    await target.close(); f.reopen();
    target = await openSavedLearningTarget({ storage: f.storage, harness: f.harness, model: async () => m, library: bridge });
    const found = await findAll(target, { query: '[literal.*%_needle]', scope });
    assert.equal(found.items.length, 1); assert.ok(ref.message_ids.includes(found.items[0].message_id));
    assert.equal(found.items[0].snippet, phrase); assert.equal(await m.count(), 4);
    assert.equal((await findAll(target, { query: 'literalXYZ', scope })).items.length, 0);
    await target.native.activate('synthetic-policy-v1');
    const archived = await target.change({ type: 'learning.lifecycle', threadId: f.input().threadId,
      expectedRevision: followup.conversation.revision, lifecycle: 'archived', idempotencyKey: 'synthetic-archive' });
    assert.equal((await findAll(target, { query: phrase, scope })).items.length, 0);
    assert.equal((await findAll(target, { query: phrase, scope: { ...scope, lifecycle: 'archived' } })).items.length, 1);
    const unarchived = await target.change({ type: 'learning.lifecycle', threadId: f.input().threadId,
      expectedRevision: archived.revision, lifecycle: 'active', idempotencyKey: 'synthetic-unarchive' });
    const linked = await target.change({ type: 'learning.project', threadId: f.input().threadId, expectedRevision: unarchived.revision,
      projectId: 'project_a', expectedProjectRevision: 1, idempotencyKey: 'synthetic-link' });
    assert.equal((await findAll(target, { query: phrase, scope: { ...scope, projectId: 'project_a' } })).items.length, 1);
    const unlinked = await target.change({ type: 'learning.project', threadId: f.input().threadId, expectedRevision: linked.revision,
      projectId: null, expectedProjectRevision: null, idempotencyKey: 'synthetic-unlink' });
    assert.equal((await findAll(target, { query: phrase, scope: { ...scope, projectId: 'project_a' } })).items.length, 0);
    await target.delete({ type: 'learning.delete', threadId: f.input().threadId, expectedRevision: unlinked.revision, idempotencyKey: 'synthetic-delete' });
    assert.equal((await findAll(target, { query: phrase, scope: { ...scope, lifecycle: 'all' } })).items.length, 0);
    assert.equal(f.db().prepare("SELECT count(*) AS n FROM learn_harness_purges WHERE state='pending'").get().n, 0);
    await assert.rejects(target.send(f.input()), { code: 'command_terminal_unavailable' });
    assert.equal(await m.count(), 4);
  } finally { await target?.close(); await m.close(); f.close(); }
});

test('native Library worker settlement cannot return or publish after Stop or canonical deletion', { timeout: 60000 }, async () => {
  for (const action of ['cancel', 'delete']) {
    const f = fixture(), m = await model([{ id: 'delayed-read', name: 'renulus_library_retrieve', input: { query: 'AKI', limit: 1 } }, 'SYNTHETIC late answer']);
    let release, entered;
    const started = new Promise(resolve => { entered = resolve; });
    const delayed = { async query() { entered(); await new Promise(resolve => { release = resolve; }); return [{ passage_id: PASSAGE, revision_id: REV }]; } };
    const target = await openSavedLearningTarget({ storage: f.storage, harness: f.harness, model: async () => m, library: delayed });
    try {
      await target.native.activateStores(); await target.native.activate('synthetic-policy-v1');
      const pending = target.send(f.input()); const terminal = pending.catch(e => e);
      await started;
      const runId = f.db().prepare('SELECT run_id FROM learn_harness_answers').get().run_id;
      let settled = false;
      const command = action === 'cancel' ? target.cancel(runId) : target.delete({ type: 'learning.delete', threadId: f.input().threadId,
        expectedRevision: 2, idempotencyKey: 'synthetic-delete-race' });
      const closing = command.then(() => { settled = true; });
      await new Promise(resolve => setImmediate(resolve));
      assert.equal(settled, false, 'real native tool/worker settlement remains owned');
      release(); await closing;
      assert.ok((await terminal) instanceof Error);
      assert.equal(f.db().prepare("SELECT count(*) AS n FROM learn_harness_answers WHERE state='completed'").get().n, 0);
      assert.equal(f.db().prepare("SELECT count(*) AS n FROM learning_evidence WHERE kind='study-answer'").get().n, 0);
      assert.equal((await findAll(target, { query: 'SYNTHETIC late answer', scope: { ...scope, lifecycle: 'all' } })).items.length, 0);
      if (action === 'cancel') {
        const replay = await target.send(f.input()); assert.equal(replay.state, 'cancelled'); assert.equal(replay.replayed, true);
        assert.equal(f.db().prepare('SELECT draft_text FROM learn_conversations WHERE thread_id=?').get(f.input().threadId).draft_text, f.input().text);
      }
    } finally { release?.(); await target.close(); await m.close(); f.close(); }
  }
});

test('native lookup rechecks Archive/project/Test/deletion after the owning-host read; reserved text is never Finder content', { timeout: 60000 }, async () => {
  const f = fixture(), m = await model([phrase]); let target;
  try {
    target = await openSavedLearningTarget({ storage: f.storage, harness: f.harness, model: async () => m, library: bridge });
    await target.native.activateStores(); await target.native.activate('synthetic-policy-v1'); const sent = await target.send(f.input());
    for (const mutation of ['archive', 'project', 'policy', 'test', 'delete']) {
      let mutated = false;
      const history = createLearningHistory(f.storage, { async observe(...args) {
        const page = await target.native.observe(...args);
        if (!mutated) {
          mutated = true;
          const current = await f.storage.command({ type: 'learning.view', threadId: f.input().threadId });
          if (mutation === 'archive') await f.storage.command({ type: 'learning.lifecycle', threadId: f.input().threadId,
            expectedRevision: current.conversation.revision, lifecycle: 'archived', idempotencyKey: 'synthetic-race-archive' });
          if (mutation === 'project') await f.storage.command({ type: 'learning.project', threadId: f.input().threadId,
            expectedRevision: current.conversation.revision, projectId: 'project_a', expectedProjectRevision: 1, idempotencyKey: 'synthetic-race-project' });
          if (mutation === 'policy') f.db().prepare("INSERT OR REPLACE INTO preferences VALUES('design_c.assessment_policy_revision','2','now')").run();
          if (mutation === 'test') f.db().prepare("INSERT INTO assessment_test_attempts(id,version_id,version_snapshot_json,mode,status,clock_high_water_at,created_at,updated_at) VALUES('synthetic-test','synthetic-version','{}','test','active','now','now','now')").run();
          if (mutation === 'delete') await f.storage.command({ type: 'learning.delete', threadId: f.input().threadId,
            expectedRevision: current.conversation.revision, idempotencyKey: 'synthetic-race-delete' });
        }
        return page;
      } });
      await assert.rejects(findAll(history, { query: phrase, scope: { ...scope, lifecycle: 'all' } }), e => ['learning_read_stale', 'conversation_missing', 'assistance_restricted'].includes(e.code));
      if (mutation === 'test') f.db().prepare("UPDATE assessment_test_attempts SET status='submitted' WHERE id='synthetic-test'").run();
    }
    const reserved = await f.begin(1);
    assert.equal(reserved.fresh, true);
    assert.equal((await findAll(target, { query: 'Explain SYNTHETIC AKI.', scope: { ...scope, lifecycle: 'all' } })).items.length, 0);
    assert.equal(await m.count(), 1);
  } finally { await target?.close(); await m.close(); f.close(); }
});

test('Library arguments carry no authority; current rows/rights/revision and generation fence callbacks', { timeout: 60000 }, async () => {
  const f = fixture();
  try {
    const started = await f.begin();
    await f.storage.command({ type: 'learning.map', runId: started.run.receipt.run_id, sessionId: 'synthetic-session' });
    const binding = { operation_id: started.run.receipt.run_id, attempt_id: '1', session_id: 'synthetic-session', input_id: 'synthetic-input', cancellation_id: started.run.receipt.run_id };
    await f.storage.command({ type: 'learning.bind', binding });
    let queryCount = 0;
    const cb = createLearningCallbacks({ storage: f.storage, identity, library: { async query(input) { queryCount++; return bridge.query(input); } } });
    const request = { binding, command: 'library.retrieve', payload: { command: 'library.retrieve', arguments: { query: 'AKI', limit: 1 },
      envelope: { scope: { kind: 'reviewed-assessment' }, policyRevision: -1, cancellationEpoch: -1 } }, signal: new AbortController().signal };
    const good = await cb.handle(request);
    assert.equal(good.outcome, 'committed_reference'); assert.equal(good.result.passages[0].id, PASSAGE); assert.equal(queryCount, 1);
    f.db().prepare("UPDATE knowledge_revisions SET rights_json=json_set(rights_json,'$.model_input',json('false')) WHERE id=?").run(REV);
    const noRights = await cb.handle(request);
    assert.equal(noRights.outcome, 'rejected_before_admission'); assert.equal(queryCount, 1);
    const stale = createLearningCallbacks({ storage: f.storage, identity: { ...identity, generation: 'other-generation' }, library: bridge });
    assert.equal((await stale.handle({ ...request, command: 'learning.check', payload: {} })).outcome, 'rejected_before_admission');
    const changedBinding = { ...binding, input_id: 'other-input' };
    assert.equal((await cb.handle({ ...request, binding: changedBinding, command: 'learning.check', payload: {} })).error.code, 'learning_binding_conflict');
  } finally { f.close(); }
});

test('local learning commands enforce expected revisions, transaction rollback, terminal replay and deletion debt', { timeout: 60000 }, async () => {
  const f = fixture();
  try {
    assert.throws(() => executeLearning(f.db(), { type: 'learning.view', threadId: f.input().threadId }), { code: 'learning_transaction_required' });
    await assert.rejects(f.begin(0, { expectedRevision: 99 }), { code: 'conversation_revision_conflict' });
    assert.equal(f.db().prepare('SELECT count(*) AS n FROM learn_runs').get().n, 0);
    f.db().exec("CREATE TRIGGER synthetic_rollback BEFORE INSERT ON conversation_commands WHEN NEW.idempotency_key='synthetic-force-rollback' BEGIN SELECT RAISE(ABORT,'synthetic rollback'); END");
    await assert.rejects(f.begin(0, { idempotencyKey: 'synthetic-force-rollback' }));
    assert.equal(f.db().prepare('SELECT revision FROM learn_conversations WHERE thread_id=?').get(f.input().threadId).revision, 1);
    assert.equal(f.db().prepare('SELECT count(*) AS n FROM learn_harness_mappings').get().n, 0);
    f.db().exec('DROP TRIGGER synthetic_rollback');
    const begun = await f.begin();
    await f.storage.command({ type: 'learning.map', runId: begun.run.receipt.run_id, sessionId: 'ses_synthetic' });
    const nativeBinding = { operation_id: begun.run.receipt.run_id, attempt_id: '1', session_id: 'ses_synthetic', input_id: 'msg_synthetic', cancellation_id: begun.run.receipt.run_id };
    await f.storage.command({ type: 'learning.bind', binding: nativeBinding });
    await assert.rejects(f.storage.command({ type: 'learning.bind', binding: { ...nativeBinding, input_id: 'msg_other' } }), { code: 'learning_binding_conflict' });
    await f.storage.command({ type: 'learning.stop', runId: nativeBinding.operation_id, state: 'cancelled' });
    const replay = await f.begin(); assert.equal(replay.fresh, false); assert.equal(replay.run.receipt.state, 'cancelled');
    await assert.rejects(f.storage.command({ type: 'learning.current', runId: nativeBinding.operation_id, binding: nativeBinding }), { code: 'learning_run_unavailable' });
    await f.storage.command({ type: 'learning.delete', threadId: f.input().threadId, expectedRevision: 2, idempotencyKey: 'synthetic-purge-debt' });
    f.reopen();
    const debts = await f.storage.command({ type: 'learning.purge.list', identity });
    assert.equal(debts.length, 1); assert.equal(debts[0].session_id, 'ses_synthetic');
    assert.equal(f.db().prepare('SELECT count(*) AS n FROM conversation_commands WHERE target_id=?').get(f.input().threadId).n, 0);
    await assert.rejects(f.begin(), { code: 'command_terminal_unavailable' });
  } finally { f.close(); }
});

test('integrated StorageClient worker owns the Python-prepared native retrieve/cite/receipt/reopen/Finder/delete journey', { timeout: 60000 }, async () => {
  const f = fixture(); f.close();
  const m = await model([{ id: 'worker-retrieve', name: 'renulus_library_retrieve', input: { query: 'AKI', limit: 1 } },
    { id: 'worker-citation', name: 'renulus_library_citation', input: { document_id: DOC, document_revision: REV, passage_id: PASSAGE } }, phrase]);
  let storage, target;
  try {
    storage = await openIsolatedStorage(f.writerOptions);
    assert.equal((await storage.command({ type: 'storage.preview' })).compatible, true);
    target = await openSavedLearningTarget({ storage, harness: f.harness, model: async () => m, library: bridge });
    await target.native.activateStores(); await target.native.activate('synthetic-policy-v1');
    const sent = await target.send(f.input());
    assert.equal(sent.state, 'completed'); assert.equal(sent.answer_reference.citations[0].passage_id, PASSAGE);
    const messages = await storage.command({ type: 'records.page', table: 'learn_messages', offset: 0, limit: 100 });
    assert.deepEqual(messages.rows, []);
    const answers = await storage.command({ type: 'records.page', table: 'learn_harness_answers', offset: 0, limit: 100 });
    assert.equal(answers.rows.length, 1); assert.equal(answers.rows[0].state, 'completed');
    assert.equal(JSON.stringify(answers.rows).includes(phrase), false);
    assert.equal((await target.send(f.input())).replayed, true); assert.equal(await m.count(), 3);
    await target.close(); target = undefined; await storage.close(); storage = undefined;
    storage = await openIsolatedStorage(f.writerOptions);
    target = await openSavedLearningTarget({ storage, harness: f.harness, model: async () => m, library: bridge });
    const found = await findAll(target, { query: '[literal.*%_needle]', scope });
    assert.equal(found.items.length, 1); assert.ok(sent.answer_reference.message_ids.includes(found.items[0].message_id));
    assert.equal((await target.range(f.input().threadId)).messages.filter(m => m.type === 'assistant').length, 3);
    assert.equal(await m.count(), 3);
    await target.native.activate('synthetic-policy-v1');
    const archived = await target.change({ type: 'learning.lifecycle', threadId: f.input().threadId, expectedRevision: sent.conversation.revision,
      lifecycle: 'archived', idempotencyKey: 'synthetic-worker-archive' });
    assert.equal((await findAll(target, { query: phrase, scope })).items.length, 0);
    assert.equal((await findAll(target, { query: phrase, scope: { ...scope, lifecycle: 'archived' } })).items.length, 1);
    await target.delete({ type: 'learning.delete', threadId: f.input().threadId, expectedRevision: archived.revision, idempotencyKey: 'synthetic-worker-delete' });
    assert.equal((await findAll(target, { query: phrase, scope: { ...scope, lifecycle: 'all' } })).items.length, 0);
    assert.deepEqual(await storage.command({ type: 'learning.purge.list', identity }), []);
    await assert.rejects(target.send(f.input()), { code: 'command_terminal_unavailable' });
    assert.equal(await m.count(), 3);
  } finally { await target?.close(); await storage?.close(); await m.close(); }
});

test('Python Send serializer, actual admission receipt/hash/replay match exact TS text intent; draft fences are host-only', { timeout: 60000 }, async t => {
  const f = fixture();
  const inputs = [f.input(0, { text: 'Explain SYNTHETIC CKD Ω 🩺 with café and\nquoted "text".' }), f.input(1)];
  const custom = { expected_revision: 1, text: inputs[0].text, request_id: inputs[0].idempotencyKey,
    teaching_style: 'guided', topic_id: 'synthetic_ckd', model: 'mimo-v2.6-pro', freshness: false, content_refs: [] };
  const runIds = ['synthetic_diff_custom', 'synthetic_diff_default'];
  const at = '2030-01-02T03:04:05.000+00:00';
  f.close();
  const script = `
import sys,json,sqlite3,importlib
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'runtime'))
from renulus.server import create_app
from renulus.learn.conversation_models import Send
from renulus.contracts import ApiError
data=json.loads(sys.stdin.read());target=Path(sys.argv[3])/'state'/'renulus.sqlite3'
target.parent.mkdir(parents=True)
with sqlite3.connect(Path(sys.argv[2]).as_uri()+'?mode=ro',uri=True) as source,sqlite3.connect(target) as dest:source.backup(dest)
s=create_app(Path(sys.argv[3])).state.services;repo=s.registry['conversations']
for module in ['renulus.learn.service','renulus.learn.conversation_stream','renulus.learn.conversation_repository']:
    importlib.import_module(module).utc_now=lambda:data['at']
learn=importlib.import_module('renulus.learn.service');original=learn.durable_id
results=[]
for i,item in enumerate(data['items']):
    run_id=data['runIds'][i]
    learn.durable_id=lambda prefix,r=run_id:r if prefix=='run' else original(prefix)
    request=Send.model_validate(item['request'])
    entry,receipt=repo.streaming.begin('learning',item['threadId'],request)
    with s.db.transaction() as conn:
        row=conn.execute('SELECT request_hash FROM conversation_commands WHERE idempotency_key=?',(request.request_id,)).fetchone()
        request_hash=row['request_hash']
    repo.streaming.active.pop(run_id,None);repo.learn.active.pop(run_id,None)
    replay_entry,replay=repo.streaming.begin('learning',item['threadId'],request)
    assert replay_entry is None
    try:
        repo.streaming.begin('learning',item['threadId'],request.model_copy(update={'teaching_style':'direct' if request.teaching_style=='guided' else 'guided'}))
        raise AssertionError('Changed intent must conflict')
    except ApiError as error:conflict=error.code
    results.append({'request':request.model_dump(mode='json'),'receipt':receipt,'replay':replay,'hash':request_hash,'conflict':conflict})
s.get('helpers').startup.close()
print(json.dumps(results,ensure_ascii=False))
`;
  const environment = Object.fromEntries(['SystemRoot', 'WINDIR', 'TEMP', 'TMP'].filter(k => process.env[k]).map(k => [k, process.env[k]]));
  environment.PATH = dirname(python);
  const result = spawnSync(python, ['-I', '-X', 'utf8', '-c', script, repository, f.database, join(root, 'send-oracle-' + serial)], {
    encoding: 'utf8', env: environment, timeout: 60000, input: JSON.stringify({ at, runIds,
      items: inputs.map((input, i) => ({ threadId: input.threadId, request: i === 0 ? custom
        : { expected_revision: 1, text: input.text, request_id: input.idempotencyKey } })) }),
  });
  assert.equal(result.status, 0, result.stderr || result.error?.message);
  const oracle = JSON.parse(result.stdout);
  f.reopen();
  t.mock.timers.enable({ apis: ['Date'], now: Date.parse(at) });
  try {
    for (let i = 0; i < inputs.length; i++) {
      const command = { type: 'learning.begin', ...inputs[i], ...(i === 0 ? { intent: custom } : {}), runId: runIds[i], attemptId: '1', identity };
      const sent = await f.storage.command(command);
      assert.equal(sent.fresh, true); assert.deepEqual(sent.run.receipt, oracle[i].receipt);
      assert.equal(f.db().prepare('SELECT request_hash FROM conversation_commands WHERE idempotency_key=?').get(inputs[i].idempotencyKey).request_hash, oracle[i].hash);
      const { text: _text, ...metadata } = oracle[i].request;
      assert.deepEqual(sent.run.checkpoint.intent, metadata);
      const replay = await f.storage.command({ ...command, expectedDraftRevision: 999, intent: oracle[i].request });
      assert.equal(replay.fresh, false); assert.deepEqual(replay.run.receipt, oracle[i].replay);
      assert.equal(oracle[i].conflict, 'idempotency_conflict');
      for (const patch of [{ teaching_style: i === 0 ? 'direct' : 'guided' }, { topic_id: 'other' },
        { model: 'gpt-6.1-sol' }, { freshness: true }]) {
        await assert.rejects(f.storage.command({ ...command, intent: { ...oracle[i].request, ...patch } }), { code: 'idempotency_conflict' });
      }
    }
    const input = f.input(2), intent = { ...oracle[1].request, text: input.text, request_id: input.idempotencyKey };
    const retained = { text: 'SYNTHETIC retained draft', refs: [{ target: { type: 'library_revision', id: REV }, locator: null }] };
    f.db().prepare('UPDATE learn_conversations SET draft_text=?,draft_refs_json=? WHERE thread_id=?').run(retained.text, JSON.stringify(retained.refs), input.threadId);
    for (const [patch, code] of [
      [{ text: 'mismatched' }, 'learning_intent_conflict'], [{ expected_revision: 2 }, 'learning_intent_conflict'],
      [{ request_id: 'different-request' }, 'learning_intent_conflict'],
      [{ content_refs: retained.refs }, 'learning_reference_input_not_admitted'],
      [{ images: [{ type: 'image', media_type: 'image/png', data: 'AAAA' }] }, 'learning_images_not_admitted'],
      [{ image_preview_id: 'synthetic-preview', case_revision: 1 }, 'learning_images_not_admitted'],
    ]) await assert.rejects(f.begin(2, { intent: { ...intent, ...patch } }), { code });
    await assert.rejects(f.begin(2, { intent }), { code: 'learning_reference_input_not_admitted' });
    assert.deepEqual({ ...f.db().prepare('SELECT draft_text,draft_refs_json,revision,draft_revision FROM learn_conversations WHERE thread_id=?').get(input.threadId) },
      { draft_text: retained.text, draft_refs_json: JSON.stringify(retained.refs), revision: 1, draft_revision: 0 });
    assert.equal(f.db().prepare('SELECT count(*) AS n FROM learn_runs WHERE thread_id=?').get(input.threadId).n, 0);
  } finally { t.mock.timers.reset(); f.close(); }
});

test('canonical accepted observer may detach or throw; pinned model/style reaches BF01 and native request before completed UI projection', { timeout: 60000 }, async () => {
  const f = fixture(), m = await model(['SYNTHETIC guided CKD answer.']);
  const input = f.input(0, { text: 'Explain SYNTHETIC CKD.' });
  const intent = { expected_revision: 1, text: input.text, request_id: input.idempotencyKey,
    teaching_style: 'guided', topic_id: 'synthetic_ckd', model: 'mimo-v2.6-pro', freshness: false, content_refs: [] };
  let accepted, observedAdmission, observedReplay, begins = 0, nativePrepares = 0, callbacks = 0;
  const target = await openSavedLearningTarget({ storage: f.storage, harness: f.harness, library: bridge,
    async onBegin(run, request) {
      begins++; assert.equal(accepted.run_id, run.receipt.run_id); assert.deepEqual(request, intent);
      assert.equal(Object.isFrozen(request), true); assert.equal(await m.count(), 0);
      assert.equal((await target.native.findSession(run.receipt.run_id)).sessions.length, 0, 'admission observer precedes native session work');
      assert.equal(run.checkpoint.intent.model, intent.model);
    },
    model: async domain => ({ ...m, preparePrimary: (binding, resolved) => Effect.succeed({ resolved,
      prepare: (request, _settings, unfiltered) => Effect.promise(async () => {
        nativePrepares++;
        assert.ok(request.system.some(part => part.type === 'text' && part.text.startsWith('Teaching style: guided.')));
        assert.ok(unfiltered.system.some(part => part.type === 'text' && part.text.startsWith('Teaching style: guided.')));
        const response = await domain.request(binding, 'model.synthetic_intent', {});
        assert.equal(response.outcome, 'committed_reference'); return request;
      }),
    }) }),
    async modelCallbacks(request, authority) {
      callbacks++; assert.equal(request.command, 'model.synthetic_intent'); assert.deepEqual(authority.request, intent);
      assert.equal(authority.run.receipt.run_id, accepted.run_id); assert.equal(authority.run.inputId, request.binding.input_id);
      return { outcome: 'committed_reference', result: { checked: true } };
    },
  });
  try {
    await target.native.activateStores(); await target.native.activate('synthetic-policy-v1');
    const pending = target.send({ ...input, intent: structuredClone(intent) }, { accepted(receipt) {
      accepted = structuredClone(receipt); observedAdmission = { state: receipt.state, active: target.status().active };
      receipt.state = 'cancelled'; // Observers cannot mutate the actual canonical receipt.
      throw new Error('SYNTHETIC renderer detached');
    } });
    const sent = await pending;
    assert.equal(sent.state, 'completed'); assert.equal(sent.run_id, accepted.run_id);
    assert.deepEqual(observedAdmission, { state: 'running', active: 1 });
    assert.deepEqual([begins, nativePrepares, callbacks, await m.count()], [1, 1, 1, 1]);
    const projected = await target.messages(input.threadId);
    assert.deepEqual(projected.items.map(message => [message.id, message.run_id, message.role, message.content, message.content_refs]), [
      [sent.answer_reference.input_id, sent.run_id, 'user', input.text, []],
      [sent.answer_reference.message_ids[0], sent.run_id, 'assistant', 'SYNTHETIC guided CKD answer.', []],
    ]);
    for (const message of projected.items) assert.equal(new Date(message.created_at).toISOString(), message.created_at);
    assert.equal(f.db().prepare('SELECT topic_id FROM learning_evidence WHERE id=?').get('learn-answer:' + sent.run_id).topic_id, intent.topic_id);
    const replay = await target.send({ ...input, intent }, { async accepted(receipt) { observedReplay = receipt.state; throw new Error('SYNTHETIC async observer detached'); } });
    assert.equal(replay.replayed, true); assert.equal(replay.run_id, sent.run_id);
    assert.equal(observedReplay, 'completed');
    await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual([begins, nativePrepares, callbacks, await m.count()], [1, 1, 1, 1]);
  } finally { await target.close(); await m.close(); f.close(); }
});

test('project move resolves its current revision in the writer; explicit trusted revision still fences and rolls back', { timeout: 60000 }, async () => {
  const f = fixture();
  try {
    const command = { type: 'learning.project', threadId: f.input().threadId, expectedRevision: 1,
      projectId: 'project_a', expectedProjectRevision: null, idempotencyKey: 'synthetic-public-project-move' };
    const linked = await f.storage.command(command);
    assert.equal(linked.project_id, 'project_a'); assert.equal(linked.revision, 2);
    assert.deepEqual(await f.storage.command(command), linked);
    f.db().prepare("UPDATE study_projects SET revision=7 WHERE id='project_a'").run();
    await assert.rejects(f.storage.command({ ...command, threadId: f.input(1).threadId,
      expectedProjectRevision: 1, idempotencyKey: 'synthetic-stale-project-move' }), { code: 'project_revision_conflict' });
    assert.equal(f.db().prepare("SELECT count(*) AS n FROM study_project_chats WHERE chat_id=?").get(f.input(1).threadId).n, 0);
    const current = await f.storage.command({ ...command, threadId: f.input(1).threadId, idempotencyKey: 'synthetic-resolved-project-move' });
    assert.equal(current.project_id, 'project_a');
    const admitted = await f.begin(1, { expectedRevision: current.revision });
    assert.equal(admitted.run.checkpoint.projectRevision, 7);
  } finally { f.close(); }
});

test('unconnected model intent refuses without changing draft; failed trusted route pin settles receipt without native work', { timeout: 60000 }, async () => {
  const f = fixture(), m = await model([]);
  let target;
  const input = f.input(), intent = { expected_revision: 1, text: input.text, request_id: input.idempotencyKey,
    teaching_style: 'direct', topic_id: null, model: 'gpt-6.1-sol', freshness: null, content_refs: [] };
  try {
    f.db().prepare('UPDATE learn_conversations SET draft_text=? WHERE thread_id=?').run('SYNTHETIC original draft', input.threadId);
    target = await openSavedLearningTarget({ storage: f.storage, harness: f.harness, library: bridge, model: async () => m });
    let accepted = 0;
    await assert.rejects(target.send({ ...input, intent }, { accepted() { accepted++; } }), { code: 'learning_model_intent_unavailable' });
    assert.equal(accepted, 0); assert.equal(await m.count(), 0);
    assert.equal(f.db().prepare('SELECT draft_text FROM learn_conversations WHERE thread_id=?').get(input.threadId).draft_text, 'SYNTHETIC original draft');
    assert.equal(f.db().prepare('SELECT count(*) AS n FROM learn_runs').get().n, 0);
    await target.close();
    let runId;
    target = await openSavedLearningTarget({ storage: f.storage, harness: f.harness, library: bridge, model: async () => m,
      async onBegin(run, request) {
        assert.equal(request.model, intent.model); assert.equal(runId, run.receipt.run_id);
        throw Object.assign(new Error('SYNTHETIC selected model unavailable'), { code: 'synthetic_route_unavailable' });
      },
    });
    await target.native.activateStores(); await target.native.activate('synthetic-policy-v1');
    await assert.rejects(target.send({ ...input, intent }, { accepted(receipt) { runId = receipt.run_id; } }), { code: 'synthetic_route_unavailable' });
    assert.equal((await target.native.findSession(runId)).sessions.length, 0); assert.equal(await m.count(), 0);
    const replay = await target.send({ ...input, intent });
    assert.equal(replay.state, 'interrupted'); assert.equal(replay.replayed, true);
    assert.equal(f.db().prepare('SELECT draft_text FROM learn_conversations WHERE thread_id=?').get(input.threadId).draft_text, input.text);
    assert.deepEqual((await target.messages(input.threadId)).items, []);
  } finally { await target?.close(); await m.close(); f.close(); }
});

test('integrated native publication pins exact recalled memory revisions, inherits eligible pins and drops revoked answer ancestry', { timeout: 60000 }, async () => {
  const f = fixture(); f.close();
  const storage = await openIsolatedStorage(f.writerOptions), m = await model([
    'SYNTHETIC CKD answer with recalled study context.', 'SYNTHETIC follow-up with eligible memory ancestry.',
    'SYNTHETIC fresh answer after memory correction.',
  ]);
  let target;
  try {
    const fact = await storage.command({ type: 'memory.add', text: 'SYNTHETIC learner studies CKD.', kind: 'learning-point',
      topicId: 'synthetic_ckd', projectId: null, idempotencyKey: 'synthetic-learning-memory-root' });
    const scoped = await storage.command({ type: 'memory.add', text: 'SYNTHETIC project-only learner note.', kind: 'learning-point',
      topicId: null, projectId: 'project_a', idempotencyKey: 'synthetic-learning-memory-project' });
    const pin = { target: { type: 'memory_revision', id: fact.id + ':' + fact.revision }, expected_revision: String(fact.revision) };
    let firstRun;
    target = await openSavedLearningTarget({ storage, harness: f.harness, library: bridge,
      model: async domain => ({ ...m, preparePrimary: (_binding, resolved) => Effect.succeed({ resolved,
        prepare: (request, _settings) => Effect.promise(async () => {
          const response = await domain.request(_binding, 'model.synthetic_memory_pin', {});
          assert.equal(response.outcome, 'committed_reference'); return request;
        }),
      }) }),
      async modelCallbacks(request, authority) {
        if (!firstRun) {
          firstRun = authority.run.receipt.run_id;
          assert.deepEqual(authority.run.checkpoint.memory, []);
          const consume = dependencies => storage.command({ type: 'learning.consumeMemory', binding: request.binding, dependencies });
          await assert.rejects(consume([{ target: { type: 'memory_revision', id: scoped.id + ':1' }, expected_revision: '1' }]), { code: 'memory_project_scope' });
          await assert.rejects(consume([{ target: { type: 'memory_revision', id: fact.id + ':2' }, expected_revision: '2' }]), { code: 'memory_dependency_revoked' });
          await assert.rejects(consume([{ ...pin, target: { type: 'library_revision', id: REV } }]), { code: 'storage_invalid_command' });
          assert.deepEqual((await storage.command({ type: 'learning.current', runId: firstRun, binding: request.binding })).checkpoint.memory, []);
          await consume([pin, pin]);
          const pinned = await storage.command({ type: 'learning.current', runId: firstRun, binding: request.binding });
          assert.deepEqual(pinned.checkpoint.memory, [pin]); assert.deepEqual(pinned.ancestry.dependencies, [pin]);
        }
        return { outcome: 'committed_reference', result: { pinned: true } };
      },
    });
    await target.native.activateStores(); await target.native.activate('synthetic-policy-v1');
    const sent = await target.send(f.input());
    assert.deepEqual(sent.answer_reference.dependencies, [pin]);
    const lineage = (await storage.command({ type: 'records.page', table: 'memory_answer_lineage', offset: 0, limit: 100 })).rows;
    assert.deepEqual(JSON.parse(lineage.find(row => row.evidence_id === 'learn-answer:' + sent.run_id).manifest_json).dependencies, [pin]);
    const followup = await target.send(f.input(0, { expectedRevision: sent.conversation.revision, expectedDraftRevision: 1,
      idempotencyKey: 'synthetic-memory-followup', text: 'SYNTHETIC follow-up on CKD.' }));
    assert.deepEqual(followup.answer_reference.dependencies, [pin]);
    assert.ok(followup.answer_reference.inputs.some(input => input.dependency.target.id === 'learn-answer:' + sent.run_id));
    await storage.command({ type: 'memory.correct', id: fact.id, expectedRevision: 1, text: 'SYNTHETIC corrected learning preference.' });
    const fresh = await target.send(f.input(0, { expectedRevision: followup.conversation.revision, expectedDraftRevision: 2,
      idempotencyKey: 'synthetic-memory-corrected-followup', text: 'SYNTHETIC new explanation after correction.' }));
    assert.deepEqual(fresh.answer_reference.dependencies, []); assert.deepEqual(fresh.answer_reference.inputs, []);
    assert.equal(await m.count(), 3);
  } finally { await target?.close(); await storage.close(); await m.close(); }
});

test('effective source status keeps exact Learning/Memory fingerprints aligned and applies only matching publication events', { timeout: 60000 }, async () => {
  const f = fixture();
  try {
    const metadata = { ...JSON.parse(f.db().prepare('SELECT metadata_json FROM knowledge_revisions WHERE id=?').get(REV).metadata_json),
      canonical_url: 'https://synthetic.invalid/publication-a' };
    f.db().prepare('UPDATE knowledge_revisions SET metadata_json=? WHERE id=?').run(JSON.stringify(metadata), REV);
    const started = await f.begin();
    await f.storage.command({ type: 'learning.map', runId: started.run.receipt.run_id, sessionId: 'synthetic-status-session' });
    const binding = { operation_id: started.run.receipt.run_id, attempt_id: '1', session_id: 'synthetic-status-session',
      input_id: 'synthetic-status-input', cancellation_id: started.run.receipt.run_id };
    await f.storage.command({ type: 'learning.bind', binding });
    const event = (id, url, changes) => {
      const payload = { source_id: 'SYNTHETIC', identity: { canonical_url: url }, changes };
      f.db().prepare('INSERT INTO knowledge_source_status_events VALUES(?,?,?,?,?)').run(id, payload.source_id,
        digest(canonical(payload)), canonical(payload), '2026-10-27T00:00:00.000+00:00');
    };
    event('synthetic-unrelated-status', 'https://synthetic.invalid/publication-b', { retracted: true });
    assert.deepEqual((await f.storage.command({ type: 'learning.library.plan', binding })).revisionIds, [REV]);
    const resolved = await f.storage.command({ type: 'learning.library.resolve', binding, passageIds: [PASSAGE] });
    await f.storage.command({ type: 'learning.consume', binding, references: resolved.references });
    const current = () => f.storage.command({ type: 'learning.current', runId: binding.operation_id, binding });
    const old = (await current()).ancestry.dependencies[0];
    const check = pin => {
      f.db().exec('BEGIN IMMEDIATE');
      try { checkMemoryDependency(f.db(), pin, null); } finally { f.db().exec('ROLLBACK'); }
    };
    check(old);
    event('synthetic-matching-status', metadata.canonical_url, { revision_date: '2026-10-27' });
    const projected = (await current()).ancestry.dependencies[0];
    assert.notEqual(projected.expected_revision, old.expected_revision);
    const revision = f.db().prepare('SELECT * FROM knowledge_revisions WHERE id=?').get(REV);
    assert.equal(projected.expected_revision, digest(canonical({ identity: { type: 'library_revision', id: REV }, document_id: DOC,
      sha256: revision.sha256, title: 'SYNTHETIC Library', source_id: 'SYNTHETIC', metadata: { ...metadata, revision_date: '2026-10-27' },
      rights: JSON.parse(revision.rights_json), passage_id: PASSAGE, locators: [{ page: 1, char_span: [0, 40] }] })));
    check(projected); assert.throws(() => check(old), { code: 'memory_dependency_revoked' });
    event('synthetic-retracted-status', metadata.canonical_url, { retracted: true });
    await assert.rejects(current(), { code: 'learning_source_unavailable' });
    assert.throws(() => check(projected), { code: 'memory_dependency_revoked' });
  } finally { f.close(); }
});
