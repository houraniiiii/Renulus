// @vitest-environment jsdom
import { useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import ReviewFields from './ReviewFields';
import { reviewDraft, reviewPayload, reviewProblem } from './types';
import type { AcquiredVersion, Entry, ReviewDraft } from './types';

const entry: Entry = { id: 'synthetic', source_id: 'L02', title: 'Synthetic publication',
  url: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/', kind: 'research', publication_date: null,
  discovered_at: '2026-10-04T12:00:00Z', reviewed_at: null, review_state: 'pending', summary: '',
  topic_ids: [], read_at: null, source_metadata: {}, review: null };
const version = (digest = 'a', edition = 'PMC1234567.1'): AcquiredVersion => ({
  document_id: 'doc-' + digest, revision_id: 'rev-' + digest, title: 'Synthetic acquired article', edition,
  original_sha256: digest.repeat(64), status: 'ready', canonical_url: entry.url,
  doi: '10.5555/renulus-synthetic', pmid: null, pmcid: 'PMC1234567' });
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body),
  { status, headers: { 'Content-Type': 'application/json' } });
const readyDraft = (): ReviewDraft => ({ ...reviewDraft(entry), summary: 'Synthetic educational implication',
  locator: 'Synthetic section 1', finding: 'Synthetic source evidence', inspected: true, metadata: true });
function Form({ initial = readyDraft() }: { initial?: ReviewDraft }) {
  const [draft, change] = useState(initial);
  return <><ReviewFields sourceId={entry.source_id} draft={draft} change={change} topics={[]} />
    <output aria-label="Review payload">{JSON.stringify(reviewPayload(entry, draft, [], 'reviewed'))}</output>
    <output aria-label="Review problem">{reviewProblem(draft)}</output></>;
}
const payload = () => JSON.parse(screen.getByLabelText('Review payload').textContent!);
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Exact acquired version review', () => {
  it('looks up only exact publication metadata, shows the cap, and leaves the version unchosen', async () => {
    const fetch = vi.fn(async (_path: string) => json({ versions: [version(), version('b')], limit: 100, truncated: true }));
    vi.stubGlobal('fetch', fetch); render(<Form />);
    const select = await screen.findByLabelText('Acquired version') as HTMLSelectElement;
    expect(select.value).toBe('');
    expect(payload().target.edition).toBeUndefined();
    expect(payload().target.original_sha256).toBeUndefined();
    expect(screen.getByText(/Showing up to 100 acquired versions/)).toBeTruthy();
    const params = new URLSearchParams(fetch.mock.calls[0][0].split('?')[1]);
    expect(params.get('source_id')).toBe('L02'); expect(params.get('canonical_url')).toBe(entry.url);
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it('records no binding for a missing import and keeps manual paired entry optional', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json({ versions: [], limit: 100, truncated: false })));
    render(<Form />); await screen.findByText(/Currency verification waits for an exact acquired version/);
    const manual = screen.getByText('Enter version details manually').closest('details')!;
    expect(manual.open).toBe(false);
    fireEvent.click(screen.getByText('Enter version details manually'));
    fireEvent.change(screen.getByLabelText('Acquired edition'), { target: { value: 'PMC1234567.1' } });
    expect(screen.getByLabelText('Review problem').textContent).toContain('both');
    fireEvent.change(screen.getByLabelText('Original SHA256'), { target: { value: 'A'.repeat(64) } });
    expect(screen.getByLabelText('Review problem').textContent).toContain('lowercase');
    fireEvent.change(screen.getByLabelText('Original SHA256'), { target: { value: 'a'.repeat(64) } });
    expect(screen.getByLabelText('Review problem').textContent).toBe('');
    expect(payload().target).toMatchObject({ edition: 'PMC1234567.1', original_sha256: 'a'.repeat(64) });
    expect(reviewPayload(entry, { ...readyDraft(), edition: 'PMC1234567.1', originalSha256: 'a'.repeat(64) }, [], 'dismissed')).not.toHaveProperty('target');
  });
  it('preserves the saved edition/hash on reopening, and drops binding and positive review flags when identity changes', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json({ versions: [version('b'), version()], limit: 100, truncated: false })));
    const saved = { ...entry, review_state: 'reviewed' as const, summary: 'Synthetic reviewed implication',
      review: { id: 'synthetic-review', target: { register_id: 'L02', canonical_url: entry.url,
        edition: version().edition, original_sha256: version().original_sha256 },
        changes: { publication_status: 'final', latest_final_verified: true, content_reviewed: true },
        evidence: [], library_sync_state: 'applied', library_sync_error: null } };
    render(<Form initial={reviewDraft(saved)} />);
    const select = await screen.findByLabelText('Acquired version') as HTMLSelectElement;
    expect(select.value).toBe('rev-a');
    expect(payload().target.original_sha256).toBe('a'.repeat(64));
    fireEvent.change(select, { target: { value: 'rev-b' } });
    expect(payload().target.original_sha256).toBe('b'.repeat(64));
    expect(payload().changes.latest_final_verified).toBeUndefined(); expect(payload().changes.content_reviewed).toBeUndefined();
    fireEvent.change(screen.getByLabelText('Affected publication URL'), { target: { value: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC9876543/' } });
    expect(payload().target.edition).toBeUndefined(); expect(payload().target.original_sha256).toBeUndefined();
    expect(payload().changes.latest_final_verified).toBeUndefined(); expect(payload().changes.content_reviewed).toBeUndefined();
  });
  it('does not look up a source family or pinned-only identity and normalizes a complete article identifier', async () => {
    const fetch = vi.fn(async (_path: string) => json({ versions: [], limit: 100, truncated: false }));
    vi.stubGlobal('fetch', fetch); render(<Form initial={{ ...readyDraft(), targetUrl: '', pinnedSourceId: 'synthetic-pack-source' }} />);
    expect(screen.getByText(/Enter an exact publication URL or article identifier/)).toBeTruthy();
    expect(fetch).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('Original DOI'), { target: { value: 'doi: 10.5555/RENULUS-SYNTHETIC' } });
    await screen.findByText(/No acquired version is available/);
    const params = new URLSearchParams(fetch.mock.calls[0][0].split('?')[1]);
    expect(params.get('doi')).toBe('10.5555/renulus-synthetic'); expect(params.has('pinned_source_id')).toBe(false);
  });
  it('reports a lookup failure and retries only on request without promoting the first returned file', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(json({ error: { message: 'Synthetic identity conflict', code: 'source_status_invalid' } }, 422))
      .mockResolvedValueOnce(json({ versions: [version()], limit: 100, truncated: false }));
    vi.stubGlobal('fetch', fetch); render(<Form />);
    await screen.findByText(/Acquired versions could not be loaded/); expect(fetch).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: 'Retry version lookup' }));
    const select = await screen.findByLabelText('Acquired version') as HTMLSelectElement;
    expect(select.value).toBe(''); expect(fetch).toHaveBeenCalledTimes(2);
    expect(payload().target.original_sha256).toBeUndefined();
  });
  it('aborts the old identity lookup and ignores its late response', async () => {
    let finishFirst!: (response: Response) => void;
    const fetch = vi.fn().mockImplementationOnce(() => new Promise<Response>(resolve => { finishFirst = resolve; }))
      .mockResolvedValue(json({ versions: [version('b', 'PMC9876543.1')], limit: 100, truncated: false }));
    vi.stubGlobal('fetch', fetch); render(<Form />);
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    fireEvent.change(screen.getByLabelText('Affected publication URL'), { target: { value: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC9876543/' } });
    await screen.findByRole('option', { name: /PMC9876543.1/ });
    expect(fetch.mock.calls[0][1].signal.aborted).toBe(true);
    await act(async () => { finishFirst(json({ versions: [version()], limit: 100, truncated: false })); });
    expect(screen.queryByRole('option', { name: /PMC1234567.1/ })).toBeNull();
    expect((screen.getByLabelText('Acquired version') as HTMLSelectElement).value).toBe('');
    expect(payload().target.edition).toBeUndefined();
  });
});
