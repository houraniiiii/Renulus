import { useEffect, useRef, useState } from 'react';
import { ApiError } from '../../platform/api';
import type { ConversationSummary } from '../../platform/designC';
import { useNavigation } from '../../shell/navigation';
import { Badge, Button, ErrorState, Notice, Select, Textarea } from '../../ui';
import { startStudyAttempt } from '../attempts/start';
import { useWorkspace } from '../workspace';
import { cancelChatTestRun, readChatTestResult, readChatTestRun, startChatTest, type ChatTestResult, type ChatTestRun } from './api';

interface Props {conversation:ConversationSummary;disabled:boolean;prepare:()=>Promise<ConversationSummary|undefined>}
export function CreateChatTest({conversation,disabled,prepare}:Props){
  const workspace=useWorkspace(),navigation=useNavigation();
  const [open,setOpen]=useState(false),[count,setCount]=useState<5|10|20>(5),[instruction,setInstruction]=useState('');
  const [run,setRun]=useState<ChatTestRun>(),[result,setResult]=useState<ChatTestResult>();
  const [working,setWorking]=useState(false),[error,setError]=useState<unknown>();
  const pending=useRef<{conversation:ConversationSummary;body:{request_id:string;expected_revision:number;count:5|10|20;instruction:string}}|undefined>(undefined);
  const mounted=useRef(true),currentRun=useRef<ChatTestRun|undefined>(undefined),creating=useRef(false);
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;const value=currentRun.current;if(value&&['queued','running'].includes(value.state))void cancelChatTestRun(value.run_id).catch(()=>{});};},[]);
  function accept(value:ChatTestRun){currentRun.current=value;setRun(value);}
  useEffect(()=>{
    if(!run||!['queued','running'].includes(run.state))return;
    const controller=new AbortController();let timer:ReturnType<typeof setTimeout>|undefined;
    async function poll(){
      try{
        const value=await readChatTestRun(run!.run_id,controller.signal);
        if(controller.signal.aborted)return;accept(value);
        if(value.state==='published'){
          const saved=await readChatTestResult(value.run_id,controller.signal);
          if(controller.signal.aborted)return;setResult(saved);setError(undefined);
          window.dispatchEvent(new Event('renulus:records-changed'));
        }else if(value.state==='failed'){
          pending.current=undefined;await readChatTestResult(value.run_id,controller.signal);
        }else if(value.state!=='cancelled')timer=setTimeout(()=>void poll(),600);
      }catch(caught){if(!controller.signal.aborted)setError(caught);}
    }
    void poll();return()=>{controller.abort();if(timer)clearTimeout(timer);};
  },[run?.run_id]);
  async function create(){
    if(creating.current||disabled||!workspace.permitted)return;
    creating.current=true;setWorking(true);setError(undefined);
    try{
      if(!pending.current){const latest=await prepare();if(!latest)return;pending.current={conversation:latest,body:{request_id:crypto.randomUUID(),expected_revision:latest.revision,count,instruction}};}
      const value=await startChatTest(pending.current.conversation,pending.current.body);
      if(!mounted.current){if(['queued','running'].includes(value.state))void cancelChatTestRun(value.run_id).catch(()=>{});return;}
      accept(value);setResult(undefined);
    }catch(caught){if(mounted.current){if(caught instanceof ApiError&&!caught.retryable&&caught.status>=400&&caught.status<500)pending.current=undefined;setError(caught);}}
    finally{creating.current=false;if(mounted.current)setWorking(false);}
  }
  async function stop(){if(!run)return;try{const value=await cancelChatTestRun(run.run_id);if(mounted.current){accept(value);pending.current=undefined;setError(undefined);}}catch(caught){if(mounted.current)setError(caught);}}
  async function readResult(){if(!run)return;setWorking(true);try{const saved=await readChatTestResult(run.run_id);if(mounted.current){setResult(saved);setError(undefined);}}catch(caught){if(mounted.current)setError(caught);}finally{if(mounted.current)setWorking(false);}}
  async function study(){
    if(!result||working||!workspace.permitted)return;setWorking(true);setError(undefined);
    try{const descriptor=result.study_start;const attempt=await startStudyAttempt(descriptor.version.id,descriptor.idempotency_key);if(mounted.current)navigation.navigate('attempts',{freshStudy:true,payload:{attempt_id:attempt.id}});}
    catch(caught){if(mounted.current)setError(caught);}finally{if(mounted.current)setWorking(false);}
  }
  const active=Boolean(run&&['queued','running'].includes(run.state)),frozen=working||active||Boolean(pending.current);
  return <section className="chat-test-builder" aria-label="Create test from conversation">
    <Button variant="ghost" disabled={disabled||!workspace.permitted} onClick={()=>setOpen(value=>!value)}>Create test from conversation</Button>
    {open&&<div className="chat-test-review">
      <h2>Turn this discussion into practice</h2><p>Renulus creates independent fictional questions, then checks that private source details were removed before saving the test. It uses sent messages and the visible Case context.</p>
      <div className="chat-test-options"><Select label="Question count" value={count} disabled={frozen||disabled} onChange={event=>setCount(Number(event.target.value) as 5|10|20)}><option value={5}>5 questions</option><option value={10}>10 questions</option><option value={20}>20 questions</option></Select>
      <Textarea label="Learning focus (optional)" maxLength={2000} rows={2} disabled={frozen||disabled} value={instruction} onChange={event=>setInstruction(event.target.value)}/></div>
      {!result&&!active&&<Button busy={working} disabled={disabled||!workspace.permitted} onClick={()=>void create()}>{pending.current?'Retry same creation request':'Create fictional test'}</Button>}
      {active&&<Notice><p>Preparing fictional questions and checking privacy. The source stays in memory for this request.</p><Button variant="secondary" onClick={()=>void stop()}>Cancel test creation</Button></Notice>}
      {run?.state==='cancelled'&&<Notice>Test creation was stopped.</Notice>}
      {run?.state==='published'&&!result&&<Button variant="secondary" busy={working} onClick={()=>void readResult()}>Read saved test</Button>}
      {result&&<div className="chat-created-test"><Badge tone="neutral">Saved personal practice</Badge><h3>{result.item_count} fictional questions</h3><p>Study is untimed. Generated practice stays separate from reviewed-bank performance.</p><div className="actions"><Button disabled={working||!workspace.permitted} onClick={()=>void study()} busy={working}>Start Study</Button><Button variant="secondary" onClick={()=>workspace.open({target:{type:'saved_test_version',id:result.version_id}})}>Open saved test</Button><Button variant="ghost" disabled={working} onClick={()=>{pending.current=undefined;setRun(undefined);currentRun.current=undefined;setResult(undefined);}}>Create another set</Button></div></div>}
      {Boolean(error)&&<ErrorState error={error} title={result?'The saved test is kept':'Test creation needs attention'}/>}
    </div>}
  </section>;
}
