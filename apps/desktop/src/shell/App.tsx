import { useEffect, useRef, useState } from 'react';
import { ArrowRight, Clock, ClipboardCheck, Folder, Library, MessageCircle, MoreHorizontal, PanelLeft, Plus, Search, Settings, Shield, X } from 'lucide-react';
import { IconButton, Button, LoadingState, Notice } from '../ui';
import { AssessmentPolicyProvider, useAssessmentPolicy } from './AssessmentPolicy';
import { api } from '../platform/api';
import type { Health } from '../platform/contracts';
import type { ConversationSummary, ProjectSummary } from '../platform/designC';
import { useResource } from '../platform/useResource';
import { ModuleOutlet } from './ModuleOutlet';
import { NavigationProvider, destinationHash, routes, useNavigation, type RouteId } from './navigation';
import { ShellWorkspaceProvider, WorkspaceHost } from './WorkspaceHost';
import { useWorkspace } from '../modules/workspace';
import { LocalSearchResults, type SearchResult } from './LocalSearchResults';

const primary = [
  { id: 'newchat', Icon: Plus }, { id: 'library', Icon: Library },
  { id: 'tests', Icon: ClipboardCheck }, { id: 'updates', Icon: Clock }, { id: 'more', Icon: MoreHorizontal },
] as const;
function Shell() {
  const { route, revision, scope, navigate, startFreshStudy } = useNavigation();
  const { policy, error: policyError, refresh: refreshPolicy } = useAssessmentPolicy();
  const reading = useWorkspace();
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('renulus.navigation.collapsed') === 'true');
  const [narrow, setNarrow] = useState(() => window.innerWidth <= 900);
  const [drawer, setDrawer] = useState(false);
  const effectiveCollapsed = narrow ? !drawer : collapsed;
  const [query, setQuery] = useState('');
  const searchDialog = useRef<HTMLDialogElement>(null);
  const searchInput = useRef<HTMLInputElement>(null);
  const searchTrigger = useRef<HTMLButtonElement>(null);
  const searchReturn = useRef<HTMLElement | null>(null);
  const searchNavigating = useRef(false);
  const content = useRef<HTMLElement>(null);
  const contentRegion = useRef<HTMLDivElement>(null);
  const navigationToggle = useRef<HTMLButtonElement>(null);
  const { resource } = useResource(signal => api<Health>('/health', { signal }));
  const projects = useResource(signal => api<{ items: ProjectSummary[] }>('/study/projects?limit=30', { signal }));
  const conversations = useResource(signal => api<{ items: ConversationSummary[] }>('/conversations?limit=30', { signal }));
  const label = routes.find(item => item.id === route)!.label;
  const scopeLabel = route === 'chat' ? null : scope.kind === 'saved-case'
    ? 'Saved case snapshot · New changes stay temporary until you Save again.'
    : scope.kind === 'temporary-case'
      ? 'Temporary case context · Only explicitly saved snapshots are kept. New changes require Save.'
      : scope.kind === 'unclassified' ? 'Unclassified context · not saved' : null;
  function openSearch() {
    if (document.querySelector('dialog[open]')) return;
    searchReturn.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    searchNavigating.current = false;
    searchDialog.current?.showModal(); searchInput.current?.focus();
  }
  function toggleNavigation() {
    if (narrow) { setDrawer(value => !value); return; }
    setCollapsed(value => { localStorage.setItem('renulus.navigation.collapsed', String(!value)); return !value; });
  }
  function open(next: RouteId, payload?: Record<string, unknown>) {
    setDrawer(false);
    navigate(next, { payload, freshStudy: next === 'newchat' });
  }
  function chooseResult(result: SearchResult) {
    searchNavigating.current = true; searchDialog.current?.close();
    if (result.identity) open('chat', { conversation: result.identity, retention: 'saved' });
    else if (result.group === 'projects') open('projects', { project_id: result.project_id });
    else if (result.reference) { reading.open(result.reference); setDrawer(false); }
  }
  useEffect(() => {
    const resize = () => { setNarrow(window.innerWidth <= 900); setDrawer(false); };
    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  }, []);
  useEffect(() => {
    document.title = 'Renulus · ' + label;
    content.current?.focus({ preventScroll: true });
    document.scrollingElement?.scrollTo({ top: 0, left: 0 });
  }, [route, revision, label]);
  useEffect(() => {
    const refresh = () => { projects.retry(); conversations.retry(); };
    window.addEventListener('renulus:records-changed', refresh);
    return () => window.removeEventListener('renulus:records-changed', refresh);
  }, [projects.retry, conversations.retry]);
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.ctrlKey && event.key.toLowerCase() === 'k') { event.preventDefault(); openSearch(); }
      if (event.altKey && /^[1-5]$/.test(event.key) && !document.querySelector('dialog[open]')) { event.preventDefault(); open(primary[Number(event.key) - 1].id); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [navigate]);
  const matches = routes.filter(item => item.label.toLowerCase().includes(query.toLowerCase()));
  const projectItems = projects.resource.status === 'ready' ? projects.resource.data.items ?? [] : [];
  const chatItems = conversations.resource.status === 'ready' ? conversations.resource.data.items ?? [] : [];
  return <div className={'desktop-shell design-c-shell' + (effectiveCollapsed ? ' navigation-collapsed' : '') + (narrow && drawer ? ' navigation-drawer-open' : '')}>
    <a className="skip-link" href="#learning-content" onClick={event => { event.preventDefault(); content.current?.focus(); }}>Skip to learning</a>
    <aside className="navigation-rail" id="main-navigation" onKeyDown={event => { if (event.key === 'Escape' && drawer) { setDrawer(false); navigationToggle.current?.focus(); } }}>
      <div className="navigation-brand-row"><a href="#/newchat" className="brand" onClick={event => { event.preventDefault(); open('newchat'); }} aria-label="Renulus home"><img src="./renulus-64.png" width="28" height="28" alt="" /><span>Renulus</span></a>
        <IconButton className="navigation-search" ref={searchTrigger} label="Find a destination" onClick={openSearch}><Search size={20} /></IconButton>
        <IconButton ref={navigationToggle} className="navigation-toggle" label={effectiveCollapsed ? 'Expand navigation' : 'Collapse navigation'} aria-expanded={!effectiveCollapsed} aria-controls="main-navigation" onClick={toggleNavigation}><PanelLeft size={20} /></IconButton>
      </div>
      <nav aria-label="Main navigation">{primary.map(({ id, Icon }, index) => { const text = routes.find(item => item.id === id)!.label; return <a key={id} href={'#/' + id} aria-label={text} title={text + ' · Alt+' + (index + 1)} onClick={event => { event.preventDefault(); open(id); }} aria-current={route === id ? 'page' : undefined}><Icon size={20} aria-hidden="true" /><span>{text}</span></a>; })}</nav>
      <div className="navigation-history" hidden={policy?.assistance_allowed === false}>
        <section className="navigation-projects" aria-label="Projects"><div className="navigation-section-heading"><button onClick={() => open('projects')}>Projects</button><IconButton label="New project" onClick={() => open('projects', { create: true })}><Plus size={18} /></IconButton></div>
          {projects.resource.status === 'loading' && <p className="navigation-empty" role="status">Loading projects…</p>}
          {projects.resource.status === 'error' && <button className="navigation-empty" onClick={projects.retry}>Retry projects</button>}
          {projects.resource.status === 'ready' && !projectItems.length && <p className="navigation-empty">Create a project to organise your study.</p>}
          {projectItems.map(project => <a key={project.id} href={destinationHash('projects', { project_id: project.id })} onClick={event => { event.preventDefault(); open('projects', { project_id: project.id }); }}><Folder size={20} aria-hidden="true" /><span>{project.title}</span></a>)}
        </section>
        <section className="navigation-recents" aria-label="Recent chats"><div className="navigation-section-heading">Recent chats</div>
          {conversations.resource.status === 'loading' && <p className="navigation-empty" role="status">Loading chats…</p>}
          {conversations.resource.status === 'error' && <button className="navigation-empty" onClick={conversations.retry}>Retry chats</button>}
          {conversations.resource.status === 'ready' && !chatItems.length && <p className="navigation-empty">Saved conversations will appear here.</p>}
          {chatItems.filter(chat => !chat.project_id).map(chat => <a key={chat.identity.type + ':' + chat.identity.id} href={destinationHash('chat', { conversation: chat.identity, retention: 'saved' })} onClick={event => { event.preventDefault(); open('chat', { conversation: chat.identity, retention: 'saved' }); }}><MessageCircle size={20} aria-hidden="true" /><span>{chat.title}</span></a>)}
        </section>
      </div>
      <div className="rail-footer"><a href="#/connections" aria-label="Settings & connections" title="Settings & connections" onClick={event => { event.preventDefault(); open('connections'); }}><Settings size={20} aria-hidden="true" /><span>Settings & connections</span><span className={'status-dot status-' + resource.status} aria-label={resource.status === 'ready' ? 'Local runtime ready' : 'Local runtime unavailable'} /></a></div>
    </aside>
    <div className="workspace">
      <header className="workspace-header"><p className="workspace-destination">{label}</p><div className="workspace-header-actions"><Button variant="ghost" disabled={!policy?.assistance_allowed} onClick={() => window.dispatchEvent(new Event('renulus:workspace-toggle'))}><PanelLeft size={20} aria-hidden="true" />Workspace</Button></div></header>
      {scopeLabel && <div className="scope-banner" role="status"><Shield size={17} aria-hidden="true" /><p>{scopeLabel}</p><Button variant="ghost" onClick={startFreshStudy}>End temporary context</Button></div>}
      <div className="shell-content" ref={contentRegion}><main className="workspace-main" id="learning-content" aria-label={label} tabIndex={-1} ref={content}>
        {route === 'connections' || route === 'attempts' ? <ModuleOutlet /> : !policy ? policyError
          ? <Notice><p>The local assessment state could not be checked.</p><div className="actions"><Button variant="secondary" onClick={refreshPolicy}>Retry</Button><Button variant="ghost" onClick={() => open('connections')}>Settings & connections</Button></div></Notice> : <LoadingState />
          : policy.assistance_allowed ? <ModuleOutlet /> : <Notice><p>A Test is in progress. Submit it to return to chat, readers and study help.</p><div className="actions"><Button onClick={() => open('attempts', { attempt_id: policy.active_test_id })}>Resume Test</Button><Button variant="ghost" onClick={() => open('connections')}>Settings & connections</Button></div></Notice>}
      </main><WorkspaceHost contentRef={contentRegion} /></div>
    </div>
    <dialog ref={searchDialog} className="destination-dialog" aria-labelledby="search-title" onClose={() => {
      setQuery('');
      if (searchNavigating.current) content.current?.focus({ preventScroll: true });
      else (searchReturn.current?.isConnected ? searchReturn.current : searchTrigger.current)?.focus();
      searchNavigating.current = false;
    }}><div className="dialog-heading"><h2 id="search-title">Find in Renulus</h2><IconButton label="Close destination search" onClick={() => searchDialog.current?.close()}><X size={19} /></IconButton></div><label className="sr-only" htmlFor="destination-search">Search destinations</label><input ref={searchInput} className="input" id="destination-search" value={query} maxLength={200} onChange={event => setQuery(event.target.value)} placeholder="Chats, projects, files…" /><div className="destination-results">{matches.map(item => <button key={item.id} onClick={() => { searchNavigating.current = true; searchDialog.current?.close(); open(item.id); }}><strong>{item.label}</strong><ArrowRight size={16} aria-hidden="true" /></button>)}{!matches.length && <p role="status">No destinations match.</p>}</div>
      <LocalSearchResults query={query} permitted={policy?.assistance_allowed === true} policyRevision={policy?.revision ?? 0} projects={projectItems} onSelect={chooseResult} />
    </dialog>
  </div>;
}
export function App() { return <NavigationProvider><AssessmentPolicyProvider><ShellWorkspaceProvider><Shell /></ShellWorkspaceProvider></AssessmentPolicyProvider></NavigationProvider>; }
