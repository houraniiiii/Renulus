import './fixtures/gateway-environment.mjs';
import assert from 'node:assert/strict';
import test from 'node:test';
import { Cause, Effect, Option } from 'effect';
import { createLearningGateway } from '../src/learning-gateway.ts';
import { binding, plan, channel, result, currentResolved, nativePrimary } from './fixtures/gateway-environment.mjs';

test('the production learning adapter registers one native manifest and decodes images before one dispatch', async () => {
  const wire = channel(frame => {
    if (frame.command === 'model.prepare') return plan();
    if (frame.command === 'model.manifest') return { registered: true };
    if (frame.command === 'learning.validate_images') return { validated: true };
    assert.equal(frame.command, 'model.dispatch');
    return result();
  });
  const adapter = await createLearningGateway(wire.domain);
  try {
    const prepared = await Effect.runPromise(adapter.preparePrimary(binding, currentResolved()));
    const native = await nativePrimary(prepared.resolved, []);
    const request = await Effect.runPromise(prepared.prepare(native.prepared.request, native.prepared.options, native.unfiltered));
    assert.equal((await Effect.runPromise(adapter.client.generate(request))).text, 'Synthetic safe teaching');
    assert.deepEqual(wire.frames.map(frame => frame.command), [
      'model.prepare', 'model.manifest', 'learning.validate_images', 'model.dispatch',
    ]);
    assert.deepEqual(wire.frames[0].payload, {});
    const manifest = wire.frames[1].payload.manifest;
    assert.equal(manifest.version, 1);
    assert.equal(manifest.system, 'Synthetic post-hook teaching instruction');
    assert.equal(manifest.tools[0].name, 'eligible_passage');
    assert.equal(manifest.messages[0].content[1].type, 'image');
    assert.deepEqual(Object.keys(wire.frames[1].payload), ['manifest']);
    assert.ok(wire.frames.every(frame => frame.input_id === binding.input_id));
  } finally { await adapter.close(); }
});

test('production preparation preserves safe authentication rejection without a dispatch', async () => {
  const wire = channel(null);
  const adapter = await createLearningGateway(wire.domain);
  try {
    const pending = Effect.runPromiseExit(adapter.preparePrimary(binding, currentResolved()));
    while (!wire.frames.length) await new Promise(resolve => setImmediate(resolve));
    wire.settle(wire.frames[0], { outcome: 'rejected_before_admission',
      error: { code: 'authentication_required', status: 401, retryable: true } });
    const exit = await pending;
    assert.equal(exit._tag, 'Failure');
    const error = Option.getOrUndefined(Cause.findErrorOption(exit.cause));
    assert.equal(error.reason._tag, 'Authentication');
    assert.equal(error.reason.message, 'Reconnect the selected subscription.');
    assert.deepEqual(wire.frames.map(frame => frame.command), ['model.prepare']);
  } finally { await adapter.close(); }
});

test('a missing image decoder acknowledgement prevents native HTTP dispatch', async () => {
  const wire = channel(frame => {
    if (frame.command === 'model.prepare') return plan();
    if (frame.command === 'model.manifest') return { registered: true };
    assert.equal(frame.command, 'learning.validate_images');
    return { validated: false };
  });
  const adapter = await createLearningGateway(wire.domain);
  try {
    const primary = await Effect.runPromise(adapter.preparePrimary(binding, currentResolved()));
    const native = await nativePrimary(primary.resolved, []);
    const request = await Effect.runPromise(primary.prepare(native.prepared.request, native.prepared.options, native.unfiltered));
    await assert.rejects(Effect.runPromise(adapter.client.generate(request)));
    assert.deepEqual(wire.frames.map(frame => frame.command), [
      'model.prepare', 'model.manifest', 'learning.validate_images',
    ]);
    assert.equal(adapter.receipt(request), undefined);
  } finally { await adapter.close(); }
});
