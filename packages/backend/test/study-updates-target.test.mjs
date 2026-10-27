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
import { createServer } from 'node:http';
import { openEngineWorker } from '../src/workers/process.ts';
import { createEvidenceDomain } from '../src/domain/evidence/index.ts';
import { createUpdatesRetrieval } from '../src/domain/updates/retrieval.ts';
import { studyCommand } from '../src/http/study-commands.ts';
import { contentCommand } from '../src/http/content-commands.ts';
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
  return { root, storage:{command}, command, async reopen(){await storage.close();storage=await openIsolatedStorage({profileRoot:root,selection,migrations,expectedSchemaHash});}, async inspect(fn){await storage.close();const db=new DatabaseSync(database);try{return fn(db);}finally{db.close();storage=await openIsolatedStorage({profileRoot:root,selection,migrations,expectedSchemaHash});}}, async close(){await storage.close();assert.ok(resolve(root).toLowerCase().startsWith('c:\\renulus\\scratch\\study-updates-bf06-'));rmSync(root,{recursive:true,force:true});} };
}
const fail = code => e => e.code === code;
const bundle = { explain: Array.from({length:5},(_,i)=>'SYNTHETIC explain topic '+i), case: Array.from({length:5},(_,i)=>'SYNTHETIC fictional case '+i), practice: Array.from({length:5},(_,i)=>'SYNTHETIC practice topic '+i) };
const batch = {items:Array.from({length:5},(_,i)=>({stem:'SYNTHETIC renal question '+i,options:[{id:'a',text:'Choice A'},{id:'b',text:'Choice B'},{id:'c',text:'Choice C'},{id:'d',text:'Choice D'}],correct_option_id:'a',explanation:'SYNTHETIC educational explanation.'}))};
test('Home native bundle, manual plan override and context/Stop publication fences use actual canonical worker',async()=>{
  const f=await fixture();let clock={now:'2026-10-27T18:00:00Z',timezone:'Europe/Warsaw'},calls=0;
  const study=createStudyCoordinator({storage:f.storage,clock:()=>clock,native:{async suggestions(context){calls++;assert.ok(!JSON.stringify(context.material).includes('correct_option_ids'));return bundle;}},assessment:{generate:async()=>{throw Error('unused');},cancel:async()=>{}}});
  try{
    assert.equal((await f.command({type:'study.nightly.read'})).preferences.enabled,false);
    const job=await study.refresh();const home=await study.settled(job.job_id);assert.deepEqual(home.suggestions,bundle);assert.equal(home.suggestions_date,'2026-10-27');await study.refresh();assert.equal(calls,1);
    const preview=await f.command({type:'study.plan.preview',clock});assert.ok(preview.activities.length);const accepted=await f.command({type:'study.plan.propose',clock});assert.ok(accepted.activities.length);assert.deepEqual(Object.keys(accepted).sort(),['activities','explanation','selection','status','tracks']);
    const first=accepted.activities[0];const changed=await f.command({type:'study.activity.change',id:first.id,expectedRevision:first.revision,dueDate:'2026-11-01',state:null,idempotencyKey:'bf06-plan-manual'});assert.equal(changed.manual_override,true);
    await f.command({type:'study.plan.propose',clock});assert.equal((await f.command({type:'study.plan.read'})).activities.find(a=>a.id===first.id).due_date,'2026-11-01');
    assert.equal((await f.command({type:'study.home.read',clock})).suggestions,null);
    const tracks=await contentCommand({method:'GET'},new URL('http://localhost/api/v1/content/tracks'),f.storage);assert.equal(tracks.status,200);assert.deepEqual(tracks.value,(await f.command({type:'study.plan.read'})).tracks);
    const late=await f.command({type:'study.home.begin',clock});
    const wrongStop=await studyCommand({method:'POST',headers:{'idempotency-key':'bf06-wrong-route'}},new URL('http://localhost/api/v1/nightly/jobs/'+late.job_id+'/cancel'),f.storage,study);assert.equal(wrongStop.status,404);
    await f.command({type:'study.home.publish',jobId:late.job_id,bundle,clock});
    clock={...clock,now:'2026-10-28T18:00:00Z'};const cancelled=await f.command({type:'study.home.begin',clock});
    const stopped=await studyCommand({method:'POST',headers:{'idempotency-key':'bf06-home-stop'}},new URL('http://localhost/api/v1/home/jobs/'+cancelled.job_id+'/cancel'),f.storage,study);assert.equal(stopped.status,200);
    await assert.rejects(f.command({type:'study.home.publish',jobId:cancelled.job_id,bundle,clock}),fail('cancelled'));
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
test('Updates source check uses the protected loopback evidence broker and retains discovery-only provenance', {skip:!process.env.RENULUS_BACKEND_TEST_PYTHON}, async()=>{
  let requests=0;
  const server=createServer((request,response)=>{requests++;assert.equal(new URL(request.url,'http://localhost').pathname,'/search');response.setHeader('content-type','application/json');response.end(JSON.stringify({resultList:{result:[{id:'12345678',source:'MED',title:'SYNTHETIC renal discovery',firstPublicationDate:'2026-10-27'}]}}));});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const f=await fixture(db=>db.prepare('INSERT OR IGNORE INTO update_source_checks(source_id,title,url,snapshot_status) VALUES(?,?,?,?)').run('S99','SYNTHETIC renal discovery','https://synthetic.invalid/source','Synthetic'));
  let worker,updates;
  try{
    const revisions={configuration:1,grant:1,context:1,deletion:1,cancellation:0};
    worker=await openEngineWorker({python:process.env.RENULUS_BACKEND_TEST_PYTHON,sourceRoot:repository,launchRoot:join(f.root,'launch'),retention:'saved',
      identity:{profile_id:'synthetic-bf06-evidence',domain_store_id:'synthetic-domain',runtime_store_id:'synthetic-native',authority_epoch:1,process_generation:'synthetic-evidence'},current:()=>revisions,
      broker:{profile_root:f.root,state_root:join(f.root,'state')}});
    const inputs=new Map();
    const evidence=createEvidenceDomain({storage:f.storage,worker:{channel:worker.channel,maxChunkBytes:worker.ready.capacity.max_chunk_bytes,retention:'saved'},
      check:async(id,signal)=>{signal.throwIfAborted();await f.command({type:'updates.check.current',input:inputs.get(id)});},
      endpoints:{'europe-pmc':{host:'127.0.0.1',port:server.address().port,private_network:true,base_url:'http://127.0.0.1:'+server.address().port}}});
    const retrieval=createUpdatesRetrieval(evidence);
    updates=createUpdatesCoordinator({storage:f.storage,native:{check:async(input,signal)=>{inputs.set(input.token,input);try{return await retrieval.check(input,signal);}finally{inputs.delete(input.token);}},digest:async()=>{throw Error('unused');}}});
    const checked=await updates.check({kind:'source',id:'S99'},true);
    const entries=(await f.command({type:'updates.entries',state:null,limit:20,offset:0})).entries;
    const entry=entries.find(e=>e.title==='SYNTHETIC renal discovery');
    assert.deepEqual({state:checked.state,requests,verification:entry?.source_metadata.verification,passage_evidence:entry?.source_metadata.passage_evidence,review_state:entry?.review_state},
      {state:'baseline',requests:1,verification:'discovery-only',passage_evidence:false,review_state:'pending'});
  }finally{await updates?.close();await worker?.close();await f.close();await new Promise(resolve=>server.close(resolve));}
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
