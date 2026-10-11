// Actual SDK and authenticated private IPC. Only admitted account evidence,
// synthetic preseeded history and Python's loopback inference are test inputs.
import assert from 'node:assert/strict';
import { Effect } from 'effect';
import { AIError, InvalidRequestError, Message } from '@opencode/ai';
import { createGatewayAdapter } from '../../src/gateway-adapter.ts';
import { captureNativeManifest } from '../../src/native-manifest.ts';
import { openHarness } from '../../src/host.ts';
import { runHarnessIpc } from '../../src/ipc.ts';

const denied = () => new AIError({ reason: new InvalidRequestError({
  message: 'Synthetic fixture authority is unavailable.' }) });

await runHarnessIpc(async (boot, domain) => {
  assert.equal(typeof boot.synthetic_system, 'string');
  assert.equal(typeof boot.synthetic_png, 'string');
  let nativePreparations = 0, imageValidations = 0, manifestRegistrations = 0;
  let waitingSubmit = false, replayBlocked = null, settlement;
  const preparedRequests = [];
  const call = async (binding, command, payload, signal) => {
    const outcome = await domain.request(binding, command, payload, { signal });
    if (outcome.outcome !== 'committed_reference' || !outcome.result) throw denied();
    return outcome.result;
  };
  const callback = (binding, command, payload) => Effect.tryPromise({
    try: signal => call(binding, command, payload, signal), catch: denied,
  });
  const adapter = await createGatewayAdapter({ domain,
    beforePrepare: binding => callback(binding, 'model.prepare', {}),
    registerManifest: (plan, unfiltered) => Effect.gen(function* () {
      const manifest = captureNativeManifest(unfiltered);
      yield* callback(plan.binding, 'model.manifest', { manifest });
      manifestRegistrations++;
    }),
    validateImages: (_binding, images) => Effect.sync(() => {
      // Python publicly decoded this fixed PNG before admitting any model input.
      // Its exact hash/bytes are pinned in synthetic evidence and final proof.
      assert.deepEqual(images, [{ type: 'image', media_type: 'image/png', data: boot.synthetic_png }]);
      imageValidations++;
    }),
  });
  const library = {
    async resolve() { throw denied(); }, async check() { throw denied(); },
    async execute() { throw denied(); }, async recordDependencies() { throw denied(); },
  };
  const host = await openHarness({ root: boot.root, profileId: boot.profile_id,
    storeId: boot.store_id, domainStoreId: boot.domain_store_id, domainPath: boot.domain_path,
    library,
    admitInput: binding => call(binding, 'model.admit_input', {}),
    async selectContext(_binding, messages) {
      return { messages: [
        Message.user('Earlier synthetic CKD prompt'),
        Message.assistant([{ type: 'tool-call', id: 'fixture_call_1', name: 'renulus_library_retrieve',
          input: { query: 'Synthetic CKD preseed', limit: 1 } }]),
        Message.make({ role: 'tool', content: [{ type: 'tool-result', id: 'fixture_call_1',
          name: 'renulus_library_retrieve', result: { type: 'text', value: '{"status":"ready","passages":[]}' } }] }),
        ...messages,
      ], additionalSystem: [{ type: 'text', text: boot.synthetic_system }] };
    },
    model: { providerId: 'synthetic', modelId: 'bootstrap', configuration: {
      model: 'synthetic/bootstrap', providers: { synthetic: {
        package: '@opencode/ai/providers/openai-compatible', settings: { baseURL: 'https://synthetic.invalid/v1' },
        models: { bootstrap: { limit: { context: 256, output: 32 } } },
      } },
    },
      preparePrimary(binding, resolved) {
        nativePreparations++;
        return adapter.preparePrimary(binding, resolved);
      },
      client: {
        stream(request, settings) {
          preparedRequests.push(request);
          return adapter.client.stream(request, settings);
        },
        generate(request, settings) {
          preparedRequests.push(request);
          return adapter.client.generate(request, settings);
        },
        compact: () => Effect.fail(denied()),
      },
    },
  });
  return { ...host,
    async submit(input) {
      waitingSubmit = true;
      try {
        const admitted = await host.submit(input);
        await host.wait(input.sessionId); // Keep the sole IPC data slot owned.
        if (preparedRequests.length) {
          const replay = await Effect.runPromise(adapter.client.generate(preparedRequests[0]).pipe(Effect.result));
          replayBlocked = replay._tag === 'Failure';
        }
        return admitted;
      } finally { waitingSubmit = false; }
    },
    async status() {
      return { ...await host.status(), nativePreparations, imageValidations, manifestRegistrations,
        nativeRequests: preparedRequests.length, waitingSubmit, replayBlocked, domainCallbacks: domain.state(),
        gatewayReceipt: preparedRequests.length ? adapter.receipt(preparedRequests[0]) ?? null : null };
    },
    settled() {
      return settlement ??= (async () => { await host.settled(); await adapter.close(); })();
    },
  };
});
