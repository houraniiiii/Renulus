// SPDX-License-Identifier: MIT
/** BF03 developer plugin: file, shell, worktree and browser families on the pinned native tools.
 * Off unless a separate developer configuration sets `enabled: true`. Trusted OS execution, not a sandbox:
 * roots and approvals govern admission only (spec section 4, "Developer execution trust"). */
import { spawn, execFile, type ChildProcessByStdio } from 'node:child_process';
import type { Readable, Writable } from 'node:stream';
import { createHash } from 'node:crypto';
import { lstat, mkdir, readFile, realpath } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { Effect } from 'effect';
import type { Tool } from '@opencode/schema/tool';
import type { BrowserAttachment, CapabilityEnvelope, CapabilityGrant, CapabilityLease } from '../../backend/src/domain/capabilities/contracts.ts';
import type { NativeCapabilityAuthority, NativeCapabilityPorts } from './capability-authority.ts';

export interface DeveloperRoot { path: string; read: boolean; write: boolean; execute: boolean }
export interface DeveloperConfiguration {
  /** Explicit direct opt-in. Any other value, or no configuration, leaves every developer tool unregistered. */
  enabled: true;
  workspace: string;
  /** Separately selectable action grants, e.g. `developer.files.read`, `developer.shell`, `developer.browser`. */
  actions: readonly string[];
  roots: readonly DeveloperRoot[];
  /** Reviewed executables by command name. A command word resolves only through this table. */
  executables: Readonly<Record<string, string>>;
  /** Reviewed git used to prove worktree identity. */
  git?: string;
  /** Exact browser network targets (host:port, resolved address pinned by the transport). */
  endpoints: readonly { host: string; port: number; private_network: boolean }[];
  /** Directory (inside a write root) that receives browser downloads, screenshots and captures. Without it those tools are refused. */
  downloads?: string;
}
export interface HelperResources { python: string; sourceRoot: string }
export interface DeveloperReceipt {
  lease_id: string; tool: string; path: string; before_sha256: string | null; after_sha256: string | null;
}
export interface OwnedWorktree { directory: string; head: string; branch: string | null; lease_id: string }
export interface DeveloperOptions {
  configuration?: DeveloperConfiguration;
  resources: HelperResources;
  /** The desktop client's owned developer browser. Absent attachment is reported, never substituted. */
  browser?: { attach(request: { sessionID: string; connectionID: string; envelope: CapabilityEnvelope }): Promise<BrowserAttachment> };
  /** Direct user approval of an exact owned worktree identity. Absent means removal is refused. */
  approveWorktreeRemoval?(worktree: OwnedWorktree & { force: boolean }, signal: AbortSignal): Promise<boolean>;
}
export type DeveloperRuntime = NonNullable<ReturnType<typeof createDeveloperRuntime>>;

export const BROWSER_EXPORTS = /^browser\.(files\.get|screenshot|trace|cpu|heap|lighthouse)/;
const deny = (code: string): never => { throw new Error(code); };
const sha256 = (bytes: string | Uint8Array) => createHash('sha256').update(bytes).digest('hex');
const same = (left: string, right: string) => process.platform === 'win32' ? left.toLowerCase() === right.toLowerCase() : left === right;
const inside = (root: string, target: string) => { const rel = path.relative(root, target); return !rel.startsWith('..') && !path.isAbsolute(rel); };

/** Minimal explicit environment for every owned helper process. */
export function launchHelper(resources: HelperResources, module: string, args: readonly string[]): ChildProcessByStdio<Writable, Readable, null> {
  const environment: NodeJS.ProcessEnv = {};
  for (const key of ['SystemRoot', 'WINDIR', 'COMSPEC', 'PATHEXT']) if (process.env[key]) environment[key] = process.env[key];
  Object.assign(environment, { PATH: path.dirname(resources.python), PYTHONUTF8: '1', PYTHONDONTWRITEBYTECODE: '1',
    PYTHONUNBUFFERED: '1', PYTHONPATH: path.join(resources.sourceRoot, 'runtime'), TEMP: tmpdir(), TMP: tmpdir() });
  return spawn(resources.python, ['-B', '-m', module, ...args], { cwd: resources.sourceRoot, env: environment,
    windowsHide: true, stdio: ['pipe', 'pipe', 'ignore'] });
}

/** Splits a command into argv without a shell: operators, expansion and redirection are refused. */
function argvOf(command: unknown): string[] {
  if (typeof command !== 'string' || !command.trim() || command.length > 8000 || /[&|<>^%;`\r\n\0]/.test(command)) return deny('developer_command_invalid');
  const words = [...command.matchAll(/"([^"]*)"|(\S+)/g)].map(match => match[1] ?? match[2]);
  return words.length > 64 ? deny('developer_command_invalid') : words;
}
function patchPaths(text: unknown): string[] {
  if (typeof text !== 'string') return deny('developer_path_required');
  return [...text.matchAll(/^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)$/gm)].map(match => match[1].trim());
}

export function createDeveloperRuntime(options: DeveloperOptions) {
  const configuration = options.configuration;
  if (configuration?.enabled !== true) return undefined;
  const workspace = path.resolve(configuration.workspace);
  if (!path.isAbsolute(configuration.workspace)) return deny('developer_workspace_absolute');
  // The patched browser plugin saves exports here (never to the OS temp directory); one developer runtime per process.
  if (configuration.downloads) (globalThis as Record<symbol, unknown>)[Symbol.for('renulus.browser.downloads')] = path.resolve(workspace, configuration.downloads);
  const receipts: DeveloperReceipt[] = [], known = new Map<string, string>(), owned = new Map<string, OwnedWorktree>();
  const key = (file: string) => process.platform === 'win32' ? file.toLowerCase() : file;
  const requireDeveloper = (envelope: CapabilityEnvelope) => {
    if (envelope.mode !== 'developer' || envelope.retention !== 'saved' || envelope.depth !== 0) deny('developer_profile_required');
  };

  /** Resolves a model-supplied path inside a granted root of the right kind; aliases are refused. */
  async function allowed(lease: CapabilityLease, raw: unknown, right: 'read' | 'write' | 'execute'): Promise<string> {
    requireDeveloper(lease.envelope);
    if (typeof raw !== 'string' || !raw || raw.includes('\0')) return deny('developer_path_required');
    const target = path.resolve(workspace, raw);
    let existing = target;
    while (!(await lstat(existing).then(() => true, () => false))) existing = path.dirname(existing);
    if (!same(await realpath(existing), existing)) return deny('developer_path_alias');
    for (const root of lease.grant.roots) {
      if (!root[right]) continue;
      const base = path.resolve(root.path);
      if (inside(base, target) && same(await realpath(base), base)) return target;
    }
    return deny('developer_root_denied');
  }
  const fileHash = async (file: string) => (await lstat(file).then(s => s.isFile(), () => false)) ? sha256(await readFile(file)) : null;

  const git = async (...args: string[]) => {
    if (!configuration.git) return deny('developer_git_unreviewed');
    return new Promise<string>((resolve, rejectRun) => execFile(configuration.git!, args, { cwd: workspace, windowsHide: true, timeout: 15000,
      env: { SystemRoot: process.env.SystemRoot ?? '', PATH: path.dirname(configuration.git!) } },
    (error, stdout) => error ? rejectRun(new Error('developer_git_failed')) : resolve(stdout)));
  };
  async function worktrees() {
    const entries: OwnedWorktree[] = [];
    for (const block of (await git('worktree', 'list', '--porcelain')).split(/\r?\n\r?\n/)) {
      const fields = Object.fromEntries(block.split(/\r?\n/).filter(Boolean).map(line => [line.split(' ')[0], line.slice(line.indexOf(' ') + 1)]));
      if (fields.worktree) entries.push({ directory: await realpath(fields.worktree), head: fields.HEAD ?? '', branch: fields.branch ?? null, lease_id: '' });
    }
    return entries;
  }

  return {
    /** Grant derived only from the separate developer configuration; never from tool arguments. */
    grant(action: string): CapabilityGrant {
      if (!configuration.actions.includes(action)) return deny('developer_action_not_enabled');
      const browser = action.startsWith('developer.browser');
      return { actions: [action], roots: configuration.roots.map(root => ({ ...root })), skills: [],
        endpoints: browser || action === 'developer.http' ? configuration.endpoints.map(endpoint => ({ ...endpoint })) : [],
        max_bytes: browser ? 100 * 1024 * 1024 : 4 * 1024 * 1024, expires_at_ms: Date.now() + 299_000 };
    },
    actions: [...configuration.actions],
    receipts: () => receipts.map(receipt => ({ ...receipt })),
    worktrees: () => [...owned.values()].map(item => ({ ...item })),

    ports(authority: NativeCapabilityAuthority, session: (sessionID: string, call: string) => Promise<CapabilityEnvelope>): NonNullable<NativeCapabilityPorts['developer']> {
      return {
        workspace,
        async files(lease, tool, input, signal) {
          signal.throwIfAborted();
          const fields = (input && typeof input === 'object' ? input : {}) as Record<string, unknown>;
          const writing = lease.action === 'developer.files.write';
          if (BROWSER_EXPORTS.test(tool)) {
            await mkdir(await allowed(lease, configuration.downloads ?? deny('developer_downloads_root_required'), 'write'), { recursive: true });
            return { async close() {} };
          }
          const raw = tool === 'patch' ? patchPaths(fields.patchText) : tool === 'browser.files.upload' || tool === 'browser.files.drop'
            ? Array.isArray(fields.paths) ? fields.paths : deny('developer_path_required')
            : tool === 'glob' || tool === 'grep' ? [fields.path ?? '.'] : [fields.path];
          if (!raw.length) return deny('developer_path_required');
          const targets = [] as { file: string; before: string | null }[];
          for (const item of raw) {
            const file = await allowed(lease, item, writing ? 'write' : 'read');
            const before = await fileHash(file);
            // A write to an existing file needs the revision this session last read or wrote.
            if (writing && before !== null && known.get(key(file)) !== before) return deny('developer_revision_required');
            targets.push({ file, before });
          }
          return { async close() {
            for (const { file, before } of targets) {
              const after = await fileHash(file);
              if (after !== null) known.set(key(file), after);
              if (writing) receipts.push({ lease_id: lease.id, tool, path: file, before_sha256: before, after_sha256: after });
            }
          } };
        },

        async shell(input, lease, signal) {
          signal.throwIfAborted();
          const fields = (input && typeof input === 'object' ? input : {}) as { command?: unknown; workdir?: unknown; timeout?: unknown; background?: unknown };
          if (fields.background === true) return deny('developer_shell_background_unsupported');
          const cwd = await allowed(lease, fields.workdir ?? '.', 'execute');
          const argv = argvOf(fields.command);
          const name = path.basename(argv[0], path.extname(argv[0])).toLowerCase();
          const reviewed = Object.entries(configuration.executables).find(([command, file]) =>
            path.isAbsolute(argv[0]) ? same(path.resolve(argv[0]), file) : command.toLowerCase() === name);
          if (!reviewed) return deny('developer_executable_unreviewed');
          argv[0] = reviewed[1];
          const timeout = typeof fields.timeout === 'number' && fields.timeout > 0 ? Math.min(fields.timeout, 60000) : 30000;
          const child = launchHelper(options.resources, 'renulus.workers.capability_shell', []);
          const reply = new Promise<Record<string, unknown>>((resolve, rejectRun) => {
            let text = '';
            child.stdout.on('data', chunk => { text += chunk; });
            child.once('close', () => { try { resolve(JSON.parse(text.trim().split('\n').pop()!)); } catch { rejectRun(new Error('developer_shell_unsettled')); } });
          });
          reply.catch(() => {});
          const environment = Object.fromEntries(['SystemRoot', 'WINDIR', 'TEMP', 'TMP'].map(name => [name, process.env[name]]).filter(([, value]) => value));
          Object.assign(environment, { PATH: path.dirname(reviewed[1]) });
          child.stdin.on('error', () => {});
          child.stdin.write(JSON.stringify({ argv, cwd, workspace, environment, mode: lease.envelope.mode, timeout_ms: timeout,
            max_output_bytes: 262144 }) + '\n');
          // Heartbeats prove the lease is current; stopping them (or `stop`) revokes the owned process family.
          const beat = setInterval(() => child.stdin.write('{"current":true}\n'), 150);
          const stop = () => { clearInterval(beat); child.stdin.write('{"stop":true}\n'); };
          signal.addEventListener('abort', stop, { once: true });
          if (signal.aborted) stop();
          let result: Record<string, unknown>;
          try { result = await reply; } finally { clearInterval(beat); signal.removeEventListener('abort', stop); child.kill(); }
          // Settlement is only claimed when the Job proved every descendant dead; otherwise the lease stays uncertain.
          if (result.ok !== true || result.descendants_settled !== true) return deny(typeof result.error === 'string' && /^[a-z_]+$/.test(result.error) ? result.error : 'developer_shell_unsettled');
          signal.throwIfAborted();
          const output = String(result.output ?? '');
          return { output: { exit: Number(result.exit_code), truncated: false, status: 'completed', output },
            content: output ? [{ type: 'text', text: output }] : [],
            metadata: { exit_code: result.exit_code, effects: 'uncertain', confined: false, descendants_settled: true,
              pid: result.pid, creation_filetime: result.creation_filetime } } as unknown as Tool.Result;
        },

        async worktree(tool, input, lease, signal) {
          signal.throwIfAborted();
          const fields = (input && typeof input === 'object' ? input : {}) as { name?: unknown; directory?: unknown; force?: unknown };
          if (tool === 'opencode.session_move') { await allowed(lease, fields.directory, 'write'); return { async close() {} }; }
          await allowed(lease, '.', 'execute');
          if (tool === 'opencode.worktree_list') return { async close() {} };
          if (tool === 'opencode.worktree_create') {
            if (typeof fields.name !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/.test(fields.name)) return deny('developer_worktree_name_invalid');
            await allowed(lease, '.', 'write');
            const before = new Set((await worktrees()).map(item => key(item.directory)));
            return { async close() {
              for (const item of await worktrees()) if (!before.has(key(item.directory))) owned.set(key(item.directory), { ...item, lease_id: lease.id });
            } };
          }
          // Destructive removal: exact owned identity plus direct approval, re-verified against git now.
          if (typeof fields.directory !== 'string' || !path.isAbsolute(fields.directory)) return deny('developer_worktree_identity_required');
          const directory = await realpath(fields.directory).catch(() => deny('developer_worktree_unowned'));
          const identity = owned.get(key(directory)) ?? deny('developer_worktree_unowned');
          const current = (await worktrees()).find(item => same(item.directory, directory));
          if (!current || current.head !== identity.head || current.branch !== identity.branch) return deny('developer_worktree_identity_changed');
          if (!options.approveWorktreeRemoval || !(await options.approveWorktreeRemoval({ ...identity, force: fields.force === true }, signal))) return deny('developer_worktree_removal_not_approved');
          return { async close() { if (!(await worktrees()).some(item => same(item.directory, directory))) owned.delete(key(directory)); } };
        },

        async browser({ sessionID, connectionID }) {
          if (!options.browser) return deny('browser_attachment_unavailable');
          const envelope = await session(sessionID, 'browser.attach.' + connectionID);
          requireDeveloper(envelope);
          const attachment = await options.browser.attach({ sessionID, connectionID, envelope });
          let browser: Awaited<ReturnType<NativeCapabilityAuthority['browser']>>;
          try { browser = await authority.browser(envelope, attachment); }
          catch (error) { await attachment.cancelPending().catch(() => {}); await attachment.removeNativeAllow().catch(() => {}); await attachment.context.close().catch(() => {}); throw error; }
          const stopped = new AbortController();
          const run = <A>(task: (signal: AbortSignal) => Promise<A>) => Effect.tryPromise({ try: () => task(stopped.signal),
            catch: error => error instanceof Error ? error : new Error(String(error)) });
          return {
            current: () => browser.current(),
            async revoke() { stopped.abort(); await browser.revoke(); },
            tunnels: {
              open: target => run(signal => browser.open(target, signal)),
              read: id => run(signal => browser.read(id, signal)),
              write: (id, data, end = false) => run(signal => browser.write(id, data, end, signal)),
              close: id => run(() => browser.closeSocket(id)),
              dispose() { stopped.abort(); void browser.revoke().catch(() => {}); },
            },
          };
        },
      };
    },
  };
}
