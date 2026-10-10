// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ApiError } from '../../platform/api';
import type { ConversationSummary } from '../../platform/designC';
import { WorkspaceProvider } from '../workspace';
import { ChatAttachments } from './ChatAttachments';
import Chat from './index';

const calls=vi.hoisted(()=>({api:vi.fn(),send:vi.fn()}));
vi.mock('../../platform/api',async()=>({...await vi.importActual('../../platform/api'),api:calls.api}));
vi.mock('./api',async()=>({...await vi.importActual('./api'),sendConversation:calls.send}));
const chat:ConversationSummary={identity:{type:'learn_thread',id:'saved-chat'},kind:'learning',retention:'saved',lifecycle:'active',revision:1,title:'CKD learning',project_id:null,created_at:'2026-10-10T00:00:00Z',updated_at:'2026-10-10T00:00:00Z'};
const inventory={conversation:chat.identity,conversation_revision:8,policy_revision:3,context_epoch:12,items:[]};
const file=new File(['A fictional educational file.'],'Kidney fictional.txt',{type:'text/plain'});
const intent={file,request_id:'stable_attachment_123'};
const receipt={id:'saved-attachment',title:file.name,filename:file.name,revision:1,reference:{target:{type:'attachment',id:'saved-attachment'}},conversation_revision:9,retention:'saved'};
const frame=(child:React.ReactNode,permitted=true)=><WorkspaceProvider policy={{revision:3,active_test_id:permitted?null:'active-test',assistance_allowed:permitted}}>{child}</WorkspaceProvider>;
beforeEach(()=>{calls.api.mockReset();calls.send.mockReset();calls.api.mockImplementation(async(path:string)=>path.startsWith('/attachments/')?inventory:path.endsWith('/draft')?{text:'Keep my existing draft',content_refs:[],revision:0,conversation_revision:1}:path.endsWith('/messages')||path.endsWith('/runs')||path.includes('/study/projects')?{items:[],next_cursor:null}:chat);});
afterEach(()=>cleanup());

it('consumes the Home File handoff once into review, preserves the composer and never uploads or sends automatically',async()=>{
  const consumed=vi.fn();
  const view=render(frame(<Chat identity={chat.identity} attachmentIntent={intent} onAttachmentIntentConsumed={consumed}/>));
  await screen.findByLabelText('Permission or licence');
  expect((screen.getByLabelText('Message Renulus') as HTMLTextAreaElement).value).toBe('Keep my existing draft');
  view.rerender(frame(<Chat identity={chat.identity} attachmentIntent={{...intent}} onAttachmentIntentConsumed={consumed}/>));
  expect(consumed).toHaveBeenCalledExactlyOnceWith(intent.request_id);
  expect(calls.api.mock.calls.filter(([path])=>path==='/attachments')).toHaveLength(0);
  expect(calls.send).not.toHaveBeenCalled();
  expect((screen.getByRole('button',{name:'Confirm attach'}) as HTMLButtonElement).disabled).toBe(true);
});

it('uploads only after explicit confirmation and repeats the exact File/pinned command after a lost acknowledgement',async()=>{
  let uploads=0;
  calls.api.mockImplementation(async(path:string)=>{
    if(path==='/attachments'){if(++uploads===1)throw new ApiError('Synthetic lost acknowledgement',0,'timeout',true);return receipt;}
    return inventory;
  });
  const before=vi.fn(async()=>chat),changed=vi.fn();
  render(frame(<ChatAttachments conversation={chat} open onOpenChange={()=>{}} intent={intent} beforeAttach={before} onChanged={changed}/>));
  await screen.findByLabelText('Permission or licence');
  fireEvent.click(screen.getByLabelText('Display this file in Renulus'));
  fireEvent.click(screen.getByLabelText('Keep a local original when this conversation is saved'));
  fireEvent.change(screen.getByLabelText('File title'),{target:{value:'Fictional ł kidney notes'}});
  fireEvent.change(screen.getByLabelText('Permission or licence'),{target:{value:'Synthetic original owned for this test'}});
  fireEvent.click(screen.getByRole('button',{name:'Confirm attach'}));
  await screen.findByText('Synthetic lost acknowledgement');
  expect((screen.getByLabelText('File title') as HTMLInputElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button',{name:'Retry same attachment'}));
  await screen.findByText('Attached to this saved conversation.');
  const requests=calls.api.mock.calls.filter(([path])=>path==='/attachments');
  expect(requests).toHaveLength(2);
  expect(requests[0][1].body).toBe(file);expect(requests[1][1].body).toBe(file);
  expect(requests[0][1].headers).toEqual(requests[1][1].headers);
  const header=requests[0][1].headers['x-renulus-attachment-options'];
  expect(header).not.toContain('ł');
  expect(JSON.parse(header)).toMatchObject({conversation:chat.identity,expected_conversation_revision:8,expected_policy_revision:3,expected_context_epoch:12,idempotency_key:intent.request_id,
    title:'Fictional ł kidney notes',rights:{display:true,cache:true,model_input:false,derivation:false,index:false,embedding:false,redistribution:false}});
  expect(before).toHaveBeenCalledTimes(1);expect(changed).toHaveBeenCalledWith({...chat,revision:9});
});

it('refuses attachment assistance during Test while retaining the volatile selection',async()=>{
  const view=render(frame(<ChatAttachments conversation={chat} open onOpenChange={()=>{}} intent={intent} beforeAttach={async()=>chat} onChanged={()=>{}}/>,false));
  expect(await screen.findByText('Files are unavailable during an active Test.')).toBeTruthy();
  expect(calls.api).not.toHaveBeenCalled();
  view.rerender(frame(<ChatAttachments conversation={chat} open onOpenChange={()=>{}} intent={intent} beforeAttach={async()=>chat} onChanged={()=>{}}/>));
  expect(await screen.findByLabelText('File title')).toBeTruthy();
  expect(calls.api.mock.calls.filter(([path])=>path==='/attachments')).toHaveLength(0);
});
