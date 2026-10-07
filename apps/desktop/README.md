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

The Windows payload uses official CPython 3.14.4 embeddable x64 Python and the
selected Windows wheel tree. python314._pth limits imports to the bundle and
disables user/registry/site startup discovery. No venv launcher, pyvenv.cfg or
developer interpreter path is shipped. Doctors launch the application executable;
Python, uv, Node and compiler tooling are build tools only.

For developer packaging, run scripts/stage-backend.py with explicit --source,
--source-revision, --environment, --helpers, --python-archive and a fresh --target
under test-results. The archive checksum is enforced. Only reviewed public helper
files are copied and hash-checked; their manifest must equal the source-root
packaging/runtime/helper-assets.json. The committed source snapshot includes all
numbered migrations, content packs, licences and attributed Hermes runtime.
An explicitly approved --runtime-patch-repo/--runtime-patch-revision applies only
the scoped runtime diff in generated scratch data, refuses conflicts and records
the patch/revision/hash. It never edits either source repository.

scripts/stage-renderer.py --source <integration> --revision <commit> --target
<fresh-test-results-folder> builds/typechecks committed integrated module pages
in this lane's scratch directory. --include-native also preserves the committed
main/profile files and compiles them with this lane's owned backend.ts adoption.
Its source/adoption hashes and exact diff are recorded in dist-electron.
Set RENULUS_RENDERER_BUNDLE to its absolute apps/desktop/dist path,
RENULUS_NATIVE_BUNDLE to its dist-electron path, and RENULUS_BACKEND_BUNDLE to the
verified backend payload. All three integrated inputs must use one revision;
the native entry must match this lane's actually installed patched Electron pin.
npm run pack:win builds the native entry and an unsigned Windows directory under
release/win-unpacked. To build NSIS after the directory proof, invoke the pinned
electron-builder CLI with --config electron-builder.config.cjs --win nsis
--publish never. Signing is explicitly disabled; installation is per-user with
no elevation, automatic launch or generated desktop/start-menu shortcuts.
App data is preserved on uninstall.
NSIS toolset1.2.1 (NSIS3.12) and Windows7-Zip toolset1.0.0 are explicitly pinned.
Their official release archive digests match the installed builder's checksum
tables; acquisition and resulting artifact hashes are recorded with evidence.

Copy the complete win-unpacked folder to a fresh location before proof. Set
RENULUS_PACKAGED_EXECUTABLE to its absolute Renulus Development.exe, then run
node scripts/native-evidence.mjs. Packaged proof strips the target PATH to OS
directories, asserts python/python3/py/uv/node/npm do not resolve, verifies the
bundled interpreter paths and launches two independent managed profiles. It
checks actual helper/import readiness and disconnected Connections, sandbox,
authentication, routes and owned-child cleanup. RENULUS_EXPECT_SOURCE_REVISION
can enforce the exact committed snapshot while preserving the bundled native
adoption provenance in evidence. RENULUS_INSTALLED_PROOF=1 marks
the same checks against an executable in the explicit isolated install folder.
These checks do not establish signed or clean-machine release evidence.

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
