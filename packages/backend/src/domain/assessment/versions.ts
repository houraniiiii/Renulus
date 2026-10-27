// SPDX-License-Identifier: MIT
/** SavedTestRepository semantics; callers own BEGIN/COMMIT and publication fences. */
import type { DatabaseSync } from 'node:sqlite';
import type { AssessmentCommand, ObjectValue, TestVersion } from './contracts.ts';
import { version as validateVersion } from './validation.ts';
import { canonical,digest,one,rows } from '../../storage/schema.ts';
import { reject } from '../../storage/contracts.ts';
import { utcNow } from '../../storage/export.ts';
import { activeContent,questionAvailability,reviewedQuestion } from '../../storage/content.ts';
import { assistance,bank,currentStamp,decode,deleted,pinned,record,replay,test,uid } from './local.ts';
export function summary(v:ObjectValue) {const items=decode(v.items_json);return {id:v.id,test_id:v.test_id,ordinal:v.ordinal,origin:v.origin,review_quality:v.review_quality,status:v.status,created_at:v.created_at,item_count:items.length,topic_ids:[...new Set(items.map((i:ObjectValue)=>i.topic_id))].sort()};}
export function publishVersion(db:DatabaseSync,c:Extract<AssessmentCommand,{type:'assessment.tests.publish'}>):ObjectValue {
  assistance(db);const v=c.version;validateVersion(v);
  if(v.provenance.fictional_artifact_id){
    const review=c.provenance.fictional_review;currentStamp(db,c.provenance.expected_stamp);
    if(!review||review.schema!=='fictional-test-review/1'||review.artifact_sha256!==digest(canonical(v.items))||review.source_identity_removed!==true||review.clinical_details_generalised!==true||review.no_source_links!==true||!Array.isArray(review.issues)||review.issues.length||v.provenance.job_id!==null||v.source_refs.length)reject('fictional_artifact_untrusted');
  }
  if(deleted(db,'saved_test',v.test_id)||deleted(db,'saved_test_version',v.id))reject('not_found');
  const prior=replay(db,'assessment_test_commands',c.idempotencyKey,'publish_version',v.test_id,c);if(prior)return prior;
  const provenance:ObjectValue={...c.provenance,producer:v.provenance};if(provenance.schema!=='saved-test-provenance/1')reject('invalid_request');
  const hash=digest(canonical({version:v,provenance}));const old=one(db,'SELECT * FROM assessment_test_versions WHERE id=?',v.id);const t=one(db,'SELECT * FROM assessment_tests WHERE id=?',v.test_id);
  if(old){if(old.sha256!==hash)reject('revision_conflict');}
  else {
    if(t){if(t.lifecycle!=='active'||t.revision!==c.expectedRevision||v.ordinal!==Number(one(db,'SELECT MAX(ordinal) AS n FROM assessment_test_versions WHERE test_id=?',v.test_id)?.n??0)+1)reject('revision_conflict');db.prepare('UPDATE assessment_tests SET revision=revision+1,updated_at=? WHERE id=?').run(utcNow(),v.test_id);}
    else {if(c.expectedRevision!==null||v.ordinal!==1)reject('revision_conflict');db.prepare("INSERT INTO assessment_tests VALUES(?,?,'active',1,?,?)").run(v.test_id,c.title,v.created_at,v.created_at);}
    db.prepare('INSERT INTO assessment_test_versions(id,test_id,ordinal,origin,review_quality,status,items_json,source_refs_json,terms,sha256,provenance_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)').run(v.id,v.test_id,v.ordinal,v.origin,v.review_quality,v.status,canonical(v.items),canonical(v.source_refs),v.terms,hash,canonical(provenance),v.created_at);
  }
  return record(db,'assessment_test_commands',c.idempotencyKey,'publish_version','saved_test',v.test_id,c,{test_id:v.test_id,version_id:v.id,revision:test(db,v.test_id).revision,status:v.status});
}
export function versionCommand(db:DatabaseSync,c:AssessmentCommand):ObjectValue {
  assistance(db);
  switch(c.type){
    case 'assessment.tests.publish':return publishVersion(db,c);
    case 'assessment.tests.list': {const all=rows(db,"SELECT * FROM assessment_tests WHERE lifecycle=? AND id>? ORDER BY id LIMIT ?",c.lifecycle,c.before??'',c.limit+1);return {items:all.slice(0,c.limit).filter(t=>!deleted(db,'saved_test',String(t.id))).map(t=>({...t,latest_version:(()=>{const v=one(db,'SELECT * FROM assessment_test_versions WHERE test_id=? ORDER BY ordinal DESC LIMIT 1',String(t.id));return v?summary(v):null;})()})),next_cursor:all.length>c.limit?all[c.limit-1].id:null,legacy_unavailable:0};}
    case 'assessment.tests.get': {const t=test(db,c.testId);const versions=rows(db,'SELECT * FROM assessment_test_versions WHERE test_id=? ORDER BY ordinal DESC LIMIT 50',c.testId).map(summary);return {...t,versions,latest_version:versions[0]??null};}
    case 'assessment.tests.preview': {const v=pinned(db,c.versionId);return {version_id:v.id,items:v.items.map(({correct_option_ids:_k,explanation:_e,key_version:_kv,...q})=>q)};}
    case 'assessment.tests.setup': {const v=pinned(db,c.versionId),t=test(db,v.test_id);const warnings=bank(v)?v.items.map(q=>({item_id:q.item_id,status:questionAvailability(db,q)})).filter(w=>w.status!=='current'):[];return {test:t,version:{id:v.id,test_id:v.test_id,ordinal:v.ordinal,origin:v.origin,review_quality:v.review_quality,status:v.status,item_count:v.items.length,topic_ids:[...new Set(v.items.map(q=>q.topic_id))]},can_start:v.status==='ready'&&t.lifecycle==='active'&&!warnings.length,content_warnings:warnings,modes:['study','test'],timing_default:'untimed'};}
    case 'assessment.tests.reviewed': {
      const prior=replay(db,'assessment_test_commands',c.idempotencyKey,c.type,'',c);if(prior){test(db,prior.test_id);return prior;}
      const families=new Set(),chosen=activeContent(db,'questions').filter(q=>reviewedQuestion(q)&&(!c.topicIds.length||c.topicIds.includes(q.topic_id))).filter(q=>{if(families.has(q.family_id))return false;families.add(q.family_id);return true;}).slice(0,c.count);
      if(chosen.length!==c.count)reject('insufficient_coverage');
      const v:TestVersion={id:uid('test_version'),test_id:uid('test'),ordinal:1,origin:'reviewed_bank',review_quality:'reviewed',status:'ready',items:chosen.map(q=>({item_id:uid('test_item'),question_id:q.id,question_version:String(q.version),key_version:String(q.key_version),family_id:q.family_id,family_version:String(q.family_version),topic_id:q.topic_id,stem:q.stem,options:q.options.map((o:ObjectValue)=>({id:o.id,text:o.text})),correct_option_ids:[q.answer],explanation:q.rationale})),source_refs:[],terms:'Original published content and source terms are retained in provenance.',created_at:utcNow(),provenance:{schema_version:1,method:'reviewed_pack',job_id:null,fictional_artifact_id:null}};
      const out=publishVersion(db,{type:'assessment.tests.publish',title:c.title,version:v,provenance:{schema:'saved-test-provenance/1',items:chosen.map((q,i)=>({item_id:v.items[i].item_id,original_snapshot:q}))},expectedRevision:null,idempotencyKey:'internal:'+digest(c.idempotencyKey)});
      return record(db,'assessment_test_commands',c.idempotencyKey,c.type,'collection','',c,out);
    }
    case 'assessment.tests.change': {
      const t=test(db,c.testId),prior=replay(db,'assessment_test_commands',c.idempotencyKey,c.type,c.testId,c);if(prior)return prior;if(t.revision!==c.expectedRevision)reject('revision_conflict');
      if(c.action==='rename')db.prepare('UPDATE assessment_tests SET title=?,revision=revision+1,updated_at=? WHERE id=?').run(c.title!,utcNow(),c.testId);
      else db.prepare('UPDATE assessment_tests SET lifecycle=?,revision=revision+1,updated_at=? WHERE id=?').run(c.action==='archive'?'archived':c.action==='restore'?'active':'deleted',utcNow(),c.testId);
      if(c.action==='delete'){
        db.prepare('UPDATE assessment_test_attempts SET live_version_id=NULL WHERE version_id IN(SELECT id FROM assessment_test_versions WHERE test_id=?)').run(c.testId);
        db.prepare('UPDATE assessment_question_reports SET live_version_id=NULL WHERE version_id IN(SELECT id FROM assessment_test_versions WHERE test_id=?)').run(c.testId);
      }
      db.prepare("INSERT INTO preferences VALUES('design_c.context_epoch','1',?) ON CONFLICT(key) DO UPDATE SET value=CAST(CAST(preferences.value AS INTEGER)+1 AS TEXT),updated_at=excluded.updated_at").run(utcNow());
      return record(db,'assessment_test_commands',c.idempotencyKey,c.type,'saved_test',c.testId,c,{id:c.testId,revision:c.expectedRevision+1,lifecycle:c.action==='archive'?'archived':c.action==='delete'?'deleted':'active'});
    }
    default:reject('invalid_request');
  }
}
