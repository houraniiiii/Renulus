# Bounded backup and recovery evidence

This slice adds a real ZIP download and verified original-file restore alongside
the records-only JSON route. Work is scoped to build/data-recovery, based at
b0bf1fbba5dd1eb3ac7e5fac3ef59f275b3bfb2a, and tracked on Renulus issue #12.
All original files and profiles used here are synthetic. No private collection
was scanned and no provider was called.

## Scope and scale policy

Both formats retain canonical learning records, published content, imported
library documents/revisions, rights, citation locators, provenance, source-status
journal events, deletion markers and three portable preferences: study.goals,
memory.enabled and learn.teaching_style. Derived memory index metadata and the
internal knowledge.index_generation preference are excluded. Compatible module
schemas must already be installed in the target.

The parent reported 183,891 acquisition catalogue rows and 156 currently eligible
originals on 2026-10-04: E01 122 and E06 34. These counts are context supplied by
the user, not a corpus inspection by this lane. knowledge_catalogue is explicitly
omitted from **both** JSON and ZIP. Export, preview and status report its count
and omission reason. Only COUNT(*) is read from the catalogue; imported Library
records retain their source metadata and rights. Older JSON exports containing
catalogue rows are accepted with an explicit omission on restore. The UI preview
counts retained records and derives an omitted count from a legacy catalogue.

Canonical tables use the existing eligible learning-module table families, with
explicit exclusions for knowledge_catalogue, credentials, provider settings and
derived indexes. Source-status integration 19762d0e adds
knowledge_source_status_events; it remains eligible canonical data. Its snapshot
preserves event order for a fresh restore. Acquisition discovery can be rebuilt
from its separately preserved external collection; this slice does not recreate
or scan that collection automatically.

ZIP includes only explicitly referenced originals under
library/knowledge/doc_<id>/rev_<id>/original.<supported extension>. Each must be
an app-owned regular copy whose exact SHA-256 and size match its canonical
revision, with explicit caching/display permission. Supported originals are TXT,
Markdown, PDF, PNG, JPEG and TIFF. External originals, unreferenced files,
credentials, provider settings, indexes and managed helper weights are excluded.
A non-owned original reference makes ZIP export refuse without reading it.

| Engineering bound | Default |
| --- | ---: |
| Complete ZIP upload/download | 288 MiB |
| Canonical JSON | 16 MiB |
| Manifest / recovery journal | 1 MiB each |
| One original | 64 MiB |
| All expanded originals | 256 MiB |
| Originals per archive | 1,000 |
| Canonical learner records | 100,000 |
| Verified preview lifetime | 15 minutes |

These are adjustable slice limits, not a claim that all 156 originals fit.
Oversized learner tables are refused before materialization; accumulated JSON is
bounded too. Reconciled existing-original cleanup is bounded. There is no partial
archive, multipart backup, automatic sharding or acquisition catalogue backup.

## Validation and commit boundary

ZIP format version 1 contains manifest.json, canonical UTF-8 records.json and
the explicit original entries. Manifest hashes and lengths bind all content.
Source absolute paths are removed; ZIP original references are relative and
restored paths are rebased to the target profile. JSON remains records-only and
never copies or follows an incoming file reference.

Before promotion, recovery checks the complete ZIP directory, local headers,
CRCs, compression method, byte/count bounds, identities, linked records,
immutable published content and hashes. It rejects traversal, absolute paths,
Windows alternate streams, aliases/duplicates, links/junctions, hard-linked
originals, encrypted members, unexpected files, trailing data, overlapping
headers, ZIP64/split archives and unsupported compression. There is no extractall.
Strict JSON rejects duplicate fields, nonfinite values, invalid SQLite scalar
ranges and incompatible schemas. A read-only candidate merge copies only
eligible canonical tables, never credentials or provider state.

Restore revalidates current canonical data in a SQLite transaction. It merges
known deletion markers first and traverses their descendants. Blocked originals
never get promoted; verified existing deleted originals are quarantined first.
Current merged caching/display rights are also checked: an older ZIP cannot
override a newer local restriction. Surviving originals are then moved without
overwriting existing files.

A flushed relative-path journal and SQLite recovery receipt coordinate file
promotion with canonical commit. SQL/file failures roll back records and moved
files. Staged-source identities distinguish recovery moves from same-byte
destination collisions so rollback preserves another file that appeared there.
If rollback fails, staging evidence remains and further backup/restore/rebuild
operations require restart. Startup completes or rolls back journals using the
committed receipt before discarding recovery scratch files. Post-commit cleanup
is reported separately.

An older backup on a fresh installation cannot know later deletions, including
deletions on another installation. The UI displays this limit and requires its
acknowledgement separately from confirmation of the backup date. Existing newer
local markers remain authoritative.

## Runtime and desktop contracts

All routes use the existing /api/v1 application transport.

| Route | Behaviour |
| --- | --- |
| GET /data/export | Explicit records-only JSON attachment, no-store |
| POST /data/restore | Bounded strict JSON restore; explicit legacy confirmation remains compatible |
| GET /data/backup | ZIP attachment; temporary export removed after response |
| POST /data/backup/preview | Raw bounded ZIP, full verification and one expiring token |
| DELETE /data/backup/preview/{token} | Discard the verified preview |
| POST /data/backup/restore | Token, exact confirmed_exported_at and strict deletion acknowledgement |
| GET /data/recovery | Last restore, omissions, bounds and persisted module rebuild status |
| POST /data/rebuild | Retry the latest restore's local rebuild |

API restore schedules a background rebuild after canonical commit and file
promotion. Storage calls only the public registry seams:

- KnowledgeRepository.rebuild_index() returns status ready, passages, generation
  and cleanup_pending. Recovery reports passage counts. Pending retired-generation
  cleanup is partial, with an explicit message that library search is ready and
  cleanup needs retry.
- MemoryService.reindex() returns ready true, count and generation. Recovery
  reports memory record counts. It never invokes capture or process_pending.
- A synchronous recovery_guard() holds module ingestion/mutation coordination
  around snapshot, merge and original promotion. The parent confirmed knowledge's
  bounded wait of up to 90 seconds and a memory guard that refuses active inference
  and pauses new claims. Without a guard, a running or still-active worker is
  refused, including a running idle worker.

The parent reports both guards implemented locally on 2026-10-04; they remain
parent-owned changes to include with this recovery handoff.

The module seams own derived index staging, validation, activation and engine
locks. Storage performs no separate index scan and copies no originals to
rebuild. Missing adapters, seams or helpers have explicit results; a blocked
rebuild does not roll back a verified canonical/file restore.

The named DataManagement component imports its CSS and uses existing Flow
tokens/primitives plus the shared authenticated api/apiResponse transport. It
offers separate ZIP backup and JSON export, verifies ZIP before confirmation,
clears cancelled/stale/expired selections, displays omissions and polls rebuild
status. Knowledge passages, memory records and pending cleanup are distinguished.
The parent owns Connections mounting; this lane changes no shared shell.

## Verification

The application imports actual synthetic CKD TXT, dialysis Markdown, a complete
one-page transplant PDF with xref table and a PNG into one profile. Tests download
and validate ZIP, restore into a fresh profile and compare exact bytes, hashes,
sizes, provenance and rebased paths. External selected originals stay untouched;
protected/provider/index/helper/unreferenced sentinels never enter the ZIP.
Replay adds no duplicate canonical records.

Further checks cover transitive imported/newer-local deletions before promotion
and rebuild; records-only restore followed by verified original repair; stale
caching rights; forged ZIPs with otherwise valid CRCs/digests; upload/expanded
bounds; SQL/file failures; same-byte collisions; and pending rollback recovery.
Subprocess os._exit() before receipt and after commit proves startup rollback
versus completion of the file journal.

A synthetic 183,891-row discovery catalogue with an SQLite authorizer denying
every bulk field read proves count-only omission and small exports. A separate
100,001-row learner table is refused before bulk reads. JSON and ZIP extension
tests use the parent's exact source-journal table shape and preserve its events,
rights and citation locators. Public seam probes verify parent response shapes,
persisted status, ordering, missing-helper behaviour and no memory capture calls.

Final backend suite command with system Python 3.12.10:

    $env:PYTHONPATH = 'runtime'
    python -m pytest tests/backup tests/integration/test_backup.py tests/integration/test_foundation.py -q

The combined run passed **75 tests** in 186.04 seconds. The subsequently added
source-journal extension tests passed **2 tests**; the final pending-rollback
guard regression passed separately (**1 test**). The resulting suite has 77
tests. Desktop npm test passed **65 tests across 8 files**, including **27
DataManagement tests**. npm run build passed TypeScript, Vite and Electron
compilation. Synthetic browser checks at 1440px and 390px found no overflow or
console errors; the UI detector had no findings. git diff --check passed.

## Remaining integration limits

The parent must include the public knowledge/memory guards, mount DataManagement,
and check recovery with actual staged index engines and the packaged renderer.
The source lane does not contain those new parent modules. System Python here
does not have LanceDB; seam probes prove orchestration, not managed-helper or
engine execution. Queued synthetic imports do not claim actual PDF/OCR or memory
engine reindex execution. No real corpus, clean-machine install, native recovery
UI journey or whole-profile recovery is claimed.

Fresh source-journal ordering is proved. For an existing profile, missing backup
events are appended without replacing local events. The parent was notified on
issue #12 that journal replay needs canonical event chronology rather than local
rowid after a merge; replay policy remains owned by the source-status module.

The ZIP is unencrypted and unsigned. Hashes establish integrity against its
manifest/canonical records, not authenticity. Process-exit recovery is tested;
machine power-loss durability is not proved. Acquisition reconstruction,
credentials/settings recovery, external originals, weights, multipart/large-corpus
backup and older module-schema migration remain outside this bounded slice.

## Integrated offline engine proof — 2026-10-04

This follow-up used build/recovery-offline-proof in a fresh recovery proof
worktree based at parent 1da890b2a73a282d285c4cd65689a80033634a15. The integrated
KnowledgeRepository.recovery_guard()/rebuild_index() and
MemoryService.recovery_guard()/reindex() ran through the existing recovery API.
The earlier seam-only limitation is resolved for this synthetic text-library
and manual learner-note flow.

Two actual UTF-8 files, covering CKD and dialysis learning topics, were imported
through the durable CPU worker. Docling-core HybridChunker, FastEmbed and native
LanceDB produced passages, hybrid retrieval and citation character spans. A
synthetic transplant study preference was stored and retrieved through the
Hermes OSSBackend adapter using actual Mem0, QdrantLocal and FastEmbed. The
source's worker remained running during ZIP export. ZIP contained manifest,
canonical JSON and exactly the two originals, with portable library paths.

Restore into a different synthetic profile verified the archive, confirmed its
exact date, promoted the originals and completed both actual background rebuild
seams. Knowledge's reported passage count had to equal the archived canonical
passage count; memory rebuilt one record. Retrieval and citation locators
survived, downloaded originals matched the input bytes and canonical hashes/
sizes, and stored paths belonged to the target library. The target generation
differed from the source's excluded generation selector. Editing the note
produced revision 2 and corrected recall. Deleting the note and CKD document,
then replaying the old ZIP, left both excluded by local tombstones while
dialysis retrieval survived. Deleted originals stayed unavailable.

The only shared directory was the explicitly selected public helper directory
under Renulus-wt-integration/.local/runtime/integration/helpers. All profile,
cache, index, library and bootstrap state was allocated under this test's own
pytest scratch roots. The fixture checked the trusted helper manifest/hashes
before and after use, blocked Python writes into shared helpers, and placed
tripwires on external sockets, provider streaming and Mem0 inference. No
tripwire fired. No parent profile, keys, external collection or private inputs
were read or copied; the proof provisions no assets and makes no provider call.

Verified engine environment: Python 3.14.4; Docling 2.133.0; Docling-core 2.99.0;
FastEmbed 0.8.1; LanceDB 0.39.0; Mem0ai 2.2.1; Qdrant-client 1.19.1;
ONNXRuntime 1.30.0; pytest 9.1.1. Embedding configuration uses the selected
BAAI/bge-small-en-v1.5 CPU helper with two threads and local files only.

The actual engine test first exposed that the table filter's singular-index
token was misspelled: it exported memory_index_state and memory_index_entries.
The owned one-line storage follow-up matches singular/plural index tokens and
excludes these derived tables from JSON/ZIP snapshots and restore validation.
Six regressions prove canonical facts/history/source links remain exported,
machine-local engine identities stay absent, and forged derived tables in
either format are refused before canonical records, local index bookkeeping
or originals change. Discovery catalogue omission and source-status journal
retention remain unchanged. The narrow fix was coordinated on issue #12,
comment 5984716973. Pre-fix exports containing derived tables must be regenerated;
the corrected validator deliberately refuses them.

The seven reported integrated-fixture failures were repaired with explicit
missing-seam/guardless adapters, a memory rebuild adapter for the deletion-order
probe, and valid JSON-encoded local knowledge selectors. The missing-helper
probe still compares retained canonical records and original bytes exactly,
and now separately verifies the real memory derivative enters failed state.
Existing deletion, ordering, rollback and deliberate confirmation assertions
remain intact. No production guard, generation validation or rebuild result
was weakened.

Commands ran using the integration venv executable and PYTHONPATH=runtime:

    python -B -m pytest tests/backup tests/integration/test_backup.py tests/integration/test_foundation.py -q

Result: 83 passed, 1 skipped in 266.76 seconds. The skip is the actual-engine
test's explicit helper opt-in. With RENULUS_RECOVERY_HELPERS set to the verified
directory, the separate command was:

    python -B -m pytest tests/backup/test_offline_engine_round_trip.py -q -o faulthandler_timeout=180

Result: 1 passed in 83.93 seconds. Focused integrated-fixture checks also passed
7 cases; the six derived-state guards passed separately after all six failed
against the old filter. These focused checks are included in the broader count.
There was one existing TestClient deprecation warning. git diff --check passed.

Native path constraint observed: LanceDB failed to persist a generation data
file at a 264-character Windows path with os error 3; the equivalent source
path was 254 characters. The same actual-engine proof passed with compact,
isolated pytest profile roots. Arbitrarily long/custom profile paths remain
unverified. Parent-owned follow-up should keep the delivery root compact and
check packaged native long-path support or expose a clear profile-path limit.

This proof covers CPU text chunking, both selected derived index engines and
HTTP recovery. Actual PDF/OCR execution, the acquired-library delivery profile,
whole-corpus bounds and a packaged/native UI recovery journey remain separate
parent checks. Archive encryption/authenticity, machine power-loss durability
and larger-than-bounded recovery retain the earlier limitations.

## Published content 1.0.0 → 1.1.0 recovery compatibility — 2026-10-04 UTC

The compatibility follow-up uses build/recovery-content-compatibility, based at
parent 620c4202c4939ebbf91c89d0e1b1656af1ac458f, with the recovery proof commit
434cb398141f08c9da105a00acf75cf5a216e018 applied as 119988e5. The two IDs are
equivalent copies of the prerequisite; integrate only one copy.

Both real HTTP routes were tested: records-only JSON and verified ZIP with exact
backup-date confirmation. The source installs only the actual published 1.0.0
pack through the supported bootstrap selection. Its export is checked for that
sole pack and its 1.0.0 active slot. A fresh current target bootstraps 1.1.0 with
160 questions and 26 teaching cases, then receives its own synthetic learner
records before restore.

Each profile contributes a study thread, manual learner preference, reviewed
assessment with one answered and one pending item, and a saved teaching case
with two revealed stages. Restore preserves both profiles' records, exact
review feedback and idempotent answer replay. Every source historical question/
key snapshot and every current target question/key snapshot is compared through
the content repository. Saved stage contents and progress remain unchanged.
Replaying the backup inserts zero records. After reopening the target, its bank
is still 1.1.0 and the pending legacy assessment resumes with its preserved
question/key versions, rationale and correct score.

No production compatibility defect reproduced. The existing merge policy keeps
target rows when their primary keys already exist: the target's singleton
content_active_pack slot is retained while missing historical pack and learner
records are added. Published versions with different immutable content remain
conflicts. This regression makes the active-slot policy explicit without
changing canonical merge or weakening content validation.

Using the integration venv executable with PYTHONPATH=runtime:

    python -B -m pytest tests/backup/test_content_release_compatibility.py -q

Result: 2 passed in 17.83 seconds. The adjacent integration command was:

    python -B -m pytest tests/content/test_bootstrap.py tests/content/test_release_110.py tests/content/test_repository.py tests/assessment/test_content_repository.py tests/integration/test_backup.py tests/backup/test_derived_state_exclusion.py tests/backup/test_content_release_compatibility.py -q

Result: 59 passed in 111.20 seconds, including the two compatibility variants.
There was one existing TestClient deprecation warning. Provider and external
socket tripwires did not fire; all profiles were synthetic and isolated.

This verifies the two published content releases with the current recovery
format/runtime. Older runtime/database schema migration is not established.
The actual CPU engine proof above remains the evidence for rebuild/retrieval;
this compatibility follow-up does not require shared helper assets or claim a
new packaged UI, acquired-library or whole-corpus recovery check. The parent
owns the separate source-status recorded-time journal fix.
