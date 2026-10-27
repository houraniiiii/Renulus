// SPDX-License-Identifier: MIT
import '../../harness/test/fixtures/gateway-environment.mjs';
import assert from 'node:assert/strict';
import test from 'node:test';
import { createLearningGateway } from '../../harness/src/learning-gateway.ts';
import { binding, plan, channel, result, sse } from '../../harness/test/fixtures/gateway-environment.mjs';

test('explicit native generation purpose binds its exact manifest and refuses a mismatched memory-only entry', async () => {
  const frames = [];
  const wire = channel(frame => {
    frames.push(frame);
    if (frame.command === 'model.prepare') return plan('mimo-v2.6-pro', {
      role: { version: 'synthetic-version', purpose: 'generated-practice', model_id: 'mimo-v2.6-pro', output_tokens: 64, dispatch_limit: 6 },
      native_capabilities: { tools: false, input: ['text'], output: ['text'] }, required_capabilities: ['text'],
    });
    if (frame.command === 'model.manifest') return { registered: true };
    assert.equal(frame.command, 'model.dispatch'); return result(sse('mimo-v2.6-pro', '{"items":[]}'));
  });
  const gateway = await createLearningGateway(wire.domain);
  try {
    const input = { system: 'SYNTHETIC bounded generation.', user: 'SYNTHETIC nephrology practice.' };
    const response = await gateway.generateStandalone(binding, 'generated-practice', input, new AbortController().signal);
    assert.equal(response.text, '{"items":[]}');
    assert.deepEqual(frames.map(f => f.command), ['model.prepare', 'model.manifest', 'model.dispatch']);
    assert.equal(frames[1].payload.manifest.system, input.system);
    assert.deepEqual(frames[1].payload.manifest.tools, []);
    assert.deepEqual(frames[1].payload.manifest.messages, [{ role: 'user', content: [{ type: 'text', text: input.user }] }]);
    const rejected = await gateway.generateExtraction({ ...binding, operation_id: 'different-run', cancellation_id: 'different-run' }, input, new AbortController().signal);
    assert.ok('failure' in rejected);
    assert.equal(frames.filter(f => f.command === 'model.dispatch').length, 1);
  } finally { await gateway.close(); }
});
