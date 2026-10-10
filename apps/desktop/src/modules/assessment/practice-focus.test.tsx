// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { NavigationProvider, useNavigation } from '../../shell/navigation';
import type { StudyHelpContext } from '../../platform/designC';
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

it('keeps the Study receipt on a lost-ack retry while cancellation stays neutral', async () => {
  const context: StudyHelpContext = { attempt_id: 'whole-study', item_id: 'whole-item', version_id: 'whole-version',
    draft_revision: 2, policy_revision: 7, kind: 'chat' };
  let calls = 0;
  const requests: { path: string; headers: Headers; body: string }[] = [];
  const fetch = vi.fn(async (path: string, options: RequestInit) => {
    requests.push({ path, headers: new Headers(options.headers), body: String(options.body ?? '') });
    if (path.endsWith('/capabilities')) return json({ available: true, live_provider_verified: false });
    if (path.endsWith('/sessions')) return json({ sessions: [] });
    if (path.endsWith('/cancel')) return json({ run_id: 'synthetic-run', cancelled: true });
    if (path.endsWith('/generate')) {
      calls += 1;
      if (calls === 1) throw new TypeError('Synthetic lost acknowledgement');
      const encoder = new TextEncoder();
      const body = new ReadableStream({ start(controller) {
        controller.enqueue(encoder.encode('data: ' + JSON.stringify({ sequence: 1, run_id: 'synthetic-run', type: 'started', payload: { mode: 'generated', persistent: true } }) + '\n\n'));
      } });
      return new Response(body, { headers: { 'Content-Type': 'text/event-stream' } });
    }
    throw new Error('Unexpected request ' + path);
  });
  vi.stubGlobal('fetch', fetch);
  function Handoff() {
    const nav = useNavigation();
    return nav.handoff?.studyHelpContext ? <GeneratedPractice />
      : <button onClick={() => nav.navigate('assessment', { payload: { studyHelpContext: context } })}>Open Study handoff</button>;
  }
  window.history.replaceState(null, '', '#/assessment');
  render(<NavigationProvider><Handoff /></NavigationProvider>);
  fireEvent.click(screen.getByText('Open Study handoff'));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Generate practice' }).hasAttribute('disabled')).toBe(true));
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Synthetic reasoning practice' } });
  await waitFor(() => expect(screen.getByRole('button', { name: 'Generate practice' }).hasAttribute('disabled')).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: 'Generate practice' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Reconnect same request' }));
  const cancel = await screen.findByRole('button', { name: 'Cancel generation' });
  await waitFor(() => expect(cancel.hasAttribute('disabled')).toBe(false));
  fireEvent.click(cancel);
  await screen.findByText('Generation cancelled. You can edit the request and explicitly generate again.');
  const generations = requests.filter(row => row.path.endsWith('/generate'));
  expect(generations).toHaveLength(2);
  expect(generations[0].body).toBe(generations[1].body);
  for (const row of requests.filter(row => !row.path.endsWith('/cancel'))) expect(JSON.parse(row.headers.get('X-Renulus-Study-Context')!)).toEqual(context);
  expect(generations[0].body).not.toContain('whole-study');
  expect(requests.find(row => row.path.endsWith('/cancel'))!.headers.has('X-Renulus-Study-Context')).toBe(false);
});

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
