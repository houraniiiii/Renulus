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
