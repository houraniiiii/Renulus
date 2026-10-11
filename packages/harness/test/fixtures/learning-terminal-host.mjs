// Actual SDK/private IPC with a synthetic, explicitly held tool continuation.
import { Effect } from "effect";
import { LLMEvent } from "@opencode/ai";
import { TestLLM } from "@opencode/ai/testing";
import { openLearningHarness } from "../../src/learning-host.ts";
import { runHarnessIpc } from "../../src/ipc.ts";
import { scriptedModel } from "../scripted-model.ts";

await runHarnessIpc(async (boot, domain) => {
  const model = await scriptedModel("First completed synthetic explanation.");
  await Effect.runPromise(model.client.push(TestLLM.toolCalls(
    LLMEvent.textStart({ id: "partial" }),
    LLMEvent.textDelta({ id: "partial", text: "Partial synthetic explanation. " }),
    LLMEvent.textEnd({ id: "partial" }),
    LLMEvent.toolCall({ id: "terminal-library-call", name: "renulus_library_retrieve",
      input: { query: "CKD", limit: 1 } }),
  )));
  const release = await model.holdNext("Final synthetic explanation after Library.");
  const host = await openLearningHarness({ root: boot.root, profileId: boot.profile_id, storeId: boot.store_id,
    domainStoreId: boot.domain_store_id, domainPath: boot.domain_path, model }, domain);
  let sessionId;
  let settlement;
  return { ...host,
    async submit(input) { sessionId = input.sessionId; return host.submit(input); },
    async cancel(id) {
      // This fixture-only control identity opens the TestLLM gate without
      // competing with the saved stream's sole data slot.
      if (id === "synthetic-release-continuation") {
        release();
        return { interrupted: false, outcome: "cancelled_settled" };
      }
      return host.cancel(id);
    },
    async status() { return { ...await host.status(), modelCalls: await model.count(),
      observation: sessionId ? await host.observe(sessionId) : null }; },
    settled() { return settlement ??= (async () => { release(); await host.settled(); await model.close(); })(); },
  };
});
