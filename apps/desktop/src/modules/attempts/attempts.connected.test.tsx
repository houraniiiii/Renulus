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
async function remote<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await request(origin + '/api/v1' + path, init);
  if (!response.ok) throw new Error('Actual backend refused ' + path + ': ' + response.status + ' ' + await response.text());
  return response.json() as Promise<T>;
}
beforeEach(async () => {
  if (!origin) return;
  const url = new URL(origin);
  if (url.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(url.hostname)) throw new Error('Connected tests require an owned loopback backend.');
  const saved = await remote<{ version_id: string }>('/assessment/tests/reviewed', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ idempotency_key: crypto.randomUUID(), title: 'Synthetic connected UI', count: 3 }) });
  versionId = saved.version_id;
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
});
