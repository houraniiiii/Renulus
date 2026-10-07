# Renulus development controller

Local Node ESM stdio MCP server for one controller-launched Renulus Electron app.
Development only: no Computer Use, OS input/focus, arbitrary endpoint attachment,
client code/evaluation, credential transport or personal-profile argument.

The isolated package pins **@modelcontextprotocol/sdk 1.32.1**, **zod 4.6.5**,
and **playwright 1.62.1**, with an npm integrity lockfile. Use Windows and Node
22.22+ in the 22.x line, or 24.11+. From this directory:

```powershell
$env:PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD = '1'
npm ci --ignore-scripts --no-audit --no-fund
npm run check
npm test
```

Only this package's node_modules is installed. No browsers are downloaded or
shared desktop dependencies modified. Unit tests use mocks and tiny synthetic
files outside Git (fresh C:/rn-control/unit-* directories on Windows). They
never start Electron, Python, providers or real ingestion.

## Configuration

Source mode, after the parent builds the renderer and native main:

```powershell
node C:/Renulus-native-delivery/desktop-20261005/repo/tools/renulus-control/server.mjs --repo C:/Renulus-native-delivery/desktop-20261005/repo --python C:/path/to/dev/python.exe --state-root C:/rn-control --helper-assets C:/path/to/reviewed/public/helper-assets
```

Replace the example Python/helper paths with the parent's prepared public inputs.
Packaged mode uses the bundled Python/helpers, so --python is optional:

```powershell
node C:/Renulus-native-delivery/desktop-20261005/repo/tools/renulus-control/server.mjs --repo C:/Renulus-native-delivery/desktop-20261005/repo --executable C:/path/to/background-build/Renulus.exe --state-root C:/rn-control
```

| CLI option | Contract |
| --- | --- |
| --repo | Required absolute Renulus repository/build root |
| --python | Absolute development Python; required for source mode |
| --executable | Optional fixed absolute packaged Renulus executable |
| --state-root | Absolute evidence root; default path.join(os.tmpdir(), 'rn-c') |
| --helper-assets | Optional absolute trusted public helper bundle |
| --fixture-root | Optional fixed absolute owned synthetic fixture directory; uploads are disabled when omitted |

The source executable is the existing apps/desktop/node_modules/electron/dist/electron.exe.
No CLI setting can be supplied through a tool. Compiled source/package preflight
requires the hidden background and owner-liveness contracts, including
RENULUS_BACKGROUND_TEST, RENULUS_BACKGROUND_OWNER_PID and background events.
The frozen 02cd88e1 package is refused before launch.

Every server creates STATE_ROOT/c/s-xxxxxxxx/p as a fresh synthetic profile.
Only the marked c/ namespace is owned; parent native-* evidence can share
C:/rn-control. Unmarked existing namespaces, Git-contained state and link/junction
paths are refused. Keep the profile path within 60 characters on Windows.
Restart reuses only this server's profile; another server creates a new session.
There is no existing-profile import/resume option.

Helper staging compares the acquired manifest with repo packaging/runtime/helper-assets.json,
checks every declared source and copied hash/size, copies only those public
files and publishes the reviewed manifest last. It follows scripts/copy_helper_assets.py
and installed packaged-backend.py, adding link checks. Undeclared files/account
state are never enumerated or copied. Source mode normally needs --helper-assets
because its new profile is empty. No helper acquisition/download occurs.

The Electron environment is an allowlist: background mode, synthetic profile,
fixed source Python if needed, offline helper flags and
RENULUS_BACKGROUND_OWNER_PID:String(process.pid). No inherited account paths,
keys, proxies, session token, backend attachment or NODE_OPTIONS are forwarded.
The PID belongs to Electron main, not the Python backend environment.

The local `client.mjs` uses the same fixed CLI configuration and MCP server.
It is available when an already-open Codex chat cached older server code.
Start it with `node client.mjs` and the same options shown above. Send one
JSON request per stdin line, for example:

```json
{"name":"renulus_start","arguments":{}}
{"name":"renulus_click","arguments":{"locator":{"role":"link","name":"Library"}}}
{"name":"renulus_snapshot","arguments":{}}
{"name":"renulus_screenshot","arguments":{}}
{"name":"renulus_close","arguments":{}}
```

Requests run in order. The client prints JSON results and screenshot paths,
without dumping image bytes; use the returned PNG for visual inspection.
EOF disconnects the session. Explicit close returns the normal shutdown
receipt before disconnect. An updated MCP module needs a fresh server
connection; rebuilding/restarting the test app alone does not reload it.

## Tools and schemas

A locator is exactly one of these strict objects:

```json
{"role":"link","name":"Cases"}
{"css":"[data-testid=\"example\"]"}
```

Role/name uses exact accessible-name matching. CSS must be pure CSS, without
selector engines/custom code. Actions require exactly one match, without index
or first-match fallbacks. Roles accepted: button, link, textbox, searchbox,
combobox, option, checkbox, radio, switch, heading, navigation, tab, tabpanel,
listbox, menuitem, spinbutton, status, dialog, article, group, main, paragraph,
row, cell and img. Names and CSS are bounded to 512 characters.

| Tool | Strict arguments |
| --- | --- |
| renulus_start | {} |
| renulus_snapshot | {}; bounded ARIA snapshot |
| renulus_click | {"locator":{"role":"link","name":"Cases"}} |
| renulus_fill | {"locator":{"role":"textbox","name":"Case notes"},"value":"Synthetic educational case"}; at most 4096 characters |
| renulus_press | {"locator":{"role":"textbox","name":"Case notes"},"key":"Enter"} |
| renulus_select | {"locator":{"role":"combobox","name":"Topic"},"value":"ckd"}; exactly one of value or label |
| renulus_wait | {"locator":{"role":"heading","name":"Case discussion"},"state":"visible","timeoutMs":5000} |
| renulus_screenshot | {}; returns text metadata/external file path plus MCP PNG image |
| renulus_errors | {"limit":100}; optional 1-200 |
| renulus_restart | {}; same owned profile, new main/backend |
| renulus_close | {}; normal app/backend exit receipt |
| renulus_upload | {"locator":{"css":"input[type=\"file\"][id=\"OBSERVED_ID\"]"},"fixture":"synthetic-study.pdf"}; copy the exact locator from snapshot.fileInputs |
| renulus_resize | {"width":1000,"height":720}; integer outer-window dimensions in device-independent pixels, width 640–2560 and height 540–1600 |

Wait states: visible, hidden, attached, detached; defaults visible/5000 ms,
maximum 12000 ms. Initially absent targets are allowed, multiple matches are
refused. DOM visibility does not require native visibility. A click confirms
the action, not completion of an async React/server transition; wait for its
resulting heading/control before snapshot/capture.

Press keys: Enter, Space, Escape, Tab, Shift+Tab, ArrowUp/Down/Left/Right,
Backspace, Delete, Home, End, PageUp, PageDown, Control+A. Credential/password
controls and native file inputs are blocked by click/fill/press/select. Every owned page has a file chooser
listener that immediately calls chooser.setFiles([]) and records cancellation,
covering indirect label/button triggers. JavaScript dialogs are dismissed.
The upload tool sets the selected input directly; it does not click a chooser.

### Synthetic uploads and hidden resizing

The original eleven tools retain their contracts. Snapshot adds `fileInputs`,
a bounded list of exact CSS locators, labels, accepted types and disabled state
for the existing Library/Case inputs. Supported labels are `Choose a study document`,
`PDF or image for text extraction`, `Image to keep in case` and
`Image to review before sending`. Other inputs, including account/backup/profile
imports and directory selection, are not upload targets. A changed or disabled
input is refused. A fresh snapshot is required after each file selection and
after changing Case input mode. No renderer or native source modification is needed.

Uploads require `--fixture-root` at server/client creation. This directory must
be outside Git, user home/profile/credential paths, controller `c/` state,
runtime/dependency directories and helper assets. Network/device paths, traversal,
alternate data streams, links, junctions and hard-linked files are refused.
The root must contain `.renulus-control-fixtures.json` with exactly:

- `format`: `renulus-control-fixtures-v1`.
- `syntheticOnly`: `true`, the operator's declaration that these are owned synthetic fixtures.
- `files`: 1–32 records, each containing only `path`, `size` and `sha256`.

Each `path` is a flat lowercase basename matching
`synthetic-[a-z0-9][a-z0-9-]{0,79}.pdf`, `.png`, `.jpg` or `.jpeg`;
credential/account/profile names are refused. Size is an integer from 1 through
10 MiB; SHA-256 is 64 lowercase hex digits. The manifest is at most 16 KiB.
Use explicit fixture filenames to create declarations; do not enumerate personal
directories or declare acquired material as synthetic. No inline bytes, full path,
directory, multiple-file or clear-selection option is exposed through a tool.

Declarations are frozen when the controller prepares its session. Changing the
fixture set requires a fresh server, not `renulus_restart`. Only the requested
declared file is read. Each upload checks its ancestors, regular-file/link count,
real path, bounded size, file identity before/after reading, SHA-256 and media
signature. Verified bytes are passed as an in-memory Playwright `setInputFiles`
payload, so Playwright cannot reopen a substituted path. Media decoding remains
the application's job. The ordinary application rights, retention and processing
gates still apply. Selection completion is not extraction/import completion;
wait for the resulting product state. Fixture name/hash/size/MIME are recorded,
without persisting upload bytes in controller logs.

The October 7 parent fixtures are prepared outside Git at
`C:/rn-finish-20261007/evidence/control/synthetic-inputs`: `synthetic-study.pdf`,
`synthetic-image.png` and `synthetic-image.jpg`, with a complete manifest. See
[the lane handoff](../../docs/implementation/finish-control-inputs-20261007.md).
Append that root to the existing fixed CLI invocation. Then navigate Library or
Cases using the ordinary tools, call `renulus_snapshot`, and pass an exact
returned `fileInputs[i].locator` to `renulus_upload`. An empty list means no
supported file input was observed; do not invent an ID or selector.

`renulus_resize` uses only the BrowserWindow associated with the verified Flow
page, calls `setSize(width, height, false)`, and checks ownership/hidden state
before and afterwards. It never sets position, shows, focuses or attaches to a
window. It returns actual outer and content dimensions. Native clamping is an
error, not a successful requested size. Use the existing screenshot tool after
resize for a fresh frame. This tests app layout; it does not change OS DPI or
establish physical-dialog acceptance.

Renderer requests are restricted to the exact owned loopback origin and API v1
prefix. **Normal product routes are allowed**, including Learn/inference, Cases,
Library/import/extraction, Memory, study/planning and canonical writes. The app's
subscription, source and retention gates produce actual product errors. There
is no local mutation firewall or direct backend API tool. Native external/source/auth
opens and backup dialogs are suppressed by the app's background mode; backup
controls reach its cancelled-dialog branch. Scope of a future control session
is selected by its operator; this worker executes only mock/dependency checks.

## Bounds and evidence

UI operations serialize and are bounded by 15 seconds. Electron handle acquisition
is bounded to 10 seconds; actual hidden loopback Flow navigation readiness to
360 seconds. Normal close/EOF/SIGTERM cleanup gets **45 seconds**, with no early
forced-close reserve. Restart has a close phase up to 45 seconds and startup
phase up to 360 seconds. Cancellation interrupts UI work and closes only the
owned lifecycle. Hooks cover EOF, disconnect, SIGTERM, SIGINT and output errors.

The parent's native owner-liveness guard must quit/stop its backend independently
if this server vanishes: SDK clients may terminate stdio servers about two seconds
after EOF, faster than normal native shutdown. EOF mocks alone do not establish
this abrupt-disconnect behavior.

Documented DEBUG=pw:browser launch diagnostics are captured/redacted before
Playwright import/launch so early background events are observed. Fixed internal
main-process callbacks track show/focus history and sample all owned windows
every 150 ms and before/after actions. Main/profile/parent/owner PID, sandbox,
unfocusability and backgroundThrottling:false are checked. Read-only Windows
CIM queries verify observed main/backend executable, creation and parent identities.
No global window inventory or unrelated process kill is performed.
Runtime throttling is read through webContents.getBackgroundThrottling();
Electron 44 omits it from getLastWebPreferences. The app's session filter
covers startup; the controller adds its exact-origin filter after verified
Flow readiness, without accessing an initial navigation's unavailable frame.

ElectronApplication.close() uses normal app quit; verified main/backend exit is
required. Surviving/unverifiable children are failures. Essential cleanup starts
only at the lifecycle deadline, for recently verified owned identities; any
forced cleanup remains failed normal shutdown. No taskkill/tree kill is issued
by this controller. A reused PID is not an owned process.

Screenshot waits for document.fonts.ready and two animation frames (at most
five seconds), calls its BrowserWindow.capturePage with stayHidden:true and
stayAwake:false, then verifies hidden state again. Failed frame preparation
returns an error. Wait for the specific async UI transition before capturing.

External session outputs contain PNGs, logs.ndjson, receipt.json and session
ownership metadata. Receipts include main-bundle SHA-256, startup timing, origin,
exact process identities and normal/forced/surviving close evidence. Limits:
1000 log rows x 2048 characters; 200 rows per errors call; 48000 ARIA characters;
8 MB PNG. Account-like text, auth URL state, emails and known filled values are
redacted before persistence. Screenshots are synthetic-app pixels without pixel
redaction. Evidence is retained for review, not deleted on close.

Worker checks cover dependency installation, syntax and mock Node tests. The
parent owns actual stdio handshake, hidden native UI, fresh pixels, packaged
build and abrupt-disconnect acceptance. No native launch occurs in worker tests.
Parent source acceptance now includes the real 39-operation MCP journey and
seven-operation interactive client check. See
[the dated report](../../docs/implementation/app-control-20261006.md) for exact
receipts, preserved failures and the remaining installed/live boundaries.

For a bounded worker run, `RENULUS_CONTROL_TEST_ROOT` can point to a fresh,
short external evidence directory for controller mocks (created exclusively);
fixture security tests create separate directories beside it. Run Node with
`--test-concurrency=1`. October 7 checks reuse the parent's pinned development
modules read-only through an external test loader; no dependency installation,
lockfile change, native launch or engine execution is needed.

Primary API references checked on October 6, 2026: Playwright ElectronApplication,
Electron launch and locator/ariaSnapshot documentation at playwright.dev;
BrowserWindow/capturePage at electronjs.org; modelcontextprotocol/typescript-sdk
v1.x documentation; installed SDK 1.32.1 server/stdio.js and mcp.d.ts; installed
Playwright 1.62.1 types/types.d.ts. Electron.launch has no AbortSignal option in
this pin; its separate finite timeout bounds cancellation before a handle exists.
