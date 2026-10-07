/** Isolated Python API fixture lifecycle; never imported by product entries. */
import { spawnSync, type ChildProcess } from 'node:child_process';
import { existsSync } from 'node:fs';
import { join } from 'node:path';

export function fixturePython(repositoryRoot: string) {
  const pinned = join(repositoryRoot, '.venv', process.platform === 'win32' ? 'Scripts' : 'bin',
    process.platform === 'win32' ? 'python.exe' : 'python');
  return process.env.RENULUS_TEST_PYTHON || (existsSync(pinned) ? pinned : 'python');
}

export async function fixtureReady(backend: ChildProcess, origin: string, fetcher: typeof globalThis.fetch) {
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    try {
      if ((await fetcher(origin + '/api/v1/health', { signal: AbortSignal.timeout(1000) })).ok) return true;
    } catch { /* Cold imports and pack/database setup have a finite readiness budget. */ }
    if (backend.exitCode !== null || backend.signalCode !== null) return false;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  return false;
}

export async function stopFixture(backend: ChildProcess | undefined) {
  if (!backend || backend.exitCode !== null || backend.signalCode !== null) return;
  const exited = new Promise<void>(resolve => backend.once('exit', () => resolve()));
  if (process.platform === 'win32') {
    // A venv launcher can have its own Python child holding SQLite/files. Only
    // the PID created by this fixture and its descendants are stopped.
    const stopped = spawnSync(join(process.env.SystemRoot || 'C:/Windows', 'System32/taskkill.exe'),
      ['/PID', String(backend.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore', timeout: 10_000 });
    if (stopped.error || (stopped.status !== 0 && backend.exitCode === null))
      throw new Error('The owned API fixture process tree could not be stopped.');
  } else backend.kill();
  await exited;
}
