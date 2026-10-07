import { useEffect, useRef, useState } from 'react';
import { RefreshCw, Search } from 'lucide-react';
import { api, ApiError } from '../../platform/api';
import { useResource } from '../../platform/useResource';
import { useNavigation } from '../../shell/navigation';
import { Button, ErrorState, LoadingState, Notice, PageHeader, Select } from '../../ui';
import SourceChecks, { checkMessage } from './SourceChecks';
import UpdatesQueue from './UpdatesQueue';
import ReviewDetail from './ReviewDetail';
import AutomaticChecks from './AutomaticChecks';
import { reviewDraft, reviewPayload, literatureMessage } from './types';
import type { Entry, EntryPage, Filter, LiteratureResult, Publication, ReviewDraft, Source, Topic } from './types';
import './updates.css';

type RetryOperation = { kind: 'literature' | 'refresh' | 'sync' } |
  { kind: 'review'; state: 'reviewed' | 'dismissed' } | { kind: 'read'; id: string };

export default function Updates() {
  const navigation = useNavigation();
  const entryId = navigation.route === 'updates' && typeof navigation.handoff?.entry_id === 'string'
    ? navigation.handoff.entry_id : undefined;
  const handoffRequest = useRef<AbortController | null>(null);
  const selectionVersion = useRef(0);
  const [handoffAttempt, setHandoffAttempt] = useState(0);
  const [handoffLoading, setHandoffLoading] = useState(false);
  const [handoffError, setHandoffError] = useState<unknown>(null);
  const [filter, setFilter] = useState<Filter>('pending');
  const [offset, setOffset] = useState(0);
  const [current, setCurrent] = useState<Entry | null>(null);
  const [draft, setDraft] = useState<ReviewDraft | null>(null);
  const [topic, setTopic] = useState('');
  const [reviewTopics, setReviewTopics] = useState<string[]>([]);
  const [showSources, setShowSources] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<{ cause: unknown; operation: RetryOperation } | null>(null);
  const [notice, setNotice] = useState('');
  const [refreshNotice, setRefreshNotice] = useState('');
  const { resource, retry } = useResource(async signal => {
    const [page, sources, publications, topics] = await Promise.all([
      api<EntryPage>('/updates/entries?state=' + filter + '&limit=50&offset=' + offset, { signal }),
      api<{ sources: Source[] }>('/updates/sources', { signal }),
      api<{ publications: Publication[] }>('/updates/publications', { signal }),
      api<Topic[]>('/content/topics', { signal }),
    ]);
    return { page, ...sources, ...publications, topics };
  });

  // Only an explicit navigation (or its retry) consumes the handoff. Queue
  // refreshes must not reopen the entry or replace an in-progress review.
  useEffect(() => {
    cancelHandoff();
    if (!entryId) return;
    const controller = new AbortController();
    handoffRequest.current = controller;
    const version = selectionVersion.current;
    setHandoffLoading(true);
    api<Entry>('/updates/entries/' + encodeURIComponent(entryId), { signal: controller.signal }).then(entry => {
      if (controller.signal.aborted || version !== selectionVersion.current) return;
      if (!entry || entry.id !== entryId) throw new ApiError('The linked update was not returned. Try again.', 0, 'invalid_response', true);
      setFilter(entry.review_state); setOffset(0); showEntry(entry); retry();
    }).catch(cause => {
      if (controller.signal.aborted || version !== selectionVersion.current) return;
      setHandoffError(cause instanceof ApiError && cause.status === 404
        ? new ApiError('This linked update could not be found. Try again or choose an update from the queue.', 404, cause.code)
        : cause);
    }).finally(() => {
      if (!controller.signal.aborted && version === selectionVersion.current) setHandoffLoading(false);
    });
    return () => { controller.abort(); selectionVersion.current += 1; };
  }, [entryId, navigation.revision, handoffAttempt, retry]);

  function cancelHandoff() {
    selectionVersion.current += 1;
    handoffRequest.current?.abort(); handoffRequest.current = null;
    setHandoffLoading(false); setHandoffError(null);
  }
  function open(entry: Entry) {
    cancelHandoff(); showEntry(entry);
  }
  function showEntry(entry: Entry) {
    setCurrent(entry); setDraft(reviewDraft(entry)); setReviewTopics(entry.topic_ids); setError(null); setRefreshNotice('');
    if (entry.review_state === 'reviewed' && !entry.read_at) void markRead(entry.id);
  }
  async function markRead(id: string) {
    const version = selectionVersion.current;
    setError(null);
    try { await api('/updates/entries/' + id + '/read', { method: 'POST' }); }
    catch (cause) { if (version === selectionVersion.current) setError({ cause, operation: { kind: 'read', id } }); }
  }
  function changeFilter(state: Filter) {
    cancelHandoff();
    setFilter(state); setOffset(0); setCurrent(null); setDraft(null); retry();
  }
  async function checkLiterature() {
    if (!topic) return;
    cancelHandoff();
    setBusy('literature'); setError(null);
    try {
      const result = await api<LiteratureResult>('/updates/literature/check', { method: 'POST', body: { topic_ids: [topic], days: 30 }, timeoutMs: 60_000 });
      setNotice(literatureMessage(result)); setFilter('pending'); setOffset(0); retry();
    } catch (cause) { setError({ cause, operation: { kind: 'literature' } }); } finally { setBusy(null); }
  }
  async function review(state: 'reviewed' | 'dismissed') {
    if (!current || !draft || resource.status !== 'ready') return;
    cancelHandoff();
    setBusy('review'); setError(null);
    try {
      const result = await api<Entry>('/updates/entries/' + current.id + '/review', { method: 'POST', body: reviewPayload(current, draft, reviewTopics, state) });
      const sync = result.review?.library_sync_state;
      setNotice(state === 'dismissed' ? 'Discovery dismissed. Its history remains in Dismissed.' :
        'Your evidence and reviewed update are saved.' + (sync && sync !== 'applied' && sync !== 'not-requested' ? ' Library metadata is awaiting application (' + sync + ').' : ''));
      if (resource.data.page.entries.length === 1 && offset > 0) setOffset(Math.max(0, offset - 50));
      setCurrent(null); setDraft(null); retry();
    } catch (cause) { setError({ cause, operation: { kind: 'review', state } }); } finally { setBusy(null); }
  }
  async function refresh() {
    if (!current) return;
    cancelHandoff();
    setBusy('refresh'); setError(null); setRefreshNotice('');
    try {
      const result = await api<{ state: string; error?: { message: string }; latest_entry?: Entry; entry: Entry }>('/updates/entries/' + current.id + '/refresh', { method: 'POST', timeoutMs: 60_000 });
      if (result.state === 'failed') { setRefreshNotice(result.error?.message ?? 'The check failed. Previous metadata and your draft are retained.'); return; }
      if (result.latest_entry && result.latest_entry.id !== current.id) {
        open(result.latest_entry); setFilter(result.latest_entry.review_state); setOffset(0);
        setRefreshNotice('Changed article metadata is ready for a new review. The earlier review remains in its history.');
      } else {
        setCurrent(result.entry); setRefreshNotice(checkMessage(result, current.kind === 'publication-change' || !!result.latest_entry));
      }
      retry();
    } catch (cause) { setError({ cause, operation: { kind: 'refresh' } }); } finally { setBusy(null); }
  }
  async function sync() {
    if (!current) return;
    cancelHandoff();
    setBusy('sync'); setError(null);
    try {
      const result = await api<{ changes: { state: string }[] }>('/updates/entries/' + current.id + '/sync', { method: 'POST' });
      setNotice(!result.changes.length ? 'This review has no library metadata change to apply.' : result.changes.every(item => item.state === 'applied') ?
        'The library acknowledged the recorded metadata changes.' : 'Library metadata remains unapplied: ' + [...new Set(result.changes.filter(item => item.state !== 'applied').map(item => item.state))].join(', ') + '.');
      setCurrent(await api<Entry>('/updates/entries/' + current.id)); retry();
    } catch (cause) { setError({ cause, operation: { kind: 'sync' } }); } finally { setBusy(null); }
  }
  function retryOperation(operation: RetryOperation) {
    if (operation.kind === 'literature') void checkLiterature();
    else if (operation.kind === 'refresh') void refresh();
    else if (operation.kind === 'sync') void sync();
    else if (operation.kind === 'review') void review(operation.state);
    else if (operation.kind === 'read') void markRead(operation.id);
  }

  const handoffFeedback = handoffLoading ? <Notice><p>Opening linked update…</p></Notice> : handoffError !== null
    ? <ErrorState title="Linked update could not be opened" error={handoffError} onRetry={() => setHandoffAttempt(value => value + 1)} /> : null;
  if (resource.status === 'loading') return <>{handoffFeedback}<LoadingState label="Loading source updates" /><AutomaticChecks key="automatic-checks" onComplete={retry} /></>;
  if (resource.status === 'error') return <>{handoffFeedback}<ErrorState error={resource.error} onRetry={retry} /><AutomaticChecks key="automatic-checks" onComplete={retry} /></>;
  const data = resource.data;
  return <><PageHeader title="Stay current." description="Follow changes in your sources and decide what matters for your learning." actions={<Button variant="ghost" onClick={() => setShowSources(value => !value)}><RefreshCw size={17} />{showSources ? 'Hide source checks' : 'Source checks'}</Button>} />
    <section className="updates-discover"><div><h2>Look for recent research</h2><p>Europe PMC checks up to 25 publication records for your selected topic.</p></div><div className="updates-search"><Select label="Nephrology topic" value={topic} onChange={event => setTopic(event.target.value)}><option value="">Choose a topic</option>{data.topics.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</Select><Button variant="secondary" disabled={!topic || busy !== null} busy={busy === 'literature'} onClick={checkLiterature}><Search size={17} />Check last 30 days</Button></div></section>
    {handoffFeedback}{error !== null && <ErrorState error={error.cause} onRetry={busy !== null ? undefined : () => retryOperation(error.operation)} />}{notice && <Notice><p role="status">{notice}</p></Notice>}
    <AutomaticChecks key="automatic-checks" onComplete={retry} />
    {showSources && <SourceChecks sources={data.sources} publications={data.publications} done={message => { setNotice(message); retry(); }} />}
    <div className="updates-workspace"><UpdatesQueue page={data.page} filter={filter} selectedId={current?.id} busy={busy !== null} open={open} filterChanged={changeFilter} pageChanged={value => { cancelHandoff(); setOffset(value); retry(); }} />
      <ReviewDetail entry={current} draft={draft} topics={data.topics} reviewTopics={reviewTopics} busy={busy} refreshNotice={refreshNotice}
        change={value => { cancelHandoff(); setDraft(value); setError(null); }} topicsChanged={value => { cancelHandoff(); setReviewTopics(value); setError(null); }}
        review={review} refresh={refresh} sync={sync} />
    </div>
  </>;
}
