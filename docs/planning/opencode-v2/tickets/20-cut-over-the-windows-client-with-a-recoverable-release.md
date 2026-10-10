# H20 — Cut over the Windows client with a recoverable release

**Status:** draft — review pending; implementation not authorised by this research request.

**Spec:** [S1](../specs/01-harness-control.md), [S2](../specs/02-memory-context.md), [S3](../specs/03-workflows-migration.md)

**Owner:** Integration + F0 and module owners

**Current source baseline:** `76cfdff23e259700bec820e174c200540c7c1e1b`. Reconcile later changes before implementation.

## What to build

The selected Windows client runs the new harness with existing learning data and a verified shutdown/reopen, backup and rollback path.

## Existing owner and delta

Current DC20/DC21 integration and packaging ownership; source presence does not imply installed acceptance. Preserve existing behavior and extend its integration boundary; do not recreate a landed producer.

## Acceptance criteria

- [ ] Integrate approved slices on one baseline with current Design C owners; retain original source/content/memory/assessment journeys.
- [ ] Verify bundled runtime/native/WASM/licence provenance with developer tools absent and one persistent store owner.
- [ ] Run populated synthetic migration, two observers, host death, cancellation settlement, dependency invalidation and backup/restore across varied text/PDF/image domains.
- [ ] Retire overlapping Hermes execution/compression and temporary compatibility writers only after parity; retain attributed reused memory/domain code.
- [ ] Record hidden app checks separately from native installation/authentication and actual account/model quality/context acceptance; optional H11 and H19 are not required for default cutover.
- [ ] Exercise supported profile paths with real selected local engines; distinguish long-path fixture errors from product failures and record the delivered path contract.

## Blocked by

- [H18](18-delete-and-restore-a-consistent-migrated-learning-profile.md)

## Design C coordination

- DC20 integrated acceptance; DC21 Windows delivery

Preserve the canonical DC owner and acceptance in the [Design C spec](../../DESIGN_C_IMPLEMENTATION_SPEC.md). These are coordination/contract obligations, not a claim that landed DC tickets remain unimplemented. Review current integration leases before changing shared modules.

## Evidence and validation

[Focused evidence](../../../research/2026-10-10-opencode-integration/w3-04-host-proof-adversary.md); [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md). Exercise observable behavior through the existing public domain/conversation facade and shared Harness interface. Record scripted transport, real engine, real account and packaged acceptance separately. Existing failures remain open until the corresponding acceptance proves their resolution.
