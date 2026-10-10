# H23 — Route imported-test refinement through the harness

**Status:** draft — review pending; implementation not authorised by this research request.

**Spec:** [S3](../specs/03-workflows-migration.md)

**Owner:** M4 + M2/F0

**Current source baseline:** `76cfdff23e259700bec820e174c200540c7c1e1b`. Reconcile later changes before implementation.

## What to build

A user imports a test, receives bounded model refinement through the selected route, edits unresolved material and publishes one eligible saved version.

## Existing owner and delta

Existing import/refinement service, edit/resolve and SavedTestRepository publication. Preserve existing behavior and extend its integration boundary; do not recreate a landed producer.

## Acceptance criteria

- [ ] Adapt the existing import/refinement producer and test-import purpose; preserve format extraction, provenance, unresolved states and edit/resolve behavior.
- [ ] Use the existing validator and canonical SavedTestRepository transaction; generated refinement cannot silently promote content into reviewed-bank status.
- [ ] Bind route/configuration, current source/policy/context revisions and shared attempt limits; unsupported input and authentication failure remain visible.
- [ ] Exercise Stop, bounded explicit retry, revoked source, failed refinement and lost publication acknowledgement without duplicate effects.
- [ ] Keep original source ownership and deterministic assessment results unchanged; assert active-Test/Study assistance and key-privacy boundaries.

## Blocked by

- [H04](04-adjust-roles-and-configuration-with-visible-activation.md)

## Design C coordination

- DC17 import/refine; DC12 saved versions

Preserve the canonical DC owner and acceptance in the [Design C spec](../../DESIGN_C_IMPLEMENTATION_SPEC.md). These are coordination/contract obligations, not a claim that landed DC tickets remain unimplemented. Review current integration leases before changing shared modules.

## Evidence and validation

[Focused evidence](../../../research/2026-10-10-opencode-integration/w5-01-ticket-review.md); [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md). Exercise observable behavior through the existing public domain/conversation facade and shared Harness interface. Record scripted transport, real engine, real account and packaged acceptance separately. Existing failures remain open until the corresponding acceptance proves their resolution.
