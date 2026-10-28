// SPDX-License-Identifier: MIT
/** One completed user/assistant exchange of the root session, by its fresh saved identities. */
export interface PromotedExchange { runId: string; inputId: string; messageIds: string[]; sha256: string }
export interface PromotionPlan {
  id: string; threadId: string; title: string; profileId: string; storeId: string; exchanges: PromotedExchange[];
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
  | { type: 'temporary.save.pending' }
  | { type: 'temporary.save.committed'; idempotencyKey: string };
export interface TemporaryResults {
  'temporary.save.begin': PromotionReceipt; 'temporary.save.copied': PromotionReceipt;
  'temporary.save.activate': PromotionReceipt; 'temporary.save.cancel': PromotionReceipt;
  'temporary.save.retire': PromotionReceipt; 'temporary.save.pending': PromotionReceipt[];
  'temporary.save.committed': PromotionReceipt | null;
}
export interface TemporaryStorage { command<C extends TemporaryCommand>(command: C): Promise<TemporaryResults[C['type']]> }
