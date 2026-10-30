// SPDX-License-Identifier: MIT
// Actual pinned SDK/native Job owner; synthetic inference only when explicitly queued.
import assert from "node:assert/strict";
import { mkdtemp } from "node:fs/promises";
import path from "node:path";
import type { DomainBinding } from "../../src/domain-ipc.ts";

export async function childAuthorityNativeFixture(options: { permission?: "allow" | "ask" | "deny";
  beforeChildPrompt?: () => import("effect").Effect.Effect<void>;
  beforeParentPromotionCommit?: () => import("effect").Effect.Effect<void> } = {}) {
  assert.ok(process.env.RENULUS_CHILD_AUTHORITY_TEST_ROOT, "Supply an owned synthetic H07 root");
  const root = await mkdtemp(path.join(process.env.RENULUS_CHILD_AUTHORITY_TEST_ROOT, "native-"));
  // Inherit the caller environment unchanged. SDK services below own every
  // profile/config/cache/database path; system home variables are not test roots.
  const { Effect, ManagedRuntime, Layer, Logger, Context, Option } = await import("effect");
  const { OpenCode, AbsolutePath, Location, Agent } = await import("@opencode/sdk/effect");
  const { Tool } = await import("@opencode/schema/tool");
  const { TestLLM } = await import("@opencode/ai/testing");
  const { LLMClient } = await import("@opencode/ai");
  const { Config } = await import("@opencode/core/config");
  const { InstructionDiscovery } = await import("@opencode/core/instruction-discovery");
  const { SessionRestart } = await import("@opencode/core/session/execution/restart");
  const { Job } = await import("@opencode/core/job");
  const { Permission } = await import("@opencode/core/permission");
  const { Bus } = await import("@opencode/core/bus");
  const { SessionEvent } = await import("@opencode/core/session/event");
  const { llmClient } = await import("@opencode/core/effect/app-node-platform");
  const { Global } = await import("@opencode/util/global");
  const { createChildAuthority } = await import("../../src/child-authority.ts");
  const authority = { epoch: 1, current: true };
  const callbacks: { binding: Readonly<DomainBinding>; command: string; payload: Readonly<Record<string, unknown>> }[] = [];
  const bindings = new Map<string, Readonly<DomainBinding>>();
  let parentBinding!: Readonly<DomainBinding>;
  let parentSessionID: string | undefined;
  const children = createChildAuthority({
    resolveParent(native) { assert.equal(native.sessionID, parentBinding.session_id); return parentBinding; },
    localCurrent: (_, epoch) => authority.current && epoch === authority.epoch,
    bindInput: child => { bindings.set(child.session_id, child); },
    request: (binding, command, payload) => Effect.suspend((): import("effect").Effect.Effect<Record<string, unknown>, import("@opencode/schema/tool").Tool.Error> => {
      callbacks.push({ binding, command, payload: structuredClone(payload) });
      if (command !== "child.prepare" && !authority.current) return Effect.fail(new Tool.Error({ message: "child_authority_stale" }));
      switch (command) {
        case "child.prepare": return Effect.succeed({ reservation_id: "child-reservation-1", operation_id: "child-operation-1",
          attempt_id: "child-attempt-1", cancellation_id: "child-cancellation-1", grant_epoch: authority.epoch });
        case "child.check": return Effect.succeed({ current: true, grant_epoch: authority.epoch });
        case "child.admit_input": return Effect.succeed({ admitted: true });
        case "child.observe_job": return Effect.succeed({ observed: true });
        case "child.report": return Effect.succeed({ report_id: "child-report-1" });
        case "child.consume_report": return Effect.succeed({ consumed: true });
        default: return Effect.fail(new Tool.Error({ message: "fixture_unknown_callback" }));
      }
    }),
  }, { maxChildren: 4, maxInvocations: 4, maxDescriptionBytes: 256, maxPromptBytes: 16000, maxReportBytes: 16000 });
  const modelRuntime = ManagedRuntime.make(TestLLM.testLayer());
  const client = await modelRuntime.runPromise(TestLLM.Test);
  const config = JSON.stringify({ model: "synthetic/parent", compaction: { auto: false },
    providers: { synthetic: { package: "@opencode/ai/providers/openai-compatible",
      settings: { baseURL: "https://synthetic.invalid/v1", apiKey: "synthetic-unused" },
      models: { parent: { limit: { context: 128000, output: 4096 } } } } },
    agents: { renulus: { mode: "primary", permissions: [{ action: "*", resource: "*", effect: "deny" },
      { action: "subagent", resource: "evidence-review", effect: options.permission ?? "deny" }] },
      "evidence-review": { mode: "subagent", permissions: [{ action: "*", resource: "*", effect: "deny" }] },
      title: { disabled: true } } });
  let jobs!: import("@opencode/core/job").Job.Interface;
  const runtime = ManagedRuntime.make(Layer.effect(OpenCode.Service, OpenCode.create({
    app: { name: "renulus-child-authority-test", version: "h07" },
    database: { path: path.join(root, "opencode.sqlite") }, plugins: [children.plugin, {
      id: "renulus-child-authority-observer", effect: context => Effect.gen(function* () {
        yield* context.command.transform(editor => editor.add({ name: "fixture_jobs_ready", execute: () => Effect.gen(function* () {
          jobs = Option.getOrThrow(Context.getOption(yield* Effect.context(), Job.Service));
          if (options.beforeParentPromotionCommit) {
            const bus = Option.getOrThrow(Context.getOption(yield* Effect.context(), Bus.Service));
            yield* bus.project(SessionEvent.InboxDelivered, event => event.data.sessionID === parentSessionID ?
              options.beforeParentPromotionCommit!() : Effect.void);
          }
        }) }));
        if (options.beforeChildPrompt) yield* context.session.hook("prompt", event =>
          parentSessionID !== undefined && event.sessionID !== parentSessionID ? options.beforeChildPrompt!() : Effect.void);
      }),
    }],
    config: { directory: path.join(root, "config"), project: false, content: config },
    models: { fetch: false, snapshot: false }, fs: { filewatcher: false, fff: false }, events: { persist: false },
  }, { overrides: [
    ...children.overrides,
    Permission.node.replace(Permission.node.mapLayer(native => Layer.effect(Permission.Service,
      Effect.flatMap(Permission.Service, children.guardPermission)).pipe(Layer.provide(native)))),
    Global.node.replace(Global.layerWith(Object.fromEntries(["home", "data", "cache", "config",
      "state", "tmp", "bin", "log", "repos"].map(key => [key, path.join(root, key)])))),
    Config.node.replace(Config.configured({ project: false, global: false, content: config })),
    InstructionDiscovery.node.replace(InstructionDiscovery.configured({ project: false, global: false })),
    llmClient.replace(Layer.succeed(LLMClient.Service, client)),
    SessionRestart.node.replace(Layer.succeed(SessionRestart.Service, { resumeSuspendedSessions: Effect.never })),
  ] })).pipe(Layer.provideMerge(Logger.layer([], { mergeWithExisting: false }))));
  try {
    const sdk = await runtime.runPromise(OpenCode.Service);
    const parent = await runtime.runPromise(sdk.sessions.create({ title: "Synthetic evidence review",
      agent: Agent.ID.make("renulus"), location: Location.Ref.make({ directory: AbsolutePath.make(root) }) }));
    parentSessionID = parent.id;
    const input = await runtime.runPromise(sdk.sessions.prompt({ sessionID: parent.id, text: "Synthetic parked resource check", resume: false }));
    parentBinding = Object.freeze({ operation_id: "parent-operation", attempt_id: "parent-attempt",
      session_id: parent.id, input_id: input.id, cancellation_id: "parent-cancellation" });
    await runtime.runPromise(sdk.sessions.command({ sessionID: parent.id, name: "fixture_jobs_ready", text: "" }));
    assert.ok(jobs, "Actual native Job service must be acquired");
    return { root, sdk, parent, input, parentBinding, jobs, children, client, TestLLM, authority, callbacks, bindings,
      run: <A, E>(effect: import("effect").Effect.Effect<A, E>) => runtime.runPromise(effect),
      requests: () => modelRuntime.runPromise(client.requests()),
      push: (...responses: readonly import("@opencode/ai/testing").TestLLM.Response[]) => modelRuntime.runPromise(client.push(...responses)),
      serve: (responder: import("@opencode/ai/testing").TestLLM.Responder) => modelRuntime.runPromise(client.serve(responder)),
      async close() {
        try { await runtime.dispose(); } finally { await modelRuntime.dispose(); }
      },
    };
  } catch (error) {
    try { await runtime.dispose(); } finally { await modelRuntime.dispose(); }
    throw error;
  }
}
