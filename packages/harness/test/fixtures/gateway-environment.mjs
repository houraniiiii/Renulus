import "./provider-environment.mjs";
import { DomainClient } from "../../src/domain-ipc.ts";
import { LLMRequest, LanguageModel, Message, SystemPart, Media, ToolDefinition } from "@opencode/ai";
import { Effect, Layer, ManagedRuntime } from "effect";
import { LayerNode } from "@opencode/util/effect/layer-node";
import { SessionRunnerModel } from "@opencode/core/session/runner/model";
import { SessionModelRequest } from "@opencode/core/session/model-request";
import { SessionModelTransport } from "@opencode/core/session/model-transport";
import { PluginHooks } from "@opencode/core/plugin/hooks";

export const binding = Object.freeze({ operation_id: "synthetic-operation", attempt_id: "synthetic-attempt",
  session_id: "synthetic-session", input_id: "synthetic-input", cancellation_id: "synthetic-cancellation" });
export const png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA6fptVAAAACklEQVR4nGNgAAAAAgABSK+kcQAAAABJRU5ErkJggg==";
export function currentResolved() {
  return SessionRunnerModel.resolved(LanguageModel.make({ provider: "openai", id: "untrusted-model" }), {
    capabilities: { tools: false, input: ["text"], output: ["text"] },
    cost: { input: 0, output: 0 }, limit: { input: 16, output: 8, context: 32 }, transport: "websocket" });
}

/** Actual pinned preparation and hook registry; no host/profile/store or default transport. */
export async function nativePrimary(resolved, timeline, shape = () => {}) {
  const runtime = ManagedRuntime.make(SessionModelRequest.layer.pipe(Layer.provideMerge(Layer.mergeAll(
    LayerNode.compile(PluginHooks.node), Layer.succeed(SessionModelTransport.Service, {
      bind: () => { throw new Error("synthetic-websocket-refused"); }, close: () => Effect.void, closeAll: Effect.void,
    }),
  ))));
  try {
    return await runtime.runPromise(Effect.gen(function* () {
      const hooks = yield* PluginHooks.Service;
      let captured;
      yield* hooks.register("session", "context", event => Effect.sync(() => {
        timeline.push("native-context");
        event.system = [SystemPart.make("Synthetic post-hook teaching instruction")];
        event.messages = [Message.user([Message.text("Synthetic post-hook dialysis"), Message.media(Media.base64(png, "image/png"))])];
        event.tools = { eligible_passage: event.tools.library_passage };
        shape(event);
        captured = { system: structuredClone(event.system), messages: structuredClone(event.messages) };
      }));
      yield* hooks.register("session", "model.request", () => Effect.sync(() => { timeline.push("native-model-request"); }));
      const service = yield* SessionModelRequest.Service;
      const prepared = yield* service.primary({
        session: { id: binding.session_id, projectID: "synthetic-project" }, agent: "renulus", model: resolved,
        tools: { definitions: [ToolDefinition.make({ name: "library_passage", description: "Synthetic passage", inputSchema: { type: "object" } })],
          execute: () => Effect.die(new Error("synthetic-unused-tool")) },
        system: [], messages: [Message.user("Synthetic pre-hook input")], webSocket: "session",
      });
      // Manifest evidence is plain data. Native constructors reject cloned MediaAsset instances.
      return { prepared, unfiltered: { ...prepared.request, ...captured, tools: structuredClone(prepared.request.tools) } };
    }).pipe(Effect.scoped));
  } finally { await runtime.dispose(); }
}
export function plan(model = "mimo-v2.6-pro", patch = {}) {
  const codex = model.startsWith("gpt-");
  return { dispatch_id: "synthetic-dispatch", binding,
    role: { version: "synthetic-version", purpose: "explain", model_id: model, output_tokens: 64, dispatch_limit: 2 },
    request_kind: "primary",
    route: { provider_id: codex ? "codex" : "opencode-go", catalog_model_id: model, wire_model_id: model,
      endpoint: codex ? "https://api.openai.com/v1/responses" : "https://opencode.ai/zen/go/v1/chat/completions",
      protocol: codex ? "openai-responses" : "openai-chat", credential_ref: "synthetic-protected-reference",
      credential_epoch: 1, catalogue_listed: false },
    native_capabilities: { tools: true, input: ["text", "image"], output: ["text"] },
    limits: { input_tokens: 1024, output_tokens: 64, window_tokens: 2048 }, required_capabilities: ["text"],
    bounds: { max_request_bytes: 8192, max_response_bytes: 8192, max_frame_bytes: 32768 }, ...patch };
}
export function request(patch = {}) {
  // This deliberately differs from the trusted role: request.model grants no routing authority.
  return new LLMRequest({ model: LanguageModel.make({ provider: "openai", id: "untrusted-model" }),
    system: [], messages: [Message.user("Explain synthetic dialysis")], tools: [], ...patch });
}
export function sse(model = "mimo-v2.6-pro", text = "Synthetic safe teaching") {
  const events = model.startsWith("gpt-") ? [
    { type: "response.output_item.added", item: { type: "message", id: "synthetic-message" } },
    { type: "response.output_text.delta", item_id: "synthetic-message", delta: text },
    { type: "response.output_item.done", item: { type: "message", id: "synthetic-message", content: [{ type: "output_text", text }] } },
    { type: "response.completed", response: { id: "synthetic-response", model, status: "completed" } },
  ] : [{ content: text }, {}].map((delta, index) => ({ id: "synthetic-response", model,
    choices: [{ index: 0, delta, finish_reason: index ? "stop" : null }] }));
  return events.map(event => "data: " + JSON.stringify(event) + "\n\n").join("")
    + (model.startsWith("gpt-") ? "" : "data: [DONE]\n\n");
}
export function result(body = sse(), patch = {}) {
  return { status: 200, headers: { "content-type": "text/event-stream" },
    body_base64: Buffer.from(body).toString("base64"), permit_id: "synthetic-permit", ...patch };
}
export function toolSse(model) {
  const events = model.startsWith("gpt-") ? [
    { type: "response.output_item.added", item: { type: "function_call", id: "synthetic-item", call_id: "native-call", name: "library_passage", arguments: "" } },
    { type: "response.output_item.done", item: { type: "function_call", id: "synthetic-item", call_id: "native-call", name: "library_passage", arguments: "{}" } },
    { type: "response.completed", response: { id: "synthetic-response", model, status: "completed" } },
  ] : [
    { id: "synthetic-response", model, choices: [{ index: 0, delta: { tool_calls: [{ index: 0, id: "native-call", type: "function", function: { name: "library_passage", arguments: "{}" } }] }, finish_reason: null }] },
    { id: "synthetic-response", model, choices: [{ index: 0, delta: {}, finish_reason: "tool_calls" }] },
  ];
  return events.map(event => "data: " + JSON.stringify(event) + "\n\n").join("") + (model.startsWith("gpt-") ? "" : "data: [DONE]\n\n");
}
export function channel(respond = () => result(), limits = {}) {
  const frames = [];
  const identity = { protocol: "renulus-harness/1", profile_id: "synthetic-profile",
    store_id: "synthetic-store", generation: "synthetic-generation", token: "synthetic-authentication-canary" };
  let domain;
  const settle = (frame, body) => {
    const { kind, command, payload, ...authenticated } = frame;
    domain.receive({ ...authenticated, kind: "domain_result", ...body });
  };
  const reply = (frame, body) => settle(frame, { outcome: "committed_reference", result: body });
  domain = new DomainClient(identity, async bytes => {
    const frame = JSON.parse(bytes); frames.push(frame);
    if (frame.kind === "domain_request" && respond) queueMicrotask(() => reply(frame, respond(frame)));
  }, { maxFrameBytes: 65536, ...limits });
  return { domain, frames, reply, settle };
}
