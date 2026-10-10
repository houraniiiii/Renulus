import { api } from '../../platform/api';
import { stream } from '../../platform/stream';
import type { ContentReference, ConversationSummary } from '../../platform/designC';

export interface SendIntent { text: string; request_id: string }
export interface RunEvent {
  run_id: string; sequence: number; type: string;
  payload: { text?: string; message?: string; code?: string; retryable?: boolean;
    conversation?: ConversationSummary; [key: string]: unknown };
}
export interface ConversationRun {
  run_id: string; state: string; conversation?: ConversationSummary; partial_text?: string;
  error?: {code: string; message: string; retryable: boolean};
}
export const conversationPath = (chat: Pick<ConversationSummary, 'kind' | 'identity'>) =>
  '/conversations/' + chat.kind + '/' + encodeURIComponent(chat.identity.id);

export function createConversation(
  input: {kind?: 'learning' | 'case'; title?: string; temporary?: boolean; project_id?: string | null; teaching_case_id?: string},
  signal?: AbortSignal,
): Promise<ConversationSummary> {
  return api('/conversations', {method: 'POST', body: input, signal,
    headers: {'Idempotency-Key': crypto.randomUUID()}});
}

export async function sendConversation(
  conversation: ConversationSummary,
  input: {text: string; request_id: string; expected_revision: number;
    teaching_style?: 'direct' | 'guided'; topic_id?: string | null; model?: string | null;
    freshness?: boolean; content_refs?: ContentReference[]},
  onEvent: (event: RunEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  for await (const event of stream<RunEvent>(conversationPath(conversation) + '/messages', {
    method: 'POST', body: input, signal, headers: {'Idempotency-Key': input.request_id},
  })) onEvent(event.data);
}
