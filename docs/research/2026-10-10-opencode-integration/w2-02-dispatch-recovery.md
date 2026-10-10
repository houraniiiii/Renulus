# Wave 2-02: dispatch and recovery composition

2026-10-10. Research only. Selected source: **4b6fea2875e4f2e3e8a8fee181803e54f7056845**. SDK **2.0.26**, tagged **9b4ec5714d481559990db0a816d5dec19541a814**, is distinct; its registry pins Effect rc.112. Current subscription defaults remain; future optional providers require explicit admission. [Package metadata](https://registry.npmjs.org/@opencode%2Fsdk/2.0.26)

**Decision:** supported service composition provides a credible fail-closed path without replacing the runner. No mandatory upstream patch is established. This is **observed source plus static checks**, not compiled composition or executed OpenCode behavior.

**Concrete composition.** Supply replacements through `OpenCode.create(options, {overrides})`; they follow standard replacements and reach selected instances. Use `node.replace(node.mapLayer(...))`: `mapLayer` preserves dependency wiring, whereas replacing with a bare layer requires that layer to be closed. Decorate the acquired service with `Layer.flatMap(raw, ctx => Layer.succeed(Tag, wrap(Context.get(ctx, Tag))))`; guards run inside returned methods. Capture the application policy controller in closures, avoiding new implicit dependencies. [Graph contract][graph] [Routing][routes] [Instance inheritance][instances]

| Replacement target | Preserved dependencies; responsibility |
| --- | --- |
| `llmClient`, from core `effect/app-node-platform` | `requestExecutor → httpClient`; wrap **stream, generate and compact**. |
| `SessionModelRequest.node` | `PluginHooks, SessionModelTransport, App`; validate four request kinds and install mandatory HTTP middleware. |
| `SessionModelTransport.node` | `webSocketConstructor`; wrap final handshake/send interceptors. |
| `SessionContext.node` | Preserve its existing graph; adapt selection/history and separately account for `selectTitle` and `request`. |
| `SessionCompaction.node` | `Agent, Bus, Database, llmClient, Model, SessionModelRequest, SessionRunnerModel`; retain lifecycle, enforce summary readiness. |
| `SessionRestart.node` | `SessionStore, SessionExecution, Bus, Job, Session`; defer the entire recovery method. |

Sources: [platform][platform], [request][request], [transport][ws], [context][context], [compaction dependencies][compactresult], [restart][restart]. Global nodes cannot acquire location nodes as graph dependencies. Adding `Plugin.node` to global LLM/recovery wiring is not the solution; preserve tags/error contracts and explicit scoped admission. [Tags][tags] [Replacement checks][graph]

**Dispatch coverage and concrete guard placement.**

- Ordinary and child turns share the runner/LLM path. Titles stream and may try a second model; compaction streams, repairs, shrinks, or calls native compact; session generation calls generate. Wrap all three LLM methods because the original `generate` captures its own inner `stream`. Install the global override: session generation captures LLM before entering the selected instance. [Runner][step] [Child][child] [Client][client] [Title][title] [Compaction][compaction] [Generation][generate]
- Proposed trusted admission carrier: the preparation decorator creates an opaque capsule containing session/configuration/retention epochs, purpose, route and attempt identity, associated with its mandatory `options.http` function in a private WeakMap. LLM methods reject missing/stale capsules. Unlike indexing only the request object, this survives compaction's request copies; endpoint compaction explicitly forwards `prepared.options.http`. Revalidate actual content and epochs at dispatch, including deterministic supplied summaries. Capsule propagation remains an **unexecuted proof**, not an upstream feature. [Preparation][request] [Compaction][compaction]
- Compose HTTP as `existing(req, sent => guard(sent).pipe(Effect.flatMap(() => send(sent))))`, or guard directly when no existing middleware exists. The guard must inspect the final URL, wire model/body and allowed attempt **after** hooks. The helper `RequestExecutor.middleware` runs outside per-call middleware, so using it as an initial check misses subsequent rewrites. [HTTP hooks][request] [Executor ordering][http]
- AI-SDK bypasses RequestExecutor, but passes `options.http` through AsyncLocalStorage around `language.doStream`; managed fetch invokes it before sending. This supports the same post-hook guard. Its route URL is only `https://ai-sdk.local`; validate the actual fetch URL. Custom language implementations/custom fetch can bypass or rewrite this boundary: admit only vetted adapters, otherwise deny. This is not containment of arbitrary executable plugins. [Adapter][adapter] [doStream][dostream] [Fetch][aisdk]
- Wrap `SessionModelTransport.bind` so supplied handshake/send hooks run first, followed by mandatory checks on their returned URL/headers/frame. Check reused-channel sends too. HTTP fallback can precede handshake; it must retain the HTTP guard and consume permitted attempts. Final network behavior, redirects and mid-flight revocation still need adversarial proof. [WS ordering/fallback][ws]

Keep stream admission lazy with `Stream.unwrap`; preserve compact overloads and the existing `AIError` channel. Context/request interfaces have no typed policy-error channel: denial mapping needs deliberate handling, without widening replacement contracts or calling a defect a pause. [Client contracts][client] [Preparation][request]

A further surface is plugin-exposed **stateless `Generate.text`**, which calls LLM without session preparation or options. Default-deny unadmitted calls; enable it only through explicit purpose admission. A header resembling a session ID is insufficient. [Stateless implementation][stateless]

**Context and activation pitfalls.** A context hook alone does not govern titles or the complete context service. Supplied compaction results skip stock dispatch; otherwise the coding template is appended after hooks, followed by a possible repair request. Require a validated educational result, or return a genuine failed compaction outcome without invoking stock generation. Preserve transform/reload, usage/events and manual-compaction settlement. A failed outcome stops the runner; it does not establish resumable pause semantics. [Context interface][context] [Compaction result/dispatch][compaction] [Outcome publication][compactresult]

The new host registers definitions before recovery, but registration only stores/publishes. `awaitActivation` means settled, including failures; failed reload can restore an older generation. Selected instances initially reject failed configured plugins, but this is not continuing health verification. Host admission must bind the approved revision and invalidate readiness on reload/failure; a settled latch or old active callback is insufficient. [Host][host] [Registry][registration] [Activation][activation] [Fallback][fallback] [Instance checks][instances]

**Recovery and deadlocks.** Gate `resumeSuspendedSessions` at invocation with an interruptible readiness effect followed by the original effect; acquire the service immediately. Waiting during layer acquisition blocks `runtime.contextEffect`, which precedes registration and creation returning: a startup deadlock. Waiting for every lazy instance to activate without first acquiring those instances also cannot establish readiness. Plugin setup must not wait for generation that itself waits for setup readiness; reject such bootstrap generation.

Keep the gate closed until policy/ownership and uncertain-dispatch decisions permit recovery. Delegate once, preserving host cancellation and the complete background-job/child reconciliation sweep. `maxAttempts:0` increments attempts and terminalizes claims; a permanent no-op loses reconciliation. Letting recovery run and denying later model calls can release claims as failed: **zero dispatch is not durable pause**. Selective per-session defer without attempt mutation remains unproved. [Host ordering][host] [Sweep/attempts][restart] [Failure settlement][termination]

**Minimal decision ledger and parent-plan corrections.**

| Disposition | Decision |
| --- | --- |
| Verified source support | Dependency-preserving decorators, all three LLM entries, managed AI-SDK HTTP middleware and deferred recovery method. |
| Integration proposal | One policy with multiple enforcement points; opaque admission, post-hook HTTP/WS checks, educational-result validation and closed recovery gate. |
| Unexecuted proof | Compile exact cohort; delayed/failed activation, reload fallback, child overrides, missing compaction result, title second attempt, native compact, AI-SDK fetch, WS reuse/fallback, shutdown while gated, and denied recovery without claim loss. |
| Required upstream patch | **None proven.** Manual recovery/required-plugin APIs remain convenience candidates, not established prerequisites. |

The relevant [parent plan](../../planning/OPENCODE_V2_INTEGRATION_PLAN.md) should explicitly include stateless generation, distinguish pause from terminal failure, and qualify “one final dispatch policy” as multiple enforced boundaries. Retry hooks can change tentative denial; title/summary retries require a shared attempt ledger. Middleware failures become transport errors, so a final denial must remain denied on retry; terminal-error presentation needs proof. [Retry decision][retry] [Error mapping][http]

**Checks executed:** 36/36 in-memory JavaScript static assertions against fetched pinned source/registry data: graph contracts, propagation, both startup orders, dispatch methods, middleware ordering, context/compaction, activation and recovery. Inspected 40 public resources; four guessed source/test paths returned 404 and supplied no evidence. Read assigned leads and relevant parent sections/current context code; confirmed Renulus HEAD `528025ff0b22477c12ee1512e0e7d15297a6e888`, detached. No OpenCode execution, installs, providers or broad test reruns. Citation ranges, local links, word count and whitespace were checked. Parent's Node 24.15.0 SQLite primitive and 19-pass/1-fail auth-capability baseline are separate evidence; neither validates this composition.

[graph]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/util/src/effect/layer-node.ts#L80-L137
[tags]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/util/src/effect/app-node.ts#L3-L12
[routes]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/server/src/routes.ts#L113-L156
[platform]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/effect/app-node-platform.ts#L7-L18
[host]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/src/internal/host.ts#L50-L60
[registration]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/plugin/sdk.ts#L28-L40
[instances]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/src/internal/instances.ts#L65-L101
[restart]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/execution/restart.ts#L77-L239
[client]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/ai/src/route/client.ts#L602-L683
[request]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/model-request.ts#L230-L436
[aisdk]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/aisdk.ts#L121-L224
[adapter]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/aisdk.ts#L368-L418
[dostream]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/aisdk.ts#L722-L745
[http]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/ai/src/route/executor.ts#L237-L278
[ws]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/model-transport.ts#L295-L571
[context]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/context.ts#L51-L207
[compaction]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/compaction.ts#L272-L455
[compactresult]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/compaction.ts#L595-L680
[title]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/title.ts#L66-L133
[generate]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/generate.ts#L25-L72
[stateless]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/generate.ts#L33-L103
[retry]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/runner/retry.ts#L64-L91
[activation]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/plugin/service.ts#L9-L16
[fallback]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/plugin.ts#L139-L178
[termination]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/execution.ts#L119-L145
[step]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/runner/step.ts#L73-L111
[child]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/tool/plugin/subagent.ts#L168-L210
