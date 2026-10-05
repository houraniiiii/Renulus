/** Bounded current-PC acceptance. Importing this file or --plan never launches anything. */
import { createHash, randomUUID } from 'node:crypto';
import { createReadStream } from 'node:fs';
import { lstat, mkdir, readFile, readdir, stat, writeFile } from 'node:fs/promises';
import { execFileSync, spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createNativeEvidence, assertSyntheticEvidenceDirectory, localEvidenceRoot } from './native-evidence-directory.mjs';
import { waitForFlowWindow } from './wait-for-flow-window.mjs';
import { syntheticPdf } from './synthetic-pdf.mjs';
import { capturePdfFrames, classifyPdfFrames } from './pdf-viewer-evidence.mjs';
import { proveNativeProductBackup } from './native-product-backup.mjs';

const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const repository = path.resolve(desktop, '../..');
const prerequisiteCommits = ['793eddb4', 'a6b5d597', '16ad199d', 'c9d145af', 'eb821aa3', '8c6c4b18', '5e0c3837'];
const sha = value => createHash('sha256').update(value).digest('hex');
const check = (condition, message) => { if (!condition) throw new Error(message); };
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const samePath = (left, right) => typeof left === 'string' && typeof right === 'string'
  && path.resolve(left).toLowerCase() === path.resolve(right).toLowerCase();
const json = buffer => JSON.parse(buffer.toString('utf8').replace(/^\uFEFF/, ''));
const git = args => execFileSync('git', args, { cwd: repository, windowsHide: true, maxBuffer: 16 * 1024 * 1024 });

export const requiredGates = Object.freeze([
  'installed-identity', 'isolated-runtime', 'programme-selectors', 'reviewed-quiz',
  'native-backup-save-cancel', 'library-text', 'library-pdf', 'library-image',
  'library-office-docx', 'library-office-pptx', 'library-office-xlsx',
  'temporary-retention', 'normal-ingestion-close', 'normal-reopen',
  'full-backup-restore', 'deletion-reconciliation', 'final-close',
]);

export function installedAcceptancePlan() {
  return {
    scope: 'Unsigned installed Windows build on this PC; signing and a separate PC/VM are optional future work.',
    prerequisiteCommits, requiredGates,
    requiredEnvironment: ['RENULUS_NATIVE_SLOT', 'RENULUS_EXPECT_SOURCE_REVISION', 'RENULUS_INSTALLED_PROOF=1',
      'RENULUS_PACKAGED_EXECUTABLE', 'RENULUS_DELIVERY_PROVENANCE', 'RENULUS_INSTALLER_EVIDENCE'],
    evidenceRoot: 'Default: this desktop test-results (also compatible with the existing native backup inspector).',
    resourceBound: 'One app/backend at a time; six small originals, at most four extra PDF queue jobs; no models/providers/compaction simulated.',
    receipt: 'installed-product-evidence.json; every gate and physical close must pass, or exit 1.',
    parentChecks: ['Assign the exclusive native/helper slot and immutable final source first.',
      'Run normal-profile/provider acceptance separately with the parent-owned profile and deliberately selected account.',
      'Review captured PDF physical page and original/Office UI screenshots.'],
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
    'RENULUS_PYTHON', 'RENULUS_TEST_ATTACH', 'RENULUS_PDF_FIXTURE_ONLY', 'RENULUS_FIXTURE_PYTHON']) {
    check(!env[key], 'Installed acceptance refuses profile/attached/runtime/fixture override ' + key + '.');
  }
  check(!env.RENULUS_NATIVE_EVIDENCE_ROOT || samePath(env.RENULUS_NATIVE_EVIDENCE_ROOT, localEvidenceRoot),
    'This reused backup-inspector recipe needs the desktop test-results root; clear RENULUS_NATIVE_EVIDENCE_ROOT for this run. C proof confinement remains available to the other native scripts.');
  return { slot: env.RENULUS_NATIVE_SLOT, revision: env.RENULUS_EXPECT_SOURCE_REVISION,
    executable: path.resolve(env.RENULUS_PACKAGED_EXECUTABLE),
    deliveryFile: path.resolve(env.RENULUS_DELIVERY_PROVENANCE), installerFile: path.resolve(env.RENULUS_INSTALLER_EVIDENCE) };
}

export function inside(root, value) {
  const relative = path.relative(root, value);
  return !!relative && relative !== '..' && !relative.startsWith('..' + path.sep) && !path.isAbsolute(relative);
}

async function ownedArtifact(value) {
  check(path.isAbsolute(value), 'Artifact paths must be absolute.');
  check([path.join(desktop, 'release'), 'C:/Renulus-native-delivery/desktop-20261005',
    'E:/Renulus-native-delivery/desktop-20261005'].some(root => inside(path.resolve(root), value)), 'Use the existing owned delivery/release tree.');
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

export function isolatedEnvironment(inherited, evidence, profile) {
  assertSyntheticEvidenceDirectory(evidence);
  check(inside(evidence, profile), 'The profile must be newly owned by this synthetic run.');
  const env = {};
  for (const name of ['SystemRoot', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'ComSpec', 'PATHEXT', 'USERPROFILE', 'LOCALAPPDATA', 'APPDATA']) {
    if (inherited[name]) env[name] = inherited[name];
  }
  const systemRoot = env.SystemRoot ?? env.SYSTEMROOT;
  check(systemRoot, 'Windows system root is required.');
  env.PATH = [path.join(systemRoot, 'System32'), path.join(systemRoot, 'System32', 'Wbem')].join(path.delimiter);
  env.RENULUS_PROFILE = profile;
  env.TEMP = path.join(evidence, 'temporary'); env.TMP = env.TEMP;
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
    'native-product-backup.mjs', 'operate-owned-save-dialog.ps1', 'inspect-native-backup.py'];
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
  throw new Error(label + ' did not reach its required state; last state: ' + JSON.stringify(value));
}

async function navigate(page, name) {
  await page.getByRole('navigation', { name: 'Main navigation', exact: true }).getByRole('link', { name, exact: true }).click();
  await page.waitForFunction(name => document.title === 'Renulus · ' + name, name);
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
  await current.application.evaluate(({ BrowserWindow }, url) => {
    const window = BrowserWindow.getAllWindows().find(item => item.webContents.getURL() === url);
    if (!window) throw new Error('The owning Flow window is missing.');
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

async function launch(request, identity, evidence, profileName, report) {
  const profile = path.join(evidence, profileName), env = isolatedEnvironment(process.env, evidence, profile);
  const absentTools = ['python', 'python3', 'py', 'uv', 'node', 'npm'];
  for (const name of absentTools) check(spawnSync(path.join(env.SystemRoot ?? env.SYSTEMROOT, 'System32/where.exe'),
    [name], { env, windowsHide: true }).status === 1, 'A developer tool resolves on the app PATH: ' + name);
  const python = path.join(identity.backend, 'python/python.exe');
  const interpreter = json(execFileSync(python, ['-I', '-B', '-X', 'utf8', '-c',
    'import sys,json;print(json.dumps(dict(version=sys.version.split()[0],prefix=sys.prefix,base_prefix=sys.base_prefix,isolated=sys.flags.isolated,no_user_site=sys.flags.no_user_site,paths=sys.path)))'],
  { env, windowsHide: true, timeout: 30_000 }));
  check(interpreter.version === '3.14.4' && interpreter.isolated === 1 && interpreter.no_user_site === 1
    && samePath(interpreter.prefix, interpreter.base_prefix) && interpreter.paths.every(value => inside(identity.backend, value)), 'The actual bundled interpreter is not isolated.');
  const { _electron: electron } = await import('@playwright/test');
  const startedAt = Date.now();
  const application = await electron.launch({ executablePath: request.executable, args: [], cwd: path.dirname(request.executable), env, timeout: 360_000 });
  // Retain ownership even if window/readiness validation subsequently fails.
  const current = { application, env, profile, identities: [], page: null };
  report.current = current;
  const { page, ...timing } = await waitForFlowWindow(application, { startedAt, timeout: 360_000 }); current.page = page;
  page.setDefaultTimeout(30_000);
  const native = await application.evaluate(({ app, BrowserWindow }, url) => {
    const window = BrowserWindow.getAllWindows().find(item => item.webContents.getURL() === url);
    const preferences = window.webContents.getLastWebPreferences();
    return { pid: process.pid, executable: process.execPath, packaged: app.isPackaged, electron: process.versions.electron,
      userData: app.getPath('userData'), persistent: window.webContents.session.isPersistent(), sandbox: preferences.sandbox,
      nodeIntegration: preferences.nodeIntegration, contextIsolation: preferences.contextIsolation,
      children: process._getActiveHandles().filter(item => item.constructor.name === 'ChildProcess').map(item => item.pid).filter(Boolean) };
  }, page.url());
  check(native.packaged && samePath(native.executable, request.executable) && native.electron === identity.electronVersion
    && samePath(native.userData, path.join(profile, 'desktop')) && !native.persistent && native.sandbox
    && !native.nodeIntegration && native.contextIsolation && native.children.length === 1, 'Installed runtime/profile/backend ownership differs.');
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
  await page.setViewportSize({ width: 1440, height: 960 });
  report.launches.push({ profile, timing, native, interpreter, absentTools, meta, runtime });
  return current;
}

export function validateProgrammeHandoff(home, catalog, selectedTrack) {
  const track = home.tracks?.find(item => item.id === 'esen_eph');
  check(home.goals?.track === 'eseneph' && home.selection?.track === 'esen_eph' && home.selection.status === 'ready'
    && track?.available && track.status === 'partial' && track.version && track.checked_on
    && home.selection.mapping_version === track.version && home.selection.topic_ids.length > 0,
  'The saved Today programme must use the active dated content mapping.');
  check(selectedTrack === 'esen_eph' && catalog.track === 'esen_eph' && catalog.complete_exam_available === false
    && catalog.tracks?.some(item => item.id === 'esen_eph' && item.available && item.exam_simulation_available === false),
  'Today Open Test must retain ESENeph and its actual reviewed catalogue.');
  return { track: selectedTrack, mappingVersion: track.version, checkedOn: track.checked_on,
    selectedTopics: home.selection.topic_ids, availableFamilies: catalog.available_families, examSimulation: false };
}

async function reviewedJourneys(page, evidence) {
  const tracks = await api(page, '/content/tracks');
  check(tracks.some(track => track.id === 'esen_eph' && track.available && track.status === 'partial'
    && track.exam_simulation_available === false), 'The integrated dated partial ESENeph programme is missing.');
  const sessions = [];
  for (const [track, pattern] of [['general_nephrology', /chronic kidney/i], ['general_nephrology', /dialysis/i], ['esen_eph', /transplant/i]]) {
    await navigate(page, 'Test');
    await page.getByLabel('Track', { exact: true }).selectOption(track);
    const catalog = await api(page, '/assessment/catalog?track=' + track);
    const topic = catalog.domains.find(row => pattern.test(row.label) && row.available_families > 0);
    check(topic && !catalog.complete_exam_available, 'No reviewed topic is available for the bounded cross-domain quiz.');
    // Wait for the actual catalog refresh before selecting its topic.
    await poll(() => page.getByLabel('Topic', { exact: true }).locator('option').evaluateAll(rows => rows.map(row => row.value)),
      rows => rows.includes(topic.id), 'Track topic selector', 30_000);
    await page.getByLabel('Topic', { exact: true }).selectOption(topic.id);
    await page.getByLabel('Questions', { exact: true }).fill('1');
    if (track === 'esen_eph') {
      await page.locator('[aria-label="Selected track coverage"]').getByText(/Exam simulation is unavailable/).waitFor();
      await page.getByText('View indicative domain coverage', { exact: true }).click();
      await page.getByRole('table', { name: 'Mapped reviewed bank', exact: true }).waitFor();
      await page.screenshot({ path: path.join(evidence, 'esen-eph-selectors.png'), fullPage: true });
    }
    const session = await actionResponse(page, '/assessment/start', () => page.getByRole('button', { name: 'Start reviewed quiz', exact: true }).click());
    check(session.item_count === 1 && session.selector.track === track && session.selector.topic_ids.includes(topic.id)
      && session.current_item?.topic_id === topic.id, 'The real quiz did not retain the selected programme/topic.');
    await page.locator('.assessment-question input[type="radio"]').first().check();
    const answer = await actionResponse(page, '/assessment/sessions/' + session.id + '/answer',
      () => page.getByRole('button', { name: 'Commit answer', exact: true }).click());
    check(answer.session.answered_count === 1 && answer.feedback.attempt_id && answer.feedback.score_bucket === 'fresh'
      && !answer.feedback.assisted && !answer.feedback.repeat && answer.feedback.sources.length > 0
      && typeof answer.feedback.correct === 'boolean' && answer.feedback.explanation, 'Committed reviewed feedback is incomplete.');
    await page.getByRole('heading', { name: 'Why this answer', exact: true }).waitFor();
    await page.getByRole('heading', { name: 'Sources for this feedback', exact: true }).waitFor();
    await page.screenshot({ path: path.join(evidence, 'quiz-feedback-' + sessions.length + '.png'), fullPage: true });
    const ended = await actionResponse(page, '/assessment/sessions/' + session.id + '/end',
      () => page.getByRole('button', { name: 'Finish quiz', exact: true }).click());
    check(ended.status === 'ended' && ended.answered_count === 1, 'The reviewed quiz was not completed.');
    const review = await actionResponse(page, '/assessment/sessions/' + session.id + '/review',
      () => page.getByRole('button', { name: 'Review committed answers', exact: true }).click(), 200, 'GET');
    check(review.feedback.length === 1 && review.feedback[0].attempt_id === answer.feedback.attempt_id, 'Persisted feedback differs from the committed answer.');
    sessions.push({ id: session.id, topic: topic.id, track, feedback: answer.feedback });
    await page.getByRole('button', { name: 'Back to quizzes', exact: true }).click();
  }
  const scores = await api(page, '/assessment/aggregates'), home = await api(page, '/study/home');
  const correct = sessions.filter(row => row.feedback.correct).length;
  check(scores.reviewed.fresh.answered === 3 && scores.reviewed.fresh.correct === correct
    && scores.reviewed.assisted.answered === 0 && scores.reviewed.repeat.answered === 0 && scores.generated.answered === 0
    && home.progress.groups.fresh.answered === 3 && home.progress.groups.fresh.correct === correct, 'Reviewed progress/Home does not reflect actual committed answers.');
  await navigate(page, 'Today');
  await page.getByText(correct + ' correct from 3 fresh unassisted reviewed answers across all tracks.', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Study preferences', exact: true }).click();
  await page.getByLabel('Track', { exact: true }).selectOption('eseneph');
  const goals = await actionResponse(page, '/study/goals', () => page.getByRole('button', { name: 'Save preferences', exact: true }).click(), 200, 'PUT');
  check(goals.track === 'eseneph', 'The real study programme preference was not saved.');
  const programmeHome = await api(page, '/study/home');
  const coverage = page.locator('[aria-label="Study track coverage"]');
  await coverage.getByText('Partial mapping', { exact: true }).waitFor();
  await coverage.getByText('Exam simulation is unavailable. The partial mapping does not establish complete exam coverage or mastery.', { exact: true }).waitFor();
  const checkedOn = programmeHome.tracks.find(item => item.id === 'esen_eph')?.checked_on;
  check(await coverage.locator('time').getAttribute('datetime') === checkedOn, 'Today lost the content-owned mapping date.');
  await coverage.getByText('Mapped domains and gaps', { exact: true }).click();
  await page.screenshot({ path: path.join(evidence, 'reviewed-progress-home.png'), fullPage: true });
  const handoffCatalog = await actionResponse(page, '/assessment/catalog',
    () => page.getByRole('button', { name: 'Open Test', exact: true }).click(), 200, 'GET');
  const handoff = validateProgrammeHandoff(programmeHome, handoffCatalog, await page.getByLabel('Track', { exact: true }).inputValue());
  await page.screenshot({ path: path.join(evidence, 'today-test-programme-handoff.png'), fullPage: true });
  return { tracks, sessions, scores, home, goals, programmeHome, handoff };
}

// Adapt the existing test_office_conversion.make_office fixtures; use only bundled packages.
export const fixturePython = [
  'import sys, pathlib, struct, zlib', 'from docx import Document', 'from pptx import Presentation',
  'from pptx.util import Inches', 'from openpyxl import Workbook', 'root=pathlib.Path(sys.argv[1])',
  'd=Document(); d.add_heading("Synthetic glomerular study",0); d.add_paragraph("Synthetic glomerular proteinuria observation.")',
  't=d.add_table(rows=2,cols=2); t.cell(0,0).text="Topic"; t.cell(0,1).text="Observation"; t.cell(1,0).text="Glomerular"; t.cell(1,1).text="Synthetic proteinuria"',
  'd.save(root/"synthetic.docx")', 'p=Presentation()',
  'for topic in ("dialysis","transplant"):',
  ' s=p.slides.add_slide(p.slide_layouts[5]); s.shapes.title.text="Synthetic "+topic+" study"',
  ' s.shapes.add_textbox(Inches(1),Inches(1),Inches(6),Inches(1)).text="Synthetic "+topic+" access observation."',
  'p.save(root/"synthetic.pptx")', 'w=Workbook(); w.remove(w.active)',
  'for topic in ("CKD","Electrolytes"):',
  ' s=w.create_sheet(topic); s.append(["Topic","Observation"]); s.append([topic,"Synthetic "+topic+" study observation."])',
  'w.save(root/"synthetic.xlsx")',
  'def chunk(kind,data): return struct.pack(">I",len(data))+kind+data+struct.pack(">I",zlib.crc32(kind+data)&0xffffffff)',
  'width,height=320,240; pixels=b"".join(b"\\0"+bytes([223,239,234])*width for _ in range(height))',
  '(root/"synthetic.png").write_bytes(b"\\x89PNG\\r\\n\\x1a\\n"+chunk(b"IHDR",struct.pack(">IIBBBBB",width,height,8,2,0,0,0))+chunk(b"IDAT",zlib.compress(pixels))+chunk(b"IEND",b""))',
].join('\n');

/** Enrich the existing two-page viewer fixture so chunking yields page-specific passages. */
export function ingestionPdf() {
  const objects = [...syntheticPdf().toString('ascii').matchAll(/[0-9]+ 0 obj\n([\s\S]*?)\nendobj/g)].map(match => match[1]);
  check(objects.length === 7, 'The existing two-page synthetic PDF structure changed.');
  for (const [index, pageName] of [[3, 'one'], [5, 'two']]) {
    const existing = objects[index].match(/stream\n([\s\S]*?)endstream/)[1];
    const lines = Array.from({ length: 60 }, (_, row) => 'BT /F1 5 Tf 18 ' + (375 - row * 5)
      + ' Td (Synthetic PDF page ' + pageName + ' dialysis acceptance observation row ' + row + ' for original source learning.) Tj ET');
    const stream = existing + lines.join('\n') + '\n';
    objects[index] = '<< /Length ' + Buffer.byteLength(stream) + ' >>\nstream\n' + stream + 'endstream';
  }
  let body = '%PDF-1.4\n'; const offsets = [0];
  for (let index = 0; index < objects.length; index++) {
    offsets.push(Buffer.byteLength(body)); body += (index + 1) + ' 0 obj\n' + objects[index] + '\nendobj\n';
  }
  const xref = Buffer.byteLength(body);
  body += 'xref\n0 8\n0000000000 65535 f \n' + offsets.slice(1).map(offset => String(offset).padStart(10, '0') + ' 00000 n \n').join('');
  return Buffer.from(body + 'trailer\n<< /Size 8 /Root 1 0 R >>\nstartxref\n' + xref + '\n%%EOF\n');
}

async function fixtures(identity, current, evidence) {
  const directory = path.join(evidence, 'fixtures'); await mkdir(directory);
  await writeFile(path.join(directory, 'synthetic.pdf'), ingestionPdf(), { flag: 'wx' });
  execFileSync(path.join(identity.backend, 'python/python.exe'), ['-I', '-B', '-c', fixturePython, directory],
    { env: current.env, windowsHide: true, timeout: 30_000 });
  const rows = [{ kind: 'text', title: 'Synthetic CKD acceptance note', query: 'Synthetic CKD acceptance note',
    text: 'Synthetic CKD acceptance note. Deliberate learning material; no patient or clinical claims.' }];
  for (const [kind, query] of [['pdf', 'Synthetic PDF page two dialysis acceptance'], ['image', null], ['office-docx', 'Synthetic glomerular'],
    ['office-pptx', 'Synthetic dialysis access observation'], ['office-xlsx', 'Synthetic CKD study observation']]) {
    const extension = kind === 'image' ? 'png' : kind.replace('office-', '');
    const file = path.join(directory, 'synthetic.' + extension);
    rows.push({ kind, title: 'Synthetic acceptance ' + extension, query, file, sha256: await hashFile(file) });
  }
  return rows;
}

async function importThroughUi(page, fixture) {
  await navigate(page, 'Library');
  await page.getByRole('button', { name: 'Add to library', exact: true }).click();
  await page.getByLabel('Title', { exact: true }).fill(fixture.title);
  if (fixture.kind === 'text') await page.getByLabel('Your study note', { exact: true }).fill(fixture.text);
  else {
    await page.getByRole('button', { name: 'Document', exact: true }).click();
    await page.getByLabel('Choose a study document', { exact: true }).setInputFiles(fixture.file);
    await page.getByLabel('I have permission to read, store, index and use this file for local learning.', { exact: true }).check();
  }
  const imported = await actionResponse(page, fixture.kind === 'text' ? '/library/import/text' : '/library/import/file',
    () => page.getByRole('button', { name: fixture.kind === 'text' ? 'Add note' : 'Add document', exact: true }).click(), 202);
  check(imported.document_id && imported.revision_id && imported.job?.id, 'A complete actual import identity is required.');
  return { ...fixture, imported };
}

async function originalBytes(page, revision, expectedHash) {
  const bytes = await page.evaluate(async revision => {
    const response = await fetch('/api/v1/library/revisions/' + revision + '/original');
    if (!response.ok) throw new Error('Original unavailable: ' + response.status);
    const buffer = new Uint8Array(await response.arrayBuffer());
    if (buffer.length > 1024 * 1024) throw new Error('Synthetic original exceeds its bounded size.');
    return { base64: btoa(Array.from(buffer, value => String.fromCharCode(value)).join('')), type: response.headers.get('content-type') };
  }, revision);
  const hash = sha(Buffer.from(bytes.base64, 'base64'));
  check(hash === expectedHash, 'The actual original bytes changed.');
  return { sha256: hash, mediaType: bytes.type };
}

async function downloadOriginal(application, page, link, evidence, extension, expectedHash) {
  const target = path.join(evidence, 'downloaded-original.' + extension);
  await application.evaluate(({ BrowserWindow }, { url, target }) => {
    const window = BrowserWindow.getAllWindows().find(item => item.webContents.getURL() === url);
    globalThis.renulusOriginalDownload = null;
    window.webContents.session.once('will-download', (_event, item, contents) => {
      if (contents?.id !== window.webContents.id) { item.cancel(); return; }
      item.setSavePath(target);
      item.once('done', (_event, state) => { globalThis.renulusOriginalDownload = { state, bytes: item.getReceivedBytes(), target: item.getSavePath() }; });
    });
  }, { url: page.url(), target });
  await link.click();
  const receipt = await poll(() => application.evaluate(() => globalThis.renulusOriginalDownload), value => !!value, 'Actual original download', 30_000);
  check(receipt.state === 'completed' && receipt.bytes > 0 && await hashFile(target) === expectedHash, 'The native original download failed or changed bytes.');
  return receipt;
}

async function inspectLibrary(page, row, evidence) {
  const status = await poll(() => api(page, '/library/documents/' + row.imported.document_id + '/import-status'), value => {
    check(!['failed', 'cancelled'].includes(value.status), 'Actual ingestion failed: ' + (value.job?.error_code ?? value.status));
    return value.status === 'ready' && value.job.state === 'ready';
  }, 'Actual ' + row.kind + ' ingestion');
  const document = await api(page, '/library/documents/' + row.imported.document_id);
  const revision = document.revisions.find(item => item.id === row.imported.revision_id);
  check(document.active_revision === revision?.id && revision.status === 'ready' && revision.rights.display
    && revision.rights.cache && revision.rights.index && revision.rights.embedding && !revision.rights.redistribution,
  'The original lost its active revision or explicit local-use rights.');
  const expectedHash = row.kind === 'text' ? sha(row.text) : row.sha256;
  check(revision.sha256 === expectedHash, 'Canonical original identity differs from the synthetic input.');
  let passage, citation;
  if (row.kind !== 'image') {
    check(revision.passage_count > 0, 'A queued/empty import is not a successful searchable source.');
    await page.getByLabel('Find a passage', { exact: true }).fill(row.query);
    const found = await actionResponse(page, '/library/retrieve', () => page.getByRole('button', { name: 'Search', exact: true }).click());
    passage = found.passages.find(item => item.document_id === document.id && item.document_revision === revision.id
      && (row.kind !== 'pdf' || item.locators.find(locator => Number.isInteger(locator.page) && locator.page > 0)?.page === 2));
    check(passage?.id && passage.locators.length > 0, 'No real passage/locator was retrieved for ' + row.kind + '.');
    citation = await api(page, '/library/revisions/' + revision.id + '/citation?passage_id=' + passage.id
      + (row.kind === 'pdf' ? '&page=2' : ''));
    check(citation.passage_id === passage.id && citation.document_revision === revision.id
      && JSON.stringify(citation.locators) === JSON.stringify(passage.locators.filter(locator => row.kind !== 'pdf' || locator.page === 2)), 'The exact passage citation changed its locators.');
    // The real passage button drives the existing SourceInspector, without a navigation fixture.
    const hit = page.locator('.library-passage').nth(found.passages.findIndex(item => item.id === passage.id));
    await hit.getByRole('heading', { name: document.title, exact: true }).waitFor();
    await hit.getByRole('button', { name: 'Inspect citation', exact: true }).click();
  } else {
    check(revision.passage_count === 0, 'The synthetic no-text image must honestly remain original-only.');
    citation = await api(page, '/library/revisions/' + revision.id + '/citation');
    check(citation.locators.length === 0 && citation.page === null, 'The original-only image invented a citation page.');
    await page.getByRole('button', { name: document.title, exact: true }).click();
    await page.getByText('This image is available to view. No searchable text was extracted.', { exact: true }).waitFor();
    const found = await api(page, '/library/retrieve', { query: row.title, scope: { kind: 'study' } });
    check(!found.passages.some(item => item.document_id === document.id), 'The original-only image invented searchable passages.');
    const missing = await api(page, '/library/revisions/' + revision.id + '/citation?page=1', undefined, 404);
    check(missing.error?.code === 'page_missing', 'The original-only image invented a physical page.');
  }
  const reader = page.getByRole('complementary', { name: 'Source reader', exact: true });
  // For page 2, require the exact passage-driven reader; whole-document fallback cannot pass.
  if (row.kind === 'pdf') await reader.getByRole('button', { name: 'Open original · page 2', exact: true }).click();
  else await reader.getByRole('button', { name: /^Open original/ }).click();
  const original = await originalBytes(page, revision.id, expectedHash);
  check(original.mediaType?.split(';')[0] === revision.media_type, 'The original response lost its declared media type.');
  let view;
  if (row.kind === 'pdf') {
    const viewer = reader.getByTitle('Original document viewer', { exact: true }); await viewer.waitFor();
    view = await poll(async () => { const frames = await capturePdfFrames(page); return { frames, ...classifyPdfFrames(frames, 2) }; },
      value => !value.blocked && value.viewerDetected && value.citationPageSelected, 'Native physical PDF page 2', 30_000);
  } else if (row.kind === 'image') {
    const image = reader.getByRole('img', { name: 'Original imported document', exact: true });
    await poll(() => image.evaluate(node => node.complete && node.naturalWidth > 0), Boolean, 'Original image rendering', 30_000);
    const link = reader.getByRole('link', { name: 'Save original (.png)', exact: true }); await link.waitFor();
    view = await downloadOriginal(row.application, page, link, evidence, 'png', expectedHash);
  } else if (row.kind.startsWith('office-')) {
    const extension = row.kind.slice(7), link = reader.getByRole('link', { name: 'Save original (.' + extension + ')', exact: true });
    await link.waitFor();
    // Same real native original-download seam used for PNG; no simulated response or dialog.
    view = await downloadOriginal(row.application, page, link, evidence, extension, expectedHash);
    check(citation.page === null && citation.locators.every(locator => locator.page === null)
      && (extension !== 'pptx' || citation.locators.some(locator => locator.slide >= 1))
      && (extension !== 'xlsx' || citation.locators.some(locator => locator.sheet >= 1 && locator.sheet_name)), 'Office citations invented a physical page or lost slide/sheet locations.');
  } else {
    await reader.locator('.library-original-text').waitFor();
    check(await reader.locator('.library-original-text').innerText() === row.text, 'The text original differs from the deliberate study note.');
  }
  await page.screenshot({ path: path.join(evidence, 'library-' + row.kind + '.png'), fullPage: true });
  return { ...row, application: undefined, status, document, revision, passage, citation, original, view };
}

async function temporaryJourney(page) {
  const sentinel = 'RENULUS_UNSAVED_' + randomUUID().replaceAll('-', '');
  await navigate(page, 'Cases');
  await page.getByLabel('Case title', { exact: true }).fill('Synthetic temporary retention check');
  await page.getByLabel('What would you like to discuss?', { exact: true }).fill(sentinel);
  const temporary = await actionResponse(page, '/cases/sessions',
    () => page.getByRole('button', { name: 'Start temporary case', exact: true }).click(), 201);
  check(temporary.id && !temporary.saved && temporary.text === sentinel && temporary.scope?.kind === 'temporary-case'
    && temporary.active_run_id === null, 'The actual temporary case was not established without Save or generation.');
  await page.getByRole('button', { name: 'End temporary context', exact: true }).waitFor();
  await navigate(page, 'Library');
  check(await page.getByRole('button', { name: 'Add to library', exact: true }).isDisabled(), 'Temporary case scope was silently promoted to Library.');
  await page.getByRole('button', { name: 'End temporary context', exact: true }).click();
  await poll(() => page.getByRole('button', { name: 'End temporary context', exact: true }).count(), value => value === 0, 'Explicit temporary context end', 30_000);
  check(!JSON.stringify(await api(page, '/data/export')).includes(sentinel), 'Unsaved case text entered canonical export.');
  return sentinel; // Never write the sentinel into an evidence receipt.
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

async function backupAll(page, evidence, sentinel) {
  const result = await page.evaluate(async () => {
    const response = await fetch('/api/v1/data/backup?format_version=2');
    if (!response.ok || response.headers.get('content-type')?.split(';')[0] !== 'application/zip') throw new Error('Actual full backup producer failed.');
    const reader = response.body.getReader(); let size = 0; const parts = [];
    while (true) { const next = await reader.read(); if (next.done) break; size += next.value.length;
      if (size > 32 * 1024 * 1024) { await reader.cancel(); throw new Error('Synthetic backup exceeds 32 MiB.'); }
      parts.push(next.value); }
    let text = ''; for (const part of parts) for (let offset = 0; offset < part.length; offset += 8192) text += String.fromCharCode(...part.subarray(offset, offset + 8192));
    return { base64: btoa(text), size, format: response.headers.get('x-renulus-backup-format') };
  });
  check(result.format === '2' && result.size > 0 && !JSON.stringify(await api(page, '/data/export')).includes(sentinel), 'A complete actual format-2 backup is required.');
  const file = path.join(evidence, 'all-formats-backup.zip'), bytes = Buffer.from(result.base64, 'base64');
  check(bytes.length === result.size, 'The actual producer transfer was incomplete.');
  await writeFile(file, bytes, { flag: 'wx' });
  return { file, bytes: bytes.length, sha256: sha(bytes), transport: 'actual authenticated backend; native Save/Cancel separately proved by reused producer harness' };
}

async function restoreThroughUi(page, file, { cancelFirst = false } = {}) {
  await navigate(page, 'Connections');
  await page.getByRole('navigation', { name: 'Connection settings', exact: true }).getByRole('button', { name: 'Your study data', exact: true }).click();
  const choose = async () => actionResponse(page, '/data/backup/preview',
    () => page.getByLabel('Choose ZIP backup or JSON export', { exact: true }).setInputFiles(file));
  let preview = await choose();
  check(preview.format_version === 2 && preview.original_count >= 6 && preview.record_count > 0, 'The actual all-format restore preview is incomplete.');
  const button = page.getByRole('button', { name: 'Restore full backup', exact: true });
  check(await button.isDisabled(), 'Restore must wait for deliberate date/deletion acknowledgement.');
  if (cancelFirst) {
    await actionResponse(page, '/data/backup/preview/' + preview.preview_token,
      () => page.getByRole('button', { name: 'Cancel restore', exact: true }).click(), 204, 'DELETE');
    check((await api(page, '/library/documents?limit=25&offset=0')).total === 0, 'Cancel restore wrote saved originals.');
    preview = await choose();
  }
  await page.getByLabel(/^I reviewed the backup date:/).check();
  await page.getByLabel('I understand and accept the deletion limits of this backup.', { exact: true }).check();
  const restored = await actionResponse(page, '/data/backup/restore', () => button.click());
  check(restored.recovery_id && restored.exported_at === preview.exported_at && restored.indexes === 'rebuild-required', 'The acknowledged restore receipt is incomplete.');
  const recovery = await poll(() => api(page, '/data/recovery'), value => {
    check(!['partial', 'blocked', 'failed'].includes(value.rebuild.status), 'Actual local rebuild failed: ' + value.rebuild.status);
    return value.rebuild.status === 'complete';
  }, 'Actual local knowledge/memory rebuild', 180_000, 1000);
  return { preview, restored, recovery };
}

export async function runInstalledProduct() {
  const request = validateInstalledRequest(process.env);
  const evidence = await createNativeEvidence('installed-product');
  const report = { kind: 'actual-installed-product-current-pc', checkedAt: new Date().toISOString(),
    slot: request.slot, sourceRevision: request.revision, executable: request.executable, evidence,
    acceptanceScope: installedAcceptancePlan().scope, gates: {}, shutdowns: [], launches: [],
    limits: ['Synthetic disconnected profiles; parent-owned normal profile and live subscription capabilities remain separately evidenced.',
      'Image/Office originals downloaded by actual DownloadItem to a confined path; opening a separate Office application or its Save dialog is not claimed.',
      'No inference/compaction/interpretation/medical-effectiveness claim; every failure or pending gate prevents this receipt passing.',
      'On this PC; unsigned is accepted. Signing and separate clean-PC/VM validation are optional future distribution work.'] };
  const pass = (name, proof) => { report.gates[name] = { status: 'passed', proof }; console.log(JSON.stringify({ gate: name, status: 'passed' })); };
  let current;
  try {
    const identity = await verifyArtifacts(request); pass('installed-identity', identity);
    await mkdir(path.join(evidence, 'temporary'));
    current = await launch(request, identity, evidence, 'profile', report); pass('isolated-runtime', report.launches.at(-1));
    const reviewed = await reviewedJourneys(current.page, evidence);
    pass('programme-selectors', { tracks: reviewed.tracks, goals: reviewed.goals, programmeHome: reviewed.programmeHome, handoff: reviewed.handoff });
    pass('reviewed-quiz', reviewed);
    // This established helper's inspector predates Office/C roots. Prove its real Save/Cancel before originals.
    const nativeBackup = await proveNativeProductBackup(current.application, current.page, evidence, request.executable, current.env);
    pass('native-backup-save-cancel', nativeBackup);
    const library = [];
    for (const fixture of await fixtures(identity, current, evidence)) {
      const row = await importThroughUi(current.page, fixture); row.application = current.application;
      const proof = await inspectLibrary(current.page, row, evidence); library.push(proof); pass('library-' + row.kind, proof);
    }
    const sentinel = await temporaryJourney(current.page);
    const backup = await backupAll(current.page, evidence, sentinel);
    const queued = [];
    const pdf = library.find(row => row.kind === 'pdf');
    // Real, bounded normal ingestion. Never pause/fake a converter to manufacture an active observation.
    for (let index = 0; index < 4; index++) {
      queued.push(await importThroughUi(current.page, { ...pdf, title: 'Synthetic shutdown PDF ' + index, imported: undefined }));
    }
    const ids = queued.map(row => row.imported.job.id);
    const active = await poll(() => api(current.page, '/library/capabilities'), value => value.ingestion_worker.running
      && ids.includes(value.ingestion_worker.active_job), 'An actually active owned ingestion job', 30_000, 100);
    const activeJob = await api(current.page, '/library/jobs/' + active.ingestion_worker.active_job);
    check(activeJob.state === 'processing', 'A queued receipt is not an active ingestion shutdown proof.');
    report.ingestionAtClose = { capabilities: active, activeJob, queued: queued.map(row => row.imported) };
    pass('normal-ingestion-close', { ingestion: report.ingestionAtClose, shutdown: await normalClose(current, report) });
    current = undefined; delete report.current;
    current = await launch(request, identity, evidence, 'profile', report);
    for (const session of reviewed.sessions) {
      const retained = await api(current.page, '/assessment/sessions/' + session.id);
      check(retained.status === 'ended' && retained.answered_count === 1, 'Reopen lost/doubled a completed reviewed session.');
    }
    check((await api(current.page, '/study/home')).progress.groups.fresh.answered === 3
      && (await api(current.page, '/study/goals')).track === 'eseneph', 'Reopen lost reviewed progress/programme preference.');
    for (const row of library) await originalBytes(current.page, row.revision.id, row.original.sha256);
    for (const row of queued) await poll(() => api(current.page, '/library/documents/' + row.imported.document_id + '/import-status'), value => {
      check(!['failed', 'cancelled'].includes(value.status), 'Restart did not recover its owned synthetic ingestion job.');
      return value.status === 'ready' && value.job.state === 'ready';
    }, 'Reopened normal ingestion');
    pass('normal-reopen', { sessions: reviewed.sessions.map(row => row.id), originals: library.length, recoveredJobs: ids });
    await normalClose(current, report); current = undefined; delete report.current;
    pass('temporary-retention', await assertNoSentinel(path.join(evidence, 'profile'), sentinel));
    current = await launch(request, identity, evidence, 'restored-profile', report);
    const restored = await restoreThroughUi(current.page, backup.file, { cancelFirst: true });
    check(restored.restored.restored_originals === library.length && restored.restored.excluded_originals === 0, 'Fresh full restore did not recover every accepted original.');
    for (const row of library) {
      await originalBytes(current.page, row.revision.id, row.original.sha256);
      const citation = await api(current.page, '/library/revisions/' + row.revision.id + '/citation'
        + (row.passage ? '?passage_id=' + row.passage.id + (row.kind === 'pdf' ? '&page=2' : '') : ''));
      check(JSON.stringify(citation) === JSON.stringify(row.citation), 'Restore changed the original passage citation.');
    }
    check((await api(current.page, '/study/home')).progress.groups.fresh.answered === 3, 'Full restore lost real assessment progress.');
    pass('full-backup-restore', { backup, ...restored, verifiedOriginals: library.length });
    const deleted = library[0];
    await navigate(current.page, 'Library');
    await current.page.getByRole('button', { name: deleted.title, exact: true }).click();
    const removal = await actionResponse(current.page, '/library/documents/' + deleted.document.id,
      () => current.page.getByRole('button', { name: 'Remove from library', exact: true }).click(), 200, 'DELETE');
    check(!removal.cleanup_pending, 'Known-deletion physical cleanup did not finish.');
    const reconciled = await restoreThroughUi(current.page, backup.file);
    check(reconciled.restored.excluded_by_deletion >= 1 && reconciled.restored.excluded_originals >= 1, 'Older restore did not reconcile this profile\'s newer deletion.');
    const missing = await current.page.evaluate(async revision => (await fetch('/api/v1/library/revisions/' + revision + '/original')).status, deleted.revision.id);
    check(missing === 404, 'An older backup resurrected the deleted original.');
    const found = await api(current.page, '/library/retrieve', { query: deleted.query, scope: { kind: 'study' } });
    check(!found.passages.some(row => row.document_id === deleted.document.id), 'Deleted source returned to search after rebuild.');
    await current.page.screenshot({ path: path.join(evidence, 'restored-data-and-deletions.png'), fullPage: true });
    pass('deletion-reconciliation', { removal, reconciled, deletedDocument: deleted.document.id, originalStatus: missing });
    pass('final-close', await normalClose(current, report)); current = undefined; delete report.current;
    validateCompleteReport(report); report.status = 'passed';
  } catch (error) {
    report.status = 'failed'; report.error = { message: error.message }; process.exitCode = 1;
  } finally {
    const owned = current ?? report.current;
    if (owned) {
      // Failure cleanup is explicitly separate from successful normal-shutdown evidence. No PID-based kill.
      try {
        let timer;
        try { await Promise.race([owned.application.close(), new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('Owned app cleanup exceeded 30 seconds; parent must inspect its exact identities.')), 30_000); })]); }
        finally { clearTimeout(timer); }
        report.failureCleanup = { attempted: true, identities: owned.identities };
      } catch (error) { report.cleanupError = error.message; process.exitCode = 1; }
    }
    delete report.current;
    for (const name of requiredGates) report.gates[name] ??= { status: 'not-run' };
    await writeFile(path.join(evidence, 'installed-product-evidence.json'), JSON.stringify(report, null, 2), { flag: 'wx' });
  }
  console.log(JSON.stringify({ evidence, status: report.status, error: report.error?.message, cleanupError: report.cleanupError }));
  return report;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.length === 3 && process.argv[2] === '--plan') console.log(JSON.stringify(installedAcceptancePlan(), null, 2));
  else if (process.argv.length === 3 && process.argv[2] === '--run') await runInstalledProduct();
  else throw new Error('Use --plan (read-only) or --run after the parent assigns the exact freeze and native/helper slot.');
}
