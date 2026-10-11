import { EventEmitter } from 'node:events';
import { mkdir, mkdtemp, writeFile, readFile, readdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { startBackend } from './backend';
import { resolveProfile } from './profile';
import { resolveHarnessLearningFixture } from './harness-learning-fixture';

const io = vi.hoisted(() => ({ spawn: vi.fn(), execFileSync: vi.fn(), createServer: vi.fn() }));
vi.mock('node:child_process', () => ({ spawn: io.spawn, execFileSync: io.execFileSync }));
vi.mock('node:net', () => ({ createServer: io.createServer }));
const workspace = path.resolve('../..');
let child: EventEmitter & { pid: number; exitCode: number | null; signalCode: null };
beforeEach(() => {
  child = Object.assign(new EventEmitter(), { pid: 424242, exitCode: null, signalCode: null });
  io.spawn.mockReturnValue(child);
  io.execFileSync.mockImplementation(() => { child.exitCode = 0; child.emit('exit'); });
  const listener = { once: vi.fn(), listen: vi.fn(), address: () => ({ port: 18777 }), close: vi.fn() };
  listener.once.mockReturnValue(listener);
  listener.listen.mockImplementation((_port, _host, ready) => { ready(); return listener; });
  listener.close.mockImplementation(done => { done(); return listener; });
  io.createServer.mockReturnValue(listener);
  vi.stubEnv('RENULUS_PYTHON', 'C:/Renulus/dev/python/Scripts/python.exe');
  vi.stubEnv('RENULUS_BACKEND_URL', undefined);
  vi.stubEnv('RENULUS_BACKGROUND_TEST', '1');
  vi.stubEnv('RENULUS_BACKGROUND_OWNER_PID', String(process.pid + 1));
  vi.stubEnv('RENULUS_BACKGROUND_HARNESS_SETTINGS', undefined);
  vi.stubEnv('RENULUS_BACKGROUND_HARNESS_LEARNING', undefined);
  // Only OS/HTTP protocol boundaries are synthetic; no runtime or model starts.
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ api_version: 1, state: 'settled' }))));
});
afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

async function fixture() {
  await mkdir('G:/rh02-electron', { recursive: true });
  const root = await mkdtemp('G:/rh02-electron/l-'), directory = path.join(root, 's-1234abcd');
  await mkdir(path.join(directory, 'out'), { recursive: true });
  await mkdir(path.join(directory, 'p'));
  const helperAssets = path.join(root, 'assets'); await mkdir(helperAssets);
  const profile = resolveProfile(path.join(directory, 'p'), false);
  const document = { version: 1, process: { node_executable: process.execPath,
    host_entry: path.join(workspace, 'packages/harness/src/main.mjs'), profile_root: profile.root,
    profile_id: 'synthetic-learning-s-1234abcd', store_id: 'synthetic-learning-s-1234abcd-runtime',
    domain_store_id: 'synthetic-learning-s-1234abcd-domain', domain_path: 'state/renulus.sqlite3',
    max_inflight: 1, max_domain_inflight: 1, max_frame_bytes: 65536, start_timeout: 45 },
    artifact_root: path.join(directory, 'a'), candidate_root: path.join(directory, 'k'),
    attempt_timeout: 45, initialize_new: true };
  const raw = JSON.stringify(document), startupDocument = path.join(directory, 'out/startup-1.json');
  await writeFile(startupDocument, raw);
  return { profile, directory, document, option: { kind: 'harness-learning-synthetic-v1' as const,
    startupDocument, startupSha256: createHash('sha256').update(raw).digest('hex'), helperAssets } };
}

it('the typed learning launch selects the fixed Python entry and retains authenticated normal stop', async () => {
  const { profile, option } = await fixture();
  const acquired: unknown[] = [];
  const backend = await startBackend({ profile, workspace, resources: '', packaged: false,
    token: 'synthetic-learning-session', signal: new AbortController().signal, learningFixture: option,
    onOwnedChild: owned => { acquired.push(owned); } } as Parameters<typeof startBackend>[0]);
  try {
    expect(io.spawn.mock.calls[0][1]).toEqual([path.join(workspace, 'tools/renulus-control/harness-learning-backend.py'),
      '--profile', profile.root, '--port', '18777', '--harness-startup', option.startupDocument,
      '--harness-startup-sha256', option.startupSha256, '--helper-assets', option.helperAssets]);
    expect(acquired).toEqual([backend]);
    expect(backend.owned).toBe(true);
    expect(await readdir(profile.root)).toEqual([]);
  } finally { await backend.stop(); }
  expect(fetch).toHaveBeenLastCalledWith('http://127.0.0.1:18777/api/v1/runtime/shutdown',
    expect.objectContaining({ method: 'POST', headers: { 'x-renulus-token': 'synthetic-learning-session',
      'content-type': 'application/json' }, body: JSON.stringify({ timeout_seconds: 5 }) }));
  expect(child.exitCode).toBe(0);
});

it('the learning resolver derives sibling desktop state without provisioning the live root', async () => {
  const { profile, option, directory } = await fixture();
  expect(resolveHarnessLearningFixture(profile, false, workspace)).toEqual({ profile });
  vi.stubEnv('RENULUS_BACKGROUND_HARNESS_LEARNING', JSON.stringify(option));
  const plan = resolveHarnessLearningFixture(profile, false, workspace);
  expect(plan.profile).toEqual({ ...profile, desktop: path.join(directory, 'd'), session: path.join(directory, 'd/session') });
  expect(plan.learningFixture).toEqual(option);
  expect(Object.isFrozen(plan.learningFixture)).toBe(true);
  expect(await readdir(profile.root)).toEqual([]);
  expect(await readdir(directory)).toEqual(expect.arrayContaining(['out', 'p']));
  expect(await readdir(directory)).not.toContain('d');
  expect(io.spawn).not.toHaveBeenCalled();
});

it('startup two permits only reopening and leaves startup one immutable', async () => {
  const { profile, option, document, directory } = await fixture();
  const initial = await readFile(option.startupDocument);
  const raw = JSON.stringify({ ...document, initialize_new: false });
  const selected = { ...option, startupDocument: path.join(directory, 'out/startup-2.json'),
    startupSha256: createHash('sha256').update(raw).digest('hex') };
  await writeFile(selected.startupDocument, raw);
  vi.stubEnv('RENULUS_BACKGROUND_HARNESS_LEARNING', JSON.stringify(selected));
  expect(resolveHarnessLearningFixture(profile, false, workspace).learningFixture).toEqual(selected);
  expect(await readFile(option.startupDocument)).toEqual(initial);
  expect(await readdir(profile.root)).toEqual([]);
});

it.each(['foreground', 'packaged', 'attached', 'python', 'owner', 'self-owner', 'unsafe-owner',
  'settings-env', 'settings-option', 'kind', 'digest', 'entry', 'assets-in-profile', 'relative-startup',
  'unknown-process', 'wrong-identity', 'frame', 'parallel', 'timeout', 'initialize', 'reinitialize',
  'noncanonical-env', 'oversized-env', 'oversized-document'])('rejects %s before child acquisition', async change => {
  const { profile, option, document, directory } = await fixture();
  let selected: unknown = option;
  if (change === 'foreground') vi.stubEnv('RENULUS_BACKGROUND_TEST', undefined);
  if (change === 'attached') vi.stubEnv('RENULUS_BACKEND_URL', 'http://127.0.0.1:18778');
  if (change === 'python') vi.stubEnv('RENULUS_PYTHON', undefined);
  if (change === 'owner') vi.stubEnv('RENULUS_BACKGROUND_OWNER_PID', undefined);
  if (change === 'self-owner') vi.stubEnv('RENULUS_BACKGROUND_OWNER_PID', String(process.pid));
  if (change === 'unsafe-owner') vi.stubEnv('RENULUS_BACKGROUND_OWNER_PID', '9007199254740993');
  if (change === 'settings-env') vi.stubEnv('RENULUS_BACKGROUND_HARNESS_SETTINGS', '{}');
  if (change === 'kind') selected = { ...option, kind: 'harness-settings-synthetic-v1' };
  if (change === 'digest') selected = { ...option, startupSha256: '0'.repeat(64) };
  if (change === 'entry') selected = { ...option, entry: 'arbitrary.py' };
  if (change === 'assets-in-profile') selected = { ...option, helperAssets: profile.root };
  if (change === 'relative-startup') selected = { ...option, startupDocument: 'startup-1.json' };
  if (['unknown-process', 'wrong-identity', 'frame', 'parallel', 'timeout', 'initialize', 'reinitialize', 'oversized-document'].includes(change)) {
    const processFields = change === 'unknown-process' ? { ...document.process, model: 'arbitrary-model' }
      : change === 'wrong-identity' ? { ...document.process, profile_id: 'synthetic-settings-s-1234abcd' }
      : change === 'frame' ? { ...document.process, max_frame_bytes: 65537 }
      : change === 'parallel' ? { ...document.process, max_inflight: 2 }
      : change === 'timeout' ? { ...document.process, start_timeout: 46 } : document.process;
    const raw = JSON.stringify({ ...document, process: processFields,
      ...(change === 'initialize' ? { initialize_new: false } : {}),
      ...(change === 'oversized-document' ? { body: 'synthetic'.repeat(40000) } : {}) });
    const startupDocument = change === 'reinitialize' ? path.join(directory, 'out/startup-2.json') : option.startupDocument;
    await writeFile(startupDocument, raw);
    selected = { ...option, startupDocument, startupSha256: createHash('sha256').update(raw).digest('hex') };
  }
  const env = change === 'noncanonical-env' ? ' ' + JSON.stringify(selected)
    : change === 'oversized-env' ? ' '.repeat(16385) : JSON.stringify(selected);
  vi.stubEnv('RENULUS_BACKGROUND_HARNESS_LEARNING', env);
  if (change === 'settings-option') {
    await expect(startBackend({ profile, workspace, resources: '', packaged: false, token: 'synthetic-learning-session',
      signal: new AbortController().signal, learningFixture: option,
      settingsFixture: { ...option, kind: 'harness-settings-synthetic-v1' } })).rejects.toThrow('mutually exclusive');
  } else {
    expect(() => resolveHarnessLearningFixture(profile, change === 'packaged', workspace)).toThrow('fixture launch is invalid');
    if (!['noncanonical-env', 'oversized-env'].includes(change)) {
      await expect(startBackend({ profile, workspace, resources: '', packaged: change === 'packaged',
        token: 'synthetic-learning-session', signal: new AbortController().signal,
        learningFixture: selected } as Parameters<typeof startBackend>[0])).rejects.toThrow('fixture launch is invalid');
    }
  }
  expect(io.spawn).not.toHaveBeenCalled();
  expect(fetch).not.toHaveBeenCalled();
  expect(await readdir(profile.root)).toEqual([]);
});
