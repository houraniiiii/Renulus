import { EventEmitter } from 'node:events';
import path from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { startBackend } from './backend';
import { resolveProfile } from './profile';

const io = vi.hoisted(() => ({ spawn: vi.fn(), execFileSync: vi.fn(), existsSync: vi.fn(), readFileSync: vi.fn(), createServer: vi.fn() }));
vi.mock('node:child_process', () => ({ spawn: io.spawn, execFileSync: io.execFileSync }));
vi.mock('node:fs', () => ({ existsSync: io.existsSync, readFileSync: io.readFileSync }));
vi.mock('node:net', () => ({ createServer: io.createServer }));

let child: EventEmitter & { pid: number; exitCode: number | null; signalCode: NodeJS.Signals | null; killed: boolean; kill: ReturnType<typeof vi.fn> };
const workspace = path.resolve('.local/synthetic-startup');
const profile = resolveProfile(path.join(workspace, 'profile'), false);

beforeEach(() => {
  vi.useFakeTimers(); vi.setSystemTime(0);
  vi.stubEnv('RENULUS_BACKEND_URL', undefined);
  vi.stubEnv('RENULUS_PYTHON', undefined);
  child = Object.assign(new EventEmitter(), { pid: 424242, exitCode: null, signalCode: null, killed: false, kill: vi.fn() });
  io.spawn.mockReturnValue(child);
  io.existsSync.mockReturnValue(true);
  io.readFileSync.mockReturnValue(JSON.stringify({ version: 1, format: 'embedded-cpython-windows-v1', python: { executable: 'python/python.exe' }, bootstrap: 'bootstrap.py' }));
  io.execFileSync.mockImplementation(() => { child.killed = true; child.exitCode = 0; child.emit('exit'); return Buffer.alloc(0); });
  const listener = { once: vi.fn(), listen: vi.fn(), address: () => ({ port: 18777 }), close: vi.fn() };
  listener.once.mockReturnValue(listener);
  listener.listen.mockImplementation((_port, _host, ready) => { ready(); return listener; });
  listener.close.mockImplementation(done => { done(); return listener; });
  io.createServer.mockReturnValue(listener);
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

function options(packaged: boolean, controller = new AbortController()) {
  return { profile, token: 'synthetic-app-session', workspace, resources: path.join(workspace, 'resources'), packaged, signal: controller.signal, onOwnedChild: vi.fn() };
}

describe('owned backend cold startup', () => {
  it.each([false, true])('allows cold helper startup after 30 seconds (packaged=%s)', async packaged => {
    vi.stubGlobal('fetch', vi.fn(async () => {
      if (Date.now() < 45_000) throw new Error('Synthetic helpers still warming');
      return new Response(JSON.stringify({ api_version: 1 }), { status: 200 });
    }));
    const setup = options(packaged);
    const pending = startBackend(setup).then(value => ({ value }), error => ({ error }));
    await vi.advanceTimersByTimeAsync(46_000);
    const outcome = await pending;
    expect(outcome).not.toHaveProperty('error');
    if (!('value' in outcome)) throw outcome.error;
    expect(outcome.value).toMatchObject({ owned: true, port: 18777, child });
    expect(setup.onOwnedChild).toHaveBeenCalledOnce();
    expect(io.execFileSync).not.toHaveBeenCalled();
    await outcome.value.stop();
    expect(child.exitCode).toBe(0);
  });

  it('stops a development child at the finite five-minute readiness limit', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('Synthetic backend never listens'); }));
    const pending = startBackend(options(false)).then(value => ({ value }), error => ({ error }));
    await vi.advanceTimersByTimeAsync(299_000);
    expect(io.execFileSync).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(2000);
    const outcome = await pending;
    expect(outcome).toHaveProperty('error.message', 'The local backend did not become ready in time.');
    expect(io.execFileSync).toHaveBeenCalledExactlyOnceWith('taskkill', ['/PID', '424242', '/T', '/F'], expect.any(Object));
    expect(child.exitCode).toBe(0);
  });

  it('cancels ownership during an in-flight late readiness request', async () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(() => {})));
    const controller = new AbortController();
    const setup = options(false, controller);
    const pending = startBackend(setup).then(value => ({ value }), error => ({ error }));
    await vi.advanceTimersByTimeAsync(35_000);
    expect(setup.onOwnedChild).toHaveBeenCalledOnce();
    expect(io.execFileSync).not.toHaveBeenCalled();
    const reason = new Error('Synthetic startup cancelled');
    controller.abort(reason);
    const outcome = await pending;
    expect(outcome).toHaveProperty('error', reason);
    expect(io.execFileSync).toHaveBeenCalledOnce();
    expect(child.exitCode).toBe(0);
  });
});
