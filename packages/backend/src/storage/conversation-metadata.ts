// SPDX-License-Identifier: MIT
/** BF02 saved Learning metadata, composed synchronously in the canonical writer's transaction.
 * Python sources: learn/conversation_repository.py, conversation_stream.py and design_c_contracts.py.
 * No database open, transaction management, native transcript, engine, files or provider calls. */
import type { DatabaseSync } from 'node:sqlite';
import { createHmac, randomBytes, randomUUID, timingSafeEqual } from 'node:crypto';
import { exact, integer, reject, text } from './contracts.ts';
import type { ConversationSummary } from './contracts.ts';
import { requireAssistance } from './conversation.ts';
import { canonical, digest, one, rows } from './schema.ts';
import { utcNow } from './export.ts';
import type { ContentLocator, ContentReference, ConversationDraft, LearningMetadataCommand, LearningMetadataResults,
  RunState, RunStatus } from '../domain/learning/metadata-contracts.ts';

const types = new Set(['learning.create', 'learning.get', 'learning.list', 'learning.draft.get',
  'learning.draft.save', 'learning.runs.list', 'learning.run.status']);
const cursorKey = randomBytes(32); // Like Python's repository: process-local, never persisted authority.
const states: RunState[] = ['running', 'completed', 'cancelled', 'failed', 'interrupted'];
const id = (v: unknown) => { text(v, 1, 256); if (!/^[A-Za-z0-9][A-Za-z0-9._:-]*$/.test(v)) reject('storage_invalid_command'); };
const nullableId = (v: unknown) => { if (v !== null) id(v); };
const key = (v: unknown) => { if (v !== null) text(v, 8, 128); };
const cursorValue = (v: unknown) => { if (v !== null) text(v, 1, 2048); };
function date(v: unknown) { text(v, 1, 64); if (!/^\d{4}-\d\d-\d\dT.+(?:Z|[+-]\d\d:\d\d)$/.test(v) || !Number.isFinite(Date.parse(v))) reject('storage_invalid_command'); }
function locator(v: ContentLocator) {
  if (!v || typeof v !== 'object') reject('storage_invalid_command');
  switch (v.kind) {
    case 'pdf': exact(v, ['kind', 'physical_page', 'printed_label']); integer(v.physical_page, 1); if (v.printed_label !== null) text(v.printed_label, 0, 80); break;
    case 'text': exact(v, ['kind', 'item_ref', 'section', 'start', 'end']); text(v.item_ref, 1, 256);
      if (v.section !== null) text(v.section, 0, 240); integer(v.start); integer(v.end, 1); if (v.end <= v.start) reject('storage_invalid_command'); break;
    case 'table': exact(v, ['kind', 'format', 'sheet_name', 'first_row', 'last_row', 'first_column', 'last_column']);
      if (!['csv', 'xlsx'].includes(v.format) || (v.format === 'xlsx') !== (v.sheet_name !== null)) reject('storage_invalid_command');
      if (v.sheet_name !== null) text(v.sheet_name, 1, 120);
      integer(v.first_row, 1); integer(v.last_row, v.first_row); integer(v.first_column, 1); integer(v.last_column, v.first_column); break;
    case 'image': exact(v, ['kind', 'frame', 'bounds']); integer(v.frame, 1);
      if (v.bounds !== null) {
        if (!Array.isArray(v.bounds) || v.bounds.length !== 4 || !v.bounds.every(n => typeof n === 'number' && Number.isFinite(n))) reject('storage_invalid_command');
        const [l, t, r, b] = v.bounds; if (!(0 <= l && l < r && r <= 1 && 0 <= t && t < b && b <= 1)) reject('storage_invalid_command');
      } break;
    default: reject('storage_invalid_command');
  }
}
function references(v: unknown): asserts v is ContentReference[] {
  if (!Array.isArray(v) || v.length > 20) reject('storage_invalid_command');
  for (const ref of v) {
    exact(ref, ['target', 'locator']); exact(ref.target, ['type', 'id']); id(ref.target.id);
    if (!['library_revision', 'note_revision', 'attachment', 'saved_test_version'].includes(String(ref.target.type))) reject('storage_invalid_command');
    if (ref.locator !== null) {
      if (ref.target.type === 'saved_test_version') reject('storage_invalid_command');
      locator(ref.locator as ContentLocator);
    }
  }
}
export function isLearningMetadataCommand(value: unknown): value is LearningMetadataCommand {
  return !!value && typeof value === 'object' && 'type' in value && types.has(String(value.type));
}
export function validateLearningMetadataCommand(command: LearningMetadataCommand): void {
  if (!command || typeof command !== 'object' || Array.isArray(command)) reject('storage_invalid_command');
  const v = command as unknown as Record<string, unknown>;
  switch (command.type) {
    case 'learning.create': {
      exact(v, ['type', 'request', 'idempotencyKey']); key(command.idempotencyKey);
      const r = command.request;
      exact(r, ['kind', 'title', 'temporary', 'project_id', 'topic_id', 'teaching_style', 'text', 'teaching_case_id']);
      if (r.kind !== 'learning' || r.temporary !== false || r.text !== '' || r.teaching_case_id !== null || !['direct', 'guided'].includes(r.teaching_style)) reject('storage_invalid_command');
      text(r.title, 1, 120); nullableId(r.project_id); nullableId(r.topic_id); break;
    }
    case 'learning.get': case 'learning.draft.get': exact(v, ['type', 'threadId']); id(command.threadId); break;
    case 'learning.list': exact(v, ['type', 'limit', 'cursor', 'lifecycle', 'projectId']); integer(command.limit, 1, 100);
      cursorValue(command.cursor); nullableId(command.projectId); if (!['active', 'archived'].includes(command.lifecycle)) reject('storage_invalid_command'); break;
    case 'learning.draft.save': exact(v, ['type', 'threadId', 'request', 'idempotencyKey']); id(command.threadId); key(command.idempotencyKey);
      exact(command.request, ['expected_revision', 'text', 'content_refs']); integer(command.request.expected_revision, 1);
      text(command.request.text, 0, 16000); references(command.request.content_refs); break;
    case 'learning.runs.list': exact(v, ['type', 'threadId', 'limit', 'cursor']); id(command.threadId); integer(command.limit, 1, 100); cursorValue(command.cursor); break;
    case 'learning.run.status': exact(v, ['type', 'threadId', 'runId', 'neutral']); id(command.threadId); id(command.runId);
      if (typeof command.neutral !== 'boolean') reject('storage_invalid_command'); break;
    default: reject('storage_invalid_command');
  }
}
function summaryShape(v: ConversationSummary) {
  exact(v, ['identity', 'kind', 'retention', 'lifecycle', 'revision', 'title', 'project_id', 'created_at', 'updated_at']);
  exact(v.identity, ['type', 'id']); id(v.identity.id);
  if (v.identity.type !== 'learn_thread' || v.kind !== 'learning' || v.retention !== 'saved' || !['active', 'archived'].includes(v.lifecycle)) reject('storage_invalid_command');
  integer(v.revision, 1); text(v.title, 1, 120); nullableId(v.project_id); date(v.created_at); date(v.updated_at);
}
function draftShape(v: ConversationDraft) {
  exact(v, ['text', 'content_refs', 'revision', 'conversation_revision']); text(v.text, 0, 16000);
  references(v.content_refs); integer(v.revision); integer(v.conversation_revision, 1);
}
function statusShape(v: RunStatus, full: boolean) {
  const keys = ['run_id', 'state']; if (full && v.conversation !== undefined) keys.push('conversation'); if (full && v.error !== undefined) keys.push('error');
  exact(v, keys); id(v.run_id); if (!states.includes(v.state)) reject('storage_invalid_command');
  if (v.conversation !== undefined) summaryShape(v.conversation);
  if (v.error !== undefined) { exact(v.error, ['code', 'message', 'retryable']); text(v.error.code, 1, 256); text(v.error.message, 0, 16000); if (typeof v.error.retryable !== 'boolean' || !v.conversation) reject('storage_invalid_command'); }
}
export function validateLearningMetadataResult<C extends LearningMetadataCommand['type']>(type: C, result: unknown): asserts result is LearningMetadataResults[C] {
  try {
    switch (type) {
      case 'learning.create': case 'learning.get': summaryShape(result as ConversationSummary); break;
      case 'learning.draft.get': case 'learning.draft.save': draftShape(result as ConversationDraft); break;
      case 'learning.list': case 'learning.runs.list': {
        exact(result, ['items', 'next_cursor']); cursorValue(result.next_cursor);
        if (!Array.isArray(result.items) || result.items.length > 100) reject('storage_invalid_command');
        result.items.forEach(v => type === 'learning.list' ? summaryShape(v) : statusShape(v, false)); break;
      }
      case 'learning.run.status': statusShape(result as RunStatus, true); break;
      default: reject('storage_invalid_command');
    }
  } catch { reject('learning_metadata_invalid_result'); }
}
const deleted = (db: DatabaseSync, type: string, identifier: string) => !!one(db, 'SELECT 1 FROM deletion_ledger WHERE entity_type=? AND entity_id=?', type, identifier);
function commandCurrent(db: DatabaseSync, k: string | null) {
  if (k !== null && (one(db, "SELECT 1 FROM learn_command_tombstones WHERE ledger='conversation_commands' AND idempotency_key=?", k) || deleted(db, 'conversation_command', k))) reject('command_terminal_unavailable');
}
function saved(db: DatabaseSync, threadId: string) {
  const t = one(db, 'SELECT * FROM learn_threads WHERE id=?', threadId);
  if (!t || deleted(db, 'learn_thread', threadId)) reject('conversation_missing');
  db.prepare('INSERT OR IGNORE INTO learn_conversations(thread_id,updated_at) VALUES(?,?)').run(threadId, utcNow());
  const c = one(db, 'SELECT * FROM learn_conversations WHERE thread_id=?', threadId)!;
  if (c.lifecycle === 'deleted') reject('conversation_missing');
  const p = one(db, "SELECT project_id FROM study_project_chats WHERE chat_kind='learning' AND chat_id=?", threadId);
  const summary: ConversationSummary = { identity: { type: 'learn_thread', id: threadId }, kind: 'learning', retention: 'saved',
    lifecycle: String(c.lifecycle), revision: Number(c.revision), title: String(t.title), project_id: p ? String(p.project_id) : null,
    created_at: String(t.created_at), updated_at: [String(t.updated_at), String(c.updated_at)].sort().at(-1)! };
  return { summary, metadata: c };
}
/** Pydantic coerces ImageLocator.bounds to floats. Python JSON hashes 1.0/0.0 and
 * scientific exponents differently from JSON.stringify. No raw content is normalised. */
function pythonFloat(n: number) {
  if (Object.is(n, -0)) return '-0.0';
  if (n !== 0 && Math.abs(n) < 1e-4) return n.toExponential().replace(/e([+-])(\d+)$/, (_, sign, exponent) => 'e' + sign + exponent.padStart(2, '0'));
  return Number.isInteger(n) ? n + '.0' : String(n);
}
function pythonCanonical(v: unknown, floats = false): string {
  if (Array.isArray(v)) return '[' + v.map(n => pythonCanonical(n, floats)).join(',') + ']';
  if (v !== null && typeof v === 'object') return '{' + Object.keys(v).sort().map(k => JSON.stringify(k) + ':' + pythonCanonical((v as Record<string, unknown>)[k], k === 'bounds')).join(',') + '}';
  return floats && typeof v === 'number' ? pythonFloat(v) : JSON.stringify(v);
}
function mutation<T>(db: DatabaseSync, k: string | null, operation: string, target: string, request: unknown, action: () => T): T {
  commandCurrent(db, k); requireAssistance(db);
  if (k === null) return action();
  const hash = digest(pythonCanonical({ operation, target_type: 'learn_thread', target_id: target, request }));
  const previous = one(db, 'SELECT request_hash,result_json FROM conversation_commands WHERE idempotency_key=?', k);
  if (previous) {
    if (previous.request_hash !== hash) reject('idempotency_conflict');
    const result = JSON.parse(String(previous.result_json));
    // An additive restore can carry an old create receipt alongside a newer owner
    // frontier. Refuse it even if command retirement has not yet been reconciled.
    if (operation === 'create' && result?.identity?.type === 'learn_thread' &&
      deleted(db, 'learn_thread', String(result.identity.id))) reject('command_terminal_unavailable');
    return result as T;
  }
  const result = action();
  db.prepare('INSERT INTO conversation_commands VALUES(?,?,?,?,?,?,?)').run(k, operation, 'learn_thread', target, hash, JSON.stringify(result), utcNow());
  return result;
}
function draft(db: DatabaseSync, threadId: string): ConversationDraft {
  const { summary, metadata } = saved(db, threadId);
  return { text: String(metadata.draft_text), content_refs: JSON.parse(String(metadata.draft_refs_json)),
    revision: Number(metadata.draft_revision), conversation_revision: summary.revision };
}
/** References remain immutable version pins, including historical retained revisions.
 * Display permission is sufficient to retain a reference; generation must separately
 * resolve model_input/currentness. No source body, extraction or original is read here. */
function validateRefs(db: DatabaseSync, threadId: string, refs: ContentReference[]) {
  for (const ref of refs) {
    const t = ref.target;
    if (deleted(db, t.type, t.id)) reject('content_unavailable');
    if (t.type === 'library_revision' || t.type === 'note_revision') {
      const r = one(db, 'SELECT r.status,r.rights_json,d.id AS document_id,d.deleted_at,d.scope_kind,d.reserved FROM knowledge_revisions r JOIN knowledge_documents d ON d.id=r.document_id WHERE r.id=?', t.id);
      if (!r || r.deleted_at || r.status === 'deleted' || ['temporary-case', 'unclassified'].includes(String(r.scope_kind)) || r.reserved ||
        ['knowledge-revision', 'revision'].some(kind => deleted(db, kind, t.id)) ||
        ['knowledge-document', 'document', 'library_document'].some(kind => deleted(db, kind, String(r.document_id))) || JSON.parse(String(r.rights_json)).display !== true) reject('content_unavailable');
    } else if (t.type === 'saved_test_version') {
      const r = one(db, 'SELECT v.test_id,t.lifecycle FROM assessment_test_versions v JOIN assessment_tests t ON t.id=v.test_id WHERE v.id=?', t.id);
      if (!r || r.lifecycle === 'deleted' || deleted(db, 'saved_test', String(r.test_id))) reject('content_unavailable');
    } else {
      // Only already saved attachments owned by this Learning conversation; Case/media admission is BF04/05.
      const a = one(db, 'SELECT a.chat_kind,a.chat_id,m.rights_json FROM knowledge_attachments a JOIN knowledge_attachment_metadata m ON m.attachment_id=a.id WHERE a.id=?', t.id);
      if (!a || a.chat_kind !== 'learning' || a.chat_id !== threadId || JSON.parse(String(a.rights_json)).display !== true) reject('content_unavailable');
    }
  }
}
function encodeCursor(value: unknown): string {
  const raw = Buffer.from(JSON.stringify(value)); return Buffer.concat([raw, createHmac('sha256', cursorKey).update(raw).digest()]).toString('base64url');
}
function decodeCursor(token: string | null, scope: unknown): Record<string, unknown> | null {
  if (token === null) return null;
  try {
    if (!/^[A-Za-z0-9_-]+={0,2}$/.test(token)) throw 0;
    const bytes = Buffer.from(token, 'base64url'), raw = bytes.subarray(0, -32), signature = bytes.subarray(-32);
    if (signature.length !== 32 || !timingSafeEqual(signature, createHmac('sha256', cursorKey).update(raw).digest())) throw 0;
    const result = JSON.parse(raw.toString()); if (canonical(result.scope) !== canonical(scope)) throw 0; return result;
  } catch { reject('invalid_cursor'); }
}
function receipts(db: DatabaseSync, threadId: string, limit: number, after: unknown = null, runId: string | null = null) {
  const args: (string | number)[] = [threadId];
  let where = '';
  if (after !== null) {
    if (!Array.isArray(after) || after.length !== 2 || after.some(v => typeof v !== 'string')) reject('invalid_cursor');
    where += ' AND (c.created_at,c.idempotency_key)<(?,?)'; args.push(...after);
  }
  if (runId !== null) { where += " AND json_extract(c.result_json,'$.run_id')=?"; args.push(runId); }
  args.push(limit);
  return rows(db, "SELECT c.idempotency_key,c.created_at,c.result_json FROM conversation_commands c WHERE c.operation='send' AND c.target_type='learn_thread' AND c.target_id=? " +
    "AND NOT EXISTS(SELECT 1 FROM learn_command_tombstones t WHERE t.ledger='conversation_commands' AND t.idempotency_key=c.idempotency_key) " +
    "AND NOT EXISTS(SELECT 1 FROM deletion_ledger d WHERE (d.entity_type='conversation_command' AND d.entity_id=c.idempotency_key) OR (d.entity_type='learn_thread' AND d.entity_id=c.target_id) OR (d.entity_type IN ('learn_run','run') AND d.entity_id=json_extract(c.result_json,'$.run_id')))" +
    where + ' ORDER BY c.created_at DESC,c.idempotency_key DESC LIMIT ?', ...args);
}
export function executeLearningMetadata<C extends LearningMetadataCommand>(db: DatabaseSync, command: C): LearningMetadataResults[C['type']] {
  validateLearningMetadataCommand(command);
  if (!db.isTransaction) reject('learning_transaction_required');
  const result = execute(db, command); validateLearningMetadataResult(command.type, result);
  return result as LearningMetadataResults[C['type']];
}
function execute(db: DatabaseSync, command: LearningMetadataCommand): unknown {
  switch (command.type) {
    case 'learning.create': {
      requireAssistance(db); commandCurrent(db, command.idempotencyKey);
      return mutation(db, command.idempotencyKey, 'create', 'new', command.request, () => {
        const r = command.request, threadId = 'thread_' + randomUUID().replaceAll('-', ''), now = utcNow();
        db.prepare('INSERT INTO learn_threads VALUES(?,?,?,?,?,?)').run(threadId, r.title, r.topic_id, r.teaching_style, now, now);
        saved(db, threadId);
        if (r.project_id !== null) {
          const p = one(db, 'SELECT lifecycle FROM study_projects WHERE id=?', r.project_id);
          if (!p || p.lifecycle === 'deleted' || deleted(db, 'project', r.project_id)) reject('project_missing');
          if (p.lifecycle !== 'active') reject('project_archived');
          const position = Number(one(db, 'SELECT COALESCE(MAX(position)+1,0) AS n FROM study_project_chats WHERE project_id=?', r.project_id)!.n);
          db.prepare("INSERT INTO study_project_chats VALUES(?,?,'learning',?,?,1,?)").run('project_chat_' + randomUUID().replaceAll('-', ''), r.project_id, threadId, position, now);
          db.prepare('UPDATE study_projects SET revision=revision+1,updated_at=? WHERE id=?').run(now, r.project_id);
          db.prepare("INSERT INTO preferences VALUES('design_c.context_epoch','1',?) ON CONFLICT(key) DO UPDATE SET value=CAST(CAST(preferences.value AS INTEGER)+1 AS TEXT),updated_at=excluded.updated_at").run(now);
        }
        return saved(db, threadId).summary;
      });
    }
    case 'learning.get': requireAssistance(db); return saved(db, command.threadId).summary;
    case 'learning.draft.get': requireAssistance(db); return draft(db, command.threadId);
    case 'learning.draft.save': {
      commandCurrent(db, command.idempotencyKey); requireAssistance(db);
      const s = saved(db, command.threadId);
      return mutation(db, command.idempotencyKey, 'draft', command.threadId, command.request, () => {
        if (s.summary.revision !== command.request.expected_revision) reject('conversation_revision_conflict');
        validateRefs(db, command.threadId, command.request.content_refs);
        db.prepare('UPDATE learn_conversations SET draft_text=?,draft_refs_json=?,draft_revision=draft_revision+1,revision=revision+1,updated_at=? WHERE thread_id=?')
          .run(command.request.text, JSON.stringify(command.request.content_refs), utcNow(), command.threadId);
        return draft(db, command.threadId);
      });
    }
    case 'learning.list': {
      requireAssistance(db);
      const scope = ['conversations', 'learning', command.lifecycle, command.projectId], page = decodeCursor(command.cursor, scope);
      if (page) exact(page, ['scope', 'boundary', 'after']);
      const boundary = page ? page.boundary : utcNow(); date(boundary);
      const args: (string | number)[] = [command.lifecycle, boundary as string];
      let where = '';
      if (command.projectId !== null) { where += ' AND p.project_id=?'; args.push(command.projectId); }
      if (page) {
        const after = page.after;
        if (!Array.isArray(after) || after.length !== 2 || after.some(v => typeof v !== 'string')) reject('invalid_cursor');
        where += ' AND (max(t.updated_at,c.updated_at),t.id)<(?,?)'; args.push(...after);
      }
      args.push(command.limit + 1);
      const candidates = rows(db, 'SELECT t.id FROM learn_threads t JOIN learn_conversations c ON c.thread_id=t.id LEFT JOIN study_project_chats p ' +
        "ON p.chat_kind='learning' AND p.chat_id=t.id WHERE c.lifecycle=? AND max(t.updated_at,c.updated_at)<=? " +
        "AND NOT EXISTS(SELECT 1 FROM deletion_ledger d WHERE d.entity_type='learn_thread' AND d.entity_id=t.id)" + where +
        ' ORDER BY max(t.updated_at,c.updated_at) DESC,t.id DESC LIMIT ?', ...args);
      const items = candidates.slice(0, command.limit).map(row => saved(db, String(row.id)).summary), last = items.at(-1);
      return { items, next_cursor: candidates.length > command.limit ? encodeCursor({ scope, boundary, after: [last!.updated_at, last!.identity.id] }) : null };
    }
    case 'learning.runs.list': {
      // Python exposes neutral states during Test; never titles, errors or transcript here.
      const scope = ['runs', 'learning', command.threadId], page = decodeCursor(command.cursor, scope);
      if (page) exact(page, ['scope', 'after']);
      const candidates = receipts(db, command.threadId, command.limit + 1, page?.after ?? null), selected = candidates.slice(0, command.limit);
      return { items: selected.map(row => { const r = JSON.parse(String(row.result_json)); return { run_id: r.run_id, state: r.state }; }),
        next_cursor: candidates.length > command.limit ? encodeCursor({ scope, after: [selected.at(-1)!.created_at, selected.at(-1)!.idempotency_key] }) : null };
    }
    case 'learning.run.status': {
      const row = receipts(db, command.threadId, 1, null, command.runId)[0]; if (!row) reject('conversation_run_missing');
      const receipt = JSON.parse(String(row.result_json));
      const result: RunStatus = { run_id: receipt.run_id, state: receipt.state };
      const restricted = one(db, "SELECT 1 FROM assessment_test_attempts WHERE mode='test' AND status='active' LIMIT 1");
      if (!command.neutral && !restricted) {
        result.conversation = saved(db, command.threadId).summary;
        if (receipt.error) result.error = receipt.error;
      }
      return result;
    }
  }
}
