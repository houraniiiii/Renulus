// SPDX-License-Identifier: MIT
import { lstat, readFile, realpath } from 'node:fs/promises';
import path from 'node:path';
import { activationOrder, canonical, PluginLifecycleError, reject, sha256 } from './manifest.ts';
import type { CapabilityManifest, InspectionReceipt, NativeArtifact, NativePluginObservation, NativeToolDefinition,
  SelectedPlugin } from './types.ts';

const identifier = /^[a-z][a-z0-9.-]{0,119}$/;
const nativeId = /^[A-Za-z][A-Za-z0-9._-]{0,119}$/;
const digest = /^[a-f0-9]{64}$/;
const relativePath = /^(?:[A-Za-z0-9_.-]+\/)*[A-Za-z0-9_.-]+$/;
function same(left: string, right: string): boolean {
  const a = path.resolve(left), b = path.resolve(right);
  return process.platform === 'win32' ? a.toLowerCase() === b.toLowerCase() : a === b;
}
async function realIsSelf(file: string): Promise<void> {
  const resolved = path.resolve(file);
  let ancestor = resolved;
  for (;;) {
    try {
      if (!same(await realpath(ancestor), ancestor)) reject('plugin_artifact_alias');
      return;
    } catch (error) {
      if (error instanceof PluginLifecycleError) throw error;
      if ((error as NodeJS.ErrnoException).code !== 'ENOENT' || ancestor === path.dirname(ancestor)) reject('plugin_artifact_unreadable');
      ancestor = path.dirname(ancestor);
    }
  }
}

export async function readArtifact(root: string, manifest: CapabilityManifest): Promise<NativeArtifact> {
  const directory = path.resolve(root, 'artifacts', manifest.plugin_id, manifest.version + '-' + manifest.artifact_sha256);
  const file = path.join(directory, 'server.js');
  const license = path.join(directory, 'LICENSE');
  if (!same(path.dirname(file), directory) || !(manifest.native_id.startsWith('renulus-'))) reject('plugin_artifact_path');
  await realIsSelf(root);
  for (const candidate of [directory, file, license]) await realIsSelf(candidate);
  const artifactStat = await lstat(file).catch(() => reject('plugin_artifact_unreadable'));
  if (!artifactStat.isFile() || artifactStat.nlink !== 1 || artifactStat.size < 1 || artifactStat.size > 1024 * 1024)
    reject('plugin_artifact_invalid');
  const bytes = await readFile(file);
  if (sha256(bytes) !== manifest.artifact_sha256) reject('plugin_artifact_integrity');
  // Reviewed license/notices are explicit, never ambient user documents.
  for (const file of [license, ...manifest.notices.map(item => path.join(directory, item))]) {
    if (!relativePath.test(path.relative(directory, file).replaceAll('\\', '/'))) reject('plugin_notice_path');
    await realIsSelf(file);
    const stat = await lstat(file).catch(() => reject('plugin_license_missing'));
    if (!stat.isFile() || stat.nlink !== 1 || stat.size < 1 || stat.size > 1024 * 1024) reject('plugin_license_missing');
    if (!(await readFile(file, 'utf8')).trim()) reject('plugin_license_missing');
  }
  return Object.freeze({ manifest: structuredClone(manifest), path: file });
}

export async function verifyArtifactHashes(artifacts: readonly NativeArtifact[]): Promise<Record<string, string>> {
  const result: Record<string, string> = {};
  for (const artifact of artifacts) {
    await realIsSelf(artifact.path);
    const stat = await lstat(artifact.path).catch(() => reject('plugin_artifact_unreadable'));
    if (!stat.isFile() || stat.nlink !== 1 || stat.size < 1 || stat.size > 1024 * 1024) reject('plugin_artifact_invalid');
    const actual = sha256(await readFile(artifact.path));
    if (actual !== artifact.manifest.artifact_sha256) reject('plugin_artifact_integrity');
    result[artifact.manifest.native_id] = actual;
  }
  return result;
}

function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}
function registry(value: unknown): NativeToolDefinition[] {
  if (!Array.isArray(value) || value.length > 256) reject('plugin_registry_schema');
  return value.map(item => {
    if (!object(item) || item.type !== 'tool' || typeof item.name !== 'string' || !/^[A-Za-z0-9_-]{1,160}$/.test(item.name) ||
        typeof item.description !== 'string' || !Object.hasOwn(item, 'inputSchema') ||
        JSON.stringify(Object.keys(item).sort()) !== JSON.stringify(['description', 'inputSchema', 'name', 'type', ...(Object.hasOwn(item, 'outputSchema') ? ['outputSchema'] : [])].sort()))
      reject('plugin_registry_schema');
    try { canonical(item.inputSchema); if (Object.hasOwn(item, 'outputSchema')) canonical(item.outputSchema); }
    catch { reject('plugin_registry_schema'); }
    return structuredClone(item) as unknown as NativeToolDefinition;
  });
}

/** Verify observations, including the native plugin inventory and final transformed tools. */
export function validateObservation(observation: NativePluginObservation, request: {
    readonly artifacts: readonly NativeArtifact[];
    readonly baseline_tools: readonly NativeToolDefinition[];
  },
    isolation: 'disposable' | 'selected-profile', effectCheck: boolean): Record<string, unknown> {
  if (!object(observation) || observation.contract !== 'renulus-native-plugin-observation/1' ||
      observation.isolation !== isolation || !observation.quiescent || !observation.recovery_held ||
      !observation.package_acquisition_closed || (effectCheck && !observation.effects_denied))
    reject('plugin_native_guards_incomplete');
  const requested = new Map(request.artifacts.map(item => [item.manifest.native_id, item]));
  const plugins: readonly unknown[] = observation.plugins;
  if (!Array.isArray(plugins) || plugins.length > 256 || !object(observation.artifact_hashes)) reject('plugin_native_observation_schema');
  const present = new Set<string>();
  for (const plugin of plugins) {
    if (!object(plugin) || typeof plugin.id !== 'string' || !nativeId.test(plugin.id) ||
        typeof plugin.source_type !== 'string' || !['local', 'sdk', 'builtin', 'package'].includes(plugin.source_type) ||
        typeof plugin.status !== 'string' || !['active', 'failed'].includes(plugin.status) ||
        (plugin.source_path !== null && typeof plugin.source_path !== 'string'))
      reject('plugin_native_observation_schema');
    if (plugin.status !== 'active') reject('plugin_candidate_failed');
    const expected = requested.get(plugin.id);
    if (expected) {
      if (present.has(plugin.id)) reject('plugin_native_id_duplicate');
      present.add(plugin.id);
      if (plugin.source_type !== 'local' || plugin.source_path === null || !same(plugin.source_path, expected.path) ||
          observation.artifact_hashes[plugin.id] !== expected.manifest.artifact_sha256)
        reject('plugin_loaded_artifact_mismatch');
    } else if (plugin.source_type === 'local') reject('plugin_unrequested_local_plugin');
    else if (plugin.source_type === 'package') reject('plugin_unrequested_package_plugin');
  }
  for (const [id, artifact] of requested) {
    if (!present.has(id)) reject('plugin_candidate_missing');
    if (observation.artifact_hashes[id] !== artifact.manifest.artifact_sha256) reject('plugin_loaded_artifact_mismatch');
  }
  if (Object.entries(observation.artifact_hashes).some(([id, value]) => !requested.has(id) || typeof value !== 'string' || !digest.test(value)))
    reject('plugin_loaded_artifact_mismatch');
  const tools = registry(observation.registry);
  if (observation.registry_hash !== sha256(canonical(tools))) reject('plugin_registry_hash_mismatch');
  if (new Set(tools.map(item => item.name)).size !== tools.length) reject('plugin_tool_duplicate');
  const byName = new Map(tools.map(item => [item.name, item]));
  const declarations = new Map<string, CapabilityManifest['tools'][number]>();
  for (const { manifest } of request.artifacts) for (const tool of manifest.tools) {
    if (declarations.has(tool.name)) reject('plugin_tool_duplicate');
    declarations.set(tool.name, tool);
  }
  const baseline = registry(request.baseline_tools);
  const baselineNames = new Set<string>();
  for (const expected of baseline) {
    if (baselineNames.has(expected.name) || declarations.has(expected.name)) reject('plugin_tool_duplicate');
    baselineNames.add(expected.name);
    const actual = byName.get(expected.name);
    if (!actual || canonical(actual) !== canonical(expected)) reject('plugin_baseline_registry_mismatch');
    byName.delete(expected.name);
  }
  for (const [name, tool] of declarations) {
    const actual = byName.get(name);
    if (!actual) reject('plugin_tool_missing');
    if (sha256(canonical(actual.inputSchema)) !== tool.input_schema_sha256 ||
        (tool.output_schema_sha256 === null ? Object.hasOwn(actual, 'outputSchema') :
          !Object.hasOwn(actual, 'outputSchema') || sha256(canonical(actual.outputSchema)) !== tool.output_schema_sha256))
      reject('plugin_tool_schema_mismatch');
    byName.delete(name);
  }
  if (byName.size) reject('plugin_registry_unexpected_tool');
  for (const { manifest } of request.artifacts) {
    const owned = tools.filter(tool => manifest.tools.some(declaration => declaration.name === tool.name));
    if (Buffer.byteLength(canonical(owned)) > manifest.resource_bounds.max_tool_bytes) reject('plugin_resource_bounds');
  }
  return { registry: tools, registryHash: observation.registry_hash };
}

export function validateReceipt(receipt: InspectionReceipt, selection: readonly SelectedPlugin[],
    baselineTools: readonly NativeToolDefinition[]): void {
  if (receipt.contract !== 'renulus-plugin-inspection/1' || !identifier.test(receipt.operation_id) ||
      canonical(receipt.requested) !== canonical(selection) ||
      canonical(receipt.baseline_tools) !== canonical(baselineTools) ||
      canonical(receipt.artifacts.map(item => item.manifest)) !== canonical(activationOrder(selection).map(item => item.manifest)))
    reject('plugin_candidate_receipt_mismatch');
}
