# Cases lane evidence

October 4, 2026 · issue #7 · branch `build/case-discussion`.

Owned writes: `runtime/renulus/cases/`, `apps/desktop/src/modules/cases/`,
`tests/cases/` and this file. Shared runtime, storage, manifests and shell are
read only. This is the first bounded backend handoff; UI follows the desktop
shell handoff.

## Decisions and requested prerequisites

The cases repository keeps new daily and staged teaching sessions in memory.
Only an explicit Save creates/updates the canonical case snapshot. Follow-up
messages and staged reveals remain pending in memory until the next Save. Save
snapshots permitted user/assistant messages; it never copies provider tool logs
or private chain of thought. A running generation must finish or be cancelled
before Save. Every asynchronous result checks run cancellation, the case revision,
the application-owned scope and the deletion marker before committing.

The module exposes `create_router(services)` under `/cases` and registers
`services.registry['cases']`. Its unnumbered `schema.sql` is proposed DDL for
the integrator's checked migration ledger, not a second migration authority.
Deletion marks the shared ledger and removes the canonical case in one transaction.

Producer and shell contracts:

- The orchestrator published `generation.Provider`: `stream(messages, *, scope,
  run_id, model=None, system=None, purpose='explain')` returns text deltas;
  `cancel(run_id)` is async. Cases consumes this exact seam with
  `purpose='case-discuss'`. All model calls, including follow-ups to a saved case,
  use application-owned `temporary-case` scope. No secondary model, memory or
  retrieval call is performed. Scope precedes the adapter call.
- M8: `list_cases()` and `get_case(id)` return original versioned teaching case
  records. Cases pins the returned version and stage snapshot for the session,
  so a pack activation cannot change an ongoing session. Historical version
  lookup should be published for canonical reopen/source provenance.
- Desktop foundation `75678df` is handed off; module entry is
  `apps/desktop/src/modules/cases/index.tsx`, using shared primitives, API/SSE and
  navigation. Shared files remain reserved. The shell can stay temporary after
  saving a canonical snapshot because follow-up discussion remains volatile.
  There is no need to override its scope propagation.

No new runtime dependency, paid inference, unsafe disk extraction or separate
content reader is proposed. Images/PDFs are unavailable until a verified volatile
provider/parser route exists. Explain/practice handoffs carry an app-owned ticket,
question and revealed case text only in memory/HTTP with temporary scope. The
destination must use the guarded context/commit seam below. No unrestricted
transcript memory capture is exposed. Generic learning evidence needs a separately
scoped explicit path that excludes raw case facts.

## First backend handoff

Implemented files:

- `runtime/renulus/cases/__init__.py`, `models.py`, `repository.py`,
  `streaming.py`, `api.py`, `schema.sql`.
- `tests/cases/__init__.py`, `conftest.py`, `test_retention.py`, `test_api.py`.
- This evidence record.

Public API under `/api/v1/cases`: capabilities, teaching catalogue, saved
snapshots; start/get/edit/delete/close sessions; reveal/save/discuss/handoff;
run status/cancel. Requests cannot supply scope. Mutations use a case revision;
discussion uses a volatile request ID with replay and changed-input rejection.
Replay buffers, partial outputs, pending messages and handoff tickets are memory
only. A disconnect records a local cancellation and calls the adapter. Ordered
SSE has one completed/failed/cancelled outcome; unexpected provider exceptions
are replaced with static errors and never stringified.

Teaching sessions copy and pin the repository's original version once. Hidden
stage narrative, teaching points and take-home material are excluded from both
the response and model context until the appropriate reveal. Save includes this
versioned snapshot and only permitted user/assistant messages. Reopen does not
silently select a new active teaching version.

Deletion atomically writes an opaque case-ID tombstone and removes the snapshot.
SQLite secure-delete comes from the shared Database; the module requests a
truncating WAL checkpoint to remove older saved bytes. If a reader pins an old
snapshot, deletion still succeeds logically but returns `purge_pending: true`.
An idempotent delete retry completes cleanup after the reader releases it. No
claim is made that unrelated backups or user-owned originals are rewritten.

Checks on Windows, Python 3.12.10:

- `python -m pytest tests/cases tests/integration -q --tb=short`: **32 passed**
  (27 cases checks, 5 shared foundation checks), October 4, 2026.
- `python -m compileall -q runtime/renulus/cases`: passed.
- `git diff --check`: passed.

Tests scan raw app-owned SQLite/WAL files and logical tables plus profile cache,
index, history, export and backup directories. They cover successful/error/cancelled
discussion, blocked providers that ignore cancellation, deletion during output,
disconnect, Explain/practice handoff scope/cancellation/edit/save/delete guards,
explicit Save/reopen, unsaved follow-ups, atomic rollback, stale canonical writes,
tombstone restore rejection, delayed physical purge and staged/versioned reveals.
Synthetic examples span CKD, dialysis, transplantation, glomerular disease and
electrolytes. Provider/content fixtures exist only in tests; no fixture answer or
teaching case is shipped. These prove application rules, not clinical accuracy
or a live Hermes subscription connection.

## Remaining limits

Live model authentication and no-save behaviour of the actual Hermes adapter
require F0/integrated evidence. Image/PDF capabilities are explicitly unavailable;
no input bytes/path are accepted for disk extraction. Generic principle capture
is not exposed. Explain/practice tickets expose an internal guarded context and
cancellation seam; destination integration is still required. UI follows this
backend commit; installer and complete S2 acceptance are not claimed.

## Additive producer handoff for integration

Baseline backend commit: `454a8015c29c3415a203ba4b3f21d8e6e5c4c447`.
The proposed `cases/schema.sql` remains unchanged: only explicit Save writes
`case_sessions`; the shared `deletion_ledger` is the deletion authority. No table
is added for temporary handoffs, messages, runs or drafts.

`POST /api/v1/cases/sessions/{case_id}/handoff` accepts
`{revision, target: "explain" | "generated-practice", question?: string}`.
Question is optional, trimmed and bounded to 12,000 characters. Its direct JSON
response is `{id, case_handoff_id, case_id, revision, target, expires_at, question,
case_text, scope: {kind: "temporary-case", entity_id: case_id}}`. Both ticket-ID
fields name the same ticket. Even saved snapshots hand off with temporary scope.
Teaching `case_text` includes only revealed narratives. Successful case responses
send `Cache-Control: no-store`. Keep the payload in React memory; no URL, browser
storage, ordinary study thread, tool history, export or memory record may receive it.

Consumers resolve the ticket through the registered repository:

```python
cases = services.registry["cases"]
context = cases.resolve_handoff(ticket_id, "explain")
# context: case_id, revision, question, scope (ContextScope),
#          cancel (asyncio.Event), messages (pinned visible context)
# Use the approved Provider.stream with context["scope"].
# Combine messages with the requested question in volatile memory only.
cases.commit_handoff(ticket_id, "explain", answer,
                     cancel=context["cancel"], scope=context["scope"])
```

Check the cancellation event before emitting/committing output. `commit_handoff`
rechecks expiry, cancellation-token identity, case revision, saved canonical
revision, deletion, idle state and temporary scope. It appends the handoff question
and permitted completed answer to the live case only. Returning to Cases should
pass `{case_id}` so the UI can reopen the RAM session. Saving this result is a
separate explicit Cases action; Learn must never auto-save or create study evidence.
Edit, Save, close and delete invalidate tickets. `cancel_handoff(ticket_id)` or
`DELETE /api/v1/cases/handoffs/{ticket_id}` idempotently signals cancellation.

Additional checks on October 4, 2026:

- `python -m pytest tests/cases tests/integration -q --tb=short`: **38 passed**.
- Saved-case Explain result leaves the canonical snapshot unchanged until Save;
  reopening confirms the explicit promotion, deletion purges the sentinel.
- Volatile HTTP payloads send no-store; teaching handoff excludes hidden material;
  cross-repository canonical edits reject late handoff commits.
- A storage failure returns a safe retryable `case_save_failed` response and
  leaves the session temporary. Invalid answers cannot append orphan questions.
- `git diff --check`: passed. No live inference was invoked.

Integration requests: wire Learn to this guarded seam and preserve the opaque
`case_id` when returning to Cases. The shell disclosure currently says temporary
case is not saved even after explicit Save; adjust the shared copy to distinguish
temporary processing from a saved snapshot. Temporary scope itself remains correct.
