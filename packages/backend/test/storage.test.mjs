// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import { spawn, spawnSync } from 'node:child_process';
import { once } from 'node:events';
import { createHash } from 'node:crypto';
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { basename, dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { openIsolatedStorage, previewStorage, loadMigrationInventory, MARKER, SELECTOR, OWNER } from '../src/storage/index.ts';

const repository = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const python = process.env.RENULUS_STORAGE_TEST_PYTHON || 'C:/Renulus/dev/python/Scripts/python.exe';
const fixtureRoot = mkdtempSync(join(tmpdir(), 'renulus-storage-bf00-test-'));
const environment = Object.fromEntries(['SystemRoot', 'WINDIR', 'TEMP', 'TMP'].filter(key => process.env[key]).map(key => [key, process.env[key]]));
environment.PATH = dirname(python);
const migrations = loadMigrationInventory(repository);
let fixture;

function runPython(script, ...args) {
  const result = spawnSync(python, ['-I', '-X', 'utf8', '-c', script, repository, ...args], { encoding: 'utf8', env: environment, timeout: 60000, maxBuffer: 24 * 1024 * 1024 });
  assert.equal(result.status, 0, result.stderr || result.error?.message);
  return JSON.parse(result.stdout);
}
const imports = `
import sys,json,sqlite3,hashlib
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(sys.argv[1])/'runtime'))
from renulus.storage.backup import export_records,validate_records
`;
function normalized(bundle) {
  const copy = structuredClone(bundle);
  delete copy.exported_at;
  for (const records of Object.values(copy.records)) records.sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b)));
  return copy;
}
function selection(overrides = {}) {
  return { contract: 'renulus-storage-selector/1', isolation: 'synthetic', profileId: 'synthetic-bf00', generation: 1,
    authorityEpoch: 1, writer: 'ts', state: 'active', ownerId: 'synthetic-storage-owner', database: 'state/renulus.sqlite3', ...overrides };
}
function admit(profile, selected = selection()) {
  writeFileSync(join(profile, MARKER), JSON.stringify({ contract: 'renulus-synthetic-storage/1', profileId: selected.profileId }));
  writeFileSync(join(profile, SELECTOR), JSON.stringify(selected));
  return { profileRoot: profile, selection: selected, migrations, expectedSchemaHash: fixture.schemaHash };
}
function hash(path) { return createHash('sha256').update(readFileSync(path)).digest('hex'); }
function fork(name) {
  const profile = join(fixtureRoot, name);
  // Python's backup primitive creates each owned populated target without reopening a domain/provider assembly.
  runPython(imports + `
target=Path(sys.argv[3]);target.parent.mkdir(parents=True,exist_ok=True)
source=sqlite3.connect(Path(sys.argv[2]).as_uri()+'?mode=ro',uri=True)
destination=sqlite3.connect(target);source.backup(destination);destination.close();source.close()
print('{}')
`, fixture.databasePath, join(profile, 'state/renulus.sqlite3'));
  return profile;
}

before(() => {
  assert.equal(process.versions.node, '26.4.0', 'Use the prepared Node26 artifact; never skip the real sqlite proof.');
  fixture = runPython(imports + `
from renulus.server import create_app
from renulus.learn.conversation_models import NewConversation
from renulus.design_c_contracts import canonical_digest,TABLE_COLUMNS
root=Path(sys.argv[2]);s=create_app(root).state.services
threads=[]
for i,title in enumerate(['Electrolytes','AKI','CKD','Glomerular disease','Transplantation']):
    threads.append(s.registry['conversations'].create(NewConversation(kind='learning',title='SYNTHETIC '+title),f'bf00-create-{i}'))
doc=s.registry['knowledge'].import_text('SYNTHETIC educational CKD text',process=False)
with s.db.transaction() as c:
    c.execute("INSERT INTO preferences VALUES('study.goals','[]','now')")
    c.execute("INSERT INTO preferences VALUES('synthetic.secret','SYNTHETIC-DO-NOT-EXPORT','now')")
    c.execute("INSERT INTO learning_evidence VALUES('bf00-evidence','synthetic','aki',?,'{}','now')",(threads[0]['identity']['id'],))
    c.execute("INSERT INTO deletion_ledger VALUES('learn_thread','synthetic-removed','now')")
    c.execute("INSERT INTO learn_runs VALUES('bf00-run',?,'bf00-run-key','completed',NULL,'now','now')",(threads[0]['identity']['id'],))
    c.execute("INSERT INTO learn_messages VALUES('bf00-msg',?,'bf00-run','assistant','SYNTHETIC answer','[]','now')",(threads[0]['identity']['id'],))
    c.execute("CREATE TRIGGER bf00_force_rollback BEFORE INSERT ON conversation_commands WHEN NEW.idempotency_key='bf00-rollback-key' BEGIN SELECT RAISE(ABORT,'synthetic failure after mutation'); END")
with s.db.connect() as c:
    def query(sql):return [dict(row) for row in c.execute(sql)]
    objects=query("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name")
    tables=[]
    for o in objects:
        if o['type']!='table':continue
        name=o['name'];indexes=[]
        for definition in query(f'PRAGMA index_list("{name}")'):
            indexes.append({'definition':definition,'columns':query('PRAGMA index_xinfo("'+definition['name']+'")')})
        tables.append({'name':name,'columns':query(f'PRAGMA table_xinfo("{name}")'),'foreignKeys':query(f'PRAGMA foreign_key_list("{name}")'),'indexes':indexes})
    schema_hash=canonical_digest({'objects':objects,'tables':tables})
    ledger=query('SELECT name,checksum FROM migration_ledger ORDER BY name')
    columns={name:[dict(row)['name'] for row in c.execute(f'PRAGMA table_info("{name}")')] for name in TABLE_COLUMNS}
print(json.dumps({'databasePath':str(s.paths.database),'schemaHash':schema_hash,'migrations':ledger,'columns':columns,'threads':threads,'export':export_records(s)},ensure_ascii=False))
`, join(fixtureRoot, 'python-source'));
});
after(() => {
  // Only the absolute directory created by this test is eligible for cleanup.
  assert.match(basename(fixtureRoot), /^renulus-storage-bf00-test-/);
  assert.equal(dirname(fixtureRoot), resolve(tmpdir()));
  rmSync(fixtureRoot, { recursive: true, force: true });
});

test('real Node26 previews populated Python schema2 with exact schema/ledger/foreign-key parity and no database mutation', async () => {
  const beforeHash = hash(fixture.databasePath);
  const preview = await previewStorage({ databasePath: fixture.databasePath, migrations, expectedSchemaHash: fixture.schemaHash });
  assert.equal(preview.compatible, true, JSON.stringify(preview.issues));
  assert.equal(preview.schemaVersion, 2);
  assert.equal(preview.schemaHash, fixture.schemaHash);
  assert.deepEqual(preview.migrations, fixture.migrations);
  assert.deepEqual(preview.foreignKeyViolations, []);
  for (const [name, columns] of Object.entries(fixture.columns)) assert.deepEqual(preview.tables.find(table => table.name === name).columns.map(column => column.name), columns);
  assert.equal(preview.tables.find(table => table.name === 'learn_threads').rowCount, 5);
  assert.equal(hash(fixture.databasePath), beforeHash);
  assert.equal(existsSync(join(dirname(fixture.databasePath), 'storage-owner.json')), false);
});

test('read-only preview refuses changed/unknown/pending migrations and incompatible schema without applying migrations', async () => {
  const changed = { ...migrations, 'learn-001': '0'.repeat(64) };
  const altered = await previewStorage({ databasePath: fixture.databasePath, migrations: changed });
  assert.equal(altered.compatible, false);
  assert.ok(altered.issues.includes('storage_migration_changed:learn-001'));
  const unknown = { ...migrations }; delete unknown['learn-001'];
  assert.ok((await previewStorage({ databasePath: fixture.databasePath, migrations: unknown })).issues.includes('storage_migration_unknown:learn-001'));
  assert.ok((await previewStorage({ databasePath: fixture.databasePath, migrations: { ...migrations, 'synthetic-future': '0'.repeat(64) } })).issues.includes('storage_migrations_pending'));
  assert.ok((await previewStorage({ databasePath: fixture.databasePath, migrations, expectedSchemaHash: '0'.repeat(64) })).issues.includes('storage_schema_inventory_changed'));
  const profile = fork('future-schema');
  const path = join(profile, 'state/renulus.sqlite3');
  runPython(imports + "\nc=sqlite3.connect(sys.argv[2]);c.execute('PRAGMA user_version=3');c.close();print('{}')", path);
  const futureHash = hash(path);
  assert.ok((await previewStorage({ databasePath: path, migrations })).issues.includes('storage_schema_unsupported'));
  const options = admit(profile);
  await assert.rejects(openIsolatedStorage(options), { code: 'storage_schema_unsupported' });
  assert.equal(hash(path), futureHash);
  assert.equal(existsSync(join(profile, OWNER)), false);
});

test('strict paginated commands and portable export match Python, excluding protected settings and acquisition paths', async () => {
  const profile = fork('export'); const client = await openIsolatedStorage(admit(profile));
  try {
    const first = await client.command({ type: 'records.page', table: 'learn_threads', offset: 0, limit: 2 });
    assert.equal(first.rows.length, 2); assert.equal(first.nextOffset, 2);
    const second = await client.command({ type: 'records.page', table: 'learn_threads', offset: 2, limit: 2 });
    assert.equal(second.nextOffset, 4);
    assert.equal(new Set([...first.rows, ...second.rows].map(row => row.id)).size, 4);
    const bundle = await client.command({ type: 'records.export' });
    assert.deepEqual(normalized(bundle), normalized(fixture.export));
    assert.equal(JSON.stringify(bundle).includes('SYNTHETIC-DO-NOT-EXPORT'), false);
    for (const command of [
      { type: 'sql', sql: 'DROP TABLE learn_threads' },
      { type: 'records.page', table: 'learn_threads', offset: 0, limit: 101 },
      { type: 'records.export', sql: 'SELECT 1' },
      { type: 'database.backup', name: '../escape' },
      { type: 'learning.rename', threadId: 't', title: 'x', expectedRevision: '1', idempotencyKey: 'valid-key' },
    ]) await assert.rejects(client.command(command), { code: 'storage_invalid_command' });
    for (const table of ['migration_ledger', 'knowledge_catalogue', 'harness_configurations', 'preferences; DROP TABLE learn_threads']) {
      await assert.rejects(client.command({ type: 'records.page', table, offset: 0, limit: 1 }), { code: 'backup_table' });
    }
  } finally { await client.close(); }
});

test('rename commits local revision, context epoch and Python-compatible idempotent receipt; conflict/failure roll back atomically', async () => {
  const profile = fork('transactions'); const options = admit(profile);
  const client = await openIsolatedStorage(options);
  const threadId = fixture.threads[0].identity.id;
  const command = { type: 'learning.rename', threadId, expectedRevision: 1, title: 'SYNTHETIC AKI \u2014 renal learning', idempotencyKey: 'bf00-rename-key' };
  let result;
  try {
    result = await client.command(command);
    assert.equal(result.revision, 2); assert.equal(result.title, command.title);
    assert.deepEqual(await client.command(command), result);
    await assert.rejects(client.command({ ...command, title: 'SYNTHETIC other' }), { code: 'idempotency_conflict' });
    await assert.rejects(client.command({ ...command, idempotencyKey: 'bf00-stale-key' }), { code: 'conversation_revision_conflict' });
    const before = normalized(await client.command({ type: 'records.export' }));
    await assert.rejects(client.command({ ...command, expectedRevision: 2, title: 'SYNTHETIC rollback', idempotencyKey: 'bf00-rollback-key' }));
    assert.deepEqual(normalized(await client.command({ type: 'records.export' })), before);
    const attempts = await Promise.allSettled([
      client.command({ ...command, expectedRevision: 2, title: 'SYNTHETIC winner A', idempotencyKey: 'bf00-winner-a' }),
      client.command({ ...command, expectedRevision: 2, title: 'SYNTHETIC winner B', idempotencyKey: 'bf00-winner-b' }),
    ]);
    assert.equal(attempts.filter(value => value.status === 'fulfilled').length, 1);
    assert.equal(attempts.find(value => value.status === 'rejected').reason.code, 'conversation_revision_conflict');
  } finally { await client.close(); }
  const proof = runPython(imports + `
from renulus.server import create_app
from renulus.learn.conversation_models import Rename
s=create_app(Path(sys.argv[2])).state.services
request=Rename(expected_revision=1,title='SYNTHETIC AKI \u2014 renal learning')
replayed=s.registry['conversations'].change('learning',sys.argv[3],request,'rename','bf00-rename-key')
print(json.dumps({'replayed':replayed,'revision':s.db.fetch_one('SELECT revision FROM learn_conversations WHERE thread_id=?',(sys.argv[3],))['revision'],
'epoch':s.db.fetch_one("SELECT value FROM preferences WHERE key='design_c.context_epoch'")['value'],
'rollback_receipt':s.db.fetch_one("SELECT * FROM conversation_commands WHERE idempotency_key='bf00-rollback-key'")}))
`, profile, threadId);
  assert.deepEqual(proof.replayed, result);
  assert.equal(proof.revision, 3); assert.equal(proof.epoch, '2'); assert.equal(proof.rollback_receipt, null);
});

test('native SQLite backup is independently readable/exportable/validatable by Python and preserves canonical queries', async () => {
  const profile = fork('backup'); const client = await openIsolatedStorage(admit(profile));
  let saved, bundle;
  try {
    saved = await client.command({ type: 'database.backup', name: 'synthetic-complete' });
    assert.ok(saved.pages > 0);
    bundle = await client.command({ type: 'records.export' });
    await assert.rejects(client.command({ type: 'database.backup', name: 'synthetic-complete' }), { code: 'storage_backup_exists' });
  } finally { await client.close(); }
  const exportPath = join(profile, 'bundle.json'); writeFileSync(exportPath, JSON.stringify(bundle));
  const proof = runPython(imports + `
class ReadOnly:
    def connect(self):
        c=sqlite3.connect(Path(sys.argv[2]).as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;return c
db=ReadOnly();c=db.connect();bundle=json.loads(Path(sys.argv[3]).read_text(encoding='utf-8'));validate_records(c,bundle)
result={'schema':c.execute('PRAGMA user_version').fetchone()[0],'integrity':c.execute('PRAGMA integrity_check').fetchone()[0],
'foreign_keys':[dict(row) for row in c.execute('PRAGMA foreign_key_check')],
'message':dict(c.execute("SELECT content,role FROM learn_messages WHERE id='bf00-msg'").fetchone()),
'export':export_records(SimpleNamespace(db=db))};c.close();print(json.dumps(result,ensure_ascii=False))
`, saved.path, exportPath);
  assert.equal(proof.schema, 2); assert.equal(proof.integrity, 'ok'); assert.deepEqual(proof.foreign_keys, []);
  assert.deepEqual(proof.message, { content: 'SYNTHETIC answer', role: 'assistant' });
  assert.deepEqual(normalized(proof.export), normalized(bundle));
});

test('prepared/python selectors, stale epochs, owner conflicts and changed owners fail closed', async () => {
  const profile = fork('admission');
  const options = admit(profile, selection({ writer: 'python', state: 'prepared' }));
  const original = hash(join(profile, 'state/renulus.sqlite3'));
  await assert.rejects(openIsolatedStorage(options), { code: 'storage_writer_not_selected' });
  assert.equal(hash(join(profile, 'state/renulus.sqlite3')), original);
  const active = admit(profile);
  await assert.rejects(openIsolatedStorage({ ...active, selection: selection({ authorityEpoch: 2 }) }), { code: 'storage_selector_stale' });
  const client = await openIsolatedStorage(active);
  try {
    await assert.rejects(openIsolatedStorage(active), { code: 'storage_owner_busy' });
    writeFileSync(join(profile, SELECTOR), JSON.stringify(selection({ authorityEpoch: 2 })));
    await assert.rejects(client.command({ type: 'records.export' }), { code: 'storage_selector_stale' });
    await assert.rejects(client.command({ type: 'learning.rename', threadId: fixture.threads[0].identity.id, expectedRevision: 1,
      title: 'SYNTHETIC stale', idempotencyKey: 'bf00-stale-owner' }), { code: 'storage_selector_stale' });
    writeFileSync(join(profile, SELECTOR), JSON.stringify(selection()));
    writeFileSync(join(profile, OWNER), '{}');
    await assert.rejects(client.command({ type: 'records.export' }), { code: 'storage_owner_stale' });
  } finally { await client.close(); }
  assert.equal(readFileSync(join(profile, OWNER), 'utf8'), '{}', 'Do not remove an ambiguous successor lock');
});

test('active Test and retired command prevent idempotency replay', async () => {
  const profile = fork('policy'); const options = admit(profile);
  const command = { type: 'learning.rename', threadId: fixture.threads[0].identity.id, expectedRevision: 1,
    title: 'SYNTHETIC policy', idempotencyKey: 'bf00-policy-key' };
  let client = await openIsolatedStorage(options);
  await client.command(command); await client.close();
  runPython(imports + `
c=sqlite3.connect(sys.argv[2]);c.execute("INSERT INTO assessment_test_attempts(id,version_id,version_snapshot_json,mode,clock_high_water_at,created_at,updated_at) VALUES('synthetic-active-test','synthetic-version','{}','test','now','now','now')");c.commit();c.close();print('{}')
`, join(profile, 'state/renulus.sqlite3'));
  client = await openIsolatedStorage(options);
  try { await assert.rejects(client.command(command), { code: 'assistance_restricted' }); }
  finally { await client.close(); }
  runPython(imports + `
c=sqlite3.connect(sys.argv[2]);c.execute("UPDATE assessment_test_attempts SET status='submitted'");c.execute("INSERT INTO learn_command_tombstones VALUES('conversation_commands','bf00-policy-key','now')");c.commit();c.close();print('{}')
`, join(profile, 'state/renulus.sqlite3'));
  client = await openIsolatedStorage(options);
  try { await assert.rejects(client.command(command), { code: 'command_terminal_unavailable' }); }
  finally { await client.close(); }
});

test('SQLite contention leaves the caller pump responsive; overload rejects before effects and close drains admitted work', async () => {
  const profile = fork('contention'); const client = await openIsolatedStorage(admit(profile));
  const script = `import sqlite3,sys\nc=sqlite3.connect(sys.argv[1]);c.execute('BEGIN IMMEDIATE');print('locked',flush=True);sys.stdin.readline();c.rollback();c.close()`;
  const holder = spawn(python, ['-I', '-X', 'utf8', '-c', script, join(profile, 'state/renulus.sqlite3')], { env: environment, stdio: ['pipe', 'pipe', 'pipe'] });
  const exited = once(holder, 'exit');
  try {
    assert.equal(String((await once(holder.stdout, 'data'))[0]).trim(), 'locked');
    let settled = false;
    const mutation = client.command({ type: 'learning.rename', threadId: fixture.threads[0].identity.id, expectedRevision: 1,
      title: 'SYNTHETIC contention', idempotencyKey: 'bf00-contention-key' }).finally(() => { settled = true; });
    const reads = Array.from({ length: 63 }, () => client.command({ type: 'records.page', table: 'learn_threads', offset: 0, limit: 1 }));
    await assert.rejects(client.command({ type: 'records.export' }), { code: 'storage_overloaded' });
    const closing = client.close();
    await assert.rejects(client.command({ type: 'records.export' }), { code: 'storage_closed' });
    await new Promise(resolve => setTimeout(resolve, 100));
    assert.equal(settled, false, 'Caller timers continue while the canonical thread is waiting for the SQLite lock');
    holder.stdin.end('\n');
    assert.equal((await mutation).revision, 2);
    assert.equal((await Promise.all(reads)).length, 63);
    await closing;
    assert.equal(existsSync(join(profile, OWNER)), false);
  } finally {
    if (!holder.stdin.writableEnded) holder.stdin.end('\n');
    await exited;
    await client.close();
  }
});
