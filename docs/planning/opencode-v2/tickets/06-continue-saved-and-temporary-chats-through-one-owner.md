# H06 — Migrate and delete one saved conversation through a single owner

**Status:** bounded implementation released after local H02/H05 acceptance. The [H02–H08 ledger](../../../implementation/OPENCODE_H02_H08_HANDOFF.md) records canonical/native migration leases; connected migration/deletion acceptance remains open. Temporary execution and cross-store Save remain H21.

**Spec:** [S2](../specs/02-memory-context.md), [S3](../specs/03-workflows-migration.md)

**Owner:** M1/M3 coordinated + F0/integration

**Current source baseline:** `76cfdff23e259700bec820e174c200540c7c1e1b`. Reconcile later changes before implementation.

## What to build

A user reopens an existing saved chat, continues it through OpenCode, and can delete it without orphaned transcript writers or retained command payloads.

## Existing owner and delta

Current saved ConversationRepository/ConversationStreams, command receipts, sidecars and read-only legacy history. Preserve existing behavior and extend its integration boundary; do not recreate a landed producer.

## Acceptance criteria

- [ ] Migrate saved history with repeatable stable mappings and the H01 paired-store contract; no generation or dual writable transcripts during conversion.
- [ ] Preserve ConversationStreams/sidecar identity, Archive, project membership, drafts, saved-disconnect continuation and explicit Stop; neutral status remains usable under active Test.
- [ ] Retain read-only legacy history/citations; unknown lineage is ineligible for automatic capture/context until checked.
- [ ] Delete owners and retire payload-bearing command receipts transactionally, including creation receipts targeting new through their result owner; new exports exclude deleted payloads/digests.
- [ ] Replay a retired command returns terminal-unavailable via an opaque tombstone, never repeats effects; legacy orphaned running receipts remain interrupted.
- [ ] Keep temporary conversations on their existing execution owner until H21 passes; do not claim this saved-only slice proves volatile runtime isolation or cross-store Save.

## Blocked by

- [H02](02-answer-with-an-eligible-library-passage.md)
- [H05](05-complete-a-learning-turn-whose-memory-stays-corrected.md)

## Design C coordination

- DC02 migrations; DC03 shell when desktop-integrated; DC04 conversation ownership; DC05 project identity

Preserve the canonical DC owner and acceptance in the [Design C spec](../../DESIGN_C_IMPLEMENTATION_SPEC.md). These are coordination/contract obligations, not a claim that landed DC tickets remain unimplemented. Review current integration leases before changing shared modules.

## Evidence and validation

[Focused evidence](../../../research/2026-10-10-opencode-integration/w4-03-current-conversations.md); [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md). Exercise observable behavior through the existing public domain/conversation facade and shared Harness interface. Record scripted transport, real engine, real account and packaged acceptance separately. Existing failures remain open until the corresponding acceptance proves their resolution.
