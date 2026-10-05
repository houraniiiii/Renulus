// SPDX-License-Identifier: MIT
import type { ContextScope } from '../../platform/contracts';

export interface CaseMessage { id: string; role: 'user' | 'assistant'; content: string; created_at: string }
export interface CaseAttachment {
  id: string; filename: string; title: string; media_type: string; bytes: number; sha256: string;
  saved: boolean; original_available: boolean;
}
export interface SourceLocator { source_id: string; locator: string }
export interface CaseCurrency {
  kind: 'case'; id: string | null; version: number | null;
  status: 'needs-re-review' | 'no-known-impact' | 'unavailable'; needs_re_review: boolean | null;
  annotations: { entry_id: string; title: string; detected_at: string | null;
    state: 'needs-re-review' | 'dismissed'; review_state: 'pending' | 'reviewed' | 'dismissed' }[];
  annotation_count: number; truncated: boolean;
}
export interface TeachingStage {
  id: string; narrative: string; prompts: string[]; teaching_points?: string[]; sources?: SourceLocator[];
}
export interface TeachingView {
  id: string; version: number; topic_id: string; stage_count: number; revealed_count: number;
  debriefed: boolean; stages: TeachingStage[]; review: { status?: string };
  license: string; synthetic: true; take_home?: string[];
  currency: CaseCurrency;
}
export interface CaseSession {
  id: string; kind: 'daily' | 'teaching'; title: string; text: string; revision: number;
  scope: ContextScope; saved: boolean; dirty: boolean; saved_at: string | null;
  created_at: string; updated_at: string; active_run_id: string | null;
  messages: CaseMessage[]; teaching: TeachingView | null;
  attachments?: CaseAttachment[];
}
export interface CaseSummary {
  id: string; kind: 'daily' | 'teaching'; title: string; revision: number;
  created_at: string; updated_at: string; saved_at: string;
  currency?: CaseCurrency;
}
export interface TeachingSummary {
  id: string; version: number; title: string; summary: string; topic_id: string;
  review?: { status?: string }; license?: string;
  currency: CaseCurrency;
}
export interface CaseCapabilities {
  inputs: Record<'text' | 'image' | 'pdf', { supported: boolean; code?: string; reason?: string; max_characters?: number }>;
  discussion: { adapter_installed: boolean; scope: 'temporary-case' };
  teaching: { content_installed: boolean };
  handoffs: Record<'explain' | 'generated-practice', string>; memory_capture: boolean;
  extraction?: { supported: boolean; max_bytes: number; max_text_characters?: number; max_pages?: number; image_pixels?: number;
    formats: string[]; scope: 'temporary-case'; code?: string | null; reason?: string | null };
  originals?: { supported: boolean; max_bytes: number; image_pixels: number; formats: string[]; scope: 'temporary-case' };
  image_interpretation?: { supported: boolean; code: string | null; reason: string | null; models?: string[];
    provider?: string | null; interpretation_verified?: boolean; max_bytes?: number; image_pixels?: number };
}
export interface AttachmentPreview {
  mode?: 'text' | 'image' | 'original'; image?: { media_type: string; data: string } | null; image_retained?: false;
  id: string; case_id: string; revision: number; scope: ContextScope;
  state: 'reading' | 'processing' | 'ready' | 'failed' | 'cancelled' | 'applied';
  filename: string; title: string; text: string;
  ocr: { confidence?: number | null; used?: boolean | null };
  error: { code: string; message: string; retryable: boolean } | null;
}
export interface CaseEvent {
  id: string; run_id: string; sequence: number;
  type: 'started' | 'answer.delta' | 'completed' | 'failed' | 'cancelled';
  payload: { revision?: number; scope?: ContextScope; text?: string; message_id?: string;
    error?: { code: string; message: string; retryable: boolean } };
}
export interface CaseHandoff {
  id: string; case_handoff_id: string; case_id: string; revision: number;
  target: 'explain' | 'generated-practice'; expires_at: string;
  question: string; case_text: string; scope: ContextScope & { kind: 'temporary-case' };
}
export type StartCase = { kind: 'daily'; title: string; text: string } |
  { kind: 'teaching'; teaching_case_id: string };
