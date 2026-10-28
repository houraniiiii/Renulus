// SPDX-License-Identifier: MIT
import { Effect } from 'effect';
import type { Plugin } from '@opencode/plugin/effect/plugin';
import { Tool } from '@opencode/schema/tool';
import { reject, text } from '../../storage/contracts.ts';
import { digest } from '../../storage/schema.ts';
import { nativeText, type NativeMessage } from './history.ts';
import type { Checkpoint, ReadView } from './contracts.ts';

export const CONTEXT_PERMISSION = 'renulus.context.read', HISTORY_PERMISSION = 'renulus.history.read';
const MAX_MESSAGES = 40, MAX_BYTES = 64 * 1024;
export interface LearningToolAuthority { readonly operationId: string; readonly attemptId: string; readonly sessionId: string;
  readonly threadId: string; readonly checkpoint: Checkpoint; readonly grants: readonly string[] }
export interface LearningToolBridgeOptions {
  references(threadId: string): Promise<ReadView['references']>;
  range(threadId: string, input: { limit: number; cursor?: string }): Promise<{ messages: readonly NativeMessage[]; cursor: string | null }>;
  /** Host-minted identity, pins and grants; native arguments never become authority. */
  resolve(context: { sessionID: string; id: string }, signal: AbortSignal): Promise<LearningToolAuthority>;
  check(authority: LearningToolAuthority, signal: AbortSignal): Promise<void>;
}
/** Read-only tools over the exact history pinned to this run; no paths, no other runs. */
export function createLearningTools(options: LearningToolBridgeOptions) {
  async function run<T>(permission: string, args: unknown, keys: string[], context: { sessionID: string; id: string }, signal: AbortSignal,
    work: (authority: LearningToolAuthority, eligible: ReadView['references'], input: Record<string, unknown>) => Promise<T>) {
    signal.throwIfAborted(); const a = await options.resolve(context, signal);
    if (a.sessionId !== context.sessionID || !a.operationId || !a.attemptId) reject('learning_tool_authority_invalid');
    if (!a.grants.includes(permission)) reject('learning_tool_grant_denied');
    const input = args as Record<string, unknown>;
    if (!input || typeof input !== 'object' || Array.isArray(input) || Object.keys(input).some(k => !keys.includes(k))) reject('learning_tool_arguments_invalid');
    await options.check(a, signal);
    const pinned = new Set(a.checkpoint.history.map(h => h.runId));
    const value = await work(a, (await options.references(a.threadId)).filter(r => pinned.has(r.reference.run_id)), input);
    await options.check(a, signal); signal.throwIfAborted(); return value;
  }
  return {
    contextRefs: (args: unknown, context: { sessionID: string; id: string }, signal: AbortSignal) =>
      run(CONTEXT_PERMISSION, args, [], context, signal, async (a, eligible) => ({
        references: eligible.map(({ reference: r }) => ({ run_id: r.run_id, input_id: r.input_id, message_ids: r.message_ids, sha256: r.sha256,
          citations: r.citations.map(c => ({ document_id: c.document_id, revision_id: c.revision_id, passage_id: c.passage_id })) })),
        consumed: a.checkpoint.consumed, memory: a.checkpoint.memory, history: a.checkpoint.history })),
    historyRange: (args: unknown, context: { sessionID: string; id: string }, signal: AbortSignal) =>
      run(HISTORY_PERMISSION, args, ['first_message_id', 'last_message_id'], context, signal, async (a, eligible, input) => {
        text(input.first_message_id, 1, 200); text(input.last_message_id, 1, 200);
        const allowed = new Set(eligible.flatMap(({ reference: r }) => [r.input_id, ...r.message_ids]));
        if (!allowed.has(input.first_message_id as string) || !allowed.has(input.last_message_id as string)) reject('history_range_denied');
        const found: NativeMessage[] = []; let cursor: string | undefined, seenFirst = false, done = false;
        for (let page = 0; page < 24 && !done; page++) {
          const result = await options.range(a.threadId, { limit: 200, ...(cursor ? { cursor } : {}) });
          for (const m of result.messages) {
            if (!allowed.has(m.id)) continue;
            seenFirst ||= m.id === input.first_message_id;
            if (seenFirst) found.push(m);
            if (seenFirst && m.id === input.last_message_id) { done = true; break; }
          }
          if (!result.cursor) break; cursor = result.cursor;
        }
        if (!done) reject('history_range_denied');
        const messages = found.map(m => ({ id: m.id, role: m.type, text: nativeText(m), sha256: digest(nativeText(m)) }));
        if (messages.length > MAX_MESSAGES || Buffer.byteLength(JSON.stringify(messages)) > MAX_BYTES) reject('history_range_limit');
        return { messages };
      }),
  };
}
function toolPlugin(id: string, name: string, description: string, permission: string, input: object,
  execute: (args: unknown, context: { sessionID: string; id: string }, signal: AbortSignal) => Promise<unknown>): Plugin {
  return { id, effect: context => context.tool.transform(editor => {
    editor.add({ name, description, input: input as never, options: { codemode: false, permission },
      execute: (args, ctx) => Effect.suspend(() => {
        let pending: Promise<Tool.Result> | undefined;
        return Effect.tryPromise({ try: signal => { pending = execute(args, ctx, signal).then(value => ({ content: JSON.stringify(value) })); return pending; },
          catch: () => new Tool.Error({ message: 'This learning context is unavailable for the current run.', metadata: { code: 'learning_tool_failed' } }) })
          .pipe(Effect.onInterrupt(() => Effect.promise(async () => { await pending?.catch(() => {}); })));
      }) });
  }).pipe(Effect.asVoid) };
}
export function createLearningPlugins(bridge: ReturnType<typeof createLearningTools>) {
  return {
    context: toolPlugin('renulus-context', 'renulus_context_refs', 'List the exact earlier answers, citations and pins available to this learning run.',
      CONTEXT_PERMISSION, { type: 'object', additionalProperties: false, properties: {} }, bridge.contextRefs),
    history: toolPlugin('renulus-history', 'renulus_history_range', 'Read the exact text of earlier chat messages between two message ids returned by renulus_context_refs.',
      HISTORY_PERMISSION, { type: 'object', additionalProperties: false, required: ['first_message_id', 'last_message_id'],
        properties: { first_message_id: { type: 'string', minLength: 1, maxLength: 200 }, last_message_id: { type: 'string', minLength: 1, maxLength: 200 } } }, bridge.historyRange),
  };
}
