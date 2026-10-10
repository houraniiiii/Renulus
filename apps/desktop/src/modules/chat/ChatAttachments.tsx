import { useEffect, useRef, useState } from 'react';
import { ApiError, isCancelled } from '../../platform/api';
import type { ConversationSummary, StudyHelpContext } from '../../platform/designC';
import { Button, ErrorState, Input, LoadingState, Notice } from '../../ui';
import { useWorkspace } from '../workspace';
import { attachmentInventory, uploadAttachment, type AttachmentCommand, type AttachmentIntent, type AttachmentInventory } from './attachments';

interface Props {
  conversation:ConversationSummary;open:boolean;onOpenChange:(open:boolean)=>void;disabled?:boolean;
  intent?:AttachmentIntent;onConsumed?:(id:string)=>void;beforeAttach:()=>Promise<ConversationSummary|undefined>;
  onChanged:(conversation:ConversationSummary)=>void;
  studyHelpContext?:StudyHelpContext;
}
export function ChatAttachments(props:Props){
  const workspace=useWorkspace();
  const [file,setFile]=useState<File>();
  const [title,setTitle]=useState(''),[owner,setOwner]=useState('User'),[edition,setEdition]=useState('');
  const [permission,setPermission]=useState(''),[display,setDisplay]=useState(false),[cache,setCache]=useState(false);
  const [modelInput,setModelInput]=useState(false),[derive,setDerive]=useState(false);
  const [inventory,setInventory]=useState<AttachmentInventory>(),[loading,setLoading]=useState(false),[busy,setBusy]=useState(false);
  const [error,setError]=useState<unknown>(),[message,setMessage]=useState('');
  const key=useRef<string>(crypto.randomUUID()),consumed=useRef(new Set<string>());
  const pending=useRef<{file:File;command:AttachmentCommand;studyHelpContext?:StudyHelpContext}|undefined>(undefined);
  const mounted=useRef(true);
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
  function select(value:File,requestId:string=crypto.randomUUID()){
    setFile(value);setTitle(value.name);key.current=requestId;pending.current=undefined;
    setDisplay(false);setCache(false);setModelInput(false);setDerive(false);setPermission('');setError(undefined);setMessage('');
  }
  useEffect(()=>{
    const intent=props.intent;
    if(!intent||consumed.current.has(intent.request_id))return;
    consumed.current.add(intent.request_id);select(intent.file,intent.request_id);
    props.onOpenChange(true);props.onConsumed?.(intent.request_id);
  },[props.intent]);
  useEffect(()=>{
    if(!props.open||!workspace.permitted)return;
    const controller=new AbortController();setLoading(true);
    attachmentInventory(props.conversation,controller.signal,props.studyHelpContext).then(value=>{setInventory(value);setError(undefined);})
      .catch(caught=>{if(!isCancelled(caught))setError(caught);}).finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return()=>controller.abort();
  },[props.open,props.conversation.identity.id,props.conversation.revision,workspace.permitted,JSON.stringify(props.studyHelpContext)]);
  async function attach(){
    if(!file||busy||props.disabled||!workspace.permitted)return;
    setBusy(true);setError(undefined);
    try{
      if(!pending.current){
        const studyHelpContext=props.studyHelpContext?{...props.studyHelpContext}:undefined;
        await props.beforeAttach();
        const live=await attachmentInventory(props.conversation,undefined,studyHelpContext);
        if(live.conversation.type!==props.conversation.identity.type||live.conversation.id!==props.conversation.identity.id
          ||!Number.isInteger(live.policy_revision)||!Number.isInteger(live.context_epoch))
          throw new ApiError('Reopen this conversation before attaching a file.',409,'attachment_context_changed');
        pending.current={file,studyHelpContext,command:{conversation:live.conversation,expected_conversation_revision:live.conversation_revision,
          expected_policy_revision:live.policy_revision,expected_context_epoch:live.context_epoch,idempotency_key:key.current,
          filename:file.name,title:title.trim(),rights:{display,cache,index:false,embedding:false,model_input:modelInput,derivation:derive,
            evaluation:false,redistribution:false,licence:'user-supplied permission',permission_reference:permission.trim(),attribution:owner.trim()},
          metadata:{source_id:'R02',source_owner:owner.trim()||'User',access_class:'user-owned',edition:edition.trim()||null}}};
      }
      const context=pending.current.studyHelpContext;
      const receipt=await uploadAttachment(pending.current.file,pending.current.command,undefined,context);
      if(!mounted.current)return;
      const latest={...props.conversation,revision:receipt.conversation_revision};
      props.onChanged(latest);
      pending.current=undefined;setFile(undefined);setMessage(receipt.retention==='temporary'?'Attached temporarily. No original was saved.':'Attached to this saved conversation.');
      void attachmentInventory(latest,undefined,context).then(value=>{if(mounted.current)setInventory(value);}).catch(caught=>{if(mounted.current)setError(caught);});
    }catch(caught){
      if(!mounted.current)return;
      if(caught instanceof ApiError&&!caught.retryable&&caught.status>=400&&caught.status<500){pending.current=undefined;key.current=crypto.randomUUID();}
      setError(caught);
    }finally{if(mounted.current)setBusy(false);}
  }
  if(!props.open)return null;
  const maxMiB=props.conversation.retention==='temporary'?10:64;
  const problem=file&&(file.size===0?'This file is empty. Choose another file.':file.size>maxMiB*1024*1024?'Choose a file under '+maxMiB+' MiB.':undefined);
  const frozen=busy||Boolean(pending.current);
  const blocked=props.disabled||!workspace.permitted;
  return <section className="chat-attachment-review" aria-label="Attachments">
    <div className="chat-review-heading"><div><h2>Conversation files</h2><p>Review the selected original and its permissions before attaching.</p></div><Button variant="ghost" disabled={busy} onClick={()=>props.onOpenChange(false)}>Close files</Button></div>
    {!workspace.permitted?<Notice>Files are unavailable during an active Test.</Notice>:<>
      <Input label="Attach files to chat" type="file" accept=".pdf,.txt,.md,.csv,.html,.htm,.xml,.png,.jpg,.jpeg,.tif,.tiff,.docx,.pptx,.xlsx" disabled={blocked||frozen} onChange={event=>{const value=event.target.files?.[0];if(value)select(value);event.target.value='';}}/>
      {file&&<div className="chat-attachment-fields">
        <p className="chat-selected-file">{file.name} <span>{(file.size/1024).toFixed(1)} KiB · {props.conversation.retention==='temporary'?'temporary original':'saved original'}</span></p>
        {problem&&<Notice tone="warning">{problem}</Notice>}
        <Input label="File title" value={title} maxLength={500} disabled={frozen||blocked} onChange={event=>setTitle(event.target.value)}/>
        <div className="chat-file-metadata"><Input label="Source owner or author" value={owner} disabled={frozen||blocked} onChange={event=>setOwner(event.target.value)}/><Input label="Edition (optional)" value={edition} disabled={frozen||blocked} onChange={event=>setEdition(event.target.value)}/></div>
        <fieldset disabled={frozen||blocked}><legend>Allowed use</legend>
          <label><input type="checkbox" checked={display} onChange={event=>setDisplay(event.target.checked)}/> Display this file in Renulus</label>
          <label><input type="checkbox" checked={cache} onChange={event=>setCache(event.target.checked)}/> Keep a local original when this conversation is saved</label>
          <label><input type="checkbox" checked={modelInput} onChange={event=>setModelInput(event.target.checked)}/> Send selected content to my learning model</label>
          <label><input type="checkbox" checked={derive} onChange={event=>setDerive(event.target.checked)}/> Create learning material from selected content</label>
        </fieldset>
        <Input label="Permission or licence" hint="Describe your permission to use this original." value={permission} maxLength={1000} disabled={frozen||blocked} onChange={event=>setPermission(event.target.value)}/>
        <div className="actions"><Button busy={busy} disabled={blocked||Boolean(problem)||!title.trim()||!display||!permission.trim()||(props.conversation.retention==='saved'&&!cache)} onClick={()=>void attach()}>{pending.current?'Retry same attachment':'Confirm attach'}</Button><Button variant="ghost" disabled={busy} onClick={()=>{setFile(undefined);pending.current=undefined;setError(undefined);}}>Discard selection</Button></div>
      </div>}
      {Boolean(error)&&<ErrorState error={error} title="File needs attention"/>}{message&&<Notice>{message}</Notice>}
      {loading?<LoadingState label="Reading conversation files"/>:inventory?.items.map(item=><div className="chat-attached-file" key={item.id}><div><strong>{item.title}</strong><p>{item.retention==='temporary'?'Temporary':'Saved'} original</p></div><Button variant="secondary" disabled={!item.access?.allowed} onClick={()=>workspace.open(item.reference)}>Open file</Button></div>)}
    </>}
  </section>;
}
