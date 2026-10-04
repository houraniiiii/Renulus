# Connections subscription recovery

Verified 2026-10-04 UTC (the renderer test logs use 2026-10-05 Europe/Warsaw).
This follow-up owns the existing `apps/desktop/src/platform/ConnectionsPage.tsx`,
its mounted renderer tests and this evidence file. The isolated branch
`build/connections-auth` starts at integration `1a29f8d3`. The owned source paths
were unchanged in the parent's reported `93027cb4` and in the integration branch
when checked before handoff.

## Observed problems and implemented recovery

The original renderer recognised only `pending` as an active OAuth attempt.
Receiving the real backend's `exchanging` state stopped polling and discarded
the cancellation reference. The page now treats both states as active, retains
the original public authorization link/expiry across status-only responses,
continues polling through exchange and keeps cancellation available. Login
responses must match the active attempt and an understood status.

An OS browser-opening failure now offers reopening the same attempt. It does
not register another login. Both native and browser links are checked against
the existing HTTPS `auth.openai.com/api/accounts/authorize` boundary before
exposure. Invalid links release a known attempt instead of leaving an invisible
listener. The Go account link is deliberate and cannot interrupt another
connection operation or an active Codex login.

Failures retain operation-specific recovery: check status, start a fresh
expired/missing/declined login, retry catalogue refresh, retry cancellation,
retry selection or retry disconnection. Poll failures retain the visible
attempt and retry with a bounded delay. Public-status loading failures do not
remove the independent sign-in/cancel panel. Known late login-start results
received after unmount are cancelled; stale status results cannot revive a
cancelled or departed view.

Saved `configured`, no-model, authentication, provider and quota states expose
catalogue refresh and disconnection. Selection is offered only for a connected
account with an approved model actually reported available. A successful
connection still requires a separate explicit Use action. Disconnect reports
local removal separately from failed remote revocation and displays the public
ChatGPT connected-app recovery message.

The five approved identities remain Codex `gpt-6.1-sol`, `gpt-6-astra`,
`gpt-6-luna`, and Go `mimo-v2.6-pro`, `deepseek-v4.1-flash`. The renderer
distinguishes unknown availability, account catalogue listing, catalogue
absence and an account rejection. Text/image acceptance is separate from
catalogue listing; image interpretation quality remains unverified. No extra
model from a response is presented as an approved model. This page inspects
availability; it does not invent a persisted global manual-model preference.

Explicit Go entries are cleared immediately, posted with `select:false`, and
never written to browser storage. A rejected entry must be entered again; no
retry closure retains or automatically resubmits that secret. The official Go
account link uses the existing public-source bridge when available.

Existing Sources/retrieval and study-data components are reused and mounted
when their tab is selected. Opening the subscription tab only loads its public
health/connection reports. Flow tokens, buttons, inputs, badges and notice
patterns are retained. Active recovery has a clear place above the account
rows; the explanation column aligns to its content instead of stretching to
the subscription list's height. Shared CSS was not edited.

## Verification

The final focused command passed **96 tests in five files**, including
**40 mounted Connections tests** and the unchanged native profile/URL, transport,
retrieval-connection and data-management checks:

```powershell
$env:NODE_OPTIONS='--max-old-space-size=768'
npm test -- --maxWorkers=1 src/platform/ConnectionsPage.test.tsx electron/profile.test.ts src/platform/api.test.ts src/platform/RetrievalConnections.test.tsx src/platform/DataManagement.test.tsx
npm run build
```

The final run took 15.19 seconds. Production TypeScript checking, Vite renderer
build and Electron entry compilation passed. `git diff --check` passed.
Fixtures use synthetic keys, public catalogues and controlled same-origin
Fetch responses. Every Connections test rejects unexpected endpoints and
checks that generation, foreign-credential and external Fetch routes were not
called. Timer and deferred-body checks exercise pending/exchanging completion,
transient poll retry, terminal errors, cancellation and late-response races.

A separate ignored Vite harness loaded the actual component and Flow styles in
Chrome with synthetic Fetch/native-bridge implementations. It visibly exercised
browser-opening failure, reopening, cancellation and saved/no-model states.
The default desktop layout and a requested 390x844 narrow window were inspected.
The latter's measured content width was 345px, with equal scroll width and no
overflowing buttons, inputs or links. The viewport override was reset. A clean
reload was used for the final recovery/cancel sequence after source hot updates.

## Integration and limits

No new backend endpoint, auth-adapter rewrite, migration, dependency, shell
registration, module-order or native/preload change is required. The existing
component export and connection routes are unchanged. Integrate the owned
commit, rerun the focused checks and refresh the packaged renderer/native
source snapshot together with the parent's completed integration revision.

This lane did not open a real authorization URL, load host credentials, use a
real account, exchange/revoke live tokens or invoke model generation. Bridge
stubs and native URL unit tests do not establish an actual Electron/OS sign-in
journey or account-specific model access. Live completion/availability and
generation remain separately evidenced acceptance checks. Closing cleanup is
best-effort for known attempt IDs; a response lost before its ID is received
relies on the existing backend attempt lifetime.

Primary references checked for the account/authentication UX:

- OpenAI Codex authentication: <https://developers.openai.com/codex/auth/>.
- OpenCode Go account/key flow: <https://opencode.ai/docs/go/>.
- The implemented local seam is `runtime/renulus/runtime/api.py`, `auth.py` and
  `manager.py`; the parent separately verified a real local start/cancel cycle.
  That evidence does not imply live authorization/exchange or inference here.
