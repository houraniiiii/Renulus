// SPDX-License-Identifier: MIT
import '../../harness/test/owned-environment.mjs';
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { ManagedRuntime } from 'effect';
import { TestLLM } from '@opencode/ai/testing';
import { openIsolatedStorage, loadMigrationInventory, MARKER, SELECTOR } from '../src/storage/index.ts';
import { inventory } from '../src/storage/schema.ts';
import { openConnectedTarget } from '../src/host/composition.ts';
import { defaultConfiguration } from '../src/dispatch/policy.ts';

const repository = fileURLToPath(new URL('../../..', import.meta.url));
const python = 'C:/Renulus/dev/python/Scripts/python.exe';
const helpersRoot = 'C:/Renulus/dev/helper-assets';
const sha = value => createHash('sha256').update(value).digest('hex');

test('Native learning tools return exact pinned history and refuse message ids outside the run checkpoint', { timeout: 180000 }, async () => {
  const root = mkdtempSync(path.join(tmpdir(), 'renulus-learning-tools-'));
  const script = `
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'runtime'))
from renulus.server import create_app
from renulus.learn.conversation_models import NewConversation
s=create_app(Path(sys.argv[2])).state.services
thread=s.registry['conversations'].create(NewConversation(kind='learning',title='SYNTHETIC tools'))
with s.db.transaction() as c:
 c.execute("INSERT OR REPLACE INTO harness_store_identity VALUES(1,'synthetic-profile','synthetic-domain',1,'4b6fea2875e4f2e3e8a8fee181803e54f7056845')")
print(json.dumps({'database':str(s.paths.database),'thread':thread['identity']['id']}))
`;
  const environment = Object.fromEntries(['SystemRoot', 'WINDIR', 'TEMP', 'TMP'].filter(k => process.env[k]).map(k => [k, process.env[k]])); environment.PATH = path.dirname(python);
  const seeded = spawnSync(python, ['-I', '-X', 'utf8', '-c', script, repository, root], { env: environment, encoding: 'utf8', timeout: 60000 });
  assert.equal(seeded.status, 0, seeded.stderr || seeded.error?.message);
  const { database, thread } = JSON.parse(seeded.stdout);
  const selection = { contract: 'renulus-storage-selector/1', isolation: 'synthetic', profileId: 'synthetic-profile', generation: 1,
    authorityEpoch: 1, writer: 'ts', state: 'active', ownerId: 'synthetic-tools-owner', database: 'state/renulus.sqlite3' };
  writeFileSync(path.join(root, MARKER), JSON.stringify({ contract: 'renulus-synthetic-storage/1', profileId: selection.profileId }));
  writeFileSync(path.join(root, SELECTOR), JSON.stringify(selection));
  mkdirSync(path.join(root, 'state/harness'), { recursive: true });
  const manifest = JSON.parse(readFileSync(path.join(repository, 'packages/contracts/fixtures/harness/paired-store-prepared.json'), 'utf8'));
  manifest.profile_id = selection.profileId; manifest.domain_store.store_id = 'synthetic-domain';
  manifest.domain_store.path = selection.database; manifest.runtime_store.store_id = 'synthetic-runtime'; manifest.runtime_store.path = 'state/harness/opencode.sqlite';
  writeFileSync(path.join(root, 'state/harness/manifest.json'), JSON.stringify(manifest));
  const migrations = loadMigrationInventory(repository), db = new DatabaseSync(database);
  const expectedSchemaHash = inventory(db, migrations).schemaHash; db.close();
  const runtime = ManagedRuntime.make(TestLLM.testLayer()), client = await runtime.runPromise(TestLLM.Test), push = (...items) => runtime.runPromise(client.push(...items));
  const model = { providerId: 'synthetic', modelId: 'scripted', client, configuration: { model: 'synthetic/scripted', providers: { synthetic: {
    package: '@opencode/ai/providers/openai-compatible', settings: { baseURL: 'https://synthetic.invalid/v1' }, models: { scripted: { limit: { context: 128000, output: 4096 } } } } } } };
  const storage = await openIsolatedStorage({ profileRoot: root, selection, migrations, expectedSchemaHash });
  const connected = await openConnectedTarget({ profileRoot: root, storage, availableModels: ['gpt-6.1-sol'], testing: { model: async () => model },
    identity: { profile_id: selection.profileId, domain_store_id: 'synthetic-domain', runtime_store_id: 'synthetic-runtime', authority_epoch: 1, process_generation: 'synthetic-tools' },
    resources: { python, sourceRoot: repository, helpers: { helpers_root: helpersRoot, source_root: repository, cache_root: path.join(root, 'cache') },
      derived: { root: path.join(root, 'derived'), namespace: 'synthetic-tools', library_tombstones: [], memory_tombstones: [] },
      broker: { profile_root: path.join(root, 'broker'), state_root: path.join(root, 'broker/state') } } });
  try {
    const spec = defaultConfiguration({ provider: 'codex', credential_reference: 'synthetic-unused', credential_revision: 0, selected_model: 'gpt-6.1-sol' }, (await connected.inspect()).registry_hash);
    const activated = await connected.configuration.activate({ ...spec, capabilities: ['text', 'tools'] });
    assert.equal(activated.admission_open, true);
    await connected.credentials.activate();
    const send = (revision, draft, text, key) => connected.learning.send({ threadId: thread, expectedRevision: revision, expectedDraftRevision: draft, text, idempotencyKey: key });
    await push(TestLLM.text('SYNTHETIC earlier answer about glomerular filtration', 'answer'));
    const first = await send(1, 0, 'Explain SYNTHETIC filtration.', 'tools-send-1');
    assert.equal(first.state, 'completed');
    const ref = first.answer_reference, last = ref.message_ids.at(-1);
    await push(TestLLM.tool('call-refs', 'renulus_context_refs', {}), TestLLM.tool('call-range', 'renulus_history_range', { first_message_id: ref.input_id, last_message_id: last }));
    await push(TestLLM.tool('call-denied', 'renulus_history_range', { first_message_id: 'message_outside_checkpoint', last_message_id: last }));
    await push(TestLLM.text('SYNTHETIC second answer', 'answer'));
    const second = await send(first.conversation.revision, 1, 'Recall the earlier SYNTHETIC answer.', 'tools-send-2');
    assert.equal(second.state, 'completed');
    const requests = await runtime.runPromise(client.requests()), final = JSON.stringify(requests.at(-1));
    assert.ok(final.includes(ref.sha256) && final.includes(ref.input_id), 'context refs list the pinned answer');
    assert.ok(final.includes('Explain SYNTHETIC filtration.') && final.includes(sha('Explain SYNTHETIC filtration.')), 'exact user text with its digest');
    assert.ok(final.includes('SYNTHETIC earlier answer about glomerular filtration'), 'exact answer text');
    assert.ok(final.includes('learning_tool_failed') || final.includes('unavailable for the current run'), 'outside message id is refused');
  } finally { await connected.close(); await storage.close(); await runtime.dispose(); rmSync(root, { recursive: true, force: true }); }
});
