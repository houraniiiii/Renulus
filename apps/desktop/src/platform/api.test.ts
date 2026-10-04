import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError, apiPath } from './api';
import { stream } from './stream';

afterEach(() => vi.unstubAllGlobals());
const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
describe('local API transport', () => {
  it('uses v1, JSON and no-store without exposing renderer-supplied credentials', async () => {
    const fetch = vi.fn().mockResolvedValue(json({ id: 'synthetic-record' })); vi.stubGlobal('fetch', fetch);
    expect(await api('/learn/threads', { method: 'POST', body: { title: 'Synthetic' }, headers: { Authorization: 'not-a-real-secret', 'x-renulus-token': 'renderer-value' } })).toEqual({ id: 'synthetic-record' });
    const [path, options] = fetch.mock.calls[0];
    expect(path).toBe('/api/v1/learn/threads'); expect(options.body).toBe('{"title":"Synthetic"}');
    expect(options.cache).toBe('no-store'); expect(options.redirect).toBe('error');
    expect(options.headers.has('authorization')).toBe(false); expect(options.headers.has('x-renulus-token')).toBe(false);
  });
  it.each(['https://example.com', '//example.com/api', '/../private', '/api/v2/runs', '/%2e%2e/private', '/%5cprivate', '/bad#fragment'])('refuses a request outside the API boundary: %s', path => {
    expect(() => apiPath(path)).toThrow(ApiError);
  });
  it('honours structured backend errors without displaying HTML tracebacks', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ error: { code: 'quota', message: 'The selected subscription has no quota.', retryable: false } }, 429)));
    await expect(api('/runtime/runs')).rejects.toMatchObject({ status: 429, code: 'quota', retryable: false });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>synthetic-sensitive-debug</html>', { status: 500 })));
    await expect(api('/runtime/status')).rejects.toMatchObject({ message: 'Renulus could not complete the request. Try again.' });
  });
  it('reports transport failure and rejects malformed JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    await expect(api('/health')).rejects.toMatchObject({ code: 'unavailable', retryable: true });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{', { headers: { 'Content-Type': 'application/json' } })));
    await expect(api('/health')).rejects.toMatchObject({ code: 'invalid_response' });
  });
  it('preserves caller cancellation', async () => {
    vi.stubGlobal('fetch', vi.fn((_url, options) => new Promise((_resolve, reject) => {
      options.signal.addEventListener('abort', () => reject(options.signal.reason), { once: true });
    })));
    const controller = new AbortController(); const pending = api('/runtime/status', { signal: controller.signal }); controller.abort();
    await expect(pending).rejects.toMatchObject({ name: 'AbortError' });
  });
});
describe('stream transport', () => {
  it('parses split UTF-8, CRLF, multiline JSON and ignores heartbeat comments', async () => {
    const bytes = new TextEncoder().encode(': heartbeat\r\n\r\nid: one\r\nevent: delta\r\ndata: {"text":\r\ndata: "renal café"}\r\n\r\n');
    const body = new ReadableStream({ start(controller) { for (let index = 0; index < bytes.length; index += 3) controller.enqueue(bytes.slice(index, index + 3)); controller.close(); } });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, { headers: { 'Content-Type': 'text/event-stream' } })));
    const events = []; for await (const event of stream('/learn/ask', { method: 'POST', body: { question: 'Synthetic' } })) events.push(event);
    expect(events).toEqual([{ id: 'one', event: 'delta', data: { text: 'renal café' } }]);
  });
  it('cancels a stream before a late event can be read', async () => {
    let source: ReadableStreamDefaultController<Uint8Array>;
    const cancel = vi.fn(); const body = new ReadableStream<Uint8Array>({ start(controller) { source = controller; }, cancel });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, { headers: { 'Content-Type': 'text/event-stream' } })));
    const controller = new AbortController(); const reader = stream('/runtime/runs', { signal: controller.signal });
    const next = reader.next(); await Promise.resolve(); await Promise.resolve(); controller.abort();
    await expect(next).rejects.toMatchObject({ name: 'AbortError' }); expect(cancel).toHaveBeenCalled(); expect(() => source!.enqueue(new Uint8Array())).toThrow();
  });
});
