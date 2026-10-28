// SPDX-License-Identifier: MIT
import '../../harness/test/owned-environment.mjs';
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { spawnSync } from 'node:child_process';
import { DatabaseSync } from 'node:sqlite';
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { basename, dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { ManagedRuntime } from 'effect';
import { TestLLM } from '@opencode/ai/testing';
import { importLegacyHistory } from '../src/domain/learning/legacy-import.ts';
import { openSavedLearningTarget } from '../src/host/learning.ts';
import { createFindDomain } from '../src/domain/find/index.ts';
import { executeLearning } from '../src/storage/learning.ts';
import { executeKnowledge } from '../src/storage/knowledge.ts';
import { executeProject } from '../src/storage/projects.ts';
import { acquireOwner, MARKER, SELECTOR } from '../src/storage/ownership.ts';
import { inventory, loadMigrationInventory } from '../src/storage/schema.ts';

const repository = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const python = 'C:/Renulus/dev/python/Scripts/python.exe';
const identity = { profileId: 'synthetic-profile', storeId: 'synthetic-store', generation: 'synthetic-find-process' };
test('legacy history imports transparently once, reaches native Finder, and deletion retains refusal tombstone', { timeout: 120_000 }, async () => {
  const root = mkdtempSync(join(tmpdir(), 'renulus-find-journey-'));
  const profile = join(root, 'profile'), migrations = loadMigrationInventory(repository);
  const script = `
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'runtime'))
from renulus.server import create_app
from renulus.learn.conversation_models import NewConversation
s=create_app(Path(sys.argv[2])).state.services
threads=[s.registry['conversations'].create(NewConversation(kind='learning',title='SYNTHETIC '+topic),'find-create-'+str(i)) for i,topic in enumerate(['AKI','CKD','Dialysis'])]
now='2026-10-27T00:00:00Z'
with s.db.transaction() as c:
    c.execute("INSERT OR REPLACE INTO harness_store_identity VALUES(1,'synthetic-profile','synthetic-domain-store',1,'4b6fea2875e4f2e3e8a8fee181803e54f7056845')")
    thread=threads[0]['identity']['id']
    c.execute("INSERT INTO learn_runs VALUES('legacy_run',?,'legacy-seed','completed',NULL,?,?)",(thread,now,now))
    c.execute("INSERT INTO learn_messages VALUES('legacy_user',?,'legacy_run','user','SYNTHETIC transplant question','[]',?)",(thread,now))
    c.execute("INSERT INTO learn_messages VALUES('legacy_answer',?,'legacy_run','assistant','SYNTHETIC LEGACYNEEDLE transplant learning','[]',?)",(thread,now))
print(json.dumps({'database':str(s.paths.database),'threads':threads}))
`;
  const environment = Object.fromEntries(['SystemRoot', 'WINDIR', 'TEMP', 'TMP'].filter(k => process.env[k]).map(k => [k, process.env[k]])); environment.PATH = dirname(python);
  const prepared = spawnSync(python, ['-I', '-X', 'utf8', '-c', script, repository, profile], { encoding: 'utf8', env: environment, timeout: 60000 });
  assert.equal(prepared.status, 0, prepared.stderr || prepared.error?.message);
  const { database, threads } = JSON.parse(prepared.stdout), thread = threads.map(t => t.identity.id);
  const selection = { contract: 'renulus-storage-selector/1', isolation: 'synthetic', profileId: identity.profileId, generation: 1, authorityEpoch: 1,
    writer: 'ts', state: 'active', ownerId: 'synthetic-find-owner', database: 'state/renulus.sqlite3' };
  writeFileSync(join(profile, MARKER), JSON.stringify({ contract: 'renulus-synthetic-storage/1', profileId: identity.profileId }));
  writeFileSync(join(profile, SELECTOR), JSON.stringify(selection));
  const manifest = JSON.parse(readFileSync(join(repository, 'packages/contracts/fixtures/harness/paired-store-prepared.json'), 'utf8'));
  manifest.domain_store.path = 'state/renulus.sqlite3'; manifest.runtime_store.store_id = identity.storeId; manifest.runtime_store.path = 'state/harness/opencode.sqlite';
  mkdirSync(join(profile, 'state/harness'), { recursive: true }); writeFileSync(join(profile, 'state/harness/manifest.json'), JSON.stringify(manifest));
  let owner, db, schemaHash;
  const open = () => { owner = acquireOwner({ profileRoot: profile, selection, migrations, expectedSchemaHash: '' });
    db = new DatabaseSync(database, { enableForeignKeyConstraints: true }); db.exec('PRAGMA secure_delete=ON; PRAGMA journal_mode=WAL;'); };
  const close = () => { if (db) { db.close(); db = undefined; owner.release(); } };
  const storage = { async command(c) {
    owner.check(); db.exec('BEGIN IMMEDIATE');
    try { const execute = c.type.startsWith('knowledge.') ? executeKnowledge : c.type.startsWith('project.') ? executeProject : executeLearning;
      const result = execute(db, c); owner.check(); db.exec('COMMIT'); return result; }
    catch (error) { db.exec('ROLLBACK'); throw error; } } };
  const harness = { root: profile, profileId: identity.profileId, storeId: identity.storeId, domainStoreId: 'synthetic-domain-store',
    domainPath: 'state/renulus.sqlite3', processGeneration: identity.generation };
  const runtime = ManagedRuntime.make(TestLLM.testLayer());
  let target;
  try {
    open();
    const original = JSON.stringify(db.prepare('SELECT * FROM learn_messages ORDER BY id').all());
    const client = await runtime.runPromise(TestLLM.Test);
    const model = async () => ({ providerId: 'synthetic', modelId: 'counted-learning', client,
      configuration: { model: 'synthetic/counted-learning', providers: { synthetic: { package: '@opencode/ai/providers/openai-compatible',
        settings: { baseURL: 'https://synthetic.invalid/v1', apiKey: 'synthetic-unused' }, models: { 'counted-learning': { limit: { context: 128000, output: 4096 } } } } } } });
    const openTarget = async () => {
      const t = await openSavedLearningTarget({ storage, harness, model, library: { async query() { return []; } } });
      await t.native.activateStores(); await t.native.activate('synthetic-policy-v1'); return t;
    };
    target = await openTarget();
    await runtime.runPromise(client.push(TestLLM.text('SYNTHETIC follow-up answer.', 'answer')));
    const sent = await target.send({ threadId: thread[0], expectedRevision: 1, expectedDraftRevision: 0,
      text: 'SYNTHETIC follow-up question', idempotencyKey: 'legacy-follow-up-send' });
    assert.equal(sent.state, 'completed');
    assert.equal(JSON.stringify(db.prepare('SELECT * FROM learn_messages ORDER BY id').all()), original);
    const receipt = db.prepare('SELECT * FROM legacy_history_imports WHERE thread_id=?').get(thread[0]);
    assert.equal(receipt.state, 'active'); assert.match(receipt.source_digest, /^[a-f0-9]{64}$/);
    const page = await target.messages(thread[0]);
    assert.ok(page.items.some(m => m.content.includes('LEGACYNEEDLE')));
    assert.equal((await runtime.runPromise(client.requests())).length, 1);
    await assert.rejects(importLegacyHistory(storage, target.native, identity, thread[0], sent.conversation.revision), { code: 'learning_migration_already_imported' });
    await target.close(); close(); open(); target = await openTarget();
    const finder = createFindDomain({ storage, history: target });
    const hits = []; let cursor = null;
    do { const result = await finder.find({ query: 'LEGACYNEEDLE', scope: { lifecycle: 'all', projectId: null }, cursor, limit: 30 });
      hits.push(...result.items); cursor = result.next_cursor; } while (cursor);
    assert.equal(hits.length, 1); assert.equal(hits[0].identity.id, thread[0]);
    assert.match(hits[0].message.id, /^msg_/);
    await target.delete({ type: 'learning.delete', threadId: thread[0], expectedRevision: sent.conversation.revision, idempotencyKey: 'legacy-delete-chat' });
    assert.equal(db.prepare('SELECT state FROM legacy_history_imports WHERE thread_id=?').get(thread[0]).state, 'deleted');
    assert.equal(db.prepare('SELECT count(*) AS n FROM learn_messages WHERE thread_id=?').get(thread[0]).n, 0);
    await assert.rejects(importLegacyHistory(storage, target.native, identity, thread[0], sent.conversation.revision), { code: 'learning_migration_already_imported' });
    assert.equal((await runtime.runPromise(client.requests())).length, 1);
  } finally {
    await target?.close(); close(); await runtime.dispose();
    assert.equal(dirname(root), resolve(tmpdir())); assert.match(basename(root), /^renulus-find-journey-/); rmSync(root, { recursive: true, force: true });
  }
});
