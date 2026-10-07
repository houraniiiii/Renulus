# Recovery capacity against the acquired library

2026-10-04 UTC · Issue #12, measured on the task-owned integration profile.

The live library exposed a delivery problem missed by small recovery fixtures.
A consistent read-only snapshot contained 3,499 records and 26,583,595 serialized
record bytes. The records-only/full-backup canonical limit was 16 MiB. Structured
Docling extraction in knowledge_revisions accounted for most of the excess; the
canonical passage table occupied 7,780,223 bytes. The 157 retained originals
occupied 238,256,457 bytes and remained below the 256 MiB original-total cap.

Exports now omit the rebuildable extraction_json projection directly in SQL,
before reading/serializing those payloads or checking the record budget. Originals,
metadata, hashes, passage text, headings and physical page/item locators remain.
The archive records this omission explicitly. Older supported backups remain
readable, and portable record handling drops the same derived field. The source
profile is not rewritten or cleaned as a side effect of export.

A subsequent consistent snapshot, while ingestion continued, measured 3,552
records and 27,044,667 bytes before omission. The actual canonical snapshot after
omission measured **9,207,062 bytes**. This resolves the observed current export
blocker without changing a size cap. It does not establish that the final or
expanded acquired corpus fits the existing bounds.

Twelve focused derived-state and integration recovery checks passed. A synthetic
20 MiB structured extraction proved omission happens before size checking for
both JSON and ZIP. Fresh restore retained passage text and physical locators;
the full ZIP retained exact original bytes, and export preserved the original
source extraction. Provider/index state exclusion and atomic record restoration
remain covered by the adjacent checks.

Current limits remain explicit: 16 MiB canonical JSON, 100,000 records,
288 MiB ZIP, 256 MiB expanded originals, 64 MiB per original, 1,000 originals and
1 MiB manifest. Larger-corpus recovery needs measured memory/disk behaviour and
a deliberate bounded implementation. It must not silently truncate a library,
transport collection metadata/credentials, or merely remove a limit.
