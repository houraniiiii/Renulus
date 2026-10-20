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

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return { promise, resolve };
}

describe('owned backend cold startup', () => {
  it.each([
    { label: 'unauthenticated', status: 401, api_version: 1 },
    { label: 'incompatible', status: 200, api_version: 2 },
  ])('keeps a $label meta response in startup-abort mode', async ({ status, api_version }) => {
    const transport = vi.fn<typeof fetch>().mockImplementation(async () => new Response(JSON.stringify({ api_version }), { status }));
    vi.stubGlobal('fetch', transport);
    const lifetime = new AbortController();
    const starting = startBackend(options(false, lifetime)).then(value => ({ value }), error => ({ error }));
    await vi.advanceTimersByTimeAsync(0);
    const reason = new Error('Synthetic startup cancelled without authenticated readiness');
    lifetime.abort(reason);

    expect(await starting).toHaveProperty('error', reason);
    expect(transport).toHaveBeenCalledExactlyOnceWith('http://127.0.0.1:18777/api/v1/meta', expect.objectContaining({
      headers: { 'x-renulus-token': 'synthetic-app-session' },
    }));
    expect(io.execFileSync).toHaveBeenCalledOnce();
    expect(child.exitCode).toBe(0);
  });

  it('aborts an unready child without a handshake and still waits for its physical exit', async () => {
    const transport = vi.fn<typeof fetch>().mockReturnValue(new Promise<Response>(() => {}));
    vi.stubGlobal('fetch', transport);
    vi.spyOn(process, 'kill').mockReturnValue(true);
    io.execFileSync.mockImplementation(() => { child.killed = true; return Buffer.alloc(0); });
    const lifetime = new AbortController();
    const setup = options(false, lifetime);
    let outcome: unknown = 'pending';
    const starting = startBackend(setup).then(value => { outcome = value; }, error => { outcome = error; });
    await vi.advanceTimersByTimeAsync(0);
    expect(setup.onOwnedChild).toHaveBeenCalledOnce();

    const reason = new Error('Synthetic startup cancelled before ready');
    lifetime.abort(reason);
    await vi.advanceTimersByTimeAsync(1000);
    expect(outcome).toBe('pending');
    expect(child.killed).toBe(true);
    expect(child.exitCode).toBeNull();
    expect(io.execFileSync).toHaveBeenCalledOnce();
    expect(transport).toHaveBeenCalledExactlyOnceWith('http://127.0.0.1:18777/api/v1/meta', expect.objectContaining({
      headers: { 'x-renulus-token': 'synthetic-app-session' }, redirect: 'error', cache: 'no-store',
    }));

    child.exitCode = 0;
    child.emit('exit');
    await starting;
    expect(outcome).toBe(reason);
    expect(io.execFileSync).toHaveBeenCalledOnce();
  });

  it('rejects readiness if startup is aborted while authentic meta is decoding', async () => {
    const metadata = deferred<{ api_version: number }>();
    const response = new Response();
    const decode = vi.spyOn(response, 'json').mockReturnValue(metadata.promise);
    const transport = vi.fn<typeof fetch>().mockResolvedValue(response);
    vi.stubGlobal('fetch', transport);
    const lifetime = new AbortController();
    const setup = options(false, lifetime);
    const pending = startBackend(setup).then(value => ({ value }), error => ({ error }));
    await vi.advanceTimersByTimeAsync(0);
    expect(decode).toHaveBeenCalledOnce();

    const reason = new Error('Synthetic startup cancelled during meta');
    lifetime.abort(reason);
    metadata.resolve({ api_version: 1 });
    expect(await pending).toHaveProperty('error', reason);
    expect(transport).toHaveBeenCalledOnce();
    expect(setup.onOwnedChild).toHaveBeenCalledOnce();
    expect(io.execFileSync).toHaveBeenCalledOnce();
    expect(child.exitCode).toBe(0);
  });

  it.each([false, true])('allows cold helper startup after 30 seconds (packaged=%s)', async packaged => {
    vi.stubGlobal('fetch', vi.fn(async url => {
      if (String(url).endsWith('/api/v1/runtime/shutdown')) return new Response(JSON.stringify({ state: 'settled', api_version: 1 }));
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
    expect(io.spawn.mock.calls[0]?.[1]).toContain('--desktop-harness');
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

describe('owned backend shutdown', () => {
  it('includes response-body decoding in the eight-second shutdown deadline', async () => {
    const headers = deferred<Response>();
    const body = deferred<{ state: string; api_version: number }>();
    const response = new Response();
    const decode = vi.spyOn(response, 'json').mockReturnValue(body.promise);
    const transport = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({ api_version: 1 })))
      .mockReturnValueOnce(headers.promise)
      .mockResolvedValueOnce(new Response(JSON.stringify({ state: 'settled', api_version: 1 })));
    vi.stubGlobal('fetch', transport);
    const backend = await startBackend(options(false));
    let outcome: unknown = 'pending';
    const stopping = backend.stop().then(() => { outcome = 'released'; }, error => { outcome = error; });

    await vi.advanceTimersByTimeAsync(3000);
    headers.resolve(response);
    await vi.advanceTimersByTimeAsync(0);
    expect(decode).toHaveBeenCalledOnce();
    await vi.advanceTimersByTimeAsync(4999);
    expect(outcome).toBe('pending');
    await vi.advanceTimersByTimeAsync(1);
    await stopping;
    expect(outcome).toHaveProperty('message', expect.stringMatching(/timed out.*retaining ownership/i));
    expect(transport.mock.calls[1][1]?.signal?.aborted).toBe(true);

    body.resolve({ state: 'settled', api_version: 1 });
    await vi.advanceTimersByTimeAsync(0);
    expect(io.execFileSync).not.toHaveBeenCalled();
    expect(child.kill).not.toHaveBeenCalled();
    expect(backend.child).toBe(child);
    await backend.stop();
    expect(transport).toHaveBeenCalledTimes(3);
    expect(child.exitCode).toBe(0);
  });

  it('retains ownership on a network failure and re-queries on retry', async () => {
    const failure = new TypeError('Synthetic loopback connection failure');
    const transport = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({ api_version: 1 })))
      .mockRejectedValueOnce(failure)
      .mockResolvedValueOnce(new Response(JSON.stringify({ state: 'settled', api_version: 1 })));
    vi.stubGlobal('fetch', transport);
    const backend = await startBackend(options(false));

    await expect(backend.stop()).rejects.toBe(failure);
    expect(backend.child).toBe(child);
    expect(backend.owned).toBe(true);
    expect(io.execFileSync).not.toHaveBeenCalled();
    expect(child.kill).not.toHaveBeenCalled();
    await backend.stop();
    expect(transport).toHaveBeenCalledTimes(3);
    expect(io.spawn).toHaveBeenCalledOnce();
    expect(child.exitCode).toBe(0);
  });

  it.each([
    { label: 'open', body: '{"state":"open","api_version":1}', status: 200 },
    { label: 'draining', body: '{"state":"draining","api_version":1}', status: 200 },
    { label: 'failed', body: '{"state":"failed","api_version":1}', status: 200 },
    { label: 'missing state', body: '{"api_version":1}', status: 200 },
    { label: 'missing API version', body: '{"state":"settled"}', status: 200 },
    { label: 'wrong API version', body: '{"state":"settled","api_version":2}', status: 200 },
    { label: 'null', body: 'null', status: 200 },
    { label: 'array', body: '[]', status: 200 },
    { label: 'primitive', body: 'true', status: 200 },
    { label: 'invalid JSON', body: '{"state":', status: 200 },
    { label: 'empty response', body: '', status: 200 },
    { label: 'unauthorized', body: '{"state":"settled","api_version":1}', status: 401 },
    { label: 'server error', body: '{"state":"settled","api_version":1}', status: 500 },
    { label: 'redirect', body: '{"state":"settled","api_version":1}', status: 302 },
  ])('retains the child for a $label shutdown response', async ({ body, status }) => {
    const transport = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({ api_version: 1 })))
      .mockResolvedValueOnce(new Response(body, { status }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ state: 'settled', api_version: 1 })));
    vi.stubGlobal('fetch', transport);
    const backend = await startBackend(options(false));

    await expect(backend.stop()).rejects.toBeInstanceOf(Error);
    expect(backend.child).toBe(child);
    expect(backend.owned).toBe(true);
    expect(child.exitCode).toBeNull();
    expect(io.execFileSync).not.toHaveBeenCalled();
    expect(child.kill).not.toHaveBeenCalled();

    await backend.stop();
    expect(transport).toHaveBeenCalledTimes(3);
    expect(io.spawn).toHaveBeenCalledOnce();
    expect(child.exitCode).toBe(0);
  });

  it('retains ownership until physical exit, including the existing 15-second wait and escalation', async () => {
    const transport = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({ api_version: 1 })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ state: 'settled', api_version: 1 })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ state: 'settled', api_version: 1 })));
    vi.stubGlobal('fetch', transport);
    vi.spyOn(process, 'kill').mockReturnValue(true);
    io.execFileSync.mockImplementation(() => { child.killed = true; return Buffer.alloc(0); });
    const backend = await startBackend(options(false));

    let outcome: unknown = 'pending';
    const stopping = backend.stop();
    expect(backend.stop()).toBe(stopping);
    const observed = stopping.then(() => { outcome = 'released'; }, error => { outcome = error; });
    await vi.advanceTimersByTimeAsync(14999);
    expect(outcome).toBe('pending');
    expect(child.killed).toBe(true);
    expect(child.exitCode).toBeNull();
    expect(io.execFileSync).toHaveBeenCalledOnce();
    expect(transport).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(1);
    expect(io.execFileSync).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(999);
    expect(outcome).toBe('pending');
    await vi.advanceTimersByTimeAsync(1);
    await observed;
    expect(outcome).toHaveProperty('message', 'Backend child (PID 424242) did not exit after SIGKILL; retaining ownership.');
    expect(backend.child).toBe(child);
    expect(backend.owned).toBe(true);

    let released = false;
    const retry = backend.stop().then(() => { released = true; });
    await vi.advanceTimersByTimeAsync(0);
    expect(transport).toHaveBeenCalledTimes(3);
    expect(released).toBe(false);
    child.exitCode = 0;
    child.emit('exit');
    await retry;
    expect(released).toBe(true);
    expect(io.spawn).toHaveBeenCalledOnce();
  });

  it('bounds shutdown independently of an already aborted lifetime and can retry', async () => {
    const stalled = deferred<Response>();
    const transport = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({ api_version: 1 })))
      .mockReturnValueOnce(stalled.promise)
      .mockResolvedValueOnce(new Response(JSON.stringify({ state: 'settled', api_version: 1 })));
    vi.stubGlobal('fetch', transport);
    const lifetime = new AbortController();
    const backend = await startBackend(options(false, lifetime));
    lifetime.abort(new Error('Synthetic app quit'));

    let outcome: unknown = 'pending';
    const stopping = backend.stop().then(() => { outcome = 'released'; }, error => { outcome = error; });
    await vi.advanceTimersByTimeAsync(7999);
    expect(outcome).toBe('pending');
    expect(io.execFileSync).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    expect(outcome).toBeInstanceOf(Error);
    expect(outcome).toHaveProperty('message', expect.stringMatching(/timed out.*retaining ownership/i));
    await stopping;
    const shutdownSignal = transport.mock.calls[1][1]?.signal;
    expect(shutdownSignal).toBeInstanceOf(AbortSignal);
    expect(shutdownSignal).not.toBe(lifetime.signal);
    expect(shutdownSignal?.aborted).toBe(true);
    expect(backend.child).toBe(child);
    expect(child.exitCode).toBeNull();
    expect(io.execFileSync).not.toHaveBeenCalled();
    expect(child.kill).not.toHaveBeenCalled();

    stalled.resolve(new Response(JSON.stringify({ state: 'settled', api_version: 1 })));
    await vi.advanceTimersByTimeAsync(0);
    expect(io.execFileSync).not.toHaveBeenCalled();
    expect(child.kill).not.toHaveBeenCalled();
    await backend.stop();
    expect(transport).toHaveBeenCalledTimes(3);
    expect(transport.mock.calls[2][1]?.signal).not.toBe(shutdownSignal);
    expect(io.execFileSync).toHaveBeenCalledOnce();
    expect(child.exitCode).toBe(0);
  });

  it('rejects a malformed settlement acknowledgement without releasing ownership', async () => {
    const transport = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({ api_version: 1 })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ state: 'settled', api_version: '1' })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ state: 'settled', api_version: 1 })));
    vi.stubGlobal('fetch', transport);
    const backend = await startBackend(options(false));

    await expect(backend.stop()).rejects.toThrow(/retaining ownership/i);
    expect(backend.child).toBe(child);
    expect(backend.owned).toBe(true);
    expect(io.execFileSync).not.toHaveBeenCalled();
    expect(child.kill).not.toHaveBeenCalled();

    await backend.stop();
    expect(transport).toHaveBeenCalledTimes(3);
    expect(child.exitCode).toBe(0);
  });

  it('retains the same owned child after a pending shutdown and retries settlement', async () => {
    const transport = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({ api_version: 1 })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: 'runtime_shutdown_pending' } }), { status: 503 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ state: 'settled', api_version: 1 })));
    vi.stubGlobal('fetch', transport);
    const setup = options(false);
    const backend = await startBackend(setup);

    await expect(backend.stop()).rejects.toThrow(/retaining ownership/i);
    expect(backend).toMatchObject({ port: 18777, child, owned: true });
    expect(child.exitCode).toBeNull();
    expect(io.execFileSync).not.toHaveBeenCalled();
    expect(child.kill).not.toHaveBeenCalled();

    await backend.stop();
    expect(transport).toHaveBeenCalledTimes(3);
    expect(io.spawn).toHaveBeenCalledOnce();
    expect(setup.onOwnedChild).toHaveBeenCalledExactlyOnceWith(backend);
    expect(io.execFileSync).toHaveBeenCalledOnce();
    expect(child.exitCode).toBe(0);
  });

  it('waits for runtime settlement before killing a ready owned backend', async () => {
    const acknowledgement = deferred<Response>();
    const transport = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({ api_version: 1 })))
      .mockReturnValueOnce(acknowledgement.promise);
    vi.stubGlobal('fetch', transport);
    const lifetime = new AbortController();
    const setup = options(false, lifetime);
    const backend = await startBackend(setup);
    expect(setup.onOwnedChild).toHaveBeenCalledExactlyOnceWith(backend);

    const stopping = backend.stop();
    lifetime.abort(new Error('Synthetic app quit during shutdown'));
    await vi.advanceTimersByTimeAsync(0);
    expect(child.exitCode).toBeNull();
    expect(io.execFileSync).not.toHaveBeenCalled();
    expect(child.kill).not.toHaveBeenCalled();
    expect(transport).toHaveBeenLastCalledWith('http://127.0.0.1:18777/api/v1/runtime/shutdown', expect.objectContaining({
      method: 'POST', headers: { 'x-renulus-token': 'synthetic-app-session', 'content-type': 'application/json' },
      body: JSON.stringify({ timeout_seconds: 5 }), redirect: 'error', cache: 'no-store',
    }));
    expect(transport.mock.calls[1][1]?.signal?.aborted).toBe(false);

    acknowledgement.resolve(new Response(JSON.stringify({ state: 'settled', api_version: 1 })));
    await stopping;
    expect(io.execFileSync).toHaveBeenCalledExactlyOnceWith('taskkill', ['/PID', '424242', '/T', '/F'], expect.any(Object));
    expect(child.exitCode).toBe(0);
    await backend.stop();
    expect(transport).toHaveBeenCalledTimes(2);
    expect(io.execFileSync).toHaveBeenCalledOnce();
  });
});
