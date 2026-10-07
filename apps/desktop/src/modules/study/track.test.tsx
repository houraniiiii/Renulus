// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { NavigationProvider, useNavigation } from '../../shell/navigation';
import Study from './index';

const goals = { hours_per_week: 4, exam_date: '2027-03-01', topic_ids: [], track: 'eseneph' };
const mapped = { id: 'study_mapped', topic_id: 'T03', title: 'Review electrolytes', due_date: '2026-10-05',
  state: 'planned', duration_minutes: 20, kind: 'mistake-review', manual_override: false, outside_selection: false,
  reason: { description: 'Your latest recorded answer was incorrect.', track: 'esen_eph', question_id: 'mapped-question' } };
const manual = { ...mapped, id: 'study_manual', topic_id: 'T21', title: 'Study transplantation',
  kind: 'topic-study', manual_override: true, outside_selection: true, reason: { description: 'Selected by you.', track: 'general_nephrology' } };
const metadata = [{ id: 'general_nephrology', title: 'General nephrology', available: true },
  { id: 'esen_eph', title: 'ESENeph preparation', available: true, status: 'partial', checked_on: '2026-10-05',
    available_questions: 12, format_compatible_questions: 8, exam_simulation_available: false,
    aligned_objective_ids: ['T03-objective'], supporting_objective_ids: ['T21-objective'],
    domains: [{ id: 'mapped-domain', label: 'Electrolytes', available_questions: 12, status: 'partial',
      alignments: [{ id: 'mapped-alignment', scope_note: 'Synthetic mapping scope.', gaps: ['Depth remains incomplete.'] }] },
    { id: 'gap-domain', label: 'Synthetic gap domain', available_questions: 0, status: 'gap', alignments: [] }] }];
const home = { resume: [], review: [mapped], upcoming: [mapped, manual], goals, tracks: metadata,
  selection: { track: 'esen_eph', title: 'ESENeph preparation', status: 'ready', message: null, topic_ids: ['T03'],
    objective_ids: { T03: ['T03-objective'] }, mapping_version: 'synthetic-2026-10-05' },
  topics: [{ id: 'T03', title: 'Electrolytes', objectives: [{ id: 'T03-objective', text: 'Synthetic electrolyte objective' }] },
    { id: 'T21', title: 'Transplantation', objectives: [{ id: 'T21-objective', text: 'Synthetic supporting objective' }] }],
  progress: { groups: { fresh: { answered: 1, correct: 0 } } }, updates: [] };
const json = (value: unknown) => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } });
const request = vi.fn<typeof fetch>();
const body = (init?: RequestInit) => JSON.parse(String(init?.body));
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(done => { resolve = done; }); return { promise, resolve }; }
function NavigationReceipt() {
  const nav = useNavigation();
  return <output data-testid="handoff">{JSON.stringify({ route: nav.route, handoff: nav.handoff })}</output>;
}
function mount() { return render(<NavigationProvider><Study /><NavigationReceipt /></NavigationProvider>); }
beforeEach(() => { window.history.replaceState(null, '', '#/study'); request.mockReset(); vi.stubGlobal('fetch', request); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Study content-owned track consumers', () => {
  it('shows dated partial coverage, domain gaps and curriculum-support limits without an exam claim', async () => {
    request.mockResolvedValue(json(home));
    mount();
    const coverage = await screen.findByRole('region', { name: 'Study track coverage' });
    expect(within(coverage).getByText('Partial mapping')).toBeTruthy();
    expect(within(coverage).getByText('2026-10-05').tagName).toBe('TIME');
    expect(within(coverage).getByText(/Exam simulation is unavailable/)).toBeTruthy();
    fireEvent.click(within(coverage).getByText('Mapped domains and gaps'));
    expect(within(coverage).getByText('Synthetic gap domain')).toBeTruthy();
    expect(within(coverage).getByText('Gap in the active content pack.')).toBeTruthy();
    expect(within(coverage).getByText('Depth remains incomplete.')).toBeTruthy();
    expect(within(coverage).getByText(/Curriculum-support objectives remain/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Study preferences' }));
    expect(screen.getByRole('checkbox', { name: 'Electrolytes' }).getAttribute('aria-describedby')).toBeNull();
    const outside = screen.getByRole('checkbox', { name: 'Transplantation' });
    expect(document.getElementById(outside.getAttribute('aria-describedby')!)?.textContent).toContain('Outside this ESENeph');
  });

  it('uses saved track selection for Test and the retained manual activity origin for Start', async () => {
    request.mockImplementation(async () => json(home));
    mount();
    fireEvent.click(await screen.findByRole('button', { name: 'Open Test' }));
    expect(JSON.parse(screen.getByTestId('handoff').textContent!)).toEqual({ route: 'assessment', handoff: { track: 'esen_eph' } });
    const manualRow = screen.getByText(manual.title).closest('article')!;
    expect(within(manualRow).getByText(/Kept from your manual plan/)).toBeTruthy();
    fireEvent.click(within(manualRow).getByRole('button', { name: 'Start' }));
    expect(JSON.parse(screen.getByTestId('handoff').textContent!)).toEqual({ route: 'learn', handoff: { topic_id: 'T21', track: 'general_nephrology' } });
    fireEvent.click(within(screen.getByText(mapped.title).closest('article')!).getByRole('button', { name: 'Start' }));
    expect(JSON.parse(screen.getByTestId('handoff').textContent!)).toEqual({ route: 'assessment',
      handoff: { topic_id: 'T03', question_id: 'mapped-question', track: 'esen_eph' } });
  });

  it('blocks a stale-goal proposal, saves track/topic choices, and reloads their actual plan', async () => {
    let stored = { ...home, goals: { ...goals, track: 'general' }, upcoming: [manual] };
    request.mockImplementation(async (url, init) => {
      if (String(url) === '/api/v1/study/home') return json(stored);
      if (String(url) === '/api/v1/study/goals') {
        stored = { ...home, goals: body(init), upcoming: [mapped, manual] }; return json(stored.goals);
      }
      if (String(url) === '/api/v1/study/plan/propose') return json({ activities: stored.upcoming, explanation: 'Confirmed mapped suggestions.' });
      throw new Error('Unexpected request: ' + url);
    });
    const view = mount();
    fireEvent.click(await screen.findByRole('button', { name: 'Study preferences' }));
    fireEvent.change(screen.getByRole('combobox', { name: 'Track' }), { target: { value: 'eseneph' } });
    fireEvent.click(screen.getByRole('checkbox', { name: 'Electrolytes' }));
    expect((screen.getByRole('button', { name: 'Suggest a plan' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Suggest a plan' }));
    expect(request.mock.calls.some(([url]) => String(url).endsWith('/plan/propose'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'Save preferences' }));
    await screen.findByText('Your study preferences are saved.');
    const saved = request.mock.calls.find(([, init]) => init?.method === 'PUT')!;
    expect(body(saved[1])).toEqual({ ...goals, topic_ids: ['T03'] });
    await waitFor(() => expect((screen.getByRole('button', { name: 'Suggest a plan' }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole('button', { name: 'Suggest a plan' }));
    await screen.findByText('Confirmed mapped suggestions.');
    view.unmount();
    mount();
    fireEvent.click(await screen.findByRole('button', { name: 'Study preferences' }));
    expect((screen.getByRole('combobox', { name: 'Track' }) as HTMLSelectElement).value).toBe('eseneph');
    expect((screen.getByRole('checkbox', { name: 'Electrolytes' }) as HTMLInputElement).checked).toBe(true);
    expect((screen.getByLabelText('Exam date (optional)') as HTMLInputElement).value).toBe('2027-03-01');
    expect(screen.getByText(mapped.title)).toBeTruthy();
  });

  it('finishes a manual move before saving a new track and removes cached automatic suggestions from the old track', async () => {
    const moved = deferred<Response>(), saved = deferred<Response>();
    const oldAutomatic = { ...manual, id: 'study_old_auto', title: 'Old automatic suggestion', manual_override: false };
    let stored = { ...home, goals: { ...goals, track: 'general' }, upcoming: [manual, oldAutomatic] };
    request.mockImplementation(async (url, init) => {
      if (String(url) === '/api/v1/study/home') return json(stored);
      if (String(url) === '/api/v1/study/plan/' + manual.id) return moved.promise;
      if (String(url) === '/api/v1/study/goals') { stored = { ...home, goals: body(init) }; return saved.promise; }
      throw new Error('Unexpected request: ' + url);
    });
    mount();
    fireEvent.click(await screen.findByRole('button', { name: 'Study preferences' }));
    fireEvent.change(screen.getByRole('combobox', { name: 'Track' }), { target: { value: 'eseneph' } });
    fireEvent.change(screen.getByLabelText('Move ' + manual.title), { target: { value: '2026-10-12' } });
    const save = screen.getByRole('button', { name: 'Save preferences' });
    expect((save as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(save);
    expect(request.mock.calls.filter(([, init]) => init?.method === 'PUT')).toHaveLength(0);
    await act(async () => moved.resolve(json({ ...manual, due_date: '2026-10-12' })));
    await waitFor(() => expect((save as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(save);
    expect((screen.getByLabelText('Move ' + manual.title) as HTMLInputElement).disabled).toBe(true);
    await act(async () => saved.resolve(json(goals)));
    await screen.findByText('Your study preferences are saved.');
    await screen.findByText(mapped.title);
    expect(screen.queryByText(oldAutomatic.title)).toBeNull();
    expect(screen.getByText(manual.title)).toBeTruthy();
  });

  it('keeps an unavailable mapping honest while showing retained manual work', async () => {
    request.mockResolvedValue(json({ ...home, upcoming: [manual], tracks: [metadata[0], {
      id: 'esen_eph', title: 'ESENeph preparation', available: false, reason: 'The active pack has no formal mapping',
      exam_simulation_available: false }], selection: { ...home.selection, status: 'track-unavailable',
      topic_ids: [], objective_ids: {}, message: 'The active pack has no formal mapping' } }));
    mount();
    expect(await screen.findByText('Mapping unavailable')).toBeTruthy();
    expect(screen.getByText('The active pack has no formal mapping')).toBeTruthy();
    expect(screen.getByText(/Kept from your manual plan/)).toBeTruthy();
    expect(screen.queryByText('Partial mapping')).toBeNull();
  });
});
