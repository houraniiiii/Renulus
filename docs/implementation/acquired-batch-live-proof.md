# Deliberate acquired batch in the running Library

October 4, 2026, UTC. Integration owner; external collection preserved.

After the nonblocking acquired enqueue patch, the actual Library UI selected
the first 50 L02 candidates from its registered, filtered catalogue. Matching
JATS, metadata and file-hash inspection ran before adoption. A read-only SQLite
audit identified the exact 50 most recently inspected receipts at
23:40:47.650–23:40:52.385 UTC: 29 were eligible and had canonical import jobs;
21 were rejected as article_permission_required without a job. The manifest
selection pass precedes these per-receipt timestamps, so that interval is not
the complete end-to-end batch timing.

The accepted records retain acquisition topic observations across 19 canonical
domains: T02, T06, T07, T08, T09, T10, T12, T13, T14, T17, T18, T19, T20, T21,
T22, T24, T25, T26 and T27. Those tags are not independent content review or
positive current-guidance evidence. The subsequent local Library snapshot had
189 documents: 136 ready, one processing and 52 queued. Queued articles are not
claimed indexed, and this development profile is distinct from the earlier
clean delivery snapshot.

The production index meta-CSP changed during the batch and caused a Vite full
page reload after its canonical imports completed. The transient import notice
was therefore not retained as evidence. The audit records the persisted receipts
and job bindings instead of inventing a final UI count. The browser did select
and invoke the real Queue selected action; no direct database mutation was used.

The previous five-candidate UI check accepted three cross-domain articles and
rejected two for licence/exclusion issues. Neither batch distributed acquired
bodies or used generative providers. Larger deliberate, bounded ingestion is
being implemented through the same inspected-version and rights rules.
