import { useEffect, useRef, useState } from 'react';
import { api, isCancelled } from '../platform/api';
import type { ContentReference, ConversationIdentity, ProjectSummary } from '../platform/designC';
import { Button, ErrorState, LoadingState, Select } from '../ui';

export interface SearchResult {
  key: string; group: 'chats' | 'projects' | 'files' | 'notes'; title: string; snippet: string;
  lifecycle?: 'active' | 'archived'; status?: string; project_id?: string | null;
  identity?: ConversationIdentity; reference?: ContentReference;
}
interface SearchPage { items: SearchResult[]; next_cursor: string | null }
interface Props {
  query: string; permitted: boolean; policyRevision: number; projects: ProjectSummary[];
  onSelect: (result: SearchResult) => void;
}
const names = { chats: 'Chats', projects: 'Projects', files: 'Files', notes: 'Notes' };

/** Existing paper/teal tokens keep results subordinate to the search input. */
export function LocalSearchResults({ query, permitted, policyRevision, projects, onSelect }: Props) {
  const [project, setProject] = useState('');
  const [archived, setArchived] = useState(false);
  const [page, setPage] = useState<SearchPage>();
  const [loaded, setLoaded] = useState('');
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [retry, setRetry] = useState(0);
  const sequence = useRef(0);
  const paging = useRef<AbortController | undefined>(undefined);
  const key = JSON.stringify([query.trim(), project, archived, policyRevision]);
  const url = '/search?' + new URLSearchParams({ q: query.trim(), archived: String(archived), ...(project ? { project_id: project } : {}) });
  useEffect(() => {
    const current = ++sequence.current, controller = new AbortController();
    paging.current?.abort(); setPage(undefined); setError(undefined); setBusy(false);
    if (!permitted || !query.trim()) return () => controller.abort();
    const timer = setTimeout(() => {
      setBusy(true);
      void api<SearchPage>(url, { signal: controller.signal }).then(value => {
        if (sequence.current === current) { setPage(value); setLoaded(key); }
      }).catch(value => { if (!isCancelled(value) && sequence.current === current) setError(value); })
        .finally(() => { if (sequence.current === current) setBusy(false); });
    }, 200);
    return () => { clearTimeout(timer); controller.abort(); paging.current?.abort(); };
  }, [key, permitted, retry]);
  async function more() {
    if (!page?.next_cursor || busy || loaded !== key || !permitted) return;
    const current = sequence.current, controller = new AbortController(); paging.current = controller; setBusy(true);
    try {
      const value = await api<SearchPage>(url + '&cursor=' + encodeURIComponent(page.next_cursor), { signal: controller.signal });
      if (sequence.current === current) setPage(previous => ({ items: [...(previous?.items ?? []), ...value.items], next_cursor: value.next_cursor }));
    } catch (value) { if (!isCancelled(value) && sequence.current === current) setError(value); }
    finally { if (sequence.current === current) setBusy(false); }
  }
  if (!permitted) return <p role="status">Saved-content search is unavailable during Test. Destinations remain reachable.</p>;
  if (!query.trim()) return null;
  const results = loaded === key ? page : undefined;
  return <section className="local-search" aria-label="Saved content results">
    <div className="search-options"><Select label="Search scope" value={project} onChange={event => setProject(event.target.value)}>
      <option value="">All saved content</option>{projects.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}
    </Select><label><input type="checkbox" checked={archived} onChange={event => setArchived(event.target.checked)} />Include archived</label></div>
    {!!error && <ErrorState error={error} title="Search could not finish" onRetry={() => setRetry(value => value + 1)} />}
    {busy && <LoadingState label="Searching saved content" />}
    {results && !results.items.length && <p role="status">No saved content matches. Files awaiting indexing are searchable by title.</p>}
    {Object.entries(names).map(([group, label]) => {
      const items = results?.items.filter(item => item.group === group) ?? [];
      return items.length ? <section key={group} aria-label={label}><h3>{label}</h3><div className="search-records">{items.map(item =>
        <button key={item.key} type="button" onClick={() => onSelect(item)}><strong>{item.title}</strong>
          {item.lifecycle === 'archived' && <span className="search-record-state">Archived</span>}
          {item.status && item.status !== 'ready' && <span className="search-record-state">{item.status}</span>}
          {item.snippet && <span>{item.snippet}</span>}</button>)}</div></section> : null;
    })}
    {results?.next_cursor && <Button variant="secondary" disabled={busy} onClick={() => { void more(); }}>More results</Button>}
  </section>;
}
