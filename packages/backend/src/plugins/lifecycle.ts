// SPDX-License-Identifier: MIT
import { mkdir, open, readFile, rename, rm, unlink } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
import path from 'node:path';
import { activationOrder, canonical, PluginLifecycleError, reject, sha256, validateSelection } from './manifest.ts';
import { readArtifact, validateObservation, validateReceipt, verifyArtifactHashes } from './validate.ts';
import type { InspectionReceipt, NativeArtifact, NativeInspectionRequest, PluginLifecycleOptions,
  PluginLifecycleStatus, SelectedPlugin } from './types.ts';

const CONTRACT = 'renulus-plugin-lifecycle/1';
interface PersistedLifecycle {
  readonly contract: typeof CONTRACT;
  readonly revision: number;
  readonly selected_operation_id: string | null;
  readonly selected: readonly SelectedPlugin[];
  readonly active_operation_id: string | null;
  readonly active: readonly SelectedPlugin[];
  readonly active_registry_hash: string | null;
  held: string | null;
  failed: { readonly operation_id: string; readonly requested: readonly SelectedPlugin[]; readonly error: string } | null;
  readonly receipt?: InspectionReceipt;
}
interface Operation {
  readonly request: NativeInspectionRequest;
  readonly receipt: InspectionReceipt;
}
interface EffectiveSelection {
  readonly contract: 'renulus-plugin-effective/1';
  readonly operation_id: string;
  readonly selected: readonly SelectedPlugin[];
  readonly receipt: InspectionReceipt;
}

/**
 * Immutable add/edit/disable/remove. Lifecycle files are separate from BF00
 * canonical records; the host performs actual cancellation and restart.
 */
export function createPluginLifecycle(options: PluginLifecycleOptions) {
  const root = path.resolve(options.root);
  const directory = path.join(root, 'state', 'plugin-lifecycle');
  const selectionFile = path.join(directory, 'selection.json');
  const activeFile = path.join(directory, 'active.json');
  const effectiveFile = path.join(directory, 'effective.json');
  const knownMigrations = structuredClone(options.knownMigrations ?? {});
  const allowUnknown = options.allowUnknownMigrations === true;
  const baselineTools = structuredClone(options.baselineTools ?? []);
  const timeout = options.quiescenceTimeoutMs ?? 30_000;
  if (!path.isAbsolute(options.root) || !Number.isFinite(timeout) || timeout < 0 || timeout > 300_000)
    throw new PluginLifecycleError('plugin_lifecycle_options');
  const newOperation = options.operationId ?? (() => 'op-' + randomUUID());
  const empty: PersistedLifecycle = { contract: CONTRACT, revision: 0, selected_operation_id: null,
    selected: [], active_operation_id: null, active: [], active_registry_hash: null, held: null, failed: null };
  let state: PersistedLifecycle = { ...empty };
  const update = (change: Partial<PersistedLifecycle>) => { state = { ...state, ...change }; };
  let initialized = false;
  let writing: Promise<void> = Promise.resolve();
  let current: Operation | undefined;
  let closed = false;
  let lastError: string | null = null;
  let effective: EffectiveSelection | null = null;
  let reobserved = false;

  function checkSelection(selection: readonly SelectedPlugin[]): void {
    validateSelection(selection, options.cohortSource, knownMigrations, allowUnknown);
  }
  function validState(value: unknown): PersistedLifecycle {
    if (!value || typeof value !== 'object' || Array.isArray(value)) reject('plugin_lifecycle_state_invalid');
    const candidate = value as Partial<PersistedLifecycle>;
    if (candidate.contract !== CONTRACT || !Number.isSafeInteger(candidate.revision) || Number(candidate.revision) < 0 ||
        (candidate.selected_operation_id !== null && typeof candidate.selected_operation_id !== 'string') ||
        (candidate.active_operation_id !== null && typeof candidate.active_operation_id !== 'string') ||
        (candidate.active_registry_hash !== null && typeof candidate.active_registry_hash !== 'string') ||
        (candidate.held !== null && typeof candidate.held !== 'string') || !Array.isArray(candidate.selected) ||
        !Array.isArray(candidate.active) || (candidate.failed !== null && candidate.failed !== undefined &&
        (typeof candidate.failed !== 'object' || Array.isArray(candidate.failed) || typeof candidate.failed.operation_id !== 'string' ||
        !Array.isArray(candidate.failed.requested) || typeof candidate.failed.error !== 'string'))) reject('plugin_lifecycle_state_invalid');
    checkSelection(candidate.selected!); checkSelection(candidate.active!);
    if (candidate.failed) checkSelection(candidate.failed.requested);
    if ((candidate.selected_operation_id === null && candidate.selected.length !== 0) ||
        (candidate.active_operation_id === null && candidate.active.length !== 0) ||
        (candidate.active_operation_id !== null && candidate.active_registry_hash === null))
      reject('plugin_lifecycle_state_invalid');
    if ((candidate.active_operation_id === null) !== (candidate.active_registry_hash === null)) reject('plugin_lifecycle_state_invalid');
    return structuredClone(candidate) as PersistedLifecycle;
  }
  async function loadState(file: string, fallback: PersistedLifecycle): Promise<PersistedLifecycle> {
    try { return validState(JSON.parse(await readFile(file, 'utf8'))); }
    catch (error) {
      if (error instanceof PluginLifecycleError) throw error;
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return structuredClone(fallback);
      throw new PluginLifecycleError('plugin_lifecycle_state_unreadable', { cause: error });
    }
  }
  async function initialize(): Promise<void> {
    if (initialized) return;
    const selected = await loadState(selectionFile, empty);
    const active = await loadState(activeFile, empty);
    if (active.active_operation_id !== null &&
        (active.active_operation_id !== active.selected_operation_id ||
        canonical(active.active) !== canonical(active.selected))) reject('plugin_active_state_inconsistent');
    // Selection is a requested generation, never evidence that it displaced
    // the last healthy generation. Only a verified restart publishes active.
    state = { ...selected, active: active.active, active_operation_id: active.active_operation_id,
      active_registry_hash: active.active_registry_hash, failed: selected.failed ?? active.failed };
    try {
      const value = JSON.parse(await readFile(effectiveFile, 'utf8')) as EffectiveSelection;
      if (value?.contract !== 'renulus-plugin-effective/1' || !/^[a-z][a-z0-9.-]{0,119}$/.test(value.operation_id))
        reject('plugin_effective_state_invalid');
      checkSelection(value.selected);
      validateReceipt(value.receipt, value.selected, baselineTools);
      if (value.receipt.operation_id !== value.operation_id) reject('plugin_candidate_receipt_mismatch');
      effective = value;
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
      // Existing partial WIP state is not activation proof. Explicit staging
      // and activation are required to create the effective selector.
      if (active.active_operation_id !== null) update({ held: 'plugin_effective_selection_required' });
    }
    // Rebuild paths from the reviewed manifests instead of trusting persisted
    // candidate paths. A missing or stale receipt requires fresh inspection.
    if (selected.selected_operation_id) {
      try {
        const receipt = selected.receipt ?? (active.receipt &&
          active.selected_operation_id === selected.selected_operation_id &&
          active.active_operation_id === selected.selected_operation_id &&
          canonical(active.selected) === canonical(selected.selected) ? active.receipt : undefined);
        if (!receipt) reject('plugin_candidate_receipt_missing');
        validateReceipt(receipt, selected.selected, baselineTools);
        if (receipt.operation_id !== selected.selected_operation_id) reject('plugin_candidate_receipt_mismatch');
        const artifacts: NativeArtifact[] = [];
        for (const item of activationOrder(selected.selected)) artifacts.push(await readArtifact(root, item.manifest));
        const request = { operation_id: selected.selected_operation_id, artifacts, baseline_tools: baselineTools };
        validateObservation(receipt.observation, request, 'disposable', true);
        await verifyArtifactHashes(artifacts);
        current = { request, receipt: { ...receipt, artifacts } };
      }
      catch (error) { update({ held: 'plugin_candidate_revalidation_required', failed: { operation_id: selected.selected_operation_id,
        requested: structuredClone(selected.selected), error: errorCode(error) } }); }
    }
    // A prior process's healthy observation is historical evidence. Even an
    // unchanged effective generation must reopen closed and reobserve natively.
    if (effective && !state.failed && !state.held) update({ held: 'plugin_restart_revalidation_required' });
    initialized = true;
  }
  function errorCode(error: unknown): string {
    return error instanceof PluginLifecycleError ? error.code : 'plugin_operation_failed';
  }
  /** Native inspection executes only a private copy of the exact reviewed bytes. */
  async function snapshotCandidate(request: NativeInspectionRequest): Promise<{
    readonly request: NativeInspectionRequest;
    readonly directory: string;
  }> {
    const parent = path.join(directory, 'candidate-bytes');
    const candidateDirectory = path.join(parent, request.operation_id + '-' + randomUUID());
    await mkdir(parent, { recursive: true });
    await mkdir(candidateDirectory);
    const artifacts: NativeArtifact[] = [];
    try {
      for (const artifact of request.artifacts) {
        const bytes = await readFile(artifact.path);
        if (sha256(bytes) !== artifact.manifest.artifact_sha256) reject('plugin_artifact_integrity');
        const artifactDirectory = path.join(candidateDirectory, artifact.manifest.native_id);
        const file = path.join(artifactDirectory, 'server.js');
        await mkdir(artifactDirectory);
        const handle = await open(file, 'wx', 0o600);
        try { await handle.writeFile(bytes); await handle.sync(); }
        finally { await handle.close(); }
        artifacts.push({ manifest: artifact.manifest, path: file });
      }
      const candidate = { operation_id: request.operation_id, artifacts, baseline_tools: request.baseline_tools };
      await verifyArtifactHashes(artifacts);
      return { request: candidate, directory: candidateDirectory };
    } catch (error) {
      await retireCandidate(candidateDirectory).catch(() => {});
      throw error;
    }
  }
  async function retireCandidate(candidateDirectory: string): Promise<void> {
    const parent = path.resolve(directory, 'candidate-bytes');
    const target = path.resolve(candidateDirectory);
    if (path.dirname(target) !== parent) reject('plugin_candidate_cleanup_path');
    await rm(target, { recursive: true, force: true });
  }
  function mapCandidateObservation(observation: Operation['receipt']['observation'],
      candidate: NativeInspectionRequest, reviewed: NativeInspectionRequest): Operation['receipt']['observation'] {
    const originals = new Map(reviewed.artifacts.map(item => [item.manifest.native_id, item]));
    const candidates = new Set(candidate.artifacts.map(item => item.manifest.native_id));
    return { ...observation, plugins: observation.plugins.map(plugin => {
      const original = originals.get(plugin.id);
      return original && candidates.has(plugin.id) && plugin.source_type === 'local'
        ? { ...plugin, source_path: original.path } : plugin;
    }) };
  }
  async function serialize<T>(action: () => Promise<T>, readOnly = false): Promise<T> {
    if (closed && !readOnly) throw new PluginLifecycleError('plugin_lifecycle_closed');
    const previous = writing;
    let release!: () => void;
    writing = new Promise<void>(resolve => { release = resolve; });
    await previous;
    try {
      await initialize();
      if (closed && !readOnly) throw new PluginLifecycleError('plugin_lifecycle_closed');
      return await action();
    }
    finally { release(); }
  }
  async function replace(file: string, value: unknown): Promise<void> {
    await mkdir(directory, { recursive: true });
    const temporary = path.join(directory, '.write-' + randomUUID() + '.tmp');
    const handle = await open(temporary, 'wx', 0o600);
    try { await handle.writeFile(JSON.stringify(value, null, 2) + '\n'); await handle.sync(); }
    finally { await handle.close(); }
    try {
      await rename(temporary, file);
      if (process.platform !== 'win32') {
        const directoryHandle = await open(directory, 'r');
        try { await directoryHandle.sync(); } finally { await directoryHandle.close(); }
      }
    } finally {
      await unlink(temporary).catch(error => { if (error.code !== 'ENOENT') throw error; });
    }
  }
  async function publishSelected(): Promise<void> {
    const next = { ...state, revision: state.revision + 1 };
    await replace(selectionFile, next);
    state = next;
  }
  async function publishActive(): Promise<void> {
    const next = { ...state, revision: state.revision + 1 };
    await replace(activeFile, { ...next, selected_operation_id: effective!.operation_id,
      selected: effective!.selected, receipt: effective!.receipt });
    state = next;
  }
  async function inspect(selection: readonly SelectedPlugin[], operationId: string): Promise<Operation> {
    const artifacts: NativeArtifact[] = [];
    for (const item of activationOrder(selection)) artifacts.push(await readArtifact(root, item.manifest));
    if (!/^[a-z][a-z0-9.-]{0,119}$/.test(operationId)) reject('plugin_operation_id_invalid');
    const request: NativeInspectionRequest = { operation_id: operationId, artifacts, baseline_tools: baselineTools };
    await verifyArtifactHashes(artifacts);
    const candidate = await snapshotCandidate(request);
    let observation;
    try {
      const observed = await options.host.inspectCandidate(candidate.request);
      validateObservation(observed, candidate.request, 'disposable', true);
      await verifyArtifactHashes(candidate.request.artifacts);
      await verifyArtifactHashes(artifacts);
      observation = mapCandidateObservation(observed, candidate.request, request);
      validateObservation(observation, request, 'disposable', true);
    } finally {
      await retireCandidate(candidate.directory).catch(() => {});
    }
    const receipt: InspectionReceipt = { contract: 'renulus-plugin-inspection/1',
      operation_id: operationId, requested: structuredClone(selection), artifacts, baseline_tools: baselineTools,
      observation: structuredClone(observation) };
    const operation = { request, receipt };
    current = operation;
    state = { ...state, selected_operation_id: operationId, selected: structuredClone(selection),
      held: null, failed: null, receipt };
    await publishSelected();
    return operation;
  }
  async function failed(error: unknown, selection?: readonly SelectedPlugin[], operationId?: string): Promise<never> {
    lastError = errorCode(error); update({ held: lastError }); current = undefined;
    if (selection && operationId && /^[a-z][a-z0-9.-]{0,119}$/.test(operationId)) {
      update({ failed: { operation_id: operationId, requested: structuredClone(selection), error: lastError } });
    }
    await publishSelected();
    throw error;
  }
  async function quiesce(request: NativeInspectionRequest): Promise<void> {
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      const settlement = await Promise.race([
        options.host.quiesce({ ...request, timeout_ms: timeout }),
        new Promise<never>((_resolve, fail) => {
          timer = setTimeout(() => fail(new PluginLifecycleError('plugin_quiescence_timeout')), timeout);
        }),
      ]);
      if (settlement.state !== 'settled' || settlement.active_operations !== 0 || settlement.pending_permissions !== 0 ||
          settlement.worker_leases !== 0 || !Array.isArray(settlement.uncertain_effects) || settlement.uncertain_effects.length)
        reject('plugin_quiescence_held');
    } finally { if (timer) clearTimeout(timer); }
  }
  async function activate(): Promise<PluginLifecycleStatus> {
    if (state.held && state.held !== 'plugin_restart_revalidation_required')
      throw new PluginLifecycleError('plugin_lifecycle_held');
    if (!current || !state.selected_operation_id || current.request.operation_id !== state.selected_operation_id)
      throw new PluginLifecycleError('plugin_candidate_required');
    const operation = current;
    try {
      validateReceipt(operation.receipt, state.selected, baselineTools);
      validateObservation(operation.receipt.observation, operation.request, 'disposable', true);
      await verifyArtifactHashes(operation.request.artifacts);
      await quiesce(operation.request);
      // Quiescence can be asynchronous; recheck bytes at the selection boundary.
      await verifyArtifactHashes(operation.request.artifacts);
      const next: EffectiveSelection = { contract: 'renulus-plugin-effective/1',
        operation_id: operation.request.operation_id, selected: structuredClone(state.selected), receipt: operation.receipt };
      await replace(effectiveFile, next);
      effective = next;
      reobserved = false;
      // The complete effective candidate is now selected. A crash stays closed.
      state.held = 'plugin_restart_revalidation_required';
      await publishSelected();
      const observation = await options.host.restart(operation.request);
      validateObservation(observation, operation.request, 'selected-profile', false);
      await verifyArtifactHashes(operation.request.artifacts);
      if (observation.registry_hash !== operation.receipt.observation.registry_hash)
        throw new PluginLifecycleError('plugin_restart_registry_mismatch');
      state = { ...state, active_operation_id: operation.request.operation_id,
        active: structuredClone(state.selected), active_registry_hash: observation.registry_hash,
        held: null, failed: null, receipt: operation.receipt };
      await publishActive();
      await publishSelected();
      reobserved = true;
      lastError = null;
      return status();
    } catch (error) {
      lastError = errorCode(error); update({ held: lastError,
        failed: { operation_id: operation.request.operation_id,
          requested: structuredClone(state.selected), error: lastError } });
      await publishSelected();
      throw error;
    }
  }
  function status(): PluginLifecycleStatus {
    return { state: state.held || closed ? 'held' as const : state.selected_operation_id !== state.active_operation_id ? 'staged' as const
        : reobserved && state.active_operation_id ? 'ready' as const : 'empty' as const,
      error: state.held ?? (closed ? 'plugin_lifecycle_closing' : lastError), requested: structuredClone(state.selected),
      requested_operation_id: state.selected_operation_id, selected_operation_id: effective?.operation_id ?? null,
      selected: structuredClone(effective?.selected ?? []), active_operation_id: state.active_operation_id,
      active: structuredClone(state.active), registry_hash: state.active_registry_hash, reobserved: reobserved && !closed,
      failed_operation_id: state.failed?.operation_id ?? null,
      failed_requested: structuredClone(state.failed?.requested ?? null), failed_error: state.failed?.error ?? null };
  }
  async function stageSelection(selection: readonly SelectedPlugin[]): Promise<PluginLifecycleStatus> {
    checkSelection(selection);
    for (const item of selection) {
      const previous = state.selected.find(old => old.manifest.plugin_id === item.manifest.plugin_id);
      if (previous && ((previous.manifest.version === item.manifest.version) !==
          (previous.manifest.artifact_sha256 === item.manifest.artifact_sha256))) reject('plugin_edit_requires_new_version_and_bytes');
    }
    const operationId = newOperation();
    try {
      if (!/^[a-z][a-z0-9.-]{0,119}$/.test(operationId)) reject('plugin_operation_id_invalid');
      if (operationId === state.selected_operation_id || operationId === effective?.operation_id || operationId === state.failed?.operation_id)
        reject('plugin_operation_id_reused');
      const enabled = new Set(selection.filter(item => item.enabled).map(item => item.manifest.native_id));
      const disabled = [...new Set([...state.active, ...state.selected].filter(item => item.enabled &&
        !enabled.has(item.manifest.native_id)).map(item => item.manifest.native_id))];
      if (disabled.length) await options.host.narrow({ operation_id: operationId, disabled_native_ids: disabled });
      await inspect(selection, operationId); lastError = null; return status();
    }
    catch (error) { return failed(error, selection, operationId); }
  }
  return {
    stage: async (selection: readonly SelectedPlugin[]) => {
      const snapshot = structuredClone(selection);
      return serialize(() => stageSelection(snapshot));
    },
    add: async (value: SelectedPlugin['manifest']) => {
      const manifest = structuredClone(value);
      return serialize(async () => {
      if (state.selected.some(item => item.manifest.plugin_id === manifest.plugin_id)) reject('plugin_id_duplicate');
      return stageSelection([...state.selected, { manifest, enabled: true }]);
      });
    },
    edit: async (value: SelectedPlugin['manifest']) => {
      const manifest = structuredClone(value);
      return serialize(async () => {
      const previous = state.selected.find(item => item.manifest.plugin_id === manifest.plugin_id);
      if (!previous) reject('plugin_missing');
      if (previous.manifest.version === manifest.version || previous.manifest.artifact_sha256 === manifest.artifact_sha256)
        reject('plugin_edit_requires_new_version_and_bytes');
      return stageSelection(state.selected.map(item => item.manifest.plugin_id === manifest.plugin_id ? { manifest, enabled: item.enabled } : item));
      });
    },
    disable: async (pluginId: string) => serialize(async () => {
      if (!state.selected.some(item => item.manifest.plugin_id === pluginId)) reject('plugin_missing');
      return stageSelection(state.selected.map(item => item.manifest.plugin_id === pluginId ? { ...item, enabled: false } : item));
    }),
    remove: async (pluginId: string) => serialize(async () => {
      if (!state.selected.some(item => item.manifest.plugin_id === pluginId)) reject('plugin_missing');
      return stageSelection(state.selected.filter(item => item.manifest.plugin_id !== pluginId));
    }),
    activate: () => serialize(activate),
    status: async () => serialize(async () => status(), true),
    /** Reobserve the effective generation, never activate a merely staged edit. */
    recover: async () => serialize(async () => {
      // A returned failure is not a crash marker. Require a fresh isolated
      // inspection before trying that candidate again.
      if (state.failed) throw new PluginLifecycleError('plugin_lifecycle_held');
      if (!effective) {
        if (state.held) throw new PluginLifecycleError('plugin_lifecycle_held');
        return status();
      }
      if (reobserved && state.held === null) return status();
      if (state.held !== 'plugin_restart_revalidation_required') throw new PluginLifecycleError('plugin_lifecycle_held');
      try {
        const artifacts: NativeArtifact[] = [];
        for (const item of activationOrder(effective.selected)) artifacts.push(await readArtifact(root, item.manifest));
        const request = { operation_id: effective.operation_id, artifacts, baseline_tools: baselineTools };
        validateReceipt(effective.receipt, effective.selected, baselineTools);
        validateObservation(effective.receipt.observation, request, 'disposable', true);
        await verifyArtifactHashes(artifacts);
        await quiesce(request);
        await verifyArtifactHashes(artifacts);
        const observation = await options.host.restart(request);
        validateObservation(observation, request, 'selected-profile', false);
        await verifyArtifactHashes(artifacts);
        if (observation.registry_hash !== effective.receipt.observation.registry_hash)
          throw new PluginLifecycleError('plugin_restart_registry_mismatch');
        update({ active_operation_id: effective.operation_id, active: structuredClone(effective.selected),
          active_registry_hash: observation.registry_hash, held: null, failed: null });
        lastError = null;
        await publishActive();
        await publishSelected();
        reobserved = true;
        return status();
      } catch (error) {
        lastError = errorCode(error); update({ held: lastError,
          failed: { operation_id: effective.operation_id,
            requested: structuredClone(effective.selected), error: lastError } });
        await publishSelected(); throw error;
      }
    }),
    async close(): Promise<void> { closed = true; await writing; current = undefined; },
  };
}
