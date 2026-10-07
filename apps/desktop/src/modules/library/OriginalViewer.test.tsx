// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import OriginalViewer from './OriginalViewer';
import type { Citation } from './types';

const citation: Citation = { document_id: 'doc_synthetic', document_revision: 'rev_synthetic', title: 'Synthetic Office source', page: null, locators: [], original_url: '/library/revisions/rev_synthetic/original' };
const createObjectURL = vi.fn(() => 'blob:synthetic-original');
const revokeObjectURL = vi.fn();
beforeEach(() => {
  createObjectURL.mockClear(); revokeObjectURL.mockClear();
  vi.stubGlobal('URL', class extends URL {
    static createObjectURL = createObjectURL;
    static revokeObjectURL = revokeObjectURL;
  });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Office originals', () => {
  it.each([
    ['docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
    ['pptx', 'application/vnd.openxmlformats-officedocument.presentationml.presentation'],
    ['xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
  ])('offers the %s original for deliberate saving and releases its blob on close', async (extension, type) => {
    const request = vi.fn<typeof fetch>(async () => new Response('Synthetic original bytes', { headers: { 'Content-Type': type } }));
    vi.stubGlobal('fetch', request);
    const view = render(<OriginalViewer citation={citation} wholeOriginal={false} />);
    expect(request).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Open original' }));
    const download = await screen.findByRole('link', { name: 'Save original (.' + extension + ')' });
    expect(download.getAttribute('href')).toBe('blob:synthetic-original');
    expect(download.getAttribute('download')).toBe('renulus-original.' + extension);
    expect(screen.queryByTitle('Original document viewer')).toBeNull();
    expect(request.mock.calls[0][0]).toBe('/api/v1/library/revisions/rev_synthetic/original');
    view.unmount();
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:synthetic-original');
  });
});

describe('Image originals and recovery', () => {
  it.each([['image/png', 'png'], ['image/jpeg', 'jpg'], ['image/tiff', 'tiff']])('keeps %s originals usable with a save action', async (type, extension) => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>(async () => new Response('Synthetic image bytes', { headers: { 'Content-Type': type } })));
    render(<OriginalViewer citation={citation} wholeOriginal={false} />);
    fireEvent.click(screen.getByRole('button', { name: 'Open original' }));
    const save = await screen.findByRole('link', { name: 'Save original (.' + extension + ')' });
    expect(save.getAttribute('href')).toBe('blob:synthetic-original');
    expect(save.getAttribute('download')).toBe('renulus-original.' + extension);
    if (extension === 'tiff') {
      expect(screen.getByText('TIFF previews are unavailable here. Save the original to view it in an image viewer.')).toBeTruthy();
      expect(screen.queryByRole('img')).toBeNull();
    } else {
      fireEvent.error(await screen.findByRole('img', { name: 'Original imported document' }));
      expect(screen.getByRole('alert').textContent).toContain('Save the original');
      expect(screen.getByRole('link', { name: 'Save original (.' + extension + ')' })).toBeTruthy();
    }
    expect(screen.queryByTitle('Original document viewer')).toBeNull();
  });

  it('keeps an original load failure visible and retries the same pinned original', async () => {
    const request = vi.fn<typeof fetch>().mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: 'offline', message: 'Synthetic original unavailable.', retryable: true } }), { status: 503, headers: { 'Content-Type': 'application/json' } })).mockResolvedValueOnce(new Response('Synthetic original text.', { headers: { 'Content-Type': 'text/plain' } }));
    vi.stubGlobal('fetch', request); render(<OriginalViewer citation={citation} wholeOriginal={false} />);
    fireEvent.click(screen.getByRole('button', { name: 'Open original' }));
    await screen.findByText('Synthetic original unavailable.');
    expect(createObjectURL).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await screen.findByText('Synthetic original text.');
    expect(request.mock.calls.map(([url]) => url)).toEqual(['/api/v1/library/revisions/rev_synthetic/original', '/api/v1/library/revisions/rev_synthetic/original']);
  });

  it('does not display an empty original response as a successful viewer', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>(async () => new Response('', { headers: { 'Content-Type': 'application/pdf' } })));
    render(<OriginalViewer citation={citation} wholeOriginal={false} />);
    fireEvent.click(screen.getByRole('button', { name: 'Open original' }));
    await screen.findByText('The original response was empty. Try again to load the source.');
    expect(createObjectURL).not.toHaveBeenCalled(); expect(screen.queryByTitle('Original document viewer')).toBeNull();
  });
});
