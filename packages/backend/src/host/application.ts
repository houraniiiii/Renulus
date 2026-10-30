// SPDX-License-Identifier: MIT
import { Context, Effect, Layer, ManagedRuntime } from "effect";
import { openCompatibilityFacade } from "../http/compatibility.ts";
import { openPythonDomain, type PythonDomainOptions } from "./python-domain.ts";

export const DomainOwner = Context.Service<Awaited<ReturnType<typeof openPythonDomain>>>("renulus/backend/DomainOwner");
export const PublicFacade = Context.Service<Awaited<ReturnType<typeof openCompatibilityFacade>>>("renulus/backend/PublicFacade");

export async function openCompatibilityApplication(options: PythonDomainOptions & { readonly port: number }) {
  const domain = Layer.effect(DomainOwner, Effect.acquireRelease(
    Effect.tryPromise(() => openPythonDomain(options)), owner => Effect.promise(() => owner.close())));
  const facade = Layer.effect(PublicFacade, Effect.gen(function* () {
    const owner = yield* DomainOwner;
    return yield* Effect.acquireRelease(Effect.tryPromise(() => openCompatibilityFacade({
      port: options.port, upstreamPort: owner.port, token: options.token,
      peerKey: options.token,
    })), service => Effect.promise(async () => { service.seal(); await owner.close(); await service.close(); }));
  })).pipe(Layer.provideMerge(domain));
  const runtime = ManagedRuntime.make(facade);
  try {
    const service = await runtime.runPromise(PublicFacade);
    const owner = await runtime.runPromise(DomainOwner);
    void owner.loss.then(() => service.block());
    let closing: Promise<void> | undefined;
    // Do not consume Effect's one-shot finalizers while an owned child refuses
    // settlement. The same retained application can retry close/reconciliation.
    const close = () => closing ??= (async () => {
      service.seal();
      await owner.close();
      await service.close();
      await runtime.dispose();
    })().catch(error => { closing = undefined; throw error; });
    return { port: service.port, state: service.state, close };
  } catch (error) { await runtime.dispose(); throw error; }
}
