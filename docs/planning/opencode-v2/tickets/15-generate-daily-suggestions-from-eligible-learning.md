# H15 — Route existing daily suggestions and Quick practice through the harness

**Status:** draft — review pending; implementation not authorised by this research request.

**Spec:** [S3](../specs/03-workflows-migration.md)

**Owner:** M6/M1 + M4/M5

**Current source baseline:** `76cfdff23e259700bec820e174c200540c7c1e1b`. Reconcile later changes before implementation.

## What to build

Existing Home actions request their daily three-by-five bundle through the configured purpose, and Quick practice keeps the existing canonical five-question producer.

## Existing owner and delta

Existing HomeService suggestions, input/cache invalidation and Quick practice path. Preserve existing behavior and extend its integration boundary; do not recreate a landed producer.

## Acceptance criteria

- [ ] Preserve existing global Home inputs from eligible observations/goals, excluding temporary/case data; project-specific suggestions remain a separate extension.
- [ ] Adapt existing HomeService purpose/cache/invalidation behavior to the harness; validate the full bundle atomically and preserve recorded inputs/day.
- [ ] Opening or selecting a suggestion does not create learner-performance evidence.
- [ ] Failure retains a still-eligible prior bundle or a clear empty state; correction/revocation invalidates affected cached entries.
- [ ] Quick practice references the same saved-test identity as Tests and chat.

## Blocked by

- [H05](05-complete-a-learning-turn-whose-memory-stays-corrected.md)
- [H12](12-publish-one-validated-five-question-saved-test.md)

## Design C coordination

- DC06 home actions; DC13 Study; DC16 Quick practice

Preserve the canonical DC owner and acceptance in the [Design C spec](../../DESIGN_C_IMPLEMENTATION_SPEC.md). These are coordination/contract obligations, not a claim that landed DC tickets remain unimplemented. Review current integration leases before changing shared modules.

## Evidence and validation

[Focused evidence](../../../research/2026-10-10-opencode-integration/w3-03-minimality-design-c.md); [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md). Exercise observable behavior through the existing public domain/conversation facade and shared Harness interface. Record scripted transport, real engine, real account and packaged acceptance separately. Existing failures remain open until the corresponding acceptance proves their resolution.
