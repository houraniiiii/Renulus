// @vitest-environment jsdom
// SPDX-License-Identifier: MIT
/** Actual mounted App/HTTP/SQLite/provider owners. Only external transport is synthetic. */
import { cleanup, configure, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { execFileSync, spawn, type ChildProcess } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { createServer } from 'node:net';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterAll, afterEach, beforeAll, expect, it, vi } from 'vitest';
import { fixturePython, fixtureReady, stopFixture } from '../testBackend';
import type { Attempt } from '../modules/attempts/types';
import { App } from './App';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../../../..');
// Pin each run to its actual committed source, rather than making the original
// evidence snapshot an obstacle to rechecking later prerequisite repairs.
const baseline = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim();
const lane = 'C:/Renulus/scratch/design-c/dc-review-data';
const token = 'synthetic-mounted-assessment';
const realFetch = globalThis.fetch;
type Exchange = { path: string; method: string; body: string; key: string | null; status: number; result: unknown };
const exchanges: Exchange[] = [], outcomes: Record<string, unknown>[] = [];
let backend: ChildProcess | undefined, origin = '', fixture = '';
let sourceHashes: Record<string, string> = {};
configure({ asyncUtilTimeout: 12000 });

// No fixture routes, invented DDL, publisher replacement, or startup CPU helpers.
const bootstrap = String.raw`
import json, pathlib, socket, sys
sys.path.insert(0, sys.argv[1])
connect, connect_ex = socket.socket.connect, socket.socket.connect_ex
def local_only(instance, address):
    if isinstance(address, tuple) and address[0] in ('127.0.0.1', '::1'): return connect(instance, address)
    raise AssertionError('Mounted fixture forbids external sockets')
def local_only_ex(instance, address):
    if isinstance(address, tuple) and address[0] in ('127.0.0.1', '::1'): return connect_ex(instance, address)
    raise AssertionError('Mounted fixture forbids external sockets')
socket.socket.connect, socket.socket.connect_ex = local_only, local_only_ex
from renulus.server import create_app
from renulus.runtime.manager import ProviderManager
app = create_app(sys.argv[2], token='synthetic-mounted-assessment')
services = app.state.services
assert all(name in services.registry for name in ('saved_tests', 'saved_generation', 'chat_tests', 'conversations', 'whole_attempts'))
provider = services.get('provider')
assert isinstance(provider, ProviderManager)
calls = []
class InstalledSyntheticTransport:
    async def stream(self, route, model, access_token, messages):
        assert route == 'codex' and model == 'gpt-6.1-sol' and access_token == 'synthetic-mounted-provider'
        try: payload = json.loads(messages[-1]['content'])
        except (TypeError, ValueError): payload = {}
        if 'artifact_sha256' in payload:
            kind = 'fictional-review'
            output = {'schema': 'fictional-test-review/1', 'artifact_sha256': payload['artifact_sha256'],
                'source_identity_removed': True, 'clinical_details_generalised': True, 'no_source_links': True, 'issues': []}
        elif 'prior_fictional_stems' in payload or 'previous_stems' in payload:
            fictional = 'prior_fictional_stems' in payload
            kind = 'fictional-batch' if fictional else 'generation-batch'
            start = len(payload.get('prior_fictional_stems', payload.get('previous_stems', [])))
            domains = ['transplant immunology', 'electrolyte physiology', 'glomerular inflammation', 'dialysis clearance', 'chronic kidney adaptation']
            output = {'items': [{'stem': ('Independent fictional ' if fictional else 'Original generated ')
                + domains[index % 5] + ' question ' + str(index),
                'options': [{'id': 'a', 'text': 'First interpretation'}, {'id': 'b', 'text': 'Second interpretation'}],
                'correct_option_id': 'a', 'explanation': 'Synthetic educational rationale for ' + domains[index % 5],
                'hint': None, 'source_indices': []} for index in range(start, start + 5)]}
        else:
            kind = 'saved-chat-answer'
            output = 'Synthetic saved discussion of transplant immunology and electrolyte physiology.'
        calls.append({'kind': kind, 'provider': route, 'model': model})
        pathlib.Path(sys.argv[4]).write_text(json.dumps(calls), encoding='utf-8')
        yield {'type': 'delta', 'text': json.dumps(output) if isinstance(output, dict) else output}
        yield {'type': 'completed', 'response_model': model}
provider._settings['connections']['codex'] = {'access_token': 'synthetic-mounted-provider', 'expires_at': 9999999999}
provider._settings['selected_provider'] = 'codex'
provider._settings.setdefault('selected_models', {})['codex'] = 'gpt-6.1-sol'
provider._transport = InstalledSyntheticTransport()
services.on_startup = [services.get('saved_tests').backfill_legacy, services.get('saved_generation').recover]
services.on_shutdown = [services.get('chat_tests').close, services.get('saved_generation').close, provider.close]
import uvicorn
uvicorn.run(app, host='127.0.0.1', port=int(sys.argv[3]), log_level='warning', access_log=False)
`;

async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await realFetch(origin + '/api/v1' + path, { method,
    headers: { 'x-renulus-token': token, 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });
  if (!response.ok) throw new Error(path + ': ' + response.status + ' ' + await response.text());
  return response.json();
}
beforeAll(async () => {
  const git = (...args: string[]) => execFileSync('git', args, { cwd: root, encoding: 'utf8', windowsHide: true }).trim();
  expect(git('rev-parse', '--show-toplevel').replaceAll('\\', '/').toLowerCase()).toBe(root.replaceAll('\\', '/').toLowerCase());
  expect(git('diff', '--name-only', baseline, '--', 'runtime/renulus', 'apps/desktop/src').split('\n')
    .filter(path => path && path !== 'apps/desktop/src/shell/assessment-producers.connected.test.tsx'), 'Frozen product source parity').toEqual([]);
  sourceHashes = Object.fromEntries(git('ls-tree', '-r', '--name-only', baseline, '--', 'runtime/renulus', 'apps/desktop/src').split('\n')
    .filter(path => path && !/\.test\./.test(path)).map(path => [path, createHash('sha256').update(readFileSync(join(root, path))).digest('hex')]));
  mkdirSync(lane, { recursive: true }); fixture = mkdtempSync(join(lane, 'ap-'));
  for (const path of ['u', 'home', 'roaming', 'local', 'tmp', 'cache']) mkdirSync(join(fixture, path));
  const listener = createServer(); await new Promise<void>(resolve => listener.listen(0, '127.0.0.1', resolve));
  const address = listener.address(); if (!address || typeof address === 'string') throw new Error('Owned loopback port unavailable');
  await new Promise<void>((resolve, reject) => listener.close(error => error ? reject(error) : resolve()));
  origin = 'http://127.0.0.1:' + address.port;
  if (!process.env.RENULUS_TEST_PYTHON) throw new Error('Pin the reviewed synthetic test interpreter explicitly');
  const python = fixturePython(root), systemRoot = process.env.SystemRoot || 'C:/Windows';
  let stderr = '';
  backend = spawn(python, ['-c', bootstrap, join(root, 'runtime'), join(fixture, 'u'), String(address.port), join(fixture, 'transport.json')], {
    cwd: fixture, windowsHide: true, stdio: ['ignore', 'ignore', 'pipe'], env: {
      SystemRoot: systemRoot, WINDIR: systemRoot, COMSPEC: join(systemRoot, 'System32/cmd.exe'), PATH: dirname(python) + ';' + join(systemRoot, 'System32'),
      USERPROFILE: join(fixture, 'home'), HOME: join(fixture, 'home'), APPDATA: join(fixture, 'roaming'), LOCALAPPDATA: join(fixture, 'local'),
      TEMP: join(fixture, 'tmp'), TMP: join(fixture, 'tmp'), XDG_CACHE_HOME: join(fixture, 'cache'), HF_HOME: join(fixture, 'cache'),
      HUGGINGFACE_HUB_CACHE: join(fixture, 'cache'), TORCH_HOME: join(fixture, 'cache'), HF_HUB_OFFLINE: '1', TRANSFORMERS_OFFLINE: '1',
      HF_HUB_DISABLE_TELEMETRY: '1', PYTHONDONTWRITEBYTECODE: '1', PYTHONNOUSERSITE: '1', PYTHONUTF8: '1',
    },
  });
  backend.stderr?.on('data', chunk => { stderr = (stderr + String(chunk)).slice(-6000); });
  if (!await fixtureReady(backend, origin, realFetch)) throw new Error(stderr || 'Actual API fixture not ready');
  vi.stubGlobal('fetch', async (path: string, options: RequestInit = {}) => {
    if (typeof path !== 'string' || !path.startsWith('/api/v1/')) throw new Error('Unexpected renderer transport target');
    const headers = new Headers(options.headers); headers.set('x-renulus-token', token);
    // Node fetch cannot consume a jsdom AbortSignal; only the transport changes.
    const response = await realFetch(origin + path, { ...options, headers, signal: undefined });
    const result = response.headers.get('content-type')?.includes('application/json') ? await response.clone().json() : null;
    exchanges.push({ path, method: options.method ?? 'GET', body: String(options.body ?? ''), key: headers.get('Idempotency-Key'), status: response.status, result });
    return response;
  });
}, 75000);
afterEach(() => { cleanup(); localStorage.clear(); window.history.replaceState(null, '', '#/newchat'); });
afterAll(async () => {
  cleanup(); vi.unstubAllGlobals(); configure({ asyncUtilTimeout: 1000 });
  let cleanupError: string | undefined;
  try { await stopFixture(backend); }
  catch (error) { cleanupError = error instanceof Error ? error.message : 'Fixture cleanup failed'; throw error; }
  finally {
    if (fixture) writeFileSync(join(fixture, 'receipt.json'), JSON.stringify({ baseline,
      qualification: 'Source-mounted jsdom + real loopback backend; not installed/native acceptance',
      cleanup: { error: cleanupError ?? null, exitCode: backend?.exitCode, signalCode: backend?.signalCode },
      sourceHashes, outcomes, exchanges }, null, 2));
  }
}, 20000);

const starts = () => exchanges.filter(entry => entry.path === '/api/v1/assessment/test-attempts' && entry.method === 'POST');
async function finishWholeStudy(versionId: string, start: Exchange) {
  expect(start.status).toBe(201);
  const first = start.result as Attempt;
  expect(first.version_id).toBe(versionId); expect(first.mode).toBe('study'); expect(first.timing.kind).toBe('untimed'); expect(first.item_count).toBe(5);
  for (let position = 0; position < 5; position++) {
    await screen.findByText('Question ' + (position + 1) + ' of 5');
    fireEvent.click(await screen.findByRole('checkbox', { name: 'First interpretation' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Submit answer' }).matches(':disabled')).toBe(false));
    fireEvent.click(screen.getByRole('button', { name: 'Submit answer' }));
    await waitFor(() => expect(screen.getByRole('checkbox', { name: 'First interpretation' }).matches(':disabled')).toBe(true));
    if (position < 4) {
      await waitFor(() => expect(screen.getByRole('button', { name: 'Next' }).matches(':disabled')).toBe(false));
      fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    }
  }
  // A disabled option can also mean an action is still pending; await the real
  // final acknowledgement before opening the finish confirmation.
  await waitFor(() => expect(screen.getByRole('button', { name: 'Finish study' }).matches(':disabled')).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: 'Finish study' }));
  await screen.findByRole('heading', { name: 'Finish this Study attempt?' });
  fireEvent.click(screen.getAllByRole('button', { name: 'Finish study' }).at(-1)!);
  await screen.findByRole('heading', { name: 'Study summary' });
  const saved = await request<Attempt>('/assessment/test-attempts/' + first.id);
  expect(saved.version_id).toBe(versionId); expect(saved.status).toBe('ended'); expect(saved.committed).toHaveLength(5);
  expect(saved.committed.every(answer => Boolean(answer.evidence_id))).toBe(true);
  expect(saved.result?.denominator).toBe(5); expect(saved.result?.correct).toBe(5);
  outcomes.push({ versionId, attemptId: saved.id, committed: saved.committed.length, denominator: saved.result?.denominator });
}

it('mounts Tests Generation → Ready pinned setup → whole Study with real publication and persisted scores', async () => {
  window.history.replaceState(null, '', '#/tests'); render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: 'Create test' }));
  const panel = await screen.findByRole('region', { name: 'Create a test' });
  fireEvent.change(within(panel).getByRole('textbox', { name: 'Test title' }), { target: { value: 'Mounted synthetic nephrology generation' } });
  const topicSelect = within(panel).getByRole('combobox', { name: 'Learning topic' });
  await waitFor(() => expect(topicSelect.matches(':disabled')).toBe(false));
  const topicId = (topicSelect as HTMLSelectElement).options[1]?.value; expect(topicId).toBeTruthy();
  fireEvent.change(topicSelect, { target: { value: topicId } });
  fireEvent.click(within(panel).getByRole('button', { name: 'Generate 5 questions' }));
  const open = await within(panel).findByRole('button', { name: 'Open saved test' });
  await waitFor(() => expect(open.matches(':disabled')).toBe(false));
  const jobs = await request<{ items: { state: string; title: string; result?: { version_id: string; test_id: string }; route: { provider: string; model: string } }[] }>('/assessment/generation/jobs');
  const job = jobs.items.find(item => item.title === 'Mounted synthetic nephrology generation')!;
  expect(job.state).toBe('published'); expect(job.route).toEqual({ provider: 'codex', model: 'gpt-6.1-sol' });
  const versionId = job.result!.version_id;
  const setup = await screen.findByRole('complementary', { name: 'Selected test setup' });
  expect(within(setup).getByText('Ready')).toBeTruthy(); expect(within(setup).getByRole('heading', { name: job.title })).toBeTruthy();
  fireEvent.click(open);
  await waitFor(() => expect(screen.queryByRole('region', { name: 'Create a test' })).toBeNull());
  fireEvent.click(within(screen.getByRole('complementary', { name: 'Selected test setup' })).getByRole('button', { name: 'Continue to Study' }));
  expect(window.location.hash).toBe('#/attempts');
  const before = starts().length;
  fireEvent.click(await screen.findByRole('button', { name: 'Start Study' }));
  await waitFor(() => expect(starts()).toHaveLength(before + 1));
  const start = starts().at(-1)!;
  expect(JSON.parse(start.body).version).toEqual({ type: 'saved_test_version', id: versionId });
  await finishWholeStudy(versionId, start);
  const calls = JSON.parse(readFileSync(join(fixture, 'transport.json'), 'utf8')) as { kind: string }[];
  expect(calls.filter(call => call.kind === 'generation-batch')).toHaveLength(1);
}, 60000);

it('mounts saved Chat → fictional pinned card → Workspace and collection exact version → returned-ID Study', async () => {
  const chat = await request<{ identity: { type: string; id: string }; retention: string }>('/conversations', 'POST', { kind: 'learning' });
  expect(chat.identity.type).toBe('learn_thread'); expect(chat.retention).toBe('saved');
  window.history.replaceState(null, '', '#/chat/learn_thread/' + chat.identity.id); render(<App />);
  fireEvent.change(await screen.findByRole('textbox', { name: 'Message Renulus' }), { target: { value: 'Synthetic conceptual learning: transplant immunology and electrolyte physiology.' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send' }));
  await screen.findByText('Synthetic saved discussion of transplant immunology and electrolyte physiology.');
  const builder = screen.getByRole('region', { name: 'Create test from conversation' });
  await waitFor(() => expect(within(builder).getByRole('button', { name: 'Create test from conversation' }).matches(':disabled')).toBe(false));
  fireEvent.click(within(builder).getByRole('button', { name: 'Create test from conversation' }));
  fireEvent.click(within(builder).getByRole('button', { name: 'Create fictional test' }));
  await within(builder).findByRole('heading', { name: '5 fictional questions' });
  expect(within(builder).getByText('Saved personal practice')).toBeTruthy();
  const exchange = exchanges.filter(entry => /\/conversations\/test-drafts\/runs\/[^/]+\/result$/.test(entry.path) && entry.status === 200).at(-1)!;
  const result = exchange.result as { version_id: string; test_id: string; study_start: { idempotency_key: string } }; expect(result.version_id).toBeTruthy();
  fireEvent.click(within(builder).getByRole('button', { name: 'Open saved test' }));
  const tabs = await screen.findByRole('tablist', { name: 'Workspace tabs' });
  const workspace = tabs.closest('aside')!;
  const preview = await within(workspace).findByRole('complementary', { name: 'Selected test setup' });
  expect(within(preview).getByText('Ready')).toBeTruthy();
  expect(within(workspace).getByRole('tabpanel').id).toBe('dc-tabpanel-' + encodeURIComponent('saved_test_version:' + result.version_id));
  expect(exchanges.some(entry => entry.path === '/api/v1/assessment/tests/versions/' + result.version_id + '/setup' && entry.status === 200)).toBe(true);
  const collection = await request<{ items: { id: string; latest_version: { id: string } }[] }>('/assessment/tests');
  expect(collection.items.find(item => item.id === result.test_id)?.latest_version.id).toBe(result.version_id);
  fireEvent.click(within(workspace).getByRole('button', { name: 'Back to chat' }));
  const before = starts().length;
  fireEvent.click(within(builder).getByRole('button', { name: 'Start Study' }));
  await waitFor(() => expect(starts()).toHaveLength(before + 1));
  const start = starts().at(-1)!; expect(start.key).toBe(result.study_start.idempotency_key);
  const returned = start.result as Attempt;
  await waitFor(() => expect(window.location.hash).toBe('#/attempts/' + returned.id));
  expect(screen.queryByRole('button', { name: 'Start Study' })).toBeNull();
  await finishWholeStudy(result.version_id, start);
  expect(starts()).toHaveLength(before + 1);
  const calls = JSON.parse(readFileSync(join(fixture, 'transport.json'), 'utf8')) as { kind: string }[];
  for (const kind of ['saved-chat-answer', 'fictional-batch', 'fictional-review']) expect(calls.filter(call => call.kind === kind)).toHaveLength(1);
}, 60000);
