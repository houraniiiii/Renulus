// SPDX-License-Identifier: MIT
import { useEffect, useRef, useState } from 'react';
import { api, isCancelled } from '../../platform/api';
import { studyHelpHeaders, type ConversationSummary, type StudyHelpContext } from '../../platform/designC';
import { Button, ErrorState, LoadingState, Notice, Select, Textarea } from '../../ui';
import { CaseAttachments } from '../cases/CaseAttachments';
import { CaseOriginals } from '../cases/CaseOriginals';
import { CaseCurrencyLabel } from '../cases/CaseCurrency';
import type { CaseCapabilities, CaseSession, TeachingSummary } from '../cases/types';
import { conversationPath } from './api';
import '../cases/cases.css';

interface CaseReceipt {conversation: ConversationSummary; case_revision: number}

export function CaseContext({conversation, disabled, beforeChange, onChanged, onStartTeaching, onDiscussImage, studyHelpContext}: {
  conversation: ConversationSummary; disabled: boolean;
  beforeChange: () => Promise<ConversationSummary|undefined>;
  onChanged: (value: ConversationSummary) => void;
  onStartTeaching: (id: string) => Promise<void>;
  onDiscussImage?: (id:string, caseRevision:number, model:string, question:string) => Promise<void>;
  studyHelpContext?:StudyHelpContext;
}) {
  const [session,setSession] = useState<CaseSession>();
  const [contextError,setContextError] = useState<unknown>();
  const [capabilities,setCapabilities] = useState<CaseCapabilities>();
  const [capabilitiesLoading,setCapabilitiesLoading] = useState(true);
  const [capabilitiesError,setCapabilitiesError] = useState<unknown>();
  const [teaching,setTeaching] = useState<TeachingSummary[]>();
  const [teachingLoading,setTeachingLoading] = useState(true);
  const [teachingError,setTeachingError] = useState<unknown>();
  const [selected,setSelected] = useState('');
  const [editing,setEditing] = useState(false);
  const [expanded,setExpanded] = useState(false);
  const [text,setText] = useState('');
  const [working,setWorking] = useState(false);
  const [error,setError] = useState<unknown>();
  const [refresh,setRefresh] = useState(0);
  const identity = useRef(conversation.identity.id); identity.current=conversation.identity.id;
  const currentSession = useRef(session); currentSession.current=session;
  const locked=disabled||working;
  const helpHeaders=studyHelpHeaders(studyHelpContext);
  function retryReads(){setError(undefined);setRefresh(value=>value+1);}

  useEffect(()=>{
    setSession(undefined);setContextError(undefined);setEditing(false);setExpanded(false);setText('');setSelected('');setError(undefined);setWorking(false);
    setCapabilities(undefined);setTeaching(undefined);
  },[conversation.identity.id]);
  useEffect(()=>{
    if(disabled||working)return;
    const controller=new AbortController();
    setContextError(undefined);
    async function read(){
      try{
        const value=await api<Omit<CaseSession,'messages'>>(conversationPath(conversation)+'/context',{signal:controller.signal,headers:helpHeaders});
        if(controller.signal.aborted)return;
        setSession({...value,messages:[]});
        if(!currentSession.current&&(value.kind==='teaching'||value.text===''))setExpanded(true);
      }catch(caught){if(!isCancelled(caught)&&!controller.signal.aborted){setContextError(caught);if(!currentSession.current)setExpanded(true);}}
    }
    void read();
    return()=>controller.abort();
  },[conversation.identity.id,conversation.revision,disabled,working,refresh,JSON.stringify(studyHelpContext)]);
  useEffect(()=>{
    const controller=new AbortController();
    setCapabilitiesLoading(true);setCapabilitiesError(undefined);
    setTeachingLoading(true);setTeachingError(undefined);
    void api<CaseCapabilities>('/cases/capabilities',{signal:controller.signal,headers:helpHeaders})
      .then(value=>{if(!controller.signal.aborted)setCapabilities(value);})
      .catch(caught=>{if(!controller.signal.aborted&&!isCancelled(caught))setCapabilitiesError(caught);})
      .finally(()=>{if(!controller.signal.aborted)setCapabilitiesLoading(false);});
    void api<{cases:TeachingSummary[]}>('/cases/teaching',{signal:controller.signal,headers:helpHeaders})
      .then(value=>{if(!controller.signal.aborted)setTeaching(value.cases);})
      .catch(caught=>{if(!controller.signal.aborted&&!isCancelled(caught))setTeachingError(caught);})
      .finally(()=>{if(!controller.signal.aborted)setTeachingLoading(false);});
    return()=>controller.abort();
  },[conversation.identity.id,refresh,JSON.stringify(studyHelpContext)]);

  async function change(action:'edit'|'reveal'|'remove'|'apply'|'keep',identifier?:string,reviewedText?:string){
    if(locked||!currentSession.current)return;
    const owner=currentSession.current,expectedIdentity=conversation.identity.id;
    setWorking(true);setError(undefined);
    try{
      const latest=await beforeChange();
      if(!latest||identity.current!==expectedIdentity)return;
      const body={expected_revision:latest.revision,case_revision:owner.revision,...(reviewedText!==undefined?{text:reviewedText}:{})};
      const suffix=action==='edit'?'/context':action==='reveal'?'/context/reveal':action==='remove'?'/attachments/'+encodeURIComponent(identifier!):'/previews/'+encodeURIComponent(identifier!)+'/'+action;
      const path=conversationPath(latest)+suffix+(action==='remove'?'?expected_revision='+body.expected_revision+'&case_revision='+body.case_revision:'');
      const receipt=await api<CaseReceipt>(path,{method:action==='edit'?'PATCH':action==='remove'?'DELETE':'POST',
        ...(action==='remove'?{}:{body}),headers:{'Idempotency-Key':crypto.randomUUID(),...helpHeaders}});
      if(identity.current!==expectedIdentity)return;
      onChanged(receipt.conversation);
      const value=await api<Omit<CaseSession,'messages'>>(conversationPath(latest)+'/context',{headers:helpHeaders});
      if(identity.current!==expectedIdentity)return;
      const next={...value,messages:[]};
      setSession(next);currentSession.current=next;
      if(action==='edit')setEditing(false);
      return next;
    }catch(caught){if(identity.current===expectedIdentity)setError(caught);}
    finally{if(identity.current===expectedIdentity)setWorking(false);}
  }

  return <section className="chat-case-context" aria-label="Case context">
    <details open={expanded} onToggle={event=>setExpanded(event.currentTarget.open)}>
      <summary>Case context{session?.teaching?' · Pinned teaching case':''}</summary>
      {!session&&!contextError&&!error&&<LoadingState label="Opening case context"/>}
      {session&&<>
        {session.kind==='daily'?<>
          {editing?<><Textarea label="Case context text" rows={5} maxLength={50000} disabled={locked} value={text} onChange={event=>setText(event.target.value)}/>
            <div className="actions"><Button disabled={locked||!text.trim()} busy={working} onClick={()=>void change('edit',undefined,text.trim())}>{conversation.retention==='saved'?'Save case context':'Use temporary context'}</Button><Button variant="ghost" disabled={locked} onClick={()=>setEditing(false)}>Keep current context</Button></div></>:<>
            {session.text?<p className="case-text">{session.text}</p>:<p className="muted">Add the case details you want to discuss. Your question stays in the composer below.</p>}
            <Button variant="secondary" disabled={locked} onClick={()=>{setText(session.text);setEditing(true);}}>Edit case context</Button>
          </>}
          <CaseOriginals studyHelpContext={studyHelpContext} session={session} retention={conversation.retention} disabled={locked} remove={id=>change('remove',id)}/>
          {capabilities&&<CaseAttachments studyHelpContext={studyHelpContext} session={session} retention={conversation.retention} capabilities={capabilities} disabled={locked||capabilitiesLoading||Boolean(capabilitiesError)} apply={(id,text)=>change('apply',id,text)} keepImage={id=>change('keep',id)} discussImage={onDiscussImage?(id,model,question)=>onDiscussImage(id,session.revision,model,question):undefined}/>}
          {teaching&&teaching.length>0&&<details className="chat-teaching-entry"><summary>Start an installed teaching case</summary><Select label="Teaching case" value={selected} disabled={locked||teachingLoading||Boolean(teachingError)} onChange={event=>setSelected(event.target.value)}><option value="">Choose a teaching case</option>{teaching.map(item=><option key={item.id} value={item.id}>{item.title}</option>)}</Select><Button variant="secondary" disabled={locked||teachingLoading||Boolean(teachingError)||!teaching.some(item=>item.id===selected)} onClick={()=>{setWorking(true);void onStartTeaching(selected).catch(setError).finally(()=>setWorking(false));}}>Start teaching conversation</Button></details>}
          {teaching?.length===0&&!teachingLoading&&!teachingError&&<p className="muted">No installed teaching cases are available.</p>}
        </>:session.teaching&&<>
          <p className="muted">Pinned version {session.teaching.version} · <CaseCurrencyLabel currency={session.teaching.currency}/></p>
          <div className="case-teaching">{session.teaching.stages.map((stage,index)=><article className="case-stage" key={stage.id}><h2>Stage {index+1} of {session.teaching!.stage_count}</h2><p className="case-text">{stage.narrative}</p><ul>{stage.prompts.map(prompt=><li key={prompt}>{prompt}</li>)}</ul>{stage.teaching_points&&<details className="case-debrief"><summary>Teaching points and sources</summary><ul>{stage.teaching_points.map(point=><li key={point}>{point}</li>)}</ul>{stage.sources?.map(source=><p className="muted" key={source.source_id+source.locator}>{source.source_id} · {source.locator}</p>)}</details>}</article>)}</div>
          {session.teaching.take_home&&<><h2>Take-home learning</h2><ul>{session.teaching.take_home.map(point=><li key={point}>{point}</li>)}</ul></>}
          {!session.teaching.debriefed&&<Button variant="secondary" disabled={locked} busy={working} onClick={()=>void change('reveal')}>{session.teaching.revealed_count<session.teaching.stage_count?'Reveal next stage':'Reveal debrief'}</Button>}
        </>}
        {session.dirty&&conversation.retention==='saved'&&<Notice tone="warning">This Case has changes from the earlier Case view. A context action here saves the current Case snapshot.</Notice>}
      </>}
      {capabilitiesLoading&&<LoadingState label="Loading case attachment options"/>}
      {Boolean(capabilitiesError)&&<ErrorState error={capabilitiesError} title="Case attachment options could not be loaded" onRetry={locked?undefined:retryReads}/>}
      {teachingLoading&&<LoadingState label="Loading teaching cases"/>}
      {Boolean(teachingError)&&<ErrorState error={teachingError} title="Teaching cases could not be loaded" onRetry={locked?undefined:retryReads}/>}
      {Boolean(contextError)&&<ErrorState error={contextError} title="Case context could not be loaded" onRetry={locked?undefined:retryReads}/>}
      {Boolean(error)&&<ErrorState error={error} title="Case context could not be updated" onRetry={locked?undefined:retryReads}/>}
    </details>
  </section>;
}
