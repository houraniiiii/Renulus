import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { allowedAuthorizationUrl, backendEnvironment, resolveProfile } from './profile';
import { stopBackendChild } from './upstream/backend-child';
import { runBackendStartStep } from './upstream/backend-start-cancellation';
import { activateWindow } from './upstream/main-window-lifecycle';

describe('isolated native profile and upstream lifecycle', () => {
  it('fails closed without an explicit development profile and isolates two instances', () => {
    expect(() => resolveProfile(undefined, false)).toThrow(); expect(() => resolveProfile('relative', false)).toThrow();
    const a = resolveProfile(path.resolve('test-results/a'), false); const b = resolveProfile(path.resolve('test-results/b'), false);
    expect(a.desktop).not.toBe(b.desktop); expect(a.instance).not.toBe(b.instance); expect(a.session.startsWith(a.root)).toBe(true);
  });
  it('passes only the OS environment and app-owned Hermes paths, never inherited provider keys', () => {
    const profile = resolveProfile(path.resolve('test-results/profile'), false);
    const env = backendEnvironment(profile, 'synthetic-session', '/synthetic/runtime', '/synthetic/hermes', { PATH: 'synthetic-path', OPENAI_API_KEY: 'SYNTHETIC_FORBIDDEN', OPENCODE_API_KEY: 'SYNTHETIC_FORBIDDEN', HERMES_HOME: 'another-app', PYTHONPATH: 'another-checkout' });
    expect(env.OPENAI_API_KEY).toBeUndefined(); expect(env.OPENCODE_API_KEY).toBeUndefined(); expect(env.HERMES_HOME).toBe(path.join(profile.root, 'hermes')); expect(env.PYTHONPATH).not.toContain('another-checkout');
  });
  it('only permits HTTPS account sign-in URLs', () => {
    expect(allowedAuthorizationUrl('https://auth.openai.com/api/accounts/authorize?state=synthetic')).toBe(true);
    for (const url of ['http://auth.openai.com', 'https://auth.openai.com.attacker.test', 'file:///private', 'https://user@auth.openai.com', 'https://auth.openai.com:444', 'https://auth.openai.com/unrelated']) expect(allowedAuthorizationUrl(url)).toBe(false);
  });
  it('uses the imported Windows tree-kill only for its explicitly owned child', () => {
    const pids: number[] = []; stopBackendChild({ pid: 8123, kill: () => { throw new Error('Unexpected direct kill'); } }, { isWindows: true, forceKillProcessTree: pid => { pids.push(pid); } }); expect(pids).toEqual([8123]);
  });
  it('does not continue startup after its owner cancels', async () => {
    const controller = new AbortController(); let finish!: (value: string) => void;
    const task = runBackendStartStep(controller.signal, () => new Promise<string>(resolve => { finish = resolve; })); controller.abort(); finish('late');
    await expect(task).rejects.toMatchObject({ name: 'AbortError' });
  });
  it('restores a user-invoked minimized window and avoids redundant focus', () => {
    const events: string[] = []; activateWindow({ isDestroyed: () => false, isMinimized: () => true, isVisible: () => false, isFocused: () => false, restore: () => events.push('restore'), show: () => events.push('show'), focus: () => events.push('focus') }); expect(events).toEqual(['restore', 'show', 'focus']);
  });
});
