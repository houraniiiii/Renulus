// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { CaseAttachments } from './CaseAttachments';
import type { AttachmentPreview, CaseCapabilities, CaseSession } from './types';

const SENTINEL = 'RENULUS_SYNTHETIC_ATTACHMENT_UI_NO_AUTOSAVE';
const session: CaseSession = { id: 'case_attachment', kind: 'daily', title: 'Synthetic case', text: 'A synthetic question',
  revision: 1, scope: { kind: 'saved-case', entity_id: 'case_attachment' }, saved: true, dirty: false,
  saved_at: '2026-10-04', created_at: '2026-10-04', updated_at: '2026-10-04', active_run_id: null, messages: [], teaching: null };
const capabilities: CaseCapabilities = { inputs: { text: { supported: true }, pdf: { supported: true }, image: { supported: true } },
  extraction: { supported: true, max_bytes: 10 * 1024 * 1024, max_pages: 20, image_pixels: 12000000,
    formats: ['.pdf', '.png', '.jpg', '.jpeg'], scope: 'temporary-case' },
  image_interpretation: { supported: false, code: 'image_input_unverified', reason: 'Text only' },
  discussion: { adapter_installed: false, scope: 'temporary-case' }, teaching: { content_installed: false },
  handoffs: { explain: 'guarded-reference', 'generated-practice': 'guarded-reference' }, memory_capture: false };
const job: AttachmentPreview = { id: 'extract_synthetic', case_id: session.id, revision: 1,
  scope: { kind: 'temporary-case', entity_id: session.id }, state: 'processing', filename: 'synthetic.pdf', title: 'Attachment text',
  text: '', ocr: {}, error: null };
const ready: AttachmentPreview = { ...job, state: 'ready', text: SENTINEL, ocr: { confidence: 0.65, used: true } };
const json = (value: unknown) => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } });
function fetchFixture(result: AttachmentPreview = ready) {
  const fetch = vi.fn((path: string, options: RequestInit) => Promise.resolve(json(
    options.method === 'DELETE' ? { id: job.id, state: 'cancelled' } : path.endsWith('/prepare') ? { ...job, state: 'reading' } : path.endsWith('/extract') ? job : result)));
  vi.stubGlobal('fetch', fetch);
  return fetch;
}
function selectFile() {
  fireEvent.change(screen.getByLabelText('PDF or image for text extraction'), {
    target: { files: [new File(['%PDF-1.7\n' + SENTINEL], 'synthetic.pdf', { type: 'application/pdf' })] },
  });
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('temporary attachment review', () => {
  it('keeps extraction unavailable when knowledge has not supplied its explicit safety capability', () => {
    const fetch = fetchFixture();
    render(<CaseAttachments session={session} disabled={false} apply={vi.fn()} capabilities={{ ...capabilities,
      extraction: { ...capabilities.extraction!, supported: false, reason: 'No-write proof is pending.' } }} />);
    expect(screen.queryByLabelText('PDF or image for text extraction')).toBeNull();
    expect(screen.getByText(/Temporary attachment extraction is unavailable in this installation/)).toBeTruthy();
    expect(fetch).not.toHaveBeenCalled();
  });

  it('sends a raw file under temporary scope and requires explicit reviewed-text apply', async () => {
    const fetch = fetchFixture();
    const apply = vi.fn(async () => ({ ...session, dirty: true }));
    const store = vi.spyOn(Storage.prototype, 'setItem');
    render(<CaseAttachments session={session} capabilities={capabilities} disabled={false} apply={apply} />);
    expect(screen.getByText(/Up to 20 PDF pages · Images up to 12 MP/)).toBeTruthy();
    selectFile();
    await waitFor(() => expect(screen.getByLabelText('Review extracted text')).toBeTruthy());
    const upload = fetch.mock.calls.find(([path]) => path.endsWith('/extract'))!;
    expect(upload[1].body).toBeInstanceOf(Blob);
    expect(upload[1].body).not.toBeInstanceOf(FormData);
    expect((upload[1].headers as Headers).get('x-renulus-preview-id')).toBe(job.id);
    expect(JSON.parse((upload[1].headers as Headers).get('x-renulus-case-options')!)).toEqual({
      revision: 1, scope: { kind: 'temporary-case', entity_id: session.id }, title: 'Attachment text',
    });
    expect(screen.getByText(/OCR confidence: 65%/)).toBeTruthy();
    expect(apply).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('Review extracted text'), { target: { value: SENTINEL + ' reviewed' } });
    fireEvent.click(screen.getByRole('button', { name: 'Use extracted text' }));
    await waitFor(() => expect(apply).toHaveBeenCalledWith(job.id, SENTINEL + ' reviewed'));
    expect(fetch.mock.calls.some(([path]) => path.endsWith('/save'))).toBe(false);
    expect(store).not.toHaveBeenCalled();
    expect(window.location.href).not.toContain(SENTINEL);
  });

  it('cancels the backend preview on unmount', async () => {
    const fetch = fetchFixture();
    const { unmount } = render(<CaseAttachments session={session} capabilities={capabilities} disabled={false} apply={vi.fn()} />);
    selectFile();
    await waitFor(() => expect(screen.getByLabelText('Review extracted text')).toBeTruthy());
    unmount();
    await waitFor(() => expect(fetch.mock.calls.some(([path, options]) => path.endsWith('/' + job.id) && options.method === 'DELETE')).toBe(true));
  });

  it('can stop before the raw upload response arrives using the reserved cancellation handle', async () => {
    let finishUpload!: (response: Response) => void;
    const fetch = vi.fn((path: string, options: RequestInit) => {
      if (path.endsWith('/prepare')) return Promise.resolve(json({ ...job, state: 'reading' }));
      if (path.endsWith('/extract')) return new Promise<Response>(resolve => { finishUpload = resolve; });
      return Promise.resolve(json({ id: job.id, state: 'cancelled' }));
    });
    vi.stubGlobal('fetch', fetch);
    render(<CaseAttachments session={session} capabilities={capabilities} disabled={false} apply={vi.fn()} />);
    selectFile();
    await waitFor(() => expect(fetch.mock.calls.some(([path]) => path.endsWith('/extract'))).toBe(true));
    fireEvent.click(screen.getByRole('button', { name: 'Stop extraction' }));
    await waitFor(() => expect(fetch.mock.calls.some(([path, options]) => path.endsWith('/' + job.id) && options.method === 'DELETE')).toBe(true));
    const upload = fetch.mock.calls.find(([path]) => path.endsWith('/extract'))!;
    expect(upload[1].signal!.aborted).toBe(true);
    finishUpload(json(ready));
    await waitFor(() => expect(screen.queryByLabelText('Review extracted text')).toBeNull());
    expect((screen.getByLabelText('PDF or image for text extraction') as HTMLInputElement).disabled).toBe(false);
    expect(fetch.mock.calls.some(([path]) => path.endsWith('/save'))).toBe(false);
  });

  it('explicitly discards the preview before another selection and never saves it', async () => {
    const fetch = fetchFixture();
    render(<CaseAttachments session={session} capabilities={capabilities} disabled={false} apply={vi.fn()} />);
    selectFile();
    await waitFor(() => expect(screen.getByLabelText('Review extracted text')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: 'Discard preview' }));
    await waitFor(() => expect(fetch.mock.calls.some(([path, options]) => path.endsWith('/' + job.id) && options.method === 'DELETE')).toBe(true));
    expect(screen.queryByLabelText('Review extracted text')).toBeNull();
    expect((screen.getByLabelText('PDF or image for text extraction') as HTMLInputElement).disabled).toBe(false);
    expect(fetch.mock.calls.some(([path]) => path.endsWith('/save'))).toBe(false);
  });

  it('rejects a late preview with a changed case revision or scope', async () => {
    const fetch = fetchFixture({ ...ready, revision: 99, scope: { kind: 'study' } });
    render(<CaseAttachments session={session} capabilities={capabilities} disabled={false} apply={vi.fn()} />);
    selectFile();
    await waitFor(() => expect(screen.getByText('The case changed before extraction finished. Select the file again.')).toBeTruthy());
    expect(screen.queryByLabelText('Review extracted text')).toBeNull();
    await waitFor(() => expect(fetch.mock.calls.some(([, options]) => options.method === 'DELETE')).toBe(true));
  });

  it('allows another file after a safe extraction failure and never previews the failed payload', async () => {
    const fetch = fetchFixture({ ...job, state: 'failed', error: {
      code: 'case_extraction_failed', message: 'The synthetic extractor could not read this file.', retryable: true,
    } });
    render(<CaseAttachments session={session} capabilities={capabilities} disabled={false} apply={vi.fn()} />);
    selectFile();
    await waitFor(() => expect(screen.getByText('The synthetic extractor could not read this file.')).toBeTruthy());
    expect(screen.queryByLabelText('Review extracted text')).toBeNull();
    selectFile();
    await waitFor(() => expect(fetch.mock.calls.filter(([path]) => path.endsWith('/extract'))).toHaveLength(2));
  });

  it('releases the file picker when the server cancels a preview', async () => {
    fetchFixture({ ...job, state: 'cancelled' });
    render(<CaseAttachments session={session} capabilities={capabilities} disabled={false} apply={vi.fn()} />);
    selectFile();
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Stop extraction' })).toBeNull());
    expect((screen.getByLabelText('PDF or image for text extraction') as HTMLInputElement).disabled).toBe(false);
    expect(screen.queryByLabelText('Review extracted text')).toBeNull();
  });
});
