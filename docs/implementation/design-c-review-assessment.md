# Design C assessment — adversarial implementation review, pass 1

October 10, 2026. Source baseline **1b30a89687cfcc5fb13b1cf824bbc43c19f870ed**
contains **528025ff0b22477c12ee1512e0e7d15297a6e888**. Worktree
`C:/Renulus/dev/worktrees/dc-review-assessment`; branch
`codex/dc-review-assessment`. Sole write reservation: this report. No source,
spec, migration, manifest or ticket status was changed; no push was performed.

**Disposition:** publish the disclosure, pinned-history, draft/finalisation and
cohort contracts before dependent assessment coding. The spec's outcomes are
sound, but existing APIs are not a complete C Study/Test engine. Findings below
are actual legacy behavior and pre-coding contract challenges, not claims that
new C features have failed. DC12–DC19 remain open.

Read AGENTS.md, README.md, PRODUCT.md, DESIGN.md, docs/PROJECT_BRIEF.md,
docs/WORKSPACE.md, docs/DECISIONS.md, the complete
[C spec](../planning/DESIGN_C_IMPLEMENTATION_SPEC.md),
[architecture](../planning/ARCHITECTURE.md),
[parallel rules](../planning/PARALLEL_WORK.md),
[app-control rules](APP_CONTROL.md) and initial [reservations](EXECUTION.md).
The direct assignment's synthetic root is
`C:/Renulus/scratch/design-c/dc-review-assessment/`, overriding the older
execution table's `review-assessment` profile label.

The parent's latest proposed next lane names new
`runtime/renulus/assessment/attempt_repository.py`, `attempt_api.py` and renderer
`apps/desktop/src/modules/attempts/` only. Collection/version ownership is separate.
**That implementation is not started or authorised by this review.** Wait for
the parent to publish the shared contract reservation. Collection/generation
have separate owners; existing assessment router/repository have one integration
adapter writer. Proposed shared contract **efcc7824** was read with `git show`
without switching this worktree. It changes `packages/contracts/design-c.md`;
its assessment-specific challenges are recorded below. This handoff does not
claim that the parent's evolving schema-2 recovery tests have already fixed them.

## Evidence and limitations

Inspected actual assessment, content, Memory and Study API/repository/service
methods; Learn, Cases, Library, retrieval, Updates, export/recovery, shell and
renderer consumers. An AST route inventory of all ten routers is retained
outside Git. Local FastAPI/SQLite probes seeded original synthetic token
questions across dialysis, glomerular and transplant topics. Content bootstrap
was disabled; a declared synthetic annotation adapter and Provider were used.
Actual assessment/content/Memory/Study/Learn APIs and the actual generation
consumer ran. Runtime connection modules, helper engines and background/outbox
workers did not start. No credentials, owner profile, acquired corpus, network
request, OS input, app window, installation or live model was used.

The first external probe stopped at an incorrectly seeded nullable chat run ID;
its partial `profile-pass1` is retained. Fixing only that probe and using a fresh
`profile-pass1b` completed thirteen observations. These are software behavior
receipts, not clinical or new C UI acceptance.

External evidence under the assigned root:

- `evidence/probe.py` and `evidence/probe-results.json` — thirteen observations.
- `evidence/route-inventory.txt` — exact baseline HTTP methods and callees.
- `pytest-pass1/` — isolated regression state; no repository cache was created.

The operations/results below make the report useful without these local files.
In R06, the JSON field `mistakes:false` is the first returned mistake's
`correct` flag, not an assertion that the mistake list is empty.
Re-running the probe requires a fresh explicitly named profile; it refuses to
overwrite a database. Use `C:/Renulus/dev/python/Scripts/python.exe`,
`PYTHONPATH=C:/Renulus/dev/worktrees/dc-review-assessment/runtime`,
`PYTHONDONTWRITEBYTECODE=1` and TMP/TEMP within the assigned synthetic root.

### Baseline regression result — not green

Executed `python -m pytest tests/assessment/test_assessment.py
tests/assessment/test_generated.py tests/assessment/test_source_currency.py
-q -p no:cacheprovider --basetemp
C:/Renulus/scratch/design-c/dc-review-assessment/pytest-pass1`.

**33 passed, 5 failed, 1 warning in 101.78 seconds.** The warning is the installed
Starlette/httpx deprecation. The failures are existing fixture prerequisites:

| Failure | Observed cause and owning follow-up |
| --- | --- |
| `test_actual_cases_producer_commits_temporary_handshake_and_invalidates_answers_on_edit[True]` | `cases.save()` reaches `save_originals()` and raises `no such table: case_attachments`. The explicit producer helper applies only `cases-001`. Its owner must apply actual additive migrations, including `cases/migrations/002-originals.sql`. Preserve production original handling. |
| Four `test_source_currency.py` tests: detected notice; review/dismissal replay; dismissal/unavailable state; identity/allowlist | `currency_app()` bootstraps current content then installs foundations `1.0.0`. Installation raises `ContentConflict: A newly published question must advance its version` before currency assertions. Its owner must pin deterministic fixture/bootstrap selection. Do not weaken immutability to make the old pack install. |

Sources: [actual_cases helper](../../tests/assessment/test_generated.py), lines
294–311; [currency_app](../../tests/assessment/test_source_currency.py), lines
22–27; [save_originals](../../runtime/renulus/cases/originals.py), line 65;
[content storage](../../runtime/renulus/content/repository.py), lines 53–73.
No source/fixture repair is included in this report-only reservation.

## Critical findings before dependent coding

P1 is a prerequisite to the claimed connected outcome; P2 is a semantic or
verification gap to settle for acceptance. These are review priorities, not new
feature tickets.

### A1 — P1: policy must precede replay and apply across the profile

The server boundary checks local host/origin/token, not assessment state.
Reviewed `answer/help/transition` call `_replay()` before session checks.
Generated `mutate()` returns a command replay before its work callback. Learn
`ask` can replay stored assistant text without generating anything. A check only
on a new C route, or only on the requested session, leaves old sessions and
acknowledgements available during another unfinished Test.

**R05:** start/answer/end a synthetic reviewed session, then POST the identical
answer body/key. Response: 200, saved explanation and
`correct_option_ids=["a"]`, although the session is ended. GET review also returns
200 with feedback. This is valid legacy Study retry behavior; it becomes a C
bypass if reachable during a profile-wide unfinished Test. **R01:** two legacy
reviewed sessions start active without conflict; this is not evidence of two new
C Tests.

**Required contract:** authoritative policy lookup before dispatch and before
replayed disclosure; expiry reconciliation before deciding restriction; coverage
of other session IDs, generated/volatile sessions, historical review, old keys
and ordinary scope payloads. Blocked replay must not return its saved help/key
body. Original retries remain idempotent once permitted. The attempt lane owns
the policy producer; parent owns cross-router/server/shell adoption. Legacy
pause/end cannot release the new C boundary.

Sources: [server](../../runtime/renulus/server.py), lines 48–65;
[reviewed repository](../../runtime/renulus/assessment/repository.py), lines
48–58, 259–263, 301–305, 352–356;
[generated repository](../../runtime/renulus/assessment/generated_repository.py),
lines 271–303; [Learn replay](../../runtime/renulus/learn/api.py), lines 53–69.
The efcc7824 replay/policy wording addresses the intended rule; actual adapters
and negative connected requests are still necessary.

### A2 — P1: all Study help producers need durable assistance before return

Dedicated reviewed `help()` correctly sets assisted/exposure/command state in a
transaction before returning; presentation also commits before the question
returns. Other producers accept ordinary scope or no scope and do not know the
current Study item.

**R02–R04/R12:** two starts produce two durable presentation rows and zero graded
answers. Reading a Memory fact containing `SYNTHETIC_HELP_SENTINEL` and a source's
question references returns 200; assisted stays 0 and hint/source exposure count
stays zero. A saved chat returns its assistant sentinel independently. A
synthetic Updates annotation returns `SYNTHETIC_KEY_LOCATOR` on an unanswered item
with assisted still 0. These receipts establish unmediated content return, not
medical usefulness.

**Required contract:** attempt/item/expected position or revision and operation
identity for help, resolved server-side. An arbitrary `scope=study` is not an
unassisted-use entitlement. Record assistance before sources, notes, stored
chat, snippets or stream chunks return. Failure can conservatively retain an
exposure; content cannot return first with best-effort recording afterwards.
Keep presentation/help separate from graded evidence. Clarify how ordinary
content navigation while a Study item is uncommitted is mediated.

Starting Test must suppress open help panes and in-flight results with a policy
revision/epoch. Item-A results cannot populate item B; pre-Test help cannot
reappear after start. Abort alone does not clear completed responses/React state.
Transport already uses `cache:no-store`; audit stored replies and application
state, not an invented HTTP cache defect.

Sources: [presentation/help](../../runtime/renulus/assessment/repository.py),
lines 127–139, 299–329; [Memory API](../../runtime/renulus/memory/api.py), lines
22–44, 70–72; [source references](../../runtime/renulus/content/repository.py),
lines 271–291; [reviewed callbacks](../../apps/desktop/src/modules/assessment/index.tsx),
lines 188–198; [generated callbacks](../../apps/desktop/src/modules/assessment/GeneratedPractice.tsx),
lines 340–352.

### A3 — P1: neutral annotations must omit locators and free-text corrections

`SourceCurrency.for_item()` omits literal keys but includes entry IDs, source
IDs/register IDs and locators. Precommit UI displays them and offers View source
updates. `ContentGateway.annotation()` includes complete withdrawal prose. The
withdrawal POST acknowledgement also returns that prose.

**R08:** withdraw the synthetic question with reason
`SYNTHETIC_WITHDRAWAL_KEY: choose b`. GET the other unanswered session returns that
reason in `current_item.content_status.withdrawal.reason` before commit. Answer
then fails with 409 `content_changed`. R04 independently returns a locator without
assistance bookkeeping.

**Required contract:** during Test return a neutral availability/currentness
projection with no source/notice links, exact locators, findings, replacement-key
details or withdrawal prose. Study source details go through assistance. Apply
to history/session lists/replays/mistakes, not only the current-question UI.
Question reports acknowledge only identity and neutral saved state; no help,
key/quality change or automatic regrading follows.

Sources: [currency](../../runtime/renulus/assessment/currency.py), lines 17–44,
50–88; [content annotation](../../runtime/renulus/assessment/content.py),
`annotation()`; [notice UI](../../apps/desktop/src/modules/assessment/SourceCurrencyNotice.tsx);
[withdrawal API](../../runtime/renulus/content/api.py), lines 193–197.

### A4 — P1: separate identities/mode/cohorts and preserve unavailable pins

Legacy `assessment_sessions` is a quiz; `assessment_attempts` is one answer.
Legacy mode is reviewed/generated, with separate generated tables. **R01:**
`mode=test` returns 422; the working request returns `mode=reviewed`. Do not change
the meaning of these columns or historical evidence. efcc7824 correctly proposes
new whole-attempt identity and independent origin/quality/Study–Test fields.

Content `_store()` and SQL triggers are useful immutable foundations. **R09**
confirmed changed same-version publication is rejected. New saved versions need
ordered question/key pins or immutable personal snapshots, family IDs, count,
digest, provenance and terms. Rename/archive changes collection metadata; edits
append versions. Retake/card/report pins do not silently move to the latest
version or reset family identity. Import/model JSON cannot grant reviewed-bank
membership; Test mode never promotes personal scores.

**Parent's critical schema-2 clarification:** version→attempt, version/attempt→
report and version→published job outcome are historical provenance links, not
ownership cascades. In the initial exchange these links were absent from the
parent's typed PARENTS registry. efcc7824 proposes owned root→version plus a hard
`attempt.version_id → version.id` FK, report links and nullable published-version
link, while generic restore text prunes unavailable links. Physically pruning
an owned version can therefore break the FK or destroy attempt/report/job rows.
Dropping those historical rows is not an acceptable repair.

**Preferred concrete representation:** attempt stores immutable
`pinned_version_id`, manifest/items/key snapshot and digest, plus nullable
`live_version_id` to the collection version. Reports retain immutable pinned
test/version/question/key/item identifiers and relevant attempt identity with
an unavailable marker and optional nullable live pointers. Job outcomes retain
the published immutable version ID/digest/count and terminal outcome even when
their live version pointer becomes null. Typed recovery nulls unavailable live
links and marks provenance unavailable; it retains the independent historical
row and snapshot. It must distinguish this from a project membership link that
can be dropped. JSON snapshots/provenance require declared traversal too.

**Valid alternative:** retain pinned immutable version rows indefinitely and
soft-delete the collection/root; do not prune any referenced version. Whichever
representation parent adopts must be frozen with exact columns/relations before
DDL, not inferred independently by the attempt and collection writers. Do not
add hard FKs from immutable historical pin fields to physically prunable rows.

Required recovery reproductions: create version→attempt→draft/exposure/report and
job→published-version, delete the collection/root, export/restore with newer
tombstones; reopen history/report/job and retain snapshots plus unavailable
state. Repeat with missing version row, backup before/after deletion, independent
attempt deletion, and same string ID in another namespace. Prove typed link
removal never drops unrelated provenance, old grades or terminal job outcomes.
No passing parent schema-2 receipt is claimed by this reviewer.

**Integration update at 388687c2:** source read with `git show`/`git grep` confirms
`storage/relations.py` now declares `UNAVAILABLE_REFERENCES` for attempt
`live_version_id`, report `live_version_id/live_attempt_id`, and job
`live_published_version_id`, clearing those pointers while preserving historical
rows. Draft/exposure remain owned by attempt. The contract Markdown still shows
the older version/report/job arrows. Parent is preparing assessment migration
004; its exact columns, JSON validation and connected restore receipts must
agree with the new live-pointer representation. This source update is progress,
not a reviewer claim that integrated recovery has passed.

Legacy adaptation must retain IDs, already-revealed feedback and original
partial denominators. An ended three-of-ten session remains that historical
Study result; do not add seven incorrect blanks. Trusted backend
`get_question_version()` is not a public detail API; preserve that boundary.

### A5 — P1: finalisation needs a latest-draft protocol and one transaction

Selection is component-local `useState('')`; reload/adopt clears it. Storage has
no editable draft/mark/position protocol. Legacy AnswerRequest requires a
nonempty answer and reviewed `answer()` accepts exactly one option; it is not a
nullable Test draft contract. It immediately publishes feedback and evidence.

**R06:** one incorrect legacy answer immediately affects assessment progress,
mistakes, Study progress and a proposed mistake-review activity. **R07:** records
export returns unanswered item snapshots with keys and stored command replies.
A loop of legacy answers for final submit would expose partial scores and could
leave partial commits after failure.

**Required contract:** nullable/empty selection, marks, position and monotonic
draft revision; stale-write rejection before and after finalisation. Manual
submit supplies the latest full displayed draft or the exact acknowledged
revision containing it. efcc7824's `expected_draft_revision/latest_draft` shape
is appropriate, provided parent defines revision validation and atomic
save-and-finalise semantics. A client saving flag/idempotency key alone is not
proof that the displayed choices are durable.

One `BEGIN IMMEDIATE` finalisation transaction reconciles timing, validates pins
and revision, computes included/excluded/unanswered outcomes, persists all
answer commits/result/denominator/immutable acknowledgement and eligible
evidence or outbox, seals the attempt and releases restriction. Evidence failure
rolls the whole operation back. Submit/reopen/expiry races return the durable
winner; late saves cannot overwrite it. No Test draft correctness or Memory
capture exists before that transaction.

Consumer risk: [StudyService.progress/propose](../../runtime/renulus/study/service.py),
lines 83–106/142–183, counts all `assessment-answer` evidence as reviewed without
checking origin. [MemoryRepository.material/scan](../../runtime/renulus/memory/repository.py),
lines 219–233/271–295, additionally requires reviewed scope/mode. Personal C
results must not reuse that legacy evidence shape. Freeze a typed personal
evidence route and negative cohort/Memory tests. Preserve existing reviewed
answer+evidence atomicity.

**Minimal migration-004 recommendation requested by parent:** the reported
current `TABLE_COLUMNS` pins a version snapshot and timing/status but does not
yet persist Study commitments or terminal results. Add the following fields to
`assessment_test_attempts`; no separate result table is required for bounded
attempts. This is a proposal for the migration owner, not DDL in this branch.

| Field | Exact storage semantics |
| --- | --- |
| `committed_json TEXT NOT NULL DEFAULT '[]'` | Validated append-only item commitments, independent of `assessment_attempt_drafts`. Entry: `commit_id`, `item_id`, `selected_option_ids`, `committed_at`, `assisted`, `repeat`, `score_bucket`, frozen `outcome`, frozen `feedback` including the revealed key/explanation, and `evidence_id`/`evidence_kind` when eligible. Item/key/family pins resolve against the retained immutable manifest. Never rewrite a committed entry. |
| `result_json TEXT NULL` | Validated immutable terminal result/acknowledgement: per-item outcomes and pinned identities, included/excluded/unanswered counts, score numerator/denominator, finalisation reason/time and final draft revision. Remains NULL while active/paused. Study Finish summarises committed work without submitting its pending draft. |
| `clock_high_water_at TEXT NOT NULL` | UTC timestamp initialised when the attempt starts, updated transactionally to a nondecreasing effective backend time. Keep existing `paused_seconds`; if absent, add nullable `paused_at TEXT` for a durable timed-Study pause. Test never pauses. |

Study answer commit appends once to `committed_json`, locks that item, writes
eligible evidence and returns the stored feedback in the same transaction;
reopen reads it while pending draft stays editable. Test keeps commitments empty
and result NULL until finalisation transactionally validates/saves the latest
draft, writes all outcomes/evidence, stores result and terminal state, and releases
policy. Retry returns that stored result after the current disclosure check.
Validate JSON shape/item uniqueness/manifest membership, outcome counts and
terminal/result consistency during write and restore; a column allowlist alone
does not establish those invariants. Parent must include these exact columns and
typed evidence relationships in its export/restore inventory. Clock high-water
prevents extension below observed time; it cannot reconstruct elapsed time
during an unobserved offline clock rollback.

### A6 — P1: timers and invalid content must reach a terminal outcome

Existing assessment has no duration/deadline/durable draft acceptance timestamps
or expiry finaliser; pause applies to both legacy families. **R13** retains active
status/exposure/graded history after backend restart, not new draft/timer state.
**R08** blocks changed-content answering; calling it inside finalisation would
strand a C Test restriction.

Freeze before DC15:

- Start timing only when a Ready pinned version's attempt starts. At
  `now >= deadline` expiry wins over new saves; generation never consumes time.
- Define the save linearisation point. Expiry uses backend-durable drafts
  accepted before deadline, including lost acknowledgements, not client clocks
  or arbitrary HTTP-arrival timestamps.
- Every attempt read/write and active-policy lookup reconciles expiry, including
  reopen. Manual submit/expiry/concurrent reads share one finaliser.
- Timed Test has no Pause and does not extend on navigation/sleep/closure.
  Timed Study paused duration is separate; expiry preserves committed progress
  and pending draft without submitting it; Continue untimed is explicit.
- State a deterministic clock-change rule. Wall-clock-only permits extra time
  on rollback; monotonic-only cannot recover closed-app elapsed time. Use
  process-monotonic elapsed plus durable observations/deadline, with a declared
  conservative recovery rule for rollback/ambiguous restart. Do not claim
  trusted elapsed time where it cannot be reconstructed.
- Pinned corrected/withdrawn/unavailable items still finalise with explicit
  exclusions, separate unanswered counts and no rewrite of old scores. Decide
  whether source Needs review alone is exclusion or warning; legacy source
  currency currently does not alter scoring.

### A7 — P1: generation must publish a saved version, not start an attempt

Reuse the selected Provider consumer, validation and bounded small-batch work.
GenerateRequest defaults to three with a 1–5 limit. Runs/checkpoints are volatile
dictionaries. `publish()` creates an active quiz and presents its first item.
Validation checks count/shape/source indices, not question duplicates.

**R10:** direct publication of two original token items returns active session,
presented question and one persisted presentation flag. **R11:** actual streaming
consumer with a synthetic Provider accepts two identical items and completes
after one synthetic Provider call. No live verification. Source inspection also
shows `cancel()` acknowledges cancelled even for completed/unknown runs; no
cancel/publication race was executed in this review.

DC16 must publish one Ready immutable version without an attempt/exposure/timer;
checkpoint validated batches; detect duplicates across batches; retain actual
count/selected route/input revisions; require explicit resume for additional
model work. A recovered short set remains Needs review until its displayed count
is explicitly accepted. Publication rechecks deletion/revision/permissions and
cancellation atomically. Publication-winning cancel returns published, not undo.
Keep raw keyed model output private. No automatic billed/model retries/fallback
on restart/quota/auth failure. DC18 card and collection use the same saved pin;
metadata-only setup reveals no keys, and actual question preview records exposure.

### A8 — P1: import and temporary fictionalisation need distinct candidate types

The bank [QUESTION schema](../../runtime/renulus/content/schema.py) requires a
key, review metadata and CC-BY-4.0; GeneratedQuestion also requires a valid key.
Neither can represent private import candidates with ambiguous/missing keys.
Import cannot fill missing answers or promote quality just to validate JSON.

DC17 consumes DC08's actual extraction result/capability, original/revision/
locators and operation permissions. Candidate edits/unresolved keys survive
separately from Ready versions; refinement shows changes; explicit resolution
precedes save. OCR success does not establish a key. Preserve literal table
values, uncertainty and original terms/locations; do not install a public pack.

Existing saved-case practice handoffs remain volatile. DC18 must not merely
relabel them generated-practice. Only the spec's validated fictional artifact
crosses into a durable job; raw prompt, temporary IDs, attachment/locator edges,
transcript/hash/log/provenance that reconstructs input stay volatile. A boolean
or successful model response does not prove fictionalisation. Cancel/restart
before crossing retains nothing; afterwards recovery owns only the artifact.
Inspect sentinels in every durable job/checkpoint/provenance/log/question path.

### A9 — P1: nightly day uniqueness cannot include mutable settings

efcc7824 says daily keys include local day/timezone/scope/settings. Those fields
are useful input dependencies but unsuitable as the sole once-per-day claim key:
a settings/timezone/scope change can create a different key for the same day.
Example: October 10 run publishes, user changes count from 5 to 10, and a second
October 10 trigger has a new settings revision. Both keys can publish unless a
separate durable day claim prevents it. This is a contract counterexample, not
a executed C scheduler test.

Freeze a stable eligible-day claim separately from mutable settings/input
revisions; settings changes invalidate pending work, not create an extra claimed
day. Declare timezone/date/DST semantics, one latest missed-night catch-up, no
backlog and at-most-one publication across triggers/restart. Disable/cancel
invalidates publication even after a response arrives. At publication recheck
eligible saved-learning/Memory/project revisions, restore and deletion markers.
Never consume raw temporary data or bank keys, or distribute private originals.
Reuse bounded scheduler patterns without copying Updates' literal source-check
retry behavior. Exact eligibility is a DC02/M5/M6 contract, not prompt wording.

### A10 — P2: freshness chronology needs a stable definition

`_repeat()` queries other same-family exposure at read/commit time.
**R01/R05:** first presentation says repeat=false, second same-family session
says repeat=true, then first answer is also classified repeat. The spec does not
yet choose this concurrent chronology explicitly.

Freeze freshness at first presentation with separate subsequent assistance/
re-exposure facts, or document a different deliberate rule. Do not recompute old
cohorts from today's ledger. Retake/version correction cannot change family ID to
recover fresh status. Personal/generated stable identities need their own repeat
contract; current generated items lack the reviewed family ledger.

## Exact baseline operation inventory for policy integration

All paths below are prefixed **/api/v1**. Every content-bearing response,
including mutation acknowledgements, command replays and asynchronous completion,
must consult policy. Test applies across the profile; Study assistance is
recorded for the current uncommitted item before content returns. Existing
rights/retention remain additional conditions. Neutral projections/cancellation/
recovery controls can remain available; blanket response bodies cannot.

| Surface | Exact HTTP operations and actual methods | Gate requirement |
| --- | --- | --- |
| Reviewed sessions | POST `/assessment/start`; GET `/assessment/sessions` and `/assessment/sessions/{session_id}`; POST session `/answer`, `/help`, `/pause`, `/resume`, `/end`; GET session `/review` including `item_id`/`mistakes_only` parameters. `start/sessions/session/answer/help/transition/review/_view/_feedback/_replay`. | Block legacy start/scoring/help/keys during unfinished Test, including other sessions/retries. Dedicated neutral metadata/resume adapter only. Legacy end/pause cannot bypass C finalisation. |
| Generated sessions | GET `/assessment/practice/sessions` and `/assessment/practice/sessions/{session_id}`; POST session `/answer`, `/help`, `/pause`, `/resume`, `/end`; GET session `/review`; POST `/assessment/practice/generate` and `/assessment/practice/runs/{run_id}/cancel`. `prepare/publish/mutate/view/feedback/sessions/session/answer/help/transition/review/cancel`. | Same cross-profile gate for volatile/durable replies and generation SSE/replay. Cancel remains neutral/truthful. New producer publishes saved version through one adapter. |
| Scores/plans | GET `/assessment/aggregates`, `/assessment/progress`, `/assessment/mistakes`; GET `/study/home`, `/study/progress`, `/study/plan`; POST `/study/plan/propose`; PATCH `/study/plan/{activity_id}`. `_scores/aggregates/progress_summary/mistakes` and Study `evidence/home/progress/plan/propose/change_activity`. | No Test draft score/evidence. Gate correctness/item-pin/plan reasons and Home's chat/update content. Mutation replies cannot leak the same data. Goal/recovery settings require safe projection. |
| Memory/notes | GET `/memory/facts`, `/memory/facts/{identifier}`, `/memory/facts/{identifier}/history`; POST `/memory/search`, `/memory/facts`, `/memory/captures`; PATCH/DELETE `/memory/facts/{identifier}`; DELETE fact `/history`; GET `/memory/jobs`; POST `/memory/retry`, `/memory/reindex`. Repository `list/get/history/material/enqueue/scan`; service `retrieve/add/edit/delete/purge_history/process_pending/reindex`. | Fact/history/search and add/edit responses are help. Gate background recall/publication; no draft capture. Deletion/status/job cancel can return neutral control. GET `/memory/status` and POST `/memory/jobs/{identifier}/cancel` stay usable when neutral. |
| Content/keys | GET `/content/topics`, `/content/tracks`, `/content/questions`, `/content/cases`, `/content/cases/{case_id}`, `/content/sources`, `/content/sources/{source_id}`, `/content/sources/{source_id}/references` including `include_historical=true`; POST `/content/packs/install` and `/content/questions/{question_id}/versions/{version}/withdraw`. `list_topics/track_metadata/list_question_summaries/list_cases/get_case/list_sources/get_source/references_for_source/install_pack/withdraw_question`. | Gate teaching/source/reference/withdrawal prose, not just literal keys. Allowlisted collection metadata only. Internal `get_question_version/list_questions/teaching_material` remain trusted producers; no new public detail bypass. |
| Library/readers/search/notes | GET `/library/documents?query=...`, `/library/documents/{document_id}`, document `/import-status`, `/library/source-versions`, `/library/revisions/{revision_id}/citation` with `page`/`passage_id` parameters, revision `/original`; POST `/library/retrieve`, `/library/import/text`, `/library/import/file`; GET `/library/jobs/{job_id}` and job `/events`; GET `/library/collection/preview`, `/library/collection/catalogue`; POST `/library/collection/catalogue`, `/library/collection/import`, `/library/collection/import-next`. Knowledge `list_documents/get_document/retrieve/citation/original/_result/get_job/import_text/_import`, worker `import_interactive/import_selected`, catalogue `preview/register/list/import_selected/import_next`, source status `version_targets`. | Before bytes, snippets, note text or locators. Study mediation and Test denial include originals even where reserved-vector filtering is correct. Notes use `/library/import/text` with `document_id`; import/revision replies and async events require projections. Citation without passage ID has different eligibility from passage retrieval; both must use policy. |
| Learn/chat | GET `/learn/threads`, `/learn/threads/{thread_id}`; POST `/learn/threads` and `/learn/ask` with completed Idempotency-Key replay. `list_threads/get_thread/create_thread/prepare/answer` plus saved assistant/citations and every SSE event. | Gate historical transcript/title-preview/search, preparation, streams and stored replay. Cancel at Test start and reject late results. POST `/learn/runs/{run_id}/cancel` remains neutral. |
| Case content | GET `/cases/teaching`, `/cases/saved`, `/cases/sessions/{case_id}`, session `/attachments/{attachment_id}/original`, `/cases/attachments/{preview_id}`, `/cases/runs/{run_id}`; POST `/cases/sessions`; PATCH `/cases/sessions/{case_id}`; POST session `/reveal`, `/handoff`, `/discuss`, `/save`, `/close`, `/attachments`, `/attachments/prepare`, `/attachments/extract`; POST preview `/apply`, `/keep`, `/discuss-image`. Repository `start/get/list_saved/list_teaching/edit/reveal/handoff/begin_discussion/save/close/original/run_status` and preview `view/apply/keep/discuss_image`. | Saved or temporary content, teaching/reveals/extracts/originals and model replies are assistance. Save/close/mutation bodies can echo it. Prevent Case→Explain/practice handoff bypass. Cancel/delete may return neutral results. |
| Updates/source details | GET `/updates/sources`, `/updates/entries`, `/updates/entries/{entry_id}`, `/updates/publications`, `/updates/sources/{source_id}/publications`, `/updates/sources/{source_id}/status`, `/updates/entries/{entry_id}/affected`, `/updates/affected/{kind}/{entity_id}/versions/{version}`, `/updates/literature/checks`; POST entry `/review`, `/read`, `/sync`, `/refresh`; POST `/updates/publications`, `/updates/publications/{publication_id}/check`, `/updates/sources/{source_id}/check`, `/updates/literature/check`, `/updates/schedule/check`; PUT `/updates/schedule`. Service `list_sources/entries_page/get_entry/review/mark_read/refresh_entry/check_source/check_literature`; publications `list/candidates/track/check`; reviews `statuses/sync_entry`; affected `for_entry/needs_re_review`; literature `checks`; scheduling `status/configure/begin/manual`. | Source links, summaries, affected-version locators and returned check/review results need gate. Neutral schedule/status/cancel can remain. Audit async notifications and cached source inspectors. No network check was executed here. |
| Retrieval assistance | POST `/retrieval/discover`, `/retrieval/articles/import`. `RetrievalService.discover/import_article`. | Gate retrieved/source content and imported-result projection regardless of caller study scope. Connection/status configuration may remain neutral. |
| Export/restore | GET `/data/export`; GET `/data/backup` and POST `/data/backup/preview`, each with `format_version=1` or `2`; POST `/data/restore`, `/data/backup/restore`. `export_records/snapshot_in` and `Recovery.mutation/backup/restore_json/complete_preview/restore_preview`. | Finalise unfinished Test before plaintext/download/restore activation. Native save and browser download both require backend gate; DataManagement button hiding is insufficient. Any permitted preview exposes bounded neutral metadata only. GET `/data/recovery`, preview discard and safe connection/recovery controls remain available. |

Complete the inventory with these metadata and control operations. Their names
do not grant an exemption: existing bodies must be inspected/projected, especially
cancel/delete replies that echo a document, case, job input or stored result.
No control may clear the active-Test restriction except its authorised finaliser.

| Surface | Exact remaining baseline operations and callees | Permitted boundary |
| --- | --- | --- |
| Setup metadata | GET `/assessment/catalog`, `/assessment/practice/capabilities`, `/content/manifest`, `/content/bootstrap`, `/cases/capabilities`, `/library/capabilities`, `/library/queue`; GET/PUT `/study/goals`; GET `/updates/schedule`. `catalog/capabilities/active_manifest`, bootstrap registry, worker `status`, Study `goals/save_goals`, scheduling `status`. | Explicit bounded setup/status projection only; no arbitrary manifest, free-text goal, source locator, model detail or worker-result return during Test. |
| Cancel/delete/recovery | POST `/library/jobs/{job_id}/cancel`, `/library/cleanup`, `/cases/runs/{run_id}/cancel`, `/updates/schedule/cancel`, `/data/rebuild`; DELETE `/library/documents/{document_id}`, `/learn/threads/{thread_id}`, `/cases/sessions/{case_id}`, `/cases/sessions/{case_id}/attachments/{attachment_id}`, `/cases/handoffs/{ticket_id}`, `/cases/attachments/{preview_id}`, `/updates/publications/{publication_id}`, `/data/backup/preview/{preview_token}`. Knowledge `cancel_job/cleanup/delete_document`; Learn `delete_thread`; Cases `cancel/delete/remove_attachment/cancel_handoff`, previews `cancel`; Updates `stop`, scheduling `cancel`; Recovery `request_rebuild/discard_preview`. | Neutral outcome/status and required deletion controls remain usable. Gate any echoed content before return and derived-index material before publication. Attachment removal returns a Case view, so verb-only cancellation/deletion allowlists are insufficient. |
| Retrieval configuration | GET `/retrieval/connections`; PUT/DELETE `/retrieval/connections/{provider}`; POST `/retrieval/connections/select`. `status/configure/select/disconnect` through retrieval service. | Existing safe connection settings and recovery remain usable; never expose a content reply through an allowed configuration action. These operations were read, not executed. |

API source map for the complete inventory: [assessment](../../runtime/renulus/assessment/api.py),
[content](../../runtime/renulus/content/api.py), [Memory](../../runtime/renulus/memory/api.py),
[Study](../../runtime/renulus/study/api.py), [Learn](../../runtime/renulus/learn/api.py),
[Cases](../../runtime/renulus/cases/api.py), [Library](../../runtime/renulus/knowledge/api.py),
[Updates](../../runtime/renulus/updates/api.py), [retrieval](../../runtime/renulus/retrieval/api.py)
and [data/recovery](../../runtime/renulus/storage/api.py). Session action shorthand
above expands under the stated `/.../sessions/{session_id}` prefix; document,
revision, entry, job and preview actions use their stated identity prefix.

Backend-only gating does not clear already-rendered content. Parent also owns
workspace open/restore/focus adapters, keyboard/deep-link legacy routes, tab
restoration, source inspector, search snippet/card caches, Memory context hooks
and late stream application. New `/conversations`, substantive global/project
search, notes, saved-test preview/edit/results and `/assessment/test-attempts`
routes from efcc7824 join this inventory before assembly. Test preview/editor
must never reveal a pinned bank key before final commit. Current global finder is
destination-only, so no implemented substantive global-search result is claimed.
Normal raw disk access is outside the educational assessment boundary; this is
not a tamper-proof examination design.

## Exact future reservations — proposed for parent adoption

These names implement the parent's latest split, not the reviewer's authority to
write source. Parent must register them with the shared contract before dispatch;
the existing `assessment/api.py` and `repository.py` have one adapter writer.

| Lane | Exact new source/UI/test paths proposed |
| --- | --- |
| Attempt DC13→DC14→DC15, prospective next lane | `runtime/renulus/assessment/attempt_repository.py`, `runtime/renulus/assessment/attempt_api.py`; `apps/desktop/src/modules/attempts/StudyAttempt.tsx`, `TestAttempt.tsx`, `AttemptResults.tsx`, `useAttempt.ts`, `types.ts`, `attempts.css`, `StudyAttempt.test.tsx`, `TestAttempt.test.tsx` in that attempts directory. Parent sets any additional backend/test paths in the explicit lease; no wildcard authority is assumed. |
| Collection/version/report DC12, separate owner | `runtime/renulus/assessment/test_contracts.py`, `test_repository.py`, `test_api.py`, `question_report_repository.py`; `apps/desktop/src/modules/assessment/collection/TestsCollection.tsx`, `TestSetup.tsx`, `types.ts`, `collection.css` in that directory; `tests/assessment/test_dc_saved_tests.py`, `test_dc_question_reports.py`. |
| Generation DC16/DC18 producer/DC19, separate owner | `runtime/renulus/assessment/generation_contracts.py`, `generation_repository.py`, `generation_service.py`, `generation_api.py`, `nightly_service.py`, `fictional_artifact.py`; `apps/desktop/src/modules/assessment/generation/GenerationSetup.tsx`, `GenerationStatus.tsx`, `NightlySettings.tsx`, `types.ts` in that directory; `tests/assessment/test_dc_generation_jobs.py`, `test_dc_fictional_artifact.py`, `test_dc_nightly_tests.py`. |
| Import DC17, separate owner | `runtime/renulus/assessment/import_contracts.py`, `import_repository.py`, `import_service.py`, `import_api.py`, `import_candidates.py`; `apps/desktop/src/modules/assessment/import/ImportTest.tsx`, `CandidateReview.tsx`, `types.ts`, `CandidateReview.test.tsx` in that directory; `tests/assessment/test_dc_test_imports.py`, `test_dc_import_refinement.py`. |

Each explicitly listed sibling inherits the directory stated in its row; these
are exact names, not wildcard reservations. Check existing live reservations
before adopting them. Future assessment numbering in efcc7824 (`assessment-003`
saved tests, `assessment-004` attempts) remains parent-owned sequencing, not lane
permission to independently write migrations.

Single adapter writer also retains existing `assessment/contracts.py`,
`content.py`, `currency.py`, `generated_repository.py`, `generated_contracts.py`,
`generated_streaming.py`, `schema.sql` and existing migrations; renderer
`assessment/index.tsx`, `GeneratedPractice.tsx`, `types.ts`,
`SourceCurrencyNotice.tsx` and `assessment.css`. Request a narrow integration
patch rather than edit these concurrently.

Parent owns shared contracts/fixtures, schema-2 migration/ledger/DDL adoption,
typed restore/backup conversions, server/services, shell/platform/shared UI,
manifests/locks and cross-module policy tests. M2 owns extraction/originals;
M1 chat-card consumers; M5/M6 eligible personalisation. Lanes propose records and
consume producer contracts; they do not alter those owners' implementations.

## Prerequisites and remaining connected proof

Starting review prerequisite: `1b30a896` containing `528025ff`. Later `efcc7824`
and the `388687c2` unavailable-pointer update were read from Git without changing
this branch. Neither substitutes for the next lane's explicit baseline/lease.
Before coding, parent publishes the accepted reservation and amended
pin/unavailable-history semantics, cohort/assistance/policy revision,
draft-final/timing and stable nightly day claim. Then merge coordinated schema-2
foundation and owning regression-fixture fixes. No current parent passing
recovery receipt or DC01/DC02 completion is inferred here.

| Ticket | Real connected proof still required |
| --- | --- |
| DC12 | Immutable edits/cards/reports/Retake; exact count; legacy populated adaptation without regrading; idempotent saved publication; delete/export/restore preserves attempts/reports/job outcomes and unavailable provenance. |
| DC13 | Draft/reopen; empty refusal; commit locks answer once with evidence; source/note/chat assistance before return/failure/restart; presentation without answering; exact Next/late-result handling and repeat cohorts. |
| DC14 | Profile Test restriction across navigation/restart/all inventory routes/old command keys; cached help invalidated; delayed save N after N+1; manual latest state; lost ACK; two finalisations; evidence failure rollback; neutral report; blanks/exclusions; no partial score. |
| DC15 | Untimed and validated timed setup; before/at/after deadline; late save/lost ACK; sleep/closure/restart; expiry/submit/reopen races; forward/backward clock; timed Study pause/Continue untimed never submits draft. |
| DC16 | Exact 5/10/20, duplicate/malformed/short rejection, checkpoint recovery without automatic model work, explicit short acceptance, dependency deletion/revision and cancellation/publication durable winner. |
| DC17 | Every declared successful extraction plus preview-only/failed state; missing/ambiguous key review; originals/locators/terms; visible refinement; bounded retry/cancel; synthetic private original delete/export/restore. |
| DC18 | One action/job/version/card/collection pin; shared setup/attempt engine; edit/tombstone states; sentinel inspection before/after fictionalisation; cancel/restart without raw durable derivatives. |
| DC19 | Off default; one day/catch-up across concurrent triggers; settings/timezone change does not duplicate; DST/restart/disable mid-response; auth/quota stop; stale Memory/context rejection; no temporary/bank-key/private-original redistribution. |

Parent integrated policy tests must cover in-flight Study help when Test starts,
source/withdrawal prose, historical review/generated answer replays, wrong-answer
plan hints, Memory fact/history/search, reader citation/original, stored chat/
replay, substantive search snippets, native/browser export and restore activation.
Provenance tests must include deletion of a collection with pinned independent
history, missing live versions, reports and published job outcomes.

This pass supplied source/API evidence only. Parent later performs hidden
app-controller journeys against assembled C; screenshots, packaged runtime,
physical dialogs, live model integration and clinical/educational acceptance
remain separate. No feature ticket was marked done. This report-only review
handoff is complete once its explicit staged path and commit are returned.
