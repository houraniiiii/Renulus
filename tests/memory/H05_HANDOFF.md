# H05 memory owner handoff — 2026-10-11

Checkout: `C:/Users/karol/.codex/worktrees/oc-memory/repo`; branch:
`codex/oc-memory-h05-support-lineage`; baseline:
`74e3424b5c03ac4616834911c13faef1c064d09c`. Local commits only, no push.

Current-owner commit: `433ac1655fbcbe6c4eff6ec79a320da953a95ddc` (13 owned paths).
The native follow-up is a separate coherent commit recorded in the final handoff
and the scratch commit/receipt ledger.

## Owned closure

Persistent reference-only answer lineage and support groups extend the existing
`Dependency`, `EligibleInput` and `Identity` contracts. Joint inputs require every
root; independent groups are alternatives. Echo captures inherit ancestor roots
and cannot become independent through a new answer identity. Corrections create
independent user support, direct deletion overrides support, and revoked support
stays terminal across scans/reopen. Unknown legacy answers remain readable but
cannot automatically seed memory.

`runtime/renulus/memory/migrations/002.sql` is additive. Applied `schema.sql` is
unchanged. Existing facts backfill profile-global retained support. New project
records use explicit ownership in deduplication and recall; moving history does
not relabel them. `group_id` is globally unique. Storage ownership is exactly
`memory_support_groups.record_id -> memory_facts.id` and
`memory_support_inputs.group_id -> memory_support_groups.group_id`. Answer lineage
is retained reference support, **not storage-owned by evidence**. Ordinary chat
deletion blocks unavailable history while preserving disclosed retained learning.
Explicit delete-related learning must revoke its truth support through M5.

Production migration registration, backup/restore inventories/relations and Learn
publication belong to integration. Synthetic publication fixtures are explicitly
labelled; they do not prove a production native resolver round trip.

## Public extension seam

```python
class AnswerInputs(BaseModel):
    version: int = 1
    inputs: tuple[EligibleInput, ...] = ()
    dependencies: tuple[Dependency, ...] = ()

memory.publish_answer_lineage_in(
    conn, evidence_id, *, inputs, dependencies=(), project_id=None
) -> str  # immutable publication_digest
memory.eligible_history(messages, *, project_id=None)
# -> filtered original dictionaries, tuple[EligibleInput, ...]
memory.register_dependency_resolver(target_type, resolver)
memory.retrieve(query, *, scope, limit=10, budget_chars=4000,
                topic_id=None, project_id=None)
memory.add(request, *, project_id=None)
```

`AnswerInputs` is frozen, forbids extra fields, and bounds each collection to 100.
Local adapters implement `resolve_dependency_in(conn, dependency, *, project_id,
for_support) -> AnswerInputs`. They synchronously validate canonical receipts;
empty closure attests an eligible independent root. They do not resolve bytes or
perform IPC. Unknown types fail closed. Bind adapters in
`services.registry['memory_dependency_resolvers']` **before constructing memory**
on reopen, because construction reconciles support. Built-in memory/answer
validators cannot be replaced. Publication persists expanded typed ancestors.

The async `services.registry['completed_answer_resolver']` implements
`resolve_completed_answer(reference)` and returns immutable
`{text, digest, publication_digest, input: AnswerInputs JSON}`. Byte resolution
runs outside canonical transactions and physical locks. Commit rechecks local
support/publication, and legacy bytes use local SQL equality only. H24's single
worker, admission, thread lease and finalizer settlement remain intact.

Conversation/source adapters may treat only the exported
`renulus.memory.lineage.INELIGIBLE_LINEAGE_CODES` as stale/unknown:

```text
memory_dependency_revoked, memory_lineage_unknown, memory_dependency_unknown,
memory_project_scope, memory_lineage_cycle, memory_lineage_conflict,
memory_capture_suppressed, memory_scope_excluded, memory_answer_unavailable,
memory_answer_reference, memory_evidence_deleted, memory_answer_version
```

Other `ApiError`s propagate. In particular, internal callback failures and
`memory_support_budget` cannot terminally revoke support or cancel a current
capture. Known source adapters translate stale/unknown revisions to the designated
codes, not arbitrary infrastructure failures.

## Reproducible validation

First red receipt: **`C:/Renulus/scratch/oc-h02-h08/memory/receipts/cycle01-red.xml`**.
All receipts and the machine-readable `receipt-ledger.json` are under
`C:/Renulus/scratch/oc-h02-h08/memory`. Commands run from the assigned checkout:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:RENULUS_MEMORY_HELPERS='C:/Renulus/dev/helper-assets'
& C:/Renulus/dev/python/Scripts/python.exe -B -m pytest `
  -p pytest_asyncio.plugin -p no:cacheprovider tests/memory tests/learn/test_discovery.py `
  --basetemp=C:/Renulus/scratch/oc-h02-h08/memory/owner-full-final `
  --junitxml=C:/Renulus/scratch/oc-h02-h08/memory/receipts/owner-full-final-green.xml -q
```

Final owner result: **166 passed, zero skipped**, 411.16 seconds. This includes
all dedicated memory tests, the three actual CPU engine tests and all 19
discovery tests. Memory Python syntax and `git diff --check` pass; the applied
memory-001 schema remains byte-identical to the baseline.

The source-only baseline confirmation uses the same pytest executable/plugins,
`tests/memory/test_support_lineage.py -k four_research_regressions`,
`-o pythonpath=C:/Renulus/scratch/oc-h02-h08/memory/baseline/runtime`,
`--basetemp=.../research-four-baseline-confirm2`, and
`--junitxml=.../receipts/research-four-baseline-confirm-red.xml`: **4 failed**
on actual stale recapture, no synthetic lineage injected into the baseline.

Selected retained red/green receipts:

| Behavior | Red | Verified green |
| --- | --- | --- |
| Four research regressions | `research-four-baseline-red.xml`, 4 failed | `research-four-current-green.xml`, 8 passed |
| Independent alternatives/last-root echo | `support-alternatives-baseline-red.xml`, 1 failed | `support-alternatives-current-green.xml`, 1 passed |
| Project publication | `cycle07-red.xml`, 4 failed | `cycle07-green-final.xml`, 4 passed |
| Scoped history | `cycle08-red.xml`, 1 failed | `cycle08-green.xml`, 5 passed |
| Unavailable history vs retained learning | `cycle09-red.xml`, 1 failed | `cycle09-green.xml`, 17 passed |
| Local resolver ancestry/reopen | `cycle11-red.xml`, 1 failed | `cycle11-green-final.xml`, 1 passed |
| Terminal source revocation | `cycle12-red.xml`, 2 failed | `cycle12-green.xml`, 2 passed |
| Bounded ancestry | `cycle13-red.xml`, 1 failed | `cycle13-green.xml`, 28 passed |
| Source check before recall/publication | `cycle14-red.xml`, 1 failed | `cycle14-green.xml`, 29 passed |
| Internal error cannot revoke learning | `cycle15-red.xml`, 1 failed | `cycle15-green.xml`, 30 passed |
| Internal error cannot cancel current capture | `cycle16-red.xml`, 1 failed | `cycle16-green.xml`, 31 passed |
| Discovery identity/revision fixture | `discovery-fixture-red.xml`, 3 failed | `discovery-fixture-green.xml`, 19 passed |

Actual Mem0/Qdrant/FastEmbed tests cover extraction, edit/delete, index erasure,
reindex and reopen. Provider generation is synthetic; public pinned CPU helpers
are real, manifest verified, and external sockets blocked. No live account or
paid provider is used. Whole-attempt restore fixtures now respect H24 admission
quiescence. The restart fixture calls the reopened public memory service; its
other variants retain HTTP endpoint coverage.

Failed intermediate broad receipts remain available: `memory-full-initial-red.xml`
(5 failed, 137 passed), `whole-attempt-final-green.xml` (despite its historical
name, **3 failed, 36 passed**), `restore-repair-green.xml` (despite its name,
**1 failed, 2 passed**), and `cycle11-green.xml` (1 failed). The ledger records
actual XML counts, not filename claims. No acceptance is based on these failures.

## Native receipt follow-up

The parent confirmed integration source `845c1f0c` (bridge source `378d9d9b`,
integrated `1631e767`). Native references accept exactly the bridge's
CompletedAnswer.reference() JSON, with no answer text:

~~~text
{version: 1, run_id, thread_id,
 runtime: {contract_version: 'harness/1', profile_id, store_id,
   engine: {name: 'opencode', version: '2.0.26',
     source_commit: '4b6fea2875e4f2e3e8a8fee181803e54f7056845'}, session_id},
 input_id, message_ids: [native assistant IDs], sha256,
 citations: [{content_ref?, passage_id?, document_id?, revision_id?, locator?}],
 inputs: [EligibleInput JSON], dependencies: [Dependency JSON]}
~~~

Runtime, content reference, locator, identifier and closure validation reuse
existing typed contracts. Collections are bounded to 100, native message IDs are
nonempty and distinct from the admitted input, and the reference is bounded to
64 KiB of JSON. Reference-only citations reject raw text and unknown fields.

The only submitted-state acceptance is inside trusted
`publish_answer_lineage_in(conn, ...)`. The same canonical transaction must:

1. Guard/check the admitted native request and its expected revisions.
2. Stage the exact immutable reference_json while the answer is still submitted.
3. Insert the reference-only eligible learning_evidence record.
4. Call memory publication with the exact reference inputs/dependencies and
   host-derived project_id. M5 validates the staged reference, current mapping,
   admitted input, running Learn run and absence of a previous publication digest.
5. Finalize learn_harness_answers to completed with M5's returned digest and
   finalize learn_runs in the same atomic transaction.

Rollback undoes both staging and M5 publication. Native history and capture
require completed answer/run states, exact mapping/reference/input and receipt
publication_digest equal to M5's local immutable publication. Unknown lineage
never becomes an empty independent closure.

~~~python
memory.eligible_answer_references_in(conn, references, *, project_id=None)
# -> tuple[EligibleInput, ...], completed references only; max 100 references
~~~

This callback performs local canonical validation only, with no IPC or answer
bytes. It returns evidence pins and filters only INELIGIBLE_LINEAGE_CODES; internal
errors propagate. eligible_history also checks the actual published message ID,
keeps original dictionaries, and deduplicates range-level evidence pins.

Explicit native capture resolves text/digest/publication_digest/typed closure
asynchronously before the canonical write. It hashes immutable resolved bytes
before entering commit and rechecks local receipt/lineage at commit. Native SQL
never reads transcript bytes. Without the async resolver it fails with
`memory_answer_resolver_unavailable` (503, retryable); this is an internal
availability error, not a stale/revoked eligibility code. Migrated automatic
enqueue remains explicitly disabled even with a valid native receipt.

Dedicated synthetic tests use the parent's exact shared 003 migration from the
composed source, with a git-show fallback to the confirmed integration commit in
this uncomposed lane. No parallel table schema is created. The tests cover staged
invisibility/completion, rollback, receipt/mapping/input/reference/digest mismatch,
typed unknown closure, automatic-capture exclusion, and a public writer progressing
during async resolution with canonical transcript-byte reads denied.

Native receipts: cycle17-red.xml (1 failed), cycle17-green.xml (32 passed with
lineage tests); cycle18-red.xml (1 failed), cycle18-green.xml (2 passed);
cycle19-red.xml (1 failed), cycle19-green.xml (53 passed with legacy producer and
lineage tests); native-validation-green.xml (15 passed); cycle20-red.xml
(1 failed, unrelated message-ID admission). All live under the same receipt root.

Final native follow-up verification: **163 passed, zero skipped**, 344.50 seconds,
including all dedicated memory tests and all three actual CPU engine tests:

~~~powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:RENULUS_MEMORY_HELPERS='C:/Renulus/dev/helper-assets'
& C:/Renulus/dev/python/Scripts/python.exe -B -m pytest `
  -p pytest_asyncio.plugin -p no:cacheprovider tests/memory `
  --basetemp=C:/Renulus/scratch/oc-h02-h08/memory/native-owner-final `
  --junitxml=C:/Renulus/scratch/oc-h02-h08/memory/receipts/native-owner-final-green.xml -q
~~~

This final receipt closes cycle20's unrelated-message regression. Source/test
syntax and whitespace checks pass. No shared contracts, storage/Services, host,
dependency locks, applied memory schema or tickets/status were changed. Native
follow-up leaves the additive migration exactly as committed in 433ac165.

## Changed paths across the two owner commits

All paths are relative to the assigned checkout above:

~~~text
runtime/renulus/memory/lineage.py
runtime/renulus/memory/migrations/002.sql
runtime/renulus/memory/repository.py
runtime/renulus/memory/service.py
runtime/renulus/memory/study_answers.py
tests/learn/test_discovery.py
tests/memory/H05_HANDOFF.md
tests/memory/conftest.py
tests/memory/test_lineage_migration.py
tests/memory/test_mem0_real.py
tests/memory/test_native_answer_lineage.py
tests/memory/test_study_answer_capture.py
tests/memory/test_support_lineage.py
tests/memory/test_whole_attempt_evidence.py
~~~

## Remaining acceptance

Migrated automatic capture stays off. Full H05 acceptance requires connected
H02/H04 dependencies, real production consumed-input/Learn publication, shared
recovery registration and the native extraction resolver/IPC round trip with one
host slot and a live receive pump. Synthetic tests and actual local CPU engine
checks do not establish account quality, native packaging or that connected gate.
