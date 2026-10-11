import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { mkdir, mkdtemp, writeFile, readFile, readdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { EventEmitter } from 'node:events';
import { parseCli, RenulusController } from './controller.mjs';

const root = path.resolve('G:/rh02-contract');
const base = ['--repo', path.join(root, 'source'), '--python', path.join(root, 'python.exe'),
  '--helper-assets', path.join(root, 'assets')];

test('the fixed learning fixture is source-only and exclusive with Settings', () => {
  const config = parseCli([...base, '--harness-learning-fixture', 'v1']);
  assert.equal(config.harnessLearningFixture, 'v1');
  assert.equal(config.harnessSettingsFixture, undefined);
  for (const args of [
    [...base, '--harness-learning-fixture', 'arbitrary.py'],
    [...base, '--harness-learning-fixture', 'v2'],
    [...base, '--harness-learning-fixture', 'v1', '--harness-learning-fixture', 'v1'],
    [...base, '--harness-learning-fixture', 'v1', '--harness-settings-fixture', 'v1'],
    ['--repo', path.join(root, 'source'), '--python', path.join(root, 'python.exe'), '--harness-learning-fixture', 'v1'],
    [...base, '--executable', path.join(root, 'Renulus.exe'), '--harness-learning-fixture', 'v1'],
    [...base, '--harness-learning-fixture', 'v1', '--model', 'arbitrary-model'],
  ]) assert.throws(() => parseCli(args), { code: 'invalid_cli' });
  assert.equal(parseCli(base).harnessLearningFixture, undefined);
});

async function sourceFixture() {
  await mkdir(root, { recursive: true });
  const directory = await mkdtemp(path.join(root, 'l-'));
  const repo = path.join(directory, 'source'), helperAssets = path.join(directory, 'assets');
  await mkdir(path.join(repo, 'packaging/runtime'), { recursive: true });
  await mkdir(path.join(repo, 'packages/harness/src'), { recursive: true });
  await mkdir(helperAssets);
  // Metadata-only stand-ins at the launch boundary; no helper engine executes.
  const groups = {};
  for (const name of ['docling', 'embedding', 'ocr']) {
    const bytes = Buffer.from('synthetic-learning-' + name);
    await writeFile(path.join(helperAssets, name + '.bin'), bytes);
    groups[name] = { revision: 'synthetic', source_url: 'https://example.invalid/' + name,
      files: [{ path: name + '.bin', size: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex') }] };
  }
  const manifest = JSON.stringify({ version: 1, groups });
  await writeFile(path.join(helperAssets, 'manifest.json'), manifest);
  await writeFile(path.join(repo, 'packaging/runtime/helper-assets.json'), manifest);
  return { repo, helperAssets, python: path.join(directory, 'runtime/python.exe'),
    stateRoot: path.join(directory, 'control'), harnessLearningFixture: 'v1' };
}

test('public learning launch freezes exact startup metadata before profile provisioning and reuses its identity', async () => {
  const config = await sourceFixture(), documents = [];
  const stopped = new Error('Synthetic OS acquisition held; no app or issuer starts');
  const controller = new RenulusController(config, {
    preflight: async () => ({ executable: path.join(config.repo, 'electron.exe'), cwd: config.repo, args: ['.'], mainSha256: 'synthetic' }),
    launch: async ({ env }) => {
      const option = JSON.parse(env.RENULUS_BACKGROUND_HARNESS_LEARNING);
      assert.deepEqual(Object.keys(option).sort(), ['helperAssets', 'kind', 'startupDocument', 'startupSha256']);
      assert.equal(option.kind, 'harness-learning-synthetic-v1');
      assert.equal(option.helperAssets, config.helperAssets);
      assert.equal(env.RENULUS_BACKGROUND_HARNESS_SETTINGS, undefined);
      const raw = await readFile(option.startupDocument), document = JSON.parse(raw);
      assert.equal(createHash('sha256').update(raw).digest('hex'), option.startupSha256);
      assert.deepEqual(await readdir(env.RENULUS_PROFILE), [], 'The live root must remain empty until its real Python issuer');
      const directory = path.dirname(env.RENULUS_PROFILE);
      const identity = 'synthetic-learning-' + path.basename(directory);
      assert.deepEqual(document, { version: 1, process: { node_executable: process.execPath,
        host_entry: path.join(config.repo, 'packages/harness/src/main.mjs'), profile_root: env.RENULUS_PROFILE,
        profile_id: identity, store_id: identity + '-runtime', domain_store_id: identity + '-domain',
        domain_path: 'state/renulus.sqlite3', max_inflight: 1, max_domain_inflight: 1,
        max_frame_bytes: 65536, start_timeout: 45 }, artifact_root: path.join(directory, 'a'),
        candidate_root: path.join(directory, 'k'), attempt_timeout: 45, initialize_new: documents.length === 0 });
      assert.equal(option.startupDocument, path.join(directory, 'out', 'startup-' + (documents.length + 1) + '.json'));
      documents.push({ option, raw, document });
      throw stopped;
    },
  });
  try {
    await assert.rejects(controller.run('renulus_start'), error => error.message === stopped.message);
    await assert.rejects(controller.run('renulus_start'), error => error.message === stopped.message);
    assert.equal(documents.length, 2);
    assert.deepEqual(documents[0].document.process, documents[1].document.process);
    assert.deepEqual(await readFile(documents[0].option.startupDocument), documents[0].raw);
  } finally { await controller.shutdown(); }
});

test('owned learning launch and restart retain normal close without a Settings observer', async () => {
  const config = await sourceFixture(), launches = [];
  let closed = false, current, settingsAttachments = 0;
  const controller = new RenulusController(config, {
    preflight: async () => ({ executable: path.join(config.repo, 'electron.exe'), cwd: config.repo, args: ['.'], mainSha256: 'synthetic' }),
    launch: async ({ env }) => {
      closed = false;
      const option = JSON.parse(env.RENULUS_BACKGROUND_HARNESS_LEARNING);
      const document = JSON.parse(await readFile(option.startupDocument));
      assert.deepEqual(await readdir(env.RENULUS_PROFILE), []);
      launches.push(document);
      const page = new EventEmitter(), app = new EventEmitter();
      const child = { pid: 910001, exitCode: null, signalCode: null };
      current = { child, env };
      const origin = 'http://127.0.0.1:18777';
      page.url = () => origin + '/'; page.isClosed = () => closed;
      page.locator = () => ({ count: async () => 1, isVisible: async () => true,
        ariaSnapshot: async () => '- heading "Synthetic Learning launch boundary"', evaluateAll: async () => [] });
      page.evaluate = async () => { throw new Error('No renderer evaluation is part of this fixture trace'); };
      app.process = () => child; app.windows = () => [page];
      app.context = () => ({ setDefaultTimeout() {}, route: async () => {},
        newCDPSession: async () => { settingsAttachments++; throw new Error('The Settings observer must remain opt-in to Settings'); } });
      app.evaluate = async fn => fn.name === 'installObservation' ? undefined : {
        name: 'Renulus', pid: child.pid, ownerPid: String(process.pid), executable: path.join(config.repo, 'electron.exe'),
        background: true, attachedBackend: false, packaged: false, profile: env.RENULUS_PROFILE,
        userData: path.join(path.dirname(env.RENULUS_PROFILE), 'd'), seen: 1, violations: [],
        windows: [{ visible: false, focused: false, focusable: false, backgroundThrottling: false,
          sandbox: true, contextIsolation: true, nodeIntegration: false }],
        children: [{ pid: 910002, executable: config.python, profile: env.RENULUS_PROFILE, exited: false }],
      };
      app.close = async () => { closed = true; child.exitCode = 0; };
      return app;
    },
    inspect: async () => closed ? [] : [
      { pid: 910001, executable: path.join(config.repo, 'electron.exe'), parentPid: process.pid, created: 'synthetic-main' },
      { pid: 910002, executable: config.python, parentPid: current.child.pid, created: 'synthetic-backend' },
    ],
  });
  try {
    const started = await controller.run('renulus_start');
    assert.equal(started.hidden, true);
    assert.equal((await controller.run('renulus_snapshot')).settingsResponses, undefined);
    const restarted = await controller.run('renulus_restart');
    assert.equal(restarted.profile, started.profile);
    assert.equal(launches[0].initialize_new, true);
    assert.equal(launches[1].initialize_new, false);
    assert.deepEqual(launches[0].process, launches[1].process);
    const result = await controller.run('renulus_close');
    assert.equal(result.normal, true);
    const receipt = JSON.parse(await readFile(result.receipt));
    assert.deepEqual(receipt.closes.map(close => close.normal), [true, true]);
    assert.deepEqual(receipt.closes.map(close => close.forcedPids), [[], []]);
    assert.equal(receipt.startupDocuments.length, 2);
    assert.equal(receipt.settingsResponses, undefined);
    assert.equal(settingsAttachments, 0);
  } finally { await controller.shutdown(); }
});
