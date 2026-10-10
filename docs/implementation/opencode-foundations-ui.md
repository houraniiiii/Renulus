# OpenCode foundations UI validation

2026-10-10. UI build/validation lane in
`C:/Users/karol/.codex/worktrees/opencode-foundations/repo`, branch
`codex/opencode-foundations`, starting at
`c2bd896420fb88f76d63ca576414dbbba182f4c2`.

**Current status:** Final backend lifecycle run **07** passed on H24
`756c8ebc` (`Services.shutdown` completed-task guard). Fresh typecheck and build
passed; all 505 source records and 54 build artifacts stayed unchanged through
the hidden launch, existing New chat route check and **0.740-second normal
close**, with no forced or remaining app processes. All eight controller
requests succeeded. The former controller process no longer existed, so the
supported tool created a fresh owned synthetic profile; this is not evidence of
reopening the prior retained profile. The original profile and prior receipts
remain preserved. The cross-loop branch itself is covered by the parent's
public service regression, not this ordinary UI lifecycle.

Fresh TypeScript, renderer and Electron builds also passed for run **06** on
committed Notes deletion fix `b6a4a7da`, including H24's
`f6bdb589` completed-close-task guard. The narrow actual Notes create/edit/
history/delete journey passed: acknowledged deletion cleared both the revision
list and historical text **without closing or reopening the panel**. The fresh
backend then closed normally in **1.126 seconds**, with no forced or remaining
processes. All eight read-only canonical cleanup checks passed. Every source
and artifact checkpoint matched the build through close.

Earlier builds passed for run **04** on H24 `29d14786` plus the parent's
`main.ts` shutdown ordering, and for run **05** on committed Notes refresh fix
`ced998e6`. Run 04 completed
the hidden Memory/Library/cited Chat restart checks and the requested
**1000 × 720 outer window at 100% and 200% zoom**. All 505 source records and
54 build artifacts stayed identical through its final normal close, even as
HEAD advanced to `9a10562a`. The earlier explicit recall rebuild and positive
query are retained separately in preliminary run 03.

Run 05 saved two actual Notes revisions, read revision 1 and deleted both.
Canonical deletion succeeded, but **the mounted Notes panel retained its old
revision buttons and historical text until reopened**. Captures 0043–0045 and
the read-only deletion receipt distinguish this UI finding from completed
storage cleanup. That historical failure is retained unchanged; run 06 accepts
the parent's subsequent repair on its recorded bytes. Parent-owned production
source was not changed by this lane. Across runs 03–07, all **53 captured PNGs
were visually inspected**.

The initial affected renderer run has **136 passed, 1 failed, 0 skipped** in
seven files. The parent subsequently directed the one-line stale Library copy
repair, and that entire file now passes **37/37**. The other 100 affected tests
retain their initial passing evidence; this is not a fresh seven-file green run.

The post-close run 05 checkpoint detected the later two-line
`MemoryService.close` guard, subsequently committed as `f6bdb589`. It was absent
before that close and was accepted only in run 06 after the parent's stability
signal. Electron and its managed backend are now closed, with **eight normal
closes** across the five runs and two owned synthetic controller sessions,
with no forced or remaining app processes. The run 07 controller remained
connected at evidence capture. The parent committed the application fixes and
the narrow Library expectation repair, then authorized a scoped commit of this
UI evidence note only.
The parent reported 689 renderer tests passed and 13 skipped before fixing the
currency fixture startup conflict in `e57e4d89`. It later confirmed the actual
source-currency frontend case passed in its full rerun. That broader suite was
not executed by this lane.

## Scope and provenance

The user authorized foundation implementation and UI verification; the parent
assigned this lane builds, affected renderer tests and hidden
Memory/Chat/Library/restart/no-auto-send checks. Only ignored dependency junctions,
generated build output, owned external scratch and this document were initially
written. A later parent instruction permits only the existing supported-format
message expectation in `apps/desktop/src/modules/library/LibraryBrowser.test.tsx`.
That one literal is now repaired; no new test or production change was added.
No shared dependency package, lockfile or other lane's work is edited. The
parent integrated the Library expectation repair. The final parent instruction
authorizes this lane to commit only this evidence note; parent documents and
application changes remain outside that commit. The broader suite is the
parent's integration check.

The parent selected **H01/H24** for this implementation batch within the user's
authorization for the first few foundation tickets.
H02 remains the next batch. Current Memory/Chat/Library checks are unchanged-flow
regressions; they do not introduce a renderer feature migration or an H02 host
citation/tool flow.

Scratch: `C:/Renulus/scratch/oc-foundations/ui`.
Node: **24.15.0**. Prepared Python: **3.14.4** at
`C:/Renulus/dev/python/Scripts/python.exe` (used by native UI checks; the initial
renderer tests did not launch it).
All **19 direct dependency pins** match their installed package versions.

| Ignored worktree junction | Existing dependency target |
| --- | --- |
| `apps/desktop/node_modules` | `C:/Renulus/dev/node_modules` |
| `tools/renulus-control/node_modules` | `C:/Renulus/dev/repo/tools/renulus-control/node_modules` |

Vite uses `configLoader: 'runner'`; cache directories are under this lane.
Vitest disables its result cache, file parallelism and extra workers. The
default bundle loader is deliberately avoided because it writes `.vite-temp`
through the shared dependency junction. No dependency installation occurred.

The three initial phases captured SHA-256s for all **298 tracked desktop files** before and
after execution. They were unchanged throughout, and `git diff --exit-code
c2bd896420fb88f76d63ca576414dbbba182f4c2 -- apps/desktop` passed after the run.
The ordered desktop source manifest hash is
`f9cbddb006139775baa38cae8f4c0edf4584e257d2eb4d6545c6614fc734bc67`.
This identifies frontend/native source; concurrent backend work is outside
these renderer-only results and must be pinned again before native launch.

## Compile and test receipts

All paths in this table are relative to the external UI scratch root above.
`evidence-manifest.json` records hashes and sizes for the 14 retained environment,
source, command-driver, log, test and build receipts, and explicitly records
the native launch gate and empty screenshot inventory.

| Phase | UTC interval / result | Receipt and output |
| --- | --- | --- |
| TypeScript `tsc --noEmit` | 19:23:02–19:23:06, exit 0 | `typecheck-01.receipt.json`, `typecheck-01.log` |
| Initial seven affected Vitest files | 19:23:02–19:24:07, exit 1; 136/137 passed | `renderer-tests-01.receipt.json`, `renderer-tests-01.log`, `renderer-tests-01.results.json`, `renderer-tests-01.junit.xml` |
| Authorized Library copy repair | 19:30:49–19:31:09, exit 0; 37/37 passed | `library-copy-02.receipt.json`, `library-copy-02.log`, `library-copy-02.results.json`, `library-copy-02.junit.xml` |
| Vite renderer + esbuild Electron main/preload | 19:23:19–19:23:23, exit 0; 2,019 renderer modules transformed | `build-01.receipt.json`, `build-01.log`, `build-artifacts.json` |
| Environment/source | 19 direct pins matched; desktop unchanged | `dependencies.json`, `dependency-junctions.json`, `frontend-source-before.json`, `git-before.json` |

The exact driver is retained as `validate.mjs`. Its `prepare`, `typecheck`,
`tests` and `build` phases write receipts exclusively, so reuse requires new
receipt names rather than overwriting this first run. The compile phase invokes
the production Vite config and the existing `scripts/build-electron.mjs` from
`apps/desktop`; it does not start a development server or Electron.

| Renderer test file, under `apps/desktop/src/` | Passed / total |
| --- | --- |
| `modules/memory/index.test.tsx` | 25 / 25 |
| `modules/learn/memory-disclosure.test.tsx` | 14 / 14 |
| `modules/learn/lifecycle.test.tsx` | 14 / 14 |
| `modules/chat/chat.test.tsx` | 17 / 17 |
| `modules/chat/api.test.ts` | 2 / 2 |
| `modules/library/LibraryBrowser.test.tsx` | 36 / 37 |
| `modules/reader/Reader.test.tsx` | 28 / 28 |

The failing test is **Deliberate import recovery > requires a new permission
confirmation when the selected file changes and explains unsupported input**.
`apps/desktop/src/modules/library/LibraryBrowser.test.tsx:642` expects
`Choose a PDF, PNG, JPEG, TIFF, text, DOCX, PPTX or XLSX file.`
The actual error from `modules/library/file-formats.ts:27` is
`Choose PDF, PNG, JPEG, TIFF, text, CSV, HTML, XML, DOCX, PPTX or XLSX.`
Both files were unchanged from the committed starting baseline when this red
result was recorded. The original failing output and receipts remain intact.

### Authorized existing-test copy repair

The parent's later integration instruction permits the narrow expectation update above,
accepts the initial failure as red, requires the four behavioral assertions to
remain and keeps native launch gated. The sole test-source edit replaces the
old literal with the current accepted-format message including CSV/HTML/XML.
Permission reset, disabled submit, `aria-invalid` and absence of import requests
remain byte-for-byte unchanged. No new test was needed.

`library-copy-02.diff` records the one-line delta;
`library-copy-02.source-proof.json` compares all 298 desktop files to the first
source manifest and proves this is their only change. It also proves that the
new test text equals the committed baseline with exactly that single literal
replaced. This repairs a stale baseline test expectation, not H24 behavior.

The full Library file passes **37/37**, including the repaired test. The run
records current integration HEAD
`fc69a8e6111fe71f5a72f1535140a9c89c73f5b6`; the test repair was uncommitted, and
its SHA-256 remained
`2465375bcea445e0ef65bee4eeb03fce850d865c1d836037bb16fb0f417426b4`
through execution. The standalone runner is `library-copy-02.mjs` and its
JSON/JUnit/stdout/exit receipt is retained separately from the first run.

All **54 existing build artifact hashes** still match `build-artifacts.json`.
The green production build was reused for this copy-only checkpoint. No broader
affected rerun, full suite, typecheck repeat or rebuild was needed for this
literal-only test repair. The later parent-reported H24 drain-handshake change to
native desktop source independently requires a new typecheck/build after the
explicit stability message, before any app launch.
The follow-up evidence inventory is `evidence-manifest-library-copy-02.json`;
the original `evidence-manifest.json` remains the unchanged initial red record.

`build-artifacts.json` records all **54 generated files**. Key SHA-256s:

| Built artifact | SHA-256 |
| --- | --- |
| `dist/assets/index-D6dJ0qHR.js` | `6df4d0ff54f53206e6928d6c75b81293db0913028508b1609243806e58578301` |
| `dist/index.html` | `5b6ff8c22f756af378768acfd79c6bf08cf6ac511ad066b7beb977983c1ef0a4` |
| `dist-electron/main.cjs` | `c4b3e337fa58ee3e2754ffbf2d485cc74d0421db6a7d339ed36f3a5cc223d615` |
| `dist-electron/preload.cjs` | `153550283d529318273451f085112ca199c339603e9d33506442b18cb36ec2d7` |

## Hidden UI protocol and original launch gate

The original launch gate was superseded by the parent's integration instruction to
proceed on `36777c27` plus the parent ordering edit. The protocol was to record
the then-current backend and native
desktop revisions/working-source hashes, typecheck and rebuild the updated native
source with fresh receipt names, then launch. Do not reuse the pre-handshake
compiled main for this acceptance.

The parent's current `apps/desktop/electron/main.ts:157` shutdown handler was
inspected directly: it awaits `backend.stop()` before closing frontend
connections/server. A rejected stop clears the retry promise and reports that
background work is still settling; the frontend and profile stay owned by the
running instance. The guidance is to try ordinary close again after settlement.
No force-close workaround is part of this acceptance. The observed main source
SHA-256 is `5164d37571774e311bc8b6225d97ae14b658fe085882d1f35e22591761c91596`;
this is a working-source observation, not a declaration that H24 is stable.

For hidden close/restart receipts:

1. Capture the settled working-source manifest, including native desktop,
   backend/runtime and controller source, before and after typecheck/build.
   Record actual file hashes as well as HEAD so uncommitted integration source
   is identified. Recheck the relevant source and compiled artifacts before
   starting and restarting the app; changes require refreshed evidence.
2. Retain the fresh renderer/Electron build manifest. Each controller launch's
   `mainSha256`, including the restart, must match that newly built
   `dist-electron/main.cjs`. Keep the source manifest, build receipt and native
   receipt together so the observed shutdown is tied to these source bytes.
3. Accept close/restart only with `normal: true`, `forcedPids: []` and
   `remainingPids: []`, plus unchanged hidden-window/owned-profile checks.
   Preserve any failed receipt. The current controller has automatic owned
   process cleanup after its 45-second normal-close deadline; such cleanup is
   explicitly a failed close, not evidence of the app's retention behavior.
   Do not intentionally exercise a held-worker timeout through that path.

Use the worktree's current controller, not the registered canonical MCP connection:

```powershell
node C:/Users/karol/.codex/worktrees/opencode-foundations/repo/tools/renulus-control/client.mjs --repo C:/Users/karol/.codex/worktrees/opencode-foundations/repo --python C:/Renulus/dev/python/Scripts/python.exe --state-root C:/Renulus/scratch/oc-foundations/ui --helper-assets C:/Renulus/dev/helper-assets
```

This produces a fresh synthetic profile below `ui/c/s-xxxxxxxx/p` (51
characters, within the Windows limit). `renulus_restart` retains only that
controller session. `renulus_close` must finish before EOF. Public helpers are
verified/staged by the controller; no profile or credentials are borrowed.

Direct checks, driven from fresh snapshots:

1. Memory: add synthetic learning, edit, inspect history, search, normal restart
   and delete. Preserve honest unavailable/cleanup/cancellation states.
2. Library: deliberate synthetic note import, actual ingestion readiness,
   source/revision inspection and an in-app reader.
3. Chat: retain a draft, use an explicit cited passage without automatic Send,
   navigate away/back and restart to check saved draft/source continuity.
4. Capture actual pixels at meaningful states, visually inspect each claimed
   screenshot, inspect `renulus_errors`, and retain normal-close evidence.

No provider call is needed. A successful migrated H02 answer/tool round trip
requires its separately scripted host transport. H01 host/store acceptance and
H24 extraction-thread settlement are not established by renderer tests or
ordinary hidden UI restart. Full-suite connected fixtures currently hardcode
older scratch roots; the parent owns their final-run reconciliation.

## Preliminary native acceptance — run 03

The fresh typecheck and renderer/Electron build both exited **0**. All 19 direct
dependency pins still matched. Source stayed unchanged during both phases.
`accept-build-03.mjs` records tracked and non-ignored untracked desktop, runtime,
controller and packaging/runtime source; `native-source-03.before.json` and the
phase receipts retain each file hash. Vite used runner loading and this lane's
scratch cache. No broader tests or dependency installation were run.

The initial launch source manifest SHA-256 was
`52213233dca74484e65281f784bcc35bb0903391859af0f8931dd59810fe513f`.
The main source remained
`5164d37571774e311bc8b6225d97ae14b658fe085882d1f35e22591761c91596`;
the native backend source remained
`90b597a014ed18984737c223d0e972788de67781ea946976417766dd9f37216c`.
All three launches verified the newly built 39,955-byte main bundle SHA-256
`6c09b21b8dc4d0a5672ce35628f377e400fd4648017b4bfecfa1cfd89de4a2a2`.
All 54 build artifact hashes stayed unchanged through the journey.

Python source changed concurrently. Before the first restart the checkpoint
detected request-drain edits in `runtime/api.py`, `server.py` and `services.py`.
Before the second restart it additionally captured Memory stopping hooks and
the updated producer/dependency shutdown ordering. Those five H24 files were
unchanged across the second restart and final normal close. Concurrent
`harness_process.py` edits are also recorded; this UI journey does not exercise
the H01 host. The final source manifest was
`3176d6d5b203bdf0566edc3881834928f485a050e50a5089152db2032cefb538`.
HEAD advanced to the parent's `ecc3367b7d194ab83bcf56786e7a7dda034f5457`
without any change to that final manifest. Checkpoint nonzero exits explicitly
report drift from the initial build source; they are not compile failures.

| Receipt under `C:/Renulus/scratch/oc-foundations/ui` | Evidence |
| --- | --- |
| `typecheck-03.receipt.json`, `typecheck-03.log` | Fresh `tsc --noEmit`, exit 0 |
| `build-03.receipt.json`, `build-03.log`, `build-artifacts-03.json` | Fresh renderer/Electron output and 54 artifact hashes |
| `before-launch-03.source.json` | Source/artifact parity immediately before first launch |
| `before-restart-03.source.json`, `after-restart-03.source.json` | First restart source checkpoints |
| `before-restart2-03.source.json`, `after-restart2-03.source.json`, `before-close-03.source.json` | Second restart and final close source checkpoints |
| `control-session-03.closed.ndjson` | Frozen full request/result transcript, 141 successful operations |
| `native-lifecycle-03.receipt.json`, `native-lifecycle-03.logs.ndjson` | Frozen controller lifecycle and diagnostic logs |
| `owned-state-03.receipt.json` | Read-only canonical/index consistency evidence after normal close |
| `native-ui-03.summary.json` | Lifecycle timings, source transitions, diagnostics and screenshot hashes |
| `evidence-manifest-native-ui-03.json` | Hash inventory for retained evidence and all 12 PNGs |

The owned profile is
`C:/Renulus/scratch/oc-foundations/ui/c/s-12449bc8/p`.
The controller verified/staged 19 public helper files (483,597,181 bytes), using
contract SHA-256 `3d8ba8f76428f2c7fc0348167dd9b8c70e2f47f29dbd6705e01a6c0fdea97fce`.
Launch readiness took 25.592, 17.388 and 19.224 seconds. Each launch verified
the same profile, a new owned process chain and hidden windows. The recorded
background events are six window creations and three renderer-ready events,
with no show/focus violation and `fault: null`.

| Normal close | UTC start → finish | Seconds | Result |
| --- | --- | --- | --- |
| First restart | 20:03:15.761 → 20:03:16.639 | 0.878 | normal; forced/remaining PID lists empty |
| Second restart | 20:05:17.689 → 20:05:18.742 | 1.053 | normal; forced/remaining PID lists empty |
| Explicit close | 20:08:32.698 → 20:08:35.356 | 2.658 | normal; forced/remaining PID lists empty |

The error inspection retained three renderer-console HTTP 409 messages, one
just after each startup. Home showed its daily-suggestions-unavailable state;
the diagnostic lines do not identify their endpoint. No page-error, route-error,
close-error or controller fault was recorded. This is not a clean-console claim.
The closed synthetic database contains zero assessment test jobs, zero memory
extraction jobs, zero Chat runs and zero messages. No live provider/account was
configured or used.

### Observed behavior and the capture-0009 clarification

Memory saved a synthetic goal, edited it to revision 2, displayed both history
entries and retrieved the edited record by search. The same record/history and
positive recall survived restart. Explicit deletion removed it and its history;
the next search returned zero records. Capture-0009 was taken at that point and
shows `Recall unavailable`, so it proves deletion/search absence only.

That status is consistent with the expected post-delete index invalidation and
asynchronous status refresh. The source's purge path clears the derived index,
marks it dirty and wakes the worker; retrieval rebuilds a non-ready index before
searching. The exact status/error code at capture-0009 was not retained, so the
image alone cannot establish index health or an exact failure cause. After the
next restart, the Memory UI showed zero records and `Ready for recall` before
any new mutation; no startup failure was observed.

A distinct synthetic goal was then saved and **Rebuild
recall index** was clicked explicitly. The actual UI reported **Index rebuilt
from 1 retained record**, **Mem0 OSS · ready** and **Ready for recall**. A fresh
`transplant immunology` search returned that exact record as available for recall.
Captures 0011/0012 establish this separate recovery/search result. This operation
uses the selected managed FastEmbed CPU assets and Mem0 `infer=False` indexing;
it does not need a generative provider. The read-only post-close receipt confirms
one current fact/index entry, ready state and no error code; the earlier deleted
goal and its history remain absent.

Library deliberately imported an original synthetic study note, waited for
`Available`, searched the extracted passage, inspected its citation and opened
the original text in the in-app and Workspace readers. The source retained its
user-owned terms, original-text locator and unverified-currentness statement.
Workspace **Discuss this passage** created an unsent saved Chat draft with one
source reference. Editing the draft, navigating away/back and both restarts
preserved its exact text and reference. **Source 1** reopened the same note after
both restarts. The final database independently confirms zero sent messages/runs,
one saved conversation and the exact retained draft/reference. H02 migration,
live answering and extraction-under-load settlement remain separate acceptance.

### Visually inspected screenshots

All files below are under
`C:/Renulus/scratch/oc-foundations/ui/c/s-12449bc8/out`, are 1384 × 921 pixels,
and were opened with the image viewer for direct inspection. Exact bytes/hashes
are in `native-ui-03.summary.json` and the evidence manifest.

| PNG | Direct visual observation |
| --- | --- |
| `capture-0001.png` | Edited Memory text and both history entries; pending recall state retained honestly |
| `capture-0002.png` | Matching Memory record, history and ready recall |
| `capture-0003.png` | Available Library note with readable source text |
| `capture-0004.png` | Matching passage and citation details, including unverified currentness |
| `capture-0005.png` | Workspace source text and Discuss this passage; Library controls compress while this side panel is open |
| `capture-0006.png` | Saved unsent draft, Source 1 and source reader before restart |
| `capture-0007.png` | Same draft/reference/reader after first restart |
| `capture-0008.png` | Retained Memory revision/history and ready recall after first restart |
| `capture-0009.png` | Empty post-delete search with unavailable recall status; not healthy-recall evidence |
| `capture-0010.png` | Same unsent draft/reference/reader after second restart |
| `capture-0011.png` | Explicit rebuild success from one record, Mem0 OSS ready |
| `capture-0012.png` | Positive search after explicit rebuild, one result and ready recall |

The parent's later instruction required a fresh rebuild/restart/close once
the H24 P1 fixes settled. Run 04 below completed that follow-up. The evidence
above remains a dated preliminary record and has not been overwritten.

### Small-window and zoom protocol — completed in run 04

The parent follow-up called for the planned 1000 × 720 and 200% zoom checks
in the settled-source run. Both operations are supported by this worktree's
scoped controller. They were completed after the callback-identity stability
signal, in run 04 below; the 12 preliminary screenshots above do not cover them.

After the stability signal and fresh typecheck/build, use the existing owned
synthetic profile for Memory, the unsent cited Chat draft and Library/reader.
Send these requests as separate lines to the connected client:

```json
{"name":"renulus_resize","arguments":{"width":1000,"height":720}}
{"name":"renulus_zoom","arguments":{"percent":100}}
{"name":"renulus_snapshot","arguments":{}}
{"name":"renulus_screenshot","arguments":{}}
{"name":"renulus_zoom","arguments":{"percent":200}}
{"name":"renulus_snapshot","arguments":{}}
{"name":"renulus_screenshot","arguments":{}}
```

The resize request sets **outer-window** dimensions in device-independent pixels;
record the actual returned outer/content dimensions rather than label it a
1000 × 720 content viewport. Zoom is the owned renderer's verified zoom factor,
not an OS DPI change. Capture and visually inspect each relevant route at 100%
and 200%, including the source panel. Check scrolling and keyboard reachability
through the controller's allowed renderer actions. Record any unavailable action,
native clamping, clipped controls or overflow exactly as observed; a successful
resize/zoom response alone does not establish usable layout. Restore 100% and
the previously recorded outer dimensions before final lifecycle checks. Keep
the new source, lifecycle and screenshot receipts separate from run 03.

## Settled H24 UI and small-window acceptance — run 04

The parent declared H24 `29d147869056c14b80b1cdfe0026e0b705454990` stable
with its native shutdown ordering edit. Fresh `tsc --noEmit` passed at
20:19:27.926–20:19:29.915 UTC; renderer and Electron builds passed at
20:19:30.348–20:19:34.495 UTC. All 19 dependency pins matched. Both phases
had no source changes. The exact runner is `accept-build-04.mjs`.

The ordered 505-record source manifest SHA-256 was
`387d72b5e8dee17a08ad7c729451963f41a4f4967881d502988d63cc212da0be`.
The 54-artifact manifest retained the 39,955-byte main bundle SHA-256
`6c09b21b8dc4d0a5672ce35628f377e400fd4648017b4bfecfa1cfd89de4a2a2`.
Native `main.ts` and `backend.ts` retained the source hashes recorded above.
The Memory service hash was
`3beff5fd3410ba52aa3f9cb9cbe342a05f78a3c7601e5f5b752d2bab3602074d`;
`services.py` was
`5affadd4d64cb3da25358bcd6f8c50ce0317ffa5346937474c6ef2adb642abbb`.

Every checkpoint before/after launch, restart and close recorded **zero source
or artifact changes**. HEAD advanced to
`9a10562afc1e0bf648667995e6ca59d4fc546f58` when the parent committed the
existing Library test repair; this changed no bytes in the captured manifest.
The byte-stable evidence includes both the final H24 provider-identity fix and
the native backend-before-frontend close ordering.

The run made **105 tool requests: 104 successful, one schema rejection**.
The rejected wait used the unsupported `region` locator role; a supported
`Opening source` status wait succeeded and the loaded reader was inspected.
The failed request remains in the transcript. Two launches took 17.423 and
21.462 seconds, used the same owned synthetic profile and matched the fresh
main bundle hash. Both remained hidden, with no controller fault.

| Normal close | UTC start → finish | Seconds | Result |
| --- | --- | --- | --- |
| Restart | 20:25:44.984 → 20:25:45.975 | 0.991 | normal; forced/remaining PID lists empty |
| Explicit close | 20:27:43.692 → 20:27:44.485 | 0.793 | normal; forced/remaining PID lists empty |

Two startup HTTP 409 renderer-console lines were retained, at 20:20:03.375
and 20:26:09.213 UTC. Their endpoints were not identified in the diagnostic
messages. No page-error, route-error or close-error was recorded. This does not
claim a clean console.

Memory returned the retained post-rebuild goal and showed ready recall before
and after restart. Library returned the synthetic transplantation passage,
opened its original and retained citation/terms/currentness information. The
unsent cited Chat draft survived restart, and Source 1 reopened its original.
No external discovery request was made. The read-only post-close check passed
all 11 assertions: exact draft/reference retained, zero messages or Chat runs,
the deleted Memory goal/history absent, one current ready index entry, and the
synthetic Library source available. These are regression checks of existing
flows; they do not establish H02 migration or a live generated answer.

### Actual small-window and zoom observations

The controller set **1000 × 720 outer DIP dimensions**, returning
**984 × 681 content pixels**. It verified both 100% and 200% renderer zoom.
At 200%, content needed vertical scrolling. A Tab sequence from Memory search
reached Search, Clear search and Edit; the record and focused Edit control were
visible. The recall panel was also reached and showed ready state. In Chat,
Tab reached Source 1 and Enter opened its reader. The Library reader's PageDown
showed the complete original paragraph and highlighted the searched term.

The captures do show vertical clipping: lower Chat composer controls and the
reader's Discuss action lie partly below some 200% views; More/Settings are
outside the visible navigation area in some states. The reader has substantial
blank space in one scrolled Chat view. The lane did not measure DOM overflow
geometry or prove keyboard access to every control. This is bounded visual and
keyboard evidence, **not a full accessibility or no-overflow pass**. At 100%,
the small-window citation reader showed its original and Discuss action.
The run restored 100% zoom and 1400 × 960 outer dimensions (1384 × 921 content)
before its final restart and close.

### Run 04 receipt inventory

All names below are relative to `C:/Renulus/scratch/oc-foundations/ui`.

| Exact receipt paths | Evidence |
| --- | --- |
| `accept-build-04.mjs`, `native-source-04.before.json`, `dependencies-04.json` | Reproducible runner, initial source and matched dependencies |
| `typecheck-04.receipt.json`, `typecheck-04.log` | TypeScript exit 0; no source drift |
| `build-04.receipt.json`, `build-04.log`, `build-artifacts-04.json` | Fresh production outputs, exit 0, all 54 hashes |
| `before-launch-04.source.json`, `after-launch-04.source.json` | Launch byte parity |
| `before-restart-04.source.json`, `after-restart-04.source.json` | Restart byte parity |
| `before-close-04.source.json`, `after-close-04.source.json` | Final close byte parity |
| `control-session-04.closed.ndjson` | Frozen run 04 request/result delta after run 03 |
| `native-lifecycle-04.receipt.json`, `native-lifecycle-04.logs.ndjson` | Lifecycle and diagnostics, cumulative through five launches/closes |
| `observe-owned-state-04.py`, `owned-state-04.receipt.json` | Read-only canonical/index check after close |
| `summarize-ui-04.mjs`, `native-ui-04.summary.json` | Exact lifecycle/source transitions and screenshot hashes |
| `evidence-manifest-native-ui-04.json` | Immutable evidence inventory and 26 PNG hashes |

All 26 screenshots below were opened for direct visual inspection. They are in
the same owned `c/s-12449bc8/out` directory. Captures 0013–0035 are 984 × 681;
0036–0038 are 1384 × 921. The summary and manifest retain individual sizes and
SHA-256s, including identical pixels across repeated stable views.

| PNG | Direct visual observation |
| --- | --- |
| `capture-0013.png` | 100% Memory positive search after the preceding searching snapshot |
| `capture-0014.png` | 100% Memory positive search after the explicit matching-result wait |
| `capture-0015.png` | 200% Memory heading/search; lower content requires scrolling |
| `capture-0016.png` | 200% matching Memory record, Edit reached and focused by Tab |
| `capture-0017.png` | 200% Memory recall panel, Ready for recall |
| `capture-0018.png` | 100% unsent Chat draft and Source 1, empty conversation |
| `capture-0019.png` | 200% Chat composer, lower controls below the initial viewport |
| `capture-0020.png` | 200% Source 1 reached by Tab |
| `capture-0021.png` | 200% citation reader loading skeleton; not loaded-reader evidence |
| `capture-0022.png` | 200% loaded citation text, lower Discuss action partly clipped |
| `capture-0023.png` | 200% citation after find-field focus/PageDown; vertical clipping and blank lower area |
| `capture-0024.png` | 100% citation original and Discuss action visible |
| `capture-0025.png` | 100% Library search/top state; external request count zero |
| `capture-0026.png` | 100% Library source inspector stacked below list |
| `capture-0027.png` | 100% Library source/citation inspection after wait |
| `capture-0028.png` | 200% Add to library reached by Tab |
| `capture-0029.png` | 200% Library Search reached by Tab |
| `capture-0030.png` | 200% reader heading; original text below the visible area |
| `capture-0031.png` | 200% reader after load wait; original text still below the visible area |
| `capture-0032.png` | 200% reader find field filled with transplantation |
| `capture-0033.png` | 200% reader PageDown reveals complete original paragraph and match highlight |
| `capture-0034.png` | 200% citation terms and unverified currentness |
| `capture-0035.png` | 100% restored Library citation details |
| `capture-0036.png` | Standard window, same unsent cited Chat draft after restart |
| `capture-0037.png` | Standard window, Source 1 reopens original after restart |
| `capture-0038.png` | Standard window, positive Memory query and ready recall after restart |

## Notes refresh integration delta — run 05

After the parent declared its Notes refresh fix stable, this lane rebuilt from
`ced998e61001b591e802ad174b98e35c3fc07875`. The parent reported the held-refresh
regression red then green, seven component tests plus the actual HTTP/SQLite
Notes journey passing, and six Updates tests passing after a stale expectation
repair. Those parent test results are distinct from this lane's native check.

Fresh TypeScript passed at 20:35:27.239–20:35:30.105 UTC; Vite and Electron
builds passed at 20:35:30.985–20:35:33.883 UTC. The 505-record source manifest
SHA-256 was
`d944751fbca83ce8b329a725659b1d6bf377cb1443f8583a6c8d2287dca6b479`.
Only four files differed from run 04: `NotesPanel.tsx`, `NotesPanel.test.tsx`,
`notes.connected.test.tsx` and `updates/AcquiredVersions.test.tsx`.
NotesPanel's source SHA-256 was
`de988668309b22542463edc3c28d9136de45ab36bbfc3113a7b958ca8ad5b876`.
The new `dist/assets/index-Bs93aILz.js` SHA-256 was
`9233cb3cc0f065e68abb7127e8862305a440a0ef7d422c07efbdaef3ed0ea51a`.
The Electron main and all H24 runtime source still matched run 04 at build and
before/after launch. No completed Memory/Library/Chat journey was repeated.

The hidden app used the existing owned profile. Startup took 24.152 seconds.
All **46 controller requests succeeded**. From the existing Chat workspace,
Notes saved **Synthetic Notes refresh validation** with revision 1:
`Synthetic study note: compare dialysis access and transplant immunology.`
After actual refresh, Revision history opened. A second save changed the text
to `Synthetic revised study note: compare dialysis access, transplant immunology
and glomerular disease.` History listed revisions 2 and 1; opening revision 1
displayed its original text. This native run did not inject a held refresh;
the parent's deterministic test covers that timing case.

With revision 1 still open, **Delete note → Delete all revisions** displayed
the successful deletion notice and reset to an empty new-note editor. However,
the old revision buttons and historical original text remained visible in the
mounted panel. Closing and reopening Workspace → Workspace tools → Notes
cleared them. The source success branch at `NotesPanel.tsx:80` resets the
selection/deletion state but does not clear `history` and `historical`, which
is consistent with the observed result. **Immediate UI deletion cleanup fails**;
the parent owns any production repair. Captures 0043/0044 record the failure and
0045 records the remount recovery.

Normal close ran from 20:40:02.661 to 20:40:03.940 UTC (**1.279 seconds**),
with `normal: true`, empty forced/remaining PID lists and no controller fault.
A single startup HTTP 409 console message was retained; no page/route/close
error was recorded. The read-only closed-profile check confirms both synthetic
revisions deleted, the document tombstoned, originals absent, the deletion
ledger present, zero note passages and no pending cleanup. The saved Chat
draft/reference remained intact, with zero messages and zero runs.

The original `owned-state-05.receipt.json` is preserved with a false comparison
of the complete derived Memory index identity. Its generation changed across
launches; epoch, model fingerprint, ready state and null error code did not.
`owned-state-05.review.json` separately records the current canonical entry
and all nine semantic checks passing. It does not rewrite the initial false
comparison or resolve the visible Notes history issue.

All source/artifact checkpoints through **before-close-05** matched the build.
The **after-close-05** checkpoint detected only
`runtime/renulus/memory/service.py`, whose completed-close-task fast path was
being added concurrently. Its source manifest became
`89b21c99207f21ff73392e91ab20b88ee58397abc9dfbbe6d973300377efffcf`;
all 54 build artifacts stayed identical. The close is scoped to the source
captured before it; run 05 does not accept that later Python delta. The parent
subsequently confirmed `f6bdb589` stable and directed a narrow lifecycle
follow-up. It then began repairing the Notes deletion display finding and
explicitly held the next UI launch until that repair is stable. The app remains
closed until the Notes signal. Run 06 below completes that later check while
preserving the failing run 05 evidence.

### Run 05 receipt and screenshot inventory

All paths below are relative to `C:/Renulus/scratch/oc-foundations/ui`.

| Exact receipt paths | Evidence |
| --- | --- |
| `accept-build-05.mjs`, `native-source-05.before.json`, `dependencies-05.json` | Current Notes source and matched dependency capture |
| `typecheck-05.receipt.json`, `typecheck-05.log` | TypeScript exit 0; source unchanged during check |
| `build-05.receipt.json`, `build-05.log`, `build-artifacts-05.json` | Fresh production build exit 0, 54 hashes |
| `before-launch-05.source.json`, `after-launch-05.source.json`, `before-close-05.source.json` | Exact build-source and artifact parity |
| `after-close-05.source.json` | Later Memory service delta, unchanged build artifacts |
| `control-session-05.closed.ndjson` | Frozen 46-request native Notes delta after run 04 |
| `native-lifecycle-05.receipt.json`, `native-lifecycle-05.logs.ndjson` | Cumulative six launches/closes and retained diagnostics |
| `observe-owned-state-05.py`, `owned-state-05.receipt.json` | Original read-only deletion receipt, including the false index-identity comparison |
| `review-owned-state-05.py`, `owned-state-05.review.json` | Separate semantic index/canonical check; Notes UI finding stays open |
| `summarize-ui-05.mjs`, `native-ui-05.summary.json` | Notes result, source drift and seven screenshot hashes |
| `evidence-manifest-native-ui-05.json` | Frozen run 05 evidence inventory |

All seven PNGs are 1384 × 921 pixels in the same owned output directory and
were directly visually inspected. Exact hashes are retained in the manifest.

| PNG | Direct visual observation |
| --- | --- |
| `capture-0039.png` | Revision 1 saved; history opens after refresh, lower revision controls below the capture |
| `capture-0040.png` | Revision 2 saved, revisions 2/1 listed, revision 1 historical view opened |
| `capture-0041.png` | Scrolled historical revision 1 original text |
| `capture-0042.png` | Deletion confirmation requested with historical revision still open; lower controls partly below frame |
| `capture-0043.png` | After deletion: empty new-note editor but stale revision buttons and original text remain |
| `capture-0044.png` | Same state scrolled upward: deletion success notice and empty title/editor; snapshot retains history below |
| `capture-0045.png` | Reopened Notes panel: empty editor, no saved-note selector or revision history |

## Notes deletion repair and final H24 lifecycle — run 06

The parent reproduced run 05's display failure in `notes-delete-red.xml`, then
committed `b6a4a7da6a6cb5c867aaa48e3af2c9dacdde5f7b`
(`fix(notes): clear open history after acknowledged deletion`). It reported
eight component tests plus one actual HTTP/SQLite case passing in
`notes-delete-green.xml`. The minimal source change clears `history`,
`historical` and `latest` only after a successful DELETE acknowledgement. These
are parent-owned behavioral test results; this lane supplies the fresh native
verification below.

After the parent's stability signal, `accept-build-06.mjs` captured the source,
checked all 19 direct dependency pins, ran fresh TypeScript, and rebuilt both
the renderer and native Electron entries using the matched dependencies and
scratch cache. No package installation or broader test rerun was needed.

| Phase | UTC interval | Result |
| --- | --- | --- |
| `tsc --noEmit` | 20:47:52.228 → 20:47:54.227 | exit 0; source unchanged |
| Vite renderer + Electron entries | 20:47:54.738 → 20:47:57.194 | exit 0; 2,019 renderer modules; source unchanged |
| Hidden reopen with fresh backend | started 20:48:06; readiness 39.618 seconds | same owned synthetic profile; hidden; built main hash matched |
| Normal close | 20:51:51.933 → 20:51:53.059 | 1.126 seconds; normal; forced/remaining PID lists empty |

### Exact final source bytes

The ordered 505-record source manifest SHA-256 was
`2afa2ccc0069fac0e7e42bd2a3fb9b0269bbb30dd4343237c1b737022791b92c`.
All 54 build artifact hashes matched before/after launch and before/after close.
Build and pre-launch HEAD were `b6a4a7da`; during startup the parent committed
assessment fixture changes as
`e57e4d89bcc2c42b9a65693fcf93b6e835fb6017`. That became the post-launch and
final-close HEAD, with **no change to any captured source or build artifact**.

Compared with run 05, only `NotesPanel.tsx`, `NotesPanel.test.tsx`,
`notes.connected.test.tsx` and `runtime/renulus/memory/service.py` changed in
the source manifest. The latter includes H24's already-completed task check
before `asyncio.wait`. Native `main.ts` and `backend.ts` retained the earlier
recorded hashes and shutdown ordering.

| Source/artifact | SHA-256 |
| --- | --- |
| `apps/desktop/src/modules/notes/NotesPanel.tsx` | `03f928225798432c5fd121c0e975b76caa22271d8fe34bab51f35122e7d5a55a` |
| `runtime/renulus/memory/service.py` | `3f699f7608967489ee9318c9f771ac17d9b2d4fb4059f7d7553f6dfca59489f6` |
| `apps/desktop/dist/assets/index-CS6-0wC6.js` | `253dd05a83b12fb14d2166baa93242b803372ca283050c0127b8626d1bd4d388` |
| `apps/desktop/dist-electron/main.cjs` | `6c09b21b8dc4d0a5672ce35628f377e400fd4648017b4bfecfa1cfd89de4a2a2` |

The controller received `renulus_restart` while its app was already closed,
reusing only its retained synthetic profile and launching a fresh owned process
chain: launcher 45440, main 39024, backend 2372. It did not add an artificial
close receipt for the already-closed state. Run 06 adds one actual launch and
one actual normal close; cumulative totals are seven of each. The two new
window-created and one renderer-ready events were hidden, with `fault: null`.

### Native Notes result and preserved timing error

The lane opened Notes from the existing saved Chat workspace and created
**Synthetic final Notes deletion validation**. Revision 1 contained
`Synthetic final study note: compare peritoneal dialysis and renal transplantation.`
Revision 2 contained `Synthetic final revised study note: compare peritoneal
dialysis, renal transplantation and glomerular disease.` The actual UI displayed
both saved revisions and independently opened revision 1's original text.

With history still open, **Delete note → Delete all revisions** succeeded.
Explicit waits confirmed that both the Saved revisions heading and historical
revision heading disappeared. Three subsequent snapshots retained the deletion
success notice and empty title/body, with no revision buttons, historical body
or article. The first snapshot still contained the old Open note option while
the list refresh was finishing; it was absent in the later snapshots. No close/
reopen, route change, New note click or restart occurred between deletion and
these observations. Home/PageUp only scrolled the still-mounted panel. The
same-state screenshots show the empty editor and, at the top, the success notice.
**The run 05 stale-history finding is resolved for these bytes.**

There were **51 controller requests: 50 successful and one timing rejection**.
An initial history click was sent before the first save response and matched
zero controls. The following snapshot still showed saving. This request and
error remain in the transcript. A subsequent explicit wait for Revision history
then succeeded, and the saved history, edit and deletion checks passed. This is
an operator synchronization error, not a clean-tool-run claim or a new product
failure. The first screenshot already shows the later successful save.

The closed-profile read-only receipt passed all eight checks: exact two saved
revision body hashes/ordinals, one tombstoned note, both revisions deleted with
metadata cleared, deletion ledger present, originals absent, no passages or
pending cleanup, retained Chat draft/reference unchanged, and zero sent messages
or Chat runs. No Memory/index or Library journey was repeated. The original
run 05 false index-identity comparison and its separate semantic review remain
unchanged, as do the stale-history screenshots.

Diagnostics retained one startup renderer-console HTTP 409 at 20:48:48.433 UTC
and the early history locator error. No page-error, route-error, close-error or
controller fault was recorded. The UI lifecycle establishes normal shutdown on
these bytes; the parent's service tests separately cover calling a completed
Memory close task from a later event loop. No held-worker timeout was injected.
Default launch, installation, native dialogs, live generation and broader
accessibility acceptance remain outside this lane's evidence.

### Run 06 receipt and screenshot inventory

All paths below are relative to `C:/Renulus/scratch/oc-foundations/ui`.

| Exact receipt paths | Evidence |
| --- | --- |
| `accept-build-06.mjs`, `native-source-06.before.json`, `dependencies-06.json` | Exact runner, source and matched dependency capture |
| `typecheck-06.receipt.json`, `typecheck-06.log` | Fresh TypeScript exit 0, no source drift |
| `build-06.receipt.json`, `build-06.log`, `build-artifacts-06.json` | Fresh production build, source and all 54 artifact hashes |
| `before-launch-06.source.json`, `after-launch-06.source.json` | Byte parity across the fresh hidden backend launch |
| `before-close-06.source.json`, `after-close-06.source.json` | Final source/artifact parity through normal close |
| `control-session-06.closed.ndjson` | Frozen 51-request run 06 delta; original rejected request retained |
| `native-lifecycle-06.receipt.json`, `native-lifecycle-06.logs.ndjson` | Cumulative seven launches/closes and diagnostics |
| `observe-owned-state-06.py`, `owned-state-06.receipt.json` | Eight read-only canonical checks, all passed |
| `summarize-ui-06.mjs`, `native-ui-06.summary.json` | Verified absence of stale content without remount; source/lifecycle/screenshot evidence |
| `evidence-manifest-native-ui-06.json` | Frozen run 06 inventory, including all seven PNG hashes |

All seven PNGs are 1384 × 921 pixels in the same owned output directory and
were opened for direct visual inspection. No small-window/zoom repeat was made.

| PNG | Direct visual observation |
| --- | --- |
| `capture-0046.png` | First save completed by capture time: Saved · Revision 1 notice and original body; preceding snapshot was still saving |
| `capture-0047.png` | Revision history opened after explicit wait; original body, Revision 1 saved status and Saved revisions heading at bottom |
| `capture-0048.png` | Revision 2 saved; both revision buttons and historical revision 1 heading; original below the viewport |
| `capture-0049.png` | Before delete, scrolled view of revisions 2/1 and complete historical revision 1 body |
| `capture-0050.png` | After acknowledged delete in the same panel: empty title/body, Not saved yet, disabled save, no stale history below |
| `capture-0051.png` | Same empty Notes state after Home in the title field; history remains absent |
| `capture-0052.png` | PageUp shows the actual deletion success notice and empty editor; no remount or New note click |

## Final Services shutdown lifecycle delta — run 07

2026-10-10 UTC. The parent committed
`756c8ebc622eef85b39dd8fbff1abbba264df2b9`
(`fix(runtime): replay settled shutdown after loop teardown`).
`Services.shutdown` now calls `asyncio.wait` only while its shutdown task is
unfinished, retaining the existing failed/completed observation and admission
state. The parent reported its public regression and all **34 shutdown, Memory
and privacy tests passed**. This lane performed only a final actual native
lifecycle on those bytes; the ordinary launch/close does **not** isolate replay
of a completed task from a new event loop.

The fresh typecheck/build used the same matched 19 dependency pins, Vite runner
configuration and external scratch cache. Relative to run 06, the 505-record
source manifest changed **only `runtime/renulus/services.py`**. Every one of the
54 newly built renderer/Electron artifacts was byte-for-byte identical to run
06, including Notes. No existing Memory/Library/Notes journey, renderer suite
or zoom check was repeated.

| Phase | UTC interval / result |
| --- | --- |
| Fresh TypeScript | 21:20:07.342 → 21:20:09.340; exit 0, no source drift |
| Fresh renderer/Electron build | 21:20:09.791 → 21:20:12.958; exit 0, 2,019 renderer modules, no source drift |
| Hidden native launch | owned process creation from 21:21:22; ready in 19.326 seconds |
| Normal close | 21:22:31.770 → 21:22:32.510; **0.740 seconds**, `normal: true`, `forcedPids: []`, `remainingPids: []` |

### Controller-session recovery and evidence boundary

The attempt to write to the prior exec session 1335 failed with **Unknown
process id 1335**. Inspection found no former controller process 31492 and no
prior main/backend processes. The scoped controller's documented contract has
no existing-profile import/resume option: a new server always creates a fresh
owned synthetic profile. The lane used that supported fresh-session path
instead of changing controller source or copying the old profile. This deviation
is recorded in `controller-recovery-07.json`; it is separate from the eight
successful MCP operations in the new session.

The new profile is
`C:/Renulus/scratch/oc-foundations/ui/c/s-27c2d344/p`.
The earlier `c/s-12449bc8/p` profile was not reused or modified by this delta.
The same fixed worktree/Python/helper-assets configuration verified and staged
the 19 public CPU helper files. The new owned process chain was launcher
49036, main 38728 and managed Python backend 13256. Two window-created events
and one renderer-ready event were verified hidden; `fault` stayed null.
Run 07's receipt contains one launch/close. The seven earlier normal closes
remain in the separate run 06 receipt, rather than being presented as one
continuous controller session.

### Exact bytes and route observation

Build and pre-launch HEAD were `756c8ebc`. During launch, the parent committed
the test-only Today fixture adjustment as
`262e7e3e759a03a1d5022a1c27a89e33c1ddb270`; that was also final-close HEAD.
All five source checkpoints, including the additional checkpoint before the
replacement controller session, matched the build exactly. The ordered source
manifest stayed
`c52905284dc170acac2f707c82067d55107eba3e01e41e1da4143f95642c5ece`.

| Source/artifact | SHA-256 |
| --- | --- |
| `runtime/renulus/services.py` | `83cff6865a979a8313c3b47bcbbabe325c6cdf29507a01afb82cb727d6ab4fbe` |
| Ordered 505 source records | `c52905284dc170acac2f707c82067d55107eba3e01e41e1da4143f95642c5ece` |
| Built `dist-electron/main.cjs` | `6c09b21b8dc4d0a5672ce35628f377e400fd4648017b4bfecfa1cfd89de4a2a2` |

The eight requests were start, snapshot, click **New chat**, wait for its empty
composer, snapshot, screenshot, errors and normal close. The snapshots showed
the ordinary New chat route with empty composer and disabled Send. The single
1384 × 921 PNG was opened for direct visual inspection. It shows normal
navigation, the empty composer, disabled Send and the daily-suggestions-
unavailable message. No message was entered or sent.

Two renderer-console HTTP 409 lines were retained, at 21:21:41.847 and
21:22:19.457 UTC; their log lines do not identify endpoints. No page-error,
route-error, operation-error, close-error or controller fault occurred in the
new controller session. This is not a clean-console claim. Run 06's single
readiness locator rejection, run 05's failed immediate history cleanup and
false index-identity comparison, and run 03's recall/startup qualifications
remain unchanged in their original receipts and report sections.

### Run 07 receipt and screenshot inventory

All names below are relative to `C:/Renulus/scratch/oc-foundations/ui`.

| Exact receipt paths | Evidence |
| --- | --- |
| `accept-build-07.mjs`, `native-source-07.before.json`, `dependencies-07.json` | Exact source, runner and matched dependencies |
| `typecheck-07.receipt.json`, `typecheck-07.log` | Fresh TypeScript exit 0 |
| `build-07.receipt.json`, `build-07.log`, `build-artifacts-07.json` | Fresh build exit 0, all 54 artifacts identical to run 06 |
| `before-launch-07.source.json`, `before-new-session-07.source.json`, `after-launch-07.source.json` | Source/artifact parity before the failed resume attempt and across the fresh launch |
| `before-close-07.source.json`, `after-close-07.source.json` | Final source/artifact parity through ordinary close |
| `control-session-07.mjs`, `controller-recovery-07.json` | Fixed configuration wrapper and honest fresh-profile recovery record |
| `control-session-07.closed.ndjson` | Frozen eight-request transcript for the new session |
| `native-lifecycle-07.receipt.json`, `native-lifecycle-07.logs.ndjson` | One actual hidden launch/normal close, empty forced/remaining lists, diagnostics |
| `summarize-ui-07.mjs`, `native-ui-07.summary.json` | Checked source delta, artifact equality, normal-close timings and scope limits |
| `evidence-manifest-native-ui-07.json` | Frozen run 07 evidence hashes |
| `c/s-27c2d344/out/capture-0001.png` | Visually inspected New chat route at 1384 × 921; screenshot numbering restarts in the new session |
