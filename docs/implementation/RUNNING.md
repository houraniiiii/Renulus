# Running Renulus

The active app is the Flow learning application in this repository. The
integration branch is `build/renulus-integration`, tracked by GitHub issue #1 and
draft PR #13. The implementation record is a dated capability report; it does
not establish clinical accuracy or live account access.

## Windows delivery

Windows bundle/installer assembly is in progress. The normal workspace launcher
is `Start-Renulus.cmd`. It uses the explicitly recorded local executable/profile
from ignored `.local/delivery.json`, or the prepared contributor Electron build.
`-CheckOnly` checks the launcher without starting the app. Each learning profile
owns its SQLite records, library copies, helper cache and derived indexes.

The assembled app manages its Python process and CPU helpers. Doctors should not
need Python, uv, Node, Docker, a GPU or a local model service. The delivered
bundle's relocation/native evidence must pass before this is claimed as a
verified installed capability. Third-party acquired originals are local imports;
they are excluded from the public bundle.

In Connections, choose Codex or OpenCode Go and authenticate deliberately. Only
the selected model allowlist is exposed. Account/model availability and image
capability are reported independently. No paid API fallback is supplied. Test,
staged teaching cases, the local library and manual study planning remain useful
without a generative connection.

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
