# Assessment fixture repair — 2026-10-10

Branch: `codex/opencode-foundations`; reviewed production baseline: `9a10562a`.
Concurrent work advanced HEAD to `f6bdb589` before this fixture-only commit.
Owned changes: `tests/assessment/conftest.py`, `serve_fixture.py`,
`serve_currency_fixture.py`, this note, and the subsequently authorised
`test_source_currency.py` and `test_original_pack.py`. No production edits.
After verification, the user explicitly requested a commit of these five Python
files and this note; the initial no-commit instruction was superseded.

## Failure and baseline distinction

Before editing, the public
`test_assessment.py::test_filter_and_track_do_not_invent_coverage` produced
**1 setup error**. Running each serving script against a fresh owned profile
also produced **2 startup failures**. All three stopped in
`ConversationRepository` with `capability_unavailable: Learn is not ready`,
before lifespan or provider execution. Receipts under
`C:/Renulus/scratch/oc-foundations/af/`: `red-pytest.txt`/`.xml`,
`red-cli.txt`, and `red-currency-cli.txt`.

This is inherited fixture assembly debt, not a newly reproduced H01/H24
production regression. These three fixtures have no diff between `c2bd8964`
and `9a10562a`. The [H24 evidence](opencode-foundations-h24.md) records the same
failure using the original baseline server; its retained
`h24/receipts/baseline-assessment-fixture.txt` and `baseline-fixture-matrix.txt`
were inspected, not rerun. The parent's backend failure manifest contains
45 affected nodeids: 33 setup errors and 12 call failures.

## Minimal repair

Define one fixture module order in `conftest.py`:
`content, updates, learn, cases, assessment`. Both serving scripts reuse it.
Learn and Cases now install their real owners and migrations before Design C's
conversation routers are constructed. Existing synthetic content, generated
provider/knowledge adapters and currency publisher remain unchanged. No runtime,
helper-engine or production code is added or modified.

For historical pack tests, `create_app_with_pack` supplies the existing
`content_pack_root` and `content_pack_selection` contract before real bootstrap,
including on reopen. Its temporary factory override preserves real `Services`
and restores the factory after construction. The real repository and version
policy remain intact; no historical currency/history/scoring assertions were
weakened. A public HTTP manifest assertion explicitly verifies `1.0.0`.

## Verification

- Red-to-green tracer: **1 setup error → 1 passed** (`green-tracer.txt`/`.xml`).
- Focused backend run: **40 passed, 5 failed, 0 setup errors, 0 skipped** in
  224.40 seconds. All 45 selected nodeids exactly match the parent's
  `h24/receipts/old-fixture-failure-nodeids.txt` (verified against JUnit).
  Receipts: `green-backend.txt`/`.xml`, `backend-manifest-match.json`.
  Despite the receipt basename, that initial run is not a 45-test pass.
- Currency tracer after pack repair: **1 passed** (`green-currency-tracer.txt`/
  `.xml`). Requested five failed cases plus startup tracer: **6 passed**,
  0 failures/errors/skips, 47.72 seconds (`green-followup.txt`/`.xml`).
- `backend-reconciliation.json` confirms **45 distinct passing nodeids across
  the focused receipts**, with no missing/additional cases or remaining failures.
  The six-case follow-up contains five repaired failures and one overlapping
  startup tracer. This is combined evidence, not a fresh 45-test rerun or
  full-suite pass.
- Static standards and specification reviews, including the expanded five-file
  diff: **0 findings on each axis**. All five Python files parse; scoped
  `git diff --check` passes.
- The optional two-file renderer attempt executed **0 tests**: Vite could not
  resolve the scratch-only network-guard setup file. This is a harness failure,
  not a fixture/backend result; retained as `frontend-driver-error.txt`/`.xml`/
  `.json`. This lane did not repair or retry its renderer driver.
- Before the pack repair, the parent's full desktop run recorded **61 files
  passed / 1 failed / 3 skipped; 689 tests passed / 13 skipped (702)**.
  Assessment index passed **13/13**; sourceCurrency failed before its test on the
  pack collision. Receipts: `parent/frontend-final.txt`/`.json`. The parent owns
  targeted reconciliation after these stable fixture changes.

Validation uses the existing `C:/Renulus/dev/python/Scripts/python.exe`, existing
desktop `node_modules`, Vite's runner config loader and owned scratch caches.
The focused backend process has a loopback-only socket/DNS guard and offline
helper settings. All profiles, logs and caches are under the owned `af` scratch
root. No live provider calls, downloads, installed profile use or complete-suite run
belongs to this lane. The tracer is included in the 45-nodeid set, not an extra
distinct test.

## Historical pack collision resolved

The five initially masked failures were one test in `test_original_pack.py` and four in
`test_source_currency.py`. Both helpers explicitly install `1.0.0` after the
current server has automatically activated `1.4.2`, raising
`ContentConflict: A newly published question must advance its version`.
Both pre-edit CLI profiles already held active `1.4.2`: Learn/Cases did not
introduce that activation. The two test files and content bootstrap code are
unchanged between the baseline commits. Selecting the declared historical
release before bootstrap resolves the collision and retains the real `1.0.0`
currency fixture used by the renderer, including its immutable restart evidence.
