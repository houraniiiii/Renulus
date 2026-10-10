import { beforeEach, expect, it, vi } from 'vitest';
import { createConversation, startQuickPractice, readChatTestRun, readChatTestResult } from './api';
const calls=vi.hoisted(()=>({api:vi.fn()}));
vi.mock('../../platform/api',()=>({api:calls.api}));
beforeEach(()=>calls.api.mockReset());
it('keeps a caller creation key stable across a lost acknowledgement retry',async()=>{
  const input={kind:'learning' as const};
  await createConversation(input,undefined,'stable_creation_key');
  await createConversation(input,undefined,'stable_creation_key');
  expect(calls.api.mock.calls.map(([,options])=>options.headers)).toEqual([
    {'Idempotency-Key':'stable_creation_key'},{'Idempotency-Key':'stable_creation_key'},
  ]);
});
it('sends only an explicit five-question Quick intent and separates neutral status from guarded result reads',async()=>{
  await startQuickPractice({text:'Fictional volatile input',request_id:'stable_draft_key'});
  expect(calls.api).toHaveBeenLastCalledWith('/conversations/test-drafts',expect.objectContaining({body:{intent:'quick_practice',text:'Fictional volatile input',request_id:'stable_draft_key',count:5}}));
  await readChatTestRun('synthetic-run');
  expect(calls.api).toHaveBeenLastCalledWith('/conversations/test-drafts/runs/synthetic-run',expect.anything());
  await readChatTestResult('synthetic-run');
  expect(calls.api).toHaveBeenLastCalledWith('/conversations/test-drafts/runs/synthetic-run/result',expect.anything());
});
