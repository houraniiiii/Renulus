# Today: durable actions and recovery

2026-10-05 UTC · issue #10 · `build/study-final`, based on `956bd2a7`.

This follow-up fixes the existing Today renderer. Production edits are limited
to `modules/study/index.tsx` and `study.css`; there are no backend, shared-hook,
schema, dependency or Library edits. It retains Flow's focal learning question
and existing layout.

## Demonstrated gaps and decisions

Before the patch, a confirmed move's subsequent home refresh unmounted ordinary
question/preferences/date controls and lost focus. Rapid date selections issued
overlapping PATCH requests. A late preferences save replaced newer edits and
closed the form. The old mutation error's Retry merely cleared the error.
These failures were reproduced in the mounted renderer before implementation.

Home refresh now retains the last confirmed snapshot and mounted controls, with
a small refreshing status or an actual retryable read error. Each activity has
one outstanding write; rapid dates coalesce to the latest queued intent. Pending
states belong to that row, so independent activities remain usable. Date drafts
remain visible while saving, including an incomplete date that sends no PATCH.

A failed or lost mutation response means the change could not be confirmed. The
renderer retains the latest intent and stops its queue; explicit Retry performs
the write. It does not infer server rollback or mark a task complete locally.
Retrying the existing absolute date/state/goals endpoints is supported by the
backend's existing persistence semantics.

Preferences and proposal requests exclude duplicate global writes. Proposal
waits for activity writes and prevents manual mutations during replacement. A
preferences save cannot overwrite later edits: the form remains open, preserves
focus and explains that newer edits are still unsaved. Failed preferences and
proposal operations have working Retry actions. All mutation requests abort on
unmount; late outcomes cannot dispatch queued writes, refreshes or UI changes.

## Checks

| Check | Result | Evidence covered |
| --- | --- | --- |
| Mounted Study regressions | 13 passed | Focus/draft retention, serialized and coalesced date changes, independent row availability, newer preferences edits, move/skip/complete/goals/proposal retries, incomplete dates, refresh failure, unmount cancellation |
| Real Today API journey plus existing Study tests | 5 passed | Original pack, committed incorrect answer, persisted preferences/manual overrides, application restart and another proposal, unchanged historical feedback/score |
| Desktop typecheck | Passed | Existing TypeScript contract |
| Desktop build | Passed | TypeScript, Vite renderer and Electron build |
| `git diff --check` | Passed | Scoped patch whitespace |

Reproduction from this worktree, using the parent's existing bootstrap
dependencies without copying profiles or credentials:

```powershell
# Repository root
& ../Renulus-wt-integration/.venv/Scripts/python.exe -m pytest tests/study/test_today_journey.py tests/study/test_study.py -q

# apps/desktop
npm test -- src/modules/study/study.test.tsx
npm run typecheck
npm run build
```

The mounted tests use the actual Study, Navigation and API transport, with
controlled synthetic fetch responses. They control response order/failure and
assert retained DOM identity/focus and dispatched requests rather than mocking
the page's internal actions. The real API test uses a fresh SQLite profile and
the bundled original pack's actual assessment producer and immutable key. The
only backend test warning was the existing Starlette TestClient deprecation.

## Local browser journey

An isolated backend on port 8893 and renderer on 5317 were exercised in Chrome.
The helper in `test_today_journey.py` bootstrapped all 27 topics and deliberately
submitted a wrong answer in T03. Today displayed 0 correct from 1 fresh
unassisted reviewed answer and proposed a T03 mistake-review tied to that
question. No educational review was invented for this check.

Through visible controls, the review was moved to 2026-10-13; preferences were
saved as 4 hours/week, exam date 2027-03-01, ESENeph preparation and T03/T21.
The Foundations activity was skipped and Clinical assessment completed. The
ordinary synthetic question draft remained during saves and home refreshes.
A deliberate page reload and another proposal retained the moved date, all
three manual overrides, preferences, selected topics and original 0/1 score.
Full application restart persistence is covered separately by the API test.

Native date keys were used to verify actual date changes: this browser
controller's fill changed a date input's DOM value without notifying React.
The isolated dev server also reported a blocked font URL through the reused
node_modules junction, so the inspected dev screenshot used the browser's font
fallback. The production build passed; this lane does not establish installed
Windows rendering. Local screenshot: ignored
`.local/verification/study-final/reload-propose.jpg`. Both owned servers and
the owned browser tab were stopped after verification.

## Goal and limits

The #10 application acceptance is demonstrated: a committed mistake changes
the next proposed study; manual changes and preferences survive restart; a
fresh home exposes the topic directory without invented mastery. Observed
assessment remains derived from committed answers. The parent independently
reported a live T03 move to October 6 surviving proposal/reload on the
integration branch. The reliability follow-up is ready for integration.

No live generation, paid/keyed provider, patient data, acquired source bodies,
native viewer, or corpus mutations were used. These checks establish local
application rules and persistence, not educational efficacy, independent
human content review, full examination coverage or provider/network proof.
The original evidence remains in `study-evidence.md`; this journey supplies
the real assessment producer and renderer verification that it left pending.
