# DC07 workspace integration seam

Import WorkspaceProvider, useWorkspace, WorkspacePanel and exported local props
from this directory. Shared ContentReference, AssessmentPolicy and ReaderProps
remain owned by platform/designC.ts; this module imports them.

- Provider: typed context/policy, optional initialPreferences,
  authorize(request, signal), onPreferencesChange, onContextChange.
- Hook: open(ContentReference), close, toggle, setContext, selectTab, closeTab,
  moveTab, showSection, setPosition, setPreferredWidth, restorePreferences,
  getPreferences, plus current context/tabs/layout inputs.
- Panel: availableWidth is the shell region **after** navigation, including
  conversation and workspace. onLayoutChange({mode,width,maximum}) lets the
  parent show the reader as the focused pane while keeping chat state mounted.
  onReturnToChat restores shell focus/place after closing.
- Inject Reader, SavedTestPreview and adapters.Files/Sources/Notes/Goals.
  These adapters own producer API calls and real content. No routes, sample
  content, readers or assessment engine are implemented here.

The open result means local reference/policy validation and tab selection, not
server permission. Every mounted content/section adapter first passes authorize;
missing authorization fails closed. Parent resolves actual owner/retention,
availability and permissions at its backend and returns the declared decision.
Readers/entrypoints receive AbortSignal, policy and context; they must abort their
requests and enforce policy at their own endpoints. Context/policy changes revoke
the prior gate and prevent late results. Active Test blocks assistance adapters
and retains neutral tab references.

Parent reads/writes /workspace/preferences and maps its final DTO to
WorkspacePreferences {width,tabs}. Every emitted tab is exactly
{content,context,retention:'saved',position}, matching the shared WorkspaceTab.
Titles, URLs, paths, bytes, scroll offsets, temporary references and selection are
excluded. Backend resolution of saved retention remains mandatory; a frontend
tag is not a privacy attestation. The callback itself does not persist.
initialPreferences restores at mount; restorePreferences merges an initial
async read without overwriting already-open tabs/positions. Do not feed stale
write acknowledgements back through restoration.

Temporary/unscoped positions and width changes stay volatile. Leaving such a
context discards its tabs. Saved contexts retain distinct tabs and locator/scroll
positions. Canonical content identity deduplicates within a context, including
new citation jumps. Test versions reject document locators. Closing a tab removes
the reference; closing workspace preserves it. Restored references must pass the
same access gate before rendering.

Sizing follows DC01: 480 preferred, 360–640 bounds, minimum chat 528. The panel
uses one focused pane below 888 available pixels (960 total with a 72 px rail).
Parent owns navigation collapse (candidate around 1280 total) and shell mounting.
Splitter drag and Left/Right (20 px; Shift 50), Home/End, Enter (480) change
preference; automatic clamping preserves it. Arrow keys/Home/End navigate tabs;
Alt+Up/Down reorders; Delete closes. Mount one panel per shell.

Local synthetic adapter tests establish the module seam. Parent still owes the
real preference API, readers/producers, integrated policy enforcement and hidden
app/narrow/200% acceptance. No DC07 feature completion is claimed here.
