// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { App } from './App';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); localStorage.clear(); });
it('preserves the actual Home draft through policy-only unmount and clears it on deliberate fresh navigation', async () => {
  let restricted = false, revision = 1;
  window.history.replaceState(null, '', '#/newchat');
  Object.defineProperty(HTMLElement.prototype, 'scrollTo', { configurable: true, value: vi.fn() });
  Object.defineProperty(document, 'scrollingElement', { configurable: true, value: document.documentElement });
  const json = (value: unknown) => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } });
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    if (path.endsWith('/assessment/policy')) return json({ revision, active_test_id: restricted ? 'synthetic_test' : null, assistance_allowed: !restricted });
    if (path.endsWith('/health')) return json({ status: 'ready' });
    if (path.includes('/home')) return json({ preferences: { doctor_name: null, revision: 1 }, suggestions: null, job: null, assistance_allowed: true });
    if (path.includes('/workspace/preferences')) return json({ width: 480, tabs: [] });
    return json({ items: [] });
  }));
  render(<App />);
  const composer = await screen.findByRole('textbox', { name: 'How can I help you today' });
  fireEvent.change(composer, { target: { value: 'Synthetic unsent policy draft' } });
  restricted = true; revision++; fireEvent(window, new Event('renulus:assessment-policy'));
  await screen.findByRole('button', { name: 'Resume Test' });
  expect(screen.queryByRole('textbox', { name: 'How can I help you today' })).toBeNull();
  restricted = false; revision++; fireEvent(window, new Event('renulus:assessment-policy'));
  await waitFor(() => expect((screen.getByRole('textbox', { name: 'How can I help you today' }) as HTMLTextAreaElement).value).toBe('Synthetic unsent policy draft'));
  expect(JSON.stringify(localStorage)).not.toContain('Synthetic unsent');
  fireEvent.click(screen.getByRole('link', { name: 'New chat' }));
  await waitFor(() => expect((screen.getByRole('textbox', { name: 'How can I help you today' }) as HTMLTextAreaElement).value).toBe(''));
});
