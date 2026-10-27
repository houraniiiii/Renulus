// SPDX-License-Identifier: MIT
export type Json = null | boolean | number | string | Json[] | { [key: string]: Json };
export type Rights = { display: boolean; cache: boolean; index: boolean; embedding: boolean; model_input: boolean;
  derivation: boolean; evaluation: boolean; redistribution: boolean; licence: string; permission_reference: string; attribution: string };
export type Metadata = { source_id: string; asset_role?: string[]; access_class?: string; original_sha256?: string | null;
  retracted?: boolean; superseded?: boolean; repository_removed?: boolean; access_changed?: boolean;
  excluded_pages?: number[]; [key: string]: Json | undefined };
export type Locator = { kind: 'pdf'; physical_page: number; printed_label?: string | null }
  | { kind: 'text'; item_ref: string; start: number; end: number; section?: string | null }
  | { kind: 'table'; format: 'csv' | 'xlsx'; sheet_name?: string | null; first_row: number; last_row: number; first_column: number; last_column: number }
  | { kind: 'image'; frame?: number; bounds?: [number, number, number, number] | null };
export interface ContentReference { target: { type: 'library_revision' | 'note_revision' | 'attachment'; id: string }; locator?: Locator | null }
export interface ReaderRequest { reference: ContentReference; conversation?: { type: 'learn_thread' | 'case'; id: string } | null;
  page?: number; sheet?: string | null; first_row?: number; row_limit?: number;
  expected_policy_revision?: number | null; expected_context_epoch?: number | null }
export interface ImportRequest { title: string; media_type: string; bytes: number; sha256: string; metadata: Metadata; rights: Rights;
  document_id: string | null; expected_revision_id: string | null; project_id: string | null; note: boolean; idempotency_key: string }
export interface ImportIntent { id: string; document_id: string; revision_id: string; job_id: string; reservation_id: string;
  request: ImportRequest; stamp: string; state: 'prepared' | 'original' | 'ready' | 'failed'; original_handle: string | null }
export interface SourcePin { reference: ContentReference; document_id: string | null; revision_id: string; title: string; filename: string;
  media_type: string; sha256: string; bytes: number; original_handle: string; rights: Rights; metadata: Metadata;
  stamp: string; fingerprint: string; policy_revision: number; context_epoch: number; attachment_revision: number | null }
export interface Passage { id: string; text: string; context_text: string; locators: Json[]; headings: string[] }
export interface NoteSummary { document_id: string; revision_id: string; ordinal: number; title: string; updated_at: string; reference: ContentReference }
export type KnowledgeCommand =
  | { type: 'knowledge.list'; limit: number; offset: number; query: string; status: string | null }
  | { type: 'knowledge.get'; documentId: string }
  | { type: 'knowledge.import.begin'; request: ImportRequest }
  | { type: 'knowledge.import.check'; intentId: string }
  | { type: 'knowledge.import.original'; intentId: string; originalHandle: string }
  | { type: 'knowledge.import.ready'; intentId: string; extraction: Json; passages: Passage[]; embeddingModel: string; chunkTokens: number }
  | { type: 'knowledge.import.fail'; intentId: string; code: string }
  | { type: 'knowledge.source.pin'; request: ReaderRequest; operation: 'display' | 'model_input' }
  | { type: 'knowledge.source.recheck'; pin: SourcePin; operation: 'display' | 'model_input' }
  | { type: 'knowledge.source.dependency'; pin: SourcePin }
  | { type: 'knowledge.notes.list'; projectId: string | null; limit: number; offset: number }
  | { type: 'knowledge.notes.pin'; documentId: string; revisionId: string | null }
  | { type: 'knowledge.delete'; documentId: string; expectedRevisionId: string | null; idempotencyKey: string; note: boolean }
  | { type: 'knowledge.cleanup'; revisionIds: string[] }
  | { type: 'knowledge.find'; query: string; projectId: string | null; after: string | null; limit: number; epoch: string | null };
export interface KnowledgeResults {
  'knowledge.list': { documents: Record<string, unknown>[]; total: number; limit: number; offset: number };
  'knowledge.get': Record<string, unknown>;
  'knowledge.import.begin': ImportIntent; 'knowledge.import.check': ImportIntent; 'knowledge.import.original': ImportIntent;
  'knowledge.import.ready': ImportIntent; 'knowledge.import.fail': ImportIntent;
  'knowledge.source.pin': SourcePin; 'knowledge.source.recheck': SourcePin;
  'knowledge.source.dependency': { target: { type: 'library_revision'; id: string }; expected_revision: string };
  'knowledge.notes.list': { items: NoteSummary[] }; 'knowledge.notes.pin': { summary: NoteSummary; pin: SourcePin };
  'knowledge.delete': { document_id: string; revision_id: string; deleted: true; revision_ids: string[] };
  'knowledge.cleanup': { removed: number };
  'knowledge.find': { items: { revision_id: string; title: string; status: string; note: boolean; text: string | null; locators_json: string | null }[]; next: string | null; epoch: string };
}
export interface KnowledgeStorage { command<C extends KnowledgeCommand>(command: C): Promise<KnowledgeResults[C['type']]> }
/** Native worker owns chooser/original/destination handle maps and all Windows I/O.
 * These callbacks are host injected; JSON requests cannot supply paths or mint handles.
 * reserve persists/binds the canonical intent before source/body I/O and enforces
 * the app budget, peak allocation and 12 GiB target-volume floor. settle does not
 * remove originals; failed publication stays journalled for explicit recovery.
 */
export interface KnowledgeNativeIO {
  reserve(intent: ImportIntent): Promise<void>;
  readSelection(input: { handle: string; intent: ImportIntent }, signal?: AbortSignal): Promise<Uint8Array>;
  publish(input: { intent: ImportIntent; body: Uint8Array }, signal?: AbortSignal): Promise<{ original_handle: string }>;
  settle(intent: ImportIntent): Promise<void>;
  read(pin: SourcePin, signal?: AbortSignal): Promise<Uint8Array>;
  payload(input: { pin: SourcePin; request: ReaderRequest; body: Uint8Array }, signal?: AbortSignal): Promise<ReaderPayload>;
  asset(input: { pin: SourcePin; request: ReaderRequest; body: Uint8Array; asset_id: string }, signal?: AbortSignal): Promise<Uint8Array>;
  handoff(input: { pin: SourcePin; action: 'open' | 'save'; destination_handle: string | null }, signal?: AbortSignal): Promise<{ handed_off: boolean }>;
}
export interface ReaderPayload { kind: 'text' | 'table' | 'pdf' | 'image'; blocks: Array<{ kind: string; item_ref: string; text: string; locator?: Locator | null }>;
  table?: { format: 'csv' | 'xlsx'; sheet_name: string | null; first_row: number; total_rows: number; total_columns: number;
    rows: Array<Array<{ display: string }>> } | null; [key: string]: unknown }
