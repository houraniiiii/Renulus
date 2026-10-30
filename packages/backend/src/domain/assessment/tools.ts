// SPDX-License-Identifier: MIT
import { Effect } from 'effect';
import type { Context, Plugin } from '@opencode/plugin/effect/plugin';
import { Tool } from '@opencode/schema/tool';
import { exact, integer, reject, text } from '../../storage/contracts.ts';
import { id } from './validation.ts';
import type { AssessmentStorage, HelpContext } from './contracts.ts';

export const ASSESSMENT_TOOLS = ['renulus_study_help', 'renulus_practice_propose'] as const;
export const ASSESSMENT_PERMISSIONS = { renulus_study_help: 'renulus.study.help', renulus_practice_propose: 'renulus.practice.propose' } as const;
export interface AssessmentToolAuthority {
  readonly operationId: string; readonly attemptId: string; readonly sessionId: string;
  /** The Study attempt this conversation is attached to; never taken from tool arguments. */
  readonly studyAttemptId: string | null; readonly grants: readonly string[];
}
export interface AssessmentToolBridgeOptions {
  storage: AssessmentStorage;
  /** Resolve/check host-minted identity, grants, Stop/deletion/configuration. Tool arguments never become authority. */
  resolve(context: { sessionID: string; id: string }, signal: AbortSignal): Promise<AssessmentToolAuthority>;
  check(authority: AssessmentToolAuthority, signal: AbortSignal): Promise<void>;
}
/** Study help records exposure on the attempt before returning anything. Practice is a proposal
 * only: no scoring, key, review, saving or publication authority exists on either tool. */
export function createAssessmentTools(options: AssessmentToolBridgeOptions) {
  return {
    async execute(name: typeof ASSESSMENT_TOOLS[number], args: unknown, context: { sessionID: string; id: string }, signal: AbortSignal) {
      signal.throwIfAborted(); const a = await options.resolve(context, signal);
      if (a.sessionId !== context.sessionID || !a.operationId || !a.attemptId) reject('assessment_tool_authority_invalid');
      if (!a.grants.includes(ASSESSMENT_PERMISSIONS[name])) reject('assessment_tool_grant_denied');
      await options.check(a, signal);
      if (name === 'renulus_practice_propose') {
        exact(args, ['title', 'focus', 'count', ...(args && typeof args === 'object' && 'topic_id' in args ? ['topic_id'] : [])]);
        const p = args as { title: string; focus: string; count: number; topic_id?: string };
        text(p.title, 1, 120); text(p.focus, 1, 2000); if (![5, 10, 20].includes(p.count)) reject('assessment_tool_arguments_invalid'); if (p.topic_id !== undefined) id(p.topic_id);
        return { status: 'proposal', title: p.title, focus: p.focus, count: p.count, topic_id: p.topic_id ?? null, requires_explicit_save: true };
      }
      exact(args, ['kind']); const kind = (args as { kind: HelpContext['kind'] }).kind;
      if (!['hint', 'sources', 'notes', 'chat'].includes(kind) || !a.studyAttemptId) reject('assessment_tool_arguments_invalid');
      const attempt = await options.storage.command({ type: 'assessment.attempts.get', attemptId: a.studyAttemptId! });
      if (attempt.mode !== 'study' || attempt.status !== 'active' || !attempt.current_item) reject('study_help_unavailable');
      // Exposure commits here, before any assistance content leaves the canonical store.
      const help = await options.storage.command({ type: 'assessment.attempts.help', attemptId: a.studyAttemptId!, expectedRevision: attempt.draft_revision,
        expectedPolicyRevision: attempt.policy.revision, itemId: attempt.current_item.item_id, kind, idempotencyKey: 'study-help:' + a.operationId + ':' + context.id });
      await options.check(a, signal); signal.throwIfAborted();
      await options.storage.command({ type: 'assessment.help.current', context: help.context });
      return { kind, item: attempt.current_item, hint: help.hint, references: help.references, context: help.context };
    },
  };
}
export function registerAssessmentTools(context: Pick<Context, 'tool'>, bridge: ReturnType<typeof createAssessmentTools>) {
  return context.tool.transform(editor => {
    for (const name of ASSESSMENT_TOOLS) {
      editor.add({ name, description: name === 'renulus_study_help'
        ? 'Record and return help for the current Study question. Unavailable in a timed Test. It never scores, reveals the key or marks help as unneeded.'
        : 'Propose a generated practice set for explicit user save. This tool never creates, scores, reviews or publishes.',
      input: (name === 'renulus_study_help' ? { type: 'object', additionalProperties: false, required: ['kind'], properties: { kind: { enum: ['hint', 'sources', 'notes', 'chat'] } } }
        : { type: 'object', additionalProperties: false, required: ['title', 'focus', 'count'], properties: {
          title: { type: 'string', minLength: 1, maxLength: 120 }, focus: { type: 'string', minLength: 1, maxLength: 2000 },
          count: { enum: [5, 10, 20] }, topic_id: { type: 'string', minLength: 1, maxLength: 256 } } }) as never,
      options: { codemode: false, permission: ASSESSMENT_PERMISSIONS[name] },
      execute: (args, ctx) => Effect.suspend(() => {
        let pending: Promise<Tool.Result> | undefined;
        return Effect.tryPromise({ try: signal => { pending = bridge.execute(name, args, ctx, signal).then(value => ({ content: JSON.stringify(value) })); return pending; },
          catch: () => new Tool.Error({ message: 'The practice tool is unavailable. Retry from Study or Tests.', metadata: { code: 'assessment_tool_failed' } }) })
          .pipe(Effect.onInterrupt(() => Effect.promise(async () => { await pending?.catch(() => {}); })));
      }) });
    }
  }).pipe(Effect.asVoid);
}
export function createAssessmentPlugin(bridge: ReturnType<typeof createAssessmentTools>): Plugin {
  return { id: 'renulus-assessment', effect: context => registerAssessmentTools(context, bridge) };
}
