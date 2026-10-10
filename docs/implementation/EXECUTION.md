# Renulus implementation run

## Current work — Design C, October 10

The [Design C implementation spec](../planning/DESIGN_C_IMPLEMENTATION_SPEC.md)
is the current UI replacement backlog and delivery sequence. Tickets DC01–DC21
are now in implementation under the owner's October 10 request authorising
local commits and matching Windows delivery. Starting canonical checkout:
`C:/Renulus/dev/repo`, clean `main` at `528025ff0b22477c12ee1512e0e7d15297a6e888`.
The integration branch is `codex/design-c-integration`. Existing newer work and
uncommitted changes were absent at start; the personal profile remains outside
all implementation tests. Track execution against those IDs, with one owner
for each reserved path and a shared committed baseline.
Use [parallel-work rules](../planning/PARALLEL_WORK.md) and record prerequisite
commits, integrated evidence and remaining limits in the ticket handoff or its
linked issue. Update this current section when execution starts.

### Active reservations — initial prerequisite wave

| Owner/lane | Branch and worktree under `C:/Renulus/dev/worktrees/` | Exact write reservation | Synthetic profile under `C:/Renulus/scratch/design-c/` |
| --- | --- | --- | --- |
| Integration lead | `codex/design-c-integration`, canonical checkout | `docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md`, this execution record, `runtime/renulus/storage/`, `runtime/renulus/server.py`, `runtime/renulus/services.py`, `apps/desktop/src/shell/`, `apps/desktop/src/ui/`, `apps/desktop/src/platform/`, root manifests/locks, build/release configuration | `integration` |
| DC01 design reconciliation | `codex/dc01-design`, `dc01-design` | editable C Figma page; `docs/implementation/design-c-reconciliation.md` | `design` |
| DC02 contract proposals/foundation fixtures | `codex/dc02-contracts`, `dc02-contracts` | `packages/contracts/design-c.md`, `packages/contracts/fixtures/design-c/`, `runtime/renulus/design_c_contracts.py`, `tests/integration/test_design_c_contracts.py` | `contracts` |
| Pass 1 migration/data reviewer | `codex/dc-review-data`, `dc-review-data` | `docs/implementation/design-c-review-data.md` only | `review-data` |
| Pass 1 assessment reviewer | `codex/dc-review-assessment`, `dc-review-assessment` | `docs/implementation/design-c-review-assessment.md` only | `review-assessment` |
| Pass 1 reader/platform reviewer | `codex/dc-review-readers`, `dc-review-readers` | `docs/implementation/design-c-review-readers.md` only | `review-readers` |

The lead publishes reviewed shared contracts and migration sequencing before
dependent implementation. Reviewers challenge actual source seams and identify
reproductions; their notes are evidence, not another backlog. Every ticket starts
open. DC01 and DC02 are in progress; dependent feature tickets stay open until
their real producers/consumers and required evidence are integrated. No live
provider request, personal-profile migration or launcher promotion is part of
this prerequisite wave.

### DC02 foundation slice — validated before dependent feature writes

The lead added a schema-2/known-migration compatibility gate, exact schema-1
column inventory and conversion adapters, typed full-row recovery identities
shared by JSON/ZIP1/ZIP2, nullable live-reference reconciliation and transactional
restore invalidation. Original legacy record columns/IDs/assessment meanings
are unchanged. History snapshots and original pins stay separate from optional
live pointers; preserve-unavailable references never enter the drop-row graph.

Validation: seven focused migration/recovery tests passed. The existing
foundation/backup selection passed 39 checks and exposed one stale absolute
export-size assertion: the current reviewed pack itself exceeds that old 1 MiB
threshold. The check now compares catalogue omission with the actual baseline
size while its SQLite authoriser still forbids reading bulk catalogue columns;
that regression and seven foundation checks passed together (eight checks).
Independent source rechecks passed 20 typed-recovery assertions and eight
restore-invalidation assertions, with exact external receipts in the review
report. Unknown column changes are refused until an exact conversion is added.

DC02 is still open for final shared contract/fixture integration and reviewed
handoff. DC04 must add the actual saved-case attachment tombstone producer;
new record owners must register their deletion aliases/relations and prove
export/restore. DC06/DC19 must compare the local context epoch before publication.

The entries below preserve earlier implementation evidence. Their Flow selection,

### Published contracts and feature reservations

The lead reviewed `design-c/1` validators at `527677f3`, after the exact-name
proposals, and integrated all three pass-1 reports (`db96f4a0`, `388687c2`,
`335e5a86`). The fixture digest follow-up is pending; its manifest is not yet
published as final evidence. Feature development may use these committed shapes
and the accepted additive clarifications in section 10 of the existing spec.
Ticket closure still requires the integrated producers and consumers.

| Owner | Reserved write paths | Scope / synthetic profile |
| --- | --- | --- |
| Lead | All module `schema.sql` and `migrations/` paths, storage, server, shared renderer/platform/shell/UI, `apps/desktop/electron/`, `tools/renulus-control/`, root configuration/locks, cross-module tests | Schema sequencing, isolation/controller, shell/policy and integration; `integration` |
| Reader worker (Poincare) | `runtime/renulus/knowledge/` except schema/migrations; `apps/desktop/src/modules/library/`, new `apps/desktop/src/modules/reader/`; `tests/knowledge/`, `tests/integration/test_design_c_readers.py` | DC08 and Library DC10; `readers` |
| Collection worker (Pauli) | New `runtime/renulus/assessment/test_repository.py`, `test_api.py`, `test_models.py`; new `apps/desktop/src/modules/tests/`; `tests/assessment/test_saved_tests.py` | DC12 collection/version/report and legacy mapping; `saved-tests` |
| Attempt worker (Russell) | New `runtime/renulus/assessment/attempt_repository.py`, `attempt_api.py`, `attempt_models.py`; new `apps/desktop/src/modules/attempts/`; `tests/assessment/test_whole_attempts.py` | DC13 then DC14/DC15 core; `attempts` |

Existing assessment repository/router and generation files remain lead-held.
Collection and attempt workers have disjoint repositories/routers and use a
small private pinned-version interface. No worker edits another reservation.
All three feature workers merge the next committed reservation baseline into
their clean existing worktree. Separate owned profiles remain outside Git.

branches, paths, issue status, time windows and heartbeat instructions describe
those dated runs; they are not assignments or scheduling instructions for C.
The current installed baseline and canonical paths are in
[the workspace guide](../WORKSPACE.md) and [project brief](../PROJECT_BRIEF.md).

## Historical implementation record — October 4–6

Final local handover October6: [the delivered app](DELIVERY_20261006.md) follows
the owner's explicit acceptance of the live blocker. The final ordinary
queue02/03 proof passed its bounded parent review: concurrent Library controls,
same revisions ready after reopen, no reimports and normal physical closes.
See [receipt-qualified queue acceptance](finalise-ingestion-usability-699938f2.md#parent-acceptance).
All C lanes are integrated/retired with commits/ignored receipts preserved;
only the main checkout and held E supplement tree remain. Issue12 is scoped
to this accepted local handover. Full/live work remains in1/2/3/5/7/9 and
draft PR13; no broader requirement or failed aggregate is silently passed.
At publication, stop the one20-minute heartbeat for this handover.

Current October6 delivery: matching699938f2 local installed acceptance and
maintenance are recorded in [the maintenance result](finalise-maintenance-699938f2.md).
The normal C launcher/owned shortcut selects that app and preserves the E
learning/account profile. Uninstall/reinstall/reopen canonical and original
signatures are unchanged; ordinary main/backend close passed12.973s. Original
failed aggregates remain failed and completed installation/storage/imports were
not repeated. Documentation and scoped queue-closeout lanes are integrated in
the final wave and retired after preserving their commits/receipts.

The selected Codex gpt-6-astra run returned subscription_limit; successful
generation/automatic capture and dependent live journeys remain unperformed.
Go stays paused. No source, account or model fallback is authorised. On October 6
the owner chose **“Deliver with the live blocker.”** The local handover follows
that decision; full product validation and draft PR13 remain open.
[The exact64-row audit](finalise-audit-699938f2.md) records accepted local scopes
and limitations. The earlier timeline below is preserved history.

Started October 4, 2026, 19:21 UTC (21:21 Warsaw). Target work window ends
October 5, 2026, 03:21 UTC (05:21 Warsaw). The user authorised implementation,
parallel bounded agents, GitHub tracking and a heartbeat every 20 minutes
(latest owner update on 2026-10-05; the earlier 15-minute setting is historical).

GitHub issues are the live queue. The earlier plans explain product intent;
they are adjustable engineering baselines, not immutable specifications.
Confirmed subscription, source-use, retention and licence choices still apply.
Flow is the selected visual direction. Preserve the UI and acquisition sessions'
uncommitted work and source originals.

## Waves

1. Integration owner establishes SQLite, process contracts, profiles and app
   boot. Runtime lane adopts attributed Hermes; desktop lane implements Flow;
   content lane publishes an original cross-domain pack.
2. Learn, library, cases and assessment build complete flows against these
   contracts. Source collection is consumed through manifests and selected files.
3. Memory, study/home and updates connect real evidence, editable records and
   current-source checks.
4. Integrate, exercise combined journeys, package the Windows app and record
   capability/coverage limits. Expand useful breadth while checks pass.

A ticket with satisfied dependencies starts in the next available lane. A
concrete failing integration becomes a prerequisite ticket, not a new planning
round. Record changes of direction in the ticket that motivated them.

## Ownership and delivery

The integration branch is `build/renulus-integration` in the sibling
`Renulus-wt-integration` worktree. Active integration subsequently moved to the
preserved clone at `E:/Renulus-native-delivery/desktop-20261005/repo` after the
disk-exhausted check; the original worktree remains preserved. Each worker has a separate branch/worktree
and runtime profile. The integrator owns contracts, storage, shared build files
and combined checks. Initial desktop shell ownership includes its local manifest,
tokens and primitives; after handoff these are reserved shared files.

Use small coherent commits and pull requests. Each handoff records owned paths,
behaviour, reuse, meaningful checks, evidence and remaining limits. Do not close a
ticket on a mock, typecheck or prototype when a real producer remains absent.
Live account access and clean-machine/signed release evidence are separate from
synthetic application checks. Do not access credentials from other apps or make
billed provider calls during verification.

## Interface baseline

One app-managed local Python process serves a versioned loopback interface.
FastAPI provides routing and streaming; this is not Hermes's unrestricted HTTP
gateway or another agent loop. The desktop renderer receives public operations
and capability state, never provider credentials or arbitrary tool execution.
`/api/v1` results are direct JSON; errors have `{error:{code,message,retryable}}`.
Streaming uses ordered SSE events with one terminal state.

Module adapters expose `create_router(services)` and register their repository
on `services.registry`. Shared `Database` offers `connect()`, `transaction()`,
`fetch_one()`, `fetch_all()` and `execute()`. SQLite owns canonical data. Module
DDL is proposed under each owned `schema.sql`; the integrator applies migrations
through one checked ledger. Engines remain rebuildable derivatives.

Scope is explicit: study, personal-library, temporary-case, saved-case,
generated-practice or reviewed-assessment. Unclassified and temporary payloads
stay volatile. Every asynchronous commit checks cancellation/revision/deletion.

## Evidence

Detailed lane evidence lives in `docs/implementation/` and GitHub ticket comments.
Machine-only output, acquired originals, indexes and logs stay outside versioned
source. The heartbeat reports observed commits/checks, active lanes, blockers and
the next ready work; it does not imply unseen work succeeded.

## October 5 follow-up wave

The original eight-hour target ended at 03:21 UTC. The active goal continues
with the same 15-minute heartbeat loop and concrete remaining work. Matching
`3ff9b0d6` package, fresh installation, isolated native lifecycle and the actual
shortcut/Library25/search/citation workload passed with the qualifications in
`final-validation.md`. Source originals and earlier checkpoints are preserved.

Curie's #14 selection patch is integrated at `716045f1`; all 15 exact review
bindings are installed and verified in the external collection metadata.
Halley's #15 Office patch is integrated at `909d2968`. Its real Office restore
failure motivated the parent's shared archive extension/MIME fix; the exact
three-format originals/locator recovery gate subsequently passed. Ramanujan's
#16 import priority patch is integrated at `6bac014b`; 20 affected queue/worker
checks passed in the combined integration checkout. Their installed acceptance
remains separate from these application checks.

Hegel's #17 patch is integrated at `55d553d1`. The parent subsequently passed
one actual pinned CPU no-text image/original/citation/retrieval/delete proof in
102.085 seconds. Halley's classified Office preview and component review are
report-integrated; a bounded primary publisher-policy follow-up addresses the
remaining E06 supplement scope question. Dirac owns the serial application-only
backend regression on freeze55, excluding real helper and capacity workloads.
The parent owns shared recovery/UI, actual adoption, native checks and #18.
Peirce's manufactured freeze55 remains a preserved checkpoint while the parent
corrects the concrete normal-queue shutdown failure.

The user completed intentional Codex sign-in and added the Go key. Native
Connections on October 5 showed both accounts connected; the parent explicitly
selected Codex at 05:46:36 UTC. Only `gpt-6-astra` currently exposes an approved
image-check control. Catalogue availability, successful input requests and
interpretation quality remain distinct. Go learning remains paused pending
educational-use eligibility. The owner subsequently authorised ending the
temporary context; it was ended at 06:27:44 UTC without reading case details.
A synthetic text attempt was truncated by the native typing harness and its run
failed with subscription_limit; no further request or successful generation is
claimed. The actual normal app/backend are now stopped. Twenty-nine classified
originals were admitted to the learning profile through the supported API with
extraction disabled; their exact app-owned bytes and rights were verified.
Queued does not mean searchable. No credentials from another application are
used. The goal and single 15-minute heartbeat continue; the original eight-hour
target remains recorded above.

## Resumed finalisation wave — October 5

After the owner's explicit pause and resume, seven bounded workers started from
9d26f1ee in separate short C worktrees under C:/rn-finalise-20261005/lanes.
Packaging, completed backend regression, Library UI, subscription error/recovery
flows, formal ESENeph mapping (#19), ingestion performance and exact E06 source
adoption preparation have disjoint ownership. The integrator owns shared
contracts, real-profile adoption, live account requests, native/helper scheduling
and installed acceptance. Current original content is already 160 questions and
26 staged cases across 27 topics and 56 objectives; formal exam mapping remains
work, rather than another initial-bank implementation.

One observable heartbeat continues every 20 minutes, per the latest owner
instruction. The original eight-hour target and pause evidence are preserved;
no new delivery deadline is invented. The launcher remains on installed
3ff9b0d6 until a matching final source passes installation, normal-queue
shutdown/reopen and required connected journeys. Earlier mock, targeted,
incomplete regression and native observations retain their separate provenance.

## Recovered delivery session and SSD relocation — October 5

The current integration checkout is
`C:/Renulus-native-delivery/desktop-20261005/repo` on `build/renulus-integration`.
The exact 458.03 MiB checkout relocation completed at 11:05:35 UTC, moving
19,483 files with zero reported mismatches or failures. Tracked source matches
the pre-move HEAD. All existing C and E Git worktree links were repaired. A
junction at the former E checkout path preserves the old launcher target while
the installed freeze remains unchanged. Acquired originals and the E learning
profile were not moved or reimported.

The integration owner recovered the existing packaging, regression, Library,
subscription, content and ingestion lane contexts and receipts before resuming
work. The completed E06 admission plan and 28-file import retain their earlier
receipts. A separate bounded lane connects the formal ESENeph metadata to
assessment selection; an audit lane records actual requirement evidence.
Shared contracts, native scheduling, live accounts and acceptance remain owned
by the integrator. Exactly one mutex-protected 20-minute heartbeat actor is
active, with original target and pause history preserved in the local queue.

The first recovered runtime fix is integrated as `da726ac1`: Stop at either
public compaction boundary prevents a further model request. Its synthetic
evidence remains separately attributed; it does not establish live generation,
automatic memory extraction or matching installed acceptance.
