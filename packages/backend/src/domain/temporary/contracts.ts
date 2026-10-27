// SPDX-License-Identifier: MIT
export interface PromotionPlan {
  id: string; threadId: string; title: string; profileId: string; storeId: string;
  rootSessionId: string; sessionIds: string[]; cancellationEpoch: number; contextEpoch: number;
  policyRevision: number; idempotencyKey: string;
}
export interface PromotionReceipt {
  id: string; state: 'staged' | 'copied' | 'active' | 'cancelled' | 'retired'; cancellationEpoch: number;
  threadId: string; rootSessionId: string; sessionIds: string[];
}
export type TemporaryCommand =
  | { type: 'temporary.save.begin'; plan: PromotionPlan }
  | { type: 'temporary.save.copied'; id: string; expectedEpoch: number; graphDigest: string }
  | { type: 'temporary.save.activate'; id: string; expectedEpoch: number }
  | { type: 'temporary.save.cancel'; id: string; expectedEpoch: number }
  | { type: 'temporary.save.retire'; id: string; expectedEpoch: number }
  | { type: 'temporary.save.pending' };
export interface TemporaryResults {
  'temporary.save.begin': PromotionReceipt; 'temporary.save.copied': PromotionReceipt;
  'temporary.save.activate': PromotionReceipt; 'temporary.save.cancel': PromotionReceipt;
  'temporary.save.retire': PromotionReceipt; 'temporary.save.pending': PromotionReceipt[];
}
export interface TemporaryStorage { command<C extends TemporaryCommand>(command: C): Promise<TemporaryResults[C['type']]> }
