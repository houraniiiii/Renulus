import type { ContentLocator, ContentReference } from '../../platform/designC';

export interface TextSpan { start: number; end: number }
export interface ImportOption { id: string; text: string }
export interface ImportCandidate {
  id: string; stem: string; options: ImportOption[]; explanation: string; topic_id: string;
  correct_option_ids: string[]; key_state: 'missing' | 'ambiguous' | 'supplied' | 'resolved';
  review_confirmed: boolean; removed: boolean; normalized: boolean; edited?: boolean;
  original: { span: TextSpan; stem_span: TextSpan; options: { id: string; span: TextSpan }[];
    key_span: TextSpan | null; supplied_key_ids: string[]; explanation_span?: TextSpan | null };
}
export interface ImportedVersion { test_id: string; version_id: string }
export interface ImportDraft {
  id: string; title: string; state: 'draft' | 'running' | 'failed' | 'cancelled' | 'published';
  revision: number; source_kind: 'paste' | 'library_revision'; source_revision_id: string | null;
  candidates: ImportCandidate[]; candidate_count: number; call_count: number; max_calls: number;
  error_code: string | null; result: ImportedVersion | null; result_available: boolean;
  created_at: string; updated_at: string;
}
export interface ImportPage { items: Omit<ImportDraft, 'candidates'>[] }
export interface ImportOriginal {
  text: string; sha256: string;
  original: { terms: string; rights: Record<string, unknown>;
    source_pin: { title?: string; reference?: ContentReference; [key: string]: unknown } | null;
    segments: { start: number; end: number; locator?: ContentLocator; reference?: ContentReference }[];
    diagnostics: { code?: string; message?: string }[] };
}
export type ImportIntent = { title: string; original:
  { kind: 'paste'; text: string; terms: string; permission_confirmed: true } |
  { kind: 'library_revision'; revision_id: string } };
export interface ImportCancellation { id: string; state: ImportDraft['state'] }

/** Backend offsets count Unicode characters rather than UTF-16 code units. */
export function originalSlice(text: string, span: TextSpan) { return Array.from(text).slice(span.start, span.end).join(''); }

export function keyLabel(candidate: ImportCandidate) {
  if (candidate.removed) return 'Removed from set';
  if (candidate.review_confirmed) return 'Reviewed by you';
  if (candidate.edited) return 'Review after edit';
  return candidate.key_state === 'missing' ? 'Answer missing' : candidate.key_state === 'ambiguous' ? 'Original keys conflict' : 'Needs your review';
}
export function importMessage(draft: ImportDraft) {
  if (draft.state === 'published') return 'Saved as personal practice. Start Study or Test from setup when you are ready.';
  if (draft.state === 'running') return 'Normalizing formatting with your selected connection. The original stays unchanged.';
  if (draft.error_code === 'interrupted') return 'Normalization was interrupted. The original and your saved edits remain. Retry explicitly when ready.';
  if (draft.error_code === 'import_edits_changed') return 'Your edits changed during normalization. The later response was discarded and your edits are retained.';
  if (draft.error_code === 'import_invalid_output') return 'The response could not be mapped safely to the original. Your original and edits are retained.';
  if (draft.state === 'failed') return 'Normalization could not finish. Your original and edits are retained. Check the connection or source, then retry explicitly.';
  if (draft.state === 'cancelled') return 'Normalization is stopped. Continue reviewing the retained original and candidates.';
  return 'Check each question against the original, resolve its answer and explicitly save your personal set.';
}
