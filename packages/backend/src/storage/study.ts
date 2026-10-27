// SPDX-License-Identifier: MIT
// Local functions only. The single canonical worker owns the transaction.
import type { DatabaseSync } from 'node:sqlite';
import { randomUUID } from 'node:crypto';
import { exact, integer, reject, text } from './contracts.ts';
import { canonical, digest, one, rows } from './schema.ts';
import { requireAssistance } from './conversation.ts';
import { utcNow } from './export.ts';
import type { Activity, HomePreferences, LocalClock, NightlyPreferences, NightlySchedule, Plan, StudyCommand, StudyContext, StudyGoals, StudyResults, SuggestionBundle } from '../domain/study/contracts.ts';

const sha = (v: unknown) => digest(canonical(v));
const json = <T>(v: unknown): T => JSON.parse(String(v));
export function studyPreference<T>(db: DatabaseSync, key: string, fallback: T): T { const r = one(db, 'SELECT value FROM preferences WHERE key=?', key); try { return r ? json<T>(r.value) : fallback; } catch { return fallback; } }
export function saveStudyPreference(db: DatabaseSync, key: string, value: unknown) { db.prepare('INSERT INTO preferences VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at').run(key, JSON.stringify(value), utcNow()); }
export function bumpStudyContext(db: DatabaseSync) { saveStudyPreference(db, 'design_c.context_epoch', epoch(db) + 1); }
const epoch = (db: DatabaseSync) => Number(studyPreference(db, 'design_c.context_epoch', 0));
const policy = (db: DatabaseSync) => Number(studyPreference(db, 'design_c.assessment_policy_revision', 1));
const deleted = (db: DatabaseSync, type: string, id: string) => !!one(db, 'SELECT 1 FROM deletion_ledger WHERE entity_type=? AND entity_id=?', type, id);
const defaults: StudyGoals = { hours_per_week: 3, exam_date: null, topic_ids: [], track: 'general' };
function preferences(db: DatabaseSync): HomePreferences { const p = studyPreference(db, 'home.preferences', { doctor_name: null, revision: 1 }); return p && Number.isSafeInteger(p.revision) && p.revision > 0 && (p.doctor_name === null || typeof p.doctor_name === 'string') ? p : { doctor_name: null, revision: 1 }; }
function nightly(db: DatabaseSync): NightlyPreferences {
  const p = studyPreference<NightlyPreferences | null>(db, 'nightly.preferences', null);
  return p && typeof p.enabled === 'boolean' && /^[0-2][0-9]:[0-5][0-9]$/.test(p.local_time) && p.local_time < '24:00' && [5,10,20].includes(p.question_count) && Number.isSafeInteger(p.revision) && p.revision > 0 ? p : { enabled: false, local_time: '22:00', question_count: 5, revision: 1 };
}
function goals(db: DatabaseSync): StudyGoals { const v = studyPreference(db, 'study.goals', defaults); try { validateGoals(v); return v; } catch { return defaults; } }
function date(v: unknown) { text(v, 10, 10); if (!/^\d{4}-\d{2}-\d{2}$/.test(v) || new Date(v + 'T00:00:00Z').toISOString().slice(0,10) !== v) reject('storage_invalid_command'); }
function strings(v: unknown, maximum = 100) { if (!Array.isArray(v) || v.length > maximum) reject('storage_invalid_command'); for (const i of v) text(i, 1, 120); }
function validateGoals(v: StudyGoals) { exact(v, ['hours_per_week','exam_date','topic_ids','track']); integer(v.hours_per_week,1,40); if (v.exam_date !== null) date(v.exam_date); strings(v.topic_ids); if (!['general','eseneph'].includes(v.track)) reject('storage_invalid_command'); }
function clock(c: LocalClock) { exact(c, ['now','timezone']); text(c.now, 20, 40); text(c.timezone, 1, 100); if (!/(Z|[+-]\d\d:\d\d)$/.test(c.now) || !Number.isFinite(Date.parse(c.now))) reject('storage_invalid_command'); try { new Intl.DateTimeFormat('en', { timeZone: c.timezone }).format(); } catch { reject('storage_invalid_command'); } }
export function localDay(c: LocalClock) { clock(c); const parts = new Intl.DateTimeFormat('en-CA', {timeZone:c.timezone,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(c.now)); return ['year','month','day'].map(k=>parts.find(p=>p.type===k)!.value).join('-'); }
function localMinute(c: LocalClock) { const p = new Intl.DateTimeFormat('en-GB',{ timeZone:c.timezone,hour:'2-digit',minute:'2-digit',hourCycle:'h23' }).formatToParts(new Date(c.now)); return p.find(p=>p.type==='hour')!.value+':'+p.find(p=>p.type==='minute')!.value; }
const addDay = (day: string, n: number) => new Date(Date.parse(day+'T12:00:00Z')+n*86400000).toISOString().slice(0,10);
function schedule(s: NightlySchedule) { exact(s, ['day','timezone','preferences_revision','home_settings_revision','eligibility_token','context_stamp']); date(s.day); text(s.timezone,1,100); integer(s.preferences_revision,1); integer(s.home_settings_revision,1); text(s.eligibility_token,1,128); hash(s.context_stamp); }
function hash(v: unknown) { if (typeof v !== 'string' || !/^[a-f0-9]{64}$/.test(v)) reject('storage_invalid_command'); }
function bundle(b: SuggestionBundle) {
  exact(b, ['explain','case','practice']); const all: string[]=[];
  for(const k of ['explain','case','practice'] as const) { if (!Array.isArray(b[k]) || b[k].length!==5) reject('invalid_suggestions'); for(const p of b[k]) { text(p,1,400); if (!p.trim() || /\p{C}/u.test(p)) reject('invalid_suggestions'); all.push(p.normalize('NFKC').toLowerCase().trim().replace(/\s+/g,' ')); } }
  if(new Set(all).size!==15) reject('invalid_suggestions');
}
export function isStudyCommand(v: unknown): v is StudyCommand { return !!v && typeof v==='object' && 'type' in v && typeof v.type==='string' && v.type.startsWith('study.'); }
export function validateStudyCommand(c: StudyCommand): void {
  switch(c.type) {
    case 'study.preferences.read': case 'study.goals.read': case 'study.context': case 'study.nightly.read': exact(c,['type']); break;
    case 'study.home.read': case 'study.home.begin': case 'study.plan.read': case 'study.nightly.claim': case 'study.nightly.recover': exact(c,['type','clock']); clock(c.clock); break;
    case 'study.preferences.write': exact(c,['type','expectedRevision','doctorName','idempotencyKey']); integer(c.expectedRevision,1); if(c.doctorName!==null) { text(c.doctorName,0,80); if(/\p{C}/u.test(c.doctorName)) reject('storage_invalid_command'); } break;
    case 'study.goals.write': exact(c,['type','expectedRevision','goals','idempotencyKey']); integer(c.expectedRevision,1); validateGoals(c.goals); break;
    case 'study.plan.accept': exact(c,['type','clock','stamp','idempotencyKey']); clock(c.clock); hash(c.stamp); break;
    case 'study.activity.change': exact(c,['type','id','expectedRevision','dueDate','state','idempotencyKey']); text(c.id,1,128); hash(c.expectedRevision); if(c.dueDate!==null) date(c.dueDate); if(c.state!==null && !['planned','completed','skipped'].includes(c.state)) reject('storage_invalid_command'); break;
    case 'study.home.publish': exact(c,['type','jobId','bundle','clock']); text(c.jobId,1,128); bundle(c.bundle); clock(c.clock); break;
    case 'study.job.stop': exact(c,['type','jobId','state','errorCode']); text(c.jobId,1,128); if(!['failed','cancelled'].includes(c.state)) reject('storage_invalid_command'); text(c.errorCode,1,80); break;
    case 'study.nightly.preferences': exact(c,['type','clock','expectedRevision','enabled','localTime','count','idempotencyKey']); clock(c.clock); integer(c.expectedRevision,1); if(typeof c.enabled!=='boolean' || !/^(?:[01][0-9]|2[0-3]):[0-5][0-9]$/.test(c.localTime) || ![5,10,20].includes(c.count)) reject('storage_invalid_command'); break;
    case 'study.nightly.attach': exact(c,['type','schedule','jobId']); schedule(c.schedule); text(c.jobId,1,128); break;
    case 'study.nightly.guard': exact(c,['type','schedule']); schedule(c.schedule); break;
    default: reject('storage_invalid_command');
  }
  if ('idempotencyKey' in c) text(c.idempotencyKey,8,128);
}
/** Scalar projections only: no transcripts, case records, questions or answer keys. */
export function studyContext(db: DatabaseSync): StudyContext {
  requireAssistance(db);
  const inputs: StudyContext['inputs'] = [], learning: unknown[] = [];
  const pin = (kind: StudyContext['inputs'][number]['kind'], type: string, id: string, v: unknown, revision=sha(v)) => inputs.push({kind,dependency:{target:{type,id},expected_revision:revision}});
  for(const r of rows(db,"SELECT id,kind,topic_id,entity_id,payload_json FROM learning_evidence WHERE kind IN ('study-interest','assessment-answer') ORDER BY created_at DESC,id LIMIT 40")) {
    if(deleted(db,'learning_evidence',String(r.id)) || one(db,'SELECT 1 FROM memory_suppression WHERE source_key=?','evidence:'+r.id)) continue;
    const p=json<Record<string,any>>(r.payload_json); let item;
    if(r.kind==='study-interest') {
      if(p.scope?.kind!=='study' || p.scope.entity_id!==r.entity_id || p.activity!=='explain' || Object.keys(p).some(k=>!['scope','topic_id','activity'].includes(k)) || !one(db,'SELECT 1 FROM learn_threads WHERE id=?',String(r.entity_id)) || deleted(db,'learn_thread',String(r.entity_id))) continue;
      item={topic_id:r.topic_id,activity:'explain'};
    } else {
      if(p.scope?.kind!=='reviewed-assessment' || p.mode!=='reviewed' || typeof p.correct!=='boolean' || !['fresh','assisted','repeat'].includes(p.score_bucket) || !one(db,'SELECT 1 FROM assessment_attempts WHERE id=?',String(r.entity_id)) || deleted(db,'assessment_attempt',String(r.entity_id))) continue;
      item={topic_id:r.topic_id,correct:p.correct,bucket:p.score_bucket};
    }
    learning.push(item); pin('committed_evidence','learning_evidence',String(r.id),r);
  }
  const gs=goals(db), projectGoals=[];
  pin('preferences','preferences','study.goals',gs);
  for(const r of rows(db,"SELECT g.id,g.project_id,g.title,g.topic_id,g.target_date,g.revision FROM study_project_goals g JOIN study_projects p ON p.id=g.project_id WHERE p.lifecycle='active' AND g.status='active' ORDER BY g.updated_at DESC,g.id LIMIT 12")) {
    if(deleted(db,'project',String(r.project_id)) || deleted(db,'goal',String(r.id))) continue;
    pin('goal','goal',String(r.id),r,String(r.revision)); projectGoals.push({title:r.title,topic_id:r.topic_id,target_date:r.target_date});
  }
  const memory: unknown[]=[];
  if(studyPreference<boolean>(db,'memory.enabled',true)!==false) for(const r of rows(db,"SELECT f.id,f.text,f.topic_id,f.scope,f.revision,h.event FROM memory_facts f JOIN memory_history h ON h.record_id=f.id AND h.revision=f.revision AND h.text=f.text WHERE f.source_kind='manual' AND f.scope IN ('study','personal-library','generated-practice','reviewed-assessment') AND ((f.revision=1 AND h.event='added') OR (f.revision>1 AND h.event='edited')) ORDER BY f.updated_at DESC,f.id LIMIT 4")) {
    if(deleted(db,'memory_fact',String(r.id)) || typeof r.text!=='string' || r.text.length>1000) continue;
    memory.push({text:r.text,topic_id:r.topic_id,scope:r.scope,authority:r.event==='edited'?'personal-correction':'manual'}); pin('memory','memory_revision',r.id+':'+r.revision,r,String(r.revision));
  }
  const material={learning_activity:learning,goals:projectGoals,preferences:gs,memory};
  const settingsRevision=parseInt(sha({preferences:preferences(db),study:gs,memory_enabled:studyPreference(db,'memory.enabled',true)}).slice(0,12),16)+1;
  const value={epoch:epoch(db),policyRevision:policy(db),settingsRevision,inputs,material}; return {...value,stamp:sha(value)};
}
function receipt<T>(db: DatabaseSync, c: StudyCommand & {idempotencyKey:string}, request: unknown, mutate:()=>T): T {
  const receipts=studyPreference<any[]>(db,'study.command_receipts',[]), h=sha({type:c.type,request});
  const old=receipts.find(r=>r.key===c.idempotencyKey); if(old) { if(old.hash!==h) reject('idempotency_conflict'); return old.result; }
  const result=mutate(); saveStudyPreference(db,'study.command_receipts',[...receipts.slice(-127),{key:c.idempotencyKey,hash:h,result}]); return result;
}
function activity(r: any): Activity { const {reason_json,manual_override,...rest}=r; return {...rest,reason:json(reason_json),manual_override:!!manual_override,revision:sha(r)}; }
function plan(db: DatabaseSync,c: LocalClock): Plan {
  const context=studyContext(db), gs=goals(db), today=localDay(c);
  const topics=rows(db,"SELECT t.topic_id AS id,json_extract(t.body_json,'$.title') AS title FROM content_topics t JOIN content_pack_topics p ON p.topic_id=t.topic_id AND p.topic_version=t.version JOIN content_active_pack a ON a.pack_id=p.pack_id AND a.pack_version=p.pack_version WHERE a.slot=1 ORDER BY t.topic_id");
  // ESENeph proposals must be supplied by its mapped-content owner. Never infer alignment.
  const selected=gs.track==='general'?topics.filter(r=>!gs.topic_ids.length || gs.topic_ids.includes(String(r.id))):[];
  const proposal=selected.slice(0,Math.min(14,Math.max(1,Math.round(gs.hours_per_week*3)))).map((r,i)=>({id:'study_'+sha({week:today,topic:r.id}).slice(0,24),topic_id:String(r.id),objective_id:null,kind:'topic-study',title:'Study '+r.title,due_date:addDay(today,Math.min(6,i)),duration_minutes:20,reason:{kind:'coverage',track:'general_nephrology',description:'Explore your selected topics.'},evidence_id:null,state:'planned' as const,manual_override:false,revision:''}));
  const activities=rows(db,'SELECT * FROM study_activities ORDER BY due_date,created_at,id').map(activity);
  return {activities,proposal,stamp:sha({context:context.stamp,today,proposal,activities}),goals:gs};
}
interface State { context_epoch:number; preferences_revision:number; eligibility_token:string; timezone:string; not_before_day:string; last_claimed_day:string|null; last_key:string|null; latest_job_id:string|null; error_code:string|null; context_stamp:string|null }
function reset(db: DatabaseSync,c:LocalClock,p:NightlyPreferences) {
  const old=studyPreference<State|null>(db,'nightly.state',null), row=one(db,"SELECT MAX(json_extract(checkpoint_json,'$.nightly.day')) AS day FROM assessment_test_jobs WHERE operation='nightly_test'");
  const last=[old?.last_claimed_day,row?.day].filter((v):v is string=>typeof v==='string').sort().at(-1)??null;
  const s:State={context_epoch:epoch(db),preferences_revision:p.revision,eligibility_token:'nightly_'+randomUUID().replaceAll('-',''),timezone:c.timezone,not_before_day:addDay(localDay(c),localMinute(c)>=p.local_time?1:0),last_claimed_day:last,last_key:old?.last_key??null,latest_job_id:old?.latest_job_id??null,error_code:null,context_stamp:null};
  saveStudyPreference(db,'nightly.state',s); return s;
}
/** Assessment calls this in the SAME publication transaction, before inserting the saved set. */
export function requireNightlyPublication(db:DatabaseSync,s:NightlySchedule): void {
  schedule(s); requireAssistance(db); const p=nightly(db), state=studyPreference<State|null>(db,'nightly.state',null);
  if(!p.enabled || !state || p.revision!==s.preferences_revision || state.preferences_revision!==p.revision || state.eligibility_token!==s.eligibility_token || state.timezone!==s.timezone || state.last_key!=='nightly:'+s.day || state.context_epoch!==epoch(db) || state.context_stamp!==s.context_stamp || studyContext(db).stamp!==s.context_stamp) reject('nightly_invalidated');
  const job=one(db,"SELECT state FROM assessment_test_jobs WHERE operation='nightly_test' AND idempotency_key=?",state.last_key);
  if(job && ['failed','cancelled'].includes(String(job.state))) reject('nightly_invalidated');
}
function home(db:DatabaseSync,c:LocalClock): StudyResults['study.home.read'] {
  let current:StudyContext|null=null,error:string|null=null; try { current=studyContext(db); } catch(e) { error=(e as any).code??'context_unavailable'; }
  const cache=studyPreference<any>(db,'home.suggestions',null), valid=!!cache && current?.stamp===cache.context_stamp;
  return {preferences:preferences(db),suggestions:valid?cache.bundle:null,suggestions_date:valid?cache.day:null,stale:valid && cache.day!==localDay(c),job:one(db,"SELECT id,state,error_code FROM assessment_test_jobs WHERE operation='daily_suggestions' ORDER BY created_at DESC,id DESC LIMIT 1")??null,assistance_allowed:!error,error_code:error};
}
export function executeStudy<C extends StudyCommand>(db:DatabaseSync,c:C): StudyResults[C['type']] {
  validateStudyCommand(c); let result:unknown;
  switch(c.type) {
    case 'study.preferences.read': result=preferences(db); break;
    case 'study.preferences.write': result=receipt(db,c,{expected_revision:c.expectedRevision,doctor_name:c.doctorName},()=>{ const p=preferences(db); if(p.revision!==c.expectedRevision) reject('revision_conflict'); const v={doctor_name:c.doctorName?.normalize('NFC').trim()||null,revision:p.revision+1}; saveStudyPreference(db,'home.preferences',v); bumpStudyContext(db); return v; }); break;
    case 'study.goals.read': result={goals:goals(db),revision:studyPreference(db,'study.goals.revision',1)}; break;
    case 'study.goals.write': requireAssistance(db); result=receipt(db,c,{expectedRevision:c.expectedRevision,goals:c.goals},()=>{ const r=studyPreference(db,'study.goals.revision',1); if(r!==c.expectedRevision) reject('revision_conflict'); saveStudyPreference(db,'study.goals',c.goals); saveStudyPreference(db,'study.goals.revision',r+1); bumpStudyContext(db); return {goals:c.goals,revision:r+1}; }); break;
    case 'study.context': result=studyContext(db); break;
    case 'study.plan.read': result=plan(db,c.clock); break;
    case 'study.plan.accept': requireAssistance(db); result=receipt(db,c,{stamp:c.stamp},()=>{const p=plan(db,c.clock); if(p.stamp!==c.stamp) reject('dependency_changed'); for(const a of p.proposal) db.prepare('INSERT OR IGNORE INTO study_activities VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)').run(a.id,a.topic_id,a.objective_id,a.kind,a.title,a.due_date,a.duration_minutes,JSON.stringify(a.reason),a.evidence_id,a.state,0,utcNow(),utcNow()); return plan(db,c.clock);}); break;
    case 'study.activity.change': requireAssistance(db); result=receipt(db,c,{id:c.id,expectedRevision:c.expectedRevision,dueDate:c.dueDate,state:c.state},()=>{const r=one(db,'SELECT * FROM study_activities WHERE id=?',c.id); if(!r) reject('activity_missing'); if(sha(r)!==c.expectedRevision) reject('revision_conflict'); db.prepare('UPDATE study_activities SET due_date=?,state=?,manual_override=1,updated_at=? WHERE id=?').run(c.dueDate??r.due_date,c.state??r.state,utcNow(),c.id); if(c.state==='completed') db.prepare('INSERT OR IGNORE INTO learning_evidence VALUES(?,?,?,?,?,?)').run('study:'+c.id,'study-completion',r.topic_id,c.id,JSON.stringify({activity_id:c.id,completion:'learner-confirmed'}),utcNow()); bumpStudyContext(db); return activity(one(db,'SELECT * FROM study_activities WHERE id=?',c.id)); }); break;
    case 'study.home.read': result=home(db,c.clock); break;
    case 'study.home.begin': {
      const context=studyContext(db), day=localDay(c.clock), key='daily_'+sha({day,timezone:c.clock.timezone,stamp:context.stamp});
      let r=one(db,'SELECT * FROM assessment_test_jobs WHERE idempotency_key=?',key), fresh=false;
      if(!r) { r=one(db,"SELECT * FROM assessment_test_jobs WHERE operation='daily_suggestions' AND state IN ('queued','running') LIMIT 1"); if(r) reject('suggestions_busy'); const id='home_'+key.slice(6,38), at=utcNow(); db.prepare("INSERT INTO assessment_test_jobs(id,operation,state,idempotency_key,request_hash,inputs_json,checkpoint_json,settings_revision,policy_revision,context_epoch,created_at,updated_at) VALUES(?,'daily_suggestions','running',?,?,?,?,?,?,?,?,?)").run(id,key,sha(context.material),JSON.stringify(context.inputs),JSON.stringify({context_stamp:context.stamp,day,timezone:c.clock.timezone}),context.settingsRevision,context.policyRevision,context.epoch,at,at); r=one(db,'SELECT * FROM assessment_test_jobs WHERE id=?',id); fresh=true; }
      result={job_id:r!.id,fresh,context,day,timezone:c.clock.timezone}; break;
    }
    case 'study.home.publish': {
      const r=one(db,"SELECT * FROM assessment_test_jobs WHERE id=? AND operation='daily_suggestions'",c.jobId); if(!r) reject('job_missing'); const cp=json<any>(r.checkpoint_json), context=studyContext(db);
      if(context.stamp!==cp.context_stamp || cp.day!==localDay(c.clock) || cp.timezone!==c.clock.timezone) reject('dependency_changed');
      if(r.state==='published') { if(cp.bundle_digest!==sha(c.bundle)) reject('idempotency_conflict'); result=home(db,c.clock); break; }
      if(r.state!=='running') reject('cancelled'); saveStudyPreference(db,'home.suggestions',{day:cp.day,timezone:cp.timezone,bundle:c.bundle,job_id:c.jobId,context_epoch:context.epoch,settings_revision:context.settingsRevision,policy_revision:context.policyRevision,inputs:context.inputs,context_stamp:context.stamp});
      db.prepare("UPDATE assessment_test_jobs SET state='published',validated_count=15,checkpoint_json=?,updated_at=? WHERE id=?").run(JSON.stringify({...cp,bundle_digest:sha(c.bundle)}),utcNow(),c.jobId); result=home(db,c.clock); break;
    }
    case 'study.job.stop': db.prepare("UPDATE assessment_test_jobs SET state=?,error_code=?,updated_at=? WHERE id=? AND operation IN ('daily_suggestions','nightly_test') AND state IN ('queued','running','needs_review')").run(c.state,c.errorCode,utcNow(),c.jobId); result={stopped:true}; break;
    case 'study.nightly.read': { const p=nightly(db), s=studyPreference<State|null>(db,'nightly.state',null); const r=one(db,"SELECT id,state,requested_count,validated_count,error_code,published_version_id FROM assessment_test_jobs j WHERE operation='nightly_test' AND NOT EXISTS(SELECT 1 FROM deletion_ledger WHERE entity_type='job' AND entity_id=j.id) ORDER BY created_at DESC,id DESC LIMIT 1"); result={preferences:p,app_running_only:true,next_eligible_at:p.enabled&&s?s.not_before_day+'T'+p.local_time+'['+s.timezone+']':null,last_job:r??null,error_code:s?.error_code??null}; break; }
    case 'study.nightly.preferences': result=receipt(db,c,{expected_revision:c.expectedRevision,enabled:c.enabled,local_time:c.localTime,question_count:c.count},()=>{const p=nightly(db); if(p.revision!==c.expectedRevision) reject('revision_conflict'); const v={enabled:c.enabled,local_time:c.localTime,question_count:c.count,revision:p.revision+1}; saveStudyPreference(db,'nightly.preferences',v); reset(db,c.clock,v); db.prepare("UPDATE assessment_test_jobs SET state='cancelled',error_code='nightly_settings_changed',updated_at=? WHERE operation='nightly_test' AND state IN ('queued','running')").run(utcNow()); return v; }); break;
    case 'study.nightly.recover': reset(db,c.clock,nightly(db)); db.prepare("UPDATE assessment_test_jobs SET state='failed',error_code='interrupted',updated_at=? WHERE operation IN ('nightly_test','daily_suggestions') AND state IN ('queued','running')").run(utcNow()); result={recovered:true}; break;
    case 'study.nightly.claim': {
      const p=nightly(db); let s=studyPreference<State|null>(db,'nightly.state',null); result={request:null};
      if(!s || s.preferences_revision!==p.revision || s.context_epoch!==epoch(db) || s.timezone!==c.clock.timezone) { reset(db,c.clock,p); break; }
      if(!p.enabled) break; const today=localDay(c.clock), due=localMinute(c.clock)>=p.local_time?today:addDay(today,-1);
      if(due<s.not_before_day || (s.last_claimed_day && due<=s.last_claimed_day) || one(db,"SELECT 1 FROM assessment_test_jobs WHERE operation='nightly_test' AND state IN ('queued','running') LIMIT 1")) break;
      s={...s,last_claimed_day:due,last_key:'nightly:'+due,not_before_day:addDay(due,1),latest_job_id:null,error_code:null,context_stamp:null};
      try { const context=studyContext(db); s.context_stamp=context.stamp; result={request:{idempotency_key:s.last_key,title:'Nightly practice · '+due,count:p.question_count,inputs:context.inputs.slice(0,20),material:context.material,nightly:{day:due,timezone:c.clock.timezone,preferences_revision:p.revision,home_settings_revision:context.settingsRevision,eligibility_token:s.eligibility_token,context_stamp:context.stamp}}}; } catch(e) { s.error_code=(e as any).code??'context_unavailable'; }
      saveStudyPreference(db,'nightly.state',s); break;
    }
    case 'study.nightly.attach': { requireNightlyPublication(db,c.schedule); const s=studyPreference<State>(db,'nightly.state',null!); const r=one(db,"SELECT id,idempotency_key FROM assessment_test_jobs WHERE id=? AND operation='nightly_test'",c.jobId); if(!r || r.idempotency_key!==s.last_key) reject('nightly_invalid_job'); saveStudyPreference(db,'nightly.state',{...s,latest_job_id:c.jobId}); result={attached:true}; break; }
    case 'study.nightly.guard': requireNightlyPublication(db,c.schedule); result={current:true}; break;
  }
  return result as StudyResults[C['type']];
}
