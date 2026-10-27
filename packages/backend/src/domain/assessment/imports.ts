// SPDX-License-Identifier: MIT
/** Lossless common MCQ parser and strict formatting-only model normalization. */
import { canonical,digest } from '../../storage/schema.ts';
import { exact,integer,reject,text } from '../../storage/contracts.ts';
import { id,list,options } from './validation.ts';
import type { ImportCandidate,ObjectValue,Option } from './contracts.ts';
const source=(s:string)=>s.normalize('NFC').replace(/\s+/g,' ').trim();
function key(original:string,labels:string[]) {
  const matches=[...original.matchAll(/^[ \t]*(?:correct answer|answer|key)[ \t]*[:=][ \t]*([^\r\n]+)/gim)];
  if(!matches.length)return {correct_option_ids:[],key_status:'missing' as const};
  const choices=matches.map(m=>{const raw=m[1].trim().toLowerCase();if(!/^[a-t](?:[ \t]*[,/;&][ \t]*[a-t])*[.)]?$/.test(raw))return null;const ids=raw.match(/[a-t]/g)!;return new Set(ids).size===ids.length&&ids.every(i=>labels.includes(i))?ids.sort():null;});
  if(choices.some(v=>!v)||choices.some(v=>canonical(v)!==canonical(choices[0])))return {correct_option_ids:[],key_status:'ambiguous' as const};
  return {correct_option_ids:choices[0]!,key_status:'resolved' as const};
}
export function parseOriginal(original:string):ImportCandidate[] {
  const headers=[...original.matchAll(/^[ \t]*(?:q(?:uestion)?[ \t]*)?\d+[.)][ \t]+/gim)],starts=headers.length?headers.map(h=>h.index):[0];const out:ImportCandidate[]=[];
  for(let i=0;i<starts.length;i++){
    const start=starts[i],end=starts[i+1]??original.length,block=original.slice(start,end),matches=[...block.matchAll(/^[ \t]*([a-t])[.)\]:][ \t]+([^\r\n]+)/gim)];
    if(matches.length<2||matches.length>20)continue;const stemStart=headers.length?headers[i].index+headers[i][0].length:start,stem=original.slice(stemStart,start+matches[0].index).trim();if(!stem||stem.length>6000)continue;
    const os=matches.map(m=>({id:m[1].toLowerCase(),text:m[2].trim()}));if(os.some(o=>!o.text||o.text.length>2000)||new Set(os.map(o=>o.id)).size!==os.length)continue;
    // Store spans as Unicode character offsets, matching Python's immutable originals.
    const span={start:[...original.slice(0,start)].length,end:[...original.slice(0,end)].length};
    out.push({id:'candidate_'+digest(canonical(span)).slice(0,24),span,stem,options:os,explanation:'',topic_id:'personal-import',...key(block,os.map(o=>o.id)),removed:false,revision:1,review_confirmed:false});
  }
  if(out.length>50)reject('import_candidate_limit');return out;
}
export function normalizedCandidates(original:string,value:unknown):ImportCandidate[] {
  exact(value,['candidates']);list(value.candidates,1,50);const chars=[...original],out:ImportCandidate[]=[];
  function span(s:unknown,parent?:unknown) {exact(s,['start','end']);integer(s.start,0,chars.length);integer(s.end,s.start+1,chars.length);const p=parent as ObjectValue|undefined;if(p&&(s.start<p.start||s.end>p.end))reject('import_invalid_normalization');return chars.slice(s.start,s.end).join('');}
  for(const raw of value.candidates){
    exact(raw,['span','stem_span','stem','options','explanation','explanation_span']);const c: ObjectValue=raw;const block=span(c.span);text(c.stem,1,6000);if(source(span(c.stem_span,c.span))!==source(c.stem))reject('import_invalid_normalization');
    list(c.options,2,20);const os:Option[]=c.options.map((o:ObjectValue)=>{exact(o,['id','text','span']);id(o.id);text(o.text,1,2000);if(source(span(o.span,c.span))!==source(o.text))reject('import_invalid_normalization');return {id:o.id,text:o.text};});options(os);
    text(c.explanation,0,6000);if(c.explanation&&(!c.explanation_span||source(span(c.explanation_span,c.span))!==source(c.explanation)))reject('import_invalid_normalization');
    out.push({id:'candidate_'+digest(canonical(c.span)).slice(0,24),span:c.span,stem:c.stem,options:os,explanation:c.explanation,topic_id:'personal-import',...key(block,os.map((o:ObjectValue)=>o.id)),removed:false,revision:1,review_confirmed:false});
  }
  const ordered=[...out].sort((a,b)=>a.span.start-b.span.start);if(ordered.some((v,i)=>i>0&&ordered[i-1].span.end>v.span.start)||new Set(out.map(q=>source(q.stem))).size!==out.length||out.some(q=>new Set(q.options.map(o=>source(o.text))).size!==q.options.length))reject('import_invalid_normalization');return out;
}
