// SPDX-License-Identifier: MIT
import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';
import { createInterface } from 'node:readline';
import path from 'node:path';

export type McpBrokerOperation = 'http' | 'http.read' | 'http.close' | 'cleanup' |
  'credential.discover' | 'credential.refresh' | 'credential.put' | 'credential.forget' | 'connection.open' | 'connection.close' |
  'stdio.open' | 'stdio.read' | 'stdio.write' | 'stdio.close';
export interface McpBrokerPort {
  request<T = Record<string, unknown>>(op: McpBrokerOperation, input: Record<string, unknown>): Promise<T>;
  current(check: (conn: string, lease: string, bytes: number) => boolean | Promise<boolean>): void;
  close(): Promise<void>;
}

/** The subprocess sees protected credentials; this pipe carries references and protocol bytes only, except the explicit Settings `credential.put` handoff (value to DPAPI, never echoed). */
export function createMcpBroker(options: { python: string; sourceRoot: string; profile: string; state: string; workspace?: string }): McpBrokerPort {
  let child: ChildProcessWithoutNullStreams | undefined, starting: Promise<void> | undefined;
  let check: Parameters<McpBrokerPort['current']>[0] = () => false;
  let sequence = 0, closed = false;
  let exited: Promise<number | null> | undefined;
  const pending = new Map<number, { resolve(value: unknown): void; reject(error: Error): void }>();
  const fail = (error: Error) => { for (const entry of pending.values()) entry.reject(error); pending.clear(); };
  function send(frame: unknown) { if (!child || child.stdin.destroyed) throw new Error('mcp_broker_closed'); child.stdin.write(JSON.stringify(frame) + '\n'); }
  function start() {
    return starting ??= new Promise<void>((resolve, reject) => {
      const environment: NodeJS.ProcessEnv = {};
      for (const key of ['SystemRoot', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT', 'TEMP', 'TMP'])
        if (process.env[key]) environment[key] = process.env[key];
      Object.assign(environment, { PATH: path.dirname(options.python), PYTHONUTF8: '1', PYTHONDONTWRITEBYTECODE: '1',
        PYTHONUNBUFFERED: '1', PYTHONPATH: path.join(options.sourceRoot, 'runtime') });
      child = spawn(options.python, ['-B', '-m', 'renulus.workers.mcp_broker'], {
        cwd: options.sourceRoot, env: environment, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'],
      });
      // Never copy subprocess diagnostics (which may be third-party output) into native logs.
      child.stderr.resume();
      const timer = setTimeout(() => { reject(new Error('mcp_broker_ready_timeout')); child?.stdin.end(); }, 10_000);
      const stop = (error: Error) => { clearTimeout(timer); reject(error); fail(error); };
      child.once('error', () => stop(new Error('mcp_broker_spawn_failed')));
      child.stdin.on('error', () => stop(new Error('mcp_broker_pipe_closed')));
      exited = new Promise(resolveExit => child!.once('exit', code => { resolveExit(code); stop(new Error('mcp_broker_exited')); }));
      const lines = createInterface({ input: child.stdout, crlfDelay: Infinity });
      lines.on('line', line => {
        if (Buffer.byteLength(line) > 4 * 1024 * 1024) { stop(new Error('mcp_broker_frame_limit')); child?.stdin.end(); return; }
        let frame;
        try { frame = JSON.parse(line); } catch { stop(new Error('mcp_broker_frame_invalid')); child?.stdin.end(); return; }
        if (frame.op === 'ready') { clearTimeout(timer); resolve(); return; }
        if (frame.op === 'current') {
          Promise.resolve().then(() => check(frame.conn, frame.lease, frame.bytes)).then(
            ok => send({ reply: frame.id, ok: ok === true }), () => send({ reply: frame.id, ok: false })).catch(() => {});
          return;
        }
        const entry = pending.get(frame.id);
        if (!entry) return;
        pending.delete(frame.id);
        if (frame.error) entry.reject(new Error(String(frame.error))); else entry.resolve(frame.ok);
      });
      send({ op: 'launch', profile: options.profile, state: options.state, workspace: options.workspace ?? null });
    });
  }
  return {
    current(value) { check = value; },
    async request<T>(op: McpBrokerOperation, input: Record<string, unknown>): Promise<T> {
      if (closed) throw new Error('mcp_broker_closed');
      if (!starting && !['connection.open', 'credential.put', 'credential.forget'].includes(op)) throw new Error('mcp_connection_required');
      await start();
      if (closed) throw new Error('mcp_broker_closed');
      const id = ++sequence;
      return new Promise<T>((resolve, reject) => {
        pending.set(id, { resolve: value => resolve(value as T), reject });
        try { send({ ...input, op, id }); } catch (error) { pending.delete(id); reject(error); }
      });
    },
    async close() {
      closed = true;
      if (!child) return;
      child.stdin.end();
      let timer: ReturnType<typeof setTimeout> | undefined;
      try {
        const code = await Promise.race([exited, new Promise<never>((_, reject) => {
          timer = setTimeout(() => reject(new Error('mcp_broker_settlement_held')), 10_000);
        })]);
        if (code !== 0) throw new Error('mcp_broker_exit_uncertain');
      } finally { clearTimeout(timer); }
    },
  };
}
