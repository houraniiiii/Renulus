import type { ContentReference } from '../../platform/designC';

/** References are resolved by the backend; renderer metadata grants no eligibility. */
export interface GenerationInput {
  kind: 'memory' | 'learning_summary' | 'fictional_case_summary' | 'goal' | 'preferences' | 'committed_evidence';
  dependency: { target: { type: 'memory_revision' | 'learning_evidence' | 'goal' | 'preferences'; id: string }; expected_revision: string };
  retention: 'saved'; content_class: 'general_learning';
}
export interface GenerationIntent {
  title: string; count: 5 | 10 | 20; topic_id?: string | null;
  inputs?: GenerationInput[]; source_refs?: ContentReference[];
}
export interface GeneratedVersion { test_id: string; version_id: string; item_count: number; available: boolean }
export interface GenerationJob {
  id: string; state: 'queued' | 'running' | 'needs_review' | 'failed' | 'cancelled' | 'published';
  title: string; requested_count: 5 | 10 | 20; validated_count: number; accepted_count: number | null;
  effective_count: number; calls_used: number; calls_remaining: number; error_code: string | null;
  route: { provider: string; model: string }; result: GeneratedVersion | null;
  can_retry: boolean; can_accept_shorter: boolean;
}
export interface GenerationJobPage { items: GenerationJob[] }
/** Cancellation remains safe when Test blocks all assistance-bearing reads. */
export interface GenerationCancellation { id: string; state: GenerationJob['state'] }
export interface GenerationTopic { id: string; label: string }

export function generationMessage(job: GenerationJob): string {
  if (job.state === 'published') return job.result?.available
    ? 'Your generated personal practice is saved. Choose Study or Test when you are ready.'
    : 'The original saved version is unavailable. This job will not regenerate it automatically.';
  if (job.state === 'running' || job.state === 'queued') return 'Validated questions are saved after each batch. You can leave this view and return to its progress.';
  if (job.error_code === 'generation_short_batch') return 'The subscription returned fewer questions. Keep these questions explicitly or retry the remaining work.';
  if (job.state === 'cancelled') return 'Generation stopped. Validated questions are retained; reopening does not send another request.';
  if (job.error_code === 'interrupted') return 'Generation was interrupted. Validated questions are retained. Continue only with an explicit retry.';
  if (job.error_code?.startsWith('generation_sources') || job.error_code === 'knowledge_rebuild_required') return 'The selected sources need attention. Rebuild restored Library search or start a new set with eligible sources.';
  if (['generation_inputs_changed', 'generation_context_changed', 'assistance_changed', 'assistance_restricted', 'connection_changed'].includes(job.error_code ?? ''))
    return 'Learning context, assessment policy or the selected connection changed. This draft is retained; create a new set with the current context.';
  if (job.error_code === 'generation_duplicate_batch') return 'A batch repeated a question. Earlier validated questions are retained.';
  if (job.error_code === 'generation_invalid_output') return 'A batch could not be validated. Earlier questions are retained; retry explicitly.';
  return 'The selected subscription could not finish this set. Check Connections, then retry explicitly if available. Validated work is retained.';
}
