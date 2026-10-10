# H00 — Restore the existing saved-generation retrieval path

**Status:** draft — review pending; implementation not authorised by this research request.

**Spec:** [S3](../specs/03-workflows-migration.md)

**Owner:** M4 + integration

**Current source baseline:** `76cfdff23e259700bec820e174c200540c7c1e1b`. Reconcile later changes before implementation.

## What to build

An existing five-question request reaches its selected synthetic provider, validates its citations and publishes one saved test before execution is migrated.

## Existing owner and delta

Existing shared retrieval and SavedGenerationService; repair the caller guard mismatch before changing the execution owner. Preserve existing behavior and extend its integration boundary; do not recreate a landed producer.

## Acceptance criteria

- [ ] Reproduce the current guard_run mismatch through the public generation flow and retain its failing evidence.
- [ ] Give shared retrieval an explicit caller-supplied current-job/execution guard; preserve the legacy caller and reject stale work before/after retrieval. A no-op compatibility method is not accepted.
- [ ] Pass the existing five-question and source-revocation cases with real SQLite/domain validators and synthetic inference; prove one canonical publication.
- [ ] Rerun the exact current generation/nightly failures affected by this repair and report independent remaining failures without claiming downstream guards passed prematurely.
- [ ] Keep current checkpoint, retry, source/publication transaction and active-Test semantics; this is a small prerequisite repair, not a new generation subsystem.

## Blocked by

None — independent initial slice after planning approval.

## Design C coordination

- DC16 producer; shared legacy retrieval guard

Preserve the canonical DC owner and acceptance in the [Design C spec](../../DESIGN_C_IMPLEMENTATION_SPEC.md). These are coordination/contract obligations, not a claim that landed DC tickets remain unimplemented. Review current integration leases before changing shared modules.

## Evidence and validation

[Focused evidence](../../../research/2026-10-10-opencode-integration/w4-02-current-workflows.md); [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md). Exercise observable behavior through the existing public domain/conversation facade and shared Harness interface. Record scripted transport, real engine, real account and packaged acceptance separately. Existing failures remain open until the corresponding acceptance proves their resolution.
