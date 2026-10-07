// Only the pinned library's matcher/copier runs, against tiny synthetic files.
// Set RENULUS_PACKAGING_POLICY_NODE_MODULES to an existing public Node tree.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';

const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const modules = path.resolve(process.env.RENULUS_PACKAGING_POLICY_NODE_MODULES || path.join(desktop, 'node_modules'));
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const pin = readJson(path.join(desktop, 'package.json')).devDependencies['electron-builder'];
for (const name of ['electron-builder', 'app-builder-lib', 'builder-util']) {
  assert.equal(readJson(path.join(modules, name, 'package.json')).version, pin, name + ' must match the desktop pin');
}
const { getFileMatchers, copyFiles } = await import(pathToFileURL(path.join(modules, 'app-builder-lib/dist/fileMatcher.js')).href);
const require = createRequire(import.meta.url);
const configFile = path.join(desktop, 'electron-builder.config.cjs');
const configKey = require.resolve(configFile);
const configEnvironment = ['RENULUS_BACKEND_BUNDLE', 'RENULUS_RENDERER_BUNDLE', 'RENULUS_NATIVE_BUNDLE', 'RENULUS_DELIVERY_OUTPUT', 'RENULUS_DELIVERY_REVISION', 'RENULUS_DELIVERY_ROOT'];
function loadConfig(bundle) {
  const previous = configEnvironment.map(name => [name, process.env[name]]);
  try {
    for (const name of configEnvironment) delete process.env[name];
    process.env.RENULUS_BACKEND_BUNDLE = bundle;
    delete require.cache[configKey];
    return require(configKey);
  } finally {
    delete require.cache[configKey];
    for (const [name, value] of previous) {
      if (value === undefined) delete process.env[name];
      else process.env[name] = value;
    }
  }
}

const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const record = (file, bytes) => ({ path: file, size: bytes.length, sha256: digest(bytes) });
const sorted = records => records.sort((a, b) => a.path.localeCompare(b.path));
function inventory(root, relative = '') {
  return sorted(fs.readdirSync(path.join(root, relative), { withFileTypes: true }).flatMap(entry => {
    const file = path.posix.join(relative, entry.name);
    assert(!entry.isSymbolicLink(), 'the fixture must not traverse links');
    return entry.isDirectory() ? inventory(root, file) : [record(file, fs.readFileSync(path.join(root, file)))];
  }));
}

test('backend extraResources preserves inventoried .gitkeep with builder ' + pin, async t => {
  const testResults = path.join(desktop, 'test-results');
  fs.mkdirSync(testResults, { recursive: true });
  const root = fs.mkdtempSync(path.join(testResults, 'backend-extra-resources-policy-'));
  t.after(() => {
    assert.equal(path.dirname(path.resolve(root)), path.resolve(testResults));
    assert(!fs.lstatSync(root).isSymbolicLink());
    fs.rmSync(root, { recursive: true, force: true });
  });
  const bundle = path.join(root, 'bundle');
  const placeholders = ['dependencies/rapidocr/models/.gitkeep', 'upstream/hermes/contributors/emails/.gitkeep'];
  const files = new Map([
    ['bundle.json', Buffer.from(JSON.stringify({ version: 1, format: 'embedded-cpython-windows-v1', python: { executable: 'python/python.exe' } }))],
    ['python/python.exe', Buffer.from('Synthetic text fixture; never executed.')],
    ['LICENSE', Buffer.from('Synthetic public licence fixture.')],
    ['runtime/renulus/fixture.py', Buffer.from('# Synthetic runtime text; never executed.')],
    ['helper-assets/.synthetic-helper', Buffer.from('Synthetic dotfile bytes.')],
    [placeholders[0], Buffer.alloc(0)],
    [placeholders[1], Buffer.from('Synthetic public placeholder; no correspondence.'.padEnd(70, ' '))],
  ]);
  const records = sorted([...files].map(([file, bytes]) => record(file, bytes)));
  files.set('inventory.json', Buffer.from(JSON.stringify(records)));
  for (const [file, bytes] of files) {
    const target = path.join(bundle, file);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, bytes);
  }
  const expected = sorted([...files].map(([file, bytes]) => record(file, bytes)));
  // A non-inventoried placeholder must not gain a direct-copy exception.
  const unlisted = path.join(bundle, 'unlisted/.gitkeep');
  fs.mkdirSync(path.dirname(unlisted));
  fs.writeFileSync(unlisted, 'Synthetic unlisted placeholder.');
  const matcherOptions = { defaultSrc: desktop, globalOutDir: path.join(root, 'output'), customBuildOptions: {}, macroExpander: value => value };
  const matchers = (config, destination) => getFileMatchers(config, 'extraResources', destination, matcherOptions);

  await t.test('directory copy reproduces exactly the two missing files even with an explicit glob', async () => {
    const destination = path.join(root, 'before');
    const legacy = matchers({ extraResources: [{ from: bundle, to: 'backend' }] }, destination);
    await copyFiles(legacy, null, false);
    assert.deepEqual(inventory(path.join(destination, 'backend')), expected.filter(entry => !placeholders.includes(entry.path)));
    const globbed = matchers({ extraResources: [{ from: bundle, to: 'backend', filter: ['**/*', '**/.gitkeep'] }] }, path.join(root, 'globbed'));
    for (const file of placeholders) {
      const source = path.join(bundle, file);
      assert.equal(globbed[0].createFilter()(source, fs.statSync(source)), true, 'the matcher accepts the placeholder');
    }
    await copyFiles(globbed, null, false);
    assert.deepEqual(inventory(path.join(root, 'globbed/backend')), expected.filter(entry => !placeholders.includes(entry.path)));
  });

  await t.test('actual config copies the complete tiny payload with exact names, sizes and SHA256', async () => {
    const config = loadConfig(bundle);
    const destination = path.join(root, 'after');
    // Exercise only backend resources; licence-directory copying is out of scope.
    const backendMatchers = matchers(config, destination).filter(matcher => matcher.from === bundle || matcher.from.startsWith(bundle + path.sep));
    await copyFiles(backendMatchers, null, false);
    assert.deepEqual(inventory(path.join(destination, 'backend')), expected);
    assert.equal(fs.existsSync(path.join(destination, 'backend/unlisted/.gitkeep')), false);
    assert.equal(fs.readFileSync(unlisted, 'utf8'), 'Synthetic unlisted placeholder.');
    assert.equal(fs.readFileSync(path.join(destination, 'backend', placeholders[1])).length, 70);
    t.diagnostic(files.size + ' inventoried fixture/manifest files, ' + [...files.values()].reduce((bytes, file) => bytes + file.length, 0) + ' bytes: full output equality; both placeholders retained');
  });

  await t.test('inventory exceptions refuse paths outside the backend root', () => {
    try {
      for (const file of ['../outside/.gitkeep', 'nested/../../outside/.gitkeep', 'C:/outside/.gitkeep', '..' + String.fromCharCode(92) + 'outside/.gitkeep']) {
        fs.writeFileSync(path.join(bundle, 'inventory.json'), JSON.stringify([...records, { path: file }]));
        assert.throws(() => loadConfig(bundle), /placeholder inventory paths must be relative and confined/, file);
      }
    } finally {
      fs.writeFileSync(path.join(bundle, 'inventory.json'), files.get('inventory.json'));
    }
  });
});
