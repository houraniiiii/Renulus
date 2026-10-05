# Running Renulus

The active app is the Flow learning application in this repository. The
integration branch is `build/renulus-integration`, tracked by GitHub issue #1 and
draft PR #13. The implementation record is a dated capability report; it does
not establish clinical accuracy or live account access.

## Windows delivery

The matching unsigned Windows installer and fresh installation completed on
October 5, 2026. On the delivery machine, the owned **Renulus** desktop shortcut
now targets the integration launcher at
`E:/Renulus-native-delivery/desktop-20261005/repo/scripts/start-renulus.ps1`.
The same integration checkout has `Start-Renulus.cmd`. Its ignored
`.local/delivery.json` identifies the installed executable and prepared local
learning profile:

| Item | Local delivery path |
| --- | --- |
| Installed application | `E:/Renulus-native-delivery/desktop-20261005/installed-3ff9b0d6/Renulus Development.exe` |
| Learning profile | `E:/Renulus-native-delivery/desktop-20261005/data/learning` |
| Installer | `E:/Renulus-native-delivery/desktop-20261005/matching-3ff9b0d6/Renulus-Development-0.1.0-windows-x64-setup.exe` |

The installer is 965,928,451 bytes, SHA-256
`49f82a58b227c3d572747c3b282fdec20c09fe03777e878c9ba8125281460ed2`.
The installed product uses the exact source freeze
`3ff9b0d6145c8d52f4c9e9b0a3009f0fc351c4cc`; later test/proof/evidence commits
do not change this installed build. `-CheckOnly`
checks the launcher without starting the app. A checkout without a delivery
record uses its prepared contributor build. The original shared C checkout and
its inherited reference launcher remain separate; use the repaired desktop
shortcut or this E integration launcher for the new learning application.

The installed app manages embedded CPython 3.14.4 and CPU helpers. The matching
fresh NSIS installation exited zero in 432.751 seconds. One isolated installed
startup passed with Python, uv, Node and npm absent from the child's OS-only
PATH: protected opening at 3.516 seconds, Flow at 166.522 seconds and
authenticated backend metadata at 166.547 seconds. Closing physically stopped
the owned application and backend in 8.245 seconds. These are observations on
this E HDD/development machine, not a clean-machine benchmark. Doctors need no
developer runtime, GPU, Docker or local inference server. The installer is
unsigned; signing and clean-machine release acceptance remain separate.

The actual desktop shortcut launched this matching replacement at **04:45:07
UTC on October 5, 2026**. Visible Today was captured at 04:47:38 UTC, a coarse
visibility bound rather than an event-timed startup measurement. Health
returned 200 with all ten modules, an unauthenticated metadata request returned
401, and the embedded backend was bound to the chosen E learning profile. The
external launcher uses Normal window style for the interactive app; its hidden
PowerShell wrapper is separate. The earlier hidden-app failure and its repair
remain in [historical validation](final-validation.md#normal-shortcut-and-queued-library-workload).

The GUI Library defaults to **25 documents per page**. On the replacement,
navigation at 04:47:41 UTC produced 25 observed documents at 04:47:50 UTC while
the normal ingestion worker continued. A `dialysis adequacy` search at 04:48:08
UTC produced eight observed citation controls at 04:48:18 UTC with no timeout
notice. Citation inspection showed E01 source metadata and an **Open original ·
page 13** control; the original PDF rendered visually. Its native PDF
accessibility tree reported unavailable text-extraction files, and the physical
page control was not independently read. This is visual original/citation
acceptance with that qualification. These action/observation windows do not
measure individual request latency or prove sustained performance under
competing helpers. See [matching native acceptance](final-validation.md#matching-installation-and-normal-library-acceptance).

The installed replacement includes Library patch `a5488b2d`. Parent integration
passed 38 Library API/exact-citation checks. Collection selection and acquired
supplement additions continue in issues #14 and #15; their source patches are
not yet claimed as part of this installed freeze.

At the 04:51:26 UTC snapshot, the profile had 7,307 documents, 16,271 passages,
672 ready jobs, 6,634 queued and one embedding, plus four historical failed
revisions. The normal worker continues indexing; queued imports are not yet
searchable. Seven selected-policy holds were subsequently cancelled through
the native UI, cleaning their app-owned derivative copies and retaining external
originals. Counts are dated snapshots, not a claim that every acquisition file
is eligible or indexed. See [source selection](source-selection-review.md).
Each profile owns its SQLite records, library copies, managed helpers and
derived indexes.
Third-party acquired originals stay local and are excluded from the public
bundle and Git repository.

In Connections, choose Codex and authenticate deliberately to enable generation.
The delivered profile starts disconnected with no provider selected. Only the
approved model allowlist is exposed. Account/model availability and image
capability are reported independently; the original synthetic image-input check
is deliberate. OpenCode Go learning requests remain paused while learning-use
eligibility is unresolved. No alternate provider or paid API fallback is supplied.
Reviewed Test, staged teaching cases, the local library and manual study planning
remain useful without a generative connection. Live account/generation and
clinical image interpretation have not yet been accepted.

## Contributor startup

From the repository root, prepare the pinned Python environment with
`uv sync --extra test`. In `apps/desktop`, run `npm ci` and
`npm run dev:electron`. This builds the renderer/Electron entry points and opens
an isolated development profile. For a durable chosen profile, set an absolute
`RENULUS_PROFILE` before starting. Public helper artifacts are prepared through
the documented runtime staging process; source documents and credentials must
never be included in that staging bundle.

A browser development route uses Vite against an explicitly authenticated local
backend. Its ignored `.local/dev-config.json` contains the app-owned loopback
origin/token. Do not publish that file or substitute another app's native state.
The Electron renderer receives public operations; its managed main process owns
the backend session token.

## Learning and data

Original pack versions activate transactionally and retain the versions used by
completed tests. Generated practice has a distinct role and separate results.
Library imports display status, rights and source locators. Receipt dates do not
establish publication editions. Current-only retrieval requires reviewed final
currency metadata, rather than merely a downloadable file.

Daily cases and attachments stay temporary until explicit Save. A handoff into
Learn/generated practice retains that scope. Learner Memory records study
evidence and preferences, with correction, deletion and rebuild controls; case
facts are excluded. Backup/restore and derived-index recovery are being validated
as a combined delivery flow, with exact dates and deletion limits presented.

Detailed evidence lives beside this file and in the module tickets. Do not infer
passed live generation, clinical image interpretation, signing or clean-machine
coverage from renderer tests or synthetic providers.
