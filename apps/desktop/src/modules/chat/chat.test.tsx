// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ConversationSummary, PassageDraft } from '../../platform/designC';
import { WorkspaceProvider } from '../workspace';
import { NavigationProvider } from '../../shell/navigation';
import Chat from './index';

const chat:ConversationSummary={identity:{type:'learn_thread',id:'saved-chat'},kind:'learning',retention:'saved',lifecycle:'active',revision:1,title:'CKD learning',project_id:null,created_at:'2026-10-10T00:00:00Z',updated_at:'2026-10-10T00:00:00Z'};
const calls=vi.hoisted(()=>({send:vi.fn(),api:vi.fn()}));
vi.mock('./api',async()=>({...await vi.importActual('./api'),sendConversation:calls.send}));
vi.mock('../../platform/api',async()=>({...await vi.importActual('../../platform/api'),api:calls.api}));
function setup() {
  calls.send.mockReset();calls.api.mockReset();
  calls.api.mockImplementation(async(path:string)=>path.endsWith('/draft')?{text:'Existing draft',content_refs:[],revision:0,conversation_revision:1}:path.includes('/messages')||path.includes('/study/projects')||path.endsWith('/runs')?{items:[],next_cursor:null}:chat);
}
const frame=(element:React.ReactNode)=><NavigationProvider><WorkspaceProvider policy={{revision:1,active_test_id:null,assistance_allowed:true}}>{element}</WorkspaceProvider></NavigationProvider>;
afterEach(()=>cleanup());

describe('Chat volatile handoffs',()=>{
  it('appends a passage once, keeps the existing draft and never sends automatically',async()=>{
    setup();const consumed=vi.fn();
    const passage:PassageDraft & {id:string}={id:'passage-action',text:'Selected fictional passage',title:'A source',reference:{target:{type:'library_revision',id:'saved-revision'}}};
    const view=render(frame(<Chat identity={chat.identity} passageIntent={passage} onPassageIntentConsumed={consumed}/>));
    const composer=await screen.findByLabelText('Message Renulus');
    await waitFor(()=>expect((composer as HTMLTextAreaElement).value).toBe('Existing draft\n\nSelected fictional passage'));
    view.rerender(frame(<Chat identity={chat.identity} passageIntent={{...passage}} onPassageIntentConsumed={consumed}/>));
    expect(consumed).toHaveBeenCalledTimes(1);expect(calls.send).not.toHaveBeenCalled();
    expect(screen.getByRole('button',{name:'Remove source 1'})).toBeTruthy();
  });

  it('consumes explicit send intent once and ignores old stream output after switching chats',async()=>{
    setup();let publish:(event:unknown)=>void=()=>{};let finish:()=>void=()=>{};
    calls.send.mockImplementation((_chat,_input,onEvent)=>{publish=onEvent;return new Promise<void>(resolve=>{finish=resolve;});});
    const consumed=vi.fn(),intent={text:'Fictional request',request_id:'handoff-request-123'};
    const view=render(frame(<Chat identity={chat.identity} sendIntent={intent} onSendIntentConsumed={consumed}/>));
    await waitFor(()=>expect(calls.send).toHaveBeenCalledTimes(1));
    view.rerender(frame(<Chat identity={chat.identity} sendIntent={{...intent}} onSendIntentConsumed={consumed}/>));
    expect(consumed).toHaveBeenCalledTimes(1);
    await act(async()=>publish({run_id:'saved-running',sequence:1,type:'started',payload:{}}));
    calls.api.mockImplementation(async(path:string)=>path.endsWith('/draft')?{text:'Second chat draft',content_refs:[],revision:0,conversation_revision:1}:path.includes('/messages')||path.includes('/study/projects')?{items:[],next_cursor:null}:{...chat,identity:{type:'learn_thread',id:'second-chat'}});
    view.rerender(frame(<Chat identity={{type:'learn_thread',id:'second-chat'}}/>));
    await waitFor(()=>expect((screen.getByLabelText('Message Renulus') as HTMLTextAreaElement).value).toBe('Second chat draft'));
    expect(calls.api.mock.calls.some(([path])=>path.includes('/cancel'))).toBe(false);
    await act(async()=>{publish({run_id:'old-run',sequence:2,type:'delta',payload:{text:'Late text from old chat'}});finish();});
    expect(screen.queryByText('Late text from old chat')).toBeNull();
    fireEvent.change(screen.getByLabelText('Message Renulus'),{target:{value:'Second revised draft'}});
    expect(calls.send).toHaveBeenCalledTimes(1);
  });

  it('reopens a saved running response and refreshes its canonical terminal transcript',async()=>{
    setup();let detailReads=0;
    calls.api.mockImplementation(async(path:string)=>{
      if(path.endsWith('/runs'))return {items:[{run_id:'reopened-run',state:'running'}],next_cursor:null};
      if(path.endsWith('/runs/reopened-run'))return ++detailReads===1?{run_id:'reopened-run',state:'running',partial_text:'Still responding',conversation:chat}:{run_id:'reopened-run',state:'completed',conversation:{...chat,revision:3}};
      if(path.endsWith('/draft'))return {text:detailReads>1?'':'Existing draft',content_refs:[],revision:0,conversation_revision:3};
      if(path.endsWith('/messages'))return {items:detailReads>1?[{id:'canonical-answer',run_id:'reopened-run',role:'assistant',content:'Canonical completed response',content_refs:[]}]:[],next_cursor:null};
      if(path.includes('/study/projects'))return {items:[],next_cursor:null};
      return chat;
    });
    render(frame(<Chat identity={chat.identity}/>));
    expect(await screen.findByText('Still responding')).toBeTruthy();
    expect(await screen.findByText('Canonical completed response',{}, {timeout:2000})).toBeTruthy();
    expect((screen.getByLabelText('Message Renulus') as HTMLTextAreaElement).value).toBe('');
    expect(calls.send).not.toHaveBeenCalled();
  });

  it('cancels a temporary response when its view closes',async()=>{
    setup();calls.api.mockImplementation(async(path:string)=>path.endsWith('/draft')?{text:'',content_refs:[],revision:0,conversation_revision:1}:path.includes('/messages')||path.includes('/study/projects')||path.endsWith('/runs')?{items:[],next_cursor:null}:{...chat,retention:'temporary'});
    calls.send.mockImplementation(async(_chat,_input,onEvent)=>{onEvent({run_id:'temporary-run',sequence:1,type:'started',payload:{}});await new Promise<void>(()=>{});});
    const view=render(frame(<Chat identity={chat.identity} sendIntent={{text:'Temporary fictional question',request_id:'temporary-intent-123'}}/>));
    await waitFor(()=>expect(calls.send).toHaveBeenCalledTimes(1));
    view.unmount();
    expect(calls.api.mock.calls.some(([path])=>path.endsWith('/runs/temporary-run/cancel'))).toBe(true);
  });

  it('shows the saved failed outcome with its retained draft after reopening',async()=>{
    setup();const ordinary=calls.api.getMockImplementation();
    calls.api.mockImplementation(async(path:string,...args)=>path.endsWith('/runs')?{items:[{run_id:'failed-run',state:'error'}],next_cursor:null}:path.endsWith('/runs/failed-run')?{run_id:'failed-run',state:'error',error:{code:'authentication_required',message:'Connect the approved subscription to continue.',retryable:true}}:ordinary?.(path,...args));
    render(frame(<Chat identity={chat.identity}/>));
    expect(await screen.findByText('Connect the approved subscription to continue.')).toBeTruthy();
    expect((screen.getByLabelText('Message Renulus') as HTMLTextAreaElement).value).toBe('Existing draft');
    expect(calls.send).not.toHaveBeenCalled();
  });
});
