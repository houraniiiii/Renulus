// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { spawnSync } from 'node:child_process';
import { DatabaseSync } from 'node:sqlite';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { openIsolatedStorage, MARKER, SELECTOR, loadMigrationInventory } from '../src/storage/index.ts';
import { inventory } from '../src/storage/schema.ts';
import { openTargetFacade } from '../src/http/target.ts';
import { createStudyCoordinator } from '../src/domain/study/coordinator.ts';
import { createUpdatesCoordinator } from '../src/domain/updates/coordinator.ts';

function compareKeys(python, target, path, mismatches) {
  if (python === null || typeof python !== 'object') return;
  if (target === null || typeof target !== 'object' || Array.isArray(python) !== Array.isArray(target)) {
    mismatches.push(path + ': expected ' + (Array.isArray(python) ? 'array' : 'object')); return;
  }
  if (Array.isArray(python)) {
    if (target.length !== python.length) mismatches.push(path + ': array lengths ' + python.length + '/' + target.length);
    python.forEach((value, index) => compareKeys(value, target[index], path + '[' + index + ']', mismatches)); return;
  }
  for (const key of Object.keys(python)) {
    if (!Object.hasOwn(target, key)) mismatches.push(path + '.' + key + ': missing');
    else compareKeys(python[key], target[key], path + '.' + key, mismatches);
  }
  for (const key of Object.keys(target)) if (key !== 'revision' && !Object.hasOwn(python, key)) mismatches.push(path + '.' + key + ': extra');
}

test('populated Python owner and TS HTTP target retain Study, Home, Nightly and Updates response keys', {
  skip: !process.env.RENULUS_BACKEND_TEST_PYTHON, timeout: 90_000,
}, async () => {
  const repository = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
  const root = mkdtempSync('C:/Renulus/scratch/shape-parity-bf06-'), python = process.env.RENULUS_BACKEND_TEST_PYTHON;
  let storage, facade, study, updates;
  try {
    const script = `
import sys,json
from pathlib import Path
from datetime import date,timedelta,datetime,timezone
sys.path.insert(0,str(Path(sys.argv[1])/'runtime'))
from fastapi.testclient import TestClient
from renulus.server import create_app
from renulus.storage import utc_now
app=create_app(Path(sys.argv[2]))
s=app.state.services
client=TestClient(app)
calls=[]
def call(method,path,body=None):
    response=client.request(method,'/api/v1'+path,**({'json':body} if body is not None else {}))
    assert response.status_code==200,(path,response.status_code,response.text)
    value=response.json()
    calls.append({'method':method,'path':path,'body':body,'value':value})
    return value
topic=s.registry['content'].list_topics()[0]['id']
call('PUT','/study/goals',{'hours_per_week':4,'exam_date':None,'topic_ids':[topic],'track':'general'})
plan=call('POST','/study/plan/propose')
assert plan['activities']
call('PATCH','/study/plan/'+plan['activities'][0]['id'],{'due_date':(date.today()+timedelta(days=3)).isoformat(),'state':'completed'})
now=utc_now()
pdf='https://kdigo.org/wp-content/uploads/synthetic-shape-parity.pdf'
s.db.execute("UPDATE update_source_checks SET links_json=?,state='failed',error_code='synthetic_failure',last_checked_at=?,last_success_at=? WHERE source_id='K01'",(json.dumps([{'url':pdf,'label':'SYNTHETIC parity PDF'}]),now,(datetime.now(timezone.utc)-timedelta(days=8)).isoformat()))
s.db.execute("INSERT INTO update_entries(id,source_id,external_id,title,url,kind,discovered_at,review_state,summary,source_metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?)",('synthetic_parity','K01','synthetic:shape-parity','SYNTHETIC publication correction',pdf,'publication-change',now,'pending','SYNTHETIC inspect evidence',json.dumps({'canonical_url':pdf})))
review=client.post('/api/v1/updates/entries/synthetic_parity/review',json={'summary':'SYNTHETIC reviewed correction','state':'reviewed','target':{'register_id':'K01','canonical_url':pdf},'changes':{'correction':'SYNTHETIC corrigendum'},'evidence':[{'url':pdf,'locator':'SYNTHETIC page 1','finding':'SYNTHETIC correction','checked_on':date.today().isoformat(),'inspected':True}]} )
assert review.status_code==200,review.text
publication=client.post('/api/v1/updates/publications',json={'source_id':'K01','url':pdf,'permission_reference':'SYNTHETIC public permission'})
assert publication.status_code==200,publication.text
selection=[{'kind':'source','id':'K01'},{'kind':'publication','id':publication.json()['id']},{'kind':'literature','id':topic}]
configured=client.put('/api/v1/updates/schedule',json={'enabled':False,'cadence_hours':48,'selection':selection})
assert configured.status_code==200,configured.text
s.db.execute("INSERT INTO update_affected_versions(entry_id,kind,entity_id,version,pinned_source_id,register_id,locators_json,topic_id,objective_ids_json,detected_at,basis) VALUES(?,?,?,?,?,?,?,?,?,?,?)",('synthetic_parity','question','synthetic_question',1,'synthetic_source','K01','[\"page 1\"]',topic,'[]',now,'SYNTHETIC reviewed correction'))
for path in ['/study/goals','/study/plan','/study/progress','/study/home','/home','/nightly','/updates/entries','/updates/entries/synthetic_parity','/updates/sources','/updates/schedule','/updates/publications','/updates/sources/K01/status','/updates/entries/synthetic_parity/affected','/updates/affected/question/synthetic_question/versions/1']:
    call('GET',path)
client.close()
print(json.dumps({'database':str(s.paths.database),'calls':calls}))
`;
    const env = Object.fromEntries(['SystemRoot', 'WINDIR', 'TEMP', 'TMP'].filter(key => process.env[key]).map(key => [key, process.env[key]]));
    env.PATH = dirname(python);
    const prepared = spawnSync(python, ['-I', '-X', 'utf8', '-c', script, repository, root], { encoding: 'utf8', env, timeout: 60_000, maxBuffer: 8 * 1024 * 1024 });
    assert.equal(prepared.status, 0, prepared.stderr || prepared.error?.message);
    const reference = JSON.parse(prepared.stdout), migrations = loadMigrationInventory(repository), db = new DatabaseSync(reference.database);
    const expectedSchemaHash = inventory(db, migrations).schemaHash; db.close();
    const selection = { contract: 'renulus-storage-selector/1', isolation: 'synthetic', profileId: 'synthetic-shape-parity', generation: 1,
      authorityEpoch: 1, writer: 'ts', state: 'active', ownerId: 'synthetic-shape-owner', database: 'state/renulus.sqlite3' };
    writeFileSync(join(root, MARKER), JSON.stringify({ contract: 'renulus-synthetic-storage/1', profileId: selection.profileId }));
    writeFileSync(join(root, SELECTOR), JSON.stringify(selection));
    storage = await openIsolatedStorage({ profileRoot: root, selection, migrations, expectedSchemaHash });
    const unused = async () => { throw Error('Shape parity must not invoke inference or retrieval'); };
    study = createStudyCoordinator({ storage, native: { suggestions: unused }, assessment: { generate: unused, cancel: unused } });
    updates = createUpdatesCoordinator({ storage, native: { check: unused, digest: unused } });
    facade = await openTargetFacade({ port: 0, token: 'synthetic-shape-token', storage, study, updates });
    const mismatches = [];
    for (const call of reference.calls) {
      const response = await fetch('http://127.0.0.1:' + facade.port + '/api/v1' + call.path, { method: call.method,
        headers: { 'x-renulus-token': 'synthetic-shape-token', 'content-type': 'application/json' },
        ...(call.body === null ? {} : { body: JSON.stringify(call.body) }) });
      const value = await response.json();
      assert.equal(response.status, 200, call.method + ' ' + call.path + ': ' + JSON.stringify(value));
      compareKeys(call.value, value, call.method + ' ' + call.path, mismatches);
    }
    assert.deepEqual(mismatches, [], mismatches.join('\n'));
  } finally {
    await study?.close(); await updates?.close();
    if (facade) await facade.close(); else await storage?.close();
    assert.ok(resolve(root).toLowerCase().startsWith('c:\\renulus\\scratch\\shape-parity-bf06-'));
    rmSync(root, { recursive: true, force: true });
  }
});
