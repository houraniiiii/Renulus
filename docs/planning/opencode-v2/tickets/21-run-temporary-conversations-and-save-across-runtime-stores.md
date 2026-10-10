# H21 — Run temporary conversations and save them across runtime stores

**Status:** draft — review pending; implementation not authorised by this research request.

**Spec:** [S1](../specs/01-harness-control.md), [S2](../specs/02-memory-context.md), [S3](../specs/03-workflows-migration.md)

**Owner:** M1/M3 + F0/integration

**Current source baseline:** `76cfdff23e259700bec820e174c200540c7c1e1b`. Reconcile later changes before implementation.

## What to build

A temporary conversation can use tools and bounded children, then either discard on disconnect or explicitly Save its eligible retained family once.

## Existing owner and delta

Current temporary/disconnect/Save and attachment semantics; extend only the cross-runtime transfer and volatile execution boundary. Preserve existing behavior and extend its integration boundary; do not recreate a landed producer.

## Acceptance criteria

- [ ] Use a separate in-memory runtime graph for the full temporary family, volatile attachments/tool spills and redacted diagnostics; test synthetic markers against persistent stores/new exports.
- [ ] Preserve temporary exclusion from Study recall/capture, disconnect cancellation/discard and saved-case eligibility; no durable temporary command payload/hash.
- [ ] Save freezes family admission and settles actual children/workers before staging an immutable retained manifest in a non-admitted persistent destination.
- [ ] Use a stable promotion ID and stage/map/activate/retire states; recheck policy/context/deletion before mapping and activation; replay without generation.
- [ ] Inject failure at each transition, including mapping before acknowledgement; preserve volatile originals while process lives, and clean orphaned staging before recovery/export.
- [ ] A hard process death may lose RAM; report the surviving committed state honestly and never promise volatile recovery.

## Blocked by

- [H06](06-continue-saved-and-temporary-chats-through-one-owner.md)
- [H07](07-delegate-a-bounded-evidence-review-and-stop-its-children.md)

## Design C coordination

- DC04 temporary/Save; DC02 retention; existing attachment ownership

Preserve the canonical DC owner and acceptance in the [Design C spec](../../DESIGN_C_IMPLEMENTATION_SPEC.md). These are coordination/contract obligations, not a claim that landed DC tickets remain unimplemented. Review current integration leases before changing shared modules.

## Evidence and validation

[Focused evidence](../../../research/2026-10-10-opencode-integration/w5-02-ipc-lifetimes.md); [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md). Exercise observable behavior through the existing public domain/conversation facade and shared Harness interface. Record scripted transport, real engine, real account and packaged acceptance separately. Existing failures remain open until the corresponding acceptance proves their resolution.
