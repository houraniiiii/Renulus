import "./fixtures/provider-environment.mjs";
import assert from "node:assert/strict";
import path from "node:path";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { test } from "node:test";
import { randomUUID } from "node:crypto";
import { spawnSync } from "node:child_process";
import { Effect, Stream } from "effect";
import { HttpClientResponse } from "effect/http";
import { AIError, AuthenticationError, InvalidRequestError, HttpOptions, LanguageModel, LLMRequest, Message, ToolDefinition, Media } from "@opencode/ai";
import { createSubscriptionAdapter } from "../src/provider-adapter.ts";
import { openHarness } from "../src/host.ts";

function route(provider = "opencode-go", model = "mimo-v2.6-pro") {
  return { provider_id: provider, catalog_model_id: model, wire_model_id: model,
    endpoint: provider === "codex" ? "https://api.openai.com/v1/responses" : "https://opencode.ai/zen/go/v1/chat/completions",
    protocol: provider === "codex" ? "openai-responses" : "openai-chat",
    credential_ref: "synthetic-protected-reference", credential_epoch: 1, catalogue_listed: false };
}
const png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA6fptVAAAACklEQVR4nGNgAAAAAgABSK+kcQAAAABJRU5ErkJggg==";

function chatSSE(content = "Synthetic dialysis explanation", model = "mimo-v2.6-pro") {
  return [{ content }, {}].map((delta, index) => "data: " + JSON.stringify({
    id: "synthetic-response", object: "chat.completion.chunk", created: 1, model,
    choices: [{ index: 0, delta, finish_reason: index ? "stop" : null }],
  }) + "\n\n").join("") + "data: [DONE]\n\n";
}

function responsesSSE(model, text) {
  return [{ type: "response.output_item.added", item: { type: "message", id: "synthetic-message" } },
    { type: "response.output_text.delta", item_id: "synthetic-message", delta: text },
    { type: "response.output_item.done", item: { type: "message", id: "synthetic-message",
      content: [{ type: "output_text", text }] } },
    { type: "response.completed", response: { id: "synthetic-response", model, status: "completed" } },
  ].map(event => "data: " + JSON.stringify(event) + "\n\n").join("");
}

function respond(request, content = chatSSE()) {
  return HttpClientResponse.fromWeb(request, new Response(content, {
    headers: { "content-type": "text/event-stream" },
  }));
}

function request(adapter, messages = [Message.user("Explain synthetic glomerular learning")], patch = {}) {
  return new LLMRequest({ model: adapter.model, system: [], messages, tools: [], ...patch });
}

test("the pinned client preserves a complete native tool pair and the exact Go route", async () => {
  const calls = [];
  const adapter = await createSubscriptionAdapter({ route: route(), sessionId: "synthetic-conversation",
    dispatch: (_route, http) => Effect.sync(() => {
      calls.push(http);
      return respond(http);
    }),
  });
  try {
    const tool = ToolDefinition.make({ name: "library_passage", description: "Read eligible teaching",
      inputSchema: { type: "object", properties: {} } });
    const messages = [Message.user("Explain synthetic dialysis"), Message.assistant([
      { type: "tool-call", id: "call-1", name: "library_passage", input: {} },
    ]), Message.make({ role: "tool", content: [
      { type: "tool-result", id: "call-1", name: "library_passage", result: { type: "text", value: "Synthetic eligible passage" } },
    ] })];
    const result = await Effect.runPromise(adapter.client.generate(request(adapter, messages, { tools: [tool] })));
    assert.equal(result.text, "Synthetic dialysis explanation");
    assert.equal(calls.length, 1);
    const http = calls[0];
    assert.equal(http.url, "https://opencode.ai/zen/go/v1/chat/completions");
    assert.equal(http.headers["x-opencode-session"], "synthetic-conversation");
    const body = JSON.parse(new TextDecoder().decode(http.body.body));
    assert.equal(body.model, "mimo-v2.6-pro");
    assert.equal(body.messages[1].tool_calls[0].id, body.messages[2].tool_call_id);
    assert.equal(body.messages[2].content, "Synthetic eligible passage");
    assert.equal(body.tools[0].function.name, "library_passage");
  } finally { await adapter.close(); }
});

test("catalogue aliases, subscription protocol and endpoint cannot change the selected wire route", async () => {
  let calls = 0;
  for (const patch of [
    { wire_model_id: "deepseek-v4.1-flash" }, { catalog_model_id: "unapproved-model" },
    { protocol: "openai-responses" }, { endpoint: "https://synthetic.invalid/v1/chat/completions" },
    { provider_id: "openai" }, { credential_ref: "" }, { credential_epoch: -1 },
  ]) {
    await assert.rejects(async () => {
      const adapter = await createSubscriptionAdapter({ route: { ...route(), ...patch },
        sessionId: "synthetic-conversation", dispatch: (_route, http) => Effect.sync(() => {
          calls += 1; return respond(http);
        }),
      });
      await adapter.close();
    });
  }
  assert.equal(calls, 0);
});

test("a final body overlay cannot substitute another wire model", async () => {
  let calls = 0;
  const adapter = await createSubscriptionAdapter({ route: route(), sessionId: "synthetic-conversation",
    dispatch: (_route, http) => Effect.sync(() => { calls += 1; return respond(http); }),
  });
  try {
    const altered = request(adapter, undefined, { http: new HttpOptions({ body: { model: "deepseek-v4.1-flash" } }) });
    await assert.rejects(Effect.runPromise(adapter.client.generate(altered)));
    assert.equal(calls, 0);
  } finally { await adapter.close(); }
});

test("unqualified middleware and WebSocket calls are denied before either transport", async () => {
  let http = 0, ws = 0, middleware = 0;
  const adapter = await createSubscriptionAdapter({ route: route(), sessionId: "synthetic-conversation",
    dispatch: (_route, req) => Effect.sync(() => { http += 1; return respond(req); }),
  });
  try {
    const socket = { execute: () => { ws += 1; throw new Error("Unexpected WS"); } };
    await assert.rejects(Effect.runPromise(adapter.client.generate(request(adapter), { webSocket: socket })));
    await assert.rejects(Effect.runPromise(adapter.client.stream(request(adapter), {
      http: () => { middleware += 1; throw new Error("Unexpected middleware"); },
    }).pipe(Stream.runCollect)));
    assert.deepEqual([http, ws, middleware], [0, 0, 0]);
  } finally { await adapter.close(); }
});

test("a caller's changed model or deployment fails visibly without substitution", async () => {
  let calls = 0;
  const adapter = await createSubscriptionAdapter({ route: route(), sessionId: "synthetic-conversation",
    dispatch: (_route, req) => Effect.sync(() => { calls += 1; return respond(req); }),
  });
  try {
    for (const model of [
      LanguageModel.update(adapter.model, { id: "deepseek-v4.1-flash" }),
      LanguageModel.update(adapter.model, { provider: "codex" }),
      LanguageModel.update(adapter.model, { route: adapter.model.route.with({ endpoint: { baseURL: "https://synthetic.invalid/v1" } }) }),
    ]) await assert.rejects(Effect.runPromise(adapter.client.generate(request(adapter, undefined, { model }))));
    assert.equal(calls, 0);
  } finally { await adapter.close(); }
});

test("incomplete, orphaned, duplicate and mismatched tool pairs are rejected without IO", async () => {
  let calls = 0;
  const adapter = await createSubscriptionAdapter({ route: route(), sessionId: "synthetic-conversation",
    dispatch: (_route, req) => Effect.sync(() => { calls += 1; return respond(req); }),
  });
  const call = Message.assistant([{ type: "tool-call", id: "call-1", name: "library_passage", input: {} }]);
  const result = name => Message.make({ role: "tool", content: [{ type: "tool-result",
    id: "call-1", name, result: { type: "text", value: "Synthetic passage" } }] });
  try {
    for (const messages of [[result("library_passage")], [call], [call, result("different_tool")],
      [call, result("library_passage"), result("library_passage")], [call, Message.user("Interrupt")]]) {
      await assert.rejects(Effect.runPromise(adapter.client.generate(request(adapter, messages))));
    }
    assert.equal(calls, 0);
  } finally { await adapter.close(); }
});

test("required media is inline, MIME matched and within the existing image and text limits", async () => {
  let calls = 0;
  const adapter = await createSubscriptionAdapter({ route: route(), sessionId: "synthetic-conversation",
    validateImages: () => Effect.void,
    dispatch: (_route, req) => Effect.sync(() => { calls += 1; return respond(req); }),
  });
  const image = () => Message.media(Media.base64(png, "image/png"));
  try {
    for (const messages of [
      [Message.user(Array.from({ length: 5 }, image))],
      [Message.user(Message.media(Media.base64(png, "image/jpeg")))],
      [Message.user(Message.media(Media.url("https://synthetic.invalid/image.png", "image/png")))],
      [Message.user(Message.media(Media.base64("bad-base64", "image/png")))],
      [Message.assistant(image())], [Message.user("a".repeat(1000001))],
      Array.from({ length: 201 }, () => Message.user("Synthetic learning")),
    ]) await assert.rejects(Effect.runPromise(adapter.client.generate(request(adapter, messages))));
    assert.equal(calls, 0);
    await Effect.runPromise(adapter.client.generate(request(adapter, [Message.user([Message.text("Synthetic image teaching"), image()])])));
    assert.equal(calls, 1);
  } finally { await adapter.close(); }
});

test("body and credential overlays cannot inject unvalidated input after preparation", async () => {
  let calls = 0;
  const adapter = await createSubscriptionAdapter({ route: route(), sessionId: "synthetic-conversation",
    dispatch: (_route, req) => Effect.sync(() => { calls += 1; return respond(req); }),
  });
  try {
    for (const http of [
      new HttpOptions({ body: { messages: [{ role: "user", content: "a".repeat(1000001) }] } }),
      new HttpOptions({ headers: { authorization: "Synthetic unowned credential" } }),
      new HttpOptions({ query: { key: "Synthetic unowned credential" } }),
    ]) await assert.rejects(Effect.runPromise(adapter.client.generate(request(adapter, undefined, { http }))));
    assert.equal(calls, 0);
  } finally { await adapter.close(); }
});

test("credential canaries in transport failures cannot reach client diagnostics", async () => {
  const canary = randomUUID();
  let calls = 0;
  const adapter = await createSubscriptionAdapter({ route: route(), sessionId: "synthetic-conversation",
    dispatch: () => { calls += 1; return Effect.fail(new AIError({
      reason: new AuthenticationError({ message: canary, body: canary, cause: new Error(canary) }),
    })); },
  });
  try {
    const result = await Effect.runPromise(adapter.client.generate(request(adapter)).pipe(Effect.result));
    assert.equal(result._tag, "Failure");
    assert.ok(!JSON.stringify(result).includes(canary), "Credential canary leaked into diagnostics");
    assert.ok(!String(result.failure).includes(canary), "Credential canary leaked into error text");
    assert.equal(result.failure.reason._tag, "Authentication");
    assert.equal(calls, 1);
  } finally { await adapter.close(); }
});

test("a counted synthetic HTTP 401 is a redacted authentication failure with no replay", async () => {
  const canary = randomUUID();
  let calls = 0;
  const adapter = await createSubscriptionAdapter({ route: route(), sessionId: "synthetic-conversation",
    dispatch: (_route, http) => Effect.sync(() => {
      calls += 1;
      return HttpClientResponse.fromWeb(http, new Response(JSON.stringify({ error: { message: canary } }),
        { status: 401, headers: { "content-type": "application/json" } }));
    }),
  });
  try {
    const result = await Effect.runPromise(adapter.client.generate(request(adapter)).pipe(Effect.result));
    assert.equal(result._tag, "Failure");
    assert.equal(result.failure.reason._tag, "Authentication");
    assert.ok(!JSON.stringify(result).includes(canary), "Credential leaked from HTTP failure");
    assert.equal(calls, 1);
  } finally { await adapter.close(); }
});

test("all five selected IDs complete a saved Harness turn through the actual pinned client", async () => {
  const root = "C:/Renulus/scratch/oc-h02-h08/providers/native";
  await mkdir(root, { recursive: true });
  const pairs = [["codex", "gpt-6.1-sol"], ["codex", "gpt-6-astra"], ["codex", "gpt-6-luna"],
    ["opencode-go", "mimo-v2.6-pro"], ["opencode-go", "deepseek-v4.1-flash"]];
  for (const [provider, model] of pairs) {
    const answer = "Synthetic transplantation teaching";
    let calls = 0;
    const adapter = await createSubscriptionAdapter({ route: route(provider, model), sessionId: "synthetic-conversation",
      dispatch: (selected, http) => Effect.sync(() => {
        calls += 1;
        assert.equal(selected.wire_model_id, model);
        assert.equal(http.url, selected.endpoint);
        assert.equal(http.headers.authorization, undefined);
        const body = JSON.parse(new TextDecoder().decode(http.body.body));
        assert.equal(body.model, model);
        if (provider === "codex") assert.equal(body.store, false);
        return respond(http, provider === "codex" ? responsesSSE(model, answer) : chatSSE(answer, model));
      }),
    });
    const profile = await mkdtemp(path.join(root, `${model}-`));
    const manifest = JSON.parse(await readFile(new URL("../../contracts/fixtures/harness/paired-store-prepared.json", import.meta.url), "utf8"));
    manifest.runtime_store.store_id = "synthetic-store";
    manifest.runtime_store.path = "state/harness/opencode.sqlite";
    await mkdir(path.join(profile, "state/harness"), { recursive: true });
    await writeFile(path.join(profile, "state/harness/manifest.json"), JSON.stringify(manifest));
    let host;
    const identities = [];
    const traced = { ...adapter, client: { ...adapter.client, stream: (req, settings) => {
      identities.push({ id: req.model.id, provider: req.model.provider, protocol: req.model.route.protocol,
        endpoint: req.model.route.endpoint.baseURL, httpKeys: Object.keys(req.http ?? {}),
        httpHeaderKeys: Object.keys(req.http?.headers ?? {}), httpBodyKeys: Object.keys(req.http?.body ?? {}),
        optionKeys: Object.keys(settings ?? {}), types: req.messages.map(msg => [msg.role, msg.content.map(part => part.type)]) });
      return adapter.client.stream(req, settings);
    } } };
    try {
      host = await openHarness({ root: profile, profileId: "synthetic-profile", storeId: "synthetic-store",
        domainStoreId: "synthetic-domain-store", domainPath: "domain/renulus.sqlite3", model: traced });
      await assert.rejects(host.createSession({ operationId: "blocked", title: "Synthetic blocked" }));
      assert.equal(calls, 0);
      await host.activate("synthetic-parent-admission");
      const session = await host.createSession({ operationId: "create", title: "Synthetic renal learning" });
      await host.submit({ sessionId: session.id, operationId: "explain", attemptId: "one", text: "Explain synthetic transplantation" });
      await host.wait(session.id);
      const observed = await host.observe(session.id);
      assert.equal(observed.session.outcome, "succeeded", JSON.stringify({ identities, calls }));
      assert.equal(observed.messages.filter(item => item.type === "assistant").at(-1).content[0].text, answer);
      assert.equal(calls, 1);
    } finally { await host?.close(); await adapter.close(); }
  }
});

test("final native images require the managed decoder before counted dispatch", async () => {
  for (const [provider, model] of [["codex", "gpt-6.1-sol"], ["opencode-go", "mimo-v2.6-pro"]]) {
    let calls = 0, validations = 0;
    const options = { route: route(provider, model), sessionId: "synthetic-conversation",
      dispatch: (_route, http) => Effect.sync(() => { calls += 1;
        return respond(http, provider === "codex" ? responsesSSE(model, "Synthetic image") : chatSSE("Synthetic image"));
      }),
    };
    const messages = [Message.user(Message.media(Media.base64(png, "image/png")))];
    for (const validateImages of [undefined, () => Effect.fail(new AIError({
      reason: new InvalidRequestError({ message: "Synthetic invalid image" }),
    }))]) {
      const adapter = await createSubscriptionAdapter({ ...options, validateImages });
      try { await assert.rejects(Effect.runPromise(adapter.client.generate(request(adapter, messages)))); }
      finally { await adapter.close(); }
    }
    assert.equal(calls, 0);
    const adapter = await createSubscriptionAdapter({ ...options, validateImages: images => Effect.sync(() => {
      validations += 1;
      assert.deepEqual(images, [{ type: "image", media_type: "image/png", data: png }]);
    }) });
    try { await Effect.runPromise(adapter.client.generate(request(adapter, messages))); }
    finally { await adapter.close(); }
    assert.deepEqual([validations, calls], [1, 1]);
  }
});

test("native hosted tools, retention, compaction and truncation cannot widen the narrow adapter", async () => {
  let calls = 0;
  const adapter = await createSubscriptionAdapter({ route: route("codex", "gpt-6.1-sol"),
    sessionId: "synthetic-conversation", dispatch: (_route, http) => Effect.sync(() => { calls += 1;
      return respond(http, responsesSSE("gpt-6.1-sol", "Synthetic explanation"));
    }),
  });
  try {
    for (const patch of [
      { providerOptions: { store: true } },
      { providerOptions: { contextManagement: [{ type: "compaction", compactThreshold: 1000 }] } },
      { providerOptions: { truncation: "auto" } },
      { tools: [ToolDefinition.make({ name: "hosted_search", description: "Synthetic hosted tool",
        inputSchema: { type: "object" }, native: { openai: { type: "web_search" } } })] },
    ]) await assert.rejects(Effect.runPromise(adapter.client.generate(request(adapter, undefined, patch))));
    assert.equal(calls, 0);
  } finally { await adapter.close(); }
});

test("the real native clients complete emitted tool continuations with managed-decoded images", { timeout: 90000 }, async () => {
  for (const [provider, model] of [["codex", "gpt-6.1-sol"], ["opencode-go", "mimo-v2.6-pro"]]) {
    const wire = [];
    let validations = 0;
    let phase = "first response";
    const adapter = await createSubscriptionAdapter({ route: route(provider, model), sessionId: "synthetic-conversation",
      validateImages: images => Effect.sync(() => {
        const decoded = spawnSync("C:/Renulus/dev/python/Scripts/python.exe", ["-c",
          "import json, sys; from renulus.runtime.provider_adapter import validate_harness_images; validate_harness_images(json.load(sys.stdin))"], {
          input: JSON.stringify(images), encoding: "utf8", windowsHide: true, timeout: 30000, maxBuffer: 4096,
          cwd: path.resolve(import.meta.dirname, "../../.."),
          env: { ...process.env, PYTHONPATH: path.resolve(import.meta.dirname, "../../../runtime") },
        });
        assert.equal(decoded.status, 0, "The managed image decoder refused the synthetic fixture");
        validations += 1;
      }),
      dispatch: (_route, http) => Effect.sync(() => {
        const body = JSON.parse(new TextDecoder().decode(http.body.body));
        wire.push(body);
        if (wire.length > 1) return respond(http, provider === "codex"
          ? responsesSSE(model, "Synthetic cited transplantation explanation") : chatSSE("Synthetic cited transplantation explanation"));
        const events = provider === "codex" ? [
          { type: "response.output_item.added", item: { type: "function_call", id: "synthetic-item", call_id: "native-call", name: "library_passage", arguments: "" } },
          { type: "response.output_item.done", item: { type: "function_call", id: "synthetic-item", call_id: "native-call", name: "library_passage", arguments: "{}" } },
          { type: "response.completed", response: { id: "synthetic-response", model, status: "completed" } },
        ] : [
          { id: "synthetic-response", model, choices: [{ index: 0, delta: { tool_calls: [{ index: 0, id: "native-call", type: "function",
            function: { name: "library_passage", arguments: "{}" } }] }, finish_reason: null }] },
          { id: "synthetic-response", model, choices: [{ index: 0, delta: {}, finish_reason: "tool_calls" }] },
        ];
        return respond(http, events.map(event => "data: " + JSON.stringify(event) + "\n\n").join("")
          + (provider === "codex" ? "" : "data: [DONE]\n\n"));
      }),
    });
    try {
      const tools = [ToolDefinition.make({ name: "library_passage", description: "Synthetic eligible teaching", inputSchema: { type: "object", properties: {} } })];
      const messages = [Message.user([Message.text("Discuss the synthetic teaching image"), Message.media(Media.base64(png, "image/png"))])];
      const first = await Effect.runPromise(adapter.client.generate(request(adapter, messages, { tools })));
      assert.equal(first.toolCalls.length, 1);
      const call = first.toolCalls[0];
      phase = "tool continuation";
      const second = await Effect.runPromise(adapter.client.generate(request(adapter, [...messages, Message.assistant([call]),
        Message.make({ role: "tool", content: [{ type: "tool-result", id: call.id, name: call.name,
          result: { type: "text", value: "Synthetic eligible transplantation passage" } }] })], { tools })));
      assert.equal(second.text, "Synthetic cited transplantation explanation");
      assert.deepEqual([wire.length, validations], [2, 2]);
      if (provider === "codex") {
        const pair = wire[1].input.filter(part => ["function_call", "function_call_output"].includes(part.type));
        assert.equal(pair[0].call_id, pair[1].call_id);
        assert.equal(pair[1].output, "Synthetic eligible transplantation passage");
      } else {
        assert.equal(wire[1].messages[1].tool_calls[0].id, wire[1].messages[2].tool_call_id);
        assert.equal(wire[1].messages[2].content, "Synthetic eligible transplantation passage");
      }
    } catch { assert.fail(`Native ${provider} ${phase} failed after ${wire.length} requests and ${validations} image validations`); }
    finally { await adapter.close(); }
  }
});

test("native provider metadata canaries never become transcript-facing events or responses", async () => {
  const canary = randomUUID();
  const model = "gpt-6.1-sol";
  const adapter = await createSubscriptionAdapter({ route: route("codex", model), sessionId: "synthetic-conversation",
    dispatch: (_route, http) => Effect.sync(() => respond(http, responsesSSE(model, "Synthetic safe explanation")
      .replace("\"id\":\"synthetic-response\"", "\"id\":\"" + canary + "\""))),
  });
  try {
    const events = await Effect.runPromise(adapter.client.stream(request(adapter)).pipe(Stream.runCollect));
    assert.ok(!JSON.stringify(events).includes(canary), "Provider metadata canary leaked into events");
    const response = await Effect.runPromise(adapter.client.generate(request(adapter)));
    assert.equal(response.text, "Synthetic safe explanation");
    assert.ok(!JSON.stringify(response).includes(canary), "Provider metadata canary leaked into response");
  } finally { await adapter.close(); }
});
