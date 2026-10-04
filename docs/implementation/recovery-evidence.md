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
