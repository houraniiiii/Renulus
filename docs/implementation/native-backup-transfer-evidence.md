# Native recovery transfer

October 4, 2026, UTC. Parent integration; actual final packaged save-dialog
interaction remains a separate desktop acceptance check.

The renderer may ask the native window to save a ZIP or records-only JSON. The
main process validates its owning top-level frame, a UUID operation ID and the
two fixed recovery routes. A native Save dialog selects the destination and
confirms any overwrite. The app token stays in the main process and is sent
only to its known loopback backend. No destination path, arbitrary URL or
authentication value is accepted from the renderer.

The selected file is streamed with backpressure to an exclusively created
sibling partial file. MIME, HTTP status, finite transfer limits, received bytes
and completion are checked; successful output is synced and then promoted.
An existing destination remains intact on failed or cancelled transfers.
Cancellation, app close and the 30-minute bound abort the owned operation.
ZIP transfers are bounded at 8 GiB; records-only JSON retains its 16-MiB bound.
The segmented recovery producer still owns its tighter format-specific guards.

Five real Node HTTP/filesystem checks passed, including a 48-MiB stream, active
cancellation, an oversize partial preserving an existing file, redirect/raw
error refusal and a bounded structured API error. The same run passed 40
Connections renderer checks. TypeScript/Vite/Electron compilation passed after
the main/preload wiring and narrow PDF policy integration. The three blank/PDF
page detector regressions also passed. These checks do not simulate a completed
native dialog or claim multi-GiB recovery capacity.

The desktop lane separately proved its actual production PDF policy at physical
page 2 and a 32-MiB authenticated proxy-to-disk transfer. Its DownloadItem proof
uses a different native transfer seam; it does not establish the parent partial
file promotion. Final matching native staging must verify this Save dialog,
renderer cancellation and the actual recovery producer together.

The existing Flow recovery action remains the focal control. It uses the same
calm teal action, paper surface, Source Sans hierarchy and ordinary error/notice
components; filenames, transfer status and deliberate cancellation serve the
doctor's task. No new visual system or optional provider is introduced.
