// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { App } from './App';

vi.mock('./ModuleOutlet', () => ({ ModuleOutlet: () => <input aria-label="Study draft" /> }));
const modal = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'showModal');
const close = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'close');
beforeEach(() => {
  window.history.replaceState(null, '', '#/study');
  Object.defineProperty(HTMLElement.prototype, 'scrollTo', { configurable: true, value: vi.fn() });
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: function(this: HTMLDialogElement) {
    this.open = true; this.querySelector<HTMLButtonElement>('button')?.focus();
  } });
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value: function(this: HTMLDialogElement) {
    this.open = false; this.dispatchEvent(new Event('close'));
  } });
});
afterEach(() => {
  cleanup(); vi.unstubAllGlobals(); Reflect.deleteProperty(HTMLElement.prototype, 'scrollTo');
  if (modal) Object.defineProperty(HTMLDialogElement.prototype, 'showModal', modal);
  else Reflect.deleteProperty(HTMLDialogElement.prototype, 'showModal');
  if (close) Object.defineProperty(HTMLDialogElement.prototype, 'close', close);
  else Reflect.deleteProperty(HTMLDialogElement.prototype, 'close');
});

it('focuses destination search on keyboard opening and reopening, returning focus on close', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ status: 'ok' }), { headers: { 'Content-Type': 'application/json' } })));
  render(<App />);
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
