// SPDX-License-Identifier: MIT
import { exact, integer, reject, text } from '../../storage/contracts.ts';
import type { DraftState, GeneratedBatch, QuestionSnapshot, TestVersion } from './contracts.ts';
export function id(v:unknown):asserts v is string { text(v,1,256); if(!/^[A-Za-z0-9][A-Za-z0-9._:-]*$/.test(v)) reject('invalid_request'); }
export function list(v:unknown,min:number,max:number):asserts v is any[] { if(!Array.isArray(v)||v.length<min||v.length>max) reject('invalid_request'); }
export function ids(v:unknown,min=0,max=20):asserts v is string[] { list(v,min,max); v.forEach(id); if(new Set(v).size!==v.length)reject('invalid_request'); }
export function options(v:unknown) { list(v,2,20); for(const o of v){exact(o,['id','text']);id(o.id);text(o.text,1,2000);} if(new Set(v.map(o=>o.id)).size!==v.length)reject('invalid_request'); }
export function question(q:QuestionSnapshot) {
  exact(q,['item_id','question_id','question_version','key_version','family_id','family_version','topic_id','stem','options','correct_option_ids','explanation']);
  [q.item_id,q.question_id,q.question_version,q.family_id,q.family_version,q.topic_id].forEach(id); if(q.key_version!==null)id(q.key_version);
  text(q.stem,1,6000); text(q.explanation,0,6000); options(q.options);ids(q.correct_option_ids);
  if(q.correct_option_ids.some(k=>!q.options.some(o=>o.id===k)))reject('invalid_request');
}
export function version(v:TestVersion) {
  exact(v,['id','test_id','ordinal','origin','review_quality','status','items','source_refs','provenance','terms','created_at']);
  id(v.id);id(v.test_id);integer(v.ordinal,1);list(v.items,1,50);v.items.forEach(question);list(v.source_refs,0,50);
  if(!['reviewed_bank','generated','imported','nightly'].includes(v.origin)||!['reviewed','personal','needs_review'].includes(v.review_quality)||!['ready','needs_review'].includes(v.status))reject('invalid_request');
  if(v.review_quality==='reviewed'&&v.origin!=='reviewed_bank')reject('invalid_request');
  if(v.status==='ready'&&(v.review_quality==='needs_review'||v.items.some(q=>!q.key_version||!q.correct_option_ids.length)))reject('test_not_ready');
  if(new Set(v.items.map(q=>q.item_id)).size!==v.items.length||new Set(v.items.map(q=>q.family_id)).size!==v.items.length)reject('invalid_request');
  exact(v.provenance,['schema_version','method','job_id','fictional_artifact_id']);
  if(v.provenance.schema_version!==1||!['reviewed_pack','generation','import','nightly','legacy_conversion'].includes(v.provenance.method))reject('invalid_request');
  for(const p of [v.provenance.job_id,v.provenance.fictional_artifact_id])if(p!==null)id(p);
  text(v.terms,1,2000);text(v.created_at,1,64);if(!Number.isFinite(Date.parse(v.created_at)))reject('invalid_request');
}
export function draft(d:DraftState) { exact(d,['position','answers']);integer(d.position,0,49);list(d.answers,1,50);
  for(const a of d.answers){exact(a,['item_id','option_ids','marked']);id(a.item_id);ids(a.option_ids);if(typeof a.marked!=='boolean')reject('invalid_request');}
  if(new Set(d.answers.map(a=>a.item_id)).size!==d.answers.length)reject('invalid_request'); }
export function batch(b:GeneratedBatch) { exact(b,['items']);list(b.items,1,5);
  for(const q of b.items){
    const keys=['stem','options','correct_option_id','explanation',...('hint'in q?['hint']:[]),...('source_indices'in q?['source_indices']:[])];exact(q,keys);
    text(q.stem,1,6000);text(q.explanation,1,6000);list(q.options,2,6);
    for(const o of q.options){exact(o,['id','text',...('rationale'in o?['rationale']:[])]);id(o.id);text(o.text,1,2000);if(o.rationale!==undefined&&o.rationale!==null)text(o.rationale,0,3000);}
    if(new Set(q.options.map(o=>o.id)).size!==q.options.length||!q.options.some(o=>o.id===q.correct_option_id))reject('generation_invalid');
    if(q.hint!==undefined&&q.hint!==null)text(q.hint,0,1600);
    if(q.source_indices!==undefined){list(q.source_indices,0,5);q.source_indices.forEach(n=>integer(n,0,4));if(new Set(q.source_indices).size!==q.source_indices.length)reject('generation_invalid');}
  }
}
