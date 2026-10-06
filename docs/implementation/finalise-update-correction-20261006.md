# Updates correction slice — October 6, 2026

Bounded production patch on `codex/release-audit-20261006`, starting at
`3d494e3ef3acf485387cfb741228f36e572e3b39`. The parent continuation is
`325bcae8`; the parent owns native Recovery format-2 parsing and the public
citation renderer. Manufacture source6599 remains historical and unchanged.
This patch is for review/integration into the next freeze, not installed acceptance.

Read Mencius's report at `0ad1daf34933485c2b8cada867df928268382188`,
`docs/implementation/finalise-freshness-learning-flow-20261006.md`, plus the
workspace/product instructions and the existing Updates, Library journal and
assessment source-impact code as text. No source acquisition, provider, network,
helper, model, native, import or test execution occurred.

The correction gap was concrete: a correction-only review could merge into a
previously verified source without clearing content/latest-final review, and
unchecked Flow confirmations were omitted from the request. The patch does the
following within Updates ownership:

- Correction references, whole/chapter replacements, retraction, removal and
  nonfinal publication states clear `content_reviewed` and
  `latest_final_verified`. The existing version-1 outbox sends a separate
  publication/scope invalidation through the existing Library status journal,
  then the exactly bound reviewed facts. Notice review is not corrected-copy
  approval; confirmations supplied with the new notice are stored false.
- Later correction eligibility needs a distinct inspected review with both
  edition and original SHA256 identifying the copy. Unbound positive
  confirmations after a correction return `corrected_copy_review_required`
  without publishing a new review or outbox event. The form retains the existing
  correction relationship but does not republish an unchanged reference when
  confirming that exact copy. It always sends both confirmation booleans,
  including explicit false. Dismissal still publishes no source facts.
- Changes to the same literature record invalidate its prior review and flag
  matching pinned versions while the new discovery stays pending. Detection
  never asserts a scientific retraction, final guidance or educational review;
  a separate correction/retraction notice never infers the original article or
  flags the whole L03 family. No new query or acquisition path is added.
- Updates delivers older pending/failed changes for the same publication before
  newer invalidations. Unacknowledged predecessors leave the newer sync visibly
  failed with `prior_source_change_pending`; existing Retry/startup outbox paths
  remain available. Applied/no-match/failed/unavailable keep their existing meanings.
- The existing key-free affected-version projection flags source re-review.
  No content pack, question key, recorded answer, score, assistance, study plan
  or historical source snapshot is rewritten. Original bytes and operation
  permissions remain under their existing owners.

There is **no shared dependency/interface/schema change**: source-status events
remain contract version1 with existing identity, scope, evidence and change
fields; routes and review payload shape are unchanged. Parent's Learn/retrieval
lane can consume the existing false review flags through current-only retrieval.
Failed/unavailable/no-match delivery remains incomplete Library acceptance and
must not be presented as successfully invalidated current evidence. Actual
corrected bytes, clinical currency and live/installed behavior are not established
by this patch or its synthetic tests. Study/history reuse guards and automatic
public passage acquisition remain with their separate owners. Flow layout and
styling are unchanged; this is a payload fix without a redesign.

Only these seven files belong to this commit:

- `runtime/renulus/updates/reviews.py`
- `runtime/renulus/updates/literature.py`
- `apps/desktop/src/modules/updates/types.ts`
- `apps/desktop/src/modules/updates/updates.test.tsx`
- `tests/updates/test_correction_invalidation.py`
- `tests/updates/test_review_currency.py`
- `docs/implementation/finalise-update-correction-20261006.md`

Prepared parent validation IDs are listed exactly below. **Every listed test
is unrun here; these are test definitions, not passes.** The new backend tests
reuse real SQLite/status-journal/retrieval/assessment consumers with synthetic
publisher material and controlled extraction/embeddings; they are neither live
generation nor an actual selected-model/installed engine acceptance claim.

| Exact test ID | Intended assertion |
| --- | --- |
| `tests/updates/test_correction_invalidation.py::test_correction_revokes_all_copies_and_only_exact_corrected_copy_can_be_reconfirmed` | Previously current copies are excluded; unbound promotion is refused; only the reviewed exact copy returns; a second correction/replayed old request cannot restore eligibility; permissions stay unchanged. |
| `tests/updates/test_correction_invalidation.py::test_material_source_states_revoke_review_without_touching_unrelated_publication[chapter-replacement]` | Chapter replacement revokes affected-copy review while unrelated publication remains current. |
| `tests/updates/test_correction_invalidation.py::test_material_source_states_revoke_review_without_touching_unrelated_publication[whole-replacement]` | Whole replacement revokes prior review/current eligibility. |
| `tests/updates/test_correction_invalidation.py::test_material_source_states_revoke_review_without_touching_unrelated_publication[retraction]` | Exact original retraction revokes copies without family-wide spill. |
| `tests/updates/test_correction_invalidation.py::test_material_source_states_revoke_review_without_touching_unrelated_publication[draft]` | Draft state clears prior content/latest-final review. |
| `tests/updates/test_correction_invalidation.py::test_material_source_states_revoke_review_without_touching_unrelated_publication[preprint]` | Preprint state clears prior review. |
| `tests/updates/test_correction_invalidation.py::test_failed_outbox_replays_older_promotion_before_newer_invalidation` | Failure is visible; local retry preserves journal order and applied-request idempotency. |
| `tests/updates/test_correction_invalidation.py::test_metadata_detection_revokes_same_article_review_without_claiming_retraction` | Same-record metadata change is pending detection with false review flags; a new notice cannot infer another original. |
| `tests/updates/test_correction_invalidation.py::test_correction_refreshes_real_feedback_without_rewriting_committed_answers_keys_or_scores` | Real reviewed attempt replay receives a later source notice; immutable assessment/content tables, answer/key, score and commit date stay identical. |
| `tests/updates/test_review_currency.py::test_retraction_requires_exact_original_article_and_never_flags_l03_family` | Affected assertion now requires both review confirmations false. |
| `tests/updates/test_review_currency.py::test_article_identity_enrichment_retains_prior_publication_and_access_facts` | Retains identity/date/access facts while clearing both review confirmations on correction. |
| `apps/desktop/src/modules/updates/updates.test.tsx > Updates review and bounded queue > submits explicit false when prior review confirmations are unchecked` | Mounted form submits actual false values for previously true confirmations. |
| `apps/desktop/src/modules/updates/updates.test.tsx > Updates review and bounded queue > separates a repeated correction reference from later exact copy confirmations` | Reconfirmation omits an unchanged notice, includes changed references and preserves evidence-free dismissal. |

Static source/diff review and Git whitespace/file-list checks are the only lane
verification. No compiler/parser, test collection, application startup, profile
inspection or runtime module import was used. The parent owns serial application
validation and the next source freeze; all actual historical failed receipts and
installed/live limits retain their original scope.
