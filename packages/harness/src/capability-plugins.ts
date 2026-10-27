// SPDX-License-Identifier: MIT
import path from 'node:path';
import { createHash } from 'node:crypto';
import { mkdir, readFile, realpath, lstat } from 'node:fs/promises';
import { Context, Effect, Layer, Logger, ManagedRuntime, PubSub, Stream } from 'effect';
import { OpenCode, AbsolutePath, Location, Agent } from '@opencode/sdk/effect';
import { Config } from '@opencode/core/config';
import { ConfigPluginSource } from '@opencode/core/config/plugin/source';
import { InstructionDiscovery } from '@opencode/core/instruction-discovery';
import { AIError, InvalidRequestError, LLMClient, ToolCall, type LLMClientShape } from '@opencode/ai';
import { llmClient } from '@opencode/core/effect/app-node-platform';
import { SessionExecution } from '@opencode/core/session/execution';
import type { Session } from '@opencode/schema/session';
import { SessionMessage } from '@opencode/schema/session-message';
import { SessionRestart } from '@opencode/core/session/execution/restart';
import { Instance } from '@opencode/core/instance';
import { Plugin } from '@opencode/core/plugin';
import { Tool } from '@opencode/core/tool';
import { Error as ToolError } from '@opencode/schema/tool';
import { Npm } from '@opencode/util/npm';
import { Global } from '@opencode/util/global';
import type { Plugin as NativePlugin } from '@opencode/plugin/effect/plugin';

export const CAPABILITY_COHORT = '4b6fea2875e4f2e3e8a8fee181803e54f7056845';
export interface NativeArtifactDescriptor {
  readonly manifest: { readonly native_id: string; readonly artifact_sha256: string;
    readonly tools?: readonly { readonly name: string }[] };
  readonly path: string;
}
export interface CapabilityObservation {
  readonly contract: 'renulus-native-plugin-observation/1';
  readonly isolation: 'disposable' | 'selected-profile';
  readonly plugins: readonly { readonly id: string; readonly source_type: 'local' | 'sdk' | 'builtin' | 'package';
    readonly source_path: string | null; readonly status: 'active' | 'failed' }[];
  readonly artifact_hashes: Readonly<Record<string, string>>;
  readonly registry: readonly { readonly type: 'tool'; readonly name: string; readonly description: string;
    readonly inputSchema: unknown; readonly outputSchema?: unknown }[];
  readonly registry_hash: string;
  readonly quiescent: boolean;
  readonly recovery_held: boolean;
  readonly package_acquisition_closed: boolean;
  readonly effects_denied: boolean;
}
interface NativeHostInspection {
  inspect(): Promise<CapabilityObservation>;
  /** Synthetic proof seam for native invalidation; production lifecycle uses fresh hosts. */
  reobserveForTest?(artifacts: readonly NativeArtifactDescriptor[]): Promise<CapabilityObservation>;
  quiesce?(): Promise<{ state: 'settled' | 'held'; active_operations: number; pending_permissions: number;
    worker_leases: number; uncertain_effects: readonly string[] }>;
}
export type NativeInspectableHost = NativeHostInspection & (
  /** Only closed/cancelled_settled proves release. A bounded close may be blocked. */
  { close(): Promise<{ readonly state: string; readonly outcome: string }>; settled?(): Promise<void> } |
  /** Legacy void adapters must explicitly prove actual release. */
  { close(): Promise<void>; settled(): Promise<void> }
);
export interface NativeHostConfiguration {
  readonly root: string;
  readonly workspace: string;
  readonly databasePath: string;
  readonly isolation: 'disposable' | 'selected-profile';
  readonly artifacts: readonly NativeArtifactDescriptor[];
  readonly baselineTools?: readonly { readonly name: string }[];
}
export interface NativeCompositionRequest {
  readonly operation_id: string;
  readonly artifacts: readonly NativeArtifactDescriptor[];
  readonly baseline_tools: readonly { readonly name: string }[];
}
export interface CapabilityHarnessOptions {
  readonly root: string;
  readonly openHost?: (configuration: NativeHostConfiguration) => Promise<NativeInspectableHost>;
  /** Mandatory for an injected protected factory; the app owns grants and leases. */
  readonly authority?: {
    narrow(request: { readonly operation_id: string; readonly disabled_native_ids: readonly string[] }): Promise<void>;
    quiesce(request: NativeCompositionRequest & { readonly timeout_ms: number }): Promise<{
      state: 'settled' | 'held'; active_operations: number; pending_permissions: number;
      worker_leases: number; uncertain_effects: readonly string[];
    }>;
  };
}

/** Shared by the protected production factory and this closed BF01 inspector.
 * The caller retains store ownership, dispatch admission and recovery overrides.
 * ConfigPluginSource must additionally be closed or supplied an exact local list.
 */
export function closedHarnessEnvironment(state: string, config: string) {
  if (!path.isAbsolute(state)) throw new Error('harness_state_path_absolute');
  return [
    Global.node.replace(Global.layerWith(Object.fromEntries(['home', 'data', 'cache', 'config', 'state', 'tmp', 'bin', 'log', 'repos']
      .map(key => [key, path.join(state, key)])))),
    Config.node.replace(Config.configured({ project: false, global: false, content: config })),
    InstructionDiscovery.node.replace(InstructionDiscovery.configured({ project: false, global: false })),
    Npm.node.replace(Layer.succeed(Npm.Service, {
      add: () => Effect.die(new Error('harness_package_acquisition_closed')),
      update: () => Effect.die(new Error('harness_package_acquisition_closed')),
      resolve: () => Effect.die(new Error('harness_package_acquisition_closed')),
      check: () => Effect.succeed(false), which: () => Effect.succeed(undefined),
    })),
  ];
}

function canonical(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonical);
  if (value !== null && typeof value === 'object') return Object.fromEntries(Object.entries(value)
    .sort(([left], [right]) => left < right ? -1 : left > right ? 1 : 0)
    .map(([key, item]) => [key, canonical(item)]));
  return value;
}
function digest(value: unknown): string {
  return createHash('sha256').update(typeof value === 'string' ? value : JSON.stringify(canonical(value))).digest('hex');
}
function samePath(left: string, right: string): boolean {
  return process.platform === 'win32' ? path.resolve(left).toLowerCase() === path.resolve(right).toLowerCase()
    : path.resolve(left) === path.resolve(right);
}
export async function verifyCapabilityArtifacts(artifacts: readonly NativeArtifactDescriptor[]): Promise<Record<string, string>> {
  const hashes: Record<string, string> = {};
  for (const artifact of artifacts) {
    if (!path.isAbsolute(artifact.path) || !/^[A-Za-z][A-Za-z0-9._-]{0,119}$/.test(artifact.manifest.native_id) ||
        !/^[a-f0-9]{64}$/.test(artifact.manifest.artifact_sha256) || Object.hasOwn(hashes, artifact.manifest.native_id))
      throw new Error('plugin_artifact_identity');
    if (!samePath(await realpath(artifact.path), artifact.path)) throw new Error('plugin_artifact_alias');
    const stat = await lstat(artifact.path);
    if (!stat.isFile() || stat.nlink !== 1 || stat.size < 1 || stat.size > 1024 * 1024 ||
        path.basename(artifact.path) !== 'server.js') throw new Error('plugin_artifact_invalid');
    const actual = createHash('sha256').update(await readFile(artifact.path)).digest('hex');
    if (actual !== artifact.manifest.artifact_sha256) throw new Error('plugin_artifact_integrity');
    hashes[artifact.manifest.native_id] = actual;
  }
  return hashes;
}

/** Pinned OpenCode 4b6fea...; local reviewed files only, never package resolution. */
export async function openCapabilityPluginHost(configuration: NativeHostConfiguration): Promise<NativeInspectableHost> {
  const root = path.resolve(configuration.root), workspace = path.resolve(configuration.workspace);
  const state = path.join(root, 'state', 'capability-native');
  await mkdir(state, { recursive: true }); await mkdir(workspace, { recursive: true });
  if (configuration.databasePath !== ':memory:') await mkdir(path.dirname(configuration.databasePath), { recursive: true });
  await verifyCapabilityArtifacts(configuration.artifacts);
  let execution!: SessionExecution.Interface;
  let instances!: Instance.Interface;
  let artifacts = configuration.artifacts;
  let sourceChanges!: PubSub.PubSub<void>;
  let sourceRevision = 0;
  const denied = () => new AIError({ reason: new InvalidRequestError({ message: 'Capability inspection has no dispatch or effect authority.' }) });
  const client: LLMClientShape = {
    stream: () => Stream.fail(denied()), generate: () => Effect.fail(denied()), compact: () => Effect.fail(denied()),
  };
  const guardId = 'renulus-capability-inspection-guard';
  const guard: NativePlugin = {
    id: guardId,
    effect: context => Effect.gen(function* () {
      // Same trusted boundary as openHarness: remove stock tools before local
      // capabilities register. Never hide undeclared capability tools afterward.
      yield* context.tool.transform(editor => {
        for (const tool of editor.list()) editor.remove(tool.id);
      });
      yield* context.tool.hook('execute.before', () =>
        Effect.fail(new ToolError({ message: 'Capability inspection denies every tool effect.',
          metadata: { code: 'capability_inspection_effects_denied' } })));
    }),
  };
  const config = JSON.stringify({
    mcp: { servers: {} }, compaction: { auto: false },
    // Configured local operations resolve a fixed directory/server.js without
    // npm acquisition. Every artifact has an immutable revision/hash directory.
    plugins: configuration.artifacts.map(item => path.dirname(item.path)),
    agents: { renulus: { mode: 'primary', system: 'Synthetic capability inspection only.',
      permissions: [{ action: '*', resource: '*', effect: 'deny' }] }, title: { disabled: true } },
  });
  const overrides = [
    ...closedHarnessEnvironment(state, config),
    ConfigPluginSource.node.replace(Layer.effect(ConfigPluginSource.Service, Effect.gen(function* () {
      sourceChanges = yield* PubSub.unbounded<void>();
      return ConfigPluginSource.Service.of({
        operations: () => Effect.succeed(artifacts.map(item => ({ type: 'add' as const,
          target: path.dirname(item.path), options: {}, mtime: sourceRevision }))),
        changes: () => Stream.fromPubSub(sourceChanges),
      });
    }))),
    llmClient.replace(Layer.succeed(LLMClient.Service, client)),
    SessionExecution.node.replace(SessionExecution.node.mapLayer(original => Layer.flatMap(original, context => {
      execution = Context.get(context, SessionExecution.Service);
      return Layer.effect(SessionExecution.Service, Effect.context<never>().pipe(Effect.map(ambient => {
        instances = Context.getUnsafe(ambient, Instance.Service);
        return execution;
      })));
    }))),
    SessionRestart.node.replace(Layer.succeed(SessionRestart.Service, { resumeSuspendedSessions: Effect.void })),
  ];
  const runtime = ManagedRuntime.make(Layer.effect(OpenCode.Service, OpenCode.create({
    app: { name: 'renulus-capability-inspection', version: 'bf01-1' },
    database: { path: configuration.databasePath },
    config: { directory: path.join(state, 'config'), project: false, content: config },
    models: { fetch: false, snapshot: false }, fs: { filewatcher: false, fff: false },
    events: { persist: false }, plugins: [guard],
  }, { overrides })).pipe(Layer.provideMerge(Logger.layer([], { mergeWithExisting: false }))));
  const run = <A, E>(effect: Effect.Effect<A, E>) => runtime.runPromise(effect);
  let sdk: OpenCode.Interface;
  try { sdk = await runtime.runPromise(OpenCode.Service); }
  catch (error) { await runtime.dispose(); throw error; }
  let closing: Promise<unknown> | undefined;
  async function inspect(): Promise<CapabilityObservation> {
    if (closing) throw new Error('plugin_host_closing');
    let probe: Session.Info | undefined;
    try {
      const active = await run(execution.active);
      probe = await run(sdk.sessions.create({ title: 'Renulus capability inspection',
        agent: Agent.ID.make('renulus'), location: Location.Ref.make({ directory: AbsolutePath.make(workspace) }) }));
      const observation = await run(Effect.scoped(Effect.gen(function* () {
        yield* Plugin.awaitActivation;
        const plugins = yield* Plugin.Service;
        const inventory = yield* plugins.list();
        const tools = yield* Tool.Service;
        // Registry visibility is not authority: the actual before-execute
        // hook below must still reject every direct/native effect.
        const snapshot = yield* tools.snapshot([{ action: 'execute', resource: '*', effect: 'deny' }]);
        for (const definition of snapshot.definitions) {
          // The guard is tested through native dispatch, not inferred from config.
          const failed = yield* snapshot.execute({ sessionID: probe!.id, agent: Agent.ID.make('renulus'),
            messageID: SessionMessage.ID.create(), call: ToolCall.make({ id: 'capability-inspection',
              type: 'tool-call', name: definition.name, input: {} }) }).pipe(Effect.result);
          if (failed._tag !== 'Failure' || failed.failure.metadata?.code !== 'capability_inspection_effects_denied')
            throw new Error('plugin_effect_guard_failed');
        }
        return { inventory, registry: snapshot.definitions.map(item => ({ ...item })) };
      })).pipe(instances.provide(probe)));
      const registry = observation.registry.sort((left, right) => left.name < right.name ? -1 : left.name > right.name ? 1 : 0);
      return { contract: 'renulus-native-plugin-observation/1', isolation: configuration.isolation,
        plugins: observation.inventory.map(plugin => ({ id: plugin.id ?? '', source_type: plugin.source.type,
          source_path: plugin.source.type === 'local' ? plugin.source.path : null, status: plugin.state.status })),
        artifact_hashes: await verifyCapabilityArtifacts(artifacts), registry,
        registry_hash: digest(registry), quiescent: active.size === 0 && (await run(execution.active)).size === 0,
        recovery_held: true, package_acquisition_closed: true, effects_denied: true };
    } finally {
      if (probe) await run(sdk.sessions.remove({ sessionID: probe.id }));
    }
  }
  return {
    inspect,
    reobserveForTest: async (nextArtifacts: readonly NativeArtifactDescriptor[]): Promise<CapabilityObservation> => {
      if (closing) throw new Error('plugin_host_closing');
      await verifyCapabilityArtifacts(nextArtifacts);
      if (nextArtifacts.length !== artifacts.length || nextArtifacts.some((item, index) =>
          item.manifest.native_id !== artifacts[index]?.manifest.native_id || item.path !== artifacts[index]?.path))
        throw new Error('plugin_reobservation_identity_changed');
      artifacts = nextArtifacts;
      sourceRevision++;
      await run(PubSub.publish(sourceChanges, undefined));
      return inspect();
    },
    async quiesce() {
      if (closing) throw new Error('plugin_host_closing');
      const active = (await run(execution.active)).size;
      return { state: active ? 'held' : 'settled', active_operations: active,
        pending_permissions: 0, worker_leases: 0, uncertain_effects: [] };
    },
    async close() {
      closing ??= runtime.dispose();
      await closing;
      return { state: 'closed', outcome: 'cancelled_settled' };
    },
  };
}

/** Isolated candidate and selected-profile native composition for BF01 proof. */
export function createCapabilityPluginHarness(options: CapabilityHarnessOptions) {
  if (!path.isAbsolute(options.root)) throw new Error('plugin_host_root_absolute');
  if (options.openHost && !options.authority) throw new Error('plugin_app_authority_required');
  const root = path.resolve(options.root);
  const openHost = options.openHost ?? openCapabilityPluginHost;
  let candidate: NativeInspectableHost | undefined;
  let selected: NativeInspectableHost | undefined;
  let closed = false;
  let writing: Promise<void> = Promise.resolve();
  let closing: Promise<void> | undefined;
  function serialize<T>(action: () => Promise<T>, shutdown = false): Promise<T> {
    if (closed && !shutdown) return Promise.reject(new Error('plugin_host_closing'));
    const operation = writing.then(() => {
      if (closed && !shutdown) throw new Error('plugin_host_closing');
      return action();
    });
    writing = operation.then(() => {}, () => {});
    return operation;
  }
  async function retire(kind: 'candidate' | 'selected'): Promise<void> {
    const host = kind === 'candidate' ? candidate : selected;
    if (!host) return;
    const proof = await host.close();
    if (proof === undefined) {
      if (!host.settled) throw new Error('plugin_host_close_proof_required');
      await host.settled();
    } else if (proof.state !== 'closed' || proof.outcome !== 'cancelled_settled') {
      throw new Error('plugin_host_close_held');
    }
    // Retain the exact handle through refusal, timeout and finalizer errors.
    if (kind === 'candidate') candidate = undefined;
    else selected = undefined;
  }
  return {
    inspectCandidate: (request: NativeCompositionRequest) => serialize(async () => {
      if (!/^[a-z][a-z0-9.-]{0,119}$/.test(request.operation_id)) throw new Error('plugin_operation_id_invalid');
      await retire('candidate');
      const directory = path.join(root, 'state', 'plugin-lifecycle', 'native-candidates', request.operation_id);
      candidate = await openHost({ root: directory, workspace: path.join(directory, 'workspace'),
        databasePath: ':memory:', isolation: 'disposable', artifacts: request.artifacts,
        baselineTools: request.baseline_tools });
      try { return await candidate.inspect(); }
      finally { await retire('candidate'); }
    }),
    // This BF01 composition has no effect admission surface. The production
    // adapter must instead revoke these IDs at its current grant epoch.
    async narrow(request: { readonly operation_id: string; readonly disabled_native_ids: readonly string[] }) {
      if (closed) throw new Error('plugin_host_closing');
      await options.authority?.narrow(request);
    },
    async quiesce(request: NativeCompositionRequest & { readonly timeout_ms: number }) {
      if (closed) throw new Error('plugin_host_closing');
      if (options.authority) return options.authority.quiesce(request);
      if (selected && !selected.quiesce) throw new Error('plugin_quiescence_unavailable');
      return selected?.quiesce ? await selected.quiesce() : { state: 'settled' as const,
        active_operations: 0, pending_permissions: 0, worker_leases: 0, uncertain_effects: [] };
    },
    restart: (request: NativeCompositionRequest) => serialize(async () => {
      await retire('selected');
      selected = await openHost({ root, workspace: path.join(root, 'harness-workspace'),
        // The standalone proof never opens the production harness store. A
        // supplied protected factory owns its store selection and writer lease.
        databasePath: path.join(root, 'state', 'plugin-lifecycle', 'native-selected', 'opencode.sqlite'),
        isolation: 'selected-profile', artifacts: request.artifacts, baselineTools: request.baseline_tools });
      try { return await selected.inspect(); }
      catch (error) { await retire('selected'); throw error; }
    }),
    close() {
      closed = true;
      return closing ??= serialize(async () => {
        const results = await Promise.allSettled([retire('candidate'), retire('selected')]);
        for (const result of results) if (result.status === 'rejected') throw result.reason;
      }, true).catch(error => { closing = undefined; throw error; });
    },
  };
}
