import type { ContextScope, RunEvent } from '../../platform/contracts';

export type PracticeContext = 'study' | 'temporary' | 'unclassified';

export interface PracticeCapabilities {
  available: boolean;
  reason: string | null;
  live_provider_verified: false;
}

export interface GeneratePracticeRequest {
  idempotency_key: string;
  prompt: string;
  count: number;
  topic_id?: string;
  context: PracticeContext;
  case_handoff_id?: string;
}

export interface PracticeItem {
  id: string;
  ordinal: number;
  kind: 'single_best_answer';
  stem: string;
  options: { id: string; text: string }[];
  assisted: boolean;
}

export interface PracticeCitation {
  source_id: string;
  locator: string;
  title?: string | null;
  url?: string | null;
  edition?: string | null;
  checked_on?: string | null;
  document_revision?: string | number | null;
  // Structured document locators belong to the content module. Render their
  // recognised labels without exposing the underlying JSON.
  locators?: unknown[];
}

export interface PracticeScoreBucket {
  answered: number;
  correct: number;
  accuracy: number | null;
}

export interface PracticeScores {
  unassisted: PracticeScoreBucket;
  assisted: PracticeScoreBucket;
}

export interface PracticeFeedback {
  attempt_id: string;
  item: PracticeItem;
  selected_option_ids: string[];
  correct_option_ids: string[];
  correct: boolean;
  assisted: boolean;
  committed_at: string;
  explanation: string;
  options: { id: string; text: string; rationale: string | null }[];
  sources: PracticeCitation[];
  verification: 'generated-unreviewed';
}

export interface PracticeSession {
  id: string;
  mode: 'generated';
  scope: ContextScope;
  retention: 'persistent' | 'volatile';
  status: 'active' | 'paused' | 'ended';
  created_at: string;
  updated_at: string;
  item_count: number;
  answered_count: number;
  current_item: PracticeItem | null;
  scores: PracticeScores;
  source_verification: 'retrieved' | 'not-verified';
  topic_id: string | null;
}

export interface PracticeAnswerResult {
  feedback: PracticeFeedback;
  session: PracticeSession;
}

export interface PracticeHelpResult {
  item_id: string;
  assisted: true;
  kind: 'hint' | 'sources';
  hint: string | null;
  sources: PracticeCitation[];
}

export interface PracticeReview {
  session_id: string;
  feedback: PracticeFeedback[];
  scores: PracticeScores;
}

export interface PracticeRetrieval {
  verification: 'retrieved' | 'not-verified' | 'not-requested' | 'retrieval-failed';
  passage_count: number;
}

/** The SSE data is the RunEvent envelope, not its payload alone. */
export type PracticeRunEvent = RunEvent & (
  | { type: 'started'; payload: { scope: ContextScope; mode: 'generated'; persistent: boolean } }
  | { type: 'retrieval'; payload: PracticeRetrieval }
  | { type: 'progress'; payload: { received_characters: number } }
  | { type: 'completed'; payload: { session: PracticeSession } }
  | { type: 'error'; payload: { code: string; message: string; retryable: boolean } }
  | { type: 'cancelled'; payload: Record<string, never> }
);
