# H12 — Adapt five-question saved generation to OpenCode

**Status:** draft — review pending; implementation not authorised by this research request.

**Spec:** [S3](../specs/03-workflows-migration.md)

**Owner:** M4 + integration

**Current source baseline:** `76cfdff23e259700bec820e174c200540c7c1e1b`. Reconcile later changes before implementation.

## What to build

The existing chat/Tests producer sends its five-question generation through OpenCode and retains one canonical saved test in both destinations.

## Existing owner and delta

SavedGenerationService, SavedTestRepository and existing DC16 chat/Tests producers. Preserve existing behavior and extend its integration boundary; do not recreate a landed producer.

## Acceptance criteria

- [ ] Adapt SavedGenerationService submission/provider-task execution; preserve its job/command IDs, bounded checkpoint/input limits, validator versions and SavedTestRepository publication.
- [ ] Validate schema, keys, source eligibility and duplicates; only a final canonical transaction may publish the test.
- [ ] Recheck source revisions, cancellation epoch and tombstones inside that publication transaction.
- [ ] Record operation/payload digest, candidate receipt and one artifact/version identity; lost acknowledgements return the existing result.
- [ ] Preserve reviewed-bank distinction and existing deterministic scoring; coordinate with DC16 instead of implementing a competing producer.
- [ ] H00's current retrieval regression is green before migration; preserve the already implemented final source/publication transaction across IPC.

## Blocked by

- [H00](00-restore-the-existing-saved-generation-retrieval-path.md)
- [H02](02-answer-with-an-eligible-library-passage.md)
- [H04](04-adjust-roles-and-configuration-with-visible-activation.md)
- [H05](05-complete-a-learning-turn-whose-memory-stays-corrected.md)

## Design C coordination

- DC12 saved-test/version contract; DC13 Study attempt; DC16 producer

Preserve the canonical DC owner and acceptance in the [Design C spec](../../DESIGN_C_IMPLEMENTATION_SPEC.md). These are coordination/contract obligations, not a claim that landed DC tickets remain unimplemented. Review current integration leases before changing shared modules.

## Evidence and validation

[Focused evidence](../../../research/2026-10-10-opencode-integration/w3-03-minimality-design-c.md); [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md). Exercise observable behavior through the existing public domain/conversation facade and shared Harness interface. Record scripted transport, real engine, real account and packaged acceptance separately. Existing failures remain open until the corresponding acceptance proves their resolution.
