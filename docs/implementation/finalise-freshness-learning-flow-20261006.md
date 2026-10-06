# Freshness in the learning flow — October 6, 2026

Report-only lane: codex/freshness-flow-20261006, base
5d039b0763c9e1576fac15ff0d4a96a93f7766fb, in
C:/rn-finalise-20261005/lanes/freshness-flow-20261006. No new admission gate.
Parent continues recovery9992, Connected, one selected Codex Probe, Journeys
with Image, and the prepared scanned-PDF/Flow/K01 slice unchanged. The accepted
manufacture freeze 6599bf79 is not edited or retested.

**Answer: the complete automatic no-upload freshness path is missing.** Explain
retrieves existing Library passages and automatically discovers key-free
literature metadata. It cannot automatically acquire a passage when Library has
none. Reviewed source restrictions and assessment annotations have working
local implementations, but correction handling does not reliably invalidate
old evidence, and affected Study activities have no source-status projection.
These are implementation gaps as well as unperformed installed acceptance.

## Existing entrypoints and precise limits

All HTTP paths below have the /api/v1 prefix. Source links refer to this base;
no installed payload, private profile or external receipt was opened here.

| Flow | Existing entrypoint | Actual behavior |
| --- | --- | --- |
| Explain | [learn/api.py](../../runtime/renulus/learn/api.py), POST /learn/ask; [LearnService.answer](../../runtime/renulus/learn/service.py), line 154 | Retrieves Library evidence for study scope, then retries without the topic filter. Neither call passes current_only. Any returned passage produces verification=retrieved. Ask has no freshness input/policy. |
| Empty-Library fallback | learn/service.py, lines 134 and 199; [RetrievalService.discover](../../runtime/renulus/retrieval/service.py), line 145 | With an installed topic and zero local citations, performs one Europe PMC topic-label discovery, maximum five records, eight-second Learn deadline. Emits discovered-literature with passage_evidence=false and latest_final_verified=false. Discovery text never enters model evidence. No acquisition or second passage retrieval follows. Free exploration without a canonical topic does not discover. |
| Visible failure | [Learn renderer](../../apps/desktop/src/modules/learn/index.tsx), lines 105–109 | Local retrieval failure/unverified state and discovery failure are visible. Discovery displays search/publication dates and says it does not verify the explanation. There is no passage-fetch failure path. Discovery disclosure is transient; saved messages retain citations, not the discovery event. |
| Deliberate full text | POST /retrieval/articles/import; retrieval/service.py, lines 218 and 246; Library **Add eligible full text** in [RetrievalConnections](../../apps/desktop/src/platform/RetrievalConnections.tsx) | Requires personal-library scope and explicit import intent. Checks exact PMC identity, nonretraction metadata and explicit CC BY/CC0 licence; fetches bounded XML and queues text through Knowledge. Currency/content review remains unverified. Explain never calls it. Manually importing and asking again does not prove automatic acquisition. |
| Source checks | [UpdatesService](../../runtime/renulus/updates/service.py), line 94; POST /updates/sources/{id}/check and publication checks | Catalogue links/publication digests create pending changes after a difference. Baseline/unchanged is not an educational update. Publication-check bytes are not ingested passages. |
| Explicit review | POST /updates/entries/{id}/review; [SourceReviews.review/sync](../../runtime/renulus/updates/reviews.py), lines 77 and 150 | Saves inspected URL/location/finding/date, educational implication and exact target. Durable version-1 outbox calls KnowledgeRepository.update_source_status. Applied/no-match/failed/unavailable are distinct; POST /entries/{id}/sync and **Retry library update** recover the seam. |
| Later evidence | [source_status.py](../../runtime/renulus/knowledge/source_status.py), lines 157, 232 and 242; [KnowledgeRepository](../../runtime/renulus/knowledge/repository.py), line 509; POST /library/retrieve | Journal changes matching revision metadata and replays on later imports. General retrieval excludes retracted/superseded/access-changed/draft/preprint sources and conservatively suppresses documents with replaced topics. current_only=true additionally requires final, latest-final verification, content review, nonremoved status and unexpired review. Edition/hash promotion is exact; acquired-copy retraction/removal/access loss remains publication-wide. |
| Reviewed Test/history | [Updates impact](../../runtime/renulus/updates/impact.py), [assessment currency](../../runtime/renulus/assessment/currency.py), [SourceCurrencyNotice](../../apps/desktop/src/modules/assessment/SourceCurrencyNotice.tsx) | Exact pinned source/item/version/locator notices refresh on pending items, feedback, sessions and replays. Recorded answer, key, score, assistance and dates stay pinned. Source review leaves question re-review pending; it does not repair a bank key. |
| Actual key correction | [ContentRepository](../../runtime/renulus/content/repository.py), lines 53, 81 and 108 | Immutable pack/item versions; changed keys require a correction and predecessor withdrawal. New published versions are separate from source-status review. No source check implicitly manufactures a new key. |

## Concrete missing core and smallest subsequent fixes

1. **Acquire evidence before Explain generation.** M1 lacks discovery → eligible
   full text → dated passage. Factor the rights/identity/licence fetch in
   RetrievalService._import_article into a reusable internal operation; add one
   bounded, cancellable study-evidence call before generation using only the
   canonical topic for public discovery and existing passage/extraction machinery.
   Keep evidence scoped to the run unless existing permitted cache retention
   applies; preserve deliberate personal-library Save semantics. Return actual
   passage text, source identity, publication/retrieval dates, locator and rights.
   Expose no eligible text, denied rights, missing dates, timeout and cancellation
   without paid-tool rotation. Add explicit freshness intent/policy through the
   existing Ask/UI flow; current-guidance requests must use current_only=true in
   both local attempts and retain it across fallback. A dated research passage
   can support research explanation; it cannot certify latest-final guidance.
2. **Correction must invalidate review until affected bytes are checked.** A
   correction reference alone changes metadata/flags items without clearing
   latest_final_verified or content_reviewed in SourceReviews/SourceStatusJournal.
   Knowledge eligibility does not examine correction, and Explain ignores the
   current-only flags. Also [reviewPayload](../../apps/desktop/src/modules/updates/types.ts)
   sends those confirmations only when true: unchecking them cannot publish false.
   A previously verified copy can remain eligible after correction-only review
   unless a separate byte-change observation invalidated it. Small fix: explicit
   invalidation of affected copies on a new correction; restore currency only
   after exact corrected-copy review, with deliberate false/unknown states in
   the existing form. Keep original bytes and the correction relationship.
3. **Show affected learning where it is reused.**
   [StudyService.list_activities/plan](../../runtime/renulus/study/service.py) never
   queries Updates impact; Home only lists three reviewed entries. Project the
   existing key-free needs_re_review seam onto activities with pinned question/
   version and link the notice, preserving schedule/manual overrides/progress.
   Learn passes old assistant messages as history without source-change
   annotations (service.py, line 228); excluding a source from later retrieval
   does not remove its prior explanation from context. Add a current warning/
   evidence-reuse guard while retaining historical messages and scores. No new
   scheduler, scoring engine, dependency or provider is needed for these seams.

These are bounded proposals for a later source freeze, not implementation
authorisation now. Parent should qualify audit S2.09 “Implemented / live flow
open” as **partial / automatic passage path missing**. S1.06/S2.06/S5.04/G8 retain
the identified correction and learning-context limits.

## Existing proof reconciled; no reruns

- [Learn discovery tests](../../tests/learn/test_discovery.py), especially
  test_one_generic_topic_request_is_discovery_only_and_not_stored, explicitly
  assert empty citations, no Knowledge documents/imports and no discovered title
  in model evidence. Failure/cancellation/scope/replay tests support that boundary.
- [Retrieval evidence](retrieval-evidence.md) records the combined 89-check local
  run and four earlier real free metadata requests on October 4. The probe made
  no full-text import or model call.
- Audit R10/[Updates acceptance](updates-acceptance-evidence.md): 53 Python/25
  renderer checks, controlled publisher, real SQLite/status journal/LanceDB and
  controlled extraction/embeddings. Three actual free requests on October 5 at
  00:14:58 UTC discarded PDF bytes and performed no educational review.
  [Exact-copy binding](updates-acquired-version-binding-evidence.md) proves local
  promotion/restriction/restart rules, not installed publisher review. Counts
  overlap earlier suites and are not added together.
- [Assessment source-currency tests](../../tests/assessment/test_source_currency.py),
  especially test_review_and_dismissal_refresh_feedback_replays_without_rewriting_attempt_facts,
  compare actual assessment tables, feedback, scores and restart/replay. The
  replacement test in tests/updates/test_review_currency.py uses a synthetic
  history sentinel; it is weaker than the real assessment consumer proof.
  Audit R12/R34 preserve version/history and publisher/corrected-byte limits.
  None proves installed correction changing later Explain or annotating Study.
- [Gap triage](finalise-gap-triage-20261006.md) correctly leaves freshness open.
  [Prepared gap slice](finalise-installed-gap-slice-20261006.md) supplies exactly
  one deliberate K01 baseline check and persistence observations. Reuse it: no
  changed-entry review or Explain passage follows from that check. No second K01
  fetch, baseline, import, Probe or Journey is proposed.

## Parent user/UI steps on existing installed surfaces

After the existing parent operations, use their owned synthetic installed
profile and approved connection; preserve their receipts and ordinary-close
recipe. These are manual observations, not a driver/binder or admission rule.

1. **Reuse K01 evidence.** In Updates read the completed gap-slice K01 badge,
   check/success dates and retained automation-off selection. Do not press Check
   now/Refresh. Baseline/unchanged has no changed educational entry; record absence.
2. **Diagnose no-upload Explain if parent elects this distinct observation.**
   Learn → **New study** → installed topic with no eligible passage already
   present → **Direct explanation**. Example T08: “Explain CKD assessment using
   the latest final guidance; show the publication date and the source passage
   you actually retrieved.” Attach nothing; **Ask Renulus** once on the existing
   selected Codex route. Capture evidence status, discovery search/publication
   dates and presence/absence of **Source 1**. Current code exposes unverified
   discovery. An existing Library citation proves reuse only; do not delete
   sources to force an empty condition. Terminal subscription failure proves
   neither passage acquisition nor successful explanation. Do not repeat Probe/
   Journeys, transfer credentials or switch to Go.
3. **Review an existing genuine relevant pending change when available.**
   Updates → **To review** → entry → **Open publication**. Fill **What changes
   for your learning?** and inspected evidence URL/page/finding/date. Expand
   **Publication status and affected source**, select **Record the source facts
   established by this evidence**, identify the original publication and actual
   acquired copy where applicable. Record only established **Correction reference**,
   **Replacement scope**, **Retraction** or draft/final state. Retraction requires
   original DOI/PMID/PMCID. Select related topics → **Save reviewed update**.
   Capture affected items/objectives and Library acknowledgement. No-match/failed
   remains incomplete; **Retry library update** retries local sync without K01
   fetching. With no genuine pending change/evidence, record review unperformed;
   do not relabel a baseline or invent inspected findings.
4. **Observe reuse/history.** Open an already recorded matching Test session/
   feedback from history; compare pinned question/key, answer and committed score
   with its retained receipt. Expect **Source notice reviewed; question review
   still needed** with retained score. Inspect its Study activity and Today
   reviewed-update link: the absent activity warning is the identified gap.
   During a later authorised affected-topic Explain, inspect citations:
   replacement/retraction/draft exclusions should persist; correction-only flags
   do not prove corrected evidence. Reuse parent ordinary reopen/close observations.

Passage-fetch failure cannot be exercised through a missing path. Record a
naturally observed discovery failure and visible message; do not alter machine
networking, fake publisher responses or corrupt state. Successful automatic
acquisition/failure and an evidenced change affecting later learning remain
unperformed installed proof after the vertical fixes.

Read required workspace/product/decision/source and stage/ownership documents,
audit/triage, relevant runtime/renderer/tests and dated reports as text. No tests,
provider/network/helper/native work, private profiles, media, secrets, subagents
or runtime edits. Flow, source-operation permissions and temporary retention
remain preserved. Codex remains GPT 6.1 Sol/GPT 6 Astra/GPT 6 Luna; Go MiMo V2.6 Pro/
DeepSeek V4.1 Flash stays paused. Only this report is committed; parent owns
integration and ledger reconciliation.
