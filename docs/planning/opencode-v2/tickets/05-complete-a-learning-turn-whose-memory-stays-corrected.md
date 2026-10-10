# H05 — Complete a learning turn whose memory stays corrected

**Status:** draft — review pending; implementation not authorised by this research request.

**Spec:** [S2](../specs/02-memory-context.md)

**Owner:** M5 + M1 + integration

**Current source baseline:** `76cfdff23e259700bec820e174c200540c7c1e1b`. Reconcile later changes before implementation.

## What to build

A saved explanation produces eligible learner memory, and a later correction or deletion cannot be undone by queued capture or historical follow-up.

## Existing owner and delta

Current memory/2 records, typed relations, publication guards and restored-memory capture barrier. Preserve existing behavior and extend its integration boundary; do not recreate a landed producer.

## Acceptance criteria

- [ ] Resolve completed answers by store/profile/message identities, accepted completion, canonical text digest and publication receipt.
- [ ] Persist dependencies on memory/source revisions, historical messages, tools and summaries; exclude unknown legacy lineage from automatic recapture.
- [ ] Reproduce and close all four queued/completed-capture edit/delete regressions through the public learning/memory interface.
- [ ] Define global/project visibility and scope-aware deduplication; distinguish generated teaching from learner observations and reviewed assessment evidence.
- [ ] Run actual Mem0/Qdrant/FastEmbed correction, deletion, reindex and reopen with synthetic profiles; no second memory worker per child.
- [ ] Extend existing Dependency/EligibleInput, publication and restore barriers. One M5/integration owner controls support lineage; echo support cannot become independent by acquiring a new answer ID.
- [ ] Preserve existing profile-global facts and temporary/saved-case exclusion; explicitly project-owned additions use scoped identity. Dependency revocation stays terminal across scan/requeue.
- [ ] Resolve immutable answer bytes outside all canonical transactions/physical thread locks; commit rechecks local dependency/publication records. Prove the extraction round trip with one host slot and a live IPC pump.

## Blocked by

- [H02](02-answer-with-an-eligible-library-passage.md)
- [H04](04-adjust-roles-and-configuration-with-visible-activation.md)
- [H24](24-keep-memory-worker-ownership-until-extraction-settles.md)

## Design C coordination

- DC02 typed references; DC04 completed-answer contract

Preserve the canonical DC owner and acceptance in the [Design C spec](../../DESIGN_C_IMPLEMENTATION_SPEC.md). These are coordination/contract obligations, not a claim that landed DC tickets remain unimplemented. Review current integration leases before changing shared modules.

## Evidence and validation

[Focused evidence](../../../research/2026-10-10-opencode-integration/w2-01-memory-dependencies.md); [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md). Exercise observable behavior through the existing public domain/conversation facade and shared Harness interface. Record scripted transport, real engine, real account and packaged acceptance separately. Existing failures remain open until the corresponding acceptance proves their resolution.
