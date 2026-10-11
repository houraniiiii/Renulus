import { openLearningHarness } from "../../src/learning-host.ts";
import { runHarnessIpc } from "../../src/ipc.ts";
import { scriptedModel } from "../scripted-model.ts";

await runHarnessIpc(async (boot, domain) => {
  const model = await scriptedModel("A closed candidate must never request this answer.");
  const host = await openLearningHarness({ root: boot.root, profileId: boot.profile_id, storeId: boot.store_id,
    domainStoreId: boot.domain_store_id, domainPath: boot.domain_path, model }, domain);
  let settlement;
  let inspectionError;
  return { ...host,
    async inspect() {
      try { return await host.inspect(); }
      catch (error) { inspectionError = String(error); throw error; }
    },
    async status() { return { ...await host.status(), modelCalls: await model.count(), inspectionError }; },
    settled() { return settlement ??= (async () => { await host.settled(); await model.close(); })(); },
  };
});
