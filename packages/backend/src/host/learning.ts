// SPDX-License-Identifier: MIT
/** Bounded BF02 isolated target assembly. Python remains production canonical until BF08.
 * The native host owns execution/messages/tools. This module owns no agent loop or DB. */
import { randomUUID } from 'node:crypto';
import { readAttachmentImage, drainAttachmentCleanup } from './learning-attachments.ts';
import { Effect } from 'effect';
import { AIError, InvalidRequestError, LLMRequest } from '@opencode/ai';
import { compactContext, type ContextCompaction } from '../domain/learning/context.ts';
import { openLearningHarness } from '../../../harness/src/learning-host.ts';
import type { HarnessOptions, ModelAdapter, PrimaryModelPreparation } from '../../../harness/src/host.ts';
import type { DomainClient } from '../../../harness/src/domain-ipc.ts';
import { createNativeDomainAdapter, type NativeDomainReply, type NativeDomainRequest } from './domain-adapter.ts';
import { createLearningCallbacks, type LibraryQueryBridge } from '../domain/learning/callbacks.ts';
import { createLearningHistory, nativeText, type NativeMessage, type NativePage } from '../domain/learning/history.ts';
import { canonical, digest } from '../storage/schema.ts';
import { learningSendIntent } from '../storage/learning.ts';
import { importLegacyHistory } from '../domain/learning/legacy-import.ts';
import { reject } from '../storage/contracts.ts';
import type { AnswerReference, BeginInput, Binding, LearningCommand, LearningMessage, LearningReceipt, LearningResults,
  LearningStorage, RunSnapshot, RuntimeIdentity, SavedSendIntent } from '../domain/learning/contracts.ts';

export interface SavedModelContext { run: RunSnapshot; request: Readonly<SavedSendIntent> }

export interface SavedLearningOptions {
  storage: LearningStorage;
  harness: Omit<HarnessOptions, 'model' | 'library' | 'admitInput' | 'selectContext'> & { processGeneration: string };
  /** App-owned exact subscription route. Tests alone inject native TestLLM here.
   * No default model/transport, account access, fallback or provider selection. */
  model: (domain: DomainClient) => Promise<ModelAdapter>;
  library: LibraryQueryBridge;
  /** Fresh canonical admission; BF01 pins the exact selected route before native work. */
  onBegin?: (run: RunSnapshot, request: Readonly<SavedSendIntent>) => void | Promise<void>;
  modelCallbacks?: (request: NativeDomainRequest, authority: SavedModelContext) => Promise<NativeDomainReply>;
  /** Evidence-review children own their callbacks; `root` serves a command against the parent's authority. */
  /** Final-request compaction against the verified route window; absent means no transform. */
  context?: ContextCompaction | ((authority: SavedModelContext, signal: AbortSignal) => Promise<ContextCompaction | undefined>);
  children?: { owns(binding: Readonly<Binding>): boolean;
    handle(request: NativeDomainRequest, root: (request: NativeDomainRequest) => Promise<NativeDomainReply>): Promise<NativeDomainReply> };
}
export type SavedSend = Omit<BeginInput, 'identity' | 'runId' | 'attemptId'>;
export async function openSavedLearningTarget(options: SavedLearningOptions) {
  const { storage } = options;
  const identity: RuntimeIdentity = Object.freeze({ profileId: options.harness.profileId, storeId: options.harness.storeId, generation: options.harness.processGeneration });
  const intents = new Map<string, Readonly<SavedSendIntent>>();
  async function modelContext(binding: Binding): Promise<SavedModelContext> {
    const run = await storage.command({ type: 'learning.current', runId: binding.operation_id, binding });
    const request = intents.get(binding.operation_id);
    if (!request) reject('learning_intent_unavailable');
    const { text, ...metadata } = request;
    if (digest(text) !== run.checkpoint.inputSha256 || canonical(metadata) !== canonical(run.checkpoint.intent)) reject('learning_intent_conflict');
    return { run, request };
  }
  const callbacks = createLearningCallbacks({ storage, identity, library: options.library,
    modelCallbacks: options.modelCallbacks ? async request => options.modelCallbacks!(request, await modelContext(request.binding)) : undefined });
  const domain = createNativeDomainAdapter({ identity: { profile_id: identity.profileId, store_id: identity.storeId, generation: identity.generation },
    handle: request => options.children?.owns(request.binding) ? options.children.handle(request, callbacks.handle) : callbacks.handle(request) });
  let native: Awaited<ReturnType<typeof openLearningHarness>>;
  try {
    const model = await options.model(domain.domain);
    // Reuse the native final-primary seam. Style is trusted intent, never user text
    // smuggled into learner-memory context, and is included before BF01 prepares its digest.
    const styled: ModelAdapter = { ...model, preparePrimary: (binding, resolved) => Effect.gen(function* () {
      const authority = yield* Effect.promise(() => modelContext(binding));
      const base = model.preparePrimary ? yield* model.preparePrimary(binding, resolved) : undefined;
      const style = { type: 'text' as const, text: authority.request.teaching_style === 'guided'
        ? 'Teaching style: guided. Use focused questions and stepwise reasoning to help the learner build understanding.'
        : 'Teaching style: direct. Explain the answer clearly and directly, then add useful reasoning.' };
      return { resolved: base?.resolved ?? resolved, prepare: (request, settings, unfiltered) => {
        const withStyle = (r: LLMRequest) => LLMRequest.update(r, { system: [...r.system, style] });
        const shape = (r: LLMRequest, run: RunSnapshot) => options.context
          ? Effect.tryPromise({ try: async signal => {
              const context = typeof options.context === 'function' ? await options.context({ run, request: authority.request }, signal) : options.context;
              return context ? compactContext(withStyle(r), context, run.checkpoint) : withStyle(r);
            }, catch: error => new AIError({ reason: new InvalidRequestError({ message: String((error as { code?: string }).code ?? 'context_compaction_blocked') }) }) })
          : Effect.succeed(withStyle(r));
        return Effect.promise(() => modelContext(binding)).pipe(Effect.flatMap(({ run }) => shape(request, run)),
          Effect.flatMap(shaped => base ? base.prepare(shaped, settings, options.context ? shaped : withStyle(unfiltered)) : Effect.succeed(shaped)));
      } } satisfies PrimaryModelPreparation;
    }) };
    native = await openLearningHarness({ ...options.harness, model: styled }, domain.domain);
  }
  catch (error) { await domain.close(); throw error; }
  const active = new Map<string, { threadId: string; pending: Promise<unknown> }>();
  let closing = false;
  const legacyImports = new Map<string, Promise<void>>();
  async function ensureLegacy(threadId: string, expectedRevision?: number) {
    if (closing) reject('learning_closed');
    const pending = legacyImports.get(threadId);
    if (pending) return pending;
    // A missing conversation has nothing to import; the caller's own command reports it (or its terminal replay).
    const view = await storage.command({ type: 'learning.view', threadId }).catch(error => {
      if ((error as { code?: string }).code === 'conversation_missing') return undefined;
      throw error;
    });
    if (closing) reject('learning_closed');
    if (legacyImports.has(threadId)) return legacyImports.get(threadId);
    if (!view || view.mapping) return;
    const task = importLegacyHistory(storage, native, identity, threadId, expectedRevision ?? view.conversation.revision);
    legacyImports.set(threadId, task);
    try { await task; } finally { legacyImports.delete(threadId); }
  }
  const history = createLearningHistory(storage, native as unknown as { observe: (sessionId: string, input: { limit: number; order?: 'asc'; cursor?: string }) => Promise<NativePage> });
  async function purge() {
    const queued = await storage.command({ type: 'learning.purge.list', identity });
    for (const p of queued) {
      // OpenCode transfer gates settlement and checks the selected profile/store/process.
      await native.transferCommand({ profileId: identity.profileId, storeId: identity.storeId, generation: identity.generation,
        operationId: p.operation_id, attemptId: p.attempt_id }, 'session.remove', { sessionId: p.session_id });
      await storage.command({ type: 'learning.purge.ack', purgeId: p.purge_id, identity });
    }
    await drainAttachmentCleanup(options.harness.root, storage);
    return { removed: queued.length };
  }
  async function stop(runId: string, state: 'cancelled' | 'failed' | 'interrupted' = 'cancelled') {
    const stopped = await storage.command({ type: 'learning.stop', runId, state });
    if (stopped.sessionId) await native.cancel(stopped.sessionId);
    return stopped;
  }
  async function execute(input: SavedSend, runId: string, initial: LearningResults['learning.begin'], signal?: AbortSignal, images?: SavedSendIntent['images']) {
    let sessionId = initial.run.mapping?.runtime.session_id;
    let created = false, mapped = !!sessionId;
    let cancellation: Promise<unknown> | undefined;
    const cancel = () => { cancellation ??= stop(runId); void cancellation.catch(() => {}); };
    signal?.addEventListener('abort', cancel, { once: true });
    if (signal?.aborted) cancel();
    try {
      await storage.command({ type: 'learning.current', runId, binding: null });
      await options.onBegin?.(structuredClone(initial.run), Object.freeze({ ...intents.get(runId)!, ...(images?.length ? { images } : {}) }));
      await storage.command({ type: 'learning.current', runId, binding: null });
      if (!sessionId) {
        const session = await native.createSession({ operationId: runId, title: initial.run.receipt.conversation.title });
        sessionId = session.id; created = true;
        await storage.command({ type: 'learning.map', runId, sessionId }); mapped = true;
      }
      if (signal?.aborted || closing) reject('learning_cancelled');
      const accepted = await native.submit({ sessionId, operationId: runId, attemptId: initial.run.checkpoint.attemptId, text: input.text, images });
      const binding: Binding = { operation_id: runId, attempt_id: accepted.attemptId, session_id: sessionId, input_id: accepted.inputId, cancellation_id: runId };
      await native.wait(sessionId);
      const messages: NativeMessage[] = [], cursors = new Set<string>();
      let cursor: string | undefined;
      // Observation pagination, never model scheduling. Overflow remains an unreconciled receipt.
      for (let page = 0; page < 24; page++) {
        const observed = await native.observe(sessionId, { limit: 200, ...(cursor ? { cursor } : { order: 'asc' as const }) });
        if (observed.session.id !== sessionId || observed.session.metadata?.renulusProfile !== identity.profileId || observed.session.metadata?.renulusStore !== identity.storeId ||
          observed.execution !== 'settled' || observed.session.outcome !== 'succeeded') reject('learning_native_incomplete');
        messages.push(...observed.messages as unknown as NativeMessage[]);
        if (Buffer.byteLength(JSON.stringify(messages)) > 8 * 1024 * 1024) reject('learning_native_range_limit');
        cursor = observed.cursor.next;
        if (!cursor) break;
        if (cursors.has(cursor) || page === 23) reject('learning_native_range_limit'); cursors.add(cursor);
      }
      const boundary = messages.findIndex(m => m.id === binding.input_id), user = messages[boundary];
      if (boundary < 0 || user.type !== 'user' || user.metadata?.operationId !== runId || user.metadata?.attemptId !== binding.attempt_id ||
        digest(nativeText(user)) !== digest(input.text)) reject('learning_native_input_conflict');
      const suffix = messages.slice(boundary + 1);
      if (suffix.some(m => m.type === 'user')) reject('learning_native_input_conflict');
      const answer = suffix.filter(m => m.type === 'assistant'), answerText = answer.map(nativeText).join('');
      if (!answer.length || answer.length > 100 || !answerText || !answer.at(-1)?.time?.completed || answer.some(m => m.error)) reject('learning_native_incomplete');
      const run = await storage.command({ type: 'learning.current', runId, binding });
      if (signal?.aborted || closing) reject('learning_cancelled');
      const ref: AnswerReference = { version: 1, run_id: runId, thread_id: input.threadId, runtime: run.mapping!.runtime,
        input_id: binding.input_id, message_ids: answer.map(m => m.id), sha256: digest(answerText),
        citations: run.checkpoint.consumed.map(c => ({ document_id: c.document_id, revision_id: c.document_revision, passage_id: c.passage_id, locators: c.locators })),
        ...run.ancestry! };
      return await storage.command({ type: 'learning.publish', binding, reference: ref });
    } catch (error) {
      await stop(runId, signal?.aborted || cancellation ? 'cancelled' : 'interrupted');
      if (created && !mapped && sessionId) {
        await storage.command({ type: 'learning.purge.enqueue', identity, sessionId, operationId: runId, attemptId: initial.run.checkpoint.attemptId });
        await purge();
      }
      throw error;
    } finally { signal?.removeEventListener('abort', cancel); await cancellation; }
  }
  return {
    /** Trusted embedding surface for BF01 activation/registry observation, not a renderer API. */
    native,
    ...history,
    /** Public UI projection; the raw owning-host range remains available for tools/tests. */
    async messages(threadId: string, input: { limit?: number; cursor?: string } = {}) {
      await ensureLegacy(threadId);
      const view = await storage.command({ type: 'learning.view', threadId });
      const page = await history.range(threadId, input);
      const owners = new Map<string, { runId: string; role: 'user' | 'assistant' }>();
      for (const ref of view.legacyReferences ?? []) owners.set(ref.id, { runId: ref.runId, role: ref.role });
      for (const { reference } of view.references) {
        for (const id of [reference.input_id, ...reference.message_ids]) {
          if (owners.has(id)) reject('learning_native_reference_conflict');
          owners.set(id, { runId: reference.run_id, role: id === reference.input_id ? 'user' : 'assistant' });
        }
      }
      const messages: LearningMessage[] = page.messages.map(message => {
        const owner = owners.get(message.id);
        if (!owner || message.type !== owner.role) reject('learning_native_reference_conflict');
        const created = (message.time as { created?: unknown } | undefined)?.created;
        if (typeof created !== 'number' || !Number.isFinite(created) || !Number.isFinite(new Date(created).getTime())) reject('learning_native_timestamp_invalid');
        return { id: message.id, run_id: owner.runId, role: owner.role, content: nativeText(message),
          created_at: new Date(created).toISOString(), content_refs: [] };
      });
      await storage.command({ type: 'learning.read.check', threadId, stamp: view.stamp });
      return { conversation: page.conversation.identity, items: messages, next_cursor: page.cursor };
    },
    async send(input: SavedSend, call: { signal?: AbortSignal; accepted?: (receipt: LearningReceipt) => void } = {}) {
      if (closing) reject('learning_closed');
      // Detach all trusted intent from caller mutation before admission or callbacks.
      input = structuredClone(input);
      const intent = learningSendIntent(input);
      if ((intent.model !== null || intent.freshness === true) && !options.onBegin) reject('learning_model_intent_unavailable');
      input.intent = intent;
      await ensureLegacy(input.threadId, input.expectedRevision);
      const runId = 'run_' + randomUUID().replaceAll('-', '');
      const admitted = await storage.command({ type: 'learning.begin', ...input, runId, attemptId: '1', identity });
      const { images: inlineImages, ...pinned } = intent;
      if (admitted.fresh) intents.set(runId, Object.freeze(pinned));
      const pending = admitted.fresh ? Promise.resolve().then(async () => {
        try {
          const attachments = await storage.command({ type: 'learning.attachments', runId });
          const images = [...inlineImages ?? []];
          for (const attachment of attachments) {
            if (attachment.mediaType === 'application/pdf') input.text += '\n\n' + attachment.text;
            else images.push(await readAttachmentImage(options.harness.root, attachment));
          }
          await storage.command({ type: 'learning.current', runId, binding: null });
          return await execute(input, runId, admitted, call.signal, images);
        } catch (error) { await stop(runId, 'interrupted'); throw error; }
      }) : undefined;
      if (pending) active.set(runId, { threadId: input.threadId, pending });
      // Observation is not job ownership. A detached/throwing observer cannot cancel it.
      try { void Promise.resolve(call.accepted?.(structuredClone(admitted.run.receipt))).catch(() => {}); } catch { /* observer detached */ }
      if (!admitted.fresh) return { ...admitted.run.receipt, replayed: true };
      try { return { ...await pending!, replayed: false }; } finally { active.delete(runId); intents.delete(runId); }
    },
    cancel: stop,
    async change(command: Extract<LearningCommand, { type: 'learning.lifecycle' | 'learning.project' }>) { return storage.command(command); },
    async delete(command: Extract<LearningCommand, { type: 'learning.delete' }>) {
      // The canonical fence/purge intent precedes physical native work. A late creator also journals cleanup.
      const view = await storage.command({ type: 'learning.view', threadId: command.threadId });
      const result = await storage.command(command);
      if (view.mapping) await native.cancel(view.mapping.runtime.session_id);
      await Promise.allSettled([legacyImports.get(command.threadId)]);
      await Promise.allSettled([...active.values()].filter(a => a.threadId === command.threadId).map(a => a.pending));
      await purge(); return result;
    },
    reconcilePurges: purge,
    status() { return { closing, active: active.size, domain: domain.domain.state() }; },
    async close() {
      closing = true;
      await Promise.allSettled([...legacyImports.values()]);
      await Promise.all([...active.keys()].map(id => stop(id, 'interrupted')));
      await Promise.allSettled([...active.values()].map(a => a.pending));
      callbacks.seal();
      const result = await native.close();
      if (result.state !== 'closed') reject('learning_native_settlement_pending');
      await domain.close();
    },
  };
}
