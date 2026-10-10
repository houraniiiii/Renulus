# Whole attempts integration

The default `AttemptsPage` reads the shell navigation handoff. The named
`AttemptPage` also mounts directly. Both accept `attemptId`, `versionId`,
`mode: 'study' | 'test'`, and `timing: {kind:'untimed'} |
{kind:'timed', duration_seconds:number}`. Optional consumers are
`onHelp(receipt)`, `onOpenReference(reference, receipt.context)` and
`onRetake(versionId)`. The shell owns navigation and Workspace mounting.

`attempt_api.create_router(services)` installs `whole_attempts` in the services
registry and routes under `/assessment`. The shared policy middleware calls
`whole_attempts.reconcile_all()` before dispatch. A caller already holding the
canonical transaction can use `reconcile_in(conn)`. The implementation uses
the shared `storage.assessment_policy` helpers; Test start and finalisation
advance its revision in the attempt transaction. Parent middleware owns the
profile policy and response/stream enforcement across other modules.

Study help commits exposure before returning a receipt with
`{attempt_id,item_id,version_id,draft_revision,policy_revision,kind}` context.
Delayed consumers must validate it with
`whole_attempts.require_help_context_in(conn, context)` before publication.
The receipt alone does not prove that Notes, Chat or Workspace integration
has consumed it. Until a callback exists, the corresponding control is
unavailable. The controller emits `renulus:assessment-policy` on a verified
revision change; the shell must invalidate cached assistance immediately.

## Evidence consumer contract

New learning evidence has `kind='assessment-test-answer'` and
`entity_id=attempt_id`. Do not dispatch it to legacy `assessment_attempts`.
Its payload contains no answer key, explanation or selected answer text:

```text
attempt_id, version_id, commit_id, item_id,
question_id, question_version, key_version, family_id, family_version, topic_id,
mode, origin, review_quality, reviewed, bank_cohort_eligible,
assisted, repeat, score_bucket, outcome, correct, committed_at
```

`reviewed` and `bank_cohort_eligible` capture eligibility at commitment. Origin
and mode alone never establish reviewed eligibility: a personal edit with
reviewed-bank origin remains personal. `assisted` and `repeat` are independent
flags. `score_bucket` is the attempt's display cohort; consumers should retain
both flags rather than reconstructing one from that bucket. `outcome` is
`correct`, `incorrect` or `unanswered`; excluded entries remain in the frozen
result but emit no learning evidence. Study drafts emit nothing before an
explicit commitment. A Test blank is a final `unanswered` commitment.

Each attempt stores an independent immutable version plus the full private
provenance envelope. Historical result entries keep readable question text.
`pinned_attempt_snapshot_in(conn, id)` supplies both typed `version` and
`pinned_provenance` to retained reports even after the live collection is
removed. This private snapshot is not a start-authorisation shortcut.

## Timing and retry authority

The repository persists clock high-water and pause state; remaining time is
computed by the backend. A same-process wall-clock rollback uses its monotonic
anchor; a restart below persisted high-water conservatively expires timed
active work. Test expiry commits only backend-durable drafts. Manual submit
waits for displayed draft saves and supplies the complete latest draft.
Study expiry preserves pending drafts without grading them.

Commands retain exact request hashes and acknowledgements. Policy gating
precedes replay; evidence, immutable final result and policy release share
one transaction. An expected request error preserves already reconciled
expiry, while a storage/evidence error rolls the entire transaction back.

## Verification boundary

`session.test.ts` checks controller concurrency and ambiguous acknowledgements.
`attempts.connected.test.tsx` is an opt-in actual HTTP/SQLite renderer journey
using an owned loopback API with synthetic reviewed content. Set
`RENULUS_ATTEMPT_TEST_ORIGIN` only for that synthetic server. No API response
fixtures or providers are used in that journey. Without the variable it is
explicitly skipped. Backend persistence/policy/timer tests are in
`tests/assessment/test_whole_attempts.py` and require published migrations
003/004 and the actual saved-test producer.

These checks do not establish native Windows acceptance. Integration still
needs the assembled shell start/resume/policy/timer/finalisation flows,
Workspace/Chat/Notes receipts, Home/Memory consumption, all origins and
populated export/restore. DC13/DC14/DC15 remain open until that evidence.

At the merged `c19d1493` baseline, the actual whole-attempt backend suite
passed 21 checks, and the renderer passed three actual HTTP journeys plus
seven controller checks. The timer journey closes the page, reconciles expiry
through the shared policy endpoint, reopens the immutable result, deletes the
collection through its API and saves a retained report through the renderer.
External receipts are `C:/Renulus/scratch/design-c/attempts/backend-pytest-09.txt`
and `frontend-connected-04.txt`; the owned backend shut down after the checks.

The `19125498` follow-up reproduced a late-save failure against actual HTTP:
expiry committed the durable Test, but a refused draft left the renderer dirty
and suppressed every later poll. The controller now reads while a save is no
longer in flight and accepts a frozen terminal result without applying the late
choice. Active work and ambiguous commands remain protected from replacement.
Four actual HTTP journeys plus eight controller checks passed in
`frontend-connected-05.txt`; five focused authority/expiry/publication/provenance
backend checks passed in `backend-pytest-11.txt`. Both receipts remain in the
same owned scratch root, alongside the preserved failing reproduction.

At merged baseline 8e9f4403, the actual Tests pinned-version setup navigated
through the shared NavigationProvider to default AttemptsPage, retaining Test
mode and an exact 60-second duration. Setup/handoff created no attempt; Start
Test established the timer. That journey and the earlier four HTTP journeys
plus eight controller checks passed in frontend-connected-06.txt. Three
parameterised backend checks published original synthetic generated/imported/
nightly versions through the actual trusted collection writer, then exercised
both Study and Test. They retained origin, mode and pinned provenance and emitted
personal evidence without reviewed eligibility (backend-pytest-13.txt).
These are published-version consumer checks, not generation/import/scheduler
producer acceptance. No provider request was made.

After the clean normal merge of parent baseline `2122f875`, the full current
whole-attempt persistence suite passed all 24 cases in `backend-pytest-15.txt`.
All five actual HTTP/SQLite renderer journeys and eight controller checks passed
in `frontend-connected-07.txt`; the desktop source/Electron typecheck passed
with `tsconfig-desktop.json` (`typescript-desktop-06.txt`). All receipts remain
under the same owned scratch root. The synthetic HTTP server was stopped after
verification. Home/Memory still omit `assessment-test-answer`, and the shell
still needs help/reference consumers. These passes do not close DC13/DC14/DC15
or establish assembled hidden-app, native, producer or export/restore acceptance.
