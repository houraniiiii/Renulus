// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import Reader from './Reader';
import type { ContentLocator, ContentReference } from '../../platform/designC';
import { WorkspacePanel, WorkspaceProvider, useWorkspace, type WorkspaceController, type WorkspacePreferences } from '../workspace';
import type { ReaderDocument } from './types';

afterEach(() => { cleanup(); window.getSelection()?.removeAllRanges(); vi.unstubAllGlobals(); });
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
function tableSource(format: 'csv' | 'xlsx', firstRow: number, sheet: string | null): ReaderDocument {
  const data = source('');
  data.media_type = format === 'csv' ? 'text/csv' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
  data.original.filename = 'synthetic.' + format;
  Object.assign(data.payload!, { kind: 'table', blocks: [], table: {
    format, sheet_name: sheet, sheets: format === 'xlsx' ? ['CKD', 'Transplant'] : [],
    first_row: firstRow, total_rows: 250, total_columns: 2,
    rows: Array.from({ length: Math.min(100, 251 - firstRow) }, (_, offset) =>
      ['SYNTHETIC ' + sheet + ' row ' + (firstRow + offset), 'value ' + (firstRow + offset)].map(display =>
        ({ display, value: display, number_format: null, formula: null, cached: true }))),
  } });
  return data;
}

describe('inert connected reader transport', () => {
  it.each(['csv', 'xlsx'] as const)('restores %s row 101 through the actual Workspace and retains page changes on reopen', async format => {
    const requests: { first_row: number; sheet?: string }[] = [];
    vi.stubGlobal('fetch', vi.fn(async (_path: string, options: RequestInit) => {
      const body = JSON.parse(String(options.body)); requests.push(body);
      return response(tableSource(format, body.first_row, format === 'xlsx' ? body.sheet ?? 'CKD' : null));
    }));
    const context = { identity: { type: 'learn_thread' as const, id: 'synthetic_chat' }, retention: 'saved' as const };
    const position: ContentLocator = { kind: 'table', format, sheet_name: format === 'xlsx' ? 'Transplant' : null,
      first_row: 101, last_row: 200, first_column: 1, last_column: 2 };
    let workspace!: WorkspaceController;
    function Probe() { workspace = useWorkspace(); return null; }
    const authorize = vi.fn(async () => ({ allowed: true as const }));
    const change = vi.fn();
    const mount = (preferences: WorkspacePreferences) => render(
      <WorkspaceProvider context={context} policy={{ active_test_id: null, revision: 3, assistance_allowed: true }}
        initialPreferences={preferences} authorize={authorize} onPreferencesChange={change}>
        <Probe /><WorkspacePanel availableWidth={1168} Reader={Reader} />
      </WorkspaceProvider>);
    const view = mount({ width: 480, tabs: [{ content: reference, context: context.identity, retention: 'saved', position }] });
    act(() => workspace.toggle());
    await screen.findByText('Rows 101–200 of 250');
    expect(requests.map(item => item.first_row)).toEqual([101]);
    expect(requests[0].sheet).toBe(format === 'xlsx' ? 'Transplant' : undefined);
    expect(workspace.getPreferences().tabs[0].position).toEqual(position);
    fireEvent.click(screen.getByRole('button', { name: 'value 102' }));
    await waitFor(() => expect(workspace.getPreferences().tabs[0].position).toEqual({
      kind: 'table', format, sheet_name: position.sheet_name, first_row: 102, last_row: 102, first_column: 2, last_column: 2,
    }));
    // The callback echo must keep the visible window and not resolve again.
    expect(screen.getByText('Rows 101–200 of 250')).toBeTruthy();
    expect(requests).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: 'Next rows' }));
    await screen.findByText('Rows 201–250 of 250');
    await waitFor(() => expect(workspace.getPreferences().tabs[0].position).toMatchObject({ first_row: 201, last_row: 250 }));
    expect(requests.map(item => item.first_row)).toEqual([101, 201]);
    const saved = workspace.getPreferences();
    expect(JSON.stringify(saved)).not.toMatch(/scrollTop|relative_path|sha256|filename|studyHelpContext/);
    view.unmount();
    mount(saved); act(() => workspace.toggle());
    await screen.findByText('Rows 201–250 of 250');
    expect(requests.map(item => item.first_row)).toEqual([101, 201, 201]);
    if (format === 'xlsx') {
      fireEvent.change(screen.getByLabelText('Sheet'), { target: { value: 'CKD' } });
      await screen.findByText('Rows 1–100 of 250');
      await waitFor(() => expect(workspace.getPreferences().tabs[0].position).toMatchObject({ sheet_name: 'CKD', first_row: 1 }));
      expect(requests.at(-1)).toMatchObject({ sheet: 'CKD', first_row: 1 });
    }
    expect(authorize).toHaveBeenCalledTimes(2);
  });

  it('keeps a selected text range when the Workspace echoes it and the click follows mouseup', async () => {
    const text = 'SYNTHETIC CKD and transplantation';
    vi.stubGlobal('fetch', vi.fn(async () => response(source(text))));
    const positions = vi.fn();
    const view = render(<Reader reference={reference} onPositionChange={positions} />);
    await screen.findByText(text);
    const item = view.container.querySelector('[data-reader-item]')!;
    const range = document.createRange(); range.setStart(item.firstChild!, 10); range.setEnd(item.firstChild!, 13);
    window.getSelection()!.removeAllRanges(); window.getSelection()!.addRange(range);
    fireEvent.mouseUp(item); fireEvent.click(item);
    const position = { kind: 'text' as const, item_ref: 'reader-v1:item:0', start: 10, end: 13 };
    expect(positions).toHaveBeenLastCalledWith(position);
    const scroll = vi.fn();
    Object.defineProperty(view.container.querySelector('[data-reader-block]'), 'scrollIntoView', { value: scroll });
    view.rerender(<Reader reference={reference} position={position} onPositionChange={positions} />);
    expect(scroll).not.toHaveBeenCalled();
    expect(positions).toHaveBeenCalledTimes(2);
    window.getSelection()!.removeAllRanges();
  });

  it('reopens selected PDF text on page 2 through the actual Workspace without replacing its offsets', async () => {
    stubBlobUrls();
    const pages: number[] = [];
    vi.stubGlobal('fetch', vi.fn(async (path: string, options: RequestInit) => {
      if (path.endsWith('/asset')) return pngResponse();
      const body = JSON.parse(String(options.body)); pages.push(body.page);
      const text = body.page === 2 ? 'SYNTHETIC SECOND PAGE TRANSPLANT' : 'SYNTHETIC page ' + body.page;
      const data = source(text); data.media_type = 'application/pdf'; data.original.filename = 'synthetic.pdf';
      Object.assign(data.payload!, { kind: 'pdf', page: body.page, pages: 5, asset_id: 'page:' + body.page });
      data.payload!.blocks[0].item_ref = 'reader-v1:pdf:' + body.page;
      data.payload!.blocks[0].locator = { kind: 'text', item_ref: data.payload!.blocks[0].item_ref, start: 0, end: text.length };
      return response(data);
    }));
    const context = { identity: { type: 'learn_thread' as const, id: 'synthetic_chat' }, retention: 'saved' as const };
    let workspace!: WorkspaceController;
    function Probe() { workspace = useWorkspace(); return null; }
    const authorize = vi.fn(async () => ({ allowed: true as const }));
    const change = vi.fn();
    const mount = (preferences: WorkspacePreferences) => render(
      <WorkspaceProvider context={context} policy={{ active_test_id: null, revision: 3, assistance_allowed: true }}
        initialPreferences={preferences} authorize={authorize} onPreferencesChange={change}>
        <Probe /><WorkspacePanel availableWidth={1168} Reader={Reader} />
      </WorkspaceProvider>);
    const view = mount({ width: 480, tabs: [{ content: reference, context: context.identity, retention: 'saved',
      position: { kind: 'pdf', physical_page: 2 } }] });
    act(() => workspace.toggle());
    const second = await screen.findByText('SYNTHETIC SECOND PAGE TRANSPLANT');
    await screen.findByRole('img', { name: 'Source page' });
    const range = document.createRange(); range.setStart(second.firstChild!, 10); range.setEnd(second.firstChild!, 16);
    window.getSelection()!.removeAllRanges(); window.getSelection()!.addRange(range);
    fireEvent.mouseUp(second); fireEvent.click(second);
    const selected: ContentLocator = { kind: 'text', item_ref: 'reader-v1:pdf:2', start: 10, end: 16 };
    await waitFor(() => expect(workspace.getPreferences().tabs[0].position).toEqual(selected));
    const saved = workspace.getPreferences();
    view.unmount(); window.getSelection()!.removeAllRanges();
    mount(saved); act(() => workspace.toggle());
    await screen.findByRole('img', { name: 'Source page' });
    expect(pages).toEqual([2, 2]);
    expect((screen.getByLabelText('Physical page') as HTMLInputElement).value).toBe('2');
    expect(workspace.getPreferences().tabs[0].position).toEqual(selected);
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    await waitFor(() => expect(workspace.getPreferences().tabs[0].position).toEqual({ kind: 'pdf', physical_page: 3 }));
    expect(pages).toEqual([2, 2, 3]);
  });

  it.each(['position', 'reference'] as const)('restores a validated PDF text %s locator and keeps its offsets', async from => {
    stubBlobUrls();
    const selected: ContentLocator = { kind: 'text', item_ref: 'reader-v1:pdf:2', section: null, start: 10, end: 16 };
    const positions = vi.fn(); const pages: number[] = [];
    vi.stubGlobal('fetch', vi.fn(async (path: string, options: RequestInit) => {
      if (path.endsWith('/asset')) return pngResponse();
      const body = JSON.parse(String(options.body)); pages.push(body.page);
      const text = 'SYNTHETIC PDF page ' + body.page; const data = source(text);
      data.media_type = 'application/pdf'; data.original.filename = 'synthetic.pdf';
      Object.assign(data.payload!, { kind: 'pdf', page: body.page, pages: 5, asset_id: 'page:' + body.page });
      data.payload!.blocks[0].item_ref = 'reader-v1:pdf:' + body.page;
      return response(data);
    }));
    render(<Reader reference={from === 'reference' ? { ...reference, locator: selected } : reference}
      position={from === 'position' ? selected : undefined} onPositionChange={positions} />);
    await screen.findByRole('img', { name: 'Source page' });
    expect(pages).toEqual([2]);
    await waitFor(() => expect(positions).toHaveBeenLastCalledWith(selected));
  });

  it('does not overwrite a retained position when preview resolution fails', async () => {
    const positions = vi.fn();
    const position: ContentLocator = { kind: 'pdf', physical_page: 3 };
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ code: 'source_unavailable', message: 'SYNTHETIC unavailable' }), { status: 404 })));
    render(<Reader reference={reference} position={position} onPositionChange={positions} />);
    await screen.findByText('The source could not be opened');
    expect(positions).not.toHaveBeenCalled();
  });

  it.each([
    { kind: 'pdf', physical_page: 0 },
    { kind: 'pdf', physical_page: 301 },
    { kind: 'pdf', physical_page: 3, path: 'SYNTHETIC-forbidden.pdf' },
    { kind: 'table', format: 'csv', first_row: 100001, last_row: 100001, first_column: 1, last_column: 1 },
    { kind: 'text', item_ref: 'reader-v1:pdf:0', start: 0, end: 1 },
    { kind: 'text', item_ref: 'reader-v1:pdf:301', start: 0, end: 1 },
    { kind: 'text', item_ref: 'reader-v1:pdf:2x', start: 0, end: 1 },
  ])('ignores malformed or unrequestable Workspace positions: %j', async invalid => {
    const positions = vi.fn();
    const pages: number[] = [];
    vi.stubGlobal('fetch', vi.fn(async (_path: string, options: RequestInit) => {
      const body = JSON.parse(String(options.body)); pages.push(body.page);
      expect(body).not.toHaveProperty('position');
      expect(JSON.stringify(body)).not.toContain('SYNTHETIC-forbidden');
      const data = source('SYNTHETIC page 2');
      Object.assign(data.payload!, { kind: 'pdf', page: body.page, pages: 5 });
      return response(data);
    }));
    render(<Reader reference={{ ...reference, locator: { kind: 'pdf', physical_page: 2 } }}
      position={invalid as ContentLocator} onPositionChange={positions} />);
    await screen.findByText('SYNTHETIC page 2');
    expect(pages).toEqual([2]);
    await waitFor(() => expect(positions).toHaveBeenLastCalledWith({ kind: 'pdf', physical_page: 2 }));
  });

  it.each(['pdf', 'image'] as const)('restores a Workspace %s position and publishes canonical page changes', async kind => {
    stubBlobUrls();
    const positions = vi.fn();
    const pages: number[] = [];
    vi.stubGlobal('fetch', vi.fn(async (path: string, options: RequestInit) => {
      if (path.endsWith('/asset')) return pngResponse();
      const body = JSON.parse(String(options.body)); pages.push(body.page);
      const data = source('SYNTHETIC page ' + body.page);
      data.media_type = kind === 'pdf' ? 'application/pdf' : 'image/tiff'; data.original.filename = 'synthetic.' + kind;
      Object.assign(data.payload!, { kind, page: body.page, pages: 5, asset_id: 'page:' + body.page });
      return response(data);
    }));
    const position = (page: number): ContentLocator => kind === 'pdf' ? { kind, physical_page: page } : { kind, frame: page };
    const view = render(<Reader reference={reference} position={position(3)} onPositionChange={positions} />);
    await screen.findByRole('img', { name: 'Source page' });
    expect(pages).toEqual([3]);
    expect((screen.getByLabelText(kind === 'pdf' ? 'Physical page' : 'Image frame') as HTMLInputElement).value).toBe('3');
    expect(positions).toHaveBeenLastCalledWith(position(3));
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    await waitFor(() => expect(positions).toHaveBeenLastCalledWith(position(4)));
    expect(pages).toEqual([3, 4]);
    view.unmount();
    render(<Reader {...{ reference, position: positions.mock.lastCall![0], onPositionChange: positions }} />);
    await screen.findByRole('img', { name: 'Source page' });
    expect(pages).toEqual([3, 4, 4]);
  });

  it('restores a validated text item locally without repeating the scroll on callback echo', async () => {
    const data = source('SYNTHETIC first paragraph');
    const position: ContentLocator = { kind: 'text', item_ref: 'reader-v1:item:1', start: 10, end: 13 };
    data.payload!.blocks.push({ ...data.payload!.blocks[0], item_ref: position.item_ref,
      text: 'SYNTHETIC CKD second paragraph', locator: { ...position, start: 0, end: 29 } });
    vi.stubGlobal('fetch', vi.fn(async () => response(data)));
    const descriptor = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'scrollIntoView');
    const scroll = vi.fn();
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: scroll });
    try {
      const positions = vi.fn();
      const view = render(<Reader reference={reference} position={position} onPositionChange={positions} />);
      await screen.findByText('SYNTHETIC CKD second paragraph');
      expect(scroll).toHaveBeenCalledOnce();
      expect((scroll.mock.instances[0] as HTMLElement).dataset.readerBlock).toBe(position.item_ref);
      expect(positions).toHaveBeenLastCalledWith(position);
      view.rerender(<Reader reference={reference} position={position} onPositionChange={value => positions(value)} />);
      expect(scroll).toHaveBeenCalledOnce();
      expect(positions).toHaveBeenCalledOnce();
    } finally {
      if (descriptor) Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', descriptor);
      else delete (HTMLElement.prototype as unknown as Record<string, unknown>).scrollIntoView;
    }
  });
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
