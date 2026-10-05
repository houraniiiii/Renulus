export interface SourceMetadata {
  source_id: string; source_owner: string; canonical_url: string | null; edition: string | null;
  publication_date: string | null; received_at: string | null; checked_at: string | null;
  publication_status: string; latest_final_verified: boolean; content_reviewed: boolean;
  collection_section: string | null; collection_chapter: string | null; notes: string[];
  asset_role?: string[]; original_sha256?: string | null;
}
export interface Rights {
  display: boolean; cache: boolean; index: boolean; embedding: boolean; model_input: boolean;
  derivation: boolean; evaluation: boolean; redistribution: boolean; licence: string;
  permission_reference: string; attribution: string;
}
export interface Revision {
  id: string; document_id: string; ordinal: number; status: string; sha256: string;
  media_type: string; bytes: number; passage_count: number; metadata: SourceMetadata; rights: Rights;
}
export interface LibraryDocument {
  id: string; title: string; source_id: string; status: string; reserved: boolean;
  scope?: { kind: 'personal-library'; entity_id?: string | null };
  active_revision: string | null; latest_revision: string | null; revisions: Revision[]; cleanup_pending: boolean;
}
export interface Job { id: string; revision_id: string; state: string; phase: string; error_code: string | null; error_message: string | null }
export interface ImportResult { document_id: string; revision_id: string; status: string; job: Job }
export interface Locator {
  item_ref: string; page: number | null; char_span?: number[];
  format?: 'docx' | 'pptx' | 'xlsx'; table_ref?: string;
  slide?: number; slide_size?: { width: number; height: number };
  sheet?: number; sheet_name?: string | null;
  cell_bbox?: { l: number; t: number; r: number; b: number; coord_origin: string };
  bbox?: { l: number; t: number; r: number; b: number; coord_origin: string };
  page_size?: { width: number; height: number };
}
export interface Passage {
  id: string; text: string; context_text: string; document_id: string; document_revision: string;
  title: string; source_id: string; locators: Locator[]; metadata: SourceMetadata; rights: Rights; original_url: string;
}
export interface Citation {
  document_id: string; document_revision: string; passage_id?: string; title: string; page: number | null; locators: Locator[]; original_url: string;
}
export interface CatalogueEntry {
  id: string; title: string; source_id: string; eligibility: string; reserved: boolean; bytes: number;
  metadata: SourceMetadata; rights: Rights; document_id: string | null; job_id: string | null;
  processing_status: string; error_code: string | null;
}
export interface Catalogue { entries: CatalogueEntry[]; total: number; offset: number }
export interface Capabilities { text_import: boolean; pdf_image_import: boolean; office_import?: boolean; temporary_extraction: boolean }
