/** Deterministic acceptance boundaries only. No Electron, Python, helpers or provider launch. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { installedAcceptancePlan, validateInstalledRequest, validateInstallationReceipts, isolatedEnvironment,
  validateCompleteReport, validateFrozenScript, requiredGates, remainingOwnedIdentities, inside,
  coreGates, readerGates, deferredGates, completeCoreReceipt, designCEvidenceRoot, ownedArtifact, validateHiddenWindows, waitForDesignCWindow,
  validateConversation, validateSavedTest, validateActiveTest, validateFinalAttempt, safeFailure,
  validateReaderManifest, validateReaderOriginal, validateReaderDocument, validateReaderPassage, validateReaderRaster, validateBundledInterpreter,
  validateIsolatedDirectories, validateReopenedPdf, validateRecoveryRequest, parseRecoveryBytes,
  validateRecoveryReceipt, validateRecoverySeed, expectedRecoveryConversations, validateRecoveredConversation,
  readRecoveryPages } from './verify-installed-product.mjs';

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
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const recoveryFixture = () => {
  const evidence = path.join(designCEvidenceRoot, 'r-0123abcd'), backend = path.join(designCEvidenceRoot, 'installed-0123abcd/resources/backend');
  const env = { ...requestEnv(), RENULUS_RECOVERY_RECEIPT: path.join(evidence, 'recovery-evidence.json'), RENULUS_RECOVERY_RECEIPT_SHA256: digest };
  const request = validateRecoveryRequest(env, 'win32');
  const identity = { backend, inventoryFiles: 1, actual: { inventory: digest }, bundle: { python: { executable_sha256: digest } } };
  const runtime = { platform: 'win32', version: '3.14.4', isolated: 1, no_site: 1, no_user_site: 1, bytecode_disabled: true,
    executable: path.join(backend, 'python/python.exe'), prefix: path.join(backend, 'python'), base_prefix: path.join(backend, 'python'),
    sys_path: ['python/python314.zip', 'python', 'dependencies', 'dependencies/win32', 'dependencies/win32/lib',
      'dependencies/pywin32_system32', 'runtime', 'upstream/hermes', '.'].map(name => path.join(backend, name)) };
  const receipt = { format: 'renulus-installed-recovery-evidence/1', status: 'passed', run_root: evidence, seed_sha256: digest,
    old_commit: '1b30a89687cfcc5fb13b1cf824bbc43c19f870ed', external_provider_calls: 0,
    identity: { source_revision: revision, bundle: backend, slot: request.slot, inventory: { files: 1, bytes: 100 }, runtime,
      bundle_sha256: digest, inventory_sha256: digest, python_sha256: digest, driver_sha256: digest },
    gates: Object.fromEntries(['identity-and-seed', 'legacy-upgrade-reopen', 'actual-current-producers', 'json-restored',
      'json-deletion-replay', 'zip1-restored', 'zip1-deletion-replay', 'zip2-restored', 'zip2-deletion-replay'].map(name => [name, { checked: true }])) };
  const seed = { format: 'renulus-installed-recovery-seed/1', old_commit: receipt.old_commit, run_root: evidence, profile: request.profile,
    synthetic: true, closed: true, schema_version: 1, old_source_archive_sha256: digest, seed_driver_sha256: digest, fixture_sha256: digest,
    exports: { json: 'old.json', zip1: 'old1.zip', zip2: 'old2.zip' },
    files: ['u/state/renulus.sqlite3', 'old.json', 'old1.zip', 'old2.zip'].map(name => ({ path: name, size: 100, sha256: digest })) };
  const messages = [{ id: 'm2', role: 'assistant', content: 'Synthetic second.\nExact bytes.', created_at: '2026-10-01T00:00:01Z' },
    { id: 'm1', role: 'user', content: 'Synthetic first.', created_at: '2026-10-01T00:00:00Z' }];
  const old = { format: 'renulus-canonical-export', format_version: 1, schema_version: 1, records: {
    learn_threads: [{ id: 'original_learn', title: 'Original synthetic Learn' }],
    learn_messages: messages.map(message => ({ ...message, thread_id: 'original_learn', run_id: 'original_run',
      citations_json: JSON.stringify([{ title: 'Legacy citation' }, { content_ref: { target: { type: 'library_revision', id: 'revision1' } } }]) })),
    case_sessions: [{ id: 'original_case', title: 'Original synthetic Case', case_text: 'Original synthetic vignette.',
      messages_json: JSON.stringify(messages) }],
  } };
  return { env, request, receipt, identity, seed, old, hashes: Object.fromEntries(['bundle', 'inventory', 'python', 'driver'].map(name => [name, digest])) };
};

test('recovery entry admits only the exact r root receipt plus explicit SHA256 and matching-package guards', () => {
  const { env, request } = recoveryFixture();
  assert.equal(request.profile, path.join(designCEvidenceRoot, 'r-0123abcd/u'));
  for (const file of [undefined, [], 'relative.json', path.join(designCEvidenceRoot, 'r-0123abcd/other.json'),
    path.join(designCEvidenceRoot, 'r-0123abcd/u/recovery-evidence.json'), path.join(designCEvidenceRoot, 'r-ABCDEF12/recovery-evidence.json'),
    path.join(designCEvidenceRoot, 'r-0123abcd') + '/../r-12345678/recovery-evidence.json', 'C:/synthetic-owner/recovery-evidence.json']) {
    assert.throws(() => validateRecoveryRequest({ ...env, RENULUS_RECOVERY_RECEIPT: file }, 'win32'));
  }
  for (const value of [undefined, 'a', 'A'.repeat(64), [], 'g'.repeat(64)]) {
    assert.throws(() => validateRecoveryRequest({ ...env, RENULUS_RECOVERY_RECEIPT_SHA256: value }, 'win32'), /SHA256/);
  }
  for (const name of ['RENULUS_PROFILE', 'RENULUS_BACKEND_URL', 'RENULUS_PYTHON']) {
    assert.throws(() => validateRecoveryRequest({ ...env, [name]: 'override' }, 'win32'), /override/);
  }
});

test('recovery JSON is admitted only after exact bounded byte hashes, including seed and old export', () => {
  const bytes = Buffer.from('{"status":"passed"}');
  assert.deepEqual(parseRecoveryBytes(bytes, hash(bytes), bytes.length), { status: 'passed' });
  assert.throws(() => parseRecoveryBytes(bytes, digest, bytes.length), /SHA256/);
  assert.throws(() => parseRecoveryBytes(bytes, hash(bytes), bytes.length - 1), /bounded/);
  assert.throws(() => parseRecoveryBytes(Buffer.from('invalid JSON'), digest, 100), /SHA256/);
  const { seed, old, receipt, request } = recoveryFixture();
  const oldBytes = Buffer.from(JSON.stringify(old)), descriptor = seed.files.find(row => row.path === 'old.json');
  Object.assign(descriptor, { size: oldBytes.length, sha256: hash(oldBytes) });
  const seedBytes = Buffer.from(JSON.stringify(seed)); receipt.seed_sha256 = hash(seedBytes);
  const admittedSeed = parseRecoveryBytes(seedBytes, receipt.seed_sha256, 256 * 1024);
  const admitted = validateRecoverySeed(request, admittedSeed);
  assert.equal(expectedRecoveryConversations(parseRecoveryBytes(oldBytes, admitted.sha256, admitted.size)).length, 2);
  assert.throws(() => parseRecoveryBytes(Buffer.concat([oldBytes, Buffer.from(' ')]), admitted.sha256, admitted.size + 1), /SHA256/);
});

test('a passed receipt cannot substitute source, bundle, inventory, driver, Python or incomplete recovery gates', () => {
  const f = recoveryFixture(); validateRecoveryReceipt(f.request, f.receipt, f.identity, f.hashes);
  for (const mutate of [r => { r.status = 'failed'; }, r => { r.external_provider_calls = 1; },
    r => { r.run_root += '-other'; }, r => { r.old_commit = revision; }, r => { r.seed_sha256 = 'invalid'; },
    r => { r.identity.source_revision = 'c'.repeat(40); }, r => { r.identity.bundle = 'C:/synthetic-owner'; },
    r => { r.identity.slot = 'other-slot'; }, r => { r.identity.inventory.files = 2; },
    ...['bundle', 'inventory', 'python', 'driver'].map(name => r => { r.identity[name + '_sha256'] = 'c'.repeat(64); }),
    ...['isolated', 'no_site', 'no_user_site'].map(name => r => { r.identity.runtime[name] = 0; }),
    r => { r.identity.runtime.executable = 'C:/synthetic-dev/python.exe'; }, r => { r.identity.runtime.bytecode_disabled = false; },
    r => { r.identity.runtime.sys_path.push('C:/synthetic-dev'); }, r => { r.identity.runtime.sys_path.reverse(); },
    ...Object.keys(f.receipt.gates).map(name => r => { delete r.gates[name]; })]) {
    const receipt = structuredClone(f.receipt); mutate(receipt);
    assert.throws(() => validateRecoveryReceipt(f.request, receipt, f.identity, f.hashes));
  }
});

test('hash-bound seed cannot redirect old export/profile or admit private/open-state inventory', () => {
  const f = recoveryFixture(); assert.equal(validateRecoverySeed(f.request, f.seed).path, 'old.json');
  for (const mutate of [s => { s.profile = 'C:/synthetic-owner'; }, s => { s.closed = false; },
    s => { s.synthetic = false; }, s => { s.schema_version = 2; }, s => { s.exports.json = '../other.json'; },
    s => { s.files.push({ ...s.files[0] }); }, s => { s.files[0].size = 33 * 1024 * 1024; },
    ...['u/../outside', 'u/con.txt', 'u/state/connections.dpapi', 'u/.env', 'u/state/renulus.sqlite3-wal',
      'u/state/credentials.json', 'u/state/secret.key', 'u//empty', 'u/C:/outside'].map(name => s => { s.files[0].path = name; })]) {
    const seed = structuredClone(f.seed); mutate(seed);
    assert.throws(() => validateRecoverySeed(f.request, seed));
  }
});

test('expected canonical histories come from original typed IDs and exact legacy fields, never caller descriptions', () => {
  const { old } = recoveryFixture(), original = structuredClone(old), expected = expectedRecoveryConversations(old);
  assert.deepEqual(old, original);
  assert.deepEqual(expected.map(row => row.identity), [{ type: 'learn_thread', id: 'original_learn' }, { type: 'case', id: 'original_case' }]);
  assert.deepEqual(expected[0].messages.map(row => row.id), ['m1', 'm2']);
  assert.equal(expected[0].messages[0].content_refs.length, 1);
  assert.equal(expected[1].messages[0].run_id, 'm1');
  assert.equal(expected[0].messages[1].content, 'Synthetic second.\nExact bytes.');
  for (const item of expected) {
    const summary = { identity: item.identity, kind: item.kind, title: item.title, retention: 'saved', lifecycle: 'active', project_id: null };
    validateRecoveredConversation(item, summary, item.messages);
    for (const change of [s => { s.title += 'changed'; }, s => { s.identity.id = 'new'; },
      s => { s.retention = 'temporary'; }, s => { s.project_id = 'retroactive'; }]) {
      const altered = structuredClone(summary); change(altered);
      assert.throws(() => validateRecoveredConversation(item, altered, item.messages));
    }
    for (const messages of [item.messages.slice(1), [...item.messages, item.messages[0]], [...item.messages].reverse(),
      item.messages.map((row, index) => index ? row : { ...row, content: row.content + ' ' })]) {
      assert.throws(() => validateRecoveredConversation(item, summary, messages));
    }
  }
  for (const change of [o => { o.schema_version = 2; }, o => { o.records.learn_threads[0].id = '../owner'; },
    o => { o.records.learn_threads.push(o.records.learn_threads[0]); },
    o => { o.records.learn_messages.push(o.records.learn_messages[0]); }, o => { o.records.case_sessions = []; }]) {
    const altered = structuredClone(old); change(altered); assert.throws(() => expectedRecoveryConversations(altered));
  }
});

test('read-only history collector actually follows opaque cursors and refuses cycles or cross-owner pages', async () => {
  const expected = expectedRecoveryConversations(recoveryFixture().old)[0], requests = [];
  const result = await readRecoveryPages(async route => {
    requests.push(route); const index = requests.length - 1;
    return { conversation: expected.identity, items: [expected.messages[index]], next_cursor: index ? null : 'opaque+/=' };
  }, '/conversations/learning/original_learn/messages', expected.identity);
  assert.deepEqual(result, { items: expected.messages, pages: 2 });
  assert.match(requests[0], /\?limit=1$/); assert.match(requests[1], /&cursor=opaque%2B%2F%3D$/);
  for (const value of [{ items: [], next_cursor: 'repeat' }, { items: [expected.messages[0]], next_cursor: 'repeat' },
    { items: [expected.messages[0]], next_cursor: null, conversation: { type: 'case', id: 'other' } },
    { items: [expected.messages[0], expected.messages[1]], next_cursor: null }, { items: [], next_cursor: undefined }]) {
    await assert.rejects(readRecoveryPages(async () => ({ conversation: expected.identity, ...value }), '/messages', expected.identity));
  }
});

test('the recovery CLI fails closed without a receipt hash before launching and remains a separate gate', () => {
  const f = recoveryFixture(), env = { ...process.env, ...f.env };
  delete env.RENULUS_RECOVERY_RECEIPT_SHA256;
  for (const name of ['RENULUS_PROFILE', 'RENULUS_BACKEND_URL', 'RENULUS_SESSION_TOKEN', 'RENULUS_PYTHON',
    'RENULUS_BACKGROUND_TEST', 'RENULUS_BACKGROUND_OWNER_PID']) delete env[name];
  assert.throws(() => execFileSync(process.execPath, [path.join(directory, 'verify-installed-product.mjs'), '--recovery-reopen'],
    { env, windowsHide: true, stdio: 'pipe' }), error => error.status === 1 && /receipt SHA256/.test(error.stderr.toString()));
  assert.equal(installedAcceptancePlan().recoveryReopen.command, '--recovery-reopen');
  assert.match(deferredGates['legacy-profile-upgrade'], /schema-1/);
});

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

test('PDF reopen requires the same page-2 text locator, original owner and rendered raster', () => {
  const { fixture, document, attachment } = readerFixture();
  const position = { kind: 'text', item_ref: 'reader-v1:pdf:2', start: 10, end: 16 };
  Object.assign(document.payload, { page: 2, blocks: [{ item_ref: position.item_ref, text: 'Synthetic SECOND page.' }] });
  const raster = { sha256: digest, width: 540, height: 360 };
  const checkpoint = { attachment, assets: [{ assetId: 'pdf:2', ...raster }],
    selection: { text: 'SECOND', reference: { target: document.reference.target, locator: position } } };
  validateReopenedPdf(fixture, checkpoint, document, position, raster);
  for (const mutate of [value => { value.document.payload.page = 1; }, value => { value.position = { kind: 'pdf', physical_page: 1 }; },
    value => { value.position.start = 0; }, value => { value.document.payload.blocks[0].text = 'Synthetic CHANGED page.'; },
    value => { value.document.original.sha256 = 'c'.repeat(64); }, value => { value.raster.sha256 = 'c'.repeat(64); },
    value => { value.raster.width = 1; }, value => { value.checkpoint.selection.reference.target.id = 'other-owner'; }]) {
    const value = structuredClone({ document, position, raster, checkpoint }); mutate(value);
    assert.throws(() => validateReopenedPdf(fixture, value.checkpoint, value.document, value.position, value.raster));
  }
  assert.ok(coreGates.includes('pdf-selection-reopen'));
  const plan = installedAcceptancePlan();
  for (const commit of ['f4fc986f', 'f5d36ac9']) assert.ok(plan.prerequisiteCommits.includes(commit));
});
