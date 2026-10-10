# H24 — Keep memory-worker ownership until extraction actually settles

**Status:** complete for the local H24 settlement scope — implemented and verified on October 10, 2026, through production checkpoint `756c8ebc`. See the [implementation handoff](../../../implementation/OPENCODE_FOUNDATIONS_HANDOFF.md). Memory lineage, quality and complete paired restore remain H05/H18.

**Spec:** [S2](../specs/02-memory-context.md), [S3](../specs/03-workflows-migration.md)

**Owner:** M5 + F0/integration

**Implementation baseline:** `c2bd896420fb88f76d63ca576414dbbba182f4c2` (final Design C handoff). The original research used `76cfdff23e259700bec820e174c200540c7c1e1b`; H00 is already consumed in the implementation baseline.

**Accepted test seams:** existing public domain/conversation commands and the shared Harness facade, with actual local state/validators and counting synthetic inference where relevant. The owner's [implementation instruction](../../2026-10-04-user-answers.md#october-10-first-opencode-foundation-implementation-authorisation) accepts the planned seams; no new approval or tracker publication is needed. Use one behavioural failing test then minimal implementation per cycle in the isolated foundation worktree.

## What to build

Stopping or closing a memory capture either settles the actual extraction worker or visibly blocks store handoff until it does.

## Existing owner and delta

Existing MemoryService extraction thread, active-run bookkeeping and recovery guard; repair lifetime accounting. Preserve existing behavior and extend its integration boundary; do not recreate a landed producer.

## Acceptance criteria

- [x] Reproduce close returning while the controlled extraction thread still runs; distinguish coroutine cancellation from actual worker/finalizer settlement.
- [x] Keep an outstanding worker lease across cancellation until the thread and its cleanup finish; retain existing worker/engine architecture.
- [x] Close admission, request cancellation, keep event-loop/reply capacity available and drain within a defined bound before releasing engine/store ownership.
- [x] A timeout leaves recovery/restore/owner handoff blocked or explicitly uncertain; it must not report an empty active set as proof of settlement.
- [x] Release a controlled worker after cancellation and prove no late publication; exercise normal completion, close, recovery guard and bounded timeout with synthetic profiles.

## Blocked by

None — authorised independent initial slice from `c2bd8964`.

## Design C coordination

- Existing M5 worker and F0/integration recovery boundary

Preserve the canonical DC owner and acceptance in the [Design C spec](../../DESIGN_C_IMPLEMENTATION_SPEC.md). These are coordination/contract obligations, not a claim that landed DC tickets remain unimplemented. Review current integration leases before changing shared modules.

## Evidence and validation

[Focused evidence](../../../research/2026-10-10-opencode-integration/w5-02-ipc-lifetimes.md); [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md). Exercise observable behavior through the existing public domain/conversation facade and shared Harness interface. Record scripted transport, real engine, real account and packaged acceptance separately. Existing failures remain open until the corresponding acceptance proves their resolution.

The [implementation ledger](../../../implementation/opencode-foundations-h24.md)
preserves each failing tracer and repair, including admitted HTTP ownership,
producer admission closure, provider callback ordering and repeated close after
event-loop teardown. The final focused run passed 34 cases; the separately
reconciled affected set and broad-suite failures are recorded there with exact
receipt ownership. [Hidden UI run 07](../../../implementation/opencode-foundations-ui.md)
also passed ordinary startup/shutdown on the final production bytes with no
forced or remaining owned processes. Normal UI close does not exercise the
controlled uncooperative-worker timeout, which has its own service tests.
