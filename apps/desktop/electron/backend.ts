import { spawn, execFileSync, type ChildProcess } from 'node:child_process';
import { existsSync } from 'node:fs';
import { createServer } from 'node:net';
import path from 'node:path';
import { backendEnvironment, type DesktopProfile } from './profile';
import { stopBackendChild, waitForBackendExit } from './upstream/backend-child';
import { runBackendStartStep } from './upstream/backend-start-cancellation';

export interface ManagedBackend { port: number; child: ChildProcess | null; owned: boolean; stop(): Promise<void> }
export async function freeLoopbackPort(): Promise<number> {
  const server = createServer();
  await new Promise<void>((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
  const port = (server.address() as { port: number }).port;
  await new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
  return port;
}

export async function startBackend(options: { profile: DesktopProfile; token: string; workspace: string; resources: string; packaged: boolean; signal: AbortSignal; onOwnedChild?: (backend: ManagedBackend) => void }): Promise<ManagedBackend> {
  const { profile, token, workspace, resources, packaged, signal } = options;
  signal.throwIfAborted();
  if (!packaged && process.env.RENULUS_BACKEND_URL) {
    const url = new URL(process.env.RENULUS_BACKEND_URL);
    if (url.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(url.hostname) || url.username || url.password || url.search || url.hash || url.pathname !== '/' || !process.env.RENULUS_SESSION_TOKEN) throw new Error('Development backend attachment requires a loopback origin and explicit app session token.');
    const port = Number(url.port || 80);
    const response = await fetch('http://127.0.0.1:' + port + '/api/v1/meta', { headers: { 'x-renulus-token': token }, signal, cache: 'no-store', redirect: 'error' });
    const meta = await response.json() as { api_version: number };
    if (!response.ok || meta.api_version !== 1) throw new Error('The configured development backend did not authenticate.');
    return { port, child: null, owned: false, stop: async () => {} };
  }
  const python = process.env.RENULUS_PYTHON ?? path.join(workspace, '.venv', 'Scripts', 'python.exe');
  const command = packaged ? path.join(resources, 'backend', 'renulus-backend.exe') : python;
  if (!path.isAbsolute(command) || !existsSync(command)) throw new Error('The Renulus Python runtime is not available. Set RENULUS_PYTHON for development.');
  const port = await runBackendStartStep(signal, freeLoopbackPort);
  const args = [...(packaged ? [] : ['-m', 'renulus.server']), '--profile', profile.root, '--port', String(port)];
  const deps = { forceKillProcessTree: (pid: number) => { execFileSync('taskkill', ['/PID', String(pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' }); } };
  signal.throwIfAborted();
  const child = spawn(command, args, { cwd: packaged ? resources : workspace, env: backendEnvironment(profile, token, path.join(workspace, 'runtime'), path.join(workspace, 'upstream', 'hermes')), windowsHide: true, detached: process.platform !== 'win32', stdio: ['ignore', 'ignore', 'ignore'] });
  let stopped: Promise<void> | undefined;
  let failed = false;
  child.once('error', () => { failed = true; });
  const stop = () => {
    if (!stopped) stopped = (async () => { if (child.pid && child.exitCode === null && child.signalCode === null) { stopBackendChild(child, deps); await waitForBackendExit(child, deps); } })();
    return stopped;
  };
  const handle: ManagedBackend = { port, child, owned: true, stop };
  // Publish physical ownership before the first asynchronous readiness wait.
  options.onOwnedChild?.(handle);
  const onAbort = () => { void stop().catch(() => {}); };
  signal.addEventListener('abort', onAbort, { once: true });
  try {
    const deadline = Date.now() + 30_000;
    while (Date.now() < deadline) {
      signal.throwIfAborted();
      if (failed || child.exitCode !== null || child.signalCode !== null) throw new Error('The local backend exited during startup.');
      try {
        // Authenticated meta proves this is our child session, not an unrelated listener.
        const response = await runBackendStartStep(signal, () => fetch('http://127.0.0.1:' + port + '/api/v1/meta', { headers: { 'x-renulus-token': token }, signal: AbortSignal.any([signal, AbortSignal.timeout(1000)]), redirect: 'error', cache: 'no-store' }));
        const meta = await response.json() as { api_version: number };
        if (response.ok && meta.api_version === 1) return handle;
      } catch { signal.throwIfAborted(); }
      await runBackendStartStep(signal, () => new Promise(resolve => setTimeout(resolve, 150)));
    }
    throw new Error('The local backend did not become ready in time.');
  } catch (error) { await stop(); throw error; }
  finally { signal.removeEventListener('abort', onAbort); }
}
