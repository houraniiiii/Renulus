# H13 — Preserve existing 10- and 20-question checkpoints through OpenCode

**Status:** draft — review pending; implementation not authorised by this research request.

**Spec:** [S3](../specs/03-workflows-migration.md)

**Owner:** M4 + F0/integration

**Current source baseline:** `76cfdff23e259700bec820e174c200540c7c1e1b`. Reconcile later changes before implementation.

## What to build

The existing generated-test job retains its validated 10/20-question batches through interruption while OpenCode owns execution and explicit retry.

## Existing owner and delta

Existing generation checkpoints, explicit retry, total budgets and interrupted-job semantics. Preserve existing behavior and extend its integration boundary; do not recreate a landed producer.

## Acceptance criteria

- [ ] Reuse existing 2/4 five-item slots, retry/checkpoint contracts and cross-batch deduplication; add engine/attempt references without another job ledger.
- [ ] Reserve each outbound attempt once; a possibly sent request remains uncertain and is not automatically resent after restart.
- [ ] Reconcile runtime inbox/history and canonical receipts on lost acknowledgements without waking generation by replay alone.
- [ ] Fault-inject dispatch, commit, acknowledgement and final publication; cancel-first prevents late results and publication-first returns the saved test.
- [ ] Partial sets require explicitly accepted count; failure preserves useful batches and source provenance.

## Blocked by

- [H12](12-publish-one-validated-five-question-saved-test.md)

## Design C coordination

- DC16 larger sets and cancellation/recovery

Preserve the canonical DC owner and acceptance in the [Design C spec](../../DESIGN_C_IMPLEMENTATION_SPEC.md). These are coordination/contract obligations, not a claim that landed DC tickets remain unimplemented. Review current integration leases before changing shared modules.

## Evidence and validation

[Focused evidence](../../../research/2026-10-10-opencode-integration/w3-03-minimality-design-c.md); [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md). Exercise observable behavior through the existing public domain/conversation facade and shared Harness interface. Record scripted transport, real engine, real account and packaged acceptance separately. Existing failures remain open until the corresponding acceptance proves their resolution.
