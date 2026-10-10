# Review 04 — Renulus reusable core and execution seam

**Synthesis clarification:** references below to disabling all automatic generative retries describe the conservative adoption-proof baseline. The October 6 confirmed rule specifically concerns actual authentication, quota, model and image rejection without automatic retry/fallback; transient-network and restart policies remain separate proposals. [Review09](review-09-route-control-authentication.md) resolves this scope. This distinction qualifies the earlier shorthand, rather than establishing a broader ban.

2026-10-10. Assignment #4; research only. These findings were verified against Renulus `528025ff0b22477c12ee1512e0e7d15297a6e888` with `git show`. Links cite immutable files and raw line ranges; repository access may be required. No runtime tests or inference were performed.

**Conclusion — engineering judgment:** retain the existing domain core and introduce a small execution interface above it. Renulus already has reusable data and educational record infrastructure. The missing general loop is at the model/tool continuation seam, not inside ingestion, learner memory or scoring. This review makes no framework choice.

Four decisive implementation findings:

1. **Knowledge and Memory preserve canonical authority.** Docling/HybridChunker produces passages and source locators; FastEmbed loads local CPU assets. Knowledge retrieval checks active revisions, rights, source status and excluded pages against SQLite before returning passage text. Memory recall similarly joins derived index hits to current canonical fact revisions and checks deletion markers. These implementations are substantial reusable harness assets: keep the existing Mem0/Docling/FastEmbed/LanceDB adapters behind the domain modules, with SQLite authority distinct from indexes and transcripts. Sources: [ingestion][K1], [knowledge retrieval][K2], [memory recall][M1].

2. **Content, assessment, storage and Study already own domain decisions.** Pack hashes prevent replacing an installed content version, and key corrections require predecessor withdrawal. Reviewed answer submission checks currency, scores against the pinned snapshot and commits attempts plus learning evidence transactionally. Study proposes committed-mistake review followed by topic coverage while preserving manual edits. SQLite supplies explicit transactions and record ledgers. These modules should remain responsible for their records; educational quality is not established by their existence. Sources: [content versions][C1], [answer commit][A1], [Study][ST1], [storage][S1].

3. **Application coupling concentrates in composition and response shapes.** Server construction applies migrations and instantiates modules through HTTP routers. Library results contain an HTTP `original_url`, so a caller currently receives an application-specific link alongside stable document/revision identities. This is evidence for extracting client-neutral bootstrap and artifact references, while retaining HTTP as one client adapter. It does not require replacing the underlying repositories. Sources: [bootstrap][W1], [Library result][W2].

4. **The generation seam cannot currently express a general agent loop.** `generation.Provider.stream(...)` yields text strings; Learn recalls memory, streams the answer and commits learning records around that interface. Input roles are limited to system/user/assistant. Transport removes tool schemas, rejects returned tool calls and sets SDK retries to zero. A reusable service registry therefore does not yet provide model → tool → result → model execution. Sources: [generation interface][G1], [Learn orchestration][L1], [message roles][G2], [transport][G3].

**Proposed interface — not implemented:**

- `start(request, trusted_policy) -> RunHandle`: references a conversation and attachments; host policy fixes scope, retention, exact subscription/model, capabilities and budgets.
- `events(run_id) -> AsyncIterator<HarnessEvent>`: streams ordered text, tool request/result and terminal events, including child-run references where delegation is granted.
- `cancel(run_id)`: propagates cancellation to the model request and owned execution.

Behind this interface, a model-step adapter must accept tool results and emit typed tool calls in addition to text/completion. Extending the restricted input/transport contract is required; wrapping the existing string iterator alone is insufficient. A scoped `invoke(name, validated_args, run_context)` interface can expose Library search, Memory recall, Study planning and public assessment summaries through existing modules. Canonical mutations retain module checks; scored answers require learner action. The model cannot grant itself permissions, rewrite keys or promote transcript text into authoritative learner evidence.

**Project tradeoff — judgment:** keeping these Python modules preserves domain logic and record ownership, but a foundation in another process needs a serialization and lifecycle adapter. The trusted host must retain the exact subscription/model policy, disabled automatic generative retries and approved local CPU helper constraints. Save-by-default/Archive remains a separate required migration. This proposal does not establish that migration or successful tool/subagent execution.

**Explicit uncertainties:** exact approved-model tool-call compatibility and cancellation across model execution and canonical writes are unverified. Evidence that would change this conclusion is a bounded headless tool-continuation trial showing that these modules require substantial application workflow rewrites, or that their canonical checks cannot survive the new execution seam. Conversely, such a trial preserving citations, revisions, scoring authority and cancellation would support this interface. Context, scheduling and broader framework comparisons are outside this review.

Handoff: `docs/research/2026-10-10-harness-adoption/review-04-renulus-reusable-core.md`; retain domain core and add the execution seam; strongest fact: transport explicitly rejects tool calls; unresolved risk: approved-model compatibility and canonical authority during execution.

[K1]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/knowledge/engines.py#L92-L224
[K2]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/knowledge/repository.py#L509-L592
[M1]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/memory/service.py#L278-L310
[C1]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/content/repository.py#L177-L227
[A1]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/assessment/repository.py#L251-L303
[ST1]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/study/service.py#L142-L219
[S1]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/storage/database.py#L16-L58
[W1]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/server.py#L86-L108
[W2]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/knowledge/repository.py#L572-L581
[G1]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/generation.py#L8-L15
[L1]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/learn/service.py#L296-L369
[G2]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/inputs.py#L39-L41
[G3]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/hermes.py#L66-L143

