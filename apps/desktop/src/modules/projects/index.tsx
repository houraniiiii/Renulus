import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ArrowLeft, ArrowRight, Archive, Plus, Trash2 } from 'lucide-react';
import { api, isCancelled } from '../../platform/api';
import type { ConversationIdentity, ConversationSummary, PageResult, ProjectSummary } from '../../platform/designC';
import type { LibraryDocument } from '../library/types';
import { createConversation, conversationPath } from '../chat/api';
import { useWorkspace } from '../workspace';
import { Badge, Button, EmptyState, ErrorState, Input, LoadingState, Notice, PageHeader, Select, Textarea } from '../../ui';
import './projects.css';

interface Goal {id:string; title:string; topic_id:string|null; target_date:string|null; status:'active'|'completed'; revision:number; progress:{manual_intent?:string|null; evidence_ids?:string[]}}
interface ProjectDocument {id:string; revision_id:string; title:string; status:string; position:number}
interface Project extends ProjectSummary {chats:ConversationSummary[]; documents:ProjectDocument[]; goals:Goal[]}
interface Props {projectId?:string; onOpenConversation?:(identity:ConversationIdentity)=>void}
const pathFor=(id:string)=>'/study/projects/'+encodeURIComponent(id);
const changed=()=>window.dispatchEvent(new Event('renulus:records-changed'));
const options=()=>({'Idempotency-Key':crypto.randomUUID()});
const tabs=['Chats','Documents','Study goals'] as const;
type Tab=typeof tabs[number];

/** Projects remain a collection of explicit links and personal study intentions. */
export default function Projects({projectId,onOpenConversation}:Props) {
  const workspace=useWorkspace();
  const [projects,setProjects]=useState<ProjectSummary[]>([]);
  const [cursor,setCursor]=useState<string|null>(null);
  const [lifecycle,setLifecycle]=useState<'active'|'archived'>('active');
  const [selected,setSelected]=useState(projectId);
  const [project,setProject]=useState<Project>();
  const [tab,setTab]=useState<Tab>('Chats');
  const [title,setTitle]=useState('');
  const [newTitle,setNewTitle]=useState('');
  const [loading,setLoading]=useState(true);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState<unknown>();
  const [chats,setChats]=useState<ConversationSummary[]>([]);
  const [chatCursor,setChatCursor]=useState<string|null>(null);
  const [pickedChat,setPickedChat]=useState('');
  const [moveTargets,setMoveTargets]=useState<Record<string,string>>({});
  const [activeProjects,setActiveProjects]=useState<ProjectSummary[]>([]);
  const [library,setLibrary]=useState<LibraryDocument[]>([]);
  const [libraryOffset,setLibraryOffset]=useState(0);
  const [libraryTotal,setLibraryTotal]=useState(0);
  const [pickedDocument,setPickedDocument]=useState('');
  const [goal,setGoal]=useState<Goal>();
  const [goalTitle,setGoalTitle]=useState('');
  const [goalDate,setGoalDate]=useState('');
  const [goalIntent,setGoalIntent]=useState('');
  const [deleteProject,setDeleteProject]=useState(false);
  const dialog=useRef<HTMLDialogElement>(null);
  const epoch=useRef(0);
  const current=useRef<Project|undefined>(undefined);current.current=project;

  useEffect(()=>{setSelected(projectId);},[projectId]);
  useEffect(()=>{
    const controller=new AbortController(),version=++epoch.current;
    setLoading(true);setError(undefined);setProject(undefined);setGoal(undefined);
    async function read(){
      try{
        if(selected){
          const value=await api<Project>(pathFor(selected),{signal:controller.signal});
          if(version!==epoch.current)return;
          setProject(value);setTitle(value.title);
          const active=await api<PageResult<ProjectSummary>>('/study/projects?limit=100',{signal:controller.signal});
          if(version===epoch.current)setActiveProjects(active.items);
        }else{
          const result=await api<PageResult<ProjectSummary>>('/study/projects?limit=30&lifecycle='+lifecycle,{signal:controller.signal});
          if(version===epoch.current){setProjects(result.items);setCursor(result.next_cursor);}
        }
      }catch(caught){if(version===epoch.current&&!isCancelled(caught))setError(caught);}
      finally{if(version===epoch.current)setLoading(false);}
    }
    void read();
    return()=>{controller.abort();epoch.current++;};
  },[selected,lifecycle]);

  useEffect(()=>{
    if(!project)return;
    const controller=new AbortController(),version=epoch.current;
    async function choices(){
      try{
        if(tab==='Chats'){
          const page=await api<PageResult<ConversationSummary>>('/conversations?limit=100',{signal:controller.signal});
          if(version===epoch.current){setChats(page.items);setChatCursor(page.next_cursor);setPickedChat('');}
        }else if(tab==='Documents'){
          const page=await api<{documents:LibraryDocument[];total:number}>('/library/documents?limit=25&offset=0&status=ready',{signal:controller.signal});
          if(version===epoch.current){setLibrary(page.documents);setLibraryTotal(page.total);setLibraryOffset(page.documents.length);setPickedDocument('');}
        }
      }catch(caught){if(version===epoch.current&&!isCancelled(caught))setError(caught);}
    }
    void choices();return()=>controller.abort();
  },[project?.id,tab]);
  useEffect(()=>{if(deleteProject)dialog.current?.showModal();},[deleteProject]);

  async function refresh(id:string,version:number){
    const value=await api<Project>(pathFor(id));
    if(version===epoch.current){setProject(value);setTitle(value.title);}
  }
  async function perform(action:(value:Project)=>Promise<unknown>){
    const value=current.current;if(!value||busy)return;
    const version=epoch.current;setBusy(true);setError(undefined);
    try{await action(value);changed();await refresh(value.id,version);return true;}
    catch(caught){if(version===epoch.current)setError(caught);return false;}
    finally{if(version===epoch.current)setBusy(false);}
  }
  async function create(event:FormEvent){
    event.preventDefault();if(!newTitle.trim()||busy)return;
    setBusy(true);setError(undefined);
    try{const value=await api<ProjectSummary>('/study/projects',{method:'POST',body:{title:newTitle.trim()},headers:options()});changed();setSelected(value.id);setNewTitle('');}
    catch(caught){setError(caught);}finally{setBusy(false);}
  }
  async function moreProjects(){
    if(!cursor)return;const version=epoch.current;
    try{const page=await api<PageResult<ProjectSummary>>('/study/projects?limit=30&lifecycle='+lifecycle+'&cursor='+encodeURIComponent(cursor));if(version===epoch.current){setProjects(previous=>[...previous,...page.items.filter(item=>!previous.some(old=>old.id===item.id))]);setCursor(page.next_cursor);}}catch(caught){setError(caught);}
  }
  async function moreChats(){
    if(!chatCursor)return;const version=epoch.current;
    try{const page=await api<PageResult<ConversationSummary>>('/conversations?limit=100&cursor='+encodeURIComponent(chatCursor));if(version===epoch.current){setChats(previous=>[...previous,...page.items.filter(item=>!previous.some(old=>old.identity.type===item.identity.type&&old.identity.id===item.identity.id))]);setChatCursor(page.next_cursor);}}catch(caught){setError(caught);}
  }
  async function moreLibrary(){
    const version=epoch.current;
    try{const page=await api<{documents:LibraryDocument[];total:number}>('/library/documents?limit=25&status=ready&offset='+libraryOffset);if(version===epoch.current){setLibrary(previous=>[...previous,...page.documents.filter(item=>!previous.some(old=>old.id===item.id))]);setLibraryOffset(previous=>previous+page.documents.length);setLibraryTotal(page.total);}}catch(caught){setError(caught);}
  }
  const move=(chat:ConversationSummary,target:string|null)=>perform(()=>api(conversationPath(chat)+'/project',{method:'PUT',body:{expected_revision:chat.revision,project_id:target},headers:options()}));
  function editGoal(value?:Goal){setGoal(value);setGoalTitle(value?.title??'');setGoalDate(value?.target_date??'');setGoalIntent(value?.progress.manual_intent??'');}
  async function saveGoal(event:FormEvent){
    event.preventDefault();if(!goalTitle.trim())return;
    const version=epoch.current;
    const saved=await perform(value=>api(pathFor(value.id)+'/goals'+(goal?'/'+encodeURIComponent(goal.id):''),{method:goal?'PUT':'POST',headers:options(),body:{expected_revision:value.revision,...(goal?{goal_revision:goal.revision}:{}),title:goalTitle.trim(),topic_id:goal?.topic_id??null,target_date:goalDate||null,status:goal?.status??'active',progress:{evidence_ids:goal?.progress.evidence_ids??[],manual_intent:goalIntent.trim()||null}}}));
    if(saved&&version===epoch.current)editGoal();
  }
  async function removeProject(){
    const value=current.current;if(!value)return;
    try{await api(pathFor(value.id)+'?expected_revision='+value.revision,{method:'DELETE',headers:options()});changed();setSelected(undefined);}
    catch(caught){setError(caught);}
    setDeleteProject(false);dialog.current?.close();
  }
  if(loading)return <LoadingState label="Opening projects"/>;
  if(!project)return <section className="projects-page"><PageHeader title="Projects" description="Keep related conversations, shared documents and study goals together."/>
    <form className="project-create" onSubmit={event=>void create(event)}><Input label="New project name" value={newTitle} onChange={event=>setNewTitle(event.target.value)} maxLength={120}/><Button type="submit" busy={busy} disabled={!newTitle.trim()}><Plus size={16}/>Create project</Button></form>
    <Select label="Show projects" value={lifecycle} onChange={event=>setLifecycle(event.target.value as 'active'|'archived')}><option value="active">Active</option><option value="archived">Archived</option></Select>
    {Boolean(error)&&<ErrorState error={error}/>}<div className="project-list">{projects.map(value=><button className="project-list-row" key={value.id} onClick={()=>{setSelected(value.id);setTab('Chats');}}><strong>{value.title}</strong><span>{value.lifecycle==='archived'?'Archived':'Open project'}<ArrowRight size={18}/></span></button>)}</div>
    {!error&&projects.length===0&&<EmptyState title={lifecycle==='archived'?'No archived projects':'Give your study a home'}><p>Create a project when a few conversations or sources belong together. Saved chats can also stay unassigned.</p></EmptyState>}{cursor&&<Button variant="secondary" onClick={()=>void moreProjects()}>Load more projects</Button>}</section>;
  const archived=project.lifecycle==='archived';
  const availableChats=chats.filter(chat=>chat.project_id!==project.id);
  const availableDocuments=library.filter(document=>document.active_revision&&!document.reserved&&(!document.scope||document.scope.kind==='personal-library')&&!project.documents.some(link=>link.revision_id===document.active_revision));
  return <section className="projects-page" aria-label="Project">
    <Button variant="ghost" className="project-back" onClick={()=>setSelected(undefined)}><ArrowLeft size={16}/>All projects</Button>
    <header className="project-heading"><div><p className="project-eyebrow">Project</p><h1>{project.title}</h1></div><div className="project-management"><Badge>{archived?'Archived':'Active'}</Badge><details><summary>Manage project</summary><div className="project-manage-form"><Input label="Project name" value={title} onChange={event=>setTitle(event.target.value)} maxLength={120}/><Button variant="secondary" disabled={busy||!title.trim()} onClick={()=>void perform(value=>api(pathFor(value.id),{method:'PATCH',body:{expected_revision:value.revision,title:title.trim()},headers:options()}))}>Rename project</Button><Button variant="ghost" disabled={busy} onClick={()=>void perform(value=>api(pathFor(value.id)+(archived?'/restore':'/archive'),{method:'POST',body:{expected_revision:value.revision},headers:options()}))}><Archive size={16}/>{archived?'Restore project':'Archive project'}</Button><Button variant="danger" disabled={busy} onClick={()=>setDeleteProject(true)}><Trash2 size={16}/>Delete project</Button></div></details></div></header>
    {archived&&<Notice>Restore this project to add or change its study work.</Notice>}
    <div className="project-tabs" role="tablist" aria-label="Project sections">{tabs.map(value=><button key={value} role="tab" id={'project-tab-'+value.replaceAll(' ','-')} aria-controls="project-section" aria-selected={tab===value} onClick={()=>{setTab(value);setError(undefined);}}>{value}</button>)}</div>
    {Boolean(error)&&<ErrorState error={error}/>}
    <div role="tabpanel" id="project-section" aria-labelledby={'project-tab-'+tab.replaceAll(' ','-')}>
      {tab==='Chats'&&<><div className="project-section-heading"><h2>Conversations</h2><div className="actions"><Button variant="secondary" disabled={busy||archived} onClick={()=>void perform(async value=>{const chat=await createConversation({project_id:value.id});changed();onOpenConversation?.(chat.identity);})}><Plus size={16}/>New learning chat</Button><Button variant="ghost" disabled={busy||archived} onClick={()=>void perform(async value=>{const chat=await createConversation({kind:'case',project_id:value.id});changed();onOpenConversation?.(chat.identity);})}>New case chat</Button></div></div>
        {project.chats.length===0&&<p className="project-empty">No conversations here yet. Create one or add an existing saved chat.</p>}
        <div className="project-rows">{project.chats.map(chat=><article className="project-row" key={chat.identity.type+':'+chat.identity.id}><button className="project-open-row" onClick={()=>onOpenConversation?.(chat.identity)}><strong>{chat.title}</strong><span>{chat.kind==='case'?'Case discussion':'Learning conversation'}{chat.lifecycle==='archived'?' · archived':''}</span></button><div className="project-row-actions"><Select label={'Move '+chat.title+' to'} value={moveTargets[chat.identity.id]??''} disabled={busy||archived} onChange={event=>setMoveTargets(previous=>({...previous,[chat.identity.id]:event.target.value}))}><option value="">Unassigned</option>{activeProjects.filter(value=>value.id!==project.id).map(value=><option key={value.id} value={value.id}>{value.title}</option>)}</Select><Button variant="ghost" disabled={busy||archived} onClick={()=>void move(chat,moveTargets[chat.identity.id]||null)}>Move</Button></div></article>)}</div>
        <div className="project-link-form"><Select label="Add saved conversation" value={pickedChat} disabled={archived||busy} onChange={event=>setPickedChat(event.target.value)}><option value="">Choose a saved chat</option>{availableChats.map(chat=><option key={chat.identity.type+':'+chat.identity.id} value={chat.identity.type+':'+chat.identity.id}>{chat.title}{chat.project_id?' · move from another project':''}</option>)}</Select><Button variant="secondary" disabled={!pickedChat||busy||archived} onClick={()=>{const chat=availableChats.find(value=>value.identity.type+':'+value.identity.id===pickedChat);if(chat)void move(chat,project.id);}}>Add to project</Button></div>{chatCursor&&<Button variant="ghost" onClick={()=>void moreChats()}>Load more saved chats</Button>}</>}
      {tab==='Documents'&&<><div className="project-section-heading"><h2>Shared documents</h2></div><p className="project-description">Linked Library revisions provide context for future requests. Each original stays in your Library.</p>{project.documents.length===0&&<p className="project-empty">No linked documents yet.</p>}<div className="project-rows">{project.documents.map(document=><article className="project-row" key={document.id}><button className="project-open-row" onClick={()=>workspace.open({target:{type:'library_revision',id:document.revision_id}})}><strong>{document.title}</strong><span>{document.status==='ready'?'Library revision':document.status}</span></button><Button variant="ghost" disabled={archived||busy} onClick={()=>void perform(value=>api(pathFor(value.id)+'/documents/'+encodeURIComponent(document.revision_id)+'?expected_revision='+value.revision,{method:'DELETE',headers:options()}))}>Unlink</Button></article>)}</div><div className="project-link-form"><Select label="Link Library document" value={pickedDocument} disabled={busy||archived} onChange={event=>setPickedDocument(event.target.value)}><option value="">Choose a ready document</option>{availableDocuments.map(document=><option key={document.id} value={document.active_revision!}>{document.title}</option>)}</Select><Button variant="secondary" disabled={!pickedDocument||busy||archived} onClick={()=>void perform(value=>api(pathFor(value.id)+'/documents',{method:'PUT',headers:options(),body:{expected_revision:value.revision,revision_id:pickedDocument,position:project.documents.length}}))}>Link document</Button></div>{libraryOffset<libraryTotal&&<Button variant="ghost" onClick={()=>void moreLibrary()}>Load more Library documents</Button>}{availableDocuments.length===0&&<p className="project-description">Import a source into Library and wait for it to become ready before linking it.</p>}</>}
      {tab==='Study goals'&&<><div className="project-section-heading"><h2>Study intentions</h2></div><p className="project-description">Record what you want to study and mark your own progress. Linked activity is evidence of work, rather than a mastery score.</p><div className="project-rows">{project.goals.map(value=><article className="project-row project-goal" key={value.id}><div><strong>{value.title}</strong><p>{value.status==='completed'?'Marked complete':'Active goal'}{value.target_date?' · target '+value.target_date:''}</p>{value.progress.manual_intent&&<p>{value.progress.manual_intent}</p>}{Boolean(value.progress.evidence_ids?.length)&&<span>{value.progress.evidence_ids!.length} linked learning record{value.progress.evidence_ids!.length===1?'':'s'}</span>}</div><div className="actions"><Button variant="ghost" disabled={busy||archived} onClick={()=>editGoal(value)}>Edit</Button><Button variant="secondary" disabled={busy||archived} onClick={()=>void perform(project=>api(pathFor(project.id)+'/goals/'+value.id,{method:'PUT',headers:options(),body:{expected_revision:project.revision,goal_revision:value.revision,title:value.title,topic_id:value.topic_id,target_date:value.target_date,status:value.status==='completed'?'active':'completed',progress:{...value.progress,manual_intent:value.progress.manual_intent??(value.status==='completed'?'Reopened for further study':'Marked complete by me')}}}))}>{value.status==='completed'?'Reopen goal':'Mark complete'}</Button><Button variant="ghost" disabled={busy||archived} onClick={()=>void perform(project=>api(pathFor(project.id)+'/goals/'+value.id+'?expected_revision='+project.revision+'&goal_revision='+value.revision,{method:'DELETE',headers:options()}))}>Remove goal</Button></div></article>)}</div>
        <form className="project-goal-form" onSubmit={event=>void saveGoal(event)}><h3>{goal?'Edit study goal':'Add a study goal'}</h3><Input label="Study goal" value={goalTitle} disabled={archived||busy} onChange={event=>setGoalTitle(event.target.value)} maxLength={240}/><Input label="Target date (optional)" type="date" disabled={archived||busy} value={goalDate} onChange={event=>setGoalDate(event.target.value)}/><Textarea label="My progress or next step (optional)" disabled={archived||busy} value={goalIntent} onChange={event=>setGoalIntent(event.target.value)} maxLength={2000}/><div className="actions"><Button type="submit" disabled={archived||busy||!goalTitle.trim()}>{goal?'Save goal':'Add goal'}</Button>{goal&&<Button variant="ghost" onClick={()=>editGoal()}>Cancel edit</Button>}</div></form></>}
    </div>
    <dialog ref={dialog} className="project-delete-dialog" onCancel={()=>setDeleteProject(false)}><h2>Delete this project?</h2><p>Its goals and memberships will be removed. Your conversations and Library originals remain available.</p><div className="actions"><Button variant="secondary" onClick={()=>{setDeleteProject(false);dialog.current?.close();}}>Keep project</Button><Button variant="danger" onClick={()=>void removeProject()}>Delete project</Button></div></dialog>
  </section>;
}
