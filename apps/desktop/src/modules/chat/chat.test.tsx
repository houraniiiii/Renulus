// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ConversationSummary, PassageDraft } from '../../platform/designC';
import { WorkspaceProvider } from '../workspace';
import Chat from './index';

const chat:ConversationSummary={identity:{type:'learn_thread',id:'saved-chat'},kind:'learning',retention:'saved',lifecycle:'active',revision:1,title:'CKD learning',project_id:null,created_at:'2026-10-10T00:00:00Z',updated_at:'2026-10-10T00:00:00Z'};
const calls=vi.hoisted(()=>({send:vi.fn(),api:vi.fn()}));
vi.mock('./api',async()=>({...await vi.importActual('./api'),sendConversation:calls.send}));
vi.mock('../../platform/api',async()=>({...await vi.importActual('../../platform/api'),api:calls.api}));
function setup() {
  calls.send.mockReset();calls.api.mockReset();
  calls.api.mockImplementation(async(path:string)=>path.endsWith('/draft')?{text:'Existing draft',content_refs:[],revision:0,conversation_revision:1}:path.includes('/messages')||path.includes('/study/projects')?{items:[],next_cursor:null}:chat);
}
const frame=(element:React.ReactNode)=><WorkspaceProvider policy={{revision:1,active_test_id:null,assistance_allowed:true}}>{element}</WorkspaceProvider>;
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
    calls.api.mockImplementation(async(path:string)=>path.endsWith('/draft')?{text:'Second chat draft',content_refs:[],revision:0,conversation_revision:1}:path.includes('/messages')||path.includes('/study/projects')?{items:[],next_cursor:null}:{...chat,identity:{type:'learn_thread',id:'second-chat'}});
    view.rerender(frame(<Chat identity={{type:'learn_thread',id:'second-chat'}}/>));
    await waitFor(()=>expect((screen.getByLabelText('Message Renulus') as HTMLTextAreaElement).value).toBe('Second chat draft'));
    await act(async()=>{publish({run_id:'old-run',sequence:2,type:'delta',payload:{text:'Late text from old chat'}});finish();});
    expect(screen.queryByText('Late text from old chat')).toBeNull();
    fireEvent.change(screen.getByLabelText('Message Renulus'),{target:{value:'Second revised draft'}});
    expect(calls.send).toHaveBeenCalledTimes(1);
  });
});
