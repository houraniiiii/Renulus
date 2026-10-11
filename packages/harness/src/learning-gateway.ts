// SPDX-License-Identifier: MIT
import { Effect } from 'effect';
import { AIError, InvalidRequestError, LLM, LLMClient } from '@opencode/ai';
import type { DomainClient, DomainBinding } from './domain-ipc.ts';
import { createGatewayAdapter, gatewayDomainError, type TrustedGatewayPreparation, type StatelessModelPreparation } from './gateway-adapter.ts';
import { captureNativeManifest } from './native-manifest.ts';
import type { ExtractionFailure, ExtractionReply } from './extraction-host.ts';

/** All account, run, counter and effect authority stays in the admitted parent. */
export async function createLearningGateway(domain: DomainClient) {
  const extracting = new Map<string, ExtractionFailure | undefined>();
  const safeFailure = (value: unknown): ExtractionFailure | undefined => {
    if (!value || typeof value !== 'object') return undefined;
    const error = value as { code?: unknown; status?: unknown; retryable?: unknown };
    if (typeof error.code !== 'string' || error.code.length > 256 || !/^[A-Za-z0-9][A-Za-z0-9._:-]*$/.test(error.code) ||
        !Number.isSafeInteger(error.status) || (error.status as number) < 100 || (error.status as number) > 599 ||
        typeof error.retryable !== 'boolean') return undefined;
    return Object.freeze({ code: error.code, status: error.status as number, retryable: error.retryable });
  };
  const denied = () => new AIError({ reason: new InvalidRequestError({
    message: 'The learning gateway is unavailable.' }) });
  const request = (binding: DomainBinding, command: string, payload: Readonly<Record<string, unknown>>) =>
    Effect.tryPromise({
      try: async signal => {
        const outcome = await domain.request(binding, command, payload, { signal });
        if (outcome.outcome !== 'committed_reference' || outcome.error !== undefined || !outcome.result) {
          if (extracting.has(binding.operation_id)) extracting.set(binding.operation_id, safeFailure(outcome.error));
          throw gatewayDomainError(outcome);
        }
        return outcome.result;
      },
      catch: error => error instanceof AIError ? error : denied(),
    });
  const gateway = await createGatewayAdapter({ domain,
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
  return { ...gateway,
    async generateExtraction(binding: DomainBinding, input: Readonly<{ system: string; user: string }>, signal: AbortSignal): Promise<ExtractionReply> {
      if (extracting.has(binding.operation_id)) return { failure: { code: 'memory_extraction_identity_conflict', status: 409, retryable: false } };
      extracting.set(binding.operation_id, undefined);
      let prepared: StatelessModelPreparation | undefined;
      try {
        const exit = await Effect.runPromiseExit(Effect.scoped(Effect.gen(function* () {
          const admitted = yield* gateway.prepareStateless(binding, input);
          prepared = admitted;
          const response = yield* LLM.generate(admitted.request).pipe(Effect.provideService(LLMClient.Service, gateway.client));
          const receipt = admitted.receipt();
          if (!receipt) return yield* Effect.fail(denied());
          return { text: response.text, receipt };
        })), { signal });
        if (exit._tag === 'Success') return exit.value;
        return { failure: safeFailure(prepared?.failure()) ?? extracting.get(binding.operation_id) ??
          { code: 'memory_extraction_failed', status: 503, retryable: true } };
      } finally { extracting.delete(binding.operation_id); }
    },
  };
}
