// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { NavigationProvider } from '../../shell/navigation';
import Learn from './index';

// Real Learn transport/decoder/navigation; controlled HTTP/SSE producers only.
const question = 'Synthetic transplant learning question.';
const marker = 'SYNTHETIC_DELETED_STUDY_CONTENT_8263';
const first = { id: 'thread-a', title: 'Resume transplant', topic_id: 'T21', teaching_style: 'direct', updated_at: '2026-10-04T20:00:00Z', messages: [{ id: 'a', role: 'user', content: marker }], runs: [] };
const other = { ...first, id: 'thread-b', title: 'Resume dialysis', messages: [{ id: 'b', role: 'assistant', content: 'Synthetic dialysis answer.' }] };
const json = (value: unknown) => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } });
function pending() {
  let resolve!: (response: Response) => void;
  const response = new Promise<Response>(done => { resolve = done; });
  return { response, resolve };
}
function events(run = 'run-a') {
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  let sequence = 0;
  const response = new Response(new ReadableStream<Uint8Array>({ start(value) { controller = value; } }), { headers: { 'Content-Type': 'text/event-stream' } });
  return { response, emit(type: string, payload: Record<string, unknown> = {}) {
    controller.enqueue(new TextEncoder().encode('data: ' + JSON.stringify({ run_id: run, sequence: ++sequence, type, payload }) + '\n\n'));
  }, close() { controller.close(); } };
}
function transport(streams: ReturnType<typeof events>[], thread: (id: string) => Response | Promise<Response>) {
  const fetch = vi.fn(async (path: string, options: RequestInit) => {
    if (path === '/api/v1/learn/threads') return json({ threads: [first, other] });
    if (path === '/api/v1/content/topics') return json([{ id: 'T21', label: 'Transplantation' }]);
    if (options.method === 'DELETE') return json({ deleted: true });
    if (path.startsWith('/api/v1/learn/threads/')) return thread(path.split('/').at(-1)!);
    if (path.endsWith('/cancel')) return json({ state: 'cancelled' });
    if (path === '/api/v1/learn/ask') return streams.shift()!.response;
    throw new Error('Unexpected controlled endpoint: ' + path);
  });
  vi.stubGlobal('fetch', fetch);
  window.location.hash = '#/learn';
  render(<NavigationProvider><Learn /></NavigationProvider>);
  return fetch;
}
async function ask(fetch: ReturnType<typeof transport>, text = question) {
  const count = fetch.mock.calls.filter(([path]) => path.endsWith('/ask')).length;
  fireEvent.change(screen.getByRole('textbox', { name: /Your nephrology question|Your follow-up/ }), { target: { value: text } });
  fireEvent.click(screen.getByRole('button', { name: 'Ask Renulus' }));
  await waitFor(() => expect(fetch.mock.calls.filter(([path]) => path.endsWith('/ask'))).toHaveLength(count + 1));
  return JSON.parse(String(fetch.mock.calls.filter(([path]) => path.endsWith('/ask')).at(-1)![1].body));
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('keeps composer focus usable while Ask becomes Stop and a failed response restores the question', async () => {
  const source = events();
  const fetch = transport([source], () => json(first));
  await screen.findByRole('button', { name: /^Resume transplant/ });
  const field = screen.getByRole('textbox', { name: 'Your nephrology question' }); field.focus();
  await ask(fetch);
  expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Stop' }));
  await act(async () => { source.emit('error', { message: 'Synthetic connection interrupted.', code: 'interrupted', retryable: true }); source.close(); });
  await screen.findByText('Synthetic connection interrupted.');
  const followUp = screen.getByRole('textbox', { name: 'Your follow-up' });
  expect((followUp as HTMLTextAreaElement).value).toBe(question);
  expect(document.activeElement).toBe(followUp);
});

it('does not pull focus away from another control when a response completes', async () => {
  const source = events();
  const fetch = transport([source], () => json(first));
  await ask(fetch);
  const connection = screen.getByRole('button', { name: 'Open Connections' }); connection.focus();
  await act(async () => { source.emit('completed', {}); source.close(); });
  await screen.findByRole('button', { name: 'Ask Renulus' });
  expect(document.activeElement).toBe(connection);
});

it('retries a failed resume by loading that thread with no generation request', async () => {
  let reads = 0;
  const fetch = transport([], () => ++reads === 1
    ? new Response(JSON.stringify({ error: { code: 'unavailable', message: 'Synthetic thread unavailable', retryable: true } }), { status: 503, headers: { 'Content-Type': 'application/json' } })
    : json(other));
  fireEvent.click(await screen.findByRole('button', { name: /^Resume dialysis/ }));
  await screen.findByRole('heading', { name: 'The study thread could not load' });
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
  await screen.findByText('Synthetic dialysis answer.');
  expect(reads).toBe(2);
  expect(fetch.mock.calls.some(([path]) => path.endsWith('/ask'))).toBe(false);
});

it.each(['fresh', 'delete', 'other'])('does not restore late thread content after %s', async action => {
  const delayed = pending(), source = events();
  const fetch = transport([source], id => id === first.id ? delayed.response : json(other));
  fireEvent.click(await screen.findByRole('button', { name: /^Resume transplant/ }));
  await waitFor(() => expect(fetch.mock.calls.some(([path]) => path.endsWith('/' + first.id))).toBe(true));
  if (action === 'fresh') fireEvent.click(screen.getByRole('button', { name: 'New study' }));
  if (action === 'delete') {
    fireEvent.click(screen.getByRole('button', { name: 'Delete Resume transplant' }));
    await waitFor(() => expect(fetch.mock.calls.some(([, options]) => options.method === 'DELETE')).toBe(true));
  }
  if (action === 'other') {
    fireEvent.click(screen.getByRole('button', { name: /^Resume dialysis/ }));
    await screen.findByText('Synthetic dialysis answer.');
  }
  // This response deliberately ignores AbortSignal, proving the state guard too.
  await act(async () => { delayed.resolve(json(first)); });
  expect(screen.queryByText(marker)).toBeNull();
  const body = await ask(fetch);
  expect(body.thread_id ?? null).toBe(action === 'other' ? other.id : null);
  await act(async () => { source.emit('completed'); source.close(); });
});

it('reports an unterminated stream and retries in the retained canonical thread', async () => {
  const source = events(), retry = events('run-retry');
  const canonical = { ...first, messages: [{ id: 'question', role: 'user', content: question }], runs: [{ id: 'run-a', state: 'interrupted' }] };
  const fetch = transport([source, retry], () => json(canonical));
  await ask(fetch);
  await act(async () => { source.emit('started', { thread_id: first.id }); source.emit('delta', { text: 'Synthetic partial answer.' }); source.close(); });
  await screen.findByRole('heading', { name: 'The explanation could not finish' });
  await waitFor(() => expect((screen.getByRole('textbox', { name: 'Your follow-up' }) as HTMLTextAreaElement).value).toBe(question));
  expect(fetch.mock.calls.some(([path]) => path === '/api/v1/learn/runs/run-a/cancel')).toBe(true);
  const body = await ask(fetch);
  expect(body.thread_id).toBe(first.id);
  await act(async () => { retry.emit('started', { thread_id: first.id }); retry.emit('completed'); retry.close(); });
});

it('reconciles a committed answer whose completed event was lost without offering model retry', async () => {
  const source = events();
  const canonical = { ...first, messages: [{ id: 'user', role: 'user', content: question }, { id: 'answer', role: 'assistant', content: 'Synthetic committed answer.' }], runs: [{ id: 'run-a', state: 'completed' }] };
  const fetch = transport([source], () => json(canonical));
  await ask(fetch);
  await act(async () => { source.emit('started', { thread_id: first.id }); source.emit('delta', { text: 'Incomplete transport copy' }); source.close(); });
  await screen.findByText('Synthetic committed answer.');
  await waitFor(() => expect(screen.getByRole('status', { name: 'Explanation status' }).textContent).toBe('Complete'));
  expect(screen.queryByText('Incomplete transport copy')).toBeNull();
  expect(screen.queryByRole('heading', { name: 'The explanation could not finish' })).toBeNull();
  expect((screen.getByRole('textbox', { name: 'Your follow-up' }) as HTMLTextAreaElement).value).toBe('');
  expect(fetch.mock.calls.filter(([path]) => path.endsWith('/ask'))).toHaveLength(1);
});

it('keeps the started thread and question after Stop for deliberate continuation', async () => {
  const source = events(), next = events('run-next');
  const canonical = { ...first, messages: [{ id: 'question', role: 'user', content: question }], runs: [{ id: 'run-a', state: 'cancelled' }] };
  const fetch = transport([source, next], () => json(canonical));
  await ask(fetch);
  await act(async () => { source.emit('started', { thread_id: first.id }); source.emit('delta', { text: 'Synthetic stopped partial.' }); });
  await screen.findByText('Synthetic stopped partial.');
  fireEvent.click(screen.getByRole('button', { name: 'Stop' }));
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Stop' })).toBeNull());
  expect((screen.getByRole('textbox', { name: 'Your follow-up' }) as HTMLTextAreaElement).value).toBe(question);
  expect((await ask(fetch)).thread_id).toBe(first.id);
  await act(async () => { next.emit('completed'); next.close(); });
});

it.each([
  ['learning_use_unverified', false, false],
  ['account_model_unsupported', false, false],
  ['subscription_limit', true, true],
  ['legacy_stream_error', undefined, true],
] as const)('preserves streamed recovery policy for %s', async (code, retryable, canRetry) => {
  const source = events(), retry = events('run-retry');
  const canonical = { ...first, messages: [{ id: 'question', role: 'user', content: question }], runs: [{ id: 'run-a', state: 'failed' }] };
  const fetch = transport([source, retry], () => json(canonical));
  await ask(fetch);
  await act(async () => {
    source.emit('started', { thread_id: first.id });
    source.emit('error', { code, retryable, message: 'Synthetic connection recovery required.' });
    source.close();
  });
  await screen.findByRole('heading', { name: 'The explanation could not finish' });
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Stop' })).toBeNull());
  expect((screen.getByRole('textbox', { name: 'Your follow-up' }) as HTMLTextAreaElement).value).toBe(question);
  expect(fetch.mock.calls.filter(([path]) => path.endsWith('/ask'))).toHaveLength(1);
  expect(screen.getByRole('button', { name: 'Open Connections' })).toBeTruthy();
  const button = screen.queryByRole('button', { name: 'Try again' });
  expect(!!button).toBe(canRetry);
  if (button) {
    fireEvent.click(button);
    await waitFor(() => expect(fetch.mock.calls.filter(([path]) => path.endsWith('/ask'))).toHaveLength(2));
    const attempts = fetch.mock.calls.filter(([path]) => path.endsWith('/ask'));
    expect(JSON.parse(String(attempts[1][1].body)).thread_id).toBe(first.id);
    expect(new Headers(attempts[1][1].headers).get('Idempotency-Key')).not.toBe(new Headers(attempts[0][1].headers).get('Idempotency-Key'));
    await act(async () => { retry.emit('delta', { text: 'Synthetic recovered explanation.' }); retry.emit('completed'); retry.close(); });
  }
});
