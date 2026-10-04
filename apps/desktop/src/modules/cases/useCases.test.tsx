// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { NavigationProvider, useNavigation } from '../../shell/navigation';
import CasesPage from './index';
import { useCases } from './useCases';
import type { CaseHandoff, CaseSession } from './types';

const SENTINEL = 'RENULUS_SYNTHETIC_UI_CASE_NEVER_AUTOSAVE';
const now = '2026-10-04T19:45:00.000+00:00';
const temporary: CaseSession = {
  id: 'case_synthetic', kind: 'daily', title: 'Daily case', text: SENTINEL, revision: 1,
  scope: { kind: 'temporary-case', entity_id: 'case_synthetic' }, saved: false, dirty: true,
  saved_at: null, created_at: now, updated_at: now, active_run_id: null, messages: [], teaching: null,
};
const snapshot: CaseSession = { ...temporary, saved: true, dirty: false, saved_at: now,
  scope: { kind: 'saved-case', entity_id: temporary.id } };
const capabilities = { inputs: { text: { supported: true }, image: { supported: false }, pdf: { supported: false } },
  discussion: { adapter_installed: true, scope: 'temporary-case' }, teaching: { content_installed: false },
  handoffs: { explain: 'guarded-reference', 'generated-practice': 'guarded-reference' }, memory_capture: false };
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
function frame(sequence: number, type: string, payload: unknown) {
  return 'event: ' + type + '\ndata: ' + JSON.stringify({ id: 'event_' + sequence,
    run_id: 'case_run_synthetic', sequence, type, payload }) + '\n\n';
}

function mockApi(extra?: (path: string, options: RequestInit) => Response | Promise<Response> | undefined) {
  const fetch = vi.fn((path: string, options: RequestInit) => {
    const response = extra?.(path, options);
    if (response) return Promise.resolve(response);
    if (path.endsWith('/capabilities')) return Promise.resolve(json(capabilities));
    if (path.endsWith('/saved') || path.endsWith('/teaching')) return Promise.resolve(json({ cases: [] }));
    if (path.endsWith('/sessions') && options.method === 'POST') return Promise.resolve(json(temporary));
    if (path.endsWith('/save')) return Promise.resolve(json(snapshot));
    if (path.endsWith('/close')) return Promise.resolve(json({ id: temporary.id, closed: true, saved: true }));
    if (options.method === 'DELETE') return Promise.resolve(json({ id: temporary.id, deleted: true, purge_pending: false }));
    if (path.endsWith('/cancel')) return Promise.resolve(json({ status: 'cancelled' }));
    if (path.endsWith('/' + temporary.id)) return Promise.resolve(json(temporary));
    throw new Error('Unexpected fixture API path: ' + path);
  });
  vi.stubGlobal('fetch', fetch);
  return fetch;
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); window.history.replaceState(null, '', '#'); });

function HandoffHarness({ observe }: { observe: (payload: Record<string, unknown> | undefined) => void }) {
  const navigation = useNavigation();
  if (navigation.route === 'learn') {
    observe(navigation.handoff);
    return <button onClick={() => navigation.navigate('cases', { payload: { case_id: navigation.handoff?.case_id } })}>Return to Cases</button>;
  }
  return <CasesPage key={navigation.revision} />;
}

describe('cases UI retention and run guards', () => {
  it('calls Save only on explicit action and keeps all case data out of browser storage', async () => {
    const fetch = mockApi();
    const store = vi.spyOn(Storage.prototype, 'setItem');
    const { result } = renderHook(() => useCases());
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => { await result.current.start({ kind: 'daily', title: 'Daily case', text: SENTINEL }); });
    expect(result.current.session?.scope.kind).toBe('temporary-case');
    expect(fetch.mock.calls.filter(([path]) => path.endsWith('/save'))).toHaveLength(0);
    await act(async () => { await result.current.save(); });
    expect(result.current.session?.scope.kind).toBe('saved-case');
    const save = fetch.mock.calls.find(([path]) => path.endsWith('/save'))!;
    expect(JSON.parse(save[1].body as string)).toEqual({ revision: 1 });
    expect(store).not.toHaveBeenCalled();
    expect(window.location.href).not.toContain(SENTINEL);
  });

  it('ignores a late saved snapshot after the case is deleted', async () => {
    let resolveSave!: (response: Response) => void;
    mockApi(path => path.endsWith('/save') ? new Promise<Response>(resolve => { resolveSave = resolve; }) : undefined);
    const { result } = renderHook(() => useCases());
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => { await result.current.start({ kind: 'daily', title: 'Daily case', text: SENTINEL }); });
    let saving!: Promise<unknown>;
    act(() => { saving = result.current.save() as Promise<unknown>; });
    await act(async () => { await result.current.remove(); });
    expect(result.current.session).toBeNull();
    await act(async () => { resolveSave(json(snapshot)); await saving; });
    expect(result.current.session).toBeNull();
  });

  it('reads the SSE envelope and cancels the actual backend run on unmount', async () => {
    let readerCancelled = false;
    const response = new Response(new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(frame(1, 'started', {
          revision: 2, scope: temporary.scope,
        }) + frame(2, 'answer.delta', { text: 'Synthetic partial answer' })));
      },
      cancel() { readerCancelled = true; },
    }), { headers: { 'Content-Type': 'text/event-stream' } });
    const fetch = mockApi(path => path.endsWith('/discuss') ? response : undefined);
    const { result, unmount } = renderHook(() => useCases());
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => { await result.current.start({ kind: 'daily', title: 'Daily case', text: SENTINEL }); });
    let pending!: Promise<void>;
    act(() => { pending = result.current.send('A synthetic question'); });
    await waitFor(() => expect(result.current.partial).toBe('Synthetic partial answer'));
    expect(result.current.session?.revision).toBe(2);
    await act(async () => { await result.current.save(); });
    expect(fetch.mock.calls.filter(([path]) => path.endsWith('/save'))).toHaveLength(0);
    unmount();
    await pending;
    expect(readerCancelled).toBe(true);
    expect(fetch.mock.calls.some(([path, options]) => path.endsWith('/case_run_synthetic/cancel') && options.method === 'POST')).toBe(true);
  });

  it('uses real temporary and saved cues and clears a submitted draft before closing', async () => {
    const fetch = mockApi();
    render(<NavigationProvider><CasesPage /></NavigationProvider>);
    const start = screen.getByRole('button', { name: /Start temporary case/ }) as HTMLButtonElement;
    expect(start.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('What would you like to discuss?'), { target: { value: SENTINEL } });
    await waitFor(() => expect(start.disabled).toBe(false));
    fireEvent.click(start);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Save case' })).toBeTruthy());
    expect(screen.getByText('Temporary')).toBeTruthy();
    expect(fetch.mock.calls.some(([path]) => path.endsWith('/save'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'Save case' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Saved' })).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: 'Close case' }));
    await waitFor(() => expect(screen.getByLabelText('What would you like to discuss?')).toBeTruthy());
    expect((screen.getByLabelText('What would you like to discuss?') as HTMLTextAreaElement).value).toBe('');
  });

  it('retains the learning question if the runtime rejects it before accepting a run', async () => {
    mockApi(path => path.endsWith('/discuss') ? json({ error: {
      code: 'provider_unavailable', message: 'The approved connection is unavailable.', retryable: true,
    } }, 503) : undefined);
    render(<NavigationProvider><CasesPage /></NavigationProvider>);
    fireEvent.change(screen.getByLabelText('What would you like to discuss?'), { target: { value: SENTINEL } });
    await waitFor(() => expect((screen.getByRole('button', { name: /Start temporary case/ }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole('button', { name: /Start temporary case/ }));
    await waitFor(() => expect(screen.getByLabelText('Your learning question')).toBeTruthy());
    fireEvent.change(screen.getByLabelText('Your learning question'), { target: { value: 'An unsent synthetic question' } });
    fireEvent.click(screen.getByRole('button', { name: 'Discuss' }));
    await waitFor(() => expect(screen.getByText('The approved connection is unavailable.')).toBeTruthy());
    expect((screen.getByLabelText('Your learning question') as HTMLTextAreaElement).value).toBe('An unsent synthetic question');
  });

  it.each([false, true])('hands off and reopens a case in memory with explicit Save only (saved=%s)', async savedFirst => {
    const ticket: CaseHandoff = { id: 'handoff_synthetic', case_handoff_id: 'handoff_synthetic',
      case_id: temporary.id, revision: 1, target: 'explain', expires_at: now, question: 'Explain this synthetic case',
      case_text: SENTINEL, scope: { kind: 'temporary-case', entity_id: temporary.id } };
    const fetch = mockApi(path => path.endsWith('/handoff') ? json(ticket, 201) :
      path.endsWith('/' + temporary.id) ? json(savedFirst ? snapshot : temporary) : undefined);
    const store = vi.spyOn(Storage.prototype, 'setItem');
    const observe = vi.fn();
    window.history.replaceState(null, '', '#/cases');
    render(<NavigationProvider><HandoffHarness observe={observe} /></NavigationProvider>);
    fireEvent.change(screen.getByLabelText('What would you like to discuss?'), { target: { value: SENTINEL } });
    await waitFor(() => expect((screen.getByRole('button', { name: /Start temporary case/ }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole('button', { name: /Start temporary case/ }));
    await waitFor(() => expect(screen.getByLabelText('Your learning question')).toBeTruthy());
    if (savedFirst) {
      fireEvent.click(screen.getByRole('button', { name: 'Save case' }));
      await waitFor(() => expect(screen.getByRole('button', { name: 'Saved' })).toBeTruthy());
    }
    fireEvent.change(screen.getByLabelText('Your learning question'), { target: { value: ticket.question } });
    fireEvent.click(screen.getByRole('button', { name: 'Explore in Learn' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Return to Cases' })).toBeTruthy());
    expect(observe).toHaveBeenLastCalledWith(ticket);
    expect(window.location.hash).toBe('#/learn');
    expect(window.location.href).not.toContain(SENTINEL);
    fireEvent.click(screen.getByRole('button', { name: 'Return to Cases' }));
    await waitFor(() => expect(screen.getByText(SENTINEL)).toBeTruthy());
    const handoff = fetch.mock.calls.find(([path]) => path.endsWith('/handoff'))!;
    expect(JSON.parse(handoff[1].body as string)).toEqual({ revision: 1, target: 'explain', question: ticket.question });
    expect(fetch.mock.calls.filter(([path]) => path.endsWith('/save'))).toHaveLength(savedFirst ? 1 : 0);
    expect(store).not.toHaveBeenCalled();
  });

  it('cancels a late handoff after deletion instead of passing its payload to another module', async () => {
    let resolveTicket!: (response: Response) => void;
    const fetch = mockApi(path => path.endsWith('/handoff') ? new Promise<Response>(resolve => { resolveTicket = resolve; }) :
      path.endsWith('/handoffs/handoff_synthetic') ? json({ cancelled: true }) : undefined);
    const { result } = renderHook(() => useCases());
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => { await result.current.start({ kind: 'daily', title: 'Daily case', text: SENTINEL }); });
    let pending!: Promise<unknown>;
    act(() => { pending = result.current.handoff('A synthetic question'); });
    await act(async () => { await result.current.remove(); });
    let output: unknown;
    await act(async () => {
      resolveTicket(json({ id: 'handoff_synthetic', case_text: SENTINEL }));
      output = await pending;
    });
    expect(output).toBeUndefined();
    expect(result.current.session).toBeNull();
    expect(fetch.mock.calls.some(([path, options]) => path.endsWith('/handoffs/handoff_synthetic') && options.method === 'DELETE')).toBe(true);
  });
});
