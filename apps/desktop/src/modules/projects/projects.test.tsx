// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { WorkspaceProvider } from '../workspace';
import Projects from './index';

const calls=vi.hoisted(()=>({api:vi.fn()}));
vi.mock('../../platform/api',async()=>({...await vi.importActual('../../platform/api'),api:calls.api}));
afterEach(()=>cleanup());
function setup(){
  let project={id:'project-a',title:'Fictional glomerular study',lifecycle:'active',revision:1,chats:[],documents:[] as Record<string,unknown>[],goals:[] as Record<string,unknown>[]};
  calls.api.mockReset();
  calls.api.mockImplementation(async(path:string,options?:{method?:string;body?:Record<string,unknown>})=>{
    if(path==='/study/projects/project-a'&&!options?.method)return structuredClone(project);
    if(path.startsWith('/study/projects?'))return {items:[project],next_cursor:null};
    if(path.startsWith('/conversations?'))return {items:[],next_cursor:null};
    if(path.startsWith('/library/documents?'))return {documents:[{id:'library-a',title:'Fictional shared guideline',reserved:false,scope:{kind:'personal-library'},active_revision:'revision-a'}],total:1};
    if(path==='/study/projects/project-a/documents')project.documents=[{id:'link-a',revision_id:'revision-a',title:'Fictional shared guideline',status:'ready',position:0}];
    if(path.startsWith('/study/projects/project-a/documents/')&&options?.method==='DELETE')project.documents=[];
    if(path==='/study/projects/project-a/goals')project.goals=[{id:'goal-a',revision:1,...options?.body}];
    if(path==='/study/projects/project-a/goals/goal-a')project.goals=[{...project.goals[0],...options?.body,revision:2}];
    project={...project,revision:project.revision+1};
    return project;
  });
}
const frame=(element:React.ReactNode)=><WorkspaceProvider policy={{revision:1,active_test_id:null,assistance_allowed:true}}>{element}</WorkspaceProvider>;

describe('Projects explicit membership and goals',()=>{
  it('links and unlinks a shared Library revision without an original deletion request',async()=>{
    setup();render(frame(<Projects projectId="project-a"/>));
    await screen.findByRole('heading',{name:'Fictional glomerular study'});
    fireEvent.click(screen.getByRole('tab',{name:'Documents'}));
    await screen.findByRole('option',{name:'Fictional shared guideline'});
    fireEvent.change(screen.getByLabelText('Link Library document'),{target:{value:'revision-a'}});
    fireEvent.click(screen.getByRole('button',{name:'Link document'}));
    await screen.findByRole('button',{name:'Unlink'});
    expect(calls.api.mock.calls.some(([path,options])=>path==='/study/projects/project-a/documents'&&options.body.revision_id==='revision-a')).toBe(true);
    fireEvent.click(screen.getByRole('button',{name:'Unlink'}));
    await waitFor(()=>expect(screen.queryByRole('button',{name:'Unlink'})).toBeNull());
    expect(calls.api.mock.calls.some(([path,options])=>path.startsWith('/library/')&&options?.method==='DELETE')).toBe(false);
  });

  it('records manual goal progress and explicitly marks completion without a percentage',async()=>{
    setup();render(frame(<Projects projectId="project-a"/>));
    await screen.findByRole('heading',{name:'Fictional glomerular study'});
    fireEvent.click(screen.getByRole('tab',{name:'Study goals'}));
    fireEvent.change(screen.getByLabelText('Study goal'),{target:{value:'Review proteinuria evidence'}});
    fireEvent.change(screen.getByLabelText('My progress or next step (optional)'),{target:{value:'Read my linked source and discuss it'}});
    fireEvent.click(screen.getByRole('button',{name:'Add goal'}));
    await screen.findByText('Review proteinuria evidence');
    expect(calls.api.mock.calls.find(([path])=>path.endsWith('/goals'))?.[1].body.progress).toEqual({evidence_ids:[],manual_intent:'Read my linked source and discuss it'});
    fireEvent.click(screen.getByRole('button',{name:'Mark complete'}));
    expect(await screen.findByText('Marked complete')).toBeTruthy();
    expect(screen.queryByText(/%/)).toBeNull();
    expect(calls.api.mock.calls.find(([path])=>path.endsWith('/goals/goal-a'))?.[1].body.status).toBe('completed');
  });
});
