# Segmented full recovery format 2

2026-10-04–05 UTC · Issue #12 · isolated capacity lane based on parent 1a29f8d3.
The companion synthetic measurement is in recovery-capacity-sidecar.md.

GET /api/v1/data/backup?format_version=2 selects the additive product route. GET
without that query produces format 1. Both use disk FileResponse downloads with
the same filename convention, no-store and X-Renulus-Data-Kind: full-backup; a new
X-Renulus-Backup-Format header reports 1 or 2. JSON /data/export and /data/restore
remain explicitly records-only with their legacy bounds.

POST /api/v1/data/backup/preview streams the request to an owned disk file and
detects the archive version. The default upload budget remains the legacy ZIP
budget. Specify ?format_version=2 for the larger upload envelope; selecting it
does not relax format-1 validation. The restore body is unchanged: preview_token,
confirmed_exported_at and acknowledge_deletion_limits. Exact date and explicit
deletion acknowledgment remain required. Preview is single use, expires after
15 minutes and does not survive app restart.

Valid ZIP1/JSON input can also restore into a target larger than the old 16 MiB
snapshot budget. Incoming legacy limits remain unchanged; bounded legacy rows
stage into SQLite and use the same disk merge. ZIP1 preview fields and format-1
restore receipts stay compatible. Legacy export still refuses an oversized source.

Preview keeps format: renulus-full-backup, exported_at, record_count,
original_count, original_bytes, deletion_notice, omissions, preview_token and
expires_at. Format 2 adds format_version: 2 and canonical_bytes. Recovery status
retains legacy limits and adds backup_formats with string keys 1 and 2. Each
describes that version's finite budgets. No data is truncated. Large disk
validation may exceed the renderer's earlier 120-second timeout. Renderer/native
save and delivery-tool adoption are parent-owned follow-ups.

## Manifest and archive

Format 2 contains manifest.json, bounded table JSONL segments and only originals
explicitly declared by canonical revisions. There is no records.json or SQLite
member. This example illustrates shape and is not a valid archive:

~~~json
{
  "format": "renulus-full-backup",
  "format_version": 2,
  "schema_version": 1,
  "exported_at": "2026-10-04T23:00:00+00:00",
  "canonical": {
    "bytes": 1234,
    "records": 3,
    "tables": {"knowledge_documents": 3},
    "segments": [{
      "path": "canonical/knowledge_documents/000000.jsonl",
      "table": "knowledge_documents",
      "bytes": 1234,
      "records": 3,
      "sha256": "<64 lowercase hexadecimal characters>"
    }]
  },
  "originals": [{
    "path": "library/knowledge/doc_example/rev_example/original.txt",
    "document_id": "doc_example",
    "revision_id": "rev_example",
    "bytes": 42,
    "sha256": "<64 lowercase hexadecimal characters>"
  }],
  "omissions": {
    "knowledge_catalogue": {"records": 0, "reason": "<existing documented reason>"},
    "knowledge_extractions": {"records": 0, "reason": "<existing documented reason>"}
  }
}
~~~

Each JSONL line is a complete canonical row for the declared table, followed by
one newline. Segments are ordered by table/sequence; rows preserve source rowid
order including source-status journal ties. Tables include zero-row declarations.
Segment bytes, SHA-256, row counts, table counts and aggregate totals must agree.
Installed app schemas alone supply tables, keys, constraints, indexes and triggers.
Archive SQL is never accepted.

## Finite engineering envelope

| Resource | Format 2 budget |
| --- | ---: |
| One JSONL row including newline | 16 MiB |
| One canonical segment | 32 MiB |
| All canonical JSONL | 2 GiB |
| Canonical records | 1,000,000 |
| Tables / segments | 128 / 4,096 |
| String identity/reference | 1,024 UTF-8 bytes |
| Originals / one original | 20,000 / 64 MiB |
| Expanded originals | 8 GiB |
| Entire expanded ZIP including canonical/manifest | 8 GiB |
| Compressed ZIP | 8 GiB |
| Manifest / central directory | 8 MiB / 16 MiB |
| Deletion graph edges | 8,000,000 |
| One scratch SQLite database | 8 GiB |
| Recovery workspace files | 32 GiB |

The whole expanded ZIP budget also limits originals: canonical bytes and manifest
consume part of its 8 GiB envelope. The version-2 file journal supports at most
40,000 promotion/removal descriptors and 16 MiB metadata, with each action group
within the original count/byte budget. Format 1 remains 16 MiB JSON, 100,000 records,
288 MiB ZIP, 256 MiB originals, 64 MiB per original, 1,000 originals and a 1 MiB
manifest. These are refusal boundaries, not full-ceiling measurement claims.

Export holds knowledge/memory recovery guards and reads one stable SQLite
snapshot. It projects extraction_json/nonportable path columns to NULL before
Python scalar reads and restricts preferences to the existing safe allowlist.
Catalogue metadata, provider settings, credentials, helpers and derived indexes
are excluded. Catalogue count/reason is separate. Imported metadata, rights,
attribution, passage text/physical locators, source-status journal, learner records
and deletion markers remain canonical. External collection originals and
unreferenced Library files are not scanned.

Import bounds the central directory before ZipFile allocates metadata, then checks
single-disk classic/ZIP64 trailers, contiguous member offsets, both headers,
names, CRCs, sizes and optional 32/64-bit descriptors. Links, devices, directories,
comments, trailing data, unexpected extras/members, encryption, unsupported
compression, duplicates and unsafe paths are refused. Exact segment/original
validation finishes before the first target mutation.

Rows stage transactionally into an app-created disk SQLite database. Preview
validates a canonical-only target copy on disk. Restore rechecks staged database
identity and merges against current target state again. Transitive deletion
graph/sets live in SQLite. Tombstones reconcile before incoming rows and original
promotion. Existing target identities/active bank slot win; immutable content or
mismatched original revision identity causes refusal. The original file journal
and SQLite receipt pair file outcome with canonical commit, including restart
rollback/cleanup. Rebuild still uses only KnowledgeRepository.rebuild_index() and
MemoryService.reindex(), without provider inference or storage-owned index scans.

## Evidence and practical limits

The initial compatibility gate passed 78 checks covering ZIP1/JSON, immutable
versions, original verification, failure/restart recovery and legacy 1.0.0 learning
history into the current 1.1.0 bank. Initial format-2 gates passed 14 checks for
the actual API with more than 32 MiB canonical passages, fresh/repeated restore,
transitive deletions before promotion/rebuild, forged rows and atomic rollback.
Another 28 checks passed ZIP64 headers/descriptors/trailers, finite-budget refusals,
staging tampering, abrupt crash receipts and five-digit staged file identity.
They include five actual 53 MiB synthetic originals, plus four small text/PDF/image
originals: 265 MiB exceeds legacy limits and restores with exact streaming hashes.
The final combined recovery gate passed **137 checks** in 806.16 seconds at
`C:/Users/karol/.r2final-582b745e`, with verified public helpers enabled. It
includes both actual CPU recovery proofs, legacy/history compatibility, original
volume, crash/restart recovery, selection/refusal and the ordinary resource gate.
There were no skips or failures; the warning is the existing Starlette TestClient
httpx deprecation. Production was frozen for this run except the subsequent
small descriptor-boundary fix requested by parent review. That fix passed
**14 focused checks** (three forged boundary/signature/descriptor crossings plus
valid ZIP64 and other forged headers) in 75.60 seconds at
`C:/Users/karol/.r2header-b371aef6`. The parser now checks payload/descriptor
boundaries and exact read lengths before unpacking. Existing integration backup
checks passed **4** in 17.21 seconds at `C:/Users/karol/.r2compat-a234981e`.

Actual offline format-2 text Library and learner-note proof passed (40.18 seconds):
source import → ZIP2 → a different profile → actual FastEmbed/LanceDB and
Mem0/Qdrant rebuild → passage retrieval and physical citation/original fetch →
note edit/delete and Library deletion → replay with no resurrection. Public
helpers were verified and read-only; external network and provider inference
were forbidden by the fixture. The companion segmented historical-bank proof
retains old keys/sessions/cases/notes while the latest target active slot wins.
Compact synthetic CPU root: `C:/Users/karol/.r2cpu-620d1a4b`.

The opt-in production resource proof passed (493.33 seconds) with 13,000
synthetic documents and 130,000 passages. It used separate fresh child processes
for export, preview and restore; it did not rebuild 13,000 engine documents.
There were 169,474 canonical records, 458,211,181 JSONL bytes and 27 segments.
The highly compressible synthetic ZIP was 5,165,757 bytes, SHA-256
`b1829ec221933470b60908751cad36f8057579577bed8d8995212a8c7de80774`.

| Phase | Seconds | Python peak bytes | Sampled native private peak bytes | Observed workspace bytes |
| --- | ---: | ---: | ---: | ---: |
| Export | 68.83 | 906,664 | 81,575,936 | 1,142,567,133 |
| Preview | 134.29 | 2,572,332 | 86,032,384 | 1,718,160,462 |
| Preview + confirmed restore | 265.42 | 2,583,529 | 85,999,616 | 2,293,513,064 |

Windows process samples were taken every 20 ms; tracemalloc records Python
allocations independently. Native baselines were approximately 72 MB private.
The workspace sampler includes the synthetic source and accumulated test targets,
not only transient recovery files. The detailed ignored report is
`C:/Users/karol/.r2scale-693c27f0/test_product_disk_round_trip_m0/product-capacity/product-report.json`.
No real source/corpus/profile was read for this measurement.

The iterable selection proof passed for both ZIP1 and ZIP2 → trusted staged SQL
content/Library selection → scratch restore → regenerated ZIP2 → fresh restore.
It preserves exact originals, rights/attribution and the source-status journal;
learner evidence, preferences and memory tombstones are absent. Four selection
refusals preserve the prior preview and leave canonical state/originals unchanged.
On Windows, an early refusal closes supplied iterators; a preview lease retires
the old stage only after the caller closes its SQL readers. This gate passed
6 checks in 50.85 seconds at `C:/Users/karol/.r2filter-d487316a`.
Valid old ZIP1 and records-only JSON also passed restore into a target with
6,000 independently retained passages beyond the old canonical cap (2 checks,
10.88 seconds at `C:/Users/karol/.r2oldlarge-b414a1f6`).

SQLite page limits enforce scratch ceilings; periodic workspace observations are
not an OS filesystem quota. Staging needs disk for upload, verified originals,
incoming canonical DB and temporary merged candidate. Payload RAM is bounded by
a row rather than the corpus; JSON escaping/decoding still allocate multiples of
one row. Bounded manifest, ZIP inventory and file journal metadata remain in RAM.
Native engine rebuild time/memory has separate budgets. No acquired originals,
live profiles, credentials or delivery profile writes are used for this proof.
The 2 GiB canonical / 8 GiB ZIP ceilings have not been fully exercised. Large
rows allocate multiples of one row during JSON encoding/decoding. Failure still
leaves the existing profile unchanged or records an explicit pending rollback
that must finish on restart before further recovery.

## Local developer filtering APIs

These are Python seams for parent-owned packaging, not a new HTTP protocol. Use
an explicit fresh scratch app/profile. `Recovery` supplies guards, preview lease,
date/token confirmation, cleanup and file/SQL transaction lifecycle. A trusted
SQL filter may read `verified.stage` in query-only mode; that SQLite database is
created by this installed app and contains only validated canonical tables.
It is never an archive member. Close SQL readers inside the preview lease.

~~~python
recovery = scratch_services.registry["data_recovery"]
token, directory = recovery.begin_preview()
keep = False
try:
    # Stream the guarded source API ZIP into directory / "input.zip".
    checked = recovery.complete_preview(token, directory)  # Detects ZIP1/ZIP2.
    keep = True
finally:
    recovery.end_upload(directory, keep=keep)

with recovery.validated_preview(token) as verified:
    selected = recovery.preview_records(
        filter_rows(verified.iter_records(scratch_services)),
        exported_at=checked["exported_at"],
        omissions=checked["omissions"],
        originals=filter_originals(verified.originals),
    )

receipt = recovery.restore_preview(
    selected["preview_token"], selected["exported_at"], True
)
directory, manifest = recovery.backup(format_version=2)
# Output: directory / "backup.zip". Caller cleans this owned export tree.
~~~

`iter_records(services, tables=None)` yields `(table, row)` one at a time. Both
archive versions now have a disk stage behind this local seam. `originals` is a
bounded list of normal manifest descriptors plus `staged: pathlib.Path`.
`preview_records` consumes/closes the row/original iterators, validates complete
references and quotas, streams selected original copies and rechecks exact
hashes. Every selected non-null original path needs its matching retained
revision/document/rights and verified bytes from the same scratch preview.
Only successful selection replaces the previous preview; deletion of leased
staging waits until lease exit. The local preview format is
`renulus-canonical-record-stage`; confirmed restore still reports full-backup
and leaves rebuild-required unless the caller runs the existing public seam.

Lower-level functions in `recovery_segmented.py` are `validate_archive_auto`,
`stage_record_rows`, `stage_legacy_bundle` and `backup_segmented_to`. The producer
must run inside `Recovery.mutation()` and use a fresh app-owned output directory.
Prefer `recovery.backup(format_version=2)` to own that lifecycle.
`installed_schema(conn, limits)` in `recovery_records.py` supplies internal
trusted schema definitions; no caller/archive SQL changes them. Producers include
zero-row installed canonical table declarations. The delivery filter must check
disallowed tables have zero records, and owns any additional selection policy.
Fresh scratch apps seed `update_source_checks` and `update_schedule`; clear those
reviewed scratch seeds before a strict content/Library-only re-export. A final
target's own fresh defaults can be separately audited against its bootstrap
snapshot. No source learner/configuration rows should substitute for those defaults.
Discovery catalogue, extraction documents, indexes, helpers and unsafe
preferences remain excluded independently of the caller's filter.
