// SPDX-License-Identifier: MIT
/** Durable checkpoints for the existing five-question producer semantics. */
import type { DatabaseSync } from 'node:sqlite';
import type { AssessmentCommand,GenerationView,ObjectValue,QuestionSnapshot,TestVersion } from './contracts.ts';
import { canonical,digest,one } from '../../storage/schema.ts';
import { reject } from '../../storage/contracts.ts';
import { utcNow } from '../../storage/export.ts';
import { assistance,currentStamp,decode,deleted,stamp,uid } from './local.ts';
import { publishVersion } from './versions.ts';
import { requireNightlyPublication } from '../../storage/study.ts';
import type { NightlySchedule } from '../study/contracts.ts';
const stem=(s:string)=>s.normalize('NFKC').toLowerCase().replace(/\s+/g,' ').trim();
export function generationRow(db:DatabaseSync,id:string):ObjectValue {
  const r=one(db,'SELECT * FROM assessment_test_jobs WHERE id=?',id);if(!r||deleted(db,'test_job',id))reject('not_found');return r;
}
function checkSources(db:DatabaseSync,input:ObjectValue) {
  for(const ref of input.source_refs??[]){
    if(ref.target?.type!=='library_revision'||ref.locator!==null)reject('generation_sources_changed');
    const r=one(db,"SELECT * FROM knowledge_revisions WHERE id=? AND status='ready'",ref.target.id);
    if(!r||deleted(db,'library_revision',ref.target.id)||deleted(db,'library_document',String(r.document_id)))reject('generation_sources_changed');
    const rights=decode(r.rights_json),meta=decode(r.metadata_json);if(!rights.model_input||!rights.derivation||meta.repository_removed)reject('generation_sources_changed');
  }
}
function guard(db:DatabaseSync,r:ObjectValue) {
  currentStamp(db,r as any);const cp=decode(r.checkpoint_json);if(cp.schema!=='saved-test-generation/1')reject('generation_checkpoint_unavailable');checkSources(db,cp.request);return cp;
}
export function generationView(r:ObjectValue):GenerationView {
  const cp=decode(r.checkpoint_json);return {id:r.id,state:r.state,requested_count:r.requested_count,validated_count:r.validated_count,accepted_count:r.accepted_count,published_version_id:r.published_version_id,error_code:r.error_code,policy_revision:r.policy_revision,context_epoch:r.context_epoch,checkpoint:cp,inputs:cp.request};
}
export function generationCommand(db:DatabaseSync,c:AssessmentCommand):ObjectValue {
  assistance(db);
  if(c.type==='assessment.generation.create'){
    const input=c.input,hash=digest(canonical(input)),prior=one(db,'SELECT * FROM assessment_test_jobs WHERE idempotency_key=?',input.idempotencyKey);
    if(prior){if(prior.request_hash!==hash)reject('idempotency_conflict');return generationView(prior);}
    checkSources(db,input);const id=uid('test_job'),s=stamp(db),now=utcNow();
    const request={...input,origin:input.origin??'generated'};
    if(request.origin==='nightly'&&!request.schedule)reject('nightly_schedule_required');
    db.prepare("INSERT INTO assessment_test_jobs(id,operation,state,idempotency_key,request_hash,inputs_json,checkpoint_json,settings_revision,policy_revision,context_epoch,requested_count,validated_count,accepted_count,published_version_id,live_published_version_id,error_code,created_at,updated_at) VALUES(?,?,'queued',?,?,?,?,1,?,?,?,0,NULL,NULL,NULL,NULL,?,?)").run(id,request.origin==='nightly'?'nightly_test':'generate_test',input.idempotencyKey,hash,canonical(input.inputs),canonical({schema:'saved-test-generation/1',request,batches:[],execution:null,...(request.schedule?{nightly:request.schedule}:{})}),s.policy_revision,s.context_epoch,input.count,now,now);
    return generationView(generationRow(db,id));
  }
  if(!('jobId'in c))reject('invalid_request');let r=generationRow(db,c.jobId);
  if(c.type==='assessment.generation.get')return generationView(r);
  if(c.type==='assessment.generation.cancel'){
    if(r.state!=='published')db.prepare("UPDATE assessment_test_jobs SET state='cancelled',error_code='cancelled',updated_at=? WHERE id=?").run(utcNow(),r.id);
    return generationView(generationRow(db,r.id));
  }
  const cp=guard(db,r);
  switch(c.type){
    case 'assessment.generation.interrupted':
      if(r.state==='running'&&cp.execution===c.execution)db.prepare("UPDATE assessment_test_jobs SET state='failed',error_code='interrupted',updated_at=? WHERE id=?").run(utcNow(),r.id);break;
    case 'assessment.generation.claim':
      if(r.state==='published')return generationView(r);
      currentStamp(db,c.stamp);if(c.stamp.policy_revision!==r.policy_revision||c.stamp.context_epoch!==r.context_epoch)reject('generation_context_changed');
      if(r.state==='running'&&cp.execution!==c.execution)reject('generation_in_progress');
      cp.execution=c.execution;db.prepare("UPDATE assessment_test_jobs SET state='running',checkpoint_json=?,error_code=NULL,updated_at=? WHERE id=?").run(canonical(cp),utcNow(),r.id);break;
    case 'assessment.generation.checkpoint': {
      if(r.state!=='running'||cp.execution!==c.execution)reject('generation_stopped');
      const existing=cp.batches[c.batchIndex];if(existing){if(canonical(existing)!==canonical(c.items))reject('revision_conflict');return generationView(r);}
      if(c.batchIndex!==cp.batches.length||r.validated_count+c.items.length>r.requested_count)reject('generation_invalid');
      const seen=new Set(cp.batches.flat().map((q:QuestionSnapshot)=>stem(q.stem)));for(const q of c.items){const s=stem(q.stem);if(!s||seen.has(s)||new Set(q.options.map(o=>stem(o.text))).size!==q.options.length)reject('generation_duplicate');seen.add(s);}
      cp.batches.push(c.items);const count=cp.batches.flat().length;
      db.prepare('UPDATE assessment_test_jobs SET checkpoint_json=?,validated_count=?,state=?,updated_at=? WHERE id=?').run(canonical(cp),count,count===r.requested_count?'needs_review':'running',utcNow(),r.id);break;
    }
    case 'assessment.generation.fail':
      if(cp.execution===c.execution&&r.state==='running')db.prepare("UPDATE assessment_test_jobs SET state='failed',error_code=?,updated_at=? WHERE id=?").run(c.code,utcNow(),r.id);break;
    case 'assessment.generation.publish': {
      if(r.state==='published')return {job_id:r.id,test_id:cp.result.test_id,version_id:r.published_version_id,requested_count:r.requested_count,accepted_count:r.accepted_count};
      if(r.state==='running'||c.acceptedCount>r.validated_count)reject('generation_incomplete');
      if(cp.request.origin==='nightly')requireNightlyPublication(db,cp.request.schedule as NightlySchedule);
      const items:QuestionSnapshot[]=cp.batches.flat().slice(0,c.acceptedCount);
      const v:TestVersion={id:'version_'+r.id,test_id:'test_'+r.id,ordinal:1,origin:cp.request.origin,review_quality:'personal',status:'ready',items,source_refs:cp.request.source_refs,provenance:{schema_version:1,method:cp.request.origin==='nightly'?'nightly':'generation',job_id:r.id,fictional_artifact_id:null},terms:'Personal AI-generated practice; not a reviewed-bank assessment.',created_at:utcNow()};
      const result=publishVersion(db,{type:'assessment.tests.publish',title:cp.request.title,version:v,provenance:{schema:'saved-test-provenance/1',requested_count:r.requested_count,accepted_count:c.acceptedCount,inputs:decode(r.inputs_json)},expectedRevision:null,idempotencyKey:c.idempotencyKey});cp.result=result;
      db.prepare("UPDATE assessment_test_jobs SET state='published',accepted_count=?,published_version_id=?,live_published_version_id=?,checkpoint_json=?,updated_at=? WHERE id=?").run(c.acceptedCount,v.id,v.id,canonical(cp),utcNow(),r.id);
      return {...result,job_id:r.id,requested_count:r.requested_count,accepted_count:c.acceptedCount};
    }
    default:reject('invalid_request');
  }
  return generationView(generationRow(db,r.id));
}
