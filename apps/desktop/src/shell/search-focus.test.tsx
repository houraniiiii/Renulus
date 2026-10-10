// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { App } from './App';
vi.mock('./ModuleOutlet', () => ({ ModuleOutlet: () => <input aria-label="Study draft" defaultValue="Kept draft" /> }));
const modal = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'showModal');
const close = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'close');
const json = (value: unknown) => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } });
const response = (path: string) => json(path.endsWith('/assessment/policy') ? { revision: 1, active_test_id: null, assistance_allowed: true } : path.endsWith('/health') ? { status: 'ready' } : { items: [] });
beforeEach(() => {
  window.history.replaceState(null, '', '#/study'); localStorage.clear();
  Object.defineProperty(HTMLElement.prototype, 'scrollTo', { configurable: true, value: vi.fn() });
  Object.defineProperty(document, 'scrollingElement', { configurable: true, value: document.documentElement });
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: function(this: HTMLDialogElement) { this.open = true; } });
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value: function(this: HTMLDialogElement) { this.open = false; this.dispatchEvent(new Event('close')); } });
  vi.stubGlobal('fetch', vi.fn(async (path: string) => response(path)));
});
afterEach(() => {
  cleanup(); vi.unstubAllGlobals(); localStorage.clear();
  Reflect.deleteProperty(HTMLElement.prototype, 'scrollTo');
  if (modal) Object.defineProperty(HTMLDialogElement.prototype, 'showModal', modal);
  else Reflect.deleteProperty(HTMLDialogElement.prototype, 'showModal');
  if (close) Object.defineProperty(HTMLDialogElement.prototype, 'close', close);
  else Reflect.deleteProperty(HTMLDialogElement.prototype, 'close');
});
it('returns keyboard-opened search to the invoking draft and preserves it on reopening', async () => {
  render(<App />);
  const draft = await screen.findByRole('textbox', { name: 'Study draft' }); draft.focus();
  fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
  const input = screen.getByLabelText('Search destinations'); expect(document.activeElement).toBe(input);
  fireEvent.change(input, { target: { value: 'Learn' } });
  fireEvent.click(screen.getByLabelText('Close destination search'));
  expect(document.activeElement).toBe(draft);
  fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
  expect(document.activeElement).toBe(input); expect((input as HTMLInputElement).value).toBe('');
  expect((draft as HTMLInputElement).value).toBe('Kept draft');
});
it('keeps focus in the destination after the native close event arrives late', async () => {
  let closeEvent!: () => void;
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value: function(this: HTMLDialogElement) { this.open = false; closeEvent = () => this.dispatchEvent(new Event('close')); } });
  render(<App />); await screen.findByRole('textbox', { name: 'Study draft' });
  fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
  fireEvent.click(screen.getByRole('button', { name: 'Learn' }));
  await act(async () => closeEvent());
  expect(document.activeElement).toBe(screen.getByRole('main', { name: 'Learn' }));
});
it('collapses navigation without remounting or losing the draft', async () => {
  render(<App />); const draft = await screen.findByRole('textbox', { name: 'Study draft' });
  fireEvent.change(draft, { target: { value: 'Synthetic revised draft' } });
  fireEvent.click(screen.getByRole('button', { name: 'Collapse navigation' }));
  expect(screen.getByRole('button', { name: 'Expand navigation' }).getAttribute('aria-expanded')).toBe('false');
  expect(screen.getByRole('textbox', { name: 'Study draft' })).toBe(draft);
  expect((draft as HTMLInputElement).value).toBe('Synthetic revised draft');
});
it('retains modal focus while asynchronous runtime health completes', async () => {
  let complete!: (value: Response) => void;
  vi.stubGlobal('fetch', vi.fn((path: string) => path.endsWith('/health') ? new Promise<Response>(resolve => { complete = resolve; }) : Promise.resolve(response(path))));
  render(<App />); await screen.findByRole('textbox', { name: 'Study draft' });
  fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
  const destination = screen.getByRole('button', { name: 'Learn' }); destination.focus();
  await act(async () => complete(json({ status: 'ready' })));
  await waitFor(() => expect(screen.getByLabelText('Local runtime ready')).toBeDefined());
  expect(document.activeElement).toBe(destination);
});
it('removes help surfaces and offers exact Test resume when policy changes', async () => {
  let restricted = false;
  vi.stubGlobal('fetch', vi.fn(async (path: string) => path.endsWith('/assessment/policy') && restricted ? json({ revision: 2, active_test_id: 'attempt_original', assistance_allowed: false }) : response(path)));
  render(<App />); await screen.findByRole('textbox', { name: 'Study draft' });
  restricted = true; fireEvent(window, new Event('renulus:assessment-policy'));
  await screen.findByRole('button', { name: 'Resume Test' });
  expect(screen.queryByRole('textbox', { name: 'Study draft' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Resume Test' }));
  await waitFor(() => expect(window.location.hash).toBe('#/attempts/attempt_original'));
});
