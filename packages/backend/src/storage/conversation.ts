// SPDX-License-Identifier: MIT
// Synchronous local mutation; no engine, native transcript, provider or IPC calls.
import type { DatabaseSync } from 'node:sqlite';
import { reject } from './contracts.ts';
import type { ConversationSummary, StorageCommand } from './contracts.ts';
import { canonical, digest, one } from './schema.ts';
import { utcNow } from './export.ts';

export function requireAssistance(db: DatabaseSync): void {
  const active = one(db, "SELECT id FROM assessment_test_attempts WHERE mode='test' AND status='active' LIMIT 1");
  if (active) reject('assistance_restricted');
}

export function renameLearning(db: DatabaseSync, command: Extract<StorageCommand, { type: 'learning.rename' }>): ConversationSummary {
  requireAssistance(db); // Replays do not bypass present policy or tombstones.
  if (one(db, 'SELECT 1 FROM learn_command_tombstones WHERE ledger=? AND idempotency_key=?', 'conversation_commands', command.idempotencyKey) ||
      one(db, "SELECT 1 FROM deletion_ledger WHERE entity_type='conversation_command' AND entity_id=?", command.idempotencyKey)) reject('command_terminal_unavailable');
  const requestHash = digest(canonical({ operation: 'rename', target_type: 'learn_thread', target_id: command.threadId,
    request: { expected_revision: command.expectedRevision, title: command.title } }));
  const previous = one(db, 'SELECT request_hash,result_json FROM conversation_commands WHERE idempotency_key=?', command.idempotencyKey);
  if (previous) {
    if (previous.request_hash !== requestHash) reject('idempotency_conflict');
    return JSON.parse(String(previous.result_json));
  }
  if (one(db, "SELECT 1 FROM deletion_ledger WHERE entity_type='learn_thread' AND entity_id=?", command.threadId)) reject('conversation_missing');
  const thread = one(db, 'SELECT * FROM learn_threads WHERE id=?', command.threadId);
  if (!thread) reject('conversation_missing');
  // Same lazy sidecar insertion as ConversationRepository._saved.
  db.prepare('INSERT OR IGNORE INTO learn_conversations(thread_id,updated_at) VALUES(?,?)').run(command.threadId, utcNow());
  const metadata = one(db, 'SELECT * FROM learn_conversations WHERE thread_id=?', command.threadId)!;
  if (metadata.revision !== command.expectedRevision) reject('conversation_revision_conflict');
  const now = utcNow();
  db.prepare('UPDATE learn_threads SET title=?,updated_at=? WHERE id=?').run(command.title, now, command.threadId);
  db.prepare('UPDATE learn_conversations SET revision=revision+1,updated_at=? WHERE thread_id=?').run(now, command.threadId);
  db.prepare("INSERT INTO preferences VALUES('design_c.context_epoch','1',?) ON CONFLICT(key) DO UPDATE SET " +
    'value=CAST(CAST(preferences.value AS INTEGER)+1 AS TEXT),updated_at=excluded.updated_at').run(now);
  const project = one(db, "SELECT project_id FROM study_project_chats WHERE chat_kind='learning' AND chat_id=?", command.threadId);
  const result: ConversationSummary = { identity: { type: 'learn_thread', id: command.threadId }, kind: 'learning', retention: 'saved',
    lifecycle: String(metadata.lifecycle), revision: Number(metadata.revision) + 1, title: command.title,
    project_id: project ? String(project.project_id) : null, created_at: String(thread.created_at), updated_at: now };
  db.prepare('INSERT INTO conversation_commands VALUES(?,?,?,?,?,?,?)').run(command.idempotencyKey, 'rename', 'learn_thread',
    command.threadId, requestHash, JSON.stringify(result), now);
  return result;
}
