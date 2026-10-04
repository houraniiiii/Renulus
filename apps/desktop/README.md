# Renulus desktop

React/TypeScript Flow renderer and a narrow Electron main process. Run from this
directory with Node 22.22+ or 24.11+ and npm.

- npm ci installs the pinned dependencies.
- npm run dev starts the browser preview on 127.0.0.1:5190.
- npm run build checks types and builds the renderer and Electron entry.
- npm test runs transport, scope and native lifecycle tests with synthetic data.
- npm run dev:electron starts an independent development instance.

Configure RENULUS_DESKTOP_PORT and RENULUS_BACKEND_PORT when another lane uses
the defaults. The Vite server proxies /api to the loopback backend. Set the
same RENULUS_SESSION_TOKEN on Vite and the backend; it is never exposed as a
VITE_ variable or returned to the renderer.

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
