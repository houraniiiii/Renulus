export type NightlyCount = 5 | 10 | 20;
export interface NightlyPreferencesValue {
  enabled: boolean; local_time: string; question_count: NightlyCount; revision: number;
}
export interface NightlyPreferencesUpdate {
  enabled: boolean; local_time: string; question_count: NightlyCount; expected_revision: number;
}
export interface NightlyJob {
  id: string; state: 'queued' | 'running' | 'published' | 'needs_review' | 'failed' | 'cancelled';
  requested_count: NightlyCount; validated_count: number; error_code: string | null;
  result: {
    version: { type: 'saved_test_version'; id: string };
    test: { type: 'saved_test'; id: string } | null; available: boolean;
  } | null;
}
export interface NightlyState {
  preferences: NightlyPreferencesValue; app_running_only: true; next_eligible_at: string | null;
  last_job: NightlyJob | null; error_code: string | null; assistance_allowed: boolean;
}
export const isActive = (job: NightlyJob | null) => job?.state === 'queued' || job?.state === 'running';
export function nightlyMessage(code: string | null): string {
  if (code === 'interrupted') return 'Generation was interrupted. Retained work has not been published.';
  if (code === 'nightly_invalidated' || code === 'nightly_context_changed' || code === 'generation_context_changed' || code === 'generation_inputs_changed')
    return 'Saved learning or preferences changed. This work has not been published.';
  if (code === 'assistance_restricted' || code === 'assistance_changed') return 'Nightly generation is paused during your Test.';
  if (code === 'generation_short_batch') return 'The full count could not be completed. Review the retained questions before accepting a shorter set.';
  if (code === 'nightly_generation_unavailable') return 'Saved test generation is not available yet.';
  return 'Nightly generation could not finish. Check Connections before the next eligible night. There is no automatic retry today.';
}
