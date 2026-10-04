import { useEffect, useId, useRef, useState, type FormEvent } from 'react';
import { History, Pencil, Trash2 } from 'lucide-react';
import { api, ApiError } from '../../platform/api';
import { Badge, Button, ErrorState, LoadingState, Notice, Textarea } from '../../ui';
import { useMemoryRequest } from './requests';
import { displayDate, factPath, kindLabels, readableState, type DeleteResult, type Fact, type FactHistory, type PurgeResult } from './types';

interface Props {
  fact: Fact;
  onChanged: (fact: Fact) => void;
  onDeleted: (id: string, result: DeleteResult) => void;
  onPurged: (result: PurgeResult) => void;
  onRefresh: () => void;
}

// Intent: inspect and correct one retained lesson in place; the lesson outweighs provenance and controls.
// Flow type weights and ink hierarchy, token spacing and paper surfaces supply depth without a new card vocabulary.
export function FactItem({ fact, onChanged, onDeleted, onPurged, onRefresh }: Props) {
  const historyId = useId();
  const [editing, setEditing] = useState(false);
  const article = useRef<HTMLElement>(null);
  const editWasOpen = useRef(false);
  const [draft, setDraft] = useState('');
  const [editRevision, setEditRevision] = useState(fact.revision);
  const [deleteRevision, setDeleteRevision] = useState<number | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState<FactHistory[]>();
  const [confirmPurge, setConfirmPurge] = useState(false);
  const mutation = useMemoryRequest();
  const historyRequest = useMemoryRequest();
  const changedDuringEdit = editing && editRevision !== fact.revision;
  const changedDuringDelete = deleteRevision !== null && deleteRevision !== fact.revision;
  useEffect(() => {
    if (editWasOpen.current && !editing) article.current?.querySelector<HTMLButtonElement>('[data-memory-edit-trigger]')?.focus();
    editWasOpen.current = editing;
  }, [editing]);

  function loadHistory() {
    void historyRequest.run(signal => api<{ history: FactHistory[] }>(factPath(fact.id) + '/history', { signal }), result => setHistory(result.history));
  }
  function closeHistory() { historyRequest.cancel(); setShowHistory(false); setHistory(undefined); setConfirmPurge(false); }
  function edit() { mutation.clearError(); closeHistory(); setDeleteRevision(null); setDraft(fact.text); setEditRevision(fact.revision); setEditing(true); }
  function save(event: FormEvent) {
    event.preventDefault();
    if (!draft.trim() || mutation.busy || changedDuringEdit) return;
    void mutation.run(signal => api<Fact>(factPath(fact.id), { method: 'PATCH', signal, body: { text: draft.trim(), expected_revision: editRevision } }), result => {
      setEditing(false); setDraft(''); closeHistory(); onChanged(result);
    });
  }
  function remove() {
    if (deleteRevision === null || changedDuringDelete || mutation.busy) return;
    void mutation.run(signal => api<DeleteResult>(factPath(fact.id) + '?expected_revision=' + deleteRevision, { method: 'DELETE', signal }), result => {
      closeHistory(); onDeleted(fact.id, result);
    });
  }
  function purge() {
    if (mutation.busy) return;
    historyRequest.cancel();
    void mutation.run(signal => api<PurgeResult>(factPath(fact.id) + '/history', { method: 'DELETE', signal }), result => {
      setHistory(undefined); setConfirmPurge(false); onPurged(result); loadHistory();
    });
  }

  return <article className="memory-fact" ref={article} aria-label={kindLabels[fact.kind] + ', revision ' + fact.revision}>
    <div className="memory-fact-meta"><span className="memory-kind">{kindLabels[fact.kind]}</span>{fact.topic_id && <span>{readableState(fact.topic_id)}</span>}<Badge tone={fact.index_state === 'ready' ? 'neutral' : fact.index_state === 'failed' ? 'error' : 'warning'}>{fact.index_state === 'ready' ? 'Available for recall' : fact.index_state === 'failed' ? 'Index needs retry' : 'Index pending'}</Badge></div>
    {editing ? <form className="memory-editor" onSubmit={save}>
      <Textarea label="Edit retained learning" value={draft} onChange={event => setDraft(event.target.value)} required maxLength={2000} disabled={mutation.busy} autoFocus autoComplete="off" />
      {changedDuringEdit && <Notice tone="warning"><p>Revision {fact.revision} is now available. Your draft is unchanged. Review the latest text before choosing to replace it.</p><p className="memory-current-text">{fact.text}</p><Button variant="secondary" disabled={mutation.busy} onClick={() => { setEditRevision(fact.revision); mutation.clearError(); }}>Use latest revision</Button></Notice>}
      <div className="actions"><Button type="submit" busy={mutation.busy} disabled={!draft.trim() || changedDuringEdit || draft.trim() === fact.text}>Save changes</Button><Button variant="ghost" disabled={mutation.busy} onClick={() => { setEditing(false); setDraft(''); mutation.clearError(); }}>Cancel edit</Button></div>
    </form> : <p className="memory-fact-text">{fact.text}</p>}
    <div className="memory-fact-footer"><time dateTime={fact.updated_at}>Updated {displayDate(fact.updated_at)}</time><div className="memory-row-actions">
      {!editing && deleteRevision === null && <Button data-memory-edit-trigger variant="ghost" disabled={mutation.busy} onClick={edit}><Pencil size={15} aria-hidden="true" />Edit</Button>}
      {!editing && deleteRevision === null && <Button variant="ghost" disabled={mutation.busy} aria-expanded={showHistory} aria-controls={historyId} onClick={() => { if (showHistory) closeHistory(); else { setShowHistory(true); loadHistory(); } }}><History size={15} aria-hidden="true" />{showHistory ? 'Hide history' : 'History'}</Button>}
      {!editing && deleteRevision === null && <Button variant="ghost" disabled={mutation.busy} onClick={() => { mutation.clearError(); closeHistory(); setDeleteRevision(fact.revision); }}><Trash2 size={15} aria-hidden="true" />Delete</Button>}
    </div></div>
    {mutation.error !== null && <div className="memory-operation-error"><ErrorState error={mutation.error} title={editing ? 'Changes could not be saved' : confirmPurge ? 'History could not be removed' : 'Learning could not be removed'} />{mutation.error instanceof ApiError && mutation.error.status === 409 && <div className="memory-inline-actions"><p className="muted">The saved revision changed. Refresh records to review it; your draft stays here.</p><Button variant="secondary" onClick={onRefresh}>Refresh records</Button></div>}</div>}
    {deleteRevision !== null && <div className="memory-confirmation" role="group" aria-label="Confirm learning deletion"><h3>Delete this learning?</h3><p>The retained record and its history will be removed. It will no longer be used for recall.</p>{changedDuringDelete && <p className="field-error">This learning changed after you opened deletion. Cancel, review it, then choose Delete again.</p>}<div className="actions"><Button variant="danger" busy={mutation.busy} disabled={changedDuringDelete} onClick={remove}>Delete learning and history</Button><Button variant="ghost" disabled={mutation.busy} onClick={() => { setDeleteRevision(null); mutation.clearError(); }}>Keep learning</Button></div></div>}
    {showHistory && <section className="memory-history" id={historyId} aria-label="Revision history">
      <div className="memory-section-heading"><h3>Revision history</h3>{history && history.length > 0 && !confirmPurge && <Button variant="ghost" disabled={mutation.busy || historyRequest.busy} onClick={() => { mutation.clearError(); setConfirmPurge(true); }}>Remove history</Button>}</div>
      {historyRequest.error !== null ? <ErrorState error={historyRequest.error} title="History could not be loaded" onRetry={loadHistory} /> : history === undefined ? <LoadingState label="Loading revision history" /> : history.length ? <ol className="memory-history-list">{history.map((entry, index) => <li key={entry.revision + '-' + entry.event + '-' + index}><div className="memory-fact-meta"><strong>Revision {entry.revision}</strong><span>{readableState(entry.event)}</span><time dateTime={entry.created_at}>{displayDate(entry.created_at)}</time></div><p>{entry.text}</p></li>)}</ol> : <p className="muted">No revision history is retained.</p>}
      {confirmPurge && <div className="memory-confirmation" role="group" aria-label="Confirm history removal"><h3>Remove revision history?</h3><p>The current learning remains. Previous retained text will be removed.</p><div className="actions"><Button variant="danger" busy={mutation.busy} onClick={purge}>Remove revision history</Button><Button variant="ghost" disabled={mutation.busy} onClick={() => { setConfirmPurge(false); mutation.clearError(); }}>Keep history</Button></div></div>}
    </section>}
    <details className="memory-provenance"><summary>Provenance</summary><dl><dt>Source</dt><dd>{readableState(fact.source_kind)}</dd>{fact.source_id && <><dt>Source reference</dt><dd>{fact.source_id}</dd></>}<dt>First retained</dt><dd><time dateTime={fact.created_at}>{displayDate(fact.created_at)}</time></dd><dt>Current revision</dt><dd>{fact.revision}</dd></dl></details>
  </article>;
}
