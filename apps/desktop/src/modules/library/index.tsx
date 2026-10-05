import { useEffect, useRef, useState } from 'react';
import { FileText, Search, Upload } from 'lucide-react';
import { api, ApiError } from '../../platform/api';
import { useResource } from '../../platform/useResource';
import { useNavigation } from '../../shell/navigation';
import { Badge, Button, EmptyState, ErrorState, Input, LoadingState, Notice, PageHeader, Panel, Select, Textarea } from '../../ui';
import type { Capabilities, Catalogue, CatalogueEntry, ImportResult, LibraryDocument, Passage, Rights } from './types';
import { Discovery } from './Discovery';
import SourceInspector, { isPhysicalPage, type SourceLocation } from './SourceInspector';
import BulkImportControl from './BulkImportControl';
import './library.css';

const libraryScope = { kind: 'personal-library' as const };
const permissions: Rights = { display: true, cache: true, index: true, embedding: true, model_input: true,
  derivation: false, evaluation: false, redistribution: false, licence: 'user-supplied permission',
  permission_reference: 'User confirms local library processing for the selected file', attribution: '' };
const labels: Record<string, string> = { ready: 'Indexed', queued: 'Queued', processing: 'Processing', failed: 'Import failed', cancelled: 'Cancelled', acquired: 'Acquired' };
const statusLabel = (value: string) => labels[value] ?? value;
const statusTone = (value: string): 'default' | 'warning' | 'error' | 'neutral' =>
  value === 'failed' ? 'error' : value === 'ready' ? 'default' : value === 'processing' || value === 'queued' ? 'warning' : 'neutral';
const documentPageSize = 25;
const documentStatuses = ['ready', 'queued', 'processing', 'failed', 'cancelled'] as const;
type DocumentStatus = typeof documentStatuses[number];
type DocumentCounts = Partial<Record<DocumentStatus, number>>;
interface DocumentPage { documents: LibraryDocument[]; total: number; counts: DocumentCounts; offset: number; limit: number }
interface DocumentSnapshot { path: string; page: DocumentPage }
const collectionPageSize = 50;
const collectionEligibilityLabels = { eligible: 'Eligible', inspection_required: 'Candidates needing inspection', reserved: 'Reserved', unavailable: 'Unavailable' } as const;
type CollectionEligibility = keyof typeof collectionEligibilityLabels;
interface CataloguePage extends Catalogue { counts?: Partial<Record<CollectionEligibility, number>>; limit?: number }
interface CatalogueSnapshot { path: string; page: CataloguePage }
function requiresLicenceInspection(entry: CatalogueEntry) {
  const roles = (entry.metadata as CatalogueEntry['metadata'] & { asset_role?: string[] }).asset_role;
  return entry.source_id === 'L02' && entry.eligibility === 'inspection_required' && Array.isArray(roles) && roles.includes('acquired-jats');
}
function selectableEntry(entry: CatalogueEntry, temporary: boolean) {
  return !temporary && !entry.reserved && entry.processing_status !== 'ready' &&
    (entry.eligibility === 'eligible' || requiresLicenceInspection(entry));
}

async function loadDocumentPage(path: string, offset: number, signal: AbortSignal): Promise<DocumentSnapshot> {
  const page = await api<DocumentPage>(path, { signal });
  if (!Array.isArray(page.documents) || !Number.isInteger(page.total) || page.total < 0 ||
      page.limit !== documentPageSize || page.offset !== offset || page.documents.length > documentPageSize ||
      page.documents.length > page.total || !page.counts || typeof page.counts !== 'object' || Array.isArray(page.counts) || documentStatuses.some(status => page.counts[status] !== undefined &&
        (!Number.isInteger(page.counts[status]) || page.counts[status]! < 0))) {
    throw new ApiError('The library returned an incomplete document page. Try again.', 0, 'invalid_document_page', true);
  }
  return { path, page };
}

async function loadCataloguePage(path: string, offset: number, signal: AbortSignal): Promise<CatalogueSnapshot> {
  const page = await api<CataloguePage>(path, { signal });
  if (!Array.isArray(page.entries) || !Number.isInteger(page.total) || page.total < 0 || page.offset !== offset ||
      page.entries.length > collectionPageSize || page.entries.length > page.total ||
      (page.limit !== undefined && page.limit !== collectionPageSize) ||
      (page.counts !== undefined && (!page.counts || typeof page.counts !== 'object' || Array.isArray(page.counts) ||
        Object.keys(collectionEligibilityLabels).some(key => {
          const count = page.counts![key as CollectionEligibility];
          return count !== undefined && (!Number.isInteger(count) || count < 0);
        })))) {
    throw new ApiError('The collection returned an incomplete receipt page. Try again.', 0, 'invalid_catalogue_page', true);
  }
  return { path, page };
}

export default function LibraryPage() {
  const navigation = useNavigation();
  const temporary = navigation.scope.kind === 'temporary-case' || navigation.scope.kind === 'unclassified';
  const [mode, setMode] = useState<'browse' | 'text' | 'file' | 'catalogue'>('browse');
  const [title, setTitle] = useState('');
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [allowed, setAllowed] = useState(false);
  const [actionBusy, setBusy] = useState(false);
  const [bulkBusy, setBulkBusy] = useState(false);
  const busy = actionBusy || bulkBusy;
  const [batchPending, setBatchPending] = useState(false);
  const [error, setError] = useState<unknown>();
  const [message, setMessage] = useState('');
  const [query, setQuery] = useState('');
  const [currentOnly, setCurrentOnly] = useState(false);
  const [hits, setHits] = useState<Passage[] | null>(null);
  const [selectedDocument, setSelectedDocument] = useState<LibraryDocument | null>(null);
  const [sourceLocation, setSourceLocation] = useState<SourceLocation>({ revisionId: null, page: null, passageId: null });
  const sourceSelection = useRef(0);
  const [selectedEntries, setSelectedEntries] = useState<Set<string>>(new Set());
  const [sourceId, setSourceId] = useState('E01');
  const [offset, setOffset] = useState(0);
  const [collectionQueryInput, setCollectionQueryInput] = useState('');
  const [collectionQuery, setCollectionQuery] = useState('');
  const [collectionEligibility, setCollectionEligibility] = useState<CollectionEligibility | ''>('');
  const [catalogueSnapshot, setCatalogueSnapshot] = useState<CatalogueSnapshot>();
  const [documentQueryInput, setDocumentQueryInput] = useState('');
  const [documentQuery, setDocumentQuery] = useState('');
  const [documentStatus, setDocumentStatus] = useState<DocumentStatus | ''>('');
  const [documentOffset, setDocumentOffset] = useState(0);
  const [documentSnapshot, setDocumentSnapshot] = useState<DocumentSnapshot>();
  const [discoveryVersion, setDiscoveryVersion] = useState(0);
  const listRegion = useRef<HTMLDivElement>(null);
  const documentParams = new URLSearchParams({ limit: String(documentPageSize), offset: String(documentOffset) });
  if (documentQuery) documentParams.set('query', documentQuery);
  if (documentStatus) documentParams.set('status', documentStatus);
  const documentPath = '/library/documents?' + documentParams;
  const documentRequestPath = useRef(documentPath);
  const collectionParams = new URLSearchParams({ limit: String(collectionPageSize), offset: String(offset) });
  if (sourceId) collectionParams.set('source_id', sourceId);
  if (collectionQuery) collectionParams.set('query', collectionQuery);
  if (collectionEligibility) collectionParams.set('eligibility', collectionEligibility);
  const cataloguePath = '/library/collection/catalogue?' + collectionParams;
  const catalogueRequestPath = useRef(cataloguePath);
  const documents = useResource(signal => loadDocumentPage(documentPath, documentOffset, signal));
  const capabilities = useResource(signal => api<Capabilities>('/library/capabilities', { signal }));
  const catalogue = useResource(signal => loadCataloguePage(cataloguePath, offset, signal));
  const ready = capabilities.resource.status === 'ready' ? capabilities.resource.data : null;
  const loadedPage = documents.resource.status === 'ready' && documents.resource.data.path === documentPath
    ? documents.resource.data.page : documentSnapshot?.path === documentPath ? documentSnapshot.page : undefined;
  const documentCounts = documents.resource.status === 'ready' ? documents.resource.data.page.counts : documentSnapshot?.page.counts;
  const beyondLastPage = !!loadedPage && documentOffset > (loadedPage.total > 0 ? Math.floor((loadedPage.total - 1) / documentPageSize) * documentPageSize : 0);
  const documentPage = beyondLastPage ? undefined : loadedPage;
  const processing = !!documentCounts && ((documentCounts.queued ?? 0) + (documentCounts.processing ?? 0) > 0);
  const filteredDocuments = !!documentQuery || !!documentStatus;
  const loadedCatalogue = catalogue.resource.status === 'ready' && catalogue.resource.data.path === cataloguePath
    ? catalogue.resource.data.page : catalogueSnapshot?.path === cataloguePath ? catalogueSnapshot.page : undefined;
  const cataloguePage = loadedCatalogue && offset <= (loadedCatalogue.total > 0 ? Math.floor((loadedCatalogue.total - 1) / collectionPageSize) * collectionPageSize : 0) ? loadedCatalogue : undefined;
  const filteredCollection = !!collectionQuery || !!collectionEligibility;

  useEffect(() => {
    if (documentRequestPath.current === documentPath) return;
    documentRequestPath.current = documentPath; documents.retry();
    if (listRegion.current) listRegion.current.scrollTop = 0;
  }, [documentPath, documents.retry]);
  useEffect(() => {
    if (documents.resource.status !== 'ready' || documents.resource.data.path !== documentPath) return;
    const snapshot = documents.resource.data;
    setDocumentSnapshot(snapshot);
    const lastOffset = snapshot.page.total > 0 ? Math.floor((snapshot.page.total - 1) / documentPageSize) * documentPageSize : 0;
    if (documentOffset > lastOffset) setDocumentOffset(lastOffset);
  }, [documents.resource, documentPath, documentOffset]);
  useEffect(() => {
    if (catalogueRequestPath.current === cataloguePath) return;
    catalogueRequestPath.current = cataloguePath; setSelectedEntries(new Set()); catalogue.retry();
  }, [cataloguePath, catalogue.retry]);
  useEffect(() => {
    if (catalogue.resource.status !== 'ready' || catalogue.resource.data.path !== cataloguePath) return;
    const snapshot = catalogue.resource.data;
    setCatalogueSnapshot(snapshot);
    const lastOffset = snapshot.page.total > 0 ? Math.floor((snapshot.page.total - 1) / collectionPageSize) * collectionPageSize : 0;
    if (offset > lastOffset) setOffset(lastOffset);
  }, [catalogue.resource, cataloguePath, offset]);

  useEffect(() => { if (temporary) { setText(''); setTitle(''); setFile(null); setMode('browse'); } }, [temporary]);
  useEffect(() => { if (navigation.handoff?.mode === 'discover') setMode('browse'); }, [navigation.revision]);
  useEffect(() => {
    const documentId = navigation.handoff?.document_id;
    const revision = navigation.handoff?.document_revision ?? navigation.handoff?.revision_id;
    const passageId = navigation.handoff?.passage_id;
    if (typeof documentId !== 'string') return;
    const selection = ++sourceSelection.current;
    setMode('browse'); setSelectedDocument(null); setError(undefined);
    if (passageId != null && typeof passageId !== 'string') {
      setError(new ApiError('The cited passage identifier is invalid. Return to the source and try again.', 422, 'invalid_passage_id'));
      return;
    }
    const controller = new AbortController();
    api<LibraryDocument>('/library/documents/' + encodeURIComponent(documentId), { signal: controller.signal })
      .then(value => { if (!controller.signal.aborted && selection === sourceSelection.current) {
        setSourceLocation({ revisionId: typeof revision === 'string' ? revision : value.active_revision, page: isPhysicalPage(navigation.handoff?.page) ? navigation.handoff.page : null, passageId: passageId ?? null });
        setSelectedDocument(value);
      } }).catch(value => { if (!controller.signal.aborted && selection === sourceSelection.current) setError(value); });
    return () => controller.abort();
  }, [navigation.revision]);
  useEffect(() => {
    if (!processing || documents.resource.status === 'loading') return;
    const timer = window.setInterval(() => { documents.retry(); if (catalogue.resource.status !== 'loading') catalogue.retry(); }, 3000);
    return () => window.clearInterval(timer);
  }, [processing, documents.resource.status, catalogue.resource.status]);

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
    ++sourceSelection.current;
    const revision = passage?.document_revision ?? document.active_revision;
    setSourceLocation({ revisionId: revision, page: passage?.locators.find(locator => isPhysicalPage(locator.page))?.page ?? null, passageId: passage?.id ?? null });
    setSelectedDocument(document);
  }
  async function remove(document: LibraryDocument) {
    await act(async () => {
      const result = await api<{ cleanup_pending: boolean }>('/library/documents/' + document.id, { method: 'DELETE' });
      ++sourceSelection.current; setSelectedDocument(null); setHits(null);
      // Discovery confirms imports by document ID; a filtered page is not a membership list.
      // Removing a source invalidates its cached discovery confirmation as well.
      setDiscoveryVersion(value => value + 1);
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
    if (temporary || busy || !selectedEntries.size || selectedEntries.size > 250) return;
    await act(async () => {
      setBatchPending(true);
      try {
        const result = await api<{ queued: number; results?: { status: string; message?: string }[] }>('/library/collection/import', { method: 'POST', timeoutMs: 600_000, body: { entry_ids: [...selectedEntries], scope: libraryScope } });
        const rejected = result.results?.filter(item => item.status === 'failed' || item.status === 'excluded') ?? [];
        const reasons = [...new Set(rejected.flatMap(item => item.message ? [item.message] : []))].slice(0, 2).join(' ');
        setSelectedEntries(new Set());
        setMessage(result.queued + ' imports queued. ' + (rejected.length ? rejected.length + (rejected.length === 1 ? ' selected entry needs attention. ' : ' selected entries need attention. ') + reasons : 'Processing states appear beside each source.'));
      } finally { setBatchPending(false); }
    });
  }
  function toggleEntry(entry: CatalogueEntry) {
    if (!selectableEntry(entry, temporary) || busy) return;
    setSelectedEntries(previous => { const next = new Set(previous); if (next.has(entry.id)) next.delete(entry.id); else if (next.size < 250) next.add(entry.id); return next; });
  }
  function clearDocumentFilters() {
    setDocumentQueryInput(''); setDocumentQuery(''); setDocumentStatus(''); setDocumentOffset(0);
  }
  function clearCollectionFilters() {
    setCollectionQueryInput(''); setCollectionQuery(''); setCollectionEligibility(''); setOffset(0); setSelectedEntries(new Set());
  }

  return <>
    <PageHeader title="Your library" description="Read, search and return to the sources behind your learning." actions={<>
      <Button variant="secondary" onClick={() => setMode('catalogue')}>Collected sources</Button>
      <Button disabled={temporary} onClick={() => setMode('text')}><FileText size={18} />Add to library</Button>
    </>} />
    {temporary && <Notice tone="warning"><p>You are in a temporary context. Browse existing sources here; adding a document requires ending that context.</p></Notice>}
    {ready && !ready.text_import && <Notice tone="warning"><p>Document processing is unavailable in this build. You can inspect the collection catalogue while the bundled helpers are completed.</p></Notice>}
    {message && <Notice><p>{message}</p></Notice>}
    {batchPending && <Notice><p>Checking selected files. This may wait for the current document to finish. Acquired article text is saved only after matching version, file hash and licence checks pass.</p></Notice>}
    {error !== undefined && <ErrorState error={error} title="The library action could not finish" />}
    <div className="library-layout">
      <div className="library-main">
        {mode === 'browse' && <Discovery key={discoveryVersion} blocked={navigation.scope.kind !== 'study' && navigation.scope.kind !== 'personal-library'}
          requestedTopicId={navigation.handoff?.mode === 'discover' && typeof navigation.handoff.topic_id === 'string' ? navigation.handoff.topic_id : undefined}
          handoffRevision={navigation.revision}
          onLibraryChange={documents.retry} onInspect={document => void act(() => inspect(document))} />}
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
        {mode === 'catalogue' && <section className="section library-collection">
          <div className="library-section-title"><h2>Collected sources</h2><Button variant="ghost" onClick={() => setMode('browse')}>Back to library</Button></div>
          <div className="library-tools"><Select label="Source register" value={sourceId} disabled={busy} onChange={event => { setSourceId(event.target.value); setOffset(0); setSelectedEntries(new Set()); }}>
            <option value="">All collected sources</option><option value="E01">ERA Neph-Manual</option><option value="K01">KDIGO CKD</option><option value="K02">KDIGO anemia</option><option value="E06">Educational reviews</option><option value="L02">PMC full text</option>
          </Select><Button variant="secondary" busy={busy} onClick={catalogueSources}>Read collection catalogue</Button></div>
          <p className="muted">Acquired files appear immediately. Only completed imports enter search. The manual receipt date does not establish an edition.</p>
          <form className="library-collection-filters" onSubmit={event => { event.preventDefault(); if (busy || collectionQueryInput.trim().length > 200) return; setCollectionQuery(collectionQueryInput.trim()); setOffset(0); setSelectedEntries(new Set()); }}>
            <Input label="Find a source" placeholder="Literal title within the source register" value={collectionQueryInput} maxLength={200} disabled={busy} onChange={event => { setCollectionQueryInput(event.target.value); setSelectedEntries(new Set()); }} />
            <Select label="Receipt eligibility" value={collectionEligibility} disabled={busy} onChange={event => { setCollectionEligibility(event.target.value as CollectionEligibility | ''); setOffset(0); setSelectedEntries(new Set()); }}>
              <option value="">All receipts</option>{Object.entries(collectionEligibilityLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </Select>
            <Button type="submit" variant="secondary" disabled={busy || collectionQueryInput.trim().length > 200}>Filter sources</Button>
            {(filteredCollection || collectionQueryInput) && <Button variant="ghost" disabled={busy} onClick={clearCollectionFilters}>Clear source filters</Button>}
          </form>
          <p className="field-hint">Choose candidates or eligible receipts, then check the files to import. Changing filters clears your selection; no source is selected automatically.</p>
          {cataloguePage?.counts && <dl className="library-counts" aria-label="Collection eligibility summary">{Object.entries(collectionEligibilityLabels).map(([value, label]) => {
            const count = cataloguePage.counts![value as CollectionEligibility];
            return count !== undefined ? <div key={value}><dt>{label}</dt><dd>{count}</dd></div> : null;
          })}</dl>}
          {catalogue.resource.status === 'error' && <ErrorState title="Collected sources could not be loaded" error={catalogue.resource.error} onRetry={catalogue.retry} />}
          {sourceId === 'L02' && <BulkImportControl key={sourceId + '|' + collectionQuery} query={collectionQuery}
            disabled={actionBusy || temporary || catalogue.resource.status === 'error' || !cataloguePage}
            onBusyChange={setBulkBusy} onBatch={() => { documents.retry(); catalogue.retry(); }} />}
          {!cataloguePage ? catalogue.resource.status !== 'error' && <LoadingState label="Loading collected source records" /> : <>
            <div className="library-document-page-heading"><p role="status" aria-live="polite">{cataloguePage.total ? <>{offset + 1}–{Math.min(offset + collectionPageSize, cataloguePage.total)} of {cataloguePage.total} {filteredCollection ? 'matching receipts' : 'receipts'}</> : '0 ' + (filteredCollection ? 'matching receipts' : 'receipts')}</p>
              {catalogue.resource.status === 'loading' && <span className="muted">Refreshing…</span>}
              {catalogue.resource.status === 'error' && <span className="muted">Showing the last loaded receipts</span>}
            </div>
            {cataloguePage.entries.length === 0 ? filteredCollection ? <EmptyState title="No collected sources match these filters"><p>Try another title or eligibility, or show all receipts in this source register.</p><Button variant="secondary" onClick={clearCollectionFilters}>Show all receipts</Button></EmptyState> : <EmptyState title="This collection has no catalogue records yet"><p>Read the collection metadata to list its acquired files, then select a processing batch.</p></EmptyState> : <>
              <Button busy={busy} disabled={temporary || catalogue.resource.status === 'error' || selectedEntries.size === 0 || selectedEntries.size > 250} onClick={importSelected}>Queue selected ({selectedEntries.size})</Button>
              <div className="library-collection-list-region" role="region" aria-label="Collected source receipts" tabIndex={0}><ul className="library-list">{cataloguePage.entries.map(entry => <li key={entry.id} className="library-catalogue-row">
                <label className="library-check"><input type="checkbox" aria-label={'Select ' + entry.title} checked={selectedEntries.has(entry.id)} disabled={busy || !selectableEntry(entry, temporary) || (!selectedEntries.has(entry.id) && selectedEntries.size >= 250)} onChange={() => toggleEntry(entry)} /></label>
                <div><h3>{entry.title}</h3><div className="library-meta"><Badge tone={statusTone(entry.processing_status)}>{statusLabel(entry.processing_status)}</Badge>{requiresLicenceInspection(entry) && <Badge tone="warning">Check licence on import</Badge>}<span>{entry.metadata.collection_section ?? entry.source_id}</span><span>{(entry.bytes / 1024 / 1024).toFixed(1)} MiB</span></div>
                  {entry.eligibility !== 'eligible' && <p className="muted">{entry.reserved ? 'Reserved assessment material is excluded from learning retrieval.' : requiresLicenceInspection(entry) ? 'Renulus checks the matching article version, file hash and licence before saving eligible text. This does not establish source currentness.' : 'Processing permission or format needs verification.'}</p>}
                  {entry.error_code && <p className="field-error">Import needs attention: {entry.error_code}</p>}
                </div></li>)}</ul></div>
            </>}
            <nav className="library-pagination" aria-label="Collection receipt pages"><Button variant="secondary" disabled={busy || offset === 0} onClick={() => { setOffset(Math.max(0, offset - collectionPageSize)); setSelectedEntries(new Set()); }}>Previous sources</Button><span className="muted">Page {Math.floor(offset / collectionPageSize) + 1} of {Math.max(1, Math.ceil(cataloguePage.total / collectionPageSize))}</span><Button variant="secondary" disabled={busy || offset + collectionPageSize >= cataloguePage.total} onClick={() => { setOffset(offset + collectionPageSize); setSelectedEntries(new Set()); }}>Next sources</Button></nav>
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
          <section className="section library-documents" aria-labelledby="library-documents-title">
            <div className="library-section-title"><h2 id="library-documents-title">Documents</h2><Button variant="ghost" busy={documents.resource.status === 'loading'} onClick={documents.retry}>Refresh documents</Button></div>
            {documentCounts && <dl className="library-counts" aria-label="Library processing summary">{documentStatuses.map(status => <div key={status}><dt>{statusLabel(status)}</dt><dd>{documentCounts[status] ?? 0}</dd></div>)}</dl>}
            <form className="library-document-filters" onSubmit={event => { event.preventDefault(); setDocumentQuery(documentQueryInput.trim()); setDocumentOffset(0); }}>
              <Input label="Find a document" placeholder="Title or source ID" value={documentQueryInput} maxLength={200} onChange={event => setDocumentQueryInput(event.target.value)} />
              <Select label="Import status" value={documentStatus} onChange={event => { setDocumentStatus(event.target.value as DocumentStatus | ''); setDocumentOffset(0); }}>
                <option value="">All documents</option>{documentStatuses.map(status => <option key={status} value={status}>{statusLabel(status)}</option>)}
              </Select>
              <Button type="submit" variant="secondary" disabled={documentQueryInput.trim().length > 200}>Filter documents</Button>
              {(filteredDocuments || documentQueryInput) && <Button variant="ghost" onClick={clearDocumentFilters}>Clear filters</Button>}
            </form>
            <p className="field-hint">Status counts cover your whole library. Filters match document titles and source IDs; passage search stays separate.</p>
            {documents.resource.status === 'error' && <ErrorState title="Documents could not be loaded" error={documents.resource.error} onRetry={documents.retry} />}
            {!documentPage ? documents.resource.status !== 'error' && <LoadingState label="Loading library documents" /> : <>
              <div className="library-document-page-heading"><p role="status" aria-live="polite">{documentPage.total ? <>{documentOffset + 1}–{Math.min(documentOffset + documentPageSize, documentPage.total)} of {documentPage.total} {filteredDocuments ? 'matching documents' : 'documents'}</> : '0 ' + (filteredDocuments ? 'matching documents' : 'documents')}</p>
                {documents.resource.status === 'loading' && <span className="muted">Refreshing…</span>}
                {documents.resource.status === 'error' && <span className="muted">Showing the last loaded page</span>}
              </div>
              {documentPage.documents.length === 0 ? filteredDocuments ? <EmptyState title="No documents match these filters"><p>Try a different title or source ID, or show all import states.</p><Button variant="secondary" onClick={clearDocumentFilters}>Show all documents</Button></EmptyState> : <EmptyState title="Build a library you can return to"><p>Add a study note or an authorised document. Once processing finishes, passages keep their link to your original source.</p></EmptyState> : <div className="library-document-list-region" ref={listRegion} role="region" aria-label="Library document list" tabIndex={0}><ul className="library-list">{documentPage.documents.map(document => <li key={document.id} className="library-document">
              <button disabled={busy} className="library-document-title" onClick={() => void act(() => inspect(document))}>{document.title}</button><div className="library-meta"><Badge tone={statusTone(document.status)}>{statusLabel(document.status)}</Badge><span>{document.source_id}</span>
                {document.active_revision && document.active_revision !== document.latest_revision && <span>Earlier indexed revision is available</span>}{document.reserved && <span>Reserved</span>}{document.cleanup_pending && <span>Storage cleanup pending</span>}</div>
              {(document.status === 'queued' || document.status === 'processing') && <Button variant="ghost" onClick={() => void act(async () => { const job = await api<ImportResult>('/library/documents/' + document.id + '/import-status'); await api('/library/jobs/' + job.job.id + '/cancel', { method: 'POST' }); })}>Cancel import</Button>}
            </li>)}</ul></div>}
              <nav className="library-pagination" aria-label="Document pages"><Button variant="secondary" disabled={documentOffset === 0} onClick={() => setDocumentOffset(value => Math.max(0, value - documentPageSize))}>Previous documents</Button>
                <span className="muted">Page {Math.floor(documentOffset / documentPageSize) + 1} of {Math.max(1, Math.ceil(documentPage.total / documentPageSize))}</span>
                <Button variant="secondary" disabled={documentOffset + documentPageSize >= documentPage.total} onClick={() => setDocumentOffset(value => value + documentPageSize)}>Next documents</Button></nav>
            </>}
          </section>
        </>}
      </div>
      <aside className="library-reader" aria-label="Source reader">{selectedDocument ? <>
        <h2>{selectedDocument.title}</h2><div className="library-meta"><Badge tone={statusTone(selectedDocument.status)}>{statusLabel(selectedDocument.status)}</Badge><span>{selectedDocument.source_id}</span></div>
        <SourceInspector key={selectedDocument.id + ':' + sourceLocation.revisionId + ':' + sourceLocation.page + ':' + sourceLocation.passageId} document={selectedDocument} location={sourceLocation} />
        <Button variant="danger" busy={busy} onClick={() => void remove(selectedDocument)}>Remove from library</Button>
      </> : <><FileText size={26} aria-hidden="true" /><h2>Keep the source in view</h2><p>Select a document or a passage to inspect its edition, permissions and original location.</p></>}</aside>
    </div>
  </>;
}
