# H06 criterion evidence map

October 11, 2026. **H06 connected acceptance remains open.** This map is pinned
to committed integration `4ce4ab17a979ad58656c8e21959d414a40cbd8b4`; it records
existing source and retained receipts, without new tests or provider calls.
Parent migration/continuation work after that checkpoint is not accepted here.

## Subsequent connected checkpoint

The parent Owner assembly now has owner-final01.xml:6 passes/89.295s and
local-affected01.xml:50 passes/36.520s, both with zero failures/errors/skips,
under G:/Renulus-agent-scratch/oc-h02-h08/saved-migration/receipts/.
This newer scope supersedes the historical prepare_in refusal described
below, without upgrading unrelated old receipts or closing H06 prematurely.

| Criterion | New connected evidence | Remaining closure |
| --- | --- | --- |
| C1 | Actual production-main stable mapping, zero-inference conversion, retained stage acknowledgement, ordinary native continuation and fresh-generation reopen | Frozen assembly review and bounded transfer-capacity disposition |
| C2 | Actual migrated Archive/restore/project/draft, Stop with retained settlement, saved observer disconnect and exact neutral status under a real active Test | Hidden desktop flow through the existing facade |
| C3 | Original legacy IDs/text/citations remain public; imported aliases are unknown/ineligible and absent from the next manifest | Frozen assembly review and desktop history/reader observation |
| C4 | Genuinely migrated populated owner deletion, project survives, native replies forgotten and no new inference; earlier command/export deletion evidence retained | Final criterion review, retaining independently owned originals/learning boundaries |
| C5 | Retired original create denied after native reopen; lost-purge-ACK independent closure already complete | Real pre-producer legacy crash/orphan proof in assigned test-only lane |
| C6 | Saved-only routing preserves the existing temporary owner | H21 remains separate; no new temporary runtime is claimed |

Native child assembly969ac780 is not integrated during these checks. Its
subagent changes require a newly observed final registry artifact; these
H06 receipts retain their two-Library-tool native registry.

The authoritative requirements are [H06](../planning/opencode-v2/tickets/06-continue-saved-and-temporary-chats-through-one-owner.md),
[S2](../planning/opencode-v2/specs/02-memory-context.md) and
[S3](../planning/opencode-v2/specs/03-workflows-migration.md).
[H06 contracts](OPENCODE_H06_MIGRATION.md) supplies the underlying interfaces;
the [H02–H08 ledger](OPENCODE_H02_H08_HANDOFF.md) records local H02–H05 readiness.
This document does not change ticket checkboxes or supersede later acceptance.

## Criterion disposition at the committed checkpoint

Evidence identifiers below refer to the receipt index in this document.

| H06 criterion | Demonstrated scope | Remaining acceptance |
| --- | --- | --- |
| C1. Stable saved-history migration, paired stores, zero generation and one transcript writer | E1–E5 demonstrate supported native transfer, exact original-row snapshots, frozen aliases/digests, supplied-transaction journal reservation/activation, rollback, immutable source checks and one claimed import. | **Open connected.** Compose the genuine legacy owner, active paired selection, journal and actual host transport through the existing public conversation flow. Prove one stable active mapping after import acknowledgement loss/reopen and no competing legacy writer. Standalone capabilities and scripted transfer do not prove this composition. |
| C2. ConversationStreams/sidecar identity, Archive, project membership, drafts, saved-disconnect continuation, explicit Stop and neutral status under active Test | E3 pins owner/draft state; E4 freezes project/policy/context/deletion pins. E7–E9 exercise deletion observation, ingress sealing and native lifecycle replacement. | **Open connected.** Each named behavior must be proved after genuine legacy migration. Deletion-observer cancellation is not explicit Stop during a migrated turn; live host status is not neutral conversation status under active Test. Existing Design C behavior remains a regression obligation. |
| C3. Read-only legacy history/citations and unknown-lineage exclusion | E1/E2 preserve exact retained history and citations; E4 preserves terminal partial text and original outcomes. Migration references explicitly have unknown lineage and false context/capture eligibility. | **Bounded transfer/exclusion contract verified; connected context remains open.** Prove migrated public history/reader projection, original citations and a follow-up dispatch that excludes imported unknown assistant/user/tool context. Imported timestamps cannot qualify M5 capture. H05 capture for independently verified new publications is a separate path. |
| C4. Transactional owner/receipt deletion, including creation receipts targeting new; clean new exports | E5/E6 capture independent purge coordinates before owner cascades, retire canonical payload-bearing commands in the owner transaction, retain opaque tombstones and exclude deleted title/draft/request digests from new records exports. E7–E9 prove actual native deletion and settlement for newly created saved native owners. | **Bounded local deletion/retirement verified.** Keep deletion of a genuinely migrated populated owner, shared-original/independently retained-learning preservation and project/owner cascade coverage open. Native projection absence does not establish physical SQLite/WAL, backup or source-file erasure. |
| C5. Opaque terminal-unavailable replay, no repeated effects; legacy orphaned runs remain interrupted | E6 rejects changed-payload and temporary-branch creation replay before recreating an owner. E7–E9 erase deleted-operation reply records, preserve unrelated observations, reject native recreation in the original/new generation and reconcile missing acknowledgement without another remove. | **Bounded replay contract verified.** Retain an explicit imported legacy orphan/interrupted-receipt proof and the populated migration/recovery matrix as open. Records-only old-export reconciliation is narrower than H18 paired restore and deletion-frontier recovery. |
| C6. Temporary execution remains with its existing owner until H21 | Saved migration rejects non-saved/non-learning owners. This slice creates no temporary runtime graph or promotion path. Existing temporary deletion cases appear only as affected regressions in E6. | **Boundary retained, not H21 acceptance.** Volatile derivatives, temporary disconnect/discard and cross-store Save/promotion require H21's own freeze/settle/stage/map/activate/retire proof. |

At this checkpoint, `HarnessBridge.prepare_in` still refuses any retained
`learn_messages` row with `harness_history_requires_migration`. The committed
snapshot, migration coordinator and transfer ports therefore must not be
described as already permitting legacy continuation. Unknown lineage is not an
empty valid dependency closure, and structural imported completion is not a
CompletedAnswer publication.

## Committed source anchors

| Component | Committed source and checkpoint |
| --- | --- |
| Native bounded stage/import/readback/remove/retire | [session-transfer.ts](../../packages/harness/src/session-transfer.ts), integrated `93c6c7cedb83074206557f200ba7ee9abc66fbe8` from `ab96a2f30e1b504e48a3af0836cfdc01f44cddab`; [dedicated native tests](../../packages/harness/test/session-transfer.test.mjs) |
| Canonical coordinator and assistant outcome producer | [harness_migration.py](../../runtime/renulus/learn/harness_migration.py), compatibility `5b09231e211f5ad56d85bec5da1990e7ad189a19`; [coordination tests](../../tests/learn/test_harness_migration.py) |
| Actual saved original-row snapshot/current check | [harness_saved_history.py](../../runtime/renulus/learn/harness_saved_history.py), `c0d74e2b79468e7a06ab4faa52703d81c63f64fe`; [snapshot test](../../tests/learn/test_harness_saved_history.py) |
| Learn004 migration/purge journal | [harness_migration_journal.py](../../runtime/renulus/learn/harness_migration_journal.py), foundation `740fbe2e83e036d5dfa9fc6a686f1fd47d038855` plus repairs through `0a4c4db15696647b362cb52d1a22ff40894e814c`; [journal tests](../../tests/learn/test_harness_migration_journal.py) |
| Python authenticated transfer adapter | [harness_saved_transfer.py](../../runtime/renulus/runtime/harness_saved_transfer.py), `e76ddbceae4cf70ad02043f66e75337ad8cc4001`; [adapter tests](../../tests/runtime/test_harness_saved_transfer.py) |
| Canonical command retirement/export/replay | [conversation_repository.py](../../runtime/renulus/learn/conversation_repository.py), [Learn005](../../runtime/renulus/learn/migrations/005-command-retirement.sql), [public API tests](../../tests/integration/test_conversation_command_retirement.py); `17acab888d07e71d7f636677a1cfabfda8a7636f` and subsequent deletion integration |
| Native deletion, retained gate and shutdown | [harness_learning.py](../../runtime/renulus/runtime/harness_learning.py), `0a4c4db15696647b362cb52d1a22ff40894e814c`, `7b65c43773a08311765c8fadc3df04dabbceb3bc`, `b5c92a4d8fa784e97c8ff5896f0517c33cb06288`; [deletion tests](../../tests/runtime/test_harness_learning_deletion.py) |
| Lost-removal-acknowledgement tracer | [purge reconciliation test](../../tests/runtime/test_harness_learning_purge_reconciliation.py), `4ce4ab17a979ad58656c8e21959d414a40cbd8b4` from `d62a93394ed4aaa613e08fce2816a6ac292aa144` |

## Retained receipt index

These are separate, overlapping runs. Counts are not summed into a suite. Receipt
outcomes were read for this map; no check was rerun. All listed successful runs
have zero failures/errors/skips; the native Node run also records zero cancelled
tests. Durations use retained suite time, or the Node reporter's total duration.
Each receipt demonstrates its recorded source/fixture version. Inclusion of the
producer at this checkpoint does not imply a fresh rerun of every earlier case
against `4ce4ab17`.

Receipt roots:

- **N:** `G:/rh06/native-transfer/receipts/`
- **L:** `C:/Renulus/scratch/oc-h02-h08/learning/`
- **D:** `G:/Renulus-agent-scratch/oc-h02-h08/native-deletion/receipts/`
- **R:** `G:/Renulus-agent-scratch/oc-h02-h08/command-retirement/`
- **A:** `G:/Renulus-agent-scratch/oc-h06/purge-reconciliation/receipts/`

| Evidence | Exact retained result | Public seam and qualification |
| --- | --- | --- |
| E1. Native transfer | **N/affected-green02.xml: 22 passed, 4.884s.** Individual red/green pairs include outcomes, lost-ack, purge, current, cleanup and inspection. | Actual pinned SDK/SQLite, supported sessions ports, explicit synthetic roots and denied/counting LLM. Every fixture closes with zero inference. SDK runtime reopen here occurs within one OS process. Bounds, byte-exact readback, poisoned text/citations, retained template cleanup and opaque retirement are adapter proof, not mapped conversation acceptance. |
| E2. Earlier native capability/reopen | `C:/Renulus/scratch/oc-h02-h08/conversations/h06-native-isolated.xml`: **1 passed, 20.313s**; earlier `h06-native-final.xml`: **1 passed, 16.867s**. | [Capability test](../../tests/learn/test_harness_migration_contract.py) imports, reopens and removes via separate native child processes, all reporting zero inference. It predates the final logical transfer contract and does not activate a canonical migration mapping. Original legacy reads remain unchanged. |
| E3. Real canonical snapshot | **D/snapshot-green01.xml: 1 passed, 5.897s.** `snapshot-red01.xml` is a missing-module/interface red. | Genuine public legacy publication, supplied canonical transaction, exact public message IDs/text/times and terminal run timestamp, draft pin and stale revision rejection. This is not native conversion or reader/continuation proof. |
| E4. Terminal legacy outcomes and coordinator | **L/h06-partial-red01.xml: 4 failed, 1.108s → h06-partial-green01.xml: 4 passed, 0.588s.** **h06-partial-affected01.xml: 23 passed, 1.590s.** | Real SQLite with injected canonical/native protocol adapters. Completed/cancelled/failed/interrupted partial history retains exact text, citations, original times and outcome; references stay unknown/ineligible. Unknown outcomes and unresolved timestamps refuse before stage. Lost import acknowledgement, immutable pins, readback defects and rollback are coordination proof, without real SDK/IPC composition. |
| E5. Canonical journal | **D/journal-red04.xml: 2 failed, 8.292s → journal-green04.xml: 4 passed, 16.457s.** | Public original Database/Services plus supplied-connection journal. Reservation rollback even when the caller catches conflict, complete mapping engine/cohort validation, activation/reopen and purge coordinates surviving owner cascade. Metadata alone cannot prove native removal. |
| E6. Canonical retirement/export/replay | **R/final01.xml: 7 passed, 28.390s**; **restore02.xml: 1 passed, 5.695s**; **retired-conflict01.xml: 1 passed, 6.285s**; **temporary-green01.xml: 1 passed, 6.934s**. | Public HTTP owner deletion, records export/reopen, changed-payload/temporary replay returning `command_terminal_unavailable`/410, and existing rollback/temporary/surviving-owner regressions. Records-only older restore cannot reintroduce retired commands. No native purge, physical erasure or full paired restore follows from this run. |
| E7. Native deletion/replay/restart/observer gate | **D/red01.xml: 1 failed, 16.977s** reproduces canonical deletion leaving native history. **native-green01.xml: 1 passed, 15.762s**; **final02.xml: 3 passed, 47.301s**. Component receipts include retirement-green01 (**1/16.415s**), restart-green01 (**2/28.732s**) and cancel-green01 (**1/17.774s**). | Actual production main/SDK/private IPC/SQLite; synthetic account/deployment and one loopback setup dispatch, zero further deletion dispatches. Both ConversationRepository and LearnService deletion routes remove a newly created saved native session. Deleted reply observations are forgotten; unrelated observations survive; retired create cannot recreate the session after native process replacement. Observer cancellation holds an actual request's result observation, not a native resource finalizer. |
| E8. Failure-safe actual shutdown | **D/shutdown-red01.xml: 1 failed, 17.018s → shutdown-green01.xml: 1 passed, 17.120s.** | A terminal purge failure no longer prevents close from cancelling/settling an unrelated actual execution held at synthetic loopback HTTP. Native process/pipe, Domain and Registry ownership settle; repeated close stays stopped. The durable pending purge is retained, not declared removed. |
| E9. Lost purge acknowledgement | **A/red03.xml: 1 failed, 21.409s → green01.xml: 1 passed, 21.579s**, unchanged test SHA256 `0203a7bfe1bf83cc7ff10e6a317fe6fcf79e784ad4d1d3f761d6478ae8485010`. | Actual production main/SDK/IPC/canonical owners; the observer hides only the acknowledgement after real removal. Authenticated originating `session.find` changes from exact one session to none. Reconciliation sends no second remove, retires the originating operation, marks the journal removed and releases the deletion seal. Fresh native-process generation rejects recreation; the canonical Services instance is retained. One setup dispatch, zero added sends/permits; actual transport finalizers and native exit/pipe settlement are observed. [Tracer handoff](G:/Renulus-agent-scratch/oc-h06/purge-reconciliation/HANDOFF.md) records exact command/provenance. |
| E10. Python transfer protocol | **L/h06-transfer-final02.xml: 46 passed, 3.764s.** | Injected public process transport, exact authenticated target/generation, bounded chunks, retained request identity after timeout/cancellation, strict readback and acknowledged observation release. This does not prove live native transport/host assembly. Later follow-on receipts do not upgrade source at this checkpoint. |

E9's first two failures are fixture qualifications: `A/red01.xml`
(1 failure, 27.742s) assumed a top-level native message role; `A/red02.xml`
(1 failure, 20.283s) assumed every transcript ID belonged to the selected answer.
Both precede deletion and are not product red proofs. E9 red03 instead reaches
reconciliation and fails on two removes rather than one.

Other retained qualifications remain visible: R/red01 is setup failure;
R/restore01 is an incorrect count assertion; D/cancel-red01 is cancellation
sequencing/revision mismatch. N/import-red01 is missing public interface,
N/import-green01 is unsupported fixture TypeScript syntax and
N/conflict-green01 is an intermediate location-shape assertion failure. None
is silently relabelled as a meaningful behavior red or successful run.

## Open connected work and excluded evidence

The next H06 proof must use the existing saved public facade to migrate actual
legacy rows once, preserve immutable legacy reads/citations/partial outcomes,
reconcile the exact map after uncertain acknowledgement, and continue using the
same native transcript owner. Follow-up context must exclude unknown imported
history while admitting only independently verified new publication lineage.
Archive, project membership/moves, drafts, saved observer disconnect, explicit
Stop and active-Test neutral status require their own connected assertions.
Deletion must also cover the resulting populated migrated owner and independent
Library originals/retained-learning rules.

The newer `G:/Renulus-agent-scratch/oc-h02-h08/saved-migration/receipts/` work is
outside the pinned composition. Its filenames do not establish success:
`owner-green01.xml` records 1 failure/15.324s; `owner-green02.xml` records
1 pass/15.207s, but is not promoted to committed-checkpoint acceptance here.
`continue-green01.xml` records 1 failure/17.400s and
`continue-diagnostic01.xml` records 1 failure/18.793s. Parent source/test WIP
and subsequent transfer fixes remain excluded until published, reviewed and
paired with exact connected receipts.

No new source edits, tests, descendants, live account calls, engines, installs or
desktop journey were performed to create this map. The accepted pinned cohort
remains OpenCode source `4b6fea2875e4f2e3e8a8fee181803e54f7056845` with Node
26.4.0. Synthetic dispatch proves coordination/accounting at the declared seam,
not real subscription access, model quality, TLS deployment or packaged/native
installation. H18 owns the full paired restore/deletion-frontier matrix; H21
owns temporary execution and cross-store Save; H20 owns final release/cutover.
