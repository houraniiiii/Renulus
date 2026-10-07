# Final keyboard and pinned-source notice fixes

Verified on 2026-10-05 in isolated worktree `Renulus-wt-focus-final`, branch
`fix/focus-final`, from parent `6abd3ae9` plus prior Updates audit commits
`c59d3ed8` and `8806613f` (local cherry-picks `4b2786ca` and `506e28dc`).
The user granted a narrow App/search and Assessment lease for these two findings.

## Changes

- Destination search explicitly focuses its input after opening the native dialog.
  Closing still clears the query and returns focus to the trigger. Repeated Ctrl+K
  while open, typing, and background runtime-health completion do not refocus it.
- When a pending question first becomes visible, its existing source-currency
  notice receives focus and scrolls into view before the answer choices. Questions
  without a notice retain legend focus. The effect follows the displayed question,
  including Next question after feedback; answer editing, source help and overview
  refresh do not trigger it. Committed-history notices remain outside the tab order.

Only focus behavior changed. Source currency rules, pinned question/key versions,
deterministic scores and committed attempts retain their existing behavior.

## Focused checks

Both original focus regressions failed before the production changes. The final
run passed **14 tests across four files**, using the integration worktree public
Python and Node dependencies:

```text
node node_modules/vitest/vitest.mjs run src/shell/search-focus.test.tsx src/shell/scope-banner.test.tsx src/modules/assessment
npm run build
```

The build passed type checking, Vite production bundling and `build-electron.mjs`.
Tests include initial/reopened search focus, close focus return, delayed runtime
health, saved-case scope banners, next-question focus, selected-radio focus, and
source-help focus. The existing original-pack/real-SQLite Updates journey verifies
detected, reviewed and dismissed annotations with original pinned keys, scores and
committed answers preserved. No test claims scientific review of teaching content.

## T3 keyboard journey

Used a fresh owned T3 preview tab `tab_r` on port 5206 with an isolated backend
profile on port 8776. Parent `tab_o` and `tab_p` were not operated on.

- Ctrl+K immediately focused `#destination-search`; no-match search worked. Escape
  returned focus to the search trigger. Reopening, typing Test, then Tab/Enter
  navigated to Test.
- Opening a pending original T20 question focused its source notice. In the actual
  measured **1683 by 1051 CSS-pixel viewport**, the notice occupied y=169–348 and
  the question legend began at y=372, so the warning was fully visible.
- Three Tabs reached the first option. ArrowDown selected B and retained radio
  focus. Tab/Enter opened local source help; after help and overview refresh,
  focus remained on a button, B remained selected, and the notice was not refocused.
  The UI still showed “Question version 1 · key 1 remain pinned.”

T3 requested 1280 by 800 but reported the measured viewport above. A compact resize
request timed out without changing it; this follow-up does not establish compact
browser proof. The original eight-route audit was not repeated.

Local metadata: `.local/focus-final/t3-evidence.json`. Screenshot:
`C:/Users/karol/.t3/userdata/browser-artifacts/browser-screenshot-127-0-0-1-muuk7v2a-e3ef4a72.png`.

The fresh profile used the original teaching pack and a synthetic baseline/change/
offline source transport. Counters recorded **0 provider calls, 0 live network
calls, and 3 synthetic publisher requests**. No acquired source bodies or host
profile state were copied or published. Local transport establishes application
behavior, not current publisher content or independent latest-guidance review.
