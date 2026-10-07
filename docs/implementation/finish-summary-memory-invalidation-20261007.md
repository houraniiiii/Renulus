# Recalled Memory invalidation during Explain — 7 October 2026

**A narrow missing guard is implemented in this lane, with 13 proposed controlled
test cases, none executed or collected.** The defect is stale recalled Memory in
the primary system context after a canonical correction/deletion. It is not an
unpurged durable Hermes summary. This refines the earlier [M disposition](finish-final-disposition-20261007.md).
Parent's manufacture of `0318c41f` remains a separate preserved release; this
patch is not in that artifact and grants it no new acceptance.

Base `91ac01c733a38400e3bc47349ed99962c206c7b3` adds only the previous audit over
product `0318c41f916ed6861a7b3be52a1d5fc37a1ca0ff`. The patch touches only
`learn/service.py`, new `learn/memory_context.py`, new
`tests/learn/test_memory_context.py`, and this report. No schema, runtime manager,
context adapter, Memory engine or previous audit is edited.

**Existing guards and what they actually establish.**

| Boundary | Existing implementation and evidence | Exact limit |
| --- | --- | --- |
| Recall | [MemoryService.retrieve](../../runtime/renulus/memory/service.py) joins current canonical revision to derived index entries, excludes deletion markers, filters topic and returns canonical text within a budget. | Valid at retrieval, not automatically valid after Learn awaits another operation. |
| Correction/deletion | [MemoryRepository](../../runtime/renulus/memory/repository.py) increments revision on edit, suppresses old producers, marks deletion and dirties the derived generation. | It cannot change a system string already copied into an active Learn coroutine. |
| Capture/reindex | `tests/memory/test_service.py::test_edit_or_delete_during_generation_suppresses_late_result[edit/delete]` and `::test_epoch_guard_prevents_stale_index_activation`; accepted controlled identities M4/M5 in [failure disposition](finish-failure-disposition-20261007.md). | These guard extraction/capture and index activation, not an ordinary Explain request waiting on compaction. Retain their acceptance. |
| Actual Memory lifecycle | Installed edit/recall/delete/reopen and qualified actual Mem0 history/rebuild are recorded in the [current audit](finish-audit-20261007.md) and failure disposition. | Sequential correction is not a concurrent protected-system-context check. No engine replay is needed solely for this finding. |
| Hermes compaction | [context.py](../../runtime/renulus/runtime/context.py) plans with protected head/tail; upstream `_protect_head_size` always protects the initial system message. `summary_messages` receives only selected turns. `_finish_context` clears its transient summary and runtime cleanup clears messages. | The newly recalled Memory is appended to that initial system message and normally is not summary input. A prior assistant message may still contain old discussion; this patch does not claim to trace every historical statement to a Memory record. |
| Runtime orchestration | [manager.py](../../runtime/renulus/runtime/manager.py) has connection identity guards, cancellation, approved summary routing, and `started` / compaction `progress` events before primary transport. `stream()` discards those non-text events. | No canonical Memory revision/deletion check existed at those boundaries. The manager's account guard protects a different invariant. |
| Accepted compaction tests | `tests/runtime/test_images_context.py::test_real_hermes_compactor_sdk_selected_route_scope_head_tail_and_no_temp_writes` and `::test_parent_cancel_stops_compaction_child_and_has_one_terminal` are in the 12-case controlled affinity invocation in [Go evidence](finish-go-20261007.md). | Actual Hermes planning with mocked output, protected context/no-write/route/cancel credit; no concurrent canonical Memory edit was exercised. |
| Learn citations and commit | [Learn](../../runtime/renulus/learn/service.py) already rechecks freshness-sensitive citations before dispatch and after generation, checks cancelled/deleted thread/run state, and creates answer-reference evidence only with the committed ordinary-study answer. | Those checks do not inspect recalled Memory revisions. They remain in place. |

Source comparison found **no changes from `cb59beb2` to `0318c41f`** in the five
production files below. Existing accepted behaviour keeps that qualified source
relevance; this read does not create new pass results.

| File under runtime/renulus | Base Git blob at 0318c41f |
| --- | --- |
| learn/service.py | `62529e9ebe48218db18a72b9368ed7c5ee665358` |
| runtime/manager.py | `d350dc3f8c6cc5b28efa7fe45392d361b81ce647` |
| runtime/context.py | `646d96b338997bec8632d872672a8735eaf85a6d` |
| memory/service.py | `364bcbedbe45377fcf17a6a01a41430d0d1cc9df` |
| memory/repository.py | `5fb638b4ea93202d959c2c38cd37e70aad5cbef0` |

**Concrete failure ordering before this patch.** Learn recalls record A at r1,
copies its text into the system instruction, and starts runtime generation.
Runtime awaits an approved compaction response. The user edits A to r2 or deletes
it; canonical/index guards correctly record that change. The completed compaction
still retains the old protected system message. Runtime can then send primary
generation with r1; Learn can commit its answer and emit new capture evidence
without noticing A changed. A correction during response streaming has the same
commit gap. This conclusion is from source control flow, not a newly executed
reproducer or a claim about a previously observed clinical answer.

**Patch behaviour.**

- [MemoryContext](../../runtime/renulus/learn/memory_context.py) selects at most
  the existing six recalled records/3,000 characters. It validates their IDs and
  revisions against canonical rows, eligible scope/topic and `deletion_ledger`,
  constructs prompt text from those rows, and pins ID/revision/text/scope/topic
  only for the current request. Opaque derivative context is not trusted. A
  missing or already revised returned record fails closed before dispatch.
- When pins exist, Learn consumes the approved provider's existing `events()`
  interface, validating before advancement and after each event. This covers
  `started` after token acquisition, compaction start, compaction completion
  before primary dispatch, deltas and completion. If Memory changes during
  compaction, its already-started summary may finish, but the stale primary
  request is refused. No manager or compactor change is necessary.
- Existing stream-only controlled adapters remain supported with checks around
  their text stream; they expose no compaction events. The production
  `ProviderManager` does expose them. This is the same selected provider, never
  an alternative subscription/model or automatic generation retry.
- The final pin check runs inside the **same `BEGIN IMMEDIATE` transaction** as
  assistant-message completion and learning/capture evidence. A canonical
  edit/delete that committed before that transaction cannot be missed, including
  one that occurred during the final awaited citation check. No lock is held
  over network/compaction awaits. Once the answer commits first, a later edit is
  a later event; historical answers are not rewritten.
- A failed guard produces retryable `explain_memory_changed`, retains the user
  question and a failed run, closes the active iterator, and creates no assistant
  answer or learning/capture evidence. Already streamed fragments cannot be
  retracted; the request ends in error and is not stored as completed. The error
  contains no Memory text/IDs. Only a deliberate new request recalls new state.
- Temporary/unclassified cases still skip Memory retrieval; absent/failed recall
  still permits the existing unpersonalised explanation. The patch changes no
  citation freshness test, case handoff, source eligibility or capture policy.
  Unrelated Memory edits do not invalidate a selected record through a global
  epoch check. No new summary store, schema, worker or engine is introduced.

**Deterministic proposal for the parent's serial validation.**

All new IDs have prefix `tests/learn/test_memory_context.py::`. They use actual
`Database`, `MemoryRepository`, `LearnService` and `ProviderManager` with only
Learn/Memory schema migrations in a fresh synthetic profile. Recall selects real
canonical records without a semantic engine. Authentication returns a synthetic
token in memory; compaction planning and response transport are controlled
doubles. Socket connections are refused. `asyncio.Event` gates fix ordering;
five-second waits are failure bounds, not sleep-based race timing.

| Exact node suffix(es) | Proposed observation |
| --- | --- |
| `test_recalled_revision_change_refuses_stale_answer[pre-dispatch-edit]`, `[pre-dispatch-delete]` | Mutate after the Memory event and before provider advancement: zero transport calls, input retained, no answer/capture. |
| `test_recalled_revision_change_refuses_stale_answer[compaction-edit]`, `[compaction-delete]` | Pause actual manager orchestration in its controlled summary transport; mutate/release: exactly one summary, zero primary calls, closed run/iterator, no answer/capture. |
| `test_recalled_revision_change_refuses_stale_answer[response-edit]`, `[response-delete]` | One fragment may have streamed; after mutation the next fragment is withheld and nothing is committed/captured. |
| `test_recalled_revision_change_refuses_stale_answer[commit-edit]`, `[commit-delete]` | Mutation during final awaited citation validation is caught inside the answer transaction after the provider completed. |
| `test_deletion_marker_wins_over_retained_canonical_row` | A retained same-revision row plus newer tombstone is ineligible, including the restore-shaped state. |
| `test_unrelated_edit_does_not_invalidate_selected_memory` | An unrelated edit permits compaction/answer commit with the selected canonical context; opaque derivative text is absent. |
| `test_explicit_new_request_after_reopen_uses_only_current_memory[edit]`, `[delete]` | Reopen the real database/repositories after refusal; an explicit new request uses r2 or no deleted record, with no automatic retry. This is not an engine rebuild run. |
| `test_source_freshness_guard_still_refuses_commit` | Unchanged Memory cannot bypass the existing final source-eligibility rejection. |

These **13 proposed cases are unexecuted**, including the controlled compaction
cases. They establish no new actual Hermes, semantic retrieval/reindex, live
provider or installed acceptance. Existing `tests/learn/test_freshness.py`
source-change cases and `tests/learn/test_learning.py::test_volatile_explain_never_calls_library_or_learner_memory`
retain their separate regression relevance; no broad sweep is requested.

**One required test-fixture repair outside this lease.**

`tests/learn/test_learning.py::test_study_recall_is_separate_from_evidence_and_capture_follows_commit`
returns `records=[{"id":"one","revision":2}]` without a canonical row and expects
successful personalised completion. That fabricated reference is now correctly
rejected. Static inspection predicts this existing test needs a fixture update;
no failing invocation was run. Parent should create a synthetic `ManualFact`
through the actual Memory repository before replacing its registry service,
optionally edit it to r2, and return that real row in the recall double. Keep its
separate evidence/capture/budget assertions. The file is not leased and is left
untouched. No production edit outside the two leased Learn paths is required.

**Handoff boundary.** Static diff/source reads, whitespace, explicit-file scope
and test-ID review only. No Python/application execution, test collection,
provider/engine/model/native/network operation or private-state access occurred.
Parent owns the fixture repair and serial execution before accepting this patch;
preserve its 0318 manufacture and existing provider receipts. No instruction to
repeat a provider call, manufacture or accepted engine/recovery run is implied.

**S4.04 / M disposition:** retain accepted sequential correction, deletion,
reopen/reindex and late-capture/index guards. The distinct active Explain context
gap now has a bounded implementation and proposed canonical concurrency proof;
its acceptance remains pending the parent's fixture repair and serial results.
There is no durable summary artifact to purge or new personalisation requirement.
