# Flow desktop implementation evidence

Lane #3, build/flow-desktop, October 4, 2026. Write boundary is apps/desktop/,
PRODUCT.md, DESIGN.md, .impeccable/ and this file. Shared foundation fffa82c
was cherry-picked as 524ee7d; no main edits or merges were made.

The initial foundation provides React/TypeScript Flow chrome, all eight routes,
native destination search, scope-aware volatile handoffs, shared tokens and
controls, same-origin API v1 JSON/SSE transport, cancellation and async recovery.
Connections consumes the runtime lane's exact public operations. Missing modules
show explicit integration states; no synthetic records, Ask responses or counts
are production state. Learn's empty entry is reserved for the integrator.

Interface Design and Impeccable were applied. Impeccable context ran once via
the installed Windows cmd launcher. Product truth comes from the explicit user
brief and project documents; Flow had already been selected. The actual Flow
code and home screenshot were inspected. No new direction interview was needed.
Source details and upstream file hashes are in apps/desktop/THIRD_PARTY_NOTICES.md.

Foundation checks: npm install completed using exact pins; typecheck passes.
Transport tests exercise JSON/error boundaries, malicious paths, credential
header stripping, caller abort, split UTF-8/CRLF/multiline SSE and stream abort.
Scope tests exercise Cases → Learn/Test/Library inheritance and a synthetic
sentinel absent from URL/history/localStorage/sessionStorage. Renderer build and
final test outcomes are recorded with the foundation commit in GitHub #3.

Native lifecycle/packaging and visual verification follow the foundation handoff.
Native launching, clean-machine installation, live authentication/inference and
clinical accuracy are not established by the renderer checks.

## Dependency security correction — October 4, 2026

The desktop manifest and regenerated lock pin Electron 44.5.1 and Vitest 4.1.11.
The Electron GitHub release was published September 30, 2026; npm
reports it as the current stable release. Primary advisory
GHSA-gr2m-v5gq-v685 lists the older branch threshold as 41.10.6, so the audit
suggestion of 40.10.6 was not used. Vitest
GHSA-82fw-gwwq-j7x9 fixes the redirect-mock file-read issue in 4.1.11.

Primary evidence was fetched with gh from:

- https://api.github.com/repos/electron/electron/releases/tags/v44.5.1
- https://api.github.com/repos/electron/electron/security-advisories/GHSA-gr2m-v5gq-v685
- https://api.github.com/repos/vitest-dev/vitest/security-advisories/GHSA-82fw-gwwq-j7x9
- https://api.github.com/advisories/GHSA-jmr9-qjv8-65gv

The last advisory still lists extract-zip <=2.0.1 with no patched version.
However Electron 44.5.1 itself adopts @electron-internal/extract-zip; the
new lock resolves its maintained 1.0.5 and no longer contains extract-zip.
No local extractor replacement or npm audit fix --force was used. Both the
updated graph and a clean npm ci graph report zero npm audit findings.
This is dated dependency evidence, not a claim that an audit proves security.

npm 11.17.0 policies permit only electron@44.5.1 and esbuild@0.28.1. The
unused Squirrel electron-winstaller install hook is explicitly denied; this
lane's packaging config selects NSIS. esbuild's pinned postinstall ran during
clean npm ci. Electron 44 has an explicit/on-demand installer rather than an
npm postinstall; scripts/install-electron.mjs verifies the official archive
before invoking Electron's own pinned install.js with only OS environment
and a lane-owned artifact cache. No other lifecycle scripts were approved.

Official Windows x64 archive SHA256:
9b382492dcfee91f8f9e92c91f7972550a1b95d2299cac72279dab33a600d7db.
It matches the release asset digest, fresh SHASUMS256.txt and the npm-package
checksums.json. Installed electron.exe SHA256:
49b61a030a520fc36a4b8fa5cce53fb4e935a7bdbbe4b80e9222f598e49cc7fa.
The maintained extractor's Windows x64 binding SHA256 is
17746910bcd13f7f268822f6fc837706f8b5be0704bbf49570112117982e7b07.
esbuild's Windows x64 binary SHA256 is
ec02ee9b14ab332416fedd10614dfb80eed5304d94f67745067c011934a8c3c3,
matching its package-published binary hash. Package SRI digests are in the
committed lock and the untracked test-results/electron-install/provenance.json.

Windows file locks initially prevented npm ci while this lane's two Vite
previews were still running. Those two owned Vite processes were verified and
stopped, then npm ci succeeded. Other lanes and the integration backend were
not stopped. The production renderer/Electron build and typecheck pass with
the new pins. The first parallel Vitest run hit a navigation worker startup
timeout after 23 passing tests. npm test -- --maxWorkers=1 --pool=threads then
passed all 26 tests across five files, including navigation isolation.

## Patched native lifecycle and Connections handoff

Electron main now owns an isolated local backend, authenticates its readiness
and stops only its owned child. The attributed unchanged Hermes lifecycle
helpers handle startup cancellation, Windows process-tree fallback and window
focus. The renderer is served from a loopback origin with CSP/no-store, sandbox,
context isolation and a nonpersistent partition. Main injects the session token;
it is absent from the renderer bridge. Wrong Host/Origin and unauthenticated API
requests are rejected. Sign-in only opens HTTPS auth.openai.com at the exact
/api/accounts/authorize path; callback ownership stays with the backend.

Development can attach to the integrator's explicit loopback URL/app-only token.
This path never adopts or kills the shared backend. Shipping defaults still
require a managed verified backend bundle. The Windows Hermes fallback uses
taskkill /T /F, so successful process exit does not prove FastAPI lifespan hooks
ran. That shared control-pipe/graceful-shutdown request was relayed in runtime #2;
the integration owner retains server ownership.

Connections consumes the public runtime JSON operations with no fabricated
availability. A pending known OAuth login is cancelled with keepalive on page
exit. Transient polling errors keep the cancel control available. An explicitly
entered key is cleared immediately and does not auto-select the provider.
Four synthetic UI tests exercise these behaviors; no account or provider request
was made. Final npm test -- --maxWorkers=1 --pool=threads passes 30 tests across
six files, and npm run build passes including native compilation.

Actual Windows Electron 44.5.1 proof directories under apps/desktop/test-results/:

- native-f851f6c6-00b8-4e7c-aba8-6162bc4ac1be: two simultaneously isolated
  instances, distinct main PIDs/userData/sessionData, one owned Python backend
  each, authenticated meta, nonpersistent sandboxed renderer, unauthenticated
  request rejected with 401, external authorization rejected, all eight routes,
  destination search and no horizontal overflow at 640 px. Both owned backend
  PIDs are absent after app close. The interpreter was the explicitly selected
  integration .venv CPython 3.14.4; the managed source was this lane's foundation.
- native-7d412cff-6b64-4dba-97e4-ff42dd9f0816: two independent native profiles
  attached to integrated F0 runtime on port 18765, zero adopted child processes,
  public Connections reports both providers disconnected and all model
  availability unknown. Image input is unverified. Shared backend still
  authenticates after both desktop instances close.
- browser-c4a4dd5f-5adb-48e1-b503-31443710992a: real Vite preview against the
  integrated runtime, all eight routes, zero page errors, same honest Connections
  state, no horizontal overflow at 390 px, three captures.

Playwright 1.62.1 was explicitly installed as temporary unsaved test tooling; it
did not change manifest/lock. The browser uses Chrome in its own synthetic
profile; native uses the checksum-verified Electron binary. Four final desktop/
Connections/compact captures were actually opened and reviewed in one bounded
batch. Flow hierarchy/tokens remain coherent; no clipping or material defect was
observed. Shared shell/UI and the integrator's Learn/Study/Updates files were not
rewritten. Earlier Electron 40 captures are superseded.

This proves source/native lifecycle and disconnected runtime display, not a
self-contained installed product, signed installer, live account login, model
generation or image capability. The integrator's newly verified 19 helper files
(483,597,181 bytes) are available for an unsigned backend/helper bundle next.
Only those public helper assets may be acquired from its profile; provider
credentials, SQLite data and other private state remain outside packaging.

## Embedded Windows payload and packaging lane #12

October 4, 2026 UTC (October 5 locally after 22:00 UTC). Owned packaging uses
official CPython3.14.4 embeddable x64, not the development venv redirector.
The ZIP SHA256 is cda80a9b1e75c0f1b4f9872ca1b417f0d19bce32facc811aea9180e70fad5fb9;
extracted python.exe SHA256 is
7ca24f26d6e3f463419ee4f537ddd3acd312c38fe45e678cce08572f26a8bd1a.
Windows Authenticode actually reported Valid / Python Software Foundation.
The published Sigstore digest matched the archive; full Sigstore signature
verification was not performed. python314._pth admits only bundled Python,
selected Windows wheels, runtime and attributed Hermes source. It does not
import site. No pyvenv.cfg, launcher wrappers, executing .pth or editable
direct_url.json are copied. Native dependency imports were checked with this
embedded interpreter; final relocated/installed launch checks follow below.

stage-backend.py snapshots a committed public allowlist and records all file
sizes/SHA256, wheel versions, source revision and explicit runtime patch
provenance. docs/SOURCES.md is included because Updates reads that public
register at runtime. Original/private .local state is excluded. Only the
declared 19 public helpers / 483,597,181 bytes are copied and hash-checked against
read-only packaging/runtime/helper-assets.json. Contract SHA256 is
3d8ba8f76428f2c7fc0348167dd9b8c70e2f47f29dbd6705e01a6c0fdea97fce.
Original helper names/model cards and additional observed licence texts are
preserved; no broad legal-compliance claim is made.

Source refresh operates only in this lane's generated test-results payload,
refuses any uv.lock/pyproject.toml change, preserves selected wheels and removes
deleted admitted source files. A new inventory is required afterwards. Eight
synthetic packaging boundary tests pass on actual embedded3.14.4, including
private-state exclusion, additive migrations/markers, acquired-manifest hash
protection, patch conflict refusal, dependency preservation/lock refusal and a
real Windows junction rejected before traversal. Expected Git conflict stderr
in the refusal test is not a test failure.

The e800affc source snapshot initially staged 39,218 inventoried files /
2,168,719,551 bytes before the public-register/bootstrap refresh. Renderer and
native entry built/typechecked from the same committed source with the owned
backend.ts adoption recorded as a patch and hashes. Parent main/profile/shared
modules stay untouched. Packager checks matching backend/renderer/native source
revisions and the installed Electron pin. Lane npm ls reports Electron44.5.1 /
Vitest4.1.11; electron.exe still hashes to
49b61a030a520fc36a4b8fa5cce53fb4e935a7bdbbe4b80e9222f598e49cc7fa,
matching this lane's verified official archive provenance. Parent's formerly
stale node_modules are not used for packaging.

An actual unsigned x64 folder build passed with electron-builder27.0.0-alpha.6.
Its v27 schema requires nativeModules.npmRebuild/nodeGypRebuild. Signing is
explicitly disabled. NSIS toolset1.2.1 / NSIS3.12 and 7-Zip toolset1.0.0 are
pinned; official release asset hashes match installed builder checksum tables:
56997fdefe25e7928a1a68b4583d08b240b66cf660234053b20131a74cc082f4 and
be071f15bd6da2f78fe81c6ddef2009b0c4d8a51f36b780cb806c7e6df95e1b3.
That folder build alone does not establish installer execution.

The first relocated launch failed during helper provisioning: a .copying
destination was262characters while machine LongPathsEnabled is0. A controlled
bootstrap reproduction captured FileNotFoundError on the approved TableFormer
asset; no provider/account call occurred. The owned bootstrap now uses Windows
extended filesystem paths for that unchanged copier. No registry mutation or
helper renaming is required. The failed proof's attributed main/tree was stopped;
no shared backend or other application was stopped. This negative evidence is
retained; a corrected native pass is not inferred from a build.

The stable planned executable is release/renulus-portable/Renulus Development.exe
with adjacent resources/backend and plain licences/notices. NSIS is configured
per-user with no elevation, automatic launch or generated shortcuts; uninstall
preserves app data. Parent owns root launchers and .local/delivery.json.
native-evidence.mjs verifies packaged44.5.1, OS-only PATH, absent Python/uv/Node,
one managed child per isolated profile, helper/import readiness, all modules,
sandbox/authentication/routes and owned-child exit. native-journeys.mjs uses
declared synthetic Library DTO/PDF responses to inspect the physical page2
viewer and a real Updates publisher link; it is not extraction/indexing proof.
Actual final native/installer results and artifact hashes will be added after
those checks run. No live model/authentication or signed/clean-machine proof
is claimed by these staging results.

Controlled embedded startup subsequently authenticated in154.936seconds with an
OS-only PATH. All10 backend modules were installed; both helper groups and their
dependency imports were ready. Providers stayed disconnected, capabilities
unknown, CPU2 controls active, and warmup reported no downloads or model
instances. The trace showed progressing cold SDK/Docling/Transformers imports,
not a startup exception. This is backend readiness evidence, not native launch.
The owned native startup budget is now300seconds so it covers that measured
startup; it remains bounded and cancellable. Slow cold startup remains a known
delivery limitation. Native evidence uses compact independent synthetic profile
paths and records each actual startup duration.

Nine synthetic packaging tests now pass in7.682seconds on embedded3.14.4. The
added Windows regression actually writes and atomically renames a262-character
temporary helper path to its254-character final path using extended filesystem
paths. No machine registry change is required. Bootstrap imports are safe for
this narrow regression test; provisioning still executes before server startup.
The matching e800affc renderer/native checkpoint rebuilt and typechecked after
the owned startup-budget change, with parent main/profile bytes preserved. Final
source staging remains held for the parent's completed integration revision.

Actual relocated unsigned native proof passed for the approved e800affc
checkpoint. `release/renulus-portable/Renulus Development.exe` ran Electron44.5.1
with two fresh independent synthetic profiles and one managed backend each.
Observed startup was147.267s and114.422s. Both owned backend PIDs (32124/228)
were gone after closing their owning apps. Actual embedded3.14.4 remained
isolated/no-user-site, prefix equalled base_prefix inside the relocated payload,
and every Python import path stayed inside resources/backend. Python/python3/py/
uv/Node/npm did not resolve on the child environment's OS-only PATH. All10
backend modules loaded; helper assets/imports ready; provider state disconnected.
The proof also passed sandbox/context-isolation, nonpersistent browser session,
renderer authentication/direct401, rejected untrusted sign-in URL, all8 routes,
destination search and compact layout. Native screenshots were inspected.
Evidence: apps/desktop/test-results/native-a33a0374/native-evidence.json.

The integration adds a pre-runtime opening window so the measured cold setup is
visible. It uses Flow palette values, accessible status copy and reduced-motion
support. This ephemeral window has no preload, JavaScript, network access or
permitted device actions. Closing it uses the existing owned-process cancellation
path. The real Flow window replaces it only after the frontend is ready, and
explicit activation can focus either current surface. The integrated full build
and the final Electron compilation passed. Actual first-display timing, closing
during startup and the packaged handoff are pending native lane verification;
the compile result is not that proof.

This checkpoint predates the parent's protected startup window7aa7f080. Native
scripts now observe the first visible native window separately from the actual
visible loopback Flow renderer and authenticated backend readiness, ignoring
transient data URLs for renderer selection. A real Electron44.5.1 synthetic
two-window regression observed the opening window at0.894s and loopback renderer
at5.401s; the opening window closed before selection. This tests proof-script
selection, not the actual parent's lifecycle or installed app. Final native proof
will require the protected early startup window and close it while its physical
backend child is starting. Serial mode checks each attributed child exit before
starting another instance; concurrent mode separately checks other attributed
instances survive. No parent main/profile/startup-window edit is made here.
Final matching source staging and installer proof remain pending.

The first real relocated Library viewer journey did not pass. Its valid original
two-page synthetic PDF opened a blob URL with #page=2, but the screenshot was
blank and the child frame was chrome-error://chromewebdata/. The previous
body-text-only detector missed that empty error frame; the screenshot review
caught it. Evidence: test-results/journeys-3d881a35. This is retained as negative
evidence, not a PDF pass. The owned detector now treats Chromium error frames,
absent viewer content and wrong physical-page selection as failures, captures
console/failed requests, and returns a nonzero result after the independent
publisher-link check. Three regression checks pass, including the exact blank
error-frame shape. The synthetic fixture bytes remain unchanged.

Actual pinned Electron44.5.1 policy diagnosis isolated two independent blockers:
default-src self rejects blob framing; after explicit frame-src self blob, the
session filter rejects Chromium's PDF extension CSS/index and then its chrome
resources. The smallest tested working variant adds frame-src self blob to both
document/header CSP and admits only the exact built-in PDF extension host
mhjfbmdgcfjbbpaeojofohoefgiehjai plus chrome://resources/ in the session request
filter. It keeps object-src none, sandbox/context-isolation/web-security and
plugins false. The native viewer's pageSelector was2; a viewed screenshot shows
RENULUS - PAGE TWO and the large2. No request failures remained. Evidence:
test-results/pdf-policy-25fa42bb/pdf-policy-evidence.json and
exact-builtin-frame-only.png. This establishes a policy-fixture remedy, not a
fixed packaged product. Parent owns main.ts/index.html/frontend.ts integration;
the desktop lane has requested the scoped shared change before final staging.

The real relocated Updates publisher action separately completed shell.openExternal
for https://kdigo.org/guidelines/, with one renderer window remaining at the
local Updates route. Read-only observation of that existing Chrome tab confirmed
the title Guidelines - KDIGO, matching public URL and visible Guidelines heading.
No browser navigation was used to manufacture that observation, and no account
or provider call occurred. No final source revision or installer proof is implied.

An unchanged committed parent-native source proof passed for protected opening
window revision 7aa7f08024bc7667d526ce7b867cc85cf918cefa. The script snapshots
the committed Electron source into this lane, records source hashes and compiles
it without a main/profile/backend substitution. Actual Electron 44.5.1 displayed
the static opening surface in 2.356 s. Its policy had JavaScript disabled, no
preload, sandbox/context isolation enabled, no node integration and a
nonpersistent session. Closing it before backend readiness stopped its physically
owned embedded Python child 34448 in 13.464 s; no Flow-origin window existed yet.
The independent shared backend PID 22620 remained alive. Evidence:
test-results/opening-1eb1265c/opening-evidence.json and the inspected
protected-opening-window.png. This is a nonpackaged early-close source proof,
not final renderer handoff, helper readiness or backend shutdown-callback proof.

The approved e800affc checkpoint also built a real unsigned NSIS installer.
release/checkpoint-e800affc/Renulus-Development-0.1.0-windows-x64-setup.exe is
965,788,144 bytes with SHA256
69703a8a6bb61640f25b6b827dec24f20b117c769e65b77d5489f0da75008722 and
Authenticode NotSigned. Its actual silent installation into a fresh owned
release/i-e800 directory exited 0 in 578.547 s. Installed source/runtime contracts
matched e800affc and embedded CPython 3.14.4. Installed executable SHA256:
65f50ff38c5a51b19e6aed0c49cfeb1ce1d0a99f9a4696cfafb4b590dc8a652b;
app.asar SHA256:
2946c6894603bfa652d2728900732aad4f8bc1c0372d02f79ddc9ecc93102523.
Evidence: test-results/installer-d64909c8/installer-evidence.json. That report
correctly records extraction only; native launch was held during shared resource
coordination and proved separately after the parent released the heavy process.
No signed, clean-VM, uninstaller or original-profile claim follows from it.

Actual installed native launch subsequently passed on October 4, 2026 at
23:30:34 UTC. release/i-e800/Renulus Development.exe used Electron 44.5.1 and
its physically relocated embedded CPython 3.14.4 with only Windows
System32/Wbem on PATH. Python/python3/py/uv/Node/npm did not resolve;
isolated/no-user-site flags were 1,
prefix equalled base_prefix, and all import paths stayed inside the installed
resources/backend tree. Fresh profile A authenticated in 139.971 s (full startup
checks 140.032 s); fresh profile B authenticated in 42.102 s (checks 42.123 s). The
profiles ran serially, with one owned Python child each, and both children
32636/17924 were gone after closing their owning apps. All 10 modules and
controlled CPU helper assets/imports were ready; providers remained disconnected.
Sandbox, nonpersistent session, renderer authentication/direct 401, rejected
untrusted sign-in URL, all 8 destinations, search and compact layout passed.
The new installed screenshots were opened and inspected. Evidence:
test-results/native-9e788d63/native-evidence.json.

The same installed executable then restarted the previously provisioned profile A
after both fresh instances had closed. The real renderer appeared in 31.629 s,
renderer readiness was 31.971 s, and authenticated backend/status checks completed
in 34.787 s. The new main PID 32416 retained the original profile and one new
owned backend child 25560; that child was gone after close. This is a measured
same-profile restart with provisioned helpers; OS caches are uncontrolled. It
must not be inferred from the two different fresh-profile timings. This older
checkpoint has no protected opening window, and its PDF policy remains the
previously reported blocker. Final matching source staging remains held for the
parent complete revision, protected opening handoff, PDF policy adaptation,
source bridge and late module/recovery handoffs.

Owned proof tooling now supports serial native instances, a separate opt-in
same-profile restart, actual guarded NSIS installation and a required optional
public-source IPC bridge journey. The Library fixture uses the full paginated
list envelope while preserving its exact document route and synthetic PDF.
Installer targets must be fresh absolute paths inside this lane release tree
without junctions/symlinks; no existing profile or folder is replaced. Three PDF
detector regressions and syntax checks passed. The installer and native source
proofs above exercise these tools on actual Windows; no extra model, OCR
conversion or provider inference was run.

The user assigned the native lane the previously requested PDF policy
prerequisite at 23:34 UTC. The narrow product patch adds `frame-src 'self' blob:`
to both CSPs and permits only Chromium's built-in PDF extension origin and
`chrome://resources` in the existing session filter. Other extension/internal
origins, external HTTP(S), credentials and ports remain outside that exception.
It keeps `object-src 'none'`, existing navigation restrictions and window
sandbox/context isolation; no plugin or viewer-library change is needed. The
patch only changes main.ts at an import and the existing request predicate,
preserving parent startup/source-link integration when cherry-picked.

Sixteen actual Vitest 4.1.11 checks passed in 1.40 s for the public-resource
boundary, both real HTTP/header and index meta CSPs, and the existing
authenticated streaming proxy. The TypeScript, Vite and Electron production
build passed. The prior pinned Electron seven-variant fixture establishes the
physical-page remedy; final matching packaged renderer verification remains
pending. Parent may take main/preload/desktop types for the recovery download
seam after this policy commit; this lane continues only proof/packaging paths.

The actual production-policy native fixture then passed on Electron 44.5.1.
It compiles the real frontend proxy and exact PDF resource helper, uses the
unchanged index meta CSP, and records their source hashes at commit 81d14dbb.
The built-in viewer rendered the synthetic blob PDF at physical page 2 with no
failed requests; the new screenshot was inspected. Evidence:
test-results/native-platform-ffdb0418/native-platform-evidence.json and
production-policy-page-two.png. This verifies production policy functions with
a synthetic window/backend; final matching product packaging remains separate.

That same lightweight native instance streamed 33,554,432 synthetic bytes
through the existing frontend proxy using webContents.downloadURL. The owning
webContents ID remained 1 in onBeforeSendHeaders and will-download; the existing
main session hook injected authentication without renderer token exposure. The
completed disk file SHA256 was
371036ccdfc733fa30542a26a4f276536147c906d1570f0becc1d6f8b868c311.
A second DownloadItem was cancelled after 2,359,296 received bytes, closing
the upstream response without finishing the transfer. The proxy drops total
length/disposition, so totalBytes was honestly 0 (unknown), while received-byte
updates worked. Official v44.5.1 web-contents/download-item docs were read for
these APIs. Save-dialog options were set but an owned automated path was used;
this is not user-dialog interaction, a valid recovery ZIP, multi-GiB capacity,
or the parent sibling-partial/fsync/rename implementation proof.

Main/preload/desktop types were explicitly released to parent after 81d14dbb.
The pending integration chain after already adopted 1fbe78d1 is 06347499,
bf1c6835, then 81d14dbb. This final proof follow-up changes only its standalone
script and this evidence document. Parent owns the backup-download helper and
actual save/cancel IPC wiring; no concurrent native entry edit occurs here.

The explicitly released parent recovery changes a0c15ef6, 32d72e78 and fdc2356d
were adopted locally as 8f3d7035, fb5037fb and 93f4bb8c. These are prerequisites
already owned by parent, not new desktop handoff patches. The tracked lane shell
predates the protected opening window, so the native recovery proof uses a fresh
untouched git-archive desktop snapshot at exact parent commit
fdc2356dbd17757101927ba9b07bafc00847622f. That snapshot typechecked and built
with the actual installed Electron 44.5.1. Its backend.ts source/adoption SHA256
values are equal; source main and compiled main hashes are checked before launch.

Actual Windows Save dialogs passed four operations in one serial source instance.
The renderer used the unchanged product preload and main save/cancel handlers.
The test operated only its PID-owned #32770 dialogs and scoped filename/button
controls, including the actual overwrite confirmation. No showSaveDialog
substitution or returned-path override occurred. A test-only Node open guard
rejects sibling partials outside the synthetic export directory and otherwise
calls the original I/O unchanged. All recorded partial opens were confined.

At test-results/native-save-99d0e54c/native-save-source-evidence.json the selected
existing synthetic destination stayed intact while a 196,608-byte sibling partial
was observed. Completion promoted 67,109,006 bytes with SHA256
4fc194db694249da152cfedf8d6f2c376d3a3ae26a10a2c877572e56f9d64c5e. This is a
valid ZIP of 64 MiB synthetic bytes plus container overhead, not a Renulus recovery
archive or multi-GiB capacity proof. A second transfer was cancelled after
262,144 bytes: the existing sentinel was unchanged, the partial was removed, and
the upstream stream closed without finishing. A deliberate bounded 409 API error
preserved its sentinel and error code. Real native dialog Cancel returned
cancelled without a fourth transfer. No sibling partial survived any operation.

The visible protected opening window was observed at 2.448 s and the actual
loopback Flow renderer at 3.317 s; its data-URL predecessor was gone. These timings
use a declared attached transfer-only server with its first metadata response
delayed 1.5 s. They do not measure production backend readiness, managed Python
startup or the Home module. That instance had no Python child; main PID 27820 was
confirmed gone after close. Source Flow screenshot and control reports are saved
with the evidence. The filename/button strip could not be captured because the
dialog was not the foreground window; the positive claim is actual programmatic
native-control operation and resulting I/O, not a manual visual dialog review.

Earlier negative harness trials found a Windows dialog variant with an
unnumbered filename ComboBox, unsupported native Edit ValuePattern, and virtual
overwrite Yes button. WM_SETTEXT changed displayed text without updating the
dialog's cached filename. One synthetic ZIP reached the dialog's default basename
renulus-backup-2026-10-05.zip; its location remains unresolved and no positive
promotion claim uses that run. The negative evidence is retained at
test-results/native-save-b96f211f. Further trials first installed the output guard
and typed through owned EM_SETSEL/WM_CHAR events, which selected the expected
synthetic paths. No private originals were read or transported while diagnosing
that negative test. The default-location artifact remains a cleanup item for its
owning workspace once its synthetic hash/location are established.

The parent format-2 route/helper tests pass 5 checks on actual Vitest 4.1.11 in
2.04 s. The proof scripts pass Node syntax and PowerShell AST parsing. This native
phase leaves main/preload/Connections/shared UI untouched. The e800affc unsigned
checkpoint installer and installed/portable folders are preserved, with its
original 69703a8a...08722 installer checksum rechecked after reservation in
release/checkpoint-e800affc. Final matching renderer/backend/native staging,
real producer/segmented recovery semantics, relocated final native journeys and
matching unsigned installer remain gated on the parent explicit final revision.

A further replay at test-results/native-save-e0b5b46e passed all four operations
with compiled-main integrity and an explicit server-side assertion that every
authenticated GET used /api/v1/data/backup?format_version=2. Opening was visible
at 1.008 s, the loopback renderer at 2.467 s, the observed cancelled partial was
327,680 bytes and the upstream closed after 393,216 sent bytes. Main PID 35844
was confirmed gone. The completed ZIP checksum was unchanged. This verifies the
actual v2 request path, while the archive body remains the declared synthetic ZIP.

The matching delivery driver now requires an exact parent commit and fresh owned
renderer/output directories. It refuses changed Windows wheel locks, desktop
manifest/lock divergence, missing integrated backend/bootstrap adoption, helper
anchor changes, a different Python archive or an installed Electron mismatch.
Before execution it verifies the complete acquired public payload inventory,
then refreshes only public committed source, compiles renderer/main/preload and
requires all three revisions and the native adoption hash to match. It packages
to a separate release/matching-<revision8> directory, preserving checkpoints, and
records hashes with native-launch evidence explicitly pending. The launcher can
use that directory's win-unpacked/Renulus Development.exe; unsigned NSIS output
uses the same directory when --package installer is selected.

A read-only --plan-only run against 35f874b52eb86fe71aa94949b0c8c69b482c8f18
passed with the unchanged selected locks, actual Electron 44.5.1 artifact,
official embedded CPython 3.14.4 checksum and trusted 19-file/483,597,181-byte
helper contract. It did not refresh/package or launch a backend. Twelve real
synthetic boundary checks passed in 7.245 s, covering the existing source/wheel/
helper inventory boundaries plus moving-ref, checkpoint, escape and changed-lock
refusals. No final delivery revision was inferred from the moving parent branch.

That exact 35f874b5 desktop source was separately archived, typechecked and built
with unchanged main/preload/backend plus recorded source/bundle hashes. The
existing native journey tool can now exercise this immutable source entry with
declared synthetic Library/original fixtures before installed packaging. In
test-results/journeys-95450eb4/journey-evidence.json the real Library inspector
loaded a blob PDF at physical page 2 under the committed CSP/request policy, with
zero failed requests, a detected built-in viewer and a selected page 2. The
library-pdf-viewer.png screenshot was inspected and visibly reads RENULUS - PAGE
TWO with the large 2 marker. No acquired/private original was used.

The actual openSource preload/main IPC called the original OS shell.openExternal
for the public KDIGO guidelines HTTPS reference. Dispatch completed, the renderer
stayed at its local Library URL and one renderer window remained. The test only
observes the original OS dispatch, not browser page load, and does not operate
the parent's tabs. The first protected opening was visible at 0.791 s and the
source Flow renderer at 2.377 s with delayed fixture metadata, independently of
real backend readiness. The source instance closed before further native work.
Final matching installed Library/source-link and producer recovery journeys still
require the explicitly frozen parent revision.

The actual committed DataManagement consumer then passed the same four native
dialog operations at that exact 35f874b5 source. In
test-results/native-save-bdd5df8f/native-save-source-evidence.json, the tool
navigated Connections to Your study data and clicked Download full backup (ZIP).
The unchanged renderer chose its real preload/main native bridge; the proof did
not call saveBackup/cancelBackup directly for these positive operations or
replace their results. Its recovery, empty-account and health reads are explicit
synthetic fixtures, separate from real producer/recovery semantics.

The UI disabled duplicate saves while pending. A 131,072-byte sibling partial
was observed with the existing synthetic destination intact; completion promoted
67,109,006 bytes with the same 4fc194db...64c5e checksum and displayed
Full backup saved: promotion.zip (64 MiB). Cancel download stopped the second
transfer after an observed 262,144-byte partial, preserved its existing sentinel,
removed the partial and displayed Backup save cancelled. Upstream closed
unfinished after 589,824 sent bytes. The deliberate 409 displayed its bounded
message and preserved its sentinel. Actual native dialog Cancel displayed the
cancelled notice without starting a fourth transfer. Each operation re-enabled
the download button and left no sibling partial. All three authenticated
transfers again requested /api/v1/data/backup?format_version=2.

These notices are recorded as renderer observations, never intercepted IPC
return objects. Real PID/control-scoped Windows dialogs and the existing
synthetic-output guard were reused; no path-result substitution occurred.
Source and compiled preload hashes matched their recorded provenance, alongside
the existing main/renderer/backend checks. The final Connections screenshot was
inspected and shows the cancelled notice and available save button. Node syntax
passed. Opening was visible at 1.514 s and the loopback renderer at 2.805 s with
delayed fixture metadata; these are not real backend/Home startup timings. Main
PID 33884 was confirmed gone. No clean delivery profile or heavy backend was used.

The read-only installer plan also passed against reported parent checkpoint
54cbeb6d1dc6c4ab537dd7d3aeafcf328ea7d7bc. It verified unchanged dependencies,
integrated backend adoption, embedded Python/Electron pins and the same trusted
public helpers. It did not refresh the payload, package, create a delivery
directory or launch an app. That checkpoint is not an inferred final freeze.

The final packaged journey has an opt-in RENULUS_EXPECT_PRODUCT_BACKUP=1 gate.
It is confined to the packaged app and the journey's disposable profile. It
creates one synthetic manual study goal through the real authenticated API,
uses the unchanged DataManagement button and actual Windows Save dialog, then
inspects the saved ZIP with that bundle's embedded Python. The inspector checks
format 2, complete member/table/count inventory, segment/original byte hashes
and the exact retained synthetic memory row. It also operates actual dialog
Cancel and checks the prior saved archive is unchanged with no surviving partial.
This reuses the existing serial native app rather than starting another backend.

Six synthetic archive integrity checks passed in 0.059 s: complete inventory,
changed segment/original hash, omitted expected row, undeclared member and
duplicate segment. Both Node modules passed syntax; inspector syntax passed.
These checks do not constitute native producer execution, restore or multi-GiB
proof. Actual execution is pending the explicitly frozen matching bundle.

The user reported an actual fresh development .venv server exceeding the old
30-second listen deadline. A focused regression reproduced that cutoff: an
owned development child with authenticated readiness at 45 seconds was killed
before readiness, while the packaged mode passed. Both managed modes now use
the same finite 300-second cold-helper budget. They warm the same approved CPU
frameworks; prior real packaged cold startup measured 139.971 seconds, and the
reported development start also exceeds 30 seconds. Attached development
backends retain their existing authentication path; no process is adopted or
stopped by that path.

Four focused virtual-clock lifecycle checks pass: development and packaged
readiness at 45 seconds, no premature development teardown at 299 seconds with
owned-child cleanup at the five-minute limit, and cancellation while a late
readiness request is in flight. They mock only OS process/listener/transport
boundaries and exercise startBackend itself, without launching helpers. Together
with the five existing actual-pin native download checks, nine Vitest 4.1.11
checks passed in 1.07 s. TypeScript passed. This is timeout/cancellation rule
evidence, not a new measured Windows cold launch. No expensive proof was repeated.

The six archive integrity checks also passed in 0.072 s under the preserved
actual NSIS-installed embedded CPython 3.14.4 at release/i-e800/resources/backend/
python/python.exe. The process used -I -B and an OS-only System32 PATH;
python.exe, uv.exe and node.exe were not discoverable through command lookup.
This confirms the inspector's standard-library compatibility in the installed
relocated interpreter. It did not start the native app, warm helpers, modify
the installed runtime or touch a user/delivery profile. Final matching native
producer/archive execution remains pending the explicit source freeze.

On 2026-10-05 the parent reserved exactly E:/Renulus-native-delivery/
desktop-20261005 for fresh final public outputs. Delivery, electron-builder and
installer guards now admit descendants of that root as well as the existing
desktop release tree. They reject the root itself, sibling prefixes, other
drives and parent escapes; existing output and install targets still refuse
replacement, and reparse ancestors remain forbidden. All C checkpoints and
the earlier installer are preserved. No rejected deletion was repeated.

Build commands and NSIS receive fresh E scratch directories through their own
child environments. Host TEMP/TMP remain unchanged. A real lightweight child
under PowerShell 7.6.6 and Windows PowerShell 5.1.26100.9444 separately observed
the reserved E TEMP/TMP, used GetTempPath and wrote its synthetic marker there.
Both exited zero, with evidence under the exact E temporary root. These are
child-environment checks; they do not claim a new NSIS install. Six delivery
boundary/dependency tests pass. Five direct electron-builder configuration
loads also accepted the authorised descendant and rejected four external/root
escapes. Node syntax and PowerShell parser checks passed.

The read-only installer plan passed against immutable parent
6abd3ae9b0d0eebe7ba4468290312f3c4286d7f9 with E output and temporary paths,
Electron 44.5.1, embedded CPython 3.14.4 and the same 19 public helpers
(483,597,181 bytes). test-results/plan-6abd3ae9-e.json records it. This did not
refresh source, create the planned package directories, start a backend or
access either clean delivery profile. Final matching package/install/native
producer proof remains pending the explicit final frozen revision.

The parent then required every final generated directory to start on E because
C had fallen below 1 GB free. The matching driver now first verifies the
preserved C public input inventory, copies it to a fresh guarded E payload and
copies the pinned installed Node build environment to E. Source refresh occurs
only in that new E payload. Renderer/native source snapshots, build working
directory, tool caches and child TEMP/TMP are on E from the start. Python and
Node developer executables, the official Python archive, public helper source
and existing locks remain read-only inputs. No venv wrapper is distributed.

Fresh synthetic native profiles, proof screenshots/archives and installer
evidence can now use exactly E:/Renulus-native-delivery/desktop-20261005/proofs
via RENULUS_NATIVE_EVIDENCE_ROOT. The producer proof still verifies that its
packaged app uses the fresh profile inside its own evidence directory. Child
native apps and Windows dialog helpers receive an evidence-owned E TEMP/TMP.
No existing profile, model asset profile or credentials are relocated.

Seven Python path/dependency checks and three Node confinement checks passed
with their new scratch on E, including an actual Windows junction refusal.
Python/Node syntax and PowerShell parser checks passed. The read-only all-E plan
against 6abd3ae9 is recorded in E:/Renulus-native-delivery/desktop-20261005/
plan-6abd3ae9-all-e.json; it created no payload, source snapshot or build.

Review of the installed pinned electron-builder NSIS installSection.nsh and
installUtil.nsh showed that a fresh /D target still calls uninstallOldVersion
for the same registered installer identity. Final checkpoint builds therefore
use org.renulus.desktop.delivery.<exact-frozen-revision> instead of the earlier
development installer identity. Actual configuration loads verified distinct
IDs and rejected HEAD as a moving identity. This protects retained checkpoint
install directories from an automatic upgrade uninstall; preservation remains
an explicit post-install check. Product filename and the executable layout stay
Renulus Development.exe. Final native and NSIS execution remain pending freeze.

The real producer Save gate also had two older C-only tool guards. The actual
Windows dialog operator and standalone isolated ZIP inspector now admit only
the same exact E proofs root alongside the existing assigned test-results root;
other drives/sibling prefixes/relative ZIP inputs and reparse paths reject.
Seven archive integrity/boundary tests passed on E, and again in 0.288 s under
the retained installed embedded Python with -I -B, System32-only PATH and
child-only E TEMP/TMP. No helper-heavy app launch occurred. The real dialog
tool accepted E output paths then correctly stopped at an intentionally missing
owner PID; a sibling-prefix path rejected before owner lookup. This is a guard
check, not a fresh GUI Save proof. Actual native execution remains pending.

The parent explicitly froze product source at
ebb2db2e5080f4d42eaf31c2eb63711797704df0. Final staging started on
2026-10-05 at 01:48 UTC under the authorised E delivery root. It verified the
preserved 39,219-file public input inventory, copied the payload and pinned Node
environment to E, and refreshed only the new E backend source. The refreshed
inventory completed at about 02:17 UTC: 39,236 files / 2,169,524,794 bytes.
TypeScript, the Vite production build and native compilation passed for that
exact committed snapshot. Native provenance records identical source/adopted
backend hashes and Electron 44.5.1; no adoption override was applied.

Proof-only tool commit 4b42bf75a90e1c0660868a060b6173c681b7539a admits the exact
frozen E snapshot for the paced source Save test and supplies E TEMP/TMP to its
fixture interpreter, Electron and Windows dialog helper. It does not alter the
frozen bundled application. Its actual execution passed at about 02:19 UTC in
proofs/native-save-9a3272e0. native-save-source-evidence.json records unchanged
committed main/preload/renderer, real DataManagement Download/Cancel buttons,
PID/executable/control-scoped Windows dialogs and authenticated fixed-route
transfers. The protected opening window appeared at 1.336 seconds; the Flow
renderer was ready at 2.628 seconds with deliberately delayed fixture metadata.
These are fixture handoff observations, not real helper startup measurements.

All four cases passed: completed promotion, cancellation during transfer, a
deliberate HTTP 409, and actual Save-dialog Cancel. A 131,072-byte sibling partial
was observed before successful promotion; a 65,536-byte partial was observed
before transfer cancellation. Existing destinations remained intact until
successful promotion and after failed/cancelled saves. No owned partial survived.
The saved 67,109,006-byte synthetic ZIP matched its fixture SHA256
4fc194db694249da152cfedf8d6f2c376d3a3ae26a10a2c877572e56f9d64c5e. Renderer notices
were observed directly; no dialog path/result was substituted. The captured
source-flow-after-dialogs.png was reviewed and shows the actual Connections
study-data page with its Cancel notice.

This source transfer proof uses declared synthetic metadata/account/recovery
reads and a ZIP of synthetic bytes. It is not a Renulus recovery archive or
proof of the packaged managed backend, module readiness, restore or multi-GiB
behaviour. Final NSIS install, relocated installed lifecycle, physical PDF
page two and real format-2 producer gates are still pending. All proof profiles
and scratch remain on E. The separately reserved restricted delivery-data
directory is excluded from public packaging and was not inspected or copied.

The final matching stage completed successfully at about 02:35 UTC. Its
unsigned NSIS installer is matching-ebb2db2e/
Renulus-Development-0.1.0-windows-x64-setup.exe under the authorised E delivery
root: 965,927,137 bytes, SHA256
8cce7d8a887fbf0ed20cae4315df14ea103224f551a550d5a4ae8efc8d023c42.
matching-ebb2db2e/delivery-provenance.json records the exact frozen source,
installed dependency pins, 19 public helper files / 483,597,181 bytes, official
embedded Python archive checksum and separate installer identity.

Fresh actual NSIS installation to installed-ebb2db2e exited zero in 661.2157
seconds. Authenticode reports NotSigned. The installed Renulus Development.exe
SHA256 is 9d8463a0212b37fea83226468f757a62530f9871ad2980b09b15e96d6d48d446;
resources/app.asar SHA256 is
a609138332032f86fe2111cf29ff1b16177fb1ca9ed12f4c8c70b2cc926d1a7d.
Both match the completed unpacked package. The installed backend contract is
embedded-cpython-windows-v1, Python 3.14.4 and exact source
ebb2db2e5080f4d42eaf31c2eb63711797704df0. Actual extraction evidence is
proofs/installer-e4aa7d23/installer-evidence.json. The installer and automation
controllers received child-only E TEMP/TMP; no global environment was changed.

preserved-after-ebb2db2e.json confirms all six retained C public files are byte
identical to the before-install record: previous installer, installed executable,
ASAR, backend manifest and original payload inventory/manifest. No previous C
payload or checkpoint was deleted. The restricted data directory remains
outside every package input.

Actual installed lifecycle proof passed with two serial independent synthetic
profiles, then protected opening-window cancellation and same-profile restart.
proofs/native-066a6df6/native-evidence.json records Electron 44.5.1 and relocated
embedded CPython 3.14.4 with isolated/no-user-site flags, prefix/base-prefix and
all interpreter paths inside the E installed runtime. python, python3, py, uv,
node and npm were absent on the application's OS-only PATH. Developer
automation runs outside that child PATH; this is not a clean-VM proof.

| Actual installed run | First visible opening | Real Flow renderer | Authenticated backend |
| --- | ---: | ---: | ---: |
| Fresh synthetic profile a | 8.102 s | 197.491 s | 197.633 s |
| Fresh synthetic profile b | 1.331 s | 60.801 s | 60.836 s |
| Same profile a restart | 0.849 s | 38.307 s | 41.752 s |

These observations are from this Windows machine and E HDD with uncontrolled
OS caches and contemporaneous C disk pressure. The restart uses provisioned
helpers; it is not a cold-start benchmark. All ten backend modules and eight
navigation entries were present. Session isolation, sandbox/context isolation,
token rejection, authorization URL rejection, destination search and compact
viewport checks passed. Accounts remained disconnected/unselected; local CPU
helper bytes/imports were ready with no startup downloads/model instances.
Screenshots of Today and Connections were reviewed.

Opening-window Cancel was observed at 0.701 seconds with JavaScript disabled,
no preload/Node integration and a sandboxed, isolated, nonpersistent session.
Its physically owned Python child exited on close. Both independent instances
and the restarted instance also left no owned backend after close. This is
physical Windows process-exit evidence, not a backend shutdown-callback claim.

The final installed journey passed in proofs/journeys-2e053e16. Its opening
appeared at 0.746 seconds and real renderer/backend readiness was 51.127/51.147
seconds. The actual Library blob-PDF iframe selected physical page two.
library-pdf-viewer.png was visually reviewed: RENULUS - PAGE TWO and the large
2 marker are visible. Browser frames confirm the built-in viewer and page two,
with no PDF policy blocking; an unrelated Library capabilities request was
cancelled. Library DTO/original requests are declared
synthetic fixtures; this does not claim parsing or indexing a real original.
The real Updates source link and openSource bridge completed original OS
shell.openExternal calls for the public KDIGO source. Renulus remained on its
local origin with one renderer window. Browser page loading was not observed.

The same installed app created a synthetic manual study goal through its real
Memory API and saved a real format-2 producer archive through DataManagement
and an actual PID/control-scoped Windows Save dialog. The installed embedded
Python, using -I -B and OS-only PATH, verified all 15 ZIP members, 477 canonical
records / 743,115 canonical bytes, segment/member inventory hashes and the
exact synthetic memory marker. The 128,575-byte archive SHA256 is
7d83bcc493c49aec91f0c0de602f1a8a41462e9c418389af5a5971d4502374cd.
Actual Save-dialog Cancel preserved that archive and left no sibling partial.
actual-producer-backup-evidence.json contains the complete inspection. This
small producer proof complements the paced 64-MiB promotion/transfer-cancel
proof; it does not establish restore or multi-GiB capacity.

All final proof instances closed, including the final journey's app and Python
child. No provider login or generative inference was performed. Product source
remains the explicit freeze; proof-only 4b42bf75 and evidence-only 09489f53
were separately integrated by the parent. The parent owns delivery.json,
shortcut wiring and the normal launch of its separately audited private E
learning profile. This lane did not access either private learning profile.

Normal-shortcut follow-up on 2026-10-05: the parent reported that its external
scripts/start-renulus.ps1 wrapper launched the interactive packaged executable
with Start-Process WindowStyle Hidden at 03:03:55 UTC. Parent-owned PID 3936
created window handle 51708302, but EnumWindows reported Visible:false and
GetProcessMainWindow returned zero. This is a concrete failure of the normal
shortcut entry path; the earlier direct Electron native proofs remain separate.
The serial-proof release notification did not establish shortcut acceptance.

The parent's external wrapper fix `4b1d2b71` changed the packaged-app launch to
WindowStyle Normal. Its ignored shortcut-launch-evidence.json records the prior
owned hidden app/backend gone before the actual shortcut relaunch at
**03:06:14 UTC**, app PID **30520** / backend PID **44272**. Visible Flow was
observed by **03:10:56 UTC**, a coarse upper bound of about 282 seconds on E HDD,
not an event-timed startup benchmark. Health returned 200 with all ten modules
and an unauthenticated metadata request returned 401. This establishes the
corrected normal shortcut launch, separately from the direct native proofs.

The native Library page size was **25**. Initial listing and passage search
hit the 30-second request timeout under cold/overlapping helper workers. The
older 100-document ASGI audit had no background worker lifespan and does not
describe that GUI workload. After heavy test workers stopped at 03:19 UTC, a
refresh begun at 03:23 UTC was observed by **03:26:49 UTC** with 25 items,
547 indexed, 6,759 queued, one processing and zero active failures. A
`dialysis adequacy` query begun at 03:26:49 UTC showed eight Inspect citation
controls and Passages by **03:27:33 UTC**, without a timeout notice. The first
citation was inspected at **03:28:36 UTC**, with physical-page labels `13`,
`8`, `1 / 2` and `2`; Today was reached again at **03:29:50 UTC**. These are
action/observation times, not individual request latencies. The initial timeouts
do not prove a permanently hung pipeline; the later retries do not establish
sustained responsiveness under overlapping workers.

This account uses the parent's metadata-only evidence at
`E:/Renulus-native-delivery/desktop-20261005/shortcut-launch-evidence.json`;
no private source bodies were read or published by this documentation lane.
The wrapper correction is external to the installed application and bundled
main assets. Installed product source remains exactly
`ebb2db2e5080f4d42eaf31c2eb63711797704df0`, with the recorded
installer/executable/ASAR hashes unchanged. The parent has since integrated
Library patch `a5488b2d` as a candidate product freeze, with compatible API checks
running; matching refreeze/packaging/installed acceptance remain separate work.
See [normal shortcut acceptance](final-validation.md#normal-shortcut-and-queued-library-workload)
and the [later profile snapshot](complete-delivery-profile-live-proof.md#normal-installed-workload-and-later-snapshot).

## Matching replacement — October 5, 2026

The parent explicitly froze replacement product source at
3ff9b0d6145c8d52f4c9e9b0a3009f0fc351c4cc, including the accepted Library
responsiveness/citation correction. The replacement was built from that exact
committed backend/renderer/native snapshot; the previous ASAR was not relabelled.
Dependencies and public helper pins were unchanged. Package, fresh unsigned
NSIS installation and one isolated installed native startup/shutdown passed.
The parent independently accepted the report and reviewed its Flow screenshot,
then took the released native slot for its actual desktop-shortcut and chosen
learning-profile checks. No further native instance or matrix was started by
this lane after that release.

All replacement artifact and report paths below are relative to
E:/Renulus-native-delivery/desktop-20261005. The completed installer is
matching-3ff9b0d6/Renulus-Development-0.1.0-windows-x64-setup.exe:
965,928,451 bytes, SHA256
49f82a58b227c3d572747c3b282fdec20c09fe03777e878c9ba8125281460ed2.
Fresh installation to installed-3ff9b0d6 exited zero in 432.7511048 seconds.
Authenticode reports NotSigned. Installed Renulus Development.exe SHA256 is
38d56a3887c2acf0e8b0db8d45047e59471723cbf3f557253f5f8a77691b3cb9;
resources/app.asar SHA256 is
8ea2cab31aaefb3ea56ca37ad524307c4c342538421811fbebe6ec80225c66f0.
Both match the completed unpacked package. A distinct per-revision NSIS identity
preserves the installed ebb2db2e checkpoint.

The public payload is 39,236 files / 2,169,529,464 bytes, inventory SHA256
34c0746714def26e518e10e0470e7054e3b1e77316a9abbeeba62d76f4786952;
the installed inventory was rechecked at final handoff. Actual embedded
CPython 3.14.4 and Electron 44.5.1 were observed. The same 19 public helper files
total 483,597,181 bytes. The installed helper contract and official embedded
Python archive checksums match the recorded manufacturing provenance. Private
originals, profiles, credentials, SQLite state and data/** are excluded from
every package input. All child scratch, cache, TEMP/TMP, install and proof writes
stayed inside the authorised E root; host environment variables were unchanged.

| Actual replacement installed synthetic run | Time |
| --- | ---: |
| Protected first visible opening window | 3.516 s |
| Actual Flow renderer | 166.522 s |
| Authenticated metadata, HTTP 200 / API version 1 | 166.547 s |
| Physical application/backend shutdown | 8.245 s |

proofs/replacement-2601cd66/replacement-evidence.json records the exact source
revision, equal isolated interpreter prefix/base-prefix and all interpreter
paths inside the installed backend. python/python3/py/uv/node/npm were absent
from the app child's OS-only PATH. Renderer sandbox/context isolation were true,
Node integration false, and exactly one managed Python child was observed. App
PID 16392 and backend PID 2160 were physically absent after closure, independently
verified by the parent. These timings are observations on this Windows machine
with uncontrolled caches/load, not clean-VM benchmarks or shutdown-callback
evidence. replacement-flow.png was reviewed.

The supplementary owned-window-observation.json at 04:43:39.5818011 UTC recorded
a zero handle/visible:false during successful shutdown, after the Flow screenshot
at about 04:43:35 UTC and before completion at about 04:43:43 UTC. The final
report preserves this timing context; that sample is not a hidden-startup
failure.

Manufacturing/tool source was fe6d3b53360d4f3ac5a8e2ac6296651a8d826573; the
focused replacement proof was introduced by
af9f3f24fee9bf746bd812f254bbb36ac07b82e2. Twelve recorded script/configuration
hashes were rechecked at handoff. The unbundled tool chain includes 0791e624,
49482d35, af9f3f24 and fe6d3b53, already parent-integrated. Its 10 Python delivery
checks, 12 PowerShell boundary refusals, actual Node-child environment
presence/removal check and five focused-proof source checks passed. Parent's
later unbundled Windows PowerShell 5.1 compatibility fix 2ffa7080 is separate
from the manufacturing tool source and frozen product.

The first Package run retained under preparation/restage-a5488b2d-20261005/
runs/3ff9b0d6-package-50cd8519 failed after public staging/Node copy because an
inherited empty RENULUS_BACKEND_URL was rejected by the frozen Vite URL parser.
The runner fix genuinely removes that child environment entry. Guarded
continuation revalidated the completed public inventory/source/pins, created
a fresh committed-source snapshot and resumed compile/package without repeating
the public payload copy. Frozen product code, failed logs/snapshot and prior
checkpoints were preserved. The completed continuation snapshot is
source-3ff9b0d6/continued-8e74325b.

preparation/restage-a5488b2d-20261005/preserved-after-3ff9b0d6.json records fresh
read-only hashes of the previous ebb2db2e installed executable and ASAR, both
matching their original install receipt. The retained previous installer's
existence, size and modification time were checked; its original verified
checksum was not recomputed during this handoff. No old payload/checkpoint was
deleted and no private learning profile was inspected. No rejected cleanup was
retried.

Final public reports are proofs/final-native-3ff9b0d6-fe6d3b53/native-delivery.md
and native-delivery.json, with SHA256SUMS.txt. They link the completed Package
2ee5c476, Install f9f108dc and Proof f0df11d5 controller receipts, actual installer
5f8670e4 evidence, manufacturing checksums, source comparison and preservation
records. Generated READY/ready-plan status now records all three completed
gates and the released native slot. Original preparation/status records were
retained alongside the final report.

Main/preload/profile source, compiled main/preload hashes and Electron pin are
unchanged from ebb2db2e, as recorded in native-source-comparison.json. The older
two-profile/full-navigation/physical-PDF/source/64-MiB-transfer/real-format-2
backup matrix remains dated evidence for ebb2db2e; it was not repeated or
relabelled for the replacement. This replacement proves one fresh synthetic
installed startup/shutdown. It does not claim signed release, clean-VM,
uninstaller, live account/inference or actual chosen-profile shortcut proof.
Parent owns normal shortcut, Library25/search/citation acceptance and delivery
pointers. External WindowStyle Normal launcher fix 4b1d2b71 is separate from
the frozen installer/main assets. This final append changes evidence only.
