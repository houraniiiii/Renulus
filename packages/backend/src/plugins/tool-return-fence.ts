// SPDX-License-Identifier: MIT
import { Effect } from 'effect';
import type { Plugin } from '@opencode/plugin/effect/plugin';
import { Tool } from '@opencode/schema/tool';
import type { StorageClient } from '../storage/index.ts';
import { reject } from '../storage/contracts.ts';
import type { NativeBinding } from '../dispatch/native.ts';

export function createToolReturnFence(storage: Pick<StorageClient, 'command'>,
  binding: (sessionId: string) => NativeBinding, open: () => boolean): Plugin {
  return { id: 'renulus-tool-return-fence', effect: context => context.tool.transform(editor => {
    for (const tool of editor.list()) {
      const permission = tool.options?.permission;
      if (typeof permission !== 'string' || !permission.startsWith('renulus.')) continue;
      editor.update(tool.id, current => {
        const execute = current.execute;
        current.execute = (input, native) => Effect.gen(function*() {
          const pinned = binding(native.sessionID);
          const snapshot = yield* Effect.tryPromise({ try: () => storage.command({ type: 'dispatch.snapshot' }),
            catch: () => new Tool.Error({ message: 'tool_authority_unavailable' }) });
          const check = () => Effect.tryPromise({ try: async signal => {
            signal.throwIfAborted(); if (!open()) reject('tool_authority_unavailable');
            await storage.command({ type: 'learning.current', runId: pinned.operation_id, binding: pinned });
            const run = await storage.command({ type: 'dispatch.run', runId: pinned.operation_id });
            await storage.command({ type: 'dispatch.current', runId: run.run_id, fence: run.fence,
              requiredCapabilities: [permission], permitId: null, grantEpoch: snapshot.grant_epoch });
          }, catch: () => new Tool.Error({ message: 'tool_authority_revoked' }) });
          yield* check();
          const result = yield* execute(input, native);
          yield* check();
          return result;
        });
      });
    }
  }).pipe(Effect.asVoid) };
}
