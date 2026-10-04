import { useState } from 'react';
import { ArrowUpRight } from 'lucide-react';
import { api } from '../../platform/api';
import { Badge, Button, ErrorState, Input, Select } from '../../ui';
import { displayDate as date } from './types';
import type { Candidate, Publication, Source } from './types';

export interface CheckResult { state: string; cached?: boolean; error?: { message: string } }
export function checkMessage(result: CheckResult, publication = false) {
  if (result.error) return result.error.message;
  if (result.state === 'failed') return 'The check failed. The last successful check has not advanced.';
  if (result.cached) return 'Showing the previous check result.';
  if (result.state === 'tracking-stopped') return 'Tracking was stopped while the check was running.';
  if (result.state === 'changed') return publication ? 'Published content changed at this URL. The change is ready to review.' : 'Publication links changed. The change is ready to review.';
  return result.state === 'baseline' ? 'The first complete snapshot is saved for future checks.' : publication ? 'The publication bytes match the previous check.' : 'No publication-link change was found.';
}

export default function SourceChecks({ sources, publications, done }: { sources: Source[]; publications: Publication[]; done: (message: string) => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [sourceId, setSourceId] = useState('');
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [url, setUrl] = useState('');
  const [permission, setPermission] = useState('');
  async function check(id: string, publication: boolean) {
    setBusy(id); setError(null);
    try {
      const result = await api<CheckResult>('/updates/' + (publication ? 'publications/' : 'sources/') + encodeURIComponent(id) + '/check?force=true', { method: 'POST', timeoutMs: 60_000 });
      done(checkMessage(result, publication));
    } catch (caught) { setError(caught); } finally { setBusy(null); }
  }
  async function choose(id: string) {
    setSourceId(id); setCandidates([]); setUrl(''); setBusy('candidates'); setError(null);
    try { if (id) setCandidates((await api<{ candidates: Candidate[] }>('/updates/sources/' + id + '/publications')).candidates); }
    catch (caught) { setError(caught); } finally { setBusy(null); }
  }
  async function track() {
    setBusy('tracking'); setError(null);
    try {
      const item = await api<Publication>('/updates/publications', { method: 'POST', body: { source_id: sourceId, url, permission_reference: permission.trim() } });
      const result = await api<CheckResult>('/updates/publications/' + item.id + '/check?force=true', { method: 'POST', timeoutMs: 60_000 });
      setPermission(''); setUrl(''); done(checkMessage(result, true));
    } catch (caught) { setError(caught); } finally { setBusy(null); }
  }
  async function stop(item: Publication) {
    setBusy(item.id); setError(null);
    try { await api('/updates/publications/' + item.id, { method: 'DELETE' }); done('Tracking stopped. Previous discoveries and reviews are retained.'); }
    catch (caught) { setError(caught); } finally { setBusy(null); }
  }
  return <section className="section updates-sources"><h2>Source checks</h2><p className="muted">Publication links and tracked file changes are discovery evidence. Publication status, access and reviewed currency remain separate.</p>
    {error !== null && <ErrorState error={error} onRetry={() => setError(null)} />}
    <div className="source-check-list">{sources.map(source => <article key={source.source_id}><div><a href={source.url} target="_blank" rel="noreferrer">{source.title}<ArrowUpRight size={15} /></a><div className="source-check-meta"><Badge tone={source.state === 'failed' || source.freshness === 'stale' ? 'warning' : 'neutral'}>{source.state === 'failed' ? 'Check failed' : source.freshness.replaceAll('-', ' ')}</Badge><span>Last success {date(source.last_success_at)}</span>{source.last_checked_at && <span>Attempt {date(source.last_checked_at)}</span>}</div></div><Button variant="ghost" disabled={busy !== null} busy={busy === source.source_id} onClick={() => check(source.source_id, false)}>Check now</Button></article>)}</div>
    <div className="updates-tracked"><h3>Tracked publications</h3><p className="muted">These checks detect changed published content at the same URL.</p>
      {publications.length ? <div className="source-check-list">{publications.map(item => <article key={item.id}><div><a href={item.url} target="_blank" rel="noreferrer">{item.title}<ArrowUpRight size={15} /></a><div className="source-check-meta"><Badge tone={item.state === 'failed' || item.freshness === 'stale' ? 'warning' : 'neutral'}>{item.state === 'failed' ? 'Check failed' : item.state.replaceAll('-', ' ')}</Badge><span>{item.freshness.replaceAll('-', ' ')}</span><span>Last success {date(item.last_success_at)}</span></div></div><div className="actions"><Button variant="ghost" disabled={busy !== null} busy={busy === item.id} onClick={() => check(item.id, true)}>Check now</Button><Button variant="ghost" disabled={busy !== null} onClick={() => stop(item)}>Stop tracking</Button></div></article>)}</div> : <p className="muted">Choose an eligible public publication to start tracking its content.</p>}
      <details className="update-track-form"><summary>Track a publication</summary><div className="update-track-fields"><Select label="Registered source" value={sourceId} disabled={busy !== null} onChange={event => choose(event.target.value)}><option value="">Choose a source</option>{sources.map(source => <option key={source.source_id} value={source.source_id}>{source.title}</option>)}</Select><Select label="Public publication" value={url} disabled={!candidates.length || busy !== null} onChange={event => setUrl(event.target.value)}><option value="">Choose a publication</option>{candidates.map(candidate => <option key={candidate.url} value={candidate.url}>{candidate.title} — {candidate.url}</option>)}</Select>{sourceId && !candidates.length && busy !== 'candidates' && <p className="muted">No registered publication links are available. Check the official source first.</p>}<Input label="Permission for a public digest check" hint="Record the licence or permission for checking this public file. Other processing permissions remain separate." value={permission} onChange={event => setPermission(event.target.value)} maxLength={1000} /><Button variant="secondary" disabled={!url || !permission.trim() || busy !== null} busy={busy === 'tracking'} onClick={track}>Track and check</Button></div></details>
    </div>
  </section>;
}
