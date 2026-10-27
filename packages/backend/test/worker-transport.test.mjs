// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { mkdtemp } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { openEngineWorker } from '../src/workers/process.ts';
import { createWorkerTransport } from '../src/workers/transport.ts';

test('real Node broker command binds final permit and returns no-account failure without discovery or inference', {
  skip: !process.env.RENULUS_BACKEND_TEST_PYTHON, timeout: 45_000,
}, async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'renulus-worker-broker-'));
  const repository = fileURLToPath(new URL('../../..', import.meta.url));
  const revisions = { configuration: 1, grant: 1, context: 1, deletion: 1, cancellation: 0 };
  const worker = await openEngineWorker({ python: process.env.RENULUS_BACKEND_TEST_PYTHON,
    sourceRoot: repository, launchRoot: path.join(root, 'launch'), retention: 'saved',
    identity: { profile_id: 'synthetic-profile', domain_store_id: 'synthetic-domain', runtime_store_id: 'synthetic-native',
      authority_epoch: 1, process_generation: 'synthetic-broker' }, current: () => revisions,
    broker: { profile_root: path.join(root, 'profile'), state_root: path.join(root, 'profile/state') } });
  const route = { provider_id: 'opencode-go', catalog_model_id: 'mimo-v2.6-pro', wire_model_id: 'mimo-v2.6-pro',
    endpoint: 'https://opencode.ai/zen/go/v1/chat/completions', protocol: 'openai-chat',
    credential_ref: 'synthetic-credential-reference', credential_epoch: 0, catalogue_listed: null };
  const body = Buffer.from('{"stream":true,"model":"mimo-v2.6-pro","max_completion_tokens":32,"messages":[]}');
  const hash = createHash('sha256').update(body).digest('hex');
  const permit = { permit_id: 'synthetic_permit_abcdefghijklmnopqrstuvwxyz', run_id: 'synthetic-run', root_id: 'synthetic-run',
    step_id: 'synthetic-step', payload_hash: hash, request_kind: 'primary', dispatch_purpose: 'explain', grant_epoch: 1,
    output_tokens: 32, required_capabilities: ['text'], state: 'dispatched', result_reference: null, failure_code: null, dispatch_allowed: true };
  let checks = 0;
  const transport = createWorkerTransport({ channel: worker.channel, maxChunkBytes: worker.ready.capacity.max_chunk_bytes,
    retention: 'saved', registryHash: async () => 'b'.repeat(64), checkCurrent: async current => { checks++; assert.equal(current, permit); } });
  const input = () => ({ permit, route, serialized: { method: 'POST', url: route.endpoint,
    headers: { 'content-type': 'application/json', accept: 'text/event-stream' }, body_base64: body.toString('base64') },
    proof: { payload_hash: hash, body_bytes: body.length, input_manifest_sha256: 'a'.repeat(64), output_tokens: 32 }, signal: new AbortController().signal });
  try {
    await assert.rejects(transport.send(input()), { code: 'broker_not_activated' });
    assert.equal(checks, 1);
    const activation = worker.channel.submit('credential.activate', {}, { operation_id: 'direct-settings-activation', attempt_id: 'attempt-1' });
    const credentials = await activation.terminal; worker.channel.release(activation.requestId);
    assert.equal(credentials.reply.outcome, 'committed_reference');
    assert.equal(credentials.reply.result.tag, 'credentials');
    assert.ok(credentials.reply.result.credentials.every(item => !item.configured && !item.usable));
    const selected = credentials.reply.result.credentials.find(item => item.provider_id === route.provider_id);
    route.credential_ref = selected.credential_ref; route.credential_epoch = selected.credential_revision;
    // A new final admission is required; the first permit remains a consumed tombstone.
    permit.permit_id = 'synthetic_permit_second_abcdefghijklmnopqrst';
    await assert.rejects(transport.send(input()), { code: 'authentication_required' });
    assert.equal(checks, 2);
    assert.equal(worker.channel.state().retained, 0);
  } finally { await worker.close(); }
});
