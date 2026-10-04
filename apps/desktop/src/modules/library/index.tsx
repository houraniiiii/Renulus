import { useEffect, useState } from 'react';
import { FileText, Search, Upload } from 'lucide-react';
import { api, apiResponse } from '../../platform/api';
import { useResource } from '../../platform/useResource';
import { useNavigation } from '../../shell/navigation';
import { Badge, Button, EmptyState, ErrorState, Input, LoadingState, Notice, PageHeader, Panel, Select, Textarea } from '../../ui';
import type { Capabilities, Catalogue, CatalogueEntry, Citation, ImportResult, LibraryDocument, Passage, Rights } from './types';
import './library.css';

const libraryScope = { kind: 'personal-library' as const };
const permissions: Rights = { display: true, cache: true, index: true, embedding: true, model_input: true,
  derivation: false, evaluation: false, redistribution: false, licence: 'user-supplied permission',
  permission_reference: 'User confirms local library processing for the selected file', attribution: '' };
const labels: Record<string, string> = { ready: 'Indexed', queued: 'Queued', processing: 'Processing', failed: 'Import failed', cancelled: 'Cancelled', acquired: 'Acquired' };
const statusLabel = (value: string) => labels[value] ?? value;
const statusTone = (value: string): 'default' | 'warning' | 'error' | 'neutral' =>
  value === 'failed' ? 'error' : value === 'ready' ? 'default' : value === 'processing' || value === 'queued' ? 'warning' : 'neutral';

export default function LibraryPage() {
  const navigation = useNavigation();
  const temporary = navigation.scope.kind === 'temporary-case' || navigation.scope.kind === 'unclassified';
  const [mode, setMode] = useState<'browse' | 'text' | 'file' | 'catalogue'>('browse');
  const [title, setTitle] = useState('');
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [allowed, setAllowed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [message, setMessage] = useState('');
  const [query, setQuery] = useState('');
  const [currentOnly, setCurrentOnly] = useState(false);
  const [hits, setHits] = useState<Passage[] | null>(null);
  const [selectedDocument, setSelectedDocument] = useState<LibraryDocument | null>(null);
  const [citation, setCitation] = useState<Citation | null>(null);
  const [original, setOriginal] = useState<{ url: string; type: string; text?: string } | null>(null);
  const [selectedEntries, setSelectedEntries] = useState<Set<string>>(new Set());
  const [sourceId, setSourceId] = useState('E01');
  const [offset, setOffset] = useState(0);
  const documents = useResource(signal => api<{ documents: LibraryDocument[] }>('/library/documents', { signal }));
  const capabilities = useResource(signal => api<Capabilities>('/library/capabilities', { signal }));
  const catalogue = useResource(signal => api<Catalogue>('/library/collection/catalogue?limit=50&offset=' + offset + (sourceId ? '&source_id=' + encodeURIComponent(sourceId) : ''), { signal }));
  const ready = capabilities.resource.status === 'ready' ? capabilities.resource.data : null;
  const processing = documents.resource.status === 'ready' && documents.resource.data.documents.some(d => d.status === 'queued' || d.status === 'processing');

  useEffect(() => { if (temporary) { setText(''); setTitle(''); setFile(null); setMode('browse'); } }, [temporary]);
  useEffect(() => { catalogue.retry(); setSelectedEntries(new Set()); }, [sourceId, offset]);
  useEffect(() => {
    const documentId = navigation.handoff?.document_id;
    const revision = navigation.handoff?.document_revision ?? navigation.handoff?.revision_id;
    if (typeof documentId !== 'string') return;
    const controller = new AbortController();
    api<LibraryDocument>('/library/documents/' + encodeURIComponent(documentId), { signal: controller.signal })
      .then(value => { if (!controller.signal.aborted) setSelectedDocument(value); }).catch(value => { if (!controller.signal.aborted) setError(value); });
    const page = navigation.handoff?.page;
    if (typeof revision === 'string') api<Citation>('/library/revisions/' + encodeURIComponent(revision) + '/citation' + (typeof page === 'number' && Number.isInteger(page) && page > 0 ? '?page=' + page : ''), { signal: controller.signal })
      .then(value => { if (!controller.signal.aborted) setCitation(value); }).catch(() => {});
    return () => controller.abort();
  }, [navigation.revision]);
  useEffect(() => {
    if (!processing) return;
    const timer = window.setInterval(() => { documents.retry(); catalogue.retry(); }, 3000);
    return () => window.clearInterval(timer);
  }, [processing]);
  useEffect(() => () => { if (original?.url) URL.revokeObjectURL(original.url); }, [original?.url]);

  async function act(action: () => Promise<void>) {
    setBusy(true); setError(undefined); setMessage('');
    try { await action(); documents.retry(); catalogue.retry(); } catch (caught) { setError(caught); } finally { setBusy(false); }
  }
  async function addText() {
    await act(async () => {
      const result = await api<ImportResult>('/library/import/text', { method: 'POST', body: {
        title: title.trim() || 'Personal study note', text, scope: libraryScope, idempotency_key: crypto.randomUUID() } });
      setMessage(statusLabel(result.status) + ': your note has an import job.'); setText(''); setTitle(''); setMode('browse');
    });
  }
  async function addFile() {
    if (!file) return;
    await act(async () => {
      const options = { title: title.trim() || file.name, scope: libraryScope, rights: permissions, idempotency_key: crypto.randomUUID() };
      const result = await api<ImportResult>('/library/import/file', { method: 'POST', body: file,
        headers: { 'x-renulus-filename': encodeURIComponent(file.name), 'x-renulus-import-options': JSON.stringify(options) } });
      setMessage(statusLabel(result.status) + ': follow processing below.'); setFile(null); setTitle(''); setAllowed(false); setMode('browse');
    });
  }
  async function search() {
    await act(async () => {
      const result = await api<{ passages: Passage[] }>('/library/retrieve', { method: 'POST', body: { query, scope: navigation.scope, current_only: currentOnly } });
      setHits(result.passages);
    });
  }
  async function inspect(document: LibraryDocument, passage?: Passage) {
    setSelectedDocument(document); setOriginal(null); setCitation(null);
    const revision = passage?.document_revision ?? document.active_revision;
    if (!revision) return;
    const page = passage?.locators.find(p => p.page)?.page;
    const value = await api<Citation>('/library/revisions/' + revision + '/citation' + (page ? '?page=' + page : ''));
    setCitation(value);
  }
  async function openOriginal() {
    if (!citation) return;
    await act(async () => {
      const response = await apiResponse(citation.original_url);
      const blob = await response.blob();
      setOriginal({ url: URL.createObjectURL(blob), type: blob.type, text: blob.type.startsWith('text/') ? await blob.text() : undefined });
    });
  }
  async function remove(document: LibraryDocument) {
    await act(async () => {
      const result = await api<{ cleanup_pending: boolean }>('/library/documents/' + document.id, { method: 'DELETE' });
      setSelectedDocument(null); setCitation(null); setOriginal(null); setHits(null);
      setMessage(result.cleanup_pending ? 'Removed from retrieval. Storage cleanup is still pending.' : 'Removed from your library. Your external original is preserved.');
    });
  }
  async function catalogueSources() {
    await act(async () => {
      const result = await api<{ catalogued: number; errors: unknown[] }>('/library/collection/catalogue' + (sourceId ? '?source_id=' + encodeURIComponent(sourceId) : ''), { method: 'POST', timeoutMs: 600_000 });
      setMessage(result.catalogued + ' resources catalogued. ' + (result.errors.length ? result.errors.length + ' metadata entries need checking.' : 'Select the files you want to process.'));
    });
  }
  async function importSelected() {
    await act(async () => {
      const result = await api<{ queued: number }>('/library/collection/import', { method: 'POST', body: { entry_ids: [...selectedEntries], scope: libraryScope } });
      setSelectedEntries(new Set()); setMessage(result.queued + ' imports queued. Processing states appear beside each source.');
    });
  }
  function toggleEntry(entry: CatalogueEntry) {
    setSelectedEntries(previous => { const next = new Set(previous); if (next.has(entry.id)) next.delete(entry.id); else next.add(entry.id); return next; });
  }

  return <>
    <PageHeader title="Your library" description="Read, search and return to the sources behind your learning." actions={<>
      <Button variant="secondary" onClick={() => setMode('catalogue')}>Collected sources</Button>
      <Button disabled={temporary} onClick={() => setMode('text')}><FileText size={18} />Add to library</Button>
    </>} />
    {temporary && <Notice tone="warning"><p>You are in a temporary context. Browse existing sources here; adding a document requires ending that context.</p></Notice>}
    {ready && !ready.text_import && <Notice tone="warning"><p>Document processing is unavailable in this build. You can inspect the collection catalogue while the bundled helpers are completed.</p></Notice>}
    {message && <Notice><p>{message}</p></Notice>}
    {error !== undefined && <ErrorState error={error} title="The library action could not finish" />}
    <div className="library-layout">
      <div className="library-main">
        {(mode === 'text' || mode === 'file') && <Panel><div className="library-mode">
          <Button variant={mode === 'text' ? 'primary' : 'ghost'} onClick={() => setMode('text')}>Study note</Button>
          <Button variant={mode === 'file' ? 'primary' : 'ghost'} onClick={() => setMode('file')}><Upload size={16} />Document</Button>
        </div><div className="library-form">
          <Input label="Title" value={title} onChange={event => setTitle(event.target.value)} maxLength={500} />
          {mode === 'text' ? <Textarea label="Your study note" value={text} onChange={event => setText(event.target.value)} hint="Deliberately added study material is saved in your personal library." /> : <>
            <Input label="Choose a PDF, image or text file" type="file" accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.txt,.md" onChange={event => setFile(event.target.files?.[0] ?? null)} />
            <label className="library-check"><input type="checkbox" checked={allowed} onChange={event => setAllowed(event.target.checked)} />I have permission to read, store, index and use this file for local learning.</label>
            <p className="muted">Maximum 64 MiB. Original terms remain attached to the file.</p>
            <p className="muted">Add teaching material here. Patient material belongs in a temporary case and requires a verified temporary extraction path.</p>
          </>}
          <div className="actions"><Button busy={busy} disabled={temporary || (mode === 'text' ? !text.trim() || !ready?.text_import : !file || !allowed || !(file.name.endsWith('.txt') || file.name.endsWith('.md') ? ready?.text_import : ready?.pdf_image_import))} onClick={mode === 'text' ? addText : addFile}>Add {mode === 'text' ? 'note' : 'document'}</Button>
            <Button variant="ghost" onClick={() => setMode('browse')}>Close</Button></div>
        </div></Panel>}
        {mode === 'catalogue' && <section className="section">
          <div className="library-section-title"><h2>Collected sources</h2><Button variant="ghost" onClick={() => setMode('browse')}>Back to library</Button></div>
          <div className="library-tools"><Select label="Source register" value={sourceId} onChange={event => { setSourceId(event.target.value); setOffset(0); }}>
            <option value="">All collected sources</option><option value="E01">ERA Neph-Manual</option><option value="K01">KDIGO CKD</option><option value="K02">KDIGO anemia</option><option value="E06">Educational reviews</option><option value="L02">PMC full text</option>
          </Select><Button variant="secondary" busy={busy} onClick={catalogueSources}>Read collection catalogue</Button></div>
          <p className="muted">Acquired files appear immediately. Only completed imports enter search. The manual receipt date does not establish an edition.</p>
          {catalogue.resource.status === 'loading' ? <LoadingState label="Loading collected source records" /> : catalogue.resource.status === 'error' ? <ErrorState error={catalogue.resource.error} onRetry={catalogue.retry} /> : <>
            {catalogue.resource.data.entries.length === 0 ? <EmptyState title="This collection has no catalogue records yet"><p>Read the collection metadata to list its acquired files, then select a processing batch.</p></EmptyState> : <>
              <Button busy={busy} disabled={temporary || selectedEntries.size === 0} onClick={importSelected}>Queue selected ({selectedEntries.size})</Button>
              <ul className="library-list">{catalogue.resource.data.entries.map(entry => <li key={entry.id} className="library-catalogue-row">
                <label className="library-check"><input type="checkbox" aria-label={'Select ' + entry.title} checked={selectedEntries.has(entry.id)} disabled={temporary || entry.eligibility !== 'eligible' || entry.processing_status === 'ready'} onChange={() => toggleEntry(entry)} /></label>
                <div><h3>{entry.title}</h3><div className="library-meta"><Badge tone={statusTone(entry.processing_status)}>{statusLabel(entry.processing_status)}</Badge><span>{entry.metadata.collection_section ?? entry.source_id}</span><span>{(entry.bytes / 1024 / 1024).toFixed(1)} MiB</span></div>
                  {entry.eligibility !== 'eligible' && <p className="muted">{entry.reserved ? 'Reserved assessment material is excluded from learning retrieval.' : 'Processing permission or format needs verification.'}</p>}
                  {entry.error_code && <p className="field-error">Import needs attention: {entry.error_code}</p>}
                </div></li>)}</ul>
              <div className="library-pagination"><Button variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}>Previous</Button><span className="muted">{offset + 1}–{Math.min(offset + 50, catalogue.resource.data.total)} of {catalogue.resource.data.total}</span><Button variant="secondary" disabled={offset + 50 >= catalogue.resource.data.total} onClick={() => setOffset(offset + 50)}>Next</Button></div>
            </>}
          </>}
        </section>}
        {mode !== 'catalogue' && <>
          <form className="library-form" onSubmit={event => { event.preventDefault(); void search(); }}><div className="library-tools">
            <Input label="Find a passage" placeholder="Search your nephrology sources" value={query} onChange={event => setQuery(event.target.value)} />
            <Button type="submit" variant="secondary" busy={busy} disabled={!query.trim()}><Search size={18} />Search</Button>
          </div><label className="library-check"><input type="checkbox" checked={currentOnly} onChange={event => setCurrentOnly(event.target.checked)} />Only verified current guidance</label></form>
          {hits !== null && <section className="section"><div className="library-section-title"><h2>Passages</h2><Button variant="ghost" onClick={() => setHits(null)}>Clear results</Button></div>
            {hits.length === 0 ? <EmptyState title="No eligible passages matched"><p>Try another phrase or check whether the source has finished processing. Current-guidance search excludes sources with unverified currency.</p></EmptyState> : <div className="library-passages">{hits.map(hit => <article className="library-passage" key={hit.id}><h3>{hit.title}</h3><p>{hit.text}</p><div className="library-meta"><span>{hit.source_id}</span><span>{hit.locators.some(l => l.page) ? 'Page ' + [...new Set(hit.locators.filter(l => l.page).map(l => l.page))].join(', ') : 'Original text span'}</span></div><Button disabled={busy} variant="ghost" onClick={() => void act(async () => { const document = await api<LibraryDocument>('/library/documents/' + hit.document_id); await inspect(document, hit); })}>Inspect citation</Button></article>)}</div>}
          </section>}
          <section className="section"><h2>Documents</h2>
            {documents.resource.status === 'loading' ? <LoadingState label="Loading library documents" /> : documents.resource.status === 'error' ? <ErrorState error={documents.resource.error} onRetry={documents.retry} /> : documents.resource.data.documents.length === 0 ? <EmptyState title="Build a library you can return to"><p>Add a study note or an authorised document. Once processing finishes, passages keep their link to your original source.</p></EmptyState> : <ul className="library-list">{documents.resource.data.documents.map(document => <li key={document.id} className="library-document">
              <button disabled={busy} className="library-document-title" onClick={() => void act(() => inspect(document))}>{document.title}</button><div className="library-meta"><Badge tone={statusTone(document.status)}>{statusLabel(document.status)}</Badge><span>{document.source_id}</span>
                {document.active_revision && document.active_revision !== document.latest_revision && <span>Earlier indexed revision is available</span>}{document.reserved && <span>Reserved</span>}{document.cleanup_pending && <span>Storage cleanup pending</span>}</div>
              {(document.status === 'queued' || document.status === 'processing') && <Button variant="ghost" onClick={() => void act(async () => { const job = await api<ImportResult>('/library/documents/' + document.id + '/import-status'); await api('/library/jobs/' + job.job.id + '/cancel', { method: 'POST' }); })}>Cancel import</Button>}
            </li>)}</ul>}
          </section>
        </>}
      </div>
      <aside className="library-reader" aria-label="Source reader">{selectedDocument ? <>
        <h2>{selectedDocument.title}</h2><div className="library-meta"><Badge tone={statusTone(selectedDocument.status)}>{statusLabel(selectedDocument.status)}</Badge><span>{selectedDocument.source_id}</span></div>
        {(() => { const revision = selectedDocument.revisions.find(r => r.id === (citation?.document_revision ?? selectedDocument.active_revision)) ?? selectedDocument.revisions[0]; if (!revision) return null; return <dl>
          <div><dt>Edition and publication</dt><dd>{revision.metadata.edition ?? 'Edition unverified'}{revision.metadata.publication_date ? ' · ' + revision.metadata.publication_date : ''}</dd></div>
          <div><dt>Source currentness</dt><dd>{revision.metadata.latest_final_verified && revision.metadata.content_reviewed ? 'Latest final verified and content reviewed' : 'Not verified as current guidance'}</dd></div>
          <div><dt>Original terms</dt><dd>{revision.rights.licence}</dd></div>
          <div><dt>Extracted passages</dt><dd>{revision.passage_count}</dd></div>
        </dl>; })()}
        {citation && <><div className="actions"><Button variant="secondary" busy={busy} onClick={openOriginal}>Open original{citation.page ? ' · page ' + citation.page : ''}</Button></div><p className="muted">{citation.locators.length} original source locations preserved.</p></>}
        {original && (original.type.startsWith('image/') ? <img className="library-original-image" src={original.url} alt="Original imported document" /> : original.text !== undefined ? <pre className="library-original-text">{original.text}</pre> : <iframe className="library-original" title="Original document viewer" src={original.url + (citation?.page ? '#page=' + citation.page : '')} />)}
        <Button variant="danger" busy={busy} onClick={() => void remove(selectedDocument)}>Remove from library</Button>
      </> : <><FileText size={26} aria-hidden="true" /><h2>Keep the source in view</h2><p>Select a document or a passage to inspect its edition, permissions and original location.</p></>}</aside>
    </div>
  </>;
}
