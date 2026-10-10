# Review 30 — Final adversarial architecture judgment

October 10, 2026. **Assessment: accept-with-corrections.** Accept Pi architecture and pi-durable as the first candidate to prove; keep the execution-owner decision reversible. This accepts a research recommendation, not a foundation change. I read reviews 01–29, especially [21](review-21-hermes-first-design.md), [22](review-22-pi-first-design.md), [23](review-23-opencode-first-design.md), [24](review-24-challenge-hermes-preference.md), [25](review-25-challenge-runtime-combination.md), the [accuracy audit](review-28-accuracy-audit.md), [scope audit](review-29-intent-and-scope-audit.md), and the [provisional synthesis](../2026-10-10-harness-foundation-recommendation.md).

Pins: Renulus `528025ff0b22477c12ee1512e0e7d15297a6e888`; Hermes bundled `af90026aa09949579bd423d24def3d38f743cde0`, inspected upstream `dce1e9b37581dd62e480a9064dc04a709c2940d3`; Pi v1.1.0 `abe508e1b89912adde45528136c3221eb69acdd7`; OpenCode v2/2.0.26 `55dde8810d8a859c0a21e42491ae7d5801fb49ef`. Links specify immutable files and one-based raw ranges. Renulus references were checked with git show; GitHub access may be required. Source inspection only; no execution, inference or Windows acceptance.

**Strongest objection — judgment:** the advantage could disappear at the adoption boundary. Renulus adds generation claims, selective purge, canonical reconciliation, client events/input and Windows ownership around an experimental coordinator. If those additions replace its task/storage machinery, choosing durable to avoid rebuilding coordination becomes circular. OpenCode already assembles the client/execution graph; Hermes keeps execution beside Python services. Give both equivalent acceptance conditions, without assuming fewer maintained changes. [O-host] [H-turn]

Five verified facts:

1. **The Pi adoption unit is substantive.** Harness options require injected Models and registry; execution environment is optional. Admission commits before acknowledgment, but repeated request IDs compare submission type rather than payload equality. Tools commit intent and default replay to unsafe. These are real library capabilities, separate from AgentSession; payload-digest binding remains Renulus work. [P-options] [P-commit] [P-reconcile] [P-tool]

2. **Control must reach dispatch and replay.** Reopen parks running tasks without dispatching; submit/wait/abort conveniences enable scheduling globally. Recovered request phases invoke generation independently of error-retry settings. Ordinary beforeRequest failures are reported and execution continues. **Correction:** initial beforeTool exceptions instead block, with final-argument revalidation; recovered safe-tool execution calls run directly, bypassing that initial guard path. Replayed domain operations need fresh service-level authority checks. [P-open] [P-resume] [P-generation] [P-retry] [P-hooks] [P-tool] [P-run]

3. **Retirement does not establish purge.** StorageWrite exposes no conversation/entry deletion operation; rewindable retirement keeps revision content. The API expressly changes without notice. Pinning alone cannot supply migration or selective purge before real saved conversations enter this store. Saved-default/Archive is already an unfinished migration; runtime persistence cannot count as its completion. [R-retention] [P-writes] [P-retire] [P-experimental]

4. **Ownership and durability have limits.** Pi's SQLite backend uses WAL/NORMAL, distinguishes process-crash survival from possible newest-commit loss on power failure, and supplies no cross-process lock. A Windows profile lock and demonstrated owner replacement remain Renulus obligations. [P-storage]

5. **OpenCode is the strongest assembled counterproposal, with an artifact trap.** The inspected branch registers supplied plugins before recovery and provides owned in-process fetch/lifecycle; restart permits repeated effects. The separate v2.0.26 tag instead starts recovery during host creation, then registers Promise-SDK plugins afterward. Review28 verified corresponding published fragments. Thus startup plugins cannot be assumed to gate published-SDK recovery. Preconstructed layer replacement or a reviewed source build needs proof. Published SDK rc.112/no gitHead differs from inspected rc.118; default CLI 1.18.35 cannot dismiss that SDK. [O-host] [O-restart] [O-tag-host] [O-tag-promise] [O-pin] [O-artifact]

**Minimum proof — proposed future evidence; all four block adoption.** The same connected proof must register a new tool/child role through a versioned extension contract and expose direct import/query to an independent consumer without creating a conversation or dispatching inference. Use synthetic text/PDF/image fixtures across nephrology domains. This verifies the data/extensibility premise.

- **Generation:** use actual durable tasks, scripted inference and interleaved parents/children. Crash after dispatch before response commit; reopen, submit unrelated work and cancel. Require zero automatic redispatch of uncertain generation, preserved validated DC16 batches, and explicit Retry bound to run/task/attempt/purpose, payload digest and selected route. Inject hook/broker failures and visible authentication/quota/model/image rejections. Hook-only denial or globally paused scheduling is insufficient.

- **Retention:** selectively purge a saved conversation with forks, children, compaction and rewindable documents; reopen and restore an older snapshot under current tombstones. Preserve unrelated conversations and canonical records. Exercise temporary scope and a supported-version migration. Archive/retirement flags cannot pass this proof.

- **Canonical effects:** crash after Python commits before runtime acknowledgment; reconcile operation receipts/outbox. Race deletion, revision replacement and Stop against safe-tool replay/publication. Require one committed outcome, no stale evidence/resurrected facts, and reviewed scoring separate from generated drafts. Runtime success cannot replace a canonical receipt.

- **Windows ownership:** package the managed JS owner and Python worker without developer PATH/Bash/WSL/Docker assumptions. Exercise two clients, owner death and reopen; demonstrate one profile writer and settled child cancellation. Deterministic reconciliation remains distinct from renewed generation.

The dated rejection rule covers authentication/quota/model/image errors; transient-network and general restart policy remains unresolved. DC16 independently prohibits automatically restarting billed/model work while preserving validated results. Preserve these distinctions. [R-policy] [R-adapter] [R-DC16]

**Reversal conditions — judgment:** reject pi-durable if passing requires rebuilding its scheduler or storage semantics, cannot preserve recoverable drafts without redispatch, or cannot selectively purge owned copies. Prefer OpenCode if its confined profile passes equivalent checks while retaining admission/jobs/client behavior and proving artifact correspondence. Prefer Hermes if controlled Python embedding passes with less maintained machinery: its synchronous loop is real, but client-hook failure falls through to ordinary construction. Python proximity establishes no route control. Agent-core remains a separate alternative requiring an explicit coordinator. [H-turn] [H-client]

Keep borrowing concrete: retain canonical SQLite/originals, Mem0/Docling HybridChunker/FastEmbed/LanceDB and compatible attributed Hermes adapters; borrow OpenCode protocol/provenance patterns without another execution graph. The Mem0 adapter does not require Hermes's loop. Exact selected-subscription/five-model tool compatibility needs separately authorised evidence; scripted proofs establish no educational quality across nephrology. [R-assets] [R-mem0] [R-route]

[P-options]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/types.ts#L453-L469
[P-commit]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/submissions.ts#L53-L60
[P-reconcile]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/submissions.ts#L148-L175
[P-tool]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/tool.ts#L62-L119
[P-run]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/tool.ts#L251-L260
[P-open]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/scheduler.ts#L238-L269
[P-resume]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/types.ts#L571-L590
[P-generation]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/generation.ts#L184-L209
[P-retry]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/generation.ts#L477-L505
[P-hooks]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/scheduler.ts#L1131-L1143
[P-writes]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/types.ts#L708-L724
[P-retire]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/storage/sqlite/storage.ts#L899-L925
[P-experimental]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/README.md#L1-L7
[P-storage]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/README.md#L536-L545
[O-host]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/sdk/src/internal/host.ts#L18-L68
[O-restart]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/execution/restart.ts#L23-L61
[O-tag-host]: https://github.com/anomalyco/opencode/blob/9b4ec5714d481559990db0a816d5dec19541a814/packages/sdk/src/internal/host.ts#L48-L64
[O-tag-promise]: https://github.com/anomalyco/opencode/blob/9b4ec5714d481559990db0a816d5dec19541a814/packages/sdk/src/promise.ts#L33-L59
[O-pin]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/package.json#L81-L85
[O-artifact]: https://registry.npmjs.org/@opencode%2Fsdk/2.0.26
[R-policy]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L142-L152
[R-adapter]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/hermes.py#L80-L116
[R-DC16]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md#L678-L695
[H-turn]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/turn_facade.py#L22-L33
[H-client]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/agent_runtime_helpers.py#L1928-L1957
[R-retention]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L23
[R-route]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/policy.py#L10-L22
[R-assets]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L48-L53
[R-mem0]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/memory/engine.py#L67-L82

**Handoff:** `docs/research/2026-10-10-harness-adoption/review-30-final-adversarial-judge.md`; conclusion: accept-with-corrections, reversible pi-durable proof candidate; strongest fact: recovered generation bypasses error-retry policy; unresolved risk: enforcing recovery/purge without replacing the adopted coordinator.

