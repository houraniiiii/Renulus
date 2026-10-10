// @vitest-environment jsdom
import { cleanup, configure, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { spawn, type ChildProcess } from 'node:child_process';
import { mkdtempSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterAll, afterEach, beforeAll, expect, it, vi } from 'vitest';
import { fixturePython, fixtureReady, stopFixture } from '../../testBackend';
import { api } from '../../platform/api';
import ImportPanel from './ImportPanel';
import { originalSlice, type ImportDraft, type ImportedVersion } from './types';

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../../../..');
const profile = mkdtempSync(join(process.env.RENULUS_TEST_STATE_ROOT || tmpdir(), 'imports-ui-'));
const originalFetch = globalThis.fetch;
let backend: ChildProcess | undefined, origin = '', losePath = '';
const sent: { path: string; body: string; method: string }[] = [];
const TEXT = '  1. Which synthetic CKD value is supplied?\nA. -1 mmol/L\nB. +1 mmol/L\nAnswer: A\n\n2. Which dialysis learning choice is supported?\nA. First option\nB. Second option\n  ';
configure({ asyncUtilTimeout: 8000 });
vi.setConfig({ testTimeout: 30_000 });

beforeAll(async () => {
  const reservation = createServer();
  await new Promise<void>(resolve => reservation.listen(0, '127.0.0.1', resolve));
  const address = reservation.address();
  if (!address || typeof address === 'string') throw new Error('Owned fixture port unavailable');
  await new Promise<void>((resolve, reject) => reservation.close(error => error ? reject(error) : resolve()));
  origin = 'http://127.0.0.1:' + address.port;
  const runtimeRoot = join(repositoryRoot, 'runtime');
  const bootstrap = [
    'import sys, asyncio, json, os, hashlib, shutil', 'from pathlib import Path',
    'sys.path[:0] = ' + JSON.stringify([runtimeRoot, join(repositoryRoot, 'tests/assessment')]),
    'import renulus', 'assert Path(renulus.__file__).resolve().parent.parent == Path(' + JSON.stringify(runtimeRoot) + ').resolve()',
    'import renulus.server as server',
    'server.MODULE_ORDER = ("runtime","content","knowledge","learn","cases","assessment","memory","study")',
    'from test_saved_imports import SyntheticTransport, normalized',
    'from renulus.assessment.import_api import create_router',
    'root = Path(' + JSON.stringify(profile) + ')',
    'assets = os.environ.get("RENULUS_SAVED_EXTRACTION_ASSETS")',
    'if assets:',
    '    manifest = json.loads(Path(' + JSON.stringify(join(repositoryRoot, 'packaging/runtime/helper-assets.json')) + ').read_text())',
    '    for record in manifest["groups"]["embedding"]["files"]:',
    '        source = Path(assets)/record["path"]',
    '        assert source.stat().st_size == record["size"] and hashlib.sha256(source.read_bytes()).hexdigest() == record["sha256"]',
    '        target = root/"helpers"/record["path"]', '        target.parent.mkdir(parents=True,exist_ok=True)', '        shutil.copyfile(source,target)',
    '    (root/"helpers/manifest.json").write_text(json.dumps(manifest))',
    'app = server.create_app(' + JSON.stringify(profile) + ', token="imports-ui-fixture")',
    'services = app.state.services',
    'if "saved_imports" not in services.registry: app.include_router(create_router(services), prefix="/api/v1")',
    'imports = services.get("saved_imports")', 'provider = services.get("provider")', 'transport = SyntheticTransport()',
    'provider._settings["connections"]["codex"] = {"access_token":"synthetic-import-token","expires_at":9999999999}',
    'provider._settings["selected_provider"] = "codex"',
    'provider._settings.setdefault("selected_models",{})["codex"] = "gpt-6.1-sol"', 'provider._transport = transport',
    'library_revision = None',
    'if assets:',
    '    result = services.get("knowledge").import_text(' + JSON.stringify(TEXT) + ',title="Synthetic renderer saved Library test")',
    '    assert result["status"] == "ready", result', '    library_revision = result["revision_id"]',
    'services.on_startup = [services.get("saved_tests").backfill_legacy, imports.recover]',
    'services.on_shutdown = [provider.close, imports.close]',
    '@app.post("/__imports_fixture/scenario")', 'async def scenario(body: dict):',
    '    transport.error = None', '    transport.release = None', '    transport.started.clear()',
    '    text = services.db.fetch_one("SELECT original_text FROM assessment_test_imports WHERE id=?",(body["id"],))["original_text"]',
    '    value = normalized(text)',
    '    if body["mode"] == "invalid": value["candidates"][0]["correct_option_ids"] = ["a"]',
    '    if body["mode"] == "wait": transport.release = asyncio.Event()',
    '    transport.responses = [None] * len(transport.calls) + [value]', '    return {"calls":len(transport.calls)}',
    '@app.get("/__imports_fixture/stats")', 'async def stats():',
    '    return {"calls":len(transport.calls),"imports":services.db.fetch_one("SELECT COUNT(*) AS n FROM assessment_test_imports")["n"],"versions":services.db.fetch_one("SELECT COUNT(*) AS n FROM assessment_test_versions")["n"],"library_revision":library_revision}',
    'import uvicorn', 'uvicorn.run(app,host="127.0.0.1",port=' + address.port + ',access_log=False,log_level="warning")',
  ].join('\n');
  let startupError = '';
  backend = spawn(fixturePython(repositoryRoot), ['-c', bootstrap], { cwd: repositoryRoot, windowsHide: true,
    stdio: ['ignore', 'ignore', 'pipe'], env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1', PYTHONPATH: runtimeRoot } });
  backend.stderr?.on('data', chunk => { startupError = (startupError + String(chunk)).slice(-2500); });
  backend.on('error', error => { startupError = error.message; });
  if (!await fixtureReady(backend, origin, originalFetch)) throw new Error('Import fixture did not start: ' + startupError);
  vi.stubGlobal('fetch', async (input: string | URL | Request, init?: RequestInit) => {
    const raw = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
    const url = new URL(raw, origin), headers = new Headers(init?.headers);
    headers.set('x-renulus-token', 'imports-ui-fixture');
    sent.push({ path: url.pathname, method: init?.method || 'GET', body: String(init?.body || '') });
    const response = await originalFetch(url, { ...init, headers });
    if (losePath && url.pathname === losePath && init?.method === 'POST' && response.ok) {
      losePath = ''; await response.text(); throw new TypeError('Synthetic lost acknowledgement after real commit');
    }
    return response;
  });
}, 75_000);
afterEach(() => { cleanup(); losePath = ''; });
afterAll(async () => { configure({ asyncUtilTimeout: 1000 }); vi.resetConfig(); vi.unstubAllGlobals(); await stopFixture(backend); }, 20_000);

it('uses the original Python Unicode character locations, including supplementary characters', () => {
  expect(originalSlice('🧪 Renal Δ value', { start: 2, end: 7 })).toBe('Renal');
});

async function request<T>(path: string, method = 'GET', body?: object, key?: string): Promise<T> {
  const response = await fetch(path, { method, headers: { 'Content-Type': 'application/json', ...(key ? { 'Idempotency-Key': key } : {}) }, body: body ? JSON.stringify(body) : undefined });
  expect(response.ok, await response.clone().text()).toBe(true);
  return response.json() as Promise<T>;
}
const stats = () => request<{ calls: number; imports: number; versions: number; library_revision: string | null }>('/__imports_fixture/stats');
const scenario = (id: string, mode: string) => request('/__imports_fixture/scenario', 'POST', { id, mode });
const review = () => screen.getByRole('region', { name: 'Import review' });
const question = () => screen.getByRole('region', { name: 'Question 1' });
async function draftFromUI() { return (await request<{ items: ImportDraft[] }>('/api/v1/assessment/imports')).items[0]; }
function fillOriginal(title: string) {
  fireEvent.change(screen.getByLabelText('Import title'), { target: { value: title } });
  fireEvent.change(screen.getByLabelText('Original test text'), { target: { value: TEXT } });
  fireEvent.change(screen.getByLabelText('Retained permission or terms'), { target: { value: 'Synthetic retained personal terms' } });
  fireEvent.click(screen.getByLabelText('I may store and use this text for private model-assisted practice'));
}
async function create(title: string) {
  render(<ImportPanel />); fillOriginal(title);
  fireEvent.click(screen.getByRole('button', { name: 'Save private original' }));
  await screen.findByRole('region', { name: 'Question 1' }); return draftFromUI();
}

it('recovers lost acknowledgements, edits/removes/reviews and publishes actual personal setup', async () => {
  const opened = vi.fn(), saved = vi.fn(), before = await stats();
  render(<ImportPanel onOpenVersion={opened} onSaved={saved} />);
  fillOriginal('Renderer imported renal practice'); losePath = '/api/v1/assessment/imports'; const start = sent.length;
  fireEvent.click(screen.getByRole('button', { name: 'Save private original' }));
  await screen.findByText('Your command needs a retry');
  expect((screen.getByLabelText('Original test text') as HTMLTextAreaElement).value).toBe(TEXT);
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
  await screen.findByRole('region', { name: 'Question 1' });
  const row = await draftFromUI();
  const creates = sent.slice(start).filter(item => item.method === 'POST' && item.path === '/api/v1/assessment/imports');
  expect(creates.length).toBe(2); expect(creates[0].body).toBe(creates[1].body);
  expect((await request<{ text: string }>('/api/v1/assessment/imports/' + row.id + '/original')).text).toBe(TEXT);
  expect((await stats()).calls).toBe(before.calls);
  expect((within(review()).getByRole('button', { name: 'Save 2 reviewed questions' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(within(question()).getByLabelText('Question text'), { target: { value: 'Personal transplant learning edit' } });
  fireEvent.click(within(question()).getByRole('button', { name: 'Save edits' }));
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Save edits' })).toBeNull());
  expect(within(question()).getByText('Review after edit')).toBeTruthy();
  expect(within(question()).getByText('Your edit requires a new answer review. Select the correct answers and confirm them against the unchanged original.')).toBeTruthy();
  expect(within(question()).queryByText('The original supplies no clear answer. Choose only answers you can personally resolve.')).toBeNull();
  await waitFor(() => { const answer = within(question()).getByLabelText('Correct answer A') as HTMLInputElement; expect(answer.disabled).toBe(false); expect(answer.checked).toBe(false); });
  fireEvent.click(within(question()).getByLabelText('Correct answer A'));
  fireEvent.click(within(question()).getByLabelText('I checked this question and chosen answers against the original'));
  await waitFor(() => expect((within(question()).getByRole('button', { name: 'Confirm answer and review' }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(within(question()).getByRole('button', { name: 'Confirm answer and review' }));
  await waitFor(() => expect(within(question()).getByText('Reviewed by you')).toBeTruthy());
  fireEvent.click(within(screen.getByRole('navigation', { name: 'Imported questions' })).getByRole('button', { name: /Question 2/ }));
  const second = screen.getByRole('region', { name: 'Question 2' });
  expect((within(second).getByLabelText('Correct answer A') as HTMLInputElement).checked).toBe(false);
  fireEvent.click(within(second).getByRole('button', { name: 'Remove from set' }));
  await waitFor(() => expect((within(review()).getByRole('button', { name: 'Save 1 reviewed questions' }) as HTMLButtonElement).disabled).toBe(false));
  losePath = '/api/v1/assessment/imports/' + row.id + '/save';
  fireEvent.click(within(review()).getByRole('button', { name: 'Save 1 reviewed questions' }));
  await screen.findByText('Your command needs a retry'); fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
  await screen.findByRole('button', { name: 'Open saved test' }); fireEvent.click(screen.getByRole('button', { name: 'Open saved test' }));
  expect(opened).toHaveBeenCalledOnce(); expect(saved).toHaveBeenCalledOnce();
  const version = opened.mock.calls[0][0] as ImportedVersion;
  const setup = await request<{ can_start: boolean; version: { item_count: number; origin: string; review_quality: string } }>('/api/v1/assessment/tests/versions/' + version.version_id + '/setup');
  expect(setup.can_start).toBe(true); expect(setup.version.item_count).toBe(1); expect(setup.version.origin).toBe('imported'); expect(setup.version.review_quality).toBe('personal');
  const after = await stats(); expect(after.imports).toBe(before.imports + 1); expect(after.versions).toBe(before.versions + 1); expect(after.calls).toBe(before.calls);
});

it('keeps edits through failed normalization and retries only on explicit action', async () => {
  const row = await create('Renderer bounded normalization'); const before = await stats();
  fireEvent.change(within(question()).getByLabelText('Question text'), { target: { value: 'Retained private edited question' } });
  fireEvent.click(within(question()).getByRole('button', { name: 'Save edits' }));
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Save edits' })).toBeNull());
  await scenario(row.id, 'invalid'); fireEvent.click(screen.getByRole('button', { name: 'Normalize with selected connection' }));
  await screen.findByText('The response could not be mapped safely to the original. Your original and edits are retained.');
  expect((within(question()).getByLabelText('Question text') as HTMLTextAreaElement).value).toBe('Retained private edited question');
  expect((await stats()).calls).toBe(before.calls + 1);
  await scenario(row.id, 'valid'); fireEvent.click(screen.getByRole('button', { name: 'Retry normalization explicitly' }));
  await waitFor(() => expect(within(review()).getByText(/2 of 3 normalization requests/)).toBeTruthy());
  expect((within(question()).getByLabelText('Question text') as HTMLTextAreaElement).value).toBe('Retained private edited question');
  expect((await stats()).calls).toBe(before.calls + 2);
  expect((await request<{ text: string }>('/api/v1/assessment/imports/' + row.id + '/original')).text).toBe(TEXT);
});

it('stops actual provider work and reopens its retained draft without another call', async () => {
  const row = await create('Renderer stopped normalization'); const before = await stats();
  await scenario(row.id, 'wait'); fireEvent.click(screen.getByRole('button', { name: 'Normalize with selected connection' }));
  await screen.findByRole('button', { name: 'Stop normalization' });
  await waitFor(async () => expect((await stats()).calls).toBe(before.calls + 1));
  fireEvent.click(screen.getByRole('button', { name: 'Stop normalization' }));
  await screen.findByText('Normalization is stopped. Continue reviewing the retained original and candidates.');
  cleanup(); render(<ImportPanel importId={row.id} />);
  await screen.findByText('Normalization is stopped. Continue reviewing the retained original and candidates.');
  expect((await stats()).calls).toBe(before.calls + 1);
});

it('consumes a real imported version in Test and hides content while neutral Stop stays available', async () => {
  const row = await create('Renderer Test restricted private original');
  await scenario(row.id, 'wait'); const before = await stats();
  fireEvent.click(screen.getByRole('button', { name: 'Normalize with selected connection' }));
  await screen.findByRole('button', { name: 'Stop normalization' });
  await waitFor(async () => expect((await stats()).calls).toBe(before.calls + 1));
  const base = '/api/v1/assessment/imports';
  let ready = await request<ImportDraft>(base, 'POST', { idempotency_key: crypto.randomUUID(), title: 'Independent explicit Test setup',
    original: { kind: 'paste', text: TEXT, terms: 'Synthetic explicit personal terms', permission_confirmed: true } });
  for (const item of ready.candidates) ready = await request<ImportDraft>(base + '/' + ready.id + '/candidates/' + item.id + '/resolve', 'POST',
    { idempotency_key: crypto.randomUUID(), expected_revision: ready.revision, correct_option_ids: ['a'], review_confirmed: true });
  ready = await request<ImportDraft>(base + '/' + ready.id + '/save', 'POST', { idempotency_key: crypto.randomUUID(), expected_revision: ready.revision });
  const attempt = await api<{ id: string; draft_revision: number }>('/assessment/test-attempts', { method: 'POST',
    headers: { 'Idempotency-Key': crypto.randomUUID() }, body: { version: { type: 'saved_test_version', id: ready.result?.version_id }, mode: 'test' } });
  try {
    await screen.findByText('Import assistance is paused during Test. You can stop normalization without opening its content.');
    expect(screen.queryByRole('region', { name: 'Immutable original' })).toBeNull();
    expect(screen.queryByLabelText('Original test text')).toBeNull();
    expect(screen.queryByText('Renderer Test restricted private original')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Stop normalization' }));
    await waitFor(async () => {
      const response = await fetch(base + '/' + row.id + '/cancel', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ idempotency_key: 'synthetic-policy-neutral-replay' }) });
      expect(response.status).toBe(200); expect(await response.json()).toEqual({ id: row.id, state: 'cancelled' });
    });
    expect((await stats()).calls).toBe(before.calls + 1);
  } finally {
    await request('/api/v1/assessment/test-attempts/' + attempt.id + '/submit', 'POST', { expected_draft_revision: attempt.draft_revision }, crypto.randomUUID());
  }
});

it.skipIf(!process.env.RENULUS_SAVED_EXTRACTION_ASSETS)('imports an actual extracted saved Library revision and opens its typed original reference', async () => {
  const before = await stats(), location = vi.fn();
  expect(before.library_revision).toBeTruthy();
  render(<ImportPanel sourceRevisionId={before.library_revision!} onOpenSource={location} />);
  await waitFor(() => expect((screen.getByLabelText('Saved Library revision') as HTMLSelectElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: 'Save private original' }));
  await screen.findByRole('region', { name: 'Question 1' });
  const row = await draftFromUI();
  expect(row.source_kind).toBe('library_revision'); expect(row.source_revision_id).toBe(before.library_revision);
  fireEvent.click(await screen.findByRole('button', { name: 'Open original location' }));
  expect(location).toHaveBeenCalledOnce(); expect(location.mock.calls[0][0].target).toEqual({ type: 'library_revision', id: before.library_revision });
  await scenario(row.id, 'valid'); fireEvent.click(screen.getByRole('button', { name: 'Normalize with selected connection' }));
  await waitFor(async () => expect((await request<ImportDraft>('/api/v1/assessment/imports/' + row.id)).state).toBe('draft'));
  expect((await stats()).calls).toBe(before.calls + 1);
  expect((screen.getByRole('button', { name: 'Save 2 reviewed questions' }) as HTMLButtonElement).disabled).toBe(true);
});
