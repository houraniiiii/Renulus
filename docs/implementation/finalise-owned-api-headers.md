# Owned renderer shutdown correction — October 6, 2026

Actual installed native06 reached the populated six-format Library backup and
closed while an owned PDF ingestion job was processing. The backend disappeared,
but Electron remained on an uncaught JavaScript error dialog. This is a genuine
product failure; the ordinary-close gate and whole invocation remain failed.

Computer Use captured only the owned Error window (handle 75173818, main PID
16468). Its text identifies TypeError: Object has been destroyed at the installed
main.cjs line 601, column 41. Reading that exact ASAR source identified the API
authorization callback's late access to the destroyed window's webContents ID.
This differs from the earlier Windows backend-exit observer issue. The existing
backend teardown and Hermes fork are unchanged by this correction.

The captured JSON and PNG are retained in
C:/rn-finalise-20261005/parent-native-035ca7bd-06/owned-error-dialog.json and
owned-error-dialog.png, SHA256
7d4b8582986dcbcbf4aacbee94cd8fa6e8278cfa5096c491f2fcc90f6951e96b and
77dbc3fb0a82957062c7d90e89aca637ef0b400dd9b06021bb46dba0ea973260.
The parent acknowledged that exact dialog for cleanup; main 16468, backend
37664 and controller 24740 were subsequently absent. Controller exit 1 was
recorded at 01:15:53 UTC. Neither acknowledgement nor cleanup is normal-close
acceptance. The immutable native06 receipt remains failed.

The new ownedApiHeaders handler captures the live renderer object and numeric
ID before installing the listener. It cancels requests after window or renderer
destruction before accessing native getters, and refuses every foreign renderer.
The live owned renderer retains the same app-token stamping and request headers.
The API allowlist, session isolation, source permissions, product/runtime/data
contracts, selected subscriptions/models and all Library originals are preserved.

Four focused regressions passed: live-owner token replacement, foreign-renderer
refusal, the observed late request after window destruction, and renderer
destruction while its window still exists. The two destruction fixtures throw
from native getters, reproducing the observed failure boundary. Their JSON
receipt is C:/rn-finalise-20261005/parent-owned-api-headers-01/tests.json (4/4,
no failures); desktop TypeScript passed. No completed backend/engine/content
sweep or Library import was repeated.

A new source freeze, matching manufacture/installation and actual active-ingestion
shutdown/reopen acceptance are required before launcher promotion. The earlier
035ca7bd installer, eleven individually passed native UI/identity/runtime gates,
six accepted Library originals, verified backup and failed shutdown evidence
remain preserved. This report alone does not establish a passing installed app,
connected journey, live generation or lifecycle maintenance.
