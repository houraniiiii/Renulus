import assert from 'node:assert/strict';
import test from 'node:test';
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { withStatelessExtractions } from '../src/extraction-host.ts';

const binding = Object.freeze({ operation_id: 'capture.1', attempt_id: '1',
  session_id: 'capture.scope.1', input_id: 'capture.input.1', cancellation_id: 'capture.1' });
const identity = Object.freeze({ operation_id: binding.operation_id, attempt_id: binding.attempt_id });
const input = { configuration_id: 'v1', binding, system: 'Extract general learning facts.', user: 'Learning data.' };
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
function native() {
  let closed = false;
  return { status: async () => ({ state: closed ? 'closed' : 'ready', configurationId: 'v1' }),
    close: async () => { closed = true; return { state: 'closed', outcome: 'cancelled_settled' }; },
    settled: async () => {}, inspect: async () => ({ registry_hash: 'synthetic' }) };
}
const bounds = { maxOperations: 2, maxInputChars: 1024 };

test('authenticated extraction controls cannot observe, cancel or release another attempt', async t => {
  const boot = { protocol: 'renulus-harness/1', profile_id: 'synthetic-profile',
    store_id: 'synthetic-store', generation: 'synthetic-generation', token: 'synthetic-token',
    root: 'G:/Renulus/scratch/oc-h02-h08/providers/extraction-attempt-identity',
    domain_store_id: 'synthetic-domain', domain_path: 'synthetic-domain.sqlite' };
  const child = spawn(process.execPath, ['--input-type=module', '--eval', `
    import { runHarnessIpc } from ${JSON.stringify(new URL('../src/ipc.ts', import.meta.url).href)};
    import { withStatelessExtractions } from ${JSON.stringify(new URL('../src/extraction-host.ts', import.meta.url).href)};
    let effects = 0, aborts = 0;
    await runHarnessIpc(async () => withStatelessExtractions({
      status: async () => ({ state: 'ready', configurationId: 'v1', effects, aborts }),
      close: async () => ({ state: 'closed', outcome: 'cancelled_settled' }),
      settled: async () => {}, inspect: async () => ({}),
    }, async (_binding, _input, signal) => {
      effects++;
      await new Promise(resolve => signal.addEventListener('abort', () => { aborts++; resolve(); }, { once: true }));
      return { text: '{}', receipt: { dispatch_id: 'dispatch1', permit_id: 'permit1' } };
    }, { maxOperations: 2, maxInputChars: 1024 }));
  `], { env: { ...process.env, RENULUS_HARNESS_BOOT: JSON.stringify(boot) }, stdio: ['pipe', 'pipe', 'pipe'] });
  const exited = new Promise((resolve, reject) => {
    child.once('error', reject); child.once('close', (code, signal) => resolve({ code, signal }));
  });
  let stderr = '';
  child.stderr.on('data', bytes => { stderr = (stderr + bytes.toString()).slice(-4096); });
  const bounded = async promise => {
    let timer;
    try { return await Promise.race([promise, new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error('synthetic IPC did not settle')), 5000);
    })]); } finally { clearTimeout(timer); }
  };
  t.after(async () => {
    child.stdin.end();
    try { await bounded(exited); }
    catch (error) { child.kill(); await exited; throw error; }
  });
  const ready = deferred(), replies = new Map();
  createInterface({ input: child.stdout }).on('line', line => {
    const frame = JSON.parse(line);
    if (frame.kind === 'ready') ready.resolve(frame);
    else if (frame.kind === 'reply') replies.get(frame.request_id)?.resolve(frame);
  });
  let requestId = 0;
  const request = (command, payload = {}, attemptId = '1') => {
    const request_id = `request.${++requestId}`;
    const reply = deferred(); replies.set(request_id, reply);
    child.stdin.write(JSON.stringify({ kind: 'request', ...boot, operation_id: 'capture.1',
      attempt_id: attemptId, request_id, command, payload }) + '\n');
    return bounded(reply.promise);
  };
  assert.equal((await bounded(ready.promise)).state, 'ready', stderr);
  const work = request('model.extract', input);
  let started;
  for (let observation = 0; observation < 8; observation++) {
    started = await request('host.status');
    if (started.result.effects === 1) break;
  }
  assert.equal(started.result.effects, 1);
  const wrongStatus = await request('model.extract.status', {}, '2');
  const wrongCancel = await request('model.extract.cancel', {}, '2');
  const wrongRelease = await request('model.extract.release', {}, '2');
  const progress = await request('host.status');
  const retained = await request('model.extract.status');
  assert.equal(progress.result.aborts, 0, 'the wrong attempt must not signal the active extraction');
  assert.equal(progress.result.effects, 1);
  assert.deepEqual(retained.result, { state: 'active' });
  for (const reply of [wrongStatus, wrongCancel, wrongRelease]) {
    assert.equal(reply.outcome, 'rejected_before_admission');
    assert.deepEqual(reply.error, { code: 'memory_extraction_identity_conflict' });
    assert.equal(reply.result, undefined);
  }
  const duplicate = await request('model.extract', { ...input, binding: { ...binding, attempt_id: '2' } }, '2');
  assert.deepEqual(duplicate.error, { code: 'memory_extraction_identity_conflict' });
  const activeRelease = await request('model.extract.release');
  assert.deepEqual(activeRelease.error, { code: 'memory_extraction_active' });
  assert.deepEqual((await request('model.extract.cancel')).result, { state: 'settled' });
  assert.deepEqual((await work).result, { failure: { code: 'memory_capture_cancelled', status: 409, retryable: false } });
  const settledRelease = await request('model.extract.release', {}, '2');
  assert.deepEqual(settledRelease.error, { code: 'memory_extraction_identity_conflict' });
  assert.deepEqual((await request('model.extract.status')).result, { state: 'settled' });
  assert.deepEqual((await request('model.extract.release')).result, { released: true });
  assert.deepEqual((await request('model.extract.status')).result, { state: 'unavailable' });
  assert.deepEqual((await request('host.status')).result, { state: 'ready', configurationId: 'v1', effects: 1, aborts: 1 });
  assert.deepEqual((await request('host.close')).result, { state: 'closed' });
  assert.deepEqual(await bounded(exited), { code: 0, signal: null });
  assert.equal(stderr, '');
});

test('Stop and close retain a stateless invocation until its real finalizer settles', async () => {
  const entered = deferred(), finalizer = deferred();
  let disposed = false, effects = 0;
  const original = native();
  const close = original.close;
  original.close = async () => { disposed = true; return close(); };
  const host = withStatelessExtractions(original, async (_binding, request, signal) => {
    effects++; assert.equal(request.system, input.system);
    entered.resolve();
    await new Promise(resolve => signal.addEventListener('abort', resolve, { once: true }));
    await finalizer.promise;
    throw new Error('synthetic private diagnostic');
  }, bounds);
  const work = host.extract(input);
  const observed = work.then(result => result.failure?.code ?? 'success', error => error.message);
  await entered.promise;
  const cancellation = host.cancelExtraction(identity);
  assert.equal(host.extractionStatus(identity).state, 'active');
  assert.equal((await host.close({ timeoutMs: 0 })).state, 'blocked');
  assert.equal(disposed, false);
  await assert.rejects(host.extract({ ...input, binding: { ...binding, operation_id: 'capture.2', cancellation_id: 'capture.2' } }), /harness_closing/);
  finalizer.resolve();
  await cancellation;
  await host.settled();
  assert.equal(await observed, 'memory_capture_cancelled');
  assert.equal(disposed, true);
  assert.equal(effects, 1);
  assert.equal(host.extractionStatus(identity).state, 'settled');
});

test('a stateless result requires a confirmed receipt and cannot replay its native operation', async () => {
  let effects = 0;
  const host = withStatelessExtractions(native(), async () => { effects++;
    return { text: '{"memory":[]}', receipt: { dispatch_id: 'dispatch1', permit_id: 'permit1' } };
  }, bounds);
  const result = await host.extract(input);
  assert.equal(result.text, '{"memory":[]}');
  assert.deepEqual(result.receipt, { dispatch_id: 'dispatch1', permit_id: 'permit1' });
  await assert.rejects(host.extract(input), /memory_extraction_identity_conflict/);
  assert.equal(effects, 1);
  host.releaseExtraction(identity);
  assert.equal(host.extractionStatus(identity).state, 'unavailable');
  await host.close();
});

test('native admission snapshots configuration and binding before awaited status', async () => {
  const gated = deferred();
  const original = native();
  original.status = async () => { await gated.promise; return { state: 'ready', configurationId: 'v1' }; };
  const mutable = structuredClone(input);
  const host = withStatelessExtractions(original, async admitted => {
    assert.deepEqual(admitted, binding);
    return { text: '{"memory":[]}', receipt: { dispatch_id: 'dispatch1', permit_id: 'permit1' } };
  }, bounds);
  const task = host.extract(mutable);
  mutable.configuration_id = 'changed'; mutable.binding.input_id = 'changed'; mutable.binding.attempt_id = '2';
  gated.resolve();
  assert.equal((await task).text, '{"memory":[]}');
  assert.equal(host.extractionStatus(identity).state, 'settled');
  assert.throws(() => host.extractionStatus({ ...identity, attempt_id: '2' }), /memory_extraction_identity_conflict/);
  await host.close();
});

test('authenticated failure classifications survive without accepting a success receipt', async () => {
  const host = withStatelessExtractions(native(), async () => ({
    failure: { code: 'memory_answer_resolver_unavailable', status: 503, retryable: true },
  }), bounds);
  assert.deepEqual(await host.extract(input), { failure: {
    code: 'memory_answer_resolver_unavailable', status: 503, retryable: true,
  } });
  assert.equal(host.extractionStatus(identity).state, 'settled');
  await host.close();
  const malformed = withStatelessExtractions(native(), async () => ({ text: 'private',
    receipt: { dispatch_id: 'dispatch1' } }), bounds);
  assert.deepEqual(await malformed.extract(input), { failure: { code: 'memory_extraction_failed', status: 503, retryable: true } });
  await malformed.close();
});

test('close owns a queued invocation and refuses it before any generation', async () => {
  let effects = 0;
  const host = withStatelessExtractions(native(), async () => { effects++;
    return { text: '{}', receipt: { dispatch_id: 'dispatch1', permit_id: 'permit1' } };
  }, bounds);
  const queued = host.extract(input);
  const result = queued.catch(error => error.message);
  await host.close();
  assert.equal(await result, 'harness_closing');
  assert.equal(host.extractionStatus(identity).state, 'settled');
  assert.equal(effects, 0);
});
