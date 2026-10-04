// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ConnectionsPage } from './ConnectionsPage';

const authorization = 'https://auth.openai.com/api/accounts/authorize?state=SYNTHETIC';
const connections = { selected_provider: null, connections: [
  { provider: 'codex', status: 'disconnected', allowed_models: [], models: [] },
  { provider: 'opencode-go', status: 'disconnected', allowed_models: [], models: [] },
] };
const request = vi.fn<typeof fetch>();
const openAuthorization = vi.fn(async () => {});
function json(value: unknown) { return new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } }); }
beforeEach(() => {
  request.mockImplementation(async (url, options) => {
    if (url === '/api/v1/health') return json({ version: 'synthetic', api_version: 1 });
    if (url === '/api/v1/connections') return json(connections);
    if (url === '/api/v1/connections/codex/login' && options?.method === 'POST') return json({ login_id: 'synthetic-login', status: 'pending', authorization_url: authorization });
    if (url === '/api/v1/connections/codex/login/synthetic-login') return json({ login_id: 'synthetic-login', status: options?.method === 'DELETE' ? 'cancelled' : 'pending' });
    if (url === '/api/v1/connections/opencode-go' && options?.method === 'POST') return json({ status: 'connected' });
    throw new Error('Unexpected synthetic request: ' + url);
  });
  vi.stubGlobal('fetch', request);
  window.renulus = { openAuthorization, version: async () => 'synthetic' };
});
afterEach(() => { cleanup(); delete window.renulus; vi.unstubAllGlobals(); });

describe('Connections operations and OAuth lifetime', () => {
  it('reports the real disconnected response without inventing an active selection', async () => {
    render(<ConnectionsPage />);
    await screen.findByRole('button', { name: /Continue with ChatGPT/ });
    expect(screen.getAllByText('disconnected')).toHaveLength(2);
    expect(screen.queryByText('Selected')).toBeNull();
    expect(request.mock.calls.some(([url]) => String(url).includes('/runtime/runs'))).toBe(false);
  });
  it('opens the public authorization URL through the native bridge and cancels on exit', async () => {
    const view = render(<ConnectionsPage />);
    fireEvent.click(await screen.findByRole('button', { name: /Continue with ChatGPT/ }));
    await screen.findByRole('button', { name: 'Cancel sign-in' });
    expect(openAuthorization).toHaveBeenCalledWith(authorization);
    view.unmount();
    await waitFor(() => expect(request.mock.calls.some(([url, options]) => url === '/api/v1/connections/codex/login/synthetic-login' && options?.method === 'DELETE' && options.keepalive)).toBe(true));
  });
  it('ends an explicitly cancelled login without a duplicate cancellation on exit', async () => {
    const view = render(<ConnectionsPage />);
    fireEvent.click(await screen.findByRole('button', { name: /Continue with ChatGPT/ }));
    fireEvent.click(await screen.findByRole('button', { name: 'Cancel sign-in' }));
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Cancel sign-in' })).toBeNull());
    view.unmount();
    expect(request.mock.calls.filter(([, options]) => options?.method === 'DELETE')).toHaveLength(1);
  });
  it('clears an explicitly entered synthetic key and never auto-selects its provider', async () => {
    render(<ConnectionsPage />);
    const field = await screen.findByLabelText('OpenCode Go key');
    fireEvent.change(field, { target: { value: 'SYNTHETIC_KEY_ONLY' } });
    fireEvent.click(screen.getByRole('button', { name: /Connect OpenCode Go/ }));
    await waitFor(() => expect(request.mock.calls.some(([url]) => url === '/api/v1/connections/opencode-go')).toBe(true));
    expect((field as HTMLInputElement).value).toBe('');
    const call = request.mock.calls.find(([url]) => url === '/api/v1/connections/opencode-go');
    expect(JSON.parse(call![1]!.body as string)).toEqual({ api_key: 'SYNTHETIC_KEY_ONLY', select: false });
    expect(JSON.stringify(window.localStorage)).not.toContain('SYNTHETIC_KEY_ONLY');
  });
});
