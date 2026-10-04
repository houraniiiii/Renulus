import { useEffect, useRef, useState } from 'react';
import { ArrowRight, BookOpen, ChevronRight, Home, Layers3, Library, MessageCircle, PanelLeft, Plug, Search, Shield, Stethoscope, X, Newspaper } from 'lucide-react';
import { IconButton, Button } from '../ui';
import { api } from '../platform/api';
import type { Health } from '../platform/contracts';
import { useResource } from '../platform/useResource';
import { ModuleOutlet } from './ModuleOutlet';
import { NavigationProvider, routes, useNavigation } from './navigation';

const icons = [Home, MessageCircle, Library, Stethoscope, Layers3, BookOpen, Newspaper, Plug];
function Shell() {
  const { route, scope, navigate, startFreshStudy } = useNavigation();
  const [railOpen, setRailOpen] = useState(false);
  const [query, setQuery] = useState('');
  const searchDialog = useRef<HTMLDialogElement>(null);
  const searchTrigger = useRef<HTMLButtonElement>(null);
  const content = useRef<HTMLElement>(null);
  const { resource } = useResource(signal => api<Health>('/health', { signal }));
  const label = routes.find(item => item.id === route)!.label;
  const temporary = scope.kind === 'temporary-case' || scope.kind === 'unclassified';
  function openSearch() { if (!searchDialog.current?.open) searchDialog.current?.showModal(); }
  useEffect(() => {
    document.title = 'Renulus · ' + label;
    content.current?.focus({ preventScroll: true });
    content.current?.scrollTo({ top: 0 });
    setRailOpen(false);
  }, [route, label]);
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.ctrlKey && event.key.toLowerCase() === 'k') { event.preventDefault(); openSearch(); }
      if (event.altKey && /^[1-8]$/.test(event.key) && !searchDialog.current?.open) { event.preventDefault(); navigate(routes[Number(event.key) - 1].id); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [navigate]);
  const matches = routes.filter(item => item.label.toLowerCase().includes(query.toLowerCase()));
  const runtimeLabel = resource.status === 'ready' ? 'Local runtime ready' : resource.status === 'loading' ? 'Checking local runtime' : 'Local runtime unavailable';
  return <div className="desktop-shell">
    <a className="skip-link" href="#learning-content" onClick={event => { event.preventDefault(); content.current?.focus(); }}>Skip to learning</a>
    <aside className={'navigation-rail' + (railOpen ? ' rail-open' : '')} id="main-navigation">
      <a href="#/study" className="brand" onClick={event => { event.preventDefault(); navigate('study'); }} aria-label="Renulus home"><img src="./renulus-64.png" width="34" height="34" alt="" /><span>Renulus</span></a>
      <nav aria-label="Main navigation">{routes.map((item, index) => { const Icon = icons[index]; return <a key={item.id} href={'#/' + item.id} onClick={event => { event.preventDefault(); navigate(item.id); }} aria-current={route === item.id ? 'page' : undefined} title={'Alt+' + (index + 1)}><Icon size={19} aria-hidden="true" /><span>{item.label}</span></a>; })}</nav>
      <div className="rail-footer"><button className="runtime-status" onClick={() => navigate('connections')}><span className={'status-dot status-' + resource.status} aria-hidden="true" />{runtimeLabel}</button><p>Learning across nephrology</p></div>
    </aside>
    <div className="workspace">
      <header className="workspace-header"><div className="workspace-breadcrumb"><IconButton className="mobile-rail-toggle" label={railOpen ? 'Close navigation' : 'Open navigation'} aria-expanded={railOpen} aria-controls="main-navigation" onClick={() => setRailOpen(value => !value)}><PanelLeft size={20} /></IconButton><span>Learning space</span><ChevronRight size={14} aria-hidden="true" /><strong>{label}</strong></div><button className="search-trigger" ref={searchTrigger} onClick={openSearch}><Search size={17} aria-hidden="true" /><span>Find a destination</span><kbd>Ctrl K</kbd></button></header>
      {temporary && <div className="scope-banner" role="status"><Shield size={17} aria-hidden="true" /><p>Temporary case · not saved</p><Button variant="ghost" onClick={startFreshStudy}>End temporary context</Button></div>}
      <main className="workspace-main" id="learning-content" tabIndex={-1} ref={content}><ModuleOutlet /></main>
      <footer className="workspace-footer"><span><img src="./renulus-64.png" width="14" height="14" alt="" />Learning across nephrology</span><span>{temporary ? 'Temporary context' : 'Your learning space'}</span><details className="shortcut-help"><summary>Keyboard</summary><div><strong>Move through Renulus</strong><p><kbd>Ctrl K</kbd> Find a destination</p><p><kbd>Alt 1–8</kbd> Open a destination</p><p><kbd>Esc</kbd> Close destination search</p></div></details></footer>
    </div>
    <dialog ref={searchDialog} className="destination-dialog" aria-labelledby="search-title" onClose={() => { setQuery(''); searchTrigger.current?.focus(); }}><div className="dialog-heading"><h2 id="search-title">Where would you like to go?</h2><IconButton label="Close destination search" onClick={() => searchDialog.current?.close()}><X size={19} /></IconButton></div><label className="sr-only" htmlFor="destination-search">Search destinations</label><input autoFocus className="input" id="destination-search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Learn, Library, Cases…" /><div className="destination-results">{matches.map(item => <button key={item.id} onClick={() => { searchDialog.current?.close(); navigate(item.id); }}><strong>{item.label}</strong><ArrowRight size={16} aria-hidden="true" /></button>)}{!matches.length && <p role="status">No destinations match. Try Learn or Library.</p>}</div></dialog>
  </div>;
}
export function App() { return <NavigationProvider><Shell /></NavigationProvider>; }
