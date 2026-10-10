// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ConversationSummary } from '../../platform/designC';
import type { CaseSession } from '../cases/types';
import { ApiError } from '../../platform/api';
import { CaseContext } from './CaseContext';

const calls=vi.hoisted(()=>({api:vi.fn()}));
vi.mock('../../platform/api',async()=>({...await vi.importActual('../../platform/api'),api:calls.api}));
const chat:ConversationSummary={identity:{type:'case',id:'saved-case'},kind:'case',retention:'saved',lifecycle:'active',revision:2,title:'Fictional Case',project_id:null,created_at:'2026-10-10T00:00:00Z',updated_at:'2026-10-10T00:00:00Z'};
const session:CaseSession={id:'saved-case',kind:'daily',title:chat.title,text:'',revision:4,scope:{kind:'saved-case',entity_id:'saved-case'},saved:true,dirty:false,saved_at:chat.created_at,created_at:chat.created_at,updated_at:chat.updated_at,active_run_id:null,messages:[],teaching:null,attachments:[]};
afterEach(()=>cleanup());

describe('Case context inside Chat',()=>{
  it('keeps a failed context edit and saves through both owner revisions without sending',async()=>{
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
    render(<CaseContext conversation={chat} disabled={false} beforeChange={before} onChanged={changed} onStartTeaching={vi.fn()}/>);
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
});
