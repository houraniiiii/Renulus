# Final Flow renderer review — 2026-10-05

This bounded review used the existing Flow design and actual local application
routes. Two evidenced Updates usability defects are fixed. Two focus findings
remain for the shell and assessment owners. No visual redesign is warranted
by the observed screens. This is renderer/application evidence, not a new
claim of scientific content review, live subscription support or native PDF
acceptance.

## Scope and isolation

- Worktree: `Renulus-wt-renderer-final`, branch `review/renderer-final`.
- The eight-route review began at parent `14bb101f`. Parent `314c0e6e` was
  subsequently merged into this isolated branch for the targeted saved-case
  banner and Go eligibility checks. Those two surfaces were checked again;
  the eight-route sweep was not needlessly repeated.
- New production edits are confined to Updates `ReviewDetail.tsx` and
  `index.tsx`, with focused Updates tests. Shell, Connections, assessment,
  shared platform and native implementation changes remain with their owners.
- Owned renderer/backend ports were `5204`/`8774`. A new browser profile and
  synthetic local runtime profile were created under this worktree's ignored
  `.local/` directory. Only public bootstrap dependencies were reused.
  No account credentials, host application state or acquired collection was
  copied. Parent bulk/source tabs and ports `5198`/`5196` were untouched.
- The initial owned browser tab was followed by an owned headless Chrome
  profile when the collaborative preview host became unavailable. CSS viewport
  dimensions were measured in each capture, rather than inferred from a
  screenshot name. This does not establish Electron-native window behavior.

## Substantive findings

| Finding | Evidence and cost | Disposition |
| --- | --- | --- |
| Compact Updates selection leaves focus in the queue | At 620×720, the publication controls remained below the visible queue. Selection did not transfer keyboard focus into the chosen publication. | Fixed: at the existing ≤1000px stacking breakpoint, a newly selected publication focuses and scrolls its title into view. At 620×720, the title begins at y≈0 and Open publication at y≈127. At 1280px, selection retains queue focus. |
| Failed publication refresh reports above the current view | At 900×800, the accurate failure status was at y≈−1023 while Refresh metadata remained visible. The draft and prior digest were already retained, but the visible action appeared to have no result. | Fixed: refresh results now render beside the selected publication actions, using the existing Notice/status pattern. The same failure is visible at y≈170–224 and the synthetic draft remains intact. Selecting a publication clears the prior refresh message. |
| Pending Test autofocus hides the source currency notice | Opening the pinned T20 session focuses the question legend, scrolling “Source change needs question review” above the viewport at both 900×800 and 620×720. The notice exists and is accessible after scrolling back. | Should-fix; assessment/parent handoff. Keep the annotation visible when focusing a newly opened affected question. The relevant effect is `questionHeading.current?.focus()` in assessment `index.tsx`; SourceCurrencyNotice precedes its fieldset. No assessment code was changed here. |
| Fresh Ctrl+K focuses the close button | On the initial modal opening, activeElement is the button labelled Close destination search. Typing requires first moving to the search field. This was reproduced again with the current parent shell. | Should-fix; Mendel handoff. Explicitly focus the destination input after showModal. No shell code was changed here. Tab reaches the input, no-match feedback works, Escape restores the search trigger, and Tab/Enter opens a matched destination. |

The two Updates regressions were demonstrated before their fixes: the compact
focus test failed, and the existing failed-refresh test failed after requiring
the result inside Selected publication. The latter retains its assertions for
the educational draft and inspected-evidence checkbox. The browser verifies
actual scrolling and visible result placement, which jsdom does not establish.

## Observed journeys

All eight destinations — Today, Learn, Library, Cases, Test, Memory, Updates
and Connections — were visited through Alt+1–8 at measured 1280×800 and
900×800. Bundled Source Sans 3 loaded. The valid captures have no horizontal
overflow, renderer exceptions or attempted external browser requests. The
existing focal content, restrained actions and metadata hierarchy remained
coherent. The 620×720 navigation control exposed all eight destinations and
closed after choosing one.

The fresh profile installed the real original Renulus foundations pack. A
pending T20 session was linked to a synthetic K01 publication-byte change. Its
source detail retains K01-2024 and the locator Practice Points 5.4.1–5.4.2;
Table 41. View source updates reaches Updates. A separately committed wrong
T08 answer appears in committed-answer review with the original question/key
versions and a deterministic fresh/unassisted result of 0/1. These journeys
do not fabricate a publication review or alter the original answer key.

Temporary Cases context persists across destinations; Test and Memory show
their retention guards. Ending that context exposes normal study Memory.
Generated practice honestly requires an approved connected subscription and
keeps Generate practice disabled. Neither account is inherited or selected.

Source checking used the real Updates producer with a controlled anonymous
publisher transport: baseline, changed bytes, then offline. Manual Check now
and Refresh metadata report failure, stale state and the retained last success
and digest. Automatic checking remains Off. No reviewed/dismissed publication
was invented. These are application rules demonstrated with synthetic
transport, not a proof of current external publisher availability.

## Targeted current-parent surfaces

The owned backend was restarted from the merged current code, preserving only
this task's synthetic profile. Actual GET /connections returned Go
learning_use status unresolved and generation_allowed false. The 1280px and
620px render shows Learning requests paused separately from account status
and model availability. No Use OpenCode Go action is exposed. Keyboard Tab
moves from the policy link to the account link to the empty password field;
Check and save Go key remains disabled. No link was opened and no key, login,
model check or learning request was submitted. Transport identity/headers were
not externally exercised in this renderer review.

A synthetic daily case was started through the real API. Keyboard Save wrote
its explicit snapshot. At 900px and 620px, Cases shows Saved plus the accurate
saved-snapshot/new-changes notice; the shell says only explicitly saved
snapshots are kept. Keyboard Close and reopen retained the snapshot. Navigation
to Learn preserved the temporary case context; keyboard End removed the
banner and restored Your learning space. No provider discussion was requested.
The parent's focused mounted tests additionally cover explicit saved-case
and unclassified scope labels. No new defect appeared on these two surfaces.

## Checks and limits

From `apps/desktop`, after the final changes:

```powershell
node node_modules/vitest/vitest.mjs run src/modules/updates src/shell/scope-banner.test.tsx src/platform/ConnectionsPage.test.tsx
# 75 passed across 6 files: Updates 26, scope banner 4, Connections 45.

npm run build
# Typecheck, production renderer and build-electron.mjs passed.

git diff --check
```

The publisher transport was synthetic; the provider HTTP transport rejected
any attempt and recorded zero calls. There were zero live publication/provider
HTTP calls and no paid-tool use. No acquired source body is published in this
evidence. The profile has no helper assets or imported Library documents:
processing/extraction-unavailable screens are an accurate profile limitation,
not evidence for ready-document retrieval or native original viewing.

Local screenshots, DOM measurements and the harness remain under
`.local/renderer-final/` in this worktree, outside the commit. Useful captures:
`shots/updates-selected-620-before.png`, `shots/updates-selected-620-after.png`,
`shots/updates-refresh-offline-900.png`,
`shots/updates-refresh-offline-900-after.png`,
`shots/assessment-pending-900.png`, `shots/assessment-pending-620.png`,
`shots/destination-initial-focus-current-620.png`, `shots/go-paused-620.png`,
and `shots/case-snapshot-banner-620.png`. Per-capture JSON records the actual
viewport and observed faults. The all-route measurements are in `audit.json`;
final own fixes are in `verify-updates-final.json`, and the current-parent
checks in `parent-surfaces.json` and `saved-journey.json`.

Commit `c59d3ed8` contains the compact focus fix. The following handoff commit
contains inline refresh feedback, its strengthened regression and this
evidence. Parent `314c0e6e` is already integrated on the review branch; handoff
requires only these owned commits, not the local merge.
