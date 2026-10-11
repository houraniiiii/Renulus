# H02 — Answer with an eligible Library passage

**Status:** authorised implementation in progress. Local SDK/Library/publication evidence is recorded in the [H02–H08 ledger](../../../implementation/OPENCODE_H02_H08_HANDOFF.md); connected desktop acceptance remains open.

**Spec:** [S1](../specs/01-harness-control.md), [S2](../specs/02-memory-context.md)

**Owner:** M2 + M1/F0

**Implementation input:** consume the [foundation handoff](../../../implementation/OPENCODE_FOUNDATIONS_HANDOFF.md) on `codex/opencode-foundations`, including the final Design C baseline `c2bd8964`, H01's `b5101da0` and H24's `756c8ebc`. The older research baseline `76cfdff23e259700bec820e174c200540c7c1e1b` is historical. Reconcile subsequent changes before implementation.

## What to build

The same headless and existing desktop learning flow retrieves a real synthetic Library passage through a registered native tool and opens its citation.

## Existing owner and delta

Existing Library, retrieval and passage-opening APIs plus the landed conversation facade. Preserve existing behavior and extend its integration boundary; do not recreate a landed producer.

## Acceptance criteria

- [ ] Retain the existing Python Library/rights/index implementations; direct listing/import still works without an agent turn.
- [ ] Before the first saved mapping, validate the actual canonical schema-2 store and native runtime store against H01's prepared manifest, select the initial active generation under the existing writer/admission barrier, and support reopening that validated selection. Failed validation or interrupted activation must remain non-admitted and reconcile without generation. H01's prepared file alone is not an active-store proof. This initial activation belongs here; H06 migrates legacy conversations and H18 later proves complete paired backup/restore.
- [ ] Tool calls carry host-derived scope, revision and cancellation data; changed eligibility before read or publication blocks the result.
- [ ] Persist one completed-answer/publication receipt and stable engine mapping, with digest conflict detection and lost-ack reconciliation.
- [ ] Expose progress, tool activity and terminal result through one event mapping; a client disconnect does not invent cancellation or repeat the effect.
- [ ] Keep migrated automatic memory capture disabled until H05 provides its dependency contract.
- [ ] Enforce current active-Test/Study exposure and publication guards at initial admission and callbacks; stale policy/context/draft revisions cannot disclose late assistance.

## Blocked by

- [H01](01-run-a-persistent-headless-opencode-conversation.md)

## Design C coordination

- DC02 reference contracts

Preserve the canonical DC owner and acceptance in the [Design C spec](../../DESIGN_C_IMPLEMENTATION_SPEC.md). These are coordination/contract obligations, not a claim that landed DC tickets remain unimplemented. Review current integration leases before changing shared modules.

## Evidence and validation

[Focused evidence](../../../research/2026-10-10-opencode-integration/w1-01-current-integration.md); [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md). Exercise observable behavior through the existing public domain/conversation facade and shared Harness interface. Record scripted transport, real engine, real account and packaged acceptance separately. Existing failures remain open until the corresponding acceptance proves their resolution.
