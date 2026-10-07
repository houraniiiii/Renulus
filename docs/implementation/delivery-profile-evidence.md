# Local delivery profile preparation

2026-10-04 UTC · Issue #12 · `build/delivery-profile`, based at parent
`c7c0e37365853c7670f15b169b9a86f3052fb4bf`.

`scripts/prepare_delivery_profile.py` is a developer packaging tool for a fresh,
compact Windows profile. It obtains a full ZIP through the local app proxy,
validates every member before filtering, regenerates the canonical JSON/manifest
integrity, and uses the supported target preview, date-confirmed restore and
derived rebuild APIs. The source app owns its recovery/ingestion coordination.
The tool never opens the source database, source profile, credential store or
external acquisition collection. Acquired originals remain local data; they
must never become publicly distributed package assets.

## Review and invocation

The source URL accepts only credential-free HTTP `localhost`/`127.0.0.1`, with
either the app base path or exact `/api/v1/data/backup` path. Redirects, environment
proxies and token-file reads are disabled. `--source-root` is the explicit
**app code/bundle root**, containing `runtime`, published content and the trusted
helper contract; it is not the source profile. Use the selected runtime Python
environment and a separate process so another checkout's imported runtime cannot
silently supply recovery code.

After the parent restarts the backend with the reviewed recovery prerequisite,
metadata capacity can be inspected without downloading originals, loading helper
engines or creating a profile:

```powershell
$deliveryCode = 'C:/Users/karol/Documents/t3-workspaces/Renulus'
$deliveryPython = 'C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe'
& $deliveryPython -B "$deliveryCode/scripts/prepare_delivery_profile.py" `
  --source-url 'http://localhost:5196' --source-root $deliveryCode --report-only
```

The JSON report contains canonical byte/record counts, table counts, discovery
omission count and the candidate delivery selection. It contains no row bodies.
HTTP 413 is reported as `status: blocked`, `error_code: backup_limit` with exit
code 1. An accepted report has `status: within_canonical_bounds`; this establishes
only a records-only snapshot bound. `zip_bytes` is null and original/rebuild
verification are false. Candidate revision bytes are logical metadata totals,
not verified existing files; candidate JSON bytes use the records-only path
sanitation and can differ from the full ZIP's records member.

Preparation requires an output which does not exist and whose parent already
exists. For native LanceDB the Windows profile root is limited to 60 characters.
Linked/junction paths and overlap with app/helper roots are rejected. This future
invocation is a usage example; no actual delivery profile was prepared in this
lane:

```powershell
$deliveryHelpers = 'C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.local/runtime/integration/helpers'
& $deliveryPython -B "$deliveryCode/scripts/prepare_delivery_profile.py" `
  --source-url 'http://localhost:5196/api/v1/data/backup' `
  --source-root $deliveryCode --helper-root $deliveryHelpers `
  --output-profile 'C:/Users/karol/.rnl-delivery'
```

The helper root must be the exact previously verified public CPU asset root. Its
embedding, Docling and OCR files are checked against the app's trusted manifest
and used read-only. No helper provision/download/copy is performed; the native
package supplies its managed public helpers separately. Writable cache, database
and derived indexes belong only to the new target. No app lifespan, ingestion
worker, memory capture or source scheduling worker is started. Queued Library
jobs remain durable for normal native startup.

A pre-restore validation failure leaves no output profile. A failure after the
fresh output is atomically claimed leaves that incomplete output for inspection,
returns failure and never clears it. Select a different fresh output for another
run. Only the exact temporary sibling directory created by the invocation is
removed. Existing profiles are refused before helper/network access.

## Canonical selection and audit

The filter enumerates each permitted table; it does not adopt arbitrary future
`knowledge_*`/`content_*` tables by prefix. It retains these published content
tables: `content_packs`, `content_topics`, `content_case_versions`,
`content_question_versions`, `content_pack_topics`, `content_pack_cases`,
`content_pack_questions`, `content_active_pack`, `content_question_withdrawals`,
`content_pack_withdrawals`.

Library documents must have personal-library scope, no scoped learner entity, no
reserved flag and no deletion. Their matching `knowledge_revisions`,
`knowledge_jobs`, `knowledge_passages` and `knowledge_cleanup` records are kept.
`knowledge_source_status_events` retains the canonical recorded source journal.
`deletion_ledger` is restricted to explicit knowledge entity types and their ID
prefixes. Current active/latest revisions must have verified original bindings.
Only their validated app-owned Library originals enter the filtered ZIP. Exact
size, SHA-256 and rebased target paths are verified after restore and rebuild.
No collection/manifest directory is scanned to find additional originals.

Source Learn/assessment/case sessions, memory/study histories, source checking and
scheduling state, preferences, credentials, provider/runtime/native state and
derived indexes are omitted. The acquisition `knowledge_catalogue` is excluded
by the supported producer and remains absent from the target; imported article
identity, rights, attribution, originals and source events are preserved through
Library records. The internal `knowledge.index_generation` preference is never
imported and is generated only by the target rebuild.

Current supported exports omit `retrieval_imports`. The tool neither reads source
SQLite to recover those bindings nor injects an unsupported table. Publication
metadata and retained article originals remain canonical. If a coordinated
producer later supports this table, the explicit filter requires matching
retained document/revision/job bindings. Supporting that producer is a separate
storage change.

The target main database is audited after recovery. Every table outside the
delivery allowlist must be empty except newly generated migration/recovery/index
bookkeeping and fresh bootstrap defaults. Fresh `update_source_checks` and the
disabled `update_schedule` row are compared exactly before/after restore; they
are repository defaults, not imported source configuration or history. The only
allowed target preference is the generated knowledge index pointer. Memory
rebuild must contain zero learner records. A successful report requires completed
rebuild/cleanup and all selected originals present.

## Finite capacity and observed corpus

No bound was raised by this tool. The current source and target contract is:

| Bound | Bytes/count |
| --- | ---: |
| Canonical JSON | 16,777,216 bytes (16 MiB) |
| Canonical records | 100,000 |
| ZIP archive | 301,989,888 bytes (288 MiB) |
| Expanded originals, total | 268,435,456 bytes (256 MiB) |
| One original | 67,108,864 bytes (64 MiB) |
| Original count | 1,000 |
| Manifest | 1,048,576 bytes (1 MiB) |

The parent measured 157 retained originals at 238,256,457 bytes, leaving
30,178,999 bytes (28.78 MiB) before the total-original cap. The 183,891 discovery
receipts are not imported Library files and are excluded. That source state does
not establish capacity for all remaining manual passages or future eligible JATS
imports. Compressed live ZIP size has not been measured in this lane.

The parent's read-only capacity check found 3,499 records occupying 26,583,595
serialized record bytes: structured extraction dominated revisions
(17,889,578 bytes), with passages using 7,780,223 bytes. The current 16-MiB source
export correctly refused that profile. The parent prerequisite `d38b7a04` omits
rebuildable `knowledge_revisions.extraction_json` in SQL before reading or
budgeting those bodies, declares an additive omission and retains original
hashes, canonical passages and physical citation locators. Its subsequent
3,552-record snapshot measured 9,207,062 canonical bytes after omission. These
are parent observations, detailed in `recovery-capacity-evidence.md`, not a new
live-export claim from this lane. The backend must be restarted with this
prerequisite before an actual export.

Full source export bounds apply **before** delivery trimming. The tool cannot
trim a source ZIP the supported producer refuses. It must report HTTP/capacity
failure honestly, with no truncation or direct profile workaround. Future scale
work should first measure the growing canonical/passages/original footprint and
peak memory/disk usage. A practical bounded direction is a source-side
Library/content selection under the same guard plus a versioned segmented/
streamed canonical format with segment hashes and bounded disk-backed validation/
merge. Raising an in-memory JSON or original cap alone is not that work.

## Synthetic validation

The focused test uses a real ephemeral HTTP proxy into the source app, a
synthetic proxy-injected session token and the selected public CPU helper assets
shared read-only. Profiles and all bodies are synthetic; external sockets,
provider generation/Mem0 inference and helper writes have tripwires. It creates
ready and queued Library text originals, reserved/deleted Library documents, a
discovery-only XML receipt, source-status journal, real Learn/assessment/case
records, a manual memory note, source preferences/scheduling and a native-state
sentinel.

The proof requires ready-document retrieval and unchanged physical citation
locators after restore/rebuild, exact bytes/hashes/sizes for both rebased
originals, preserved rights/attribution/journal/knowledge tombstones, and one
durable queued job. The ready original is served by the viewer; the queued
original remains present on disk while the viewer correctly refuses it until
ingestion is ready. Every learner/config/native sentinel stays in the source
and is absent from the target. A tampered reserved-original ZIP must be rejected
before filtering or target creation. A separate CLI test refuses an existing
profile without touching its sentinel, and the metadata-only capacity refusal
is tested without assets or profile creation.

Using the integration venv executable, `PYTHONPATH=runtime` and
`RENULUS_RECOVERY_HELPERS` set to the exact verified directory:

```text
python -B -m pytest tests/backup/test_prepare_delivery_profile.py -q -x --basetemp <fresh compact task-owned scratch> -o faulthandler_timeout=150
```

Result: **3 passed in 93.72 seconds** on `c7c0e373`, with the existing Starlette
TestClient deprecation warning. The preceding actual restore/rebuild check passed
2 tests in 64.62 seconds; the added capacity refusal was first red for the missing
report API, then passed. The final three-test run includes the complete discovery
and corruption guards. `git diff --check` passed. This lane made no production
storage change.

The parent prerequisite `d38b7a04` was read/reviewed after that test run; the
post-handoff proof below runs this focused slice with that prerequisite integrated.
Its additive omission metadata is passed through by the script, while the app
runtime at `--source-root` owns producer/validator compatibility. Actual live
delivery, full manual/PDF/JATS/OCR corpus capacity, final native packaging and
Windows power-loss durability remain parent/follow-up checks.

## Post-handoff extraction-omission compatibility

After handing off implementation `e35759507ec17af7e65525cd6f64b973ec94d4e5`,
the parent prerequisite `d38b7a04a7452e180c5770d3475e07be52417c89` was applied in
the isolated worktree as `05ba684fd52d0669d140ad06e56bdcb6284e6621`. It is the
same parent-owned storage change, not an additional delivery-tool patch.

The same focused command, verified public helpers and a new compact synthetic
scratch passed **3 tests in 38.10 seconds**. No script or fixture correction was
needed. Additive omission metadata survives trimming/manifest regeneration;
original-byte, passage retrieval, physical citation locator, durable-queue,
source preservation and target exclusion proofs remain intact without structured
extraction in the snapshot. The existing TestClient warning remains. The CLI help
and `git diff --check` also passed. No actual live ZIP export/preparation was run;
live/backend/final corpus capacity gates remain as described above.

## Segmented delivery preparation, October 5

The integration tool now explicitly supports both archive formats. The CLI
defaults to `--format-version 2`; the existing callable default remains format 1.
Format 2 validates the complete source archive through the guarded API, selects
content and personal Library rows using the trusted disk stage, verifies retained
originals, restores a scratch profile and exports a new segmented archive. It
clears the scratch's reviewed source-check defaults before export, then uses
the normal target preview, confirmed restore and actual CPU index rebuild.
Learner records, source configuration, credentials, discovery receipts and
native application state remain excluded. Source/profile originals are preserved.

The selection streams rows and reference joins from the verified SQLite stage;
it does not build whole-corpus identity sets or open the source database.
Knowledge tombstones include the deployed `passage_` and `ingest_` prefixes
and the earlier compatible prefixes. The format-2 report records canonical
bytes and segment count instead of inventing an aggregate JSON hash.

The real helper-backed integration checks passed **4 tests in 114.03 seconds**,
including complete format-1 and format-2 restore/rebuild, corrupted source
rejection, retained originals/queue/locators and excluded learner state. A
separate read-only review found no production blocker in the adapter against
the integrated recovery contract. Its test independence finding led to direct
assertions for retained passage/job tombstones and an excluded learner tombstone.
Full format-2 engineering limits and scale observations remain in
`recovery-format2-evidence.md`; these checks do not benchmark its full ceilings
or establish the larger live collection's final prepared profile.
