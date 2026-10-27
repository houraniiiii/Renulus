// SPDX-License-Identifier: MIT
import '../../harness/test/owned-environment.mjs';
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createConnection } from 'node:net';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';
import { mkdtemp } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { openTargetFacade } from '../src/http/target.ts';
import { PluginLifecycleError } from '../src/plugins/manifest.ts';
import { createPluginLifecycle } from '../src/plugins/lifecycle.ts';
import { createCapabilityPluginHarness, CAPABILITY_COHORT } from '../../harness/src/capability-plugins.ts';
import { openHarness } from '../../harness/src/host.ts';
import { acquireStore } from '../../harness/src/ownership.ts';
import { scriptedModel } from '../../harness/test/scripted-model.ts';

const token = 'synthetic-target-shutdown-token';
const headers = { 'x-renulus-token': token };
function pipeline(t, port, requests) {
  const socket = createConnection({ host: '127.0.0.1', port });
  t.after(() => socket.destroy());
  return new Promise((resolve, reject) => {
    let wire = '';
    socket.setTimeout(2000, () => socket.destroy(new Error('synthetic_pipeline_timeout')));
    socket.on('data', chunk => { wire += chunk.toString('utf8'); });
    socket.once('error', reject);
    socket.once('end', () => resolve(wire));
    socket.once('connect', () => socket.write(requests.map(([method, pathname], i) =>
      `${method} ${pathname} HTTP/1.1\r\nHost: 127.0.0.1:${port}\r\nX-Renulus-Token: ${token}\r\nContent-Length: 0\r\nConnection: ${i === requests.length - 1 ? 'close' : 'keep-alive'}\r\n\r\n`).join('')));
  });
}

test('target loopback pipeline shares shutdown, drains prior ordinary work, and synchronously seals new work', { timeout: 5000 }, async t => {
  const started = Promise.withResolvers(), release = Promise.withResolvers();
  const events = [];
  const facade = await openTargetFacade({ port: 0, token,
    storage: { command: async () => {
      events.push('ordinary-start'); started.resolve(); await release.promise;
      events.push('ordinary-end'); return { synthetic: true };
    }, close: async () => { events.push('storage-close'); } },
    settlePlugins: async () => { events.push('plugins-settled'); },
  });
  t.after(async () => { release.resolve(); await facade.close(); });
  const response = pipeline(t, facade.port, [
    ['GET', '/api/v1/data/export'], ['POST', '/api/v1/runtime/shutdown'],
    ['POST', '/api/v1/runtime/shutdown'], ['GET', '/api/v1/data/export'],
  ]);
  await started.promise;
  assert.deepEqual(events, ['ordinary-start']);
  release.resolve();
  const wire = await response;
  assert.deepEqual([...wire.matchAll(/HTTP\/1\.1 (\d{3}) /g)].map(match => Number(match[1])), [200, 200, 200, 503]);
  assert.equal([...wire.matchAll(/"state":"settled"/g)].length, 2);
  assert.match(wire, /"code":"runtime_stopping"/);
  await facade.closed;
  await facade.close();
  assert.deepEqual(events, ['ordinary-start', 'ordinary-end', 'plugins-settled', 'storage-close']);
});

for (const entry of ['HTTP', 'direct']) {
  test(`target held ${entry} shutdown retains status and storage until a successful retry`, { timeout: 5000 }, async t => {
    let allowed = false, settlements = 0, storageCloses = 0, commands = 0, statusReads = 0, closed = false;
    const facade = await openTargetFacade({ port: 0, token,
      storage: { command: async () => { commands++; return {}; }, close: async () => { storageCloses++; } },
      plugins: { status: async () => { statusReads++; return { state: allowed ? 'ready' : 'held' }; } },
      settlePlugins: async () => { settlements++; if (!allowed) throw new PluginLifecycleError('plugin_quiescence_held'); },
    });
    facade.closed.then(() => { closed = true; });
    t.after(async () => { allowed = true; await facade.close(); });
    const request = (pathname, options = {}) => fetch(`http://127.0.0.1:${facade.port}${pathname}`,
      { headers, signal: AbortSignal.timeout(2000), ...options });
    const shutdown = async () => {
      if (entry === 'direct') return facade.close();
      const response = await request('/api/v1/runtime/shutdown', { method: 'POST' });
      const value = await response.json();
      if (!allowed) { assert.equal(response.status, 409); assert.equal(value.error.code, 'plugin_quiescence_held'); }
      else { assert.equal(response.status, 200); assert.deepEqual(value, { state: 'settled', api_version: 1 }); }
    };
    for (let attempt = 0; attempt < 2; attempt++) {
      if (entry === 'direct') await assert.rejects(shutdown(), { code: 'plugin_quiescence_held' });
      else await shutdown();
      assert.equal(closed, false);
      assert.equal(storageCloses, 0);
    }
    assert.equal(settlements, 2);
    for (const pathname of ['/api/v1/meta', '/api/v1/runtime/plugins', '/api/v1/runtime/status']) {
      const unauthenticated = await request(pathname, { headers: {} });
      assert.equal(unauthenticated.status, 401);
      await unauthenticated.arrayBuffer();
      const response = await request(pathname);
      assert.equal(response.status, 200);
      const value = await response.json();
      if (pathname === '/api/v1/runtime/status') {
        assert.equal(value.state, 'held'); assert.equal(value.admission, 'closed');
        assert.equal(value.active_operations, 0);
      }
    }
    assert.equal(statusReads, 1);
    for (const [method, pathname] of [['GET', '/api/v1/data/export'], ['POST', '/api/v1/runtime/plugins/activate']]) {
      const response = await request(pathname, { method });
      assert.equal(response.status, 503);
      assert.equal((await response.json()).error.code, 'runtime_stopping');
    }
    assert.equal(commands, 0);
    allowed = true;
    await shutdown();
    await facade.closed;
    await facade.close();
    assert.equal(settlements, 3);
    assert.equal(storageCloses, 1);
    assert.equal(closed, true);
  });
}

test('real native 25ms refused close retains its store and readable lifecycle until the same handle settles', {
  timeout: 30_000,
}, async t => {
  const root = await mkdtemp(path.join(tmpdir(), 'renulus-held-native-target-'));
  const model = await scriptedModel('Synthetic uninterruptible answer', true);
  const python = process.env.RENULUS_BACKEND_TEST_PYTHON ?? 'C:/Renulus/dev/python/Scripts/python.exe';
  const pythonPath = fileURLToPath(new URL('../../../runtime', import.meta.url));
  let selected, selectedOpens = 0, storageCloses = 0, storageOpen = true;
  const handles = [], proofs = [];
  const harness = createCapabilityPluginHarness({ root,
    authority: {
      narrow: async () => {},
      quiesce: async () => ({ state: 'settled', active_operations: 0, pending_permissions: 0,
        worker_leases: 0, uncertain_effects: [] }),
    },
    openHost: async configuration => {
      await promisify(execFile)(python, ['-c', `from pathlib import Path
from renulus.runtime.harness_profile import prepare_harness_profile
import sys
prepare_harness_profile(Path(sys.argv[1]), profile_id='synthetic-held-native',
 domain_store_id='synthetic-held-domain', runtime_store_id='synthetic-held-runtime', domain_path='domain/renulus.sqlite3')`, configuration.root],
      { env: { ...process.env, PYTHONPATH: pythonPath, PYTHONDONTWRITEBYTECODE: '1' }, windowsHide: true });
      const native = await openHarness({ root: configuration.root, profileId: 'synthetic-held-native',
        storeId: 'synthetic-held-runtime', domainStoreId: 'synthetic-held-domain', domainPath: 'domain/renulus.sqlite3',
        capabilityArtifacts: configuration.artifacts, ...(configuration.isolation === 'selected-profile' ? { model } : {}) });
      if (configuration.isolation === 'selected-profile') { selected = native; selectedOpens++; }
      return {
        inspect: () => native.inspectCapabilities(configuration.isolation),
        close: async () => {
          const proof = await native.close({ timeoutMs: configuration.isolation === 'selected-profile' ? 25 : 5000 });
          if (configuration.isolation === 'selected-profile') { handles.push(native); proofs.push(proof); }
          return proof;
        },
      };
    },
  });
  const lifecycle = createPluginLifecycle({ root, host: harness, cohortSource: CAPABILITY_COHORT });
  let facade, facadeClosed = false;
  t.after(async () => {
    model.release();
    await selected?.settled().catch(() => {});
    await facade?.close();
    await lifecycle.close(); await harness.close(); await model.close();
  });
  await lifecycle.stage([]);
  const active = await lifecycle.activate();
  assert.equal(active.state, 'ready');
  await selected.activate('synthetic-held-policy');
  const session = await selected.createSession({ operationId: 'held-native-session', title: 'Synthetic shutdown' });
  await selected.submit({ sessionId: session.id, operationId: 'held-native-turn', attemptId: '1', text: 'Synthetic educational request' });
  await model.started();
  facade = await openTargetFacade({ port: 0, token, plugins: lifecycle,
    storage: { command: async () => { assert.equal(storageOpen, true); return {}; },
      close: async () => { storageOpen = false; storageCloses++; } },
    settlePlugins: async () => { await lifecycle.close(); await harness.close(); },
  });
  facade.closed.then(() => { facadeClosed = true; });
  const request = (pathname, options = {}) => fetch(`http://127.0.0.1:${facade.port}${pathname}`,
    { headers, signal: AbortSignal.timeout(2000), ...options });
  for (let attempt = 0; attempt < 2; attempt++) {
    const response = await request('/api/v1/runtime/shutdown', { method: 'POST' });
    assert.equal(response.status, 503);
    assert.equal((await response.json()).error.code, 'backend_operation_failed');
    assert.deepEqual(proofs.at(-1), { state: 'blocked', outcome: 'uncertain_after_disconnect' });
    assert.equal(storageOpen, true); assert.equal(storageCloses, 0); assert.equal(facadeClosed, false);
    assert.equal((await selected.status()).state, 'closing');
    await assert.rejects(acquireStore(path.join(root, 'state/harness'), 'synthetic-held-runtime'), /store_owned/);
    const runtimeResponse = await request('/api/v1/runtime/status');
    assert.equal(runtimeResponse.status, 200);
    const runtime = await runtimeResponse.json();
    assert.equal(runtime.state, 'held'); assert.equal(runtime.admission, 'closed');
    const pluginResponse = await request('/api/v1/runtime/plugins');
    assert.equal(pluginResponse.status, 200);
    const status = await pluginResponse.json();
    assert.equal(status.state, 'held'); assert.equal(status.error, 'plugin_lifecycle_closing');
    assert.equal(status.active_operation_id, active.active_operation_id);
    assert.equal(status.reobserved, false);
    await assert.rejects(lifecycle.stage([]), { code: 'plugin_lifecycle_closed' });
  }
  assert.equal(selectedOpens, 1);
  assert.deepEqual(handles, [selected, selected]);
  model.release();
  await selected.settled();
  const response = await request('/api/v1/runtime/shutdown', { method: 'POST' });
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { state: 'settled', api_version: 1 });
  await facade.closed;
  assert.deepEqual(handles, [selected, selected, selected]);
  assert.deepEqual(proofs.at(-1), { state: 'closed', outcome: 'cancelled_settled' });
  assert.equal(storageCloses, 1); assert.equal(storageOpen, false); assert.equal(selectedOpens, 1);
  const successor = await acquireStore(path.join(root, 'state/harness'), 'synthetic-held-runtime');
  await successor.release();
  assert.equal(await model.count(), 1, 'shutdown retry never resubmits generation');
});
