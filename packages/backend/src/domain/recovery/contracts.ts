// SPDX-License-Identifier: MIT
import type { RecordRow } from '../../storage/contracts.ts';
export type RecoveryRecords = Record<string, RecordRow[]>;
export interface NativeMapping { incomingStore: string; candidateStore: string; sessions: Record<string,string>; messages: Record<string,string> }
export interface RecoverySnapshot { records: RecoveryRecords; frontierDigest: string; schemaHash: string }
export interface RecoveryMerge { retained: number; currentOnly: number; added: number; excluded: number; conflicts: number; mappedReferences: number; captureBarriers: number }
export interface ReservationRequest { id: string; intentId: string; peakBytes: number; allocatedBytes: number; freeBytes: number; ceilingBytes: number }
export type RecoveryCommand =
  | { type: 'recovery.snapshot' }
  | { type: 'recovery.merge'; incoming: RecoverySnapshot; mapping: NativeMapping; currentFrontierDigest: string }
  | { type: 'storage.reserve'; request: ReservationRequest }
  | { type: 'storage.settle'; id: string; intentId: string; settled: boolean; cleanupDebtBytes: number }
  | { type: 'storage.reservations' };
export interface ReservationStatus { reservedBytes: number; cleanupDebtBytes: number; reservations: number }
export interface RecoveryResults {
  'recovery.snapshot': RecoverySnapshot; 'recovery.merge': RecoveryMerge;
  'storage.reserve': ReservationStatus; 'storage.settle': ReservationStatus; 'storage.reservations': ReservationStatus;
}
export interface RecoveryStorage { command<C extends RecoveryCommand>(command:C):Promise<RecoveryResults[C['type']]> }
