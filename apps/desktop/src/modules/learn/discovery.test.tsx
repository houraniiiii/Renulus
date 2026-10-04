// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { useEffect, useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ContextScope } from '../../platform/contracts';
import { NavigationProvider, useNavigation } from '../../shell/navigation';
import Learn from './index';

// Controlled event producers; real Learn renderer, transport and SSE decoder.
const answer = 'Synthetic explanation for the discovery UI.';
const captureFailure = 'The explanation was saved. Learner memory capture will retry later.';
const discovered = { topic_id: 'T08', topic_label: 'Chronic kidney disease', provider: 'europe-pmc',
  queried_at: '2026-10-04T21:00:00Z', verification: 'discovery-only', passage_evidence: false, latest_final_verified: false,
  records: [{ id: 'MED:10001', title: 'Synthetic CKD article', url: 'https://pubmed.ncbi.nlm.nih.gov/10001/',
    authors: 'Synthetic Author', publication_date: '2026-09-01', doi: '10.0000/synthetic' }] };
const thread = { id: 'synthetic-thread', title: 'Resume synthetic study', topic_id: 'T08', teaching_style: 'direct', updated_at: '2026-10-04T20:00:00Z', messages: [] };
const json = (value: unknown) => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } });

function events(runId = 'synthetic-run') {
  let controller!: ReadableStreamDefaultController<Uint8Array>, sequence = 0;
  const cancelled = vi.fn();
  const response = new Response(new ReadableStream<Uint8Array>({ start(value) { controller = value; }, cancel: cancelled }), { headers: { 'Content-Type': 'text/event-stream' } });
  return { response, cancelled,
    emit(type: string, payload: Record<string, unknown> = {}) {
      const newline = String.fromCharCode(10);
      controller.enqueue(new TextEncoder().encode('event: ' + type + newline + 'data: ' + JSON.stringify({ run_id: runId, sequence: ++sequence, type, payload }) + newline + newline));
    },
    close() { controller.close(); },
  };
}
function transport(streams: ReturnType<typeof events>[]) {
  const pending = [...streams];
  const fetch = vi.fn(async (path: string, options: RequestInit) => {
    if (path === '/api/v1/learn/ask') {
      const stream = pending.shift();
      if (!stream) throw new Error('No controlled stream remains.');
      return stream.response;
    }
    if (path === '/api/v1/content/topics') return json([{ id: 'T08', label: 'Chronic kidney disease' }]);
    if (path === '/api/v1/learn/threads') return json({ threads: [thread] });
    if (path === '/api/v1/learn/threads/' + thread.id) return json(thread);
    if (path.endsWith('/cancel')) return json({ state: 'cancelled' });
    if (path.startsWith('/api/v1/cases/sessions/') && path.endsWith('/handoff')) return json({ id: 'synthetic-ticket' });
    if (path.startsWith('/api/v1/cases/sessions/')) return json({ revision: 1 });
    if (path.startsWith('/api/v1/cases/handoffs/')) return new Response(null, { status: 204 });
    throw new Error('Unexpected endpoint in controlled UI tests: ' + path + ' ' + options.method);
  });
  vi.stubGlobal('fetch', fetch);
  return fetch;
}
function Route({ scope }: { scope?: ContextScope }) {
  const navigation = useNavigation();
  const [ready, setReady] = useState(!scope);
  useEffect(() => { if (scope) navigation.navigate('learn', { scope }); setReady(true); }, []);
  if (!ready) return null;
  return navigation.route === 'learn' ? <Learn /> : <output aria-label="Library handoff">{JSON.stringify({ scope: navigation.scope, handoff: navigation.handoff })}</output>;
}
function open(scope?: ContextScope) {
  window.location.hash = '#/learn';
  return render(<NavigationProvider><Route scope={scope} /></NavigationProvider>);
}
async function ask(fetch: ReturnType<typeof transport>) {
  const count = fetch.mock.calls.filter(([path]) => path === '/api/v1/learn/ask').length;
  fireEvent.change(screen.getByRole('textbox', { name: /Your nephrology question|Your follow-up/ }), { target: { value: 'SYNTHETIC_QUESTION_NO_HANDOFF_OR_URL_4519' } });
  fireEvent.click(screen.getByRole('button', { name: 'Ask Renulus' }));
  await waitFor(() => expect(fetch.mock.calls.filter(([path]) => path === '/api/v1/learn/ask')).toHaveLength(count + 1));
}
async function finish(source: ReturnType<typeof events>) {
  await act(async () => { source.emit('delta', { text: answer }); source.emit('completed'); source.close(); });
  await screen.findAllByText(answer);
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Stop' })).toBeNull());
}
afterEach(() => { cleanup(); delete window.renulus; vi.unstubAllGlobals(); window.localStorage.clear(); window.sessionStorage.clear(); });

describe('Learn literature discovery stays separate from evidence and memory', () => {
  it.each(['before', 'after'] as const)('discloses metadata without turning it into citations when memory arrives %s discovery', async order => {
    const source = events(); const fetch = transport([source]); open(); await ask(fetch);
    await act(async () => {
      source.emit('sources', { citations: [] });
      if (order === 'before') source.emit('memory', { count: 1 });
      source.emit('discovered-literature', discovered);
      if (order === 'after') source.emit('memory', { count: 1 });
      source.emit('memory-capture-unavailable', { message: captureFailure });
    });
    await finish(source);
    const literature = screen.getByRole('region', { name: 'Discovered literature' });
    const link = within(literature).getByRole('link', { name: 'Synthetic CKD article' });
    expect(link.getAttribute('href')).toBe(discovered.records[0].url);
    expect(link.getAttribute('rel')).toBe('noopener noreferrer');
    expect(within(literature).getByText('2026-10-04T21:00:00Z')).toBeDefined();
    expect(within(literature).getByText('Published 2026-09-01 · Synthetic Author')).toBeDefined();
    expect(within(literature).getByText('DOI: 10.0000/synthetic')).toBeDefined();
    expect(within(literature).getByText(/Topic search results do not verify this explanation/)).toBeDefined();
    expect(screen.getByRole('status', { name: 'Scientific evidence' }).textContent).toContain('No evidence retrieved · answer not source-verified');
    expect(screen.getByRole('region', { name: 'Retained learner context' })).toBeDefined();
    expect(screen.getByRole('region', { name: 'Learner memory capture' }).textContent).toContain(captureFailure);
    expect(screen.queryByRole('button', { name: /^Source / })).toBeNull();
    expect(screen.queryByText('Retrieved evidence')).toBeNull();
    expect(fetch.mock.calls.some(([path]) => path.includes('/retrieval/') || path.startsWith('https:'))).toBe(false);
  });

  it('preserves local retrieval failure across empty sources and successful topic discovery', async () => {
    const source = events(); const fetch = transport([source]); open(); await ask(fetch);
    await act(async () => { source.emit('retrieval-failed'); source.emit('sources', { citations: [] }); source.emit('discovered-literature', discovered); });
    await finish(source);
    expect(screen.getByRole('status', { name: 'Scientific evidence' }).textContent).toContain('Evidence retrieval unavailable · answer not source-verified');
    expect(screen.getByRole('link', { name: 'Synthetic CKD article' })).toBeDefined();
    expect(screen.queryByRole('button', { name: /^Source / })).toBeNull();
  });

  it('keeps discovery failure compatible with completion and hands only a canonical topic to Library', async () => {
    const source = events(); const fetch = transport([source]); open();
    expect(await screen.findByRole('option', { name: 'Chronic kidney disease' })).toBeDefined();
    await ask(fetch);
    await act(async () => { source.emit('sources', { citations: [] }); source.emit('memory', { count: 1 }); source.emit('literature-discovery-unavailable', { topic_id: 'T08', topic_label: 'Chronic kidney disease', message: 'Synthetic Europe PMC unavailable. Try topic discovery in Library.' }); });
    await finish(source);
    expect(screen.getByRole('region', { name: 'Discovered literature' }).textContent).toContain('Synthetic Europe PMC unavailable');
    expect(screen.getByRole('status', { name: 'Scientific evidence' }).textContent).toContain('answer not source-verified');
    expect(screen.getByRole('region', { name: 'Retained learner context' })).toBeDefined();
    expect(screen.queryByRole('heading', { name: 'The explanation could not finish' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Discover this topic in Library' }));
    const handoff = await screen.findByRole('status', { name: 'Library handoff' });
    expect(JSON.parse(handoff.textContent!)).toEqual({ scope: { kind: 'personal-library' }, handoff: { mode: 'discover', topic_id: 'T08' } });
    expect(window.location.hash).toBe('#/library');
    expect(window.localStorage.length).toBe(0); expect(window.sessionStorage.length).toBe(0);
  });

  it('shows an honest empty discovery state with a Library action', async () => {
    const source = events(); const fetch = transport([source]); open(); await ask(fetch);
    await act(async () => { source.emit('sources', { citations: [] }); source.emit('discovered-literature', { ...discovered, records: [] }); });
    await finish(source);
    expect(screen.getByText('No literature records were found for this topic.')).toBeDefined();
    expect(screen.getByRole('button', { name: 'Discover this topic in Library' })).toBeDefined();
    expect(screen.queryByRole('link')).toBeNull();
    expect(screen.getByRole('status', { name: 'Scientific evidence' }).textContent).toContain('answer not source-verified');
  });

  it.each(['temporary-case', 'unclassified', 'saved-case'] as const)('ignores discovery metadata and failures in %s', async kind => {
    const source = events(); const fetch = transport([source]); open({ kind, entity_id: 'synthetic-case' }); await ask(fetch);
    await act(async () => { source.emit('discovered-literature', discovered); source.emit('literature-discovery-unavailable', { topic_id: 'T08', topic_label: 'SYNTHETIC_EXCLUDED_DISCOVERY', message: 'SYNTHETIC_EXCLUDED_FAILURE' }); source.emit('sources', { citations: [] }); });
    await finish(source);
    expect(screen.queryByRole('region', { name: 'Discovered literature' })).toBeNull();
    expect(screen.queryByRole('link', { name: 'Synthetic CKD article' })).toBeNull();
    expect(screen.queryByText('SYNTHETIC_EXCLUDED_DISCOVERY')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Discover this topic in Library' })).toBeNull();
    expect(window.localStorage.length).toBe(0); expect(window.sessionStorage.length).toBe(0);
  });

  it.each(['fresh', 'resume', 'run'] as const)('clears discovery and memory when starting %s', async action => {
    const first = events(), next = events('synthetic-next-run'); const fetch = transport([first, next]); open(); await ask(fetch);
    await act(async () => { first.emit('sources', { citations: [] }); first.emit('discovered-literature', discovered); first.emit('memory', { count: 1 }); });
    await finish(first);
    expect(screen.getByRole('region', { name: 'Discovered literature' })).toBeDefined();
    if (action === 'fresh') fireEvent.click(screen.getByRole('button', { name: 'New study' }));
    if (action === 'resume') fireEvent.click(await screen.findByRole('button', { name: /^Resume synthetic study/ }));
    if (action === 'run') await ask(fetch);
    expect(screen.queryByRole('region', { name: 'Discovered literature' })).toBeNull();
    expect(screen.queryByRole('region', { name: 'Retained learner context' })).toBeNull();
    if (action === 'run') await finish(next);
  });

  it('cancels a waiting stream without inventing a discovered or checked source', async () => {
    const source = events(); const fetch = transport([source]); open(); await ask(fetch);
    await act(async () => { source.emit('started'); source.emit('sources', { citations: [] }); source.emit('memory', { count: 1 }); });
    await screen.findByText('Using 1 retained learning record to personalize this explanation.');
    fireEvent.click(screen.getByRole('button', { name: 'Stop' }));
    await waitFor(() => expect(source.cancelled).toHaveBeenCalled());
    expect(screen.getByRole('status', { name: 'Explanation status' }).textContent).toBe('Stopped · partial explanation not saved');
    expect(screen.queryByRole('region', { name: 'Discovered literature' })).toBeNull();
    expect(screen.queryByRole('button', { name: /^Source / })).toBeNull();
    expect(screen.getByRole('status', { name: 'Scientific evidence' }).textContent).toContain('answer not source-verified');
    expect(screen.getByRole('region', { name: 'Retained learner context' })).toBeDefined();
  });

  it('keeps unsupported source URLs as plain titles and reports a retraction without claiming review', async () => {
    const source = events(); const fetch = transport([source]); open(); await ask(fetch);
    await act(async () => source.emit('discovered-literature', { ...discovered, records: [
      { id: 'unsafe-1', title: 'Synthetic unsupported URL', url: 'javascript:alert(1)' },
      { id: 'unsafe-2', title: 'Synthetic local URL', url: 'https://127.0.0.1/private' },
      { id: 'unsafe-3', title: 'Synthetic retracted record', url: 'https://user:password@pubmed.ncbi.nlm.nih.gov/10001/', retracted: true },
    ] }));
    await finish(source);
    const literature = screen.getByRole('region', { name: 'Discovered literature' });
    expect(within(literature).queryByRole('link')).toBeNull();
    expect(within(literature).getByText('Synthetic unsupported URL')).toBeDefined();
    expect(within(literature).getByText('Retraction reported')).toBeDefined();
    expect(within(literature).getAllByText('Published date unavailable')).toHaveLength(3);
    expect(within(literature).getByText(/publication status and permissions have not been reviewed here/)).toBeDefined();
  });

  it.each(['success', 'failure'] as const)('uses the optional native bridge and keeps source opening %s separate from verification', async outcome => {
    const openSource = vi.fn(async () => { if (outcome === 'failure') throw new Error('Synthetic native opening failure'); });
    window.renulus = { openAuthorization: async () => {}, version: async () => 'synthetic', ...{ openSource } };
    const source = events(); const fetch = transport([source]); open(); await ask(fetch);
    await act(async () => { source.emit('sources', { citations: [] }); source.emit('discovered-literature', discovered); source.emit('memory', { count: 1 }); });
    await finish(source);
    fireEvent.click(screen.getByRole('link', { name: 'Synthetic CKD article' }));
    await waitFor(() => expect(openSource).toHaveBeenCalledWith(discovered.records[0].url));
    if (outcome === 'failure') expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'The source link could not open. Try again or discover this topic in Library.');
    else expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.getByRole('status', { name: 'Scientific evidence' }).textContent).toContain('answer not source-verified');
    expect(screen.getByRole('region', { name: 'Retained learner context' })).toBeDefined();
    expect(screen.queryByRole('heading', { name: 'The explanation could not finish' })).toBeNull();
  });
});
