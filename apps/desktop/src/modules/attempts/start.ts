import { api } from '../../platform/api';
import type { Attempt } from './types';

/** Reuse the caller's stable command key after an ambiguous start acknowledgement. */
export async function startStudyAttempt(versionId: string, idempotencyKey: string): Promise<Attempt> {
  return api<Attempt>('/assessment/test-attempts', { method: 'POST',
    headers: { 'Idempotency-Key': idempotencyKey },
    body: { version: { type: 'saved_test_version', id: versionId }, mode: 'study', timing: { kind: 'untimed' } },
  });
}
