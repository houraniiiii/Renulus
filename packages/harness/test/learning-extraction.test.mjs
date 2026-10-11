import './fixtures/gateway-environment.mjs';
import assert from 'node:assert/strict';
import test from 'node:test';
import { createLearningGateway } from '../src/learning-gateway.ts';
import { binding, plan, channel, result, sse } from './fixtures/gateway-environment.mjs';

const memoryPlan = () => plan('mimo-v2.6-pro', {
  role: { version: 'synthetic-version', purpose: 'memory-extraction', model_id: 'mimo-v2.6-pro', output_tokens: 64, dispatch_limit: 1 },
  native_capabilities: { tools: false, input: ['text'], output: ['text'] }, required_capabilities: ['text'],
});
async function frame(wire, command) {
  const deadline = Date.now() + 3000;
  while (Date.now() < deadline) {
    const found = wire.frames.find(item => item.command === command);
    if (found) return found;
    await new Promise(resolve => setTimeout(resolve, 2));
  }
  throw new Error('Expected authenticated callback was not observed.');
}

test('learning gateway uses one stateless plan and complete manifest before returning a consumed receipt', async () => {
  const wire = channel(null), gateway = await createLearningGateway(wire.domain);
  try {
    const work = gateway.generateExtraction(binding, { system: 'Extract general learning facts.', user: 'Synthetic educational answer.' }, new AbortController().signal);
    wire.reply(await frame(wire, 'model.prepare'), memoryPlan());
    const manifest = await frame(wire, 'model.manifest');
    assert.equal(manifest.payload.manifest.system, 'Extract general learning facts.');
    assert.deepEqual(manifest.payload.manifest.tools, []);
    assert.deepEqual(manifest.payload.manifest.messages, [{ role: 'user', content: [{ type: 'text', text: 'Synthetic educational answer.' }] }]);
    wire.reply(manifest, { registered: true });
    const dispatch = await frame(wire, 'model.dispatch');
    wire.reply(dispatch, result(sse('mimo-v2.6-pro', '{"memory":[]}')));
    const reply = await work;
    assert.equal(reply.text, '{"memory":[]}');
    assert.equal(reply.receipt.dispatch_id, dispatch.payload.dispatch_id);
    assert.equal(reply.receipt.permit_id, 'synthetic-permit');
    assert.deepEqual(wire.frames.filter(item => item.kind === 'domain_request').map(item => item.command), ['model.prepare', 'model.manifest', 'model.dispatch']);
  } finally { await gateway.close(); }
});

test('stateless dispatch returns the authenticated internal classification without diagnostic text', async () => {
  const wire = channel(null), gateway = await createLearningGateway(wire.domain);
  try {
    const work = gateway.generateExtraction(binding, { system: 'Extract facts.', user: 'Learning data.' }, new AbortController().signal);
    wire.reply(await frame(wire, 'model.prepare'), memoryPlan());
    wire.reply(await frame(wire, 'model.manifest'), { registered: true });
    wire.settle(await frame(wire, 'model.dispatch'), { outcome: 'uncertain_after_disconnect',
      error: { code: 'memory_answer_resolver_unavailable', status: 503, retryable: true } });
    assert.deepEqual(await work, { failure: { code: 'memory_answer_resolver_unavailable', status: 503, retryable: true } });
  } finally { await gateway.close(); }
});
