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

### Current integration checkpoint — 08d9272f

The earlier reservations below are historical. Active work remains against the
same DC01–DC21 backlog. Canonical root/branch and baseline 528025ff ancestry were
rechecked; the 18 pre-existing normalization-only flags remain unstaged.

| Owner | Current exact lease / prerequisite | Current evidence and next gate |
| --- | --- | --- |
| Lead | Shared shell/platform/server, migration/release paths; new modules/notes; study/service.py + study conftest/whole progress test; R9 CandidateEditor/types/owned renderer test | Study `77e139d9` 20 actual checks; Notes backend `7116e427` + retention `820d1906` six actual checks, frontend and mounted Workspace validation continuing. Home policy draft `434dc41a` eight focused checks; Workspace Files `1b0d22d3` seven actual checks. |
| Aquinas / dc01-design | TestSetupPane.tsx; attempts/session.ts + session.test.ts and AttemptRun/connected test only if needed; existing integration review report | R4 preview stylesheet and R6 durable action errors; independent recheck after source checkpoint. |
| Zeno / dc02-contracts | docs/implementation/design-c-windows-review.md only after completed Chat lease | Case image `c4b5f1df` and Save retry `08d9272f` integrated. 55 affected checks, five final image checks, two legacy image checks, 18 renderer then nine final Chat checks (overlapping counts). DC21 report identifies concrete verifier/path gaps; no packaging/profile/default mutations delegated. |
| Pauli / dc-review-data | tests/integration/test_design_c_populated_upgrade.py + docs/implementation/design-c-review-data.md only | C4 `a2a5f2d4` 35 actual checks, C1 `1b12c19f` independent report native pins; hidden import normal close, two personal results and original hashes retained. Current full populated upgrade/restore harness uses real producers. |
| Russell / dc-review-assessment | memory/repository.py + memory/service.py + focused Memory tests; report-only independent C1/C4 recheck after commit | C3 fresh canonical fingerprint after boundary cancellation; terminal explicit cancellation/suppression/source invalidity must not retry. |
| Poincare / dc-review-readers | Notes owner note_api/models/service and Knowledge CAS/retention; existing Reader source/test lease for R7 | Backend notes published; original prerequisite e0e51784 integrated separately as820d1906. R7 typed page/sheet/row position rehydrate/report remains active. |
| Kant / dc-home | study/home_service.py + tests/study/test_home_suggestions.py only | C2 actual captured whole-attempt Memory scope/correction repair; 24 focused checks passed, full Home/Nightly including actual connected Home run underway. |

The hidden c3 controller closed normally after real Study pause/reopen/finish and
Test normal restart/deadline results. Narrow/200% results were inspected; receipt
index and final readonly persistence audit are still being assembled. No live
provider/account or owner profile was used. DC20 is active; DC21 preparation is
an audit, with no matching C package/default cutover claimed.

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

### Attachment and import prerequisites — continuation from 2122f875

Integrated actual ordinary attachment producer as aef0a6c4 (source 6a633ae2),
chat/legacy deletion callers as 8cfa395e (source ce9567c2), and router mount as
d8dcc056. The assembled migration/attachment/conversation batch passed 64
checks with one test-only migration-name lookup failure. Its corrected import
migration suite passed all seven checks. Receipts are
C:/Renulus/scratch/design-c/integration/attachments-import005-run1.xml and
C:/Renulus/scratch/design-c/integration/import005-run2.xml; the initial failure
is retained. Owner/attachment revocation, journal-before-delete, rollback,
locked-original restart cleanup and temporary byte isolation use real owners.

Lead publishes assessment005, exact contract inventory, test_import tombstone,
unavailable live references and restore interruption for explicit private imports.
Pauli owns only new assessment/import_models.py, import_service.py, import_api.py,
modules/imports and tests/assessment/test_saved_imports.py. The lead separately
reserves assessment/fictionalisation.py, its tests and the trusted publication
method in generation_service.py; Zeno owns new learn/chat_test_* and Chat callers.
Six existing workers continue disjoint leases. No ticket is closed by these
prerequisites. The historical 18 normalization flags remain unstaged. Controller
c02 was closed normally before loading the new backend; owner state is untouched.

### Connected assessment, private practice and Study help — continuation from efada051

The lead integrated private paste imports, canonical whole-attempt evidence, the
volatile ChatTest producer and actual File review/upload. Trusted fictionalisation
and independent review are committed at dce4d88f; actual 5/10/20 publication to
saved versions and whole Study replay is integrated at 6cdf0d35. Raw source/request
identities remain volatile. Home consumes scalar evidence at 5fbcd42a; actual Chat
attachment review is efada051. Library import extraction and connected default
Home consumers remain with their owners.

The lead reserves storage/publication.py, storage/study_help.py,
storage/study_help_api.py, database.py, server.py and shared shell/platform paths
for current recorded-exposure receipts, key-free question preparation and inherited
publication guards. Receipts and File handoffs live only in React memory. The
shared routing slice forwards matching attachment intents, guards reader/workspace
requests and restores wrapper Case practice to its typed Chat. Lead additionally
reserves learn/conversation_stream.py temporarily for neutral interruption
bookkeeping when a Study receipt becomes stale; Zeno continues disjoint Chat UI
and API callers. Notes creation/editing remains a real prerequisite.

Validation: seven actual Recovery JSON migration checks, 31 whole-attempt/policy
checks, five focused neutral-route checks and seven Study-help checks pass. The
first imports/policy aggregate had four fixture errors (missing terms), corrected
before the 31-pass run; its receipt is retained. Renderer checks pass 43/43, and
the exact canonical TypeScript/Vite/Electron build passes. Receipts are under
C:/Renulus/scratch/design-c/integration/: import005-actual-recovery.xml,
imports-policy-assembled.xml, whole-policy-final.xml, policy-neutral-final.xml and
study-help-01.xml. Actual delayed Chat completion and safe failure bookkeeping,
Notes, full reader help and combined hidden acceptance remain open. No ticket
closure or installed default cutover is claimed.

Actual delayed Chat regression reproduced a stale Study receipt leaving the saved
command running despite refusing assistant publication (study-chat-red.xml). A
fixed neutral SQL fallback now closes only an existing running command/Learn run
as interrupted; it cannot write messages, drafts, sidecars or evidence, recreate a
deleted owner or overwrite a terminal winner. The affected Study-help/conversation
suite passes 39/39 in study-chat-green.xml (168.01s). Lead releases
learn/conversation_stream.py back to Zeno after this checkpoint.

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

### Published contracts and feature reservations

The lead reviewed `design-c/1` validators at `527677f3`, after the exact-name
proposals, and integrated all three pass-1 reports (`db96f4a0`, `388687c2`,
`335e5a86`). Final contract follow-ups are integrated through `17f5d6a4`; the
27-case suite and all eleven committed fixture digests passed. Feature development may use these committed shapes
and the accepted additive clarifications in section 10 of the existing spec.
Ticket closure still requires the integrated producers and consumers.

| Owner | Reserved write paths | Scope / synthetic profile |
| --- | --- | --- |
| Lead | All module `schema.sql` and `migrations/` paths, storage, server, shared renderer/platform/shell/UI, `apps/desktop/electron/`, `tools/renulus-control/`, root configuration/locks, cross-module tests | Schema sequencing, isolation/controller, shell/policy and integration; `integration` |
| Reader worker (Poincare) | `runtime/renulus/knowledge/` except schema/migrations; `apps/desktop/src/modules/library/`, new `apps/desktop/src/modules/reader/`; `tests/knowledge/`, `tests/integration/test_design_c_readers.py` | DC08 and Library DC10; `readers` |
| Collection worker (Pauli) | New `runtime/renulus/assessment/test_repository.py`, `test_api.py`, `test_models.py`; new `apps/desktop/src/modules/tests/`; `tests/assessment/test_saved_tests.py` | DC12 collection/version/report and legacy mapping; `saved-tests` |
| Attempt worker (Russell) | New `runtime/renulus/assessment/attempt_repository.py`, `attempt_api.py`, `attempt_models.py`; new `apps/desktop/src/modules/attempts/`; `tests/assessment/test_whole_attempts.py` | DC13 then DC14/DC15 core; `attempts` |
| Chat/projects worker (Zeno) | `runtime/renulus/learn/`, `cases/` except schema/migrations; new Study `project_repository.py`, `project_api.py`, `project_models.py`; new frontend `chat/`, `projects/` plus existing `learn/`, `cases/`; `tests/learn/`, `tests/cases/`, new integration conversation/project tests | DC04/DC05, then project DC09; `chat-projects` |
| Workspace worker (Aquinas) | New `apps/desktop/src/modules/workspace/` and colocated tests | DC07 typed tab/layout adapters after DC01 report; `workspace` |
| Home/suggestions worker | New Study `home_service.py`, `home_api.py`, `home_models.py`; new frontend `modules/home/`; `tests/study/test_home_suggestions.py` | DC06 name/home/daily cache, Quick practice consumer pending DC16; `home` |

Existing assessment repository/router and generation files remain lead-held.
Collection and attempt workers have disjoint repositories/routers and use a
small private pinned-version interface. No worker edits another reservation.
Feature workers merge the next committed reservation baseline into
their clean existing worktree. Separate owned profiles remain outside Git.

### Additive schema publication and policy seam

Knowledge003 is now published with exact attachment/original inventories and a
separate metadata/rights/preview sidecar. The reader router joins the assembled
API. Eleven migration/policy/typed-recovery checks passed; installed inventory
checks now include these tables. The reader run passed 33 checks and exposed
three stale expectations that assumed the schema was absent; the reader owner
is updating those tests. Typed attachment-original ZIP promotion, deletion and
rollback evidence remains open and is owned by integration.

Lead migrations Learn002, Cases003, Study002 and Assessment003/004 implement
the published sidecars, memberships, goals, collection/version/report/job records
and independent attempt snapshots. Exact installed column inventories are checked
against the final Python contracts. Command outcomes have separate saved-only
`conversation_commands`, `study_project_commands` and `assessment_attempt_commands`
ledgers; no command has a foreign key to its live target. Hash/outcome replay
remains subject to the current assessment policy. Temporary commands stay volatile.
Knowledge003 is published separately with its original/media recovery handling.

Shared storage seams are `assessment_policy.policy_snapshot(conn)`,
`require_assistance(conn, expected_revision=...)`, `advance_policy(conn)` and
`invalidation.context_epoch_in(conn)`. Test start/finalisation advances policy
inside the attempt transaction. Producers capture and recheck policy/context
before publication; their private pinned content stays out of renderer responses.
The lead will assemble feature routers only from reviewed connected slices.

The canonical root and documentation baseline ancestry were rechecked. Linked
worktrees use their exact per-worktree root after removal of the shared root
override. Eighteen historical status-only normalization flags remain preserved.
An earlier migration run failed before setup because its scratch parent did not
exist; the corrected run passed all 35 migration/contract checks.

`db6852f9` publishes the exact additive migrations and policy helper; ten focused
checks passed (`integration/migration04.xml`). Home's first slice, chat sidecars
and workspace panel are integrated at `1a242f93`, `94b6e9bc` and `96fefd5b`.
Their consumers and feature acceptance remain open. The lead's HTTP policy
boundary blocks legacy help, source/reader requests, generated-practice replay
and key-containing export/restore while a Test is active. Connection settings,
neutral policy and recovery status stay reachable. A late-read reproduction
confirms a private answer cannot publish after Test start. Membership unlink
tombstones prevent an old export reviving a removed shared-document link.
Four focused checks passed in `integration/policy02.xml`; full attempt expiry,
provider cancellation and integrated UI/reader publication still require DC14.

### Connected slices and next reservations

The lead integrated Home persistence/name receipts at `2702ff08`, conversation
lifecycle/paged history at `ae1ee175`, and the collection/version/report slice at
`dda7d8da` + `ea62d7ce`. The collection handoff includes 17 actual SQLite/router
checks and five real-loopback renderer journeys; Home has 38 backend and ten
renderer checks in its updated lane. These are bounded feature evidence, not
closure of combined journeys. The C shell and shared Workspace wiring are still
under integration. The historical normalization flags remain unstaged.

The Workspace worker also reserves only
`docs/implementation/design-c-review-integration.md` for independent pass 2
review after its pending Workspace persistence slice, using hidden owned root
`C:/Renulus/scratch/dcctl/rev1`. The lead reserves new
`runtime/renulus/storage/workspace.py`, `workspace_api.py`,
`tests/integration/test_design_c_workspace.py` and shared shell adapters for
canonical Workspace access/preferences. No feature worker edits these paths.

With DC12 contracts and real producers integrated, the collection worker moves
to DC16. Its additional exact reservation is new
`runtime/renulus/assessment/generation_service.py`, `generation_models.py`,
`generation_api.py`, new `apps/desktop/src/modules/generation/`, and
`tests/assessment/test_saved_generation.py`. Existing generated-practice files,
collection/attempt routers and repositories, schema/migrations and server wiring
remain with their current owners. The worker reuses the existing selected-provider
and small-batch validators, and publishes through the trusted saved-version seam.
No DC16 closure precedes actual integrated 5/10/20, recovery and cancellation proof.

The lead's C shell baseline connects default Home and Tests, saved-identity routes,
typed volatile send/passage intents and the contextual Workspace provider. Local
Workspace preferences contain only validated saved references; temporary contexts
are refused, removed originals retain already-known unavailable tabs, and deleted
contexts no longer reopen. Display permission is independent from extraction.
Five real assembled-API/SQLite Workspace checks passed in
`integration/workspace01.xml`; 25 shell/navigation/Workspace renderer regressions,
desktop typecheck and build passed. The controller accepts the eight declared file
categories and collapsed-shell readiness; all 47 guard checks passed using owned
root `C:/Renulus/scratch/dcctl/u04`. Reader and attachment adapters still require
their producer integration before connected acceptance. Historical profile,
originals, credentials and installed Flow selection remain untouched.

The connected Chat page is integrated at `c19d1493`. The lead corrected modern
saved-chat selection to use its typed retention/context rather than inherited
legacy Case snapshot state, wires directly created/deleted chats into Workspace
context without remounting the route, and keeps one content heading per screen.
Typed run cancellation remains reachable during Test while run/text disclosures
stay blocked. Fourteen affected shell checks, three policy checks, typecheck and
build passed. Hidden source pixels cover wide/narrow Home and drawer reachability;
the latest connected build restarted in the same owned `dcctl/c01` profile.
These checks do not yet establish full Chat/reader/attempt or delivery acceptance.

The owner requested a current twenty-minute progress follow-up. The app heartbeat
`renulus-design-c-progress` is active on this task and continues unfinished
authorised work without duplicating active lanes or repeating unchanged tests.
The historical paused delivery heartbeat remains paused.

DC11 lead-owned paths are new storage `search.py`/search_api.py and shell
`LocalSearchResults.tsx` with their integration/component tests. They use the
saved-only canonical query and shared policy contract recorded in the existing
spec; no new search table, temporary cache, provider work or duplicate ownership
is introduced. Actual search receipt is `integration/search01.xml`. The hidden
source `dcctl/c01` check also verified the narrow Workspace focused pane and
explicit Back to chat, then an offline Home handoff kept its saved message and
draft with a truthful connection-required failure. Screenshot captures 3/4 and
the owned receipt remain outside Git. This is bounded source evidence.

After the Home evidence checkpoint, Kant additionally owns new
`runtime/renulus/study/nightly_service.py`, `nightly_models.py`,
`nightly_api.py`, new `apps/desktop/src/modules/nightly/` and
`tests/study/test_design_c_nightly.py` for DC19. The lead retains all DDL,
server/preferences export wiring, shared Settings and generation producer files.
This lane reuses published saved generation and canonical eligible inputs;
no provider or source fallback, duplicated scheduler or renderer attestation.

The entries below preserve earlier implementation evidence. Their Flow selection,
branches, paths, issue status, time windows and heartbeat instructions describe
those dated runs; they are not assignments or scheduling instructions for C.
The current installed baseline and canonical paths are in
[the workspace guide](../WORKSPACE.md) and [project brief](../PROJECT_BRIEF.md).

### Design C integration continuation — October 10

Canonical `codex/design-c-integration` retains documentation baseline `528025ff`.
Historical normalization-only flags remain unstaged. Owner profile, originals,
credentials and installed Flow selection are untouched. The existing
`renulus-design-c-progress` twenty-minute heartbeat remains active.

Shared baseline `48729826` publishes typed attachment originals `f61799c5`,
epoch-independent restore interruption `a9d657e8`, postcommit cleanup journal
`e66bf8fe`, neutral run reads `70762aa8` and safe Nightly API/export assembly.
Recovery recorded 53 passes and two obsolete zero-preference assertions; the
updated six-case filter suite passes, proving local invalidation markers exist
while exported learner preferences remain absent. Receipts under
`C:/Renulus/scratch/design-c/integration/`: `attachment-recovery01.xml`,
`filter-markers02.xml`, `restore-invalidation02.xml` (12 passes),
`neutral-policy03.xml` (four passes), `cleanup-policy02.xml` (seven passes).
Restore retains validated work and never resumes provider calls.

Case context/pinned teaching `e80e046e`, Nightly connected hook tests `0acf3fb6`,
generator orphan reconciliation `bee764de`, Nightly renderer `91a7148a`, actual
Settings/Tests mounts `f24fbfce` and scheduler recovery calls `837ea3d0` integrated.
Lead inspected Figma Nightly Off `83:7590` and reused C tokens/primitives/assets.
Build/typecheck, 69 affected renderer checks and one real-router preferences/
handoff check passed. Hidden source-app checks run in owned
`C:/Renulus/scratch/dcctl/c02`; Kant owns independent Nightly pixels/reopen.
Pauli's final generation/scheduler evidence is 89 actual-DDL/ProviderManager
synthetic checks at `C:/Renulus/scratch/design-c/generation/nightly-assembled-final01.xml`.
Kant's 44 scheduler cases are covered by corrected recovery/neutral runs; the
original failed assertion receipts remain dated evidence, not silent clean passes.

Reservations: Russell owns whole attempts; Poincare owns ordinary attachment/
reader producers; Zeno owns Case/conversation callers and cleanup consumption;
Kant owns Nightly; Aquinas owns Workspace persistence then independent pass 2.
Pauli's new DC17 lease is only `assessment/import_{models,service,api}.py`,
`modules/imports/` and `tests/assessment/test_saved_imports.py`. Lead retains
schemas/migrations/shared contracts/typed relations, shell/Settings/root files
and Tests collection integration. Import persistence waits for concrete DDL.
All feature tickets remain open at their actual producer/consumer gates.

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
