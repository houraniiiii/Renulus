// SPDX-License-Identifier: MIT
/** Fixed, bounded production workflows; native OpenCode owns all model execution. */
import { randomUUID } from 'node:crypto';
import type { AssessmentStorage,GeneratedBatch,GenerationInput,GenerationView,ImportCandidate,ObjectValue,QuestionSnapshot,TestVersion } from './contracts.ts';
import { batch } from './validation.ts';
import { canonical,digest } from '../../storage/schema.ts';
import { exact,reject,text } from '../../storage/contracts.ts';
import { normalizedCandidates } from './imports.ts';
export interface AssessmentNativePort {
  /** Resolve/cancel the exact retained native execution before allowing explicit retry. */
  settleInterrupted?(job:GenerationView):Promise<'settled'|'held'>;
  generate(input:{jobId:string;batchIndex:number;count:5;priorStems:string[];input:GenerationInput;signal:AbortSignal}):Promise<GeneratedBatch>;
  normalize(input:{importId:string;originalText:string;candidates:ImportCandidate[];signal:AbortSignal}):Promise<unknown>;
  /** Both private calls MUST use the existing fully volatile graph with no raw persistence. */
  fictionalTransform(input:{sourceText:string;instruction:string;count:5;priorStems:string[];signal:AbortSignal}):Promise<GeneratedBatch>;
  privacyReview(input:{sourceText:string;instruction:string;artifactSha256:string;questions:QuestionSnapshot[];signal:AbortSignal}):Promise<{
    schema:'fictional-test-review/1';artifact_sha256:string;source_identity_removed:boolean;clinical_details_generalised:boolean;no_source_links:boolean;issues:string[];
  }>;
  narrative(input:{committed:ObjectValue;signal:AbortSignal}):Promise<string>;
}
function snapshots(output:GeneratedBatch,prefix:string,topic:string):QuestionSnapshot[] {
  batch(output);return output.items.map((q,i)=>({item_id:prefix+'_item_'+i,question_id:prefix+'_question_'+i,question_version:'1',key_version:'1',family_id:prefix+'_family_'+i,family_version:'1',topic_id:topic,stem:q.stem,options:q.options.map(o=>({id:o.id,text:o.text})),correct_option_ids:[q.correct_option_id],explanation:q.explanation}));
}
/** Independent conservative source-overlap refusal, matching fictionalisation.py. */
export function privacyOverlap(source:string,output:string) {
  source=source.normalize('NFKC').toLowerCase();output=output.normalize('NFKC').toLowerCase();
  const patterns=[/[\w.+-]+@[\w.-]+\.[a-z]{2,}/g,/https?:\/\/[^\s]+/g,/\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b/g,/(?<!\w)\+?\d[\d ()-]{6,}\d(?!\w)/g,/\b[\w.-]{8,}\b/g];
  for(let i=0;i<patterns.length;i++)for(const match of source.matchAll(patterns[i])){const v=match[0];if(i===4&&!v.includes('_')&&!(/\d/.test(v)&&/[a-z]/.test(v)))continue;if(output.includes(v))return true;}
  for(const m of source.matchAll(/(?:patient(?: name)?|name|address|hospital|mrn|identifier|dob|clinician)\s*[:=]\s*([^\n;,]{3,100})/g))if(output.includes(m[1].trim()))return true;
  const original=source.match(/[\p{L}\p{N}_]+/gu)??[],fictional=output.match(/[\p{L}\p{N}_]+/gu)??[];
  const phrases=new Set();for(let i=0;i+8<=original.length;i++)phrases.add(original.slice(i,i+8).join(' '));for(let i=0;i+8<=fictional.length;i++)if(phrases.has(fictional.slice(i,i+8).join(' ')))return true;return false;
}
export function createAssessmentGeneration(storage:AssessmentStorage,native:AssessmentNativePort) {
  const active=new Map<string,{controller:AbortController;promise:Promise<void>}>();
  const read=(jobId:string)=>storage.command({type:'assessment.generation.get',jobId});
  async function produce(jobId:string,controller:AbortController) {
    let current=await read(jobId);if(current.state==='published')return;
    const execution='generation_'+randomUUID().replaceAll('-','');
    current=await storage.command({type:'assessment.generation.claim',jobId,execution,stamp:{policy_revision:current.policy_revision,context_epoch:current.context_epoch}});
    try{
      for(let index=current.checkpoint.batches.length;index<current.requested_count/5;index++){
        controller.signal.throwIfAborted();const output=await native.generate({jobId,batchIndex:index,count:5,priorStems:current.checkpoint.batches.flat().map((q:QuestionSnapshot)=>q.stem),input:current.inputs as GenerationInput,signal:controller.signal});
        controller.signal.throwIfAborted();batch(output);if(output.items.length!==5)reject('generation_invalid');
        const items=snapshots(output,jobId+'_batch_'+index,current.inputs.topic_id??'general');
        current=await storage.command({type:'assessment.generation.checkpoint',jobId,execution,batchIndex:index,items});
      }
      controller.signal.throwIfAborted();await storage.command({type:'assessment.generation.publish',jobId,acceptedCount:current.requested_count,idempotencyKey:'generation-publish:'+jobId});
    }catch(error){const code=error&&typeof error==='object'&&'code'in error?String(error.code):controller.signal.aborted?'cancelled':'generation_failed';try{await storage.command({type:'assessment.generation.fail',jobId,execution,code:/^[a-z][a-z0-9_]+$/.test(code)?code:'generation_failed'});}catch{/* The original checkpoint and cancellation stay authoritative. */}}
  }
  function run(jobId:string) {
    if(active.has(jobId))return;
    const controller=new AbortController();const promise=produce(jobId,controller).finally(()=>{active.delete(jobId);});
    // All failures are reflected by durable state; observer detach never resends or cancels.
    promise.catch(()=>{});active.set(jobId,{controller,promise});
  }
  const api={
    async create(input:GenerationInput){const job=await storage.command({type:'assessment.generation.create',input});if(job.state==='queued')run(job.id);return job;},
    async resume(jobId:string){
      const job=await read(jobId);if(active.has(jobId)||job.state==='published')return job;
      if(job.state==='running'){
        if(!native.settleInterrupted||await native.settleInterrupted(job)!=='settled')reject('generation_settlement_required');
        await storage.command({type:'assessment.generation.interrupted',jobId,execution:job.checkpoint.execution});
      }
      run(jobId);return read(jobId);
    },
    read,
    async settled(jobId:string){await active.get(jobId)?.promise;return read(jobId);},
    async cancel(jobId:string){const job=await storage.command({type:'assessment.generation.cancel',jobId});active.get(jobId)?.controller.abort();return job;},
    async acceptShorter(jobId:string,count:number,idempotencyKey:string){if(active.has(jobId))reject('generation_in_progress');return storage.command({type:'assessment.generation.publish',jobId,acceptedCount:count,idempotencyKey});},
    async normalize(importId:string,expectedRevision:number,signal:AbortSignal){
      const execution='normalize_'+randomUUID().replaceAll('-','');const claimed=await storage.command({type:'assessment.import.claim',importId,expectedRevision,execution});
      try{
        const output=await native.normalize({importId,originalText:claimed.original_text,candidates:claimed.candidates,signal});signal.throwIfAborted();
        const candidates=normalizedCandidates(claimed.original_text,output);return await storage.command({type:'assessment.import.normalized',importId,execution,candidates});
      }catch(error){try{await storage.command({type:'assessment.import.cancel',importId,expectedRevision,idempotencyKey:'normalization-failed:'+execution});}catch{/* Retained edits may have advanced. */}throw error;}
    },
    async fictionalise(input:{title:string;sourceText:string;instruction:string;count:5|10|20;idempotencyKey:string},signal:AbortSignal){
      text(input.title,1,120);text(input.sourceText,1,32000);text(input.instruction,0,2000);text(input.idempotencyKey,8,128);if(![5,10,20].includes(input.count))reject('fictionalisation_input');
      const initial=await storage.command({type:'assessment.policy'});if(!initial.assistance_allowed)reject('assistance_restricted');
      // Read the canonical context without persisting source, source digest or a raw job.
      const s=await storage.command({type:'assessment.fictional.stamp'});
      const id='fictional_'+randomUUID().replaceAll('-',''),questions:QuestionSnapshot[]=[];
      for(let i=0;i<input.count/5;i++){
        signal.throwIfAborted();const output=await native.fictionalTransform({sourceText:input.sourceText,instruction:input.instruction,count:5,priorStems:questions.map(q=>q.stem),signal});batch(output);
        if(output.items.length!==5||output.items.some(q=>q.source_indices?.length)||privacyOverlap(input.sourceText+'\n'+input.instruction,canonical(output)))reject('fictionalisation_privacy_refused');
        questions.push(...snapshots(output,id+'_batch_'+i,'general'));
      }
      if(new Set(questions.map(q=>q.stem.normalize('NFKC').toLowerCase().replace(/\s+/g,' '))).size!==questions.length||privacyOverlap(input.sourceText+'\n'+input.instruction,canonical(questions)))reject('fictionalisation_privacy_refused');
      const artifactSha256=digest(canonical(questions));const review=await native.privacyReview({sourceText:input.sourceText,instruction:input.instruction,artifactSha256,questions,signal});
      exact(review,['schema','artifact_sha256','source_identity_removed','clinical_details_generalised','no_source_links','issues']);
      if(review.schema!=='fictional-test-review/1'||review.artifact_sha256!==artifactSha256||review.source_identity_removed!==true||review.clinical_details_generalised!==true||review.no_source_links!==true||!Array.isArray(review.issues)||review.issues.length)reject('fictionalisation_privacy_refused');signal.throwIfAborted();
      const version:TestVersion={id:'version_'+id,test_id:'test_'+id,ordinal:1,origin:'generated',review_quality:'personal',status:'ready',items:questions,source_refs:[],terms:'Original fictional educational practice; not reviewed-bank content.',created_at:new Date().toISOString(),provenance:{schema_version:1,method:'generation',job_id:null,fictional_artifact_id:id}};
      return storage.command({type:'assessment.tests.publish',title:input.title,version,provenance:{schema:'saved-test-provenance/1',fictional_review:review,expected_stamp:s},expectedRevision:null,idempotencyKey:input.idempotencyKey});
    },
    async narrative(attemptId:string,signal:AbortSignal){const committed=await storage.command({type:'assessment.narrative.input',attemptId});const output=await native.narrative({committed,signal});signal.throwIfAborted();text(output,1,16000);const current=await storage.command({type:'assessment.narrative.input',attemptId});if(canonical(current)!==canonical(committed))reject('assistance_changed');return {attempt_id:attemptId,text:output,result_revision:committed.result_revision};},
    async close(){for(const entry of active.values())entry.controller.abort();await Promise.allSettled([...active.values()].map(e=>e.promise));},
  };
  return api;
}
export type AssessmentGeneration=ReturnType<typeof createAssessmentGeneration>;
