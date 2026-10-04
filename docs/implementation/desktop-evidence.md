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
