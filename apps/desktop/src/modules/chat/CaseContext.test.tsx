// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ConversationSummary, StudyHelpContext } from '../../platform/designC';
import type { AttachmentPreview, CaseCapabilities, CaseSession, TeachingSummary } from '../cases/types';
import { ApiError } from '../../platform/api';
import { CaseContext } from './CaseContext';

const calls=vi.hoisted(()=>({api:vi.fn()}));
vi.mock('../../platform/api',async()=>({...await vi.importActual('../../platform/api'),api:calls.api}));
const chat:ConversationSummary={identity:{type:'case',id:'saved-case'},kind:'case',retention:'saved',lifecycle:'active',revision:2,title:'Fictional Case',project_id:null,created_at:'2026-10-10T00:00:00Z',updated_at:'2026-10-10T00:00:00Z'};
const session:CaseSession={id:'saved-case',kind:'daily',title:chat.title,text:'',revision:4,scope:{kind:'saved-case',entity_id:'saved-case'},saved:true,dirty:false,saved_at:chat.created_at,created_at:chat.created_at,updated_at:chat.updated_at,active_run_id:null,messages:[],teaching:null,attachments:[]};
const capabilities:CaseCapabilities={inputs:{text:{supported:true},image:{supported:false},pdf:{supported:true}},discussion:{adapter_installed:true,scope:'temporary-case'},teaching:{content_installed:true},handoffs:{explain:'available','generated-practice':'available'},memory_capture:false,extraction:{supported:true,max_bytes:10000,formats:['.pdf'],scope:'temporary-case'}};
const teachingCase:TeachingSummary={id:'synthetic-teaching',version:2,title:'Synthetic teaching case',summary:'Synthetic installed case',topic_id:'renal',currency:{kind:'case',id:'synthetic-teaching',version:2,status:'unavailable',needs_re_review:null,annotations:[],annotation_count:0,truncated:false}};
const pinned:CaseSession={...session,kind:'teaching',teaching:{id:teachingCase.id,version:1,topic_id:'renal',stage_count:2,revealed_count:1,debriefed:false,stages:[{id:'first',narrative:'Retained pinned first stage',prompts:[]}],review:{},license:'CC BY 4.0',synthetic:true,currency:teachingCase.currency}};
const readFailure=(message:string)=>new ApiError(message,503,'synthetic_read_failed',true);
function deferred<T>(){
  let resolve!:(value:T)=>void;
  const promise=new Promise<T>(done=>{resolve=done;});
  return {promise,resolve};
}
function mountContext(){
  const before=vi.fn(async()=>chat),changed=vi.fn(),start=vi.fn(async()=>{});
  const props={conversation:chat,disabled:false,beforeChange:before,onChanged:changed,onStartTeaching:start};
  return {...render(<CaseContext {...props}/>),props,before,changed,start};
}
function retryRead(title:string){
  const alert=screen.getByRole('heading',{name:title}).closest('[role="alert"]')! as HTMLElement;
  fireEvent.click(within(alert).getByRole('button',{name:'Try again'}));
}
afterEach(()=>cleanup());

describe('Case context inside Chat',()=>{
  it('keeps a failed context edit and saves through both owner revisions without sending',async()=>{
    const context:StudyHelpContext={attempt_id:'case-study',item_id:'study-item',version_id:'study-version',draft_revision:1,policy_revision:1,kind:'chat'};
    calls.api.mockReset();let saved=false,fail=true;
    calls.api.mockImplementation(async(path:string,options?:{method?:string;body?:unknown})=>{
      if(path==='/cases/capabilities')return {};
      if(path==='/cases/teaching')return {cases:[]};
      if(options?.method==='PATCH'){
        if(fail)throw new ApiError('Fictional save unavailable',503,'case_save_failed',true);
        saved=true;return {conversation:{...chat,revision:8},case_revision:5};
      }
      return {...session,text:saved?'Revised fictional context':'',revision:saved?5:4};
    });
    const changed=vi.fn(),before=vi.fn(async()=>({...chat,revision:7}));
    render(<CaseContext studyHelpContext={context} conversation={chat} disabled={false} beforeChange={before} onChanged={changed} onStartTeaching={vi.fn()}/>);
    fireEvent.click(await screen.findByRole('button',{name:'Edit case context'}));
    fireEvent.change(screen.getByLabelText('Case context text'),{target:{value:'Revised fictional context'}});
    fireEvent.click(screen.getByRole('button',{name:'Save case context'}));
    expect(await screen.findByText('Fictional save unavailable')).toBeTruthy();
    expect((screen.getByLabelText('Case context text') as HTMLTextAreaElement).value).toBe('Revised fictional context');
    expect(changed).not.toHaveBeenCalled();
    fail=false;
    fireEvent.click(screen.getByRole('button',{name:'Save case context'}));
    await waitFor(()=>expect(changed).toHaveBeenCalledWith({...chat,revision:8}));
    const [,options]=calls.api.mock.calls.find(([,options])=>options?.method==='PATCH')!;
    expect(options.body).toEqual({expected_revision:7,case_revision:4,text:'Revised fictional context'});
    expect(calls.api.mock.calls.every(([,options])=>options?.headers?.['X-Renulus-Study-Context']===JSON.stringify(context))).toBe(true);
    expect(calls.api.mock.calls.some(([path])=>path.endsWith('/messages'))).toBe(false);
  });

  it('reveals only server-provided teaching stages and keeps the pin visible',async()=>{
    calls.api.mockReset();let revealed=false;
    calls.api.mockImplementation(async(path:string,options?:{method?:string})=>{
      if(path==='/cases/capabilities')return {};
      if(path==='/cases/teaching')return {cases:[]};
      if(options?.method==='POST'){revealed=true;return {conversation:{...chat,revision:3},case_revision:5};}
      return {...session,kind:'teaching',teaching:{id:'fictional-teaching',version:1,stage_count:2,revealed_count:revealed?2:1,debriefed:false,currency:{status:'unavailable'},stages:[{id:'first',narrative:'First fictional stage',prompts:[]},...(revealed?[{id:'second',narrative:'Additional fictional information',prompts:[]}]:[])]}};
    });
    render(<CaseContext conversation={chat} disabled={false} beforeChange={async()=>chat} onChanged={vi.fn()} onStartTeaching={vi.fn()}/>);
    expect(await screen.findByText('First fictional stage')).toBeTruthy();
    expect(screen.getByText(/Pinned version 1/)).toBeTruthy();
    expect(screen.queryByText('Additional fictional information')).toBeNull();
    fireEvent.click(screen.getByRole('button',{name:'Reveal next stage'}));
    expect(await screen.findByText('Additional fictional information')).toBeTruthy();
    expect(screen.getByRole('button',{name:'Reveal debrief'})).toBeTruthy();
  });

  it('recovers a failed capability read without claiming unsupported extraction or losing a context edit',async()=>{
    calls.api.mockReset();let failed=true;
    calls.api.mockImplementation(async(path:string)=>{
      if(path==='/cases/capabilities'){if(failed)throw readFailure('Capabilities temporarily offline');return capabilities;}
      if(path==='/cases/teaching')return {cases:[teachingCase]};
      return session;
    });
    const {before,changed,start}=mountContext();
    fireEvent.click(await screen.findByRole('button',{name:'Edit case context'}));
    fireEvent.change(screen.getByLabelText('Case context text'),{target:{value:'Keep my unsaved fictional details'}});
    expect(await screen.findByRole('heading',{name:'Case attachment options could not be loaded'})).toBeTruthy();
    expect(screen.queryByText(/Temporary attachment extraction is unavailable/)).toBeNull();
    expect(screen.queryByLabelText('PDF or image for text extraction')).toBeNull();
    failed=false;retryRead('Case attachment options could not be loaded');
    expect(await screen.findByLabelText('PDF or image for text extraction')).toBeTruthy();
    expect((screen.getByLabelText('Case context text') as HTMLTextAreaElement).value).toBe('Keep my unsaved fictional details');
    expect(screen.queryByRole('alert')).toBeNull();
    expect(before).not.toHaveBeenCalled();expect(changed).not.toHaveBeenCalled();expect(start).not.toHaveBeenCalled();
    expect(calls.api.mock.calls.every(([,options])=>!options?.method)).toBe(true);
  });

  it('recovers a failed teaching list as a read, and starts only after explicit selection and action',async()=>{
    calls.api.mockReset();let failed=true;
    calls.api.mockImplementation(async(path:string)=>{
      if(path==='/cases/capabilities')return capabilities;
      if(path==='/cases/teaching'){if(failed)throw readFailure('Teaching list temporarily offline');return {cases:[teachingCase]};}
      return session;
    });
    const {start}=mountContext();
    expect(await screen.findByRole('heading',{name:'Teaching cases could not be loaded'})).toBeTruthy();
    expect(screen.queryByText('No installed teaching cases are available.')).toBeNull();
    failed=false;retryRead('Teaching cases could not be loaded');
    await screen.findByText('Start an installed teaching case');
    fireEvent.click(screen.getByText('Start an installed teaching case'));
    fireEvent.change(screen.getByLabelText('Teaching case'),{target:{value:teachingCase.id}});
    expect(start).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button',{name:'Start teaching conversation'}));
    await waitFor(()=>expect(start).toHaveBeenCalledExactlyOnceWith(teachingCase.id));
  });

  it('reloads failed companion reads when retrying the context read',async()=>{
    calls.api.mockReset();let failed=true;
    calls.api.mockImplementation(async(path:string)=>{
      if(failed)throw readFailure('Context and companion reads offline');
      if(path==='/cases/capabilities')return capabilities;
      if(path==='/cases/teaching')return {cases:[teachingCase]};
      return session;
    });
    mountContext();
    // The initial context error is inside the collapsible Case panel.
    fireEvent.click(screen.getByText('Case context'));
    await screen.findAllByText('Context and companion reads offline');
    failed=false;
    const contextAlert=screen.getAllByRole('alert').find(alert=>within(alert).queryByRole('heading',{name:/Case context could not be/}))!;
    fireEvent.click(within(contextAlert).getByRole('button',{name:'Try again'}));
    expect(await screen.findByLabelText('PDF or image for text extraction')).toBeTruthy();
    expect(await screen.findByText('Start an installed teaching case')).toBeTruthy();
    for(const path of ['/cases/capabilities','/cases/teaching','/conversations/case/saved-case/context']){
      expect(calls.api.mock.calls.filter(([called])=>called===path)).toHaveLength(2);
    }
  });

  it('distinguishes pending and confirmed unsupported/empty reads from failures',async()=>{
    calls.api.mockReset();const capabilityRead=deferred<CaseCapabilities>(),teachingRead=deferred<{cases:TeachingSummary[]}>();
    calls.api.mockImplementation((path:string)=>path==='/cases/capabilities'?capabilityRead.promise:path==='/cases/teaching'?teachingRead.promise:Promise.resolve(session));
    mountContext();
    await screen.findByRole('button',{name:'Edit case context'});
    expect(screen.getByRole('status',{name:'Loading case attachment options'})).toBeTruthy();
    expect(screen.getByRole('status',{name:'Loading teaching cases'})).toBeTruthy();
    expect(screen.queryByText(/Temporary attachment extraction is unavailable/)).toBeNull();
    expect(screen.queryByText('No installed teaching cases are available.')).toBeNull();
    await act(async()=>{capabilityRead.resolve({...capabilities,extraction:{...capabilities.extraction!,supported:false}});teachingRead.resolve({cases:[]});});
    expect(await screen.findByText(/Temporary attachment extraction is unavailable/)).toBeTruthy();
    expect(screen.getByText('No installed teaching cases are available.')).toBeTruthy();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('retains the original teaching pin and revealed stage during metadata recovery',async()=>{
    calls.api.mockReset();let failed=true;
    calls.api.mockImplementation(async(path:string)=>{
      if(path==='/cases/capabilities')return capabilities;
      if(path==='/cases/teaching'){if(failed)throw readFailure('Teaching list temporarily offline');return {cases:[teachingCase]};}
      return pinned;
    });
    const {before,changed,start}=mountContext();
    expect(await screen.findByText('Retained pinned first stage')).toBeTruthy();
    expect(await screen.findByRole('heading',{name:'Teaching cases could not be loaded'})).toBeTruthy();
    failed=false;retryRead('Teaching cases could not be loaded');
    await waitFor(()=>expect(screen.queryByRole('alert')).toBeNull());
    expect(screen.getByText(/Pinned version 1/)).toBeTruthy();
    expect(screen.getByText('Retained pinned first stage')).toBeTruthy();
    expect(screen.queryByText(/Pinned version 2/)).toBeNull();
    expect(screen.getByRole('button',{name:'Reveal next stage'})).toBeTruthy();
    expect(before).not.toHaveBeenCalled();expect(changed).not.toHaveBeenCalled();expect(start).not.toHaveBeenCalled();
    expect(calls.api.mock.calls.every(([,options])=>!options?.method)).toBe(true);
  });

  it('preserves attachment review edits, context edits and teaching selection across failed rereads and recovery',async()=>{
    calls.api.mockReset();let phase:'ready'|'failed'|'retry'='ready';
    const capabilityRead=deferred<CaseCapabilities>(),teachingRead=deferred<{cases:TeachingSummary[]}>();
    const preview:AttachmentPreview={id:'preview-one',case_id:session.id,revision:session.revision,scope:{kind:'temporary-case',entity_id:session.id},state:'reading',filename:'synthetic.pdf',title:'Synthetic preview',text:'',ocr:{},error:null};
    calls.api.mockImplementation(async(path:string)=>{
      if(path==='/cases/capabilities'){
        if(phase==='failed')throw readFailure('Capability refresh failed');
        return phase==='retry'?capabilityRead.promise:capabilities;
      }
      if(path==='/cases/teaching'){
        if(phase==='failed')throw readFailure('Teaching refresh failed');
        return phase==='retry'?teachingRead.promise:{cases:[teachingCase]};
      }
      if(path.endsWith('/prepare'))return preview;
      if(path.endsWith('/extract'))return {...preview,state:'ready',text:'Extracted synthetic words'};
      return session;
    });
    const {rerender,props,start,changed}=mountContext();
    fireEvent.change(await screen.findByLabelText('PDF or image for text extraction'),{target:{files:[new File(['synthetic bytes'],'synthetic.pdf',{type:'application/pdf'})]}});
    fireEvent.change(await screen.findByLabelText('Review extracted text'),{target:{value:'Retain reviewed synthetic words'}});
    fireEvent.click(screen.getByRole('button',{name:'Edit case context'}));
    fireEvent.change(screen.getByLabelText('Case context text'),{target:{value:'Retain unsaved context'}});
    fireEvent.click(screen.getByText('Start an installed teaching case'));
    fireEvent.change(screen.getByLabelText('Teaching case'),{target:{value:teachingCase.id}});
    const readStart=calls.api.mock.calls.length;
    const study:StudyHelpContext={attempt_id:'study',item_id:'item',version_id:'version',draft_revision:2,policy_revision:2,kind:'chat'};
    phase='failed';rerender(<CaseContext {...props} studyHelpContext={study}/>);
    await screen.findByRole('heading',{name:'Case attachment options could not be loaded'});
    expect((screen.getByLabelText('Review extracted text') as HTMLTextAreaElement).disabled).toBe(true);
    expect((screen.getByRole('button',{name:'Start teaching conversation'}) as HTMLButtonElement).disabled).toBe(true);
    phase='retry';retryRead('Case attachment options could not be loaded');
    await screen.findByRole('status',{name:'Loading case attachment options'});
    expect((screen.getByLabelText('Review extracted text') as HTMLTextAreaElement).value).toBe('Retain reviewed synthetic words');
    expect((screen.getByLabelText('Teaching case') as HTMLSelectElement).disabled).toBe(true);
    await act(async()=>{capabilityRead.resolve(capabilities);teachingRead.resolve({cases:[teachingCase]});});
    await waitFor(()=>expect((screen.getByLabelText('Review extracted text') as HTMLTextAreaElement).disabled).toBe(false));
    expect((screen.getByLabelText('Review extracted text') as HTMLTextAreaElement).value).toBe('Retain reviewed synthetic words');
    expect((screen.getByLabelText('Case context text') as HTMLTextAreaElement).value).toBe('Retain unsaved context');
    expect((screen.getByLabelText('Teaching case') as HTMLSelectElement).value).toBe(teachingCase.id);
    expect((screen.getByRole('button',{name:'Start teaching conversation'}) as HTMLButtonElement).disabled).toBe(false);
    expect(start).not.toHaveBeenCalled();expect(changed).not.toHaveBeenCalled();
    const rereads=calls.api.mock.calls.slice(readStart);
    expect(rereads.every(([,options])=>!options?.method&&options?.headers?.['X-Renulus-Study-Context']===JSON.stringify(study))).toBe(true);
  });

  it('keeps repeated teaching read failures recoverable and refuses a selection removed by the fresh list',async()=>{
    calls.api.mockReset();let phase:'ready'|'failed'|'changed'='ready';
    calls.api.mockImplementation(async(path:string)=>{
      if(path==='/cases/capabilities')return capabilities;
      if(path==='/cases/teaching'){
        if(phase==='failed')throw readFailure('Still offline');
        return {cases:[phase==='changed'?{...teachingCase,id:'replacement',title:'Replacement case'}:teachingCase]};
      }
      return session;
    });
    const {rerender,props,start}=mountContext();
    fireEvent.click(await screen.findByText('Start an installed teaching case'));
    fireEvent.change(screen.getByLabelText('Teaching case'),{target:{value:teachingCase.id}});
    phase='failed';
    rerender(<CaseContext {...props} studyHelpContext={{attempt_id:'study',item_id:'item',version_id:'version',draft_revision:1,policy_revision:1,kind:'chat'}}/>);
    await screen.findByText('Still offline');retryRead('Teaching cases could not be loaded');
    await screen.findByText('Still offline');
    expect((screen.getByRole('button',{name:'Start teaching conversation'}) as HTMLButtonElement).disabled).toBe(true);
    phase='changed';retryRead('Teaching cases could not be loaded');
    await screen.findByRole('option',{name:'Replacement case'});
    expect((screen.getByRole('button',{name:'Start teaching conversation'}) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button',{name:'Start teaching conversation'}));
    expect(start).not.toHaveBeenCalled();
  });

  it.each(['conversation','Study context'] as const)('ignores late companion responses after changing %s',async(boundary)=>{
    calls.api.mockReset();let reads=0;
    const oldCapabilities=deferred<CaseCapabilities>(),oldTeaching=deferred<{cases:TeachingSummary[]}>();
    calls.api.mockImplementation((path:string)=>{
      if(path==='/cases/capabilities'){reads++;return reads===1?oldCapabilities.promise:Promise.resolve(capabilities);}
      if(path==='/cases/teaching')return reads===1?oldTeaching.promise:Promise.resolve({cases:[teachingCase]});
      return Promise.resolve(session);
    });
    const {rerender,props}=mountContext();
    await screen.findByRole('button',{name:'Edit case context'});
    const oldSignals=calls.api.mock.calls.filter(([path])=>path==='/cases/capabilities'||path==='/cases/teaching').map(([,options])=>options.signal as AbortSignal);
    const next=boundary==='conversation'?{conversation:{...chat,identity:{type:'case' as const,id:'other-case'}}}:{studyHelpContext:{attempt_id:'study',item_id:'item',version_id:'version',draft_revision:2,policy_revision:2,kind:'chat' as const}};
    rerender(<CaseContext {...props} {...next}/>);
    await screen.findByLabelText('PDF or image for text extraction');
    expect(oldSignals.every(signal=>signal.aborted)).toBe(true);
    await act(async()=>{oldCapabilities.resolve({...capabilities,extraction:{...capabilities.extraction!,supported:false}});oldTeaching.resolve({cases:[]});});
    expect(screen.getByLabelText('PDF or image for text extraction')).toBeTruthy();
    expect(screen.getByText('Start an installed teaching case')).toBeTruthy();
    expect(screen.queryByText(/Temporary attachment extraction is unavailable/)).toBeNull();
    expect(screen.queryByText('No installed teaching cases are available.')).toBeNull();
  });
});
