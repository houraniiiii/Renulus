// SPDX-License-Identifier: MIT
import type { DatabaseSync } from 'node:sqlite';
import type { LearningDispatchCommand } from '../domain/learning/admission-contracts.ts';
import { exact, integer, reject } from './contracts.ts';
import { executeLearning } from './learning.ts';
import { executeDispatch } from './dispatch.ts';
import { id, hash, strings } from '../dispatch/policy.ts';

export function validateLearningDispatchCommand(c: LearningDispatchCommand) {
  exact(c, ['type', 'runId', 'expectedVersion', 'availableModels', 'operationModel', 'capabilities', 'fenceBase']);
  id(c.runId); hash(c.expectedVersion); strings(c.availableModels); strings(c.capabilities);
  if (c.operationModel !== null) id(c.operationModel);
  exact(c.fenceBase, ['profile_id', 'domain_store_id', 'runtime_store_id', 'authority_epoch', 'process_generation']);
  for (const field of ['profile_id', 'domain_store_id', 'runtime_store_id', 'process_generation'] as const) id(c.fenceBase[field]);
  integer(c.fenceBase.authority_epoch, 1);
}
/** Called by the one canonical worker inside its current local transaction. */
export function executeLearningDispatch(db: DatabaseSync, c: LearningDispatchCommand) {
  if (!db.isTransaction) reject('learning_transaction_required');
  validateLearningDispatchCommand(c);
  const run = executeLearning(db, { type: 'learning.current', runId: c.runId, binding: null });
  const cp = run.checkpoint, base = c.fenceBase;
  if (cp.identity.profileId !== base.profile_id || cp.identity.storeId !== base.runtime_store_id ||
      cp.identity.generation !== base.process_generation) reject('learning_generation_changed');
  const owner = db.prepare('SELECT profile_id,store_id FROM harness_store_identity WHERE singleton=1').get();
  if (!owner || owner.profile_id !== base.profile_id || owner.store_id !== base.domain_store_id) reject('learning_generation_changed');
  // Source deletion and policy changes invalidate this same checkpoint/context.
  return executeDispatch(db, { type: 'dispatch.begin', runId: c.runId, purpose: 'explain', expectedVersion: c.expectedVersion,
    capabilities: c.capabilities, availableModels: c.availableModels, operationModel: c.operationModel, batchSize: null,
    fence: { ...base, context_epoch: cp.contextEpoch, deletion_epoch: cp.policyRevision, cancellation_epoch: cp.cancellationEpoch } });
}
