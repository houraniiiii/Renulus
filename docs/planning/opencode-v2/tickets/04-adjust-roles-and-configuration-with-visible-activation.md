# H04 — Adjust roles and configuration with visible activation

**Status:** local acceptance verified on 2026-10-11. Authority/budgets, actual managed bootstrap/reopen, hidden Settings stage/activate/reopen and actual failure/crash reconciliation are mapped in the [acceptance record](../../../implementation/OPENCODE_H03_H04_ACCEPTANCE_MAP.md) and [desktop journey](../../../implementation/OPENCODE_H04_HIDDEN_SETTINGS.md). Native auxiliary enablement, account and package gates retain their separate scope.

**Spec:** [S1](../specs/01-harness-control.md)

**Owner:** F0 + integration

**Current source baseline:** `76cfdff23e259700bec820e174c200540c7c1e1b`. Reconcile later changes before implementation.

## What to build

A profile owner changes a purpose model or capability setting, sees the effective revision and can recover a failed change without partial activation.

## Existing owner and delta

Current connection/catalog owner and Settings; add one versioned activation boundary. Preserve existing behavior and extend its integration boundary; do not recreate a landed producer.

## Acceptance criteria

- [x] Stage immutable inputs, hashes, credential references and purpose/context/attempt policies; show requested versus effective revision.
- [x] Validate a candidate with generation/recovery/package acquisition/external MCP startup closed and no second live-store writer.
- [x] Activate only the effective healthy registry after all transforms; crashed/failed activation reconciles to a known state.
- [x] Existing runs retain pinned versions; explicit migration widens access only deliberately, while revocations immediately narrow all affected work.
- [x] Exercise title/repair/transport/recovery attempts through a shared durable budget; deterministic degradation and configured retries remain distinct.
- [x] Begin with restart-based activation; busy-run changes retain the pinned version or use explicit cancellation/migration. Reuse the existing connection catalog and expose no parallel selector.
- [x] Use the plan's explicitly proposed numeric dispatch/output/child bounds; distinguish tool-continuation steps from retries. Disabled roles precede overrides; Automatic follows allowlist order filtered by catalogue membership, then the first allowed ID.
- [x] F0 plus each consuming domain owner records role-fixture comparisons before specialized defaults; inheritance is not a model-quality ranking.

## Blocked by

- [H01](01-run-a-persistent-headless-opencode-conversation.md)
- [H03](03-use-the-selected-subscription-for-tools-and-images.md)

## Design C coordination

- DC10 settings integration

Preserve the canonical DC owner and acceptance in the [Design C spec](../../DESIGN_C_IMPLEMENTATION_SPEC.md). These are coordination/contract obligations, not a claim that landed DC tickets remain unimplemented. Review current integration leases before changing shared modules.

## Evidence and validation

[Focused evidence](../../../research/2026-10-10-opencode-integration/w2-05-configuration-revocation.md); [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md). Exercise observable behavior through the existing public domain/conversation facade and shared Harness interface. Record scripted transport, real engine, real account and packaged acceptance separately. Existing failures remain open until the corresponding acceptance proves their resolution.
