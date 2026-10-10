// @vitest-environment jsdom
/** Mounted App/Navigation/Workspace against production HTTP owners; no response fixtures. */
import { cleanup, configure, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { spawn, type ChildProcess } from 'node:child_process';
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { createServer } from 'node:net';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { fixturePython, fixtureReady, stopFixture } from '../testBackend';
import type { ContentReference, ConversationSummary } from '../platform/designC';
import { App } from './App';

const connected = describe.skipIf(process.env.RENULUS_SEARCH_CONNECTED !== '1');
const root = resolve(dirname(fileURLToPath(import.meta.url)), '../../../..');
const token = 'synthetic-search-connected';
const originalFetch = globalThis.fetch.bind(globalThis);
const deletedBody = 'SYNTHETIC_DELETED_LIBRARY_BODY_CKD_73';
const historicalBody = 'SYNTHETIC_HISTORICAL_ORIGINAL_DIALYSIS_84';
const replacementBody = 'SYNTHETIC_REPLACEMENT_ORIGINAL_TRANSPLANT_95';
interface LibraryPin { document_id: string; revision_id: string }
interface Seed {
  deleted: LibraryPin; prior: LibraryPin; latest: LibraryPin;
  projectA: { id: string; title: string }; projectB: { id: string; title: string };
  chat: ConversationSummary; other: ConversationSummary; reference: ContentReference;
}
interface Exchange { path: string; method: string; body: string; status: number; response: string }
let backend: ChildProcess | undefined, origin = '', evidence = '', seed: Seed;
let caseNumber = 0;
let observed: Exchange[] = [];
const descriptors = {
  modal: Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'showModal'),
  close: Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'close'),
  scroll: Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'scrollTo'),
  scrolling: Object.getOwnPropertyDescriptor(document, 'scrollingElement'),
};

async function owner(path: string, method = 'GET', body?: unknown) {
  return originalFetch(origin + '/api/v1' + path, { method,
    headers: { 'x-renulus-token': token, 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body) });
}
async function ownerJson<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await owner(path, method, body);
  if (!response.ok) throw new Error('Production owner refused ' + path + ': ' + await response.text());
  return response.json();
}
function restore(object: object, key: string, descriptor?: PropertyDescriptor) {
  if (descriptor) Object.defineProperty(object, key, descriptor);
  else Reflect.deleteProperty(object, key);
}
async function displayed(query: string, projectId?: string) {
  fireEvent.click(screen.getByRole('button', { name: 'Find a destination' }));
  const dialog = screen.getByRole('dialog', { name: 'Find in Renulus' });
  fireEvent.change(within(dialog).getByRole('textbox', { name: 'Search destinations' }), { target: { value: query } });
  if (projectId) fireEvent.change(within(dialog).getByRole('combobox', { name: 'Search scope' }), { target: { value: projectId } });
  return within(dialog).findByRole('button', { name: new RegExp(query) });
}

connected('displayed search result → current canonical destination authority', () => {
  beforeAll(async () => {
    const stateRoot = resolve(process.env.RENULUS_TEST_STATE_ROOT || 'C:/Renulus/scratch/design-c/dc-review-readers');
    const portableRoot = stateRoot.split(String.fromCharCode(92)).join('/').toLowerCase();
    const laneRoot = 'c:/renulus/scratch/design-c/dc-review-readers';
    if (portableRoot !== laneRoot && !portableRoot.startsWith(laneRoot + '/'))
      throw new Error('Search evidence requires the assigned synthetic scratch root');
    mkdirSync(stateRoot, { recursive: true });
    evidence = mkdtempSync(join(stateRoot, 'search-connected-'));
    for (const directory of ['home', 'temp', 'cache', 'appdata', 'localappdata']) mkdirSync(join(evidence, directory));
    const port = createServer();
    await new Promise<void>(resolve => port.listen(0, '127.0.0.1', resolve));
    const address = port.address();
    if (!address || typeof address === 'string') throw new Error('Owned loopback port unavailable');
    await new Promise<void>((resolve, reject) => port.close(error => error ? reject(error) : resolve()));
    origin = 'http://127.0.0.1:' + address.port;
    const manifest = join(evidence, 'seed.json');
    const bootstrap = [
      'import json,socket,sys', 'sys.path.insert(0,' + JSON.stringify(join(root, 'runtime')) + ')',
      'connect = socket.socket.connect',
      'def local_only(instance,address):',
      '    if isinstance(address,tuple) and address[0] in ("127.0.0.1","::1"): return connect(instance,address)',
      '    raise AssertionError("Search fixture forbids external network")',
      'socket.socket.connect = local_only',
      'from renulus.server import create_app',
      'from renulus.learn.conversation_models import NewConversation',
      'from renulus.study.project_models import NewProject',
      'from renulus.knowledge.note_models import CreateNote,EditNote',
      'from renulus.design_c_contracts import ConversationDraft,ContentReference',
      'app = create_app(' + JSON.stringify(join(evidence, 'profile')) + ',token=' + JSON.stringify(token) + ')',
      'services = app.state.services',
      'services.on_startup = []',
      'knowledge = services.get("knowledge")',
      'deleted = knowledge.import_text(' + JSON.stringify(deletedBody) + ',title="SearchDeletedSource",process=False)',
      'notes = services.get("notes")',
      'prior = notes.save(CreateNote(title="SearchHistoricalSource",text=' + JSON.stringify(historicalBody) + ',idempotency_key="search-original-one"))',
      'latest = notes.save(EditNote(title="SearchHistoricalSource",text=' + JSON.stringify(replacementBody) + ',expected_revision_id=prior["revision_id"],idempotency_key="search-original-two"),document_id=prior["document_id"])',
      'projects = services.get("projects")',
      'project_a = projects.create(NewProject(title="Synthetic project alpha"))',
      'project_b = projects.create(NewProject(title="Synthetic project beta"))',
      'conversations = services.get("conversations")',
      'chat = conversations.create(NewConversation(title="SearchMovedChat",project_id=project_a["id"]))',
      'other = conversations.create(NewConversation(title="Synthetic other context",project_id=project_a["id"]))',
      'reference = ContentReference(target={"type":"note_revision","id":prior["revision_id"]}).model_dump(mode="json")',
      'conversations.save_draft("learning",chat["identity"]["id"],ConversationDraft(expected_revision=chat["revision"],text="Synthetic retained historical draft",content_refs=[ContentReference.model_validate(reference)]))',
      'chat = conversations.get("learning",chat["identity"]["id"])',
      'with open(' + JSON.stringify(manifest) + ',"w",encoding="utf-8") as output:',
      '    json.dump({"deleted":deleted,"prior":prior,"latest":latest,"projectA":project_a,"projectB":project_b,"chat":chat,"other":other,"reference":reference},output)',
      'import uvicorn',
      'uvicorn.run(app,host="127.0.0.1",port=' + address.port + ',log_level="warning",access_log=False)',
    ].join(String.fromCharCode(10));
    const childEnv: NodeJS.ProcessEnv = {};
    for (const name of ['SystemRoot', 'WINDIR', 'PATH', 'PATHEXT', 'COMSPEC']) childEnv[name] = process.env[name];
    Object.assign(childEnv, { PYTHONDONTWRITEBYTECODE: '1', HF_HUB_OFFLINE: '1', TRANSFORMERS_OFFLINE: '1',
      USERPROFILE: join(evidence, 'home'), APPDATA: join(evidence, 'appdata'), LOCALAPPDATA: join(evidence, 'localappdata'),
      TEMP: join(evidence, 'temp'), TMP: join(evidence, 'temp'), HF_HOME: join(evidence, 'cache'),
      XDG_CACHE_HOME: join(evidence, 'cache') });
    let error = '';
    backend = spawn(fixturePython(root), ['-c', bootstrap], { cwd: root, windowsHide: true,
      stdio: ['ignore', 'ignore', 'pipe'], env: childEnv });
    backend.stderr?.on('data', chunk => { error = (error + String(chunk)).slice(-5000); });
    if (!await fixtureReady(backend, origin, originalFetch)) throw new Error(error);
    seed = JSON.parse(readFileSync(manifest, 'utf8')) as Seed;
    expect(seed.prior.revision_id).not.toBe(seed.latest.revision_id);
    console.info('Search connected evidence: ' + evidence);
    configure({ asyncUtilTimeout: 8000 });
  }, 75000);

  beforeEach(async () => {
    const current = await ownerJson<ConversationSummary>('/conversations/learning/' + seed.chat.identity.id);
    if (current.project_id !== seed.projectA.id) await ownerJson('/conversations/learning/' + seed.chat.identity.id + '/project', 'PUT',
      { expected_revision: current.revision, project_id: seed.projectA.id });
    observed = []; localStorage.clear();
    window.history.replaceState(null, '', '#/chat/learn_thread/' + seed.other.identity.id);
    Object.defineProperty(HTMLElement.prototype, 'scrollTo', { configurable: true, value() {} });
    Object.defineProperty(document, 'scrollingElement', { configurable: true, value: document.documentElement });
    Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value(this: HTMLDialogElement) { this.open = true; } });
    Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value(this: HTMLDialogElement) { this.open = false; this.dispatchEvent(new Event('close')); } });
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} });
    vi.stubGlobal('fetch', async (path: string, options: RequestInit = {}) => {
      if (typeof path !== 'string' || !path.startsWith('/api/v1/')) throw new Error('Search renderer attempted nonlocal transport');
      const headers = new Headers(options.headers); headers.set('x-renulus-token', token);
      // This bridge transports real replies; jsdom AbortSignals are not accepted by Node fetch.
      const response = await originalFetch(origin + path, { ...options, headers, signal: undefined });
      observed.push({ path, method: options.method ?? 'GET', body: String(options.body ?? ''),
        status: response.status, response: await response.clone().text() });
      return response;
    });
  });
  afterEach(() => {
    if (evidence) writeFileSync(join(evidence, 'exchanges-' + (++caseNumber) + '.json'), JSON.stringify(observed, null, 2));
    cleanup(); vi.unstubAllGlobals(); localStorage.clear();
    restore(HTMLElement.prototype, 'scrollTo', descriptors.scroll);
    restore(document, 'scrollingElement', descriptors.scrolling);
    restore(HTMLDialogElement.prototype, 'showModal', descriptors.modal);
    restore(HTMLDialogElement.prototype, 'close', descriptors.close);
  });
  afterAll(async () => { configure({ asyncUtilTimeout: 1000 }); await stopFixture(backend); }, 20000);

  it('refuses the removed Library body when its displayed result is selected after owner deletion', async () => {
    render(<App />);
    await screen.findByRole('heading', { name: seed.other.title });
    const result = await displayed('SearchDeletedSource');
    const deletion = await owner('/library/documents/' + seed.deleted.document_id, 'DELETE');
    expect(deletion.ok).toBe(true);
    expect(result.isConnected).toBe(true);
    expect(screen.getByRole('button', { name: /SearchDeletedSource/ })).toBe(result);
    const beforeClick = observed.length;
    fireEvent.click(result);
    await screen.findByRole('heading', { name: 'Content unavailable' });
    const decision = observed.slice(beforeClick).find(item => item.path === '/api/v1/workspace/authorize'
      && JSON.parse(item.body).reference?.target.id === seed.deleted.revision_id);
    expect(decision).toBeDefined();
    expect(JSON.parse(decision!.response)).toEqual({ allowed: false, reason: 'not_found' });
    expect(JSON.parse(decision!.body).context).toEqual({ identity: seed.other.identity, retention: 'saved' });
    expect(document.body.textContent).not.toContain(deletedBody);
    expect(observed.slice(beforeClick).some(item => item.path === '/api/v1/readers/resolve')).toBe(false);
    const original = await owner('/library/revisions/' + seed.deleted.revision_id + '/original');
    expect(original.status).toBe(404); expect(await original.text()).not.toContain(deletedBody);
    const current = await ownerJson<{ items: unknown[] }>('/search?q=SearchDeletedSource');
    expect(current.items).toEqual([]);
  }, 30000);

  it.each([false, true])('opens a reassigned chat in its current project and preserves its earlier immutable source pin (already mounted: %s)', async alreadyMounted => {
    const initial = alreadyMounted ? seed.chat : seed.other;
    window.history.replaceState(null, '', '#/chat/learn_thread/' + initial.identity.id);
    render(<App />);
    await screen.findByRole('heading', { name: initial.title });
    await waitFor(() => expect((screen.getByRole('combobox', { name: 'Project' }) as HTMLSelectElement).value).toBe(seed.projectA.id));
    const result = await displayed('SearchMovedChat', seed.projectA.id);
    const current = await ownerJson<ConversationSummary>('/conversations/learning/' + seed.chat.identity.id);
    const moved = await ownerJson<ConversationSummary>('/conversations/learning/' + seed.chat.identity.id + '/project', 'PUT',
      { expected_revision: current.revision, project_id: seed.projectB.id });
    expect(moved.project_id).toBe(seed.projectB.id);
    expect(result.isConnected).toBe(true);
    const beforeClick = observed.length;
    fireEvent.click(result);
    await waitFor(() => expect((screen.getByRole('combobox', { name: 'Project' }) as HTMLSelectElement).value).toBe(seed.projectB.id));
    expect(window.location.hash).toBe('#/chat/learn_thread/' + seed.chat.identity.id);
    expect(observed.slice(beforeClick).some(item => item.path === '/api/v1/conversations/learning/' + seed.chat.identity.id && item.status === 200)).toBe(true);
    const draft = await ownerJson<{ text: string; content_refs: ContentReference[] }>('/conversations/learning/' + seed.chat.identity.id + '/draft');
    expect(draft.content_refs).toEqual([seed.reference]);
    expect((screen.getByRole('textbox', { name: 'Message Renulus' }) as HTMLTextAreaElement).value).toBe(draft.text);
    fireEvent.click(screen.getByRole('button', { name: 'Source 1' }));
    await screen.findByText(historicalBody);
    expect(document.body.textContent).not.toContain(replacementBody);
    const authorizations = observed.slice(beforeClick).filter(item => item.path === '/api/v1/workspace/authorize');
    expect(authorizations.some(item => JSON.parse(item.body).reference?.target.id === seed.prior.revision_id)).toBe(true);
    for (const item of authorizations) expect(JSON.parse(item.body).context).toEqual({ identity: seed.chat.identity, retention: 'saved' });
    const staleScope = await ownerJson<{ items: { identity?: { id: string } }[] }>('/search?' + new URLSearchParams({ q: 'SearchMovedChat', project_id: seed.projectA.id }));
    expect(staleScope.items).toEqual([]);
    const newScope = await ownerJson<{ items: { identity?: { id: string }; project_id?: string }[] }>('/search?' + new URLSearchParams({ q: 'SearchMovedChat', project_id: seed.projectB.id }));
    expect(newScope.items).toHaveLength(1);
    expect(newScope.items[0].identity?.id).toBe(seed.chat.identity.id);
    expect(newScope.items[0].project_id).toBe(seed.projectB.id);
    expect(observed.some(item => ['/messages', '/tests', '/test-drafts'].some(suffix => item.path.endsWith(suffix)) && item.method === 'POST')).toBe(false);
  }, 30000);
});
