import { EventEmitter } from 'node:events';
import { execFileSync, spawn } from 'node:child_process';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { stopBackendChild, waitForBackendExit, type StopBackendChildDeps, type WaitableChild } from './upstream/backend-child';

function pendingChild(): WaitableChild & EventEmitter {
  return Object.assign(new EventEmitter(), { pid: 424242, exitCode: null, signalCode: null, killed: true, kill: vi.fn() });
}
beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe('managed backend physical exit', () => {
  it('accepts explicit Windows absence when the Node exit fields are delayed', async () => {
    const child = pendingChild();
    const deps = { isWindows: true, forceKillProcessTree: vi.fn(), isProcessAlive: vi.fn(() => false) };
    await waitForBackendExit(child, deps);
    expect(deps.isProcessAlive).toHaveBeenCalledWith(child.pid);
    expect(deps.forceKillProcessTree).not.toHaveBeenCalled();
    expect(child.listenerCount('exit')).toBe(0);
  });

  it('checks physical absence after waiting, before escalating the same PID', async () => {
    const child = pendingChild();
    let alive = true;
    const deps = { isWindows: true, forceKillProcessTree: vi.fn(), isProcessAlive: vi.fn(() => alive) };
    const outcome = waitForBackendExit(child, deps).then(() => 'released', () => 'retained');
    alive = false;
    await vi.advanceTimersByTimeAsync(5000);
    expect(await outcome).toBe('released');
    expect(deps.forceKillProcessTree).not.toHaveBeenCalled();
    expect(child.listenerCount('exit')).toBe(0);
  });

  it.each(['alive', 'unknown', 'query-error'] as const)('retains ownership for %s even when a signal was sent', async state => {
    const child = pendingChild();
    const deps: StopBackendChildDeps = { isWindows: true, forceKillProcessTree: vi.fn(), isProcessAlive: () => {
      if (state === 'query-error') throw new Error('Synthetic access denied');
      return state === 'alive' ? true : undefined;
    } };
    const outcome = waitForBackendExit(child, deps).then(() => ({ released: true }), error => ({ error }));
    await vi.advanceTimersByTimeAsync(6000);
    expect(await outcome).toHaveProperty('error.message', 'Backend child (PID 424242) did not exit after SIGKILL; retaining ownership.');
    expect(deps.forceKillProcessTree).toHaveBeenCalledOnce();
    expect(child.listenerCount('exit')).toBe(0);
  });

  it('does not substitute a Windows root probe for POSIX group shutdown', async () => {
    const child = pendingChild();
    const deps = { isWindows: false, forceKillProcessTree: vi.fn(), killGroup: vi.fn(), isProcessAlive: vi.fn(() => false) };
    const outcome = waitForBackendExit(child, deps).then(() => 'released', () => 'retained');
    await vi.advanceTimersByTimeAsync(6000);
    expect(await outcome).toBe('retained');
    expect(deps.killGroup).toHaveBeenCalledWith(-424242, 'SIGKILL');
    expect(deps.isProcessAlive).not.toHaveBeenCalled();
  });

  it.skipIf(process.platform !== 'win32')('physically stops one real Windows child with delayed exit fields', async () => {
    vi.useRealTimers();
    const child = spawn(process.execPath, ['-e', "process.stdout.write('ready'); setInterval(() => {}, 1000)"], { windowsHide: true, stdio: ['ignore', 'pipe', 'ignore'] });
    const probe = (pid: number): boolean | undefined => {
      try { process.kill(pid, 0); return true; }
      catch (error) { return (error as NodeJS.ErrnoException).code === 'ESRCH' ? false : undefined; }
    };
    try {
      await new Promise<void>((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error('Synthetic child did not open')), 7000);
        child.stdout.once('data', () => { clearTimeout(timer); resolve(); });
        child.once('error', error => { clearTimeout(timer); reject(error); });
      });
      expect(Number.isInteger(child.pid)).toBe(true);
      const delayed: WaitableChild = { pid: child.pid, exitCode: null, signalCode: null,
        kill: signal => { child.kill(signal); }, once: (event, listener) => child.once(event, listener),
        removeListener: (event, listener) => child.removeListener(event, listener) };
      const deps = { isWindows: true, isProcessAlive: probe, forceKillProcessTree: (pid: number) => {
        execFileSync('taskkill', ['/PID', String(pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore', timeout: 10000 });
      } };
      stopBackendChild(delayed, deps);
      await waitForBackendExit(delayed, deps);
      expect(probe(child.pid!)).toBe(false);
    } finally {
      if (child.pid && probe(child.pid) === true) child.kill('SIGKILL');
      child.stdout.destroy();
    }
  }, 20000);
});
