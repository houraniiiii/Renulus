// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { NavigationProvider, destinationHash, savedHandoffFromHash, nextScope, routeFromHash, useNavigation } from './navigation';

afterEach(cleanup);
function Probe() {
  const nav = useNavigation();
  return <><span data-testid="scope">{nav.scope.kind}</span><span data-testid="payload">{nav.handoff?.text as string}</span><button onClick={() => nav.navigate('learn', { payload: { text: 'SYNTHETIC_CASE_SENTINEL' } })}>Handoff</button><button onClick={() => nav.navigate('cases')}>Cases</button><button onClick={nav.startFreshStudy}>End</button></>;
}
describe('navigation and retention boundary', () => {
  it('resolves all destination aliases and safe unknown routes', () => {
    expect(routeFromHash('#/learn')).toBe('learn'); expect(routeFromHash('#/test')).toBe('assessment'); expect(routeFromHash('#/home')).toBe('newchat'); expect(routeFromHash('#/unknown')).toBe('newchat');
  });
  it('round-trips only canonical saved identities without serialising private handoffs', () => {
    const conversation = { type: 'learn_thread', id: 'thread_original' };
    expect(savedHandoffFromHash(destinationHash('chat', { conversation, retention: 'saved', text: 'PRIVATE_DRAFT' }))).toEqual({ conversation, retention: 'saved' });
    expect(destinationHash('chat', { conversation, retention: 'temporary', text: 'PRIVATE_DRAFT' })).toBe('#/chat');
    expect(savedHandoffFromHash('#/chat/learn_thread/../secret')).toBeUndefined();
    expect(destinationHash('projects', { project_id: 'invalid/id' })).toBe('#/projects');
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
