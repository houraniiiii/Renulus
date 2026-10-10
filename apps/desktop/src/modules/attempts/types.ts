import type { AssessmentPolicy, ContentReference } from '../../platform/designC';

export type Mode = 'study' | 'test';
export type Origin = 'reviewed_bank' | 'generated' | 'imported' | 'nightly';
export interface DraftAnswer { item_id: string; option_ids: string[]; marked: boolean }
export interface Draft { position: number; answers: DraftAnswer[] }
export interface Question {
  item_id: string; question_id: string; question_version: string; key_version: string | null;
  family_id: string; family_version: string; topic_id: string; stem: string;
  options: { id: string; text: string }[]; repeat?: boolean; availability?: string;
}
export interface Commitment {
  commit_id: string; item_id: string; selected_option_ids: string[]; committed_at: string;
  assisted: boolean; repeat: boolean; score_bucket: 'fresh' | 'assisted' | 'repeat' | 'personal';
  correct: boolean; outcome: 'correct' | 'incorrect' | 'unanswered' | 'excluded';
  exclusion_reason: string | null; question: Question; evidence_id: string | null;
  feedback: { correct_option_ids: string[]; explanation: string };
}
export interface Result {
  attempt_id: string; version_id: string; origin: Origin; mode: Mode; items: Commitment[];
  correct: number; denominator: number; excluded: number; unanswered: number;
  not_submitted: number; item_count: number; reason: string; finalized_at: string;
  cohorts: Record<Commitment['score_bucket'], { answered: number; correct: number; denominator: number; unanswered: number }>;
}
export interface Attempt extends Draft {
  id: string; version_id: string; origin: Origin; review_quality: string; mode: Mode;
  status: 'active' | 'paused' | 'timer_expired' | 'submitted' | 'ended';
  item_count: number; provenance_unavailable: boolean; draft_revision: number;
  current_item: Question | null; committed: Commitment[]; result: Result | null;
  timing: { kind: 'untimed' | 'timed'; duration_seconds: number | null; deadline_at: string | null; paused_seconds: number; remaining_seconds: number | null };
  policy: AssessmentPolicy;
}
export interface Setup {
  test: { id: string; title: string; lifecycle: string };
  version: { id: string; origin: Origin; review_quality: string; ordinal: number; item_count: number };
  can_start: boolean; content_warnings: { item_id: string; status: string }[]; timing_default: 'untimed';
}
export interface HelpReceipt {
  hint: string | null; references: ContentReference[]; assisted: boolean;
  context: { attempt_id: string; item_id: string; version_id: string; draft_revision: number; policy_revision: number; kind: 'hint' | 'sources' | 'notes' | 'chat' };
}
export interface AttemptSummary { id: string; version_id: string; mode: Mode; status: Attempt['status']; created_at: string; finalized_at: string | null }
export const draftOf = (attempt: Attempt): Draft => ({ position: attempt.position, answers: attempt.answers.map(answer => ({ ...answer, option_ids: [...answer.option_ids] })) });
export const originLabel: Record<Origin, string> = { reviewed_bank: 'Reviewed bank', generated: 'Generated practice', imported: 'Imported practice', nightly: 'Nightly practice' };
