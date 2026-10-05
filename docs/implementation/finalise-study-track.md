# Study/Home programme consumers — issue #19

October 5, 2026. Bounded lane `build/finalise-study-track` in
`C:/rn-finalise-20261005/lanes/study-track`. The parent's authorised
prerequisites were fast-forwarded from `50aac06c` to `8c6c4b18` while preserving
the local owned edits. Hand back only the new Study commit; prerequisites are
already integrated by the parent.

## Result and ownership

Saved general-nephrology/ESENeph preferences now select real canonical Study
activities and Home review/upcoming records. Content's `track_metadata()` is
the programme authority, introduced in `604b6d11` and integrated as `a6b5d597`.
Study translates the existing goal values `general` / `eseneph` into the
content IDs `general_nephrology` / `esen_eph`. It consumes the active dated
mapping, rather than copying a blueprint or deriving alignment from question
counts, model output or the topic's broad mapping label.

General study uses active saved topics, with no selection meaning all active
topics. ESENeph intersects topic objectives with active exam-domain objective
links. Curriculum-support links are shown separately and do not create
exam-domain activities. A mapped mistake additionally requires an exact active
question/version pin and a linked objective. A later answer in the same family
resolves an earlier mistake for new suggestions; equal evidence timestamps
use insertion order as the tie-breaker. Observed scores remain based on
committed answers, separate from generated practice and conversation volume.

Automatic activities outside the saved track/topics are filtered from the
active plan/Home; their canonical records are preserved. Manual moves, skips,
completions and historical activities survive filtering, another proposal and
restart. Kept manual rows outside the current selection are identified. Legacy
activities without track provenance are treated as general study. New ESENeph
activity identities include the programme version, and their reasons retain
the mapping version/check date. A withdrawn mapped pin hides an automatic
review; a manual override remains inspectable and marked outside the selection.

The existing preferences and `study_activities` tables remain authoritative.
There is no migration or shared schema/contract edit. Home and plan responses
add `tracks`, `selection` and per-row `outside_selection`; existing goals keep
their response shape. Missing metadata/content or an unmatched topic preference
produces an explicit waiting/unavailable result without substituting general
study for the selected ESENeph track.

Flow keeps the primary learning question, existing layout, Source Sans 3,
Renal flow mark, shared controls and tokens. The plan has dated partial coverage
and a native domain/gap disclosure. It states that exam simulation is
unavailable and that the mapping does not establish full coverage or mastery.
Topic choices explain unsupported exam-domain links. Unsaved goal changes
cannot trigger a stale-goal proposal. Preference saves and activity mutations
are serialized so cached suggestions from the previous selection cannot
reappear after a confirmed save. Existing drafts, retry and cancellation
behaviour remains covered by the earlier mounted regressions.

Owned tracked changes:

- `runtime/renulus/study/service.py` and `api.py`.
- `apps/desktop/src/modules/study/index.tsx`, `study.css`,
  `StudyTrack.tsx` and `track.test.tsx`.
- `tests/study/conftest.py`, `test_tracks.py` and `test_today_journey.py`.
- This report.

Content, Assessment, shared contracts/storage, launchers and packaging have no
new lane-owned edits. Hermes, Docling/HybridChunker, FastEmbed, LanceDB and
Mem0 integrations, model/subscription policy, source permissions and
temporary-case navigation/retention are preserved.

## Verification and receipts

All receipts below are ignored and confined to
`.local/verification/study-track/` in this lane. `receipt.json` records the
final source commit, exact owned-file hashes, commands/results, proof hashes
and the final renderer artifact hashes after committing.

| Check | Result | Evidence |
| --- | --- | --- |
| Study backend suite | 13 passed | `pytest.log`, `pytest.xml` |
| Mounted Study renderer suites | 18 passed | `vitest.log`, `vitest.xml` |
| Desktop TypeScript check | Exit 0 | `typecheck.log`, receipt |
| Final Vite renderer build | Exit 0 | `renderer-build.log`, `renderer-final/` |
| Scoped whitespace check | Passed | receipt |

The backend tests exercise real SQLite and the actual content/assessment
producer from the bundled original pack, plus synthetic producer edge cases.
They verify goal/topic changes, exact mapped pins, curriculum-support exclusion,
unavailable metadata, withdrawal, committed-score separation, manual
overrides and application recreation on the same isolated profile. The real
journey submits an incorrect reviewed answer, observes a mapped mistake-review
and then verifies the saved exam date, moved activity, original score and
content-owned metadata after restart.

The mounted tests exercise the actual Study, Navigation and same-origin API
transport with controlled synthetic responses. They verify dated coverage and
domain gaps, the saved track handoff to Test, a retained activity's own track,
saved selections/reload, unavailable metadata, and mutation ordering during a
track change. The existing 13 Study regressions also pass.

Study's autouse test fixture installs only Content, Learn, Assessment and Study.
It excludes all helper/provider workers and refuses external socket/DNS access,
while permitting the loopback self-pipe required by Windows asyncio. No model,
OCR, embedding, native packaging, provider request, private profile/credential
read or external acquisition/import was performed.

Reproduction from the lane root, with the authorised reusable public Python:

```powershell
& C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe -m pytest tests/study -q
```

From `apps/desktop`, using its ignored junction to the authorised public Node
modules:

```powershell
node node_modules/vitest/vitest.mjs run src/modules/study
node node_modules/typescript/bin/tsc --noEmit
node node_modules/vite/bin/vite.js build --outDir ../../.local/verification/study-track/renderer-final
```

## Failures and proof limits

The first backend run had 4 failures/9 passes because an over-strict new test
socket guard blocked Windows asyncio's own loopback pipe. It was corrected to
allow only loopback connections; the final suite has 13 passes and the existing
Starlette/httpx deprecation warning. Original logs/JUnit remain in
`pytest-initial-harness-failure.log` and `.xml`.

The initial ignored preview seeder assumed a wholly unmapped topic and raised
`StopIteration`: the active pack gives each topic some exam-domain objective
links, which still constitute partial coverage. The seeder was corrected to
choose a manual topic outside the saved focus instead. Its original failure
is preserved in `preview-seed-initial-failure.log`. The successful real API seed
in `preview-seed.json` has a retained general T01 manual activity, a mapped T03
mistake-review, a T21 study activity, saved ESENeph/T03/T21 goals and 0/1 fresh
reviewed answers. This is API seed evidence, not a visible-browser journey.

Both in-app and Chrome `createBrowserTab` attempts timed out and reset their
controller kernels; the intervening in-app URL lookup found no tab. No visual
screenshot/layout pass is claimed. The owned loopback preview servers on
ports 5337/8937 were stopped after their port/process command identities were
checked; `preview-shutdown.json` records them and the controller limitations.

## Narrow parent prerequisite and current completion checklist

Assessment `16ad199d` has the content-owned track selector/catalogue, but
`AssessmentStudyPage` still initializes `track` with the literal
`general_nephrology`. Study now sends `nav.handoff.track` on Open Test and
mistake-review Start. Parent/Assessment ownership must initialize the selector
from an allowed handoff value (`general_nephrology` or `esen_eph`) and add the
receiver regression. This is the only requested code prerequisite; Study's
emitted payload is tested. It is not a claim that the complete Home-to-Test
track journey already passes.

- [x] Content-owned programme metadata drives Study/Home records.
- [x] Manual overrides and goals survive another proposal and restart.
- [x] Partial pool, domain gaps, unavailable states and score scope are honest.
- [x] Meaningful backend and mounted consumer checks, typecheck and renderer build.
- [ ] Parent/Assessment consumes the track handoff and verifies Home-to-Test.
- [ ] Visual inspection through an available browser or the final installed app.
- [ ] Parent freezes/integrates the source and validates the matching unsigned
  Windows build on this PC: bundled runtime under OS-only PATH, installation,
  source/artifact hashes, normal shutdown/reopen and required journeys/recovery.

The October 5 owner decision, accepted at `793eddb4`, supersedes mandatory
signing and separate clean-PC/VM acceptance. They are optional future
distribution work and do not block the current target. Historical observations
are preserved; this lane does not manufacture an installer, change a launcher
or declare the parent's final installed acceptance.
