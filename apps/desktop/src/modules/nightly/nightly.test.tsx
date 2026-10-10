// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ApiError } from '../../platform/api';
import { NightlyPreferences } from './NightlyPreferences';
import { NightlyStatus } from './NightlyStatus';
import type { NightlyState } from './types';

const mocks = vi.hoisted(() => ({ readNightly: vi.fn(), readPreferences: vi.fn(), savePreferences: vi.fn(), cancelNightly: vi.fn() }));
vi.mock('./api', () => mocks);
const status = (): NightlyState => ({
  preferences: { enabled: false, local_time: '22:00', question_count: 5, revision: 1 },
  app_running_only: true, next_eligible_at: null, last_job: null, error_code: null, assistance_allowed: true,
});
const running = (): NightlyState => ({ ...status(), preferences: { ...status().preferences, enabled: true },
  last_job: { id: 'nightly-job', state: 'running', requested_count: 10, validated_count: 5, error_code: null, result: null },
});
const ready = (): NightlyState => ({ ...running(), last_job: { id: 'nightly-job', state: 'published', requested_count: 10, validated_count: 10, error_code: null,
  result: { test: { type: 'saved_test', id: 'same-test' }, version: { type: 'saved_test_version', id: 'same-version' }, available: true } },
});
beforeEach(() => {
  vi.resetAllMocks(); mocks.readNightly.mockResolvedValue(status());
  mocks.readPreferences.mockResolvedValue(status().preferences);
  mocks.savePreferences.mockImplementation(async body => ({ enabled: body.enabled, local_time: body.local_time, question_count: body.question_count, revision: body.expected_revision + 1 }));
});
afterEach(() => { cleanup(); vi.useRealTimers(); });
const timeField = () => screen.getByLabelText('Preferred time') as HTMLInputElement;

it('loads actual Off defaults and exposes local time and exact five/ten/twenty choices', async () => {
  render(<NightlyPreferences />);
  await screen.findByRole('heading', { name: 'Nightly generation' });
  expect(screen.getByText('Off')).toBeTruthy();
  expect(timeField().value).toBe('22:00');
  for (const count of [5, 10, 20]) expect(screen.getByRole('button', { name: count + ' questions' }).getAttribute('aria-pressed')).toBe(String(count === 5));
  expect(screen.getByText(/Reopening or restoring waits/)).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Generate now' })).toBeNull();
  expect(mocks.savePreferences).not.toHaveBeenCalled();
});

it('claims one preference command on repeated clicks and reports the saved On state', async () => {
  let complete!: (value: unknown) => void;
  mocks.savePreferences.mockImplementation(() => new Promise(resolve => { complete = resolve; }));
  render(<NightlyPreferences />);
  const turnOn = await screen.findByRole('button', { name: 'Turn on' });
  fireEvent.click(turnOn); fireEvent.click(turnOn);
  expect(mocks.savePreferences).toHaveBeenCalledTimes(1);
  expect(mocks.savePreferences.mock.calls[0][0]).toEqual({ enabled: true, local_time: '22:00', question_count: 5, expected_revision: 1 });
  await act(async () => complete({ ...status().preferences, enabled: true, revision: 2 }));
  expect(screen.getByText('On')).toBeTruthy();
});

it('retains unsaved time/count after a lost response and reuses the exact retry key', async () => {
  mocks.savePreferences.mockRejectedValueOnce(new ApiError('The response was lost. Retry.', 0, 'unavailable', true));
  render(<NightlyPreferences />);
  await screen.findByRole('heading', { name: 'Nightly generation' });
  fireEvent.change(timeField(), { target: { value: '21:15' } });
  fireEvent.click(screen.getByRole('button', { name: '20 questions' }));
  fireEvent.click(screen.getByRole('button', { name: 'Save preferences' }));
  await screen.findByRole('alert');
  expect(timeField().value).toBe('21:15');
  expect(screen.getByRole('button', { name: '20 questions' }).getAttribute('aria-pressed')).toBe('true');
  fireEvent.click(screen.getByRole('button', { name: 'Save preferences' }));
  await waitFor(() => expect(mocks.savePreferences).toHaveBeenCalledTimes(2));
  expect(mocks.savePreferences.mock.calls[1].slice(0, 2)).toEqual(mocks.savePreferences.mock.calls[0].slice(0, 2));
  await screen.findByText('Nightly preferences saved. Generation is off.');
});

it('reloads a conflicted canonical revision while preserving the typed draft', async () => {
  mocks.savePreferences.mockRejectedValueOnce(new ApiError('Preferences changed. Your draft is retained.', 409, 'revision_conflict'));
  mocks.readPreferences.mockResolvedValue({ ...status().preferences, revision: 7 });
  render(<NightlyPreferences />);
  await screen.findByRole('heading', { name: 'Nightly generation' });
  fireEvent.change(timeField(), { target: { value: '19:30' } });
  fireEvent.click(screen.getByRole('button', { name: '10 questions' }));
  fireEvent.click(screen.getByRole('button', { name: 'Save preferences' }));
  await waitFor(() => expect(mocks.readPreferences).toHaveBeenCalledTimes(1));
  await waitFor(() => expect((screen.getByRole('button', { name: 'Save preferences' }) as HTMLButtonElement).disabled).toBe(false));
  expect(timeField().value).toBe('19:30');
  fireEvent.click(screen.getByRole('button', { name: 'Save preferences' }));
  await waitFor(() => expect(mocks.savePreferences).toHaveBeenCalledTimes(2));
  expect(mocks.savePreferences.mock.calls[1][0]).toEqual({ enabled: false, local_time: '19:30', question_count: 10, expected_revision: 7 });
});

it('permits immediate Off during Test using saved settings even when a draft time is invalid', async () => {
  mocks.readNightly.mockResolvedValue({ ...running(), assistance_allowed: false });
  render(<NightlyPreferences assistanceAllowed={false} />);
  await screen.findByRole('heading', { name: 'Nightly generation' });
  fireEvent.change(timeField(), { target: { value: '' } });
  expect((screen.getByRole('button', { name: 'Save preferences' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: 'Turn off' }));
  await screen.findByText('Off');
  expect(mocks.savePreferences.mock.calls[0][0]).toEqual({ enabled: false, local_time: '22:00', question_count: 5, expected_revision: 1 });
  expect(timeField().value).toBe('');
  expect((screen.getByRole('button', { name: 'Turn on' }) as HTMLButtonElement).disabled).toBe(true);
});

it('aborts an in-flight save when Settings unmounts', async () => {
  mocks.savePreferences.mockImplementation(() => new Promise(() => {}));
  const view = render(<NightlyPreferences />);
  fireEvent.click(await screen.findByRole('button', { name: 'Turn on' }));
  const signal = mocks.savePreferences.mock.calls[0][2] as AbortSignal;
  expect(signal.aborted).toBe(false); view.unmount(); expect(signal.aborted).toBe(true);
});

it('opens the exact canonical saved test/version once through the parent callback', async () => {
  const open = vi.fn(); mocks.readNightly.mockResolvedValue(ready());
  render(<NightlyStatus onOpenTest={open} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Open saved test' }));
  expect(open).toHaveBeenCalledExactlyOnceWith({ test_id: 'same-test', version_id: 'same-version' });
  expect(screen.getByText('10 questions')).toBeTruthy();
  expect(mocks.cancelNightly).not.toHaveBeenCalled();
});

it('marks a deleted published version unavailable and offers no stale open', async () => {
  const data = ready(); data.last_job!.result!.available = false; data.last_job!.result!.test = null;
  mocks.readNightly.mockResolvedValue(data);
  render(<NightlyStatus onOpenTest={vi.fn()} />);
  await screen.findByText('This saved test is unavailable.');
  expect(screen.queryByRole('button', { name: 'Open saved test' })).toBeNull();
});

it('keeps neutral Stop during Test and refreshes a publication winner without changing identity', async () => {
  mocks.readNightly.mockResolvedValueOnce({ ...running(), assistance_allowed: false }).mockResolvedValue({ ...ready(), assistance_allowed: false });
  mocks.cancelNightly.mockResolvedValue({ id: 'nightly-job', state: 'published' });
  render(<NightlyStatus onOpenTest={vi.fn()} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Stop generation' }));
  await screen.findByText('Ready');
  expect(mocks.cancelNightly.mock.calls[0][0]).toBe('nightly-job');
  expect((screen.getByRole('button', { name: 'Open saved test' }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.queryByRole('button', { name: 'Stop generation' })).toBeNull();
});

it('retains a failed Stop receipt for an explicit retry', async () => {
  mocks.readNightly.mockResolvedValue(running());
  mocks.cancelNightly.mockRejectedValueOnce(new ApiError('Stop failed. Retry.', 503, 'unavailable', true)).mockResolvedValue({ id: 'nightly-job', state: 'cancelled' });
  render(<NightlyStatus />);
  fireEvent.click(await screen.findByRole('button', { name: 'Stop generation' }));
  await screen.findByRole('alert');
  fireEvent.click(screen.getByRole('button', { name: 'Stop generation' }));
  await waitFor(() => expect(mocks.cancelNightly).toHaveBeenCalledTimes(2));
  expect(mocks.cancelNightly.mock.calls[1].slice(0, 2)).toEqual(mocks.cancelNightly.mock.calls[0].slice(0, 2));
});

it('shows retained short work without claiming Ready or accepting it automatically', async () => {
  const review = vi.fn(); const data = running(); data.last_job = { ...data.last_job!, state: 'needs_review', error_code: 'generation_short_batch', validated_count: 3 };
  mocks.readNightly.mockResolvedValue(data);
  render(<NightlyStatus onReviewJob={review} />);
  await screen.findByText('Needs review');
  expect(screen.getByText('3 of 10 questions validated')).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Open saved test' })).toBeNull();
  expect(review).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Review retained work' }));
  expect(review).toHaveBeenCalledExactlyOnceWith('nightly-job');
});

it('polls reads while active, preserves Stop after a read failure and aborts on unmount', async () => {
  vi.useFakeTimers();
  mocks.readNightly.mockResolvedValueOnce(running()).mockRejectedValueOnce(new ApiError('Offline', 0, 'unavailable'));
  const view = render(<NightlyStatus />);
  await act(async () => {});
  expect(screen.getByRole('button', { name: 'Stop generation' })).toBeTruthy();
  await act(async () => { await vi.advanceTimersByTimeAsync(5_000); });
  expect(mocks.readNightly).toHaveBeenCalledTimes(2);
  expect(screen.getByRole('button', { name: 'Stop generation' })).toBeTruthy();
  expect(screen.getByRole('alert')).toBeTruthy();
  const signal = mocks.readNightly.mock.calls[1][0] as AbortSignal;
  view.unmount(); expect(signal.aborted).toBe(true);
  await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
  expect(mocks.readNightly).toHaveBeenCalledTimes(2);
});
