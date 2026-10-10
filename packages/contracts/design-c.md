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
- Timed Study is pauseable as the labelled planning default; expiry preserves
  drafts and committed work and offers Continue untimed/Finish, never submits a
  draft. Invalid/withdrawn pinned items can still finalise, with excluded counts
  separate from unanswered counts; prior results are never rewritten.

## Jobs, personalisation and temporary boundary

Use existing bounded local job patterns, not a new scheduler/event service.
`Job` has operation, state, input dependencies, settings/policy revision,
progress, idempotency key and optional published version. States are queued,
running, needs_review, failed, cancelled, published. No incomplete result is Ready.
Within the publication transaction recheck deletion, expected revisions,
permissions, active-Test policy and opt-in settings. Cancellation winning first
prevents publication; publication winning first returns published. Retry returns
the same outcome. Restart may recover validated checkpoints but never starts
provider work automatically. Daily keys include local day/timezone/scope/settings;
nightly is off by default and has at most one catch-up.

Eligible personalisation inputs are saved learning summaries, current eligible
memory revisions, user goals/preferences and aggregate committed learning
evidence. Server resolution attests their operation-specific eligibility and
revision. Raw case content, temporary identifiers, reviewed keys, private original
bytes and model-controlled eligibility flags are rejected. Saved case summaries
must already be generalised fictional learning evidence, separately eligible;
retention alone grants no permission. Memory correction/deletion, project removal
and relevant restore invalidate jobs/cache before publication.

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

No schema number is claimed by this branch. Parent reserves named additive
migrations through the existing checksum ledger; module owners propose DDL.
Proposed reservation order: conversation identity/retention/attachment tombstones;
typed relations/project membership; saved tests/versions; new attempts/drafts/
exposure/timing; jobs/preferences. Do not rewrite legacy tables or their IDs.
Increase the supported profile schema and truthful health schema only when the
parent proves refusal by older runtimes, atomic interrupted upgrade and replay.

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
