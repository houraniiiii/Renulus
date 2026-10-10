// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { NavigationProvider, destinationHash, savedHandoffFromHash, nextScope, routeFromHash, useNavigation } from './navigation';

afterEach(cleanup);
function Probe() {
  const nav = useNavigation();
  return <><span data-testid="scope">{nav.scope.kind}</span><span data-testid="payload">{nav.handoff?.text as string}</span><button onClick={() => nav.navigate('learn', { payload: { text: 'SYNTHETIC_CASE_SENTINEL' } })}>Handoff</button><button onClick={() => nav.navigate('cases')}>Cases</button><button onClick={nav.startFreshStudy}>End</button></>;
}
function AttachmentProbe() {
  const nav = useNavigation();
  return <><button onClick={() => nav.navigate('chat', { payload: {
    conversation: { type: 'learn_thread', id: 'synthetic_saved_chat' }, retention: 'saved',
    prefill: 'PRIVATE_SYNTHETIC_DRAFT', attachmentIntent: { file: new File(['synthetic'], 'PRIVATE_SYNTHETIC_NAME.md'), request_id: 'attachment-receipt' },
  } })}>Choose attachment</button><span data-testid="attachment">{nav.handoff?.attachmentIntent ? 'pending' : 'clear'}</span>
    <button onClick={() => nav.consumeIntent('attachmentIntent', 'different-receipt')}>Other receipt</button>
    <button onClick={() => nav.consumeIntent('attachmentIntent', 'attachment-receipt')}>Consume attachment</button></>;
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
  it('selects a saved C chat without inheriting a legacy temporary context', () => {
    const current = { kind: 'temporary-case' as const, entity_id: 'legacy_case' };
    expect(nextScope(current, 'chat', { payload: { conversation: { type: 'case', id: 'saved_case' }, retention: 'saved' } })).toEqual({ kind: 'saved-case', entity_id: 'saved_case' });
    expect(nextScope(current, 'chat', { payload: { conversation: { type: 'learn_thread', id: 'saved_learning' }, retention: 'saved' } })).toEqual({ kind: 'study' });
    expect(nextScope(current, 'chat', { payload: { conversation: { type: 'case', id: '../invalid' }, retention: 'saved' } })).toEqual(current);
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
  it('keeps actual File handoffs volatile and clears only the matching receipt', async () => {
    window.history.replaceState(null, '', '#/newchat'); window.localStorage.clear(); window.sessionStorage.clear();
    render(<NavigationProvider><AttachmentProbe /></NavigationProvider>);
    fireEvent.click(screen.getByText('Choose attachment'));
    await waitFor(() => expect(screen.getByTestId('attachment').textContent).toBe('pending'));
    expect(window.location.hash).toBe('#/chat/learn_thread/synthetic_saved_chat');
    expect(window.location.href).not.toContain('PRIVATE_SYNTHETIC');
    expect(JSON.stringify(window.history.state) ?? '').not.toContain('PRIVATE_SYNTHETIC');
    expect(window.localStorage.length).toBe(0); expect(window.sessionStorage.length).toBe(0);
    fireEvent.click(screen.getByText('Other receipt')); expect(screen.getByTestId('attachment').textContent).toBe('pending');
    fireEvent.click(screen.getByText('Consume attachment')); expect(screen.getByTestId('attachment').textContent).toBe('clear');
  });
});
