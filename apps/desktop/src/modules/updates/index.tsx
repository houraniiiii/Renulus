import { useState } from 'react';
import { RefreshCw, Search } from 'lucide-react';
import { api } from '../../platform/api';
import { useResource } from '../../platform/useResource';
import { Button, ErrorState, LoadingState, Notice, PageHeader, Select } from '../../ui';
import SourceChecks, { checkMessage } from './SourceChecks';
import UpdatesQueue from './UpdatesQueue';
import ReviewDetail from './ReviewDetail';
import { reviewDraft, reviewPayload, literatureMessage } from './types';
import type { Entry, EntryPage, Filter, LiteratureResult, Publication, ReviewDraft, Source, Topic } from './types';
import './updates.css';

export default function Updates() {
  const [filter, setFilter] = useState<Filter>('pending');
  const [offset, setOffset] = useState(0);
  const [current, setCurrent] = useState<Entry | null>(null);
  const [draft, setDraft] = useState<ReviewDraft | null>(null);
  const [topic, setTopic] = useState('');
  const [reviewTopics, setReviewTopics] = useState<string[]>([]);
  const [showSources, setShowSources] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [notice, setNotice] = useState('');
  const { resource, retry } = useResource(async signal => {
    const [page, sources, publications, topics] = await Promise.all([
      api<EntryPage>('/updates/entries?state=' + filter + '&limit=50&offset=' + offset, { signal }),
      api<{ sources: Source[] }>('/updates/sources', { signal }),
      api<{ publications: Publication[] }>('/updates/publications', { signal }),
      api<Topic[]>('/content/topics', { signal }),
    ]);
    return { page, ...sources, ...publications, topics };
  });

  function open(entry: Entry) {
    setCurrent(entry); setDraft(reviewDraft(entry)); setReviewTopics(entry.topic_ids); setError(null);
    if (entry.review_state === 'reviewed' && !entry.read_at) api('/updates/entries/' + entry.id + '/read', { method: 'POST' }).catch(setError);
  }
  function changeFilter(state: Filter) {
    setFilter(state); setOffset(0); setCurrent(null); setDraft(null); retry();
  }
  async function checkLiterature() {
    if (!topic) return;
    setBusy('literature'); setError(null);
    try {
      const result = await api<LiteratureResult>('/updates/literature/check', { method: 'POST', body: { topic_ids: [topic], days: 30 }, timeoutMs: 60_000 });
      setNotice(literatureMessage(result)); setFilter('pending'); setOffset(0); retry();
    } catch (caught) { setError(caught); } finally { setBusy(null); }
  }
  async function review(state: 'reviewed' | 'dismissed') {
    if (!current || !draft || resource.status !== 'ready') return;
    setBusy('review'); setError(null);
    try {
      const result = await api<Entry>('/updates/entries/' + current.id + '/review', { method: 'POST', body: reviewPayload(current, draft, reviewTopics, state) });
      const sync = result.review?.library_sync_state;
      setNotice(state === 'dismissed' ? 'Discovery dismissed. Its history remains in Dismissed.' :
        'Your evidence and reviewed update are saved.' + (sync && sync !== 'applied' && sync !== 'not-requested' ? ' Library metadata is awaiting application (' + sync + ').' : ''));
      if (resource.data.page.entries.length === 1 && offset > 0) setOffset(Math.max(0, offset - 50));
      setCurrent(null); setDraft(null); retry();
    } catch (caught) { setError(caught); } finally { setBusy(null); }
  }
  async function refresh() {
    if (!current) return;
    setBusy('refresh'); setError(null);
    try {
      const result = await api<{ state: string; error?: { message: string }; latest_entry?: Entry; entry: Entry }>('/updates/entries/' + current.id + '/refresh', { method: 'POST', timeoutMs: 60_000 });
      if (result.state === 'failed') { setNotice(result.error?.message ?? 'The check failed. Previous metadata and your draft are retained.'); return; }
      if (result.latest_entry && result.latest_entry.id !== current.id) {
        open(result.latest_entry); setFilter(result.latest_entry.review_state); setOffset(0);
        setNotice('Changed article metadata is ready for a new review. The earlier review remains in its history.');
      } else {
        setCurrent(result.entry); setNotice(checkMessage(result, current.kind === 'publication-change' || !!result.latest_entry));
      }
      retry();
    } catch (caught) { setError(caught); } finally { setBusy(null); }
  }
  async function sync() {
    if (!current) return;
    setBusy('sync'); setError(null);
    try {
      const result = await api<{ changes: { state: string }[] }>('/updates/entries/' + current.id + '/sync', { method: 'POST' });
      setNotice(!result.changes.length ? 'This review has no library metadata change to apply.' : result.changes.every(item => item.state === 'applied') ?
        'The library acknowledged the recorded metadata changes.' : 'Library metadata remains unapplied: ' + [...new Set(result.changes.filter(item => item.state !== 'applied').map(item => item.state))].join(', ') + '.');
      setCurrent(await api<Entry>('/updates/entries/' + current.id)); retry();
    } catch (caught) { setError(caught); } finally { setBusy(null); }
  }

  if (resource.status === 'loading') return <LoadingState label="Loading source updates" />;
  if (resource.status === 'error') return <ErrorState error={resource.error} onRetry={retry} />;
  const data = resource.data;
  return <><PageHeader title="Stay current." description="Follow changes in your sources and decide what matters for your learning." actions={<Button variant="ghost" onClick={() => setShowSources(value => !value)}><RefreshCw size={17} />{showSources ? 'Hide source checks' : 'Source checks'}</Button>} />
    <section className="updates-discover"><div><h2>Look for recent research</h2><p>Europe PMC checks up to 25 publication records for your selected topic.</p></div><div className="updates-search"><Select label="Nephrology topic" value={topic} onChange={event => setTopic(event.target.value)}><option value="">Choose a topic</option>{data.topics.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</Select><Button variant="secondary" disabled={!topic || busy !== null} busy={busy === 'literature'} onClick={checkLiterature}><Search size={17} />Check last 30 days</Button></div></section>
    {error !== null && <ErrorState error={error} onRetry={() => setError(null)} />}{notice && <Notice><p role="status">{notice}</p></Notice>}
    {showSources && <SourceChecks sources={data.sources} publications={data.publications} done={message => { setNotice(message); retry(); }} />}
    <div className="updates-workspace"><UpdatesQueue page={data.page} filter={filter} selectedId={current?.id} busy={busy !== null} open={open} filterChanged={changeFilter} pageChanged={value => { setOffset(value); retry(); }} />
      <ReviewDetail entry={current} draft={draft} topics={data.topics} reviewTopics={reviewTopics} busy={busy} change={setDraft} topicsChanged={setReviewTopics} review={review} refresh={refresh} sync={sync} />
    </div>
  </>;
}
