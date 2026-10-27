// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { spawnSync } from 'node:child_process';
import { DatabaseSync } from 'node:sqlite';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { basename, dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { openIsolatedStorage, previewStorage, loadMigrationInventory, MARKER, SELECTOR } from '../src/storage/index.ts';
import { defaultConfiguration } from '../src/dispatch/policy.ts';
import { digest } from '../src/storage/schema.ts';

test('actual canonical StorageClient worker: Python full schema → config select → reserve/admit → revoke/uncertain → reopen', { timeout: 60000 }, async () => {
  assert.equal(process.versions.node, '26.4.0');
  const repository = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
  const temporary = resolve(tmpdir()), profile = mkdtempSync(join(temporary, 'renulus-dispatch-worker-bf01-'));
  const python = process.env.RENULUS_BACKEND_TEST_PYTHON || 'C:/Renulus/dev/python/Scripts/python.exe';
  let client;
  try {
    const prepared = spawnSync(python, ['-I', '-B', '-X', 'utf8', '-c', `
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'runtime'))
from renulus.server import create_app
s=create_app(sys.argv[2]).state.services
print(json.dumps({'prepared':True,'database':str(s.paths.database)}))
`, repository, profile], { encoding: 'utf8', windowsHide: true, timeout: 45000,
      env: { SystemRoot: process.env.SystemRoot, WINDIR: process.env.WINDIR, TEMP: profile, TMP: profile, PATH: dirname(python) } });
    assert.equal(prepared.status, 0, prepared.stderr || prepared.error?.message);
    const databasePath = JSON.parse(prepared.stdout).database;
    assert.equal(resolve(databasePath), join(profile, 'state', 'renulus.sqlite3'));
    const migrations = loadMigrationInventory(repository);
    const preview = await previewStorage({ databasePath, migrations });
    assert.equal(preview.compatible, true, JSON.stringify(preview.issues));
    const selection = { contract: 'renulus-storage-selector/1', isolation: 'synthetic', profileId: 'dispatch_synthetic_worker', generation: 1,
      authorityEpoch: 1, writer: 'ts', state: 'active', ownerId: 'dispatch_synthetic_owner', database: 'state/renulus.sqlite3' };
    writeFileSync(join(profile, MARKER), JSON.stringify({ contract: 'renulus-synthetic-storage/1', profileId: selection.profileId }));
    writeFileSync(join(profile, SELECTOR), JSON.stringify(selection));
    const options = { profileRoot: profile, selection, migrations, expectedSchemaHash: preview.schemaHash };
    client = await openIsolatedStorage(options);
    const spec = defaultConfiguration({ provider: 'codex', credential_reference: 'protected_reference_only', credential_revision: 1, selected_model: 'gpt-6.1-sol' }, digest('synthetic_registry'));
    spec.capabilities = ['text', 'tools'];
    spec.inputs = [{ kind: 'artifact', name: 'library_plugin', sha256: digest('synthetic_loaded_library') }];
    const { version } = await client.command({ type: 'dispatch.stage', spec, expectedEffective: null, expectedRequested: null, grantEpoch: 0 });
    const inspection = { configuration_version: version, grant_epoch: 0, registry_hash: spec.registry_hash, loaded_inputs: spec.inputs,
      healthy: true, generation_open: false, recovery_open: false, package_acquisition_open: false, mcp_startup_open: false, live_store_writer: false };
    assert.deepEqual(await client.command({ type: 'dispatch.inspect', inspection }), { ready: true });
    await client.command({ type: 'dispatch.close', version, expectedEffective: null, grantEpoch: 0 });
    await client.command({ type: 'dispatch.activate', version, expectedEffective: null,
      settlement: { configuration_version: version, grant_epoch: 0, admission_closed: true, runtime_stopped: true, domain_settled: true } });
    assert.equal((await client.command({ type: 'dispatch.open', inspection })).admission_open, true);
    const fence = { profile_id: selection.profileId, domain_store_id: 'domain', runtime_store_id: 'runtime', authority_epoch: 1,
      process_generation: 'native_process', context_epoch: 0, deletion_epoch: 0, cancellation_epoch: 0 };
    const begin = runId => client.command({ type: 'dispatch.begin', runId, purpose: 'explain', expectedVersion: version, capabilities: ['text', 'tools'],
      availableModels: ['gpt-6.1-sol'], operationModel: null, fence, batchSize: null });
    const sent = await begin('sent'), queued = await begin('queued');
    const proof = { qualification: { id: 'synthetic_evidence', route: sent.route, limits: { input_tokens: 49152, output_tokens: 4096, window_tokens: 57344 },
      capabilities: ['text', 'tools'], limits_revision: 'synthetic_limits', capabilities_revision: 'synthetic_tools', counter_revision: 'synthetic_count_fixture' },
      payload_hash: digest('synthetic_serialized_body'), wire_sha256: digest('synthetic_exact_wire'), input_manifest_sha256: digest('synthetic_native_manifest'),
      body_bytes: 128, input_tokens: 16, output_tokens: 64 };
    const reservation = run => client.command({ type: 'dispatch.reserve', runId: run.run_id, stepId: 'first', requestKind: 'primary', continuationOf: null,
      requiredCapabilities: ['text', 'tools'], fence, proof });
    const first = await reservation(sent), waiting = await reservation(queued);
    assert.equal(first.dispatch_allowed, false);
    assert.equal((await client.command({ type: 'dispatch.admit', permitId: first.permit_id, fence, proof })).dispatch_allowed, true);
    await client.command({ type: 'dispatch.complete', permitId: first.permit_id, outcome: 'uncertain', resultReference: null, failureCode: 'transport_timeout' });
    assert.deepEqual(await client.command({ type: 'dispatch.revoke', capability: 'tools' }), { epoch: 1 });
    await assert.rejects(client.command({ type: 'dispatch.admit', permitId: waiting.permit_id, fence, proof }), { code: 'capability_revoked' });
    await client.close(); client = await openIsolatedStorage(options);
    assert.equal((await client.command({ type: 'dispatch.permit', permitId: first.permit_id })).state, 'uncertain');
    assert.equal((await client.command({ type: 'dispatch.permit', permitId: waiting.permit_id })).state, 'reserved');
    await assert.rejects(client.command({ type: 'dispatch.admit', permitId: first.permit_id, fence, proof }), { code: 'dispatch_already_admitted' });
    await assert.rejects(client.command({ type: 'dispatch.admit', permitId: waiting.permit_id, fence, proof }), { code: 'capability_revoked' });
    await client.command({ type: 'dispatch.complete', permitId: first.permit_id, outcome: 'confirmed', resultReference: 'late_known_receipt', failureCode: null });
    await assert.rejects(client.command({ type: 'dispatch.current', runId: sent.run_id, fence, requiredCapabilities: [], permitId: first.permit_id }), { code: 'grant_epoch_changed' });

    await client.command({ type: 'dispatch.complete', permitId: waiting.permit_id, outcome: 'cancelled_before_send', resultReference: null, failureCode: null });
    const parent = await client.command({ type: 'dispatch.begin', runId: 'overlapping_root', purpose: 'explain', expectedVersion: version,
      capabilities: ['text'], availableModels: ['gpt-6.1-sol'], operationModel: null, fence, batchSize: null });
    const child = await client.command({ type: 'dispatch.child', runId: 'overlapping_child', parentId: parent.run_id, purpose: 'evidence-review',
      capabilities: ['text'], operationModel: null, fence });
    const queuedPermit = run => client.command({ type: 'dispatch.reserve', runId: run.run_id, stepId: 'overlapping_step',
      requestKind: run.parent_id ? 'child' : 'primary', continuationOf: null, requiredCapabilities: ['text'], fence, proof });
    const parentPermit = await queuedPermit(parent), childPermit = await queuedPermit(child);
    // Submit both before observing either result: the canonical worker must serialize admission by root.
    const admissions = await Promise.allSettled([parentPermit, childPermit].map(permit =>
      client.command({ type: 'dispatch.admit', permitId: permit.permit_id, fence, proof })));
    assert.equal(admissions[0].status, 'fulfilled');
    assert.equal(admissions[0].value.dispatch_allowed, true);
    assert.equal(admissions[1].status, 'rejected');
    assert.equal(admissions[1].reason.code, 'dispatch_uncertain');
    await client.command({ type: 'dispatch.complete', permitId: parentPermit.permit_id, outcome: 'uncertain', resultReference: null, failureCode: 'transport_timeout' });
    await client.close(); client = await openIsolatedStorage(options);
    await assert.rejects(client.command({ type: 'dispatch.admit', permitId: childPermit.permit_id, fence, proof }), { code: 'dispatch_uncertain' });
    assert.equal((await client.command({ type: 'dispatch.permit', permitId: childPermit.permit_id })).state, 'reserved');
    await client.command({ type: 'dispatch.complete', permitId: parentPermit.permit_id, outcome: 'confirmed', resultReference: 'overlap_late_receipt', failureCode: null });
    assert.equal((await client.command({ type: 'dispatch.admit', permitId: childPermit.permit_id, fence, proof })).dispatch_allowed, true);
    await client.command({ type: 'dispatch.complete', permitId: childPermit.permit_id, outcome: 'confirmed', resultReference: 'child_receipt', failureCode: null });
    await client.close(); client = undefined;
    // Protected dispatch metadata is correctly absent from the public export/page allowlist.
    const observed = new DatabaseSync(databasePath, { readOnly: true });
    try { assert.equal(observed.prepare('SELECT count(*) AS n FROM harness_configuration_attempts').get().n, 4); }
    finally { observed.close(); } // Reopen/reconciliation never minted another network attempt.
  } finally {
    await client?.close();
    assert.equal(dirname(profile), temporary); assert.match(basename(profile), /^renulus-dispatch-worker-bf01-/);
    rmSync(profile, { recursive: true, force: true });
  }
});
