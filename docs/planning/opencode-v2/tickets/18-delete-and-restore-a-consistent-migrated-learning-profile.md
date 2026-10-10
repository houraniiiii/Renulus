# H18 — Delete and restore a consistent migrated learning profile

**Status:** draft — review pending; implementation not authorised by this research request.

**Spec:** [S2](../specs/02-memory-context.md), [S3](../specs/03-workflows-migration.md)

**Owner:** Integration + F0 + M1/M2/M5

**Current source baseline:** `76cfdff23e259700bec820e174c200540c7c1e1b`. Reconcile later changes before implementation.

## What to build

A user deletes scoped data or restores a paired runtime/domain backup covering every migrated default producer, without resurrecting suppressed learning or breaking shared originals.

## Existing owner and delta

Current schema-2 compatibility, typed relations, recovery barrier, suppression and restore capture barrier. Preserve existing behavior and extend its integration boundary; do not recreate a landed producer.

## Acceptance criteria

- [ ] Define direct deletion, chat deletion, delete-related-learning, Archive and project membership separately.
- [ ] Extend existing typed dependency/ownership/restore relations; independent retained/edited facts survive under valid support. H05's M5/integration owner governs shared support schema.
- [ ] Consume the paired-store manifest/identity contract established in H01 and migration in H06; extend the current recovery barrier and schema-2 converter to a quiescent complete-generation snapshot.
- [ ] Restore applies current suppression/correction/deletion before activating indexes, views or recovery; missing current ledger is explicitly quarantined.
- [ ] Prove erasure/invalidation across transcripts, recent tails, children, summaries, events and indexes at the required scope; rollback never dual-writes or opens an incompatible newer schema.
- [ ] Consume H05 lineage, H06 receipt erasure and H21 promotion proofs; implement only the paired-store adapter/integrated matrix here. Include Home/nightly, imports and fictionalisation. Tree coverage is added by H11 before that strategy is enabled.
- [ ] Close admission with a logical lease and drain remote workers before acquiring recovery engine guards; no cross-process waits inside transactions/physical recovery locks. Abort snapshot/handoff on unsettled workers instead of releasing ownership after timeout.

## Blocked by

- [H09](09-use-and-revoke-an-explicitly-connected-mcp-tool.md)
- [H10](10-continue-an-evidence-aware-128k-or-256k-conversation.md)
- [H14](14-explain-deterministic-reviewed-test-results.md)
- [H15](15-generate-daily-suggestions-from-eligible-learning.md)
- [H16](16-produce-a-dated-updates-digest-without-altering-source-review.md)
- [H17](17-run-one-bounded-opt-in-nightly-practice-occurrence.md)
- [H22](22-route-explicit-fictional-test-preparation-through-the-harness.md)
- [H23](23-route-imported-test-refinement-through-the-harness.md)

## Design C coordination

- DC02 typed relations; DC20 populated migration/restore

Preserve the canonical DC owner and acceptance in the [Design C spec](../../DESIGN_C_IMPLEMENTATION_SPEC.md). These are coordination/contract obligations, not a claim that landed DC tickets remain unimplemented. Review current integration leases before changing shared modules.

## Evidence and validation

[Focused evidence](../../../research/2026-10-10-opencode-integration/w3-01-migration-retention.md); [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md). Exercise observable behavior through the existing public domain/conversation facade and shared Harness interface. Record scripted transport, real engine, real account and packaged acceptance separately. Existing failures remain open until the corresponding acceptance proves their resolution.
