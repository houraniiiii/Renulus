# Renulus desktop source and dependency notices

Renulus code is MIT; see LICENSE. Third-party licences retain their own scope.
Runtime packages are pinned in package-lock.json. React and React DOM use MIT;
Lucide includes ISC and Feather MIT; bundled Source Sans 3 uses SIL OFL 1.1.
Their full notices are retained under licenses/. No font service is contacted.

Flow chrome, typography, control treatments and headings are adapted from the
user-selected Renulus UX exploration in Renulus-wt-ux-exploration, specifically
prototypes/design-directions/src/App.tsx and styles.css. No fixture content,
synthetic progress, model responses or prototype persistence was adopted.
The unchanged mark and icon are copied from assets/brand/renulus-64.png and
renulus.ico. The original brand provenance remains in assets/brand/README.md.

Nous Research Hermes source is MIT, copyright (c) 2025 Nous Research; the full
upstream licence is licenses/hermes-MIT.txt. The following exact source files
are copied unchanged into electron/upstream/ and used by Renulus lifecycle:

| Upstream source under apps/desktop/electron/ | SHA256 |
| --- | --- |
| backend-child.ts | f1c86124763c87bed75c416a860de921037da34422a1ecdd0c2b90b4e8fdfe49 |
| backend-start-cancellation.ts | c886c98146b52fd47c6464e937291f7a0e482d6b24d88522482f77ce11a9bdc2 |
| main-window-lifecycle.ts | 7999f9a0488845917ec7bfac61c7d8f1229428159f620172efa83824ecb8b6f9 |
| window-focus-policy.ts | 440cd65aff9b5f8b15dbe081186bdf9230bfccac5cf7a5cc7a67575662657af3 |

Immutable research/import pin: af90026aa09949579bd423d24def3d38f743cde0.
Acquired upstream archive SHA256:
c1ee01756a755a4d5ee670f7a671e658359423355545b32fc908a413c6abdb4f.
Acquisition was supplied by the runtime lane in its owned upstream/hermes;
this lane reads it and keeps source-path provenance. The upstream head reported
by the runtime lane is 32172d4622195697e4f077976140d0ed0738318a, 27 commits newer;
it is not the imported baseline. No upstream patches were made by this lane.

Electron packaging follows upstream apps/desktop/package.json and
electron-builder.config.cjs's build-before-pack, whitelist, asar and Windows
identity approach, scoped to Renulus. The controlled renulus.server replaces
stock headless gateway startup; the general-purpose Hermes renderer/preload,
filesystem commands, updater, telemetry and credential discovery are not enabled.
Electron, electron-builder, Vite and other development tools retain their
package notices; distributing a full dependency tree needs its complete notices.

Security correction on October 4, 2026 pins Electron 44.5.1 and Vitest 4.1.11.
Electron's published installer now uses its BSD-2-Clause
@electron-internal/extract-zip (lock: 1.0.5) rather than extract-zip 2.0.1.
This is an upstream adoption; Renulus does not provide a replacement extractor.
The downloaded Electron Windows x64 ZIP is verified against its npm checksums
and the fresh official release SHASUMS256.txt. The ZIP SHA256 is
9b382492dcfee91f8f9e92c91f7972550a1b95d2299cac72279dab33a600d7db.
Source/artifact and package-integrity details are recorded in
docs/implementation/desktop-evidence.md and generated locally by
scripts/install-electron.mjs. Extraction is development/install tooling only;
the renderer has no archive-extraction interface. The NSIS packaging reservation
does not enable Squirrel or its electron-winstaller install hook.
