// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import { spawnSync } from 'node:child_process';
import { DatabaseSync } from 'node:sqlite';
import { copyFileSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { basename, dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { executeLearningMetadata, validateLearningMetadataCommand, validateLearningMetadataResult } from '../src/storage/conversation-metadata.ts';
import { openIsolatedStorage, MARKER, SELECTOR } from '../src/storage/index.ts';
import { inventory, loadMigrationInventory } from '../src/storage/schema.ts';

const repository = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const python = 'C:/Renulus/dev/python/Scripts/python.exe';
const root = mkdtempSync(join(tmpdir(), 'renulus-conversation-metadata-'));
const migrations = loadMigrationInventory(repository);
let prepared, serial = 0;
const cleanups = [];
const environment = Object.fromEntries(['SystemRoot', 'WINDIR', 'TEMP', 'TMP'].filter(k => process.env[k]).map(k => [k, process.env[k]]));
environment.PATH = dirname(python);

before(() => {
  assert.equal(process.versions.node, '26.4.0', 'Run with the pinned Node artifact.');
  // Only synthetic schema-2 state. The original Python repository is the receipt/hash/draft oracle.
  const script = `
import sys,json,sqlite3
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'runtime'))
from renulus.server import create_app
from renulus.learn.conversation_models import NewConversation, Send
from renulus.design_c_contracts import ConversationDraft, ContentReference
from renulus.learn.conversation_repository import command
s=create_app(Path(sys.argv[2])/'oracle').state.services
repo=s.registry['conversations'];stream=repo.streaming
topics=['Electrolytes','AKI','CKD','Glomerular disease','Transplantation','Dialysis']
requests=[NewConversation(kind='learning',title='SYNTHETIC '+topic,teaching_style='guided' if i==0 else 'direct') for i,topic in enumerate(topics)]
threads=[repo.create(r,'metadata-python-create-'+str(i)) for i,r in enumerate(requests)]
rights={'display':True,'model_input':False,'cache':True,'index':True,'embedding':True,'derivation':True}
with s.db.transaction() as c:
    c.execute("INSERT INTO study_projects VALUES('synthetic_project','SYNTHETIC project','active',1,'2026-10-26T00:00:00.000+00:00','2026-10-26T00:00:00.000+00:00')")
    c.execute("INSERT INTO study_projects VALUES('synthetic_archived','SYNTHETIC archived','archived',1,'2026-10-26T00:00:00.000+00:00','2026-10-26T00:00:00.000+00:00')")
    c.execute("INSERT INTO knowledge_documents VALUES('synthetic_doc','SYNTHETIC retained source','SYNTHETIC','personal-library',NULL,0,'synthetic_rev2','synthetic_rev2',NULL,'2026-10-26T00:00:00.000+00:00','2026-10-26T00:00:00.000+00:00')")
    for n in [1,2]:
        c.execute("INSERT INTO knowledge_revisions VALUES(?, 'synthetic_doc',?,'ready',?,'application/pdf',0,NULL,'{}',?,NULL,NULL,NULL,'2026-10-26T00:00:00.000+00:00','2026-10-26T00:00:00.000+00:00')",('synthetic_rev'+str(n),n,'a'*64,json.dumps(rights)))
    c.execute("INSERT INTO assessment_tests VALUES('synthetic_test','SYNTHETIC test','active',1,'2026-10-26T00:00:00.000+00:00','2026-10-26T00:00:00.000+00:00')")
    c.execute("INSERT INTO assessment_test_versions VALUES('synthetic_version','synthetic_test',1,'imported','personal','ready','[]','[]','SYNTHETIC',?,'{}','2026-10-26T00:00:00.000+00:00')",('b'*64,))
    c.execute("INSERT INTO knowledge_attachments VALUES('synthetic_attachment','learning',?,'SYNTHETIC retained attachment','text/plain',1,'ready','ready','2026-10-26T00:00:00.000+00:00','2026-10-26T00:00:00.000+00:00')",(threads[0]['identity']['id'],))
    c.execute("INSERT INTO knowledge_attachment_metadata(attachment_id,filename,source_id,metadata_json,rights_json) VALUES('synthetic_attachment','SYNTHETIC.txt','SYNTHETIC','{}',?)",(json.dumps(rights),))
refs=[ContentReference.model_validate(v) for v in [
 {'target':{'type':'library_revision','id':'synthetic_rev1'},'locator':{'kind':'pdf','physical_page':2,'printed_label':'ii'}},
 {'target':{'type':'note_revision','id':'synthetic_rev2'},'locator':{'kind':'text','item_ref':'SYNTHETIC section','section':'Summary','start':0,'end':10}},
 {'target':{'type':'library_revision','id':'synthetic_rev1'},'locator':{'kind':'table','format':'xlsx','sheet_name':'SYNTHETIC','first_row':1,'last_row':2,'first_column':1,'last_column':3}},
 {'target':{'type':'library_revision','id':'synthetic_rev2'},'locator':{'kind':'image','frame':1,'bounds':[0,0.0000001,1,1]}},
 {'target':{'type':'attachment','id':'synthetic_attachment'},'locator':None},
 {'target':{'type':'saved_test_version','id':'synthetic_version'},'locator':None}]]
seed=ConversationDraft(expected_revision=1,text='SYNTHETIC baseline π 🩺',content_refs=tuple(refs))
seed_receipt=repo.save_draft('learning',threads[0]['identity']['id'],seed,'metadata-python-draft')
with s.db.transaction() as c:
    for i,state in enumerate(['completed','failed','running']):
        run='synthetic_run_'+str(i)
        receipt={'run_id':run,'state':state,'conversation':repo._saved(c,'learning',threads[0]['identity']['id'])[0]}
        if state=='failed': receipt['error']={'code':'synthetic_failure','message':'SYNTHETIC retained error','retryable':True}
        command(c,'conversation_commands','metadata-python-send-'+str(i),'send','learn_thread',threads[0]['identity']['id'],Send(expected_revision=2,text='SYNTHETIC question',request_id=run),lambda r=receipt:r)
        c.execute("UPDATE conversation_commands SET created_at=? WHERE idempotency_key=?",('2026-10-26T00:00:0'+str(i)+'.000+00:00','metadata-python-send-'+str(i)))
# Freeze a Python-prepared database BEFORE the oracle follow-up; no schema substitute.
target=Path(sys.argv[2])/'prepared.sqlite3'
with s.db.connect() as source, sqlite3.connect(target) as destination: source.backup(destination)
follow=ConversationDraft(expected_revision=2,text='SYNTHETIC edited CKD Ω 🩺',content_refs=tuple(refs))
follow_receipt=repo.save_draft('learning',threads[0]['identity']['id'],follow,'metadata-followup-key')
follow_replay=repo.save_draft('learning',threads[0]['identity']['id'],follow,'metadata-followup-key')
later=repo.save_draft('learning',threads[0]['identity']['id'],ConversationDraft(expected_revision=3,text='SYNTHETIC newer draft'),'metadata-later-key')
old_replay=repo.save_draft('learning',threads[0]['identity']['id'],follow,'metadata-followup-key')
with s.db.transaction() as c:
    hashes={r['idempotency_key']:r['request_hash'] for r in c.execute('SELECT idempotency_key,request_hash FROM conversation_commands')}
    c.execute("INSERT INTO assessment_test_attempts(id,version_id,version_snapshot_json,mode,status,clock_high_water_at,created_at,updated_at) VALUES('synthetic_attempt','synthetic_version','{}','test','active','now','now','now')")
restricted=stream.status('learning',threads[0]['identity']['id'],'synthetic_run_1')
restricted_list=stream.list('learning',threads[0]['identity']['id'])
with s.db.transaction() as c: c.execute("UPDATE assessment_test_attempts SET status='submitted' WHERE id='synthetic_attempt'")
print(json.dumps({'database':str(target),'threads':threads,'create_request':requests[0].model_dump(mode='json'),
 'seed_request':seed.model_dump(mode='json'),'seed_receipt':seed_receipt,'follow_request':follow.model_dump(mode='json'),
 'follow_receipt':follow_receipt,'follow_replay':follow_replay,'later_receipt':later,'old_replay':old_replay,'hashes':hashes,
 'neutral_status':stream.status('learning',threads[0]['identity']['id'],'synthetic_run_1',neutral=True),
 'restricted_status':restricted,'restricted_list':restricted_list,
 'status_error':{'code':'synthetic_failure','message':'SYNTHETIC retained error','retryable':True}},ensure_ascii=False))
`;
  const r = spawnSync(python, ['-I', '-X', 'utf8', '-c', script, repository, root], { encoding: 'utf8', env: environment, timeout: 60000 });
  assert.equal(r.status, 0, r.stderr || r.error?.message); prepared = JSON.parse(r.stdout);
});
after(() => {
  cleanups.forEach(close => close());
  assert.equal(dirname(root), resolve(tmpdir())); assert.match(basename(root), /^renulus-conversation-metadata-/);
  rmSync(root, { recursive: true, force: true });
});
function fixture() {
  const profile = join(root, 'subject-' + (++serial)), database = join(profile, 'state/renulus.sqlite3');
  mkdirSync(dirname(database), { recursive: true }); copyFileSync(prepared.database, database);
  let db = new DatabaseSync(database, { enableForeignKeyConstraints: true });
  const schemaHash = inventory(db, migrations).schemaHash;
  function transaction(action) {
    db.exec('BEGIN IMMEDIATE');
    try { const result = action(); assert.equal(typeof result?.then, 'undefined'); db.exec('COMMIT'); return result; }
    catch (error) { db.exec('ROLLBACK'); throw error; }
  }
  function close() { if (db) { db.close(); db = undefined; } }
  cleanups.push(close);
  return { profile, database, db: () => db, schemaHash, close, transaction,
    execute: command => transaction(() => executeLearningMetadata(db, command)),
    threadId: prepared.threads[0].identity.id,
    create: (overrides = {}, idempotencyKey = 'metadata-python-create-0') => ({ type: 'learning.create', request: { ...prepared.create_request, ...overrides }, idempotencyKey }),
    save: (request = prepared.follow_request, idempotencyKey = 'metadata-followup-key') => ({ type: 'learning.draft.save', threadId: prepared.threads[0].identity.id, request, idempotencyKey }) };
}
const code = value => ({ code: value });
const list = (overrides = {}) => ({ type: 'learning.list', limit: 2, cursor: null, lifecycle: 'active', projectId: null, ...overrides });
function activeTest(f, active = true) {
  f.transaction(() => {
    if (active) f.db().prepare("INSERT INTO assessment_test_attempts(id,version_id,version_snapshot_json,mode,status,clock_high_water_at,created_at,updated_at) VALUES('synthetic_attempt','synthetic_version','{}','test','active','now','now','now')").run();
    else f.db().prepare("DELETE FROM assessment_test_attempts WHERE id='synthetic_attempt'").run();
  });
}
test('Python create/draft receipts, full Unicode/reference hash, stale-revision replay and latest draft remain identical', () => {
  const f = fixture();
  assert.equal(inventory(f.db(), migrations).schemaVersion, 2);
  assert.deepEqual(f.execute(f.create()), prepared.threads[0]);
  assert.deepEqual(f.execute(f.save(prepared.seed_request, 'metadata-python-draft')), prepared.seed_receipt);
  const result = f.execute(f.save());
  assert.deepEqual(result, prepared.follow_receipt); assert.deepEqual(f.execute(f.save()), prepared.follow_replay);
  assert.equal(f.db().prepare('SELECT request_hash FROM conversation_commands WHERE idempotency_key=?').get('metadata-followup-key').request_hash, prepared.hashes['metadata-followup-key']);
  const later = f.execute(f.save({ expected_revision: 3, text: 'SYNTHETIC newer draft', content_refs: [] }, 'metadata-later-key'));
  assert.deepEqual(later, prepared.later_receipt); assert.deepEqual(f.execute(f.save()), prepared.old_replay);
  assert.deepEqual(f.execute({ type: 'learning.draft.get', threadId: f.threadId }), prepared.later_receipt);
  assert.throws(() => f.execute(f.save({ ...prepared.follow_request, text: 'different' })), code('idempotency_conflict'));
  assert.throws(() => f.execute(f.save(prepared.follow_request, 'new-stale-revision')), code('conversation_revision_conflict'));
  assert.equal(f.db().prepare("SELECT value FROM preferences WHERE key='design_c.context_epoch'").get()?.value,
    undefined, 'drafts do not bump the Python context epoch');
});

test('fresh create uses Python request hash, durable IDs, project revision/position/epoch and atomic failure', () => {
  const f = fixture();
  const c = f.create({}, 'metadata-ts-create-key'), created = f.execute(c);
  assert.match(created.identity.id, /^thread_[a-f0-9]{32}$/);
  assert.equal(created.kind, 'learning'); assert.equal(created.revision, 1); assert.equal(created.title, prepared.threads[0].title);
  assert.equal(f.db().prepare('SELECT request_hash FROM conversation_commands WHERE idempotency_key=?').get(c.idempotencyKey).request_hash, prepared.hashes['metadata-python-create-0']);
  assert.deepEqual(f.execute(c), created);
  assert.throws(() => f.execute(f.create({ title: 'different' }, c.idempotencyKey)), code('idempotency_conflict'));
  f.transaction(() => f.db().prepare("INSERT INTO deletion_ledger VALUES('learn_thread',?,'now')").run(created.identity.id));
  assert.throws(() => f.execute(c), code('command_terminal_unavailable'), 'newer owner frontier refuses an additive restored create receipt');
  const linked = f.execute(f.create({ project_id: 'synthetic_project' }, 'metadata-project-create'));
  assert.equal(linked.project_id, 'synthetic_project'); assert.equal(linked.revision, 1);
  assert.equal(f.db().prepare("SELECT revision FROM study_projects WHERE id='synthetic_project'").get().revision, 2);
  assert.equal(f.db().prepare("SELECT position FROM study_project_chats WHERE chat_id=?").get(linked.identity.id).position, 0);
  assert.equal(f.db().prepare("SELECT value FROM preferences WHERE key='design_c.context_epoch'").get().value, '1');
  const count = f.db().prepare('SELECT COUNT(*) AS n FROM learn_threads').get().n;
  assert.throws(() => f.execute(f.create({ project_id: 'synthetic_archived' }, 'metadata-archived-create')), code('project_archived'));
  assert.throws(() => f.execute(f.create({ project_id: 'missing' }, 'metadata-missing-create')), code('project_missing'));
  assert.equal(f.db().prepare('SELECT COUNT(*) AS n FROM learn_threads').get().n, count);
  assert.equal(f.db().prepare("SELECT COUNT(*) AS n FROM conversation_commands WHERE idempotency_key IN ('metadata-archived-create','metadata-missing-create')").get().n, 0);
  f.db().exec("CREATE TRIGGER synthetic_receipt_failure BEFORE INSERT ON conversation_commands WHEN NEW.idempotency_key='metadata-rollback-key' BEGIN SELECT RAISE(ABORT,'synthetic fail'); END");
  assert.throws(() => f.execute(f.create({}, 'metadata-rollback-key')));
  assert.equal(f.db().prepare('SELECT COUNT(*) AS n FROM learn_threads').get().n, count);
});

test('Test policy, retired commands, deletion frontiers, and saved references cannot be bypassed or silently discarded', () => {
  const f = fixture(), initial = f.execute({ type: 'learning.draft.get', threadId: f.threadId });
  assert.equal(initial.content_refs.length, 6); assert.deepEqual(initial, prepared.seed_receipt);
  activeTest(f);
  for (const c of [f.create(), f.save(prepared.seed_request, 'metadata-python-draft'), { type: 'learning.get', threadId: f.threadId }, { type: 'learning.draft.get', threadId: f.threadId }, list()]) {
    assert.throws(() => f.execute(c), code('assistance_restricted'));
  }
  activeTest(f, false);
  f.transaction(() => f.db().prepare("INSERT INTO learn_command_tombstones VALUES('conversation_commands','metadata-python-draft','now')").run());
  assert.throws(() => f.execute(f.save(prepared.seed_request, 'metadata-python-draft')), code('command_terminal_unavailable'));
  f.transaction(() => f.db().prepare("INSERT INTO deletion_ledger VALUES('conversation_command','metadata-python-create-0','now')").run());
  assert.throws(() => f.execute(f.create()), code('command_terminal_unavailable'));
  f.transaction(() => f.db().prepare("INSERT INTO deletion_ledger VALUES('learn_thread',?,'now')").run(f.threadId));
  assert.throws(() => f.execute({ type: 'learning.get', threadId: f.threadId }), code('conversation_missing'));
  assert.throws(() => f.execute(f.save()), code('conversation_missing'));
  assert.ok(!f.execute(list({ limit: 100 })).items.some(c => c.identity.id === f.threadId));
});

test('reference validation preserves historical version pins and rejects missing/erased/reserved/wrong-owner/display-denied targets atomically', () => {
  const f = fixture();
  const original = f.execute({ type: 'learning.draft.get', threadId: f.threadId });
  const saveRef = (ref, key) => f.execute(f.save({ expected_revision: 2, text: 'SYNTHETIC reference check', content_refs: [ref] }, key));
  const libraryRef = prepared.seed_request.content_refs[0];
  assert.throws(() => saveRef({ target: { type: 'library_revision', id: 'absent' }, locator: null }, 'missing-reference'), code('content_unavailable'));
  f.transaction(() => f.db().prepare("UPDATE knowledge_revisions SET rights_json='{}' WHERE id='synthetic_rev1'").run());
  assert.throws(() => saveRef(libraryRef, 'display-denied-reference'), code('content_unavailable'));
  f.transaction(() => f.db().prepare("UPDATE knowledge_revisions SET rights_json=? WHERE id='synthetic_rev1'").run(JSON.stringify({ display: true })));
  f.transaction(() => f.db().prepare("UPDATE knowledge_documents SET reserved=1 WHERE id='synthetic_doc'").run());
  assert.throws(() => saveRef(libraryRef, 'reserved-reference'), code('content_unavailable'));
  f.transaction(() => f.db().prepare("UPDATE knowledge_documents SET reserved=0 WHERE id='synthetic_doc'").run());
  f.transaction(() => f.db().prepare("INSERT INTO deletion_ledger VALUES('revision','synthetic_rev1','now')").run());
  assert.throws(() => saveRef(libraryRef, 'erased-reference'), code('content_unavailable'));
  const other = prepared.threads[1].identity.id;
  assert.throws(() => f.execute({ ...f.save({ expected_revision: 1, text: 'SYNTHETIC', content_refs: [prepared.seed_request.content_refs[4]] }, 'wrong-owner-reference'), threadId: other }), code('content_unavailable'));
  f.transaction(() => f.db().prepare("INSERT INTO deletion_ledger VALUES('saved_test','synthetic_test','now')").run());
  assert.throws(() => saveRef(prepared.seed_request.content_refs[5], 'deleted-test-reference'), code('content_unavailable'));
  assert.deepEqual(f.execute({ type: 'learning.draft.get', threadId: f.threadId }), original, 'retained draft refs are never filtered away');
  assert.equal(f.db().prepare("SELECT COUNT(*) AS n FROM conversation_commands WHERE operation='draft'").get().n, 1, 'failed validations leave no receipt/revision mutation');
});

test('saved list cursor is scoped/stable/bounded, includes metadata updates, excludes Archive/deletions and lazily adapts legacy owners', () => {
  const f = fixture();
  f.transaction(() => {
    f.db().prepare("UPDATE learn_conversations SET lifecycle='archived' WHERE thread_id=?").run(prepared.threads[5].identity.id);
    for (let i = 0; i < 5; i++) {
      f.db().prepare('UPDATE learn_threads SET updated_at=? WHERE id=?').run('2026-10-26T00:00:0' + i + '.000+00:00', prepared.threads[i].identity.id);
      f.db().prepare('UPDATE learn_conversations SET updated_at=? WHERE thread_id=?').run('2026-10-26T01:00:0' + i + '.000+00:00', prepared.threads[i].identity.id);
    }
  });
  const first = f.execute(list()); assert.equal(first.items.length, 2); assert.ok(first.next_cursor);
  assert.equal(first.items[0].identity.id, prepared.threads[4].identity.id);
  assert.equal(first.items[0].updated_at, '2026-10-26T01:00:04.000+00:00');
  assert.throws(() => f.execute(list({ lifecycle: 'archived', cursor: first.next_cursor })), code('invalid_cursor'));
  assert.throws(() => f.execute(list({ projectId: 'synthetic_project', cursor: first.next_cursor })), code('invalid_cursor'));
  assert.throws(() => f.execute(list({ cursor: first.next_cursor.slice(0, -4) + 'AAAA' })), code('invalid_cursor'));
  f.transaction(() => f.db().prepare("INSERT INTO deletion_ledger VALUES('learn_thread',?,'now')").run(prepared.threads[2].identity.id));
  const second = f.execute(list({ cursor: first.next_cursor }));
  assert.deepEqual(second.items.map(c => c.identity.id), [prepared.threads[1].identity.id, f.threadId]); assert.equal(second.next_cursor, null);
  assert.equal(f.execute(list({ lifecycle: 'archived' })).items[0].identity.id, prepared.threads[5].identity.id);
  f.transaction(() => f.db().prepare("INSERT INTO learn_threads VALUES('synthetic_legacy','SYNTHETIC legacy',NULL,'direct','2026-10-26T00:00:00.000+00:00','2026-10-26T00:00:00.000+00:00')").run());
  const legacy = f.execute({ type: 'learning.get', threadId: 'synthetic_legacy' }); assert.equal(legacy.revision, 1);
  assert.deepEqual(f.execute({ type: 'learning.draft.get', threadId: 'synthetic_legacy' }), { text: '', content_refs: [], revision: 0, conversation_revision: 1 });
});

test('original Python run receipt status/list are neutral during Test and refuse retired/deleted run frontiers', () => {
  const f = fixture(), status = { type: 'learning.run.status', threadId: f.threadId, runId: 'synthetic_run_1', neutral: false };
  assert.deepEqual(f.execute({ ...status, neutral: true }), prepared.neutral_status);
  const full = f.execute(status); assert.deepEqual(full.error, prepared.status_error);
  assert.deepEqual(full.conversation, f.execute({ type: 'learning.get', threadId: f.threadId }));
  const c = { type: 'learning.runs.list', threadId: f.threadId, limit: 2, cursor: null };
  const first = f.execute(c); assert.deepEqual(first.items.map(r => r.run_id), ['synthetic_run_2', 'synthetic_run_1']);
  const second = f.execute({ ...c, cursor: first.next_cursor }); assert.deepEqual(second.items.map(r => r.run_id), ['synthetic_run_0']);
  assert.throws(() => f.execute({ ...c, threadId: prepared.threads[1].identity.id, cursor: first.next_cursor }), code('invalid_cursor'));
  activeTest(f);
  assert.deepEqual(f.execute(status), prepared.restricted_status);
  assert.deepEqual(f.execute({ ...c, limit: 20 }), prepared.restricted_list);
  f.transaction(() => f.db().prepare("INSERT INTO learn_command_tombstones VALUES('conversation_commands','metadata-python-send-1','now')").run());
  assert.throws(() => f.execute(status), code('conversation_run_missing'));
  f.transaction(() => f.db().prepare("INSERT INTO deletion_ledger VALUES('learn_run','synthetic_run_0','now')").run());
  assert.deepEqual(f.execute({ ...c, limit: 20 }).items.map(r => r.run_id), ['synthetic_run_2']);
  f.transaction(() => f.db().prepare("INSERT INTO deletion_ledger VALUES('learn_thread',?,'now')").run(f.threadId));
  assert.deepEqual(f.execute(c), { items: [], next_cursor: null });
});

test('strict command/result contracts reject extra/missing/nested malformed fields, and executor requires caller transaction', () => {
  const f = fixture();
  assert.throws(() => executeLearningMetadata(f.db(), f.create()), code('learning_transaction_required'));
  const bad = [ null, [], { ...f.create(), extra: true }, { ...f.create(), request: { ...prepared.create_request, temporary: true } },
    { ...f.create(), request: { ...prepared.create_request, kind: 'case' } },
    { ...f.create(), request: { title: 'SYNTHETIC' } },
    { ...f.create(), request: { ...prepared.create_request, images: [] } },
    f.save({ ...prepared.follow_request, expected_revision: '2' }),
    f.save({ ...prepared.follow_request, content_refs: [{ target: { type: 'library_revision', id: 'x' } }] }),
    f.save({ ...prepared.follow_request, content_refs: [{ target: { type: 'library_revision', id: 'x', extra: 1 }, locator: null }] }),
    f.save({ ...prepared.follow_request, content_refs: [{ target: { type: 'saved_test_version', id: 'x' }, locator: { kind: 'pdf', physical_page: 1, printed_label: null } }] }),
    f.save({ ...prepared.follow_request, content_refs: [{ target: { type: 'library_revision', id: 'x' }, locator: { kind: 'text', item_ref: 'x', section: null, start: 1, end: 1 } }] }),
    { type: 'learning.run.status', threadId: f.threadId, runId: 'synthetic_run_1', neutral: 'false' }, list({ limit: 101 }) ];
  for (const value of bad) assert.throws(() => validateLearningMetadataCommand(value), code('storage_invalid_command'));
  const result = f.execute({ type: 'learning.draft.get', threadId: f.threadId });
  assert.throws(() => validateLearningMetadataResult('learning.draft.get', { ...result, extra: true }), code('learning_metadata_invalid_result'));
  assert.throws(() => validateLearningMetadataResult('learning.create', { ...prepared.threads[0], retention: 'temporary' }), code('learning_metadata_invalid_result'));
  assert.throws(() => validateLearningMetadataResult('learning.runs.list', { items: [{ run_id: 'x', state: 'completed', error: {} }], next_cursor: null }), code('learning_metadata_invalid_result'));
});

test('actual StorageClient routes all metadata variants with Python differential draft/replay and explicit send-reference refusal', { timeout: 60000 }, async () => {
  const f = fixture();
  const selection = { contract: 'renulus-storage-selector/1', isolation: 'synthetic', profileId: 'synthetic-metadata',
    generation: 1, authorityEpoch: 1, writer: 'ts', state: 'active', ownerId: 'synthetic-metadata-owner', database: 'state/renulus.sqlite3' };
  writeFileSync(join(f.profile, MARKER), JSON.stringify({ contract: 'renulus-synthetic-storage/1', profileId: selection.profileId }));
  writeFileSync(join(f.profile, SELECTOR), JSON.stringify(selection));
  f.close(); // No second canonical connection while the actual writer owns the profile.
  const storage = await openIsolatedStorage({ profileRoot: f.profile, selection, migrations, expectedSchemaHash: f.schemaHash });
  let created;
  try {
    assert.deepEqual(await storage.command(f.create()), prepared.threads[0]);
    assert.deepEqual(await storage.command(f.save()), prepared.follow_receipt);
    assert.deepEqual(await storage.command(f.save()), prepared.follow_replay);
    assert.deepEqual(await storage.command({ type: 'learning.draft.get', threadId: f.threadId }), prepared.follow_receipt);
    assert.equal((await storage.command({ type: 'learning.get', threadId: f.threadId })).revision, 3);
    assert.equal((await storage.command(list({ limit: 100 }))).items.length, 6);
    assert.deepEqual((await storage.command({ type: 'learning.runs.list', threadId: f.threadId, limit: 100, cursor: null })).items, prepared.restricted_list.items);
    assert.deepEqual(await storage.command({ type: 'learning.run.status', threadId: f.threadId, runId: 'synthetic_run_1', neutral: true }), prepared.neutral_status);
    await assert.rejects(storage.command({ type: 'learning.begin', threadId: f.threadId, expectedRevision: 3, expectedDraftRevision: 2,
      text: 'SYNTHETIC never dispatch referenced draft', idempotencyKey: 'synthetic-no-discard-send', runId: 'synthetic_no_discard', attemptId: '1',
      identity: { profileId: 'synthetic-metadata', storeId: 'synthetic-store', generation: 'synthetic-generation' } }), code('learning_reference_input_not_admitted'));
    assert.deepEqual(await storage.command({ type: 'learning.draft.get', threadId: f.threadId }), prepared.follow_receipt);
    created = await storage.command(f.create({ title: 'SYNTHETIC worker create', project_id: 'synthetic_project' }, 'metadata-worker-create'));
    assert.equal(created.project_id, 'synthetic_project');
    await assert.rejects(storage.command({ ...f.create(), surprise: true }), code('storage_invalid_command'));
  } finally { await storage.close(); }
  const reopened = await openIsolatedStorage({ profileRoot: f.profile, selection, migrations, expectedSchemaHash: f.schemaHash });
  try {
    assert.deepEqual(await reopened.command({ type: 'learning.get', threadId: created.identity.id }), created);
    assert.deepEqual(await reopened.command(f.save()), prepared.follow_receipt);
    assert.deepEqual(await reopened.command({ type: 'learning.draft.get', threadId: f.threadId }), prepared.follow_receipt);
  } finally { await reopened.close(); }
});
