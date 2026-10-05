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
