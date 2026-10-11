// SPDX-License-Identifier: MIT
// H07 preparation probe. No production host, domain authority or model dispatch.
import assert from "node:assert/strict";
import { mkdtemp, mkdir } from "node:fs/promises";
import path from "node:path";
import type { Plugin } from "@opencode/plugin/effect/plugin";
import type { Session } from "@opencode/sdk/effect";
import type { Permission as NativePermission } from "@opencode/core/permission";

export async function nativeChildContractFixture() {
  const scratch = process.env.RENULUS_CHILD_CONTRACT_TEST_ROOT;
  assert.ok(scratch, "Supply a dedicated synthetic H07 test root");
  await mkdir(scratch, { recursive: true });
  const root = await mkdtemp(path.join(scratch, "native-"));
  const previous = new Map<string, string | undefined>();
  const set = (name: string, value: string) => {
    previous.set(name, process.env[name]);
    process.env[name] = value;
  };
  for (const name of ["HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "OPENCODE_TEST_HOME",
    "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME", "XDG_RUNTIME_DIR", "TEMP", "TMP"]) {
    const directory = path.join(root, "environment", name);
    await mkdir(directory, { recursive: true });
    set(name, directory);
  }
  set("PATH", path.dirname(process.execPath));
  const { Effect, ManagedRuntime, Layer, Logger, Context, Option } = await import("effect");
  const { OpenCode, AbsolutePath, Location, Agent, SessionMessage, Model, Provider } = await import("@opencode/sdk/effect");
  const { TestLLM } = await import("@opencode/ai/testing");
  const { LLMClient } = await import("@opencode/ai");
  const { Config } = await import("@opencode/core/config");
  const { InstructionDiscovery } = await import("@opencode/core/instruction-discovery");
  const { SessionRestart } = await import("@opencode/core/session/execution/restart");
  const { Session } = await import("@opencode/core/session");
  const { Permission } = await import("@opencode/core/permission");
  const { llmClient } = await import("@opencode/core/effect/app-node-platform");
  const { Global } = await import("@opencode/util/global");
  const modelRuntime = ManagedRuntime.make(TestLLM.testLayer());
  const client = await modelRuntime.runPromise(TestLLM.Test);
  const pins = new Map<string, number>();
  const prompts: { sessionID: string; inputID: string; parentEpoch: number | undefined }[] = [];
  const syntheticAdmissions: { sessionID: string; resume: boolean | undefined }[] = [];
  const permissionProbes = new WeakMap<NativePermission.Interface, NativePermission.Interface["assert"]>();
  const permissionIntents = new Map<string, { id: NativePermission.ID; guarded: boolean }>();
  const permissionEffects: string[] = [];
  const permissionDiagnostics: unknown[] = [];
  let recoveryEntered = 0;
  const plugin: Plugin = { id: "renulus-h07-contract-probe", effect: context => Effect.gen(function* () {
    yield* context.session.hook("prompt", event => Effect.sync(() => {
      // Probe metadata only: this map is supplied by the fixture, never prompt arguments.
      const parentEpoch = pins.get(event.sessionID);
      prompts.push({ sessionID: event.sessionID, inputID: event.messageID, parentEpoch });
      event.metadata = { ...event.metadata, ...(parentEpoch === undefined ? {} : { fixtureParentEpoch: parentEpoch }),
        fixtureInputID: event.messageID };
    }));
    yield* context.command.transform(editor => editor.add({ name: "fixture_permission_wait", execute: invocation =>
      Effect.gen(function* () {
        permissionDiagnostics.push("command_entered");
        // The held public command owns its live native location throughout assertion/reply.
        const activePermission = Option.getOrThrow(Context.getOption(yield* Effect.context(), Permission.Service));
        const intent = permissionIntents.get(invocation.sessionID);
        assert.ok(intent);
        const raw = permissionProbes.get(activePermission);
        assert.ok(raw);
        yield* (intent.guarded ? activePermission.assert : raw)({
          id: intent.id, sessionID: invocation.sessionID, action: "subagent", resources: ["reviewer"],
          agent: Agent.ID.make("parent") });
        permissionEffects.push(invocation.sessionID);
      }).pipe(Effect.tapCause(cause => Effect.sync(() => { permissionDiagnostics.push(cause); }))) }));
  }) };
  const config = JSON.stringify({ model: "synthetic/parent", compaction: { auto: false },
    providers: { synthetic: { package: "@opencode/ai/providers/openai-compatible",
      settings: { baseURL: "https://synthetic.invalid/v1", apiKey: "synthetic-unused" },
      models: { parent: { limit: { context: 128000, output: 4096 } },
        override: { limit: { context: 128000, output: 4096 } } } } },
    agents: { parent: { mode: "primary", permissions: [{ action: "*", resource: "*", effect: "deny" }] },
      reviewer: { mode: "subagent", permissions: [{ action: "*", resource: "*", effect: "deny" }] },
      title: { disabled: true } } });
  const runtime = ManagedRuntime.make(Layer.effect(OpenCode.Service, OpenCode.create({
    app: { name: "renulus-child-contract-probe", version: "h07-preparation" },
    database: { path: path.join(root, "opencode.sqlite") }, plugins: [plugin],
    config: { directory: path.join(root, "config"), project: false, content: config },
    models: { fetch: false, snapshot: false }, fs: { filewatcher: false, fff: false }, events: { persist: false },
  }, { overrides: [
    Global.node.replace(Global.layerWith(Object.fromEntries(["home", "data", "cache", "config",
      "state", "tmp", "bin", "log", "repos"].map(key => [key, path.join(root, key)])))),
    Config.node.replace(Config.configured({ project: false, global: false, content: config })),
    InstructionDiscovery.node.replace(InstructionDiscovery.configured({ project: false, global: false })),
    llmClient.replace(Layer.succeed(LLMClient.Service, client)),
    Session.node.replace(Session.node.mapLayer(layer => Layer.effect(Session.Service,
      Effect.gen(function* () {
        const original = yield* Session.Service;
        return Session.Service.of({ ...original, synthetic: input =>
          Effect.sync(() => { syntheticAdmissions.push({ sessionID: input.sessionID, resume: input.resume }); })
            .pipe(Effect.andThen(original.synthetic(input))) });
      })).pipe(Layer.provide(layer)))),
    Permission.node.replace(Permission.node.mapLayer(layer => Layer.effect(Permission.Service,
      Effect.gen(function* () {
        const original = yield* Permission.Service;
        const guarded: NativePermission.Interface["assert"] = input => Effect.suspend(() => {
          const admittedEpoch = pins.get(input.sessionID);
          return original.assert(input).pipe(Effect.andThen(Effect.suspend(() =>
            admittedEpoch === undefined || pins.get(input.sessionID) === admittedEpoch ? Effect.void :
              Effect.fail(new Permission.BlockedError({ rules: [], permission: input.action,
                resources: input.resources, reason: "fixture_parent_revoked_after_approval" })) )));
        });
        const decorated = Permission.Service.of({ ...original, assert: guarded });
        permissionProbes.set(decorated, original.assert);
        return decorated;
      })).pipe(Layer.provide(layer)))),
    // Keep the SDK startup sweep closed even if this fixture later reopens a store.
    SessionRestart.node.replace(Layer.succeed(SessionRestart.Service, { resumeSuspendedSessions:
      Effect.sync(() => { recoveryEntered++; }).pipe(Effect.andThen(Effect.never)) })),
  ] })).pipe(Layer.provideMerge(Logger.layer([], { mergeWithExisting: false }))));
  const restore = () => {
    for (const [name, value] of previous) {
      if (value === undefined) delete process.env[name];
      else process.env[name] = value;
    }
  };
  try {
    const sdk = await runtime.runPromise(OpenCode.Service);
    return { sdk, root, pins, prompts, syntheticAdmissions, permissionIntents, permissionEffects,
      permissionDiagnostics,
      Agent, SessionMessage, Model, Provider, Permission,
      run: <A, E>(effect: import("effect").Effect.Effect<A, E>) => runtime.runPromise(effect),
      createParent: (title: string, metadata: Session.Metadata,
        permissions: readonly { action: string; resource: string; effect: "allow" | "deny" | "ask" }[]) =>
        runtime.runPromise(sdk.sessions.create({ title, agent: Agent.ID.make("parent"),
          model: { id: Model.ID.make("parent"), providerID: Provider.ID.make("synthetic") },
          location: Location.Ref.make({ directory: AbsolutePath.make(root) }), metadata, permissions })),
      requests: () => modelRuntime.runPromise(client.requests()),
      recoveryEntered: () => recoveryEntered,
      async close() {
        try { await runtime.dispose(); }
        finally { try { await modelRuntime.dispose(); } finally { restore(); } }
      },
    };
  } catch (error) {
    try { await runtime.dispose(); }
    finally { try { await modelRuntime.dispose(); } finally { restore(); } }
    throw error;
  }
}
