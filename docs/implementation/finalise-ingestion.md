# Ingestion finalisation — October 5, 2026

Implementation commit: `f25da20ece7eeecaf5b44ca9a2bb2cf9aaf9fff6`, based on
`9d26f1eedf31cd488b9aab5837a105ee152d9efa`. Worktree
`C:/rn-finalise-20261005/lanes/ingestion`, branch `build/finalise-ingestion`,
GitHub issue #6. The parent granted the narrow `knowledge/api.py` lease for
`POST /collection/import`; no other route was changed. This report accompanies
the code commit for local parent cherry-pick. Nothing was pushed or merged.

The parent reported roughly 6,175 queued originals and 29 deliberate adoptions
at 06:48 UTC still without ready revisions at 07:26 UTC. This lane inspected
code, the public dependency sources/manifest and isolated synthetic fixtures.
It did not inspect those originals, the learning profile or private/native state.
The changes remove concrete redundant work and connect selected-import priority;
they do not establish the cause or resolution of that actual-profile interval.

## Changes and ownership

| File | Change |
| --- | --- |
| `runtime/renulus/knowledge/engines.py` | Validate before loading and reuse the process-owned converter/tokenizer. Bound Docling page queues to eight. Keep Docling/HybridChunker and its table splitter; use the existing semchunk semantic splitter with its public `memoize=False` option. |
| `runtime/renulus/knowledge/priority_queue.py` | Save a bounded selected batch of advisory job IDs in one transaction through `mark_many`. |
| `runtime/renulus/knowledge/worker.py` | Admit explicit selected batches under the existing admission lock, mark only queued results, and wake the same CPU worker. |
| `runtime/renulus/knowledge/api.py` | Route only explicit `/collection/import` through that worker adapter after scope validation. |
| `tests/knowledge/test_ingestion_throughput.py` | Synthetic SDK/hash-validation checks, serialization, retry/tamper rejection, real semchunk cache checks and table-dispatch checks. |
| `tests/knowledge/test_selected_import_priority.py` | Synthetic SQLite backlog, admission/recovery/race checks and four focused Library API checks. |
| `tests/knowledge/test_interactive_queue.py` | Update the one obsolete assertion that explicit collection selection had no priority. Existing shared fixtures and their implementations are unchanged. |

Canonical repository logic, schemas/migrations, acquired-source inspection,
helper artifacts, pins, FastEmbed/LanceDB, Hermes/Mem0/Qdrant, subscription/model
allowlists, source-operation rights and Flow design are unchanged. No new engine,
heavy worker, provider call, precomputed ready revision or runtime service is added.

## Precise selection semantics

- Explicit `POST /api/v1/library/collection/import` keeps its request, HTTP status
  and result shape. The existing collector still decides eligibility and performs
  admission. The worker returns that result unchanged. Only entries returned as
  `queued` contribute candidate job IDs. Ready, failed, excluded and processing
  results do not create new hints.
- Canonical admission and hint marking share the existing admission lock. The
  active conversion can finish; another dispatch cannot slip between those steps.
  There is no preemption and no extraction inside the route.
- Hint validation retains only live queued/processing personal-library jobs with
  an undeleted document and its latest revision. Cancellation, replacement and
  deletion continue to invalidate candidates. Repository publication/cleanup
  guards and source inspection are unchanged.
- At most 64 hints are retained. Existing hints preserve order; new distinct
  queued IDs append in result order. Overflow drops the oldest hints, while their
  canonical jobs remain in ordinary FIFO. Queued replays preserve identities,
  timestamps and existing hint positions. No job creation time is rewritten.
- The existing fairness policy remains three hinted jobs, then one unhinted FIFO
  job when available. If only hinted jobs remain, they continue. The burst counter
  is in-process; a new worker starts it at zero. Persisted hints survive a normal
  restart and interrupted-job recovery.
- Hint writes are advisory. A failed write preserves successful admission and
  retains a bounded in-memory retry buffer; priority is not restart-durable until
  the write succeeds. Failed hint reads fall back to ordinary FIFO.
- `/collection/import-next` keeps background admission and its existing wake,
  cancellation and result behavior. Direct note/file imports retain their priority.

## Evidence and checks

| Observation | Untouched baseline | Fixed synthetic check |
| --- | --- | --- |
| Docling group validations across 29 PDF jobs | 87 | 3 |
| OCR group validations across those jobs | 87 | 3 |
| Embedding group validations for chunking | 29 | 1 |
| Tokenizer loads across those jobs | 29 | 1 |
| New global semchunk counters across 29 split documents | Baseline default has unbounded global memoization, confirmed in pinned source | 0, with an unrelated synthetic counter preserved |
| Dispatches to finish 29 selected jobs ahead of 6,175 background jobs | Not a baseline latency measurement | 38, including nine background jobs, with initially empty hints |
| Initial advisory writes for a 29-entry explicit API batch | No collection hints previously | 1; all 29 remained canonical queued jobs until processing |

The validator checks hash tiny synthetic artifacts using the real helper
validator. Converter, tokenizer SDK and index doubles establish orchestration
rules, not actual Docling/OCR/FastEmbed/LanceDB performance or extraction quality.
The semantic-split check uses the installed semchunk implementation and verifies
token bounds/content preservation without accumulating its global caches.
The table check verifies delegation and the reserved budget through the SDK seam.

Receipts below are ignored, machine-local files under this owned worktree.
Selections overlap and their pass counts must not be added together.

- `.local/ingestion-baseline.xml`: one intentional failure against the exact
  baseline engines module compiled in memory; the validation counters were
  87/87/29. No checkout was reset.
- `.local/ingestion-compatibility.xml`: 50 queue/concurrency checks passed
  before the API hookup; pytest reported 73.02 seconds.
- `.local/ingestion-latest.xml`: 17 engine/queue checks passed, zero failures,
  errors or skips; JUnit suite time 34.751 seconds. This completed receipt was
  recovered after Git relocation when session 7801 was unavailable. It was not
  rerun. The four API checks were added subsequently.
- `.local/ingestion-api.xml`: 23 affected API/interactive-queue checks completed
  with 21 passes and two replay failures in 31.25 seconds. The new synthetic
  catalogue fixture had omitted receipt hashes and byte counts.
- `.local/ingestion-api-corrected.xml`: those two checks passed in 13.20 seconds
  after correcting only the owned fixture to contain actual synthetic SHA-256
  hashes and sizes. The other 21 checks do not use that helper and were not
  repeated. Production replay/provenance code was not changed.

All checks used the existing interpreter at
`C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe`.
No dependencies were rebuilt. The new queue/API fixtures reject native-engine
imports; no actual helper configuration/model load, OCR, native launch or
original adoption was performed. `git diff --check` passed.

The recovered core selection can be reproduced at the implementation commit
with the following command; `collection_api` excludes the four later API checks:

```powershell
$python = 'C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe'
& $python -B -m pytest tests/knowledge/test_ingestion_throughput.py tests/knowledge/test_selected_import_priority.py -k 'not collection_api' -q --tb=short
```

The affected API run selected all of `test_interactive_queue.py` plus the four
`test_collection_api_*` functions in `test_selected_import_priority.py`. The
corrected run selected only the two failed functions.

## Measurement risks and parent acceptance

Validation-call and dispatch counts are deterministic work measurements, not
native latency, disk throughput, peak RAM or ready-time guarantees. Cold converter
construction still performs its existing validation passes. Loaded objects are
reused for the process lifetime; helper repair/replacement needs a fresh engine.
Other helper capability validation and per-document Lance FTS maintenance remain.

Disabling semantic memoization can increase repeated token-count work within one
large document. The eight-page queue is a backpressure limit, not a total RAM
bound; individual pages, models and tables can still be expensive. Actual
Docling/HybridChunker text/table/image/Office fidelity, temporary-input behavior
and CPU/RAM tradeoffs require the parent's serial helper/native acceptance.

An active long conversion still delays every new import. Existing hinted work
and the deliberately retained background fairness also affect waiting time.
Persisted hints do not retroactively identify the previously admitted 29 files;
the parent owns deliberate supported-route reselection/application to that
profile and must retain current source-selection/permission guards.

An existing generic-catalogue gap was observed with the incomplete fixture:
hashless rows can be admitted, but replay then returns `idempotency_conflict`
because the stored revision hash cannot match a missing receipt hash. The
selected-import checks use hashed receipts matching the parent's classified
adoption direction. Supporting or rejecting hashless receipts is outside this
API call-site lease; the collector/repository policy was left unchanged.

The parent must inspect the complete diff and own the real-profile normal queue,
ingestion and image/Office native checks before acceptance. This lane claims no
installed-app improvement, complete backend regression or end-to-end acceptance.
