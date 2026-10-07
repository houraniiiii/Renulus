// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { useEffect, useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ContextScope } from '../../platform/contracts';
import { NavigationProvider, useNavigation } from '../../shell/navigation';
import Learn from './index';

// Synthetic HTTP/SSE fixtures exercise the real renderer transport and decoder.
// No provider, memory engine or backend integration is implied by these checks.
const answer = 'Synthetic explanation for the UI contract.';
const recallFailure = 'Learner memory could not be recalled for this explanation.';
const captureFailure = 'The explanation was saved. Learner memory capture will retry later.';
const citation = { id: 'synthetic-passage', document_id: 'synthetic-source', document_revision: 'revision-2', locators: [{ page: 3 }] };
const resumedThread = { id: 'synthetic-thread', title: 'Resume CKD learning', topic_id: 'ckd', teaching_style: 'direct', updated_at: '2026-10-04T20:00:00Z', messages: [{ id: 'resumed-answer', role: 'assistant', content: 'Synthetic resumed explanation.' }] };
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });

function events(runId = 'synthetic-run') {
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  let sequence = 0;
  const cancelled = vi.fn();
  const response = new Response(new ReadableStream<Uint8Array>({ start(value) { controller = value; }, cancel: cancelled }), { headers: { 'Content-Type': 'text/event-stream' } });
  return {
    response, cancelled,
    emit(type: string, payload: Record<string, unknown> = {}) {
      const data = { run_id: runId, sequence: ++sequence, type, payload };
      const newline = String.fromCharCode(10);
      controller.enqueue(new TextEncoder().encode('event: ' + type + newline + 'data: ' + JSON.stringify(data) + newline + newline));
    },
    close() { controller.close(); },
  };
}
type EventStream = ReturnType<typeof events>;
type Handler = (path: string, options: RequestInit) => Response | Promise<Response> | undefined;
function transport(streams: EventStream[], handler: Handler = () => undefined) {
  const pending = [...streams];
  const fetch = vi.fn(async (path: string, options: RequestInit) => {
    const custom = handler(path, options);
    if (custom !== undefined) return custom;
    if (path === '/api/v1/learn/ask') {
      const selected = pending.shift();
      if (!selected) throw new Error('No synthetic stream remains.');
      return selected.response;
    }
    if (path === '/api/v1/learn/threads') return json({ threads: [resumedThread] });
    if (path === '/api/v1/learn/threads/' + resumedThread.id) return json(resumedThread);
    if (path === '/api/v1/content/topics') return json([{ id: 'ckd', title: 'CKD' }]);
    if (path.endsWith('/cancel')) return json({ state: 'cancelled' });
    if (path.startsWith('/api/v1/cases/sessions/') && path.endsWith('/handoff')) return json({ id: 'synthetic-case-ticket' });
    if (path.startsWith('/api/v1/cases/sessions/')) return json({ revision: 1 });
    if (path.startsWith('/api/v1/cases/handoffs/')) return new Response(null, { status: 204 });
    throw new Error('Unexpected synthetic endpoint: ' + path);
  });
  vi.stubGlobal('fetch', fetch);
  return fetch;
}
function ScopedLearn({ scope }: { scope: ContextScope }) {
  const navigation = useNavigation();
  const [ready, setReady] = useState(false);
  useEffect(() => { navigation.navigate('learn', { scope }); setReady(true); }, []);
  return ready ? <Learn /> : null;
}
function open(scope?: ContextScope) {
  window.location.hash = '#/learn';
  return render(<NavigationProvider>{scope ? <ScopedLearn scope={scope} /> : <Learn />}</NavigationProvider>);
}
async function ask(fetch: ReturnType<typeof transport>, question = 'A synthetic learning question.') {
  const count = fetch.mock.calls.filter(([path]) => path === '/api/v1/learn/ask').length;
  fireEvent.change(screen.getByRole('textbox', { name: /Your nephrology question|Your follow-up/ }), { target: { value: question } });
  fireEvent.click(screen.getByRole('button', { name: 'Ask Renulus' }));
  await waitFor(() => expect(fetch.mock.calls.filter(([path]) => path === '/api/v1/learn/ask')).toHaveLength(count + 1));
}
async function finish(source: EventStream) {
  await act(async () => { source.emit('delta', { text: answer }); source.emit('completed'); source.close(); });
  await screen.findByText(answer);
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Stop' })).toBeNull());
}
function expectNoDisclosures() {
  expect(screen.queryByRole('region', { name: 'Retained learner context' })).toBeNull();
  expect(screen.queryByRole('region', { name: 'Learner memory capture' })).toBeNull();
  expect(screen.queryByRole('status', { name: 'Scientific evidence' })).toBeNull();
  expect(screen.queryByRole('status', { name: 'Explanation status' })).toBeNull();
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.localStorage.clear(); window.sessionStorage.clear(); });

describe('Learn memory disclosure remains distinct from scientific evidence', () => {
  it.each(['before', 'after'] as const)('does not turn recall into evidence when memory arrives %s sources', async order => {
    const source = events(); const fetch = transport([source]); open(); await ask(fetch);
    await act(async () => {
      source.emit('started');
      if (order === 'before') source.emit('memory', { count: 2 });
      source.emit('sources', { citations: [] });
      if (order === 'after') source.emit('memory', { count: 2 });
    });
    await finish(source);
    const memory = screen.getByRole('region', { name: 'Retained learner context' });
    expect(within(memory).getByText('Using 2 retained learning records to personalize this explanation.')).toBeDefined();
    expect(within(memory).getByText('Retained learning personalizes study; it does not verify scientific support.')).toBeDefined();
    const evidence = screen.getByRole('status', { name: 'Scientific evidence' });
    expect(evidence.textContent).toContain('No evidence retrieved · answer not source-verified');
    expect(evidence.contains(memory)).toBe(false);
    expect(screen.queryByText('Retrieved evidence')).toBeNull();
    expect(screen.queryByRole('button', { name: /^Source / })).toBeNull();
  });

  it('reports recall failure without hiding retrieved evidence or its source link', async () => {
    const source = events(); const fetch = transport([source]); open(); await ask(fetch);
    await act(async () => { source.emit('sources', { citations: [citation] }); source.emit('memory-unavailable', { message: recallFailure }); });
    await finish(source);
    expect(screen.getByRole('status', { name: 'Scientific evidence' }).textContent).toContain('Retrieved evidence');
    expect(within(screen.getByRole('region', { name: 'Retained learner context' })).getByText(recallFailure)).toBeDefined();
    expect(screen.getByRole('button', { name: 'Source 1' })).toBeDefined();
    expect(screen.queryByRole('heading', { name: 'The explanation could not finish' })).toBeNull();
  });

  it('keeps capture retry, successful recall and source verification separate after completion', async () => {
    const source = events(); const fetch = transport([source]); open(); await ask(fetch);
    await act(async () => { source.emit('sources', { citations: [citation] }); source.emit('memory', { count: 1 }); source.emit('memory-capture-unavailable', { message: captureFailure }); });
    await finish(source);
    expect(screen.getByRole('status', { name: 'Scientific evidence' }).textContent).toContain('Retrieved evidence');
    expect(within(screen.getByRole('region', { name: 'Retained learner context' })).getByText('Using 1 retained learning record to personalize this explanation.')).toBeDefined();
    expect(within(screen.getByRole('region', { name: 'Learner memory capture' })).getByText(captureFailure)).toBeDefined();
    expect(screen.getByRole('button', { name: 'Source 1' })).toBeDefined();
    expect(screen.queryByText('Partial')).toBeNull();
    expect(screen.queryByRole('heading', { name: 'The explanation could not finish' })).toBeNull();
  });

  it('does not claim scientific support when retrieval fails but learner context is available', async () => {
    const source = events(); const fetch = transport([source]); open(); await ask(fetch);
    await act(async () => { source.emit('retrieval-failed'); source.emit('memory', { count: 1 }); source.emit('memory-capture-unavailable', { message: captureFailure }); });
    await finish(source);
    expect(screen.getByRole('status', { name: 'Scientific evidence' }).textContent).toContain('Evidence retrieval unavailable · answer not source-verified');
    expect(screen.getByRole('region', { name: 'Retained learner context' })).toBeDefined();
    expect(screen.getByRole('region', { name: 'Learner memory capture' })).toBeDefined();
    expect(screen.queryByText('Retrieved evidence')).toBeNull();
    expect(screen.queryByRole('button', { name: /^Source / })).toBeNull();
  });

  it('reports zero recalled records without claiming personal context was used', async () => {
    const source = events(); const fetch = transport([source]); open(); await ask(fetch);
    await act(async () => { source.emit('memory', { count: 0 }); source.emit('sources', { citations: [] }); });
    await finish(source);
    expect(screen.getByText('No retained learning was used for this explanation.')).toBeDefined();
    expect(screen.queryByText(/Using .* retained learning/)).toBeNull();
  });

  it.each(['fresh', 'resume', 'run'] as const)('clears prior evidence, recall and capture status on %s', async action => {
    const first = events(); const next = events('synthetic-next-run');
    let releaseResume!: (response: Response) => void;
    const resume = new Promise<Response>(resolve => { releaseResume = resolve; });
    const fetch = transport([first, next], path => path === '/api/v1/learn/threads/' + resumedThread.id ? resume : undefined);
    open(); await ask(fetch);
    await act(async () => { first.emit('sources', { citations: [citation] }); first.emit('memory', { count: 2 }); first.emit('memory-capture-unavailable', { message: captureFailure }); });
    await finish(first);
    expect(screen.getByRole('region', { name: 'Learner memory capture' })).toBeDefined();
    if (action === 'fresh') fireEvent.click(screen.getByRole('button', { name: 'New study' }));
    if (action === 'run') await ask(fetch, 'A synthetic follow-up.');
    if (action === 'resume') {
      fireEvent.click(await screen.findByRole('button', { name: /^Resume CKD learning/ }));
      await waitFor(() => expect(fetch.mock.calls.some(([path]) => path === '/api/v1/learn/threads/' + resumedThread.id)).toBe(true));
    }
    expectNoDisclosures();
    if (action === 'resume') {
      await act(async () => releaseResume(json(resumedThread)));
      await screen.findByText('Synthetic resumed explanation.');
      expectNoDisclosures();
    }
  });

  it.each(['temporary-case', 'unclassified', 'saved-case'] as const)('ignores all three memory disclosures in %s scope', async kind => {
    const source = events(); const fetch = transport([source]); open({ kind, entity_id: 'synthetic-case' }); await ask(fetch);
    await act(async () => { source.emit('memory', { count: 2 }); source.emit('memory-unavailable', { message: 'SYNTHETIC_EXCLUDED_RECALL' }); source.emit('memory-capture-unavailable', { message: 'SYNTHETIC_EXCLUDED_CAPTURE' }); source.emit('sources', { citations: [] }); });
    await finish(source);
    expect(screen.queryByRole('region', { name: 'Retained learner context' })).toBeNull();
    expect(screen.queryByRole('region', { name: 'Learner memory capture' })).toBeNull();
    expect(screen.queryByText('SYNTHETIC_EXCLUDED_RECALL')).toBeNull();
    expect(screen.queryByText('SYNTHETIC_EXCLUDED_CAPTURE')).toBeNull();
    expect(screen.getByRole('status', { name: 'Scientific evidence' }).textContent).toContain('answer not source-verified');
    expect(fetch.mock.calls.some(([path]) => path.includes('/memory/'))).toBe(false);
    expect(window.localStorage.length).toBe(0); expect(window.sessionStorage.length).toBe(0);
  });

  it('keeps cancellation independent of memory and evidence status and aborts the stream', async () => {
    const source = events(); const fetch = transport([source]); open(); await ask(fetch);
    await act(async () => { source.emit('started'); source.emit('memory-unavailable', { message: recallFailure }); source.emit('retrieval-failed'); source.emit('delta', { text: 'Synthetic partial explanation.' }); });
    await screen.findByText('Synthetic partial explanation.');
    fireEvent.click(screen.getByRole('button', { name: 'Stop' }));
    await waitFor(() => expect(screen.getByRole('status', { name: 'Explanation status' }).textContent).toBe('Stopped · partial explanation not saved'));
    await waitFor(() => expect(source.cancelled).toHaveBeenCalled());
    expect(screen.getByText(recallFailure)).toBeDefined();
    expect(screen.getByRole('status', { name: 'Scientific evidence' }).textContent).toContain('Evidence retrieval unavailable · answer not source-verified');
    expect(screen.getByText('Partial')).toBeDefined();
    expect(screen.queryByText('Complete')).toBeNull();
    expect(fetch.mock.calls.some(([path, options]) => path === '/api/v1/learn/runs/synthetic-run/cancel' && options.method === 'POST')).toBe(true);
  });

  it('receives committed completion and capture retry when completion wins a Stop request', async () => {
    const source = events(); const fetch = transport([source], path => path.endsWith('/cancel') ? json({ state: 'completed' }) : undefined);
    open(); await ask(fetch);
    await act(async () => { source.emit('started'); source.emit('sources', { citations: [citation] }); source.emit('memory', { count: 1 }); });
    await screen.findByText('Using 1 retained learning record to personalize this explanation.');
    fireEvent.click(screen.getByRole('button', { name: 'Stop' }));
    await waitFor(() => expect(screen.getByRole('status', { name: 'Explanation status' }).textContent).toBe('Complete'));
    expect(source.cancelled).not.toHaveBeenCalled();
    await act(async () => source.emit('memory-capture-unavailable', { message: captureFailure }));
    await finish(source);
    expect(screen.getByRole('status', { name: 'Explanation status' }).textContent).toBe('Complete');
    expect(screen.getByText(captureFailure)).toBeDefined();
    expect(screen.getByRole('status', { name: 'Scientific evidence' }).textContent).toContain('Retrieved evidence');
    expect(screen.queryByText('Stopped · partial explanation not saved')).toBeNull();
    expect(screen.queryByRole('heading', { name: 'The explanation could not finish' })).toBeNull();
  });
});
