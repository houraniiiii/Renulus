// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import CasesPage from '../modules/cases';
import type { CaseSession } from '../modules/cases/types';
import { App } from './App';
import { useNavigation } from './navigation';

// Keep the real shell, navigation, Cases controls and HTTP/SSE transport. Other
// destinations expose their scope without loading unrelated module resources.
vi.mock('./ModuleOutlet', () => ({ ModuleOutlet: function Destination() {
  const nav = useNavigation();
  return <>
    <output data-testid="scope">{nav.scope.kind}:{nav.scope.entity_id ?? ''}</output>
    <output data-testid="handoff">{nav.handoff?.case_id as string ?? ''}</output>
    <button onClick={() => nav.navigate('learn', { scope: { kind: 'saved-case', entity_id: 'case_synthetic' } })}>Open saved scope</button>
    <button onClick={() => nav.navigate('learn', { scope: { kind: 'temporary-case', entity_id: 'case_synthetic' }, payload: { case_id: 'case_synthetic' } })}>Branch case</button>
    <button onClick={() => nav.navigate('learn', { scope: { kind: 'unclassified' } })}>Open unclassified scope</button>
    <button onClick={() => nav.navigate('assessment', { scope: { kind: 'study' } })}>Continue in Test</button>
    <button onClick={() => nav.navigate('cases', { payload: { case_id: nav.scope.entity_id } })}>Return to case</button>
    {nav.route === 'cases' && <CasesPage key={nav.revision} />}
  </>;
} }));

const SENTINEL = 'RENULUS_SYNTHETIC_SCOPE_BANNER_CASE';
const date = '2026-10-05T00:30:00+00:00';
const temporary: CaseSession = {
  id: 'case_synthetic', kind: 'daily', title: 'Synthetic scope case', text: SENTINEL,
  revision: 1, scope: { kind: 'temporary-case', entity_id: 'case_synthetic' },
  saved: false, dirty: true, saved_at: null, created_at: date, updated_at: date,
  active_run_id: null, messages: [], teaching: null,
};
const snapshot: CaseSession = { ...temporary, saved: true, dirty: false, saved_at: date,
  scope: { kind: 'saved-case', entity_id: temporary.id } };
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status,
  headers: { 'Content-Type': 'application/json' } });
const banner = () => document.querySelector('.scope-banner');
const temporaryLabel = 'Temporary case context · Only explicitly saved snapshots are kept. New changes require Save.';
const savedLabel = 'Saved case snapshot · New changes stay temporary until you Save again.';

function mockApi(savedFirst = false) {
  let live = savedFirst ? snapshot : temporary;
  let failSave = false;
  const fetch = vi.fn(async (path: string, options: RequestInit) => {
    if (path.endsWith('/health')) return json({ status: 'ok' });
    if (path.endsWith('/capabilities')) return json({
      inputs: { text: { supported: true }, pdf: { supported: false }, image: { supported: false } },
      discussion: { adapter_installed: true, scope: 'temporary-case' },
      teaching: { content_installed: false }, handoffs: { explain: 'guarded-reference' }, memory_capture: false,
    });
    if (path.endsWith('/teaching')) return json({ cases: [] });
    if (path.endsWith('/saved')) return json({ cases: live.saved ? [{ ...snapshot }] : [] });
    if (path.endsWith('/sessions') && options.method === 'POST') { live = temporary; return json(live, 201); }
    if (path.endsWith('/save')) {
      if (failSave) return json({ error: { code: 'case_save_failed', message: 'The synthetic save failed.', retryable: true } }, 503);
      live = { ...live, saved: true, dirty: false, saved_at: date, scope: snapshot.scope };
      return json(live);
    }
    if (path.endsWith('/discuss')) {
      live = { ...live, revision: live.revision + 1, dirty: true, scope: temporary.scope,
        messages: [{ id: 'synthetic_followup', role: 'user', content: 'New synthetic discussion', created_at: date }] };
      const frame = (sequence: number, type: string, payload: unknown) => 'event: ' + type + '\ndata: ' +
        JSON.stringify({ id: 'event_' + sequence, run_id: 'run_synthetic', sequence, type, payload }) + '\n\n';
      return new Response(frame(1, 'started', { revision: live.revision, scope: live.scope }) +
        frame(2, 'completed', {}), { headers: { 'Content-Type': 'text/event-stream' } });
    }
    if (path.endsWith('/handoff')) return json({ id: 'ticket_synthetic', case_handoff_id: 'ticket_synthetic',
      case_id: live.id, revision: live.revision, target: 'explain', expires_at: date,
      question: 'Explore the synthetic case', case_text: SENTINEL, scope: temporary.scope });
    if (path.endsWith('/' + temporary.id)) return json(live);
    throw new Error('Unexpected fixture request: ' + path);
  });
  vi.stubGlobal('fetch', fetch);
  return { fetch, failSave: (value: boolean) => { failSave = value; } };
}

beforeEach(() => { Object.defineProperty(HTMLElement.prototype, 'scrollTo', { configurable: true, value: vi.fn() }); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); Reflect.deleteProperty(HTMLElement.prototype, 'scrollTo'); window.history.replaceState(null, '', '#/study'); });

describe('shell scope banner and explicit case snapshots', () => {
  it('respects failed Save, reflects a saved snapshot and requires Save for later discussion', async () => {
    const fixture = mockApi();
    const storage = vi.spyOn(Storage.prototype, 'setItem');
    window.history.replaceState(null, '', '#/cases');
    render(<App />);
    expect(banner()?.textContent).toContain(temporaryLabel);
    fireEvent.change(screen.getByLabelText('What would you like to discuss?'), { target: { value: SENTINEL } });
    const start = screen.getByRole('button', { name: /Start temporary case/ }) as HTMLButtonElement;
    await waitFor(() => expect(start.disabled).toBe(false));
    fireEvent.click(start);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Save case' })).toBeTruthy());
    fixture.failSave(true);
    fireEvent.click(screen.getByRole('button', { name: 'Save case' }));
    await screen.findByText('The synthetic save failed.');
    expect(banner()?.textContent).toContain(temporaryLabel);
    expect(screen.queryByRole('button', { name: 'Saved' })).toBeNull();
    fixture.failSave(false);
    await waitFor(() => expect((screen.getByRole('button', { name: 'Save case' }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole('button', { name: 'Save case' }));
    await screen.findByRole('button', { name: 'Saved' });
    expect(screen.getByText('Saved snapshot · Further discussion stays temporary until you save again.')).toBeTruthy();
    expect(banner()?.textContent).toContain(temporaryLabel);
    expect(banner()?.textContent).not.toContain('not saved');
    expect(screen.getByTestId('scope').textContent).toBe('temporary-case:');
    fireEvent.change(screen.getByLabelText('Your learning question'), { target: { value: 'New synthetic discussion' } });
    fireEvent.click(screen.getByRole('button', { name: 'Discuss' }));
    await screen.findByRole('button', { name: 'Save changes' });
    expect(screen.getByText('Saved snapshot · You have temporary changes. Save again to keep them.')).toBeTruthy();
    expect(banner()?.textContent).toContain('New changes require Save.');
    expect(fixture.fetch.mock.calls.filter(([path]) => path.endsWith('/save'))).toHaveLength(2);
    await waitFor(() => expect((screen.getByRole('button', { name: 'Save changes' }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
    await screen.findByRole('button', { name: 'Saved' });
    const saveRequests = fixture.fetch.mock.calls.filter(([path]) => path.endsWith('/save'));
    expect(JSON.parse(saveRequests[2][1].body as string)).toEqual({ revision: 2 });
    expect(storage).not.toHaveBeenCalled();
    expect(window.location.href).not.toContain(SENTINEL);
  });

  it('keeps saved-case Learn and Test handoffs temporary and clears them on explicit End', async () => {
    const fixture = mockApi(true);
    window.history.replaceState(null, '', '#/cases');
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: /Synthetic scope case/ }));
    await screen.findByRole('button', { name: 'Saved' });
    fireEvent.change(screen.getByLabelText('Your learning question'), { target: { value: 'Explore the synthetic case' } });
    fireEvent.click(screen.getByRole('button', { name: 'Explore in Learn' }));
    await waitFor(() => expect(screen.getByTestId('scope').textContent).toBe('temporary-case:case_synthetic'));
    expect(screen.getByTestId('handoff').textContent).toBe(temporary.id);
    expect(banner()?.textContent).toContain(temporaryLabel);
    fireEvent.click(screen.getByRole('button', { name: 'Continue in Test' }));
    expect(screen.getByTestId('scope').textContent).toBe('temporary-case:case_synthetic');
    expect(banner()?.textContent).toContain(temporaryLabel);
    fireEvent.click(screen.getByRole('button', { name: 'End temporary context' }));
    expect(screen.getByTestId('scope').textContent).toBe('study:');
    expect(screen.getByTestId('handoff').textContent).toBe('');
    expect(banner()).toBeNull();
    expect(fixture.fetch.mock.calls.filter(([path]) => path.endsWith('/save'))).toHaveLength(0);
  });

  it('labels saved scope as a snapshot and still requires explicit Save for new changes', () => {
    mockApi();
    window.history.replaceState(null, '', '#/study');
    render(<App />);
    expect(banner()).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Open saved scope' }));
    expect(screen.getByTestId('scope').textContent).toBe('saved-case:case_synthetic');
    expect(banner()?.textContent).toContain(savedLabel);
    expect(document.querySelector('.workspace-footer')?.textContent).toContain('Temporary context');
    fireEvent.click(screen.getByRole('button', { name: 'Branch case' }));
    expect(screen.getByTestId('scope').textContent).toBe('temporary-case:case_synthetic');
    expect(banner()?.textContent).toContain(temporaryLabel);
    fireEvent.click(screen.getByRole('button', { name: 'End temporary context' }));
    expect(banner()).toBeNull();
    expect(screen.getByTestId('handoff').textContent).toBe('');
  });

  it('labels unclassified context separately and preserves its guard until explicit End', () => {
    mockApi();
    window.history.replaceState(null, '', '#/study');
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: 'Open unclassified scope' }));
    expect(banner()?.textContent).toContain('Unclassified context · not saved');
    fireEvent.click(screen.getByRole('button', { name: 'Continue in Test' }));
    expect(screen.getByTestId('scope').textContent).toBe('unclassified:');
    expect(banner()?.textContent).toContain('Unclassified context · not saved');
    fireEvent.click(screen.getByRole('button', { name: 'End temporary context' }));
    expect(banner()).toBeNull();
    expect(screen.getByTestId('scope').textContent).toBe('study:');
  });
});
