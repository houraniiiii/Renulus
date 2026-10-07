// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { NavigationProvider, useNavigation } from '../../shell/navigation';
import LibraryPage from './index';
import SourceInspector from './SourceInspector';
import Learn from '../learn';
import type { Citation, LibraryDocument, Locator, Revision } from './types';

const metadata = { source_id: 'SYNTHETIC', source_owner: 'Renulus synthetic test', canonical_url: null, edition: 'Cited edition', publication_date: null, received_at: null, checked_at: null, publication_status: 'unverified', latest_final_verified: false, content_reviewed: false, collection_section: null, collection_chapter: null, notes: [] };
const rights = { display: true, cache: true, index: true, embedding: true, model_input: true, derivation: false, evaluation: false, redistribution: true, licence: 'Synthetic fixture', permission_reference: 'Synthetic test permission', attribution: 'Renulus' };
const oldRevision: Revision = { id: 'synthetic-cited-revision', document_id: 'synthetic-document', ordinal: 1, status: 'ready', sha256: 'a'.repeat(64), media_type: 'application/pdf', bytes: 100, passage_count: 2, metadata, rights };
const document: LibraryDocument = { id: oldRevision.document_id, title: 'Synthetic cited source', source_id: metadata.source_id, status: 'ready', reserved: false, cleanup_pending: false, active_revision: 'synthetic-current-revision', latest_revision: 'synthetic-current-revision', revisions: [{ ...oldRevision, id: 'synthetic-current-revision', ordinal: 2, metadata: { ...metadata, edition: 'Newer edition' } }, oldRevision] };
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
const target = { document_id: document.id, revision_id: oldRevision.id, passage_id: 'passage_' + 'a'.repeat(32), page: 2 };
const newerPassageId = 'passage_' + 'b'.repeat(32);
const citation = (page: number | null): Citation => ({ document_id: document.id, document_revision: oldRevision.id, passage_id: target.passage_id, title: document.title, page, locators: [{ item_ref: '#/texts/1', page: page ?? 1, char_span: [0, 20] }], original_url: '/api/v1/library/revisions/' + oldRevision.id + '/original' });
const request = vi.fn<typeof fetch>();
async function base(url: RequestInfo | URL) {
  const path = String(url);
  if (path.startsWith('/api/v1/library/documents?')) return json({ documents: [document], total: 1, counts: { ready: 1 }, offset: 0, limit: 25 });
  if (path === '/api/v1/library/documents/' + document.id) return json(document);
  if (path === '/api/v1/library/capabilities') return json({ text_import: true, pdf_image_import: false, temporary_extraction: false });
  if (path.startsWith('/api/v1/library/collection/catalogue?')) return json({ entries: [], total: 0, offset: 0, limit: 50 });
  if (path === '/api/v1/content/topics') return json([]);
  if (path === '/api/v1/retrieval/connections') return json({ connections: [], selected_tool: null });
  const endpoint = new URL(path, 'https://synthetic.invalid');
  if (endpoint.pathname === '/api/v1/library/revisions/' + oldRevision.id + '/citation') {
    if (endpoint.searchParams.get('page') === '2') return json({ error: { code: 'page_missing', message: 'That page has no extracted citation location', retryable: false } }, 404);
    return json(citation(null));
  }
  if (path === citation(null).original_url) return new Response('Synthetic PDF protocol fixture', { headers: { 'Content-Type': 'application/pdf' } });
  throw new Error('Unexpected synthetic endpoint: ' + path);
}
function Journey() {
  const navigation = useNavigation();
  return <><button onClick={() => navigation.navigate('library', { payload: target })}>Inspect cited revision</button>
    <button onClick={() => navigation.navigate('library', { payload: { ...target, page: null } })}>Inspect unknown page</button>
    <button onClick={() => navigation.navigate('library', { payload: { ...target, passage_id: newerPassageId } })}>Inspect another passage on this page</button>
    <button onClick={() => navigation.navigate('library', { payload: { ...target, passage_id: newerPassageId, revision_id: document.active_revision, page: 3 } })}>Inspect newer citation</button><LibraryPage /></>;
}
function DiscussionJourney() {
  const navigation = useNavigation();
  return navigation.route === 'library' ? <LibraryPage /> : <Learn />;
}
function discussion(citedPage: number | null) {
  const events = [{ type: 'sources', payload: { citations: [{ id: target.passage_id, document_id: document.id, document_revision: oldRevision.id, locators: [{ page: citedPage }] }] } },
    { type: 'delta', payload: { text: 'Synthetic discussion answer.' } }, { type: 'completed', payload: {} }];
  return new Response(events.map(({ type, payload }, index) => 'event: ' + type + '\ndata: ' + JSON.stringify({ run_id: 'synthetic-run', sequence: index + 1, type, payload }) + '\n\n').join(''), { headers: { 'Content-Type': 'text/event-stream' } });
}
beforeEach(() => {
  window.history.replaceState(null, '', '#/library');
  request.mockReset().mockImplementation(base); vi.stubGlobal('fetch', request);
  let blobNumber = 0;
  vi.stubGlobal('URL', class extends URL {
    static createObjectURL() { return 'blob:synthetic-original-' + ++blobNumber; }
    static revokeObjectURL() {}
  });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Library citation journey', () => {
  it.each([
    { media: 'application/vnd.openxmlformats-officedocument.presentationml.presentation', locator: { item_ref: '#/texts/0', page: null, format: 'pptx', slide: 2 }, label: 'Slide 2 · source location in the original presentation.' },
    { media: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', locator: { item_ref: '#/tables/0', table_ref: '#/tables/0', page: null, format: 'xlsx', sheet: 1, sheet_name: 'Adequacy' }, label: 'Sheet Adequacy · source location in the original workbook.' },
    { media: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', locator: { item_ref: '#/tables/0', table_ref: '#/tables/0', page: null, format: 'docx' }, label: 'Document table · source location in the original document.' },
  ])('shows the real Office location for $media without inventing a physical page', async ({ media, locator, label }) => {
    const value = { ...citation(null), locators: [locator as Locator] };
    request.mockImplementation(async url => String(url).endsWith('/original') ? new Response('Synthetic Office bytes', { headers: { 'Content-Type': media } }) : json(value));
    render(<SourceInspector document={{ ...document, revisions: [{ ...oldRevision, media_type: media }] }} location={{ revisionId: oldRevision.id, page: null, passageId: target.passage_id }} />);
    await screen.findByText(label);
    expect(screen.queryByText(/Physical page is unknown/)).toBeNull();
    expect(screen.getByText('Renulus', { selector: 'dd' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Open original' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Open original' }));
    const extension = locator.format;
    const original = await screen.findByRole('link', { name: 'Save original (.' + extension + ')' });
    expect(original.getAttribute('download')).toBe('renulus-original.' + extension);
    expect(screen.queryByTitle('Original document viewer')).toBeNull();
  });

  it('keeps a ready no-text image viewable and explains that search has no text', async () => {
    request.mockImplementation(async url => String(url).endsWith('/original') ? new Response('Synthetic no-text image bytes', { headers: { 'Content-Type': 'image/png' } }) : json({ ...citation(null), locators: [] }));
    render(<SourceInspector document={{ ...document, revisions: [{ ...oldRevision, media_type: 'image/png', passage_count: 0 }] }} location={{ revisionId: oldRevision.id, page: null, passageId: null }} />);
    await screen.findByRole('button', { name: 'Open original' });
    expect(screen.getByText('This image is available to view. No searchable text was extracted.')).toBeTruthy();
    expect(screen.getByText('Open the original for visual study. It will not appear in passage search.')).toBeTruthy();
    expect(screen.queryByText(/Physical page is unknown/)).toBeNull();
    expect(screen.queryByText(/0 extracted source locations/)).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Open original' }));
    expect((await screen.findByRole('img', { name: 'Original imported document' })).getAttribute('src')).toBe('blob:synthetic-original-1');
    expect(screen.getByRole('link', { name: 'Save original (.png)' })).toBeTruthy();
  });

  it('updates the selected reader after a queued no-text image becomes available', async () => {
    let ready = false;
    const imageDocument = () => ({ ...document, status: ready ? 'ready' : 'queued', active_revision: ready ? oldRevision.id : null, latest_revision: oldRevision.id, revisions: [{ ...oldRevision, status: ready ? 'ready' : 'queued', media_type: 'image/png', passage_count: 0 }] });
    request.mockImplementation(async url => {
      const path = String(url);
      if (path.startsWith('/api/v1/library/documents?')) return json({ documents: [imageDocument()], total: 1, counts: ready ? { ready: 1 } : { queued: 1 }, offset: 0, limit: 25 });
      if (path === '/api/v1/library/documents/' + document.id) return json(imageDocument());
      if (path.endsWith('/import-status')) return json({ document_id: document.id, revision_id: oldRevision.id, status: ready ? 'ready' : 'queued', job: { id: 'job_image', revision_id: oldRevision.id, state: ready ? 'ready' : 'queued', phase: ready ? 'complete' : 'queued', error_code: null, error_message: null } });
      if (path === '/api/v1/library/queue') return json({ running: true, cpu_workers: 1, queued: 1, active_job: null, error_code: null });
      if (path.includes('/' + oldRevision.id + '/citation')) return json({ ...citation(null), passage_id: undefined, locators: [] });
      return base(url);
    });
    render(<NavigationProvider><LibraryPage /></NavigationProvider>);
    fireEvent.click(await screen.findByRole('button', { name: document.title }));
    const reader = screen.getByRole('complementary', { name: 'Source reader' });
    await within(reader).findByText(/This import is waiting/);
    expect(within(reader).queryByRole('button', { name: 'Open original' })).toBeNull();
    ready = true; fireEvent.click(screen.getByRole('button', { name: 'Refresh documents' }));
    await within(reader).findByText('This image is available to view. No searchable text was extracted.');
    expect(await within(reader).findByRole('button', { name: 'Open original' })).toBeTruthy();
    expect(within(reader).queryByText(/waiting for document processing/)).toBeNull();
  });

  it('keeps an earlier ready original open while a replacement job reports failure', async () => {
    const failed = { ...document, status: 'failed', active_revision: oldRevision.id, revisions: [{ ...oldRevision, id: document.latest_revision!, status: 'failed', metadata: { ...metadata, edition: 'Failed replacement edition' } }, oldRevision] };
    request.mockImplementation(async url => {
      const path = String(url);
      if (path.startsWith('/api/v1/library/documents?')) return json({ documents: [failed], total: 1, counts: { failed: 1 }, offset: 0, limit: 25 });
      if (path === '/api/v1/library/documents/' + document.id) return json(failed);
      if (path.endsWith('/import-status')) return json({ document_id: document.id, revision_id: document.latest_revision, status: 'failed', job: { id: 'job_failed', revision_id: document.latest_revision, state: 'failed', phase: 'failed', error_code: 'extraction_failed', error_message: 'Synthetic replacement failed.' } });
      return base(url);
    });
    render(<NavigationProvider><LibraryPage /></NavigationProvider>);
    fireEvent.click(await screen.findByRole('button', { name: document.title }));
    const reader = screen.getByRole('complementary', { name: 'Source reader' });
    await within(reader).findByText('Synthetic replacement failed.');
    expect(await within(reader).findByRole('button', { name: 'Open original' })).toBeTruthy();
    expect(within(reader).getByText('Cited edition')).toBeTruthy();
    expect(within(reader).queryByText('Failed replacement edition', { selector: 'dd' })).toBeNull();
    fireEvent.click(within(reader).getByRole('button', { name: 'Open original' }));
    await within(reader).findByTitle('Original document viewer');
    expect(request.mock.calls.some(([url]) => String(url) === citation(null).original_url)).toBe(true);
    expect(request.mock.calls.some(([url]) => String(url).includes('/' + document.latest_revision + '/original'))).toBe(false);
  });

  it('explains a missing physical page and retains the cited edition for opening the whole original', async () => {
    render(<NavigationProvider><Journey /></NavigationProvider>);
    fireEvent.click(screen.getByRole('button', { name: 'Inspect cited revision' }));
    const reader = screen.getByRole('complementary', { name: 'Source reader' });
    await within(reader).findByText('Cited page 2 is unavailable. You can still open this original without a page jump.');
    expect(within(reader).getByText('Cited edition')).toBeTruthy();
    expect(within(reader).queryByText('Newer edition')).toBeNull();
    expect(within(reader).getByRole('button', { name: 'Open whole original' })).toBeTruthy();
    fireEvent.click(within(reader).getByRole('button', { name: 'Open whole original' }));
    expect((await within(reader).findByTitle('Original document viewer')).getAttribute('src')).toBe('blob:synthetic-original-1');
    expect(request.mock.calls.some(([url]) => String(url).includes('synthetic-current-revision/citation'))).toBe(false);
    expect(request.mock.calls.filter(([url]) => String(url).includes('/citation')).map(([url]) => url)).toEqual([
      '/api/v1/library/revisions/' + oldRevision.id + '/citation?page=2&passage_id=' + target.passage_id,
      '/api/v1/library/revisions/' + oldRevision.id + '/citation?passage_id=' + target.passage_id,
    ]);
  });

  it.each([{ format: 'PDF', mediaType: 'application/pdf', page: 2 }, { format: 'text', mediaType: 'text/plain', page: null }, { format: 'image', mediaType: 'image/png', page: 1 }])('keeps a generated discussion citation pinned to its $format original and physical locator', async ({ format, mediaType, page }) => {
    window.history.replaceState(null, '', '#/learn');
    request.mockImplementation(async url => {
      const path = String(url);
      if (path === '/api/v1/learn/threads') return json({ threads: [] });
      if (path === '/api/v1/learn/ask') return discussion(page);
      if (path === '/api/v1/library/documents/' + document.id) return json({ ...document, revisions: document.revisions.map(revision => ({ ...revision, media_type: mediaType })) });
      if (path.includes('/' + oldRevision.id + '/citation')) return json({ ...citation(page), locators: [{ item_ref: '#/texts/1', page, char_span: [0, 20] }] });
      if (path === citation(page).original_url) return new Response('Synthetic ' + format + ' original', { headers: { 'Content-Type': mediaType } });
      return base(url);
    });
    render(<NavigationProvider><DiscussionJourney /></NavigationProvider>);
    fireEvent.change(screen.getByRole('textbox', { name: 'Your nephrology question' }), { target: { value: 'Synthetic source journey question.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Ask Renulus' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Source 1' }));
    const reader = screen.getByRole('complementary', { name: 'Source reader' });
    const open = await within(reader).findByRole('button', { name: page ? 'Open original · page ' + page : 'Open original' });
    expect(within(reader).getByText('Cited edition')).toBeTruthy();
    expect(within(reader).queryByText('Newer edition')).toBeNull();
    expect(window.location.hash).toBe('#/library');
    fireEvent.click(open);
    if (format === 'PDF') expect((await within(reader).findByTitle('Original document viewer')).getAttribute('src')).toBe('blob:synthetic-original-1#page=2');
    if (format === 'text') {
      expect(await within(reader).findByText('Synthetic text original')).toBeTruthy();
      expect(within(reader).queryByTitle('Original document viewer')).toBeNull();
    }
    if (format === 'image') expect((await within(reader).findByRole('img', { name: 'Original imported document' })).getAttribute('src')).toBe('blob:synthetic-original-1');
    expect(request.mock.calls.some(([url]) => String(url).includes('synthetic-current-revision/'))).toBe(false);
    const locationRequest = request.mock.calls.map(([url]) => new URL(String(url), 'https://synthetic.invalid'))
      .find(url => url.pathname === '/api/v1/library/revisions/' + oldRevision.id + '/citation');
    expect(locationRequest?.searchParams.get('passage_id')).toBe(target.passage_id);
    expect(locationRequest?.searchParams.get('page')).toBe(page === null ? null : String(page));
    expect(within(reader).getByText('1 extracted source location for this passage. Exact passage highlighting is unavailable.')).toBeTruthy();
    expect(request.mock.calls.some(([url]) => String(url) === citation(page).original_url)).toBe(true);
  });

  it('does not display a delayed original under a newer citation', async () => {
    let release!: (blob: Blob) => void;
    request.mockImplementation(async url => {
      const path = String(url);
      if (path === citation(2).original_url) {
        const response = new Response(null, { headers: { 'Content-Type': 'application/pdf' } });
        response.blob = () => new Promise(resolve => { release = resolve; }); return response;
      }
      if (path.includes('/' + oldRevision.id + '/citation?page=2')) return json(citation(2));
      if (path.includes('/synthetic-current-revision/citation?page=3')) return json({ ...citation(3), passage_id: newerPassageId, document_revision: document.active_revision, original_url: '/api/v1/library/revisions/synthetic-current-revision/original' });
      return base(url);
    });
    render(<NavigationProvider><Journey /></NavigationProvider>);
    fireEvent.click(screen.getByRole('button', { name: 'Inspect cited revision' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Open original · page 2' }));
    await waitFor(() => expect(release).toBeTypeOf('function'));
    fireEvent.click(screen.getByRole('button', { name: 'Inspect newer citation' }));
    await screen.findByRole('button', { name: 'Open original · page 3' });
    await act(async () => release(new Blob(['Synthetic old PDF bytes'], { type: 'application/pdf' })));
    const reader = screen.getByRole('complementary', { name: 'Source reader' });
    expect(within(reader).queryByTitle('Original document viewer')).toBeNull();
    expect(within(reader).getByText('Newer edition')).toBeTruthy();
    expect(within(reader).getByRole('button', { name: 'Open original · page 3' })).toBeTruthy();
  });

  it('rejects a citation response without the requested physical page instead of opening at that page', async () => {
    request.mockImplementation(async url => {
      const path = String(url);
      if (path.includes('/' + oldRevision.id + '/citation?page=2')) return json({ ...citation(null), locators: [{ item_ref: '#/texts/1', page: null, char_span: [0, 20] }] });
      return base(url);
    });
    render(<NavigationProvider><Journey /></NavigationProvider>);
    fireEvent.click(screen.getByRole('button', { name: 'Inspect cited revision' }));
    await screen.findByRole('alert');
    expect(screen.queryByRole('button', { name: /Open original/ })).toBeNull();
    expect(screen.getByText('The citation does not match this source revision, passage and page. Try again.')).toBeTruthy();
  });

  it('opens an unknown-page PDF without choosing a page from unrelated revision locators', async () => {
    render(<NavigationProvider><Journey /></NavigationProvider>);
    fireEvent.click(screen.getByRole('button', { name: 'Inspect unknown page' }));
    await screen.findByText('Physical page is unknown. The original opens without a page jump.');
    fireEvent.click(screen.getByRole('button', { name: 'Open original' }));
    expect((await screen.findByTitle('Original document viewer')).getAttribute('src')).toBe('blob:synthetic-original-1');
    expect(request.mock.calls.filter(([url]) => String(url).includes('/citation')).map(([url]) => url)).toEqual(['/api/v1/library/revisions/' + oldRevision.id + '/citation?passage_id=' + target.passage_id]);
  });

  it('shows an unavailable pinned revision without opening the current replacement', async () => {
    request.mockImplementation(async url => String(url).includes('/' + oldRevision.id + '/citation')
      ? json({ error: { code: 'citation_missing', message: 'The cited document revision is unavailable', retryable: false } }, 404) : base(url));
    render(<NavigationProvider><Journey /></NavigationProvider>);
    fireEvent.click(screen.getByRole('button', { name: 'Inspect cited revision' }));
    await screen.findByText('The cited document revision is unavailable');
    expect(screen.queryByRole('button', { name: /Open (whole )?original/ })).toBeNull();
    expect(request.mock.calls.filter(([url]) => String(url).includes('/citation'))).toHaveLength(1);
    expect(request.mock.calls.some(([url]) => String(url).includes('synthetic-current-revision/'))).toBe(false);
  });

  it('keeps passage search citations exact when switching between passages sharing a page', async () => {
    request.mockImplementation(async url => {
      const endpoint = new URL(String(url), 'https://synthetic.invalid');
      if (endpoint.pathname === '/api/v1/library/retrieve') return json({ passages: [
        { id: target.passage_id, text: 'Synthetic first passage', title: document.title, document_id: document.id, document_revision: oldRevision.id, source_id: metadata.source_id, locators: citation(2).locators },
        { id: newerPassageId, text: 'Synthetic second passage', title: document.title, document_id: document.id, document_revision: oldRevision.id, source_id: metadata.source_id, locators: citation(2).locators },
      ] });
      if (endpoint.pathname.endsWith('/' + oldRevision.id + '/citation')) {
        const second = endpoint.searchParams.get('passage_id') === newerPassageId;
        return json({ ...citation(2), passage_id: second ? newerPassageId : target.passage_id,
          locators: second ? [...citation(2).locators, { item_ref: '#/texts/42', page: 2, char_span: [50, 70] }] : citation(2).locators });
      }
      return base(url);
    });
    render(<NavigationProvider><LibraryPage /></NavigationProvider>);
    fireEvent.change(screen.getByRole('textbox', { name: 'Find a passage' }), { target: { value: 'Synthetic passage' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    const inspect = await screen.findAllByRole('button', { name: 'Inspect citation' });
    fireEvent.click(inspect[0]);
    await screen.findByText('1 extracted source location for this passage. Exact passage highlighting is unavailable.');
    fireEvent.click(inspect[1]);
    await screen.findByText('2 extracted source locations for this passage. Exact passage highlighting is unavailable.');
    const locations = request.mock.calls.map(([url]) => new URL(String(url), 'https://synthetic.invalid'))
      .filter(url => url.pathname.endsWith('/citation'));
    expect(locations.map(url => [url.searchParams.get('passage_id'), url.searchParams.get('page')]))
      .toEqual([[target.passage_id, '2'], [newerPassageId, '2']]);
    expect(locations.every(url => url.pathname.includes(oldRevision.id))).toBe(true);
  });

  it.each([undefined, newerPassageId])('rejects a missing or different passage identity in the citation response (%s)', async passageId => {
    request.mockImplementation(async url => String(url).includes('/' + oldRevision.id + '/citation')
      ? json({ ...citation(2), passage_id: passageId }) : base(url));
    render(<NavigationProvider><Journey /></NavigationProvider>);
    fireEvent.click(screen.getByRole('button', { name: 'Inspect cited revision' }));
    await screen.findByText('The citation does not match this source revision, passage and page. Try again.');
    expect(screen.queryByRole('button', { name: /Open (whole )?original/ })).toBeNull();
    expect(request.mock.calls.filter(([url]) => String(url).includes('/citation'))).toHaveLength(1);
    expect(request.mock.calls.some(([url]) => String(url).endsWith('/original'))).toBe(false);
  });

  it.each([{ status: 404, code: 'passage_missing' }, { status: 403, code: 'display_denied' },
    { status: 503, code: 'offline' }, { status: 403, code: 'page_missing' }])
  ('does not broaden a blocked citation after $status $code', async ({ status, code }) => {
    request.mockImplementation(async url => String(url).includes('/' + oldRevision.id + '/citation')
      ? json({ error: { code, message: 'Synthetic passage is unavailable', retryable: false } }, status) : base(url));
    render(<NavigationProvider><Journey /></NavigationProvider>);
    fireEvent.click(screen.getByRole('button', { name: 'Inspect cited revision' }));
    await screen.findByText('Synthetic passage is unavailable');
    expect(screen.queryByRole('button', { name: /Open (whole )?original/ })).toBeNull();
    expect(request.mock.calls.filter(([url]) => String(url).includes('/citation'))).toHaveLength(1);
    expect(request.mock.calls.some(([url]) => String(url).endsWith('/original'))).toBe(false);
  });

  it('keeps document-level browsing available without inventing a passage binding', async () => {
    request.mockImplementation(async url => String(url).endsWith('/synthetic-current-revision/citation')
      ? json({ ...citation(null), passage_id: undefined, document_revision: document.active_revision,
          original_url: '/api/v1/library/revisions/synthetic-current-revision/original' }) : base(url));
    render(<NavigationProvider><LibraryPage /></NavigationProvider>);
    fireEvent.click(await screen.findByRole('button', { name: document.title }));
    await screen.findByRole('button', { name: 'Open original' });
    expect(screen.getByText('1 extracted source location in this revision. Exact passage highlighting is unavailable.')).toBeTruthy();
    expect(request.mock.calls.filter(([url]) => String(url).includes('/citation')).map(([url]) => url))
      .toEqual(['/api/v1/library/revisions/synthetic-current-revision/citation']);
  });
});
