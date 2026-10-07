// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import SourceChecks from './SourceChecks';
import type { Source } from './types';

const source: Source = { source_id: 'K01', title: 'Synthetic CKD catalogue',
  url: 'https://kdigo.org/guidelines/ckd-evaluation-and-management/', state: 'failed', freshness: 'stale',
  last_checked_at: '2026-10-04T20:00:00Z', last_success_at: '2026-10-04T19:00:00Z',
  error_code: 'source_fetch_failed', snapshot_status: 'Synthetic dated metadata' };

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('retries the failed public check at the same registered route instead of dismissing its failure', async () => {
  let attempts = 0;
  const fetch = vi.fn<typeof globalThis.fetch>(async () => new Response(JSON.stringify(++attempts === 1
    ? { error: { code: 'synthetic_offline', message: 'Synthetic local check unavailable.', retryable: true } }
    : { state: 'unchanged' }), { status: attempts === 1 ? 503 : 200,
      headers: { 'Content-Type': 'application/json' } }));
  vi.stubGlobal('fetch', fetch);
  const done = vi.fn();
  render(<SourceChecks done={done} publications={[]} sources={[source]} />);
  fireEvent.click(screen.getByRole('button', { name: 'Check now' }));
  await screen.findByText('Synthetic local check unavailable.');
  expect(done).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
  await waitFor(() => expect(done).toHaveBeenCalledWith('No publication-link change was found.'));
  expect(fetch.mock.calls).toHaveLength(2);
  expect(fetch.mock.calls.map(call => call[0])).toEqual([
    '/api/v1/updates/sources/K01/check?force=true', '/api/v1/updates/sources/K01/check?force=true',
  ]);
});

it('retries tracking with the visible edited permission after an unconfirmed submission', async () => {
  const url = 'https://kdigo.org/wp-content/uploads/synthetic-publication.pdf';
  let attempts = 0;
  const fetch = vi.fn(async (path: string, options: RequestInit = {}) => {
    const body = path.endsWith('/K01/publications') ? { candidates: [{ url, title: 'Synthetic public publication', provenance: 'Synthetic registered link' }] }
      : path.endsWith('/updates/publications') ? ++attempts === 1
        ? { error: { code: 'synthetic_offline', message: 'Synthetic tracking unavailable.', retryable: true } }
        : { id: 'synthetic-tracked', source_id: 'K01', url } : { state: 'baseline' };
    return new Response(JSON.stringify(body), { status: options.method === 'POST' && path.endsWith('/updates/publications') && attempts === 1 ? 503 : 200,
      headers: { 'Content-Type': 'application/json' } });
  });
  vi.stubGlobal('fetch', fetch);
  const done = vi.fn();
  render(<SourceChecks done={done} publications={[]} sources={[source]} />);
  fireEvent.click(screen.getByText('Track a publication'));
  fireEvent.change(screen.getByLabelText('Registered source'), { target: { value: 'K01' } });
  await screen.findByRole('option', { name: /Synthetic public publication/ });
  fireEvent.change(screen.getByLabelText('Public publication'), { target: { value: url } });
  fireEvent.change(screen.getByLabelText('Permission for a public digest check'), { target: { value: 'Synthetic original permission' } });
  fireEvent.click(screen.getByRole('button', { name: 'Track and check' }));
  await screen.findByText('Synthetic tracking unavailable.');
  fireEvent.change(screen.getByLabelText('Permission for a public digest check'), { target: { value: 'Synthetic corrected permission' } });
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
  await waitFor(() => expect(done).toHaveBeenCalledWith('The first complete snapshot is saved for future checks.'));
  const submissions = fetch.mock.calls.flatMap(([path, options]) => path.endsWith('/updates/publications') && options?.method === 'POST'
    ? [JSON.parse(options.body as string)] : []);
  expect(submissions).toHaveLength(2);
  expect(submissions[1].permission_reference).toBe('Synthetic corrected permission');
});
