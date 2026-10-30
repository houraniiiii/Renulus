// SPDX-License-Identifier: MIT
import { Worker } from 'node:worker_threads';
import { StorageError, validateCommand } from './contracts.ts';
import type { CommandResults, PreviewOptions, StorageCommand, StoragePreview, WriterOptions } from './contracts.ts';
export { StorageError } from './contracts.ts';
export { loadMigrationInventory } from './schema.ts';
export { MARKER, SELECTOR, OWNER } from './ownership.ts';
export type * from './contracts.ts';

type Pending = { resolve: (value: unknown) => void; reject: (error: Error) => void };
export interface StorageClient {
  command<C extends StorageCommand>(command: C): Promise<CommandResults[C['type']]>;
  /** Drains admitted work. A worker crash rejects with uncertain settlement, never auto-retries. */
  close(): Promise<void>;
}

async function connect(data: { mode: 'preview'; options: PreviewOptions } | { mode: 'writer'; options: WriterOptions }): Promise<StorageClient> {
  // Do not inherit arbitrary preload/loader arguments into the canonical worker.
  const worker = new Worker(new URL(import.meta.url.endsWith('.ts') ? './worker.ts' : './storage-worker.mjs', import.meta.url), { workerData: data, execArgv: [], env: {} });
  const pending = new Map<number, Pending>();
  let sequence = 0, closing = false, dead = false, closePromise: Promise<void> | undefined;
  let readyResolve: () => void, readyReject: (error: Error) => void;
  const ready = new Promise<void>((resolve, reject) => { readyResolve = resolve; readyReject = reject; });
  function failure(error: Error) {
    dead = true; readyReject(error);
    for (const entry of pending.values()) entry.reject(error);
    pending.clear();
  }
  worker.on('error', () => failure(new StorageError('storage_worker_lost', 'Canonical worker lost; admitted mutations have uncertain settlement. Reconcile the receipt before retry.')));
  worker.on('exit', () => {
    if (pending.size || !closing) failure(new StorageError('storage_worker_lost'));
    dead = true;
  });
  worker.on('message', message => {
    if (message.type === 'ready') { readyResolve(); return; }
    if (message.type === 'startup-error') {
      failure(new StorageError(message.code, message.message)); return;
    }
    const entry = pending.get(message.id);
    if (!entry) return;
    pending.delete(message.id);
    if (message.error) entry.reject(new StorageError(message.error.code, message.error.message));
    else entry.resolve(message.result);
  });
  await ready;
  function send(command: StorageCommand | { type: 'close' }): Promise<unknown> {
    if (dead) return Promise.reject(new StorageError('storage_worker_lost'));
    if (command.type !== 'close' && pending.size >= 64) return Promise.reject(new StorageError('storage_overloaded'));
    return new Promise((resolve, reject) => {
      const id = ++sequence;
      pending.set(id, { resolve, reject });
      try { worker.postMessage({ id, command }); }
      catch (error) { pending.delete(id); reject(error); }
    });
  }
  return {
    command<C extends StorageCommand>(command: C): Promise<CommandResults[C['type']]> {
      if (closing) return Promise.reject(new StorageError('storage_closed'));
      try { validateCommand(command); } catch (error) { return Promise.reject(error); }
      return send(command) as Promise<CommandResults[C['type']]>;
    },
    close() {
      if (closePromise) return closePromise;
      closing = true;
      // Reserve one control slot; close stays behind every already admitted command.
      closePromise = send({ type: 'close' }).then(() => undefined);
      return closePromise;
    },
  };
}

export function openIsolatedStorage(options: WriterOptions): Promise<StorageClient> { return connect({ mode: 'writer', options }); }
export async function previewStorage(options: PreviewOptions): Promise<StoragePreview> {
  const client = await connect({ mode: 'preview', options });
  try { return await client.command({ type: 'storage.preview' }); }
  finally { await client.close(); }
}
