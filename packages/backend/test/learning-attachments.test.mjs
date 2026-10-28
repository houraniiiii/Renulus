// SPDX-License-Identifier: MIT
import '../../harness/test/owned-environment.mjs';
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { spawnSync } from 'node:child_process';
import { DatabaseSync } from 'node:sqlite';
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, rmSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { ManagedRuntime } from 'effect';
import { TestLLM } from '@opencode/ai/testing';
import { openSavedLearningTarget } from '../src/host/learning.ts';
import { openIsolatedStorage } from '../src/storage/index.ts';
import { MARKER, SELECTOR } from '../src/storage/ownership.ts';
import { inventory, loadMigrationInventory } from '../src/storage/schema.ts';

const repository = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const python = 'C:/Renulus/dev/python/Scripts/python.exe';
test('Saved image and extracted PDF reach native model; chat deletion cleans only its owned attachments', { timeout: 120000 }, async () => {
  const root = mkdtempSync(join(tmpdir(), 'renulus-learning-attachments-')), profile = join(root, 'profile');
  let storage, target, runtime;
  try {
    const migrations = loadMigrationInventory(repository);
    const script = `
import sys,json,hashlib,io
from PIL import Image
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'runtime'))
from renulus.server import create_app
from renulus.learn.conversation_models import NewConversation
s=create_app(Path(sys.argv[2])).state.services
threads=[s.registry['conversations'].create(NewConversation(kind='learning',title='SYNTHETIC attachments '+str(i))) for i in range(2)]
buffer=io.BytesIO();Image.new('RGB',(16,16),'teal').save(buffer,format='PNG');png=buffer.getvalue()
shared=Path(sys.argv[2])/'shared-original.pdf';shared.write_bytes(b'SYNTHETIC shared PDF original')
with s.db.transaction() as c:
 c.execute("INSERT OR REPLACE INTO harness_store_identity VALUES(1,'synthetic-profile','synthetic-domain-store',1,'4b6fea2875e4f2e3e8a8fee181803e54f7056845')")
 for id,thread,media,data in [('att_image',threads[0],'image/png',png),('att_pdf',threads[0],'application/pdf',b'SYNTHETIC PDF'),('att_other',threads[1],'application/pdf',b'SYNTHETIC other PDF')]:
  folder=Path(sys.argv[2])/'library'/'attachments'/id;folder.mkdir(parents=True)
  original=folder/'original';original.write_bytes(data)
  c.execute("INSERT INTO knowledge_attachments(id,chat_kind,chat_id,title,media_type,extraction_state,created_at,updated_at) VALUES(?,'learning',?,?,?,'ready','2026-10-27','2026-10-27')",(id,thread['identity']['id'],id,media))
  c.execute("INSERT INTO knowledge_attachment_originals VALUES(?,?,'original',?,?,?,'2026-10-27')",(id+'_original',id,str(original),hashlib.sha256(data).hexdigest(),len(data)))
  c.execute("INSERT INTO knowledge_attachment_metadata(attachment_id,filename,source_id,metadata_json,rights_json,extraction_json) VALUES(?,?,?,'{}',?,?)",(id,id,'SYNTHETIC',json.dumps({'display':True,'cache':True,'model_input':True}),json.dumps({'text':'SYNTHETIC extracted glomerular PDF teaching'})))
print(json.dumps({'database':str(s.paths.database),'threads':threads,'shared':str(shared)}))
`;
    const env = Object.fromEntries(['SystemRoot', 'WINDIR', 'TEMP', 'TMP'].filter(k => process.env[k]).map(k => [k, process.env[k]])); env.PATH = dirname(python);
    const prepared = spawnSync(python, ['-I', '-X', 'utf8', '-c', script, repository, profile], { encoding: 'utf8', env, timeout: 60000 });
    assert.equal(prepared.status, 0, prepared.stderr); const fixture = JSON.parse(prepared.stdout);
    const db = new DatabaseSync(fixture.database), expectedSchemaHash = inventory(db, migrations).schemaHash; db.close();
    const selection = { contract: 'renulus-storage-selector/1', isolation: 'synthetic', profileId: 'synthetic-profile', generation: 1,
      authorityEpoch: 1, writer: 'ts', state: 'active', ownerId: 'synthetic-attachments-owner', database: 'state/renulus.sqlite3' };
    writeFileSync(join(profile, MARKER), JSON.stringify({ contract: 'renulus-synthetic-storage/1', profileId: 'synthetic-profile' }));
    writeFileSync(join(profile, SELECTOR), JSON.stringify(selection));
    const manifest = JSON.parse(readFileSync(join(repository, 'packages/contracts/fixtures/harness/paired-store-prepared.json'), 'utf8'));
    manifest.domain_store.path = 'state/renulus.sqlite3'; manifest.runtime_store.store_id = 'synthetic-store'; manifest.runtime_store.path = 'state/harness/opencode.sqlite';
    mkdirSync(join(profile, 'state/harness'), { recursive: true }); writeFileSync(join(profile, 'state/harness/manifest.json'), JSON.stringify(manifest));
    storage = await openIsolatedStorage({ profileRoot: profile, selection, migrations, expectedSchemaHash });
    runtime = ManagedRuntime.make(TestLLM.testLayer()); const client = await runtime.runPromise(TestLLM.Test);
    await runtime.runPromise(client.push(TestLLM.text('SYNTHETIC image and PDF educational answer', 'answer')));
    const model = { providerId: 'synthetic', modelId: 'attachments', client, configuration: { model: 'synthetic/attachments', providers: { synthetic: {
      package: '@opencode/ai/providers/openai-compatible', settings: { baseURL: 'https://synthetic.invalid/v1' },
      models: { attachments: { capabilities: { input: ['text', 'image'], output: ['text'] }, limit: { context: 128000, output: 4096 } } } } } } };
    target = await openSavedLearningTarget({ storage, model: async () => model, library: { query: async () => [] },
      harness: { root: profile, profileId: 'synthetic-profile', storeId: 'synthetic-store', domainStoreId: 'synthetic-domain-store',
        domainPath: 'state/renulus.sqlite3', processGeneration: 'synthetic-attachments-process' } });
    await target.native.activateStores(); await target.native.activate('synthetic-attachments');
    const threadId = fixture.threads[0].identity.id, content_refs = ['att_image', 'att_pdf'].map(id => ({ target: { type: 'attachment', id }, locator: null }));
    const text = 'Discuss SYNTHETIC educational glomerular findings', idempotencyKey = 'synthetic-attachments-send';
    const receipt = await target.send({ threadId, expectedRevision: 1, expectedDraftRevision: 0, text, idempotencyKey,
      intent: { expected_revision: 1, text, request_id: idempotencyKey, teaching_style: 'direct', topic_id: null, model: null, freshness: null, content_refs } });
    assert.equal(receipt.state, 'completed');
    const requests = await runtime.runPromise(client.requests()); assert.equal(requests.length, 1);
    const serialized = JSON.stringify(requests[0]); assert.ok(serialized.includes('SYNTHETIC extracted glomerular PDF teaching'));
    assert.ok(serialized.includes('image/png'), serialized);
    assert.ok(serialized.includes('"type":"media"'), 'image reaches the scripted model as native media, not OCR text');
    await target.delete({ type: 'learning.delete', threadId, expectedRevision: receipt.conversation.revision, idempotencyKey: 'synthetic-attachments-delete' });
    assert.equal(existsSync(join(profile, 'library/attachments/att_image')), false);
    assert.equal(existsSync(join(profile, 'library/attachments/att_pdf')), false);
    assert.equal(existsSync(join(profile, 'library/attachments/att_other/original')), true);
    assert.equal(readFileSync(fixture.shared, 'utf8'), 'SYNTHETIC shared PDF original');
    const check = new DatabaseSync(fixture.database, { readOnly: true });
    try {
      assert.equal(check.prepare("SELECT count(*) n FROM knowledge_attachments WHERE chat_id=?").get(threadId).n, 0);
      assert.equal(check.prepare("SELECT count(*) n FROM deletion_ledger WHERE entity_type='attachment'").get().n, 2);
      assert.equal(check.prepare("SELECT count(*) n FROM knowledge_attachments WHERE id='att_other'").get().n, 1);
    } finally { check.close(); }
  } finally { await target?.close(); await runtime?.dispose(); await storage?.close(); rmSync(root, { recursive: true, force: true }); }
});
