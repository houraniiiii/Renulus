# Bounded correction-effect acceptance preparation — October 7

Prepared on `codex/finish-update-effects-20261007`, base
`1dde6d904dac436cafae331b5898fe45c410a6a6`. **No new application acceptance
was executed.** This report is the only tracked change. The external recipe,
source pins, recovered-proof metadata and binding template are under
`C:/rn-finish-20261007/evidence/update-effects-preparation/`.

The smallest missing actual-app slice is **one explicitly synthetic correction
review through Updates → acknowledged Library invalidation → current-only
retrieval exclusion → affected pinned question/retained feedback → normal
close/reopen without duplicate reviews or attempts**. This addresses the
remaining S5.04 effect in the [finish audit](finish-audit-20261007.md), with a
bounded S5.02/S5.05 eligibility observation. It does not close every S5 state.
No production fix is proposed: recovered application tests already establish
the underlying policy, and source inspection found the relevant implementation
unchanged. Parent owns the hidden retained-learning handoff, integration,
matching installation, and serial native/helper slot. This recipe does not
replace or launch that work.

## Recovered proof; do not repeat it

Read the workspace instructions, README, brief, workspace guide, APP_CONTROL,
current FINISH, [correction patch](finalise-update-correction-20261006.md),
[Updates acceptance](updates-acceptance-evidence.md),
[exact-copy binding](updates-acquired-version-binding-evidence.md),
[recovery/currency integration](integration-recovery-currency.md),
[recovery/freshness checkpoint](finalise-recovery-freshness-20261006.md), and
[older deferred recipe](finalise-freshness-correction-followon-20261006.md).
Read the actual external receipts named below; no profile/database, original,
credential, account or private record was opened.

| Receipt | Recovered result and exact scope |
| --- | --- |
| `C:/rn-finalise-20261005/parent-correction-fixture-20261006-02/result.json` | Source `699938f20efb6bbc2cf8df684cc5c6c3450e6eaf`, completed 2026-10-06 07:42:42 UTC; 11 selected/11 passed, exit 0, complete/source-unchanged/accepted-stage true, zero guard violations. Real SQLite/journal/assessment with controlled engines. Receipt SHA256 `b00ce05cd0a8bd54757e3fc4cbd358b2799188a192a8a6c5b8c1759c7d0a8cff`. |
| Same root, `results.xml` | Actual 11-case JUnit SHA256 `d789ca5f9d909af54e9750932cb53b5e22b6c8949f0c69192c9d7a8b2f2a5bda`; IDs below were read from `outcomes.json` and JUnit, not inferred from test definitions. |
| `C:/rn-finalise-20261005/parent-updates-renderer-699938f2-01/terminal.json`, `junit.xml` | Renderer and typecheck exit 0. **Two executed cases, eleven skipped**, not thirteen passes. JUnit SHA256 `fbe5b755a29250580da0f9eb3af0e15b4bf0ff736158315a9a509c3a31792b37`. Explicit false confirmations and unchanged-correction-reference handling. |
| `C:/rn-finish-20261007/evidence/connected/updates-installed-cb59-02/result.json` | Hash verified `750a9e176eb5b6863932c13a5fec68a34adf979c8b33c3004f70f97c063dbef5`; accepted installed discovery/review/unchanged refresh/reopen. The [report](finish-updates-review-20261007.md) identifies entry `update_90e368a9ee685659a6228389`, review `review_e7e301dec492b835a34fab42`, null target, empty changes, zero affected versions. It cannot establish correction effects. No mutation of this entry/profile is prepared. |

The 11 executed backend IDs are:

```text
tests/updates/test_correction_invalidation.py::test_correction_revokes_all_copies_and_only_exact_corrected_copy_can_be_reconfirmed
tests/updates/test_correction_invalidation.py::test_material_source_states_revoke_review_without_touching_unrelated_publication[chapter-replacement]
tests/updates/test_correction_invalidation.py::test_material_source_states_revoke_review_without_touching_unrelated_publication[whole-replacement]
tests/updates/test_correction_invalidation.py::test_material_source_states_revoke_review_without_touching_unrelated_publication[retraction]
tests/updates/test_correction_invalidation.py::test_material_source_states_revoke_review_without_touching_unrelated_publication[draft]
tests/updates/test_correction_invalidation.py::test_material_source_states_revoke_review_without_touching_unrelated_publication[preprint]
tests/updates/test_correction_invalidation.py::test_failed_outbox_replays_older_promotion_before_newer_invalidation
tests/updates/test_correction_invalidation.py::test_metadata_detection_revokes_same_article_review_without_claiming_retraction
tests/updates/test_correction_invalidation.py::test_correction_refreshes_real_feedback_without_rewriting_committed_answers_keys_or_scores
tests/updates/test_review_currency.py::test_retraction_requires_exact_original_article_and_never_flags_l03_family
tests/updates/test_review_currency.py::test_article_identity_enrichment_retains_prior_publication_and_access_facts
```

The renderer IDs, in `apps/desktop/src/modules/updates/updates.test.tsx`, are
`Updates review and bounded queue > submits explicit false when prior review
confirmations are unchecked` and `Updates review and bounded queue > separates
a repeated correction reference from later exact copy confirmations`.
The earlier `parent-correction-9b5410ce-01` collection failure stays failed;
none of these later passes turns it into an executed suite.

Git object comparison at this base proves equality to 699938f2 for all twelve
qualified paths in external `recovered-proof.json`: Updates `api.py`,
`models.py`, `reviews.py`, `impact.py`; assessment `repository.py`, `currency.py`;
Knowledge `repository.py`, `source_status.py`; Updates renderer `types.ts`,
`ReviewFields.tsx`; both backend test files above. Exact old/current Git blob IDs
are recorded there. The inspected Updates delta instead consists of
`literature.py`, new `topic_queries.py`, renderer `index.tsx` and its test file.
This preserves correction-test relevance while avoiding a whole-tree or
current-installation pass claim. Historical test setup uses an older content
pack; current content and navigation have changed.

The October 5 connected HTTP/restart proof in `updates-acceptance-evidence.md`
already covers same-URL digest change, exclusions, dismissal, unrelated topics,
and exact hash reconfirmation using controlled publisher/extraction/embeddings.
The recovery integration proves journal order after restore and one-event retry.
Neither needs a new broad test sweep, restore, import replay or network check.
The October 6 deferred correction follow-on was explicitly **unperformed**:
it lacked actual owned fixture identities and cannot be counted as acceptance.

## Deferred executable and isolated setup

`acceptance.mjs` is a parent-invoked packaged-app driver. It imports the existing
`RenulusController`, with its real launch preflight, fresh session allocation,
isolated environment, hidden-window/managed-backend ownership checks, screenshots
and normal restart/close. It reuses the parent's same-origin `page.evaluate`
HTTP pattern from `evidence/release/installed-updates-review.mjs` and reads
`release-b8a3c177/handoff-retained.mjs` as the lifecycle/package-binding precedent.
It does not add an arbitrary-evaluation MCP tool or attach to another app.
The documented `client.mjs` remains the normal manual controller entry point;
there is no unsupported MCP API/SQL tool assumed by this recipe.

The script takes a parent binding for an already accepted matching package
receipt. It checks its full receipt hash, EXE/ASAR hashes, package-to-checkout
product-path equality and 24 prepared source-file SHA256 pins before launch.
These are recipe identity checks; they do not replace the parent's backend/
helper inventory and installation receipts, and no repackage/install is requested.
If pins fail after integration, inspect the actual delta before adapting the
external preparation; never bypass the mismatch or relabel an older package.

There is no profile argument. A unique parent slot allocates fresh
`C:/rn-ue-SLOT/c/s-xxxxxxxx/p` through the existing controller. The compact path
stays within its 60-character Windows profile bound; an existing state root or
receipt directory is refused. This future parent-owned runtime location is
distinct from this lane's permitted preparation-write root. This lane creates
neither it nor a profile. No connection/account import, credential read, E: data,
existing `s-e8f93772` profile, retained recovery profile, or real original is used.

Synthetic setup is explicit and separately recorded in `result.json.setup`:

1. Start the new installed app once for normal migrations/bootstrap, read only
   the public bundled source metadata for `K01-2024`, and close normally.
   With zero Updates entries, quizzes, Library documents and Learn threads,
   seed **one pending** `update_entries` row into that same owned closed database.
   This follows the existing `test_review_currency.update` fixture schema.
   There is no public arbitrary-entry-create route. No review, affected row,
   journal event, answer, status change or exclusion is precomputed in SQL.
2. Reopen, add two short original synthetic notes through `/library/import/text`,
   and wait for their real product `ready` states. These new fixtures are the
   sole imports; old accepted imports are never repeated. The target uses T20,
   K01 and the bundled K01-2024 canonical URL solely as a matching identifier;
   the control uses T21 and `https://example.invalid/unrelated-SLOT`. Both start
   with synthetic final/content/latest-final flags, own-text permissions,
   an explicit synthetic edition and SHA256 of their original fixture bytes.
   They contain no guideline text. This is setup, not inspected clinical currency
   or a genuine acquired/corrected edition. The target URL is never fetched.
3. Create one T20 reviewed quiz through the product API. In the pinned 1.3.0 pack
   a fresh profile selects `RN-DIAL-001` v1, key v1, citing `K01-2024`; the driver
   asserts the actual item and fails if selection differs. Commit the first
   offered option once and end the session. Correctness is not the acceptance
   criterion. No bank version/key or real learner record is edited. The result
   belongs solely to this new synthetic profile. Snapshot public feedback plus
   canonical hashes before the notice.

The fixture declaration is the inspected evidence. Its `example.invalid` notice
URL is an inert identifier, not a retrieved document. The label, review finding,
receipt and summary all say synthetic. The real K01 URL only links the simulated
status to existing immutable content in this empty test profile. Nothing here
claims that KDIGO issued a correction or changes the source register.

## Product route contracts and assertions

All routes below are relative to the owned renderer's `/api/v1` prefix. Actual
HTTP responses must succeed; asynchronous import gets a 120-second ceiling,
each request a 120-second ceiling, and UI actions retain controller bounds.
Unexpected failure ends the run with its receipt; there is no automatic rerun.

| Route/schema | Purpose and required assertion |
| --- | --- |
| `GET /content/sources/K01-2024`, `GET /updates/schedule` | Read public bundled source identity; automation remains disabled. No `/check`, `/refresh`, retrieval-provider or subscription route is used. |
| `POST /library/import/text` | Setup body: `text`, `title`, `scope:{kind:"personal-library"}`, unique `idempotency_key`, `metadata:{source_id,source_owner,canonical_url,edition,original_sha256,topic_ids,publication_status:"final",content_reviewed:true,latest_final_verified:true,notes}`. Default `own_text_rights` supplies explicit processing permissions; `reserved` defaults false. Returns `document_id`, `revision_id`, `status`, `job`. Poll only the two `/library/documents/{id}` records until ready. No acquired collection call. |
| `POST /assessment/start` | `{idempotency_key,count:1,selector:{topic_ids:["T20"]}}`; default mode reviewed. Assert expected pinned item before submitting. |
| `POST /assessment/sessions/{id}/answer`, `/end` | Answer `{idempotency_key,item_id,option_ids:[first-offered-id]}`; end `{idempotency_key}`. Save actual attempt ID, key/version, options, correctness, assistance/repeat bucket, score and commit time. |
| `POST /library/retrieve` | `{query:"Renulus synthetic correction eligibility sentinel",scope:{kind:"study"},topic_id:"T20" or "T21",current_only:true,limit:8}`. Before review, positive target/control passage IDs must appear. Afterwards T20 must return `status:"no_eligible_documents"` and `passages:[]`; T21 still returns the unrelated note. Positive baseline prevents treating an empty/broken index as exclusion proof. |
| Real Updates form → `POST /updates/entries/{id}/review` | Actual form fills inspected synthetic evidence, exact source URL, pinned ID and correction reference. Captured request: `summary`, `topic_ids`, `reviewer:"learner"`, `state:"reviewed"`, one `evidence:{url,locator,finding,checked_on,inspected:true}`, `target:{register_id:"K01",canonical_url,pinned_source_id:"K01-2024"}`, `changes:{latest_final_verified:false,content_reviewed:false,correction}`. No draft/final, retraction or replacement inference. |
| Review result + `GET /library/documents/{id}` | Review `library_sync_state:"applied"`; exactly two applied outbox events (invalidation and review). `no-match`, failed or unavailable does not pass. Target metadata flags are false with the synthetic correction; active revision, original SHA256 and rights unchanged. Unrelated document remains exactly unchanged. |
| `GET /updates/entries/{id}/affected?limit=250&offset=N` | Read every page, bounded to 2,000 records; assert complete total, target question v1 present, and every row restricted to K01/K01-2024. Immutable historical question/case pins can legitimately yield more than one row; do not assert a fabricated one-row total. |
| `GET /updates/affected/question/RN-DIAL-001/versions/1` | `needs_re_review:true`; the concrete annotation belongs to the synthetic notice. |
| `GET /assessment/sessions/{id}/review` | Live `source_currency.state:"available"`, `needs_re_review:true`, matching reviewed notice. All other feedback fields and scores equal baseline. Actual Test → Open review → Review committed answers displays “Source notice reviewed; question review still needed” with retained version/key/result. Capture hidden pixels and ARIA before and after reopen. |

The current eligibility behavior is source-backed by `KnowledgeRepository`
`_eligible`/`retrieve`; notice flags flow through `SourceReviews.reviewed_changes`
and the actual `SourceStatusJournal`. `AffectedVersions` reads immutable pinned
citations without keys. `SourceCurrency` refreshes public feedback projections
while the saved command acknowledgement excludes `source_currency`.

The script also hashes canonical `assessment_attempts`, `assessment_commands`,
`assessment_items`, `learning_evidence`, `content_question_versions` and
`content_case_versions` in **its own new synthetic database only**. Hashes must
stay equal after correction, retry and reopen. It does not read connection or
credential tables. These hashes supplement public feedback equality; no direct
database mutation participates in the effect assertion.

Duplicate/persistence proof is deliberately local: replay the exact captured
review body once and the exact existing answer idempotency key once. Assert the
same review ID, same committed time, one review, one attempt, two setup imports,
unchanged outbox/journal IDs and payloads, and unchanged canonical hashes.
Then restart the same controller-owned app normally. Only read routes and the
existing Test review UI run after reopen: repeat the eligibility/affected/history
assertions, compare the complete affected projection, confirm the same reviewed
entry, and compare counts again. No discovery refresh, new quiz, new import or
model request is used to manufacture a deduplication pass. Final normal close
must have no forced/remaining owned PIDs; controller ownership/visibility failures
fail the result. Existing controller emergency cleanup remains classified as
failure, never ordinary-close acceptance.

## Exact parent commands, not run here

After the parent completes its current handoff and has a matching accepted
installation, inspect the external recipe and fill a new binding. The template
is deliberately non-executable until that parent scope is bound. Keep the same
external directory; the script resolves its pins beside itself.

```powershell
$prepRoot = 'C:/rn-finish-20261007/evidence/update-effects-preparation'
if (Test-Path -LiteralPath "$prepRoot/binding.parent.json") { throw 'Preserve the existing binding; use a new explicit filename.' }
Copy-Item -LiteralPath "$prepRoot/binding.template.json" -Destination "$prepRoot/binding.parent.json" -ErrorAction Stop
# Parent supplies the actual accepted package-result.json path and a unique slot.
# Set parentSerialSlot=true and allowSyntheticSetup=true only for that allocated run.
# packageReceiptSha256 = (Get-FileHash -LiteralPath <actual package receipt> -Algorithm SHA256).Hash.ToLowerInvariant()
& 'C:/Program Files/nodejs/node.exe' --check "$prepRoot/acceptance.mjs"
& 'C:/Program Files/nodejs/node.exe' "$prepRoot/acceptance.mjs" --binding "$prepRoot/binding.parent.json"
```

The only run command requires the completed binding; no unresolved ID is used as
an application target. Fixture IDs are derived from its unique slot and actual
API responses. The parent reviews `runs/SLOT/result.json`, controller receipt,
and both screenshots; the script's bounded-pass status is not full-product
acceptance. Preserve failed outputs and inspect their retained state before
deciding any continuation; changing the slot is not a reason to rerun accepted
setup/import/quiz steps. No GitHub action, deployment, install, existing-profile
adoption, backup/restore or cleanup command is included.

## Remaining truth and lane verification

This lane performed source/receipt reading, Git blob qualification, SHA256
calculation and `node --check acceptance.mjs` only. No test execution/collection,
application/runtime import, engine/model/provider/network/native operation,
content edit or profile/credential read occurred. The initial status caught
transient worktree setup; the next bounded status was clean at the requested
branch/HEAD. No reset, checkout, restore, clean or modification of other work
was used.

The recipe still needs actual parent execution. Its two text imports and positive
retrieval controls use the installed local Docling-core/FastEmbed/LanceDB path,
so it belongs in the parent's serial helper/native slot. It downloads no helpers
and requests no model generation or publisher network retrieval. It does not
establish live publisher correction, corrected-copy acquisition/reconfirmation,
all retraction/replacement states, internal provider-history screening, or
derived learner-memory invalidation. Existing controlled proofs retain those
specific policy scopes. No public `check_evidence` route exists: a displayed
answer or missing citation cannot substitute for observing provider dispatch.
Physical Windows dialogs, foreground accessibility, installation and real
external handoffs retain their separate native acceptance; hidden screenshots
do not close them. Parent source/installation acceptance remains independent.

External artifact hashes and final report-only commit are recorded in the lane
handoff. `manifest.json` records the exact preparation payload sizes/SHA256;
it excludes itself. The external artifacts remain outside Git and are not a
receipt of a performed application journey.

Sealed preparation SHA256 values:

- `acceptance.mjs`: `ad45c4d7b382abd812a6fe411e68c2da44394425e4b9c249a411165cfc49eee5`.
- `manifest.json`: `59f0cc4939f22f197ef5267eaac0aae9171a37c1fb56e01c139b4a8b58a1003d`.
