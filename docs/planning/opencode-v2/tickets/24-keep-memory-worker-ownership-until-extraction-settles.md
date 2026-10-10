# H24 — Keep memory-worker ownership until extraction actually settles

**Status:** draft — review pending; implementation not authorised by this research request.

**Spec:** [S2](../specs/02-memory-context.md), [S3](../specs/03-workflows-migration.md)

**Owner:** M5 + F0/integration

**Current source baseline:** `76cfdff23e259700bec820e174c200540c7c1e1b`. Reconcile later changes before implementation.

## What to build

Stopping or closing a memory capture either settles the actual extraction worker or visibly blocks store handoff until it does.

## Existing owner and delta

Existing MemoryService extraction thread, active-run bookkeeping and recovery guard; repair lifetime accounting. Preserve existing behavior and extend its integration boundary; do not recreate a landed producer.

## Acceptance criteria

- [ ] Reproduce close returning while the controlled extraction thread still runs; distinguish coroutine cancellation from actual worker/finalizer settlement.
- [ ] Keep an outstanding worker lease across cancellation until the thread and its cleanup finish; retain existing worker/engine architecture.
- [ ] Close admission, request cancellation, keep event-loop/reply capacity available and drain within a defined bound before releasing engine/store ownership.
- [ ] A timeout leaves recovery/restore/owner handoff blocked or explicitly uncertain; it must not report an empty active set as proof of settlement.
- [ ] Release a controlled worker after cancellation and prove no late publication; exercise normal completion, close, recovery guard and bounded timeout with synthetic profiles.

## Blocked by

None — independent initial slice after planning approval.

## Design C coordination

- Existing M5 worker and F0/integration recovery boundary

Preserve the canonical DC owner and acceptance in the [Design C spec](../../DESIGN_C_IMPLEMENTATION_SPEC.md). These are coordination/contract obligations, not a claim that landed DC tickets remain unimplemented. Review current integration leases before changing shared modules.

## Evidence and validation

[Focused evidence](../../../research/2026-10-10-opencode-integration/w5-02-ipc-lifetimes.md); [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md). Exercise observable behavior through the existing public domain/conversation facade and shared Harness interface. Record scripted transport, real engine, real account and packaged acceptance separately. Existing failures remain open until the corresponding acceptance proves their resolution.
