// SPDX-License-Identifier: MIT
// TEST-ONLY synthetic deployment evidence and scripted fixture transport for standalone producers.
// Never imported by src/. The counter is a deterministic character estimate and is not account/tokenizer qualification.
import { routeFor } from '../../src/dispatch/policy.ts';

export function syntheticEvidence(connection, model) {
  const calls = { counted: 0 };
  const evidence = Object.freeze({
    metadata: { id: 'synthetic_scripted_route', route: routeFor(connection, model), limits: { input_tokens: 49152, output_tokens: 4096, window_tokens: 57344 },
      capabilities: ['text'], limits_revision: 'synthetic_limits', capabilities_revision: 'synthetic_entitlement', counter_revision: 'synthetic_chars_div_4' },
    count: async body => { calls.counted++; return Math.ceil(body.length / 4); },
  });
  return { evidence, calls };
}

/** Each admitted request consumes the next scripted text and answers as a codex (responses) stream. */
export function scriptedTransport(model) {
  const script = [], sent = [];
  const transport = { fixtureOnly: true, async send({ permit, serialized }) {
    const text = script.shift();
    if (text === undefined) throw Object.assign(new Error('script exhausted'), { code: 'synthetic_script_exhausted' });
    sent.push({ permit_id: permit.permit_id, request: JSON.parse(Buffer.from(serialized.body_base64, 'base64')) });
    const events = [
      { type: 'response.output_item.added', item: { type: 'message', id: 'm' } },
      { type: 'response.output_text.delta', item_id: 'm', delta: text },
      { type: 'response.output_item.done', item: { type: 'message', id: 'm', content: [{ type: 'output_text', text }] } },
      { type: 'response.completed', response: { id: 'r', model, status: 'completed' } },
    ];
    return { status: 200, headers: { 'content-type': 'text/event-stream' }, result_reference: 'receipt_' + permit.permit_id.replaceAll(/[^A-Za-z0-9_-]/g, ''),
      body_base64: Buffer.from(events.map(e => 'data: ' + JSON.stringify(e) + '\n\n').join('')).toString('base64') };
  } };
  return { transport, sent, push: (...texts) => { script.push(...texts); } };
}
