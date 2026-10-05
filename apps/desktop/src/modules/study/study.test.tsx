// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { NavigationProvider } from '../../shell/navigation';
import Study from './index';

const activity = { id: 'study_synthetic_review', topic_id: 'T03', title: 'Review electrolyte disorders',
  due_date: '2026-10-06', state: 'planned', duration_minutes: 20, kind: 'mistake-review',
  manual_override: false, reason: { description: 'Synthetic committed-mistake scheduling fixture.', question_id: 'synthetic-question' } };
const otherActivity = { ...activity, id: 'study_synthetic_transplant', topic_id: 'T21', title: 'Study transplantation', kind: 'topic-study' };
const goals = { hours_per_week: 3, exam_date: null, topic_ids: [], track: 'general' };
const home = { resume: [{ id: 'synthetic-thread', title: 'Synthetic study discussion', updated_at: '2026-10-04T23:00:00Z' }],
  review: [activity], upcoming: [activity, otherActivity], goals,
  topics: [{ id: 'T03', title: 'Electrolyte disorders' }, { id: 'T21', title: 'Kidney transplantation' }],
  progress: { groups: { fresh: { answered: 1, correct: 0 } } }, updates: [] };
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
const request = vi.fn<typeof fetch>();
const body = (init?: RequestInit) => JSON.parse(String(init?.body));
const mutationCalls = () => request.mock.calls.filter(([, init]) => init?.method && init.method !== 'GET');
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(done => { resolve = done; }); return { promise, resolve }; }
beforeEach(() => { window.history.replaceState(null, '', '#/study'); request.mockReset(); vi.stubGlobal('fetch', request); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function mount() { return render(<NavigationProvider><Study /></NavigationProvider>); }

describe('Today durable actions', () => {
  it('keeps the question, preferences draft and date focus mounted while a successful move refreshes home', async () => {
    const refresh = deferred<Response>();
    let homeReads = 0;
    request.mockImplementation(async (url, init) => {
      if (String(url) === '/api/v1/study/home') return ++homeReads === 1 ? json(home) : refresh.promise;
      if (String(url) === '/api/v1/study/plan/' + activity.id) return json({ ...activity, ...body(init), manual_override: true });
      throw new Error('Unexpected synthetic request: ' + url);
    });
    mount();
    const question = await screen.findByRole('textbox', { name: 'Your nephrology question' });
    fireEvent.change(question, { target: { value: 'Keep this ordinary learning draft.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Study preferences' }));
    const hours = screen.getByRole('spinbutton', { name: 'Hours per week' });
    fireEvent.change(hours, { target: { value: '7' } });
    const date = screen.getByLabelText('Move ' + activity.title);
    date.focus();
    fireEvent.change(date, { target: { value: '2026-10-12' } });
    await waitFor(() => expect(homeReads).toBe(2));
    expect(screen.getByRole('textbox', { name: 'Your nephrology question' })).toBe(question);
    expect((question as HTMLTextAreaElement).value).toBe('Keep this ordinary learning draft.');
    expect(screen.getByRole('spinbutton', { name: 'Hours per week' })).toBe(hours);
    expect((hours as HTMLInputElement).value).toBe('7');
    expect(document.activeElement).toBe(date);
    expect(screen.getByText('Synthetic study discussion')).toBeTruthy();
    await act(async () => refresh.resolve(json(home)));
    expect((screen.getByLabelText('Move ' + activity.title) as HTMLInputElement).value).toBe('2026-10-12');
  });

  it('serializes rapid date selections and saves the latest selection without replacing it with an older response', async () => {
    const first = deferred<Response>(), last = deferred<Response>();
    let writes = 0;
    request.mockImplementation(async (url, init) => {
      if (String(url) === '/api/v1/study/home') return json(home);
      if (String(url) === '/api/v1/study/plan/' + activity.id) return ++writes === 1 ? first.promise : last.promise;
      throw new Error('Unexpected synthetic request: ' + url);
    });
    mount();
    const date = await screen.findByLabelText('Move ' + activity.title);
    date.focus();
    fireEvent.change(date, { target: { value: '2026-10-12' } });
    fireEvent.change(date, { target: { value: '2026-10-13' } });
    fireEvent.change(date, { target: { value: '2026-10-14' } });
    expect(mutationCalls()).toHaveLength(1);
    expect((date as HTMLInputElement).value).toBe('2026-10-14');
    expect((within(date.closest('article')!).getByRole('button', { name: 'Mark done' }) as HTMLButtonElement).disabled).toBe(true);
    expect((within(screen.getByText(otherActivity.title).closest('article')!).getByRole('button', { name: 'Mark done' }) as HTMLButtonElement).disabled).toBe(false);
    await act(async () => first.resolve(json({ ...activity, due_date: '2026-10-12', manual_override: true })));
    await waitFor(() => expect(mutationCalls()).toHaveLength(2));
    expect(body(mutationCalls()[1][1])).toEqual({ due_date: '2026-10-14' });
    expect((date as HTMLInputElement).value).toBe('2026-10-14');
    await act(async () => last.resolve(json({ ...activity, due_date: '2026-10-14', manual_override: true })));
    await within(date.closest('article')!).findByText('Adjusted by you');
    expect(document.activeElement).toBe(date);
    expect((date as HTMLInputElement).value).toBe('2026-10-14');
  });

  it('keeps newer preferences edits when an older save completes, then deliberately saves the newer draft', async () => {
    const firstSave = deferred<Response>();
    let saves = 0;
    request.mockImplementation(async (url, init) => {
      if (String(url) === '/api/v1/study/home') return json(home);
      if (String(url) === '/api/v1/study/goals') return ++saves === 1 ? firstSave.promise : json(body(init));
      throw new Error('Unexpected synthetic request: ' + url);
    });
    mount();
    fireEvent.click(await screen.findByRole('button', { name: 'Study preferences' }));
    const hours = screen.getByRole('spinbutton', { name: 'Hours per week' });
    fireEvent.change(hours, { target: { value: '7' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save preferences' }));
    fireEvent.change(hours, { target: { value: '9' } });
    hours.focus();
    await act(async () => firstSave.resolve(json({ ...goals, hours_per_week: 7 })));
    expect(screen.getByRole('spinbutton', { name: 'Hours per week' })).toBe(hours);
    expect((hours as HTMLInputElement).value).toBe('9');
    expect(document.activeElement).toBe(hours);
    expect(screen.getByText('Your preferences are saved. Newer edits are still unsaved.')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Save preferences' }));
    await screen.findByText('Your study preferences are saved.');
    expect(mutationCalls().map(([, init]) => body(init).hours_per_week)).toEqual([7, 9]);
  });

  it.each([{ action: 'Skip', state: 'skipped' }, { action: 'Mark done', state: 'completed' }])
  ('retries the failed $action write and reflects only the confirmed activity state', async ({ action, state }) => {
    let writes = 0;
    request.mockImplementation(async (url, init) => {
      if (String(url) === '/api/v1/study/home') return json(home);
      if (String(url) === '/api/v1/study/plan/' + activity.id) return ++writes === 1
        ? json({ error: { code: 'synthetic_offline', message: 'Synthetic save failed.', retryable: true } }, 503)
        : json({ ...activity, ...body(init), manual_override: true });
      throw new Error('Unexpected synthetic request: ' + url);
    });
    mount();
    const row = (await screen.findByText(activity.title)).closest('article')!;
    fireEvent.click(within(row).getByRole('button', { name: action }));
    await within(row).findByText('This study change could not be confirmed');
    expect(within(row).queryByText(state)).toBeNull();
    fireEvent.click(within(row).getByRole('button', { name: 'Try again' }));
    await within(row).findByText(state);
    expect(mutationCalls().map(([, init]) => body(init))).toEqual([{ state }, { state }]);
    expect(within(row).getByText('Adjusted by you')).toBeTruthy();
  });

  it('retains the latest queued date after failure and retries that date explicitly', async () => {
    const first = deferred<Response>();
    let writes = 0;
    request.mockImplementation(async (url, init) => {
      if (String(url) === '/api/v1/study/home') return json(home);
      if (String(url) === '/api/v1/study/plan/' + activity.id) return ++writes === 1 ? first.promise : json({ ...activity, ...body(init), manual_override: true });
      throw new Error('Unexpected synthetic request: ' + url);
    });
    mount();
    const date = await screen.findByLabelText('Move ' + activity.title);
    fireEvent.change(date, { target: { value: '2026-10-12' } });
    fireEvent.change(date, { target: { value: '2026-10-14' } });
    await act(async () => first.resolve(json({ error: { code: 'synthetic_offline', message: 'Synthetic save failed.', retryable: true } }, 503)));
    await screen.findByText('This study change could not be confirmed');
    expect((date as HTMLInputElement).value).toBe('2026-10-14');
    expect(mutationCalls()).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await screen.findByText('Adjusted by you');
    expect(mutationCalls().map(([, init]) => body(init))).toEqual([{ due_date: '2026-10-12' }, { due_date: '2026-10-14' }]);
  });

  it('retries failed preferences with the retained hours, exam date, track and topic selection', async () => {
    let saves = 0;
    request.mockImplementation(async (url, init) => {
      if (String(url) === '/api/v1/study/home') return json(home);
      if (String(url) === '/api/v1/study/goals') return ++saves === 1
        ? json({ error: { code: 'synthetic_offline', message: 'Synthetic preferences failed.', retryable: true } }, 503) : json(body(init));
      throw new Error('Unexpected synthetic request: ' + url);
    });
    mount();
    fireEvent.click(await screen.findByRole('button', { name: 'Study preferences' }));
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Hours per week' }), { target: { value: '7' } });
    fireEvent.change(screen.getByLabelText('Exam date (optional)'), { target: { value: '2027-03-01' } });
    fireEvent.change(screen.getByRole('combobox', { name: 'Track' }), { target: { value: 'eseneph' } });
    fireEvent.click(screen.getByRole('checkbox', { name: 'Kidney transplantation' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save preferences' }));
    await screen.findByText('Your preferences could not be confirmed');
    expect((screen.getByRole('spinbutton', { name: 'Hours per week' }) as HTMLInputElement).value).toBe('7');
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await screen.findByText('Your study preferences are saved.');
    const expected = { hours_per_week: 7, exam_date: '2027-03-01', track: 'eseneph', topic_ids: ['T21'] };
    expect(mutationCalls().map(([, init]) => body(init))).toEqual([expected, expected]);
  });

  it('retries a failed proposal and prevents manual writes while the replacement plan is pending', async () => {
    const proposed = deferred<Response>();
    let suggestions = 0;
    request.mockImplementation(async url => {
      if (String(url) === '/api/v1/study/home') return json(home);
      if (String(url) === '/api/v1/study/plan/propose') return ++suggestions === 1
        ? json({ error: { code: 'synthetic_offline', message: 'Synthetic proposal failed.', retryable: true } }, 503) : proposed.promise;
      throw new Error('Unexpected synthetic request: ' + url);
    });
    mount();
    fireEvent.click(await screen.findByRole('button', { name: 'Suggest a plan' }));
    await screen.findByText('The suggested plan could not be confirmed');
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(suggestions).toBe(2));
    expect((screen.getByLabelText('Move ' + activity.title) as HTMLInputElement).disabled).toBe(true);
    expect(screen.getAllByRole('button', { name: 'Skip' }).every(button => (button as HTMLButtonElement).disabled)).toBe(true);
    await act(async () => proposed.resolve(json({ activities: [{ ...activity, due_date: '2026-10-14', manual_override: true }], explanation: 'Synthetic manual override preserved.' })));
    await screen.findByText('Synthetic manual override preserved.');
    expect((screen.getByLabelText('Move ' + activity.title) as HTMLInputElement).value).toBe('2026-10-14');
    expect(mutationCalls()).toHaveLength(2);
  });

  it.each(['move', 'preferences', 'plan'])('aborts a pending %s on unmount and does not dispatch its queued or refresh work', async operation => {
    const pending = deferred<Response>();
    request.mockImplementation(async url => String(url) === '/api/v1/study/home' ? json(home) : pending.promise);
    const view = mount();
    await screen.findByRole('textbox', { name: 'Your nephrology question' });
    if (operation === 'move') {
      const date = screen.getByLabelText('Move ' + activity.title);
      fireEvent.change(date, { target: { value: '2026-10-12' } });
      fireEvent.change(date, { target: { value: '2026-10-14' } });
    } else if (operation === 'preferences') {
      fireEvent.click(screen.getByRole('button', { name: 'Study preferences' }));
      fireEvent.click(screen.getByRole('button', { name: 'Save preferences' }));
    } else fireEvent.click(screen.getByRole('button', { name: 'Suggest a plan' }));
    expect(mutationCalls()).toHaveLength(1);
    const signal = mutationCalls()[0][1]!.signal!;
    expect(signal.aborted).toBe(false);
    view.unmount();
    expect(signal.aborted).toBe(true);
    await act(async () => pending.resolve(json(operation === 'preferences' ? goals : operation === 'plan' ? { activities: [activity] } : { ...activity, due_date: '2026-10-12' })));
    expect(mutationCalls()).toHaveLength(1);
    expect(request.mock.calls.filter(([url]) => String(url) === '/api/v1/study/home')).toHaveLength(1);
  });

  it('retains an incomplete date draft without sending a malformed move', async () => {
    request.mockImplementation(async url => String(url) === '/api/v1/study/home' ? json(home) : json({ error: { code: 'unexpected', message: 'No mutation expected.' } }, 422));
    mount();
    const date = await screen.findByLabelText('Move ' + activity.title);
    date.focus();
    fireEvent.change(date, { target: { value: '' } });
    expect((date as HTMLInputElement).value).toBe('');
    expect(screen.getByText('Choose a complete date to move this activity.')).toBeTruthy();
    expect(document.activeElement).toBe(date);
    expect(mutationCalls()).toHaveLength(0);
  });

  it('retains confirmed activity and ordinary drafts through a failed home refresh, then retries that read', async () => {
    let homeReads = 0;
    request.mockImplementation(async (url, init) => {
      if (String(url) === '/api/v1/study/home') return ++homeReads === 2
        ? json({ error: { code: 'synthetic_offline', message: 'Synthetic refresh failed.', retryable: true } }, 503) : json(home);
      if (String(url) === '/api/v1/study/plan/' + activity.id) return json({ ...activity, ...body(init), manual_override: true });
      throw new Error('Unexpected synthetic request: ' + url);
    });
    mount();
    const question = await screen.findByRole('textbox', { name: 'Your nephrology question' });
    fireEvent.change(question, { target: { value: 'Retain my ordinary question.' } });
    fireEvent.change(screen.getByLabelText('Move ' + activity.title), { target: { value: '2026-10-14' } });
    await screen.findByText('Study records could not be refreshed');
    expect((screen.getByLabelText('Move ' + activity.title) as HTMLInputElement).value).toBe('2026-10-14');
    expect(screen.getByRole('textbox', { name: 'Your nephrology question' })).toBe(question);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(homeReads).toBe(3));
    expect((question as HTMLTextAreaElement).value).toBe('Retain my ordinary question.');
    expect(mutationCalls()).toHaveLength(1);
  });
});
