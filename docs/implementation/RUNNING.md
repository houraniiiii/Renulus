# Running Renulus

The active app is the Flow learning application in this repository. The
integration branch is `build/renulus-integration`, tracked by GitHub issue #1 and
draft PR #13. The implementation record is a dated capability report; it does
not establish clinical accuracy or live account access.
For the app's controls and everyday workflows, see [Using Renulus](USING_RENULUS.md).

## Windows delivery

On October 6, installed acceptance found and repaired an Electron shutdown
exception caused by a late request after window destruction. The correction is
committed at `c7b3b5dea9258845273a8df95ca24f5da5bf1ca5`; matching manufacture
and acceptance are in progress. The 035ca7bd artifacts below are preserved
historical candidates and do not have accepted ordinary-close/recovery proof.
The normal launcher remains on its previous selection until the rebuilt app
passes matching installed acceptance and maintenance. See
[the correction](finalise-owned-api-headers.md) and
[current continuation](CONTINUATION_20261005.md).

The matching unsigned installer and fresh installation for product source
`035ca7bd07337c65266c17f9b762ca1f97238e11` completed on October 5, 2026.
The active checkout is on C:. Raw collection files and the normal learning
profile remain on the second drive. Preserved 035ca7bd artifacts are:

| Item | Local delivery path |
| --- | --- |
| Installed candidate | `C:/Renulus-native-delivery/desktop-20261005/installed-035ca7bd/Renulus Development.exe` |
| Learning profile | `E:/Renulus-native-delivery/desktop-20261005/data/learning` |
| Matching installer | `C:/Renulus-native-delivery/desktop-20261005/matching-035ca7bd/Renulus-Development-0.1.0-windows-x64-setup.exe` |

The installer is 1,010,348,169 bytes, SHA256
`b4f120e7bd115cca00caf0379d6607e1ae2267d88743490f1b1380c1d8ea29af`.
Package and extraction-only Install passed with matching source, executable,
ASAR and bundled-runtime identities. Installed UI, connected journeys and
maintenance remain under acceptance. The six actual bundled-storage phases
have passed independently, including interrupted migration recovery and saved
original retention. See [the continuation](CONTINUATION_20261005.md),
[lifecycle evidence](finalise-lifecycle.md) and [requirement audit](finalise-audit.md).
Later documentation commits do not change this manufactured product.

The owned **Renulus** desktop shortcut and `Start-Renulus.cmd` use
`scripts/start-renulus.ps1`. The ignored `.local/delivery.json` still selects
the previously accepted `installed-3ff9b0d6` executable and the same E learning
profile. Promote it only after matching installed acceptance and maintenance;
an extracted candidate is not a substitute for those journeys. `-CheckOnly`
checks the selected launcher without opening an app. A checkout without a
delivery record uses its prepared contributor build.

The observations below concern the earlier accepted E installation at
`3ff9b0d6`, including its historical queue counts. They do not establish
acceptance of the current C candidate. Preserve their detailed receipts in
[historical validation](final-validation.md).

The installed app manages embedded CPython 3.14.4 and CPU helpers. The matching
fresh NSIS installation exited zero in 432.751 seconds. One isolated installed
startup passed with Python, uv, Node and npm absent from the child's OS-only
PATH: protected opening at 3.516 seconds, Flow at 166.522 seconds and
authenticated backend metadata at 166.547 seconds. Closing physically stopped
the owned application and backend in 8.245 seconds. These are observations on
this E HDD/development machine, not a clean-machine benchmark. Doctors need no
developer runtime, GPU, Docker or local inference server. The installer is
unsigned. The owner chose current-PC unsigned acceptance on October 5;
signing and a separate clean PC/VM are optional future distribution checks.

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
facts are excluded. Explicitly saved case PDF/image originals have authenticated
View original controls. Full backups include eligible saved originals;
records-only exports omit their bytes. Backup/restore and derived-index recovery
are being validated as a combined installed flow. Review the displayed backup
date and deletion reconciliation; an older backup alone cannot know about later
deletions.

Detailed evidence lives beside this file and in the module tickets. Do not infer
passed live generation, clinical image interpretation, signing or clean-machine
coverage from renderer tests or synthetic providers.
