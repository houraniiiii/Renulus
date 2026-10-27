// SPDX-License-Identifier: MIT
import { exact, integer, reject, text } from '../storage/contracts.ts';
import { canonical, digest } from '../storage/schema.ts';
import { PURPOSES, REQUEST_KINDS } from './contracts.ts';
import type { ConfigurationSpec, ConnectionReference, Fence, Inspection, Limits, Purpose, Qualification, Route, Settlement } from './contracts.ts';

export const ALLOWED_MODELS = {
  codex: ['gpt-6.1-sol', 'gpt-6-astra', 'gpt-6-luna'],
  'opencode-go': ['mimo-v2.6-pro', 'deepseek-v4.1-flash'],
} as const;
export const BASE_URLS = { codex: 'https://api.openai.com/v1', 'opencode-go': 'https://opencode.ai/zen/go/v1' } as const;
export const STANDALONE = new Set<Purpose>(['memory-extraction', 'compaction', 'summary', 'test-result-narrative', 'daily_suggestions', 'updates-digest']);
export const GENERATION = new Set<Purpose>(['generated-practice', 'fictional-test', 'test-import']);
export const BATCH_DISPATCHES = { 5: 6, 10: 12, 20: 24 } as const;
export function id(value: unknown): asserts value is string {
  if (typeof value !== 'string' || !/^[A-Za-z0-9_-]{1,128}$/.test(value)) reject('invalid_operation_identity');
}
export function hash(value: unknown): asserts value is string {
  if (typeof value !== 'string' || !/^[a-f0-9]{64}$/.test(value)) reject('invalid_payload_identity');
}
export function strings(value: unknown, max = 128): asserts value is string[] {
  if (!Array.isArray(value) || value.length > max || new Set(value).size !== value.length) reject('configuration_invalid');
  for (const item of value) { text(item, 1, 160); if (!/^[A-Za-z0-9_.:-]+$/.test(item)) reject('invalid_capability'); }
}
export function purpose(value: unknown): asserts value is Purpose {
  if (!(PURPOSES as readonly unknown[]).includes(value)) reject('purpose_not_allowed');
}
export function connection(value: ConnectionReference) {
  exact(value, ['provider', 'credential_reference', 'credential_revision', 'selected_model']);
  if (!Object.hasOwn(ALLOWED_MODELS, value.provider)) reject('provider_not_allowed');
  id(value.credential_reference); integer(value.credential_revision);
  if (value.selected_model !== null && !(ALLOWED_MODELS[value.provider] as readonly string[]).includes(value.selected_model)) reject('model_not_allowed');
}
export function validateFence(value: Fence) {
  exact(value, ['profile_id', 'domain_store_id', 'runtime_store_id', 'authority_epoch', 'process_generation', 'context_epoch', 'deletion_epoch', 'cancellation_epoch']);
  for (const key of ['profile_id', 'domain_store_id', 'runtime_store_id', 'process_generation'] as const) id(value[key]);
  for (const key of ['authority_epoch', 'context_epoch', 'deletion_epoch', 'cancellation_epoch'] as const) integer(value[key]);
}
export function validateSpec(spec: ConfigurationSpec) {
  exact(spec, ['connection', 'registry_hash', 'roles', 'inputs', 'capabilities', 'context', 'attempts', 'children']);
  connection(spec.connection); hash(spec.registry_hash); strings(spec.capabilities);
  if (!Array.isArray(spec.roles) || spec.roles.length > PURPOSES.length || new Set(spec.roles.map(r => r.purpose)).size !== spec.roles.length) reject('configuration_invalid');
  for (const role of spec.roles) {
    exact(role, ['purpose', 'enabled', 'model_id', 'output_tokens', 'dispatch_limit']); purpose(role.purpose);
    if (typeof role.enabled !== 'boolean') reject('configuration_invalid');
    if (role.model_id !== null && !(ALLOWED_MODELS[spec.connection.provider] as readonly string[]).includes(role.model_id)) reject('model_not_allowed');
    integer(role.output_tokens, 1, 32768); if (role.dispatch_limit !== null) integer(role.dispatch_limit, 0, 128);
  }
  if (!Array.isArray(spec.inputs) || spec.inputs.length > 256) reject('configuration_invalid');
  const keys = new Set<string>();
  for (const item of spec.inputs) {
    exact(item, ['kind', 'name', 'sha256']); id(item.name); hash(item.sha256);
    if (!['artifact', 'build', 'role', 'instruction', 'skill', 'tool-schema', 'mcp-identity'].includes(item.kind) || keys.has(item.kind + ':' + item.name)) reject('configuration_invalid');
    keys.add(item.kind + ':' + item.name);
  }
  exact(spec.context, ['requested_window_tokens', 'reserve_tokens']); integer(spec.context.requested_window_tokens, 1, 262144); integer(spec.context.reserve_tokens, 0, 262144);
  exact(spec.attempts, ['foreground_dispatches', 'standalone_dispatches', 'title_dispatches', 'retries', 'retryable_errors']);
  for (const key of ['foreground_dispatches', 'standalone_dispatches', 'title_dispatches'] as const) integer(spec.attempts[key], 0, 128);
  // A new network attempt after failure needs a separate explicit host workflow; native retries remain closed.
  integer(spec.attempts.retries, 0, 0); strings(spec.attempts.retryable_errors);
  if (spec.attempts.retryable_errors.length) reject('retry_not_allowed');
  exact(spec.children, ['max_depth', 'concurrency']); integer(spec.children.max_depth, 0, 1); integer(spec.children.concurrency, 0, 1);
}
export function defaultConfiguration(connectionRef: ConnectionReference, registryHash: string): ConfigurationSpec {
  const spec: ConfigurationSpec = { connection: { ...connectionRef }, registry_hash: registryHash, inputs: [], capabilities: ['text'],
    roles: PURPOSES.map(p => ({ purpose: p, enabled: p !== 'title', model_id: null, output_tokens: 4096,
      dispatch_limit: p === 'title' ? 0 : p === 'memory-extraction' || p === 'test-result-narrative' ? 1 : GENERATION.has(p) ? 32 : STANDALONE.has(p) ? 2 : 8 })),
    context: { requested_window_tokens: 57344, reserve_tokens: 4096 },
    attempts: { foreground_dispatches: 8, standalone_dispatches: 2, title_dispatches: 0, retries: 0, retryable_errors: [] },
    children: { max_depth: 1, concurrency: 1 } };
  validateSpec(spec); return spec;
}
export function resolveRole(spec: ConfigurationSpec, p: Purpose, available: readonly string[], operation: string | null, parent: string | null = null) {
  purpose(p);
  const role = spec.roles.find(r => r.purpose === p);
  if (role?.enabled === false || (!role && p === 'title')) reject('role_disabled');
  const allowed: readonly string[] = ALLOWED_MODELS[spec.connection.provider];
  const model = operation ?? role?.model_id ?? parent ?? spec.connection.selected_model ?? allowed.find(m => available.includes(m));
  if (!model || !allowed.includes(model)) reject('model_not_allowed');
  // Empty means no newly supplied catalogue for an already pinned child/auxiliary route.
  if (!parent && !available.includes(model)) reject('model_unavailable');
  const limit = role?.dispatch_limit ?? (p === 'title' ? spec.attempts.title_dispatches : STANDALONE.has(p) ? spec.attempts.standalone_dispatches : spec.attempts.foreground_dispatches);
  if (!limit) reject('dispatch_budget_exhausted');
  return { model, limit, output: role?.output_tokens ?? 4096 };
}
export function routeFor(ref: ConnectionReference, model: string): Route {
  if (!(ALLOWED_MODELS[ref.provider] as readonly string[]).includes(model)) reject('model_not_allowed');
  return { provider_id: ref.provider, catalog_model_id: model, wire_model_id: model,
    endpoint: BASE_URLS[ref.provider] + (ref.provider === 'codex' ? '/responses' : '/chat/completions'),
    protocol: ref.provider === 'codex' ? 'openai-responses' : 'openai-chat', credential_ref: ref.credential_reference,
    credential_epoch: ref.credential_revision, catalogue_listed: null };
}
export function validateQualification(q: Qualification, route: Route, required: string[]) {
  exact(q, ['id', 'route', 'limits', 'capabilities', 'limits_revision', 'capabilities_revision', 'counter_revision']);
  for (const key of ['id', 'limits_revision', 'capabilities_revision', 'counter_revision'] as const) id(q[key]);
  exact(q.route, ['provider_id', 'catalog_model_id', 'wire_model_id', 'endpoint', 'protocol', 'credential_ref', 'credential_epoch', 'catalogue_listed']);
  if (canonical({ ...q.route, catalogue_listed: null }) !== canonical({ ...route, catalogue_listed: null })) reject('deployment_evidence_mismatch');
  exact(q.limits, ['input_tokens', 'output_tokens', 'window_tokens']);
  for (const value of Object.values(q.limits)) integer(value, 1, 262144);
  if (q.limits.input_tokens > q.limits.window_tokens || q.limits.output_tokens >= q.limits.window_tokens) reject('route_limits_unknown');
  strings(q.capabilities); if (!required.every(c => q.capabilities.includes(c))) reject('deployment_capability_unknown');
}
export function fit(spec: ConfigurationSpec, limits: Limits, input: number, output: number) {
  integer(input); integer(output, 1, 32768);
  if (output > limits.output_tokens || input > limits.input_tokens || input + output + spec.context.reserve_tokens > Math.min(limits.window_tokens, spec.context.requested_window_tokens)) reject('request_does_not_fit');
}
export function inspect(spec: ConfigurationSpec, version: string, epoch: number, value: Inspection) {
  exact(value, ['configuration_version', 'grant_epoch', 'registry_hash', 'loaded_inputs', 'healthy', 'generation_open', 'recovery_open', 'package_acquisition_open', 'mcp_startup_open', 'live_store_writer']);
  if (value.configuration_version !== version || value.grant_epoch !== epoch) reject('candidate_authority_stale');
  if (value.registry_hash !== spec.registry_hash || canonical(value.loaded_inputs) !== canonical(spec.inputs)) reject('registry_mismatch');
  if (value.healthy !== true || ['generation_open', 'recovery_open', 'package_acquisition_open', 'mcp_startup_open', 'live_store_writer'].some(k => value[k as keyof Inspection] !== false)) reject('candidate_not_closed');
}
export function boundary(value: Settlement, version: string | null, epoch: number) {
  exact(value, ['configuration_version', 'grant_epoch', 'admission_closed', 'runtime_stopped', 'domain_settled']);
  if (value.configuration_version !== version || value.grant_epoch !== epoch || value.admission_closed !== true || value.runtime_stopped !== true || value.domain_settled !== true) reject('restart_boundary_required');
}
export function requestKind(value: unknown) { if (!(REQUEST_KINDS as readonly unknown[]).includes(value)) reject('request_kind_not_allowed'); }
export function metadataHash(value: unknown) { return digest(canonical(value)); }
