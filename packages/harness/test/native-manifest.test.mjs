import assert from "node:assert/strict";
import { test } from "node:test";
import { LLMRequest, Message, Media, SystemPart, ToolDefinition } from "@opencode/ai";
import { OpenAICompatibleChat } from "@opencode/ai/protocols/openai-compatible-chat";
import { OpenAIResponses } from "@opencode/ai/protocols/openai-responses";
import { Route } from "@opencode/ai/route/client";
import { Auth } from "@opencode/ai/route/auth";
import { Effect } from "effect";
import { captureNativeManifest } from "../src/native-manifest.ts";

const png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA6fptVAAAACklEQVR4nGNgAAAAAgABSK+kcQAAAABJRU5ErkJggg==";
const request = () => new LLMRequest({
  model: OpenAICompatibleChat.route.with({ provider: "synthetic", endpoint: { baseURL: "https://synthetic.invalid/v1" } })
    .model({ id: "synthetic-only" }),
  system: [SystemPart.make("Synthetic renal education"), SystemPart.make("Use eligible evidence")],
  messages: [Message.user([Message.text("Explain "), Message.text("dialysis"),
    Message.media(Media.base64(png, "image/png"))]),
    Message.assistant([{ type: "tool-call", id: "call-1", name: "library_passage", input: { query: "dialysis" } }]),
    Message.make({ role: "tool", content: [{ type: "tool-result", id: "call-1", name: "library_passage",
      result: { type: "json", value: { text: "Synthetic eligible passage" } } }] })],
  tools: [ToolDefinition.make({ name: "library_passage", description: "Retrieve eligible evidence",
    inputSchema: { type: "object", properties: { query: { type: "string" } }, required: ["query"] } })],
});

test("capture retains ordered system, image identity and exact tool pairs in immutable v1 input", () => {
  const input = request();
  const manifest = captureNativeManifest(input);
  assert.deepEqual(manifest, { version: 1, system: "Synthetic renal education\nUse eligible evidence",
    messages: [{ role: "user", content: [{ type: "text", text: "Explain dialysis" },
      { type: "image", media_type: "image/png", sha256: "eaa4a94ea300e0d2c775968cbe42f0b5b51ceafdeb73d64e9efddf6d4e880865", bytes: 67, detail: null }] },
    { role: "assistant", content: [{ type: "tool-call", id: "call-1", name: "library_passage", arguments_json: '{"query":"dialysis"}' }] },
    { role: "tool", content: [{ type: "tool-result", id: "call-1", output_text: '{"text":"Synthetic eligible passage"}' }] }],
    tools: [{ name: "library_passage", description: "Retrieve eligible evidence",
      parameters_json: '{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}' }] });
  assert.throws(() => { manifest.messages[0].content[0].text = "mutation"; }, TypeError);
  input.messages[0].content[0].text = "changed original";
  assert.equal(manifest.messages[0].content[0].text, "Explain dialysis");
});

test("native argument capture denies objects that rewrite themselves during JSON serialization", () => {
  const input = request();
  input.messages[1].content[0].input = { date: new Date("2026-10-11T00:00:00Z") };
  assert.throws(() => captureNativeManifest(input), error => error.reason?._tag === "InvalidRequest");
});

test("array serialization callbacks are rejected without being invoked", () => {
  const input = request();
  let invoked = 0;
  const items = ["original"];
  items.toJSON = () => { invoked++; return ["replacement"]; };
  input.messages[1].content[0].input = { items };
  assert.throws(() => captureNativeManifest(input), error => error.reason?._tag === "InvalidRequest");
  assert.equal(invoked, 0);
});

test("Responses capture uses the route's effective native image metadata namespace", async () => {
  const original = request();
  const model = Route.make({ id: "openai-responses", provider: "codex",
    protocol: OpenAIResponses.protocol, endpoint: { baseURL: "https://synthetic.invalid/v1", path: "/responses" },
    auth: Auth.none, transport: OpenAIResponses.httpTransport }).model({ id: "synthetic-only" });
  const input = LLMRequest.update(original, { model });
  input.messages[0].content[2].providerMetadata = { openresponses: { detail: "high" } };
  const wire = await Effect.runPromise(OpenAIResponses.protocol.body.from(input));
  assert.equal(wire.input[0].content.find(part => part.type === "input_image").detail, "high");
  assert.equal(captureNativeManifest(input).messages[0].content[1].detail, "high");
  input.messages[0].content[2].providerMetadata = { openai: { detail: "high" } };
  assert.throws(() => captureNativeManifest(input), error => error.reason?._tag === "InvalidRequest");
});

test("explicit null image detail is rejected on a native openai metadata route", async () => {
  const input = LLMRequest.update(request(), { model: OpenAIResponses.route.model({ id: "synthetic-only" }) });
  input.messages[0].content[2].providerMetadata = { openai: { detail: "low" } };
  const wire = await Effect.runPromise(OpenAIResponses.protocol.body.from(input));
  assert.equal(wire.input[0].content.find(part => part.type === "input_image").detail, "low");
  assert.equal(captureNativeManifest(input).messages[0].content[1].detail, "low");
  input.messages[0].content[2].providerMetadata = { openai: { detail: null } };
  await assert.rejects(Effect.runPromise(OpenAIResponses.protocol.body.from(input)));
  assert.throws(() => captureNativeManifest(input), error => error.reason?._tag === "InvalidRequest");
});

test("array accessors, sparse values, custom properties and prototypes cannot run or change capture", () => {
  let invoked = 0;
  const accessor = [0];
  Object.defineProperty(accessor, "0", { enumerable: true, get: () => { invoked++; return "changed"; } });
  const prototype = [0];
  Object.setPrototypeOf(prototype, { toJSON: () => { invoked++; return ["changed"]; } });
  const custom = [0];
  custom.extra = "unaccounted";
  for (const items of [accessor, prototype, custom, Array(1)]) {
    const input = request();
    input.messages[1].content[0].input = { items };
    assert.throws(() => captureNativeManifest(input), error => error.reason?._tag === "InvalidRequest");
  }
  assert.equal(invoked, 0);
  const input = request();
  input.messages[1].content[0].input = { items: ["retained", 1, null] };
  assert.equal(captureNativeManifest(input).messages[1].content[0].arguments_json, '{"items":["retained",1,null]}');
});

for (const [name, change] of [
  ["opaque reasoning", input => { input.messages[0].content.push({ type: "reasoning", text: "opaque" }); }],
  ["native compaction", input => { input.messages[0].content.push({ type: "compaction", provider: "synthetic", encrypted: "opaque" }); }],
  ["remote image", input => { input.messages[0].content[2] = Message.media(Media.url("https://synthetic.invalid/image.png", { mediaType: "image/png" })); }],
  ["mismatched tool result", input => { input.messages[2].content[0].id = "other-call"; }],
  ["provider executed call", input => { input.messages[1].content[0].providerExecuted = true; }],
  ["tool namespace", input => { input.tools = [{ type: "namespace", name: "opaque", tools: input.tools }]; }],
  ["system message outside ordered system", input => { input.messages.push(Message.system("unaccounted")); }],
  ["nonfinite arguments", input => { input.messages[1].content[0].input = { value: Infinity }; }],
  ["content tool result with unproven lowering", input => { input.messages[2].content[0].result = { type: "content", value: [{ type: "text", text: "unproven" }] }; }],
  ["Chat image detail that native drops", input => { input.messages[0].content[2].providerMetadata = { openai: { detail: "high" } }; }],
  ["oversized manifest", input => { input.messages[0].content[0].text = "x".repeat(1_048_576); }],
]) {
  test(`native v1 capture refuses ${name}`, () => {
    const input = request();
    change(input);
    assert.throws(() => captureNativeManifest(input), error => error.reason?._tag === "InvalidRequest");
  });
}
