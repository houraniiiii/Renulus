// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import type { ConversationSummary, StudyHelpContext } from '../../platform/designC';
import { cancelChatTestRun, createConversation, readChatTestResult, readChatTestRun, sendConversation, startChatTest } from './api';

const context:StudyHelpContext={attempt_id:'study-attempt',item_id:'study-item',version_id:'study-version',draft_revision:2,policy_revision:3,kind:'chat'};
const conversation={kind:'learning',identity:{type:'learn_thread',id:'saved-chat'}} as ConversationSummary;
afterEach(()=>vi.unstubAllGlobals());
it('sends the exposure receipt only in guarded HTTP/SSE headers and keeps status/cancel neutral',async()=>{
  const fetch=vi.fn(async(path:string,_options:RequestInit)=>path.endsWith('/messages')?new Response('',{headers:{'Content-Type':'text/event-stream'}}):new Response('{}',{headers:{'Content-Type':'application/json'}}));
  vi.stubGlobal('fetch',fetch);
  await createConversation({},undefined,'stable-create-key',context);
  await sendConversation(conversation,{text:'Fictional question',request_id:'stable-send-key',expected_revision:1},()=>{},undefined,context);
  await startChatTest(conversation,{expected_revision:1,request_id:'stable-test-key',count:5},undefined,context);
  await readChatTestResult('volatile-run',undefined,context);
  await readChatTestRun('volatile-run');
  await cancelChatTestRun('volatile-run');
  expect(fetch.mock.calls).toHaveLength(6);
  for(const [index,[,options]] of fetch.mock.calls.entries()){
    expect((options as RequestInit).headers instanceof Headers).toBe(true);
    expect(((options as RequestInit).headers as Headers).get('X-Renulus-Study-Context')).toBe(index<4?JSON.stringify(context):null);
    expect(String((options as RequestInit).body??'')).not.toContain('study-attempt');
  }
});
