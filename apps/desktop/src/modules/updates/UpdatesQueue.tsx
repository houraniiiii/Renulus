import { Button, EmptyState } from '../../ui';
import { displayDate as date } from './types';
import type { Entry, EntryPage, Filter } from './types';

interface Props {
  page: EntryPage; filter: Filter; selectedId?: string; busy: boolean;
  open: (entry: Entry) => void; filterChanged: (state: Filter) => void; pageChanged: (offset: number) => void;
}
export default function UpdatesQueue({ page, filter, selectedId, busy, open, filterChanged, pageChanged }: Props) {
  return <section className="updates-queue" aria-label="Publication review queue">
    <div className="updates-filters" role="group" aria-label="Update review state">{(['pending', 'reviewed', 'dismissed'] as Filter[]).map(state => <button key={state} disabled={busy} className={filter === state ? 'active' : ''} aria-pressed={filter === state} aria-label={(state === 'pending' ? 'To review' : state === 'reviewed' ? 'Reviewed' : 'Dismissed') + ' ' + page.counts[state]} onClick={() => filterChanged(state)}>{state === 'pending' ? 'To review' : state === 'reviewed' ? 'Reviewed' : 'Dismissed'}<span>{page.counts[state]}</span></button>)}</div>
    {page.entries.length ? <div className="updates-entry-list">{page.entries.map(entry => <button key={entry.id} disabled={busy} onClick={() => open(entry)} className={selectedId === entry.id ? 'active' : ''} aria-pressed={selectedId === entry.id}><div className="update-entry-kicker"><span>{entry.kind.replaceAll('-', ' ')}</span><span>{entry.publication_date ? date(entry.publication_date) : 'Discovered ' + date(entry.discovered_at)}</span></div><h2>{entry.title}</h2><p>{entry.review_state === 'reviewed' ? entry.summary : 'Open the publication and review its relevance.'}</p></button>)}</div> : <EmptyState title={page.total ? 'No records on this page' : filter === 'pending' ? 'Your review queue is clear' : filter === 'reviewed' ? 'No reviewed updates yet' : 'No dismissed discoveries'}><p>{page.total ? 'Return to the previous page to see the remaining records.' : filter === 'pending' ? 'Choose a topic to look for recent research, or check an official source above.' : 'Publication discoveries move here when you review them.'}</p></EmptyState>}
    <nav className="updates-pagination" aria-label="Update pages"><span>{page.entries.length ? page.offset + 1 : 0}–{page.offset + page.entries.length} of {page.total}</span><div className="actions"><Button variant="ghost" disabled={busy || page.offset === 0} onClick={() => pageChanged(Math.max(0, page.offset - page.limit))}>Previous</Button><Button variant="ghost" disabled={busy || page.next_offset === null} onClick={() => pageChanged(page.next_offset ?? page.offset)}>Next</Button></div></nav>
  </section>;
}
