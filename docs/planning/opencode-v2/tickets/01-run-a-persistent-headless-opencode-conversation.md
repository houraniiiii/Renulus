# H01 — Run a persistent headless OpenCode conversation

**Status:** draft — review pending; implementation not authorised by this research request.

**Spec:** [S1](../specs/01-harness-control.md)

**Owner:** F0 + integration

**Current source baseline:** `76cfdff23e259700bec820e174c200540c7c1e1b`. Reconcile later changes before implementation.

## What to build

A client submits a synthetic learning request to the pinned, managed OpenCode host, observes its result, closes and reopens it with the same execution identity.

## Existing owner and delta

Current Windows supervisor and design-c/1 identity/store contracts; this is the first runtime proof, not a replacement app. Preserve existing behavior and extend its integration boundary; do not recreate a landed producer.

## Acceptance criteria

- [ ] Build one coherent source/dependency cohort and record hashes/licences; developer tools are absent from the delivered host PATH.
- [ ] Exercise the real SDK loop, durable store and observation interface with a counting scripted model; reopen preserves the transcript without generation.
- [ ] Required policy is installed before any dispatch/recovery; waiting for readiness cannot deadlock host construction.
- [ ] Reject a second owner of the same store; bound shutdown's drain attempt. Release ownership only after actual host/worker settlement; timeout preserves blocked/uncertain handoff rather than reporting success.
- [ ] Record unresolved native dependencies, selective recovery defer and packaging behavior as failures, never simulated passes.
- [ ] Extend landed store/command contracts with engine identities and a versioned paired-store manifest before any migration writes; preserve existing schema-2 conversion.
- [ ] Delayed recovery opens only under proven admission/child-ownership quiescence; a held uncertain session remains resumable without clearing fresh claims.
- [ ] Bind IPC requests/replies to process generation and operation/attempt/request IDs; reserve control capacity under queue saturation, reject stale replies, and never treat an observation timeout as permission to resend.
- [ ] Distinguish rejected-before-admission, accepted/pending, committed-reference, cancelled/settled and uncertain-after-disconnect. Do not drop command replies under observation's drop-oldest policy.
- [ ] Prohibit all cross-process waits inside canonical transactions and conversation/case/recovery physical locks. Close admission with a logical lease, drain remote work before engine guards, and validate publication locally.

## Blocked by

None — independent initial slice after planning approval.

## Design C coordination

- DC02 shared identity and scope vocabulary

Preserve the canonical DC owner and acceptance in the [Design C spec](../../DESIGN_C_IMPLEMENTATION_SPEC.md). These are coordination/contract obligations, not a claim that landed DC tickets remain unimplemented. Review current integration leases before changing shared modules.

## Evidence and validation

[Focused evidence](../../../research/2026-10-10-opencode-integration/w2-02-dispatch-recovery.md); [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md). Exercise observable behavior through the existing public domain/conversation facade and shared Harness interface. Record scripted transport, real engine, real account and packaged acceptance separately. Existing failures remain open until the corresponding acceptance proves their resolution.
