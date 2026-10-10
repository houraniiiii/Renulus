# H10 — Continue an evidence-aware 128K or 256K conversation

**Status:** draft — review pending; implementation not authorised by this research request.

**Spec:** [S2](../specs/02-memory-context.md)

**Owner:** F0 + M1/M5

**Current source baseline:** `76cfdff23e259700bec820e174c200540c7c1e1b`. Reconcile later changes before implementation.

## What to build

A long learning conversation uses its supported context profile, compacts educationally and continues with exact eligible recent exchanges and evidence.

## Existing owner and delta

Existing educational invariants and publication/context epochs; OpenCode takes over the migrated context lifecycle. Preserve existing behavior and extend its integration boundary; do not recreate a landed producer.

## Acceptance criteria

- [ ] Define requested decimal token ceilings and effective route/account limits; unknown/lower support is visible.
- [ ] Check final assembled input, tool schemas/media, output and reserves after hooks, route changes and history expansion.
- [ ] Use educational supplied summaries with validated readiness; stock coding summary fallback and native opaque checkpoints remain disabled.
- [ ] Reconstruct recent tool-call/result pairs and media markers from authoritative IDs without duplicated clipped tails; preserve unresolved calls.
- [ ] Test saturation, empty/failed summary, correction during preparation, instruction reacquisition and same-provider route expansion; actual model-window acceptance remains separately evidenced.
- [ ] Expose exact older-range/reference lookup after compaction with explicit ineligible/unavailable results; this baseline history resolver does not depend on the optional H11 tree.
- [ ] Use the shared H03/H04 admission fixture to test final input/output caps for auxiliary requests as well as main requests; one shared parent permit pool covers continuations and summaries.

## Blocked by

- [H03](03-use-the-selected-subscription-for-tools-and-images.md)
- [H05](05-complete-a-learning-turn-whose-memory-stays-corrected.md)
- [H06](06-continue-saved-and-temporary-chats-through-one-owner.md)
- [H08](08-apply-versioned-instructions-and-skills-to-a-learning-task.md)
- [H21](21-run-temporary-conversations-and-save-across-runtime-stores.md)

## Design C coordination

- DC04 context status and failure presentation

Preserve the canonical DC owner and acceptance in the [Design C spec](../../DESIGN_C_IMPLEMENTATION_SPEC.md). These are coordination/contract obligations, not a claim that landed DC tickets remain unimplemented. Review current integration leases before changing shared modules.

## Evidence and validation

[Focused evidence](../../../research/2026-10-10-opencode-integration/w2-04-context-integration.md); [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md). Exercise observable behavior through the existing public domain/conversation facade and shared Harness interface. Record scripted transport, real engine, real account and packaged acceptance separately. Existing failures remain open until the corresponding acceptance proves their resolution.
