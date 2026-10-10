# W2-04 — Context integration boundary

2026-10-10. Research only. **Recommendation: use a Renulus plugin plus the mandatory host dispatch gate; defer native checkpoints and tree-driven prompt replacement.** The [parent plan’s context section](../../planning/OPENCODE_V2_INTEGRATION_PLAN.md#memory-retrieval-and-128k256k-context) is directionally sound but needs the qualifications below.

**Evidence:** OpenCode source `4b6fea2875e4f2e3e8a8fee181803e54f7056845`; [SDK 2.0.26 metadata][sdk] belongs to the distinct tag `9b4ec5714d481559990db0a816d5dec19541a814`. Its [compaction-result contract][tag] matches the inspected source. Findings are static unless explicitly labelled Python probes; no OpenCode host/provider was executed.

**Smallest extension — proposed.** Set effective model/variant `settings.compaction={type:"summary"}` through `ctx.model.transform`, cap model input/context limits using the proven route ceiling, and set `compaction.auto/buffer/keep.tokens` through managed configuration. Neither a 128,000 nor 256,000 requested ceiling establishes subscription capacity. [Model editor][editor], [variant merge][variant], [policy schema][policy], [configuration][config]

Register `ctx.session.hook("compaction")`: obtain an eligible, bounded educational summary through the purpose-gated summary operation, then set `event.result={summary,metadata,tokens}`. Metadata references transcript ranges, policy version, dependency revisions and retention epoch. This skips stock generation; changing the ordinary agent prompt does not, because stock compaction appends its template **after** hooks. Validate summary completeness/size before returning. Supplied-result tokens record summary-generation expenditure, not the next prompt’s size. [Hook][hook], [dispatch][deliver], [accounting][fromhook]

Use `hook("context")` for bounded context assembly and native history read/search/zoom tools backed by host `Session.messages/message`. `Session.context` returns compacted history, so it cannot alone recover originals. Keep one OpenCode transcript and lifecycle; the tree is derived. Use the shared mandatory dispatcher to validate readiness, epochs and final request size after hooks; do not rely solely on a customization exception. [History APIs][store], [request assembly][request], [hook failure contract][failures]

**Recent exchanges are not preserved losslessly.** Stock summary compaction defaults to 15,000 estimated recent tokens, aligns the boundary to user exchanges, then serializes them into one historical user message. Tool outputs are clipped to 1,250 characters and attachments become labels. `keep.tokens=0` still retains the latest exchange in a multi-exchange conversation. The supplied-result contract cannot replace `recent`; the native branch supplies no such tail. Thus the parent’s “recent complete exchanges” is an additional integration requirement. [Split/serialization][tail], [checkpoint rendering][render]

Initially restore the selected complete recent exchanges from authoritative message IDs in the context hook, replacing the serialized tail to avoid duplicates. Preserve call/result IDs, order and explicit media availability; treat completed historical calls as records, never executable instructions. Keep unresolved calls outside summary coverage. The runner awaits tool fibers and settles interrupted calls; manual preview excludes an unfinished assistant. Preserve these boundaries and test cancellation/restart rather than injecting invented results. [Settlement][step], [preview][history]

**Token accounting needs an independent check.** Native checkpoints require matching provider, model, route, protocol and endpoint. Incompatible history expands correctly, but `hasMeasuredPrompt` checks only provider ID. A same-provider model/endpoint switch can therefore reuse usage measured against an unavailable compressed window. Context-hook additions also occur after the runner’s estimate/output-limit calculation. [Provenance][native], [estimator][estimate], [request assembly][request]

**Executed Python translation:** synthetic same-provider A→B re-expansion produced **5,025 estimated versus 150,125 expanded-text tokens**; the former falls below the 128,000-window trigger. Default triggers are **112,000/230,400** for decimal 128,000/256,000 windows; unknown limits yield infinity, with a separate 200,000 fallback for compaction requests. These are source-formula results, not tokenizer or provider measurements. Admit only after accounting for the actual assembled text, schemas, media, output and reserves. [Ceiling/estimator][estimate], [unknown fallback][fallback]

**Instructions, readiness and lineage.** Completed compaction advances the instruction epoch to current values. Read-loaded file instructions use visible synthetic-message paths as their ledger; they become eligible for reinjection on another load, not automatically on every post-compaction request. Reacquire versioned required policy explicitly and prevent stale serialized instruction text becoming authority. [Epoch][epoch], [read ledger][ledger]

`fromHook` accepts even an empty supplied summary without readiness validation. Publish a checkpoint/view only for a complete, current dependency manifest; retain eligible children/raw ranges when a tree parent is unavailable. If that representation cannot fit, block with retryable context-not-ready. Do not publish a partial tree or wait indefinitely for background summaries. [Supplied result][fromhook]

[W1-02](w1-02-memory.md) reproduced corrected/deleted memory resurfacing through a later answer’s distinct evidence ID. Independent inspection confirms request-local pins and completed-answer references without durable memory dependencies. Link answer→memory/source revisions and summary→answer/range dependencies before automatic capture; revalidate at summary publication, dispatch, zoom and memory commit. Summaries remain ineligible capture producers. [Pins][pins], [answer publication][answer]

Removal invalidates affected ancestors/views and closes native continuation state; opaque checkpoints cannot be selectively scrubbed. Whole-session removal stops execution and recursively removes children, but the inspected API supplies no equivalent scoped redaction flow. Prove erasure across retained events/checkpoints and restore, separately from prompt suppression and the user’s choice about independently retained learning. [Removal][remove]

**Challenge to the article.** The [pinned article][article] uses UTF-8 bytes, summarizes even the recent view, clips tool output, and waits for earlier summaries before starting a fresh turn. Those choices do not establish lossless recall or fit OpenCode’s existing turn lifecycle. Retain only derived navigation and optional batched views; permit lexical lookup, revision invalidation and deletion. Its cache simulation is not a Renulus measurement.

**Staged acceptance / next-wave gaps — proposed.**

1. Scripted embedded-host test: educational result, exact recent pairs/media markers, refreshed instructions; inject missing plugin, empty/failed summary and correction during preparation. Require zero stock-summary dispatch, zero unready checkpoint publication, and complete cancelled-tool settlement.
2. Synthetic CKD/dialysis/transplant/glomerular histories: saturate both requested ceilings, inject schema/media growth and same-provider re-expansion; verify final admission and exact evidence recovery. Exercise deletion during zoom, dependent-answer capture, child/restart/restore and lagging tree parents.
3. Enable tree selection only after those invariants pass. Real summary fidelity, subscription windows and cache/latency remain unproved and need separately authorized inference.

Prefer extension-level assembly. Use a narrow host service override only if it cannot enforce checkpoint readiness before publication. Native checkpoint adoption additionally needs provenance/context-epoch-aware usage invalidation; scoped erasure needs a verified storage mutation path. These are conditional patches, not reasons to replace the runner. [Embedding override][host]

**Exact checks run:** managed `C:/Renulus/dev/python/Scripts/python.exe -B -`, inline, sockets denied: **11 static assertions and three translated-logic probes passed**—contract/result handling/configuration/provenance/estimation; ceiling arithmetic; re-expansion accounting; zero-keep/clipped-tail behavior. Article SHA-256 matched the parent’s pin; five local implementation files matched Renulus `528025ff0b22477c12ee1512e0e7d15297a6e888`. No prior suites or 20,001-interval simulation rerun. One earlier oversized inline invocation failed before execution and was reduced.

[sdk]: https://registry.npmjs.org/@opencode%2Fsdk/2.0.26
[tag]: https://github.com/anomalyco/opencode/blob/9b4ec5714d481559990db0a816d5dec19541a814/packages/plugin/src/promise/session.ts#L38-L48
[editor]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/plugin/src/promise/model.ts#L7-L27
[variant]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/model-resolver.ts#L143-L161
[policy]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/schema/src/provider.ts#L36-L54
[config]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/config/plugin/compaction.ts#L15-L22
[hook]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/plugin/src/promise/session.ts#L25-L48
[deliver]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/compaction.ts#L272-L309
[fromhook]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/compaction.ts#L594-L608
[store]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/store.ts#L140-L185
[request]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/model-request.ts#L240-L302
[failures]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/plugin/hooks.ts#L21-L29
[tail]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/compaction.ts#L698-L850
[render]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/runner/to-llm-message.ts#L306-L325
[step]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/runner/step.ts#L144-L235
[history]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/history.ts#L137-L159
[native]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/provider-context.ts#L17-L39
[estimate]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/compaction.ts#L868-L963
[fallback]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/compaction.ts#L200-L229
[epoch]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/projector.ts#L729-L735
[ledger]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/instructions.ts#L35-L79
[pins]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/learn/memory_context.py
[answer]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/learn/service.py#L342-L370
[remove]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session.ts#L367-L377
[article]: https://gist.githubusercontent.com/VictorTaelin/91837951a5ce5b38f341ec1ba1df6449/raw/4c09901baa3685852bf252cdb70ace81d01d6be5/optchat.md
[host]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/src/internal/host.ts#L25-L45

