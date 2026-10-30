// SPDX-License-Identifier: MIT
import '../../harness/test/owned-environment.mjs';
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { spawnSync } from 'node:child_process';
import { DatabaseSync } from 'node:sqlite';
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createLearningGateway } from '../../harness/src/learning-gateway.ts';
import { openIsolatedStorage, loadMigrationInventory, MARKER, SELECTOR } from '../src/storage/index.ts';
import { inventory } from '../src/storage/schema.ts';
import { openConnectedTarget } from '../src/host/composition.ts';
import { defaultConfiguration } from '../src/dispatch/policy.ts';
import { syntheticEvidence, scriptedTransport } from './support/synthetic-route.mjs';

const repository = fileURLToPath(new URL('../../..', import.meta.url));
const python = 'C:/Renulus/dev/python/Scripts/python.exe';
const MODEL = 'gpt-6.1-sol', CONNECTION = { provider: 'codex', credential_reference: 'synthetic-unused', credential_revision: 0, selected_model: MODEL };

test('connected compaction dispatches once, preserves recent input and blocks failed summaries', { timeout: 240000 }, async () => {
  const root = mkdtempSync(path.join(tmpdir(), 'renulus-connected-compaction-')), gateways = [];
  const script = `
import sys
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'runtime'))
from renulus.server import create_app
s=create_app(Path(sys.argv[2])).state.services
with s.db.transaction() as c:
 c.execute("INSERT OR REPLACE INTO harness_store_identity VALUES(1,'synthetic-profile','synthetic-domain',1,'4b6fea2875e4f2e3e8a8fee181803e54f7056845')")
print(str(s.paths.database))
`;
  const env = Object.fromEntries(['SystemRoot', 'WINDIR', 'TEMP', 'TMP'].filter(k => process.env[k]).map(k => [k, process.env[k]]));
  env.PATH = path.dirname(python);
  const prepared = spawnSync(python, ['-I', '-X', 'utf8', '-c', script, repository, root], { env, encoding: 'utf8', timeout: 60000 });
  assert.equal(prepared.status, 0, prepared.stderr || prepared.error?.message);
  const selection = { contract: 'renulus-storage-selector/1', isolation: 'synthetic', profileId: 'synthetic-profile', generation: 1,
    authorityEpoch: 1, writer: 'ts', state: 'active', ownerId: 'synthetic-compaction-owner', database: 'state/renulus.sqlite3' };
  writeFileSync(path.join(root, MARKER), JSON.stringify({ contract: 'renulus-synthetic-storage/1', profileId: selection.profileId }));
  writeFileSync(path.join(root, SELECTOR), JSON.stringify(selection));
  mkdirSync(path.join(root, 'state/harness'), { recursive: true });
  const manifest = JSON.parse(readFileSync(path.join(repository, 'packages/contracts/fixtures/harness/paired-store-prepared.json'), 'utf8'));
  manifest.profile_id = selection.profileId; manifest.domain_store.store_id = 'synthetic-domain';
  manifest.domain_store.path = selection.database; manifest.runtime_store.store_id = 'synthetic-runtime'; manifest.runtime_store.path = 'state/harness/opencode.sqlite';
  writeFileSync(path.join(root, 'state/harness/manifest.json'), JSON.stringify(manifest));
  const migrations = loadMigrationInventory(repository), db = new DatabaseSync(prepared.stdout.trim());
  const expectedSchemaHash = inventory(db, migrations).schemaHash; db.close();
  const storage = await openIsolatedStorage({ profileRoot: root, selection, migrations, expectedSchemaHash });
  const base = syntheticEvidence(CONNECTION, MODEL).evidence;
  const evidence = { ...base, metadata: { ...base.metadata, capabilities: ['text', 'tools'], limits: { input_tokens: 7500, output_tokens: 512, window_tokens: 9000 } } };
  const scripted = scriptedTransport(MODEL);
  const connected = await openConnectedTarget({ profileRoot: root, storage,
    identity: { profile_id: selection.profileId, domain_store_id: 'synthetic-domain', runtime_store_id: 'synthetic-runtime', authority_epoch: 1, process_generation: 'synthetic-compaction' },
    availableModels: [MODEL], evidence: [evidence], testing: { transport: scripted.transport, model: async domain => {
      const gateway = await createLearningGateway(domain); gateways.push(gateway);
      return { providerId: 'renulus', modelId: 'admission', client: gateway.client, preparePrimary: gateway.preparePrimary,
        configuration: { model: 'renulus/admission', providers: { renulus: { package: '@opencode/ai/providers/openai-compatible',
          settings: { baseURL: 'https://denied.invalid/v1' }, models: { admission: { limit: { context: 1, output: 1 } } } } } } };
    } }, resources: { python, sourceRoot: repository,
      helpers: { helpers_root: 'C:/Renulus/dev/helper-assets', source_root: repository, cache_root: path.join(root, 'cache') },
      derived: { root: path.join(root, 'derived'), namespace: 'synthetic-compaction', library_tombstones: [], memory_tombstones: [] },
      broker: { profile_root: path.join(root, 'broker'), state_root: path.join(root, 'broker/state') } } });
  try {
    const registry = await connected.inspect(), spec = defaultConfiguration(CONNECTION, registry.registry_hash);
    spec.capabilities = ['text', 'tools'];
    spec.context = { requested_window_tokens: 9000, requested_decimal_tokens: 9000, reserve_tokens: 256 };
    for (const role of spec.roles) role.output_tokens = 512;
    spec.roles.find(r => r.purpose === 'memory-extraction').enabled = false;
    await connected.configuration.activate(spec);
    const conversation = await storage.command({ type: 'learning.create', request: { kind: 'learning', title: 'SYNTHETIC connected compaction',
      project_id: null, topic_id: null, temporary: false, teaching_style: 'direct', text: '', teaching_case_id: null }, idempotencyKey: 'compaction-create' });
    const threadId = conversation.identity.id;
    let draft = 0;
    const pad = (label, size = 400) => 'SYNTHETIC ' + label + ' ' + 'filtration '.repeat(size);
    const send = async label => {
      const view = await storage.command({ type: 'learning.view', threadId });
      const result = await connected.learning.send({ threadId, expectedRevision: view.conversation.revision, expectedDraftRevision: draft,
        text: pad(label, label === 'four' ? 800 : 400), idempotencyKey: 'connected-' + label }); draft++; return result;
    };
    scripted.push('SYNTHETIC answer one', 'SYNTHETIC answer two');
    await send('one'); await send('two');
    scripted.push('SYNTHETIC concise educational summary', 'SYNTHETIC answer three');
    const third = await send('three');
    assert.equal(third.state, 'completed');
    const last = JSON.stringify(scripted.sent.at(-1).request);
    assert.ok(last.includes('renulus-context-summary/1') && last.includes('SYNTHETIC concise educational summary'));
    assert.ok(last.includes(pad('three'))); assert.ok(!last.includes(pad('one')));
    const ledger = new DatabaseSync(path.join(root, 'state/renulus.sqlite3'), { readOnly: true });
    try {
      assert.equal(ledger.prepare("SELECT COUNT(*) AS n FROM harness_configuration_runs WHERE purpose='compaction'").get().n, 1);
      assert.equal(ledger.prepare("SELECT COUNT(*) AS n FROM harness_configuration_attempts WHERE dispatch_purpose='compaction' AND state='confirmed'").get().n, 1);
    } finally { ledger.close(); }
    scripted.push('');
    await assert.rejects(send('four'));
    const failed = await connected.learning.native.observe(third.answer_reference.runtime.session_id, { limit: 50, order: 'asc' });
    assert.ok(JSON.stringify(failed).includes('context_compaction_blocked'), 'failed summary blocks compaction explicitly');
    assert.equal(scripted.sent.length, 5, 'failed compaction admits no primary answer');
  } finally { await connected.close(); for (const gateway of gateways) await gateway.close(); await storage.close(); }
});
