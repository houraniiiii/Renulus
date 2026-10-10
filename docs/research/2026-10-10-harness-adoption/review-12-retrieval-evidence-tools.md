# Review 12 — Retrieval tools and trustworthy evidence

2026-10-10. Research only; no execution or corpus reads. Reviews 01–08 and 10 supplied leads. Baselines: Renulus `528025ff`; bundled/upstream Hermes `af90026aa`/`dce1e9b3`; Pi 1.1.0 `abe508e1`; OpenCode v2 `55dde881`. Links below give full immutable commits and raw line ranges.

**Conclusion — judgment:** retain Renulus’s Library/currentness/revision/rights/passage services behind two local tools and one separately granted network tool. Borrow Pi’s separation of model content and client details, Hermes’s Python handler integration, and OpenCode v2’s schema enforcement. Retrieval alone does not decide the overall foundation; none of these interfaces establishes educational quality.

**Five verified facts:**

1. Library retrieval selects active, ready, nondeleted, nonreserved revisions in the permitted Library entity scope before LanceDB hybrid search, then reloads canonical passages and checks eligibility/excluded pages afterward. Ordinary eligibility excludes drafts, preprints, retractions, supersession and replaced topics; `current_only` additionally requires final/latest-final/content review and no expired review deadline. Any replaced topic conservatively excludes the whole source. [K][I]

2. Docling passage locators retain item references, page/bounding boxes and character spans; text need not have a page. Returned results include document/revision/source IDs, headings, rights and an application HTTP original link. Source-status events update matching revision metadata transactionally. These are reusable domain assets, not framework capabilities. [L][K][J]

3. `check_evidence` currently accepts study scope only. Local references resolve canonical IDs/locators; public-article references supply their own text, metadata, digest and rights for validation. It does not authenticate those public bytes against a host-held receipt. Learn rechecks fresh citations before/after generation, but the final check precedes its answer-write transaction. **Inference:** expose opaque host evidence IDs, not this internal object checker directly; close the publication race explicitly. [V][P]

4. Network discovery uses installed topic labels, blocks case/unclassified scopes, reserves usage, and requires optional tools to be configured, enabled and selected. Discovery explicitly returns `passage_evidence:false`. Europe PMC’s body gateway checks metadata/JATS licence and identity; its excerpts remain dated research, never verified latest-final guidance. Candidate ineligibility may advance to a distinct article; network/budget/identity failures stop selection. [N0][N][B][E]

5. All three supply actual custom-tool seams; rights still belong in Renulus handlers:

| Pinned interface | Verified contract and project tradeoff |
| --- | --- |
| Hermes built-in registry, both pins | Schema plus sync/async handler; dispatch returns strings or multimodal envelopes and does not itself validate arguments. Python services fit directly; validate and serialize the evidence envelope explicitly. [H1][H2][H3] |
| Pi AgentSession SDK | `customTools`, explicit tool selection/suppression, cancellation/progress, output schema; model-facing `content` is separate from `details`/`structuredContent`. A local bridge must preserve that distinction. [PI1][PI4][PI2][PI3] |
| OpenCode v2 plugin API | Add/remove tools, cancellation/progress, input/output schemas; runtime decodes inputs and encodes declared outputs. `codemode:false` supplies direct tools. Typed adapters fit, but schemas do not authorize documents. [OC1][OC2][OC3] |

Pi’s separate **experimental** `packages/durable` also documents typed committed state beside transcripts. Its tool task commits intent and defaults replay to unsafe; interrupted execution repeats only when both recorded/current policies permit it. This is distinct from AgentSession. Borrow that classification for evidence receipts: a network lookup consumes quota and can change results, so “read only” does not make replay safe. Durable documents would remain operational receipts, not replacement SQLite authority. [PD1][PD3][PD2]

**Proposed minimal contract — not implemented:**

- `library_search(query, topic_id?, limit?)`: bounded passages plus host-issued evidence IDs; host policy fixes scope and minimum freshness. Model arguments may narrow grants, never broaden them.
- `evidence_read(ids, max_chars?)`: resolve only issued, authorized IDs; reload/recheck canonical text before expansion. Historical reader access must not bypass active-revision retrieval eligibility.
- `literature_lookup(topic_id, mode)`: separately granted discovery or licensed-body acquisition through existing services. Optional selected web tools provide discovery; the fixed Europe PMC body route retains its separate grant and dated-research class. No arbitrary URL, credential, import or index operation is model-callable.

An evidence artifact binds the exact supplied excerpt/context digest, document/revision/passage or article/hash identity, locators, attribution/operation rights, edition/publication/retrieval/check dates and verification class. A client-neutral original reference replaces model-facing filesystem/HTTP paths; clients resolve it through authorized readers. Save receipts under conversation retention policy; temporary receipts remain temporary. Mem0 learner context stays distinct from scientific evidence; Docling/FastEmbed/LanceDB stay derived infrastructure.

Filter scope and operation rights before index search; before returning text, check display/cache/model-input/derivation permissions and currentness. Treat text as untrusted data. Parent/child handlers inherit trusted source grants and cancellation. A host-only publication gate resolves cited IDs, revalidates them within the canonical write transaction or an equivalent revision fence, and blocks verified publication on change. Streamed draft text remains provisional. Never relabel case/generated-practice scopes as study to use today’s checker.

**No-result contract:** normalize to `ok`, `empty`, `blocked`, `failed` or `cancelled`. Non-`ok` results carry `evidence:[]`, a reason, searched scope/freshness and verification class. Distinguish no eligible documents from no matching passages; today’s `ready` may contain zero passages. Empty means this search supplied no evidence, not that none exists. Do not silently widen scope, downgrade currency, switch providers or invent citations. Discovery snippets cannot support passage verification. [K][N]

The October 6 rule specifically prohibits automatic retries/fallback on authentication, quota, model or image rejection. `max_retries=0` remains the conservative proof baseline; transient-network and restart recovery policy is separately unresolved. Broader automatic replay/regeneration would be a proposal. [R][A]

**Uncertainty/reversal evidence:** approved-model tool calling is unproven because current transport removes tools. Future authorized synthetic checks must reject fabricated evidence IDs, cross-scope reads and revision/rights changes during publication; distinguish empty/error results and replay quota-bearing lookup without hidden usage. Difficulty preserving these boundaries would weaken the preferred interface pattern. No clinical retrieval benchmark is claimed. OpenCode SDK 2.0.26 is published, but its Effect rc.112/no gitHead does not prove identity with this rc.118 source pin. [A][DIST][CAT]

Handoff: `docs/research/2026-10-10-harness-adoption/review-12-retrieval-evidence-tools.md`. Conclusion: retain domain retrieval behind evidence-ID tools. Strongest fact: search already rechecks canonical eligibility after index retrieval. Unresolved risk: authenticated evidence receipts and atomic publication remain missing seams.

[K]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/knowledge/repository.py#L509-L592
[I]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/knowledge/engines.py#L454-L463
[L]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/knowledge/engines.py#L201-L224
[J]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/knowledge/source_status.py#L242-L260
[V]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/knowledge/repository.py#L594-L655
[P]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/learn/service.py#L315-L357
[N0]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/retrieval/service.py#L35-L45
[N]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/retrieval/service.py#L108-L221
[B]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/retrieval/service.py#L251-L277
[E]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/retrieval/evidence.py#L13-L164
[H1]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/tools/registry.py#L666-L691
[H2]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/tools/registry.py#L875-L921
[H3]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/tools/registry.py#L875-L921
[PI1]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/sdk.ts#L64-L104
[PI4]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/sdk.ts#L465-L475
[PI2]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/extensions/types.ts#L574-L642
[PI3]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/src/types.ts#L424-L445
[OC1]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/plugin/src/promise/tool.ts#L11-L35
[OC2]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/tool/runtime.ts#L29-L69
[OC3]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/tool.ts#L225-L261
[PD1]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/README.md#L1-L7
[PD3]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/README.md#L78-L85
[PD2]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/tool.ts#L82-L116
[R]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L142-L152
[A]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/hermes.py#L66-L143
[DIST]: https://registry.npmjs.org/@opencode/sdk/2.0.26
[CAT]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/package.json#L83

