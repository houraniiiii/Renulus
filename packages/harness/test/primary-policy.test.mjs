import "./owned-environment.mjs";
import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { randomUUID } from "node:crypto";
import { test } from "node:test";
import { Effect } from "effect";
import { AIError, InvalidRequestError } from "@opencode/ai";
import { openHarness } from "../src/host.ts";
import { scriptedModel } from "./scripted-model.ts";

test("a primary learning turn requires trusted preparation before native dispatch", async () => {
  const root = path.join("G:/Renulus-agent-scratch/oc-h02-h08/model-primary", randomUUID());
  const model = await scriptedModel("This unadmitted response must never run.");
  let preparations = 0;
  const options = { root, profileId: "synthetic-profile", storeId: "synthetic-primary-store",
    domainStoreId: "synthetic-domain", domainPath: "domain/renulus.sqlite3",
    model: { ...model,
      preparePrimary: () => {
        preparations++;
        return Effect.fail(new AIError({ reason: new InvalidRequestError({
          message: "Trusted primary authority is unavailable." }) }));
      },
    },
  };
  const manifest = JSON.parse(await readFile(new URL("../../contracts/fixtures/harness/paired-store-prepared.json", import.meta.url), "utf8"));
  manifest.domain_store.store_id = options.domainStoreId;
  manifest.runtime_store.store_id = options.storeId;
  manifest.runtime_store.path = "state/harness/opencode.sqlite";
  await mkdir(path.join(root, "state/harness"), { recursive: true });
  await writeFile(path.join(root, "state/harness/manifest.json"), JSON.stringify(manifest));
  let host;
  try {
    host = await openHarness(options);
    await host.activate("synthetic-primary-policy");
    const session = await host.createSession({ operationId: "primary-admission", title: "Synthetic glomerular education" });
    await host.submit({ sessionId: session.id, operationId: "primary-admission", attemptId: "1", text: "Explain synthetic glomerular injury." });
    await host.wait(session.id);
    assert.equal(await model.count(), 0, "Missing primary authority must produce zero model effects");
    assert.equal(preparations, 1);
    assert.equal((await host.observe(session.id)).session.outcome, "failed");
  } finally {
    await host?.close();
    await model.close();
  }
});

test("admitted context selection precedes native shaping and stays with one preparation", async () => {
  const root = path.join("G:/Renulus-agent-scratch/oc-h02-h08/model-primary", randomUUID());
  const model = await scriptedModel("Selected synthetic learning answer.");
  const order = [];
  const options = { root, profileId: "synthetic-profile", storeId: "synthetic-primary-store",
    domainStoreId: "synthetic-domain", domainPath: "domain/renulus.sqlite3",
    selectContext: async (_binding, messages) => {
      order.push("select");
      return messages;
    },
    model: { ...model, preparePrimary: (_binding, resolved) => {
      order.push("prepare");
      return Effect.succeed({ resolved, prepare: (request, _settings, unfiltered) => Effect.sync(() => {
        order.push("final");
        assert.ok(unfiltered, "Final preparation needs the captured pre-filter input");
        assert.ok(unfiltered.system.some(part => part.text.includes("nephrology education")));
        assert.ok(unfiltered.messages.some(message => message.content.some(part =>
          part.type === "text" && part.text.includes("Synthetic dialysis lesson"))));
        assert.deepEqual(unfiltered.messages, request.messages);
        return request;
      }) });
    } },
  };
  const manifest = JSON.parse(await readFile(new URL("../../contracts/fixtures/harness/paired-store-prepared.json", import.meta.url), "utf8"));
  manifest.domain_store.store_id = options.domainStoreId;
  manifest.runtime_store.store_id = options.storeId;
  manifest.runtime_store.path = "state/harness/opencode.sqlite";
  await mkdir(path.join(root, "state/harness"), { recursive: true });
  await writeFile(path.join(root, "state/harness/manifest.json"), JSON.stringify(manifest));
  let host;
  try {
    host = await openHarness(options);
    await host.activate("synthetic-primary-policy");
    const session = await host.createSession({ operationId: "selected-input", title: "Synthetic dialysis" });
    await host.submit({ sessionId: session.id, operationId: "selected-input", attemptId: "1", text: "Synthetic dialysis lesson" });
    await host.wait(session.id);
    assert.equal(await model.count(), 1);
    assert.deepEqual(order, ["prepare", "select", "final"]);
    assert.equal((await host.observe(session.id)).session.outcome, "succeeded");
  } finally {
    await host?.close();
    await model.close();
  }
});

test("unadmitted recovery preserves its native claim instead of terminalizing it", async () => {
  const root = path.join("G:/Renulus-agent-scratch/oc-h02-h08/model-primary", randomUUID());
  const model = await scriptedModel("Held synthetic answer.", true);
  const options = { root, profileId: "synthetic-profile", storeId: "synthetic-primary-store",
    domainStoreId: "synthetic-domain", domainPath: "domain/renulus.sqlite3", model };
  const manifest = JSON.parse(await readFile(new URL("../../contracts/fixtures/harness/paired-store-prepared.json", import.meta.url), "utf8"));
  manifest.domain_store.store_id = options.domainStoreId;
  manifest.runtime_store.store_id = options.storeId;
  manifest.runtime_store.path = "state/harness/opencode.sqlite";
  await mkdir(path.join(root, "state/harness"), { recursive: true });
  await writeFile(path.join(root, "state/harness/manifest.json"), JSON.stringify(manifest));
  let host;
  try {
    host = await openHarness(options);
    await host.activate("synthetic-primary-policy");
    const session = await host.createSession({ operationId: "held-input", title: "Synthetic transplant education" });
    await host.submit({ sessionId: session.id, operationId: "held-input", attemptId: "1", text: "Synthetic transplant lesson" });
    await model.started();
    assert.equal((await host.close({ timeoutMs: 0 })).state, "blocked");
    model.release();
    await host.settled();
    options.model = { ...model, preparePrimary: () => Effect.fail(new AIError({
      reason: new InvalidRequestError({ message: "Recovered run authority unavailable." }) })) };
    host = await openHarness(options);
    await host.activate("synthetic-primary-policy");
    const before = await host.observe(session.id);
    assert.equal(before.execution, "held");
    await assert.rejects(host.recover({ configurationId: "synthetic-primary-policy", sessionIds: [session.id] }),
      /recovery_admission_unavailable/);
    assert.deepEqual(await host.observe(session.id), before);
    assert.deepEqual((await host.status()).heldSessionIds, [session.id]);
    assert.equal(await model.count(), 1);
  } finally {
    model.release();
    await host?.close();
    await model.close();
  }
});
