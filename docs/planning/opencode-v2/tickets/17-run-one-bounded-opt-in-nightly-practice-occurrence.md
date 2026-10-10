# H17 — Adapt the existing nightly occurrence to OpenCode execution

**Status:** draft — review pending; implementation not authorised by this research request.

**Spec:** [S3](../specs/03-workflows-migration.md)

**Owner:** M4/M6 + integration

**Current source baseline:** `76cfdff23e259700bec820e174c200540c7c1e1b`. Reconcile later changes before implementation.

## What to build

Existing NightlyService submits its bounded opted-in occurrence through the harness and keeps its established occurrence and explicit-retry authority.

## Existing owner and delta

Existing NightlyService occurrence ledger and generation producer; preserve default-off/app-running semantics. Preserve existing behavior and extend its integration boundary; do not recreate a landed producer.

## Acceptance criteria

- [ ] Reuse NightlyService, off by default and app-running; adapt submission to the same generation operation and budget as foreground work, without another scheduler.
- [ ] Persist stable profile/purpose/local-date identity, timezone/due-time evidence and consumed frontier.
- [ ] Settings/input changes, DST, timezone changes and clock rollback cannot create duplicate daily work.
- [ ] Preserve latest-due sleep catch-up and future-only cold restart; reconcile claim-before-submit without duplicate keyed jobs. Disable fences pending dispatch and publication.
- [ ] Preserve completed batches and require explicit recovery for uncertain generation; no new background OS service.

## Blocked by

- [H13](13-resume-10-and-20-question-generation-without-duplicate-work.md)

## Design C coordination

- DC19 scheduling and catch-up

Preserve the canonical DC owner and acceptance in the [Design C spec](../../DESIGN_C_IMPLEMENTATION_SPEC.md). These are coordination/contract obligations, not a claim that landed DC tickets remain unimplemented. Review current integration leases before changing shared modules.

## Evidence and validation

[Focused evidence](../../../research/2026-10-10-opencode-integration/w3-03-minimality-design-c.md); [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md). Exercise observable behavior through the existing public domain/conversation facade and shared Harness interface. Record scripted transport, real engine, real account and packaged acceptance separately. Existing failures remain open until the corresponding acceptance proves their resolution.
