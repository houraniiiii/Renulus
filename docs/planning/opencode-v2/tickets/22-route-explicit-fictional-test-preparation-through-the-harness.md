# H22 — Route explicit fictional-test preparation through the harness

**Status:** draft — review pending; implementation not authorised by this research request.

**Spec:** [S3](../specs/03-workflows-migration.md)

**Owner:** M4 + M1/M3/F0

**Current source baseline:** `76cfdff23e259700bec820e174c200540c7c1e1b`. Reconcile later changes before implementation.

## What to build

A user explicitly prepares fictional practice from temporary material, reviews the eligible result and publishes one canonical saved test through the existing flow.

## Existing owner and delta

Existing fictionalisation, ChatTestService, review and fictional-artifact publication. Preserve existing behavior and extend its integration boundary; do not recreate a landed producer.

## Acceptance criteria

- [ ] Adapt existing fictionalisation/chat-test services and fictional-test purpose; keep raw preparation and engine family volatile.
- [ ] Preserve current validation, review/edit and trusted fictional-artifact publication; no raw temporary input becomes ordinary durable generation input.
- [ ] Bind role/configuration, parent permits, policy/context and source identities; disabled roles and active-Test restrictions block dispatch/disclosure.
- [ ] Stop, route failure and explicit retry preserve existing user-visible semantics and do not reset spent permits or duplicate a saved version.
- [ ] Test temporary sentinels, failed validation, late revocation, lost acknowledgement and matching chat/Tests references through the existing facade.

## Blocked by

- [H04](04-adjust-roles-and-configuration-with-visible-activation.md)
- [H21](21-run-temporary-conversations-and-save-across-runtime-stores.md)

## Design C coordination

- DC18 chat-test/fictionalisation producer; DC12 saved versions

Preserve the canonical DC owner and acceptance in the [Design C spec](../../DESIGN_C_IMPLEMENTATION_SPEC.md). These are coordination/contract obligations, not a claim that landed DC tickets remain unimplemented. Review current integration leases before changing shared modules.

## Evidence and validation

[Focused evidence](../../../research/2026-10-10-opencode-integration/w5-01-ticket-review.md); [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md). Exercise observable behavior through the existing public domain/conversation facade and shared Harness interface. Record scripted transport, real engine, real account and packaged acceptance separately. Existing failures remain open until the corresponding acceptance proves their resolution.
