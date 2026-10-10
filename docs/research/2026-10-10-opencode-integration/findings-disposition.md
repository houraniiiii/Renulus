# Findings disposition and implementation gates

This ledger distinguishes research resolution from implementation completion. Assigning a finding to a specification/ticket closes a planning gap; it does not repair the product or satisfy that ticket. Current source is `76cfdff`; earlier findings retain their dated scope.

| Finding | Verified observation / limitation | Evidence class | Owner slice | Disposition |
| --- | --- | --- | --- | --- |
| [Artifact identity](w1-03-artifact-host.md) | SDK2.0.26 and newer source have different Effect/startup cohorts | Static + registry/SRI | H01 | Pin one source-built cohort; no mixed dependencies |
| [Late policy readiness](w2-02-dispatch-recovery.md) | Registration is not successful activation; recovery may dispatch | Static | H01/H04 | Closed construction and method-level recovery gate; executable proof required |
| [Delayed recovery cleanup](w3-04-host-proof-adversary.md) | Cleanup predicate can clear a fresh foreground child | SQL predicate reproduction, not runtime race | H01/H07 | Full-sweep admission quiescence first; selective defer only with proven filtering |
| [Bypass surfaces](w2-05-configuration-revocation.md) | Stateless/auxiliary/AI-SDK/WS/MCP retries reach distinct effects | Static | H03/H04/H09 | One policy at all real dispatch seams; trusted code is not sandboxed |
| [Failed reload](w1-04-extensions.md) | Failed generation can restore an older plugin registration | Static | H04 | Effective registry proof; atomic active version; restart activation first |
| [Temporary storage](w3-04-host-proof-adversary.md) | Instances share DB; oversized tool output spills to disk | Static | H06 | Separate volatile graph/output services; sentinel scans and promotion proof |
| [Current work](w3-03-minimality-design-c.md) | Conversation/jobs/Home/nightly/typed restore already landed | Current committed source | All migration slices | Adapt existing owners and IDs; freeze/reconcile source baseline |
| [Memory recapture](w4-01-current-memory.md) | Old consumed text reappears after edit/delete under new ID | 4 current service/worker reproductions | H05 | Persist transitive dependencies and terminal invalidation; preserve existing restore barrier |
| [Typed cascades](w3-01-migration-retention.md) | Old generic cascade fixtures are fixed in current code | 8 helper assertions + current selected tests | H18 | Extend typed relations rather than recreate or repeat obsolete defect |
| [Deleted receipt payload](w4-03-current-conversations.md) | Deleted draft text/hash remains in receipts/new export | 2 current-kind reproductions | H06/H18 | Reference-only live receipts; opaque retired-operation tombstones; creation receipts included |
| [Generation retrieval](w4-02-current-workflows.md) | SavedGenerationService lacks helper-required guard_run | Current failing tests + direct probe | H00 then H12 | Narrow caller-guard prerequisite; preserve guarded legacy caller |
| [Publication fence](w4-02-current-workflows.md) | Current saved generation already fences source in commit | Current source, runtime path blocked upstream | H12/H13 | Preserve transaction and bind authority across IPC; retest after H00 |
| [Nightly semantics](w4-02-current-workflows.md) | Sleep catch-up differs from future-only cold restart | Source + 2 passing recovery tests | H17 | Preserve semantics; reconcile claim-to-submit gap without inference replay |
| [Capability reset](w3-02-capabilities-evaluation.md) | Stored credential can restore available after mocked401 | Current-unchanged methods + earlier suite failure | H03 | Separate documented support/access/observations; new credential epoch |
| [Model roles](w3-02-capabilities-evaluation.md) | No measured best model or verified selected-account256K | Evidence limit | H03/H04/H10 | Inherit selected model, explicit role evaluation, independent capability evidence |
| [Context tail](w2-04-context-integration.md) | Supplied summaries retain separately clipped recent text | Static + translated logic | H10 | Rebuild eligible complete recent pairs and final-budget check |
| [Usage estimate](w2-04-context-integration.md) | Same-provider route change can reuse wrong measurement | Translated formula probe, not runtime proof | H10 | Invalidate incompatible observations; final-route budget |
| [Article units](parent-context.md) | 64–128KB view is not128Ktokens | Pinned article + interval/UTF8 simulation | H10/H11 | Separate byte/token budgets; exact-history first, then evaluated derived tree |
| [Memory scopes](w4-01-current-memory.md) | Current recall/dedup is profile-global; temporary excludes it | Current source/selected tests | H05/H06 | Preserve existing scope; explicit project-owned additions only |
| [Cross-store consistency](w3-01-migration-retention.md) | No transaction spans domain/runtime stores | Design constraint | H01/H06/H18 | Stable IDs/receipts, paired manifest, quiescent generations and compatible rollback |
| [Current path behavior](w4-01-current-memory.md) | Long synthetic paths caused Qdrant errors; short paths passed | Executed test environment limitation | H20 | Test supported delivered paths; do not invent an OS threshold |
| [Full host acceptance](w3-04-host-proof-adversary.md) | No compiled/running integrated OpenCode proof in research | Explicit unexecuted gate | H01 then H20 | First implementation gate; do not call static support runtime acceptance |
| [Unowned model producers](w5-01-ticket-review.md) | Import/refinement and fictionalisation still dispatch through existing purposes | Current source review | H22/H23 | Explicit vertical adapters; all default producers precede H18/H20 |
| [Worker close lifetime](w5-02-ipc-lifetimes.md) | Close can return while extraction thread still runs | Controlled current-service probe | H24 then H05/H18 | Actual worker lease/finalizer settlement before engines/store handoff; no observed late facts |
| [Resolver RPC lock hazard](w5-02-ipc-lifetimes.md) | Current resolver calls occur inside canonical write transactions | Current source + integration inference | H05 | Resolve immutable content outside transactions/thread locks; local reference checks at commit |
| [IPC/reconnect/Save](w5-02-ipc-lifetimes.md) | Observer queue rules and local ContextVars cannot become cross-process command semantics | Source-informed design requirement | H01/H02/H21 | Process generations, reserved control capacity, rebound guards and explicit promotion states |
| [Attempt/output ambiguity](w5-03-route-context-audit.md) | Continuations differ from retries; hooks can remove auxiliary output caps | Pinned source review | H03/H04/H10 | Shared durable dispatch allowances and all-kind final budgets; numeric defaults explicitly proposed |
| [Optional strategy blockers](w5-01-ticket-review.md) | Tree was optional but unnecessarily gated baseline release | Ticket graph review | H10/H11/H18/H20 | Exact-history baseline in H10; H11 follows core restore and is required only for tree activation |
| [Instruction precedence](w5-03-route-context-audit.md) | Pinned guidance wording conflicted with ordinary edits/current constraints | Spec/ticket review | H08/H10 | User preference before optional skill; pinned content plus current mandatory revocations; explicit migration |

Wave-5 changes preserve stable IDs: H06 is saved migration; H21 is temporary/Save; H22 fictionalisation; H23 import/refinement; H24 actual memory-worker settlement. The review's suggested H06A/B and H21/H22 identifiers were proposals, not lost work. H18 consumes all default producers; H11/H19 are optional after their own gates. Numeric dispatch/output/child bounds remain proposed defaults subject to task fixtures.

No claim of educational efficacy, live selected-account context capacity or installed OpenCode acceptance is made.

## Final-wave disposition

- W6-01 found no remaining requirement/default-producer orphan or cycle: 25 slices, 53 edges; all default paths reach H18/H20, with optional H11/H19 excluded.
- W6-02's three remaining contract details were applied and rechecked: all cross-process waits stay outside canonical transactions and conversation/case/recovery physical locks; bounded drain is distinct from actual settlement/ownership release; IPC exposes five admission/outcome states and never drops command replies as observation events. H01/H18/S1 and the plan own these rules.
- W6-03 verified evidence categories and overlapping counts. Nine machine-specific W5 links were replaced with portable commit/path source-map references; the map now includes 29 raw-byte-identified source entries. No aggregate regression-pass count is asserted.
- W6-04's exact Automatic ordering and standalone one-permit preflight refinements were applied. The initial numeric budgets remain proposals and all runtime/quality gates remain open.

The final implementation frontier is H00 (generation guard), H24 (memory-worker settlement) and H01 (actual embedded host). All are still unchecked. Research/specification review is complete; the requested skill's human seam/breakdown review and GitHub publication remain pending.

