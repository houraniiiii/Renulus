# BF00 canonical storage seam

This is the isolated TypeScript target slice. The current product's Python
writer and entrypoints retain authority. This module does not select a production
profile, apply migrations, transfer authority, restore a backup or resume work.

## Runtime and API

Use the prepared **Node 26.4.0** executable:
`C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe`.
It is the path in `runtime/renulus/runtime/desktop_harness.py`; the public
archive/executable hashes remain in `scripts/prepare_opencode_cohort.py`.
No package or runtime acquisition is needed by this seam. The integrator owns
the backend manifest and build configuration. Source tests use native Node
TypeScript stripping; the eventual build must emit the worker and rewrite its
relative `.ts` imports/worker URL together, or retain this source module graph.

Import from `index.ts`:

- `loadMigrationInventory(repositoryRoot)` reads and hashes the same checked-in
  SQL scripts enumerated by `server.create_app`. It never executes migration SQL.
- `previewStorage({databasePath, migrations, expectedSchemaHash?})` uses a worker
  with an actual read-only SQLite connection. It returns schema 2 inventory,
  table columns/counts, foreign keys, index definitions/columns, schema hash,
  applied checksums, pending migrations, quick-check results and incompatibilities.
  Compare the schema hash to a trusted populated Python baseline. A checksum
  ledger alone cannot detect a modified table or trigger. Counts are excluded
  from the schema hash. Unsupported schema 1/3 is reported without conversion.
- `openIsolatedStorage({profileRoot, selection, migrations, expectedSchemaHash})`
  returns a `StorageClient`. Startup first validates read-only, then opens the
  sole worker writer. All installed source migrations must already be applied.
  It creates no application tables and changes no existing schema meaning.
- `client.command(command)` accepts the closed union in `contracts.ts`:
  `storage.preview`, `records.page`, `records.export`, `learning.rename` and
  `database.backup`. Extra fields and unknown commands are rejected at both ends.
- `client.close()` seals admission and drains all admitted work, including online
  backup settlement, before closing SQLite and releasing its owned lease.

The public facade/plugin layer retains responsibility for authentication,
request ownership and domain-specific permissions before calling this internal
seam. `records.page` is a bounded administrative canonical-record reader, not a
renderer SQL endpoint. It follows the records-only export eligibility and
preference policy; it cannot read credentials/configuration tables or arbitrary
queries. Pages contain at most 100 rows and 16 MiB, with a next offset. Separate
pages are separate snapshots; use `records.export` for one consistent snapshot.

## Synthetic target admission

The caller prepares a complete Python-produced schema-2 database at
`<profileRoot>/state/renulus.sqlite3`, closes its Python canonical connections,
then supplies two explicit metadata files. The storage API never creates or
updates the selector/marker itself.

`<profileRoot>/.renulus-synthetic-storage.json`:

```json
{"contract":"renulus-synthetic-storage/1","profileId":"synthetic-bf00"}
```

`<profileRoot>/state/storage-selector.json`:

```json
{
  "contract":"renulus-storage-selector/1",
  "isolation":"synthetic",
  "profileId":"synthetic-bf00",
  "generation":1,
  "authorityEpoch":1,
  "writer":"ts",
  "state":"active",
  "ownerId":"synthetic-storage-owner",
  "database":"state/renulus.sqlite3"
}
```

The `selection` argument must match every selector field. `prepared`,
`recovery`, `writer=python`, mismatched identities/epochs and aliased paths
cannot admit TS writes. A create-if-absent `state/storage-owner.json` binds the
whole selection and a nonce to the worker. Another Node worker cannot open it.
Every command and both sides of every transaction revalidate the marker,
selection, database file identity and owner file identity/content. The worker
rejects linked/junction/hardlink paths and checks existing SQLite sidecars.
Workers receive an empty environment and no inherited preload/loader arguments.

A crash or ambiguous owner leaves the lease in place. There is no PID/time-based
reclamation. Selector publishers must settle and close the existing owner before
changing selection; this BF00 file lease is **not** the BF08 Windows native
process/descendant owner or a protocol enforced by the existing Python writer.
Do not open Python writers concurrently on an admitted target. Production
handoff requires the later shared owner/settlement and atomic selector protocol.

## Transactions and compatibility

Only the worker imports `DatabaseSync` at runtime. It mirrors Python's
foreign keys, `secure_delete=ON`, WAL and 15,000 ms bounded busy handling.
Writes run synchronously inside `BEGIN IMMEDIATE`/commit/rollback, with no
cross-process or engine waits. The parent pump remains free while SQLite waits.
There are 64 in-flight command slots plus a reserved close control slot. Full
queues reject before posting work. A worker failure makes admitted outcomes
uncertain (`storage_worker_lost`); the caller must reconcile a durable receipt
before an explicit retry. This layer never retries or invokes inference.

The connected mutation is saved learning-conversation rename. It preserves the
Python request digest and existing `conversation_commands` receipt shape;
checks assistance policy and retired receipts before replay; checks owner
deletion and expected conversation revision for new work; and atomically
updates title, sidecar revision, context epoch and receipt. It does not create
another transcript. The test injects a SQLite abort during receipt insertion
to prove earlier mutations roll back. New commands should be explicit typed
local transaction functions composed here, not SQL callbacks from plugins.

`records.export` preserves `renulus-canonical-export` version 1 / schema 2,
Python's table/preference eligibility, original-path scrubbing, extraction and
case-part omissions, deletion notice and the 100,000-record / 16 MiB bounds.
Export row order is deterministic by primary key (source-status events retain
rowid chronology); Python's current exporter does not promise an order for
other tables. Unsafe integers or unsupported SQLite scalar values fail rather
than lose precision. The test compares all portable records, omission metadata
and the installed Design C column inventory to Python.

`database.backup` uses Node's actual online SQLite backup outside a canonical
transaction while retaining the command queue/owner. A safe `name` produces
`state/backups/<name>.sqlite3` via exclusive staging and create-if-absent
publication. It never overwrites another file. This machine-local raw database
backup includes canonical machine-local/configuration records, unlike the
portable export; keep it in the owned synthetic profile. It is **not** a paired
native OpenCode/originals backup or BF07 recovery generation. Python opens the
test backup read-only, checks integrity/foreign keys, queries saved messages,
exports records and validates the Node JSON bundle against its existing schema.

## Verification and remaining integration

From the repository root, without accounts/network:

```powershell
& C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe --test --test-concurrency=1 --test-timeout=60000 packages/backend/test/storage.test.mjs
```

The suite uses `C:/Renulus/dev/python/Scripts/python.exe` (`-I -X utf8`, minimal
environment) to create fresh temporary profiles through the real Python
repositories. `RENULUS_STORAGE_TEST_PYTHON` may point to another explicitly
prepared Python. No tests skip if Node/SQLite/Python are missing. Its synthetic
learning records span electrolytes, AKI, CKD, glomerular disease and transplant;
the installed content, Library revision, evidence, tombstones and conversation
messages/receipts remain populated. Profiles are removed only after clients close.

Remaining work belongs to the owning BF waves: full domain transaction functions
and facade/Effect composition; schema-1 conversion and registered closed-admission
migrations; lineage/frontiers/additive restore and paired native graph/originals
backup; Windows owner and atomic generation selection/recovery/rollback; measured
large-profile storage limits; and the compiled/self-contained BF08 bundle.
This slice supplies useful BF00 parity and ownership evidence, not completion
of BF00's host settlement gates or BF07/BF08.
