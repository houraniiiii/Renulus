/** Bounded current-PC acceptance. Importing this file or --plan never launches anything. */
import { createHash, randomUUID } from 'node:crypto';
import { createReadStream } from 'node:fs';
import { lstat, mkdir, open, readFile, readdir, stat, writeFile } from 'node:fs/promises';
import { execFileSync, spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { isDeepStrictEqual } from 'node:util';
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
  'native-backup-save-cancel': 'Hidden mode suppresses physical Save dialogs; no native dialog claim.',
});
export const coreGates = Object.freeze([
  'installed-identity', 'isolated-runtime', 'c-readiness', 'saved-conversations',
  'project-membership', 'saved-reviewed-test', 'whole-study', 'active-test-policy',
  'test-draft-reopen', 'whole-test', 'pdf-selection-reopen', 'temporary-retention', 'normal-reopen',
  'project-delete-preserves-chats', 'normal-ingestion-close', 'final-close',
]);
export const requiredGates = Object.freeze([...coreGates, ...readerGates, ...Object.keys(deferredGates)]);

export function installedAcceptancePlan() {
  return {
    scope: 'Hidden unsigned installed Design C on this Windows PC; signing and a separate PC/VM are optional future work.',
    prerequisiteCommits, requiredGates, coreGates, readerGates, deferredGates,
    requiredEnvironment: ['RENULUS_NATIVE_SLOT', 'RENULUS_EXPECT_SOURCE_REVISION', 'RENULUS_INSTALLED_PROOF=1',
      'RENULUS_PACKAGED_EXECUTABLE', 'RENULUS_DELIVERY_PROVENANCE', 'RENULUS_INSTALLER_EVIDENCE',
      'RENULUS_NATIVE_EVIDENCE_ROOT=' + designCEvidenceRoot],
    optionalEnvironment: ['RENULUS_ACCEPTANCE_REVISION (defaults to product revision; product ancestor, exact product/recovery verifier/test and Markdown docs-only changes)'],
    evidenceRoot: designCEvidenceRoot,
    resourceBound: 'One owned hidden app/backend at a time; two saved draft chats, one project, eleven deterministic synthetic originals covering eight reader categories, one Library import reusing that two-page PDF, and one real two-question reviewed set; no providers or simulated producer results.',
    receipt: 'installed-product-evidence.json; absent reader/migration/native gates remain not-run and make the aggregate incomplete/exit 1.',
    recoveryReopen: { command: '--recovery-reopen', requiredEnvironment: ['RENULUS_RECOVERY_RECEIPT', 'RENULUS_RECOVERY_RECEIPT_SHA256'],
      scope: 'Same matching-package environment; hash-verified Pauli recovery-evidence.json selects only its existing r-<8>/u. Two hidden launches, read-only original history checks and normal closes.',
      receipt: 'installed-recovery-reopen.json (exclusive create); no broader acceptance gates are changed.' },
    parentChecks: ['Assign the exclusive native/helper slot and immutable final source first.',
      'Publish the exact Design C generated/native proof root in shared guards; never bypass those guards.',
      'Supply the matching package/install receipts. Preserve separate native/live/physical and legacy-profile acceptance.'],
  };
}

export function validateInstalledRequest(env, platform = process.platform) {
  check(platform === 'win32', 'Installed acceptance runs on the authorised Windows PC.');
  check(/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}$/.test(env.RENULUS_NATIVE_SLOT ?? ''), 'The parent must assign RENULUS_NATIVE_SLOT before any native/helper work.');
  check(/^[0-9a-f]{40}$/.test(env.RENULUS_EXPECT_SOURCE_REVISION ?? ''), 'An exact immutable parent freeze is required.');
  const acceptanceRevision = env.RENULUS_ACCEPTANCE_REVISION === undefined
    ? env.RENULUS_EXPECT_SOURCE_REVISION : env.RENULUS_ACCEPTANCE_REVISION;
  check(typeof acceptanceRevision === 'string' && /^[0-9a-f]{40}$/.test(acceptanceRevision),
    'RENULUS_ACCEPTANCE_REVISION must be an exact immutable 40-character commit SHA.');
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
  return { slot: env.RENULUS_NATIVE_SLOT, revision: env.RENULUS_EXPECT_SOURCE_REVISION, acceptanceRevision,
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

export function validateAcceptanceChanges(productRevision, acceptanceRevision, changes, productIsAncestor) {
  check([productRevision, acceptanceRevision].every(value => typeof value === 'string' && /^[0-9a-f]{40}$/.test(value))
    && productIsAncestor === true, 'The exact product commit must be an ancestor of the acceptance commit.');
  const allowedScripts = ['apps/desktop/scripts/verify-installed-product.mjs', 'apps/desktop/scripts/test-verify-installed-product.mjs',
    'apps/desktop/scripts/verify-installed-recovery.py', 'apps/desktop/scripts/test_verify_installed_recovery.py'];
  check(Array.isArray(changes) && changes.every(name => typeof name === 'string'
    && (allowedScripts.includes(name) || name.startsWith('docs/') && name.endsWith('.md')
      && !name.includes('\\') && !name.includes(':') && name.split('/').every(part => part && part !== '.' && part !== '..'))),
  'Acceptance-only changes may touch only the exact product/recovery verifiers, their tests and Markdown documentation; product changes require a new manufacture.');
  check(productRevision !== acceptanceRevision || changes.length === 0, 'A single freeze cannot claim a separate acceptance diff.');
  return { productRevision, acceptanceRevision, changedPaths: changes };
}

function acceptanceFreeze(request) {
  for (const revision of [request.revision, request.acceptanceRevision]) {
    check(git(['rev-parse', '--verify', revision + '^{commit}']).toString('utf8').trim() === revision,
      'Product and acceptance revisions must resolve to their exact commit objects.');
  }
  git(['merge-base', '--is-ancestor', request.revision, request.acceptanceRevision]);
  const changes = git(['diff', '--name-only', '-z', '--no-renames', request.revision, request.acceptanceRevision, '--'])
    .toString('utf8').split('\0').filter(Boolean);
  return validateAcceptanceChanges(request.revision, request.acceptanceRevision, changes, true);
}

const exportAttributeNames = ['text', 'eol', 'filter', 'working-tree-encoding', 'export-subst'];
async function frozenExportAttributes(revision, names) {
  // --source uses committed attributes; disable global/system attributes and refuse the remaining local override.
  const local = path.resolve(repository, git(['rev-parse', '--git-path', 'info/attributes']).toString('utf8').trim());
  try { check((await lstat(local)).size === 0, 'Frozen source export refuses local info/attributes overrides.'); }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
  const fields = execFileSync('git', ['-c', 'core.attributesFile=NUL', 'check-attr', '--source=' + revision,
    '-z', '--stdin', ...exportAttributeNames], { cwd: repository, windowsHide: true, maxBuffer: 16 * 1024 * 1024,
    env: { ...process.env, GIT_ATTR_NOSYSTEM: '1' }, input: Buffer.from(names.join('\0') + '\0') })
    .toString('utf8').split('\0');
  check(fields.pop() === '' && fields.length === names.length * exportAttributeNames.length * 3,
    'Frozen export attributes returned an incomplete path inventory.');
  const result = new Map(names.map(name => [name, {}]));
  for (let index = 0; index < fields.length; index += 3) {
    const [name, attribute, value] = fields.slice(index, index + 3), entry = result.get(name);
    check(entry && exportAttributeNames.includes(attribute) && !(attribute in entry), 'Unexpected frozen export attribute.');
    entry[attribute] = value;
  }
  return result;
}

export function validateFrozenExport(name, blob, attributes, actual) {
  check(Buffer.isBuffer(blob) && ['filter', 'working-tree-encoding', 'export-subst']
    .every(key => ['unspecified', 'unset'].includes(attributes?.[key])), 'Unsupported frozen source export transformation: ' + name);
  let expected = blob;
  if (attributes.eol === 'crlf') {
    check(attributes.text === 'set', 'Only explicitly declared text/eol=crlf export is supported: ' + name);
    // Transform expected Git bytes only, matching declared text export. Never normalize installed bytes.
    const parts = [];
    let start = 0;
    for (let index = 0; index < blob.length; index++) {
      if (blob[index] === 10 && (index === 0 || blob[index - 1] !== 13)) {
        parts.push(blob.subarray(start, index), Buffer.from([13, 10])); start = index + 1;
      }
    }
    if (parts.length) { parts.push(blob.subarray(start)); expected = Buffer.concat(parts); }
  } else {
    check(['lf', 'unspecified', 'unset'].includes(attributes.eol), 'Unsupported frozen EOL declaration: ' + name);
  }
  check(actual?.size === expected.length && actual.sha256 === sha(expected),
    'Installed source bytes differ from the exact frozen export: ' + name);
  return { path: name, attributes, blobSha256: sha(blob), exportSha256: sha(expected), exportBytes: expected.length };
}

async function verifyArtifacts(request) {
  const freeze = acceptanceFreeze(request);
  for (const commit of prerequisiteCommits) git(['merge-base', '--is-ancestor', commit, request.revision]);
  const scripts = ['native-journeys.mjs', 'verify-installed-product.mjs', 'native-replacement-evidence.mjs',
    'native-evidence-directory.mjs', 'wait-for-flow-window.mjs', 'synthetic-pdf.mjs', 'pdf-viewer-evidence.mjs',
    'native-product-backup.mjs', 'operate-owned-save-dialog.ps1', 'inspect-native-backup.py', 'design-c-reader-fixtures.py',
    'test-verify-installed-product.mjs', 'verify-installed-recovery.py', 'test_verify_installed_recovery.py'];
  const driverHashes = {};
  for (const name of scripts) {
    const file = 'apps/desktop/scripts/' + name;
    driverHashes[name] = validateFrozenScript(name, git(['show', request.acceptanceRevision + ':' + file]),
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
  const sourceRows = git(['ls-tree', '-r', '-z', request.revision, '--', ...roots]).toString('utf8').split('\0').filter(Boolean)
    .map(row => { const [header, name] = row.split('\t'); const [mode, type, object] = header.split(' '); return { name, mode, type, object }; })
    .filter(row => !(row.name.startsWith('upstream/hermes/') && excluded.test(row.name.slice('upstream/hermes/'.length))));
  const attributes = await frozenExportAttributes(request.revision, sourceRows.map(row => row.name));
  const sourceExports = [];
  let frozenFiles = 0;
  for (const { name, mode, type, object } of sourceRows) {
    check(type === 'blob' && mode !== '120000' && listed.has(name), 'The installed backend omits a frozen source file: ' + name);
    const declaration = attributes.get(name);
    check(['filter', 'working-tree-encoding', 'export-subst'].every(key => ['unspecified', 'unset'].includes(declaration[key])),
      'Unsupported frozen source export transformation: ' + name);
    if (declaration.eol === 'crlf') {
      sourceExports.push({ gitBlob: object, ...validateFrozenExport(name, git(['cat-file', 'blob', object]), declaration, listed.get(name)) });
    } else {
      check(['lf', 'unspecified', 'unset'].includes(declaration.eol), 'Unsupported frozen EOL declaration: ' + name);
      const file = path.join(backend, name);
      check(await hashFile(file, 'sha1', 'blob ' + listed.get(name).size + '\0') === object, 'Installed source bytes differ from Git: ' + name);
    }
    frozenFiles++;
  }
  return { resources, backend, archive, electronVersion, actual, frozenFiles, inventoryFiles: listed.size, driverHashes, freeze, sourceExports,
    productRevision: request.revision, acceptanceRevision: request.acceptanceRevision,
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

export function captureResponse(page, matches, { expected = 200, binary = false, label, timeout = 120_000 }) {
  // Consume the real body as soon as the response arrives. Waiting for a click/navigation
  // to finish first lets Chromium evict the response from its inspector cache.
  return page.waitForResponse(matches, { timeout }).then(async response => {
    check(response.status() === expected, 'The actual UI response failed: ' + label + ' (' + response.status() + ').');
    const headers = response.headers();
    try {
      const body = expected === 204 ? null : await (binary ? response.body() : response.json());
      return { body, headers };
    } catch (error) {
      throw new Error('Actual response body capture failed: ' + label + ': ' + error.message, { cause: error });
    }
  });
}

async function actionResponse(page, route, action, expected = 200, method = 'POST') {
  const pending = captureResponse(page, response => new URL(response.url()).pathname === '/api/v1' + route
    && response.request().method() === method, { expected, label: method + ' ' + route });
  const [captured] = await Promise.all([pending, action()]);
  return captured.body;
}

// Evaluated in the owned renderer only around one saved synthetic Confirm attach.
// CDP does not retain this upload's response body; observe a clone of the real fetch
// response instead. The app receives the identical promise/Response, without replay.
export function installAttachmentCapture(spec) {
  const require = (condition, message) => { if (!condition) throw new Error(message); };
  const origin = new URL(spec.origin), limit = 64 * 1024;
  require(origin.protocol === 'http:' && origin.hostname === '127.0.0.1' && origin.port
    && origin.origin === spec.origin && location.origin === spec.origin && location.hash === spec.hash
    && spec.retention === 'saved' && spec.conversation?.type === 'learn_thread'
    && /^thread_[a-f0-9]{32}$/.test(spec.conversation.id)
    && spec.hash === '#/chat/learn_thread/' + spec.conversation.id
    && /^(?:synthetic-reading\.(?:pdf|docx|csv|xlsx|md|html|xml|png|jpg|tiff)|synthetic-denied-entity\.xml)$/.test(spec.filename)
    && Number.isSafeInteger(spec.bytes) && spec.bytes > 0 && spec.bytes < limit
    && /^[a-f0-9]{64}$/.test(spec.sha256), 'Attachment capture requires its exact saved synthetic original.');
  const original = globalThis.fetch, endpoint = spec.origin + '/api/v1/attachments';
  let settled = false, reader, timer, resolve, reject;
  const result = new Promise((yes, no) => { resolve = yes; reject = no; });
  result.catch(() => {}); // A UI action may fail before the host awaits the observer.
  const restore = () => { if (globalThis.fetch === observedFetch) globalThis.fetch = original; };
  const finish = (error, value) => {
    if (settled) return;
    settled = true; clearTimeout(timer); restore();
    if (error) { if (reader) void reader.cancel().catch(() => {}); reject(new Error(error)); }
    else resolve(value);
  };
  function match(args) {
    const [input, init] = args;
    // Do not read arbitrary Request bodies, temporary input or credential values.
    if (typeof input !== 'string' || !init || init.method !== 'POST'
      || location.origin !== spec.origin || location.hash !== spec.hash) return;
    const url = new URL(input, spec.origin);
    if (url.href !== endpoint || url.username || url.password || !(init.body instanceof File)
      || init.body.name !== spec.filename || init.body.size !== spec.bytes
      || !(init.headers instanceof Headers)) return;
    if ([...init.headers.keys()].some(name => !['accept', 'x-renulus-attachment-options'].includes(name))) return;
    const options = init.headers.get('x-renulus-attachment-options');
    if (!options || options.length > 16_000) return;
    const command = JSON.parse(options);
    if (command.conversation?.type !== spec.conversation.type || command.conversation.id !== spec.conversation.id
      || command.filename !== spec.filename || command.title !== spec.filename
      || !/^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/.test(command.idempotency_key ?? '')
      || !['expected_conversation_revision', 'expected_policy_revision', 'expected_context_epoch']
        .every(name => Number.isSafeInteger(command[name]) && command[name] >= 0)
      || command.rights?.display !== true || command.rights.cache !== true
      || command.metadata?.source_owner !== 'Renulus synthetic fixture author') return;
    return { file: init.body, key: command.idempotency_key };
  }
  async function observe(response, request) {
    // Clone synchronously, before the app's continuation can consume the body.
    require(response.url === endpoint && !response.redirected && response.status === 201,
      'Attachment capture requires the actual nonredirected 201 response.');
    const headers = Object.fromEntries(['content-type', 'cache-control', 'x-content-type-options', 'content-length']
      .map(name => [name, response.headers.get(name)]));
    require(/^application\/json(?:;|$)/i.test(headers['content-type'] ?? '') && headers['cache-control'] === 'no-store'
      && (headers['content-length'] === null || /^\d+$/.test(headers['content-length'])
        && Number(headers['content-length']) <= limit), 'Attachment response headers or size are invalid.');
    reader = response.clone().body.getReader();
    const digest = await crypto.subtle.digest('SHA-256', await request.file.arrayBuffer());
    require(Array.from(new Uint8Array(digest), value => value.toString(16).padStart(2, '0')).join('') === spec.sha256,
      'Attachment request original SHA differs from the checked fixture.');
    const chunks = []; let length = 0;
    while (!settled) {
      const { value, done } = await reader.read(); if (done) break;
      length += value.byteLength;
      require(length <= limit, 'Attachment response exceeds the capture byte bound.'); chunks.push(value);
    }
    if (settled) return;
    const bytes = new Uint8Array(length); let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    finish(null, { status: response.status, headers, bytes: Array.from(bytes), request: {
      method: 'POST', path: '/api/v1/attachments', conversation: spec.conversation, idempotency_key: request.key,
      filename: spec.filename, sha256: spec.sha256, bytes: spec.bytes } });
  }
  function observedFetch(...args) {
    let request;
    try { request = match(args); } catch { /* Nonmatching input remains untouched. */ }
    const pending = Reflect.apply(original, this, args);
    if (request) {
      restore(); // One actual upload only; later app traffic is never observed.
      void pending.then(response => {
        if (!settled) return observe(response, request);
      }, () => { finish('The actual attachment fetch failed.'); })
        .catch(error => finish(error.message?.startsWith('Attachment ') ? error.message : 'Attachment response capture failed.'));
    }
    return pending;
  }
  globalThis.fetch = observedFetch;
  timer = setTimeout(() => finish('Attachment response capture timed out.'), 120_000);
  return { result, dispose: () => finish('Attachment response capture disposed.') };
}

async function attachmentResponse(page, chat, fixture, action) {
  const capture = await page.evaluateHandle(installAttachmentCapture, { origin: new URL(page.url()).origin,
    hash: chatHash(chat), conversation: chat.identity, retention: chat.retention,
    filename: fixture.filename, bytes: fixture.bytes, sha256: fixture.sha256 });
  try {
    const [record] = await Promise.all([capture.evaluate(value => value.result), action()]);
    check(record.status === 201 && record.headers['cache-control'] === 'no-store'
      && record.bytes.length <= 64 * 1024, 'The actual attachment response was not a bounded saved publication.');
    return json(Buffer.from(record.bytes));
  } finally {
    try { await capture.evaluate(value => value.dispose()); } finally { await capture.dispose(); }
  }
}

// These are the real UI's binary fetches, not a new fetch or a CDP byte repair.
// Each installation observes one exact saved-fixture asset/original request.
export function installReaderBinaryCapture(spec) {
  const require = (condition, message) => { if (!condition) throw new Error(message); };
  const origin = new URL(spec.origin), asset = spec.operation === 'asset';
  const allowed = { pdf: ['pdf:1', 'pdf:2'], docx: ['docx:rId1'], png: ['image:1'], jpg: ['image:1'], tiff: ['image:1', 'image:2'] };
  const extension = spec.filename?.split('.').at(-1);
  require(origin.protocol === 'http:' && origin.hostname === '127.0.0.1' && origin.port && origin.origin === spec.origin
    && location.origin === spec.origin && location.hash === spec.hash && spec.retention === 'saved'
    && spec.conversation?.type === 'learn_thread' && /^thread_[a-f0-9]{32}$/.test(spec.conversation.id)
    && spec.hash === '#/chat/learn_thread/' + spec.conversation.id
    && spec.reference?.target?.type === 'attachment' && /^attachment_[a-f0-9]{32}$/.test(spec.reference.target.id)
    && /^(?:synthetic-reading\.(?:pdf|docx|csv|xlsx|md|html|xml|png|jpg|tiff)|synthetic-denied-entity\.xml)$/.test(spec.filename)
    && /^[a-f0-9]{64}$/.test(spec.sha256) && Number.isSafeInteger(spec.bytes) && spec.bytes > 0 && spec.bytes < 65536
    && ['asset', 'original'].includes(spec.operation) && (!asset || allowed[extension]?.includes(spec.assetId))
    && [1, 2].includes(spec.page) && [1, 101].includes(spec.firstRow)
    && (spec.page === 1 || ['pdf', 'tiff'].includes(extension)) && (spec.firstRow === 1 || extension === 'csv')
    && [null, 'Dialysis'].includes(spec.sheet) && (spec.sheet === null || extension === 'xlsx')
    && (!asset || spec.assetId === 'docx:rId1' || Number(spec.assetId.split(':')[1]) === spec.page),
  'Reader capture requires one exact saved synthetic original/view.');
  const endpoint = spec.origin + '/api/v1/readers/' + spec.operation;
  const limit = asset ? 16 * 1024 * 1024 : spec.bytes, original = globalThis.fetch;
  let settled = false, resolve, reject, reader, timer;
  const result = new Promise((yes, no) => { resolve = yes; reject = no; }); result.catch(() => {});
  const restore = () => { if (globalThis.fetch === observedFetch) globalThis.fetch = original; };
  const finish = (error, value) => {
    if (settled) return;
    settled = true; clearTimeout(timer); restore();
    if (error) { if (reader) void reader.cancel().catch(() => {}); reject(new Error(error)); } else resolve(value);
  };
  const canonical = value => JSON.stringify(value, (_key, item) => item && typeof item === 'object' && !Array.isArray(item)
    ? Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]])) : item);
  function matches(args) {
    const [input, init] = args;
    if (typeof input !== 'string' || !init || init.method !== 'POST' || typeof init.body !== 'string' || init.body.length > 4096
      || location.origin !== spec.origin || location.hash !== spec.hash || !(init.headers instanceof Headers)) return false;
    const url = new URL(input, spec.origin);
    if (url.href !== endpoint || url.username || url.password
      || [...init.headers.keys()].some(name => !['accept', 'content-type'].includes(name))
      || init.headers.get('content-type') !== 'application/json') return false;
    const body = JSON.parse(init.body);
    const keys = ['reference', 'conversation', 'page', 'sheet', 'first_row', 'row_limit', ...(asset ? ['asset_id', 'original_sha256'] : [])];
    return Object.keys(body).every(key => keys.includes(key))
      && canonical(body.conversation) === canonical(spec.conversation)
      && Object.keys(body.reference ?? {}).every(key => ['target', 'locator'].includes(key))
      && canonical(body.reference?.target) === canonical(spec.reference.target)
      && canonical(body.reference?.locator ?? null) === canonical(spec.reference.locator ?? null)
      && body.page === spec.page && (body.sheet ?? null) === spec.sheet && body.first_row === spec.firstRow && body.row_limit === 100
      && (!asset || body.asset_id === spec.assetId && body.original_sha256 === spec.sha256);
  }
  async function observe(response) {
    require(response.url === endpoint && !response.redirected && response.status === 200,
      'Reader binary capture requires the actual nonredirected 200 response.');
    const headers = Object.fromEntries(['content-type', 'cache-control', 'x-content-type-options', 'content-length',
      'content-security-policy', 'content-disposition'].map(name => [name, response.headers.get(name)]));
    require(headers['content-type'] === (asset ? 'image/png' : 'application/octet-stream') && headers['cache-control'] === 'no-store'
      && (headers['content-length'] === null || /^\d+$/.test(headers['content-length']) && Number(headers['content-length']) <= limit),
      'Reader binary response headers or size are invalid.');
    reader = response.clone().body.getReader(); // Synchronous clone before the app consumes its blob.
    const chunks = []; let length = 0;
    while (!settled) {
      const { value, done } = await reader.read(); if (done) break;
      length += value.byteLength;
      require(length <= limit, 'Reader binary response exceeds the capture byte bound.'); chunks.push(value);
    }
    if (settled) return;
    require(headers['content-length'] === null || length === Number(headers['content-length']), 'Reader binary response length differs.');
    const bytes = new Uint8Array(length); let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    finish(null, { status: response.status, headers, bytes: Array.from(bytes) });
  }
  function observedFetch(...args) {
    let matched = false; try { matched = matches(args); } catch { /* Other requests are untouched. */ }
    const pending = Reflect.apply(original, this, args);
    if (matched) {
      restore();
      void pending.then(response => { if (!settled) return observe(response); }, () => finish('The actual Reader binary fetch failed.'))
        .catch(error => finish(error.message?.startsWith('Reader binary ') ? error.message : 'Reader binary capture failed.'));
    }
    return pending;
  }
  globalThis.fetch = observedFetch;
  timer = setTimeout(() => finish('Reader binary capture timed out.'), 30_000);
  return { result, dispose: () => finish('Reader binary capture disposed.') };
}

export function observedBinaryBytes(bytes) {
  check(Buffer.isBuffer(bytes) && bytes.length <= 16 * 1024 * 1024, 'Synthetic byte diagnostics exceed their bound.');
  return { length: bytes.length, first16Hex: bytes.subarray(0, 16).toString('hex'), sha256: sha(bytes) };
}

export function observeReaderCdp(page, matches) {
  let settled = false, resolve;
  const result = new Promise(yes => { resolve = yes; });
  const finish = value => {
    if (settled) return;
    settled = true; clearTimeout(timer); page.off('response', onResponse); resolve(value);
  };
  const onResponse = response => {
    try { if (!matches(response)) return; } catch { return; }
    page.off('response', onResponse); // Observe only the same single actual request.
    void (async () => ({ status: 'observed', httpStatus: response.status(), contentType: response.headers()['content-type'],
      ...observedBinaryBytes(await response.body()) }))().then(finish, () => finish({ status: 'unavailable' }));
  };
  const timer = setTimeout(() => finish({ status: 'unavailable' }), 30_000);
  page.on('response', onResponse);
  return { result, dispose: () => finish({ status: 'unavailable' }) };
}

async function readerBinaryAction(page, chat, attachment, fixture, view, action, progress) {
  validateReaderOriginal(fixture, attachment.original, attachment.media_type);
  check(attachment.retention === 'saved' && attachment.conversation?.type === chat.identity.type
    && attachment.conversation.id === chat.identity.id, 'Binary capture requires the actual saved original owner.');
  const spec = { origin: new URL(page.url()).origin, hash: chatHash(chat), conversation: chat.identity,
    retention: chat.retention, reference: attachment.reference, filename: fixture.filename, sha256: fixture.sha256,
    bytes: fixture.bytes, operation: view.assetId ? 'asset' : 'original', page: view.page ?? 1,
    sheet: view.sheet ?? null, firstRow: view.firstRow ?? 1, assetId: view.assetId };
  const capture = await page.evaluateHandle(installReaderBinaryCapture, spec);
  const observation = { route: '/readers/' + spec.operation, ...(spec.assetId ? { assetId: spec.assetId } : {}),
    clone: { status: 'pending' }, cdp: { status: 'pending' } };
  progress.binaryObservation = observation;
  // CDP is diagnostic only. Never decode/repair it or use it as replacement data.
  const cdp = observeReaderCdp(page, response => {
    if (response.url() !== spec.origin + '/api/v1/readers/' + spec.operation || response.request().method() !== 'POST') return false;
    const body = response.request().postDataJSON();
    return body?.reference?.target?.type === 'attachment' && body.reference.target.id === attachment.id
      && body.conversation?.type === chat.identity.type && body.conversation.id === chat.identity.id
      && body.page === spec.page && (body.sheet ?? null) === spec.sheet && body.first_row === spec.firstRow && body.row_limit === 100
      && (!spec.assetId || body.asset_id === spec.assetId && body.original_sha256 === fixture.sha256);
  });
  const diagnostic = cdp.result.then(value => { observation.cdp = value; });
  try {
    const bytes = capture.evaluate(value => value.result).then(record => {
      const body = Buffer.from(record.bytes);
      observation.clone = { status: 'observed', httpStatus: record.status, contentType: record.headers['content-type'],
        ...observedBinaryBytes(body) };
      return { body, headers: record.headers, observation };
    });
    const [record, actionResult] = await Promise.all([bytes, action(), diagnostic]);
    return { record, actionResult };
  } finally {
    cdp.dispose();
    try { await capture.evaluate(value => value.dispose()); } finally { await capture.dispose(); }
  }
}

async function poll(work, accepts, label, timeout = 180_000, interval = 500) {
  const deadline = Date.now() + timeout;
  let value;
  do { value = await work(); if (accepts(value)) return value; await sleep(interval); } while (Date.now() < deadline);
  throw new Error(label + ' did not reach its required state.');
}

async function navigate(page, hash) {
  check(/^#\/(?:projects|tests|chat|attempts|library)(?:\/[a-zA-Z0-9_-]+){0,2}$/.test(hash), 'Use a bounded canonical C route.');
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
    // The frozen embedded _pth includes '..', which resolves to this exact backend root.
    && Array.isArray(interpreter.paths) && interpreter.paths.length > 0
    && interpreter.paths.every(value => typeof value === 'string' && path.isAbsolute(value)
      && (samePath(backend, value) || inside(backend, value)))
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
  const current = { application, env, profile, executable: request.executable, identities: [], page: null };
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
  current.mainPid = native.pid;
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

export async function freshHiddenFrame() {
  let timer;
  try {
    await Promise.race([
      (async () => { await document.fonts.ready; await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))); })(),
      new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('The hidden renderer did not produce a fresh frame within five seconds.')), 5_000); }),
    ]);
  } finally { clearTimeout(timer); }
}

export async function captureHiddenWindow({ BrowserWindow }, expected) {
  const same = (left, right) => typeof left === 'string' && typeof right === 'string'
    && left.replaceAll('\\', '/').toLowerCase() === right.replaceAll('\\', '/').toLowerCase();
  if (!Number.isSafeInteger(expected.pid) || process.pid !== expected.pid || !same(process.execPath, expected.executable))
    throw new Error('The hidden capture executable/process identity differs.');
  const windows = BrowserWindow.getAllWindows().filter(window => !window.isDestroyed());
  const matches = windows.filter(window => window.webContents.getURL() === expected.url);
  const hidden = window => !window.isDestroyed() && !window.isVisible() && !window.isFocused() && !window.isFocusable();
  if (matches.length !== 1 || !windows.every(hidden)) throw new Error('The exact owned hidden capture window is unavailable.');
  const window = matches[0];
  const image = await window.capturePage(undefined, { stayHidden: true, stayAwake: false });
  if (!hidden(window) || window.webContents.getURL() !== expected.url) throw new Error('The hidden capture window changed.');
  const size = image.getSize();
  if (image.isEmpty() || size.width < 1 || size.height < 1 || size.width > 4096 || size.height > 4096
    || size.width * size.height > 12_000_000) throw new Error('The hidden capture has invalid dimensions.');
  const bytes = image.toPNG();
  if (bytes.length > 16 * 1024 * 1024) throw new Error('The hidden capture exceeds its byte bound.');
  return bytes.toString('base64');
}

async function captureDeadline(pending, milliseconds) {
  let timer;
  try { return await Promise.race([pending, new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error('The owned hidden capture exceeded its deadline.')), milliseconds);
  })]); } finally { clearTimeout(timer); }
}

export async function hiddenScreenshotBytes(current) {
  const url = current.page.url(), parsed = new URL(url);
  check(parsed.protocol === 'http:' && parsed.hostname === '127.0.0.1' && parsed.port
    && !parsed.username && !parsed.password && !parsed.search && ['/', '/index.html'].includes(parsed.pathname),
    'The capture requires the owned loopback renderer URL.');
  const before = await hiddenWindowState(current.application);
  check(before.filter(window => window.url === url).length === 1, 'The exact owned capture page is unavailable.');
  try {
    await captureDeadline(current.page.evaluate(freshHiddenFrame), 5_100);
    const encoded = await captureDeadline(current.application.evaluate(captureHiddenWindow,
      { url, executable: current.executable, pid: current.mainPid }), 15_000);
    check(typeof encoded === 'string' && encoded.length <= Math.ceil(16 * 1024 * 1024 / 3) * 4
      && /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(encoded), 'Invalid hidden PNG encoding.');
    const bytes = Buffer.from(encoded, 'base64');
    const raster = validateReaderRaster(bytes);
    check(raster.width <= 4096 && raster.height <= 4096, 'The hidden PNG dimensions exceed the bound.');
    return bytes;
  } finally {
    const after = await captureDeadline(hiddenWindowState(current.application), 5_000);
    check(after.filter(window => window.url === url).length === 1, 'The owned capture page changed.');
  }
}

async function screenshot(current, evidence, name) {
  const bytes = await hiddenScreenshotBytes(current);
  await writeFile(path.join(evidence, name + '.png'), bytes, { flag: 'wx' });
}
export async function captureFailureScreenshot(current, evidence, report, temporaryPhase) {
  if (!current?.page || temporaryPhase) return;
  try {
    await screenshot(current, evidence, 'failure');
    report.failureScreenshot = 'failure.png';
  } catch (error) {
    report.failureScreenshotError = safeFailure(error); // Preserve the primary journey failure.
  }
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
export function validateAssistanceRefusal(refusal) {
  check(refusal?.status === 409 && refusal.code === 'assistance_restricted' && refusal.cacheControl === 'no-store',
    'Active Test must refuse conversation help with exactly 409 assistance_restricted and no-store.');
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
    const body = await response.json(); return { status: response.status, code: body.error?.code,
      cacheControl: response.headers.get('cache-control') };
  });
  validateAssistanceRefusal(refusal);
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
  const pending = captureResponse(page, response => {
    if (new URL(response.url()).pathname !== '/api/v1/readers/resolve' || response.request().method() !== 'POST') return false;
    return response.request().postDataJSON()?.reference?.target?.id === attachment.id;
  }, { label: 'POST /readers/resolve' });
  const [captured] = await Promise.all([pending, action()]);
  return captured.body;
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
  const attachment = await attachmentResponse(page, chat, fixture,
    () => page.getByRole('button', { name: 'Confirm attach', exact: true }).click());
  validateReaderOriginal(fixture, attachment.original, attachment.media_type);
  check(attachment.retention === 'saved' && attachment.filename === fixture.filename && attachment.reference?.target?.id === attachment.id
    && attachment.reference.target.type === 'attachment' && attachment.conversation?.type === chat.identity.type
    && attachment.conversation.id === chat.identity.id, 'Upload did not publish an original under the intended saved conversation.');
  return attachment;
}

async function prepareReaderDownload(page, reader, chat, attachment, fixture, document, progress) {
  const { record: { body: data, headers } } = await readerBinaryAction(page, chat, attachment, fixture,
    { page: document.payload?.page ?? 1, sheet: fixture.gate === 'reader-xlsx' ? 'Dialysis' : null,
      firstRow: document.payload?.table?.first_row ?? 1 },
    () => reader.getByRole('button', { name: 'Prepare original download', exact: true }).click(), progress);
  check(sha(data) === fixture.sha256 && data.length === fixture.bytes,
    'The real original-download action changed the uploaded bytes.');
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

async function readerFixtureJourney(current, chat, fixtures, fixture, evidence, progress) {
  const { page } = current;
  progress.stage = 'attachment-upload';
  const attachment = await uploadReaderOriginal(page, chat, fixtures, fixture);
  const assets = [], externalRequests = [];
  async function assetAction(assetId, pageNumber, action) {
    const { record, actionResult } = await readerBinaryAction(page, chat, attachment, fixture,
      { assetId, page: pageNumber }, action, progress);
    assets.push({ assetId, ...record }); return actionResult;
  }
  const deny = route => { externalRequests.push(route.request().url()); return route.abort('blockedbyclient'); };
  await page.context().route(fixtures.manifest.external_origin + '/**', deny);
  try {
    progress.stage = 'reader-open';
    const open = () => readerResponse(page, attachment, () => page.locator('.chat-attached-file')
      .filter({ hasText: fixture.filename }).getByRole('button', { name: 'Open file', exact: true }).click());
    const firstAsset = fixture.gate === 'reader-pdf' ? 'pdf:1' : fixture.gate === 'reader-images' ? 'image:1'
      : fixture.gate === 'reader-docx' ? 'docx:rId1' : null;
    let document = await (firstAsset ? assetAction(firstAsset, 1, open) : open());
    validateReaderDocument(fixture, document, attachment);
    progress.stage = 'reader-render';
    const reader = page.getByRole('region', { name: 'Document reader', exact: true });
    await reader.getByRole('heading', { name: attachment.title, exact: true }).waitFor();
    const positions = [];
    async function raster(assetId) {
      const captured = assets.find(row => row.assetId === assetId);
      check(captured, 'The actual UI did not request the expected fixture asset.');
      progress.binaryObservation = captured.observation;
      const result = { assetId, ...validateReaderRaster(captured.body) };
      await poll(() => reader.getByAltText('Source page', { exact: true }).evaluateAll(images => images.every(image => image.complete && image.naturalWidth > 0) && images.length > 0), Boolean, 'Decoded reader image', 30_000);
      if (fixture.expect.width) check(result.width === fixture.expect.width && result.height === fixture.expect.height, 'Decoded image size differs from the original.');
      return result;
    }
    let firstRaster;
    progress.stage = 'initial-raster-and-position';
    if (document.payload?.asset_id) firstRaster = await raster(document.payload.asset_id);
    if (fixture.expect.pages === 2) {
      const kind = fixture.expect.kind === 'pdf' ? 'pdf' : 'image';
      positions.push(await savedReaderPosition(page, chat, attachment, kind === 'pdf' ? { kind, physical_page: 1 } : { kind, frame: 1 }));
      progress.stage = 'second-page-or-frame';
      document = await assetAction(kind + ':2', 2,
        () => readerResponse(page, attachment, () => reader.getByRole('button', { name: 'Next', exact: true }).click()));
      validateReaderDocument(fixture, document, attachment);
      check(document.payload.page === 2, 'Next did not open the second physical page/frame.');
      const nextRaster = await raster(document.payload.asset_id);
      check(firstRaster.sha256 !== nextRaster.sha256, 'Changing page/frame returned the previous raster.');
      positions.push(await savedReaderPosition(page, chat, attachment, kind === 'pdf' ? { kind, physical_page: 2 } : { kind, frame: 2 }));
      check(await reader.getByLabel(kind === 'pdf' ? 'Physical page' : 'Image frame', { exact: true }).inputValue() === '2', 'Reader position control is stale.');
    }
    if (fixture.gate === 'reader-csv') {
      progress.stage = 'csv-next-rows';
      check(document.payload.table.total_rows === fixture.expect.rows && document.payload.table.first_row === 1, 'CSV dimensions changed.');
      document = await readerResponse(page, attachment, () => reader.getByRole('button', { name: 'Next rows', exact: true }).click());
      validateReaderDocument(fixture, document, attachment);
      check(document.payload.table.first_row === 101 && document.payload.table.rows.length === 6, 'CSV row window did not advance exactly.');
    }
    if (fixture.gate === 'reader-xlsx') {
      progress.stage = 'xlsx-sheet';
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
    progress.stage = 'document-table-and-images';
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
    progress.stage = 'passage-selection-and-draft';
    if (fixture.expect.text) selection = await selectReaderPassage(page, reader, fixture, attachment, document, chat);
    if (fixture.expect.error) await reader.getByText(/XML must be complete and contain no DTD or entity declarations/).waitFor();
    if (fixture.expect.kind === 'image') {
      check(await reader.getByRole('button', { name: /Discuss this passage|Ask about selected passage/ }).count() === 0,
        'Preview-only image exposed an extracted passage action.');
    }
    progress.stage = 'original-download';
    const original = await prepareReaderDownload(page, reader, chat, attachment, fixture, document, progress);
    let inert;
    progress.stage = 'inert-markup';
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
    progress.stage = 'screenshot';
    await screenshot(current, evidence, 'reader-' + fixture.filename.replaceAll('.', '-'));
    return { filename: fixture.filename, mediaType: fixture.media_type, attachmentId: attachment.id, attachment,
      original, previewState: document.preview_state, positions, selection,
      assets: assets.map(item => ({ assetId: item.assetId, ...validateReaderRaster(item.body), observation: item.observation })), inert,
      scope: 'Actual saved attachment, Workspace reader, guarded selection/draft and prepared original. No native Save dialog, model, OCR or ingestion claim.' };
  } finally {
    await page.context().unroute(fixtures.manifest.external_origin + '/**', deny);
  }
}

async function readerJourneys(current, chat, fixtures, evidence, report, pass) {
  report.readerFixtures = { ...fixtures.generator, manifest: fixtures.manifest };
  report.readerJourneys = [];
  for (const gate of readerGates) {
    const completed = [];
    let activeOriginal;
    try {
      for (const fixture of fixtures.manifest.files.filter(item => item.gate === gate)) {
        // Only a validated synthetic fixture filename and fixed phase names enter failure provenance.
        activeOriginal = { filename: fixture.filename, stage: 'starting' };
        const receipt = await readerFixtureJourney(current, chat, fixtures, fixture, evidence, activeOriginal);
        completed.push(receipt); report.readerJourneys.push({ gate, ...receipt });
      }
      check(completed.length > 0, 'An empty reader category cannot pass.');
      pass(gate, { originals: completed });
    } catch (error) {
      report.gates[gate] = { status: 'failed', error: safeFailure(error), failedOriginal: activeOriginal, completedOriginals: completed };
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
  await navigate(page, chatHash(chat));
  const progress = { filename: fixture.filename, stage: 'reopened-pdf-page2' };
  report.pdfReopenObservation = progress;
  const { actionResult: document, record: asset } = await readerBinaryAction(page, chat, attachment, fixture,
    { assetId: 'pdf:2', page: 2 }, () => readerResponse(page, attachment, async () => {
    if (!await page.getByLabel('Attach files to chat', { exact: true }).isVisible())
      await page.getByRole('button', { name: 'Attach file', exact: true }).click();
    // Opening the existing attachment preserves its stored locator. No preferences are injected.
    await page.locator('.chat-attached-file').filter({ hasText: fixture.filename })
      .getByRole('button', { name: 'Open file', exact: true }).click();
  }), progress);
  check(asset.headers['content-type'] === 'image/png', 'Reopened PDF asset is not its expected PNG raster.');
  const raster = validateReaderRaster(asset.body);
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

function validateIngestionIdentity(checkpoint, job) {
  check(job?.id === checkpoint.job.id && job.revision_id === checkpoint.revision_id
    && ['request_hash', 'idempotency_key', 'created_at'].every(name => typeof checkpoint.job[name] === 'string'
      && checkpoint.job[name].length > 0 && job[name] === checkpoint.job[name]),
  'Library ingestion changed its original job, revision or import command.');
}

export function validateActiveLibraryIngestion(checkpoint, job, queue) {
  validateIngestionIdentity(checkpoint, job);
  check(job.state === 'processing' && job.phase === 'extraction' && job.finished_at === null
    && queue?.running === true && queue.cpu_workers === 1 && queue.active_job === job.id && queue.error_code === null,
  'Actual matching Library extraction must be active immediately before ordinary window close.');
}

export function validateReopenedLibraryIngestion(checkpoint, status, document) {
  validateIngestionIdentity(checkpoint, status?.job);
  check(status.document_id === checkpoint.document_id && status.revision_id === checkpoint.revision_id
    && status.status === 'ready' && status.job.state === 'ready' && status.job.phase === 'complete'
    && status.job.error_code === null && Number.isFinite(Date.parse(checkpoint.reopenStartedAt))
    && Date.parse(status.job.finished_at) >= Date.parse(checkpoint.reopenStartedAt),
  'The same interrupted job must finish after the fresh installed reopen; an import completed before close cannot pass.');
  check(document?.id === checkpoint.document_id && document.title === checkpoint.title
    && document.status === 'ready' && document.latest_revision === checkpoint.revision_id && document.active_revision === checkpoint.revision_id
    && document.scope?.kind === 'personal-library' && document.scope.entity_id === null && document.reserved === false
    && document.cleanup_pending === false && document.revisions?.length === 1,
  'Reopen lost, replaced or duplicated the Library document/revision.');
  const revision = document.revisions[0];
  check(revision.id === checkpoint.revision_id && revision.document_id === checkpoint.document_id && revision.status === 'ready'
    && Number.isInteger(revision.passage_count) && revision.passage_count > 0
    && typeof revision.embedding_model === 'string' && revision.embedding_model.length > 0
    && ['display', 'cache', 'index', 'embedding', 'model_input'].every(name => revision.rights?.[name] === true),
  'The original Library revision has no actual indexed extraction or retained processing rights.');
  validateReaderOriginal(checkpoint.fixture, revision, revision.media_type);
  return revision;
}

export function validateIngestionPassage(checkpoint, passages, citation) {
  check(Array.isArray(passages), 'Actual Library retrieval must return passages.');
  const matches = passages.filter(row => row.document_id === checkpoint.document_id && row.document_revision === checkpoint.revision_id
    && row.title === checkpoint.title && typeof row.text === 'string' && row.text.includes(checkpoint.fixture.expect.text));
  check(matches.length > 0 && matches.every(row => typeof row.id === 'string' && Array.isArray(row.locators)
    && row.locators.some(locator => Number.isInteger(locator.page) && locator.page >= 1 && locator.page <= 2)),
  'Real retrieval did not return the synthetic PDF text with its original revision and physical-page provenance.');
  const hit = matches[0];
  if (citation !== undefined) {
    const page = hit.locators.find(locator => Number.isInteger(locator.page) && locator.page > 0).page;
    check(citation.document_id === checkpoint.document_id && citation.document_revision === checkpoint.revision_id
      && citation.title === checkpoint.title && citation.passage_id === hit.id && citation.page === page
      && isDeepStrictEqual(citation.locators, hit.locators.filter(locator => locator.page === page))
      && citation.original_url === '/api/v1/library/revisions/' + checkpoint.revision_id + '/original',
    'The mounted citation does not match the retrieved original passage/page.');
  }
  return hit;
}

async function beginLibraryIngestion(page, fixtures) {
  const fixture = fixtures.manifest.files.find(row => row.filename === 'synthetic-reading.pdf');
  check(fixture?.expect.kind === 'pdf' && fixture.expect.pages === 2, 'Use only the existing frozen two-page synthetic PDF.');
  const file = await checkedReaderOriginal(fixtures.directory, fixture);
  const title = 'DC21 synthetic ingestion ' + randomUUID().slice(0, 8);
  await navigate(page, '#/library');
  await page.getByRole('heading', { name: 'Your library', exact: true }).waitFor();
  await page.getByRole('button', { name: 'Add to library', exact: true }).click();
  await page.getByRole('button', { name: 'Document', exact: true }).click();
  await page.getByLabel('Title', { exact: true }).fill(title);
  await page.getByLabel('Choose a study document', { exact: true }).setInputFiles(file);
  await page.getByRole('checkbox', { name: 'I have permission to read, store, index and use this file for local learning.', exact: true }).check();
  const imported = await actionResponse(page, '/library/import/file',
    () => page.getByRole('button', { name: 'Add document', exact: true }).click(), 202);
  check(/^doc_[0-9a-f]{32}$/.test(imported.document_id ?? '') && /^rev_[0-9a-f]{32}$/.test(imported.revision_id ?? '')
    && /^ingest_[0-9a-f]{32}$/.test(imported.job?.id ?? '') && imported.job.revision_id === imported.revision_id,
  'Mounted Library import did not return its actual canonical document, revision and job.');
  const checkpoint = { ...imported, title, fixture };
  // Observe the production worker only. No delayed converter, paused route, substitute job or artificial workload.
  checkpoint.preClose = await poll(async () => {
    const [job, queue] = await Promise.all([api(page, '/library/jobs/' + imported.job.id), api(page, '/library/queue')]);
    validateIngestionIdentity(checkpoint, job);
    check(job.state === 'queued' || job.state === 'processing' && job.phase === 'extraction',
      'The real extraction window was missed or failed; normal-ingestion-close remains unproved.');
    return { job, queue, observedAt: new Date().toISOString() };
  }, snapshot => snapshot.job.state === 'processing' && snapshot.queue.active_job === imported.job.id,
  'Real active Library extraction', 30_000, 50);
  validateActiveLibraryIngestion(checkpoint, checkpoint.preClose.job, checkpoint.preClose.queue);
  return checkpoint;
}

async function verifyReopenedIngestion(page, checkpoint) {
  const status = await poll(async () => {
    const value = await api(page, '/library/documents/' + checkpoint.document_id + '/import-status');
    validateIngestionIdentity(checkpoint, value.job);
    check(value.document_id === checkpoint.document_id && value.revision_id === checkpoint.revision_id
      && ['queued', 'processing', 'ready'].includes(value.status), 'Reopened Library ingestion failed, disappeared or changed ownership.');
    return value;
  }, value => value.status === 'ready', 'Actual resumed extraction and indexing', 360_000);
  const document = await api(page, '/library/documents/' + checkpoint.document_id);
  const revision = validateReopenedLibraryIngestion(checkpoint, status, document);
  const downloaded = await page.evaluate(async route => {
    const response = await fetch(route);
    return { status: response.status, data: Array.from(new Uint8Array(await response.arrayBuffer())),
      mediaType: response.headers.get('content-type')?.split(';')[0], noSniff: response.headers.get('x-content-type-options') };
  }, '/api/v1/library/revisions/' + checkpoint.revision_id + '/original');
  check(downloaded.status === 200 && downloaded.noSniff === 'nosniff', 'The reopened Library original could not be downloaded safely.');
  const original = { sha256: sha(Buffer.from(downloaded.data)), bytes: downloaded.data.length };
  validateReaderOriginal(checkpoint.fixture, original, downloaded.mediaType);
  await navigate(page, '#/library');
  const row = page.getByRole('region', { name: 'Library document list', exact: true }).locator('.library-document')
    .filter({ has: page.getByRole('button', { name: checkpoint.title, exact: true }) });
  await row.getByText('Available', { exact: true }).waitFor();
  check(await row.count() === 1, 'The mounted Library lost or duplicated its imported document.');
  await page.getByLabel('Find a passage', { exact: true }).fill(checkpoint.fixture.expect.text);
  const retrieved = await actionResponse(page, '/library/retrieve',
    () => page.getByRole('button', { name: 'Search', exact: true }).click());
  const hit = validateIngestionPassage(checkpoint, retrieved.passages);
  const passage = page.locator('.library-passage').filter({ has: page.getByText(hit.text, { exact: true }) });
  const pending = captureResponse(page, response => {
    const url = new URL(response.url());
    return response.request().method() === 'GET' && url.pathname === '/api/v1/library/revisions/' + checkpoint.revision_id + '/citation'
      && url.searchParams.get('passage_id') === hit.id;
  }, { label: 'GET /library/revisions/{revision_id}/citation' });
  const [{ body: citation }] = await Promise.all([pending, passage.getByRole('button', { name: 'Inspect citation', exact: true }).click()]);
  validateIngestionPassage(checkpoint, retrieved.passages, citation);
  await page.getByRole('complementary', { name: 'Source reader', exact: true })
    .getByRole('heading', { name: checkpoint.title, exact: true }).waitFor();
  return { status, revision, original, passage: hit, citation, mountedAvailable: true };
}

const recoveryOldCommit = '1b30a89687cfcc5fb13b1cf824bbc43c19f870ed';
const recoveryPythonPaths = ['python/python314.zip', 'python', 'dependencies', 'dependencies/win32',
  'dependencies/win32/lib', 'dependencies/pywin32_system32', 'runtime', 'upstream/hermes', '.'];
const recoveryGateNames = ['identity-and-seed', 'legacy-upgrade-reopen', 'actual-current-producers',
  'json-restored', 'json-deletion-replay', 'zip1-restored', 'zip1-deletion-replay', 'zip2-restored', 'zip2-deletion-replay'];
const exactDigest = value => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);

export function validateRecoveryRequest(env, platform = process.platform) {
  const request = validateInstalledRequest(env, platform), file = env.RENULUS_RECOVERY_RECEIPT;
  check(typeof file === 'string' && path.isAbsolute(file) && !file.split(/[/\\]/).some(part => part === '.' || part === '..')
    && path.basename(file) === 'recovery-evidence.json', 'An absolute exact recovery-evidence.json path without traversal is required.');
  const evidence = path.dirname(file);
  check(samePath(path.dirname(evidence), designCEvidenceRoot) && /^r-[0-9a-f]{8}$/.test(path.basename(evidence)),
    'Recovery reopen accepts only the exact delivery/r-<8> root.');
  check(exactDigest(env.RENULUS_RECOVERY_RECEIPT_SHA256), 'An explicit recovery receipt SHA256 is required.');
  assertSyntheticEvidenceDirectory(file);
  const profile = path.join(evidence, 'u');
  check(profile.length <= 60, 'The upgraded profile exceeds the 60-character native bound.');
  return { ...request, evidence, profile, recoveryFile: file, recoverySha256: env.RENULUS_RECOVERY_RECEIPT_SHA256 };
}

/** Hash admission precedes parsing; callers cannot supply expected titles, IDs or a profile. */
export function parseRecoveryBytes(bytes, expected, maximum) {
  check(Buffer.isBuffer(bytes) && bytes.length <= maximum && exactDigest(expected) && sha(bytes) === expected,
    'Recovery input bytes differ from their bounded SHA256 identity.');
  return json(bytes);
}

export function validateRecoveryReceipt(request, receipt, identity, hashes) {
  check(receipt?.format === 'renulus-installed-recovery-evidence/1' && receipt.status === 'passed' && !receipt.error
    && receipt.external_provider_calls === 0 && receipt.old_commit === recoveryOldCommit
    && samePath(receipt.run_root, request.evidence) && exactDigest(receipt.seed_sha256)
    && recoveryGateNames.every(name => receipt.gates?.[name] && typeof receipt.gates[name] === 'object'
      && !Array.isArray(receipt.gates[name]) && Object.keys(receipt.gates[name]).length),
  'A complete successful Pauli recovery receipt for this exact synthetic root is required.');
  const claimed = receipt.identity, runtime = claimed?.runtime;
  check(claimed?.source_revision === request.revision && samePath(claimed.bundle, identity.backend)
    && samePath(path.dirname(path.dirname(path.dirname(identity.backend))), designCEvidenceRoot)
    && /^installed-[0-9a-f]{8}$/.test(path.basename(path.dirname(path.dirname(identity.backend))))
    && claimed.slot === request.slot && claimed.inventory?.files === identity.inventoryFiles
    && Number.isSafeInteger(claimed.inventory?.bytes) && claimed.inventory.bytes > 0,
  'Recovery source, installed bundle, inventory or assigned slot differs.');
  for (const name of ['bundle', 'inventory', 'python', 'driver']) {
    check(exactDigest(hashes[name]) && claimed[name + '_sha256'] === hashes[name], 'Recovery ' + name + ' identity differs.');
  }
  const driver = identity.driverHashes?.['verify-installed-recovery.py'];
  check(identity.productRevision === request.revision && identity.acceptanceRevision === request.acceptanceRevision
    && hashes.driver === driver?.frozenSha256 && hashes.driver === driver?.executedSha256,
  'Copied recovery driver differs from the exact acceptance freeze.');
  check(hashes.inventory === identity.actual.inventory && hashes.python === identity.bundle.python.executable_sha256,
    'Recovery hashes differ from the verified installation.');
  check(runtime?.platform === 'win32' && runtime.version === '3.14.4'
    && runtime.isolated === 1 && runtime.no_site === 1 && runtime.no_user_site === 1 && runtime.bytecode_disabled === true
    && samePath(runtime.executable, path.join(identity.backend, 'python/python.exe'))
    && samePath(runtime.prefix, path.join(identity.backend, 'python')) && samePath(runtime.base_prefix, runtime.prefix)
    && Array.isArray(runtime.sys_path) && runtime.sys_path.length === recoveryPythonPaths.length
    && runtime.sys_path.every((value, index) => samePath(value, path.join(identity.backend, recoveryPythonPaths[index]))),
  'Recovery was not executed with the exact isolated installed Python.');
}

export function validateRecoverySeed(request, seed) {
  check(seed?.format === 'renulus-installed-recovery-seed/1' && seed.old_commit === recoveryOldCommit
    && seed.synthetic === true && seed.closed === true && seed.schema_version === 1
    && samePath(seed.run_root, request.evidence) && samePath(seed.profile, request.profile)
    && isDeepStrictEqual(seed.exports, { json: 'old.json', zip1: 'old1.zip', zip2: 'old2.zip' })
    && ['old_source_archive_sha256', 'seed_driver_sha256', 'fixture_sha256'].every(name => exactDigest(seed[name])),
  'The hash-verified seed must bind the original closed synthetic schema1 u profile.');
  check(Array.isArray(seed.files) && seed.files.length >= 4 && seed.files.length <= 256, 'A bounded original seed inventory is required.');
  const names = new Set();
  let bytes = 0;
  for (const record of seed.files) {
    check(record && typeof record.path === 'string' && (['old.json', 'old1.zip', 'old2.zip'].includes(record.path)
      || record.path.startsWith('u/')) && record.path.split('/').every(part => /^[a-zA-Z0-9_.-]+$/.test(part)
        && !['.', '..'].includes(part) && !part.endsWith('.') && !/^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:[.]|$)/i.test(part))
      && !/(?:^|\/)(?:runtime|credentials?|secrets?|connections?)(?:\/|[.]|$)/i.test(record.path)
      && !/(?:-wal|-shm|[.]dpapi|[.]pem|[.]key|[.]token)$/.test(record.path) && !record.path.split('/').includes('.env')
      && !names.has(record.path.toLowerCase()) && Number.isSafeInteger(record.size) && record.size >= 0 && exactDigest(record.sha256),
    'Unsafe, duplicate or unbounded seed descriptor.');
    names.add(record.path.toLowerCase()); bytes += record.size;
  }
  check(bytes <= 32 * 1024 * 1024 && ['u/state/renulus.sqlite3', 'old.json', 'old1.zip', 'old2.zip'].every(name => names.has(name)),
    'The original closed database and exports must be present in the bounded seed.');
  return seed.files.find(record => record.path === 'old.json');
}

export function expectedRecoveryConversations(old) {
  check(old?.format === 'renulus-canonical-export' && old.schema_version === 1 && old.format_version === 1
    && Array.isArray(old.records?.learn_threads) && Array.isArray(old.records?.learn_messages)
    && Array.isArray(old.records?.case_sessions), 'A genuine schema1 canonical export with Learn and Case history is required.');
  const result = [], identities = new Set(), records = old.records;
  check(records.learn_threads.length > 0 && records.case_sessions.length > 0
    && records.learn_threads.length + records.case_sessions.length <= 100
    && records.learn_messages.length <= 10000, 'The original Learn/Case seed must be populated and bounded.');
  for (const [kind, rows] of [['learning', records.learn_threads], ['case', records.case_sessions]]) {
    for (const row of rows) {
      const type = kind === 'learning' ? 'learn_thread' : 'case';
      check(typeof row.id === 'string' && /^[a-zA-Z0-9_-]{1,128}$/.test(row.id)
        && typeof row.title === 'string' && row.title.length > 0 && row.title.length <= 120
        && !identities.has(type + ':' + row.id), 'Invalid or duplicate original conversation identity/title.');
      identities.add(type + ':' + row.id);
      const original = kind === 'learning' ? records.learn_messages.filter(item => item.thread_id === row.id) : JSON.parse(row.messages_json);
      check(Array.isArray(original) && original.length <= 10000, 'Unbounded original message history.');
      const ids = new Set();
      const messages = original.map(item => {
        check(typeof item.id === 'string' && !ids.has(item.id) && ['user', 'assistant'].includes(item.role)
          && typeof item.content === 'string' && typeof item.created_at === 'string', 'Invalid or duplicated original message.');
        ids.add(item.id);
        const message = structuredClone(item);
        if (kind === 'learning') {
          message.content_refs = JSON.parse(message.citations_json).filter(entry => 'content_ref' in entry).map(entry => entry.content_ref);
          delete message.thread_id; delete message.citations_json;
        } else {
          message.run_id ??= message.id; message.content_refs ??= [];
        }
        return message;
      }).sort((a, b) => a.created_at < b.created_at ? -1 : a.created_at > b.created_at ? 1 : a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
      result.push({ identity: { type, id: row.id }, kind, title: row.title, messages,
        legacyMessages: original, ...(kind === 'case' ? { caseText: row.case_text } : {}) });
    }
  }
  check(['learning', 'case'].every(kind => result.some(item => item.kind === kind && item.messages.length >= 2))
    && records.learn_messages.every(message => records.learn_threads.some(thread => thread.id === message.thread_id)),
  'Both original owners must contain multi-message history with no orphan Learn messages.');
  return result;
}

export function validateRecoveredConversation(expected, summary, messages) {
  check(isDeepStrictEqual(summary.identity, expected.identity) && summary.kind === expected.kind && summary.title === expected.title
    && summary.retention === 'saved' && summary.lifecycle === 'active' && summary.project_id === null,
  'Original saved identity/title/lifecycle changed or gained retroactive project membership.');
  check(isDeepStrictEqual(messages, expected.messages), 'Original canonical paged history changed, duplicated or was truncated.');
}

/** All pagination is read from the actual server, bounded and cycle-refusing. Small pages exercise cursor reads even with compact seeds. */
export async function readRecoveryPages(read, route, identity) {
  const items = [], cursors = new Set();
  let cursor = null, pages = 0;
  do {
    check(++pages <= 10000, 'Recovery history exceeded its page bound.');
    const page = await read(route + (route.includes('?') ? '&' : '?') + 'limit=1' + (cursor ? '&cursor=' + encodeURIComponent(cursor) : ''));
    check(Array.isArray(page.items) && page.items.length <= 1 && (page.next_cursor === null
      || typeof page.next_cursor === 'string' && page.next_cursor.length > 0 && page.next_cursor.length <= 4096),
    'Invalid recovery pagination response.');
    if (identity) check(isDeepStrictEqual(page.conversation, identity), 'Paged history crossed conversation ownership.');
    items.push(...page.items); cursor = page.next_cursor;
    if (cursor) { check(page.items.length === 1 && !cursors.has(cursor), 'Repeated or empty recovery cursor.'); cursors.add(cursor); }
  } while (cursor);
  return { items, pages };
}

async function readRecoveryFile(file, expected, maximum) {
  assertSyntheticEvidenceDirectory(file);
  const information = await lstat(file);
  check(information.isFile() && !information.isSymbolicLink() && information.size <= maximum, 'Missing or oversized recovery input.');
  return parseRecoveryBytes(await readFile(file), expected, maximum);
}

async function recoveredHistoryJourney(page, expected) {
  const listed = await readRecoveryPages(route => api(page, route), '/conversations'), proof = [];
  for (const item of expected) {
    const matches = listed.items.filter(row => isDeepStrictEqual(row.identity, item.identity));
    check(matches.length === 1, 'The saved list lost or duplicated an original conversation.');
    const route = chatPath(item), summary = await api(page, route);
    const history = await readRecoveryPages(route => api(page, route), route + '/messages', item.identity);
    validateRecoveredConversation(item, matches[0], history.items);
    validateRecoveredConversation(item, summary, history.items);
    const legacy = await api(page, item.kind === 'learning' ? '/learn/threads/' + item.identity.id : '/cases/sessions/' + item.identity.id);
    const originals = item.legacyMessages.map(message => {
      if (item.kind === 'case') return message;
      const { citations_json, ...rest } = message; return { ...rest, citations: JSON.parse(citations_json) };
    });
    // Legacy Learn also orders by created_at,id; Case preserves the stored array order.
    if (item.kind === 'learning') originals.sort((a, b) => a.created_at < b.created_at ? -1 : a.created_at > b.created_at ? 1 : a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
    check(legacy.id === item.identity.id && legacy.title === item.title && isDeepStrictEqual(legacy.messages, originals)
      && (item.kind !== 'case' || legacy.text === item.caseText && legacy.saved === true), 'The original legacy owner history changed.');
    await navigate(page, chatHash(item));
    await page.getByRole('heading', { level: 1, name: item.title, exact: true }).waitFor();
    const transcript = page.locator('.chat-transcript'), more = transcript.getByRole('button', { name: 'Load more history', exact: true });
    let uiPages = 1;
    while (await more.count()) {
      check(++uiPages <= Math.ceil(item.messages.length / 50), 'UI history pagination exceeded the original message count.');
      const previous = await transcript.locator('.chat-message').count();
      await more.click();
      await poll(() => transcript.locator('.chat-message').count(), count => count > previous, 'Actual UI history page', 30_000, 100);
    }
    const displayed = await transcript.locator('.chat-message').evaluateAll(elements => elements.map(element => ({
      role: element.classList.contains('chat-message-user') ? 'user' : 'assistant',
      content: element.querySelector('.chat-message-text')?.textContent,
    })));
    check(isDeepStrictEqual(displayed, item.messages.map(({ role, content }) => ({ role, content }))), 'The C renderer changed or truncated original history.');
    proof.push({ identity: item.identity, title: item.title, messages: history.items.length, apiPages: history.pages, uiPages,
      canonicalHistorySha256: sha(JSON.stringify(history.items)), legacyOwnerChecked: true });
  }
  return { listPages: listed.pages, conversations: proof };
}

export async function runInstalledRecoveryReopen() {
  const request = validateRecoveryRequest(process.env);
  nativeEvidenceRoot(designCEvidenceRoot);
  const receipt = await readRecoveryFile(request.recoveryFile, request.recoverySha256, 1024 * 1024);
  const identity = await verifyArtifacts(request);
  const hashes = { bundle: await hashFile(path.join(identity.backend, 'bundle.json')), inventory: identity.actual.inventory,
    python: await hashFile(path.join(identity.backend, 'python/python.exe')),
    driver: sha(git(['show', request.acceptanceRevision + ':apps/desktop/scripts/verify-installed-recovery.py'])) };
  validateRecoveryReceipt(request, receipt, identity, hashes);
  const seed = await readRecoveryFile(path.join(request.evidence, 'seed.json'), receipt.seed_sha256, 256 * 1024);
  const original = validateRecoverySeed(request, seed);
  const old = await readRecoveryFile(path.join(request.evidence, 'old.json'), original.sha256, original.size);
  check((await stat(path.join(request.evidence, 'old.json'))).size === original.size, 'Old export size differs from the frozen seed.');
  const expected = expectedRecoveryConversations(old);
  for (const [file, directory] of [[request.profile, true], [path.join(request.profile, 'state/renulus.sqlite3'), false]]) {
    assertSyntheticEvidenceDirectory(file);
    const entry = await lstat(file);
    check(directory ? entry.isDirectory() : entry.isFile(), 'The verified upgraded u profile must already exist.');
  }
  const claimFile = path.join(request.evidence, 'verify.claim');
  assertSyntheticEvidenceDirectory(claimFile);
  check((await lstat(claimFile)).size <= 4096, 'Oversized recovery ownership claim.');
  const claim = json(await readFile(claimFile)), env = isolatedEnvironment(process.env, request.evidence, request.profile);
  check(processIdentities([claim.pid], env).length === 0, 'The recovery owner must exit before Electron opens its profile.');
  const output = path.join(request.evidence, 'installed-recovery-reopen.json');
  assertSyntheticEvidenceDirectory(output);
  // Reserve before launch; a repeat/refusal never replaces either evidence receipt.
  const receiptOutput = await open(output, 'wx');
  const report = { kind: 'actual-installed-recovery-reopen-current-pc', status: 'running', checkedAt: new Date().toISOString(),
    slot: request.slot, sourceRevision: request.revision, acceptanceRevision: request.acceptanceRevision,
    executable: request.executable, evidence: request.evidence, profile: request.profile,
    recoveryReceipt: { path: request.recoveryFile, sha256: request.recoverySha256, seedSha256: receipt.seed_sha256, oldSha256: original.sha256 },
    identity, launches: [], shutdowns: [], histories: [],
    limits: ['Only the existing verified schema1-upgraded u is opened; no profile copy, new content or provider calls.',
      'Two hidden installed launches and ordinary closes complement the separately hashed recovery receipt.',
      'Reader, native dialogs, active ingestion and broader DC21 acceptance are not exercised by this runner.'] };
  let current;
  try {
    for (let pass = 0; pass < 2; pass++) {
      current = await launch(request, identity, request.evidence, 'u', report);
      report.histories.push(await recoveredHistoryJourney(current.page, expected));
      await normalClose(current, report); current = undefined; delete report.current;
    }
    check(report.shutdowns.length === 2 && report.shutdowns.every(row => row.normalWindowClose && row.ownedBackendObserved && row.remaining.length === 0),
      'Both upgraded-profile launches must terminate normally.');
    report.status = 'passed';
  } catch (error) {
    report.status = 'failed'; report.error = safeFailure(error); process.exitCode = 1;
  } finally {
    const owned = current ?? report.current;
    if (owned) {
      try {
        let timer;
        try { await Promise.race([owned.application.close(), new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('Owned recovery app cleanup exceeded 30 seconds.')), 30_000); })]); }
        finally { clearTimeout(timer); }
        report.failureCleanup = { attempted: true, identities: owned.identities };
      } catch (error) { report.cleanupError = error.message; process.exitCode = 1; }
    }
    delete report.current;
    report.finishedAt = new Date().toISOString();
    try { await receiptOutput.writeFile(JSON.stringify(report, null, 2)); }
    finally { await receiptOutput.close(); }
  }
  console.log(JSON.stringify({ evidence: output, status: report.status, error: report.error?.message }));
  return report;
}

export async function runInstalledProduct() {
  const request = validateInstalledRequest(process.env);
  // Published parent helper must accept exactly this root before any state is created.
  nativeEvidenceRoot(designCEvidenceRoot);
  const evidence = await createNativeEvidence('c');
  check(inside(designCEvidenceRoot, evidence), 'Generated proof left the Design C scratch root.');
  const report = { kind: 'actual-installed-product-current-pc', checkedAt: new Date().toISOString(),
    slot: request.slot, sourceRevision: request.revision, acceptanceRevision: request.acceptanceRevision, executable: request.executable, evidence,
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
    const ingestion = await beginLibraryIngestion(current.page, fixtures);
    ingestion.closeRequestedAt = new Date().toISOString();
    report.ingestion = ingestion; // Retain real pre-close observations even if close/recovery subsequently fails.
    ingestion.close = await normalClose(current, report); current = undefined; delete report.current;
    ingestion.reopenStartedAt = new Date().toISOString();
    current = await launch(request, identity, evidence, 'p', report);
    ingestion.reopened = await verifyReopenedIngestion(current.page, ingestion);
    pass('normal-ingestion-close', { ...ingestion,
      scope: 'Ordinary-window-close interruption/resume with observed active extraction and same-job completion after fresh reopen. Windows uses the existing owned backend termination; no graceful worker-drain claim.' });
    pass('final-close', await normalClose(current, report)); current = undefined; delete report.current;
    completeCoreReceipt(report); process.exitCode = 1;
  } catch (error) {
    report.status = 'failed'; report.error = safeFailure(error, temporaryPhase); process.exitCode = 1;
    await captureFailureScreenshot(current ?? report.current, evidence, report, temporaryPhase);
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
  else if (process.argv.length === 3 && process.argv[2] === '--recovery-reopen') await runInstalledRecoveryReopen();
  else throw new Error('Use --plan (read-only), --run or --recovery-reopen after the parent supplies the matching package and exact freeze/slot.');
}
