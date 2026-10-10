import { useEffect, useRef, useState, type FormEvent } from 'react';
import { api } from '../../platform/api';
import type { ContentReference } from '../../platform/designC';
import { useResource } from '../../platform/useResource';
import { Badge, Button, EmptyState, ErrorState, Input, LoadingState, Notice, Select, Textarea } from '../../ui';
import type { LibraryDocument } from '../library/types';
import CandidateEditor from './CandidateEditor';
import { getImport, getImportOriginal, importBase, importPath, listImports } from './api';
import { importMessage, keyLabel, type ImportCancellation, type ImportDraft, type ImportedVersion, type ImportIntent, type ImportOriginal } from './types';
import { useImportCommand } from './useImportCommand';
import './imports.css';

export interface ImportPanelProps {
  importId?: string; sourceRevisionId?: string;
  onSaved?: (selection: ImportedVersion) => void; onOpenVersion?: (selection: ImportedVersion) => void;
  onOpenSource?: (reference: ContentReference) => void;
}

// Review is the focal task: a spacious question and a quieter immutable original
// share a reading surface. Paper/teal tokens, borders and a 4px rhythm follow C.
export default function ImportPanel({ importId, sourceRevisionId, onSaved, onOpenVersion, onOpenSource }: ImportPanelProps) {
  const [title, setTitle] = useState('Imported practice'), [text, setText] = useState('');
  const [terms, setTerms] = useState(''), [permission, setPermission] = useState(false);
  const [kind, setKind] = useState<'paste' | 'library_revision'>(sourceRevisionId ? 'library_revision' : 'paste');
  const [source, setSource] = useState(sourceRevisionId ?? '');
  const [selected, setSelected] = useState(importId ?? ''), [draft, setDraft] = useState<ImportDraft | null>(null);
  const [original, setOriginal] = useState<ImportOriginal | null>(null), [candidateId, setCandidateId] = useState('');
  const [readError, setReadError] = useState<unknown>(null), [refresh, setRefresh] = useState(0);
  const [dirty, setDirty] = useState(false), [denied, setDenied] = useState(false), [deleteConfirmed, setDeleteConfirmed] = useState(false);
  const mutation = useImportCommand(), sequence = useRef(0), seen = useRef(new Set<string>());
  const saved = useRef(onSaved); saved.current = onSaved;
  const command = useRef(mutation); command.current = mutation;
  const { resource: history, retry: reloadHistory } = useResource(signal => listImports(signal));
  const { resource: library, retry: reloadLibrary } = useResource(signal => api<{ documents: LibraryDocument[] }>('/library/documents?limit=100', { signal }));
  useEffect(() => { if (importId) { sequence.current++; setSelected(importId); setDraft(null); setOriginal(null); setDirty(false); setRefresh(value => value + 1); } }, [importId]);
  useEffect(() => { if (sourceRevisionId) { setSource(sourceRevisionId); setKind('library_revision'); } }, [sourceRevisionId]);
  useEffect(() => {
    function restrict() { sequence.current++; command.current.clear(); setDenied(true); setDraft(null); setOriginal(null);
      setText(''); setTerms(''); setTitle('Imported practice'); setPermission(false); setDirty(false); }
    window.addEventListener('renulus:assessment-policy', restrict);
    return () => window.removeEventListener('renulus:assessment-policy', restrict);
  }, []);
  useEffect(() => {
    if (!selected || denied) return;
    const controller = new AbortController(), current = ++sequence.current;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function read() {
      try {
        const [value, immutable] = await Promise.all([getImport(selected, controller.signal), getImportOriginal(selected, controller.signal)]);
        if (controller.signal.aborted || current !== sequence.current) return;
        setDraft(value); setOriginal(immutable); setReadError(null);
        setCandidateId(id => value.candidates.some(item => item.id === id) ? id : value.candidates[0]?.id ?? '');
        if (value.state === 'running') timer = setTimeout(() => void read(), 750);
      } catch (error) { if (!controller.signal.aborted && current === sequence.current) setReadError(error); }
    }
    void read(); return () => { controller.abort(); clearTimeout(timer); };
  }, [selected, refresh, denied]);
  useEffect(() => {
    if (draft?.result && draft.result_available && !seen.current.has(draft.result.version_id)) {
      seen.current.add(draft.result.version_id); saved.current?.(draft.result);
    }
  }, [draft]);
  function received(value: ImportDraft) {
    sequence.current++; setDraft(value); setSelected(value.id); setReadError(null); reloadHistory();
    if (!original || value.state === 'running') setRefresh(number => number + 1);
    setCandidateId(id => value.candidates.some(item => item.id === id) ? id : value.candidates[0]?.id ?? '');
  }
  function create(event: FormEvent) {
    event.preventDefault();
    const intent: ImportIntent = { title, original: kind === 'paste'
      ? { kind: 'paste', text, terms, permission_confirmed: true } : { kind: 'library_revision', revision_id: source } };
    mutation.mutate<ImportDraft>(importBase, intent, value => { setText(''); setTerms(''); setPermission(false); received(value); });
  }
  function action(operation: 'normalize' | 'retry' | 'save') {
    if (draft) mutation.mutate<ImportDraft>(importPath(draft.id) + '/' + operation, { expected_revision: draft.revision }, received);
  }
  function cancel() {
    if (selected) mutation.mutate<ImportCancellation>(importPath(selected) + '/cancel', {}, receipt => {
      if (!denied) { setDraft(value => value ? { ...value, state: receipt.state } : null); setRefresh(number => number + 1); reloadHistory(); }
    });
  }
  const candidate = draft?.candidates.find(item => item.id === candidateId);
  const retained = draft?.candidates.filter(item => !item.removed) ?? [];
  const ready = retained.length > 0 && retained.every(item => item.review_confirmed && item.key_state === 'resolved');
  const published = draft?.state === 'published', active = draft?.state === 'running';
  const location = candidate?.original.span;
  const segment = original?.original.segments.find(item => location && item.start < location.end && location.start < item.end);
  const sourceReference: ContentReference | undefined = segment?.reference ?? (draft?.source_revision_id && segment?.locator
    ? { target: { type: 'library_revision', id: draft.source_revision_id }, locator: segment.locator } : original?.original.source_pin?.reference);
  const revisions = library.status === 'ready' ? library.data.documents.flatMap(document => document.revisions.filter(revision =>
    document.scope?.kind === 'personal-library' && revision.status === 'ready' && revision.rights.display && revision.rights.cache && revision.rights.model_input && revision.rights.derivation)
    .map(revision => ({ id: revision.id, label: document.title + ' · revision ' + revision.ordinal }))) : [];
  if (denied) return <div className="import-panel"><Notice>Import assistance is paused during Test. You can stop normalization without opening its content.</Notice>
    {mutation.error !== null && <ErrorState title="Stop needs a retry" error={mutation.error} onRetry={mutation.retry} />}
    <div className="actions">{selected && <Button variant="secondary" disabled={mutation.locked} onClick={cancel}>Stop normalization</Button>}
      <Button variant="ghost" onClick={() => { setDenied(false); setRefresh(value => value + 1); reloadHistory(); reloadLibrary(); }}>Check import availability</Button></div></div>;
  return <div className="import-panel">
    {mutation.error !== null && <div><ErrorState title="Your command needs a retry" error={mutation.error} onRetry={mutation.retry} />
      {mutation.canReload && <Button variant="secondary" onClick={() => { mutation.reload(); setRefresh(value => value + 1); }}>Reload saved state, keep unsaved edits</Button>}</div>}
    <details className="import-create panel" open={!selected}><summary>Import a private test</summary>
      <form onSubmit={create}>
        <p>Save a permitted original first. Normalize formatting separately, then review the answers yourself.</p>
        <div className="import-create-fields"><Input label="Import title" value={title} required maxLength={120} disabled={mutation.locked || dirty} onChange={event => setTitle(event.target.value)} />
          <Select label="Original source" value={kind} disabled={mutation.locked || dirty} onChange={event => setKind(event.target.value as typeof kind)}>
            <option value="paste">Paste test text</option><option value="library_revision">Saved Library revision</option></Select></div>
        {kind === 'paste' ? <><Textarea label="Original test text" value={text} rows={7} maxLength={96000} required disabled={mutation.locked || dirty} onChange={event => setText(event.target.value)}
          hint="This explicit action stores the exact original privately, including whitespace. Up to 96,000 characters." />
          <Textarea label="Retained permission or terms" value={terms} rows={2} maxLength={2000} required disabled={mutation.locked || dirty} onChange={event => setTerms(event.target.value)} />
          <label className="import-check"><input type="checkbox" checked={permission} disabled={mutation.locked || dirty} onChange={event => setPermission(event.target.checked)} />I may store and use this text for private model-assisted practice</label></>
          : <><Select label="Saved Library revision" value={source} required disabled={mutation.locked || dirty || library.status !== 'ready'} onChange={event => setSource(event.target.value)}>
            <option value="">Choose an extracted saved revision</option>{source && !revisions.some(item => item.id === source) && <option value={source}>Selected saved revision · eligibility checked on Save</option>}
            {revisions.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</Select>
            <p className="import-caption">Successful extraction, original integrity and current permissions are checked by Library before import.</p>
            {library.status === 'error' && <ErrorState title="Library could not be loaded" error={library.error} onRetry={reloadLibrary} />}</>}
        <Button type="submit" busy={mutation.busy} disabled={mutation.locked || dirty || !title.trim() || (kind === 'paste' ? !text.trim() || !terms.trim() || !permission : !source)}>Save private original</Button>
      </form></details>
    <section className="import-history" aria-label="Private imports"><div className="import-heading"><h2>Your imports</h2><Button variant="ghost" disabled={dirty} onClick={reloadHistory}>Refresh imports</Button></div>
      {history.status === 'loading' && <LoadingState label="Loading retained imports" />}
      {history.status === 'error' && <ErrorState error={history.error} onRetry={reloadHistory} />}
      {history.status === 'ready' && (history.data.items.length ? <div className="import-history-list">{history.data.items.map(item => <button key={item.id} className="import-history-row"
        aria-pressed={selected === item.id} disabled={mutation.locked || dirty} onClick={() => { sequence.current++; setSelected(item.id); setDraft(null); setOriginal(null); setReadError(null); setDeleteConfirmed(false); setRefresh(value => value + 1); }}>
        <strong>{item.title}</strong><span>{item.candidate_count} questions · {item.state === 'published' ? 'Saved' : item.state === 'running' ? 'Normalizing' : 'Retained draft'}</span></button>)}</div>
        : <p className="import-caption">Your private originals and review progress will appear here.</p>)}
    </section>
    {selected && <section className="import-review" aria-label="Import review">
      {readError !== null && <ErrorState title="This import could not be opened" error={readError} onRetry={() => setRefresh(value => value + 1)} />}
      {!draft && readError === null && <LoadingState label="Loading private original and candidates" />}
      {draft && <><div className="import-heading"><div><h2>{draft.title}</h2><p>{importMessage(draft)}</p></div><Badge tone={published ? 'default' : 'neutral'}>{published ? 'Saved personal practice' : 'Private draft'}</Badge></div>
        <div className="import-toolbar"><span>{retained.filter(item => item.review_confirmed).length} of {retained.length} retained questions reviewed · {draft.call_count} of {draft.max_calls} normalization requests</span>
          <div className="actions">{active ? <Button variant="secondary" disabled={mutation.locked} onClick={cancel}>Stop normalization</Button> : !published && <Button variant="secondary" disabled={mutation.locked || dirty || draft.call_count >= draft.max_calls}
            onClick={() => action(draft.state === 'failed' || draft.state === 'cancelled' ? 'retry' : 'normalize')}>{draft.call_count ? 'Retry normalization explicitly' : 'Normalize with selected connection'}</Button>}
            {!published && <Button disabled={mutation.locked || dirty || active || !ready} onClick={() => action('save')}>Save {retained.length} reviewed questions</Button>}
            {draft.result && <Button disabled={!draft.result_available || !onOpenVersion} onClick={() => { if (draft.result) onOpenVersion?.(draft.result); }}>Open saved test</Button>}</div></div>
        {draft.candidates.length === 0 && <EmptyState title="This layout needs normalization"><p>The original is saved. Normalize with your selected connection to propose source-mapped candidates.</p></EmptyState>}
        {!!draft.candidates.length && <div className="import-review-layout"><nav className="import-candidates" aria-label="Imported questions">
          {draft.candidates.map((item, index) => <button key={item.id} aria-current={candidateId === item.id ? 'true' : undefined} disabled={mutation.locked || dirty} onClick={() => setCandidateId(item.id)}>
            <strong>Question {index + 1}</strong><span>{keyLabel(item)}</span></button>)}</nav>
          {candidate && <CandidateEditor key={candidate.id} candidate={candidate} ordinal={draft.candidates.indexOf(candidate) + 1} locked={mutation.locked} immutable={published}
            onDirty={setDirty} onEdit={(value, done) => mutation.mutate<ImportDraft>(importPath(draft.id) + '/candidates/' + encodeURIComponent(candidate.id) + '/edit',
              { ...value, expected_revision: draft.revision }, updated => { done(); received(updated); })}
            onResolve={keys => mutation.mutate<ImportDraft>(importPath(draft.id) + '/candidates/' + encodeURIComponent(candidate.id) + '/resolve',
              { correct_option_ids: keys, review_confirmed: true, expected_revision: draft.revision }, received)}
            onVisibility={removed => mutation.mutate<ImportDraft>(importPath(draft.id) + '/candidates/' + encodeURIComponent(candidate.id) + '/visibility',
              { removed, expected_revision: draft.revision }, received)} />}
          <aside className="import-original" aria-label="Immutable original"><div className="import-heading"><h3>Original text</h3><Badge tone="neutral">Unchanged</Badge></div>
            <p className="import-caption">{location ? 'Characters ' + location.start + '–' + location.end + ' · end exclusive' : 'Exact retained original'}</p>
            <pre>{original && location ? original.text.slice(location.start, location.end) : original?.text}</pre>
            {onOpenSource && sourceReference && <Button variant="secondary" onClick={() => onOpenSource(sourceReference)}>Open original location</Button>}
            <details><summary>Full original and retained terms</summary><pre>{original?.text}</pre><p>{original?.original.terms}</p>
              {original?.original.diagnostics.map((item, index) => <p key={index}>{item.message ?? item.code}</p>)}</details>
          </aside></div>}
        <details className="import-delete"><summary>Delete private import</summary><p>Deletes the original and review draft. A separately saved test remains in your collection.</p>
          <label className="import-check"><input type="checkbox" checked={deleteConfirmed} disabled={mutation.locked || dirty} onChange={event => setDeleteConfirmed(event.target.checked)} />Delete this private original and its draft</label>
          <Button variant="danger" disabled={mutation.locked || dirty || !deleteConfirmed} onClick={() => mutation.mutate(importPath(draft.id) + '/delete', { expected_revision: draft.revision }, () => {
            sequence.current++; setSelected(''); setDraft(null); setOriginal(null); setCandidateId(''); setDeleteConfirmed(false); reloadHistory(); })}>Delete import</Button></details>
      </>}
    </section>}
  </div>;
}
