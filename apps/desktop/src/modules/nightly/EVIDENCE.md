# DC19 nightly slice evidence — October 10, 2026

This lane verified the exact `C:/Renulus/dev/worktrees/dc-home` root and
`codex/dc-home` before writes. Backend checkpoint `2d5fe2f8` preceded UI.
Follow-ups `3571eb21` (connected scheduler tests), `8c97be57` (renderer seam) and
`f008fe8d` (neutral status/orphan reconciliation and restore checks) changed only
leased nightly files/tests. Normal shared merges retained concurrent work. The
owned nightly-test add/add conflict retained the newer scheduler tests; no
unowned file was reset or reverted. Pauli's `85d24be6`, `8d798089` and
`d443c9c7` were consumed as `a05c56a9`, `a93a083c` and `3214d70d`. The final
shared shell/Settings/Tests baseline `837ea3d0` was merged as `9ad99b3e`.

## Connected backend proof

The actual NightlyService's `update_preferences` and `tick` claim days; no
hand-written scheduler state substitutes for producer proof. Real application
migrations, Home canonical eligibility, SavedGenerationService, saved-test
repository and ProviderManager run against synthetic owned databases. Only the
provider transport is synthetic; there were no live provider calls.

- Exact 5/10/20 sets publish once with nightly origin and producer provenance
  through the selected Codex/GPT 6.1 Sol route, using one/two/four bounded batches.
- Eight concurrent triggers and a long app-running sleep claim only the latest
  due day; backwards date changes do not duplicate it. An offline day is consumed
  without retry, while a later eligible day can run. Short/invalid output never
  auto-publishes or silently becomes a shorter Ready set.
- Off/Stop, memory correction/deletion, epoch, policy and timezone changes stop
  publication. The final publication transaction rechecks eligibility after
  validated progress. Published original-key replay remains immutable after Off
  without invoking another provider call.
- An actual source job with epoch 5 restored by JSON into destination epoch 5
  becomes failed/interrupted in canonical recovery, retains its checkpoint/counts,
  and does not resume inference. Nightly then waits for the next future boundary.
  A new cold owner also reconciles a same-epoch orphan through neutral status,
  even when the generation UI was never opened.
- Safe preferences are exported with exactly enabled/local_time/question_count/
  revision. nightly.state, nightly.commands and home.suggestions remain local.
  Assembled HTTP status, Off and neutral Stop remain usable under active-Test
  policy, with no question/key payload and the durable publication winner. This
  last check uses an explicit real-DDL policy row specimen; it is not DC13 attempt
  consumer evidence. Earlier manually inserted rows test the guard only.

The owned suite covers 44 cases. The recovery run passed 43 and exposed an HTTP
test fixture that referenced the not-yet-published whole_attempts owner. That
fixture was replaced with the explicit policy specimen; its focused rerun passed.
The earlier 41-case connected run passed 38; three assertions incorrectly read
the outer provenance envelope instead of producer.method. The corrected three
passed separately. Failed receipts are retained and are not reported as all-green
suite runs.

| Receipt | Result | SHA-256 |
| --- | --- | --- |
| `C:/Renulus/scratch/design-c/nightly/recovery.xml` | 43 passed, 1 fixture failure | `2d68e90adeb019c4f991e8aeb6a1726c416443f7963ac0783f66c18b06c5848d` |
| `C:/Renulus/scratch/design-c/nightly/neutral.xml` | Corrected policy case passed, 43 deselected | `98dea285cceb2a5a81702ee9ba95c22e2c0d075189d78c3ad106bac0b7615935` |
| `C:/Renulus/scratch/design-c/nightly/published.xml` | Corrected 5/10/20 assertions passed | `420c381bf26ab68a72f3f92e5b4079fb4c73d555b387532cebb879be49f4c13c` |

## Actual hidden Settings/Tests proof

Figma design-to-code, Interface Design and Impeccable informed the leased UI.
The reference is the reconciled C file zV8JiWybVHP1UxJtLbZjEt, nightly Off/On
83:7590/83:7750 and preferences child 83:7879. Confirmed 22:00/five defaults
and future-only recovery supersede prototype values/copy. Existing controls,
Source Sans 3 and semantic paper/teal tokens are reused.

The exact worktree build passed TypeScript, Vite and Electron compilation. All
12 nightly Vitest checks passed again after the final hint/spacing fixes. Actual
pixels used the installed canonical controller client with `--repo` fixed to
dc-home, existing Python/public helpers and compact owned root
`C:/Renulus/scratch/dcctl/night1`. The worktree client lacked the controller SDK;
the existing canonical client supplied it without an installation or shared
write. Controller profile: `C:/Renulus/scratch/dcctl/night1/c/s-c772ebcb/p`.

The real first-run form displayed Off, 22:00 and five selected. UI actions saved
21:30/20 while Off, then turned On. Tests displayed On and the next eligible
time; its Preferences action opened the same canonical settings. After rebuilding
and restarting the same synthetic profile, On/21:30/20 remained. The final local
DB read confirmed revision 3 and zero nightly jobs, with no provider connection
or credential interaction. The hint and inter-form spacing were corrected from
the first pixel batch, then confirmed in a bounded final batch.

Evidence directory: `C:/Renulus/scratch/dcctl/night1/c/s-c772ebcb/out`.

| Screenshot | Actual observation | SHA-256 for final captures |
| --- | --- | --- |
| capture-0001.png | First-run Off, 22:00/five | Initial capture retained |
| capture-0002.png | Saved On, 21:30/20 | Initial capture retained |
| capture-0003.png | Narrow settings at 1000×720 outer window | Initial capture retained |
| capture-0004.png / capture-0005.png | 200% scroll and keyboard navigation | Initial captures retained |
| capture-0006.png | Tests On status and Preferences consumer | Initial capture retained |
| capture-0007.png | Final reopened Settings; spacing/hint fixed, wide 1440×900 | `c01bb9fcfd6d2efba5c9532f2e8c07cb65677925c9c22b9b7c33b97a27fe2aa6` |
| capture-0008.png | Final 1000×720; all nightly controls reachable with keyboard focus | `8e03d5fef12b9197dd907ec9b826ca90f75ed0e4f2367dc0542cb5cb1c242b74` |
| capture-0009.png | Final 200%; Local time and focused Save remain readable/reachable | `fe4e31459413601dd713465229c4794dd0001cc0e42bdf2306e44f176a33dd1a` |

The controller receipt reports fault=null, normal restart and close, no forced
or remaining processes, and hidden non-focusable windows.
`receipt.json` SHA-256: `f659e2fca41cbf8ee139d6bfd3ebc8e96906ad311e15605873c2db5d27231c39`.
The retained log contains an initial disconnected Home HTTP 409; Home still
displayed its usable composer and unavailable-suggestions message. No nightly
request failure, page error or hidden-window fault was observed. Native dialogs,
OS scaling and physical assistive-technology acceptance are outside this proof.

## Remaining integration gates

DC19 is not marked done. Saved publication is proven through actual backend
owners with synthetic transport, and Settings/Tests preference consumers now
have real hidden UI evidence. A complete published-nightly result to canonical
saved setup and shared Study/Test attempt journey remains an integration gate.
No live content quality or provider availability claim is made. Home remains
the sole canonical eligibility adapter; Russell's assessment-test-answer input
needs its explicit frozen eligibility/cohort payload before inclusion. Raw cases,
temporary originals/metadata and reviewed keys are not substituted as input.
