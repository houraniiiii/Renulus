export type FactKind = 'learning-point' | 'preference' | 'goal' | 'study-interest' | 'mistake';

export interface Fact {
  id: string;
  text: string;
  kind: FactKind;
  topic_id: string | null;
  revision: number;
  source_kind: string;
  source_id: string | null;
  created_at: string;
  updated_at: string;
  index_state: 'pending' | 'ready' | 'failed';
  purge_pending?: boolean;
}

export interface MemoryStatus {
  index: { ready: boolean; state: string; message?: string; helper_ready?: boolean; error_code?: string | null };
  pending_jobs: number;
  producer: 'mem0-oss';
  automatic_capture: boolean;
}

export interface MemoryJob {
  id: string;
  state: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  error_code?: string;
}

export interface FactHistory {
  revision: number;
  text: string;
  event: string;
  created_at: string;
}

export interface SearchResult { records: Fact[]; context: string }
export interface PurgeResult { purged: true; purge_pending: boolean }
export interface DeleteResult { deleted: true; purge_pending: boolean }

export const kindLabels: Record<FactKind, string> = {
  'learning-point': 'Learning point',
  preference: 'Preference',
  goal: 'Goal',
  'study-interest': 'Study interest',
  mistake: 'Mistake to revisit',
};

export function factPath(id: string): string { return '/memory/facts/' + encodeURIComponent(id); }
export function readableState(state: string): string { return state.replaceAll('-', ' ').replaceAll('_', ' '); }
export function displayDate(date: string): string {
  const value = new Date(date);
  return Number.isNaN(value.getTime()) ? date : value.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}
