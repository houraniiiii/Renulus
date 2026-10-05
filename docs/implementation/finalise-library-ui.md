# Library UI finalisation — October 5, 2026

Assigned worktree: `C:/rn-finalise-20261005/lanes/library-ui`. Branch:
`build/finalise-library-ui`. Baseline: `9d26f1eedf31cd488b9aab5837a105ee152d9efa`.
Owned paths: `apps/desktop/src/modules/library/**` and this report. Issue #3.

## Scope and design intent

Repair deliberate Library import, failed-job recovery, original viewing and
Office location journeys using the existing local API and synthetic fixtures.
Shared contracts, native application/profile/account and final installed
acceptance stay with the parent.

Interface Design and Impeccable were read and applied from the installed
`C:/Users/karol/Documents/t3-workspaces/Renulus/.agents/skills/` directory.
At initial inspection no `.interface-design/system.md` was found in this
worktree or the supplied skills workspace. `PRODUCT.md`, `DESIGN.md`, existing
Flow tokens and components provide the incumbent design. Shared design files
and the normal native file input are preserved.

- Intent: an EU nephrologist brings authorised study material, understands its
  actual import state, recovers a failure and returns to the original.
- Hierarchy: source title leads the reader; import progress/recovery follows;
  edition, terms and locations remain secondary.
- Palette: existing reading paper, clinical white, pale sage, petrol teal and
  dark green ink. Warning/error colours only describe observed problems.
- Depth and surfaces: existing quiet borders and sage reader surface; no added
  elevation, modal or card system.
- Typography: existing Source Sans 3, source titles in strong semibold, body
  explanations at the existing size and secondary metadata in muted ink.
- Spacing: existing 4px base and 8/12/16/24px grouping. Native file input,
  Button, Input, Notice, LoadingState and ErrorState are reused.

The source/edition/passage/slide/sheet/original vocabulary and explicit
permission boundary drive the structure. Actual source locations are retained;
no invented pages, counts or rights are added. Native picker automation's
failure to observe a dialog is not treated as evidence of a product defect.
The parent reserved collaborative preview `tab_1` and ports 5196/8787. This
worker used no preview tab, native application, helpers or live providers.

## Implemented behaviour

Failed note/file requests retain the draft title, text or selected file, and
permission confirmation. Retry uses the same import key for unchanged input;
editing the input creates a new key. Unicode titles and metadata use JSON
escapes in HTTP headers, retaining their decoded values. Empty, oversized,
unsupported or unavailable formats explain their problem beside the native
picker. Selecting another file requires a fresh permission confirmation.

The reader loads the canonical latest job and document, shows its actual
phase/error, and refreshes while queued or processing. Different revisions
cannot be cancelled or substituted. A job/document state transition is
rechecked before updating the reader. A cancellation that loses to publication
is shown as Available. `/library/queue` supplies the waiting count and worker
state; missing counts produce an error rather than an invented zero.

A deliberate retry creates a replacement revision of the same document using
its existing metadata, rights, reservation and scope. Acquired receipts instead
return to Collected sources so version/hash/permission checks run again. No
receipt is selected or imported automatically. The receipt title filter is
bounded to the existing 200-character API limit. Partial batch failures retain
their rejected selection. Available earlier originals and pinned citations
remain usable during a failed replacement.

Ready images with no extracted text explain that the original is usable for
visual study and absent from passage search. PNG/JPEG originals offer Save; a
failed preview retains that action. TIFF offers an explicit save path instead
of a broken inline preview. Office locators retain actual slide/sheet/item/table
labels and provide correctly suffixed original downloads. Empty original
responses fail visibly; load retry remains on the same pinned original.

## Exact functional UI state evidence

All checks below use controlled synthetic renderer/API fixtures, real React
components and the existing local transport. They do not run document engines.

| Trigger | Observed renderer state and action | Evidence |
| --- | --- | --- |
| Note request returns 503 | Title and note remain; Try again posts the same payload/key in personal-library scope | `LibraryBrowser.test.tsx` |
| File request returns 503, including Unicode title | Selected File, title and permission remain; retry sends the same File/key and decodable ASCII JSON header | `LibraryBrowser.test.tsx` |
| File changes, unsupported extension or size above 64 MiB | Permission resets; field reports the concrete problem; Add document stays disabled; no import POST | `LibraryBrowser.test.tsx` |
| Latest import fails | Actual error/reason appear; retry retains document ID, edition, licence, scope and model-input=false rights | `LibraryBrowser.test.tsx`, `ImportStatus.test.tsx` |
| Acquired article retry, including long title | Matching register/title filter opens within 200 characters; receipt remains unchecked; no raw-file replacement or automatic import | `LibraryBrowser.test.tsx` |
| Selected batch partly fails | Successful receipt is unchecked; rejected receipt remains selected; no automatic second POST | `LibraryBrowser.test.tsx` |
| Job moves queued → extraction → ready | Actual phase and state update; polling stops on terminal state; mismatched revision blocks mutation; publication winning cancellation is Available | `ImportStatus.test.tsx` |
| Worker paused/running or queue DTO missing count | Supplied count and actual worker state appear; paused state gives restart recovery; missing count fails without claiming zero | `ImportStatus.test.tsx` |
| Queued no-text image becomes ready | Reader changes to Available and exposes Open original; no-text notice appears without invented page or zero-location highlighting text | `SourceInspector.test.tsx` |
| Replacement fails with an earlier ready revision | Earlier edition and original remain open; failed replacement does not supply the original URL | `SourceInspector.test.tsx` |
| Office citation with no physical page | PPTX shows Slide 2, XLSX Sheet Adequacy, DOCX Document table; all three expose the corresponding original extension | `SourceInspector.test.tsx`, `OriginalViewer.test.tsx` |
| Image decode, original fetch or empty response fails | PNG/JPEG retain Save; TIFF explains external viewing; fetch retry targets the same original; empty response creates no viewer/blob | `OriginalViewer.test.tsx` |

## Verification receipts

The completed pre-relocation suite was recovered from the existing tool output.
It was not rerun merely to create a log. Working directory was this worktree's
`apps/desktop`. Exact command:

```text
node node_modules/vitest/vitest.mjs run src/modules/library --pool=threads --maxWorkers=1 --no-file-parallelism --testTimeout=15000 --hookTimeout=15000
```

Recovered terminal summary:

```text
 Test Files  6 passed (6)
      Tests  118 passed (118)
   Start at  12:33:46
   Duration  49.14s (transform 4.44s, setup 0ms, import 9.02s, tests 27.54s, environment 10.19s)
```

After relocation the only production-code refinement was bounding the acquired
receipt title filter. Its existing test was extended to a title longer than
200 characters and checked alone:

```text
node node_modules/vitest/vitest.mjs run src/modules/library/LibraryBrowser.test.tsx --pool=threads --maxWorkers=1 --no-file-parallelism --testTimeout=15000 --hookTimeout=15000 -t 'returns an acquired article retry'

 Test Files  1 passed (1)
      Tests  1 passed | 35 skipped (36)
   Start at  13:12:20
   Duration  4.89s (transform 1.94s, setup 0ms, import 2.53s, tests 776ms, environment 1.24s)
```

`npm run build` passed with exit 0 after that production refinement: TypeScript
`tsc --noEmit`, Vite production renderer (1,954 modules, 3.50 seconds), and the
Electron main/preload bundle script. The Library renderer chunk was
`dist/assets/library-C9WVkeRq.js`, 60.51 kB / 17.55 kB gzip. These ignored build
outputs are verification artifacts, not an installed package. The later test
fixture-only correction removed trailing whitespace from its synthetic title.
No production source changed after the successful final build.

Earlier attempts remain qualified: the initial fork-worker run passed 45 checks
but had two worker-start timeouts. The first full thread-worker run had 113
passes, two five-second test timeouts and one new assertion made before citation
loading completed. The wait was corrected and the 118-check command above
passed. The first resumed long-title check failed because its synthetic title
had trailing whitespace that the accessible-name lookup normalised; the
fixture was trimmed and the isolated check passed.

The ignored `apps/desktop/node_modules` junction reuses the supplied public
`E:/Renulus-native-delivery/desktop-20261005/environment/node-3ff9b0d6/node_modules`;
no dependency installation or rebuild was performed. Git metadata now resolves
to `C:/Renulus-native-delivery/desktop-20261005/repo/.git`, while this assigned
worktree and branch remain unchanged.

## Changed paths and handoff limits

All application edits are under `apps/desktop/src/modules/library/`:

- New: `ImportStatus.tsx`, `ImportStatus.test.tsx`, `QueueStatus.tsx`.
- Modified: `index.tsx`, `types.ts`, `file-formats.ts`, `library.css`,
  `LibraryBrowser.test.tsx`, `SourceInspector.tsx`, `SourceInspector.test.tsx`,
  `OriginalViewer.tsx`, `OriginalViewer.test.tsx`.
- Report: `docs/implementation/finalise-library-ui.md`.

No shared contracts, runtime, schemas, migrations, helper pins, main/preload,
design tokens or package manifests changed. Hermes, SQLite and the selected
document/memory engines and subscription/source-operation policies are retained.

Material behaviour limits for the parent:

- A direct failed-job retry requires deliberate re-selection of the original
  file or re-pasting the note; there is no new stored-byte retry endpoint. An
  acquired retry requires a matching catalogue receipt. A renamed/missing
  receipt may need clearing/refining the title filter or refreshing the catalogue.
- Available describes a completed revision/original; search still depends on
  passages and existing source eligibility. No-text images remain outside
  passage retrieval.
- Office and TIFF originals use external viewers. Office locators tell the
  reader where to look; this patch does not provide automatic Office section
  jumps or exact highlighting.
- Native picker operation, installed blob downloads/decoding, exact original
  bytes and matching installed citation acceptance remain parent-owned. No
  screenshot or visual/native acceptance is claimed from jsdom or the build.
  This is bounded renderer evidence, not full end-to-end product acceptance.
