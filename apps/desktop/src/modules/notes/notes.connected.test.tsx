// @vitest-environment jsdom
/** Actual Notes router/SQLite/originals. Only a completed acknowledgement is dropped. */
import { cleanup, configure, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { spawn, type ChildProcess } from 'node:child_process';
import { mkdtempSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterAll, beforeAll, expect, it, vi } from 'vitest';
import { fixturePython, fixtureReady, stopFixture } from '../../testBackend';
import NotesPanel from './NotesPanel';
import { NotesDraftProvider } from './NotesDrafts';
import type { Note } from './types';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../../../../..');
const profile = mkdtempSync(join(process.env.RENULUS_TEST_STATE_ROOT || tmpdir(), 'notes-ui-'));
const originalFetch = globalThis.fetch;
let backend: ChildProcess | undefined, origin = '', loseCreate = true;
const writes: { path: string; method: string; body: string; key: string | null }[] = [];
configure({ asyncUtilTimeout: 8000 });

async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await originalFetch(origin + '/api/v1' + path, { method,
    headers: { 'x-renulus-token': 'synthetic-notes-ui', 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}
beforeAll(async () => {
  const port = createServer();
  await new Promise<void>(resolve => port.listen(0, '127.0.0.1', resolve));
  const address = port.address();
  if (!address || typeof address === 'string') throw new Error('Owned loopback port unavailable');
  await new Promise<void>((resolve, reject) => port.close(error => error ? reject(error) : resolve()));
  origin = 'http://127.0.0.1:' + address.port;
  const bootstrap = [
    'import socket,sys', 'sys.path.insert(0,' + JSON.stringify(join(root, 'runtime')) + ')',
    'from renulus.server import create_app',
    'connect = socket.socket.connect',
    'def local_only(instance,address):',
    '    if isinstance(address,tuple) and address[0] in ("127.0.0.1","::1"): return connect(instance,address)',
    '    raise AssertionError("Notes fixture forbids external network")',
    'socket.socket.connect = local_only',
    'app = create_app(' + JSON.stringify(profile) + ', token="synthetic-notes-ui")',
    'assert "notes" in app.state.services.registry',
    'app.state.services.on_startup = []',
    'import uvicorn',
    'uvicorn.run(app,host="127.0.0.1",port=' + address.port + ',log_level="warning",access_log=False)',
  ].join('\n');
  let error = '';
  backend = spawn(fixturePython(root), ['-c', bootstrap], { cwd: root, windowsHide: true,
    stdio: ['ignore', 'ignore', 'pipe'], env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' } });
  backend.stderr?.on('data', chunk => { error = (error + String(chunk)).slice(-3000); });
  if (!await fixtureReady(backend, origin, originalFetch)) throw new Error(error);
  vi.stubGlobal('fetch', async (path: string, options: RequestInit = {}) => {
    const headers = new Headers(options.headers); headers.set('x-renulus-token', 'synthetic-notes-ui');
    const response = await originalFetch(origin + path, { ...options, headers, signal: undefined });
    if (options.method && options.method !== 'GET') writes.push({ path, method: options.method,
      body: String(options.body ?? ''), key: headers.get('Idempotency-Key') });
    if (loseCreate && options.method === 'POST' && path === '/api/v1/library/notes' && response.ok) {
      loseCreate = false; await response.arrayBuffer(); throw new TypeError('Synthetic lost ACK after actual commit');
    }
    return response;
  });
}, 75000);
afterAll(async () => { cleanup(); vi.unstubAllGlobals(); configure({ asyncUtilTimeout: 1000 }); await stopFixture(backend); }, 20000);

it('creates once, explicitly rebases a retained draft, reads immutable history and deletes the real originals', async () => {
  const onUse = vi.fn(async () => {});
  render(<NotesDraftProvider><NotesPanel onUse={onUse} onOpen={vi.fn()} /></NotesDraftProvider>);
  await screen.findByText('Your personal notes · Saved revisions retain earlier citations.');
  fireEvent.change(screen.getByRole('textbox', { name: 'Note title' }), { target: { value: 'Synthetic CKD notes' } });
  fireEvent.change(screen.getByRole('textbox', { name: 'Note' }), { target: { value: 'Synthetic first original' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save note' }));
  await screen.findByRole('alert');
  await waitFor(() => expect(screen.getByRole('button', { name: 'Retry save' }).hasAttribute('disabled')).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: 'Retry save' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Use note in chat' }).hasAttribute('disabled')).toBe(false));
  expect(writes).toHaveLength(2); expect(writes[1]).toEqual(writes[0]);
  const first = (await request<{ items: Note[] }>('/library/notes')).items[0];
  expect(first.ordinal).toBe(1); expect(first.reference.target.type).toBe('note_revision');
  const path = '/library/notes/' + first.document_id;
  fireEvent.change(screen.getByRole('textbox', { name: 'Note' }), { target: { value: 'Synthetic retained local edits' } });
  await request(path, 'PUT', { title: 'Synthetic concurrent title', text: 'Synthetic concurrent original',
    expected_revision_id: first.revision_id, idempotency_key: 'synthetic-notes-concurrent' });
  fireEvent.click(screen.getByRole('button', { name: 'Save note' }));
  await screen.findByRole('heading', { name: 'Latest saved revision 2' });
  expect((screen.getByRole('textbox', { name: 'Note' }) as HTMLTextAreaElement).value).toBe('Synthetic retained local edits');
  fireEvent.click(screen.getByRole('button', { name: 'Keep my edits after this revision' }));
  fireEvent.click(screen.getByRole('button', { name: 'Save note' }));
  await screen.findByText('Revision 3 · Saved');
  fireEvent.click(screen.getByRole('button', { name: 'Revision history' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Revision 1' }));
  await screen.findByText('Synthetic first original');
  fireEvent.click(screen.getByRole('button', { name: 'Close revision' }));
  fireEvent.click(screen.getByRole('button', { name: 'Use note in chat' }));
  await waitFor(() => expect(onUse).toHaveBeenCalledOnce());
  expect((await request<Note>(path)).text).toBe('Synthetic retained local edits');
  fireEvent.click(screen.getByRole('button', { name: 'Delete note' }));
  fireEvent.click(screen.getByRole('button', { name: 'Delete all revisions' }));
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Revision history' })).toBeNull());
  expect(await request('/library/notes')).toEqual({ items: [] });
  const removed = await originalFetch(origin + '/api/v1' + path + '?revision_id=' + first.revision_id,
    { headers: { 'x-renulus-token': 'synthetic-notes-ui' } });
  expect(removed.status).toBe(404);
}, 45000);
