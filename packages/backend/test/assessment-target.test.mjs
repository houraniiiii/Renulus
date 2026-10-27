// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { spawnSync } from 'node:child_process';
import { DatabaseSync } from 'node:sqlite';
import { mkdtempSync,writeFileSync,rmSync } from 'node:fs';
import { dirname,join,resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { openIsolatedStorage } from '../src/storage/index.ts';
import { MARKER,SELECTOR } from '../src/storage/ownership.ts';
import { inventory,loadMigrationInventory,canonical,digest } from '../src/storage/schema.ts';
import { createAssessmentGeneration } from '../src/domain/assessment/generation.ts';
import { assessmentCommand } from '../src/http/assessment-commands.ts';
const repository=resolve(dirname(fileURLToPath(import.meta.url)),'../../..');
const python='C:/Renulus/dev/python/Scripts/python.exe';
async function fixture() {
  const root=mkdtempSync('C:/Renulus/scratch/assessment-bf05-');
  const script=`
import sys
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'runtime'))
from renulus.server import create_app
s=create_app(Path(sys.argv[2])).state.services
print(s.paths.database)
`;
  const env=Object.fromEntries(['SystemRoot','WINDIR','TEMP','TMP'].filter(k=>process.env[k]).map(k=>[k,process.env[k]]));env.PATH=dirname(python);
  const prepared=spawnSync(python,['-I','-X','utf8','-c',script,repository,root],{encoding:'utf8',env,timeout:60000});
  assert.equal(prepared.status,0,prepared.stderr);const database=prepared.stdout.trim();
  const migrations=loadMigrationInventory(repository),db=new DatabaseSync(database);const expectedSchemaHash=inventory(db,migrations).schemaHash;db.close();
  const selection={contract:'renulus-storage-selector/1',isolation:'synthetic',profileId:'bf05-synthetic',generation:1,authorityEpoch:1,writer:'ts',state:'active',ownerId:'bf05-synthetic-owner',database:'state/renulus.sqlite3'};
  writeFileSync(join(root,MARKER),JSON.stringify({contract:'renulus-synthetic-storage/1',profileId:selection.profileId}));writeFileSync(join(root,SELECTOR),JSON.stringify(selection));
  const options={profileRoot:root,selection,migrations,expectedSchemaHash};let storage=await openIsolatedStorage(options);
  return {get storage(){return storage;},command:c=>storage.command(c).catch(e=>{e.message=c.type+': '+e.code;throw e;}),database,
    async reopen(mutate){await storage.close();if(mutate){const db=new DatabaseSync(database);try{mutate(db);}finally{db.close();}}storage=await openIsolatedStorage(options);},
    async close(){await storage.close();assert.ok(resolve(root).toLowerCase().startsWith('c:\\renulus\\scratch\\assessment-bf05-'));rmSync(root,{recursive:true,force:true});}};
}
const fail=code=>e=>e.code===code;
const batch=(index=0)=>({items:Array.from({length:5},(_,i)=>({stem:`SYNTHETIC ${['AKI','CKD','glomerular disease','dialysis','transplant'][i]} question ${index}-${i}`,options:[{id:'a',text:'Synthetic option A'},{id:'b',text:'Synthetic option B'}],correct_option_id:'a',explanation:'Synthetic teaching rationale.',hint:null,source_indices:[]}))});
const unavailable=async()=>{throw Object.assign(new Error('fixture unavailable'),{code:'synthetic_unavailable'});};
const native=overrides=>({generate:unavailable,normalize:unavailable,fictionalTransform:unavailable,privacyReview:unavailable,narrative:unavailable,...overrides});
test('immutable reviewed version → whole Study/help, lost ACK → atomic Test, expiry after closed-app rollback excludes withdrawn key',async()=>{
  const f=await fixture();try{
    const saved=await f.command({type:'assessment.tests.reviewed',title:'SYNTHETIC broad nephrology',count:5,topicIds:[],idempotencyKey:'bf05-reviewed-create'});
    const start={type:'assessment.attempts.start',versionId:saved.version_id,mode:'study',timing:{kind:'untimed',duration_seconds:null},idempotencyKey:'bf05-study-start'};
    let study=await f.command(start);assert.equal(study.item_count,5);assert.ok(!JSON.stringify(study).includes('correct_option_ids'));assert.ok(!JSON.stringify(study).includes('explanation'));
    assert.equal((await f.command(start)).id,study.id);
    const help=await f.command({type:'assessment.attempts.help',attemptId:study.id,expectedRevision:0,expectedPolicyRevision:study.policy.revision,itemId:study.current_item.item_id,kind:'sources',idempotencyKey:'bf05-study-help'});
    const answered=await f.command({type:'assessment.attempts.answer',attemptId:study.id,expectedRevision:0,itemId:study.current_item.item_id,optionIds:[study.current_item.options[0].id],idempotencyKey:'bf05-study-answer'});assert.equal(answered.committed[0].assisted,true);
    await assert.rejects(f.command({type:'assessment.help.current',context:help.context}),fail('revision_conflict'));
    await assert.rejects(f.command({type:'assessment.attempts.help',attemptId:study.id,expectedRevision:0,expectedPolicyRevision:study.policy.revision,itemId:study.current_item.item_id,kind:'sources',idempotencyKey:'bf05-study-help'}),fail('revision_conflict'));
    const test=await f.command({...start,mode:'test',idempotencyKey:'bf05-test-start'});
    await assert.rejects(f.command({type:'assessment.help.current',context:help.context}),fail('assistance_restricted'));
    await assert.rejects(f.command({type:'assessment.tests.preview',versionId:saved.version_id}),fail('assistance_restricted'));
    await assert.rejects(f.command({type:'assessment.attempts.transition',attemptId:test.id,expectedRevision:0,action:'pause',idempotencyKey:'bf05-test-pause'}),fail('attempt_restricted'));
    const latest={position:4,answers:test.answers.map(a=>({...a,option_ids:[]}))};
    const submit={type:'assessment.attempts.submit',attemptId:test.id,expectedRevision:0,latestDraft:latest,idempotencyKey:'bf05-submit-lostack'};
    const committed=await f.command(submit);assert.equal(committed.result.denominator,5);assert.equal(committed.result.unanswered,5);assert.equal(committed.draft_revision,1);
    assert.deepEqual((await f.command(submit)).result,committed.result);
    await f.reopen();assert.deepEqual((await f.command({type:'assessment.attempts.get',attemptId:test.id})).result,committed.result);
    const timed=await f.command({...start,mode:'test',timing:{kind:'timed',duration_seconds:60},idempotencyKey:'bf05-deadline-start'});
    const pinnedQuestion=timed.current_item;
    await f.reopen(db=>{
      db.prepare('INSERT INTO content_question_withdrawals VALUES(?,?,?,?,NULL)').run(pinnedQuestion.question_id,Number(pinnedQuestion.question_version),'SYNTHETIC withdrawn key',new Date().toISOString());
      db.prepare('UPDATE assessment_test_attempts SET clock_high_water_at=?,deadline_at=? WHERE id=?').run('2099-01-01T00:00:00Z','2099-01-01T00:01:00Z',timed.id);
    });
    // Reconciliation commits before the ordinary command, even if that command is rejected.
    await assert.rejects(f.command({type:'learning.rename',threadId:'synthetic_missing',expectedRevision:1,title:'SYNTHETIC',idempotencyKey:'bf05-invalid-after-expiry'}));
    const expired=await f.command({type:'assessment.attempts.get',attemptId:timed.id});assert.equal(expired.status,'submitted');assert.equal(expired.result.reason,'deadline');assert.equal(expired.result.excluded,1);assert.equal(expired.result.denominator,4);
    assert.equal(expired.result.items[0].feedback.correct_option_ids.length,0);assert.deepEqual((await f.command({type:'assessment.attempts.get',attemptId:test.id})).result,committed.result);
  }finally{await f.close();}
});
test('5/10/20 batch checkpoints survive cancellation, lost ACK, reopen and explicit shorter acceptance without providers',async()=>{
  const f=await fixture();try{
    const producer=createAssessmentGeneration(f.storage,native({generate:async ({batchIndex})=>batch(batchIndex)}));
    let checkpointItems;
    for(const count of [5,10]){const input={title:'SYNTHETIC saved practice',count,topic_id:null,inputs:[],source_refs:[],idempotencyKey:'bf05-generated-'+count};const job=await producer.create(input);await producer.settled(job.id);const published=await producer.read(job.id);assert.equal(published.state,'published');assert.equal(published.accepted_count,count);assert.equal((await producer.create(input)).id,job.id);checkpointItems=published.checkpoint.batches[0];
      const response=await assessmentCommand({method:'GET',headers:{}},new URL('http://127.0.0.1/api/v1/assessment/generation/jobs/'+job.id),f.storage,producer);
      assert.ok(!JSON.stringify(response.value).includes('correct_option_ids'));assert.ok(!('checkpoint'in response.value));
    }
    const interrupted=await f.command({type:'assessment.generation.create',input:{title:'SYNTHETIC interrupted-native',count:10,topic_id:null,inputs:[],source_refs:[],idempotencyKey:'bf05-native-interrupted'}});
    await f.command({type:'assessment.generation.claim',jobId:interrupted.id,execution:'native_old_execution',stamp:{policy_revision:interrupted.policy_revision,context_epoch:interrupted.context_epoch}});
    const checkpoint={type:'assessment.generation.checkpoint',jobId:interrupted.id,execution:'native_old_execution',batchIndex:0,items:checkpointItems};
    await f.command(checkpoint);assert.equal((await f.command(checkpoint)).validated_count,5);
    await assert.rejects(producer.resume(interrupted.id),fail('generation_settlement_required'));
    const recovered=createAssessmentGeneration(f.storage,native({settleInterrupted:async job=>{assert.equal(job.checkpoint.execution,'native_old_execution');return 'settled';},generate:async ({batchIndex})=>batch(batchIndex)}));
    await recovered.resume(interrupted.id);assert.equal((await recovered.settled(interrupted.id)).accepted_count,10);await recovered.close();
    let release;const waiting=new Promise(resolve=>release=resolve);let secondStarted;const second=new Promise(resolve=>secondStarted=resolve);
    const cancellable=createAssessmentGeneration(f.storage,native({generate:async ({batchIndex})=>{if(batchIndex===1){secondStarted();await waiting;}return batch(batchIndex);}}));
    const input={title:'SYNTHETIC twenty interrupted',count:20,topic_id:null,inputs:[],source_refs:[],idempotencyKey:'bf05-generated-20'};
    const job=await cancellable.create(input);await second;await cancellable.cancel(job.id);release();await cancellable.settled(job.id);
    assert.equal((await cancellable.read(job.id)).validated_count,5);assert.equal((await cancellable.read(job.id)).state,'cancelled');
    await producer.close();await cancellable.close();await f.reopen();
    const result=await f.command({type:'assessment.generation.publish',jobId:job.id,acceptedCount:5,idempotencyKey:'bf05-accept-five'});assert.equal(result.requested_count,20);assert.equal(result.accepted_count,5);
    const start=await f.command({type:'assessment.attempts.start',versionId:result.version_id,mode:'test',timing:{kind:'untimed',duration_seconds:null},idempotencyKey:'bf05-personal-test'});
    const scored=await f.command({type:'assessment.attempts.submit',attemptId:start.id,expectedRevision:0,latestDraft:null,idempotencyKey:'bf05-personal-submit'});assert.equal(scored.result.cohorts.personal.denominator,5);assert.equal(scored.result.cohorts.fresh.denominator,0);
  }finally{await f.close();}
});
test('ambiguous imported key requires explicit resolution; private fiction reviews exact artifact and retains no original',async()=>{
  const f=await fixture();try{
    const imported=await f.command({type:'assessment.import.create',title:'SYNTHETIC imported',original:{kind:'paste',text:'1. SYNTHETIC electrolyte question\na. Option A\nb. Option B\nAnswer: a\nKey: b',terms:'SYNTHETIC owner permission',permission_confirmed:true},idempotencyKey:'bf05-import-original'});
    assert.equal(imported.candidates[0].key_status,'ambiguous');
    await assert.rejects(f.command({type:'assessment.import.publish',importId:imported.id,expectedRevision:1,idempotencyKey:'bf05-unresolved-publish'}),fail('import_keys_unresolved'));
    const resolved=await f.command({type:'assessment.import.resolve',importId:imported.id,expectedRevision:1,candidateId:imported.candidates[0].id,optionIds:['a'],reviewConfirmed:true,idempotencyKey:'bf05-resolve-import'});
    const published=await f.command({type:'assessment.import.publish',importId:imported.id,expectedRevision:resolved.revision,idempotencyKey:'bf05-import-publish'});assert.equal(published.result.status,'ready');
    const bounded=await f.command({type:'assessment.import.create',title:'SYNTHETIC bounded normalization',original:{kind:'paste',text:'SYNTHETIC unfamiliar imported layout',terms:'SYNTHETIC owner permission',permission_confirmed:true},idempotencyKey:'bf05-normalize-original'});
    const normalizer=createAssessmentGeneration(f.storage,native({normalize:unavailable}));
    for(let i=0;i<3;i++){const current=await f.command({type:'assessment.import.get',importId:bounded.id,original:false});await assert.rejects(normalizer.normalize(bounded.id,current.revision,new AbortController().signal),fail('synthetic_unavailable'));}
    const exhausted=await f.command({type:'assessment.import.get',importId:bounded.id,original:false});assert.equal(exhausted.call_count,3);
    await assert.rejects(normalizer.normalize(bounded.id,exhausted.revision,new AbortController().signal),fail('import_call_limit'));await normalizer.close();
    const sentinel='SYNTHETIC_PATIENT_SECRET_00042';let reviewCalls=0;
    const producer=createAssessmentGeneration(f.storage,native({fictionalTransform:async()=>batch(),privacyReview:async ({artifactSha256,questions})=>{reviewCalls++;assert.equal(artifactSha256,digest(canonical(questions)));return {schema:'fictional-test-review/1',artifact_sha256:artifactSha256,source_identity_removed:true,clinical_details_generalised:true,no_source_links:true,issues:[]};}}));
    const fiction=await producer.fictionalise({title:'SYNTHETIC fictional learning',sourceText:sentinel,instruction:'General fictional nephrology practice',count:5,idempotencyKey:'bf05-fictional-create'},new AbortController().signal);assert.equal(fiction.status,'ready');assert.equal(reviewCalls,1);
    const exported=await f.command({type:'records.export'});assert.ok(!JSON.stringify(exported).includes(sentinel));assert.ok(!JSON.stringify(exported).includes(digest(sentinel)));
    const refused=createAssessmentGeneration(f.storage,native({fictionalTransform:async()=>batch(),privacyReview:async()=>({schema:'fictional-test-review/1',artifact_sha256:'0'.repeat(64),source_identity_removed:true,clinical_details_generalised:true,no_source_links:true,issues:[]})}));
    await assert.rejects(refused.fictionalise({title:'SYNTHETIC refused',sourceText:sentinel,instruction:'Fictional nephrology',count:5,idempotencyKey:'bf05-fictional-refused'},new AbortController().signal),fail('fictionalisation_privacy_refused'));
    await producer.close();await refused.close();
  }finally{await f.close();}
});
