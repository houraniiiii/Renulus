// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import test from 'node:test';
import { mkdtemp, mkdir, writeFile, link } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { activationOrder, canonical, compareVersions, satisfies, sha256, validateManifest, validateSelection } from '../src/plugins/manifest.ts';
import { readArtifact, validateObservation } from '../src/plugins/validate.ts';

const cohort = 'synthetic-reviewed-cohort';
const schema = { type: 'object', properties: {}, additionalProperties: false };
const bytes = 'export default { id: "renulus-synthetic", effect: context => context.tool.transform(() => {}) };\n';
function manifest(id = 'synthetic.base') {
  return { contract: 'renulus-plugin/1', plugin_id: id, version: '1.0.0', native_id: 'renulus-' + id,
    artifact_sha256: sha256(bytes), cohort_source: cohort, contract_schema: 'renulus-capabilities/1',
    dependencies: [], migrations: [], tools: [], prompts: [], skills: [], capabilities: [], endpoints: [], retention: 'derived',
    resource_bounds: { max_tool_bytes: 4096 }, license: 'MIT', notices: [], derived_namespaces: [] };
}

test('dependency versions compare numeric prereleases and validate all comparator alternatives', () => {
  assert.ok(compareVersions('1.0.0-rc.10', '1.0.0-rc.2') > 0);
  assert.ok(compareVersions('1.0.0-rc-beta.10', '1.0.0-rc-alpha.10') > 0);
  assert.ok(compareVersions('1.0.0', '1.0.0-rc.10') > 0);
  assert.equal(compareVersions('1.0.0+build.2', '1.0.0+build.10'), 0);
  assert.equal(satisfies('0.2.9', '^0.2.1'), true);
  assert.equal(satisfies('0.3.0', '^0.2.1'), false);
  assert.equal(satisfies('1.0.0-rc.2', '^1.0.0'), false);
  assert.equal(satisfies('1.0.0-rc.10', '>=1.0.0-rc.2 <1.0.0'), true);
  assert.throws(() => satisfies('1.0.0', '>=0.0.0 || invalid'), /plugin_dependency_range/);
  assert.throws(() => compareVersions('1.0.0-01', '1.0.0'), /plugin_semver_invalid/);
  assert.throws(() => compareVersions('9007199254740992.0.0', '1.0.0'), /plugin_semver_invalid/);
});

test('closed manifests reject incompatible cohort/schema, unknown migration, notices traversal and later-wave surfaces', () => {
  const valid = manifest();
  assert.deepEqual(validateManifest(valid, cohort), valid);
  for (const [change, code] of [
    [{ cohort_source: 'another-cohort' }, 'plugin_cohort_incompatible'],
    [{ contract_schema: 'unknown/2' }, 'plugin_schema_incompatible'],
    [{ migrations: [{ id: 'unregistered', sha256: 'a'.repeat(64) }] }, 'plugin_migration_unknown'],
    [{ notices: ['../LICENSE'] }, 'plugin_notice_path'],
    [{ notices: ['nested/../LICENSE'] }, 'plugin_notice_path'],
    [{ license: '' }, 'plugin_manifest_text'],
    [{ prompts: [{ id: 'prompt', version: '1', sha256: 'a'.repeat(64) }] }, 'plugin_prompt_skill_observation_unsupported'],
    [{ endpoints: ['https://example.invalid'] }, 'plugin_endpoints_require_bf03'],
  ]) assert.throws(() => validateManifest({ ...valid, ...change }, cohort), new RegExp(code));
  const migration = { ...valid, migrations: [{ id: 'registered', sha256: 'a'.repeat(64) }] };
  assert.doesNotThrow(() => validateManifest(migration, cohort, { registered: 'a'.repeat(64) }));
  assert.throws(() => validateManifest(migration, cohort, { registered: 'b'.repeat(64) }), /plugin_migration_unknown/);
});

test('dependency-first order is deterministic and duplicate native/tool identities cannot stage', () => {
  const base = manifest('synthetic.base'), dependent = manifest('synthetic.dependent');
  dependent.dependencies = [{ plugin_id: base.plugin_id, range: '^1.0.0' }];
  const selected = [{ manifest: dependent, enabled: true }, { manifest: base, enabled: true }];
  validateSelection(selected, cohort);
  assert.deepEqual(activationOrder(selected).map(item => item.manifest.plugin_id), [base.plugin_id, dependent.plugin_id]);
  assert.throws(() => validateSelection([{ manifest: base, enabled: true }, { manifest: { ...dependent, native_id: base.native_id }, enabled: true }], cohort), /plugin_native_id_duplicate/);
  const declaration = { name: 'shared_tool', permission: 'synthetic.lookup', input_schema_sha256: sha256(canonical(schema)), output_schema_sha256: null };
  base.tools = [declaration]; dependent.tools = [declaration];
  assert.throws(() => validateSelection(selected, cohort), /plugin_tool_duplicate/);
  assert.throws(() => validateSelection([{ manifest: base, enabled: true, undeclared: true }], cohort), /plugin_selection_schema/);
});

test('artifact integrity, linked bytes and actual licence/notices are checked before native execution', async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'renulus-bf01-integrity-'));
  const item = manifest();
  const directory = path.join(root, 'artifacts', item.plugin_id, item.version + '-' + item.artifact_sha256);
  await mkdir(directory, { recursive: true });
  const file = path.join(directory, 'server.js');
  await writeFile(file, bytes);
  await assert.rejects(readArtifact(root, item), /plugin_license_missing|plugin_artifact_unreadable/);
  await writeFile(path.join(directory, 'LICENSE'), '   \n');
  await assert.rejects(readArtifact(root, item), /plugin_license_missing/);
  await writeFile(path.join(directory, 'LICENSE'), 'Synthetic MIT licence.\n');
  await readArtifact(root, item);
  await assert.rejects(readArtifact(root, { ...item, notices: ['NOTICE'] }), /plugin_license_missing|plugin_artifact_unreadable/);
  await writeFile(path.join(directory, 'NOTICE'), 'Synthetic attribution.\n');
  await readArtifact(root, { ...item, notices: ['NOTICE'] });
  await writeFile(file, bytes + '// tampered\n');
  await assert.rejects(readArtifact(root, item), /plugin_artifact_integrity/);
  await writeFile(file, bytes);
  await link(file, path.join(directory, 'another-name.js'));
  await assert.rejects(readArtifact(root, item), /plugin_artifact_invalid/);
});

test('final registry requires every declared schema, exact baseline and no privileged-name exception', () => {
  const item = manifest();
  item.tools = [{ name: 'synthetic_lookup', permission: 'synthetic.lookup', input_schema_sha256: sha256(canonical(schema)), output_schema_sha256: null }];
  const artifact = { manifest: item, path: path.resolve('synthetic-bf01/server.js') };
  const definition = { type: 'tool', name: 'synthetic_lookup', description: 'Synthetic tool', inputSchema: schema };
  const observation = {
    contract: 'renulus-native-plugin-observation/1', isolation: 'disposable',
    plugins: [{ id: item.native_id, source_type: 'local', source_path: artifact.path, status: 'active' }],
    artifact_hashes: { [item.native_id]: item.artifact_sha256 }, registry: [definition],
    registry_hash: sha256(canonical([definition])), quiescent: true, recovery_held: true,
    package_acquisition_closed: true, effects_denied: true,
  };
  const request = { artifacts: [artifact], baseline_tools: [] };
  assert.doesNotThrow(() => validateObservation(observation, request, 'disposable', true));
  for (const name of ['opencode_extra', 'renulus_internal_extra', 'execute', 'websearch']) {
    const registry = [...observation.registry, { ...definition, name }];
    assert.throws(() => validateObservation({ ...observation, registry, registry_hash: sha256(canonical(registry)) }, request, 'disposable', true), /plugin_registry_unexpected_tool/);
  }
  assert.throws(() => validateObservation({ ...observation, plugins: [{ ...observation.plugins[0], status: 'failed' }] }, request, 'disposable', true), /plugin_candidate_failed/);
  const registry = [{ ...definition, inputSchema: { type: 'string' } }];
  assert.throws(() => validateObservation({ ...observation, registry, registry_hash: sha256(canonical(registry)) }, request, 'disposable', true), /plugin_tool_schema_mismatch/);
  assert.throws(() => validateObservation(observation, { ...request, baseline_tools: [{ ...definition, name: 'host_baseline' }] }, 'disposable', true), /plugin_baseline_registry_mismatch/);
});
