// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Discovery } from './Discovery';
import LibraryPage from './index';

const { navigation } = vi.hoisted(() => ({ navigation: { scope: { kind: 'study', entity_id: 'SYNTHETIC_PRIVATE_SENTINEL' }, handoff: { question: 'SYNTHETIC_PRIVATE_SENTINEL', mode: undefined as string | undefined, topic_id: undefined as string | undefined }, revision: 0 } }));
vi.mock('../../shell/navigation', () => ({ useNavigation: () => navigation }));
const request = vi.fn<typeof fetch>();
const topics = [{ id: 'T21', label: 'Kidney transplantation' }, { id: 'T19', label: 'Medicines and nephrotoxicity' }];
const tools = ['ncbi', 'brave', 'tavily', 'exa'];
let connections: { selected_tool: string | null; connections: Array<{ provider: string; enabled: boolean; configured: boolean; selected: boolean; daily_request_limit: number; daily_credit_limit: number; requests_used: number; credits_used: number; auth_status: string }> };
let job: { id: string; revision_id: string; state: string; phase: string; error_code: string | null; error_message: string | null };
let document: { id: string; title: string; source_id: string; status: string; reserved: boolean; active_revision: string | null; latest_revision: string; cleanup_pending: boolean; revisions: Array<{ id: string; status: string; passage_count: number }> };
function json(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } }); }
function result(topic = 'T21', provider = 'europe-pmc') { return { topic_id: topic, topic_label: topics.find(row => row.id === topic)!.label, provider, queried_at: '2026-10-04T12:00:00+00:00', records: [{ id: 'MED:10001', title: 'Synthetic public transplantation study', url: 'https://pubmed.ncbi.nlm.nih.gov/10001/', authors: 'Synthetic Author', publication_date: '2026-09-01', pmcid: 'PMC10001', pmid: '10001', doi: '10.0000/synthetic', open_access: true, retracted: null, article_types: ['Journal Article'], comment_corrections: [{ type: 'Erratum in', id: '10002', source: 'MED' }] }] }; }
function accepted(topic = 'T21') { return { topic_id: topic, article: { pmcid: 'PMC10001', licence: 'CC-BY-4.0', licence_url: 'https://creativecommons.org/licenses/by/4.0/', attribution: 'Synthetic Author' }, import: { document_id: document.id, revision_id: job.revision_id, status: 'queued', job: { ...job } }, replayed: false, latest_final_verified: false, content_reviewed: false }; }
const base = async (url: RequestInfo | URL, options?: RequestInit) => {
  if (url === '/api/v1/content/topics') return json(topics);
  if (url === '/api/v1/retrieval/connections') return json(connections);
  if (url === '/api/v1/retrieval/discover') { const body = JSON.parse(options!.body as string); return json(result(body.topic_id, body.provider)); }
  if (url === '/api/v1/retrieval/articles/import') return json(accepted(JSON.parse(options!.body as string).topic_id));
  if (url === '/api/v1/library/jobs/job_synthetic') return json(job);
  if (url === '/api/v1/library/documents/doc_synthetic') return json(document);
  if (String(url).startsWith('/api/v1/library/documents?')) return json({ documents: [], total: 0, counts: {}, offset: 0, limit: 25 });
  if (url === '/api/v1/library/capabilities') return json({ text_import: true, pdf_image_import: false, temporary_extraction: false });
  if (String(url).startsWith('/api/v1/library/collection/catalogue?')) return json({ entries: [], total: 0, offset: 0 });
  throw new Error('Unexpected synthetic request: ' + url);
};
beforeEach(() => {
  connections = { selected_tool: null, connections: ['europe-pmc', 'pubmed', ...tools].map(provider => ({ provider, enabled: !tools.includes(provider), configured: false, selected: false, daily_request_limit: 100, daily_credit_limit: 20, requests_used: 0, credits_used: 0, auth_status: 'not_checked' })) };
  job = { id: 'job_synthetic', revision_id: 'rev_synthetic', state: 'queued', phase: 'queued', error_code: null, error_message: null };
  document = { id: 'doc_synthetic', title: 'Synthetic public transplantation study', source_id: 'L03', status: 'ready', reserved: false, active_revision: 'rev_synthetic', latest_revision: 'rev_synthetic', cleanup_pending: false, revisions: [{ id: 'rev_synthetic', status: 'ready', passage_count: 2 }] };
  navigation.scope.kind = 'study';
  navigation.handoff.mode = navigation.handoff.topic_id = undefined; navigation.revision = 0;
  request.mockReset().mockImplementation(base);
  vi.stubGlobal('fetch', request);
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); delete window.renulus; });
async function ready(props: Parameters<typeof Discovery>[0] = {}) {
  const view = render(<Discovery {...props} />);
  await screen.findByText(/Today UTC: 0\/100/);
  return view;
}
async function discover(source = 'europe-pmc', topic = 'T21') {
  fireEvent.change(screen.getByLabelText('Literature topic'), { target: { value: topic } });
  fireEvent.change(screen.getByLabelText('Literature source'), { target: { value: source } });
  fireEvent.click(screen.getByRole('button', { name: 'Search literature' }));
  await screen.findByRole('article', { name: 'Synthetic public transplantation study' });
}
const callsTo = (path: string) => request.mock.calls.filter(([url]) => url === '/api/v1' + path);

describe('Library topic discovery', () => {
  it('mount reads only local topics and public status; searching is deliberate and key-free by default', async () => {
    connections.selected_tool = 'tavily';
    Object.assign(connections.connections.find(row => row.provider === 'tavily')!, { enabled: true, configured: true, selected: true });
    await ready();
    expect(request.mock.calls.map(([url]) => url).sort()).toEqual(['/api/v1/content/topics', '/api/v1/retrieval/connections']);
    expect((screen.getByRole('button', { name: 'Search literature' }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByLabelText('Literature source') as HTMLSelectElement).value).toBe('europe-pmc');
    expect(screen.queryByRole('textbox')).toBeNull();
    await discover();
    expect(JSON.parse(callsTo('/retrieval/discover')[0][1]!.body as string)).toEqual({ topic_id: 'T21', provider: 'europe-pmc', scope: { kind: 'study' }, limit: 5 });
    expect(JSON.stringify(request.mock.calls)).not.toContain('SYNTHETIC_PRIVATE_SENTINEL');
    expect(callsTo('/runtime/runs')).toHaveLength(0);
  });

  it('PubMed shows actual identifiers, source date and separate search timestamp without indexed claims', async () => {
    await ready(); await discover('pubmed');
    const article = screen.getByRole('article');
    expect(within(article).getByText('2026-09-01')).toBeTruthy();
    expect(within(article).getByText('10.0000/synthetic')).toBeTruthy();
    expect(within(article).getByText('10001')).toBeTruthy();
    expect(within(article).getByText('PMC10001')).toBeTruthy();
    expect(within(article).getByText(/Erratum in/)).toBeTruthy();
    expect(within(article).getByRole('link').getAttribute('href')).toBe('https://pubmed.ncbi.nlm.nih.gov/10001/');
    expect(screen.getByText(/Searched/).querySelector('time')?.dateTime).toBe('2026-10-04T12:00:00+00:00');
    expect(within(article).getByText('Discovery only')).toBeTruthy();
    expect(screen.queryByText('Indexed')).toBeNull();
    expect(screen.getByText(/do not establish reviewed evidence or the latest final guidance/)).toBeTruthy();
    expect(callsTo('/retrieval/discover')).toHaveLength(1);
  });

  it('Learn handoffs preselect only installed topics without searching and clear previous results on a new handoff', async () => {
    const view = await ready({ requestedTopicId: 'T21', handoffRevision: 1 });
    await waitFor(() => expect((screen.getByLabelText('Literature topic') as HTMLSelectElement).value).toBe('T21'));
    expect(callsTo('/retrieval/discover')).toHaveLength(0);
    await discover();
    view.rerender(<Discovery requestedTopicId="T19" handoffRevision={2} />);
    await waitFor(() => expect((screen.getByLabelText('Literature topic') as HTMLSelectElement).value).toBe('T19'));
    expect(screen.queryByRole('article')).toBeNull();
    expect(callsTo('/retrieval/discover')).toHaveLength(1);
    expect(callsTo('/retrieval/articles/import')).toHaveLength(0);
  });

  it('an invalid handoff is not reflected into UI or a network request', async () => {
    await ready({ requestedTopicId: 'SYNTHETIC_PRIVATE_SENTINEL', handoffRevision: 1 });
    await screen.findByText(/requested study topic is not installed/);
    expect((screen.getByLabelText('Literature topic') as HTMLSelectElement).value).toBe('');
    expect(screen.queryByText('SYNTHETIC_PRIVATE_SENTINEL')).toBeNull();
    expect(JSON.stringify(request.mock.calls)).not.toContain('SYNTHETIC_PRIVATE_SENTINEL');
    expect(callsTo('/retrieval/discover')).toHaveLength(0);
  });

  it('the Library mount opens Discovery from Learn even after viewing collected sources', async () => {
    const view = render(<LibraryPage />);
    await screen.findByLabelText('Literature topic');
    fireEvent.click(screen.getByRole('button', { name: 'Collected sources' }));
    await screen.findByText('This collection has no catalogue records yet');
    navigation.handoff.mode = 'discover'; navigation.handoff.topic_id = 'T19'; navigation.revision = 1;
    view.rerender(<LibraryPage />);
    const selector = await screen.findByLabelText('Literature topic');
    await waitFor(() => expect((selector as HTMLSelectElement).value).toBe('T19'));
    expect(screen.queryByText('This collection has no catalogue records yet')).toBeNull();
    expect(callsTo('/retrieval/discover')).toHaveLength(0);
    expect(JSON.stringify(request.mock.calls)).not.toContain('SYNTHETIC_PRIVATE_SENTINEL');
  });

  it('binds an optional search to the displayed selected provider; a failure refreshes usage with no fallback', async () => {
    connections.selected_tool = 'tavily';
    Object.assign(connections.connections.find(row => row.provider === 'tavily')!, { enabled: true, configured: true, selected: true });
    request.mockImplementation(async (url, options) => {
      if (url === '/api/v1/retrieval/discover') {
        Object.assign(connections.connections.find(row => row.provider === 'tavily')!, { requests_used: 1, credits_used: 1, auth_status: 'retrieval_authentication_required' });
        return json({ error: { code: 'retrieval_authentication_required', message: 'Synthetic tool permission failure.', retryable: false } }, 401);
      }
      return base(url, options);
    });
    await ready();
    fireEvent.change(screen.getByLabelText('Literature topic'), { target: { value: 'T21' } });
    fireEvent.change(screen.getByLabelText('Literature source'), { target: { value: 'tavily' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search literature' }));
    await screen.findByText('Synthetic tool permission failure.');
    await screen.findByText(/Today UTC: 1\/100 requests attempted · 1\/20 credit units. Check key permissions/);
    expect(JSON.parse(callsTo('/retrieval/discover')[0][1]!.body as string).provider).toBe('tavily');
    expect(callsTo('/retrieval/discover')).toHaveLength(1);
    expect(callsTo('/retrieval/connections')).toHaveLength(2);
  });

  it('a changed optional selection demands another choice rather than silently charging the replacement', async () => {
    connections.selected_tool = 'tavily';
    Object.assign(connections.connections.find(row => row.provider === 'tavily')!, { enabled: true, configured: true, selected: true });
    request.mockImplementation(async (url, options) => {
      if (url === '/api/v1/retrieval/discover') {
        connections.selected_tool = 'exa';
        connections.connections.find(row => row.provider === 'tavily')!.selected = false;
        Object.assign(connections.connections.find(row => row.provider === 'exa')!, { enabled: true, configured: true, selected: true });
        return json({ error: { code: 'retrieval_connection_changed', message: 'Synthetic selection changed.', retryable: false } }, 409);
      }
      return base(url, options);
    });
    await ready();
    fireEvent.change(screen.getByLabelText('Literature topic'), { target: { value: 'T21' } });
    fireEvent.change(screen.getByLabelText('Literature source'), { target: { value: 'tavily' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search literature' }));
    await screen.findByText(/The selected tool changed/);
    expect((screen.getByLabelText('Literature source') as HTMLSelectElement).value).toBe('tavily');
    expect((screen.getByRole('button', { name: 'Search literature' }) as HTMLButtonElement).disabled).toBe(true);
    expect(callsTo('/retrieval/discover')).toHaveLength(1);
  });

  it('does not search for an uninstalled topic or accept another topic in a response', async () => {
    request.mockImplementation(async (url, options) => url === '/api/v1/retrieval/discover' ? json(result('T19')) : base(url, options));
    await ready();
    fireEvent.change(screen.getByLabelText('Literature topic'), { target: { value: 'UNKNOWN_PATIENT_QUERY' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search literature' }));
    expect(callsTo('/retrieval/discover')).toHaveLength(0);
    fireEvent.change(screen.getByLabelText('Literature topic'), { target: { value: 'T21' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search literature' }));
    await screen.findByText(/result does not match the selected topic/);
    expect(screen.queryByRole('article')).toBeNull();
  });

  it('changing topics aborts stale search work and discards even a delayed JSON body', async () => {
    let release!: (value: unknown) => void;
    request.mockImplementation(async (url, options) => {
      if (url === '/api/v1/retrieval/discover') {
        const response = json({});
        response.json = () => new Promise(resolve => { release = resolve; });
        return response;
      }
      return base(url, options);
    });
    await ready();
    fireEvent.change(screen.getByLabelText('Literature topic'), { target: { value: 'T21' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search literature' }));
    await waitFor(() => expect(release).toBeTypeOf('function'));
    fireEvent.change(screen.getByLabelText('Literature topic'), { target: { value: 'T19' } });
    await act(async () => release(result()));
    expect(screen.queryByRole('article')).toBeNull();
    expect(callsTo('/retrieval/articles/import')).toHaveLength(0);
    expect((screen.getByLabelText('Literature topic') as HTMLSelectElement).value).toBe('T19');
  });

  it('changing to a blocked context unmounts the panel and aborts its outstanding request', async () => {
    let release!: (value: Response) => void;
    request.mockImplementation(async (url, options) => url === '/api/v1/retrieval/discover' ? await new Promise<Response>(resolve => { release = resolve; }) : base(url, options));
    const view = await ready();
    fireEvent.change(screen.getByLabelText('Literature topic'), { target: { value: 'T21' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search literature' }));
    await waitFor(() => expect(release).toBeTypeOf('function'));
    const signal = callsTo('/retrieval/discover')[0][1]!.signal!;
    view.rerender(<Discovery blocked />);
    expect(signal.aborted).toBe(true);
    await act(async () => release(json(result())));
    expect(screen.queryByLabelText('Literature topic')).toBeNull();
    expect(screen.queryByRole('article')).toBeNull();
  });

  it.each(['temporary-case', 'saved-case', 'unclassified', 'reviewed-assessment', 'generated-practice'])('mounted Library keeps %s discovery inactive with no case/question egress', async kind => {
    navigation.scope.kind = kind;
    render(<LibraryPage />);
    await screen.findByText(/Literature discovery is available in a fresh study context/);
    await screen.findByText('Build a library you can return to');
    expect(callsTo('/content/topics')).toHaveLength(0);
    expect(callsTo('/retrieval/connections')).toHaveLength(0);
    expect(callsTo('/retrieval/discover')).toHaveLength(0);
    expect(JSON.stringify(request.mock.calls)).not.toContain('SYNTHETIC_PRIVATE_SENTINEL');
  });

  it('eligible import progresses from queued through processing to a verified active revision before Indexed', async () => {
    const onLibraryChange = vi.fn(), onInspect = vi.fn();
    await ready({ onLibraryChange, onInspect }); await discover();
    vi.useFakeTimers();
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Add eligible text' })));
    expect(screen.getByText('Queued for import')).toBeTruthy();
    expect(callsTo('/library/jobs/job_synthetic')).toHaveLength(1);
    expect(screen.queryByText('Indexed')).toBeNull();
    expect(JSON.parse(callsTo('/retrieval/articles/import')[0][1]!.body as string)).toEqual({ topic_id: 'T21', pmcid: 'PMC10001', scope: { kind: 'personal-library' }, idempotency_key: expect.any(String) });
    job.state = job.phase = 'processing';
    await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
    expect(screen.getByText('Processing')).toBeTruthy();
    job.state = job.phase = 'ready';
    await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
    expect(screen.getByText('Indexed')).toBeTruthy();
    expect(screen.getByText(/Passages are available in library search/)).toBeTruthy();
    expect(callsTo('/library/documents/doc_synthetic').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: 'Inspect library source' }));
    expect(onInspect).toHaveBeenCalledWith(document);
    expect(onLibraryChange.mock.calls.length).toBeGreaterThanOrEqual(2);
  }, 12000);

  it.each(['no-passages', 'different-revision', 'reserved'])('a ready job with %s cannot claim Indexed', async condition => {
    job.state = job.phase = 'ready';
    if (condition === 'no-passages') document.revisions[0].passage_count = 0;
    if (condition === 'different-revision') document.active_revision = 'rev_other';
    if (condition === 'reserved') document.reserved = true;
    await ready(); await discover();
    fireEvent.click(screen.getByRole('button', { name: 'Add eligible text' }));
    await screen.findByText('Index not confirmed');
    await waitFor(() => expect(callsTo('/library/documents/doc_synthetic')).toHaveLength(1));
    expect(screen.queryByText('Indexed')).toBeNull();
    expect(screen.getByText(/Passage availability is not confirmed yet/)).toBeTruthy();
  });

  it('a removed document in the refreshed library list loses its Indexed marker', async () => {
    job.state = job.phase = 'ready';
    const view = await ready(); await discover();
    fireEvent.click(screen.getByRole('button', { name: 'Add eligible text' }));
    await screen.findByText('Indexed');
    view.rerender(<Discovery libraryDocuments={[]} />);
    expect(screen.queryByText('Indexed')).toBeNull();
    expect(screen.getByText('Index not confirmed')).toBeTruthy();
  });

  it('licence rejection writes no indexed claim or job and a deliberate retry keeps its replay key', async () => {
    let attempt = 0;
    request.mockImplementation(async (url, options) => url === '/api/v1/retrieval/articles/import' && ++attempt === 1
      ? json({ error: { code: 'article_permission_required', message: 'Synthetic licence is restricted.', retryable: false } }, 403) : base(url, options));
    await ready(); await discover();
    fireEvent.click(screen.getByRole('button', { name: 'Add eligible text' }));
    await screen.findByText('Synthetic licence is restricted.');
    expect(screen.queryByText('Indexed')).toBeNull();
    expect(callsTo('/library/jobs/job_synthetic')).toHaveLength(0);
    fireEvent.click(screen.getByRole('button', { name: 'Retry eligible text import' }));
    await screen.findByText('Queued for import');
    const bodies = callsTo('/retrieval/articles/import').map(([, options]) => JSON.parse(options!.body as string));
    expect(bodies).toHaveLength(2);
    expect(bodies[0].idempotency_key).toBe(bodies[1].idempotency_key);
  });

  it('job-status failure stays visible and status retry is local, without refetching article text', async () => {
    let checks = 0;
    request.mockImplementation(async (url, options) => url === '/api/v1/library/jobs/job_synthetic' && ++checks === 1
      ? json({ error: { code: 'unavailable', message: 'Synthetic status unavailable.', retryable: true } }, 503) : base(url, options));
    await ready(); await discover();
    fireEvent.click(screen.getByRole('button', { name: 'Add eligible text' }));
    await screen.findByText('Synthetic status unavailable.');
    job.state = job.phase = 'ready';
    fireEvent.click(screen.getByRole('button', { name: 'Check import status' }));
    await screen.findByText('Indexed');
    expect(callsTo('/retrieval/articles/import')).toHaveLength(1);
    expect(callsTo('/retrieval/discover')).toHaveLength(1);
    expect(callsTo('/library/jobs/job_synthetic')).toHaveLength(2);
  });

  it('indexing failure shows the real error without retrying the public route', async () => {
    job.state = job.phase = 'failed'; job.error_message = 'Synthetic indexing failure.'; job.error_code = 'index_unavailable';
    await ready(); await discover();
    fireEvent.click(screen.getByRole('button', { name: 'Add eligible text' }));
    await screen.findByText('Import failed');
    expect(screen.getByText('Synthetic indexing failure.')).toBeTruthy();
    expect(screen.queryByText('Indexed')).toBeNull();
    expect(callsTo('/retrieval/articles/import')).toHaveLength(1);
    expect(callsTo('/library/jobs/job_synthetic')).toHaveLength(0);
  });

  it('reported retractions and records without a PMCID have no import action', async () => {
    request.mockImplementation(async (url, options) => url === '/api/v1/retrieval/discover'
      ? json({ ...result(), records: [{ ...result().records[0], retracted: true }, { id: 'WEB:1', title: 'Synthetic discovery link', url: 'https://example.org/article', publication_date: null }] }) : base(url, options));
    await ready(); await discover();
    expect(screen.getByText('Retraction reported · import blocked')).toBeTruthy();
    expect(screen.getByText('Date not supplied')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Add eligible text' })).toBeNull();
  });

  it.each(['javascript:alert(1)', 'http://example.org/article', 'https://127.0.0.1/article', 'https://172.16.1.1/article', 'https://169.254.169.254/article', 'https://[::1]/article', 'https://private.internal/article', 'https://user:password@example.org/article'])('keeps unsafe source address %s inert', async url => {
    request.mockImplementation(async (path, options) => path === '/api/v1/retrieval/discover'
      ? json({ ...result(), records: [{ ...result().records[0], url }] }) : base(path, options));
    const openSource = vi.fn(async () => {});
    await ready({ openSource }); await discover();
    expect(screen.queryByRole('link')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Copy source link' })).toBeNull();
    expect(openSource).not.toHaveBeenCalled();
  });

  it('a mismatched job acknowledgement cannot publish another revision as Indexed', async () => {
    request.mockImplementation(async (url, options) => url === '/api/v1/library/jobs/job_synthetic'
      ? json({ ...job, revision_id: 'rev_another', state: 'ready' }) : base(url, options));
    await ready(); await discover();
    fireEvent.click(screen.getByRole('button', { name: 'Add eligible text' }));
    await screen.findByText(/library returned a different import job/);
    expect(screen.queryByText('Indexed')).toBeNull();
    expect(callsTo('/library/documents/doc_synthetic')).toHaveLength(0);
  });

  it('uses the public native bridge only for deliberate clicks; clipboard failure leaves a selectable address', async () => {
    const openSource = vi.fn(async () => {}), openAuthorization = vi.fn();
    Object.defineProperty(window, 'renulus', { value: { openSource, openAuthorization }, configurable: true });
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: vi.fn(async () => { throw new Error('Synthetic clipboard denial'); }) }, configurable: true });
    await ready(); await discover();
    expect(openSource).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('link', { name: 'Synthetic public transplantation study' }));
    await waitFor(() => expect(openSource).toHaveBeenCalledWith('https://pubmed.ncbi.nlm.nih.gov/10001/'));
    expect(openAuthorization).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Copy source link' }));
    await screen.findByText(/Copying is unavailable/);
    expect(screen.getByText('https://pubmed.ncbi.nlm.nih.gov/10001/')).toBeTruthy();
    expect(request.mock.calls.every(([url]) => String(url).startsWith('/api/v1/'))).toBe(true);
  });
});
