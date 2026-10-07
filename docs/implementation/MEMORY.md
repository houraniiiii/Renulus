# Learner memory implementation

October 4, 2026 · M5 · branch `build/learner-memory`, based on integration
`1f8f38b5`. Owned changes are confined to `runtime/renulus/memory/`,
`apps/desktop/src/modules/memory/`, `tests/memory/` and this file.

## Integration contract

`create_router(services)` registers `services.registry['memory']`, startup
outbox processing and shutdown cleanup. The integrator applies `schema.sql`
centrally as memory-001. This schema is immutable after the first handoff;
additions go in `memory/migrations/002-*.sql` or higher. No shared build,
storage, provider, upstream or dependency file is changed by this lane.

`MemoryService.enqueue(evidence_id, ContextScope)` takes a canonical evidence
reference, never a case transcript. The durable reference-only outbox scans
committed `learning_evidence` from Learn (`study-interest`) and Assessment
(`assessment-answer`), plus explicitly classified `learning-point` evidence.
The latter requires `{scope, general_learning:true, text}` with no other
payload fields. Existing activity/assessment producers need no generated
claim: interest and an observed incorrect answer are recorded as such, never
as mastery or copied bank content. General points use actual Mem0 extraction.

`MemoryService.retrieve(query, scope=ContextScope(...), limit=10,
budget_chars=4000, topic_id=None)` returns `{records, context, producer}`.
Context contains canonical IDs and revisions, a bounded character budget and
canonical text. M1/integration must consume this through its existing Hermes
context path before the approved provider call. Combined Learn context
injection is a handoff boundary, not an implemented claim of this lane.

The desktop routes are `/memory/facts` (list/add), `/memory/facts/{id}`
(read/revision-guarded edit/delete), `/memory/facts/{id}/history`
(inspect/remove), `/memory/captures` (enqueue reference), `/memory/jobs`
(inspect), `/memory/jobs/{id}/cancel`, `/memory/retry`, `/memory/reindex`,
`/memory/search` and `/memory/status`, all beneath `/api/v1`.

Manual add requires study scope and an idempotency key. Edits/deletes require
the expected canonical revision. Missing assets do not prevent inspecting,
adding, correcting or removing canonical facts. Index failures are visible
and retryable; canonical records do not pretend to have been indexed.

## Selected engines and paths

The actual selected packages are the shared root pins: mem0ai 2.2.1,
qdrant-client 1.19.1, fastembed 0.8.1. The adapter loads only the vendored
Hermes `plugins/memory/mem0/_backend.py` from its attributed pinned source
(`af90026aa09949579bd423d24def3d38f743cde0`). It retains OSSBackend's
add/search/update/delete interface and replaces its constructor configuration
step. The stock constructor drops the history path and can recreate a
collection when dimensions change; neither behavior is suitable here.
There is no upstream modification or platform/cloud Mem0 backend.

Mem0 factories bind the shared helper configuration and
`services.registry['provider']`. CPU embedding uses BAAI/bge-small-en-v1.5,
384 dimensions, a validated 512-token tokenizer, two CPU threads and
`local_files_only=True`. Over-budget text fails instead of being silently
truncated. No replacement embedding, Docling inference, Torch inference or
additional generative model is introduced. Mem0's optional BM25/spaCy
model acquisition is disabled; its built-in text/no-entity fallbacks are
used. Telemetry is disabled before import; engine exception bodies are not
logged. No inference credentials are acquired by the memory adapter.

Durable derived generations live in `indexes/learner-memory/generation_*/`,
with a separate `renulus_learner_facts` Qdrant collection and profile-owned
`history.sqlite3`. Extraction uses a transient local Qdrant client and
in-memory Mem0 history, then an epoch/state/revision-guarded canonical
commit. Generated candidates do not reach the live index before that commit.
Mem0 history/messages are removed and compacted after rebuilding, leaving
canonical history as the only learner revision history.

Rebuild stages a new generation and commits its canonical ID/revision map
only if the canonical epoch is unchanged. It then removes prior generations.
Corrections/deletions/history removal invalidate recall immediately, close
Qdrant, remove physical derived generations and checkpoint canonical WAL.
Physical cleanup failures return `purge_pending:true`; the deletion marker
still excludes the record from recall. Source suppression prevents queued
or later automatic recapture from evidence the learner removed/corrected.
An older backup alone cannot discover later deletions; shared restore/export
policy remains integrator-owned.

Temporary cases, saved cases and unclassified input are rejected before
lookup, hashing, operation rows, helper initialisation or provider use. A
case's persistent classification is not permission to store case facts in
learner memory. Classification is retained from canonical producer evidence;
passing a new study scope cannot relabel a case payload.

## Evidence at the first backend handoff

Public helpers were copied with the integrator's `scripts/copy_helper_assets.py`
from integration `.local/runtime/integration/helpers` to this worktree's
`.local/runtime/memory/helpers`, verifying 19 files / 483,597,181 bytes.
Only the embedding group (8 files / 67,412,843 bytes; revision
`aa8f8b060edb00e03bfdd08813a2949946c8ba55`) is used in memory verification.
The integration `.venv` Python 3.14.4 binary runs this worktree's code using
the existing pytest `runtime` path. Tests use separate synthetic profiles.

Executed on October 4, 2026:

```powershell
$env:RENULUS_MEMORY_HELPERS=(Resolve-Path .local/runtime/memory/helpers).Path
& ../Renulus-wt-integration/.venv/Scripts/python.exe -m pytest tests/memory -q
```

**11 passed in 15.46 seconds.** Nine canonical checks cover idempotence,
distinct contextual notes, revision conflict, inspect/remove history,
idempotent delete, source suppression, restartable jobs, source revision
guards and excluded scopes without sentinel writes. Two actual-engine
checks cover offline Mem0/Qdrant/FastEmbed construction, cross-domain
semantic recall, history/message purge, physical removal of superseded
and deleted sentinel text, restart/reindex and the approved scoped
extraction adapter. Remote socket connections were blocked in those tests;
loopback remains available for Windows asyncio's self-pipe. Qdrant emits
its expected local-mode payload-index warning; no server is required.

Producer distinction: facts, SQLite, FastEmbed inference, Mem0 indexing/
extraction control flow and Qdrant are real. The extraction provider response
is explicitly synthetic. Live subscription extraction, educational accuracy,
installed-app packaging and combined Learn context injection are not
established by these checks. UI and additional asynchronous race checks
continue after the first backend handoff.

## Complete owned slice and final checks

The first useful backend commit is
`de4946f1eab6ff5ddd3da3bc879b2a55f3313fa4`. The subsequent handoff adds the
Flow page and controlled asynchronous checks, reconciles restored facts
against retained deletion markers, exposes all deduplicated source references,
and checks producer classification metadata before reading text. Automatic
scanning pages beyond invalid records without copying case payloads or
creating rejected-input jobs. Shared schema/build/contracts remain untouched.

The page uses existing Flow tokens, Source Sans, UI primitives, navigation,
API and resource hooks. It supports list/add/edit/delete, revision history
and its removal, scoped semantic search, actual recall status, capture-job
inspection/cancellation, retry and index rebuild. Drafts survive transport
errors and revision conflicts; stopped or superseded requests cannot overwrite
current state. A non-study navigation context requires an explicit fresh
study transition before memory operations. No case input is silently relabelled.

Capture cancellation, source revision/classification/deletion, suppression
and canonical index epochs are checked before results commit. Edit/delete
also cancel an active provider run through the existing seam. Failed indexing
keeps canonical facts and completed jobs; explicit retry rebuilds the index.
Failed physical cleanup or a busy SQLite WAL checkpoint reports
`purge_pending:true`. An open canonical reader cannot make cleanup appear
complete. Restart/rebuild honors retained deletion markers. Concurrent
capture/search shares one lazily loaded embedding instance in this module.

Final backend command is the helper-enabled command above: **27 passed, two
warnings, in 16.32 seconds**, on October 4, 2026. Of these, two exercise the
actual Mem0/Qdrant/FastEmbed producer path; 25 exercise real SQLite/API and
policy or explicitly controlled synthetic engines. New checks cover
cancellation during extraction, a completed job winning a later cancel,
edit/delete while generation runs, stale index activation, retry after
provider/index failure, restored deletion markers, missing-helper canonical
CRUD, classification rejection before producer-text fetch, valid evidence
beyond a page of invalid records, Windows-style physical-lock recovery and
an actual SQLite reader preventing WAL truncation.

Desktop checks using integration's installed dependencies:

```powershell
node apps/desktop/src/modules/memory/typecheck.mjs
node ../Renulus-wt-integration/apps/desktop/node_modules/vitest/vitest.mjs run --config apps/desktop/src/modules/memory/preview.config.mjs --configLoader runner
node ../Renulus-wt-integration/apps/desktop/node_modules/vite/bin/vite.js build --config apps/desktop/src/modules/memory/preview.config.mjs --configLoader runner
```

Full desktop TypeScript check passed; **19 UI tests passed in 27.79 seconds**
with simulated API responses. Renderer production build passed, including the
memory route and bundled Flow font. The owned verification config permits
`RENULUS_DEPENDENCY_ROOT` for any installed desktop dependency directory and
does not alter production build configuration. The design detector returned
`[]` for the changed page components/CSS before the bounded finish-review fixes.

Browser checks against a disposable real backend without helpers performed
add, edit to revision 2, inspect/remove history, delete and reload to zero
facts. Available captures are 1280 by 800 and 380 by 1641 pixels; the compact
capture was initially summarized as 390px, which was corrected to its actual
380px width. The worker observed no page exceptions or horizontal overflow
and verified the bundled Flow font loaded. Captures/profiles/build output
remain ignored under `.local/runtime/memory/`; synthetic test fixtures are
the only retained examples.
The screenshot paths are
`.local/runtime/memory/ui-verification-2026-10-04/.desktop-check.png` and
`.local/runtime/memory/ui-verification-2026-10-04/.compact-check.png`.

The independent finish review confirmed the Flow identity and requested two
material fixes. Both were applied in one batch: unavailable local search now
has learner-facing copy, unhelpful retry/rebuild controls are disabled until
helpers are usable, and technical details live in an optional disclosure.
Closing an add/edit form after save or cancellation returns focus to its
stable trigger. The final 19-test run includes these behaviors. Renderer
build and typecheck passed after the fixes. Available screenshots predate
that final batch; post-fix visual recapture is not established.
The reviewer scored both findings resolved at source/test scope; this is
not whole-surface visual approval. The documentation check found no durable
Flow system drift, so shared design records were not changed.

A separate HTTP check on the isolated memory profile **with validated helpers**
performed add -> actual reindex/search -> edit revision 2 -> history count
2 -> history purge to 0 -> delete -> actual rebuild count 0. The final API
list was empty, `producer=mem0-oss`, `purge_pending=false`; no generation was
used in this manual flow.

The preview host subsequently disconnected. Automatic approval review rejected
an additional hidden Electron verification process with reason "blocked by
policy". That process did not run, and it is not native-app evidence. The
available renderer/browser checks do not establish a signed installer or
installed-app lifecycle.

All test facts are synthetic. Real local producers are SQLite, the vendored
Hermes/Mem0 operations, Qdrant and FastEmbed CPU inference; the extraction
provider response and controlled race engines are mocked. No paid/live
generation, private credentials, new model acquisition, Torch inference or
Docling inference is part of this lane's proof. Live subscription extraction,
clinical/educational quality and combined Learn personalization need separate
integration evidence.
