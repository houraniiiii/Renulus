import { ApiError } from '../../platform/api';
import { startStudyAttempt } from '../attempts/start';
import type { Attempt } from '../attempts/types';
import { startQuickPractice, readChatTestRun, readChatTestResult, type ChatTestRun, type ChatTestResult } from '../chat/api';

/** One Home command's volatile receipts. Source text is never persisted here. */
export interface QuickPracticeCommand {
  text: string; request_id: string; run?: ChatTestRun; result?: ChatTestResult; attempt?: Attempt;
}
const abort = () => new DOMException('Request cancelled.', 'AbortError');
function check(signal: AbortSignal) { if (signal.aborted) throw abort(); }
function pause(signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const cancelled = () => { clearTimeout(timer); reject(abort()); };
    const timer = setTimeout(() => { signal.removeEventListener('abort', cancelled); resolve(); }, 1000);
    signal.addEventListener('abort', cancelled, { once: true });
    if (signal.aborted) cancelled();
  });
}

export async function prepareQuickPractice(command: QuickPracticeCommand, signal: AbortSignal,
  onRun?: (run: ChatTestRun) => void): Promise<Attempt> {
  check(signal);
  if (command.attempt) return command.attempt;
  command.run ??= await startQuickPractice({ text: command.text, request_id: command.request_id, count: 5 }, signal);
  check(signal);
  onRun?.(command.run);
  const deadline = performance.now() + 240_000;
  while (command.run.state === 'queued' || command.run.state === 'running') {
    if (performance.now() >= deadline) throw new ApiError('Quick practice is still preparing. Your draft is kept; retry to check this request.', 0, 'quick_practice_pending', true);
    await pause(signal);
    command.run = await readChatTestRun(command.run.run_id, signal);
    onRun?.(command.run);
  }
  if (command.run.state !== 'published') throw new ApiError('Quick practice did not finish. Your draft is kept.', 409, 'quick_practice_' + command.run.state, true);
  check(signal);
  command.result ??= await readChatTestResult(command.run.run_id, signal);
  const result = command.result, start = result.study_start;
  // This is the trusted backend's saved-version descriptor, never a renderer artifact.
  if (result.item_count !== 5 || !result.test_id || !result.version_id ||
      start?.version.type !== 'saved_test_version' || start.version.id !== result.version_id ||
      start.mode !== 'study' || start.timing?.kind !== 'untimed' || !start.idempotency_key) {
    throw new ApiError('The saved five-question Study result is unavailable. Your draft is kept.', 409, 'quick_practice_result_invalid');
  }
  check(signal);
  const attempt = await startStudyAttempt(result.version_id, start.idempotency_key);
  if (attempt.version_id !== result.version_id || attempt.mode !== 'study' ||
      attempt.timing.kind !== 'untimed' || attempt.item_count !== 5 || !attempt.id) {
    throw new ApiError('The Study handoff could not be verified. Your draft is kept.', 409, 'quick_practice_attempt_invalid');
  }
  command.attempt = attempt;
  check(signal);
  return attempt;
}
