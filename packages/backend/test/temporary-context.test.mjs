// SPDX-License-Identifier: MIT
import '../../harness/test/owned-environment.mjs';
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { mkdtempSync, readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { tmpdir } from 'node:os';
import { ManagedRuntime } from 'effect';
import { TestLLM } from '@opencode/ai/testing';
import { openVolatileHarness, invokeVolatileHost } from '../../harness/src/volatile-host.ts';

const sentinel = 'SYNTHETIC_VOLATILE_CASE_bf04_a73dc1';
async function fixture() {
  const root = mkdtempSync(path.join(tmpdir(), 'renulus-bf04-'));
  const runtime = ManagedRuntime.make(TestLLM.testLayer()), client = await runtime.runPromise(TestLLM.Test);
  const model = { providerId: 'synthetic', modelId: 'volatile', client,
    configuration: { model: 'synthetic/volatile', providers: { synthetic: { package: '@opencode/ai/providers/openai-compatible',
      settings: { baseURL: 'https://synthetic.invalid/v1' }, models: { volatile: { limit: { context: 128000, output: 4096 } } } } } } };
  const host = await openVolatileHarness({ root, profileId: 'synthetic-profile', storeId: 'synthetic-volatile',
    domainStoreId: 'synthetic-volatile-domain', domainPath: 'unused.sqlite', model });
  await host.activate('synthetic-bf04');
  return { root, host, runtime, client };
}
function diskFiles(root) {
  return readdirSync(root, { withFileTypes: true }).flatMap(item => item.isDirectory() ? diskFiles(path.join(root, item.name)) : [path.join(root, item.name)]);
}
test('actual native Session/Job/history and media sentinel remain RAM before Save', { timeout: 30000 }, async () => {
  const f = await fixture();
  try {
    await f.runtime.runPromise(f.client.push(TestLLM.text('Synthetic native answer ' + sentinel, 'answer')));
    const result = await invokeVolatileHost(f.host, { text: 'Synthetic educational source ' + sentinel, signal: new AbortController().signal });
    assert.equal(result, 'Synthetic native answer ' + sentinel);
    assert.equal((await f.runtime.runPromise(f.client.requests())).length, 1);
    assert.deepEqual(diskFiles(f.root), []);
    await assert.rejects(f.host.activateStores(), /volatile_store_activation_forbidden/);
  } finally {
    assert.equal((await f.host.close({ timeoutMs: 10000 })).state, 'closed'); await f.runtime.dispose();
    for (const file of diskFiles(f.root)) assert.equal(readFileSync(file).includes(Buffer.from(sentinel)), false);
  }
});
