// SPDX-License-Identifier: MIT
import type { ConversationSummary } from '../../storage/contracts.ts';
import type { LibraryDependency, LibraryPassage, LibraryToolEnvelope } from '../../../../harness/src/domain-tools.ts';
import type { NativeInputBinding } from '../../../../harness/src/host.ts';
import type { ContentReference } from './metadata-contracts.ts';
import type { MemoryDependency } from '../memory/contracts.ts';

export type Binding = NativeInputBinding;
export interface RuntimeIdentity { profileId: string; storeId: string; generation: string }
export interface RuntimeReference {
  contract_version: 'harness/1'; profile_id: string; store_id: string;
  engine: { name: 'opencode'; version: '2.0.26'; source_commit: string }; session_id: string;
}
export interface Mapping { contract_version: 'harness/1'; conversation: { type: 'learn_thread'; id: string };
  retention: 'saved'; runtime: RuntimeReference }
export interface AnswerReference {
  version: 1; run_id: string; thread_id: string; runtime: RuntimeReference; input_id: string;
  message_ids: string[]; sha256: string;
  citations: { document_id: string; revision_id: string; passage_id: string; locators: LibraryDependency['locators'] }[];
  inputs: { kind: 'committed_evidence'; dependency: Dependency }[]; dependencies: Dependency[];
}
export interface Dependency extends MemoryDependency {}
export interface Checkpoint {
  version: 1; kind: 'bf02-target-pending'; identity: RuntimeIdentity; attemptId: string;
  conversationRevision: number; draftRevision: number; policyRevision: number; contextEpoch: number;
  cancellationEpoch: number; projectId: string | null; projectRevision: number | null;
  membershipRevision: number | null; revisionIds: string[] | null; inputSha256: string;
  consumed: LibraryDependency[]; history: { runId: string; publicationDigest: string }[];
  memory: MemoryDependency[];
  /** Text stays in the existing composer/native transcript; only intent metadata is pinned here. */
  intent?: Omit<SavedSendIntent, 'text'>;
  attachments?: { id: string; stamp: string }[];
}
/** Exact fully defaulted Python Send.model_dump(mode='json') for a text send.
 * Media producers are deliberately outside this saved-text admission surface. */
export interface SavedSendIntent {
  expected_revision: number; text: string; request_id: string; teaching_style: 'direct' | 'guided';
  topic_id: string | null; model: string | null; freshness: boolean | null; content_refs: ContentReference[];
  images?: { type: 'image'; media_type: 'image/png' | 'image/jpeg' | 'image/webp'; data: string }[];
}
export interface LearningMessage {
  id: string; run_id: string; role: 'user' | 'assistant'; content: string;
  created_at: string; content_refs: ContentReference[];
}
export interface LearningReceipt {
  run_id: string; state: 'running' | 'completed' | 'cancelled' | 'failed' | 'interrupted';
  conversation: ConversationSummary; answer_reference?: AnswerReference;
}
export interface RunSnapshot {
  receipt: LearningReceipt; checkpoint: Checkpoint; mapping: Mapping | null; inputId: string | null;
  ancestry?: Pick<AnswerReference, 'inputs' | 'dependencies'>;
}
export interface BeginInput {
  threadId: string; expectedRevision: number; expectedDraftRevision: number; text: string;
  idempotencyKey: string; runId: string; attemptId: string; identity: RuntimeIdentity;
  intent?: SavedSendIntent;
}
export interface FindScope { lifecycle: 'active' | 'archived' | 'all'; projectId: string | null }
export interface ReadView {
  conversation: ConversationSummary; mapping: Mapping | null;
  references: { reference: AnswerReference; publicationDigest: string }[];
  legacyReferences?: { id: string; role: 'user' | 'assistant'; runId: string }[];
  contextEpoch: number; policyRevision: number; stamp: string;
}
export interface Purge { purge_id: string; profile_id: string; store_id: string; session_id: string;
  operation_id: string; attempt_id: string; state: 'pending' | 'removed' }
export type LearningCommand =
  | { type: 'learning.legacy.prepare'; threadId: string; expectedRevision: number; identity: RuntimeIdentity }
  | { type: 'learning.legacy.activate'; threadId: string; sourceDigest: string; sourceStamp: string; identity: RuntimeIdentity }
  | ({ type: 'learning.begin' } & BeginInput)
  | { type: 'learning.current'; runId: string; binding: Binding | null }
  | { type: 'learning.attachments'; runId: string }
  | { type: 'learning.attachment.cleanup'; removed: string[] }
  | { type: 'learning.map'; runId: string; sessionId: string }
  | { type: 'learning.bind'; binding: Binding }
  | { type: 'learning.consume'; binding: Binding; references: LibraryDependency[] }
  | { type: 'learning.consumeMemory'; binding: Binding; dependencies: MemoryDependency[] }
  | { type: 'learning.context'; binding: Binding; messages: { id: string; role: 'user' | 'assistant' | 'tool' }[] }
  | { type: 'learning.publish'; binding: Binding; reference: AnswerReference }
  | { type: 'learning.stop'; runId: string; state: 'cancelled' | 'failed' | 'interrupted' }
  | { type: 'learning.lifecycle'; threadId: string; expectedRevision: number; lifecycle: 'active' | 'archived'; idempotencyKey: string }
  | { type: 'learning.project'; threadId: string; expectedRevision: number; projectId: string | null; expectedProjectRevision: number | null; idempotencyKey: string }
  | { type: 'learning.delete'; threadId: string; expectedRevision: number; idempotencyKey: string }
  | { type: 'learning.view'; threadId: string }
  | { type: 'learning.read.check'; threadId: string; stamp: string }
  | { type: 'learning.scan'; scope: FindScope; after: string | null; limit: number; epoch: string | null }
  | { type: 'learning.library.plan'; binding: Binding }
  | { type: 'learning.library.resolve'; binding: Binding; passageIds: string[] }
  | { type: 'learning.purge.enqueue'; identity: RuntimeIdentity; sessionId: string; operationId: string; attemptId: string }
  | { type: 'learning.purge.list'; identity: RuntimeIdentity }
  | { type: 'learning.purge.ack'; purgeId: string; identity: RuntimeIdentity };
export interface LearningResults {
  'learning.legacy.prepare': { document: string; sessionId: string; sourceDigest: string; sourceStamp: string; operationId: string; messageCount: number } | null;
  'learning.legacy.activate': Mapping;
  'learning.begin': { fresh: boolean; run: RunSnapshot };
  'learning.current': RunSnapshot;
  'learning.attachments': { id: string; mediaType: string; path: string | null; sha256: string; bytes: number; text: string }[];
  'learning.attachment.cleanup': { attachment_id: string; relative_directory: string }[];
  'learning.map': Mapping;
  'learning.bind': RunSnapshot;
  'learning.consume': { recorded: true };
  'learning.consumeMemory': { recorded: true };
  'learning.context': { message_ids: string[]; learner_context: string };
  'learning.publish': LearningReceipt;
  'learning.stop': { receipt: LearningReceipt | null; sessionId: string | null };
  'learning.lifecycle': ConversationSummary;
  'learning.project': ConversationSummary;
  'learning.delete': { deleted: true; identity: { type: 'learn_thread'; id: string } };
  'learning.view': ReadView;
  'learning.read.check': { current: true };
  'learning.scan': { views: ReadView[]; next: string | null; epoch: string };
  'learning.library.plan': { revisionIds: string[]; envelope: LibraryToolEnvelope };
  'learning.library.resolve': { passages: LibraryPassage[]; references: LibraryDependency[] };
  'learning.purge.enqueue': Purge;
  'learning.purge.list': Purge[];
  'learning.purge.ack': { removed: true };
}
/** Implemented by the integration-owned canonical worker, never an independent connection. */
export interface LearningStorage {
  command<C extends LearningCommand>(command: C): Promise<LearningResults[C['type']]>;
}
