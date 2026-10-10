// @vitest-environment jsdom
/** Opt-in real loopback HTTP/SQLite journey; responses and saved artifacts are never fixtures. */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { env } from 'node:process';
import Home from './index';
import AttemptsPage from '../attempts';
import type { Attempt } from '../attempts/types';
import { NavigationProvider, useNavigation } from '../../shell/navigation';

const origin = env.RENULUS_HOME_TEST_ORIGIN;
const connected = describe.skipIf(!origin);
const request = globalThis.fetch.bind(globalThis);
const raw = 'HOME_VOLATILE_ORIGINAL_SOURCE_8FA0';
type ObservedRequest = { path: string; body: string; key: string | null };
let observed: ObservedRequest[];
async function remote<T>(path: string): Promise<T> {
  const response = await request(origin + '/api/v1' + path);
  if (!response.ok) throw new Error('Actual backend refused ' + path + ': ' + response.status + ' ' + await response.text());
  return response.json() as Promise<T>;
}
function connect(dropPreparation = false, dropStart = false) {
  vi.stubGlobal('fetch', async (path: string, options: RequestInit = {}) => {
    // Node fetch cannot accept jsdom's AbortSignal. This suite checks acknowledgements,
    // while cancellation/unmount have their separate Home behavior checks.
    const response = await request(origin + path, { ...options, signal: undefined });
    if (options.method === 'POST') observed.push({ path, body: String(options.body ?? ''),
      key: new Headers(options.headers).get('Idempotency-Key') });
    if (response.ok && options.method === 'POST' &&
        ((dropPreparation && path === '/api/v1/conversations/test-drafts') ||
         (dropStart && path === '/api/v1/assessment/test-attempts'))) {
      await response.arrayBuffer(); // The real server completed; only the acknowledgement is lost.
      if (path === '/api/v1/conversations/test-drafts') dropPreparation = false;
      else dropStart = false;
      throw new TypeError('Synthetic lost acknowledgement after actual server effect');
    }
    return response;
  });
}
beforeEach(() => {
  if (!origin) return;
  const url = new URL(origin);
  if (url.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(url.hostname) || url.pathname !== '/' || url.search || url.hash || url.username || url.password) {
    throw new Error('Connected Home requires an owned loopback backend origin.');
  }
  observed = []; window.history.replaceState(null, '', '#/newchat'); connect();
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function ConnectedHomeRoute() {
  const navigation = useNavigation();
  return navigation.route === 'attempts' ? <AttemptsPage /> : <Home />;
}
const composer = () => screen.getByRole('textbox', { name: 'How can I help you today' }) as HTMLTextAreaElement;
async function practiceDraft(text?: string, suggestion = true) {
  await screen.findByRole('heading', { name: 'Welcome back' });
  fireEvent.click(screen.getByRole('button', { name: 'Quick practice' }));
  if (suggestion) fireEvent.click(await screen.findByRole('button', { name: 'Synthetic practice learning prompt 0' }, { timeout: 15000 }));
  if (text) fireEvent.change(composer(), { target: { value: text } });
  expect(observed.filter(value => value.path === '/api/v1/conversations/test-drafts')).toHaveLength(0);
}
async function returnedAttempt(previous: Set<string>): Promise<Attempt> {
  const list = await remote<{ items: { id: string }[] }>('/assessment/test-attempts');
  const fresh = list.items.filter(value => !previous.has(value.id));
  expect(fresh).toHaveLength(1);
  return remote<Attempt>('/assessment/test-attempts/' + fresh[0].id);
}

connected('default Home → trusted fictional producer → saved-five → whole Study', () => {
  it('prefills without creating practice, starts exactly once on Send, commits and reopens the returned attempt', async () => {
    const before = new Set((await remote<{ items: { id: string }[] }>('/assessment/test-attempts')).items.map(value => value.id));
    const view = render(<NavigationProvider><ConnectedHomeRoute /></NavigationProvider>);
    await practiceDraft(raw + '_normal');
    expect(composer().value).toBe(raw + '_normal');
    fireEvent.submit(composer().closest('form')!); fireEvent.submit(composer().closest('form')!);
    fireEvent.click(await screen.findByRole('checkbox', { name: 'First fictional interpretation' }, { timeout: 20000 }));
    expect(screen.queryByRole('button', { name: 'Start Study' })).toBeNull();
    const attempt = await returnedAttempt(before);
    expect(attempt.item_count).toBe(5); expect(attempt.mode).toBe('study');
    expect(attempt.timing.kind).toBe('untimed'); expect(attempt.timing.deadline_at).toBeNull();
    expect(attempt.origin).toBe('generated'); expect(attempt.review_quality).toBe('personal');
    expect(window.location.hash).toBe('#/attempts/' + attempt.id);
    expect(observed.filter(value => value.path === '/api/v1/conversations/test-drafts')).toHaveLength(1);
    expect(observed.filter(value => value.path === '/api/v1/assessment/test-attempts')).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: 'Submit answer' }));
    await screen.findByText('An independent educational rationale.');
    const committed = await remote<Attempt>('/assessment/test-attempts/' + attempt.id);
    expect(committed.committed).toHaveLength(1); expect(committed.committed[0].evidence_id).toBeTruthy();
    view.unmount(); render(<NavigationProvider><ConnectedHomeRoute /></NavigationProvider>);
    await screen.findByText('An independent educational rationale.');
    expect(screen.getByRole('checkbox', { name: 'First fictional interpretation' }).matches(':disabled')).toBe(true);
    expect((await returnedAttempt(before)).committed).toEqual(committed.committed);
    expect(observed.filter(value => value.path === '/api/v1/assessment/test-attempts')).toHaveLength(1);
  }, 45000);

  it('replays lost preparation and Study acknowledgements without a second saved version or attempt', async () => {
    const before = new Set((await remote<{ items: { id: string }[] }>('/assessment/test-attempts')).items.map(value => value.id));
    connect(true, true);
    render(<NavigationProvider><ConnectedHomeRoute /></NavigationProvider>);
    await practiceDraft(raw + '_replay', false);
    for (let index = 0; index < 2; index++) {
      fireEvent.click(screen.getByRole('button', { name: 'Send' }));
      await screen.findByText('The local runtime is unavailable. Open Connections to check it, then retry.', { exact: true }, { timeout: 20000 });
      await waitFor(() => expect(composer().disabled).toBe(false));
      expect(composer().value).toBe(raw + '_replay');
      expect(window.location.hash).toBe('#/newchat');
    }
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    await screen.findByRole('checkbox', { name: 'First fictional interpretation' }, { timeout: 20000 });
    const attempts = observed.filter(value => value.path === '/api/v1/assessment/test-attempts');
    expect(attempts).toHaveLength(2); expect(attempts[0]).toEqual(attempts[1]);
    const preparations = observed.filter(value => value.path === '/api/v1/conversations/test-drafts');
    expect(preparations).toHaveLength(2); expect(preparations[0]).toEqual(preparations[1]);
    const input = JSON.parse(preparations[0].body);
    expect(Object.keys(input).sort()).toEqual(['count', 'intent', 'request_id', 'text']);
    expect(input.count).toBe(5); expect(input.intent).toBe('quick_practice');
    expect(attempts[0].key).toMatch(/^chat-test-study-/);
    expect(attempts[0].key).not.toContain(input.request_id);
    const attempt = await returnedAttempt(before);
    expect(attempt.item_count).toBe(5); expect(attempt.mode).toBe('study'); expect(attempt.timing.kind).toBe('untimed');
    expect(JSON.parse(attempts[0].body)).toEqual({ version: { type: 'saved_test_version', id: attempt.version_id }, mode: 'study', timing: { kind: 'untimed' } });
    expect(window.location.hash).toBe('#/attempts/' + attempt.id);
    expect(JSON.stringify({ local: { ...localStorage }, session: { ...sessionStorage }, hash: window.location.hash })).not.toContain(raw);
  }, 60000);
});
