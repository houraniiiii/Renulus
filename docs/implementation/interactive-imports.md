# Deliberate Library imports during bulk ingestion

Issue #16, implemented on 2026-10-05 in `build/interactive-library-queue`, based
on `dc9c3d442360430c7bbb3c278acd16e9d6a51b2b`. This is a narrow queue-ordering
change; the parent owns final integration and native acceptance.

Direct `/library/import/text` and `/library/import/file` requests mark their
resulting queued job as interactive. The existing single CPU worker finishes
its current conversion, then prefers these jobs while allowing bulk work a
turn after a finite interactive burst. Collection imports retain normal FIFO
priority. A queued import is still not an indexed revision.

## Storage and selection

`runtime/renulus/knowledge/priority_queue.py` stores one JSON array under the
canonical SQLite preference `knowledge.interactive_imports`. Its value contains
only valid `ingest_` job IDs. It never copies source/case text, paths, titles,
permissions, metadata or acquisition details. Other preferences remain untouched.
There is no migration, separate queue, extra CPU worker or generic scheduler.

The current engineering defaults retain up to 64 distinct hints and select up
to three interactive jobs before one waiting, unhinted bulk job. These are
tunable policy defaults, not permanent product requirements. Interactive hints
keep admission order; replay does not move an existing hint. If capacity is
exceeded, the oldest hints fall back to the durable normal queue. No import job
is discarded. Bulk jobs retain `ORDER BY created_at,id`; creation timestamps
are never rewritten. If no bulk job is waiting, interactive jobs continue.

Read/merge/write operations use the existing SQLite transaction mechanism, so
independent hint writers do not overwrite each other's IDs. The bounded list is
validated against canonical jobs/revisions/documents. Only current, undeleted
personal-library revisions with queued/processing jobs retain hints; only queued
jobs can be selected. Completed, failed, cancelled, deleted, replaced and missing
IDs are pruned at subsequent queue selection/admission. Malformed or oversized
preferences are ignored and a subsequent mark repairs the value.

Direct admission holds a small shared selection lock while the repository
creates/replays the import and the worker marks its resulting job. This prevents
another bulk selection between the canonical import commit and the hint write.
The active conversion keeps running. File scope/format/body validation happens
before this lock; the lock is not held while awaiting upload bytes. Existing
repository guards remain responsible for cancellation, replacement and deletion
during conversion.

## Restart and failure behaviour

Selection does not consume a hint. It stays until the job becomes terminal, so
`repository.recover()` can requeue an interrupted conversion with its priority
intact. Graceful stop finishes the active conversion and leaves newly queued
interactive jobs for the next worker. The burst counter belongs to a worker
instance; a new process resets it. The preference remains job IDs only.

A hint persistence failure does not turn a successfully committed import into
an API error. The API returns the existing successful import result and job ID,
and wakes the worker. A bounded in-memory ID buffer retries advisory persistence
at subsequent admission/selection; a selection already read from canonical
state can proceed despite a failed hint write. Raw persistence exceptions never
enter the response or worker status. Failed hint reads fall back to normal FIFO.

If the process exits before a failed hint write can be retried successfully,
that advisory priority may be lost. The canonical import remains queued and a
replay with the same idempotency key returns the same job, reattempting its hint
while it is queued. Terminal replay does not requeue or promote a completed
job; a changed request retains the existing idempotency-conflict response.

## Focused synthetic evidence

The actual Library router, SQLite repository and worker are exercised with
synthetic extraction, embedding and index adapters. Tests install only the
Library router, use an explicit synthetic collection root, and control worker
lifecycle; they do not bootstrap helpers or unrelated application pollers.

The affected checks cover:

- Direct note and raw-file priority ahead of 2,000 old synthetic bulk jobs,
  preserving every bulk creation timestamp. The two direct jobs are converted;
  the entire bulk backlog is not converted as a performance demonstration.
- A blocked current conversion, followed by the direct note/file before bulk.
- Finite bursts, bulk FIFO progress, and draining when only interactive work
  remains.
- The conversion finishing between direct import commit and hint marking,
  without another bulk job starting in that interval.
- Fresh-worker recovery of a selected processing job, and graceful stop/restart.
- Cancellation, replacement, deletion, terminal/missing IDs, malformed hints,
  personal-library scope and current-revision filtering.
- Note/file replay with forced hint-write failure, no duplicate job, no leaked
  exception text, preserved timestamps and later successful hint persistence.
- Hint capacity/overflow, concurrent canonical hint writers, unchanged other
  preferences, real selected synthetic collection import remaining bulk, and
  temporary-case rejection without a stored original or hint.

Run from the owned worktree with the pinned interpreter and isolated scratch:

```powershell
$queueScratch = 'E:/Renulus-native-delivery/desktop-20261005/interactive-queue-checks-20261005'
$env:PYTHONPATH = 'E:/Renulus-native-delivery/desktop-20261005/interactive-library-queue/runtime'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:TEMP = $queueScratch
$env:TMP = $queueScratch
& 'C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe' -m pytest tests/knowledge/test_interactive_queue.py -q -p no:cacheprovider --basetemp ($queueScratch + '/pytest-03')
```

Result on 2026-10-05: **19 passed, 2 warnings in 104.85 seconds**. After adjusting
the test import guard to permit engines already imported by unrelated tests in
a larger run, a narrow follow-up used the same interpreter/environment with
`-k 'conversion_finishing or advisory_write_failure'` and `--basetemp
($queueScratch + '/pytest-04')`: **3 passed, 16 deselected, 2 warnings in 15.07
seconds**. The guard rejects new heavy engine imports caused by these tests.

The issue handoff records the exact commit and commands. `git diff --check` is
also required before handoff. Both isolated runs report the existing
disabled-plugin `asyncio_mode` config warning and the installed Starlette/httpx
deprecation; no dependency changes are part of this slice.

## Integration limits

This establishes application ordering, durability and replay rules. It does
not establish native parser/model performance or installed-app acceptance. No
helpers/models, provider calls, native processes, acquired originals or current
profile were accessed. Current-app PID 6488 and its heavy slot remain untouched.
The parent reports Curie's collection/acquisition work (#14) integrated at
`716045f1`, and integrates Halley's file admission/engine work (#15) separately.
`MEDIA` remains owned by Halley;
the raw-file error label now mentions supported Office files, without changing
file admission independently. New Office UI imports are gated by
`capabilities.office_import` in the parent's work. Schemas, repository,
dependencies, UI and native delivery remain outside this slice.
