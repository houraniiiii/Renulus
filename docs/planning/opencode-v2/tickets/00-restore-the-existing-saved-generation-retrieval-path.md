# H00 — Restore the existing saved-generation retrieval path

**Status:** existing-product prerequisite completed in the separately authorised Design C closeout — `fa3b590cd40de145c198a64168aa46b82384e2bc`. H12 consumes this repair; do not implement it twice. H01/H24's later implementation authorisation is separate from this completed repair.

The original uncommitted planning snapshot is retained in documentation commit
`75b4b503085b3592d89f5114b282073847b2159d`. See the
[current integration handoff](../../../implementation/DESIGN_C_OPENCODE_HANDOFF.md#final-closeout-evidence-and-review-launch)
for exact red/green receipts, affected 160+1 cases, full App producer recheck and
the stale fixture/cleanup qualifications.

**Spec:** [S3](../specs/03-workflows-migration.md)

**Owner:** M4 + integration

**Research baseline:** `76cfdff23e259700bec820e174c200540c7c1e1b` reproduced the defect. **Foundation baseline:** `c2bd896420fb88f76d63ca576414dbbba182f4c2` includes the repair and final Design C App evidence. The [dated reconciliation](../../../research/2026-10-10-opencode-integration/h00-handoff-reconciliation.md) retains its preliminary receipts and adds a subsequent final-closeout note; its earlier pending-App wording is historical.

## What to build

Historical scope, now consumed: an existing five-question request reaches its selected synthetic provider, validates its citations and publishes one saved test before execution is migrated. H12 preserves this repaired authority when adapting execution.

## Existing owner and delta

Existing shared retrieval and SavedGenerationService; repair the caller guard mismatch before changing the execution owner. Preserve existing behavior and extend its integration boundary; do not recreate a landed producer.

## Acceptance criteria

- [x] Reproduce the current guard_run mismatch through the public generation flow and retain its failing evidence.
- [x] Give shared retrieval an explicit caller-supplied current-job/execution guard; preserve the legacy caller and reject stale work before/after retrieval. A no-op compatibility method is not accepted.
- [x] Pass the existing five-question and source-revocation cases with real SQLite/domain validators and synthetic inference; prove one canonical publication.
- [x] Rerun the affected generation/nightly/legacy inventory: 160 passed plus the corrected missing-owner fixture passed, covering 161 unique cases across runs, not one full-green affected run. The subsequent App producer rerun passed 2/2 with clean shutdown as separately recorded in the final handoff.
- [x] Keep current checkpoint, retry, source/publication transaction and active-Test semantics; this is a small prerequisite repair, not a new generation subsystem.

## Blocked by

None — completed and consumed at `fa3b590c`, included in `c2bd8964`; no duplicate implementation work.

## Design C coordination

- DC16 producer; shared legacy retrieval guard

Preserve the canonical DC owner and acceptance in the [Design C spec](../../DESIGN_C_IMPLEMENTATION_SPEC.md). These are coordination/contract obligations, not a claim that landed DC tickets remain unimplemented. Review current integration leases before changing shared modules.

## Evidence and validation

[Focused evidence](../../../research/2026-10-10-opencode-integration/w4-02-current-workflows.md); [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md). Exercise observable behavior through the existing public domain/conversation facade and shared Harness interface. Record scripted transport, real engine, real account and packaged acceptance separately. Existing failures remain open until the corresponding acceptance proves their resolution.
