// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { spawnSync } from 'node:child_process';
import { DatabaseSync } from 'node:sqlite';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { openIsolatedStorage } from '../src/storage/index.ts';
import { MARKER, SELECTOR } from '../src/storage/ownership.ts';
import { inventory, loadMigrationInventory } from '../src/storage/schema.ts';
import { createStudyCoordinator } from '../src/domain/study/coordinator.ts';
import { createUpdatesCoordinator } from '../src/domain/updates/coordinator.ts';
import { createAssessmentGeneration } from '../src/domain/assessment/generation.ts';
const repository = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
async function fixture(seed = () => {}) {
  const root = mkdtempSync('C:/Renulus/scratch/study-updates-bf06-');
  const python = 'C:/Renulus/dev/python/Scripts/python.exe';
  const script = `import sys\nfrom pathlib import Path\nsys.path.insert(0,str(Path(sys.argv[1])/'runtime'))\nfrom renulus.server import create_app\ns=create_app(Path(sys.argv[2])).state.services\nprint(s.paths.database)`;
  const env = Object.fromEntries(['SystemRoot','WINDIR','TEMP','TMP'].filter(k => process.env[k]).map(k => [k,process.env[k]])); env.PATH = dirname(python);
  const prepared = spawnSync(python, ['-I','-X','utf8','-c',script,repository,root], { encoding:'utf8',env,timeout:60_000 });
  assert.equal(prepared.status,0,prepared.stderr);
  const database = prepared.stdout.trim(), migrations = loadMigrationInventory(repository), db = new DatabaseSync(database); seed(db);
  const expectedSchemaHash = inventory(db,migrations).schemaHash; db.close();
  const selection = { contract:'renulus-storage-selector/1',isolation:'synthetic',profileId:'bf06-synthetic',generation:1,authorityEpoch:1,writer:'ts',state:'active',ownerId:'bf06-synthetic-owner',database:'state/renulus.sqlite3' };
  writeFileSync(join(root,MARKER),JSON.stringify({contract:'renulus-synthetic-storage/1',profileId:selection.profileId})); writeFileSync(join(root,SELECTOR),JSON.stringify(selection));
  let storage = await openIsolatedStorage({profileRoot:root,selection,migrations,expectedSchemaHash});
  const command=c=>storage.command(c).catch(error=>{error.message=c.type+': '+error.code;throw error;});
  return { storage:{command}, command, async reopen(){await storage.close();storage=await openIsolatedStorage({profileRoot:root,selection,migrations,expectedSchemaHash});}, async inspect(fn){await storage.close();const db=new DatabaseSync(database);try{return fn(db);}finally{db.close();storage=await openIsolatedStorage({profileRoot:root,selection,migrations,expectedSchemaHash});}}, async close(){await storage.close();assert.ok(resolve(root).toLowerCase().startsWith('c:\\renulus\\scratch\\study-updates-bf06-'));rmSync(root,{recursive:true,force:true});} };
}
const fail = code => e => e.code === code;
const bundle = { explain: Array.from({length:5},(_,i)=>'SYNTHETIC explain topic '+i), case: Array.from({length:5},(_,i)=>'SYNTHETIC fictional case '+i), practice: Array.from({length:5},(_,i)=>'SYNTHETIC practice topic '+i) };
const batch = {items:Array.from({length:5},(_,i)=>({stem:'SYNTHETIC renal question '+i,options:[{id:'a',text:'Choice A'},{id:'b',text:'Choice B'},{id:'c',text:'Choice C'},{id:'d',text:'Choice D'}],correct_option_id:'a',explanation:'SYNTHETIC educational explanation.'}))};
test('Home native bundle, manual plan override and context/Stop publication fences use actual canonical worker',async()=>{
  const f=await fixture();let clock={now:'2026-10-27T18:00:00Z',timezone:'Europe/Warsaw'},calls=0;
  const study=createStudyCoordinator({storage:f.storage,clock:()=>clock,native:{async suggestions(context){calls++;assert.ok(!JSON.stringify(context.material).includes('correct_option_ids'));return bundle;}},assessment:{generate:async()=>{throw Error('unused');},cancel:async()=>{}}});
  try{
    assert.equal((await f.command({type:'study.nightly.read'})).preferences.enabled,false);
    const job=await study.refresh();const home=await study.settled(job.id);assert.deepEqual(home.suggestions,bundle);assert.equal(home.suggestions_date,'2026-10-27');await study.refresh();assert.equal(calls,1);
    const proposed=await f.command({type:'study.plan.read',clock});const accepted=await f.command({type:'study.plan.accept',clock,stamp:proposed.stamp,idempotencyKey:'bf06-plan-accept'});assert.ok(accepted.activities.length);
    const first=accepted.activities[0];const changed=await f.command({type:'study.activity.change',id:first.id,expectedRevision:first.revision,dueDate:'2026-11-01',state:null,idempotencyKey:'bf06-plan-manual'});assert.equal(changed.manual_override,true);
    const newer=await f.command({type:'study.plan.read',clock});await f.command({type:'study.plan.accept',clock,stamp:newer.stamp,idempotencyKey:'bf06-plan-reaccept'});assert.equal((await f.command({type:'study.plan.read',clock})).activities.find(a=>a.id===first.id).due_date,'2026-11-01');
    assert.equal((await f.command({type:'study.home.read',clock})).suggestions,null);
    const late=await f.command({type:'study.home.begin',clock});await f.command({type:'study.job.stop',jobId:late.job_id,state:'cancelled',errorCode:'cancelled'});await assert.rejects(f.command({type:'study.home.publish',jobId:late.job_id,bundle,clock}),fail('cancelled'));
  }finally{await study.close();await f.close();}
});
test('nightly claims once, publishes through assessment Ready, catches up once and rejects Off/restart late publication',async()=>{
  const f=await fixture();let clock={now:'2026-10-27T18:00:00Z',timezone:'Europe/Warsaw'};
  const generation=createAssessmentGeneration(f.storage,{generate:async()=>batch});
  const study=createStudyCoordinator({storage:f.storage,clock:()=>clock,native:{suggestions:async()=>bundle},assessment:{generate:async r=>generation.create({title:r.title,count:r.count,topic_id:null,inputs:r.inputs,source_refs:[],idempotencyKey:r.idempotency_key,origin:'nightly',schedule:r.nightly}),cancel:id=>generation.cancel(id)}});
  try{
    await study.start();await study.updateNightly({type:'study.nightly.preferences',clock,expectedRevision:1,enabled:true,localTime:'22:00',count:5,idempotencyKey:'bf06-nightly-on'});
    assert.equal((await f.command({type:'study.nightly.claim',clock})).request,null);clock={...clock,now:'2026-10-27T21:01:00Z'};
    const status=await study.tick();const id=status.last_job.id;await generation.settled(id);const job=await generation.read(id);assert.equal(job.state,'published');assert.equal(job.accepted_count,5);assert.equal((await f.command({type:'study.nightly.claim',clock})).request,null);
    const test=await f.command({type:'assessment.tests.setup',versionId:job.published_version_id});assert.equal(test.version.origin,'nightly');
    clock={...clock,now:'2026-11-01T08:00:00Z'};const catchup=await f.command({type:'study.nightly.claim',clock});assert.equal(catchup.request.nightly.day,'2026-10-31');assert.equal((await f.command({type:'study.nightly.claim',clock})).request,null);
    await f.command({type:'study.nightly.guard',schedule:catchup.request.nightly});await study.updateNightly({type:'study.nightly.preferences',clock,expectedRevision:2,enabled:false,localTime:'22:00',count:5,idempotencyKey:'bf06-nightly-off'});await assert.rejects(f.command({type:'study.nightly.guard',schedule:catchup.request.nightly}),fail('nightly_invalidated'));
    await f.command({type:'study.nightly.recover',clock});assert.equal((await f.command({type:'study.nightly.claim',clock})).request,null);
  }finally{await study.close();await generation.close();await f.close();}
});
test('Updates keeps failed-check success date and correction/outbox/source links; digest cannot review',async()=>{
  const f=await fixture(db=>{const at=new Date().toISOString();db.prepare('INSERT OR IGNORE INTO update_source_checks(source_id,title,url,snapshot_status) VALUES(?,?,?,?)').run('S99','SYNTHETIC official source','https://synthetic.invalid/source','Synthetic');db.prepare('INSERT INTO update_entries VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)').run('synthetic_update','S99','synthetic:entry','SYNTHETIC correction','https://synthetic.invalid/article','publication-change',null,at,null,null,'pending','Inspect','[]',JSON.stringify({canonical_url:'https://synthetic.invalid/article'}),null);});
  await f.inspect(db=>{const at=new Date().toISOString();for(const [id,url] of [['matched','https://synthetic.invalid/article'],['other','https://synthetic.invalid/other']]){db.prepare('INSERT INTO knowledge_documents(id,title,source_id,scope_kind,active_revision,latest_revision,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)').run('doc_'+id,'SYNTHETIC '+id,'S99','personal-library','rev_'+id,'rev_'+id,at,at);db.prepare('INSERT INTO knowledge_revisions(id,document_id,ordinal,status,sha256,media_type,bytes,metadata_json,rights_json,created_at) VALUES(?,?,1,?,?,?,?,?,?,?)').run('rev_'+id,'doc_'+id,'ready','b'.repeat(64),'text/plain',10,JSON.stringify({source_id:'S99',canonical_url:url,publication_status:'final',content_reviewed:true,latest_final_verified:true}),JSON.stringify({display:true,model_input:true,derivation:true}),at);}});
  let failed=false;const updates=createUpdatesCoordinator({storage:f.storage,native:{async check(){if(failed)throw Object.assign(Error('synthetic failure'),{code:'source_fetch_failed'});return {digest:'a'.repeat(64),links:[],entries:[],metadata:{}};},async digest(input){return 'SYNTHETIC digest of '+input.entries[0].url;}}});
  try{
    await updates.check({kind:'source',id:'S99'},true);const before=(await f.command({type:'updates.sources'})).sources.find(s=>s.source_id==='S99');failed=true;const check=await updates.check({kind:'source',id:'S99'},true);assert.equal(check.state,'failed');const after=(await f.command({type:'updates.sources'})).sources.find(s=>s.source_id==='S99');assert.equal(after.last_success_at,before.last_success_at);assert.equal(after.error_code,'source_fetch_failed');
    const entry=await f.command({type:'updates.entry',id:'synthetic_update'});const review={summary:'SYNTHETIC correction needs re-review',topic_ids:[],reviewer:'learner',state:'reviewed',evidence:[{url:entry.url,locator:'Correction notice',finding:'SYNTHETIC educational change',checked_on:'2026-10-27',inspected:true}],target:{register_id:'S99',canonical_url:entry.url},changes:{publication_status:'final',correction:'SYNTHETIC corrigendum',latest_final_verified:true,content_reviewed:true}};
    const command={type:'updates.review',id:entry.id,review,expectedRevision:entry.revision,idempotencyKey:'bf06-source-correction'};const reviewed=await f.command(command);assert.equal(reviewed.review.changes.latest_final_verified,false);assert.equal(reviewed.review.changes.content_reviewed,false);assert.equal((await f.command(command)).revision,reviewed.revision);
    const digest=await updates.digest();assert.ok(digest.text.includes(entry.url));assert.equal((await f.command({type:'updates.entry',id:entry.id})).revision,reviewed.revision);
    await f.inspect(db=>{assert.equal(db.prepare('SELECT COUNT(*) AS n FROM knowledge_source_status_events').get().n,2);assert.equal(db.prepare("SELECT COUNT(*) AS n FROM update_library_changes WHERE state NOT IN ('applied','no-match')").get().n,0);const matched=JSON.parse(db.prepare('SELECT metadata_json FROM knowledge_revisions WHERE id=?').get('rev_matched').metadata_json),other=JSON.parse(db.prepare('SELECT metadata_json FROM knowledge_revisions WHERE id=?').get('rev_other').metadata_json);assert.equal(matched.content_reviewed,false);assert.equal(matched.latest_final_verified,false);assert.equal(matched.correction,'SYNTHETIC corrigendum');assert.equal(other.content_reviewed,true);assert.equal(other.correction,undefined);});
  }finally{await updates.close();await f.close();}
});
