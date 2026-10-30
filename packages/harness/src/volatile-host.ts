// SPDX-License-Identifier: MIT
/** Native Session/Job/context graph and all Effect filesystem writes live in RAM. */
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { ByteSize, Effect, FileSystem, Layer, Option, Stream } from 'effect';
import { Database } from '@opencode/core/database/database';
import { filesystem } from '@opencode/util/effect/app-node-platform';
import { Session } from '@opencode/schema/session';
import { SessionMessage } from '@opencode/schema/session-message';
import { openHarness, type HarnessOptions } from './host.ts';

function fail(code: string): never { throw Object.assign(new Error(code), { code }); }

/** Bounded bytes only; unsupported filesystem operations fail instead of falling back. */
export function createVolatileFiles(root: string, maxBytes = 64 * 1024 * 1024) {
  const files = new Map<string, Uint8Array>(), directories = new Set<string>([path.resolve(root)]);
  let bytes = 0, closed = false;
  const key = (value: string) => {
    const result = path.resolve(value);
    // Even native ancestor/config probes resolve exclusively in this RAM map.
    // No path is ever forwarded to the physical filesystem.
    if (closed) fail('volatile_files_closed');
    return result;
  };
  const write = (name: string, value: Uint8Array) => {
    name = key(name); const size = bytes - (files.get(name)?.byteLength ?? 0) + value.byteLength;
    if (size > maxBytes) fail('volatile_capacity');
    bytes = size; files.set(name, value.slice()); directories.add(path.dirname(name));
  };
  const info = (name: string): FileSystem.File.Info => ({ type: directories.has(name) ? 'Directory' : 'File',
    size: ByteSize.bytes(files.get(name)?.byteLength ?? 0), mtime: Option.none(), atime: Option.none(), birthtime: Option.none(),
    dev: 0, ino: Option.none(), mode: 0o600, nlink: Option.none(), uid: Option.none(), gid: Option.none(),
    rdev: Option.none(), blksize: Option.none(), blocks: Option.none() });
  const service = FileSystem.makeNoop({
    exists: name => Effect.sync(() => files.has(key(name)) || directories.has(key(name))),
    makeDirectory: name => Effect.sync(() => { directories.add(key(name)); }),
    realPath: name => Effect.sync(() => key(name)),
    stat: name => Effect.sync(() => { name = key(name); if (!files.has(name) && !directories.has(name)) fail('volatile_file_missing'); return info(name); }),
    readFile: name => Effect.sync(() => { const body = files.get(key(name)); if (!body) fail('volatile_file_missing'); return body.slice(); }),
    readFileString: name => Effect.sync(() => { const body = files.get(key(name)); if (!body) fail('volatile_file_missing'); return Buffer.from(body).toString('utf8'); }),
    writeFile: (name, body) => Effect.sync(() => write(name, body)),
    writeFileString: (name, body) => Effect.sync(() => write(name, Buffer.from(body))),
    readDirectory: name => Effect.sync(() => { const directory = key(name); return [...new Set([...files.keys(), ...directories].filter(p => path.dirname(p) === directory).map(p => path.basename(p)))]; }),
    remove: (name, options) => Effect.sync(() => { name = key(name); for (const [p, body] of files) if (p === name || options?.recursive && p.startsWith(name + path.sep)) { bytes -= body.byteLength; body.fill(0); files.delete(p); } directories.delete(name); }),
    rename: (from, to) => Effect.sync(() => { from = key(from); const body = files.get(from); if (!body) fail('volatile_file_missing'); write(to, body); bytes -= body.byteLength; files.delete(from); }),
    watch: () => Stream.never,
  });
  return { service, entries: () => [...files].map(([name, body]) => ({ name, body: body.slice() })),
    close() { closed = true; for (const body of files.values()) body.fill(0); files.clear(); directories.clear(); bytes = 0; } };
}

export async function openVolatileHarness(options: Omit<HarnessOptions, 'volatileGraph'>) {
  const files = createVolatileFiles(path.resolve(options.root));
  const database = Database.configured({ path: ':memory:' });
  const host = await openHarness({ ...options, processGeneration: undefined, capabilityArtifacts: [],
    volatileGraph: { overrides: [
      Database.node.replace(database.mapLayer(original => Layer.flatMap(original, context => Layer.effect(Database.Service,
        Effect.gen(function* () {
          const service = yield* Effect.provide(Database.Service, Layer.succeedContext(context));
          yield* service.db.run('PRAGMA temp_store=MEMORY'); return service;
        }).pipe(Effect.orDie))))),
      filesystem.replace(Layer.succeed(FileSystem.FileSystem, files.service)),
    ] } }).catch(error => { files.close(); throw error; });
  return { ...host, retention: 'temporary' as const,
    files: () => files.entries(),
    async close(input?: { timeoutMs?: number }) {
      const result = await host.close(input); if (result.state === 'closed') files.close(); return result;
    } };
}
export type VolatileHarness = Awaited<ReturnType<typeof openVolatileHarness>>;

export type NativeGraph = Awaited<ReturnType<VolatileHarness['exportSession']>>[];
/** Freeze/settle before calling. These are native transfers, never a second transcript. */
export async function exportVolatileFamily(host: VolatileHarness, rootId: string): Promise<NativeGraph> {
  const pending = [rootId], seen = new Set<string>(), graph: NativeGraph = [];
  while (pending.length) {
    const id = pending.shift()!; if (seen.has(id)) fail('volatile_family_cycle'); seen.add(id);
    if (seen.size > 64) fail('volatile_family_capacity');
    const children = await host.listChildren(id);
    if (children.length >= 100) fail('volatile_family_capacity');
    pending.push(...children.map(child => child.id)); graph.push(await host.exportSession(id));
  }
  return graph;
}
export function remapVolatileFamily(graph: NativeGraph, input: { profileId: string; storeId: string; promotionId: string }) {
  const ids = new Map<string, string>();
  for (const session of graph) {
    ids.set(session.info.id, Session.ID.create());
    for (const message of session.messages) ids.set(message.id, SessionMessage.ID.create());
  }
  const collect = (value: unknown): void => {
    if (Array.isArray(value)) { value.forEach(collect); return; }
    if (!value || typeof value !== 'object') return;
    for (const [key, child] of Object.entries(value)) {
      if (key === 'id' && typeof child === 'string' && !ids.has(child)) ids.set(child, 'ref_' + randomUUID().replaceAll('-', ''));
      collect(child);
    }
  };
  graph.forEach(collect);
  const rewrite = (value: unknown, key?: string): unknown => {
    if (typeof value === 'string') return ['text', 'title', 'content', 'description'].includes(key ?? '') ? value : ids.get(value) ?? value;
    if (Array.isArray(value)) return value.map(v => rewrite(v));
    if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, rewrite(v, k)]));
    return value;
  };
  const transferred = graph.map(source => {
    const data = rewrite(source) as NativeGraph[number];
    return { ...data, info: { ...data.info,
      metadata: { renulusProfile: input.profileId, renulusStore: input.storeId,
        operationId: input.promotionId, promotionId: input.promotionId },
      permissions: [{ action: '*', resource: '*', effect: 'deny' as const }] } };
  });
  return { graph: transferred, ids };
}

/** One native execution, no custom generation loop or retained transcript copy. */
export async function invokeVolatileHost(host: VolatileHarness, input: { text: string; signal: AbortSignal }): Promise<string> {
  input.signal.throwIfAborted();
  const operationId = 'volatile_' + randomUUID().replaceAll('-', '');
  const session = await host.createSession({ operationId, title: 'Temporary education' });
  let cancellation: Promise<unknown> | undefined;
  const cancel = () => {
    cancellation ??= (async () => {
      const interrupted = host.cancel(session.id);
      // close seals admission synchronously, including a pending admitInput.
      const closed = host.close({ timeoutMs: 30_000 });
      await interrupted; if ((await closed).state !== 'closed') fail('volatile_settlement_held');
    })(); void cancellation.catch(() => {});
  };
  input.signal.addEventListener('abort', cancel, { once: true });
  try {
    if (input.signal.aborted) cancel();
    input.signal.throwIfAborted();
    await host.submit({ sessionId: session.id, operationId, attemptId: '1', text: input.text });
    await host.wait(session.id); await cancellation; input.signal.throwIfAborted();
    const chunks: string[] = []; let cursor: string | undefined;
    do {
      const page = await host.observe(session.id, { limit: 200, ...(cursor ? { cursor } : { order: 'asc' as const }) });
      if (page.execution !== 'settled') fail('volatile_execution_unsettled');
      for (const message of page.messages) {
        if (message.type === 'idle' && message.outcome !== 'succeeded') fail('volatile_execution_failed');
        if (message.type === 'assistant') for (const part of message.content) if (part.type === 'text') chunks.push(part.text);
      }
      cursor = page.cursor.next;
    } while (cursor);
    const output = chunks.join('').trim(); if (!output) fail('volatile_empty_output'); return output;
  } finally { input.signal.removeEventListener('abort', cancel); await cancellation; }
}

export async function invokeVolatile(options: Omit<HarnessOptions, 'volatileGraph'>,
  input: { purpose: 'fictional-test' | 'compaction'; text: string; signal: AbortSignal }): Promise<string> {
  const host = await openVolatileHarness(options);
  try { await host.activate('volatile-' + input.purpose); return await invokeVolatileHost(host, input); }
  finally { const result = await host.close({ timeoutMs: 30_000 }); if (result.state !== 'closed') fail('volatile_settlement_held'); }
}
