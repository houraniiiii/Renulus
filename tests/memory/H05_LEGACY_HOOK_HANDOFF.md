# H05 legacy Learn hook handoff

2026-10-11. Bounded continuation from memory commits

- `433ac1655fbcbe6c4eff6ec79a320da953a95ddc`: persistent support lineage.
- `fd1d0d6da7ec8769dc53a0be27b6f2cdfb706898`: native local receipt validation.

The parent consumed the second commit as `696b798f`. This patch uses the
exclusive leases for `learn/service.py` and `learn/memory_context.py`, plus the
existing memory owner and dedicated tests. The parent owns native LearningOwner,
activation, source adapters, shared registrations and connected acceptance.
No shared schema, dependency lock, native owner or ticket/status file changes.

## Real legacy behavior

Learn filters original message dictionaries with `memory.eligible_history`
before citation/history projection loses run identities. Actual retained
assistant evidence pins and actual `MemoryContext` revision pins are published
with the saved answer in the same canonical transaction. Unknown or revoked
assistant text stays in display history but is omitted from model dispatch.
Echoes keep their ancestor roots and cannot acquire independence through a
fresh answer identity. Queued and completed edit/delete regressions use the real
Learn hook without a trusted synthetic lineage publisher.

Direct legacy prepare resolves `projects.context_in(conn, 'learning', thread_id)`
and captures its host-owned project ID and document restriction. Recall and
history admission use that project. No project parameter is accepted from the
user/model. The original policy/context guards and temporary/saved-case
exclusions remain. Generated answer hashing occurs before its publication
transaction; only local canonical checks occur within publication.

## Exact interfaces and prerequisites

`memory.check_answer_inputs_in(conn, *, inputs, dependencies=(), project_id=None)`
returns `None` or raises the existing eligibility/internal error. It accepts the
existing `EligibleInput` and `Dependency` types through `AnswerInputs`, uses its
supplied connection, and performs no answer/source body, engine, original-file
or IPC resolution. Parent native current/publication callbacks can replace
their temporary direct `repository.lineage.check_inputs_in` call with this seam.

`guarded_stream(..., current=None)` is backward compatible. A supplied synchronous
local checker runs before dispatch and before/after each provider event or
stream advancement. A callback selects the provider events path even when no
memory fact is directly recalled, protecting history-only dependencies during
awaited compaction. Policy/context and the typed closure are also checked in
the final answer transaction. Internal resolver errors retain their code;
only named helper/index availability errors become memory-unavailable events.

Prerequisites from parent `63457a15`:

- Additive `ActiveRun.project_id` is already present in parent. This lane adds
  the identical field; retain the parent's legacy/native ownership guards.
- Bind `services.registry['harness_library']` to the existing shared
  `HarnessLibrary` instance, after Knowledge and before Memory.
- Use `KnowledgeRepository.check_evidence(..., conn=...)` and the public
  `HarnessLibrary.validate_publication`/`resolve_dependency` supplied-connection
  paths from that parent composition.
- Prebind the source owner's persistent `library_revision` resolver in
  `services.registry['memory_dependency_resolvers']` before Memory construction.
  No adapter means fail closed, including before provider dispatch.

Legacy citations name `document_revision`. Source `Dependency.expected_revision`
is the exact 64hex digest returned by `HarnessLibrary.resolve_dependency`,
never the document revision ID. Capture uses the run's exact scope, restriction,
policy/context revisions, topic and freshness, with guard/recorder noops to
avoid recursive owner checks. Noncanonical citations fail closed.

An ordinary `run.publication` callback executes once and still gets real M5
publication. Explicit synthetic publisher callbacks remain supported: the
callback's returned digest must equal the actual canonical lineage row on the
same connection. A false digest or internal callback failure rolls the answer,
evidence and lineage transaction back together.

## Fixtures and verification

`tests/memory/legacy_source_fixture.py` labels its synthetic ready Library
rows and synthetic independent-source adapter explicitly. Its local canonical
receipt calculation uses the real parent Library and Knowledge code. This
uncomposed lane falls back to exact `git show 63457a15:<path>` source in memory;
it does not copy runtime files or private profiles. A source-only test export
needs the composed Library modules or that Git object. The previous native
receipt tests separately need the composed bridge migration or object
`845c1f0c`, as documented in the original H05 handoff.

The real Mem0/Qdrant/FastEmbed CPU edit/delete/reindex/reopen test now uses the
actual Learn hook; its trusted synthetic publisher was removed. Generation is
synthetic, helper artifacts are pinned, and external sockets are blocked.

All receipts live under `C:/Renulus/scratch/oc-h02-h08/memory/receipts/`.
Original first red: `cycle01-red.xml`. This lease's first behavior red:
`legacy-cycle21-red.xml`, one failure (`memory_lineage_unknown` on public capture
admission). An earlier weak probe passed through unknown-lineage exclusion;
capture admission was added before implementation to make the test sensitive.

Each cycle 21–28 has one behavior failure before its implementation. Cumulative
green counts for cycles 21–25 are 1, 2, 3, 4 and 5 passed. Cycle 26's intended
green still had one fixture failure; cycle 27 passed all seven cases after that
expectation was corrected. Cycle 28 passed all 17 dedicated cases. Every one of
these receipts has zero errors/skips.

| Receipt | Executed outcome |
| --- | --- |
| `legacy-discovery-fixture-red.xml` | 3 failed before the fixture inherited real Memory hooks |
| `legacy-fixtures-green.xml` | 31 passed, 5 deselected |
| `legacy-real-cpu-green.xml` | 1 passed: actual Mem0/Qdrant/FastEmbed with real Learn publication, edit/delete/reindex/reopen |
| `legacy-current-source-green.xml` | 18 passed, zero skipped: 17 dedicated cases plus the real CPU case on final production source |
| `legacy-owner-final-green.xml` | 198 passed, 1 failed, zero skipped: the sole failure was the compaction fixture's `tests.learn` import under full collection |
| `legacy-full-collection-compaction-green.xml` | 1 passed, 198 deselected, zero skipped: the same compaction case under the same full collection after using an explicit local fixture path |

All 199 distinct owner/discovery cases have passing evidence across the broad
attempt and corrected exact-case rerun. This is a reconciled union, not a single
fresh 199-case green run. No production behavior changed after the 18-case
current-source run; the final correction affects only fixture import resolution.

Intermediate filenames containing green are not acceptance claims:
`legacy-focused-green.xml` has 2 failed/64 passed; `legacy-cycle26-green.xml`
has 1 failed/5 passed because a project fixture included independent study
interest records in its expected learning-point list. Both fixture expectations
were corrected without weakening lineage checks. The failed receipts remain.

Exact final commands, run from the assigned checkout with managed Python and
public helper assets:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:RENULUS_MEMORY_HELPERS='C:/Renulus/dev/helper-assets'

& C:/Renulus/dev/python/Scripts/python.exe -B -m pytest `
  -p pytest_asyncio.plugin -p no:cacheprovider `
  tests/memory/test_legacy_learn_lineage.py `
  tests/memory/test_mem0_real.py::test_actual_cpu_engine_support_revocation_after_edit_delete_reindex_reopen `
  --basetemp=C:/Renulus/scratch/oc-h02-h08/memory/lh-final `
  --junitxml=C:/Renulus/scratch/oc-h02-h08/memory/receipts/legacy-current-source-green.xml -q

& C:/Renulus/dev/python/Scripts/python.exe -B -m pytest `
  -p pytest_asyncio.plugin -p no:cacheprovider `
  tests/memory tests/learn/test_discovery.py `
  --basetemp=C:/Renulus/scratch/oc-h02-h08/memory/legacy-owner-final `
  --junitxml=C:/Renulus/scratch/oc-h02-h08/memory/receipts/legacy-owner-final-green.xml -q

& C:/Renulus/dev/python/Scripts/python.exe -B -m pytest `
  -p pytest_asyncio.plugin -p no:cacheprovider `
  tests/memory tests/learn/test_discovery.py -k history_only_revocation `
  --basetemp=C:/Renulus/scratch/oc-h02-h08/memory/lh-coll `
  --junitxml=C:/Renulus/scratch/oc-h02-h08/memory/receipts/legacy-full-collection-compaction-green.xml -q
```

AST parsing of all eight changed Python files and `git diff --check` passed.
The final staged diff is checked before commit. Manual standards and spec review
found no remaining material issue within this lease. The user prohibited
descendants, so this review did not spawn the code-review skill's agents.

## Changed paths and integration boundary

- `runtime/renulus/learn/service.py`
- `runtime/renulus/learn/memory_context.py`
- `runtime/renulus/memory/service.py`
- `tests/learn/test_discovery.py`
- `tests/memory/test_mem0_real.py`
- `tests/memory/test_support_lineage.py`
- `tests/memory/test_legacy_learn_lineage.py`
- `tests/memory/legacy_source_fixture.py`
- `tests/memory/H05_LEGACY_HOOK_HANDOFF.md`

The commit SHA is reported separately after commit; the handoff does not attempt
to contain its own Git identity. Parent can release both Learn leases on receipt
of the verified commit and compose the public checker at its native owner seam.

Migrated automatic capture remains disabled. Actual native SDK/IPC extraction
resolver round trip, one host slot/live receive pump, source persistent adapter
composition, shared recovery registrations and full H05 acceptance remain
parent integration work. This patch does not close those gates.
