# H05 memory owner handoff — 2026-10-11

Checkout: `C:/Users/karol/.codex/worktrees/oc-memory/repo`; branch:
`codex/oc-memory-h05-support-lineage`; baseline:
`74e3424b5c03ac4616834911c13faef1c064d09c`. Local commits only, no push.

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
not relabel them. `group_id` is globally unique. Groups are storage-owned by
`memory_facts(record_id)`, inputs by `support_groups(group_id)`. Answer lineage
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

## Remaining acceptance

Migrated automatic capture stays off. Full H05 acceptance requires connected
H02/H04 dependencies, real production consumed-input/Learn publication, shared
recovery registration and the native extraction resolver/IPC round trip with one
host slot and a live receive pump. Synthetic tests and actual local CPU engine
checks do not establish account quality, native packaging or that connected gate.
