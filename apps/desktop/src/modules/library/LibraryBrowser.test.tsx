// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import LibraryPage from './index';
import type { CatalogueEntry, LibraryDocument } from './types';

const { navigation } = vi.hoisted(() => ({ navigation: { scope: { kind: 'study', entity_id: 'SYNTHETIC_PRIVATE_SENTINEL' }, handoff: {} as Record<string, unknown>, revision: 0 } }));
vi.mock('../../shell/navigation', () => ({ useNavigation: () => navigation }));

const request = vi.fn<typeof fetch>();
const states = ['ready', 'queued', 'processing', 'failed', 'cancelled'] as const;
let records: LibraryDocument[];
let catalogueEntries: CatalogueEntry[];
let catalogueCounts: boolean;
function documentFor(number: number): LibraryDocument {
  const id = 'doc_' + String(number).padStart(3, '0');
  const status = number <= 100 ? 'ready' : number <= 140 ? 'queued' : number <= 150 ? 'processing' : number <= 155 ? 'failed' : 'cancelled';
  const revision = 'rev_' + String(number).padStart(3, '0');
  return { id, title: 'Synthetic source ' + String(number).padStart(3, '0'), source_id: number % 3 === 0 ? 'SYNTHETIC-CKD' : 'SYNTHETIC-TRANSPLANT', status, reserved: false, cleanup_pending: false,
    active_revision: status === 'ready' ? revision : null, latest_revision: revision, revisions: [{ id: revision, document_id: id, ordinal: 1, status, sha256: 'synthetic', media_type: 'text/plain', bytes: 100, passage_count: status === 'ready' ? 2 : 0,
      metadata: { source_id: 'SYNTHETIC', source_owner: 'Synthetic Author', canonical_url: null, edition: 'Synthetic edition', publication_date: '2026-01-01', received_at: null, checked_at: null, publication_status: 'unverified', latest_final_verified: false, content_reviewed: false, collection_section: null, collection_chapter: null, notes: [] },
      rights: { display: true, cache: true, index: true, embedding: true, model_input: true, derivation: false, evaluation: false, redistribution: false, licence: 'CC-BY-4.0', permission_reference: 'Synthetic test permission', attribution: 'Synthetic Author' } }] };
}
function json(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } }); }
function pageFor(url: string) {
  const params = new URL(url, 'http://127.0.0.1').searchParams;
  const limit = Number(params.get('limit')), offset = Number(params.get('offset'));
  const query = (params.get('query') ?? '').toLowerCase(), status = params.get('status');
  const matching = records.filter(document => (!status || document.status === status) && (!query || (document.title + ' ' + document.source_id).toLowerCase().includes(query)));
  const counts = Object.fromEntries(states.map(state => [state, records.filter(document => document.status === state).length]));
  return { documents: matching.slice(offset, offset + limit), total: matching.length, counts, offset, limit };
}
function receiptFor(number: number, eligibility = 'inspection_required', overrides: Partial<CatalogueEntry> = {}): CatalogueEntry {
  return { id: 'receipt_' + number, title: 'Synthetic receipt ' + String(number).padStart(3, '0'), source_id: 'L02', eligibility,
    reserved: eligibility === 'reserved', bytes: 1200, metadata: { ...documentFor(1).revisions[0].metadata, source_id: 'L02', asset_role: ['acquired-jats'] },
    rights: documentFor(1).revisions[0].rights, document_id: null, job_id: null, processing_status: 'acquired', error_code: null, ...overrides } as CatalogueEntry;
}
const receiptBucket = (entry: CatalogueEntry) => entry.reserved || entry.eligibility === 'reserved' ? 'reserved' : entry.eligibility === 'eligible' || entry.eligibility === 'inspection_required' ? entry.eligibility : 'unavailable';
function receiptPageFor(url: string) {
  const params = new URL(url, 'http://127.0.0.1').searchParams;
  const sourceId = params.get('source_id'), query = (params.get('query') ?? '').toLowerCase(), eligibility = params.get('eligibility');
  const limit = Number(params.get('limit')), offset = Number(params.get('offset'));
  const sourceEntries = catalogueEntries.filter(entry => !sourceId || entry.source_id === sourceId);
  const matching = sourceEntries.filter(entry => (!query || entry.title.toLowerCase().includes(query)) && (!eligibility || receiptBucket(entry) === eligibility));
  const counts = Object.fromEntries(['eligible', 'inspection_required', 'reserved', 'unavailable'].map(bucket => [bucket, sourceEntries.filter(entry => receiptBucket(entry) === bucket).length]));
  return { entries: matching.slice(offset, offset + limit), total: matching.length, offset, limit, ...(catalogueCounts ? { counts } : {}) };
}
const base = async (url: RequestInfo | URL, options?: RequestInit): Promise<Response> => {
  const path = String(url);
  if (path.startsWith('/api/v1/library/documents?')) return json(pageFor(path));
  if (path === '/api/v1/library/queue') return json({ running: true, cpu_workers: 1, active_job: null, error_code: null, queued: records.filter(value => value.status === 'queued').length });
  if (path.endsWith('/import-status')) {
    const document = records.find(row => row.id === path.split('/').at(-2))!;
    return json({ document_id: document.id, revision_id: document.latest_revision, status: document.status, job: { id: 'job_' + document.id, revision_id: document.latest_revision, state: document.status, phase: document.status, error_code: document.status === 'failed' ? 'extraction_failed' : null, error_message: document.status === 'failed' ? 'Synthetic extraction failed. Choose the original again.' : null } });
  }
  if (path.startsWith('/api/v1/library/documents/')) {
    const id = path.split('/').at(-1);
    const document = records.find(row => row.id === id);
    if (options?.method === 'DELETE') { records = records.filter(row => row.id !== id); return json({ cleanup_pending: false }); }
    return document ? json(document) : json({ error: { code: 'document_not_found', message: 'Synthetic document removed.', retryable: false } }, 404);
  }
  if (path.includes('/library/revisions/') && path.includes('/citation')) {
    const revision = path.split('/')[5];
    const document = records.find(row => row.latest_revision === revision)!;
    const page = new URL(path, 'http://127.0.0.1').searchParams.get('page');
    return json({ document_id: document.id, document_revision: revision, title: document.title, page: page ? Number(page) : null, locators: [{ page: Number(page ?? 1), char_span: [0, 100], item_ref: '#/texts/0' }], original_url: '/library/revisions/' + revision + '/original' });
  }
  if (path === '/api/v1/library/capabilities') return json({ text_import: true, pdf_image_import: false, temporary_extraction: false });
  if (path.startsWith('/api/v1/library/collection/catalogue?')) return json(receiptPageFor(path));
  if (path === '/api/v1/content/topics') return json([{ id: 'T21', label: 'Kidney transplantation' }, { id: 'T19', label: 'Medicines and nephrotoxicity' }]);
  if (path === '/api/v1/retrieval/connections') return json({ selected_tool: null, connections: ['europe-pmc', 'pubmed'].map(provider => ({ provider, enabled: true, configured: false, selected: false, requests_used: 0, daily_request_limit: 100, credits_used: 0, daily_credit_limit: 20, auth_status: 'not_checked' })) });
  if (path === '/api/v1/retrieval/discover') return json({ topic_id: 'T21', topic_label: 'Kidney transplantation', provider: 'europe-pmc', queried_at: '2026-01-01T12:00:00Z', records: [{ id: 'MED:10001', title: 'Synthetic discovered source', url: 'https://pubmed.ncbi.nlm.nih.gov/10001/', pmcid: 'PMC10001', publication_date: '2026-01-01' }] });
  if (path === '/api/v1/retrieval/articles/import') return json({ topic_id: 'T21', article: { pmcid: 'PMC10001', licence: 'CC-BY-4.0', licence_url: 'https://creativecommons.org/licenses/by/4.0/', attribution: 'Synthetic Author' }, import: { document_id: 'doc_050', revision_id: 'rev_050', status: 'ready', job: { id: 'job_synthetic', revision_id: 'rev_050', state: 'ready', phase: 'ready', error_code: null, error_message: null } }, replayed: false });
  if (path === '/api/v1/library/jobs/job_synthetic') return json({ id: 'job_synthetic', revision_id: 'rev_050', state: 'ready', phase: 'ready', error_code: null, error_message: null });
  throw new Error('Unexpected synthetic request: ' + path);
};
beforeEach(() => {
  records = Array.from({ length: 156 }, (_, index) => documentFor(index + 1));
  catalogueEntries = [];
  catalogueCounts = false;
  navigation.scope.kind = 'study'; navigation.handoff = {}; navigation.revision = 0;
  request.mockReset().mockImplementation(base);
  vi.stubGlobal('fetch', request);
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });
const listCalls = () => request.mock.calls.filter(([url]) => String(url).startsWith('/api/v1/library/documents?'));
const list = () => screen.getByRole('region', { name: 'Library document list' });
const summary = () => screen.getByLabelText('Library processing summary');
function count(label: string) { return within(summary()).getByText(label, { selector: 'dt' }).nextElementSibling?.textContent; }
async function mount() { const view = render(<LibraryPage />); await screen.findByText('1–25 of 156 documents'); return view; }
async function next(range: string) { fireEvent.click(screen.getByRole('button', { name: 'Next documents' })); await screen.findByText(range); }
const collectionCalls = () => request.mock.calls.filter(([url]) => String(url).startsWith('/api/v1/library/collection/catalogue?'));
const receipts = () => screen.getByRole('region', { name: 'Collected source receipts' });
async function mountCollection() {
  const view = await mount(); fireEvent.click(screen.getByRole('button', { name: 'Collected sources' }));
  fireEvent.change(screen.getByLabelText('Source register'), { target: { value: 'L02' } });
  await screen.findByRole('region', { name: 'Collected source receipts' }); return view;
}

describe('Library document browser', () => {
  it.each(['DOCX', 'PPTX', 'XLSX'])('imports a deliberate %s file when Office processing is available without PDF/OCR capability', async extension => {
    let postedOptions: Record<string, unknown> | null = null;
    let postedBody: unknown;
    request.mockImplementation(async (url, options) => {
      if (String(url) === '/api/v1/library/capabilities') return json({ text_import: true, pdf_image_import: false, office_import: true, temporary_extraction: false });
      if (String(url) === '/api/v1/library/import/file') {
        postedOptions = JSON.parse(new Headers(options?.headers).get('x-renulus-import-options')!);
        postedBody = options?.body;
        return json({ document_id: 'doc_synthetic_office', revision_id: 'rev_synthetic_office', status: 'queued', job: { id: 'job_synthetic', revision_id: 'rev_synthetic_office', state: 'queued', phase: 'queued', error_code: null, error_message: null } }, 202);
      }
      return base(url, options);
    });
    await mount();
    fireEvent.click(screen.getByRole('button', { name: 'Add to library' }));
    fireEvent.click(screen.getByRole('button', { name: 'Document' }));
    const file = new File(['Synthetic Office bytes'], 'study.' + extension);
    fireEvent.change(screen.getByLabelText('Choose a study document'), { target: { files: [file] } });
    const add = screen.getByRole('button', { name: 'Add document' }) as HTMLButtonElement;
    expect(add.disabled).toBe(true);
    fireEvent.click(screen.getByRole('checkbox', { name: 'I have permission to read, store, index and use this file for local learning.' }));
    await waitFor(() => expect(add.disabled).toBe(false));
    fireEvent.click(add);
    await screen.findByText('Queued: follow processing below.');
    expect(postedBody).toBe(file);
    expect(postedOptions).toMatchObject({ scope: { kind: 'personal-library' }, title: file.name });
  });

  it('bounds a 156-document library to 25 visible rows and displays global status counts', async () => {
    await mount();
    expect(within(list()).getAllByRole('listitem')).toHaveLength(25);
    expect(count('Available')).toBe('100'); expect(count('Queued')).toBe('40'); expect(count('Processing')).toBe('10'); expect(count('Import failed')).toBe('5'); expect(count('Cancelled')).toBe('1');
    expect(screen.getByText('Page 1 of 7')).toBeTruthy();
    expect((screen.getByRole('button', { name: 'Previous documents' }) as HTMLButtonElement).disabled).toBe(true);
    expect(list().tabIndex).toBe(0);
    expect(listCalls()).toHaveLength(1);
    expect(listCalls()[0][0]).toBe('/api/v1/library/documents?limit=25&offset=0');
    expect(request.mock.calls.some(([url]) => url === '/api/v1/library/documents' || url === '/api/v1/runtime/runs')).toBe(false);
  });

  it('pages to the six-document final page without rendering earlier rows, then moves back', async () => {
    await mount();
    for (const range of ['26–50', '51–75', '76–100', '101–125', '126–150', '151–156']) await next(range + ' of 156 documents');
    expect(within(list()).getAllByRole('listitem')).toHaveLength(6);
    expect(within(list()).queryByText('Synthetic source 001')).toBeNull();
    expect(screen.getByText('Page 7 of 7')).toBeTruthy();
    expect((screen.getByRole('button', { name: 'Next documents' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Previous documents' }));
    await screen.findByText('126–150 of 156 documents');
    expect(within(list()).getAllByRole('listitem')).toHaveLength(25);
    expect(listCalls().map(([url]) => new URL(String(url), 'http://127.0.0.1').searchParams.get('offset'))).toEqual(['0', '25', '50', '75', '100', '125', '150', '125']);
  });

  it('applies title/source filters locally, resets page offset and keeps whole-library counts', async () => {
    await mount(); await next('26–50 of 156 documents');
    fireEvent.change(screen.getByLabelText('Find a document'), { target: { value: 'SYNTHETIC-CKD' } });
    expect(listCalls()).toHaveLength(2);
    fireEvent.click(screen.getByRole('button', { name: 'Filter documents' }));
    await screen.findByText('1–25 of 52 matching documents');
    fireEvent.change(screen.getByLabelText('Import status'), { target: { value: 'queued' } });
    await screen.findByText('1–13 of 13 matching documents');
    expect(within(list()).getAllByRole('listitem')).toHaveLength(13);
    expect(count('Available')).toBe('100'); expect(count('Queued')).toBe('40');
    expect(String(listCalls().at(-1)![0])).toBe('/api/v1/library/documents?limit=25&offset=0&query=SYNTHETIC-CKD&status=queued');
    expect(JSON.stringify(request.mock.calls)).not.toContain('SYNTHETIC_PRIVATE_SENTINEL');
    expect(request.mock.calls.some(([url]) => url === '/api/v1/library/retrieve' || url === '/api/v1/retrieval/discover')).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }));
    await screen.findByText('1–25 of 156 documents');
    expect((screen.getByLabelText('Find a document') as HTMLInputElement).value).toBe('');
    expect((screen.getByLabelText('Import status') as HTMLSelectElement).value).toBe('');
  });

  it('encodes a literal title with percent/underscore/ampersand rather than a second query argument', async () => {
    records[0].title = 'Synthetic 100%_ & status=failed';
    await mount();
    fireEvent.change(screen.getByLabelText('Find a document'), { target: { value: '100%_ & status=failed' } });
    fireEvent.click(screen.getByRole('button', { name: 'Filter documents' }));
    await screen.findByText('1–1 of 1 matching documents');
    const params = new URL(String(listCalls().at(-1)![0]), 'http://127.0.0.1').searchParams;
    expect(params.get('query')).toBe('100%_ & status=failed'); expect(params.has('status')).toBe(false);
    expect(within(list()).getAllByRole('listitem')).toHaveLength(1);
  });

  it('distinguishes a filter with no matches from an empty library and can clear it', async () => {
    await mount();
    fireEvent.change(screen.getByLabelText('Find a document'), { target: { value: 'No synthetic source matches' } });
    fireEvent.click(screen.getByRole('button', { name: 'Filter documents' }));
    await screen.findByText('No documents match these filters');
    expect(screen.getByText('0 matching documents')).toBeTruthy();
    expect(screen.queryByText('Build a library you can return to')).toBeNull();
    expect(count('Available')).toBe('100');
    fireEvent.click(screen.getByRole('button', { name: 'Show all documents' }));
    await screen.findByText('1–25 of 156 documents');
  });

  it('shows honest zero counts and disabled pagination for an actually empty library', async () => {
    records = []; render(<LibraryPage />);
    await screen.findByText('Build a library you can return to');
    expect(screen.getByText('0 documents')).toBeTruthy();
    for (const label of ['Available', 'Queued', 'Processing', 'Import failed', 'Cancelled']) expect(count(label)).toBe('0');
    expect(screen.queryByRole('region', { name: 'Library document list' })).toBeNull();
    expect((screen.getByRole('button', { name: 'Next documents' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('keeps the failed filter/error visible and retries the same request without claiming an empty library', async () => {
    let fail = true;
    request.mockImplementation(async (url, options) => String(url).includes('&status=failed') && fail ? json({ error: { code: 'index_unavailable', message: 'Synthetic document page unavailable.', retryable: true } }, 503) : base(url, options));
    await mount(); fireEvent.change(screen.getByLabelText('Import status'), { target: { value: 'failed' } });
    await screen.findByText('Synthetic document page unavailable.');
    expect(screen.queryByText('No documents match these filters')).toBeNull();
    expect(screen.queryByText('Build a library you can return to')).toBeNull();
    expect((screen.getByLabelText('Import status') as HTMLSelectElement).value).toBe('failed');
    expect(count('Queued')).toBe('40');
    fail = false; fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await screen.findByText('1–5 of 5 matching documents');
    expect(listCalls().slice(-2).map(([url]) => url)).toEqual(['/api/v1/library/documents?limit=25&offset=0&status=failed', '/api/v1/library/documents?limit=25&offset=0&status=failed']);
  });

  it('retains a loaded page during refresh failure and labels its status as last loaded', async () => {
    await mount();
    request.mockImplementation(async (url, options) => String(url).startsWith('/api/v1/library/documents?') ? json({ error: { code: 'unavailable', message: 'Synthetic refresh unavailable.', retryable: true } }, 503) : base(url, options));
    fireEvent.click(screen.getByRole('button', { name: 'Refresh documents' }));
    await screen.findByText('Synthetic refresh unavailable.');
    expect(screen.getByText('Showing the last loaded page')).toBeTruthy();
    expect(within(list()).getAllByRole('listitem')).toHaveLength(25);
  });

  it('rejects incomplete page metadata instead of displaying invented totals', async () => {
    request.mockImplementation(async (url, options) => String(url).startsWith('/api/v1/library/documents?') ? json({ documents: [] }) : base(url, options));
    render(<LibraryPage />);
    await screen.findByText('The library returned an incomplete document page. Try again.');
    expect(screen.queryByText('0 documents')).toBeNull(); expect(screen.queryByText('Build a library you can return to')).toBeNull();
  });

  it('discards a delayed old-filter JSON body after a newer filter has loaded', async () => {
    let release!: (value: unknown) => void;
    request.mockImplementation(async (url, options) => {
      if (String(url).includes('&status=queued')) {
        const response = json({}); response.json = () => new Promise(resolve => { release = resolve; }); return response;
      }
      return base(url, options);
    });
    await mount(); fireEvent.change(screen.getByLabelText('Import status'), { target: { value: 'queued' } });
    await waitFor(() => expect(release).toBeTypeOf('function'));
    fireEvent.change(screen.getByLabelText('Import status'), { target: { value: 'failed' } });
    await screen.findByText('1–5 of 5 matching documents');
    await act(async () => release(pageFor('/api/v1/library/documents?limit=25&offset=0&status=queued')));
    expect(screen.getByText('1–5 of 5 matching documents')).toBeTruthy();
    expect(within(list()).queryByText('Synthetic source 101')).toBeNull();
    expect((screen.getByLabelText('Import status') as HTMLSelectElement).value).toBe('failed');
  });

  it('polls global queued/processing counts when the current failed page contains no pending jobs', async () => {
    vi.useFakeTimers();
    await act(async () => { render(<LibraryPage />); });
    await act(async () => { fireEvent.change(screen.getByLabelText('Import status'), { target: { value: 'failed' } }); });
    expect(screen.getByText('1–5 of 5 matching documents')).toBeTruthy();
    const priorCalls = listCalls().length;
    records[100].status = 'ready';
    await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
    expect(listCalls().length).toBe(priorCalls + 1);
    expect(count('Queued')).toBe('39'); expect(count('Available')).toBe('101');
    expect(within(list()).getAllByRole('listitem')).toHaveLength(5);
    expect(screen.getByText('1–5 of 5 matching documents')).toBeTruthy();
  });

  it('recovers to the last valid page when a library shrinks beyond the current offset', async () => {
    await mount();
    for (const range of ['26–50', '51–75', '76–100', '101–125', '126–150', '151–156']) await next(range + ' of 156 documents');
    records = records.slice(0, 125);
    fireEvent.click(screen.getByRole('button', { name: 'Refresh documents' }));
    await screen.findByText('101–125 of 125 documents');
    expect(screen.getByText('Page 5 of 5')).toBeTruthy();
    expect(within(list()).getAllByRole('listitem')).toHaveLength(25);
    expect(screen.queryByText('No documents match these filters')).toBeNull();
    expect(String(listCalls().at(-1)![0])).toBe('/api/v1/library/documents?limit=25&offset=100');
  });

  it('does not let background polling repeatedly abort a slow document page', async () => {
    vi.useFakeTimers();
    let release!: (value: Response) => void;
    request.mockImplementation(async (url, options) => String(url).endsWith('offset=25')
      ? await new Promise<Response>(resolve => { release = resolve; }) : base(url, options));
    await act(async () => { render(<LibraryPage />); });
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Next documents' })); });
    expect(release).toBeTypeOf('function');
    const pending = listCalls().at(-1)!;
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
    expect(listCalls()).toHaveLength(2); expect(pending[1]!.signal!.aborted).toBe(false);
    await act(async () => { release(json(pageFor(String(pending[0])))); });
    expect(screen.getByText('26–50 of 156 documents')).toBeTruthy();
    expect(within(list()).getAllByRole('listitem')).toHaveLength(25);
  });

  it('keeps page navigation usable while a background refresh is pending', async () => {
    vi.useFakeTimers();
    let release!: (value: Response) => void, firstRequests = 0;
    request.mockImplementation(async (url, options) => String(url).endsWith('offset=0') && ++firstRequests === 2
      ? await new Promise<Response>(resolve => { release = resolve; }) : base(url, options));
    await act(async () => { render(<LibraryPage />); });
    await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
    expect(release).toBeTypeOf('function');
    expect(screen.getByText('Refreshing…')).toBeTruthy();
    const refresh = listCalls().at(-1)!;
    expect((screen.getByRole('button', { name: 'Next documents' }) as HTMLButtonElement).disabled).toBe(false);
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Next documents' })); });
    expect(screen.getByText('26–50 of 156 documents')).toBeTruthy();
    expect(refresh[1]!.signal!.aborted).toBe(true);
    await act(async () => { release(json(pageFor(String(refresh[0])))); });
    expect(screen.getByText('26–50 of 156 documents')).toBeTruthy();
  });

  it('opens a handed-off source by ID despite a filter/page or collected-sources view', async () => {
    const view = await mount();
    fireEvent.change(screen.getByLabelText('Import status'), { target: { value: 'failed' } });
    await screen.findByText('1–5 of 5 matching documents');
    fireEvent.click(screen.getByRole('button', { name: 'Collected sources' }));
    await screen.findByText('This collection has no catalogue records yet');
    navigation.handoff = { document_id: 'doc_002', document_revision: 'rev_002', page: 4, question: 'SYNTHETIC_PRIVATE_SENTINEL' }; navigation.revision++;
    view.rerender(<LibraryPage />);
    const reader = screen.getByRole('complementary', { name: 'Source reader' });
    await within(reader).findByRole('heading', { name: 'Synthetic source 002' });
    await within(reader).findByRole('button', { name: 'Open original · page 4' });
    expect(screen.getByText('1–5 of 5 matching documents')).toBeTruthy();
    expect(within(list()).queryByText('Synthetic source 002')).toBeNull();
    expect(request.mock.calls.some(([url]) => url === '/api/v1/library/documents/doc_002')).toBe(true);
    expect(request.mock.calls.some(([url]) => url === '/api/v1/library/revisions/rev_002/citation?page=4')).toBe(true);
    expect(JSON.stringify(request.mock.calls)).not.toContain('SYNTHETIC_PRIVATE_SENTINEL');
  });

  it('preserves canonical Discovery handoffs and does not automatically search when paging', async () => {
    navigation.handoff = { mode: 'discover', topic_id: 'T21' }; navigation.revision++;
    await mount();
    await waitFor(() => expect((screen.getByLabelText('Literature topic') as HTMLSelectElement).value).toBe('T21'));
    await next('26–50 of 156 documents');
    expect((screen.getByLabelText('Literature topic') as HTMLSelectElement).value).toBe('T21');
    expect(request.mock.calls.some(([url]) => url === '/api/v1/retrieval/discover')).toBe(false);
  });

  it('keeps a confirmed Discovery import Indexed on another page/filter and invalidates it on deletion', async () => {
    await mount(); await screen.findByLabelText('Literature topic');
    fireEvent.change(screen.getByLabelText('Literature topic'), { target: { value: 'T21' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search literature' }));
    const article = await screen.findByRole('article', { name: 'Synthetic discovered source' });
    fireEvent.click(within(article).getByRole('button', { name: 'Add eligible text' }));
    await within(article).findByText('Indexed');
    expect(within(list()).queryByText('Synthetic source 050')).toBeNull();
    await next('26–50 of 156 documents'); await next('51–75 of 156 documents');
    expect(within(article).getByText('Indexed')).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Import status'), { target: { value: 'failed' } });
    await screen.findByText('1–5 of 5 matching documents');
    expect(within(article).getByText('Indexed')).toBeTruthy();
    fireEvent.click(within(article).getByRole('button', { name: 'Inspect library source' }));
    const reader = screen.getByRole('complementary', { name: 'Source reader' });
    await within(reader).findByRole('heading', { name: 'Synthetic source 050' });
    await waitFor(() => expect((within(reader).getByRole('button', { name: 'Remove from library' }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(within(reader).getByRole('button', { name: 'Remove from library' }));
    await screen.findByText('Removed from your library. Your external original is preserved.');
    expect(screen.queryByRole('article', { name: 'Synthetic discovered source' })).toBeNull();
    expect(records.some(document => document.id === 'doc_050')).toBe(false);
  });

  it('selects only marked acquired JATS for licence inspection, keeps denied entries blocked and waits honestly for the selected batch', async () => {
    vi.useFakeTimers();
    const metadata = { ...documentFor(1).revisions[0].metadata, source_id: 'L02', asset_role: ['fulltext-jats', 'acquired-jats'] };
    const entry = (id: string, overrides: Partial<CatalogueEntry> = {}): CatalogueEntry => ({ id, title: id, source_id: 'L02', eligibility: 'inspection_required', reserved: false, bytes: 1200, metadata, rights: documentFor(1).revisions[0].rights, document_id: null, job_id: null, processing_status: 'acquired', error_code: null, ...overrides });
    catalogueEntries = [entry('Synthetic JATS inspection'), entry('Synthetic unavailable payload', { eligibility: 'permission_or_format_unavailable' }),
      entry('Synthetic unmarked inspection', { metadata: { ...metadata, asset_role: [] } as typeof metadata }),
      entry('Synthetic reserved JATS', { reserved: true }), entry('Synthetic ready JATS', { processing_status: 'ready' }), entry('Synthetic permitted source', { eligibility: 'eligible' })];
    let release!: (value: Response) => void;
    request.mockImplementation(async (url, options) => url === '/api/v1/library/collection/import'
      ? await new Promise<Response>(resolve => { release = resolve; }) : base(url, options));
    let view!: ReturnType<typeof render>;
    await act(async () => { view = render(<LibraryPage />); });
    fireEvent.click(screen.getByRole('button', { name: 'Collected sources' }));
    await act(async () => { fireEvent.change(screen.getByLabelText('Source register'), { target: { value: 'L02' } }); });
    const inspect = screen.getByRole('checkbox', { name: 'Select Synthetic JATS inspection' }) as HTMLInputElement;
    expect(inspect.disabled).toBe(false);
    expect((screen.getByRole('checkbox', { name: 'Select Synthetic permitted source' }) as HTMLInputElement).disabled).toBe(false);
    for (const title of ['Synthetic unavailable payload', 'Synthetic unmarked inspection', 'Synthetic reserved JATS', 'Synthetic ready JATS']) {
      const denied = screen.getByRole('checkbox', { name: 'Select ' + title }) as HTMLInputElement;
      expect(denied.disabled).toBe(true); fireEvent.click(denied); expect(denied.checked).toBe(false);
    }
    expect(screen.getAllByText('Check licence on import').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/does not establish source currentness/).length).toBeGreaterThan(0);
    fireEvent.click(inspect);
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Queue selected (1)' })); });
    expect(screen.getByText(/Checking selected files/)).toBeTruthy();
    const batch = request.mock.calls.find(([url]) => url === '/api/v1/library/collection/import')!;
    expect(JSON.parse(batch[1]!.body as string)).toEqual({ entry_ids: ['Synthetic JATS inspection'], scope: { kind: 'personal-library' } });
    await act(async () => { await vi.advanceTimersByTimeAsync(31_000); });
    expect(batch[1]!.signal!.aborted).toBe(false);
    expect(screen.getByText(/Checking selected files/)).toBeTruthy();
    await act(async () => { release(json({ queued: 0, results: [{ entry_id: 'Synthetic JATS inspection', status: 'failed', message: 'Synthetic matching licence is restricted.' }] })); });
    expect(screen.queryByText(/Checking selected files/)).toBeNull();
    expect(screen.getByText(/0 imports queued. 1 selected entry needs attention. Synthetic matching licence is restricted./)).toBeTruthy();
    navigation.scope.kind = 'temporary-case'; navigation.revision++;
    await act(async () => { view.rerender(<LibraryPage />); });
    fireEvent.click(screen.getByRole('button', { name: 'Collected sources' }));
    expect((screen.getByRole('checkbox', { name: 'Select Synthetic JATS inspection' }) as HTMLInputElement).disabled).toBe(true);
  });
});

describe('Collection receipt filters', () => {
  it('bounds a reported 178k-receipt catalogue and shows supplied counts without selecting or importing anything', async () => {
    const counts = { eligible: 1000, inspection_required: 172000, reserved: 1000, unavailable: 4000 };
    request.mockImplementation(async (url, options) => String(url).startsWith('/api/v1/library/collection/catalogue?') && String(url).includes('source_id=L02')
      ? json({ entries: Array.from({ length: 50 }, (_, index) => receiptFor(index + 1)), total: 178000, offset: 0, limit: 50, counts }) : base(url, options));
    await mountCollection();
    expect(within(receipts()).getAllByRole('listitem')).toHaveLength(50);
    expect(screen.getByText('1–50 of 178000 receipts')).toBeTruthy();
    expect(screen.getByText('Page 1 of 3560')).toBeTruthy();
    const summary = screen.getByLabelText('Collection eligibility summary');
    expect(within(summary).getByText('Candidates needing inspection', { selector: 'dt' }).nextElementSibling?.textContent).toBe('172000');
    expect((screen.getByRole('button', { name: 'Queue selected (0)' }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByLabelText('Find a source') as HTMLInputElement).maxLength).toBe(200);
    expect(receipts().tabIndex).toBe(0);
    expect(request.mock.calls.some(([url]) => url === '/api/v1/library/collection/import')).toBe(false);
  });

  it('filters candidates and eligible receipts while preserving explicit selection and clearing it on each change', async () => {
    catalogueCounts = true;
    catalogueEntries = [receiptFor(1), receiptFor(2, 'eligible'), receiptFor(3, 'reserved'), receiptFor(4, 'article_permission_required')];
    await mountCollection();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Select Synthetic receipt 001' }));
    expect((screen.getByRole('button', { name: 'Queue selected (1)' }) as HTMLButtonElement).disabled).toBe(false);
    fireEvent.change(screen.getByLabelText('Receipt eligibility'), { target: { value: 'inspection_required' } });
    await screen.findByText('1–1 of 1 matching receipts');
    expect(within(receipts()).getAllByRole('listitem')).toHaveLength(1);
    expect((screen.getByRole('checkbox', { name: 'Select Synthetic receipt 001' }) as HTMLInputElement).checked).toBe(false);
    expect(screen.getByRole('button', { name: 'Queue selected (0)' })).toBeTruthy();
    const summary = screen.getByLabelText('Collection eligibility summary');
    expect(within(summary).getByText('Eligible', { selector: 'dt' }).nextElementSibling?.textContent).toBe('1');
    fireEvent.click(screen.getByRole('checkbox', { name: 'Select Synthetic receipt 001' }));
    fireEvent.change(screen.getByLabelText('Receipt eligibility'), { target: { value: 'eligible' } });
    await screen.findByRole('checkbox', { name: 'Select Synthetic receipt 002' });
    expect(screen.queryByRole('checkbox', { name: 'Select Synthetic receipt 001' })).toBeNull();
    expect((screen.getByRole('checkbox', { name: 'Select Synthetic receipt 002' }) as HTMLInputElement).checked).toBe(false);
    expect(String(collectionCalls().at(-1)![0])).toBe('/api/v1/library/collection/catalogue?limit=50&offset=0&source_id=L02&eligibility=eligible');
    fireEvent.click(screen.getByRole('checkbox', { name: 'Select Synthetic receipt 002' }));
    fireEvent.click(screen.getByRole('button', { name: 'Clear source filters' }));
    await screen.findByText('1–4 of 4 receipts');
    expect(screen.getByRole('button', { name: 'Queue selected (0)' })).toBeTruthy();
    expect(new URL(String(collectionCalls().at(-1)![0]), 'http://127.0.0.1').searchParams.has('eligibility')).toBe(false);
    expect(request.mock.calls.some(([url]) => url === '/api/v1/library/collection/import')).toBe(false);
  });

  it('encodes a literal title, resets paging, and does not send a draft or overlong query', async () => {
    catalogueEntries = Array.from({ length: 55 }, (_, index) => receiptFor(index + 1));
    catalogueEntries[0].title = 'Synthetic 100%_ & eligibility=reserved';
    await mountCollection();
    fireEvent.click(screen.getByRole('button', { name: 'Next sources' }));
    await screen.findByText('51–55 of 55 receipts');
    fireEvent.click(screen.getByRole('checkbox', { name: 'Select Synthetic receipt 051' }));
    const prior = collectionCalls().length;
    fireEvent.change(screen.getByLabelText('Find a source'), { target: { value: '100%_ & eligibility=reserved' } });
    expect(collectionCalls()).toHaveLength(prior);
    expect(screen.getByRole('button', { name: 'Queue selected (0)' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Filter sources' }));
    await screen.findByText('1–1 of 1 matching receipts');
    const params = new URL(String(collectionCalls().at(-1)![0]), 'http://127.0.0.1').searchParams;
    expect(params.get('offset')).toBe('0'); expect(params.get('query')).toBe('100%_ & eligibility=reserved'); expect(params.has('eligibility')).toBe(false);
    const filteredCalls = collectionCalls().length;
    fireEvent.change(screen.getByLabelText('Find a source'), { target: { value: 'x'.repeat(201) } });
    const filter = screen.getByRole('button', { name: 'Filter sources' }) as HTMLButtonElement;
    expect(filter.disabled).toBe(true); fireEvent.submit(filter.closest('form')!);
    expect(collectionCalls()).toHaveLength(filteredCalls);
    expect(JSON.stringify(request.mock.calls)).not.toContain('SYNTHETIC_PRIVATE_SENTINEL');
  });

  it('keeps reserved and unavailable rows visible but blocked; omits counts when the API supplies none', async () => {
    catalogueEntries = [receiptFor(1, 'reserved'), receiptFor(2, 'article_permission_required')];
    await mountCollection();
    expect(screen.queryByLabelText('Collection eligibility summary')).toBeNull();
    fireEvent.change(screen.getByLabelText('Receipt eligibility'), { target: { value: 'reserved' } });
    await screen.findByText('1–1 of 1 matching receipts');
    const reserved = screen.getByRole('checkbox', { name: 'Select Synthetic receipt 001' }) as HTMLInputElement;
    expect(reserved.disabled).toBe(true); fireEvent.click(reserved); expect(reserved.checked).toBe(false);
    fireEvent.change(screen.getByLabelText('Receipt eligibility'), { target: { value: 'unavailable' } });
    await screen.findByRole('checkbox', { name: 'Select Synthetic receipt 002' });
    const unavailable = screen.getByRole('checkbox', { name: 'Select Synthetic receipt 002' }) as HTMLInputElement;
    expect(unavailable.disabled).toBe(true); fireEvent.click(unavailable); expect(unavailable.checked).toBe(false);
    expect(request.mock.calls.some(([url]) => url === '/api/v1/library/collection/import')).toBe(false);
  });

  it('distinguishes an empty filter from an empty collection and keeps the source register when clearing', async () => {
    catalogueEntries = [receiptFor(1)];
    await mountCollection();
    fireEvent.change(screen.getByLabelText('Find a source'), { target: { value: 'No synthetic receipt matches' } });
    fireEvent.click(screen.getByRole('button', { name: 'Filter sources' }));
    await screen.findByText('No collected sources match these filters');
    expect(screen.getByText('0 matching receipts')).toBeTruthy();
    expect(screen.queryByText('This collection has no catalogue records yet')).toBeNull();
    expect((screen.getByRole('button', { name: 'Next sources' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Show all receipts' }));
    await screen.findByText('1–1 of 1 receipts');
    expect((screen.getByLabelText('Source register') as HTMLSelectElement).value).toBe('L02');
    expect((screen.getByLabelText('Find a source') as HTMLInputElement).value).toBe('');
    expect((screen.getByRole('checkbox', { name: 'Select Synthetic receipt 001' }) as HTMLInputElement).checked).toBe(false);
  });

  it('retries a failed candidate filter without hiding its criteria or making an import', async () => {
    catalogueEntries = [receiptFor(1)];
    let fail = true;
    request.mockImplementation(async (url, options) => String(url).includes('eligibility=inspection_required') && fail
      ? json({ error: { code: 'catalogue_unavailable', message: 'Synthetic receipt filter unavailable.', retryable: true } }, 503) : base(url, options));
    await mountCollection();
    fireEvent.change(screen.getByLabelText('Receipt eligibility'), { target: { value: 'inspection_required' } });
    await screen.findByText('Synthetic receipt filter unavailable.');
    expect(screen.queryByText('No collected sources match these filters')).toBeNull();
    expect((screen.getByLabelText('Receipt eligibility') as HTMLSelectElement).value).toBe('inspection_required');
    fail = false; fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await screen.findByText('1–1 of 1 matching receipts');
    expect(collectionCalls().slice(-2).map(([url]) => url)).toEqual([
      '/api/v1/library/collection/catalogue?limit=50&offset=0&source_id=L02&eligibility=inspection_required',
      '/api/v1/library/collection/catalogue?limit=50&offset=0&source_id=L02&eligibility=inspection_required']);
    expect(request.mock.calls.some(([url]) => url === '/api/v1/library/collection/import')).toBe(false);
  });

  it('discards a delayed candidate response after a newer eligible filter and resets selection on source changes', async () => {
    catalogueEntries = [receiptFor(1), receiptFor(2, 'eligible'), receiptFor(3, 'eligible', { source_id: 'E01' })];
    let release!: (value: unknown) => void;
    request.mockImplementation(async (url, options) => {
      if (String(url).includes('eligibility=inspection_required')) {
        const response = json({}); response.json = () => new Promise(resolve => { release = resolve; }); return response;
      }
      return base(url, options);
    });
    await mountCollection();
    fireEvent.change(screen.getByLabelText('Receipt eligibility'), { target: { value: 'inspection_required' } });
    await waitFor(() => expect(release).toBeTypeOf('function'));
    fireEvent.change(screen.getByLabelText('Receipt eligibility'), { target: { value: 'eligible' } });
    await screen.findByRole('checkbox', { name: 'Select Synthetic receipt 002' });
    fireEvent.click(screen.getByRole('checkbox', { name: 'Select Synthetic receipt 002' }));
    await act(async () => release(receiptPageFor('/api/v1/library/collection/catalogue?limit=50&offset=0&source_id=L02&eligibility=inspection_required')));
    expect(screen.queryByRole('checkbox', { name: 'Select Synthetic receipt 001' })).toBeNull();
    expect((screen.getByRole('checkbox', { name: 'Select Synthetic receipt 002' }) as HTMLInputElement).checked).toBe(true);
    fireEvent.change(screen.getByLabelText('Source register'), { target: { value: 'E01' } });
    await screen.findByRole('checkbox', { name: 'Select Synthetic receipt 003' });
    expect(screen.getByRole('button', { name: 'Queue selected (0)' })).toBeTruthy();
    expect((screen.getByRole('checkbox', { name: 'Select Synthetic receipt 003' }) as HTMLInputElement).checked).toBe(false);
  });

  it('does not let document polling abort a slow receipt filter or silently submit its selection', async () => {
    vi.useFakeTimers(); catalogueEntries = [receiptFor(1)];
    let release!: (value: Response) => void;
    request.mockImplementation(async (url, options) => String(url).includes('eligibility=inspection_required')
      ? await new Promise<Response>(resolve => { release = resolve; }) : base(url, options));
    await act(async () => { render(<LibraryPage />); });
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Collected sources' })); });
    await act(async () => { fireEvent.change(screen.getByLabelText('Source register'), { target: { value: 'L02' } }); });
    await act(async () => { fireEvent.click(screen.getByRole('checkbox', { name: 'Select Synthetic receipt 001' })); fireEvent.change(screen.getByLabelText('Receipt eligibility'), { target: { value: 'inspection_required' } }); });
    expect(release).toBeTypeOf('function');
    const pending = collectionCalls().at(-1)!;
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
    expect(pending[1]!.signal!.aborted).toBe(false);
    expect(collectionCalls().filter(([url]) => String(url).includes('eligibility=inspection_required'))).toHaveLength(1);
    await act(async () => { release(json(receiptPageFor(String(pending[0])))); });
    expect(screen.getByText('1–1 of 1 matching receipts')).toBeTruthy();
    expect((screen.getByRole('checkbox', { name: 'Select Synthetic receipt 001' }) as HTMLInputElement).checked).toBe(false);
    expect(request.mock.calls.some(([url]) => url === '/api/v1/library/collection/import')).toBe(false);
  });
});

describe('Deliberate import recovery', () => {
  it('retains a failed note request and reuses its import key on retry', async () => {
    const posted: Record<string, unknown>[] = [];
    request.mockImplementation(async (url, options) => {
      if (String(url) === '/api/v1/library/import/text') {
        posted.push(JSON.parse(options!.body as string));
        return posted.length === 1 ? json({ error: { code: 'unavailable', message: 'Synthetic note request unavailable.', retryable: true } }, 503) : json({ document_id: 'doc_note', revision_id: 'rev_note', status: 'queued', job: { id: 'job_note', revision_id: 'rev_note', state: 'queued', phase: 'queued', error_code: null, error_message: null } }, 202);
      }
      return base(url, options);
    });
    await mount(); fireEvent.click(screen.getByRole('button', { name: 'Add to library' }));
    fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'Synthetic dialysis note' } });
    fireEvent.change(screen.getByLabelText('Your study note'), { target: { value: 'Synthetic dialysis study text.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add note' }));
    await screen.findByText('Synthetic note request unavailable.');
    expect((screen.getByLabelText('Title') as HTMLInputElement).value).toBe('Synthetic dialysis note');
    expect((screen.getByLabelText('Your study note') as HTMLTextAreaElement).value).toBe('Synthetic dialysis study text.');
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await screen.findByText('Queued: your note has an import job.');
    expect(posted).toHaveLength(2); expect(posted[1]).toEqual(posted[0]);
    expect(posted[0]).toMatchObject({ scope: { kind: 'personal-library' }, title: 'Synthetic dialysis note' });
    expect(screen.getByRole('button', { name: 'View import details' })).toBeTruthy();
  });

  it('retains selected bytes, title and permission after file failure and preserves Unicode metadata in the header', async () => {
    const posted: { body: unknown; options: Record<string, unknown>; header: string }[] = [];
    request.mockImplementation(async (url, options) => {
      if (String(url) === '/api/v1/library/import/file') {
        const header = new Headers(options!.headers).get('x-renulus-import-options')!;
        posted.push({ body: options!.body, options: JSON.parse(header), header });
        return posted.length === 1 ? json({ error: { code: 'unavailable', message: 'Synthetic file request unavailable.', retryable: true } }, 503) : json({ document_id: 'doc_file', revision_id: 'rev_file', status: 'queued', job: { id: 'job_file', revision_id: 'rev_file', state: 'queued', phase: 'queued', error_code: null, error_message: null } }, 202);
      }
      return base(url, options);
    });
    await mount(); fireEvent.click(screen.getByRole('button', { name: 'Add to library' })); fireEvent.click(screen.getByRole('button', { name: 'Document' }));
    const file = new File(['Synthetic transplant text.'], 'Synthetic Łódź study.txt', { type: 'text/plain' });
    fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'Synthetic λ study 腎 📖' } });
    fireEvent.change(screen.getByLabelText('Choose a study document'), { target: { files: [file] } });
    const permission = screen.getByRole('checkbox', { name: 'I have permission to read, store, index and use this file for local learning.' }) as HTMLInputElement;
    fireEvent.click(permission); fireEvent.click(screen.getByRole('button', { name: 'Add document' }));
    await screen.findByText('Synthetic file request unavailable.');
    expect((screen.getByLabelText('Title') as HTMLInputElement).value).toBe('Synthetic λ study 腎 📖');
    expect(permission.checked).toBe(true); expect(screen.getByText(/Selected: Synthetic Łódź study.txt/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await screen.findByText('Queued: follow processing below.');
    expect(posted).toHaveLength(2); expect(posted[1].body).toBe(file); expect(posted[1].options).toEqual(posted[0].options);
    expect(posted[0].options.title).toBe('Synthetic λ study 腎 📖');
    expect([...posted[0].header].every(character => character.charCodeAt(0) < 127)).toBe(true);
  });

  it('requires a new permission confirmation when the selected file changes and explains unsupported input', async () => {
    await mount(); fireEvent.click(screen.getByRole('button', { name: 'Add to library' })); fireEvent.click(screen.getByRole('button', { name: 'Document' }));
    const input = screen.getByLabelText('Choose a study document');
    fireEvent.change(input, { target: { files: [new File(['Synthetic note'], 'first.txt')] } });
    const permission = screen.getByRole('checkbox', { name: 'I have permission to read, store, index and use this file for local learning.' }) as HTMLInputElement;
    fireEvent.click(permission);
    expect((screen.getByRole('button', { name: 'Add document' }) as HTMLButtonElement).disabled).toBe(false);
    fireEvent.change(input, { target: { files: [new File(['Synthetic file'], 'second.exe')] } });
    expect(permission.checked).toBe(false); expect((screen.getByRole('button', { name: 'Add document' }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText('Choose a PDF, PNG, JPEG, TIFF, text, DOCX, PPTX or XLSX file.')).toBeTruthy();
    expect(input.getAttribute('aria-invalid')).toBe('true');
    expect(request.mock.calls.some(([url]) => String(url).includes('/library/import/'))).toBe(false);
  });

  it('rejects an oversized file without allocating large fixture bytes or posting it', async () => {
    await mount(); fireEvent.click(screen.getByRole('button', { name: 'Add to library' })); fireEvent.click(screen.getByRole('button', { name: 'Document' }));
    const file = new File(['Synthetic size boundary'], 'large.txt');
    Object.defineProperty(file, 'size', { value: 64 * 1024 * 1024 + 1 });
    fireEvent.change(screen.getByLabelText('Choose a study document'), { target: { files: [file] } });
    expect(screen.getByText('This file exceeds 64 MiB. Choose a smaller document.')).toBeTruthy();
    expect((screen.getByRole('button', { name: 'Add document' }) as HTMLButtonElement).disabled).toBe(true);
    expect(request.mock.calls.some(([url]) => String(url).includes('/library/import/'))).toBe(false);
  });

  it('reimports a failed source into the same document while retaining its original metadata and operation rights', async () => {
    const source = records[150];
    source.scope = { kind: 'personal-library', entity_id: null };
    source.revisions[0].metadata.edition = 'Synthetic verified edition';
    source.revisions[0].rights = { ...source.revisions[0].rights, model_input: false, licence: 'Synthetic retained licence', attribution: 'Synthetic retained author' };
    let posted: Record<string, unknown> | undefined;
    request.mockImplementation(async (url, options) => {
      if (String(url) === '/api/v1/library/import/file') {
        posted = JSON.parse(new Headers(options!.headers).get('x-renulus-import-options')!);
        return json({ document_id: source.id, revision_id: 'rev_retry', status: 'queued', job: { id: 'job_retry', revision_id: 'rev_retry', state: 'queued', phase: 'queued', error_code: null, error_message: null } }, 202);
      }
      return base(url, options);
    });
    await mount(); fireEvent.change(screen.getByLabelText('Import status'), { target: { value: 'failed' } });
    fireEvent.click(await screen.findByRole('button', { name: source.title }));
    await screen.findByText('Synthetic extraction failed. Choose the original again.');
    expect(screen.getByText('Synthetic retained licence', { selector: 'dd' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Retry import' }));
    expect((screen.getByLabelText('Title') as HTMLInputElement).value).toBe(source.title);
    fireEvent.change(screen.getByLabelText('Choose a study document'), { target: { files: [new File(['Synthetic replacement bytes'], 'retry.txt')] } });
    fireEvent.click(screen.getByRole('checkbox', { name: 'I have permission to read, store, index and use this file for local learning.' }));
    fireEvent.click(screen.getByRole('button', { name: 'Add document' }));
    await screen.findByText('Queued: follow processing below.');
    expect(posted).toMatchObject({ document_id: source.id, title: source.title, scope: source.scope, metadata: source.revisions[0].metadata, rights: source.revisions[0].rights, reserved: false });
    expect((posted!.rights as Record<string, unknown>).model_input).toBe(false);
    expect(request.mock.calls.some(([url]) => String(url).includes('/jobs/') && String(url).includes('/retry'))).toBe(false);
  });

  it('retains rejected receipt selection after a partial batch without automatically submitting it again', async () => {
    catalogueEntries = [receiptFor(1, 'eligible'), receiptFor(2, 'eligible')];
    request.mockImplementation(async (url, options) => String(url) === '/api/v1/library/collection/import'
      ? json({ queued: 1, results: [{ entry_id: 'receipt_1', status: 'queued' }, { entry_id: 'receipt_2', status: 'failed', message: 'Synthetic permission needs review.' }] }, 202) : base(url, options));
    await mountCollection();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Select Synthetic receipt 001' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Select Synthetic receipt 002' }));
    fireEvent.click(screen.getByRole('button', { name: 'Queue selected (2)' }));
    await screen.findByText(/1 imports queued. 1 selected entry needs attention/);
    expect((screen.getByRole('checkbox', { name: 'Select Synthetic receipt 001' }) as HTMLInputElement).checked).toBe(false);
    expect((screen.getByRole('checkbox', { name: 'Select Synthetic receipt 002' }) as HTMLInputElement).checked).toBe(true);
    expect(screen.getByRole('button', { name: 'Queue selected (1)' })).toBeTruthy();
    expect(request.mock.calls.filter(([url]) => String(url) === '/api/v1/library/collection/import')).toHaveLength(1);
  });

  it('returns an acquired article retry to its receipt checks without a raw-file replacement or automatic selection', async () => {
    const source = records[150]; source.source_id = 'L02';
    source.title = ('Synthetic acquired article with a long title ' + 'study '.repeat(40)).trim();
    source.revisions[0].metadata = { ...source.revisions[0].metadata, source_id: 'L02', asset_role: ['acquired-jats'], original_sha256: 'a'.repeat(64) };
    catalogueEntries = [receiptFor(1, 'eligible', { title: source.title, document_id: source.id, processing_status: 'failed' })];
    await mount(); fireEvent.change(screen.getByLabelText('Import status'), { target: { value: 'failed' } });
    fireEvent.click(await screen.findByRole('button', { name: source.title }));
    fireEvent.click(await screen.findByRole('button', { name: 'Retry import' }));
    await screen.findByRole('region', { name: 'Collected source receipts' });
    expect((screen.getByLabelText('Source register') as HTMLSelectElement).value).toBe('L02');
    expect((screen.getByLabelText('Find a source') as HTMLInputElement).value).toBe(source.title.slice(0, 200));
    const path = String(collectionCalls().at(-1)![0]);
    expect(new URL(path, 'http://127.0.0.1').searchParams.get('query')).toBe(source.title.slice(0, 200));
    expect((screen.getByRole('checkbox', { name: 'Select ' + source.title }) as HTMLInputElement).checked).toBe(false);
    expect(screen.queryByLabelText('Choose a study document')).toBeNull();
    expect(request.mock.calls.some(([url]) => String(url).includes('/library/import/') || String(url) === '/api/v1/library/collection/import')).toBe(false);
  });
});
