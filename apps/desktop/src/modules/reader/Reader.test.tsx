// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
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

describe('inert connected reader transport', () => {
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
});
