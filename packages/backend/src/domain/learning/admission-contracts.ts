// SPDX-License-Identifier: MIT
import type { ProcessIdentity } from '../../../../contracts/worker.ts';
import type { Run } from '../../dispatch/contracts.ts';
export type LearningDispatchCommand = { type: 'learning.dispatch.begin'; runId: string; expectedVersion: string;
  availableModels: string[]; operationModel: string | null; capabilities: string[]; fenceBase: ProcessIdentity };
export interface LearningDispatchResults { 'learning.dispatch.begin': Run }
