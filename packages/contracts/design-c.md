# Design C additive contract proposal

DC02 · `design-c/1` · October 10, 2026 · baseline `1b30a896` (includes
`528025ff`). These are the small shared meanings proposed for parent review.
`runtime/renulus/design_c_contracts.py` validates records and boundary decisions;
it does not register routes, create tables or implement feature persistence.
The integration lead owns storage, server integration and migration sequencing.
DC02 remains open until its actual migration foundation is connected and proven.

## Identity, retention and ownership

- A conversation has `identity: {type: learn_thread|case, id}`,
  `kind: learning|case`, `retention: saved|temporary`,
  `lifecycle: active|archived|deleted`, `revision` and optional `project_id`.
  Preserve the original Learn/case ID byte for byte. Use the typed pair as its
  canonical identity; do not create duplicate transcripts or infer memberships.
- The backend chooses retention before accepting payloads. New conversations
  default to saved; `temporary: true` is an explicit create intent. Later writes
  resolve the canonical conversation and revision rather than trusting a supplied
  `ContextScope`. Explicit Save is the only promotion of a temporary conversation.
  Kind never changes merely because retention changes. Case payloads, saved or
  temporary, are not learner-memory inputs. Archive does not change retention.
- Temporary conversation identities, titles, drafts, tab positions, attachments,
  locators, run IDs, idempotency outcomes, provenance and job metadata are volatile.
  Nothing enters durable stores/search/exports/logs/derived indexes. A persisted
  pointer to a temporary conversation is also forbidden. Deleting a saved
  attachment writes its typed tombstone before cancelling dependent work.
- Canonical references are `{type, id}`; immutable revision IDs are themselves
  typed identities. A dependency adds `expected_revision` for compare-and-publish.
  IDs are opaque; suffixes and equal strings in different namespaces imply no edge.
- `Relation {source, target, relationship: owned|link}` is explicit. Ownership
  cascades only through owned edges. Project-to-chat membership and project-to-
  Library-revision edges are links. Deleting/unlinking a project preserves the
  independent chats and Library originals. A deleted target invalidates its links.
  Conversation-to-attachment and attachment-to-original/preview edges are owned.
  Only installed, reviewed relation declarations may drive restore pruning.
  Distinguish disposable membership links from retained unavailable provenance.
  Delete a membership row whose endpoint is gone; preserve an attempt/report/job
  outcome and its original pinned ID when its live source becomes unavailable.
- Content references pin `library_revision`, `attachment`, `note_revision` or
  `saved_test_version`, with optional typed locator. The server resolves their
  owner, availability, retention, revision and per-operation permissions. No
  absolute path, API URL, HTML or duplicate document bytes belong in a reference.
  Workspace tabs use the same content identity and a saved conversation/project
  context; reopening the identity reuses a tab. Temporary tabs stay in memory.

Locators: `pdf` uses one-based physical page and optional printed label; `text`
uses a stable item/section reference and zero-based half-open character offsets;
`table` uses a sheet name (XLSX), one-based inclusive rows and columns (CSV/XLSX);
`image` uses one-based frame and optional normalised bounds. DOCX has paragraph/
section locators, never invented page numbers. Existing Docling `page`,
`item_ref`, `char_span`, `sheet_name` and `cell_bbox` remain original provenance;
reader adapters must translate explicitly, preserving coordinate origins/units.
Reading, extraction, indexing and model use have independent states/permissions.
Opening a preview never silently imports into Library or sends model context.

## Requests, pagination and errors

Exact proposed route names (all under `/api/v1`): `/conversations` for list/create;
`/conversations/{chat_kind}/{chat_id}` for read/rename/delete, with `/messages`,
`/draft`, `/archive`, `/restore`, `/save` and `/project` actions. `chat_kind` is
`learning|case`; resolve to the original Learn/case owner. `/projects` and
`/projects/{project_id}/chats|documents|goals` are Study-owned.
`/assessment/tests`, `/assessment/tests/{test_id}/versions`,
`/assessment/test-attempts` and `/assessment/test-attempts/{attempt_id}` are the
new M4 collection/whole-attempt routes; subactions are `/draft`, `/present`,
`/help`, `/submit-answer`, `/submit`, `/pause`, `/resume` and `/reports`.
Existing `/assessment/sessions` and generated routes retain their meanings.
`/assessment/test-jobs/{job_id}` reads work; `/cancel` returns its durable winner.

Create input: `{kind,title,temporary:false,project_id:null}`. Response:
`{identity:{type:learn_thread|case,id},kind,retention,lifecycle,revision,title,
project_id,created_at,updated_at}`. Mutation targets are carried by routes;
body carries `expected_revision` plus operation fields. Draft body:
`{expected_revision,text,content_refs}`. Message page:
`{conversation,items:[{id,run_id,role,content,created_at,content_refs}],next_cursor}`.
Test start: `{version:{type:saved_test_version,id},mode,timing:{kind:untimed}}`;
timed setup instead sends `{kind:timed,duration_seconds}`. Draft write:
`{expected_revision,position,answers:[{item_id,option_ids,marked}]}`; Test submit:
`{expected_draft_revision,latest_draft}` (full displayed state) or the same
revision without latest_draft once durable. Results never include answer keys
until the server policy permits them. Exact validated response shapes follow
the Python models and fixtures; command bodies cannot set retention/policy.

Proposed module routes remain under `/api/v1`; routes listed here are not installed.

| Operation | Minimum input/result | Authority |
| --- | --- | --- |
| Create conversation | kind, optional project, explicit temporary intent; canonical summary | Backend default saved; no payload-selected scope |
| List conversations | limit 1–100, opaque cursor, project/lifecycle filter; summaries + next_cursor | Saved records only; active default, archive explicit |
| Read messages | typed conversation, limit 1–100, cursor; messages + next_cursor | Recheck retention/deletion on each page |
| Rename/archive/restore/move/delete/Save | canonical identity, expected revision, idempotency key | Revision conflict never loses draft |
| Resolve/open/use content | pinned content reference, operation and current context | Rights and active-Test policy checked by server |
| Read/start/save/submit attempt | pinned saved-test version, expected draft revision, mode/timing | Assessment owns writes and restrictions |
| Start/cancel/read job | eligible input references, idempotency key; actual durable job state | Cancellation/publication winner returned |

Message pages are oldest-to-newest with keyset ordering `(created_at, id)`.
The first page pins a high-water mark; later messages appear on a new read.
Conversation lists use `(updated_at, typed identity)` and a snapshot boundary.
Cursors bind identity, filters, order and snapshot; malformed/cross-chat cursors
are rejected. A deleted/temporary identity cannot be restored by a stale cursor.
Unstable offset pagination and unbounded transcript reads are not the C contract.
Cursor implementation and transport encoding belong to the producer.

Reuse the existing `{error:{code,message,retryable}}` envelope and no-store
responses. Codes include `invalid_request` (422), `not_found` (404),
`revision_conflict`, `idempotency_conflict`, `attempt_restricted`,
`saving_incomplete`, `dependency_changed`, `cancelled` (409), `access_denied`
(403), `unavailable` (503). Messages are safe fixed copy, never validation
payloads, raw exceptions or case text. Connection failures keep existing codes.

Every mutation has a bounded `Idempotency-Key` (8–128 characters). Store a
fingerprint of operation, typed target and canonical request; same key/same
request returns its committed outcome, changed request returns 409. Replay must
recheck current disclosure policy: a stored result containing old help is not
permission to reveal it during Test. Temporary command outcomes remain volatile.
Lost save acknowledgements reconcile against backend revision/outcome.

## Saved tests, attempts and disclosure

- `SavedTest` is collection identity/lifecycle; `SavedTestVersion` is an immutable
  published question/key snapshot manifest. Edit creates a new version. Every
  attempt/card/tab pins the same version identity, with actual item count.
  Required `provenance` is a versioned object (`schema_version: 1`,
  `method: reviewed_pack|generation|import|nightly|legacy_conversion`, optional
  saved job/fictional-artifact IDs), stored as `provenance_json`. An old-backup
  adapter explicitly chooses `legacy_conversion`; missing provenance is not an
  attestation. Temporary origins/IDs remain forbidden in provenance.
  `origin: reviewed_bank|generated|imported|nightly` and
  `review_quality: reviewed|personal|needs_review` stay separate from
  `mode: study|test` and timing. Only reviewed-bank/reviewed items can enter bank
  cohorts. User-private source terms do not become CC BY by conversion.
- New `TestAttempt` is distinct from legacy `assessment_attempts` (one committed
  answer) and `assessment_sessions` (quiz run). Legacy mode remains reviewed/
  generated; its exposed feedback, partial denominators, committed answers, IDs
  and exposure survive. Legacy sessions are Study-compatible, never retroactive
  Test attempts, deadlines or scores for unanswered blanks.
- `AttemptDraft` contains version-pinned item ID, selected option IDs, marked
  state, position and monotonically increasing revision. Test selection writes
  no score/evidence. Manual final submit supplies the latest displayed full draft
  or requires the matching durable revision; transactionally save-and-finalise or
  return `saving_incomplete`. Delayed saves cannot mutate a terminal attempt.
  `assessment_test_attempts.committed_json` stores independent Study answer
  commitments (and Test answers after final commit); `result_json` stores the
  terminal result with answered/unanswered/excluded/scored counts. Draft updates
  never write either field. Defaults are `committed_json = []` and nullable
  `result_json`; both stay empty during Test until final atomic publication.
  Public `committed` and `result` are withheld during
  active Test; Study resume returns committed work without making it editable.
- Exposure pins question/key/family/item/version and records presented/help
  before returning content. Study assistance precedes hints/sources/notes/chat;
  answer commit precedes feedback/evidence. Test final commit precedes all keys,
  feedback and learning evidence. Keep exposure separate from graded evidence.
- One active Test per profile is the current planning default. Across pause/
  restart/navigation deny chat/help/source/note/search-snippet, legacy feedback/
  replay, revealing aggregates and plaintext export/backup/restore activation.
  Permit neutral question presentation/reporting and recovery/settings. Cancel
  in-flight assistance and reject late responses using a policy revision.
- Untimed is default. Timed Test stores UTC started_at/deadline_at at ready
  attempt start, has no pause, continues closed/asleep, and reconciles on every
  read/write. At deadline, accept no new draft; submit durable predeadline drafts
  and blanks exactly once on reopen if necessary. Backend clock reconciliation
  must not extend a deadline after a backward clock change.
  Each attempt persists nonnull `clock_high_water_at` from its creation and
  advances it monotonically; `paused_at` is nullable and used only for Study.
  Reconciliation uses the later of server time and persisted clock high-water.
- Timed Study is pauseable as the labelled planning default; expiry preserves
  drafts and committed work and offers Continue untimed/Finish, never submits a
  draft. Invalid/withdrawn pinned items can still finalise, with excluded counts
  separate from unanswered counts; prior results are never rewritten.

## Jobs, personalisation and temporary boundary

Use existing bounded local job patterns, not a new scheduler/event service.
`Job` has operation, state, input dependencies, settings/policy revision,
progress, original request hash/count, idempotency key and optional published
version. States are queued,
running, needs_review, failed, cancelled, published. No incomplete result is Ready.
Within the publication transaction recheck deletion, expected revisions,
permissions, active-Test policy and opt-in settings. Cancellation winning first
prevents publication; publication winning first returns published. Retry returns
the same outcome. Restart may recover validated checkpoints but never starts
provider work automatically. Daily keys include local day/timezone/scope/settings;
nightly is off by default and has at most one catch-up.
Test jobs preserve `requested_count` (5/10/20) and `request_hash`. A deliberate
shorter-set action may supply `accepted_count` (integer 1–20, at most both
validated_count and requested_count). Effective publication uses accepted_count
when supplied, otherwise requested_count; the producer atomically publishes
exactly that many validated items and never rewrites the original request.
Without explicit acceptance, partial work cannot become Ready.

Eligible personalisation inputs are saved learning summaries, current eligible
memory revisions, user goals/preferences and aggregate committed learning
evidence. Server resolution attests their operation-specific eligibility and
revision. Raw case content, temporary identifiers, reviewed keys, private original
bytes and model-controlled eligibility flags are rejected. Saved case summaries
must already be generalised fictional learning evidence, separately eligible;
retention alone grants no permission. Memory correction/deletion, project removal
and relevant restore invalidate jobs/cache before publication.
Capture `storage.invalidation.context_epoch` with each derived job and compare
it transactionally before publication; producers call `bump_context_epoch` for
relevant edits/deletions/settings changes. Restore's Library dirty marker blocks
source queries until a real successful rebuild clears it. The parent's storage
implementation owns these mechanisms; the contract pure check does not run them.
Project goals default to `status: active` and `progress_json: {}`. Status is
`active|completed`; public `progress` records optional unique `evidence_ids` and
explicit `manual_intent`. Empty progress is valid. The backend verifies saved
evidence eligibility; neither model inference nor invented percentages count as
completion. These fields do not alter legacy `study.goals`.

DC18 explicit create-test intent can transform temporary text entirely in memory
into a `FictionalTestArtifact`: validated generalised fictional questions and
keys with synthetic content IDs, digest and validator receipt. Only a trusted
server validation boundary constructs it. It contains no temporary origin ID,
raw prompt, attachment/locator, transcript, identifying derivative, source edge
or job metadata. A boolean from the renderer/model is not validation evidence.
Semantic privacy checks are the producer's required connected evidence; shape
validation alone does not prove fictionalisation. Before this boundary, no job/
draft/log/checkpoint is durable. After it, recovery owns only the fictional
artifact; metadata must not reconnect it to temporary input. Explicit Save is
the alternative before durable processing of original details.

## Migration and old-backup proposals for integration

Parent reserves schema compatibility 1→2 and exact migrations `learn-002`,
`cases-003`, `knowledge-003`, `study-002`, `assessment-003` (saved tests) and
`assessment-004` (new attempt/timing). This worker implements no DDL. Do not
rewrite legacy tables or their IDs. Increase truthful health schema only when
parent proves refusal by older runtimes, atomic interrupted upgrade and replay.

Exact proposed persisted names/identity and relation columns:

| Table (owner/migration) | Identity / relation columns | Semantics |
| --- | --- | --- |
| learn_conversations (Learn/002) | thread_id PK → learn_threads.id | Saved-only sidecar: lifecycle, revision, draft_text, draft_refs_json, draft_revision; original ID |
| case_conversations (Cases/003) | case_id PK → case_sessions.id | Same saved-only sidecar, case kind; no temporary rows |
| study_projects (Study/002) | id PK | Independently owned project, title/lifecycle/revision |
| study_project_chats (Study/002) | id PK, project_id → study_projects.id, chat_kind + chat_id → learn_threads.id or case_sessions.id | Both edges link; UNIQUE(chat_kind,chat_id), sole membership authority |
| study_project_documents (Study/002) | id PK, project_id → study_projects.id, revision_id → knowledge_revisions.id | Both edges link; UNIQUE(project_id,revision_id) |
| study_project_goals (Study/002) | id PK, project_id → study_projects.id | Owned goal; status active/completed and progress_json; does not rewrite study.goals |
| knowledge_attachments (Knowledge/003) | id PK, chat_kind + chat_id → learn_threads.id or case_sessions.id | Owned saved-chat attachment; retention saved only |
| knowledge_attachment_originals (Knowledge/003) | id PK, attachment_id → knowledge_attachments.id | Owned bytes/preview reference, separate extraction/index status; one authority |
| assessment_tests (Assessment/003) | id PK | Collection identity/lifecycle; newest version derived by ordinal, no reverse cascade |
| assessment_test_versions (Assessment/003) | id PK, test_id → assessment_tests.id | Owned immutable manifest; ordinal/origin/review_quality/items_json/terms/provenance/digest |
| assessment_test_attempts (Assessment/004) | id PK, original version_id, nullable live_version_id, version_snapshot_json | Independent immutable payload/provenance; original pin has no hard version FK or pruning edge |
| assessment_attempt_drafts (Assessment/004) | attempt_id PK → assessment_test_attempts.id | Owned revision/answers_json/position; no scores |
| assessment_attempt_exposure (Assessment/004) | id PK, attempt_id → assessment_test_attempts.id | Owned item/question/key/family version snapshot and kind; not learning evidence |
| assessment_question_reports (Assessment/003) | id PK, original version_id/attempt_id, nullable live_version_id/live_attempt_id | Independent item/question/key/family pins, question_snapshot_json and request_hash; neutral report survives deleted source |
| assessment_test_jobs (Assessment/003) | id PK, original published_version_id, nullable live_published_version_id | Retained original requested_count/request_hash and optional accepted_count; inputs/checkpoints obey durable boundary; never ownership of a source |
| assessment_test_commands (Assessment/003) | idempotency_key PK | operation, target_type, target_id, request_hash, result_json, created_at; separate from legacy and attempt command ledgers |

These names are frozen proposals for review, not independently reserved new
migrations. In particular M2 must reuse existing case attachment/original rows
for legacy saved cases instead of copying their bytes into new attachment tables.
Knowledge attachments provide the shared ordinary-chat entry; legacy case
attachment references retain their existing IDs and route through the Case owner.
Neither sidecar stores project_id: the API derives it from study_project_chats.
Metadata preference storage keeps saved typed references and server-validated
context only. JSON references in draft_refs_json, immutable test provenance and
job inputs need explicit typed traversal/revalidation; column-suffix heuristics
are insufficient. Relation proposals in the Python module specify parent table/
column, child table/column, ownership/link and any discriminator condition.
Existing legacy relationships must remain in the parent's installed registry.
`TABLE_COLUMNS` and `relations-and-rows.json` freeze the proposed scalar column
inventory. `UNAVAILABLE_REFERENCE_COLUMNS` is separate from pruning relations:
never add its pinned columns to deletion traversal or null/erase those pins.
Attempt version_snapshot_json stores the complete immutable version privately
at start; public TestAttempt responses omit its keys. A nullable live pointer
can only equal the original pin or be unavailable; it cannot repin history.
`unavailable-references.json` supplies an absent-live-version attempt snapshot,
original report pins with an independent private question snapshot/request hash
and the retained job outcome for migration/restore tests. A report's snapshot
retains the question/key and original pins even after live pins become unavailable;
active-Test reads and command replay must still withhold keys.

Foreign keys may guard owned/membership rows. Original provenance pins in
attempts/reports/job outcomes must survive physical pruning of deleted tests/
versions; no hard FK may prevent that restore. Parent and M4 can instead retain
referenced versions with root soft deletion, but must preserve the same public
unavailable meaning and independent immutable attempt payload.

Explicit converters must inspect known source format/schema/column inventory
before exact-column validation against the target. Supported source inventories:
records JSON format 1/schema 1, ZIP format 1 and segmented ZIP format 2/schema 1.
ZIP manifest/media/hash/path validation precedes record conversion; reject
unknown schemas, extra columns/tables/preferences/media or arbitrary SQL.
Record converter version and omissions; never silently fill unknown semantics.

| Old record | Explicit additive conversion |
| --- | --- |
| learn_threads/messages/runs | Same ID, learning/saved/active, no project, original messages/citations/run states |
| case_sessions and owned attachments/parts | Same ID, case/saved/active from explicit saved snapshots only |
| Unsaved/dirty Case in process memory | No durable source row; create nothing and never infer Save |
| assessment_sessions/items/attempts/exposure/commands and generated equivalents | Preserve all rows, snapshots, partial denominator, shown feedback; legacy/Study-compatible adapter only |
| knowledge documents/revisions/passages and Library notes | Same identity and revision/rights; notes remain existing documents; no inferred project links |
| study.goals/global study records | Keep global defaults; no inferred project goal or overrides |
| deletion_ledger | Map exact known entity_type namespaces; suppress owned descendants, drop links to deleted targets, never cascade links |

The fictional fixture conversion helper only maps known legacy identities; it
is not the production JSON/ZIP converter. Parent must cover all installed table
column inventories in storage and preserve JSON absence of original bytes. ZIP
original promotion stays owned, bounded, verified and transactional. New media
extensions and MIME/signature support require explicit archive/controller work.
Safe new preferences are chosen name, workspace width and **saved typed tab
references only**, nightly opt-in/time/count and explicit project study overrides;
do not export credential/native state, cookies, acquisition paths, caches, engines
or temporary selection/draft/tab metadata.

Restore first merges newer known typed tombstones, then prunes owned descendants
and unavailable links, validates surviving references, stages originals and
publishes atomically. Include attachment tombstones and prevent late job
resurrection. Separately retained memory survives with unavailable provenance
unless explicitly deleted; do not cascade through a provenance link. An old
backup alone cannot know later deletions on a fresh installation. Rebuild
eligible derived indexes after restore, never treat them as canonical.

Rollback proposal: application rollback is allowed only for a proven compatible
profile; otherwise refuse and deliberately restore a supported pre-upgrade
backup into a separate owned profile. Parent proves populated repeatable upgrade,
interruption, schema/downgrade refusal and actual old JSON/ZIP conversion.
Feature owners prove new-record export/delete/restore; DC20 proves the combined
populated profile and DC21 the matching Windows release.
