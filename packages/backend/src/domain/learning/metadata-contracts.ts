// SPDX-License-Identifier: MIT
import type { ConversationSummary } from '../../storage/contracts.ts';

/** Fully defaulted NewConversation.model_dump(mode='json'); no Case/temporary admission. */
export interface SavedLearningCreate {
  kind: 'learning'; title: string; temporary: false; project_id: string | null;
  topic_id: string | null; teaching_style: 'direct' | 'guided'; text: ''; teaching_case_id: null;
}
export type ContentLocator =
  | { kind: 'pdf'; physical_page: number; printed_label: string | null }
  | { kind: 'text'; item_ref: string; section: string | null; start: number; end: number }
  | { kind: 'table'; format: 'csv' | 'xlsx'; sheet_name: string | null;
      first_row: number; last_row: number; first_column: number; last_column: number }
  | { kind: 'image'; frame: number; bounds: [number, number, number, number] | null };
export interface ContentReference {
  target: { type: 'library_revision' | 'note_revision' | 'attachment' | 'saved_test_version'; id: string };
  locator: ContentLocator | null;
}
export interface ConversationDraft { text: string; content_refs: ContentReference[]; revision: number; conversation_revision: number }
export interface DraftRequest { expected_revision: number; text: string; content_refs: ContentReference[] }
export type RunState = 'running' | 'completed' | 'cancelled' | 'failed' | 'interrupted';
export interface RunStatus {
  run_id: string; state: RunState; conversation?: ConversationSummary;
  error?: { code: string; message: string; retryable: boolean };
}
export type LearningMetadataCommand =
  | { type: 'learning.create'; request: SavedLearningCreate; idempotencyKey: string | null }
  | { type: 'learning.get'; threadId: string }
  | { type: 'learning.list'; limit: number; cursor: string | null; lifecycle: 'active' | 'archived'; projectId: string | null }
  | { type: 'learning.draft.get'; threadId: string }
  | { type: 'learning.draft.save'; threadId: string; request: DraftRequest; idempotencyKey: string | null }
  | { type: 'learning.runs.list'; threadId: string; limit: number; cursor: string | null }
  | { type: 'learning.run.status'; threadId: string; runId: string; neutral: boolean };
export interface LearningMetadataResults {
  'learning.create': ConversationSummary;
  'learning.get': ConversationSummary;
  'learning.list': { items: ConversationSummary[]; next_cursor: string | null };
  'learning.draft.get': ConversationDraft;
  'learning.draft.save': ConversationDraft;
  'learning.runs.list': { items: Pick<RunStatus, 'run_id' | 'state'>[]; next_cursor: string | null };
  'learning.run.status': RunStatus;
}
/** Composes into the integration writer. No separate database or transaction owner. */
export interface LearningMetadataStorage {
  command<C extends LearningMetadataCommand>(command: C): Promise<LearningMetadataResults[C['type']]>;
}
