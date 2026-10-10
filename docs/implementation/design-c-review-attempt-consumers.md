# Design C attempt consumers — independent backend/data review, pass 2

October 10, 2026. Assigned integration baseline
**84be584e90d54192305495eec58dc6c929b4e5ed**, normally merged into
`codex/dc-review-assessment` as **940841d49b081da2831ada0d4b69f6b28f8a5164**.
`git diff 84be584e HEAD -- runtime apps tests packages` was empty before this
report: the reviewed production/test sources match the assigned baseline.
Worktree/root: `C:/Renulus/dev/worktrees/dc-review-assessment`. The sole edit
reservation for this pass is this report. No attempt, consumer, shared code,
test, spec, schema, manifest or ticket status was edited; no push was performed.

**Disposition:** preserve the passing scalar/policy/history boundaries, repair
the report provenance projection, connect Home's Memory adapter to the new
canonical producer, and settle automatic recovery of interrupted capture. This
pass does not close DC06 or DC12–DC20. Findings were sent to the parent as the
actual producer probes completed; Home findings were also sent to its owner.

## Scope and evidence

Read the workspace/product/design rules and the current C spec/execution/app
control records; inspected the integrated Home, Memory, import, fictionalisation,
saved-generation, saved-test/report, Study-help/publication and typed recovery
implementations. This is backend/data review. No renderer, hidden Electron,
installation, physical input, live provider or owner-profile acceptance is claimed.

All writable runtime/test state, scripts and receipts are under
`C:/Renulus/scratch/design-c/dc-review-assessment/pass2/`. The independent script
uses actual `create_app`, installed migrations, ProviderManager, HTTP routers and
canonical SQLite producers. Reviewed questions are original synthetic tokens
through the existing synthetic content fixture. Imports use actual paste parsing,
explicit resolution and Save. Fictional tests use the actual trusted transform,
independent review and private publisher, with only the external subscription
transport replaced by original synthetic responses. No provider credentials were
read or copied; the fixture's synthetic token is held in process.

Memory observations execute the actual `scan/enqueue/claim/material/commit_capture`
repository path, without starting its background worker, embedding engine or
derived index. Home's delayed-publication observation runs its actual
ProviderManager/job/cache producer. No fixture DDL or fabricated saved-version
publication outcomes are used by the independent script. Privileged SQL mutation
is confined to the explicit forged-evidence test in the owned synthetic profile.

Retained receipts:

- `probe.py`, `probe03.txt`, `probe-results.json`, `profile-probe03/`: ten final
  observations R21–R30; final process exit 0. The script refuses an existing
  profile name, making reproduction use a fresh profile.
- `probe01.txt`, `probe-partial-results.json`, `profile-probe01/`: the first run
  completed R21–R29, then failed at harness cleanup because the conversation
  property is `streaming`, not `streams`. This is a harness error, not a product
  failure. Only scratch code was corrected.
- `probe02.txt`, `profile-probe02/`: corrected R21–R29 run, exit 0. The final
  script adds fictional completion/deletion/restore observation R30.
- `regression01.txt`, `pytest01/`: **132 passed, 1 skipped, 1 warning in
  428.89 seconds**. The skip is the explicitly opt-in assembled Home
  loopback-renderer test requiring `RENULUS_HOME_CONNECTED=1`; it was not
  silently counted as acceptance. The warning is installed Starlette/httpx
  deprecation. Existing regression fixtures have their separately bounded scopes.

Regression command:

```text
python -m pytest tests/study/test_home_suggestions.py
  tests/memory/test_whole_attempt_evidence.py
  tests/assessment/test_saved_imports.py
  tests/integration/test_design_c_chat_tests.py
  tests/integration/test_design_c_study_help.py
  tests/integration/test_design_c_import_migration.py
  -q -p no:cacheprovider
  --basetemp C:/Renulus/scratch/design-c/dc-review-assessment/pass2/pytest01
```

Reproduce the independent script with
`C:/Renulus/dev/python/Scripts/python.exe <scratch>/probe.py <fresh-profile-name>`,
`PYTHONPATH=C:/Renulus/dev/worktrees/dc-review-assessment/runtime`,
`PYTHONDONTWRITEBYTECODE=1`, TMP/TEMP in the stated scratch root, and
`HF_HUB_OFFLINE=1`/`TRANSFORMERS_OFFLINE=1`. It makes no external requests.

## Material findings and remediation

### C1 — P1: independent reports discard the producer provenance envelope

The report writer receives the attempt's full frozen producer envelope, but
`save_question_report` projects it to only `schema` and one `items` entry.
Question text/options/key, terms, origin, review quality and source references
remain pinned; this is specifically a loss of producer/source authority, not
loss of the report row or a public key disclosure.

**R24 reproduction:** actual paste import → explicitly resolve both keys →
Save → start whole Test → atomically submit the two latest answers → POST
`/api/v1/assessment/test-attempts/{id}/reports`. The response is correctly neutral
with exactly `id/status/created_at`. The attempt's private pinned envelope has
`schema/producer/import/items`, including the original SHA-256, import ID/revision,
source pin and private flag. The report's `question_snapshot_json.provenance` has
only `schema/item`; its retained character spans are no longer independently
bound to that original hash.

**R26 reproduction:** actual private Quick practice → trusted transform plus
separate independent review (two actual ProviderManager calls with synthetic
transport) → publish exactly five → whole Study answer commitment → local
report. The attempt's envelope retains `fictionalisation` with boundary version,
validation ID, artifact SHA, selected route and privacy-review method. The
report stores exactly `{schema: saved-test-provenance/1, item: null}` because
this producer has no `items` envelope. It loses the privacy-boundary receipt.

R25/R30 prove reports and attempts survive collection deletion and restore with
nullable live version pointers. Survival makes the truncated report an
independent historical row; resolving the missing metadata through the deleted
version is no longer possible. The attempt currently retains it, but that
separate record is not an appropriate hidden ownership prerequisite for the
report's own immutable provenance.

**Required repair, collection/report owner:** retain the validated frozen native
producer envelope in the private report snapshot, including origin-specific
import/fictionalisation/generation/reviewed-pack metadata and the relevant item.
Keep the public acknowledgement neutral. Do not add raw chat/case source, private
input text or a renderer attestation. Use the already trusted pinned envelope,
with a documented snapshot version/compatibility rule. Existing snapshots need
an explicit incomplete-provenance treatment; do not invent missing validation.
No DDL expansion is needed to store the repair in the existing snapshot JSON.

**Required proof:** actual imported and fictional report, then remove both live
version and any live attempt dependency and restore an older bundle. Report row,
question pin, original hash/source pin or fictional receipt, terms and origin
must survive unchanged; public replay remains neutral and policy guarded.

Source: [saved report writer](../../runtime/renulus/assessment/test_repository.py),
lines 392–427, especially 416–417; [import publication](../../runtime/renulus/assessment/import_service.py),
lines 515–524; [fictional publication](../../runtime/renulus/assessment/generation_service.py),
lines 64–85. C spec DC12 requires delete/restore to preserve required provenance
or explicit unavailable references; DC13 requires reports to survive restart
unchanged. Section 10 explicitly gives independently pinned provenance to
attempts/reports/job outcomes.

### C2 — P2: Home accepts whole-attempt activity but drops its canonical Memory fact

The new activity branch correctly uses `committed_evidence_in`. The separate
Memory branch still requires a legacy `payload.scope` and restricts sources to
`study-interest/study-answer/assessment-answer/learning-point`. New
`assessment-test-answer` deliberately has no legacy scope object and is absent
from that allowlist.

**R21 reproduction:** actual saved reviewed version → whole Study start →
explicit Submit answer → actual Memory enqueue/claim/material/capture. Canonical
Memory has one fact, in `reviewed-assessment`, and capture ignores a supplied
forged text sentinel. `HomeService._context(conn)` returns learning activity 1,
Memory 0, and no `memory_revision` pin. Home still receives the scalar activity;
this is an omitted consumer path, not complete loss of the initial answer signal.

**R22 reproduction:** edit that actual canonical fact to a personal corrected
learning interest through `MemoryRepository.edit`. Revision 2 remains inspectable
as the sole canonical fact. Suppression correctly excludes regeneration/direct
old evidence, but Home now returns both activity 0 and Memory 0. The retained
correction is not passed to personalisation. Independently edited facts need an
explicit eligibility decision rather than inheriting permanent exclusion from
their superseded producer.

**Required repair, Home owner:** resolve the new source through the trusted
scalar helper inside `_context` and publication transactions; validate the exact
captured scope/cohort and pin both source digest and canonical Memory revision.
Never read raw commitments or private attempt snapshots. Define how an explicit
canonical correction establishes independent fact authority while keeping the
old source suppressed; preserve scope/retention exclusions. Memory deletion
must still remove both the fact and applicable activity. Do not simply add the
new string to the legacy allowlist or accept a fabricated legacy scope field.

**Required proof:** actual reviewed and personal whole commitments → automatic
Memory capture → Home prompt/pins; correct the fact, then delete it; change
source availability, suppression, policy and epoch during generation. Updated
eligible correction should be used without resurrecting old text; stale output
must not publish. Retain assisted/repeat independently and personal practice as
unreviewed key comparison.

Source: [Home context](../../runtime/renulus/study/home_service.py), lines 160–181
and 185–226, especially 205–208; [canonical capture](../../runtime/renulus/memory/repository.py),
lines 176–216 and 382–401; [Memory correction](../../runtime/renulus/memory/repository.py),
lines 129–146. C spec DC06 uses eligible usage/Memory and DC10 preserves
inspection/edit/delete/provenance; the completion matrix requires Memory edits
and deletion to affect later personalisation.

### C3 — P2: safe boundary cancellation becomes permanent automatic-capture loss

**R27 reproduction:** obtain actual fictional whole-Study evidence; enqueue and
claim a Memory job; start and finalise another whole Test; attempt late capture.
The old job is correctly rejected during Test and remains stale after Test ends
because its policy fingerprint changed. `commit_capture` writes no fact and
marks the old job cancelled. Calling `scan()` leaves only that cancelled job.
Explicitly enqueueing the same still-eligible evidence succeeds with a distinct
fingerprint and state `queued`.

The scanner excludes any evidence having any historical job, regardless of
state/fingerprint. `retry()` only changes failed jobs; the worker's normal scan
therefore cannot recover this valid commitment after a temporary boundary.
Restore similarly records `restore_interrupted` cancellation. This finding is
loss of automatic recovery, not a reason to weaken the publication guard.

**Bounded repair proposal, Memory/shared worker owners:** distinguish explicit
user cancellation and suppression from policy/restore interruption. Permit a
fresh job only for eligible boundary-interrupted evidence with a new canonical
fingerprint, while deduplicating queued/running/completed captures. Do not loop
on permanently missing/forged/deleted sources, or undo a user cancellation.
Current state/error columns can carry the distinction; establish semantics
before changing the worker's cancellation path.

**Required proof:** active Test never captures; one fresh capture occurs after
finalisation/recovery; repeated scans deduplicate; explicit cancellation,
correction/suppression and deletion never auto-requeue. No inference is needed
for these structured scalar commitments.

Source: [scanner](../../runtime/renulus/memory/repository.py), lines 320–330;
[capture cancellation/retry](../../runtime/renulus/memory/repository.py), lines
382–419; [worker cancellation](../../runtime/renulus/memory/service.py), lines
199–239; [restore interruption](../../runtime/renulus/storage/invalidation.py),
lines 35–56. No worker or shared-policy changes are included here.

## Passing observations and limits

| Probe | Actual result at this baseline |
| --- | --- |
| R23 imported whole Test | Start omits keys/commitments/results. Home, Memory facts, private import, saved collection and a different Study attempt all return 409 during active Test. Final submission commits the latest two choices atomically: personal correct 2/denominator 2; fresh reviewed denominator 0; scalar evidence `reviewed=false`, `bank_cohort_eligible=false`. |
| R25 imported deletion/recovery | Delete collection and private import, then actual restore of older records: neither deleted root returns; attempt and report remain; result digest unchanged; report live version null; attempt marks unavailable provenance; trusted scalar evidence is ineligible. |
| R26 fictional boundary | Actual transform and independent review publish exact five; source text and source request ID are absent from exported records, and source text is absent from profile files. Saved/attempt origin is generated, quality personal. The report provenance defect is C1. |
| R28 forgery | Mutating the evidence payload to claim reviewed/fresh eligibility and include a private key is rejected by the attempt authority and Memory currentness; the sentinel never enters Home material. |
| R29 epoch | Hold an actual Home ProviderManager response, bump context epoch, then release: job fails `dependency_changed`, with no published suggestion cache. |
| R30 fictional result/recovery | End Study after one of five explicit answers, delete the actual saved collection, restore older records: result hash unchanged; personal correct 1/denominator 1; four remain not submitted; attempt retains the fictional privacy envelope and marks unavailable provenance; report survives with null live version. |

The selected regression also covers drafts, unanswered/excluded commitments,
assisted/repeat flags, typed overlapping Learn tombstones, missing/deleted
sources, suppression, policy cycles, import retry/permission gates, both ZIP
formats, and current/stale/forged Study-help transaction/publication checks.
These passes do not repair C1–C3; the independent probes exercise combinations
not asserted by the existing tests.

Actual Library extraction/import with pinned helper assets, derived Memory
index/recall, all legacy bypass routes, hidden UI handoffs, timed app closure/
reopen and installed recovery were not independently rerun in this pass. Paste
import and private fictional saved versions were exercised through production
consumers. No new timer defect was reproduced, and no all-consumer, clinical,
live-provider or ticket-completion claim is made.

## Handoff

The parent owns integration, shared storage/publication/policy and acceptance.
Collection/report ownership should handle C1; Home owns C2; Memory/shared-worker
owners should agree the bounded C3 recovery semantics. Use small disjoint fixes
and preserve this baseline/receipts. Do not remove immutable history or loosen
the passing scalar/active-Test/epoch guards to make consumer tests green.

This report is the only changed path. Testcase scripts, profiles and receipts
remain in the owned scratch directory. Local report commit follows explicit
file staging; dependent implementation is not included.

## Follow-up at canonical 319ff190

Normally merged canonical `319ff190` as `dd2116dc` after the clean report
checkpoint `c17c4a8d`. `git diff 84be584e 319ff190 -- runtime tests packages`
is empty; the original backend findings remain applicable. The follow-up
checks use a new owned profile, actual production migrations/services/HTTP,
and actual `knowledge.import_text` extraction. Public local embedding assets
from `C:/Renulus/dev/helper-assets` were checked against the committed size
and SHA-256 inventory, then copied into the synthetic profile. External
connections were denied. No normalization or live provider was required.

Script and receipts:

- `C:/Renulus/scratch/design-c/dc-review-assessment/pass2/import-boundaries.py`
- `C:/Renulus/scratch/design-c/dc-review-assessment/pass2/import-boundaries01.txt`
- `C:/Renulus/scratch/design-c/dc-review-assessment/pass2/import-boundaries-results.json`
- Profile: `C:/Renulus/scratch/design-c/dc-review-assessment/pass2/profile-import-boundaries01`

### C4 — P1: Library import Save replay bypasses current display permission

**R31 reproduction:** import two synthetic MCQs through actual Library text
extraction (`status=ready`); create a Library-revision private import; explicitly
resolve each retained key; Save through HTTP. Revoke `display` in the canonical
source revision rights, then issue these actual assembled HTTP requests:

| Operation | Observed result |
| --- | --- |
| `GET /api/v1/assessment/imports/{id}` | 403 `saved_extraction_denied` |
| `GET /api/v1/assessment/imports/{id}/original` | 403 `saved_extraction_denied` |
| `POST /api/v1/assessment/imports/{id}/save`, same original body/idempotency key | 200; stored candidate text and resolved `correct_option_ids` returned |

The Save replay checks the published version but returns `_view(row)` before
checking current source display/cache rights. `_view` includes private question
and option text as well as resolved keys. Idempotency therefore provides an
alternate disclosure path after ordinary reads have correctly been denied.
This is a source-permission boundary failure; no active-Test bypass is alleged.

Source: [Save replay](../../runtime/renulus/assessment/import_service.py), lines
489–498; [source/display guard and private view](../../runtime/renulus/assessment/import_service.py),
lines 168–218.

**Bounded repair, import owner:** recheck the current source display permission
and original integrity before every replay returning `_view`, including cache
permission and deletion aliases already checked by the reader helper. If Save
replay is changed to a neutral acknowledgement, update its consumer contract
explicitly; a valid historical publication does not authorize current source
display. Preserve the immutable publication and historical command receipt.

**Required proof:** actual Library Save replay is denied after display/cache
revocation, source deletion or original loss; unchanged permitted sources retain
idempotent acknowledgement; active Test continues to deny disclosure before
replay. Test the actual HTTP path and reader helper, not a fabricated ready row.
Only display revocation was independently reproduced here; the remaining cases
are required verification for the proposed repair.

### R32 — assembled neutral import cancellation passes

Create an actual pasted draft, then start an actual whole Test from a reviewed
saved version. `POST /api/v1/assessment/imports/{draft_id}/cancel` returns 200
with exactly `{id, state}`, state `cancelled`; identical replay returns the same
body. Ordinary import read returns 409 while Test is active. The shared server
already exempts this neutral control, so the hypothesized HTTP cancellation
gap is not a finding. This check did not hold normalization inference in flight;
the existing production-service transport cancellation regression supplies
that separate evidence.

The initial report limits still apply except that this follow-up did exercise
actual Library text extraction and Library-backed import. C1/C2 repairs are now
assigned by the parent. C3 has a separate subsequent Memory source lease; no
source changes are part of this report checkpoint.

## Repair checkpoints and independent C1/C4 recheck at 51f208b4

The parent integrated C1 as `1b12c19f`, C4 as `a2a5f2d4`, and assigned C2
to Home (`a14e06a9`). C3 received a separate explicit Memory source lease
after the clean report checkpoint. The sole source fix checkpoint from this
lane is `e4a7b0ed38b27969a681a824c1f3cdde902ccc0c`, integrated by the parent
as `51f208b4`. Its four explicitly staged paths are:

- `runtime/renulus/memory/repository.py`
- `runtime/renulus/memory/service.py`
- `tests/memory/test_repository.py`
- `tests/memory/test_whole_attempt_evidence.py`

The source checkpoint adds no DDL, shared policy/storage, attempt, Home, spec
or renderer edits. It uses the existing `memory_jobs` state/error/hash fields.
New job fingerprints carry only canonical source SHA-256, policy revision and
context epoch: `memory/2:<source_sha256>:<policy_revision>:<context_epoch>`.
Boundary cancellation codes `boundary_policy_changed`,
`boundary_context_changed` and `restore_interrupted` permit one fresh fingerprint
after current owner/source/policy validation. Completed, failed, pending,
explicitly cancelled, suppressed, invalid and changed-source work block automatic
replacement; permanently invalid recovery records become terminal. Structured
whole-attempt capture continues to resolve safe scalars and performs no inference.

`cancel_stale(job)` retains the distinct cause; user Stop writes
`explicit_cancelled`, including when it wins after a restore interruption.
Suppression/correction/deletion remain authoritative. The `attempts` counter
of the captured execution is checked before commit or cancellation so old output
cannot affect a restarted execution. Shutdown leaves current interrupted work
recoverable; late outputs remain fenced.

Compatibility is conservative: an earlier whole-attempt SHA fingerprint is
accepted only if exact current source/policy/epoch reproduces it. Ambiguous
old NULL cancellations and crossed unversioned fingerprints remain terminal,
requiring explicit re-enqueue; no historical boundary is invented. A distinctly
recorded restore interruption can re-resolve into a fresh current fingerprint.

**C3 verification:** the final five-module Memory regression passed **76 tests**
in 221.91 seconds (`c3/full02.xml`), the restart repository check passed 14
(`c3/repository02.xml`), and earlier-fingerprint compatibility passed one
separately (`c3/compat01.xml`). These are overlapping runs, not 91 unique tests.
The focused actual producer/recovery checks passed 13 (`c3/green02.xml`),
including active Test, exactly one fresh capture, actual production restore,
queued worker interruption, explicit cancellation after restore, invalid/forged
source, source changes, suppression and deletion.

Preserve the red and harness-failure receipts in
`C:/Renulus/scratch/design-c/dc-review-assessment/c3/`: the original checks
reproduced five failures; an initial restore fixture used the lower-level
`restore_records` merge, which does not call context invalidation. That fixture
was corrected to actual `data_recovery.restore_json` before the green checks.
The final warnings concern installed Starlette/httpx deprecation and local
Qdrant payload indexes. No live provider acceptance is implied.

### Independent report-only recheck of C1 and C4

After the source checkpoint was clean, normally merged `6145fc70` as
`822c8c3e`, then `51f208b4` as
`062625970b794ff146cc1a5309d63483e3dcf470`. The main recheck began at
`822c8c3e`; its production runtime and relevant producer fixtures are byte
identical to `51f208b4`. `git diff 822c8c3e 51f208b4 -- runtime` is empty.
The later narrow source-deletion check ran after the `51f208b4` merge. No
source changes were made during these independent rechecks.

Actual real-producer observations, with external connections denied:

| Check | Result |
| --- | --- |
| R33 permitted/denied Save replay | The unchanged permitted replay equals its original response. Revoke display, then cache: import read, original read and identical Save replay all return 403 `saved_extraction_denied`, with no candidates. |
| R34 imported report | Actual Library extraction → explicit key resolution → Save → whole Test latest-draft submit → report. Private report provenance equals the complete pinned native producer envelope except other items; original SHA/source pin retained, origin imported/quality personal. Public acknowledgement contains exactly id/status/created_at. |
| R35 original loss | Remove only the actual owned synthetic original. Import read, original read and identical Save replay all return 404 `original_missing`, with no candidates. |
| R36 retention | Delete the actual saved collection, private import and Library source; invoke actual production `data_recovery.restore_json` on the older records. Result digest unchanged; unavailable provenance explicit. A new report from the retained attempt still preserves the same import envelope. Deleted-import Save replay remains 404. |
| R37 fictional report | Actual trusted transform and separate privacy review through ProviderManager with two synthetic transport calls, exact five saved, whole Study commitment and report. Complete fictionalisation/privacy envelope retained before and after collection deletion plus actual restore; immutable result digest unchanged; original private source absent from all profile files and export. Public acknowledgement remains id/status/created_at. |
| R38 source deletion independently | Reopen the owned synthetic profile; create another actual Library import and Save; delete only the Library document. The private import and published version still exist. Import read, original read and Save replay all return 404 `saved_extraction_not_found`, with no candidates. |

Scripts and exit-zero receipts remain outside the repository:

- `C:/Renulus/scratch/design-c/dc-review-assessment/pass2/recheck-fixed.py`
- `C:/Renulus/scratch/design-c/dc-review-assessment/pass2/recheck-fixed01.txt`
- `C:/Renulus/scratch/design-c/dc-review-assessment/pass2/recheck-fixed-results.json`
- `C:/Renulus/scratch/design-c/dc-review-assessment/pass2/recheck-source-delete.py`
- `C:/Renulus/scratch/design-c/dc-review-assessment/pass2/recheck-source-delete01.txt`
- `C:/Renulus/scratch/design-c/dc-review-assessment/pass2/recheck-source-delete-results.json`

Both checks use `profile-recheck-fixed01` under the same owned pass2 scratch
root, actual production SQLite/migrations/services/HTTP and SHA-validated
public offline embedding assets. The second check deliberately reopens that
verified synthetic profile; no owner state is read.

**Disposition:** the original C1/C4 failures no longer reproduce in the exercised
paths at `51f208b4`; no new material failure arose in this bounded recheck.
The connected canonical/worker C3 tests pass and its source is integrated. The
C2 repair is parent-reported and was not independently rechecked here. Existing
historical findings remain in this report; discarded pre-fix provenance is not
reconstructed. The parent owns combined Home/Memory/attempt/renderer acceptance
and ticket disposition. Hidden UI, installed/native acceptance, all legacy
routes and live subscriptions remain outside this checkpoint. No ticket is
marked complete. This final recheck changes only this reserved report path.

### C5 — Recovery can autonomously infer from restored ordinary learning

**Confirmed P1 at `51f208b4`.** The C3 fresh-fingerprint rule also covered
ordinary `study-answer` and `learning-point` material with `infer=True`. Moving
the provider call outside the restore transaction did not meet the spec's
_Recovery does not start provider work_ guarantee. `MemoryService.recovery_guard`
wakes the normal worker after recovery, and its ordinary two-second scan can
enqueue new inferred captures for restored evidence without another user action.
The old provider execution is not replayed; a fresh job still starts autonomous
provider work for historical restored learning.

Bounded reproductions used actual assembled services/migrations, a completed
ordinary Learn answer, production `data_recovery.restore_json`, normal Memory
worker, ProviderManager, Mem0 OSS, QdrantLocal and SHA-validated public offline
FastEmbed assets. Only the remote provider transport was synthetic, and external
connections were refused. The process scheduling lock held the actual worker
until restore completed; no inference was active when restore was admitted.

| Reproduction | Observed failure before the repair |
| --- | --- |
| R39 queued ordinary capture | Restore itself makes zero provider calls and cancels the old job with `restore_interrupted`. The normal worker then creates one fresh fingerprint/job, makes one synthetic transport inference call and commits one fact without explicit capture or retry. |
| R40 never-scanned ordinary source | No Memory job exists before or during restore. On normal worker resume, the restored source still creates one inferred job/call/fact without an explicit action. A guard restricted to historical interrupted jobs cannot prevent this case. |

The distinction is source identity and user action. New eligible learning
created after restore may be automatically captured on a later normal scan.
Structured scalar evidence can also be freshly resolved without inference.
Restored inferred sources need deliberate capture; simply waiting for the
normal scan does not make them new learning.

Original proof scripts and exit-zero receipts are retained outside Git:

- `C:/Renulus/scratch/design-c/dc-review-assessment/pass2/recheck-restore-inference.py`
- `C:/Renulus/scratch/design-c/dc-review-assessment/pass2/recheck-restore-inference01.txt`
- `C:/Renulus/scratch/design-c/dc-review-assessment/pass2/recheck-restore-inference-results.json`
- `C:/Renulus/scratch/design-c/dc-review-assessment/pass2/recheck-restore-unscanned.py`
- `C:/Renulus/scratch/design-c/dc-review-assessment/pass2/recheck-restore-unscanned01.txt`
- `C:/Renulus/scratch/design-c/dc-review-assessment/pass2/recheck-restore-unscanned-results.json`

**Authorised repair:** parent foundation `009b8780` adds the local preference
barrier `storage.invalidation.MEMORY_RESTORE_CAPTURE_PREFIX`, exactly
`memory.restore_capture:` plus canonical evidence ID. The restore transaction
bumps the local context epoch, marks every merged evidence ID with that epoch,
and emits no jobs. It includes destination, imported and never-scanned rows.
The existing export whitelist excludes these markers. No raw text, scope, new
schema or export change is required. The parent's three foundation checks cover
rollback, export exclusion and new post-restore IDs remaining unmarked.

Memory source checkpoint `d98915592c2f0a0b4d50bd7b8fcdbfb49aa60f28` changes
only `runtime/renulus/memory/repository.py`,
`tests/memory/test_service.py` and `tests/memory/test_whole_attempt_evidence.py`.
It imports the published constant and enforces:

- Automatic enqueue resolves current canonical material, policy and suppression,
  then refuses inferred material with a restore marker. It does not block
  structured `infer=False` captures or ordinary policy-only recovery.
- Existing global Retry can queue failed rows directly. The worker's canonical
  `_capture_error_in` therefore checks the same barrier before provider work
  and publication, returning `restore_interrupted` for marked inferred material.
  Global Retry never consumes the marker.
- Existing explicit `POST /api/v1/memory/captures` with `{evidence_id, scope}`
  validates current source, scope, policy and suppression. Successful enqueue
  consumes the marker in the same canonical transaction. Denial, insertion
  failure and replay of a still-cancelled/failed terminal receipt preserve it.
- Equal fingerprints from foreign profiles cannot revive an old execution.
  Explicit capture can requeue the same `cancelled/restore_interrupted` receipt;
  automatic enqueue cannot. Requeue preserves its attempts counter; the next
  claim increments it and refuses late foreign execution output. A forged stored
  receipt scope is refused. Completed same-fingerprint receipts remain unchanged.

**Verification at the clean source checkpoint:** `c5/green01.xml` passes 15
focused checks in 79.13 seconds, and `c5/http01.xml` adds two distinct HTTP checks
in 12.24 seconds. They prove queued, never-scanned and reopened Memory-service
restore barriers using the actual Learn producer and running Memory worker,
zero implicit inference before deliberate capture, real ProviderManager/Mem0/
FastEmbed/Qdrant extraction afterwards, automatic inference for new evidence,
policy-only inferred recovery, structured scalar recovery, equal foreign
fingerprints with execution fencing, global Retry refusal, atomic marker
rollback, completed receipts and cancellation/suppression retention. Actual HTTP
requests also refuse active-Test and wrong-scope capture, then deleted/forged
whole commitments, without consuming markers. Reopen here means a new actual
MemoryService over its retained SQLite profile; it is not an Electron/process
reopen claim.

`c5/red01.xml` preserves the initial three actual autonomous-inference failures
and equal foreign receipt failure. Its global Retry check initially observed
the context mismatch reason; the final fixture also exercises a foreign equal
epoch, the case that requires the additional worker guard. Three initial fixture
uniqueness failures are preserved and corrected by idempotent marker upserts;
they are harness errors, not additional product findings. Existing Starlette/
httpx and local-Qdrant warnings do not qualify provider or installed acceptance.

The affected five-module Memory regression passes **91 checks** in 185.79
seconds at `d9891559`: repository, service, Study-answer capture, API and whole
attempt evidence (`c5/regression01.xml`). Those checks include the earlier
focused tests; the counts are not additive. Follow-up test checkpoint
`a4898f2645a7974976d2fca7203b3349de6ad921` adds one distinct passing check
in 12.91 seconds (`c5/retry-http01.xml`). It creates an actual failed inferred
Learn capture through ProviderManager/Mem0 with a synthetic transport error,
restores a failed receipt with a foreign equal fingerprint, invokes actual
`POST /api/v1/memory/retry` and observes zero new inference calls or facts. The
marker remains. Actual `POST /api/v1/memory/captures` then requeues that same
row, consumes the marker and completes one fresh actual extraction/fact. No
production code changed for this additional proof. Final receipts and profiles
are under `C:/Renulus/scratch/design-c/dc-review-assessment/c5/`.

**Disposition:** C5 no longer reproduces in these bounded production paths
with foundation `009b8780` and Memory `d9891559`; the source is ready for
integration. `MemoryService` and the existing router require no API changes.
Parent renderer checkpoint `e5209f17` supplies deliberate capture for
an exact interrupted receipt through the existing endpoint; its 25 renderer
checks and typecheck are parent-reported. No-history restored evidence stays
quiet and receives no discovery job. This worker makes no renderer/shared
storage changes. Combined hidden app/installed acceptance and final feature
disposition remain with the parent; no ticket is closed here.
