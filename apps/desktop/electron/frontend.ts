import { createServer, request as httpRequest, type Server } from 'node:http';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { timingSafeEqual } from 'node:crypto';

const types: Record<string, string> = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.woff2': 'font/woff2', '.png': 'image/png', '.ico': 'image/x-icon' };
const csp = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'";

/** Same-origin streaming proxy. Only our Electron session may reach privileged API routes. */
export async function startFrontend(dist: string, backendPort: number, token: string): Promise<{ server: Server; origin: string }> {
  const server = createServer(async (incoming, response) => {
    response.setHeader('Cache-Control', 'no-store');
    response.setHeader('Content-Security-Policy', csp);
    response.setHeader('X-Content-Type-Options', 'nosniff');
    response.setHeader('Referrer-Policy', 'no-referrer');
    const ownPort = (server.address() as { port: number }).port;
    if (incoming.headers.host !== '127.0.0.1:' + ownPort) { response.writeHead(403).end(); return; }
    const origin = incoming.headers.origin;
    if (origin && origin !== 'http://127.0.0.1:' + ownPort) { response.writeHead(403).end(); return; }
    let pathname: string;
    try { pathname = decodeURIComponent(new URL(incoming.url ?? '/', 'http://127.0.0.1').pathname); } catch { response.writeHead(400).end(); return; }
    if (pathname.startsWith('/api/v1/')) {
      const supplied = incoming.headers['x-renulus-token'];
      if (typeof supplied !== 'string' || Buffer.byteLength(supplied) !== Buffer.byteLength(token) || !timingSafeEqual(Buffer.from(supplied), Buffer.from(token))) { response.writeHead(401, { 'Content-Type': 'application/json' }).end(JSON.stringify({ error: { code: 'invalid_session', message: 'Reconnect the application', retryable: true } })); return; }
      const headers = { ...incoming.headers, host: '127.0.0.1:' + backendPort, 'x-renulus-token': token };
      delete headers.authorization;
      const upstream = httpRequest({ host: '127.0.0.1', port: backendPort, path: incoming.url, method: incoming.method, headers }, result => {
        response.writeHead(result.statusCode ?? 502, { 'Content-Type': result.headers['content-type'] ?? 'application/json', 'Cache-Control': 'no-store' });
        result.on('error', () => response.destroy());
        result.pipe(response);
      });
      upstream.on('error', () => { if (!response.headersSent) response.writeHead(502, { 'Content-Type': 'application/json' }).end(JSON.stringify({ error: { code: 'backend_unavailable', message: 'The local runtime is unavailable. Restart Renulus.', retryable: true } })); else response.destroy(); });
      response.on('close', () => upstream.destroy());
      incoming.on('aborted', () => upstream.destroy());
      incoming.pipe(upstream);
      return;
    }
    if (incoming.method !== 'GET' && incoming.method !== 'HEAD') { response.writeHead(405).end(); return; }
    if (pathname.includes(String.fromCharCode(92)) || pathname.includes(String.fromCharCode(0))) { response.writeHead(400).end(); return; }
    const relative = pathname === '/' ? 'index.html' : pathname.slice(1);
    const file = path.resolve(dist, relative);
    const inside = path.relative(path.resolve(dist), file);
    if (inside.startsWith('..') || path.isAbsolute(inside)) { response.writeHead(403).end(); return; }
    try { const bytes = await readFile(file); response.writeHead(200, { 'Content-Type': types[path.extname(file)] ?? 'application/octet-stream' }); response.end(incoming.method === 'HEAD' ? undefined : bytes); }
    catch { response.writeHead(404).end(); }
  });
  await new Promise<void>((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
  return { server, origin: 'http://127.0.0.1:' + (server.address() as { port: number }).port };
}
