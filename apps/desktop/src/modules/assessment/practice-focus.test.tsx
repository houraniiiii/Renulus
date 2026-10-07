// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { NavigationProvider } from '../../shell/navigation';
import { GeneratedPractice } from './GeneratedPractice';
import type { PracticeSession } from './generated-types';

const initial: PracticeSession = {
  id: 'synthetic-practice', mode: 'generated', scope: { kind: 'study' }, retention: 'persistent', status: 'active',
  created_at: '2026-10-07T10:00:00Z', updated_at: '2026-10-07T10:00:00Z', item_count: 1, answered_count: 0,
  current_item: { id: 'synthetic-question', ordinal: 1, kind: 'single_best_answer', stem: 'Synthetic practice question',
    options: [{ id: 'a', text: 'Synthetic option A' }, { id: 'b', text: 'Synthetic option B' }], assisted: false },
  scores: { unassisted: { answered: 0, correct: 0, accuracy: null }, assisted: { answered: 0, correct: 0, accuracy: null } },
  source_verification: 'not-verified', topic_id: null,
};
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('retains keyboard orientation through pause, resume, review, end and return to request', async () => {
  let session = initial;
  const fetch = vi.fn(async (path: string) => {
    if (path.endsWith('/capabilities')) return json({ available: false, reason: 'Synthetic offline check.', live_provider_verified: false });
    if (path.endsWith('/sessions')) return json({ sessions: [session] });
    if (path.endsWith('/review')) return json({ session_id: session.id, feedback: [], scores: session.scores });
    if (path.endsWith('/pause')) session = { ...session, status: 'paused' };
    else if (path.endsWith('/resume')) session = { ...session, status: 'active' };
    else if (path.endsWith('/end')) session = { ...session, status: 'ended' };
    else if (!path.endsWith('/' + session.id)) throw new Error('Unexpected synthetic request: ' + path);
    return json(session);
  });
  vi.stubGlobal('fetch', fetch);
  window.history.replaceState(null, '', '#/assessment');
  render(<NavigationProvider><GeneratedPractice /></NavigationProvider>);
  fireEvent.click(await screen.findByRole('button', { name: 'Open session' }));
  const question = await screen.findByText('Synthetic practice question');
  await waitFor(() => expect(document.activeElement).toBe(question.closest('legend')));
  expect(screen.getByRole('radio', { name: 'Synthetic option A' })).toBeDefined();
  fireEvent.click(screen.getByRole('button', { name: 'Pause' }));
  await screen.findByRole('heading', { name: 'Practice paused' });
  expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Generated practice' }));
  fireEvent.click(screen.getByRole('button', { name: 'Resume practice' }));
  await waitFor(() => expect(document.activeElement?.tagName).toBe('LEGEND'));
  fireEvent.click(screen.getByRole('button', { name: 'Review committed answers' }));
  const review = await screen.findByRole('heading', { name: 'Committed answer review' });
  await waitFor(() => expect(document.activeElement).toBe(review));
  fireEvent.click(screen.getByRole('button', { name: 'End practice' }));
  await screen.findByText('This practice ended with 0 committed answers.');
  expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Generated practice' }));
  fireEvent.click(screen.getByRole('button', { name: 'Back to practice request' }));
  expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Generated practice' }));
  expect(fetch.mock.calls.some(([path]) => path.endsWith('/generate'))).toBe(false);
});
