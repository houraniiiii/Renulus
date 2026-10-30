// SPDX-License-Identifier: MIT
import { Effect } from 'effect';
import type { Context, Plugin } from '@opencode/plugin/effect/plugin';
import { Tool } from '@opencode/schema/tool';
import { exact, reject } from '../../storage/contracts.ts';
import type { AssessmentToolBridgeOptions } from '../assessment/tools.ts';
import type { UpdatesStorage } from './contracts.ts';

export function createUpdatesTools(options: Pick<AssessmentToolBridgeOptions, 'resolve' | 'check'> & { storage: UpdatesStorage }) {
  return {
    async execute(name: 'renulus_updates_read', args: unknown, context: { sessionID: string; id: string }, signal: AbortSignal) {
      signal.throwIfAborted(); const a = await options.resolve(context, signal);
      if (a.sessionId !== context.sessionID || !a.operationId || !a.attemptId) reject('updates_tool_authority_invalid');
      if (!a.grants.includes('renulus.updates.read')) reject('updates_tool_grant_denied');
      await options.check(a, signal); exact(args, []);
      const result = await options.storage.command({ type: 'updates.entries', state: null, limit: 20, offset: 0 });
      await options.check(a, signal); signal.throwIfAborted();
      return { entries: result.entries.map(({ id, title, url, review_state, summary, reviewed_at, source_id }: Record<string, unknown>) =>
        ({ id, title, url, review_state, summary, reviewed_at, source_id })) };
    },
  };
}
export function registerUpdatesTools(context: Pick<Context, 'tool'>, bridge: ReturnType<typeof createUpdatesTools>) {
  return context.tool.transform(editor => {
    editor.add({ name: 'renulus_updates_read', description: 'Read dated update summaries and review states. Never marks sources reviewed or current.',
      input: { type: 'object', additionalProperties: false, properties: {} } as never,
      options: { codemode: false, permission: 'renulus.updates.read' },
      execute: (args, ctx) => Effect.suspend(() => {
        let pending: Promise<Tool.Result> | undefined;
        return Effect.tryPromise({ try: signal => { pending = bridge.execute('renulus_updates_read', args, ctx, signal).then(value => ({ content: JSON.stringify(value) })); return pending; },
          catch: () => new Tool.Error({ message: 'The dated updates are unavailable.', metadata: { code: 'updates_tool_failed' } }) })
          .pipe(Effect.onInterrupt(() => Effect.promise(async () => { await pending?.catch(() => {}); })));
      }) });
  }).pipe(Effect.asVoid);
}
export function createUpdatesPlugin(bridge: ReturnType<typeof createUpdatesTools>): Plugin {
  return { id: 'renulus-updates', effect: context => registerUpdatesTools(context, bridge) };
}
