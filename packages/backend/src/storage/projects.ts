// SPDX-License-Identifier: MIT
import type { DatabaseSync } from 'node:sqlite';
import { exact, integer, reject, text } from './contracts.ts';
import { requireAssistance } from './conversation.ts';
import { canonical, digest, one, rows } from './schema.ts';
import { bumpKnowledgeContext, currentKnowledgeRevision, deleted, knowledgeId, knowledgeStamp, markDeleted } from './knowledge.ts';
import type { GoalInput, ProjectCommand, ProjectResults } from '../domain/projects/contracts.ts';

const now = () => new Date().toISOString();
const identifier = (v: unknown) => { text(v, 1, 128); if (!/^[A-Za-z0-9_-]+$/.test(v)) reject('storage_invalid_command'); };
export function isProjectCommand(v: unknown): v is ProjectCommand { return !!v && typeof v === 'object' && String((v as ProjectCommand).type).startsWith('project.'); }
function goalInput(input: GoalInput) {
  exact(input, ['title', 'topic_id', 'target_date', 'status', 'progress']); text(input.title, 1, 240);
  if (input.topic_id !== null) identifier(input.topic_id);
  if (input.target_date !== null && (!/^\d{4}-\d{2}-\d{2}$/.test(input.target_date) || new Date(input.target_date).toISOString().slice(0, 10) !== input.target_date)) reject('goal_date_invalid');
  if (!['active', 'completed'].includes(input.status)) reject('goal_status_invalid');
  exact(input.progress, ['evidence_ids', 'manual_intent']);
  if (!Array.isArray(input.progress.evidence_ids) || input.progress.evidence_ids.length > 100 || new Set(input.progress.evidence_ids).size !== input.progress.evidence_ids.length) reject('goal_evidence_invalid');
  input.progress.evidence_ids.forEach(identifier); if (input.progress.manual_intent !== null) text(input.progress.manual_intent, 1, 2000);
}
export function validateProjectCommand(value: unknown): asserts value is ProjectCommand {
  const c = value as ProjectCommand;
  switch (c.type) {
    case 'project.list': exact(c, ['type', 'limit', 'cursor', 'lifecycle']); integer(c.limit, 1, 100); if (c.cursor !== null) text(c.cursor, 1, 2048); if (!['active', 'archived'].includes(c.lifecycle)) reject('storage_invalid_command'); break;
    case 'project.get': exact(c, ['type', 'projectId']); identifier(c.projectId); break;
    case 'project.find': exact(c, ['type', 'query', 'lifecycle', 'projectId', 'after', 'limit', 'epoch']); text(c.query, 1, 240); if (!['active', 'archived', 'all'].includes(c.lifecycle)) reject('storage_invalid_command');
      if (c.projectId !== null) identifier(c.projectId); if (c.after !== null) identifier(c.after); integer(c.limit, 1, 200); if (c.epoch !== null) text(c.epoch, 64, 64); break;
    case 'project.create': exact(c, ['type', 'title', 'idempotencyKey']); text(c.title, 1, 120); text(c.idempotencyKey, 1, 200); break;
    case 'project.change': exact(c, ['type', 'projectId', 'expectedRevision', 'action', 'title', 'idempotencyKey']);
      if (!['rename', 'archive', 'restore', 'delete'].includes(c.action) || (c.action === 'rename') !== (c.title !== null)) reject('storage_invalid_command'); if (c.title !== null) text(c.title, 1, 120); break;
    case 'project.document': exact(c, ['type', 'projectId', 'expectedRevision', 'revisionId', 'position', 'action', 'idempotencyKey']); identifier(c.revisionId); integer(c.position, 0, 10000); if (!['link', 'unlink'].includes(c.action)) reject('storage_invalid_command'); break;
    case 'project.goal': exact(c, ['type', 'projectId', 'expectedRevision', 'goalId', 'goalRevision', 'action', 'input', 'idempotencyKey']);
      if (!['save', 'delete'].includes(c.action) || (c.goalId === null) !== (c.goalRevision === null) || (c.action === 'save') !== (c.input !== null) || c.action === 'delete' && !c.goalId) reject('storage_invalid_command');
      if (c.goalId !== null) { identifier(c.goalId); integer(c.goalRevision, 1); } if (c.input !== null) goalInput(c.input); break;
    default: reject('storage_invalid_command');
  }
  if ('expectedRevision' in c) { identifier(c.projectId); integer(c.expectedRevision, 1); text(c.idempotencyKey, 1, 200); }
}
function project(db: DatabaseSync, id: string) {
  const p = one(db, "SELECT * FROM study_projects WHERE id=? AND lifecycle!='deleted'", id);
  if (!p || deleted(db, id, 'project')) reject('project_missing'); return p;
}
function touch(db: DatabaseSync, id: string) { db.prepare('UPDATE study_projects SET revision=revision+1,updated_at=? WHERE id=?').run(now(), id); }
function view(db: DatabaseSync, id: string) {
  const p = project(db, id);
  const chats = rows(db, 'SELECT * FROM study_project_chats WHERE project_id=? ORDER BY position,id', id).flatMap(m => {
    const learning = m.chat_kind === 'learning', entity = learning ? 'learn_thread' : 'case';
    if (deleted(db, String(m.chat_id), entity) || deleted(db, String(m.id), 'project_chat')) return [];
    const parent = learning ? one(db, 'SELECT t.*,c.lifecycle,c.revision FROM learn_threads t LEFT JOIN learn_conversations c ON c.thread_id=t.id WHERE t.id=?', String(m.chat_id)) : one(db, 'SELECT * FROM case_sessions WHERE id=?', String(m.chat_id));
    if (!parent) return [];
    return [{ identity: { type: entity, id: m.chat_id }, kind: m.chat_kind, retention: 'saved', lifecycle: parent.lifecycle ?? 'active', revision: parent.revision ?? 1,
      title: parent.title, project_id: id, created_at: parent.created_at, updated_at: parent.updated_at, membership_id: m.id, position: m.position }];
  });
  const documents = rows(db, 'SELECT m.*,d.title,r.status FROM study_project_documents m JOIN knowledge_revisions r ON r.id=m.revision_id JOIN knowledge_documents d ON d.id=r.document_id WHERE m.project_id=? AND d.deleted_at IS NULL ORDER BY m.position,m.id', id)
    .filter(m => !deleted(db, String(m.id), 'project_document') && !deleted(db, String(m.revision_id), 'revision', 'knowledge-revision'));
  const goals = rows(db, 'SELECT * FROM study_project_goals WHERE project_id=? ORDER BY created_at,id', id).filter(g => !deleted(db, String(g.id), 'goal')).map(g => {
    const { progress_json, ...rest } = g; return { ...rest, progress: JSON.parse(String(progress_json)) };
  });
  return { ...p, chats, documents, goals };
}
function evidence(db: DatabaseSync, id: string) {
  const e = one(db, 'SELECT * FROM learning_evidence WHERE id=?', id); if (!e || deleted(db, id, 'learning_evidence')) reject('goal_evidence_unavailable');
  let payload: Record<string, any>; try { payload = JSON.parse(String(e.payload_json)); } catch { reject('goal_evidence_unavailable'); }
  const validStudy = e.kind === 'study-interest' && payload.activity === 'explain' && canonical(payload.scope) === canonical({ kind: 'study', entity_id: e.entity_id }) &&
    !!one(db, 'SELECT 1 FROM learn_threads WHERE id=?', String(e.entity_id)) && !deleted(db, String(e.entity_id), 'learn_thread');
  const validAssessment = e.kind === 'assessment-answer' && payload.scope?.kind === 'reviewed-assessment' && payload.mode === 'reviewed' && typeof payload.correct === 'boolean' &&
    !!one(db, 'SELECT 1 FROM assessment_attempts WHERE id=?', String(e.entity_id)) && !deleted(db, String(e.entity_id), 'assessment_attempt');
  if (!validStudy && !validAssessment) reject('goal_evidence_unavailable');
}
export function executeProject<C extends ProjectCommand>(db: DatabaseSync, c: C): ProjectResults[C['type']] {
  validateProjectCommand(c); requireAssistance(db);
  if (c.type === 'project.find') {
    const stamp = knowledgeStamp(db); if (c.epoch !== null && c.epoch !== stamp) reject('search_cursor_changed');
    if (c.projectId !== null) project(db, c.projectId);
    const selected = rows(db, "SELECT id,title,lifecycle FROM study_projects p WHERE lifecycle!='deleted' AND (?='all' OR lifecycle=?) AND (?='' OR id=?) AND id>? AND instr(lower(title),?)>0 AND NOT EXISTS(SELECT 1 FROM deletion_ledger WHERE entity_type='project' AND entity_id=p.id) ORDER BY id LIMIT ?",
      c.lifecycle, c.lifecycle, c.projectId ?? '', c.projectId ?? '', c.after ?? '', c.query.toLowerCase(), c.limit + 1);
    return { items: selected.slice(0, c.limit).map(p => ({ id: String(p.id), title: String(p.title), lifecycle: String(p.lifecycle) })),
      next: selected.length > c.limit ? String(selected[c.limit - 1].id) : null, epoch: stamp } as ProjectResults[C['type']];
  }
  if (c.type === 'project.get') return view(db, c.projectId) as unknown as ProjectResults[C['type']];
  if (c.type === 'project.list') {
    let page: { boundary: string; after: [string, string] | null; lifecycle: string } = { boundary: now(), after: null, lifecycle: c.lifecycle };
    if (c.cursor) {
      try { const v = JSON.parse(Buffer.from(c.cursor, 'base64url').toString('utf8')); exact(v, ['boundary', 'after', 'lifecycle']);
        text(v.boundary, 1, 80); if (v.lifecycle !== c.lifecycle || !Array.isArray(v.after) || v.after.length !== 2) reject('project_cursor_invalid');
        text(v.after[0], 1, 80); identifier(v.after[1]); page = v as typeof page;
      } catch { reject('project_cursor_invalid'); }
    }
    const selected = rows(db, "SELECT * FROM study_projects p WHERE lifecycle=? AND updated_at<=? AND (?='' OR (updated_at,id)<(?,?)) AND NOT EXISTS(SELECT 1 FROM deletion_ledger WHERE entity_type='project' AND entity_id=p.id) ORDER BY updated_at DESC,id DESC LIMIT ?",
      c.lifecycle, page.boundary, page.after?.[0] ?? '', page.after?.[0] ?? '', page.after?.[1] ?? '', c.limit + 1);
    const items = selected.slice(0, c.limit), last = items.at(-1);
    return { items, next_cursor: selected.length > c.limit && last ? Buffer.from(JSON.stringify({ ...page, after: [last.updated_at, last.id] })).toString('base64url') : null } as ProjectResults[C['type']];
  }
  const requestHash = digest(canonical(c)), previous = one(db, 'SELECT * FROM study_project_commands WHERE idempotency_key=?', c.idempotencyKey);
  if (deleted(db, c.idempotencyKey, 'project_command') || one(db, "SELECT 1 FROM learn_command_tombstones WHERE ledger='study_project_commands' AND idempotency_key=?", c.idempotencyKey)) reject('command_terminal_unavailable');
  if (previous) {
    if (previous.request_hash !== requestHash) reject('idempotency_conflict');
    const result = JSON.parse(String(previous.result_json)); if (c.type !== 'project.change' || c.action !== 'delete') project(db, result.id);
    return result as ProjectResults[C['type']];
  }
  let result: unknown, target: string;
  if (c.type === 'project.create') {
    target = knowledgeId('project'); db.prepare("INSERT INTO study_projects VALUES(?,?,'active',1,?,?)").run(target, c.title, now(), now()); result = view(db, target);
  } else {
    target = c.projectId; const p = project(db, target); if (p.revision !== c.expectedRevision) reject('project_revision_conflict');
    if (c.type === 'project.change') {
      if (c.action === 'delete') {
        for (const [table, type] of [['study_project_chats', 'project_chat'], ['study_project_documents', 'project_document'], ['study_project_goals', 'goal']])
          for (const m of rows(db, `SELECT id FROM ${table} WHERE project_id=?`, target)) markDeleted(db, type, String(m.id));
        // Membership owns no chat/document bytes. FK cascades only membership/goals.
        db.prepare('DELETE FROM study_projects WHERE id=?').run(target); markDeleted(db, 'project', target); result = { id: target, deleted: true };
      } else {
        if (c.action === 'rename') db.prepare('UPDATE study_projects SET title=? WHERE id=?').run(c.title, target);
        else db.prepare('UPDATE study_projects SET lifecycle=? WHERE id=?').run(c.action === 'archive' ? 'archived' : 'active', target);
        touch(db, target); result = view(db, target);
      }
    } else if (c.type === 'project.document') {
      const m = one(db, 'SELECT * FROM study_project_documents WHERE project_id=? AND revision_id=?', target, c.revisionId);
      if (c.action === 'link') {
        if (p.lifecycle !== 'active') reject('project_archived'); const { d, r } = currentKnowledgeRevision(db, c.revisionId);
        if (d.scope_kind !== 'personal-library' || d.scope_entity !== null || d.reserved || d.active_revision !== r.id || r.status !== 'ready') reject('document_unavailable');
        if (m) db.prepare('UPDATE study_project_documents SET position=?,revision=revision+1 WHERE id=?').run(c.position, m.id);
        else db.prepare('INSERT INTO study_project_documents VALUES(?,?,?,?,1,?)').run(knowledgeId('project_document'), target, c.revisionId, c.position, now());
      } else if (m) { markDeleted(db, 'project_document', String(m.id)); db.prepare('DELETE FROM study_project_documents WHERE id=?').run(m.id); }
      touch(db, target); result = view(db, target);
    } else {
      if (p.lifecycle !== 'active') reject('project_archived');
      if (c.goalId) { const g = one(db, 'SELECT * FROM study_project_goals WHERE id=? AND project_id=?', c.goalId, target);
        if (!g || deleted(db, c.goalId, 'goal')) reject('goal_missing'); if (g.revision !== c.goalRevision) reject('goal_revision_conflict'); }
      if (c.action === 'delete') { markDeleted(db, 'goal', c.goalId!); db.prepare('DELETE FROM study_project_goals WHERE id=?').run(c.goalId); }
      else {
        const input = c.input!; input.progress.evidence_ids.forEach(id => evidence(db, id));
        if (c.goalId) db.prepare('UPDATE study_project_goals SET title=?,topic_id=?,target_date=?,status=?,progress_json=?,revision=revision+1,updated_at=? WHERE id=?').run(input.title, input.topic_id, input.target_date, input.status, JSON.stringify(input.progress), now(), c.goalId);
        else db.prepare('INSERT INTO study_project_goals VALUES(?,?,?,?,?,?,?,1,?,?)').run(knowledgeId('goal'), target, input.title, input.topic_id, input.target_date, input.status, JSON.stringify(input.progress), now(), now());
      }
      touch(db, target); result = view(db, target);
    }
  }
  bumpKnowledgeContext(db);
  db.prepare('INSERT INTO study_project_commands VALUES(?,?,?,?,?,?,?)').run(c.idempotencyKey, c.type, 'project', target, requestHash, JSON.stringify(result), now());
  return result as ProjectResults[C['type']];
}
