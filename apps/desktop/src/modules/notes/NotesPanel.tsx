import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Check, MessageCircle } from 'lucide-react';
import { api, ApiError, isCancelled } from '../../platform/api';
import { studyHelpHeaders, type PassageDraft, type StudyHelpContext } from '../../platform/designC';
import { Button, ErrorState, Input, LoadingState, Notice, Select, Textarea } from '../../ui';
import { useNoteDrafts } from './NotesDrafts';
import type { Note, NoteCommand, NoteDraft, NoteSummary } from './types';
import './notes.css';

interface Props {
  projectId?: string; studyHelpContext?: StudyHelpContext; signal?: AbortSignal;
  onUse: (passage: PassageDraft) => Promise<void>; onOpen: (note: NoteSummary) => void;
}
const path = (id: string) => '/library/notes/' + encodeURIComponent(id);
const changed = () => window.dispatchEvent(new Event('renulus:records-changed'));
export default function NotesPanel({ projectId, studyHelpContext, signal, onUse, onOpen }: Props) {
  const store = useNoteDrafts();
  const scope = projectId ?? 'personal';
  const [selected, select] = useState(() => store.selected.get(scope) ?? 'new');
  const draftKey = selected === 'new' ? 'new:' + scope : selected;
  const [draft, setDraft] = useState<NoteDraft>(() => store.notes.get(draftKey) ?? { title: '', text: '' });
  const [items, setItems] = useState<NoteSummary[]>();
  const [loading, setLoading] = useState(selected !== 'new');
  const [error, setError] = useState<unknown>();
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [refresh, reload] = useState(0);
  const [deleting, setDeleting] = useState(false);
  const [history, setHistory] = useState<{ id: string; ordinal: number }[]>();
  const [historical, setHistorical] = useState<Note>();
  const [latest, setLatest] = useState<Note>();
  const [blocked, setBlocked] = useState(false);
  const generation = useRef(0);
  const pending: { current?: NoteCommand } = store.commands.get(draftKey) ?? {};
  store.commands.set(draftKey, pending);
  const headers = studyHelpHeaders(studyHelpContext);
  const boundary = JSON.stringify(studyHelpContext);
  const dirty = !draft.base || draft.title !== draft.base.title || draft.text !== draft.base.text;
  const valid = !!draft.title.trim() && !!draft.text.trim() && draft.text.length <= 4 * 1024 * 1024;
  function failure(caught: unknown) {
    setError(caught);
    if (caught instanceof ApiError && [403, 404, 410].includes(caught.status)) {
      setBlocked(true); setHistorical(undefined); setHistory(undefined); setLatest(undefined);
    }
  }
  function remember(value: NoteDraft) { store.notes.set(draftKey, value); setDraft(value); }
  function choose(id: string) {
    if (busy || pending.current) return;
    store.selected.set(scope, id); select(id); setHistorical(undefined); setHistory(undefined); setLatest(undefined); setDeleting(false); setMessage(''); setBlocked(false);
  }
  useEffect(() => {
    const epoch = ++generation.current, controller = new AbortController();
    const abort = () => controller.abort(); signal?.addEventListener('abort', abort, { once: true });
    if (signal?.aborted) controller.abort();
    setError(undefined); setLoading(selected !== 'new');
    const retained = store.notes.get(draftKey);
    setDraft(retained ?? { title: '', text: '' });
    void api<{ items: NoteSummary[] }>('/library/notes' + (projectId ? '?project_id=' + encodeURIComponent(projectId) : ''), { signal: controller.signal, headers })
      .then(value => { if (!controller.signal.aborted && generation.current === epoch) { setItems(value.items); if (selected === 'new') setBlocked(false); } })
      .catch(caught => { if (!controller.signal.aborted && generation.current === epoch && !isCancelled(caught)) failure(caught); });
    if (selected !== 'new') void api<Note>(path(selected), { signal: controller.signal, headers }).then(value => {
      if (controller.signal.aborted || generation.current !== epoch) return;
      if (!retained || (retained.base && retained.title === retained.base.title && retained.text === retained.base.text)) {
        const next = { title: value.title, text: value.text, base: value }; store.notes.set(draftKey, next); setDraft(next);
      } else if (retained.base?.revision_id !== value.revision_id) { setLatest(value); setMessage('A newer revision exists. Compare it with your retained draft before saving.'); }
      setLoading(false); setBlocked(false);
    }).catch(caught => { if (!controller.signal.aborted && generation.current === epoch && !isCancelled(caught)) { setLoading(false); failure(caught); } });
    return () => { generation.current++; controller.abort(); signal?.removeEventListener('abort', abort); };
  }, [draftKey, projectId, boundary, refresh, signal]);

  async function execute() {
    if (busy || !pending.current) return;
    const command = pending.current, epoch = generation.current;
    setBusy(true); setError(undefined);
    try {
      const result = await api<Note | { deleted: true }>(command.url, { method: command.method,
        body: command.body, headers: { ...command.headers, 'Idempotency-Key': command.key }, signal });
      if (epoch !== generation.current || signal?.aborted) return;
      pending.current = undefined; changed();
      if ('deleted' in result) {
        store.notes.delete(draftKey); store.selected.delete(scope); select('new'); setDeleting(false);
        setMessage('Note deleted. Earlier references now show that the source is unavailable.');
      } else {
        const value = { title: result.title, text: result.text, base: result };
        setLoading(true);
        store.notes.delete(draftKey); store.notes.set(result.document_id, value); store.selected.set(scope, result.document_id);
        select(result.document_id); setDraft(value); setMessage('Saved · Revision ' + result.ordinal); setHistory(undefined);
      }
      reload(value => value + 1);
    } catch (caught) {
      if (epoch === generation.current && !isCancelled(caught)) {
        failure(caught);
        // A stale revision needs a new explicit comparison and command. The
        // backend's retryable flag means the workflow can recover, not that the
        // same stale revision should be sent again.
        const stale = caught instanceof ApiError && ['note_revision_conflict', 'note_rights_changed'].includes(caught.code);
        if (caught instanceof ApiError && caught.status >= 400 && caught.status < 500 && (!caught.retryable || stale)) pending.current = undefined;
        if (caught instanceof ApiError && caught.status === 409 && (!caught.retryable || stale)) reload(value => value + 1);
      }
    } finally { if (epoch === generation.current) setBusy(false); }
  }
  function save(event: FormEvent) {
    event.preventDefault(); if (busy || !valid || latest || blocked) return;
    if (!pending.current) {
      const key = crypto.randomUUID();
      pending.current = { key, method: draft.base ? 'PUT' : 'POST', url: draft.base ? path(draft.base.document_id) : '/library/notes', headers,
        body: { title: draft.title.trim(), text: draft.text, idempotency_key: key,
          ...(draft.base ? { expected_revision_id: draft.base.revision_id } : projectId ? { project_id: projectId } : {}) } };
    }
    void execute();
  }
  async function useSaved() {
    if (!draft.base || dirty || busy || draft.text.length > 16000) return;
    const epoch = generation.current;
    setBusy(true); setError(undefined);
    try {
      const note = await api<Note>(path(draft.base.document_id) + '?revision_id=' + encodeURIComponent(draft.base.revision_id), { headers, signal });
      if (!signal?.aborted && epoch === generation.current) await onUse({ title: note.title, text: note.text, reference: note.reference });
    } catch (caught) { if (epoch === generation.current && !isCancelled(caught)) failure(caught); }
    finally { if (epoch === generation.current) setBusy(false); }
  }
  async function readHistory(revisionId?: string) {
    if (!draft.base || busy || loading) return;
    const epoch = generation.current;
    setBusy(true); setError(undefined);
    try {
      if (revisionId) {
        const value = await api<Note>(path(draft.base.document_id) + '?revision_id=' + encodeURIComponent(revisionId), { headers, signal });
        if (epoch === generation.current && !signal?.aborted) setHistorical(value);
      }
      else {
        const document = await api<{ revisions: { id: string; ordinal: number }[] }>('/library/documents/' + encodeURIComponent(draft.base.document_id), { headers, signal });
        if (epoch === generation.current && !signal?.aborted) setHistory(document.revisions);
      }
    } catch (caught) { if (epoch === generation.current && !isCancelled(caught)) failure(caught); }
    finally { if (epoch === generation.current) setBusy(false); }
  }
  return <section className="study-notes" aria-label="Study notes">
    <div className="notes-heading"><h3>Study notes</h3><Button variant="ghost" disabled={busy || !!pending.current} onClick={() => choose('new')}>New note</Button></div>
    <p className="notes-meta">{projectId ? 'Linked to this project' : 'Your personal notes'} · Saved revisions retain earlier citations.</p>
    {!!items?.length && <Select label="Open note" value={selected} disabled={busy || !!pending.current} onChange={event => choose(event.target.value)}>
      <option value="new">New note</option>{items.map(note => <option key={note.document_id} value={note.document_id}>{note.title} · Revision {note.ordinal}</option>)}</Select>}
    {message && <Notice>{message}</Notice>}
    {!!error && <ErrorState title="The note needs attention" error={error} onRetry={pending.current ? () => void execute() : () => reload(value => value + 1)} />}
    {latest && !blocked && <article className="notes-history"><h4>Latest saved revision {latest.ordinal}</h4><p className="notes-original">{latest.text}</p>
      <Button variant="secondary" onClick={() => { remember({ ...draft, base: latest }); setLatest(undefined); setMessage('Your edits are retained. Save will create a revision after the latest one.'); }}>Keep my edits after this revision</Button>
      <Button variant="ghost" onClick={() => { remember({ title: latest.title, text: latest.text, base: latest }); setLatest(undefined); setMessage('Opened the latest saved revision.'); }}>Replace draft with latest</Button></article>}
    {loading ? <LoadingState label="Opening saved note" /> : blocked ? <Notice>This note is unavailable. Its saved contents are hidden until access is restored.</Notice> : <form onSubmit={save}>
      <Input label="Note title" value={draft.title} maxLength={500} required disabled={busy || !!pending.current} onChange={event => remember({ ...draft, title: event.target.value })} />
      <Textarea label="Note" className="notes-editor" value={draft.text} rows={12} maxLength={4 * 1024 * 1024} required disabled={busy || !!pending.current}
        onChange={event => remember({ ...draft, text: event.target.value })} hint="Write your own study notes. Save creates an immutable revision." />
      <Button className="notes-use" variant="secondary" disabled={busy || dirty || !draft.base || draft.text.length > 16000} onClick={() => void useSaved()}><MessageCircle size={20} aria-hidden="true" />Use note in chat</Button>
      {draft.text.length > 16000 && <Notice>Open the saved original to choose a shorter passage for chat.</Notice>}
      <p className="notes-meta" role="status">{draft.base ? 'Revision ' + draft.base.ordinal + (dirty ? ' · Unsaved changes' : ' · Saved') : 'Not saved yet'}</p>
      <Button className="notes-save" type="submit" busy={busy} disabled={!valid || !!latest || (!dirty && !pending.current)}><Check size={20} aria-hidden="true" />{pending.current ? (pending.current.method === 'DELETE' ? 'Retry deletion' : 'Retry save') : 'Save note'}</Button>
    </form>}
    {draft.base && !blocked && <div className="notes-actions"><Button variant="ghost" disabled={busy || loading || !!pending.current} onClick={() => void readHistory()}>Revision history</Button>
      <Button variant="ghost" disabled={busy || loading} onClick={() => onOpen(draft.base!)}>Open saved original</Button>
      <Button variant="danger" disabled={busy || loading || !!pending.current} onClick={() => setDeleting(true)}>Delete note</Button></div>}
    {history && <div className="notes-history"><h4>Saved revisions</h4>{history.map(revision => <Button variant="ghost" key={revision.id} disabled={busy} onClick={() => void readHistory(revision.id)}>Revision {revision.ordinal}</Button>)}</div>}
    {historical && <article className="notes-history"><h4>{historical.title} · Revision {historical.ordinal}</h4><p className="notes-original">{historical.text}</p><Button variant="ghost" onClick={() => setHistorical(undefined)}>Close revision</Button></article>}
    {deleting && !blocked && <div className="notes-delete" role="group" aria-label="Confirm note deletion"><p>Delete every revision and its originals? Project links will be removed. Existing citations will show an unavailable source.</p>
      <Button variant="danger" busy={busy} onClick={() => {
        if (!draft.base || pending.current) return;
        pending.current = { key: crypto.randomUUID(), method: 'DELETE', url: path(draft.base.document_id) + '?expected_revision_id=' + encodeURIComponent(draft.base.revision_id), headers };
        void execute();
      }}>Delete all revisions</Button><Button variant="ghost" disabled={busy} onClick={() => setDeleting(false)}>Keep note</Button></div>}
  </section>;
}
