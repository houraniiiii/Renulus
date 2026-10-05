// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { spawn, type ChildProcess } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterAll, beforeAll, expect, it, vi } from 'vitest';
import { NavigationProvider, useNavigation } from '../../shell/navigation';
import UpdatesPage from '../updates';
import AssessmentPage from './index';
import type { ReviewResult, Session } from './types';

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../../../..');
const testProfile = mkdtempSync(join(tmpdir(), 'renulus-currency-ui-'));
const originalFetch = globalThis.fetch;
let backend: ChildProcess;
let origin = '';

async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await originalFetch(origin + '/api/v1' + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'x-renulus-token': 'currency-fixture-session', 'content-type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<T>;
}

beforeAll(async () => {
  const reservation = createServer();
  await new Promise<void>(resolve => reservation.listen(0, '127.0.0.1', resolve));
  const address = reservation.address();
  if (!address || typeof address === 'string') throw new Error('Could not allocate an isolated currency test port.');
  const port = address.port;
  await new Promise<void>((resolve, reject) => reservation.close(error => error ? reject(error) : resolve()));
  origin = 'http://127.0.0.1:' + port;
  backend = spawn('python', [join(repositoryRoot, 'tests/assessment/serve_currency_fixture.py'),
    '--profile', testProfile, '--port', String(port)], {
    cwd: repositoryRoot, windowsHide: true, stdio: 'ignore',
    env: { ...process.env, PYTHONPATH: join(repositoryRoot, 'runtime') },
  });
  let ready = false;
  for (let attempt = 0; attempt < 100; attempt++) {
    try { ready = (await originalFetch(origin + '/api/v1/health')).ok; } catch { /* Bounded local startup. */ }
    if (ready || backend.exitCode !== null) break;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  if (!ready) throw new Error('The isolated currency fixture did not start.');
  vi.stubGlobal('fetch', (input: string | URL | Request, init?: RequestInit) => {
    const value = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
    const url = new URL(value, origin);
    if (url.origin !== origin) throw new Error('Currency UI tests permit loopback requests only.');
    const headers = new Headers(init?.headers);
    headers.set('x-renulus-token', 'currency-fixture-session');
    return originalFetch(url, { ...init, headers });
  });
}, 20_000);

afterAll(async () => {
  cleanup(); vi.unstubAllGlobals();
  if (backend && backend.exitCode === null) {
    const exited = new Promise<void>(resolve => backend.once('exit', () => resolve()));
    backend.kill(); await exited;
  }
  if (testProfile.startsWith(join(tmpdir(), 'renulus-currency-ui-'))) rmSync(testProfile, { recursive: true, force: true });
});

function Journey() {
  const nav = useNavigation();
  return nav.route === 'updates' ? <><button onClick={() => nav.navigate('assessment')}>Return to Test</button><UpdatesPage /></>
    : <AssessmentPage />;
}

it('shows real detected/reviewed/dismissed annotations on pinned questions and history, retaining deterministic results', async () => {
  const session = await request<Session>('/assessment/start', {
    idempotency_key: 'currency-renderer-start', count: 1, selector: { topic_ids: ['T20'] },
  });
  const item = session.current_item!;
  const sources = await request<{ id: string; register_id: string; url: string }[]>('/content/sources');
  const source = sources.find(row => row.id === 'K01-2024')!;
  const publication = await request<{ id: string }>('/updates/publications', {
    source_id: source.register_id, url: source.url,
    permission_reference: 'Synthetic renderer fixture; no live publisher check',
  });
  const check = '/updates/publications/' + publication.id + '/check?force=true';
  expect((await request<{ state: string }>(check, {})).state).toBe('baseline');
  expect((await request<{ state: string }>(check, {})).state).toBe('changed');
  const entries = await request<{ entries: { id: string; kind: string }[] }>('/updates/entries');
  const entry = entries.entries.find(row => row.kind === 'publication-change')!;
  const pinned = JSON.parse(readFileSync(join(repositoryRoot, 'content/packs/renulus-foundations/1.0.0/questions.json'), 'utf8'))
    .find((question: { id: string }) => question.id === item.question_id) as {
      answer: string; rationale: string; options: { id: string; text: string }[];
    };

  window.location.hash = '#/assessment';
  render(<NavigationProvider><Journey /></NavigationProvider>);
  await screen.findByText('1 question needs source re-review');
  fireEvent.click(screen.getByText('Open session'));
  await screen.findByText('Source change needs question review');
  const pendingNotice = screen.getByText('Source change needs question review').closest('.assessment-source-currency');
  expect(document.activeElement).toBe(pendingNotice);
  expect(screen.queryByText('Why this answer')).toBeNull();
  expect(screen.queryByText(pinned.rationale)).toBeNull();
  fireEvent.click(screen.getByText('Source notice details (1)'));
  expect(screen.getByText(source.id)).toBeDefined();
  expect(screen.getByText('Awaiting notice review')).toBeDefined();
  expect((await request<Session>('/assessment/sessions/' + session.id)).current_item?.assisted).toBe(false);

  fireEvent.click(screen.getByText('Pause'));
  await screen.findByText('Quiz paused');
  expect(screen.getByText('1 unanswered question is affected.')).toBeDefined();
  fireEvent.click(screen.getByText('View source updates'));
  await screen.findByRole('heading', { name: 'Stay current.', level: 1 });
  fireEvent.click(screen.getByText('Return to Test'));
  await screen.findByText('1 question needs source re-review');
  fireEvent.click(screen.getByText('Open session'));
  await screen.findByText('Quiz paused');
  fireEvent.click(screen.getByText('Resume quiz'));
  await screen.findByText('Source change needs question review');
  const answerOption = screen.getByLabelText(pinned.options.find(option => option.id === pinned.answer)!.text);
  answerOption.focus(); fireEvent.click(answerOption);
  expect(document.activeElement).toBe(answerOption);
  fireEvent.click(screen.getByText('Commit answer'));
  await screen.findByText('Why this answer');
  expect(screen.getByText('Correct')).toBeDefined();
  expect(screen.getByText(/Recorded answer and score are retained/)).toBeDefined();
  const original = await request<ReviewResult>('/assessment/sessions/' + session.id + '/review');
  expect(original.scores.reviewed.fresh.correct).toBe(1);
  expect(original.scores.reviewed.assisted.answered).toBe(0);
  const recorded = original.feedback[0];

  await request('/updates/entries/' + entry.id + '/review', {
    state: 'reviewed', summary: 'Synthetic software sequence; no educational review claimed',
    target: { register_id: 'K01', canonical_url: source.url },
    changes: { correction: 'Synthetic correction reference' },
    evidence: [{ url: source.url, locator: 'Synthetic publisher fixture',
      finding: 'Synthetic bytes only; no medical correctness claim', checked_on: '2026-10-04', inspected: true }],
  });
  fireEvent.click(screen.getByText('Back to quizzes'));
  await screen.findByText('1 question needs source re-review');
  fireEvent.click(screen.getByText('Open session'));
  await screen.findByText('All selected answers are committed');
  fireEvent.click(screen.getByText('Review committed answers'));
  await screen.findByText('Source notice reviewed; question review still needed');
  expect(screen.getByText('Why this answer').nextElementSibling?.textContent).toBe(pinned.rationale);
  const reviewed = await request<ReviewResult>('/assessment/sessions/' + session.id + '/review');
  expect(reviewed.feedback[0].source_currency?.needs_re_review).toBe(true);
  expect(reviewed.scores).toEqual(original.scores);
  expect(reviewed.feedback[0].correct_option_ids).toEqual(recorded.correct_option_ids);

  await request('/updates/entries/' + entry.id + '/review', {
    state: 'dismissed', summary: 'Synthetic notice dismissed; original question and key retained',
  });
  fireEvent.click(screen.getByText('Back to quizzes'));
  await screen.findByText('Dismissed source notices on 1 question');
  fireEvent.click(screen.getByText('Open session'));
  await screen.findByText('All selected answers are committed');
  fireEvent.click(screen.getByText('Review committed answers'));
  await screen.findByText('Source notice dismissed');
  const dismissed = await request<ReviewResult>('/assessment/sessions/' + session.id + '/review');
  expect(dismissed.scores).toEqual(original.scores);
  expect(dismissed.feedback[0].correct_option_ids).toEqual(recorded.correct_option_ids);
  expect(dismissed.feedback[0].committed_at).toBe(recorded.committed_at);
  expect(dismissed.feedback[0].item).toEqual(recorded.item);
  expect(screen.getByText('Correct')).toBeDefined();
  const answer = screen.getByText('Reviewed answer').nextElementSibling!;
  expect(answer.textContent).toBe(pinned.options.find(option => option.id === pinned.answer)!.text);
  await waitFor(() => expect(window.location.hash).toBe('#/assessment'));
}, 25_000);
