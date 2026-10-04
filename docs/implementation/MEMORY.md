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
canonical text. Learn can consume this through its existing Hermes context
path before the approved provider call. This lane does not edit Learn or
introduce another agent loop.

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
