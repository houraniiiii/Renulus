import type { Lifecycle } from '../../platform/designC';

export type TestOrigin = 'reviewed_bank' | 'generated' | 'imported' | 'nightly';
export interface VersionSummary {
  id: string; test_id: string; ordinal: number; origin: TestOrigin;
  review_quality: 'reviewed' | 'personal' | 'needs_review'; status: 'ready' | 'needs_review';
  item_count: number; topic_ids: string[]; created_at?: string;
}
export interface TestSummary {
  id: string; title: string; lifecycle: Lifecycle; revision: number; updated_at: string;
  latest_version: VersionSummary | null;
}
export interface TestPage { items: TestSummary[]; next_cursor: string | null }
export interface TestSetup {
  test: TestSummary; version: VersionSummary; can_start: boolean;
  content_warnings: { item_id: string; status: string }[];
  legacy: { kind: 'reviewed' | 'generated'; session_id: string } | null;
}
export interface PreviewItem {
  item_id: string; question_id: string; question_version: string; family_id: string;
  family_version: string; topic_id: string; stem: string; options: { id: string; text: string }[];
}
export interface PublishedTest { test_id: string; version_id: string; item_count: number; ordinal: number; status: string }
export type TestSelection = { test_id: string; version_id?: string } | { test_id?: never; version_id: string };
export const originLabel: Record<TestOrigin, string> = {
  reviewed_bank: 'Reviewed bank', generated: 'Generated', imported: 'Imported', nightly: 'Nightly',
};
