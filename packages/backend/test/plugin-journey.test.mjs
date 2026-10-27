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
import { defaultConfiguration } from '../src/dispatch/policy.ts';

const repository = fileURLToPath(new URL('../../..', import.meta.url));
const python = 'C:/Renulus/dev/python/Scripts/python.exe';
const helpersRoot = 'C:/Renulus/dev/helper-assets';
const DOC = 'doc_' + '1'.repeat(32), REV = 'rev_' + '2'.repeat(32), PASSAGE = 'passage_' + '3'.repeat(32);

/** Synthetic profile with one ready Library passage (same shape as composition.test.mjs). */
function fixture() {
  const root = mkdtempSync(path.join(tmpdir(), 'renulus-plugin-journey-'));
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
    authorityEpoch: 1, writer: 'ts', state: 'active', ownerId: 'synthetic-journey-owner', database: 'state/renulus.sqlite3' };
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
    identity: { profile_id: selection.profileId, domain_store_id: 'synthetic-domain', runtime_store_id: 'synthetic-runtime', authority_epoch: 1, process_generation: 'synthetic-journey' } };
}
async function scriptedModel() {
  const runtime = ManagedRuntime.make(TestLLM.testLayer()), client = await runtime.runPromise(TestLLM.Test);
  const model = { providerId: 'synthetic', modelId: 'scripted', client,
    configuration: { model: 'synthetic/scripted', providers: { synthetic: { package: '@opencode/ai/providers/openai-compatible',
      settings: { baseURL: 'https://synthetic.invalid/v1' }, models: { scripted: { limit: { context: 128000, output: 4096 } } } } } } };
  return { model, push: (...items) => runtime.runPromise(client.push(...items)), requests: () => runtime.runPromise(client.requests()), close: () => runtime.dispose() };
}

test('registry exploration', { timeout: 180000 }, async () => {
  const f = fixture(), m = await scriptedModel();
  const storage = await openIsolatedStorage(f.writer);
  const connected = await openConnectedTarget({ profileRoot: f.root, storage, identity: f.identity, availableModels: ['gpt-6.1-sol'],
    testing: { model: async () => m.model },
    resources: { python, sourceRoot: repository, helpers: { helpers_root: helpersRoot, source_root: repository, cache_root: path.join(f.root, 'cache') },
      derived: { root: path.join(f.root, 'derived'), namespace: 'synthetic-journey', library_tombstones: [], memory_tombstones: [] },
      broker: { profile_root: path.join(f.root, 'broker'), state_root: path.join(f.root, 'broker/state') } } });
  try {
    const registry = await connected.inspect();
    writeFileSync('C:/Renulus/scratch/ocf/l1a-registry.json', JSON.stringify(registry.registry, null, 1));
  } catch (error) { console.error('EXPLORE ERROR', error); throw error; }
  finally { await connected.close(); await storage.close(); await m.close(); }
});
