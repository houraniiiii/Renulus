// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { LocalSearchResults } from './LocalSearchResults';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const response = (title: string) => new Response(JSON.stringify({ items: [{ key: title, group: 'files', title, snippet: title + ' snippet', reference: { target: { type: 'library_revision', id: title }, locator: { kind: 'pdf', physical_page: 2 } } }], next_cursor: null }), { headers: { 'Content-Type': 'application/json' } });

it('discards an older response and opens the exact current pinned source', async () => {
  const pending = new Map<string, (value: Response) => void>();
  vi.stubGlobal('fetch', vi.fn((url: string) => new Promise<Response>(resolve => { pending.set(new URL('http://localhost' + url).searchParams.get('q')!, resolve); })));
  const onSelect = vi.fn();
  const props = { query: 'old', permitted: true, policyRevision: 1, projects: [], onSelect };
  const view = render(<LocalSearchResults {...props} />);
  await waitFor(() => expect(pending.has('old')).toBe(true));
  view.rerender(<LocalSearchResults {...props} query="current" />);
  await waitFor(() => expect(pending.has('current')).toBe(true));
  await act(async () => pending.get('current')!(response('current')));
  fireEvent.click(await screen.findByRole('button', { name: /current snippet/ }));
  expect(onSelect.mock.calls[0][0].reference).toEqual({ target: { type: 'library_revision', id: 'current' }, locator: { kind: 'pdf', physical_page: 2 } });
  await act(async () => pending.get('old')!(response('old')));
  expect(screen.queryByText('old snippet')).toBeNull();
});

it('removes cached snippets immediately on Test and blocks late results', async () => {
  let resolve!: (response: Response) => void;
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(done => { resolve = done; })));
  const props = { query: 'dialysis', permitted: true, policyRevision: 1, projects: [], onSelect: vi.fn() };
  const view = render(<LocalSearchResults {...props} />);
  await waitFor(() => expect(resolve).toBeDefined());
  await act(async () => resolve(response('saved')));
  expect(await screen.findByText('saved snippet')).toBeDefined();
  view.rerender(<LocalSearchResults {...props} permitted={false} policyRevision={2} />);
  expect(screen.queryByText('saved snippet')).toBeNull();
  expect(screen.getByRole('status').textContent).toContain('during Test');
  expect(screen.queryByRole('button', { name: /saved snippet/ })).toBeNull();
});
