import { useEffect, useId, useRef, useState, type FormEvent, type MouseEvent } from 'react';
import { Search } from 'lucide-react';
import { api, ApiError, isCancelled } from '../../platform/api';
import { useResource } from '../../platform/useResource';
import { Badge, Button, EmptyState, ErrorState, LoadingState, Notice, Panel, Select } from '../../ui';
import type { ImportResult, Job, LibraryDocument } from './types';
import './Discovery.css';

type Provider = 'europe-pmc' | 'pubmed' | 'ncbi' | 'brave' | 'tavily' | 'exa';
interface Topic { id: string; label: string }
interface Connection {
  provider: Provider; enabled: boolean; configured: boolean; selected: boolean;
  requests_used: number; daily_request_limit: number; credits_used: number; daily_credit_limit: number; auth_status: string;
}
interface Connections { selected_tool: Provider | null; connections: Connection[] }
interface Article {
  id: string; title: string; url: string; authors?: string | null; publication_date?: string | null;
  doi?: string | null; pmid?: string | null; pmcid?: string | null; open_access?: boolean | null;
  retracted?: boolean | null; snippet?: string; article_types?: string[];
  comment_corrections?: { source?: string; id?: string; type?: string }[];
}
interface Results { topic_id: string; topic_label: string; provider: Provider; queried_at: string; records: Article[] }
interface ArticleImport {
  topic_id: string; article: { pmcid: string; licence: string; licence_url: string; attribution: string };
  import: ImportResult; replayed: boolean;
}
type ImportState =
  | { phase: 'checking' }
  | { phase: 'rejected'; error: unknown }
  | { phase: 'accepted'; result: ArticleImport; job: Job; document?: LibraryDocument; statusError?: unknown; check: number };
interface Props {
  blocked?: boolean;
  requestedTopicId?: string;
  handoffRevision?: number;
  libraryDocuments?: LibraryDocument[];
  onLibraryChange?: () => void;
  onInspect?: (document: LibraryDocument) => void;
  openSource?: (url: string) => Promise<void>;
}
const names: Record<Provider, string> = { 'europe-pmc': 'Europe PMC', pubmed: 'PubMed', ncbi: 'NCBI key', brave: 'Brave Search', tavily: 'Tavily', exa: 'Exa' };
const publicSources: Provider[] = ['europe-pmc', 'pubmed'];
const pmcidPattern = /^PMC[1-9][0-9]{0,10}$/;
const health: Record<string, string> = { not_checked: 'Not checked', request_succeeded: 'Last request succeeded',
  retrieval_authentication_required: 'Check key permissions', retrieval_provider_limit: 'Provider limit reached',
  retrieval_unavailable: 'Source unavailable', retrieval_failed: 'Last request failed' };
const bindingFor = (topicId: string, pmcid: string) => topicId + ':' + pmcid;

function sourceUrl(value: string): string | undefined {
  try {
    const url = new URL(value);
    if (url.protocol === 'https:' && !url.username && !url.password && !url.port &&
        url.hostname.includes('.') && !url.hostname.includes(':') && !/^\d+(?:\.\d+){3}$/.test(url.hostname) &&
        !/\.(local|internal|localhost)$/.test(url.hostname)) return url.href;
  } catch { /* Unsupported source links remain inert text. */ }
}
function searchedAt(value: string) {
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date.toLocaleString() : 'Date unavailable';
}
function indexed(entry: Extract<ImportState, { phase: 'accepted' }>, document?: LibraryDocument) {
  const revision = document?.revisions.find(row => row.id === entry.result.import.revision_id);
  return entry.job.state === 'ready' && document?.active_revision === revision?.id &&
    document?.status === 'ready' && !document.reserved && revision?.status === 'ready' && revision.passage_count > 0;
}

/** A forbidden context unmounts the active panel and aborts all of its requests. */
export function Discovery({ blocked = false, ...props }: Props) {
  if (blocked) return <Notice tone="warning"><p>Literature discovery is available in a fresh study context. Case and assessment details are never sent to search tools.</p></Notice>;
  return <DiscoveryPanel {...props} />;
}

function DiscoveryPanel({ libraryDocuments, requestedTopicId, handoffRevision = 0, ...actions }: Omit<Props, 'blocked'>) {
  const titleId = useId();
  const topics = useResource(signal => api<Topic[]>('/content/topics', { signal }));
  const connections = useResource(signal => api<Connections>('/retrieval/connections', { signal }));
  const [topic, setTopic] = useState('');
  const [source, setSource] = useState<Provider>('europe-pmc');
  const [results, setResults] = useState<Results>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [linkError, setLinkError] = useState<unknown>();
  const [notice, setNotice] = useState('');
  const [imports, setImports] = useState<Record<string, ImportState>>({});
  const operation = useRef<AbortController | null>(null);
  const keys = useRef(new Map<string, string>());
  const appliedHandoff = useRef<string | undefined>(undefined);
  const callbacks = useRef(actions);
  callbacks.current = actions;
  const mounted = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; operation.current?.abort(); }; }, []);

  const status = connections.resource.status === 'ready' ? connections.resource.data : undefined;
  const selected = status?.connections.find(row => row.provider === status.selected_tool && row.enabled && row.configured && row.selected);
  const sourceStatus = status?.connections.find(row => row.provider === source);
  const validTopic = topics.resource.status === 'ready' && topics.resource.data.some(row => row.id === topic);
  const allowedSource = !!status && (publicSources.includes(source) || selected?.provider === source);
  const staleTool = !publicSources.includes(source) && !!status && selected?.provider !== source;

  useEffect(() => {
    if (!requestedTopicId || topics.resource.status !== 'ready') return;
    const identity = handoffRevision + ':' + requestedTopicId;
    if (appliedHandoff.current === identity) return;
    appliedHandoff.current = identity;
    if (!topics.resource.data.some(row => row.id === requestedTopicId)) {
      change('', source);
      setError(new ApiError('The requested study topic is not installed. Choose a topic from the list.', 0, 'discovery_topic_missing'));
      return;
    }
    change(requestedTopicId, source);
  }, [requestedTopicId, handoffRevision, topics.resource]);

  const pending = Object.entries(imports).filter(([, entry]) => entry.phase === 'accepted' && !entry.statusError &&
    (entry.job.state === 'queued' || entry.job.state === 'processing' || (entry.job.state === 'ready' && !entry.document)));
  const pendingKey = pending.map(([key, entry]) => entry.phase === 'accepted' ? key + ':' + entry.job.id + ':' + entry.check : '').join('|');
  useEffect(() => {
    if (!pendingKey) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function check() {
      await Promise.all(pending.map(async ([key, entry]) => {
        if (entry.phase !== 'accepted') return;
        try {
          const job = await api<Job>('/library/jobs/' + encodeURIComponent(entry.job.id), { signal: controller.signal });
          if (job.id !== entry.job.id || job.revision_id !== entry.result.import.revision_id ||
              !['queued', 'processing', 'ready', 'failed', 'cancelled'].includes(job.state)) {
            throw new ApiError('The library returned a different import job. Inspect your library before retrying.', 0, 'discovery_job_mismatch');
          }
          const document = job.state === 'ready' ? await api<LibraryDocument>('/library/documents/' + encodeURIComponent(entry.result.import.document_id), { signal: controller.signal }) : undefined;
          if (document && document.id !== entry.result.import.document_id) throw new ApiError('The library returned a different document.', 0, 'discovery_document_mismatch');
          if (controller.signal.aborted) return;
          setImports(current => {
            const value = current[key];
            return value?.phase === 'accepted' && value.job.id === job.id ? { ...current, [key]: { ...value, job, document } } : current;
          });
          if (['ready', 'failed', 'cancelled'].includes(job.state)) callbacks.current.onLibraryChange?.();
        } catch (problem) {
          if (controller.signal.aborted || isCancelled(problem)) return;
          setImports(current => {
            const value = current[key];
            return value?.phase === 'accepted' && value.job.id === entry.job.id ? { ...current, [key]: { ...value, statusError: problem } } : current;
          });
        }
      }));
      if (!controller.signal.aborted) timer = setTimeout(check, 3000);
    }
    void check();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [pendingKey]);

  function change(topicId: string, provider: Provider) {
    operation.current?.abort();
    if (busy) connections.retry();
    setTopic(topicId); setSource(provider); setResults(undefined); setError(undefined); setLinkError(undefined); setNotice(''); setBusy(false);
    setImports(current => Object.fromEntries(Object.entries(current).map(([key, value]) => [key, value.phase === 'checking'
      ? { phase: 'rejected', error: new ApiError('The import request was interrupted. Check your library, then retry this article if needed.', 0, 'discovery_interrupted') } : value])));
  }
  async function search(event: FormEvent) {
    event.preventDefault();
    if (!validTopic || !allowedSource || busy) return;
    operation.current?.abort();
    const controller = new AbortController();
    operation.current = controller;
    const requestedTopic = topic, requestedSource = source;
    setBusy(true); setResults(undefined); setError(undefined); setLinkError(undefined); setNotice('');
    try {
      const found = await api<Results>('/retrieval/discover', { method: 'POST', signal: controller.signal, timeoutMs: 60_000,
        body: { topic_id: requestedTopic, scope: { kind: 'study' }, provider: requestedSource, limit: 5 } });
      if (controller.signal.aborted) return;
      if (found.topic_id !== requestedTopic || found.provider !== requestedSource) throw new ApiError('The result does not match the selected topic and source. Repeat the search deliberately.', 0, 'discovery_result_mismatch');
      setResults(found);
    } catch (problem) { if (!controller.signal.aborted && !isCancelled(problem)) setError(problem); }
    finally { if (!controller.signal.aborted) { setBusy(false); connections.retry(); } }
  }
  async function addArticle(topicId: string, pmcid: string) {
    if (busy || !pmcidPattern.test(pmcid)) return;
    const key = bindingFor(topicId, pmcid);
    const replayKey = keys.current.get(key) ?? crypto.randomUUID();
    keys.current.set(key, replayKey);
    operation.current?.abort();
    const controller = new AbortController();
    operation.current = controller;
    setBusy(true); setError(undefined); setNotice('');
    setImports(current => ({ ...current, [key]: { phase: 'checking' } }));
    try {
      const result = await api<ArticleImport>('/retrieval/articles/import', { method: 'POST', signal: controller.signal, timeoutMs: 60_000,
        body: { topic_id: topicId, pmcid, scope: { kind: 'personal-library' }, idempotency_key: replayKey } });
      if (controller.signal.aborted) return;
      if (result.topic_id !== topicId || result.article.pmcid !== pmcid || !result.import.document_id || !result.import.revision_id ||
          !result.import.job.id || result.import.job.revision_id !== result.import.revision_id) {
        throw new ApiError('The import acknowledgement does not match this article. Check your library before retrying.', 0, 'discovery_import_mismatch');
      }
      setImports(current => ({ ...current, [key]: { phase: 'accepted', result, job: result.import.job, check: 0 } }));
      callbacks.current.onLibraryChange?.();
    } catch (problem) {
      if (!controller.signal.aborted && !isCancelled(problem)) setImports(current => ({ ...current, [key]: { phase: 'rejected', error: problem } }));
    } finally { if (!controller.signal.aborted) { setBusy(false); connections.retry(); } }
  }
  function recheck(key: string) {
    setImports(current => {
      const entry = current[key];
      return entry?.phase === 'accepted' ? { ...current, [key]: { ...entry, document: undefined, statusError: undefined, check: entry.check + 1 } } : current;
    });
  }
  async function open(event: MouseEvent<HTMLAnchorElement>, url: string) {
    // Shared preload/types are parent-owned. This additive view also builds at
    // the assigned 1da890b2 baseline, before the public-source bridge lands.
    const native = window.renulus as typeof window.renulus & { openSource?: (url: string) => Promise<void> };
    const openSource = callbacks.current.openSource ?? (native?.openSource ? (value: string) => native.openSource!(value) : undefined);
    if (openSource) {
      event.preventDefault();
      try { await openSource(url); } catch { if (mounted.current) setLinkError(new ApiError('The source could not be opened. Copy its link to open it in your browser.', 0, 'source_open_unavailable')); }
    }
  }
  async function copy(url: string) {
    try { await navigator.clipboard.writeText(url); if (mounted.current) { setNotice('Source link copied.'); setLinkError(undefined); } }
    catch { if (mounted.current) setLinkError(new ApiError('Copying is unavailable. Select and copy the source address shown below the article.', 0, 'source_copy_unavailable')); }
  }

  return <Panel className="library-discovery"><header className="library-discovery-heading"><div>
    <h2 id={titleId}>Discover literature</h2><p>Find sources for a study topic and add eligible article text to your library.</p>
  </div><Badge tone="neutral">Topic discovery</Badge></header>
    {topics.resource.status === 'loading' && <LoadingState label="Loading installed discovery topics" />}
    {topics.resource.status === 'error' && <ErrorState error={topics.resource.error} title="Study topics could not be loaded" onRetry={topics.retry} />}
    {connections.resource.status === 'error' && <ErrorState error={connections.resource.error} title="Retrieval status could not be loaded" onRetry={connections.retry} />}
    {topics.resource.status === 'ready' && (topics.resource.data.length ? <form onSubmit={search} className="library-discovery-form" aria-labelledby={titleId}>
      <div className="library-discovery-selectors"><Select label="Literature topic" value={topic} onChange={event => change(event.target.value, source)}>
        <option value="">Choose an installed topic</option>{topics.resource.data.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}
      </Select><Select label="Literature source" value={source} onChange={event => change(topic, event.target.value as Provider)}>
        <option value="europe-pmc">Europe PMC · key-free</option><option value="pubmed">PubMed · key-free</option>
        {staleTool && <option value={source} disabled>{names[source]} · selection changed</option>}
        <option value={selected?.provider ?? 'optional'} disabled={!selected}>{selected ? names[selected.provider] + ' · selected tool' : 'Optional tool · configure in Connections'}</option>
      </Select></div>
      <div className="library-discovery-actions"><Button type="submit" busy={busy} disabled={!validTopic || !allowedSource}><Search size={18} aria-hidden="true" />Search literature</Button>
        {sourceStatus && <p className="muted">Today UTC: {sourceStatus.requests_used}/{sourceStatus.daily_request_limit} requests attempted{!publicSources.includes(source) && ' · ' + sourceStatus.credits_used + '/' + sourceStatus.daily_credit_limit + ' credit units'}. {health[sourceStatus.auth_status] ?? 'Last retrieval needs attention'}.</p>}
        {connections.resource.status === 'loading' && <p className="muted" role="status">Refreshing retrieval status…</p>}
      </div>
      {staleTool && <Notice tone="warning"><p>The selected tool changed. Choose a source again before searching; no replacement tool will run automatically.</p></Notice>}
      <p className="field-hint">Search uses the installed topic label. Case details and personal questions stay local. Optional tools keep the limits set in Connections.</p>
    </form> : <EmptyState title="Install a topic pack first"><p>Discovery uses the canonical topics in your installed learning content.</p></EmptyState>)}
    {error !== undefined && <ErrorState error={error} title="Literature search did not finish" />}
    {linkError !== undefined && <ErrorState error={linkError} title="Source link needs attention" />}
    {notice && <Notice><p>{notice}</p></Notice>}
    {results && <section className="library-discovery-results" aria-label="Literature discovery results" aria-live="polite">
      <header><h3>{results.topic_label}</h3><p className="muted">{names[results.provider]} · Searched <time dateTime={results.queried_at}>{searchedAt(results.queried_at)}</time></p></header>
      {results.records.length === 0 && <EmptyState title="No discovery records found"><p>Try another installed topic or deliberately choose another source. No other tool has been called.</p></EmptyState>}
      <ul className="library-discovery-list">{results.records.map(record => {
        const key = bindingFor(results.topic_id, record.pmcid ?? record.id);
        const entry = imports[key];
        const url = sourceUrl(record.url);
        const document = entry?.phase === 'accepted' ? (libraryDocuments ? libraryDocuments.find(row => row.id === entry.result.import.document_id) : entry.document) : undefined;
        const isIndexed = entry?.phase === 'accepted' && !!entry.document && indexed(entry, document);
        const jobLabels: Record<string, string> = { queued: 'Queued for import', processing: 'Processing', ready: isIndexed ? 'Indexed' : 'Index not confirmed', failed: 'Import failed', cancelled: 'Import cancelled' };
        const jobLabel = entry?.phase === 'accepted' ? (jobLabels[entry.job.state] ?? 'Import status unknown') : 'Discovery only';
        const eligibleCandidate = record.pmcid && pmcidPattern.test(record.pmcid) && record.retracted !== true;
        return <li key={record.id}><article className="library-discovery-article" aria-label={record.title}>
          <div className="library-discovery-article-top"><Badge tone={isIndexed ? 'default' : entry?.phase === 'accepted' && entry.job.state === 'failed' ? 'error' : entry ? 'warning' : 'neutral'}>{entry?.phase === 'checking' ? 'Checking licence' : entry?.phase === 'rejected' ? 'Text not added' : jobLabel}</Badge>
            {record.retracted === true && <Badge tone="error">Retraction reported · import blocked</Badge>}</div>
          <h4>{url ? <a href={url} target="_blank" rel="noopener noreferrer" onClick={event => void open(event, url)}>{record.title}</a> : record.title}</h4>
          <p className="library-discovery-authors">{record.authors || 'Authors not supplied'}</p>
          <dl className="library-discovery-metadata"><div><dt>Published</dt><dd>{record.publication_date || 'Date not supplied'}</dd></div>
            {record.pmid && <div><dt>PMID</dt><dd>{record.pmid}</dd></div>}{record.pmcid && <div><dt>PMCID</dt><dd>{record.pmcid}</dd></div>}
            {record.doi && <div><dt>DOI</dt><dd>{record.doi}</dd></div>}</dl>
          {!!record.article_types?.length && <p className="muted">{record.article_types.join(' · ')}</p>}
          {!!record.comment_corrections?.length && <p className="field-hint">Source relationships: {record.comment_corrections.map(item => item.type || 'Notice').join(' · ')}. Check the source record for details.</p>}
          {record.snippet && <p className="library-discovery-excerpt"><span className="muted">Search excerpt: </span>{record.snippet}</p>}
          <div className="library-discovery-record-actions">
            {eligibleCandidate && (!entry || entry.phase === 'rejected') && <Button variant="secondary" disabled={busy} onClick={() => void addArticle(results.topic_id, record.pmcid!)}>{entry?.phase === 'rejected' ? 'Retry eligible text import' : 'Add eligible text'}</Button>}
            {entry?.phase === 'accepted' && actions.onInspect && document && <Button variant="secondary" onClick={() => callbacks.current.onInspect?.(document)}>Inspect library source</Button>}
            {entry?.phase === 'accepted' && (entry.statusError || entry.job.state === 'ready') && <Button variant="ghost" onClick={() => recheck(key)}>Check import status</Button>}
            {url && <Button variant="ghost" onClick={() => void copy(url)}>Copy source link</Button>}
          </div>
          {url && <p className="library-discovery-address">{url}</p>}
          {entry?.phase === 'accepted' && <p className="field-hint">{entry.result.article.licence} terms checked on import. {isIndexed ? 'Passages are available in library search.' : 'Passage availability is not confirmed yet.'} Currency and content review remain unverified.</p>}
          {entry?.phase === 'rejected' && <ErrorState error={entry.error} title="Article text could not be added" />}
          {entry?.phase === 'accepted' && entry.statusError !== undefined && <ErrorState error={entry.statusError} title="Import status could not be checked" />}
          {entry?.phase === 'accepted' && entry.job.state === 'failed' && <p className="field-error" role="alert">{entry.job.error_message || 'The library could not finish this import. Inspect the source in your library.'}</p>}
          {!entry && <p className="field-hint">{record.open_access === true ? 'Open access reported; licence not checked. ' : ''}{eligibleCandidate ? 'Import checks CC BY or CC0 terms before saving text. Figures, tables and media are excluded.' : record.retracted ? 'Retracted records cannot be imported here.' : 'No eligible full-text identifier is available through this route.'}</p>}
        </article></li>;
      })}</ul>
    </section>}
    <p className="library-discovery-boundary">Discovery records provide source metadata. Only completed imports enter passage search; they do not establish reviewed evidence or the latest final guidance.</p>
  </Panel>;
}
