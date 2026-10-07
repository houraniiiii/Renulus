# Windows renderer finish — October 7, 2026

Bounded renderer lane in `C:/rn-finish-20261007/lanes/windows`, branch
`codex/final-windows-20261007`, based on integration commit
`ea73f4dcdb90f4f67e0fb2d948939cc213f95ffd`. The integration parent owns PR13,
native app control, connected generation, packaging and installed acceptance.

The corrected lease excludes `src/platform/ConnectionsPage.tsx` and its test.
No connection implementation, shared API/contract, model selection, dependency
lock, backend, engine, original, profile or earlier receipt was changed.
Impeccable context and Interface Design review informed a focused refinement
of the existing Flow renderer. Its colours, typography, rail and page structure
are retained. This is a source and mounted-DOM review, without visual approval.

## Defects repaired

| Surface | User-visible problem | Change |
| --- | --- | --- |
| Navigation | The native destination dialog's delayed close event returned focus to search after a destination had opened. Choosing the current destination did not run route focus/collapse logic. Keyboard dismissal always returned to the search trigger, even when opened from an editor. Scroll reset targeted the main element although the document scrolls. | Preserve the invoking element for dismissal; explicitly keep focus in the named main region after destination selection; include navigation revision in the focus/collapse effect and reset the document scrolling element. |
| Compact navigation | Opening the rail left keyboard focus after its links in DOM order; Escape did not return to the toggle. Global route shortcuts could navigate underneath a Case confirmation. | Focus the current link when expanding; Escape closes the rail and restores its toggle; suppress global search/navigation while a dialog is open. The existing IconButton now accepts a typed React ref. |
| Learn | Ask/Stop replacement and disabling the composer could strand keyboard focus. | Move focus to Stop while starting, then back to the retained question after finishing/failing, only if focus is still in the composer or has fallen to the body. A learner who moved elsewhere keeps focus there. |
| Generated practice | Pause, end, return to request and committed-answer review changed content without a surviving focus destination. | Focus the practice heading for those session transitions and the review heading when review arrives. Existing question/feedback focus remains in place. |
| Memory | Delete and history-removal confirmations replaced their focused controls without moving focus. Cancelling or deleting the record could leave focus on the body. Repeated Edit/History/Delete buttons lacked a description identifying the learning point. | Focus each inline confirmation; restore its surviving control on cancellation/history removal; focus the retained-learning heading after deletion. Associate record actions and deletion confirmation with the retained text. |
| Cases | Start/open/close/delete changed the current case without a focus handoff. Opening the close confirmation could announce the previous dialog title before React committed its new content. Cases also nested a main landmark inside the shell main. | Focus the named case section when session identity changes; show the native dialog after committing its action, associate its explanation, and reset on close; use a named section within the single shell main. |
| Library | Inspecting a source left keyboard focus in the list while its reader could be below the entire list at compact widths. Removing a source removed the focused reader action. | Focus the reader heading on explicit inspection or citation handoff; add Return to sources, restoring the originating control or Documents heading. Focus Documents after removal. Background refreshes do not refocus the reader. |
| Wrapping and focus visibility | Library mode buttons and section headings did not wrap; unbroken passage/notice text and assessment grid children could force overflow. New programmatic focus targets needed the existing visible focus treatment. | Wrap Library control rows and long passages, constrain fields/notices and assessment grid children, allow long main-content text to wrap, and apply the Flow focus outline to elements with tabindex. |

All existing data operations and retention guards are retained. The checks
exercise temporary context, no implicit Save, failed-operation recovery,
original/rights preservation and unchanged import idempotency alongside the
new focus behaviours, using controlled synthetic HTTP/SSE responses.

## Exact verification

All configuration, cache and raw evidence for this lane are external at
`C:/rn-finish-20261007/evidence/windows/`. Node `v24.15.0` and the parent's existing
public desktop dependencies were used through an ignored node_modules junction
in this worktree. No dependency installation or lock change occurred. Python,
Electron, browser automation, backend processes and models were not run.

From this lane's `apps/desktop` directory:

```powershell
node node_modules/vitest/vitest.mjs run --config C:/rn-finish-20261007/evidence/windows/vitest.config.mjs --maxWorkers=1 --fileParallelism=false --reporter=default --reporter=json --outputFile=C:/rn-finish-20261007/evidence/windows/mounted-checks-final.json
```

Result: **86/86 tests, six files, one worker, exit 0**, 24.04 seconds.
The external config selects only these affected mounted suites:

- `src/shell/search-focus.test.tsx`: 7 checks, including delayed native-close
  delivery, invoking-field restoration, same-destination navigation, compact
  rail focus/Escape and shortcuts suppressed over another dialog.
- `src/modules/learn/lifecycle.test.tsx`: 13 checks, including composer focus
  after failure and no focus theft when the learner moved to another control.
- `src/modules/assessment/practice-focus.test.tsx`: 1 sequence covering an
  existing synthetic session's question, pause, resume, review, end and return.
  It makes no generate request.
- `src/modules/memory/index.test.tsx`: 21 checks, including failed deletion,
  cancel/success focus, history confirmation, retained drafts and revision guards.
- `src/modules/library/LibraryBrowser.test.tsx`: 37 checks, including reader
  entry/return/removal, refresh stability, paging, import retry and rights guards.
- `src/modules/cases/CaseCurrency.test.tsx`: 7 checks, including case focus,
  committed dialog title, dismissal/reopening, close focus and no implicit Save.

From the lane root:

```powershell
node apps/desktop/node_modules/typescript/bin/tsc -p C:/rn-finish-20261007/evidence/windows/tsconfig.affected.json
git diff --check
```

Both passed with exit 0. The external TypeScript config selects changed TS/TSX
files, the new practice test and existing renderer declarations, plus their
transitive imports, with no emit or incremental state. This is not a desktop
build or a broad regression run. CSS changes received source review only.

The final source review then corrected the document scroll target. Only its
affected shell suite and TypeScript were repeated, both exit 0:

```powershell
# From apps/desktop
node node_modules/vitest/vitest.mjs run src/shell/search-focus.test.tsx --config C:/rn-finish-20261007/evidence/windows/vitest.config.mjs --maxWorkers=1 --fileParallelism=false --reporter=default --reporter=json --outputFile=C:/rn-finish-20261007/evidence/windows/shell-final.json
# From the lane root
node apps/desktop/node_modules/typescript/bin/tsc -p C:/rn-finish-20261007/evidence/windows/tsconfig.affected.json
```

`shell-final.json/log` records **7/7** passes in 1.97 seconds, including scroll
reset on new and same destinations. `typecheck-scroll-final.log` is clean.
The other five suites' source is unchanged from the 86/86 mounted run.

Earlier attempts remain preserved: `mounted-checks-1.json/log` records 85 passes
and one Case test assertion that ran before the passive focus effect;
`case-check-2.json/log` records the corrected wait and 7/7 passes. The initial
external typecheck could not resolve type libraries; the second identified
unsupported `exact` options in the new role queries. Explicit external type paths
and corrected queries produce the clean `typecheck-final.log`. No failed receipt
is overwritten or credited as a pass. The final mounted report is
`mounted-checks-final.json`, with its console log beside it.

## Parent's minimal actual acceptance

Use the app-scoped controller and owned synthetic profile described in
[APP_CONTROL.md](APP_CONTROL.md), after integrating this commit and building the
matching renderer. Keep hidden runs parent-owned; no native slot was used here.

1. From Learn's question field, Ctrl+K then Escape should return to that field.
   Select Library through search and then select Library again; after each
   dialog close, focus should stay in the Library main region and the document
   should be at the top, including when navigating from a long page. In compact
   navigation, open the rail, verify the current link receives focus, and use
   Escape to return to the toggle. A Case confirmation must block Alt+route
   shortcuts and another Ctrl+K dialog.
2. Inspect a synthetic Library document and a cited passage at desktop and
   compact widths. Verify the reader heading is reached and visible, Return to
   sources restores the originating control, background refresh does not move
   focus, and removing the synthetic source returns to Documents.
3. Open/cancel both Memory confirmations, remove one synthetic record, and
   start/close a synthetic Case. Verify each surviving focus target and the
   correct close/delete dialog title, including reopen after Escape. Use Tab
   and Shift+Tab to confirm the native dialog contains focus.
4. During the parent's separately authorised Learn run, verify Ask/Stop/failure
   recovery focus and a retained question. Move focus elsewhere during a response
   and verify completion does not take it back. For generated practice, use an
   existing synthetic session to check pause/resume/end/review/request focus.
5. Capture the five learning surfaces with long synthetic titles, source IDs,
   passage text and error messages, including the stacked reader and expanded
   navigation at narrow renderer widths. Confirm controls and focused headings
   remain visible and no page-level horizontal overflow appears. Do not credit
   JSDOM or source-level CSS review as layout measurement.

Physical Windows scaling, high-contrast rendering, native dialog behaviour and
spoken Narrator/NVDA announcements remain separate, unperformed acceptance.
When the parent arranges that scope, check 100/150/200% Windows scaling and
spoken destination names, retained-record descriptions and confirmation text.
Do not change the owner's display settings incidentally during hidden checks.

## Unresolved product and evidence gaps

Matching Chromium/Electron focus timing, scrolling, compact overflow and visual
appearance remain unverified for these patches. In particular, the mounted
dialog shims do not prove native inertness, Tab trapping, Escape behaviour or
screen-reader speech. Other controls and all reviewed-bank flows were not given
a new exhaustive accessibility audit by this bounded lane.

Successful connected generation, automatic learning capture, dependent live
journeys, engine behaviour and matching installed/package acceptance remain
parent work. Prior delivery/recovery receipts retain their original scope; this
patch grants no new credit to those outcomes. The renderer changes need no
shared contract, migration, dependency or account change to integrate.

## Changed paths

All paths below are relative to the assigned lane root; no other tracked path
is included in this patch.

```text
apps/desktop/src/shell/App.tsx
apps/desktop/src/shell/shell.css
apps/desktop/src/shell/search-focus.test.tsx
apps/desktop/src/ui/index.tsx
apps/desktop/src/ui/styles.css
apps/desktop/src/modules/learn/index.tsx
apps/desktop/src/modules/learn/lifecycle.test.tsx
apps/desktop/src/modules/assessment/GeneratedPractice.tsx
apps/desktop/src/modules/assessment/assessment.css
apps/desktop/src/modules/assessment/practice-focus.test.tsx
apps/desktop/src/modules/memory/FactItem.tsx
apps/desktop/src/modules/memory/index.tsx
apps/desktop/src/modules/memory/index.test.tsx
apps/desktop/src/modules/library/index.tsx
apps/desktop/src/modules/library/library.css
apps/desktop/src/modules/library/LibraryBrowser.test.tsx
apps/desktop/src/modules/cases/index.tsx
apps/desktop/src/modules/cases/CaseCurrency.test.tsx
docs/implementation/finish-windows-20261007.md
```
