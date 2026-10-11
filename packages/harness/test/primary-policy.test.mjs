import "./owned-environment.mjs";
import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { randomUUID } from "node:crypto";
import { test } from "node:test";
import { Effect } from "effect";
import { AIError, InvalidRequestError } from "@opencode/ai";
import { OpenAICompatibleChat } from "@opencode/ai/protocols/openai-compatible-chat";
import { SessionRunnerModel } from "@opencode/core/session/runner/model";
import { captureNativeManifest } from "../src/native-manifest.ts";
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

test("trusted role routing identifies both the native request and saved assistant model", async () => {
  const root = path.join("G:/Renulus-agent-scratch/oc-h02-h08/model-primary", randomUUID());
  const model = await scriptedModel("Selected synthetic transplant education.");
  let preparations = 0;
  const trusted = OpenAICompatibleChat.route.with({ provider: "synthetic",
    endpoint: { baseURL: "https://synthetic.invalid/v1" } }).model({ id: "trusted-selected" });
  const options = { root, profileId: "synthetic-profile", storeId: "synthetic-primary-store",
    domainStoreId: "synthetic-domain", domainPath: "domain/renulus.sqlite3",
    model: { ...model, preparePrimary: (_binding, initial) => {
      preparations++;
      const resolved = SessionRunnerModel.resolved(trusted, { capabilities: initial.capabilities,
        cost: initial.cost, limit: initial.limit });
      return Effect.succeed({ resolved, prepare: request => Effect.succeed(request) });
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
    const session = await host.createSession({ operationId: "routed-input", title: "Synthetic transplant" });
    await host.submit({ sessionId: session.id, operationId: "routed-input", attemptId: "1", text: "Synthetic transplant lesson" });
    await host.wait(session.id);
    const observed = await host.observe(session.id);
    assert.equal(observed.session.outcome, "succeeded");
    assert.equal((await model.requests())[0].model.id, "trusted-selected");
    assert.equal(observed.messages.find(message => message.type === "assistant").model.id, "trusted-selected");
    assert.equal(preparations, 1, "Context loading and primary preparation must share one trusted plan");
  } finally {
    await host?.close();
    await model.close();
  }
});

test("inline image ingress reaches native shaping and the admitted manifest unchanged", async () => {
  const root = path.join("G:/Renulus-agent-scratch/oc-h02-h08/model-primary", randomUUID());
  const model = await scriptedModel("Synthetic renal image learning.");
  const data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA6fptVAAAACklEQVR4nGNgAAAAAgABSK+kcQAAAABJRU5ErkJggg==";
  let captured;
  const options = { root, profileId: "synthetic-profile", storeId: "synthetic-primary-store",
    domainStoreId: "synthetic-domain", domainPath: "domain/renulus.sqlite3",
    model: { ...model, preparePrimary: (_binding, initial) => Effect.succeed({
      resolved: SessionRunnerModel.resolved(initial.model, { capabilities: { ...initial.capabilities, input: ["text", "image"] },
        cost: initial.cost, limit: initial.limit }),
      prepare: (request, _settings, unfiltered) => Effect.sync(() => {
        captured = captureNativeManifest(unfiltered);
        assert.ok(request.messages.some(message => message.content.some(part => part.type === "media")));
        return request;
      }),
    }) },
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
    const session = await host.createSession({ operationId: "image-input", title: "Synthetic renal image" });
    const valid = { type: "image", media_type: "image/png", data };
    for (const images of [null, { uri: "file:///synthetic.png" },
      [{ ...valid, uri: "https://synthetic.invalid/image.png" }],
      [{ ...valid, media_type: "image/jpeg" }], [{ ...valid, data: "not-base64" }],
      Array(5).fill(valid)]) {
      await assert.rejects(host.submit({ sessionId: session.id, operationId: "rejected-image", attemptId: "1",
        text: "Unadmitted input", images }), /invalid_images/);
    }
    assert.equal(await model.count(), 0);
    assert.deepEqual((await host.observe(session.id)).messages, []);
    const input = await host.submit({ sessionId: session.id, operationId: "image-input", attemptId: "1",
      text: "Explain this synthetic renal image.", images: [{ type: "image", media_type: "image/png", data }] });
    await host.wait(session.id);
    const result = await host.observe(session.id);
    assert.equal(result.session.outcome, "succeeded", JSON.stringify(result.messages));
    const image = captured.messages.flatMap(message => message.content).find(part => part.type === "image");
    assert.deepEqual(image, { type: "image", media_type: "image/png", bytes: 67, detail: null,
      sha256: "eaa4a94ea300e0d2c775968cbe42f0b5b51ceafdeb73d64e9efddf6d4e880865" });
    const before = await host.observe(session.id);
    const saved = before.messages.find(message => message.id === input.inputId);
    assert.equal(saved.files[0].data, data);
    assert.deepEqual(saved.files[0].source, { type: "inline" });
    await host.close();
    host = await openHarness(options);
    assert.deepEqual(await host.observe(session.id), before);
    assert.equal(await model.count(), 1);
  } finally {
    await host?.close();
    await model.close();
  }
});
