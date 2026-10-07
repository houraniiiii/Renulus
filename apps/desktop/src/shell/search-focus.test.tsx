// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { App } from './App';

vi.mock('./ModuleOutlet', () => ({ ModuleOutlet: () => <input aria-label="Study draft" /> }));
const modal = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'showModal');
const close = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'close');
const scrollingElement = Object.getOwnPropertyDescriptor(document, 'scrollingElement');
beforeEach(() => {
  window.history.replaceState(null, '', '#/study');
  Object.defineProperty(HTMLElement.prototype, 'scrollTo', { configurable: true, value: vi.fn() });
  Object.defineProperty(document, 'scrollingElement', { configurable: true, value: document.documentElement });
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: function(this: HTMLDialogElement) {
    this.open = true; this.querySelector<HTMLButtonElement>('button')?.focus();
  } });
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value: function(this: HTMLDialogElement) {
    this.open = false; this.dispatchEvent(new Event('close'));
  } });
});
afterEach(() => {
  cleanup(); vi.unstubAllGlobals(); Reflect.deleteProperty(HTMLElement.prototype, 'scrollTo');
  if (scrollingElement) Object.defineProperty(document, 'scrollingElement', scrollingElement);
  else Reflect.deleteProperty(document, 'scrollingElement');
  if (modal) Object.defineProperty(HTMLDialogElement.prototype, 'showModal', modal);
  else Reflect.deleteProperty(HTMLDialogElement.prototype, 'showModal');
  if (close) Object.defineProperty(HTMLDialogElement.prototype, 'close', close);
  else Reflect.deleteProperty(HTMLDialogElement.prototype, 'close');
});

it('focuses destination search on keyboard opening and reopening, returning focus on close', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ status: 'ok' }), { headers: { 'Content-Type': 'application/json' } })));
  render(<App />);
  const trigger = screen.getByRole('button', { name: /Find a destination/ }); trigger.focus();
  fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
  const input = screen.getByLabelText('Search destinations');
  expect(document.activeElement).toBe(input);
  fireEvent.change(input, { target: { value: 'Learn' } });
  expect(screen.getByRole('button', { name: 'Learn' })).toBeDefined();
  fireEvent.click(screen.getByLabelText('Close destination search'));
  expect(document.activeElement).toBe(screen.getByRole('button', { name: /Find a destination/ }));
  fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
  expect(document.activeElement).toBe(input);
  expect((input as HTMLInputElement).value).toBe('');
});

it('returns keyboard-opened search to the invoking field on dismissal', () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ status: 'ok' }))));
  render(<App />);
  const draft = screen.getByRole('textbox', { name: 'Study draft' }); draft.focus();
  fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
  fireEvent.click(screen.getByLabelText('Close destination search'));
  expect(document.activeElement).toBe(draft);
});

it.each(['Learn', 'Today'])('keeps focus in %s after a delayed native close event', async label => {
  let closeEvent!: () => void;
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value: function(this: HTMLDialogElement) {
    this.open = false; closeEvent = () => this.dispatchEvent(new Event('close'));
  } });
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ status: 'ok' }))));
  render(<App />);
  fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
  vi.mocked(document.documentElement.scrollTo).mockClear();
  fireEvent.click(screen.getByRole('button', { name: label }));
  await act(async () => closeEvent());
  expect(document.activeElement).toBe(screen.getByRole('main', { name: label }));
  expect(document.documentElement.scrollTo).toHaveBeenCalledWith({ top: 0, left: 0 });
});

it('moves through compact navigation and returns focus on Escape', () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ status: 'ok' }))));
  render(<App />);
  fireEvent.click(screen.getByRole('button', { name: 'Open navigation' }));
  expect(document.activeElement).toBe(screen.getByRole('link', { name: 'Today' }));
  fireEvent.keyDown(document.activeElement!, { key: 'Escape' });
  expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Open navigation' }));
  fireEvent.click(screen.getByRole('button', { name: 'Open navigation' }));
  fireEvent.click(screen.getByRole('link', { name: 'Today' }));
  expect(screen.getByRole('button', { name: 'Open navigation' }).getAttribute('aria-expanded')).toBe('false');
  expect(document.activeElement).toBe(screen.getByRole('main', { name: 'Today' }));
});

it('does not navigate or open another dialog over a case confirmation', () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ status: 'ok' }))));
  render(<App />);
  const confirmation = document.createElement('dialog'); confirmation.open = true; document.body.append(confirmation);
  try {
    fireEvent.keyDown(window, { key: '2', altKey: true });
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
    expect(screen.getByRole('main', { name: 'Today' })).toBeDefined();
    expect(document.querySelectorAll('dialog[open]')).toHaveLength(1);
  } finally { confirmation.remove(); }
});

it('retains modal keyboard focus when runtime health finishes in the background', async () => {
  let complete!: (value: Response) => void;
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(resolve => { complete = resolve; })));
  render(<App />);
  fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
  const input = screen.getByLabelText('Search destinations');
  expect(document.activeElement).toBe(input);
  fireEvent.change(input, { target: { value: 'Learn' } });
  const destination = screen.getByRole('button', { name: 'Learn' }); destination.focus();
  complete(new Response(JSON.stringify({ status: 'ok' }), { headers: { 'Content-Type': 'application/json' } }));
  await waitFor(() => expect(screen.getByText('Local runtime ready')).toBeDefined());
  expect(document.activeElement).toBe(destination);
  fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
  expect(document.activeElement).toBe(destination);
});
