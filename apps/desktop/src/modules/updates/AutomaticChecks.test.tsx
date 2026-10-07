// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import AutomaticChecks, { type Schedule } from './AutomaticChecks';

const option = { kind: 'source' as const, id: 'K01', source_id: 'K01', title: 'KDIGO CKD', route: 'public publication links' };
const initial: Schedule = { enabled: false, cadence_hours: 24, selection: [], options: [option], jobs: [],
  running: false, next_due_at: null, last_run: null, max_batch: 5, max_selection: 20, max_retries: 2 };
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
function mockSchedule(start = initial) {
  let state = structuredClone(start);
  const fetch = vi.fn(async (path: string, options: RequestInit = {}) => {
    if (options.method === 'PUT') state = { ...state, ...JSON.parse(options.body as string) };
    if (path.endsWith('/check')) state = { ...state, running: true };
    if (path.endsWith('/cancel')) state = { ...state, running: false, last_run: { id: 'synthetic-run', trigger: 'manual',
      started_at: '2026-10-05T06:00:00Z', finished_at: '2026-10-05T06:01:00Z', state: 'cancelled', checked: 0, failed: 0, error_code: 'check_cancelled' } };
    return response(state);
  });
  vi.stubGlobal('fetch', fetch); return fetch;
}
async function openSettings() {
  await screen.findByLabelText('Check my selected sources automatically');
  fireEvent.click(screen.getByText('Automatic checks'));
}
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });

describe('Automatic public source checks', () => {
  it('announces a completed automatic run even when it finishes between polls', async () => {
    vi.useFakeTimers();
    let state: Schedule = { ...initial, enabled: true, selection: [{ kind: 'source', id: 'K01' }] };
    vi.stubGlobal('fetch', vi.fn(async () => response(state)));
    const completed = vi.fn();
    await act(async () => { render(<AutomaticChecks onComplete={completed} />); });
    state = { ...state, last_run: { id: 'short-automatic-run', trigger: 'automatic', started_at: '2026-10-05T06:00:00Z',
      finished_at: '2026-10-05T06:00:01Z', state: 'checked', checked: 1, failed: 0, error_code: null } };
    await act(async () => { await vi.advanceTimersByTimeAsync(15_000); });
    expect(completed).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(15_000); });
    expect(completed).toHaveBeenCalledTimes(1);
  });
  it('stays off and daily until an explicit selection and save', async () => {
    const fetch = mockSchedule(); render(<AutomaticChecks onComplete={() => {}} />); await openSettings();
    expect((screen.getByLabelText('Check my selected sources automatically') as HTMLInputElement).checked).toBe(false);
    expect((screen.getByLabelText('Check interval') as HTMLSelectElement).value).toBe('24');
    fireEvent.click(screen.getByLabelText('Check my selected sources automatically'));
    expect((screen.getByRole('button', { name: 'Save automatic checks' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByLabelText(/KDIGO CKD/));
    expect(fetch.mock.calls.every(([, options]) => options?.method !== 'PUT')).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Save automatic checks' }));
    await screen.findByText('Automatic checks saved. Discoveries will wait for your review.');
    const saved = fetch.mock.calls.find(([, options]) => options?.method === 'PUT')!;
    expect(JSON.parse(saved[1]!.body as string)).toEqual({ enabled: true, cadence_hours: 24, selection: [{ kind: 'source', id: 'K01' }] });
  });
  it('shows persisted failure and retry information without inventing a successful check', async () => {
    mockSchedule({ ...initial, enabled: true, selection: [{ kind: 'source', id: 'K01' }], next_due_at: '2026-10-05T06:05:00Z',
      last_run: { id: 'synthetic-offline', trigger: 'automatic', started_at: '2026-10-05T06:00:00Z', finished_at: '2026-10-05T06:00:01Z', state: 'failed', checked: 1, failed: 1, error_code: 'source_fetch_failed' },
      jobs: [{ kind: 'source', target_id: 'K01', title: 'KDIGO CKD', available: true, state: 'retry-wait', next_due_at: '2026-10-05T06:05:00Z',
        last_attempt_at: '2026-10-05T06:00:00Z', last_success_at: null, retry_count: 1, failure_count: 1, error_code: 'source_fetch_failed' }] });
    render(<AutomaticChecks onComplete={() => {}} />); await openSettings();
    expect(screen.getByText(/Previous successful evidence is retained/)).toBeTruthy();
    expect(screen.getByText(/Last successful check: Not yet/)).toBeTruthy();
    expect(screen.getByText(/Retry 1 of 2/)).toBeTruthy();
    expect(screen.getByText('On · failed')).toBeTruthy();
  });
  it('keeps a manual selection check available while automatic checks are off and allows stopping', async () => {
    const fetch = mockSchedule({ ...initial, selection: [{ kind: 'source', id: 'K01' }] });
    const completed = vi.fn(); render(<AutomaticChecks onComplete={completed} />); await openSettings();
    fireEvent.click(screen.getByRole('button', { name: 'Check selected now' }));
    await screen.findByText('Checking selected sources…');
    expect((screen.getByRole('button', { name: 'Check selected now' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Stop checks' }));
    await screen.findByText('Checks stopped. Completed observations are retained.');
    expect(fetch.mock.calls.some(([path, options]) => path.endsWith('/cancel') && options?.method === 'POST')).toBe(true);
    expect(completed).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls.some(([, options]) => options?.method === 'PUT')).toBe(false);
  });
  it('saves disabling and cadence without automatic review or provider fields', async () => {
    const fetch = mockSchedule({ ...initial, enabled: true, selection: [{ kind: 'source', id: 'K01' }] });
    render(<AutomaticChecks onComplete={() => {}} />); await openSettings();
    fireEvent.click(screen.getByLabelText('Check my selected sources automatically'));
    fireEvent.change(screen.getByLabelText('Check interval'), { target: { value: '168' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save automatic checks' }));
    await screen.findByText('Automatic checks are off. Your source selection is saved.');
    await waitFor(() => expect(fetch.mock.calls.some(([, options]) => options?.method === 'PUT')).toBe(true));
    expect(JSON.parse(fetch.mock.calls.find(([, options]) => options?.method === 'PUT')![1]!.body as string)).toEqual({
      enabled: false, cadence_hours: 168, selection: [{ kind: 'source', id: 'K01' }] });
  });
  it('retries a failed opt-in save with its selected sources and cadence, retaining the unsaved settings', async () => {
    let attempts = 0;
    const fetch = vi.fn(async (_path: string, options: RequestInit = {}) => options.method === 'PUT'
      ? ++attempts === 1
        ? response({ error: { code: 'synthetic_offline', message: 'Synthetic settings unavailable.', retryable: true } }, 503)
        : response({ ...initial, ...JSON.parse(options.body as string) })
      : response(initial));
    vi.stubGlobal('fetch', fetch);
    render(<AutomaticChecks onComplete={() => {}} />); await openSettings();
    fireEvent.click(screen.getByLabelText('Check my selected sources automatically'));
    fireEvent.click(screen.getByLabelText(/KDIGO CKD/));
    fireEvent.change(screen.getByLabelText('Check interval'), { target: { value: '168' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save automatic checks' }));
    await screen.findByText('Synthetic settings unavailable.');
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await screen.findByText('Automatic checks saved. Discoveries will wait for your review.');
    const saved = fetch.mock.calls.filter(([, options]) => options?.method === 'PUT');
    expect(saved).toHaveLength(2);
    expect(saved.map(([, options]) => JSON.parse(options!.body as string))).toEqual([
      { enabled: true, cadence_hours: 168, selection: [{ kind: 'source', id: 'K01' }] },
      { enabled: true, cadence_hours: 168, selection: [{ kind: 'source', id: 'K01' }] },
    ]);
  });
  it('keeps a failed disabling action retryable across successful and failed status polls', async () => {
    vi.useFakeTimers();
    const persisted = { ...initial, enabled: true, selection: [{ kind: 'source', id: 'K01' }] };
    let attempts = 0;
    let pollFails = false;
    const fetch = vi.fn(async (_path: string, options: RequestInit = {}) => options.method === 'PUT'
      ? ++attempts === 1
        ? response({ error: { code: 'synthetic_offline', message: 'Synthetic disable response unavailable.', retryable: true } }, 503)
        : response({ ...persisted, ...JSON.parse(options.body as string) })
      : pollFails ? response({ error: { code: 'synthetic_offline', message: 'Synthetic poll unavailable.', retryable: true } }, 503)
        : response(persisted));
    vi.stubGlobal('fetch', fetch);
    await act(async () => { render(<AutomaticChecks onComplete={() => {}} />); });
    fireEvent.click(screen.getByText('Automatic checks'));
    fireEvent.click(screen.getByLabelText('Check my selected sources automatically'));
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Save automatic checks' })); });
    expect(screen.getByText('Synthetic disable response unavailable.')).toBeTruthy();
    await act(async () => { await vi.advanceTimersByTimeAsync(15_000); });
    expect(screen.getByText('Synthetic disable response unavailable.')).toBeTruthy();
    pollFails = true;
    await act(async () => { await vi.advanceTimersByTimeAsync(15_000); });
    expect(screen.getByText('Synthetic disable response unavailable.')).toBeTruthy();
    expect((screen.getByLabelText('Check my selected sources automatically') as HTMLInputElement).checked).toBe(false);
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Try again' })); });
    expect(screen.getByText('Automatic checks are off. Your source selection is saved.')).toBeTruthy();
    expect(attempts).toBe(2);
  });
});
