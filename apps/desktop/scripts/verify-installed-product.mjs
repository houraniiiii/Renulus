/** Bounded current-PC acceptance. Importing this file or --plan never launches anything. */
import { createHash, randomUUID } from 'node:crypto';
import { createReadStream } from 'node:fs';
import { lstat, mkdir, readFile, readdir, stat, writeFile } from 'node:fs/promises';
import { execFileSync, spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createNativeEvidence, assertSyntheticEvidenceDirectory, nativeEvidenceRoot, designCEvidenceRoot } from './native-evidence-directory.mjs';

const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const repository = path.resolve(desktop, '../..');
const prerequisiteCommits = ['793eddb4', 'a6b5d597', '16ad199d', 'c9d145af', 'eb821aa3', '8c6c4b18', '5e0c3837', '6145fc70', '728555e2', 'f4fc986f', 'f5d36ac9'];
const sha = value => createHash('sha256').update(value).digest('hex');
const check = (condition, message) => { if (!condition) throw new Error(message); };
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const samePath = (left, right) => typeof left === 'string' && typeof right === 'string'
  && path.resolve(left).toLowerCase() === path.resolve(right).toLowerCase();
const json = buffer => JSON.parse(buffer.toString('utf8').replace(/^\uFEFF/, ''));
const git = args => execFileSync('git', args, { cwd: repository, windowsHide: true, maxBuffer: 16 * 1024 * 1024 });

export { designCEvidenceRoot };
export const readerGates = Object.freeze(['reader-pdf', 'reader-docx', 'reader-csv', 'reader-xlsx',
  'reader-markdown', 'reader-html', 'reader-xml', 'reader-images']);
export const deferredGates = Object.freeze({
  'legacy-profile-upgrade': 'Requires an immutable preserved schema-1 synthetic profile; fresh-state startup is not upgrade proof.',
  'full-backup-restore': 'JSON/ZIP1/ZIP2 restore, originals and real derived rebuild require their separate connected journey.',
  'deletion-reconciliation': 'Project live deletion does not prove old-backup deletion reconciliation.',
  'normal-ingestion-close': 'No real active ingestion job is scheduled by this bounded core driver.',
  'native-backup-save-cancel': 'Hidden mode suppresses physical Save dialogs; no native dialog claim.',
});
export const coreGates = Object.freeze([
  'installed-identity', 'isolated-runtime', 'c-readiness', 'saved-conversations',
  'project-membership', 'saved-reviewed-test', 'whole-study', 'active-test-policy',
  'test-draft-reopen', 'whole-test', 'pdf-selection-reopen', 'temporary-retention', 'normal-reopen',
  'project-delete-preserves-chats', 'final-close',
]);
export const requiredGates = Object.freeze([...coreGates, ...readerGates, ...Object.keys(deferredGates)]);

export function installedAcceptancePlan() {
  return {
    scope: 'Hidden unsigned installed Design C on this Windows PC; signing and a separate PC/VM are optional future work.',
    prerequisiteCommits, requiredGates, coreGates, readerGates, deferredGates,
    requiredEnvironment: ['RENULUS_NATIVE_SLOT', 'RENULUS_EXPECT_SOURCE_REVISION', 'RENULUS_INSTALLED_PROOF=1',
      'RENULUS_PACKAGED_EXECUTABLE', 'RENULUS_DELIVERY_PROVENANCE', 'RENULUS_INSTALLER_EVIDENCE',
      'RENULUS_NATIVE_EVIDENCE_ROOT=' + designCEvidenceRoot],
    evidenceRoot: designCEvidenceRoot,
    resourceBound: 'One owned hidden app/backend at a time; two saved draft chats, one project, eleven deterministic synthetic originals covering eight reader categories, and one real two-question reviewed set; no providers or simulated producer results.',
    receipt: 'installed-product-evidence.json; absent reader/migration/native gates remain not-run and make the aggregate incomplete/exit 1.',
    parentChecks: ['Assign the exclusive native/helper slot and immutable final source first.',
      'Publish the exact Design C generated/native proof root in shared guards; never bypass those guards.',
      'Supply the matching package/install receipts. Preserve separate native/live/physical and legacy-profile acceptance.'],
  };
}

export function validateInstalledRequest(env, platform = process.platform) {
  check(platform === 'win32', 'Installed acceptance runs on the authorised Windows PC.');
  check(/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}$/.test(env.RENULUS_NATIVE_SLOT ?? ''), 'The parent must assign RENULUS_NATIVE_SLOT before any native/helper work.');
  check(/^[0-9a-f]{40}$/.test(env.RENULUS_EXPECT_SOURCE_REVISION ?? ''), 'An exact immutable parent freeze is required.');
  check(env.RENULUS_INSTALLED_PROOF === '1', 'Use the matching actual installation, with RENULUS_INSTALLED_PROOF=1.');
  for (const key of ['RENULUS_PACKAGED_EXECUTABLE', 'RENULUS_DELIVERY_PROVENANCE', 'RENULUS_INSTALLER_EVIDENCE']) {
    check(typeof env[key] === 'string' && path.isAbsolute(env[key]), 'An absolute ' + key + ' is required.');
  }
  for (const key of ['RENULUS_PROFILE', 'RENULUS_SOURCE_DESKTOP', 'RENULUS_BACKEND_URL', 'RENULUS_SESSION_TOKEN',
    'RENULUS_PYTHON', 'RENULUS_TEST_ATTACH', 'RENULUS_PDF_FIXTURE_ONLY', 'RENULUS_FIXTURE_PYTHON',
    'RENULUS_BACKGROUND_TEST', 'RENULUS_BACKGROUND_OWNER_PID']) {
    check(!env[key], 'Installed acceptance refuses profile/attached/runtime/fixture override ' + key + '.');
  }
  check(samePath(env.RENULUS_NATIVE_EVIDENCE_ROOT, designCEvidenceRoot),
    'Design C installed proof requires its exact synthetic delivery evidence root.');
  return { slot: env.RENULUS_NATIVE_SLOT, revision: env.RENULUS_EXPECT_SOURCE_REVISION,
    executable: path.resolve(env.RENULUS_PACKAGED_EXECUTABLE),
    deliveryFile: path.resolve(env.RENULUS_DELIVERY_PROVENANCE), installerFile: path.resolve(env.RENULUS_INSTALLER_EVIDENCE) };
}

export function inside(root, value) {
  const relative = path.relative(root, value);
  return !!relative && relative !== '..' && !relative.startsWith('..' + path.sep) && !path.isAbsolute(relative);
}

export async function ownedArtifact(value) {
  check(path.isAbsolute(value), 'Artifact paths must be absolute.');
  check([path.join(desktop, 'release'), 'C:/Renulus-native-delivery/desktop-20261005',
    'E:/Renulus-native-delivery/desktop-20261005', designCEvidenceRoot].some(root => inside(path.resolve(root), value)), 'Use the existing owned delivery/release tree.');
  if (inside(designCEvidenceRoot, value)) check(/^(?:matching-[0-9a-f]{8}|installed-[0-9a-f]{8}|proofs)$/.test(path.relative(designCEvidenceRoot, value).split(path.sep)[0]),
    'Design C artifacts must use matching/installed/proofs directories, never synthetic runtime profiles.');
  for (let cursor = path.resolve(value); ; cursor = path.dirname(cursor)) {
    try { check(!(await lstat(cursor)).isSymbolicLink(), 'Artifact paths may not traverse a junction/reparse point.'); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
    if (cursor === path.dirname(cursor)) break;
  }
}

async function hashFile(file, algorithm = 'sha256', prefix) {
  const digest = createHash(algorithm);
  if (prefix) digest.update(prefix);
  for await (const block of createReadStream(file)) digest.update(block);
  return digest.digest('hex');
}

export function validateInstallationReceipts(request, delivery, installation, actual) {
  check(delivery.source_revision === request.revision && installation.expectedSourceRevision === request.revision
    && installation.installedSourceRevision === request.revision, 'The manufacture and actual installation must name the exact freeze.');
  check(!delivery.error && !installation.error && installation.installExitCode === 0
    && ['unsigned-installer-extraction-only', 'unsigned-installer-execution'].includes(installation.kind), 'An actual successful installer receipt is required.');
  check(samePath(installation.installedExecutable, request.executable)
    && samePath(installation.target, path.dirname(request.executable)), 'The installation receipt does not own this executable.');
  const installer = delivery.installers?.[0];
  check(delivery.installers?.length === 1 && samePath(installer?.path, installation.installer), 'One exact manufactured installer must match the installation receipt.');
  for (const [observed, claims] of [[actual.executable, [delivery.executable_sha256, installation.installedExecutableSha256]],
    [actual.asar, [delivery.app_asar_sha256, installation.installedAsarSha256]],
    [actual.inventory, [delivery.packaged_backend_inventory_sha256]],
    [actual.installer, [installer?.sha256, installation.installerSha256]]]) {
    check(/^[0-9a-f]{64}$/.test(observed ?? '') && claims.every(claim => claim === observed), 'Actual source/artifact hashes differ from the completed package/install receipts.');
  }
}

const isolatedDirectoryKeys = ['USERPROFILE', 'HOME', 'LOCALAPPDATA', 'APPDATA', 'ALLUSERSPROFILE', 'PROGRAMDATA',
  'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'RENULUS_PROFILE', 'TEMP', 'TMP'];

export function validateIsolatedDirectories(env, evidence) {
  for (const name of isolatedDirectoryKeys) {
    check(typeof env[name] === 'string' && path.isAbsolute(env[name]) && inside(evidence, env[name]),
      'Child ' + name + ' must remain inside its fresh evidence directory.');
    assertSyntheticEvidenceDirectory(env[name]);
  }
}

export async function prepareIsolatedDirectories(env, evidence) {
  validateIsolatedDirectories(env, evidence);
  for (const directory of new Set(isolatedDirectoryKeys.map(name => env[name]))) {
    await mkdir(directory, { recursive: true });
    assertSyntheticEvidenceDirectory(directory);
  }
}

export function isolatedEnvironment(inherited, evidence, profile) {
  check(inside(designCEvidenceRoot, evidence), 'Design C state requires the exact synthetic delivery evidence root.');
  assertSyntheticEvidenceDirectory(evidence);
  check(inside(evidence, profile), 'The profile must be newly owned by this synthetic run.');
  check(path.resolve(profile).length <= 60, 'The installed helper profile must use at most 60 characters.');
  const env = {};
  for (const name of ['SystemRoot', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'ComSpec', 'PATHEXT']) {
    if (inherited[name]) env[name] = inherited[name];
  }
  const systemRoot = env.SystemRoot ?? env.SYSTEMROOT;
  check(systemRoot, 'Windows system root is required.');
  env.PATH = [path.join(systemRoot, 'System32'), path.join(systemRoot, 'System32', 'Wbem')].join(path.delimiter);
  env.USERPROFILE = path.join(evidence, 'h'); env.HOME = env.USERPROFILE;
  env.LOCALAPPDATA = path.join(evidence, 'local'); env.APPDATA = path.join(evidence, 'roaming');
  env.ALLUSERSPROFILE = path.join(env.LOCALAPPDATA, 'common'); env.PROGRAMDATA = env.ALLUSERSPROFILE;
  env.XDG_CACHE_HOME = path.join(env.LOCALAPPDATA, 'cache');
  env.XDG_CONFIG_HOME = env.APPDATA; env.XDG_DATA_HOME = env.LOCALAPPDATA;
  env.RENULUS_PROFILE = profile;
  env.RENULUS_BACKGROUND_TEST = '1'; env.RENULUS_BACKGROUND_OWNER_PID = String(process.pid);
  env.TEMP = path.join(evidence, 't'); env.TMP = env.TEMP;
  validateIsolatedDirectories(env, evidence);
  return env; // No inherited Electron-as-Node flag, developer path, token, provider key or runtime override.
}

export function validateCompleteReport(report) {
  check(report.kind === 'actual-installed-product-current-pc' && !report.error && !report.cleanupError,
    'A failed/fixture/partial receipt cannot establish installed acceptance.');
  check(/^[0-9a-f]{40}$/.test(report.sourceRevision ?? '') && requiredGates.every(name => report.gates?.[name]?.status === 'passed'
    && report.gates[name].proof && typeof report.gates[name].proof === 'object'
    && !Array.isArray(report.gates[name].proof) && Object.keys(report.gates[name].proof).length > 0),
  'Every required journey must have a complete passing receipt.');
  check(report.shutdowns?.length >= 3 && report.shutdowns.every(record => record.normalWindowClose
    && record.ownedBackendObserved && record.remaining.length === 0), 'Physical owned backend termination is required for every normal close.');
}

export function validateFrozenScript(name, expectedBytes, actualBytes) {
  // The repository checks PowerShell files out as CRLF; Git stores their LF source.
  const canonical = name.endsWith('.ps1') ? Buffer.from(actualBytes.toString('utf8').replaceAll('\r\n', '\n')) : actualBytes;
  const expected = sha(expectedBytes);
  check(sha(canonical) === expected, 'The acceptance script differs from the parent freeze: ' + name);
  return { frozenSha256: expected, executedSha256: sha(actualBytes) };
}

async function verifyArtifacts(request) {
  for (const commit of prerequisiteCommits) git(['merge-base', '--is-ancestor', commit, request.revision]);
  const scripts = ['native-journeys.mjs', 'verify-installed-product.mjs', 'native-replacement-evidence.mjs',
    'native-evidence-directory.mjs', 'wait-for-flow-window.mjs', 'synthetic-pdf.mjs', 'pdf-viewer-evidence.mjs',
    'native-product-backup.mjs', 'operate-owned-save-dialog.ps1', 'inspect-native-backup.py', 'design-c-reader-fixtures.py'];
  const driverHashes = {};
  for (const name of scripts) {
    const file = 'apps/desktop/scripts/' + name;
    driverHashes[name] = validateFrozenScript(name, git(['show', request.revision + ':' + file]),
      await readFile(path.join(repository, file)));
  }
  const requiredCells = git(['ls-tree', '-r', '--name-only', request.revision, '--', 'content/required-cells']).toString('utf8')
    .trim().split('\n').filter(name => name.endsWith('.json')).map(name => {
      const bytes = git(['show', request.revision + ':' + name]), manifest = json(bytes);
      return { path: name, sha256: sha(bytes), pack: manifest.pack, checkedOn: manifest.checked_on,
        adoptedBankMinimaMet: manifest.adopted_bank_minima_met, completeContentCoverage: manifest.complete_content_coverage };
    });
  check(requiredCells.length > 0, 'The final source must retain its content-owned required-cells evidence.');
  for (const file of [request.executable, request.deliveryFile, request.installerFile]) await ownedArtifact(file);
  const delivery = json(await readFile(request.deliveryFile)), installation = json(await readFile(request.installerFile));
  await ownedArtifact(installation.installer);
  const resources = path.join(path.dirname(request.executable), 'resources'), backend = path.join(resources, 'backend');
  const archive = path.join(resources, 'app.asar');
  const actual = { executable: await hashFile(request.executable), asar: await hashFile(archive),
    inventory: await hashFile(path.join(backend, 'inventory.json')), installer: await hashFile(installation.installer) };
  validateInstallationReceipts(request, delivery, installation, actual);
  const { extractFile } = await import('@electron/asar');
  const { validateReplacementSource } = await import('./native-replacement-evidence.mjs');
  const bundle = json(await readFile(path.join(backend, 'bundle.json')));
  const renderer = json(extractFile(archive, 'dist/renderer-provenance.json'));
  const native = json(extractFile(archive, 'dist-electron/native-provenance.json'));
  const electronVersion = json(git(['show', request.revision + ':apps/desktop/package.json'])).devDependencies.electron;
  validateReplacementSource(bundle, renderer, native, request.revision, electronVersion);
  check(native.main_bundle_sha256 === sha(extractFile(archive, 'dist-electron/main.cjs'))
    && native.preload_bundle_sha256 === sha(extractFile(archive, 'dist-electron/preload.cjs')), 'Installed native bundle bytes differ from frozen provenance.');
  for (const [file, field] of [['main.ts', 'main_source_sha256'], ['preload.ts', 'preload_source_sha256'], ['profile.ts', 'profile_source_sha256']]) {
    check(native[field] === sha(git(['show', request.revision + ':apps/desktop/electron/' + file])), 'Installed native source does not match the integrated freeze: ' + file);
  }
  const inventory = json(await readFile(path.join(backend, 'inventory.json'))), listed = new Map();
  for (const item of inventory) {
    check(typeof item.path === 'string' && inside(backend, path.resolve(backend, item.path)) && !listed.has(item.path), 'Installed backend inventory has an unsafe or duplicate path.');
    const file = path.resolve(backend, item.path); await ownedArtifact(file);
    check((await stat(file)).size === item.size && await hashFile(file) === item.sha256, 'Installed backend/helper bytes differ: ' + item.path);
    listed.set(item.path, item);
  }
  const roots = ['runtime/renulus', 'content/packs', 'content/LICENSE', 'LICENSE', 'licenses', 'upstream/hermes',
    'packaging/runtime', 'uv.lock', 'pyproject.toml', 'docs/SOURCES.md'];
  const excluded = /^(?:tests|tests-js|website|evals|[.]github|nix|docker|apps|ui-tui|web|scripts|docs)(?:\/|$)/;
  let frozenFiles = 0;
  for (const row of git(['ls-tree', '-r', '-z', request.revision, '--', ...roots]).toString('utf8').split('\0').filter(Boolean)) {
    const [header, name] = row.split('\t'), [mode, type, object] = header.split(' ');
    if (name.startsWith('upstream/hermes/') && excluded.test(name.slice('upstream/hermes/'.length))) continue;
    check(type === 'blob' && mode !== '120000' && listed.has(name), 'The installed backend omits a frozen source file: ' + name);
    const file = path.join(backend, name);
    check(await hashFile(file, 'sha1', 'blob ' + listed.get(name).size + '\0') === object, 'Installed source bytes differ from Git: ' + name);
    frozenFiles++;
  }
  return { resources, backend, archive, electronVersion, actual, frozenFiles, inventoryFiles: listed.size, driverHashes,
    sourceReview: { sourceRegisterSha256: listed.get('docs/SOURCES.md').sha256, requiredCells,
      scope: 'Frozen development evidence; neither complete coverage nor current-source clearance is inferred from a native pass.' },
    bundle, renderer, native, installation: { kind: installation.kind, installExitCode: installation.installExitCode,
      signature: installation.signature, installer: installation.installer }, receiptFiles: [request.deliveryFile, request.installerFile] };
}

async function api(page, route, body, expected = 200, method = body === undefined ? 'GET' : 'POST') {
  const response = await page.evaluate(async ({ route, body, method }) => {
    const response = await fetch('/api/v1' + route, { method, ...(body === undefined ? {} : {
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }) });
    return { status: response.status, body: response.status === 204 ? null : await response.json() };
  }, { route, body, method });
  check(response.status === expected, 'Actual backend ' + method + ' ' + route + ' returned ' + response.status + ': ' + (response.body?.error?.code ?? 'unexpected result'));
  return response.body;
}

async function actionResponse(page, route, action, expected = 200, method = 'POST') {
  const pending = page.waitForResponse(response => new URL(response.url()).pathname === '/api/v1' + route
    && response.request().method() === method, { timeout: 120_000 });
  const [response] = await Promise.all([pending, action()]);
  check(response.status() === expected, 'The actual UI action failed: ' + route + ' (' + response.status() + ').');
  return expected === 204 ? null : response.json();
}

async function poll(work, accepts, label, timeout = 180_000, interval = 500) {
  const deadline = Date.now() + timeout;
  let value;
  do { value = await work(); if (accepts(value)) return value; await sleep(interval); } while (Date.now() < deadline);
  throw new Error(label + ' did not reach its required state.');
}

async function navigate(page, hash) {
  check(/^#\/(?:projects|tests|chat|attempts)(?:\/[a-zA-Z0-9_-]+){0,2}$/.test(hash), 'Use a bounded canonical C route.');
  await page.evaluate(value => { window.location.hash = value; }, hash);
  await page.waitForFunction(value => window.location.hash === value && !!document.querySelector('.desktop-shell.design-c-shell'), hash);
}

export function validateHiddenWindows(windows) {
  check(windows.every(window => !window.visible && !window.focused), 'Installed proof must keep every owned window hidden and unfocused.');
}
async function hiddenWindowState(application) {
  const windows = await application.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()
    .filter(window => !window.isDestroyed()).map(window => ({ visible: window.isVisible(), focused: window.isFocused(), url: window.webContents.getURL() })));
  validateHiddenWindows(windows);
  return windows;
}
export async function waitForDesignCWindow(application, { startedAt = Date.now(), timeout = 360_000 } = {}) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const windows = await hiddenWindowState(application);
    for (const page of application.windows()) {
      if (page.isClosed()) continue;
      let url; try { url = new URL(page.url()); } catch { continue; }
      if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1' || !url.port || !windows.some(window => window.url === page.url())) continue;
      // DOM readiness works with hidden/collapsed navigation; no visible heading is required.
      if (await page.locator('.desktop-shell.design-c-shell').count() !== 1) continue;
      return { page, rendererReadySeconds: (Date.now() - startedAt) / 1000, hidden: true, landmark: '.desktop-shell.design-c-shell' };
    }
    await sleep(100);
  }
  throw new Error('The hidden owned loopback Design C renderer did not become ready.');
}

export function remainingOwnedIdentities(owners, observed) {
  // A reused PID is a different process. Unknown identity retains ownership and fails closed.
  return owners.filter(owner => observed.some(row => row.pid === owner.pid
    && (!row.executable || !row.created || samePath(row.executable, owner.executable) && row.created === owner.created)));
}

function processIdentities(pids, env) {
  check(pids.length && pids.every(pid => Number.isSafeInteger(pid) && pid > 0), 'Only observed owned process IDs may be queried.');
  const filter = pids.map(pid => 'ProcessId = ' + pid).join(' OR ');
  const script = "$ErrorActionPreference='Stop'; $rows=@(Get-CimInstance Win32_Process -Filter '" + filter
    + "' | ForEach-Object { [pscustomobject]@{ pid=[int]$_.ProcessId; executable=$_.ExecutablePath; created=$_.CreationDate.ToUniversalTime().ToString('o') } }); ConvertTo-Json -InputObject $rows -Compress";
  const output = execFileSync(path.join(env.SystemRoot ?? env.SYSTEMROOT, 'System32/WindowsPowerShell/v1.0/powershell.exe'),
    ['-NoProfile', '-Command', script], { env, windowsHide: true, encoding: 'utf8', timeout: 15_000 });
  const rows = json(Buffer.from(output));
  return Array.isArray(rows) ? rows : rows ? [rows] : [];
}

async function normalClose(current, report) {
  const started = Date.now();
  await hiddenWindowState(current.application);
  await current.application.evaluate(({ BrowserWindow }, url) => {
    const window = BrowserWindow.getAllWindows().find(item => item.webContents.getURL() === url);
    if (!window) throw new Error('The owning Design C window is missing.');
    window.close(); // Same close handler as the window's ordinary Close control; no taskkill/CDP forced app exit.
  }, current.page.url());
  const remaining = await poll(async () => {
    const rows = processIdentities(current.identities.map(item => item.pid), current.env);
    return remainingOwnedIdentities(current.identities, rows);
  }, rows => rows.length === 0, 'Normal owned-process shutdown', 30_000, 300);
  const receipt = { normalWindowClose: true, ownedBackendObserved: true, seconds: (Date.now() - started) / 1000,
    identities: current.identities, remaining };
  report.shutdowns.push(receipt);
  return receipt;
}

export function validateBundledInterpreter(interpreter, backend) {
  check(interpreter.version === '3.14.4' && interpreter.isolated === 1 && interpreter.no_user_site === 1
    && samePath(interpreter.prefix, interpreter.base_prefix) && inside(backend, interpreter.prefix)
    && interpreter.paths.length > 0 && interpreter.paths.every(value => inside(backend, value))
    && inside(backend, interpreter.pillow), 'The actual bundled interpreter and Pillow must be isolated inside the verified installation.');
}
function inspectBundledInterpreter(identity, env, evidence) {
  const python = path.join(identity.backend, 'python/python.exe');
  const interpreter = json(execFileSync(python, ['-I', '-B', '-X', 'utf8', '-c',
    'import sys,json,os,importlib.util;print(json.dumps(dict(version=sys.version.split()[0],prefix=sys.prefix,base_prefix=sys.base_prefix,isolated=sys.flags.isolated,no_user_site=sys.flags.no_user_site,paths=sys.path,pillow=importlib.util.find_spec("PIL").origin,directories={key:os.environ.get(key) for key in json.loads(sys.argv[1])})))',
    JSON.stringify(isolatedDirectoryKeys)],
  { env, windowsHide: true, timeout: 30_000 }));
  validateBundledInterpreter(interpreter, identity.backend);
  validateIsolatedDirectories(interpreter.directories, evidence);
  check(isolatedDirectoryKeys.every(name => samePath(interpreter.directories[name], env[name])), 'The Python child changed its isolated directories.');
  return interpreter;
}
async function launch(request, identity, evidence, profileName, report) {
  const profile = path.join(evidence, profileName), env = isolatedEnvironment(process.env, evidence, profile);
  await prepareIsolatedDirectories(env, evidence);
  const absentTools = ['python', 'python3', 'py', 'uv', 'node', 'npm'];
  for (const name of absentTools) check(spawnSync(path.join(env.SystemRoot ?? env.SYSTEMROOT, 'System32/where.exe'),
    [name], { env, windowsHide: true }).status === 1, 'A developer tool resolves on the app PATH: ' + name);
  const python = path.join(identity.backend, 'python/python.exe');
  const interpreter = inspectBundledInterpreter(identity, env, evidence);
  const { _electron: electron } = await import('@playwright/test');
  const startedAt = Date.now();
  const application = await electron.launch({ executablePath: request.executable, args: [], cwd: path.dirname(request.executable), env, timeout: 360_000 });
  // Retain ownership even if window/readiness validation subsequently fails.
  const current = { application, env, profile, identities: [], page: null };
  report.current = current;
  const { page, ...timing } = await waitForDesignCWindow(application, { startedAt, timeout: 360_000 }); current.page = page;
  page.setDefaultTimeout(30_000);
  const native = await application.evaluate(({ app, BrowserWindow }, { url, directoryKeys }) => {
    const window = BrowserWindow.getAllWindows().find(item => item.webContents.getURL() === url);
    const preferences = window.webContents.getLastWebPreferences();
    return { pid: process.pid, executable: process.execPath, packaged: app.isPackaged, electron: process.versions.electron,
      background: process.env.RENULUS_BACKGROUND_TEST, backgroundOwner: process.env.RENULUS_BACKGROUND_OWNER_PID,
      directories: Object.fromEntries(directoryKeys.map(name => [name, process.env[name]])),
      userData: app.getPath('userData'), persistent: window.webContents.session.isPersistent(), sandbox: preferences.sandbox,
      nodeIntegration: preferences.nodeIntegration, contextIsolation: preferences.contextIsolation,
      children: process._getActiveHandles().filter(item => item.constructor.name === 'ChildProcess').map(item => item.pid).filter(Boolean) };
  }, { url: page.url(), directoryKeys: isolatedDirectoryKeys });
  validateIsolatedDirectories(native.directories, evidence);
  check(isolatedDirectoryKeys.every(name => samePath(native.directories[name], env[name])), 'The Electron child changed its isolated directories.');
  check(native.packaged && samePath(native.executable, request.executable) && native.electron === identity.electronVersion
    && samePath(native.userData, path.join(profile, 'desktop')) && !native.persistent && native.sandbox
    && !native.nodeIntegration && native.contextIsolation && native.children.length === 1
    && native.background === '1' && native.backgroundOwner === String(process.pid), 'Installed runtime/profile/backend ownership differs.');
  current.identities = processIdentities([native.pid, ...native.children], env);
  check(current.identities.length === 2 && current.identities.every(item => item.created && item.executable)
    && current.identities.some(item => item.pid === native.pid && samePath(item.executable, request.executable))
    && current.identities.some(item => item.pid === native.children[0] && samePath(item.executable, python)), 'Physical main/backend identities could not be established.');
  const meta = await api(page, '/meta'), connections = await api(page, '/connections');
  check(meta.api_version === 1 && connections.selected_provider === null
    && connections.connections.every(item => item.status === 'disconnected'), 'Acceptance requires its own disconnected synthetic profile.');
  const runtime = await api(page, '/runtime/status');
  check(runtime.helpers?.embedding?.ready && runtime.helpers?.docling?.ready && runtime.helper_startup?.configured
    && runtime.helper_startup?.imports?.embedding?.ready && runtime.helper_startup?.imports?.docling?.ready
    && runtime.helper_startup.downloads === false, 'Actual bundled offline helpers are not ready.');
  await page.setViewportSize({ width: 1440, height: 900 });
  report.launches.push({ profile, timing, native, interpreter, absentTools, meta, runtime });
  return current;
}

async function assertNoSentinel(directory, sentinel) {
  let files = 0;
  const needles = [Buffer.from(sentinel, 'utf8'), Buffer.from(sentinel, 'utf16le')];
  const overlap = Math.max(...needles.map(needle => needle.length)) - 1;
  async function visit(root) {
    for (const entry of await readdir(root, { withFileTypes: true })) {
      const file = path.join(root, entry.name); check(!entry.isSymbolicLink(), 'Synthetic profile contains a reparse path.');
      if (entry.isDirectory()) await visit(file);
      else if (entry.isFile()) {
        let tail = Buffer.alloc(0);
        for await (const block of createReadStream(file)) {
          const joined = Buffer.concat([tail, block]); check(!needles.some(needle => joined.includes(needle)), 'Unsaved synthetic case persisted in owned state.');
          tail = joined.subarray(Math.max(0, joined.length - overlap));
        }
        files++;
      }
    }
  }
  await visit(directory);
  return { files, sentinelAbsent: true, encodings: ['utf8', 'utf16le'],
    scope: 'All closed owned profile files, including canonical/index/cache/Hermes/desktop/helper state; no directory exclusion.' };
}


/** These assertions inspect real producer responses in --run; unit fixtures prove only refusal logic. */
export function validateConversation(summary, kind, projectId) {
  check(summary?.kind === kind && summary.retention === 'saved' && summary.lifecycle === 'active'
    && summary.identity?.type === (kind === 'case' ? 'case' : 'learn_thread') && typeof summary.identity.id === 'string'
    && !summary.identity.id.startsWith('tmp_') && summary.project_id === projectId && Number.isInteger(summary.revision),
  'The canonical saved conversation did not retain its typed owner/project.');
}
export function validateSavedTest(published, setup) {
  check(published?.test_id && published.version_id && published.item_count === 2
    && setup.test?.id === published.test_id && setup.version?.id === published.version_id
    && setup.version.origin === 'reviewed_bank' && setup.version.review_quality === 'reviewed'
    && setup.version.status === 'ready' && setup.version.item_count === 2 && setup.can_start,
  'The real saved reviewed test/version is incomplete or differs from publication.');
}
export function validateActiveTest(attempt, versionId, expectedId = attempt?.id) {
  check(attempt?.id && attempt.id === expectedId && attempt.version_id === versionId && attempt.mode === 'test'
    && attempt.status === 'active' && attempt.item_count === 2 && attempt.origin === 'reviewed_bank'
    && attempt.review_quality === 'reviewed' && attempt.timing?.kind === 'untimed'
    && attempt.policy?.assistance_allowed === false && attempt.policy.active_test_id === attempt.id
    && Array.isArray(attempt.committed) && attempt.committed.length === 0 && attempt.result === null,
  'Active Test identity/policy changed or feedback was published before final submission.');
  function noFeedback(value) {
    if (!value || typeof value !== 'object') return;
    for (const [key, child] of Object.entries(value)) {
      check(!['correct_option_ids', 'correct', 'explanation', 'feedback'].includes(key), 'Active Test question exposes feedback.');
      noFeedback(child);
    }
  }
  noFeedback(attempt.current_item);
}
export function validateFinalAttempt(attempt, mode, versionId) {
  const result = attempt?.result;
  check(attempt?.id && attempt.mode === mode && attempt.version_id === versionId && attempt.item_count === 2
    && attempt.status === (mode === 'study' ? 'ended' : 'submitted') && result?.attempt_id === attempt.id
    && result.version_id === versionId && result.mode === mode && result.origin === 'reviewed_bank'
    && result.item_count === 2 && result.excluded === 0 && result.denominator === (mode === 'study' ? 1 : 2)
    && result.unanswered === (mode === 'study' ? 0 : 1) && result.not_submitted === (mode === 'study' ? 1 : 0)
    && result.items?.length === (mode === 'study' ? 1 : 2) && attempt.policy?.assistance_allowed === true
    && attempt.policy.active_test_id === null, 'Whole-attempt final result/pin/counts or released policy differ.');
  check(result.correct === result.items.filter(item => item.correct === true).length
    && result.items.every(item => item.commit_id && item.question?.item_id === item.item_id
      && Array.isArray(item.selected_option_ids) && item.feedback?.explanation), 'Final feedback is not pinned to actual commitments.');
}
export function safeFailure(error, temporaryPhase = false) {
  return { message: temporaryPhase ? 'Temporary retention check failed; volatile text and identity are withheld.' : error.message };
}

export function completeCoreReceipt(report) {
  for (const [name, reason] of Object.entries(deferredGates)) {
    check(!report.gates[name] || report.gates[name].status === 'not-run', 'The core verifier cannot attest an unexecuted migration/native gate.');
    report.gates[name] = { status: 'not-run', reason };
  }
  check(coreGates.every(name => report.gates[name]?.status === 'passed'), 'A core journey is incomplete.');
  report.coreCompleted = true;
  report.status = 'incomplete';
  report.readersCompleted = readerGates.every(name => report.gates[name]?.status === 'passed');
  for (const name of readerGates) report.gates[name] ??= { status: 'not-run', reason: 'Matching installed reader journey was not exercised.' };
  report.pendingGates = requiredGates.filter(name => report.gates[name]?.status !== 'passed');
  // A successful bounded core is never advertised as complete DC21 acceptance.
  return report;
}

const chatPath = chat => '/conversations/' + chat.kind + '/' + encodeURIComponent(chat.identity.id);
const chatHash = chat => '#/chat/' + chat.identity.type + '/' + chat.identity.id;
async function screenshot(current, evidence, name) {
  await hiddenWindowState(current.application);
  await current.page.screenshot({ path: path.join(evidence, name + '.png'), fullPage: true });
}
async function savedConversationJourney(page) {
  await navigate(page, '#/projects');
  const projectTitle = 'DC21 synthetic study ' + randomUUID().slice(0, 8);
  await page.getByLabel('New project name', { exact: true }).fill(projectTitle);
  const project = await actionResponse(page, '/study/projects', () => page.getByRole('button', { name: 'Create project', exact: true }).click(), 201);
  check(project.id && project.lifecycle === 'active', 'Project creation did not return its canonical owner.');
  const conversations = [];
  for (const kind of ['learning', 'case']) {
    await navigate(page, '#/projects/' + project.id);
    await page.getByRole('heading', { level: 1, name: projectTitle, exact: true }).waitFor();
    const chat = await actionResponse(page, '/conversations', () => page.getByRole('button', {
      name: kind === 'learning' ? 'New learning chat' : 'New case chat', exact: true }).click(), 201);
    validateConversation(chat, kind, project.id);
    const composer = page.getByLabel(kind === 'case' ? 'Your case question' : 'Message Renulus', { exact: true });
    const draft = 'Synthetic ' + (kind === 'case' ? 'dialysis case' : 'CKD learning') + ' draft; no patient information or generation.';
    await composer.fill(draft);
    await poll(() => api(page, chatPath(chat) + '/draft'), value => value.text === draft && value.revision > 0, 'Durable saved chat draft');
    await page.locator('.chat-tools summary').click();
    const title = 'DC21 ' + kind + ' ' + project.id;
    await page.getByLabel('Conversation title', { exact: true }).fill(title);
    const renamed = await actionResponse(page, chatPath(chat), () => page.getByRole('button', { name: 'Rename', exact: true }).click(), 200, 'PATCH');
    validateConversation(renamed, kind, project.id);
    check(renamed.title === title, 'Chat rename did not persist.');
    check((await api(page, chatPath(chat) + '/messages')).items.length === 0, 'Draft editing unexpectedly created a message.');
    check((await api(page, chatPath(chat) + '/runs')).items.length === 0, 'Draft editing unexpectedly started a provider run.');
    conversations.push({ ...renamed, expectedDraft: draft });
  }
  const linked = await api(page, '/study/projects/' + project.id);
  check(linked.chats.length === 2 && conversations.every(chat => linked.chats.some(row => row.identity.id === chat.identity.id
    && row.identity.type === chat.identity.type)), 'The project did not retain exactly its two typed chat memberships.');
  await navigate(page, chatHash(conversations[0]));
  await page.getByRole('heading', { level: 1, name: conversations[0].title, exact: true }).waitFor();
  await page.locator('.chat-tools summary').click();
  await actionResponse(page, chatPath(conversations[0]) + '/archive', () => page.getByRole('button', { name: 'Archive', exact: true }).click());
  check((await api(page, chatPath(conversations[0]))).lifecycle === 'archived', 'Archive was not persisted.');
  // The Manage details may retain its state; select the actual action rather than toggle blindly.
  const restore = page.getByRole('button', { name: 'Restore', exact: true });
  if (!await restore.isVisible()) await page.locator('.chat-tools summary').click();
  await actionResponse(page, chatPath(conversations[0]) + '/restore', () => restore.click());
  return { project: linked, conversations };
}
async function reopenSavedWork(page, work, projectId = work.project.id) {
  for (const saved of work.conversations) {
    const chat = await api(page, chatPath(saved)); validateConversation(chat, saved.kind, projectId);
    check(chat.title === saved.title && (await api(page, chatPath(saved) + '/draft')).text === saved.expectedDraft,
      'Reopen lost the original chat title or durable draft.');
    await navigate(page, chatHash(saved));
    await poll(() => page.getByLabel(saved.kind === 'case' ? 'Your case question' : 'Message Renulus', { exact: true }).inputValue(),
      text => text === saved.expectedDraft, 'Reopened composer draft');
    check((await api(page, chatPath(saved) + '/messages')).items.length === 0
      && (await api(page, chatPath(saved) + '/runs')).items.length === 0, 'Reopen duplicated or generated conversation content.');
  }
  return { chatIds: work.conversations.map(chat => chat.identity), draftsPreserved: true, projectId };
}
async function reviewedStudyJourney(page) {
  await navigate(page, '#/tests');
  await page.getByRole('button', { name: 'New reviewed test', exact: true }).click();
  const title = 'DC21 reviewed set ' + randomUUID().slice(0, 8);
  await page.getByLabel('Test title', { exact: true }).fill(title);
  await page.getByLabel('Questions', { exact: true }).fill('2');
  const published = await actionResponse(page, '/assessment/tests/reviewed', () => page.getByRole('button', { name: 'Save test', exact: true }).click());
  const setup = await api(page, '/assessment/tests/versions/' + published.version_id + '/setup');
  validateSavedTest(published, setup);
  await page.getByRole('button', { name: 'Continue to Study', exact: true }).click();
  const started = await actionResponse(page, '/assessment/test-attempts', () => page.getByRole('button', { name: 'Start Study', exact: true }).click(), 201);
  check(started.mode === 'study' && started.status === 'active' && started.version_id === published.version_id
    && started.item_count === 2 && started.committed.length === 0 && started.result === null && started.timing.kind === 'untimed', 'Study start did not pin the saved version.');
  await page.locator('.attempt-options input[type="radio"]').first().check();
  const commit = await actionResponse(page, '/assessment/test-attempts/' + started.id + '/submit-answer',
    () => page.getByRole('button', { name: 'Submit answer', exact: true }).click());
  check(commit.id === started.id && commit.committed.length === 1 && commit.committed[0].commit_id
    && commit.committed[0].feedback?.explanation && commit.result === null, 'Study feedback did not follow an actual explicit commitment.');
  await page.getByRole('button', { name: 'Finish study', exact: true }).click();
  const final = await actionResponse(page, '/assessment/test-attempts/' + started.id + '/submit',
    () => page.locator('.attempt-confirm').getByRole('button', { name: 'Finish study', exact: true }).click());
  validateFinalAttempt(final, 'study', published.version_id);
  await page.locator('.attempt-result-score').waitFor();
  return { published, setup, study: final };
}
async function startTestJourney(page, versionId) {
  await navigate(page, '#/tests/' + versionId);
  await page.getByLabel('Mode', { exact: true }).selectOption('test');
  await page.getByRole('button', { name: 'Continue to Test', exact: true }).click();
  const started = await actionResponse(page, '/assessment/test-attempts', () => page.getByRole('button', { name: 'Start Test', exact: true }).click(), 201);
  validateActiveTest(started, versionId);
  await page.locator('.attempt-options input[type="radio"]').first().check();
  const draft = await poll(() => api(page, '/assessment/test-attempts/' + started.id),
    value => value.answers[0].option_ids.length === 1 && value.draft_revision > started.draft_revision, 'Backend-durable Test choice');
  validateActiveTest(draft, versionId, started.id);
  check(await page.getByRole('button', { name: 'Hint', exact: true }).count() === 0, 'Active Test displayed Study help.');
  const refusal = await page.evaluate(async () => {
    const response = await fetch('/api/v1/conversations?limit=1');
    const body = await response.json(); return { status: response.status, code: body.error?.code };
  });
  check(refusal.status === 403 && refusal.code === 'assistance_restricted', 'Active Test did not refuse conversation help at the real API.');
  return { draft, refusal };
}
async function finishTestJourney(page, before) {
  const current = await api(page, '/assessment/test-attempts/' + before.id);
  validateActiveTest(current, before.version_id, before.id);
  check(JSON.stringify(current.answers) === JSON.stringify(before.answers) && current.draft_revision === before.draft_revision,
    'Closing/reopening changed the durable Test draft.');
  await navigate(page, '#/attempts/' + before.id);
  await page.locator('.attempt-options input[type="radio"]:checked').waitFor();
  await page.getByRole('button', { name: 'Review and submit test', exact: true }).click();
  const final = await actionResponse(page, '/assessment/test-attempts/' + before.id + '/submit',
    () => page.locator('.attempt-confirm').getByRole('button', { name: 'Submit test', exact: true }).click());
  validateFinalAttempt(final, 'test', before.version_id);
  check(JSON.stringify(final.result.items[0].selected_option_ids) === JSON.stringify(before.answers[0].option_ids), 'Final Test discarded its durable choice.');
  await page.locator('.attempt-result-score').waitFor();
  return final;
}
async function temporaryJourney(page) {
  await navigate(page, '#/chat');
  const chat = await actionResponse(page, '/conversations', () => page.getByRole('button', { name: 'Start temporary chat', exact: true }).click(), 201);
  check(chat.retention === 'temporary' && chat.project_id === null, 'The explicit temporary conversation was not volatile.');
  const sentinel = 'DC21-TEMP-' + randomUUID();
  await page.getByLabel('Message Renulus', { exact: true }).fill(sentinel);
  await poll(() => api(page, chatPath(chat) + '/draft'), value => value.text === sentinel, 'Volatile temporary draft');
  check(!page.url().includes(chat.identity.id), 'Temporary identity entered a navigation URL.');
  await navigate(page, '#/tests');
  const exported = JSON.stringify(await api(page, '/data/export'));
  check(!exported.includes(sentinel) && !exported.includes(chat.identity.id), 'Temporary draft or identity entered canonical export.');
  return { sentinel, chat }; // Volatile variables only; never included in the report or screenshots.
}
async function deleteProjectJourney(page, work) {
  await navigate(page, '#/projects/' + work.project.id);
  await page.getByText('Manage project', { exact: true }).click();
  await page.getByRole('button', { name: 'Delete project', exact: true }).click();
  const deleted = await actionResponse(page, '/study/projects/' + work.project.id,
    () => page.getByRole('dialog').getByRole('button', { name: 'Delete project', exact: true }).click(), 200, 'DELETE');
  check(deleted.id === work.project.id && deleted.deleted === true, 'Project deletion was not acknowledged.');
  const retained = await reopenSavedWork(page, work, null);
  return { deleted, ...retained };
}

const fixtureMedia = Object.freeze({ pdf: 'application/pdf', docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  csv: 'text/csv', xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', md: 'text/markdown',
  html: 'text/html', xml: 'application/xml', png: 'image/png', jpg: 'image/jpeg', tiff: 'image/tiff' });
const fixtureGate = extension => 'reader-' + ({ md: 'markdown', png: 'images', jpg: 'images', tiff: 'images' }[extension] ?? extension);

export function validateReaderManifest(manifest) {
  check(manifest.schema === 'design-c-reader-fixtures/1' && manifest.synthetic === true
    && typeof manifest.pillow_version === 'string' && manifest.files?.length === 11,
  'The frozen generator must supply eleven deterministic synthetic originals.');
  check(manifest.execution_marker === 'DC21_SYNTHETIC_SCRIPT_EXECUTED' && manifest.external_origin === 'https://design-c-reader.invalid',
    'Reader denial probes must use only their reserved inert marker and invalid origin.');
  const expected = new Set([...Object.keys(fixtureMedia).map(extension => 'synthetic-reading.' + extension), 'synthetic-denied-entity.xml']);
  for (const entry of manifest.files) {
    const extension = entry.filename?.split('.').at(-1);
    check(expected.delete(entry.filename) && entry.media_type === fixtureMedia[extension] && entry.gate === fixtureGate(extension)
      && /^[0-9a-f]{64}$/.test(entry.sha256 ?? '') && Number.isInteger(entry.bytes) && entry.bytes > 0 && entry.bytes < 64 * 1024
      && entry.expect && typeof entry.expect === 'object', 'A reader fixture has an unsafe name, type, size, hash or category.');
  }
  check(expected.size === 0, 'A required original format is missing.');
  return manifest;
}

async function generateReaderFixtures(identity, evidence) {
  const directory = path.join(evidence, 'reader-originals');
  check(inside(evidence, directory), 'Fixture output must belong to this fresh evidence directory.');
  assertSyntheticEvidenceDirectory(directory);
  const script = path.join(desktop, 'scripts/design-c-reader-fixtures.py');
  check(sha(await readFile(script)) === identity.driverHashes['design-c-reader-fixtures.py'].executedSha256,
    'The frozen fixture generator changed before execution.');
  const python = path.join(identity.backend, 'python/python.exe');
  const env = isolatedEnvironment(process.env, evidence, path.join(evidence, 'p'));
  await prepareIsolatedDirectories(env, evidence);
  // Inspect isolation and Pillow resolution before the generator can import it.
  const interpreter = inspectBundledInterpreter(identity, env, evidence);
  const generated = json(execFileSync(python, ['-I', '-B', '-X', 'utf8', script, '--output', directory],
    { env, windowsHide: true, timeout: 30_000, maxBuffer: 1024 * 1024 }));
  const manifest = validateReaderManifest(json(await readFile(path.join(directory, 'manifest.json'))));
  check(generated.schema === manifest.schema && generated.files === manifest.files.length && generated.pillow_version === manifest.pillow_version,
    'The bundled fixture generator returned a mismatched receipt.');
  for (const fixture of manifest.files) await checkedReaderOriginal(directory, fixture);
  return { directory, manifest, generator: { python, interpreter, scriptSha256: sha(await readFile(script)), ...generated } };
}

async function checkedReaderOriginal(directory, fixture) {
  const file = path.join(directory, fixture.filename);
  check(inside(directory, file) && path.basename(file) === fixture.filename, 'Original upload left its declared fixture directory.');
  assertSyntheticEvidenceDirectory(file);
  check((await lstat(file)).isFile(), 'Upload only a generated regular original.');
  const bytes = await readFile(file);
  check(bytes.length === fixture.bytes && sha(bytes) === fixture.sha256, 'Generated original bytes changed before upload.');
  return file;
}

export function validateReaderOriginal(fixture, original, mediaType) {
  check(original?.sha256 === fixture.sha256 && original.bytes === fixture.bytes && mediaType === fixture.media_type,
    'Reader/attachment original hash, byte count or format differs from its generated original.');
}

export function validateReaderDocument(fixture, document, attachment) {
  validateReaderOriginal(fixture, document.original, document.media_type);
  check(document.schema_version === 'reader/1' && document.reference?.target?.type === 'attachment'
    && document.reference.target.id === attachment.id && document.original.id === attachment.original.id
    && document.original.filename === fixture.filename && document.original.available === true
    && document.attachment_revision === attachment.revision && document.capabilities?.original === true
    && Number.isInteger(document.policy_revision) && document.policy_revision >= 1
    && Number.isInteger(document.context_epoch) && document.context_epoch >= 0,
  'The reader did not resolve the actual saved attachment owner and current authority.');
  if (fixture.expect.error) {
    check(document.preview_state === 'failed' && document.error?.code === fixture.expect.error
      && document.payload === null && document.capabilities.read === false && document.capabilities.passage === false,
    'The unsafe XML original was not explicitly refused.');
  } else {
    check(document.preview_state === 'ready' && document.error === null && document.capabilities.read === true
      && document.payload?.kind === fixture.expect.kind, 'The actual reader did not produce the required format.');
    if (fixture.expect.pages) check(document.payload.pages === fixture.expect.pages, 'Reader page/frame count differs from its original.');
    if (fixture.expect.kind === 'image') check(document.extraction_state === 'unavailable' && document.capabilities.passage === false
      && document.capabilities.ocr === false && document.capabilities.model_image === false, 'An image preview incorrectly claims extracted or interpreted content.');
    else check(document.capabilities.passage === true, 'Eligible text/table selection is unavailable.');
  }
}

export function validateReaderPassage(fixture, attachment, document, passage, locator, expectedText) {
  const reference = passage.reference;
  check(passage.title === document.title && passage.text === expectedText
    && reference?.target?.type === 'attachment' && reference.target.id === attachment.id
    && Object.entries(locator).every(([key, value]) => reference.locator?.[key] === value),
  'The actual selected passage changed text, source or canonical location.');
  check(fixture.expect.kind !== 'image' && !fixture.expect.error, 'A preview-only/refused original cannot establish passage acceptance.');
}

export function validateReaderRaster(bytes) {
  check(bytes.length > 24 && bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))
    && bytes.toString('ascii', 12, 16) === 'IHDR', 'The actual reader asset was not a raster PNG.');
  const width = bytes.readUInt32BE(16), height = bytes.readUInt32BE(20);
  check(width > 0 && height > 0 && width * height <= 12_000_000, 'The reader raster has invalid dimensions.');
  return { sha256: sha(bytes), bytes: bytes.length, width, height };
}

async function readerResponse(page, attachment, action) {
  const pending = page.waitForResponse(response => {
    if (new URL(response.url()).pathname !== '/api/v1/readers/resolve' || response.request().method() !== 'POST') return false;
    return response.request().postDataJSON()?.reference?.target?.id === attachment.id;
  }, { timeout: 120_000 });
  const [response] = await Promise.all([pending, action()]);
  check(response.status() === 200, 'Actual Workspace reader resolution failed.');
  return response.json();
}

async function uploadReaderOriginal(page, chat, fixtures, fixture) {
  const file = await checkedReaderOriginal(fixtures.directory, fixture);
  await navigate(page, chatHash(chat));
  const input = page.getByLabel('Attach files to chat', { exact: true });
  if (!await input.isVisible()) await page.getByRole('button', { name: 'Attach file', exact: true }).click();
  await input.setInputFiles(file); // Generated, hash-checked bytes; no native chooser.
  await page.getByLabel('Source owner or author', { exact: true }).fill('Renulus synthetic fixture author');
  await page.getByLabel('Display this file in Renulus', { exact: true }).check();
  await page.getByLabel('Keep a local original when this conversation is saved', { exact: true }).check();
  await page.getByLabel('Send selected content to my learning model', { exact: true }).check();
  await page.getByLabel('Permission or licence', { exact: true }).fill('CC0 synthetic original for local reader validation; no patient data.');
  const attachment = await actionResponse(page, '/attachments',
    () => page.getByRole('button', { name: 'Confirm attach', exact: true }).click(), 201);
  validateReaderOriginal(fixture, attachment.original, attachment.media_type);
  check(attachment.retention === 'saved' && attachment.filename === fixture.filename && attachment.reference?.target?.id === attachment.id
    && attachment.reference.target.type === 'attachment' && attachment.conversation?.type === chat.identity.type
    && attachment.conversation.id === chat.identity.id, 'Upload did not publish an original under the intended saved conversation.');
  return attachment;
}

async function prepareReaderDownload(page, reader, fixture) {
  const pending = page.waitForResponse(response => new URL(response.url()).pathname === '/api/v1/readers/original'
    && response.request().method() === 'POST');
  const [response] = await Promise.all([pending, reader.getByRole('button', { name: 'Prepare original download', exact: true }).click()]);
  const data = await response.body();
  check(response.status() === 200 && sha(data) === fixture.sha256 && data.length === fixture.bytes,
    'The real original-download action changed the uploaded bytes.');
  const headers = response.headers();
  check(headers['content-type'] === 'application/octet-stream' && headers['x-content-type-options'] === 'nosniff'
    && headers['content-security-policy'] === "default-src 'none'; sandbox" && headers['content-disposition']?.startsWith('attachment;'),
  'Original download did not retain its inert attachment response boundary.');
  const link = reader.getByRole('link', { name: 'Save original', exact: true });
  await link.waitFor();
  check(await link.getAttribute('download') === fixture.filename && (await link.getAttribute('href'))?.startsWith('blob:'),
    'The prepared original must remain a download, never a document frame.');
  return { sha256: sha(data), bytes: data.length, contentType: headers['content-type'], preparedOnly: true };
}

async function savedReaderPosition(page, chat, attachment, expected) {
  return poll(async () => {
    const preferences = await api(page, '/workspace/preferences');
    return preferences.tabs.find(tab => tab.context.type === chat.identity.type && tab.context.id === chat.identity.id
      && tab.retention === 'saved' && tab.content.target.type === 'attachment' && tab.content.target.id === attachment.id)?.position;
  }, value => !!value && Object.entries(expected).every(([key, item]) => value[key] === item), 'Canonical saved reader position', 30_000);
}

async function selectReaderPassage(page, reader, fixture, attachment, document, chat) {
  let locator, text;
  if (document.payload.kind === 'table') {
    const table = document.payload.table;
    const offset = table.rows.findIndex(row => row.some(cell => cell.display === fixture.expect.text));
    check(offset >= 0, 'The expected table selection is absent from the actual reader.');
    const column = table.rows[offset].findIndex(cell => cell.display === fixture.expect.text);
    text = table.rows[offset][column].display;
    locator = { kind: 'table', format: table.format, sheet_name: table.sheet_name,
      first_row: table.first_row + offset, last_row: table.first_row + offset, first_column: column + 1, last_column: column + 1 };
    await reader.getByRole('button', { name: text, exact: true }).click();
  } else {
    const block = document.payload.blocks.find(item => item.text.includes(fixture.expect.text));
    check(block, 'The expected passage is absent from the parsed original.');
    const start = Array.from(block.text.slice(0, block.text.indexOf(fixture.expect.text))).length;
    text = fixture.expect.text;
    locator = { kind: 'text', item_ref: block.item_ref, start, end: start + Array.from(text).length };
    // A real DOM range in the owned renderer triggers the actual selection handler.
    // No React state, API response or callback is injected.
    await reader.locator('[data-reader-item]').filter({ hasText: text }).first().evaluate((element, value) => {
      const node = element.firstChild;
      if (!node || node.nodeType !== Node.TEXT_NODE || !node.textContent?.includes(value)) throw new Error('Selectable text node missing.');
      const start = node.textContent.indexOf(value), range = document.createRange();
      range.setStart(node, start); range.setEnd(node, start + value.length);
      const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range);
      element.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
    }, text);
  }
  const position = await savedReaderPosition(page, chat, attachment, locator);
  const passage = await actionResponse(page, '/readers/passage',
    () => reader.getByRole('button', { name: 'Ask about selected passage', exact: true }).click());
  validateReaderPassage(fixture, attachment, document, passage, locator, text);
  const expectedDraft = chat.expectedDraft + '\n\n' + text;
  const composer = page.getByLabel('Message Renulus', { exact: true });
  await poll(() => composer.inputValue(), value => value === expectedDraft, 'Reader passage in preserved Chat draft', 30_000);
  const draft = await poll(() => api(page, chatPath(chat) + '/draft'), value => value.text === expectedDraft
    && value.content_refs?.some(ref => JSON.stringify(ref) === JSON.stringify(passage.reference)), 'Actual source-linked draft', 30_000);
  check((await api(page, chatPath(chat) + '/messages')).items.length === 0 && (await api(page, chatPath(chat) + '/runs')).items.length === 0,
    'Selecting a passage unexpectedly sent a message or invoked a provider.');
  // Keep the pre-existing core journey's draft; selection and its receipt were checked above.
  await composer.fill(chat.expectedDraft);
  await page.getByRole('button', { name: 'Remove source 1', exact: true }).click();
  await poll(() => api(page, chatPath(chat) + '/draft'), value => value.text === chat.expectedDraft && value.content_refs.length === 0,
    'Preserved original draft after selection check', 30_000);
  await page.evaluate(() => window.getSelection()?.removeAllRanges());
  return { text, reference: passage.reference, draftRevision: draft.revision, position, sent: false };
}

async function readerFixtureJourney(current, chat, fixtures, fixture, evidence) {
  const { page } = current;
  const attachment = await uploadReaderOriginal(page, chat, fixtures, fixture);
  const assets = [], externalRequests = [];
  const onResponse = response => {
    if (new URL(response.url()).pathname !== '/api/v1/readers/asset' || response.request().method() !== 'POST') return;
    const body = response.request().postDataJSON();
    if (body?.reference?.target?.id !== attachment.id) return;
    assets.push((async () => {
      check(response.status() === 200 && response.headers()['content-type'] === 'image/png'
        && body.original_sha256 === fixture.sha256, 'Actual reader asset failed or lost its original pin.');
      return { assetId: body.asset_id, ...validateReaderRaster(await response.body()) };
    })().catch(error => ({ error: error.message })));
  };
  const deny = route => { externalRequests.push(route.request().url()); return route.abort('blockedbyclient'); };
  await page.context().route(fixtures.manifest.external_origin + '/**', deny);
  page.on('response', onResponse);
  try {
    let document = await readerResponse(page, attachment, () => page.locator('.chat-attached-file')
      .filter({ hasText: fixture.filename }).getByRole('button', { name: 'Open file', exact: true }).click());
    validateReaderDocument(fixture, document, attachment);
    const reader = page.getByRole('region', { name: 'Document reader', exact: true });
    await reader.getByRole('heading', { name: attachment.title, exact: true }).waitFor();
    const positions = [];
    async function raster(assetId) {
      const rows = await poll(() => Promise.all(assets), values => values.some(row => row.assetId === assetId) || values.some(row => row.error), 'Actual reader raster', 30_000);
      check(!rows.some(row => row.error), rows.find(row => row.error)?.error ?? 'Reader raster failed.');
      await poll(() => reader.getByAltText('Source page', { exact: true }).evaluateAll(images => images.every(image => image.complete && image.naturalWidth > 0) && images.length > 0), Boolean, 'Decoded reader image', 30_000);
      const result = rows.find(row => row.assetId === assetId);
      if (fixture.expect.width) check(result.width === fixture.expect.width && result.height === fixture.expect.height, 'Decoded image size differs from the original.');
      return result;
    }
    let firstRaster;
    if (document.payload?.asset_id) firstRaster = await raster(document.payload.asset_id);
    if (fixture.expect.pages === 2) {
      const kind = fixture.expect.kind === 'pdf' ? 'pdf' : 'image';
      positions.push(await savedReaderPosition(page, chat, attachment, kind === 'pdf' ? { kind, physical_page: 1 } : { kind, frame: 1 }));
      document = await readerResponse(page, attachment, () => reader.getByRole('button', { name: 'Next', exact: true }).click());
      validateReaderDocument(fixture, document, attachment);
      check(document.payload.page === 2, 'Next did not open the second physical page/frame.');
      const nextRaster = await raster(document.payload.asset_id);
      check(firstRaster.sha256 !== nextRaster.sha256, 'Changing page/frame returned the previous raster.');
      positions.push(await savedReaderPosition(page, chat, attachment, kind === 'pdf' ? { kind, physical_page: 2 } : { kind, frame: 2 }));
      check(await reader.getByLabel(kind === 'pdf' ? 'Physical page' : 'Image frame', { exact: true }).inputValue() === '2', 'Reader position control is stale.');
    }
    if (fixture.gate === 'reader-csv') {
      check(document.payload.table.total_rows === fixture.expect.rows && document.payload.table.first_row === 1, 'CSV dimensions changed.');
      document = await readerResponse(page, attachment, () => reader.getByRole('button', { name: 'Next rows', exact: true }).click());
      validateReaderDocument(fixture, document, attachment);
      check(document.payload.table.first_row === 101 && document.payload.table.rows.length === 6, 'CSV row window did not advance exactly.');
    }
    if (fixture.gate === 'reader-xlsx') {
      const table = document.payload.table;
      check(JSON.stringify(table.sheets) === JSON.stringify(fixture.expect.sheets) && table.sheet_name === 'CKD'
        && table.rows[1][1].display === '24' && table.rows[1][1].formula === '=A2*2' && table.rows[1][1].cached === true,
      'The actual XLSX reader lost sheet names or its cached formula result.');
      await reader.getByRole('button', { name: '24', exact: true }).waitFor();
      document = await readerResponse(page, attachment, () => reader.getByLabel('Sheet', { exact: true }).selectOption('Dialysis'));
      validateReaderDocument(fixture, document, attachment);
      check(document.payload.table.sheet_name === 'Dialysis' && document.payload.table.first_row === 1
        && document.payload.table.rows[1][1].cached === false && document.payload.table.rows[1][1].display === 'Cached value unavailable',
      'Sheet change or missing cached formula semantics failed.');
      await reader.getByRole('button', { name: 'Cached value unavailable', exact: true }).waitFor();
    }
    if (fixture.expect.table_cell) {
      const table = document.payload.blocks.find(block => block.kind === 'table');
      check(table?.grid?.rows.some(row => row.includes(fixture.expect.table_cell)), 'Document table structure was lost.');
      await reader.getByRole('table', { name: 'Source document table', exact: true }).getByRole('cell', { name: fixture.expect.table_cell, exact: true }).waitFor();
    }
    if (fixture.expect.embedded_image) {
      const image = document.payload.blocks.find(block => block.kind === 'image');
      check(image?.asset_id, 'DOCX embedded image missing.'); await raster(image.asset_id);
    }
    let selection;
    if (fixture.expect.text) selection = await selectReaderPassage(page, reader, fixture, attachment, document, chat);
    if (fixture.expect.error) await reader.getByText(/XML must be complete and contain no DTD or entity declarations/).waitFor();
    if (fixture.expect.kind === 'image') {
      check(await reader.getByRole('button', { name: /Discuss this passage|Ask about selected passage/ }).count() === 0,
        'Preview-only image exposed an extracted passage action.');
    }
    const original = await prepareReaderDownload(page, reader, fixture);
    let inert;
    if (fixture.expect.inert) {
      inert = await reader.evaluate((element, marker) => ({ executed: window[marker] !== undefined,
        activeNodes: element.querySelectorAll('script,iframe,object,embed,form,link,style,svg,math,[onload],[onerror]').length,
        externalAttributes: [...element.querySelectorAll('[src],[href],[srcset],[action],[data]')].filter(node =>
          [...node.attributes].some(attribute => attribute.value.includes('design-c-reader.invalid'))).length,
        text: element.querySelector('.reader-content')?.textContent ?? '' }), fixtures.manifest.execution_marker);
      check(!inert.executed && inert.activeNodes === 0 && inert.externalAttributes === 0 && externalRequests.length === 0,
        'Reader markup executed or attempted an external resource; intercepted refusal does not count as inert parsing.');
      if (fixture.gate === 'reader-html') check(!inert.text.includes(fixtures.manifest.execution_marker)
        && !inert.text.includes('HIDDEN_REMOTE_FALLBACK') && !inert.text.includes('HIDDEN_FORM'), 'HTML active subtree content was not omitted.');
      delete inert.text;
      inert.externalRequests = externalRequests.length;
      inert.xmlEntityDenied = fixture.expect.error === 'reader_xml_invalid';
    }
    await screenshot(current, evidence, 'reader-' + fixture.filename.replaceAll('.', '-'));
    return { filename: fixture.filename, mediaType: fixture.media_type, attachmentId: attachment.id, attachment,
      original, previewState: document.preview_state, positions, selection, assets: await Promise.all(assets), inert,
      scope: 'Actual saved attachment, Workspace reader, guarded selection/draft and prepared original. No native Save dialog, model, OCR or ingestion claim.' };
  } finally {
    page.off('response', onResponse);
    await page.context().unroute(fixtures.manifest.external_origin + '/**', deny);
  }
}

async function readerJourneys(current, chat, fixtures, evidence, report, pass) {
  report.readerFixtures = { ...fixtures.generator, manifest: fixtures.manifest };
  report.readerJourneys = [];
  for (const gate of readerGates) {
    const completed = [];
    try {
      for (const fixture of fixtures.manifest.files.filter(item => item.gate === gate)) {
        const receipt = await readerFixtureJourney(current, chat, fixtures, fixture, evidence);
        completed.push(receipt); report.readerJourneys.push({ gate, ...receipt });
      }
      check(completed.length > 0, 'An empty reader category cannot pass.');
      pass(gate, { originals: completed });
    } catch (error) {
      report.gates[gate] = { status: 'failed', error: safeFailure(error), completedOriginals: completed };
      throw error;
    }
  }
}

export function validateReopenedPdf(fixture, checkpoint, document, position, raster) {
  validateReaderDocument(fixture, document, checkpoint.attachment);
  const selected = checkpoint.selection, locator = selected?.reference?.locator;
  check(locator?.kind === 'text' && locator.item_ref === 'reader-v1:pdf:2'
    && selected.reference.target.type === 'attachment' && selected.reference.target.id === checkpoint.attachment.id
    && document.payload.page === 2 && Number.isInteger(locator.start) && Number.isInteger(locator.end)
    && locator.start >= 0 && locator.end > locator.start,
  'The reopened PDF did not retain its selected page-2 text source.');
  check(Object.entries(locator).every(([key, value]) => position?.[key] === value),
    'The saved PDF selection offsets were overwritten on reopen.');
  const block = document.payload.blocks.find(item => item.item_ref === locator.item_ref);
  check(block && Array.from(block.text).slice(locator.start, locator.end).join('') === selected.text,
    'The reopened PDF locator no longer selects the original text.');
  const previous = checkpoint.assets.find(item => item.assetId === 'pdf:2');
  check(previous && raster.sha256 === previous.sha256 && raster.width === previous.width && raster.height === previous.height,
    'The reopened PDF raster differs from the original page-2 render.');
}

async function reopenSelectedPdfJourney(current, chat, fixtures, report, evidence) {
  const { page } = current;
  const fixture = fixtures.manifest.files.find(item => item.gate === 'reader-pdf');
  const checkpoint = report.readerJourneys.find(item => item.gate === 'reader-pdf');
  check(checkpoint?.selection && fixture, 'A real prior PDF selection receipt is required for reopen.');
  const attachment = checkpoint.attachment;
  // Closing the pane unmounts any warm reader without deleting its saved tab/locator.
  const closeWorkspace = page.getByRole('button', { name: 'Close workspace', exact: true });
  if (await closeWorkspace.isVisible()) await closeWorkspace.click();
  const pendingAsset = page.waitForResponse(response => {
    if (new URL(response.url()).pathname !== '/api/v1/readers/asset' || response.request().method() !== 'POST') return false;
    const body = response.request().postDataJSON();
    return body?.reference?.target?.id === attachment.id && body.asset_id === 'pdf:2';
  }, { timeout: 30_000 });
  const [document, asset] = await Promise.all([readerResponse(page, attachment, async () => {
    await navigate(page, chatHash(chat));
    if (!await page.getByLabel('Attach files to chat', { exact: true }).isVisible())
      await page.getByRole('button', { name: 'Attach file', exact: true }).click();
    // Opening the existing attachment preserves its stored locator. No preferences are injected.
    await page.locator('.chat-attached-file').filter({ hasText: fixture.filename })
      .getByRole('button', { name: 'Open file', exact: true }).click();
  }), pendingAsset]);
  check(asset.status() === 200 && asset.headers()['content-type'] === 'image/png'
    && asset.request().postDataJSON().original_sha256 === fixture.sha256, 'Reopened PDF asset lost its immutable original pin.');
  const raster = validateReaderRaster(await asset.body());
  const tab = page.locator('[role="tab"][id="dc-tab-' + encodeURIComponent('attachment:' + attachment.id) + '"]');
  // Identity chooses the tab. The current authorized title supplies its visible/close labels;
  // no generic Attachment label or duplicate-title ordering is used as identity.
  await poll(() => tab.textContent(), title => title === attachment.title, 'Authorized restored PDF tab title', 30_000);
  check(await tab.getAttribute('aria-selected') === 'true', 'Reopened PDF tab is not selected.');
  await page.getByRole('button', { name: 'Close ' + attachment.title + ' tab', exact: true }).waitFor();
  const reader = page.getByRole('region', { name: 'Document reader', exact: true });
  await reader.getByRole('heading', { name: attachment.title, exact: true }).waitFor();
  check(await reader.getByLabel('Physical page', { exact: true }).inputValue() === '2', 'The reopened Reader control returned to page 1.');
  await poll(() => reader.getByAltText('Source page', { exact: true }).evaluate(image => image.complete && image.naturalWidth > 0),
    Boolean, 'Decoded reopened PDF page', 30_000);
  const position = await savedReaderPosition(page, chat, attachment, checkpoint.selection.reference.locator);
  validateReopenedPdf(fixture, checkpoint, document, position, raster);
  const passage = await selectReaderPassage(page, reader, fixture, attachment, document, chat);
  check(JSON.stringify(passage.reference) === JSON.stringify(checkpoint.selection.reference)
    && passage.text === checkpoint.selection.text, 'The actual reopened passage changed its selected original text.');
  await screenshot(current, evidence, 'pdf-page2-selection-reopened');
  return { attachmentId: attachment.id, title: await tab.textContent(), position, original: document.original,
    page: document.payload.page, raster, passage, normalShutdownsBeforeCheck: report.shutdowns.length };
}

export async function runInstalledProduct() {
  const request = validateInstalledRequest(process.env);
  // Published parent helper must accept exactly this root before any state is created.
  nativeEvidenceRoot(designCEvidenceRoot);
  const evidence = await createNativeEvidence('c');
  check(inside(designCEvidenceRoot, evidence), 'Generated proof left the Design C scratch root.');
  const report = { kind: 'actual-installed-product-current-pc', checkedAt: new Date().toISOString(),
    slot: request.slot, sourceRevision: request.revision, executable: request.executable, evidence,
    acceptanceScope: installedAcceptancePlan().scope, gates: {}, shutdowns: [], launches: [],
    limits: ['Hidden synthetic disconnected profiles only. No owner profile, providers, fabricated generation or native dialogs.',
      'Real reviewed content and real SQLite/API producers; unit checks never establish installed acceptance.',
      'Migration/recovery and physical/native gates remain explicit not-run; the bounded core/reader driver cannot close DC21.'] };
  const pass = (name, proof) => { check([...coreGates, ...readerGates].includes(name), 'Only an executed core/reader gate can be recorded here.');
    report.gates[name] = { status: 'passed', proof }; console.log(JSON.stringify({ gate: name, status: 'passed' })); };
  let current;
  let temporaryPhase = false;
  try {
    const identity = await verifyArtifacts(request); report.identity = identity;
    pass('installed-identity', { hashes: identity.actual, frozenFiles: identity.frozenFiles, inventoryFiles: identity.inventoryFiles });
    const fixtures = await generateReaderFixtures(identity, evidence);
    current = await launch(request, identity, evidence, 'p', report);
    pass('isolated-runtime', report.launches[0]); pass('c-readiness', report.launches[0].timing);
    const work = await savedConversationJourney(current.page);
    pass('saved-conversations', { conversations: work.conversations, draftOnly: true });
    pass('project-membership', { project: work.project, owner: 'study_project_chats' });
    await readerJourneys(current, work.conversations[0], fixtures, evidence, report, pass);
    const reviewed = await reviewedStudyJourney(current.page);
    pass('saved-reviewed-test', { published: reviewed.published, setup: reviewed.setup });
    pass('whole-study', { attempt: reviewed.study });
    const test = await startTestJourney(current.page, reviewed.published.version_id);
    pass('active-test-policy', { id: test.draft.id, policy: test.draft.policy, refusal: test.refusal });
    await screenshot(current, evidence, 'test-durable-draft');
    await normalClose(current, report); current = undefined; delete report.current;
    current = await launch(request, identity, evidence, 'p', report);
    const final = await finishTestJourney(current.page, test.draft);
    pass('test-draft-reopen', { id: test.draft.id, draftRevision: test.draft.draft_revision, answers: test.draft.answers });
    pass('whole-test', { attempt: final });
    await reopenSavedWork(current.page, work);
    pass('pdf-selection-reopen', await reopenSelectedPdfJourney(current, work.conversations[0], fixtures, report, evidence));
    check(JSON.stringify((await api(current.page, '/assessment/test-attempts/' + reviewed.study.id)).result) === JSON.stringify(reviewed.study.result),
      'Reopen rewrote the immutable Study result.');
    const collection = await api(current.page, '/assessment/tests?limit=100');
    check(collection.items.filter(item => item.id === reviewed.published.test_id).length === 1, 'Reopen lost or duplicated the saved set.');
    await screenshot(current, evidence, 'saved-chat-reopen');
    temporaryPhase = true;
    const temporary = await temporaryJourney(current.page);
    await normalClose(current, report); current = undefined; delete report.current;
    const scan = await assertNoSentinel(path.join(evidence, 'p'), temporary.sentinel);
    const idScan = await assertNoSentinel(path.join(evidence, 'p'), temporary.chat.identity.id);
    current = await launch(request, identity, evidence, 'p', report);
    const absent = await current.page.evaluate(async route => (await fetch('/api/v1' + route)).status, chatPath(temporary.chat));
    check(absent === 404, 'Restart restored an ordinary temporary conversation.');
    pass('temporary-retention', { ...scan, temporaryIdAbsent: idScan.sentinelAbsent, restartStatus: absent });
    temporaryPhase = false;
    pass('normal-reopen', await reopenSavedWork(current.page, work));
    pass('project-delete-preserves-chats', await deleteProjectJourney(current.page, work));
    await screenshot(current, evidence, 'project-deletion-retained-chat');
    pass('final-close', await normalClose(current, report)); current = undefined; delete report.current;
    completeCoreReceipt(report); process.exitCode = 1;
  } catch (error) {
    report.status = 'failed'; report.error = safeFailure(error, temporaryPhase); process.exitCode = 1;
  } finally {
    const owned = current ?? report.current;
    if (owned) {
      try {
        let timer;
        try { await Promise.race([owned.application.close(), new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('Owned app cleanup exceeded 30 seconds; inspect its exact identities.')), 30_000); })]); }
        finally { clearTimeout(timer); }
        report.failureCleanup = { attempted: true, identities: owned.identities };
      } catch (error) { report.cleanupError = error.message; process.exitCode = 1; }
    }
    delete report.current;
    for (const name of requiredGates) report.gates[name] ??= { status: 'not-run', reason: deferredGates[name] ?? 'Execution stopped before this core gate.' };
    report.finishedAt = new Date().toISOString();
    await writeFile(path.join(evidence, 'installed-product-evidence.json'), JSON.stringify(report, null, 2), { flag: 'wx' });
  }
  console.log(JSON.stringify({ evidence, status: report.status, coreCompleted: report.coreCompleted ?? false,
    pendingGates: report.pendingGates, error: report.error?.message, cleanupError: report.cleanupError }));
  return report;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.length === 3 && process.argv[2] === '--plan') console.log(JSON.stringify(installedAcceptancePlan(), null, 2));
  else if (process.argv.length === 3 && process.argv[2] === '--run') await runInstalledProduct();
  else throw new Error('Use --plan (read-only) or --run after the parent supplies the matching package and exact freeze/slot.');
}
