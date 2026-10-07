// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ImportStatus from './ImportStatus';
import QueueStatus from './QueueStatus';
import type { ImportResult, LibraryDocument } from './types';

const source: LibraryDocument = { id: 'doc_synthetic', title: 'Synthetic glomerular source', source_id: 'SYNTHETIC', status: 'failed', reserved: false, active_revision: null, latest_revision: 'rev_synthetic', revisions: [], cleanup_pending: false };
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
const resultFor = (state: string): ImportResult => ({ document_id: source.id, revision_id: source.latest_revision!, status: state, job: { id: 'job_synthetic', revision_id: source.latest_revision!, state, phase: state === 'processing' ? 'extraction' : state, error_code: state === 'failed' ? 'extraction_failed' : null, error_message: state === 'failed' ? 'Synthetic extraction failed. Use an unencrypted original.' : null } });
const request = vi.fn<typeof fetch>();
let state: string;
const base = async (url: RequestInfo | URL) => String(url).endsWith('/import-status') ? json(resultFor(state)) : json({ ...source, status: state, active_revision: state === 'ready' ? source.latest_revision : null });
beforeEach(() => { state = 'failed'; request.mockReset().mockImplementation(base); vi.stubGlobal('fetch', request); });
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });
function mount() {
  const callbacks = { onDocument: vi.fn(), onLibraryChange: vi.fn(), onReimport: vi.fn() };
  const view = render(<ImportStatus document={source} disabled={false} {...callbacks} />);
  return { ...callbacks, ...view };
}

describe('Canonical import recovery', () => {
  it('shows the actual job error and offers deliberate reimport of the same document', async () => {
    const view = mount();
    await screen.findByText('Synthetic extraction failed. Use an unencrypted original.');
    expect(screen.getByText('Reason: extraction_failed')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Retry import' }));
    expect(view.onReimport).toHaveBeenCalledWith(source);
    expect(request.mock.calls.every(([, options]) => !options?.method)).toBe(true);
  });

  it('reads queued, extraction and terminal states without overlapping polls', async () => {
    vi.useFakeTimers(); state = 'queued';
    const view = mount();
    await act(async () => {});
    expect(screen.getByText(/This import is waiting/)).toBeTruthy();
    state = 'processing';
    await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
    expect(screen.getByText('Processing · Reading the original')).toBeTruthy();
    state = 'ready';
    await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
    expect(screen.getByText('Available')).toBeTruthy();
    expect(view.onDocument).toHaveBeenLastCalledWith({ ...source, status: 'ready', active_revision: source.latest_revision });
    expect(view.onLibraryChange).toHaveBeenCalledTimes(1);
    const count = request.mock.calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(12000); });
    expect(request).toHaveBeenCalledTimes(count);
  });

  it('does not cancel or replace a different returned revision', async () => {
    request.mockImplementation(async url => String(url).endsWith('/import-status') ? json({ ...resultFor('queued'), revision_id: 'rev_other' }) : base(url));
    const view = mount();
    await screen.findByText('The import changed while its status was loading. Refresh the document before trying again.');
    expect(screen.queryByRole('button', { name: 'Cancel this import' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Retry import' })).toBeNull();
    expect(view.onDocument).not.toHaveBeenCalled();
  });

  it('rechecks a state transition between the job and document reads before updating the reader', async () => {
    vi.useFakeTimers(); state = 'ready'; let changing = true;
    request.mockImplementation(async url => String(url).endsWith('/import-status') ? json(resultFor(state)) : changing ? json({ ...source, status: 'queued' }) : base(url));
    const view = mount(); await act(async () => {});
    expect(view.onDocument).not.toHaveBeenCalled();
    expect(screen.getByText('The import is changing state. Checking its latest status again.')).toBeTruthy();
    changing = false; await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(screen.getByText('Available')).toBeTruthy();
    expect(view.onDocument).toHaveBeenLastCalledWith({ ...source, status: 'ready', active_revision: source.latest_revision });
  });

  it('reads a publication that won a cancellation race as available', async () => {
    state = 'queued';
    request.mockImplementation(async (url, options) => {
      if (String(url).endsWith('/cancel')) { state = 'ready'; return json(resultFor(state).job); }
      return base(url);
    });
    mount();
    fireEvent.click(await screen.findByRole('button', { name: 'Cancel this import' }));
    await screen.findByText('Available');
    expect(screen.queryByText('Cancelled')).toBeNull();
    expect(request.mock.calls.filter(([, options]) => options?.method === 'POST').map(([url]) => url)).toEqual(['/api/v1/library/jobs/job_synthetic/cancel']);
  });

  it('keeps an unavailable status honest and retries the read without mutating the job', async () => {
    let fail = true;
    request.mockImplementation(async url => String(url).endsWith('/import-status') && fail ? json({ error: { code: 'unavailable', message: 'Synthetic status unavailable.', retryable: true } }, 503) : base(url));
    mount(); await screen.findByText('Synthetic status unavailable.');
    expect(screen.queryByText('Available')).toBeNull();
    fail = false; fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await screen.findByRole('button', { name: 'Retry import' });
    expect(request.mock.calls.every(([, options]) => !options?.method)).toBe(true);
  });

  it('aborts a superseded status and ignores a late result', async () => {
    let release!: (value: Response) => void;
    request.mockImplementation(async url => String(url).endsWith('/import-status') ? await new Promise(resolve => { release = resolve; }) : base(url));
    const view = mount();
    await waitFor(() => expect(release).toBeTypeOf('function'));
    const signal = request.mock.calls.find(([url]) => String(url).endsWith('/import-status'))![1]!.signal!;
    view.unmount();
    expect(signal.aborted).toBe(true);
    await act(async () => { release(json(resultFor('ready'))); });
    expect(view.onDocument).not.toHaveBeenCalled();
  });
});

describe('Actual queue state', () => {
  it.each([false, true])('reports the supplied count and running=%s without claiming jobs are searchable', async running => {
    request.mockResolvedValue(json({ running, cpu_workers: 1, active_job: running ? 'job_synthetic' : null, error_code: null, queued: 7 }));
    render(<QueueStatus />);
    await screen.findByText(running ? '7 imports waiting for processing. A document is being processed locally.' : '7 imports waiting for processing. Document processing is paused.');
    expect(request.mock.calls[0][0]).toBe('/api/v1/library/queue');
    expect(screen.queryByText(/searchable/)).toBeNull();
    if (!running) expect(screen.getByText(/Restart Renulus to resume/)).toBeTruthy();
  });

  it('rejects missing queue counts rather than inventing zero', async () => {
    request.mockResolvedValue(json({ running: true, cpu_workers: 1, active_job: null, error_code: null }));
    render(<QueueStatus />);
    await screen.findByText('Document processing returned an incomplete queue status. Refresh to check it again.');
    expect(screen.queryByText(/0 imports/)).toBeNull();
  });
});
