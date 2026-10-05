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
| Installed application | `E:/Renulus-native-delivery/desktop-20261005/installed-ebb2db2e/Renulus Development.exe` |
| Learning profile | `E:/Renulus-native-delivery/desktop-20261005/data/learning` |
| Installer | `E:/Renulus-native-delivery/desktop-20261005/matching-ebb2db2e/Renulus-Development-0.1.0-windows-x64-setup.exe` |

The installer is 965,927,137 bytes, SHA-256
`8cce7d8a887fbf0ed20cae4315df14ea103224f551a550d5a4ae8efc8d023c42`.
The installed product uses the exact source freeze
`ebb2db2e5080f4d42eaf31c2eb63711797704df0`; later test/proof/evidence commits
do not change this installed build. `-CheckOnly`
checks the launcher without starting the app. A checkout without a delivery
record uses its prepared contributor build. The original shared C checkout and
its inherited reference launcher remain separate; use the repaired desktop
shortcut or this E integration launcher for the new learning application.

The installed app manages its Python process and CPU helpers. Two fresh E
profiles and a same-profile restart passed with Python, uv, Node and npm absent
from the app's OS-only PATH. Doctors need no developer runtime, GPU, Docker or
local inference server. A protected opening window appears while the backend
and managed helpers prepare; actual first-run Flow readiness on this E HDD
varied from about 61 to 197 seconds, and the provisioned restart took about
38 seconds. These are observed development-machine timings, not a clean-machine
benchmark. Closing the app stops its owned backend. The installer is unsigned;
signing and clean-machine release acceptance remain separate. The actual normal
shortcut first launched an invisible app at 03:03:55 UTC on October 5, 2026.
External launcher fix `4b1d2b71` changed the app's window style from Hidden to
Normal. The 03:06:14 UTC relaunch had visible Flow by 03:10:56 UTC, a coarse
upper bound of about 282 seconds on the large profile. Health returned 200 with
all ten modules; an unauthenticated metadata request returned 401.

The GUI Library defaults to **25 documents per page**. Its initial listing and
passage search hit the 30-second request timeout under cold and overlapping
helper workers. After heavy test workers stopped at 03:19 UTC, a refresh begun
at 03:23 UTC was observed by 03:26:49 UTC with 25 items, 547 indexed documents,
6,759 queued, one processing and zero active failures. A `dialysis adequacy`
search begun at 03:26:49 UTC showed eight Inspect citation controls and Passages
by 03:27:33 UTC without a timeout notice; citation inspection and return to
Today followed. These observation times do not measure individual request
latency. See [normal shortcut acceptance](final-validation.md#normal-shortcut-and-queued-library-workload).

The parent has integrated Library patch `a5488b2d` as a candidate product freeze;
compatible API checks are running. Refreeze, packaging and installed acceptance
for that candidate remain with the parent and packaging lane. This record
continues to describe the installed `ebb2db2e` build.

At the separate 02:54 UTC preparation audit, the profile had 7,307 verified
originals and 11,755 rebuilt passages from 481 ready documents, with another
6,826 imports queued. Those are dated snapshot counts; the normal worker
continues indexing. Queued imports are present but are not yet searchable.
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
