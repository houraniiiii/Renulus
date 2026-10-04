import { createServer, type RequestListener, type Server } from 'node:http';
import { mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { tmpdir } from 'node:os';
import { once } from 'node:events';
import { afterEach, expect, it } from 'vitest';
import { BackupDownloadError, downloadBackup, validBackupOperation } from './backup-download';

const servers: Server[] = []; const dirs: string[] = [];
afterEach(async () => {
  for (const server of servers.splice(0)) { server.closeAllConnections(); await new Promise<void>(resolve => server.close(() => resolve())); }
  for (const directory of dirs.splice(0)) await rm(directory, { recursive: true, force: true });
});
async function fixture(handler: RequestListener) {
  const server = createServer(handler); servers.push(server);
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  const directory = await mkdtemp(path.join(tmpdir(), 'renulus-download-')); dirs.push(directory);
  return { port: (server.address() as { port: number }).port, token: 'synthetic-session',
    kind: 'zip' as const, destination: path.join(directory, 'study.zip'), directory, signal: new AbortController().signal };
}

it('streams a large backup with backpressure through only the owned route and session header', async () => {
  const block = Buffer.alloc(256 * 1024, 65); const count = 192;
  let route: string | undefined; let session: string | string[] | undefined; let authorization: string | undefined;
  const target = await fixture(async (request, response) => {
    route = request.url; session = request.headers['x-renulus-token']; authorization = request.headers.authorization;
    response.writeHead(200, { 'Content-Type': 'application/zip', 'Content-Length': block.length * count });
    for (let i = 0; i < count; i++) if (!response.write(block)) await once(response, 'drain');
    response.end();
  });
  const result = await downloadBackup(target);
  expect(result).toEqual({ fileName: 'study.zip', bytes: block.length * count });
  expect(route).toBe('/api/v1/data/backup'); expect(session).toBe('synthetic-session'); expect(authorization).toBeUndefined();
  expect(await readdir(target.directory)).toEqual(['study.zip']);
  expect((await readFile(target.destination)).subarray(-5).toString()).toBe('AAAAA');
});

it('removes a partial oversize transfer and preserves an existing destination', async () => {
  const target = await fixture((_request, response) => { response.writeHead(200, { 'Content-Type': 'application/zip' }); response.end('TOO_MANY_BYTES'); });
  await writeFile(target.destination, 'EXISTING_BACKUP');
  await expect(downloadBackup({ ...target, maxBytes: 5 })).rejects.toMatchObject({ code: 'backup_limit' });
  expect(await readFile(target.destination, 'utf8')).toBe('EXISTING_BACKUP');
  expect(await readdir(target.directory)).toEqual(['study.zip']);
});

it('cancels an active transfer, cleans only its partial, and preserves the selected existing file', async () => {
  let release!: () => void; const started = new Promise<void>(resolve => { release = resolve; });
  const target = await fixture((_request, response) => { response.writeHead(200, { 'Content-Type': 'application/zip' }); response.write('PARTIAL'); release(); });
  await writeFile(target.destination, 'EXISTING_BACKUP');
  const controller = new AbortController(); const pending = downloadBackup({ ...target, signal: controller.signal });
  await started; controller.abort();
  await expect(pending).rejects.toMatchObject({ name: 'AbortError' });
  expect(await readFile(target.destination, 'utf8')).toBe('EXISTING_BACKUP');
  expect(await readdir(target.directory)).toEqual(['study.zip']);
});

it('rejects redirects and raw error bodies without creating a file or exposing response content', async () => {
  const target = await fixture((_request, response) => { response.writeHead(302, { Location: 'https://untrusted.example' }); response.end('PRIVATE_RAW_RESPONSE'); });
  await expect(downloadBackup(target)).rejects.toMatchObject({ code: 'backup_unavailable' });
  expect(await readdir(target.directory)).toEqual([]);
});

it('returns a bounded structured app error and rejects a wrong MIME before saving', async () => {
  let failure = true;
  const target = await fixture((_request, response) => {
    if (failure) { response.writeHead(409, { 'Content-Type': 'application/json' }); response.end(JSON.stringify({ error: { code: 'backup_original_missing', message: 'An eligible original is missing.' } })); }
    else { response.writeHead(200, { 'Content-Type': 'text/html' }); response.end('WRONG_FORMAT'); }
  });
  await expect(downloadBackup(target)).rejects.toEqual(new BackupDownloadError('backup_original_missing', 'An eligible original is missing.'));
  failure = false;
  await expect(downloadBackup(target)).rejects.toMatchObject({ code: 'invalid_backup_response' });
  expect(await readdir(target.directory)).toEqual([]);
  expect(validBackupOperation('d0b5d129-013a-4363-8f21-fc51e1454ae4')).toBe(true);
  expect(validBackupOperation('../../outside')).toBe(false);
});
