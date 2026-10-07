import { ApiError, api, type ApiOptions } from './api';
import type { RunEvent } from './contracts';
import { stream } from './stream';

/** Ordered run envelopes; drop duplicates/late events and stop at one terminal result. */
export async function* runEvents(path: string, options: ApiOptions & { runId?: string } = {}): AsyncGenerator<RunEvent> {
  const { runId: expected, ...request } = options;
  let runId = expected;
  let sequence = -1;
  let terminal = false;
  for await (const { data } of stream<RunEvent>(path, request)) {
    if (!data || typeof data.run_id !== 'string' || !Number.isInteger(data.sequence) || typeof data.type !== 'string' || !data.payload || typeof data.payload !== 'object') throw new ApiError('The runtime sent an invalid run event.', 0, 'invalid_event');
    runId ??= data.run_id;
    if (data.run_id !== runId || data.sequence <= sequence) continue;
    sequence = data.sequence;
    terminal = ['completed', 'cancelled', 'error'].includes(data.type);
    yield data;
    if (terminal) break;
  }
  if (!terminal) throw new ApiError('The runtime stream ended before the operation finished. Your input remains available.', 0, 'interrupted_stream', true);
}
/** Caller supplies its published module cancellation path and method. */
export function cancelRun(path: string, method: 'POST' | 'DELETE' = 'POST') {
  return api<{ run_id: string; cancelled: boolean }>(path, { method });
}
