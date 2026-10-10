// @vitest-environment jsdom
import { cleanup, configure, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { spawn, type ChildProcess } from 'node:child_process';
import { mkdtempSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { NavigationProvider, useNavigation } from '../../shell/navigation';
import { fixturePython, fixtureReady, stopFixture } from '../../testBackend';
import Tests from './index';
import type { PublishedTest, TestPage, TestSetup } from './types';

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../../../..');
const profile = mkdtempSync(join(process.env.RENULUS_TEST_STATE_ROOT || tmpdir(), 'renulus-saved-tests-ui-'));
const originalFetch = globalThis.fetch;
const requests: { path: string; method: string; body: string }[] = [];
let backend: ChildProcess | undefined, origin = '', losePath: RegExp | null = null;
vi.setConfig({ testTimeout: 30_000 });
configure({ asyncUtilTimeout: 5_000 });

beforeAll(async () => {
  const reservation = createServer();
  await new Promise<void>(resolve => reservation.listen(0, '127.0.0.1', resolve));
  const address = reservation.address();
  if (!address || typeof address === 'string') throw new Error('An owned fixture port could not be allocated.');
  await new Promise<void>((resolve, reject) => reservation.close(error => error ? reject(error) : resolve()));
  origin = 'http://127.0.0.1:' + address.port;
  const runtimeRoot = join(repositoryRoot, 'runtime');
  const bootstrap = [
    'import sys', 'from pathlib import Path',
    'sys.path[:0] = ' + JSON.stringify([runtimeRoot, join(repositoryRoot, 'tests/assessment')]),
    'import renulus',
    'assert Path(renulus.__file__).resolve().parent.parent == Path(' + JSON.stringify(runtimeRoot) + ').resolve()',
    'import renulus.server as server',
    'from conftest import SyntheticContentRepository',
    'from renulus.assessment.test_api import create_router',
    'app = server.create_app(' + JSON.stringify(profile) + ', token="saved-tests-fixture")',
    'app.state.services.registry["content"] = SyntheticContentRepository()',
    'if "saved_tests" not in app.state.services.registry: app.include_router(create_router(app.state.services), prefix="/api/v1")',
    'import uvicorn',
    'uvicorn.run(app, host="127.0.0.1", port=' + address.port + ', access_log=False, log_level="warning")',
  ].join('\n');
  let startupError = '';
  backend = spawn(fixturePython(repositoryRoot), ['-c', bootstrap], { cwd: repositoryRoot,
    windowsHide: true, stdio: ['ignore', 'ignore', 'pipe'],
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1', PYTHONPATH: runtimeRoot } });
  backend.stderr?.on('data', chunk => { startupError = (startupError + String(chunk)).slice(-2000); });
  backend.on('error', error => { startupError = error.message; });
  if (!await fixtureReady(backend, origin, originalFetch)) throw new Error('Saved-test fixture did not start: ' + startupError);
  vi.stubGlobal('fetch', async (input: string | URL | Request, init?: RequestInit) => {
    const raw = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
    const url = new URL(raw, origin), headers = new Headers(init?.headers);
    headers.set('x-renulus-token', 'saved-tests-fixture');
    requests.push({ path: url.pathname, method: init?.method || 'GET', body: String(init?.body || '') });
    const response = await originalFetch(url, { ...init, headers });
    if (losePath?.test(url.pathname) && response.ok) {
      losePath = null;
      await response.text();
      throw new TypeError('Synthetic lost acknowledgement after actual commit');
    }
    return response;
  });
}, 75_000);

afterEach(() => { cleanup(); losePath = null; });
afterAll(async () => {
  configure({ asyncUtilTimeout: 1000 }); vi.resetConfig(); vi.unstubAllGlobals();
  await stopFixture(backend);
  // Retain the isolated profile for evidence; no owner state or providers are used.
}, 20_000);

async function request<T>(path: string, method = 'GET', body?: object): Promise<T> {
  const response = await globalThis.fetch('/api/v1/assessment/tests' + path, {
    method, headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined,
  });
  expect(response.status).toBe(200);
  return response.json() as Promise<T>;
}
function mount(versionId?: string) {
  function Card() {
    const { navigate } = useNavigation();
    return <button onClick={() => navigate('assessment', { payload: { version_id: versionId } })}>Open pinned card</button>;
  }
  window.location.hash = '#/assessment';
  render(<NavigationProvider>{versionId && <Card />}<Tests /></NavigationProvider>);
}

describe('saved collection against the real local router and schema', () => {
  it('opens the connected generation controls without creating or starting an attempt', async () => {
    mount(); await screen.findByLabelText('Find a saved test');
    const before = requests.length;
    fireEvent.click(screen.getByRole('button', { name: 'Create test' }));
    await screen.findByRole('heading', { name: 'Create personal practice' });
    expect(Array.from((screen.getByLabelText('Question count') as HTMLSelectElement).options).map(option => option.value)).toEqual(['5', '10', '20']);
    await screen.findByRole('heading', { name: 'Your generation jobs' });
    expect(requests.slice(before).every(request => request.method === 'GET')).toBe(true);
    expect(requests.slice(before).some(request => request.path === '/api/v1/assessment/generation/jobs')).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Close generation' }));
    expect(screen.queryByRole('heading', { name: 'Create personal practice' })).toBeNull();
  });
  it('retries the exact create command, renames, archives and restores the real saved set', async () => {
    const before = (await request<TestPage>('')).items.length;
    mount(); await screen.findByLabelText('Find a saved test');
    fireEvent.click(screen.getByText('New reviewed test'));
    fireEvent.change(screen.getByLabelText('Test title'), { target: { value: 'Renderer renal fixture' } });
    fireEvent.change(screen.getByLabelText('Questions'), { target: { value: '1' } });
    losePath = /\/tests\/reviewed$/;
    const start = requests.length;
    fireEvent.click(screen.getByText('Save test'));
    await screen.findByText('Your request needs a retry');
    expect((screen.getByText('Save test') as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByText('Try again'));
    await screen.findByRole('heading', { name: 'Renderer renal fixture' });
    const sent = requests.slice(start).filter(item => item.path.endsWith('/reviewed'));
    expect(sent.length).toBe(2); expect(sent[0].body).toBe(sent[1].body);
    expect((await request<TestPage>('')).items.length).toBe(before + 1);
    expect(screen.queryByText('PRIVATE_REVIEWED_KEY_SENTINEL')).toBeNull();
    fireEvent.click(screen.getByText('Rename'));
    fireEvent.change(screen.getByLabelText('New title'), { target: { value: 'Renderer dialysis fixture' } });
    fireEvent.click(screen.getByText('Save title'));
    await screen.findByRole('heading', { name: 'Renderer dialysis fixture' });
    fireEvent.click(screen.getByText('Archive'));
    await screen.findByText('Restore');
    expect((screen.getByText('Continue to Study') as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Collection'), { target: { value: 'archived' } });
    await screen.findByRole('button', { name: /Renderer dialysis fixture.*1 questions/ });
    fireEvent.click(screen.getByText('Restore'));
    await screen.findByText('Archive');
    expect((await request<TestPage>('')).items.some(item => item.title === 'Renderer dialysis fixture')).toBe(true);
  });

  it('creates a personal version, retains the original pin and saves a neutral report through retry', async () => {
    const saved = await request<PublishedTest>('/reviewed', 'POST', {
      idempotency_key: crypto.randomUUID(), title: 'Personal version fixture', count: 1,
    });
    mount(saved.version_id); fireEvent.click(screen.getByText('Open pinned card'));
    await screen.findByRole('heading', { name: 'Personal version fixture' });
    fireEvent.click(screen.getByText('Edit personal version'));
    await screen.findByLabelText('Question text');
    expect(screen.queryByText('PRIVATE_REVIEWED_KEY_SENTINEL')).toBeNull();
    fireEvent.change(screen.getByLabelText('Question text'), { target: { value: 'Synthetic personal refinement' } });
    fireEvent.change(screen.getByLabelText('Personal answer key'), { target: { value: 'a' } });
    fireEvent.click(screen.getByText('Save personal version'));
    await waitFor(() => expect(screen.queryByText('Save personal version')).toBeNull());
    const latest = await request<TestSetup>('/' + saved.test_id + '/setup');
    expect(latest.version.ordinal).toBe(2); expect(latest.version.review_quality).toBe('personal');
    expect(latest.can_start).toBe(true);
    const original = await request<TestSetup>('/versions/' + saved.version_id + '/setup');
    expect(original.version.ordinal).toBe(1); expect(original.version.review_quality).toBe('reviewed');
    // The card remains on version one after a new version is published.
    await screen.findByText('Version 1');
    fireEvent.click(screen.getByText('Question seems wrong'));
    await screen.findByLabelText('What seems wrong?');
    fireEvent.change(screen.getByLabelText('What seems wrong?'), { target: { value: 'Synthetic source ambiguity' } });
    losePath = /\/reports$/;
    const start = requests.length;
    fireEvent.click(screen.getByText('Save local report'));
    await screen.findByRole('alert');
    fireEvent.click(screen.getByText('Try again'));
    await screen.findByText('Your local report is saved. The key, review quality and scores have not changed.');
    const reports = requests.slice(start).filter(item => item.path.endsWith('/reports'));
    expect(reports.length).toBe(2); expect(reports[0].body).toBe(reports[1].body);
    expect((await request<TestSetup>('/versions/' + saved.version_id + '/setup')).version.review_quality).toBe('reviewed');
  });

  it('keeps an unresolved edit in Needs review and disables start', async () => {
    const saved = await request<PublishedTest>('/reviewed', 'POST', {
      idempotency_key: crypto.randomUUID(), title: 'Unresolved key fixture', count: 1,
    });
    mount(); await screen.findByRole('button', { name: /Unresolved key fixture.*1 questions/ });
    fireEvent.click(screen.getByRole('button', { name: /Unresolved key fixture.*1 questions/ }));
    await screen.findByText('Edit personal version'); fireEvent.click(screen.getByText('Edit personal version'));
    await screen.findByLabelText('Personal answer key'); fireEvent.click(screen.getByText('Save personal version'));
    await screen.findByText('Resolve missing or ambiguous keys in a personal version before starting.');
    expect((screen.getByText('Continue to Study') as HTMLButtonElement).disabled).toBe(true);
    expect((await request<TestSetup>('/' + saved.test_id + '/setup')).version.status).toBe('needs_review');
  });

  it('requires explicit deletion and shows useful unavailable state for the old pinned card', async () => {
    const saved = await request<PublishedTest>('/reviewed', 'POST', {
      idempotency_key: crypto.randomUUID(), title: 'Deleted collection fixture', count: 1,
    });
    mount(saved.version_id); fireEvent.click(screen.getByText('Open pinned card'));
    await screen.findByRole('heading', { name: 'Deleted collection fixture' });
    fireEvent.click(screen.getByText('Delete'));
    expect(screen.getByText('Delete this saved test?')).toBeDefined();
    fireEvent.click(screen.getByText('Keep test'));
    expect((await request<TestSetup>('/versions/' + saved.version_id + '/setup')).version.id).toBe(saved.version_id);
    fireEvent.click(screen.getByText('Delete')); fireEvent.click(screen.getByText('Delete saved test'));
    await waitFor(() => expect(screen.queryByLabelText('Selected test setup')).toBeNull());
    fireEvent.click(screen.getByText('Open pinned card'));
    const unavailable = await screen.findByRole('alert');
    expect(within(unavailable).getByText('This saved version is unavailable')).toBeDefined();
    expect(screen.queryByText('Continue to Study')).toBeNull();
  });

  it('opens original commitments inline without showing feedback for unanswered legacy items', async () => {
    const response = await globalThis.fetch('/api/v1/assessment/start', { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ idempotency_key: crypto.randomUUID(), count: 2 }) });
    expect(response.status).toBe(200);
    const session = await response.json() as { id: string; current_item: { id: string } };
    const answer = await globalThis.fetch('/api/v1/assessment/sessions/' + session.id + '/answer', { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ idempotency_key: crypto.randomUUID(),
        item_id: session.current_item.id, option_ids: ['a'] }) });
    expect(answer.status).toBe(200);
    mount();
    fireEvent.click(await screen.findByRole('button', { name: /Previous reviewed quiz.*2 questions/ }));
    await screen.findByText('1 committed answers · 1 unscored blanks');
    expect(screen.queryByText('PRIVATE_REVIEWED_KEY_SENTINEL')).toBeNull();
    fireEvent.click(screen.getByText('View original committed answers'));
    await screen.findByText('PRIVATE_REVIEWED_KEY_SENTINEL');
    expect(screen.getByRole('heading', { name: 'Question 1' })).toBeDefined();
    expect(screen.queryByRole('heading', { name: 'Question 2' })).toBeNull();
    expect(screen.getByText('Original commitments and scores are retained. Blanks have no feedback.')).toBeDefined();
  });
});
