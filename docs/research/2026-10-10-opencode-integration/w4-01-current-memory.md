# W4-01 — Current memory recapture revalidation

2026-10-10. **Research/testing only. The W2 stale-memory recapture defect remains reproducible at current Design C commit `76cfdff23e259700bec820e174c200540c7c1e1b`.** Four synthetic cases recreate corrected/deleted text under a new fact ID. This is a canonical admission defect, not a measurement of model repetition frequency.

The [W2 replay](w2-01-memory-dependencies.md) used research baseline `528025ff0b22477c12ee1512e0e7d15297a6e888`. All repository paths below identify **current commit `76cfdff23e259700bec820e174c200540c7c1e1b`**, reproducible with `git show <commit>:<path>`; the [current source map](current-source-map.md) supplies public citation anchors and SHA-256 identifiers. All **365 Git blobs** under `runtime/renulus`, `tests`, and `pyproject.toml` matched the frozen snapshot byte-for-byte. Documentation was read from the research checkout. The selected harness baseline remains [OpenCode `4b6fea2`](https://github.com/anomalyco/opencode/tree/4b6fea2875e4f2e3e8a8fee181803e54f7056845), distinct from [SDK 2.0.26 tag `9b4ec57`](https://github.com/anomalyco/opencode/tree/9b4ec5714d481559990db0a816d5dec19541a814); neither upstream runtime was executed here.

**Executed reproductions.** The owned research `probe.py` follows W2's two intervals, using current `LearnService`, `MemoryService` edit/delete, automatic scan, worker claim/current/commit, and real SQLite. Answer generation, recall ranking, extraction and vector rebuilding are deterministic doubles. Every profile is synthetic and isolated; external socket destinations are denied. The extraction double deliberately returns the old point only after confirming its source answer contains that point and `current(job)` accepts it.

| Interval | Mutation | Observed result |
| --- | --- | --- |
| Completed answer, capture queued | Edit original | Old point committed under a new ID; corrected original survives; two learning points. |
| Completed answer, capture queued | Delete original | Old point committed under a new ID; original tombstone survives; one learning point. |
| First capture completed, then same-chat follow-up | Edit original | Explicit recapture of first evidence is suppressed; old assistant text enters follow-up context; new answer recaptures it. |
| First capture completed, then same-chat follow-up | Delete original | Same replay despite first-evidence suppression; new stale ID coexists with the original tombstone. |

All four jobs finish `completed`, with `current=true` immediately before extraction. Mutation advances the memory-index epoch (`1→2` queued; `2→3` previously captured), while `design_c.context_epoch` remains `0→0`. These are executed service/worker findings; the four cases do not exercise the desktop or OpenCode host. The owned `probe-output.txt` retains the four JSON results.

**Why current protections do not close this defect.** Static inspection finds `capture_fingerprint()` now includes source revision, assessment-policy revision and context epoch. Edit/delete still invalidate only the memory-index epoch and suppress sources already attached to that fact. A queued answer that merely consumed the fact has no such source edge. The answer's unchanged reference remains eligible. Source: `runtime/renulus/memory/repository.py`, lines 16–21, 89–91, 134–176 and 455–536 ([map 11](current-source-map.md#source-11)).

Memory pins still live only inside the current explanation. Completed-answer publication persists `scope` plus `{message_id, run_id, sha256, version}`; it omits consumed memory revisions. The resolver checks completion, ownership, suppression, tombstones, length and digest, without learner-dependency checks. History filtering checks citations, leaving uncited old answers available after their underlying facts change. Current sources: `runtime/renulus/learn/memory_context.py` (`MemoryContext`), `runtime/renulus/learn/service.py` (`answer`), `runtime/renulus/memory/study_answers.py` (`answer_text`), and `runtime/renulus/learn/evidence.py` (`conversation_history`).

**Changes since W2 that must be retained.** Current code fences pre-restart executions, checks policy/context before inference and commit, and implements transactional restore barriers covering evidence even without jobs plus explicit capture admission after restore. `MemoryService` coordinates recovery with active capture. The selected tests exercise these protections. Sources: `runtime/renulus/memory/service.py`, repository admission/commit ([map 11](current-source-map.md#source-11)), and `runtime/renulus/storage/invalidation.py` ([map 16](current-source-map.md#source-16)).

Typed restore relationships exist: project membership cannot delete shared endpoints, and deleting a conversation does not automatically delete independently retained memory. Publication callbacks surround database transactions; conversation completion checks context epochs. These protect registered boundaries, without supplying missing memory dependencies. W2's proposal to introduce typed restore traversal is superseded. Sources: `runtime/renulus/storage/relations.py` ([map 19](current-source-map.md#source-19)), `runtime/renulus/storage/publication.py` ([map 17](current-source-map.md#source-17)), and `runtime/renulus/learn/conversation_stream.py:131` ([map 10](current-source-map.md#source-10)).

**Scope qualification.** Current memory storage, deduplication and recall have no project discriminator: ordinary Study memory is profile-global. Project setup restricts document revisions, not memory visibility. W2's project-local/global memory split remains a proposal. Temporary ordinary conversations use `UNCLASSIFIED`, skip Study recall/capture and retain volatile history; saved cases remain ineligible. Temporary-conversation and capture-exclusion tests passed. Sources: `runtime/renulus/memory/schema.sql`, `runtime/renulus/memory/models.py`, and `runtime/renulus/learn/conversation_stream.py:180–220` ([map 10](current-source-map.md#source-10)).

**Minimal remaining delta — proposal only.** Persist a versioned, reference-only dependency manifest with each completed-answer receipt, including consumed memory revisions and dependencies inherited through prior assistant messages. Validate that manifest before extraction and again inside `commit_capture()`. Fact correction/deletion must permanently invalidate dependent receipts/jobs and exclude their historical text from future context; retain user-visible history separately. Unknown legacy lineage cannot be treated as an empty, valid dependency set. Extend the existing typed restore/suppression machinery to those references and preserve independent user corrections/support.

Advancing the context epoch alone is insufficient: current scan deliberately requeues boundary-cancelled work when its source remains unchanged. A revoked dependency must remain terminal across scan, retry, restart and restore. Keep the current memory engine and worker; no new scheduler or wholesale restore rewrite is needed. For OpenCode integration, resolve the authoritative answer through its receipt adapter instead of copying transcripts. Future optional providers must obey the same contract; selected defaults are unaffected.

Next-wave acceptance should exercise these four cases through the assembled conversation/API path and selected embedded host, pause at resolution/extraction/commit, reopen both stores, then restore an older export. Check inherited dependencies through summaries, recent history, children and explicit recapture; test independently supported facts separately from echoes. Project isolation requires its own explicit scope decision and tests. Those integrated outcomes, real extraction quality and Windows desktop behavior are **not proved here**.

**Exact checks.** Managed Python was `3.14.4`. Owned probes/logs reside in ignored `.local/research/w4-01-memory`; these are local execution receipts, not public source links. `checks.py` denies external socket destinations, disables pytest plugin autoload/cache and bytecode, and enables the asyncio plugin. From frozen `.local/research/opencode-v2-current-76cfdff`, the executed selections were:

```powershell
$py = 'C:/Renulus/dev/python/Scripts/python.exe'
& $py -B ../w4-01-memory/checks.py identity
& $py -B ../w4-01-memory/probe.py
$suite = @(
  'tests/memory/test_repository.py'
  'tests/memory/test_service.py'
  'tests/memory/test_study_answer_capture.py'
  'tests/integration/test_design_c_migration.py'
  'tests/integration/test_design_c_conversations.py::test_temporary_multi_turn_generation_stays_out_of_profile_and_export'
  'tests/integration/test_design_c_conversations.py::test_context_change_during_reply_blocks_late_assistant_publication'
)
& $py -B ../w4-01-memory/checks.py @suite
$boundary = @(
  'tests/memory/test_whole_attempt_evidence.py::test_equal_foreign_restore_fingerprint_requires_explicit_same_row_requeue_and_fences_old_execution'
  'tests/memory/test_whole_attempt_evidence.py::test_boundary_interruption_requeues_one_fresh_canonical_scalar_capture'
  'tests/memory/test_whole_attempt_evidence.py::test_scan_never_requeues_terminal_capture_after_boundary'
)
& $py -u -B ../w4-01-memory/checks.py @boundary
& $py -u -B ../w4-01-memory/checks.py short-profiles tests/memory/test_study_answer_capture.py -k 'not reference_eligibility'
```

Outputs: identity **365 matched**; probe **4/4 confirmed**; initial suite **12 failed, 56 passed in 113.47s**; boundary selection **12 passed in 65.57s**; failing-case rerun **12 passed, 7 deselected in 7.40s**. Initial Qdrant SQLite open/lock-cleanup failures disappeared when only synthetic profiles moved to shorter owned `C:/Renulus/scratch/w4m-*` paths; the exact OS threshold was not established. There are **80 distinct passing regression cases** across the runs. Same-source suppression tests do not exercise a fresh follow-up receipt. Logs: `tests-output.txt`, `boundary-tests-output.txt`, `short-profile-tests-output.txt`. Current test sources include [migration tests, map 24](current-source-map.md#source-24) and [conversation tests, map 23](current-source-map.md#source-23), alongside the exact memory test paths above.

No live provider/auth calls, installations, deployment, private profiles or product edits occurred. Only this memo and owned research probes/logs were written; synthetic profiles were removed by their test owners.
