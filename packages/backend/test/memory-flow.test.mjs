// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { openIsolatedStorage, previewStorage, loadMigrationInventory, MARKER, SELECTOR } from '../src/storage/index.ts';
import { createMemoryHost, createWorkerMemory } from '../src/host/memory.ts';
import { openEngineWorker } from '../src/workers/process.ts';
import { memoryCommand } from '../src/http/memory-commands.ts';

const repository = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const python = process.env.RENULUS_BACKEND_TEST_PYTHON;
const helpers = process.env.RENULUS_WORKER_TEST_HELPERS;
function deferred() { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; }

test('actual one-writer Memory + Mem0/Qdrant captures, cancels, corrects, revokes support, deletes and reopens', {
  skip: !python || !helpers, timeout: 240_000,
}, async () => {
  assert.equal(process.versions.node, '26.4.0');
  const root = mkdtempSync(join(tmpdir(), 'renulus-memory-flow-')), profile = join(root, 'profile');
  const script = String.raw`
import sys,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'runtime'))
from renulus.server import create_app
from renulus.design_c_contracts import canonical_digest
s=create_app(Path(sys.argv[2])).state.services
stamp='2026-10-27T00:00:00.000Z'
with s.db.transaction() as c:
    c.execute("INSERT INTO memory_facts VALUES('memory_synthetic_root','Synthetic AKI root',?,'learning-point','aki','study',1,'manual',NULL,?,?)",(canonical_digest('synthetic aki root'),stamp,stamp))
    c.execute("INSERT INTO memory_history VALUES('memory_synthetic_root',1,'Synthetic AKI root','added',?)",(stamp,))
    c.execute("INSERT INTO memory_sources VALUES('manual:synthetic-root','memory_synthetic_root')")
    c.execute("INSERT INTO memory_support_groups VALUES('support:synthetic-root','memory_synthetic_root','manual:synthetic-root','manual','active',NULL)")
    for name,body in [('echo','Synthetic AKI support echo'),('independent','Synthetic CKD educational learning'),('cancel','Synthetic glomerular educational learning'),('echoback','Synthetic CKD answer echoed back')]:
        thread='thread_'+name;run='run_'+name;message='message_'+name;eid='learn-answer:'+run
        c.execute('INSERT INTO learn_threads VALUES(?,?,?,\'direct\',?,?)',(thread,'SYNTHETIC '+name,'aki',stamp,stamp))
        c.execute("INSERT INTO learn_runs VALUES(?,?,?,'completed',NULL,?,?)",(run,thread,'synthetic-key-'+name,stamp,stamp))
        c.execute("INSERT INTO learn_messages VALUES(?,?,?,'assistant',?,'[]',?)",(message,thread,run,body,stamp))
        ref={'version':1,'message_id':message,'run_id':run,'sha256':hashlib.sha256(body.encode()).hexdigest()}
        payload={'scope':{'kind':'study','entity_id':thread},'answer_reference':ref}
        evidence={'id':eid,'kind':'study-answer','topic_id':'aki','entity_id':thread,'payload_json':json.dumps(payload,sort_keys=True,separators=(',',':')),'created_at':stamp}
        c.execute('INSERT INTO learning_evidence VALUES(?,?,?,?,?,?)',tuple(evidence.values()))
        deps=[{'target':{'type':'memory_revision','id':'memory_synthetic_root:1'},'expected_revision':'1'}] if name=='echo' else []
        manifest={'version':1,'inputs':[],'dependencies':deps}
        publication=canonical_digest({'evidence':evidence,'manifest':manifest,'project_id':None})
        c.execute("INSERT INTO memory_answer_lineage VALUES(?,?,?,'active',NULL,?)",(eid,publication,json.dumps(manifest),stamp))
        if name=='echo':
            policy=c.execute("SELECT value FROM preferences WHERE key='design_c.assessment_policy_revision'").fetchone()
            context=c.execute("SELECT value FROM preferences WHERE key='design_c.context_epoch'").fetchone()
            fingerprint='memory-ts/1:'+canonical_digest({'publication':publication,'support':manifest,'policy':int(policy[0]) if policy else 1,'context':int(context[0]) if context else 0})
            c.execute("INSERT INTO memory_jobs VALUES('capture_synthetic_automatic',?,?,?,'queued',0,NULL,?,?)",(eid,fingerprint,json.dumps(payload['scope']),stamp,stamp))
print(json.dumps({'databasePath':str(s.paths.database)}))
`;
  const seeded = spawnSync(python, ['-I', '-X', 'utf8', '-c', script, repository, profile], { encoding: 'utf8', windowsHide: true, timeout: 60000 });
  assert.equal(seeded.status, 0, seeded.stderr);
  const databasePath = JSON.parse(seeded.stdout).databasePath, migrations = loadMigrationInventory(repository);
  const preview = await previewStorage({ databasePath, migrations });
  assert.equal(preview.compatible, true, JSON.stringify(preview.issues));
  const selection = { contract: 'renulus-storage-selector/1', isolation: 'synthetic', profileId: 'synthetic-memory', generation: 1,
    authorityEpoch: 1, writer: 'ts', state: 'active', ownerId: 'synthetic-memory-owner', database: 'state/renulus.sqlite3' };
  writeFileSync(join(profile, MARKER), JSON.stringify({ contract: 'renulus-synthetic-storage/1', profileId: selection.profileId }));
  writeFileSync(join(profile, SELECTOR), JSON.stringify(selection));
  const storageOptions = { profileRoot: profile, selection, migrations, expectedSchemaHash: preview.schemaHash };
  let storage = await openIsolatedStorage(storageOptions), host, worker;
  const started = deferred(), cancelled = deferred(), settled = deferred();
  let generationCalls = 0, failRebuild = false;
  const workerOptions = { python, sourceRoot: repository, launchRoot: join(root, 'launch'), retention: 'saved',
    identity: { profile_id: 'synthetic-memory', domain_store_id: 'synthetic-domain', runtime_store_id: 'synthetic-native', authority_epoch: 1, process_generation: 'synthetic-generation' },
    current: () => ({ configuration: 1, grant: 1, context: 1, deletion: 1, cancellation: 0 }),
    helpers: { helpers_root: helpers, cache_root: join(root, 'cache'), source_root: repository },
    derived: { root: join(root, 'derived'), namespace: 'synthetic-memory', library_tombstones: [], memory_tombstones: [] },
    generate: (request, signal) => host.generation(request, signal) };
  const createHost = () => {
    const engine = createWorkerMemory(worker.channel, worker.ready.capacity.max_chunk_bytes);
    return createMemoryHost({ storage, engine: { ...engine, async reconcile(records, signal) {
      const staged = await engine.reconcile(records, signal);
      if (failRebuild) { failRebuild = false; throw new Error('synthetic staging failure before canonical activation'); }
      return staged;
    } },
    resolveAnswer: async () => { throw new Error('legacy-fixture-resolves-locally'); },
    generate: async (request, signal) => {
      generationCalls++;
      const prompt = JSON.stringify(request.messages);
      if (prompt.includes('Synthetic glomerular')) {
        started.resolve(); signal.addEventListener('abort', () => cancelled.resolve(), { once: true });
        await settled.promise; return { status: 'cancelled', output: null };
      }
      if (prompt.includes('Synthetic CKD answer echoed back')) return { status: 'completed', output: JSON.stringify({ memory: [{ text: 'Corrected CKD learning point' }] }) };
      const memory = prompt.includes('Synthetic AKI support echo') ? 'Derived AKI learning point' : 'CKD educational learning point';
      return { status: 'completed', output: JSON.stringify({ memory: [{ text: memory }] }) };
    } });
  };
  const search = query => host.recall({ query, scope: { kind: 'study' }, limit: 10 });
  try {
    worker = await openEngineWorker(workerOptions); host = createHost();
    await host.start();
    const status = await memoryCommand({ method: 'GET' }, new URL('http://127.0.0.1/api/v1/memory/status'), storage, host);
    assert.equal(status.value.index.ready, true, 'existing Memory screen receives its nested status contract');
    assert.equal(status.value.automatic_capture, true);
    // A durably queued automatic capture runs on startup without an explicit
    // Capture request or model-write tool. Replaying the source cannot repeat it.
    const echo = { records: (await storage.command({ type: 'memory.list', offset: 0, limit: 100 })).records.filter(r => r.source_id === 'learn-answer:run_echo') };
    assert.equal(echo.records.length, 1);
    assert.equal((await host.captureEvidence('learn-answer:run_echo')).captured, false);
    assert.ok((await search('AKI')).records.some(r => r.id === echo.records[0].id));
    const rootCorrection = await host.correct('memory_synthetic_root', 'Corrected AKI root', 1);
    assert.equal(rootCorrection.revision, 2);
    await assert.rejects(storage.command({ type: 'memory.inspect', id: echo.records[0].id }), { code: 'memory_missing' });
    await assert.rejects(host.captureEvidence('learn-answer:run_echo', true), { code: 'memory_capture_suppressed' });
    assert.ok(!(await search('AKI')).records.some(r => r.id === echo.records[0].id));
    const capture = await host.captureEvidence('learn-answer:run_independent');
    assert.equal(capture.captured, true);
    const id = capture.records[0].id, before = await search('CKD'); assert.ok(before.records.some(r => r.id === id));
    const changed = await host.correct(id, 'Corrected CKD learning point', 1);
    assert.equal(changed.revision, 2); assert.deepEqual(changed.history.map(h => h.text), ['Corrected CKD learning point']);
    await assert.rejects(host.captureEvidence('learn-answer:run_independent', true), { code: 'memory_capture_suppressed' });
    assert.equal((await search('CKD')).records.find(r => r.id === id).text, 'Corrected CKD learning point');
    await storage.command({ type: 'memory.add', text: 'Transplantation study goal', kind: 'goal', topicId: 'transplant', projectId: null, idempotencyKey: 'synthetic-staged-goal' });
    failRebuild = true;
    await assert.rejects(host.rebuild(), /synthetic staging failure/);
    assert.equal((await search('CKD')).records.find(r => r.id === id).text, 'Corrected CKD learning point', 'previous accepted vectors remain usable after failed staging');
    await host.rebuild();
    // Cancellation is observed before real native-generation settlement. The
    // public cancel promise must retain the worker lease until that finalizer.
    const pending = host.captureEvidence('learn-answer:run_cancel'); void pending.catch(() => {});
    await started.promise;
    const jobs = await storage.command({ type: 'memory.jobs', recover: false });
    let cancelDone = false; const cancellation = host.cancel(jobs.find(j => j.evidence_id === 'learn-answer:run_cancel').id).then(() => { cancelDone = true; });
    await cancelled.promise; assert.equal(cancelDone, false); assert.ok(worker.channel.state().unsettled > 0);
    settled.resolve(); await cancellation; await assert.rejects(pending);
    assert.equal(generationCalls, 3);
    assert.equal((await storage.command({ type: 'memory.purge.pending' })).length, 0);
    await host.close(); await worker.close(); await storage.close();
    storage = await openIsolatedStorage(storageOptions); worker = await openEngineWorker(workerOptions); host = createHost();
    await host.start();
    assert.equal((await search('CKD')).records.find(r => r.id === id).text, 'Corrected CKD learning point');
    assert.equal((await host.delete(id, 2)).deleted, true);
    assert.ok(!(await search('CKD')).records.some(r => r.id === id));
    assert.ok(!(await storage.command({ type: 'memory.export' })).records.some(r => r.id === id));
    // A later assistant message that merely echoes the deleted fact cannot recapture it.
    const echoed = await host.captureEvidence('learn-answer:run_echoback');
    assert.deepEqual(echoed.records, []);
    assert.ok(!(await search('CKD')).records.some(r => r.text === 'Corrected CKD learning point'));
    assert.equal((await storage.command({ type: 'memory.purge.pending' })).length, 0);
    assert.equal(worker.channel.state().unsettled, 0);
    await host.close(); await worker.close();
    // Inspect only the owned synthetic derived store after native closure. This
    // distinguishes physical purge of all revisions/history from recall filters.
    const inspected = spawnSync(python, ['-I', '-X', 'utf8', '-c', String.raw`
import sys,json,sqlite3
from pathlib import Path
from qdrant_client import QdrantClient
base=Path(sys.argv[1])/'synthetic-memory'/'indexes'/'learner-memory'/'facts'
client=QdrantClient(path=str(base/'qdrant'))
rows,_=client.scroll('renulus_learner_facts',limit=1000,with_payload=True,with_vectors=False)
payloads=[row.payload for row in rows];client.close()
db=sqlite3.connect(base/'history.sqlite3')
history=db.execute('SELECT count(*) FROM history').fetchone()[0]
messages=db.execute('SELECT count(*) FROM messages').fetchone()[0];db.close()
print(json.dumps({'payloads':payloads,'history':history,'messages':messages}))
`, join(root, 'derived')], { encoding: 'utf8', windowsHide: true, timeout: 30000 });
    assert.equal(inspected.status, 0, inspected.stderr);
    const physical = JSON.parse(inspected.stdout);
    assert.equal(physical.history, 0); assert.equal(physical.messages, 0);
    assert.ok(!physical.payloads.some(p => String(p.canonical_id).startsWith(id + ':') || String(p.canonical_id).startsWith(echo.records[0].id + ':') || p.data === 'Synthetic AKI root'));
  } finally {
    settled.resolve(); await host?.close(); await worker?.close(); await storage.close();
  }
});
