// @vitest-environment jsdom
import { cleanup, configure, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { spawn, type ChildProcess } from 'node:child_process';
import { mkdtempSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { fixturePython, fixtureReady, stopFixture } from '../../testBackend';
import GenerationPanel from './GenerationPanel';
import type { GeneratedVersion, GenerationJob } from './types';

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../../../..');
const profile = mkdtempSync(join(process.env.RENULUS_TEST_STATE_ROOT || tmpdir(), 'generation-ui-'));
const originalFetch = globalThis.fetch;
let backend: ChildProcess | undefined, origin = '', loseCreate = false;
const sent: { path: string; method: string; body: string }[] = [];
configure({ asyncUtilTimeout: 8000 });
vi.setConfig({ testTimeout: 30_000 });

beforeAll(async () => {
  const reservation = createServer();
  await new Promise<void>(resolve => reservation.listen(0, '127.0.0.1', resolve));
  const address = reservation.address();
  if (!address || typeof address === 'string') throw new Error('An owned fixture port could not be allocated.');
  await new Promise<void>((resolve, reject) => reservation.close(error => error ? reject(error) : resolve()));
  origin = 'http://127.0.0.1:' + address.port;
  const runtimeRoot = join(repositoryRoot, 'runtime');
  const bootstrap = [
    'import sys, asyncio, json', 'from pathlib import Path',
    'sys.path[:0] = ' + JSON.stringify([runtimeRoot, join(repositoryRoot, 'tests/assessment')]),
    'import renulus',
    'assert Path(renulus.__file__).resolve().parent.parent == Path(' + JSON.stringify(runtimeRoot) + ').resolve()',
    'import renulus.server as server',
    'server.MODULE_ORDER = ("runtime","content","knowledge","learn","cases","assessment","memory","study")',
    'from test_saved_generation import SyntheticTransport, batch',
    'from renulus.assessment.generation_api import create_router',
    'app = server.create_app(' + JSON.stringify(profile) + ', token="generation-ui-fixture")',
    'services = app.state.services',
    'if "saved_generation" not in services.registry: app.include_router(create_router(services), prefix="/api/v1")',
    'generation = services.get("saved_generation")',
    'provider = services.get("provider")',
    'transport = SyntheticTransport()',
    'provider._settings["connections"]["codex"] = {"access_token":"synthetic-generation-token","expires_at":9999999999}',
    'provider._settings["selected_provider"] = "codex"',
    'provider._settings.setdefault("selected_models",{})["codex"] = "gpt-6.1-sol"',
    'provider._transport = transport',
    'services.on_startup = [services.get("saved_tests").backfill_legacy, generation.recover]',
    'services.on_shutdown = [provider.close, generation.close]',
    '@app.post("/__generation_fixture/scenario")',
    'async def scenario(body: dict):',
    '    transport.error = None', '    transport.release = None', '    transport.started.clear()',
    '    offset = len(transport.calls)', '    transport.responses = [batch(i*5) for i in range(offset)]',
    '    if body["mode"] == "short": transport.responses += [batch(offset*5), batch(offset*5+5,2)]',
    '    if body["mode"] == "wait": transport.release = asyncio.Event()',
    '    return {"calls":offset}',
    '@app.get("/__generation_fixture/stats")',
    'async def stats():',
    '    return {"calls":len(transport.calls),"jobs":services.db.fetch_one("SELECT COUNT(*) AS n FROM assessment_test_jobs WHERE operation=\'generate_test\'")["n"],"versions":services.db.fetch_one("SELECT COUNT(*) AS n FROM assessment_test_versions")["n"]}',
    'import uvicorn',
    'uvicorn.run(app,host="127.0.0.1",port=' + address.port + ',access_log=False,log_level="warning")',
  ].join('\n');
  let startupError = '';
  backend = spawn(fixturePython(repositoryRoot), ['-c', bootstrap], { cwd: repositoryRoot,
    windowsHide: true, stdio: ['ignore', 'ignore', 'pipe'],
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1', PYTHONPATH: runtimeRoot } });
  backend.stderr?.on('data', chunk => { startupError = (startupError + String(chunk)).slice(-2500); });
  backend.on('error', error => { startupError = error.message; });
  if (!await fixtureReady(backend, origin, originalFetch)) throw new Error('Generation fixture did not start: ' + startupError);
  vi.stubGlobal('fetch', async (input: string | URL | Request, init?: RequestInit) => {
    const raw = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
    const url = new URL(raw, origin), headers = new Headers(init?.headers);
    headers.set('x-renulus-token', 'generation-ui-fixture');
    sent.push({ path: url.pathname, method: init?.method || 'GET', body: String(init?.body || '') });
    const response = await originalFetch(url, { ...init, headers });
    if (loseCreate && init?.method === 'POST' && url.pathname.endsWith('/generation/jobs') && response.ok) {
      loseCreate = false; await response.text();
      throw new TypeError('Synthetic lost acknowledgement after real job commit');
    }
    return response;
  });
}, 75_000);
afterEach(() => { cleanup(); loseCreate = false; });
afterAll(async () => {
  configure({ asyncUtilTimeout: 1000 }); vi.resetConfig(); vi.unstubAllGlobals();
  await stopFixture(backend);
}, 20_000);

async function request<T>(path: string, method = 'GET', body?: object): Promise<T> {
  const response = await globalThis.fetch(path, { method, headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined });
  expect(response.status).toBe(200);
  return response.json() as Promise<T>;
}
const scenario = (mode: string) => request('/__generation_fixture/scenario', 'POST', { mode });
const stats = () => request<{ calls: number; jobs: number; versions: number }>('/__generation_fixture/stats');
const progress = () => screen.getByRole('region', { name: 'Generation progress' });

describe('generation with real local persistence and selected ProviderManager transport', () => {
  it('retries the exact lost create acknowledgement and opens the same saved five-question version', async () => {
    await scenario('valid'); const before = await stats();
    const opened = vi.fn(), published = vi.fn();
    render(<GenerationPanel initial={{ title: 'Renderer quick renal learning' }} onOpenVersion={opened} onPublished={published} />);
    await screen.findByLabelText('Learning topic');
    loseCreate = true; const start = sent.length;
    fireEvent.click(screen.getByRole('button', { name: 'Generate 5 questions' }));
    await screen.findByText('Your command needs a retry');
    expect((screen.getByRole('button', { name: 'Generate 5 questions' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await screen.findByText('Your generated personal practice is saved. Choose Study or Test when you are ready.');
    expect(within(progress()).getByText('saved questions')).toBeTruthy();
    expect(screen.queryByText('PRIVATE_GENERATED_EXPLANATION')).toBeNull();
    fireEvent.click(within(progress()).getByRole('button', { name: 'Open saved test' }));
    expect(opened).toHaveBeenCalledOnce(); expect(published).toHaveBeenCalledOnce();
    const version = opened.mock.calls[0][0] as GeneratedVersion;
    const setup = await request<{ version: { item_count: number; origin: string }; can_start: boolean }>('/api/v1/assessment/tests/versions/' + version.version_id + '/setup');
    expect(setup.version.item_count).toBe(5); expect(setup.version.origin).toBe('generated'); expect(setup.can_start).toBe(true);
    const creates = sent.slice(start).filter(item => item.method === 'POST' && item.path.endsWith('/generation/jobs'));
    expect(creates.length).toBe(2); expect(creates[0].body).toBe(creates[1].body);
    const after = await stats(); expect(after.calls).toBe(before.calls + 1); expect(after.jobs).toBe(before.jobs + 1); expect(after.versions).toBe(before.versions + 1);
  });

  it('requires explicit seven-question acceptance and opens the actual shorter saved version', async () => {
    await scenario('short'); const before = await stats(); const opened = vi.fn();
    render(<GenerationPanel initial={{ title: 'Renderer shorter set', count: 10 }} onOpenVersion={opened} />);
    fireEvent.click(screen.getByRole('button', { name: 'Generate 10 questions' }));
    await screen.findByText('Accept a 7-question set');
    expect((screen.getByRole('button', { name: 'Save these 7 questions' }) as HTMLButtonElement).disabled).toBe(true);
    expect((await stats()).versions).toBe(before.versions);
    fireEvent.click(screen.getByLabelText('Accept a 7-question set'));
    fireEvent.click(screen.getByRole('button', { name: 'Save these 7 questions' }));
    await screen.findByText('Your generated personal practice is saved. Choose Study or Test when you are ready.');
    expect(within(progress()).getByText('7')).toBeTruthy();
    fireEvent.click(within(progress()).getByRole('button', { name: 'Open saved test' }));
    const version = opened.mock.calls[0][0] as GeneratedVersion;
    const setup = await request<{ version: { item_count: number } }>('/api/v1/assessment/tests/versions/' + version.version_id + '/setup');
    expect(setup.version.item_count).toBe(7);
    expect((await stats()).calls).toBe(before.calls + 2);
  });

  it('neutral Stop, reopening and explicit remaining-work retry do not silently restart provider work', async () => {
    await scenario('wait'); const before = await stats(); const created = vi.fn();
    render(<GenerationPanel initial={{ title: 'Renderer stopped set' }} onJobCreated={created} />);
    fireEvent.click(screen.getByRole('button', { name: 'Generate 5 questions' }));
    await screen.findByRole('button', { name: 'Stop generation' });
    await waitFor(async () => expect((await stats()).calls).toBe(before.calls + 1));
    fireEvent.click(screen.getByRole('button', { name: 'Stop generation' }));
    await screen.findByText('Generation stopped. Validated questions are retained; reopening does not send another request.');
    const identifier = (created.mock.calls[0][0] as GenerationJob).id;
    cleanup();
    render(<GenerationPanel jobId={identifier} />);
    await screen.findByText('Generation stopped. Validated questions are retained; reopening does not send another request.');
    expect((await stats()).calls).toBe(before.calls + 1);
    const start = sent.length;
    await scenario('valid');
    fireEvent.click(screen.getByRole('button', { name: 'Retry remaining questions' }));
    await screen.findByText('Your generated personal practice is saved. Choose Study or Test when you are ready.');
    expect((await stats()).calls).toBe(before.calls + 2);
    expect(sent.slice(start).filter(item => item.method === 'POST' && item.path.endsWith('/retry')).length).toBe(1);
  });
});
