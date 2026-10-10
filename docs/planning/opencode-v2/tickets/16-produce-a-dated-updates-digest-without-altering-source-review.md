# H16 — Produce a dated Updates digest without altering source review

**Status:** draft — review pending; implementation not authorised by this research request.

**Spec:** [S3](../specs/03-workflows-migration.md)

**Owner:** M7 + M2/F0

**Current source baseline:** `76cfdff23e259700bec820e174c200540c7c1e1b`. Reconcile later changes before implementation.

## What to build

A user sees deterministic source-change checks and an optional generated digest tied to the exact observed revisions.

## Existing owner and delta

Current source checks, outbox and explicit review status; generated interpretation is a separate purpose. Preserve existing behavior and extend its integration boundary; do not recreate a landed producer.

## Acceptance criteria

- [ ] Retain current source/link/metadata checking, outbox acknowledgements and review authority.
- [ ] An explicitly enabled digest uses one purpose budget and source-revision identity; retries of deterministic checks do not become generation retries.
- [ ] Show retrieval failure, edition/currentness and digest provenance separately; generation cannot mark guidance reviewed.
- [ ] Revocation or revision changes before publication block stale digest output.
- [ ] Replayed delivery preserves one update/digest identity and no duplicate memory/progress events.

## Blocked by

- [H02](02-answer-with-an-eligible-library-passage.md)
- [H04](04-adjust-roles-and-configuration-with-visible-activation.md)

## Design C coordination

- DC10 Updates integration

Preserve the canonical DC owner and acceptance in the [Design C spec](../../DESIGN_C_IMPLEMENTATION_SPEC.md). These are coordination/contract obligations, not a claim that landed DC tickets remain unimplemented. Review current integration leases before changing shared modules.

## Evidence and validation

[Focused evidence](../../../research/2026-10-10-opencode-integration/w2-03-workflows.md); [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md). Exercise observable behavior through the existing public domain/conversation facade and shared Harness interface. Record scripted transport, real engine, real account and packaged acceptance separately. Existing failures remain open until the corresponding acceptance proves their resolution.
