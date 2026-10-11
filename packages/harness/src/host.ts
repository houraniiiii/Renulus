import path from "node:path";
import { createHash } from "node:crypto";
import { mkdir } from "node:fs/promises";
import { Cause, Context, Effect, Layer, Logger, ManagedRuntime, Schema, Stream } from "effect";
import { AIError, InvalidRequestError, LLMClient, LLMRequest, type LLMClientShape, type Message } from "@opencode/ai";
import { OpenCode, AbsolutePath, Location, Session, Agent } from "@opencode/sdk/effect";
import { Config } from "@opencode/core/config";
import { Agent as NativeAgent } from "@opencode/core/agent";
import { InstructionDiscovery } from "@opencode/core/instruction-discovery";
import { llmClient } from "@opencode/core/effect/app-node-platform";
import { SessionRestart } from "@opencode/core/session/execution/restart";
import { SessionExecution } from "@opencode/core/session/execution";
import { SessionStore } from "@opencode/core/session/store";
import { Job } from "@opencode/core/job";
import { SessionModelRequest } from "@opencode/core/session/model-request";
import { Instance } from "@opencode/core/instance";
import { Plugin } from "@opencode/core/plugin";
import { Tool } from "@opencode/core/tool";
import { Npm } from "@opencode/util/npm";
import { Global } from "@opencode/util/global";
import { SessionMessage } from "@opencode/schema/session-message";
import { acquireStore } from "./ownership.ts";
import { verifyPreparedProfile, type ProfileSelection } from "./manifest.ts";
import { activateStores, validateStores } from "./stores.ts";
import { createLibraryPlugin, type LibraryToolBridge } from "./domain-tools.ts";

export interface ModelAdapter {
  readonly providerId: string;
  readonly modelId: string;
  readonly configuration: object;
  readonly client: LLMClientShape;
}

export interface HarnessOptions extends ProfileSelection {
  readonly model?: ModelAdapter;
  readonly library?: LibraryToolBridge;
  readonly admitInput?: (binding: NativeInputBinding) => Promise<void>;
  readonly selectContext?: (binding: NativeInputBinding, messages: readonly Message[]) => Promise<readonly Message[]>;
}

export interface NativeInputBinding {
  readonly operation_id: string;
  readonly attempt_id: string;
  readonly session_id: string;
  readonly input_id: string;
  readonly cancellation_id: string;
}

/** A persistent execution owner. Domain records continue to belong to Python. */
export async function openHarness(options: HarnessOptions) {
  const selection = await verifyPreparedProfile(options);
  if (selection.state === "active") validateStores(options);
  const root = path.resolve(options.root);
  const state = path.join(root, "state", "harness");
  const workspace = path.join(root, "harness-workspace");
  await mkdir(state, { recursive: true });
  await mkdir(workspace, { recursive: true });
  const ownership = await acquireStore(state, options.storeId);
  let phase = "policy_blocked";
  let configurationId: string | undefined;
  let store!: SessionStore.Interface;
  let execution!: SessionExecution.Interface;
  let jobs!: Job.Interface;
  let instances!: Instance.Interface;
  const held = new Set<string>();
  const bindings = new Map<string, NativeInputBinding>();
  let recoveryStarted = false;
  let releaseRecovery!: () => void;
  let recovered!: () => void;
  let recoveryFailed!: (error: unknown) => void;
  const recoveryPermit = new Promise<void>(resolve => { releaseRecovery = resolve; });
  const recoveryDone = new Promise<void>((resolve, reject) => { recovered = resolve; recoveryFailed = reject; });
  void recoveryDone.catch(() => {}); // Startup/close may precede an explicit recovery observer.
  const admissions = new WeakSet<object>();
  const denied = () => new AIError({ reason: new InvalidRequestError({ message: "Harness policy has not admitted this model request." }) });
  const dispatchAllowed = (request: object) => (phase === "ready" || phase === "recovering") && admissions.has(request);
  const client: LLMClientShape = {
    stream: (request, settings) => Stream.unwrap(Effect.sync(() => dispatchAllowed(request) && options.model
      ? options.model.client.stream(request, settings) : Stream.fail(denied()))),
    generate: (request, settings) => Effect.suspend(() => dispatchAllowed(request) && options.model
      ? options.model.client.generate(request, settings) : Effect.fail(denied())),
    compact: () => Effect.fail(denied()),
  };
  const modelConfiguration = options.model?.configuration as { model?: string; providers?: object } | undefined;
  const config = JSON.stringify({
    model: modelConfiguration?.model,
    providers: modelConfiguration?.providers,
    mcp: { servers: {} },
    compaction: { auto: false },
    agents: {
      renulus: { mode: "primary", system: "Support nephrology education. Use the supplied learning request.", permissions: [
        { action: "*", resource: "*", effect: "deny" },
        ...(options.library ? [{ action: "renulus.library", resource: "*", effect: "allow" }] : []),
      ] },
      title: { disabled: true },
    },
  });
  const overrides = [
    Global.node.replace(Global.layerWith(Object.fromEntries(
      ["home", "data", "cache", "config", "state", "tmp", "bin", "log", "repos"].map(key => [key, path.join(state, key)]),
    ))),
    Config.node.replace(Config.configured({ project: false, global: false, content: config })),
    InstructionDiscovery.node.replace(InstructionDiscovery.configured({ project: false, global: false })),
    llmClient.replace(Layer.succeed(LLMClient.Service, client)),
    // The reviewed cohort is already bundled. Candidate and admitted hosts
    // cannot acquire or update executable packages at runtime.
    Npm.node.replace(Layer.succeed(Npm.Service, {
      add: () => Effect.die(new Error("harness_package_acquisition_closed")),
      update: () => Effect.die(new Error("harness_package_acquisition_closed")),
      resolve: () => Effect.die(new Error("harness_package_acquisition_closed")),
      check: () => Effect.succeed(false),
      which: () => Effect.succeed(undefined),
    })),
    SessionStore.node.replace(SessionStore.node.mapLayer(original => Layer.flatMap(original, context => {
      store = Context.get(context, SessionStore.Service);
      return Layer.succeed(SessionStore.Service, store);
    }))),
    SessionExecution.node.replace(SessionExecution.node.mapLayer(original => Layer.flatMap(original, context => {
      execution = Context.get(context, SessionExecution.Service);
      return Layer.effect(SessionExecution.Service, Effect.context<never>().pipe(Effect.map(ambient => {
        // The pinned SessionExecution node declares Instance in its dependency
        // graph. mapLayer deliberately erases that graph to generic R.
        instances = Context.getUnsafe(ambient, Instance.Service);
        return execution;
      })));
    }))),
    Job.node.replace(Job.node.mapLayer(original => Layer.flatMap(original, context => {
      jobs = Context.get(context, Job.Service);
      return Layer.succeed(Job.Service, jobs);
    }))),
    SessionModelRequest.node.replace(SessionModelRequest.node.mapLayer(original => Layer.flatMap(original, context => {
      const service = Context.get(context, SessionModelRequest.Service);
      return Layer.succeed(SessionModelRequest.Service, {
        ...service,
        primary: input => service.primary(input).pipe(Effect.flatMap(prepared => Effect.promise(async () => {
          let request = prepared.request;
          if (options.selectContext) {
            const binding = bindings.get(input.session.id);
            if (!binding) throw new Error("harness_context_unbound");
            const messages = await options.selectContext(binding, request.messages);
            request = LLMRequest.update(request, { messages });
          }
          if (phase === "recovering" || (phase === "ready" && !held.has(input.session.id))) admissions.add(request);
          return { ...prepared, request, retry: event => Effect.sync(() => { event.decision = { retry: false }; }) };
        }))),
      });
    }))),
    SessionRestart.node.replace(SessionRestart.node.mapLayer(original => Layer.flatMap(original, context => {
      const service = Context.get(context, SessionRestart.Service);
      return Layer.succeed(SessionRestart.Service, {
        resumeSuspendedSessions: Effect.promise(() => recoveryPermit).pipe(
          Effect.andThen(service.resumeSuspendedSessions), Effect.tap(() => Effect.sync(recovered)),
          Effect.onExit(exit => Effect.sync(() => { if (exit._tag === "Failure") recoveryFailed(Cause.squash(exit.cause)); })),
        ),
      });
    }))),
  ];
  const runtime = ManagedRuntime.make(Layer.effect(OpenCode.Service, OpenCode.create({
    app: { name: "renulus", version: "opencode-foundation-1" },
    database: { path: path.join(state, "opencode.sqlite") },
    config: { directory: path.join(state, "config"), project: false, content: config },
    models: { fetch: false, snapshot: false },
    fs: { filewatcher: false, fff: false },
    events: { persist: false },
    plugins: options.library ? [{
      id: "renulus-internal-tool-boundary",
      effect: context => context.tool.transform(editor => {
        for (const tool of editor.list()) editor.remove(tool.id);
      }).pipe(Effect.asVoid),
    }, createLibraryPlugin(options.library)] : [],
  }, { overrides })).pipe(Layer.provideMerge(Logger.layer([], { mergeWithExisting: false }))));
  const run = <A, E>(effect: Effect.Effect<A, E>) => runtime.runPromise(effect);
  let sdk: OpenCode.Interface;
  try {
    sdk = await runtime.runPromise(OpenCode.Service);
    for (const id of await run(store.listSuspended())) held.add(id);
    for (const job of await run(jobs.pendingBackground)) {
      if (job.recovery.kind === "subagent") {
        held.add(job.recovery.parentSessionID);
        if (job.status === "running") held.add(job.recovery.childSessionID);
      } else held.add(job.recovery.sessionID);
    }
  }
  catch (error) {
    await runtime.dispose();
    await ownership.release();
    throw error;
  }
  let closing: Promise<void> | undefined;
  const admittedWrites = new Set<Promise<void>>();
  const requireReady = () => {
    if (phase !== "ready" || !configurationId || !options.model) throw new Error("harness_policy_blocked");
  };
  const mutate = async <A>(action: () => Promise<A>) => {
    requireReady();
    let settled!: () => void;
    const lease = new Promise<void>(resolve => { settled = resolve; });
    admittedWrites.add(lease);
    try { return await action(); }
    finally { admittedWrites.delete(lease); settled(); }
  };
  return {
    async inspect() {
      if (phase !== "policy_blocked" || selection.state !== "prepared" || admittedWrites.size) {
        throw new Error("harness_candidate_inspection_blocked");
      }
      phase = "candidate_inspecting";
      let settled!: () => void;
      const lease = new Promise<void>(resolve => { settled = resolve; });
      admittedWrites.add(lease);
      let probe: Session.Info | undefined;
      try {
        if ((await run(execution.active)).size || held.size) throw new Error("harness_candidate_not_quiescent");
        probe = await run(sdk.sessions.create({ title: "Renulus candidate registry probe",
          agent: Agent.ID.make("renulus"), location: Location.Ref.make({ directory: AbsolutePath.make(workspace) }) }));
        const session = probe;
        const definitions = await run(Effect.gen(function* () {
            yield* Plugin.awaitActivation;
            const plugins = yield* Plugin.Service;
            if ((yield* plugins.list()).some(plugin => plugin.state.status === "failed")) {
              throw new Error("harness_candidate_plugin_failed");
            }
            const agents = yield* NativeAgent.Service;
            const agent = yield* agents.get(Agent.ID.make("renulus"));
            if (!agent) throw new Error("harness_candidate_agent_missing");
            const tools = yield* Tool.Service;
            return (yield* tools.snapshot(agent.permissions)).definitions;
        }).pipe(instances.provide(session)));
        const registry = definitions.map(tool => ({ ...tool }))
          .sort((left, right) => left.name < right.name ? -1 : left.name > right.name ? 1 : 0);
        const canonical = (value: unknown): unknown => Array.isArray(value) ? value.map(canonical)
          : value !== null && typeof value === "object" ? Object.fromEntries(Object.entries(value)
            .sort(([left], [right]) => left < right ? -1 : left > right ? 1 : 0)
            .map(([key, item]) => [key, canonical(item)])) : value;
        return { state: "policy_blocked", generation_open: false, recovery_open: false,
          package_acquisition_open: false, mcp_startup_open: false, live_store_writer: false, registry,
          registry_hash: createHash("sha256").update(JSON.stringify(canonical(registry))).digest("hex") };
      } finally {
        try { if (probe) await run(sdk.sessions.remove({ sessionID: probe.id })); }
        finally {
          if (phase === "candidate_inspecting") phase = "policy_blocked";
          admittedWrites.delete(lease);
          settled();
        }
      }
    },
    async findSession(operationId: string) {
      if (!operationId || ["closing", "closed"].includes(phase)) throw new Error("harness_closing");
      const matched = [];
      let cursor: NonNullable<Parameters<typeof sdk.sessions.list>[0]>["cursor"];
      const cursors = new Set<string>();
      for (let pageNumber = 0; pageNumber < 100; pageNumber++) {
        const page = await run(sdk.sessions.list({ limit: 100,
          ...(cursor ? { cursor } : { directory: AbsolutePath.make(workspace), order: "asc" as const }) }));
        for (const session of page.data) {
          if (session.metadata?.renulusProfile === options.profileId
              && session.metadata?.renulusStore === options.storeId
              && session.metadata?.operationId === operationId) {
            matched.push(Schema.encodeSync(Session.Info)(session));
            if (matched.length > 1) throw new Error("harness_session_identity_conflict");
          }
        }
        cursor = page.cursor.next;
        if (!cursor || page.data.length < 100) return { sessions: matched };
        if (cursors.has(cursor)) throw new Error("harness_session_lookup_unavailable");
        cursors.add(cursor);
      }
      throw new Error("harness_session_lookup_unavailable");
    },
    binding(sessionId: string): NativeInputBinding {
      const binding = bindings.get(sessionId);
      if (!binding || !["ready", "recovering"].includes(phase)) throw new Error("native_input_not_admitted");
      return binding;
    },
    async activateStores() {
      if (!["policy_blocked", "ready", "store_activation_failed"].includes(phase)) throw new Error("harness_policy_blocked");
      const prior = phase;
      phase = "store_validating";
      const writesActive = admittedWrites.size > 0;
      let settled!: () => void;
      const lease = new Promise<void>(resolve => { settled = resolve; });
      admittedWrites.add(lease);
      try {
        if (writesActive || (await run(execution.active)).size) throw new Error("store_activation_requires_quiescence");
        const selected = await activateStores(options);
        if (phase === "store_validating") phase = prior === "store_activation_failed" ? "policy_blocked" : prior;
        return selected;
      } catch (error) {
        if (phase === "store_validating") phase = "store_activation_failed";
        throw error;
      } finally {
        admittedWrites.delete(lease);
        settled();
      }
    },
    async activate(id: string) {
      if (!id || !options.model || !["policy_blocked", "ready"].includes(phase)) throw new Error("harness_policy_blocked");
      if (configurationId && configurationId !== id) throw new Error("configuration_requires_new_generation");
      configurationId = id;
      phase = "ready";
    },
    async status() {
      return { state: phase, configurationId, heldSessionIds: [...held].sort(),
        activeSessionIds: phase === "closing" ? null : phase === "closed" ? [] : [...await run(execution.active)].sort() };
    },
    async recover(input: { configurationId: string; sessionIds: string[] }) {
      requireReady();
      if (input.configurationId !== configurationId || JSON.stringify([...input.sessionIds].sort()) !== JSON.stringify([...held].sort())) {
        throw new Error("recovery_admission_mismatch");
      }
      // Seal fresh admission before inspecting ALL native executions, including children.
      phase = "recovering";
      try {
        if (admittedWrites.size) throw new Error("recovery_requires_quiescence");
        if ((await run(execution.active)).size) throw new Error("recovery_requires_quiescence");
        if (!recoveryStarted) {
          recoveryStarted = true;
          releaseRecovery();
          try { await recoveryDone; }
          catch (error) { if (phase === "recovering") phase = "recovery_uncertain"; throw error; }
          held.clear();
        }
      } finally { if (phase === "recovering") phase = "ready"; }
    },
    async createSession(input: { operationId: string; title: string }) {
      return mutate(async () => Schema.encodeSync(Session.Info)(await run(sdk.sessions.create({
        title: input.title,
        agent: Agent.ID.make("renulus"),
        location: Location.Ref.make({ directory: AbsolutePath.make(workspace) }),
        metadata: { renulusProfile: options.profileId, renulusStore: options.storeId, operationId: input.operationId },
      }))));
    },
    async submit(input: { sessionId: string; operationId: string; attemptId: string; text: string }) {
      return mutate(async () => {
        if (held.has(input.sessionId)) throw new Error("recovery_required");
        const inputId = SessionMessage.ID.create();
        const binding = Object.freeze({ operation_id: input.operationId, attempt_id: input.attemptId,
          session_id: input.sessionId, input_id: inputId, cancellation_id: input.operationId });
        // Parent authority is pinned before native admission can schedule work.
        // A lost acknowledgement stays uncertain and must never mint a new input.
        await options.admitInput?.(binding);
        requireReady();
        bindings.set(input.sessionId, binding);
        const item = await run(sdk.sessions.prompt({
          sessionID: Session.ID.make(input.sessionId), id: inputId, text: input.text,
          metadata: { operationId: input.operationId, attemptId: input.attemptId, configurationId },
        }));
        if (item.id !== inputId) throw new Error("native_input_identity_conflict");
        return { operationId: input.operationId, attemptId: input.attemptId, sessionId: input.sessionId, inputId: item.id };
      });
    },
    async cancel(sessionId: string) {
      if (["closing", "closed"].includes(phase)) throw new Error("harness_closing");
      if (held.has(sessionId)) throw new Error("recovery_required");
      const id = Session.ID.make(sessionId);
      await run(sdk.sessions.get({ sessionID: id }));
      const interrupted = await run(execution.interrupt(id, { resume: false, reason: "user", awaitSettlement: true }));
      bindings.delete(sessionId);
      return { interrupted, outcome: "cancelled_settled" };
    },
    async wait(sessionId: string) { await run(sdk.sessions.wait({ sessionID: Session.ID.make(sessionId) })); },
    async observe(sessionId: string, input: { limit?: number; order?: "asc" | "desc"; cursor?: string } = {}) {
      const limit = input.limit ?? 100;
      if (!Number.isInteger(limit) || limit < 1 || limit > 200
          || (input.order !== undefined && !["asc", "desc"].includes(input.order))
          || (input.cursor !== undefined && (typeof input.cursor !== "string" || !input.cursor || input.cursor.length > 2048 || input.order !== undefined))) {
        throw new Error("invalid_observation_page");
      }
      const id = Session.ID.make(sessionId);
      const state = async () => await run(execution.isActive(id)) ? "active" as const
        : held.has(sessionId) || (await run(store.listSuspended())).includes(id) ? "held" as const : "settled" as const;
      const before = await state();
      const session = await run(sdk.sessions.get({ sessionID: id }));
      const messages = await run(sdk.message.list({ sessionID: id, limit,
        ...(input.cursor === undefined ? { order: input.order ?? "asc" } : { cursor: input.cursor }) }));
      const after = await state();
      const executionState = before === "active" || after === "active" ? "active"
        : before === "held" || after === "held" ? "held" : "settled";
      return { session: Schema.encodeSync(Session.Info)(session), execution: executionState,
        messages: messages.data.map(message => Schema.encodeSync(SessionMessage.Info)(message)), cursor: messages.cursor };
    },
    async close(input: { timeoutMs?: number } = {}) {
      const timeout = input.timeoutMs ?? 5000;
      if (!Number.isFinite(timeout) || timeout < 0) throw new Error("invalid_close_timeout");
      if (phase === "closed") return { state: "closed", outcome: "cancelled_settled" };
      phase = "closing";
      closing ??= (async () => {
        await Promise.all([...admittedWrites]);
        await runtime.dispose();
        await ownership.release();
        phase = "closed";
      })();
      let timer: ReturnType<typeof setTimeout> | undefined;
      try {
        const settled = await Promise.race([
          closing.then(() => true),
          new Promise<false>(resolve => { timer = setTimeout(() => resolve(false), timeout); }),
        ]);
        return settled ? { state: "closed", outcome: "cancelled_settled" }
          : { state: "blocked", outcome: "uncertain_after_disconnect" };
      } finally { clearTimeout(timer); }
    },
    async settled() { if (!closing) throw new Error("close_not_started"); await closing; },
  };
}
