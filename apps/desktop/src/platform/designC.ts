/** Shared Design C references. Domain records stay in the local backend. */
export type ConversationKind = 'learning' | 'case';
export type Retention = 'saved' | 'temporary';
export type Lifecycle = 'active' | 'archived' | 'deleted';
export interface ConversationIdentity { type: 'learn_thread' | 'case'; id: string }
export type ContentIdentity = { type: 'library_revision' | 'attachment' | 'note_revision' | 'saved_test_version'; id: string };
export type ContentLocator =
  | { kind: 'pdf'; physical_page: number; printed_label?: string | null }
  | { kind: 'text'; item_ref: string; section?: string | null; start: number; end: number }
  | { kind: 'table'; format: 'csv' | 'xlsx'; sheet_name?: string | null; first_row: number; last_row: number; first_column: number; last_column: number }
  | { kind: 'image'; frame: number; bounds?: [number, number, number, number] | null };
export interface ContentReference { target: ContentIdentity; locator?: ContentLocator | null }
export interface ConversationSummary {
  identity: ConversationIdentity; kind: ConversationKind; retention: Retention; lifecycle: Lifecycle;
  revision: number; title: string; project_id: string | null; created_at: string; updated_at: string;
}
export interface PageResult<T> { items: T[]; next_cursor: string | null }
export interface ProjectSummary { id: string; title: string; lifecycle: Lifecycle; revision: number }
export interface PassageDraft { text: string; reference: ContentReference; title: string }
export interface AssessmentPolicy { active_test_id: string | null; revision: number; assistance_allowed: boolean }
/** Volatile receipt from one recorded Study-help exposure. */
export interface StudyHelpContext {
  attempt_id: string; item_id: string; version_id: string; draft_revision: number; policy_revision: number;
  kind: 'hint' | 'sources' | 'notes' | 'chat';
}
export const studyHelpHeaders = (context?: StudyHelpContext): Record<string, string> => context
  ? { 'X-Renulus-Study-Context': JSON.stringify(context) } : {};
/** Readers only open canonical references; passage use is explicit and does not send. */
export interface ReaderProps {
  reference: ContentReference; conversation?: ConversationIdentity;
  studyHelpContext?: StudyHelpContext;
  onPassage?: (passage: PassageDraft) => void;
}
export const conversationKey = (identity: ConversationIdentity) => identity.type + ':' + identity.id;
export const contentKey = (reference: ContentIdentity) => reference.type + ':' + reference.id;
