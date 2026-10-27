// SPDX-License-Identifier: MIT
/** content/repository.py local transaction functions; no files, engines or DB construction. */
import type { DatabaseSync } from 'node:sqlite';
import type { ContentCommand, ContentPackPlan } from '../domain/content/contracts.ts';
import type { ObjectValue, QuestionSnapshot } from '../domain/assessment/contracts.ts';
import { exact, integer, reject, text } from './contracts.ts';
import { id, list } from '../domain/assessment/validation.ts';
import { canonical, digest, one, rows } from './schema.ts';
import { requireAssistance } from './conversation.ts';
import { utcNow } from './export.ts';
const types=new Set(['content.active','content.topics','content.sources','content.topic','content.case','content.install','content.withdraw','content.pack.withdraw']);
export const isContentCommand=(v:unknown):v is ContentCommand=>!!v&&typeof v==='object'&&'type'in v&&types.has(String(v.type));
export function validateContentCommand(c:ContentCommand) {
  switch(c.type){
    case 'content.active':case 'content.topics':case 'content.sources':exact(c,['type']);break;
    case 'content.topic':exact(c,['type','topicId']);id(c.topicId);break;
    case 'content.case':exact(c,['type','caseId','version']);id(c.caseId);if(c.version!==null)integer(c.version,1);break;
    case 'content.withdraw':exact(c,['type','questionId','version','reason','replacementVersion']);id(c.questionId);integer(c.version,1);text(c.reason,1,2000);if(!c.reason.trim())reject('invalid_request');if(c.replacementVersion!==null)integer(c.replacementVersion,c.version+1);break;
    case 'content.pack.withdraw':exact(c,['type','packId','version','reason']);id(c.packId);text(c.version,1,80);text(c.reason,1,2000);if(!c.reason.trim())reject('invalid_request');break;
    case 'content.install': {
      exact(c,['type','plan']);exact(c.plan,['manifest','bundle','sha256']);exact(c.plan.bundle,['topics','cases','questions','sources']);
      if(!/^[a-f0-9]{64}$/.test(c.plan.sha256))reject('invalid_request');id(c.plan.manifest.id);text(c.plan.manifest.version,1,80);
      for(const v of Object.values(c.plan.bundle))list(v,0,5000);break;
    }
    default:reject('invalid_request');
  }
}
export function activeContent(db:DatabaseSync,name:'topics'|'cases'|'questions'):ObjectValue[] {
  const [table,key,pin]=name==='topics'?['content_topics','topic_id','topic_version']:name==='cases'?['content_case_versions','case_id','case_version']:['content_question_versions','question_id','question_version'];
  return rows(db,`SELECT v.body_json FROM content_active_pack a JOIN content_pack_${name} p ON p.pack_id=a.pack_id AND p.pack_version=a.pack_version JOIN ${table} v ON v.${key}=p.${key} AND v.version=p.${pin} WHERE a.slot=1 `+
    (name==='questions'?'AND NOT EXISTS(SELECT 1 FROM content_question_withdrawals w WHERE w.question_id=v.question_id AND w.version=v.version) ':'')+`ORDER BY v.${key}`).map(r=>JSON.parse(String(r.body_json)));
}
export const reviewedQuestion=(q:ObjectValue)=>q.usage==='assessment_reserved'&&q.kind==='single_best_answer'&&['assistant_reviewed','human_reviewed'].includes(q.review?.status)&&q.review?.source_key_checked===true&&q.sources?.length>0&&!!q.rationale;
export function pinnedQuestion(db:DatabaseSync,questionId:string,version:number):ObjectValue|null {
  const row=one(db,'SELECT body_json FROM content_question_versions WHERE question_id=? AND version=?',questionId,version);
  return row?JSON.parse(String(row.body_json)):null;
}
export function questionAvailability(db:DatabaseSync,q:QuestionSnapshot):string {
  const current=one(db,'SELECT p.question_version FROM content_pack_questions p JOIN content_active_pack a ON a.pack_id=p.pack_id AND a.pack_version=p.pack_version WHERE p.question_id=?',q.question_id);
  if(one(db,'SELECT 1 FROM content_question_withdrawals WHERE question_id=? AND version=?',q.question_id,Number(q.question_version)))return 'withdrawn';
  const body=pinnedQuestion(db,q.question_id,Number(q.question_version));
  if(!body||!current||!reviewedQuestion(body))return 'unavailable';
  if(String(current.question_version)!==q.question_version||String(body.key_version)!==q.key_version||String(body.family_version)!==q.family_version||canonical([body.answer])!==canonical(q.correct_option_ids))return 'corrected';
  if(one(db,"SELECT 1 FROM update_affected_versions WHERE kind='question' AND entity_id=? AND version=? AND state='needs-re-review'",q.question_id,Number(q.question_version)))return 'source_needs_review';
  return 'current';
}
function withdraw(db:DatabaseSync,q:string,v:number,reason:string,replacement:number|null) {
  const old=one(db,'SELECT reason,replacement_version FROM content_question_withdrawals WHERE question_id=? AND version=?',q,v);
  if(old){if(old.reason!==reason||old.replacement_version!==replacement)reject('content_conflict');return;}
  if(!pinnedQuestion(db,q,v))reject('not_found');
  if(replacement!==null&&(!pinnedQuestion(db,q,replacement)||one(db,'SELECT 1 FROM content_question_withdrawals WHERE question_id=? AND version=?',q,replacement)))reject('content_conflict');
  db.prepare('INSERT INTO content_question_withdrawals VALUES(?,?,?,?,?)').run(q,v,reason,utcNow(),replacement);
}
function install(db:DatabaseSync,plan:ContentPackPlan) {
  const m=plan.manifest,old=one(db,'SELECT sha256 FROM content_packs WHERE pack_id=? AND version=?',m.id,m.version);
  if(m.state!=='published')reject('content_not_published');
  if(old&&old.sha256!==plan.sha256)reject('content_conflict');
  if(one(db,'SELECT 1 FROM content_pack_withdrawals WHERE pack_id=? AND version=?',m.id,m.version))reject('content_withdrawn');
  if(!old){
    db.prepare('INSERT INTO content_packs VALUES(?,?,?,?,?)').run(m.id,m.version,canonical(m),plan.sha256,utcNow());
    for(const name of ['topics','cases','questions'] as const){
      const [table,key,pin]=name==='topics'?['content_topics','topic_id','topic_version']:name==='cases'?['content_case_versions','case_id','case_version']:['content_question_versions','question_id','question_version'];
      for(const original of plan.bundle[name]){
        const cited=new Set((original.sources??[]).map((s:ObjectValue)=>s.source_id));
        for(const s of original.stages??[])for(const ref of s.sources??[])cited.add(ref.source_id);
        const item=name==='topics'?original:{...original,source_records:plan.bundle.sources.filter(s=>cited.has(s.id))};
        const hash=digest(canonical(item));const prior=one(db,`SELECT sha256 FROM ${table} WHERE ${key}=? AND version=?`,item.id,item.version);
        if(prior&&prior.sha256!==hash)reject('content_conflict');
        if(!prior){
          if(name==='questions'){
            const prev=one(db,'SELECT * FROM content_question_versions WHERE question_id=? ORDER BY version DESC LIMIT 1',item.id);
            if(prev){const p=JSON.parse(String(prev.body_json));if(prev.family_id!==item.family_id||Number(prev.version)>=item.version)reject('content_conflict');if((canonical(p.options)!==canonical(item.options)||p.answer!==item.answer)&&!item.correction)reject('content_correction_required');}
            if(item.correction&&(!pinnedQuestion(db,item.id,item.correction.previous_version)||!(m.withdrawals??[]).some((w:ObjectValue)=>w.question_id===item.id&&w.version===item.correction.previous_version&&w.replacement_version===item.version)))reject('content_correction_required');
            db.prepare(`INSERT INTO ${table} VALUES(?,?,?,?,?)`).run(item.id,item.version,item.family_id,canonical(item),hash);
          }else db.prepare(`INSERT INTO ${table} VALUES(?,?,?,?)`).run(item.id,item.version,canonical(item),hash);
        }
        db.prepare(`INSERT INTO content_pack_${name} VALUES(?,?,?,?)`).run(m.id,m.version,item.id,item.version);
      }
    }
    for(const w of m.withdrawals??[])withdraw(db,w.question_id,w.version,w.reason,w.replacement_version??null);
  }
  if(one(db,'SELECT 1 FROM content_pack_questions p JOIN content_question_withdrawals w ON w.question_id=p.question_id AND w.version=p.question_version WHERE p.pack_id=? AND p.pack_version=?',m.id,m.version))reject('content_withdrawn');
  db.prepare('INSERT INTO content_active_pack VALUES(1,?,?) ON CONFLICT(slot) DO UPDATE SET pack_id=excluded.pack_id,pack_version=excluded.pack_version').run(m.id,m.version);
  return {id:m.id,version:m.version,sha256:plan.sha256,installed:!old,active:true,questions:plan.bundle.questions.length,cases:plan.bundle.cases.length};
}
/** Permanent pack withdrawal; the active pointer is cleared only when it names this pack. */
function withdrawPack(db:DatabaseSync,id:string,version:string,reason:string) {
  if(!one(db,'SELECT 1 FROM content_packs WHERE pack_id=? AND version=?',id,version))reject('not_found');
  const old=one(db,'SELECT reason FROM content_pack_withdrawals WHERE pack_id=? AND version=?',id,version);
  if(old&&old.reason!==reason)reject('content_conflict');
  if(!old)db.prepare('INSERT INTO content_pack_withdrawals VALUES(?,?,?,?)').run(id,version,reason,utcNow());
  db.prepare('DELETE FROM content_active_pack WHERE pack_id=? AND pack_version=?').run(id,version);
}
export function executeContent(db:DatabaseSync,c:ContentCommand):ObjectValue {
  validateContentCommand(c);requireAssistance(db);
  switch(c.type){
    case 'content.install':return install(db,c.plan);
    case 'content.active': {const r=one(db,'SELECT manifest_json FROM content_packs p JOIN content_active_pack a ON a.pack_id=p.pack_id AND a.pack_version=p.version WHERE a.slot=1');return {manifest:r?JSON.parse(String(r.manifest_json)):null};}
    case 'content.topics':return {items:activeContent(db,'topics').map(t=>({...t,title:t.label,name:t.label}))};
    case 'content.topic': {const t=activeContent(db,'topics').find(t=>t.id===c.topicId);if(!t)reject('not_found');return {...t,title:t.label,name:t.label};}
    case 'content.case': {const r=c.version===null?activeContent(db,'cases').find(v=>v.id===c.caseId):one(db,'SELECT body_json FROM content_case_versions WHERE case_id=? AND version=?',c.caseId,c.version);if(!r)reject('not_found');return 'body_json'in r?JSON.parse(String(r.body_json)):r;}
    case 'content.sources': {const sources=new Map();for(const item of [...activeContent(db,'cases'),...activeContent(db,'questions')])for(const s of item.source_records??[])sources.set(s.id,s);return {items:[...sources.values()].sort((a,b)=>a.id.localeCompare(b.id))};}
    case 'content.pack.withdraw':withdrawPack(db,c.packId,c.version,c.reason);return {id:c.packId,version:c.version,withdrawn:true,reason:c.reason};
    case 'content.withdraw':withdraw(db,c.questionId,c.version,c.reason,c.replacementVersion);return {question_id:c.questionId,version:c.version,withdrawn:true};
  }
}
