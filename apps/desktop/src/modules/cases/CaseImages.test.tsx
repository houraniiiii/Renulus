// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { NavigationProvider } from '../../shell/navigation';
import CasesPage from './index';
import type { AttachmentPreview, CaseSession } from './types';

const MODEL = 'gpt-6.1-sol';
const DATA = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a3ioAAAAASUVORK5CYII=';
const caseItem: CaseSession = { id: 'case_image_ui', kind: 'daily', title: 'Daily case', text: 'Synthetic learning',
  revision: 1, scope: { kind: 'temporary-case', entity_id: 'case_image_ui' }, saved: false, dirty: true,
  saved_at: null, created_at: '2026-10-05', updated_at: '2026-10-05', active_run_id: null, messages: [], teaching: null };
const preview: AttachmentPreview = { id: 'image_preview', case_id: caseItem.id, revision: 1, scope: caseItem.scope,
  mode: 'image', state: 'ready', filename: 'synthetic.png', title: 'Temporary image', text: '', ocr: {}, error: null,
  image: { media_type: 'image/png', data: DATA }, image_retained: false };
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const frame = (sequence: number, type: string, payload: unknown) => 'event: ' + type + '\ndata: ' + JSON.stringify({
  id: 'image_event_' + sequence, run_id: 'image_run_ui', sequence, type, payload }) + '\n\n';

function fixture({ supported = true, pause = false, reject = false, originalsSupported = true, keepReject = false } = {}) {
  let current = caseItem;
  let readerCancelled = false;
  const fetch = vi.fn((path: string, options: RequestInit) => {
    if (path.endsWith('/capabilities')) return Promise.resolve(json({
      inputs: { text: { supported: true }, pdf: { supported: false }, image: { supported: false } },
      extraction: { supported: false, max_bytes: 10 * 1024 * 1024, formats: [], scope: 'temporary-case' },
      originals: { supported: originalsSupported, max_bytes: 8 * 1024 * 1024, image_pixels: 16000000,
        formats: ['.png', '.jpg', '.jpeg'], scope: 'temporary-case' },
      image_interpretation: { supported, models: supported ? [MODEL] : [], provider: supported ? 'codex' : null,
        interpretation_verified: false, max_bytes: 8 * 1024 * 1024, image_pixels: 16000000,
        reason: supported ? null : 'Connect and select an approved image model in Connections.' },
      discussion: { adapter_installed: supported, scope: 'temporary-case' }, teaching: { content_installed: false },
      handoffs: {}, memory_capture: false }));
    if (path.endsWith('/saved') || path.endsWith('/teaching')) return Promise.resolve(json({ cases: [] }));
    if (path.endsWith('/sessions') && options.method === 'POST') return Promise.resolve(json(caseItem));
    if (path.endsWith('/save')) {
      current = { ...current, saved: true, dirty: false, saved_at: '2026-10-05', scope: { kind: 'saved-case', entity_id: caseItem.id },
        attachments: current.attachments?.map(attachment => ({ ...attachment, saved: true })) };
      return Promise.resolve(json(current));
    }
    if (path.endsWith('/keep')) {
      if (keepReject) return Promise.resolve(json({ error: { code: 'case_attachment_limit',
        message: 'A case can keep up to 16 originals totalling 32 MiB. Remove an attachment before adding another.', retryable: false } }, 413));
      current = { ...caseItem, revision: 2, attachments: [{ id: 'kept_image', filename: 'synthetic.png', title: 'Temporary image',
        media_type: 'image/png', bytes: 21, sha256: 'a'.repeat(64), saved: false, original_available: true }] };
      return Promise.resolve(json(current));
    }
    if (path.endsWith('/prepare') || path.endsWith('/extract')) {
      const mode = JSON.parse((options.headers as Headers).get('x-renulus-case-options')!).mode as AttachmentPreview['mode'];
      return Promise.resolve(json(path.endsWith('/prepare') ? { ...preview, mode, image: null, state: 'reading' } : { ...preview, mode }));
    }
    if (options.method === 'DELETE') return Promise.resolve(json({ state: 'cancelled' }));
    if (path.endsWith('/discuss-image')) {
      if (reject) return Promise.resolve(json({ error: { code: 'image_input_unsupported',
        message: 'The selected account changed. Review the image and check Connections.', retryable: true } }, 409));
      current = { ...caseItem, revision: pause ? 2 : 3, messages: pause ? [] : [
        { id: 'image-question', role: 'user', content: 'Synthetic image question', created_at: '2026-10-05' },
        { id: 'image-answer', role: 'assistant', content: 'Synthetic image response', created_at: '2026-10-05' }] };
      return Promise.resolve(new Response(new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(new TextEncoder().encode(frame(1, 'started', { revision: 2, scope: caseItem.scope }) +
            frame(2, 'answer.delta', { text: pause ? 'Synthetic partial image response' : 'Synthetic image response' })));
          if (!pause) { controller.enqueue(new TextEncoder().encode(frame(3, 'completed', { revision: 3 }))); controller.close(); }
        }, cancel() { readerCancelled = true; },
      }), { headers: { 'Content-Type': 'text/event-stream' } }));
    }
    if (path.endsWith('/cancel')) return Promise.resolve(json({ status: 'cancelled' }));
    if (path.endsWith('/' + caseItem.id)) return Promise.resolve(json(current));
    throw new Error('Unexpected synthetic Cases path: ' + path);
  });
  vi.stubGlobal('fetch', fetch);
  return { fetch, cancelled: () => readerCancelled };
}

async function startCase() {
  render(<NavigationProvider><CasesPage /></NavigationProvider>);
  fireEvent.change(screen.getByLabelText('What would you like to discuss?'), { target: { value: caseItem.text } });
  await waitFor(() => expect((screen.getByRole('button', { name: 'Start temporary case' }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: 'Start temporary case' }));
  await waitFor(() => expect(screen.getByLabelText('Use this file for')).toBeTruthy());
}
async function reviewImage() {
  await startCase();
  fireEvent.change(screen.getByLabelText('Use this file for'), { target: { value: 'image' } });
  fireEvent.change(screen.getByLabelText('Image to review before sending'), {
    target: { files: [new File(['synthetic image bytes'], 'synthetic.png', { type: 'image/png' })] } });
  await waitFor(() => expect(screen.getByAltText('Selected image for temporary case discussion')).toBeTruthy());
  fireEvent.change(screen.getByLabelText('Question about this image'), { target: { value: 'Synthetic image question' } });
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); window.history.replaceState(null, '', '#'); });

describe('actual Cases renderer image consumer', () => {
  it('keeps an original image and explicitly saves it with no model or extraction capability', async () => {
    const { fetch } = fixture({ supported: false });
    const store = vi.spyOn(Storage.prototype, 'setItem');
    await startCase();
    expect((screen.getByRole('option', { name: 'Keep original image' }) as HTMLOptionElement).disabled).toBe(false);
    expect((screen.getByRole('option', { name: 'Image discussion with selected subscription' }) as HTMLOptionElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Use this file for'), { target: { value: 'original' } });
    fireEvent.change(screen.getByLabelText('Image to keep in case'), {
      target: { files: [new File(['synthetic image bytes'], 'synthetic.png', { type: 'image/png' })] } });
    await screen.findByAltText('Selected image original');
    expect(screen.queryByLabelText('Selected account image model')).toBeNull();
    expect(screen.queryByLabelText('Question about this image')).toBeNull();
    expect(screen.queryByLabelText('Review extracted text')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Send image for discussion' })).toBeNull();
    const upload = fetch.mock.calls.find(([path]) => path.endsWith('/extract'))!;
    expect(JSON.parse((upload[1].headers as Headers).get('x-renulus-case-options')!)).toEqual({
      revision: 1, scope: caseItem.scope, title: 'Temporary image', mode: 'original',
    });
    expect(upload[1].body).toBeInstanceOf(Blob);
    expect(fetch.mock.calls.some(([path]) => path.endsWith('/keep') || path.endsWith('/save'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'Keep image in case' }));
    await screen.findByRole('region', { name: 'Case originals' });
    expect(JSON.parse(fetch.mock.calls.find(([path]) => path.endsWith('/keep'))![1].body as string)).toEqual({ revision: 1 });
    expect(fetch.mock.calls.some(([path]) => path.endsWith('/save'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'Save case' }));
    await screen.findByRole('button', { name: 'Saved' });
    expect(fetch.mock.calls.filter(([path]) => path.endsWith('/save'))).toHaveLength(1);
    expect(fetch.mock.calls.some(([path]) => path.endsWith('/apply') || path.endsWith('/discuss-image') || path.endsWith('/discuss') || path.endsWith('/original'))).toBe(false);
    expect(store).not.toHaveBeenCalled();
  });

  it('uses the original-image eight-MiB limit before preparing any upload', async () => {
    const { fetch } = fixture({ supported: false });
    await startCase();
    fireEvent.change(screen.getByLabelText('Use this file for'), { target: { value: 'original' } });
    const file = new File(['synthetic'], 'synthetic.png', { type: 'image/png' });
    Object.defineProperty(file, 'size', { value: 8 * 1024 * 1024 + 1 });
    fireEvent.change(screen.getByLabelText('Image to keep in case'), { target: { files: [file] } });
    await screen.findByText('Choose a PNG or JPEG image up to 8 MiB and 16 MP.');
    expect(fetch.mock.calls.some(([path]) => path.endsWith('/prepare') || path.endsWith('/extract'))).toBe(false);
  });

  it('keeps a rejected original review visible without replaying Keep or saving', async () => {
    const { fetch } = fixture({ supported: false, keepReject: true });
    await startCase();
    fireEvent.change(screen.getByLabelText('Use this file for'), { target: { value: 'original' } });
    fireEvent.change(screen.getByLabelText('Image to keep in case'), {
      target: { files: [new File(['synthetic image bytes'], 'synthetic.png', { type: 'image/png' })] } });
    await screen.findByAltText('Selected image original');
    fireEvent.click(screen.getByRole('button', { name: 'Keep image in case' }));
    await screen.findByText('A case can keep up to 16 originals totalling 32 MiB. Remove an attachment before adding another.');
    expect(screen.getByAltText('Selected image original')).toBeTruthy();
    expect(fetch.mock.calls.filter(([path]) => path.endsWith('/keep'))).toHaveLength(1);
    expect(fetch.mock.calls.some(([path]) => path.endsWith('/save') || path.endsWith('/discuss-image'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'Discard image' }));
    await waitFor(() => expect(screen.queryByAltText('Selected image original')).toBeNull());
    expect(fetch.mock.calls.some(([path, options]) => path.endsWith('/image_preview') && options.method === 'DELETE')).toBe(true);
  });

  it('does not offer original retention when its own capability is unavailable', async () => {
    const { fetch } = fixture({ originalsSupported: false });
    await startCase();
    expect((screen.getByRole('option', { name: 'Keep original image' }) as HTMLOptionElement).disabled).toBe(true);
    expect(fetch.mock.calls.some(([path]) => path.endsWith('/prepare'))).toBe(false);
  });

  it('reviews without inference, sends only explicitly with the selected model and explains explicit Save', async () => {
    const { fetch } = fixture();
    const store = vi.spyOn(Storage.prototype, 'setItem');
    await reviewImage();
    expect(screen.getByText(/Keeping an image does not send it to a model/)).toBeTruthy();
    expect((screen.getByAltText('Selected image for temporary case discussion') as HTMLImageElement).src).toBe('data:image/png;base64,' + DATA);
    expect(fetch.mock.calls.some(([path]) => path.endsWith('/discuss-image'))).toBe(false);
    expect((screen.getByLabelText('Selected account image model') as HTMLSelectElement).value).toBe(MODEL);
    fireEvent.click(screen.getByRole('button', { name: 'Send image for discussion' }));
    await waitFor(() => expect(screen.getByText('Synthetic image response')).toBeTruthy());
    const send = fetch.mock.calls.find(([path]) => path.endsWith('/discuss-image'))!;
    expect(send[0]).toContain('/attachments/image_preview/discuss-image');
    expect(JSON.parse(send[1].body as string)).toMatchObject({ revision: 1, model: MODEL, message: 'Synthetic image question' });
    expect(send[1].body).not.toContain(DATA);
    expect(fetch.mock.calls.some(([path]) => path.endsWith('/save'))).toBe(false);
    expect(store).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.queryByAltText('Selected image for temporary case discussion')).toBeNull());
  });

  it('keeps a ready image original with revision only and persists it only on explicit Save', async () => {
    const { fetch } = fixture();
    await reviewImage();
    fireEvent.click(screen.getByRole('button', { name: 'Keep image in case' }));
    await screen.findByRole('region', { name: 'Case originals' });
    expect(screen.getByRole('button', { name: 'View original' })).toBeTruthy();
    const keep = fetch.mock.calls.find(([path]) => path.endsWith('/keep'))!;
    expect(keep[0]).toBe('/api/v1/cases/attachments/image_preview/keep');
    expect(JSON.parse(keep[1].body as string)).toEqual({ revision: 1 });
    expect(fetch.mock.calls.some(([path]) => path.endsWith('/save') || path.endsWith('/discuss-image') || path.endsWith('/original'))).toBe(false);
    await waitFor(() => expect(screen.queryByAltText('Selected image for temporary case discussion')).toBeNull());
    fireEvent.click(screen.getByRole('button', { name: 'Save case' }));
    await screen.findByRole('button', { name: 'Saved' });
    expect(screen.getAllByText('Saved')).toHaveLength(2);
    expect(fetch.mock.calls.filter(([path]) => path.endsWith('/save'))).toHaveLength(1);
  });

  it('uses the normal real run cancellation route and clears the image preview', async () => {
    const state = fixture({ pause: true });
    await reviewImage();
    fireEvent.click(screen.getByRole('button', { name: 'Send image for discussion' }));
    await waitFor(() => expect(screen.getByText('Synthetic partial image response')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: 'Stop response' }));
    await waitFor(() => expect(state.fetch.mock.calls.some(([path]) => path.endsWith('/image_run_ui/cancel'))).toBe(true));
    await waitFor(() => expect(state.cancelled()).toBe(true));
    await waitFor(() => expect(screen.queryByAltText('Selected image for temporary case discussion')).toBeNull());
    expect(state.fetch.mock.calls.some(([path]) => path.endsWith('/save'))).toBe(false);
  });

  it('clears a pending image review when Save changes scope without changing revision', async () => {
    const { fetch } = fixture();
    await reviewImage();
    fireEvent.click(screen.getByRole('button', { name: 'Save case' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Saved' })).toBeTruthy());
    await waitFor(() => expect(screen.queryByAltText('Selected image for temporary case discussion')).toBeNull());
    await waitFor(() => expect(fetch.mock.calls.some(([path, options]) => path.endsWith('/image_preview') && options.method === 'DELETE')).toBe(true));
    expect(fetch.mock.calls.some(([path]) => path.endsWith('/discuss-image'))).toBe(false);
  });

  it('keeps a review visible when a changed account rejects Send before acceptance', async () => {
    const { fetch } = fixture({ reject: true });
    await reviewImage();
    fireEvent.click(screen.getByRole('button', { name: 'Send image for discussion' }));
    await waitFor(() => expect(screen.getByText('The selected account changed. Review the image and check Connections.')).toBeTruthy());
    expect(screen.getByAltText('Selected image for temporary case discussion')).toBeTruthy();
    expect(fetch.mock.calls.filter(([path]) => path.endsWith('/discuss-image'))).toHaveLength(1);
    expect(fetch.mock.calls.some(([path]) => path.endsWith('/save'))).toBe(false);
  });

  it('disables image discussion for an unverified account while explaining the limitation', async () => {
    const { fetch } = fixture({ supported: false });
    render(<NavigationProvider><CasesPage /></NavigationProvider>);
    fireEvent.change(screen.getByLabelText('What would you like to discuss?'), { target: { value: caseItem.text } });
    await waitFor(() => expect((screen.getByRole('button', { name: 'Start temporary case' }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole('button', { name: 'Start temporary case' }));
    await waitFor(() => expect(screen.getByText(/Image discussion is unavailable/)).toBeTruthy());
    expect((screen.getByRole('option', { name: 'Image discussion with selected subscription' }) as HTMLOptionElement).disabled).toBe(true);
    expect(fetch.mock.calls.some(([path]) => path.endsWith('/prepare') || path.endsWith('/discuss-image'))).toBe(false);
  });
});
