import type { ContentLocator, ContentReference } from '../../platform/designC';

export interface ReaderBlock {
  kind: 'paragraph' | 'heading' | 'list_item' | 'code' | 'image';
  item_ref: string; text: string; level: number | null;
  locator: ContentLocator | null; asset_id: string | null;
}
export interface ReaderCell {
  display: string; value: string | number | boolean | null;
  number_format: string | null; formula: string | null; cached: boolean;
}
export interface ReaderTable {
  format: 'csv' | 'xlsx'; sheet_name: string | null; sheets: string[];
  first_row: number; total_rows: number; total_columns: number; rows: ReaderCell[][];
}
export interface ReaderPayload {
  schema_version: 'reader/1'; kind: 'text' | 'table' | 'pdf' | 'image';
  blocks: ReaderBlock[]; table: ReaderTable | null;
  page: number | null; pages: number | null; asset_id: string | null;
  diagnostics: { code: string; message: string }[];
}
export interface ReaderDocument {
  schema_version: 'reader/1'; reference: ContentReference; title: string; media_type: string;
  authority: 'knowledge' | 'case';
  original: { id: string; sha256: string; bytes: number; filename: string; available: boolean };
  attachment_revision: number | null; preview_state: 'ready' | 'failed' | 'unsupported';
  policy_revision: number | null; context_epoch: number | null;
  extraction_state: 'ready' | 'unavailable';
  capabilities: { read: boolean; original: boolean; passage: boolean; ocr: boolean; model_image: boolean };
  payload: ReaderPayload | null; error: { code: string; message: string } | null;
}
