# Backend application regression finalisation

Evidence dated October 5, 2026. Owned branch: `build/finalise-backend-checks`.
Application baseline: **9d26f1eedf31cd488b9aab5837a105ee152d9efa**.
This lane changes only the regression runner, its receipt tests and this report.
Production code, shared schemas, dependencies, helpers and native/profile state
are unchanged. This baseline is not the parent's final product revision.

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
code or existing test was changed. One fresh full application run will use
`C:/rn-finalise-20261005/b3` after the recorder-fix commit.

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

The full application run is pending. Actual Docling/OCR/embedding/Mem0/helpers,
large capacity fixtures, acquired-collection inputs, dedicated native proofs,
live providers and installed acceptance remain separate. Their excluded nodeids
will be recorded explicitly in the full inventory. The parent holds the heavy
and native slot and owns final product acceptance.

After the parent supplies integrated product changes, compare runtime, Hermes,
content, contract, test and dependency identities with this baseline. Enumerate
and rerun affected checks on that revision. Baseline evidence must not be
presented as acceptance of later untested source.
