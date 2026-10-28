// SPDX-License-Identifier: MIT
import { parentPort, workerData } from 'node:worker_threads';
import { executeDispatch, isDispatchCommand } from './dispatch.ts';
import { executeLearning, isLearningCommand } from './learning.ts';
import { executeLearningMetadata, isLearningMetadataCommand } from './conversation-metadata.ts';
import { executeMemoryCommand, isMemoryCommand, reconcileMemorySupport, queueMemoryCapture } from './memory.ts';
import { executeKnowledge, isKnowledgeCommand } from './knowledge.ts';
import { executeStudy, isStudyCommand } from './study.ts';
import { executeEvidenceCommand, isEvidenceCommand } from '../domain/evidence/commands.ts';
import { executeCapabilityCommand, isCapabilityCommand } from '../domain/capabilities/commands.ts';
import { executeMcpConnectionCommand, isMcpConnectionCommand } from '../domain/capabilities/mcp-commands.ts';
import { executeLearningDispatch } from './admission.ts';
import { executeContent, isContentCommand } from './content.ts';
import { executeProject, isProjectCommand } from './projects.ts';
import { executeAssessment, isAssessmentCommand, reconcileAssessments } from './assessment.ts';
import { executeRecovery, isRecoveryCommand } from './recovery.ts';
import { executeUpdates, isUpdatesCommand } from './updates.ts';
import { executeTemporary, isTemporaryCommand } from './temporary.ts';
import { DatabaseSync, backup } from 'node:sqlite';
import { closeSync, existsSync, linkSync, mkdirSync, openSync, realpathSync, unlinkSync } from 'node:fs';
import { isAbsolute, join, resolve } from 'node:path';
import { randomUUID } from 'node:crypto';
import { reject, validateCommand } from './contracts.ts';
import type { PreviewOptions, StorageCommand, WriterOptions } from './contracts.ts';
import { inventory } from './schema.ts';
import { exportRecords, page } from './export.ts';
import { renameLearning } from './conversation.ts';
import { acquireOwner, owned } from './ownership.ts';

const port = parentPort!;
let db: DatabaseSync | undefined;
let owner: ReturnType<typeof acquireOwner> | undefined;
let closed = false;
const mode = workerData.mode as 'preview' | 'writer';
const options = workerData.options as PreviewOptions & WriterOptions;

function serialized(error: unknown) {
  const code = error !== null && typeof error === 'object' && 'code' in error ? String(error.code) : 'storage_failure';
  // SQLite diagnostics can contain payloads; return a stable local code only.
  return { code, message: code };
}
function transaction<T>(write: boolean, action: () => T): T {
  owner?.check();
  db!.exec(write ? 'BEGIN IMMEDIATE' : 'BEGIN');
  try {
    owner?.check();
    const result = action(); // Deliberately synchronous; no promise/cross-process wait.
    owner?.check();
    db!.exec('COMMIT');
    return result;
  } catch (error) {
    try { db!.exec('ROLLBACK'); } catch { /* SQLite may already have rolled back the transaction. */ }
    throw error;
  }
}
function preview() { return inventory(db!, options.migrations, options.expectedSchemaHash); }

async function backupDatabase(name: string) {
  owner!.check();
  const root = resolve(options.profileRoot);
  const directory = owned(root, join(root, 'state', 'backups'));
  mkdirSync(directory, { recursive: true });
  const destination = owned(root, join(directory, name + '.sqlite3'));
  if (existsSync(destination)) reject('storage_backup_exists');
  const staging = owned(root, join(directory, '.backup-' + randomUUID() + '.sqlite3'));
  closeSync(openSync(staging, 'wx', 0o600));
  try {
    // Native online backup runs outside canonical transactions; queue retains ownership until settlement.
    const pages = await backup(db!, staging);
    owner!.check();
    linkSync(staging, destination); // create-if-absent publication, never overwrite an original.
    return { path: destination, pages };
  } finally { unlinkSync(staging); }
}

async function dispatch(command: StorageCommand) {
  validateCommand(command);
  if (closed) reject('storage_closed');
  if (mode === 'preview' && command.type !== 'storage.preview') reject('storage_read_only');
  owner?.check();
  // Deadline finalisation is committed independently of a subsequently refused
  // assistance command, preserving offline scoring and the Test policy fence.
  if (mode === 'writer') transaction(true, () => reconcileAssessments(db!));
  if (isDispatchCommand(command)) return transaction(true, () => executeDispatch(db!, command));
  if (isAssessmentCommand(command)) return transaction(true, () => executeAssessment(db!, command));
  if (isRecoveryCommand(command)) return transaction(command.type !== 'recovery.snapshot' && command.type !== 'storage.reservations', () => executeRecovery(db!, command));
  if (isUpdatesCommand(command)) return transaction(true, () => executeUpdates(db!, command));
  if (isTemporaryCommand(command)) return transaction(true, () => executeTemporary(db!, command));
  if (isMemoryCommand(command)) return transaction(true, () => executeMemoryCommand(db!, command));
  if (isKnowledgeCommand(command)) return transaction(true, () => {
    const result = executeKnowledge(db!, command);
    if (['knowledge.import.ready', 'knowledge.delete', 'knowledge.cleanup'].includes(command.type)) reconcileMemorySupport(db!);
    return result;
  });
  if (isProjectCommand(command)) return transaction(true, () => {
    const result = executeProject(db!, command);
    if (command.type !== 'project.list' && command.type !== 'project.get') reconcileMemorySupport(db!);
    return result;
  });
  if (isStudyCommand(command)) return transaction(true, () => executeStudy(db!, command));
  if (isEvidenceCommand(command)) return transaction(command.type === 'evidence.reserve' || command.type === 'evidence.settle', () => executeEvidenceCommand(db!, command));
  if (isCapabilityCommand(command)) return transaction(true, () => executeCapabilityCommand(db!, command));
  if (isMcpConnectionCommand(command)) return transaction(true, () => executeMcpConnectionCommand(db!, command));
  if (isContentCommand(command)) return transaction(true, () => executeContent(db!, command));
  if (command.type === 'learning.dispatch.begin') return transaction(true, () => executeLearningDispatch(db!, command));
  if (isLearningMetadataCommand(command)) return transaction(true, () => executeLearningMetadata(db!, command));
  if (isLearningCommand(command)) return transaction(true, () => {
    const result = executeLearning(db!, command);
    if (command.type === 'learning.publish') queueMemoryCapture(db!, 'learn-answer:' + command.binding.operation_id);
    if (['learning.lifecycle', 'learning.project', 'learning.delete'].includes(command.type)) reconcileMemorySupport(db!);
    return result;
  });
  switch (command.type) {
    case 'storage.preview': return transaction(false, preview);
    case 'records.page': return transaction(false, () => page(db!, command.table, command.offset, command.limit));
    case 'records.export': return transaction(false, () => exportRecords(db!));
    case 'learning.rename': return transaction(true, () => renameLearning(db!, command));
    case 'database.backup': return backupDatabase(command.name);
  }
}

try {
  if (process.versions.node !== '26.4.0') reject('storage_node_cohort_mismatch');
  let path: string;
  if (mode === 'writer') { owner = acquireOwner(options); path = owner.databasePath; }
  else {
    if (mode !== 'preview' || !isAbsolute(options.databasePath)) reject('storage_preview_path');
    path = resolve(options.databasePath);
    if (realpathSync(path).toLowerCase() !== path.toLowerCase()) reject('storage_path_alias');
  }
  // Preview is opened read-only, including the initial schema check; it cannot bootstrap/migrate a profile.
  db = new DatabaseSync(path, { readOnly: true, timeout: 15000, enableForeignKeyConstraints: true, allowExtension: false });
  db.exec('PRAGMA foreign_keys=ON; PRAGMA busy_timeout=15000; PRAGMA secure_delete=ON;');
  const initial = transaction(false, preview);
  if (mode === 'writer') {
    if (!/^[a-f0-9]{64}$/.test(options.expectedSchemaHash)) reject('storage_schema_baseline_required');
    if (!initial.compatible) reject(initial.issues[0]!);
    db.close();
    owner!.check();
    db = new DatabaseSync(path, { timeout: 15000, enableForeignKeyConstraints: true, allowExtension: false });
    db.exec('PRAGMA foreign_keys=ON; PRAGMA busy_timeout=15000; PRAGMA secure_delete=ON; PRAGMA journal_mode=WAL;');
    owner!.check();
    // Close a read-only-open/reopen race before publishing readiness.
    const reopened = transaction(false, preview);
    if (!reopened.compatible) reject(reopened.issues[0]!);
  }
  let tail = Promise.resolve();
  port.on('message', ({ id, command }) => {
    // Includes asynchronous backup settlement; messages cannot overlap canonical ownership.
    tail = tail.then(async () => {
      try {
        if (command?.type === 'close' && Object.keys(command).length === 1) {
          closed = true; db!.close(); owner?.release();
          port.postMessage({ id, result: null }); port.close(); return;
        }
        const result = await dispatch(command);
        port.postMessage({ id, result });
      } catch (error) { port.postMessage({ id, error: serialized(error) }); }
    });
  });
  port.postMessage({ type: 'ready' });
} catch (error) {
  try { db?.close(); owner?.release(); } catch { /* Retain ambiguous ownership. */ }
  port.postMessage({ type: 'startup-error', ...serialized(error) });
  port.close();
}
