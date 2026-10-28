// SPDX-License-Identifier: MIT
/** BF01 target contracts. Only the trusted host submits these to the canonical writer. */
export const PURPOSES = ['explain', 'case-discuss', 'case-image-discuss', 'evidence-review',
  'generated-practice', 'fictional-test', 'test-import', 'memory-extraction', 'compaction',
  'summary', 'test-result-narrative', 'daily_suggestions', 'updates-digest', 'title'] as const;
export type Purpose = typeof PURPOSES[number];
export const REQUEST_KINDS = ['primary', 'root', 'child', 'tool-continuation', 'continuation',
  'generate', 'title', 'summary', 'compaction', 'summary-repair', 'repair', 'recovery', 'scheduled',
  'transport-fallback'] as const;
export type RequestKind = typeof REQUEST_KINDS[number];
export type Provider = 'codex' | 'opencode-go';
export interface ConnectionReference {
  provider: Provider; credential_reference: string; credential_revision: number; selected_model: string | null;
}
export interface RolePolicy { purpose: Purpose; enabled: boolean; model_id: string | null; output_tokens: number; dispatch_limit: number | null }
export interface InputHash { kind: 'artifact' | 'build' | 'role' | 'instruction' | 'skill' | 'tool-schema' | 'mcp-identity'; name: string; sha256: string }
/** Same canonical JSON shape as Python ConfigurationSpec, including credential references only. */
export interface ConfigurationSpec {
  connection: ConnectionReference; registry_hash: string; roles: RolePolicy[]; inputs: InputHash[]; capabilities: string[];
  context: { requested_window_tokens: number; reserve_tokens: number; requested_decimal_tokens?: number };
  attempts: { foreground_dispatches: number; standalone_dispatches: number; title_dispatches: number;
    retries: number; retryable_errors: ('transport_unavailable' | 'summary_invalid')[] };
  children: { max_depth: number; concurrency: number };
}
export interface Fence {
  profile_id: string; domain_store_id: string; runtime_store_id: string; authority_epoch: number; process_generation: string;
  context_epoch: number; deletion_epoch: number; cancellation_epoch: number;
}
export interface Route {
  provider_id: Provider; catalog_model_id: string; wire_model_id: string; endpoint: string;
  protocol: 'openai-responses' | 'openai-chat'; credential_ref: string; credential_epoch: number; catalogue_listed: boolean | null;
}
export interface Limits { input_tokens: number; output_tokens: number; window_tokens: number }
export interface Qualification {
  id: string; route: Route; limits: Limits; capabilities: string[];
  limits_revision: string; capabilities_revision: string; counter_revision: string;
}
export interface Inspection {
  configuration_version: string; grant_epoch: number; registry_hash: string; loaded_inputs: InputHash[];
  healthy: boolean; generation_open: boolean; recovery_open: boolean; package_acquisition_open: boolean;
  mcp_startup_open: boolean; live_store_writer: boolean;
}
/** Produced after real settlement by the host, never inferred from canonical run pins. */
export interface Settlement {
  configuration_version: string; grant_epoch: number; admission_closed: boolean; runtime_stopped: boolean; domain_settled: boolean;
}
export interface Run {
  run_id: string; version: string; root_id: string; parent_id: string | null; purpose: Purpose; state: 'active' | 'settled';
  dispatch_limit: number; output_tokens: number; effective_capabilities: string[]; route: Route; fence: Fence; batch_size: 5 | 10 | 20 | null;
}
export interface RequestProof {
  qualification: Qualification; payload_hash: string; wire_sha256: string; input_manifest_sha256: string; body_bytes: number;
  input_tokens: number; output_tokens: number;
}
export interface Permit {
  permit_id: string; run_id: string; root_id: string; step_id: string; payload_hash: string; request_kind: RequestKind;
  dispatch_purpose: Purpose; grant_epoch: number; output_tokens: number; required_capabilities: string[];
  state: 'reserved' | 'dispatched' | 'confirmed' | 'failed' | 'uncertain' | 'cancelled_before_send';
  result_reference: string | null; failure_code: string | null; dispatch_allowed: boolean;
}
export type DispatchCommand =
  | { type: 'dispatch.snapshot' }
  | { type: 'dispatch.configuration'; version: string }
  | { type: 'dispatch.stage'; spec: ConfigurationSpec; expectedEffective: string | null; expectedRequested: string | null; grantEpoch: number }
  | { type: 'dispatch.inspect'; inspection: Inspection }
  | { type: 'dispatch.close'; version: string; expectedEffective: string | null; grantEpoch: number }
  | { type: 'dispatch.activate'; version: string; expectedEffective: string | null; settlement: Settlement }
  | { type: 'dispatch.open'; inspection: Inspection }
  | { type: 'dispatch.begin'; runId: string; purpose: Purpose; expectedVersion: string; capabilities: string[];
      availableModels: string[]; operationModel: string | null; fence: Fence; batchSize: 5 | 10 | 20 | null }
  | { type: 'dispatch.child'; runId: string; parentId: string; purpose: Purpose; capabilities: string[]; operationModel: string | null; fence: Fence }
  | { type: 'dispatch.run'; runId: string }
  | { type: 'dispatch.current'; runId: string; fence: Fence; requiredCapabilities: string[]; permitId: string | null }
  | { type: 'dispatch.reserve'; runId: string; stepId: string; requestKind: RequestKind; continuationOf: string | null;
      requiredCapabilities: string[]; fence: Fence; proof: RequestProof }
  | { type: 'dispatch.admit'; permitId: string; fence: Fence; proof: RequestProof }
  | { type: 'dispatch.permit'; permitId: string }
  | { type: 'dispatch.complete'; permitId: string; outcome: 'confirmed' | 'failed' | 'uncertain' | 'cancelled_before_send';
      resultReference: string | null; failureCode: string | null }
  | { type: 'dispatch.revoke'; capability: string }
  | { type: 'dispatch.settle'; runId: string; settlement: Settlement }
  | { type: 'dispatch.reconcile'; settlement: Settlement };
export interface Snapshot {
  requested: string | null; effective: string | null; previous: string | null; activating: string | null;
  failed: string | null; failure_code: string | null; admission_open: boolean; grant_epoch: number; revoked: string[];
}
export interface DispatchResults {
  'dispatch.configuration': ConfigurationSpec;
  'dispatch.snapshot': Snapshot; 'dispatch.stage': { version: string }; 'dispatch.inspect': { ready: boolean };
  'dispatch.close': Snapshot; 'dispatch.activate': Snapshot; 'dispatch.open': Snapshot;
  'dispatch.begin': Run; 'dispatch.child': Run; 'dispatch.run': Run; 'dispatch.current': Run;
  'dispatch.reserve': Permit; 'dispatch.admit': Permit; 'dispatch.permit': Permit; 'dispatch.complete': Permit;
  'dispatch.revoke': { epoch: number }; 'dispatch.settle': Run; 'dispatch.reconcile': Snapshot;
}
