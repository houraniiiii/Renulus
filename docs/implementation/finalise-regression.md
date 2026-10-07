# Backend application regression finalisation

Evidence dated October 5, 2026. Owned branch:
`codex/finalise-backend-checks-8c6c4b18` (recovered from
`build/finalise-backend-checks`).
Recovered application baseline: **9d26f1eedf31cd488b9aab5837a105ee152d9efa**.
This lane owns the regression runner, its receipt tests, this report and the
release-recovery assertions in `tests/backup/test_content_release_compatibility.py`
and `tests/backup/test_segmented_engine_and_history.py`. It edits no production
code, shared schemas, dependencies, helpers or native/profile state. The recovered
baseline is not the parent's final product revision. The parent owns
`tests/backup/test_prepare_delivery_profile.py` and its current-bank assertion.

Recovered on October 5 at **14:29 UTC**: b3 is interrupted; b3h and b3p have
complete passing receipts. At that recovery checkpoint no application or
harness test was rerun. The parent subsequently integrated runner commits
`30e88174` and `2d16bd58` as `eb821aa3` and `8c6c4b18`, integrated the
content/assessment/packaging prerequisites, and released one application-only
regression slot. The report edit was preserved while this same worktree switched
to unpublished branch `codex/finalise-backend-checks-8c6c4b18` at exact source
**8c6c4b181281a0d5a6057ff032ab504f82f4e20e**. No prerequisite is a new lane
change. The subsequent owned repair is `35187437744440740f7e885633e0810e62a12598`,
integrated by the parent as `324af6f28d61d4fc3971977d3316ebcff950cbfe`. The recovered
report edits are preserved; this handoff adds only the report.

**Current bounded acceptance:** the parent explicitly requested validation of
integrated **b473ecb3d58ea7dabcef83bac8d0335a420d45ab**. Its strict runner passed
**28/28 harness tests and all five affected application tests**, with final
JUnit, terminal exit 0, unchanged HEAD/production/tests/runner and no unexpected
module sources or guard violations. The original b4 full run remains failed
and nonaccepted. No subsequent full sweep was started. The parent decides
whether a further broad run is needed after reviewing the final source delta.

## Authorised integrated application regression

One new application-only run started at **14:34:14.100375 UTC** on October 5.
Terminal session **94649**, actual interpreter PID **21000**, receipt directory
`C:/rn-finalise-20261005/b4-8c6c4b18/`, log
`C:/rn-finalise-20261005/b4-8c6c4b18.log`. Its pinned source is `8c6c4b18`,
including accepted current-PC unsigned specification `793eddb4`. Production,
contracts, tests, runner and dependencies were clean; only this report was
modified. Recorded interpreter identity is in
`C:/rn-finalise-20261005/b4-8c6c4b18.process.json`.
Execution root is **`C:/rn-finalise-20261005/lanes/backend-checks`**, isolated
from parent integration. Its HEAD and tested files remain pinned throughout
the run; no duplicate test checkout or process is launched.

Collection records **1,271 unique identities**, **1,219 application selections**
and **52 exclusions**. The exact exclusion identity set equals b3's appendix,
not only its counts. Counts by area are assessment 94, backup 128, cases 90,
content 121, integration 13, knowledge 430, Learn 46, memory 46, retrieval 63,
runtime 130, Study 5 and updates 53. The run finished at **15:06:49 UTC**:
**1,214 passed, five failed**, with no skips and valid **1,219-case JUnit**.
All 3,657 phase events reconcile: 1,219 passed setups, 1,214 passed calls, five
failed calls and 1,219 passed teardowns, with one of each phase per selected
identity. Session and result record pytest exit **1**; the recorded process
terminal exit is **2**, because the runner also rejected source attribution.
`complete: true`, `source_unchanged: false`, `accepted_stage_pass: false`, no
runner error and no guard violations. This is a completed failed application
run, not an interrupted run or a full application pass.

The terminal receipt is `C:/rn-finalise-20261005/b4-8c6c4b18.terminal.json`.
JUnit SHA-256 is
`1a26539447f9ef8b290b897b897ea14a5b8fab7264d634d8dcb33ed41571662b`;
module-source receipt SHA-256 is
`36a37154badb465f47f852562167e60eafae95d3b9e582015b8a9acd405bed35`.

| Source path | Recorded Git tree/blob identity at `8c6c4b18` |
| --- | --- |
| `runtime` | `3212d73065592d598d27690151f7fb6a8a4ade2c` |
| `upstream/hermes` | `01eb1c8a37a5cec57e3099f5a7bf7713f4862456` |
| `tests` | `15a7438040d0fa47960d06104e9515234798ce54` |
| `content` | `92124273440676d71e7cb00b4886d07f40c2a236` |
| `packaging/runtime` | `c04717446e20ea71c95237fa2354838c35e98da7` |
| `pyproject.toml` | `df7ad2a92b0d8ac8136778ad7fbda0828e486156` |
| `uv.lock` | `6fc5f725e427e1da058ec330c233e5b5dea18825` |

Actual package versions, offline/resource policy and runner SHA-256 are in
`b4-8c6c4b18/run.json`. The initial free disk was 325,314,461,696 bytes; the
floor remains 12 GiB and CPU thread bounds remain two. The observed minimum free
disk was 321,362,141,184 bytes. No old receipt is reused.
Source attribution stays at `8c6c4b18` even if parent integration advances.

## b4 failure diagnosis and reviewed repair

The JSON and ZIP legacy-bank restore tests and the segmented legacy-history
restore test failed before restoration because their target assertion required
pack `1.1.0`, while this source correctly activates the published `1.1.1` pack.
The cold filelock startup and cold Hermes context tests failed in the runner's
Windows subprocess audit: `shlex.split(..., posix=False)` attempted to parse a
serialized multiline Python `-c` program and raised `ValueError: No closing
quotation`. Neither failure establishes a production restore or context defect.

All **95** recorded Renulus module paths were examined. Exactly **one** lies
outside this checkout's `runtime/`:

- Name: `renulus.memory._vendored_hermes_backend`.
- Path: `C:/rn-finalise-20261005/lanes/backend-checks/upstream/hermes/plugins/memory/mem0/_backend.py`.

`runtime/renulus/memory/engine.py` loads that exact file under that exact alias;
the b4 Git tree includes the adopted Hermes source. The old source predicate
rejected every module outside `runtime/`, so this path alone necessarily makes
its combined source result false. No foreign runtime module is recorded. The
old receipt did not split HEAD, working-tree and module checks; separate terminal
HEAD/cleanliness booleans are not reconstructed or invented for b4. The original
false source result and failed application result remain unchanged.

Repair `35187437` classifies the executable before inspecting Python arguments,
preserves the restrictions on non-Python commands, and permits only the exact
adopted module name/path pair. Its harness rejects alternate names, alternate
paths, resolved foreign paths, disguised shell executables and malformed
non-Python commands. The runner now requires clean tests, runner and packaging
sources at entry and records individual source checks at completion.

The three restore assertions validate the current published pack, its installed
SHA-256 and exact API manifest/question/case/cited-source identities. They retain
the 160-question/26-case minimum, exact historical keys and both profiles' learner
history. The same snapshot must survive restore, duplicate restore and reopening.
This verifies preservation of the current target rather than merely accepting a
different version string. The parent's separate delivery-profile assertion in
`b473ecb3` likewise preserves exact current-bank identity; its engine test remains
outside this application-only selection.

## Completed bounded repair validation

No completed post-fix receipt or matching active runner was present when this
lane resumed. First, the repair source `35187437` was checked once in the original
lane with its preserved report edits and clean tested paths. The parent then
explicitly requested the same bounded checks on integrated `b473ecb3`. A new
clean detached checkout at `C:/rn-finalise-20261005/checks/backend-b473ecb3` kept
that exact source isolated from integration. Neither test checkout's HEAD changed
during its runs. The interrupted tool handle for b6h was recovered from its
completed receipts; that harness was not repeated.

All paths in this table are under `C:/rn-finalise-20261005/`. Each directory
contains `run.json`, `inventory.json`, `events.jsonl`, `session.json`,
`outcomes.json`, `module-sources.json`, `result.json` and `results.xml`; adjacent
`.log` and `.terminal.json` files preserve logs and the observed child exit.

| Receipt directory | Exact source | Result | Completion UTC | Terminal exit | Phase events |
| --- | --- | --- | --- | ---: | ---: |
| `b5h-35187437-20261005T155342Z/` | `35187437744440740f7e885633e0810e62a12598` | Harness 28/28 | 15:53:51 | 0 | 84 |
| `b5p-35187437-20261005T155451Z/` | `35187437744440740f7e885633e0810e62a12598` | Affected application 5/5 | 15:56:14 | 0 | 15 |
| `b6h-b473ecb3-20261005T155837Z/` | `b473ecb3d58ea7dabcef83bac8d0335a420d45ab` | Harness 28/28 | 15:58:46 | 0 | 84 |
| `b6p-b473ecb3-20261005T160018Z/` | `b473ecb3d58ea7dabcef83bac8d0335a420d45ab` | Affected application 5/5 | 16:02:46 | 0 | 15 |

For every b5/b6 stage: `complete`, `source_unchanged` and `accepted_stage_pass`
are true; pytest/session/process exits are 0; `head_unchanged`,
`production_unchanged` and `tests_and_runner_unchanged` are true;
`unexpected_module_sources` is empty; runner errors, collection errors, guard
violations, skips and duplicate identities/phases are absent. Each selected
identity has exactly one passed setup, call and teardown. The harness loads no
product modules; both application selections record **91** Renulus modules from
their respective pinned `runtime/` roots, with no module outside those roots.
The adopted Mem0 alias boundary is checked by the harness and the actual b4
module-source receipt, without constructing an engine.

Tested runner SHA-256 for all b5/b6 stages:
`58012d7a5945bf5d5053d567d647e75663489684925adfc74ae86de51ecd2b53`.
JUnit SHA-256 anchors:

- b5h: `8a5690800af13b286ab055cb56db5632a7270c1db6518810d48da941255455e0`.
- b5p: `f31aa24c6378023372322c29453442e1cb20dd1de167e3089e0d0322c78d8ac2`.
- b6h: `f2bba46850bc710f29f59aa27e1aeb7e2baebe455283a3b6493e6efcc7896463`.
- b6p: `fb48cdccbc898a48f1745bffcdbd0637d8bc6610e370a9f1d5a1e1a5bcc1f94d`.

The b5/b6 application stages use only these exact selected identities:

- `tests/backup/test_content_release_compatibility.py::test_legacy_100_backup_keeps_historical_keys_and_sessions_without_downgrading_current_target[json]`.
- `tests/backup/test_content_release_compatibility.py::test_legacy_100_backup_keeps_historical_keys_and_sessions_without_downgrading_current_target[zip]`.
- `tests/backup/test_segmented_engine_and_history.py::test_segmented_legacy_bank_and_learner_history_keep_latest_target_selection`.
- `tests/runtime/test_helper_startup.py::test_real_cold_filelock_probe_is_profile_owned_then_warm_import_has_no_writes`.
- `tests/runtime/test_hermes_provenance.py::test_cold_hermes_context_does_not_create_native_state_or_log_files`.

The first two map to b4's former `_without_downgrading_110_target` names; the
remaining three are unchanged. These same five checks across two sources do not
become ten distinct application checks, and harness results are never added to
the application denominator. No model/helper construction, provider/native/paid
request or heavy test was run in this lane. The filelock check imports installed
Python dependencies, and the context check supplies its summary in-process.

Read-only reconciliation of b4 and all four b5/b6 stages passed. It compares
exact selected identities against JUnit, events and outcomes, including the IPv6
parameter containing `::`; verifies phase uniqueness, statuses, JUnit hashes,
session/process exits, recorded Git trees and resolved module paths. Evidence:

- `C:/rn-finalise-20261005/backend-reconcile-20261005.py`.
- `C:/rn-finalise-20261005/backend-reconciliation-b4-b5-b6-20261005.json`.

Reconciliation SHA-256:
`2caa6d5656b03275f0fb014ed4f44fe68ab2ea46373bec13f4cba234c228ee5b`.
It reads the original receipts without rewriting them or running tests.

## Integrated source and delta reconciliation

The b6 run manifests record these exact `b473ecb3` source identities:

| Source path | Git tree/blob identity |
| --- | --- |
| `runtime` | `bdc119012dc26a55aff1378ef391f8402a804181` |
| `upstream/hermes` | `01eb1c8a37a5cec57e3099f5a7bf7713f4862456` |
| `tests` | `157dd6748fd4ffa8aa98c7e1fe9e2ee6bd8108cb` |
| `content` | `4f07089704b6446dc859df368178bc84b6b4a122` |
| `packaging/runtime` | `c04717446e20ea71c95237fa2354838c35e98da7` |
| `pyproject.toml` | `df7ad2a92b0d8ac8136778ad7fbda0828e486156` |
| `uv.lock` | `6fc5f725e427e1da058ec330c233e5b5dea18825` |
| `scripts/run_backend_regression.py` | `d400f565726c8ba7ad1ee8b8fe3e34788a89c7f1` |

The adopted Hermes source, packaging runtime, dependency manifest and lock are
identical to b4; the repair source `35187437` also keeps b4's production trees
unchanged. Between b4 and `b473ecb3`, production changes are limited to
`assessment/generated_streaming.py`, `learn/api.py`, `study/api.py` and
`study/service.py` under `runtime/renulus/`, plus `content/README.md` and the new
`content/required-cells/renulus-foundations-1.1.1.json`. The runner and leased
repair tests are identical between `35187437` and `b473ecb3`. The parent adds the
delivery-profile assertion, response-close/learning-cancellation checks, required
content-cell checks and Study track/journey tests.

b6 accepts the runner and five repaired application checks on the integrated
source. It does not accept every changed Study/Learn/content flow. Their
producer checks and receipts remain with the parent; changes after `b473ecb3`
require exact source-delta reconciliation. b4's 1,214 recorded passing identities
remain useful evidence at `8c6c4b18`, without becoming a passing final-source
suite or being combined with b6 to relabel b4.

## Completed harness checkpoint

The receipt harness completed **16 tests, 16 passed, zero skips**, exit **0**,
at **10:35:01 UTC**. Final JUnit parses successfully and contains all 16 selected
identities. Every selected test has setup, call and teardown results; source
checks passed and no guard violation was recorded. These are harness checks,
reported separately from application coverage.

The existing receipts were recovered after central Git relocation. Old terminal
session 87618 no longer exists; the completed harness was not rerun.

- `C:/rn-finalise-20261005/r1/harness2/run.json`
- `C:/rn-finalise-20261005/r1/harness2/result.json`
- `C:/rn-finalise-20261005/r1/harness2/results.xml`
- `C:/rn-finalise-20261005/r1/harness2/inventory.json`
- `C:/rn-finalise-20261005/r1/harness2/outcomes.json`
- `C:/rn-finalise-20261005/r1/harness2/events.jsonl`
- `C:/rn-finalise-20261005/r1/harness2.log`

JUnit SHA-256:
`762a0ff61a2c43b2fe7e484e71e90d00a41aea8099bebec97eec63b351a721dc`.
Tested runner SHA-256:
`c6f90abf28bc0fe56247db2e8b049495244338929c7aabda58b33ad835b34d40`.

**No completed full application regression exists at this checkpoint.** The
first fresh full attempt used `C:/rn-finalise-20261005/b2` after harness commit
`30e88174ccde852df0ac7254177222a60e55acc8`. Its recorder conflict and repair are
recorded below. Harness tests are not added to an application pass total.

## Method and repaired finalization

`scripts/run_backend_regression.py` reuses the public integration Python
environment and loads this worktree's runtime. Its inherited editable-install
source path is removed. Clean production sources, explicit HEAD pinning, loaded
module paths, Git tree identities and actual package versions establish source
attribution without rebuilding dependencies.

One process executes serially. Fresh short C scratch owns synthetic profiles,
caches, temporary files and logs. The 12 GiB disk floor is checked before scratch
creation and each test and cannot be reduced. CPU thread bounds are two.
External sockets/DNS and Windows asyncio connections are blocked, including
connections to parent ports 8787/5196. Private profile access and writes outside
scratch are denied. Actual ONNX, FastEmbed model and Docling StandardPdfPipeline
construction are forbidden in the application-only stage. Existing controlled
seams are application checks, not actual model/OCR/engine acceptance.

Duplicate nodeids are rejected. Exact selected/excluded identities and every
setup/call/teardown event are retained. Acceptance requires terminal session and
JUnit reconciliation. Skips, missing JUnit, interrupted tests, source drift,
collection failures and guard violations cannot become a passing receipt.
Exceptions preserve a failed result when the process can still write evidence.

CPython 3.14's Windows lookup used by JUnit can execute `cmd /c ver`. Real OS
metadata is now cached before the restricted test phase, allowing finalization
without arbitrary shell admission during tests. Nullable Windows subprocess
executables and command strings are handled explicitly.

## Metadata recording under strict application privacy tests

The full `b2` attempt started at **11:10:32 UTC**, collected **1,146** unique
identities and selected **1,095** application tests. Its 51 explicit exclusions
were 13 capacity, 19 actual engine/helper, one external collection, two native
protection and 16 harness identities. It ended with terminal exit **1** after
the recorder reopened `events.jsonl` while
`tests/runtime/test_images_context.py::test_real_hermes_compactor_sdk_selected_route_scope_head_tail_and_no_temp_writes`
had installed its strict no-filesystem-write guard. The application call had
passed; the recorder triggered an internal pytest error. No production failure
or completed-suite pass is attributed to this interrupted attempt. Its original
inventory, partial events and `C:/rn-finalise-20261005/b2.log` remain preserved.
Owned process 14116 ended; no unfinished duplicate was launched.

The runner now pre-opens a fixed set of metadata-only receipt files before
application tests install their privacy guards. It writes events and final
receipts through those non-inherited handles. Application filesystem APIs and
the existing privacy assertions remain unchanged. A new harness regression
rejects an application payload write while setup/call/teardown/session/result
metadata successfully finalizes; it checks both sides of the boundary.

Changed-harness validation completed **17 of 17**, exit **0**, at **11:15:49 UTC**,
with valid 17-case JUnit and no guard violations. Evidence: `C:/rn-finalise-20261005/b3h/`
and `C:/rn-finalise-20261005/b3h.log`. JUnit SHA-256:
`86ac30b4614b951b251902f0331a58c53ecdae82ed30f3c845aa83fda15b56ea`.

The exact existing compactor privacy regression then completed **one of one**,
exit **0**, at **11:16:35 UTC**, with final JUnit, source reconciliation and no
guard violation. Evidence: `C:/rn-finalise-20261005/b3p/` and `C:/rn-finalise-20261005/b3p.log`.
JUnit SHA-256:
`12afb91691336278b407b4fc6a544777c3889089e0d43093d7283d001f6941b1`.
This targeted check is not added to a future full-run denominator. No production
code or existing test was changed. One fresh full application run started at
**11:17:35 UTC** in `C:/rn-finalise-20261005/b3` on recorder-fix commit
`2d16bd58eedad9d42adef071b42ba68afa482eea`. Tested runner SHA-256:
`a6d9aa12ef0da050907cf8da39939b09497c416929ab54c964224fa34bfdd034`.

The b3h and b3p manifests name HEAD `30e88174` with owned runner/test edits.
Those edits became `2d16bd58`; the recovered runner hash matches that committed
runner and its integrated counterpart `8c6c4b18`. Their JUnit identities, counts and all phase events reconcile,
with no failures, skips or duplicate phases. Production paths are identical
between the application baseline and `2d16bd58`. These are pre-commit repair
checks, not evidence that the unmodified `30e88174` runner contained the fix.

## Exact full-run selection

The interrupted run collected **1,147 unique identities**, selected **1,095 application
tests** and explicitly excluded **52**: 13 capacity, 19 actual engine/helper,
one external collection, two dedicated native protection and 17 harness tests.
All identities, classification reasons and execution order are in
`C:/rn-finalise-20261005/b3/inventory.json`. The extracted exact exclusions are
`C:/rn-finalise-20261005/b3/excluded-nodeids.json`. No exclusion is labelled a
pass or a skipped application test. These counts are collection evidence,
not terminal results.

| Backend area | Application selected | Excluded |
| --- | ---: | ---: |
| Assessment | 45 | 0 |
| Backup | 128 | 16 |
| Cases | 90 | 3 |
| Content | 90 | 0 |
| Integration | 13 | 0 |
| Knowledge | 409 | 9 |
| Learn | 36 | 0 |
| Memory | 46 | 2 |
| Retrieval | 63 | 1 |
| Runtime | 117 | 4 |
| Study | 5 | 0 |
| Updates | 53 | 0 |
| Harness, reported separately | 0 | 17 |
| **Total** | **1,095** | **52** |

The 35 capacity/helper/collection/native exclusions retain exactly the original
freeze55 denominator boundary; the 17 new receipt checks are separate. Actual
Office SimplePipeline/HybridChunker checks in the application selection use
synthetic packages, a local synthetic tokenizer and controlled vectors. They
do not establish real PDF OCR or embedding-model behaviour.

## Recovered b3 accounting

| Evidence | Recovered result | Terminal acceptance |
| --- | --- | --- |
| `b3h/`, `b3h.log` | 17 harness tests, all three phases passed | Exit 0; valid 17-case JUnit; accepted harness pass |
| `b3p/`, `b3p.log` | One compactor privacy test, all three phases passed | Exit 0; valid one-case JUnit; accepted targeted pass |
| `b3/`, `b3.log` | 595 complete three-phase passes; one setup-only test; 499 selected tests not reached | Incomplete; exit status unknown; no accepted full application pass |

All paths above are under `C:/rn-finalise-20261005/`. At **14:29:17 UTC**,
recorded PIDs **24592** (b3), **2160** (b3h) and **15124** (b3p) were absent;
no matching Python regression runner was active. No process was terminated.

b3 retains **1,786 phase events**: 596 passed setups, 595 passed calls and
595 passed teardowns, with no recorded failure, skip or duplicate phase. Its
last event at **11:37:30.159386 UTC** is setup for
`tests/knowledge/test_image_original_preservation.py::test_durable_success_browses_original_and_empty_citation_then_deletes[.png]`.
That test's call and teardown are absent. The last recorded disk reserve was
357,675,991,040 bytes, above the 12 GiB floor. Termination cause is unproved.

`session.json`, `outcomes.json`, `module-sources.json` and `result.json` are
zero-byte preopened files; `results.xml` is absent. Missing terminal source and
guard reconciliation cannot be inferred from passing calls. Original evidence
is preserved without manufacturing a final result or combining partial counts
with a later run. SHA-256 anchors:

- `b3/inventory.json`: `2bc209a2fe947a79240729755e0935d173389352b6793d58812f8f4662a93b9d`.
- `b3/events.jsonl`: `f1543aac4b7f7aadf3cb55594c81ac3e5a1169072583b302427fa81f4a842082`.

## Preserved incomplete attempts

The freeze55 corrected attempt never launched after disk reserve failed. Its
report-only commit is `5019df63b1748496304c86bcfce97ef6e3036e34`; no pass is added.

The later E-only attempt at
`E:/Renulus-native-delivery/desktop-20261005/application-regression-55/.local/application-regression-E-only/20261005T0722Z/`
retains 14 passed calls/42 phase events, a 14-dot log and no final JUnit. It is
incomplete. Its application freeze was `55d553d1d18026a0a490f4292c033ac1aadd2595`;
runtime, Hermes, tests and dependency identities match the 9d26f1ee baseline.
No unfinished unowned process was rerun or terminated.

This lane's preliminary attempts remain under `C:/rn-finalise-20261005/r1/`.
The 140-test light attempt in `r1/light4` reached 100% with no observed test
failure but failed JUnit finalization on the Windows version probe. It contributes
no accepted application pass total. The subsequent 16-test harness receipt proves
repaired finalization; it does not relabel the light attempt.

## Outstanding acceptance and source reconciliation

The one authorised integrated application run is recorded above; no broad
old-baseline rerun was performed. Actual Docling/OCR/embedding/Mem0/helpers,
large capacity fixtures, acquired-collection inputs, dedicated native proofs,
live providers and installed acceptance remain separate. Exact exclusions are
preserved in the inventories and remain explicit. The parent holds the heavy
and native slot and owns final product acceptance.

The owner's **October 5, 2026** decision makes current delivery acceptance an
**unsigned Windows build validated on this PC**. The parent verifies bundled
runtime execution with an OS-only PATH, matching installation, source/artifact
hashes, normal shutdown/reopen and actual required journeys/recovery. Code
signing and separate clean-PC/VM validation are optional future distribution
work and do not block current completion. Historical observations are retained.

The parent owns final source freeze and the decision about any further broad
regression. Later Study/content or other product changes need their own affected
checks and source reconciliation. b4's actual 1,219-case inventory replaces b3's
1,095 denominator only for b4's source; its failures and false source result remain
recorded. The concrete runner defects and bounded repair acceptance are above.

## Prepared final-source reconciliation and optional application sweep

The runner prerequisites are integrated as `eb821aa3`, `8c6c4b18` and `324af6f2`.
The parent has not released a final freeze or another broad sweep. First compare
the supplied final 40-character SHA with the accepted bounded source:

```powershell
$regressionFinalCommit = 'REPLACE_WITH_PARENT_FINAL_40_CHARACTER_SHA'
if ($regressionFinalCommit -notmatch '^[0-9a-f]{40}$') { throw 'Supply the final SHA.' }
git -C C:/Renulus-native-delivery/desktop-20261005/repo diff --name-status `
    b473ecb3d58ea7dabcef83bac8d0335a420d45ab $regressionFinalCommit -- `
    runtime content upstream/hermes packages tests scripts/run_backend_regression.py `
    packaging/runtime pyproject.toml uv.lock
if ($LASTEXITCODE -ne 0) { throw 'Final source delta could not be read.' }
```

Map each changed producer/test/content path to its affected checks and current
receipts. Preserve b4's exact 1,214 passing identities at their original source;
do not schedule their wholesale repetition merely to turn that historical
receipt green. The parent decides whether the final delta and existing coverage
justify a broad run. The following optional command is prepared for that explicit
release; it has **not** been executed during this recovery.

Preserve other lanes' edits and confirm no existing regression
process owns the proposed run. Use a fresh pinned isolated test checkout; parent
integration must remain free to advance. Use a
durable process with separate logs; a tool-session interruption must not be
treated as process completion.

```powershell
$regressionPython = 'C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe'
$regressionCommit = 'REPLACE_WITH_PARENT_FINAL_40_CHARACTER_SHA'
if ($regressionCommit -notmatch '^[0-9a-f]{40}$') { throw 'Supply the final SHA.' }
$regressionRepo = 'C:/rn-finalise-20261005/checks/application-' + $regressionCommit.Substring(0, 8)
if (Test-Path -LiteralPath $regressionRepo) { throw 'Choose a fresh test checkout.' }
git -C C:/Renulus-native-delivery/desktop-20261005/repo worktree add --detach $regressionRepo $regressionCommit
if ($LASTEXITCODE -ne 0) { throw 'Pinned test checkout creation failed.' }
if ((git -C $regressionRepo rev-parse HEAD) -ne $regressionCommit) { throw 'HEAD differs.' }
$regressionDirty = git -C $regressionRepo status --porcelain -- runtime content upstream/hermes packages tests scripts/run_backend_regression.py packaging/runtime pyproject.toml uv.lock
if ($regressionDirty) { throw 'Freeze the tested sources, tests and runner first.' }
$regressionScratch = 'C:/rn-finalise-20261005/app-final-' + $regressionCommit.Substring(0, 8) + '-' + (Get-Date -AsUTC -Format 'yyyyMMddTHHmmssZ')
$regressionProcess = Start-Process -FilePath $regressionPython -ArgumentList @(
    '-B', ($regressionRepo + '/scripts/run_backend_regression.py'),
    '--scratch', $regressionScratch, '--expect-commit', $regressionCommit,
    '--stage', 'application', 'tests'
) -WorkingDirectory $regressionRepo -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput ($regressionScratch + '.stdout.log') `
  -RedirectStandardError ($regressionScratch + '.stderr.log')
Get-CimInstance Win32_Process -Filter ('ProcessId = ' + $regressionProcess.Id) |
    Select-Object ProcessId, ParentProcessId, Name, ExecutablePath, CreationDate, CommandLine |
    ConvertTo-Json | Set-Content -LiteralPath ($regressionScratch + '.process.json') -Encoding utf8
```

Keep the process handle; poll without a long blocking wait. When `run.json`
appears, verify its actual PID and interpreter against the recorded process
identity; a Windows venv launcher may have a child interpreter. Before any
rerun or termination, check creation time, executable and exact source/scratch
arguments, not PID alone. Capture the process exit code after it exits in an
adjacent terminal receipt; a lost handle does not prove an exit status. Keep
the detached checkout's HEAD unchanged until terminal evidence is complete.

Accept only a nonempty final `result.json` with `accepted_stage_pass: true`,
`complete: true`, `source_unchanged: true`, exit 0, no runner error or guard
violations, matching selected identities in session/events/outcomes/JUnit,
passing setup/call/teardown for every selected test and valid final JUnit. Keep
the module-source paths, tree/package identities, resource receipt and log
alongside it. Never combine b3's partial results with this receipt or lower the
12 GiB floor/exclusions. Require all three individual source-check booleans true
and no unexpected module sources. The final inventory supplies its own exact
denominator and exclusions; b4's 52 exclusions include the then-current 17-test
harness, whereas the repaired harness has 28 tests.
`faulthandler_timeout=120` provides diagnostics only;
it is not a timeout that terminates a test. Heavy/helper/native and installed
journey evidence remains separately scheduled and attributed.

## Excluded identity appendix

| Category | Exact nodeid |
| --- | --- |
| capacity | `tests/backup/test_derived_state_exclusion.py::test_large_structured_extraction_is_omitted_before_budget_checks_but_passage_locators_survive[json]` |
| capacity | `tests/backup/test_derived_state_exclusion.py::test_large_structured_extraction_is_omitted_before_budget_checks_but_passage_locators_survive[zip]` |
| engines | `tests/backup/test_offline_engine_round_trip.py::test_actual_cpu_library_and_manual_note_zip_restore_retrieve_edit_delete` |
| engines | `tests/backup/test_prepare_delivery_profile.py::test_guarded_http_library_delivery_retains_originals_journal_and_queue_without_learner_history[1]` |
| engines | `tests/backup/test_prepare_delivery_profile.py::test_guarded_http_library_delivery_retains_originals_journal_and_queue_without_learner_history[2]` |
| capacity | `tests/backup/test_recovery_capacity_sidecar.py::test_capacity_experiment_preserves_unicode_citation_and_journal_with_real_schema` |
| capacity | `tests/backup/test_recovery_capacity_sidecar.py::test_late_segment_corruption_rolls_back_all_scratch_records` |
| capacity | `tests/backup/test_recovery_capacity_sidecar.py::test_experimental_descriptor_cannot_reach_sibling_owner_state` |
| capacity | `tests/backup/test_recovery_capacity_sidecar.py::test_experimental_record_budget_refuses_without_partial_stage` |
| capacity | `tests/backup/test_recovery_capacity_sidecar.py::test_existing_capacity_workspace_is_refused_before_runtime_access` |
| capacity | `tests/backup/test_round_trip.py::test_catalogue_at_183891_rows_is_explicitly_omitted_without_reading_bulk_metadata` |
| capacity | `tests/backup/test_round_trip.py::test_oversized_learner_table_is_refused_before_materializing_it_for_either_export` |
| capacity | `tests/backup/test_segmented_capacity.py::test_product_disk_round_trip_measurement_refuses_whole_corpus_ram_growth` |
| engines | `tests/backup/test_segmented_engine_and_history.py::test_actual_cpu_segmented_library_note_restore_retrieve_cite_edit_delete` |
| capacity | `tests/backup/test_segmented_guards.py::test_actual_265_mib_synthetic_originals_exceed_legacy_budget_and_stream_into_fresh_profile` |
| capacity | `tests/backup/test_segmented_recovery.py::test_product_api_streams_large_canonical_library_and_rebases_verified_originals` |
| engines | `tests/cases/test_offline_attachment_flow.py::test_actual_proven_byte_extractor_through_case_preview_apply_save_delete[pdf]` |
| engines | `tests/cases/test_offline_attachment_flow.py::test_actual_proven_byte_extractor_through_case_preview_apply_save_delete[png]` |
| engines | `tests/cases/test_offline_attachment_flow.py::test_actual_native_stream_after_approved_startup_has_no_filesystem_writes` |
| external_collection | `tests/knowledge/test_acquired_offline.py::test_actual_selected_acquired_jats_through_offline_api_worker` |
| capacity | `tests/knowledge/test_api_collection.py::test_raw_file_upload_and_malformed_size_format_errors` |
| engines | `tests/knowledge/test_byte_extraction.py::test_real_documentstream_text_native_scanned_pdf_and_image_never_write` |
| engines | `tests/knowledge/test_byte_extraction.py::test_byte_scope_capability_requires_prepared_verified_helpers` |
| engines | `tests/knowledge/test_chunk_budget.py::test_real_hybrid_table_split_reserves_heading_overhead_and_preserves_cells` |
| engines | `tests/knowledge/test_library_responsiveness_offline.py::test_selected_text_engines_keep_metadata_available_during_query` |
| engines | `tests/knowledge/test_offline_engines.py::test_real_text_hybrid_roundtrip_and_shared_token_budget` |
| engines | `tests/knowledge/test_offline_engines.py::test_real_docling_cpu_page_region_original_roundtrip[pdf]` |
| engines | `tests/knowledge/test_offline_engines.py::test_real_docling_cpu_page_region_original_roundtrip[image]` |
| engines | `tests/memory/test_mem0_real.py::test_actual_mem0_qdrant_fastembed_delete_history_restart_reindex` |
| engines | `tests/memory/test_mem0_real.py::test_actual_mem0_extraction_uses_only_mocked_scoped_provider` |
| harness | `tests/regression/test_receipt.py::test_complete_final_junit_with_all_phases_can_be_accepted` |
| harness | `tests/regression/test_receipt.py::test_privacy_guards_stay_strict_while_preopened_receipts_finalize` |
| harness | `tests/regression/test_receipt.py::test_fourteen_call_dots_without_teardown_or_junit_cannot_pass` |
| harness | `tests/regression/test_receipt.py::test_completed_calls_need_terminal_evidence_and_unchanged_source[missing-junit]` |
| harness | `tests/regression/test_receipt.py::test_completed_calls_need_terminal_evidence_and_unchanged_source[wrong-junit-count]` |
| harness | `tests/regression/test_receipt.py::test_completed_calls_need_terminal_evidence_and_unchanged_source[source-drift]` |
| harness | `tests/regression/test_receipt.py::test_completed_calls_need_terminal_evidence_and_unchanged_source[guard-violation]` |
| harness | `tests/regression/test_receipt.py::test_completed_calls_need_terminal_evidence_and_unchanged_source[nonzero-exit]` |
| harness | `tests/regression/test_receipt.py::test_completed_calls_need_terminal_evidence_and_unchanged_source[collection-error]` |
| harness | `tests/regression/test_receipt.py::test_teardown_failure_and_setup_skip_are_not_passing_calls` |
| harness | `tests/regression/test_receipt.py::test_nullable_executable_and_windows_command_strings_are_supported[command0]` |
| harness | `tests/regression/test_receipt.py::test_nullable_executable_and_windows_command_strings_are_supported["C:\\Users\\karol\\Documents\\t3-workspaces\\Renulus-wt-integration\\.venv\\Scripts\\python.exe" -B "synthetic.py"]` |
| harness | `tests/regression/test_receipt.py::test_nullable_executable_and_windows_command_strings_are_supported[command2]` |
| harness | `tests/regression/test_receipt.py::test_nullable_executable_and_windows_command_strings_are_supported[git describe --always --dirty]` |
| harness | `tests/regression/test_receipt.py::test_git_argument_cannot_disguise_a_shell_executable` |
| harness | `tests/regression/test_receipt.py::test_parent_ports_remote_addresses_and_outside_writes_are_denied` |
| harness | `tests/regression/test_receipt.py::test_duplicate_collected_identities_are_rejected_before_execution` |
| native | `tests/retrieval/test_connections_http_api.py::test_native_windows_dpapi_own_synthetic_key_and_wrong_namespace` |
| engines | `tests/runtime/test_cross_module_generation.py::test_actual_mem0_oss_outbox_rejects_go_without_assets_or_model_calls` |
| engines | `tests/runtime/test_helper_startup.py::test_actual_rapidocr_parser_accepts_local_root_and_two_thread_config` |
| native | `tests/runtime/test_protected_helpers.py::test_actual_windows_dpapi_round_trip_is_profile_bound` |
| engines | `tests/runtime/test_windows_helpers.py::test_selected_cpu_stack_imports_and_native_embedded_store_roundtrips` |
