// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { spawnSync } from 'node:child_process';
import { DatabaseSync } from 'node:sqlite';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { openIsolatedStorage } from '../src/storage/index.ts';
import { inventory, loadMigrationInventory } from '../src/storage/schema.ts';
import { MARKER, SELECTOR } from '../src/storage/ownership.ts';
import { openEngineWorker } from '../src/workers/process.ts';
import { createWorkerContent } from '../src/workers/content.ts';
import { openTargetFacade } from '../src/http/target.ts';

const repository = fileURLToPath(new URL('../../..', import.meta.url));
const python = process.env.RENULUS_BACKEND_TEST_PYTHON ?? 'C:/Renulus/dev/python/Scripts/python.exe';
const prepare = String.raw`
import sys, json, hashlib, shutil
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1])/'runtime'))
from renulus.server import create_app
from renulus.content.validation import validate_pack, PackValidationError, coverage_for
root = Path(sys.argv[2]); packs = root/'packs'; packs.mkdir()
s = create_app(root/'profile').state.services
topics=[]; questions=[]; cases=[]
review=dict(status='assistant_reviewed', reviewer='Synthetic reviewer', reviewer_kind='assistant',
 reviewed_on='2026-10-01', method='Synthetic schema fixture', source_key_checked=True, independent_human_review=False)
for i, label in enumerate(['AKI', 'CKD', 'Glomerular', 'Dialysis', 'Transplant', 'Electrolytes']):
 tid='S16-T'+str(i); objectives=[dict(id=tid+'-O'+str(j), text='Synthetic objective '+str(j)) for j in range(2)]
 topics.append(dict(id=tid, version=1, label=label, description='Synthetic topic', objectives=objectives,
  mapping=dict(general_nephrology=True, esen_eph='not_formally_mapped'), license='CC-BY-4.0'))
 common=dict(version=1, topic_id=tid, secondary_topic_ids=[], objective_ids=[o['id'] for o in objectives],
  license='CC-BY-4.0', original=True, sources=[dict(source_id='S16-source', locator='Synthetic locator')], review=review)
 questions.append(dict(common, id='S16-Q'+str(i), family_id='S16-F'+str(i), family_version=1, key_version=1,
  kind='single_best_answer', usage='assessment_reserved', stem='Synthetic '+label+' question',
  options=[dict(id=str(j), text='Synthetic option '+str(j), rationale='Synthetic rationale') for j in range(4)],
  answer='0', rationale='Synthetic rationale', difficulty='foundation'))
 cases.append(dict(common, id='S16-C'+str(i), synthetic=True, usage='teaching', title='Synthetic '+label,
  summary='Synthetic case', stages=[dict(id='stage'+str(j), narrative='Synthetic narrative', prompts=['Synthetic prompt'],
   teaching_points=['Synthetic teaching'], sources=common['sources']) for j in range(2)], take_home=['Synthetic learning']))
sources=[dict(id='S16-source', register_id='K01', title='Synthetic source fixture', edition='Synthetic',
 publication_status='final', url='https://example.org/synthetic', canonical_topic_url='https://example.org/synthetic',
 checked_on='2026-10-01', check_status='locator_checked', currency='dated_final_baseline', scope='Synthetic only',
 rights_note='Synthetic original fixture', check_note='Synthetic check')]
coverage=coverage_for(topics,cases,questions,[t['id'] for t in topics],6)
manifest=dict(schema_version=1, repository_contract=1, id='s16-synthetic', version='1.0.0', state='published',
 published_on='2026-10-01', title='Synthetic content validation', license='CC-BY-4.0', authors=['Synthetic author'],
 attribution='Synthetic fixture CC BY 4.0', source_register='docs/SOURCES.md', files={},
 claims=dict(complete_curriculum=False, complete_esen_eph_blueprint=False, independent_human_review=False), withdrawals=[])
good=packs/'good'; good.mkdir()
for name, value in dict(topics=topics, cases=cases, questions=questions, sources=sources, coverage=coverage).items():
 raw=json.dumps(value).encode(); (good/(name+'.json')).write_bytes(raw)
 manifest['files'][name]=dict(path=name+'.json', sha256=hashlib.sha256(raw).hexdigest())
(good/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
pack=validate_pack(good)
expected=dict(id=pack.manifest['id'], version=pack.manifest['version'], sha256=pack.sha256, valid=True,
 questions=len(pack.bundle['questions']), cases=len(pack.bundle['cases']))
errors={}
for kind in ['bad-hash', 'missing-key', 'reserved']:
 target=packs/kind; shutil.copytree(good,target)
 qs=json.loads((target/'questions.json').read_text())
 if kind=='bad-hash': (target/'questions.json').write_text(json.dumps(qs)+' ',encoding='utf-8')
 else:
  if kind=='missing-key': del qs[0]['answer']
  else: qs[0]['usage']='evaluation_reserved'
  raw=json.dumps(qs).encode(); (target/'questions.json').write_bytes(raw)
  m=json.loads((target/'manifest.json').read_text()); m['files']['questions']['sha256']=hashlib.sha256(raw).hexdigest()
  (target/'manifest.json').write_text(json.dumps(m),encoding='utf-8')
 try: validate_pack(target); raise AssertionError('Invalid fixture accepted')
 except PackValidationError as e: errors[kind]=dict(code='invalid_content_pack', message=str(e))
print(json.dumps(dict(database=str(s.paths.database),expected=expected,errors=errors)))
`;

test('owned Python validator: HTTP validation is read-only; hashes, keys and reserved coverage reject; install activates', { timeout: 120_000 }, async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'renulus-s16-'));
  let storage, worker, facade;
  try {
    const env = Object.fromEntries(['SystemRoot', 'WINDIR', 'TEMP', 'TMP'].filter(k => process.env[k]).map(k => [k, process.env[k]]));
    env.PATH = path.dirname(python);
    const result = spawnSync(python, ['-I', '-X', 'utf8', '-c', prepare, repository, root], { env, encoding: 'utf8', timeout: 60_000, windowsHide: true });
    assert.equal(result.status, 0, result.stderr);
    const prepared = JSON.parse(result.stdout.trim());
    const migrations = loadMigrationInventory(repository);
    const db = new DatabaseSync(prepared.database);
    const expectedSchemaHash = inventory(db, migrations).schemaHash;
    db.close();
    const profileRoot = path.join(root, 'profile');
    const selection = { contract: 'renulus-storage-selector/1', isolation: 'synthetic', profileId: 's16-synthetic', generation: 1,
      authorityEpoch: 1, writer: 'ts', state: 'active', ownerId: 's16-owner', database: 'state/renulus.sqlite3' };
    await writeFile(path.join(profileRoot, MARKER), JSON.stringify({ contract: 'renulus-synthetic-storage/1', profileId: selection.profileId }));
    await writeFile(path.join(profileRoot, SELECTOR), JSON.stringify(selection));
    storage = await openIsolatedStorage({ profileRoot, selection, migrations, expectedSchemaHash });
    worker = await openEngineWorker({ python, sourceRoot: repository, launchRoot: path.join(root, 'launch'), retention: 'saved',
      identity: { profile_id: 's16-synthetic', domain_store_id: 's16-domain', runtime_store_id: 's16-native', authority_epoch: 1, process_generation: 's16-generation' },
      current: () => ({ configuration: 1, grant: 1, context: 1, deletion: 1, cancellation: 0 }) });
    assert.ok(worker.ready.supported_commands.includes('content.validate'));
    const content = createWorkerContent(worker.channel, worker.ready.capacity.max_chunk_bytes, path.join(root, 'packs'));
    facade = await openTargetFacade({ port: 0, token: 's16-synthetic-token', storage, content, settlePlugins: () => worker.close() });
    const call = async (route, selected) => {
      const response = await fetch('http://127.0.0.1:' + facade.port + '/api/v1/content/' + route, {
        method: selected === undefined ? 'GET' : 'POST', headers: { 'x-renulus-token': 's16-synthetic-token', 'content-type': 'application/json' },
        ...(selected === undefined ? {} : { body: JSON.stringify({ path: selected }) }) });
      return { status: response.status, value: await response.json() };
    };
    const counts = () => {
      const db = new DatabaseSync(prepared.database, { readOnly: true });
      try { return Object.fromEntries(db.prepare("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").all()
        .map(({ name }) => [name, db.prepare('SELECT COUNT(*) AS n FROM "' + name.replaceAll('"', '""') + '"').get().n])); }
      finally { db.close(); }
    };
    const before = counts();
    assert.deepEqual(await call('packs/validate', 'good'), { status: 200, value: prepared.expected });
    for (const kind of ['bad-hash', 'missing-key', 'reserved']) {
      const rejected = await call('packs/validate', kind);
      assert.equal(rejected.status, 422, JSON.stringify(rejected));
      assert.equal(rejected.value.error.code, prepared.errors[kind].code);
      assert.deepEqual(counts(), before);
    }
    assert.equal((await call('packs/validate', '../profile')).value.error.code, 'invalid_pack_path');
    assert.deepEqual(counts(), before);
    const installed = await call('packs/install', 'good');
    assert.equal(installed.status, 200, JSON.stringify(installed));
    assert.equal(installed.value.active, true);
    assert.equal(installed.value.sha256, prepared.expected.sha256);
    assert.equal((await call('manifest')).value.id, prepared.expected.id);
    assert.equal(worker.channel.state().unsettled, 0);
  } finally {
    if (facade) await facade.close();
    else { await worker?.close(); await storage?.close(); }
    assert.ok(path.resolve(root).startsWith(path.resolve(tmpdir()) + path.sep));
    await rm(root, { recursive: true, force: true });
  }
});
