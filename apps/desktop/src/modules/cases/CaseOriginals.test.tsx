// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CaseOriginals } from './CaseOriginals';
import type { CaseAttachment, CaseSession } from './types';

const bytes = 'Synthetic original bytes';
const attachment: CaseAttachment = { id: 'own original', filename: 'synthetic.pdf', title: 'Synthetic chart',
  media_type: 'application/pdf', bytes: bytes.length, sha256: 'a'.repeat(64), saved: true, original_available: true };
const session: CaseSession = { id: 'own case', kind: 'daily', title: 'Synthetic case', text: 'Synthetic learning',
  revision: 3, scope: { kind: 'saved-case', entity_id: 'own case' }, saved: true, dirty: false,
  saved_at: '2026-10-05', created_at: '2026-10-05', updated_at: '2026-10-05', active_run_id: null,
  messages: [], teaching: null, attachments: [attachment] };
const createObjectURL = vi.fn(() => 'blob:synthetic-case-original');
const revokeObjectURL = vi.fn();
beforeEach(() => {
  createObjectURL.mockClear(); revokeObjectURL.mockClear();
  vi.stubGlobal('URL', class extends URL {
    static createObjectURL = createObjectURL;
    static revokeObjectURL = revokeObjectURL;
  });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('case originals with explicit retention', () => {
  it('lists saved and temporary metadata without fetching bytes, and removes only the chosen ID', () => {
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
    const remove = vi.fn();
    render(<CaseOriginals session={{ ...session, attachments: [attachment,
      { ...attachment, id: 'new-image', filename: 'synthetic.png', title: 'Synthetic geometry', media_type: 'image/png', saved: false }] }} disabled={false} remove={remove} />);
    expect(screen.getByText('Saved')).toBeTruthy(); expect(screen.getByText('Temporary')).toBeTruthy();
    expect(screen.getByText(/Choose Save case or Save changes/)).toBeTruthy();
    expect(fetch).not.toHaveBeenCalled(); expect(createObjectURL).not.toHaveBeenCalled();
    fireEvent.click(within(screen.getByRole('listitem', { name: 'synthetic.png' })).getByRole('button', { name: 'Remove' }));
    expect(remove).toHaveBeenCalledExactlyOnceWith('new-image');
  });

  it.each([['application/pdf', 'synthetic.pdf'], ['image/png', 'synthetic.png'], ['image/jpeg', 'synthetic.jpg']])(
    'loads a %s original only on View using the authenticated no-store helper, then releases it', async (type, filename) => {
      const fetch = vi.fn<typeof globalThis.fetch>(async () => new Response(bytes, { headers: { 'Content-Type': type } }));
      vi.stubGlobal('fetch', fetch);
      const view = render(<CaseOriginals session={{ ...session, attachments: [{ ...attachment, media_type: type, filename }] }} disabled={false} remove={vi.fn()} />);
      expect(fetch).not.toHaveBeenCalled();
      fireEvent.click(screen.getByRole('button', { name: 'View original' }));
      if (type === 'application/pdf') expect((await screen.findByTitle('Original ' + filename)).getAttribute('src')).toBe('blob:synthetic-case-original');
      else expect((await screen.findByRole('img', { name: 'Original ' + filename })).getAttribute('src')).toBe('blob:synthetic-case-original');
      expect(fetch.mock.calls[0][0]).toBe('/api/v1/cases/sessions/own%20case/attachments/own%20original/original');
      expect(fetch.mock.calls[0][1]).toMatchObject({ credentials: 'same-origin', cache: 'no-store', redirect: 'error' });
      expect((fetch.mock.calls[0][1]!.headers as Headers).get('Authorization')).toBeNull();
      fireEvent.click(screen.getByRole('button', { name: 'Close original' }));
      expect(revokeObjectURL).toHaveBeenCalledExactlyOnceWith('blob:synthetic-case-original');
      view.unmount(); expect(revokeObjectURL).toHaveBeenCalledTimes(1);
    });

  it('explains an unavailable original and disables actions during case changes', () => {
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
    render(<CaseOriginals session={{ ...session, attachments: [{ ...attachment, original_available: false }] }} disabled remove={vi.fn()} />);
    expect(screen.getByText('The original is unavailable. Restore a full backup that includes originals.')).toBeTruthy();
    expect((screen.getByRole('button', { name: 'View original' }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole('button', { name: 'Remove' }) as HTMLButtonElement).disabled).toBe(true);
    expect(fetch).not.toHaveBeenCalled();
  });

  it('shows an actual API error and requires a deliberate retry of the same own original', async () => {
    const fetch = vi.fn<typeof globalThis.fetch>().mockResolvedValueOnce(new Response(JSON.stringify({ error: {
      code: 'case_original_not_found', message: 'Synthetic original is unavailable.', retryable: false,
    } }), { status: 404, headers: { 'Content-Type': 'application/json' } })).mockResolvedValueOnce(new Response(bytes, { headers: { 'Content-Type': 'application/pdf' } }));
    vi.stubGlobal('fetch', fetch); render(<CaseOriginals session={session} disabled={false} remove={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'View original' }));
    await screen.findByText('Synthetic original is unavailable.');
    expect(fetch).toHaveBeenCalledTimes(1); expect(createObjectURL).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await screen.findByTitle('Original synthetic.pdf'); expect(fetch).toHaveBeenCalledTimes(2);
  });

  it('rejects a response that does not match the original metadata', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>(async () => new Response('wrong bytes', { headers: { 'Content-Type': 'application/pdf' } })));
    render(<CaseOriginals session={session} disabled={false} remove={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'View original' }));
    await screen.findByText('The original does not match this case file. Close and reopen the case to refresh it.');
    expect(createObjectURL).not.toHaveBeenCalled(); expect(screen.queryByTitle('Original synthetic.pdf')).toBeNull();
  });

  it('aborts on Cancel and ignores late bytes without creating an object URL', async () => {
    let finish!: (response: Response) => void;
    const fetch = vi.fn<typeof globalThis.fetch>(() => new Promise<Response>(resolve => { finish = resolve; }));
    vi.stubGlobal('fetch', fetch); render(<CaseOriginals session={session} disabled={false} remove={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'View original' }));
    fireEvent.click(screen.getByRole('button', { name: 'Cancel loading' }));
    expect(fetch.mock.calls[0][1]!.signal!.aborted).toBe(true);
    expect(screen.getByText('Original loading cancelled.')).toBeTruthy();
    finish(new Response(bytes, { headers: { 'Content-Type': 'application/pdf' } }));
    await waitFor(() => expect((screen.getByRole('button', { name: 'View original' }) as HTMLButtonElement).disabled).toBe(false));
    expect(createObjectURL).not.toHaveBeenCalled();
  });

  it('releases object URLs on removal or case replacement and aborts loading on unmount', async () => {
    const fetch = vi.fn<typeof globalThis.fetch>(async () => new Response(bytes, { headers: { 'Content-Type': 'application/pdf' } }));
    vi.stubGlobal('fetch', fetch);
    const view = render(<CaseOriginals session={session} disabled={false} remove={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'View original' })); await screen.findByTitle('Original synthetic.pdf');
    view.rerender(<CaseOriginals session={{ ...session, id: 'another synthetic case' }} disabled={false} remove={vi.fn()} />);
    expect(revokeObjectURL).toHaveBeenCalledTimes(1); expect(screen.queryByTitle('Original synthetic.pdf')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'View original' })); await screen.findByTitle('Original synthetic.pdf');
    view.rerender(<CaseOriginals session={{ ...session, attachments: [] }} disabled={false} remove={vi.fn()} />);
    expect(revokeObjectURL).toHaveBeenCalledTimes(2);
    const pending = vi.fn<typeof globalThis.fetch>(() => new Promise<Response>(() => {})); vi.stubGlobal('fetch', pending);
    view.rerender(<CaseOriginals session={session} disabled={false} remove={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'View original' })); view.unmount();
    expect(pending.mock.calls[0][1]!.signal!.aborted).toBe(true);
  });
});
