# H09 — Use and revoke an explicitly connected MCP tool

**Status:** draft — review pending; implementation not authorised by this research request.

**Spec:** [S1](../specs/01-harness-control.md)

**Owner:** F0 + integration

**Current source baseline:** `76cfdff23e259700bec820e174c200540c7c1e1b`. Reconcile later changes before implementation.

## What to build

A user connects a selected MCP server, approves a scoped operation and can disable or revoke it with a defined in-flight outcome.

## Existing owner and delta

Current permission/scope/settings vocabulary; use native upstream MCP coordination with explicit policy adapters. Preserve existing behavior and extend its integration boundary; do not recreate a landed producer.

## Acceptance criteria

- [ ] Bind server endpoint/transport/tool-schema identity, current grants and payload digest to the operation.
- [ ] Exercise real Tool/Permission/MCP coordination with a counted synthetic server: approve, revoke while pending, reply once/always; require no stale dispatch or saved grant.
- [ ] Cover internal reconnect retries and adopted direct call paths; generic execute and Code Mode remain disabled initially.
- [ ] Disconnect, disable and credential removal have separate results; uncertain remote effects retain receipts and are not blindly resent.
- [ ] Cancellation reports settlement/uncertainty honestly; endpoint/schema changes invalidate old approvals.
- [ ] Extend H02's assistance guard to MCP dispatch and delayed results, including current Test/policy/context transitions.

## Blocked by

- [H04](04-adjust-roles-and-configuration-with-visible-activation.md)
- [H07](07-delegate-a-bounded-evidence-review-and-stop-its-children.md)

## Design C coordination

- DC10 connections/permission presentation

Preserve the canonical DC owner and acceptance in the [Design C spec](../../DESIGN_C_IMPLEMENTATION_SPEC.md). These are coordination/contract obligations, not a claim that landed DC tickets remain unimplemented. Review current integration leases before changing shared modules.

## Evidence and validation

[Focused evidence](../../../research/2026-10-10-opencode-integration/w2-05-configuration-revocation.md); [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md). Exercise observable behavior through the existing public domain/conversation facade and shared Harness interface. Record scripted transport, real engine, real account and packaged acceptance separately. Existing failures remain open until the corresponding acceptance proves their resolution.
