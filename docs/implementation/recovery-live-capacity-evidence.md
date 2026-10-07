# Integration profile format-2 capacity observation

2026-10-05 UTC · Issue #12 · parent source code 54cbeb6d.

The source was the task-owned profile at
`C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.local/runtime/integration`,
database `state/renulus.sqlite3`. One read-only SQLite transaction observed the
snapshot at **00:47:01.721645 UTC** and finished at **00:47:03.899326 UTC**.
The connection used `mode=ro` and `query_only`. Only schema and aggregate
COUNT/SUM/MAX/LENGTH results and permission/status counters were returned. No
record bodies, identifiers, titles, credential values or original bytes were
returned or copied. No API export, profile mutation, file hash scan or scale test
was performed. Ingestion continued; these are timestamped observations.

## Installed format-2 envelope

| Resource | Observed snapshot | Installed limit |
| --- | ---: | ---: |
| Referenced originals | 5,346 | 20,000 |
| Expanded original bytes | 434,885,185 | 8,589,934,592 (8 GiB) |
| Largest original bytes | 25,190,819 | 67,108,864 (64 MiB) |
| Canonical records before deletion pruning | 26,095 | 1,000,000 |
| Installed canonical tables | 52 | 128 |
| Conservative canonical JSONL byte bound | 366,617,276 | 2,147,483,648 (2 GiB) |
| Conservative largest JSONL row byte bound | 196,542 | 16,777,216 (16 MiB) |
| Originals + canonical bound + maximum manifest allowance | 809,891,069 | 8,589,934,592 expanded ZIP |

No oversize blocker was observed for these resources. Zero original metadata
rows exceeded 64 MiB, had invalid sizes, lacked retained personal-library scope
or caching/display rights, duplicated an original path, or used a path outside
this profile Library prefix. All 5,346 originals also matched the current
nonreserved personal-Library delivery predicate. This is a metadata check; exact
file existence, ownership, size and SHA-256 remain the guarded export checks.

The legacy ZIP1 limits are already insufficient: 5,346 exceeds its 1,000-original
cap and 434,885,185 bytes exceeds its 268,435,456-byte original-total cap.
The format-2 opt-in is necessary for this source.

## Canonical and worker counts

| Canonical Library table | Rows |
| --- | ---: |
| knowledge_documents | 5,346 |
| knowledge_revisions | 5,350 |
| knowledge_jobs | 5,350 |
| knowledge_passages | 9,334 |
| knowledge_cleanup | 0 |
| knowledge_source_status_events | 0 |
| deletion_ledger | 0 |

The full canonical count includes source learner/update records; the delivery
adapter retains only its explicit content/Library allowlist. Discovery catalogue
rows are excluded: **183,891** receipts do not enter the canonical count or imply
copying external discovery originals. **369** non-null structured extraction
documents are also omitted; retained passage text and physical locators remain
canonical. The safe preference filter excludes the derived index-generation key.

Knowledge jobs and revisions each had **369 ready, 1 processing, 4,976 queued and
4 failed** entries. These are job/revision counts, not a claim that all imported
documents have a ready derived index. Queued records can remain durable.

## Aggregate byte method and limits of the observation

Installed table eligibility and safe-preference filtering were taken from
`backup.py`; budgets came from installed `recovery_limits.py`. The projection
excludes `extraction_json` and nonportable path columns before aggregate lengths
are evaluated. Retained original paths were counted in their longer source form.
No canonical rows were materialized in Python.

Projected scalar byte lengths totaled **59,106,608**; the largest projected row
was **32,642** bytes. The reported JSONL bound uses six times those scalar UTF-8
lengths, a 32-byte reserve per value, and installed JSON key/punctuation overhead.
It conservatively allows JSON escaping and numeric/null syntax; it is not an
actual archive or serialized canonical-byte measurement. Deletion pruning can
reduce the observed input counts.

Compressed ZIP size, manifest/central-directory size, scratch/workspace usage,
original file hashes, linked-file guards and CPU rebuild time were not measured
by this read-only observation. Parent owns final guarded export, validation and
fresh preparation. Product proof and finite refusal limits remain documented in
`recovery-format2-evidence.md`.
