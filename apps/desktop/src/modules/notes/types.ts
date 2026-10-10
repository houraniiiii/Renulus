import type { ContentReference } from '../../platform/designC';
export interface NoteSummary {
  document_id: string; revision_id: string; ordinal: number; title: string; updated_at: string;
  reference: ContentReference;
}
export interface Note extends NoteSummary { text: string }
export interface NoteDraft { title: string; text: string; base?: Note }
export interface NoteCommand { key: string; method: string; url: string; body?: unknown; headers: Record<string, string> }
