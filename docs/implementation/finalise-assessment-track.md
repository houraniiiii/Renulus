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
