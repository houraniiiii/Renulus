# H07 — Delegate a bounded evidence review and stop its children

**Status:** bounded implementation released after local H02/H04/H05 acceptance. The [H02–H08 ledger](../../../implementation/OPENCODE_H02_H08_HANDOFF.md) records canonical policy, registry, Python family and native child ownership leases. Connected child/Stop/restart acceptance remains open.

**Spec:** [S1](../specs/01-harness-control.md), [S3](../specs/03-workflows-migration.md)

**Owner:** F0 + M1/M2

**Current source baseline:** `76cfdff23e259700bec820e174c200540c7c1e1b`. Reconcile later changes before implementation.

## What to build

A learning run delegates a narrow evidence review, observes foreground/background progress and stops every owned descendant without widening access.

## Existing owner and delta

Existing Stop and conversation receipt semantics; OpenCode supplies child coordination. Preserve existing behavior and extend its integration boundary; do not recreate a landed producer.

## Acceptance criteria

- [ ] Use upstream child/session coordination; child role/model/tool grants intersect the parent's current authority.
- [ ] Persist parent/child operation and cancellation epochs; default bounded depth/concurrency/output/attempt budgets are inspectable.
- [ ] Parent Stop interrupts descendants and reports settlement; late background completion cannot wake revoked generation or publish results.
- [ ] Test restart, child failure, denied overrides and revocation while a permission prompt waits.
- [ ] Child reports preserve source identifiers and remain ineligible automatic learner-memory producers unless a domain publication explicitly qualifies them.
- [ ] Extend H02's active-Test/Study exposure guard to child admission, results and detached callbacks; epochs/draft revisions cannot be widened or dropped over IPC.

## Blocked by

- [H02](02-answer-with-an-eligible-library-passage.md)
- [H04](04-adjust-roles-and-configuration-with-visible-activation.md)
- [H05](05-complete-a-learning-turn-whose-memory-stays-corrected.md)

## Design C coordination

- DC04 progress/Stop presentation

Preserve the canonical DC owner and acceptance in the [Design C spec](../../DESIGN_C_IMPLEMENTATION_SPEC.md). These are coordination/contract obligations, not a claim that landed DC tickets remain unimplemented. Review current integration leases before changing shared modules.

## Evidence and validation

[Focused evidence](../../../research/2026-10-10-opencode-integration/w2-03-workflows.md); [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md). Exercise observable behavior through the existing public domain/conversation facade and shared Harness interface. Record scripted transport, real engine, real account and packaged acceptance separately. Existing failures remain open until the corresponding acceptance proves their resolution.
