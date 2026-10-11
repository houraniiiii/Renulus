// Owned subprocess fixture. TestLLM and native SDK only; no live provider.
import { openHarness } from "../../src/host.ts";
import { runHarnessIpc } from "../../src/ipc.ts";
import { scriptedModel } from "../scripted-model.ts";

await runHarnessIpc(async (boot, domain) => {
  // Request order: outer tool call, nested extraction, outer continuation.
  const model = await scriptedModel("Synthetic extraction complete.", false,
    { name: "renulus_library_retrieve", input: { query: "CKD", limit: 1 } });
  await model.respond("Synthetic cited CKD explanation [1].");
  const admitted = new Map();
  const dependencies = new Map();
  const checks = [];
  let native;
  let host;
  let ownedSettlement;
  const library = {
    async resolve(context, signal) {
      signal.throwIfAborted();
      native = { sessionID: context.sessionID, messageID: context.messageID,
        id: context.id, agent: context.agent };
      const binding = host.binding(context.sessionID);
      if (admitted.get(binding.operation_id) !== binding || context.messageID === binding.input_id) {
        throw new Error("invalid_native_authority");
      }
      return { sessionId: binding.session_id, operationId: binding.operation_id, attemptId: binding.attempt_id,
        scope: { kind: "study" }, revisionIds: ["rev_" + "3".repeat(32)],
        policyRevision: 0, contextEpoch: 0, cancellationEpoch: 0 };
    },
    async check(envelope, stage, signal) {
      signal.throwIfAborted();
      const binding = host.binding(envelope.sessionId);
      if (binding.operation_id !== envelope.operationId || binding.attempt_id !== envelope.attemptId
          || admitted.get(binding.operation_id) !== binding) throw new Error("invalid_native_authority");
      checks.push(stage);
    },
    async execute(command, arguments_, envelope, signal) {
      const outcome = await domain.request(host.binding(envelope.sessionId), command,
        { command, arguments: arguments_, envelope }, { signal });
      if (outcome.outcome !== "committed_reference" || !outcome.result) throw new Error("domain_unavailable");
      return outcome.result;
    },
    async recordDependencies(envelope, references, signal) {
      signal.throwIfAborted();
      for (const reference of references) dependencies.set(JSON.stringify(reference), structuredClone(reference));
    },
  };
  try {
    host = await openHarness({ root: boot.root, profileId: boot.profile_id, storeId: boot.store_id,
      domainStoreId: boot.domain_store_id, domainPath: boot.domain_path, model, library,
      async admitInput(binding) {
        // Trusted host hook precedes actual native user-input scheduling.
        admitted.set(binding.operation_id, binding);
      },
    });
  } catch (error) { await model.close(); throw error; }
  return {
    ...host,
    async status() {
      return { ...await host.status(), synthetic: { modelRequests: await model.count(),
        callback: domain.state(), binding: admitted.get("learning") ?? null, native: native ?? null,
        dependencies: [...dependencies.values()], checks } };
    },
    settled() {
      return ownedSettlement ??= (async () => { await host.settled(); await model.close(); })();
    },
  };
});
