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
