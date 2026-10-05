// @vitest-environment jsdom
import { createHash } from 'node:crypto';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ConnectionsPage } from './ConnectionsPage';
import { IMAGE_CHECK_PNG, imageCapabilityRequest } from './imageCapability';

const request = vi.fn<typeof fetch>();
const ids = ['gpt-6.1-sol', 'gpt-6-astra', 'gpt-6-luna'];
let selected: string | null;
let state: string;
let available: boolean;
let imageInput: string;
let checkedModel: string | undefined;
let check: (body: ReturnType<typeof imageCapabilityRequest>) => Response | Promise<Response>;
let cancel: () => Response | Promise<Response>;
function json(body: unknown) { return new Response(JSON.stringify(body), { headers: { 'content-type': 'application/json' } }); }
function envelope(runId: string, sequence: number, type: string, payload = {}) {
  return 'data: ' + JSON.stringify({ id: 'synthetic-' + sequence, run_id: runId, sequence, type, payload }) + '\n\n';
}
function sse(body: string) { return new Response(body, { headers: { 'content-type': 'text/event-stream' } }); }
function calls(path: string, method = 'POST') { return request.mock.calls.filter(([url, options]) => url === path && (options?.method ?? 'GET') === method); }
async function mount() { const view = render(<ConnectionsPage />); await screen.findByRole('region', { name: 'Codex subscription' }); return view; }
function click(model = ids[0]) { fireEvent.click(screen.getByRole('button', { name: 'Check image input for ' + model })); }
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(done => { resolve = done; }); return { promise, resolve }; }

beforeEach(() => {
  request.mockReset(); selected = 'codex'; state = 'connected'; available = true; imageInput = 'unknown'; checkedModel = undefined;
  cancel = () => json({ cancelled: true });
  check = body => { checkedModel = body.model; return sse(envelope(body.run_id, 1, 'started') + envelope(body.run_id, 2, 'completed')); };
  request.mockImplementation(async (url, options) => {
    if (url === '/api/v1/health') return json({ version: 'synthetic', api_version: 1 });
    if (url === '/api/v1/connections') return json({ selected_provider: selected, connections: [
      { provider: 'codex', status: state, allowed_models: ids, models: ids.map(id => ({ id,
        availability: available ? 'available' : 'unknown', image_input: id === checkedModel ? 'supported' : imageInput, text_input: 'unknown' })) },
      { provider: 'opencode-go', status: 'connected', allowed_models: ['mimo-v2.6-pro', 'deepseek-v4.1-flash'],
        learning_use: { status: 'unresolved', generation_allowed: false },
        models: ['mimo-v2.6-pro', 'deepseek-v4.1-flash'].map(id => ({ id, availability: 'available', image_input: 'supported' })) },
    ] });
    if (url === '/api/v1/runtime/runs' && options?.method === 'POST') return check(JSON.parse(options.body as string));
    if (String(url).startsWith('/api/v1/runtime/runs/') && options?.method === 'DELETE') return cancel();
    throw new Error('Unexpected request ' + url);
  });
  vi.stubGlobal('fetch', request);
});
afterEach(() => {
  cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks();
  expect(request.mock.calls.every(([url]) => String(url).startsWith('/api/v1/'))).toBe(true);
  expect(request.mock.calls.some(([url]) => /connections\/select|credentials|auth\.json|\/cases|\/learn/.test(String(url)))).toBe(false);
});

it('uses a tiny original PNG with exact recorded bytes', () => {
  const bytes = Buffer.from(IMAGE_CHECK_PNG, 'base64');
  expect(bytes.length).toBe(100);
  expect(bytes.subarray(0, 8).toString('hex')).toBe('89504e470d0a1a0a');
  expect(createHash('sha256').update(bytes).digest('hex')).toBe('004300443c19b2ac42179cb4a9859445ea610cbfa5d52512e9aa5edf0bbef76d');
});

it.each(ids)('makes one deliberate temporary request to %s and refreshes observed support only on completion', async model => {
  await mount(); expect(calls('/api/v1/runtime/runs')).toHaveLength(0);
  expect(screen.getByText(/uses your subscription/)).toBeTruthy();
  expect(screen.getByText(/original synthetic Renulus test image/)).toBeTruthy();
  click(model);
  await screen.findByText(model + ' accepted the Renulus test image. Refreshing observed input support; interpretation quality remains unverified.');
  const posted = calls('/api/v1/runtime/runs'); expect(posted).toHaveLength(1);
  const body = JSON.parse(posted[0][1]!.body as string);
  expect(body).toEqual(imageCapabilityRequest(body.run_id, model));
  expect(body.run_id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  expect(body.scope).toEqual({ kind: 'temporary-case' });
  await waitFor(() => expect(within(screen.getByRole('region', { name: 'Codex subscription' })).getAllByText(/Images: request accepted/)).toHaveLength(1));
  expect(calls('/api/v1/connections', 'GET').length).toBeGreaterThan(1);
  expect(selected).toBe('codex');
});

it.each([null, 'opencode-go'])('does not expose a request for non-selected Codex or selected Go (%s)', async provider => {
  selected = provider; await mount();
  expect(screen.queryByRole('button', { name: /Check image input/ })).toBeNull();
  expect(calls('/api/v1/runtime/runs')).toHaveLength(0);
});
it.each(['disconnected', 'authentication_required', 'configured'])('does not offer an image request for %s', async status => {
  state = status; await mount();
  expect(screen.queryByRole('button', { name: /Check image input/ })).toBeNull();
});
it('does not offer a request to an unverified catalogue model', async () => {
  available = false; await mount(); expect(screen.queryByRole('button', { name: /Check image input/ })).toBeNull();
});
it('keeps an account image rejection disabled until a deliberate catalogue refresh', async () => {
  imageInput = 'account_unsupported'; await mount();
  expect((screen.getByRole('button', { name: 'Check image input for ' + ids[0] }) as HTMLButtonElement).disabled).toBe(true);
  expect(calls('/api/v1/runtime/runs')).toHaveLength(0);
});

it.each(['authentication_required', 'subscription_limit', 'image_input_unsupported', 'connection_changed', 'model_not_allowed'])('presents %s without success or automatic retry', async code => {
  check = body => sse(envelope(body.run_id, 1, 'error', { code, message: 'Synthetic public ' + code, retryable: false, status: 409 }));
  await mount(); click();
  await screen.findByText('Synthetic public ' + code);
  expect(screen.getByText('Image input could not be checked')).toBeTruthy();
  expect(screen.queryByText(/accepted the Renulus test image/)).toBeNull();
  expect(calls('/api/v1/runtime/runs')).toHaveLength(1);
});
it('does not treat deltas or an interrupted stream as capability success', async () => {
  check = body => sse(envelope(body.run_id, 1, 'started') + envelope(body.run_id, 2, 'delta', { text: 'PRIVATE_SYNTHETIC_OUTPUT' }));
  await mount(); click();
  await screen.findByText(/stream ended before/);
  expect(screen.queryByText(/PRIVATE_SYNTHETIC_OUTPUT|accepted the Renulus test image/)).toBeNull();
});
it('stops the active run and ignores a late successful response', async () => {
  const pending = deferred<Response>(); let body!: ReturnType<typeof imageCapabilityRequest>;
  check = value => { body = value; return pending.promise; };
  await mount(); click(); await screen.findByRole('button', { name: 'Stop image check' });
  fireEvent.click(screen.getByRole('button', { name: 'Stop image check' }));
  await screen.findByText('Image input check stopped.');
  const path = '/api/v1/runtime/runs/' + body.run_id;
  expect(calls(path, 'DELETE')).toHaveLength(1);
  await act(async () => { pending.resolve(sse(envelope(body.run_id, 1, 'completed'))); });
  expect(screen.queryByText(/accepted the Renulus test image/)).toBeNull();
  expect(calls('/api/v1/connections', 'GET')).toHaveLength(1);
  expect(calls('/api/v1/runtime/runs')).toHaveLength(1);
});
it('closes the stream and publishes cancellation once when unmounted', async () => {
  const pending = deferred<Response>(); let body!: ReturnType<typeof imageCapabilityRequest>;
  check = value => { body = value; return pending.promise; };
  const view = await mount(); click(); await screen.findByRole('button', { name: 'Stop image check' });
  view.unmount();
  await waitFor(() => expect(calls('/api/v1/runtime/runs/' + body.run_id, 'DELETE')).toHaveLength(1));
  await act(async () => { pending.resolve(sse(envelope(body.run_id, 1, 'completed'))); });
  expect(calls('/api/v1/connections', 'GET')).toHaveLength(1);
});
it('cancels body consumption after response headers and keeps other model actions disabled while running', async () => {
  const bodyCancelled = vi.fn(); let runId = '';
  check = body => {
    runId = body.run_id;
    return new Response(new ReadableStream({
      start(controller) { controller.enqueue(new TextEncoder().encode(envelope(runId, 1, 'started'))); },
      cancel() { bodyCancelled(); },
    }), { headers: { 'content-type': 'text/event-stream' } });
  };
  await mount(); click(); await screen.findByRole('button', { name: 'Stop image check' });
  expect((screen.getByRole('button', { name: 'Check image input for ' + ids[1] }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: 'Stop image check' }));
  await screen.findByText('Image input check stopped.');
  await waitFor(() => expect(bodyCancelled).toHaveBeenCalledTimes(1));
  expect(calls('/api/v1/runtime/runs/' + runId, 'DELETE')).toHaveLength(1);
  expect(screen.queryByText(/accepted the Renulus test image/)).toBeNull();
});
it('keeps a failed cancellation visible and does not resubmit or switch subscriptions', async () => {
  const pending = deferred<Response>();
  check = () => pending.promise;
  cancel = () => new Response(JSON.stringify({ error: { code: 'provider_unavailable', message: 'Synthetic stop failed', retryable: true } }),
    { status: 503, headers: { 'content-type': 'application/json' } });
  await mount(); click(); await screen.findByRole('button', { name: 'Stop image check' });
  fireEvent.click(screen.getByRole('button', { name: 'Stop image check' }));
  await screen.findByText(/server cancellation could not be confirmed/);
  expect(screen.getByText('Synthetic stop failed')).toBeTruthy();
  expect(calls('/api/v1/runtime/runs')).toHaveLength(1);
  await act(async () => { pending.resolve(sse('')); });
});
