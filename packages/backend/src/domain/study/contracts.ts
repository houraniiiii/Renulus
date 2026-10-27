// SPDX-License-Identifier: MIT
export interface LocalClock { now: string; timezone: string }
export interface HomePreferences { doctor_name: string | null; revision: number }
export interface StudyGoals { hours_per_week: number; exam_date: string | null; topic_ids: string[]; track: 'general' | 'eseneph' }
export interface NightlyPreferences { enabled: boolean; local_time: string; question_count: 5 | 10 | 20; revision: number }
export interface SuggestionBundle { explain: string[]; case: string[]; practice: string[] }
export interface EligibleInput { kind: 'committed_evidence' | 'learning_summary' | 'goal' | 'preferences' | 'memory'; dependency: { target: { type: string; id: string }; expected_revision: string } }
export interface StudyContext { stamp: string; epoch: number; policyRevision: number; settingsRevision: number; inputs: EligibleInput[]; material: Record<string, unknown> }
export interface NightlySchedule { day: string; timezone: string; preferences_revision: number; home_settings_revision: number; eligibility_token: string; context_stamp: string }
export interface GenerationRequest { idempotency_key: string; title: string; count: 5 | 10 | 20; inputs: EligibleInput[]; material: Record<string, unknown>; nightly?: NightlySchedule }
export interface Activity { id: string; topic_id: string; objective_id: string | null; kind: string; title: string; due_date: string; duration_minutes: number; reason: Record<string, any>; evidence_id: string | null; state: 'planned' | 'completed' | 'skipped'; manual_override: boolean; revision: string; outside_selection?: boolean }
export interface Selection { track: string; title: string; status: string; message: string | null; topic_ids: string[]; objective_ids: Record<string, string[]>; mapping_version: string | null }
export interface Plan { activities: Activity[]; selection: Selection; tracks: Record<string, any>[] }
export type PlanProposal = Pick<Activity, 'id' | 'topic_id' | 'objective_id' | 'kind' | 'title' | 'due_date' | 'duration_minutes' | 'reason' | 'evidence_id'>;
export interface PlanPreview { activities: PlanProposal[]; selection: Selection; status: string; message: string | null }
export interface Progress { groups: Record<string, { answered: number; correct: number }>; topics: { topic_id: string; answered: number; correct: number; fresh_answered: number; fresh_correct: number }[]; interpretation: string }
export interface HomeView { preferences: HomePreferences; suggestions: SuggestionBundle | null; suggestions_date: string | null; stale: boolean; job: unknown; assistance_allowed: boolean; error_code: string | null }
export interface HomeJob { job_id: string; fresh: boolean; context: StudyContext; day: string; timezone: string }
export interface NightlyStatus { preferences: NightlyPreferences; app_running_only: true; next_eligible_at: string | null; last_job: { id: string; state: string; [key: string]: unknown } | null; error_code: string | null; assistance_allowed: boolean }
export type StudyCommand =
  | { type: 'study.preferences.read' }
  | { type: 'study.preferences.write'; expectedRevision: number; doctorName: string | null; idempotencyKey: string }
  | { type: 'study.goals.read' }
  | { type: 'study.goals.write'; expectedRevision: number; goals: StudyGoals; idempotencyKey: string }
  | { type: 'study.plan.read' }
  | { type: 'study.plan.preview'; clock: LocalClock }
  | { type: 'study.plan.propose'; clock: LocalClock }
  | { type: 'study.progress' }
  | { type: 'study.activity.change'; id: string; expectedRevision: string; dueDate: string | null; state: Activity['state'] | null; idempotencyKey: string }
  | { type: 'study.context' }
  | { type: 'study.home.read'; clock: LocalClock }
  | { type: 'study.home.begin'; clock: LocalClock }
  | { type: 'study.home.publish'; jobId: string; bundle: SuggestionBundle; clock: LocalClock }
  | { type: 'study.job.stop'; jobId: string; operation: 'daily_suggestions' | 'nightly_test'; state: 'failed' | 'cancelled'; errorCode: string }
  | { type: 'study.nightly.read' }
  | { type: 'study.nightly.preferences'; clock: LocalClock; expectedRevision: number; enabled: boolean; localTime: string; count: 5 | 10 | 20; idempotencyKey: string }
  | { type: 'study.nightly.recover'; clock: LocalClock }
  | { type: 'study.nightly.claim'; clock: LocalClock }
  | { type: 'study.nightly.attach'; schedule: NightlySchedule; jobId: string }
  | { type: 'study.nightly.guard'; schedule: NightlySchedule };
export interface StudyResults {
  'study.preferences.read': HomePreferences; 'study.preferences.write': HomePreferences;
  'study.goals.read': { goals: StudyGoals; revision: number }; 'study.goals.write': { goals: StudyGoals; revision: number };
  'study.plan.read': Plan; 'study.plan.preview': PlanPreview; 'study.plan.propose': Plan & { status: string; message?: string | null; explanation?: string }; 'study.progress': Progress; 'study.activity.change': Activity;
  'study.context': StudyContext; 'study.home.read': HomeView; 'study.home.begin': HomeJob;
  'study.home.publish': HomeView; 'study.job.stop': { stopped: true };
  'study.nightly.read': NightlyStatus;
  'study.nightly.preferences': NightlyPreferences; 'study.nightly.recover': { recovered: true };
  'study.nightly.claim': { request: GenerationRequest | null }; 'study.nightly.attach': { attached: true }; 'study.nightly.guard': { current: true };
}
export interface StudyStorage { command<C extends StudyCommand>(command: C): Promise<StudyResults[C['type']]> }
/** Native dispatch executes one bounded role. No provider selection/loop lives in Study. */
export interface StudyNativePort { suggestions(context: StudyContext, signal: AbortSignal): Promise<SuggestionBundle> }
/** Assessment owns generation, validation, immutable publication and idempotency.
 * Its nightly publication transaction must invoke requireNightlyPublication. */
export interface StudyAssessmentPort { generate(request: GenerationRequest, signal: AbortSignal): Promise<{ id: string; [key: string]: unknown }>; cancel(id: string): Promise<unknown> }
