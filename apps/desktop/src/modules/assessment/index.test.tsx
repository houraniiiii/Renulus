// @vitest-environment jsdom
import { cleanup, configure, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { spawn, type ChildProcess } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import AssessmentPage from './index';
import { NavigationProvider, useNavigation } from '../../shell/navigation';
import { fixturePython, fixtureReady, stopFixture } from '../../testBackend';
import type { Catalog } from './types';

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../../../..');
const testProfile = mkdtempSync(join(tmpdir(), 'renulus-assessment-ui-'));
let origin = '';
const originalFetch = globalThis.fetch;
let backend: ChildProcess;
let simulateLostAcknowledgement = false;
let simulateLostGenerationCompletion = false;
const answerRequests: string[] = [];
const generationRequests: string[] = [];
const startRequests: string[] = [];
let transformCatalog: ((catalog: Catalog, track: string | null) => Catalog) | null = null;
vi.setConfig({ testTimeout: 30_000 });
configure({ asyncUtilTimeout: 5_000 });

beforeAll(async () => {
  const reservation = createServer();
  await new Promise<void>(resolve => reservation.listen(0, '127.0.0.1', resolve));
  const address = reservation.address();
  if (!address || typeof address === 'string') throw new Error('An isolated test port could not be allocated.');
  const port = address.port;
  await new Promise<void>((resolve, reject) => reservation.close(error => error ? reject(error) : resolve()));
  origin = 'http://127.0.0.1:' + port;
  let startupError = '';
  // Venv editable finders can otherwise win over PYTHONPATH and silently test
  // another worktree. Prepend this lane before importing the API/fixtures.
  const runtimeRoot = join(repositoryRoot, 'runtime');
  const fixtureRoot = join(repositoryRoot, 'tests/assessment');
  const bootstrap = [
    'import runpy, sys',
    'from pathlib import Path',
    'sys.path[:0] = ' + JSON.stringify([runtimeRoot, fixtureRoot]),
    'import renulus',
    'assert Path(renulus.__file__).resolve().parent.parent == Path(' + JSON.stringify(runtimeRoot) + ').resolve()',
    'from test_track_catalog import MappedContentRepository',
    'import conftest',
    'conftest.SyntheticContentRepository = MappedContentRepository',
    'runpy.run_path(' + JSON.stringify(join(fixtureRoot, 'serve_fixture.py')) + ', run_name="__main__")',
  ].join('\n');
  backend = spawn(fixturePython(repositoryRoot), ['-c', bootstrap,
    '--profile', testProfile, '--port', String(port), '--generated-provider'], { cwd: repositoryRoot, windowsHide: true,
      stdio: ['ignore', 'ignore', 'pipe'], env: { ...process.env, PYTHONPATH: join(repositoryRoot, 'runtime') } });
  backend.stderr?.on('data', chunk => { startupError = (startupError + String(chunk)).slice(-2000); });
  backend.on('error', error => { startupError = error.message; });
  const ready = await fixtureReady(backend, origin, originalFetch);
  if (!ready) throw new Error('The isolated assessment test backend did not start. ' + startupError);
  vi.stubGlobal('fetch', async (input: string | URL | Request, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
    const headers = new Headers(init?.headers); headers.set('x-renulus-token', 'assessment-fixture-session');
    const response = await originalFetch(new URL(url, origin), { ...init, headers });
    const parsed = new URL(url, origin);
    if (parsed.pathname === '/api/v1/assessment/catalog' && transformCatalog && response.ok) {
      const catalog = await response.json() as Catalog;
      return Response.json(transformCatalog(catalog, parsed.searchParams.get('track')));
    }
    if (parsed.pathname === '/api/v1/assessment/start') startRequests.push(String(init?.body));
    if (url.endsWith('/practice/generate')) {
      generationRequests.push(String(init?.body));
      if (simulateLostGenerationCompletion) {
        simulateLostGenerationCompletion = false;
        const completed = await response.text();
        return new Response(completed.slice(0, completed.lastIndexOf('id: ')), { status: response.status, headers: response.headers });
      }
    }
    if (url.endsWith('/answer')) {
      answerRequests.push(String(init?.body));
      if (simulateLostAcknowledgement) { simulateLostAcknowledgement = false; throw new TypeError('Synthetic lost acknowledgement'); }
    }
    return response;
  });
}, 75_000);

afterEach(() => { cleanup(); simulateLostAcknowledgement = false; simulateLostGenerationCompletion = false; transformCatalog = null; });
afterAll(async () => {
  configure({ asyncUtilTimeout: 1000 });
  vi.resetConfig();
  vi.unstubAllGlobals();
  await stopFixture(backend);
  // Only remove this test's newly allocated temporary directory.
  if (testProfile.startsWith(join(tmpdir(), 'renulus-assessment-ui-'))) rmSync(testProfile, { recursive: true, force: true, maxRetries: 20, retryDelay: 100 });
}, 20_000);

function mount() {
  window.location.hash = '#/assessment';
  render(<NavigationProvider><AssessmentPage /></NavigationProvider>);
}

describe('assessment UI with real local API responses', () => {
  it('selects the mapped content track, shows honest gaps and launches that exact track', async () => {
    mount();
    await screen.findByText('Choose a focused quiz');
    fireEvent.change(screen.getByLabelText('Topic'), { target: { value: 'glomerular' } });
    fireEvent.change(screen.getByLabelText('Track'), { target: { value: 'esen_eph' } });
    await screen.findByText('Mapping checked 2026-10-05.');
    expect((screen.getByLabelText('Track') as HTMLSelectElement).value).toBe('esen_eph');
    expect((screen.getByLabelText('Topic') as HTMLSelectElement).value).toBe('');
    expect(screen.getByText('3 reviewed questions in 2 item families available.')).toBeDefined();
    expect(screen.getByText('0 questions match the exam option format. Exam simulation is unavailable.')).toBeDefined();
    expect(screen.getByRole('option', { name: 'Glomerular workflow fixture (0 item families)' }).hasAttribute('disabled')).toBe(true);
    expect(screen.queryByText(/ESENeph examination mapping is not available/)).toBeNull();
    fireEvent.click(screen.getByText('View indicative domain coverage'));
    expect(screen.getByRole('row', { name: 'Uncovered fixture domain 0 0 2 Gap' })).toBeDefined();
    expect(screen.getByRole('row', { name: 'Haemodialysis fixture domain 2 1 3 Partial' })).toBeDefined();
    const before = startRequests.length;
    fireEvent.click(screen.getByText('Start reviewed quiz'));
    await screen.findByText('Question 1');
    expect(startRequests.length - before).toBe(1);
    expect(JSON.parse(startRequests[before]).selector).toEqual({ track: 'esen_eph', topic_ids: [] });
    expect(screen.getByText('ESENeph preparation')).toBeDefined();
    expect(screen.getByText('Only 2 item families matched the requested 10 questions.')).toBeDefined();
    fireEvent.click(screen.getByLabelText('Token a'));
    fireEvent.click(screen.getByText('Commit answer'));
    await screen.findByText('PRIVATE_REVIEWED_KEY_SENTINEL');
    expect(screen.getByText('Correct')).toBeDefined();
  });

  it('preserves an explicit unavailable legacy track and prevents its launch', async () => {
    transformCatalog = (catalog, track) => {
      const unavailable = { ...catalog, tracks: catalog.tracks.map(candidate => candidate.id === 'esen_eph'
        ? { ...candidate, available: false, available_families: 0, available_questions: 0,
          status: 'not_formally_mapped', reason: 'The active pack has no formal mapping',
          checked_on: undefined, format_compatible_questions: undefined, domains: [] } : candidate) };
      return track === 'esen_eph' ? { ...unavailable, available_families: 0, available_questions: 0,
        domains: catalog.domains.map(domain => ({ ...domain, available_families: 0 })) } : unavailable;
    };
    mount();
    await screen.findByText('Choose a focused quiz');
    expect(screen.getByRole('option', { name: 'ESENeph preparation (unavailable)' })).toBeDefined();
    fireEvent.change(screen.getByLabelText('Track'), { target: { value: 'esen_eph' } });
    await screen.findByText('ESENeph preparation is unavailable.');
    expect(screen.getByText(/The active pack has no formal mapping/)).toBeDefined();
    const button = screen.getByText('Start reviewed quiz') as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    const before = startRequests.length;
    fireEvent.click(button);
    expect(startRequests.length).toBe(before);
    fireEvent.change(screen.getByLabelText('Track'), { target: { value: 'general_nephrology' } });
    await screen.findByText('4 reviewed questions in 3 item families available.');
    expect((screen.getByText('Start reviewed quiz') as HTMLButtonElement).disabled).toBe(false);
  });

  it('retains the chosen track through a catalog failure and cannot launch stale general coverage', async () => {
    mount();
    await screen.findByText('Choose a focused quiz');
    transformCatalog = (catalog, track) => {
      if (track === 'esen_eph') throw new TypeError('Synthetic lost track coverage');
      return catalog;
    };
    const before = startRequests.length;
    fireEvent.change(screen.getByLabelText('Track'), { target: { value: 'esen_eph' } });
    await screen.findByRole('alert');
    expect(screen.queryByText('Start reviewed quiz')).toBeNull();
    expect(startRequests.length).toBe(before);
    transformCatalog = null;
    fireEvent.click(screen.getByText('Try again'));
    await screen.findByText('Mapping checked 2026-10-05.');
    expect((screen.getByLabelText('Track') as HTMLSelectElement).value).toBe('esen_eph');
    expect(screen.getByText('3 reviewed questions in 2 item families available.')).toBeDefined();
  });

  it('commits, shows actual source feedback, pauses, resumes and reviews without prototype scores', async () => {
    mount();
    await screen.findByText('Choose a focused quiz');
    fireEvent.change(screen.getByLabelText('Questions'), { target: { value: '2' } });
    fireEvent.click(screen.getByText('Start reviewed quiz'));
    await screen.findByText('Question 1');
    await waitFor(() => expect(document.activeElement?.tagName).toBe('LEGEND'));
    fireEvent.click(screen.getByLabelText('Token b'));
    fireEvent.click(screen.getByText('Commit answer'));
    await screen.findByText('PRIVATE_REVIEWED_KEY_SENTINEL');
    await waitFor(() => expect(document.activeElement?.tagName).toBe('H2'));
    expect(screen.getByText('Fixture section 1')).toBeDefined();
    expect(screen.getByText('Review this answer')).toBeDefined();
    fireEvent.click(screen.getByText('Next question'));
    const nextQuestion = await screen.findByText('Question 2');
    // Finding the rendered question can precede its focus effect.
    await waitFor(() => {
      expect(document.activeElement?.tagName).toBe('LEGEND');
      expect(document.activeElement).toBe(nextQuestion.closest('legend'));
    });
    const sourceHelp = screen.getByText('View source help'); sourceHelp.focus();
    fireEvent.click(sourceHelp);
    await screen.findByText('Source help · assisted');
    expect(document.activeElement).toBe(sourceHelp);
    fireEvent.click(screen.getByText('Pause'));
    await screen.findByText('Quiz paused');
    fireEvent.click(screen.getByText('Resume quiz'));
    await screen.findByText('Question 2');
    fireEvent.click(screen.getByText('End session'));
    await screen.findByText(/This session ended with 1 committed answers/);
    fireEvent.click(screen.getByText('Review committed answers'));
    await screen.findByText('Committed answer review');
    expect(screen.getByText('PRIVATE_REVIEWED_KEY_SENTINEL')).toBeDefined();
    expect(screen.queryByLabelText('Token a')).toBeNull();
  });

  it('retries an answer with the same request key after the server commits but acknowledgement is lost', async () => {
    mount();
    await screen.findByText('Choose a focused quiz');
    fireEvent.change(screen.getByLabelText('Questions'), { target: { value: '1' } });
    fireEvent.click(screen.getByText('Start reviewed quiz'));
    await screen.findByText('Question 1');
    fireEvent.click(screen.getByLabelText('Token a'));
    simulateLostAcknowledgement = true;
    const before = answerRequests.length;
    fireEvent.click(screen.getByText('Commit answer'));
    await screen.findByText('Your action needs attention');
    expect((screen.getByText('Commit answer') as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByText('Try again'));
    await screen.findByText('PRIVATE_REVIEWED_KEY_SENTINEL');
    expect(answerRequests.length - before).toBe(2);
    expect(answerRequests[before]).toBe(answerRequests[before + 1]);
    expect(screen.getByText('1 / 1 committed')).toBeDefined();
  });

  it('generates through the approved seam and keeps actual generated results separate', async () => {
    mount();
    await screen.findByText('Choose a focused quiz');
    fireEvent.click(screen.getByText('Generated practice'));
    const instruction = await screen.findByLabelText('What would you like to practise?');
    fireEvent.change(instruction, { target: { value: 'Original token practice' } });
    fireEvent.change(screen.getByLabelText('Questions'), { target: { value: '1' } });
    await waitFor(() => expect((screen.getByText('Generate practice') as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByText('Generate practice'));
    await screen.findByText('Original token exercise 0');
    expect(screen.queryByText('ORIGINAL_GENERATED_KEY_NOT_REVIEWED')).toBeNull();
    expect(screen.queryByText('Start reviewed quiz')).toBeNull();
    fireEvent.click(screen.getByText('View sources'));
    await screen.findByText('Source help · assisted');
    fireEvent.click(screen.getByLabelText('Marked token'));
    fireEvent.click(screen.getByText('Commit answer'));
    await screen.findByText('ORIGINAL_GENERATED_KEY_NOT_REVIEWED');
    expect(screen.getByText('Matches generated key')).toBeDefined();
    expect(screen.getByText('Generated key comparisons')).toBeDefined();
    expect(screen.getByText('page 2')).toBeDefined();
    fireEvent.click(screen.getByText('Finish practice'));
    await screen.findByText('This practice ended with 1 committed answers.');
    fireEvent.click(screen.getByText('Review committed answers'));
    await screen.findByText('Committed answer review');
  });

  it('does not convert a temporary case handoff into durable reviewed progress', async () => {
    function TemporaryEntry() {
      const nav = useNavigation();
      return <button onClick={() => nav.navigate('assessment')}>Open temporary Test</button>;
    }
    window.location.hash = '#/cases';
    render(<NavigationProvider><TemporaryEntry /><AssessmentPage /></NavigationProvider>);
    fireEvent.click(screen.getByText('Open temporary Test'));
    await screen.findByText('This case context is temporary. Start a separate study session to use the reviewed bank.');
    expect(screen.queryByText('Start reviewed quiz')).toBeNull();
    fireEvent.click(screen.getByText('Start separate study'));
    await waitFor(() => expect(screen.getByText('Choose a focused quiz')).toBeDefined());
  });

  it('keeps temporary generated questions and answers out of saved study history', async () => {
    const beforeHistory = await (await globalThis.fetch('/api/v1/assessment/practice/sessions')).json() as { sessions: unknown[] };
    const beforeProgress = await (await globalThis.fetch('/api/v1/assessment/progress')).json() as { attempt_count: number };
    function TemporaryEntry() {
      const nav = useNavigation();
      return <button onClick={() => nav.navigate('assessment')}>Open temporary practice</button>;
    }
    window.location.hash = '#/cases';
    render(<NavigationProvider><TemporaryEntry /><AssessmentPage /></NavigationProvider>);
    fireEvent.click(screen.getByText('Open temporary practice'));
    await screen.findByLabelText('What would you like to practise?');
    await waitFor(() => expect(screen.queryByText('Checking practice generation availability')).toBeNull());
    fireEvent.change(screen.getByLabelText('What would you like to practise?'), { target: { value: 'Original volatile token practice' } });
    fireEvent.change(screen.getByLabelText('Questions'), { target: { value: '1' } });
    await waitFor(() => expect((screen.getByText('Generate practice') as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByText('Generate practice'));
    await screen.findByText('Original token exercise 0');
    fireEvent.click(screen.getByLabelText('Marked token'));
    fireEvent.click(screen.getByText('Commit answer'));
    await screen.findByText('ORIGINAL_GENERATED_KEY_NOT_REVIEWED');
    const response = await globalThis.fetch('/api/v1/assessment/practice/sessions');
    const history = await response.json() as { sessions: { id: string; retention: string }[] };
    expect(history.sessions.every(session => session.retention === 'persistent')).toBe(true);
    expect(history.sessions.length).toBe(beforeHistory.sessions.length);
    const afterProgress = await (await globalThis.fetch('/api/v1/assessment/progress')).json() as { attempt_count: number };
    expect(afterProgress.attempt_count).toBe(beforeProgress.attempt_count);
    expect(screen.queryByText('Reviewed results')).toBeNull();
    expect(window.location.hash).toBe('#/assessment');
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
  });

  it('recovers completed generation with the same body and key after its terminal acknowledgement is lost', async () => {
    mount();
    await screen.findByText('Choose a focused quiz');
    fireEvent.click(screen.getByText('Generated practice'));
    fireEvent.change(await screen.findByLabelText('What would you like to practise?'), { target: { value: 'Original recovered generation' } });
    fireEvent.change(screen.getByLabelText('Questions'), { target: { value: '1' } });
    await waitFor(() => expect((screen.getByText('Generate practice') as HTMLButtonElement).disabled).toBe(false));
    const before = generationRequests.length;
    simulateLostGenerationCompletion = true;
    fireEvent.click(screen.getByText('Generate practice'));
    await screen.findByText('Generation could not be confirmed');
    fireEvent.click(screen.getByText('Reconnect same request'));
    await screen.findByText('Original token exercise 0');
    expect(generationRequests.length - before).toBe(2);
    expect(generationRequests[before]).toBe(generationRequests[before + 1]);
    expect(screen.queryByText('ORIGINAL_GENERATED_KEY_NOT_REVIEWED')).toBeNull();
  });

  it('opens pinned source feedback from the Today question handoff without starting a new quiz', async () => {
    const result = await (await globalThis.fetch('/api/v1/assessment/mistakes')).json() as {
      mistakes: { question_id: string; topic_id: string }[] };
    const mistake = result.mistakes[0];
    expect(mistake).toBeDefined();
    function TodayEntry() {
      const nav = useNavigation();
      return <button onClick={() => nav.navigate('assessment', { payload: {
        topic_id: mistake.topic_id, question_id: mistake.question_id,
      } })}>Open observed mistake</button>;
    }
    window.location.hash = '#/study';
    render(<NavigationProvider><TodayEntry /><AssessmentPage /></NavigationProvider>);
    await screen.findByText('Choose a focused quiz');
    fireEvent.click(screen.getByText('Open observed mistake'));
    await screen.findByText('PRIVATE_REVIEWED_KEY_SENTINEL');
    expect(screen.getByText('Fixture section 1')).toBeDefined();
    expect(screen.getByText('Review this answer')).toBeDefined();
    expect(screen.queryByText('Start reviewed quiz')).toBeNull();
  });
});
