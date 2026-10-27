// SPDX-License-Identifier: MIT
// Minimum worker-backed boundary proof; does not claim native execute acceptance.
// Run with --import ../harness/test/capability-patch-loader.mjs from packages/backend.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createServer } from 'node:http';
import { DatabaseSync } from 'node:sqlite';
import { mkdtemp, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createCapabilityAuthority } from '../src/domain/capabilities/authority.ts';
import { executeCapabilityCommand, CAPABILITY_SCHEMA } from '../src/domain/capabilities/commands.ts';
import { executeDispatch } from '../src/storage/dispatch.ts';
import { defaultConfiguration, ALLOWED_MODELS } from '../src/dispatch/policy.ts';
import { digest } from '../src/storage/schema.ts';
import { openEngineWorker } from '../src/workers/process.ts';
import { createWorkerHttp } from '../src/workers/transport.ts';

test('Code Mode authority fetch uses real worker: redirect credits, response bounds, closure and forbidden headers', {
  skip: !process.env.RENULUS_BACKEND_TEST_PYTHON, timeout: 60_000,
}, async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'renulus-codemode-fetch-'));
  const repository = fileURLToPath(new URL('../../..', import.meta.url));
  const seen = [], admissions = [];
  const server = createServer((req, res) => {
    seen.push(req.url);
    if (req.url === '/redirect') { res.writeHead(302, { location: '/ok' }); res.end(); }
    else { res.writeHead(200); res.end(req.url === '/large' ? 'x'.repeat(2 * 1024 * 1024) : 'synthetic renal result'); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  const revisions = { configuration: 0, grant: 0, context: 0, deletion: 0, cancellation: 0 };
  const identity = { profile_id: 'synthetic-profile', domain_store_id: 'synthetic-domain', runtime_store_id: 'synthetic-native', authority_epoch: 1, process_generation: 'synthetic-process' };
  const worker = await openEngineWorker({ python: process.env.RENULUS_BACKEND_TEST_PYTHON, sourceRoot: repository,
    launchRoot: path.join(root, 'launch'), identity, retention: 'saved', current: () => revisions,
    broker: { profile_root: path.join(root, 'profile'), state_root: path.join(root, 'profile/state') } });
  const db = new DatabaseSync(':memory:');
  for (const name of ['002-harness-configuration.sql','004-harness-dispatch-purpose.sql','005-harness-children.sql'])
    db.exec(await readFile(path.join(repository, 'runtime/renulus/runtime/migrations', name), 'utf8'));
  db.exec('CREATE TABLE preferences(key TEXT PRIMARY KEY,value TEXT,updated_at TEXT); CREATE TABLE assessment_test_attempts(id TEXT,mode TEXT,status TEXT);');
  db.exec(CAPABILITY_SCHEMA);
  const command = c => { db.exec('BEGIN IMMEDIATE'); try {
    const result = c.type.startsWith('capability.') ? executeCapabilityCommand(db,c) : executeDispatch(db,c);
    db.exec('COMMIT'); return result;
  } catch (error) { db.exec('ROLLBACK'); throw error; } };
  const spec = defaultConfiguration({ provider: 'codex', credential_reference: 'synthetic', credential_revision: 1, selected_model: ALLOWED_MODELS.codex[0] }, digest('synthetic-registry'));
  spec.capabilities = ['text','developer.http'];
  const { version } = command({ type:'dispatch.stage',spec,expectedEffective:null,expectedRequested:null,grantEpoch:0 });
  const inspection = { configuration_version:version,grant_epoch:0,registry_hash:spec.registry_hash,loaded_inputs:[],healthy:true,
    generation_open:false,recovery_open:false,package_acquisition_open:false,mcp_startup_open:false,live_store_writer:false };
  command({type:'dispatch.inspect',inspection}); command({type:'dispatch.close',version,expectedEffective:null,grantEpoch:0});
  command({type:'dispatch.activate',version,expectedEffective:null,settlement:{configuration_version:version,grant_epoch:0,admission_closed:true,runtime_stopped:true,domain_settled:true}});
  command({type:'dispatch.open',inspection});
  const fence = {...identity,context_epoch:0,deletion_epoch:0,cancellation_epoch:0};
  command({type:'dispatch.begin',runId:'synthetic-run',purpose:'explain',expectedVersion:version,capabilities:spec.capabilities,availableModels:[...ALLOWED_MODELS.codex],operationModel:null,batchSize:null,fence});
  const envelope = {run_id:'synthetic-run',root_id:'synthetic-run',session_id:'synthetic-session',call_id:'synthetic-call',configuration:version,grant_epoch:0,fence,retention:'saved',mode:'developer',depth:0};
  const http = createWorkerHttp({channel:worker.channel,maxChunkBytes:worker.ready.capacity.max_chunk_bytes,retention:'saved'});
  const authority = createCapabilityAuthority({storage:{execute:async c=>command(c)},
    current:async()=>({actions:['developer.http'],roots:[],skills:[],endpoints:[{host:'127.0.0.1',port,private_network:true}],max_bytes:4*1024*1024,expires_at_ms:Date.now()+60_000}),
    transport:{http:async(plan,signal)=>{admissions.push(plan.url);return http(plan,signal);},
      tunnelOpen(){throw new Error('unused');},tunnelRead(){throw new Error('unused');},tunnelWrite(){throw new Error('unused');},tunnelClose(){throw new Error('unused');}}});
  const url = suffix => `http://127.0.0.1:${port}${suffix}`;
  try {
    assert.equal(await (await authority.fetch(envelope,url('/redirect'))).text(),'synthetic renal result');
    assert.deepEqual(admissions,[url('/redirect'),url('/ok')]);
    await assert.rejects(authority.fetch(envelope,url('/large')), {code:'capability_response_limit'});
    const before = seen.length;
    await assert.rejects(authority.fetch(envelope,url('/ok'),{headers:{authorization:'Bearer synthetic-model-input'}}), {code:'capability_header_denied'});
    assert.equal(seen.length,before);
    await authority.stop(envelope.root_id);
    await assert.rejects(authority.fetch(envelope,url('/ok')), {code:'capability_stale'});
    assert.equal(seen.length,before);
    assert.equal(worker.channel.state().retained,0);
  } finally { await authority.close(); await worker.close(); db.close(); await new Promise(resolve=>server.close(resolve)); }
});
