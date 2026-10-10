// SPDX-License-Identifier: MIT
import { useEffect, useRef, useState } from 'react';
import { api } from '../../platform/api';
import type { ContextScope } from '../../platform/contracts';
import { studyHelpHeaders, type ConversationSummary, type StudyHelpContext } from '../../platform/designC';
import { useNavigation } from '../../shell/navigation';
import { Button, ErrorState } from '../../ui';
import { conversationPath } from './api';

interface Handoff {id:string;case_handoff_id:string;case_id:string;question:string;scope:ContextScope;conversation:ConversationSummary['identity'];retention:ConversationSummary['retention']}

export function CaseHandoffActions({conversation,question,disabled,prepare,studyHelpContext}:{
  conversation:ConversationSummary;question:string;disabled:boolean;prepare:()=>Promise<ConversationSummary|undefined>;
  studyHelpContext?:StudyHelpContext;
}) {
  const navigation=useNavigation();
  const [working,setWorking]=useState(false);
  const [error,setError]=useState<unknown>();
  const current=useRef(conversation.identity.id);
  useEffect(()=>{current.current=conversation.identity.id;setWorking(false);setError(undefined);return()=>{current.current='';};},[conversation.identity.id]);
  async function handoff(target:'explain'|'generated-practice'){
    if(disabled||working)return;
    const identifier=conversation.identity.id;
    setWorking(true);setError(undefined);
    try{
      const latest=await prepare();
      if(!latest||current.current!==identifier)return;
      const headers=studyHelpHeaders(studyHelpContext);
      const context=await api<{revision:number}>(conversationPath(latest)+'/context',{headers});
      const ticket=await api<Handoff>(conversationPath(latest)+'/handoff',{method:'POST',body:{
        expected_revision:latest.revision,case_revision:context.revision,target,question:target==='explain'?question.trim():'',
      },headers});
      if(current.current!==identifier){void api('/cases/handoffs/'+encodeURIComponent(ticket.id),{method:'DELETE'}).catch(()=>{});return;}
      navigation.navigate(target==='explain'?'learn':'assessment',{scope:ticket.scope,payload:{...ticket,...(studyHelpContext?{studyHelpContext:{...studyHelpContext}}:{})}});
    }catch(caught){if(current.current===identifier)setError(caught);}
    finally{if(current.current===identifier)setWorking(false);}
  }
  return <div className="chat-case-handoff">
    <div className="actions"><Button variant="ghost" disabled={disabled||working||!question.trim()||question.trim().length>12000} onClick={()=>void handoff('explain')}>Explore in Learn</Button>
      <Button variant="ghost" disabled={disabled||working} onClick={()=>void handoff('generated-practice')}>Practise from this case</Button></div>
    <p className="muted">{conversation.retention==='saved'?'The completed explanation or practice receipt stays in this Case.':'Explanations and practice stay temporary.'} Practice questions and scores remain separate.</p>
    {Boolean(error)&&<ErrorState error={error} title="The Case handoff could not start"/>}
  </div>;
}
