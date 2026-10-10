# W2-03 — Workflow ownership, receipts and recovery

2026-10-10; research only. Renulus baseline: `528025ff0b22477c12ee1512e0e7d15297a6e888`; OpenCode source: `4b6fea2875e4f2e3e8a8fee181803e54f7056845`. SDK `2.0.26` belongs to tag `9b4ec5714d481559990db0a816d5dec19541a814`; registry dependencies include Effect `4.0.0-rc.112`. These are distinct artifacts; no OpenCode runtime was executed. [Package][package]

Read [W1 ownership](w1-01-current-integration.md), [W1 routing](w1-05-model-routing.md) and the parent draft’s [workflow contract][parent]. **Recommendation:** Renulus decides finite domain stages and commits results; OpenCode exclusively runs admitted model work, children, tools and execution recovery. No second agent scheduler.

**Observed Renulus code.** Generated publication and its command receipt commit together; repeated keys compare payload hashes. However, runs/cancellation remain in memory, generation accepts at most five items, and source revalidation precedes publication rather than sharing its transaction. Reviewed answers, exposure, learning evidence and command receipts commit together. [Generated repository][generated], [streaming][streaming], [limits][limits], [reviewed][reviewed]

Updates already has a domain outbox: review/change publication enqueues `update_library_changes`; delivery awaits an acknowledgement, while Knowledge rejects reused event IDs with changed payloads. This is reusable precedent, not an existing general two-database protocol. Source-link fingerprints and publication observations create deterministic pending-review entries. Scheduling permits five checks per batch, 50 seconds/check and two delayed retries; these allowances must not become generation retries. [Outbox][outbox], [consumer][consumer], [sources][sources], [publications][publications], [schedule][schedule]

**Observed OpenCode coordination.** Foreground subagents block on their child job; interruption explicitly interrupts that child and cancels its job. Background observers use global scope and stable completion-notification IDs. A parent stop calls `jobs.cancel(parentID)`, not a recursive descendant sweep; background-tree cancellation therefore needs explicit host coordination. Acceptance of interruption precedes settlement. [Subagent][subagent], [observer][observer], [completion][completion], [execution][execution]

Shutdown retains execution claims; restart reconciles background children/notices and resumes orphaned work with a default ten-resumption counter. Recovery is explicitly at least once, assumes the old owner is dead, and can wake parents through child completion. The separate runner retry policy also allows ten retries. Neither is Renulus’s attempt budget. [Restart][restart], [retry][retry]

**Proposed domain boundaries and starting budgets.** These refine DC06/DC16/DC19, not implemented functionality. [Design C][design]

| Operation | Deterministic authority and bounded execution |
| --- | --- |
| Generated 5/10/20 | M4 fixes 1/2/4 sequential five-item slots. OpenCode executes each admitted batch; no model plans the slots and no autonomous child is required. Persist validated slots; verify exact total, keys, evidence and cross-batch duplicates before one immutable version. Partial sets require explicit count acceptance. |
| Reviewed score summary | Repository computes score/buckets from pinned attempts. Optional narrative gets one request against a key-free aggregate snapshot; failure leaves numbers usable. Narrative cannot alter marks or learning evidence. |
| Daily suggestions | One request produces the complete three-by-five bundle. Validate/cache atomically; retain a still-eligible prior cache or empty state on failure. Opening/selecting suggestions creates no learning evidence. |
| Nightly | Off by default; admission uses the same generated-test operation. Persist one profile/purpose/local-date occurrence, frozen timezone/due-UTC and settings revision. Settings/input hashes do not create another daily identity. Coalesce missed dates into one catch-up; no backlog or clock-rewind replay. Disable revokes pending work and publication. |
| Updates | Keep existing source/metadata checks and review authority deterministic. A separately enabled digest gets one bounded generation request keyed to the observed revision; it cannot mark an edition reviewed. |

Daily/date admission runs only with the application. DST/timezone changes recompute future due times but preserve consumed occurrences and a monotonic occurrence frontier. Temporary input crosses into durable generation only after DC18’s validated fictionalisation or explicit permitted save. [Design C][design]

**Proposed receipts across two databases.**

1. In Renulus SQLite A, atomically create `operation_id`, immutable payload digest, stage/slot, input revisions, cancellation epoch, route/configuration revision, budget and a delivery outbox row. Uniqueness is operation ID; digest mismatch conflicts. Persist chosen runtime session/input IDs before delivery.
2. Deliver into OpenCode SQLite B using those same IDs and `resume:false`; acknowledge admission in A. Lost acknowledgements reconcile B’s inbox/history before waking. OpenCode admission matches ID/session/type, not payload equality; repeated prompts still wake by default. A must enforce digest equality and distinguish admission replay from permission to execute. [Inbox][inbox], [prompt][prompt]
3. At each actual outbound model attempt, atomically reserve/consume its A permit before dispatch. Store route, attempt ID and outcome; a consumed permit cannot be reused or reset by recovery. Transport replay, auxiliary calls and children spend permits too. Start with one permit per batch/bundle/narrative, zero automatic repair/title/compaction requests, and zero crash resends. After restart, unfinished generation requires explicit continuation even for unsent remaining slots. A possibly sent request remains uncertain; never refund merely because acknowledgement is absent.
4. Domain effects use stable `(operation_id, stage, slot)` keys. In one A transaction, compare epoch, enabled state, tombstones and input revisions; then persist result/version, receipt and notification outbox. Publication has one unique operation/version identity. Replayed tools return that receipt; deleted results stay unavailable, and changed payloads conflict. This extends existing `BEGIN IMMEDIATE` commitment. [Database][database]
5. Deliver the result/card notification to B with a stable message ID and `resume:false`; record delivery only after acknowledgement. Replay can repeat delivery, never create another artifact. A crash after B completion but before A publication revalidates the recorded candidate; no regeneration. B’s success is execution success, not proof of publication.

This guarantees deduplicated canonical effects through transactions/constraints, not exactly-once provider consumption. Domain stages advance from receipts; the outbox transports intents/results and never reimplements OpenCode’s drain, child queue or retry loop.

**Minimum states and race outcomes.** A workflow needs `pending → active → ready`, plus `needs-attention` and terminal `cancelled`; reason codes distinguish invalid input, uncertainty, exhausted budget and failure. Retain validated slots through interruption. Execution is a projection of OpenCode running/stopping/settled outcomes; track settlement separately from the durable cancellation decision.

Cancel increments A’s epoch transactionally, rejecting further child admission and dispatch. Trusted workflow/epoch metadata identifies descendants; the host interrupts them and reconciles until settled. Cancel-first rejects late effects; publication-first returns the committed version, never “cancelled.” Delete/disable/revision changes use the same publication fence. Closing an observer does not cancel; host shutdown suspends execution without authorising more generation. A late child notification cannot restore a revoked permit. [Execution][execution], [completion][completion]

**Material parent-draft corrections / next wave.** Treat descendant cancellation as a requirement, not upstream behavior; separate ID uniqueness from payload comparison; distinguish existing domain receipts from proposed workflow/outbox tables. SDK host starts recovery automatically after plugin registration, so F0 must install the permit gate and a recovery hold before it can resume billable work. Verify this through the service-replacement seam; do not rebuild recovery. M4/integration minimally add stage receipts, atomic publication fencing and delivery reconciliation; M1/M6 and M7 consume them. [Host][host]

Unproved: selected-build Windows execution, recursive stop settlement, crash boundaries across both databases, pre-recovery gating, DST/catch-up correctness and 5/10/20 assembly. Next wave should fault-inject those specific boundaries with scripted inference; no further framework comparison is needed.

**Checks executed.** Seven existing tests passed in **33.65s**, with one Starlette/httpx deprecation warning. Synthetic profiles/providers/fetchers only; no installs, services, live auth or providers. Exact command (both `PYTHONDONTWRITEBYTECODE=1` and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`):

```powershell
& 'C:/Renulus/dev/python/Scripts/python.exe' -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -q tests/assessment/test_generated.py::test_approved_seam_separate_scoring_assistance_restart_and_idempotent_generation tests/assessment/test_generated.py::test_source_revision_change_aborts_generated_publish tests/assessment/test_assessment.py::test_evidence_failure_rolls_back_score_answer_exposure_and_retry tests/assessment/test_assessment.py::test_parallel_answer_retries_commit_exactly_once tests/updates/test_scheduling.py::test_cancel_before_first_task_step_does_not_leave_running_record tests/updates/test_scheduling.py::test_abrupt_restart_marks_unfinished_evidence_and_preserves_retry_delay tests/updates/test_scheduling.py::test_offline_retries_are_capped_and_success_evidence_is_retained
```

Eight static source assertions passed: foreground stop, global observer, notification-before-marker-removal, durable restart budget, exact-ID parent cancellation, replay wake, inbox matching and plugin-before-recovery order. Fourteen cited local source/spec/test files matched HEAD via `git diff --exit-code HEAD -- <paths>`. These checks establish legacy behavior and source structure, not the proposed integration.

[package]: https://registry.npmjs.org/@opencode%2Fsdk/2.0.26
[parent]: ../../planning/OPENCODE_V2_INTEGRATION_PLAN.md#deterministic-workflow-and-recovery-contract
[generated]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/assessment/generated_repository.py#L228
[streaming]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/assessment/generated_streaming.py#L222
[limits]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/assessment/generated_contracts.py#L9
[reviewed]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/assessment/repository.py#L251
[outbox]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/updates/reviews.py#L51
[consumer]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/knowledge/source_status.py#L242
[sources]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/updates/service.py#L97
[publications]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/updates/publications.py#L115
[schedule]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/updates/scheduling.py
[subagent]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/tool/plugin/subagent.ts#L200-L255
[observer]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/subagent-job.ts#L20-L67
[completion]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/subagent-completion.ts#L21-L45
[execution]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/execution.ts
[restart]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/execution/restart.ts
[retry]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/runner/retry.ts#L42-L90
[design]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md
[inbox]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/inbox.ts#L154-L201
[prompt]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/session.ts#L145-L175
[database]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/storage/database.py#L44
[host]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/src/internal/host.ts#L25-L56

