// SPDX-License-Identifier: MIT
import assert from "node:assert/strict";
import { test } from "node:test";
import { childAuthorityNativeFixture } from "./fixtures/child-authority-native.ts";

function deferred() {
  let resolve!: () => void;
  return { promise: new Promise<void>(done => { resolve = done; }), resolve: () => resolve() };
}

test("adopted native subagent job cannot complete before its actual scope finalizer", { timeout: 20_000 }, async () => {
  const native = await childAuthorityNativeFixture();
  const { Effect, Scope, Context, Option } = await import("effect");
  const bodyReturned = deferred(), finalizerEntered = deferred(), release = deferred();
  let started: Promise<unknown> | undefined;
  try {
    started = native.run(Effect.scoped(native.jobs.start({ id: "held-finalizer", type: "subagent", run: Effect.gen(function* () {
      const scope = Option.getOrThrow(Context.getOption(yield* Effect.context(), Scope.Scope));
      yield* Scope.addFinalizer(scope, Effect.promise(() => {
        finalizerEntered.resolve(); return release.promise;
      }));
      bodyReturned.resolve();
      return "Synthetic evidence report";
    }) })));
    await bodyReturned.promise;
    await finalizerEntered.promise;
    assert.equal((await native.run(native.jobs.get("held-finalizer")))?.status, "running",
      "Native done/status must not outrun the adopted resource finalizer");
    let observed = false;
    const completed = native.run(native.jobs.wait({ id: "held-finalizer" })).then(result => { observed = true; return result; });
    await new Promise(done => setTimeout(done, 10));
    assert.equal(observed, false);
    release.resolve();
    assert.equal((await completed).info?.output, "Synthetic evidence report");
    assert.deepEqual(await native.requests(), []);
  } finally { release.resolve(); await started; await native.close(); }
});

test("model selectors and invalid work are refused without reservations or echoed private diagnostics", { timeout: 20_000 }, async () => {
  const native = await childAuthorityNativeFixture({ permission: "allow" });
  const { LLMEvent } = await import("@opencode/ai");
  const work = { description: "Review synthetic evidence", prompt: "PRIVATE_WORK_CANARY", background: false };
  const invalid = [{ ...work, model: "PRIVATE_SELECTOR_CANARY" }, { ...work, agent: "evidence-review" },
    { ...work, sessionID: native.parent.id }, { ...work, grant_epoch: 999 }, { ...work, background: "false" },
    { ...work, description: " " }, { ...work, prompt: "x".repeat(16001) }];
  try {
    await native.push(native.TestLLM.toolCalls(...invalid.map((input, index) => LLMEvent.toolCall({
      id: `invalid-child-${index}`, name: "subagent", input }))), native.TestLLM.text("Synthetic refused selectors", "parent-answer"));
    await native.run(native.sdk.sessions.prompt({ sessionID: native.parent.id, id: native.input.id, text: "Synthetic parked resource check" }));
    await native.run(native.sdk.sessions.wait({ sessionID: native.parent.id }));
    assert.deepEqual(native.callbacks, []);
    assert.deepEqual((await native.run(native.sdk.sessions.list({ parentID: native.parent.id, limit: 10 }))).data, []);
    const messages = (await native.run(native.sdk.message.list({ sessionID: native.parent.id, limit: 20 }))).data;
    const results = messages.flatMap(message => message.type === "assistant" ? message.content.filter(part => part.type === "tool") : []);
    assert.equal(results.length, invalid.length);
    for (const result of results) {
      assert.equal(result.state.status, "error");
      assert.equal(result.state.status === "error" && JSON.stringify(result.state.error).includes("child_invalid_work"), true);
      assert.equal(result.state.status === "error" && /PRIVATE_/.test(JSON.stringify(result.state.error)), false);
    }
    assert.equal((await native.requests()).length, 2);
  } finally { await native.close(); }
});

test("family Stop rejects the actual permission waiter before draining its foreground tool", { timeout: 20_000 }, async () => {
  const native = await childAuthorityNativeFixture({ permission: "ask" });
  try {
    await native.push(native.TestLLM.tool("actual-child-call", "subagent", { description: "Review synthetic evidence",
      prompt: "Review the synthetic learning evidence.", background: false }));
    await native.run(native.sdk.sessions.prompt({ sessionID: native.parent.id, id: native.input.id, text: "Synthetic parked resource check" }));
    let pending = await native.run(native.sdk.permission.list({ sessionID: native.parent.id }));
    for (let read = 0; read < 200 && pending.length === 0; read++) {
      await new Promise(done => setTimeout(done, 5));
      pending = await native.run(native.sdk.permission.list({ sessionID: native.parent.id }));
    }
    assert.equal(pending.length, 1);
    const stopped = await native.run(native.children.familyStop(native.parentBinding, 1000));
    assert.equal(stopped.settled, true);
    assert.equal(stopped.owned, 0);
    assert.deepEqual(await native.run(native.sdk.permission.list({ sessionID: native.parent.id })), []);
    assert.deepEqual((await native.run(native.sdk.sessions.list({ parentID: native.parent.id, limit: 10 }))).data, []);
    assert.equal((await native.requests()).length, 1);
  } finally { await native.close(); }
});

test("native cancelled status and wait do not release adopted Job resource ownership or close", { timeout: 20_000 }, async () => {
  const native = await childAuthorityNativeFixture();
  const { Effect, Scope, Context, Option } = await import("effect");
  const running = deferred(), entered = deferred(), release = deferred();
  let cancellation: Promise<unknown> | undefined;
  try {
    await native.run(Effect.scoped(native.jobs.start({ id: "cancel-held-resource", type: "subagent", run: Effect.gen(function* () {
      const scope = Option.getOrThrow(Context.getOption(yield* Effect.context(), Scope.Scope));
      yield* Scope.addFinalizer(scope, Effect.promise(() => { entered.resolve(); return release.promise; }));
      running.resolve();
      return yield* Effect.never;
    }) })));
    await running.promise;
    cancellation = native.run(native.jobs.cancel("cancel-held-resource"));
    await entered.promise;
    assert.equal((await native.run(native.jobs.wait({ id: "cancel-held-resource" }))).info?.status, "cancelled");
    assert.equal(native.children.status().jobs, 1);
    const closing = native.children.close(25);
    assert.equal(native.children.status().state, "closing");
    const held = await native.run(closing);
    assert.equal(held.settled, false);
    assert.equal(held.jobs, 1);
    release.resolve();
    await cancellation;
    const settled = await native.run(native.children.settlement(1000));
    assert.equal(settled.state, "closed");
    assert.equal(settled.owned, 0);
    assert.equal((await native.run(native.children.close(25))).settled, true);
    assert.deepEqual(await native.requests(), []);
  } finally { release.resolve(); await cancellation; await native.close(); }
});

test("current authority is checked at the actual native Inbox publication after prompt preparation awaits", { timeout: 20_000 }, async () => {
  const { Effect } = await import("effect");
  const reached = deferred(), release = deferred();
  const native = await childAuthorityNativeFixture({ permission: "allow",
    beforeChildPrompt: () => Effect.promise(() => { reached.resolve(); return release.promise; }) });
  try {
    await native.push(native.TestLLM.tool("actual-child-call", "subagent", { description: "Review synthetic evidence",
      prompt: "Review the synthetic learning evidence.", background: false }), native.TestLLM.text("Synthetic refused child admission", "parent-answer"));
    await native.run(native.sdk.sessions.prompt({ sessionID: native.parent.id, id: native.input.id, text: "Synthetic parked resource check" }));
    await reached.promise;
    native.authority.epoch++; native.authority.current = false; release.resolve();
    await native.run(native.sdk.sessions.wait({ sessionID: native.parent.id }));
    const child = (await native.run(native.sdk.sessions.list({ parentID: native.parent.id, limit: 10 }))).data[0];
    assert.ok(child);
    assert.equal(native.bindings.size, 1, "This refusal is after actual child binding and authenticated input admission");
    assert.equal(native.callbacks.some(item => item.command === "child.admit_input"), true);
    assert.deepEqual((await native.run(native.sdk.message.list({ sessionID: child.id, limit: 20 }))).data, []);
    assert.deepEqual(await native.run(native.sdk.sessions.inbox.list({ sessionID: child.id })), [], "No stale native USER bytes may publish");
    const requests = await native.requests();
    assert.equal(requests.length, 2, "Only parent setup and explicit refusal continuation run");
    assert.equal(requests.some(request => JSON.stringify(request.messages).includes("You are a subagent spawned by another session.")), false);
    assert.equal(native.callbacks.some(item => item.command === "child.report"), false);
  } finally { release.resolve(); await native.close(); }
});

test("family Stop seals before awaiting and retains actual child generation and job finalizers on observer timeout", { timeout: 20_000 }, async () => {
  const native = await childAuthorityNativeFixture({ permission: "allow" });
  const { Stream, Effect } = await import("effect");
  const entered = deferred(), release = deferred();
  try {
    const held = Stream.fromIterable(native.TestLLM.text("Synthetic completed body with held native finalizer", "child-answer")).pipe(
      Stream.ensuring(Effect.promise(() => { entered.resolve(); return release.promise; })));
    let parentRequests = 0;
    await native.serve(request => JSON.stringify(request.messages).includes("You are a subagent spawned by another session.") ? held :
      parentRequests++ === 0 ? native.TestLLM.tool("actual-child-call", "subagent", { description: "Review synthetic evidence",
        prompt: "Review the synthetic learning evidence.", background: true }) : native.TestLLM.text("Synthetic root background answer", "parent-answer"));
    await native.run(native.sdk.sessions.prompt({ sessionID: native.parent.id, id: native.input.id, text: "Synthetic parked resource check" }));
    await entered.promise;
    await native.run(native.sdk.sessions.wait({ sessionID: native.parent.id }));
    const stopping = native.children.familyStop(native.parentBinding, 25);
    assert.equal(native.children.status(native.parentBinding).state, "sealed", "Seal is synchronous, before the returned Effect runs");
    const heldStatus = await native.run(stopping);
    assert.equal(heldStatus.settled, false);
    assert.ok(heldStatus.owned > 0, "A bounded observation cannot release actual cleanup ownership");
    assert.equal(native.callbacks.some(item => item.command === "child.report"), false);
    const child = (await native.run(native.sdk.sessions.list({ parentID: native.parent.id, limit: 10 }))).data[0];
    assert.ok(child);
    await assert.rejects(native.run(native.sdk.sessions.prompt({ sessionID: child.id,
      id: native.input.id, text: "Attempted stale replay" })));
    release.resolve();
    const settled = await native.run(native.children.settlement(1000, native.parentBinding));
    assert.equal(settled.settled, true, JSON.stringify(settled));
    assert.equal(settled.owned, 0);
    assert.equal(native.callbacks.some(item => item.command === "child.report" || item.command === "child.consume_report"), false);
    assert.deepEqual(await native.run(native.sdk.sessions.inbox.list({ sessionID: native.parent.id })), []);
    assert.equal((await native.requests()).length, 3);
  } finally { release.resolve(); await native.close(); }
});

test("detached native report is authenticated and parked without consumption or a parent wake", { timeout: 20_000 }, async () => {
  const native = await childAuthorityNativeFixture({ permission: "allow" });
  const { Stream, Effect } = await import("effect");
  const release = deferred(), childEntered = deferred();
  try {
    const held = Stream.fromEffect(Effect.promise(() => { childEntered.resolve(); return release.promise; })).pipe(
      Stream.flatMap(() => Stream.fromIterable(native.TestLLM.text("Synthetic detached report", "child-answer"))));
    let parentRequests = 0;
    await native.serve(request => {
      if (JSON.stringify(request.messages).includes("You are a subagent spawned by another session.")) return held;
      return parentRequests++ === 0 ? native.TestLLM.tool("actual-child-call", "subagent", { description: "Review synthetic evidence",
        prompt: "Review the synthetic learning evidence.", background: true }) : native.TestLLM.text("Synthetic root background answer", "parent-answer");
    });
    await native.run(native.sdk.sessions.prompt({ sessionID: native.parent.id, id: native.input.id, text: "Synthetic parked resource check" }));
    await childEntered.promise;
    await native.run(native.sdk.sessions.wait({ sessionID: native.parent.id }));
    release.resolve();
    const child = (await native.run(native.sdk.sessions.list({ parentID: native.parent.id, limit: 10 }))).data[0];
    assert.ok(child);
    await native.run(native.sdk.sessions.wait({ sessionID: child.id }));
    let pending = await native.run(native.sdk.sessions.inbox.list({ sessionID: native.parent.id }));
    for (let read = 0; read < 200 && pending.length === 0; read++) {
      await new Promise(done => setTimeout(done, 5));
      pending = await native.run(native.sdk.sessions.inbox.list({ sessionID: native.parent.id }));
    }
    assert.equal(native.callbacks.filter(item => item.command === "child.report").length, 1, "Detached report must authenticate before native delivery");
    assert.equal(pending.length, 1, "The actual detached notification stays parked in the native inbox");
    assert.equal(pending[0].delivery, "queue", "A parked report must support an explicit queue-to-steer admission");
    const observed = native.callbacks.find(item => item.command === "child.observe_job")!;
    assert.equal(observed.payload.notification_id, pending[0].id);
    assert.equal(native.callbacks.find(item => item.command === "child.report")!.payload.notification_id, pending[0].id);
    assert.equal(native.callbacks.filter(item => item.command === "child.consume_report").length, 0);
    assert.equal((await native.requests()).length, 3, "Detached notification cannot wake another parent generation");
    await native.run(native.sdk.sessions.prompt({ sessionID: native.parent.id, id: native.input.id, text: "Synthetic parked resource check" }));
    await native.run(native.sdk.sessions.wait({ sessionID: native.parent.id }));
    assert.equal((await native.run(native.sdk.message.list({ sessionID: native.parent.id, limit: 20 }))).data.some(message =>
      message.type === "synthetic" && message.id === pending[0].id), false, "Plain prompt replay cannot adopt an unconsumed detached report");
    assert.equal((await native.run(native.sdk.sessions.inbox.list({ sessionID: native.parent.id }))).length, 1);
    assert.equal(native.callbacks.filter(item => item.command === "child.consume_report").length, 0);
    assert.equal((await native.requests()).length, 3);
    const steered = await native.run(native.sdk.sessions.inbox.update({ sessionID: native.parent.id, inboxID: pending[0].id, delivery: "steer" })).then(() => true, () => false);
    assert.equal(native.callbacks.filter(item => item.command === "child.consume_report").length, 1, "Explicit current-admitted steering consumes the parked report");
    assert.equal(steered, true);
    await native.run(native.sdk.sessions.wait({ sessionID: native.parent.id }));
    assert.equal(native.callbacks.filter(item => item.command === "child.check").at(-1)?.payload.stage, "before_wake");
    assert.equal((await native.run(native.sdk.message.list({ sessionID: native.parent.id, limit: 20 }))).data.some(message =>
      message.type === "synthetic" && message.id === pending[0].id), true);
    assert.deepEqual(await native.run(native.sdk.sessions.inbox.list({ sessionID: native.parent.id })), []);
    assert.equal((await native.requests()).length, 4);
  } finally { release.resolve(); await native.close(); }
});

test("revocation during the actual Inbox projector rolls back detached promotion before native commit", { timeout: 20_000 }, async () => {
  const { Stream, Effect } = await import("effect");
  const projectionEntered = deferred(), releaseProjection = deferred(), releaseChild = deferred(), childEntered = deferred();
  let holdProjection = false;
  const native = await childAuthorityNativeFixture({ permission: "allow", beforeParentPromotionCommit: () =>
    holdProjection ? Effect.promise(() => { projectionEntered.resolve(); return releaseProjection.promise; }) : Effect.void });
  try {
    const held = Stream.fromEffect(Effect.promise(() => { childEntered.resolve(); return releaseChild.promise; })).pipe(
      Stream.flatMap(() => Stream.fromIterable(native.TestLLM.text("Synthetic detached final-commit report", "child-answer"))));
    let parentRequests = 0;
    await native.serve(request => JSON.stringify(request.messages).includes("You are a subagent spawned by another session.") ? held :
      parentRequests++ === 0 ? native.TestLLM.tool("actual-child-call", "subagent", { description: "Review synthetic evidence",
        prompt: "Review the synthetic learning evidence.", background: true }) : native.TestLLM.text("Synthetic root answer", "parent-answer"));
    await native.run(native.sdk.sessions.prompt({ sessionID: native.parent.id, id: native.input.id, text: "Synthetic parked resource check" }));
    await childEntered.promise;
    await native.run(native.sdk.sessions.wait({ sessionID: native.parent.id }));
    releaseChild.resolve();
    const child = (await native.run(native.sdk.sessions.list({ parentID: native.parent.id, limit: 10 }))).data[0];
    await native.run(native.sdk.sessions.wait({ sessionID: child.id }));
    let pending = await native.run(native.sdk.sessions.inbox.list({ sessionID: native.parent.id }));
    for (let read = 0; read < 200 && pending.length === 0; read++) {
      await new Promise(done => setTimeout(done, 5));
      pending = await native.run(native.sdk.sessions.inbox.list({ sessionID: native.parent.id }));
    }
    assert.equal(pending.length, 1);
    assert.equal(native.callbacks.filter(item => item.command === "child.consume_report").length, 0);
    holdProjection = true;
    await native.run(native.sdk.sessions.inbox.update({ sessionID: native.parent.id, inboxID: pending[0].id, delivery: "steer" }));
    await projectionEntered.promise;
    assert.equal(native.callbacks.filter(item => item.command === "child.consume_report").length, 1);
    native.authority.epoch++; native.authority.current = false; releaseProjection.resolve();
    await native.run(native.sdk.sessions.wait({ sessionID: native.parent.id }));
    assert.equal((await native.run(native.sdk.message.list({ sessionID: native.parent.id, limit: 20 }))).data.some(message =>
      message.type === "synthetic" && message.id === pending[0].id), false, "The final local gate must abort the actual native projector transaction");
    assert.equal((await native.run(native.sdk.sessions.inbox.list({ sessionID: native.parent.id }))).some(item => item.id === pending[0].id), true);
    assert.equal((await native.requests()).length, 3, "No model request follows the refused native promotion");
    const settled = await native.run(native.children.familyStop(native.parentBinding, 1000));
    assert.equal(settled.owned, 0);
    assert.equal(settled.settled, true);
  } finally { releaseChild.resolve(); releaseProjection.resolve(); await native.close(); }
});

test("native child binds its allocated USER input and returns only an authenticated consumed report", { timeout: 20_000 }, async () => {
  const native = await childAuthorityNativeFixture({ permission: "allow" });
  try {
    await native.push(native.TestLLM.tool("actual-child-call", "subagent", { description: "Review synthetic evidence",
      prompt: "Review the synthetic learning evidence.", background: false }),
      native.TestLLM.text("Synthetic exact child report", "child-answer"), native.TestLLM.text("Synthetic root answer", "parent-answer"));
    await native.run(native.sdk.sessions.prompt({ sessionID: native.parent.id, id: native.input.id, text: "Synthetic parked resource check" }));
    await native.run(native.sdk.sessions.wait({ sessionID: native.parent.id }));
    const child = (await native.run(native.sdk.sessions.list({ parentID: native.parent.id, limit: 10 }))).data[0];
    assert.ok(child);
    const binding = native.bindings.get(child.id);
    assert.ok(binding, "Actual child USER binding must be registered before native prompt");
    const messages = await native.run(native.sdk.message.list({ sessionID: child.id, limit: 20 }));
    assert.equal(messages.data.find(message => message.type === "user")?.id, binding.input_id);
    assert.notEqual(binding.input_id, native.callbacks.find(item => item.command === "child.prepare")?.payload.invocation &&
      (native.callbacks.find(item => item.command === "child.prepare")!.payload.invocation as { message_id: string }).message_id);
    assert.deepEqual(native.callbacks.filter(item => item.command !== "child.check").map(item => item.command),
      ["child.prepare", "child.admit_input", "child.observe_job", "child.report", "child.consume_report"]);
    const report = native.callbacks.find(item => item.command === "child.report")!;
    assert.equal(report.binding.input_id, binding.input_id);
    assert.equal(report.payload.output, "Synthetic exact child report");
    const { createHash } = await import("node:crypto");
    assert.equal(report.payload.report_digest, createHash("sha256").update("Synthetic exact child report").digest("hex"));
    assert.equal((await native.requests()).length, 3);
  } finally { await native.close(); }
});

test("revocation while the actual native subagent permission waits prevents child construction", { timeout: 20_000 }, async () => {
  const native = await childAuthorityNativeFixture({ permission: "ask" });
  try {
    await native.push(native.TestLLM.tool("actual-child-call", "subagent", { description: "Review synthetic evidence",
      prompt: "Review the synthetic learning evidence.", background: false }),
      native.TestLLM.text("Synthetic child report", "child-answer"), native.TestLLM.text("Synthetic parent answer", "parent-answer"));
    await native.run(native.sdk.sessions.prompt({ sessionID: native.parent.id, id: native.input.id, text: "Synthetic parked resource check" }));
    let request: { id: import("@opencode/core/permission").Permission.ID } | undefined;
    for (let read = 0; read < 200; read++) {
      request = (await native.run(native.sdk.permission.list({ sessionID: native.parent.id })))[0];
      if (request) break;
      await new Promise(done => setTimeout(done, 5));
    }
    assert.ok(request, "The original native permission assertion must be awaiting approval");
    native.authority.epoch++;
    native.authority.current = false;
    await native.run(native.sdk.permission.reply({ sessionID: native.parent.id, requestID: request.id, decision: "once" }));
    await native.run(native.sdk.sessions.wait({ sessionID: native.parent.id }));
    assert.deepEqual((await native.run(native.sdk.sessions.list({ parentID: native.parent.id, limit: 10 }))).data, [],
      "A stale approval must not create a native child");
    assert.equal(native.callbacks.filter(item => item.command === "child.prepare").length, 1);
    assert.equal(native.callbacks.some(item => item.command === "child.check" && item.payload.stage === "before_create"), false);
    assert.equal((await native.requests()).length, 2, "Only synthetic parent setup and refusal continuation may run");
  } finally { await native.close(); }
});
