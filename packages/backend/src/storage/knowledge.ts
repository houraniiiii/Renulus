// SPDX-License-Identifier: MIT
// Local canonical functions only. The single storage worker owns the transaction.
import type { DatabaseSync } from 'node:sqlite';
import { randomUUID } from 'node:crypto';
import { exact, integer, reject, text } from './contracts.ts';
import { requireAssistance } from './conversation.ts';
import { canonical, digest, one, rows } from './schema.ts';
import type { RecordRow } from './contracts.ts';
import type { ContentReference, ImportIntent, ImportRequest, KnowledgeCommand, KnowledgeResults, Locator, Metadata, NoteSummary, Rights, SourcePin } from '../domain/knowledge/contracts.ts';
import { effectiveKnowledgeMetadata } from '../domain/knowledge/source-status.ts';
export { effectiveKnowledgeMetadata, projectKnowledgeSourceStatus } from '../domain/knowledge/source-status.ts';

const now = () => new Date().toISOString();
export const knowledgeId = (prefix: string) => prefix + '_' + randomUUID().replaceAll('-', '');
const parse = <T>(value: unknown): T => JSON.parse(String(value));
const sha = (value: unknown) => digest(canonical(value));
const identifier = (value: unknown) => { text(value, 1, 256); if (!/^[A-Za-z0-9][A-Za-z0-9_.:-]*$/.test(value)) reject('storage_invalid_command'); };
const hash = (value: unknown) => { if (typeof value !== 'string' || !/^[a-f0-9]{64}$/.test(value)) reject('storage_invalid_command'); };
const nullableId = (value: unknown) => { if (value !== null) identifier(value); };
export function deleted(db: DatabaseSync, id: string, ...types: string[]): boolean {
  return !!one(db, 'SELECT 1 FROM deletion_ledger WHERE entity_id=? AND entity_type IN (' + types.map(() => '?').join(',') + ')', id, ...types);
}
export function markDeleted(db: DatabaseSync, type: string, id: string) {
  db.prepare('INSERT OR IGNORE INTO deletion_ledger(entity_type,entity_id,deleted_at) VALUES(?,?,?)').run(type, id, now());
}
export function bumpKnowledgeContext(db: DatabaseSync) {
  db.prepare("INSERT INTO preferences VALUES('design_c.context_epoch','1',?) ON CONFLICT(key) DO UPDATE SET value=CAST(CAST(preferences.value AS INTEGER)+1 AS TEXT),updated_at=excluded.updated_at").run(now());
}
const pref = (db: DatabaseSync, key: string) => one(db, 'SELECT value FROM preferences WHERE key=?', key)?.value;
function put(db: DatabaseSync, key: string, value: unknown) {
  db.prepare('INSERT INTO preferences VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at').run(key, JSON.stringify(value), now());
}
export function knowledgeStamp(db: DatabaseSync) {
  requireAssistance(db);
  return sha({ policy: pref(db, 'design_c.assessment_policy_revision') ?? '1', context: pref(db, 'design_c.context_epoch') ?? '0',
    grant: one(db, 'SELECT epoch FROM harness_configuration_grants WHERE id=1')?.epoch ?? 0,
    configuration: one(db, 'SELECT effective,admission_open FROM harness_configuration_pointer WHERE id=1') ?? null,
    deletion: one(db, 'SELECT COUNT(*) AS n,MAX(deleted_at) AS latest FROM deletion_ledger')!,
    sourceStatus: one(db, 'SELECT COUNT(*) AS n,MAX(created_at) AS latest FROM knowledge_source_status_events')! });
}
export function eligibleKnowledge(metadata: Metadata, rights: Rights, currentOnly = false) {
  if (!['display', 'cache', 'derivation', 'model_input', 'index', 'embedding'].every(key => rights[key as keyof Rights] === true)) return false;
  if (metadata.retracted || metadata.superseded || metadata.repository_removed || metadata.access_changed || metadata.correction && !metadata.content_reviewed || (metadata.replaced_topics as unknown[] | undefined)?.length ||
    ['draft', 'preprint'].includes(String(metadata.publication_status))) return false;
  return !currentOnly || metadata.publication_status === 'final' && metadata.latest_final_verified === true && metadata.content_reviewed === true &&
    !metadata.repository_removed && (!metadata.review_due || String(metadata.review_due).slice(0, 10) >= now().slice(0, 10));
}
export function validateLocator(value: unknown): asserts value is Locator {
  if (!value || typeof value !== 'object') reject('reader_locator_invalid');
  const v = value as Locator;
  const allowed = (keys: string[], optional: string[]) => {
    for (const key of Object.keys(v)) if (![...keys, ...optional].includes(key)) reject('reader_locator_invalid');
    for (const key of keys) if (!(key in v)) reject('reader_locator_invalid');
  };
  switch (v.kind) {
    case 'pdf': allowed(['kind', 'physical_page'], ['printed_label']); integer(v.physical_page, 1, 300); if (v.printed_label != null) text(v.printed_label, 0, 80); break;
    case 'text': allowed(['kind', 'item_ref', 'start', 'end'], ['section']); text(v.item_ref, 1, 256); integer(v.start); integer(v.end, v.start + 1); if (v.section != null) text(v.section, 0, 240); break;
    case 'table':
      allowed(['kind', 'format', 'first_row', 'last_row', 'first_column', 'last_column'], ['sheet_name']);
      if (!['csv', 'xlsx'].includes(v.format) || (v.format === 'xlsx') !== (v.sheet_name != null)) reject('reader_locator_invalid');
      if (v.sheet_name != null) text(v.sheet_name, 1, 120);
      integer(v.first_row, 1, 100000); integer(v.last_row, v.first_row, 100000);
      integer(v.first_column, 1, 200); integer(v.last_column, v.first_column, 200); break;
    case 'image':
      allowed(['kind'], ['frame', 'bounds']); if (v.frame !== undefined) integer(v.frame, 1, 300);
      if (v.bounds != null && (!Array.isArray(v.bounds) || v.bounds.length !== 4 || !v.bounds.every(n => typeof n === 'number' && Number.isFinite(n)) ||
        !(0 <= v.bounds[0] && v.bounds[0] < v.bounds[2] && v.bounds[2] <= 1 && 0 <= v.bounds[1] && v.bounds[1] < v.bounds[3] && v.bounds[3] <= 1))) reject('reader_locator_invalid'); break;
    default: reject('reader_locator_invalid');
  }
}
export function validateReaderRequest(value: unknown) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) reject('reader_request_invalid');
  const r = value as import('../domain/knowledge/contracts.ts').ReaderRequest;
  for (const k of Object.keys(r)) if (!['reference', 'conversation', 'page', 'sheet', 'first_row', 'row_limit', 'expected_policy_revision', 'expected_context_epoch'].includes(k)) reject('reader_request_invalid');
  const ref = r.reference; if (!ref || typeof ref !== 'object') reject('reader_request_invalid');
  for (const k of Object.keys(ref)) if (!['target', 'locator'].includes(k)) reject('reader_request_invalid');
  exact(ref.target, ['type', 'id']); identifier(ref.target.id);
  if (!['library_revision', 'note_revision', 'attachment'].includes(ref.target.type)) reject('reader_target_unsupported');
  if (ref.locator != null) validateLocator(ref.locator);
  if (r.conversation != null) { exact(r.conversation, ['type', 'id']); identifier(r.conversation.id); if (!['case', 'learn_thread'].includes(r.conversation.type)) reject('reader_context_mismatch'); }
  if (r.page !== undefined) integer(r.page, 1, 300); if (r.sheet != null) text(r.sheet, 1, 120);
  if (r.first_row !== undefined) integer(r.first_row, 1, 100000); if (r.row_limit !== undefined) integer(r.row_limit, 1, 200);
  if (r.expected_policy_revision != null) integer(r.expected_policy_revision); if (r.expected_context_epoch != null) integer(r.expected_context_epoch);
}
export function validateImportRequest(r: ImportRequest) {
  exact(r, ['title', 'media_type', 'bytes', 'sha256', 'metadata', 'rights', 'document_id', 'expected_revision_id', 'project_id', 'note', 'idempotency_key']);
  text(r.title, 1, 500); text(r.media_type, 1, 160); integer(r.bytes, 1, 64 * 1024 * 1024); hash(r.sha256);
  nullableId(r.document_id); nullableId(r.expected_revision_id); nullableId(r.project_id); text(r.idempotency_key, 1, 200);
  if (typeof r.note !== 'boolean' || !!r.document_id !== !!r.expected_revision_id) reject('storage_invalid_command');
  exact(r.rights, ['display', 'cache', 'index', 'embedding', 'model_input', 'derivation', 'evaluation', 'redistribution', 'licence', 'permission_reference', 'attribution']);
  for (const k of ['display', 'cache', 'index', 'embedding', 'model_input', 'derivation', 'evaluation', 'redistribution']) if (typeof r.rights[k as keyof Rights] !== 'boolean') reject('storage_invalid_command');
  for (const k of ['licence', 'permission_reference', 'attribution']) text(r.rights[k as keyof Rights], 0, 4000);
  if (!r.metadata || typeof r.metadata !== 'object' || Array.isArray(r.metadata) || Buffer.byteLength(JSON.stringify(r.metadata)) > 65536) reject('source_metadata_invalid');
  text(r.metadata.source_id, 1, 128);
  for (const k of ['retracted', 'superseded', 'repository_removed', 'access_changed', 'latest_final_verified', 'content_reviewed'])
    if (r.metadata[k] !== undefined && typeof r.metadata[k] !== 'boolean') reject('source_metadata_invalid');
  for (const k of ['asset_role', 'topic_ids', 'replaced_topics', 'notes']) if (r.metadata[k] !== undefined &&
    (!Array.isArray(r.metadata[k]) || (r.metadata[k] as unknown[]).length > 1000 || !(r.metadata[k] as unknown[]).every(v => typeof v === 'string' && v.length <= 4000))) reject('source_metadata_invalid');
  if (r.metadata.excluded_pages !== undefined && (!Array.isArray(r.metadata.excluded_pages) || r.metadata.excluded_pages.length > 300 || !r.metadata.excluded_pages.every(n => Number.isSafeInteger(n) && n >= 1 && n <= 300))) reject('source_metadata_invalid');
  if (r.metadata.original_sha256 != null && r.metadata.original_sha256 !== r.sha256) reject('original_digest_mismatch');
  if (!r.rights.cache || !r.rights.display) reject('import_rights_denied');
  if (r.note && (r.media_type !== 'text/plain' || r.bytes > 4 * 1024 * 1024 || r.rights.licence !== 'user-owned' || r.metadata.access_class !== 'user-owned' || !r.metadata.asset_role?.includes('study-note'))) reject('note_edit_denied');
}
export function isKnowledgeCommand(value: unknown): value is KnowledgeCommand { return !!value && typeof value === 'object' && String((value as KnowledgeCommand).type).startsWith('knowledge.'); }
export function validateKnowledgeCommand(value: unknown): asserts value is KnowledgeCommand {
  const c = value as KnowledgeCommand;
  switch (c.type) {
    case 'knowledge.list': exact(c, ['type', 'limit', 'offset', 'query', 'status']); integer(c.limit, 1, 100); integer(c.offset); text(c.query, 0, 200); if (c.status !== null && !['ready', 'queued', 'processing', 'failed', 'cancelled', 'empty'].includes(c.status)) reject('storage_invalid_command'); break;
    case 'knowledge.get': exact(c, ['type', 'documentId']); identifier(c.documentId); break;
    case 'knowledge.import.begin': exact(c, ['type', 'request']); validateImportRequest(c.request); break;
    case 'knowledge.import.check': exact(c, ['type', 'intentId']); identifier(c.intentId); break;
    case 'knowledge.import.original': exact(c, ['type', 'intentId', 'originalHandle']); identifier(c.intentId); text(c.originalHandle, 1, 4096); break;
    case 'knowledge.import.ready':
      exact(c, ['type', 'intentId', 'extraction', 'passages', 'embeddingModel', 'chunkTokens']); identifier(c.intentId); text(c.embeddingModel, 1, 200); integer(c.chunkTokens, 1, 480);
      if (!Array.isArray(c.passages) || c.passages.length > 12000 || Buffer.byteLength(JSON.stringify(c.extraction)) > 32 * 1024 * 1024) reject('document_limit');
      for (const p of c.passages) { exact(p, ['id', 'text', 'context_text', 'locators', 'headings']); identifier(p.id); text(p.text, 1, 200000); text(p.context_text, 1, 200000);
        if (!Array.isArray(p.locators) || !Array.isArray(p.headings) || p.locators.length > 12000 || p.headings.length > 200 || Buffer.byteLength(JSON.stringify(p.locators)) > 1024 * 1024) reject('document_limit'); p.headings.forEach(h => text(h, 0, 4000)); }
      if (new Set(c.passages.map(p => p.id)).size !== c.passages.length) reject('document_invalid'); break;
    case 'knowledge.import.fail': exact(c, ['type', 'intentId', 'code']); identifier(c.intentId); identifier(c.code); break;
    case 'knowledge.source.pin': exact(c, ['type', 'request', 'operation']); validateReaderRequest(c.request); if (!['display', 'model_input'].includes(c.operation)) reject('storage_invalid_command'); break;
    case 'knowledge.source.dependency':
    case 'knowledge.source.recheck': exact(c, c.type === 'knowledge.source.dependency' ? ['type', 'pin'] : ['type', 'pin', 'operation']);
      exact(c.pin, ['reference', 'document_id', 'revision_id', 'title', 'filename', 'media_type', 'sha256', 'bytes', 'original_handle', 'rights', 'metadata', 'stamp', 'fingerprint', 'policy_revision', 'context_epoch', 'attachment_revision']);
      validateReaderRequest({ reference: c.pin.reference }); hash(c.pin.fingerprint); hash(c.pin.stamp); if (c.type === 'knowledge.source.recheck' && !['display', 'model_input'].includes(c.operation)) reject('storage_invalid_command'); break;
    case 'knowledge.notes.list': exact(c, ['type', 'projectId', 'limit', 'offset']); nullableId(c.projectId); integer(c.limit, 1, 100); integer(c.offset); break;
    case 'knowledge.notes.pin': exact(c, ['type', 'documentId', 'revisionId']); identifier(c.documentId); nullableId(c.revisionId); break;
    case 'knowledge.delete': exact(c, ['type', 'documentId', 'expectedRevisionId', 'idempotencyKey', 'note']); identifier(c.documentId); nullableId(c.expectedRevisionId); text(c.idempotencyKey, 1, 200); if (typeof c.note !== 'boolean' || c.note && c.expectedRevisionId === null) reject('storage_invalid_command'); break;
    case 'knowledge.find': exact(c, ['type', 'query', 'projectId', 'after', 'limit', 'epoch']); text(c.query, 1, 240); nullableId(c.projectId); if (c.after !== null) text(c.after, 1, 256); integer(c.limit, 1, 200); if (c.epoch !== null) hash(c.epoch); break;
    case 'knowledge.cleanup': exact(c, ['type', 'revisionIds']); if (!Array.isArray(c.revisionIds) || c.revisionIds.length > 256) reject('storage_invalid_command'); c.revisionIds.forEach(identifier); break;
    default: reject('storage_invalid_command');
  }
}
function document(db: DatabaseSync, id: string) {
  const d = one(db, 'SELECT * FROM knowledge_documents WHERE id=? AND deleted_at IS NULL', id);
  if (!d || deleted(db, id, 'document', 'knowledge-document')) reject('document_missing'); return d;
}
export function currentKnowledgeRevision(db: DatabaseSync, id: string) {
  const r = one(db, 'SELECT * FROM knowledge_revisions WHERE id=?', id); if (!r || r.status === 'deleted' || deleted(db, id, 'revision', 'knowledge-revision')) reject('reader_content_missing');
  const d = document(db, String(r.document_id)); return { d, r };
}
function summary(db: DatabaseSync, id: string) {
  const d = document(db, id); const revisions = rows(db, 'SELECT id,document_id,ordinal,status,sha256,media_type,bytes,metadata_json,rights_json,embedding_model,chunk_tokens,created_at,activated_at FROM knowledge_revisions WHERE document_id=? ORDER BY ordinal DESC', id).map(r => {
    const { metadata_json, rights_json, ...rest } = r; return { ...rest, status: String(r.status), metadata: parse(metadata_json), rights: parse(rights_json), passage_count: Number(one(db, 'SELECT COUNT(*) AS n FROM knowledge_passages WHERE revision_id=?', String(r.id))!.n) };
  });
  return { ...d, scope: { kind: d.scope_kind, entity_id: d.scope_entity }, reserved: !!d.reserved, revisions,
    status: revisions[0]?.status ?? 'empty', cleanup_pending: !!one(db, 'SELECT 1 FROM knowledge_cleanup c JOIN knowledge_revisions r ON r.id=c.revision_id WHERE r.document_id=?', id) };
}
function pinSource(db: DatabaseSync, reference: ContentReference, operation: 'display' | 'model_input', conversation?: { type: string; id: string } | null): SourcePin {
  const stamp = knowledgeStamp(db); let r: RecordRow, d: RecordRow | undefined, filename: string, handle: string, attachmentRevision: number | null = null;
  if (reference.target.type === 'attachment') {
    const a = one(db, 'SELECT a.*,m.filename,m.metadata_json,m.rights_json FROM knowledge_attachments a JOIN knowledge_attachment_metadata m ON m.attachment_id=a.id WHERE a.id=?', reference.target.id);
    if (!a || deleted(db, String(a.id), 'attachment', 'case_attachment')) reject('reader_content_missing');
    const kind = a.chat_kind === 'case' ? 'case' : 'learn_thread';
    if (conversation && (conversation.type !== kind || conversation.id !== a.chat_id)) reject('reader_context_mismatch');
    const parent = kind === 'case' ? one(db, 'SELECT id FROM case_sessions WHERE id=?', String(a.chat_id)) : one(db, 'SELECT id FROM learn_threads WHERE id=?', String(a.chat_id));
    if (!parent || deleted(db, String(a.chat_id), kind)) reject('reader_content_missing');
    const originals = rows(db, "SELECT * FROM knowledge_attachment_originals WHERE attachment_id=? AND role='original'", String(a.id));
    if (originals.length !== 1 || deleted(db, String(originals[0].id), 'attachment_original')) reject('original_missing');
    r = { ...originals[0], metadata_json: a.metadata_json, rights_json: a.rights_json, media_type: a.media_type, title: a.title };
    filename = String(a.filename); handle = String(r.original_path ?? ''); attachmentRevision = Number(a.revision);
  } else {
    ({ d, r } = currentKnowledgeRevision(db, reference.target.id));
    if (d.scope_kind !== 'personal-library' || d.scope_entity !== null || d.reserved) reject('reader_scope_denied');
    if (reference.target.type === 'note_revision' && !parse<Metadata>(r.metadata_json).asset_role?.includes('study-note')) reject('note_missing');
    filename = String(d.title); handle = String(r.original_path ?? '');
    r = { ...r, title: d.title };
  }
  const rights = parse<Rights>(r.rights_json), metadata = effectiveKnowledgeMetadata(db, parse<Metadata>(r.metadata_json));
  if (!rights.display || !handle || !(Number(r.bytes) > 0 && Number(r.bytes) <= 64 * 1024 * 1024)) reject('reader_original_unavailable');
  if (operation === 'model_input' && (!eligibleKnowledge(metadata, rights) || d && (d.active_revision !== r.id || r.status !== 'ready'))) reject('reader_passage_denied');
  if (operation === 'model_input' && reference.locator?.kind === 'pdf' && metadata.excluded_pages?.includes(reference.locator.physical_page)) reject('reader_passage_denied');
  const base = { reference, document_id: d ? String(d.id) : null, revision_id: String(r.id), title: String(r.title), filename,
    media_type: String(r.media_type), sha256: String(r.sha256), bytes: Number(r.bytes), original_handle: handle, rights, metadata,
    stamp, policy_revision: Number(pref(db, 'design_c.assessment_policy_revision') ?? 1), context_epoch: Number(pref(db, 'design_c.context_epoch') ?? 0), attachment_revision: attachmentRevision };
  return { ...base, fingerprint: sha(base) };
}
function notePin(db: DatabaseSync, documentId: string, revisionId: string | null) {
  const d = document(db, documentId), id = revisionId ?? String(d.latest_revision), { r } = currentKnowledgeRevision(db, id);
  if (r.document_id !== documentId || !parse<Metadata>(r.metadata_json).asset_role?.includes('study-note')) reject('note_missing');
  const reference: ContentReference = { target: { type: 'note_revision', id } }, pin = pinSource(db, reference, 'display');
  const metadata = parse<Metadata>(r.metadata_json), title = [...(metadata.notes as string[] ?? [])].reverse().find(v => v.startsWith('renulus:note-title:'))?.slice(19) ?? String(d.title);
  const summary: NoteSummary = { document_id: documentId, revision_id: id, ordinal: Number(r.ordinal), title, updated_at: String(r.created_at), reference };
  return { summary, pin };
}
function intent(db: DatabaseSync, id: string): ImportIntent { const stored = pref(db, 'knowledge.target.intent:' + id); if (!stored) reject('import_intent_missing'); return parse(stored); }
function saveIntent(db: DatabaseSync, i: ImportIntent) { put(db, 'knowledge.target.intent:' + i.id, i); return i; }
function checkIntent(db: DatabaseSync, i: ImportIntent) {
  if (i.state === 'ready') { document(db, i.document_id); return; }
  if (i.state === 'failed' || i.stamp !== knowledgeStamp(db)) reject('import_stale');
  if (deleted(db, i.document_id, 'document', 'knowledge-document') || deleted(db, i.revision_id, 'revision', 'knowledge-revision')) reject('document_deleted');
  if (i.request.document_id) {
    const d = document(db, i.document_id);
    if (d.latest_revision !== (i.state === 'prepared' ? i.request.expected_revision_id : i.revision_id)) reject('note_revision_conflict');
    if (i.request.note) { const previous = notePin(db, i.document_id, i.state === 'prepared' ? i.request.expected_revision_id : i.revision_id);
      if (previous.pin.rights.licence !== 'user-owned' || previous.pin.metadata.access_class !== 'user-owned') reject('note_edit_denied'); }
  }
}
function linkNote(db: DatabaseSync, i: ImportIntent) {
  const associations = rows(db, 'SELECT m.* FROM study_project_documents m JOIN knowledge_revisions r ON r.id=m.revision_id WHERE r.document_id=? ORDER BY m.position,m.id', i.document_id);
  const owners = new Set(associations.map(a => String(a.project_id))); if (i.request.project_id) owners.add(i.request.project_id);
  for (const project of owners) {
    if (!one(db, "SELECT 1 FROM study_projects WHERE id=? AND lifecycle!='deleted'", project) || deleted(db, project, 'project')) reject('project_missing');
    if (project === i.request.project_id && one(db, 'SELECT lifecycle FROM study_projects WHERE id=?', project)?.lifecycle !== 'active') reject('project_archived');
    const old = associations.filter(a => a.project_id === project), position = old.length ? Number(old[0].position) : Number(one(db, 'SELECT COALESCE(MAX(position)+1,0) AS n FROM study_project_documents WHERE project_id=?', project)!.n);
    for (const row of old) { markDeleted(db, 'project_document', String(row.id)); db.prepare('DELETE FROM study_project_documents WHERE id=?').run(row.id); }
    db.prepare('INSERT INTO study_project_documents VALUES(?,?,?,?,1,?)').run(knowledgeId('project_document'), project, i.revision_id, position, now());
    db.prepare('UPDATE study_projects SET revision=revision+1,updated_at=? WHERE id=?').run(now(), project);
  }
}
export function executeKnowledge<C extends KnowledgeCommand>(db: DatabaseSync, c: C): KnowledgeResults[C['type']] {
  validateKnowledgeCommand(c); if (!['knowledge.import.fail', 'knowledge.cleanup'].includes(c.type)) requireAssistance(db); let result: unknown;
  switch (c.type) {
    case 'knowledge.list': {
      const where = "d.deleted_at IS NULL AND NOT EXISTS(SELECT 1 FROM deletion_ledger l WHERE l.entity_id=d.id AND l.entity_type IN ('document','knowledge-document')) AND (?='' OR instr(lower(d.title || ' ' || d.source_id),lower(?))>0) AND (?='' OR r.status=?)";
      const args = [c.query.trim(), c.query.trim(), c.status ?? '', c.status ?? ''];
      const source = ' FROM knowledge_documents d LEFT JOIN knowledge_revisions r ON r.id=d.latest_revision WHERE ' + where;
      result = { documents: rows(db, 'SELECT d.id' + source + ' ORDER BY d.updated_at DESC,d.id LIMIT ? OFFSET ?', ...args, c.limit, c.offset).map(d => summary(db, String(d.id))),
        total: Number(one(db, 'SELECT COUNT(*) AS n' + source, ...args)!.n), limit: c.limit, offset: c.offset }; break;
    }
    case 'knowledge.get': result = summary(db, c.documentId); break;
    case 'knowledge.import.begin': {
      const requestHash = sha(c.request), id = digest(c.request.idempotency_key), old = pref(db, 'knowledge.target.intent:' + id);
      if (old) { const i = parse<ImportIntent>(old); if (sha(i.request) !== requestHash) reject('idempotency_conflict'); checkIntent(db, i); result = i; break; }
      if (Number(one(db, "SELECT COUNT(*) AS n FROM preferences WHERE key LIKE 'knowledge.target.intent:%' AND json_extract(value,'$.state') IN ('prepared','original')")!.n) >= 8) reject('import_capacity');
      const occupied = Number(one(db, "SELECT COALESCE(SUM(bytes),0) AS n FROM knowledge_revisions")!.n);
      const reserved = Number(one(db, "SELECT COALESCE(SUM(json_extract(value,'$.request.bytes')*4),0) AS n FROM preferences WHERE key LIKE 'knowledge.target.intent:%' AND json_extract(value,'$.state') IN ('prepared','original')")!.n);
      if (occupied + reserved + c.request.bytes * 4 > 70_000_000_000) reject('waiting_space');
      if (c.request.document_id) { const d = document(db, c.request.document_id); if (d.latest_revision !== c.request.expected_revision_id || d.source_id !== c.request.metadata.source_id || d.scope_kind !== 'personal-library' || d.reserved) reject('note_revision_conflict'); }
      if (c.request.project_id && (!one(db, "SELECT 1 FROM study_projects WHERE id=? AND lifecycle='active'", c.request.project_id) || deleted(db, c.request.project_id, 'project'))) reject('project_missing');
      const i: ImportIntent = { id, request: c.request, document_id: c.request.document_id ?? knowledgeId('doc'), revision_id: knowledgeId('rev'), job_id: knowledgeId('ingest'),
        reservation_id: 'knowledge_' + id, stamp: knowledgeStamp(db), state: 'prepared', original_handle: null };
      checkIntent(db, i); result = saveIntent(db, i); break;
    }
    case 'knowledge.import.check': { const i = intent(db, c.intentId); checkIntent(db, i); result = i; break; }
    case 'knowledge.import.original': {
      const i = intent(db, c.intentId); checkIntent(db, i);
      if (i.state !== 'prepared') { if (i.original_handle !== c.originalHandle) reject('original_publication_conflict'); result = i; break; }
      const r = i.request, time = now(), d = r.document_id ? document(db, r.document_id) : null;
      const ordinal = Number(one(db, 'SELECT COALESCE(MAX(ordinal),0)+1 AS n FROM knowledge_revisions WHERE document_id=?', i.document_id)!.n);
      if (!d) db.prepare("INSERT INTO knowledge_documents(id,title,source_id,scope_kind,scope_entity,reserved,latest_revision,created_at,updated_at) VALUES(?,?,?,'personal-library',NULL,0,?,?,?)").run(i.document_id, r.title, r.metadata.source_id, i.revision_id, time, time);
      else db.prepare('UPDATE knowledge_documents SET title=?,latest_revision=?,updated_at=? WHERE id=?').run(r.title, i.revision_id, time, i.document_id);
      db.prepare("INSERT INTO knowledge_revisions(id,document_id,ordinal,status,sha256,media_type,bytes,original_path,metadata_json,rights_json,created_at) VALUES(?,?,?,'queued',?,?,?,?,?,?,?)").run(i.revision_id, i.document_id, ordinal, r.sha256, r.media_type, r.bytes, c.originalHandle, JSON.stringify(effectiveKnowledgeMetadata(db, r.metadata)), JSON.stringify(r.rights), time);
      db.prepare("INSERT INTO knowledge_jobs(id,revision_id,idempotency_key,request_hash,state,phase,created_at) VALUES(?,?,?,?,'processing','extraction',?)").run(i.job_id, i.revision_id, r.idempotency_key, sha(r), time);
      if (r.note) linkNote(db, i);
      bumpKnowledgeContext(db); i.state = 'original'; i.original_handle = c.originalHandle; i.stamp = knowledgeStamp(db); result = saveIntent(db, i); break;
    }
    case 'knowledge.import.ready': {
      const i = intent(db, c.intentId); checkIntent(db, i); if (i.state === 'ready') { result = i; break; }
      if (i.state !== 'original' || document(db, i.document_id).latest_revision !== i.revision_id) reject('import_stale');
      const { r } = currentKnowledgeRevision(db, i.revision_id);
      const metadata = effectiveKnowledgeMetadata(db, i.request.metadata);
      if (r.sha256 !== i.request.sha256 || r.bytes !== i.request.bytes || sha(parse(r.metadata_json)) !== sha(metadata) || sha(parse(r.rights_json)) !== sha(i.request.rights) || !eligibleKnowledge(metadata, i.request.rights)) reject('import_rights_changed');
      const insert = db.prepare('INSERT INTO knowledge_passages VALUES(?,?,?,?,?,?,?)');
      c.passages.forEach((p, n) => insert.run(p.id, i.revision_id, n, p.text, p.context_text, JSON.stringify(p.locators), JSON.stringify(p.headings)));
      db.prepare("UPDATE knowledge_revisions SET status='ready',extraction_json=?,embedding_model=?,chunk_tokens=?,activated_at=? WHERE id=?").run(JSON.stringify(c.extraction), c.embeddingModel, c.chunkTokens, now(), i.revision_id);
      db.prepare('UPDATE knowledge_documents SET active_revision=?,updated_at=? WHERE id=?').run(i.revision_id, now(), i.document_id);
      db.prepare("UPDATE knowledge_jobs SET state='ready',phase='ready',finished_at=? WHERE id=?").run(now(), i.job_id);
      bumpKnowledgeContext(db); i.state = 'ready'; i.stamp = knowledgeStamp(db); result = saveIntent(db, i); break;
    }
    case 'knowledge.import.fail': {
      const i = intent(db, c.intentId); if (i.state === 'ready') { result = i; break; }
      db.prepare("UPDATE knowledge_jobs SET state='failed',phase='failed',error_code=?,error_message=?,finished_at=? WHERE id=? AND state!='ready'").run(c.code, c.code, now(), i.job_id);
      db.prepare("UPDATE knowledge_revisions SET status='failed' WHERE id=? AND status!='deleted'").run(i.revision_id);
      if (i.original_handle) db.prepare('INSERT OR IGNORE INTO knowledge_cleanup VALUES(?,0,?,?)').run(i.revision_id, c.code, now());
      i.state = 'failed'; result = saveIntent(db, i); break;
    }
    case 'knowledge.source.pin': {
      const initial = pinSource(db, c.request.reference, c.operation, c.request.conversation);
      if (c.operation === 'model_input' && initial.metadata.excluded_pages?.length) {
        const locator = c.request.reference.locator;
        const page = c.request.page ?? (locator?.kind === 'pdf' ? locator.physical_page : locator?.kind === 'text' && locator.item_ref.startsWith('reader-v1:pdf:') ? Number(locator.item_ref.split(':').at(-1)) : 1);
        if (initial.metadata.excluded_pages.includes(page)) reject('reader_passage_denied');
      }
      result = initial;
      const pin = result as SourcePin;
      if (c.operation === 'model_input' && (c.request.expected_policy_revision !== pin.policy_revision || c.request.expected_context_epoch !== pin.context_epoch)) reject('reader_context_changed'); break;
    }
    case 'knowledge.source.recheck': {
      const pin = pinSource(db, c.pin.reference, c.operation);
      if (pin.fingerprint !== c.pin.fingerprint || pin.stamp !== c.pin.stamp) reject('reader_revision_conflict'); result = pin; break;
    }
    case 'knowledge.source.dependency': {
      const pin = pinSource(db, c.pin.reference, 'model_input'); if (pin.fingerprint !== c.pin.fingerprint) reject('reader_revision_conflict');
      const { d, r } = currentKnowledgeRevision(db, pin.revision_id), metadata = effectiveKnowledgeMetadata(db, parse<Metadata>(r.metadata_json)), rights = parse<Rights>(r.rights_json);
      const representative = rows(db, 'SELECT id,locators_json FROM knowledge_passages WHERE revision_id=? ORDER BY ordinal LIMIT 12000', pin.revision_id)
        .find(p => !parse<{ page?: number }[]>(p.locators_json).some(l => metadata.excluded_pages?.includes(l.page!)));
      if (!representative) reject('learning_source_unavailable');
      const target = { type: 'library_revision' as const, id: pin.revision_id };
      result = { target, expected_revision: sha({ identity: target, document_id: r.document_id, sha256: r.sha256, title: d.title, source_id: d.source_id,
        metadata, rights, passage_id: representative.id, locators: parse(representative.locators_json) }) }; break;
    }
    case 'knowledge.notes.pin': result = notePin(db, c.documentId, c.revisionId); break;
    case 'knowledge.notes.list': {
      if (c.projectId && (!one(db, "SELECT 1 FROM study_projects WHERE id=? AND lifecycle!='deleted'", c.projectId) || deleted(db, c.projectId, 'project'))) reject('project_missing');
      const selected = rows(db, "SELECT d.id FROM knowledge_documents d JOIN knowledge_revisions r ON r.id=d.latest_revision WHERE d.deleted_at IS NULL AND d.scope_kind='personal-library' AND d.scope_entity IS NULL AND d.reserved=0 AND EXISTS(SELECT 1 FROM json_each(r.metadata_json,'$.asset_role') WHERE value='study-note') AND (?='' OR EXISTS(SELECT 1 FROM study_project_documents m WHERE m.revision_id=r.id AND m.project_id=?)) ORDER BY r.created_at DESC,r.id DESC LIMIT ? OFFSET ?", c.projectId ?? '', c.projectId ?? '', c.limit, c.offset);
      result = { items: selected.filter(d => !deleted(db, String(d.id), 'document', 'knowledge-document')).map(d => notePin(db, String(d.id), null).summary) }; break;
    }
    case 'knowledge.delete': {
      const key = 'knowledge.target.delete:' + digest(c.idempotencyKey), requestHash = sha(c), previous = pref(db, key);
      if (previous) { const p = parse<{ hash: string; result: unknown }>(previous); if (p.hash !== requestHash) reject('idempotency_conflict'); result = p.result; break; }
      const d = document(db, c.documentId); if (c.expectedRevisionId !== null && d.latest_revision !== c.expectedRevisionId) reject('note_revision_conflict'); if (c.note) notePin(db, c.documentId, c.expectedRevisionId);
      const revisions = rows(db, 'SELECT id FROM knowledge_revisions WHERE document_id=?', c.documentId).map(r => String(r.id));
      for (const revision of revisions) {
        markDeleted(db, 'knowledge-revision', revision); db.prepare("UPDATE knowledge_revisions SET status='deleted' WHERE id=?").run(revision);
        db.prepare("UPDATE knowledge_jobs SET state='cancelled',phase='cancelled',finished_at=? WHERE revision_id=? AND state IN ('queued','processing')").run(now(), revision);
        db.prepare('INSERT OR IGNORE INTO knowledge_cleanup VALUES(?,0,NULL,?)').run(revision, now());
        for (const m of rows(db, 'SELECT id,project_id FROM study_project_documents WHERE revision_id=?', revision)) {
          markDeleted(db, 'project_document', String(m.id)); db.prepare('DELETE FROM study_project_documents WHERE id=?').run(m.id);
          db.prepare('UPDATE study_projects SET revision=revision+1,updated_at=? WHERE id=?').run(now(), m.project_id);
        }
      }
      markDeleted(db, 'knowledge-document', c.documentId); db.prepare('UPDATE knowledge_documents SET deleted_at=?,active_revision=NULL,updated_at=? WHERE id=?').run(now(), now(), c.documentId);
      bumpKnowledgeContext(db); result = { document_id: c.documentId, revision_id: String(d.latest_revision), deleted: true, revision_ids: revisions }; put(db, key, { hash: requestHash, result }); break;
    }
    case 'knowledge.find': {
      const stamp = knowledgeStamp(db); if (c.epoch !== null && c.epoch !== stamp) reject('search_cursor_changed');
      if (c.projectId !== null && (!one(db, "SELECT 1 FROM study_projects WHERE id=? AND lifecycle!='deleted'", c.projectId) || deleted(db, c.projectId, 'project'))) reject('project_missing');
      const needle = c.query.toLowerCase(), link = c.projectId === null ? '' : ' JOIN study_project_documents links ON links.revision_id=r.id AND links.project_id=?';
      const scanned = rows(db, 'SELECT r.id,r.status,d.id AS document_id,d.title,r.rights_json,r.metadata_json FROM knowledge_documents d JOIN knowledge_revisions r ON r.id=COALESCE(d.active_revision,d.latest_revision)' + link +
        " WHERE d.deleted_at IS NULL AND d.reserved=0 AND d.scope_kind='personal-library' AND d.scope_entity IS NULL AND r.id>? ORDER BY r.id LIMIT ?", ...(c.projectId === null ? [] : [c.projectId]), c.after ?? '', c.limit + 1);
      const items: KnowledgeResults['knowledge.find']['items'] = [];
      for (const row of scanned.slice(0, c.limit)) {
        if (deleted(db, String(row.document_id), 'document', 'knowledge-document') || deleted(db, String(row.id), 'revision', 'knowledge-revision')) continue;
        let rights: Rights, metadata: Metadata; try { rights = parse(row.rights_json); metadata = parse(row.metadata_json); } catch { continue; }
        if (rights.display !== true) continue;
        // Index text only from eligible ready revisions; titles of display-permitted files stay findable.
        const hit = row.status === 'ready' && eligibleKnowledge(metadata, rights) ? one(db, 'SELECT text,locators_json FROM knowledge_passages WHERE revision_id=? AND instr(lower(text),?)>0 ORDER BY ordinal LIMIT 1', String(row.id), needle) : undefined;
        if (!hit && !String(row.title).toLowerCase().includes(needle)) continue;
        items.push({ revision_id: String(row.id), title: String(row.title), status: String(row.status), note: !!metadata.asset_role?.includes('study-note'),
          text: hit ? String(hit.text) : null, locators_json: hit ? String(hit.locators_json) : null });
      }
      result = { items, next: scanned.length > c.limit ? String(scanned[c.limit - 1].id) : null, epoch: stamp }; break;
    }
    case 'knowledge.cleanup':
      for (const id of c.revisionIds) { db.prepare('DELETE FROM knowledge_passages WHERE revision_id=? AND EXISTS(SELECT 1 FROM knowledge_cleanup WHERE revision_id=?)').run(id, id); db.prepare('DELETE FROM knowledge_cleanup WHERE revision_id=? AND remove_original=0').run(id); }
      result = { removed: c.revisionIds.length }; break;
  }
  return result as KnowledgeResults[C['type']];
}
