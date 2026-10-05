# Assessment track consumer — October 5, 2026

This bounded S3/Flow change lets a learner select General nephrology or an
available content-owned ESENeph preparation track, inspect its partial coverage,
and launch a reviewed quiz from that exact selection. It keeps unmapped content
explicitly unavailable for ESENeph.

Worktree: `C:/rn-finalise-20261005/lanes/assessment-track`. Branch:
`build/finalise-assessment-track`. Baseline:
`da726ac147f20232cb3941ce50a1833af6d12336`. The commit containing this report owns
the complete slice; its hash and evidence receipts are recorded in the final
handoff and ignored `.local/finalise-assessment-track-handoff.json`. No push.

## Producer contract and behaviour

The consumer calls `ContentRepository.track_metadata()` through the existing
assessment gateway. Content remains the sole mapping owner. The content lane's
read-only contract is now committed as `604b6d11` (release 1.1.1); its
`runtime/renulus/content/programmes.py` SHA-256 observed for this handoff is
`285e0324c147622068fb330ee193362a97bbc9a6f8867c64612acab3b245a9c3`.
The content-owned `/api/v1/content/tracks` endpoint remains independent; the
renderer obtains its assessment selection and coverage from `/assessment/catalog`.

- Catalog tracks are an explicit key-free projection of the producer's IDs,
  titles, availability, counts, status, reason, dated coverage note, format
  compatibility and indicative domain counts/shortfalls. Neither question
  resolution nor stems, options, keys, rationales or item alignments enter the
  catalog. Catalog reads create no attempt or exposure records.
- Filtered catalog counts use active reviewed summaries for the selected track.
  An unavailable or unknown track has zero selectable questions, even if a
  permissive old adapter ignores the selector. An adapter without metadata keeps
  its general pool and an explicit `not_formally_mapped` ESENeph state.
- Reviewed eligibility still requires `assessment_reserved`, a reviewed status
  and a checked source/key. Mapping metadata cannot override those checks.
  Content selects exact mapped question/version pins; assessment introduces no
  topic-name inference or mapping of corrected versions.
- Flow reuses its Select, Input, Button, Notice and table patterns, Source Sans
  and existing tokens. Track comes before Topic. Changing track clears the old
  topic and reloads coverage. Failed or stale coverage cannot launch a quiz;
  retry retains the chosen track. Unavailable tracks show their actual reason.
- Coverage includes reviewed questions versus distinct families, the mapping
  check date, format compatibility, and expandable partial/gap domain rows with
  family shortfalls. Available quizzes preserve the existing 1–50 question
  request and visible shortfall behaviour. There is no exam simulation, full
  exam or clinician-review claim.
- Start sends the selected track and retains its title/note in existing coverage
  JSON. The optional title displays in session/history without requiring a
  migration or changing old sessions. Selection order, snapshots, key/family
  versions, idempotency, exposure, committed answers, scoring buckets and source
  currency logic remain intact. Generated practice stays separate.

## Owned changes

| Path | Change |
| --- | --- |
| `runtime/renulus/assessment/content.py` | Track metadata projection, legacy fallback and availability guard |
| `runtime/renulus/assessment/repository.py` | Content-owned catalog tracks, selected counts and session coverage title/note |
| `apps/desktop/src/modules/assessment/index.tsx` | Track selection, guarded launch, coverage and retained title |
| `apps/desktop/src/modules/assessment/types.ts` | Local consumer types for track/domain metadata and additive coverage |
| `apps/desktop/src/modules/assessment/index.test.tsx` | Real API fixture for explicit synthetic mapping; selection, unavailable and recovery checks |
| `apps/desktop/src/modules/assessment/assessment.css` | Token-based coverage disclosure and scrollable domain table |
| `tests/assessment/test_track_catalog.py` | Synthetic mapped contract adapter and focused catalog/selection/pin regressions |
| `docs/implementation/finalise-assessment-track.md` | This evidence and integration handoff |

No content files, immutable releases, shared schemas/contracts, migrations,
generated streaming implementation, subscription-worker tests, global tokens,
primitives, dependency files or other lanes were edited.

## Verification

Tests use the existing public Python environment, with this lane's `runtime`
inserted at the front of `sys.path` **before** importing Renulus. The unmodified
editable finder otherwise resolves to the integration checkout. The UI fixture
does the same and asserts the resolved source path. No shared editable install
or dependency tree was changed.

| Check | Result / receipt in this worktree |
| --- | --- |
| Python assessment, real synthetic content-repository and source-currency batch | 33 passed; `.local/finalise-assessment-track-python.xml` |
| Final expanded track catalog suite | 12 passed; `.local/finalise-assessment-track-catalog.xml` |
| Final assessment/catalog check after the explicit legacy track keyword | 29 passed; `.local/finalise-assessment-track-final-python.xml` |
| Assessment UI through isolated real local API, including existing generated/temporary/retry flows | 10 passed; `.local/finalise-assessment-track-ui.xml` |
| Renderer typecheck | `npm run typecheck`, passed after the final UI tests |
| Production renderer | `node node_modules/vite/bin/vite.js build`, passed; bundled font assets emitted |
| Patch whitespace | `git diff --check`, passed |

The synthetic mapped adapter deliberately includes two variants in one family,
an unmapped topic and an uncovered indicative domain. Tests exercise exact
selectors, no key lookup during catalog reads, projection of future unwanted
fields, unknown/unavailable tracks, unchecked keys, family deduplication,
idempotent start, corrected versions and withdrawals with retained historical
scores. UI tests assert the actual POST selector and disabled/recovery states.

The built Flow renderer was inspected with the same synthetic API and
disconnected providers. The saved 1280×800 pixel capture is
`.local/assessment-track-preview/selected-track-wide.png`; the browser reported
a 1683×1052 CSS viewport. Track/control alignment, coverage copy and review
layout were readable. `document.fonts.check` confirmed Source Sans 3 and the
renderer loaded its bundled WOFF2. The initial dev preview's managed-junction
font request returned 403; built preview resolved this verification issue
without editing shared Vite configuration.

Preview ownership is recorded in
`.local/assessment-track-preview/owned-processes.json`. The backend process tree
(root PID 42716) and built renderer (PID 44008) were verified as owned and
stopped at 11:28:57 UTC on October 5, 2026. The earlier dev renderer (PID 7592)
was also stopped before the built preview. See
`.local/assessment-track-preview/close.json`. No private profiles, providers,
helpers, native delivery work, heavyweight slot or heartbeat were used.

## Remaining integration gate and limits

Parent `C:/Renulus-native-delivery/desktop-20261005/repo` was at `50aac06c` on
the last read and did not yet contain `track_metadata()`. Integrate the content
producer (`604b6d11`) and this consumer, then run the content-track and affected
assessment tests together against the actual active immutable 1.1.1 release.
The synthetic producer contract and legacy repository checks do not establish
that parent combination; this handoff does not mark it passed. No prerequisite
files were copied or cherry-picked into this owned lane.

Narrow-window visual verification remains unproved: resizing timed out and the
preview automation host then disconnected. No repeated unavailable-host call or
private/native browser fallback was attempted. The domain table has a bounded
scroll region and the existing responsive Flow layout is preserved.
Live subscription behaviour, installed/native acceptance and content efficacy
are outside this bounded consumer check.

## Focus-only checkpoint — October 5, 2026

The integration owner's actual renderer run at `8c6c4b18` failed 1 of the 10
tests: `commits, shows actual source feedback, pauses, resumes and reviews
without prototype scores`. After Next question and awaiting Question 2, the
assertion at the original `index.test.tsx:189` expected `LEGEND` but observed
`BODY`. The other nine tests and the parent's post-integration TypeScript check
passed. This reported failure supersedes the earlier isolated 10-pass result
as evidence about that integration run.

This follow-up started from the clean `71420716` assessment lane on
`build/finalise-assessment-track`. Prerequisite merge `54187513` incorporates
the specified integration `8c6c4b18`, including the assessment slice integrated
as `16ad199d` and content release 1.1.1. The merge had no conflicts and its tree
matched `8c6c4b18`; no working edits were reset or copied from other lanes. The
missing-producer note above describes the first handoff, before this merge.

No persistent production focus failure was reproduced in the bounded local
checks. The unchanged journey passed alone and after its three preceding
tests. The existing renderer focuses the newly visible question in an effect
keyed by `visibleQuestionId`, prioritises a source-currency notice when present,
and focuses the feedback heading on commitment. Finding the question text
does not synchronise the test with completion of that focus effect.

The repair waits for the original actual `LEGEND` and `H2` focus assertions.
For Question 2 it also requires `document.activeElement` to be that question's
own legend. The source-help focus-preservation assertion remains in place.
These checks use the existing `waitFor` timeout and continue to fail if actual
focus never arrives; they add no forced focus, sleeps, mocks or weaker fallback.
The production renderer, Flow styles, keyboard rules and focus priorities are
unchanged.

| Check | Observed result / receipt in this worktree |
| --- | --- |
| Unchanged failing journey alone | 1 passed, 9 skipped; `.local/assessment-focus-repair/reproduce.junit.xml` |
| Unchanged journey with preceding suite sequence | 4 passed, 6 skipped; `.local/assessment-focus-repair/reproduce-sequence.junit.xml` |
| Full repaired `src/modules/assessment/index.test.tsx`, run once | 10 passed, 0 failed, 0 errors, 0 skipped; `.local/assessment-focus-repair/final.junit.xml` |
| Patch whitespace | `git diff --check`, passed |

The full run took 52.47 seconds; its JUnit timestamp is
`2026-10-05T14:46:57.308Z`. The final JUnit SHA-256 is
`1b5eb3f20c0596586eb9585aabb9284be444c6f1aa3944fa3a601293049e324b`.
Matching verbose logs and a source/hash/commit receipt are in the same ignored
directory. The fixture asserts this lane's runtime import path, uses an
allocated local port and disposable synthetic profile, and stops its own API
process tree during teardown. It uses synthetic content/generation adapters;
no live provider, actual helper, native workload or installed profile was used.
No unrelated suites, build or TypeScript rerun was performed; the parent
TypeScript pass above is the owner's supplied evidence.

Current Windows acceptance follows the owner's October 5 decision recorded in
`docs/DECISIONS.md`: an unsigned build installed and validated on the current
Windows PC. Mandatory signing and a separate clean PC/VM were removed; they
remain optional future distribution checks. Matching source/artifact
provenance, bundled runtime without developer tools in the app PATH, fresh
isolated installation, shutdown/reopen, recovery and connected journeys remain
required. This renderer receipt does not establish installed acceptance.

The focus-only checkpoint commit `f8207735` owns exactly
`apps/desktop/src/modules/assessment/index.test.tsx` and this report. Its hash
and final changed paths are recorded in
`.local/assessment-focus-repair/receipt.json` and the final handoff. No new
backend, GeneratedPractice, shared-module, CSS or type edits; no agents, push
or native-slot work. The owner extended the request after this checkpoint with
the selector prerequisite below. Its original receipt remains preserved.

## Study-to-Test selector repair and final combined receipt

The owner's additional narrow prerequisite references the published Study/Home
commit `e3d74e3078ed6514ebc20fcd710137e0460de011`. Its Open Test action emits
`nav.handoff.track` as `general_nephrology` or `esen_eph`; the activity handoff
can also retain its topic. Assessment previously initialised only the topic and
always selected General nephrology, losing an ESENeph handoff. The producer
source was inspected read-only; parent owns its review and integration.

Assessment now initialises its selected track from either allowed value.
Missing, unknown or non-string values fall back to `general_nephrology`. Topic
initialisation, later manual track changes, availability guards, temporary
scope and all original focus/keyboard behaviour are preserved. The production
change is confined to this initial state in `index.tsx`.

Three added cases pass the published handoff shape through the real
`NavigationProvider`, launch a reviewed quiz through the isolated real local
API, and inspect the actual POST selector. They cover ESENeph, General
nephrology and an unknown value falling back to General nephrology. They also
assert one start request and the expected empty topic selection for Home's
track-only handoff. This is consumer/navigation-contract evidence; the parent
continues to own the complete Study UI integration.

| Final combined check | Observed result / receipt in this worktree |
| --- | --- |
| Full `src/modules/assessment/index.test.tsx`, once after both fixes | 13 passed, 0 failed, 0 errors, 0 skipped; `.local/assessment-focus-selector-repair/final.junit.xml` |
| Renderer TypeScript check after the production selector change | `node node_modules/typescript/bin/tsc --noEmit`, passed; `.local/assessment-focus-selector-typecheck.log` |
| Patch whitespace | `git diff --check`, passed |

The combined file run took 22.28 seconds, with JUnit timestamp
`2026-10-05T14:53:58.974Z` and SHA-256
`db08b3070be7ff6ed822ac3ab9def32d288a3e7a3e20e9acced21f0a6c0e5092`.
The earlier 10-test run belongs to the focus-only checkpoint before the owner
added this prerequisite. No other suites or full-file reruns followed the
combined 13-test pass. The same synthetic fixture boundaries and own-process
teardown apply. Windows acceptance remains unsigned current-PC delivery as
recorded above; this check establishes no installed/native acceptance.

The final selector commit follows `f8207735` without rewriting that checkpoint.
Together the owned repair changes exactly `index.tsx`, `index.test.tsx` and
this report. Both commit IDs, cumulative changed paths, source hashes and final
evidence are recorded in `.local/assessment-focus-selector-repair/receipt.json`
and the final handoff. No backend, GeneratedPractice, shared-module, CSS or type
writes, agents, live providers, actual helpers, native work or push were added.
The extended bounded task ends with that local commit.
