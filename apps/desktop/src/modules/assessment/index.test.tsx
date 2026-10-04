// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { spawn, type ChildProcess } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import AssessmentPage from './index';
import { NavigationProvider, useNavigation } from '../../shell/navigation';

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../../../..');
const testProfile = mkdtempSync(join(tmpdir(), 'renulus-assessment-ui-'));
let origin = '';
const originalFetch = globalThis.fetch;
let backend: ChildProcess;
let simulateLostAcknowledgement = false;
const answerRequests: string[] = [];

beforeAll(async () => {
  const reservation = createServer();
  await new Promise<void>(resolve => reservation.listen(0, '127.0.0.1', resolve));
  const address = reservation.address();
  if (!address || typeof address === 'string') throw new Error('An isolated test port could not be allocated.');
  const port = address.port;
  await new Promise<void>((resolve, reject) => reservation.close(error => error ? reject(error) : resolve()));
  origin = 'http://127.0.0.1:' + port;
  backend = spawn('python', [join(repositoryRoot, 'tests/assessment/serve_fixture.py'),
    '--profile', testProfile, '--port', String(port)], { cwd: repositoryRoot, windowsHide: true,
      stdio: 'ignore', env: { ...process.env, PYTHONPATH: join(repositoryRoot, 'runtime') } });
  let ready = false;
  for (let attempt = 0; attempt < 100; attempt++) {
    try { ready = (await originalFetch(origin + '/api/v1/health')).ok; } catch { /* Await bounded startup. */ }
    if (ready) break;
    if (backend.exitCode !== null) break;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  if (!ready) throw new Error('The isolated assessment test backend did not start.');
  vi.stubGlobal('fetch', async (input: string | URL | Request, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
    const headers = new Headers(init?.headers); headers.set('x-renulus-token', 'assessment-fixture-session');
    const response = await originalFetch(new URL(url, origin), { ...init, headers });
    if (url.endsWith('/answer')) {
      answerRequests.push(String(init?.body));
      if (simulateLostAcknowledgement) { simulateLostAcknowledgement = false; throw new TypeError('Synthetic lost acknowledgement'); }
    }
    return response;
  });
}, 20_000);

afterEach(() => { cleanup(); simulateLostAcknowledgement = false; });
afterAll(async () => {
  vi.unstubAllGlobals();
  if (backend && backend.exitCode === null) {
    const exited = new Promise<void>(resolve => backend.once('exit', () => resolve()));
    backend.kill(); await exited;
  }
  // Only remove this test's newly allocated temporary directory.
  if (testProfile.startsWith(join(tmpdir(), 'renulus-assessment-ui-'))) rmSync(testProfile, { recursive: true, force: true });
});

function mount() {
  window.location.hash = '#/assessment';
  render(<NavigationProvider><AssessmentPage /></NavigationProvider>);
}

describe('assessment UI with real local API responses', () => {
  it('commits, shows actual source feedback, pauses, resumes and reviews without prototype scores', async () => {
    mount();
    await screen.findByText('Choose a focused quiz');
    fireEvent.change(screen.getByLabelText('Questions'), { target: { value: '2' } });
    fireEvent.click(screen.getByText('Start reviewed quiz'));
    await screen.findByText('Question 1');
    expect(document.activeElement?.tagName).toBe('LEGEND');
    fireEvent.click(screen.getByLabelText('Token b'));
    fireEvent.click(screen.getByText('Commit answer'));
    await screen.findByText('PRIVATE_REVIEWED_KEY_SENTINEL');
    expect(document.activeElement?.tagName).toBe('H2');
    expect(screen.getByText('Fixture section 1')).toBeDefined();
    expect(screen.getByText('Review this answer')).toBeDefined();
    fireEvent.click(screen.getByText('Next question'));
    await screen.findByText('Question 2');
    fireEvent.click(screen.getByText('View source help'));
    await screen.findByText('Source help · assisted');
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

  it('shows generated practice as unavailable and sends no generation request', async () => {
    mount();
    await screen.findByText('Choose a focused quiz');
    fireEvent.click(screen.getByText('Generated practice'));
    await screen.findByText('Practice generation is not connected');
    expect(screen.queryByText('Start reviewed quiz')).toBeNull();
    expect(screen.queryByText('Commit answer')).toBeNull();
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
});
