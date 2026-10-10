# OpenCode v2 integration investigation

2026-10-10. Research, validation and planning only. The user explicitly selected
OpenCode v2 and requested at least six adaptive waves of at most six agents each.
No product implementation, live provider use or deployment is part of this run.

Start with the [integration plan](../../planning/OPENCODE_V2_INTEGRATION_PLAN.md).
The [side-chat findings](../2026-10-10-pi-opencode-v2-side-chat-findings.md) and
earlier thirty-agent comparison are inputs; their earlier undecided/Pi statuses
do not override the user's later OpenCode selection.

## Evidence discipline

- Earlier research source: `528025ff0b22477c12ee1512e0e7d15297a6e888` (waves 1–2).
- Current committed Design C source: `76cfdff23e259700bec820e174c200540c7c1e1b`
  (wave 3 delta and wave 4 focused tests). A frozen committed source copy under
  ignored `.local/research` isolates tests from the active integration worktree.
- OpenCode source candidate: `4b6fea2875e4f2e3e8a8fee181803e54f7056845`.
- Published SDK 2.0.26 and tag `9b4ec5714d481559990db0a816d5dec19541a814`
  are distinct evidence targets; their startup ordering differs from the source.
- Existing behavior tests, static assertions, mathematical simulations and
  proposed integration acceptance are labelled separately. Agent count is a
  review process, not a measurement of correctness.
- The full OpenCode/Renulus integration has not been executed. Exact selected
  account capabilities, model quality and packaged Windows behavior need the
  implementation gates described in the plan.

## Adaptive wave ledger

| Wave | Why selected | Agent memos |
| --- | --- | --- |
| 1 | Establish actual reuse, memory behavior, artifact identity and customization/routing surfaces from the side-chat | [Current integration](w1-01-current-integration.md), [memory](w1-02-memory.md), [artifact/host](w1-03-artifact-host.md), [extensions](w1-04-extensions.md), [model routing](w1-05-model-routing.md) |
| 2 | Wave 1 found stale memory recapture, non-atomic reload, stale approvals, automatic recovery and auxiliary model routes | [Dependency lineage](w2-01-memory-dependencies.md), [dispatch/recovery](w2-02-dispatch-recovery.md), [workflows](w2-03-workflows.md), [context](w2-04-context-integration.md), [configuration/revocation](w2-05-configuration-revocation.md) |
| 3 | Challenged host composition, model evidence, migration and minimality; discovered the newer active Design C baseline | [Migration/retention](w3-01-migration-retention.md), [capabilities](w3-02-capabilities-evaluation.md), [current-work/minimality](w3-03-minimality-design-c.md), [host adversary](w3-04-host-proof-adversary.md) |
| 4 | Current Design C already implements jobs, conversation retention and typed restore; revalidate old defects and precise adaptation seams | [Current memory](w4-01-current-memory.md), [current workflows](w4-02-current-workflows.md), [current conversations/restore](w4-03-current-conversations.md) |
| 5 | Wave 4 reproduced recapture, deleted-draft residue and a generation retrieval failure; review the resulting prerequisite, lifetimes, role/context claims and ticket graph | [Ticket review](w5-01-ticket-review.md), [IPC/lifetimes](w5-02-ipc-lifetimes.md), [route/context](w5-03-route-context-audit.md), [independent defect verification](w5-04-current-defect-verification.md) |
| 6 | Wave 5 found two unowned producers, an oversized conversation slice, worker-lifetime/IPC hazards and optional-tree ambiguity; verify their closure in the revised 25-slice plan | [Completeness](w6-01-completeness.md), [lifecycle closure](w6-02-lifecycle-closure.md), [fact/evidence](w6-03-fact-and-evidence.md), [minimality/routing](w6-04-minimality-routing.md); all complete, final narrow corrections rechecked |

All six waves are complete. Later waves were selected from the preceding findings,
including the current-branch discovery and reproduced defects. See the
[finding dispositions](findings-disposition.md), [source reference map](current-source-map.md)
and agent identities below. The final review closes planning gaps only; every
runtime, account, migration and delivery gate remains explicit implementation work.

## Executed evidence summary

| Check | Result | Scope/qualification |
| --- | --- | --- |
| Earlier-snapshot Learn subscription cancellation | 14 passed | Existing real domain/HTTP seams with synthetic responses; no OpenCode execution |
| Earlier-snapshot memory repository/service/API/capture/Learn context | 59 passed | Existing scoped synthetic tests; controlled generation/embeddings where specified |
| Real Mem0/Qdrant/FastEmbed | 2 passed | Public helper assets, synthetic profiles, mocked generative extraction; initial fixture-path setup errors retained in memo |
| Current image/context suite, system Python | 7 passed, 13 failed | Missing declared ruamel dependency; not thirteen established product defects |
| Same suite, managed Python | 19 passed, 1 failed | Remaining post-401 capability/availability expectation mismatch |
| Article interval simulation | 20,001 correct merge states; wrong age formulation matched 481 | Mathematical bookkeeping only, no summary quality/cache/runtime claim |
| Existing Node SQLite primitive | Passed on Node24.15.0 win32 x64 | In-memory SELECT; setReadBigInts and setReturnArrays exist; not selected24.21.0/full host proof |
| Public artifact integrity | Five SRI comparisons passed | Downloaded tarballs inspected in memory; no imports/install/build; not full cohort reproducibility |
| Model selection cases | 9 passed | Isolated AST-extracted functions with synthetic configuration |
| Four stale-memory recapture cases | Reproduced at both baselines | Current service/worker and real SQLite with deterministic inference/index doubles; not an OpenCode execution |
| Current typed restore/deletion helpers | 8 comparative assertions passed | Old generic cascade cases fixed at current source; helper-only proof |
| Both providers' post-401 status | Reproduced by isolated unchanged methods | Four relevant files byte-identical at current source; no live account request |
| Recovery child-cleanup predicate | 4 synthetic SQLite assertions passed | Demonstrates predicate can clear a fresh foreground child; not an executed runtime race |
| Current memory regression selection | 80 distinct cases passed within this lane | Twelve initial Qdrant path/cleanup failures resolved by shorter owned synthetic-profile paths; exact threshold unproved |
| Current conversation/retention selection | 25 passed, 25 deselected | Scripted providers; saved/temp/promotion/epochs/typed restore; overlaps some other lane coverage |
| Deleted draft receipts/export | Reproduced for learning and case | Current owners deleted/tombstoned but prior receipt text/hash remains in fresh export |
| Current saved-generation/Home/nightly selection | 8 passed, 16 failed | Shared retrieval calls missing guard_run; direct provider-free reproduction; generation-dependent downstream assertions not established |
| Current frozen source identity | 365 blobs matched | Git-byte comparison of runtime, tests and pyproject at the current commit |
| Current image/context repeat | 19 passed, 1 failed | Current frozen source, synthetic HTTP; same post-401 availability discrepancy |
| Current IPC-adjacent domain regression selection | 18 passed, 50 deselected | Existing memory/conversation/policy/Study-help behavior; no actual cross-process OpenCode proof |
| Memory close/settlement probe | Lifetime gap reproduced | close returned while controlled extraction thread still ran and recovery guard admitted; no late facts observed |
| Generation failure independent checks | Direct helper and selected service test reproduced | Missing guard_run; zero synthetic transport calls; downstream assertions not reached |
| Upstream source assertions | Recorded in lane memos | Static source behavior assertions, not runtime acceptance |

The [parent context memo](parent-context.md) records the immutable article URL,
hash, probe and context design. Each lane records its exact commands, outcomes,
warnings, failed setup attempts and limits. Do not combine these categories into
an undifferentiated integration pass count.

## Agent identities

Final parent validation: all 25 wave memos exist and all agents are closed;
three spec templates contain 56 user stories; 25 ticket files have 53 blocking
edges, zero missing targets/cycles and 22 transitive default-cutover prerequisites.
Optional H11/H19 are excluded from that frontier. All 29 source-map hashes,
byte counts and line counts match raw Git source. `scripts/check_workspace.py`
passed with 18,322 public files and 1,786 local links; `git diff --check` passed.
Only documentation and owned ignored research/probe artifacts were changed.
No product repair, OpenCode execution, live inference, installation or deployment
was performed. The review question for skill-required publication remains pending.

The earlier thirty-agent comparison is historical input. This request added six adaptive waves with 25 subagents (5, 5, 4, 3, 4, 4); no wave exceeded six. All completed and were closed. Completion describes research memos, not product implementation.

| Wave | Agent | ID | Memo |
| --- | --- | --- | --- |
| 1 | Meitner | `01a126c2-a47d-7942-8ddb-b1dfd7cadf9c` | [w1-01-current-integration](w1-01-current-integration.md) |
| 1 | Dewey | `01a126c2-a68a-7e82-bea4-ac1e32f64a9d` | [w1-02-memory](w1-02-memory.md) |
| 1 | Kant | `01a126c2-aac6-7030-85d6-22817e88a9f5` | [w1-03-artifact-host](w1-03-artifact-host.md) |
| 1 | Fermat | `01a126c2-b0f6-7eb2-af78-b3e5c4840156` | [w1-04-extensions](w1-04-extensions.md) |
| 1 | Mill | `01a126c2-b7d3-7c21-8241-45aae9fa1492` | [w1-05-model-routing](w1-05-model-routing.md) |
| 2 | Jason | `01a126ca-b692-7a21-b2f2-c3c3073fe764` | [w2-01-memory-dependencies](w2-01-memory-dependencies.md) |
| 2 | Feynman | `01a126ca-b87c-72c1-87af-0917cb494f21` | [w2-02-dispatch-recovery](w2-02-dispatch-recovery.md) |
| 2 | McClintock | `01a126cb-0eab-7a40-92fd-67d23cfc66a4` | [w2-03-workflows](w2-03-workflows.md) |
| 2 | Einstein | `01a126cb-101c-74f2-8be5-aad48d543c80` | [w2-04-context-integration](w2-04-context-integration.md) |
| 2 | Curie | `01a126cb-11f6-7602-800c-1d151227fa1f` | [w2-05-configuration-revocation](w2-05-configuration-revocation.md) |
| 3 | Singer | `01a126d3-2954-7303-bda4-379abec5082b` | [w3-01-migration-retention](w3-01-migration-retention.md) |
| 3 | Erdos | `01a126d3-2c65-7500-a69e-783d6f2ec3b8` | [w3-02-capabilities-evaluation](w3-02-capabilities-evaluation.md) |
| 3 | Epicurus | `01a126d3-2e40-7df3-8849-5d2c5631e47d` | [w3-03-minimality-design-c](w3-03-minimality-design-c.md) |
| 3 | Dirac | `01a126d3-c597-70e0-8919-f75f83c89cae` | [w3-04-host-proof-adversary](w3-04-host-proof-adversary.md) |
| 4 | Aristotle | `01a126db-eff0-75b0-9adf-20224223ac2e` | [w4-01-current-memory](w4-01-current-memory.md) |
| 4 | Hilbert | `01a126db-f21f-7082-a099-51f41148dcb2` | [w4-02-current-workflows](w4-02-current-workflows.md) |
| 4 | Herschel | `01a126db-f3fd-7b92-ae80-2e1ddbd2b9fc` | [w4-03-current-conversations](w4-03-current-conversations.md) |
| 5 | Maxwell | `01a126e5-7192-7b90-946f-0cf2d567f91d` | [w5-01-ticket-review](w5-01-ticket-review.md) |
| 5 | Lovelace | `01a126e5-7307-7f93-95c4-0cb1fbd5e258` | [w5-02-ipc-lifetimes](w5-02-ipc-lifetimes.md) |
| 5 | Faraday | `01a126e5-74e8-7880-a5aa-07d0c7ada4bc` | [w5-03-route-context-audit](w5-03-route-context-audit.md) |
| 5 | Mendel | `01a126e5-78a1-7563-a743-58eac01cf012` | [w5-04-current-defect-verification](w5-04-current-defect-verification.md) |
| 6 | Newton | `01a126f0-0319-7f40-b156-5e51fd1eff0f` | [w6-01-completeness](w6-01-completeness.md) |
| 6 | Bohr | `01a126f0-0c1a-70c3-99ed-0494361eb264` | [w6-02-lifecycle-closure](w6-02-lifecycle-closure.md) |
| 6 | Avicenna | `01a126f0-3001-7cc1-94c0-2d10ca247b42` | [w6-03-fact-and-evidence](w6-03-fact-and-evidence.md) |
| 6 | Peirce | `01a126f0-3cbb-7bf1-9cca-b633d0e0276e` | [w6-04-minimality-routing](w6-04-minimality-routing.md) |

