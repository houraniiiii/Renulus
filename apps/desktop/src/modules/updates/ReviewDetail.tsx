import { ArrowUpRight, Check, RefreshCw } from 'lucide-react';
import { Badge, Button } from '../../ui';
import AffectedList from './AffectedList';
import ReviewFields from './ReviewFields';
import { displayDate as date, reviewProblem } from './types';
import type { Entry, ReviewDraft, Topic } from './types';

interface Props {
  entry: Entry | null; draft: ReviewDraft | null; topics: Topic[]; reviewTopics: string[]; busy: string | null;
  change: (draft: ReviewDraft) => void; topicsChanged: (ids: string[]) => void;
  review: (state: 'reviewed' | 'dismissed') => void; refresh: () => void; sync: () => void;
}
export default function ReviewDetail({ entry, draft, topics, reviewTopics, busy, change, topicsChanged, review, refresh, sync }: Props) {
  if (!entry || !draft) return <aside className="update-detail"><div className="update-detail-empty"><h2>Read, then review.</h2><p>Select a discovery to inspect the publication and keep its implications for your learning.</p></div></aside>;
  const problem = reviewProblem(draft);
  const jobs = entry.library_changes ?? [];
  const outstanding = jobs.filter(job => job.state !== 'applied');
  const syncState = outstanding.length ? [...new Set(outstanding.map(job => job.state))].join(', ') : jobs.length ? 'applied' : entry.review?.library_sync_state;
  return <aside className="update-detail" aria-label="Selected publication">
    <Badge tone={entry.kind === 'retraction' || entry.kind === 'correction' ? 'warning' : 'neutral'}>{entry.kind.replaceAll('-', ' ')}</Badge><h2>{entry.title}</h2>
    <p className="muted">{entry.publication_date ? 'Published ' + date(entry.publication_date) : 'Publication date unavailable'} · Discovered {date(entry.discovered_at)}</p>
    <div className="actions"><a className="update-publication" href={entry.url} target="_blank" rel="noreferrer">Open publication<ArrowUpRight size={17} /></a><Button variant="ghost" disabled={busy !== null} busy={busy === 'refresh'} onClick={refresh}><RefreshCw size={15} />Refresh metadata</Button></div>
    {entry.source_metadata.new_links?.map(link => <a className="update-source-link" href={link.url} target="_blank" rel="noreferrer" key={link.url}>{link.label || 'New publication link'}<ArrowUpRight size={15} /></a>)}
    {entry.source_metadata.reported_publication_status === 'preprint' && <p className="update-status-note">The source reports a preprint. Final publication status requires inspected evidence.</p>}
    {entry.review_state === 'reviewed' && !entry.review?.evidence.length && <p className="update-status-note">This earlier review has no recorded inspected evidence. Add evidence to verify it now.</p>}
    {syncState && syncState !== 'not-requested' && <div className="update-status-note"><p>{syncState === 'applied' ? 'The library acknowledged this metadata change.' : 'Library metadata has not been applied (' + syncState + ').'}</p>{syncState !== 'applied' && <Button variant="ghost" disabled={busy !== null} busy={busy === 'sync'} onClick={sync}>Retry library update</Button>}</div>}
    <AffectedList key={entry.id + (entry.review?.id ?? '')} entryId={entry.id} />
    <ReviewFields sourceId={entry.source_id} draft={draft} topics={topics} change={change} />
    <details className="update-metadata"><summary>Related learning topics{reviewTopics.length ? ' · ' + reviewTopics.length + ' selected' : ''}</summary><fieldset className="update-topic-list"><legend>Related learning topics</legend>{topics.map(item => <label key={item.id}><input type="checkbox" checked={reviewTopics.includes(item.id)} onChange={event => topicsChanged(event.target.checked ? [...reviewTopics, item.id] : reviewTopics.filter(id => id !== item.id))} />{item.title}</label>)}</fieldset></details>
    <div className="actions"><Button disabled={!!problem || busy !== null} busy={busy === 'review'} onClick={() => review('reviewed')}><Check size={16} />Save reviewed update</Button><Button variant="ghost" disabled={busy !== null} onClick={() => review('dismissed')}>Dismiss</Button></div>
    {problem && <p className="field-hint">{problem}</p>}{entry.reviewed_at && <p className="muted">Reviewed {date(entry.reviewed_at)}</p>}
  </aside>;
}
