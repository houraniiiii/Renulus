// SPDX-License-Identifier: MIT
import { Effect } from 'effect';
import type { Context, Plugin } from '@opencode/plugin/effect/plugin';
import { Tool } from '@opencode/schema/tool';
import { exact, reject } from '../../storage/contracts.ts';
import type { AssessmentToolBridgeOptions } from '../assessment/tools.ts';
import type { StudyStorage } from './contracts.ts';
import { systemLocalClock } from './coordinator.ts';

export function createStudyTools(options: Pick<AssessmentToolBridgeOptions, 'resolve' | 'check'> & { storage: StudyStorage }) {
  return {
    async execute(name: 'renulus_plan_propose', args: unknown, context: { sessionID: string; id: string }, signal: AbortSignal) {
      signal.throwIfAborted(); const a = await options.resolve(context, signal);
      if (a.sessionId !== context.sessionID || !a.operationId || !a.attemptId) reject('study_tool_authority_invalid');
      if (!a.grants.includes('renulus.plan.propose')) reject('study_tool_grant_denied');
      await options.check(a, signal); exact(args, []);
      const proposal = await options.storage.command({ type: 'study.plan.preview', clock: systemLocalClock() });
      await options.check(a, signal); signal.throwIfAborted();
      return { ...proposal, requires_explicit_save: true };
    },
  };
}
export function registerStudyTools(context: Pick<Context, 'tool'>, bridge: ReturnType<typeof createStudyTools>) {
  return context.tool.transform(editor => {
    editor.add({ name: 'renulus_plan_propose', description: 'Preview a dated study plan for explicit user save. Never saves or changes the plan.',
      input: { type: 'object', additionalProperties: false, properties: {} } as never,
      options: { codemode: false, permission: 'renulus.plan.propose' },
      execute: (args, ctx) => Effect.suspend(() => {
        let pending: Promise<Tool.Result> | undefined;
        return Effect.tryPromise({ try: signal => { pending = bridge.execute('renulus_plan_propose', args, ctx, signal).then(value => ({ content: JSON.stringify(value) })); return pending; },
          catch: () => new Tool.Error({ message: 'The study plan preview is unavailable.', metadata: { code: 'study_tool_failed' } }) })
          .pipe(Effect.onInterrupt(() => Effect.promise(async () => { await pending?.catch(() => {}); })));
      }) });
  }).pipe(Effect.asVoid);
}
export function createStudyPlugin(bridge: ReturnType<typeof createStudyTools>): Plugin {
  return { id: 'renulus-study', effect: context => registerStudyTools(context, bridge) };
}
