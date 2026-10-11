import { spawn, execFileSync, type ChildProcess } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { createServer } from 'node:net';
import path from 'node:path';
import { backendEnvironment, type DesktopProfile } from './profile';
import { stopBackendChild, waitForBackendExit } from './upstream/backend-child';
import { runBackendStartStep } from './upstream/backend-start-cancellation';
import { validateHarnessSettingsFixture, type HarnessSettingsFixtureLaunch } from './harness-settings-fixture';

export interface ManagedBackend { port: number; child: ChildProcess | null; owned: boolean; stop(): Promise<void> }
export async function freeLoopbackPort(): Promise<number> {
  const server = createServer();
  await new Promise<void>((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
  const port = (server.address() as { port: number }).port;
  await new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
  return port;
}

export async function startBackend(options: { profile: DesktopProfile; token: string; workspace: string; resources: string; packaged: boolean; signal: AbortSignal; settingsFixture?: HarnessSettingsFixtureLaunch; onOwnedChild?: (backend: ManagedBackend) => void }): Promise<ManagedBackend> {
  const { profile, token, workspace, resources, packaged, signal } = options;
  signal.throwIfAborted();
  if (options.settingsFixture) validateHarnessSettingsFixture(options.settingsFixture, profile, workspace, packaged);
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
  const bundleRoot = path.join(resources, 'backend');
  if (packaged) {
    const manifest = JSON.parse(readFileSync(path.join(bundleRoot, 'bundle.json'), 'utf8')) as { version: number; format: string; python: { executable: string }; bootstrap: string };
    if (manifest.version !== 1 || manifest.format !== 'embedded-cpython-windows-v1' || manifest.python.executable !== 'python/python.exe' || manifest.bootstrap !== 'bootstrap.py') throw new Error('The packaged runtime launch contract is invalid.');
  }
  const command = packaged ? path.join(bundleRoot, 'python', 'python.exe') : python;
  if (!path.isAbsolute(command) || !existsSync(command)) throw new Error('The Renulus Python runtime is not available. Set RENULUS_PYTHON for development.');
  const port = await runBackendStartStep(signal, freeLoopbackPort);
  const fixture = options.settingsFixture;
  const args = [...(fixture ? [path.join(workspace, 'tools/renulus-control/harness-settings-backend.py')]
    : packaged ? ['-I', '-B', '-X', 'utf8', path.join(bundleRoot, 'bootstrap.py')] : ['-m', 'renulus.server']),
    '--profile', profile.root, '--port', String(port), ...(packaged ? ['--source-root', bundleRoot] : []),
    ...(fixture ? ['--harness-startup', fixture.startupDocument, '--harness-startup-sha256', fixture.startupSha256, '--helper-assets', fixture.helperAssets] : [])];
  const deps = {
    forceKillProcessTree: (pid: number) => { execFileSync('taskkill', ['/PID', String(pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore', timeout: 10000 }); },
    isProcessAlive: (pid: number): boolean | undefined => {
      try { process.kill(pid, 0); return true; }
      catch (error) { return (error as NodeJS.ErrnoException).code === 'ESRCH' ? false : undefined; }
    },
  };
  signal.throwIfAborted();
  const source = packaged ? bundleRoot : workspace;
  const child = spawn(command, args, { cwd: source, env: backendEnvironment(profile, token, path.join(source, 'runtime'), path.join(source, 'upstream', 'hermes')), windowsHide: true, detached: process.platform !== 'win32', stdio: ['ignore', 'ignore', 'ignore'] });
  let stopped: Promise<void> | undefined;
  let failed = false;
  let ready = false;
  child.once('error', () => { failed = true; });
  const stop = () => {
    if (!stopped) {
      stopped = (async () => {
        if (child.pid && child.exitCode === null && child.signalCode === null) {
          if (ready) {
            // Quit aborts the app lifetime first. Bound the full shutdown response independently.
            const shutdown = new AbortController();
            const deadline = setTimeout(() => shutdown.abort(new Error('The local backend shutdown timed out; retaining ownership.')), 8000);
            try {
              await runBackendStartStep(shutdown.signal, async () => {
                const response = await fetch('http://127.0.0.1:' + port + '/api/v1/runtime/shutdown', {
                  method: 'POST', headers: { 'x-renulus-token': token, 'content-type': 'application/json' },
                  body: JSON.stringify({ timeout_seconds: 5 }), redirect: 'error', cache: 'no-store', signal: shutdown.signal,
                });
                if (!response.ok) throw new Error('The local backend shutdown did not settle; retaining ownership.');
                const acknowledgement = await response.json() as { state?: unknown; api_version?: unknown } | null;
                if (acknowledgement?.state !== 'settled' || acknowledgement.api_version !== 1) throw new Error('The local backend shutdown acknowledgement is invalid; retaining ownership.');
              });
            } finally { clearTimeout(deadline); }
          }
          stopBackendChild(child, deps);
          await waitForBackendExit(child, deps, 15000);
        }
      })();
      stopped.catch(() => { stopped = undefined; });
    }
    return stopped;
  };
  const handle: ManagedBackend = { port, child, owned: true, stop };
  // Publish physical ownership before the first asynchronous readiness wait.
  options.onOwnedChild?.(handle);
  const onAbort = () => { void stop().catch(() => {}); };
  signal.addEventListener('abort', onAbort, { once: true });
  try {
    // Both managed launch modes verify helpers and warm the same CPU frameworks.
    // Cold Windows startup can exceed 30s in development and 120s when packaged.
    // Keep a finite shared bound; cancellation still releases the owned child.
    const deadline = Date.now() + 300_000;
    while (Date.now() < deadline) {
      signal.throwIfAborted();
      if (failed || child.exitCode !== null || child.signalCode !== null) throw new Error('The local backend exited during startup.');
      try {
        // Authenticated meta proves this is our child session, not an unrelated listener.
        const response = await runBackendStartStep(signal, () => fetch('http://127.0.0.1:' + port + '/api/v1/meta', { headers: { 'x-renulus-token': token }, signal: AbortSignal.any([signal, AbortSignal.timeout(1000)]), redirect: 'error', cache: 'no-store' }));
        const meta = await response.json() as { api_version: number };
        signal.throwIfAborted();
        if (response.ok && meta.api_version === 1) { ready = true; return handle; }
      } catch { signal.throwIfAborted(); }
      await runBackendStartStep(signal, () => new Promise(resolve => setTimeout(resolve, 150)));
    }
    throw new Error('The local backend did not become ready in time.');
  } catch (error) { await stop(); throw error; }
  finally { signal.removeEventListener('abort', onAbort); }
}
