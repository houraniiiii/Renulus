// SPDX-License-Identifier: MIT
import type { DomainClient, DomainBinding } from './domain-ipc.ts';
import { openHarness, type HarnessOptions } from './host.ts';
import type { LibraryToolBridge, LibraryToolEnvelope } from './domain-tools.ts';

/** Both authority and consumed evidence are owned by the canonical Python run. */
export async function openLearningHarness(options: HarnessOptions, domain: DomainClient) {
  let host: Awaited<ReturnType<typeof openHarness>>;
  const request = async (binding: DomainBinding, command: string, payload: Readonly<Record<string, unknown>>, signal?: AbortSignal) => {
    const outcome = await domain.request(binding, command, payload, { signal });
    if (outcome.outcome !== 'committed_reference' || !outcome.result) throw new Error('learning_domain_unavailable');
    return outcome.result;
  };
  const library: LibraryToolBridge = {
    async resolve(context, signal) {
      return await request(host.binding(context.sessionID), 'learning.authority', {}, signal) as unknown as LibraryToolEnvelope;
    },
    async check(envelope, _stage, signal) {
      await request(host.binding(envelope.sessionId), 'learning.check', {}, signal);
    },
    async execute(command, arguments_, envelope, signal) {
      return await request(host.binding(envelope.sessionId), command, { command, arguments: arguments_, envelope }, signal) as never;
    },
    async recordDependencies(envelope, _references, signal) {
      // Python records exact engine provenance before returning the tool value.
      await request(host.binding(envelope.sessionId), 'learning.check', {}, signal);
    },
  };
  host = await openHarness({ ...options, library,
    async admitInput(binding) { await request(binding, 'learning.admit_input', {}); },
  });
  return host;
}
