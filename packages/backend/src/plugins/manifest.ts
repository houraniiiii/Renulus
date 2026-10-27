// SPDX-License-Identifier: MIT
import { createHash } from 'node:crypto';
import type { CapabilityManifest, SelectedPlugin } from './types.ts';

export class PluginLifecycleError extends Error {
  readonly code: string;
  constructor(code: string, options?: ErrorOptions) { super(code, options); this.name = 'PluginLifecycleError'; this.code = code; }
}
export function reject(code: string): never { throw new PluginLifecycleError(code); }

export function canonical(value: unknown): string {
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return JSON.stringify(value);
  if (typeof value === 'number') { if (!Number.isFinite(value)) reject('plugin_nonfinite_value'); return JSON.stringify(value); }
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (value !== null && typeof value === 'object' && (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null)) {
    return '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + canonical((value as Record<string, unknown>)[key])).join(',') + '}';
  }
  return reject('plugin_non_json_value');
}
export function sha256(value: string | Uint8Array): string { return createHash('sha256').update(value).digest('hex'); }

const idPattern = /^[a-z][a-z0-9.-]{0,119}$/;
const nativePattern = /^[A-Za-z][A-Za-z0-9._-]{0,119}$/;
const toolPattern = /^[A-Za-z0-9_-]{1,128}$/;
const hashPattern = /^[a-f0-9]{64}$/;
const versionPattern = /^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$/;
function object(value: unknown, keys: readonly string[]): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value) ||
      (Object.getPrototypeOf(value) !== Object.prototype && Object.getPrototypeOf(value) !== null) ||
      JSON.stringify(Object.keys(value).sort()) !== JSON.stringify([...keys].sort())) reject('plugin_manifest_schema');
  return value as Record<string, unknown>;
}
function text(value: unknown, maximum = 512): string {
  if (typeof value !== 'string' || !value.trim() || value.length > maximum || /[\u0000-\u001f]/.test(value)) reject('plugin_manifest_text');
  return value;
}
function hash(value: unknown): string { if (typeof value !== 'string' || !hashPattern.test(value)) reject('plugin_manifest_hash'); return value; }
function id(value: unknown): string { const checked = text(value, 120); if (!idPattern.test(checked)) reject('plugin_id_invalid'); return checked; }
function array(value: unknown): unknown[] { if (!Array.isArray(value) || value.length > 128) reject('plugin_manifest_array'); return value; }
function strings(value: unknown, maximum = 128): string[] {
  const values = array(value).map(item => text(item));
  if (values.length > maximum || new Set(values).size !== values.length) reject('plugin_manifest_duplicate');
  return values;
}

export interface Version { readonly core: readonly number[]; readonly prerelease: readonly (number | string)[]; }
export function parseVersion(value: unknown): Version {
  const checked = text(value, 128);
  if (!versionPattern.test(checked)) reject('plugin_semver_invalid');
  const semantic = checked.split('+', 1)[0]!;
  const separator = semantic.indexOf('-');
  const core = separator < 0 ? semantic : semantic.slice(0, separator);
  const suffix = separator < 0 ? undefined : semantic.slice(separator + 1);
  const numbers = core.split('.').map(Number);
  const prerelease = suffix?.split('.').map(part => {
    if (!/^[0-9]+$/.test(part)) return part;
    if ((part.length > 1 && part.startsWith('0')) || !Number.isSafeInteger(Number(part))) reject('plugin_semver_invalid');
    return Number(part);
  }) ?? [];
  if (numbers.some(part => !Number.isSafeInteger(part))) reject('plugin_semver_invalid');
  return { core: numbers, prerelease };
}
export function compareVersions(left: string, right: string): number {
  const a = parseVersion(left), b = parseVersion(right);
  for (let index = 0; index < 3; index++) if (a.core[index] !== b.core[index]) return a.core[index]! < b.core[index]! ? -1 : 1;
  if (!a.prerelease.length || !b.prerelease.length) return a.prerelease.length ? -1 : b.prerelease.length ? 1 : 0;
  for (let index = 0; index < Math.max(a.prerelease.length, b.prerelease.length); index++) {
    const x = a.prerelease[index], y = b.prerelease[index];
    if (x === undefined || y === undefined) return x === undefined ? -1 : 1;
    if (x === y) continue;
    if (typeof x === 'number' && typeof y === 'number') return x < y ? -1 : 1;
    if (typeof x === 'number' || typeof y === 'number') return typeof x === 'number' ? -1 : 1;
    return x < y ? -1 : 1;
  }
  return 0;
}

/** Deterministic dependency subset; no package resolver or registry lookup. */
export function satisfies(version: string, range: string): boolean {
  parseVersion(version);
  if (range === '*') return parseVersion(version).prerelease.length === 0;
  const alternatives = range.split('||').map(item => item.trim());
  if (alternatives.some(item => !item)) reject('plugin_dependency_range');
  const groups = alternatives.map(alternative => alternative.split(/\s+/).map(comparator => {
    const match = /^(\^|~|>=|<=|>|<|=)?([0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?)$/.exec(comparator);
    if (!match) reject('plugin_dependency_range');
    const [, operator = '=', target] = match;
    parseVersion(target!);
    return { operator, target: target! };
  }));
  return groups.some(group => {
    const actual = parseVersion(version);
    if (actual.prerelease.length && !group.some(({ target }) => {
      const base = parseVersion(target);
      return base.prerelease.length > 0 && base.core.every((value, index) => value === actual.core[index]);
    })) return false;
    return group.every(({ operator, target }) => {
    const comparison = compareVersions(version, target!);
    if (operator === '>') return comparison > 0;
    if (operator === '>=') return comparison >= 0;
    if (operator === '<') return comparison < 0;
    if (operator === '<=') return comparison <= 0;
    if (operator === '^') {
      const base = parseVersion(target!), upper = [...base.core];
      const index = upper[0]! > 0 ? 0 : upper[1]! > 0 ? 1 : 2;
      upper[index]!++; for (let i = index + 1; i < 3; i++) upper[i] = 0;
      return comparison >= 0 && compareVersions(version, upper.join('.')) < 0;
    }
    if (operator === '~') {
      const base = parseVersion(target!);
      return comparison >= 0 && compareVersions(version, `${base.core[0]}.${base.core[1]! + 1}.0`) < 0;
    }
    return comparison === 0;
    });
  });
}

export function validateManifest(value: unknown, cohortSource: string,
    knownMigrations: Readonly<Record<string, string>> = {}, allowUnknownMigrations = false): CapabilityManifest {
  const input = object(value, ['contract', 'plugin_id', 'version', 'native_id', 'artifact_sha256', 'cohort_source',
    'contract_schema', 'dependencies', 'migrations', 'tools', 'prompts', 'skills', 'capabilities', 'endpoints',
    'retention', 'resource_bounds', 'license', 'notices', 'derived_namespaces']);
  if (input.contract !== 'renulus-plugin/1' || input.cohort_source !== cohortSource) reject('plugin_cohort_incompatible');
  if (input.contract_schema !== 'renulus-capabilities/1') reject('plugin_schema_incompatible');
  const nativeId = text(input.native_id, 120); if (!nativePattern.test(nativeId)) reject('plugin_native_id_invalid');
  const dependencies = array(input.dependencies).map(item => {
    const dependency = object(item, ['plugin_id', 'range']);
    return { plugin_id: id(dependency.plugin_id), range: text(dependency.range, 256) };
  });
  if (new Set(dependencies.map(item => item.plugin_id)).size !== dependencies.length) reject('plugin_dependency_duplicate');
  const migrations = array(input.migrations).map(item => {
    const migration = object(item, ['id', 'sha256']);
    const migrationId = text(migration.id, 160), digest = hash(migration.sha256);
    if (!allowUnknownMigrations && (!Object.hasOwn(knownMigrations, migrationId) || knownMigrations[migrationId] !== digest))
      reject('plugin_migration_unknown');
    return { id: migrationId, sha256: digest };
  });
  if (new Set(migrations.map(item => item.id)).size !== migrations.length) reject('plugin_migration_duplicate');
  const tools = array(input.tools).map(item => {
    const tool = object(item, ['name', 'permission', 'input_schema_sha256', 'output_schema_sha256']);
    const name = text(tool.name, 128), permission = text(tool.permission, 160);
    if (!toolPattern.test(name) || !/^[a-z][a-z0-9_.*-]{0,159}$/.test(permission)) reject('plugin_tool_schema');
    if (tool.output_schema_sha256 !== null && typeof tool.output_schema_sha256 !== 'string') reject('plugin_manifest_hash');
    return { name, permission, input_schema_sha256: hash(tool.input_schema_sha256),
      output_schema_sha256: tool.output_schema_sha256 === null ? null : hash(tool.output_schema_sha256) };
  });
  if (new Set(tools.map(item => item.name)).size !== tools.length) reject('plugin_tool_duplicate');
  const declarations = (items: unknown, kind: string) => array(items).map(item => {
    const declaration = object(item, ['id', 'version', 'sha256']);
    return { id: text(declaration.id, 160), version: text(declaration.version, 128), sha256: hash(declaration.sha256), kind };
  });
  const prompts = declarations(input.prompts, 'prompt'), skills = declarations(input.skills, 'skill');
  // The BF01 native tool registry has no supported prompt/skill identity seam.
  if (prompts.length || skills.length) reject('plugin_prompt_skill_observation_unsupported');
  if (array(input.endpoints).length) reject('plugin_endpoints_require_bf03');
  if (!['profile', 'derived'].includes(String(input.retention))) reject('plugin_retention_invalid');
  const bounds = object(input.resource_bounds, ['max_tool_bytes']);
  if (!Number.isSafeInteger(bounds.max_tool_bytes) || Number(bounds.max_tool_bytes) < 1 || Number(bounds.max_tool_bytes) > 64 * 1024 * 1024)
    reject('plugin_resource_bounds');
  const manifest: CapabilityManifest = {
    contract: 'renulus-plugin/1', plugin_id: id(input.plugin_id), version: text(input.version, 128),
    native_id: nativeId, artifact_sha256: hash(input.artifact_sha256), cohort_source: cohortSource,
    contract_schema: 'renulus-capabilities/1', dependencies, migrations, tools, prompts: [], skills: [],
    capabilities: strings(input.capabilities), endpoints: [], retention: input.retention as 'profile' | 'derived',
    resource_bounds: { max_tool_bytes: Number(bounds.max_tool_bytes) }, license: text(input.license, 160),
    notices: strings(input.notices).map(item => {
      if (!/^(?:[A-Za-z0-9_.-]+\/)*[A-Za-z0-9_.-]+$/.test(item) || item.split('/').some(part => part === '.' || part === '..'))
        reject('plugin_notice_path');
      return item;
    }),
    derived_namespaces: strings(input.derived_namespaces).map(item => { if (!idPattern.test(item)) reject('plugin_namespace_invalid'); return item; }),
  };
  parseVersion(manifest.version);
  if (dependencies.some(item => item.plugin_id === manifest.plugin_id)) reject('plugin_dependency_cycle');
  for (const dependency of dependencies) satisfies('1.0.0', dependency.range); // syntax only; closure is checked below
  return manifest;
}

export function enabledPlugins(selection: readonly SelectedPlugin[]): readonly SelectedPlugin[] {
  return selection.filter(item => item.enabled);
}

/** A validated closed graph has one deterministic dependency-first load order. */
export function activationOrder(selection: readonly SelectedPlugin[]): readonly SelectedPlugin[] {
  const enabled = new Map(enabledPlugins(selection).map(item => [item.manifest.plugin_id, item]));
  const result: SelectedPlugin[] = [], visited = new Set<string>();
  const visit = (id: string) => {
    if (visited.has(id)) return;
    visited.add(id);
    const item = enabled.get(id);
    if (!item) reject('plugin_dependency_missing');
    for (const dependency of [...item.manifest.dependencies].sort((a, b) => a.plugin_id < b.plugin_id ? -1 : 1)) visit(dependency.plugin_id);
    result.push(item);
  };
  for (const id of [...enabled.keys()].sort()) visit(id);
  return result;
}

export function validateSelection(selection: readonly SelectedPlugin[], cohortSource: string,
    knownMigrations: Readonly<Record<string, string>> = {}, allowUnknownMigrations = false): void {
  if (!Array.isArray(selection) || selection.length > 128 || selection.some(item => !item || typeof item !== 'object' ||
      Object.keys(item).sort().join(',') !== 'enabled,manifest')) reject('plugin_selection_schema');
  const manifests = selection.map(item => validateManifest(item.manifest, cohortSource, knownMigrations, allowUnknownMigrations));
  if (new Set(manifests.map(item => item.plugin_id)).size !== selection.length) reject('plugin_id_duplicate');
  if (selection.some(item => typeof item.enabled !== 'boolean')) reject('plugin_enablement_invalid');
  const active = manifests.filter((_, index) => selection[index]!.enabled);
  if (new Set(active.map(item => item.native_id)).size !== active.length) reject('plugin_native_id_duplicate');
  const tools = active.flatMap(item => item.tools.map(tool => tool.name));
  if (new Set(tools).size !== tools.length) reject('plugin_tool_duplicate');
  const namespaces = active.flatMap(item => item.derived_namespaces);
  if (new Set(namespaces).size !== namespaces.length) reject('plugin_namespace_duplicate');
  const versions = new Map(active.map(item => [item.plugin_id, item.version]));
  for (const plugin of active) for (const dependency of plugin.dependencies) {
    const version = versions.get(dependency.plugin_id);
    if (!version) reject('plugin_dependency_missing');
    if (!satisfies(version, dependency.range)) reject('plugin_dependency_version');
  }
  const visiting = new Set<string>(), visited = new Set<string>();
  const visit = (pluginId: string) => {
    if (visiting.has(pluginId)) reject('plugin_dependency_cycle');
    if (visited.has(pluginId)) return;
    visiting.add(pluginId);
    const plugin = active.find(item => item.plugin_id === pluginId);
    for (const dependency of plugin?.dependencies ?? []) visit(dependency.plugin_id);
    visiting.delete(pluginId); visited.add(pluginId);
  };
  for (const plugin of active) visit(plugin.plugin_id);
}
