# Cases lane evidence

October 4, 2026 · issue #7 · branch `build/case-discussion`.

Owned writes: `runtime/renulus/cases/`, `apps/desktop/src/modules/cases/`,
`tests/cases/` and this file. Shared runtime, storage, manifests and shell are
read only. The first backend handoff is followed by the isolated Flow page.

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
cancellation seam; main owns destination integration. The isolated Cases UI is
implemented below. Installer and complete S2 acceptance are not claimed.

## Additive producer handoff for integration

Baseline backend commit: `454a8015c29c3415a203ba4b3f21d8e6e5c4c447`.
Additive producer commit: `b0fb9a08c8a3d4b1d524d5399ca2dd78fb8b4f0a`.
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

## Flow Cases page handoff

The desktop prerequisite `75678df` was explicitly handed off and cherry-picked
locally as `444e3829`; main already integrated the foundation as `5a8644e`.
Do not replay this duplicate prerequisite. The isolated UI depends on the
additive producer commit above for its Explain payload.

Owned UI files are `apps/desktop/src/modules/cases/index.tsx`, `types.ts`,
`useCases.ts`, `cases.css` and `useCases.test.tsx`. The default entry uses the
shared Flow primitives, API helper, SSE helper and volatile navigation. No
shared shell, platform, tokens, manifests or dependencies were changed.

The page starts a text case, clears an accepted draft, discusses through ordered
SSE, stops a run, explicitly saves, reopens a saved snapshot, closes/discards
temporary changes, deletes and reports deferred physical cleanup. Original
teaching options come from the content repository API; the page reveals only
returned stages, then teaching points and the debrief. Empty, loading, unavailable
provider and storage-error states use actual responses. No sample content or
provider answer ships with the page.

Temporary and saved-snapshot cues distinguish the current live work from the
canonical snapshot. New questions and staged reveals stay temporary until Save.
The page clears a discussion question only after the started event; a request
rejected before acceptance retains the draft. Async action epochs suppress late
Save and handoff results after deletion or unmount. Unmount aborts requests/streams
and cancels the actual backend run.

Explore in Learn requests the app-owned Explain ticket with the current revision
and question. It navigates using the entire returned payload in React memory and
the returned temporary scope, including for saved cases. Cases remounts from a
volatile `handoff.case_id` (or temporary-scope entity ID) by GET, preserving its
live backend session without any automatic Save. Main owns guarded Learn/practice
integration and its return action. This lane does not claim that consumer is done.

UI checks on Windows, October 4, 2026:

- `npm run typecheck`: passed.
- `npm test -- --reporter=dot`: **24 passed** across three test files, including
  eight Cases tests. The suite verifies explicit Save only, volatile temporary
  and saved-case navigation/return, no browser-storage writes or raw URL payload,
  late Save/handoff rejection after delete, SSE envelope consumption, cancellation
  on unmount, submitted-draft cleanup and rejected-question retention.
- `npx vite build`: passed (renderer build; Electron packaging not exercised).
- Browser smoke check against the isolated actual backend on ports 8879/5197:
  synthetic text start and explicit Save succeeded. Desktop and 800×900 layouts
  were inspected; the final default-viewport page has no document overflow.
  The temporary viewport override was reset. The preview has no live provider or
  installed content pack; discussion/reveals are covered with isolated fixtures,
  not claimed as live provider/content validation.
- `git diff --check`: passed. Python backend suite remains **38 passed**; UI
  changes do not alter its schema or provider adapter.

At that UI handoff, image/PDF extraction remained disabled until a real no-write
parser proof existed. Generic principle capture, live subscription retention, clean-machine
installation and complete combined consumer verification remain follow-up work.

## Temporary attachment consumer handoff

October 4, 2026. Main integrated the preceding backend/UI commits as `3260cb91`
and `1d71cbaa`. This slice changes only Cases runtime, module UI, tests and this
evidence. It adds no dependency, shared-file change or schema migration. Main
continues to own the guarded Learn/practice consumer handshake.

Cases accepts the exact knowledge producer
`extract_bytes(data, filename, title) -> Extracted(passages, document, ocr, status)`.
It requires `knowledge.capabilities()["temporary_extraction"] is True` and a
callable producer before reading body bytes. Durable library import, installed
packages and truthy capability values do not enable temporary processing.
Knowledge owns Docling/RapidOCR and the proof; Cases has no alternate parser.

API additions under `/api/v1/cases`:

| Operation | Result |
| --- | --- |
| `POST /sessions/{case_id}/attachments/prepare` | 201, empty RAM reservation with a cancellation ID before any file bytes |
| `POST /sessions/{case_id}/attachments/extract` | 202, RAM-only extraction job |
| `GET /attachments/{preview_id}` | Reading/processing/ready/failed/cancelled/applied state, text preview and OCR metadata |
| `DELETE /attachments/{preview_id}` | Idempotent cancellation/discard |
| `POST /attachments/{preview_id}/apply` | Explicitly reviewed text added to the live case, without Save |

Upload a raw bounded body, never multipart/UploadFile. Headers are
`Content-Type: application/pdf | image/png | image/jpeg`,
`x-renulus-filename: <percent-encoded plain basename>` and
`x-renulus-case-options: {"revision": 1, "scope": {"kind": "temporary-case",
"entity_id": "<case_id>"}, "title": "Attachment text"}`. Title is optional and
bounded to 120 characters. Scope, revision, saved canonical revision, daily-case
kind, capacity, capability, filename/media and declared length are checked before
the first `Request.stream()` read. Every chunk rechecks the live case. Actual
length and file signatures are checked regardless of Content-Length. No source
path, multipart spool, original-copy path or disk extraction is used.

The module first calls the header-only prepare route, then supplies the returned
ID in `x-renulus-preview-id` on the raw upload. Stop/unmount can therefore cancel
even while the upload response is pending. A reservation is bound to the exact
case, revision, scope, filename and title, can be claimed once, and expires after
60 seconds while reading. Expired abandoned reservations release capacity on the
next guard/preflight. No file bytes are sent before the UI receives the handle.
The direct single-request extraction seam remains supported for other callers.

The RAM response contains `id`, `case_id`, `revision`, `scope`, `state`,
`filename`, `title`, `text`, `ocr: {used, confidence}` and safe optional `error`.
Missing/invalid OCR confidence stays null; it is never invented. Apply accepts
`{revision, text}` and returns the actual CaseSession. Successful Cases responses
retain `Cache-Control: no-store`.

Retention is explicit: preview in RAM → review/edit → **Use extracted text** →
optional **Save case**. Apply appends the reviewed derivative to live case text.
Only the existing atomic Save writes that text and permitted user/assistant
messages into canonical SQLite. This slice does not retain an attachment copy;
the original stays where the user selected it. No attachment, document, passage,
index, memory, evidence or tool-history record is created automatically. Teaching
continues to use its installed original stages.

Bounds are 10 MiB per upload, 50,000 characters for preview/combined case text,
16 RAM previews and two native worker slots. Producer-reported limits (currently
20 PDF pages and 12 megapixels) appear in capabilities/UI when reported. Native
conversion cannot be forcibly interrupted: Stop/discard clears visible text and
job references immediately, but the worker retains its bounded slot/input until
the CPU step ends. Cancellation, Session identity, case revision, saved canonical
revision, deletion, idle state and temporary scope are checked before publication
or Apply. Edit, discussion, Save, close and delete invalidate previews. Late
output is discarded; engine exceptions are never stringified into responses/logs.

The Flow page uses existing Input/Textarea/Button/Notice/ErrorState/API primitives.
It sends File/Blob directly, polls a volatile job, offers editable text/OCR preview
and explicit apply/discard, and aborts/cancels on unmount or revision change. No
FormData, object URL, browser storage or URL payload is used. Cancelled/failed
previews release the picker for retry. Capabilities control the picker; the
unavailable state offers pasted text. Image interpretation stays unsupported:
extraction reads words; the approved runtime has not published verified image
input. No generative image call is made.

Checks for this slice on Windows:

- `python -m pytest tests/cases tests/integration -q --tb=short`: **69 passed,
  3 skipped in 7.62 seconds**. Opt-in skips without producer/helper settings are not passes.
  Fixtures verify application retention rules, not engine safety/OCR accuracy.
- `npm test -- --reporter=dot`: **32 passed** across four files. Attachment UI checks cover disabled
  capability, raw temporary upload, explicit reviewed apply/no autosave, unmount
  cancellation, Stop before the upload response, explicit Discard without Save,
  stale scope/revision, failed retry and cancelled retry.
- `npm run typecheck`, `npx vite build`, `python -m compileall -q
  runtime/renulus/cases` and `git diff --check`: passed. Renderer build only; no
  packaging or live subscription inference is claimed.
- Synthetic extraction → discussion error → Explain handoff → explicit Save/delete
  scans all app-owned SQLite/WAL/cache/index/history/export/backup files and
  logical tables. Partial uploads, changed canonical snapshots, blocked native
  workers, partial producer results, cancellation and late output are covered separately.
  Reserved uploads reject cancel/replay/case rebinding/expiry/capability loss
  before the first body read; lost empty reservations cannot retain capacity.
- Real unavailable-capability browser smoke used ports 8880/5198 and isolated
  profile `.local/runtime/cases-attachment-preview`. An unsaved synthetic case
  displayed the disabled picker and truthful extraction/interpretation states.
  The final desktop layout was inspected. No file, Save or provider call occurred
  in that smoke; no viewport override was introduced.

During initial development `TEMPORARY_EXTRACTION_PROVEN` remained false. The
strict cold check identified `filelock._strict._probe_link_follow_symlinks()`:
`tempfile.TemporaryDirectory()` → `probe-source.touch()` →
`os.link(..., "probe-link")` during dependency import. It probes default Windows
Temp, so cold imports after accepting a case fail the strict no-write proof.
Durable `KnowledgeRepository._import` is ineligible too: it writes
`library/knowledge/{document_id}/{revision_id}/original.*`. Cases never calls it.
Parent adopted F0 profile-owned startup/import preparation before payload
acceptance and the actual guarded byte proof. Cases needs no contract change.

Optional checks use explicit `RENULUS_CASES_KNOWLEDGE_SOURCE`,
`RENULUS_CASES_HELPER_MODULE` and `RENULUS_CASES_HELPER_PROFILE` settings. They
read only validated public helper artifacts; SQLite/cache/history/export state
lives in pytest-owned profiles. Approved F0 startup runs before synthetic input
construction. No capability is forced. Real PDF/PNG API flows require the actual
producer capability; a separate direct native-stream check denies filesystem
writes/mutations and connections after startup, and inspects inventories/logs.

The selected-engine run using the knowledge lane public assets and F0 startup
returned **1 passed, 2 skipped in 86.11 seconds**, process exit 0. The direct
PDF/PNG stream passed write-denial, inventory and sentinel/log assertions; both
API flows skipped at the false producer gate. **The run also emitted a Windows
fatal access-violation diagnostic** in `docling_parse/pdf_parser.py`
`_image_from_bytes` → `PIL.Image.copy`, through Docling page preprocessing. The
process continued and assertions passed, but this is not a clean native stability
proof. Parent was notified in issue #7; no enablement was based on this run.
No no-write or native-readiness claim is inferred from its skipped API flows.

### Published producer proof and actual Cases flow

Parent subsequently reported **2 actual guarded checks passed in 94.77 seconds**
for text/native PDF/scanned PDF/image OCR, with file-write/socket denial and no
content logs/warnings. Parent enables the producer proof flag and additionally
requires `helpers.startup` configured with Docling imports ready. F0 prerequisites
`12fe822f` and `f9922270` are integrated; knowledge producer `5b70371f` supplies
the stream method and the parent applies the startup readiness gate. This lane
consumes the actual integration producer without replaying these prerequisite
commits or editing their owned files.

The user confirmed enabled prepared-helper integration at `50f4a72c`. The
subsequent actual Cases checks consume clean knowledge/startup source in the
integration worktree (observed HEAD `ea5af2e7`); neither prerequisite commits
nor shared engine files are part of this lane's handoff.

The first enabled selected-engine Cases suite used the integration knowledge/F0 source
and only the already validated public helper artifacts in the knowledge lane:
**3 passed in 168.49 seconds**, exit 0. Neither proof flag nor readiness was
simulated. These checks cover actual bounded PDF/PNG HTTP bodies → RAM preview
and OCR confidence (unknown/null) → explicit Apply → volatile guarded Explain
and generated-practice inputs for both unsaved and saved cases → explicit
Save/delete. Cancelled/deleted tickets reject further resolution. Sentinel scans
confirm no payload in app-owned SQLite/cache/history/export before Save or after
delete. No provider was installed or called: these prove the actual extraction
and guarded inputs, not live generated answers.

That run emitted generic package deprecation warnings and a Windows
`0x8007000e` diagnostic from `platform._wmi_query` during Docling dependency
startup; the process continued, imports were ready and all three checks passed.
The earlier small-page PDF diagnostic remains recorded above. These native
diagnostics are reported to the integrator rather than hidden or treated as a
no-write failure. Main owns framework/native engine follow-up.

The enabled browser smoke used the actual offline producer, isolated profile
`.local/runtime/cases-attachment-preview-enabled` and ports 8880/5198. Normal
approved startup completed before HTTP input; cold readiness took about four
minutes on this machine. A synthetic PNG produced the actual text preview
"Synthetic transplant rejection learning question", with accurately unreported
OCR confidence. Explicit Use extracted text appended it to the case while the
page still showed Temporary and No saved cases. Only explicit Save changed the
module cue to Saved snapshot and added the saved-case entry. The default desktop
layout was inspected, with no viewport override. No provider was installed or
called. The owned synthetic snapshot was deleted through the guarded API, purge
completed, the original synthetic files were retained, and both owned preview
processes were stopped.

The shared shell banner still says "Temporary case · not saved" after explicit
Save while the module correctly shows Saved snapshot. The temporary branch is
intentional for later Explain/practice; the inaccurate shell wording is an
integrator-owned copy/state seam, reported on issue #7. This lane does not edit
the reserved shell. Main also owns destination page wiring; actual tests here
prove guarded Explain/practice inputs and invalidation, not live model output.

After adding the reservation step, the current actual-engine suite was rerun
with the same explicit producer/helper environment and returned **3 passed,
7 generic deprecation warnings in 256.77 seconds**, process exit 0. Both PDF and
PNG API checks now prepare a cancellation handle before sending bounded bytes;
the guarded native-stream write/socket-denial check also passed. The Windows
WMI `platform._wmi_query` startup diagnostic `0x8007000e` recurred before
payload acceptance and the process continued. No live subscription, image
interpretation, Electron packaging or clean-machine engine stability is claimed.
