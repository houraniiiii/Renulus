// SPDX-License-Identifier: MIT
import { createInterface } from 'node:readline';
import type { CapabilityLease, CapabilityTransport } from './contracts.ts';
import { reject } from '../../storage/contracts.ts';
import { launchHelper, type HelperResources } from '../../../../harness/src/developer-plugin.ts';

export interface BrowserTransportOptions extends HelperResources {
  /** Canonical current check for one lease (epochs, closure, expiry). The authority itself counts bytes. */
  current(lease: CapabilityLease): Promise<boolean>;
}
type Helper = { send(op: string, args?: unknown): Promise<unknown>; closed: Promise<void>; kill(): void };

/** Broker-backed tunnel factory: Python owns each lease's sockets, Node owns every credit decision.
 * `http` is not provided here; the evidence/MCP broker is a separate admitted capability. */
export function createBrowserTransport(options: BrowserTransportOptions): Omit<CapabilityTransport, 'http'> & { release(leaseId: string): Promise<void> } {
  const helpers = new Map<string, Promise<Helper>>(), sockets = new Map<string, string>();
  function start(lease: CapabilityLease): Promise<Helper> {
    const child = launchHelper(options, 'renulus.workers.capability_transport_host', []);
    const pending = new Map<number, { resolve(value: unknown): void; reject(error: Error): void }>();
    let sequence = 0, dead: Error | undefined;
    const closed = new Promise<void>(resolve => child.once('close', () => {
      dead = new Error('capability_transport_died');
      for (const item of pending.values()) item.reject(dead);
      pending.clear(); resolve();
    }));
    createInterface({ input: child.stdout }).on('line', line => {
      const message = JSON.parse(line) as { id?: number; credit?: number; ok: boolean; result?: unknown; error?: string };
      if (message.credit !== undefined) {
        void options.current(lease).catch(() => false).then(ok =>
          child.stdin.write(JSON.stringify({ credit: message.credit, ok }) + '\n'));
        return;
      }
      const item = pending.get(message.id!); pending.delete(message.id!);
      if (message.ok) item?.resolve(message.result); else item?.reject(new Error(message.error));
    });
    child.stdin.on('error', () => {});
    const helper: Helper = { closed, kill: () => { child.kill(); },
      send: (op, args) => new Promise((resolve, rejectRequest) => {
        if (dead) return rejectRequest(dead);
        const id = ++sequence; pending.set(id, { resolve, reject: rejectRequest });
        child.stdin.write(JSON.stringify({ id, op, args }) + '\n');
      }) };
    const grant = lease.grant;
    return helper.send('init', { lease: { id: lease.id, endpoints: grant.endpoints, expires_at_ms: grant.expires_at_ms,
      max_bytes: Math.min(grant.max_bytes, 100 * 1024 * 1024), max_sockets: 8 } }).then(() => helper, error => { helper.kill(); throw error; });
  }
  const owner = (leaseId: string) => helpers.get(leaseId) ?? reject('capability_transport_unbound');
  const abortable = <T>(task: Promise<T>, signal: AbortSignal) => signal.aborted ? Promise.reject(signal.reason) :
    Promise.race([task, new Promise<never>((_, fail) => signal.addEventListener('abort', () => fail(signal.reason), { once: true }))]);
  return {
    async tunnelOpen(lease, target, signal) {
      if (!helpers.has(lease.id)) helpers.set(lease.id, start(lease));
      const id = await abortable((await owner(lease.id)).send('open', { target }), signal) as string;
      sockets.set(id, lease.id); return id;
    },
    async tunnelRead(id, signal) {
      const data = await abortable((await owner(sockets.get(id) ?? reject('capability_socket_unbound'))).send('read', { socket: id }), signal) as string;
      return { data: new Uint8Array(Buffer.from(data, 'base64')), eof: data === '' };
    },
    async tunnelWrite(id, data, end, signal) {
      await abortable((await owner(sockets.get(id) ?? reject('capability_socket_unbound'))).send('write',
        { socket: id, data: Buffer.from(data).toString('base64'), end }), signal);
    },
    async tunnelClose(id) {
      const lease = sockets.get(id); sockets.delete(id);
      const helper = lease && helpers.get(lease); if (helper) await (await helper).send('close_socket', { socket: id }).catch(() => {});
    },
    /** Destroys every socket of the lease and waits for actual process exit. */
    async release(leaseId) {
      const pending = helpers.get(leaseId); if (!pending) return;
      const helper = await pending;
      const timer = setTimeout(helper.kill, 5000); timer.unref();
      try { await helper.send('close').catch(() => {}); await helper.closed; }
      finally { clearTimeout(timer); }
      helpers.delete(leaseId);
      for (const [id, lease] of sockets) if (lease === leaseId) sockets.delete(id);
    },
  };
}
