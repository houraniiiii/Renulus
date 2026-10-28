// SPDX-License-Identifier: MIT
/** BF02 local schema-2 functions. The shared writer owns BEGIN/COMMIT and ownership.
 * No native/worker/transport calls, files, waits, migrations or writable transcript. */
import type { DatabaseSync } from 'node:sqlite';
import { exact, integer, reject, text } from './contracts.ts';
import { requireAssistance } from './conversation.ts';
import { canonical, digest, one, rows } from './schema.ts';
import { utcNow } from './export.ts';
import { checkMemoryDependency } from './memory.ts';
import type { MemoryDependency } from '../domain/memory/contracts.ts';
import { effectiveKnowledgeMetadata } from '../domain/knowledge/source-status.ts';
import type { Metadata } from '../domain/knowledge/contracts.ts';
import type { AnswerReference, BeginInput, Binding, Checkpoint, Dependency, FindScope, LearningCommand, LearningReceipt,
  LearningResults, Mapping, Purge, ReadView, RunSnapshot, RuntimeIdentity, SavedSendIntent } from '../domain/learning/contracts.ts';
import type { LibraryDependency, LibraryPassage, LibraryToolEnvelope } from '../../../harness/src/domain-tools.ts';

const SOURCE = '4b6fea2875e4f2e3e8a8fee181803e54f7056845';
const now = utcNow;
const json = <T>(value: unknown): T => JSON.parse(String(value));
const sha = (value: unknown) => digest(canonical(value));
const bindingKeys = ['operation_id', 'attempt_id', 'session_id', 'input_id', 'cancellation_id'];
const identifier = (value: unknown) => { text(value, 1, 256); if (!/^[A-Za-z0-9][A-Za-z0-9._:-]*$/.test(value)) reject('storage_invalid_command'); };
const hash = (value: unknown) => { if (typeof value !== 'string' || !/^[a-f0-9]{64}$/.test(value)) reject('storage_invalid_command'); };
const bounded = (value: unknown, bytes = 65536) => { if (Buffer.byteLength(JSON.stringify(value)) > bytes) reject('learning_reference_limit'); };
function identity(value: RuntimeIdentity) { exact(value, ['profileId', 'storeId', 'generation']); Object.values(value).forEach(identifier); }
function binding(value: Binding) { exact(value, bindingKeys); Object.values(value).forEach(identifier); }
function ids(value: unknown, maximum = 100): asserts value is string[] {
  if (!Array.isArray(value) || value.length > maximum || new Set(value).size !== value.length) reject('storage_invalid_command'); value.forEach(identifier);
}
function references(value: LibraryDependency[]) {
  if (!Array.isArray(value) || value.length > 100) reject('learning_reference_limit'); bounded(value);
  for (const ref of value) {
    exact(ref, ['document_id', 'document_revision', 'passage_id', 'locators']);
    identifier(ref.document_id); identifier(ref.document_revision); identifier(ref.passage_id);
    if (!Array.isArray(ref.locators) || ref.locators.length > 12000) reject('storage_invalid_command');
  }
}
function memoryDependencies(value: MemoryDependency[]) {
  if (!Array.isArray(value) || value.length > 100) reject('learning_reference_limit'); bounded(value);
  for (const dependency of value) {
    exact(dependency, ['target', 'expected_revision']); exact(dependency.target, ['type', 'id']);
    if (dependency.target.type !== 'memory_revision') reject('storage_invalid_command');
    identifier(dependency.target.id); text(dependency.expected_revision, 1, 16);
    integer(Number(dependency.expected_revision), 1);
    if (String(Number(dependency.expected_revision)) !== dependency.expected_revision ||
      !dependency.target.id.endsWith(':' + dependency.expected_revision)) reject('storage_invalid_command');
  }
}
/** Sender and writer use one exact intent. The draft fence is never a public hash field. */
export function learningSendIntent(input: Pick<BeginInput, 'expectedRevision' | 'text' | 'idempotencyKey' | 'intent'>): SavedSendIntent {
  const r = input.intent === undefined ? { expected_revision: input.expectedRevision, text: input.text, request_id: input.idempotencyKey,
    teaching_style: 'direct' as const, topic_id: null, model: null, freshness: null, content_refs: [] } : input.intent;
  if (r && typeof r === 'object' && ['image_preview_id', 'case_revision'].some(k => Object.hasOwn(r, k))) reject('learning_images_not_admitted');
  exact(r, ['expected_revision', 'text', 'request_id', 'teaching_style', 'topic_id', 'model', 'freshness', 'content_refs', ...(Object.hasOwn(r, 'images') ? ['images'] : [])]);
  if (r.images !== undefined && (!Array.isArray(r.images) || r.images.length > 4)) reject('invalid_images');
  for (const image of r.images ?? []) {
    exact(image, ['type', 'media_type', 'data']);
    if (image.type !== 'image' || !['image/png', 'image/jpeg', 'image/webp'].includes(image.media_type)) reject('invalid_images');
    text(image.data, 1, 11184812);
  }
  integer(r.expected_revision, 1); text(r.text, 1, 16000); text(r.request_id, 8, 120);
  if (!r.text.trim() || !/^[A-Za-z0-9._-]+$/.test(r.request_id)) reject('storage_invalid_command');
  if (r.expected_revision !== input.expectedRevision || r.text !== input.text || r.request_id !== input.idempotencyKey) reject('learning_intent_conflict');
  if (!['direct', 'guided'].includes(r.teaching_style)) reject('storage_invalid_command');
  if (r.topic_id !== null) identifier(r.topic_id);
  if (r.model !== null) text(r.model, 0, 128);
  if (r.freshness !== null && typeof r.freshness !== 'boolean') reject('storage_invalid_command');
  if (!Array.isArray(r.content_refs) || r.content_refs.length > 20) reject('storage_invalid_command');
  for (const ref of r.content_refs) {
    exact(ref, ['target', 'locator']); exact(ref.target, ['type', 'id']); identifier(ref.target.id);
    if (ref.target.type !== 'attachment' || ref.locator !== null) reject('learning_reference_input_not_admitted');
  }
  return r;
}
export function isLearningCommand(value: unknown): value is LearningCommand {
  return !!value && typeof value === 'object' && 'type' in value && typeof value.type === 'string' && value.type.startsWith('learning.') && value.type !== 'learning.rename';
}
/** Integration: call this from validateCommand before the shared switch. */
export function validateLearningCommand(command: LearningCommand): void {
  const value = command as unknown as Record<string, unknown>;
  switch (command.type) {
    case 'learning.legacy.prepare':
      exact(value, ['type', 'threadId', 'expectedRevision', 'identity']); identifier(command.threadId); integer(command.expectedRevision, 1); identity(command.identity); break;
    case 'learning.legacy.activate':
      exact(value, ['type', 'threadId', 'sourceDigest', 'sourceStamp', 'identity']); identifier(command.threadId); hash(command.sourceDigest); hash(command.sourceStamp); identity(command.identity); break;
    case 'learning.begin':
      exact(value, ['type', 'threadId', 'expectedRevision', 'expectedDraftRevision', 'text', 'idempotencyKey', 'runId', 'attemptId', 'identity', ...(Object.hasOwn(value, 'intent') ? ['intent'] : [])]);
      identifier(command.threadId); integer(command.expectedRevision, 1); integer(command.expectedDraftRevision);
      text(command.text, 1, 16000); if (!command.text.trim()) reject('storage_invalid_command');
      text(command.idempotencyKey, 8, 128); identifier(command.runId); identifier(command.attemptId); identity(command.identity); learningSendIntent(command); break;
    case 'learning.current': exact(value, ['type', 'runId', 'binding']); identifier(command.runId); if (command.binding !== null) binding(command.binding); break;
    case 'learning.attachments': exact(value, ['type', 'runId']); identifier(command.runId); break;
    case 'learning.attachment.cleanup': exact(value, ['type', 'removed']); ids(command.removed, 1000); break;
    case 'learning.map': exact(value, ['type', 'runId', 'sessionId']); identifier(command.runId); identifier(command.sessionId); break;
    case 'learning.bind': exact(value, ['type', 'binding']); binding(command.binding); break;
    case 'learning.consume': exact(value, ['type', 'binding', 'references']); binding(command.binding); references(command.references); break;
    case 'learning.consumeMemory': exact(value, ['type', 'binding', 'dependencies']); binding(command.binding); memoryDependencies(command.dependencies); break;
    case 'learning.context':
      exact(value, ['type', 'binding', 'messages']); binding(command.binding);
      if (!Array.isArray(command.messages) || command.messages.length > 4096) reject('learning_reference_limit');
      for (const m of command.messages) { exact(m, ['id', 'role']); identifier(m.id); if (!['user', 'assistant', 'tool'].includes(m.role)) reject('storage_invalid_command'); } break;
    case 'learning.publish':
      exact(value, ['type', 'binding', 'reference']); binding(command.binding); bounded(command.reference);
      exact(command.reference, ['version', 'run_id', 'thread_id', 'runtime', 'input_id', 'message_ids', 'sha256', 'citations', 'inputs', 'dependencies']);
      if (command.reference.version !== 1) reject('storage_invalid_command'); hash(command.reference.sha256);
      ids(command.reference.message_ids); if (!command.reference.message_ids.length) reject('storage_invalid_command'); break;
    case 'learning.stop': exact(value, ['type', 'runId', 'state']); identifier(command.runId); if (!['cancelled', 'failed', 'interrupted'].includes(command.state)) reject('storage_invalid_command'); break;
    case 'learning.lifecycle':
      exact(value, ['type', 'threadId', 'expectedRevision', 'lifecycle', 'idempotencyKey']);
      identifier(command.threadId); integer(command.expectedRevision, 1); text(command.idempotencyKey, 8, 128);
      if (!['active', 'archived'].includes(command.lifecycle)) reject('storage_invalid_command'); break;
    case 'learning.project':
      exact(value, ['type', 'threadId', 'expectedRevision', 'projectId', 'expectedProjectRevision', 'idempotencyKey']);
      identifier(command.threadId); integer(command.expectedRevision, 1); text(command.idempotencyKey, 8, 128);
      if (command.projectId !== null) { identifier(command.projectId); if (command.expectedProjectRevision !== null) integer(command.expectedProjectRevision, 1); }
      else if (command.expectedProjectRevision !== null) reject('storage_invalid_command'); break;
    case 'learning.delete': exact(value, ['type', 'threadId', 'expectedRevision', 'idempotencyKey']); identifier(command.threadId); integer(command.expectedRevision, 1); text(command.idempotencyKey, 8, 128); break;
    case 'learning.view': exact(value, ['type', 'threadId']); identifier(command.threadId); break;
    case 'learning.read.check': exact(value, ['type', 'threadId', 'stamp']); identifier(command.threadId); hash(command.stamp); break;
    case 'learning.scan':
      exact(value, ['type', 'scope', 'after', 'limit', 'epoch']); exact(command.scope, ['lifecycle', 'projectId']);
      if (!['active', 'archived', 'all'].includes(command.scope.lifecycle)) reject('storage_invalid_command');
      if (command.scope.projectId !== null) identifier(command.scope.projectId); if (command.after !== null) identifier(command.after);
      integer(command.limit, 1, 20); if (command.epoch !== null) hash(command.epoch); break;
    case 'learning.library.plan': exact(value, ['type', 'binding']); binding(command.binding); break;
    case 'learning.library.resolve': exact(value, ['type', 'binding', 'passageIds']); binding(command.binding); ids(command.passageIds, 24); break;
    case 'learning.purge.enqueue': exact(value, ['type', 'identity', 'sessionId', 'operationId', 'attemptId']); identity(command.identity); identifier(command.sessionId); identifier(command.operationId); identifier(command.attemptId); break;
    case 'learning.purge.list': exact(value, ['type', 'identity']); identity(command.identity); break;
    case 'learning.purge.ack': exact(value, ['type', 'purgeId', 'identity']); identity(command.identity); identifier(command.purgeId); break;
    default: reject('storage_invalid_command');
  }
}
function policy(db: DatabaseSync) {
  requireAssistance(db);
  return Number(one(db, "SELECT value FROM preferences WHERE key='design_c.assessment_policy_revision'")?.value ?? 1);
}
function epoch(db: DatabaseSync) { return Number(one(db, "SELECT value FROM preferences WHERE key='design_c.context_epoch'")?.value ?? 0); }
function bump(db: DatabaseSync) {
  db.prepare("INSERT INTO preferences VALUES('design_c.context_epoch','1',?) ON CONFLICT(key) DO UPDATE SET value=CAST(CAST(preferences.value AS INTEGER)+1 AS TEXT),updated_at=excluded.updated_at").run(now());
}
function deleted(db: DatabaseSync, type: string, id: string) { return !!one(db, 'SELECT 1 FROM deletion_ledger WHERE entity_type=? AND entity_id=?', type, id); }
function summary(db: DatabaseSync, threadId: string) {
  if (deleted(db, 'learn_thread', threadId)) reject('conversation_missing');
  const thread = one(db, 'SELECT t.*,c.lifecycle,c.revision,c.draft_revision,c.draft_refs_json,max(t.updated_at,c.updated_at) AS updated_at FROM learn_threads t JOIN learn_conversations c ON c.thread_id=t.id WHERE t.id=?', threadId);
  if (!thread || thread.lifecycle === 'deleted') reject('conversation_missing');
  const membership = one(db, "SELECT m.project_id,m.revision AS membership_revision,p.revision AS project_revision,p.lifecycle AS project_lifecycle FROM study_project_chats m JOIN study_projects p ON p.id=m.project_id WHERE m.chat_kind='learning' AND m.chat_id=?", threadId);
  if (membership && (membership.project_lifecycle === 'deleted' || deleted(db, 'project', String(membership.project_id)))) reject('project_missing');
  return { conversation: { identity: { type: 'learn_thread' as const, id: threadId }, kind: 'learning' as const,
    retention: 'saved' as const, lifecycle: String(thread.lifecycle), revision: Number(thread.revision), title: String(thread.title),
    project_id: membership ? String(membership.project_id) : null, created_at: String(thread.created_at), updated_at: String(thread.updated_at) },
    draftRevision: Number(thread.draft_revision), draftRefs: json<unknown[]>(thread.draft_refs_json), membership, topicId: thread.topic_id };
}
function mapping(db: DatabaseSync, threadId: string): Mapping | null {
  const row = one(db, 'SELECT * FROM learn_harness_mappings WHERE thread_id=?', threadId);
  if (!row?.session_id || !row.mapping_json) return null;
  const result = json<Mapping>(row.mapping_json);
  if (canonical(result) !== canonical({ contract_version: 'harness/1', conversation: { type: 'learn_thread', id: threadId }, retention: 'saved',
    runtime: { contract_version: 'harness/1', profile_id: row.profile_id, store_id: row.store_id,
      engine: { name: 'opencode', version: '2.0.26', source_commit: SOURCE }, session_id: row.session_id } })) reject('learning_mapping_conflict');
  return result;
}
function commandCurrent(db: DatabaseSync, key: string) {
  if (one(db, "SELECT 1 FROM learn_command_tombstones WHERE ledger='conversation_commands' AND idempotency_key=?", key) || deleted(db, 'conversation_command', key)) reject('command_terminal_unavailable');
}
function snapshot(db: DatabaseSync, runId: string): RunSnapshot {
  const answer = one(db, 'SELECT a.*,r.idempotency_key FROM learn_harness_answers a JOIN learn_runs r ON r.id=a.run_id WHERE a.run_id=?', runId);
  if (!answer || deleted(db, 'learn_run', runId)) reject('learning_run_missing');
  commandCurrent(db, String(answer.idempotency_key));
  const command = one(db, 'SELECT result_json FROM conversation_commands WHERE idempotency_key=?', String(answer.idempotency_key));
  if (!command) reject('learning_receipt_missing');
  summary(db, String(answer.thread_id));
  const receipt = json<LearningReceipt>(command.result_json);
  const checkpoint = answer.state === 'completed' ? null : json<Checkpoint>(answer.reference_json);
  // Terminal replay does not reconstruct authority or cause inference.
  return { receipt, checkpoint: checkpoint as Checkpoint, mapping: mapping(db, String(answer.thread_id)), inputId: answer.input_id as string | null };
}
function current(db: DatabaseSync, runId: string, native: Binding | null = null, admitting = false): RunSnapshot {
  const revision = policy(db), run = snapshot(db, runId), cp = run.checkpoint;
  if (!cp || cp.kind !== 'bf02-target-pending' || run.receipt.state !== 'running' || cp.cancellationEpoch !== 0) reject('learning_run_unavailable');
  if (cp.policyRevision !== revision) reject('assistance_changed');
  if (cp.contextEpoch !== epoch(db)) reject('context_epoch_changed');
  const s = summary(db, run.receipt.conversation.identity.id);
  if (s.conversation.lifecycle !== 'active' || s.conversation.revision !== cp.conversationRevision || s.draftRevision !== cp.draftRevision ||
    s.conversation.project_id !== cp.projectId || (s.membership?.membership_revision ?? null) !== cp.membershipRevision ||
    (s.membership?.project_revision ?? null) !== cp.projectRevision) reject('learning_context_changed');
  if (deleted(db, 'learning_evidence', 'learn-answer:' + runId)) reject('learning_run_unavailable');
  if (native) {
    if (native.operation_id !== runId || native.attempt_id !== cp.attemptId || native.cancellation_id !== runId ||
      native.session_id !== run.mapping?.runtime.session_id || (!admitting && run.inputId !== native.input_id) ||
      (admitting && run.inputId !== null && run.inputId !== native.input_id)) reject('learning_binding_conflict');
  }
  for (const pin of cp.attachments ?? []) if (attachment(db, run.receipt.conversation.identity.id, pin.id).stamp !== pin.stamp) reject('learning_attachment_changed');
  for (const ref of cp.consumed) passage(db, cp, ref.passage_id, ref);
  for (const dependency of cp.memory ?? []) checkMemoryDependency(db, dependency, cp.projectId);
  for (const ref of cp.history) eligibleAnswer(db, ref.runId, ref.publicationDigest, cp.projectId);
  return { ...run, ancestry: closure(db, cp) };
}
function attachment(db: DatabaseSync, threadId: string, id: string) {
  const row = one(db, "SELECT a.*,m.rights_json,m.extraction_json,o.original_path,o.sha256,o.bytes FROM knowledge_attachments a JOIN knowledge_attachment_metadata m ON m.attachment_id=a.id JOIN knowledge_attachment_originals o ON o.attachment_id=a.id AND o.role='original' WHERE a.id=? AND a.chat_kind='learning' AND a.chat_id=?", id, threadId);
  if (!row || deleted(db, 'attachment', id) || json<Record<string, unknown>>(row.rights_json).model_input !== true) reject('learning_attachment_unavailable');
  if (!['image/png', 'image/jpeg', 'image/webp', 'application/pdf'].includes(String(row.media_type))) reject('learning_attachment_unsupported');
  const extraction = row.extraction_json ? json<{ text?: string; blocks?: { text?: string }[] }>(row.extraction_json) : null;
  const extracted = extraction?.text ?? extraction?.blocks?.map(b => b.text ?? '').join('\n') ?? '';
  if (row.media_type === 'application/pdf' && (row.extraction_state !== 'ready' || !extracted.trim())) reject('learning_attachment_extraction_unavailable');
  return { row, stamp: sha(row), extracted };
}
function saveCheckpoint(db: DatabaseSync, runId: string, cp: Checkpoint) { bounded(cp); db.prepare('UPDATE learn_harness_answers SET reference_json=? WHERE run_id=?').run(canonical(cp), runId); }
function envelope(run: RunSnapshot): LibraryToolEnvelope {
  const cp = run.checkpoint;
  return { sessionId: run.mapping!.runtime.session_id, operationId: run.receipt.run_id, attemptId: cp.attemptId,
    scope: { kind: 'study', entity_id: cp.projectId }, revisionIds: cp.revisionIds,
    policyRevision: cp.policyRevision, contextEpoch: cp.contextEpoch, cancellationEpoch: cp.cancellationEpoch };
}
/** No query engine result (including text/locators) is authority. Resolve canonical rows. */
function source(db: DatabaseSync, cp: Checkpoint, revisionId: string) {
  const row = one(db, "SELECT r.*,d.title,d.source_id,d.scope_entity FROM knowledge_revisions r JOIN knowledge_documents d ON d.active_revision=r.id WHERE r.id=? AND r.status='ready' AND d.deleted_at IS NULL AND d.reserved=0 AND d.scope_kind='personal-library'", revisionId);
  if (!row || (cp.revisionIds !== null && !cp.revisionIds.includes(revisionId)) ||
    (row.scope_entity !== null && row.scope_entity !== cp.projectId) ||
    ['knowledge-revision', 'revision'].some(t => deleted(db, t, revisionId)) ||
    ['knowledge-document', 'document'].some(t => deleted(db, t, String(row.document_id)))) reject('learning_source_unavailable');
  const rights = json<Record<string, unknown>>(row.rights_json), metadata = effectiveKnowledgeMetadata(db, json<Metadata>(row.metadata_json));
  if (!['display', 'cache', 'index', 'embedding', 'model_input', 'derivation'].every(k => rights[k] === true) ||
    ['retracted', 'superseded', 'access_changed', 'repository_removed'].some(k => metadata[k]) ||
    ['draft', 'preprint'].includes(String(metadata.publication_status)) ||
    (Array.isArray(metadata.replaced_topics) && metadata.replaced_topics.length) || (metadata.correction && !metadata.content_reviewed)) reject('learning_source_unavailable');
  return { row, metadata, rights };
}
function passage(db: DatabaseSync, cp: Checkpoint, passageId: string, expected?: LibraryDependency): LibraryPassage {
  const row = one(db, 'SELECT * FROM knowledge_passages WHERE id=?', passageId);
  if (!row) reject('learning_source_unavailable');
  const revision = source(db, cp, String(row.revision_id));
  const locators = json<LibraryDependency['locators']>(row.locators_json);
  if (locators.some(l => typeof l.page === 'number' && Array.isArray(revision.metadata.excluded_pages) && revision.metadata.excluded_pages.includes(l.page))) reject('learning_source_unavailable');
  const result = { id: passageId, document_id: String(revision.row.document_id), document_revision: String(row.revision_id), text: String(row.text), locators };
  if (expected && canonical({ document_id: result.document_id, document_revision: result.document_revision, passage_id: passageId, locators }) !== canonical(expected)) reject('learning_source_changed');
  return result;
}
const referenceFor = (p: LibraryPassage): LibraryDependency => ({ document_id: p.document_id, document_revision: p.document_revision, passage_id: p.id, locators: p.locators });
function sourceDependency(db: DatabaseSync, cp: Checkpoint, revisionId: string): Dependency {
  const { row, metadata, rights } = source(db, cp, revisionId);
  const representative = rows(db, 'SELECT id,locators_json FROM knowledge_passages WHERE revision_id=? ORDER BY ordinal LIMIT 4096', revisionId)
    .find(p => !json<LibraryDependency['locators']>(p.locators_json).some(l => typeof l.page === 'number' && Array.isArray(metadata.excluded_pages) && metadata.excluded_pages.includes(l.page)));
  if (!representative) reject('learning_source_unavailable');
  const target = { type: 'library_revision' as const, id: revisionId };
  return { target, expected_revision: sha({ identity: target, document_id: row.document_id, sha256: row.sha256,
    title: row.title, source_id: row.source_id, metadata, rights, passage_id: representative.id, locators: json(representative.locators_json) }) };
}
function eligibleAnswer(db: DatabaseSync, runId: string, expected: string, projectId: string | null, seen = new Set<string>()): AnswerReference {
  if (seen.has(runId) || seen.size >= 100) reject('learning_history_limit'); seen.add(runId);
  const a = one(db, "SELECT a.reference_json,a.publication_digest,a.thread_id,l.manifest_json,l.project_id,l.state,e.* FROM learn_harness_answers a JOIN memory_answer_lineage l ON l.evidence_id='learn-answer:'||a.run_id JOIN learning_evidence e ON e.id=l.evidence_id WHERE a.run_id=? AND a.state='completed'", runId);
  if (!a || a.state !== 'active' || a.publication_digest !== expected || (a.project_id !== null && a.project_id !== projectId) ||
    deleted(db, 'learning_evidence', 'learn-answer:' + runId) || deleted(db, 'learn_run', runId) ||
    one(db, 'SELECT 1 FROM memory_suppression WHERE source_key=?', 'evidence:learn-answer:' + runId)) reject('learning_history_unavailable');
  const reference = json<AnswerReference>(a.reference_json), manifest = json<{ version: 1; inputs: AnswerReference['inputs']; dependencies: Dependency[] }>(a.manifest_json);
  summary(db, String(a.thread_id));
  if (canonical(reference.runtime) !== canonical(mapping(db, String(a.thread_id))?.runtime) ||
    reference.message_ids.some(id => deleted(db, 'learn_message', id)) || sha({ evidence: { id: a.id, kind: a.kind, topic_id: a.topic_id,
      entity_id: a.entity_id, payload_json: a.payload_json, created_at: a.created_at }, manifest, project_id: a.project_id }) !== expected) reject('learning_history_unavailable');
  const cp = { projectId, revisionIds: null } as Checkpoint;
  for (const citation of reference.citations) passage(db, cp, citation.passage_id, { document_revision: citation.revision_id,
    document_id: citation.document_id, passage_id: citation.passage_id, locators: citation.locators });
  for (const dep of [...manifest.dependencies, ...manifest.inputs.map(i => i.dependency)]) {
    if (dep.target.type === 'library_revision') { if (canonical(sourceDependency(db, cp, dep.target.id)) !== canonical(dep)) reject('learning_history_unavailable'); }
    else if (dep.target.type === 'memory_revision') checkMemoryDependency(db, dep, projectId);
    else if (dep.target.type === 'learning_evidence' && dep.target.id.startsWith('learn-answer:')) eligibleAnswer(db, dep.target.id.slice(13), dep.expected_revision, projectId, new Set(seen));
    else reject('learning_history_unavailable');
  }
  return reference;
}
function closure(db: DatabaseSync, cp: Checkpoint) {
  const inputs: AnswerReference['inputs'] = [], dependencies: Dependency[] = [];
  for (const pin of cp.history) {
    const previous = eligibleAnswer(db, pin.runId, pin.publicationDigest, cp.projectId);
    inputs.push({ kind: 'committed_evidence', dependency: { target: { type: 'learning_evidence', id: 'learn-answer:' + pin.runId }, expected_revision: pin.publicationDigest } }, ...previous.inputs);
    dependencies.push(...previous.dependencies);
  }
  for (const ref of cp.consumed) dependencies.push(sourceDependency(db, cp, ref.document_revision));
  for (const dependency of cp.memory ?? []) {
    checkMemoryDependency(db, dependency, cp.projectId); dependencies.push(dependency);
  }
  const unique = <T>(values: T[]) => [...new Map(values.map(v => [canonical(v), v])).values()];
  if (unique(inputs).length > 100 || unique(dependencies).length > 100) reject('learning_reference_limit');
  return { inputs: unique(inputs), dependencies: unique(dependencies) };
}
function view(db: DatabaseSync, threadId: string): ReadView {
  const policyRevision = policy(db), s = summary(db, threadId);
  const refs = rows(db, "SELECT reference_json,publication_digest FROM learn_harness_answers WHERE thread_id=? AND state='completed' ORDER BY run_id LIMIT 101", threadId);
  if (refs.length > 100) reject('learning_history_limit');
  const base = { conversation: s.conversation, mapping: mapping(db, threadId), references: refs.map(a => ({ reference: json<AnswerReference>(a.reference_json), publicationDigest: String(a.publication_digest) }))
    .filter(({ reference }) => !deleted(db, 'learn_run', reference.run_id) && !deleted(db, 'learning_evidence', 'learn-answer:' + reference.run_id) &&
      ![reference.input_id, ...reference.message_ids].some(id => deleted(db, 'learn_message', id))),
    legacyReferences: json<NonNullable<ReadView['legacyReferences']>>(one(db, "SELECT message_refs_json FROM legacy_history_imports WHERE thread_id=? AND state='active'", threadId)?.message_refs_json ?? '[]'),
    contextEpoch: epoch(db), policyRevision };
  return { ...base, stamp: sha(base) };
}
function enqueue(db: DatabaseSync, runtime: RuntimeIdentity, sessionId: string, operationId: string, attemptId: string): Purge {
  const purgeId = 'purge:' + sha([runtime.profileId, runtime.storeId, sessionId, operationId, attemptId]);
  db.prepare("INSERT OR IGNORE INTO learn_harness_purges VALUES(?,?,?,?,?,?,'pending')").run(purgeId, runtime.profileId, runtime.storeId, sessionId, operationId, attemptId);
  return one(db, 'SELECT * FROM learn_harness_purges WHERE purge_id=?', purgeId) as unknown as Purge;
}
function persistReceipt(db: DatabaseSync, runId: string, receipt: LearningReceipt) {
  db.prepare('UPDATE conversation_commands SET result_json=? WHERE idempotency_key=(SELECT idempotency_key FROM learn_runs WHERE id=?)').run(canonical(receipt), runId);
}
function retire(db: DatabaseSync, threadId: string) {
  const commands = rows(db, "SELECT idempotency_key FROM conversation_commands WHERE target_type='learn_thread' AND target_id=?", threadId);
  for (const c of commands) {
    db.prepare("INSERT OR IGNORE INTO learn_command_tombstones VALUES('conversation_commands',?,?)").run(c.idempotency_key, now());
    db.prepare("INSERT OR IGNORE INTO deletion_ledger VALUES('conversation_command',?,?)").run(c.idempotency_key, now());
  }
  db.prepare("DELETE FROM conversation_commands WHERE target_type='learn_thread' AND target_id=?").run(threadId);
}
/** Integration: execute inside the same synchronous shared-writer transaction as BF01. */
export function executeLearning<C extends LearningCommand>(db: DatabaseSync, command: C): LearningResults[C['type']] {
  validateLearningCommand(command);
  if (!db.isTransaction) reject('learning_transaction_required');
  return execute(db, command) as LearningResults[C['type']];
}
function execute(db: DatabaseSync, command: LearningCommand): unknown {
  switch (command.type) {
    case 'learning.legacy.prepare': {
      policy(db);
      if (one(db, 'SELECT 1 FROM legacy_history_imports WHERE thread_id=?', command.threadId)) reject('learning_migration_already_imported');
      const s = summary(db, command.threadId);
      if (s.conversation.revision !== command.expectedRevision) reject('conversation_revision_conflict');
      if (mapping(db, command.threadId)) return null;
      if (one(db, 'SELECT 1 FROM learn_harness_mappings WHERE thread_id=?', command.threadId) ||
        one(db, "SELECT 1 FROM learn_runs WHERE thread_id=? AND state='running'", command.threadId)) reject('learning_migration_or_reconciliation_required');
      const legacy = rows(db, 'SELECT m.*,r.state AS run_outcome,r.updated_at AS completed_at FROM learn_messages m LEFT JOIN learn_runs r ON r.id=m.run_id AND r.thread_id=m.thread_id WHERE m.thread_id=? ORDER BY m.created_at,m.rowid LIMIT 4097', command.threadId);
      if (!legacy.length) return null;
      if (legacy.length > 4096) reject('learning_migration_budget');
      const messages = legacy.map(m => {
        const citations = json<unknown[]>(m.citations_json);
        if (!Array.isArray(citations) || citations.some(c => !c || typeof c !== 'object' || Array.isArray(c)) ||
          !Number.isFinite(Date.parse(String(m.created_at))) || !/(?:Z|[+-]\d\d:\d\d)$/.test(String(m.created_at))) reject('learning_migration_source');
        if (m.role === 'assistant' && (!['completed', 'cancelled', 'failed', 'interrupted'].includes(String(m.run_outcome)) ||
          !Number.isFinite(Date.parse(String(m.completed_at))) || !/(?:Z|[+-]\d\d:\d\d)$/.test(String(m.completed_at)) ||
          Date.parse(String(m.completed_at)) < Date.parse(String(m.created_at)))) reject('learning_migration_source');
        return { id: String(m.id), role: String(m.role), content: String(m.content), runId: String(m.run_id), createdAt: String(m.created_at), citations,
          ...(m.role === 'assistant' ? { completedAt: String(m.completed_at), legacyOutcome: String(m.run_outcome) } : {}) };
      });
      const document = canonical({ format: 'renulus.saved-session/1', conversationId: command.threadId, title: s.conversation.title, messages });
      if (Buffer.byteLength(document) > 8 * 1024 * 1024) reject('learning_migration_budget');
      const sessionId = 'ses_' + sha(['renulus-h06-session-v1', command.identity.profileId, command.identity.storeId, command.threadId]);
      const operationId = 'migration_' + sessionId.slice(4), sourceDigest = digest(document), sourceStamp = sha([view(db, command.threadId).stamp, s.draftRevision]);
      const refs = messages.map(m => ({ id: 'msg_' + sha(['renulus-h06-message-v1', sessionId, m.id]), role: m.role, runId: m.runId }));
      db.prepare("INSERT INTO legacy_history_imports VALUES(?,?,?,?,?,?,?,?,'reserved',?)").run(command.threadId, command.identity.profileId, command.identity.storeId,
        sessionId, operationId, sourceDigest, sourceStamp, canonical(refs), now());
      return { document, sessionId, sourceDigest, sourceStamp, operationId, messageCount: messages.length };
    }
    case 'learning.legacy.activate': {
      const s = summary(db, command.threadId), stamp = sha([view(db, command.threadId).stamp, s.draftRevision]);
      const receipt = one(db, "SELECT * FROM legacy_history_imports WHERE thread_id=? AND state='reserved'", command.threadId);
      if (!receipt || receipt.profile_id !== command.identity.profileId || receipt.store_id !== command.identity.storeId ||
        receipt.source_digest !== command.sourceDigest || receipt.source_stamp !== command.sourceStamp || stamp !== command.sourceStamp) reject('learning_migration_conflict');
      const result: Mapping = { contract_version: 'harness/1', conversation: { type: 'learn_thread', id: command.threadId }, retention: 'saved',
        runtime: { contract_version: 'harness/1', profile_id: command.identity.profileId, store_id: command.identity.storeId,
          engine: { name: 'opencode', version: '2.0.26', source_commit: SOURCE }, session_id: String(receipt.session_id) } };
      db.prepare('INSERT INTO learn_harness_mappings(thread_id,profile_id,store_id,session_id,mapping_json,create_request_id,process_generation) VALUES(?,?,?,?,?,?,?)')
        .run(command.threadId, command.identity.profileId, command.identity.storeId, receipt.session_id, canonical(result), receipt.operation_id, command.identity.generation);
      db.prepare("UPDATE legacy_history_imports SET state='active' WHERE thread_id=?").run(command.threadId);
      bump(db); return result;
    }
    case 'learning.begin': {
      const p = policy(db); commandCurrent(db, command.idempotencyKey); summary(db, command.threadId);
      const existingMapping = mapping(db, command.threadId);
      if (existingMapping && (existingMapping.runtime.profile_id !== command.identity.profileId || existingMapping.runtime.store_id !== command.identity.storeId)) reject('learning_mapping_conflict');
      const intent = learningSendIntent(command);
      const requestHash = sha({ operation: 'send', target_type: 'learn_thread', target_id: command.threadId, request: intent });
      const previous = one(db, 'SELECT * FROM conversation_commands WHERE idempotency_key=?', command.idempotencyKey);
      if (previous) {
        if (previous.request_hash !== requestHash) reject('idempotency_conflict');
        return { fresh: false, run: snapshot(db, json<LearningReceipt>(previous.result_json).run_id) };
      }
      const s = summary(db, command.threadId);
      if (s.conversation.lifecycle !== 'active') reject('conversation_archived');
      if (s.conversation.revision !== command.expectedRevision || s.draftRevision !== command.expectedDraftRevision) reject('conversation_revision_conflict');
      if (s.draftRefs.length && canonical(s.draftRefs) !== canonical(intent.content_refs)) reject('learning_reference_input_not_admitted');
      const attachments = intent.content_refs.map(ref => ({ id: ref.target.id, stamp: attachment(db, command.threadId, ref.target.id).stamp }));
      if (one(db, "SELECT 1 FROM learn_runs WHERE thread_id=? AND state='running'", command.threadId)) reject('learning_run_busy');
      const m = mapping(db, command.threadId);
      if (m && (m.runtime.profile_id !== command.identity.profileId || m.runtime.store_id !== command.identity.storeId)) reject('learning_mapping_conflict');
      if (!m && (one(db, 'SELECT 1 FROM learn_messages WHERE thread_id=? LIMIT 1', command.threadId) || one(db, 'SELECT 1 FROM learn_harness_mappings WHERE thread_id=?', command.threadId))) reject('learning_migration_or_reconciliation_required');
      const now_ = now();
      db.prepare('UPDATE learn_conversations SET revision=revision+1,draft_text=?,updated_at=? WHERE thread_id=?').run(command.text, now_, command.threadId);
      const conversation = summary(db, command.threadId).conversation;
      const cp: Checkpoint = { version: 1, kind: 'bf02-target-pending', identity: command.identity, attemptId: command.attemptId,
        conversationRevision: conversation.revision, draftRevision: s.draftRevision, policyRevision: p, contextEpoch: epoch(db), cancellationEpoch: 0,
        projectId: conversation.project_id, projectRevision: s.membership ? Number(s.membership.project_revision) : null,
        membershipRevision: s.membership ? Number(s.membership.membership_revision) : null, revisionIds: conversation.project_id === null ? null :
          rows(db, 'SELECT revision_id FROM study_project_documents WHERE project_id=? ORDER BY revision_id LIMIT 1001', conversation.project_id).map(r => String(r.revision_id)),
        inputSha256: digest(command.text), consumed: [], memory: [], history: [], attachments,
        intent: (({ text: _text, images: _images, ...metadata }) => metadata)(intent) };
      if (cp.revisionIds && cp.revisionIds.length > 1000) reject('learning_reference_limit');
      const receipt: LearningReceipt = { run_id: command.runId, state: 'running', conversation };
      db.prepare("INSERT INTO learn_runs VALUES(?,?,?,'running',NULL,?,?)").run(command.runId, command.threadId, command.idempotencyKey, now_, now_);
      db.prepare("INSERT INTO learn_harness_answers(run_id,thread_id,request_digest,state,reference_json,command_request_id,process_generation) VALUES(?,?,?,'reserved',?,?,?)")
        .run(command.runId, command.threadId, requestHash, canonical(cp), command.idempotencyKey, command.identity.generation);
      db.prepare("INSERT INTO conversation_commands VALUES(?,'send','learn_thread',?,?,?,?)").run(command.idempotencyKey, command.threadId, requestHash, canonical(receipt), now_);
      if (!m) db.prepare('INSERT INTO learn_harness_mappings(thread_id,profile_id,store_id,create_request_id,process_generation) VALUES(?,?,?,?,?)')
        .run(command.threadId, command.identity.profileId, command.identity.storeId, command.runId, command.identity.generation);
      return { fresh: true, run: snapshot(db, command.runId) };
    }
    case 'learning.current': return current(db, command.runId, command.binding);
    case 'learning.attachments': {
      const run = current(db, command.runId);
      return (run.checkpoint.attachments ?? []).map(pin => {
        const { row, extracted } = attachment(db, run.receipt.conversation.identity.id, pin.id);
        return { id: pin.id, mediaType: String(row.media_type), path: row.original_path as string | null, sha256: String(row.sha256), bytes: Number(row.bytes), text: extracted };
      });
    }
    case 'learning.attachment.cleanup': {
      const key = 'design_c.attachment_cleanup';
      const pending = json<{ attachment_id: string; relative_directory: string }[]>(one(db, 'SELECT value FROM preferences WHERE key=?', key)?.value ?? '[]');
      const remaining = pending.filter(e => !command.removed.includes(e.attachment_id) || !deleted(db, 'attachment', e.attachment_id) || one(db, 'SELECT 1 FROM knowledge_attachments WHERE id=?', e.attachment_id));
      if (remaining.length) db.prepare('INSERT INTO preferences VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at').run(key, canonical(remaining), now());
      else db.prepare('DELETE FROM preferences WHERE key=?').run(key);
      return remaining.filter(e => deleted(db, 'attachment', e.attachment_id) && !one(db, 'SELECT 1 FROM knowledge_attachments WHERE id=?', e.attachment_id) && !one(db, 'SELECT 1 FROM knowledge_attachment_originals WHERE attachment_id=?', e.attachment_id));
    }
    case 'learning.map': {
      const run = current(db, command.runId), cp = run.checkpoint;
      const result: Mapping = { contract_version: 'harness/1', conversation: run.receipt.conversation.identity, retention: 'saved',
        runtime: { contract_version: 'harness/1', profile_id: cp.identity.profileId, store_id: cp.identity.storeId,
          engine: { name: 'opencode', version: '2.0.26', source_commit: SOURCE }, session_id: command.sessionId } };
      if (run.mapping && canonical(run.mapping) !== canonical(result)) reject('learning_mapping_conflict');
      const m = one(db, 'SELECT * FROM learn_harness_mappings WHERE thread_id=?', result.conversation.id)!;
      if (!run.mapping && (m.create_request_id !== command.runId || m.process_generation !== cp.identity.generation)) reject('learning_mapping_conflict');
      db.prepare('UPDATE learn_harness_mappings SET session_id=?,mapping_json=? WHERE thread_id=?').run(command.sessionId, canonical(result), result.conversation.id);
      return result;
    }
    case 'learning.bind': {
      const run = current(db, command.binding.operation_id, command.binding, true);
      if (run.inputId && run.inputId !== command.binding.input_id) reject('learning_binding_conflict');
      db.prepare("UPDATE learn_harness_answers SET input_id=?,state='submitted' WHERE run_id=? AND state IN ('reserved','submitted')").run(command.binding.input_id, command.binding.operation_id);
      return current(db, command.binding.operation_id, command.binding);
    }
    case 'learning.consume': {
      const run = current(db, command.binding.operation_id, command.binding);
      for (const ref of command.references) passage(db, run.checkpoint, ref.passage_id, ref);
      run.checkpoint.consumed = [...new Map([...run.checkpoint.consumed, ...command.references].map(ref => [canonical(ref), ref])).values()];
      if (run.checkpoint.consumed.length > 100) reject('learning_reference_limit');
      saveCheckpoint(db, command.binding.operation_id, run.checkpoint); return { recorded: true };
    }
    case 'learning.consumeMemory': {
      const run = current(db, command.binding.operation_id, command.binding);
      for (const dependency of command.dependencies) checkMemoryDependency(db, dependency, run.checkpoint.projectId);
      run.checkpoint.memory = [...new Map([...(run.checkpoint.memory ?? []), ...command.dependencies].map(dependency => [canonical(dependency), dependency])).values()];
      if (run.checkpoint.memory.length > 100) reject('learning_reference_limit');
      saveCheckpoint(db, command.binding.operation_id, run.checkpoint); return { recorded: true };
    }
    case 'learning.context': {
      const run = current(db, command.binding.operation_id, command.binding), messages = command.messages;
      const boundary = messages.findIndex(m => m.id === command.binding.input_id);
      if (boundary < 0 || messages[boundary].role !== 'user' || messages.filter(m => m.id === command.binding.input_id).length !== 1 ||
        messages.slice(boundary + 1).some(m => m.role === 'user')) reject('learning_context_invalid');
      const allowed = new Set(messages.slice(boundary).map(m => m.id));
      const previous = rows(db, "SELECT run_id,reference_json,publication_digest FROM learn_harness_answers WHERE thread_id=? AND state='completed' ORDER BY run_id LIMIT 101", run.receipt.conversation.identity.id);
      if (previous.length > 100) reject('learning_history_limit');
      for (const a of previous) {
        let ref: AnswerReference;
        try { ref = eligibleAnswer(db, String(a.run_id), String(a.publication_digest), run.checkpoint.projectId); }
        catch (error) { if (error && typeof error === 'object' && 'code' in error && /^(learning_(history_unavailable|source_)|memory_(dependency_revoked|lineage_unknown|project_scope|capture_suppressed|evidence_missing|evidence_invalid)$)/.test(String(error.code))) continue; throw error; }
        const roles = (id: string) => messages.slice(0, boundary).filter(m => m.id === id).map(m => m.role);
        if (canonical(roles(ref.input_id)) !== canonical(['user']) || ref.message_ids.some(id => !roles(id).length || roles(id).some(r => !['assistant', 'tool'].includes(r)))) continue;
        [ref.input_id, ...ref.message_ids].forEach(id => allowed.add(id));
        const pin = { runId: ref.run_id, publicationDigest: String(a.publication_digest) };
        if (!run.checkpoint.history.some(p => p.runId === pin.runId)) run.checkpoint.history.push(pin);
      }
      saveCheckpoint(db, command.binding.operation_id, run.checkpoint);
      return { message_ids: [...new Set(messages.filter(m => allowed.has(m.id)).map(m => m.id))], learner_context: '' };
    }
    case 'learning.publish': {
      const previous = snapshot(db, command.binding.operation_id);
      if (previous.receipt.state === 'completed') { policy(db); if (canonical(previous.receipt.answer_reference) !== canonical(command.reference)) reject('learning_publication_conflict'); return previous.receipt; }
      const run = current(db, command.binding.operation_id, command.binding), ref = command.reference, cp = run.checkpoint;
      const consumed = cp.consumed.map(c => ({ document_id: c.document_id, revision_id: c.document_revision, passage_id: c.passage_id, locators: c.locators }));
      const ancestors = closure(db, cp);
      if (ref.run_id !== run.receipt.run_id || ref.thread_id !== run.receipt.conversation.identity.id || ref.input_id !== run.inputId ||
        ref.message_ids.includes(ref.input_id) || canonical(ref.runtime) !== canonical(run.mapping?.runtime) || canonical(ref.citations) !== canonical(consumed) ||
        canonical(ref.inputs) !== canonical(ancestors.inputs) || canonical(ref.dependencies) !== canonical(ancestors.dependencies)) reject('learning_publication_conflict');
      const evidence = { id: 'learn-answer:' + ref.run_id, kind: 'study-answer', topic_id: cp.intent ? cp.intent.topic_id : summary(db, ref.thread_id).topicId,
        entity_id: ref.thread_id, payload_json: canonical({ scope: { kind: 'study', entity_id: ref.thread_id }, answer_reference: ref }), created_at: now() };
      const manifest = { version: 1, ...ancestors }, publication = sha({ evidence, manifest, project_id: cp.projectId });
      db.prepare('INSERT INTO learning_evidence VALUES(?,?,?,?,?,?)').run(evidence.id, evidence.kind, evidence.topic_id, evidence.entity_id, evidence.payload_json, evidence.created_at);
      db.prepare("INSERT INTO memory_answer_lineage VALUES(?,?,?,'active',?,?)").run(evidence.id, publication, canonical(manifest), cp.projectId, now());
      db.prepare("UPDATE learn_harness_answers SET state='completed',reference_json=?,publication_digest=? WHERE run_id=?").run(canonical(ref), publication, ref.run_id);
      db.prepare("UPDATE learn_runs SET state='completed',updated_at=? WHERE id=?").run(now(), ref.run_id);
      db.prepare("UPDATE learn_conversations SET revision=revision+1,draft_text='',draft_refs_json='[]',draft_revision=draft_revision+1,updated_at=? WHERE thread_id=?").run(now(), ref.thread_id);
      db.prepare('UPDATE learn_threads SET updated_at=? WHERE id=?').run(now(), ref.thread_id);
      const receipt: LearningReceipt = { run_id: ref.run_id, state: 'completed', conversation: summary(db, ref.thread_id).conversation, answer_reference: ref };
      persistReceipt(db, ref.run_id, receipt); return receipt;
    }
    case 'learning.stop': {
      // Stop is a fence even while Test/policy/context changed; no assistance disclosure.
      const a = one(db, 'SELECT a.*,r.state AS run_state FROM learn_harness_answers a JOIN learn_runs r ON r.id=a.run_id WHERE a.run_id=?', command.runId);
      if (!a) return { receipt: null, sessionId: null };
      const m = mapping(db, String(a.thread_id));
      if (a.run_state !== 'running') return { receipt: null, sessionId: null };
      const cp = json<Checkpoint>(a.reference_json); cp.cancellationEpoch++;
      saveCheckpoint(db, command.runId, cp);
      db.prepare('UPDATE learn_harness_answers SET state=? WHERE run_id=?').run(command.state === 'failed' ? 'failed' : 'cancelled', command.runId);
      db.prepare('UPDATE learn_runs SET state=?,updated_at=? WHERE id=?').run(command.state, now(), command.runId);
      const prior = one(db, 'SELECT result_json FROM conversation_commands WHERE idempotency_key=(SELECT idempotency_key FROM learn_runs WHERE id=?)', command.runId);
      if (!prior) reject('learning_receipt_missing');
      const receipt: LearningReceipt = { run_id: command.runId, state: command.state, conversation: json<LearningReceipt>(prior.result_json).conversation };
      persistReceipt(db, command.runId, receipt); return { receipt, sessionId: m?.runtime.session_id ?? null };
    }
    case 'learning.lifecycle': case 'learning.project': case 'learning.delete': {
      policy(db); commandCurrent(db, command.idempotencyKey);
      const s = summary(db, command.threadId), request = { ...command, type: undefined, idempotencyKey: undefined };
      delete request.type; delete request.idempotencyKey;
      const requestHash = sha({ operation: command.type, request });
      const previous = one(db, 'SELECT * FROM conversation_commands WHERE idempotency_key=?', command.idempotencyKey);
      if (previous) { if (previous.request_hash !== requestHash) reject('idempotency_conflict'); return json(previous.result_json); }
      if (s.conversation.revision !== command.expectedRevision) reject('conversation_revision_conflict');
      if (command.type === 'learning.lifecycle') db.prepare('UPDATE learn_conversations SET lifecycle=? WHERE thread_id=?').run(command.lifecycle, command.threadId);
      if (command.type === 'learning.project') {
        if (command.projectId !== null) {
          const project = one(db, "SELECT * FROM study_projects WHERE id=? AND lifecycle='active'", command.projectId);
          if (!project || deleted(db, 'project', command.projectId)) reject('project_missing');
          // Public ProjectMove has no project revision. Resolve it under this same
          // writer transaction; trusted callers may additionally fence an exact revision.
          if (command.expectedProjectRevision !== null && project.revision !== command.expectedProjectRevision) reject('project_revision_conflict');
        }
        db.prepare("DELETE FROM study_project_chats WHERE chat_kind='learning' AND chat_id=?").run(command.threadId);
        if (command.projectId) db.prepare("INSERT INTO study_project_chats VALUES(?,?,'learning',?,0,1,?)").run('membership:' + sha([command.projectId, command.threadId]), command.projectId, command.threadId, now());
      }
      if (command.type === 'learning.delete') {
        const imported = one(db, 'SELECT * FROM legacy_history_imports WHERE thread_id=?', command.threadId);
        if (imported) {
          db.prepare("UPDATE legacy_history_imports SET state='deleted',message_refs_json='[]' WHERE thread_id=?").run(command.threadId);
          enqueue(db, { profileId: String(imported.profile_id), storeId: String(imported.store_id), generation: 'deletion' }, String(imported.session_id), command.idempotencyKey, '1');
        }
        const attachments = rows(db, "SELECT id FROM knowledge_attachments WHERE chat_kind='learning' AND chat_id=? LIMIT 201", command.threadId);
        if (attachments.length > 200) reject('attachment_cleanup_limit');
        const key = 'design_c.attachment_cleanup';
        const pending = json<{ attachment_id: string; relative_directory: string }[]>(one(db, 'SELECT value FROM preferences WHERE key=?', key)?.value ?? '[]');
        for (const a of attachments) {
          const id = String(a.id); if (!/^[A-Za-z0-9_-]{1,128}$/.test(id)) reject('attachment_id_invalid');
          db.prepare("INSERT OR IGNORE INTO deletion_ledger VALUES('attachment',?,?)").run(id, now());
          for (const original of rows(db, 'SELECT id FROM knowledge_attachment_originals WHERE attachment_id=?', id))
            db.prepare("INSERT OR IGNORE INTO deletion_ledger VALUES('attachment_original',?,?)").run(original.id, now());
          if (!pending.some(e => e.attachment_id === id)) pending.push({ attachment_id: id, relative_directory: 'library/attachments/' + id });
        }
        if (pending.length > 1000 || Buffer.byteLength(canonical(pending)) > 512 * 1024) reject('attachment_cleanup_limit');
        if (pending.length) db.prepare('INSERT INTO preferences VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at').run(key, canonical(pending), now());
        db.prepare("DELETE FROM knowledge_attachments WHERE chat_kind='learning' AND chat_id=?").run(command.threadId);
        const m = mapping(db, command.threadId);
        if (m) enqueue(db, { profileId: m.runtime.profile_id, storeId: m.runtime.store_id, generation: 'deletion' }, m.runtime.session_id, command.idempotencyKey, '1');
        const answers = rows(db, 'SELECT run_id FROM learn_harness_answers WHERE thread_id=?', command.threadId);
        for (const a of answers) {
          const evidenceId = 'learn-answer:' + a.run_id;
          db.prepare("UPDATE memory_answer_lineage SET state='revoked' WHERE evidence_id=?").run(evidenceId);
          db.prepare("INSERT OR IGNORE INTO memory_suppression VALUES(?,?)").run('evidence:' + evidenceId, now());
          db.prepare("UPDATE memory_jobs SET state='cancelled',updated_at=? WHERE evidence_id=? AND state IN ('queued','running')").run(now(), evidenceId);
          db.prepare('DELETE FROM learning_evidence WHERE id=?').run(evidenceId);
          db.prepare("INSERT OR IGNORE INTO deletion_ledger VALUES('learning_evidence',?,?)").run(evidenceId, now());
        }
        db.prepare("DELETE FROM study_project_chats WHERE chat_kind='learning' AND chat_id=?").run(command.threadId);
        db.prepare('DELETE FROM learn_threads WHERE id=?').run(command.threadId);
        db.prepare("INSERT OR IGNORE INTO deletion_ledger VALUES('learn_thread',?,?)").run(command.threadId, now());
        retire(db, command.threadId);
        db.prepare("INSERT OR IGNORE INTO learn_command_tombstones VALUES('conversation_commands',?,?)").run(command.idempotencyKey, now());
        bump(db); return { deleted: true, identity: s.conversation.identity };
      }
      db.prepare('UPDATE learn_conversations SET revision=revision+1,updated_at=? WHERE thread_id=?').run(now(), command.threadId);
      bump(db); const result = summary(db, command.threadId).conversation;
      db.prepare("INSERT INTO conversation_commands VALUES(?,?,'learn_thread',?,?,?,?)").run(command.idempotencyKey, command.type, command.threadId, requestHash, canonical(result), now()); return result;
    }
    case 'learning.view': return view(db, command.threadId);
    case 'learning.read.check': if (view(db, command.threadId).stamp !== command.stamp) reject('learning_read_stale'); return { current: true };
    case 'learning.scan': {
      const stamp = sha({ contextEpoch: epoch(db), policyRevision: policy(db), scope: command.scope });
      if (command.epoch !== null && command.epoch !== stamp) reject('learning_cursor_stale');
      if (command.scope.projectId !== null && deleted(db, 'project', command.scope.projectId)) reject('project_missing');
      const matches = rows(db, "SELECT t.id FROM learn_threads t JOIN learn_conversations c ON c.thread_id=t.id LEFT JOIN study_project_chats m ON m.chat_kind='learning' AND m.chat_id=t.id WHERE c.lifecycle<>'deleted' AND (?='all' OR c.lifecycle=?) AND (?='' OR m.project_id=?) AND t.id>? AND NOT EXISTS(SELECT 1 FROM deletion_ledger WHERE entity_type='learn_thread' AND entity_id=t.id) ORDER BY t.id LIMIT ?",
        command.scope.lifecycle, command.scope.lifecycle, command.scope.projectId ?? '', command.scope.projectId ?? '', command.after ?? '', command.limit + 1);
      return { views: matches.slice(0, command.limit).map(r => view(db, String(r.id))), next: matches.length > command.limit ? String(matches[command.limit - 1].id) : null, epoch: stamp };
    }
    case 'learning.library.plan': {
      const run = current(db, command.binding.operation_id, command.binding), eligible: string[] = [];
      const revisions = rows(db, "SELECT r.id FROM knowledge_revisions r JOIN knowledge_documents d ON d.active_revision=r.id WHERE r.status='ready' AND d.deleted_at IS NULL AND d.reserved=0 ORDER BY r.id LIMIT 1001");
      if (revisions.length > 1000) reject('learning_reference_limit');
      for (const r of revisions) { try { source(db, run.checkpoint, String(r.id)); eligible.push(String(r.id)); } catch (e) {
        if (e && typeof e === 'object' && 'code' in e && String(e.code).startsWith('learning_source_')) continue; throw e;
      } }
      return { revisionIds: eligible, envelope: envelope(run) };
    }
    case 'learning.library.resolve': {
      const run = current(db, command.binding.operation_id, command.binding);
      const passages = command.passageIds.map(id => passage(db, run.checkpoint, id));
      bounded(passages, 256 * 1024); return { passages, references: passages.map(referenceFor) };
    }
    case 'learning.purge.enqueue': return enqueue(db, command.identity, command.sessionId, command.operationId, command.attemptId);
    case 'learning.purge.list': return rows(db, "SELECT * FROM learn_harness_purges WHERE profile_id=? AND store_id=? AND state='pending' ORDER BY purge_id LIMIT 100", command.identity.profileId, command.identity.storeId);
    case 'learning.purge.ack': {
      const p = one(db, 'SELECT * FROM learn_harness_purges WHERE purge_id=? AND profile_id=? AND store_id=?', command.purgeId, command.identity.profileId, command.identity.storeId);
      if (!p) reject('learning_purge_missing');
      db.prepare("UPDATE learn_harness_purges SET state='removed' WHERE purge_id=?").run(command.purgeId); return { removed: true };
    }
  }
}
