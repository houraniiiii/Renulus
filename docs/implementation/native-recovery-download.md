# Native recovery download renderer

2026-10-04 UTC. Bounded renderer lane based on integration
8bbc2cabe584ac69083fa2d872a950ab423c0d4d. Owned production files are
DataManagement.tsx, its focused test file, and desktop.d.ts. Parent retains
Electron main/preload, streamed disk writes, recovery backend, styles and
dependency ownership.

## Native save contract and behavior

The optional bridge exposes saveBackup(kind, operationId) and
cancelBackup(operationId) together. Each save uses a fresh crypto.randomUUID()
v4 identifier. The renderer captures that operation's bridge functions and
waits for its structured saved, cancelled or error result. A saved result must
contain a basename with the requested extension and a positive safe byte count.
Full paths, malformed results and rejected IPC calls produce a visible safe
failure. Neither native cancellation nor any native failure switches to Fetch
or a browser download. An incomplete native bridge refuses the operation.

Cancel download requests cancellation for the matching UUID and stays pending
until the original save promise settles. Duplicate cancellation is disabled;
a failed cancellation request allows an explicit retry. A save that completes
first is reported as saved, including its public filename and byte count. A
terminal result clears any earlier cancellation error. Unmount requests
best-effort cancellation through the captured bridge and ignores late save or
cancellation results. No token, destination path, credential or provider route
enters this renderer flow.

The parent implementation read at a0c15ef6 exposes the agreed main/preload
protocol and owns its thirty-minute abort budget. With its current Windows save
dialog, cancellation aborts the pending transfer but saveBackup does not settle
until the dialog closes. The UI explicitly tells the user to close an open save
dialog and continues waiting; it does not claim that cancellation has finished.
Parent owns any later dialog cancellation/timeout refinement.

## Browser and restore compatibility

Without the native save bridge, the existing authenticated same-origin browser
download remains available. It reads the Response body through a counted
ReadableStream reader, checks the declared and actual size, rejects empty or
truncated transfers, and constructs a Blob only after bounded completion. It
never calls Response.blob(). The cap is the smaller of the reported limit and
the existing 288 MiB ZIP / 16 MiB JSON browser ceiling, even if native backups
are allowed to be larger. Cancellation and the thirty-minute download deadline
remain active after response headers. A cancelled response cannot dispatch an
anchor or replace a later operation's result. Object URLs are released.

ZIP preview uploads still send the original File directly through Fetch.
Preview and restore request budgets are thirty minutes rather than two. The
exact reviewed export date and staged preview token remain required. ZIP
preview format remains renulus-full-backup; an omitted format_version and
versions 1 and 2 use the same validated common fields. Legacy records-only JSON
and catalogue omissions keep their existing handling.

The parent-provided GET /data/recovery envelope keeps legacy limits and adds
backup_formats with version 1/2 limits. An advertised version 2 must have valid
base limits and positive safe values within the approved caps: 8 GiB archive,
2 GiB canonical records, 1,000,000 records, 4,096 segments, 16 MiB per row and
32 MiB per segment. Malformed or unsupported advertisements produce a visible
recovery-status error and cannot enable larger-archive routes or uploads.
Unknown additive fields remain intact; internal format/segmentation terms are
not added to the main controls.

With a validated advertisement, browser ZIP export requests
/data/backup?format_version=2 and raw ZIP preview upload requests
/data/backup/preview?format_version=2 using the advertised full-backup limit.
That preview route can validate either old or new ZIP archives. Without the
advertisement, existing ZIP routes/limits remain. An advertised producer error
does not trigger a legacy retry. The advertisement survives local rebuild
results. JSON continues to use legacy routes and its legacy 16 MiB budget, even
if the full-backup limits report a different json_bytes value. Native save
continues to receive only kind and UUID; parent owns its ZIP query selection.

## Checks and limits of this evidence

The combined command below passed **114 checks in three files**, including
61 focused DataManagement journeys. Tests use synthetic ZIP/JSON bytes, native
bridge promises and real browser-style ReadableStreams. They exercise UUIDs,
native success/cancellation/error/rejected IPC, incomplete bridges, path
redaction, cancellation failure/retry, saved-versus-cancel races, unmount and
late results, body cancellation after headers, dishonest/missing size headers,
browser ceiling clamping, truncated bodies and the thirty-minute body deadline.
ZIP 1, missing-version ZIP, additive ZIP 2 and legacy JSON preview/restore
journeys preserve exact permission/date payloads. Long preview/restore and
native-save fixtures remain pending beyond 120 seconds. Unexpected routes fail
the fixtures; native-save tests permit only the independent recovery-status
request and assert no export Fetch, object URL or anchor dispatch.
Advertisement checks cover route selection, a synthetic File with a larger
declared size passed untouched to Fetch, malformed/over-budget caps, legacy
JSON bounds, failed producer behavior and retention across a rebuild result.

    $env:NODE_OPTIONS='--max-old-space-size=768'
    npm test -- --maxWorkers=1 src/platform/DataManagement.test.tsx src/platform/api.test.ts src/platform/ConnectionsPage.test.tsx
    npm run build
    git diff --check

TypeScript checking, the production Vite build and Electron compilation pass.
Initial timer fixtures were corrected to render before querying controls and to
persist the synthetic restore result before the recovery-status refresh. No
production lifetime or validation checks were relaxed to make fixtures pass.

This lane proves renderer behavior and builds. It does not establish a real
Windows dialog/disk-save, multi-GiB memory/disk measurement, actual format-2
segmented archive round trip or installer proof. Parent must integrate the
Electron helper/main/preload revision with this renderer, build that combined
revision, and verify save, cancellation, destination preservation and the
new backend archive envelope. Its native ZIP request must opt into version 2
as agreed; the kind/UUID consumer protocol does not change. No private profile/originals or live
generation/provider credentials were used.
