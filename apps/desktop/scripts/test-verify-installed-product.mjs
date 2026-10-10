/** Deterministic acceptance boundaries only. No Electron, Python, helpers or provider launch. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { installedAcceptancePlan, validateInstalledRequest, validateInstallationReceipts, isolatedEnvironment,
  validateCompleteReport, validateFrozenScript, requiredGates, remainingOwnedIdentities, inside,
  coreGates, readerGates, deferredGates, completeCoreReceipt, designCEvidenceRoot, ownedArtifact, validateHiddenWindows, waitForDesignCWindow,
  validateConversation, validateSavedTest, validateActiveTest, validateFinalAttempt, safeFailure,
  validateReaderManifest, validateReaderOriginal, validateReaderDocument, validateReaderPassage, validateReaderRaster, validateBundledInterpreter,
  validateIsolatedDirectories } from './verify-installed-product.mjs';

const directory = path.dirname(fileURLToPath(import.meta.url));
const desktop = path.resolve(directory, '..');
const revision = 'a'.repeat(40), digest = 'b'.repeat(64);
const executable = path.join(desktop, 'release/installed-synthetic/Renulus Development.exe');
const requestEnv = () => ({ RENULUS_NATIVE_SLOT: 'parent-synthetic-slot', RENULUS_EXPECT_SOURCE_REVISION: revision,
  RENULUS_INSTALLED_PROOF: '1', RENULUS_PACKAGED_EXECUTABLE: executable, RENULUS_NATIVE_EVIDENCE_ROOT: designCEvidenceRoot,
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
  for (const key of ['RENULUS_NATIVE_SLOT', 'RENULUS_EXPECT_SOURCE_REVISION']) {
    const env = requestEnv(); delete env[key];
    assert.throws(() => validateInstalledRequest(env, 'win32'), /parent|freeze/);
  }
  const env = requestEnv(); env.RENULUS_EXPECT_SOURCE_REVISION = 'HEAD';
  assert.throws(() => validateInstalledRequest(env, 'win32'), /immutable/);
});

test('installed acceptance refuses supplied profiles, attached services and fixture/runtime overrides', () => {
  assert.equal(validateInstalledRequest(requestEnv(), 'win32').revision, revision);
  for (const key of ['RENULUS_PROFILE', 'RENULUS_SOURCE_DESKTOP', 'RENULUS_BACKEND_URL', 'RENULUS_SESSION_TOKEN',
    'RENULUS_PYTHON', 'RENULUS_TEST_ATTACH', 'RENULUS_PDF_FIXTURE_ONLY', 'RENULUS_FIXTURE_PYTHON', 'RENULUS_BACKGROUND_TEST', 'RENULUS_BACKGROUND_OWNER_PID']) {
    assert.throws(() => validateInstalledRequest({ ...requestEnv(), [key]: 'synthetic-override' }, 'win32'), /override/);
  }
  assert.throws(() => validateInstalledRequest(requestEnv(), 'linux'), /Windows/);
  assert.throws(() => validateInstalledRequest({ ...requestEnv(), RENULUS_INSTALLED_PROOF: '0' }, 'win32'), /actual installation/);
  assert.throws(() => validateInstalledRequest({ ...requestEnv(), RENULUS_PACKAGED_EXECUTABLE: 'relative.exe' }, 'win32'), /absolute/);
  assert.throws(() => validateInstalledRequest({ ...requestEnv(), RENULUS_NATIVE_EVIDENCE_ROOT: path.resolve('C:/Renulus-native-delivery/desktop-20261005/proofs') }, 'win32'), /exact synthetic/);
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

test('synthetic child environment strips developer, Electron-as-Node and provider inputs', () => {
  const evidence = path.join(designCEvidenceRoot, 'c-12345678');
  const env = isolatedEnvironment({ SystemRoot: 'C:/Windows', PATH: 'synthetic-developer-path',
    ELECTRON_RUN_AS_NODE: '1', RENULUS_SESSION_TOKEN: 'synthetic-token', OPENAI_API_KEY: 'synthetic-key',
    RENULUS_PYTHON: 'synthetic-python', RENULUS_PROFILE: 'synthetic-private-placeholder' }, evidence, path.join(evidence, 'profile'));
  assert.ok(env.PATH.includes('System32'));
  assert.ok(!env.PATH.includes('developer'));
  for (const key of ['ELECTRON_RUN_AS_NODE', 'RENULUS_SESSION_TOKEN', 'OPENAI_API_KEY', 'RENULUS_PYTHON']) assert.equal(env[key], undefined);
  assert.equal(env.RENULUS_PROFILE, path.join(evidence, 'profile'));
  assert.equal(env.RENULUS_BACKGROUND_TEST, '1');
  assert.equal(env.RENULUS_BACKGROUND_OWNER_PID, String(process.pid));
  assert.throws(() => isolatedEnvironment({ SystemRoot: 'C:/Windows' }, path.join(desktop, 'test-results/unit'), path.join(desktop, 'test-results/unit/profile')), /exact synthetic/);
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

test('inherited owner homes, AppData and cache paths are replaced with evidence-owned directories', () => {
  const evidence = path.join(designCEvidenceRoot, 'c-12345678'), profile = path.join(evidence, 'p');
  const inherited = { SystemRoot: 'C:/Windows', USERPROFILE: 'C:/synthetic-outside-owner', HOME: 'C:/synthetic-outside-owner',
    APPDATA: 'C:/synthetic-outside-owner/roaming', LOCALAPPDATA: 'C:/synthetic-outside-owner/local',
    ALLUSERSPROFILE: 'C:/synthetic-outside-common', PROGRAMDATA: 'C:/synthetic-outside-common',
    TEMP: 'C:/synthetic-outside-temp', TMP: 'C:/synthetic-outside-temp', XDG_CACHE_HOME: 'C:/synthetic-outside-cache',
    XDG_CONFIG_HOME: 'C:/synthetic-outside-config', XDG_DATA_HOME: 'C:/synthetic-outside-data',
    HF_HOME: 'C:/synthetic-outside-hf', TORCH_HOME: 'C:/synthetic-outside-torch',
    HOMEDRIVE: 'Z:', HOMEPATH: '\\synthetic-outside-home', userprofile: 'C:/synthetic-outside-lowercase' };
  const before = structuredClone(inherited);
  const env = isolatedEnvironment(inherited, evidence, profile);
  assert.deepEqual(inherited, before);
  for (const [name, suffix] of Object.entries({ USERPROFILE: 'h', HOME: 'h', LOCALAPPDATA: 'local', APPDATA: 'roaming',
    XDG_CACHE_HOME: 'local/cache', XDG_CONFIG_HOME: 'roaming', XDG_DATA_HOME: 'local',
    ALLUSERSPROFILE: 'local/common', PROGRAMDATA: 'local/common', RENULUS_PROFILE: 'p', TEMP: 't', TMP: 't' })) {
    assert.equal(env[name], path.join(evidence, suffix));
    assert.ok(inside(evidence, env[name]));
  }
  for (const name of ['HF_HOME', 'TORCH_HOME', 'HOMEDRIVE', 'HOMEPATH', 'userprofile']) assert.equal(env[name], undefined);
  assert.ok(!JSON.stringify(env).includes('synthetic-outside'));
  assert.equal(isolatedEnvironment({ SystemRoot: 'C:/Windows' }, evidence, profile).HOME, path.join(evidence, 'h'));
});

test('child directory assertion rejects escaped, missing and non-scalar user/cache/profile/temp paths', () => {
  const evidence = path.join(designCEvidenceRoot, 'c-12345678');
  const env = isolatedEnvironment({ SystemRoot: 'C:/Windows' }, evidence, path.join(evidence, 'p'));
  validateIsolatedDirectories(env, evidence);
  for (const name of ['USERPROFILE', 'HOME', 'LOCALAPPDATA', 'APPDATA', 'ALLUSERSPROFILE', 'PROGRAMDATA',
    'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'RENULUS_PROFILE', 'TEMP', 'TMP']) {
    for (const value of [undefined, null, [], { path: env[name] }, 'relative', evidence,
      evidence + '-sibling', path.join(evidence, '../outside')]) {
      assert.throws(() => validateIsolatedDirectories({ ...env, [name]: value }, evidence), /inside its fresh evidence/);
    }
  }
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

test('--plan can run without a freeze, slot, dependencies or profile and never requests a live run', () => {
  const output = execFileSync(process.execPath, [path.join(directory, 'verify-installed-product.mjs'), '--plan'],
    { encoding: 'utf8', windowsHide: true, env: { SystemRoot: process.env.SystemRoot ?? 'C:/Windows',
      RENULUS_NATIVE_EVIDENCE_ROOT: 'synthetic-invalid-root-which-must-not-be-used' } });
  const plan = JSON.parse(output); assert.deepEqual(plan.requiredGates, requiredGates);
  assert.match(plan.parentChecks[0], /exclusive native\/helper slot/);
});


test('only exercised readers pass; old-profile/recovery/native gaps keep the aggregate incomplete', () => {
  const report = { kind: 'actual-installed-product-current-pc', sourceRevision: revision,
    gates: Object.fromEntries(coreGates.map(name => [name, { status: 'passed', proof: { unitOnly: true } }])),
    shutdowns: Array.from({ length: 3 }, () => ({ normalWindowClose: true, ownedBackendObserved: true, remaining: [] })) };
  completeCoreReceipt(report);
  assert.equal(report.status, 'incomplete'); assert.equal(report.coreCompleted, true);
  assert.equal(readerGates.length, 8);
  assert.equal(report.readersCompleted, false);
  for (const name of readerGates) assert.equal(report.gates[name].status, 'not-run');
  for (const name of ['legacy-profile-upgrade', 'full-backup-restore', ...Object.keys(deferredGates)]) {
    assert.equal(report.gates[name].status, 'not-run'); assert.ok(report.gates[name].reason);
  }
  assert.throws(() => validateCompleteReport(report), /Every/);
  for (const name of readerGates) report.gates[name] = { status: 'passed', proof: { unitOnly: true } };
  completeCoreReceipt(report);
  assert.equal(report.readersCompleted, true);
  assert.deepEqual(report.pendingGates, Object.keys(deferredGates));
  assert.equal(report.status, 'incomplete');
  report.gates['legacy-profile-upgrade'] = { status: 'passed', proof: { unitOnly: true } };
  assert.throws(() => completeCoreReceipt(report), /cannot attest/);
});

test('Design C artifact scope accepts named public deliveries and rejects profile/sibling roots', async () => {
  for (const name of ['matching-aaaaaaaa/setup.exe', 'installed-aaaaaaaa/resources/backend/bundle.json', 'proofs/install/installer-evidence.json']) {
    await ownedArtifact(path.join(designCEvidenceRoot, name));
  }
  for (const value of [path.join(designCEvidenceRoot, 'profile/Renulus.exe'), designCEvidenceRoot,
    path.resolve('C:/Renulus/data/learning/Renulus.exe'), path.resolve(designCEvidenceRoot + '-other/installed-aaaaaaaa/Renulus.exe')]) {
    await assert.rejects(ownedArtifact(value), /owned|artifacts/);
  }
});

test('hidden C readiness accepts collapsed shell without Flow heading and rejects visible windows', async () => {
  const url = 'http://127.0.0.1:12345/#/newchat';
  const page = { isClosed: () => false, url: () => url, locator: selector => {
    assert.equal(selector, '.desktop-shell.design-c-shell'); return { count: async () => 1 };
  } };
  const windows = [{ url, visible: false, focused: false }];
  const application = { evaluate: async () => windows, windows: () => [page] };
  assert.equal((await waitForDesignCWindow(application, { timeout: 10 })).page, page);
  validateHiddenWindows(windows);
  for (const property of ['visible', 'focused']) {
    windows[0][property] = true;
    await assert.rejects(waitForDesignCWindow(application, { timeout: 10 }), /hidden and unfocused/);
    windows[0][property] = false;
  }
  await assert.rejects(waitForDesignCWindow({ ...application, windows: () => [{ ...page, url: () => 'https://example.test' }] }, { timeout: 1 }), /did not become ready/);
});

test('saved chat and set assertions reject temporary, wrong-owner and stale-version producer responses', () => {
  const chat = { identity: { type: 'learn_thread', id: 'learn-unit' }, kind: 'learning', retention: 'saved', lifecycle: 'active', project_id: 'project-unit', revision: 1 };
  validateConversation(chat, 'learning', 'project-unit');
  for (const mutate of [v => { v.retention = 'temporary'; }, v => { v.identity.type = 'case'; }, v => { v.project_id = null; }]) {
    const value = structuredClone(chat); mutate(value); assert.throws(() => validateConversation(value, 'learning', 'project-unit'));
  }
  const published = { test_id: 'test-unit', version_id: 'version-unit', item_count: 2 };
  const setup = { test: { id: published.test_id }, version: { id: published.version_id, origin: 'reviewed_bank', review_quality: 'reviewed', status: 'ready', item_count: 2 }, can_start: true };
  validateSavedTest(published, setup);
  for (const mutate of [v => { v.version.id = 'wrong'; }, v => { v.version.review_quality = 'personal'; }, v => { v.can_start = false; }, v => { v.version.item_count = 1; }]) {
    const value = structuredClone(setup); mutate(value); assert.throws(() => validateSavedTest(published, value));
  }
});

const activeAttempt = () => ({ id: 'attempt-unit', version_id: 'version-unit', mode: 'test', status: 'active', item_count: 2,
  origin: 'reviewed_bank', review_quality: 'reviewed', timing: { kind: 'untimed' },
  policy: { assistance_allowed: false, active_test_id: 'attempt-unit' }, committed: [], result: null,
  current_item: { item_id: 'item-unit', options: [{ id: 'a', text: 'Synthetic option' }] } });

test('whole Test assertions reject leaked keys/feedback, changed pins and incorrectly released policy', () => {
  validateActiveTest(activeAttempt(), 'version-unit');
  for (const mutate of [v => { v.id = 'wrong'; }, v => { v.version_id = 'wrong'; }, v => { v.committed = [{}]; },
    v => { v.result = {}; }, v => { v.current_item.options[0].correct = false; },
    v => { v.current_item.feedback = { explanation: 'unit leak' }; }, v => { v.current_item.correct_option_ids = ['a']; },
    v => { v.policy.assistance_allowed = true; }, v => { v.policy.active_test_id = null; }]) {
    const value = activeAttempt(); mutate(value); assert.throws(() => validateActiveTest(value, 'version-unit', 'attempt-unit'));
  }
});

test('final whole-attempt assertions distinguish committed Study from final Test drafts', () => {
  for (const mode of ['study', 'test']) {
    const value = activeAttempt(); value.mode = mode; value.status = mode === 'study' ? 'ended' : 'submitted';
    value.policy = { assistance_allowed: true, active_test_id: null };
    const entry = { commit_id: 'commit-unit', item_id: 'item-unit', question: { item_id: 'item-unit' }, selected_option_ids: ['a'], correct: true, feedback: { explanation: 'Unit-only explanation' } };
    value.result = { attempt_id: value.id, version_id: value.version_id, mode, origin: 'reviewed_bank', item_count: 2,
      excluded: 0, denominator: mode === 'study' ? 1 : 2, unanswered: mode === 'study' ? 0 : 1, not_submitted: mode === 'study' ? 1 : 0,
      correct: 1, items: mode === 'study' ? [entry] : [entry, { ...entry, commit_id: 'commit-2', correct: false, selected_option_ids: [] }] };
    validateFinalAttempt(value, mode, value.version_id);
    for (const mutate of [v => { v.result.version_id = 'wrong'; }, v => { v.result.denominator = 99; },
      v => { v.result.correct = 99; }, v => { v.result.not_submitted = 99; }, v => { v.policy.assistance_allowed = false; }]) {
      const changed = structuredClone(value); mutate(changed); assert.throws(() => validateFinalAttempt(changed, mode, value.version_id));
    }
  }
});


test('temporary failure receipts never include Playwright input text or ephemeral request identity', () => {
  const raw = new Error('Timeout filling TEMP-SYNTHETIC on /conversations/learning/tmp_unit');
  const receipt = safeFailure(raw, true);
  assert.ok(!JSON.stringify(receipt).includes('TEMP-SYNTHETIC'));
  assert.ok(!JSON.stringify(receipt).includes('tmp_unit'));
  assert.match(receipt.message, /withheld/);
  assert.deepEqual(safeFailure(new Error('Immutable artifact mismatch')), { message: 'Immutable artifact mismatch' });
});

test('compact installed helper profile paths fail before any launch when over 60 characters', () => {
  const root = path.join(designCEvidenceRoot, 'c-12345678');
  const profile = path.join(root, 'p');
  const env = isolatedEnvironment({ SystemRoot: 'C:/Windows' }, root, profile);
  assert.ok(profile.length <= 60);
  assert.equal(env.RENULUS_PROFILE, profile);
  assert.equal(env.TEMP, path.join(root, 't'));
  assert.throws(() => isolatedEnvironment({ SystemRoot: 'C:/Windows' }, root, path.join(root, 'profile-name-that-is-too-long')), /60 characters/);
});

test('fixture generation refuses a developer Pillow or interpreter path before importing the encoder', () => {
  const backend = path.join(designCEvidenceRoot, 'installed-aaaaaaaa/resources/backend');
  const value = { version: '3.14.4', isolated: 1, no_user_site: 1,
    prefix: path.join(backend, 'python'), base_prefix: path.join(backend, 'python'),
    paths: [path.join(backend, 'python/python314.zip'), path.join(backend, 'python/Lib/site-packages')],
    pillow: path.join(backend, 'python/Lib/site-packages/PIL/__init__.py') };
  validateBundledInterpreter(value, backend);
  for (const mutate of [v => { v.pillow = 'C:/Renulus/dev/python/Lib/site-packages/PIL/__init__.py'; },
    v => { v.paths.push('C:/Renulus/dev/repo'); }, v => { v.paths = []; }, v => { v.isolated = 0; },
    v => { v.no_user_site = 0; }, v => { v.prefix = v.base_prefix = 'C:/Renulus/dev/python'; }]) {
    const changed = structuredClone(value); mutate(changed); assert.throws(() => validateBundledInterpreter(changed, backend));
  }
});

const media = { pdf: 'application/pdf', docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  csv: 'text/csv', xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', md: 'text/markdown',
  html: 'text/html', xml: 'application/xml', png: 'image/png', jpg: 'image/jpeg', tiff: 'image/tiff' };
const manifestFixture = () => ({ schema: 'design-c-reader-fixtures/1', synthetic: true, pillow_version: 'unit-only',
  execution_marker: 'DC21_SYNTHETIC_SCRIPT_EXECUTED', external_origin: 'https://design-c-reader.invalid',
  files: [...Object.entries(media).map(([extension, media_type]) => ({ filename: 'synthetic-reading.' + extension, media_type,
    gate: 'reader-' + ({ md: 'markdown', png: 'images', jpg: 'images', tiff: 'images' }[extension] ?? extension),
    bytes: 100, sha256: digest, expect: { kind: 'text' } })),
  { filename: 'synthetic-denied-entity.xml', media_type: media.xml, gate: 'reader-xml', bytes: 100, sha256: digest, expect: { error: 'reader_xml_invalid' } }] });

test('reader originals require exact bounded names, eight categories and all three image encodings', () => {
  validateReaderManifest(manifestFixture());
  for (const mutate of [value => { value.files.pop(); }, value => { value.synthetic = false; },
    value => { value.external_origin = 'https://example.com'; }, value => { value.execution_marker = 'other'; },
    value => { value.files[0].filename = '../synthetic-reading.pdf'; }, value => { value.files[0].filename = 'C:/source.pdf'; },
    value => { value.files[0].filename = value.files[1].filename; }, value => { value.files[0].bytes = 0; },
    value => { value.files[0].bytes = 65536; }, value => { value.files[0].sha256 = 'invalid'; },
    value => { value.files[0].media_type = 'text/html'; }, value => { value.files[0].gate = 'reader-images'; }]) {
    const value = manifestFixture(); mutate(value); assert.throws(() => validateReaderManifest(value));
  }
});

const readerFixture = () => {
  const fixture = manifestFixture().files.find(row => row.filename.endsWith('.pdf'));
  fixture.expect = { kind: 'pdf', pages: 2 };
  const attachment = { id: 'attachment-unit', original: { id: 'original-unit' }, revision: 1 };
  const document = { schema_version: 'reader/1', reference: { target: { type: 'attachment', id: attachment.id } },
    media_type: fixture.media_type, title: 'Synthetic title',
    original: { id: attachment.original.id, filename: fixture.filename, bytes: fixture.bytes, sha256: fixture.sha256, available: true },
    attachment_revision: 1, policy_revision: 2, context_epoch: 3, preview_state: 'ready', error: null,
    capabilities: { read: true, original: true, passage: true, ocr: false, model_image: false },
    payload: { kind: 'pdf', page: 1, pages: 2 } };
  return { fixture, attachment, document };
};

test('reader acceptance pins original bytes, media, live attachment identity and policy', () => {
  const baseline = readerFixture();
  validateReaderDocument(baseline.fixture, baseline.document, baseline.attachment);
  for (const mutate of [value => { value.original.sha256 = 'c'.repeat(64); }, value => { value.original.bytes++; },
    value => { value.media_type = 'text/plain'; }, value => { value.reference.target.type = 'library_revision'; },
    value => { value.reference.target.id = 'wrong'; }, value => { value.original.id = 'wrong'; },
    value => { value.original.available = false; }, value => { value.original.filename = 'other.pdf'; },
    value => { value.policy_revision = 0; }, value => { value.context_epoch = -1; },
    value => { value.attachment_revision++; }, value => { value.preview_state = 'unsupported'; },
    value => { value.payload.pages = 1; }, value => { value.capabilities.passage = false; }]) {
    const { fixture, attachment, document } = readerFixture(); mutate(document);
    assert.throws(() => validateReaderDocument(fixture, document, attachment));
  }
  assert.throws(() => validateReaderOriginal(baseline.fixture, {}, baseline.fixture.media_type));
});

test('XML refusal keeps the original but cannot pass as a readable or selectable preview', () => {
  const { document, attachment } = readerFixture();
  const fixture = manifestFixture().files.at(-1);
  Object.assign(document, { media_type: fixture.media_type, preview_state: 'failed', error: { code: 'reader_xml_invalid' }, payload: null });
  Object.assign(document.original, { filename: fixture.filename });
  Object.assign(document.capabilities, { read: false, passage: false });
  validateReaderDocument(fixture, document, attachment);
  for (const mutate of [value => { value.capabilities.read = true; }, value => { value.capabilities.passage = true; },
    value => { value.error.code = 'reader_parse_failed'; }, value => { value.payload = { kind: 'text' }; }]) {
    const value = structuredClone(document); mutate(value); assert.throws(() => validateReaderDocument(fixture, value, attachment));
  }
});

test('image previews cannot be treated as OCR, model interpretation or extracted passages', () => {
  const { document, attachment } = readerFixture();
  const fixture = manifestFixture().files.find(row => row.filename.endsWith('.tiff'));
  fixture.expect = { kind: 'image', pages: 2 };
  Object.assign(document, { media_type: fixture.media_type, extraction_state: 'unavailable', payload: { kind: 'image', pages: 2 } });
  document.original.filename = fixture.filename; document.capabilities.passage = false;
  validateReaderDocument(fixture, document, attachment);
  for (const key of ['passage', 'ocr', 'model_image']) {
    const value = structuredClone(document); value.capabilities[key] = true;
    assert.throws(() => validateReaderDocument(fixture, value, attachment));
  }
});

test('passage proof requires exact returned text, typed source and actual locator', () => {
  const { fixture, document, attachment } = readerFixture();
  const locator = { kind: 'text', item_ref: 'reader-v1:pdf:2', start: 1, end: 10 };
  const passage = { title: document.title, text: 'Synthetic', reference: { target: document.reference.target, locator } };
  validateReaderPassage(fixture, attachment, document, passage, locator, 'Synthetic');
  for (const mutate of [value => { value.text = 'Other'; }, value => { value.title = 'Other'; },
    value => { value.reference.target.id = 'Other'; }, value => { value.reference.locator.start = 0; },
    value => { value.reference.locator.item_ref = 'reader-v1:pdf:1'; }]) {
    const value = structuredClone(passage); mutate(value);
    assert.throws(() => validateReaderPassage(fixture, attachment, document, value, locator, 'Synthetic'));
  }
});

test('asset receipt requires bounded raster PNG bytes rather than active original markup', () => {
  const data = Buffer.alloc(32);
  Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]).copy(data);
  data.write('IHDR', 12); data.writeUInt32BE(48, 16); data.writeUInt32BE(32, 20);
  const observed = validateReaderRaster(data);
  assert.equal(observed.width, 48); assert.equal(observed.height, 32);
  assert.throws(() => validateReaderRaster(Buffer.from('<html>not a PNG</html>')));
  data.writeUInt32BE(0, 16); assert.throws(() => validateReaderRaster(data));
  data.writeUInt32BE(12000000, 16); assert.throws(() => validateReaderRaster(data));
});
