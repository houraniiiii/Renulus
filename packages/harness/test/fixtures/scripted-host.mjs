import { openHarness } from "../../src/host.ts";
import { runHarnessIpc } from "../../src/ipc.ts";
import { scriptedModel } from "../scripted-model.ts";

// Real SDK TestLLM is the only model adapter in this separate test entry.
let model;
let releaseTimer;
try {
  await runHarnessIpc(async boot => {
    const holdMs = boot.test?.hold_ms ?? 0;
    if (!Number.isSafeInteger(holdMs) || holdMs < 0 || holdMs > 5000) throw new Error("invalid_test_hold");
    const answers = boot.test?.answers ?? ["Synthetic CKD learning answer."];
    if (!Array.isArray(answers) || answers.length < 1 || answers.length > 8 ||
        !answers.every(answer => typeof answer === "string" && answer.length <= 4096)) throw new Error("invalid_test_answers");
    model = await scriptedModel(answers[0], holdMs > 0);
    for (const answer of answers.slice(1)) await model.respond(answer);
    if (holdMs) void model.started().then(() => { releaseTimer = setTimeout(model.release, holdMs); }).catch(() => {});
    const host = await openHarness({
      root: boot.root, profileId: boot.profile_id, storeId: boot.store_id,
      domainStoreId: boot.domain_store_id, domainPath: boot.domain_path, model,
    });
    return {
      ...host,
      async status() {
        return { ...await host.status(), modelCalls: await model.count(), runtimePath: process.env.PATH };
      },
    };
  });
} finally {
  clearTimeout(releaseTimer);
  model?.release();
  await model?.close();
}
