// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { NavigationProvider, useNavigation } from '../../shell/navigation';
import LibraryPage from './index';
import Learn from '../learn';
import type { Citation, LibraryDocument, Revision } from './types';

const metadata = { source_id: 'SYNTHETIC', source_owner: 'Renulus synthetic test', canonical_url: null, edition: 'Cited edition', publication_date: null, received_at: null, checked_at: null, publication_status: 'unverified', latest_final_verified: false, content_reviewed: false, collection_section: null, collection_chapter: null, notes: [] };
const rights = { display: true, cache: true, index: true, embedding: true, model_input: true, derivation: false, evaluation: false, redistribution: true, licence: 'Synthetic fixture', permission_reference: 'Synthetic test permission', attribution: 'Renulus' };
const oldRevision: Revision = { id: 'synthetic-cited-revision', document_id: 'synthetic-document', ordinal: 1, status: 'ready', sha256: 'a'.repeat(64), media_type: 'application/pdf', bytes: 100, passage_count: 2, metadata, rights };
const document: LibraryDocument = { id: oldRevision.document_id, title: 'Synthetic cited source', source_id: metadata.source_id, status: 'ready', reserved: false, cleanup_pending: false, active_revision: 'synthetic-current-revision', latest_revision: 'synthetic-current-revision', revisions: [{ ...oldRevision, id: 'synthetic-current-revision', ordinal: 2, metadata: { ...metadata, edition: 'Newer edition' } }, oldRevision] };
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
const target = { document_id: document.id, revision_id: oldRevision.id, passage_id: 'synthetic-passage', page: 2 };
const citation = (page: number | null): Citation => ({ document_id: document.id, document_revision: oldRevision.id, title: document.title, page, locators: [{ item_ref: '#/texts/1', page: page ?? 1, char_span: [0, 20] }], original_url: '/api/v1/library/revisions/' + oldRevision.id + '/original' });
const request = vi.fn<typeof fetch>();
async function base(url: RequestInfo | URL) {
  const path = String(url);
  if (path.startsWith('/api/v1/library/documents?')) return json({ documents: [document], total: 1, counts: { ready: 1 }, offset: 0, limit: 25 });
  if (path === '/api/v1/library/documents/' + document.id) return json(document);
  if (path === '/api/v1/library/capabilities') return json({ text_import: true, pdf_image_import: false, temporary_extraction: false });
  if (path.startsWith('/api/v1/library/collection/catalogue?')) return json({ entries: [], total: 0, offset: 0, limit: 50 });
  if (path === '/api/v1/content/topics') return json([]);
  if (path === '/api/v1/retrieval/connections') return json({ connections: [], selected_tool: null });
  if (path === '/api/v1/library/revisions/' + oldRevision.id + '/citation?page=2') return json({ error: { code: 'page_missing', message: 'That page has no extracted citation location', retryable: false } }, 404);
  if (path === '/api/v1/library/revisions/' + oldRevision.id + '/citation') return json(citation(null));
  if (path === citation(null).original_url) return new Response('Synthetic PDF protocol fixture', { headers: { 'Content-Type': 'application/pdf' } });
  throw new Error('Unexpected synthetic endpoint: ' + path);
}
function Journey() {
  const navigation = useNavigation();
  return <><button onClick={() => navigation.navigate('library', { payload: target })}>Inspect cited revision</button>
    <button onClick={() => navigation.navigate('library', { payload: { ...target, page: null } })}>Inspect unknown page</button>
    <button onClick={() => navigation.navigate('library', { payload: { ...target, revision_id: document.active_revision, page: 3 } })}>Inspect newer citation</button><LibraryPage /></>;
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
    expect(request.mock.calls.some(([url]) => String(url).includes('/' + oldRevision.id + '/citation' + (page ? '?page=' + page : '')))).toBe(true);
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
      if (path.endsWith('/' + oldRevision.id + '/citation?page=2')) return json(citation(2));
      if (path.endsWith('/synthetic-current-revision/citation?page=3')) return json({ ...citation(3), document_revision: document.active_revision, original_url: '/api/v1/library/revisions/synthetic-current-revision/original' });
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
      if (path.endsWith('/' + oldRevision.id + '/citation?page=2')) return json({ ...citation(null), locators: [{ item_ref: '#/texts/1', page: null, char_span: [0, 20] }] });
      return base(url);
    });
    render(<NavigationProvider><Journey /></NavigationProvider>);
    fireEvent.click(screen.getByRole('button', { name: 'Inspect cited revision' }));
    await screen.findByRole('alert');
    expect(screen.queryByRole('button', { name: /Open original/ })).toBeNull();
    expect(screen.getByText('The citation does not match this source revision and page. Try again.')).toBeTruthy();
  });

  it('opens an unknown-page PDF without choosing a page from unrelated revision locators', async () => {
    render(<NavigationProvider><Journey /></NavigationProvider>);
    fireEvent.click(screen.getByRole('button', { name: 'Inspect unknown page' }));
    await screen.findByText('Physical page is unknown. The original opens without a page jump.');
    fireEvent.click(screen.getByRole('button', { name: 'Open original' }));
    expect((await screen.findByTitle('Original document viewer')).getAttribute('src')).toBe('blob:synthetic-original-1');
    expect(request.mock.calls.filter(([url]) => String(url).includes('/citation')).map(([url]) => url)).toEqual(['/api/v1/library/revisions/' + oldRevision.id + '/citation']);
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
});
