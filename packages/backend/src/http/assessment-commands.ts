// SPDX-License-Identifier: MIT
/** Existing JSON assessment routes. Internal publish/claim/key authority is never exposed. */
import type { IncomingMessage } from 'node:http';
import type { StorageClient } from '../storage/index.ts';
import type { AssessmentGeneration } from '../domain/assessment/generation.ts';
import type { AssessmentCommand,DraftState,GenerationInput,ObjectValue } from '../domain/assessment/contracts.ts';
import { exact,reject } from '../storage/contracts.ts';
import { readJsonObject } from './body.ts';
type Response={status:number;value:unknown};
export async function assessmentCommand(request:IncomingMessage,url:URL,storage:StorageClient,generation?:AssessmentGeneration):Promise<Response|undefined> {
  if(!url.pathname.startsWith('/api/v1/assessment/'))return;
  const path=url.pathname.slice('/api/v1/assessment/'.length),method=request.method;
  const result=(value:unknown,status=200)=>({status,value});
  const body=()=>readJsonObject(request,1024*1024);
  const key=(b?:ObjectValue)=>{const h=request.headers['idempotency-key'];if(Array.isArray(h))reject('invalid_request');return h??b?.idempotency_key??'';};
  const producer=()=>{if(!generation)reject('assessment_generation_unavailable');return generation;};
  // The receipt is host-only and may be null; no public route reads it.
  const command=(c:Exclude<AssessmentCommand,{type:'assessment.fictional.receipt'}>)=>storage.command(c);
  // Validated draft keys/checkpoints are trusted producer material, not pre-attempt output.
  const generationView=(job:ObjectValue)=>({id:job.id,state:job.state,requested_count:job.requested_count,validated_count:job.validated_count,accepted_count:job.accepted_count,published_version_id:job.published_version_id,error_code:job.error_code,result:job.published_version_id?{version_id:job.published_version_id}:null});
  if(path==='policy'&&method==='GET')return result(await command({type:'assessment.policy'}));
  if(path==='test-attempts'){
    if(method==='GET')return result(await command({type:'assessment.attempts.list'}));
    if(method==='POST'){const b=await body();exact(b,['version','mode','timing']);exact(b.version,['type','id']);if(b.version.type!=='saved_test_version')reject('invalid_request');return result(await command({type:'assessment.attempts.start',versionId:b.version.id as string,mode:b.mode as 'study'|'test',timing:{duration_seconds:null,...b.timing as ObjectValue} as never,idempotencyKey:key()}),201);}
  }
  const attempt=/^test-attempts\/([A-Za-z0-9_.:-]+)(?:\/(.+))?$/.exec(path);
  if(attempt){
    const attemptId=attempt[1],action=attempt[2]??'';
    if(!action&&method==='GET')return result(await command({type:'assessment.attempts.get',attemptId}));
    if(method==='POST'||method==='PUT'){
      const b=await body(),expectedRevision=b.expected_revision as number,idempotencyKey=key(b);
      switch(action){
        case 'draft':exact(b,['expected_revision','position','answers']);return result(await command({type:'assessment.attempts.draft',attemptId,expectedRevision,draft:{position:b.position,answers:b.answers} as DraftState,idempotencyKey}));
        case 'present':exact(b,['expected_revision','item_id']);return result(await command({type:'assessment.attempts.present',attemptId,expectedRevision,itemId:b.item_id as string,idempotencyKey}));
        case 'submit-answer':exact(b,['expected_revision','item_id','option_ids']);return result(await command({type:'assessment.attempts.answer',attemptId,expectedRevision,itemId:b.item_id as string,optionIds:b.option_ids as string[],idempotencyKey}));
        case 'submit':exact(b,['expected_draft_revision',...('latest_draft'in b?['latest_draft']:[])]);return result(await command({type:'assessment.attempts.submit',attemptId,expectedRevision:b.expected_draft_revision as number,latestDraft:(b.latest_draft??null) as DraftState|null,idempotencyKey}));
        case 'help':exact(b,['expected_revision','expected_policy_revision','item_id','kind']);return result(await command({type:'assessment.attempts.help',attemptId,expectedRevision,expectedPolicyRevision:b.expected_policy_revision as number,itemId:b.item_id as string,kind:b.kind as never,idempotencyKey}));
        case 'pause':case 'resume':case 'continue-untimed':exact(b,['expected_revision']);return result(await command({type:'assessment.attempts.transition',attemptId,expectedRevision,action,idempotencyKey}));
        case 'reports':exact(b,['item_id','report_text']);return result(await command({type:'assessment.report',attemptId,itemId:b.item_id as string,reportText:b.report_text as string,idempotencyKey}),201);
        case 'narrative':exact(b,[]);return result(await producer().narrative(attemptId,new AbortController().signal));
      }
    }
  }
  if(path==='tests'&&method==='GET')return result(await command({type:'assessment.tests.list',lifecycle:(url.searchParams.get('lifecycle')??'active') as never,limit:Number(url.searchParams.get('limit')??50),before:url.searchParams.get('cursor')}));
  if(path==='tests/reviewed'&&method==='POST'){
    const b=await body();exact(b,['idempotency_key',...('title'in b?['title']:[]),...('count'in b?['count']:[]),...('selector'in b?['selector']:[])]);
    const selector=(b.selector??{}) as ObjectValue;exact(selector,[...('domain_ids'in selector?['domain_ids']:[]),...('topic_ids'in selector?['topic_ids']:[]),...('track'in selector?['track']:[])]);
    // Track mapping is not inferred from a topic label.
    if(selector.track&&selector.track!=='general_nephrology')reject('track_unavailable');
    return result(await command({type:'assessment.tests.reviewed',title:(b.title??'Reviewed practice') as string,count:(b.count??5) as number,topicIds:(selector.topic_ids??selector.domain_ids??[]) as string[],idempotencyKey:key(b)}),201);
  }
  const setup=/^tests\/versions\/([A-Za-z0-9_.:-]+)\/setup$/.exec(path);if(setup&&method==='GET')return result(await command({type:'assessment.tests.setup',versionId:setup[1]}));
  const test=/^tests\/([A-Za-z0-9_.:-]+)(?:\/(.*))?$/.exec(path);
  if(test){
    const testId=test[1],action=test[2]??'';
    if(method==='GET'){
      if(!action)return result(await command({type:'assessment.tests.get',testId}));
      if(action==='setup'){let versionId=url.searchParams.get('version_id');if(!versionId){const detail=await command({type:'assessment.tests.get',testId});versionId=detail.latest_version?.id??null;}if(!versionId)reject('not_found');const setup=await command({type:'assessment.tests.setup',versionId});if(setup.test.id!==testId)reject('not_found');return result(setup);}
      if(action==='versions'){const detail=await command({type:'assessment.tests.get',testId});return result({items:detail.versions,next_before:null});}
      const preview=/^versions\/([A-Za-z0-9_.:-]+)\/preview$/.exec(action);if(preview)return result(await command({type:'assessment.tests.preview',versionId:preview[1]}));
    }
    if((!action&&['PATCH','DELETE'].includes(method??''))||(['archive','restore'].includes(action)&&method==='POST')){const b=await body();exact(b,['expected_revision','idempotency_key',...(method==='PATCH'?['title']:[])]);return result(await command({type:'assessment.tests.change',testId,expectedRevision:b.expected_revision as number,action:method==='PATCH'?'rename':method==='DELETE'?'delete':action as 'archive'|'restore',title:method==='PATCH'?b.title as string:null,idempotencyKey:key(b)}));}
  }
  if((path==='generation/jobs'||path==='generation/quick-practice')&&method==='POST'){
    const b=await body();exact(b,['idempotency_key',...('title'in b?['title']:[]),...('count'in b?['count']:[]),...('topic_id'in b?['topic_id']:[]),...('inputs'in b?['inputs']:[]),...('source_refs'in b?['source_refs']:[])]);
    if(path.endsWith('quick-practice')&&(b.count??5)!==5)reject('invalid_request');
    return result(generationView(await producer().create({title:(b.title??'Generated practice') as string,count:(b.count??5) as GenerationInput['count'],topic_id:(b.topic_id??null) as string|null,inputs:(b.inputs??[]) as ObjectValue[],source_refs:(b.source_refs??[]) as ObjectValue[],idempotencyKey:key(b)})),202);
  }
  const job=/^generation\/jobs\/([A-Za-z0-9_.:-]+)(?:\/(retry|cancel|accept-shorter))?$/.exec(path);
  if(job){if(!job[2]&&method==='GET')return result(generationView(await command({type:'assessment.generation.get',jobId:job[1]})));if(method==='POST'){const b=await body();exact(b,['idempotency_key',...(job[2]==='accept-shorter'?['accepted_count']:[])]);if(job[2]==='retry')return result(generationView(await producer().resume(job[1])));if(job[2]==='cancel')return result(generationView(await producer().cancel(job[1])));if(job[2]==='accept-shorter')return result(await producer().acceptShorter(job[1],b.accepted_count as number,key(b)));}}
  if(path==='imports'&&method==='POST'){const b=await body();exact(b,['idempotency_key','original',...('title'in b?['title']:[])]);return result(await command({type:'assessment.import.create',title:(b.title??'Imported practice') as string,original:b.original as never,idempotencyKey:key(b)}),201);}
  const imported=/^imports\/([A-Za-z0-9_.:-]+)(?:\/(.*))?$/.exec(path);
  if(imported){
    const importId=imported[1],action=imported[2]??'';
    if(method==='GET'&&(!action||action==='original'))return result(await command({type:'assessment.import.get',importId,original:action==='original'}));
    if(method==='POST'){
      const b=await body(),idempotencyKey=key(b),expectedRevision=b.expected_revision as number;
      if(['normalize','retry','save','cancel'].includes(action)){
        exact(b,['idempotency_key',...(action!=='cancel'?['expected_revision']:[])]);
        if(action==='normalize'||action==='retry')return result(await producer().normalize(importId,expectedRevision,new AbortController().signal),202);
        if(action==='cancel'){const current=await command({type:'assessment.import.get',importId,original:false});return result(await command({type:'assessment.import.cancel',importId,expectedRevision:current.revision,idempotencyKey}));}
        return result(await command({type:'assessment.import.publish',importId,expectedRevision,idempotencyKey}));
      }
      const candidate=/^candidates\/([A-Za-z0-9_.:-]+)\/(edit|resolve|visibility)$/.exec(action);
      if(candidate){const candidateId=candidate[1];if(candidate[2]==='edit'){exact(b,['idempotency_key','expected_revision','stem','options',...('explanation'in b?['explanation']:[]),...('topic_id'in b?['topic_id']:[])]);return result(await command({type:'assessment.import.edit',importId,expectedRevision,candidateId,stem:b.stem as string,options:b.options as never,explanation:(b.explanation??'') as string,topicId:(b.topic_id??'personal-import') as string,idempotencyKey}));}if(candidate[2]==='resolve'){exact(b,['idempotency_key','expected_revision','correct_option_ids','review_confirmed']);return result(await command({type:'assessment.import.resolve',importId,expectedRevision,candidateId,optionIds:b.correct_option_ids as string[],reviewConfirmed:b.review_confirmed as true,idempotencyKey}));}exact(b,['idempotency_key','expected_revision','removed']);return result(await command({type:'assessment.import.visibility',importId,expectedRevision,candidateId,removed:b.removed as boolean,idempotencyKey}));}
    }
  }
  return undefined;
}
export const handleAssessmentCommand=assessmentCommand;
