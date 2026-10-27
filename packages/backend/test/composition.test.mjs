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
import { openTargetFacade } from '../src/http/target.ts';
import { createEngineArtifacts } from '../src/workers/artifacts.ts';
import { defaultConfiguration } from '../src/dispatch/policy.ts';

const repository = fileURLToPath(new URL('../../..', import.meta.url));
const python = 'C:/Renulus/dev/python/Scripts/python.exe';
const helpersRoot = 'C:/Renulus/dev/helper-assets';
const DOC = 'doc_' + '1'.repeat(32), REV = 'rev_' + '2'.repeat(32), PASSAGE = 'passage_' + '3'.repeat(32);
const phrase = 'SYNTHETIC native-only HTTP [literal.*%_needle]';
function fixture() {
  const root = mkdtempSync(path.join(tmpdir(), 'renulus-composition-'));
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
    authorityEpoch: 1, writer: 'ts', state: 'active', ownerId: 'synthetic-composition-owner', database: 'state/renulus.sqlite3' };
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
    identity: { profile_id: selection.profileId, domain_store_id: 'synthetic-domain', runtime_store_id: 'synthetic-runtime', authority_epoch: 1, process_generation: 'synthetic-composition' } };
}
async function countedModel() {
  const runtime = ManagedRuntime.make(TestLLM.testLayer()), client = await runtime.runPromise(TestLLM.Test);
  const model = { providerId: 'synthetic', modelId: 'counted-learning', client,
    configuration: { model: 'synthetic/counted-learning', providers: { synthetic: { package: '@opencode/ai/providers/openai-compatible',
      settings: { baseURL: 'https://synthetic.invalid/v1' }, models: { 'counted-learning': { limit: { context: 128000, output: 4096 } } } } } } };
  return { model, push: item => runtime.runPromise(client.push(item)), count: async () => (await runtime.runPromise(client.requests())).length,
    close: () => runtime.dispose() };
}

test('connected HTTP native Library/citation/receipt/history/Finder/archive/delete and reopen use one real canonical worker', { timeout: 180000 }, async () => {
  const f = fixture(), m = await countedModel();
  let facade, connected, storage;
  const options = { profileRoot: f.root, identity: f.identity, availableModels: ['gpt-6.1-sol'], testing: { model: async () => m.model },
    resources: { python, sourceRoot: repository, helpers: { helpers_root: helpersRoot, source_root: repository, cache_root: path.join(f.root, 'cache') },
      derived: { root: path.join(f.root, 'derived'), namespace: 'synthetic-composition', library_tombstones: [], memory_tombstones: [] },
      broker: { profile_root: path.join(f.root, 'broker'), state_root: path.join(f.root, 'broker/state') } } };
  async function open() {
    storage = await openIsolatedStorage(f.writer); connected = await openConnectedTarget({ ...options, storage });
    facade = await openTargetFacade({ port: 0, token: 'synthetic-composition-token', storage, learning: connected.learning,
      plugins: connected.plugins, credentials: connected.credentials, configuration: connected.configuration, inspect: connected.inspect,
      memory: connected.memory, settlePlugins: connected.close });
  }
  async function api(method, route, body, key) {
    const response = await fetch(`http://127.0.0.1:${facade.port}/api/v1${route}`, { method,
      headers: { 'x-renulus-token': 'synthetic-composition-token', ...(body === undefined ? {} : { 'content-type': 'application/json' }), ...(key ? { 'idempotency-key': key } : {}) },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
    const text = await response.text();
    assert.equal(response.status < 400, true, method + ' ' + route + ' ' + text);
    return response.headers.get('content-type').includes('event-stream') ? text : JSON.parse(text);
  }
  try {
    await open();
    const artifacts = createEngineArtifacts(connected.worker.channel, connected.worker.ready.capacity.max_chunk_bytes);
    const binding = { operation_id: 'synthetic-stage', attempt_id: '1' };
    const input = await artifacts.upload(Buffer.from(JSON.stringify({ passages: [{ passage_id: PASSAGE, text: 'SYNTHETIC AKI kidney injury Library.' }] })), binding, ['read'], Date.now() + 120000);
    const output = artifacts.output(16384, Date.now() + 120000);
    try { await artifacts.run('library.stage', { artifact_handle: input.artifact_handle, artifact_revision: input.artifact_revision,
      offset: 0, length: input.bytes, document_id: DOC, revision_id: REV, output }, binding); }
    finally { await artifacts.release(input.artifact_handle, binding); await artifacts.release(output.artifact_handle, binding); }
    const registry = await api('GET', '/runtime/registry');
    const spec = defaultConfiguration({ provider: 'codex', credential_reference: 'synthetic-unused', credential_revision: 0, selected_model: 'gpt-6.1-sol' }, registry.registry_hash);
    spec.capabilities = ['text', 'tools'];
    assert.equal((await api('POST', '/runtime/configuration', { spec })).admission_open, true);
    const credentials = await api('POST', '/settings/credentials', {});
    assert.ok(credentials.credentials.every(c => !c.configured && !c.usable));
    const chat = await api('POST', '/conversations', { title: 'SYNTHETIC HTTP' }, 'synthetic-create');
    const thread = '/conversations/learning/' + chat.identity.id;
    const priorDraft = await api('GET', thread + '/draft');
    const draft = await api('PUT', thread + '/draft', { expected_revision: priorDraft.conversation_revision, text: 'Explain SYNTHETIC AKI.' });
    assert.equal(draft.revision, priorDraft.revision + 1);
    await m.push(TestLLM.tool('synthetic-retrieve', 'renulus_library_retrieve', { query: 'AKI', limit: 1 }));
    await m.push(TestLLM.tool('synthetic-citation', 'renulus_library_citation', { document_id: DOC, document_revision: REV, passage_id: PASSAGE, page: 1 }));
    await m.push(TestLLM.text(phrase, 'answer'));
    const send = { expected_revision: draft.conversation_revision, text: 'Explain SYNTHETIC AKI.', request_id: 'synthetic-http-send', teaching_style: 'guided' };
    const streamed = await api('POST', thread + '/messages', send, send.request_id);
    assert.match(streamed, /event: started/); assert.match(streamed, /event: completed/); assert.equal(await m.count(), 3);
    assert.equal((await api('GET', thread + '/messages')).items.at(-1).content, phrase);
    const runs = await api('GET', thread + '/runs'); assert.equal(runs.items[0].state, 'completed');
    const found = await api('GET', '/find?q=' + encodeURIComponent('[literal.*%_needle]')); assert.equal(found.items.length, 1);
    const before = await api('GET', thread);
    await api('POST', thread + '/archive', { expected_revision: before.revision }, 'synthetic-archive');
    assert.equal((await api('GET', '/find?q=' + encodeURIComponent(phrase))).items.length, 0);
    await facade.close(); facade = undefined;
    await open();
    assert.equal((await api('GET', thread + '/messages')).items.at(-1).content, phrase);
    assert.equal(await m.count(), 3);
    const archived = await api('GET', thread);
    await api('DELETE', thread + '?expected_revision=' + archived.revision, undefined, 'synthetic-delete');
    assert.equal((await api('GET', '/conversations?lifecycle=archived')).items.length, 0);
  } finally { await facade?.close(); if (!facade) { await connected?.close(); await storage?.close(); } await m.close(); }
});

test('actual native serializer → canonical dispatch permit → protected worker broker refuses missing account without a network probe', { timeout: 60000 }, async () => {
  const f = fixture(), storage = await openIsolatedStorage(f.writer);
  const evidence = [];
  const connected = await openConnectedTarget({ profileRoot: f.root, storage, identity: f.identity, availableModels: ['mimo-v2.6-pro'], evidence,
    resources: { python, sourceRoot: repository, broker: { profile_root: path.join(f.root, 'broker'), state_root: path.join(f.root, 'broker/state') } } });
  let facade;
  try {
    const metadata = await connected.credentials.activate();
    const credential = metadata.credentials.find(c => c.provider_id === 'opencode-go');
    assert.equal(credential.configured, false); assert.equal(credential.usable, false);
    const observation = await connected.inspect();
    const spec = defaultConfiguration({ provider: 'opencode-go', credential_reference: credential.credential_ref,
      credential_revision: credential.credential_revision, selected_model: 'mimo-v2.6-pro' }, observation.registry_hash);
    spec.capabilities = ['text', 'tools'];
    // This test owns an explicit synthetic counter. It is never installed as
    // production evidence or used to claim account/tokenizer qualification.
    const { routeFor } = await import('../src/dispatch/policy.ts');
    let counted = 0;
    evidence.push(Object.freeze({ metadata: { id: 'synthetic_noaccount', route: routeFor(spec.connection, 'mimo-v2.6-pro'),
      limits: { input_tokens: 49152, output_tokens: 4096, window_tokens: 57344 }, capabilities: ['text', 'tools'],
      limits_revision: 'synthetic', capabilities_revision: 'synthetic', counter_revision: 'synthetic_fixture_only' },
      count: async () => { counted++; return 64; } }));
    // Evidence is immutable at composition creation, so use a fresh target with
    // this explicit test evidence after the account-free metadata handoff.
    await connected.close();
    const actual = await openConnectedTarget({ profileRoot: f.root, storage, identity: f.identity, availableModels: ['mimo-v2.6-pro'], evidence,
      resources: { python, sourceRoot: repository, broker: { profile_root: path.join(f.root, 'broker'), state_root: path.join(f.root, 'broker/state') } } });
    await actual.credentials.activate();
    facade = await openTargetFacade({ port: 0, token: 'synthetic-noaccount', storage, learning: actual.learning, plugins: actual.plugins,
      configuration: actual.configuration, settlePlugins: actual.close });
    await actual.configuration.activate(spec);
    const chat = await storage.command({ type: 'learning.create', request: { kind: 'learning', title: 'SYNTHETIC no account', temporary: false,
      project_id: null, topic_id: null, teaching_style: 'direct', text: '', teaching_case_id: null }, idempotencyKey: 'synthetic-noaccount-create' });
    const response = await fetch(`http://127.0.0.1:${facade.port}/api/v1/conversations/learning/${chat.identity.id}/messages`, {
      method: 'POST', headers: { 'x-renulus-token': 'synthetic-noaccount', 'content-type': 'application/json', 'idempotency-key': 'synthetic-noaccount-send' },
      body: JSON.stringify({ expected_revision: chat.revision, text: 'Explain SYNTHETIC CKD.', request_id: 'synthetic-noaccount-send' }) });
    const stream = await response.text();
    assert.match(stream, /event: started/); assert.match(stream, /event: error/); assert.equal(counted, 1);
    assert.equal(actual.worker.channel.state().retained, 0);
    await facade.close(); facade = undefined;
    const db = new DatabaseSync(path.join(f.root, 'state/renulus.sqlite3'), { readOnly: true });
    try {
      const attempts = db.prepare('SELECT state FROM harness_configuration_attempts').all();
      assert.equal(attempts.length, 1); assert.equal(attempts[0].state, 'uncertain');
    } finally { db.close(); }
  } finally { if (facade) await facade.close(); else { await connected.close(); await storage.close(); } }
});
