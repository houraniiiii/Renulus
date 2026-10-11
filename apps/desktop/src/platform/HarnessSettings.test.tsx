// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { HarnessSettings } from './HarnessSettings';

const path = '/api/v1/runtime/harness/configuration';
const effective = 'a'.repeat(64);
const requested = 'b'.repeat(64);
const failed = 'c'.repeat(64);
const request = vi.fn<typeof fetch>();
const role = (purpose: string, dispatch_limit: number | null = null) => ({ purpose, enabled: purpose !== 'title', model_id: null as string | null, output_tokens: 4096, dispatch_limit });
const configuration = () => ({ roles: [role('explain'), role('summary'), role('title')], attempts: { foreground_dispatches: 12, standalone_dispatches: 1, title_dispatches: 0, retries: 0 } });
const initial = () => ({ requested, effective, failed: null as string | null, failure_code: null as string | null, admission_open: true, configuration: configuration(), requested_configuration: configuration(), pinned_runs: [] as Array<{ run_id: string; purpose: string; version: string }>, catalogue: ['gpt-6.1-sol', 'gpt-6-astra'] });
let snapshot = initial();
function json(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } }); }
beforeEach(() => {
  snapshot = initial();
  request.mockReset().mockImplementation(async url => {
    if (url === path) return json(snapshot);
    throw new Error('Unexpected synthetic request: ' + url);
  });
  vi.stubGlobal('fetch', request);
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
async function ready() { render(<HarnessSettings />); await screen.findByText('Effective revision'); }

describe('Harness Settings public user seam', () => {
  it('reads opaque revisions, admission and pinned runs without selecting a subscription or dispatching', async () => {
    snapshot.failed = failed; snapshot.failure_code = 'candidate_registry_mismatch';
    snapshot.pinned_runs = [{ run_id: 'synthetic-transplant-case', purpose: 'case-discuss', version: effective }];
    await ready();
    const revisions = screen.getByRole('region', { name: 'Configuration revisions' });
    expect(within(revisions).getByTitle(effective).textContent).toBe('aaaaaaaaaaaa');
    expect(within(revisions).getByTitle(requested).textContent).toBe('bbbbbbbbbbbb');
    expect(within(revisions).getByTitle(failed).textContent).toBe('cccccccccccc');
    expect(screen.getByText('Open for new runs')).toBeTruthy();
    expect(screen.getByText('synthetic-transplant-case')).toBeTruthy();
    expect(within(screen.getByRole('region', { name: 'Pinned runs' })).getByText('Case discussion')).toBeTruthy();
    expect(screen.getByText(/candidate_registry_mismatch/)).toBeTruthy();
    expect(request.mock.calls).toHaveLength(1);
    expect(request.mock.calls[0][0]).toBe(path);
    expect(request.mock.calls[0][1]?.method).toBeUndefined();
  });

  it('edits requested role policies with catalogue-only overrides and stages without changing effective', async () => {
    snapshot.requested_configuration.roles[1].output_tokens = 8192;
    const next = 'd'.repeat(64);
    request.mockImplementation(async (url, options) => {
      if (url === path && options?.method === 'POST') {
        snapshot.requested = next;
        snapshot.requested_configuration.roles = JSON.parse(options.body as string).roles;
        return json({ version: next });
      }
      return json(snapshot);
    });
    await ready();
    fireEvent.click(screen.getByText('Summary'));
    expect((screen.getByLabelText('Summary output tokens') as HTMLInputElement).value).toBe('8192');
    expect(Array.from((screen.getByLabelText('Summary model') as HTMLSelectElement).options, option => option.value)).toEqual(['', 'gpt-6.1-sol', 'gpt-6-astra']);
    fireEvent.change(screen.getByLabelText('Summary model'), { target: { value: 'gpt-6-astra' } });
    fireEvent.change(screen.getByLabelText('Summary output tokens'), { target: { value: '2048' } });
    fireEvent.change(screen.getByLabelText('Summary dispatch limit'), { target: { value: '0' } });
    fireEvent.click(screen.getByLabelText('Enable Summary'));
    fireEvent.click(screen.getByText('Title'));
    fireEvent.click(screen.getByLabelText('Enable Title'));
    fireEvent.change(screen.getByLabelText('Title dispatch limit'), { target: { value: '1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Stage role settings' }));
    await within(screen.getByRole('region', { name: 'Configuration revisions' })).findByTitle(next);
    const post = request.mock.calls.find(([, options]) => options?.method === 'POST')!;
    expect(post[0]).toBe(path);
    const body = JSON.parse(post[1]!.body as string);
    expect(Object.keys(body)).toEqual(['roles']);
    expect(body.roles.find((item: { purpose: string }) => item.purpose === 'summary')).toEqual({ purpose: 'summary', enabled: false, model_id: 'gpt-6-astra', output_tokens: 2048, dispatch_limit: 0 });
    expect(body.roles.find((item: { purpose: string }) => item.purpose === 'explain')).toEqual({ purpose: 'explain', enabled: true, model_id: null, output_tokens: 4096, dispatch_limit: null });
    expect(body.roles.find((item: { purpose: string }) => item.purpose === 'title')).toEqual({ purpose: 'title', enabled: true, model_id: null, output_tokens: 4096, dispatch_limit: 1 });
    expect(screen.getByTitle(effective)).toBeTruthy();
    expect(request.mock.calls.filter(([, options]) => !options?.method)).toHaveLength(2);
    expect(request.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1);
  });

  it('refreshes after busy activation and shows pinned-run recovery without failing the candidate', async () => {
    request.mockImplementation(async (url, options) => {
      if (url === path + '/activate') {
        snapshot.pinned_runs = [{ run_id: 'synthetic-dialysis-explain', purpose: 'explain', version: effective }];
        return json({ error: { code: 'harness_configuration_busy', message: 'Active learning must settle before restart.', retryable: true } }, 409);
      }
      return json(snapshot);
    });
    await ready();
    fireEvent.click(screen.getByRole('button', { name: 'Activate requested revision' }));
    await screen.findByText('Active learning must settle before restart.');
    await screen.findByText('synthetic-dialysis-explain');
    expect(screen.getByText(/Finish or stop the active runs/)).toBeTruthy();
    const revisions = screen.getByRole('region', { name: 'Configuration revisions' });
    expect(within(revisions).getByTitle(effective)).toBeTruthy();
    expect(within(revisions).getByTitle(requested)).toBeTruthy();
    expect(within(revisions).getByText('Failed revision').parentElement!.textContent).toContain('None');
    expect(screen.queryByText(/Candidate activation failed/)).toBeNull();
    expect(screen.getByText('Open for new runs')).toBeTruthy();
    const post = request.mock.calls.find(([url]) => url === path + '/activate')!;
    expect(JSON.parse(post[1]!.body as string)).toEqual({ version: requested });
    expect(request.mock.calls.filter(([, options]) => !options?.method)).toHaveLength(2);
  });

  it('keeps edits and last known revisions when the activation read fails, and never replays activation', async () => {
    let unreadable = false;
    request.mockImplementation(async (url, options) => {
      if (url === path + '/activate') {
        unreadable = true;
        return json({ effective: requested, admission_open: true });
      }
      return unreadable ? json({ error: { code: 'unavailable', message: 'Local status unavailable.', retryable: true } }, 503) : json(snapshot);
    });
    await ready();
    fireEvent.click(screen.getByText('Summary'));
    fireEvent.change(screen.getByLabelText('Summary output tokens'), { target: { value: '2048' } });
    fireEvent.click(screen.getByRole('button', { name: 'Activate requested revision' }));
    await screen.findByText('Local status unavailable.');
    expect(screen.getByText('Status needs refreshing')).toBeTruthy();
    expect(screen.queryByText('Open for new runs')).toBeNull();
    expect((screen.getByLabelText('Summary output tokens') as HTMLInputElement).value).toBe('2048');
    expect((screen.getByRole('button', { name: 'Stage role settings' }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole('button', { name: 'Activate requested revision' }) as HTMLButtonElement).disabled).toBe(true);
    expect(within(screen.getByRole('region', { name: 'Configuration revisions' })).getByTitle(effective)).toBeTruthy();
    unreadable = false; snapshot.effective = requested; snapshot.admission_open = false;
    fireEvent.click(screen.getByRole('button', { name: 'Refresh configuration status' }));
    await screen.findByText('New runs paused');
    snapshot.admission_open = true;
    fireEvent.click(screen.getByRole('button', { name: 'Refresh configuration status' }));
    await screen.findByText('Open for new runs');
    expect(request.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1);
  });

  it('blocks invalid output and dispatch bounds locally while preserving nullable purpose defaults', async () => {
    await ready();
    fireEvent.click(screen.getByText('Summary'));
    fireEvent.change(screen.getByLabelText('Summary output tokens'), { target: { value: '' } });
    expect(screen.getByText('Use a whole number from 1 to 32768.')).toBeTruthy();
    expect((screen.getByRole('button', { name: 'Stage role settings' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Summary output tokens'), { target: { value: '2048' } });
    fireEvent.change(screen.getByLabelText('Summary dispatch limit'), { target: { value: '1.5' } });
    expect(screen.getByText('Use a whole number from 0 to 128, or leave blank.')).toBeTruthy();
    expect((screen.getByRole('button', { name: 'Stage role settings' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Summary dispatch limit'), { target: { value: '' } });
    expect((screen.getByRole('button', { name: 'Stage role settings' }) as HTMLButtonElement).disabled).toBe(false);
    expect((screen.getByLabelText('Summary dispatch limit') as HTMLInputElement).placeholder).toBe('Default · 1');
    expect(request.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(0);
  });

  it('preserves a withdrawn override and edits on refresh until the owner chooses an allowed model', async () => {
    snapshot.requested_configuration.roles[1].model_id = 'gpt-6-astra';
    await ready();
    fireEvent.click(screen.getByText('Summary'));
    fireEvent.change(screen.getByLabelText('Summary output tokens'), { target: { value: '2048' } });
    snapshot.catalogue = ['gpt-6.1-sol'];
    fireEvent.click(screen.getByRole('button', { name: 'Refresh configuration status' }));
    await screen.findByText('Choose inheritance or a model from the current allowed catalogue.');
    expect((screen.getByLabelText('Summary model') as HTMLSelectElement).value).toBe('gpt-6-astra');
    expect((screen.getByLabelText('Summary output tokens') as HTMLInputElement).value).toBe('2048');
    expect((screen.getByRole('button', { name: 'Stage role settings' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Summary model'), { target: { value: '' } });
    expect((screen.getByRole('button', { name: 'Stage role settings' }) as HTMLButtonElement).disabled).toBe(false);
    expect(request.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(0);
  });

  it('uses the failure pointer from GET and preserves healthy effective settings after validation fails', async () => {
    request.mockImplementation(async url => {
      if (url === path + '/activate') {
        snapshot.failed = requested; snapshot.failure_code = 'candidate_registry_mismatch';
        return json({ error: { code: 'candidate_registry_mismatch', message: 'The candidate registry did not validate.', retryable: false } }, 422);
      }
      return json(snapshot);
    });
    await ready();
    fireEvent.click(screen.getByRole('button', { name: 'Activate requested revision' }));
    await screen.findByText('Candidate activation failed (candidate_registry_mismatch). The effective revision is shown above.');
    expect(screen.getByText('Open for new runs')).toBeTruthy();
    expect(within(screen.getByRole('region', { name: 'Configuration revisions' })).getByTitle(effective)).toBeTruthy();
    expect(screen.getByText('Failed revision').parentElement!.textContent).toContain('bbbbbbbbbbbb');
    expect(request.mock.calls.filter(([, options]) => !options?.method)).toHaveLength(2);
  });

  it('offers existing connection recovery when no effective configuration exists', async () => {
    request.mockImplementation(async () => json({ ...snapshot, effective: null, requested: null, configuration: null, requested_configuration: null, admission_open: false, catalogue: [] }));
    await ready();
    expect(screen.getByText(/Select a learning subscription in Connections/)).toBeTruthy();
    expect(screen.getByText('New runs paused')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Stage role settings' })).toBeNull();
    expect((screen.getByRole('button', { name: 'Activate requested revision' }) as HTMLButtonElement).disabled).toBe(true);
    expect(request.mock.calls).toHaveLength(1);
  });

  it('recovers an initial local read error with a read-only retry', async () => {
    request.mockResolvedValueOnce(json({ error: { code: 'unavailable', message: 'Synthetic runtime offline.', retryable: true } }, 503));
    render(<HarnessSettings />);
    await screen.findByText('Synthetic runtime offline.');
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await screen.findByText('Effective revision');
    expect(request.mock.calls).toHaveLength(2);
    expect(request.mock.calls.every(([, options]) => !options?.method)).toBe(true);
  });

  it('aborts an activation on unmount and does not refresh or replay after its late response', async () => {
    let release!: (value: Response) => void;
    request.mockImplementation(async url => url === path + '/activate' ? await new Promise<Response>(resolve => { release = resolve; }) : json(snapshot));
    const view = render(<HarnessSettings />);
    await screen.findByText('Effective revision');
    fireEvent.click(screen.getByRole('button', { name: 'Activate requested revision' }));
    await waitFor(() => expect(release).toBeTypeOf('function'));
    const post = request.mock.calls.find(([url]) => url === path + '/activate')!;
    view.unmount();
    expect(post[1]!.signal!.aborted).toBe(true);
    await act(async () => { release(json({ effective: requested, admission_open: true })); });
    expect(request.mock.calls).toHaveLength(2);
    expect(request.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1);
  });
});
