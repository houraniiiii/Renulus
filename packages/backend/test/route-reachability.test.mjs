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
import { loadMigrationInventory, MARKER, SELECTOR } from '../src/storage/index.ts';
import { inventory } from '../src/storage/schema.ts';
import { openTargetApplication } from '../src/host/target.ts';
import { questionCommand } from '../src/http/question-commands.ts';
import { createQuestions } from '../src/plugins/questions.ts';

const repository = fileURLToPath(new URL('../../..', import.meta.url));
const python = 'C:/Renulus/dev/python/Scripts/python.exe';
const helpersRoot = 'C:/Renulus/dev/helper-assets';
const TOKEN = 'synthetic-reachability-token';

/** Python-prepared synthetic profile; the TS target must agree on its migration inventory. */
function fixture() {
  const root = mkdtempSync(path.join(tmpdir(), 'renulus-route-reachability-'));
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
  const environment = Object.fromEntries(['SystemRoot', 'WINDIR', 'TEMP', 'TMP'].filter(k => process.env[k]).map(k => [k, process.env[k]]));
  environment.PATH = path.dirname(python);
  const result = spawnSync(python, ['-I', '-X', 'utf8', '-c', script, repository, root], { env: environment, encoding: 'utf8', timeout: 60000 });
  assert.equal(result.status, 0, result.stderr || result.error?.message);
  const selection = { contract: 'renulus-storage-selector/1', isolation: 'synthetic', profileId: 'synthetic-profile', generation: 1,
    authorityEpoch: 1, writer: 'ts', state: 'active', ownerId: 'route_reachability_owner', database: 'state/renulus.sqlite3' };
  writeFileSync(path.join(root, MARKER), JSON.stringify({ contract: 'renulus-synthetic-storage/1', profileId: selection.profileId }));
  writeFileSync(path.join(root, SELECTOR), JSON.stringify(selection));
  mkdirSync(path.join(root, 'state/harness'), { recursive: true });
  const manifest = JSON.parse(readFileSync(path.join(repository, 'packages/contracts/fixtures/harness/paired-store-prepared.json'), 'utf8'));
  manifest.profile_id = selection.profileId; manifest.domain_store.store_id = 'synthetic-domain';
  manifest.domain_store.path = selection.database; manifest.runtime_store.store_id = 'synthetic-runtime'; manifest.runtime_store.path = 'state/harness/opencode.sqlite';
  writeFileSync(path.join(root, 'state/harness/manifest.json'), JSON.stringify(manifest));
  const migrations = loadMigrationInventory(repository), db = new DatabaseSync(result.stdout.trim());
  const expectedSchemaHash = inventory(db, migrations).schemaHash; db.close();
  return { root, selection, migrations, expectedSchemaHash,
    identity: { profile_id: selection.profileId, domain_store_id: 'synthetic-domain', runtime_store_id: 'synthetic-runtime', authority_epoch: 1, process_generation: 'synthetic-reachability' } };
}

test('every implemented /api/v1 route family is reachable through the connected facade and unauthenticated requests are refused', { timeout: 180000 }, async () => {
  const f = fixture(), runtime = ManagedRuntime.make(TestLLM.testLayer()), client = await runtime.runPromise(TestLLM.Test);
  const model = { providerId: 'synthetic', modelId: 'scripted', client,
    configuration: { model: 'synthetic/scripted', providers: { synthetic: { package: '@opencode/ai/providers/openai-compatible',
      settings: { baseURL: 'https://synthetic.invalid/v1' }, models: { scripted: { limit: { context: 128000, output: 4096 } } } } } } };
  const app =await openTargetApplication({ port: 0, token: TOKEN, profileRoot: f.root, selection: f.selection, migrations: f.migrations, expectedSchemaHash: f.expectedSchemaHash,
    connected: { identity: f.identity, availableModels: ['gpt-6.1-sol'], testing: { model: async () => model },
      resources: { python, sourceRoot: repository, helpers: { helpers_root: helpersRoot, source_root: repository, cache_root: path.join(f.root, 'cache') },
        derived: { root: path.join(f.root, 'derived'), namespace: 'synthetic-reachability', library_tombstones: [], memory_tombstones: [] },
        broker: { profile_root: path.join(f.root, 'broker'), state_root: path.join(f.root, 'broker/state') } } } });
  const call = (method, route, body, token = TOKEN) => fetch(`http://127.0.0.1:${app.port}/api/v1${route}`, { method,
    headers: { 'x-renulus-token': token, ...(body === undefined ? {} : { 'content-type': 'application/json' }) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
  try {
    assert.equal((await call('GET', '/conversations', undefined, 'wrong')).status, 401);
    const routes = [
      ['GET', '/runtime/configuration'], ['GET', '/runtime/registry'], ['GET', '/runtime/plugins'], ['GET', '/settings/credentials'],
      ['GET', '/mcp/connections'], ['GET', '/developer/worktree-removals'], ['POST', '/developer/leases/lease_x/renew', {}],
      ['GET', '/learning/questions'], ['POST', '/learning/questions/question_x/answer', { grant_epoch: 1, answers: [] }],
      ['GET', '/memory/status'], ['GET', '/study/projects'], ['GET', '/assessment/policy'], ['GET', '/content/manifest'],
      ['GET', '/study/home'], ['GET', '/updates/sources'], ['GET', '/find?q=kidney'], ['GET', '/library/documents'],
      ['GET', '/conversations'], ['POST', '/conversations', { temporary: true, kind: 'invalid' }], ['GET', '/conversations/learning/missing_thread'],
    ];
    for (const [method, route, body] of routes) {
      const response = await call(method, route, body), text = await response.text(), code = (() => { try { return JSON.parse(text).error?.code; } catch { return undefined; } })();
      assert.ok(!(response.status === 404 && code === 'not_found'), `${method} ${route} is not wired: ${text}`);
      // MCP is opt-in (it needs the patched owned native build), so only its own "not configured" refusal is expected.
      if (!route.startsWith('/mcp/')) assert.ok(!/_host_unavailable$/.test(code ?? ''), `${method} ${route} has no host: ${text}`);
    }
  } finally { await app.close(); await runtime.dispose(); }
});

test('a pending question is answered only for its own call and current grant epoch', async () => {
  const questions = createQuestions();
  let current = 3;
  const commands = { list: questions.list, reject: questions.reject, answer: async (id, epoch, answers) => questions.answer(id, epoch, answers, current) };
  const post = (id, body) => questionCommand(Object.assign((async function* () { yield Buffer.from(JSON.stringify(body)); })(), { method: 'POST', headers: {} }),
    new URL(`http://127.0.0.1/api/v1/learning/questions/${id}/answer`), commands);
  const ask = id => questions.ask({ questions: [] }, { call_id: id, session_id: 's', grant_epoch: 3 }, new AbortController().signal);
  const pending = ask('call_1');
  await assert.rejects(post('call_1', { grant_epoch: 2, answers: ['a'] }), /question_stale/);
  await assert.rejects(post('other_call', { grant_epoch: 3, answers: ['a'] }), /question_stale/);
  current = 4;
  await assert.rejects(post('call_1', { grant_epoch: 3, answers: ['a'] }), /question_stale/);
  current = 3;
  assert.deepEqual((await post('call_1', { grant_epoch: 3, answers: ['a'] })).value, { answered: 'call_1' });
  assert.deepEqual(JSON.parse((await pending).content), { answers: ['a'] });
});
