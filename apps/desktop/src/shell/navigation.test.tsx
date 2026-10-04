// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { NavigationProvider, nextScope, routeFromHash, useNavigation } from './navigation';

afterEach(cleanup);
function Probe() {
  const nav = useNavigation();
  return <><span data-testid="scope">{nav.scope.kind}</span><span data-testid="payload">{nav.handoff?.text as string}</span><button onClick={() => nav.navigate('learn', { payload: { text: 'SYNTHETIC_CASE_SENTINEL' } })}>Handoff</button><button onClick={() => nav.navigate('cases')}>Cases</button><button onClick={nav.startFreshStudy}>End</button></>;
}
describe('navigation and retention boundary', () => {
  it('resolves all destination aliases and safe unknown routes', () => {
    expect(routeFromHash('#/learn')).toBe('learn'); expect(routeFromHash('#/test')).toBe('assessment'); expect(routeFromHash('#/home')).toBe('study'); expect(routeFromHash('#/unknown')).toBe('study');
  });
  it('inherits temporary scope across Explain and Test even if a caller requests study', () => {
    expect(nextScope({ kind: 'study' }, 'cases')).toEqual({ kind: 'temporary-case' });
    for (const route of ['learn', 'assessment', 'library'] as const) expect(nextScope({ kind: 'temporary-case', entity_id: 'volatile-case' }, route, { scope: { kind: 'study' } })).toEqual({ kind: 'temporary-case', entity_id: 'volatile-case' });
    expect(nextScope({ kind: 'temporary-case' }, 'study', { freshStudy: true })).toEqual({ kind: 'study' });
  });
  it('keeps handoffs volatile and clears them on explicit end', async () => {
    window.location.hash = '#/study'; window.localStorage.clear(); window.sessionStorage.clear();
    render(<NavigationProvider><Probe /></NavigationProvider>);
    fireEvent.click(screen.getByText('Cases')); await waitFor(() => expect(screen.getByTestId('scope').textContent).toBe('temporary-case'));
    fireEvent.click(screen.getByText('Handoff')); await waitFor(() => expect(window.location.hash).toBe('#/learn'));
    expect(screen.getByTestId('payload').textContent).toBe('SYNTHETIC_CASE_SENTINEL');
    expect(window.location.href).not.toContain('SYNTHETIC_CASE_SENTINEL'); expect(JSON.stringify(window.history.state) ?? '').not.toContain('SYNTHETIC_CASE_SENTINEL');
    expect(window.localStorage.length).toBe(0); expect(window.sessionStorage.length).toBe(0);
    fireEvent.click(screen.getByText('End')); expect(screen.getByTestId('payload').textContent).toBe(''); expect(screen.getByTestId('scope').textContent).toBe('study');
  });
});
