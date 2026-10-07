# Today reviewed-update handoff — 2026-10-07

## Scope and outcome

Branch `codex/finish-reviewed-update-link-20261007`, worktree
`C:/rn-finish-20261007/lanes/reviewed-update-link`, based on
`577f1c3741e7a05a5fe11ef78c6b3e118931aee2` (installed product source
`b8a3c177945268706227ea3b8355c2fcd5d6bafb`).

Today already passes the selected reviewed update as
`navigate('updates', { payload: { entry_id } })`. Updates previously ignored
navigation and could only open a queue row. The renderer now consumes the
volatile handoff through the real shell navigation context and fetches
`GET /updates/entries/{encoded entry_id}`. It verifies the returned identity,
selects the entry's actual review state, resets the queue offset and opens the
detail independently of the current queue page. It reuses the existing detail,
draft initialization and mark-read condition: only a reviewed entry without
`read_at` is marked read when opened.

An abort controller and selection version invalidate delayed results after
another handoff, navigation, unmount, manual entry/filter/page choice, or work
on the visible review. Read-confirmation failures also respect the selection
version. Loading and failure feedback reuse Flow's existing Notice/ErrorState;
a missing entry has a specific message and an explicit retry. Retry fetches
the same requested identity. Resource refreshes do not consume the handoff
again or reset an edited review; another explicit handoff, including the same
entry on a new navigation revision, deliberately opens a fresh draft.

Only these files change:

- `apps/desktop/src/modules/updates/index.tsx`
- `apps/desktop/src/modules/updates/updates.test.tsx`
- This report.

The existing test file now mounts Updates inside NavigationProvider. No optional
navigation production workaround, backend/schema/Study/native/token edits, or
replacement design were introduced. Impeccable context, harden and craft-floor
were read; the incumbent Flow primitives and detail layout remain the authority.

## Focused evidence

One Vitest worker ran only `src/modules/updates/updates.test.tsx`: **27/27 passed**,
including 13 existing Updates checks and 14 focused handoff cases. The new cases
exercise the real Updates component, navigation provider and API transport with
synthetic intercepted fetch responses:

- Exact reviewed entry absent from the returned queue page; correct detail,
  filter, topic selection and one initial read request.
- Draft/evidence retention and no repeated handoff GET or read on metadata/
  resource refresh; deliberate reopening on a new explicit same-entry handoff.
- Pending, dismissed and already-read entries: correct filter, no read request.
- Missing (404) and failed (503) lookup with visible retry of the exact entry.
- An older successful or failed lookup arriving after a newer handoff.
- Cancellation by entry selection, filter, page, navigation without a payload,
  leaving Updates, and editing the retained draft.

Command, run from `apps/desktop`:

```text
node node_modules/vitest/vitest.mjs run --config C:/rn-finish-20261007/evidence/reviewed-update-link/vitest.config.mjs --configLoader native
```

External evidence:

- `C:/rn-finish-20261007/evidence/reviewed-update-link/vitest-result.json`
- `C:/rn-finish-20261007/evidence/reviewed-update-link/vitest.log`
- `C:/rn-finish-20261007/evidence/reviewed-update-link/vitest.config.mjs`
- `C:/rn-finish-20261007/evidence/reviewed-update-link/slot.json`

Vitest 4.1.11 completed in 27.19 seconds (test execution 4.949 seconds).
The external config fixes one worker, disables file parallelism, selects only
the Updates test file and keeps Vite cache under the evidence directory.
Dependencies were reused through a temporary junction in this worktree to
`E:/Renulus-native-delivery/desktop-20261005/environment/node-3ff9b0d6/node_modules`.
The junction was removed without changing its target. Slot acquired at
`2026-10-07T15:07:48.7345809Z`, released at `2026-10-07T15:08:58.4628788Z`.
`git diff --check` passed. No desktop-wide suite, native run, provider operation,
network request, Python/backend engine, package build or GitHub operation ran.

## Installed evidence and next acceptance

The original installed receipt remains **failed and unchanged**:
`C:/rn-finish-20261007/evidence/connected/study-installed-b8-02/result.json`.
Its recorded failure is a 15-second wait for the selected-publication detail;
the omitted handoff consumer is the concrete product bug fixed here. SHA256
before and after this work:
`E8E41F51BE8131FCAA41CFBBA17A97168F61EA0611B16A5F476EF99B70502880`.

The earlier Study01 driver width 800 error, corrected to 690, is a separate
driver issue. It is not evidence for this Updates defect. Per the parent
handoff, activation, keyboard, new case, real T11 discovery of 21 records, and
the reviewed wrong-answer/manual-plan actions already have individual passes;
this patch neither repeats nor upgrades those receipts.

Mounted tests establish renderer behavior only. The parent owns source and new
installed acceptance: Today to the existing reviewed entry, then retained quiz
and plan reopen using Study02 records. No generation, discovery or quiz repeat
is needed for this patch. No installed-pass or packaging claim is made here.


## Parent source acceptance, 15:15 UTC

Reviewed and integrated as `1dde6d904dac436cafae331b5898fe45c410a6a6`.
The lane and its worktree are retired; branch and external evidence are retained.
Parent desktop build passed. Actual hidden source acceptance
`C:/rn-finish-20261007/evidence/connected/handoff-source-02/result.json`
passed at **2026-10-07T15:14:24.186Z–15:15:10.986Z**, SHA256
`1231b4812b0eab16de3497431110e41b83634724b835af51959db85bfa87db93`.

- Today opens exact existing reviewed publication
  `update_90e368a9ee685659a6228389`, review
  `review_e7e301dec492b835a34fab42`, including the saved synthetic learning note.
- Existing installed-b8 quiz feedback, manual activity date, goals and case IDs
  remain unchanged. Keyboard Start returns to that exact feedback; no new answer.
- Normal close/reopen preserves the entire goals/plan/review/update response,
  exactly one review and zero completed provider requests. The same Today link
  works after reopen. No new discovery, review, import or generation is run.
- Normal closes take0.1977319/0.1931247s, with no remaining owned process,
  visibility/focus violation or renderer error. Parent inspected the exact
  publication screenshot: title, dates, saved note and inspected-source fields
  are readable. The reopened capture has the same SHA256.

`handoff-source-01` stays **failed**: the driver incorrectly searched textarea
content using `innerText`. The exact detail/title had already opened; this was
a verification defect, not a second product defect. The corrected driver uses
the labelled textarea value. Original driver bytes and the failure are retained
with hashes in `evidence/reviewed-update-link/driver-repair.json`.
These are source results, not installed acceptance. The matching1dde6d90
manufacture/installation is running under `evidence/release-1dde6d90`; promotion
requires its own exact handoff/lifecycle receipt. The normal launcher stays cb59.
