/** Deterministic acceptance boundaries only. No Electron, Python, helpers or provider launch. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash, webcrypto } from 'node:crypto';
import { runInNewContext } from 'node:vm';
import { installedAcceptancePlan, validateInstalledRequest, validateInstallationReceipts, isolatedEnvironment,
  validateCompleteReport, validateFrozenScript, validateFrozenExport, validateAcceptanceChanges, captureResponse, captureFailureScreenshot,
  installAttachmentCapture, freshHiddenFrame, captureHiddenWindow, hiddenScreenshotBytes,
  requiredGates, remainingOwnedIdentities, inside,
  coreGates, readerGates, deferredGates, completeCoreReceipt, designCEvidenceRoot, ownedArtifact, validateHiddenWindows, waitForDesignCWindow,
  validateConversation, validateSavedTest, validateActiveTest, validateFinalAttempt, validateAssistanceRefusal, safeFailure,
  validateReaderManifest, validateReaderOriginal, validateReaderDocument, validateReaderPassage, validateReaderRaster, validateBundledInterpreter,
  validateIsolatedDirectories, validateReopenedPdf, validateRecoveryRequest, parseRecoveryBytes,
  validateRecoveryReceipt, validateRecoverySeed, expectedRecoveryConversations, validateRecoveredConversation,
  readRecoveryPages, validateActiveLibraryIngestion, validateReopenedLibraryIngestion,
  validateIngestionPassage } from './verify-installed-product.mjs';

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

const captureRace = (binary = false) => {
  let resolveResponse, evicted = false;
  const events = [], expected = binary ? Buffer.from([0, 1, 255, 10, 13]) : { original: { sha256: digest }, page: 2 };
  const headers = { 'content-type': binary ? 'application/octet-stream' : 'application/json', 'cache-control': 'no-store' };
  const read = async () => {
    events.push('read-body');
    if (evicted) throw new Error('Request content was evicted from inspector cache');
    return expected;
  };
  const response = { status: () => 200, headers: () => headers, json: read, body: read };
  const page = { waitForResponse: () => new Promise(resolve => { resolveResponse = resolve; }) };
  const action = async () => {
    events.push('action-start'); resolveResponse(response);
    await Promise.resolve(); // Response continuation can consume bytes while the UI action is still pending.
    evicted = true; events.push('navigation');
  };
  return { page, action, response, events, expected, headers };
};

test('JSON response bytes are captured before action completion can evict them; old late ordering fails', async () => {
  const old = captureRace();
  const late = old.page.waitForResponse(() => true);
  const [response] = await Promise.all([late, old.action()]);
  await assert.rejects(response.json(), /evicted/);
  assert.deepEqual(old.events, ['action-start', 'navigation', 'read-body']);

  const current = captureRace();
  const pending = captureResponse(current.page, () => true, { label: 'POST /readers/resolve' });
  const [captured] = await Promise.all([pending, current.action()]);
  assert.deepEqual(current.events, ['action-start', 'read-body', 'navigation']);
  assert.deepEqual(captured.body, current.expected);
  assert.deepEqual(captured.headers, current.headers);
});

test('eager binary capture preserves the exact original bytes and response headers across action navigation', async () => {
  const current = captureRace(true);
  const pending = captureResponse(current.page, () => true, { binary: true, label: 'POST /readers/original' });
  const [captured] = await Promise.all([pending, current.action()]);
  assert.deepEqual(current.events, ['action-start', 'read-body', 'navigation']);
  assert.ok(Buffer.isBuffer(captured.body)); assert.deepEqual(captured.body, current.expected);
  assert.equal(hash(captured.body), hash(current.expected)); assert.deepEqual(captured.headers, current.headers);
});

test('early capture retains status and parse failures without a second request or substitute payload', async () => {
  let requests = 0, reads = 0;
  const page = response => ({ waitForResponse: async (_matches, options) => {
    requests++; assert.equal(options.timeout, 120_000); return response;
  } });
  await assert.rejects(captureResponse(page({ status: () => 409, json: () => { reads++; } }), () => true,
    { label: 'POST /readers/resolve' }), /readers\/resolve \(409\)/);
  assert.equal(reads, 0); assert.equal(requests, 1);
  const failure = new Error('invalid actual JSON');
  await assert.rejects(captureResponse(page({ status: () => 200, headers: () => ({}), json: async () => { reads++; throw failure; } }),
    () => true, { label: 'POST /readers/resolve' }), error => error.cause === failure && /readers\/resolve.*invalid actual JSON/.test(error.message));
  assert.equal(reads, 1); assert.equal(requests, 2);
  const empty = await captureResponse(page({ status: () => 204, headers: () => ({ 'cache-control': 'no-store' }), json: () => { reads++; } }),
    () => true, { expected: 204, label: 'DELETE /synthetic' });
  assert.equal(empty.body, null); assert.equal(reads, 1); assert.equal(requests, 3);
});

test('failure screenshot is skipped for temporary work or missing owned page before any app inspection', async () => {
  const current = { page: {}, application: { evaluate: () => { throw new Error('must not inspect temporary pixels'); } } };
  const report = { error: { message: 'primary failure' } }, before = structuredClone(report);
  for (const [owned, temporary] of [[current, true], [undefined, false], [{ page: null }, false]]) {
    await captureFailureScreenshot(owned, designCEvidenceRoot, report, temporary);
    assert.deepEqual(report, before);
  }
});

const hiddenCaptureFixture = () => {
  const events = [], png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=', 'base64');
  const url = 'http://127.0.0.1:12345/#/projects';
  const state = { visible: false, focused: false, focusable: false, destroyed: false, url, width: 1, height: 1 };
  const window = { isDestroyed: () => state.destroyed, isVisible: () => state.visible,
    isFocused: () => state.focused, isFocusable: () => state.focusable, webContents: { getURL: () => state.url },
    capturePage: async (rectangle, options) => {
      assert.equal(rectangle, undefined); assert.deepEqual(options, { stayHidden: true, stayAwake: false });
      events.push('capturePage');
      return { isEmpty: () => false, getSize: () => ({ width: state.width, height: state.height }), toPNG: () => png };
    } };
  const electron = { BrowserWindow: { getAllWindows: () => [window] } };
  const current = { executable: process.execPath, mainPid: process.pid,
    application: { evaluate: async (fn, input) => {
      events.push(fn === captureHiddenWindow ? 'capture-identity' : 'hidden-state'); return fn(electron, input);
    } }, page: { url: () => url, evaluate: async fn => { assert.equal(fn, freshHiddenFrame); events.push('fresh-frame'); } } };
  return { current, electron, window, state, events, png, expected: { url, executable: current.executable, pid: current.mainPid } };
};

test('hidden screenshots use BrowserWindow capturePage with false awake and before/after hidden checks', async () => {
  const f = hiddenCaptureFixture();
  assert.deepEqual(await hiddenScreenshotBytes(f.current), f.png);
  assert.deepEqual(f.events, ['hidden-state', 'fresh-frame', 'capture-identity', 'capturePage', 'hidden-state']);
});

test('fresh hidden frame waits for fonts then exactly two frames, and bounds an unready renderer', async () => {
  const events = []; let timeout;
  const context = { document: { fonts: { ready: Promise.resolve().then(() => events.push('fonts')) } },
    requestAnimationFrame: fn => { events.push('frame'); fn(); },
    setTimeout: (fn, milliseconds) => { assert.equal(milliseconds, 5_000); timeout = fn; return 1; },
    clearTimeout: id => { assert.equal(id, 1); events.push('clear-timeout'); } };
  const frame = runInNewContext('(' + freshHiddenFrame.toString() + ')', context);
  await frame(); assert.deepEqual(events, ['fonts', 'frame', 'frame', 'clear-timeout']);
  context.document.fonts.ready = new Promise(() => {});
  const pending = frame(); timeout(); await assert.rejects(pending, /five seconds/);
});

test('capture refuses wrong executable/PID/URL, visible/focusable windows and oversized PNG dimensions', async () => {
  for (const mutate of [f => { f.expected.executable += '.other'; }, f => { f.expected.pid++; },
    f => { f.expected.url += '/other'; }, f => { f.state.visible = true; }, f => { f.state.focused = true; },
    f => { f.state.focusable = true; }, f => { f.state.destroyed = true; }]) {
    const f = hiddenCaptureFixture(); mutate(f);
    await assert.rejects(captureHiddenWindow(f.electron, f.expected));
    assert.deepEqual(f.events, []);
  }
  const f = hiddenCaptureFixture(); f.state.width = 4097;
  await assert.rejects(captureHiddenWindow(f.electron, f.expected), /dimensions/);
  const changed = hiddenCaptureFixture();
  const capture = changed.window.capturePage;
  changed.window.capturePage = async (...args) => { const image = await capture(...args); changed.state.visible = true; return image; };
  await assert.rejects(hiddenScreenshotBytes(changed.current), /hidden and unfocused/);
  assert.equal(changed.events.at(-1), 'hidden-state');
});

test('failure screenshot errors remain secondary, with no page.screenshot or foreground fallback', async () => {
  const evidence = path.join(designCEvidenceRoot, 'c-12345678');
  const primary = { message: 'actual primary response failure' };
  const f = hiddenCaptureFixture(), current = f.current;
  f.window.capturePage = async () => { throw new Error('owned screenshot unavailable'); };
  const failed = { error: primary };
  await captureFailureScreenshot(current, evidence, failed, false);
  assert.equal(failed.failureScreenshot, undefined);
  assert.deepEqual(failed.failureScreenshotError, { message: 'owned screenshot unavailable' });
  assert.equal(failed.error, primary);
  assert.equal(f.events.at(-1), 'hidden-state');
  f.state.visible = true;
  const visible = { error: primary };
  await captureFailureScreenshot(current, evidence, visible, false);
  assert.match(visible.failureScreenshotError.message, /hidden and unfocused/);
  assert.equal(visible.error, primary);
});

const attachmentCaptureFixture = (t, options = {}) => {
  const bytes = Buffer.from('synthetic original only'), filename = 'synthetic-reading.pdf';
  const conversation = { type: 'learn_thread', id: 'thread_' + 'a'.repeat(32) };
  const spec = { origin: 'http://127.0.0.1:12345', hash: '#/chat/learn_thread/' + conversation.id,
    conversation, retention: 'saved', filename, bytes: bytes.length, sha256: hash(bytes) };
  const command = { conversation, filename, title: filename, idempotency_key: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    expected_conversation_revision: 1, expected_policy_revision: 0, expected_context_epoch: 0,
    rights: { display: true, cache: true }, metadata: { source_owner: 'Renulus synthetic fixture author' } };
  const headers = new Headers({ Accept: 'application/json', 'x-renulus-attachment-options': JSON.stringify(command) });
  const file = new File([bytes], filename), init = { method: 'POST', headers, body: file };
  const endpoint = spec.origin + '/api/v1/attachments', calls = [], events = [];
  const body = options.body ?? JSON.stringify({ original: { sha256: spec.sha256 }, retention: 'saved' });
  const response = new Response(body, { status: options.status ?? 201,
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store', ...options.headers } });
  Object.defineProperty(response, 'url', { value: options.url ?? endpoint });
  const clone = response.clone.bind(response);
  response.clone = () => { events.push('clone'); return clone(); };
  const pending = options.rejection ? Promise.reject(options.rejection) : Promise.resolve(response);
  const original = function (...args) { calls.push({ receiver: this, args }); return pending; };
  const context = { fetch: original, location: { origin: spec.origin, hash: spec.hash }, URL, File, Headers,
    Uint8Array, crypto: webcrypto, setTimeout, clearTimeout };
  const install = runInNewContext('(' + installAttachmentCapture.toString() + ')', context);
  const capture = install(spec); t.after(() => capture.dispose());
  return { spec, command, init, context, capture, install, endpoint, original, response, pending, calls, events };
};

test('single-use upload observer clones before UI consumption and preserves exact fetch promise/Response/args/this', async t => {
  const f = attachmentCaptureFixture(t), receiver = { owned: true }, args = [f.endpoint, f.init];
  const pending = Reflect.apply(f.context.fetch, receiver, args);
  assert.equal(pending, f.pending); assert.equal(f.context.fetch, f.original);
  const actual = await pending;
  assert.equal(actual, f.response); assert.deepEqual(f.events, ['clone']);
  const normalBody = await actual.json(), record = await f.capture.result;
  assert.deepEqual(JSON.parse(Buffer.from(record.bytes).toString()), normalBody);
  assert.equal(record.request.idempotency_key, f.command.idempotency_key);
  assert.equal(record.request.sha256, f.spec.sha256);
  assert.deepEqual(Object.keys(record.headers), ['content-type', 'cache-control', 'x-content-type-options', 'content-length']);
  assert.equal(f.calls.length, 1); assert.equal(f.calls[0].receiver, receiver);
  assert.equal(f.calls[0].args[0], args[0]); assert.equal(f.calls[0].args[1], args[1]);
  assert.equal(f.init.body.name, f.spec.filename);
  f.context.fetch(...args); await Promise.resolve();
  assert.equal(f.calls.length, 2); assert.deepEqual(f.events, ['clone']); // No second observation.
});

test('upload observer never clones nonmatching routes/owners/temporary inputs or credential-bearing requests', async t => {
  for (const mutate of [f => { f.endpoint += '?other=1'; }, f => { f.endpoint += '/other'; },
    f => { f.endpoint = f.endpoint.replace(':12345', ':54321'); }, f => { f.init.method = 'GET'; },
    f => { f.command.conversation = { type: 'learn_thread', id: 'tmp_other' }; },
    f => { f.command.idempotency_key = 'unbound'; }, f => { f.command.expected_policy_revision = -1; },
    f => { f.command.filename = 'private.pdf'; }, f => { f.command.title = 'private title'; },
    f => { f.command.rights.cache = false; }, f => { f.command.metadata.source_owner = 'Other'; },
    f => { f.init.body = new File(['different-size'], f.spec.filename); },
    f => { f.init.body = new Blob(['unclassified']); }, f => { f.context.location.hash = '#/chat/temporary'; },
    ...['Authorization', 'x-renulus-token', 'Cookie', 'X-Renulus-Study-Context'].map(name => f => { f.init.headers.set(name, 'not-observed'); })]) {
    const f = attachmentCaptureFixture(t); mutate(f);
    f.init.headers.set('x-renulus-attachment-options', JSON.stringify(f.command));
    const pending = f.context.fetch(f.endpoint, f.init);
    assert.equal(pending, f.pending); assert.equal(await pending, f.response);
    assert.deepEqual(f.events, []); assert.equal(f.calls.length, 1);
    f.capture.dispose(); await assert.rejects(f.capture.result, /disposed/);
    assert.equal(f.context.fetch, f.original);
  }
});

test('capture installation refuses unsaved or unbound synthetic scope before replacing fetch', async t => {
  const f = attachmentCaptureFixture(t); f.capture.dispose();
  for (const mutate of [s => { s.retention = 'temporary'; }, s => { s.origin = 'http://127.0.0.1:12346'; },
    s => { s.origin = 'https://example.invalid'; }, s => { s.filename = 'other.pdf'; },
    s => { s.sha256 = ''; }, s => { s.bytes = 65536; }, s => { s.conversation.type = 'case'; },
    s => { s.hash += '/other'; }, s => { s.conversation.id = 'tmp_private'; }]) {
    const spec = structuredClone(f.spec); mutate(spec);
    assert.throws(() => f.install(spec), /exact saved synthetic original/);
    assert.equal(f.context.fetch, f.original);
  }
});

test('capture refuses wrong response status/origin/headers and oversized bytes without altering the actual response', async t => {
  for (const options of [{ status: 409 }, { url: 'http://127.0.0.1:12345/other' },
    { headers: { 'content-type': 'text/html' } }, { headers: { 'cache-control': 'public' } },
    { headers: { 'content-length': '65537' } }, { body: 'a'.repeat(65537) }]) {
    const f = attachmentCaptureFixture(t, options);
    assert.equal(f.context.fetch(f.endpoint, f.init), f.pending);
    const actual = await f.pending, appText = await actual.text();
    await assert.rejects(f.capture.result, /Attachment /);
    assert.equal(appText, options.body ?? JSON.stringify({ original: { sha256: f.spec.sha256 }, retention: 'saved' }));
    assert.equal(f.calls.length, 1); assert.equal(f.context.fetch, f.original);
  }
});

test('wrong original SHA and fetch failure cannot substitute a body, retry or change original rejection', async t => {
  const wrong = attachmentCaptureFixture(t); wrong.spec.sha256 = 'f'.repeat(64);
  wrong.context.fetch(wrong.endpoint, wrong.init);
  await (await wrong.pending).json();
  await assert.rejects(wrong.capture.result, /SHA differs/);
  assert.equal(wrong.calls.length, 1);
  const error = new Error('synthetic transport failure'), failed = attachmentCaptureFixture(t, { rejection: error });
  const pending = failed.context.fetch(failed.endpoint, failed.init);
  assert.equal(pending, failed.pending); await assert.rejects(pending, value => value === error);
  await assert.rejects(failed.capture.result, /actual attachment fetch failed/);
  assert.equal(failed.calls.length, 1); assert.deepEqual(failed.events, []);
});

const ingestionFixture = () => {
  const checkpoint = { document_id: 'doc-unit', revision_id: 'rev-unit', title: 'Synthetic Library original',
    fixture: { filename: 'synthetic-reading.pdf', sha256: digest, bytes: 512, media_type: 'application/pdf',
      expect: { kind: 'pdf', pages: 2, text: 'Synthetic dialysis reading page two.' } },
    job: { id: 'ingest-unit', revision_id: 'rev-unit', request_hash: digest, idempotency_key: 'unit-import',
      created_at: '2026-10-10T12:00:00Z', state: 'queued', phase: 'queued', finished_at: null, error_code: null },
    reopenStartedAt: '2026-10-10T12:01:00Z' };
  const active = { ...checkpoint.job, state: 'processing', phase: 'extraction' };
  const queue = { running: true, cpu_workers: 1, active_job: active.id, error_code: null };
  const status = { document_id: checkpoint.document_id, revision_id: checkpoint.revision_id, status: 'ready',
    job: { ...checkpoint.job, state: 'ready', phase: 'complete', finished_at: '2026-10-10T12:01:20Z' } };
  const document = { id: checkpoint.document_id, title: checkpoint.title, status: 'ready', latest_revision: checkpoint.revision_id,
    active_revision: checkpoint.revision_id, scope: { kind: 'personal-library', entity_id: null }, reserved: false, cleanup_pending: false,
    revisions: [{ id: checkpoint.revision_id, document_id: checkpoint.document_id, status: 'ready', sha256: digest, bytes: 512,
      media_type: 'application/pdf', passage_count: 2, embedding_model: 'bundled-unit-model',
      rights: { display: true, cache: true, index: true, embedding: true, model_input: true } }] };
  const hit = { id: 'passage-unit', document_id: checkpoint.document_id, document_revision: checkpoint.revision_id,
    title: checkpoint.title, text: checkpoint.fixture.expect.text, locators: [{ page: 2, item_ref: '#/texts/1' }] };
  const citation = { document_id: checkpoint.document_id, document_revision: checkpoint.revision_id, title: checkpoint.title,
    passage_id: hit.id, page: 2, locators: hit.locators, original_url: '/api/v1/library/revisions/rev-unit/original' };
  return { checkpoint, active, queue, status, document, hit, citation };
};

test('ingestion-close requires an actual matching processing/extraction observation, never queued or already ready', () => {
  const f = ingestionFixture(); validateActiveLibraryIngestion(f.checkpoint, f.active, f.queue);
  for (const mutate of [v => { v.active.state = 'queued'; }, v => { v.active.state = 'ready'; },
    v => { v.active.phase = 'embedding'; }, v => { v.active.finished_at = '2026-10-10T12:00:30Z'; },
    ...['id', 'revision_id', 'request_hash', 'idempotency_key', 'created_at'].map(name => v => { v.active[name] = 'changed'; }),
    v => { v.queue.active_job = 'another-job'; }, v => { v.queue.running = false; },
    v => { v.queue.cpu_workers = 0; }, v => { v.queue.error_code = 'worker-failed'; }]) {
    const value = structuredClone(f); mutate(value);
    assert.throws(() => validateActiveLibraryIngestion(value.checkpoint, value.active, value.queue));
  }
});

test('reopened ingestion must finish the original command after fresh launch with unchanged indexed original', () => {
  const f = ingestionFixture(); validateReopenedLibraryIngestion(f.checkpoint, f.status, f.document);
  for (const mutate of [
    ...['id', 'revision_id', 'request_hash', 'idempotency_key', 'created_at'].map(name => v => { v.status.job[name] = 'changed'; }),
    v => { v.status.job.finished_at = '2026-10-10T12:00:30Z'; }, v => { v.status.job.finished_at = null; },
    v => { v.checkpoint.reopenStartedAt = undefined; }, v => { v.status.status = 'failed'; },
    v => { v.status.job.phase = 'embedding'; }, v => { v.status.job.error_code = 'failed'; },
    v => { v.status.document_id = 'other'; }, v => { v.document.latest_revision = 'replacement'; },
    v => { v.document.active_revision = null; }, v => { v.document.revisions.push(v.document.revisions[0]); },
    v => { v.document.revisions[0].passage_count = 0; }, v => { v.document.revisions[0].embedding_model = ''; },
    v => { v.document.revisions[0].sha256 = 'c'.repeat(64); }, v => { v.document.revisions[0].bytes++; },
    v => { v.document.revisions[0].rights.index = false; }, v => { v.document.cleanup_pending = true; }]) {
    const value = structuredClone(f); mutate(value);
    assert.throws(() => validateReopenedLibraryIngestion(value.checkpoint, value.status, value.document));
  }
});

test('actual ingestion retrieval and citation must pin original text, revision, passage and PDF page', () => {
  const f = ingestionFixture();
  assert.equal(validateIngestionPassage(f.checkpoint, [f.hit], f.citation), f.hit);
  assert.throws(() => validateIngestionPassage(f.checkpoint, []));
  for (const mutate of [v => { v.hit.document_revision = 'wrong'; }, v => { v.hit.document_id = 'wrong'; },
    v => { v.hit.text = 'Other text'; }, v => { v.hit.locators = []; }, v => { v.hit.locators[0].page = 3; },
    v => { v.citation.document_revision = 'wrong'; }, v => { v.citation.passage_id = 'wrong'; },
    v => { v.citation.page = 1; }, v => { v.citation.locators = []; },
    v => { v.citation.original_url = '/api/v1/library/revisions/wrong/original'; }]) {
    const value = structuredClone(f); mutate(value);
    assert.throws(() => validateIngestionPassage(value.checkpoint, [value.hit], value.citation));
  }
});

test('normal-ingestion-close is mandatory but no core receipt can pass without its executed flow', () => {
  assert.ok(coreGates.includes('normal-ingestion-close'));
  assert.equal(deferredGates['normal-ingestion-close'], undefined);
  assert.equal(requiredGates.filter(name => name === 'normal-ingestion-close').length, 1);
  const report = { gates: Object.fromEntries(coreGates.filter(name => name !== 'normal-ingestion-close')
    .map(name => [name, { status: 'passed', proof: { unitOnly: true } }])) };
  assert.throws(() => completeCoreReceipt(report), /core journey is incomplete/);
  assert.equal(report.gates['normal-ingestion-close'], undefined);
  assert.deepEqual(Object.keys(deferredGates), ['legacy-profile-upgrade', 'full-backup-restore', 'deletion-reconciliation', 'native-backup-save-cancel']);
});

const recoveryFixture = () => {
  const evidence = path.join(designCEvidenceRoot, 'r-0123abcd'), backend = path.join(designCEvidenceRoot, 'installed-0123abcd/resources/backend');
  const env = { ...requestEnv(), RENULUS_RECOVERY_RECEIPT: path.join(evidence, 'recovery-evidence.json'), RENULUS_RECOVERY_RECEIPT_SHA256: digest };
  const request = validateRecoveryRequest(env, 'win32');
  const identity = { backend, inventoryFiles: 1, actual: { inventory: digest }, bundle: { python: { executable_sha256: digest } },
    productRevision: request.revision, acceptanceRevision: request.acceptanceRevision,
    driverHashes: { 'verify-installed-recovery.py': { frozenSha256: digest, executedSha256: digest } } };
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

test('optional acceptance revision defaults to the product and accepts only an explicit immutable scalar SHA', () => {
  assert.equal(validateInstalledRequest(requestEnv(), 'win32').acceptanceRevision, revision);
  const acceptanceRevision = 'c'.repeat(40);
  const request = validateInstalledRequest({ ...requestEnv(), RENULUS_ACCEPTANCE_REVISION: acceptanceRevision }, 'win32');
  assert.equal(request.acceptanceRevision, acceptanceRevision);
  assert.equal(request.revision, revision);
  for (const value of ['', 'HEAD', 'c'.repeat(39), 'C'.repeat(40), 'g'.repeat(40), null, [], [acceptanceRevision], 123]) {
    assert.throws(() => validateInstalledRequest({ ...requestEnv(), RENULUS_ACCEPTANCE_REVISION: value }, 'win32'), /ACCEPTANCE_REVISION/);
  }
});

test('dual freeze permits only descendant exact product/recovery verifier/test and Markdown docs changes', () => {
  const acceptanceRevision = 'c'.repeat(40), changedPaths = [
    'apps/desktop/scripts/verify-installed-product.mjs', 'apps/desktop/scripts/test-verify-installed-product.mjs',
    'apps/desktop/scripts/verify-installed-recovery.py', 'apps/desktop/scripts/test_verify_installed_recovery.py',
    'docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md', 'docs/implementation/design-c-windows-review.md',
  ];
  assert.deepEqual(validateAcceptanceChanges(revision, acceptanceRevision, changedPaths, true),
    { productRevision: revision, acceptanceRevision, changedPaths });
  assert.deepEqual(validateAcceptanceChanges(revision, revision, [], true).changedPaths, []);
  for (const ancestor of [false, undefined, null, 1, 'true']) {
    assert.throws(() => validateAcceptanceChanges(revision, acceptanceRevision, changedPaths, ancestor), /ancestor/);
  }
  assert.throws(() => validateAcceptanceChanges(revision, revision, changedPaths, true), /single freeze/);
  assert.throws(() => validateAcceptanceChanges(revision, 'HEAD', changedPaths, true), /exact product/);
});

test('acceptance diff cannot admit runtime, renderer, native, packaging, dependencies or redirected paths', () => {
  for (const name of ['runtime/renulus/server.py', 'apps/desktop/src/App.tsx', 'apps/desktop/electron/main.cjs',
    'packaging/runtime/bundle.json', 'apps/desktop/scripts/stage-backend.py', 'apps/desktop/package.json',
    'package-lock.json', 'uv.lock', 'pyproject.toml', '.gitattributes', 'upstream/hermes/activate.ps1',
    'content/packs/test.json', 'apps/desktop/scripts/native-evidence-directory.mjs',
    'apps/desktop/scripts/design-c-reader-fixtures.py', 'apps/desktop/scripts/verify-installed-recovery-other.py',
    'apps/desktop/scripts/verify-installed-recovery.py/extra', 'apps/desktop/scripts/test_verify_installed_recovery_extra.py',
    'apps/desktop/scripts/verify-old-recovery-seed.py',
    'apps/desktop/scripts/verify-installed-product.mjs/extra', 'README.md', 'docs/build.mjs', 'docs/data.json',
    'docs/x.MD', 'docs/../runtime/hidden.md', 'docs//extra.md', 'docs/./extra.md', 'docs/C:/extra.md',
    'docs/..\\extra.md', 'docs-other/report.md', undefined, null, []]) {
    assert.throws(() => validateAcceptanceChanges(revision, 'c'.repeat(40), [name], true), /Acceptance-only/);
  }
  // --no-renames supplies both paths; a move into documentation cannot hide the removed product file.
  assert.throws(() => validateAcceptanceChanges(revision, 'c'.repeat(40),
    ['runtime/renulus/legacy.md', 'docs/legacy.md'], true), /Acceptance-only/);
});

test('QA revision never substitutes the product revision in install or recovery receipts', () => {
  const f = receiptFixture(); f.request.acceptanceRevision = 'c'.repeat(40); validate(f);
  f.delivery.source_revision = f.request.acceptanceRevision;
  assert.throws(() => validate(f), /exact freeze/);
  const recovery = recoveryFixture(); recovery.request.acceptanceRevision = 'c'.repeat(40);
  recovery.identity.acceptanceRevision = recovery.request.acceptanceRevision;
  validateRecoveryReceipt(recovery.request, recovery.receipt, recovery.identity, recovery.hashes);
  recovery.receipt.identity.source_revision = recovery.request.acceptanceRevision;
  assert.throws(() => validateRecoveryReceipt(recovery.request, recovery.receipt, recovery.identity, recovery.hashes));
});

test('copied recovery proof must match the acceptance driver, rejecting stale-product or arbitrary driver bytes', () => {
  const f = recoveryFixture(), productBytes = Buffer.from('synthetic old recovery driver\n');
  const acceptanceBytes = Buffer.from('synthetic corrected recovery driver\n'), expected = hash(acceptanceBytes);
  f.request.acceptanceRevision = 'c'.repeat(40); f.identity.acceptanceRevision = f.request.acceptanceRevision;
  f.identity.driverHashes['verify-installed-recovery.py'] = validateFrozenScript('verify-installed-recovery.py', acceptanceBytes, acceptanceBytes);
  f.hashes.driver = expected; f.receipt.identity.driver_sha256 = expected;
  validateRecoveryReceipt(f.request, f.receipt, f.identity, f.hashes);
  for (const bytes of [productBytes, Buffer.from('arbitrary replacement driver\n'),
    Buffer.from(acceptanceBytes.toString().replaceAll('\n', '\r\n'))]) {
    assert.throws(() => validateFrozenScript('verify-installed-recovery.py', acceptanceBytes, bytes), /parent freeze/);
    const receipt = structuredClone(f.receipt); receipt.identity.driver_sha256 = hash(bytes);
    assert.throws(() => validateRecoveryReceipt(f.request, receipt, f.identity, f.hashes), /driver identity/);
    // Matching caller-provided hashes still cannot replace the separately frozen acceptance source.
    assert.throws(() => validateRecoveryReceipt(f.request, receipt, f.identity, { ...f.hashes, driver: hash(bytes) }), /acceptance freeze/);
  }
  for (const change of [v => { v.acceptanceRevision = f.request.revision; },
    v => { v.productRevision = f.request.acceptanceRevision; }, v => { delete v.driverHashes; },
    v => { v.driverHashes['verify-installed-recovery.py'].executedSha256 = hash(productBytes); }]) {
    const identity = structuredClone(f.identity); change(identity);
    assert.throws(() => validateRecoveryReceipt(f.request, f.receipt, identity, f.hashes), /acceptance freeze/);
  }
});

const exportAttributes = () => ({ text: 'set', eol: 'crlf', filter: 'unspecified',
  'working-tree-encoding': 'unspecified', 'export-subst': 'unspecified' });
const exportedBytes = bytes => ({ size: bytes.length, sha256: hash(bytes) });

test('committed text/eol export transforms expected bytes only and records both exact digests', () => {
  const blob = Buffer.from('synthetic first\nsecond \u03b1\nlast'), before = Buffer.from(blob);
  const exported = Buffer.from('synthetic first\r\nsecond \u03b1\r\nlast'), attributes = exportAttributes();
  const result = validateFrozenExport('upstream/hermes/activate.ps1', blob, attributes, exportedBytes(exported));
  assert.deepEqual(blob, before);
  assert.deepEqual(result, { path: 'upstream/hermes/activate.ps1', attributes,
    blobSha256: hash(blob), exportSha256: hash(exported), exportBytes: exported.length });
  const lf = { ...attributes, eol: 'lf' };
  assert.equal(validateFrozenExport('source.py', blob, lf, exportedBytes(blob)).exportSha256, hash(blob));
  const binary = Buffer.from([0, 10, 255]);
  assert.equal(validateFrozenExport('original.bin', binary, { ...attributes, text: 'unset', eol: 'unspecified' },
    exportedBytes(binary)).exportSha256, hash(binary));
});

test('wrong content, LF or mixed installed line endings cannot pass a declared CRLF export', () => {
  const blob = Buffer.from('synthetic first\nsecond\n'), attributes = exportAttributes();
  for (const wrong of [blob, Buffer.from('synthetic first\r\nchanged\r\n'),
    Buffer.from('synthetic first\r\nsecond\n'), Buffer.from('synthetic first\r\r\nsecond\r\n'),
    Buffer.from('synthetic first\r\nsecond\r\n\r\n')]) {
    assert.throws(() => validateFrozenExport('source.ps1', blob, attributes, exportedBytes(wrong)), /exact frozen export/);
  }
  const exported = Buffer.from('synthetic first\r\nsecond\r\n');
  assert.throws(() => validateFrozenExport('source.ps1', blob, attributes,
    { size: exported.length - 1, sha256: hash(exported) }), /exact frozen export/);
  assert.throws(() => validateFrozenExport('source.ps1', blob, { ...attributes, eol: 'lf' },
    exportedBytes(exported)), /exact frozen export/);
});

test('source suffix never authorizes EOL conversion and undeclared transformations fail closed', () => {
  const blob = Buffer.from('synthetic\n'), exported = Buffer.from('synthetic\r\n');
  const attributes = exportAttributes();
  assert.throws(() => validateFrozenExport('source.ps1', blob, { ...attributes, eol: 'unspecified' },
    exportedBytes(exported)), /exact frozen export/);
  for (const changed of [{ text: 'auto' }, { text: 'unset' }, { eol: 'native' }, { filter: 'lfs' },
    { 'working-tree-encoding': 'UTF-16LE' }, { 'export-subst': 'set' }]) {
    assert.throws(() => validateFrozenExport('source.ps1', blob, { ...attributes, ...changed }, exportedBytes(exported)));
  }
  assert.throws(() => validateFrozenExport('source.ps1', blob, {}, exportedBytes(exported)), /Unsupported/);
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

test('active Test assistance refusal requires exactly the frozen 409 code and no-store response', () => {
  const refusal = { status: 409, code: 'assistance_restricted', cacheControl: 'no-store' };
  validateAssistanceRefusal(refusal);
  for (const changed of [
    ...[200, 401, 403, 422, 500, '409', undefined].map(status => ({ status })),
    ...['assistance_changed', 'forbidden', undefined].map(code => ({ code })),
    ...[undefined, null, '', 'no-cache', 'public', 'max-age=60'].map(cacheControl => ({ cacheControl })),
  ]) assert.throws(() => validateAssistanceRefusal({ ...refusal, ...changed }), /409 assistance_restricted and no-store/);
  assert.throws(() => validateAssistanceRefusal(null), /409 assistance_restricted and no-store/);
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

test('frozen embedded sys.path may include exact backend root, but prefix and Pillow must remain descendants', () => {
  const backend = path.join(designCEvidenceRoot, 'installed-aaaaaaaa/resources/backend');
  const value = { version: '3.14.4', isolated: 1, no_user_site: 1,
    prefix: path.join(backend, 'python'), base_prefix: path.join(backend, 'python'),
    paths: ['python/python314.zip', 'python', 'dependencies', 'dependencies/win32', 'dependencies/win32/lib',
      'dependencies/pywin32_system32', 'runtime', 'upstream/hermes', '.'].map(name => path.join(backend, name)),
    pillow: path.join(backend, 'dependencies/PIL/__init__.py') };
  validateBundledInterpreter(value, backend);
  assert.equal(inside(backend, backend), false); // The general containment guard remains strict.
  for (const replacement of ['', '.', '..', backend + '-sibling', path.dirname(backend),
    'C:/synthetic-outside/python', null, undefined, [], {}]) {
    assert.throws(() => validateBundledInterpreter({ ...value, paths: [...value.paths, replacement] }, backend));
  }
  for (const paths of [[], null, undefined, backend, {}]) {
    assert.throws(() => validateBundledInterpreter({ ...value, paths }, backend));
  }
  assert.throws(() => validateBundledInterpreter({ ...value, prefix: backend, base_prefix: backend }, backend));
  assert.throws(() => validateBundledInterpreter({ ...value, pillow: backend }, backend));
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
