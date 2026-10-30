// SPDX-License-Identifier: MIT
/** Target counterparts of assessment/{attempt,test,generation,import}_models.py.
 * Internal commands are host-only; HTTP never accepts origin, keys or policy authority. */
export type Json = null | boolean | number | string | Json[] | { [key: string]: Json };
export type ObjectValue = { [key: string]: any };
export interface Option { id: string; text: string }
export interface QuestionSnapshot {
  item_id: string; question_id: string; question_version: string; key_version: string | null;
  family_id: string; family_version: string; topic_id: string; stem: string; options: Option[];
  correct_option_ids: string[]; explanation: string;
}
export interface TestVersion {
  id: string; test_id: string; ordinal: number; origin: 'reviewed_bank' | 'generated' | 'imported' | 'nightly';
  review_quality: 'reviewed' | 'personal' | 'needs_review'; status: 'ready' | 'needs_review';
  items: QuestionSnapshot[]; source_refs: ObjectValue[]; terms: string; created_at: string;
  provenance: { schema_version: 1; method: 'reviewed_pack' | 'generation' | 'import' | 'nightly' | 'legacy_conversion';
    job_id: string | null; fictional_artifact_id: string | null };
}
export interface DraftAnswer { item_id: string; option_ids: string[]; marked: boolean }
export interface DraftState { position: number; answers: DraftAnswer[] }
export interface Policy { revision: number; active_test_id: string | null; assistance_allowed: boolean }
export interface Stamp { policy_revision: number; context_epoch: number }
export interface HelpContext { attempt_id: string; item_id: string; version_id: string; draft_revision: number; policy_revision: number; kind: 'hint'|'sources'|'notes'|'chat' }
export interface GenerationInput {
  title: string; count: 5 | 10 | 20; topic_id: string | null; inputs: ObjectValue[]; source_refs: ObjectValue[];
  idempotencyKey: string; origin?: 'generated' | 'nightly'; schedule?: ObjectValue;
}
export interface GeneratedQuestion { stem: string; options: Array<Option & { rationale?: string | null }>;
  correct_option_id: string; explanation: string; hint?: string | null; source_indices?: number[] }
export interface GeneratedBatch { items: GeneratedQuestion[] }
export interface GenerationView extends Stamp {
  id: string; state: 'queued'|'running'|'needs_review'|'failed'|'cancelled'|'published';
  requested_count: number; validated_count: number; accepted_count: number | null;
  published_version_id: string | null; error_code: string | null; checkpoint: ObjectValue; inputs: ObjectValue;
}
export interface ImportCandidate { id: string; span: { start: number; end: number }; stem: string; options: Option[];
  explanation: string; topic_id: string; correct_option_ids: string[]; key_status: 'missing'|'ambiguous'|'resolved';
  removed: boolean; revision: number; review_confirmed: boolean }
export type AssessmentCommand =
  | { type: 'assessment.policy' }
  | { type: 'assessment.fictional.stamp' }
  | { type: 'assessment.fictional.receipt'; idempotencyKey: string }
  | { type: 'assessment.tests.list'; lifecycle: 'active'|'archived'; limit: number; before: string | null }
  | { type: 'assessment.tests.get'; testId: string }
  | { type: 'assessment.tests.setup'; versionId: string }
  | { type: 'assessment.tests.preview'; versionId: string }
  | { type: 'assessment.tests.reviewed'; title: string; count: number; topicIds: string[]; idempotencyKey: string }
  | { type: 'assessment.tests.publish'; title: string; version: TestVersion; provenance: ObjectValue; expectedRevision: number | null; idempotencyKey: string }
  | { type: 'assessment.tests.change'; testId: string; expectedRevision: number; action: 'rename'|'archive'|'restore'|'delete'; title: string | null; idempotencyKey: string }
  | { type: 'assessment.attempts.list' }
  | { type: 'assessment.attempts.start'; versionId: string; mode: 'study'|'test'; timing: { kind:'untimed'|'timed'; duration_seconds:number|null }; idempotencyKey: string }
  | { type: 'assessment.attempts.get'; attemptId: string }
  | { type: 'assessment.attempts.draft'; attemptId: string; expectedRevision: number; draft: DraftState; idempotencyKey: string }
  | { type: 'assessment.attempts.present'; attemptId: string; expectedRevision: number; itemId: string; idempotencyKey: string }
  | { type: 'assessment.attempts.answer'; attemptId: string; expectedRevision: number; itemId: string; optionIds: string[]; idempotencyKey: string }
  | { type: 'assessment.attempts.submit'; attemptId: string; expectedRevision: number; latestDraft: DraftState | null; idempotencyKey: string }
  | { type: 'assessment.attempts.transition'; attemptId: string; expectedRevision: number; action:'pause'|'resume'|'continue-untimed'; idempotencyKey:string }
  | { type: 'assessment.attempts.help'; attemptId:string; expectedRevision:number; expectedPolicyRevision:number; itemId:string; kind:HelpContext['kind']; idempotencyKey:string }
  | { type: 'assessment.help.current'; context:HelpContext }
  | { type: 'assessment.report'; attemptId:string; itemId:string; reportText:string; idempotencyKey:string }
  | { type: 'assessment.narrative.input'; attemptId:string }
  | { type: 'assessment.generation.create'; input:GenerationInput }
  | { type: 'assessment.generation.get'; jobId:string }
  | { type: 'assessment.generation.interrupted'; jobId:string; execution:string }
  | { type: 'assessment.generation.claim'; jobId:string; execution:string; stamp:Stamp }
  | { type: 'assessment.generation.checkpoint'; jobId:string; execution:string; batchIndex:number; items:QuestionSnapshot[] }
  | { type: 'assessment.generation.fail'; jobId:string; execution:string; code:string }
  | { type: 'assessment.generation.cancel'; jobId:string }
  | { type: 'assessment.generation.publish'; jobId:string; acceptedCount:number; idempotencyKey:string }
  | { type: 'assessment.import.create'; title:string; original:{kind:'paste';text:string;terms:string;permission_confirmed:true}; idempotencyKey:string }
  | { type: 'assessment.import.get'; importId:string; original:boolean }
  | { type: 'assessment.import.edit'; importId:string; expectedRevision:number; candidateId:string; stem:string; options:Option[]; explanation:string; topicId:string; idempotencyKey:string }
  | { type: 'assessment.import.resolve'; importId:string; expectedRevision:number; candidateId:string; optionIds:string[]; reviewConfirmed:true; idempotencyKey:string }
  | { type: 'assessment.import.visibility'; importId:string; expectedRevision:number; candidateId:string; removed:boolean; idempotencyKey:string }
  | { type: 'assessment.import.claim'; importId:string; expectedRevision:number; execution:string }
  | { type: 'assessment.import.normalized'; importId:string; execution:string; candidates:ImportCandidate[] }
  | { type: 'assessment.import.cancel'; importId:string; expectedRevision:number; idempotencyKey:string }
  | { type: 'assessment.import.publish'; importId:string; expectedRevision:number; idempotencyKey:string };
export type AssessmentResults = { [K in Exclude<AssessmentCommand['type'],'assessment.fictional.receipt'>]: ObjectValue } & {
  /** The saved publication result for this key, or null when nothing was published. */
  'assessment.fictional.receipt':ObjectValue|null;
  'assessment.policy':Policy; 'assessment.generation.create':GenerationView; 'assessment.generation.get':GenerationView;
  'assessment.generation.claim':GenerationView; 'assessment.generation.checkpoint':GenerationView;
  'assessment.generation.fail':GenerationView; 'assessment.generation.cancel':GenerationView;
};
export interface AssessmentStorage { command<C extends AssessmentCommand>(command:C):Promise<AssessmentResults[C['type']]> }
