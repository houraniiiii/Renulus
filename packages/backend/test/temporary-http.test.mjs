// SPDX-License-Identifier: MIT
import '../../harness/test/owned-environment.mjs';
import assert from 'node:assert/strict';
import { test } from 'node:test';
import http from 'node:http';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { Effect, ManagedRuntime, Stream } from 'effect';
import { TestLLM } from '@opencode/ai/testing';
import { createTemporaryFamily } from '../src/domain/temporary/index.ts';
import { openVolatileHarness } from '../../harness/src/volatile-host.ts';
import { openTargetFacade } from '../src/http/target.ts';

async function fixture() {
  const root = mkdtempSync(join(tmpdir(), 'renulus-temporary-http-'));
  const runtime = ManagedRuntime.make(TestLLM.testLayer()), client = await runtime.runPromise(TestLLM.Test);
  const host = await openVolatileHarness({ root, profileId: 'synthetic-profile', storeId: 'synthetic-store',
    domainStoreId: 'synthetic-domain', domainPath: 'unused.sqlite', model: { providerId: 'synthetic', modelId: 'volatile', client,
      configuration: { model: 'synthetic/volatile', providers: { synthetic: { package: '@opencode/ai/providers/openai-compatible',
        settings: { baseURL: 'https://synthetic.invalid/v1' }, models: { volatile: { limit: { context: 128000, output: 4096 } } } } } } } });
  await host.activate('synthetic-http');
  const session = await host.createSession({ operationId: 'synthetic-create', title: 'Temporary' });
  const graphs = new Map(), receipts = new Map(); let committed, activations = 0;
  const storage = { close: async () => {}, command: async c => {
    if (c.type === 'learning.get') return { identity: { type: 'learn_thread', id: c.threadId }, title: 'Synthetic HTTP', retention: 'saved', revision: 1 };
    if (c.type === 'temporary.save.begin') {
      committed = { id: c.plan.id, state: 'staged', cancellationEpoch: c.plan.cancellationEpoch, threadId: c.plan.threadId,
        rootSessionId: c.plan.rootSessionId, sessionIds: c.plan.sessionIds };
      receipts.set(c.plan.idempotencyKey, committed); return committed;
    }
    if (c.type === 'temporary.save.copied') return { ...committed, state: 'copied' };
    if (c.type === 'temporary.save.activate') {
      activations++; committed = { ...committed, state: 'active' };
      for (const [key, r] of receipts) if (r.id === committed.id) receipts.set(key, committed);
      return committed;
    }
    if (c.type === 'temporary.save.committed') { const r = receipts.get(c.idempotencyKey); return r?.state === 'active' ? r : null; }
    throw new Error(c.type);
  } };
  const family = createTemporaryFamily({ host, rootSessionId: session.id, storage,
    saved: { importSession: async d => graphs.set(d.info.id, d), exportSession: async id => graphs.get(id), removeSession: async id => graphs.delete(id) },
    identity: { profileId: 'synthetic-profile', storeId: 'synthetic-store' }, current: async () => ({ contextEpoch: 0, policyRevision: 1 }), settle: async () => 'settled' });
  const facade = await openTargetFacade({ port: 0, token: 'synthetic-token', storage, temporary: { open: async () => family } });
  const base = `http://127.0.0.1:${facade.port}`;
  const request = (path, body, key = 'synthetic-http-key') => fetch(base + path, { method: 'POST', headers: {
    'x-renulus-token': 'synthetic-token', 'content-type': 'application/json', 'idempotency-key': key }, body: JSON.stringify(body) });
  const created = await request('/api/v1/conversations', { temporary: true, title: 'Synthetic HTTP' });
  assert.equal(created.status, 201); const summary = await created.json();
  return { family, receipts, storage, activations: () => activations, summary, base, request, runtime, client,
    async close() { await facade.close(); await host.close({ timeoutMs: 10000 }); await runtime.dispose(); rmSync(root, { recursive: true, force: true }); } };
}

test('Authenticated temporary HTTP owner socket abort cancels, settles and discards the live family', { timeout: 120000 }, async () => {
  const f = await fixture();
  try {
    await f.runtime.runPromise(f.client.push(Stream.fromEffect(Effect.never)));
    const body = JSON.stringify({ expected_revision: 1, text: 'Synthetic AKI question', request_id: 'synthetic-http-send' });
    let response;
    const req = http.request(`${f.base}/api/v1/conversations/learning/${f.summary.identity.id}/messages`, { method: 'POST', headers: {
      'x-renulus-token': 'synthetic-token', 'content-type': 'application/json', 'content-length': Buffer.byteLength(body), 'idempotency-key': 'synthetic-http-send' } });
    const received = new Promise((resolve, reject) => { req.on('response', r => { response = r; r.once('data', resolve); }); req.once('error', reject); });
    req.end(body); await received; await f.runtime.runPromise(f.client.wait(1));
    response.destroy(); req.destroy();
    await new Promise((resolve, reject) => {
      const deadline = Date.now() + 15000;
      const check = () => { if (f.family.status().state === 'discarded') resolve(); else if (Date.now() > deadline) reject(new Error(JSON.stringify(f.family.status()))); else setTimeout(check, 10); }; check();
    });
    assert.equal(f.family.status().state, 'discarded');
  } finally { await f.close(); }
});

test('Temporary HTTP normal completion detaches; Save replay returns the same committed reference', { timeout: 120000 }, async () => {
  const f = await fixture();
  try {
    await f.runtime.runPromise(f.client.push(TestLLM.text('Synthetic transplant teaching', 'answer')));
    const response = await f.request(`/api/v1/conversations/learning/${f.summary.identity.id}/messages`, {
      expected_revision: 1, text: 'Synthetic transplant question', request_id: 'synthetic-http-send' }, 'synthetic-http-send');
    assert.equal(response.status, 200); const stream = await response.text();
    for (const event of ['started', 'progress', 'sources', 'delta', 'completed']) assert.ok(stream.includes(`event: ${event}\n`), stream);
    assert.equal(f.family.status().state, 'open');
    const path = `/api/v1/conversations/learning/${f.summary.identity.id}/save`;
    const saved = await f.request(path, { expected_revision: 3 }, 'synthetic-http-save');
    assert.equal(saved.status, 200); const first = await saved.json();
    const replay = await f.request(path, { expected_revision: 3 }, 'synthetic-http-save');
    assert.equal(replay.status, 200); assert.deepEqual(await replay.json(), first);
    assert.equal(f.family.status().state, 'saved'); assert.equal(f.receipts.size, 1);
  } finally { await f.close(); }
});

test('Committed temporary Save replays its durable reference after restart without a second activation', { timeout: 120000 }, async () => {
  const f = await fixture();
  try {
    await f.runtime.runPromise(f.client.push(TestLLM.text('Synthetic glomerular teaching', 'answer')));
    const sent = await f.request(`/api/v1/conversations/learning/${f.summary.identity.id}/messages`, {
      expected_revision: 1, text: 'Synthetic glomerular question', request_id: 'synthetic-http-send' }, 'synthetic-http-send');
    assert.equal(sent.status, 200); await sent.text();
    const path = `/api/v1/conversations/learning/${f.summary.identity.id}/save`;
    const first = await (await f.request(path, { expected_revision: 3 }, 'synthetic-http-save')).json();
    assert.equal(f.activations(), 1);
    // Restart: a fresh facade over the same canonical storage has no live families.
    const restarted = await openTargetFacade({ port: 0, token: 'synthetic-token', storage: f.storage, temporary: { open: async () => f.family } });
    try {
      const replay = await fetch(`http://127.0.0.1:${restarted.port}${path}`, { method: 'POST', headers: {
        'x-renulus-token': 'synthetic-token', 'content-type': 'application/json', 'idempotency-key': 'synthetic-http-save' }, body: JSON.stringify({ expected_revision: 3 }) });
      assert.equal(replay.status, 200); assert.deepEqual(await replay.json(), first);
      assert.equal(f.activations(), 1);
    } finally { await restarted.close(); }
  } finally { await f.close(); }
});
