// SPDX-License-Identifier: MIT

/** Application configuration only. Native OpenCode remains the execution owner. */
export interface PluginToolDeclaration {
  readonly name: string;
  readonly permission: string;
  readonly input_schema_sha256: string;
  readonly output_schema_sha256: string | null;
}

export interface PluginDependency {
  readonly plugin_id: string;
  readonly range: string;
}

export interface PluginMigrationDeclaration {
  readonly id: string;
  readonly sha256: string;
}

export interface PluginPromptDeclaration {
  readonly id: string;
  readonly version: string;
  readonly sha256: string;
}

export interface CapabilityManifest {
  readonly contract: 'renulus-plugin/1';
  readonly plugin_id: string;
  readonly version: string;
  readonly native_id: string;
  readonly artifact_sha256: string;
  readonly cohort_source: string;
  readonly contract_schema: string;
  readonly dependencies: readonly PluginDependency[];
  readonly migrations: readonly PluginMigrationDeclaration[];
  readonly tools: readonly PluginToolDeclaration[];
  readonly prompts: readonly PluginPromptDeclaration[];
  readonly skills: readonly PluginPromptDeclaration[];
  readonly capabilities: readonly string[];
  readonly endpoints: readonly string[];
  readonly retention: 'profile' | 'derived';
  readonly resource_bounds: { readonly max_tool_bytes: number };
  readonly license: string;
  readonly notices: readonly string[];
  readonly derived_namespaces: readonly string[];
}

export interface SelectedPlugin {
  readonly manifest: CapabilityManifest;
  readonly enabled: boolean;
}

export interface NativePluginIdentity {
  readonly id: string;
  readonly source_type: 'local' | 'sdk' | 'builtin' | 'package';
  readonly source_path: string | null;
  readonly status: 'active' | 'failed';
}

export interface NativeToolDefinition {
  readonly type: 'tool';
  readonly name: string;
  readonly description: string;
  readonly inputSchema: unknown;
  readonly outputSchema?: unknown;
}

export interface NativePluginObservation {
  readonly contract: 'renulus-native-plugin-observation/1';
  readonly isolation: 'disposable' | 'selected-profile';
  readonly plugins: readonly NativePluginIdentity[];
  readonly artifact_hashes: Readonly<Record<string, string>>;
  readonly registry: readonly NativeToolDefinition[];
  readonly registry_hash: string;
  readonly quiescent: boolean;
  readonly recovery_held: boolean;
  readonly package_acquisition_closed: boolean;
  readonly effects_denied: boolean;
}

export interface NativeArtifact {
  readonly manifest: CapabilityManifest;
  readonly path: string;
}

export interface NativeInspectionRequest {
  readonly operation_id: string;
  readonly artifacts: readonly NativeArtifact[];
  /** Exact trusted host registrations retained alongside capability artifacts. */
  readonly baseline_tools: readonly NativeToolDefinition[];
}

export interface PluginQuiescence {
  readonly state: 'settled' | 'held';
  readonly active_operations: number;
  readonly pending_permissions: number;
  readonly worker_leases: number;
  readonly uncertain_effects: readonly string[];
}

export interface PluginLifecycleHost {
  inspectCandidate(request: NativeInspectionRequest): Promise<NativePluginObservation>;
  /** Close affected grants immediately; never restore them on candidate failure. */
  narrow(request: { readonly operation_id: string; readonly disabled_native_ids: readonly string[] }): Promise<void>;
  quiesce(request: NativeInspectionRequest & { readonly timeout_ms: number }): Promise<PluginQuiescence>;
  restart(request: NativeInspectionRequest): Promise<NativePluginObservation>;
}

export interface InspectionReceipt {
  readonly contract: 'renulus-plugin-inspection/1';
  readonly operation_id: string;
  readonly requested: readonly SelectedPlugin[];
  readonly artifacts: readonly NativeArtifact[];
  readonly baseline_tools: readonly NativeToolDefinition[];
  readonly observation: NativePluginObservation;
}

export interface PluginLifecycleStatus {
  readonly state: 'empty' | 'staged' | 'ready' | 'held';
  readonly error: string | null;
  readonly requested: readonly SelectedPlugin[];
  readonly requested_operation_id: string | null;
  /** Atomic effective selection, distinct from an inspected/staged request. */
  readonly selected_operation_id: string | null;
  readonly selected: readonly SelectedPlugin[];
  readonly active_operation_id: string | null;
  readonly active: readonly SelectedPlugin[];
  readonly registry_hash: string | null;
  readonly reobserved: boolean;
  readonly failed_operation_id: string | null;
  readonly failed_requested: readonly SelectedPlugin[] | null;
  readonly failed_error: string | null;
}

export interface PluginLifecycleOptions {
  /** A lifecycle-only directory. No canonical database or manifest is written. */
  readonly root: string;
  readonly host: PluginLifecycleHost;
  readonly cohortSource: string;
  /** Host-owned tools, not an allow-prefix for capability registrations. */
  readonly baselineTools?: readonly NativeToolDefinition[];
  readonly knownMigrations?: Readonly<Record<string, string>>;
  /** Synthetic fixtures only; production leaves this false and supplies knownMigrations. */
  readonly allowUnknownMigrations?: boolean;
  readonly quiescenceTimeoutMs?: number;
  readonly operationId?: () => string;
}
