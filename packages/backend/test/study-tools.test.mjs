// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { spawnSync } from 'node:child_process';
import { DatabaseSync } from 'node:sqlite';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Effect } from 'effect';
import { openIsolatedStorage } from '../src/storage/index.ts';
import { MARKER, SELECTOR } from '../src/storage/ownership.ts';
import { inventory, loadMigrationInventory } from '../src/storage/schema.ts';
import { createStudyTools, registerStudyTools } from '../src/domain/study/tools.ts';
import { createUpdatesTools, registerUpdatesTools } from '../src/domain/updates/tools.ts';
const repository = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
async function fixture() {
  const root = mkdtempSync('C:/Renulus/scratch/study-tools-bf06-'), python = 'C:/Renulus/dev/python/Scripts/python.exe';
  const script = `import sys\nfrom pathlib import Path\nsys.path.insert(0,str(Path(sys.argv[1])/'runtime'))\nfrom renulus.server import create_app\ns=create_app(Path(sys.argv[2])).state.services\nprint(s.paths.database)`;
  const env = Object.fromEntries(['SystemRoot','WINDIR','TEMP','TMP'].filter(k => process.env[k]).map(k => [k,process.env[k]])); env.PATH = dirname(python);
  const prepared = spawnSync(python, ['-I','-X','utf8','-c',script,repository,root], { encoding:'utf8',env,timeout:60_000 });
  assert.equal(prepared.status,0,prepared.stderr);
  const database = prepared.stdout.trim(), migrations = loadMigrationInventory(repository), db = new DatabaseSync(database);
  db.prepare('INSERT INTO update_entries VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)').run('synthetic_tools_update','S99','synthetic:tools','SYNTHETIC update','https://synthetic.invalid/update','publication-change',null,new Date().toISOString(),null,null,'pending','SYNTHETIC summary','[]',JSON.stringify({secret_evidence_blob:'not-for-model'}),null);
  const expectedSchemaHash = inventory(db,migrations).schemaHash; db.close();
  const selection = { contract:'renulus-storage-selector/1',isolation:'synthetic',profileId:'bf06-tools',generation:1,authorityEpoch:1,writer:'ts',state:'active',ownerId:'bf06-tools-owner',database:'state/renulus.sqlite3' };
  writeFileSync(join(root,MARKER),JSON.stringify({contract:'renulus-synthetic-storage/1',profileId:selection.profileId})); writeFileSync(join(root,SELECTOR),JSON.stringify(selection));
  const storage = await openIsolatedStorage({profileRoot:root,selection,migrations,expectedSchemaHash});
  return { storage, async close(){await storage.close();rmSync(root,{recursive:true,force:true});} };
}
test('native plan and update tools require grants, preview without saving, project safe fields and deny active Test assistance', async () => {
  const f = await fixture();
  try {
    let grants = ['renulus.plan.propose', 'renulus.updates.read'], checks = 0;
    const authority = { storage:f.storage, resolve:async context=>({operationId:'synthetic-op',attemptId:'1',sessionId:context.sessionID,studyAttemptId:null,grants}), check:async()=>{checks++;} };
    const study = createStudyTools(authority), updates = createUpdatesTools(authority), context = { sessionID:'synthetic-session',id:'synthetic-call' }, signal = () => new AbortController().signal;
    const before = await f.storage.command({type:'study.plan.read'});
    const proposal = await study.execute('renulus_plan_propose',{},context,signal());
    assert.equal(proposal.requires_explicit_save,true);assert.ok(proposal.activities.length);
    assert.deepEqual(await f.storage.command({type:'study.plan.read'}),before);
    const entries = await updates.execute('renulus_updates_read',{},context,signal());
    assert.equal(entries.entries[0].id,'synthetic_tools_update');
    assert.deepEqual(Object.keys(entries.entries[0]).sort(),['id','title','url','review_state','summary','reviewed_at','source_id'].sort());
    assert.ok(!JSON.stringify(entries).includes('secret_evidence_blob'));assert.equal(checks,4);
    const registered = [], registry = {tool:{transform:fn=>{fn({add:t=>registered.push(t)});return Effect.void;}}};
    await Effect.runPromise(registerStudyTools(registry,study));await Effect.runPromise(registerUpdatesTools(registry,updates));
    assert.deepEqual(registered.map(t=>[t.name,t.options.permission]),[['renulus_plan_propose','renulus.plan.propose'],['renulus_updates_read','renulus.updates.read']]);
    assert.equal(JSON.parse((await Effect.runPromise(registered[0].execute({},context))).content).requires_explicit_save,true);
    grants = [];
    await assert.rejects(study.execute('renulus_plan_propose',{},context,signal()),e=>e.code==='study_tool_grant_denied');
    await assert.rejects(updates.execute('renulus_updates_read',{},context,signal()),e=>e.code==='updates_tool_grant_denied');
    grants = ['renulus.plan.propose','renulus.updates.read'];
    const saved = await f.storage.command({type:'assessment.tests.reviewed',title:'SYNTHETIC active Test',count:5,topicIds:[],idempotencyKey:'bf06-tools-reviewed'});
    await f.storage.command({type:'assessment.attempts.start',versionId:saved.version_id,mode:'test',timing:{kind:'untimed',duration_seconds:null},idempotencyKey:'bf06-tools-test'});
    await assert.rejects(study.execute('renulus_plan_propose',{},context,signal()),e=>e.code==='assistance_restricted');
    await assert.rejects(updates.execute('renulus_updates_read',{},context,signal()),e=>e.code==='assistance_restricted');
  } finally { await f.close(); }
});
