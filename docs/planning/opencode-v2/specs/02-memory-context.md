# S2 — Evidence, learner memory and long conversation context

Status: reviewed specification. H24 has local worker-settlement acceptance in the [implementation handoff](../../../implementation/OPENCODE_FOUNDATIONS_HANDOFF.md). Lineage, corrected-memory behavior, migrated conversations, long context and complete paired restore remain their owning tickets.

## Problem Statement

Moving execution must preserve Renulus's existing memory and source safeguards. Four current-baseline service/worker reproductions confirm that a completed answer can recapture text from a corrected/deleted fact. Current Design C's added invalidation and restore barriers must be preserved, but they do not provide the missing answer dependency. Long conversations also need more than a larger constant: correct instruction injection, exact evidence recovery and retention-aware summaries are required.

## Solution

Retain the approved domain engines and canonical records. Connect OpenCode messages through verified answer references and persistent dependency lineage. Provide explicit 128K/256K context profiles where the route supports them, educational compaction, exact history retrieval and a derived summary tree that can be enabled after recall and invalidation tests pass.

## User Stories

1. As a doctor, I want useful learning points retained without duplicate records, so that later study benefits from earlier work.
2. As a doctor, I want corrections to remain authoritative, so that an older answer cannot silently restore a corrected belief.
3. As a doctor, I want deletion and suppression to cover derived captures, so that removed memory does not reappear under another ID.
4. As a doctor, I want to see whether a record is my observation, preference or generated teaching, so that its evidential role is clear.
5. As a doctor, I want assessed performance kept separate from generated explanations, so that memory does not invent mastery.
6. As a project user, I want clear global/project scope, so that one project's material does not leak into another.
7. As a doctor, I want temporary conversation derivatives to remain temporary, so that history and memory controls are meaningful.
8. As a doctor, I want cited passages and their originals to reopen, so that I can inspect the actual source.
9. As a doctor, I want changed or retracted sources reflected in later answers, so that old context is not treated as current evidence.
10. As a doctor, I want a long-context profile with an honest effective limit, so that I know whether 128K or 256K is actually usable.
11. As a doctor, I want recent exchanges, exact values, units and pending questions preserved, so that compaction does not change the task.
12. As a doctor, I want older summaries to open into exact retained detail, so that the assistant can verify rather than infer a missing fact.
13. As a doctor, I want history search as well as summary navigation, so that omitted summary clues do not make retained information inaccessible.
14. As a doctor, I want current instructions reapplied after compaction and restart, so that obsolete guidance does not silently govern work.
15. As a doctor, I want a failed summary to preserve my input, so that the system does not continue with a hidden gap.
16. As a profile owner, I want deletion to survive backup restore, so that an older archive cannot resurrect revoked data.
17. As a maintainer, I want inspectable context provenance and bounded summary costs, so that regressions can be diagnosed without logging private payloads.

## Implementation Decisions

- SQLite remains canonical for learner facts, revisions, evidence and tombstones. Mem0/local Qdrant and LanceDB remain derived indexes. Docling/HybridChunker and FastEmbed retain their roles. Use one profile-owned memory worker; do not instantiate one per child.
- Extend current typed Dependency/EligibleInput contracts, publication guards and restore/context epochs for answer/history/tool/summary lineage. Preserve the current deliberately restored-memory barrier. Do not add a competing invalidation, retention or scope authority.
- OpenCode owns the migrated conversation transcript. A Completed Answer reference identifies immutable message/range identities, a content digest, completed execution and eligible publication receipt. A resolver verifies these without maintaining another writable transcript. Existing legacy answers remain readable through the same logical interface.
- Resolve immutable answer bytes outside canonical transactions and physical conversation/case/recovery locks. Revalidate local publication receipts, dependencies and current policy at commit. Keep the existing extraction thread off the event loop and retain its worker lease through actual finalizer completion, even after coroutine cancellation. A close timeout cannot release engines/stores as if work settled.
- Persist reference-only dependencies on exact memory/source revisions used by an answer. Validate them when admitting and committing later capture, reconstructing context and publishing dependent artifacts. Correction/suppression invalidates descendants and queued work; deletion tombstones survive rebuild and restore. Multi-source and independently edited facts require explicit relation semantics, not a generic cascade by field name.
- Include historical messages, tool results and summary nodes in the dependency closure. Independent reproduction found stale recapture even after the first capture completed and was suppressed. Unknown legacy lineage is not treated as an empty valid manifest.
- Separate storage ownership from truth support. Inputs inside a support group are jointly required; independently rooted groups may support a fact separately. Echoes inherit roots, cycles are rejected, explicit manual corrections have new support and direct deletion overrides all groups. Ordinary chat deletion follows the existing disclosed retained-learning rule; explicit delete-related-learning revokes the relevant support.
- Distinguish generated teaching from learner observations, preferences and reviewed assessment evidence. A summary is navigation/reference data. It cannot grant permissions, become a scientific source, produce mastery evidence or automatically seed learner memory.
- Define profile-global and project visibility explicitly; scope is host-derived. Temporary history, attachments, children and summary indexes remain volatile. Deliberate promotion uses the established eligible-save semantics and cannot silently copy excluded material.
- Existing learner memory remains explicitly profile-global during migration. New project-owned records require scoped identity/deduplication; chat moves cannot relabel old facts. Preserve current exclusion of Study recall/capture in temporary ordinary conversations and learner capture from raw saved cases. Advancing an epoch alone cannot fix recapture when scans can requeue unchanged sources; revoked dependency lineage stays terminal.
- Temporary sessions use a separate in-memory runtime graph and volatile output/attachment handling, not a flag on the persistent store. Whole-session erasure, scoped correction/invalidation and human-readable retained history have distinct semantics. Inspect event payloads, recent tails, spills and backup copies separately.
- Retrieval rechecks current rights, ready revisions and source eligibility before returning/using passages and before dependent publication. Preserve exact document/revision/locator identities. Source lookup failure remains visible.
- A Context manifest records instruction/configuration versions, exact active task, recent complete exchanges, pending tool results, memory/source revisions, history ranges, route limits and retention epoch. Corrections/revocations apply before dispatch and commit; already invalidated material is never treated as current simply because it appears in an old transcript.
- Reinjection uses the run's pinned instruction/skill version and current mandatory scope/revocation constraints. Newly edited global guidance requires explicit run migration; old serialized instructions cannot restore authority. Retrieved passages and historical summaries remain delimited evidence.
- Treat 128K/256K as requested token profiles. Admit the minimum proven route/model/account capacity minus output, tool and safety reserves. Report unknown or lower limits explicitly. Use route-appropriate token accounting with calibrated estimation; count tools and media. Byte budgets for stored summaries are separate.
- Keep one context lifecycle owner. Replace Hermes compression for migrated conversations and adapt OpenCode's context/compaction seam to educational content. Required compaction failure blocks an unsupported continuation rather than falling through to stock coding summaries.
- Start with summary compaction; native opaque checkpoints remain disabled. Reconstruct complete eligible recent exchanges from authoritative identities, replacing the upstream clipped/serialized tail without duplication. Validate the final assembled request after hooks and route changes. Prompt suppression alone does not prove erasure from persisted recent text or event history.
- First deliver educational compaction with exact history retrieval. Then add a versioned, derived summary tree and persisted view with zoom and reference search. The article's permanent append-only retention and summaries-as-truth rules are not adopted. Original retained history remains the source; summaries may omit information.
- Baseline acceptance includes exact older-range lookup and explicit unavailable/ineligible history. The tree is a later configurable strategy; it does not block baseline cutover. Enabling it requires its own recall, invalidation and paired-store restore acceptance.
- Summary nodes identify covered ranges and their dependency/retention epochs. A correction/deletion invalidates affected ancestors and views. Missing summaries preserve original input and expose readiness/failure; they do not disappear behind placeholders. Reconstruction is bounded derived work under the same model budget when generation is needed.
- Preserve stable prompt prefixes where compatible with correctness, but do not promise cache savings. Current instructions, source revisions, consent and revocation take precedence. Native provider checkpoints are only reused on compatible routes; otherwise reconstruct eligible history.

## Testing Decisions

- Test at the public domain/Harness interface using synthetic CKD, dialysis, transplantation and glomerular learning with exact values, units, citations and contradictions. Reuse existing memory, source-revision, temporary-retention and cross-module tests.
- Add post-completion correction and deletion capture regressions reproducing the identified stale recapture gap. Cover edit during generation, late capture, child output, derived summaries and restore under tombstones. Assert IDs, revisions, source lineage and absence of stale text.
- Execute actual Mem0/Qdrant/FastEmbed rebuild/recall tests using public pinned helper assets and synthetic profiles. Keep simulated generation, real engine behavior and real model quality claims separate.
- For long context, test saturated input, large tools/media, pending tool pairs, summary failure, restart, route changes and exact-history zoom. Compare reference-target recall and false recall across current compaction and tree-assisted profiles; include adversarial quoted instructions.
- Measure prompt overhead, summary requests, retrieval latency and reported cache use without assuming the article's simulations transfer. A token-counting fixture tests budgeting only; actual account requests establish usable 128K/256K limits.

## Out of Scope

Implementing the remaining planned memory/context slices in the initial H01/H24 batch; replacing the selected memory/index engines; a universal never-delete log; using generated summaries as scientific truth; claiming lossless semantic recall; or changing clinical content/review standards.

## Further Notes

See the [memory audit](../../../research/2026-10-10-opencode-integration/w1-02-memory.md) for actual engine tests and the reproduced gap. The [article/context memo](../../../research/2026-10-10-opencode-integration/parent-context.md) records the immutable article source, successful mathematical simulation and its limits. Design C retains authority for Archive, project membership and temporary/saved product behavior.
