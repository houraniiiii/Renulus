// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { WorkspacePanel, WorkspaceProvider, useWorkspace, type WorkspaceController } from '../modules/workspace';
import { useWorkspaceTitles } from './workspaceTitles';

vi.mock('./StudyHelp', () => ({ useStudyHelp: () => ({ context: undefined }) }));
const context = { identity: { type: 'learn_thread', id: 'synthetic-chat' }, retention: 'saved' } as const;
let workspace: WorkspaceController;
function Panel() { workspace = useWorkspace(); const getTitle = useWorkspaceTitles(); return <WorkspacePanel availableWidth={1200} getTitle={getTitle} />; }
const policy = { active_test_id: null, revision: 1, assistance_allowed: true };
const ref = (id: string) => ({ target: { type: 'library_revision' as const, id } });
const json = (value: unknown) => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('rehydrates distinct authorized titles and close names without saving titles; revocation removes them', async () => {
  let allowed = true;
  vi.stubGlobal('fetch', vi.fn(async () => json({ items: allowed ? [
    { target: ref('first').target, title: 'Dialysis source' }, { target: ref('second').target, title: 'Transplant source' },
  ] : [] })));
  const changes = vi.fn();
  render(<WorkspaceProvider context={context} policy={policy} onPreferencesChange={changes}
    initialPreferences={{ width: 480, tabs: ['first', 'second'].map(id => ({ content: ref(id), context: context.identity, retention: 'saved', position: null })) }}>
    <Panel /></WorkspaceProvider>);
  act(() => workspace.toggle());
  await screen.findByRole('tab', { name: 'Dialysis source' });
  expect(screen.getByRole('button', { name: 'Close Transplant source tab' })).toBeTruthy();
  expect(JSON.stringify(workspace.getPreferences())).not.toContain('source');
  act(() => workspace.setPreferredWidth(500));
  expect(JSON.stringify(changes.mock.calls)).not.toContain('Dialysis');
  allowed = false; fireEvent(window, new Event('renulus:records-changed'));
  await waitFor(() => expect(screen.queryByRole('tab', { name: 'Dialysis source' })).toBeNull());
  expect(screen.getByRole('button', { name: 'Close Document 2 tab' })).toBeTruthy();
});

it('disambiguates equal titles and discards a late response across a Test boundary', async () => {
  let finish!: (value: Response) => void;
  let pending = false;
  vi.stubGlobal('fetch', vi.fn(async () => pending ? new Promise<Response>(resolve => { finish = resolve; })
    : json({ items: ['first', 'second'].map(id => ({ target: ref(id).target, title: 'Same title' })) })));
  const build = (restricted = false) => <WorkspaceProvider context={context}
    policy={{ ...policy, revision: restricted ? 2 : 1, active_test_id: restricted ? 'test' : null, assistance_allowed: !restricted }}><Panel /></WorkspaceProvider>;
  const view = render(build());
  act(() => { workspace.open(ref('first')); workspace.open(ref('second')); });
  await screen.findByRole('tab', { name: 'Same title (1)' });
  expect(screen.getByRole('button', { name: 'Close Same title (2) tab' })).toBeTruthy();
  pending = true; fireEvent(window, new Event('renulus:records-changed'));
  await waitFor(() => expect(finish).toBeTypeOf('function'));
  view.rerender(build(true));
  await act(async () => finish(json({ items: [{ target: ref('first').target, title: 'LATE_PRIVATE_TITLE' }] })));
  expect(screen.queryByText('LATE_PRIVATE_TITLE')).toBeNull();
  expect(screen.getAllByRole('tab', { name: 'Saved tab' })).toHaveLength(2);
});
