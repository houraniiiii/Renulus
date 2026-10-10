// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import Home from './index';
import { NamePreference } from './NamePreference';
import { ApiError } from '../../platform/api';
import type { HomeState } from './types';

const mocks = vi.hoisted(() => ({ readHome: vi.fn(), refreshHome: vi.fn(), readName: vi.fn(), saveName: vi.fn(), navigate: vi.fn(), createConversation: vi.fn(), sendConversation: vi.fn(), cancelChatTestRun: vi.fn(), prepareQuickPractice: vi.fn() }));
vi.mock('./requests', () => mocks);
vi.mock('../chat/api', () => mocks);
vi.mock('./practice', () => mocks);
vi.mock('../../shell/navigation', () => ({
  routes: ['newchat', 'chat', 'tests', 'attempts'].map(id => ({ id })),
  useNavigation: () => ({ route: 'newchat', scope: { kind: 'study' }, navigate: mocks.navigate }),
}));
const state = (): HomeState => ({ preferences: { doctor_name: 'Ada', revision: 1 },
  suggestions: { explain: Array.from({ length: 5 }, (_, i) => 'Synthetic explain ' + i),
    case: Array.from({ length: 5 }, (_, i) => 'Synthetic fictional case ' + i),
    practice: Array.from({ length: 5 }, (_, i) => 'Synthetic five-question practice ' + i) },
  suggestions_date: '2026-10-10', stale: false, job: null, error_code: null, assistance_allowed: true });
beforeEach(() => {
  vi.resetAllMocks(); mocks.readHome.mockResolvedValue(state()); mocks.refreshHome.mockResolvedValue(state());
  mocks.readName.mockResolvedValue(state().preferences);
});
afterEach(() => cleanup());
const composer = () => screen.getByRole('textbox', { name: 'How can I help you today' }) as HTMLTextAreaElement;

it('renders exact greeting/composer/Attach/Send and switches exactly five suggestions in one region', async () => {
  render(<Home />);
  await screen.findByRole('heading', { name: 'Welcome back, Dr. Ada' });
  expect(composer().placeholder).toBe('How can I help you today');
  expect(screen.getByRole('button', { name: 'Attach' })).toBeTruthy();
  expect((screen.getByRole('button', { name: 'Send' }) as HTMLButtonElement).disabled).toBe(true);
  for (const category of ['Explain a topic', 'Discuss a case', 'Quick practice']) {
    fireEvent.click(screen.getByRole('button', { name: category }));
    expect(screen.getAllByRole('region', { name: / suggestions$/ })).toHaveLength(1);
    expect(within(screen.getByRole('region', { name: category + ' suggestions' })).getAllByRole('button')).toHaveLength(5);
    expect(screen.getAllByRole('button').filter(button => button.getAttribute('aria-expanded') === 'true')).toHaveLength(1);
  }
  fireEvent.click(screen.getByRole('button', { name: 'Quick practice' }));
  expect(screen.queryByRole('region', { name: / suggestions$/ })).toBeNull();
  expect(screen.queryByText('Auto')).toBeNull();
  expect(screen.queryByText('Your learning space')).toBeNull();
});

it('prefills only and keeps an existing draft until an explicit append or replace', async () => {
  const create = vi.fn(); render(<Home adapters={{ create }} />);
  await screen.findByRole('heading', { name: 'Welcome back, Dr. Ada' });
  fireEvent.click(screen.getByRole('button', { name: 'Discuss a case' }));
  fireEvent.click(screen.getByRole('button', { name: 'Synthetic fictional case 0' }));
  expect(composer().value).toBe('Synthetic fictional case 0');
  expect(create).not.toHaveBeenCalled();
  expect(mocks.navigate).not.toHaveBeenCalled();
  fireEvent.change(composer(), { target: { value: 'My existing draft' } });
  fireEvent.click(screen.getByRole('button', { name: 'Explain a topic' }));
  fireEvent.click(screen.getByRole('button', { name: 'Synthetic explain 0' }));
  expect(composer().value).toBe('My existing draft');
  fireEvent.click(screen.getByRole('button', { name: 'Keep draft' }));
  expect(composer().value).toBe('My existing draft');
  fireEvent.click(screen.getByRole('button', { name: 'Synthetic explain 0' }));
  fireEvent.click(screen.getByRole('button', { name: 'Add to draft' }));
  expect(composer().value).toBe('My existing draft\n\nSynthetic explain 0');
  fireEvent.click(screen.getByRole('button', { name: 'Synthetic explain 1' }));
  fireEvent.click(screen.getByRole('button', { name: 'Replace draft' }));
  expect(composer().value).toBe('Synthetic explain 1');
  expect(create).not.toHaveBeenCalled();
});

it('creates through the published helper and hands off one explicit send intent with canonical identity/retention', async () => {
  const conversation = { identity: { type: 'case' as const, id: 'synthetic-case' }, kind: 'case' as const,
    title: 'Synthetic', retention: 'saved' as const, lifecycle: 'active' as const, revision: 2, project_id: null, created_at: 'now', updated_at: 'now' };
  mocks.createConversation.mockResolvedValue(conversation);
  render(<Home />);
  await screen.findByRole('heading', { name: 'Welcome back, Dr. Ada' });
  fireEvent.click(screen.getByRole('button', { name: 'Discuss a case' }));
  fireEvent.click(screen.getByRole('button', { name: 'Synthetic fictional case 1' }));
  fireEvent.click(screen.getByRole('button', { name: 'Send' }));
  await act(async () => {});
  expect(mocks.createConversation).toHaveBeenCalledExactlyOnceWith({ kind: 'case' }, expect.any(AbortSignal), expect.any(String));
  expect(mocks.navigate).toHaveBeenCalledExactlyOnceWith('chat', { scope: { kind: 'saved-case', entity_id: 'synthetic-case' },
    payload: { conversation: { type: 'case', id: 'synthetic-case' }, retention: 'saved',
      sendIntent: { text: 'Synthetic fictional case 1', request_id: expect.any(String) } } });
  expect(mocks.navigate.mock.calls[0][1].payload.sendIntent.request_id).toMatch(/^[0-9a-f-]{36}$/);
  expect(mocks.sendConversation).not.toHaveBeenCalled();
  expect(composer().value).toBe('');
});

it('keeps generic first run and offline composer usable without fabricated prompts', async () => {
  mocks.readHome.mockRejectedValue(new Error('Synthetic offline runtime'));
  mocks.createConversation.mockRejectedValue(new Error('Synthetic offline chat'));
  render(<Home />);
  await screen.findByText('Daily suggestions are unavailable. You can still write a message.');
  expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeTruthy();
  expect(composer().disabled).toBe(false);
  fireEvent.change(composer(), { target: { value: 'An educational question' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send' }));
  await screen.findByText('Your message could not be sent. Your draft is kept.');
  expect(composer().value).toBe('An educational question');
});

it('retains a failed handoff draft and retries the same conversation and stable send request', async () => {
  mocks.createConversation.mockResolvedValue({ identity: { type: 'learn_thread', id: 'synthetic-learning' },
    kind: 'learning', retention: 'saved' });
  mocks.navigate.mockImplementationOnce(() => { throw new Error('Synthetic navigation failure'); });
  render(<Home />);
  await screen.findByRole('heading', { name: 'Welcome back, Dr. Ada' });
  fireEvent.change(composer(), { target: { value: 'My retained learning draft' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send' }));
  await screen.findByText('Your message could not be sent. Your draft is kept.');
  expect(composer().value).toBe('My retained learning draft');
  const original = mocks.navigate.mock.calls[0][1];
  fireEvent.click(screen.getByRole('button', { name: 'Send' }));
  await act(async () => {});
  expect(mocks.createConversation).toHaveBeenCalledExactlyOnceWith({ kind: 'learning' }, expect.any(AbortSignal), expect.any(String));
  expect(mocks.navigate).toHaveBeenLastCalledWith('chat', original);
  expect(original.scope).toEqual({ kind: 'study', entity_id: 'synthetic-learning' });
  expect(composer().value).toBe('');
  expect(mocks.sendConversation).not.toHaveBeenCalled();
});

it('keeps draft during creation and refuses duplicate submissions before the handoff', async () => {
  let resolve!: (value: unknown) => void;
  mocks.createConversation.mockReturnValue(new Promise(done => { resolve = done; }));
  render(<Home />);
  await screen.findByRole('heading', { name: 'Welcome back, Dr. Ada' });
  fireEvent.change(composer(), { target: { value: 'One educational request' } });
  fireEvent.submit(composer().closest('form')!);
  fireEvent.submit(composer().closest('form')!);
  expect(composer().value).toBe('One educational request');
  expect(mocks.createConversation).toHaveBeenCalledTimes(1);
  expect(mocks.navigate).not.toHaveBeenCalled();
  await act(async () => resolve({ identity: { type: 'learn_thread', id: 'synthetic-once' }, kind: 'learning', retention: 'saved' }));
  expect(mocks.navigate).toHaveBeenCalledTimes(1);
  expect(mocks.sendConversation).not.toHaveBeenCalled();
});

it('pauses assistance on the actual policy error while keeping the draft controls visible', async () => {
  mocks.readHome.mockRejectedValue(new ApiError('Submit the active Test before opening learning help.', 409, 'assistance_restricted'));
  render(<Home />);
  await screen.findByText('Chat and daily suggestions are paused during an active Test.');
  expect(composer().disabled).toBe(true);
  expect((screen.getByRole('button', { name: 'Send' }) as HTMLButtonElement).disabled).toBe(true);
  expect(mocks.createConversation).not.toHaveBeenCalled();
  expect(mocks.refreshHome).not.toHaveBeenCalled();
});

it('does not change the greeting when name data arrives after composing starts', async () => {
  let resolve!: (value: HomeState) => void;
  mocks.readHome.mockReturnValue(new Promise<HomeState>(done => { resolve = done; }));
  render(<Home />);
  fireEvent.change(composer(), { target: { value: 'Started typing' } });
  await act(async () => resolve(state()));
  expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeTruthy();
});

it('shows old cache date and keeps a failed Quick practice draft and volatile request for explicit retry', async () => {
  const old = { ...state(), stale: true, suggestions_date: '2026-10-09' };
  mocks.readHome.mockResolvedValue(old); mocks.refreshHome.mockResolvedValue(old);
  mocks.prepareQuickPractice.mockRejectedValue(new ApiError('The trusted test preparation service is not ready', 503, 'chat_test_unavailable'));
  render(<Home />);
  await screen.findByRole('heading', { name: 'Welcome back, Dr. Ada' });
  fireEvent.click(screen.getByRole('button', { name: 'Quick practice' }));
  expect(screen.getByText('2026-10-09').tagName).toBe('TIME');
  expect(screen.getByText(/Previous suggestions/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Synthetic five-question practice 0' }));
  fireEvent.click(screen.getByRole('button', { name: 'Send' }));
  await screen.findByText('The trusted test preparation service is not ready');
  expect(mocks.navigate).not.toHaveBeenCalled();
  expect(composer().value).toBe('Synthetic five-question practice 0');
  const request = mocks.prepareQuickPractice.mock.calls[0][0];
  fireEvent.click(screen.getByRole('button', { name: 'Send' }));
  await act(async () => {});
  expect(mocks.prepareQuickPractice.mock.calls[1][0]).toBe(request);
  expect(request.request_id).toMatch(/^[0-9a-f-]{36}$/);
});

it('selects an actual File then hands canonical Chat identity, editable draft and one volatile attachment intent', async () => {
  let resolve!: (value: unknown) => void;
  mocks.createConversation.mockReturnValue(new Promise(done => { resolve = done; }));
  render(<Home />);
  await screen.findByRole('heading', { name: 'Welcome back, Dr. Ada' });
  fireEvent.change(composer(), { target: { value: 'My original learning draft' } });
  const file = new File(['Original synthetic reading'], 'synthetic.md', { type: 'text/markdown' });
  fireEvent.change(screen.getByLabelText('Attach file'), { target: { files: [file] } });
  expect(composer().value).toBe('My original learning draft');
  expect(mocks.navigate).not.toHaveBeenCalled();
  await act(async () => resolve({ identity: { type: 'learn_thread', id: 'attachment-chat' }, kind: 'learning', retention: 'saved' }));
  const handoff = mocks.navigate.mock.calls[0][1];
  expect(handoff.scope).toEqual({ kind: 'study', entity_id: 'attachment-chat' });
  expect(handoff.payload).toEqual({ conversation: { type: 'learn_thread', id: 'attachment-chat' }, retention: 'saved',
    prefill: 'My original learning draft', attachmentIntent: { file, request_id: expect.any(String) } });
  expect(handoff.payload.sendIntent).toBeUndefined();
  expect(mocks.sendConversation).not.toHaveBeenCalled();
  expect(composer().value).toBe('');
});

it('retries an ambiguous attachment creation with the same UUID and preserves the current draft', async () => {
  mocks.createConversation.mockRejectedValueOnce(new Error('lost creation acknowledgement'));
  mocks.createConversation.mockResolvedValueOnce({ identity: { type: 'case', id: 'case-file' }, kind: 'case', retention: 'saved' });
  render(<Home />);
  await screen.findByRole('heading', { name: 'Welcome back, Dr. Ada' });
  fireEvent.click(screen.getByRole('button', { name: 'Discuss a case' }));
  fireEvent.change(composer(), { target: { value: 'Preserved synthetic case draft' } });
  const file = new File(['Synthetic case reading'], 'case.md');
  fireEvent.change(screen.getByLabelText('Attach file'), { target: { files: [file] } });
  await screen.findByText('This attachment could not be opened. Your draft is kept.');
  const firstKey = mocks.createConversation.mock.calls[0][2];
  expect(composer().value).toBe('Preserved synthetic case draft');
  fireEvent.change(composer(), { target: { value: 'Edited retained draft' } });
  fireEvent.click(screen.getByRole('button', { name: 'Retry attachment' }));
  await act(async () => {});
  expect(mocks.createConversation.mock.calls[1][2]).toBe(firstKey);
  expect(mocks.navigate.mock.calls[0][1].payload.prefill).toBe('Edited retained draft');
  expect(mocks.navigate.mock.calls[0][1].scope).toEqual({ kind: 'saved-case', entity_id: 'case-file' });
  expect(mocks.sendConversation).not.toHaveBeenCalled();
});

it('starts Quick practice only on Send, guards duplicates and navigates the returned pinned Study attempt', async () => {
  let resolve!: (value: unknown) => void;
  mocks.prepareQuickPractice.mockReturnValue(new Promise(done => { resolve = done; }));
  render(<Home />);
  await screen.findByRole('heading', { name: 'Welcome back, Dr. Ada' });
  fireEvent.click(screen.getByRole('button', { name: 'Quick practice' }));
  fireEvent.click(screen.getByRole('button', { name: 'Synthetic five-question practice 2' }));
  expect(mocks.prepareQuickPractice).not.toHaveBeenCalled();
  fireEvent.submit(composer().closest('form')!);
  fireEvent.submit(composer().closest('form')!);
  expect(mocks.prepareQuickPractice).toHaveBeenCalledTimes(1);
  expect(composer().value).toBe('Synthetic five-question practice 2');
  await act(async () => resolve({ id: 'canonical-study', version_id: 'saved-five-version' }));
  expect(mocks.navigate).toHaveBeenCalledExactlyOnceWith('attempts', {
    scope: { kind: 'generated-practice', entity_id: 'canonical-study' },
    payload: { attempt_id: 'canonical-study', version_id: 'saved-five-version' },
  });
  expect(mocks.createConversation).not.toHaveBeenCalled();
  expect(mocks.sendConversation).not.toHaveBeenCalled();
});

it('saves the optional chosen name with exact revision and retains unsaved text on failure', async () => {
  mocks.saveName.mockRejectedValue(new Error('Synthetic failure'));
  render(<NamePreference />);
  const input = await screen.findByRole('textbox', { name: 'Name for your greeting' });
  await act(async () => {});
  fireEvent.change(input, { target: { value: '  Grace  ' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save name' }));
  await screen.findByText('Your name could not be saved. Try again.');
  expect((input as HTMLInputElement).value).toBe('  Grace  ');
  const firstKey = mocks.saveName.mock.calls[0][2];
  mocks.saveName.mockResolvedValue({ doctor_name: 'Grace', revision: 2 });
  fireEvent.click(screen.getByRole('button', { name: 'Save name' }));
  await screen.findByText('Your greeting name is saved.');
  expect(mocks.saveName).toHaveBeenLastCalledWith('Grace', 1, firstKey);
});

it.each(['cancelled', 'published', 'unconfirmed'])('holds Send until Stop is acknowledged: %s', async outcome => {
  let finishStop!: (value: unknown) => void, failStop!: (error: Error) => void;
  mocks.cancelChatTestRun.mockReturnValue(new Promise((resolve, reject) => { finishStop = resolve; failStop = reject; }));
  mocks.prepareQuickPractice.mockImplementation((current, signal, onRun) => {
    current.run = { run_id: 'known-run', state: 'running' }; onRun(current.run);
    return new Promise((_resolve, reject) => signal.addEventListener('abort', () => reject(new DOMException('Interrupted', 'AbortError')), { once: true }));
  });
  render(<Home />);
  await screen.findByRole('heading', { name: 'Welcome back, Dr. Ada' });
  fireEvent.click(screen.getByRole('button', { name: 'Quick practice' }));
  fireEvent.change(composer(), { target: { value: 'Keep this original practice draft' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Stop practice' }));
  await act(async () => {});
  expect(screen.getByText('Stopping Quick practice…')).toBeTruthy();
  expect(composer().disabled).toBe(true);
  expect((screen.getByRole('button', { name: 'Send' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.submit(composer().closest('form')!);
  fireEvent.click(screen.getByRole('button', { name: 'Stop practice' }));
  expect(mocks.prepareQuickPractice).toHaveBeenCalledTimes(1);
  expect(mocks.cancelChatTestRun).toHaveBeenCalledExactlyOnceWith('known-run');
  expect(screen.queryByText('Quick practice stopped. Your draft is kept.')).toBeNull();
  const firstCommand = mocks.prepareQuickPractice.mock.calls[0][0];
  await act(async () => {
    if (outcome === 'unconfirmed') failStop(new Error('Lost stop acknowledgement'));
    else finishStop({ run_id: 'known-run', state: outcome });
  });
  expect(composer().value).toBe('Keep this original practice draft');
  expect(composer().disabled).toBe(false);
  expect(mocks.navigate).not.toHaveBeenCalled();
  expect(screen.getByText(outcome === 'cancelled' ? 'Quick practice stopped. Your draft is kept.' :
    outcome === 'published' ? 'The five-question set finished before Stop. Your draft is kept; Send opens its Study attempt.' :
      'The stop could not be confirmed. Your draft is kept; retry to check this request.')).toBeTruthy();
  mocks.prepareQuickPractice.mockResolvedValue({ id: 'returned-study', version_id: 'saved-five' });
  fireEvent.click(screen.getByRole('button', { name: 'Send' }));
  await act(async () => {});
  expect(mocks.prepareQuickPractice.mock.calls[1][0].request_id === firstCommand.request_id).toBe(outcome !== 'cancelled');
  expect(mocks.navigate).toHaveBeenCalledExactlyOnceWith('attempts', {
    scope: { kind: 'generated-practice', entity_id: 'returned-study' }, payload: { attempt_id: 'returned-study', version_id: 'saved-five' },
  });
});

it('aborts attachment creation on unmount and does not hand off late acknowledgement', async () => {
  let resolve!: (value: unknown) => void;
  mocks.createConversation.mockReturnValue(new Promise(done => { resolve = done; }));
  const view = render(<Home />);
  await screen.findByRole('heading', { name: 'Welcome back, Dr. Ada' });
  fireEvent.change(screen.getByLabelText('Attach file'), { target: { files: [new File(['Original synthetic'], 'reading.md')] } });
  const signal = mocks.createConversation.mock.calls[0][1] as AbortSignal;
  view.unmount();
  expect(signal.aborted).toBe(true);
  await act(async () => resolve({ identity: { type: 'learn_thread', id: 'late-chat' }, kind: 'learning', retention: 'saved' }));
  expect(mocks.navigate).not.toHaveBeenCalled();
});
