// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ApiError } from '../../platform/api';
import type { ConversationSummary } from '../../platform/designC';
import { NavigationProvider } from '../../shell/navigation';
import { WorkspaceProvider } from '../workspace';
import { CreateChatTest } from './CreateChatTest';
const calls=vi.hoisted(()=>({api:vi.fn()}));
vi.mock('../../platform/api',async()=>({...await vi.importActual('../../platform/api'),api:calls.api}));
const chat:ConversationSummary={identity:{type:'learn_thread',id:'saved-chat'},kind:'learning',retention:'saved',lifecycle:'active',revision:1,title:'CKD learning',project_id:null,created_at:'2026-10-10T00:00:00Z',updated_at:'2026-10-10T00:00:00Z'};
const published={test_id:'fixture-test',version_id:'fixture-version',item_count:10,study_start:{version:{type:'saved_test_version',id:'fixture-version'},mode:'study',timing:{kind:'untimed'},idempotency_key:'chat-test-study-fixture-publication'}};
const frame=(child:React.ReactNode)=><NavigationProvider><WorkspaceProvider policy={{revision:1,active_test_id:null,assistance_allowed:true}}>{child}</WorkspaceProvider></NavigationProvider>;
beforeEach(()=>{calls.api.mockReset();window.history.replaceState(null,'','#/chat');});
afterEach(()=>cleanup());
it('replays an ambiguous creation acknowledgement and starts the exact published version with its stable Study key',async()=>{
  let creates=0,starts=0;
  calls.api.mockImplementation(async(path:string)=>{
    if(path.endsWith('/tests')){if(++creates===1)throw new ApiError('Lost creation acknowledgement',0,'timeout',true);return {run_id:'fixture-run',state:'running'};}
    if(path.endsWith('/result'))return published;
    if(path==='/assessment/test-attempts'){if(++starts===1)throw new ApiError('Lost Study acknowledgement',0,'timeout',true);return {id:'fixture-attempt'};}
    return {run_id:'fixture-run',state:'published'};
  });
  const prepare=vi.fn(async()=>({...chat,revision:8}));
  render(frame(<CreateChatTest conversation={chat} disabled={false} prepare={prepare}/>));
  fireEvent.click(screen.getByRole('button',{name:'Create test from conversation'}));
  fireEvent.change(screen.getByLabelText('Question count'),{target:{value:'10'}});
  fireEvent.change(screen.getByLabelText('Learning focus (optional)'),{target:{value:'Conceptual nephrology reasoning'}});
  expect(calls.api).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button',{name:'Create fictional test'}));
  await screen.findByText('Lost creation acknowledgement');
  fireEvent.click(screen.getByRole('button',{name:'Retry same creation request'}));
  await screen.findByText('10 fictional questions');
  const requests=calls.api.mock.calls.filter(([path])=>path.endsWith('/tests'));
  expect(requests).toHaveLength(2);expect(requests[1][1].body).toEqual(requests[0][1].body);
  expect(requests[0][1].body).toMatchObject({expected_revision:8,count:10,instruction:'Conceptual nephrology reasoning'});
  expect(prepare).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button',{name:'Start Study'}));
  await screen.findByText('Lost Study acknowledgement');
  fireEvent.click(screen.getByRole('button',{name:'Start Study'}));
  await waitFor(()=>expect(window.location.hash).toBe('#/attempts/fixture-attempt'));
  const startRequests=calls.api.mock.calls.filter(([path])=>path==='/assessment/test-attempts');
  expect(startRequests).toHaveLength(2);expect(startRequests[1][1]).toEqual(startRequests[0][1]);
  expect(startRequests[0][1]).toMatchObject({headers:{'Idempotency-Key':published.study_start.idempotency_key},body:{version:published.study_start.version,mode:'study',timing:{kind:'untimed'}}});
});
it('cancels preparation when the conversation view closes without reading rich results',async()=>{
  calls.api.mockImplementation(async(path:string)=>({run_id:'volatile-run',state:path.endsWith('/cancel')?'cancelled':'running'}));
  const view=render(frame(<CreateChatTest conversation={chat} disabled={false} prepare={async()=>chat}/>));
  fireEvent.click(screen.getByRole('button',{name:'Create test from conversation'}));
  fireEvent.click(screen.getByRole('button',{name:'Create fictional test'}));
  await screen.findByRole('button',{name:'Cancel test creation'});
  view.unmount();
  expect(calls.api.mock.calls.some(([path])=>path==='/conversations/test-drafts/runs/volatile-run/cancel')).toBe(true);
  expect(calls.api.mock.calls.some(([path])=>path.endsWith('/result'))).toBe(false);
});
