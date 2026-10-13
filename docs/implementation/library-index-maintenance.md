# Library index maintenance contract

Issue #26 builds on the reviewed #25 cleanup/publication baseline (`03a7a9e6`).
This is source implementation documentation, not installed-app acceptance or a
claim of a measured native storage bound. The unchanged default Flow application
and owner profile are outside this change.

## Search and maintenance

The pinned dependency remains **LanceDB 0.39.0**. The adapter discovers existing
FTS metadata with public `list_indices()` and creates `text` FTS only if absent,
using `replace=False`. Reopen does not replace an existing FTS index. Ordinary
imports append bounded batches; their publication no longer rebuilds FTS.

The existing hybrid query, vector/text legs, canonical revision prefilter and
`RRFReranker` remain. Do not enable `fast_search()`: the pinned SDK documents that
it skips unindexed fragments. The source adapter preserves the default search
path, but actual appended keyword/vector freshness through this exact hybrid
path still needs the parent's serial pinned-engine acceptance. SDK source and
query-builder doubles alone do not establish native retrieval behavior.

A native append, revision delete or possible first FTS creation is preceded by a
committed dirty sequence. Additive migration **knowledge-005** extends only
`knowledge_index_work` with pending batch/estimated-growth counters and capacity
forecast measurements. Canonical job, cleanup, revision and export shapes do
not change. This machine-local table remains excluded from portable records.

Maintenance is coalesced at these operation boundaries:

- Initial configurable thresholds: **32 append/delete batches** or **64 MiB
  estimated row growth**. FTS readiness checks do not count as append batches.
- Bounded staging batches check thresholds even within a long single import.
- The worker checks due retry/removal debt before selecting another job, and
  checks queue drain when no eligible job remains. A wholly fenced queue cannot
  indefinitely postpone maintenance.
- Explicit `cleanup()` retries immediately. Ordinary direct `run_job()` calls do
  not full-optimize per document; they check thresholds. Callers without the
  product worker must signal a coalesced idle boundary with
  `cleanup(force=False, queue_drained=True)`.
- Maintenance failure retains dirty debt, attempts and exponential backoff
  (initial one second, capped at 300 seconds). New mutations do not reset the
  timer. A successful attempt acknowledges the captured dirty sequence under
  the index operation lock and resets pending counters.

Maintenance runs public
`table.optimize(cleanup_older_than=timedelta(0), delete_unverified=False)`.
This is compaction, verified-version pruning and incremental index optimization,
not a standalone prune API. It neither requires optional `pylance` nor deletes
Lance internal files directly. Age-zero cleanup follows the owned snapshot
contract below; the SDK's default seven days is not a growth bound. Public
optimize can create versions after pruning, so exactly one version/file is not
an invariant. Unverified files retain the SDK's protective handling; bounded
verified history is not a promise to erase recent failed-transaction bytes.

Maintenance failure does not undo an accepted import or selector publication.
An import result adds `maintenance_pending`; worker status adds
`index_maintenance` (pending/error/backoff, counters and forecasts), without
source text or paths. Projection includes all local retirement/removal/admission
and publication debt, not only active-generation maintenance. Existing fields
remain; additive `retirement_pending` and `original_pending` expose preserved
bytes separately. Errors/backoff are selected deterministically by earliest
retry, kind priority (removal, retirement, then other), target and generation;
settled maintenance must not hide an outstanding removal error. Cleanup-only retry preserves #25's same-revision removal
fence and activation/retirement intent.

## Native lifetime and snapshot ownership

`knowledge/ownership.py` consumes the shared #27 Windows filesystem policy.
There is no portable production fallback and no separate process/PID lease
ledger. A missing policy fails closed with a retryable error.

A repository acquires `state/knowledge-native-owner` through the native
`exclusive_guard` **before** reading its selector or admitting work. The guard
holds an exact file identity/no-sharing token and its ancestor pins throughout
the repository lifetime. It excludes a second cooperating repository/process
for that profile, including readers, writers, recovery and rebuild. Tokens are
atomic no-replace local files and never transferable canonical ownership.

Each `LanceIndex` also retains a generation-specific native token next to its
folder (`<generation-folder>.native-owner`). Standalone adapters use the same
key. This fences a direct generation reader/writer as well as repository use.
The adapter retains its token across the complete synchronous operation and
native handles' lifetime. The operation lock drains a reader's complete
`to_list()`, not merely a query builder. No historical checkout or escaped
query/reader snapshot is supported. All production native consumers must use
this ownership path; an out-of-band raw SDK opener is outside this contract and
must never be introduced as a production reader or maintenance tool.

Rebuild candidates bind to the same profile owner before opening. Atomic native
`created_directory` contexts retain every newly created ancestor/leaf through
acquiring generation pins and its sibling token; exact creation identities are
validated before admission. `mkdir_exact` followed by reopening is not sufficient.
Existing generation paths use no-follow lifetime pins; 8.3 aliases normalize to
one physical sibling token.

**Follow-up 15 is fail-closed, not completed retirement.** No governed-birth or
stream-only reclamation authority is implemented yet. Native close retains the
exact generation pin and token. The adapter does not release a pin to make
pathname `rmtree` possible, and ordinary close/finish-retirement cannot release
pending retirement ownership. Discoverable generations acquire the same token
without creating missing folders. A truly absent generation, including an absent
`k` parent, may settle under existing-ancestor no-follow pins without touching or
creating a foreign object. Access failures/reparses are uncertainty, not absence.
Follow-up 18 additionally permits sealing a **bound, never-native-admitted,
resource-free candidate** when both its exact generation and sibling token are
verified absent. This acknowledges no existing resource and performs no native
close, ownership acquisition/release, folder creation or disposition. The
adapter's monotonic native-attempt marker, unresolved close/retirement state,
retained table/rejected-table/connection/token and repository retirement owners
all exclude this shortcut. An absent pathname with unresolved ownership remains
pending rather than releasing that owner. Missing-ancestor verification rechecks
the first missing child under the existing ancestor's no-follow pins; an appeared
child, reparse/alias refusal or access error is uncertainty and preserves retry.
Existing generation trees always remain preserved with retirement debt/backoff;
canonical names, identity checks and sidecars do not authorize unknown files,
substitutions or late named streams. Ready selector publication therefore stays
`ready` plus `cleanup_pending`; retry is cleanup-only, not another build.

Original cleanup likewise refuses recursive pathname deletion, even when the
canonical original is known. Native row-removal acknowledgement remains in local
`completed_sequence=1`, while the independently pending original disposition
keeps its canonical original reference and reports `original_cleanup_pending`.
Absence of an original's old spelling is not proof that a renamed original was
safely disposed. No canonical row shape or export contract changes. Follow-up 15
stopped rollback tree wipes but left failed original publication without durable
intent; that was a remaining storage defect, **not** an accepted documentation
limitation. Follow-up 16 adds the pre-allocation local intent contract below.
No old fixture/generation cleanup is authorized by either checkpoint.

`KnowledgeRepository.close()` is the real drain/close boundary. It is registered
as a `Services.on_shutdown_dependencies` callback, after existing
`stop(None)`/request drain and before helper dependencies close. `stop(0)`, a
join/observer timeout or worker settlement alone cannot release profile/native
ownership. Close seals native admission before releasing any resource, so even
a direct bound adapter cannot reopen in the native-close/profile-release gap.
A failed native close, folder retirement or guard release leaves ownership
retained; explicit close retry is required. Portable tests inject a
filesystem model; they do not represent POSIX locks, hashes or read-only flags
as Windows immutability.

Recovery's existing adapter `recovery_guard()` holds the same owner and lock
order. Restore imports canonical records only; the guard reconstructs local
maintenance debt and discards local ingestion-wait timers, while retaining actual
native retirement owners. Startup `recover()` reconstructs maintenance for an
existing local generation even when older code left no debt row. It preserves
ready publication and requeues interrupted jobs only after #25 row cleanup.

## Target-volume capacity

The shared filesystem policy supplies caller-available bytes and bounded
metadata-only logical/unique-allocated measurements. The existing **12 GiB
floor cannot be lowered** through the knowledge capacity constructor. Admission
uses the actual target path's existing ancestor/volume, before original copy,
first staging, candidate construction, each bounded stage/rebuild batch, possible
first FTS creation, revision row removal and maintenance. Removal can append
native manifests/versions: it commits dirty intent, forecasts a bounded measured
rewrite plus native margin outside the SQLite writer, and only then calls the
SDK. Low space leaves removal unacknowledged with durable error/backoff; explicit
retry may acknowledge rows while original disposition still remains pending.
No huge copy is used to discover capacity.
Native work never runs inside a canonical SQLite write transaction.

Initial conservative forecasts are:

- Original publication: original length plus 1 MiB metadata margin.
- Native stage/FTS/rebuild/removal/maintenance: twice the maximum of measured logical
  index bytes, unique allocated bytes and supplied canonical live estimate,
  plus twice estimated incoming row bytes and an 8 MiB native margin.
- Rebuild forecasts canonical passages before constructing a candidate and
  rechecks while materializing it. Maintenance measurements/forecasts are kept
  in machine-local work state, not presented as observed native peak bytes.

These are headroom forecasts, not calibrated worst-case SDK guarantees. They
can conservatively refuse an operation on a heavily amplified legacy index.
Actual peak/live/history/allocation measurements must calibrate the margin and
thresholds before release. Unique allocation is not logical bytes or reclaimable
bytes; the parent's acceptance must measure them separately.

Low original-copy admission creates no revision/folder. Mid-staging low capacity
keeps the stored original, current ready revision and committed canonical rows;
it returns the job to `queued`/`waiting_space`, with local exponential retry
backoff. Partial rows still settle through #25's removal fence before retry.
FIFO and interactive selection honor the capacity timer; explicit `run_job()`
can retry immediately. Native generation-owner contention uses the same retained
original/removal-fence/backoff path with `waiting_owner`, rather than deleting the
imported input as a failed conversion. Maintenance/rebuild low capacity preserves
the accepted revision/selected generation and records retryable debt/error instead
of fabricating rollback.

## Original publication intent (follow-up 16)

Additive **knowledge-006** creates `knowledge_index_original_publications`, a
separate machine-local table excluded by the existing backup/restore `index`
name policy. Immutable migrations 004/005 and canonical export row shapes remain
unchanged. No widening of the work-table kind CHECK, raw input, title, metadata,
provider/account state or plain import key is stored in this table. Its bounded
records contain record IDs, a hashed operation ID/request SHA, declared paths,
root/parent/created-directory/file identities when known, expected content SHA-256,
expected byte length and phase. String/JSON lengths are bounded by SQL CHECKs.

The product admits at most **64 unresolved original-publication intents**, with
both a transactionally checked admission limit and an independent SQLite insert
trigger. A durable intent is committed **before any original namespace/file
allocation**. Failure to persist that intent refuses before allocation. The
normal target-volume 12 GiB floor plus original/metadata headroom is checked
before admission. Atomic no-replace directory/file contexts retain created
identities across writes and canonical publication; no pathname write/reopen
fallback or adoption of racing directories/files is used. Every successful
creation identity is recorded before allocating the next object or writing the
file body. Failed later recording leaves the earlier committed intent and stops
further allocation. Exact verified default-stream publication clears the intent
inside the same transaction as the canonical revision/job/document commit;
canonical rollback restores intent rather than leaving untracked original bytes.

Follow-up 16 incorrectly narrowed original publication to the recorder primitive's
32 MiB convenience bound even though upload/reader support remained **64 MiB**.
That was a compatibility regression, not an accepted new product limit.
Follow-up 17 restores the existing 64 MiB contract with Library-only
`original_io.py`: at-most-1-MiB native write/read chunks on the **same retained
claim**, exact full write/read counts, flush and streamed SHA-256 verification.
No unpinned data-path fallback, duplicate descriptor, private WinDLL or change to
frozen core/recorder limits is used. The 64 pending slots and migration 006 metadata
bounds are unchanged. Oversized inputs still refuse before intent/allocation.
This finite product admission/headroom contract is **not a bound on externally
introduced bytes, aliases, ADS or later uncontrolled writes**.

The wrapper retains no-follow parent/ancestor pins and validates captured file
identity, parent identity, single-link status, exact length and bounded
HANDLE-based no-ADS metadata before/after chunks and at truncate/flush/hash
checkpoints. `renulus.storage.native` events precede every low-level data
read/write/truncate/flush, with the exact physical DOS target, retained physical
identity and `retained=True`, using producer15's `_native_audit` event shape.
Audit denial stops before the kernel operation. Stream observations and an audit
grant do **not** confer cross-stream ownership or prohibit a later hardlink/ADS.
Unknown streams are never opened, repaired or removed; partial bytes and intent
remain held. Production uses only the native wrapper; explicitly injected portable
filesystem doubles provide a modeled adapter and are not native enforcement proof.

Constructor reopen and explicit `recover()` serialize against live original
publication and examine only the at-most-64 recorded paths. Retained no-follow
checks compare the recorded physical root/parent/creation identities before
reading a known file's bounded default stream. Missing, changed, access/reparse
uncertain and matching-but-unpublished states stay held; matching content alone
never adopts the file, publishes canonical records, clears intent or grants
reclamation. Crash-gap files whose identity was never recorded are uncertain,
not adoptable. Identity/content expectations are preserved, not overwritten by
what recovery happens to find. Recovery does not enumerate/sweep Library orphans.
Late hardlinks are known to be possible; no all-stream/whole-object deletion
authority is claimed, even with an exact retained data handle.

Status adds `original_publication_pending`, `original_publication_limit`,
`original_publication_admission_held` and bounded phase counts; follow-up 17 also
exposes `original_publication_max_bytes` (64 MiB) and
`original_publication_chunk_bytes` (1 MiB). Such debt sets
pending/error status and appears in cleanup results but is **not native row
removal**. Same-operation retries refuse without allocating another original;
a different request on the same hashed operation reports idempotency conflict.
The cap reports actionable held admission rather than silently evicting intent.
Ordinary repository close may release this publication's completed native
resources while retaining durable local intent for the next reopen. Original
publication intent is not exported, imported, erased or replayed by canonical
restore. Existing retired-generation/native-close pins retain their separate
fail-closed behavior.

## Table admission correctness

The cache-before-dimension-validation defect predates the index-maintenance
patch. Follow-up 15 corrects it within this lane: a table is a private candidate
until its vector dimension and passage schema validate. Incompatible candidates
never enter the queryable cache. Failed candidate close retains a separate native
handle and its connection/ownership; repeated open refuses while that close is
unresolved, and close retry drains the rejected table before its connection.
Successful disposal permits a fresh validation attempt, not cached admission.

## Integration and release gates

Integrate the shared policy before running the production constructor. Required
stable interfaces are `path_exists`, `created_file()` (retained no-replace claim),
`created_directory` (retained exact identity), `file_info`, `canonical_path`,
`guarded_roots`, `exclusive_guard(...).close()`, `process_identity`, `available_bytes`, and
`measure_roots(..., max_entries=...).logical_bytes/allocated_bytes`. The latter
must be the repaired metadata-accounting path that coexists with held exclusive
native tokens, not an immutable/full-read inventory of locked token files.
The storage-policy lane owns those implementations and their actual Windows
acceptance; no unstable policy code is copied into this lane.

The source lane exercises tiny SQLite/file fixtures and explicit engine,
ownership and capacity doubles only. Red cases cover missing pre-append debt,
continuous-ingress maintenance, idle maintenance, and five FTS replacements on
the reviewed baseline. Unit checks cover coalescing, exact API options, query
shape, cancellation/restart/prior-publication safety, held work/readers,
retirement and low-capacity retry. They do **not** measure LanceDB amplification
or demonstrate native Windows cross-process handle exclusion.

Before release, the integration owner must run serial actual pinned LanceDB
repeated-import/hybrid/reopen/restore/continuous-queue acceptance; compare with an
equivalent fresh index and record live, verified history, unverified leftovers,
actual temporary peak and unique allocated bytes separately. Actual Windows
process/profile contention, held reader/worker through shutdown, junction/root
identity checks and a separately reserved packaged synthetic installation are
also required. Some older native/application fixtures reopened an already-live
repository; migrate those to real close/drain or test expected ownership refusal,
not a test-only production bypass. The normal installed app remains unchanged
until separately authorized delivery acceptance.

## Follow-up 15 checkpoint evidence (2026-10-13)

Preserved handoff source is `9b314d1d44368a02799382112858e8f1f904a017` plus the
existing partial work snapshotted in
`C:/Renulus/scratch/sr26/followup15-handoff-d711dab4/source-sha256.json`.
Review 14 retained 64 passing focused checks, eight normative failures across
seven defects, and separately bounded lifecycle evidence. No prior fixture or
receipt was removed. No Services, storage-policy, provider/helper or app changes
are made by this continuation; those prerequisites remain at their handoff hashes.

Fresh namespace `C:/Renulus/scratch/sr26/index15-sole-20261013` retains the
stable-source **13-failure normative red**, an intermediate 13-pass green and the
first focused rerun failure receipt. Whole-tree calls in red tests were
intercepted, never executed. Actual tiny native creation tests challenge leaf and
missing-parent substitution while atomic creation handles remain held. New
synthetic tests preserve unknown siblings, original/generation replacements,
late Windows ADS and renamed originals, independently asserting native row
acknowledgement, original debt and low-space retry. Incompatible dimension/schema
candidates include unresolved native-close retry tests.

Final scoped reruns and exact before/after source hashes are in
`C:/Renulus/scratch/sr26/index15-final-20261013/`:
`focused-v2-receipt.json` (all original 64 test cases, no exclusions),
`normative-receipt.json`, `lifecycle-receipt.json`, and `final-provenance.json`.
The earlier `focused-receipt.json` in that namespace retains 64 passing bodies
with one portable-model process-end teardown error; the fixture correction is
explicit, not a production ownership bypass. Test postconditions formerly
requiring recursive deletion now require honest pending debt/pins. Portable
fixture teardown models process termination after asserting graceful close
refusal; it does not acknowledge retirement or delete bytes. Narrow lifecycle
checks use real Windows generation/profile handles, close-thread observation,
observer cancellation and process-end release with preserved synthetic ADS.

Each new namespace is bounded to 32 MiB, uses pinned Python `-I`, and retains its
failures. No broad SDK, helpers, provider, installed application or actual tree
reclamation is exercised. This is a **source checkpoint only**, not end-to-end
retirement, original deletion, native growth or final application acceptance.
The eventual stream-only/governed-birth design remains a parent integration gate.

## Follow-up 16 checkpoint evidence (2026-10-13)

The same sole-writer lane continues without rollback, commits, core/Services
writes, helpers, providers or application work. Pre-allocation original intent is
now a source repair, not a waiver of the defect left at checkpoint 15.
`C:/Renulus/scratch/sr26/index16-intent-20261013/` preserves the stable-source
12-failure normative red plus intermediate green receipts. New tests cover intent
commit failure before allocation, partial writes, canonical commit rollback,
later identity-recording failure, same-key refusal, current pending counts and
both application/SQL cap enforcement, records-backup exclusion and canonical
restore preservation. Unknown sibling/root/directory/file replacements are
preserved without adoption or orphan enumeration.

Actual tiny Windows subprocess controls terminate before creation, after atomic
directory creation, after atomic file creation and after flushed body publication.
Reopen holds the committed intent/known expectations at each boundary rather
than replaying publication. Late synthetic ADS/hardlink preservation checks do
not claim deletion authority. A successful actual retained native original
publication separately verifies atomic canonical publication/intent clearance.
All SDK extraction/vector/index calls and capacity measurements remain doubles.

The first 85-case rerun is retained under
`C:/Renulus/scratch/sr26/index16-final-20261013/`: 84 passed; one old assertion
expected a complete orphan body where the new guard correctly stopped at an empty
claim after identity-recording failure. Its updated postcondition requires the
retained empty claim, durable preintent/expectations and no canonical publication.
Final stable-source receipts are under
`C:/Renulus/scratch/sr26/index16-verified-20261013/`:
`existing-receipt.json` (the complete prior 85-case partition, no exclusions),
`new-receipt.json`, `final-provenance.json` and `scoped-final-source.diff`.
Failed/intermediate receipts and namespaces remain untouched; each new namespace
is bounded to 32 MiB. Exact hashes include the new migration and unchanged
004/005/core prerequisites. This remains a source checkpoint, not native growth,
stream reclamation, original deletion or installed application acceptance.

## Follow-up 17 compatibility checkpoint (2026-10-13)

The parent's correction rejects the follow-up 16 32 MiB publication regression.
Existing `engines.MAX_BYTES` and `reader.MAX_ORIGINAL_BYTES` remain 64 MiB;
Library's dedicated chunk wrapper now matches them without editing core,
Services, immutable migrations 004/005, migration 006's bounds or recorder caps.
Intent still precedes allocation/body I/O and clears only with canonical commit.
No new deletion or stream-reclamation authority is introduced.

`C:/Renulus/scratch/sr26/index17-red-20261013/red-receipt.json` preserves the
stable-source 18-case red: 17 failures and one passing >64 MiB refusal control.
Two failures are actual 33 MiB publication/rollback refusals; the remaining
failures require the absent retained chunk helper. Intermediate green receipts
are preserved in the new `index17-green-*` namespaces. The earlier 107 controls
retain all postconditions; the real after-write subprocess injection now hooks
the wrapper's flush boundary instead of the unused monolithic core `publish`.
Portable doubles explicitly model the original-I/O seam, not native enforcement.

Final evidence is partitioned into separate bounded namespaces so the two
retained 33 MiB bodies are never accumulated under one 64 MiB ceiling:

- `C:/Renulus/scratch/sr26/index17-verified-prior-20261013/prior-receipt.json`:
  all **107 prior controls**, including the four actual process-exit boundaries.
- `C:/Renulus/scratch/sr26/index17-verified-tiny-20261013/tiny-receipt.json`:
  **18 small checks**, including exact-64-MiB algorithm admission on an explicit
  no-disk model, >64-MiB modeled refusal before intent/allocation, kernel-audit
  refusal, full chunk counts/flush/hash/parent-pin checks, native partial/error
  writes, truncated original recovery, changed identity, unknown ADS and aliases.
- `C:/Renulus/scratch/sr26/index17-verified-success-20261013/large-success-receipt.json`:
  one actual Windows **33 MiB** synthetic PDF-signature upload, `process=False`,
  atomic intent clearance and a second retained streamed hash proof.
- `C:/Renulus/scratch/sr26/index17-verified-held-20261013/large-held-receipt.json`:
  one actual **33 MiB** canonical rollback, preserved intent/body, reopen and
  recorded-only streamed hash classification without adoption/replay.

All 127 controls are covered across those partitions, with no excluded case.
`C:/Renulus/scratch/sr26/index17-verified-20261013/final-provenance.json` captures
exact hashes, unchanged prerequisites, per-namespace logical/allocated stream
metadata (including ADS, conservatively overcounting hardlink paths), source
stability and the scoped final diff. Every fresh index17 namespace has an explicit
**64 MiB logical AND allocated ceiling**, expanded from 32 MiB solely to verify
existing upload compatibility. The owned 33 MiB source and positive/held original
proofs remain preserved. No prior fixture cleanup, SDK/helper/provider, app or
installed acceptance is run. Native I/O/process checks are real Windows;
extraction/index/capacity remain doubles and this is not clinical/PDF parsing,
SDK growth, all-stream ownership or reclamation acceptance.
