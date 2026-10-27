import './owned-environment.mjs';
import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdtemp, mkdir, writeFile, readFile, access } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createCapabilityPluginHarness, openCapabilityPluginHost, CAPABILITY_COHORT } from '../src/capability-plugins.ts';

const schema = { type: 'object', additionalProperties: false, properties: { query: { type: 'string' } }, required: ['query'] };
function source(tool, marker, revision = 1) {
  return `import { appendFileSync } from 'node:fs';
export default { id: 'renulus-synthetic-${tool}', effect: context => context.tool.transform(editor => {
  editor.add({ name: '${tool}', description: 'Synthetic lifecycle revision ${revision}',
    input: ${JSON.stringify(schema)}, options: { codemode: false, permission: 'synthetic.${tool}' },
    execute: () => { appendFileSync(${JSON.stringify(marker)}, 'executed'); throw new Error('must not execute'); } });
}) };\n`;
}
async function fixture(root, tool, revision = 1) {
  const marker = path.join(root, tool + '-executed');
  const bytes = source(tool, marker, revision);
  const artifactSha256 = createHash('sha256').update(bytes).digest('hex');
  const directory = path.join(root, 'artifacts', 'synthetic.' + tool, `1.0.${revision - 1}-` + artifactSha256);
  await mkdir(directory, { recursive: true });
  await writeFile(path.join(directory, 'server.js'), bytes);
  await writeFile(path.join(directory, 'LICENSE'), 'Synthetic MIT test fixture.\n');
  const manifest = { contract: 'renulus-plugin/1', plugin_id: 'synthetic.' + tool,
    version: `1.0.${revision - 1}`, native_id: 'renulus-synthetic-' + tool, artifact_sha256: artifactSha256,
    cohort_source: CAPABILITY_COHORT, contract_schema: 'renulus-capabilities/1', dependencies: [], migrations: [],
    tools: [{ name: tool, permission: 'synthetic.' + tool,
      input_schema_sha256: createHash('sha256').update(JSON.stringify(schema)).digest('hex'), output_schema_sha256: null }],
    prompts: [], skills: [], capabilities: ['synthetic.inspect'], endpoints: [], retention: 'derived',
    resource_bounds: { max_tool_bytes: 4096 }, license: 'MIT', notices: [], derived_namespaces: ['synthetic.' + tool] };
  return { manifest, path: path.join(directory, 'server.js'), marker };
}

test('actual native candidate loads reviewed local tools after transforms and denies every effect', async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'renulus-bf01-native-'));
  const artifact = await fixture(root, 'synthetic_lookup');
  let host;
  try {
    host = await openCapabilityPluginHost({ root: path.join(root, 'candidate'), workspace: path.join(root, 'workspace'),
      databasePath: ':memory:', isolation: 'disposable', artifacts: [artifact] });
    const first = await host.inspect();
    const second = await host.inspect();
    assert.deepEqual(second, first);
    assert.ok(first.plugins.some(plugin => plugin.id === artifact.manifest.native_id &&
      plugin.source_path === artifact.path && plugin.status === 'active'));
    assert.equal(first.registry_hash.length, 64);
    assert.deepEqual(first.registry.map(tool => tool.name), ['synthetic_lookup']);
    assert.equal(first.quiescent, true);
    await assert.rejects(access(artifact.marker), { code: 'ENOENT' });
  } finally { await host?.close(); }
});

test('native composition accepts only explicitly declared baseline tools', async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'renulus-bf01-native-baseline-'));
  const artifact = await fixture(root, 'synthetic_baseline');
  const original = artifact.manifest;
  artifact.manifest = { ...original, tools: [...(original.tools ?? []), { name: 'renulus_library_retrieve' }] };
  let host;
  try {
    host = await openCapabilityPluginHost({ root: path.join(root, 'candidate'), workspace: path.join(root, 'workspace'),
      databasePath: ':memory:', isolation: 'disposable', artifacts: [artifact],
      baselineTools: [{ name: 'renulus_library_retrieve' }] });
    const observation = await host.inspect();
    assert.ok(observation.registry.some(tool => tool.name === 'synthetic_baseline'));
    assert.ok(!observation.registry.some(tool => tool.name === 'renulus_library_retrieve'));
  } finally { await host?.close(); }
});

test('fresh native hosts omit disabled and removed plugin registrations rather than unregistering', async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'renulus-bf01-native-restart-'));
  const artifact = await fixture(root, 'synthetic_restart');
  const harness = createCapabilityPluginHarness({ root });
  try {
    const added = await harness.inspectCandidate({ operation_id: 'op-add', artifacts: [artifact], baseline_tools: [] });
    assert.deepEqual(added.registry.map(tool => tool.name), ['synthetic_restart']);
    await harness.restart({ operation_id: 'op-add', artifacts: [artifact], baseline_tools: [] });
    const omitted = await harness.restart({ operation_id: 'op-remove', artifacts: [], baseline_tools: [] });
    assert.ok(!omitted.plugins.some(plugin => plugin.id === artifact.manifest.native_id));
    assert.ok(!omitted.registry.some(tool => tool.name === 'synthetic_restart'));
    await assert.rejects(access(artifact.marker), { code: 'ENOENT' });
    const bytes = await readFile(artifact.path, 'utf8');
    assert.match(bytes, /renulus-synthetic-synthetic_restart/);
  } finally { await harness.close(); }
});

test('tampered bytes and a native setup failure cannot produce a healthy candidate receipt', async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'renulus-bf01-native-failure-'));
  const artifact = await fixture(root, 'synthetic_failure');
  const harness = createCapabilityPluginHarness({ root });
  try {
    await writeFile(artifact.path, source('synthetic_failure', artifact.marker, 2));
    await assert.rejects(harness.inspectCandidate({ operation_id: 'op-tampered', artifacts: [artifact], baseline_tools: [] }), /plugin_artifact_integrity/);
    await assert.rejects(access(artifact.marker), { code: 'ENOENT' });
  } finally { await harness.close(); }
});

test('native source reload exposes restored old bytes after a failed new generation', async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'renulus-bf01-native-old-bytes-'));
  const artifact = await fixture(root, 'synthetic_old_bytes');
  let host;
  try {
    host = await openCapabilityPluginHost({ root: path.join(root, 'candidate'), workspace: path.join(root, 'workspace'),
      databasePath: ':memory:', isolation: 'disposable', artifacts: [artifact] });
    const healthy = await host.inspect();
    assert.match(healthy.registry[0].description, /revision 1/);
    const bytes = `export default { id: ${JSON.stringify(artifact.manifest.native_id)}, effect: () => { throw new Error('synthetic setup failure'); } };\n`;
    await writeFile(artifact.path, bytes);
    const next = { ...artifact, manifest: { ...artifact.manifest,
      artifact_sha256: createHash('sha256').update(bytes).digest('hex') } };
    const observed = await host.reobserveForTest([next]);
    assert.ok(observed.plugins.some(plugin => plugin.id === artifact.manifest.native_id && plugin.status === 'failed'));
    assert.match(observed.registry[0].description, /revision 1/);
    await assert.rejects(access(artifact.marker), { code: 'ENOENT' });
  } finally { await host?.close(); }
});

for (const isolation of ['disposable', 'selected-profile']) {
  test(`held ${isolation} retirement retains the exact handle before replacement and shutdown retry`, async () => {
    const root = await mkdtemp(path.join(tmpdir(), 'renulus-plugin-retained-'));
    const request = { operation_id: 'op-first', artifacts: [], baseline_tools: [] };
    const handles = [], attempts = [];
    let allowed = false;
    const harness = createCapabilityPluginHarness({ root,
      authority: { narrow: async () => {}, quiesce: async () => ({ state: 'settled', active_operations: 0,
        pending_permissions: 0, worker_leases: 0, uncertain_effects: [] }) },
      openHost: async () => {
        const handle = {
          inspect: async () => ({ isolation }),
          close: async () => {
            attempts.push(handle);
            return allowed ? { state: 'closed', outcome: 'cancelled_settled' }
              : { state: 'blocked', outcome: 'uncertain_after_disconnect' };
          },
        };
        handles.push(handle);
        return handle;
      },
    });
    try {
      if (isolation === 'disposable') {
        await assert.rejects(harness.inspectCandidate(request), /plugin_host_close_held/);
        await assert.rejects(harness.inspectCandidate({ ...request, operation_id: 'op-second' }), /plugin_host_close_held/);
      } else {
        await harness.restart(request);
        await assert.rejects(harness.restart({ ...request, operation_id: 'op-second' }), /plugin_host_close_held/);
        await assert.rejects(harness.restart({ ...request, operation_id: 'op-third' }), /plugin_host_close_held/);
      }
      assert.equal(handles.length, 1);
      assert.deepEqual(attempts, [handles[0], handles[0]]);
      await assert.rejects(harness.close(), /plugin_host_close_held/);
      allowed = true;
      await harness.close();
      assert.deepEqual(attempts, [handles[0], handles[0], handles[0], handles[0]]);
      assert.equal(handles.length, 1);
      await harness.close();
      assert.equal(attempts.length, 4);
    } finally { allowed = true; await harness.close(); }
  });
}

test('legacy void close requires and awaits explicit adapter settlement', async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'renulus-plugin-legacy-close-'));
  const release = Promise.withResolvers(), started = Promise.withResolvers();
  let settlementCalls = 0, closed = false;
  const handle = { inspect: async () => ({}), close: async () => {} };
  const harness = createCapabilityPluginHarness({ root,
    authority: { narrow: async () => {}, quiesce: async () => ({ state: 'settled', active_operations: 0,
      pending_permissions: 0, worker_leases: 0, uncertain_effects: [] }) },
    openHost: async () => handle,
  });
  await harness.restart({ operation_id: 'op-legacy', artifacts: [], baseline_tools: [] });
  await assert.rejects(harness.close(), /plugin_host_close_proof_required/);
  handle.settled = async () => { settlementCalls++; started.resolve(); await release.promise; };
  const closing = harness.close().then(() => { closed = true; });
  await started.promise;
  assert.equal(closed, false);
  release.resolve();
  await closing;
  assert.equal(closed, true); assert.equal(settlementCalls, 1);
});
