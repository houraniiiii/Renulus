// SPDX-License-Identifier: MIT
/** Settled full native graph recovery through the SAME public sessions seam used
 * by session-transfer.ts. No SDK database files, execution jobs or claims are imported.
 * The candidate host stays recovery-held and empty until this owner finishes.
 */
import { createHash } from 'node:crypto';
import { Schema, type Effect } from 'effect';
import type { OpenCode } from '@opencode/sdk/effect';
import type { Location } from '@opencode/schema/location';
import { Session } from '@opencode/schema/session';
import { SessionMessage } from '@opencode/schema/session-message';
type JsonObject=Record<string,unknown>;
export interface GraphSession { info:JsonObject; messages:JsonObject[] }
export interface RecoveryGraph { contract:'renulus-native-recovery/1'; storeId:string; sessions:GraphSession[] }
export interface GraphMap { incomingStore:string; candidateStore:string; sessions:Record<string,string>; messages:Record<string,string> }
export interface GraphRecoveryOptions {
  sdk:{sessions:Pick<OpenCode.Interface['sessions'],'export'|'import'|'list'>};
  run:<A,E>(effect:Effect.Effect<A,E>)=>Promise<A>;
  storeId:string;location:Location.Ref;
  /** Retained host ownership + recovery hold, checked on both sides of native I/O. */
  checkHeld:()=>void;
}
export class GraphRecoveryError extends Error {readonly code:string;constructor(code:string){super(code);this.code=code;}}
const fail=(code:string):never=>{throw new GraphRecoveryError(code);};
function canonical(v:unknown):string {if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';if(v&&typeof v==='object')return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical((v as JsonObject)[k])).join(',')+'}';return JSON.stringify(v);}
const sha=(v:unknown)=>createHash('sha256').update(canonical(v)).digest('hex');
const encodeMessage=(v:SessionMessage.Info)=>Schema.encodeSync(SessionMessage.Info)(v) as unknown as JsonObject;
const encodeInfo=(v:Session.Info)=>Schema.encodeSync(Session.Info)(v) as unknown as JsonObject;
const ident=(v:unknown,prefix:string)=>typeof v==='string'&&v.startsWith(prefix)&&v.length<=256;
function references(value:unknown,sessions:Set<string>,messages:Set<string>) {
  if(Array.isArray(value)){for(const v of value)references(v,sessions,messages);return;}
  if(!value||typeof value!=='object')return;
  for(const [key,v]of Object.entries(value)) {
    if(['parentID','sessionID','session_id','childSessionID','child_session_id'].includes(key)&&typeof v==='string'&&!sessions.has(v))fail('recovery_graph_parent_missing');
    if(['messageID','message_id','input_id','parentMessageID'].includes(key)&&typeof v==='string'&&!messages.has(v))fail('recovery_graph_message_missing');
    references(v,sessions,messages);
  }
}
export function validateRecoveryGraph(graph:RecoveryGraph) {
  if(graph.contract!=='renulus-native-recovery/1'||!graph.storeId||graph.sessions.length>4096||Buffer.byteLength(canonical(graph))>64*1024*1024)fail('recovery_graph_limit');
  const sessions=new Set<string>(),messages=new Set<string>();
  for(const session of graph.sessions) {
    Schema.decodeUnknownSync(Session.Info)(session.info);
    const id=session.info.id;if(!ident(id,'ses_')||sessions.has(String(id)))fail('recovery_graph_duplicate');sessions.add(String(id));
    // The pinned public importer does not preserve fork/revert. Never flatten them.
    if(session.info.fork||session.info.revert)fail('recovery_graph_unsupported_branch');
    let time=-Infinity;
    for(const message of session.messages) {
      Schema.decodeUnknownSync(SessionMessage.Info)(message);
      const mid=message.id;if(!ident(mid,'msg_')||messages.has(String(mid)))fail('recovery_graph_duplicate');messages.add(String(mid));
      const created=Number((message.time as JsonObject).created);if(!Number.isFinite(created)||created<time)fail('recovery_graph_order');time=created;
      if(message.type==='assistant'&&typeof(message.time as JsonObject).completed!=='number'||['shell','compaction'].includes(String(message.type))&&message.status==='running')fail('recovery_graph_unsettled');
      for(const part of Array.isArray(message.content)?message.content:[])if(part.type==='tool'&&!['completed','error'].includes(String(part.state?.status)))fail('recovery_graph_tool_unsettled');
    }
  }
  for(const session of graph.sessions) {references(session.info,sessions,messages);for(const message of session.messages)references(message,sessions,messages);}
  // Parent cycles are refused before the first import.
  const pending=new Map(graph.sessions.map(s=>[String(s.info.id),s.info.parentID]));
  for(let n=0;pending.size&&n<=graph.sessions.length;n++)for(const [id,parent]of pending)if(!parent||!pending.has(String(parent)))pending.delete(id);
  if(pending.size)fail('recovery_graph_parent_cycle');
}
/** Exact settled history only: compaction/summary nodes and provider continuation state are derived. */
const history=(messages:JsonObject[])=>messages.filter(m=>m.type!=='compaction').map(m=>{
  const next=structuredClone(m);delete next.providerState;delete next.retry;
  if(Array.isArray(next.content))for(const part of next.content){delete part.providerState;delete part.providerResultState;}
  return next;
});
/** Incoming sessions never bring live permissions, claims or provider state with them. */
function inert(session:GraphSession,storeId:string):GraphSession {
  const info=structuredClone(session.info);info.permissions=[{action:'*',resource:'*',effect:'deny'}];
  info.metadata={...(info.metadata as JsonObject??{}),renulusStore:storeId,recoveryInert:true};
  return {info,messages:history(session.messages)};
}
/** Additive merge: current sessions are kept exactly (mutable metadata, order and permissions win); incoming-only
 * sessions and strictly newer incoming suffixes are added inertly. Any identity/order/relation disagreement refuses. */
export function mergeRecoveryGraphs(current:RecoveryGraph,incoming:RecoveryGraph,candidateStore=current.storeId,eligible:(session:GraphSession)=>boolean=()=>true):{graph:RecoveryGraph;mapping:GraphMap;retained:number;currentOnly:number;added:number;excluded:number} {
  validateRecoveryGraph(current);validateRecoveryGraph(incoming);
  const currentSessions=new Map(current.sessions.map(s=>[String(s.info.id),structuredClone(s)]));
  const bySession=new Map(incoming.sessions.map(s=>[String(s.info.id),s]));
  const mapping:GraphMap={incomingStore:incoming.storeId,candidateStore,sessions:{},messages:{}};
  // A child is imported only with its parent: excluded roots exclude their whole closure.
  const memo=new Map<string,boolean>();
  const included=(s:GraphSession):boolean=>{
    const id=String(s.info.id),known=memo.get(id);if(known!==undefined)return known;
    const parent=s.info.parentID?bySession.get(String(s.info.parentID)):undefined;
    const ok=!parent?eligible(s):included(parent);memo.set(id,ok);return ok;
  };
  const added:GraphSession[]=[];let retained=0,appended=0,excluded=0;
  for(const source of incoming.sessions) {
    if(!included(source)){excluded++;continue;}
    const sid=String(source.info.id),existing=currentSessions.get(sid),theirs=history(source.messages);mapping.sessions[sid]=sid;
    for(const m of theirs)mapping.messages[String(m.id)]=String(m.id);
    if(!existing){added.push(source);continue;}
    if(existing.info.parentID!==source.info.parentID)fail('recovery_graph_identity_conflict');
    const ours=history(existing.messages),common=Math.min(ours.length,theirs.length);
    for(let i=0;i<common;i++) {
      if(ours[i].id!==theirs[i].id||canonical(ours[i])!==canonical(theirs[i]))fail('recovery_graph_identity_conflict');retained++;
    }
    // A single consistent ordering is mandatory. Divergent suffixes are never interleaved.
    if(theirs.length>ours.length){existing.messages.push(...theirs.slice(common));appended+=theirs.length-common;}
  }
  // Incoming-only sessions are added after current ones so every parent precedes its children on import.
  const sessions=[...currentSessions.values(),...added.map(s=>inert(s,candidateStore))];
  const graph:RecoveryGraph={contract:'renulus-native-recovery/1',storeId:candidateStore,sessions};
  validateRecoveryGraph(graph);
  const addedMessages=added.reduce((n,s)=>n+history(s.messages).length,0);
  const currentMessages=current.sessions.reduce((n,s)=>n+history(s.messages).length,0);
  return {graph,mapping,retained,currentOnly:currentMessages-retained,added:addedMessages+appended,excluded};
}
export function createGraphRecovery(o:GraphRecoveryOptions) {
  let busy=false;
  /** Every session of the store: paged roots, then each root's children (deduplicated, so listing order is irrelevant). */
  async function allSessionIds():Promise<string[]> {
    const ids=new Set<string>(),queue:(string|undefined)[]=[undefined];
    while(queue.length) {
      const parent=queue.shift();
      let cursor:NonNullable<Parameters<typeof o.sdk.sessions.list>[0]>['cursor']|undefined;
      for(let page=0;page<100;page++) {
        o.checkHeld();
        const result=await o.run(o.sdk.sessions.list({limit:100,...(parent?{parentID:Session.ID.make(parent)}:{}),...(cursor?{cursor}:{})}));
        for(const s of result.data)if(!ids.has(String(s.id))){ids.add(String(s.id));queue.push(String(s.id));}
        cursor=result.cursor.next;if(!cursor||result.data.length<100)break;
      }
    }
    return [...ids];
  }
  return {
    async snapshotAll():Promise<RecoveryGraph> {return this.snapshot(await allSessionIds());},
    async snapshot(sessionIds:readonly string[]):Promise<RecoveryGraph> {
      o.checkHeld();if(busy)fail('recovery_graph_busy');busy=true;
      try {const sessions:GraphSession[]=[];for(const id of sessionIds){o.checkHeld();const result=await o.run(o.sdk.sessions.export({sessionID:Session.ID.make(id),sanitize:false}));o.checkHeld();sessions.push({info:encodeInfo(result.info),messages:result.messages.map(encodeMessage)});}
        const graph:RecoveryGraph={contract:'renulus-native-recovery/1',storeId:o.storeId,sessions};validateRecoveryGraph(graph);return graph;
      }finally{busy=false;}
    },
    async importMerged(current:RecoveryGraph,incoming:RecoveryGraph,eligible?:(session:GraphSession)=>boolean) {
      o.checkHeld();if(busy)fail('recovery_graph_busy');busy=true;
      try {
        const merged=mergeRecoveryGraphs(current,incoming,o.storeId,eligible);
        const existing=await o.run(o.sdk.sessions.list({limit:1}));o.checkHeld();if(existing.data.length)fail('recovery_graph_candidate_not_empty');
        const pending=new Map(merged.graph.sessions.map(s=>[String(s.info.id),s]));
        while(pending.size)for(const [id,s]of pending) {
          if(s.info.parentID&&pending.has(String(s.info.parentID)))continue;
          o.checkHeld();const info=Schema.decodeUnknownSync(Session.Info)(s.info),messages=s.messages.map(m=>Schema.decodeUnknownSync(SessionMessage.Info)(m));
          await o.run(o.sdk.sessions.import({info,messages,location:o.location}));o.checkHeld();
          const actual=await o.run(o.sdk.sessions.export({sessionID:Session.ID.make(id),sanitize:false}));o.checkHeld();
          if(canonical(actual.messages.map(encodeMessage))!==canonical(s.messages)||actual.info.parentID!==info.parentID||canonical(actual.info.metadata)!==canonical(info.metadata))fail('recovery_graph_import_unconfirmed');
          pending.delete(id);
        }
        return {...merged,digest:sha(merged.graph)};
      }finally{busy=false;}
    },
  };
}
