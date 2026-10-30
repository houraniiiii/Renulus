// SPDX-License-Identifier: MIT
import type { RecordRow } from '../../storage/contracts.ts';
export type RecoveryRecords = Record<string, RecordRow[]>;
export interface NativeMapping { incomingStore: string; candidateStore: string; sessions: Record<string,string>; messages: Record<string,string> }
export interface RecoverySnapshot { records: RecoveryRecords; frontierDigest: string; schemaHash: string }
export interface RecoveryMerge {
  retained: number; currentOnly: number; added: number; excluded: number; conflicts: number; mappedReferences: number; captureBarriers: number;
  /** Native sessions referenced by incoming rows that survive the current deletion frontier. */
  eligibleNativeSessions: string[];
  /** Native sessions referenced only by incoming rows the frontier excludes. */
  excludedNativeSessions: string[];
}
export interface ReservationRequest { id: string; intentId: string; peakBytes: number; allocatedBytes: number; freeBytes: number; ceilingBytes: number }
export type RecoveryCommand =
  | { type: 'recovery.snapshot' }
  /** Read-only: applies the merge inside a rolled-back savepoint and reports the same counts. */
  | { type: 'recovery.preview'; incoming: RecoverySnapshot; currentFrontierDigest: string }
  | { type: 'recovery.rollback'; incoming: RecoverySnapshot; currentFrontierDigest: string }
  | { type: 'recovery.merge'; incoming: RecoverySnapshot; mapping: NativeMapping; currentFrontierDigest: string }
  | { type: 'recovery.originals'; originals: {table:'knowledge_revisions'|'knowledge_attachment_originals';id:string;handle:string|null}[] }
  | { type: 'storage.reserve'; request: ReservationRequest }
  | { type: 'storage.settle'; id: string; intentId: string; settled: boolean; cleanupDebtBytes: number }
  | { type: 'storage.reservations' };
export interface ReservationStatus { reservedBytes: number; cleanupDebtBytes: number; reservations: number; recovery: {id:string;intentId:string;peakBytes:number}[] }
export interface RecoveryResults {
  'recovery.snapshot': RecoverySnapshot; 'recovery.preview': RecoveryMerge; 'recovery.merge': RecoveryMerge;
  'recovery.originals': {updated:number};
  'recovery.rollback': {compatible:true};
  'storage.reserve': ReservationStatus; 'storage.settle': ReservationStatus; 'storage.reservations': ReservationStatus;
}
export interface RecoveryStorage { command<C extends RecoveryCommand>(command:C):Promise<RecoveryResults[C['type']]> }
