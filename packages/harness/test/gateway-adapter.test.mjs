import "./fixtures/gateway-environment.mjs";
import assert from "node:assert/strict";
import test from "node:test";
import { Effect, Stream, Fiber } from "effect";
import { createGatewayAdapter } from "../src/gateway-adapter.ts";
import { binding, plan, request, channel, result, sse, png, toolSse } from "./fixtures/gateway-environment.mjs";

test("authenticated safe gateway 401 reaches the native caller as Authentication without a receipt or replay", async () => {
  for (const mode of ["generate", "stream"]) {
    const wire = channel(null);
    const adapter = await createGatewayAdapter({ domain: wire.domain, beforePrepare: () => Effect.succeed(plan()), validateImages: () => Effect.void });
    try {
      const prepared = await Effect.runPromise(adapter.prepare(binding, request()));
      const operation = mode === "generate" ? adapter.client.generate(prepared)
        : adapter.client.stream(prepared).pipe(Stream.runCollect);
      const running = Effect.runPromise(operation.pipe(Effect.result));
      await until(() => wire.frames.length === 1);
      wire.settle(wire.frames[0], { outcome: "rejected_before_admission",
        error: { code: "authentication_required", status: 401, retryable: false } });
      const failed = await running;
      assert.equal(failed._tag, "Failure");
      assert.equal(failed.failure.reason._tag, "Authentication");
      assert.equal(failed.failure.reason.message, "Reconnect the selected subscription.");
      assert.equal(adapter.receipt(prepared), undefined);
      assert.equal(wire.domain.state().active, 0);
      await assert.rejects(Effect.runPromise(adapter.client.generate(prepared)));
      assert.equal(wire.frames.length, 1);
    } finally { wire.domain.disconnect(); await adapter.close(); }
  }
});

test("authenticated safe gateway subscription limit reaches native generate and stream as RateLimit without replay", async () => {
  for (const mode of ["generate", "stream"]) {
    const wire = channel(null);
    const adapter = await createGatewayAdapter({ domain: wire.domain, beforePrepare: () => Effect.succeed(plan()), validateImages: () => Effect.void });
    try {
      const prepared = await Effect.runPromise(adapter.prepare(binding, request()));
      const operation = mode === "generate" ? adapter.client.generate(prepared)
        : adapter.client.stream(prepared).pipe(Stream.runCollect);
      const running = Effect.runPromise(operation.pipe(Effect.result));
      await until(() => wire.frames.length === 1);
      wire.settle(wire.frames[0], { outcome: "rejected_before_admission",
        error: { code: "subscription_limit", status: 429, retryable: true } });
      const failed = await running;
      assert.equal(failed._tag, "Failure");
      assert.equal(failed.failure.reason._tag, "RateLimit");
      assert.equal(failed.failure.reason.message, "The selected subscription reached a usage limit.");
      assert.equal(adapter.receipt(prepared), undefined);
      assert.equal(wire.domain.state().active, 0);
      await assert.rejects(Effect.runPromise(adapter.client.generate(prepared)));
      assert.equal(wire.frames.length, 1);
    } finally { wire.domain.disconnect(); await adapter.close(); }
  }
});

test("trusted typed preparation failures retain allowlisted native categories while removing diagnostic canaries", async () => {
  const { AIError, AuthenticationError, RateLimitError, QuotaExceededError, ProviderInternalError, TransportError, InvalidRequestError, HttpContext } = await import("@opencode/ai");
  const canary = crypto.randomUUID();
  for (const [ErrorType, patch, category, message] of [
    [AuthenticationError, {}, "Authentication", "Reconnect the selected subscription."],
    [RateLimitError, { retryAfterMs: 123 }, "RateLimit", "The selected subscription reached a usage limit."],
    [QuotaExceededError, {}, "QuotaExceeded", "The selected subscription reached its quota."],
    [ProviderInternalError, { retryAfterMs: 123 }, "ProviderInternal", "The selected subscription could not finish the request."],
    [TransportError, { transport: "websocket", operation: "read", url: canary, code: canary, recovery: "retry-full" },
      "Transport", "The selected subscription transport was interrupted."],
    [InvalidRequestError, { parameter: canary }, "InvalidRequest", "Trusted model gateway refused the request."],
  ]) {
    const wire = channel();
    const adapter = await createGatewayAdapter({ domain: wire.domain, beforePrepare: () => Effect.fail(new AIError({
      reason: new ErrorType({ message: canary, body: canary, cause: new Error(canary),
        http: new HttpContext({ url: canary, status: 401, headers: { authorization: canary } }), ...patch }) })),
      validateImages: () => Effect.void });
    try {
      const failed = await Effect.runPromise(adapter.prepare(binding, request()).pipe(Effect.result));
      assert.equal(failed._tag, "Failure");
      assert.equal(failed.failure.reason._tag, category);
      assert.equal(failed.failure.reason.message, message);
      assert.ok(!JSON.stringify(failed).includes(canary), "A credential canary survived safe failure mapping");
      assert.ok(!String(failed.failure).includes(canary), "A credential canary survived error text mapping");
      for (const key of ["body", "http", "cause", "retryAfterMs", "rateLimit", "url", "code", "recovery", "parameter"])
        assert.equal(failed.failure.reason[key], undefined);
      assert.equal(wire.frames.length, 0);
    } finally { await adapter.close(); }
  }
});

test("authenticated model and input rejection keeps fixed InvalidRequest guidance through native error sanitization", async () => {
  for (const code of ["model_unavailable", "model_not_found", "model_access_denied", "account_model_unsupported",
    "unsupported_image_input", "image_input_not_supported", "unsupported_input_modality", "unsupported_modality"]) {
    const wire = channel(null);
    const adapter = await createGatewayAdapter({ domain: wire.domain, beforePrepare: () => Effect.succeed(plan()), validateImages: () => Effect.void });
    try {
      const prepared = await Effect.runPromise(adapter.prepare(binding, request()));
      const operation = code === "model_unavailable" ? adapter.client.generate(prepared)
        : adapter.client.stream(prepared).pipe(Stream.runCollect);
      const running = Effect.runPromise(operation.pipe(Effect.result));
      await until(() => wire.frames.length === 1);
      wire.settle(wire.frames[0], { outcome: "rejected_before_admission", error: { code, status: 409, retryable: false } });
      const failed = await running;
      assert.equal(failed._tag, "Failure");
      assert.equal(failed.failure.reason._tag, "InvalidRequest");
      assert.equal(failed.failure.reason.message, "The selected model or input is unavailable. Refresh its capabilities.");
      assert.equal(adapter.receipt(prepared), undefined);
      assert.equal(wire.domain.state().active, 0);
      await assert.rejects(Effect.runPromise(adapter.client.generate(prepared)));
      assert.equal(wire.frames.length, 1);
    } finally { wire.domain.disconnect(); await adapter.close(); }
  }
});

test("authenticated safe gateway provider and transport failures retain sanitized native categories without retry", async () => {
  for (const [code, category, message] of [
    ["provider_stream_failed", "ProviderInternal", "The selected subscription could not finish the request."],
    ["provider_unavailable", "ProviderInternal", "The selected subscription could not finish the request."],
    ["transport_unavailable", "Transport", "The selected subscription transport was interrupted."],
  ]) {
    const wire = channel(null);
    const adapter = await createGatewayAdapter({ domain: wire.domain, beforePrepare: () => Effect.succeed(plan()), validateImages: () => Effect.void });
    try {
      const prepared = await Effect.runPromise(adapter.prepare(binding, request()));
      const running = Effect.runPromise(adapter.client.generate(prepared).pipe(Effect.result));
      await until(() => wire.frames.length === 1);
      wire.settle(wire.frames[0], { outcome: "rejected_before_admission", error: { code, status: 503, retryable: true } });
      const failed = await running;
      assert.equal(failed._tag, "Failure");
      assert.equal(failed.failure.reason._tag, category);
      assert.equal(failed.failure.reason.message, message);
      assert.equal(failed.failure.reason.recovery, undefined);
      assert.equal(failed.failure.reason.retryAfterMs, undefined);
      assert.equal(adapter.receipt(prepared), undefined);
      await assert.rejects(Effect.runPromise(adapter.client.generate(prepared)));
      assert.equal(wire.frames.length, 1);
    } finally { wire.domain.disconnect(); await adapter.close(); }
  }
});

test("gateway error categories require exact safe codes statuses and terminal outcomes", async () => {
  const canary = crypto.randomUUID();
  const errors = [
    { code: "authentication_required", status: 429 }, { code: "subscription_limit", status: 401 },
    { code: "model_unavailable", status: 401 }, { code: "provider_stream_failed", status: 401 },
    { code: "transport_unavailable", status: 429 }, { code: canary, status: 401 },
  ].map(error => ({ outcome: "rejected_before_admission", error }));
  for (const outcome of ["committed_reference", "cancelled_settled", "uncertain_after_disconnect"])
    errors.push({ outcome, error: { code: "authentication_required", status: 401 } });
  errors.push({ outcome: "committed_reference", result: result(canary, { status: 401 }) });
  for (const reply of errors) {
    const wire = channel(null);
    const adapter = await createGatewayAdapter({ domain: wire.domain, beforePrepare: () => Effect.succeed(plan()), validateImages: () => Effect.void });
    try {
      const prepared = await Effect.runPromise(adapter.prepare(binding, request()));
      const running = Effect.runPromise(adapter.client.generate(prepared).pipe(Effect.result));
      await until(() => wire.frames.length === 1);
      wire.settle(wire.frames[0], reply);
      const failed = await running;
      assert.equal(failed._tag, "Failure");
      assert.equal(failed.failure.reason._tag, "InvalidRequest");
      assert.equal(failed.failure.reason.message, "Trusted model gateway refused the request.");
      assert.ok(!JSON.stringify(failed).includes(canary), "An unknown error diagnostic canary surfaced");
      assert.equal(adapter.receipt(prepared), undefined);
      await assert.rejects(Effect.runPromise(adapter.client.generate(prepared)));
      assert.equal(wire.frames.length, 1);
    } finally { wire.domain.disconnect(); await adapter.close(); }
  }
});

test("owned IO preserves typed native categories but rebuilds every diagnostic field and rejects reason-shaped objects", async () => {
  const { AIError, AuthenticationError, RateLimitError, QuotaExceededError, ProviderInternalError, TransportError } = await import("@opencode/ai");
  const { DomainClient } = await import("../src/domain-ipc.ts");
  const canary = crypto.randomUUID();
  for (const [ErrorType, patch, category] of [
    [AuthenticationError, {}, "Authentication"], [RateLimitError, { retryAfterMs: 123 }, "RateLimit"],
    [QuotaExceededError, {}, "QuotaExceeded"], [ProviderInternalError, {}, "ProviderInternal"],
    [TransportError, { transport: "websocket", operation: "read", url: canary, recovery: "retry-full" }, "Transport"],
    [null, {}, "InvalidRequest"],
  ]) {
    let calls = 0;
    const error = ErrorType ? new AIError({ reason: new ErrorType({ message: canary, body: canary, cause: new Error(canary), ...patch }) })
      : { reason: { _tag: "Authentication", message: canary } };
    class RejectingDomainClient extends DomainClient {
      request(bound, command, payload) {
        assert.deepEqual(bound, binding);
        assert.equal(command, "model.dispatch");
        assert.deepEqual(Object.keys(payload).sort(), ["dispatch_id", "serialized_request"]);
        calls++;
        return Promise.reject(error);
      }
    }
    const domain = new RejectingDomainClient({ protocol: "renulus-harness/1", profile_id: "synthetic-profile",
      store_id: "synthetic-store", generation: "synthetic-generation", token: "synthetic-channel-token" }, async () => {});
    const adapter = await createGatewayAdapter({ domain, beforePrepare: () => Effect.succeed(plan()), validateImages: () => Effect.void });
    try {
      const prepared = await Effect.runPromise(adapter.prepare(binding, request()));
      const failed = await Effect.runPromise(adapter.client.generate(prepared).pipe(Effect.result));
      assert.equal(failed._tag, "Failure");
      assert.equal(failed.failure.reason._tag, category);
      assert.ok(!JSON.stringify(failed).includes(canary), "An IO diagnostic canary surfaced");
      assert.ok(!String(failed.failure).includes(canary), "An IO diagnostic canary survived error text");
      for (const key of ["body", "http", "cause", "retryAfterMs", "url", "recovery"])
        assert.equal(failed.failure.reason[key], undefined);
      assert.equal(adapter.receipt(prepared), undefined);
      await assert.rejects(Effect.runPromise(adapter.client.generate(prepared)));
      assert.equal(calls, 1);
    } finally { await adapter.close(); }
  }
});

test("trusted preparation reaches native serialized HTTP through two-key model.dispatch and yields its permit receipt", async () => {
  const wire = channel();
  let preparations = 0;
  const adapter = await createGatewayAdapter({ domain: wire.domain,
    beforePrepare: bound => Effect.sync(() => { assert.deepEqual(bound, binding); preparations++; return plan(); }),
    validateImages: () => Effect.void });
  try {
    const original = request();
    const prepared = await Effect.runPromise(adapter.prepare(binding, original));
    assert.equal(prepared.model.id, "mimo-v2.6-pro");
    assert.equal(prepared.generation.maxTokens, 64);
    assert.equal(adapter.receipt(prepared), undefined);
    const response = await Effect.runPromise(adapter.client.generate(prepared));
    assert.equal(response.text, "Synthetic safe teaching");
    assert.equal(preparations, 1);
    assert.equal(wire.frames.length, 1);
    const frame = wire.frames[0];
    assert.equal(frame.command, "model.dispatch");
    assert.deepEqual(Object.keys(frame.payload).sort(), ["dispatch_id", "serialized_request"]);
    const http = frame.payload.serialized_request;
    assert.deepEqual(Object.keys(http).sort(), ["body_base64", "headers", "method", "url"]);
    assert.equal(http.method, "POST");
    assert.equal(http.url, "https://opencode.ai/zen/go/v1/chat/completions");
    assert.equal(http.headers.authorization, undefined);
    const body = JSON.parse(Buffer.from(http.body_base64, "base64"));
    assert.equal(body.model, "mimo-v2.6-pro");
    assert.equal(body.max_completion_tokens, 64);
    assert.deepEqual(adapter.receipt(prepared), { dispatch_id: "synthetic-dispatch", permit_id: "synthetic-permit" });
    assert.equal(adapter.receipt(original), undefined);
  } finally { await adapter.close(); }
});

test("pending, rejected, cancelled and uncertain callbacks never publish a receipt or permit replay", async () => {
  for (const outcome of ["rejected_before_admission", "cancelled_settled", "uncertain_after_disconnect"]) {
    const wire = channel(null);
    const adapter = await createGatewayAdapter({ domain: wire.domain, beforePrepare: () => Effect.succeed(plan()), validateImages: () => Effect.void });
    try {
      const prepared = await Effect.runPromise(adapter.prepare(binding, request()));
      let settled = false;
      const running = Effect.runPromise(adapter.client.generate(prepared).pipe(Effect.result)).then(value => { settled = true; return value; });
      await until(() => wire.frames.length === 1);
      wire.settle(wire.frames[0], { outcome: "accepted_pending", result: {} });
      await new Promise(resolve => setTimeout(resolve, 10));
      assert.equal(settled, false);
      assert.equal(adapter.receipt(prepared), undefined);
      wire.settle(wire.frames[0], { outcome, error: { code: "synthetic-safe-error", status: 401 } });
      assert.equal((await running)._tag, "Failure");
      await assert.rejects(Effect.runPromise(adapter.client.generate(prepared)));
      assert.equal(adapter.receipt(prepared), undefined);
      assert.equal(wire.frames.length, 1);
    } finally { wire.domain.disconnect(); await adapter.close(); }
  }
});

test("close alone cancels buffered stream IO and waits for its actual callback finalizer", { timeout: 6000 }, async () => {
  const wire = channel(null);
  const adapter = await createGatewayAdapter({ domain: wire.domain, beforePrepare: () => Effect.succeed(plan()), validateImages: () => Effect.void });
  const prepared = await Effect.runPromise(adapter.prepare(binding, request()));
  const running = Effect.runPromise(adapter.client.stream(prepared).pipe(Stream.runCollect, Effect.result));
  let closing, closed = false;
  try {
    await until(() => wire.frames.length === 1);
    closing = adapter.close().then(() => { closed = true; });
    await until(() => wire.frames.some(frame => frame.kind === "domain_cancel"));
    await new Promise(resolve => setTimeout(resolve, 20));
    assert.equal(closed, false);
    assert.equal(wire.domain.state().active, 1);
    wire.reply(wire.frames[0], result());
    assert.equal((await running)._tag, "Failure");
    await closing;
    assert.equal(adapter.receipt(prepared), undefined);
    assert.equal(wire.domain.state().accepting, true);
  } finally { wire.domain.disconnect(); await running; await closing; await adapter.close(); }
});

test("a synchronously throwing trusted preparation releases ownership and close can finish", async () => {
  const wire = channel();
  const adapter = await createGatewayAdapter({ domain: wire.domain, beforePrepare: () => { throw new Error(crypto.randomUUID()); }, validateImages: () => Effect.void });
  const failed = await Effect.runPromise(adapter.prepare(binding, request()).pipe(Effect.result));
  assert.equal(failed._tag, "Failure");
  const closed = await Promise.race([adapter.close().then(() => true), new Promise(resolve => setTimeout(() => resolve(false), 100))]);
  assert.equal(closed, true, "Throwing trusted hook retained a preparation lease");
  assert.equal(wire.frames.length, 0);
});

test("close during trusted image validation settles validation but prevents the still-unsent HTTP request", { timeout: 6000 }, async () => {
  const { Media, Message } = await import("@opencode/ai");
  let releaseValidation, validating = false, closed = false;
  const validation = new Promise(resolve => { releaseValidation = resolve; });
  const wire = channel();
  const adapter = await createGatewayAdapter({ domain: wire.domain, beforePrepare: () => Effect.succeed(plan()),
    validateImages: () => Effect.promise(() => { validating = true; return validation; }) });
  const prepared = await Effect.runPromise(adapter.prepare(binding, request({ messages: [Message.user(Message.media(Media.base64(png, "image/png")))] })));
  const running = Effect.runPromise(adapter.client.generate(prepared).pipe(Effect.result));
  let closing;
  try {
    await until(() => validating);
    closing = adapter.close().then(() => { closed = true; });
    await new Promise(resolve => setTimeout(resolve, 20));
    assert.equal(closed, false);
    releaseValidation();
    assert.equal((await running)._tag, "Failure");
    await closing;
    assert.equal(wire.frames.length, 0);
    assert.equal(adapter.receipt(prepared), undefined);
  } finally { releaseValidation(); await running; await closing; await adapter.close(); }
});

test("canonical buffered SSE at its declared byte bound survives base64 expansion without parser stack growth", async () => {
  const text = "x".repeat(512000);
  const body = sse(undefined, text);
  const wire = channel(() => result(body), { maxFrameBytes: 1048576, maxBytes: 4194304 });
  const adapter = await createGatewayAdapter({ domain: wire.domain, beforePrepare: () => Effect.succeed(plan(undefined, {
    bounds: { ...plan().bounds, max_response_bytes: Buffer.byteLength(body), max_frame_bytes: 1048576 } })), validateImages: () => Effect.void });
  try {
    const prepared = await Effect.runPromise(adapter.prepare(binding, request()));
    const response = await Effect.runPromise(adapter.client.generate(prepared));
    assert.equal(response.text.length, 512000);
    assert.equal(adapter.receipt(prepared).permit_id, "synthetic-permit");
  } finally { await adapter.close(); }
});

test("mutating bound input cannot widen the trusted native modalities at consumption", async () => {
  const { Message, Media } = await import("@opencode/ai");
  const wire = channel();
  let validations = 0;
  const adapter = await createGatewayAdapter({ domain: wire.domain, beforePrepare: () => Effect.succeed(plan(undefined, {
    native_capabilities: { tools: false, input: ["text"], output: ["text"] } })), validateImages: () => Effect.sync(() => { validations++; }) });
  try {
    const prepared = await Effect.runPromise(adapter.prepare(binding, request()));
    prepared.messages.push(Message.user(Message.media(Media.base64(png, "image/png"))));
    await assert.rejects(Effect.runPromise(adapter.client.generate(prepared)));
    assert.equal(validations, 0);
    assert.equal(wire.frames.length, 0);
  } finally { await adapter.close(); }
});

test("bindings and role preparations are snapshots and each request uses the newly selected same-subscription route", async () => {
  const originalBinding = { ...binding };
  let hookBinding, releaseHook, started = false, calls = 0, supplied;
  const hook = new Promise(resolve => { releaseHook = resolve; });
  const wire = channel(frame => {
    const model = JSON.parse(Buffer.from(frame.payload.serialized_request.body_base64, "base64")).model;
    return result(sse(model), { permit_id: `synthetic-permit-${wire.frames.length}` });
  });
  const adapter = await createGatewayAdapter({ domain: wire.domain, beforePrepare: bound => Effect.tryPromise({
    try: async () => {
      hookBinding = bound; started = true; calls++;
      if (calls === 1) await hook;
      supplied = plan(calls === 1 ? "mimo-v2.6-pro" : "deepseek-v4.1-flash", { binding: { ...bound }, dispatch_id: `synthetic-dispatch-${calls}` });
      return supplied;
    }, catch: () => { throw new Error("synthetic-hook-failure"); } }), validateImages: () => Effect.void });
  try {
    const preparing = Effect.runPromise(adapter.prepare(originalBinding, request()));
    await until(() => started);
    originalBinding.attempt_id = "mutated-attempt";
    releaseHook();
    const first = await preparing;
    assert.equal(hookBinding.attempt_id, "synthetic-attempt");
    assert.equal(Object.isFrozen(hookBinding), true);
    supplied.route.wire_model_id = "unapproved-model";
    supplied.role.output_tokens = 1000;
    await Effect.runPromise(adapter.client.generate(first));
    const second = await Effect.runPromise(adapter.prepare(binding, request()));
    await Effect.runPromise(adapter.client.generate(second));
    assert.equal(first.model.id, "mimo-v2.6-pro");
    assert.equal(second.model.id, "deepseek-v4.1-flash");
    assert.equal(wire.frames[0].attempt_id, "synthetic-attempt");
    assert.equal(wire.frames.length, 2);
  } finally { releaseHook(); await adapter.close(); }
});

test("both pinned protocols roundtrip native emitted tools and managed-decoded images through fresh bound primary and continuation IO", async () => {
  const { Message, Media, ToolDefinition } = await import("@opencode/ai");
  const { spawnSync } = await import("node:child_process");
  const { default: path } = await import("node:path");
  for (const model of ["mimo-v2.6-pro", "gpt-6.1-sol"]) {
    let preparations = 0, validations = 0;
    const bodies = [];
    const wire = channel(frame => {
      const body = JSON.parse(Buffer.from(frame.payload.serialized_request.body_base64, "base64"));
      bodies.push(body);
      assert.equal(body.model, model);
      assert.equal(body[model.startsWith("gpt-") ? "max_output_tokens" : "max_completion_tokens"], 64);
      return result(bodies.length === 1 ? toolSse(model) : sse(model), { permit_id: `synthetic-permit-${bodies.length}` });
    });
    const adapter = await createGatewayAdapter({ domain: wire.domain, beforePrepare: () => {
      preparations++;
      return Effect.succeed(plan(model, { dispatch_id: `synthetic-dispatch-${preparations}`,
        request_kind: preparations === 1 ? "primary" : "tool-continuation",
        ...(preparations === 1 ? {} : { continuation_of: "synthetic-permit-1" }) }));
    }, validateImages: (bound, images) => Effect.sync(() => {
      assert.deepEqual(bound, binding);
      assert.equal(images.length, 1);
      const decoded = spawnSync("C:/Renulus/dev/python/Scripts/python.exe", ["-c",
        "import json, sys; from renulus.runtime.provider_adapter import validate_harness_images; validate_harness_images(json.load(sys.stdin))"],
      { input: JSON.stringify(images), encoding: "utf8", windowsHide: true, timeout: 30000, maxBuffer: 4096,
        cwd: path.resolve(import.meta.dirname, "../../.."), env: { ...process.env, PYTHONPATH: path.resolve(import.meta.dirname, "../../../runtime") } });
      assert.equal(decoded.status, 0, "Managed image validation failed");
      validations++;
    }) });
    try {
      const tools = [ToolDefinition.make({ name: "library_passage", description: "Synthetic eligible teaching", inputSchema: { type: "object", properties: {} } })];
      const messages = [Message.user([Message.text("Discuss the synthetic teaching image"), Message.media(Media.base64(png, "image/png"))])];
      const primary = await Effect.runPromise(adapter.prepare(binding, request({ tools, messages })));
      const first = await Effect.runPromise(adapter.client.generate(primary));
      assert.equal(first.toolCalls.length, 1);
      const call = first.toolCalls[0];
      const continuation = await Effect.runPromise(adapter.prepare(binding, request({ tools, messages: [...messages, Message.assistant([call]),
        Message.make({ role: "tool", content: [{ type: "tool-result", id: call.id, name: call.name, result: { type: "text", value: "Synthetic eligible transplantation passage" } }] })] })));
      const events = await Effect.runPromise(adapter.client.stream(continuation).pipe(Stream.runCollect));
      assert.ok(events.some(event => event.type === "text-delta" && event.text === "Synthetic safe teaching"));
      assert.deepEqual([preparations, validations, bodies.length], [2, 2, 2]);
      assert.deepEqual(adapter.receipt(primary), { dispatch_id: "synthetic-dispatch-1", permit_id: "synthetic-permit-1" });
      assert.deepEqual(adapter.receipt(continuation), { dispatch_id: "synthetic-dispatch-2", permit_id: "synthetic-permit-2" });
      if (model.startsWith("gpt-")) {
        const pair = bodies[1].input.filter(part => ["function_call", "function_call_output"].includes(part.type));
        assert.equal(pair[0].call_id, pair[1].call_id);
      } else assert.equal(bodies[1].messages[1].tool_calls[0].id, bodies[1].messages[2].tool_call_id);
    } finally { await adapter.close(); }
  }
});

test("preparation failures and missing trusted dependencies fail closed without retaining diagnostic canaries", async () => {
  const { AIError, InvalidRequestError } = await import("@opencode/ai");
  const canary = crypto.randomUUID();
  const wire = channel();
  const adapter = await createGatewayAdapter({ domain: wire.domain, beforePrepare: () => Effect.fail(new AIError({
    reason: new InvalidRequestError({ message: canary }) })), validateImages: () => Effect.void });
  try {
    const failed = await Effect.runPromise(adapter.prepare(binding, request()).pipe(Effect.result));
    assert.equal(failed._tag, "Failure");
    assert.ok(!JSON.stringify(failed).includes(canary), "Preparation diagnostic canary surfaced");
    assert.equal(wire.frames.length, 0);
  } finally { await adapter.close(); }
  for (const options of [{ domain: undefined, beforePrepare: () => Effect.succeed(plan()), validateImages: () => Effect.void },
    { domain: wire.domain, beforePrepare: undefined, validateImages: () => Effect.void },
    { domain: wire.domain, beforePrepare: () => Effect.succeed(plan()), validateImages: undefined }]) {
    await assert.rejects(createGatewayAdapter(options), "Missing trusted dependency was bound");
  }
});

test("trusted native modalities and tools must permit the actual inputs before preparation", async () => {
  const { Media, Message, ToolDefinition } = await import("@opencode/ai");
  const wire = channel();
  let validations = 0;
  for (const [native_capabilities, patch] of [
    [{ tools: true, input: ["text"], output: ["text"] }, { messages: [Message.user(Message.media(Media.base64(png, "image/png")))] }],
    [{ tools: false, input: ["text", "image"], output: ["text"] }, { tools: [ToolDefinition.make({ name: "library_passage", description: "Synthetic eligible passage", inputSchema: { type: "object" } })] }],
  ]) {
    const adapter = await createGatewayAdapter({ domain: wire.domain, beforePrepare: () => Effect.succeed(plan(undefined, { native_capabilities })),
      validateImages: () => Effect.sync(() => { validations++; }) });
    try { await assert.rejects(Effect.runPromise(adapter.prepare(binding, request(patch)))); }
    finally { await adapter.close(); }
  }
  assert.equal(validations, 0);
  assert.equal(wire.frames.length, 0);
});

test("close waits for an outstanding trusted preparation and refuses its late request", { timeout: 6000 }, async () => {
  const wire = channel();
  let finishPreparation;
  const preparation = new Promise(resolve => { finishPreparation = resolve; });
  let started = false, closed = false;
  const adapter = await createGatewayAdapter({ domain: wire.domain, beforePrepare: () => Effect.tryPromise({
    try: () => { started = true; return preparation; }, catch: () => { throw new Error("synthetic-unexpected-hook-failure"); } }),
    validateImages: () => Effect.void });
  const preparing = Effect.runPromise(adapter.prepare(binding, request()).pipe(Effect.result));
  let closing;
  try {
    await until(() => started);
    closing = adapter.close().then(() => { closed = true; });
    await new Promise(resolve => setTimeout(resolve, 20));
    assert.equal(closed, false);
    finishPreparation(plan());
    assert.equal((await preparing)._tag, "Failure");
    await closing;
    assert.equal(wire.frames.length, 0);
    assert.equal(wire.domain.state().accepting, true);
  } finally { finishPreparation(plan()); await preparing; await closing; await adapter.close(); }
});

async function until(predicate) {
  for (let i = 0; i < 100; i++) { if (predicate()) return; await new Promise(resolve => setTimeout(resolve, 5)); }
  assert.fail("Synthetic callback did not reach its expected state");
}
test("interruption and close retain native ownership until actual cancelled callback settlement", { timeout: 6000 }, async () => {
  const wire = channel(null);
  const adapter = await createGatewayAdapter({ domain: wire.domain, beforePrepare: () => Effect.succeed(plan()), validateImages: () => Effect.void });
  const prepared = await Effect.runPromise(adapter.prepare(binding, request()));
  const fiber = Effect.runFork(adapter.client.generate(prepared));
  let interrupted = false, closed = false, interrupting, closing;
  try {
    await until(() => wire.frames.some(frame => frame.kind === "domain_request"));
    interrupting = Effect.runPromise(Fiber.interrupt(fiber)).then(() => { interrupted = true; });
    await until(() => wire.frames.some(frame => frame.kind === "domain_cancel"));
    closing = adapter.close().then(() => { closed = true; });
    await new Promise(resolve => setTimeout(resolve, 20));
    assert.equal(interrupted, false);
    assert.equal(closed, false);
    assert.equal(wire.domain.state().active, 1);
    assert.equal(wire.domain.state().accepting, true);
    assert.equal(adapter.receipt(prepared), undefined);
    wire.reply(wire.frames[0], result());
    await Promise.all([interrupting, closing]);
    assert.equal(wire.domain.state().active, 0);
    assert.equal(adapter.receipt(prepared), undefined);
    assert.deepEqual(wire.frames.map(frame => frame.kind), ["domain_request", "domain_cancel"]);
  } finally { wire.domain.disconnect(); await interrupting; await closing; await adapter.close(); }
});

test("custom HTTP or WS at preparation or consumption cannot escape the trusted adapter", async () => {
  const wire = channel();
  let calls = 0;
  const adapter = await createGatewayAdapter({ domain: wire.domain, beforePrepare: () => Effect.succeed(plan(undefined, { dispatch_id: `synthetic-dispatch-${++calls}` })), validateImages: () => Effect.void });
  try {
    for (const settings of [{ http: () => { throw new Error("synthetic-http-escape"); } }, { webSocket: {} }]) {
      await assert.rejects(Effect.runPromise(adapter.prepare(binding, request(), settings)));
      const prepared = await Effect.runPromise(adapter.prepare(binding, request()));
      await assert.rejects(Effect.runPromise(adapter.client.generate(prepared, settings)));
      await assert.rejects(Effect.runPromise(adapter.client.generate(prepared)));
    }
    const { HttpOptions } = await import("@opencode/ai");
    for (const http of [{ headers: { authorization: "synthetic-auth-canary" } }, { body: { model: "fallback-model" } }, { query: { redirect: "yes" } }]) {
      const prepared = await Effect.runPromise(adapter.prepare(binding, request({ http: new HttpOptions(http) })));
      await assert.rejects(Effect.runPromise(adapter.client.generate(prepared)));
    }
    assert.equal(wire.frames.length, 0);
  } finally { await adapter.close(); }
});

test("final transformed request bytes, payload frame and explicit output ceiling are bounded before domain dispatch", async () => {
  for (const [patch, bounds] of [
    [{}, { ...plan().bounds, max_request_bytes: 32 }],
    [{}, { ...plan().bounds, max_frame_bytes: 32 }],
    [null, plan().bounds],
  ]) {
    const wire = channel();
    const adapter = await createGatewayAdapter({ domain: wire.domain, beforePrepare: () => Effect.succeed(plan(undefined, { bounds })), validateImages: () => Effect.void });
    try {
      const prepared = await Effect.runPromise(adapter.prepare(binding, request(patch ?? {})));
      if (patch === null) prepared.generation.maxTokens = 1000;
      await assert.rejects(Effect.runPromise(adapter.client.generate(prepared)), "Unbounded native body was sent");
      assert.equal(wire.frames.length, 0);
      assert.equal(adapter.receipt(prepared), undefined);
    } finally { await adapter.close(); }
  }
});

test("malformed, noncanonical or oversized gateway results cannot become HTTP or permit receipts", async () => {
  const variants = [
    result(sse(), { status: 302 }), result(sse(), { headers: { "content-type": "text/event-stream", location: "https://synthetic.invalid" } }),
    result(sse(), { headers: { "content-type": "application/json" } }),
    result(sse(), { permit_id: "" }), result(sse(), { extra: "synthetic-sensitive-diagnostic" }),
    result(sse(), { body_base64: Buffer.from(sse()).toString("base64") + "\n" }),
    result(sse(), { body_base64: "Zh==" }), result(sse(), { body_base64: "" }),
  ];
  for (const safeResult of variants) {
    const wire = channel(() => safeResult);
    const adapter = await createGatewayAdapter({ domain: wire.domain, beforePrepare: () => Effect.succeed(plan()), validateImages: () => Effect.void });
    try {
      const prepared = await Effect.runPromise(adapter.prepare(binding, request()));
      const outcome = await Effect.runPromise(adapter.client.generate(prepared).pipe(Effect.result));
      assert.equal(outcome._tag, "Failure", "Unsafe gateway result became native HTTP");
      assert.equal(adapter.receipt(prepared), undefined);
      assert.ok(!JSON.stringify(outcome).includes("synthetic-sensitive-diagnostic"), "Unsafe diagnostic was retained");
    } finally { await adapter.close(); }
  }
  for (const bounds of [{ ...plan().bounds, max_response_bytes: 32 }, { ...plan().bounds, max_frame_bytes: 1000 }]) {
    const wire = channel(() => result(sse(undefined, "x".repeat(1200))));
    const adapter = await createGatewayAdapter({ domain: wire.domain, beforePrepare: () => Effect.succeed(plan(undefined, { bounds })), validateImages: () => Effect.void });
    try {
      const prepared = await Effect.runPromise(adapter.prepare(binding, request()));
      await assert.rejects(Effect.runPromise(adapter.client.generate(prepared)));
      assert.equal(adapter.receipt(prepared), undefined);
    } finally { await adapter.close(); }
  }
});

test("incoherent or repeated trusted preparations fail before any domain IO", async () => {
  const wire = channel();
  const patches = [
    { binding: { ...binding, attempt_id: "foreign-attempt" } }, { dispatch_id: "" },
    { role: { ...plan().role, model_id: "gpt-6-astra" } },
    { role: { ...plan().role, output_tokens: 65 } },
    { limits: { ...plan().limits, window_tokens: 32 } },
    { bounds: { ...plan().bounds, max_frame_bytes: -1 } },
    { request_kind: "fallback" }, { request_kind: "tool-continuation" },
    { continuation_of: "unexpected-primary-permit" },
    { native_capabilities: { tools: true, input: ["text"], output: [] } },
  ];
  for (const patch of patches) {
    const adapter = await createGatewayAdapter({ domain: wire.domain, beforePrepare: () => Effect.succeed(plan(undefined, patch)), validateImages: () => Effect.void });
    try { await assert.rejects(Effect.runPromise(adapter.prepare(binding, request())), "Incoherent preparation was admitted"); }
    finally { await adapter.close(); }
  }
  const adapter = await createGatewayAdapter({ domain: wire.domain, beforePrepare: () => Effect.succeed(plan()), validateImages: () => Effect.void });
  try {
    await Effect.runPromise(adapter.prepare(binding, request()));
    await assert.rejects(Effect.runPromise(adapter.prepare(binding, request())));
  } finally { await adapter.close(); }
  assert.equal(wire.frames.length, 0);
});

test("partial trusted limit or capability records fail closed at preparation", async () => {
  const wire = channel();
  for (const patch of [{ bounds: { max_response_bytes: 8192, max_frame_bytes: 32768 } },
    { limits: { output_tokens: 64, window_tokens: 2048 } },
    { native_capabilities: { tools: true, input: "text", output: ["text"] } }]) {
    const adapter = await createGatewayAdapter({ domain: wire.domain, beforePrepare: () => Effect.succeed(plan(undefined, patch)), validateImages: () => Effect.void });
    try { await assert.rejects(Effect.runPromise(adapter.prepare(binding, request()))); }
    finally { await adapter.close(); }
  }
  assert.equal(wire.frames.length, 0);
});

test("only the returned request identity can dispatch once; clones, unbound calls and compact cannot send", async () => {
  const wire = channel();
  const adapter = await createGatewayAdapter({ domain: wire.domain, beforePrepare: () => Effect.succeed(plan()), validateImages: () => Effect.void });
  try {
    const original = request();
    await assert.rejects(Effect.runPromise(adapter.client.generate(original)));
    const prepared = await Effect.runPromise(adapter.prepare(binding, original));
    const { LLMRequest } = await import("@opencode/ai");
    await assert.rejects(Effect.runPromise(adapter.client.generate(LLMRequest.update(prepared, { metadata: {} }))));
    await assert.rejects(Effect.runPromise(adapter.client.compact(prepared)));
    const outcomes = await Promise.allSettled([Effect.runPromise(adapter.client.generate(prepared)),
      Effect.runPromise(adapter.client.stream(prepared).pipe(Stream.runCollect))]);
    assert.equal(outcomes.filter(item => item.status === "fulfilled").length, 1);
    await assert.rejects(Effect.runPromise(adapter.client.generate(prepared)));
    assert.equal(wire.frames.length, 1);
  } finally { await adapter.close(); }
  await assert.rejects(Effect.runPromise(adapter.prepare(binding, request())));
  assert.equal(wire.frames.length, 1);
});
