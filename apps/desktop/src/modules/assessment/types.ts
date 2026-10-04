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
export interface SourceCurrency {
  state: 'available' | 'unavailable';
  needs_re_review: boolean | null;
  annotations: {
    entry_id: string; pinned_source_id: string; register_id: string; locators: string[];
    detected_at: string; state: 'needs-re-review' | 'dismissed';
    review_state: 'pending' | 'reviewed' | 'dismissed';
  }[];
}
export interface SessionSourceCurrency {
  state: 'available' | 'partial' | 'unavailable';
  needs_re_review: boolean | null;
  affected_count: number; pending_affected_count: number; dismissed_count: number;
  question_count: number; notice_count: number;
}
export interface Item {
  id: string; ordinal: number; question_id: string; question_version: string;
  key_version: string; family_id: string; family_version: string;
  topic_id: string; domain_id: string; kind: 'single_best_answer'; stem: string;
  options: { id: string; text: string }[]; assisted: boolean;
  repeat?: boolean; content_status?: ContentStatus; source_currency?: SourceCurrency;
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
  source_currency?: SourceCurrency;
}
export interface Session {
  id: string; mode: 'reviewed'; scope: { kind: 'reviewed-assessment'; entity_id: string };
  status: 'active' | 'paused' | 'ended'; created_at: string; updated_at: string; ended_at: string | null;
  selector: { domain_ids: string[]; topic_ids: string[]; track: string | null };
  coverage: { requested_count: number; selected_count: number; available_families: number;
    insufficient_count: boolean; missing_topic_ids: string[]; missing_domain_ids: string[];
    complete_exam_available: false; note: string };
  item_count: number; answered_count: number; scores: Scores; current_item: Item | null;
  source_currency?: SessionSourceCurrency;
}
export interface Catalog {
  mode: 'reviewed'; domains: { id: string; label: string; available_families: number }[];
  available_families: number; tracks: { id: string; available: boolean; reason?: string }[];
  complete_exam_available: false; coverage_note: string;
  generated: { available: boolean; reason: string | null };
}
export interface AnswerResult { feedback: Feedback; session: Session }
export interface ReviewResult { session_id: string; feedback: Feedback[]; scores: Scores;
  unanswered_feedback_available: false }
export interface HelpResult { item_id: string; assisted: true; kind: 'hint' | 'sources';
  hint: string | null; sources: Citation[] }
