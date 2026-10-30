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
const ID = (prefix, n) => prefix + '_' + String(n).repeat(32);
const REV = { library: ID('rev', 1), reserved: ID('rev', 2), retracted: ID('rev', 3), note: ID('rev', 4) };
const NATIVE = 'ZEBRAFISH-native-only';

test('Finder: native-only text after restart, canonical metadata, Archive/project/delete/ineligible boundaries and epoch-bound cursors', { timeout: 120_000 }, async () => {
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
revs=json.loads(sys.argv[3]); now='2026-10-27T00:00:00Z'
rights={key:True for key in ['display','cache','index','embedding','model_input','derivation']}
rights.update(licence='CC-BY-4.0',permission_reference='SYNTHETIC',attribution='Synthetic test author')
base={'source_id':'SYNTHETIC','publication_status':'final','content_reviewed':True,'latest_final_verified':True,'excluded_pages':[]}
docs=[('library','SYNTHETIC Library',0,base,'SYNTHETIC canonical Library AKI passage'),
 ('reserved','Hidden assessment source',1,base,'RESERVEDNEEDLE passage'),
 ('retracted','Retracted source',0,{**base,'retracted':True},'RETRACTEDNEEDLE passage'),
 ('note','Study note',0,{**base,'asset_role':['study-note'],'access_class':'user-owned'},'NOTENEEDLE personal passage')]
with s.db.transaction() as c:
    c.execute("INSERT OR REPLACE INTO harness_store_identity VALUES(1,'synthetic-profile','synthetic-domain-store',1,'4b6fea2875e4f2e3e8a8fee181803e54f7056845')")
    c.execute("INSERT INTO study_projects VALUES('project_a','SYNTHETIC project','active',1,?,?)",(now,now))
    for name,title,reserved,metadata,text in docs:
        rev=revs[name]; doc='doc_'+name
        c.execute("INSERT INTO knowledge_documents VALUES(?,?,?,'personal-library',NULL,?,?,?,NULL,?,?)",(doc,title,'SYNTHETIC',reserved,rev,rev,now,now))
        c.execute("INSERT INTO knowledge_revisions VALUES(?,?,1,'ready',?,'text/plain',40,NULL,?,?,NULL,NULL,NULL,?,?)",(rev,doc,'1'*64,json.dumps(metadata),json.dumps(rights),now,now))
        c.execute("INSERT INTO knowledge_passages VALUES(?,?,0,?,?,?,'[]')",('passage_'+name,rev,text,text,json.dumps([{'page':1,'char_span':[0,40]}])))
print(json.dumps({'database':str(s.paths.database),'threads':threads}))
`;
  const environment = Object.fromEntries(['SystemRoot', 'WINDIR', 'TEMP', 'TMP'].filter(k => process.env[k]).map(k => [k, process.env[k]])); environment.PATH = dirname(python);
  const prepared = spawnSync(python, ['-I', '-X', 'utf8', '-c', script, repository, profile, JSON.stringify(REV)], { encoding: 'utf8', env: environment, timeout: 60000 });
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
  const bridge = { async query() { return []; } };
  try {
    open(); schemaHash = inventory(db, migrations).schemaHash;
    const client = await runtime.runPromise(TestLLM.Test);
    const model = async () => ({ providerId: 'synthetic', modelId: 'counted-learning', client,
      configuration: { model: 'synthetic/counted-learning', providers: { synthetic: { package: '@opencode/ai/providers/openai-compatible',
        settings: { baseURL: 'https://synthetic.invalid/v1', apiKey: 'synthetic-unused' }, models: { 'counted-learning': { limit: { context: 128000, output: 4096 } } } } } } });
    const open_ = async () => { const t = await openSavedLearningTarget({ storage, harness, model, library: bridge });
      await t.native.activateStores(); await t.native.activate('synthetic-policy-v1'); return t; };
    const requests = async () => (await runtime.runPromise(client.requests())).length;
    const send = async (index, text, answer) => { await runtime.runPromise(client.push(TestLLM.text(answer, 'answer')));
      return target.send({ threadId: thread[index], expectedRevision: 1, expectedDraftRevision: 0, text, idempotencyKey: 'find-send-' + index }); };

    target = await open_();
    const first = await send(0, 'Explain SYNTHETIC AKI.', 'Answer holding ' + NATIVE + ' text.');
    await send(1, 'Explain SYNTHETIC CKD.', 'An unrelated answer.');
    const calls = await requests(); assert.equal(calls, 2);
    await target.close(); close(); open(); assert.equal(inventory(db, migrations).schemaHash, schemaHash);
    target = await open_();
    const finder = createFindDomain({ storage, history: target });
    const every = async (query, scope = { lifecycle: 'active', projectId: null }, limit = 30) => {
      const items = []; let cursor = null;
      for (let page = 0; page < 60; page++) { const result = await finder.find({ query, scope, cursor, limit }); items.push(...result.items); cursor = result.next_cursor; if (!cursor) return items; }
      return assert.fail('bounded synthetic Finder must finish');
    };

    // Native-only message text, found after restart by case-insensitive literal, with exact message identity and no model work.
    const hits = await every('zebrafish-NATIVE');
    assert.equal(hits.length, 1); assert.equal(hits[0].group, 'chats'); assert.ok(first.answer_reference.message_ids.includes(hits[0].message.id));
    assert.equal(hits[0].identity.id, thread[0]); assert.match(hits[0].snippet, /ZEBRAFISH-native-only/); assert.equal(await requests(), calls);
    assert.equal(JSON.stringify(db.prepare('SELECT * FROM learn_messages').all()).includes(NATIVE), false, 'canonical SQLite holds no message copy');

    // Titles, projects, files and notes across every group, with bounded cursors and no duplicate result.
    const all = await every('synthetic', undefined, 2); const keys = all.map(i => i.key);
    assert.equal(new Set(keys).size, keys.length);
    assert.deepEqual(thread.map(id => 'chat:learning:' + id).filter(k => !keys.includes(k)), []);
    assert.ok(keys.includes('project:project_a')); assert.ok(keys.includes('file:' + REV.library));
    const library = (await every('canonical library aki')).find(i => i.key === 'file:' + REV.library);
    assert.deepEqual(library.reference, { target: { type: 'library_revision', id: REV.library }, locator: { kind: 'pdf', physical_page: 1 } }); assert.equal(library.group, 'files');
    const notes = (await every('NOTENEEDLE'))[0]; assert.equal(notes.group, 'notes'); assert.equal(notes.reference.target.type, 'note_revision');
    assert.deepEqual(await every('RESERVEDNEEDLE'), []); assert.deepEqual(await every('RETRACTEDNEEDLE'), []);
    assert.deepEqual(await every('hidden assessment'), [], 'reserved titles stay out of Finder');

    // Archive is immediate; project membership follows canonical moves; Library links scope files.
    let conversation = first.conversation;
    conversation = await storage.command({ type: 'learning.lifecycle', threadId: thread[0], expectedRevision: conversation.revision, lifecycle: 'archived', idempotencyKey: 'find-archive' });
    assert.deepEqual(await every(NATIVE), []); assert.equal((await every(NATIVE, { lifecycle: 'archived', projectId: null })).length, 1);
    assert.equal((await every(NATIVE, { lifecycle: 'all', projectId: null })).length, 1);
    assert.equal((await every('canonical library', { lifecycle: 'archived', projectId: null })).length, 0, 'files have no Archive lifecycle');
    conversation = await storage.command({ type: 'learning.lifecycle', threadId: thread[0], expectedRevision: conversation.revision, lifecycle: 'active', idempotencyKey: 'find-restore' });
    const scoped = { lifecycle: 'active', projectId: 'project_a' };
    assert.deepEqual(await every(NATIVE, scoped), []);
    conversation = await storage.command({ type: 'learning.project', threadId: thread[0], expectedRevision: conversation.revision, projectId: 'project_a', expectedProjectRevision: 1, idempotencyKey: 'find-move' });
    assert.equal((await every(NATIVE, scoped)).length, 1);
    assert.deepEqual(await every('canonical library', scoped), []);
    const project = await storage.command({ type: 'project.get', projectId: 'project_a' });
    await storage.command({ type: 'project.document', projectId: 'project_a', expectedRevision: project.revision, revisionId: REV.library, position: 0, action: 'link', idempotencyKey: 'find-link' });
    assert.equal((await every('canonical library', scoped)).length, 1);
    const linked = await storage.command({ type: 'project.get', projectId: 'project_a' });
    await storage.command({ type: 'project.document', projectId: 'project_a', expectedRevision: linked.revision, revisionId: REV.library, position: 0, action: 'unlink', idempotencyKey: 'find-unlink' });
    assert.deepEqual(await every('canonical library', scoped), []); assert.equal((await every('canonical library')).length, 1, 'unlinking keeps the independent original');
    await storage.command({ type: 'learning.project', threadId: thread[0], expectedRevision: conversation.revision, projectId: null, expectedProjectRevision: null, idempotencyKey: 'find-move-out' });
    assert.deepEqual(await every(NATIVE, scoped), []); assert.equal((await every(NATIVE)).length, 1);
    await assert.rejects(finder.find({ query: 'x', scope: { lifecycle: 'active', projectId: 'project_missing' } }), { code: 'project_missing' });

    // Cursors pin query, filter and canonical epoch; changed canonical state refuses a stale continuation.
    const page = await finder.find({ query: 'synthetic', scope: { lifecycle: 'active', projectId: null }, limit: 1 }); assert.ok(page.next_cursor);
    await assert.rejects(finder.find({ query: 'other', scope: { lifecycle: 'active', projectId: null }, cursor: page.next_cursor }), { code: 'search_cursor_changed' });
    await assert.rejects(finder.find({ query: 'synthetic', scope: { lifecycle: 'all', projectId: null }, cursor: page.next_cursor }), { code: 'search_cursor_changed' });
    const archived = (await storage.command({ type: 'learning.view', threadId: thread[2] })).conversation;
    await storage.command({ type: 'learning.lifecycle', threadId: thread[2], expectedRevision: archived.revision, lifecycle: 'archived', idempotencyKey: 'find-archive-2' });
    await assert.rejects(finder.find({ query: 'synthetic', scope: { lifecycle: 'active', projectId: null }, cursor: page.next_cursor }), { code: /learning_cursor_stale|search_cursor_changed/ });

    // Deleting the chat removes its native text from Finder results.
    const current = (await storage.command({ type: 'learning.view', threadId: thread[0] })).conversation;
    await target.delete({ type: 'learning.delete', threadId: thread[0], expectedRevision: current.revision, idempotencyKey: 'find-delete' });
    assert.deepEqual(await every(NATIVE, { lifecycle: 'all', projectId: null }), []);
    assert.equal((await every('synthetic', { lifecycle: 'all', projectId: null })).some(i => i.key === 'chat:learning:' + thread[0]), false);
    assert.equal(await requests(), calls);
  } finally {
    await target?.close(); close(); await runtime.dispose();
    assert.equal(dirname(root), resolve(tmpdir())); assert.match(basename(root), /^renulus-find-journey-/); rmSync(root, { recursive: true, force: true });
  }
});
