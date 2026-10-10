// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useState } from 'react';
import NotesPanel from './NotesPanel';
import { NotesDraftProvider } from './NotesDrafts';
import type { Note } from './types';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
const note = (ordinal = 1, text = 'Synthetic saved text'): Note => ({ document_id: 'synthetic_note', revision_id: 'synthetic_revision_' + ordinal,
  ordinal, title: 'Synthetic note', text, updated_at: '2026-10-10T12:00:00Z', reference: { target: { type: 'library_revision', id: 'synthetic_revision_' + ordinal } } });
const receipt = { attempt_id: 'synthetic_attempt', item_id: 'synthetic_item', version_id: 'synthetic_version', draft_revision: 4, policy_revision: 2, kind: 'notes' as const };
function Harness({ onUse = vi.fn(), guarded = false }: { onUse?: (value: unknown) => Promise<void>; guarded?: boolean }) {
  const [open, setOpen] = useState(true);
  return <NotesDraftProvider><button onClick={() => setOpen(value => !value)}>Toggle notes</button>{open &&
    <NotesPanel onOpen={vi.fn()} onUse={onUse} studyHelpContext={guarded ? receipt : undefined} />}</NotesDraftProvider>;
}
function fill(title = 'Synthetic note', text = 'Synthetic private draft') {
  fireEvent.change(screen.getByRole('textbox', { name: 'Note title' }), { target: { value: title } });
  fireEvent.change(screen.getByRole('textbox', { name: 'Note' }), { target: { value: text } });
}
async function selectNote() {
  fireEvent.change(await screen.findByRole('combobox', { name: 'Open note' }), { target: { value: 'synthetic_note' } });
  await waitFor(() => expect((screen.getByRole('textbox', { name: 'Note' }) as HTMLTextAreaElement).value).toBe('Synthetic saved text'));
}
describe('saved notes editor', () => {
  it('keeps unsaved text across workspace remounts without sending or saving', async () => {
    const transport = vi.fn(async (_path: string, _options: RequestInit) => json({ items: [] })); vi.stubGlobal('fetch', transport);
    const onUse = vi.fn(); render(<Harness onUse={onUse} />);
    fill(); fireEvent.click(screen.getByRole('button', { name: 'Toggle notes' }));
    fireEvent.click(screen.getByRole('button', { name: 'Toggle notes' }));
    expect((screen.getByRole('textbox', { name: 'Note' }) as HTMLTextAreaElement).value).toBe('Synthetic private draft');
    expect((screen.getByRole('button', { name: 'Use note in chat' }) as HTMLButtonElement).disabled).toBe(true);
    expect(transport.mock.calls.every(([, options]) => !options || !(options as RequestInit).method)).toBe(true);
    expect(onUse).not.toHaveBeenCalled();
  });
  it('replays the exact saved command and Study receipt after a lost ACK and panel remount', async () => {
    const writes: RequestInit[] = []; let current: Note | undefined;
    vi.stubGlobal('fetch', vi.fn(async (path: string, options: RequestInit) => {
      if (options.method === 'POST') { writes.push(options); current = note(1, 'Synthetic private draft'); if (writes.length === 1) throw new Error('lost ACK'); return json(current); }
      return json(path.endsWith('/notes') ? { items: current ? [current] : [] } : current);
    }));
    render(<Harness guarded />); fill(); fireEvent.click(screen.getByRole('button', { name: 'Save note' }));
    await screen.findByRole('button', { name: 'Retry save' });
    fireEvent.click(screen.getByRole('button', { name: 'Toggle notes' })); fireEvent.click(screen.getByRole('button', { name: 'Toggle notes' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Retry save' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Use note in chat' }).hasAttribute('disabled')).toBe(false));
    expect(writes).toHaveLength(2); expect(writes[1].body).toBe(writes[0].body);
    expect(new Headers(writes[1].headers).get('Idempotency-Key')).toBe(new Headers(writes[0].headers).get('Idempotency-Key'));
    expect(JSON.parse(new Headers(writes[1].headers).get('X-Renulus-Study-Context')!)).toEqual(receipt);
  });
  it('pins the current revision on edit and passes only explicitly re-read saved text to chat', async () => {
    let current = note(); const writes: Record<string, unknown>[] = [], reads: string[] = [];
    vi.stubGlobal('fetch', vi.fn(async (path: string, options: RequestInit) => {
      if (options.method === 'PUT') { const body = JSON.parse(String(options.body)); writes.push(body); current = note(2, body.text); return json(current); }
      reads.push(path); return json(path.endsWith('/notes') ? { items: [current] } : current);
    }));
    const onUse = vi.fn(async (_value: unknown) => {}); render(<Harness onUse={onUse} />); await selectNote();
    fill('Synthetic note', 'Synthetic updated text'); fireEvent.click(screen.getByRole('button', { name: 'Save note' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Use note in chat' }).hasAttribute('disabled')).toBe(false));
    fireEvent.click(screen.getByRole('button', { name: 'Use note in chat' }));
    await waitFor(() => expect(onUse).toHaveBeenCalledOnce());
    expect(writes[0].expected_revision_id).toBe('synthetic_revision_1');
    expect(reads.some(path => path.endsWith('?revision_id=synthetic_revision_2'))).toBe(true);
    expect(onUse.mock.calls[0][0]).toEqual({ title: current.title, text: current.text, reference: current.reference });
  });
  it('retains a conflicting draft and requires explicit comparison before rebasing', async () => {
    let current = note(); const revisions: string[] = [];
    vi.stubGlobal('fetch', vi.fn(async (path: string, options: RequestInit) => {
      if (options.method === 'PUT') {
        const body = JSON.parse(String(options.body)); revisions.push(body.expected_revision_id);
        if (revisions.length === 1) { current = note(2, 'Synthetic concurrent edit'); return json({ error: { code: 'note_revision_conflict', message: 'A newer revision exists', retryable: true } }, 409); }
        current = note(3, body.text); return json(current);
      }
      return json(path.endsWith('/notes') ? { items: [current] } : current);
    }));
    render(<Harness />); await selectNote(); fill('Synthetic note', 'Synthetic retained edit'); fireEvent.click(screen.getByRole('button', { name: 'Save note' }));
    await screen.findByRole('heading', { name: 'Latest saved revision 2' });
    expect((screen.getByRole('textbox', { name: 'Note' }) as HTMLTextAreaElement).value).toBe('Synthetic retained edit');
    expect(screen.getByRole('button', { name: 'Save note' }).hasAttribute('disabled')).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Keep my edits after this revision' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save note' }));
    await waitFor(() => expect(revisions).toEqual(['synthetic_revision_1', 'synthetic_revision_2']));
  });
  it('hides retained saved content when its owner denies a later read', async () => {
    let denied = false;
    vi.stubGlobal('fetch', vi.fn(async (path: string) => {
      if (denied && !path.endsWith('/notes')) return json({ error: { code: 'note_denied', message: 'Access was revoked' } }, 403);
      return json(path.endsWith('/notes') ? { items: [note()] } : note());
    }));
    const onUse = vi.fn(async () => {}); render(<Harness onUse={onUse} />); await selectNote(); denied = true;
    fireEvent.click(screen.getByRole('button', { name: 'Use note in chat' }));
    await screen.findByText('This note is unavailable. Its saved contents are hidden until access is restored.');
    expect(screen.queryByRole('textbox', { name: 'Note' })).toBeNull(); expect(onUse).not.toHaveBeenCalled();
  });
  it('does not hand a late saved read to chat after its panel was closed', async () => {
    let finish!: (value: Response) => void;
    vi.stubGlobal('fetch', vi.fn(async (path: string) => path.includes('?revision_id=') ? new Promise<Response>(resolve => { finish = resolve; }) : json(path.endsWith('/notes') ? { items: [note()] } : note())));
    const onUse = vi.fn(async () => {}); render(<Harness onUse={onUse} />); await selectNote();
    fireEvent.click(screen.getByRole('button', { name: 'Use note in chat' })); fireEvent.click(screen.getByRole('button', { name: 'Toggle notes' }));
    await act(async () => finish(json(note()))); expect(onUse).not.toHaveBeenCalled();
  });
});
