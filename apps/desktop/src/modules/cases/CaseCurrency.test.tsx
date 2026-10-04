// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { NavigationProvider, useNavigation } from '../../shell/navigation';
import { CaseCurrencyNotice } from './CaseCurrency';
import CasesPage from './index';
import { useCases } from './useCases';
import type { CaseCurrency, CaseSession, TeachingView } from './types';

const SENTINEL = 'SYNTHETIC_PINNED_CASE_CURRENCY_NEVER_AUTOSAVE';
const currency: CaseCurrency = { kind: 'case', id: 'original-synthetic-case', version: 1, status: 'needs-re-review',
  needs_re_review: true, annotation_count: 1, truncated: false, annotations: [{ entry_id: 'synthetic-change',
    title: 'Synthetic cited-source correction', detected_at: '2026-10-04T18:00:00+00:00', state: 'needs-re-review', review_state: 'pending' }] };
const teaching: TeachingView = { id: currency.id!, version: 1, topic_id: 'transplantation', stage_count: 2, revealed_count: 1,
  debriefed: false, review: { status: 'assistant_reviewed' }, license: 'CC-BY-4.0', synthetic: true,
  stages: [{ id: 'stage-1', narrative: SENTINEL, prompts: ['A synthetic learning question'] }], currency };
const session: CaseSession = { id: 'synthetic-session', kind: 'teaching', title: 'Synthetic pinned teaching case', text: 'Synthetic summary',
  revision: 1, scope: { kind: 'temporary-case', entity_id: 'synthetic-session' }, saved: false, dirty: true, saved_at: null,
  created_at: '2026-10-04T18:00:00+00:00', updated_at: '2026-10-04T18:00:00+00:00', active_run_id: null, messages: [], teaching };
const clear = { ...currency, status: 'no-known-impact' as const, needs_re_review: false, annotations: [], annotation_count: 0 };
const json = (value: unknown) => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } });

function backend(extra?: (path: string, options: RequestInit) => Response | Promise<Response> | undefined) {
  const fetch = vi.fn((path: string, options: RequestInit) => {
    const response = extra?.(path, options);
    if (response) return Promise.resolve(response);
    if (path.endsWith('/capabilities')) return Promise.resolve(json({ inputs: { text: { supported: true } },
      discussion: { adapter_installed: false }, teaching: { content_installed: true }, handoffs: { explain: 'guarded-reference' } }));
    if (path.endsWith('/teaching')) return Promise.resolve(json({ cases: [{ id: teaching.id, version: 1, title: session.title,
      topic_id: teaching.topic_id, summary: session.text, currency }] }));
    if (path.endsWith('/saved')) return Promise.resolve(json({ cases: [] }));
    if (options.method === 'DELETE') return Promise.resolve(json({ id: session.id, deleted: true, purge_pending: false }));
    return Promise.resolve(json(session));
  });
  vi.stubGlobal('fetch', fetch);
  return fetch;
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); window.history.replaceState(null, '', '#'); });

describe('pinned teaching case source currency', () => {
  it.each(['needs-re-review', 'no-known-impact', 'unavailable'] as const)('shows %s without replacing the original content review', status => {
    const value = status === 'no-known-impact' ? clear : status === 'unavailable' ?
      { ...currency, status, needs_re_review: null, annotations: [], annotation_count: 0 } : currency;
    render(<CaseCurrencyNotice teaching={{ ...teaching, currency: value }} disabled={false} refreshing={false}
      onRefresh={vi.fn()} onUpdates={vi.fn()} />);
    expect(screen.getByText(/Pinned version 1/)).toBeTruthy();
    if (status === 'needs-re-review') {
      expect(screen.getByText('Needs re-review')).toBeTruthy();
      fireEvent.click(screen.getByText('Source notices (1)'));
      expect(screen.getByText('Synthetic cited-source correction')).toBeTruthy();
      expect(screen.getByText(/Source review pending/)).toBeTruthy();
    } else if (status === 'no-known-impact') {
      expect(screen.getByText('No recorded source impact')).toBeTruthy();
      expect(screen.getByText('This status does not establish that the case is current.')).toBeTruthy();
    } else expect(screen.getByText('Currency checks unavailable')).toBeTruthy();
    expect(screen.queryByText(SENTINEL)).toBeNull();
  });

  it('refreshes via GET while preserving pin, draft, stages and temporary scope without Save', async () => {
    const fetch = backend((path, options) => path.endsWith('/' + session.id) && options.method !== 'POST' ?
      json({ ...session, teaching: { ...teaching, currency: clear } }) : undefined);
    const store = vi.spyOn(Storage.prototype, 'setItem');
    window.history.replaceState(null, '', '#/cases');
    render(<NavigationProvider><CasesPage /></NavigationProvider>);
    await waitFor(() => expect(screen.getByRole('button', { name: /Synthetic pinned teaching case/ })).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: /Synthetic pinned teaching case/ }));
    await waitFor(() => expect(screen.getByText(SENTINEL)).toBeTruthy());
    fireEvent.change(screen.getByLabelText('Your learning question'), { target: { value: 'Keep this unsent question' } });
    fireEvent.click(screen.getByRole('button', { name: 'Refresh currency' }));
    const region = screen.getByRole('region', { name: 'Teaching case source currency' });
    await waitFor(() => expect(within(region).getByText('No recorded source impact')).toBeTruthy());
    expect(screen.getByText(SENTINEL)).toBeTruthy();
    expect(screen.getByText('Stage 1 of 2')).toBeTruthy();
    expect((screen.getByLabelText('Your learning question') as HTMLTextAreaElement).value).toBe('Keep this unsent question');
    expect(fetch.mock.calls.some(([path]) => path.endsWith('/save') || path.endsWith('/reveal'))).toBe(false);
    expect(store).not.toHaveBeenCalled();
    expect(window.location.href).not.toContain(SENTINEL);
  });

  it('keeps Open Updates and return in a volatile temporary branch with only the session reference', async () => {
    const fetch = backend();
    const observe = vi.fn();
    function Harness() {
      const navigation = useNavigation();
      if (navigation.route === 'updates') {
        observe(navigation.scope, navigation.handoff);
        return <button onClick={() => navigation.navigate('cases', { payload: { case_id: navigation.handoff?.case_id } })}>Return to case</button>;
      }
      return <CasesPage key={navigation.revision} />;
    }
    window.history.replaceState(null, '', '#/cases');
    render(<NavigationProvider><Harness /></NavigationProvider>);
    await waitFor(() => expect(screen.getByRole('button', { name: /Synthetic pinned teaching case/ })).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: /Synthetic pinned teaching case/ }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Open Updates' })).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: 'Open Updates' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Return to case' })).toBeTruthy());
    expect(observe).toHaveBeenLastCalledWith(expect.objectContaining({ kind: 'temporary-case' }), { case_id: session.id });
    expect(window.location.href).not.toContain(session.id);
    fireEvent.click(screen.getByRole('button', { name: 'Return to case' }));
    await waitFor(() => expect(screen.getByText(SENTINEL)).toBeTruthy());
    expect(fetch.mock.calls.some(([path]) => path.endsWith('/save'))).toBe(false);
  });

  it('does not republish a late currency refresh after deletion', async () => {
    let resolveRefresh!: (response: Response) => void;
    backend((path, options) => path.endsWith('/' + session.id) && options.method !== 'DELETE' ?
      new Promise<Response>(resolve => { resolveRefresh = resolve; }) : undefined);
    const { result } = renderHook(() => useCases());
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => { await result.current.start({ kind: 'teaching', teaching_case_id: teaching.id }); });
    let pending!: Promise<unknown>;
    act(() => { pending = result.current.refreshCurrency() as Promise<unknown>; });
    await act(async () => { await result.current.remove(); });
    await act(async () => { resolveRefresh(json(session)); await pending; });
    expect(result.current.session).toBeNull();
  });
});
