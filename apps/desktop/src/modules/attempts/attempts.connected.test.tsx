// @vitest-environment jsdom
/** Opt-in actual HTTP/SQLite producer journey; no fetch response fixtures. */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AttemptPage } from './index';
import type { Attempt } from './types';
import { env } from 'node:process';

const origin = env.RENULUS_ATTEMPT_TEST_ORIGIN;
const connected = describe.skipIf(!origin);
const request = globalThis.fetch.bind(globalThis);
let versionId: string;
let testId: string;
async function remote<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await request(origin + '/api/v1' + path, init);
  if (!response.ok) throw new Error('Actual backend refused ' + path + ': ' + response.status + ' ' + await response.text());
  return response.json() as Promise<T>;
}
beforeEach(async () => {
  if (!origin) return;
  const url = new URL(origin);
  if (url.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(url.hostname)) throw new Error('Connected tests require an owned loopback backend.');
  const saved = await remote<{ test_id: string; version_id: string }>('/assessment/tests/reviewed', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ idempotency_key: crypto.randomUUID(), title: 'Synthetic connected UI', count: 3 }) });
  versionId = saved.version_id;
  testId = saved.test_id;
  vi.stubGlobal('fetch', (path: string, options: RequestInit) => request(origin + path, { ...options, signal: undefined }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

connected('actual attempt page → router → collection/SQLite', () => {
  it('commits Study explicitly and restores locked feedback after page reopen', async () => {
    const page = render(<AttemptPage versionId={versionId} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Start Study' }));
    const answer = await screen.findByRole('radio', { name: 'Token a' });
    expect(screen.queryByText('PRIVATE_REVIEWED_KEY_SENTINEL')).toBeNull();
    fireEvent.click(answer); fireEvent.click(screen.getByRole('button', { name: 'Submit answer' }));
    await screen.findByText('PRIVATE_REVIEWED_KEY_SENTINEL');
    const list = await remote<{ items: { id: string; version_id: string }[] }>('/assessment/test-attempts');
    const attempt = await remote<Attempt>('/assessment/test-attempts/' + list.items.find(item => item.version_id === versionId)!.id);
    expect(attempt.committed).toHaveLength(1); expect(attempt.committed[0].evidence_id).toBeTruthy();
    expect(screen.getByRole('radio', { name: 'Token a' }).matches(':disabled')).toBe(true);
    page.unmount(); render(<AttemptPage attemptId={attempt.id} />); await screen.findByText('PRIVATE_REVIEWED_KEY_SENTINEL');
    const reopened = await remote<Attempt>('/assessment/test-attempts/' + attempt.id);
    expect(reopened.committed).toEqual(attempt.committed);
    fireEvent.click(screen.getByRole('button', { name: 'Finish study' }));
    fireEvent.click(screen.getAllByRole('button', { name: 'Finish study' }).at(-1)!);
    await screen.findByRole('heading', { name: 'Study summary' });
  });
  it('keeps Test help/keys hidden and finalises the latest displayed draft atomically', async () => {
    render(<AttemptPage versionId={versionId} mode="test" timing={{ kind: 'untimed' }} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Start Test' }));
    fireEvent.click(await screen.findByRole('radio', { name: 'Token a' }));
    expect(screen.queryByRole('button', { name: 'Hint' })).toBeNull();
    expect(screen.queryByText('PRIVATE_REVIEWED_KEY_SENTINEL')).toBeNull();
    const denied = await request(origin + '/api/v1/assessment/progress'); expect(denied.status).toBe(409);
    fireEvent.click(screen.getByRole('button', { name: 'Review and submit test' }));
    fireEvent.click(screen.getByRole('button', { name: 'Submit test' }));
    await screen.findByRole('heading', { name: 'Test results' });
    await waitFor(() => expect(screen.getByText(/2 unanswered · 0 excluded/)).toBeTruthy());
    const list = await remote<{ items: { id: string; version_id: string }[] }>('/assessment/test-attempts');
    const attempt = await remote<Attempt>('/assessment/test-attempts/' + list.items.find(item => item.version_id === versionId)!.id);
    expect(attempt.answers[0].option_ids).toEqual(['a']); expect(attempt.result!.correct).toBe(1);
    expect(attempt.result!.denominator).toBe(3); expect(attempt.result!.items).toHaveLength(3);
    expect(attempt.policy.assistance_allowed).toBe(true);
  });
  it('expires a timed Test while its page is closed and retains results and reports after collection deletion', async () => {
    const page = render(<AttemptPage versionId={versionId} mode="test" timing={{ kind: 'timed', duration_seconds: 5 }} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Start Test' }));
    fireEvent.click(await screen.findByRole('radio', { name: 'Token a' }));
    const list = await remote<{ items: { id: string; version_id: string }[] }>('/assessment/test-attempts');
    const id = list.items.find(item => item.version_id === versionId)!.id;
    await waitFor(async () => {
      const saved = await remote<Attempt>('/assessment/test-attempts/' + id);
      expect(saved.answers[0].option_ids).toEqual(['a']);
    });
    page.unmount();
    await waitFor(async () => {
      const policy = await remote<{ assistance_allowed: boolean }>('/assessment/policy');
      expect(policy.assistance_allowed).toBe(true);
    }, { timeout: 9000, interval: 250 });
    const terminal = await remote<Attempt>('/assessment/test-attempts/' + id);
    expect(terminal.result!.reason).toBe('deadline');
    expect(terminal.result!.correct).toBe(1);
    const collection = await remote<{ revision: number }>('/assessment/tests/' + testId);
    await remote('/assessment/tests/' + testId, { method: 'DELETE', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ expected_revision: collection.revision, idempotency_key: crypto.randomUUID() }) });
    render(<AttemptPage attemptId={id} />);
    await screen.findByRole('heading', { name: 'Test results' });
    expect(screen.getByText(/The original collection is unavailable/)).toBeTruthy();
    const retained = await remote<Attempt>('/assessment/test-attempts/' + id);
    expect(retained.result).toEqual(terminal.result);
    expect(retained.provenance_unavailable).toBe(true);
    fireEvent.click(screen.getAllByRole('button', { name: 'Question seems wrong' })[0]);
    fireEvent.change(screen.getByRole('textbox', { name: 'What seems wrong?' }), { target: { value: 'Original synthetic report after removal' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save report' }));
    await screen.findByText('Your local report was saved. It does not change this answer or result.');
    expect((await remote<Attempt>('/assessment/test-attempts/' + id)).result).toEqual(terminal.result);
  });
  it('shows backend-finalised results when a displayed choice reaches the server after expiry', async () => {
    let release!: () => void;
    const delayed = new Promise<void>(resolve => { release = resolve; });
    vi.stubGlobal('fetch', async (path: string, options: RequestInit) => {
      if (path.endsWith('/draft') && options.method === 'PUT') await delayed;
      return request(origin + path, { ...options, signal: undefined });
    });
    render(<AttemptPage versionId={versionId} mode="test" timing={{ kind: 'timed', duration_seconds: 2 }} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Start Test' }));
    fireEvent.click(await screen.findByRole('radio', { name: 'Token a' }));
    try {
      await waitFor(async () => {
        expect((await remote<{ assistance_allowed: boolean }>('/assessment/policy')).assistance_allowed).toBe(true);
      }, { timeout: 7000, interval: 200 });
    } finally { release(); }
    await screen.findByRole('heading', { name: 'Test results' }, { timeout: 6000 });
    expect(screen.getByText(/Results use the backend-saved/)).toBeTruthy();
    const list = await remote<{ items: { id: string; version_id: string }[] }>('/assessment/test-attempts');
    const terminal = await remote<Attempt>('/assessment/test-attempts/' + list.items.find(item => item.version_id === versionId)!.id);
    expect(terminal.result!.unanswered).toBe(3);
    expect(terminal.answers[0].option_ids).toEqual([]);
    expect(terminal.result!.reason).toBe('deadline');
  });
});
