// SPDX-License-Identifier: MIT
/** WholeAttemptRepository port. Pure local SQLite work in the integration-owned transaction. */
import type { DatabaseSync } from 'node:sqlite';
import type { AssessmentCommand,DraftState,HelpContext,ObjectValue,QuestionSnapshot,TestVersion } from './contracts.ts';
import { canonical,one,rows } from '../../storage/schema.ts';
import { reject } from '../../storage/contracts.ts';
import { questionAvailability,pinnedQuestion } from '../../storage/content.ts';
import { fictionalReceipt } from './versions.ts';
import { allowed,assistance,bank,bumpPolicy,decode,deleted,pinned,policy,record,replay,stamp,test,uid } from './local.ts';
const observations=new WeakMap<DatabaseSync,Map<string,{wall:number;tick:number}>>();
const terminal=(r:ObjectValue)=>['submitted','ended'].includes(r.status);
function row(db:DatabaseSync,id:string):ObjectValue {const r=one(db,'SELECT * FROM assessment_test_attempts WHERE id=?',id);if(!r||deleted(db,'test_attempt',id))reject('not_found');return r;}
function version(r:ObjectValue):TestVersion {const s=decode(r.version_snapshot_json);return s.schema==='whole-attempt-snapshot/1'?s.version:s;}
function draft(db:DatabaseSync,r:ObjectValue):ObjectValue {const d=one(db,'SELECT * FROM assessment_attempt_drafts WHERE attempt_id=?',r.id);if(!d)reject('invalid_attempt_snapshot');return d;}
function availability(db:DatabaseSync,r:ObjectValue,q:QuestionSnapshot) {
  if(!r.live_version_id||!one(db,"SELECT 1 FROM assessment_test_versions v JOIN assessment_tests t ON t.id=v.test_id WHERE v.id=? AND t.lifecycle!='deleted'",r.live_version_id))return 'unavailable';
  return bank(version(r))?questionAvailability(db,q):'current';
}
function repeat(db:DatabaseSync,r:ObjectValue,q:QuestionSnapshot):boolean {
  const fixed=one(db,"SELECT result_json FROM assessment_attempt_commands WHERE operation='presentation' AND target_id=? AND json_extract(result_json,'$.item_id')=? LIMIT 1",r.id,q.item_id);
  if(fixed)return decode(fixed.result_json).repeat;
  return !!one(db,'SELECT 1 FROM assessment_attempt_exposure WHERE family_id=? AND attempt_id<>? LIMIT 1',q.family_id,r.id)||!!one(db,'SELECT 1 FROM assessment_exposure WHERE family_id=? LIMIT 1',q.family_id);
}
function expose(db:DatabaseSync,r:ObjectValue,q:QuestionSnapshot,kind:string,now:string) {
  const repeated=repeat(db,r,q),id=uid('exposure');
  const result=db.prepare('INSERT OR IGNORE INTO assessment_attempt_exposure VALUES(?,?,?,?,?,?,?,?,?,?)').run(id,r.id,q.item_id,q.question_id,q.question_version,q.key_version,q.family_id,q.family_version,kind,now);
  if(result.changes&&kind==='presented')record(db,'assessment_attempt_commands','presentation:'+id,'presentation','test_attempt',r.id,{item_id:q.item_id},{item_id:q.item_id,repeat:repeated});
  return repeated;
}
function safeQuestion(q:QuestionSnapshot) {const {correct_option_ids:_key,explanation:_explanation,key_version:_kv,...safe}=q;return safe;}
function view(db:DatabaseSync,r:ObjectValue):ObjectValue {
  const p=allowed(db,r.id),v=version(r),d=draft(db,r),q=v.items[Number(d.position)];
  const shown=!!one(db,"SELECT 1 FROM assessment_attempt_exposure WHERE attempt_id=? AND item_id=? AND kind='presented'",r.id,q.item_id);
  return {id:r.id,version_id:r.version_id,origin:v.origin,review_quality:v.review_quality,mode:r.mode,status:r.status,item_count:v.items.length,
    provenance_unavailable:!r.live_version_id,draft_revision:r.draft_revision,position:d.position,answers:decode(d.answers_json),
    current_item:r.status==='active'&&shown?{...safeQuestion(q),repeat:repeat(db,r,q),availability:availability(db,r,q)}:null,
    committed:r.mode==='test'&&!terminal(r)?[]:decode(r.committed_json),result:r.result_json?decode(r.result_json):null,
    timing:{kind:r.timing_kind,duration_seconds:r.duration_seconds,deadline_at:r.deadline_at,paused_seconds:r.paused_seconds,
      remaining_seconds:r.deadline_at?Math.max(0,Math.floor((Date.parse(r.deadline_at)-Date.parse(r.status==='paused'?r.paused_at:r.clock_high_water_at))/1000)):null},policy:p};
}
function requireActive(r:ObjectValue,revision:number) {if(r.status!=='active')reject('attempt_not_active');if(r.draft_revision!==revision)reject('revision_conflict');}
function save(db:DatabaseSync,r:ObjectValue,d:DraftState,revision:number) {
  requireActive(r,revision);const v=version(r),old=draft(db,r),by=new Map(d.answers.map(a=>[a.item_id,a]));
  if(d.position>=v.items.length||by.size!==v.items.length||v.items.some(q=>!by.has(q.item_id)))reject('invalid_request');
  for(const q of v.items){const a=by.get(q.item_id)!;if(a.option_ids.some(k=>!q.options.some(o=>o.id===k))||(bank(v)&&a.option_ids.length>1))reject('invalid_request');}
  const committed:ObjectValue[]=decode(r.committed_json);
  for(const e of committed)if(canonical([...by.get(e.item_id)!.option_ids].sort())!==canonical([...e.selected_option_ids].sort()))reject('answer_locked');
  if(r.mode==='study'&&d.position>old.position&&!committed.some(e=>e.item_id===v.items[Number(old.position)].item_id))reject('answer_required');
  db.prepare('UPDATE assessment_attempt_drafts SET revision=?,position=?,answers_json=?,updated_at=? WHERE attempt_id=?').run(revision+1,d.position,canonical(d.answers),r.clock_high_water_at,r.id);
  db.prepare('UPDATE assessment_test_attempts SET draft_revision=?,updated_at=? WHERE id=?').run(revision+1,r.clock_high_water_at,r.id);r.draft_revision=revision+1;
}
function commit(db:DatabaseSync,r:ObjectValue,q:QuestionSnapshot,choices:string[],now:string):ObjectValue {
  const v=version(r),available=availability(db,r,q),excluded=available!=='current';
  const assisted=!!one(db,"SELECT 1 FROM assessment_attempt_exposure WHERE attempt_id=? AND item_id=? AND kind IN ('hint','sources','notes','chat')",r.id,q.item_id);
  const repeated=repeat(db,r,q),bucket=bank(v)?repeated?'repeat':assisted?'assisted':'fresh':'personal';
  const correct=!excluded&&choices.length>0&&canonical([...choices].sort())===canonical([...q.correct_option_ids].sort());
  const e:ObjectValue={commit_id:uid('answer_commit'),item_id:q.item_id,selected_option_ids:choices,question_id:q.question_id,question_version:q.question_version,key_version:q.key_version,family_id:q.family_id,family_version:q.family_version,
    committed_at:now,assisted,repeat:repeated,score_bucket:bucket,correct,outcome:excluded?'excluded':!choices.length?'unanswered':correct?'correct':'incorrect',exclusion_reason:excluded?available:null,
    feedback:{correct_option_ids:excluded?[]:q.correct_option_ids,explanation:excluded?'This pinned item was excluded because its content is no longer current.':q.explanation},question:safeQuestion(q),evidence_id:null};
  if(!excluded){
    e.evidence_id=uid('evidence');const payload:ObjectValue={};for(const k of ['commit_id','item_id','question_id','question_version','key_version','family_id','family_version','assisted','repeat','score_bucket','correct','outcome','committed_at'])payload[k]=e[k];
    Object.assign(payload,{attempt_id:r.id,version_id:v.id,origin:v.origin,review_quality:v.review_quality,mode:r.mode,reviewed:bank(v),bank_cohort_eligible:bank(v),topic_id:q.topic_id});
    db.prepare('INSERT INTO learning_evidence VALUES(?,?,?,?,?,?)').run(e.evidence_id,'assessment-test-answer',q.topic_id,r.id,canonical(payload),now);
  }
  expose(db,r,q,'answered',now);return e;
}
function finalise(db:DatabaseSync,r:ObjectValue,now:string,reason:string) {
  if(terminal(r))return;
  const v=version(r);let entries:ObjectValue[]=decode(r.committed_json);
  if(r.mode==='test'){const answers=new Map<string,string[]>(decode(draft(db,r).answers_json).map((a:ObjectValue)=>[a.item_id,a.option_ids]));entries=v.items.map(q=>commit(db,r,q,answers.get(q.item_id)??[],now));}
  const included=entries.filter(e=>e.outcome!=='excluded');const cohorts:ObjectValue={};for(const bucket of ['fresh','assisted','repeat','personal']){const es=included.filter(e=>e.score_bucket===bucket);cohorts[bucket]={denominator:es.length,answered:es.filter(e=>e.outcome!=='unanswered').length,unanswered:es.filter(e=>e.outcome==='unanswered').length,correct:es.filter(e=>e.correct).length};}
  const result={attempt_id:r.id,version_id:v.id,origin:v.origin,review_quality:v.review_quality,mode:r.mode,items:entries,correct:included.filter(e=>e.correct).length,denominator:included.length,excluded:entries.length-included.length,unanswered:included.filter(e=>e.outcome==='unanswered').length,not_submitted:v.items.length-entries.length,item_count:v.items.length,reason,finalized_at:now,draft_revision:r.draft_revision,cohorts};
  r.status=r.mode==='test'?'submitted':'ended';r.committed_json=canonical(entries);r.result_json=canonical(result);r.finalized_at=now;
  db.prepare('UPDATE assessment_test_attempts SET status=?,committed_json=?,result_json=?,finalized_at=?,updated_at=? WHERE id=?').run(r.status,r.committed_json,r.result_json,now,now,r.id);if(r.mode==='test')bumpPolicy(db);
}
/** Must be run and committed before global assistance reads/dispatch. No timers/scheduler. */
export function reconcileAssessments(db:DatabaseSync) {
  let clock=observations.get(db);if(!clock){clock=new Map();observations.set(db,clock);}
  for(const r of rows(db,"SELECT * FROM assessment_test_attempts WHERE status IN ('active','paused')") as ObjectValue[]){
    const wall=Date.now(),tick=performance.now(),high=Date.parse(r.clock_high_water_at),previous=clock.get(r.id);
    let effective=Math.max(wall,high,previous?previous.wall+Math.max(0,tick-previous.tick):0);
    if(!previous&&r.timing_kind==='timed'&&r.status==='active'&&wall<high-1000)effective=Math.max(effective,Date.parse(r.deadline_at));
    clock.set(r.id,{wall:effective,tick});r.clock_high_water_at=new Date(effective).toISOString();
    db.prepare('UPDATE assessment_test_attempts SET clock_high_water_at=? WHERE id=?').run(r.clock_high_water_at,r.id);
    if(r.status==='active'&&r.deadline_at&&effective>=Date.parse(r.deadline_at)){
      if(r.mode==='test')finalise(db,r,r.clock_high_water_at,'deadline');
      else db.prepare("UPDATE assessment_test_attempts SET status='timer_expired',updated_at=? WHERE id=?").run(r.clock_high_water_at,r.id);
    }
  }
}
export function requireHelpCurrent(db:DatabaseSync,c:HelpContext) {
  assistance(db,c.policy_revision);const r=row(db,c.attempt_id);requireActive(r,c.draft_revision);const v=version(r),q=v.items[Number(draft(db,r).position)];
  if(r.mode!=='study'||v.id!==c.version_id||q.item_id!==c.item_id||decode(r.committed_json).some((e:ObjectValue)=>e.item_id===c.item_id)||!one(db,'SELECT 1 FROM assessment_attempt_exposure WHERE attempt_id=? AND item_id=? AND kind=?',r.id,q.item_id,c.kind))reject('assistance_changed');
  return {policy_revision:policy(db).revision};
}
export function attemptCommand(db:DatabaseSync,c:AssessmentCommand):ObjectValue|null {
  if(c.type==='assessment.policy')return policy(db);
  if(c.type==='assessment.fictional.stamp'){assistance(db);return stamp(db);}
  if(c.type==='assessment.fictional.receipt'){assistance(db);return fictionalReceipt(db,c.idempotencyKey);}
  if(c.type==='assessment.help.current')return requireHelpCurrent(db,c.context);
  if(c.type==='assessment.attempts.list')return {items:rows(db,'SELECT id,version_id,mode,status,created_at,finalized_at FROM assessment_test_attempts ORDER BY created_at DESC,id LIMIT 100'),policy:policy(db)};
  if(c.type==='assessment.attempts.start'){
    const prior=one(db,'SELECT target_id FROM assessment_attempt_commands WHERE idempotency_key=?',c.idempotencyKey);allowed(db,prior?String(prior.target_id):undefined);
    const old=replay(db,'assessment_attempt_commands',c.idempotencyKey,c.type,'',c);if(old)return view(db,row(db,old.id));
    const v=pinned(db,c.versionId);if(v.status!=='ready'||test(db,v.test_id).lifecycle!=='active'||(bank(v)&&v.items.some(q=>questionAvailability(db,q)!=='current')))reject('test_not_ready');
    const now=new Date().toISOString(),id=uid('test_attempt'),deadline=c.timing.kind==='timed'?new Date(Date.parse(now)+c.timing.duration_seconds!*1000).toISOString():null;
    const provenance=decode(one(db,'SELECT provenance_json FROM assessment_test_versions WHERE id=?',v.id)!.provenance_json);
    db.prepare("INSERT INTO assessment_test_attempts(id,version_id,live_version_id,version_snapshot_json,mode,status,draft_revision,timing_kind,duration_seconds,started_at,deadline_at,paused_seconds,committed_json,result_json,clock_high_water_at,paused_at,created_at,updated_at,finalized_at) VALUES(?,?,?,?,?,'active',0,?,?,?,?,0,'[]',NULL,?,NULL,?,?,NULL)").run(id,v.id,v.id,canonical({schema:'whole-attempt-snapshot/1',version:v,pinned_provenance:provenance}),c.mode,c.timing.kind,c.timing.duration_seconds,deadline?now:null,deadline,now,now,now);
    db.prepare('INSERT INTO assessment_attempt_drafts VALUES(?,0,0,?,?)').run(id,canonical(v.items.map(q=>({item_id:q.item_id,option_ids:[],marked:false}))),now);
    if(c.mode==='test')bumpPolicy(db);const r=row(db,id);expose(db,r,v.items[0],'presented',now);
    return record(db,'assessment_attempt_commands',c.idempotencyKey,c.type,'test_attempt',id,c,view(db,r));
  }
  if(!('attemptId'in c))reject('invalid_request');
  let r=row(db,c.attemptId);allowed(db,r.id);
  if(c.type==='assessment.attempts.get')return view(db,r);
  if(c.type==='assessment.narrative.input'){
    assistance(db);if(!terminal(r)||!r.result_json)reject('result_not_committed');const result=decode(r.result_json);
    return {attempt_id:r.id,result_revision:r.finalized_at,summary:{correct:result.correct,denominator:result.denominator,excluded:result.excluded,unanswered:result.unanswered,origin:result.origin,review_quality:result.review_quality,cohorts:result.cohorts},policy_revision:policy(db).revision};
  }
  if(!('idempotencyKey'in c))reject('invalid_request');
  const prior=replay(db,'assessment_attempt_commands',c.idempotencyKey,c.type,r.id,c);
  if(prior){if(c.type==='assessment.attempts.help')requireHelpCurrent(db,prior.context);return prior;}
  // A late draft cannot prevent committed deadline reconciliation or alter its grade.
  if(terminal(r)&&['assessment.attempts.draft','assessment.attempts.submit'].includes(c.type))return record(db,'assessment_attempt_commands',c.idempotencyKey,c.type,'test_attempt',r.id,c,view(db,r));
  const v=version(r),d=draft(db,r),q=v.items[Number(d.position)];
  switch(c.type){
    case 'assessment.attempts.draft':save(db,r,c.draft,c.expectedRevision);break;
    case 'assessment.attempts.present':requireActive(r,c.expectedRevision);if(q.item_id!==c.itemId)reject('revision_conflict');expose(db,r,q,'presented',r.clock_high_water_at);break;
    case 'assessment.attempts.answer': {
      requireActive(r,c.expectedRevision);if(r.mode!=='study'||q.item_id!==c.itemId)reject('attempt_restricted');if(decode(r.committed_json).some((e:ObjectValue)=>e.item_id===q.item_id))reject('answer_locked');
      const state:DraftState={position:Number(d.position),answers:decode(d.answers_json)};state.answers.find(a=>a.item_id===q.item_id)!.option_ids=c.optionIds;save(db,r,state,c.expectedRevision);
      const entries=decode(r.committed_json);entries.push(commit(db,r,q,c.optionIds,r.clock_high_water_at));r.committed_json=canonical(entries);db.prepare('UPDATE assessment_test_attempts SET committed_json=? WHERE id=?').run(r.committed_json,r.id);break;
    }
    case 'assessment.attempts.help': {
      assistance(db,c.expectedPolicyRevision);requireActive(r,c.expectedRevision);if(r.mode!=='study'||q.item_id!==c.itemId||decode(r.committed_json).some((e:ObjectValue)=>e.item_id===q.item_id))reject('attempt_restricted');
      let hint=null;if(c.kind==='hint'){const original=bank(v)&&availability(db,r,q)==='current'?pinnedQuestion(db,q.question_id,Number(q.question_version)):null;hint=typeof original?.hint==='string'?original.hint:null;if(!hint)reject('hint_unavailable');}
      expose(db,r,q,c.kind,r.clock_high_water_at);const context:HelpContext={attempt_id:r.id,item_id:q.item_id,version_id:v.id,draft_revision:r.draft_revision,policy_revision:policy(db).revision,kind:c.kind};
      return record(db,'assessment_attempt_commands',c.idempotencyKey,c.type,'test_attempt',r.id,c,{hint,references:c.kind==='sources'?v.source_refs:[],context,assisted:true});
    }
    case 'assessment.attempts.submit':if(r.draft_revision!==c.expectedRevision)reject('saving_incomplete');if(c.latestDraft)save(db,r,c.latestDraft,c.expectedRevision);finalise(db,r,r.clock_high_water_at,'manual');break;
    case 'assessment.attempts.transition': {
      if(r.mode==='test')reject('attempt_restricted');if(r.draft_revision!==c.expectedRevision)reject('revision_conflict');const now=r.clock_high_water_at;
      if(c.action==='pause'&&r.status==='active')db.prepare("UPDATE assessment_test_attempts SET status='paused',paused_at=?,updated_at=? WHERE id=?").run(now,now,r.id);
      else if(c.action==='resume'&&r.status==='paused'){const delta=Date.parse(now)-Date.parse(r.paused_at);db.prepare("UPDATE assessment_test_attempts SET status='active',paused_at=NULL,paused_seconds=paused_seconds+?,deadline_at=?,updated_at=? WHERE id=?").run(Math.floor(delta/1000),r.deadline_at?new Date(Date.parse(r.deadline_at)+delta).toISOString():null,now,r.id);}
      else if(c.action==='continue-untimed'&&r.status==='timer_expired')db.prepare("UPDATE assessment_test_attempts SET status='active',timing_kind='untimed',duration_seconds=NULL,started_at=NULL,deadline_at=NULL,paused_at=NULL,updated_at=? WHERE id=?").run(now,r.id);
      else reject('invalid_transition');r=row(db,r.id);break;
    }
    case 'assessment.report': {
      const item=v.items.find(i=>i.item_id===c.itemId);if(!item)reject('not_found');const id=uid('question_report');
      db.prepare('INSERT INTO assessment_question_reports VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)').run(id,v.id,r.live_version_id,r.id,r.id,item.item_id,item.question_id,item.question_version,item.key_version,item.family_id,item.family_version,c.reportText,c.idempotencyKey,canonical(c),canonical({question:item,version_id:v.id}),r.clock_high_water_at);
      return record(db,'assessment_attempt_commands',c.idempotencyKey,c.type,'test_attempt',r.id,c,{id,item_id:item.item_id,status:'recorded'});
    }
    default:reject('invalid_request');
  }
  return record(db,'assessment_attempt_commands',c.idempotencyKey,c.type,'test_attempt',r.id,c,view(db,r));
}
