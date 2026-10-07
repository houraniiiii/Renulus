import { randomUUID } from 'node:crypto';
import { createWriteStream } from 'node:fs';
import { open, rename, rm } from 'node:fs/promises';
import { request, type IncomingMessage } from 'node:http';
import path from 'node:path';
import { Transform } from 'node:stream';
import { pipeline } from 'node:stream/promises';

export type BackupKind = 'zip' | 'json';
export type BackupSaveResult = { status: 'saved'; fileName: string; bytes: number }
  | { status: 'cancelled' } | { status: 'error'; code: string; message: string };
const MiB = 1024 * 1024;
const transferLimits = { zip: 8 * 1024 * MiB, json: 16 * MiB };

export class BackupDownloadError extends Error {
  constructor(readonly code: string, message: string) { super(message); this.name = 'BackupDownloadError'; }
}
export function validBackupOperation(value: unknown): value is string {
  return typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}

function response(port: number, token: string, kind: BackupKind, signal: AbortSignal): Promise<IncomingMessage> {
  return new Promise((resolve, reject) => {
    const pending = request({ host: '127.0.0.1', port, method: 'GET',
      path: kind === 'zip' ? '/api/v1/data/backup?format_version=2' : '/api/v1/data/export', signal,
      headers: { Accept: kind === 'zip' ? 'application/zip' : 'application/json', 'x-renulus-token': token },
    }, resolve);
    pending.on('error', reject); pending.end();
  });
}
async function rejectedResponse(incoming: IncomingMessage): Promise<BackupDownloadError> {
  const parts: Buffer[] = []; let size = 0;
  for await (const block of incoming) {
    size += block.length;
    if (size > 16 * 1024) {
      incoming.destroy();
      return new BackupDownloadError('backup_unavailable', 'The local runtime could not prepare this backup. Check your study data and try again.');
    }
    parts.push(block);
  }
  if (incoming.headers['content-type']?.includes('application/json')) {
    try {
      const body = JSON.parse(Buffer.concat(parts).toString('utf8'));
      const detail = body.error ?? body.detail;
      if (detail && typeof detail.code === 'string' && /^[a-z0-9_]{1,80}$/.test(detail.code) &&
          typeof detail.message === 'string' && detail.message.length > 0 && detail.message.length <= 1024) {
        return new BackupDownloadError(detail.code, detail.message);
      }
    } catch { /* Do not expose a raw response, path or traceback. */ }
  }
  return new BackupDownloadError('backup_unavailable', 'The local runtime could not prepare this backup. Check your study data and try again.');
}

/** Stream only a fixed app-owned recovery route to the user's selected file. */
export async function downloadBackup(options: {
  port: number; token: string; kind: BackupKind; destination: string; signal: AbortSignal; maxBytes?: number;
}): Promise<{ fileName: string; bytes: number }> {
  const { port, token, kind, destination, signal } = options;
  if (!Number.isInteger(port) || port < 1 || port > 65535 || !token || !['zip', 'json'].includes(kind) ||
      !path.isAbsolute(destination) || path.extname(destination).toLowerCase() !== '.' + kind) {
    throw new BackupDownloadError('invalid_backup_destination', 'Choose a local .' + kind + ' file for this backup.');
  }
  const bound = Math.min(options.maxBytes ?? transferLimits[kind], transferLimits[kind]);
  if (!Number.isSafeInteger(bound) || bound <= 0) throw new BackupDownloadError('backup_limit', 'The backup transfer limit is invalid.');
  signal.throwIfAborted();
  // A sibling partial file keeps the existing destination intact until success.
  const partial = destination + '.renulus-' + randomUUID() + '.partial';
  let ownsPartial = false;
  let incoming: IncomingMessage | undefined;
  try {
    incoming = await response(port, token, kind, signal);
    if (incoming.statusCode !== 200) throw await rejectedResponse(incoming);
    const mime = kind === 'zip' ? 'application/zip' : 'application/json';
    if (incoming.headers['content-type']?.split(';')[0].trim().toLowerCase() !== mime || incoming.headers['content-encoding']) {
      throw new BackupDownloadError('invalid_backup_response', 'The local runtime returned the wrong backup format. Try again.');
    }
    const length = incoming.headers['content-length'];
    const declared = typeof length === 'string' && /^[0-9]{1,16}$/.test(length) ? Number(length) : undefined;
    if (length !== undefined && (declared === undefined || !Number.isSafeInteger(declared) || declared > bound)) {
      throw new BackupDownloadError('backup_limit', 'The backup exceeds the supported transfer size.');
    }
    const handle = await open(partial, 'wx', 0o600); ownsPartial = true;
    await handle.close();
    let bytes = 0;
    const meter = new Transform({ transform(block: Buffer, _encoding, done) {
      bytes += block.length;
      done(bytes > bound ? new BackupDownloadError('backup_limit', 'The backup exceeds the supported transfer size.') : null, block);
    } });
    await pipeline(incoming, meter, createWriteStream(partial, { flags: 'r+', highWaterMark: 64 * 1024 }), { signal });
    if (!incoming.complete || bytes === 0 || declared !== undefined && declared !== bytes) {
      throw new BackupDownloadError('incomplete_backup', 'The backup transfer did not finish. Try again.');
    }
    signal.throwIfAborted();
    const finished = await open(partial, 'r+');
    try { await finished.sync(); } finally { await finished.close(); }
    signal.throwIfAborted();
    await rename(partial, destination); ownsPartial = false;
    return { fileName: path.basename(destination), bytes };
  } finally {
    incoming?.destroy();
    if (ownsPartial) await rm(partial, { force: true });
  }
}
