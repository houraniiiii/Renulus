# H08 — Apply versioned instructions and skills to a learning task

**Status:** draft — review pending; implementation not authorised by this research request.

**Spec:** [S1](../specs/01-harness-control.md), [S2](../specs/02-memory-context.md)

**Owner:** F0 + M1

**Current source baseline:** `76cfdff23e259700bec820e174c200540c7c1e1b`. Reconcile later changes before implementation.

## What to build

A user enables a reviewed learning skill or instruction revision and sees it applied consistently after reopen and compaction.

## Existing owner and delta

Existing context/eligibility policy; replace only migrated instruction loading and compaction reinjection. Preserve existing behavior and extend its integration boundary; do not recreate a landed producer.

## Acceptance criteria

- [ ] Load only explicit versioned instruction/skill sources with documented precedence and content hashes.
- [ ] Verify hostile ancestor/global files and Library text cannot inject executable configuration, grants or package installation.
- [ ] Skills never grant tools. Ordinary edits affect new runs; existing runs change only through explicit migration. Mandatory revocations apply immediately.
- [ ] Reinject pinned guidance plus current mandatory constraints after reopen/compaction; explicit user requests outrank optional skill preferences. H10 owns production educational-compaction acceptance.
- [ ] Show effective revision and failure; failed activation retains a healthy version under current revocations.

## Blocked by

- [H04](04-adjust-roles-and-configuration-with-visible-activation.md)
- [H06](06-continue-saved-and-temporary-chats-through-one-owner.md)

## Design C coordination

- DC10 configuration presentation

Preserve the canonical DC owner and acceptance in the [Design C spec](../../DESIGN_C_IMPLEMENTATION_SPEC.md). These are coordination/contract obligations, not a claim that landed DC tickets remain unimplemented. Review current integration leases before changing shared modules.

## Evidence and validation

[Focused evidence](../../../research/2026-10-10-opencode-integration/w1-04-extensions.md); [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md). Exercise observable behavior through the existing public domain/conversation facade and shared Harness interface. Record scripted transport, real engine, real account and packaged acceptance separately. Existing failures remain open until the corresponding acceptance proves their resolution.
