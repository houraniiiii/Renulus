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
next action is one fresh application-only run in `C:/rn-finalise-20261005/b2`
after committing this tested harness/report. Its own inventory, exact selection
and exclusions, terminal JUnit and result establish its denominator and outcome.
Harness tests are not added to the application pass total. No heavy slot is used.

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
