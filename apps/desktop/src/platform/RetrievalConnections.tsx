import { useEffect, useRef, useState, type FormEvent } from 'react';
import { api, ApiError, isCancelled } from './api';
import { useResource } from './useResource';
import { Badge, Button, ErrorState, Input, LoadingState, Notice, Select } from '../ui';
import './RetrievalConnections.css';

type Tool = 'ncbi' | 'brave' | 'tavily' | 'exa';
interface Connection {
  provider: string; enabled: boolean; configured: boolean; selected: boolean;
  daily_request_limit: number; daily_credit_limit: number;
  requests_used: number; credits_used: number; auth_status: string;
  last_attempt_at?: string; last_success_at?: string; error_code?: string;
}
interface Connections { selected_tool: Tool | null; connections: Connection[] }
interface Topic { id: string; label: string }
interface Record { id: string; title: string; url: string; authors?: string; publication_date?: string; pmcid?: string; retracted?: boolean; snippet?: string }
interface Discovery { topic_id: string; topic_label: string; provider: string; queried_at: string; records: Record[] }
const names: { [provider: string]: string } = { 'europe-pmc': 'Europe PMC', pubmed: 'PubMed', ncbi: 'NCBI key', brave: 'Brave Search', tavily: 'Tavily', exa: 'Exa' };
const statuses: { [status: string]: string } = {
  not_checked: 'Not checked', request_succeeded: 'Last request succeeded',
  retrieval_authentication_required: 'Check key permissions', retrieval_provider_limit: 'Provider limit reached',
  retrieval_unavailable: 'Source unavailable', retrieval_failed: 'Retrieval failed',
};

function ToolSettings({ row, busy, save, select, disconnect }: {
  row: Connection; busy: boolean;
  save: (provider: string, body: unknown) => Promise<void>;
  select: (provider: string | null) => Promise<void>;
  disconnect: (provider: string) => Promise<void>;
}) {
  const [key, setKey] = useState('');
  const [enabled, setEnabled] = useState(row.enabled);
  const [requests, setRequests] = useState(row.daily_request_limit);
  const [credits, setCredits] = useState(row.daily_credit_limit);
  async function submit(event: FormEvent) {
    event.preventDefault();
    const body = { ...(key.trim() ? { api_key: key.trim() } : {}), enabled,
      daily_request_limit: requests, daily_credit_limit: credits };
    setKey('');
    await save(row.provider, body);
  }
  return <section className="retrieval-tool" aria-label={names[row.provider] + ' settings'}>
    <div className="retrieval-heading"><h3>{names[row.provider]}</h3><div className="actions">
      <Badge tone={row.enabled ? 'default' : 'neutral'}>{row.enabled ? 'Enabled' : 'Disabled'}</Badge>
      {row.selected && <Badge>Selected</Badge>}
    </div></div>
    <p className="muted">{row.provider === 'ncbi' ? 'Optional key for PubMed requests. PubMed also works without a key.' : 'Optional search tool. Your provider’s plan and billing terms apply.'}</p>
    <form onSubmit={submit} className="section">
      <Input label={names[row.provider] + ' key'} type="password" value={key} onChange={event => setKey(event.target.value)}
        maxLength={8192} autoComplete="off" spellCheck={false}
        hint={row.configured ? 'Key is saved in your protected app profile. Leave blank to keep it.' : 'Enter your own key. Saving it makes no provider request.'} />
      <div className="retrieval-limits"><Input label={names[row.provider] + ' daily requests'} type="number" min={0} max={10000}
        value={requests} onChange={event => setRequests(Number(event.target.value))} />
        <Input label={names[row.provider] + ' daily credits'} type="number" min={0} max={10000}
          value={credits} onChange={event => setCredits(Number(event.target.value))}
          hint={row.provider === 'tavily' ? 'One basic search credit per attempted request.' : row.provider === 'ncbi' ? 'This route uses zero billed search credits.' : 'Search request budget units; not a currency or billing guarantee.'} /></div>
      <label className="retrieval-enable"><input type="checkbox" checked={enabled} onChange={event => setEnabled(event.target.checked)} />Enable {names[row.provider]}</label>
      <div className="actions"><Button type="submit" disabled={busy || (enabled && !row.configured && !key.trim())}>Save {names[row.provider]}</Button>
        {row.enabled && row.configured && !row.selected && <Button variant="secondary" disabled={busy} onClick={() => void select(row.provider)}>Select {names[row.provider]}</Button>}
        {row.selected && <Button variant="ghost" disabled={busy} onClick={() => void select(null)}>Use key-free sources</Button>}
        {row.configured && <Button variant="ghost" disabled={busy} onClick={() => void disconnect(row.provider)}>Remove {names[row.provider]} key</Button>}</div>
    </form>
    <p className="retrieval-usage">Today UTC: {row.requests_used}/{row.daily_request_limit} requests attempted · {row.credits_used}/{row.daily_credit_limit} credits</p>
    <p role={row.error_code ? 'alert' : undefined}>{statuses[row.auth_status] ?? (row.error_code ? 'The last retrieval did not complete.' : 'Not checked')}{row.last_success_at ? ' · ' + new Date(row.last_success_at).toLocaleString() : ''}</p>
  </section>;
}

export function RetrievalConnections({ openSource }: { openSource?: (url: string) => Promise<void> } = {}) {
  const { resource, retry } = useResource(async signal => {
    const [connections, topics] = await Promise.all([
      api<Connections>('/retrieval/connections', { signal }), api<Topic[]>('/content/topics', { signal }),
    ]);
    return { connections, topics };
  });
  const [topic, setTopic] = useState('');
  const [provider, setProvider] = useState('europe-pmc');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [discovery, setDiscovery] = useState<Discovery>();
  const [notice, setNotice] = useState('');
  const operation = useRef<AbortController | null>(null);
  const importKeys = useRef(new Map<string, string>());
  useEffect(() => () => operation.current?.abort(), []);

  function changeDiscovery(topicId: string, source: string) {
    operation.current?.abort();
    setBusy(false); setError(undefined); setNotice(''); setDiscovery(undefined);
    setTopic(topicId); setProvider(source);
  }

  async function run(action: (signal: AbortSignal) => Promise<void>, refreshUsage = false) {
    operation.current?.abort();
    const controller = new AbortController();
    operation.current = controller;
    setBusy(true); setError(undefined); setNotice('');
    try { await action(controller.signal); }
    catch (problem) { if (!controller.signal.aborted && !isCancelled(problem)) setError(problem); }
    finally { if (!controller.signal.aborted) { setBusy(false); if (refreshUsage) retry(); } }
  }
  async function configure(path: string, method: string, body?: unknown) {
    await run(async signal => {
      await api(path, { method, body, signal });
      if (!signal.aborted) { setNotice('Retrieval settings saved. No provider request was made.'); retry(); }
    });
  }
  async function search(event: FormEvent) {
    event.preventDefault();
    setDiscovery(undefined);
    const selectedTopic = topic;
    await run(async signal => {
      const result = await api<Discovery>('/retrieval/discover', { method: 'POST', signal,
        timeoutMs: 60_000,
        body: { topic_id: topic, scope: { kind: 'study' }, provider, limit: 5 } });
      if (!signal.aborted && result.topic_id === selectedTopic) setDiscovery(result);
    }, true);
  }
  async function importArticle(topicId: string, pmcid: string) {
    const binding = topicId + ':' + pmcid;
    const idempotencyKey = importKeys.current.get(binding) ?? crypto.randomUUID();
    importKeys.current.set(binding, idempotencyKey);
    await run(async signal => {
      const result = await api<{ import: { status: string } }>('/retrieval/articles/import', {
        method: 'POST', signal, timeoutMs: 60_000, body: { topic_id: topicId, pmcid, scope: { kind: 'personal-library' }, idempotency_key: idempotencyKey },
      });
      if (!signal.aborted) setNotice('Eligible article text added to your library queue: ' + result.import.status + '. Currency and content review remain unverified.');
    }, true);
  }
  async function copySource(url: string) {
    await run(async signal => {
      try { await navigator.clipboard.writeText(url); if (!signal.aborted) setNotice('Source link copied.'); }
      catch { throw new ApiError('The source link could not be copied. Select the article link and copy its address.', 0, 'source_copy_unavailable'); }
    });
  }
  return <section className="retrieval-connections" aria-labelledby="retrieval-title">
    <header className="section"><h2 id="retrieval-title">Sources and retrieval</h2><p>Discover literature for a study topic. Searches send the selected topic label; case details stay local.</p></header>
    {resource.status === 'loading' && <LoadingState label="Loading retrieval connections" />}
    {resource.status === 'error' && <ErrorState error={resource.error} onRetry={retry} />}
    {error !== undefined && <ErrorState error={error} title="Retrieval did not complete" />}
    {notice && <Notice><p>{notice}</p></Notice>}
    {resource.status === 'ready' && <>
      <form className="retrieval-discovery" onSubmit={search}>
        <div className="retrieval-heading"><h3>{provider === 'selected-tool' ? 'Topic literature discovery' : 'Key-free literature discovery'}</h3><Badge>{provider === 'selected-tool' ? 'Explicit tool selection' : 'Available without a key'}</Badge></div>
        <div className="retrieval-limits"><Select label="Study topic" value={topic} onChange={event => changeDiscovery(event.target.value, provider)}>
          <option value="">Choose a topic</option>{resource.data.topics.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</Select>
          <Select label="Discovery source" value={provider} onChange={event => changeDiscovery(topic, event.target.value)}>
            <option value="europe-pmc">Europe PMC · key-free</option><option value="pubmed">PubMed · key-free</option>
            <option value="selected-tool" disabled={!resource.data.connections.selected_tool}>{resource.data.connections.selected_tool ? 'Selected tool · ' + names[resource.data.connections.selected_tool] : 'Optional tool · enable and select below'}</option>
          </Select></div>
        <Button type="submit" disabled={!topic || busy || (provider === 'selected-tool' && !resource.data.connections.selected_tool)} busy={busy}>Discover literature</Button>
        {resource.data.connections.connections.filter(row => row.provider === (provider === 'selected-tool' ? resource.data.connections.selected_tool : provider)).map(row => <p className="retrieval-usage" key={row.provider}>Today UTC: {row.requests_used}/{row.daily_request_limit} requests attempted · {statuses[row.auth_status] ?? 'Last retrieval needs attention'}</p>)}
        <p className="muted">Search results are discovery records. They do not verify the latest final guidance or supply reviewed passage evidence.</p>
      </form>
      {discovery && <section className="section" aria-live="polite"><h3>Discovery results · {discovery.topic_label}</h3><p className="muted">{names[discovery.provider]} · checked {new Date(discovery.queried_at).toLocaleString()}</p>
        {!discovery.records.length && <p>No records found for this topic.</p>}
        {discovery.records.map(record => <article className="retrieval-result" key={record.id}><h4><a href={record.url} target="_blank" rel="noreferrer" onClick={event => {
          if (openSource) { event.preventDefault(); void run(async () => openSource(record.url)); }
          else if (window.renulus) { event.preventDefault(); setError(new ApiError('Native source opening is not available here. Copy the source link to open it in your browser.', 0, 'source_open_unavailable')); }
        }}>{record.title}</a></h4>
          <p className="muted">{record.authors}{record.publication_date && ' · ' + record.publication_date}</p>
          {record.snippet && <p>{record.snippet}</p>}
          {record.retracted && <Badge tone="warning">Retraction reported · import blocked</Badge>}
          {record.pmcid && !record.retracted && <Button variant="secondary" disabled={busy} onClick={() => void importArticle(discovery.topic_id, record.pmcid!)}>Add eligible full text</Button>}
          <Button variant="ghost" disabled={busy} onClick={() => void copySource(record.url)}>Copy source link</Button>
          <p className="muted">Licence checked on import. Figures, tables and media are outside this text route.</p></article>)}
      </section>}
      <div className="retrieval-heading"><h3>Optional retrieval tools</h3><span className="muted">Enable and select a tool explicitly after adding your key.</span></div>
      <div className="retrieval-tools">{resource.data.connections.connections.filter(row => ['ncbi', 'brave', 'tavily', 'exa'].includes(row.provider)).map(row =>
        <ToolSettings key={row.provider} row={row} busy={busy}
          save={(id, body) => configure('/retrieval/connections/' + id, 'PUT', body)}
          select={id => configure('/retrieval/connections/select', 'POST', { provider: id })}
          disconnect={id => configure('/retrieval/connections/' + id, 'DELETE')} />)}</div>
      <Notice><p>Daily caps reset at midnight UTC. Attempted requests count even when they fail. Search-credit caps do not guarantee your provider’s bill. Renulus does not switch tools after a failure or request generated answers.</p></Notice>
    </>}
  </section>;
}
