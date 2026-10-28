// SPDX-License-Identifier: MIT
import type { DispatchCommand, DispatchResults } from '../dispatch/contracts.ts';
import { isDispatchCommand } from './dispatch.ts';
import type { LearningCommand, LearningResults } from '../domain/learning/contracts.ts';
import { isLearningCommand, validateLearningCommand } from './learning.ts';
import type { LearningMetadataCommand, LearningMetadataResults } from '../domain/learning/metadata-contracts.ts';
import { isLearningMetadataCommand, validateLearningMetadataCommand } from './conversation-metadata.ts';
import type { MemoryCommand, MemoryResults } from '../domain/memory/contracts.ts';
import { isMemoryCommand, validateMemoryCommand } from './memory.ts';
import type { KnowledgeCommand, KnowledgeResults } from '../domain/knowledge/contracts.ts';
import { isKnowledgeCommand, validateKnowledgeCommand } from './knowledge.ts';
import type { StudyCommand, StudyResults } from '../domain/study/contracts.ts';
import { isStudyCommand, validateStudyCommand } from './study.ts';
import type { CapabilityCommand, CapabilityResults } from '../domain/capabilities/contracts.ts';
import { isCapabilityCommand, validateCapabilityCommand } from '../domain/capabilities/commands.ts';
import type { McpConnectionCommand, McpConnectionResults } from '../domain/capabilities/mcp-commands.ts';
import { isMcpConnectionCommand, validateMcpConnectionCommand } from '../domain/capabilities/mcp-commands.ts';
import type { LearningDispatchCommand, LearningDispatchResults } from '../domain/learning/admission-contracts.ts';
import { validateLearningDispatchCommand } from './admission.ts';
import type { ContentCommand, ContentResults } from '../domain/content/contracts.ts';
import { isContentCommand, validateContentCommand } from './content.ts';
import type { ProjectCommand, ProjectResults } from '../domain/projects/contracts.ts';
import { isProjectCommand, validateProjectCommand } from './projects.ts';
import type { AssessmentCommand, AssessmentResults } from '../domain/assessment/contracts.ts';
import { isAssessmentCommand, validateAssessmentCommand } from './assessment.ts';
import type { RecoveryCommand, RecoveryResults } from '../domain/recovery/contracts.ts';
import { isRecoveryCommand, validateRecoveryCommand } from './recovery.ts';
import type { UpdatesCommand, UpdatesResults } from '../domain/updates/contracts.ts';
import { isUpdatesCommand, validateUpdatesCommand } from './updates.ts';
import type { TemporaryCommand, TemporaryResults } from '../domain/temporary/contracts.ts';
import { isTemporaryCommand, validateTemporaryCommand } from './temporary.ts';
import type { EvidenceCommand, EvidenceResults } from '../domain/evidence/contracts.ts';
import { isEvidenceCommand, validateEvidenceCommand } from '../domain/evidence/commands.ts';
import type { SelectedWriterAuthority } from './selected-owner.ts';
export type Scalar = string | number | null;
export type RecordRow = Record<string, Scalar>;
export type MigrationInventory = Record<string, string>;

/** BF00 only. This is a separate contract, not an extension of harness/1. */
export interface SyntheticSelector {
  contract: 'renulus-storage-selector/1';
  isolation: 'synthetic';
  profileId: string;
  generation: number;
  authorityEpoch: number;
  writer: 'python' | 'ts';
  state: 'prepared' | 'active' | 'recovery';
  ownerId: string;
  database: 'state/renulus.sqlite3';
}

export interface PreviewOptions {
  databasePath: string;
  /** SHA256 of the exact UTF-8 migration scripts read by Python. */
  migrations: MigrationInventory;
  expectedSchemaHash?: string;
}

export type WriterOptions = {
  profileRoot: string;
  migrations: MigrationInventory;
  /** Compare a trusted populated baseline, never bless an unknown schema. */
  expectedSchemaHash: string;
} & ({ selection: SyntheticSelector; selectedAuthority?: never } |
     { selectedAuthority: SelectedWriterAuthority; selection?: never });

export interface TableInventory {
  name: string;
  columns: RecordRow[];
  foreignKeys: RecordRow[];
  indexes: Array<{ definition: RecordRow; columns: RecordRow[] }>;
  rowCount: number;
}

export interface StoragePreview {
  schemaVersion: number;
  schemaHash: string;
  migrations: Array<{ name: string; checksum: string }>;
  pendingMigrations: string[];
  tables: TableInventory[];
  foreignKeyViolations: RecordRow[];
  integrityCheck: string[];
  compatible: boolean;
  issues: string[];
}

export interface ConversationSummary {
  identity: { type: 'learn_thread'; id: string };
  kind: 'learning';
  retention: 'saved';
  lifecycle: string;
  revision: number;
  title: string;
  project_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface CanonicalExport {
  format: 'renulus-canonical-export';
  format_version: 1;
  schema_version: 2;
  exported_at: string;
  data_kind: 'records-only';
  records: Record<string, RecordRow[]>;
  artifacts: Record<string, never>;
  limits: string;
  omissions: Record<string, { records: number; reason: string }>;
}

export type StorageCommand = DispatchCommand | LearningMetadataCommand | LearningDispatchCommand | LearningCommand | MemoryCommand | KnowledgeCommand | StudyCommand | EvidenceCommand | CapabilityCommand | McpConnectionCommand | ContentCommand | ProjectCommand | AssessmentCommand | RecoveryCommand | UpdatesCommand | TemporaryCommand
  | { type: 'storage.preview' }
  | { type: 'records.page'; table: string; offset: number; limit: number }
  | { type: 'records.export' }
  | { type: 'learning.rename'; threadId: string; expectedRevision: number; title: string; idempotencyKey: string }
  | { type: 'database.backup'; name: string };

export interface CommandResults extends DispatchResults, LearningResults, LearningDispatchResults, LearningMetadataResults, MemoryResults, KnowledgeResults, StudyResults, EvidenceResults, CapabilityResults, McpConnectionResults, ContentResults, ProjectResults, AssessmentResults, RecoveryResults, UpdatesResults, TemporaryResults {
  'storage.preview': StoragePreview;
  'records.page': { rows: RecordRow[]; nextOffset: number | null };
  'records.export': CanonicalExport;
  'learning.rename': ConversationSummary;
  'database.backup': { path: string; pages: number };
}

export class StorageError extends Error {
  readonly code: string;
  constructor(code: string, message = code) {
    super(message);
    this.name = 'StorageError';
    this.code = code;
  }
}

export function reject(code: string, message?: string): never {
  throw new StorageError(code, message);
}

/** Runtime validation also rejects extra fields sent by untyped callers. */
export function exact(value: unknown, keys: readonly string[]): asserts value is Record<string, unknown> {
  if (value === null || typeof value !== 'object' || Array.isArray(value) ||
      Object.keys(value).sort().join('\0') !== [...keys].sort().join('\0')) reject('storage_invalid_command');
}

export function text(value: unknown, min: number, max: number): asserts value is string {
  if (typeof value !== 'string' || [...value].length < min || [...value].length > max ||
      /[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/u.test(value)) reject('storage_invalid_command');
}

export function integer(value: unknown, min = 0, max = Number.MAX_SAFE_INTEGER): asserts value is number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < min || value > max) reject('storage_invalid_command');
}

export function validateCommand(value: unknown): asserts value is StorageCommand {
  if (!value || typeof value !== 'object') reject('storage_invalid_command');
  if (isDispatchCommand(value)) return;
  if (isMemoryCommand(value)) { validateMemoryCommand(value); return; }
  if (isKnowledgeCommand(value)) { validateKnowledgeCommand(value); return; }
  if (isStudyCommand(value)) { validateStudyCommand(value); return; }
  if (isEvidenceCommand(value)) { validateEvidenceCommand(value); return; }
  if (isCapabilityCommand(value)) { validateCapabilityCommand(value); return; }
  if (isMcpConnectionCommand(value)) { validateMcpConnectionCommand(value); return; }
  if (isContentCommand(value)) { validateContentCommand(value); return; }
  if (isProjectCommand(value)) { validateProjectCommand(value); return; }
  if (isAssessmentCommand(value)) { validateAssessmentCommand(value); return; }
  if (isRecoveryCommand(value)) { validateRecoveryCommand(value); return; }
  if (isUpdatesCommand(value)) { validateUpdatesCommand(value); return; }
  if (isTemporaryCommand(value)) { validateTemporaryCommand(value); return; }
  if ('type' in value && value.type === 'learning.dispatch.begin') { validateLearningDispatchCommand(value as LearningDispatchCommand); return; }
  if (isLearningMetadataCommand(value)) { validateLearningMetadataCommand(value); return; }
  if (isLearningCommand(value)) { validateLearningCommand(value); return; }
  const command = value as StorageCommand;
  switch (command.type) {
    case 'storage.preview': case 'records.export': exact(value, ['type']); break;
    case 'records.page':
      exact(value, ['type', 'table', 'offset', 'limit']); text(command.table, 1, 128);
      integer(command.offset); integer(command.limit, 1, 100); break;
    case 'learning.rename':
      exact(value, ['type', 'threadId', 'expectedRevision', 'title', 'idempotencyKey']);
      text(command.threadId, 1, 120); text(command.title, 1, 120);
      text(command.idempotencyKey, 8, 128); integer(command.expectedRevision, 1); break;
    case 'database.backup':
      exact(value, ['type', 'name']); text(command.name, 1, 80);
      if (!/^[a-zA-Z0-9_-]+$/.test(command.name)) reject('storage_invalid_command'); break;
    default: reject('storage_invalid_command');
  }
}
