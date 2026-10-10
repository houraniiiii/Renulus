// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { NavigationProvider, useNavigation } from '../../shell/navigation';
import type { ConversationSummary, StudyHelpContext } from '../../platform/designC';
import { CaseHandoffActions } from './CaseHandoffActions';
const calls=vi.hoisted(()=>({api:vi.fn()}));
vi.mock('../../platform/api',async()=>({...await vi.importActual('../../platform/api'),api:calls.api}));
const conversation:ConversationSummary={identity:{type:'case',id:'fictional-temporary-case'},kind:'case',retention:'temporary',lifecycle:'active',revision:1,title:'Fictional case',project_id:null,created_at:'2026-10-10T00:00:00Z',updated_at:'2026-10-10T00:00:00Z'};
afterEach(()=>{cleanup();calls.api.mockReset();window.history.replaceState({},'','#/newchat');});
it.each(['explain','generated-practice'] as const)('passes a %s ticket in volatile navigation and keeps temporary identity out of history',async target=>{
  const context:StudyHelpContext={attempt_id:'handoff-study',item_id:'study-item',version_id:'study-version',draft_revision:2,policy_revision:1,kind:'chat'};
  let navigation:ReturnType<typeof useNavigation>;
  function Observe(){navigation=useNavigation();return null;}
  calls.api.mockImplementation(async(path:string)=>path.endsWith('/context')?{revision:7}:{id:'volatile-ticket',case_handoff_id:'volatile-ticket',case_id:conversation.identity.id,question:'FICTIONAL_DRAFT_HANDOFF',conversation:conversation.identity,retention:'temporary',scope:{kind:'temporary-case',entity_id:conversation.identity.id}});
  const prepare=vi.fn(async()=>({...conversation,revision:3}));
  render(<NavigationProvider><Observe/><CaseHandoffActions studyHelpContext={context} conversation={conversation} question="FICTIONAL_DRAFT_HANDOFF" disabled={false} prepare={prepare}/></NavigationProvider>);
  fireEvent.click(screen.getByRole('button',{name:target==='explain'?'Explore in Learn':'Practise from this case'}));
  await waitFor(()=>{expect(navigation!.route).toBe(target==='explain'?'learn':'assessment');expect(navigation!.handoff?.conversation).toEqual(conversation.identity);});
  expect(calls.api).toHaveBeenLastCalledWith('/conversations/case/fictional-temporary-case/handoff',expect.objectContaining({body:{expected_revision:3,case_revision:7,target,question:target==='explain'?'FICTIONAL_DRAFT_HANDOFF':''}}));
  expect(navigation!.handoff?.conversation).toEqual(conversation.identity);
  expect(navigation!.handoff?.studyHelpContext).toEqual(context);
  expect(calls.api.mock.calls.every(([,options])=>options?.headers?.['X-Renulus-Study-Context']===JSON.stringify(context))).toBe(true);
  expect(window.location.hash).not.toContain('handoff-study');
  expect(window.location.hash).not.toContain(conversation.identity.id);
  expect(window.location.hash).not.toContain('FICTIONAL_DRAFT_HANDOFF');
});
