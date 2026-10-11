// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ContentReference, ConversationSummary, PassageDraft, StudyHelpContext } from '../../platform/designC';
import { WorkspaceProvider } from '../workspace';
import { NavigationProvider } from '../../shell/navigation';
import { ApiError } from '../../platform/api';
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
  it('retries a failed rename without sending the unrelated composer draft',async()=>{
    setup();let renames=0;
    const original=calls.api.getMockImplementation();
    calls.api.mockImplementation(async(path:string,options?:{method?:string;body?:{title?:string}})=>{
      if(options?.method==='PATCH'){
        if(++renames===1)throw new ApiError('Synthetic rename unavailable',503,'unavailable',true);
        return {...chat,title:options.body?.title,revision:2};
      }
      return original?.(path,options);
    });
    render(frame(<Chat identity={chat.identity}/>));
    fireEvent.change(await screen.findByLabelText('Message Renulus'),{target:{value:'Unrelated unsent draft'}});
    fireEvent.change(screen.getByLabelText('Conversation title'),{target:{value:'Renamed learning'}});
    fireEvent.click(screen.getByRole('button',{name:'Rename'}));
    expect(await screen.findByText('Synthetic rename unavailable')).toBeTruthy();
    await act(async()=>fireEvent.click(screen.getByRole('button',{name:'Try again'})));
    expect(calls.send).not.toHaveBeenCalled();
    await waitFor(()=>expect(renames).toBe(2));
    expect(await screen.findByRole('heading',{name:'Renamed learning'})).toBeTruthy();
    expect((screen.getByLabelText('Message Renulus') as HTMLTextAreaElement).value).toBe('Unrelated unsent draft');
    expect(calls.send).not.toHaveBeenCalled();
    expect(calls.api.mock.calls.some(([path,options])=>path==='/conversations'&&options?.method==='POST')).toBe(false);
  });

  it('reloads an existing conversation after a history read fails without creating or sending',async()=>{
    setup();let historyReads=0;
    const context:StudyHelpContext={attempt_id:'retry-study',item_id:'retry-item',version_id:'retry-version',draft_revision:2,policy_revision:3,kind:'chat'};
    const reference={target:{type:'library_revision' as const,id:'retained-source'}};
    const original=calls.api.getMockImplementation(),navigated=vi.fn();
    calls.api.mockImplementation(async(path:string,...args)=>{
      if(path.endsWith('/messages')){
        if(++historyReads===1)throw new ApiError('Synthetic history unavailable',503,'unavailable',true);
        return {items:[{id:'retained-message',run_id:'past-run',role:'assistant',content:'Retained conversation history',content_refs:[]}],next_cursor:null};
      }
      if(path.endsWith('/draft'))return {text:'Retained draft',content_refs:[reference],revision:2,conversation_revision:3};
      return original?.(path,...args);
    });
    render(frame(<Chat identity={chat.identity} onConversation={navigated} studyHelpContext={context}/>));
    expect(await screen.findByRole('heading',{name:'Conversation could not be opened'})).toBeTruthy();
    expect(screen.queryByRole('button',{name:'Start saved chat'})).toBeNull();
    expect(screen.queryByRole('button',{name:'Start temporary chat'})).toBeNull();
    fireEvent.click(screen.getByRole('button',{name:'Try again'}));
    expect(await screen.findByText('Retained conversation history')).toBeTruthy();
    expect((screen.getByLabelText('Message Renulus') as HTMLTextAreaElement).value).toBe('Retained draft');
    expect(screen.getByRole('button',{name:'Remove source 1'})).toBeTruthy();
    expect(historyReads).toBe(2);
    expect(calls.send).not.toHaveBeenCalled();expect(navigated).not.toHaveBeenCalled();
    expect(calls.api.mock.calls.every(([,options])=>!options?.method||options.method==='GET')).toBe(true);
    for(const [path,options] of calls.api.mock.calls){
      if(!path.endsWith('/runs'))expect(options?.headers?.['X-Renulus-Study-Context']).toBe(JSON.stringify(context));
    }
  });

  it('keeps an unsaved draft and source through a failed same-identity refresh and reload',async()=>{
    setup();let summaryReads=0;
    const original=calls.api.getMockImplementation();
    const reference={target:{type:'library_revision' as const,id:'retained-source'}};
    calls.api.mockImplementation(async(path:string,...args)=>{
      if(path==='/conversations/learning/saved-chat'){
        if(++summaryReads===2)throw new ApiError('Synthetic conversation unavailable',404,'conversation_missing');
        return chat;
      }
      if(path.endsWith('/draft'))return {text:'Earlier saved draft',content_refs:[reference],revision:1,conversation_revision:1};
      return original?.(path,...args);
    });
    const view=render(frame(<Chat identity={chat.identity} navigationRevision={1}/>));
    fireEvent.change(await screen.findByLabelText('Message Renulus'),{target:{value:'Keep my latest unsaved draft'}});
    view.rerender(frame(<Chat identity={chat.identity} navigationRevision={2}/>));
    expect(await screen.findByRole('heading',{name:'Conversation could not be opened'})).toBeTruthy();
    fireEvent.click(screen.getByRole('button',{name:'Try again'}));
    const composer=await screen.findByLabelText('Message Renulus');
    expect((composer as HTMLTextAreaElement).value).toBe('Keep my latest unsaved draft');
    expect(screen.getByRole('button',{name:'Remove source 1'})).toBeTruthy();
    expect(calls.send).not.toHaveBeenCalled();
  });

  it('retries failed history pagination without submitting the retained draft',async()=>{
    setup();let pageReads=0;
    const original=calls.api.getMockImplementation();
    calls.api.mockImplementation(async(path:string,...args)=>{
      if(path.endsWith('/messages'))return {items:[],next_cursor:'older'};
      if(path.endsWith('/messages?cursor=older')){
        if(++pageReads===1)throw new ApiError('Synthetic older history unavailable',503,'unavailable',true);
        return {items:[{id:'older-message',run_id:'past-run',role:'assistant',content:'Older retained answer',content_refs:[]}],next_cursor:null};
      }
      return original?.(path,...args);
    });
    render(frame(<Chat identity={chat.identity}/>));
    fireEvent.click(await screen.findByRole('button',{name:'Load more history'}));
    expect(await screen.findByText('Synthetic older history unavailable')).toBeTruthy();
    fireEvent.click(screen.getByRole('button',{name:'Try again'}));
    expect(await screen.findByText('Older retained answer')).toBeTruthy();
    expect(screen.queryByText('Synthetic older history unavailable')).toBeNull();
    expect((screen.getByLabelText('Message Renulus') as HTMLTextAreaElement).value).toBe('Existing draft');
    expect(calls.send).not.toHaveBeenCalled();
  });

  it('keeps a pending passage through repeated Case load failures and consumes it once after reload',async()=>{
    setup();let reads=0;
    const original=calls.api.getMockImplementation(),consumed=vi.fn();
    const caseChat={...chat,kind:'case' as const,identity:{type:'case' as const,id:'retry-case'}};
    const passage:PassageDraft & {id:string}={id:'retry-passage',text:'Selected fictional passage',title:'A source',reference:{target:{type:'library_revision',id:'saved-revision'}}};
    calls.api.mockImplementation(async(path:string,...args)=>{
      if(path==='/conversations/case/retry-case'){
        if(++reads<=2)throw new ApiError('Synthetic Case unavailable',503,'unavailable',true);
        return caseChat;
      }
      if(path.endsWith('/context'))return {id:'retry-case',kind:'daily',text:'Synthetic context',revision:1,attachments:[],scope:{kind:'saved-case',entity_id:'retry-case'}};
      if(path==='/cases/capabilities')return {extraction:{supported:false}};
      if(path==='/cases/teaching')return {cases:[]};
      return original?.(path,...args);
    });
    const view=render(frame(<Chat identity={caseChat.identity} passageIntent={passage} onPassageIntentConsumed={consumed}/>));
    expect(await screen.findByRole('heading',{name:'Conversation could not be opened'})).toBeTruthy();
    expect(consumed).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button',{name:'Try again'}));
    expect(await screen.findByRole('heading',{name:'Conversation could not be opened'})).toBeTruthy();
    expect(consumed).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button',{name:'Try again'}));
    const composer=await screen.findByLabelText('Your case question');
    await waitFor(()=>expect((composer as HTMLTextAreaElement).value).toBe('Existing draft\n\nSelected fictional passage'));
    view.rerender(frame(<Chat identity={caseChat.identity} passageIntent={{...passage}} onPassageIntentConsumed={consumed}/>));
    expect(consumed).toHaveBeenCalledTimes(1);expect(calls.send).not.toHaveBeenCalled();
    expect(calls.api.mock.calls.some(([path,options])=>path==='/conversations'&&options?.method==='POST')).toBe(false);
  });

  it('does not replay a consumed send intent after a failed reload of the same identity',async()=>{
    setup();let refuse=false;
    const original=calls.api.getMockImplementation(),consumed=vi.fn();
    const intent={text:'Explicit fictional question',request_id:'consumed-before-reload'};
    const context:StudyHelpContext={attempt_id:'reload-study',item_id:'reload-item',version_id:'reload-version',draft_revision:1,policy_revision:2,kind:'chat'};
    calls.api.mockImplementation(async(path:string,...args)=>{
      if(path==='/conversations/learning/saved-chat'&&refuse){refuse=false;throw new ApiError('Synthetic reload unavailable',503,'unavailable',true);}
      return original?.(path,...args);
    });
    calls.send.mockImplementation(async(_chat,_body,onEvent)=>onEvent({run_id:'explicit-run',sequence:1,type:'error',payload:{message:'Synthetic send failed',code:'unavailable',retryable:true}}));
    const view=render(frame(<Chat identity={chat.identity} sendIntent={intent} onSendIntentConsumed={consumed}/>));
    expect(await screen.findByText('Synthetic send failed')).toBeTruthy();
    expect(screen.queryByRole('button',{name:'Try again'})).toBeNull();
    refuse=true;
    view.rerender(frame(<Chat identity={chat.identity} sendIntent={{...intent}} onSendIntentConsumed={consumed} studyHelpContext={context}/>));
    expect(await screen.findByRole('heading',{name:'Conversation could not be opened'})).toBeTruthy();
    fireEvent.click(screen.getByRole('button',{name:'Try again'}));
    expect(await screen.findByLabelText('Message Renulus')).toBeTruthy();
    expect(consumed).toHaveBeenCalledTimes(1);expect(calls.send).toHaveBeenCalledTimes(1);
    expect(calls.send.mock.calls[0][1].request_id).toBe(intent.request_id);
    expect(calls.api.mock.calls.some(([path,options])=>path==='/conversations'&&options?.method==='POST')).toBe(false);
  });

  it('refreshes the same chat membership on explicit navigation without replacing its draft',async()=>{
    setup();let current={...chat,project_id:'project-a'};
    const original=calls.api.getMockImplementation();
    calls.api.mockImplementation(async(path:string,options?:{method?:string})=>{
      if(path.includes('/study/projects'))return {items:[{id:'project-a',title:'Project A'},{id:'project-b',title:'Project B'}],next_cursor:null};
      if(path==='/conversations/learning/saved-chat')return current;
      return original?.(path,options);
    });
    const view=render(frame(<Chat identity={chat.identity} navigationRevision={1}/>));
    fireEvent.change(await screen.findByLabelText('Message Renulus'),{target:{value:'Keep my unsaved draft'}});
    await waitFor(()=>expect((screen.getByLabelText('Project') as HTMLSelectElement).value).toBe('project-a'));
    current={...current,revision:3,project_id:'project-b'};
    view.rerender(frame(<Chat identity={chat.identity} navigationRevision={2}/>));
    await waitFor(()=>expect((screen.getByLabelText('Project') as HTMLSelectElement).value).toBe('project-b'));
    expect((screen.getByLabelText('Message Renulus') as HTMLTextAreaElement).value).toBe('Keep my unsaved draft');
    expect(calls.api.mock.calls.filter(([path,options])=>path.endsWith('/draft')&&options?.method!=='PUT')).toHaveLength(1);
    expect(calls.api.mock.calls.filter(([path])=>path.endsWith('/messages'))).toHaveLength(1);
    expect(calls.send).not.toHaveBeenCalled();
  });

  it('keeps the same response subscription when navigation refreshes its chat',async()=>{
    setup();let streamSignal:AbortSignal|undefined;
    calls.send.mockImplementation(async(_chat,_body,onEvent,signal)=>{
      streamSignal=signal;onEvent({run_id:'retained-run',sequence:1,type:'started',payload:{}});
      await new Promise<void>(resolve=>signal.addEventListener('abort',()=>resolve(),{once:true}));
    });
    const view=render(frame(<Chat identity={chat.identity} navigationRevision={1} sendIntent={{text:'Keep this request',request_id:'retained-request'}}/>));
    await waitFor(()=>expect(calls.send).toHaveBeenCalledTimes(1));
    view.rerender(frame(<Chat identity={chat.identity} navigationRevision={2}/>));
    await waitFor(()=>expect(calls.api.mock.calls.filter(([path])=>path==='/conversations/learning/saved-chat')).toHaveLength(2));
    expect(streamSignal?.aborted).toBe(false);
    expect(screen.getByRole('button',{name:'Stop'})).toBeTruthy();
    expect(calls.send).toHaveBeenCalledTimes(1);
    expect((screen.getByLabelText('Message Renulus') as HTMLTextAreaElement).value).toBe('Keep this request');
  });

  it('sends a reviewed Case image through the conversation stream while retaining the separate composer draft',async()=>{
    setup();const context:StudyHelpContext={attempt_id:'image-study',item_id:'item',version_id:'version',draft_revision:1,policy_revision:1,kind:'chat'};
    const caseChat={...chat,kind:'case' as const,identity:{type:'case' as const,id:'image-case'}};
    const session={id:'image-case',kind:'daily',title:'Fictional image Case',text:'',revision:4,scope:{kind:'saved-case',entity_id:'image-case'},saved:true,dirty:false,messages:[],teaching:null,attachments:[]};
    const preview={id:'image-preview',case_id:'image-case',revision:4,scope:{kind:'temporary-case',entity_id:'image-case'},mode:'image',filename:'synthetic.png',text:'',ocr:{},image:{media_type:'image/png',data:'AAAA'},error:null};
    calls.api.mockImplementation(async(path:string)=>{
      if(path==='/cases/capabilities')return {image_interpretation:{supported:true,models:['approved-image'],max_bytes:8000000},extraction:{supported:false}};
      if(path==='/cases/teaching')return {cases:[]};
      if(path.endsWith('/prepare'))return {...preview,state:'reading'};
      if(path.endsWith('/extract'))return {...preview,state:'ready'};
      if(path.endsWith('/context'))return session;
      if(path.endsWith('/draft'))return {text:'Keep this separate draft',content_refs:[],revision:0,conversation_revision:1};
      if(path.includes('/messages')||path.includes('/study/projects')||path.endsWith('/runs'))return {items:[],next_cursor:null};
      return caseChat;
    });
    calls.send.mockImplementation(async(_chat,_body,onEvent)=>onEvent({run_id:'image-run',sequence:1,type:'completed',payload:{conversation:caseChat}}));
    render(frame(<Chat identity={caseChat.identity} studyHelpContext={context}/>));
    fireEvent.change(await screen.findByLabelText('Use this file for'),{target:{value:'image'}});
    fireEvent.change(screen.getByLabelText('Image to review before sending'),{target:{files:[new File(['synthetic'], 'synthetic.png', {type:'image/png'})]}});
    const question=await screen.findByLabelText('Question about this image');
    expect(calls.send).not.toHaveBeenCalled();
    fireEvent.change(question,{target:{value:'Fictional image learning question'}});
    fireEvent.click(screen.getByRole('button',{name:'Send image for discussion'}));
    await waitFor(()=>expect(calls.send).toHaveBeenCalledTimes(1));
    expect(calls.send.mock.calls[0][1]).toMatchObject({text:'Fictional image learning question',image_preview_id:'image-preview',case_revision:4,model:'approved-image',content_refs:[]});
    expect(calls.send.mock.calls[0][4]).toEqual(context);
    expect((screen.getByLabelText('Your case question') as HTMLTextAreaElement).value).toBe('Keep this separate draft');
  });
  it('flushes an immediate Archive once and retains the draft after Restore and remount',async()=>{
    setup();
    const reference={target:{type:'library_revision' as const,id:'draft-source'}};
    let current:ConversationSummary={...chat};
    let stored={text:'',content_refs:[reference],revision:0};
    const mutations:{method:string;path:string;body:unknown}[]=[];
    let releaseWrite:()=>void=()=>{};
    const draftGate=new Promise<void>(resolve=>{releaseWrite=resolve;});
    calls.api.mockImplementation(async(path:string,options?:{method?:string;body?:{expected_revision:number;text?:string;content_refs?:typeof stored.content_refs}})=>{
      if(options?.method){
        mutations.push({method:options.method,path,body:options.body});
        if(options.body?.expected_revision!==current.revision)throw new ApiError('Synthetic stale revision',409,'revision_conflict');
        if(path.endsWith('/draft')&&options.method==='PUT'){
          await draftGate;
          stored={text:options.body.text!,content_refs:options.body.content_refs!,revision:stored.revision+1};
          current={...current,revision:current.revision+1};
          return {...stored,conversation_revision:current.revision};
        }
        if(path.endsWith('/archive')||path.endsWith('/restore')){
          current={...current,revision:current.revision+1,lifecycle:path.endsWith('/archive')?'archived':'active'};
          return current;
        }
        throw new Error('Unexpected synthetic mutation');
      }
      if(path.endsWith('/draft'))return {...stored,conversation_revision:current.revision};
      if(path.endsWith('/messages')||path.endsWith('/runs')||path.includes('/study/projects'))return {items:[],next_cursor:null};
      return current;
    });
    const view=render(frame(<Chat identity={chat.identity}/>));
    const composer=await screen.findByLabelText('Message Renulus');
    vi.useFakeTimers({toFake:['setTimeout','clearTimeout']});
    try{
      fireEvent.change(composer,{target:{value:'Retain this edited CKD draft'}});
      await act(async()=>fireEvent.click(screen.getByRole('button',{name:'Archive'})));
      await act(async()=>{await vi.advanceTimersByTimeAsync(450);});
      expect(mutations).toEqual([{method:'PUT',path:'/conversations/learning/saved-chat/draft',body:{expected_revision:1,text:'Retain this edited CKD draft',content_refs:[reference]}}]);
      expect((composer as HTMLTextAreaElement).disabled).toBe(true);
      expect((screen.getByRole('button',{name:'Archive'}) as HTMLButtonElement).disabled).toBe(true);
      await act(async()=>{releaseWrite();await draftGate;});
      expect(screen.getByRole('button',{name:'Restore'})).toBeTruthy();
      await act(async()=>{await vi.advanceTimersByTimeAsync(450);});
      await act(async()=>fireEvent.click(screen.getByRole('button',{name:'Restore'})));
      await act(async()=>{await vi.advanceTimersByTimeAsync(450);});
      expect(mutations).toEqual([
        {method:'PUT',path:'/conversations/learning/saved-chat/draft',body:{expected_revision:1,text:'Retain this edited CKD draft',content_refs:[reference]}},
        {method:'POST',path:'/conversations/learning/saved-chat/archive',body:{expected_revision:2}},
        {method:'POST',path:'/conversations/learning/saved-chat/restore',body:{expected_revision:3}},
      ]);
      expect(screen.queryByText('Synthetic stale revision')).toBeNull();
    }finally{
      await act(async()=>{releaseWrite();await draftGate;});
      view.unmount();vi.useRealTimers();
    }
    render(frame(<Chat identity={chat.identity}/>));
    expect((await screen.findByLabelText('Message Renulus') as HTMLTextAreaElement).value).toBe('Retain this edited CKD draft');
    expect(screen.getByRole('button',{name:'Remove source 1'})).toBeTruthy();
    expect(calls.send).not.toHaveBeenCalled();
  });

  it.each(['passage','send'] as const)('retains a fresh %s intent through pending Archive and consumes it once after Restore',async(kind)=>{
    setup();
    let current:ConversationSummary={...chat};
    let stored={text:'Existing draft',content_refs:[] as ContentReference[],revision:0};
    let releaseWrite:()=>void=()=>{};
    const draftGate=new Promise<void>(resolve=>{releaseWrite=resolve;});
    const original=calls.api.getMockImplementation(),onConsumed=vi.fn();
    const queuedProps=()=>kind==='passage'
      ?{passageIntent:{id:'queued-passage',text:'Queued fictional passage',title:'Queued source',reference:{target:{type:'library_revision' as const,id:'queued-source'}}},onPassageIntentConsumed:onConsumed}
      :{sendIntent:{text:'Queued fictional question',request_id:'queued-send'},onSendIntentConsumed:onConsumed};
    calls.api.mockImplementation(async(path:string,options?:{method?:string;body?:{expected_revision:number;text?:string;content_refs?:ContentReference[]}})=>{
      if(options?.method){
        if(options.body?.expected_revision!==current.revision)throw new ApiError('Synthetic stale revision',409,'revision_conflict');
        if(path.endsWith('/draft')){
          await draftGate;
          stored={text:options.body.text!,content_refs:options.body.content_refs!,revision:stored.revision+1};
          current={...current,revision:current.revision+1};
          return {...stored,conversation_revision:current.revision};
        }
        if(path.endsWith('/archive')||path.endsWith('/restore')){
          current={...current,revision:current.revision+1,lifecycle:path.endsWith('/archive')?'archived':'active'};
          return current;
        }
        throw new Error('Unexpected synthetic mutation');
      }
      if(path==='/conversations/learning/saved-chat')return current;
      if(path.endsWith('/draft'))return {...stored,conversation_revision:current.revision};
      return original?.(path,options);
    });
    calls.send.mockImplementation(async(_chat,_body,onEvent)=>onEvent({run_id:'queued-run',sequence:1,type:'error',payload:{message:'Synthetic terminal refusal',code:'unavailable',retryable:true}}));
    const view=render(frame(<Chat identity={chat.identity}/>));
    const composer=await screen.findByLabelText('Message Renulus');
    vi.useFakeTimers({toFake:['setTimeout','clearTimeout']});
    try{
      fireEvent.change(composer,{target:{value:'Archive snapshot draft'}});
      await act(async()=>fireEvent.click(screen.getByRole('button',{name:'Archive'})));
      expect(calls.api.mock.calls.find(([path,options])=>path.endsWith('/draft')&&options?.method==='PUT')?.[1].body).toEqual({expected_revision:1,text:'Archive snapshot draft',content_refs:[]});
      view.rerender(frame(<Chat identity={chat.identity} {...queuedProps()}/>));
      await act(async()=>{await vi.advanceTimersByTimeAsync(450);});
      expect(onConsumed).not.toHaveBeenCalled();
      expect((screen.getByLabelText('Message Renulus') as HTMLTextAreaElement).value).toBe('Archive snapshot draft');
      expect(screen.queryByRole('button',{name:'Remove source 1'})).toBeNull();
      expect(calls.send).not.toHaveBeenCalled();
      await act(async()=>{releaseWrite();await draftGate;});
      expect(screen.getByRole('button',{name:'Restore'})).toBeTruthy();
      view.rerender(frame(<Chat identity={chat.identity} {...queuedProps()}/>));
      await act(async()=>{await vi.advanceTimersByTimeAsync(450);});
      expect(onConsumed).not.toHaveBeenCalled();
      expect((screen.getByLabelText('Message Renulus') as HTMLTextAreaElement).value).toBe('Archive snapshot draft');
      expect(screen.queryByRole('button',{name:'Remove source 1'})).toBeNull();
      expect(calls.send).not.toHaveBeenCalled();
      await act(async()=>fireEvent.click(screen.getByRole('button',{name:'Restore'})));
      expect(onConsumed).toHaveBeenCalledTimes(1);
      expect(onConsumed).toHaveBeenCalledWith(kind==='passage'?'queued-passage':'queued-send');
      const expectedText=kind==='passage'?'Archive snapshot draft\n\nQueued fictional passage':'Queued fictional question';
      expect((screen.getByLabelText('Message Renulus') as HTMLTextAreaElement).value).toBe(expectedText);
      view.rerender(frame(<Chat identity={chat.identity} {...queuedProps()}/>));
      await act(async()=>{await vi.advanceTimersByTimeAsync(450);});
      expect(onConsumed).toHaveBeenCalledTimes(1);
      expect((screen.getByLabelText('Message Renulus') as HTMLTextAreaElement).value).toBe(expectedText);
      if(kind==='passage'){
        expect(screen.getAllByRole('button',{name:'Remove source 1'})).toHaveLength(1);
        expect(calls.send).not.toHaveBeenCalled();
      }else{
        expect(calls.send).toHaveBeenCalledTimes(1);
        expect(calls.send.mock.calls[0][1]).toMatchObject({text:'Queued fictional question',request_id:'queued-send',expected_revision:4,content_refs:[]});
      }
      expect(screen.queryByText('Synthetic stale revision')).toBeNull();
    }finally{
      await act(async()=>{releaseWrite();await draftGate;});
      view.unmount();vi.useRealTimers();
    }
  });

  it('flushes a new temporary draft before Save and replays the same command after a lost acknowledgement',async()=>{
    setup();let attempts=0;
    const temporary={...chat,retention:'temporary' as const};
    calls.api.mockImplementation(async(path:string,options?:{method?:string;body?:unknown})=>{
      if(path.endsWith('/save')){if(++attempts===1)throw new Error('Synthetic lost acknowledgement');return {...chat,revision:3};}
      if(path.endsWith('/draft'))return options?.method==='PUT'?{text:'Latest draft',content_refs:[],revision:1,conversation_revision:2}:{text:'Existing draft',content_refs:[],revision:0,conversation_revision:1};
      if(path.includes('/messages')||path.includes('/study/projects')||path.endsWith('/runs'))return {items:[],next_cursor:null};
      return temporary;
    });
    render(frame(<Chat identity={chat.identity}/>));
    fireEvent.change(await screen.findByLabelText('Message Renulus'),{target:{value:'Latest draft'}});
    fireEvent.click(screen.getByRole('button',{name:'Save conversation'}));
    await waitFor(()=>expect(attempts).toBe(1));
    const first=calls.api.mock.calls.find(([path])=>path.endsWith('/save'))!;
    expect(first[1].body.expected_revision).toBe(2);
    fireEvent.click(screen.getByRole('button',{name:'Try again'}));
    await waitFor(()=>expect(attempts).toBe(2));
    const requests=calls.api.mock.calls.filter(([path])=>path.endsWith('/save'));
    expect(requests[1][1]).toEqual(requests[0][1]);
    expect((screen.getByLabelText('Message Renulus') as HTMLTextAreaElement).value).toBe('Latest draft');
    expect(calls.send).not.toHaveBeenCalled();
  });

  it('flushes the second conversation draft after leaving a failed Save in the first',async()=>{
    setup();let active={...chat,retention:'temporary' as const};
    calls.api.mockImplementation(async(path:string,options?:{method?:string})=>{
      if(path.endsWith('/save'))throw new Error('Synthetic unavailable acknowledgement');
      if(path.endsWith('/draft'))return {text:'Existing draft',content_refs:[],revision:0,conversation_revision:options?.method==='PUT'?2:1};
      if(path.includes('/messages')||path.includes('/study/projects')||path.endsWith('/runs'))return {items:[],next_cursor:null};
      return active;
    });
    const view=render(frame(<Chat identity={active.identity}/>));
    fireEvent.click(await screen.findByRole('button',{name:'Save conversation'}));
    await waitFor(()=>expect(calls.api.mock.calls.filter(([path])=>path.endsWith('/save'))).toHaveLength(1));
    active={...active,identity:{type:'learn_thread',id:'second-temporary'}};
    view.rerender(frame(<Chat identity={active.identity}/>));
    fireEvent.change(await screen.findByLabelText('Message Renulus'),{target:{value:'Second conversation unsaved draft'}});
    fireEvent.click(screen.getByRole('button',{name:'Save conversation'}));
    await waitFor(()=>expect(calls.api.mock.calls.filter(([path])=>path.endsWith('/save'))).toHaveLength(2));
    const saves=calls.api.mock.calls.filter(([path])=>path.endsWith('/save'));
    expect(saves[1][1].body.expected_revision).toBe(2);
    expect(saves[1][1].headers['Idempotency-Key']).not.toBe(saves[0][1].headers['Idempotency-Key']);
  });
  it('carries Study help on reads, drafts and send while Stop stays neutral',async()=>{
    setup();
    const context:StudyHelpContext={attempt_id:'study-attempt',item_id:'current-item',version_id:'pinned-version',draft_revision:4,policy_revision:2,kind:'chat'};
    calls.send.mockImplementation(async(_chat,_input,onEvent)=>{onEvent({run_id:'help-run',sequence:1,type:'started',payload:{}});await new Promise<void>(()=>{});});
    render(frame(<Chat identity={chat.identity} studyHelpContext={context}/>));
    const composer=await screen.findByLabelText('Message Renulus');
    fireEvent.change(composer,{target:{value:'Fictional help request'}});
    await waitFor(()=>expect(calls.api.mock.calls.some(([path,options])=>path.endsWith('/draft')&&options?.method==='PUT')).toBe(true));
    fireEvent.click(screen.getByRole('button',{name:'Send'}));
    await waitFor(()=>expect(calls.send).toHaveBeenCalledTimes(1));
    expect(calls.send.mock.calls[0][4]).toEqual(context);
    fireEvent.click(screen.getByRole('button',{name:'Stop'}));
    await waitFor(()=>expect(calls.api.mock.calls.some(([path])=>path.endsWith('/help-run/cancel'))).toBe(true));
    for(const [path,options] of calls.api.mock.calls){
      if(path.endsWith('/cancel')||path.endsWith('/runs'))expect(options?.headers?.['X-Renulus-Study-Context']).toBeUndefined();
      else expect(options?.headers?.['X-Renulus-Study-Context']).toBe(JSON.stringify(context));
      expect(JSON.stringify(options?.body??{})).not.toContain('study-attempt');
    }
  });

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
