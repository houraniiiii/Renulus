// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { AssessmentPolicy, ContentReference } from '../../platform/designC';
import { WorkspacePanel, WorkspaceProvider, useWorkspace, workspaceLayout, type WorkspaceAuthorizer, type WorkspaceController, type WorkspaceContext, type WorkspacePreferences, type WorkspaceReaderProps } from './index';

const saved: WorkspaceContext = { identity: { type: 'learn_thread', id: 'chat_synthetic' }, retention: 'saved' };
const temporary: WorkspaceContext = { identity: { type: 'case', id: 'TEMPORARY_SENTINEL' }, retention: 'temporary' };
const policy: AssessmentPolicy = { active_test_id: null, revision: 1, assistance_allowed: true };
const file = (id = 'revision_synthetic', page?: number): ContentReference => ({ target: { type: 'library_revision', id }, ...(page ? { locator: { kind: 'pdf', physical_page: page } as const } : {}) });
const allow = vi.fn<WorkspaceAuthorizer>(async () => ({ allowed: true as const }));
let controller: WorkspaceController;
function Probe() { controller = useWorkspace(); return null; }
function Reader(props: WorkspaceReaderProps) {
  return <div data-testid={'reader-' + props.reference.target.id}><p>Page {props.position?.kind === 'pdf' ? props.position.physical_page : 1}</p><label>Reader scratch<input defaultValue="" /></label><button onClick={() => props.onPositionChange({ kind: 'pdf', physical_page: 9 })}>Page nine</button></div>;
}
function mount(options: { context?: WorkspaceContext; policy?: AssessmentPolicy; preferences?: WorkspacePreferences; width?: number; authorize?: WorkspaceAuthorizer; change?: (snapshot: WorkspacePreferences) => void } = {}) {
  const build = (overrides: Partial<typeof options> = {}) => { const value = { ...options, ...overrides }; return <WorkspaceProvider context={value.context ?? saved} policy={value.policy ?? policy} initialPreferences={value.preferences} authorize={value.authorize ?? allow} onPreferencesChange={value.change}><Probe /><WorkspacePanel availableWidth={value.width ?? 1168} Reader={Reader} getTitle={reference => reference.target.id} /></WorkspaceProvider>; };
  const view = render(build()); return { ...view, update: (overrides: Partial<typeof options>) => view.rerender(build(overrides)) };
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); allow.mockClear(); });

describe('Workspace tabs and safe preference snapshots', () => {
  it('deduplicates canonical identity, jumps to a new locator and snapshots caller values', async () => {
    const change = vi.fn(); mount({ change }); const reference = file('revision_synthetic', 2);
    act(() => { controller.open(reference); reference.target.id = 'MUTATED_AFTER_OPEN'; });
    await screen.findByTestId('reader-revision_synthetic');
    act(() => controller.open(file('revision_synthetic', 6)));
    expect(controller.tabs).toHaveLength(1); expect(controller.tabs[0].position).toEqual({ kind: 'pdf', physical_page: 6 });
    expect(controller.getPreferences().tabs[0].context).toEqual(saved.identity);
    expect(JSON.stringify(change.mock.calls)).not.toContain('MUTATED_AFTER_OPEN');
    expect(controller.getPreferences().tabs[0]).not.toHaveProperty('title');
  });

  it('retains reader state/positions across tab switching, closing workspace and responsive transitions', async () => {
    const view = mount(); act(() => controller.open(file('first', 2))); await screen.findByTestId('reader-first');
    fireEvent.change(screen.getByLabelText('Reader scratch'), { target: { value: 'local selection' } });
    fireEvent.click(screen.getByText('Page nine'));
    act(() => controller.open(file('second'))); await screen.findByTestId('reader-second');
    act(() => controller.selectTab('library_revision:first'));
    expect((within(screen.getByTestId('reader-first')).getByLabelText('Reader scratch') as HTMLInputElement).value).toBe('local selection');
    expect(screen.getByTestId('reader-first').textContent).toContain('Page 9');
    view.update({ width: 568 }); expect(screen.getByRole('complementary').dataset.workspaceLayout).toBe('focused');
    expect(screen.getByRole('button', { name: 'Back to chat' })).toBeTruthy(); expect(screen.queryByRole('separator')).toBeNull();
    act(() => controller.close()); expect(screen.queryByRole('complementary')).toBeNull();
    act(() => controller.toggle()); await screen.findByTestId('reader-first'); expect(screen.getByTestId('reader-first').textContent).toContain('Page 9');
    expect(controller.tabs).toHaveLength(2);
  });

  it('isolates saved contexts, never emits temporary width/tabs/positions, and drops temporary state on leave', async () => {
    const change = vi.fn(); const view = mount({ change }); act(() => controller.open(file('saved_document', 3))); await screen.findByTestId('reader-saved_document');
    const before = change.mock.calls.length;
    view.update({ context: temporary });
    act(() => { controller.open({ target: { type: 'attachment', id: 'TEMPORARY_ATTACHMENT_SENTINEL' } }); controller.setPreferredWidth(600); });
    await waitFor(() => expect(controller.tabs).toHaveLength(1));
    act(() => controller.setPosition(controller.tabs[0].key, { kind: 'pdf', physical_page: 4 }));
    expect(change.mock.calls).toHaveLength(before);
    expect(JSON.stringify(controller.getPreferences())).not.toContain('TEMPORARY');
    expect(controller.getPreferences().width).toBe(480);
    view.update({ context: { identity: { type: 'project', id: 'project_second' }, retention: 'saved' } });
    expect(controller.tabs).toHaveLength(0);
    act(() => controller.open(file('saved_document', 8))); await screen.findByTestId('reader-saved_document');
    view.update({ context: saved }); expect(controller.tabs[0].position).toEqual({ kind: 'pdf', physical_page: 3 });
    view.update({ context: temporary }); expect(controller.tabs).toHaveLength(0);
  });

  it('restores only valid saved references, rejects paths/extras/test locators and reauthorizes restoration', async () => {
    const preferences = { width: Infinity, tabs: [null, { content: file('valid', 3), context: saved.identity, retention: 'saved', position: { kind: 'pdf', physical_page: 5 } }, { content: file('temporary'), context: temporary.identity, retention: 'temporary', position: null }, { content: { target: { type: 'attachment', id: 'C:/private/document.pdf' } }, context: saved.identity, retention: 'saved', position: null }, { content: file('with_title'), context: saved.identity, retention: 'saved', position: null, title: 'UNCLASSIFIED_TITLE' }] } as unknown as WorkspacePreferences;
    mount({ preferences }); expect(controller.tabs).toHaveLength(1); expect(controller.preferredWidth).toBe(480);
    act(() => controller.toggle()); await screen.findByTestId('reader-valid');
    expect(allow).toHaveBeenCalled(); expect(screen.getByTestId('reader-valid').textContent).toContain('Page 5');
    act(() => { expect(controller.open({ target: { type: 'saved_test_version', id: 'test_version' }, locator: { kind: 'pdf', physical_page: 1 } })).toBe('invalid_reference'); });
    expect(controller.tabs).toHaveLength(1);
  });

  it('ignores stale context callbacks rather than publishing into the next context', async () => {
    const view = mount(); const staleOpen = controller.open;
    view.update({ context: temporary }); act(() => expect(staleOpen(file('late_saved_reference'))).toBe('restricted'));
    expect(controller.tabs).toHaveLength(0); expect(controller.getPreferences().tabs).toHaveLength(0);
  });
});

describe('Workspace geometry and tab controls', () => {
  it('matches reconciled split/focused compositions and preserves preference under clamping', () => {
    expect(workspaceLayout(1168, 480)).toEqual({ mode: 'split', width: 480, maximum: 640 });
    expect(workspaceLayout(928, 480)).toEqual({ mode: 'split', width: 400, maximum: 400 });
    expect(workspaceLayout(568, 480)).toEqual({ mode: 'focused', width: 568, maximum: 568 });
    expect(workspaceLayout(648, 480).mode).toBe('focused');
    const view = mount({ width: 928 }); act(() => controller.toggle());
    expect(screen.getByRole('separator').getAttribute('aria-valuenow')).toBe('400'); expect(controller.preferredWidth).toBe(480);
    view.update({ width: 1168 }); expect(screen.getByRole('separator').getAttribute('aria-valuenow')).toBe('480');
  });

  it('keyboard splitter persists explicit changes, clamps bounds and restores default', () => {
    const change = vi.fn(); mount({ change }); act(() => controller.toggle()); const splitter = screen.getByRole('separator');
    fireEvent.keyDown(splitter, { key: 'ArrowLeft' }); expect(controller.preferredWidth).toBe(500);
    fireEvent.keyDown(splitter, { key: 'End' }); expect(controller.preferredWidth).toBe(640);
    fireEvent.keyDown(splitter, { key: 'ArrowLeft' }); expect(controller.preferredWidth).toBe(640);
    fireEvent.keyDown(splitter, { key: 'Home' }); expect(controller.preferredWidth).toBe(360);
    fireEvent.keyDown(splitter, { key: 'Enter' }); expect(controller.preferredWidth).toBe(480);
    expect(change.mock.calls.at(-1)?.[0].width).toBe(480);
  });

  it('pointer drag resizes from the starting width and stops on cancellation', () => {
    class Pointer extends MouseEvent { pointerId: number; constructor(type: string, init: MouseEventInit & { pointerId?: number } = {}) { super(type, init); this.pointerId = init.pointerId ?? 1; } }
    vi.stubGlobal('PointerEvent', Pointer);
    const capture = vi.fn();
    Object.defineProperty(HTMLElement.prototype, 'setPointerCapture', { configurable: true, value: capture });
    Object.defineProperty(HTMLElement.prototype, 'hasPointerCapture', { configurable: true, value: () => true });
    Object.defineProperty(HTMLElement.prototype, 'releasePointerCapture', { configurable: true, value: vi.fn() });
    try {
      mount(); act(() => controller.toggle()); const splitter = screen.getByRole('separator');
      fireEvent.pointerDown(splitter, { pointerId: 3, button: 0, clientX: 800 });
      fireEvent.pointerMove(splitter, { pointerId: 3, clientX: 740 }); expect(controller.preferredWidth).toBe(540);
      fireEvent.pointerCancel(splitter, { pointerId: 3 }); fireEvent.pointerMove(splitter, { pointerId: 3, clientX: 600 }); expect(controller.preferredWidth).toBe(540);
      expect(capture).toHaveBeenCalledWith(3);
    } finally { vi.unstubAllGlobals(); delete (HTMLElement.prototype as unknown as Record<string, unknown>).setPointerCapture; delete (HTMLElement.prototype as unknown as Record<string, unknown>).hasPointerCapture; delete (HTMLElement.prototype as unknown as Record<string, unknown>).releasePointerCapture; }
  });

  it('supports keyboard tab selection, reordering and close without duplicate identities', async () => {
    mount(); act(() => controller.open(file('first'))); await screen.findByTestId('reader-first'); act(() => controller.open(file('second'))); await screen.findByTestId('reader-second');
    fireEvent.keyDown(screen.getByRole('tab', { name: 'second' }), { key: 'ArrowLeft' }); expect(controller.selectedKey).toBe('library_revision:first');
    fireEvent.keyDown(screen.getByRole('tab', { name: 'first' }), { key: 'ArrowDown', altKey: true }); expect(controller.tabs.map(tab => tab.key)).toEqual(['library_revision:second', 'library_revision:first']);
    fireEvent.keyDown(screen.getByRole('tab', { name: 'first' }), { key: 'Delete' }); expect(controller.tabs).toHaveLength(1); expect(controller.selectedKey).toBe('library_revision:second');
  });
});

describe('Workspace policy and adapter boundary', () => {
  it('fails closed with no server access adapter and preserves the tab on actual denial', async () => {
    const deny = vi.fn(async () => ({ allowed: false as const, reason: 'not_found' as const }));
    render(<WorkspaceProvider context={saved} policy={policy}><Probe /><WorkspacePanel availableWidth={1168} Reader={Reader} /></WorkspaceProvider>);
    act(() => controller.open(file())); expect(screen.getByText('Content access is not connected')).toBeTruthy(); expect(screen.queryByTestId('reader-revision_synthetic')).toBeNull();
    cleanup(); render(<WorkspaceProvider context={saved} policy={policy} authorize={deny}><Probe /><WorkspacePanel availableWidth={1168} Reader={Reader} /></WorkspaceProvider>);
    act(() => controller.open(file())); await screen.findByText('Content unavailable'); expect(controller.tabs).toHaveLength(1); expect(screen.queryByTestId('reader-revision_synthetic')).toBeNull();
  });

  it('revokes in-flight access on Test policy change and never mounts a late response', async () => {
    let finish!: (value: { allowed: true }) => void; let signal!: AbortSignal;
    const pending = vi.fn<WorkspaceAuthorizer>((_request, requestSignal) => { signal = requestSignal; return new Promise<{ allowed: true }>(resolve => { finish = resolve; }); });
    const view = mount({ authorize: pending }); act(() => controller.open(file())); await waitFor(() => expect(pending).toHaveBeenCalled());
    view.update({ policy: { active_test_id: 'attempt_synthetic', revision: 2, assistance_allowed: false } });
    expect(signal.aborted).toBe(true); expect(screen.getByText('Active Test')).toBeTruthy();
    await act(async () => finish({ allowed: true })); expect(screen.queryByTestId('reader-revision_synthetic')).toBeNull();
    expect(controller.tabs).toHaveLength(1); act(() => expect(controller.open(file('denied_second'))).toBe('restricted')); expect(controller.tabs).toHaveLength(1);
  });

  it('uses real injected section/test-preview seams without reader/test coupling', async () => {
    const preview = vi.fn(() => <p>Injected saved-version preview</p>);
    const entry = vi.fn((props: { open: (reference: ContentReference) => unknown }) => <button onClick={() => props.open({ target: { type: 'saved_test_version', id: 'version_synthetic' } })}>Open producer reference</button>);
    render(<WorkspaceProvider context={saved} policy={policy} authorize={allow}><Probe /><WorkspacePanel availableWidth={1168} SavedTestPreview={preview} adapters={{ Sources: entry, Notes: entry, Goals: entry }} /></WorkspaceProvider>);
    act(() => { controller.toggle(); controller.showSection('Sources'); });
    fireEvent.click(await screen.findByText('Open producer reference')); await screen.findByText('Injected saved-version preview');
    expect(preview).toHaveBeenCalled(); expect(allow.mock.calls.some(([request]) => request.kind === 'section')).toBe(true);
    expect(controller.getPreferences().tabs[0].content.target).toEqual({ type: 'saved_test_version', id: 'version_synthetic' });
  });
});
