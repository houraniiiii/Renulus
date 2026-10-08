# App-scoped Renulus control

The owner requested this development path on October 6, 2026 after stopping
Computer Use while working on the same PC. Use the local Renulus Playwright
MCP controller for interactive UI work. It sends input to its own Electron
renderer and captures app pixels without moving the shared mouse, typing into
other applications or showing test windows.

`tools/renulus-control` is developer tooling, outside the distributed doctor
runtime. It launches one separate synthetic profile and its managed backend.
It does not attach to the owner's open app, import an account, copy credentials
or select a different subscription/model. Its default run is local UI testing;
live generation still needs separately authorised account acceptance.

The real source-app MCP journey is accepted at its recorded scope: 39 tool
operations, five screenshots, explicit synthetic Case save/reopen, track
selection and owned cleanup. The local interactive client adds seven actual
Library/control operations and a normal close. Read
[the October 6 report](app-control-20261006.md) before repeating checks.

## Setup and operation

Install the pinned development dependencies with
`npm ci --ignore-scripts --prefix tools/renulus-control`. Build the desktop
renderer/native entry with `npm run build --prefix apps/desktop`. Configure
the MCP server using the package's [README](../../tools/renulus-control/README.md).
The server uses stdio rather than exposing another local HTTP control port.

Start the owned instance, inspect its accessibility snapshot, operate controls
from that snapshot and take screenshots as needed. Wait for the expected
control/state when a local operation is asynchronous. Restart reuses only that
controller's synthetic profile. Close stops its app and backend and retains
evidence. Use the errors tool after a journey. Do not add focus(), bringToFront(),
SetForegroundWindow, OS key/mouse helpers or the legacy foreground dialog scripts
to this path.

The local Codex MCP registration points to `C:/Renulus/dev/repo` and uses the
retained development Python at `C:/Renulus/dev/python`. It has no account secrets.
A chat which cached an earlier MCP server can use the local client without
restarting the user's desktop. From the canonical checkout:

```powershell
node tools/renulus-control/client.mjs --repo C:/Renulus/dev/repo --python C:/Renulus/dev/python/Scripts/python.exe --state-root C:/Renulus/scratch/control --helper-assets C:/Renulus/dev/helper-assets
```

Send `{"name":"renulus_start","arguments":{}}`, then the documented
tool requests as individual stdin lines. The client prints results and
captures to external files. Use `renulus_close` before EOF. A new client
reads the latest server code; `renulus_restart` loads the latest built app
with the same owned synthetic profile. The original eleven tools remain available.
The October 7 extension adds `renulus_upload` and `renulus_resize`; arbitrary
evaluation remains unavailable. Read the [bounded input contract](../../tools/renulus-control/README.md#synthetic-uploads-and-hidden-resizing)
and [lane handoff](finish-control-inputs-20261007.md) before the parent's first
actual upload/resize check.

For PDF/PNG/JPEG input, start a fresh client/server with the same configuration
plus `--fixture-root C:/Renulus/evidence/runs/rn-finish-20261007/evidence/control/synthetic-inputs`.
That external directory contains original synthetic files and the required
size/SHA-256 manifest. No personal/acquired source is part of it. The root is
fixed by CLI, separate from profiles and dependencies; tool arguments accept
only a declared synthetic basename. Omitting it leaves uploads disabled.

Navigate to the existing Library or Case file field, then take a snapshot.
Its additional `fileInputs` list supplies exact observed locators. Use one as
`renulus_upload`'s `locator` and `synthetic-study.pdf`, `synthetic-image.png` or
`synthetic-image.jpg` as `fixture`. The controller verifies the declared bytes
and uses Playwright `setInputFiles` directly. Refresh the snapshot after a
selection or Case mode change. Observe the app's resulting extraction, preview,
rights and Save state separately; successful selection alone proves none of them.

Send `{"name":"renulus_resize","arguments":{"width":1000,"height":720}}`
to resize only the owned hidden Flow window. Bounds are 640–2560 wide and
540–1600 high, in device-independent pixels. The result includes actual outer
and content dimensions. Capture fresh pixels with `renulus_screenshot` after
resizing. No focus, show, position change or OS input is involved.

Screenshots use Electron's capturePage with stayHidden enabled. The controller
checks its windows for visibility/focus and keeps hidden rendering unthrottled.
The app's opt-in `RENULUS_BACKGROUND_TEST=1` requires an explicit absolute
profile and its own backend. Startup, activation and second-instance handling
keep background windows non-focusable and off the taskbar. Ordinary app startup
retains its existing behaviour.

Optional public helper seeding copies only the reviewed embedding, Docling and
OCR assets; use the declared helper contract. It does not borrow the owner's
Library, indexes or connections. Keep the synthetic profile path compact on
Windows and all screenshots, profiles and logs outside Git.

## Evidence and boundaries

External browser actions are blocked and recorded in this mode. Authorization
URLs are not logged; recorded source targets exclude query strings/fragments.
Native backup save requests return cancelled and record suppression. Startup
and shutdown errors go to stderr rather than a foreground message box. These
checks establish app control and suppression, not successful native dialogs or
external handoffs.
Indirect HTML chooser requests still receive an empty file list and are logged
as cancelled. Upload never opens one. The fixed manifest, strict PDF/image types,
observed Library/Case input labels and filesystem guards exclude account/profile
imports and arbitrary personal paths. These guards do not replace the operator's
responsibility to declare only owned synthetic material.

The controller supplies its own process ID as the background owner. The
controller verifies the Windows launcher/main/backend process chain; Renulus
observes owner loss and requests its ordinary
shutdown independently. A closed diagnostic pipe does not interrupt backend
cleanup. This covers Windows stdio clients that terminate their MCP server
before a longer app shutdown finishes.

The native [evidence script](../../apps/desktop/scripts/background-control-evidence.mjs)
requires absolute RENULUS_PYTHON and RENULUS_CONTROL_EVIDENCE values and a fresh
receipt directory. Default runs use its synthetic profile. For a narrow missing
native-bridge/lifecycle check, set RENULUS_CONTROL_CHECKS=bridges and optionally
reuse a known owned synthetic RENULUS_CONTROL_PROFILE. Never point it at the
owner's active personal profile. Recover existing receipts before rerunning.

Actual Windows installation, physical file dialogs, external browser sign-in
and full packaged/connected journeys keep their separate acceptance scopes.
Hidden development checks do not replace matching source/runtime provenance
or establish generation, memory capture or installed acceptance.
