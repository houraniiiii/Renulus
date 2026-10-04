import { createServer, type Server } from 'node:http';
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises';
import path from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import { startFrontend } from './frontend';

const servers: Server[] = [];
const dirs: string[] = [];
afterEach(async () => {
  for (const server of servers.splice(0)) { server.closeAllConnections(); await new Promise<void>(resolve => server.close(() => resolve())); }
  for (const dir of dirs.splice(0)) await rm(dir, { recursive: true, force: true });
});
async function fixture() {
  await mkdir('test-results', { recursive: true });
  const dist = await mkdtemp(path.resolve('test-results/frontend-')); dirs.push(dist); await writeFile(path.join(dist, 'index.html'), '<h1>Synthetic Renulus</h1>');
  let received: string | undefined;
  const backend = createServer((request, response) => {
    received = request.headers['x-renulus-token'] as string;
    if (request.url === '/api/v1/stream') { response.writeHead(200, { 'Content-Type': 'text/event-stream' }); response.end('data: {"type":"completed"}\n\n'); return; }
    response.writeHead(200, { 'Content-Type': 'application/json' }); response.end('{"status":"ready"}');
  }); servers.push(backend); await new Promise<void>(resolve => backend.listen(0, '127.0.0.1', resolve));
  const frontend = await startFrontend(dist, (backend.address() as { port: number }).port, 'synthetic-session'); servers.push(frontend.server);
  return { ...frontend, received: () => received };
}
describe('native same-origin API boundary', () => {
  it('serves the real local bundle without exposing app-session auth to browser scripts', async () => {
    const app = await fixture(); const response = await fetch(app.origin);
    expect(await response.text()).toContain('Synthetic Renulus'); expect(response.headers.get('cache-control')).toBe('no-store'); expect(response.headers.get('content-security-policy')).toContain("connect-src 'self'");
    expect(await (await fetch(app.origin + '/api/v1/health')).json()).toMatchObject({ error: { code: 'invalid_session' } }); expect(app.received()).toBeUndefined();
  });
  it('requires the desktop session, keeps SSE and rejects cross-origin requests', async () => {
    const app = await fixture(); const response = await fetch(app.origin + '/api/v1/stream', { headers: { 'x-renulus-token': 'synthetic-session' } });
    expect(response.headers.get('content-type')).toBe('text/event-stream'); expect(await response.text()).toContain('"completed"'); expect(app.received()).toBe('synthetic-session');
    expect((await fetch(app.origin + '/api/v1/health', { headers: { 'x-renulus-token': 'synthetic-session', Origin: 'https://untrusted.example' } })).status).toBe(403);
  });
});
