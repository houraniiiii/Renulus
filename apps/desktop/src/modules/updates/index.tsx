import { useState } from 'react';
import { ArrowUpRight, Check, RefreshCw, Search } from 'lucide-react';
import { api } from '../../platform/api';
import { useResource } from '../../platform/useResource';
import { Badge, Button, EmptyState, ErrorState, LoadingState, Notice, PageHeader, Select, Textarea } from '../../ui';
import './updates.css';

interface Topic { id: string; title: string }
interface Entry { id: string; source_id: string; title: string; url: string; kind: string; publication_date: string | null; discovered_at: string; reviewed_at: string | null; review_state: 'pending' | 'reviewed' | 'dismissed'; summary: string; topic_ids: string[]; read_at: string | null; source_metadata: { new_links?: { url: string; label: string }[] } }
interface Source { source_id: string; title: string; url: string; state: string; freshness: string; last_checked_at: string | null; last_success_at: string | null; error_code: string | null; snapshot_status: string }
type Filter = 'pending' | 'reviewed' | 'dismissed';
const date = (value: string | null) => value ? new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : 'Not checked';

export default function Updates() {
  const { resource, retry } = useResource(async signal => {
    const [entries, sources, topics] = await Promise.all([
      api<{ entries: Entry[] }>('/updates/entries', { signal }),
      api<{ sources: Source[] }>('/updates/sources', { signal }),
      api<Topic[]>('/content/topics', { signal }),
    ]);
    return { ...entries, ...sources, topics };
  });
  const [filter, setFilter] = useState<Filter>('pending');
  const [selected, setSelected] = useState<string | null>(null);
  const [summary, setSummary] = useState('');
  const [topic, setTopic] = useState('');
  const [reviewTopics, setReviewTopics] = useState<string[]>([]);
  const [showSources, setShowSources] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [notice, setNotice] = useState('');

  if (resource.status === 'loading') return <LoadingState label="Loading source updates" />;
  if (resource.status === 'error') return <ErrorState error={resource.error} onRetry={retry} />;
  const data = resource.data;
  const entries = data.entries.filter(entry => entry.review_state === filter);
  const current = data.entries.find(entry => entry.id === selected);

  function open(entry: Entry) {
    setSelected(entry.id); setSummary(entry.review_state === 'pending' ? '' : entry.summary); setReviewTopics(entry.topic_ids); setError(null);
    if (entry.review_state === 'reviewed' && !entry.read_at) api('/updates/entries/' + entry.id + '/read', { method: 'POST' }).catch(setError);
  }
  async function checkLiterature() {
    if (!topic) return;
    setBusy('literature'); setError(null);
    try {
      const result = await api<{ discovered: number }>('/updates/literature/check', { method: 'POST', body: { topic_ids: [topic], days: 30 }, timeoutMs: 60_000 });
      setNotice(result.discovered ? `${result.discovered} new publication records are ready to review.` : 'No new publication records were found for this topic in the last 30 days.');
      setFilter('pending'); retry();
    } catch (caught) { setError(caught); } finally { setBusy(null); }
  }
  async function checkSource(source: Source) {
    setBusy(source.source_id); setError(null);
    try {
      const result = await api<{ state: string; error?: { message: string } }>('/updates/sources/' + encodeURIComponent(source.source_id) + '/check', { method: 'POST', timeoutMs: 60_000 });
      setNotice(result.error?.message ?? (result.state === 'changed' ? 'Publication links changed. The change is in your review queue.' : result.state === 'baseline' ? 'The first publication-link snapshot is saved for future checks.' : 'No publication-link change was found.'));
      retry();
    } catch (caught) { setError(caught); } finally { setBusy(null); }
  }
  async function review(state: 'reviewed' | 'dismissed') {
    if (!current) return;
    setBusy(current.id); setError(null);
    try {
      await api('/updates/entries/' + current.id + '/review', { method: 'POST', body: { summary: summary.trim(), topic_ids: reviewTopics, reviewer: 'learner', state } });
      setNotice(state === 'reviewed' ? 'Your reviewed update is saved and available on Today.' : 'This discovery is dismissed. You can find it in Dismissed.');
      setSelected(null); retry();
    } catch (caught) { setError(caught); } finally { setBusy(null); }
  }

  return <><PageHeader title="Stay current." description="Follow changes in your sources and decide what matters for your learning." actions={<Button variant="ghost" onClick={() => setShowSources(value => !value)}><RefreshCw size={17} />{showSources ? 'Hide source checks' : 'Source checks'}</Button>} />
    <section className="updates-discover"><div><h2>Look for recent research</h2><p>Europe PMC checks publication metadata for your selected topic.</p></div><div className="updates-search"><Select label="Nephrology topic" value={topic} onChange={event => setTopic(event.target.value)}><option value="">Choose a topic</option>{data.topics.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</Select><Button variant="secondary" disabled={!topic || busy !== null} busy={busy === 'literature'} onClick={checkLiterature}><Search size={17} />Check last 30 days</Button></div></section>
    {error !== null && <ErrorState error={error} onRetry={() => setError(null)} />}{notice && <Notice><p>{notice}</p></Notice>}
    {showSources && <section className="section updates-sources"><h2>Official source checks</h2><p className="muted">Check dates and publication-link changes are kept separately from the edition and review of an imported document.</p><div className="source-check-list">{data.sources.map(source => <article key={source.source_id}><div><a href={source.url} target="_blank" rel="noreferrer">{source.title}<ArrowUpRight size={15} /></a><div className="source-check-meta"><Badge tone={source.state === 'failed' || source.freshness === 'stale' ? 'warning' : 'neutral'}>{source.state === 'failed' ? 'Check failed' : source.freshness.replaceAll('-', ' ')}</Badge><span>Last success {date(source.last_success_at)}</span>{source.last_checked_at && <span>Attempt {date(source.last_checked_at)}</span>}</div></div><Button variant="ghost" disabled={busy !== null} busy={busy === source.source_id} onClick={() => checkSource(source)}>Check</Button></article>)}</div></section>}
    <div className="updates-workspace"><section className="updates-queue"><div className="updates-filters" role="group" aria-label="Update review state">{(['pending', 'reviewed', 'dismissed'] as Filter[]).map(state => <button key={state} className={filter === state ? 'active' : ''} aria-pressed={filter === state} onClick={() => { setFilter(state); setSelected(null); }}>{state === 'pending' ? 'To review' : state === 'reviewed' ? 'Reviewed' : 'Dismissed'}<span>{data.entries.filter(row => row.review_state === state).length}</span></button>)}</div>
      {entries.length ? <div className="updates-entry-list">{entries.map(entry => <button key={entry.id} onClick={() => open(entry)} className={selected === entry.id ? 'active' : ''}><div className="update-entry-kicker"><span>{entry.kind.replaceAll('-', ' ')}</span><span>{entry.publication_date ? date(entry.publication_date) : 'Discovered ' + date(entry.discovered_at)}</span></div><h2>{entry.title}</h2><p>{entry.review_state === 'reviewed' ? entry.summary : 'Open the publication and review its relevance.'}</p></button>)}</div> : <EmptyState title={filter === 'pending' ? 'Your review queue is clear' : filter === 'reviewed' ? 'No reviewed updates yet' : 'No dismissed discoveries'}><p>{filter === 'pending' ? 'Choose a topic to look for recent research, or check an official source above.' : 'Publication discoveries move here when you review them.'}</p></EmptyState>}
    </section><aside className="update-detail">{current ? <><Badge tone={current.kind === 'retraction' || current.kind === 'correction' ? 'warning' : 'neutral'}>{current.kind.replaceAll('-', ' ')}</Badge><h2>{current.title}</h2><p className="muted">{current.publication_date ? 'Published ' + date(current.publication_date) : 'Publication date unavailable'} · Discovered {date(current.discovered_at)}</p><a className="update-publication" href={current.url} target="_blank" rel="noreferrer">Open publication<ArrowUpRight size={17} /></a>{current.source_metadata.new_links?.map(link => <a className="update-source-link" href={link.url} target="_blank" rel="noreferrer" key={link.url}>{link.label || 'New publication link'}<ArrowUpRight size={15} /></a>)}
      <Textarea label="What changes for your learning?" hint="Record the educational implication after checking the source, publication status and relevant corrections." rows={7} value={summary} onChange={event => setSummary(event.target.value)} maxLength={8000} />
      <fieldset className="update-topic-list"><legend>Related topics</legend>{data.topics.map(item => <label key={item.id}><input type="checkbox" checked={reviewTopics.includes(item.id)} onChange={event => setReviewTopics(event.target.checked ? [...reviewTopics, item.id] : reviewTopics.filter(id => id !== item.id))} />{item.title}</label>)}</fieldset><div className="actions"><Button disabled={!summary.trim() || busy !== null} busy={busy === current.id} onClick={() => review('reviewed')}><Check size={16} />Save reviewed update</Button><Button variant="ghost" disabled={busy !== null} onClick={() => review('dismissed')}>Dismiss</Button></div>{current.reviewed_at && <p className="muted">Reviewed {date(current.reviewed_at)}</p>}</> : <div className="update-detail-empty"><h2>Read, then review.</h2><p>Select a discovery to inspect the publication and keep its implications for your learning.</p></div>}</aside></div>
  </>;
}
