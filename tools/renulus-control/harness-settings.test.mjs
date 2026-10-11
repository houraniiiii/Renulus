import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { mkdir, mkdtemp, writeFile, readFile, readdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { EventEmitter } from 'node:events';
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
  const response = (url, length = String(bytes.length)) => ({
    url: () => url, status: () => 200, request: () => ({ method: () => 'GET' }),
    headerValue: async () => length, body: async () => { reads++; return bytes; },
  });
  const row = await control.captureSettingsResponse(response(origin + '/api/v1/runtime/harness/configuration'), origin);
  assert.deepEqual(row, { method: 'GET', path: '/api/v1/runtime/harness/configuration', status: 200,
    requested: 'a'.repeat(64), effective: 'b'.repeat(64), failed: null, admission_open: true,
    error_code: 'harness_configuration_busy' });
  assert.equal(await control.captureSettingsResponse(response(origin + '/api/v1/connections'), origin), null);
  assert.equal(await control.captureSettingsResponse(response('http://127.0.0.1:18778/api/v1/runtime/harness/configuration'), origin), null);
  assert.equal(reads, 1);
  const oversized = await control.captureSettingsResponse(response(origin + '/api/v1/runtime/harness/configuration', '65537'), origin);
  assert.equal(oversized.metadata, 'unavailable');
  assert.equal(reads, 1);
});

test('unrelated replies do not consume Settings slots and a held metadata read does not veto normal close', async () => {
  await mkdir('G:/r4-contract', { recursive: true });
  const directory = await mkdtemp('G:/r4-contract/o-');
  const repo = path.join(directory, 'source'), helperAssets = path.join(directory, 'assets');
  await mkdir(repo); await mkdir(helperAssets);
  const python = path.join(directory, 'runtime/python.exe'), main = path.join(repo, 'electron.exe');
  const origin = 'http://127.0.0.1:18777', page = new EventEmitter(), app = new EventEmitter();
  const child = { pid: 900001, exitCode: null, signalCode: null };
  let environment, closed = false;
  page.url = () => origin + '/'; page.isClosed = () => closed;
  page.locator = () => ({ count: async () => 1, isVisible: async () => true,
    ariaSnapshot: async () => '- heading "Synthetic Settings"', evaluateAll: async () => [] });
  app.process = () => child; app.windows = () => [page];
  app.context = () => ({ setDefaultTimeout() {}, route: async () => {} });
  app.evaluate = async fn => fn.name === 'installObservation' ? undefined : {
    name: 'Renulus', pid: child.pid, ownerPid: String(process.pid), executable: main,
    background: true, attachedBackend: false, packaged: false, profile: environment.RENULUS_PROFILE,
    userData: path.join(path.dirname(environment.RENULUS_PROFILE), 'd'), seen: 1, violations: [],
    windows: [{ visible: false, focused: false, focusable: false, backgroundThrottling: false,
      sandbox: true, contextIsolation: true, nodeIntegration: false }],
    children: [{ pid: 900002, executable: python, profile: environment.RENULUS_PROFILE, exited: false }],
  };
  app.close = async () => { closed = true; child.exitCode = 0; };
  const controller = new RenulusController({ repo, python, helperAssets,
    stateRoot: path.join(directory, 'control'), harnessSettingsFixture: 'v1' }, {
    preflight: async () => ({ executable: main, cwd: repo, args: ['.'], mainSha256: 'synthetic' }),
    launch: async ({ env }) => { environment = env; return app; },
    inspect: async () => closed ? [] : [
      { pid: child.pid, executable: main, parentPid: process.pid, created: 'synthetic-main' },
      { pid: 900002, executable: python, parentPid: child.pid, created: 'synthetic-backend' },
    ],
  });
  const raw = Buffer.from(JSON.stringify({ requested: 'c'.repeat(64), effective: null, admission_open: false }));
  const response = (url, body = async () => raw) => ({ url: () => url, status: () => 200,
    request: () => ({ method: () => 'GET' }), headerValue: async () => String(raw.length), body });
  let release;
  try {
    await controller.run('renulus_start');
    for (let i = 0; i < 4; i++) page.emit('response', response(origin + '/api/v1/connections'));
    page.emit('response', response(origin + '/api/v1/runtime/harness/configuration'));
    await new Promise(resolve => setImmediate(resolve));
    const snapshot = await controller.run('renulus_snapshot');
    assert.equal(snapshot.settingsResponsesDropped, 0);
    assert.equal(snapshot.settingsResponses[0].requested, 'c'.repeat(64));
    const held = new Promise(resolve => { release = () => resolve(raw); });
    page.emit('response', response(origin + '/api/v1/runtime/harness/configuration', () => held));
    const result = await controller.run('renulus_close');
    assert.equal(result.normal, true);
    const receipt = JSON.parse(await readFile(result.receipt));
    assert.equal(receipt.closes[0].normal, true);
    assert.equal(receipt.settingsResponsesPending, 1);
  } finally {
    release?.();
    await controller.shutdown();
  }
});
