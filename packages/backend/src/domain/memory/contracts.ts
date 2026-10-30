// SPDX-License-Identifier: MIT
import type { AnswerReference } from '../learning/contracts.ts';
import type { CapturePlan } from '../../../../contracts/worker.ts';

export type FactKind = 'learning-point' | 'preference' | 'goal' | 'study-interest' | 'mistake';
export interface MemoryDependency { target: { type: 'memory_revision' | 'learning_evidence' | 'library_revision'; id: string }; expected_revision: string }
export interface MemoryManifest { version: 1; inputs: { kind: string; dependency: MemoryDependency }[]; dependencies: MemoryDependency[] }
export interface MemoryScope { kind: 'study' | 'personal-library' | 'generated-practice' | 'reviewed-assessment'; entity_id?: string | null }
export interface MemoryFact { id: string; text: string; kind: FactKind; topic_id: string | null; scope: string; revision: number;
  source_kind: string; source_id: string | null; created_at: string; updated_at: string; project_id: string | null;
  visibility: 'project' | 'profile-global'; index_state: 'ready' | 'pending'; sources: { source_key: string }[] }
export interface MemoryRecord { id: string; revision: number; text: string; scope: string; topic_id: string | null; kind: FactKind }
export interface MemoryVector { canonical_id: string; canonical_revision: number; engine_id: string }
export interface CaptureTicket { jobId: string; evidenceId: string; attempt: number; fingerprint: string; publicationDigest: string;
  supportSha256: string; projectId: string | null; scope: MemoryScope; topicId: string | null;
  reference: AnswerReference | { version: 1; message_id: string; run_id: string; sha256: string }; sourceText: string | null }
export interface MemoryPurge { intentId: string; ids: string[] }
/** Derived IDs are immutable per fact revision; canonical ownership stays logical. */
export const memoryEngineId = (id: string, revision: number) => `${id}:v${revision}`;
export interface MemoryMutation { record: MemoryFact | null; deleted: boolean; purge: MemoryPurge | null }
export interface MemorySnapshot { epoch: number; records: MemoryRecord[]; accepted: MemoryVector[]; stamp: string; projectId: string | null }
export type MemoryCommand =
  | { type: 'memory.list'; offset: number; limit: number }
  | { type: 'memory.inspect'; id: string }
  | { type: 'memory.status' }
  | { type: 'memory.add'; text: string; kind: FactKind; topicId: string | null; projectId: string | null; idempotencyKey: string }
  | { type: 'memory.correct'; id: string; expectedRevision: number; text: string }
  | { type: 'memory.delete'; id: string; expectedRevision: number }
  | { type: 'memory.history.purge'; id: string }
  | { type: 'memory.export' }
  | { type: 'memory.capture.claim'; evidenceId: string; retry: boolean }
  | { type: 'memory.capture.explicit'; evidenceId: string }
  | { type: 'memory.capture.check'; ticket: CaptureTicket }
  | { type: 'memory.capture.complete'; ticket: CaptureTicket; facts: string[] }
  | { type: 'memory.capture.fail'; ticket: CaptureTicket; cancelled: boolean; code: string }
  | { type: 'memory.jobs'; recover: boolean }
  | { type: 'memory.job.cancel'; jobId: string }
  | { type: 'memory.purge.pending' }
  | { type: 'memory.purge.ack'; intentId: string }
  | { type: 'memory.snapshot'; projectId: string | null }
  | { type: 'memory.index.accept'; snapshot: MemorySnapshot; references: MemoryVector[]; generation: string }
  | { type: 'memory.recall.resolve'; snapshot: MemorySnapshot; candidates: MemoryVector[]; budgetChars: number };
export interface MemoryResults {
  'memory.list': { records: MemoryFact[]; nextOffset: number | null };
  'memory.inspect': MemoryFact & { history: { revision: number; text: string; event: string; created_at: string }[] };
  'memory.status': { state: string; epoch: number; generation: string | null; error_code: string | null; pending: number };
  'memory.add': MemoryFact; 'memory.correct': MemoryMutation; 'memory.delete': MemoryMutation; 'memory.history.purge': MemoryMutation;
  'memory.export': { format: 'renulus-memory'; version: 1; records: MemoryFact[] };
  'memory.capture.claim': CaptureTicket | null; 'memory.capture.explicit': CaptureTicket | null; 'memory.capture.check': { current: true };
  'memory.capture.complete': { records: MemoryFact[] }; 'memory.capture.fail': { settled: true };
  'memory.jobs': { id: string; evidence_id: string; scope: string; state: string; error_code: string | null }[];
  'memory.job.cancel': { cancelled: true }; 'memory.purge.pending': MemoryPurge[]; 'memory.purge.ack': { purged: true };
  'memory.snapshot': MemorySnapshot; 'memory.index.accept': { ready: true };
  'memory.recall.resolve': { records: MemoryFact[]; dependencies: MemoryDependency[]; context: string };
}
export interface MemoryStorage { command<C extends MemoryCommand>(command: C): Promise<MemoryResults[C['type']]> }
export interface MemoryEngine {
  extract(input: { text: string; plan: CapturePlan; operationId: string; attemptId: string; signal: AbortSignal }): Promise<string[]>;
  reconcile(records: MemoryRecord[], signal?: AbortSignal): Promise<MemoryVector[]>;
  recall(query: string, accepted: MemoryVector[], limit: number, signal?: AbortSignal): Promise<MemoryVector[]>;
  purge(ids: string[]): Promise<void>;
}
