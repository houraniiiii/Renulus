// SPDX-License-Identifier: MIT
import type { StorageClient } from '../../storage/index.ts';
import type { WorkerChannel } from '../../workers/channel.ts';
import type { Metadata, Rights, Json } from '../knowledge/contracts.ts';
export interface EvidencePassage { id: string; text: string; canonical_url: string; publication_date: string;
  locators: Json[]; metadata: Metadata; rights: Rights; [key: string]: unknown }
export type EvidenceProvider = 'europe-pmc' | 'pubmed' | 'brave' | 'tavily' | 'exa';
/** `official-source` meters the registered-page fetches made by Updates checks. */
export type EvidenceMeter = EvidenceProvider | 'official-source';
export interface EvidenceReservation { id: string; operation_id: string; provider: EvidenceMeter; day: string;
  requests: number; credits: number; started: number; state: 'reserved' | 'settled' | 'uncertain' }
export type EvidenceCommand = { type: 'evidence.reserve'; id: string; operation_id: string; provider: EvidenceMeter;
  day: string; requests: number; credits: number; request_limit: number; credit_limit: number } |
  { type: 'evidence.settle'; id: string; requests_started: number; effect: 'not_sent' | 'response_received' | 'uncertain' } |
  { type: 'evidence.check'; passages: EvidencePassage[] } | { type: 'evidence.current'; stamp: string };
export interface EvidenceResults { 'evidence.reserve': EvidenceReservation; 'evidence.settle': EvidenceReservation;
  'evidence.check': { passages: EvidencePassage[]; stamp: string }; 'evidence.current': { stamp: string } }
export interface EvidenceBudget { max_requests: number; max_credits: number }
export interface EvidenceSearch { query: string; providers: EvidenceProvider[]; budget: EvidenceBudget; operationId: string; signal: AbortSignal }
export interface EvidenceConnection { provider: EvidenceProvider; configured: boolean; enabled: boolean; selected: boolean;
  credential_ref: string | null; credential_revision: number | null; daily_request_limit: number; daily_credit_limit: number }
export interface DatedDiscovery { records: Record<string, unknown>[]; queried_at: string; verification: 'discovery-only';
  passage_evidence: false; usage: { requests: number; credits: number; uncertain: boolean }; error?: string }
export interface EvidenceDomainOptions { storage: Pick<StorageClient, 'command'>;
  worker: { channel: WorkerChannel; maxChunkBytes: number; retention: 'saved' | 'temporary' };
  check(operationId: string, signal: AbortSignal): Promise<void>;
  /** Protected broker HTTP for registered official pages (Updates source/publication checks). */
  http?: ReturnType<typeof import('../../workers/transport.ts').createWorkerHttp>;
  endpoints?: Partial<Record<EvidenceMeter, { host: string; port: number; private_network: boolean; base_url: string }>> }
