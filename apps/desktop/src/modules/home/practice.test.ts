import { beforeEach, expect, it, vi } from 'vitest';
import { prepareQuickPractice, type QuickPracticeCommand } from './practice';

const mocks = vi.hoisted(() => ({ startQuickPractice: vi.fn(), readChatTestRun: vi.fn(), readChatTestResult: vi.fn(), startStudyAttempt: vi.fn() }));
vi.mock('../chat/api', () => mocks);
vi.mock('../attempts/start', () => mocks);
const result = () => ({ test_id: 'fictional-five', version_id: 'fictional-five-v1', item_count: 5,
  study_start: { version: { type: 'saved_test_version', id: 'fictional-five-v1' }, mode: 'study',
    timing: { kind: 'untimed' }, idempotency_key: 'backend-pinned-study-key' } });
const command = (): QuickPracticeCommand => ({ text: 'Original synthetic learning request', request_id: 'stable-volatile-request' });
beforeEach(() => {
  vi.resetAllMocks();
  mocks.startQuickPractice.mockResolvedValue({ run_id: 'volatile-run', state: 'published' });
  mocks.readChatTestResult.mockResolvedValue(result());
  mocks.startStudyAttempt.mockResolvedValue({ id: 'one-study', version_id: 'fictional-five-v1', item_count: 5,
    mode: 'study', timing: { kind: 'untimed' } });
});

it('uses the actual Chat helper contract then starts pinned exact-five untimed Study with its backend key', async () => {
  const current = command(), signal = new AbortController().signal;
  const attempt = await prepareQuickPractice(current, signal);
  expect(mocks.startQuickPractice).toHaveBeenCalledExactlyOnceWith({ text: current.text, request_id: current.request_id, count: 5 }, signal);
  expect(mocks.readChatTestResult).toHaveBeenCalledExactlyOnceWith('volatile-run', signal);
  expect(mocks.startStudyAttempt).toHaveBeenCalledExactlyOnceWith('fictional-five-v1', 'backend-pinned-study-key');
  expect(await prepareQuickPractice(current, signal)).toBe(attempt);
  expect(mocks.startStudyAttempt).toHaveBeenCalledTimes(1);
});

it('retains the same volatile UUID after lost creation acknowledgement and never supplies a renderer artifact', async () => {
  const current = command(), signal = new AbortController().signal;
  mocks.startQuickPractice.mockRejectedValueOnce(new Error('lost ACK'));
  await expect(prepareQuickPractice(current, signal)).rejects.toThrow('lost ACK');
  await prepareQuickPractice(current, signal);
  expect(mocks.startQuickPractice.mock.calls[0]).toEqual(mocks.startQuickPractice.mock.calls[1]);
  expect(Object.keys(mocks.startQuickPractice.mock.calls[0][0]).sort()).toEqual(['count', 'request_id', 'text']);
});

it('retries a lost Study ACK using the same saved receipt/key without regenerating or republishing', async () => {
  const current = command(), signal = new AbortController().signal;
  mocks.startStudyAttempt.mockRejectedValueOnce(new Error('lost Study ACK'));
  await expect(prepareQuickPractice(current, signal)).rejects.toThrow('lost Study ACK');
  await prepareQuickPractice(current, signal);
  expect(mocks.startQuickPractice).toHaveBeenCalledTimes(1);
  expect(mocks.readChatTestResult).toHaveBeenCalledTimes(1);
  expect(mocks.startStudyAttempt.mock.calls[0]).toEqual(mocks.startStudyAttempt.mock.calls[1]);
});

it.each(['short', 'other-version', 'test-mode', 'timed'])('refuses a mismatched saved Study descriptor: %s', async change => {
  const invalid = result();
  if (change === 'short') invalid.item_count = 4;
  if (change === 'other-version') invalid.study_start.version.id = 'other-version';
  if (change === 'test-mode') invalid.study_start.mode = 'test';
  if (change === 'timed') invalid.study_start.timing.kind = 'timed';
  mocks.readChatTestResult.mockResolvedValue(invalid);
  await expect(prepareQuickPractice(command(), new AbortController().signal)).rejects.toMatchObject({ code: 'quick_practice_result_invalid' });
  expect(mocks.startStudyAttempt).not.toHaveBeenCalled();
});

it('never starts Study for a failed/cancelled request or after its page is aborted', async () => {
  mocks.startQuickPractice.mockResolvedValue({ run_id: 'stopped-run', state: 'cancelled' });
  await expect(prepareQuickPractice(command(), new AbortController().signal)).rejects.toMatchObject({ code: 'quick_practice_cancelled' });
  const controller = new AbortController(); controller.abort();
  await expect(prepareQuickPractice(command(), controller.signal)).rejects.toMatchObject({ name: 'AbortError' });
  expect(mocks.readChatTestResult).not.toHaveBeenCalled();
  expect(mocks.startStudyAttempt).not.toHaveBeenCalled();
});
