# H14 — Explain deterministic reviewed-test results

**Status:** draft — review pending; implementation not authorised by this research request.

**Spec:** [S3](../specs/03-workflows-migration.md)

**Owner:** M4 + M5/F0

**Current source baseline:** `76cfdff23e259700bec820e174c200540c7c1e1b`. Reconcile later changes before implementation.

## What to build

A doctor receives an authoritative reviewed-test result and an optional model explanation that cannot change the score or learner evidence.

## Existing owner and delta

Current whole-attempt authority, deterministic results and active-Test assistance barriers. Preserve existing behavior and extend its integration boundary; do not recreate a landed producer.

## Acceptance criteria

- [ ] Compute results from pinned attempts without model transport; failure of explanation leaves numbers/review usable.
- [ ] Supply the narrative role only a key-free permitted aggregate with provenance and bounded output.
- [ ] Consume H02's existing active-Test/Study guard for aggregate-only explanations; H07/H09 extend their own paths. Narrative failure or forbidden help cannot alter deterministic results.
- [ ] Generated narrative cannot update marks, mastery, reviewed status or memory without an eligible domain event.
- [ ] Test answer/evidence transaction rollback, retries, forbidden help and explanation failure through the user flow.

## Blocked by

- [H03](03-use-the-selected-subscription-for-tools-and-images.md)
- [H04](04-adjust-roles-and-configuration-with-visible-activation.md)
- [H05](05-complete-a-learning-turn-whose-memory-stays-corrected.md)

## Design C coordination

- DC14 Test commitment; DC15 results/explanations

Preserve the canonical DC owner and acceptance in the [Design C spec](../../DESIGN_C_IMPLEMENTATION_SPEC.md). These are coordination/contract obligations, not a claim that landed DC tickets remain unimplemented. Review current integration leases before changing shared modules.

## Evidence and validation

[Focused evidence](../../../research/2026-10-10-opencode-integration/w2-03-workflows.md); [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md). Exercise observable behavior through the existing public domain/conversation facade and shared Harness interface. Record scripted transport, real engine, real account and packaged acceptance separately. Existing failures remain open until the corresponding acceptance proves their resolution.
