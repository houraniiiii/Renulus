// SPDX-License-Identifier: MIT
export type ObjectValue = Record<string, any>;
export interface SourceTarget { register_id: string; canonical_url?: string; pinned_source_id?: string; doi?: string; pmid?: string; pmcid?: string; edition?: string; original_sha256?: string; topic_ids?: string[]; locators?: string[] }
export interface ReviewedEvidence { url: string; locator: string; finding: string; checked_on: string; inspected: true; sha256?: string | null }
export interface Review { summary: string; topic_ids: string[]; reviewer: 'learner' | 'assistant'; state: 'reviewed' | 'dismissed'; evidence: ReviewedEvidence[]; target: SourceTarget | null; changes: ObjectValue }
export interface CheckRoute { kind: 'source' | 'publication' | 'literature'; id: string }
export interface CheckInput { route: CheckRoute; token: string; stamp: string; target: ObjectValue; previous_digest: string | null; checked_at: string }
export interface Observation { digest: string; links: Array<{ url: string; label: string }>; entries: Array<{ external_id: string; title: string; url: string; publication_date: string | null; metadata: ObjectValue }>; metadata: ObjectValue }
export type UpdatesCommand =
  | { type: 'updates.sources' }
  | { type: 'updates.entries'; state: 'pending' | 'reviewed' | 'dismissed' | null; limit: number; offset: number }
  | { type: 'updates.entry'; id: string }
  | { type: 'updates.read'; id: string }
  | { type: 'updates.statuses'; sourceId: string }
  | { type: 'updates.affected'; id: string; limit: number; offset: number }
  | { type: 'updates.annotations'; kind: 'question' | 'case'; id: string; version: number }
  | { type: 'updates.review'; id: string; review: Review; expectedRevision: string; idempotencyKey: string }
  | { type: 'updates.sync'; id: string }
  | { type: 'updates.publications' }
  | { type: 'updates.publications.track'; sourceId: string; url: string; permissionReference: string; maxBytes: number; idempotencyKey: string }
  | { type: 'updates.publications.stop'; id: string }
  | { type: 'updates.check.begin'; route: CheckRoute; force: boolean }
  | { type: 'updates.check.finish'; input: CheckInput; observation: Observation | null; errorCode: string | null }
  | { type: 'updates.check.current'; input: CheckInput }
  | { type: 'updates.literature.checks' }
  | { type: 'updates.schedule.read' }
  | { type: 'updates.schedule.write'; enabled: boolean; cadenceHours: number; selection: CheckRoute[]; expectedRevision: number; idempotencyKey: string }
  | { type: 'updates.schedule.claim'; manual: boolean }
  | { type: 'updates.schedule.finish'; id: string; checked: number; failed: number; errorCode: string | null }
  | { type: 'updates.schedule.stop' }
  | { type: 'updates.recover' }
  | { type: 'updates.digest.input'; limit: number }
  | { type: 'updates.digest.current'; stamp: string; limit: number };
export type UpdatesResults = { [K in UpdatesCommand['type']]: ObjectValue } & {
  'updates.check.begin': { input: CheckInput | null; cached: boolean; state: string };
  'updates.schedule.claim': { id: string | null; selection: CheckRoute[] };
  'updates.digest.input': { stamp: string; entries: ObjectValue[]; checked_at: string; limit: number };
};
export interface UpdatesStorage { command<C extends UpdatesCommand>(command: C): Promise<UpdatesResults[C['type']]> }
/** Network retrieval uses the existing protected retrieval adapter; digest uses native OpenCode. */
export interface UpdatesNativePort {
  check(input: CheckInput, signal: AbortSignal): Promise<Observation>;
  digest(input: UpdatesResults['updates.digest.input'], signal: AbortSignal): Promise<string>;
}
