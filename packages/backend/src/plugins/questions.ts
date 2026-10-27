// SPDX-License-Identifier: MIT
import type { Tool } from '@opencode/schema/tool';
import { reject } from '../storage/contracts.ts';
import type { CapabilityEnvelope } from '../domain/capabilities/contracts.ts';

export interface PendingQuestion {
  readonly id: string; readonly session_id: string; readonly grant_epoch: number; readonly input: unknown;
}
/** App question UI for the native `question` tool. An answer binds the pending call and its grant epoch. */
export function createQuestions() {
  const pending = new Map<string, PendingQuestion & { settle(result: Tool.Result | Error): void }>();
  return {
    ask(input: unknown, envelope: CapabilityEnvelope, signal: AbortSignal): Promise<Tool.Result> {
      const id = envelope.call_id;
      if (pending.has(id)) reject('question_already_pending');
      return new Promise((resolve, fail) => {
        const settle = (result: Tool.Result | Error) => {
          signal.removeEventListener('abort', cancel); pending.delete(id);
          return result instanceof Error ? fail(result) : resolve(result);
        };
        const cancel = () => settle(new Error('question_cancelled'));
        pending.set(id, { id, session_id: envelope.session_id, grant_epoch: envelope.grant_epoch, input, settle });
        if (signal.aborted) cancel(); else signal.addEventListener('abort', cancel, { once: true });
      });
    },
    list: (): PendingQuestion[] => [...pending.values()].map(({ settle: _settle, ...question }) => question),
    answer(id: string, grantEpoch: number, answers: unknown, currentEpoch: number) {
      const question = pending.get(id);
      if (!question || question.grant_epoch !== grantEpoch || currentEpoch !== grantEpoch) reject('question_stale');
      question.settle({ content: JSON.stringify({ answers }) });
    },
    reject(id: string) {
      const question = pending.get(id);
      if (!question) reject('question_stale');
      question.settle(new Error('question_rejected'));
    },
    cancelAll() { for (const question of [...pending.values()]) question.settle(new Error('question_cancelled')); },
  };
}
export type Questions = ReturnType<typeof createQuestions>;
