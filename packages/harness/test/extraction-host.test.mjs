import assert from 'node:assert/strict';
import test from 'node:test';
import { withStatelessExtractions } from '../src/extraction-host.ts';

const binding = Object.freeze({ operation_id: 'capture.1', attempt_id: '1',
  session_id: 'capture.scope.1', input_id: 'capture.input.1', cancellation_id: 'capture.1' });
const input = { configuration_id: 'v1', binding, system: 'Extract general learning facts.', user: 'Learning data.' };
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
function native() {
  let closed = false;
  return { status: async () => ({ state: closed ? 'closed' : 'ready', configurationId: 'v1' }),
    close: async () => { closed = true; return { state: 'closed', outcome: 'cancelled_settled' }; },
    settled: async () => {}, inspect: async () => ({ registry_hash: 'synthetic' }) };
}
const bounds = { maxOperations: 2, maxInputChars: 1024 };

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
  const cancellation = host.cancelExtraction(binding.operation_id);
  assert.equal(host.extractionStatus(binding.operation_id).state, 'active');
  assert.equal((await host.close({ timeoutMs: 0 })).state, 'blocked');
  assert.equal(disposed, false);
  await assert.rejects(host.extract({ ...input, binding: { ...binding, operation_id: 'capture.2', cancellation_id: 'capture.2' } }), /harness_closing/);
  finalizer.resolve();
  await cancellation;
  await host.settled();
  assert.equal(await observed, 'memory_capture_cancelled');
  assert.equal(disposed, true);
  assert.equal(effects, 1);
  assert.equal(host.extractionStatus(binding.operation_id).state, 'settled');
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
  host.releaseExtraction(binding.operation_id);
  assert.equal(host.extractionStatus(binding.operation_id).state, 'unavailable');
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
  mutable.configuration_id = 'changed'; mutable.binding.input_id = 'changed';
  gated.resolve();
  assert.equal((await task).text, '{"memory":[]}');
  await host.close();
});

test('authenticated failure classifications survive without accepting a success receipt', async () => {
  const host = withStatelessExtractions(native(), async () => ({
    failure: { code: 'memory_answer_resolver_unavailable', status: 503, retryable: true },
  }), bounds);
  assert.deepEqual(await host.extract(input), { failure: {
    code: 'memory_answer_resolver_unavailable', status: 503, retryable: true,
  } });
  assert.equal(host.extractionStatus(binding.operation_id).state, 'settled');
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
  assert.equal(host.extractionStatus(binding.operation_id).state, 'settled');
  assert.equal(effects, 0);
});
