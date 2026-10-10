# S3 — Durable learning workflows and safe migration

Status: draft for review; implementation is not authorised by this document.

## Problem Statement

Agent execution alone cannot guarantee correct scoring, validated test publication or consistent recovery across runtime and canonical databases. Current Design C already implements saved conversations, 5/10/20 generation/checkpoints, Home/nightly, saved tests and whole attempts. The migration must adapt these producers while preserving their contracts, source originals, memory and history.

## Solution

Use OpenCode for execution and bounded child work while existing domain modules validate and publish results through durable operation receipts. Migrate conversation ownership explicitly, preserve deterministic operations, and prove recovery and packaged Windows behavior before switching normal use.

## User Stories

1. As a doctor, I want a generated set of 5, 10 or 20 questions, so that practice fits my available time.
2. As a doctor, I want only validated questions published, so that malformed partial output is not presented as a finished test.
3. As a doctor, I want completed valid batches retained after interruption, so that I can resume without losing useful work.
4. As a doctor, I want uncertain generation reported before a repeat request, so that a crash does not silently repeat billed work.
5. As a doctor, I want one saved test referenced from chat and Tests, so that those views cannot diverge.
6. As a doctor, I want reviewed-bank scoring to remain deterministic, so that a model cannot alter my result.
7. As a doctor, I want an optional explanation of my result, so that I can learn from it without changing the marks.
8. As a doctor, I want source checks and Updates digests to retain dates and source identity, so that fresh evidence is distinguishable from generated interpretation.
9. As a doctor, I want daily suggestions based only on eligible learning, so that temporary case material is excluded.
10. As a doctor, I want opt-in nightly work to follow configured limits, so that background generation stays predictable.
11. As a doctor, I want Stop and late publication to resolve consistently, so that a cancelled result cannot appear unexpectedly.
12. As a client, I want to reconnect after a lost acknowledgement, so that I can recover the committed outcome without repeating it.
13. As a doctor, I want my existing saved chats, citations and attempts preserved during migration, so that the new harness does not erase prior work.
14. As a doctor, I want shared Library originals preserved when one chat/project is removed, so that independent references remain usable.
15. As a profile owner, I want backups to represent compatible runtime and domain state, so that restore does not create mismatched histories.
16. As a profile owner, I want a clear rollback path, so that a failed upgrade does not open incompatible state with an old host.
17. As a Windows user, I want ordinary launch, quit and reopen to work with bundled dependencies, so that developer tools are unnecessary.
18. As a doctor, I want an imported test refined through the selected model while unresolved material remains editable, so that migration preserves the existing import flow.
19. As a doctor, I want explicit fictionalisation of temporary material to publish only a reviewed eligible test, so that temporary originals do not become durable generation inputs.

## Implementation Decisions

- Existing domain modules own reviewed scoring, source eligibility, test validation, learning observations and canonical publication. OpenCode owns operational execution/children. Deterministic import, scoring, indexing and source-change checks do not become agent turns.
- Preserve current saved-generation jobs, command IDs, checkpoints, saved-version identities, conversation run receipts and Home/nightly occurrence ownership. Adapt their submission/provider-task boundary to OpenCode and extend existing records with engine/attempt references. Keep fictionalisation, test imports and active-Test assistance checks connected through the same authority.
- Give test import/refinement and temporary fictionalisation/review explicit vertical adapter slices. Preserve their purposes, bounded stages, validators, edit/resolve and canonical publication; do not retire the old generation route while either consumer still needs it. Initial learning admission, then child and MCP slices, each prove the current active-Test and Study exposure guard before becoming usable.
- A workflow definition lists bounded domain stages, validator versions and permitted child roles. It is not a replacement agent scheduler. Generated tests checkpoint inputs/source versions, validated batches, model-attempt identities and one publication identity.
- Repair and retest the current shared-retrieval guard mismatch as a bounded prerequisite slice. The existing source/publication fence already runs inside the canonical transaction; preserve and bind it across IPC. Earlier missing-fence claims describe the old source, not the current saved producer.
- Preserve batches of up to five, the existing twelve batch-call counter, three-active-job bound, explicit retry and shorter-set acceptance. Nominal successful batching uses 1/2/4 slots for 5/10/20 sets; auxiliary inference consumes separately recorded shared permits. Daily suggestions retain the existing fifteen-prompt global bundle; project-specific filtering is a separate extension. Partial sets require an explicit accepted count.
- Operation receipts use stable IDs plus payload digests. A repeated ID with a different payload is rejected. Executors recheck scope, revisions and cancellation before effects. Repeated delivery returns the canonical receipt rather than repeating the effect.
- Cross-store consistency uses receipts and an outbox/reconciliation protocol. A runtime acknowledgement cannot establish canonical commit by itself. A crash after domain commit and before acknowledgement recovers the committed result. Two SQLite stores are not assumed to share a transaction.
- Persist engine input/session identities before delivery; replay admission without automatically waking generation. Reserve a durable permit for each actual outbound attempt. Current source/revision/cancellation checks and final domain publication share the canonical transaction.
- Record model-dispatch uncertainty distinctly from a deterministic step needing reconciliation. Recovery may reconcile committed effects and rerun permitted deterministic work; repeating uncertain generation requires its explicit policy/decision. Preserve validated test batches without restarting billed generation automatically.
- Cancellation and publication race under a durable epoch. Commit-first returns the committed outcome; cancel-first prohibits late publication. Parent/child/worker settlement is observable and cannot be inferred from cancellation acceptance alone.
- Generated practice remains separate from reviewed scored content. Model-written result explanations consume deterministic scores; they cannot rewrite them or invent learner evidence. Updates detection/review and generated digest production remain distinct stages.
- Nightly work remains off by default, app-running, bounded and limited to the established catch-up behavior. Scheduling submits the same typed operations and model budgets as foreground clients.
- A consumed daily occurrence is stable across settings/input changes, timezone/DST changes and clock rollback. One catch-up coalesces missed dates; disabling scheduling fences pending dispatch and publication.
- Preserve one latest-due catch-up after sleep while running and future-only arming on cold restart. Reconcile a claimed-but-unsubmitted occurrence to its stable keyed job without treating a possibly sent model call as safe to repeat. Current occurrence/cache ownership remains; no Home UI dependency is needed for backend scheduling.
- Design C IDs and module owners remain stable. Shared identity/scope contracts, conversation migration, saved tests, suggestions, readers and integrated acceptance are coordinated contributions to its backlog, not competing implementations.
- Current-code baseline is the committed Design C integration source at 76cfdff. Source presence and prior test receipts do not imply installed acceptance. Reconcile later changes before implementation; do not recreate already landed producers from the older research snapshot.
- Migrate legacy saved history through stable mappings and exact citation/provenance references. Do not migrate temporary buffers or trigger generation. Freeze legacy writes per migrated conversation; preserve read access without two writable transcript authorities.
- Preserve saved observation-disconnect continuation, temporary disconnect cancellation/discard and explicit Stop. Temporary Save settles descendants, stages the retained family/originals and commits one persistent mapping, retaining volatile state on failure. Current single-store Save tests do not prove this new cross-store transfer.
- Saved migration/receipt retirement and temporary execution/Save are separate slices. Promotion uses a stable ID and freeze, settle, stage, map, activate, retire states; recheck current epochs at map/activation. Stage is non-admitted, orphan cleanup precedes recovery/export, and replay cannot regenerate. A failed transfer preserves volatile originals only while their process survives; a hard crash cannot preserve RAM.
- Snapshot runtime/canonical stores and relevant source/tombstone versions under a demonstrated consistency protocol. Restore validates the bundle and current deletion frontier before replay. Rollback uses a compatible bundle or read/export path, never an unsupported database downgrade.
- Extend the existing recovery barrier and schema-2 converter. Establish store identities and the paired-store manifest contract in the first persistent slice, before migrated writes. Publish a verified manifest last and switch a complete generation atomically; abort if writers cannot settle. Later integrated acceptance exercises all producers against that contract.
- Retire payload-bearing command receipts with owner deletion. Keep an opaque operation identity and terminal-unavailable state for replay without deleted result text or payload digest. Preserve deduplication against old backups; new exports must not carry deleted payloads. An unavailable trustworthy deletion frontier permits inspection only, not active recovery.
- Package one coherent runtime cohort and all required native/WASM assets. Preserve upstream notices and patch provenance. Hidden application tests and native installation/authentication acceptance remain separate scopes.

## Testing Decisions

- Use connected public-interface flows with synthetic data across several nephrology domains and text/PDF/image inputs. Reuse current generated validation, subscription cancellation, scoring, source-revision and backup tests.
- Fault-inject before dispatch, after dispatch, before/after canonical commit, before acknowledgement, at child completion and at final test publication. Assert one canonical artifact/evidence event, explicit uncertainty and preservation of valid batches.
- Exercise 5/10/20 sets, insufficient source coverage, malformed/duplicate questions, cancelled review children and source changes during validation. A validator passing is distinct from a claim of educational quality.
- Prove deterministic scoring without any model transport. Add optional explanations and ensure failure leaves scores/results usable. Enforce active Test assistance restrictions through new tools as well as existing client routes.
- Migrate/restore a populated synthetic profile containing saved/archived/temporary conversations, shared originals, corrected memory and historical attempts. Verify relationships, tombstones, citations and no model calls during conversion.
- Verify packaged startup, one host owner, owned shutdown, host death/reopen and two observing clients. Native Windows and real subscription checks require matching artifact evidence; no such acceptance is claimed by this spec.

## Out of Scope

Implementing now; rewriting Design C's visual specification or file readers; replacing assessment standards; adding another general workflow engine; background OS services; or incidental deployment/provider usage.

## Further Notes

The [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md) governs shared integration decisions. The [current-branch delta](../../../research/2026-10-10-opencode-integration/w3-03-minimality-design-c.md) supersedes the older inventory where producers have landed. Vertical tickets preserve harness blockers and Design C coordination, with one canonical owner for each shared change.
