import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Archive, ArrowUp, Paperclip, Square, Trash2, X } from 'lucide-react';
import { api, ApiError, isCancelled } from '../../platform/api';
import type { ContentReference, ConversationIdentity, ConversationSummary, PageResult, PassageDraft, ProjectSummary } from '../../platform/designC';
import { Badge, Button, ErrorState, IconButton, Input, LoadingState, Notice, Select, Textarea } from '../../ui';
import { useWorkspace } from '../workspace';
import { CaseContext } from './CaseContext';
import { CaseHandoffActions } from './CaseHandoffActions';
import { conversationPath, createConversation, sendConversation, type ConversationRun, type SendIntent } from './api';
import './chat.css';

interface Message {id: string; run_id: string; role: 'user'|'assistant'; content: string; content_refs: ContentReference[]}
interface Draft {text: string; content_refs: ContentReference[]; revision: number; conversation_revision: number}
export interface ChatPageProps {
  identity?: ConversationIdentity;
  conversation?: ConversationSummary;
  prefill?: string;
  sendIntent?: SendIntent;
  onSendIntentConsumed?: (requestId: string) => void;
  passageIntent?: PassageDraft & {id: string};
  onPassageIntentConsumed?: (id: string) => void;
  onConversation?: (value: ConversationSummary|null) => void;
}
const changed = () => window.dispatchEvent(new Event('renulus:records-changed'));
const signature = (text: string, refs: ContentReference[]) => JSON.stringify({text,refs});

/** The reading measure leads; paper/teal, Source Sans and 4px rhythm match the shell. */
export default function ChatPage(props: ChatPageProps) {
  const workspace = useWorkspace();
  const [chat,setChat] = useState<ConversationSummary>();
  const [messages,setMessages] = useState<Message[]>([]);
  const [cursor,setCursor] = useState<string|null>(null);
  const [text,setText] = useState('');
  const [refs,setRefs] = useState<ContentReference[]>([]);
  const [style,setStyle] = useState<'direct'|'guided'>('direct');
  const [partial,setPartial] = useState('');
  const [status,setStatus] = useState('');
  const [error,setError] = useState<unknown>();
  const [loading,setLoading] = useState(true);
  const [busy,setBusy] = useState(false);
  const [recovering,setRecovering] = useState(false);
  const [title,setTitle] = useState('');
  const [projects,setProjects] = useState<ProjectSummary[]>([]);
  const [confirmDelete,setConfirmDelete] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const chatRef = useRef<ConversationSummary|undefined>(undefined);
  const textRef = useRef('');
  const refsRef = useRef<ContentReference[]>([]);
  const epoch = useRef(0);
  const streamAbort = useRef<AbortController|null>(null);
  const activeRun = useRef<string|undefined>(undefined);
  const visibleRun = useRef<string|undefined>(undefined);
  const draftWrite = useRef<Promise<void>>(Promise.resolve());
  const persisted = useRef('');
  const consumed = useRef(new Set<string>());
  const callback = useRef(props); callback.current=props;
  textRef.current=text; refsRef.current=refs;
  function accept(value: ConversationSummary) {chatRef.current=value;setChat(value);setTitle(value.title);}
  const incoming = props.identity ?? props.conversation?.identity;
  const incomingKey = incoming ? incoming.type+':'+incoming.id : 'new';

  useEffect(() => {
    const version=++epoch.current, controller=new AbortController();
    setLoading(true);setError(undefined);setMessages([]);setPartial('');setBusy(false);setRecovering(false);setStatus('');
    activeRun.current=undefined;visibleRun.current=undefined;
    chatRef.current=undefined;setChat(undefined);setRefs([]);setText('');persisted.current='';
    async function load() {
      try {
        if (!incoming) {setLoading(false);return;}
        const kind=incoming.type==='learn_thread'?'learning':'case';
        const value=await api<ConversationSummary>('/conversations/'+kind+'/'+encodeURIComponent(incoming.id),{signal:controller.signal});
        const [page,draft,runs] = await Promise.all([
          api<PageResult<Message>>(conversationPath(value)+'/messages',{signal:controller.signal}),
          api<Draft>(conversationPath(value)+'/draft',{signal:controller.signal}),
          api<PageResult<ConversationRun>>(conversationPath(value)+'/runs',{signal:controller.signal}),
        ]);
        if (epoch.current!==version) return;
        accept({...value,revision:draft.conversation_revision});setMessages(page.items);setCursor(page.next_cursor);
        persisted.current=signature(draft.text,draft.content_refs);
        setText(draft.text || callback.current.prefill || '');setRefs(draft.content_refs);setLoading(false);
        const running=runs.items?.find(run=>run.state==='running');
        if(running){activeRun.current=running.run_id;visibleRun.current=running.run_id;setBusy(true);setRecovering(true);setStatus('Response is running');}
        else if(runs.items?.[0]&&runs.items[0].state!=='completed'){
          const latest=await api<ConversationRun>(conversationPath(value)+'/runs/'+encodeURIComponent(runs.items[0].run_id),{signal:controller.signal});
          if(epoch.current!==version)return;
          setStatus(latest.state==='cancelled'?'Stopped. Your draft is retained.':'Response did not finish. Your draft is retained.');
          if(latest.error)setError(new ApiError(latest.error.message,409,latest.error.code,latest.error.retryable));
        }
        void api<PageResult<ProjectSummary>>('/study/projects?limit=100',{signal:controller.signal}).then(result=>{
          if (epoch.current===version) setProjects(result.items);
        }).catch(()=>{});
      } catch(caught) {if(!isCancelled(caught)&&epoch.current===version){setError(caught);setLoading(false);}}
    }
    void load();
    return () => {
      controller.abort();epoch.current++;
      const current=chatRef.current, run=activeRun.current;
      if(current?.retention==='temporary'&&run) void api(conversationPath(current)+'/runs/'+encodeURIComponent(run)+'/cancel',{method:'POST'}).catch(()=>{});
      streamAbort.current?.abort();activeRun.current=undefined;
    };
  },[incomingKey]);

  useEffect(()=>{
    if(!recovering||!chat||chat.retention!=='saved')return;
    const controller=new AbortController(),version=epoch.current;
    let timer:ReturnType<typeof setTimeout>|undefined;
    async function poll(){
      const current=chatRef.current,run=activeRun.current;
      if(!current||!run)return;
      try{
        const result=await api<ConversationRun>(conversationPath(current)+'/runs/'+encodeURIComponent(run),{signal:controller.signal});
        if(version!==epoch.current)return;
        if(result.conversation)accept(result.conversation);
        setPartial(result.partial_text??'');
        if(result.state==='running'){timer=setTimeout(()=>void poll(),750);return;}
        await refreshMessages(result.conversation??current,version);
        const draft=await api<Draft>(conversationPath(current)+'/draft',{signal:controller.signal});
        if(version!==epoch.current)return;
        setText(draft.text);setRefs(draft.content_refs);persisted.current=signature(draft.text,draft.content_refs);
        activeRun.current=undefined;setBusy(false);setRecovering(false);
        setStatus(result.state==='completed'?'Saved':result.state==='cancelled'?'Stopped. Your draft is retained.':'Response did not finish. Your draft is retained.');
        if(result.error)setError(new ApiError(result.error.message,409,result.error.code,result.error.retryable));
        changed();
      }catch(caught){if(version===epoch.current&&!isCancelled(caught)){setError(caught);setBusy(false);setRecovering(false);}}
    }
    void poll();
    return()=>{controller.abort();if(timer)clearTimeout(timer);};
  },[recovering,chat?.identity.id]);

  useEffect(()=>{if(confirmDelete)dialog.current?.showModal();},[confirmDelete]);
  useEffect(()=>{
    if(loading||busy||!chat||chat.lifecycle!=='active')return;
    const value=signature(text,refs);
    if(value===persisted.current)return;
    const version=epoch.current;
    const timer=setTimeout(()=>{
      draftWrite.current=draftWrite.current.then(async()=>{
        const current=chatRef.current;
        if(!current||epoch.current!==version)return;
        try {
          const saved=await api<Draft>(conversationPath(current)+'/draft',{method:'PUT',body:{expected_revision:current.revision,text,content_refs:refs},headers:{'Idempotency-Key':crypto.randomUUID()}});
          if(epoch.current!==version)return;
          persisted.current=value;accept({...current,revision:saved.conversation_revision});setStatus(current.retention==='saved'?'Draft saved':'Temporary draft');
        }catch(caught){if(epoch.current===version)setError(caught);}
      });
    },400);
    return()=>clearTimeout(timer);
  },[text,refs,loading,busy,chat?.revision,chat?.lifecycle]);

  useEffect(()=>{
    const intent=props.passageIntent;
    if(!intent||loading||!chat||consumed.current.has('passage:'+intent.id))return;
    if(refs.length>=20||text.length+intent.text.length+2>16000){setError(new ApiError('Make room in the draft before using this passage.',422,'draft_limit'));return;}
    consumed.current.add('passage:'+intent.id);
    setText(previous=>previous+(previous?'\n\n':'')+intent.text);
    setRefs(previous=>previous.some(ref=>JSON.stringify(ref)===JSON.stringify(intent.reference))?previous:[...previous,intent.reference]);
    props.onPassageIntentConsumed?.(intent.id);
  },[props.passageIntent,loading,chat?.identity.id]);

  useEffect(()=>{
    const intent=props.sendIntent;
    if(!intent||loading||!chat||busy||consumed.current.has('send:'+intent.request_id))return;
    consumed.current.add('send:'+intent.request_id);
    setText(intent.text);props.onSendIntentConsumed?.(intent.request_id);
    void send(intent.text,intent.request_id);
  },[props.sendIntent,loading,chat?.identity.id]);

  async function refreshMessages(current: ConversationSummary,version=epoch.current) {
    const page=await api<PageResult<Message>>(conversationPath(current)+'/messages');
    if(epoch.current===version){setMessages(page.items);setCursor(page.next_cursor);}
  }
  async function flushDraft() {
    const version=epoch.current;
    await draftWrite.current;
    const current=chatRef.current;
    if(!current||version!==epoch.current)return;
    const draftText=textRef.current,draftRefs=refsRef.current,value=signature(draftText,draftRefs);
    if(value===persisted.current)return current;
    const draft=await api<Draft>(conversationPath(current)+'/draft',{method:'PUT',
      body:{expected_revision:current.revision,text:draftText,content_refs:draftRefs},headers:{'Idempotency-Key':crypto.randomUUID()}});
    if(version!==epoch.current)return;
    const updated={...current,revision:draft.conversation_revision};
    persisted.current=value;accept(updated);return updated;
  }
  async function send(value=textRef.current,requestId:string=crypto.randomUUID()) {
    if(!value.trim()||busy||!chatRef.current)return;
    const version=epoch.current,controller=new AbortController();streamAbort.current=controller;
    setBusy(true);setError(undefined);setPartial('');setStatus('Sending');
    await draftWrite.current;
    const current=chatRef.current;
    if(!current||version!==epoch.current)return;
    let terminal=false,watching=false;
    try {
      await sendConversation(current,{text:value,request_id:requestId,expected_revision:current.revision,teaching_style:style,content_refs:refsRef.current},event=>{
        if(epoch.current!==version)return;
        activeRun.current=event.run_id;
        visibleRun.current=event.run_id;
        if(event.payload.conversation)accept(event.payload.conversation);
        if(event.type==='delta')setPartial(previous=>previous+(event.payload.text??''));
        if(event.type==='started')setStatus('Responding');
        if(event.type==='retrieval-failed')setStatus(event.payload.message??'Sources were unavailable');
        if(['completed','error','cancelled'].includes(event.type)) {
          terminal=true;activeRun.current=undefined;
          if(event.type==='completed') {
            setStatus('Saved');
            if(textRef.current===value){setText('');setRefs([]);persisted.current=signature('',[]);}
            if(current.retention==='saved')changed();
          }else{
            setStatus(event.type==='cancelled'?'Stopped. Your draft is retained.':'Response did not finish. Your draft is retained.');
            if(event.type==='error')setError(new ApiError(event.payload.message??'Retry this request.',409,event.payload.code??'response_failed',event.payload.retryable));
          }
        }
      },controller.signal);
      if(!terminal&&!controller.signal.aborted)throw new ApiError('The response was interrupted. Your draft is retained.',0,'response_interrupted',true);
      if(epoch.current===version)await refreshMessages(chatRef.current??current,version);
    }catch(caught){if(epoch.current===version&&!isCancelled(caught)){setError(caught);if(current.retention==='saved'&&activeRun.current&&!terminal){watching=true;setRecovering(true);setStatus('Checking running response');}}}
    finally{if(epoch.current===version){if(!watching){setBusy(false);activeRun.current=undefined;}streamAbort.current=null;}}
  }
  async function stop() {
    const current=chatRef.current,run=activeRun.current;
    if(!current||!run)return;
    try{await api(conversationPath(current)+'/runs/'+run+'/cancel',{method:'POST'});}catch(caught){setError(caught);}
  }
  async function mutate(action:'rename'|'archive'|'restore'|'save'|'project',body:Record<string,unknown>={}) {
    const current=chatRef.current;if(!current||busy)return;
    const version=epoch.current;
    await draftWrite.current;
    const latest=chatRef.current??current;
    try {
      const path=conversationPath(latest)+(action==='rename'?'':'/'+action);
      const result=await api<ConversationSummary>(path,{method:action==='rename'?'PATCH':action==='project'?'PUT':'POST',body:{expected_revision:latest.revision,...body},headers:{'Idempotency-Key':crypto.randomUUID()}});
      if(result.retention==='saved')changed();
      if(version!==epoch.current)return;
      accept(result);callback.current.onConversation?.(result);setError(undefined);
    }catch(caught){if(version===epoch.current)setError(caught);}
  }
  async function remove() {
    const current=chatRef.current;if(!current)return;
    try{await api(conversationPath(current)+'?expected_revision='+current.revision,{method:'DELETE',headers:{'Idempotency-Key':crypto.randomUUID()}});changed();callback.current.onConversation?.(null);setChat(undefined);chatRef.current=undefined;setText('');setMessages([]);}catch(caught){setError(caught);}
    setConfirmDelete(false);dialog.current?.close();
  }
  async function fresh(temporary:boolean) {
    try{const value=await createConversation({temporary});accept(value);setLoading(false);callback.current.onConversation?.(value);}catch(caught){setError(caught);}
  }
  async function more() {
    if(!cursor||!chat)return;
    const version=epoch.current;
    try{const page=await api<PageResult<Message>>(conversationPath(chat)+'/messages?cursor='+encodeURIComponent(cursor));if(version!==epoch.current)return;setMessages(previous=>[...previous,...page.items.filter(item=>!previous.some(old=>old.id===item.id))]);setCursor(page.next_cursor);}catch(caught){if(version===epoch.current)setError(caught);}
  }

  if(loading)return <LoadingState label="Opening conversation"/>;
  if(!chat)return <section className="chat-page"><h1>Start a conversation</h1><p>Saved chats keep your discussion and draft for next time.</p><div className="actions"><Button onClick={()=>void fresh(false)}>Start saved chat</Button><Button variant="secondary" onClick={()=>void fresh(true)}>Start temporary chat</Button></div>{Boolean(error)&&<ErrorState error={error}/>}</section>;
  const disabled=busy||chat.lifecycle==='archived';
  return <section className="chat-page" aria-label="Conversation">
    <header className="chat-heading"><div><p className="chat-eyebrow">{chat.kind==='case'?'Case discussion':'Learning conversation'}</p><h1>{chat.title}</h1></div><div className="chat-tools"><Badge tone={chat.retention==='temporary'?'warning':'neutral'}>{chat.retention==='temporary'?'Temporary':chat.lifecycle==='archived'?'Archived':'Saved'}</Badge><details><summary>Manage</summary><div className="chat-management"><Input label="Conversation title" value={title} onChange={event=>setTitle(event.target.value)} maxLength={120}/><Button variant="secondary" disabled={busy||!title.trim()} onClick={()=>void mutate('rename',{title:title.trim()})}>Rename</Button>{chat.retention==='temporary'?<Button disabled={busy} onClick={()=>void mutate('save')}>Save conversation</Button>:<Button variant="ghost" disabled={busy} onClick={()=>void mutate(chat.lifecycle==='archived'?'restore':'archive')}><Archive size={16}/>{chat.lifecycle==='archived'?'Restore':'Archive'}</Button>}<Select label="Project" disabled={busy||chat.retention==='temporary'} value={chat.project_id??''} onChange={event=>void mutate('project',{project_id:event.target.value||null})}><option value="">Unassigned</option>{projects.map(project=><option key={project.id} value={project.id}>{project.title}</option>)}</Select><Button variant="danger" disabled={busy} onClick={()=>setConfirmDelete(true)}><Trash2 size={16}/>Delete conversation</Button></div></details></div></header>
    {chat.retention==='temporary'&&<Notice tone="warning">This conversation stays temporary until you choose Save. Closing Renulus discards it.</Notice>}
    {chat.lifecycle==='archived'&&<Notice>Archived conversations keep their history and draft. Restore to continue.</Notice>}
    {chat.kind==='case'&&<CaseContext conversation={chat} disabled={disabled} beforeChange={flushDraft} onChanged={value=>{accept(value);callback.current.onConversation?.(value);if(value.retention==='saved')changed();}} onStartTeaching={async teaching_case_id=>{const value=await createConversation({kind:'case',teaching_case_id,temporary:chat.retention==='temporary',project_id:chat.project_id});callback.current.onConversation?.(value);if(value.retention==='saved')changed();}}/>}
    <div className="chat-transcript" aria-label="Message history">{messages.map(message=><article className={'chat-message chat-message-'+message.role} key={message.id}><p className="chat-role">{message.role==='user'?'You':'Renulus'}</p><div className="chat-message-text">{message.content}</div>{message.content_refs?.length>0&&<div className="chat-references">{message.content_refs.map((reference,index)=><Button key={index} variant="ghost" onClick={()=>workspace.open(reference)}>Open source {index+1}</Button>)}</div>}</article>)}{cursor&&<Button variant="secondary" onClick={()=>void more()}>Load more history</Button>}{partial&&!messages.some(message=>message.run_id===visibleRun.current&&message.role==='assistant')&&<article className="chat-message chat-message-assistant"><p className="chat-role">Renulus {busy?'Â· responding':''}</p><div className="chat-message-text">{partial}</div></article>}{messages.length===0&&!partial&&<div className="chat-empty"><h2>What would you like to understand?</h2><p>{chat.kind==='case'?'Discuss a case, ask for missing information, or work through a teaching case.':'Ask a nephrology question. Choose guided teaching when you would like to work through it step by step.'}</p></div>}</div>
    {Boolean(error)&&<ErrorState error={error} title="Your draft is kept" onRetry={()=>{setError(undefined);void send();}}/>}
    <form className="chat-composer" onSubmit={(event:FormEvent)=>{event.preventDefault();void send();}}><Textarea label={chat.kind==='case'?'Your case question':'Message Renulus'} value={text} onChange={event=>setText(event.target.value)} rows={3} maxLength={16000} disabled={disabled}/>{refs.length>0&&<div className="chat-reference-chips">{refs.map((reference,index)=><span key={index}><Button variant="ghost" onClick={()=>workspace.open(reference)}>Source {index+1}</Button><IconButton label={'Remove source '+(index+1)} disabled={busy} onClick={()=>setRefs(previous=>previous.filter((_,i)=>i!==index))}><X size={14}/></IconButton></span>)}</div>}<div className="chat-composer-footer"><div className="chat-composer-options"><IconButton label="Open files workspace" onClick={()=>workspace.showSection('Files')}><Paperclip size={18}/></IconButton><Select label="Teaching" value={style} onChange={event=>setStyle(event.target.value as 'direct'|'guided')} disabled={disabled}><option value="direct">Direct</option><option value="guided">Guided</option></Select></div><span className="chat-status" role="status">{status}</span>{busy?<Button variant="secondary" onClick={()=>void stop()}><Square size={16}/>Stop</Button>:<Button type="submit" disabled={disabled||!text.trim()}><ArrowUp size={17}/>Send</Button>}</div></form>
    {chat.kind==='case'&&<CaseHandoffActions conversation={chat} question={text} disabled={disabled} prepare={flushDraft}/>}
    <dialog ref={dialog} onCancel={()=>setConfirmDelete(false)} className="chat-delete-dialog"><h2>Delete this conversation?</h2><p>Its messages and owned originals will be removed. Separately retained learning memory remains inspectable.</p><div className="actions"><Button variant="secondary" onClick={()=>{setConfirmDelete(false);dialog.current?.close();}}>Keep conversation</Button><Button variant="danger" onClick={()=>void remove()}>Delete conversation</Button></div></dialog>
  </section>;
}
