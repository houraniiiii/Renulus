// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ConnectionsPage } from './ConnectionsPage';

type Provider = 'codex' | 'opencode-go';
type Availability = 'unknown' | 'available' | 'unavailable' | 'account_unsupported';
type Capability = 'unknown' | 'supported' | 'account_unsupported';
interface Model { id: string; availability: Availability; text_input: Capability; image_input: Capability }
interface Connection { provider: Provider; status: string; allowed_models: string[]; models: Model[]; learning_use?: { status: string; generation_allowed: boolean } }
interface Connections { selected_provider: Provider | null; selected_models?: Partial<Record<Provider, string | null>>; connections: Connection[] }
const approved = { codex: ['gpt-6.1-sol', 'gpt-6-astra', 'gpt-6-luna'], 'opencode-go': ['mimo-v2.6-pro', 'deepseek-v4.1-flash'] };
const authorization = 'https://auth.openai.com/api/accounts/authorize?state=SYNTHETIC';
const loginPath = '/api/v1/connections/codex/login/synthetic-login';
const request = vi.fn<typeof fetch>();
const openAuthorization = vi.fn(async (_url: string) => {});
const openSource = vi.fn(async (_url: string) => {});
const unexpected: string[] = [];
let current: Connections;
let start: () => Response | Promise<Response>;
let status: (id: string) => Response | Promise<Response>;
let cancel: (id: string) => Response | Promise<Response>;
let go: () => Response | Promise<Response>;
let refresh: (provider: Provider) => Response | Promise<Response>;
let disconnect: (provider: Provider) => Response | Promise<Response>;
let publicUnavailable: boolean;

function connection(provider: Provider, state = 'disconnected'): Connection {
  return { provider, status: state, allowed_models: approved[provider], models: approved[provider].map(id => ({
    id, availability: provider === 'codex' && state !== 'disconnected' ? 'available' : state === 'connected' ? 'available' : state === 'no_allowed_models' ? 'unavailable' : 'unknown',
    text_input: state === 'no_allowed_models' ? 'account_unsupported' : 'unknown', image_input: state === 'no_allowed_models' ? 'account_unsupported' : 'unknown',
  })) };
}
function setConnection(provider: Provider, state: string) {
  current.connections = current.connections.map(item => item.provider === provider ? connection(provider, state) : item);
}
function json(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } }); }
function failure(code: string, message = 'Synthetic connection check failed.', status = 503) { return json({ error: { code, message, retryable: true } }, status); }
function calls(path: string, method = 'GET') { return request.mock.calls.filter(([url, options]) => url === path && (options?.method ?? 'GET') === method); }
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(done => { resolve = done; }); return { promise, resolve }; }
async function mount() { const view = render(<ConnectionsPage />); await screen.findByRole('region', { name: 'Codex subscription' }); return view; }
async function beginLogin() {
  fireEvent.click(screen.getByRole('button', { name: /Continue with ChatGPT/ }));
  await screen.findByRole('button', { name: 'Cancel sign-in' });
  await waitFor(() => expect((screen.getByRole('button', { name: 'Cancel sign-in' }) as HTMLButtonElement).disabled).toBe(false));
}
function subscription(provider: Provider) { return within(screen.getByRole('region', { name: (provider === 'codex' ? 'Codex' : 'OpenCode Go') + ' subscription' })); }

beforeEach(() => {
  request.mockReset(); openAuthorization.mockReset(); openSource.mockReset(); unexpected.length = 0;
  openAuthorization.mockResolvedValue(); openSource.mockResolvedValue(); publicUnavailable = false;
  current = { selected_provider: null, connections: [connection('codex'), connection('opencode-go')] };
  start = () => json({ login_id: 'synthetic-login', status: 'pending', authorization_url: authorization, expires_at: Math.floor(Date.now() / 1000) + 600 });
  status = id => json({ login_id: id, status: 'pending' });
  cancel = id => json({ login_id: id, status: 'cancelled' });
  go = () => { setConnection('opencode-go', 'connected'); return json(current); };
  refresh = () => json(current);
  disconnect = provider => { setConnection(provider, 'disconnected'); if (current.selected_provider === provider) current.selected_provider = null; return json(current); };
  request.mockImplementation(async (url, options) => {
    const method = options?.method ?? 'GET';
    if (url === '/api/v1/health') return publicUnavailable ? failure('unavailable') : json({ version: 'synthetic', api_version: 1 });
    if (url === '/api/v1/connections') return publicUnavailable ? failure('unavailable') : json(current);
    if (url === '/api/v1/connections/codex/login' && method === 'POST') return start();
    const loginMatch = String(url).match(/^\/api\/v1\/connections\/codex\/login\/([^/]+)$/);
    if (loginMatch && method === 'GET') return status(decodeURIComponent(loginMatch[1]));
    if (loginMatch && method === 'DELETE') return cancel(decodeURIComponent(loginMatch[1]));
    if (url === '/api/v1/connections/opencode-go' && method === 'POST') return go();
    if (url === '/api/v1/connections/select' && method === 'POST') {
      const body = JSON.parse(options!.body as string); current.selected_provider = body.provider;
      current.selected_models = { ...current.selected_models, [body.provider]: body.model ?? null }; return json(current);
    }
    const providerMatch = String(url).match(/^\/api\/v1\/connections\/(codex|opencode-go)(\/refresh)?$/);
    if (providerMatch && providerMatch[2] && method === 'POST') return refresh(providerMatch[1] as Provider);
    if (providerMatch && !providerMatch[2] && method === 'DELETE') return disconnect(providerMatch[1] as Provider);
    unexpected.push(String(url)); throw new Error('Unexpected synthetic request: ' + url);
  });
  vi.stubGlobal('fetch', request);
  window.renulus = { openAuthorization, openSource, version: async () => 'synthetic' };
});

afterEach(() => {
  cleanup(); vi.useRealTimers(); delete window.renulus; vi.unstubAllGlobals(); vi.restoreAllMocks();
  expect(unexpected).toEqual([]);
  expect(request.mock.calls.every(([url]) => String(url).startsWith('/api/v1/'))).toBe(true);
  expect(request.mock.calls.some(([url]) => /runtime\/runs|generation|completions|credentials|auth\.json/.test(String(url)))).toBe(false);
});

describe('subscription status and explicit model selection', () => {
  it('loads only public subscription status, with all five approved identities honestly unchecked', async () => {
    await mount();
    expect(screen.getAllByText('Not connected')).toHaveLength(2);
    expect(screen.queryByText('Selected')).toBeNull();
    expect(screen.getAllByText('Connect account')).toHaveLength(5);
    Object.values(approved).flat().forEach(id => expect(screen.getByText(id)).toBeTruthy());
    expect(request.mock.calls.map(([url]) => url)).toEqual(['/api/v1/health', '/api/v1/connections']);
    expect(screen.queryByRole('button', { name: /^Use / })).toBeNull();
  });
  it.each(['configured', 'no_allowed_models', 'authentication_required', 'provider_unavailable', 'subscription_limit'])('keeps refresh and disconnect available for a %s saved account', async state => {
    setConnection('codex', state); await mount();
    expect(subscription('codex').getByRole('button', { name: 'Check models' })).toBeTruthy();
    expect(subscription('codex').getByRole('button', { name: 'Disconnect' })).toBeTruthy();
    expect(subscription('codex').getByRole('button', { name: 'Use Codex' })).toBeTruthy();
    expect(subscription('codex').queryByText('Account connected')).toBeNull();
  });
  it('shows catalogue absence and account rejections separately from accepted input requests', async () => {
    setConnection('codex', 'connected');
    current.connections[0].models[0] = { id: approved.codex[0], availability: 'account_unsupported', text_input: 'account_unsupported', image_input: 'account_unsupported' };
    current.connections[0].models[1] = { id: approved.codex[1], availability: 'unavailable', text_input: 'account_unsupported', image_input: 'account_unsupported' };
    current.connections[0].models[2] = { id: approved.codex[2], availability: 'available', text_input: 'supported', image_input: 'supported' };
    current.connections[0].models.push({ id: 'UNAPPROVED_SYNTHETIC_MODEL', availability: 'available', text_input: 'supported', image_input: 'supported' });
    await mount();
    expect(screen.getByText('Account rejected this model')).toBeTruthy();
    expect(screen.getByText('Unavailable')).toBeTruthy();
    expect(screen.getByText('Text and image input.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Check image input/ })).toBeNull();
    expect(screen.queryByText('UNAPPROVED_SYNTHETIC_MODEL')).toBeNull();
  });
  it('does not offer selection when every listed model was rejected by the account', async () => {
    setConnection('codex', 'connected');
    current.connections[0].models.forEach(model => { model.availability = 'account_unsupported'; });
    await mount();
    expect(subscription('codex').queryByRole('button', { name: 'Use Codex' })).toBeNull();
    expect(subscription('codex').getByRole('button', { name: 'Check models' })).toBeTruthy();
  });
  it('checks the catalogue and selects only on the separate explicit Use action', async () => {
    setConnection('codex', 'configured'); setConnection('opencode-go', 'connected'); current.selected_provider = 'opencode-go';
    refresh = provider => { setConnection(provider, 'connected'); return json(current); };
    await mount(); fireEvent.click(subscription('codex').getByRole('button', { name: 'Check models' }));
    const use = await screen.findByRole('button', { name: 'Use Codex' });
    expect(current.selected_provider).toBe('opencode-go'); expect(calls('/api/v1/connections/select', 'POST')).toHaveLength(0);
    expect(screen.getByText('Codex connection checked.')).toBeTruthy();
    fireEvent.click(use);
    await waitFor(() => expect(current.selected_provider).toBe('codex'));
    expect(JSON.parse(calls('/api/v1/connections/select', 'POST')[0][1]!.body as string)).toEqual({ provider: 'codex' });
  });
  it('selects the exact approved default without an image probe or generation request', async () => {
    setConnection('codex', 'configured'); current.selected_provider = 'codex'; await mount();
    const field = screen.getByLabelText('Default Codex model');
    expect(Array.from(field.querySelectorAll('option')).map(option => option.value)).toEqual(['automatic', ...approved.codex]);
    fireEvent.change(field, { target: { value: 'gpt-6.1-sol' } });
    await waitFor(() => expect((screen.getByLabelText('Default Codex model') as HTMLSelectElement).value).toBe('gpt-6.1-sol'));
    expect(JSON.parse(calls('/api/v1/connections/select', 'POST')[0][1]!.body as string)).toEqual({ provider: 'codex', model: 'gpt-6.1-sol' });
    expect(screen.queryByRole('button', { name: /Check image input/ })).toBeNull();
  });
  it('retries the failed catalogue operation, rather than merely reloading public status', async () => {
    setConnection('codex', 'configured'); let attempts = 0;
    refresh = provider => { if (++attempts === 1) return failure('provider_unavailable'); setConnection(provider, 'connected'); return json(current); };
    await mount(); fireEvent.click(subscription('codex').getByRole('button', { name: 'Check models' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Try again' }));
    await screen.findByRole('button', { name: 'Use Codex' });
    expect(calls('/api/v1/connections/codex/refresh', 'POST')).toHaveLength(2);
    expect(current.selected_provider).toBeNull();
  });
  it('shows local disconnection and failed remote revocation without switching to another account', async () => {
    setConnection('codex', 'connected'); setConnection('opencode-go', 'connected'); current.selected_provider = 'codex';
    disconnect = provider => { setConnection(provider, 'disconnected'); current.selected_provider = null; return json({ ...current, revocation: 'failed', recovery: "Remove Renulus in your ChatGPT account's connected apps." }); };
    await mount(); fireEvent.click(subscription('codex').getByRole('button', { name: 'Disconnect' }));
    await screen.findByText(/ChatGPT access could not be revoked/);
    expect(screen.getByText(/Remove Renulus in your ChatGPT account's connected apps/)).toBeTruthy();
    await screen.findByText(/No subscription selected/);
    expect(subscription('codex').getByText('Not connected')).toBeTruthy();
    expect(calls('/api/v1/connections/select', 'POST')).toHaveLength(0);
  });
  it('keeps the local runtime error honest and supports a public-status retry', async () => {
    publicUnavailable = true; render(<ConnectionsPage />);
    await screen.findByText('Connections could not be loaded');
    expect(screen.queryByText('Account connected')).toBeNull(); expect(screen.queryByText('Selected')).toBeNull();
    publicUnavailable = false; fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await screen.findByRole('region', { name: 'Codex subscription' });
    expect(screen.getAllByText('Not connected')).toHaveLength(2);
  });
});

describe('explicit OpenCode Go access', () => {
  it.each([
    undefined,
    { status: 'unresolved', generation_allowed: false },
    { status: 'unsupported', generation_allowed: false },
    { status: 'confirmed', generation_allowed: false },
  ])('keeps account availability separate from learning eligibility: %j', async learning_use => {
    setConnection('opencode-go', 'connected'); current.selected_provider = 'opencode-go';
    current.connections[1].learning_use = learning_use;
    await mount();
    const section = subscription('opencode-go');
    expect(section.getByText('Account connected')).toBeTruthy();
    expect(section.getByText('Selected')).toBeTruthy();
    expect(section.getByText('Learning requests paused.')).toBeTruthy();
    expect(screen.getByText(/remains selected, but learning requests are paused/)).toBeTruthy();
    expect(section.queryByRole('button', { name: 'Use OpenCode Go' })).toBeNull();
    expect(section.getByRole('button', { name: 'Check models' })).toBeTruthy();
    expect(section.getByRole('button', { name: 'Disconnect' })).toBeTruthy();
    expect(section.getByRole('link', { name: 'Read the Go usage policy' }).getAttribute('href')).toBe('https://opencode.ai/docs/go/');
    expect(calls('/api/v1/connections/select', 'POST')).toHaveLength(0);
    expect(openSource).not.toHaveBeenCalled();
  });
  it('requires explicit selection even with hypothetical confirmed learning eligibility', async () => {
    setConnection('opencode-go', 'connected');
    current.connections[1].learning_use = { status: 'confirmed', generation_allowed: true };
    await mount();
    expect(subscription('opencode-go').getByRole('button', { name: 'Use OpenCode Go' })).toBeTruthy();
    expect(subscription('opencode-go').queryByText('Learning requests paused.')).toBeNull();
    expect(current.selected_provider).toBeNull();
    expect(calls('/api/v1/connections/select', 'POST')).toHaveLength(0);
  });
  it('clears the entered key immediately, saves nothing in browser storage, and never auto-selects', async () => {
    const storage = vi.spyOn(Storage.prototype, 'setItem'); const held = deferred<Response>(); go = () => held.promise;
    await mount(); const field = screen.getByLabelText('OpenCode Go key') as HTMLInputElement;
    fireEvent.change(field, { target: { value: '  SYNTHETIC_KEY_ONLY  ' } });
    fireEvent.click(screen.getByRole('button', { name: /Check and save Go key/ }));
    expect(field.value).toBe('');
    expect(JSON.parse(calls('/api/v1/connections/opencode-go', 'POST')[0][1]!.body as string)).toEqual({ api_key: 'SYNTHETIC_KEY_ONLY', select: false });
    setConnection('opencode-go', 'connected'); await act(async () => { held.resolve(json(current)); });
    await screen.findByText(/OpenCode Go key saved and catalogue checked/);
    expect(subscription('opencode-go').queryByRole('button', { name: 'Use OpenCode Go' })).toBeNull();
    expect(storage).not.toHaveBeenCalled(); expect(current.selected_provider).toBeNull();
  });
  it('requires fresh key entry after failure, with no retry closure or subscription fallback', async () => {
    setConnection('codex', 'connected'); current.selected_provider = 'codex'; go = () => failure('authentication_required', 'The synthetic subscription key was rejected.', 401);
    await mount(); const field = screen.getByLabelText('OpenCode Go key') as HTMLInputElement;
    fireEvent.change(field, { target: { value: 'SYNTHETIC_REJECTED_KEY' } }); fireEvent.click(screen.getByRole('button', { name: /Check and save Go key/ }));
    await screen.findByText('The synthetic subscription key was rejected.');
    expect(screen.getByText(/The previous entry has been cleared/)).toBeTruthy(); expect(field.value).toBe('');
    expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull();
    expect((screen.getByRole('button', { name: /Check and save Go key/ }) as HTMLButtonElement).disabled).toBe(true);
    expect(calls('/api/v1/connections/opencode-go', 'POST')).toHaveLength(1); expect(current.selected_provider).toBe('codex');
  });
  it('reports a saved key with no approved catalogue as unavailable for learning', async () => {
    go = () => { setConnection('opencode-go', 'no_allowed_models'); return json(current); };
    await mount(); fireEvent.change(screen.getByLabelText('OpenCode Go key'), { target: { value: 'SYNTHETIC_EMPTY_CATALOGUE' } });
    fireEvent.click(screen.getByRole('button', { name: /Check and save Go key/ }));
    await screen.findByText(/OpenCode Go key saved and catalogue checked/);
    expect(await subscription('opencode-go').findByText('No approved models')).toBeTruthy();
    expect(subscription('opencode-go').queryByRole('button', { name: 'Use OpenCode Go' })).toBeNull();
    expect(subscription('opencode-go').getByRole('button', { name: 'Disconnect' })).toBeTruthy();
  });
  it('opens the official account page only on an explicit click through the source bridge', async () => {
    await mount(); expect(openSource).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('link', { name: /Open OpenCode Go account/ }));
    await waitFor(() => expect(openSource).toHaveBeenCalledWith('https://opencode.ai/auth'));
    expect(request.mock.calls).toHaveLength(2);
  });
  it('does not let the Go account link interrupt an in-flight Codex login start', async () => {
    const held = deferred<Response>(); start = () => held.promise; await mount();
    fireEvent.click(screen.getByRole('button', { name: /Continue with ChatGPT/ }));
    const account = screen.getByRole('link', { name: /Open OpenCode Go account/ });
    expect(account.getAttribute('aria-disabled')).toBe('true'); fireEvent.click(account);
    expect(openSource).not.toHaveBeenCalled();
    expect(calls('/api/v1/connections/codex/login', 'POST')[0][1]!.signal!.aborted).toBe(false);
    await act(async () => { held.resolve(json({ login_id: 'synthetic-login', status: 'pending', authorization_url: authorization })); });
    await screen.findByRole('button', { name: 'Cancel sign-in' });
    expect(openAuthorization).toHaveBeenCalledWith(authorization); expect(calls(loginPath, 'DELETE')).toHaveLength(0);
  });
});

describe('Codex sign-in recovery and lifetime', () => {
  it('opens the native authorization bridge and cancels the app-owned attempt on exit', async () => {
    const view = await mount(); await beginLogin();
    expect(openAuthorization).toHaveBeenCalledWith(authorization);
    expect(JSON.parse(calls('/api/v1/connections/codex/login', 'POST')[0][1]!.body as string)).toEqual({ select: false });
    view.unmount();
    await waitFor(() => expect(calls(loginPath, 'DELETE')).toHaveLength(1));
    expect(calls(loginPath, 'DELETE')[0][1]!.keepalive).toBe(true);
  });
  it('does not cancel an explicitly cancelled attempt twice on exit', async () => {
    const view = await mount(); await beginLogin(); fireEvent.click(screen.getByRole('button', { name: 'Cancel sign-in' }));
    await screen.findByText('ChatGPT sign-in cancelled.'); view.unmount();
    expect(calls(loginPath, 'DELETE')).toHaveLength(1);
  });
  it('reopens the same attempt after a native browser failure without another login POST', async () => {
    openAuthorization.mockRejectedValueOnce(new Error('Synthetic OS browser failure'));
    await mount(); await beginLogin(); await screen.findByText(/The sign-in browser could not be opened/);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(openAuthorization).toHaveBeenCalledTimes(2));
    expect(openAuthorization.mock.calls[1][0]).toBe(authorization); expect(calls('/api/v1/connections/codex/login', 'POST')).toHaveLength(1);
    expect(screen.getByRole('button', { name: 'Cancel sign-in' })).toBeTruthy();
  });
  it('provides a validated explicit browser link without pretending it opened natively', async () => {
    delete window.renulus; await mount(); await beginLogin();
    const link = screen.getByRole('link', { name: 'Open sign-in in your browser' }) as HTMLAnchorElement;
    expect(link.href).toBe(authorization); expect(link.target).toBe('_blank'); expect(link.rel).toBe('noopener noreferrer');
    expect(openAuthorization).not.toHaveBeenCalled();
  });
  it.each(['http://auth.openai.com/api/accounts/authorize', 'https://auth.openai.com.evil.invalid/api/accounts/authorize', 'https://auth.openai.com/wrong-path', 'https://user@auth.openai.com/api/accounts/authorize', 'https://auth.openai.com:444/api/accounts/authorize', 'javascript:alert(1)'])('rejects an unsafe returned authorization link: %s', async url => {
    start = () => json({ login_id: 'synthetic-login', status: 'pending', authorization_url: url });
    await mount(); fireEvent.click(screen.getByRole('button', { name: /Continue with ChatGPT/ }));
    await screen.findByText(/invalid sign-in link/);
    expect(openAuthorization).not.toHaveBeenCalled(); expect(screen.queryByRole('button', { name: 'Cancel sign-in' })).toBeNull();
    expect(calls(loginPath, 'DELETE')).toHaveLength(1);
    expect([...document.querySelectorAll('a')].some(link => link.getAttribute('href') === url)).toBe(false);
  });
  it('polls pending through exchanging to connected, preserving expiry and requiring explicit selection', async () => {
    await mount(); vi.useFakeTimers();
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: /Continue with ChatGPT/ })); });
    status = id => json({ login_id: id, status: 'exchanging' });
    await act(async () => { await vi.advanceTimersByTimeAsync(1500); });
    expect(screen.getByText(/Renulus is finishing the account connection/)).toBeTruthy();
    expect(screen.getByText(/Sign-in expires at/)).toBeTruthy(); expect(screen.getByRole('button', { name: 'Cancel sign-in' })).toBeTruthy();
    expect((screen.getByRole('button', { name: 'Sources and retrieval' }) as HTMLButtonElement).disabled).toBe(true);
    setConnection('codex', 'connected'); status = id => json({ login_id: id, status: 'connected' });
    await act(async () => { await vi.advanceTimersByTimeAsync(1500); });
    expect(screen.queryByRole('button', { name: 'Cancel sign-in' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Use Codex' })).toBeTruthy();
    expect(calls(loginPath)).toHaveLength(2); expect(calls('/api/v1/connections/select', 'POST')).toHaveLength(0); expect(current.selected_provider).toBeNull();
  });
  it('cancels an exchanging attempt and ignores an already in-flight stale status', async () => {
    const view = await mount(); await beginLogin(); status = id => json({ login_id: id, status: 'exchanging' });
    fireEvent.click(screen.getByRole('button', { name: 'Check sign-in status' })); await screen.findByText(/Renulus is finishing the account connection/);
    const late = deferred<unknown>(); const delayed = json({}); delayed.json = () => late.promise; status = () => delayed;
    fireEvent.click(screen.getByRole('button', { name: 'Check sign-in status' }));
    await waitFor(() => expect(calls(loginPath)).toHaveLength(2));
    // Leaving the view while status JSON is delayed must still cancel exchanging.
    view.unmount(); await waitFor(() => expect(calls(loginPath, 'DELETE')).toHaveLength(1));
    await act(async () => { late.resolve({ login_id: 'synthetic-login', status: 'connected' }); });
    expect(calls('/api/v1/connections/select', 'POST')).toHaveLength(0);
  });
  it('keeps cancel visible after a polling failure and retries status, not registration', async () => {
    await mount(); vi.useFakeTimers(); await act(async () => { fireEvent.click(screen.getByRole('button', { name: /Continue with ChatGPT/ })); });
    status = () => failure('provider_unavailable');
    await act(async () => { await vi.advanceTimersByTimeAsync(1500); });
    expect(screen.getByRole('button', { name: 'Cancel sign-in' })).toBeTruthy();
    status = id => json({ login_id: id, status: 'pending' });
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Try again' })); });
    expect(calls(loginPath)).toHaveLength(2); expect(calls('/api/v1/connections/codex/login', 'POST')).toHaveLength(1);
    expect(screen.queryByRole('alert')).toBeNull(); expect(screen.getByRole('button', { name: 'Reopen sign-in in browser' })).toBeTruthy();
  });
  it('explicitly cancels during exchange and rejects late status JSON from the cancelled attempt', async () => {
    await mount(); vi.useFakeTimers(); await act(async () => { fireEvent.click(screen.getByRole('button', { name: /Continue with ChatGPT/ })); });
    status = id => json({ login_id: id, status: 'exchanging' });
    await act(async () => { await vi.advanceTimersByTimeAsync(1500); });
    const late = deferred<unknown>(); const delayed = json({}); delayed.json = () => late.promise; status = () => delayed;
    await act(async () => { await vi.advanceTimersByTimeAsync(1500); });
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Cancel sign-in' })); });
    await act(async () => { late.resolve({ login_id: 'synthetic-login', status: 'connected' }); });
    expect(screen.getByText('ChatGPT sign-in cancelled.')).toBeTruthy();
    expect(screen.queryByText(/sign-in completed/)).toBeNull(); expect(screen.queryByRole('button', { name: 'Cancel sign-in' })).toBeNull();
    expect(calls(loginPath, 'DELETE')).toHaveLength(1); expect(current.selected_provider).toBeNull();
  });
  it('automatically retries a transient poll failure while keeping the same login', async () => {
    await mount(); vi.useFakeTimers(); await act(async () => { fireEvent.click(screen.getByRole('button', { name: /Continue with ChatGPT/ })); });
    let attempts = 0; status = id => ++attempts === 1 ? failure('unavailable') : json({ login_id: id, status: 'pending' });
    await act(async () => { await vi.advanceTimersByTimeAsync(4500); });
    expect(attempts).toBe(2); expect(screen.queryByRole('alert')).toBeNull();
    expect(calls('/api/v1/connections/codex/login', 'POST')).toHaveLength(1);
  });
  it.each(['login_expired', 'login_not_found', 'login_declined'])('offers fresh sign-in after terminal %s instead of polling forever', async code => {
    await mount(); await beginLogin();
    status = id => code === 'login_not_found' ? failure(code, 'This login attempt is no longer active.', 404) : json({ login_id: id, status: 'error', error: { code, message: 'Synthetic sign-in ended.', retryable: true } });
    fireEvent.click(screen.getByRole('button', { name: 'Check sign-in status' }));
    await screen.findByRole('button', { name: 'Try again' }); expect(screen.queryByRole('button', { name: 'Cancel sign-in' })).toBeNull();
    start = () => json({ login_id: 'synthetic-login-2', status: 'pending', authorization_url: authorization });
    fireEvent.click(screen.getByRole('button', { name: 'Try again' })); await screen.findByRole('button', { name: 'Cancel sign-in' });
    expect(calls('/api/v1/connections/codex/login', 'POST')).toHaveLength(2); expect(current.selected_provider).toBeNull();
  });
  it.each([{ login_id: 'other-synthetic-attempt', status: 'connected' }, { login_id: 'synthetic-login', status: 'invented' }])('does not accept a mismatched or unknown login status: %j', async value => {
    await mount(); await beginLogin(); status = () => json(value);
    fireEvent.click(screen.getByRole('button', { name: 'Check sign-in status' })); await screen.findByText(/invalid sign-in status/);
    expect(screen.getByRole('button', { name: 'Cancel sign-in' })).toBeTruthy(); expect(screen.queryByText(/sign-in completed/)).toBeNull();
  });
  it('retries a failed cancel as DELETE and retains the visible attempt until cancellation succeeds', async () => {
    await mount(); await beginLogin(); let attempts = 0; cancel = id => ++attempts === 1 ? failure('unavailable') : json({ login_id: id, status: 'cancelled' });
    fireEvent.click(screen.getByRole('button', { name: 'Cancel sign-in' })); await screen.findByRole('button', { name: 'Try again' });
    expect(screen.getByRole('button', { name: 'Cancel sign-in' })).toBeTruthy(); fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await screen.findByText('ChatGPT sign-in cancelled.'); expect(calls(loginPath, 'DELETE')).toHaveLength(2);
  });
  it('keeps sign-in cancellation available independently of a public-status reload failure', async () => {
    await mount(); await beginLogin(); publicUnavailable = true; fireEvent.click(screen.getByRole('button', { name: 'Refresh status' }));
    await screen.findByText('Connections could not be loaded');
    fireEvent.click(screen.getByRole('button', { name: 'Cancel sign-in' })); await screen.findByText('ChatGPT sign-in cancelled.');
    expect(calls(loginPath, 'DELETE')).toHaveLength(1);
  });
  it('cancels a known login returned after unmount without opening a browser or losing its listener', async () => {
    const late = deferred<unknown>(); const response = json({}); response.json = () => late.promise; start = () => response;
    const view = await mount(); fireEvent.click(screen.getByRole('button', { name: /Continue with ChatGPT/ }));
    await waitFor(() => expect(calls('/api/v1/connections/codex/login', 'POST')).toHaveLength(1)); view.unmount();
    await act(async () => { late.resolve({ login_id: 'synthetic-login', status: 'pending', authorization_url: authorization }); });
    expect(openAuthorization).not.toHaveBeenCalled(); expect(calls(loginPath, 'DELETE')).toHaveLength(1);
    expect(calls(loginPath, 'DELETE')[0][1]!.keepalive).toBe(true);
  });
});
