import { EventEmitter } from 'node:events';
import { mkdir, mkdtemp, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { startBackend } from './backend';
import { resolveProfile } from './profile';
import { resolveHarnessSettingsFixture } from './harness-settings-fixture';

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
  listener.listen.mockImplementation((_port, _host, done) => { done(); return listener; });
  listener.close.mockImplementation(done => { done(); return listener; });
  io.createServer.mockReturnValue(listener);
  vi.stubEnv('RENULUS_PYTHON', 'C:/Renulus/dev/python/Scripts/python.exe');
  vi.stubEnv('RENULUS_BACKEND_URL', undefined);
  vi.stubEnv('RENULUS_BACKGROUND_TEST', '1');
  vi.stubEnv('RENULUS_BACKGROUND_OWNER_PID', String(process.pid + 1));
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ api_version: 1, state: 'settled' }))));
});
afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

async function fixture() {
  await mkdir('G:/r4-electron', { recursive: true });
  const root = await mkdtemp('G:/r4-electron/t-'), directory = path.join(root, 's-1234abcd');
  await mkdir(path.join(directory, 'out'), { recursive: true });
  await mkdir(path.join(directory, 'p'));
  const helperAssets = path.join(root, 'assets'); await mkdir(helperAssets);
  const profile = resolveProfile(path.join(directory, 'p'), false);
  const document = { version: 1, process: { node_executable: process.execPath,
    host_entry: path.join(workspace, 'packages/harness/src/main.mjs'), profile_root: profile.root,
    profile_id: 'synthetic-settings-s-1234abcd', store_id: 'synthetic-settings-s-1234abcd-runtime',
    domain_store_id: 'synthetic-settings-s-1234abcd-domain', domain_path: 'state/renulus.sqlite3',
    max_inflight: 1, max_domain_inflight: 1, max_frame_bytes: 65536, start_timeout: 45 },
    artifact_root: path.join(directory, 'a'), candidate_root: path.join(directory, 'k'),
    attempt_timeout: 45, initialize_new: true };
  const raw = JSON.stringify(document), startupDocument = path.join(directory, 'out/startup-1.json');
  await writeFile(startupDocument, raw);
  return { profile, directory, option: { kind: 'harness-settings-synthetic-v1' as const,
    startupDocument, startupSha256: createHash('sha256').update(raw).digest('hex'), helperAssets } };
}

it('the typed opt-in selects only the fixed fixture and retains authenticated normal stop', async () => {
  const { profile, option } = await fixture();
  const backend = await startBackend({ profile, workspace, resources: '', packaged: false,
    token: 'synthetic-app-session', signal: new AbortController().signal, settingsFixture: option } as Parameters<typeof startBackend>[0]);
  try {
    const args = io.spawn.mock.calls[0][1];
    expect(args[0]).toBe(path.join(workspace, 'tools/renulus-control/harness-settings-backend.py'));
    expect(args).toContain('--harness-startup-sha256');
    expect(args).toContain(option.startupSha256);
  } finally { await backend.stop(); }
  expect(fetch).toHaveBeenLastCalledWith('http://127.0.0.1:18777/api/v1/runtime/shutdown',
    expect.objectContaining({ method: 'POST', body: JSON.stringify({ timeout_seconds: 5 }) }));
});

it('the resolver derives sibling desktop state and preserves ordinary launch when absent', async () => {
  const { profile, option, directory } = await fixture();
  vi.stubEnv('RENULUS_BACKGROUND_HARNESS_SETTINGS', undefined);
  expect(resolveHarnessSettingsFixture(profile, false, workspace)).toEqual({ profile });
  vi.stubEnv('RENULUS_BACKGROUND_HARNESS_SETTINGS', JSON.stringify(option));
  const plan = resolveHarnessSettingsFixture(profile, false, workspace);
  expect(plan.profile.root).toBe(profile.root);
  expect(plan.profile.desktop).toBe(path.join(directory, 'd'));
  expect(plan.profile.session).toBe(path.join(directory, 'd/session'));
});

it('fixture assets cannot be read from the writable session namespace', async () => {
  const { profile, option } = await fixture();
  vi.stubEnv('RENULUS_BACKGROUND_HARNESS_SETTINGS', JSON.stringify({ ...option, helperAssets: profile.root }));
  expect(() => resolveHarnessSettingsFixture(profile, false, workspace)).toThrow('fixture launch is invalid');
  expect(io.spawn).not.toHaveBeenCalled();
});

it.each(['foreground', 'packaged', 'digest', 'unknown-entry'])('rejects %s opt-in before child acquisition', async change => {
  const { profile, option } = await fixture();
  if (change === 'foreground') vi.stubEnv('RENULUS_BACKGROUND_TEST', undefined);
  const selected = change === 'digest' ? { ...option, startupSha256: '0'.repeat(64) }
    : change === 'unknown-entry' ? { ...option, entry: 'arbitrary.py' } : option;
  await expect(startBackend({ profile, workspace, resources: '', packaged: change === 'packaged',
    token: 'synthetic-app-session', signal: new AbortController().signal, settingsFixture: selected }))
    .rejects.toThrow('fixture launch is invalid');
  expect(io.spawn).not.toHaveBeenCalled();
});
