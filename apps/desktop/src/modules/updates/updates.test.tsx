// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import Updates from './index';
import { literatureMessage } from './types';
import type { Entry } from './types';

const entry = (id = 'synthetic-update'): Entry => ({ id, source_id: 'L03', title: 'Synthetic publication ' + id,
  url: 'https://europepmc.org/article/MED/999999', kind: 'research', publication_date: '2020-03-01',
  discovered_at: '2026-10-04T12:00:00Z', reviewed_at: null, review_state: 'pending', summary: '', topic_ids: [],
  read_at: null, source_metadata: {}, review: null });
const json = (body: unknown) => new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json' } });
function mockApi(rows = [entry()], extra?: (path: string, options: RequestInit) => Response | undefined) {
  const fetch = vi.fn(async (path: string, options: RequestInit = {}) => {
    const overridden = extra?.(path, options); if (overridden) return overridden;
    if (path.startsWith('/api/v1/updates/entries?')) {
      const params = new URLSearchParams(path.split('?')[1]); const offset = Number(params.get('offset'));
      const state = params.get('state'); const selected = state === 'pending' ? rows : [];
      return json({ entries: selected.slice(offset, offset + 50), offset, limit: 50, total: selected.length,
        counts: { pending: rows.length, reviewed: 17, dismissed: 3 }, next_offset: offset + 50 < selected.length ? offset + 50 : null });
    }
    if (path.endsWith('/updates/sources')) return json({ sources: [] });
    if (path.startsWith('/api/v1/library/source-versions?')) return json({ versions: [], limit: 100, truncated: false });
    if (path.endsWith('/updates/publications')) return json({ publications: [] });
    if (path.endsWith('/updates/schedule')) return json({ enabled: false, cadence_hours: 24, selection: [], options: [], jobs: [], running: false,
      next_due_at: null, last_run: null, max_batch: 5, max_selection: 20, max_retries: 2 });
    if (path.endsWith('/content/topics')) return json([{ id: 'ckd', title: 'Chronic kidney disease' }, { id: 'transplantation', title: 'Transplantation' }]);
    if (path.includes('/affected?')) return json({ affected: [], total: 0, next_offset: null });
    if (path.endsWith('/review')) return json({ ...rows[0], review_state: 'reviewed' });
    if (path.endsWith('/read')) return json({ read: true });
    throw new Error('Unexpected synthetic request: ' + path);
  });
  vi.stubGlobal('fetch', fetch); return fetch;
}
async function openFirst() { fireEvent.click(await screen.findByRole('button', { name: /Synthetic publication/ })); }
function inspectEvidence() {
  fireEvent.change(screen.getByLabelText('What changes for your learning?'), { target: { value: 'Synthetic educational implication only' } });
  fireEvent.change(screen.getByLabelText('Page or section'), { target: { value: 'Synthetic notice, section 2' } });
  fireEvent.change(screen.getByLabelText('What did the source establish?'), { target: { value: 'Synthetic publisher relationship evidence' } });
  fireEvent.click(screen.getByLabelText('I inspected this evidence and its stated publication status.'));
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Updates review and bounded queue', () => {
  it('requires inspected evidence and submits the actual evidence with the educational summary', async () => {
    const fetch = mockApi(); render(<Updates />); await openFirst();
    const save = screen.getByRole('button', { name: 'Save reviewed update' }) as HTMLButtonElement;
    fireEvent.change(screen.getByLabelText('What changes for your learning?'), { target: { value: 'Summary alone' } });
    expect(save.disabled).toBe(true);
    inspectEvidence(); expect(save.disabled).toBe(false); fireEvent.click(save);
    await screen.findByText('Your evidence and reviewed update are saved.');
    const request = fetch.mock.calls.find(([path]) => path.endsWith('/review'))!;
    const body = JSON.parse(request[1]!.body as string);
    expect(body.state).toBe('reviewed'); expect(body.evidence[0]).toMatchObject({ inspected: true,
      url: entry().url, locator: 'Synthetic notice, section 2', finding: 'Synthetic publisher relationship evidence' });
    expect(body.changes).toBeUndefined();
  });
  it('uses server counts and reaches records beyond 100 without client-side truncation', async () => {
    const fetch = mockApi(Array.from({ length: 120 }, (_, index) => entry('record-' + index))); render(<Updates />);
    await screen.findByText('1–50 of 120');
    expect(screen.getByRole('button', { name: 'Reviewed 17' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Next' })); await screen.findByText('51–100 of 120');
    fireEvent.click(screen.getByRole('button', { name: 'Next' })); await screen.findByText('101–120 of 120');
    fireEvent.click(screen.getByRole('button', { name: /Synthetic publication record-110/ }));
    inspectEvidence(); fireEvent.click(screen.getByRole('button', { name: 'Save reviewed update' }));
    await waitFor(() => expect(fetch.mock.calls.some(([path]) => path.endsWith('/record-110/review'))).toBe(true));
    fireEvent.click(await screen.findByRole('button', { name: 'Reviewed 17' }));
    await waitFor(() => expect(fetch.mock.calls.some(([path]) => path.includes('state=reviewed&limit=50&offset=0'))).toBe(true));
  });
  it('retains the draft and previous identity when an old article refresh fails', async () => {
    mockApi([entry()], path => path.endsWith('/refresh') ? json({ state: 'failed', entry: entry(), error: { message: 'Synthetic article check failed' } }) : undefined);
    render(<Updates />); await openFirst(); inspectEvidence();
    fireEvent.click(screen.getByRole('button', { name: 'Refresh metadata' })); await screen.findByText('Synthetic article check failed');
    expect((screen.getByLabelText('What changes for your learning?') as HTMLTextAreaElement).value).toBe('Synthetic educational implication only');
    expect((screen.getByLabelText('I inspected this evidence and its stated publication status.') as HTMLInputElement).checked).toBe(true);
  });
  it('requires the original article identity and selected replacement scope before publishing metadata', async () => {
    const fetch = mockApi(); render(<Updates />); await openFirst(); inspectEvidence();
    fireEvent.click(screen.getByText('Publication status and affected source'));
    fireEvent.click(screen.getByLabelText('Record the source facts established by this evidence'));
    fireEvent.change(screen.getByLabelText('Retraction'), { target: { value: 'yes' } });
    const save = screen.getByRole('button', { name: 'Save reviewed update' }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Affected publication URL'), { target: { value: 'https://europepmc.org/article/MED/111111' } });
    fireEvent.change(screen.getByLabelText('Original PMID'), { target: { value: '111111' } });
    fireEvent.change(screen.getByLabelText('Replacement scope'), { target: { value: 'topics' } }); expect(save.disabled).toBe(true);
    fireEvent.click(screen.getAllByLabelText('Transplantation')[0]); expect(save.disabled).toBe(false); fireEvent.click(save);
    await screen.findByText('Your evidence and reviewed update are saved.');
    const body = JSON.parse(fetch.mock.calls.find(([path]) => path.endsWith('/review'))![1]!.body as string);
    expect(body.target).toMatchObject({ register_id: 'L03', pmid: '111111', canonical_url: 'https://europepmc.org/article/MED/111111', topic_ids: ['transplantation'] });
    expect(body.evidence[0].url).toBe(entry().url); expect(body.changes).toMatchObject({ retracted: true, replaced_topics: ['transplantation'] });
  });
  it('dismisses without fabricating review evidence and does not claim an empty library sync applied', async () => {
    const row = { ...entry(), library_changes: [{ id: 'observed:synthetic', state: 'unavailable', error_code: 'library_status_seam_unavailable' }] };
    const fetch = mockApi([row], path => path.endsWith('/sync') ? json({ changes: [] }) : path.endsWith('/synthetic-update') ? json(row) : undefined);
    render(<Updates />); await openFirst(); fireEvent.click(screen.getByRole('button', { name: 'Retry library update' }));
    await screen.findByText('This review has no library metadata change to apply.');
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' })); await screen.findByText('Discovery dismissed. Its history remains in Dismissed.');
    expect(JSON.parse(fetch.mock.calls.find(([path]) => path.endsWith('/review'))![1]!.body as string)).toEqual({ summary: '', topic_ids: [], reviewer: 'learner', state: 'dismissed' });
  });
  it('deliberately binds an acquired version without requiring entry of its original hash', async () => {
    const row = { ...entry(), source_id: 'L02', url: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/' };
    const versions = ['a', 'b'].map((digest, index) => ({ document_id: 'doc-' + index, revision_id: 'rev-' + index,
      title: 'Synthetic acquired publication', edition: 'PMC1234567.1', original_sha256: digest.repeat(64),
      status: 'ready', canonical_url: row.url, doi: null, pmid: null, pmcid: 'PMC1234567' }));
    const fetch = mockApi([row], path => path.startsWith('/api/v1/library/source-versions?')
      ? json({ versions, limit: 100, truncated: false }) : undefined);
    render(<Updates />); await openFirst(); inspectEvidence();
    fireEvent.click(screen.getByText('Publication status and affected source'));
    fireEvent.click(screen.getByLabelText('Record the source facts established by this evidence'));
    const select = await screen.findByLabelText('Acquired version') as HTMLSelectElement;
    await screen.findByRole('option', { name: /file bbbbbbbb/ });
    expect(select.value).toBe('');
    fireEvent.change(select, { target: { value: 'rev-1' } });
    fireEvent.change(screen.getByLabelText('Publication status'), { target: { value: 'final' } });
    fireEvent.click(screen.getByLabelText('Verified latest final for this scope'));
    fireEvent.click(screen.getByLabelText('Content reviewed for the recorded educational scope'));
    fireEvent.click(screen.getByRole('button', { name: 'Save reviewed update' }));
    await screen.findByText('Your evidence and reviewed update are saved.');
    const body = JSON.parse(fetch.mock.calls.find(([path]) => path.endsWith('/review'))![1]!.body as string);
    expect(body.target).toMatchObject({ register_id: 'L02', canonical_url: row.url,
      edition: 'PMC1234567.1', original_sha256: 'b'.repeat(64) });
    expect(body.changes).toMatchObject({ publication_status: 'final', latest_final_verified: true, content_reviewed: true });
    const lookup = fetch.mock.calls.find(([path]) => path.startsWith('/api/v1/library/source-versions?'))![0];
    expect(new URLSearchParams(lookup.split('?')[1]).get('source_id')).toBe('L02');
    expect(new URLSearchParams(lookup.split('?')[1]).get('canonical_url')).toBe(row.url);
    expect(fetch.mock.calls.some(([path]) => path.startsWith('/api/v1/library/documents'))).toBe(false);
  });
  it('reports failures and truncated discovery without claiming an exhaustive no-change result', () => {
    expect(literatureMessage({ state: 'failed', discovered: 0, checks: [], max_records_per_topic: 25 })).toContain('failed');
    expect(literatureMessage({ state: 'checked', discovered: 0, checks: [{ state: 'checked', records_checked: 25, hit_count: 3400, truncated: true }], max_records_per_topic: 25 })).toContain('more matches exist');
  });
});
