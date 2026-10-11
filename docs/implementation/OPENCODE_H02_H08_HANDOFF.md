# OpenCode H02–H08 implementation ledger

2026-10-11. Integration checkout:
`C:/Users/karol/.codex/worktrees/opencode-foundations/repo`, branch
`codex/opencode-foundations`. Verified clean starting commit:
`74e3424b5c03ac4616834911c13faef1c064d09c`. Sole remote is Renulus origin.

The owner explicitly authorized implementation, local commits, directed workers,
dependency-driven parallelism, independent reviews and hidden desktop acceptance
for **H02–H08**. This supersedes the historical research-only status in these
tickets. H00/H01/H24 are consumed, with their evidence and limitations preserved.
The immutable planning snapshot, other checkouts, installed launcher and private
profile/credentials remain protected. No incidental live provider usage, release,
installation, push or downstream-ticket expansion is authorized.

## Resumed integration — October 11

Parent consumed native tools (`ce85b7c5`), saved bridge (`1631e767`),
configuration authority (`a85e1ee0`), controlled Library SDK composition
(`63dde885`), pre-dispatch native input binding (`a884ef17`), failed-store
admission fence/read-only recovery lookup (`def4b12b`), Python Library adapter
(`12a88d79`) and local revision resolver (`845c1f0c`). These are preparation,
not H02–H08 acceptance. LearnService project pin and shared relation registration
remain integration work.

Independent standards review found activation missing from close's drain.
Controlled lower storage delay with actual SDK/SQLite/ownership reproduced
close returning closed before activation completed (`activation/review-drain-red02.xml`).
Activation now registers its existing writer lease before its first await,
retaining ownership through success/failure and close.
`activation/review-drain-green02.xml`: 13 passed; TypeScript exited 0.
`review-drain-red01.xml` did not reproduce the race. The first green attempt
failed only on an incorrect expected ownership error string; its receipt is
retained. Memory/conversation/configuration review fixes remain open in their lanes.

Runtime migration 004 is integrated for stable dispatch-purpose accounting;
002 configuration and 003 paired stores are immutable applied predecessors.
Native publication stages exact reference-only JSON in the submitted receipt
inside the same canonical transaction before memory lineage publication,
then marks completed atomically. Public resolution/history requires completed.

Subsequent parent integrations (source handoffs remain in their lane receipts):

| Parent commit | Integrated result |
| --- | --- |
| `ecfba55e` | Reverse callback IPC, source `f27fee89` |
| `9a1893eb` | Selected-provider preparation, source `07da2a3e` |
| `c3cee829` | Final Library read/publication guards, source `650f3e44` |
| `8ed52b82` | Three actual SDK/private-pipe tests, source `96dc85f1` |
| `dde84eec` | Persistent memory support lineage, source `433ac165` |
| `6fea1787` | Lost-ack native reconciliation, source `93d3a39d` |
| `ba368855` | Adaptive byte-bounded history pages, source `6bee8f6a` |
| `baace4ae` | Stable auxiliary dispatch purpose, source `0e1322f0` |

Activation correction independent Standards and Spec reviews close the prior
P1; focused Standards rerun passed two native tests with zero dispatch. Bounded
004 review reports zero material Standards/Spec findings and confirms the
122-case receipt matches the integrated source. These are bounded closures,
not complete H02/H04 acceptance.

LearningOwner composes actual paired activation, canonical input authority,
native Library callbacks and saved publication. `learning/green05.xml` exposed
a nested writer: a supplied-connection Library guard called the full callback
predicate, which opened another `BEGIN IMMEDIATE`. The local guard now checks
the exact binding and cancellation in its caller's connection.
`learning/green06.xml`: **1 passed**, actual SDK/private IPC, real offline
FastEmbed/LanceDB, two counted TestLLM dispatches, one native receipt/mapping,
citation opening and no legacy transcript. Earlier failed receipts remain
retained. The explicit owner installation is preparation; normal server/Settings
assembly, run-aware recovery checks, context filtering and memory roundtrip
remain required. Migrated automatic capture stays disabled.

## Goal and continuation

The active goal is to implement and verify every required H02–H08 criterion.
Heartbeat `renulus-h02-h08-completion` checks this chat every 30 minutes and
continues unfinished authorized work. It must stop when the goal is achieved.
Read this ledger and actual Git/agent state before resuming; do not duplicate a
running lane or treat prepared work as dependent-ticket acceptance.

Public test seams are the existing domain/conversation commands and Harness
facade, as specified in the accepted plan and this implementation instruction.
Use the real SDK/stores/domain engines with counting synthetic external inference.
Lower transport fault injection is reserved for failures the public seam cannot
express. Account and native package acceptance retain their separate gates.

## Readiness and ownership

| Ticket | Current state | Required predecessors | Integration outcome |
| --- | --- | --- | --- |
| H02 | Implementing | H01 accepted | Actual paired activation, Library native tool, one publication/engine mapping and shared events |
| H03 | Parallel adapter preparation | H02 | Selected protected subscription routes, capabilities, final transport admission/limits |
| H04 | Parallel authority preparation | H03 | One immutable configuration authority, healthy restart activation, role/attempt policy |
| H05 | Parallel lineage preparation | H02/H04/H24 | Corrected/deleted memory remains revoked; actual one-slot extraction round trip |
| H06 | Pending | H05 | Saved migration, one transcript owner, receipt retirement/deletion |
| H07 | Pending | H05 | Native bounded children, inherited authority and actual cancellation settlement |
| H08 | Pending | H04/H06 | Explicit pinned instructions/skills and reinjection under current revocations |

After H05, H06/H07 may proceed together. H08 may overlap H07 after H06.
Integration owns shared contracts, canonical migrations, Services assembly,
host/IPC, configuration authority, dependency locks and cross-module fixtures.

| Lane | Checkout | Worker | Reserved write scope |
| --- | --- | --- | --- |
| Library | `C:/Users/karol/.codex/worktrees/oc-library/repo` | Sartre / `01a129a8-b899-76f2-81b4-31fbcfec0e0e` | Dedicated Python Library bridge, native domain-tools module, dedicated tests |
| Providers | `C:/Users/karol/.codex/worktrees/oc-providers/repo` | Arendt / `01a129a8-ba65-7a72-b7d0-f52a04732663` | Existing protected provider adapters/policy/auth, dedicated harness provider adapter/tests |
| Memory | `C:/Users/karol/.codex/worktrees/oc-memory/repo` | Russell / `01a129a8-c092-7d92-b529-30cc2e35183f` | Memory owner/support lineage/tests; shared schema proposals require coordination |
| Conversations | `C:/Users/karol/.codex/worktrees/oc-conversations/repo` | Ohm / `01a129aa-de12-7823-a972-f74a8b71133f` | Dedicated H02 bridge, Learn 003 migration, saved-producer selection and tests; parent owns LearnService |
| Configuration | `C:/Users/karol/.codex/worktrees/oc-configuration/repo` | Nietzsche / `01a129aa-dfab-7030-b0c0-5b6da297e825` | Dedicated immutable authority/role/attempt modules, runtime 002 migration, tests |
| Reverse IPC | `C:/Users/karol/.codex/worktrees/oc-domain-ipc/repo` | Turing the 2nd / `01a129b6-f96c-76b0-a3b8-f731bdcf74de` | Dedicated domain callback modules/tests, harness_process.py and ipc.ts after parent prerequisite commit/lease |

Workers use TDD/implement and relevant research/design/domain skills. Each
hands off exact changes, commits, red/green receipts and limitations. They do
not edit integration-owned files or enable migrated automatic capture early.

## Evidence

No new acceptance is claimed yet. Owned synthetic receipts go under
`C:/Renulus/scratch/oc-h02-h08/`. Reuse managed Python, pinned Node/cohort and
reviewed public helper assets. Relevant inherited failures from the foundation
ledger remain assigned to H02 (Library owners), H03 (provider access/capability),
H05 (memory revisions); unrelated failure families retain their later owners.

Independent standards/specification review fixed point is `74e3424b`. Verify
each material finding before repair. Record full runs separately from targeted
repairs or reconciled unions. Desktop acceptance uses APP_CONTROL.md and hidden
app-scoped synthetic profiles, including normal shutdown and persisted reopen.

## Activation prerequisite — verified, not H02 acceptance

The parent adds logical canonical writer admission and quiescence, active-profile
reopen without repreparation, actual paired schema/identity/native migration
validation, atomic selected-manifest publication and owned activation observation.
`host.stores.activate` takes an empty payload and returns the active manifest.
The domain migration is `runtime-003-harness-stores`; configuration owns
`runtime-002-harness-configuration`. Domain identity is stamped before sealing
writers; native identity is stamped in the supported underscore namespace under
native quiescence. No transaction/physical lock is held across IPC.

Observer cancellation does not cancel the activation owner or release its lease.
Actual process/pipe settlement is separate from a clean close receipt: process
death can release native write ownership while command outcomes remain uncertain.
Reverse IPC must extend this observation to include owned callback finalizers.

Receipts under `C:/Renulus/scratch/oc-h02-h08/activation/`:

| Run | Exact result | Qualification |
| --- | --- | --- |
| cycle01-red.xml / cycle01-green.xml | 1 failed / 1 passed | Writer barrier |
| cycle02-red.xml / cycle02-green.xml | 1 failed, 1 passed / 24 passed | Active selection loader and profile regression |
| native-cycle01-red.xml / native-cycle01-green.xml | 1 failed / 1 passed | Actual SDK activation, zero model dispatch |
| native-cycle02-red.xml / native-cycle02-green.xml | 1 failed / 1 passed | Identity substitution rejected |
| python-regression01.xml | 149 passed | Earlier activation/profile/process/contracts run |
| python-regression02.xml | 150 passed | Adds fixed interruption writer admission |
| native-regression01.xml | 14 passed | Earlier host/ownership/activation checks |
| native-regression02.xml | 14 passed, 0 failures | Repeats affected host/ownership/activation after identity substitution fix |
| ipc-cycle01-green.xml | 1 passed | Actual Python Database + native SDK stores + authenticated IPC, max_inflight=1, zero model calls; reopen |
| cycle03-red.xml | 1 failed, 3 passed | Fixed interruption bypass reproduced before fix |
| cycle04b-red.xml / cycle04-green.xml | 1 failed, 4 passed / 51 passed | Actual process death settlement and transport regression |
| cancel-sdk-green.xml | 7 passed | Observer cancellation scripted delay plus actual SDK/IPC activate/reopen |

The initial cycle04-red is a fixture error (missing domain_path), not a behavior
regression. Failed native/schema/IPC green attempts remain retained; the pinned
schema uses session_v2.metadata/idle_outcome and manifest comparison now uses
structural equality across Python/Node JSON key order. Affected consumer
TypeScript check passed after these changes. Counts above are distinct runs, not
one combined green suite. Connected startup, Library tool, publication and UI
acceptance remain open.

## Published shared contracts

Memory owns additive `memory/migrations/002.sql`, `AnswerInputs(version=1,
inputs, dependencies)`, local-only `publish_answer_lineage_in`, and async
`resolve_completed_answer` outside canonical transactions/physical capture locks.
Within-group support is joint; independent groups may independently support a
fact; echoes inherit ancestor roots. Unknown/revoked assistant history is removed
before dispatch. Migrated automatic capture remains disabled until H05 passes.
Parent owns shared relation/export registration and Learn publication wiring.

Conversations own additive `learn/migrations/003-harness-bridge.sql`. Mapping
columns: thread_id/profile_id/store_id/session_id/mapping_json/create_request_id/
process_generation. Answer columns: run_id/thread_id/request_digest/state/input_id/
reference_json/publication_digest/command_request_id/process_generation. The
bridge accepts parent local dependency checks and publication callbacks; no
duplicate transcript. Parent guards legacy LearnService.prepare for mapped and
pending harness-owned threads. Actual callback closure is rechecked at callback
and publication, with native get/messages projected through existing events.

Configuration preparation reports 96 passing synthetic SQLite cases (worker
report, integration verification pending). Authority health binds exact version/
grant epoch/final registry hash; actual stopped-owner proof remains parent-owned.
Durable attempts reserve before dispatch and retain uncertain debits. Revocation
overlay and require_current can share parent publication transactions. Restore
must account for immutable-version SQL triggers; H18 remains downstream.

The legacy Learn writer guard reproduced both pending/committed mapping failures
in `conversations/parent-owner-red.xml` (2 failed).
`conversations/parent-owner-green.xml` passes 13 cases including existing Learn
persistence/cancellation/recall regression (one inherited TestClient deprecation
warning). It checks ownership before admission/replay and again at write commit;
any reserved mapping blocks a second legacy transcript. This is a synthetic owner
fixture, not native mapping acceptance. Shared ownership-only restore relations
for reference/lineage tables are prepared; no generic truth-support cascade or
H18 paired recovery acceptance is claimed.
