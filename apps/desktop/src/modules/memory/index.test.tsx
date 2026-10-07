// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { useEffect, useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { NavigationProvider, useNavigation } from '../../shell/navigation';
import type { ContextScope } from '../../platform/contracts';
import Memory from './index';
import type { Fact, FactHistory, MemoryJob, MemoryStatus } from './types';

// Synthetic HTTP fixtures exercise the real renderer transport; they are not Mem0 producer evidence.
const retained: Fact = { id: 'synthetic-learning', text: 'Review the mechanisms of transplant rejection.', kind: 'learning-point', topic_id: 'transplantation', revision: 1, source_kind: 'manual', source_id: null, created_at: '2026-10-04T19:00:00Z', updated_at: '2026-10-04T19:00:00Z', index_state: 'ready' };
const readyStatus: MemoryStatus = { index: { ready: true, state: 'ready' }, pending_jobs: 0, producer: 'mem0-oss', automatic_capture: false };
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
type Handler = (path: string, options: RequestInit) => Promise<Response> | Response | undefined;
function transport(handler: Handler = () => undefined) {
  const fetch = vi.fn(async (path: string, options: RequestInit) => {
    const response = await handler(path, options);
    if (response) return response;
    if (path === '/api/v1/memory/facts') return json({ records: [retained] });
    if (path === '/api/v1/memory/status') return json(readyStatus);
    if (path === '/api/v1/memory/jobs') return json({ jobs: [] });
    if (path === '/api/v1/content/topics') return json([{ id: 'transplantation', title: 'Transplantation' }]);
    throw new Error('Unexpected synthetic endpoint: ' + path);
  });
  vi.stubGlobal('fetch', fetch);
  return fetch;
}
function open() { window.location.hash = '#/memory'; return render(<NavigationProvider><Memory /></NavigationProvider>); }
function factItem(text = retained.text) { return screen.getByText(text).closest('article')!; }
function body(options: RequestInit) { return JSON.parse(options.body as string); }
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(accept => { resolve = accept; }); return { promise, resolve }; }
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.localStorage.clear(); window.sessionStorage.clear(); });

describe('Learning memory API page', () => {
  it('keeps keyboard context through deletion confirmation, failure, cancellation and success', async () => {
    let attempts = 0;
    transport((path, options) => {
      if (options.method === 'DELETE' && path.includes('/memory/facts/')) {
        if (++attempts === 1) return json({ error: { code: 'busy', message: 'Synthetic deletion unavailable.', retryable: true } }, 503);
        return json({ deleted: true, purge_pending: false });
      }
    });
    open(); await screen.findByText(retained.text);
    const remove = screen.getByRole('button', { name: 'Delete' }); remove.focus(); fireEvent.click(remove);
    expect(document.activeElement).toBe(screen.getByRole('group', { name: 'Confirm learning deletion' }));
    expect(document.getElementById(remove.getAttribute('aria-describedby')!)?.textContent).toBe(retained.text);
    fireEvent.click(screen.getByRole('button', { name: 'Delete learning and history' }));
    await screen.findByText('Synthetic deletion unavailable.');
    fireEvent.click(screen.getByRole('button', { name: 'Keep learning' }));
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Delete' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete learning and history' }));
    await screen.findByText('Learning and its history removed.');
    expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Retained learning' }));
    expect(screen.queryByText(retained.text)).toBeNull();
  });

  it('focuses history confirmation and restores its surviving history control', async () => {
    transport((path, options) => {
      if (path.endsWith('/history')) return options.method === 'DELETE' ? json({ purge_pending: false })
        : json({ history: [{ revision: 1, event: 'created', text: 'Synthetic earlier wording.', created_at: retained.created_at }] });
    });
    open(); await screen.findByText(retained.text);
    fireEvent.click(screen.getByRole('button', { name: 'History' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Remove history' }));
    expect(document.activeElement).toBe(screen.getByRole('group', { name: 'Confirm history removal' }));
    fireEvent.click(screen.getByRole('button', { name: 'Keep history' }));
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Hide history' }));
    fireEvent.click(screen.getByRole('button', { name: 'Remove history' }));
    fireEvent.click(screen.getByRole('button', { name: 'Remove revision history' }));
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Hide history' })));
  });
  it('shows actual records, source/history affordances and reported capability state', async () => {
    transport(); open();
    await screen.findByText(retained.text);
    expect(screen.getByRole('heading', { name: 'Learning memory' })).toBeDefined();
    expect(screen.getByText('Ready for recall')).toBeDefined();
    expect(screen.getByText('Automatic capture is off. You can retain learning manually.')).toBeDefined();
    expect(within(factItem()).getByText('Provenance')).toBeDefined();
    expect(screen.queryByText('Make room for what you learn')).toBeNull();
  });

  it('keeps a failed add draft and uses the same idempotency key for an unchanged retry', async () => {
    let records = [retained]; const writes: Record<string, unknown>[] = [];
    const fetch = transport((path, options) => {
      if (path === '/api/v1/memory/facts' && options.method === 'POST') {
        const sent = body(options); writes.push(sent);
        if (writes.length === 1) return json({ error: { code: 'synthetic_busy', message: 'Synthetic worker unavailable.', retryable: true } }, 503);
        const added = { ...retained, id: 'synthetic-goal', text: sent.text, kind: sent.kind, topic_id: sent.topic_id }; records = [added, retained]; return json(added);
      }
      if (path === '/api/v1/memory/facts') return json({ records });
    });
    open(); await screen.findByText(retained.text);
    fireEvent.click(screen.getByRole('button', { name: 'Add learning' }));
    await screen.findByRole('option', { name: 'Transplantation' });
    fireEvent.change(screen.getByLabelText('Learning to retain'), { target: { value: 'Compare dialysis modalities during review.' } });
    fireEvent.change(screen.getByLabelText('Kind of learning'), { target: { value: 'goal' } });
    fireEvent.change(screen.getByLabelText('Topic'), { target: { value: 'transplantation' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save learning' }));
    await screen.findByText('Synthetic worker unavailable.');
    expect((screen.getByLabelText('Learning to retain') as HTMLTextAreaElement).value).toBe('Compare dialysis modalities during review.');
    fireEvent.click(screen.getByRole('button', { name: 'Save learning' }));
    await screen.findByText('Compare dialysis modalities during review.');
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Add learning' })));
    expect(writes).toHaveLength(2); expect(writes[0]).toEqual(writes[1]);
    expect(writes[0]).toMatchObject({ scope: { kind: 'study' }, kind: 'goal', topic_id: 'transplantation' });
    expect(typeof writes[0].idempotency_key).toBe('string');
    expect(fetch.mock.calls.every(([path]) => !path.includes('Compare'))).toBe(true);
    expect(window.localStorage.length).toBe(0); expect(window.sessionStorage.length).toBe(0);
  });

  it('preserves the edit draft on a revision conflict and requires review of the new revision', async () => {
    let record = retained; const writes: Record<string, unknown>[] = [];
    transport((path, options) => {
      if (path === '/api/v1/memory/facts') return json({ records: [record] });
      if (path === '/api/v1/memory/facts/' + retained.id && options.method === 'PATCH') {
        const sent = body(options); writes.push(sent);
        if (writes.length === 1) { record = { ...retained, text: 'A newer retained lesson.', revision: 2 }; return json({ error: { code: 'revision_conflict', message: 'The saved revision changed.', retryable: false } }, 409); }
        record = { ...record, text: sent.text, revision: 3 }; return json(record);
      }
    });
    open(); await screen.findByText(retained.text);
    fireEvent.click(within(factItem()).getByRole('button', { name: 'Edit' }));
    fireEvent.change(screen.getByLabelText('Edit retained learning'), { target: { value: 'My revised transplant lesson.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
    await screen.findByRole('button', { name: 'Refresh records' });
    fireEvent.click(screen.getByRole('button', { name: 'Refresh records' }));
    await screen.findByRole('button', { name: 'Use latest revision' });
    expect((screen.getByLabelText('Edit retained learning') as HTMLTextAreaElement).value).toBe('My revised transplant lesson.');
    expect((screen.getByRole('button', { name: 'Save changes' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Use latest revision' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
    await screen.findByText('My revised transplant lesson.');
    expect(writes.map(write => write.expected_revision)).toEqual([1, 2]);
    expect(screen.queryByLabelText('Edit retained learning')).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(within(factItem('My revised transplant lesson.')).getByRole('button', { name: 'Edit' })));
  });

  it('returns keyboard focus to stable add and edit controls after cancellation', async () => {
    transport(); open(); await screen.findByText(retained.text);
    fireEvent.click(screen.getByRole('button', { name: 'Add learning' }));
    expect(document.activeElement).toBe(screen.getByLabelText('Learning to retain'));
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Add learning' }));
    fireEvent.click(within(factItem()).getByRole('button', { name: 'Edit' }));
    expect(document.activeElement).toBe(screen.getByLabelText('Edit retained learning'));
    fireEvent.click(screen.getByRole('button', { name: 'Cancel edit' }));
    expect(document.activeElement).toBe(within(factItem()).getByRole('button', { name: 'Edit' }));
  });

  it('explains unavailable local search and disables recovery that cannot restore missing helpers', async () => {
    const fetch = transport(path => path === '/api/v1/memory/status' ? json({ ...readyStatus, index: { ready: false, state: 'failed', helper_ready: false, message: 'Synthetic missing installation assets.' } }) : undefined);
    open(); await screen.findByText(retained.text);
    await screen.findByText(/Local search is unavailable/);
    const details = screen.getByText('Recall details').closest('details')!;
    expect(details.open).toBe(false);
    expect(within(details).getByText('Synthetic missing installation assets.')).toBeDefined();
    expect((screen.getByRole('button', { name: 'Retry pending jobs' }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole('button', { name: 'Rebuild recall index' }) as HTMLButtonElement).disabled).toBe(true);
    expect((within(factItem()).getByRole('button', { name: 'Edit' }) as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'Refresh memory status' }));
    await waitFor(() => expect(fetch.mock.calls.filter(([path]) => path.endsWith('/status')).length).toBeGreaterThan(1));
    expect(fetch.mock.calls.some(([path]) => path.endsWith('/retry') || path.endsWith('/reindex'))).toBe(false);
  });

  it('purges history separately and deletes only after inline confirmation with the reviewed revision', async () => {
    let records = [retained]; let history: FactHistory[] = [{ revision: 1, text: 'SYNTHETIC_HISTORY_ONLY', event: 'created', created_at: retained.created_at }];
    const fetch = transport((path, options) => {
      if (path === '/api/v1/memory/facts') return json({ records });
      if (path.endsWith('/' + retained.id + '/history')) {
        if (options.method === 'DELETE') { history = []; return json({ purged: true, purge_pending: false }); }
        return json({ history });
      }
      if (path === '/api/v1/memory/facts/' + retained.id + '?expected_revision=1' && options.method === 'DELETE') { records = []; return json({ deleted: true, purge_pending: true }); }
      if (path === '/api/v1/memory/reindex') return json({ ready: true, count: records.length });
    });
    open(); await screen.findByText(retained.text);
    fireEvent.click(within(factItem()).getByRole('button', { name: 'History' }));
    await screen.findByText('SYNTHETIC_HISTORY_ONLY');
    fireEvent.click(screen.getByRole('button', { name: 'Remove history' }));
    expect(fetch.mock.calls.some(([, options]) => options.method === 'DELETE')).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'Remove revision history' }));
    await screen.findByText('No revision history is retained.');
    expect(screen.getByText(retained.text)).toBeDefined(); expect(screen.queryByText('SYNTHETIC_HISTORY_ONLY')).toBeNull();
    fireEvent.click(within(factItem()).getByRole('button', { name: 'Delete' }));
    expect(fetch.mock.calls.filter(([path, options]) => path.includes('expected_revision') && options.method === 'DELETE')).toHaveLength(0);
    fireEvent.click(screen.getByRole('button', { name: 'Delete learning and history' }));
    await screen.findByText('Learning removed from recall. Index cleanup is pending.');
    await screen.findByText('Make room for what you learn');
    fireEvent.click(screen.getByRole('button', { name: 'Rebuild recall index' }));
    await screen.findByText('Index rebuilt from 0 retained records.');
    expect(screen.queryByText(retained.text)).toBeNull();
    expect(fetch.mock.calls.filter(([path, options]) => path.endsWith('/history') && options.method === 'DELETE')).toHaveLength(1);
  });

  it('blocks deletion if the record changes while its confirmation is open', async () => {
    let record = retained; const fetch = transport((path) => path === '/api/v1/memory/facts' ? json({ records: [record] }) : undefined);
    open(); await screen.findByText(retained.text);
    fireEvent.click(within(factItem()).getByRole('button', { name: 'Delete' }));
    record = { ...retained, text: 'Updated externally.', revision: 2 };
    fireEvent.click(screen.getByRole('button', { name: 'Refresh memory status' }));
    await screen.findByText('Updated externally.');
    expect((screen.getByRole('button', { name: 'Delete learning and history' }) as HTMLButtonElement).disabled).toBe(true);
    expect(fetch.mock.calls.some(([, options]) => options.method === 'DELETE')).toBe(false);
  });

  it('does not restore a deleted record from a superseded list refresh', async () => {
    const pending = deferred<Response>(); let reads = 0; let removed = false; let signal: AbortSignal | null | undefined;
    transport((path, options) => {
      if (path === '/api/v1/memory/facts') {
        reads += 1;
        if (reads === 2) { signal = options.signal; return pending.promise; }
        return json({ records: removed ? [] : [retained] });
      }
      if (path.includes('?expected_revision=1') && options.method === 'DELETE') { removed = true; return json({ deleted: true, purge_pending: false }); }
    });
    open(); await screen.findByText(retained.text);
    fireEvent.click(screen.getByRole('button', { name: 'Refresh memory status' }));
    await waitFor(() => expect(signal).toBeDefined());
    fireEvent.click(within(factItem()).getByRole('button', { name: 'Delete' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete learning and history' }));
    await screen.findByText('Make room for what you learn');
    expect(signal?.aborted).toBe(true);
    await act(async () => pending.resolve(json({ records: [retained] })));
    expect(screen.queryByText(retained.text)).toBeNull();
  });

  it('keeps history visible after a failed purge and can retry the same confirmation', async () => {
    let history: FactHistory[] = [{ revision: 1, text: 'SYNTHETIC_HISTORY_RETRY', event: 'created', created_at: retained.created_at }]; let attempts = 0;
    transport((path, options) => {
      if (path.endsWith('/history')) {
        if (options.method === 'DELETE') {
          attempts += 1;
          if (attempts === 1) return json({ error: { code: 'synthetic_purge', message: 'Synthetic history purge failed.', retryable: true } }, 503);
          history = []; return json({ purged: true, purge_pending: false });
        }
        return json({ history });
      }
    });
    open(); await screen.findByText(retained.text); fireEvent.click(within(factItem()).getByRole('button', { name: 'History' }));
    await screen.findByText('SYNTHETIC_HISTORY_RETRY'); fireEvent.click(screen.getByRole('button', { name: 'Remove history' }));
    fireEvent.click(screen.getByRole('button', { name: 'Remove revision history' }));
    await screen.findByText('Synthetic history purge failed.');
    expect(screen.getByText('SYNTHETIC_HISTORY_RETRY')).toBeDefined(); expect(screen.queryByLabelText('Loading revision history')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Remove revision history' }));
    await screen.findByText('No revision history is retained.'); expect(attempts).toBe(2);
  });

  it('reports an edit cleanup still pending and immediately refreshes index status', async () => {
    let record = retained; let edited = false;
    transport((path, options) => {
      if (path === '/api/v1/memory/facts') return json({ records: [record] });
      if (path === '/api/v1/memory/status' && edited) return json({ ...readyStatus, index: { ready: false, state: 'failed', error_code: 'memory_purge_pending' } });
      if (path === '/api/v1/memory/facts/' + retained.id && options.method === 'PATCH') { edited = true; record = { ...retained, text: body(options).text, revision: 2, index_state: 'pending', purge_pending: true }; return json(record); }
    });
    open(); await screen.findByText(retained.text); fireEvent.click(within(factItem()).getByRole('button', { name: 'Edit' }));
    fireEvent.change(screen.getByLabelText('Edit retained learning'), { target: { value: 'Revised learning with pending cleanup.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
    await screen.findByText('Learning saved. Recall cleanup is pending.'); await screen.findByText('Recall unavailable');
    expect(screen.getByText('Revised learning with pending cleanup.')).toBeDefined();
  });

  it('sends search in a study POST body and ignores superseded results even if transport resolves after abort', async () => {
    const old = deferred<Response>(); let oldSignal: AbortSignal | null | undefined;
    const match = { ...retained, id: 'synthetic-dialysis', text: 'Compare haemodialysis with peritoneal dialysis.' };
    const fetch = transport((path, options) => {
      if (path === '/api/v1/memory/search') {
        if (body(options).query === 'transplant') { oldSignal = options.signal; return old.promise; }
        return json({ records: [match], context: 'SYNTHETIC_CURRENT_CONTEXT' });
      }
    });
    open(); await screen.findByText(retained.text);
    fireEvent.change(screen.getByRole('searchbox', { name: 'Search retained learning' }), { target: { value: 'transplant' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    await waitFor(() => expect(oldSignal).toBeDefined());
    fireEvent.change(screen.getByRole('searchbox', { name: 'Search retained learning' }), { target: { value: 'dialysis' } });
    expect(oldSignal?.aborted).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    await screen.findByText(match.text);
    await act(async () => { old.resolve(json({ records: [{ ...retained, text: 'SYNTHETIC_STALE_FACT' }], context: 'SYNTHETIC_STALE_CONTEXT' })); });
    expect(screen.queryByText('SYNTHETIC_STALE_FACT')).toBeNull(); expect(screen.queryByText('SYNTHETIC_STALE_CONTEXT')).toBeNull();
    expect(screen.getByText('SYNTHETIC_CURRENT_CONTEXT')).toBeDefined();
    const calls = fetch.mock.calls.filter(([path]) => path === '/api/v1/memory/search');
    expect(calls.map(([, options]) => body(options))).toEqual([{ query: 'transplant', scope: { kind: 'study' }, limit: 10 }, { query: 'dialysis', scope: { kind: 'study' }, limit: 10 }]);
    fireEvent.click(screen.getByRole('button', { name: 'Clear search' }));
    await screen.findByText(retained.text); expect(screen.queryByText('SYNTHETIC_CURRENT_CONTEXT')).toBeNull();
  });

  it('does not claim cancellation when the backend reports the job already completed', async () => {
    let job: MemoryJob = { id: 'synthetic-job', state: 'running' };
    transport((path) => {
      if (path === '/api/v1/memory/jobs') return json({ jobs: [job] });
      if (path === '/api/v1/memory/jobs/synthetic-job/cancel') { job = { ...job, state: 'completed' }; return json(job); }
    });
    open(); await screen.findByText(retained.text);
    fireEvent.click(screen.getByText('Memory jobs (1)'));
    fireEvent.click(screen.getByRole('button', { name: 'Cancel job' }));
    await screen.findByText('Job is completed.');
    expect(screen.queryByText('Job cancelled.')).toBeNull(); expect(screen.queryByRole('button', { name: 'Cancel job' })).toBeNull();
  });

  it('shows producer errors honestly and uses actual retry and reindex results', async () => {
    let status: MemoryStatus = { ...readyStatus, index: { ready: false, state: 'helper-missing', message: 'Synthetic offline helper is unavailable.' } };
    let reindexes = 0; const fetch = transport((path) => {
      if (path === '/api/v1/memory/status') return json(status);
      if (path === '/api/v1/memory/retry') return json({ processed: 2 });
      if (path === '/api/v1/memory/reindex') {
        reindexes += 1;
        if (reindexes === 1) return json({ error: { code: 'index_unavailable', message: 'Synthetic offline helper is unavailable.', retryable: true } }, 503);
        status = readyStatus; return json({ ready: true, count: 1 });
      }
    });
    open(); await screen.findByText(retained.text); await screen.findByText('Recall unavailable');
    fireEvent.click(screen.getByRole('button', { name: 'Rebuild recall index' }));
    await screen.findByRole('heading', { name: 'Index could not be rebuilt' });
    expect(screen.queryByText('Index rebuilt from 1 retained record.')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Retry pending jobs' }));
    await screen.findByText('Retry processed 2 jobs.');
    fireEvent.click(screen.getByRole('button', { name: 'Rebuild recall index' }));
    await screen.findByText('Index rebuilt from 1 retained record.'); await screen.findByText('Ready for recall');
    expect(fetch.mock.calls.filter(([path, options]) => (path.endsWith('/reindex') || path.endsWith('/retry')) && options.method === 'POST')).toHaveLength(3);
  });

  it('keeps existing records visible when a refresh fails', async () => {
    let fail = false; transport(path => path === '/api/v1/memory/facts' && fail ? json({ error: { code: 'synthetic_refresh', message: 'Synthetic refresh failed.', retryable: true } }, 503) : undefined);
    open(); await screen.findByText(retained.text); fail = true;
    fireEvent.click(screen.getByRole('button', { name: 'Refresh memory status' }));
    await screen.findByText('Synthetic refresh failed.'); expect(screen.getByText(retained.text)).toBeDefined();
  });

  it('does not allow a late history read to repopulate a closed history view', async () => {
    const pending = deferred<Response>(); let signal: AbortSignal | null | undefined;
    transport((path, options) => { if (path.endsWith('/history')) { signal = options.signal; return pending.promise; } });
    open(); await screen.findByText(retained.text);
    fireEvent.click(within(factItem()).getByRole('button', { name: 'History' }));
    await waitFor(() => expect(signal).toBeDefined());
    fireEvent.click(screen.getByRole('button', { name: 'Hide history' })); expect(signal?.aborted).toBe(true);
    await act(async () => pending.resolve(json({ history: [{ revision: 1, text: 'SYNTHETIC_LATE_HISTORY', event: 'created', created_at: retained.created_at }] })));
    expect(screen.queryByText('SYNTHETIC_LATE_HISTORY')).toBeNull(); expect(screen.queryByRole('region', { name: 'Revision history' })).toBeNull();
  });

  it('aborts an in-flight write on unmount and ignores its late response', async () => {
    const pending = deferred<Response>(); let signal: AbortSignal | null | undefined;
    transport((path, options) => { if (path === '/api/v1/memory/reindex') { signal = options.signal; return pending.promise; } });
    const view = open(); await screen.findByText(retained.text);
    fireEvent.click(screen.getByRole('button', { name: 'Rebuild recall index' }));
    await waitFor(() => expect(signal).toBeDefined()); view.unmount(); expect(signal?.aborted).toBe(true);
    open(); await screen.findByText(retained.text);
    await act(async () => pending.resolve(json({ ready: true, count: 999 })));
    expect(screen.queryByText('Index rebuilt from 999 retained records.')).toBeNull();
  });
});

function ScopedMemory({ scope }: { scope: ContextScope }) {
  const nav = useNavigation(); const [mounted, setMounted] = useState(false);
  useEffect(() => { nav.navigate('memory', { scope, payload: { text: 'SYNTHETIC_CASE_SENTINEL' } }); setMounted(true); }, []);
  return mounted ? <Memory /> : null;
}
describe('memory scope exclusion', () => {
  it.each(['temporary-case', 'unclassified', 'saved-case'] as const)('never sends inherited %s input to memory', async kind => {
    const fetch = transport(); window.location.hash = '#/study';
    render(<NavigationProvider><ScopedMemory scope={{ kind, entity_id: 'synthetic-private-case' }} /></NavigationProvider>);
    await screen.findByRole('button', { name: 'Open memory in study context' });
    expect(fetch).not.toHaveBeenCalled(); expect(screen.queryByLabelText('Learning to retain')).toBeNull();
    expect(window.location.href).not.toContain('SYNTHETIC_CASE_SENTINEL');
    expect(window.localStorage.length).toBe(0); expect(window.sessionStorage.length).toBe(0);
    fireEvent.click(screen.getByRole('button', { name: 'Open memory in study context' }));
    await screen.findByText(retained.text);
    expect(JSON.stringify(fetch.mock.calls)).not.toContain('SYNTHETIC_CASE_SENTINEL');
    expect(JSON.stringify(fetch.mock.calls)).not.toContain('synthetic-private-case');
  });
});
