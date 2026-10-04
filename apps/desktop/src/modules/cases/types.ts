// SPDX-License-Identifier: MIT
import type { ContextScope } from '../../platform/contracts';

export interface CaseMessage { id: string; role: 'user' | 'assistant'; content: string; created_at: string }
export interface SourceLocator { source_id: string; locator: string }
export interface TeachingStage {
  id: string; narrative: string; prompts: string[]; teaching_points?: string[]; sources?: SourceLocator[];
}
export interface TeachingView {
  id: string; version: number; topic_id: string; stage_count: number; revealed_count: number;
  debriefed: boolean; stages: TeachingStage[]; review: { status?: string };
  license: string; synthetic: true; take_home?: string[];
}
export interface CaseSession {
  id: string; kind: 'daily' | 'teaching'; title: string; text: string; revision: number;
  scope: ContextScope; saved: boolean; dirty: boolean; saved_at: string | null;
  created_at: string; updated_at: string; active_run_id: string | null;
  messages: CaseMessage[]; teaching: TeachingView | null;
}
export interface CaseSummary {
  id: string; kind: 'daily' | 'teaching'; title: string; revision: number;
  created_at: string; updated_at: string; saved_at: string;
}
export interface TeachingSummary {
  id: string; version: number; title: string; summary: string; topic_id: string;
  review?: { status?: string }; license?: string;
}
export interface CaseCapabilities {
  inputs: Record<'text' | 'image' | 'pdf', { supported: boolean; code?: string; reason?: string; max_characters?: number }>;
  discussion: { adapter_installed: boolean; scope: 'temporary-case' };
  teaching: { content_installed: boolean };
  handoffs: Record<'explain' | 'generated-practice', string>; memory_capture: boolean;
  extraction?: { supported: boolean; max_bytes: number; max_text_characters?: number; max_pages?: number; image_pixels?: number;
    formats: string[]; scope: 'temporary-case'; code?: string | null; reason?: string | null };
  image_interpretation?: { supported: boolean; code: string; reason: string };
}
export interface AttachmentPreview {
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
