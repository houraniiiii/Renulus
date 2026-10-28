// SPDX-License-Identifier: MIT
import { Context, Effect, Layer, ManagedRuntime } from "effect";
import { openIsolatedStorage, type StorageClient, type WriterOptions } from "../storage/index.ts";
import { openTargetFacade, type TargetFacadeOptions } from "../http/target.ts";
import type { ConnectedTargetOptions } from './composition.ts';
import { createRecoveryPort } from './recovery-select.ts';

export const CanonicalOwner = Context.Service<StorageClient>("renulus/backend/CanonicalOwner");
export const TargetFacade = Context.Service<Awaited<ReturnType<typeof openTargetFacade>>>("renulus/backend/TargetFacade");

/** Target flows use TS sole authority on an explicitly selected synthetic DB. */
export async function openTargetApplication(options: WriterOptions & Omit<TargetFacadeOptions, "storage"> & {
  connected?: Omit<ConnectedTargetOptions, 'storage' | 'profileRoot'>;
  /** Exact bundle verifier; with a selected-owner launch it opens candidate-generation selection. */
  verifyBinaries?: Parameters<typeof createRecoveryPort>[0]['verifyBinaries'];
}) {
  const writer: WriterOptions = { profileRoot: options.profileRoot,
    ...('selectedAuthority' in options && options.selectedAuthority ? { selectedAuthority: options.selectedAuthority } : { selection: options.selection! }),
    migrations: options.migrations, expectedSchemaHash: options.expectedSchemaHash };
  const storage = Layer.effect(CanonicalOwner, Effect.acquireRelease(Effect.tryPromise(() => openIsolatedStorage(writer)),
    owner => Effect.promise(() => owner.close())));
  const facade = Layer.effect(TargetFacade, Effect.gen(function* () {
    const owner = yield* CanonicalOwner;
    return yield* Effect.acquireRelease(Effect.tryPromise(async () => {
      const connected = options.connected ? await (await import('./composition.ts')).openConnectedTarget({
        ...options.connected, profileRoot: options.profileRoot, storage: owner }) : undefined;
      try {
        return await openTargetFacade({ ...options, storage: owner,
          ...(options.verifyBinaries && 'selectedAuthority' in options && options.selectedAuthority
            ? { recovery: createRecoveryPort({ authority: options.selectedAuthority, verifyBinaries: options.verifyBinaries }) } : {}),
          ...(connected ? { learning: connected.learning, temporary: connected.temporary, plugins: connected.plugins, credentials: connected.credentials,
            mcp: connected.mcp, developer: connected.developer, questions: connected.questions,
            configuration: connected.configuration, inspect: connected.inspect, memory: connected.memory,
            knowledge: connected.knowledge, find: connected.find, assessment: connected.assessment, study: connected.study, updates: connected.updates,
            settlePlugins: connected.close } : {}) });
      } catch (error) { await connected?.close(); throw error; }
    }),
      service => Effect.promise(() => service.close()));
  })).pipe(Layer.provideMerge(storage));
  const runtime = ManagedRuntime.make(facade);
  try {
    const service = await runtime.runPromise(TargetFacade);
    let closing: Promise<void> | undefined;
    const close = () => closing ??= service.close().then(() => runtime.dispose()).catch(error => { closing = undefined; throw error; });
    return { port: service.port, closed: service.closed, close };
  }
  catch (error) { await runtime.dispose(); throw error; }
}
