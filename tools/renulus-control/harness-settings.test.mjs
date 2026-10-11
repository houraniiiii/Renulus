import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { mkdir, mkdtemp, writeFile, readFile, readdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { EventEmitter } from 'node:events';
import { setTimeout as delay } from 'node:timers/promises';
import { parseCli, RenulusController } from './controller.mjs';
import * as control from './controller.mjs';

const root = path.resolve('G:/rh04-contract');
const base = ['--repo', path.join(root, 'repo'), '--python', path.join(root, 'python.exe'),
  '--helper-assets', path.join(root, 'assets')];

test('the fixed Settings fixture requires source Python and reviewed helper assets', () => {
  const config = parseCli([...base, '--harness-settings-fixture', 'v1']);
  assert.equal(config.harnessSettingsFixture, 'v1');
  for (const args of [
    [...base, '--harness-settings-fixture', 'module.py'],
    [...base, '--harness-settings-fixture', 'v1', '--harness-settings-fixture', 'v1'],
    ['--repo', path.join(root, 'repo'), '--python', path.join(root, 'python.exe'), '--harness-settings-fixture', 'v1'],
    [...base, '--executable', path.join(root, 'Renulus.exe'), '--harness-settings-fixture', 'v1'],
  ]) assert.throws(() => parseCli(args), { code: 'invalid_cli' });
  assert.equal(parseCli(base).harnessSettingsFixture, undefined);
});

test('public start binds immutable metadata and leaves the live root empty before Python ownership', async () => {
  await mkdir('G:/r4-contract', { recursive: true });
  const directory = await mkdtemp('G:/r4-contract/s-');
  const stateRoot = path.join(directory, 'control');
  const repo = path.join(directory, 'source'), helperAssets = path.join(directory, 'assets');
  await mkdir(path.join(repo, 'packaging/runtime'), { recursive: true });
  await mkdir(path.join(repo, 'packages/harness/src'), { recursive: true });
  await writeFile(path.join(repo, 'packages/harness/src/main.mjs'), '// Synthetic metadata-only source placeholder');
  await mkdir(helperAssets);
  const groups = {};
  for (const name of ['docling', 'embedding', 'ocr']) {
    const bytes = Buffer.from('synthetic-' + name);
    await writeFile(path.join(helperAssets, name + '.bin'), bytes);
    groups[name] = { revision: 'synthetic', source_url: 'https://example.invalid/' + name,
      files: [{ path: name + '.bin', size: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex') }] };
  }
  const manifest = JSON.stringify({ version: 1, groups });
  await writeFile(path.join(helperAssets, 'manifest.json'), manifest);
  await writeFile(path.join(repo, 'packaging/runtime/helper-assets.json'), manifest);
  const stopped = new Error('Synthetic OS launch boundary held; no app starts');
  const documents = [];
  const controller = new RenulusController({ repo, python: path.join(directory, 'runtime/python.exe'),
    helperAssets, stateRoot, harnessSettingsFixture: 'v1' }, {
    preflight: async () => ({ executable: path.join(repo, 'electron.exe'), cwd: repo, args: ['.'], mainSha256: 'synthetic' }),
    launch: async ({ env }) => {
      const option = JSON.parse(env.RENULUS_BACKGROUND_HARNESS_SETTINGS);
      assert.equal(option.kind, 'harness-settings-synthetic-v1');
      assert.equal(option.helperAssets, helperAssets);
      const raw = await readFile(option.startupDocument);
      assert.equal(createHash('sha256').update(raw).digest('hex'), option.startupSha256);
      const document = JSON.parse(raw);
      assert.equal(document.process.profile_root, env.RENULUS_PROFILE);
      assert.deepEqual(await readdir(env.RENULUS_PROFILE), []);
      assert.equal(document.initial_spec, undefined);
      assert.equal(document.process.host_entry, path.join(repo, 'packages/harness/src/main.mjs'));
      documents.push({ file: option.startupDocument, raw, document });
      throw stopped;
    },
  });
  try {
    await assert.rejects(controller.run('renulus_start'), error => error.message === stopped.message);
    await assert.rejects(controller.run('renulus_start'), error => error.message === stopped.message);
    assert.equal(documents.length, 2);
    assert.notEqual(documents[0].file, documents[1].file);
    assert.equal(documents[0].document.initialize_new, true);
    assert.equal(documents[1].document.initialize_new, false);
    assert.deepEqual(documents[0].document.process, documents[1].document.process);
    assert.deepEqual(await readFile(documents[0].file), documents[0].raw);
  } finally { await controller.shutdown(); }
});

test('passive Settings observation records exact revisions and never retains account/body data', async () => {
  const origin = 'http://127.0.0.1:18777';
  const bytes = Buffer.from(JSON.stringify({ requested: 'a'.repeat(64), effective: 'b'.repeat(64),
    failed: null, admission_open: true, configuration: { secret: 'synthetic-do-not-retain' },
    error: { code: 'harness_configuration_busy', message: 'synthetic-do-not-retain' } }));
  let reads = 0;
  const response = (url, length = String(bytes.length)) => ({ url, status: 200, method: 'GET', length });
  const readBytes = async () => { reads++; return bytes; };
  const row = await control.captureSettingsResponse(response(origin + '/api/v1/runtime/harness/configuration'), origin, readBytes);
  assert.deepEqual(row, { method: 'GET', path: '/api/v1/runtime/harness/configuration', status: 200,
    requested: 'a'.repeat(64), effective: 'b'.repeat(64), failed: null, admission_open: true,
    error_code: 'harness_configuration_busy' });
  assert.equal(await control.captureSettingsResponse(response(origin + '/api/v1/connections'), origin, readBytes), null);
  assert.equal(await control.captureSettingsResponse(response('http://127.0.0.1:18778/api/v1/runtime/harness/configuration'), origin, readBytes), null);
  assert.equal(reads, 1);
  const oversized = await control.captureSettingsResponse(response(origin + '/api/v1/runtime/harness/configuration', '65537'), origin, readBytes);
  assert.equal(oversized.metadata, 'unavailable');
  const missingLength = await control.captureSettingsResponse({ ...response(origin + '/api/v1/runtime/harness/configuration'), length: undefined }, origin, readBytes);
  assert.equal(missingLength.metadata, 'unavailable');
  assert.equal(reads, 1);
  const oversizedBytes = await control.captureSettingsResponse(response(origin + '/api/v1/runtime/harness/configuration'), origin, async () => Buffer.alloc(65537));
  assert.equal(oversizedBytes.metadata, 'unavailable');
});

test('held POST observations expire while GET hashes and late native read ownership remain bounded', async () => {
  await mkdir('G:/r4-contract', { recursive: true });
  const directory = await mkdtemp('G:/r4-contract/o-');
  const repo = path.join(directory, 'source'), helperAssets = path.join(directory, 'assets');
  await mkdir(repo); await mkdir(helperAssets);
  const python = path.join(directory, 'runtime/python.exe'), main = path.join(repo, 'electron.exe');
  const origin = 'http://127.0.0.1:18777', page = new EventEmitter(), app = new EventEmitter();
  const native = new EventEmitter(), replies = new Map(), nativeReads = [], legacyReads = [];
  native.send = async (command, args) => {
    assert.ok(['Network.enable', 'Network.getResponseBody'].includes(command), 'Only passive native lookup commands are allowed');
    if (command === 'Network.enable') return {};
    assert.equal(Object.keys(args).join(','), 'requestId');
    const reply = replies.get(args.requestId);
    assert.ok(reply, 'Lookup must use the exact observed native identity');
    nativeReads.push(args.requestId);
    return await reply;
  };
  page.evaluate = async () => { throw new Error('Renderer evaluation is not a metadata read'); };
  const child = { pid: 900001, exitCode: null, signalCode: null };
  let environment, closed = false;
  page.url = () => origin + '/'; page.isClosed = () => closed;
  page.locator = () => ({ count: async () => 1, isVisible: async () => true,
    ariaSnapshot: async () => '- heading "Synthetic Settings"', evaluateAll: async () => [] });
  app.process = () => child; app.windows = () => [page];
  app.context = () => ({ setDefaultTimeout() {}, route: async () => {},
    newCDPSession: async target => { assert.equal(target, page); return native; } });
  app.evaluate = async fn => fn.name === 'installObservation' ? undefined : {
    name: 'Renulus', pid: child.pid, ownerPid: String(process.pid), executable: main,
    background: true, attachedBackend: false, packaged: false, profile: environment.RENULUS_PROFILE,
    userData: path.join(path.dirname(environment.RENULUS_PROFILE), 'd'), seen: 1, violations: [],
    windows: [{ visible: false, focused: false, focusable: false, backgroundThrottling: false,
      sandbox: true, contextIsolation: true, nodeIntegration: false }],
    children: [{ pid: 900002, executable: python, profile: environment.RENULUS_PROFILE, exited: false }],
  };
  app.close = async () => { closed = true; child.exitCode = 0; native.emit('close'); };
  const controller = new RenulusController({ repo, python, helperAssets,
    stateRoot: path.join(directory, 'control'), harnessSettingsFixture: 'v1' }, {
    preflight: async () => ({ executable: main, cwd: repo, args: ['.'], mainSha256: 'synthetic' }),
    launch: async ({ env }) => { environment = env; return app; },
    inspect: async () => closed ? [] : [
      { pid: child.pid, executable: main, parentPid: process.pid, created: 'synthetic-main' },
      { pid: 900002, executable: python, parentPid: child.pid, created: 'synthetic-backend' },
    ],
  });
  const raw = Buffer.from(JSON.stringify({ requested: 'c'.repeat(64), effective: 'b'.repeat(64),
    failed: null, admission_open: true, configuration: { secret: 'synthetic-do-not-retain' },
    message: 'synthetic-prose-do-not-retain' }));
  const payload = { body: raw.toString('utf8'), base64Encoded: false };
  const releases = new Map();
  function observe(requestId, method, pathname, held = false, responsePath = pathname) {
    const reply = held ? new Promise(resolve => { releases.set(requestId, () => resolve(payload)); }) : Promise.resolve(payload);
    replies.set(requestId, reply);
    const url = origin + pathname;
    native.emit('Network.requestWillBeSent', { requestId, request: { url, method } });
    native.emit('Network.responseReceived', { requestId, response: { url: origin + responsePath, status: 200,
      headers: { 'Content-Length': String(raw.length) } } });
    native.emit('Network.loadingFinished', { requestId });
    // The original public response seam reproduces the existing unbounded wait.
    // The repaired native path must never call this Playwright body API.
    page.emit('response', { url: () => origin + responsePath, status: () => 200,
      request: () => ({ method: () => method }), headerValue: async () => String(raw.length),
      body: async () => { legacyReads.push(requestId); return Buffer.from((await reply).body); } });
  }
  try {
    await controller.run('renulus_start');
    observe('unrelated', 'GET', '/api/v1/connections');
    observe('stage', 'POST', '/api/v1/runtime/harness/configuration', true);
    observe('activate', 'POST', '/api/v1/runtime/harness/configuration/activate', true);
    observe('readback', 'GET', '/api/v1/runtime/harness/configuration');
    const started = Date.now();
    await delay(2100);
    const snapshot = await controller.run('renulus_snapshot');
    assert.equal(snapshot.settingsResponses.length, 3, 'Both held POSTs must publish status-only rows by their deadline');
    assert.ok(Date.now() - started < 3000, 'Expired observations must not wait again for native read completion');
    assert.deepEqual(snapshot.settingsResponses.filter(row => row.method === 'POST'), [
      { method: 'POST', path: '/api/v1/runtime/harness/configuration', status: 200, metadata: 'unavailable' },
      { method: 'POST', path: '/api/v1/runtime/harness/configuration/activate', status: 200, metadata: 'unavailable' },
    ]);
    assert.deepEqual(snapshot.settingsResponses.find(row => row.method === 'GET'), {
      method: 'GET', path: '/api/v1/runtime/harness/configuration', status: 200,
      requested: 'c'.repeat(64), effective: 'b'.repeat(64), failed: null, admission_open: true });
    assert.equal(snapshot.settingsResponsesPending, 2, 'Deadline does not cancel either actual native read');
    assert.equal(snapshot.settingsResponsesDropped, 0);
    assert.deepEqual(legacyReads, []);
    assert.deepEqual(nativeReads, ['stage', 'activate', 'readback']);

    observe('held-third', 'POST', '/api/v1/runtime/harness/configuration', true);
    observe('held-fourth', 'POST', '/api/v1/runtime/harness/configuration/activate', true);
    observe('over-read-cap', 'GET', '/api/v1/runtime/harness/configuration');
    observe('mismatched-path', 'GET', '/api/v1/runtime/harness/configuration', false, '/api/v1/runtime/harness/configuration/activate');
    native.emit('Network.responseReceived', { requestId: 'unknown-native-input',
      response: { url: origin + '/api/v1/runtime/harness/configuration', status: 200, headers: { 'Content-Length': String(raw.length) } } });
    await delay(2100);
    const full = await controller.run('renulus_snapshot');
    assert.equal(full.settingsResponsesPending, 4);
    assert.deepEqual(nativeReads, ['stage', 'activate', 'readback', 'held-third', 'held-fourth']);
    assert.equal(full.settingsResponses.length, 6);
    const immutable = JSON.stringify(full.settingsResponses);
    assert.ok(!immutable.includes('synthetic-do-not-retain') && !immutable.includes('synthetic-prose-do-not-retain'));
    releases.get('stage')(); releases.get('activate')();
    await new Promise(resolve => setImmediate(resolve));
    const late = await controller.run('renulus_snapshot');
    assert.equal(late.settingsResponsesPending, 2);
    assert.equal(JSON.stringify(late.settingsResponses), immutable, 'Late bytes cannot rewrite or duplicate a published observation');
    observe('after-late-read', 'GET', '/api/v1/runtime/harness/configuration');
    await new Promise(resolve => setImmediate(resolve));
    const resumed = await controller.run('renulus_snapshot');
    assert.equal(resumed.settingsResponses.at(-1).effective, 'b'.repeat(64));
    assert.equal(resumed.settingsResponsesPending, 2);
    const result = await controller.run('renulus_close');
    assert.equal(result.normal, true);
    const receipt = JSON.parse(await readFile(result.receipt));
    assert.equal(receipt.closes[0].normal, true);
    assert.equal(receipt.settingsResponsesPending, 2, 'Closing the observer cannot invent completion of held native lookups');
    releases.get('held-third')(); releases.get('held-fourth')();
    await new Promise(resolve => setImmediate(resolve));
    await controller.run('renulus_errors');
    assert.equal(JSON.parse(await readFile(result.receipt)).settingsResponsesPending, 0);
    assert.deepEqual(legacyReads, []);
  } finally {
    for (const release of releases.values()) release();
    await controller.shutdown();
  }
});
