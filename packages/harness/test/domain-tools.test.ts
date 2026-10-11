// SPDX-License-Identifier: MIT
import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdtemp, mkdir } from "node:fs/promises";
import path from "node:path";
import { createLibraryPlugin } from "../src/domain-tools.ts";
import { executeLibraryTool, type LibraryToolBridge, type LibraryToolEnvelope,
  type NativeLibraryContext, type LibraryDependency } from "../src/domain-tools.ts";

const context = { sessionID: "native-session", messageID: "native-message", id: "call-1", agent: "renulus" } as NativeLibraryContext;
const envelope: LibraryToolEnvelope = { sessionId: "native-session", operationId: "learning-1", attemptId: "attempt-1",
  scope: { kind: "study" }, revisionIds: ["rev-1"], policyRevision: 1, contextEpoch: 0, cancellationEpoch: 0 };
const passage = { id: "passage_0123456789abcdef0123456789abcdef", document_id: "doc-1", document_revision: "rev-1",
  text: "Synthetic dialysis fistula teaching.", locators: [{ page: 2, item_ref: "#/texts/0" }] };

function bridgeFixture() {
  const consumed: LibraryDependency[] = [];
  const bridge: LibraryToolBridge = {
    async resolve() { return envelope; },
    async check() {},
    async execute(command, arguments_, trusted) {
      assert.equal(command, "library.retrieve");
      assert.deepEqual(arguments_, { query: "fistula", limit: 2 });
      assert.deepEqual(trusted, envelope);
      return { status: "ready", passages: [passage] };
    },
    async recordDependencies(_, dependencies) { consumed.push(...dependencies); },
  };
  return { bridge, consumed };
}

test("native execution uses host identity and records consumed exact source references", async () => {
  const { bridge, consumed } = bridgeFixture();
  const result = await executeLibraryTool("library.retrieve", { query: "fistula", limit: 2 },
    context, bridge, new AbortController().signal);
  assert.equal(typeof result.content, "string");
  assert.deepEqual(JSON.parse(result.content as string), { status: "ready", passages: [passage] });
  assert.deepEqual(consumed, [{ document_id: "doc-1", document_revision: "rev-1",
    passage_id: "passage_0123456789abcdef0123456789abcdef", locators: [{ page: 2, item_ref: "#/texts/0" }] }]);
});

async function nativeHarness(bridge: LibraryToolBridge) {
  assert.ok(process.env.RENULUS_LIBRARY_TEST_ROOT, "Supply a dedicated synthetic test root");
  const root = await mkdtemp(path.join(process.env.RENULUS_LIBRARY_TEST_ROOT, "native-"));
  for (const name of ["HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "OPENCODE_TEST_HOME",
    "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME", "XDG_RUNTIME_DIR", "TEMP", "TMP"]) {
    process.env[name] = path.join(root, "environment", name);
    await mkdir(process.env[name], { recursive: true });
  }
  process.env.PATH = path.dirname(process.execPath);
  const { Effect, ManagedRuntime, Layer, Logger } = await import("effect");
  const { OpenCode, AbsolutePath, Location, Agent } = await import("@opencode/sdk/effect");
  const { TestLLM } = await import("@opencode/ai/testing");
  const { LLMClient } = await import("@opencode/ai");
  const { Config } = await import("@opencode/core/config");
  const { InstructionDiscovery } = await import("@opencode/core/instruction-discovery");
  const { llmClient } = await import("@opencode/core/effect/app-node-platform");
  const { Global } = await import("@opencode/util/global");
  const modelRuntime = ManagedRuntime.make(TestLLM.testLayer());
  const client = await modelRuntime.runPromise(TestLLM.Test);
  const config = JSON.stringify({ model: "synthetic/library", compaction: { auto: false },
    providers: { synthetic: { package: "@opencode/ai/providers/openai-compatible",
      settings: { baseURL: "https://synthetic.invalid/v1", apiKey: "synthetic-unused" },
      models: { library: { limit: { context: 128000, output: 4096 } } } } },
    agents: { renulus: { mode: "primary", permissions: [
      { action: "*", resource: "*", effect: "deny" },
      { action: "renulus.library", resource: "*", effect: "allow" }], system: "Synthetic Library tool check" },
      title: { disabled: true } } });
  const runtime = ManagedRuntime.make(Layer.effect(OpenCode.Service, OpenCode.create({
    app: { name: "renulus-library-test", version: "h02" },
    database: { path: path.join(root, "opencode.sqlite") },
    plugins: [createLibraryPlugin(bridge)],
    config: { directory: path.join(root, "config"), project: false, content: config },
    models: { fetch: false, snapshot: false }, fs: { filewatcher: false, fff: false }, events: { persist: false },
  }, { overrides: [
    Global.node.replace(Global.layerWith(Object.fromEntries(["home", "data", "cache", "config",
      "state", "tmp", "bin", "log", "repos"].map(key => [key, path.join(root, key)])))),
    Config.node.replace(Config.configured({ project: false, global: false, content: config })),
    InstructionDiscovery.node.replace(InstructionDiscovery.configured({ project: false, global: false })),
    llmClient.replace(Layer.succeed(LLMClient.Service, client)),
  ] })).pipe(Layer.provideMerge(Logger.layer([], { mergeWithExisting: false }))));
  const sdk = await runtime.runPromise(OpenCode.Service);
  const session = await runtime.runPromise(sdk.sessions.create({ title: "Synthetic cited learning",
    agent: Agent.ID.make("renulus"), location: Location.Ref.make({ directory: AbsolutePath.make(root) }),
    metadata: { operationId: "native-learning", attemptId: "native-attempt" } }));
  return { sdk, session, runtime, client, modelRuntime, TestLLM,
    async close() { await runtime.dispose(); await modelRuntime.dispose(); } };
}

test("pinned OpenCode executes registered retrieval in its native loop and consumes the result", async () => {
  const { bridge, consumed } = bridgeFixture();
  bridge.resolve = async native => ({ ...envelope, sessionId: native.sessionID });
  bridge.execute = async (command, arguments_) => {
    assert.equal(command, "library.retrieve");
    assert.deepEqual(arguments_, { query: "fistula", limit: 2 });
    return { status: "ready", passages: [passage] };
  };
  const native = await nativeHarness(bridge);
  try {
    await native.modelRuntime.runPromise(native.client.push(
      native.TestLLM.tool("native-call", "renulus_library_retrieve", { query: "fistula", limit: 2 }),
      native.TestLLM.text("Synthetic cited answer after native retrieval.", "answer")));
    await native.runtime.runPromise(native.sdk.sessions.prompt({ sessionID: native.session.id, text: "Explain fistula evidence" }));
    await native.runtime.runPromise(native.sdk.sessions.wait({ sessionID: native.session.id }));
    const requests = await native.modelRuntime.runPromise(native.client.requests());
    assert.equal(requests.length, 2);
    assert.match(JSON.stringify(requests[1]), /Synthetic dialysis fistula teaching/);
    assert.equal(consumed[0]?.passage_id, passage.id);
    const completed = await native.runtime.runPromise(native.sdk.sessions.get({ sessionID: native.session.id }));
    assert.equal(completed.outcome, "succeeded");
  } finally { await native.close(); }
});

test("pinned OpenCode opens an exact citation through its registered native tool", async () => {
  const citation = { document_id: "doc_0123456789abcdef0123456789abcdef",
    document_revision: "rev_0123456789abcdef0123456789abcdef", passage_id: passage.id,
    locators: passage.locators, original_url: "/api/v1/library/revisions/synthetic/original",
    viewer_url: "/library/synthetic?revision=synthetic&passage_id=" + passage.id };
  const { bridge, consumed } = bridgeFixture();
  bridge.resolve = async native => ({ ...envelope, sessionId: native.sessionID });
  bridge.execute = async command => { assert.equal(command, "library.citation"); return citation; };
  const native = await nativeHarness(bridge);
  try {
    await native.modelRuntime.runPromise(native.client.push(native.TestLLM.tool("native-citation", "renulus_library_citation", {
      document_id: citation.document_id, document_revision: citation.document_revision, passage_id: citation.passage_id, page: 2,
    }), native.TestLLM.text("Synthetic citation ready.", "answer")));
    await native.runtime.runPromise(native.sdk.sessions.prompt({ sessionID: native.session.id, text: "Open the cited passage" }));
    await native.runtime.runPromise(native.sdk.sessions.wait({ sessionID: native.session.id }));
    const requests = await native.modelRuntime.runPromise(native.client.requests());
    assert.equal(requests.length, 2);
    assert.match(JSON.stringify(requests[1]), /viewer_url/);
    assert.deepEqual(consumed, [{ document_id: citation.document_id, document_revision: citation.document_revision,
      passage_id: citation.passage_id, locators: citation.locators }]);
  } finally { await native.close(); }
});

test("model arguments cannot add scope, grants or widen retrieval bounds", async () => {
  const { bridge } = bridgeFixture();
  for (const input of [
    { query: "fistula", scope: { kind: "personal-library" } },
    { query: "fistula", revisionIds: ["ungranted-revision"] },
    { query: "fistula", toolkit: ["shell"] },
    { query: "fistula", limit: 50 }, { query: "fistula", limit: "2" },
    { query: " " }, { query: "x".repeat(16001) },
  ]) {
    await assert.rejects(executeLibraryTool("library.retrieve", input, context, bridge,
      new AbortController().signal), /invalid_library_arguments/);
  }
});

test("abort at every bridge boundary prevents the native result from returning", async () => {
  for (const stage of ["initial", "resolve", "check", "execute", "recordDependencies"] as const) {
    const { bridge } = bridgeFixture();
    const controller = new AbortController();
    if (stage === "initial") controller.abort();
    else {
      const original = bridge[stage];
      Object.defineProperty(bridge, stage, { value: async (...args: unknown[]) => {
        const result = await Reflect.apply(original, bridge, args);
        controller.abort();
        return result;
      } });
    }
    await assert.rejects(executeLibraryTool("library.retrieve", { query: "fistula", limit: 2 },
      context, bridge, controller.signal), { name: "AbortError" }, stage);
  }
});

test("an envelope for another native session is rejected before any domain read", async () => {
  const { bridge } = bridgeFixture();
  let reads = 0;
  bridge.resolve = async () => ({ ...envelope, sessionId: "other-session" });
  bridge.execute = async () => { reads++; return { status: "ready", passages: [passage] }; };
  await assert.rejects(executeLibraryTool("library.retrieve", { query: "fistula" },
    context, bridge, new AbortController().signal), /invalid_library_authority/);
  assert.equal(reads, 0);
});

test("native admission captures the host revision set before callbacks can mutate it", async () => {
  const { bridge } = bridgeFixture();
  const mutable = structuredClone(envelope);
  bridge.resolve = async () => mutable;
  bridge.check = async (_, stage) => {
    if (stage === "before_read") (mutable.revisionIds as string[]).push("ungranted");
  };
  bridge.execute = async (_, __, trusted) => {
    assert.deepEqual(trusted.revisionIds, ["rev-1"]);
    return { status: "ready", passages: [passage] };
  };
  await executeLibraryTool("library.retrieve", { query: "fistula" }, context, bridge, new AbortController().signal);
});

test("revoked run scope during dependency recording prevents native disclosure", async () => {
  const { bridge } = bridgeFixture();
  let admitted = true;
  bridge.check = async () => { if (!admitted) throw new Error("dependency_changed"); };
  bridge.recordDependencies = async () => { admitted = false; };
  await assert.rejects(executeLibraryTool("library.retrieve", { query: "fistula", limit: 2 },
    context, bridge, new AbortController().signal), /dependency_changed/);
});
