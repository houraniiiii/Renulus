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
import { ManagedRuntime } from 'effect';
import { TestLLM } from '@opencode/ai/testing';
import { openIsolatedStorage, loadMigrationInventory, MARKER, SELECTOR } from '../src/storage/index.ts';
import { inventory } from '../src/storage/schema.ts';
import { openConnectedTarget } from '../src/host/composition.ts';
import { createEngineArtifacts } from '../src/workers/artifacts.ts';
import { defaultConfiguration } from '../src/dispatch/policy.ts';

const repository = fileURLToPath(new URL('../../..', import.meta.url));
const python = 'C:/Renulus/dev/python/Scripts/python.exe';
const helpersRoot = 'C:/Renulus/dev/helper-assets';
const DOC = 'doc_' + '1'.repeat(32), REV = 'rev_' + '2'.repeat(32), PASSAGE = 'passage_' + '3'.repeat(32);

/** Synthetic profile with one ready Library passage (same shape as plugin-journey.test.mjs). */
function fixture() {
  const root = mkdtempSync(path.join(tmpdir(), 'renulus-registry-journey-'));
  const script = `
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'runtime'))
from renulus.server import create_app
s=create_app(Path(sys.argv[2])).state.services
with s.db.transaction() as c:
 c.execute("INSERT OR REPLACE INTO harness_store_identity VALUES(1,'synthetic-profile','synthetic-domain',1,'4b6fea2875e4f2e3e8a8fee181803e54f7056845')")
 rights={key:True for key in ['display','cache','index','embedding','model_input','derivation']}
 rights.update(licence='CC-BY-4.0',permission_reference='SYNTHETIC',attribution='Synthetic test author')
 metadata={'source_id':'SYNTHETIC','publication_status':'final','content_reviewed':True,'latest_final_verified':True,'excluded_pages':[]}
 c.execute("INSERT INTO knowledge_documents VALUES(?,?,?,'personal-library',NULL,0,?,?,NULL,?,?)",(sys.argv[3],'SYNTHETIC Library','SYNTHETIC',sys.argv[4],sys.argv[4],'2026-10-27T00:00:00Z','2026-10-27T00:00:00Z'))
 c.execute("INSERT INTO knowledge_revisions VALUES(?,?,1,'ready',?,'text/plain',40,NULL,?,?,NULL,NULL,NULL,?,?)",(sys.argv[4],sys.argv[3],'1'*64,json.dumps(metadata),json.dumps(rights),'2026-10-27T00:00:00Z','2026-10-27T00:00:00Z'))
 c.execute("INSERT INTO knowledge_passages VALUES(?,?,0,?,?,?,'[]')",(sys.argv[5],sys.argv[4],'SYNTHETIC canonical Library AKI passage','SYNTHETIC canonical Library AKI passage',json.dumps([{'page':1,'char_span':[0,40]}])))
print(str(s.paths.database))
`;
  const environment = Object.fromEntries(['SystemRoot', 'WINDIR', 'TEMP', 'TMP'].filter(k => process.env[k]).map(k => [k, process.env[k]]));
  environment.PATH = path.dirname(python);
  const result = spawnSync(python, ['-I', '-X', 'utf8', '-c', script, repository, root, DOC, REV, PASSAGE], { env: environment, encoding: 'utf8', timeout: 60000 });
  assert.equal(result.status, 0, result.stderr || result.error?.message);
  const selection = { contract: 'renulus-storage-selector/1', isolation: 'synthetic', profileId: 'synthetic-profile', generation: 1,
    authorityEpoch: 1, writer: 'ts', state: 'active', ownerId: 'synthetic-registry-owner', database: 'state/renulus.sqlite3' };
  writeFileSync(path.join(root, MARKER), JSON.stringify({ contract: 'renulus-synthetic-storage/1', profileId: selection.profileId }));
  writeFileSync(path.join(root, SELECTOR), JSON.stringify(selection));
  mkdirSync(path.join(root, 'state/harness'), { recursive: true });
  const manifest = JSON.parse(readFileSync(path.join(repository, 'packages/contracts/fixtures/harness/paired-store-prepared.json'), 'utf8'));
  manifest.profile_id = selection.profileId; manifest.domain_store.store_id = 'synthetic-domain';
  manifest.domain_store.path = selection.database; manifest.runtime_store.store_id = 'synthetic-runtime'; manifest.runtime_store.path = 'state/harness/opencode.sqlite';
  writeFileSync(path.join(root, 'state/harness/manifest.json'), JSON.stringify(manifest));
  const migrations = loadMigrationInventory(repository), db = new DatabaseSync(result.stdout.trim());
  const expectedSchemaHash = inventory(db, migrations).schemaHash; db.close();
  return { root, writer: { profileRoot: root, selection, migrations, expectedSchemaHash },
    identity: { profile_id: selection.profileId, domain_store_id: 'synthetic-domain', runtime_store_id: 'synthetic-runtime', authority_epoch: 1, process_generation: 'synthetic-registry' } };
}
async function scriptedModel() {
  const runtime = ManagedRuntime.make(TestLLM.testLayer()), client = await runtime.runPromise(TestLLM.Test);
  const model = { providerId: 'synthetic', modelId: 'scripted', client,
    configuration: { model: 'synthetic/scripted', providers: { synthetic: { package: '@opencode/ai/providers/openai-compatible',
      settings: { baseURL: 'https://synthetic.invalid/v1' }, models: { scripted: { limit: { context: 128000, output: 4096 } } } } } } };
  return { model, push: (...items) => runtime.runPromise(client.push(...items)), requests: () => runtime.runPromise(client.requests()), close: () => runtime.dispose() };
}


const EXPECTED = ['opencode_models', 'opencode_session_rename', 'question', 'skill', 'subagent', 'webfetch', 'websearch',
  'renulus_library_retrieve', 'renulus_library_citation', 'renulus_source_read', 'renulus_note_read', 'renulus_note_propose',
  'renulus_project_read', 'renulus_memory_recall', 'renulus_find', 'renulus_evidence_search', 'renulus_evidence_fetch', 'renulus_study_help',
  'renulus_practice_propose', 'renulus_plan_propose', 'renulus_updates_read', 'renulus_context_refs', 'renulus_history_range'].sort();
const DEVELOPER = /^(read|glob|grep|edit|write|patch|shell|execute|browser.*|opencode_worktree.*|opencode_session_move)$/;
const todo = [];

test('every doctor tool is registered, granted and callable under the default configuration; revoke narrows exactly one', { timeout: 240000 }, async () => {
  const f = fixture(), m = await scriptedModel();
  const storage = await openIsolatedStorage(f.writer);
  const connected = await openConnectedTarget({ profileRoot: f.root, storage, identity: f.identity, availableModels: ['gpt-6.1-sol'],
    testing: { model: async () => m.model },
    resources: { python, sourceRoot: repository, helpers: { helpers_root: helpersRoot, source_root: repository, cache_root: path.join(f.root, 'cache') },
      derived: { root: path.join(f.root, 'derived'), namespace: 'synthetic-registry', library_tombstones: [], memory_tombstones: [] },
      broker: { profile_root: path.join(f.root, 'broker'), state_root: path.join(f.root, 'broker/state') } } });
  try {
    const artifacts = createEngineArtifacts(connected.worker.channel, connected.worker.ready.capacity.max_chunk_bytes);
    const binding = { operation_id: 'synthetic-stage', attempt_id: '1' };
    const input = await artifacts.upload(Buffer.from(JSON.stringify({ passages: [{ passage_id: PASSAGE, text: 'SYNTHETIC AKI kidney injury Library.' }] })), binding, ['read'], Date.now() + 120000);
    const output = artifacts.output(16384, Date.now() + 120000);
    try { await artifacts.run('library.stage', { artifact_handle: input.artifact_handle, artifact_revision: input.artifact_revision,
      offset: 0, length: input.bytes, document_id: DOC, revision_id: REV, output }, binding); }
    finally { await artifacts.release(input.artifact_handle, binding); await artifacts.release(output.artifact_handle, binding); }
    const registry = await connected.inspect();
    await connected.configuration.activate(defaultConfiguration({ provider: 'codex', credential_reference: 'synthetic-unused', credential_revision: 0,
      selected_model: 'gpt-6.1-sol' }, registry.registry_hash));
    await connected.credentials.activate();
    const chat = await storage.command({ type: 'learning.create', request: { kind: 'learning', title: 'SYNTHETIC registry', temporary: false,
      project_id: null, topic_id: null, teaching_style: 'direct', text: '', teaching_case_id: null }, idempotencyKey: 'registry-create' });
    const thread = chat.identity.id;
    let revision = chat.revision, draft = 0, n = 0;
    const send = async (text) => {
      const sent = await connected.learning.send({ threadId: thread, expectedRevision: revision, expectedDraftRevision: draft, text, idempotencyKey: 'registry-' + ++n });
      assert.equal(sent.state, 'completed'); revision = sent.conversation.revision; draft++; return sent;
    };
    const toolStates = async () => Object.fromEntries((await connected.learning.range(thread)).messages.flatMap(x => x.content ?? [])
      .filter(part => part.type === 'tool').map(part => [part.name, part.state]));

    // Part A: the final native tool snapshot is exactly the doctor set.
    await m.push(TestLLM.text('SYNTHETIC first answer', 'answer'));
    const first = await send('SYNTHETIC register.');
    const names = (await m.requests())[0].tools.map(t => t.name).sort();
    const missing = EXPECTED.filter(name => !names.includes(name)); todo.push(...missing);
    assert.deepEqual(names.filter(name => !DEVELOPER.test(name) && !EXPECTED.includes(name)), [], 'unexpected tool');
    assert.deepEqual(names.filter(name => DEVELOPER.test(name)), [], 'no developer tool');
    assert.deepEqual(todo, [], 'tools missing from the registry: ' + todo.join(','));

    // The default configuration pins every doctor permission into the run.
    const snapshot = await storage.command({ type: 'dispatch.snapshot' });
    const effective = await storage.command({ type: 'dispatch.configuration', version: snapshot.effective });
    for (const id of connected.grantable()) assert.ok(effective.capabilities.includes(id), id);

    // Part B: one scripted call per lightweight tool; value is the expected tool state.
    const ref = first.answer_reference, last = ref.message_ids.at(-1);
    const calls = [
      ['renulus_library_retrieve', { query: 'AKI', limit: 1 }, 'completed'],
      ['renulus_library_citation', { document_id: DOC, document_revision: REV, passage_id: PASSAGE, page: 1 }, 'completed'],
      ['renulus_source_read', { reference: { target: { type: 'library_revision', id: REV }, locator: null } }, 'error'],
      ['renulus_note_read', { reference: { target: { type: 'note_revision', id: 'note_revision_absent' }, locator: null } }, 'error'],
      ['renulus_note_propose', { title: 'SYNTHETIC note', text: 'SYNTHETIC body' }, 'completed'],
      ['renulus_project_read', { project_id: 'project_absent' }, 'error'],
      ['renulus_memory_recall', { query: 'AKI' }, 'completed'],
      ['renulus_find', { query: 'SYNTHETIC' }, 'completed'],
      ['renulus_study_help', { kind: 'hint' }, 'error'],
      ['renulus_practice_propose', { title: 'SYNTHETIC set', focus: 'AKI', count: 5 }, 'completed'],
      ['renulus_plan_propose', {}, 'completed'],
      ['renulus_updates_read', {}, 'completed'],
      ['renulus_context_refs', {}, 'completed'],
      ['renulus_history_range', { first_message_id: ref.input_id, last_message_id: last }, 'completed'],
      ['opencode_models', {}, 'completed'],
      ['opencode_session_rename', { title: 'SYNTHETIC renamed' }, 'completed'],
    ];
    await m.push(...calls.map(([name, input]) => TestLLM.tool('call-' + name, name, input)), TestLLM.text('SYNTHETIC all tools called', 'answer'));
    await send('Call every SYNTHETIC tool.');
    const states = await toolStates();
    for (const [name, , expected] of calls) assert.equal(states[name]?.status, expected, name + ' ' + JSON.stringify(states[name]));

    // Part C: revoking one permission narrows a pinned run to exactly that tool's grant; every tool resolves its grants from this pin.
    const context = await storage.command({ type: 'study.context' });
    const pinned = await storage.command({ type: 'dispatch.begin', runId: 'registry_run_1', purpose: 'explain', expectedVersion: snapshot.effective,
      capabilities: [...effective.capabilities], availableModels: ['gpt-6.1-sol'], operationModel: null, batchSize: null,
      fence: { ...f.identity, context_epoch: context.epoch, deletion_epoch: context.policyRevision, cancellation_epoch: 0 } });
    assert.ok(pinned.effective_capabilities.includes('renulus.find'));
    await storage.command({ type: 'dispatch.revoke', capability: 'renulus.find' });
    const narrowed = (await storage.command({ type: 'dispatch.run', runId: 'registry_run_1' })).effective_capabilities;
    assert.deepEqual(pinned.effective_capabilities.filter(id => !narrowed.includes(id)), ['renulus.find']);
    assert.ok(narrowed.includes('renulus.plan.propose') && narrowed.includes('renulus.memory.recall'));
  } finally { await connected.close(); await storage.close(); await m.close(); }
});
