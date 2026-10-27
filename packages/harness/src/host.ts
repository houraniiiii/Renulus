import path from "node:path";
import { createHash } from "node:crypto";
import { mkdir } from "node:fs/promises";
import { Cause, Context, Effect, Layer, Logger, ManagedRuntime, Schema, Stream } from "effect";
import { AIError, InvalidRequestError, LLMClient, LLMRequest, Media, type LLMClientShape, type Message, type SystemPart } from "@opencode/ai";
import { OpenCode, AbsolutePath, Location, Session, Agent } from "@opencode/sdk/effect";
import { Config } from "@opencode/core/config";
import { ConfigPluginSource } from "@opencode/core/config/plugin/source";
import { Agent as NativeAgent } from "@opencode/core/agent";
import { InstructionDiscovery } from "@opencode/core/instruction-discovery";
import { llmClient } from "@opencode/core/effect/app-node-platform";
import { SessionRestart } from "@opencode/core/session/execution/restart";
import { SessionExecution } from "@opencode/core/session/execution";
import { SessionStore } from "@opencode/core/session/store";
import { Job } from "@opencode/core/job";
import { createSessionTransfer, nativeSessionId, type TransferFrame, type TransferCommand, type StagePayload, type ImportTarget } from "./session-transfer.ts";
import { SessionModelRequest } from "@opencode/core/session/model-request";
import { SessionRunnerModel } from "@opencode/core/session/runner/model";
import { SessionContext as NativeSessionContext } from "@opencode/core/session/context";
import type { StreamOptions } from "@opencode/ai/route/client";
import { Instance } from "@opencode/core/instance";
import { Plugin } from "@opencode/core/plugin";
import { PluginHooks } from "@opencode/core/plugin/hooks";
import type { SessionContext } from "@opencode/plugin/effect/session";
import { Tool } from "@opencode/core/tool";
import { Npm } from "@opencode/util/npm";
import { Global } from "@opencode/util/global";
import { SessionMessage } from "@opencode/schema/session-message";
import { acquireStore } from "./ownership.ts";
import { verifyPreparedProfile, type ProfileSelection } from "./manifest.ts";
import { activateStores, validateStores } from "./stores.ts";
import { createLibraryPlugin, type LibraryToolBridge } from "./domain-tools.ts";
import { closedHarnessEnvironment, verifyCapabilityArtifacts, type NativeArtifactDescriptor } from "./capability-plugins.ts";
import type { Plugin as NativePlugin } from "@opencode/plugin/effect/plugin";
import type { NativeCapabilities } from "./native-capability-plugin.ts";
import type { LayerNode } from "@opencode/util/effect/layer-node";
import { SessionTransfer as NativeSessionTransfer } from "@opencode/core/session/transfer";

export interface ModelAdapter {
  readonly providerId: string;
  readonly modelId: string;
  readonly configuration: object;
  readonly client: LLMClientShape;
  readonly preparePrimary?: (binding: NativeInputBinding, model: SessionRunnerModel.Resolved) =>
    Effect.Effect<PrimaryModelPreparation, AIError>;
}

export interface PrimaryModelPreparation {
  readonly resolved: SessionRunnerModel.Resolved;
  /** Reuse the same trusted preparation after native hooks and context selection. */
  readonly prepare: (request: LLMRequest, settings: StreamOptions, unfiltered: LLMRequest) =>
    Effect.Effect<LLMRequest, AIError>;
}

export interface HarnessOptions extends ProfileSelection {
  readonly processGeneration?: string;
  readonly model?: ModelAdapter;
  readonly library?: LibraryToolBridge;
  /** Reviewed immutable local bytes, selected by the owning backend. */
  readonly capabilityArtifacts?: readonly NativeArtifactDescriptor[];
  /** Current host-resolved native permission IDs; plugin bytes cannot mint them. */
  readonly capabilityPermissions?: readonly string[];
  /** Trusted application built-ins only; never accepted from JSON/artifact code. */
  readonly trustedPlugins?: readonly NativePlugin[];
  readonly nativeCapabilities?: NativeCapabilities;
  /** Trusted RAM graph composition; caller supplies the pinned database and no-spill FS replacements. */
  readonly volatileGraph?: { readonly overrides: LayerNode.Replacements };
  readonly admitInput?: (binding: NativeInputBinding) => Promise<void>;
  readonly selectContext?: (binding: NativeInputBinding, messages: readonly Message[]) =>
    Promise<readonly Message[] | NativeContextSelection>;
}

export interface NativeContextSelection {
  readonly messages: readonly Message[];
  /** Trusted data context appended to native ordered system parts. */
  readonly additionalSystem?: readonly SystemPart[];
}

export interface NativeInputBinding {
  readonly operation_id: string;
  readonly attempt_id: string;
  readonly session_id: string;
  readonly input_id: string;
  readonly cancellation_id: string;
}

function imageFiles(value: unknown): { uri: string }[] | undefined {
  if (value === undefined) return undefined;
  if (!Array.isArray(value) || value.length > 4) throw new Error("invalid_images");
  let total = 0;
  return value.map(image => {
    if (!image || typeof image !== "object" || Array.isArray(image) ||
        Object.keys(image).sort().join(",") !== "data,media_type,type" || image.type !== "image" ||
        !["image/png", "image/jpeg", "image/webp"].includes(image.media_type) || typeof image.data !== "string" ||
        image.data.length > 11184812 ||
        !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(image.data))
      throw new Error("invalid_images");
    const bytes = Buffer.from(image.data, "base64");
    total += bytes.length;
    if (!bytes.length || bytes.length > 8 * 1024 * 1024 || total > 16 * 1024 * 1024 ||
        bytes.toString("base64") !== image.data || Media.detectMediaType(bytes) !== image.media_type)
      throw new Error("invalid_images");
    // Only validated inline bytes enter the SDK's public data-URI attachment
    // seam. Python's managed decoder must separately admit actual inference.
    return { uri: `data:${image.media_type};base64,${image.data}` };
  });
}

/** A persistent execution owner. Domain records continue to belong to Python. */
export async function openHarness(options: HarnessOptions) {
  const selection = options.volatileGraph ? undefined : await verifyPreparedProfile(options);
  if (selection?.state === "active") validateStores(options);
  let storesActive = selection?.state === "active";
  const root = path.resolve(options.root);
  const state = path.join(root, "state", "harness");
  const workspace = path.join(root, "harness-workspace");
  const capabilityArtifacts = structuredClone(options.capabilityArtifacts ?? []);
  const capabilityPermissions = [...(options.capabilityPermissions ?? [])];
  if (capabilityPermissions.some(value => !/^[a-z][a-z0-9_.-]{0,159}$/.test(value)))
    throw new Error("harness_capability_permission_invalid");
  const checkCapabilityArtifacts = () => verifyCapabilityArtifacts(capabilityArtifacts);
  await checkCapabilityArtifacts();
  if (!options.volatileGraph) { await mkdir(state, { recursive: true }); await mkdir(workspace, { recursive: true }); }
  const ownership = options.volatileGraph ? { release: async () => {} } : await acquireStore(state, options.storeId);
  let phase = "policy_blocked";
  let capabilityObservation: {
    plugins: { id: string; source_type: "local" | "sdk" | "builtin" | "package"; source_path: string | null; status: "active" | "failed" }[];
    artifact_hashes: Record<string, string>;
  } | undefined;
  let configurationId: string | undefined;
  let store!: SessionStore.Interface;
  let execution!: SessionExecution.Interface;
  let jobs!: Job.Interface;
  let instances!: Instance.Interface;
  const held = new Set<string>();
  const bindings = new Map<string, NativeInputBinding>();
  const primaryLoad = Context.Reference<NativeInputBinding | undefined>("Renulus.PrimaryModelLoad", {
    defaultValue: () => undefined,
  });
  const primaryPreparations = new WeakMap<object, {
    readonly binding: NativeInputBinding; readonly preparation: PrimaryModelPreparation;
  }>();
  const primaryContexts = new Map<string, {
    readonly binding: NativeInputBinding | undefined;
    snapshot?: Pick<SessionContext, "system" | "messages">;
  }>();
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
        ...capabilityPermissions.map(action => ({ action, resource: "*", effect: "allow" })),
      ] },
      title: { disabled: true },
      ...(options.nativeCapabilities?.child ? { 'evidence-review': { mode: 'subagent',
        system: 'Review the bounded supplied nephrology learning evidence and return a concise cited report.',
        permissions: [{ action: '*', resource: '*', effect: 'deny' },
          ...(options.library ? [{ action: 'renulus.library', resource: '*', effect: 'allow' }] : [])] } } : {}),
    },
  });
  const overrides = [
    ...closedHarnessEnvironment(state, config),
    ConfigPluginSource.node.replace(Layer.succeed(ConfigPluginSource.Service, {
      operations: () => Effect.succeed(capabilityArtifacts.map(artifact => ({ type: "add" as const,
        target: path.dirname(artifact.path), options: {}, mtime: 0 }))),
      changes: () => Stream.never,
    })),
    llmClient.replace(Layer.succeed(LLMClient.Service, client)),
    // The reviewed cohort is already bundled. Candidate and admitted hosts
    // cannot acquire or update executable packages at runtime.
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
    NativeSessionContext.node.replace(NativeSessionContext.node.mapLayer(original => Layer.flatMap(original, context => {
      const service = Context.get(context, NativeSessionContext.Service);
      return Layer.succeed(NativeSessionContext.Service, { ...service,
        load: selection => {
          if (!options.model?.preparePrimary) return service.load(selection);
          const binding = bindings.get(selection.session.id);
          if (!binding || !["ready", "recovering"].includes(phase) || held.has(selection.session.id))
            return Effect.die(denied());
          // Scope resolution to this primary load. Auxiliary title resolution
          // must not allocate a primary plan, even for the same session.
          return service.load(selection).pipe(Effect.provideService(primaryLoad, binding));
        },
      });
    }))),
    SessionRunnerModel.node.replace(SessionRunnerModel.node.mapLayer(original => Layer.flatMap(original, context => {
      const service = Context.get(context, SessionRunnerModel.Service);
      return Layer.succeed(SessionRunnerModel.Service, { ...service,
        resolve: (session, available) => Effect.gen(function* () {
          const initial = yield* service.resolve(session, available);
          const binding = yield* primaryLoad;
          if (!binding) return initial;
          const requireCurrent = () => {
            if (binding.session_id !== session.id || bindings.get(session.id) !== binding ||
                !["ready", "recovering"].includes(phase) || held.has(session.id)) throw denied();
          };
          requireCurrent();
          const preparation = yield* options.model!.preparePrimary!(binding, initial).pipe(Effect.orDie);
          requireCurrent();
          if (primaryPreparations.has(preparation.resolved)) throw denied();
          primaryPreparations.set(preparation.resolved, { binding, preparation });
          // History provenance, tool preparation and saved assistant identity
          // now use the same trusted model that will serialize the request.
          return preparation.resolved;
        }),
      });
    }))),
    PluginHooks.node.replace(PluginHooks.node.mapLayer(original => Layer.flatMap(original, context => {
      const service = Context.get(context, PluginHooks.Service);
      const trigger: typeof service.trigger = (domain, name, event) => service.trigger(domain, name, event).pipe(
        Effect.flatMap(shaped => Effect.gen(function* () {
          if (domain !== "session" || name !== "context") return shaped;
          const draft = shaped as SessionContext;
          const current = primaryContexts.get(draft.sessionID);
          if (!current) return shaped;
          const requireCurrent = () => {
            if (primaryContexts.get(draft.sessionID) !== current ||
                !["ready", "recovering"].includes(phase) || held.has(draft.sessionID) ||
                (current.binding && bindings.get(draft.sessionID) !== current.binding)) throw denied();
          };
          requireCurrent();
          if (options.selectContext) {
            if (!current.binding) throw denied();
            const selected = yield* Effect.promise(() => options.selectContext!(current.binding!, draft.messages));
            if ("messages" in selected) {
              draft.messages = [...selected.messages];
              draft.system = [...draft.system, ...(selected.additionalSystem ?? [])];
            } else draft.messages = [...selected];
            requireCurrent();
          }
          // This is the shaped native context before unsupportedParts/boundImages.
          // Copy it while owned; final preparation receives the same surviving
          // tool definitions that native preparation advertises.
          current.snapshot = structuredClone({ system: draft.system, messages: draft.messages });
          return shaped;
        })),
      );
      return Layer.succeed(PluginHooks.Service, { ...service, trigger });
    }))),
    SessionModelRequest.node.replace(SessionModelRequest.node.mapLayer(original => Layer.flatMap(original, context => {
      const service = Context.get(context, SessionModelRequest.Service);
      return Layer.succeed(SessionModelRequest.Service, {
        ...service,
        primary: input => Effect.gen(function* () {
          const binding = bindings.get(input.session.id);
          const requireBinding = () => {
            if (!binding || bindings.get(input.session.id) !== binding ||
                !["ready", "recovering"].includes(phase) || held.has(input.session.id)) throw denied();
            return binding;
          };
          const selected = primaryPreparations.get(input.model);
          const preparation = options.model?.preparePrimary ? selected?.preparation : undefined;
          if (options.model?.preparePrimary && (!selected || selected.binding !== requireBinding())) throw denied();
          primaryPreparations.delete(input.model);
          if (preparation) requireBinding();
          // Native primary shapes media against this exact resolved capability
          // snapshot. Preparing only its final request would lose images first.
          if (primaryContexts.has(input.session.id)) throw denied();
          const context = { binding, snapshot: undefined as Pick<SessionContext, "system" | "messages"> | undefined };
          primaryContexts.set(input.session.id, context);
          const prepared = yield* service.primary(preparation ? { ...input, model: preparation.resolved } : input).pipe(
            Effect.ensuring(Effect.sync(() => {
              if (primaryContexts.get(input.session.id) === context) primaryContexts.delete(input.session.id);
            })),
          );
          let request = prepared.request;
          if (preparation) {
            requireBinding();
            if (!context.snapshot) throw denied();
            // structuredClone detaches the snapshot but removes Media.Asset's
            // prototype. Restore the public asset from its exact copied source
            // before the native request codec validates the input.
            const messages = context.snapshot.messages.map(message => ({ ...message,
              content: message.content.map(part => part.type === "media"
                ? { ...part, media: new Media.Asset(part.media) } : part),
            }));
            const unfiltered = LLMRequest.update(request, { system: context.snapshot.system, messages,
              tools: structuredClone(request.tools) });
            request = yield* preparation.prepare(request, prepared.options, unfiltered);
            requireBinding();
          }
          if (phase === "recovering" || (phase === "ready" && !held.has(input.session.id))) admissions.add(request);
          return { ...prepared, request, retry: (event: Parameters<typeof prepared.retry>[0]) =>
            Effect.sync(() => { event.decision = { retry: false }; }) };
        }).pipe(Effect.orDie),
      });
    }))),
    SessionRestart.node.replace(SessionRestart.node.mapLayer(original => Layer.flatMap(original, context => {
      const service = Context.get(context, SessionRestart.Service);
      return Layer.succeed(SessionRestart.Service, {
        resumeSuspendedSessions: options.volatileGraph ? Effect.sync(recovered) : Effect.promise(() => recoveryPermit).pipe(
          Effect.andThen(service.resumeSuspendedSessions), Effect.tap(() => Effect.sync(recovered)),
          Effect.onExit(exit => Effect.sync(() => { if (exit._tag === "Failure") recoveryFailed(Cause.squash(exit.cause)); })),
        ),
      });
    }))),
    ...(options.nativeCapabilities?.overrides ?? []),
    ...(options.volatileGraph?.overrides ?? []),
  ];
  const creation = OpenCode.create({
    app: { name: "renulus", version: "opencode-foundation-1" },
    database: { path: options.volatileGraph ? ':memory:' : path.join(state, "opencode.sqlite") },
    config: { directory: path.join(state, "config"), project: false, content: config },
    models: { fetch: false, snapshot: false },
    fs: { filewatcher: false, fff: false },
    events: { persist: false },
    plugins: options.library || options.capabilityArtifacts !== undefined || options.trustedPlugins || options.nativeCapabilities ? [
      ...(options.nativeCapabilities ? [options.nativeCapabilities.capture] : []), {
      id: "renulus-internal-tool-boundary",
      effect: context => context.tool.transform(editor => {
        for (const tool of editor.list()) editor.remove(tool.id);
      }).pipe(Effect.asVoid),
    }, ...(options.library ? [createLibraryPlugin(options.library)] : []),
      ...(options.trustedPlugins ?? []), ...(options.nativeCapabilities?.plugins ?? [])] : [],
  }, { overrides });
  const runtime = ManagedRuntime.make(Layer.effect(OpenCode.Service,
    options.nativeCapabilities ? options.nativeCapabilities.provide(creation) : creation
  ).pipe(Layer.provideMerge(Logger.layer([], { mergeWithExisting: false }))));
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
  const transfer = options.processGeneration && !options.volatileGraph ? createSessionTransfer({ sdk, run,
    scope: { profileId: options.profileId, storeId: options.storeId, generation: options.processGeneration,
      location: Location.Ref.make({ directory: AbsolutePath.make(workspace) }) },
    checkCurrent: () => {
      if (phase !== "store_transfer" || !storesActive) throw new Error("harness_policy_blocked");
    },
  }) : undefined;
  const mutate = async <A>(action: () => Promise<A>) => {
    requireReady();
    let settled!: () => void;
    const lease = new Promise<void>(resolve => { settled = resolve; });
    admittedWrites.add(lease);
    try { return await action(); }
    finally { admittedWrites.delete(lease); settled(); }
  };
  return {
    async transferCommand(frame: TransferFrame, command: TransferCommand, payload: Record<string, unknown>) {
      requireReady();
      if (!transfer || !storesActive) throw new Error("harness_policy_blocked");
      phase = "store_transfer";
      let settle!: () => void;
      const lease = new Promise<void>(resolve => { settle = resolve; });
      admittedWrites.add(lease);
      try {
        if ((await run(execution.active)).size || held.size) throw new Error("recovery_requires_quiescence");
        switch (command) {
          case "session.import.stage": return transfer.stage(frame, payload as unknown as StagePayload);
          case "session.import": return await transfer.commit(frame, payload as unknown as ImportTarget);
          case "session.import.inspect": return await transfer.inspect(frame, payload as unknown as ImportTarget);
          case "session.remove": return await transfer.remove(frame, payload as unknown as { sessionId: string });
          case "operation.retire":
            if (Object.keys(payload).length) throw new Error("invalid_payload");
            return transfer.retire(frame);
        }
      } finally {
        if (phase === "store_transfer") phase = "ready";
        admittedWrites.delete(lease); settle();
      }
    },
    async inspect() {
      if (phase !== "policy_blocked" || admittedWrites.size) {
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
        const observed = await run(Effect.gen(function* () {
            yield* Plugin.awaitActivation;
            const plugins = yield* Plugin.Service;
            const inventory = yield* plugins.list();
            if (inventory.some(plugin => plugin.state.status === "failed")) {
              throw new Error("harness_candidate_plugin_failed");
            }
            const agents = yield* NativeAgent.Service;
            const agent = yield* agents.get(Agent.ID.make("renulus"));
            if (!agent) throw new Error("harness_candidate_agent_missing");
            const tools = yield* Tool.Service;
            // Inspect the complete final transform, independently of execution
            // permissions. Otherwise an undeclared denied tool could be hidden
            // from the immutable registry receipt and become visible later.
            return { definitions: (yield* tools.snapshot([{ action: "execute", resource: "*", effect: "deny" }])).definitions, inventory };
        }).pipe(instances.provide(session)));
        const artifact_hashes = await checkCapabilityArtifacts();
        const inventory = observed.inventory.map(plugin => ({ id: plugin.id ?? "", source_type: plugin.source.type,
          source_path: plugin.source.type === "local" ? plugin.source.path : null, status: plugin.state.status }));
        const expected = new Map(capabilityArtifacts.map(artifact => [artifact.manifest.native_id, artifact]));
        for (const item of inventory) {
          if (item.source_type === "package" || item.source_type === "local" && (!expected.has(item.id) ||
              path.resolve(item.source_path!).toLowerCase() !== path.resolve(expected.get(item.id)!.path).toLowerCase()))
            throw new Error("harness_capability_identity_mismatch");
        }
        if ([...expected.keys()].some(id => !inventory.some(item => item.id === id && item.status === "active")))
          throw new Error("harness_capability_identity_missing");
        capabilityObservation = { plugins: inventory, artifact_hashes };
        const registry = observed.definitions.map(tool => ({ ...tool }))
          .sort((left, right) => left.name < right.name ? -1 : left.name > right.name ? 1 : 0);
        const canonical = (value: unknown): unknown => Array.isArray(value) ? value.map(canonical)
          : value !== null && typeof value === "object" ? Object.fromEntries(Object.entries(value)
            .sort(([left], [right]) => left < right ? -1 : left > right ? 1 : 0)
            .map(([key, item]) => [key, canonical(item)])) : value;
        return { state: "policy_blocked", generation_open: false, recovery_open: false,
          package_acquisition_open: false, mcp_startup_open: false, live_store_writer: storesActive, registry,
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
    /** Additive in-process observation; harness/1 host.inspect keeps its shape. */
    async inspectCapabilities(isolation: "disposable" | "selected-profile") {
      const result = await this.inspect();
      return { contract: "renulus-native-plugin-observation/1" as const, isolation,
        ...capabilityObservation!, registry: result.registry, registry_hash: result.registry_hash,
        quiescent: true, recovery_held: !recoveryStarted, package_acquisition_closed: true,
        effects_denied: true };
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
    /** Child authority registers its allocated child USER here before native prompt admission. */
    bindChild(binding: NativeInputBinding) {
      if (!options.nativeCapabilities?.child || phase !== "ready" || held.has(binding.session_id) || bindings.has(binding.session_id))
        throw new Error("native_child_binding_conflict");
      bindings.set(binding.session_id, Object.freeze({ ...binding }));
    },
    async activateStores() {
      if (options.volatileGraph) throw new Error('volatile_store_activation_forbidden');
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
        storesActive = selected.state === "active";
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
    async exportSession(sessionId: string) {
      return mutate(async () => {
        const id=Session.ID.make(sessionId);if(await run(execution.isActive(id)))throw new Error('transfer_requires_quiescence');
        return Schema.encodeSync(NativeSessionTransfer.Data)(await run(sdk.sessions.export({sessionID:id,sanitize:false})));
      });
    },
    async importSession(data: typeof NativeSessionTransfer.Data.Encoded) {
      return mutate(async () => {
        if((await run(execution.active)).size)throw new Error('transfer_requires_quiescence');
        const decoded=Schema.decodeUnknownSync(NativeSessionTransfer.Data)(data);
        const imported=await run(sdk.sessions.import({...decoded,info:{...decoded.info,permissions:[{action:'*',resource:'*',effect:'deny'}]},
          location:Location.Ref.make({directory:AbsolutePath.make(workspace)})}));
        await run(sdk.sessions.update({sessionID:imported.id,permissions:[{action:'*',resource:'*',effect:'deny'}]}));
        return Schema.encodeSync(Session.Info)(imported);
      });
    },
    async removeSession(sessionId: string) { return mutate(async()=>{
      const id=Session.ID.make(sessionId);if(await run(execution.isActive(id)))throw new Error('transfer_requires_quiescence');
      await run(sdk.sessions.remove({sessionID:id}));bindings.delete(sessionId);
    }); },
    async listChildren(sessionId: string) { requireReady();return (await run(sdk.sessions.list({parentID:Session.ID.make(sessionId),limit:100}))).data.map(info=>Schema.encodeSync(Session.Info)(info)); },
    async recover(input: { configurationId: string; sessionIds: string[] }) {
      requireReady();
      if (input.configurationId !== configurationId || JSON.stringify([...input.sessionIds].sort()) !== JSON.stringify([...held].sort())) {
        throw new Error("recovery_admission_mismatch");
      }
      // Recovered claims have no reconstructed Python run/input authority yet.
      // Keep them durable: a late primary denial would already have released
      // the recovery gate and could terminalize the retained execution.
      if (options.model?.preparePrimary && held.size) throw new Error("recovery_admission_unavailable");
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
    async submit(input: { sessionId: string; operationId: string; attemptId: string; text: string; images?: unknown }) {
      return mutate(async () => {
        if (held.has(input.sessionId)) throw new Error("recovery_required");
        const files = imageFiles(input.images);
        const inputId = SessionMessage.ID.create();
        const binding = Object.freeze({ operation_id: input.operationId, attempt_id: input.attemptId,
          session_id: input.sessionId, input_id: inputId, cancellation_id: input.operationId });
        // Parent authority is pinned before native admission can schedule work.
        // A lost acknowledgement stays uncertain and must never mint a new input.
        await options.admitInput?.(binding);
        requireReady();
        if (options.admitInput) {
          const sessionID = Session.ID.make(input.sessionId);
          const current = await run(sdk.sessions.get({ sessionID }));
          requireReady();
          const metadata = current.metadata;
          if (metadata?.legacyConversationId !== undefined || metadata?.bundleDigest !== undefined) {
            if (Object.keys(metadata).sort().join(",") !== "bundleDigest,legacyConversationId,lineage,operationId,renulusProfile,renulusStore" ||
                metadata.renulusProfile !== options.profileId || metadata.renulusStore !== options.storeId ||
                typeof metadata.legacyConversationId !== "string" || !metadata.legacyConversationId ||
                typeof metadata.bundleDigest !== "string" || !/^[a-f0-9]{64}$/.test(metadata.bundleDigest) ||
                typeof metadata.operationId !== "string" || !metadata.operationId || metadata.lineage !== "unknown" ||
                nativeSessionId(options.profileId, options.storeId, metadata.legacyConversationId) !== input.sessionId ||
                current.parentID !== undefined || current.fork !== undefined || current.location.directory !== workspace)
              throw new Error("native_migrated_identity_conflict");
            // Import remains inert. Only an authenticated new root admission
            // selects the learning agent and replaces its session deny fence.
            await run(sdk.sessions.switchAgent({ sessionID, agent: Agent.ID.make("renulus") }));
            requireReady();
            await run(sdk.sessions.update({ sessionID, permissions: [
              { action: "*", resource: "*", effect: "deny" },
              ...(options.library ? [{ action: "renulus.library", resource: "*", effect: "allow" as const }] : []),
            ] }));
            requireReady();
          }
        }
        bindings.set(input.sessionId, binding);
        const item = await run(sdk.sessions.prompt({
          sessionID: Session.ID.make(input.sessionId), id: inputId, text: input.text, files,
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
      const binding = bindings.get(sessionId);
      if (binding) await options.nativeCapabilities?.stop(binding.operation_id, binding);
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
      transfer?.seal();
      closing ??= (async () => {
        await Promise.all([...admittedWrites]);
        await transfer?.settled();
        await options.nativeCapabilities?.close();
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
