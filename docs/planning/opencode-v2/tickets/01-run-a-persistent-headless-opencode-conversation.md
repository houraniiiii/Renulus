# H01 — Run a persistent headless OpenCode conversation

**Status:** complete for the local H01 foundation scope — implemented and verified on October 10, 2026, principally in `b5101da0`. Production account adapters, client migration and packaged acceptance remain later tickets. See the [implementation handoff](../../../implementation/OPENCODE_FOUNDATIONS_HANDOFF.md).

**Spec:** [S1](../specs/01-harness-control.md)

**Owner:** F0 + integration

**Implementation baseline:** `c2bd896420fb88f76d63ca576414dbbba182f4c2` (final Design C handoff). The original research used `76cfdff23e259700bec820e174c200540c7c1e1b`; H00 is already consumed in the implementation baseline.

**Accepted test seams:** existing public domain/conversation commands and the shared Harness facade, with actual local state/validators and counting synthetic inference where relevant. The owner's [implementation instruction](../../2026-10-04-user-answers.md#october-10-first-opencode-foundation-implementation-authorisation) accepts the planned seams; no new approval or tracker publication is needed. Use one behavioural failing test then minimal implementation per cycle in the isolated foundation worktree.

## What to build

A client submits a synthetic learning request to the pinned, managed OpenCode host, observes its result, closes and reopens it with the same execution identity.

## Existing owner and delta

Current Windows supervisor and design-c/1 identity/store contracts; this is the first runtime proof, not a replacement app. Preserve existing behavior and extend its integration boundary; do not recreate a landed producer.

## Acceptance criteria

- [x] Build one coherent source/dependency cohort and record hashes/licences; developer tools are absent from the delivered host PATH.
- [x] Exercise the real SDK loop, durable store and observation interface with a counting scripted model; reopen preserves the transcript without generation.
- [x] Required policy is installed before any dispatch/recovery; waiting for readiness cannot deadlock host construction.
- [x] Reject a second owner of the same store; bound shutdown's drain attempt. Release ownership only after actual host/worker settlement; timeout preserves blocked/uncertain handoff rather than reporting success.
- [x] Record unresolved native dependencies, selective recovery defer and packaging behavior as failures, never simulated passes.
- [x] Extend landed store/command contracts with engine identities and a versioned paired-store manifest before any migration writes; preserve existing schema-2 conversion.
- [x] Delayed recovery opens only under proven admission/child-ownership quiescence; a held uncertain session remains resumable without clearing fresh claims.
- [x] Bind IPC requests/replies to process generation and operation/attempt/request IDs; reserve control capacity under queue saturation, reject stale replies, and never treat an observation timeout as permission to resend.
- [x] Distinguish rejected-before-admission, accepted/pending, committed-reference, cancelled/settled and uncertain-after-disconnect. Do not drop command replies under observation's drop-oldest policy.
- [x] Prohibit all cross-process waits inside canonical transactions and conversation/case/recovery physical locks. Close admission with a logical lease, drain remote work before engine guards, and validate publication locally.

## Blocked by

None — authorised independent initial slice from `c2bd8964`.

## Design C coordination

- DC02 shared identity and scope vocabulary

Preserve the canonical DC owner and acceptance in the [Design C spec](../../DESIGN_C_IMPLEMENTATION_SPEC.md). These are coordination/contract obligations, not a claim that landed DC tickets remain unimplemented. Review current integration leases before changing shared modules.

## Evidence and validation

[Focused evidence](../../../research/2026-10-10-opencode-integration/w2-02-dispatch-recovery.md); [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md). Exercise observable behavior through the existing public domain/conversation facade and shared Harness interface. Record scripted transport, real engine, real account and packaged acceptance separately. Existing failures remain open until the corresponding acceptance proves their resolution.

Executed receipts: [host/cohort](../../../implementation/opencode-foundations-h01.md),
[IPC](../../../implementation/opencode-foundations-ipc.md) and
[shared contracts](../../../../packages/contracts/harness.md#bounded-validation-evidence).
Direct SDK/store tests passed 13/13; actual SDK-through-IPC tests passed 14/14;
transport tests passed 46/46; shared-contract/profile tests passed 102/102.
These runs overlap in responsibility and are not one aggregate suite.
The prepared manifest does not authorize saved mappings: H02 validates the actual
stores and activates the initial generation. H06/H18 retain migration/restore.
Selective recovery, clean-checkout reproduction, 29 packages without recognized
licence files and packaged/native qualification remain explicit downstream work.
