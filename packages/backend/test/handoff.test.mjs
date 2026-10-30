// SPDX-License-Identifier: MIT
// BF08: profile-wide Python -> TS authority handoff on populated SYNTHETIC schema-2 Python-owned profiles
// (built by the real Python app code), through the REAL native supervisor (python renulus.workers.profile_owner -> node
// main.mjs staged in a synthetic bundle), with rollback, crash boundaries and both-writer exclusion. No provider/network.
await import('../../harness/test/owned-environment.mjs');
import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import { spawn, spawnSync } from 'node:child_process';
import { once } from 'node:events';
import { createHash, randomUUID } from 'node:crypto';
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, realpathSync, statSync, symlinkSync, writeFileSync } from 'node:fs';
import { DatabaseSync } from 'node:sqlite';
import { tmpdir } from 'node:os';
import path, { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { Effect, Layer, Logger, ManagedRuntime, Schema, Stream } from 'effect';
import { AIError, InvalidRequestError, LLMClient } from '@opencode/ai';
import { OpenCode, AbsolutePath } from '@opencode/sdk/effect';
import { Session } from '@opencode/schema/session';
import { SessionMessage } from '@opencode/schema/session-message';
import { Config } from '@opencode/core/config';
import { InstructionDiscovery } from '@opencode/core/instruction-discovery';
import { llmClient } from '@opencode/core/effect/app-node-platform';
import { Global } from '@opencode/util/global';
import { activateStores } from '../../harness/src/stores.ts';
import { BACKEND_SELECTOR, GENERATION_MANIFEST, RETIRED_SELECTOR, resolveBackendSelection } from '../src/host/handoff.ts';
import { NODE_SHA256 } from '../src/host/bundle-verify.ts';
import { canonical } from '../src/storage/schema.ts';

const repository = fileURLToPath(new URL('../../..', import.meta.url)).replace(/[\\/]$/, '');
const python = process.env.RENULUS_BACKEND_TEST_PYTHON;
const skip = !python || process.versions.node !== '26.4.0';
const root = realpathSync(mkdtempSync(join(tmpdir(), 'renulus-bf08-handoff-')));
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const hex = char => char.repeat(64);
const DEVELOPER_PATH = join(root, 'developer-tools');   // a sentinel developer PATH entry that must never reach Node
let bundle;

// ---------------------------------------------------------------- synthetic Python-owned profiles
const NETWORK_GUARD = `
import socket
def local_only(original):
    def guarded(instance, address):
        if isinstance(address, tuple) and address[0] in ('127.0.0.1', '::1'):
            return original(instance, address)  # asyncio's Windows self-pipe only
        raise AssertionError('synthetic fixture forbids network')
    return guarded
socket.socket.connect, socket.socket.connect_ex = local_only(socket.socket.connect), local_only(socket.socket.connect_ex)
`;
/** Current code, schema 2: records across learn/knowledge/assessment/memory/study, a deleted chat (deletion frontier),
 * a revoked grant, Library originals, the desktop owner receipt and the paired harness selection. */
const SCHEMA2 = `
import asyncio, hashlib, json, sys
from pathlib import Path
repo, profile, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
sys.path.insert(0, str(repo / 'runtime'))
${NETWORK_GUARD}
from renulus.runtime.harness_profile_owner import ProfileOwnerScope, acquire_profile_owner
from renulus.server import create_app
from renulus.storage.backup import export_records
from renulus.learn.conversation_models import NewConversation, Mutation
from renulus.study.project_models import NewProject, GoalInput
from renulus.knowledge.models import SourceMetadata, own_text_rights
from renulus.knowledge.note_models import CreateNote
from renulus.memory.models import ManualFact
from renulus.contracts import ContextScope, Scope
from renulus.assessment.import_models import CreateImportRequest, ResolveImportCandidateRequest, ImportRevisionCommand
from renulus.assessment.attempt_models import StartAttempt, SubmitAttempt, DraftState
from renulus.runtime.harness_configuration import ConfigurationAuthority
from renulus.runtime.harness_profile import prepare_harness_profile
from renulus.harness_contracts import OPENCODE_SOURCE
profile.mkdir()
root = profile.resolve()
pid = 'desktop-' + hashlib.sha256(str(root).casefold().encode()).hexdigest()[:32]
# The desktop entry binds the profile issuer before any app write (desktop_harness.create_desktop_app).
acquire_profile_owner(ProfileOwnerScope(root, pid, pid + '-domain', pid + '-runtime'), initialize_new=True)
s = create_app(root).state.services
chats = s.get('conversations')
chat = chats.create(NewConversation(kind='learning', title='SYNTHETIC AKI saved chat'), 'bf08-chat')
gone = chats.create(NewConversation(kind='learning', title='SYNTHETIC deleted chat'), 'bf08-gone')
asyncio.run(chats.delete('learning', gone['identity']['id'], Mutation(expected_revision=gone['revision']), 'bf08-gone-delete'))
project = s.get('projects').create(NewProject(title='SYNTHETIC CKD project'), 'bf08-project')
project = s.get('projects').get(project['id'])
s.get('projects').goal(project['id'], GoalInput(expected_revision=project['revision'], title='SYNTHETIC dialysis goal', topic_id='T01'), 'create-goal', key='bf08-goal')
source = out / 'synthetic-library-original.txt'
source.write_text('SYNTHETIC glomerular Library original.\\n', encoding='utf-8')
document = s.get('knowledge').import_file(source, rights=own_text_rights(), metadata=SourceMetadata(), process=False)
note = s.get('notes').save(CreateNote(title='SYNTHETIC transplant note', text='SYNTHETIC note text.\\n', idempotency_key='bf08-note', project_id=None))
fact = s.get('memory').add(ManualFact(text='SYNTHETIC remembered electrolyte point', scope=ContextScope(kind=Scope.STUDY), idempotency_key='bf08-fact'))
PASTED = ('1. Which SYNTHETIC CKD choice is supplied?\\nA. First interpretation\\nB. Second interpretation\\nAnswer: A\\n\\n'
          '2. Which SYNTHETIC dialysis choice is supplied?\\nA. First dialysis option\\nB. Second dialysis option\\nAnswer: A\\n')
imports = s.get('saved_imports')
imported = imports.create(CreateImportRequest(idempotency_key='bf08-import', title='SYNTHETIC imported set',
    original={'kind': 'paste', 'text': PASTED, 'terms': 'Synthetic personal original', 'permission_confirmed': True}))
for index, candidate in enumerate(imported['candidates']):
    imported = imports.mutate_candidate(imported['id'], candidate['id'], 'resolve', ResolveImportCandidateRequest(
        idempotency_key='bf08-resolve-%d' % index, expected_revision=imported['revision'], correct_option_ids=('a',), review_confirmed=True))
imported = imports.save(imported['id'], ImportRevisionCommand(idempotency_key='bf08-import-save', expected_revision=imported['revision']))
with s.db.transaction() as conn:
    version = s.get('saved_tests').pinned_version(conn, imported['result']['version_id'])
attempt = s.get('whole_attempts').start(StartAttempt(version={'type': 'saved_test_version', 'id': version.id}, mode='test'), 'bf08-attempt')
answers = [{'item_id': item.item_id, 'option_ids': list(item.correct_option_ids)} for item in version.items]
attempt = s.get('whole_attempts').submit(attempt['id'], SubmitAttempt(expected_draft_revision=attempt['draft_revision'],
    latest_draft=DraftState(position=0, answers=answers)), 'bf08-submit')
revoked_epoch = ConfigurationAuthority(s.db).revoke('renulus.memory.recall')
session = 'ses_' + hashlib.sha256(b'bf08-session').hexdigest()
prepare_harness_profile(root, profile_id=pid, domain_store_id=pid + '-domain', runtime_store_id=pid + '-runtime', domain_path='state/renulus.sqlite3')
with s.db.transaction() as conn:
    conn.execute('INSERT INTO harness_store_identity VALUES(1,?,?,1,?)', (pid, pid + '-domain', OPENCODE_SOURCE))
    conn.execute('INSERT INTO learn_harness_mappings VALUES(?,?,?,?,?,?,?)', (chat['identity']['id'], pid, pid + '-runtime', session,
        json.dumps({'session_id': session, 'store_id': pid + '-runtime'}, sort_keys=True, separators=(',', ':')), 'bf08-mapping', 'synthetic-python-owner'))
s.get('knowledge').index.close()
(out / 'source-export.json').write_text(json.dumps(export_records(s)), encoding='utf-8')
print(json.dumps({'identity': {'profile_id': pid, 'domain_store_id': pid + '-domain', 'runtime_store_id': pid + '-runtime'},
    'chat': chat['identity']['id'], 'deleted_chat': gone['identity']['id'], 'project': project['id'], 'documents': [document['revision_id'], note['revision_id']],
    'fact': fact['id'], 'attempt': attempt['id'], 'revoked_epoch': revoked_epoch, 'session': session}))
`;

function pythonEnvironment(extra = {}) {
  const environment = Object.fromEntries(['SystemRoot', 'WINDIR', 'TEMP', 'TMP'].filter(key => process.env[key]).map(key => [key, process.env[key]]));
  return { ...environment, PATH: dirname(python), PYTHONDONTWRITEBYTECODE: '1', HF_HUB_OFFLINE: '1', TRANSFORMERS_OFFLINE: '1', ...extra };
}
function runPython(script, ...args) {
  const result = spawnSync(python, ['-I', '-X', 'utf8', '-c', script, ...args], { encoding: 'utf8', env: pythonEnvironment(), windowsHide: true,
    timeout: 300_000, maxBuffer: 64 * 1024 * 1024 });
  assert.equal(result.status, 0, result.stderr || result.error?.message);
  return result.stdout.trim() ? JSON.parse(result.stdout.trim().split('\n').at(-1)) : null;
}
/** The real native owner of a Python-owned profile opens/creates its OpenCode store; we seed one synthetic session. */
async function seedNative(profile, identity, sessionId) {
  const database = join(profile, 'state/harness/opencode.sqlite'), scratch = join(root, 'native-scratch', randomUUID());
  const workspace = join(scratch, 'workspace');
  mkdirSync(workspace, { recursive: true });
  const denied = () => new AIError({ reason: new InvalidRequestError({ message: 'Synthetic BF08 fixture forbids inference.' }) });
  const client = { stream: () => Stream.fail(denied()), generate: () => Effect.fail(denied()), compact: () => Effect.fail(denied()) };
  const content = JSON.stringify({ compaction: { auto: false }, agents: { title: { disabled: true } } });
  const runtime = ManagedRuntime.make(Layer.effect(OpenCode.Service, OpenCode.create({
    app: { name: 'renulus-bf08-fixture', version: '1' }, database: { path: database },
    config: { directory: join(scratch, 'config'), project: false, content },
    models: { fetch: false, snapshot: false }, fs: { filewatcher: false, fff: false }, events: { persist: false },
  }, { overrides: [
    Global.node.replace(Global.layerWith(Object.fromEntries(['home', 'data', 'cache', 'config', 'state', 'tmp', 'bin', 'log', 'repos'].map(key => [key, join(scratch, key)])))),
    Config.node.replace(Config.configured({ project: false, global: false, content })),
    InstructionDiscovery.node.replace(InstructionDiscovery.configured({ project: false, global: false })),
    llmClient.replace(Layer.succeed(LLMClient.Service, client)),
  ] })).pipe(Layer.provideMerge(Logger.layer([], { mergeWithExisting: false }))));
  try {
    const sdk = await runtime.runPromise(OpenCode.Service), location = { directory: AbsolutePath.make(workspace) };
    const template = await runtime.runPromise(sdk.sessions.create({ id: Session.ID.make('ses_' + sha('template' + randomUUID())), location,
      metadata: { synthetic: true }, permissions: [{ action: 'read', resource: '*', effect: 'allow' }] }));
    const T0 = Date.parse('2026-10-20T10:00:00Z');
    await runtime.runPromise(sdk.sessions.import({ location, info: { ...template, id: Session.ID.make(sessionId), title: 'SYNTHETIC AKI',
      metadata: { renulusStore: identity.runtime_store_id, synthetic: true } }, messages: [
      { id: 'msg_' + sha('u1'), type: 'user', time: { created: T0 }, text: 'Synthetic: potassium 5.2 mmol/L' },
      { id: 'msg_' + sha('a1'), type: 'assistant', agent: 'synthetic', model: { providerID: 'synthetic', id: 'fixture' },
        time: { created: T0 + 1000, completed: T0 + 1001 }, content: [{ type: 'text', text: 'Synthetic retained answer' }] },
    ].map(m => Schema.decodeUnknownSync(SessionMessage.Info)(m)) }));
    await runtime.runPromise(sdk.sessions.remove({ sessionID: template.id }));
  } finally { await runtime.dispose(); }
  const db = new DatabaseSync(database);
  try { db.exec('PRAGMA wal_checkpoint(TRUNCATE)'); } finally { db.close(); }
  // The native owner's activation binds the runtime identity and flips the paired selection to active.
  await activateStores({ root: profile, profileId: identity.profile_id, storeId: identity.runtime_store_id,
    domainStoreId: identity.domain_store_id, domainPath: 'state/renulus.sqlite3' });
}
async function schema2Profile(name) {
  const out = join(root, name + '-fixture'); mkdirSync(out);
  const profile = join(root, name);
  const fixture = runPython(SCHEMA2, repository, profile, out);
  await seedNative(profile, fixture.identity, fixture.session);
  return { ...fixture, profile, out, source: JSON.parse(readFileSync(join(out, 'source-export.json'), 'utf8')) };
}

// ---------------------------------------------------------------- synthetic staged bundle and the real supervisor
/** Same layout/manifest contract as packaging/backend_bundle.py: pinned Node, the compiled entry, a cohort inventory.
 * RENULUS_BF08_BUNDLE names a REAL bundle staged by packaging/backend_bundle.py instead: its bundled Python runs the
 * supervisor, migration tool and workers, and its Node runs launch.mjs under the closed package graph. */
function stageBundle() {
  const real = process.env.RENULUS_BF08_BUNDLE;
  if (real) {
    const target = realpathSync(real);
    return { root: target, node: join(target, 'node/node.exe'), entry: join(target, 'launch.mjs'), python: join(target, 'python/python.exe'),
      source: target, cohortHash: JSON.parse(readFileSync(join(target, 'backend-bundle.json'), 'utf8')).cohortHash };
  }
  const target = join(root, 'bundle');
  const files = { 'node/node.exe': process.execPath, 'packages/backend/dist/main.mjs': join(repository, 'packages/backend/dist/main.mjs'),
    'packages/backend/dist/storage-worker.mjs': join(repository, 'packages/backend/dist/storage-worker.mjs') };
  for (const [name, source] of Object.entries(files)) { mkdirSync(dirname(join(target, name)), { recursive: true }); copyFileSync(source, join(target, name)); }
  mkdirSync(join(target, 'cohort'), { recursive: true }); mkdirSync(join(target, 'python'), { recursive: true });
  writeFileSync(join(target, 'cohort/source-inventory.json'), JSON.stringify({ source_commit: '4b6fea2875e4f2e3e8a8fee181803e54f7056845', files: [] }));
  writeFileSync(join(target, 'python/python.exe'), 'synthetic bundled python placeholder');
  // The frozen external package graph resolves from the bundle's parent, outside the closed verified tree
  // (the staged bundle uses its graph loader instead).
  symlinkSync(realpathSync(join(repository, 'packages/backend/node_modules')), join(root, 'node_modules'), 'junction');
  const inventory = ['node/node.exe', 'packages/backend/dist/main.mjs', 'packages/backend/dist/storage-worker.mjs', 'cohort/source-inventory.json', 'python/python.exe']
    .map(name => ({ path: name, sha256: sha(readFileSync(join(target, name))), bytes: statSync(join(target, name)).size }));
  writeFileSync(join(target, 'backend-inventory.json'), JSON.stringify(inventory));
  writeFileSync(join(target, 'backend-bundle.json'), JSON.stringify({ contract: 'renulus-backend-bundle/1', node: 'node/node.exe', nodeSha256: NODE_SHA256,
    python: 'python/python.exe', entrypoint: 'packages/backend/dist/main.mjs', cohortHash: sha(readFileSync(join(target, 'cohort/source-inventory.json'))),
    inventorySha256: sha(readFileSync(join(target, 'backend-inventory.json'))) }, null, 2));
  return { root: target, node: join(target, 'node/node.exe'), entry: join(target, 'packages/backend/dist/main.mjs'), python, source: repository,
    cohortHash: sha(readFileSync(join(target, 'cohort/source-inventory.json'))) };
}
/** python -m renulus.workers.profile_owner, given a deliberately polluted developer environment. */
function supervise(profile, identity, childArgs, { maintenance = false, adoptLegacy = false, token, entry = bundle.entry } = {}) {
  const env = pythonEnvironment({ PATH: dirname(python) + ';' + DEVELOPER_PATH, PYTHONPATH: join(repository, 'runtime'),
    NODE_OPTIONS: '--renulus-leaked-developer-option', RENULUS_DEVELOPER_SENTINEL: 'leaked', ...(token ? { RENULUS_SESSION_TOKEN: token } : {}) });
  // A real bundle's embedded Python runs isolated (-I) from its own tree, exactly as Electron launches it.
  return spawn(bundle.python, [...(bundle.python === python ? [] : ['-I', '-B']), '-X', 'utf8', '-m', 'renulus.workers.profile_owner', '--profile', profile, '--node', bundle.node, '--entrypoint', entry,
    '--profile-id', identity.profile_id, '--domain-store-id', identity.domain_store_id, '--runtime-store-id', identity.runtime_store_id,
    ...(maintenance ? ['--maintenance'] : []), ...(adoptLegacy ? ['--adopt-legacy'] : []), '--', ...childArgs],
  { cwd: bundle.source, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
}
async function finished(child) {
  let stdout = '', stderr = '';
  child.stdout.on('data', chunk => { stdout += chunk; }); child.stderr.on('data', chunk => { stderr += chunk; });
  const [code] = await once(child, 'exit');
  return { code, stdout, stderr };
}
async function handoff(fixture, action, { expected, adoptLegacy } = {}) {
  const result = await finished(supervise(fixture.profile, fixture.identity, ['--handoff', action, '--selected-owner', '--profile', fixture.profile,
    '--python', bundle.python, '--source-root', bundle.source, ...(expected ? ['--expected-source-sha256', expected] : [])], { maintenance: true, adoptLegacy }));
  const line = result.stdout.split('\n').find(text => text.startsWith('{"event":"handoff"'));
  assert.ok(line, `no handoff result (exit ${result.code}): ${result.stderr.slice(-4000)}`);
  return { ...JSON.parse(line), code: result.code };
}
/** Normal (non-maintenance) launch of the selected TS owner through the supervisor. */
async function launchTarget(fixture) {
  const selected = resolveBackendSelection(fixture.profile), generation = selected.profileRoot;
  for (const directory of ['native-grants', 'broker/state']) mkdirSync(join(generation, directory), { recursive: true });
  const resources = join(generation, 'target-resources.json'), token = 'synthetic-bf08-' + randomUUID();
  writeFileSync(resources, JSON.stringify({ identity: { ...fixture.identity, authority_epoch: selected.authorityEpoch, process_generation: 'bf08-' + randomUUID() },
    available_models: ['gpt-6.1-sol'], broker: { profile_root: join(generation, 'broker'), state_root: join(generation, 'broker/state') },
    native: { originals_root: join(generation, 'originals'), budget_root: generation, grants_root: join(generation, 'native-grants'), grant_token_sha256: hex('a') } }));
  const child = supervise(fixture.profile, fixture.identity, ['--target', '--selected-owner', '--profile', generation, '--python', bundle.python,
    '--source-root', bundle.source, '--port', '0', '--target-resources', resources], { token });
  let stdout = '', stderr = '';
  child.stderr.on('data', chunk => { stderr += chunk; });
  const exited = once(child, 'exit');
  const ready = await new Promise(resolve => {
    child.stdout.on('data', chunk => { stdout += chunk; const line = stdout.split('\n').find(text => text.startsWith('{"event":"ready"')); if (line) resolve(JSON.parse(line)); });
    void exited.then(([code]) => resolve({ exited: code }));
  });
  if (ready.exited !== undefined) return { refused: true, code: ready.exited, stdout, stderr };
  const origin = `http://127.0.0.1:${ready.port}`, headers = { 'x-renulus-token': token };
  const call = async (pathname, init = {}) => {
    const response = await fetch(origin + pathname, { ...init, headers: { ...headers, ...(init.body ? { 'content-type': 'application/json' } : {}), ...init.headers } });
    const type = response.headers.get('content-type') ?? '';
    return { status: response.status, body: type.includes('json') ? await response.json() : Buffer.from(await response.arrayBuffer()) };
  };
  return { ready, call, generation, logs: () => stderr, stop: async () => {
    assert.deepEqual((await call('/api/v1/runtime/shutdown', { method: 'POST' })).body, { state: 'settled', api_version: 1 });
    const [code] = await exited; assert.equal(code, 0, stderr.slice(-4000));
  } };
}
const pythonRefusal = (profile) => runPython(`
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'runtime'))
from renulus.storage.database import Database
try:
    Database(Path(sys.argv[2])); print(json.dumps({'opened': True}))
except RuntimeError as error: print(json.dumps({'refused': str(error)}))
`, repository, profile);
const selectorOf = profile => existsSync(join(profile, BACKEND_SELECTOR)) ? readFileSync(join(profile, BACKEND_SELECTOR), 'utf8') : null;
const sorted = rows => [...rows].map(row => canonical(row)).sort();
/** Python source export vs TS export: same tables, IDs, counts and row values (TS export nulls *_path like Python's). */
function assertSameRecords(source, exported, { sourceColumnsOnly = false } = {}) {
  for (const [table, rows] of Object.entries(source.records)) {
    const actual = exported.records[table] ?? [];
    const project = row => sourceColumnsOnly && rows[0] ? Object.fromEntries(Object.keys(rows[0]).map(key => [key, row[key]])) : row;
    assert.equal(actual.length, rows.length, table);
    assert.deepEqual(sorted(actual.map(project)), sorted(rows), table);
  }
}

before(() => {
  if (skip) return;
  mkdirSync(DEVELOPER_PATH);
  bundle = stageBundle();
});
after(() => { /* Retained under the test temp root for diagnostics; every byte is synthetic. */ });

test('schema-2 Python profile: preview, apply, activate and open the TS owner through the real supervisor', { skip, timeout: 600_000 }, async () => {
  const fixture = await schema2Profile('schema2');
  const before = { selector: selectorOf(fixture.profile), canonical: sha(readFileSync(join(fixture.profile, 'state/renulus.sqlite3'))),
    native: sha(readFileSync(join(fixture.profile, 'state/harness/opencode.sqlite'))) };
  assert.equal(before.selector, null);
  const preview = await handoff(fixture, 'preview');
  assert.equal(preview.ok, true, JSON.stringify(preview.error));
  assert.equal(preview.result.schemaVersion, 2); assert.equal(preview.result.sourceSha256, before.canonical);
  assert.equal(preview.result.nativeStore, true); assert.equal(preview.result.originals, 2);
  assert.match(preview.result.contracts.migrationToolSha256, /^[a-f0-9]{64}$/);
  assert.equal(selectorOf(fixture.profile), null);   // read-only
  const applied = await handoff(fixture, 'apply', { expected: preview.result.sourceSha256 });
  assert.equal(applied.ok, true, JSON.stringify(applied.error));
  assert.deepEqual([applied.result.selector.writer, applied.result.selector.state, applied.result.selector.authorityEpoch, applied.result.generationPath],
    ['ts', 'held', 1, 'generations/g1']);
  // The original Python profile is never upgraded in place.
  assert.equal(sha(readFileSync(join(fixture.profile, 'state/renulus.sqlite3'))), before.canonical);
  assert.equal(sha(readFileSync(join(fixture.profile, 'state/harness/opencode.sqlite'))), before.native);
  // Held: no normal launch, no TS writer and no Python canonical writer.
  const held = await launchTarget(fixture);
  assert.equal(held.refused, true); assert.match(held.stderr, /backend_selected_admission_held/);
  assert.deepEqual(pythonRefusal(join(fixture.profile, 'state/renulus.sqlite3')), { refused: 'backend_canonical_authority_ts' });
  const activated = await handoff(fixture, 'activate');
  assert.equal(activated.ok, true, JSON.stringify(activated.error));
  assert.equal(resolveBackendSelection(fixture.profile).admission, 'active');
  fixture.generation = join(fixture.profile, 'generations', 'g1');
  assert.deepEqual(pythonRefusal(join(fixture.generation, 'state/renulus.sqlite3')), { refused: 'backend_canonical_authority_ts' });
  const target = await launchTarget(fixture);
  assert.equal(target.refused, undefined, target.stderr?.slice(-4000));
  try {
    const exported = await target.call('/api/v1/data/export');
    assert.equal(exported.status, 200);
    assertSameRecords(fixture.source, exported.body);
    const status = await target.call('/api/v1/runtime/status');
    // The development cohort is not the patched native build: MCP is reported disabled, not crashed; developer Off.
    assert.deepEqual(status.body.capabilities, { mcp: { state: 'disabled', code: 'native_capability_patch_required' }, developer: { state: 'off' } });
    const mcp = await target.call('/api/v1/mcp/connections');
    assert.equal(mcp.status, 409); assert.equal(mcp.body.error.code, 'native_capability_patch_required');
    const configuration = await target.call('/api/v1/runtime/configuration');
    assert.ok(configuration.body.revoked.includes('renulus.memory.recall'), JSON.stringify(configuration.body));
    assert.equal(configuration.body.grant_epoch, fixture.revoked_epoch);
    const deleted = await target.call('/api/v1/conversations/learning/' + fixture.deleted_chat);
    assert.notEqual(deleted.status, 200);
    for (const revision of fixture.documents) {
      const original = await target.call(`/api/v1/library/revisions/${revision}/original`);
      assert.equal(original.status, 200, JSON.stringify(original.body) + target.logs().slice(-6000));
      const row = fixture.source.records.knowledge_revisions.find(r => r.id === revision);
      assert.equal(sha(original.body), row.sha256);
    }
    const write = await target.call('/api/v1/study/projects', { method: 'POST', headers: { 'idempotency-key': 'bf08-ts-write' },
      body: JSON.stringify({ title: 'SYNTHETIC TS-owned project' }) });
    assert.ok([200, 201].includes(write.status), JSON.stringify(write.body));
    fixture.newProject = write.body;
  } finally { await target.stop(); }
  // Python is engine/broker only: it never opened either canonical store.
  assert.equal(sha(readFileSync(join(fixture.profile, 'state/renulus.sqlite3'))), before.canonical);
  const refused = await handoff(fixture, 'rollback');
  assert.equal(refused.ok, false); assert.equal(refused.error.code, 'backend_rollback_newer_work');
  assert.equal(resolveBackendSelection(fixture.profile).admission, 'active');
});

test('crash leftovers and failed apply keep Python; rollback returns authority and a later handoff continues the epoch', { skip, timeout: 600_000 }, async () => {
  const fixture = await schema2Profile('rollback');
  const canonicalFile = join(fixture.profile, 'state/renulus.sqlite3');
  // A crash after the candidate directory but before the selector: no selector, Python stays the owner.
  mkdirSync(join(fixture.profile, 'generations/g1/state'), { recursive: true });
  writeFileSync(join(fixture.profile, 'generations/g1/state/renulus.sqlite3'), 'partial crashed candidate');
  const preview = await handoff(fixture, 'preview');
  assert.equal(preview.ok, true, JSON.stringify(preview.error));
  // A stale expectation refuses before any candidate or selector exists.
  const stale = await handoff(fixture, 'apply', { expected: hex('0') });
  assert.equal(stale.ok, false); assert.equal(stale.error.code, 'handoff_source_changed');
  assert.equal(selectorOf(fixture.profile), null);
  assert.deepEqual(readdirSync(join(fixture.profile, 'generations')), ['g1']);
  const applied = await handoff(fixture, 'apply', { expected: preview.result.sourceSha256 });
  assert.equal(applied.ok, true, JSON.stringify(applied.error));
  assert.equal(applied.result.generationPath, 'generations/g2');   // the crashed candidate is never reused
  assert.equal((await handoff(fixture, 'activate')).ok, true);
  const target = await launchTarget(fixture);
  try { assert.equal((await target.call('/api/v1/data/export')).status, 200); } finally { await target.stop(); }
  // An original edited in place (Reader > Open in its associated app) is newer work: rollback refuses.
  const originalsDir = join(fixture.profile, 'generations/g2/originals'), [first] = readdirSync(originalsDir);
  const originalBytes = readFileSync(join(originalsDir, first));
  writeFileSync(join(originalsDir, first), Buffer.concat([originalBytes, Buffer.from('edited')]));
  const edited = await handoff(fixture, 'rollback');
  assert.equal(edited.ok, false); assert.equal(edited.error.code, 'backend_rollback_newer_work');
  writeFileSync(join(originalsDir, first), originalBytes);
  // A read-only TS session holds no newer work: rollback retires the selector in one rename.
  const rollback = await handoff(fixture, 'rollback');
  assert.equal(rollback.ok, true, JSON.stringify(rollback.error));
  assert.deepEqual(rollback.result, { writer: 'python', retiredEpoch: 1, generationPath: 'generations/g2' });
  assert.equal(selectorOf(fixture.profile), null);
  assert.ok(existsSync(join(fixture.profile, RETIRED_SELECTOR)));
  assert.equal(sha(readFileSync(canonicalFile)), preview.result.sourceSha256);   // untouched Python profile
  assert.deepEqual(pythonRefusal(canonicalFile), { opened: true });
  // Nothing about the retired TS selection is resurrected: the profile resolves to the Python writer.
  assert.deepEqual(resolveBackendSelection(fixture.profile), { writer: 'python', profileRoot: fixture.profile, admission: 'active' });
  // A later handoff starts from the (re-opened) Python profile and continues the authority epoch.
  const again = await handoff(fixture, 'preview');
  assert.equal(again.ok, true, JSON.stringify(again.error));
  const second = await handoff(fixture, 'apply', { expected: again.result.sourceSha256 });
  assert.equal(second.ok, true, JSON.stringify(second.error));
  assert.deepEqual([second.result.selector.authorityEpoch, second.result.generationPath, second.result.selector.state], [2, 'generations/g3', 'held']);
  assert.equal((await handoff(fixture, 'activate')).ok, true);
  const reopened = await launchTarget(fixture);
  try {
    const exported = await reopened.call('/api/v1/data/export');
    assert.equal(exported.status, 200);
    assertSameRecords(fixture.source, exported.body, { sourceColumnsOnly: true });
  } finally { await reopened.stop(); }
});
