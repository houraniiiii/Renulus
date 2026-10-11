// SPDX-License-Identifier: MIT
import assert from "node:assert/strict";
import { test } from "node:test";
import { createHash, randomUUID } from "node:crypto";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { Effect, Layer, Logger, ManagedRuntime, Schema, Stream } from "effect";
import { AIError, InvalidRequestError, LLMClient } from "@opencode/ai";
import { OpenCode, AbsolutePath } from "@opencode/sdk/effect";
import { Session } from "@opencode/schema/session";
import { SessionMessage } from "@opencode/schema/session-message";
import { Config } from "@opencode/core/config";
import { InstructionDiscovery } from "@opencode/core/instruction-discovery";
import { llmClient } from "@opencode/core/effect/app-node-platform";
import { Global } from "@opencode/util/global";
import { createSessionTransfer } from "../src/session-transfer.ts";

const receiptRoot = "G:/rh06/native-transfer";
const identity = { profileId: "synthetic-h06-profile", storeId: "synthetic-h06-store",
  generation: "synthetic-generation-1", operationId: "synthetic-import-1", attemptId: "attempt-1" };
const bundle = { format: "renulus.saved-session/1", conversationId: "legacy-chat-1",
  title: "Synthetic kidney learning", messages: [
    { id: "legacy-user-1", role: "user", content: "Synthetic potassium 5.2 mmol/L — résumé.",
      runId: "legacy-run-1", createdAt: "2026-10-10T10:00:00Z", citations: [] },
    { id: "legacy-answer-1", role: "assistant", content: "Synthetic retained answer, not current clinical guidance.",
      runId: "legacy-run-1", createdAt: "2026-10-10T10:00:01Z", completedAt: "2026-10-10T10:00:02Z",
      legacyOutcome: "completed",
      citations: [{ passage_id: "synthetic-passage", document_revision: "synthetic-revision",
        locators: [{ page: 4, marker: "renal-study-delta-47" }] }] },
  ] };
const sha = text => createHash("sha256").update(text, "utf8").digest("hex");
function deferred() { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; }
const targetFor = (source = bundle) => ({
  sessionId: "ses_" + sha(JSON.stringify(["renulus-h06-session-v1", identity.profileId, identity.storeId, source.conversationId])),
  bundleDigest: sha(JSON.stringify(source)),
});
function stageAll(transfer, frame = identity, source = bundle) {
  const document = JSON.stringify(source);
  const chunks = document.match(/[\s\S]{1,8192}/gu);
  let result;
  for (let index = 0; index < chunks.length; index++) result = transfer.stage(frame,
    { ...targetFor(source), partIndex: index, partCount: chunks.length,
      totalBytes: Buffer.byteLength(document, "utf8"), chunk: chunks[index] });
  return result;
}

async function openNative(root = path.join(receiptRoot, randomUUID())) {
  const workspace = path.join(root, "workspace");
  await mkdir(workspace, { recursive: true });
  let modelCalls = 0;
  const denied = () => {
    modelCalls++;
    return new AIError({ reason: new InvalidRequestError({ message: "Synthetic H06 transfer forbids inference." }) });
  };
  const client = { stream: () => Stream.fail(denied()), generate: () => Effect.fail(denied()),
    compact: () => Effect.fail(denied()) };
  const content = JSON.stringify({ compaction: { auto: false }, agents: { title: { disabled: true } } });
  const runtime = ManagedRuntime.make(Layer.effect(OpenCode.Service, OpenCode.create({
    app: { name: "renulus-h06-transfer-test", version: "1" }, database: { path: path.join(root, "native.sqlite") },
    config: { directory: path.join(root, "config"), project: false, content },
    models: { fetch: false, snapshot: false }, fs: { filewatcher: false, fff: false }, events: { persist: false },
  }, { overrides: [
    Global.node.replace(Global.layerWith(Object.fromEntries(
      ["home", "data", "cache", "config", "state", "tmp", "bin", "log", "repos"].map(
        key => [key, path.join(root, key)])))),
    Config.node.replace(Config.configured({ project: false, global: false, content })),
    InstructionDiscovery.node.replace(InstructionDiscovery.configured({ project: false, global: false })),
    llmClient.replace(Layer.succeed(LLMClient.Service, client)),
  ] })).pipe(Layer.provideMerge(Logger.layer([], { mergeWithExisting: false }))));
  const sdk = await runtime.runPromise(OpenCode.Service);
  const scope = { ...identity, location: { directory: AbsolutePath.make(workspace) } };
  const run = effect => runtime.runPromise(effect);
  const transfer = createSessionTransfer({ sdk, run, scope, checkCurrent: () => {} });
  return { root, sdk, run, scope, transfer, modelCalls: () => modelCalls, async close() {
    transfer.seal();
    await transfer.settled();
    await runtime.dispose();
    assert.equal(modelCalls, 0);
  } };
}

test("supported native import retains exact Unicode history and citation provenance with zero inference", async () => {
  const native = await openNative();
  try {
    assert.equal(stageAll(native.transfer).complete, true);
    const target = targetFor();
    // Literals independently calculated with the managed Python compact-JSON contract.
    assert.equal(target.sessionId, "ses_b5f51cee5912a37129c27aba4725b7be373104aa07e2800a1c332d01f7322954");
    assert.deepEqual(await native.transfer.commit(identity, target),
      { state: "verified", ...target, messageCount: 2 });
    const exported = await native.run(native.sdk.sessions.export({
      sessionID: Session.ID.make(target.sessionId), sanitize: false }));
    const messages = exported.messages.map(message => Schema.encodeSync(SessionMessage.Info)(message));
    assert.equal(messages[0].id, "msg_f8ffa5b16fdc51de2a51d8c2b041c4849d1210cdbc44349ab40cdf4806c8d873");
    assert.equal(messages.length, 2);
    for (let index = 0; index < messages.length; index++) {
      const actual = messages[index], expected = bundle.messages[index];
      assert.equal(actual.type, expected.role);
      assert.equal(actual.type === "user" ? actual.text : actual.content[0].text, expected.content);
      assert.equal(actual.metadata.legacy.id, expected.id);
      assert.deepEqual(actual.metadata.legacy.citations, expected.citations);
      assert.equal(actual.metadata.lineage, "unknown");
    }
    assert.equal(exported.info.metadata.renulusProfile, identity.profileId);
    assert.equal(exported.info.metadata.renulusStore, identity.storeId);
    assert.equal(exported.info.metadata.bundleDigest, target.bundleDigest);
    assert.deepEqual(exported.info.permissions, [{ action: "*", resource: "*", effect: "deny" }]);
  } finally { await native.close(); }
});

test("out-of-order JSON parts and identical replay form one complete exact stage", async () => {
  const native = await openNative();
  try {
    const document = JSON.stringify(bundle), cut = document.indexOf("messages");
    const chunks = [document.slice(0, cut), document.slice(cut)];
    const part = index => ({ ...targetFor(), partCount: 2, partIndex: index,
      totalBytes: Buffer.byteLength(document), chunk: chunks[index] });
    const first = native.transfer.stage(identity, part(1));
    assert.equal(first.complete, false);
    assert.equal(first.receivedParts, 1);
    assert.deepEqual(native.transfer.stage(identity, part(1)), first);
    const complete = native.transfer.stage(identity, part(0));
    assert.equal(complete.complete, true);
    assert.equal(complete.receivedBytes, Buffer.byteLength(document));
    assert.equal((await native.transfer.commit(identity, targetFor())).messageCount, 2);
  } finally { await native.close(); }
});

test("a staged operation cannot change attempt, target, digest, declaration or part bytes", async () => {
  const native = await openNative();
  try {
    const payload = { ...targetFor(), partIndex: 0, partCount: 2, totalBytes: 100, chunk: "{" };
    const first = native.transfer.stage(identity, payload);
    for (const changed of [
      { frame: { ...identity, attemptId: "other-attempt" }, payload },
      { payload: { ...payload, sessionId: "ses_" + "a".repeat(64) } },
      { payload: { ...payload, bundleDigest: "a".repeat(64) } },
      { payload: { ...payload, partCount: 3 } },
      { payload: { ...payload, totalBytes: 101 } },
      { payload: { ...payload, chunk: "[" } },
    ]) {
      assert.throws(() => native.transfer.stage(changed.frame ?? identity, changed.payload),
        { code: "transfer_conflict" });
    }
    assert.deepEqual(native.transfer.stage(identity, payload), first);
    assert.equal((await native.run(native.sdk.sessions.list())).data.length, 0);
  } finally { await native.close(); }
});

test("stage declaration bounds and authenticated frame are enforced before native effects", async () => {
  const native = await openNative();
  try {
    const payload = { ...targetFor(), partIndex: 0, partCount: 2, totalBytes: 100, chunk: "{" };
    for (const changed of [
      { partCount: 0 }, { partCount: 257 }, { partIndex: -1 }, { partIndex: 2 }, { partIndex: 0.5 },
      { totalBytes: 0 }, { totalBytes: 8 * 1024 * 1024 + 1 }, { chunk: "" },
      { chunk: "\ud800" }, { chunk: "x".repeat(48 * 1024) }, { path: "G:/untrusted" },
      { bundleDigest: "invalid" }, { sessionId: "ses_unreserved" },
    ]) assert.throws(() => native.transfer.stage(identity, { ...payload, ...changed }),
      { code: "transfer_invalid_stage" });
    assert.throws(() => native.transfer.stage({ ...identity, generation: "stale" }, payload),
      { code: "transfer_scope_mismatch" });
    assert.equal((await native.run(native.sdk.sessions.list())).data.length, 0);
  } finally { await native.close(); }
});

test("invalid or incomplete legacy history is refused without native effects or silent omission", async () => {
  const native = await openNative();
  try {
    const badAnswer = { ...bundle.messages[1] };
    delete badAnswer.completedAt;
    const sources = [
      { ...bundle, messages: [badAnswer] },
      { ...bundle, messages: [{ ...bundle.messages[0], role: "system" }] },
      { ...bundle, messages: [{ ...bundle.messages[0], createdAt: "2026-02-30T10:00:00Z" }] },
      { ...bundle, messages: [{ ...bundle.messages[1], completedAt: "2026-10-09T10:00:00Z" }] },
      { ...bundle, messages: [{ ...bundle.messages[0], content: "\ud800" }] },
      { ...bundle, messages: [{ ...bundle.messages[0], permissions: [] }] },
      { ...bundle, messages: [bundle.messages[0], bundle.messages[0]] },
      { ...bundle, messages: [{ ...bundle.messages[0], citations: "invalid" }] },
      { ...bundle, messages: [{ ...bundle.messages[0], legacyOutcome: "completed" }] },
      { ...bundle, messages: [{ ...bundle.messages[1], legacyOutcome: "unknown" }] },
      { ...bundle, path: "G:/untrusted" },
      { ...bundle, messages: Array.from({ length: 4097 }, (_, index) => ({ ...bundle.messages[0], id: "legacy-" + index })) },
    ];
    for (let index = 0; index < sources.length; index++) {
      const transfer = createSessionTransfer({ sdk: native.sdk, run: native.run, scope: native.scope, checkCurrent: () => {} });
      assert.throws(() => stageAll(transfer, { ...identity, operationId: "invalid-" + index }, sources[index]),
        { code: "transfer_invalid_bundle" });
    }
    assert.equal((await native.run(native.sdk.sessions.list())).data.length, 0);
  } finally { await native.close(); }
});

test("stage capacity reserves declared bytes without evicting existing work", async () => {
  const native = await openNative();
  try {
    const part = { ...targetFor(), partIndex: 0, partCount: 2, totalBytes: 100, chunk: "{" };
    for (let index = 0; index < 4; index++) native.transfer.stage({ ...identity, operationId: "stage-" + index }, part);
    assert.throws(() => native.transfer.stage({ ...identity, operationId: "stage-5" }, part),
      { code: "transfer_capacity" });
    assert.equal(native.transfer.stage({ ...identity, operationId: "stage-0" }, part).receivedParts, 1);
    const other = createSessionTransfer({ sdk: native.sdk, run: native.run, scope: native.scope, checkCurrent: () => {} });
    for (let index = 0; index < 2; index++) other.stage({ ...identity, operationId: "large-" + index },
      { ...part, totalBytes: 8 * 1024 * 1024 });
    assert.throws(() => other.stage({ ...identity, operationId: "excess-bytes" }, part),
      { code: "transfer_capacity" });
    const third = createSessionTransfer({ sdk: native.sdk, run: native.run, scope: native.scope, checkCurrent: () => {} });
    assert.throws(() => third.stage(identity, { ...part, totalBytes: 1, chunk: "{}" }),
      { code: "transfer_invalid_stage" });
    assert.equal((await native.run(native.sdk.sessions.list())).data.length, 0);
  } finally { await native.close(); }
});

test("reopen restages the immutable bundle and verifies by get/export without another import", async () => {
  const first = await openNative();
  stageAll(first.transfer);
  await first.transfer.commit(identity, targetFor());
  await first.close();
  const reopened = await openNative(first.root);
  try {
    const frame = { ...identity, generation: "synthetic-generation-2" };
    const transfer = createSessionTransfer({ sdk: { sessions: { ...reopened.sdk.sessions,
      create: () => assert.fail("reopen inspection must not create a template"),
      import: () => assert.fail("reopen inspection must not resend import"),
    } }, run: reopened.run, scope: { ...reopened.scope, generation: frame.generation }, checkCurrent: () => {} });
    stageAll(transfer, frame);
    assert.deepEqual(await transfer.inspect(frame, targetFor()), { state: "verified", ...targetFor(), messageCount: 2 });
    assert.equal((await reopened.run(reopened.sdk.sessions.list())).data.length, 1);
  } finally { await reopened.close(); }
});

test("lost import acknowledgement resolves by exact readback and duplicate commit shares ownership", async () => {
  const native = await openNative();
  try {
    let imports = 0;
    const transfer = createSessionTransfer({ sdk: { sessions: { ...native.sdk.sessions, import: input => {
      imports++;
      return native.sdk.sessions.import(input).pipe(Effect.flatMap(() => Effect.fail(new Error("synthetic lost acknowledgement"))));
    } } }, run: native.run, scope: native.scope, checkCurrent: () => {} });
    stageAll(transfer);
    const first = transfer.commit(identity, targetFor()), repeated = transfer.commit(identity, targetFor());
    assert.equal(first, repeated);
    assert.deepEqual(await first, { state: "verified", ...targetFor(), messageCount: 2 });
    assert.equal(imports, 1);
    assert.equal((await native.run(native.sdk.sessions.list())).data.length, 1);
    assert.deepEqual(await transfer.inspect(identity, targetFor()), await first);
  } finally { await native.close(); }
});

test("an existing target with changed native permissions fails closed without overwrite", async () => {
  const native = await openNative();
  try {
    stageAll(native.transfer);
    await native.transfer.commit(identity, targetFor());
    const sessionID = Session.ID.make(targetFor().sessionId);
    const retained = await native.run(native.sdk.sessions.export({ sessionID, sanitize: false }));
    await native.run(native.sdk.sessions.remove({ sessionID }));
    await native.run(native.sdk.sessions.import({ ...retained, info: { ...retained.info,
      permissions: [{ action: "*", resource: "*", effect: "allow" }] }, location: native.scope.location }));
    const reopened = createSessionTransfer({ sdk: native.sdk, run: native.run, scope: native.scope, checkCurrent: () => {} });
    stageAll(reopened);
    await assert.rejects(reopened.commit(identity, targetFor()), { code: "transfer_conflict" });
    assert.deepEqual((await native.run(native.sdk.sessions.get({ sessionID }))).permissions,
      [{ action: "*", resource: "*", effect: "allow" }]);
  } finally { await native.close(); }
});

test("purge removes an owned native session without a migration mapping and reconciles lost acknowledgement", async () => {
  const native = await openNative();
  try {
    const original = await native.run(native.sdk.sessions.create({ location: native.scope.location,
      metadata: { renulusProfile: identity.profileId, renulusStore: identity.storeId, operationId: "old-learning-operation" } }));
    const frame = { ...identity, operationId: "independent-purge" };
    let removals = 0;
    const transfer = createSessionTransfer({ sdk: { sessions: { ...native.sdk.sessions, remove: input => {
      removals++;
      return native.sdk.sessions.remove(input).pipe(Effect.flatMap(() => Effect.fail(new Error("synthetic lost purge acknowledgement"))));
    } } }, run: native.run, scope: native.scope, checkCurrent: () => {} });
    const first = transfer.remove(frame, { sessionId: original.id });
    assert.equal(first, transfer.remove(frame, { sessionId: original.id }));
    assert.deepEqual(await first, { state: "removed", sessionId: original.id });
    assert.equal(removals, 1);
    await assert.rejects(native.run(native.sdk.sessions.get({ sessionID: original.id })),
      error => error._tag === "Session.NotFoundError");
  } finally { await native.close(); }
});

test("observer loss and seal retain template ownership until cleanup before retirement", async () => {
  const native = await openNative(), entered = deferred(), gate = deferred();
  let transfer, work;
  try {
    transfer = createSessionTransfer({ sdk: { sessions: { ...native.sdk.sessions, create: input =>
      native.sdk.sessions.create(input).pipe(Effect.flatMap(info => Effect.promise(async () => {
        entered.resolve(); await gate.promise; return info;
      }))),
    } }, run: native.run, scope: native.scope, checkCurrent: () => {} });
    stageAll(transfer);
    work = transfer.commit(identity, targetFor());
    const observer = new AbortController();
    const observation = Promise.race([work, new Promise((_, reject) => observer.signal.addEventListener("abort",
      () => reject(new Error("synthetic observer cancelled")), { once: true }))]);
    await entered.promise;
    observer.abort();
    await assert.rejects(observation, /synthetic observer cancelled/);
    assert.deepEqual(transfer.retire(identity), { state: "pending" });
    transfer.seal();
    assert.throws(() => stageAll(transfer, { ...identity, operationId: "fresh-after-seal" }), { code: "transfer_stopping" });
    let settled = false;
    const drain = transfer.settled().then(() => { settled = true; });
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(settled, false);
    gate.resolve();
    await assert.rejects(work, { code: "transfer_stopping" });
    await drain;
    assert.deepEqual(transfer.retire(identity), { state: "retired" });
    assert.throws(() => transfer.stage(identity, { chunk: "different erased payload" }), { code: "transfer_retired" });
    assert.equal((await native.run(native.sdk.sessions.list())).data.length, 0);
  } finally {
    gate.resolve();
    await work?.catch(() => {});
    transfer?.seal();
    await transfer?.settled();
    await native.close();
  }
});

test("revocation during native read prevents export and successful observation", async () => {
  const native = await openNative(), entered = deferred(), gate = deferred();
  let work;
  try {
    stageAll(native.transfer);
    await native.transfer.commit(identity, targetFor());
    let revoked = false, exports = 0;
    const transfer = createSessionTransfer({ sdk: { sessions: { ...native.sdk.sessions,
      get: input => native.sdk.sessions.get(input).pipe(Effect.flatMap(info => Effect.promise(async () => {
        entered.resolve(); await gate.promise; return info;
      }))),
      export: input => { exports++; return native.sdk.sessions.export(input); },
    } }, run: native.run, scope: native.scope, checkCurrent: () => {
      if (revoked) throw Object.assign(new Error("synthetic current scope revoked"), { code: "synthetic_revoked" });
    } });
    stageAll(transfer);
    work = transfer.inspect(identity, targetFor());
    await entered.promise;
    revoked = true;
    gate.resolve();
    await assert.rejects(work, { code: "synthetic_revoked" });
    assert.equal(exports, 0);
  } finally { gate.resolve(); await work?.catch(() => {}); await native.close(); }
});

test("incomplete stages cannot begin native observation or import", async () => {
  const native = await openNative();
  try {
    let reads = 0;
    const transfer = createSessionTransfer({ sdk: { sessions: { ...native.sdk.sessions, get: input => {
      reads++; return native.sdk.sessions.get(input);
    } } }, run: native.run, scope: native.scope, checkCurrent: () => {} });
    transfer.stage(identity, { ...targetFor(), partIndex: 0, partCount: 2, totalBytes: 100, chunk: "{" });
    await assert.rejects(async () => transfer.commit(identity, targetFor()), { code: "transfer_stage_incomplete" });
    assert.equal(reads, 0);
    assert.equal((await native.run(native.sdk.sessions.list())).data.length, 0);
  } finally { await native.close(); }
});

test("terminal failed cancelled and interrupted legacy text remains exact unknown-lineage history", async () => {
  const native = await openNative();
  try {
    for (const outcome of ["completed", "cancelled", "failed", "interrupted"]) {
      const source = { ...bundle, conversationId: "legacy-" + outcome, messages: [bundle.messages[0],
        { ...bundle.messages[1], content: "Exact partial retained text: " + outcome, legacyOutcome: outcome }] };
      const frame = { ...identity, operationId: "import-" + outcome };
      stageAll(native.transfer, frame, source);
      const result = await native.transfer.commit(frame, targetFor(source));
      const retained = await native.run(native.sdk.sessions.export({ sessionID: Session.ID.make(result.sessionId), sanitize: false }));
      const answer = Schema.encodeSync(SessionMessage.Info)(retained.messages[1]);
      assert.equal(answer.content[0].text, source.messages[1].content);
      assert.deepEqual(answer.metadata.legacy.citations, source.messages[1].citations);
      assert.equal(answer.metadata.legacy.outcome, outcome);
      assert.equal(answer.metadata.lineage, "unknown");
      assert.equal(answer.finish, undefined);
      assert.equal(retained.info.outcome, undefined);
    }
  } finally { await native.close(); }
});

test("template creation acknowledgement failure cleans its exact identity and sanitizes native faults", async () => {
  const native = await openNative();
  try {
    const transfer = createSessionTransfer({ sdk: { sessions: { ...native.sdk.sessions, create: input =>
      native.sdk.sessions.create(input).pipe(Effect.flatMap(() => Effect.fail(new Error("synthetic private error marker")))),
    } }, run: native.run, scope: native.scope, checkCurrent: () => {} });
    stageAll(transfer);
    await assert.rejects(transfer.commit(identity, targetFor()), error =>
      error.code === "transfer_native_failed" && !String(error).includes("private error marker"));
    await transfer.settled();
    assert.equal((await native.run(native.sdk.sessions.list())).data.length, 0);
    assert.deepEqual(transfer.retire(identity), { state: "retired" });
  } finally { await native.close(); }
});

test("failed template cleanup retains ownership and drain retries only the exact cleanup", async () => {
  const native = await openNative();
  let allowCleanup = false, transfer, templateId;
  try {
    transfer = createSessionTransfer({ sdk: { sessions: { ...native.sdk.sessions,
      create: input => { templateId = input.id; return native.sdk.sessions.create(input); },
      remove: input => allowCleanup ? native.sdk.sessions.remove(input) : Effect.fail(new Error("synthetic cleanup unavailable")),
    } }, run: native.run, scope: native.scope, checkCurrent: () => {} });
    stageAll(transfer);
    await assert.rejects(transfer.commit(identity, targetFor()));
    assert.deepEqual(transfer.retire(identity), { state: "pending" });
    await assert.rejects(transfer.settled());
    assert.equal((await native.run(native.sdk.sessions.get({ sessionID: templateId }))).id, templateId);
    allowCleanup = true;
    transfer.seal();
    await transfer.settled();
    assert.equal((await native.run(native.sdk.sessions.list())).data.length, 0);
    assert.deepEqual(transfer.retire(identity), { state: "retired" });
  } finally {
    allowCleanup = true;
    await transfer?.settled().catch(() => {});
    if (templateId) {
      let retained;
      try { retained = await native.run(native.sdk.sessions.get({ sessionID: templateId })); }
      catch (error) { if (error._tag !== "Session.NotFoundError") throw error; }
      if (retained) await native.run(native.sdk.sessions.remove({ sessionID: templateId }));
    }
    await native.close();
  }
});

test("legacy UTC microsecond timestamps survive exactly in provenance through native millisecond storage", async () => {
  const native = await openNative();
  try {
    const source = { ...bundle, messages: [{ ...bundle.messages[1],
      createdAt: "2026-10-10T10:00:01.123456+00:00", completedAt: "2026-10-10T10:00:02.654321+00:00" }] };
    stageAll(native.transfer, identity, source);
    await native.transfer.commit(identity, targetFor(source));
    const retained = await native.run(native.sdk.sessions.export({ sessionID: Session.ID.make(targetFor(source).sessionId), sanitize: false }));
    assert.equal(retained.messages[0].metadata.legacy.createdAt, source.messages[0].createdAt);
    assert.equal(retained.messages[0].metadata.legacy.completedAt, source.messages[0].completedAt);
  } finally { await native.close(); }
});

test("only the exact native missing-session outcome establishes absence", async () => {
  const native = await openNative();
  try {
    stageAll(native.transfer);
    assert.deepEqual(await native.transfer.inspect(identity, targetFor()), { state: "absent", ...targetFor() });
    for (const error of [new Error("synthetic not found"), { _tag: "NotFoundError" }, { _tag: "SessionNotFoundError" }]) {
      const transfer = createSessionTransfer({ sdk: { sessions: { ...native.sdk.sessions,
        get: () => Effect.fail(error),
        create: () => assert.fail("unknown read failure cannot admit an import"),
      } }, run: native.run, scope: native.scope, checkCurrent: () => {} });
      stageAll(transfer);
      await assert.rejects(transfer.inspect(identity, targetFor()), { code: "transfer_native_failed" });
      await assert.rejects(transfer.commit(identity, targetFor()), { code: "transfer_native_failed" });
    }
  } finally { await native.close(); }
});

test("retired opaque identities free staged bytes but remain bounded without payload replay or eviction", async () => {
  const native = await openNative();
  try {
    for (let index = 0; index < 256; index++) {
      const frame = { ...identity, operationId: "retired-" + index };
      stageAll(native.transfer, frame);
      assert.deepEqual(native.transfer.retire(frame), { state: "retired" });
    }
    const old = { ...identity, operationId: "retired-0", attemptId: "changed-attempt" };
    assert.throws(() => native.transfer.stage(old, { chunk: "erased and changed" }), { code: "transfer_retired" });
    assert.throws(() => native.transfer.commit(old, {}), { code: "transfer_retired" });
    assert.deepEqual(native.transfer.retire(old), { state: "retired" });
    assert.throws(() => stageAll(native.transfer, { ...identity, operationId: "record-257" }), { code: "transfer_capacity" });
    assert.equal((await native.run(native.sdk.sessions.list())).data.length, 0);
  } finally { await native.close(); }
});

test("exact document digest and deterministic target are both required before native work", async () => {
  const native = await openNative();
  try {
    const document = JSON.stringify(bundle);
    assert.throws(() => native.transfer.stage(identity, { ...targetFor(), bundleDigest: "0".repeat(64),
      partIndex: 0, partCount: 1, totalBytes: Buffer.byteLength(document), chunk: document }), { code: "transfer_digest_mismatch" });
    assert.throws(() => native.transfer.stage({ ...identity, operationId: "wrong-target" },
      { ...targetFor(), sessionId: "ses_" + "0".repeat(64), partIndex: 0, partCount: 1,
        totalBytes: Buffer.byteLength(document), chunk: document }), { code: "transfer_target_mismatch" });
    assert.equal((await native.run(native.sdk.sessions.list())).data.length, 0);
  } finally { await native.close(); }
});

test("concurrent inspection observers join one retained native readback", async () => {
  const native = await openNative(), entered = deferred(), gate = deferred();
  let transfer, first;
  try {
    stageAll(native.transfer);
    await native.transfer.commit(identity, targetFor());
    let exports = 0;
    transfer = createSessionTransfer({ sdk: { sessions: { ...native.sdk.sessions, export: input => {
      exports++;
      return native.sdk.sessions.export(input).pipe(Effect.flatMap(retained => Effect.promise(async () => {
        entered.resolve(); await gate.promise; return retained;
      })));
    } } }, run: native.run, scope: native.scope, checkCurrent: () => {} });
    stageAll(transfer);
    first = transfer.inspect(identity, targetFor());
    const second = transfer.inspect(identity, targetFor());
    await entered.promise;
    assert.equal(first, second);
    assert.deepEqual(transfer.retire(identity), { state: "pending" });
    gate.resolve();
    assert.deepEqual(await first, { state: "verified", ...targetFor(), messageCount: 2 });
    assert.equal(exports, 1);
    assert.deepEqual(transfer.retire(identity), { state: "retired" });
  } finally { gate.resolve(); await first?.catch(() => {}); await transfer?.settled(); await native.close(); }
});

test("a matching native digest header cannot admit changed citation or message bytes", async () => {
  const native = await openNative();
  try {
    stageAll(native.transfer);
    await native.transfer.commit(identity, targetFor());
    const sessionID = Session.ID.make(targetFor().sessionId);
    const retained = await native.run(native.sdk.sessions.export({ sessionID, sanitize: false }));
    for (const poisoned of [
      { ...retained.messages[1], content: [{ type: "text", text: "changed retained answer" }] },
      { ...retained.messages[1], metadata: { ...retained.messages[1].metadata, legacy: {
        ...retained.messages[1].metadata.legacy, citations: [{ passage_id: "other-passage", locators: [{ page: 99 }] }] } } },
    ]) {
      await native.run(native.sdk.sessions.remove({ sessionID }));
      await native.run(native.sdk.sessions.import({ ...retained, messages: [retained.messages[0], poisoned], location: native.scope.location }));
      const transfer = createSessionTransfer({ sdk: native.sdk, run: native.run, scope: native.scope, checkCurrent: () => {} });
      stageAll(transfer);
      await assert.rejects(transfer.inspect(identity, targetFor()), { code: "transfer_conflict" });
      await assert.rejects(transfer.commit(identity, targetFor()), { code: "transfer_conflict" });
      const existing = await native.run(native.sdk.sessions.export({ sessionID, sanitize: false }));
      assert.deepEqual(existing.messages[1], poisoned);
    }
  } finally { await native.close(); }
});
