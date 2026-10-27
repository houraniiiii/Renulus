// SPDX-License-Identifier: MIT
import type { Fence } from '../../dispatch/contracts.ts';

/** Minted by the host from the admitted native call. Never decoded from tool arguments. */
export interface CapabilityEnvelope {
  run_id: string; root_id: string; session_id: string; call_id: string;
  configuration: string; grant_epoch: number; fence: Fence;
  retention: 'saved' | 'temporary'; mode: 'doctor' | 'developer'; depth: number;
}
export interface CapabilityGrant {
  actions: string[]; roots: { path: string; read: boolean; write: boolean; execute: boolean }[];
  endpoints: { host: string; port: number; private_network: boolean }[];
  skills: string[]; max_bytes: number; expires_at_ms: number;
}
export interface CapabilityLease {
  id: string; envelope: CapabilityEnvelope; action: string; payload_sha256: string;
  grant: CapabilityGrant; state: 'admitted' | 'closed' | 'settled' | 'uncertain';
  used_bytes: number; effect_reference: string | null;
}
export type CapabilityCommand =
  | { type: 'capability.admit'; id: string; envelope: CapabilityEnvelope; action: string; payload_sha256: string; grant: CapabilityGrant }
  | { type: 'capability.current'; id: string; envelope: CapabilityEnvelope; bytes: number; now_ms: number }
  | { type: 'capability.close'; root_id: string }
  | { type: 'capability.settle'; id: string; outcome: 'settled' | 'uncertain'; effect_reference: string | null }
  | { type: 'capability.pending'; root_id: string };
export interface CapabilityResults {
  'capability.admit': CapabilityLease; 'capability.current': CapabilityLease;
  'capability.close': { closed: number }; 'capability.settle': CapabilityLease;
  'capability.pending': CapabilityLease[];
}
export interface CapabilityStorage {
  execute<C extends CapabilityCommand>(command: C): Promise<CapabilityResults[C['type']]>;
}
export interface HttpPlan {
  lease_id: string; url: string; method: string; headers: Record<string, string>;
  body_base64: string; body_sha256: string; max_response_bytes: number;
  /** Worker-only credential lookup. No credential value may cross this port. */
  credential_ref?: string; credential_revision?: number;
}
export interface HttpStream {
  status: number; headers: Record<string, string>;
  read(signal: AbortSignal): Promise<Uint8Array | null>;
  close(): Promise<void>;
}
export interface CapabilityTransport {
  http(plan: HttpPlan, signal: AbortSignal): Promise<HttpStream>;
  tunnelOpen(lease: CapabilityLease, target: { host: string; port: number }, signal: AbortSignal): Promise<string>;
  tunnelRead(id: string, signal: AbortSignal): Promise<{ data: Uint8Array; eof: boolean }>;
  tunnelWrite(id: string, data: Uint8Array, end: boolean, signal: AbortSignal): Promise<void>;
  tunnelClose(id: string): Promise<void>;
}
export interface OwnedBrowserContext {
  /** Close includes pending actions, proxy connections and the isolated context. */
  close(): Promise<void>;
  identity: string; proxy_only: true; quic_disabled: true; webrtc_disabled: true;
}
export interface BrowserAttachment {
  connection_id: string; client_generation: string; context: OwnedBrowserContext;
  removeNativeAllow(): Promise<void>;
  cancelPending(): Promise<void>;
}
