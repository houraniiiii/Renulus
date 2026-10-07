// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import BulkImportControl from './BulkImportControl';

const request = vi.fn<typeof fetch>();
const onBatch = vi.fn();
const onBusyChange = vi.fn();
function json(value: unknown, status = 202) { return new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } }); }
function batch(overrides: Record<string, unknown> = {}) { return { attempted: 3, accepted: 2, newly_queued: 2, rejected: 1, rejections: { article_permission_required: 1 }, remaining: 0, next_cursor: null, done: true, cancelled: false, ...overrides }; }
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(done => { resolve = done; }); return { promise, resolve }; }
const start = () => fireEvent.click(screen.getByRole('button', { name: 'Check and queue matching articles' }));
const body = (index: number) => JSON.parse(request.mock.calls[index][1]?.body as string);
beforeEach(() => { request.mockReset(); onBatch.mockReset(); onBusyChange.mockReset(); vi.stubGlobal('fetch', request); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function mount(disabled = false) { return render(<BulkImportControl query="dialysis" disabled={disabled} onBatch={onBatch} onBusyChange={onBusyChange} />); }

describe('deliberate collected article scans', () => {
  it('walks sequential bounded pages and distinguishes attention from queued imports', async () => {
    request.mockResolvedValueOnce(json(batch({ remaining: 4, next_cursor: 'next-page', done: false }))).mockResolvedValueOnce(json(batch({ attempted: 4, accepted: 2, newly_queued: 1, rejected: 2, rejections: { article_permission_required: 2 } })));
    mount(); start();
    await screen.findByText(/All matching pending articles in this scan were checked/);
    expect(request).toHaveBeenCalledTimes(2);
    expect(body(0)).toEqual({ source_id: 'L02', query: 'dialysis', limit: 100, cursor: null, scope: { kind: 'personal-library' } });
    expect(body(1).cursor).toBe('next-page');
    expect(screen.getByText(/7 articles checked · 3 added for processing · 3 need attention · 0 remaining/)).toBeTruthy();
    expect(screen.getByText('3 · Processing permission needs review')).toBeTruthy();
    expect(onBatch).toHaveBeenCalledTimes(2);
    expect(onBusyChange.mock.calls).toEqual([[true], [false]]);
  });

  it('pauses an in-flight page, ignores a late result, and resumes from the last reported cursor', async () => {
    const pending = deferred<Response>();
    request.mockResolvedValueOnce(json(batch({ remaining: 4, next_cursor: 'last-confirmed', done: false }))).mockReturnValueOnce(pending.promise);
    mount(); start(); await waitFor(() => expect(request).toHaveBeenCalledTimes(2));
    const signal = request.mock.calls[1][1]?.signal;
    fireEvent.click(screen.getByRole('button', { name: 'Pause article checks' }));
    expect(signal?.aborted).toBe(true);
    await act(async () => { pending.resolve(json(batch())); await pending.promise; });
    await screen.findByRole('button', { name: 'Resume article checks' });
    expect(onBatch).toHaveBeenCalledTimes(1);
    request.mockResolvedValueOnce(json(batch()));
    fireEvent.click(screen.getByRole('button', { name: 'Resume article checks' }));
    await screen.findByText(/All matching pending articles in this scan were checked/);
    expect(body(2).cursor).toBe('last-confirmed');
    expect(screen.getByText(/6 articles checked · 4 added for processing · 2 need attention/)).toBeTruthy();
  });

  it('retains the cursor and reported progress when a later page fails, then retries', async () => {
    request.mockResolvedValueOnce(json(batch({ remaining: 4, next_cursor: 'retry-here', done: false }))).mockResolvedValueOnce(json({ error: { code: 'unavailable', message: 'Synthetic runtime unavailable.', retryable: true } }, 503));
    mount(); start(); await screen.findByText('Synthetic runtime unavailable.');
    request.mockResolvedValueOnce(json(batch()));
    fireEvent.click(screen.getByRole('button', { name: 'Retry article checks' }));
    await screen.findByText(/All matching pending articles in this scan were checked/);
    expect(body(2).cursor).toBe('retry-here'); expect(onBatch).toHaveBeenCalledTimes(2);
  });

  it('aborts on navigation without reporting a late committed page as observed', async () => {
    const pending = deferred<Response>(); request.mockReturnValue(pending.promise);
    const view = mount(); start(); await waitFor(() => expect(request).toHaveBeenCalledTimes(1));
    const signal = request.mock.calls[0][1]?.signal; view.unmount(); expect(signal?.aborted).toBe(true);
    await act(async () => { pending.resolve(json(batch())); await pending.promise; });
    expect(onBatch).not.toHaveBeenCalled(); expect(onBusyChange.mock.calls).toEqual([[true], [false]]);
  });

  it('allows a fresh deliberate scan after completion without reusing an old cursor or totals', async () => {
    request.mockResolvedValueOnce(json(batch())).mockResolvedValueOnce(json(batch({ attempted: 0, accepted: 0, newly_queued: 0, rejected: 0, rejections: {} })));
    mount(); start(); await screen.findByRole('button', { name: 'Start another article scan' });
    fireEvent.click(screen.getByRole('button', { name: 'Start another article scan' }));
    await screen.findByText(/0 articles checked · 0 added for processing · 0 need attention · 0 remaining/);
    expect(body(1).cursor).toBeNull(); expect(screen.queryByText('3 · Processing permission needs review')).toBeNull();
  });

  it('stops a non-progressing response instead of looping indefinitely', async () => {
    request.mockResolvedValue(json(batch({ attempted: 0, accepted: 0, newly_queued: 0, rejected: 0, rejections: {}, remaining: 4, next_cursor: 'stuck', done: false })));
    mount(); start(); await screen.findByText('Article checks made no further progress. Refresh the catalogue and retry.');
    expect(request).toHaveBeenCalledTimes(1); expect(onBatch).not.toHaveBeenCalled();
  });

  it('rejects inconsistent counts and safely displays an unfamiliar prototype-named reason', async () => {
    request.mockResolvedValueOnce(json(batch({ rejections: { article_permission_required: 9 } }))).mockResolvedValueOnce(json(batch({ rejections: { constructor: 1 } })));
    mount(); start(); await screen.findByText('The article batch returned an incomplete result. Refresh the catalogue and try again.');
    expect(onBatch).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Retry article checks' }));
    await screen.findByText('1 · Inspection needs review (constructor)');
  });

  it('does not adopt collected articles when the containing scope is blocked', () => {
    mount(true); expect((screen.getByRole('button', { name: 'Check and queue matching articles' }) as HTMLButtonElement).disabled).toBe(true);
    start(); expect(request).not.toHaveBeenCalled();
  });
});
