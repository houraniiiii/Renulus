import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Plus, Search, X } from 'lucide-react';
import { api } from '../../platform/api';
import { useNavigation } from '../../shell/navigation';
import { Button, EmptyState, ErrorState, Input, LoadingState, Notice, PageHeader } from '../../ui';
import { AddFact } from './AddFact';
import { FactItem } from './FactItem';
import { IndexStatus } from './IndexStatus';
import { useMemoryRequest, useMemoryResource } from './requests';
import type { DeleteResult, Fact, PurgeResult, SearchResult } from './types';
import './memory.css';

// Intent: a nephrologist reviews the learning they chose to keep. The open, readable list is the focal surface.
// Hierarchy uses Source Sans weights and Flow ink; teal is reserved for actions. Paper, quiet lines and
// the shared 4px spacing scale keep the editor in the list and provenance/recovery secondary.
function StudyMemory() {
  const facts = useMemoryResource(signal => api<{ records: Fact[] }>('/memory/facts', { signal }));
  const [adding, setAdding] = useState(false);
  const page = useRef<HTMLDivElement>(null);
  const listHeading = useRef<HTMLHeadingElement>(null);
  const addWasOpen = useRef(false);
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState<(SearchResult & { query: string })>();
  const [notice, setNotice] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);
  const searchRequest = useMemoryRequest();
  const records = search?.records ?? facts.data?.records;
  useEffect(() => {
    if (addWasOpen.current && !adding) page.current?.querySelector<HTMLButtonElement>('[data-memory-add-trigger]')?.focus();
    addWasOpen.current = adding;
  }, [adding]);

  function resetSearch() { searchRequest.cancel(); setSearch(undefined); }
  function find(event: FormEvent) {
    event.preventDefault();
    const text = query.trim();
    if (!text || searchRequest.busy) return;
    setSearch(undefined); setNotice('');
    void searchRequest.run(signal => api<SearchResult>('/memory/search', { method: 'POST', signal, body: { query: text, scope: { kind: 'study' }, limit: 10 } }), result => setSearch({ ...result, query: text }));
  }
  function changed(fact: Fact) {
    resetSearch();
    facts.update(previous => previous ? { records: previous.records.some(record => record.id === fact.id) ? previous.records.map(record => record.id === fact.id ? fact : record) : [fact, ...previous.records] } : { records: [fact] });
    setRefreshKey(value => value + 1);
    setNotice(fact.purge_pending ? 'Learning saved. Recall cleanup is pending.' : 'Learning saved.');
  }
  function deleted(id: string, result: DeleteResult) {
    resetSearch();
    facts.update(previous => previous ? { records: previous.records.filter(record => record.id !== id) } : undefined);
    setRefreshKey(value => value + 1);
    setNotice(result.purge_pending ? 'Learning removed from recall. Index cleanup is pending.' : 'Learning and its history removed.');
    listHeading.current?.focus();
  }
  function purged(result: PurgeResult) {
    resetSearch(); facts.refresh(); setRefreshKey(value => value + 1);
    setNotice(result.purge_pending ? 'History removed. Index cleanup is pending.' : 'Revision history removed. Current learning is retained.');
  }

  return <div className="memory-page" ref={page}>
    <PageHeader title="Learning memory" description="Inspect and shape the learning Renulus retains for you." actions={<Button data-memory-add-trigger onClick={() => setAdding(true)} disabled={adding}><Plus size={17} aria-hidden="true" />Add learning</Button>} />
    <div className="memory-layout"><section className="memory-main" aria-label="Retained learning">
      {adding && <AddFact onAdded={changed} onClose={() => setAdding(false)} />}
      <form className="memory-search" onSubmit={find} role="search" aria-label="Search retained learning"><Input label="Search retained learning" type="search" value={query} maxLength={2000} autoComplete="off" onChange={event => { resetSearch(); setQuery(event.target.value); }} placeholder="Find a learning point, preference or goal" /><div className="actions"><Button variant="secondary" type="submit" busy={searchRequest.busy} disabled={!query.trim()}><Search size={16} aria-hidden="true" />Search</Button>{searchRequest.busy ? <Button variant="ghost" onClick={() => { resetSearch(); setNotice('Search stopped.'); }}>Stop search</Button> : (search || query) && <Button variant="ghost" onClick={() => { resetSearch(); setQuery(''); }}><X size={16} aria-hidden="true" />Clear search</Button>}</div></form>
      {notice && <Notice><p>{notice}</p></Notice>}
      {searchRequest.error !== null && <ErrorState error={searchRequest.error} title="Memory search could not finish" />}
      {facts.error !== null && <ErrorState error={facts.error} title="Retained learning could not be loaded" onRetry={facts.refresh} />}
      <div className="memory-section-heading"><h2 ref={listHeading} tabIndex={-1}>{search ? 'Matching learning' : 'Retained learning'}</h2>{records && <span className="muted">{records.length} {records.length === 1 ? 'record' : 'records'}</span>}</div>
      {searchRequest.busy && <p className="muted" role="status">Searching retained learning…</p>}
      {!records && facts.loading && <LoadingState label="Loading retained learning" />}
      {records && records.length > 0 && <ul className="memory-fact-list">{records.map(fact => <li key={fact.id}><FactItem fact={fact} onChanged={changed} onDeleted={deleted} onPurged={purged} onRefresh={facts.refresh} /></li>)}</ul>}
      {records?.length === 0 && (search ? <EmptyState title="No matching learning" action={<Button variant="secondary" onClick={() => { resetSearch(); setQuery(''); }}>Show all learning</Button>}><p>Try another phrase, or return to your retained learning.</p></EmptyState> : <EmptyState title="Make room for what you learn" action={!adding && <Button variant="secondary" onClick={() => setAdding(true)}>Add your first learning point</Button>}><p>Retain a learning point, study preference or goal. Eligible learning captured during study also appears here.</p></EmptyState>)}
      {search?.context && <details className="memory-search-context"><summary>Context returned for recall</summary><p>{search.context}</p></details>}
    </section><IndexStatus pendingFacts={facts.data?.records.some(fact => fact.index_state === 'pending') ?? false} refreshRecords={facts.refresh} refreshKey={refreshKey} /></div>
  </div>;
}

export default function Memory() {
  const { scope, navigate } = useNavigation();
  if (scope.kind !== 'study') return <div className="memory-page"><PageHeader title="Learning memory" description="Inspect and shape the learning Renulus retains for you." /><Notice tone="warning"><p>Open a fresh study context to manage learning memory. Case and unclassified input cannot be retained here.</p><Button variant="secondary" onClick={() => navigate('memory', { freshStudy: true })}>Open memory in study context</Button></Notice></div>;
  return <StudyMemory />;
}
