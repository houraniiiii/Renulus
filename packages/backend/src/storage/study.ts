// SPDX-License-Identifier: MIT
// Local functions only. The single canonical worker owns the transaction.
import type { DatabaseSync } from 'node:sqlite';
import { createHash, randomUUID } from 'node:crypto';
import { exact, integer, reject, text } from './contracts.ts';
import { canonical, digest, one, rows } from './schema.ts';
import { requireAssistance } from './conversation.ts';
import { utcNow } from './export.ts';
import { activeContent } from './content.ts';
import { programmeMetadata } from '../domain/study/programmes.ts';
import type { ObjectValue } from '../domain/assessment/contracts.ts';
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
/** Local wall-clock day+time in a zone as an offset ISO string (the Python owner's aware datetime). */
function zonedIso(day: string, time: string, timezone: string) {
  const offset = (at: number) => { const name = new Intl.DateTimeFormat('en', { timeZone: timezone, timeZoneName: 'longOffset' }).formatToParts(new Date(at)).find(p => p.type === 'timeZoneName')!.value, m = /([+-])(\d\d):(\d\d)$/.exec(name); return m ? (m[1] === '-' ? -1 : 1) * (Number(m[2]) * 60 + Number(m[3])) : 0; };
  const wall = Date.parse(day + 'T' + time + ':00Z'), minutes = offset(wall - offset(wall) * 60000), sign = minutes < 0 ? '-' : '+', abs = Math.abs(minutes);
  return day + 'T' + time + ':00' + sign + String(Math.floor(abs / 60)).padStart(2, '0') + ':' + String(abs % 60).padStart(2, '0');
}
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
    case 'study.preferences.read': case 'study.goals.read': case 'study.context': case 'study.nightly.read': case 'study.plan.read': case 'study.progress': exact(c,['type']); break;
    case 'study.home.read': case 'study.home.begin': case 'study.plan.propose': case 'study.plan.preview': case 'study.nightly.claim': case 'study.nightly.recover': exact(c,['type','clock']); clock(c.clock); break;
    case 'study.preferences.write': exact(c,['type','expectedRevision','doctorName','idempotencyKey']); integer(c.expectedRevision,1); if(c.doctorName!==null) { text(c.doctorName,0,80); if(/\p{C}/u.test(c.doctorName)) reject('storage_invalid_command'); } break;
    case 'study.goals.write': exact(c,['type','expectedRevision','goals','idempotencyKey']); integer(c.expectedRevision,1); validateGoals(c.goals); break;
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
  for(const r of rows(db,"SELECT id,kind,topic_id,entity_id,payload_json FROM learning_evidence WHERE kind IN ('study-interest','assessment-answer','assessment-test-answer') ORDER BY created_at DESC,id LIMIT 40")) {
    if(deleted(db,'learning_evidence',String(r.id)) || one(db,'SELECT 1 FROM memory_suppression WHERE source_key=?','evidence:'+r.id)) continue;
    const p=json<Record<string,any>>(r.payload_json); let item, revision: string|undefined;
    if(typeof r.topic_id!=='string' || r.topic_id.length>120) continue;
    if(r.kind==='study-interest') {
      if(p.scope?.kind!=='study' || p.scope.entity_id!==r.entity_id || p.activity!=='explain' || Object.keys(p).some(k=>!['scope','topic_id','activity'].includes(k)) || !one(db,'SELECT 1 FROM learn_threads WHERE id=?',String(r.entity_id)) || deleted(db,'learn_thread',String(r.entity_id))) continue;
      item={topic_id:r.topic_id,activity:'explain'};
    } else if(r.kind==='assessment-test-answer') {
      // Scalar commitment fields only; never the item, options or key.
      const answer=testAnswer(db,r); if(!answer) continue;
      item=Object.fromEntries(WHOLE_LEARNING_FIELDS.map(k=>[k,answer.payload[k]])); revision=answer.revision;
    } else {
      if(p.scope?.kind!=='reviewed-assessment' || p.mode!=='reviewed' || typeof p.correct!=='boolean' || !['fresh','assisted','repeat'].includes(p.score_bucket) || !one(db,'SELECT 1 FROM assessment_attempts WHERE id=?',String(r.entity_id)) || deleted(db,'assessment_attempt',String(r.entity_id))) continue;
      item={topic_id:r.topic_id,correct:p.correct,bucket:p.score_bucket};
    }
    learning.push(item); pin('committed_evidence','learning_evidence',String(r.id),r,revision);
  }
  const gs=goals(db), projectGoals=[];
  pin('preferences','preferences','study.goals',gs);
  for(const r of rows(db,"SELECT g.id,g.project_id,g.title,g.topic_id,g.target_date,g.revision FROM study_project_goals g JOIN study_projects p ON p.id=g.project_id WHERE p.lifecycle='active' AND g.status='active' ORDER BY g.updated_at DESC,g.id LIMIT 12")) {
    if(deleted(db,'project',String(r.project_id)) || deleted(db,'goal',String(r.id))) continue;
    pin('goal','goal',String(r.id),r,String(r.revision)); projectGoals.push({title:r.title,topic_id:r.topic_id,target_date:r.target_date});
  }
  const memory: unknown[]=[];
  let budget=0;
  if(studyPreference<boolean>(db,'memory.enabled',true)!==false) for(const r of rows(db,"SELECT id,text,kind,topic_id,scope,revision,source_kind,source_id FROM memory_facts WHERE scope IN ('study','personal-library','generated-practice','reviewed-assessment') ORDER BY updated_at DESC,id LIMIT 12")) {
    const body=String(r.text);
    if(deleted(db,'memory_fact',String(r.id)) || !body.length || body.length>2000 || (r.topic_id!==null && (typeof r.topic_id!=='string' || r.topic_id.length>120))) continue;
    const history=one(db,'SELECT text,event FROM memory_history WHERE record_id=? AND revision=?',String(r.id),r.revision as number);
    if(!history || history.text!==r.text || !((r.revision===1 && history.event==='added') || (Number(r.revision)>1 && history.event==='edited')) || budget+body.length>4000) continue;
    const corrected=history.event==='edited', item:Record<string,unknown>={text:body,kind:corrected?'learning-point':r.kind,topic_id:r.topic_id,scope:r.scope,authority:corrected?'personal-correction':r.source_kind==='manual'?'manual':'captured'};
    let evidence: [Record<string,unknown>, string|undefined]|null=null;
    if(r.source_kind!=='manual') {
      // A captured fact stays eligible only while its live evidence source attests it.
      if(r.source_kind!=='learning-evidence') continue;
      const source=one(db,'SELECT id,kind,topic_id,entity_id,payload_json FROM learning_evidence WHERE id=?',String(r.source_id));
      if(!source || deleted(db,'learning_evidence',String(source.id)) || !one(db,'SELECT 1 FROM memory_sources WHERE record_id=? AND source_key=?',String(r.id),'evidence:'+source.id)) continue;
      let sourceRevision: string|undefined;
      if(source.kind==='assessment-test-answer') {
        const answer=testAnswer(db,source); if(!answer) continue;
        const generated=answer.payload.bank_cohort_eligible!==true;
        if(r.scope!==(generated?'generated-practice':'reviewed-assessment') || r.topic_id!==source.topic_id || r.kind!==(!generated && !answer.payload.correct?'mistake':'study-interest')) continue;
        item.assessment=Object.fromEntries(WHOLE_LEARNING_FIELDS.map(k=>[k,answer.payload[k]])); sourceRevision=answer.revision;
      } else {
        const payload=json<Record<string,any>>(source.payload_json), scope=payload.scope;
        if(!scope || typeof scope!=='object' || scope.kind!==r.scope || !['study-interest','study-answer','assessment-answer','learning-point'].includes(String(source.kind))) continue;
        if(['study-interest','study-answer'].includes(String(source.kind))) { if(!one(db,'SELECT 1 FROM learn_threads WHERE id=?',String(source.entity_id)) || deleted(db,'learn_thread',String(source.entity_id))) continue; }
        else if(source.kind==='assessment-answer') { if(payload.mode!=='reviewed' || !one(db,'SELECT 1 FROM assessment_attempts WHERE id=?',String(source.entity_id)) || deleted(db,'assessment_attempt',String(source.entity_id))) continue; }
        else if(payload.general_learning!==true) continue;
      }
      // An explicit edit owns only its current revision; superseded evidence stays suppressed.
      if(!corrected && one(db,'SELECT 1 FROM memory_suppression WHERE source_key=?','evidence:'+source.id)) continue;
      evidence=[source,sourceRevision];
    }
    if(evidence) pin('learning_summary','learning_evidence',String(evidence[0].id),evidence[0],evidence[1]);
    memory.push(item); pin('memory','memory_revision',r.id+':'+r.revision,r,String(r.revision)); budget+=body.length;
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
const WHOLE_LEARNING_FIELDS = ['topic_id','mode','origin','review_quality','reviewed','bank_cohort_eligible','assisted','repeat','score_bucket','outcome','correct'] as const;
/** Whole-attempt answer evidence, valid only while its attempt still holds that commit. Scalars only. */
function testAnswer(db: DatabaseSync, row: ObjectValue): { payload: ObjectValue; revision: string } | null {
  const p = json<ObjectValue>(row.payload_json);
  if (!['study','test'].includes(p.mode) || typeof p.origin !== 'string' || typeof p.reviewed !== 'boolean' || typeof p.bank_cohort_eligible !== 'boolean' || typeof p.correct !== 'boolean' || typeof p.assisted !== 'boolean' || typeof p.repeat !== 'boolean' ||
      !['fresh','assisted','repeat','personal'].includes(p.score_bucket) || typeof p.outcome !== 'string' || p.topic_id !== row.topic_id || typeof p.question_id !== 'string') return null;
  const attempt = one(db, 'SELECT committed_json FROM assessment_test_attempts WHERE id=?', String(row.entity_id));
  if (!attempt || deleted(db, 'assessment_attempt', String(row.entity_id))) return null;
  try { if (!json<ObjectValue[]>(attempt.committed_json).some(e => e.evidence_id === row.id)) return null; } catch { return null; }
  return { payload: p, revision: sha(row) };
}
/** Reviewed-bank evidence only: Test drafts, personal and generated versions never become progress. */
function reviewedEvidence(db: DatabaseSync) {
  requireAssistance(db);
  const result: { id: string; kind: string; topic_id: string; entity_id: string; payload: ObjectValue; revision: string; created_at: string }[] = [];
  for (const r of rows(db, "SELECT * FROM learning_evidence WHERE kind IN ('assessment-answer','assessment-test-answer') ORDER BY created_at DESC,rowid DESC LIMIT 2000")) {
    let payload: ObjectValue | undefined, revision = sha(r);
    if (r.kind === 'assessment-test-answer') { const a = testAnswer(db, r); if (!a || a.payload.bank_cohort_eligible !== true) continue; payload = a.payload; revision = a.revision; }
    else try { payload = json<ObjectValue>(r.payload_json); } catch { continue; }
    result.push({ id: String(r.id), kind: String(r.kind), topic_id: String(r.topic_id), entity_id: String(r.entity_id), payload: payload!, revision, created_at: String(r.created_at) });
  }
  return result;
}
const family = (e: { id: string; payload: ObjectValue }) => String(e.payload.family_id ?? e.payload.question_id ?? e.id);
const pinKey = (id: unknown, version: unknown) => id + '@' + version;
function topicRows(db: DatabaseSync): ObjectValue[] { return activeContent(db, 'topics').map(t => ({ ...t, title: t.title ?? t.label, name: t.label ?? t.title })); }
function tracks(db: DatabaseSync): ObjectValue[] {
  const manifest = one(db, 'SELECT manifest_json FROM content_packs p JOIN content_active_pack a ON a.pack_id=p.pack_id AND a.pack_version=p.version WHERE a.slot=1');
  return programmeMetadata(manifest ? json<ObjectValue>(manifest.manifest_json) : null, activeContent(db, 'topics'), activeContent(db, 'cases'), activeContent(db, 'questions'));
}
const TRACK_IDS = { general: 'general_nephrology', eseneph: 'esen_eph' } as const;
function mappedPins(track: ObjectValue) { return new Set((track.domains ?? []).flatMap((d: ObjectValue) => (d.alignments ?? []).flatMap((a: ObjectValue) => (a.questions ?? []).map((p: ObjectValue) => pinKey(p.id, p.version))))); }
function selection(gs: StudyGoals, topics: ObjectValue[], allTracks: ObjectValue[]) {
  const trackId = TRACK_IDS[gs.track], metadata = allTracks.find(t => t.id === trackId) ?? {};
  const requested = new Set(gs.topic_ids.length ? gs.topic_ids : topics.map(t => t.id));
  let selected = topics.filter(t => requested.has(t.id));
  const objectives: Record<string, string[]> = {};
  if (trackId === 'esen_eph') {
    // Only active exam-domain links count; curriculum-support links stay separate producer metadata.
    const aligned = new Set<string>(metadata.aligned_objective_ids ?? []);
    for (const topic of selected) { const linked = (topic.objectives ?? []).map((o: ObjectValue) => o.id).filter((id: string) => aligned.has(id)); if (linked.length) objectives[topic.id] = linked; }
    selected = selected.filter(t => objectives[t.id]);
  }
  let status = 'ready', message: string | null = null;
  if (trackId === 'esen_eph' && !metadata.available) { selected = []; for (const k of Object.keys(objectives)) delete objectives[k]; status = 'track-unavailable'; message = metadata.reason ?? 'No active ESENeph mapping is available.'; }
  else if (!topics.length) { status = 'waiting-content'; message = 'Install a topic pack to build your study plan.'; }
  else if (!selected.length) { status = 'waiting-topics'; message = 'No active topics match these preferences. Choose other topics or a different track.'; }
  return { track: trackId, title: metadata.title ?? trackId, status, message, topic_ids: selected.map(t => t.id), objective_ids: objectives, mapping_version: metadata.version ?? null };
}
type Selection = ReturnType<typeof selection>;
function listActivities(db: DatabaseSync, sel: Selection, allTracks: ObjectValue[]) {
  let list = rows(db, 'SELECT * FROM study_activities ORDER BY due_date,created_at,id').map(r => ({ ...activity(r), outside_selection: false }));
  if (list.some(a => a.reason.evidence_kind === 'assessment-test-answer')) {
    // A vanished source or later correct commitment removes only an automatic suggestion.
    const latest = new Map<string, ReturnType<typeof reviewedEvidence>[number]>();
    for (const e of reviewedEvidence(db)) if (!latest.has(family(e))) latest.set(family(e), e);
    const eligible = new Set([...latest.values()].filter(e => !e.payload.correct).map(e => e.id));
    list = list.filter(a => a.reason.evidence_kind !== 'assessment-test-answer' || a.manual_override || a.state !== 'planned' || eligible.has(String(a.evidence_id)));
  }
  const pins = mappedPins(allTracks.find(t => t.id === sel.track) ?? {}), visible = [];
  for (const a of list) {
    let matches = sel.topic_ids.includes(a.topic_id) && (a.reason.track ?? 'general_nephrology') === sel.track;
    if (sel.track === 'esen_eph') {
      matches = matches && a.reason.mapping_version === sel.mapping_version && (sel.objective_ids[a.topic_id] ?? []).includes(String(a.objective_id));
      if (a.kind === 'mistake-review') matches = matches && pins.has(pinKey(a.reason.question_id, a.reason.question_version));
    }
    if (matches || a.manual_override || a.state !== 'planned') visible.push({ ...a, outside_selection: !matches });
  }
  return visible;
}
function plan(db: DatabaseSync): Plan {
  requireAssistance(db);
  const allTracks = tracks(db), sel = selection(goals(db), topicRows(db), allTracks);
  return { activities: listActivities(db, sel, allTracks), selection: sel, tracks: allTracks };
}
const isoWeek = (day: string) => { const d = new Date(day + 'T00:00:00Z'), n = (d.getUTCDay() + 6) % 7; d.setUTCDate(d.getUTCDate() - n + 3); const year = d.getUTCFullYear(), first = new Date(Date.UTC(year, 0, 4)); return `${year}-${1 + Math.round(((d.getTime() - first.getTime()) / 86400000 - 3 + (first.getUTCDay() + 6) % 7) / 7)}`; };
/** Committed mistakes first, then selected-topic coverage. Pure: the caller decides whether to save. */
function proposals(db: DatabaseSync, today: string) {
  const gs = goals(db), topics = topicRows(db), evidence = reviewedEvidence(db), allTracks = tracks(db), sel = selection(gs, topics, allTracks);
  const names = new Map(topics.map(t => [t.id, t.title ?? t.id])), track = allTracks.find(t => t.id === sel.track) ?? {}, pins = mappedPins(track);
  const result = { sel, allTracks, items: [] as (Omit<Activity, 'revision' | 'state' | 'manual_override'> & { id: string })[] };
  if (!sel.topic_ids.length) return result;
  const available = Math.max(1, Math.min(14, Math.round(gs.hours_per_week * 60 / 20))), candidates: ObjectValue[] = [], seenFamilies = new Set<string>(), seenTopics = new Set<string>();
  for (const e of evidence) {
    if (!sel.topic_ids.includes(e.topic_id)) continue;
    const fam = family(e); if (seenFamilies.has(fam)) continue; seenFamilies.add(fam);
    // A later correct answer resolves an earlier mistake for scheduling, without rewriting it.
    if (e.payload.correct) continue;
    let objectiveId = e.payload.objective_id ?? null;
    if (sel.track === 'esen_eph') {
      const linked: string[] = sel.objective_ids[e.topic_id] ?? [];
      let objectives: string[] = e.payload.objective_ids ?? [objectiveId];
      if (e.kind === 'assessment-test-answer') objectives = (track.domains ?? []).flatMap((d: ObjectValue) => (d.alignments ?? []).filter((a: ObjectValue) => (a.questions ?? []).some((p: ObjectValue) => p.id === e.payload.question_id && String(p.version) === String(e.payload.question_version))).flatMap((a: ObjectValue) => a.objective_ids));
      objectiveId = objectives.find(o => linked.includes(o)) ?? null;
      if (!pins.has(pinKey(e.payload.question_id, e.payload.question_version)) || objectiveId === null) continue;
    }
    candidates.push({ topic_id: e.topic_id, objective_id: objectiveId, kind: 'mistake-review', title: 'Review ' + (names.get(e.topic_id) ?? e.topic_id), evidence_id: e.id,
      reason: { kind: 'committed-mistake', evidence_id: e.id, question_id: e.payload.question_id ?? null, question_version: e.payload.question_version ?? null,
        description: 'Your latest recorded answer in this question family was incorrect.',
        ...(e.kind === 'assessment-test-answer' ? { evidence_kind: e.kind, evidence_revision: e.revision, attempt_id: e.entity_id, mode: e.payload.mode, origin: e.payload.origin, assisted: e.payload.assisted, repeat: e.payload.repeat, score_bucket: e.payload.score_bucket } : {}) } });
    seenTopics.add(e.topic_id);
  }
  for (const topicId of sel.topic_ids) if (!seenTopics.has(topicId)) {
    const linked = sel.objective_ids[topicId] ?? [];
    candidates.push({ topic_id: topicId, objective_id: linked[0] ?? null, kind: 'topic-study', title: 'Study ' + (names.get(topicId) ?? topicId), evidence_id: null,
      reason: { kind: 'coverage', description: sel.track === 'esen_eph' ? 'Explore an objective linked to a partially mapped ESENeph exam domain.' : 'Explore an objective from your selected topics.' } });
  }
  candidates.slice(0, available).forEach((c, i) => {
    c.reason.track = sel.track;
    if (sel.track === 'esen_eph') Object.assign(c.reason, { mapping_version: sel.mapping_version, mapping_checked_on: track.checked_on ?? null });
    let identity = c.evidence_id ?? `${isoWeek(today)}:${c.topic_id}`;
    if (sel.track === 'esen_eph') identity = `esen_eph:${sel.mapping_version}:${identity}`;
    result.items.push({ id: 'study_' + createHash('sha256').update(identity).digest('hex').slice(0, 24), topic_id: c.topic_id, objective_id: c.objective_id, kind: c.kind,
      title: c.title, due_date: addDay(today, Math.min(6, Math.floor(i / Math.max(1, Math.floor(available / 7))))), duration_minutes: 20, reason: c.reason, evidence_id: c.evidence_id });
  });
  return result;
}
function progress(db: DatabaseSync) {
  const groups: Record<string, { answered: number; correct: number }> = { fresh: { answered: 0, correct: 0 }, assisted: { answered: 0, correct: 0 }, repeat: { answered: 0, correct: 0 } };
  const topics = new Map<string, { topic_id: string; answered: number; correct: number; fresh_answered: number; fresh_correct: number }>();
  for (const e of reviewedEvidence(db)) {
    const bucket = groups[e.payload.score_bucket] ? e.payload.score_bucket : e.payload.assisted ? 'assisted' : e.payload.repeat ? 'repeat' : 'fresh', correct = e.payload.correct ? 1 : 0;
    groups[bucket].answered++; groups[bucket].correct += correct;
    const t = topics.get(e.topic_id) ?? { topic_id: e.topic_id, answered: 0, correct: 0, fresh_answered: 0, fresh_correct: 0 }; topics.set(e.topic_id, t);
    t.answered++; t.correct += correct; if (bucket === 'fresh') { t.fresh_answered++; t.fresh_correct += correct; }
  }
  return { groups, topics: [...topics.values()], interpretation: 'Observed reviewed-question results. Conversations indicate interest, not mastery.' };
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
  let current:StudyContext|null=null,error:string|null=null; try { current=studyContext(db); } catch(e) { const code=(e as any).code??'context_unavailable'; error=code==='assistance_restricted'?'attempt_restricted':code; }
  const cache=studyPreference<any>(db,'home.suggestions',null), valid=!!cache && current?.stamp===cache.context_stamp;
  return {preferences:preferences(db),suggestions:valid?cache.bundle:null,suggestions_date:valid?cache.day:null,stale:valid && cache.day!==localDay(c),job:one(db,"SELECT id,state,error_code FROM assessment_test_jobs WHERE operation='daily_suggestions' ORDER BY created_at DESC,id DESC LIMIT 1")??null,assistance_allowed:error!=='attempt_restricted',error_code:error};
}
export function executeStudy<C extends StudyCommand>(db:DatabaseSync,c:C): StudyResults[C['type']] {
  validateStudyCommand(c); let result:unknown;
  switch(c.type) {
    case 'study.preferences.read': result=preferences(db); break;
    case 'study.preferences.write': result=receipt(db,c,{expected_revision:c.expectedRevision,doctor_name:c.doctorName},()=>{ const p=preferences(db); if(p.revision!==c.expectedRevision) reject('revision_conflict'); const v={doctor_name:c.doctorName?.normalize('NFC').trim()||null,revision:p.revision+1}; saveStudyPreference(db,'home.preferences',v); bumpStudyContext(db); return v; }); break;
    case 'study.goals.read': result={goals:goals(db),revision:studyPreference(db,'study.goals.revision',1)}; break;
    case 'study.goals.write': requireAssistance(db); result=receipt(db,c,{expectedRevision:c.expectedRevision,goals:c.goals},()=>{ const r=studyPreference(db,'study.goals.revision',1); if(r!==c.expectedRevision) reject('revision_conflict'); saveStudyPreference(db,'study.goals',c.goals); saveStudyPreference(db,'study.goals.revision',r+1); bumpStudyContext(db); return {goals:c.goals,revision:r+1}; }); break;
    case 'study.context': result=studyContext(db); break;
    case 'study.plan.read': result=plan(db); break;
    case 'study.plan.preview': { const p=proposals(db,localDay(c.clock)); result={activities:p.items,selection:p.sel,status:p.sel.topic_ids.length?'ready':p.sel.status,message:p.sel.topic_ids.length?null:p.sel.message}; break; }
    case 'study.plan.propose': {
      requireAssistance(db); const p=proposals(db,localDay(c.clock));
      for(const a of p.items) db.prepare('INSERT OR IGNORE INTO study_activities VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)').run(a.id,a.topic_id,a.objective_id,a.kind,a.title,a.due_date,a.duration_minutes,JSON.stringify(a.reason),a.evidence_id,'planned',0,utcNow(),utcNow());
      const activities=listActivities(db,p.sel,p.allTracks);
      result=p.sel.topic_ids.length?{activities,status:'ready',selection:p.sel,tracks:p.allTracks,explanation:'Committed mistakes are suggested first, followed by selected topic coverage. Manual changes are preserved.'}:{activities,status:p.sel.status,message:p.sel.message,selection:p.sel,tracks:p.allTracks};
      break;
    }
    case 'study.progress': result=progress(db); break;
    case 'study.activity.change': requireAssistance(db); result=receipt(db,c,{id:c.id,expectedRevision:c.expectedRevision,dueDate:c.dueDate,state:c.state},()=>{const r=one(db,'SELECT * FROM study_activities WHERE id=?',c.id); if(!r) reject('activity_missing'); if(sha(r)!==c.expectedRevision) reject('revision_conflict'); db.prepare('UPDATE study_activities SET due_date=?,state=?,manual_override=1,updated_at=? WHERE id=?').run(c.dueDate??r.due_date,c.state??r.state,utcNow(),c.id); if(c.state==='completed') db.prepare('INSERT OR IGNORE INTO learning_evidence VALUES(?,?,?,?,?,?)').run('study:'+c.id,'study-completion',r.topic_id,c.id,JSON.stringify({activity_id:c.id,completion:'learner-confirmed'}),utcNow()); bumpStudyContext(db); return plan(db).activities.find(a=>a.id===c.id)!; }); break;
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
    case 'study.job.stop': if(!one(db,"SELECT 1 FROM assessment_test_jobs WHERE id=? AND operation IN ('daily_suggestions','nightly_test')",c.jobId)) reject('not_found'); db.prepare("UPDATE assessment_test_jobs SET state=?,error_code=?,updated_at=? WHERE id=? AND operation IN ('daily_suggestions','nightly_test') AND state IN ('queued','running','needs_review')").run(c.state,c.errorCode,utcNow(),c.jobId); result={stopped:true}; break;
    case 'study.nightly.read': {
      const p=nightly(db), s=studyPreference<State|null>(db,'nightly.state',null), r=one(db,"SELECT id,state,requested_count,validated_count,error_code,published_version_id FROM assessment_test_jobs j WHERE operation='nightly_test' AND NOT EXISTS(SELECT 1 FROM deletion_ledger WHERE entity_type='job' AND entity_id=j.id) ORDER BY created_at DESC,id DESC LIMIT 1");
      let last_job:Record<string,unknown>|null=null;
      if(r) {
        last_job={id:r.id,state:r.state,requested_count:r.requested_count,validated_count:r.validated_count,error_code:r.error_code,result:null};
        if(r.published_version_id) { const live=one(db,"SELECT v.test_id FROM assessment_test_versions v JOIN assessment_tests t ON t.id=v.test_id WHERE v.id=? AND t.lifecycle!='deleted' AND NOT EXISTS(SELECT 1 FROM deletion_ledger WHERE (entity_type='saved_test' AND entity_id=t.id) OR (entity_type='saved_test_version' AND entity_id=v.id))",String(r.published_version_id)); last_job.result={version:{type:'saved_test_version',id:r.published_version_id},test:live?{type:'saved_test',id:live.test_id}:null,available:!!live}; }
      }
      const current=!!s && s.context_epoch===epoch(db) && s.preferences_revision===p.revision;
      result={preferences:p,app_running_only:true,next_eligible_at:p.enabled&&current?zonedIso(s!.not_before_day,p.local_time,s!.timezone):null,last_job,error_code:s?.error_code??null,assistance_allowed:!one(db,"SELECT 1 FROM assessment_test_attempts WHERE mode='test' AND status='active' LIMIT 1")}; break;
    }
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
