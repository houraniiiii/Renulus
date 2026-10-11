// SPDX-License-Identifier: MIT
import assert from "node:assert/strict";
import { test } from "node:test";
import { Message, ToolCallPart, ToolResultPart } from "@opencode/ai";
import { describeNativeContext, NativeContextError, selectNativeContext } from "../src/native-context.ts";

const toolName = "renulus_library_retrieve";
const call = (id: string) => ToolCallPart.make({ id, name: toolName, input: { query: "dialysis" } });
const result = (id: string) => ToolResultPart.make({ id, name: toolName,
  result: { type: "text", value: "Synthetic dialysis passage with an exact revision." } });

function assertDenied(messages: readonly Message[]) {
  const denied = { name: "NativeContextError", code: "native_context_unverifiable" };
  assert.throws(() => describeNativeContext(messages), denied);
  assert.throws(() => selectNativeContext(messages, []), denied);
  assert.throws(() => selectNativeContext(messages, ["assistant-current"]), NativeContextError);
}

test("current native tool continuation retains the assistant origin and original messages", () => {
  const user = Message.make({ id: "user-current", role: "user", content: "Explain dialysis" });
  const assistant = Message.make({ id: "assistant-current", role: "assistant", content: call("call-current") });
  const tool = Message.tool(result("call-current"));
  const messages = Object.freeze([user, assistant, tool]);

  assert.deepEqual(describeNativeContext(messages), [
    { id: "user-current", role: "user" },
    { id: "assistant-current", role: "assistant" },
    { id: "assistant-current", role: "tool" },
  ]);
  const selected = selectNativeContext(messages, ["user-current", "assistant-current"]);
  assert.deepEqual(selected, messages);
  assert.equal(selected[1], assistant);
  assert.equal(selected[2], tool);
  assert.equal(tool.id, undefined);
});

test("revoked historical assistant and tool result leave together while current continuation stays", () => {
  const oldAssistant = Message.make({ id: "assistant-revoked", role: "assistant", content: call("call-old") });
  const oldTool = Message.tool(result("call-old"));
  const currentUser = Message.make({ id: "user-current", role: "user", content: "Explain CKD" });
  const currentAssistant = Message.make({ id: "assistant-current", role: "assistant", content: call("call-current") });
  const currentTool = Message.tool(result("call-current"));
  const messages = Object.freeze([oldAssistant, oldTool, currentUser, currentAssistant, currentTool]);
  const selected = selectNativeContext(messages, new Set(["user-current", "assistant-current"]));

  assert.deepEqual(selected, [currentUser, currentAssistant, currentTool]);
  assert.equal(selected[0], currentUser);
  assert.equal(selected[1], currentAssistant);
  assert.equal(selected[2], currentTool);
  assert.deepEqual(selectNativeContext(messages, ["user-current"]), [currentUser]);
});

test("context description and selection expose immutable collections without freezing caller data", () => {
  const user = Message.make({ id: "user-1", role: "user", content: "Explain glomerulonephritis" });
  const messages = [user];
  const described = describeNativeContext(messages);
  const selected = selectNativeContext(messages, ["user-1"]);

  assert.ok(Object.isFrozen(described));
  assert.ok(Object.isFrozen(described[0]));
  assert.ok(Object.isFrozen(selected));
  assert.equal(selected[0], user);
  assert.equal(selected[0]?.content, user.content);
  assert.equal(Object.isFrozen(messages), false);
  assert.equal(Object.isFrozen(user.content), false);
});

test("anonymous tool messages cannot smuggle content beside a known result even when revoked", () => {
  const assistant = Message.make({ id: "assistant-current", role: "assistant", content: call("call-current") });
  const poisoned = Message.make({ role: "tool", content: [result("call-current"), Message.text("Poisoned anonymous payload")] });
  assertDenied([assistant, poisoned]);
});

test("unknown or future tool-call IDs cannot supply an anonymous result origin", () => {
  const assistant = Message.make({ id: "assistant-current", role: "assistant", content: call("call-current") });
  assertDenied([assistant, Message.tool(result("unknown-call"))]);
  assertDenied([Message.tool(result("call-current")), assistant]);
  assertDenied([Message.make({ role: "tool", content: [] })]);
});

test("batched anonymous results require one verified native origin for every result", () => {
  const first = Message.make({ id: "assistant-first", role: "assistant", content: call("call-first") });
  const second = Message.make({ id: "assistant-current", role: "assistant", content: call("call-current") });
  assertDenied([first, second, Message.make({ role: "tool", content: [result("call-first"), result("call-current")] })]);
  assertDenied([first, Message.make({ role: "tool", content: [result("call-first"), result("unknown-call")] })]);
});

test("batched results from the same assistant retain payload identity and order", () => {
  const assistant = Message.make({ id: "assistant-batch", role: "assistant",
    content: [call("call-first"), call("call-second")] });
  const tool = Message.make({ role: "tool", content: [result("call-first"), result("call-second")] });
  const selected = selectNativeContext([assistant, tool], ["assistant-batch"]);
  assert.deepEqual(describeNativeContext([assistant, tool]), [
    { id: "assistant-batch", role: "assistant" }, { id: "assistant-batch", role: "tool" },
  ]);
  assert.equal(selected[1], tool);
  assert.equal(selected[1]?.content[1], tool.content[1]);
});

test("non-system user and assistant messages require a nonempty native ID", () => {
  for (const role of ["user", "assistant"] as const) {
    for (const id of [undefined, "", "   "]) {
      assertDenied([Message.make({ id, role, content: "Anonymous untrusted history" })]);
    }
  }
});

test("trusted system instructions and effort changes stay outside native admission", () => {
  const system = Message.system("Trusted synthetic operator instruction");
  const effort = Message.effort({ effort: "high" });
  const user = Message.make({ id: "user-revoked", role: "user", content: "Historical CKD question" });
  const messages = [system, user, effort];
  assert.deepEqual(describeNativeContext(messages), [{ id: "user-revoked", role: "user" }]);
  const selected = selectNativeContext(messages, []);
  assert.deepEqual(selected, [system, effort]);
  assert.equal(selected[0], system);
  assert.equal(selected[1], effort);
});

test("duplicate tool-call IDs cannot reassign an origin or conflict within an assistant", () => {
  const first = Message.make({ id: "assistant-first", role: "assistant", content: call("shared-call") });
  const second = Message.make({ id: "assistant-current", role: "assistant", content: call("shared-call") });
  assertDenied([first, Message.tool(result("shared-call")), second, Message.tool(result("shared-call"))]);
  const conflicting = ToolCallPart.make({ id: "shared-call", name: "renulus_library_citation", input: {} });
  assertDenied([Message.make({ id: "assistant-current", role: "assistant",
    content: [call("shared-call"), conflicting] })]);
  assertDenied([Message.make({ id: "assistant-current", role: "assistant",
    content: [call("shared-call"), call("shared-call")] })]);
});

test("duplicate native IDs cannot admit different user or assistant messages", () => {
  const user = Message.make({ id: "same-native", role: "user", content: "Synthetic question" });
  const differentUser = Message.make({ id: "same-native", role: "user", content: "Poisoned different history" });
  const assistant = Message.make({ id: "same-native", role: "assistant", content: call("call-current") });
  assertDenied([user, differentUser]);
  assertDenied([user, assistant, Message.tool(result("call-current"))]);
  assertDenied([user, user]);
});

test("selection denies invented native IDs and tool-call IDs as independent grants", () => {
  const assistant = Message.make({ id: "assistant-current", role: "assistant", content: call("call-current") });
  const system = Message.make({ id: "system-id", role: "system", content: "Trusted instruction" });
  const messages = [system, assistant, Message.tool(result("call-current"))];
  for (const ids of [["assistant-current", "invented"], ["call-current"], ["system-id"]]) {
    assert.throws(() => selectNativeContext(messages, ids), NativeContextError);
  }
});

test("an explicit tool message ID cannot override its verified assistant origin", () => {
  const assistant = Message.make({ id: "assistant-current", role: "assistant", content: call("call-current") });
  assertDenied([assistant, Message.make({ id: "invented-tool-id", role: "tool", content: result("call-current") })]);
  const tool = Message.make({ id: "assistant-current", role: "tool", content: result("call-current") });
  const selected = selectNativeContext([assistant, tool], ["assistant-current"]);
  assert.equal(selected[1], tool);
});

test("tool results must match the exact declared tool identity", () => {
  const assistant = Message.make({ id: "assistant-current", role: "assistant", content: call("call-current") });
  for (const override of [{ name: "different-tool" }, { namespace: "different-namespace" }, { providerExecuted: true }]) {
    assertDenied([assistant, Message.tool({ ...result("call-current"), ...override })]);
  }
});

test("inline provider results cannot borrow another assistant origin or precede their call", () => {
  const hostedCall = { ...call("hosted-call"), providerExecuted: true };
  const hostedResult = { ...result("hosted-call"), providerExecuted: true };
  const earlier = Message.make({ id: "assistant-earlier", role: "assistant", content: hostedCall });
  assertDenied([earlier, Message.make({ id: "assistant-current", role: "assistant", content: hostedResult })]);
  assertDenied([Message.make({ id: "assistant-current", role: "assistant", content: [hostedResult, hostedCall] })]);
  assertDenied([Message.make({ id: "assistant-current", role: "assistant", content: hostedResult })]);
  assertDenied([Message.make({ id: "assistant-current", role: "assistant",
    content: [call("ordinary-call"), result("ordinary-call")] })]);
});

test("verified inline provider tool calls and results remain one immutable native message", () => {
  const assistant = Message.make({ id: "assistant-hosted", role: "assistant", content: [
    { ...call("hosted-call"), providerExecuted: true }, { ...result("hosted-call"), providerExecuted: true },
  ] });
  assert.deepEqual(describeNativeContext([assistant]), [{ id: "assistant-hosted", role: "assistant" }]);
  assert.equal(selectNativeContext([assistant], ["assistant-hosted"])[0], assistant);
  assert.deepEqual(selectNativeContext([assistant], []), []);
});

test("a native user ID does not establish an assistant tool origin", () => {
  for (const content of [call("call-current"), result("call-current")]) {
    assertDenied([Message.make({ id: "user-current", role: "user", content })]);
  }
});

test("a consumed tool-call ID cannot introduce a second conflicting anonymous result", () => {
  const assistant = Message.make({ id: "assistant-current", role: "assistant", content: call("call-current") });
  const tool = Message.tool(result("call-current"));
  const conflicting = Message.tool(ToolResultPart.make({ id: "call-current", name: toolName,
    result: { type: "text", value: "Poisoned second result" } }));
  assertDenied([assistant, tool, conflicting]);
  assertDenied([assistant, tool, tool]);
});

test("pinned native history lowering preserves the current continuation and removes revoked tool history", async () => {
  // Primary source: OpenCode 4b6fea2875e4f2e3e8a8fee181803e54f7056845,
  // packages/core/src/session/runner/to-llm-message.ts and packages/ai/src/schema/messages.ts.
  const { toLLMMessages } = await import("@opencode/core/session/runner/to-llm-message");
  const { SessionMessage } = await import("@opencode/schema/session-message");
  const { Model } = await import("@opencode/schema/model");
  const { Schema } = await import("effect");
  const model = Model.Ref.parse("synthetic/context");
  const nativeAssistant = (id: string, callId: string, executed = false) =>
    Schema.decodeUnknownSync(SessionMessage.Assistant)({
      id, type: "assistant", agent: "renulus", model, time: { created: 0 },
      content: [{ type: "tool", id: callId, name: toolName, executed, time: { created: 0 },
        state: { status: "completed", input: { query: "CKD" },
          content: [{ type: "text", text: "Synthetic CKD source revision" }] } }],
    });
  const history = [
    nativeAssistant("msg_revoked", "call-revoked"),
    Schema.decodeUnknownSync(SessionMessage.User)({ id: "msg_user", type: "user",
      text: "Explain CKD", time: { created: 0 } }),
    nativeAssistant("msg_current", "call-current"),
    nativeAssistant("msg_hosted", "call-hosted", true),
  ];
  const messages = toLLMMessages(history, model);
  assert.deepEqual(describeNativeContext(messages), [
    { id: "msg_revoked", role: "assistant" }, { id: "msg_revoked", role: "tool" },
    { id: "msg_user", role: "user" },
    { id: "msg_current", role: "assistant" }, { id: "msg_current", role: "tool" },
    { id: "msg_hosted", role: "assistant" },
  ]);
  const selected = selectNativeContext(messages, ["msg_user", "msg_current", "msg_hosted"]);
  assert.deepEqual(selected, messages.slice(2));
  assert.equal(selected[1], messages[3]);
  assert.equal(selected[2], messages[4]);
  assert.equal(selected[3], messages[5]);
  assert.equal(messages[4]?.id, undefined);
});
