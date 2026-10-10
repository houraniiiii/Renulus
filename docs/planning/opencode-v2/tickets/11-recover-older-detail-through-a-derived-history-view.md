# H11 — Recover older detail through a derived history view

**Status:** draft — review pending; implementation not authorised by this research request.

**Spec:** [S2](../specs/02-memory-context.md)

**Owner:** M1/M5 + F0

**Current source baseline:** `76cfdff23e259700bec820e174c200540c7c1e1b`. Reconcile later changes before implementation.

## What to build

The assistant can navigate a persisted summary tree or reference search to exact eligible historical detail without creating another transcript.

## Existing owner and delta

H10's authoritative transcript/history resolver; the tree is a derived optional context strategy. Preserve existing behavior and extend its integration boundary; do not recreate a landed producer.

## Acceptance criteria

- [ ] Store versioned range/dependency references and a persisted view; originals remain in the authoritative transcript.
- [ ] Zoom/search retrieves exact allowed detail; omitted summary clues can be found through lexical/reference lookup.
- [ ] Lagging or failed parents retain eligible children/raw ranges and expose readiness; no incomplete checkpoint is treated as complete.
- [ ] Corrections/deletions invalidate ancestors, views, snippets and model-visible history before reuse; temporary state remains volatile.
- [ ] Evaluate recall/false recall, overhead, latency and summary attempts across varied synthetic domains before enabling tree-driven context; do not claim the article's cache percentages.
- [ ] This is optional evaluated strategy adoption, not a default-cutover blocker. Before activation, extend the accepted H18 paired-store restore/delete matrix to tree nodes/views and pass recall gates.

## Blocked by

- [H10](10-continue-an-evidence-aware-128k-or-256k-conversation.md)
- [H18](18-delete-and-restore-a-consistent-migrated-learning-profile.md)

## Design C coordination

- DC04 history and context status

Preserve the canonical DC owner and acceptance in the [Design C spec](../../DESIGN_C_IMPLEMENTATION_SPEC.md). These are coordination/contract obligations, not a claim that landed DC tickets remain unimplemented. Review current integration leases before changing shared modules.

## Evidence and validation

[Focused evidence](../../../research/2026-10-10-opencode-integration/w2-04-context-integration.md); [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md). Exercise observable behavior through the existing public domain/conversation facade and shared Harness interface. Record scripted transport, real engine, real account and packaged acceptance separately. Existing failures remain open until the corresponding acceptance proves their resolution.
