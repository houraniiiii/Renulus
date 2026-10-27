// SPDX-License-Identifier: MIT
import type { DatabaseSync } from 'node:sqlite';
import type { AssessmentCommand,ImportCandidate,ObjectValue,TestVersion } from './contracts.ts';
import { canonical,digest,one } from '../../storage/schema.ts';
import { reject } from '../../storage/contracts.ts';
import { utcNow } from '../../storage/export.ts';
import { assistance,currentStamp,decode,deleted,record,replay,stamp } from './local.ts';
import { parseOriginal } from './imports.ts';
import { publishVersion } from './versions.ts';
function row(db:DatabaseSync,id:string):ObjectValue {const r=one(db,'SELECT * FROM assessment_test_imports WHERE id=?',id);if(!r||deleted(db,'test_import',id))reject('not_found');return r;}
function view(r:ObjectValue) {const candidates=decode(r.candidates_json);return {id:r.id,title:r.title,state:r.state,revision:r.revision,source_kind:r.source_kind,source_revision_id:r.source_revision_id,candidates,candidate_count:candidates.filter((i:ImportCandidate)=>!i.removed).length,call_count:r.call_count,max_calls:3,error_code:r.error_code,result:r.published_version_id?{test_id:'import_test_'+r.id,version_id:r.published_version_id}:null,result_available:!!r.live_published_version_id,created_at:r.created_at,updated_at:r.updated_at};}
export function importCommand(db:DatabaseSync,c:AssessmentCommand):ObjectValue {
  assistance(db);
  if(c.type==='assessment.import.create'){
    const id='import_'+digest(c.idempotencyKey).slice(0,32);if(deleted(db,'test_import',id))reject('not_found');const old=replay(db,'assessment_test_commands',c.idempotencyKey,c.type,id,c);if(old)return old;
    const s=stamp(db),now=utcNow();db.prepare("INSERT INTO assessment_test_imports(id,title,state,revision,source_kind,source_revision_id,live_source_revision_id,original_text,original_sha256,original_json,candidates_json,checkpoint_json,policy_revision,context_epoch,call_count,idempotency_key,request_hash,published_version_id,live_published_version_id,error_code,created_at,updated_at) VALUES(?,?,'draft',1,'paste',NULL,NULL,?,?,?,?,?,?,?,0,?,?,NULL,NULL,NULL,?,?)").run(id,c.title,c.original.text,digest(c.original.text),canonical(c.original),canonical(parseOriginal(c.original.text)),canonical({schema:'saved-test-import/1',execution:null}),s.policy_revision,s.context_epoch,c.idempotencyKey,digest(canonical(c)),now,now);
    return record(db,'assessment_test_commands',c.idempotencyKey,c.type,'test_import',id,c,view(row(db,id)));
  }
  if(!('importId'in c))reject('invalid_request');let r=row(db,c.importId);
  if(c.type==='assessment.import.get')return c.original?{text:r.original_text,sha256:r.original_sha256,original:decode(r.original_json)}:view(r);
  if('idempotencyKey'in c){const old=replay(db,'assessment_test_commands',c.idempotencyKey,c.type,r.id,c);if(old)return old;}
  const cp=decode(r.checkpoint_json),candidates:ImportCandidate[]=decode(r.candidates_json);
  if(c.type==='assessment.import.normalized'){
    currentStamp(db,r as any);if(r.state!=='running'||cp.execution!==c.execution||cp.base_revision!==r.revision)reject('import_stopped');
    // Existing user edits and removal decisions always win over a later normalizer.
    const protectedItems=candidates.filter(i=>i.removed||i.review_confirmed||i.revision>1);
    const overlaps=(a:ImportCandidate,b:ImportCandidate)=>a.span.start<b.span.end&&b.span.start<a.span.end;
    const merged=[...c.candidates.filter(i=>!protectedItems.some(p=>overlaps(i,p))),...protectedItems].sort((a,b)=>a.span.start-b.span.start);
    if(merged.length>50)reject('import_candidate_limit');
    db.prepare("UPDATE assessment_test_imports SET state='draft',candidates_json=?,revision=revision+1,updated_at=? WHERE id=?").run(canonical(merged),utcNow(),r.id);return view(row(db,r.id));
  }
  if(!('expectedRevision'in c)||c.expectedRevision!==r.revision)reject('revision_conflict');
  if(r.state==='published')reject('import_already_published');
  if(c.type==='assessment.import.claim'){
    if(r.state==='running')reject('import_in_progress');if(r.call_count>=3)reject('import_call_limit');
    const s=stamp(db);cp.execution=c.execution;cp.base_revision=r.revision;
    db.prepare("UPDATE assessment_test_imports SET state='running',checkpoint_json=?,call_count=call_count+1,policy_revision=?,context_epoch=?,error_code=NULL,updated_at=? WHERE id=?").run(canonical(cp),s.policy_revision,s.context_epoch,utcNow(),r.id);
    return {...view(row(db,r.id)),original_text:r.original_text};
  }
  if(c.type==='assessment.import.cancel'){
    db.prepare("UPDATE assessment_test_imports SET state='cancelled',revision=revision+1,updated_at=? WHERE id=?").run(utcNow(),r.id);
  }else if(c.type==='assessment.import.publish'){
    if(r.state==='running')reject('import_in_progress');const selected=candidates.filter(i=>!i.removed);if(!selected.length||selected.some(i=>i.key_status!=='resolved'||!i.correct_option_ids.length))reject('import_keys_unresolved');
    const items=selected.map(i=>({item_id:i.id,question_id:'import_question_'+r.id+'_'+i.id,question_version:String(i.revision),key_version:String(i.revision),family_id:'import_family_'+r.id+'_'+i.id,family_version:'1',topic_id:i.topic_id,stem:i.stem,options:i.options,correct_option_ids:i.correct_option_ids,explanation:i.explanation}));
    const v:TestVersion={id:'import_version_'+r.id,test_id:'import_test_'+r.id,ordinal:1,origin:'imported',review_quality:'personal',status:'ready',items,source_refs:[],terms:decode(r.original_json).terms,provenance:{schema_version:1,method:'import',job_id:null,fictional_artifact_id:null},created_at:utcNow()};
    const out=publishVersion(db,{type:'assessment.tests.publish',title:r.title,version:v,provenance:{schema:'saved-test-provenance/1',import_id:r.id,original_sha256:r.original_sha256,candidates:selected},expectedRevision:null,idempotencyKey:'internal:'+c.idempotencyKey});
    db.prepare("UPDATE assessment_test_imports SET state='published',revision=revision+1,published_version_id=?,live_published_version_id=?,updated_at=? WHERE id=?").run(v.id,v.id,utcNow(),r.id);
    return record(db,'assessment_test_commands',c.idempotencyKey,c.type,'test_import',r.id,c,{...view(row(db,r.id)),result:out});
  }else if('candidateId'in c){
    const candidate=candidates.find(i=>i.id===c.candidateId);if(!candidate)reject('not_found');
    if(c.type==='assessment.import.edit'){
      const changed=canonical(candidate.options)!==canonical(c.options)||candidate.stem!==c.stem;Object.assign(candidate,{stem:c.stem,options:c.options,explanation:c.explanation,topic_id:c.topicId,revision:candidate.revision+1});
      if(changed)Object.assign(candidate,{correct_option_ids:[],key_status:'missing',review_confirmed:false});
    }else if(c.type==='assessment.import.resolve'){
      if(c.optionIds.some(id=>!candidate.options.some(o=>o.id===id)))reject('invalid_request');Object.assign(candidate,{correct_option_ids:c.optionIds,key_status:'resolved',review_confirmed:true,revision:candidate.revision+1});
    }else if(c.type==='assessment.import.visibility')candidate.removed=c.removed;
    else reject('invalid_request');
    db.prepare("UPDATE assessment_test_imports SET state='draft',candidates_json=?,revision=revision+1,updated_at=? WHERE id=?").run(canonical(candidates),utcNow(),r.id);
  }else reject('invalid_request');
  return record(db,'assessment_test_commands',(c as any).idempotencyKey,c.type,'test_import',r.id,c,view(row(db,r.id)));
}
