// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { RetrievalConnections } from './RetrievalConnections';

const request = vi.fn<typeof fetch>();
const tools = ['ncbi', 'brave', 'tavily', 'exa'];
const topics = [{ id: 'T21', label: 'Transplantation' }, { id: 'T19', label: 'Dialysis' }];
let connections: { selected_tool: string | null; connections: Array<{ provider: string; enabled: boolean; configured: boolean; selected: boolean; daily_request_limit: number; daily_credit_limit: number; requests_used: number; credits_used: number; auth_status: string }> };
function json(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } }); }
function result(topic = 'T21') { return { topic_id: topic, topic_label: topics.find(row => row.id === topic)!.label, provider: 'europe-pmc', queried_at: '2026-10-04T12:00:00+00:00', records: [{ id: 'MED:10001', title: 'Synthetic public study', url: 'https://example.org/paper', pmcid: 'PMC10001', retracted: null }] }; }
const base = async (url: RequestInfo | URL, options?: RequestInit) => {
  if (url === '/api/v1/retrieval/connections') return json(connections);
  if (url === '/api/v1/content/topics') return json(topics);
  if (url === '/api/v1/retrieval/discover') return json(result(JSON.parse(options!.body as string).topic_id));
  if (url === '/api/v1/retrieval/articles/import') return json({ import: { status: 'queued' } });
  if (String(url).startsWith('/api/v1/retrieval/connections/') && options?.method === 'PUT') {
    const row = connections.connections.find(row => row.provider === String(url).split('/').at(-1))!;
    const body = JSON.parse(options.body as string);
    Object.assign(row, { enabled: body.enabled, configured: body.api_key ? true : row.configured });
    return json(connections);
  }
  if (url === '/api/v1/retrieval/connections/select') {
    connections.selected_tool = JSON.parse(options!.body as string).provider;
    return json(connections);
  }
  throw new Error('Unexpected synthetic request: ' + url);
};
beforeEach(() => {
  connections = { selected_tool: null, connections: ['europe-pmc', 'pubmed', ...tools].map(provider => ({ provider, enabled: !tools.includes(provider), configured: false, selected: false, daily_request_limit: 100, daily_credit_limit: 20, requests_used: 0, credits_used: 0, auth_status: 'not_checked' })) };
  request.mockReset().mockImplementation(base);
  vi.stubGlobal('fetch', request);
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

async function ready() {
  render(<RetrievalConnections />);
  await screen.findByLabelText('Study topic');
}

describe('Explicit topic discovery and retrieval connections', () => {
  it('mount only reads local state; discovery is a deliberate topic-only operation', async () => {
    await ready();
    expect(request.mock.calls.every(([url]) => ['/api/v1/retrieval/connections', '/api/v1/content/topics'].includes(String(url)))).toBe(true);
    expect((screen.getByRole('button', { name: 'Discover literature' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Study topic'), { target: { value: 'T21' } });
    fireEvent.click(screen.getByRole('button', { name: 'Discover literature' }));
    await screen.findByText('Synthetic public study');
    const call = request.mock.calls.find(([url]) => url === '/api/v1/retrieval/discover')!;
    expect(JSON.parse(call[1]!.body as string)).toEqual({ topic_id: 'T21', scope: { kind: 'study' }, provider: 'europe-pmc', limit: 5 });
    expect(screen.getByText(/They do not verify the latest final guidance/)).toBeTruthy();
    expect(request.mock.calls.every(([url]) => String(url).startsWith('/api/v1/'))).toBe(true);
  });

  it('clears a key on save, uses distinct enable/select controls and never checks a vendor on save', async () => {
    await ready();
    const field = screen.getByLabelText('Tavily key');
    fireEvent.change(field, { target: { value: 'SYNTHETIC_EXPLICIT_KEY' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save Tavily' }));
    await screen.findByText('Retrieval settings saved. No provider request was made.');
    expect((await screen.findByLabelText('Tavily key') as HTMLInputElement).value).toBe('');
    const call = request.mock.calls.find(([url, options]) => url === '/api/v1/retrieval/connections/tavily' && options?.method === 'PUT')!;
    expect(JSON.parse(call[1]!.body as string)).toEqual({ api_key: 'SYNTHETIC_EXPLICIT_KEY', enabled: false, daily_request_limit: 100, daily_credit_limit: 20 });
    expect(screen.queryByRole('button', { name: 'Select Tavily' })).toBeNull();
    fireEvent.click(screen.getByLabelText('Enable Tavily'));
    fireEvent.click(screen.getByRole('button', { name: 'Save Tavily' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Select Tavily' }));
    await waitFor(() => expect(connections.selected_tool).toBe('tavily'));
    expect(request.mock.calls.some(([url]) => String(url).includes('/discover'))).toBe(false);
    expect(JSON.stringify(window.localStorage)).not.toContain('SYNTHETIC_EXPLICIT_KEY');
  });

  it('shows quota/auth failure without falling back or publishing old results', async () => {
    request.mockImplementation(async (url, options) => url === '/api/v1/retrieval/discover'
      ? json({ error: { code: 'retrieval_daily_limit', message: 'Synthetic daily request cap reached.', retryable: false } }, 429)
      : base(url, options));
    await ready();
    fireEvent.change(screen.getByLabelText('Study topic'), { target: { value: 'T21' } });
    fireEvent.click(screen.getByRole('button', { name: 'Discover literature' }));
    await screen.findByText('Synthetic daily request cap reached.');
    expect(screen.queryByText('Synthetic public study')).toBeNull();
    expect(request.mock.calls.filter(([url]) => url === '/api/v1/retrieval/discover')).toHaveLength(1);
    expect((screen.getByLabelText('Discovery source') as HTMLSelectElement).value).toBe('europe-pmc');
  });

  it('refreshes actual usage and auth state after a failed explicit search', async () => {
    connections.selected_tool = 'tavily';
    Object.assign(connections.connections.find(row => row.provider === 'tavily')!, { enabled: true, configured: true, selected: true });
    request.mockImplementation(async (url, options) => {
      if (url === '/api/v1/retrieval/discover') {
        Object.assign(connections.connections.find(row => row.provider === 'tavily')!, { requests_used: 1, credits_used: 1, auth_status: 'retrieval_authentication_required' });
        return json({ error: { code: 'retrieval_authentication_required', message: 'Synthetic key permission failure.', retryable: false } }, 401);
      }
      return base(url, options);
    });
    await ready();
    fireEvent.change(screen.getByLabelText('Study topic'), { target: { value: 'T21' } });
    fireEvent.change(screen.getByLabelText('Discovery source'), { target: { value: 'selected-tool' } });
    fireEvent.click(screen.getByRole('button', { name: 'Discover literature' }));
    await screen.findByText('Synthetic key permission failure.');
    await screen.findByText('Today UTC: 1/100 requests attempted · 1/20 credits');
    expect(screen.getAllByText(/Check key permissions/).length).toBeGreaterThan(0);
    expect(request.mock.calls.filter(([url]) => url === '/api/v1/retrieval/discover')).toHaveLength(1);
    expect(request.mock.calls.filter(([url]) => url === '/api/v1/retrieval/connections')).toHaveLength(2);
  });

  it('changing the topic aborts stale work and never attaches an old article to the new topic', async () => {
    let release!: (value: Response) => void;
    request.mockImplementation(async (url, options) => url === '/api/v1/retrieval/discover'
      ? await new Promise<Response>(resolve => { release = resolve; })
      : base(url, options));
    await ready();
    fireEvent.change(screen.getByLabelText('Study topic'), { target: { value: 'T21' } });
    fireEvent.click(screen.getByRole('button', { name: 'Discover literature' }));
    await waitFor(() => expect(release).toBeTypeOf('function'));
    const call = request.mock.calls.find(([url]) => url === '/api/v1/retrieval/discover')!;
    fireEvent.change(screen.getByLabelText('Study topic'), { target: { value: 'T19' } });
    expect(call[1]!.signal!.aborted).toBe(true);
    release(json(result('T21')));
    await waitFor(() => expect((screen.getByRole('button', { name: 'Discover literature' }) as HTMLButtonElement).disabled).toBe(false));
    expect(screen.queryByText('Synthetic public study')).toBeNull();
    expect(request.mock.calls.some(([url]) => url === '/api/v1/retrieval/articles/import')).toBe(false);
  });

  it('explicit article import uses the result topic and reuses the retry key', async () => {
    await ready();
    fireEvent.change(screen.getByLabelText('Study topic'), { target: { value: 'T21' } });
    fireEvent.click(screen.getByRole('button', { name: 'Discover literature' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Add eligible full text' }));
    await screen.findByText(/library queue: queued/);
    fireEvent.click(await screen.findByRole('button', { name: 'Add eligible full text' }));
    await waitFor(() => expect(request.mock.calls.filter(([url]) => url === '/api/v1/retrieval/articles/import')).toHaveLength(2));
    const calls = request.mock.calls.filter(([url]) => url === '/api/v1/retrieval/articles/import').map(([, options]) => JSON.parse(options!.body as string));
    expect(calls[0]).toEqual({ topic_id: 'T21', pmcid: 'PMC10001', scope: { kind: 'personal-library' }, idempotency_key: expect.any(String) });
    expect(calls[1].idempotency_key).toBe(calls[0].idempotency_key);
  });

  it('reported retraction has no automatic import button', async () => {
    request.mockImplementation(async (url, options) => url === '/api/v1/retrieval/discover'
      ? json({ ...result(), records: [{ ...result().records[0], retracted: true }] }) : base(url, options));
    await ready();
    fireEvent.change(screen.getByLabelText('Study topic'), { target: { value: 'T21' } });
    fireEvent.click(screen.getByRole('button', { name: 'Discover literature' }));
    await screen.findByText('Retraction reported · import blocked');
    expect(screen.queryByRole('button', { name: 'Add eligible full text' })).toBeNull();
  });

  it('uses the parent public-source bridge only for an explicit article click', async () => {
    const openSource = vi.fn(async () => {});
    render(<RetrievalConnections openSource={openSource} />);
    fireEvent.change(await screen.findByLabelText('Study topic'), { target: { value: 'T21' } });
    fireEvent.click(screen.getByRole('button', { name: 'Discover literature' }));
    const link = await screen.findByRole('link', { name: 'Synthetic public study' });
    expect(openSource).not.toHaveBeenCalled();
    fireEvent.click(link);
    await waitFor(() => expect(openSource).toHaveBeenCalledWith('https://example.org/paper'));
    expect(request.mock.calls.some(([url]) => String(url).includes('/runtime/'))).toBe(false);
  });

  it('copy-link fallback makes no remote or model request', async () => {
    const writeText = vi.fn(async () => {});
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    await ready();
    fireEvent.change(screen.getByLabelText('Study topic'), { target: { value: 'T21' } });
    fireEvent.click(screen.getByRole('button', { name: 'Discover literature' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Copy source link' }));
    await screen.findByText('Source link copied.');
    expect(writeText).toHaveBeenCalledWith('https://example.org/paper');
    expect(request.mock.calls.every(([url]) => String(url).startsWith('/api/v1/'))).toBe(true);
  });
});
