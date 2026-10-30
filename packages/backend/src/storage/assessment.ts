// SPDX-License-Identifier: MIT
/** Single-writer command contribution. No connection opens, awaits, files or providers. */
import type { DatabaseSync } from 'node:sqlite';
import type { AssessmentCommand,ObjectValue } from '../domain/assessment/contracts.ts';
import { draft,id,ids,list,options,question,version } from '../domain/assessment/validation.ts';
import { exact,integer,reject,text } from './contracts.ts';
import { attemptCommand,reconcileAssessments } from '../domain/assessment/attempts.ts';
import { versionCommand } from '../domain/assessment/versions.ts';
import { generationCommand } from '../domain/assessment/generation-store.ts';
import { importCommand } from '../domain/assessment/import-store.ts';
export { reconcileAssessments } from '../domain/assessment/attempts.ts';
const types=new Set(['assessment.policy','assessment.tests.list','assessment.tests.get','assessment.tests.setup','assessment.tests.preview','assessment.tests.reviewed','assessment.tests.publish','assessment.tests.change','assessment.attempts.list','assessment.attempts.start','assessment.attempts.get','assessment.attempts.draft','assessment.attempts.present','assessment.attempts.answer','assessment.attempts.submit','assessment.attempts.transition','assessment.attempts.help','assessment.help.current','assessment.report','assessment.narrative.input','assessment.generation.create','assessment.generation.get','assessment.generation.claim','assessment.generation.checkpoint','assessment.generation.fail','assessment.generation.cancel','assessment.generation.publish','assessment.import.create','assessment.import.get','assessment.import.edit','assessment.import.resolve','assessment.import.visibility','assessment.import.claim','assessment.import.normalized','assessment.import.cancel','assessment.import.publish']);
export const isAssessmentCommand=(v:unknown):v is AssessmentCommand=>!!v&&typeof v==='object'&&'type'in v&&types.has(String(v.type));
types.add('assessment.fictional.stamp');
types.add('assessment.fictional.receipt');
types.add('assessment.generation.interrupted');
export function validateAssessmentCommand(c:AssessmentCommand) {
  const fields:Record<string,string[]>={
    'assessment.policy':[], 'assessment.fictional.stamp':[], 'assessment.fictional.receipt':['idempotencyKey'], 'assessment.tests.list':['lifecycle','limit','before'], 'assessment.tests.get':['testId'],
    'assessment.tests.setup':['versionId'],'assessment.tests.preview':['versionId'],'assessment.tests.reviewed':['title','count','topicIds','idempotencyKey'],
    'assessment.tests.publish':['title','version','provenance','expectedRevision','idempotencyKey'], 'assessment.tests.change':['testId','expectedRevision','action','title','idempotencyKey'],
    'assessment.attempts.list':[],'assessment.attempts.start':['versionId','mode','timing','idempotencyKey'],'assessment.attempts.get':['attemptId'],
    'assessment.attempts.draft':['attemptId','expectedRevision','draft','idempotencyKey'],'assessment.attempts.present':['attemptId','expectedRevision','itemId','idempotencyKey'],
    'assessment.attempts.answer':['attemptId','expectedRevision','itemId','optionIds','idempotencyKey'],'assessment.attempts.submit':['attemptId','expectedRevision','latestDraft','idempotencyKey'],
    'assessment.attempts.transition':['attemptId','expectedRevision','action','idempotencyKey'],'assessment.attempts.help':['attemptId','expectedRevision','expectedPolicyRevision','itemId','kind','idempotencyKey'],
    'assessment.help.current':['context'],'assessment.report':['attemptId','itemId','reportText','idempotencyKey'],'assessment.narrative.input':['attemptId'],
    'assessment.generation.create':['input'],'assessment.generation.get':['jobId'],'assessment.generation.claim':['jobId','execution','stamp'],
    'assessment.generation.interrupted':['jobId','execution'],
    'assessment.generation.checkpoint':['jobId','execution','batchIndex','items'],'assessment.generation.fail':['jobId','execution','code'],
    'assessment.generation.cancel':['jobId'],'assessment.generation.publish':['jobId','acceptedCount','idempotencyKey'],
    'assessment.import.create':['title','original','idempotencyKey'],'assessment.import.get':['importId','original'],
    'assessment.import.edit':['importId','expectedRevision','candidateId','stem','options','explanation','topicId','idempotencyKey'],
    'assessment.import.resolve':['importId','expectedRevision','candidateId','optionIds','reviewConfirmed','idempotencyKey'],
    'assessment.import.visibility':['importId','expectedRevision','candidateId','removed','idempotencyKey'],'assessment.import.claim':['importId','expectedRevision','execution'],
    'assessment.import.normalized':['importId','execution','candidates'],'assessment.import.cancel':['importId','expectedRevision','idempotencyKey'],
    'assessment.import.publish':['importId','expectedRevision','idempotencyKey'],
  };
  if(!c||!fields[c.type])reject('storage_invalid_command');exact(c,['type',...fields[c.type]]);
  for(const k of ['testId','versionId','attemptId','itemId','jobId','importId','candidateId','execution','topicId'])if(k in c)id((c as any)[k]);
  if('idempotencyKey'in c)text(c.idempotencyKey,8,128);
  if('expectedRevision'in c&&c.expectedRevision!==null)integer(c.expectedRevision);
  if('expectedPolicyRevision'in c)integer(c.expectedPolicyRevision,1);
  if('optionIds'in c)ids(c.optionIds,1);
  if('title'in c&&c.title!==null)text(c.title,1,120);
  switch(c.type){
    case 'assessment.tests.list':if(!['active','archived'].includes(c.lifecycle))reject('invalid_request');integer(c.limit,1,100);if(c.before!==null)id(c.before);break;
    case 'assessment.tests.reviewed':integer(c.count,1,50);ids(c.topicIds,0,100);break;
    case 'assessment.tests.publish':version(c.version);if(!c.provenance||typeof c.provenance!=='object'||Array.isArray(c.provenance))reject('invalid_request');break;
    case 'assessment.tests.change':if(!['rename','archive','restore','delete'].includes(c.action)||(c.action==='rename')!==(c.title!==null))reject('invalid_request');break;
    case 'assessment.attempts.start':exact(c.timing,['kind','duration_seconds']);if(!['study','test'].includes(c.mode)||!['untimed','timed'].includes(c.timing.kind))reject('invalid_request');if(c.timing.kind==='timed')integer(c.timing.duration_seconds,1,86400);else if(c.timing.duration_seconds!==null)reject('invalid_request');break;
    case 'assessment.attempts.draft':draft(c.draft);break;
    case 'assessment.attempts.submit':if(c.latestDraft!==null)draft(c.latestDraft);break;
    case 'assessment.attempts.transition':if(!['pause','resume','continue-untimed'].includes(c.action))reject('invalid_request');break;
    case 'assessment.attempts.help':if(!['hint','sources','notes','chat'].includes(c.kind))reject('invalid_request');break;
    case 'assessment.help.current':exact(c.context,['attempt_id','item_id','version_id','draft_revision','policy_revision','kind']);[c.context.attempt_id,c.context.item_id,c.context.version_id].forEach(id);integer(c.context.draft_revision);integer(c.context.policy_revision,1);if(!['hint','sources','notes','chat'].includes(c.context.kind))reject('invalid_request');break;
    case 'assessment.report':text(c.reportText,1,2000);break;
    case 'assessment.generation.create':{
      const i=c.input;exact(i,['title','count','topic_id','inputs','source_refs','idempotencyKey',...('origin'in i?['origin']:[]),...('schedule'in i?['schedule']:[])]);text(i.title,1,120);text(i.idempotencyKey,8,128);if(![5,10,20].includes(i.count))reject('invalid_request');if(i.topic_id!==null)id(i.topic_id);list(i.inputs,0,20);list(i.source_refs,0,20);if(i.origin!==undefined&&!['generated','nightly'].includes(i.origin))reject('invalid_request');if(i.origin==='nightly'&&!i.schedule)reject('invalid_request');break;
    }
    case 'assessment.generation.claim':exact(c.stamp,['policy_revision','context_epoch']);integer(c.stamp.policy_revision,1);integer(c.stamp.context_epoch);break;
    case 'assessment.generation.checkpoint':integer(c.batchIndex,0,3);list(c.items,5,5);c.items.forEach(question);break;
    case 'assessment.generation.fail':text(c.code,1,120);if(!/^[a-z][a-z0-9_]+$/.test(c.code))reject('invalid_request');break;
    case 'assessment.generation.publish':integer(c.acceptedCount,1,20);break;
    case 'assessment.import.create':exact(c.original,['kind','text','terms','permission_confirmed']);if(c.original.kind!=='paste'||c.original.permission_confirmed!==true)reject('invalid_request');text(c.original.text,1,96000);text(c.original.terms,1,2000);if(!c.original.text.trim()||!c.original.terms.trim())reject('invalid_request');break;
    case 'assessment.import.get':if(typeof c.original!=='boolean')reject('invalid_request');break;
    case 'assessment.import.edit':text(c.stem,1,6000);options(c.options);text(c.explanation,0,6000);break;
    case 'assessment.import.resolve':if(c.reviewConfirmed!==true)reject('invalid_request');break;
    case 'assessment.import.visibility':if(typeof c.removed!=='boolean')reject('invalid_request');break;
    case 'assessment.import.normalized':list(c.candidates,1,50);for(const v of c.candidates){exact(v,['id','span','stem','options','explanation','topic_id','correct_option_ids','key_status','removed','revision','review_confirmed']);id(v.id);exact(v.span,['start','end']);integer(v.span.start);integer(v.span.end,v.span.start+1);text(v.stem,1,6000);options(v.options);text(v.explanation,0,6000);id(v.topic_id);ids(v.correct_option_ids);if(!['missing','ambiguous','resolved'].includes(v.key_status)||typeof v.removed!=='boolean'||typeof v.review_confirmed!=='boolean')reject('invalid_request');integer(v.revision,1);}break;
  }
}
export function executeAssessment(db:DatabaseSync,c:AssessmentCommand):ObjectValue|null {
  validateAssessmentCommand(c);reconcileAssessments(db);
  if(c.type.startsWith('assessment.tests.'))return versionCommand(db,c);
  if(c.type.startsWith('assessment.generation.'))return generationCommand(db,c);
  if(c.type.startsWith('assessment.import.'))return importCommand(db,c);
  return attemptCommand(db,c);
}
