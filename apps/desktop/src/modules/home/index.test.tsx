// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import Home from './index';
import { NamePreference } from './NamePreference';
import type { HomeState } from './types';

const mocks = vi.hoisted(() => ({ readHome: vi.fn(), refreshHome: vi.fn(), readName: vi.fn(), saveName: vi.fn(), navigate: vi.fn() }));
vi.mock('./requests', () => mocks);
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
  vi.clearAllMocks(); mocks.readHome.mockResolvedValue(state()); mocks.refreshHome.mockResolvedValue(state());
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
  const send = vi.fn(); render(<Home adapters={{ send }} />);
  await screen.findByRole('heading', { name: 'Welcome back, Dr. Ada' });
  fireEvent.click(screen.getByRole('button', { name: 'Discuss a case' }));
  fireEvent.click(screen.getByRole('button', { name: 'Synthetic fictional case 0' }));
  expect(composer().value).toBe('Synthetic fictional case 0');
  expect(send).not.toHaveBeenCalled();
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
  expect(send).not.toHaveBeenCalled();
});

it('sends separately with typed canonical identity, selected kind and volatile prefill', async () => {
  const conversation = { identity: { type: 'case' as const, id: 'synthetic-case' }, kind: 'case' as const,
    title: 'Synthetic', retention: 'saved' as const, lifecycle: 'active' as const, revision: 2, project_id: null, created_at: 'now', updated_at: 'now' };
  const send = vi.fn().mockResolvedValue(conversation);
  render(<Home adapters={{ send }} />);
  await screen.findByRole('heading', { name: 'Welcome back, Dr. Ada' });
  fireEvent.click(screen.getByRole('button', { name: 'Discuss a case' }));
  fireEvent.click(screen.getByRole('button', { name: 'Synthetic fictional case 1' }));
  fireEvent.click(screen.getByRole('button', { name: 'Send' }));
  await act(async () => {});
  expect(send).toHaveBeenCalledWith({ text: 'Synthetic fictional case 1', kind: 'case' });
  expect(mocks.navigate).toHaveBeenCalledWith('chat', { scope: { kind: 'study' },
    payload: { conversation: { type: 'case', id: 'synthetic-case' }, kind: 'case', prefill: 'Synthetic fictional case 1' } });
});

it('keeps generic first run and offline composer usable without fabricated prompts', async () => {
  mocks.readHome.mockRejectedValue(new Error('Synthetic offline runtime'));
  render(<Home />);
  await screen.findByText('Daily suggestions are unavailable. You can still write a message.');
  expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeTruthy();
  expect(composer().disabled).toBe(false);
  fireEvent.change(composer(), { target: { value: 'An educational question' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send' }));
  await screen.findByText('Chat is not available yet. Your draft is kept.');
  expect(composer().value).toBe('An educational question');
});

it('does not change the greeting when name data arrives after composing starts', async () => {
  let resolve!: (value: HomeState) => void;
  mocks.readHome.mockReturnValue(new Promise<HomeState>(done => { resolve = done; }));
  render(<Home />);
  fireEvent.change(composer(), { target: { value: 'Started typing' } });
  await act(async () => resolve(state()));
  expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeTruthy();
});

it('shows old cache date and keeps the Quick practice prerequisite exact', async () => {
  const old = { ...state(), stale: true, suggestions_date: '2026-10-09' };
  mocks.readHome.mockResolvedValue(old); mocks.refreshHome.mockResolvedValue(old);
  render(<Home />);
  await screen.findByRole('heading', { name: 'Welcome back, Dr. Ada' });
  fireEvent.click(screen.getByRole('button', { name: 'Quick practice' }));
  expect(screen.getByText('2026-10-09').tagName).toBe('TIME');
  expect(screen.getByText(/Previous suggestions/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Synthetic five-question practice 0' }));
  fireEvent.click(screen.getByRole('button', { name: 'Send' }));
  await screen.findByText('Quick practice is awaiting the saved five-question Study flow. Your draft is kept.');
  expect(mocks.navigate).not.toHaveBeenCalled();
  expect(composer().value).toBe('Synthetic five-question practice 0');
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
