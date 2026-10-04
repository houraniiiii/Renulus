# Renulus desktop

React/TypeScript Flow renderer and a narrow Electron main process. Run from this
directory with Node 22.22+ or 24.11+ and npm.

- npm ci installs the pinned dependencies.
- node scripts/install-electron.mjs verifies and installs the official pinned
  Windows Electron artifact before native development.
- npm run dev starts the browser preview on 127.0.0.1:5190.
- npm run build checks types and builds the renderer and Electron entry.
- npm test runs transport, scope and native lifecycle tests with synthetic data.
- npm run dev:electron starts an independent development instance.

Configure RENULUS_DESKTOP_PORT and RENULUS_BACKEND_PORT when another lane uses
the defaults. RENULUS_BACKEND_URL may specify an HTTP loopback origin instead
of a backend port. The Vite server proxies /api to that backend. Set the same
RENULUS_SESSION_TOKEN on Vite and the backend; it is never exposed as a VITE_
variable or returned to the renderer. These are app-only development tokens,
not provider credentials.

The native development launcher builds first, then uses a fresh isolated profile
under test-results unless RENULUS_PROFILE is an explicit absolute path. Set
RENULUS_PYTHON to this project's dependency environment if the worktree has no
.venv/Scripts/python.exe. Main starts one loopback backend with a random session
token and free port, authenticates readiness, and owns its lifetime. The renderer
has a nonpersistent session, sandbox, context isolation and no Node integration.
Only main injects API session authentication. The native bridge exposes version
and exact-host/path system-browser account sign-in; no provider keys are returned.

For development only, RENULUS_BACKEND_URL plus RENULUS_SESSION_TOKEN attaches
to an existing local backend. It authenticates that server without adopting or
stopping it. A packaged app always owns its backend. Windows fallback shutdown
uses the attributed Hermes process-tree helpers; graceful server callbacks need
the integration owner's control seam.

npm scripts are version-scoped for Electron 44.5.1 and esbuild 0.28.1. The unused
Squirrel installer hook is disabled. The pinned Electron release uses its own
maintained extractor; no extract-zip 2.0.1 remains in the lock. Do not replace
these policies with blanket script approvals or npm audit fix --force.

Native/browser proof scripts use temporary @playwright/test 1.62.1 tooling. For
reproduction, install that exact package with --no-save --package-lock=false
--ignore-scripts, then run scripts/native-evidence.mjs or browser-evidence.mjs.
RENULUS_TEST_ATTACH=1 selects native attachment evidence using the explicit
development backend/token. They require disconnected synthetic profiles and
write captures/public state under test-results. They do not log in or call models.

pack:win is a packaging reservation that requires an explicit absolute
RENULUS_BACKEND_BUNDLE with verified renulus-backend.exe and helpers. It builds
an unsigned directory first, never publishes, and preserves app data on uninstall.
A self-contained Windows backend/helper bundle and installer verification are
the next integration steps; source native launch does not establish installation.

Feature entry points are src/modules/{study,learn,library,cases,assessment,
memory,updates,connections}/index.tsx with a default React component. A missing
entry shows an honest integration state. Import useNavigation from
src/shell/navigation, shared controls from src/ui, api<T> from src/platform/api,
and stream<T> from src/platform/stream. Modules own their domain types and CSS.

Navigation uses only destination names in history. Handoff payloads remain in
React memory; temporary-case and unclassified scope cannot be promoted by a
normal navigation request. Use the explicit fresh-study action to end the
temporary context. Module effects must abort and cancel their backend runs on
unmount. An explicit case Save is a module-owned backend transition.

The initial package manifest/lock, shell, platform and UI are shared reservations
after foundation handoff. Request changes through the integration owner.
Do not edit these files from a feature lane.
