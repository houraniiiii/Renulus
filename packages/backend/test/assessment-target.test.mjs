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
import { createAssessmentTools,registerAssessmentTools } from '../src/domain/assessment/tools.ts';
import { Effect } from 'effect';
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

const signal=()=>new AbortController().signal;
const review=({artifactSha256})=>({schema:'fictional-test-review/1',artifact_sha256:artifactSha256,source_identity_removed:true,clinical_details_generalised:true,no_source_links:true,issues:[]});
test('fictional receipt replays the published request after restart with no inference; Test fence survives restart; personal cohorts only',async()=>{
  const f=await fixture();try{
    const key='quick-practice:bf05-request-1',receipt={type:'assessment.fictional.receipt',idempotencyKey:key};let transforms=0;
    const make=()=>createAssessmentGeneration(f.storage,native({fictionalTransform:async()=>{transforms++;return batch();},privacyReview:async input=>review(input)}));
    const sentinel='SYNTHETIC_PATIENT_SECRET_00077',input={title:'SYNTHETIC quick practice',sourceText:sentinel,instruction:'General fictional nephrology practice',count:5,idempotencyKey:key};
    assert.equal(await f.command(receipt),null);
    const first=make(),published=await first.fictionalise(input,signal());assert.equal(transforms,1);assert.equal(published.status,'ready');
    assert.deepEqual(await f.command(receipt),published);await first.close();
    await f.reopen();const restarted=make();
    assert.deepEqual(await f.command(receipt),published);
    assert.deepEqual(await restarted.fictionalise(input,signal()),published);assert.equal(transforms,1);
    assert.ok(!JSON.stringify(await f.command({type:'records.export'})).includes(sentinel));
    // Only fictional publications answer the receipt; other saved results are not readable through it.
    const generated=createAssessmentGeneration(f.storage,native({generate:async ({batchIndex})=>batch(batchIndex)}));
    const job=await generated.create({title:'SYNTHETIC saved practice',count:5,topic_id:null,inputs:[],source_refs:[],idempotencyKey:'bf05-receipt-generated'});await generated.settled(job.id);
    assert.equal(await f.command({type:'assessment.fictional.receipt',idempotencyKey:'generation-publish:'+job.id}),null);
    const test=await f.command({type:'assessment.attempts.start',versionId:published.version_id,mode:'test',timing:{kind:'untimed',duration_seconds:null},idempotencyKey:'bf05-fiction-test'});
    await f.reopen();const afterRestart=make();
    assert.equal((await f.command({type:'assessment.policy'})).assistance_allowed,false);
    await assert.rejects(afterRestart.fictionalise({...input,idempotencyKey:'quick-practice:bf05-request-2'},signal()),fail('assistance_restricted'));
    await assert.rejects(f.command({type:'assessment.generation.create',input:{title:'SYNTHETIC blocked',count:5,topic_id:null,inputs:[],source_refs:[],idempotencyKey:'bf05-blocked-generation'}}),fail('assistance_restricted'));
    await assert.rejects(f.command(receipt),fail('assistance_restricted'));
    const scored=await f.command({type:'assessment.attempts.submit',attemptId:test.id,expectedRevision:0,latestDraft:null,idempotencyKey:'bf05-fiction-submit'});
    assert.equal(scored.result.origin,'generated');assert.equal(scored.result.cohorts.personal.denominator,5);assert.equal(scored.result.cohorts.fresh.denominator,0);
    assert.deepEqual(await f.command(receipt),published);assert.equal(transforms,1);
    await afterRestart.close();await generated.close();
  }finally{await f.close();}
});
test('import refinement keeps edits, resolved keys and the original across failed normalization and reopen without self-approval',async()=>{
  const f=await fixture();try{
    const text='1. SYNTHETIC unfamiliar question\na. Alpha option\nb. Beta option\nAnswer: a';
    const created=await f.command({type:'assessment.import.create',title:'SYNTHETIC refined import',original:{kind:'paste',text,terms:'SYNTHETIC owner permission',permission_confirmed:true},idempotencyKey:'bf05-refine-original'});
    const candidate=created.candidates[0];assert.equal(candidate.key_status,'resolved');
    const edited=await f.command({type:'assessment.import.edit',importId:created.id,expectedRevision:created.revision,candidateId:candidate.id,stem:'SYNTHETIC edited stem',options:candidate.options,explanation:'',topicId:'personal-import',idempotencyKey:'bf05-refine-edit'});
    assert.equal(edited.candidates[0].key_status,'missing');
    const resolved=await f.command({type:'assessment.import.resolve',importId:created.id,expectedRevision:edited.revision,candidateId:candidate.id,optionIds:['b'],reviewConfirmed:true,idempotencyKey:'bf05-refine-resolve'});
    const at=s=>({start:text.indexOf(s),end:text.indexOf(s)+s.length});
    const normalization={candidates:[{span:{start:0,end:text.length},stem_span:at('SYNTHETIC unfamiliar question'),stem:'SYNTHETIC unfamiliar question',options:[{id:'a',text:'Alpha option',span:at('Alpha option')},{id:'b',text:'Beta option',span:at('Beta option')}],explanation:'',explanation_span:null}]};
    const normalizer=createAssessmentGeneration(f.storage,native({normalize:async()=>normalization}));
    const normalized=await normalizer.normalize(created.id,resolved.revision,signal());
    assert.equal(normalized.candidates[0].stem,'SYNTHETIC edited stem');assert.deepEqual(normalized.candidates[0].correct_option_ids,['b']);
    const failing=createAssessmentGeneration(f.storage,native({normalize:unavailable}));
    await assert.rejects(failing.normalize(created.id,normalized.revision,signal()),fail('synthetic_unavailable'));
    await normalizer.close();await failing.close();await f.reopen();
    const reopened=await f.command({type:'assessment.import.get',importId:created.id,original:false});
    assert.equal(reopened.state,'cancelled');assert.equal(reopened.call_count,2);assert.equal(reopened.result,null);
    assert.equal(reopened.candidates[0].stem,'SYNTHETIC edited stem');assert.equal(reopened.candidates[0].key_status,'resolved');assert.equal(reopened.candidates[0].review_confirmed,true);
    const original=await f.command({type:'assessment.import.get',importId:created.id,original:true});assert.equal(original.text,text);assert.equal(original.sha256,digest(text));
    assert.equal((await f.command({type:'assessment.tests.list',lifecycle:'active',limit:10,before:null})).items.length,0);
  }finally{await f.close();}
});
test('P tools record Study help before assistance and only propose practice; narrative sees the committed result only; pack withdrawal',async()=>{
  const f=await fixture();try{
    const saved=await f.command({type:'assessment.tests.reviewed',title:'SYNTHETIC broad nephrology',count:5,topicIds:[],idempotencyKey:'bf05-tools-reviewed'});
    const study=await f.command({type:'assessment.attempts.start',versionId:saved.version_id,mode:'study',timing:{kind:'untimed',duration_seconds:null},idempotencyKey:'bf05-tools-study'});
    let grants=['renulus.study.help','renulus.practice.propose'];
    const tools=createAssessmentTools({storage:f.storage,resolve:async context=>({operationId:'op1',attemptId:'att1',sessionId:context.sessionID,studyAttemptId:study.id,grants}),check:async()=>{}});
    const context={sessionID:'sess1',id:'call1'};
    const help=await tools.execute('renulus_study_help',{kind:'sources'},context,signal());
    assert.equal(help.kind,'sources');assert.ok(!JSON.stringify(help).includes('correct_option_ids'));assert.ok(!JSON.stringify(help).includes('explanation'));
    assert.deepEqual((await tools.execute('renulus_study_help',{kind:'sources'},context,signal())).context,help.context);
    await assert.rejects(tools.execute('renulus_study_help',{kind:'sources',attempt_id:'other'},{...context,id:'call-x'},signal()),e=>e.code==='storage_invalid_command'||/invalid|exact|unexpected/i.test(String(e.code??e.message)));
    const proposal=await tools.execute('renulus_practice_propose',{title:'SYNTHETIC proposal',focus:'Electrolytes',count:10},{...context,id:'call2'},signal());
    assert.equal(proposal.status,'proposal');assert.equal(proposal.requires_explicit_save,true);
    await assert.rejects(tools.execute('renulus_practice_propose',{title:'SYNTHETIC proposal',focus:'Electrolytes',count:7},{...context,id:'call3'},signal()));
    grants=['renulus.practice.propose'];
    await assert.rejects(tools.execute('renulus_study_help',{kind:'hint'},{...context,id:'call4'},signal()),fail('assessment_tool_grant_denied'));grants=['renulus.study.help','renulus.practice.propose'];
    const added=[];await Effect.runPromise(registerAssessmentTools({tool:{transform:fn=>{fn({add:t=>added.push(t)});return Effect.void;}}},tools));
    assert.deepEqual(added.map(t=>[t.name,t.options.permission]),[['renulus_study_help','renulus.study.help'],['renulus_practice_propose','renulus.practice.propose']]);
    const viaNative=await Effect.runPromise(added[0].execute({kind:'sources'},context));assert.deepEqual(JSON.parse(viaNative.content).context,help.context);
    const answered=await f.command({type:'assessment.attempts.answer',attemptId:study.id,expectedRevision:0,itemId:study.current_item.item_id,optionIds:[study.current_item.options[0].id],idempotencyKey:'bf05-tools-answer'});
    assert.equal(answered.committed[0].assisted,true);
    const test=await f.command({type:'assessment.attempts.start',versionId:saved.version_id,mode:'test',timing:{kind:'untimed',duration_seconds:null},idempotencyKey:'bf05-tools-test'});
    await assert.rejects(tools.execute('renulus_study_help',{kind:'hint'},{...context,id:'call5'},signal()),fail('attempt_restricted'));
    let seen;const producer=createAssessmentGeneration(f.storage,native({narrative:async ({committed})=>{seen=committed;return 'SYNTHETIC narrative';}}));
    await assert.rejects(producer.narrative(test.id,signal()),fail('assistance_restricted'));
    const scored=await f.command({type:'assessment.attempts.submit',attemptId:test.id,expectedRevision:0,latestDraft:null,idempotencyKey:'bf05-tools-submit'});
    const narrated=await producer.narrative(test.id,signal());assert.equal(narrated.text,'SYNTHETIC narrative');
    assert.ok(!JSON.stringify(seen).includes('correct_option_ids'));assert.ok(!('items'in seen.summary));assert.equal(seen.summary.denominator,5);
    assert.deepEqual((await f.command({type:'assessment.attempts.get',attemptId:test.id})).result,scored.result);await producer.close();
    // Reserved questions never appear in teaching material; withdrawing the pack is permanent and ends reviewed assembly.
    assert.ok(!JSON.stringify(await f.command({type:'content.topics'})).includes(study.current_item.stem));
    const manifest=(await f.command({type:'content.active'})).manifest;assert.ok(manifest);
    const withdrawal={type:'content.pack.withdraw',packId:manifest.id,version:manifest.version,reason:'SYNTHETIC withdrawal'};
    assert.equal((await f.command(withdrawal)).withdrawn,true);assert.equal((await f.command(withdrawal)).withdrawn,true);
    await assert.rejects(f.command({...withdrawal,reason:'SYNTHETIC other reason'}),fail('content_conflict'));
    assert.equal((await f.command({type:'content.active'})).manifest,null);
    await assert.rejects(f.command({type:'assessment.tests.reviewed',title:'SYNTHETIC after withdrawal',count:5,topicIds:[],idempotencyKey:'bf05-after-withdrawal'}),fail('insufficient_coverage'));
  }finally{await f.close();}
});
