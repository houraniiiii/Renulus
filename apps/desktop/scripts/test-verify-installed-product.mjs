/** Deterministic acceptance boundaries only. No Electron, Python, helpers or provider launch. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { validateJourneyEntry } from './native-journeys.mjs';
import { installedAcceptancePlan, validateInstalledRequest, validateInstallationReceipts, isolatedEnvironment,
  validateCompleteReport, validateFrozenScript, validateProgrammeHandoff, requiredGates, remainingOwnedIdentities, inside,
  ingestionPdf, fixturePython } from './verify-installed-product.mjs';

const directory = path.dirname(fileURLToPath(import.meta.url));
const desktop = path.resolve(directory, '..');
const revision = 'a'.repeat(40), digest = 'b'.repeat(64);
const executable = path.join(desktop, 'release/installed-synthetic/Renulus Development.exe');
const requestEnv = () => ({ RENULUS_NATIVE_SLOT: 'parent-synthetic-slot', RENULUS_EXPECT_SOURCE_REVISION: revision,
  RENULUS_INSTALLED_PROOF: '1', RENULUS_PACKAGED_EXECUTABLE: executable,
  RENULUS_DELIVERY_PROVENANCE: path.join(desktop, 'release/matching-synthetic/delivery-provenance.json'),
  RENULUS_INSTALLER_EVIDENCE: path.join(desktop, 'release/proofs/installer-evidence.json') });
const receiptFixture = () => ({
  request: { revision, executable },
  delivery: { source_revision: revision, executable_sha256: digest, app_asar_sha256: digest,
    packaged_backend_inventory_sha256: digest, installers: [{ path: path.join(desktop, 'release/setup.exe'), sha256: digest }] },
  installation: { expectedSourceRevision: revision, installedSourceRevision: revision, installExitCode: 0,
    kind: 'unsigned-installer-extraction-only', installedExecutable: executable, target: path.dirname(executable),
    installer: path.join(desktop, 'release/setup.exe'), installedExecutableSha256: digest, installedAsarSha256: digest, installerSha256: digest },
  actual: { executable: digest, asar: digest, inventory: digest, installer: digest },
});
const validate = f => validateInstallationReceipts(f.request, f.delivery, f.installation, f.actual);

test('an explicit parent slot/freeze is required before either native mode', () => {
  assert.equal(validateJourneyEntry(['--installed-product'], requestEnv()), 'installed-product');
  assert.equal(validateJourneyEntry([], requestEnv()), 'declared-fixtures');
  for (const key of ['RENULUS_NATIVE_SLOT', 'RENULUS_EXPECT_SOURCE_REVISION']) {
    const env = requestEnv(); delete env[key];
    assert.throws(() => validateJourneyEntry([], env), /parent-assigned/);
    assert.throws(() => validateInstalledRequest(env, 'win32'), /parent|freeze/);
  }
  const env = requestEnv(); env.RENULUS_EXPECT_SOURCE_REVISION = 'HEAD';
  assert.throws(() => validateInstalledRequest(env, 'win32'), /immutable/);
  assert.throws(() => validateJourneyEntry(['--unknown'], requestEnv()), /argument/);
  assert.throws(() => validateJourneyEntry(['--installed-product', '--fixture'], requestEnv()), /argument/);
});

test('installed acceptance refuses supplied profiles, attached services and fixture/runtime overrides', () => {
  assert.equal(validateInstalledRequest(requestEnv(), 'win32').revision, revision);
  for (const key of ['RENULUS_PROFILE', 'RENULUS_SOURCE_DESKTOP', 'RENULUS_BACKEND_URL', 'RENULUS_SESSION_TOKEN',
    'RENULUS_PYTHON', 'RENULUS_TEST_ATTACH', 'RENULUS_PDF_FIXTURE_ONLY', 'RENULUS_FIXTURE_PYTHON']) {
    assert.throws(() => validateInstalledRequest({ ...requestEnv(), [key]: 'synthetic-override' }, 'win32'), /override/);
  }
  assert.throws(() => validateInstalledRequest(requestEnv(), 'linux'), /Windows/);
  assert.throws(() => validateInstalledRequest({ ...requestEnv(), RENULUS_INSTALLED_PROOF: '0' }, 'win32'), /actual installation/);
  assert.throws(() => validateInstalledRequest({ ...requestEnv(), RENULUS_PACKAGED_EXECUTABLE: 'relative.exe' }, 'win32'), /absolute/);
  assert.throws(() => validateInstalledRequest({ ...requestEnv(), RENULUS_NATIVE_EVIDENCE_ROOT: path.resolve('C:/Renulus-native-delivery/desktop-20261005/proofs') }, 'win32'), /backup-inspector/);
});

test('matching unsigned manufacture/extraction receipts are accepted without signing or VM conditions', () => {
  const f = receiptFixture(); f.installation.signature = 'NotSigned'; validate(f);
  const plan = installedAcceptancePlan();
  assert.match(plan.scope, /unsigned/i); assert.match(plan.scope, /optional future/);
  assert.ok(!requiredGates.some(name => /sign|clean|VM/i.test(name)));
});

test('a successful-looking but stale, partial or mismatched install cannot pass', () => {
  for (const mutate of [
    f => { f.delivery.source_revision = 'c'.repeat(40); },
    f => { f.installation.installedSourceRevision = 'c'.repeat(40); },
    f => { delete f.installation.installExitCode; },
    f => { f.installation.error = 'Synthetic interrupted installer'; },
    f => { f.installation.installedExecutable = executable + '.other'; },
    f => { f.installation.target = path.join(desktop, 'test-results'); },
    f => { f.delivery.installers.push({ ...f.delivery.installers[0] }); },
    f => { f.installation.installer = path.join(desktop, 'release/other-setup.exe'); },
    ...['executable', 'asar', 'inventory', 'installer'].map(key => f => { f.actual[key] = 'd'.repeat(64); }),
  ]) { const f = receiptFixture(); mutate(f); assert.throws(() => validate(f)); }
});

test('the executed harness must match the freeze, allowing only the declared PowerShell checkout line endings', () => {
  const source = Buffer.from('synthetic line one\nsynthetic line two\n');
  const windows = Buffer.from(source.toString().replaceAll('\n', '\r\n'));
  const hashes = validateFrozenScript('owned-dialog.ps1', source, windows);
  assert.notEqual(hashes.frozenSha256, hashes.executedSha256);
  assert.throws(() => validateFrozenScript('owned-dialog.ps1', source, Buffer.from('altered synthetic body\r\n')), /parent freeze/);
  assert.throws(() => validateFrozenScript('native-journeys.mjs', source, windows), /parent freeze/);
  assert.equal(validateFrozenScript('native-journeys.mjs', source, source).frozenSha256, hashes.frozenSha256);
});

test('Today handoff rejects general-track fallback, unavailable mapping and mismatched producer versions', () => {
  const fixture = () => ({ home: { goals: { track: 'eseneph' },
    selection: { track: 'esen_eph', status: 'ready', mapping_version: 'synthetic-version', topic_ids: ['synthetic-topic'] },
    tracks: [{ id: 'esen_eph', available: true, status: 'partial', version: 'synthetic-version', checked_on: '2026-10-05' }] },
    catalog: { track: 'esen_eph', complete_exam_available: false, available_families: 1,
      tracks: [{ id: 'esen_eph', available: true, exam_simulation_available: false }] }, selected: 'esen_eph' });
  const f = fixture(); assert.equal(validateProgrammeHandoff(f.home, f.catalog, f.selected).track, 'esen_eph');
  for (const mutate of [
    f => { f.home.goals.track = 'general'; }, f => { f.home.selection.track = 'general_nephrology'; },
    f => { f.home.selection.mapping_version = 'older-synthetic-version'; }, f => { f.home.selection.topic_ids = []; },
    f => { f.home.tracks[0].available = false; }, f => { f.catalog.track = 'general_nephrology'; },
    f => { f.catalog.complete_exam_available = true; }, f => { f.selected = 'general_nephrology'; },
  ]) { const changed = fixture(); mutate(changed); assert.throws(() => validateProgrammeHandoff(changed.home, changed.catalog, changed.selected)); }
});

test('synthetic child environment strips developer, Electron-as-Node and provider inputs', () => {
  const evidence = path.join(desktop, 'test-results/installed-product-synthetic');
  const env = isolatedEnvironment({ SystemRoot: 'C:/Windows', PATH: 'synthetic-developer-path',
    ELECTRON_RUN_AS_NODE: '1', RENULUS_SESSION_TOKEN: 'synthetic-token', OPENAI_API_KEY: 'synthetic-key',
    RENULUS_PYTHON: 'synthetic-python', RENULUS_PROFILE: 'synthetic-private-placeholder' }, evidence, path.join(evidence, 'profile'));
  assert.ok(env.PATH.includes('System32'));
  assert.ok(!env.PATH.includes('developer'));
  for (const key of ['ELECTRON_RUN_AS_NODE', 'RENULUS_SESSION_TOKEN', 'OPENAI_API_KEY', 'RENULUS_PYTHON']) assert.equal(env[key], undefined);
  assert.equal(env.RENULUS_PROFILE, path.join(evidence, 'profile'));
  assert.throws(() => isolatedEnvironment({ SystemRoot: 'C:/Windows' }, evidence, evidence), /newly owned/);
  assert.throws(() => isolatedEnvironment({ SystemRoot: 'C:/Windows' }, evidence, path.join(desktop, 'other-profile')), /newly owned/);
});

test('filesystem confinement rejects roots and siblings, while accepting an ordinary double-dot-prefixed filename', () => {
  const root = path.join(desktop, 'test-results');
  assert.equal(inside(root, path.join(root, 'proof/profile')), true);
  assert.equal(inside(root, path.join(root, '..synthetic')), true);
  assert.equal(inside(root, root), false);
  assert.equal(inside(root, path.join(desktop, 'test-results-other/profile')), false);
  assert.equal(inside(root, path.resolve(root, '../other')), false);
});

test('physical shutdown retains unknown/live ownership and distinguishes Windows PID reuse', () => {
  const owners = [{ pid: 12, executable, created: 'synthetic-creation-a' }];
  assert.deepEqual(remainingOwnedIdentities(owners, owners), owners);
  assert.deepEqual(remainingOwnedIdentities(owners, []), []);
  assert.deepEqual(remainingOwnedIdentities(owners, [{ pid: 12, executable, created: 'synthetic-creation-b' }]), []);
  assert.deepEqual(remainingOwnedIdentities(owners, [{ pid: 12, executable: executable + '.other', created: 'synthetic-creation-a' }]), []);
  assert.deepEqual(remainingOwnedIdentities(owners, [{ pid: 12, executable: null, created: null }]), owners);
});

test('partial gates, cleanup failures and an unproved normal close cannot be labelled passed', () => {
  const fixture = () => ({ kind: 'actual-installed-product-current-pc', sourceRevision: revision,
    gates: Object.fromEntries(requiredGates.map(name => [name, { status: 'passed', proof: { synthetic: true } }])),
    shutdowns: Array.from({ length: 3 }, () => ({ normalWindowClose: true, ownedBackendObserved: true, remaining: [] })) });
  validateCompleteReport(fixture());
  for (const name of requiredGates) {
    const f = fixture(); f.gates[name].status = 'not-run'; assert.throws(() => validateCompleteReport(f), /Every/);
    f.gates[name] = { status: 'passed' }; assert.throws(() => validateCompleteReport(f), /Every/);
    for (const proof of [{}, []]) { f.gates[name] = { status: 'passed', proof }; assert.throws(() => validateCompleteReport(f), /Every/); }
  }
  for (const mutate of [f => { f.error = { message: 'synthetic' }; }, f => { f.cleanupError = 'synthetic'; },
    f => { f.kind = 'declared-viewer-source-fixtures'; }, f => { f.shutdowns[0].remaining = [12]; },
    f => { f.shutdowns[1].ownedBackendObserved = false; }, f => { f.shutdowns[2].normalWindowClose = false; },
    f => { f.shutdowns.pop(); }]) { const f = fixture(); mutate(f); assert.throws(() => validateCompleteReport(f)); }
});

test('the enriched existing PDF remains a valid two-page byte fixture with exact stream lengths and xref', () => {
  const pdf = ingestionPdf().toString('ascii');
  assert.match(pdf, /\/Count 2/); assert.match(pdf, /RENULUS - PAGE TWO/);
  assert.match(pdf, /Synthetic PDF page two dialysis acceptance observation row 59/);
  for (const match of pdf.matchAll(/<< \/Length (\d+) >>\nstream\n([\s\S]*?)endstream/g)) {
    assert.equal(Number(match[1]), Buffer.byteLength(match[2]));
  }
  const xref = Number(pdf.match(/startxref\n(\d+)/)[1]); assert.equal(pdf.slice(xref, xref + 4), 'xref');
  const entries = pdf.slice(xref).split('\n').slice(3, 10);
  entries.forEach((entry, index) => assert.ok(pdf.slice(Number(entry.slice(0, 10))).startsWith((index + 1) + ' 0 obj\n')));
  assert.ok(!fixturePython.includes('\0'));
  assert.ok(fixturePython.includes('b"\\x89PNG\\r\\n\\x1a\\n"'));
});

test('--plan can run without a freeze, slot, dependencies or profile and never requests a live run', () => {
  const output = execFileSync(process.execPath, [path.join(directory, 'verify-installed-product.mjs'), '--plan'],
    { encoding: 'utf8', windowsHide: true, env: { SystemRoot: process.env.SystemRoot ?? 'C:/Windows',
      RENULUS_NATIVE_EVIDENCE_ROOT: 'synthetic-invalid-root-which-must-not-be-used' } });
  const plan = JSON.parse(output); assert.deepEqual(plan.requiredGates, requiredGates);
  assert.match(plan.parentChecks[0], /exclusive native\/helper slot/);
});
