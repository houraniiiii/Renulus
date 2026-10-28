// SPDX-License-Identifier: MIT
import '../../harness/test/owned-environment.mjs';
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { spawnSync } from 'node:child_process';
import { DatabaseSync } from 'node:sqlite';
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { ManagedRuntime } from 'effect';
import { TestLLM } from '@opencode/ai/testing';
import { openSavedLearningTarget } from '../src/host/learning.ts';
import { openIsolatedStorage } from '../src/storage/index.ts';
import { MARKER, SELECTOR } from '../src/storage/ownership.ts';
import { inventory, loadMigrationInventory } from '../src/storage/schema.ts';
import { effectiveCapacity, legacyContextPreview, requireProfile } from '../src/domain/learning/context.ts';
import { createLearningTools, HISTORY_PERMISSION } from '../src/domain/learning/tools.ts';

const repository = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const python = 'C:/Renulus/dev/python/Scripts/python.exe';

test('Context profiles map decimal windows; 256K is refused below a verified 256000 route', () => {
  assert.deepEqual(legacyContextPreview(131072), { status: 'mapped', requested_decimal_tokens: 128000 });
  assert.deepEqual(legacyContextPreview(262144), { status: 'mapped', requested_decimal_tokens: 256000 });
  assert.deepEqual(legacyContextPreview(57344), { status: 'preserved', requested_decimal_tokens: 57344 });
  assert.equal(legacyContextPreview(200000).status, 'needs_validation');
  assert.equal(effectiveCapacity(256000, 128000), 128000);
  assert.throws(() => requireProfile(256000, 128000), { code: 'context_window_unsupported' });
  assert.doesNotThrow(() => requireProfile(128000, 128000));
});

test('Compaction summarises older groups, reinjects the recent exchange, keeps exact history readable and blocks bad summaries', { timeout: 120000 }, async () => {
  const root = mkdtempSync(join(tmpdir(), 'renulus-context-compaction-')), profile = join(root, 'profile');
  let storage, target, runtime;
  try {
    const migrations = loadMigrationInventory(repository);
    const script = `
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'runtime'))
from renulus.server import create_app
from renulus.learn.conversation_models import NewConversation
s=create_app(Path(sys.argv[2])).state.services
thread=s.registry['conversations'].create(NewConversation(kind='learning',title='SYNTHETIC compaction'))
with s.db.transaction() as c:
 c.execute("INSERT OR REPLACE INTO harness_store_identity VALUES(1,'synthetic-profile','synthetic-domain-store',1,'4b6fea2875e4f2e3e8a8fee181803e54f7056845')")
print(json.dumps({'database':str(s.paths.database),'thread':thread['identity']['id']}))
`;
    const env = Object.fromEntries(['SystemRoot', 'WINDIR', 'TEMP', 'TMP'].filter(k => process.env[k]).map(k => [k, process.env[k]])); env.PATH = dirname(python);
    const prepared = spawnSync(python, ['-I', '-X', 'utf8', '-c', script, repository, profile], { encoding: 'utf8', env, timeout: 60000 });
    assert.equal(prepared.status, 0, prepared.stderr); const fixture = JSON.parse(prepared.stdout);
    const db = new DatabaseSync(fixture.database), expectedSchemaHash = inventory(db, migrations).schemaHash; db.close();
    const selection = { contract: 'renulus-storage-selector/1', isolation: 'synthetic', profileId: 'synthetic-profile', generation: 1,
      authorityEpoch: 1, writer: 'ts', state: 'active', ownerId: 'synthetic-compaction-owner', database: 'state/renulus.sqlite3' };
    writeFileSync(join(profile, MARKER), JSON.stringify({ contract: 'renulus-synthetic-storage/1', profileId: 'synthetic-profile' }));
    writeFileSync(join(profile, SELECTOR), JSON.stringify(selection));
    const manifest = JSON.parse(readFileSync(join(repository, 'packages/contracts/fixtures/harness/paired-store-prepared.json'), 'utf8'));
    manifest.domain_store.path = 'state/renulus.sqlite3'; manifest.runtime_store.store_id = 'synthetic-store'; manifest.runtime_store.path = 'state/harness/opencode.sqlite';
    mkdirSync(join(profile, 'state/harness'), { recursive: true }); writeFileSync(join(profile, 'state/harness/manifest.json'), JSON.stringify(manifest));
    storage = await openIsolatedStorage({ profileRoot: profile, selection, migrations, expectedSchemaHash });
    runtime = ManagedRuntime.make(TestLLM.testLayer()); const client = await runtime.runPromise(TestLLM.Test);
    const model = { providerId: 'synthetic', modelId: 'compaction', client, configuration: { model: 'synthetic/compaction', providers: { synthetic: {
      package: '@opencode/ai/providers/openai-compatible', settings: { baseURL: 'https://synthetic.invalid/v1' }, models: { compaction: { limit: { context: 128000, output: 4096 } } } } } } };
    let capacity = 1e9, summary = 'SYNTHETIC summary of the earlier filtration discussion', current = true; const summarised = [];
    const context = { count: async request => JSON.stringify({ system: request.system, messages: request.messages }).length, capacity: async () => capacity,
      summarise: async input => { summarised.push(input); return summary; }, isCurrent: async () => current };
    target = await openSavedLearningTarget({ storage, model: async () => model, library: { query: async () => [] }, context,
      harness: { root: profile, profileId: 'synthetic-profile', storeId: 'synthetic-store', domainStoreId: 'synthetic-domain-store',
        domainPath: 'state/renulus.sqlite3', processGeneration: 'synthetic-compaction-process' } });
    await target.native.activateStores(); await target.native.activate('synthetic-compaction');
    const threadId = fixture.thread, pad = label => `SYNTHETIC ${label} ` + 'filtration '.repeat(150);
    const requests = async () => await runtime.runPromise(client.requests());
    let completed = 0;
    const send = async (label, key) => { await runtime.runPromise(client.push(TestLLM.text(`SYNTHETIC answer ${label}`, 'answer')));
      const { conversation } = await storage.command({ type: 'learning.view', threadId });
      const receipt = await target.send({ threadId, expectedRevision: conversation.revision, expectedDraftRevision: completed, text: pad(label), idempotencyKey: key }); completed++; return receipt; };
    const first = await send('one', 'compaction-1'); await send('two', 'compaction-2');
    assert.equal(summarised.length, 0, 'under the window nothing is summarised');
    const measured = await requests(); capacity = JSON.stringify({ system: measured[1].system, messages: measured[1].messages }).length + 300;
    const third = await send('three', 'compaction-3');
    assert.equal(third.state, 'completed'); assert.equal(summarised.length, 1);
    assert.ok(first.answer_reference.message_ids.every(id => summarised[0].coveredMessageIds.includes(id)), 'covered ids name the older answer');
    const final = JSON.stringify((await requests()).at(-1));
    assert.ok(final.includes('renulus-context-summary/1') && final.includes(summary), 'validated summary with receipt is reinjected');
    assert.ok(final.includes(pad('three')), 'recent exchange is reinjected exactly');
    assert.ok(!final.includes(pad('one')), 'older exact text left the model window');
    // The older exact messages stay readable through the bounded history tool.
    const view = await storage.command({ type: 'learning.view', threadId });
    const tools = createLearningTools({ references: async () => view.references, range: (id, input) => target.range(id, input),
      resolve: async () => ({ operationId: 'o', attemptId: '1', sessionId: 's', threadId, grants: [HISTORY_PERMISSION],
        checkpoint: { history: view.references.map(r => ({ runId: r.reference.run_id })), consumed: [], memory: [] } }), check: async () => {} });
    const firstRef = first.answer_reference;
    const range = await tools.historyRange({ first_message_id: firstRef.input_id, last_message_id: firstRef.message_ids.at(-1) }, { sessionID: 's', id: 'c' }, new AbortController().signal);
    assert.equal(range.messages[0].text, pad('one')); assert.equal(range.messages.at(-1).text, 'SYNTHETIC answer one');
    await assert.rejects(tools.historyRange({ first_message_id: 'message_outside', last_message_id: firstRef.input_id }, { sessionID: 's', id: 'c' }, new AbortController().signal), { code: 'history_range_denied' });
    // Empty or stale summaries block the request before any model call.
    const before = (await requests()).length; summary = '';
    await assert.rejects(send('four', 'compaction-4'));
    summary = 'SYNTHETIC stale summary'; current = false;
    await assert.rejects(send('five', 'compaction-5'));
    assert.equal((await requests()).length, before, 'blocked compaction never reaches the model');
  } finally { await target?.close(); await runtime?.dispose(); await storage?.close(); rmSync(root, { recursive: true, force: true }); }
});
