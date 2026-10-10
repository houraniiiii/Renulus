import path from "node:path";
import { mkdir } from "node:fs/promises";
import { Cause, Context, Effect, Layer, Logger, ManagedRuntime, Schema, Stream } from "effect";
import { AIError, InvalidRequestError, LLMClient, type LLMClientShape } from "@opencode/ai";
import { OpenCode, AbsolutePath, Location, Session, Agent } from "@opencode/sdk/effect";
import { Config } from "@opencode/core/config";
import { InstructionDiscovery } from "@opencode/core/instruction-discovery";
import { llmClient } from "@opencode/core/effect/app-node-platform";
import { SessionRestart } from "@opencode/core/session/execution/restart";
import { SessionExecution } from "@opencode/core/session/execution";
import { SessionStore } from "@opencode/core/session/store";
import { Job } from "@opencode/core/job";
import { SessionModelRequest } from "@opencode/core/session/model-request";
import { Global } from "@opencode/util/global";
import { SessionMessage } from "@opencode/schema/session-message";
import { acquireStore } from "./ownership.ts";
import { verifyPreparedProfile, type ProfileSelection } from "./manifest.ts";

export interface ModelAdapter {
  readonly providerId: string;
  readonly modelId: string;
  readonly configuration: object;
  readonly client: LLMClientShape;
}

export interface HarnessOptions extends ProfileSelection {
  readonly model?: ModelAdapter;
}

/** A persistent execution owner. Domain records continue to belong to Python. */
export async function openHarness(options: HarnessOptions) {
  await verifyPreparedProfile(options);
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
  const held = new Set<string>();
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
  const config = JSON.stringify({
    ...(options.model?.configuration ?? {}),
    compaction: { auto: false },
    agents: {
      renulus: { mode: "primary", system: "Support nephrology education. Use the supplied learning request.", permissions: [{ action: "*", resource: "*", effect: "deny" }] },
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
    SessionStore.node.replace(SessionStore.node.mapLayer(original => Layer.flatMap(original, context => {
      store = Context.get(context, SessionStore.Service);
      return Layer.succeed(SessionStore.Service, store);
    }))),
    SessionExecution.node.replace(SessionExecution.node.mapLayer(original => Layer.flatMap(original, context => {
      execution = Context.get(context, SessionExecution.Service);
      return Layer.succeed(SessionExecution.Service, execution);
    }))),
    Job.node.replace(Job.node.mapLayer(original => Layer.flatMap(original, context => {
      jobs = Context.get(context, Job.Service);
      return Layer.succeed(Job.Service, jobs);
    }))),
    SessionModelRequest.node.replace(SessionModelRequest.node.mapLayer(original => Layer.flatMap(original, context => {
      const service = Context.get(context, SessionModelRequest.Service);
      return Layer.succeed(SessionModelRequest.Service, {
        ...service,
        primary: input => service.primary(input).pipe(Effect.map(prepared => {
          if (phase === "recovering" || (phase === "ready" && !held.has(input.session.id))) admissions.add(prepared.request);
          return { ...prepared, retry: event => Effect.sync(() => { event.decision = { retry: false }; }) };
        })),
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
        const item = await run(sdk.sessions.prompt({
          sessionID: Session.ID.make(input.sessionId), text: input.text,
          metadata: { operationId: input.operationId, attemptId: input.attemptId, configurationId },
        }));
        return { operationId: input.operationId, attemptId: input.attemptId, sessionId: input.sessionId, inputId: item.id };
      });
    },
    async cancel(sessionId: string) {
      if (["closing", "closed"].includes(phase)) throw new Error("harness_closing");
      if (held.has(sessionId)) throw new Error("recovery_required");
      const id = Session.ID.make(sessionId);
      await run(sdk.sessions.get({ sessionID: id }));
      const interrupted = await run(execution.interrupt(id, { resume: false, reason: "user", awaitSettlement: true }));
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
      const session = await run(sdk.sessions.get({ sessionID: id }));
      const messages = await run(sdk.message.list({ sessionID: id, limit,
        ...(input.cursor === undefined ? { order: input.order ?? "asc" } : { cursor: input.cursor }) }));
      return { session: Schema.encodeSync(Session.Info)(session),
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
