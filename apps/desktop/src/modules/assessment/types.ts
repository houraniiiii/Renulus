export interface ScoreBucket { answered: number; correct: number; accuracy: number | null }
export interface Scores {
  reviewed: Record<'fresh' | 'assisted' | 'repeat', ScoreBucket>;
  generated: { available: boolean; answered: number };
  bucket_policy: string;
}
export interface ContentStatus {
  status: 'current' | 'corrected' | 'withdrawn' | 'inactive' | 'unavailable';
  withdrawn: boolean | null;
  current_version: number | null;
  withdrawal: { reason: string; replacement_version: number | null } | null;
  message: string | null;
}
export interface Item {
  id: string; ordinal: number; question_id: string; question_version: string;
  key_version: string; family_id: string; family_version: string;
  topic_id: string; domain_id: string; kind: 'single_best_answer'; stem: string;
  options: { id: string; text: string }[]; assisted: boolean;
  repeat?: boolean; content_status?: ContentStatus;
}
export interface Citation {
  source_id: string; locator: string; title?: string; url?: string; edition?: string;
  checked_on?: string; check_status?: string; currency?: string;
}
export interface Feedback {
  attempt_id: string; item: Item; selected_option_ids: string[]; correct_option_ids: string[];
  correct: boolean; score_bucket: 'fresh' | 'assisted' | 'repeat'; assisted: boolean; repeat: boolean;
  committed_at: string; explanation: string;
  options: { id: string; text: string; rationale: string | null }[];
  sources: Citation[]; review: { status: string; independent_human_review?: boolean };
  content_status: ContentStatus;
}
export interface Session {
  id: string; mode: 'reviewed'; scope: { kind: 'reviewed-assessment'; entity_id: string };
  status: 'active' | 'paused' | 'ended'; created_at: string; updated_at: string; ended_at: string | null;
  selector: { domain_ids: string[]; topic_ids: string[]; track: string | null };
  coverage: { requested_count: number; selected_count: number; available_families: number;
    insufficient_count: boolean; missing_topic_ids: string[]; missing_domain_ids: string[];
    complete_exam_available: false; note: string };
  item_count: number; answered_count: number; scores: Scores; current_item: Item | null;
}
export interface Catalog {
  mode: 'reviewed'; domains: { id: string; label: string; available_families: number }[];
  available_families: number; tracks: { id: string; available: boolean; reason?: string }[];
  complete_exam_available: false; coverage_note: string;
  generated: { available: boolean; reason: string };
}
export interface AnswerResult { feedback: Feedback; session: Session }
export interface ReviewResult { session_id: string; feedback: Feedback[]; scores: Scores;
  unanswered_feedback_available: false }
export interface HelpResult { item_id: string; assisted: true; kind: 'hint' | 'sources';
  hint: string | null; sources: Citation[] }
