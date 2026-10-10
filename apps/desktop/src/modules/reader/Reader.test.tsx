// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import Reader from './Reader';
import type { ContentReference } from '../../platform/designC';
import type { ReaderDocument } from './types';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const reference: ContentReference = { target: { type: 'library_revision', id: 'synthetic_revision' } };
function response(value: unknown) { return new Response(JSON.stringify(value), { headers: { 'content-type': 'application/json' } }); }
function source(text: string, id = 'synthetic_revision'): ReaderDocument {
  return { schema_version: 'reader/1', reference: { target: { type: 'library_revision', id } },
    title: 'SYNTHETIC source ' + id, media_type: 'text/html', authority: 'knowledge',
    original: { id, sha256: 'a'.repeat(64), bytes: 50, filename: 'synthetic.html', available: true },
    attachment_revision: null, policy_revision: 3, context_epoch: 1,
    preview_state: 'ready', extraction_state: 'ready', error: null,
    capabilities: { read: true, original: true, passage: true, ocr: false, model_image: false },
    payload: { schema_version: 'reader/1', kind: 'text', table: null, page: null, pages: null,
      asset_id: null, diagnostics: [], blocks: [{ kind: 'paragraph', item_ref: 'reader-v1:item:0', text,
        level: null, locator: { kind: 'text', item_ref: 'reader-v1:item:0', start: 0, end: Array.from(text).length }, asset_id: null }] } };
}

const studyHelpContext = {
  attempt_id: 'synthetic_attempt', item_id: 'synthetic_item', version_id: 'synthetic_version',
  draft_revision: 4, policy_revision: 3, kind: 'sources' as const,
};
const studyHeader = 'X-Renulus-Study-Context';
function stubBlobUrls() {
  let nextId = 0;
  const createObjectURL = vi.fn(() => 'blob:synthetic-reader-' + ++nextId);
  const revokeObjectURL = vi.fn();
  vi.stubGlobal('URL', class extends URL {
    static createObjectURL = createObjectURL;
    static revokeObjectURL = revokeObjectURL;
  });
  return { createObjectURL, revokeObjectURL };
}
function deferredResponse() {
  let resolve!: (value: Response) => void;
  const promise = new Promise<Response>(finish => { resolve = finish; });
  return { promise, resolve };
}
function pngResponse() { return new Response('SYNTHETIC PNG transport fixture', { headers: { 'content-type': 'image/png' } }); }

describe('inert connected reader transport', () => {
  it('renders structured cells as a native table and keeps the canonical passage locator', async () => {
    const text = 'Topic\tValue\nSYNTHETIC CKD\t<img src="/api/v1/private" onerror="fetch()">';
    const data = source(text);
    data.payload!.blocks[0].kind = 'table';
    data.payload!.blocks[0].grid = { header_rows: 1,
      rows: [['Topic', 'Value'], ['SYNTHETIC CKD', '<img src="/api/v1/private" onerror="fetch()">']] };
    const onPassage = vi.fn();
    const requests: Record<string, unknown>[] = [];
    vi.stubGlobal('fetch', vi.fn(async (path: string, options: RequestInit) => {
      const body = JSON.parse(String(options.body)); requests.push(body);
      return response(path.endsWith('/resolve') ? data : { text, reference: { ...reference, locator: body.locator }, title: data.title });
    }));
    const { container } = render(<Reader reference={reference} onPassage={onPassage} />);
    await screen.findByRole('table', { name: 'Source document table' });
    expect(screen.getAllByRole('columnheader').map(item => item.textContent)).toEqual(['Topic', 'Value']);
    expect(screen.getAllByRole('cell').map(item => item.textContent)).toEqual([
      'SYNTHETIC CKD', '<img src="/api/v1/private" onerror="fetch()">']);
    expect(container.querySelector('iframe, script, img')).toBeNull();
    expect(container.querySelector('table [data-reader-item]')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Discuss this passage' }));
    await waitFor(() => expect(onPassage).toHaveBeenCalledOnce());
    expect(requests[1].locator).toEqual({ kind: 'text', item_ref: 'reader-v1:item:0', start: 0, end: Array.from(text).length });
  });
  it('escapes markup and asks for a validated passage only after the explicit action', async () => {
    const text = '<img src="/api/v1/private" onerror="fetch()"> SYNTHETIC CKD';
    const onPassage = vi.fn();
    const requests: { path: string; body: Record<string, unknown> }[] = [];
    vi.stubGlobal('fetch', vi.fn(async (path: string, options: RequestInit) => {
      const body = JSON.parse(String(options.body)); requests.push({ path, body });
      return response(path.endsWith('/resolve') ? source(text) : { text, reference: { ...reference, locator: body.locator }, title: 'SYNTHETIC source' });
    }));
    const { container } = render(<Reader reference={reference} onPassage={onPassage} />);
    await screen.findByText(text);
    expect(container.querySelector('iframe, script, img')).toBeNull();
    expect(requests.map(item => item.path)).toEqual(['/api/v1/readers/resolve']);
    expect(onPassage).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Discuss this passage' }));
    await waitFor(() => expect(onPassage).toHaveBeenCalledOnce());
    expect(requests[1].path).toBe('/api/v1/readers/passage');
    expect(requests[1].body.expected_policy_revision).toBe(3);
    expect(requests[1].body.expected_context_epoch).toBe(1);
    expect(requests.some(item => /runs|send|provider/.test(item.path))).toBe(false);
  });

  it('drops an old response and selection when a different reference opens', async () => {
    let finishOld: (response: Response) => void = () => {};
    vi.stubGlobal('fetch', vi.fn((path: string, options: RequestInit) => {
      const body = JSON.parse(String(options.body));
      if (body.reference.target.id === 'synthetic_revision') return new Promise<Response>(resolve => { finishOld = resolve; });
      return Promise.resolve(response(source('SYNTHETIC new source', 'synthetic_new')));
    }));
    const view = render(<Reader reference={reference} />);
    view.rerender(<Reader reference={{ target: { type: 'library_revision', id: 'synthetic_new' } }} />);
    await screen.findByText('SYNTHETIC new source');
    finishOld(response(source('SYNTHETIC stale source')));
    await waitFor(() => expect(screen.queryByText('SYNTHETIC stale source')).toBeNull());
    expect(screen.queryByText('Selected source passage')).toBeNull();
  });

  it('does not offer model passage use when the shared policy or rights deny it', async () => {
    const data = source('SYNTHETIC permitted reading'); data.capabilities.passage = false;
    vi.stubGlobal('fetch', vi.fn(async () => response(data)));
    render(<Reader reference={reference} onPassage={vi.fn()} />);
    await screen.findByText('SYNTHETIC permitted reading');
    expect(screen.queryByRole('button', { name: 'Discuss this passage' })).toBeNull();
    expect(screen.getByText(/Passage discussion is unavailable/)).toBeTruthy();
  });

  it.each([undefined, studyHelpContext])('carries optional Study context only in headers on all four request kinds: %j', async context => {
    const urls = stubBlobUrls();
    const text = 'SYNTHETIC PDF passage';
    const data = source(text);
    data.media_type = 'application/pdf';
    data.original.filename = 'synthetic.pdf';
    Object.assign(data.payload!, { kind: 'pdf', page: 1, pages: 1, asset_id: 'page:1' });
    const onPassage = vi.fn();
    const requests: { path: string; headers: Headers; body: Record<string, unknown> }[] = [];
    vi.stubGlobal('fetch', vi.fn(async (path: string, options: RequestInit) => {
      const body = JSON.parse(String(options.body));
      requests.push({ path, headers: new Headers(options.headers), body });
      if (path.endsWith('/resolve')) return response(data);
      if (path.endsWith('/asset')) return pngResponse();
      if (path.endsWith('/original')) return new Response('SYNTHETIC PDF original');
      return response({ text, title: data.title, reference: { ...reference, locator: body.locator } });
    }));
    const view = render(<Reader reference={reference} onPassage={onPassage} {...{ studyHelpContext: context }} />);
    await screen.findByRole('img', { name: 'Source page' });
    fireEvent.click(screen.getByRole('button', { name: 'Prepare original download' }));
    await screen.findByRole('link', { name: 'Save original' });
    fireEvent.click(screen.getByRole('button', { name: 'Discuss this passage' }));
    await waitFor(() => expect(onPassage).toHaveBeenCalledOnce());
    expect(requests.map(item => item.path)).toEqual([
      '/api/v1/readers/resolve', '/api/v1/readers/asset', '/api/v1/readers/original', '/api/v1/readers/passage',
    ]);
    for (const request of requests) {
      expect(request.headers.get(studyHeader)).toBe(context === undefined ? null : JSON.stringify(context));
      expect(request.body.reference).toEqual(reference);
      expect(request.body).not.toHaveProperty('studyHelpContext');
      expect(request.body).not.toHaveProperty('study_context');
      expect(JSON.stringify(request.body)).not.toContain('synthetic_attempt');
      expect(JSON.stringify(request.body)).not.toContain('synthetic_item');
      expect(request.headers.has('Authorization')).toBe(false);
      expect(request.headers.has('x-renulus-token')).toBe(false);
    }
    expect(onPassage.mock.calls[0][0].reference).toEqual({ ...reference, locator: requests[3].body.locator });
    view.unmount();
    expect(urls.createObjectURL).toHaveBeenCalledTimes(2);
    expect(urls.revokeObjectURL.mock.calls.map(call => call[0])).toEqual(expect.arrayContaining(['blob:synthetic-reader-1', 'blob:synthetic-reader-2']));
  });

  it('carries Study context on inline document image requests', async () => {
    stubBlobUrls();
    const data = source('SYNTHETIC DOCX paragraph');
    data.media_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
    data.payload!.blocks.push({ kind: 'image', text: '', item_ref: 'reader-v1:item:1',
      level: null, locator: null, asset_id: 'image:1' });
    const requests: { path: string; headers: Headers; body: Record<string, unknown> }[] = [];
    vi.stubGlobal('fetch', vi.fn(async (path: string, options: RequestInit) => {
      requests.push({ path, headers: new Headers(options.headers), body: JSON.parse(String(options.body)) });
      return path.endsWith('/resolve') ? response(data) : pngResponse();
    }));
    render(<Reader reference={reference} {...{ studyHelpContext }} />);
    await screen.findByRole('img', { name: 'Source page' });
    expect(requests.map(request => request.path)).toEqual(['/api/v1/readers/resolve', '/api/v1/readers/asset']);
    expect(requests[1].headers.get(studyHeader)).toBe(JSON.stringify(studyHelpContext));
    expect(requests[1].body.asset_id).toBe('image:1');
    expect(requests[1].body.reference).toEqual(reference);
  });

  it('aborts a pending resolve when Study context changes on the same reference', async () => {
    const pending = deferredResponse();
    let oldSignal: AbortSignal | null = null;
    const current = { ...studyHelpContext, item_id: 'synthetic_next_item', draft_revision: 5 };
    vi.stubGlobal('fetch', vi.fn((path: string, options: RequestInit) => {
      if (new Headers(options.headers).get(studyHeader) === JSON.stringify(studyHelpContext)) {
        oldSignal = options.signal!; return pending.promise;
      }
      expect(new Headers(options.headers).get(studyHeader)).toBe(JSON.stringify(current));
      return Promise.resolve(response(source('SYNTHETIC current item')));
    }));
    const view = render(<Reader reference={reference} {...{ studyHelpContext }} />);
    view.rerender(<Reader reference={reference} {...{ studyHelpContext: current }} />);
    await screen.findByText('SYNTHETIC current item');
    expect(oldSignal!.aborted).toBe(true);
    await act(async () => pending.resolve(response(source('SYNTHETIC late old item'))));
    expect(screen.queryByText('SYNTHETIC late old item')).toBeNull();
    expect(screen.getByText('SYNTHETIC current item')).toBeTruthy();
  });

  it.each(['asset', 'original', 'passage'])('aborts pending %s and clears old selection/download on a changed Study receipt', async kind => {
    const urls = stubBlobUrls();
    const pending = deferredResponse();
    const data = source('SYNTHETIC selectable passage');
    const onPassage = vi.fn();
    if (kind === 'asset') Object.assign(data.payload!, { kind: 'image', page: 1, pages: 1, asset_id: 'frame:1' });
    let oldSignal: AbortSignal | null = null;
    vi.stubGlobal('fetch', vi.fn((path: string, options: RequestInit) => {
      const oldContext = new Headers(options.headers).get(studyHeader) === JSON.stringify(studyHelpContext);
      if (path.endsWith('/' + kind) && oldContext) { oldSignal = options.signal!; return pending.promise; }
      if (path.endsWith('/resolve')) return Promise.resolve(response(data));
      if (path.endsWith('/asset')) return Promise.resolve(pngResponse());
      return Promise.resolve(new Response('SYNTHETIC retained original'));
    }));
    const view = render(<Reader reference={reference} onPassage={onPassage} {...{ studyHelpContext }} />);
    await screen.findByText('SYNTHETIC selectable passage');
    if (kind === 'passage') {
      // A prepared original and a DOM selection must not survive a new help receipt.
      fireEvent.click(screen.getByRole('button', { name: 'Prepare original download' }));
      await screen.findByRole('link', { name: 'Save original' });
      const item = view.container.querySelector('[data-reader-item]')!;
      const range = document.createRange(); range.selectNodeContents(item);
      window.getSelection()!.removeAllRanges(); window.getSelection()!.addRange(range);
      fireEvent.mouseUp(item);
      fireEvent.click(screen.getByRole('button', { name: 'Ask about selected passage' }));
    } else if (kind === 'original') {
      fireEvent.click(screen.getByRole('button', { name: 'Prepare original download' }));
    }
    await waitFor(() => expect(oldSignal).not.toBeNull());
    const current = { ...studyHelpContext, policy_revision: 4 };
    view.rerender(<Reader reference={reference} onPassage={onPassage} {...{ studyHelpContext: current }} />);
    await screen.findByText('SYNTHETIC selectable passage');
    expect(oldSignal!.aborted).toBe(true);
    if (kind === 'asset') await screen.findByRole('img', { name: 'Source page' });
    await act(async () => pending.resolve(kind === 'asset' ? pngResponse() : kind === 'passage' ?
      response({ text: 'SYNTHETIC late passage', reference, title: data.title }) : new Response('SYNTHETIC late original')));
    expect(onPassage).not.toHaveBeenCalled();
    expect(screen.queryByText('Selected source passage')).toBeNull();
    expect(screen.queryByRole('link', { name: 'Save original' })).toBeNull();
    expect(urls.createObjectURL).toHaveBeenCalledTimes(kind === 'original' ? 0 : 1);
    if (kind === 'passage') expect(urls.revokeObjectURL).toHaveBeenCalledWith('blob:synthetic-reader-1');
  });
});
