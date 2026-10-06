# App-scoped development control — October 6, 2026

The owner stopped Computer Use while using the same PC and authorised the
recommended Playwright/Electron control through MCP. The development app now
supports hidden, non-focusable startup and Flow windows, a fresh synthetic
profile, its own managed backend, renderer input, app screenshots and owned
cleanup. This change makes ongoing development testing possible without
shared desktop input. It establishes source-app control at the scopes below.

## Implementation and integration

- `15a1e29e` and `f00831c6` add opt-in background startup, native/external
  suppression, owner-loss shutdown and diagnostic-pipe cleanup. Normal app
  startup remains the existing product path. Explicit absolute profiles and
  managed backends are required; dev-backend attachment is refused.
- Worker `ad733762` is integrated as `50575236`. Its eight-file, dev-only MCP
  package pins SDK 1.32.1, Playwright 1.62.1 and Zod 4.6.5 outside the doctor
  runtime. No browser download or shared dependency replacement occurred.
- `bff6037e` verifies Windows Playwright's physical controller → CMD launcher
  → Electron main → managed Python process chain. PID/executable/creation
  identities are checked before accepting Flow.
- `7f1080bd` reads runtime throttling with getBackgroundThrottling. Actual
  Electron 44 diagnostics show false while getLastWebPreferences omits it.
- `a11e3d2e` adds controller routing after verified Flow readiness. The app's
  own session filter covers startup. An initial navigation no longer calls
  request.frame before a Frame exists; callback errors are contained.
- `664c46cf` and `b4678c35` add an interactive local stdio MCP client and a
  regression check for that initial navigation. Piped requests are retained
  while the client establishes its connection.

Eleven strict tools expose start, snapshot, click, fill, press, select, wait,
screenshot, errors, restart and close. Tools cannot attach to another endpoint
or supply a profile/evaluation function. Screenshots await fonts and two
animation frames, then capturePage with stayHidden. Native Save requests
return cancelled; source/auth opens are blocked. HTML file choosers are
intercepted, but file upload is not exposed in this first toolset. Password
and credential fields are blocked. Product routes still reach their normal
subscription, source-permission and retention gates.

## Accepted evidence and preserved failures

All receipts, synthetic profiles and screenshots remain outside Git under
`C:/rn-control`. Failed aggregate runs retain their original status.

| Receipt | Result and exact scope |
| --- | --- |
| `native-20261006-01` | Failed aggregate: the test used a non-UUID backup operation and received the correct invalid_backup_request. Earlier real hidden navigation/input/screenshots and blocked source/auth actions are retained individually. One early Case capture was stale; it is not accepted as fresh visual proof. |
| `native-20261006-02` | Passed only the missing valid-backup cancellation, activation/second-instance isolation and normal managed shutdown. Reused the owned synthetic Native01 profile; no providers/imports. |
| `mcp-20261006-01` | Failed start from the incorrect direct-parent PID assumption. Handshake and eleven-tool listing occurred; no UI acceptance. |
| `mcp-20261006-02` | Failed start from the omitted preference-throttling field. Its normal operation-failure cleanup is retained. |
| `mcp-20261006-03` | Failed after an initial navigation Frame lookup crashed the server. The later read-only observation found no queried owner/main/backend/interpreter processes; it does not establish normal-close acceptance. |
| `mcp-20261006-04` | Failed at Track wait because closing a saved Case deliberately retained temporary context. Its 20 completed operations, three captures and normal operation-failure cleanup are retained; no full pass. |
| `mcp-20261006-05` | Passed at `a11e3d2e`, 18:19:42–18:22:01 UTC: 39 real MCP operations and five PNGs. Explicit synthetic Case save, end temporary context, ESENeph track selection, actual backup cancellation, normal restart, one persisted Case without duplication, saved text replay and SDK disconnect cleanup. |
| `client-20261006-01` | Passed at `b4678c35`, finished 18:32:37 UTC: seven actual stdio-client operations, hidden Library navigation, renderer Home key, ARIA snapshot, PNG and requested normal close. No tool errors; exit0. |

MCP05's first/reopened readiness was 42.078/25.532 seconds. The same synthetic
profile was reused on restart. Four window-created and two renderer-ready
events were recorded across both launches; no show/focus/error event or
renderer error was recorded. Native backup was cancelled through the actual
product UI. Prior launcher/main/backend identities were absent after restart.
Actual SDK transport disconnect left no owned identities after 12.861 seconds.
Its external controller receipt retains the completed restart-close; abrupt
server termination cannot be credited with an unperformed final close receipt.

The client used a new owned profile, reached hidden readiness in 33.214
seconds, and completed requested normal close in 16.553 seconds. Its close
receipt has no forced or remaining PIDs and no controller fault. The Library
capture shows the actual source-app UI. Captures from MCP05 show Home, typed
Case, saved Case, cancelled backup and persisted Case. The last capture
retains the scrolled catalogue position; its ARIA checks also establish the
reopened title/text and Saved state. These are app pixels, not desktop captures.

Worker evidence reports 27 mock passes. Parent Windows-launcher selection
passed three IDs, and the later initial-navigation selection passed three
IDs, including two overlapping launcher IDs. These are separately recorded
mock selections, not a newly claimed full aggregate. Existing desktop
typecheck/native build and the earlier 56 UI passes are retained at their
prior source scope; no broad sweep or completed import was repeated.

The 104-file bytes/SHA256 reconciliation is
`C:/rn-control/work-notes/accepted-control-manifest-01.json`, SHA256
`9e561553bcf260e8cb9dde197aa5739bfe2d40f914f1f03fe642cf154eb18850`.
MCP05 result SHA256 is
`12cbf9e92f7774f2b153c5d49bad39e9c59ed55f9304eab1262fadcfc0c91ff9`.
The compiled main SHA256 is
`477049229cff689e17f9d9bddb375797d2cc43f81560a904daf64a4c3fff848c`.
The manifest verifies all five MCP05 capture hashes, current controller/server/
client/native bundle identities, success conditions and unchanged failed origins.

## Operation and remaining boundaries

Read [APP_CONTROL.md](APP_CONTROL.md) and the
[MCP guide](../../tools/renulus-control/README.md). The owner's T3 project
configuration points to the active C server, prepared public Python/helpers
and external state root. Existing design declarations are preserved.

The already-open Codex chat had loaded pre-repair server modules. Its direct
start failed at the old preference check and is preserved separately. The
two verified idle old Node servers were stopped, with only their console
children present. This chat's direct MCP transport remains closed pending a
fresh server connection; no desktop restart or Computer Use was performed.
The validated `client.mjs` talks to a freshly loaded server now and is the
working path for continued interactive development in this chat.

The clean worker worktree is retired after integration; its original branch
and commit remain recoverable. Its only ignored files were npm dependencies;
worker evidence was already outside it. The held E supplement worktree and
normal E learning/account profile are preserved.

No provider, acquisition request, document import, personal Library access
or credential copying occurred in these control checks. Flow, approved
engines/models/subscriptions, Go pause, source permissions and explicit
Save retention are preserved. Physical Windows dialogs, external sign-in,
PDF/image/upload control, accessibility/DPI and matching installed/live
journeys require their own evidence. Hidden suppression is not successful
native-dialog acceptance.

The older frozen `02cd88e1` model-fix directory build has now completed
manufacture, package inventory, fresh deployment and deployed inventory
verification. Its result remains `manufactured-and-deployed`, not installed
acceptance. It lacks the newer background contract and is refused by this
controller before launch. The normal launcher remains `installed-699938f2`.
No heartbeat was recreated for this scoped development task.
