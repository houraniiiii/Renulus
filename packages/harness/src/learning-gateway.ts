// SPDX-License-Identifier: MIT
import { Effect } from 'effect';
import { AIError, InvalidRequestError } from '@opencode/ai';
import type { DomainClient, DomainBinding } from './domain-ipc.ts';
import { createGatewayAdapter, gatewayDomainError, type TrustedGatewayPreparation } from './gateway-adapter.ts';
import { captureNativeManifest } from './native-manifest.ts';

/** All account, run, counter and effect authority stays in the admitted parent. */
export async function createLearningGateway(domain: DomainClient) {
  const denied = () => new AIError({ reason: new InvalidRequestError({
    message: 'The learning gateway is unavailable.' }) });
  const request = (binding: DomainBinding, command: string, payload: Readonly<Record<string, unknown>>) =>
    Effect.tryPromise({
      try: async signal => {
        const outcome = await domain.request(binding, command, payload, { signal });
        if (outcome.outcome !== 'committed_reference' || outcome.error !== undefined || !outcome.result)
          throw gatewayDomainError(outcome);
        return outcome.result;
      },
      catch: error => error instanceof AIError ? error : denied(),
    });
  return createGatewayAdapter({ domain,
    beforePrepare: binding => request(binding, 'model.prepare', {}).pipe(
      Effect.map(value => value as unknown as TrustedGatewayPreparation)),
    registerManifest: (plan, native) => Effect.try({ try: () => captureNativeManifest(native), catch: denied }).pipe(
      Effect.flatMap(manifest => request(plan.binding, 'model.manifest', { manifest })),
      Effect.flatMap(value => Object.keys(value).join(',') === 'registered' && value.registered === true
        ? Effect.void : Effect.fail(denied())),
    ),
    validateImages: (binding, images) => request(binding, 'learning.validate_images', { images }).pipe(
      Effect.flatMap(value => Object.keys(value).join(',') === 'validated' && value.validated === true
        ? Effect.void : Effect.fail(denied())),
    ),
  });
}
