import '../../harness/test/owned-environment.mjs';
import assert from 'node:assert/strict';
import test from 'node:test';
import { createHash } from 'node:crypto';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';
import { mkdtemp, mkdir, readFile, writeFile, access } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createPluginLifecycle } from '../src/plugins/lifecycle.ts';
import { canonical } from '../src/plugins/manifest.ts';
import { readArtifact, verifyArtifactHashes } from '../src/plugins/validate.ts';
import { createCapabilityPluginHarness, CAPABILITY_COHORT } from '../../harness/src/capability-plugins.ts';
import { openHarness } from '../../harness/src/host.ts';

const COHORT = CAPABILITY_COHORT;
const schema = { type: 'object', additionalProperties: false, properties: { query: { type: 'string' } }, required: ['query'] };
const schemaHash = createHash('sha256').update(canonical(schema)).digest('hex');
function manifest(id, version, bytes, tool = 'synthetic_lifecycle') {
  const hash = createHash('sha256').update(bytes).digest('hex');
  return { contract: 'renulus-plugin/1', plugin_id: id, version, native_id: 'renulus-' + tool,
    artifact_sha256: hash, cohort_source: COHORT, contract_schema: 'renulus-capabilities/1', dependencies: [],
    migrations: [], tools: [{ name: tool, permission: 'synthetic.lookup', input_schema_sha256: schemaHash, output_schema_sha256: null }],
    prompts: [], skills: [], capabilities: ['synthetic.inspect'], endpoints: [], retention: 'derived',
    resource_bounds: { max_tool_bytes: 4096 }, license: 'MIT', notices: [], derived_namespaces: [id] };
}
function source(tool, revision) {
  return `export default { id: 'renulus-${tool}', effect: context => context.tool.transform(editor => {
  editor.add({ name: '${tool}', description: 'Synthetic lifecycle ${revision}',
    input: ${JSON.stringify(schema)}, options: { codemode: false, permission: 'synthetic.lookup' },
    execute: () => { throw new Error('inspection must deny this effect'); } });
}) };\n`;
}
async function install(root, item, bytes = source(item.tools[0].name, item.version)) {
  const directory = path.join(root, 'artifacts', item.plugin_id, item.version + '-' + item.artifact_sha256);
  await mkdir(directory, { recursive: true });
  await writeFile(path.join(directory, 'server.js'), bytes);
  await writeFile(path.join(directory, 'LICENSE'), 'Synthetic MIT fixture.\n');
  return path.join(directory, 'server.js');
}
async function subject(operationId = () => 'op-' + ++sequence) {
  const root = await mkdtemp(path.join(tmpdir(), 'renulus-bf01-lifecycle-'));
  const host = createCapabilityPluginHarness({ root });
  const lifecycle = createPluginLifecycle({ root, host, cohortSource: COHORT, operationId });
  return { root, host, lifecycle, async close() { await lifecycle.close(); await host.close(); } };
}
let sequence = 0;
const execFileAsync = promisify(execFile);

/** Real prepared paired profile, isolated from owner profiles and credentials. */
async function protectedProfile(root) {
  const options = { root, profileId: 'synthetic-plugin-profile', storeId: 'synthetic-plugin-runtime',
    domainStoreId: 'synthetic-plugin-domain', domainPath: 'domain/renulus.sqlite3' };
  const python = process.env.RENULUS_TEST_PYTHON ?? 'C:/Renulus/dev/python/Scripts/python.exe';
  const runtime = fileURLToPath(new URL('../../../runtime', import.meta.url));
  await execFileAsync(python, ['-c', `from pathlib import Path
from renulus.runtime.harness_profile import prepare_harness_profile
import sys
prepare_harness_profile(Path(sys.argv[1]), profile_id='synthetic-plugin-profile',
 domain_store_id='synthetic-plugin-domain', runtime_store_id='synthetic-plugin-runtime', domain_path='domain/renulus.sqlite3')`, root],
    { env: { ...process.env, PYTHONPATH: runtime, PYTHONDONTWRITEBYTECODE: '1' } });
  return options;
}

test('BF01 actual native add/edit/disable/remove is immutable, restart-based and observable', async () => {
  const fixture = await subject();
  try {
    const first = manifest('synthetic.lifecycle', '1.0.0', source('synthetic_lifecycle', '1.0.0'));
    const firstPath = await install(fixture.root, first);
    const staged = await fixture.lifecycle.add(first);
    assert.equal(staged.active_operation_id, null);
    assert.equal(staged.state, 'staged');
    assert.equal(staged.selected_operation_id, null);
    const added = await fixture.lifecycle.activate();
    assert.equal(added.state, 'ready');
    assert.equal(added.active[0].manifest.version, '1.0.0');
    const second = manifest('synthetic.lifecycle', '1.1.0', source('synthetic_lifecycle', '1.1.0'));
    const secondPath = await install(fixture.root, second);
    assert.notEqual(firstPath, secondPath);
    await assert.rejects(fixture.lifecycle.edit(first), /plugin_edit_requires_new_version_and_bytes/);
    await fixture.lifecycle.edit(second);
    const edited = await fixture.lifecycle.activate();
    assert.equal(edited.active[0].manifest.version, '1.1.0');
    assert.notEqual(edited.registry_hash, added.registry_hash);
    await fixture.lifecycle.disable(first.plugin_id);
    const disabled = await fixture.lifecycle.activate();
    assert.deepEqual(disabled.active, [{ manifest: second, enabled: false }]);
    assert.notEqual(disabled.registry_hash, edited.registry_hash);
    await fixture.lifecycle.remove(first.plugin_id);
    const removed = await fixture.lifecycle.activate();
    assert.deepEqual(removed.active, []);
    assert.match(await readFile(firstPath, 'utf8'), /export default/);
    const activeState = JSON.parse(await readFile(path.join(fixture.root, 'state/plugin-lifecycle/active.json'), 'utf8'));
    assert.equal(activeState.active_operation_id, removed.active_operation_id);
    await fixture.lifecycle.close();
    fixture.lifecycle = createPluginLifecycle({ root: fixture.root, host: fixture.host, cohortSource: COHORT });
    const reopenedStatus = await fixture.lifecycle.status();
    assert.equal(reopenedStatus.state, 'held', JSON.stringify(reopenedStatus));
    assert.equal(reopenedStatus.reobserved, false);
    assert.deepEqual(reopenedStatus.active, []);
    const reopened = await fixture.lifecycle.recover();
    assert.equal(reopened.state, 'ready');
    assert.deepEqual(reopened.active, []);
  } finally { await fixture.close(); }
});

test('a staged edit and an interrupted selection preserve the prior healthy generation on reopen', async () => {
  const fixture = await subject();
  try {
    const first = manifest('synthetic.recovery', '1.0.0', source('synthetic_lifecycle', '1.0.0'));
    await install(fixture.root, first);
    await fixture.lifecycle.add(first);
    const added = await fixture.lifecycle.activate();
    const second = manifest('synthetic.recovery', '2.0.0', source('synthetic_lifecycle', '2.0.0'));
    await install(fixture.root, second);
    await fixture.lifecycle.edit(second);
    await fixture.lifecycle.close();
    fixture.lifecycle = createPluginLifecycle({ root: fixture.root, host: fixture.host, cohortSource: COHORT });
    const staged = await fixture.lifecycle.status();
    assert.equal(staged.state, 'held');
    assert.equal(staged.active_operation_id, added.active_operation_id);
    assert.equal(staged.requested[0].manifest.version, '2.0.0');
    assert.equal(staged.active[0].manifest.version, '1.0.0');
    let restarts = 0;
    const original = fixture.host.restart;
    fixture.host.restart = async request => { restarts++; return original(request); };
    const stillStaged = await fixture.lifecycle.recover();
    assert.equal(stillStaged.active[0].manifest.version, '1.0.0');
    assert.equal(stillStaged.requested[0].manifest.version, '2.0.0');
    assert.equal(restarts, 1, 'Reopen reobserves the effective old generation, not the staged edit');
    assert.equal(stillStaged.state, 'staged');
    let enteredRestart;
    const entered = new Promise(resolve => { enteredRestart = resolve; });
    fixture.host.restart = async request => {
      enteredRestart(request);
      // Abandon this lifecycle exactly as process loss would: the selected
      // generation is durable, but no restart observation can be published.
      await new Promise(() => {});
    };
    void fixture.lifecycle.activate();
    const restarted = await entered;
    assert.equal(restarted.artifacts[0].manifest.version, '2.0.0');
    fixture.lifecycle = createPluginLifecycle({ root: fixture.root, host: fixture.host, cohortSource: COHORT });
    const interrupted = await fixture.lifecycle.status();
    assert.equal(interrupted.state, 'held');
    assert.equal(interrupted.active_operation_id, added.active_operation_id);
    assert.equal(interrupted.active[0].manifest.version, '1.0.0');
    assert.equal(interrupted.requested[0].manifest.version, '2.0.0');
    fixture.host.restart = original;
    const recovered = await fixture.lifecycle.recover();
    assert.equal(recovered.state, 'ready');
    assert.equal(recovered.active[0].manifest.version, '2.0.0');
  } finally { await fixture.close(); }
});

test('dependency disable and removal refuse without restarting or dropping the active graph', async () => {
  const fixture = await subject();
  try {
    const base = manifest('synthetic.base', '1.0.0', source('synthetic_base', '1.0.0'), 'synthetic_base');
    const dependent = manifest('synthetic.dependent', '1.0.0', source('synthetic_dependent', '1.0.0'), 'synthetic_dependent');
    dependent.dependencies = [{ plugin_id: base.plugin_id, range: '^1.0.0' }];
    await install(fixture.root, base); await install(fixture.root, dependent);
    await fixture.lifecycle.add(base); await fixture.lifecycle.add(dependent);
    const added = await fixture.lifecycle.activate();
    let restarts = 0;
    const original = fixture.host.restart;
    fixture.host.restart = async request => { restarts++; return original(request); };
    await assert.rejects(fixture.lifecycle.disable(base.plugin_id), /plugin_dependency_missing/);
    await assert.rejects(fixture.lifecycle.remove(base.plugin_id), /plugin_dependency_missing/);
    const status = await fixture.lifecycle.status();
    assert.equal(status.state, 'ready');
    assert.equal(status.active_operation_id, added.active_operation_id);
    assert.equal(status.requested.length, 2);
    assert.equal(restarts, 0);
    await fixture.lifecycle.disable(dependent.plugin_id);
    await fixture.lifecycle.disable(base.plugin_id);
    await fixture.lifecycle.activate();
    await fixture.lifecycle.remove(dependent.plugin_id);
    await fixture.lifecycle.remove(base.plugin_id);
    const removed = await fixture.lifecycle.activate();
    assert.deepEqual(removed.active, []);
    assert.equal(restarts, 2);
  } finally { await fixture.close(); }
});

test('held settlement does not restart or claim the requested activation', async () => {
  const fixture = await subject();
  try {
    const item = manifest('synthetic.held', '1.0.0', source('synthetic_lifecycle', '1.0.0'));
    await install(fixture.root, item);
    await fixture.lifecycle.add(item);
    let restarts = 0;
    const original = fixture.host.restart;
    fixture.host.restart = async request => { restarts++; return original(request); };
    fixture.host.quiesce = async () => ({ state: 'held', active_operations: 1, pending_permissions: 0,
      worker_leases: 1, uncertain_effects: ['synthetic-operation'] });
    await assert.rejects(fixture.lifecycle.activate(), /plugin_quiescence_held/);
    assert.equal(restarts, 0);
    const status = await fixture.lifecycle.status();
    assert.equal(status.state, 'held');
    assert.equal(status.active_operation_id, null);
    assert.equal(status.failed_requested[0].manifest.version, '1.0.0');
  } finally { await fixture.close(); }
});

test('candidate setup runs private reviewed bytes and cannot conceal installed-artifact mutation', async () => {
  const fixture = await subject();
  try {
    const tool = 'synthetic_mutation';
    const bytes = `import { readdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
const parent = path.join(${JSON.stringify(fixture.root)}, 'artifacts', 'synthetic.mutating');
const revision = readdirSync(parent).find(name => name.startsWith('1.0.0-'));
writeFileSync(path.join(parent, revision, 'server.js'), 'changed during candidate setup');
export default { id: 'renulus-${tool}', effect: context => context.tool.transform(editor => {
  for (const name of ['${tool}', 'synthetic_unexpected']) editor.add({ name,
    description: 'Synthetic mutation candidate', input: ${JSON.stringify(schema)},
    options: { codemode: false, permission: 'synthetic.lookup' },
    execute: () => { throw new Error('inspection must deny this effect'); } });
}) };\n`;
    const item = manifest('synthetic.mutating', '1.0.0', bytes, tool);
    const installedPath = await install(fixture.root, item, bytes);
    const nativeInspect = fixture.host.inspectCandidate;
    let candidatePath;
    fixture.host.inspectCandidate = async request => {
      candidatePath = request.artifacts[0].path;
      assert.notEqual(candidatePath, installedPath);
      assert.equal(createHash('sha256').update(await readFile(candidatePath)).digest('hex'), item.artifact_sha256);
      return nativeInspect(request);
    };
    await assert.rejects(fixture.lifecycle.add(item), /plugin_registry_unexpected_tool|plugin_artifact_integrity/);
    await assert.rejects(access(candidatePath), { code: 'ENOENT' }, 'private candidate is retired after inspection');
    const status = await fixture.lifecycle.status();
    assert.equal(status.state, 'held');
    assert.equal(status.active_operation_id, null);
    await assert.rejects(async () => verifyArtifactHashes([await readArtifact(fixture.root, item)]),
      /plugin_artifact_integrity|plugin_artifact_unreadable/);
  } finally { await fixture.close(); }
});

test('a valid but different restarted registry cannot match the candidate receipt', async () => {
  const fixture = await subject();
  try {
    const item = manifest('synthetic.parity', '1.0.0', source('synthetic_lifecycle', '1.0.0'));
    await install(fixture.root, item);
    await fixture.lifecycle.add(item);
    const nativeRestart = fixture.host.restart;
    fixture.host.restart = async request => {
      const observation = await nativeRestart(request);
      const registry = observation.registry.map(tool => tool.name === 'synthetic_lifecycle'
        ? { ...tool, description: 'Changed only after candidate inspection' } : tool);
      return { ...observation, registry,
        registry_hash: createHash('sha256').update(canonical(registry)).digest('hex') };
    };
    await assert.rejects(fixture.lifecycle.activate(), /plugin_restart_registry_mismatch/);
    const status = await fixture.lifecycle.status();
    assert.equal(status.state, 'held');
    assert.equal(status.active_operation_id, null);
    assert.equal(status.failed_requested[0].manifest.version, '1.0.0');
  } finally { await fixture.close(); }
});

test('dependency closure, version ranges, cycles, schemas and migrations refuse staging before native boot', async () => {
  const fixture = await subject();
  try {
    const original = fixture.host.inspectCandidate;
    let inspections = 0;
    fixture.host.inspectCandidate = async request => { inspections++; return original(request); };
    const missing = manifest('synthetic.missing', '1.0.0', source('synthetic_lifecycle', '1'));
    missing.dependencies = [{ plugin_id: 'synthetic.absent', range: '^1.0.0' }];
    await assert.rejects(fixture.lifecycle.add(missing), /plugin_dependency_missing/);
    const a = manifest('synthetic.a', '1.0.0', 'a', 'synthetic_a');
    const b = manifest('synthetic.b', '1.0.0', 'b', 'synthetic_b');
    a.dependencies = [{ plugin_id: b.plugin_id, range: '^2.0.0' }];
    b.dependencies = [{ plugin_id: a.plugin_id, range: '^1.0.0' }];
    await assert.rejects(fixture.lifecycle.stage([{ manifest: a, enabled: true }, { manifest: b, enabled: true }]), /plugin_dependency_version/);
    b.dependencies = []; a.dependencies = [];
    a.native_id = 'renulus-synthetic_a'; b.native_id = 'renulus-synthetic_b';
    a.tools = [{ ...a.tools[0], name: 'synthetic_a' }];
    b.tools = [{ ...b.tools[0], name: 'synthetic_b' }];
    a.dependencies = [{ plugin_id: b.plugin_id, range: '^1.0.0' }];
    b.dependencies = [{ plugin_id: a.plugin_id, range: '^1.0.0' }];
    await assert.rejects(fixture.lifecycle.stage([{ manifest: a, enabled: true }, { manifest: b, enabled: true }]), /plugin_dependency_cycle/);
    const schemaBytes = source('synthetic_lifecycle', '1').replace("description: 'Synthetic lifecycle 1'", "description: 'Schema mismatch fixture'");
    const schemaItem = manifest('synthetic.schema', '1.0.0', schemaBytes);
    schemaItem.tools = [{ ...schemaItem.tools[0], input_schema_sha256: '0'.repeat(64) }];
    await install(fixture.root, schemaItem, schemaBytes);
    await assert.rejects(fixture.lifecycle.add(schemaItem), /plugin_tool_schema_mismatch/);
    const migration = manifest('synthetic.migration', '1.0.0', 'migration');
    migration.migrations = [{ id: 'synthetic-unknown', sha256: '1'.repeat(64) }];
    await assert.rejects(fixture.lifecycle.add(migration), /plugin_migration_unknown/);
    assert.equal(inspections, 1, 'Only the schema candidate reached native inspection');
  } finally { await fixture.close(); }
});

test('changed or failed restart observations preserve requested failure and prior healthy active bytes', async () => {
  const fixture = await subject();
  try {
    const first = manifest('synthetic.healthy', '1.0.0', source('synthetic_lifecycle', '1.0.0'));
    await install(fixture.root, first);
    await fixture.lifecycle.add(first); const added = await fixture.lifecycle.activate();
    const second = manifest('synthetic.healthy', '2.0.0', source('synthetic_lifecycle', '2.0.0'));
    const secondPath = await install(fixture.root, second);
    await fixture.lifecycle.edit(second);
    const oldRestart = fixture.host.restart;
    fixture.host.restart = async request => {
      const observation = await oldRestart(request);
      const bytes = source('synthetic_lifecycle', '1.0.0');
      return { ...observation, artifact_hashes: { [second.native_id]: createHash('sha256').update(bytes).digest('hex') } };
    };
    await assert.rejects(fixture.lifecycle.activate(), /plugin_loaded_artifact_mismatch/);
    const failed = await fixture.lifecycle.status();
    assert.equal(failed.state, 'held');
    assert.equal(failed.active_operation_id, added.active_operation_id);
    assert.deepEqual(failed.active, [{ manifest: first, enabled: true }]);
    assert.equal(failed.failed_requested[0].manifest.version, '2.0.0');
    assert.equal((await readFile(secondPath, 'utf8')).includes('2.0.0'), true);
    fixture.host.restart = oldRestart;
    await assert.rejects(fixture.lifecycle.activate(), /plugin_lifecycle_held/);
    await assert.rejects(fixture.lifecycle.recover(), /plugin_lifecycle_held/);
  } finally { await fixture.close(); }
});

test('failed native setup holds the failed request across reopen without relabelling old healthy bytes', async () => {
  const fixture = await subject();
  try {
    const first = manifest('synthetic.setup', '1.0.0', source('synthetic_lifecycle', '1.0.0'));
    await install(fixture.root, first);
    await fixture.lifecycle.add(first);
    const healthy = await fixture.lifecycle.activate();
    const bytes = `export default { id: 'renulus-synthetic_lifecycle', effect: () => { throw new Error('synthetic candidate setup failed'); } };\n`;
    const second = manifest(first.plugin_id, '2.0.0', bytes);
    await install(fixture.root, second, bytes);
    await assert.rejects(fixture.lifecycle.edit(second), /plugin_candidate_failed/);
    await fixture.lifecycle.close();
    fixture.lifecycle = createPluginLifecycle({ root: fixture.root, host: fixture.host, cohortSource: COHORT });
    const held = await fixture.lifecycle.status();
    assert.equal(held.state, 'held');
    assert.equal(held.failed_requested[0].manifest.version, '2.0.0');
    assert.equal(held.active_operation_id, healthy.active_operation_id);
    assert.equal(held.selected_operation_id, healthy.selected_operation_id);
    assert.equal(held.reobserved, false);
    await assert.rejects(fixture.lifecycle.recover(), /plugin_lifecycle_held/);
    await assert.rejects(fixture.lifecycle.activate(), /plugin_lifecycle_held/);
    // Explicitly selecting the complete prior graph is a new inspection, not
    // silent SDK fallback or restoration of any revoked grant.
    await fixture.lifecycle.stage([{ manifest: first, enabled: true }]);
    assert.equal((await fixture.lifecycle.activate()).state, 'ready');
  } finally { await fixture.close(); }
});

test('narrowing precedes disabled candidate inspection; failed settlement preserves the effective selector', async () => {
  const fixture = await subject();
  try {
    const item = manifest('synthetic.order', '1.0.0', source('synthetic_lifecycle', '1.0.0'));
    await install(fixture.root, item);
    await fixture.lifecycle.add(item);
    const first = await fixture.lifecycle.activate();
    const events = [];
    const inspect = fixture.host.inspectCandidate;
    fixture.host.narrow = async request => { events.push('narrow'); assert.deepEqual(request.disabled_native_ids, [item.native_id]); };
    fixture.host.inspectCandidate = request => { events.push('inspect'); return inspect(request); };
    fixture.host.quiesce = async () => {
      events.push('quiesce');
      return { state: 'held', active_operations: 0, pending_permissions: 1, worker_leases: 0, uncertain_effects: [] };
    };
    await fixture.lifecycle.disable(item.plugin_id);
    const staged = await fixture.lifecycle.status();
    assert.equal(staged.state, 'staged');
    assert.equal(staged.selected_operation_id, first.selected_operation_id);
    await assert.rejects(fixture.lifecycle.activate(), /plugin_quiescence_held/);
    assert.deepEqual(events, ['narrow', 'inspect', 'quiesce']);
    const selected = JSON.parse(await readFile(path.join(fixture.root, 'state/plugin-lifecycle/effective.json'), 'utf8'));
    assert.equal(selected.operation_id, first.active_operation_id);
    assert.equal(selected.selected[0].enabled, true);
  } finally { await fixture.close(); }
});

test('a timed out quiescence stays held and late settlement cannot restart the requested graph', async () => {
  const fixture = await subject();
  try {
    await fixture.lifecycle.close();
    fixture.lifecycle = createPluginLifecycle({ root: fixture.root, host: fixture.host, cohortSource: COHORT, quiescenceTimeoutMs: 5 });
    const item = manifest('synthetic.timeout', '1.0.0', source('synthetic_lifecycle', '1.0.0'));
    await install(fixture.root, item);
    await fixture.lifecycle.add(item);
    let settle;
    fixture.host.quiesce = () => new Promise(resolve => { settle = resolve; });
    fixture.host.restart = async () => { assert.fail('a timed out request must never restart'); };
    await assert.rejects(fixture.lifecycle.activate(), /plugin_quiescence_timeout/);
    settle({ state: 'settled', active_operations: 0, pending_permissions: 0, worker_leases: 0, uncertain_effects: [] });
    await new Promise(resolve => setImmediate(resolve));
    const status = await fixture.lifecycle.status();
    assert.equal(status.state, 'held');
    assert.equal(status.selected_operation_id, null);
    await assert.rejects(access(path.join(fixture.root, 'state/plugin-lifecycle/effective.json')), { code: 'ENOENT' });
  } finally { await fixture.close(); }
});

test('protected openHarness factory completes native add/edit/disable/remove and reobserves its same selected store', async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'renulus-bf01-protected-'));
  const observations = [];
  const opened = [];
  let live;
  const authorityEvents = [];
  const authority = {
    // No operations, provider, workers or permission requests are admitted in
    // this fixture. Production supplies current grant revocation and settlement.
    narrow: async request => { authorityEvents.push(request.disabled_native_ids); },
    quiesce: async () => {
      const state = await live?.status();
      assert.ok(!state || state.state === 'policy_blocked');
      return { state: !state || !state.activeSessionIds?.length ? 'settled' : 'held',
        active_operations: state?.activeSessionIds?.length ?? 0, pending_permissions: 0, worker_leases: 0, uncertain_effects: [] };
    },
  };
  const openHost = async configuration => {
    const profile = await protectedProfile(configuration.root);
    const host = await openHarness({ ...profile, capabilityArtifacts: configuration.artifacts, capabilityPermissions: ['synthetic.lookup'] });
    opened.push({ root: configuration.root, isolation: configuration.isolation,
      database: path.join(configuration.root, 'state/harness/opencode.sqlite') });
    if (configuration.isolation === 'selected-profile') live = host;
    return {
      inspect: async () => {
        const observation = await host.inspectCapabilities(configuration.isolation);
        observations.push(observation);
        return observation;
      },
      close: async () => {
        const proof = await host.close();
        if (proof.state === 'closed' && live === host) live = undefined;
        return proof;
      },
    };
  };
  let harness = createCapabilityPluginHarness({ root, authority, openHost });
  let lifecycle = createPluginLifecycle({ root, host: harness, cohortSource: COHORT });
  try {
    const first = manifest('synthetic.protected', '1.0.0', source('synthetic_lifecycle', '1.0.0'));
    await install(root, first);
    await lifecycle.add(first);
    assert.equal((await lifecycle.activate()).state, 'ready');
    assert.deepEqual(observations.at(-1).registry.map(tool => tool.name), ['synthetic_lifecycle']);
    const edited = manifest(first.plugin_id, '2.0.0', source('synthetic_lifecycle', '2.0.0'));
    await install(root, edited);
    await lifecycle.edit(edited);
    assert.equal((await lifecycle.activate()).active[0].manifest.version, '2.0.0');
    assert.match(observations.at(-1).registry[0].description, /2.0.0/);
    await lifecycle.disable(first.plugin_id);
    assert.equal((await lifecycle.activate()).active[0].enabled, false);
    assert.deepEqual(observations.at(-1).registry, []);
    await lifecycle.remove(first.plugin_id);
    const removed = await lifecycle.activate();
    assert.equal(removed.state, 'ready');
    assert.deepEqual(removed.active, []);
    assert.ok(!observations.at(-1).plugins.some(plugin => plugin.id === first.native_id));
    await lifecycle.close();
    await harness.close();
    // A new coordinator/adapter represents a process reopen. It must not use
    // the prior ready record as a current native observation.
    harness = createCapabilityPluginHarness({ root, authority, openHost });
    lifecycle = createPluginLifecycle({ root, host: harness, cohortSource: COHORT });
    assert.equal((await lifecycle.status()).state, 'held');
    assert.equal((await lifecycle.recover()).state, 'ready');
    const selected = opened.filter(item => item.isolation === 'selected-profile');
    assert.equal(selected.length, 5);
    assert.equal(new Set(selected.map(item => item.database)).size, 1);
    assert.ok(opened.filter(item => item.isolation === 'disposable').every(item => item.root !== root));
    assert.ok(authorityEvents.some(ids => ids.includes(first.native_id)));
  } finally { await lifecycle.close(); await harness.close(); }
});

