# Design C reconciliation — DC01

October 10, 2026 · Pass 1 design review complete; visual contract ready for shell/workspace implementation. This is the DC01 design prerequisite, not connected feature or release acceptance.

## Scope and prerequisite

Assigned worktree `C:/Renulus/dev/worktrees/dc01-design`, branch `codex/dc01-design`. Starting baseline `1b30a89687cfcc5fb13b1cf824bbc43c19f870ed` contains `528025ff`. After the parent's shared Git/root repair, normal `rev-parse --show-toplevel` returned this exact worktree path, with clean content/status, before any mutation. The authorised `1ca45ff2` baseline was merged by fast-forward for this handoff. No reset, checkout, unowned normalisation staging or push was used.

Only this report and the existing editable [C page](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=2-250) were edited by DC01. Editable access, node inspection, composition/text changes, component overrides and screenshot exports succeeded. The static comparison, other pages and global component/token definitions were preserved. No application source, spec, PRODUCT, DESIGN, manifests or owner state was authored by this lane; shared baseline files came from the authorised fast-forward.

The current AGENTS, README, PRODUCT, DESIGN, PROJECT_BRIEF, WORKSPACE, DECISIONS, C spec, architecture, parallel-work and APP_CONTROL instructions were read. Figma design-to-code was loaded before design-context calls; figma-use before Plugin API calls. Figma generate-design, Impeccable, Interface Design and Interface Design Review informed composition and review. Home and chat/reader were inspected through design context plus pixels. Remaining screens used bounded node/text/action queries and representative screenshots rather than repeated full-page metadata.

## Corrections saved on the editable C page

| Correction | Final reference / evidence |
| --- | --- |
| Ordinary Case discussion saves by default. Subtitle is “Saved conversation”; banner is “Case discussion · Synthetic example”; body says “This conversation and its attachments save automatically. Add it to a project when useful.” Add to project and Archive chat are distinct actions. | [C05 saved Case](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=4-4855) → [project](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=4-4609) / [archive](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=119-11294) |
| Goals no longer describes temporary conversations or explicit Save as the ordinary default. | [C09](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=5-2969): “Bring a question from your day into a saved conversation.” / “Conversations save by default.” |
| Temporary labels and Save conversation / Discard temporary appear only in the explicit temporary reference. | [Temporary conversation](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=122-12225) |
| 31 original open side panels widened from 360 to 480 px, including readers, workspace, neutral assessment panes and import review. Main content uses flexible auto-layout; attachment area flexes and source links wrap. | [C12 chat + reader](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=25-2863); exact node list in audit receipt |
| Added resize, collapsed split, focused chat/reader and 200% effective-viewport compositions. | Geometry references below |
| Removed residual “Your learning space” headings in both More views, hiding their heading wrappers. | Text nodes `25:5000`, `32:4987`; [More](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=25-4860) / [More overlay](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=32-4985) |
| Removed illustrative goals completion. “No progress recorded” and three “Not started” statuses replace “This week · 2 of 3 completed”. | [C15 workspace Goals](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=25-3701) |
| C24/C25 identify generic PDF readers. Revision outline remains an example PDF title, not a new generated-outline feature. C24 metadata says “PDF · Example document · Project file”. | [C24 PDF beside chat](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=29-4500) / [C25 Library PDF](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=29-4724) |
| Zero-commit partial Study uses em dashes in aggregate fields, removing inherited fixture-count bindings. | [Partial Study](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=90-10541): “Outcomes include submitted answers only. Pending choices are saved for resume.” |
| Import review avoids extraction/key certainty before candidate review; generation-ready copy separates format/duplicate validation from unreviewed keys. | [Import review](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=83-7406) / [Generation ready](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=82-6711) |
| More exposes Today/study plan, teaching cases and archives alongside existing memory/preferences/connections/settings. Ordinary C navigation footers route to Settings. Original Test reactions were retained. | [More](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=25-4860) / [More overlay](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=32-4985) / [Settings](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=119-17244) |

Retained example names, suggestions, source titles, counts, timer values and the synthetic 70% result are demonstration data. Production reads canonical records and committed outcomes; these values must not seed real progress, source evidence, defaults or model responses. The chosen-name Home example does not require the sample name. First run supplies an absent-name/disconnected state. Existing C01 already satisfies the Auto / introductory filler / learning-space row / Ask a follow-up removals; the final audit found no visible stale copies.

## Reconciled shell and workspace geometry

These are reviewed engineering candidates, not additional confirmed user decisions. Widths are effective CSS/layout pixels; the separator belongs to the workspace allocation.

| Viewport | Navigation | Conversation/content | Workspace | Reference |
| --- | ---: | ---: | ---: | --- |
| 1440×900 default | 272 | 688 | 480 | [C12](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=25-2863) |
| 1440×900 resize example | 272 | 528 | 640 | [Resize](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=123-12895) |
| 1000×720 | 72 | 528 | 400 | [Collapsed split](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=123-13205) |
| 640×540 | 72 | 568 | One focused pane | [Chat](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=123-13577) / [reader](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=123-13946) |
| 200% of 1440×900 → 720×450 effective | 72 | 648 | One focused pane | [Chat](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=123-14285) / [reader](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=123-14654) |

Recommended implementation algorithm:

1. Start with a preferred workspace width of 480 px. Candidate workspace bounds are 360–640 px and minimum conversation width is 528 px. Retain the preference independently of temporary clamping.
2. Collapse 272 px navigation to a 72 px rail below approximately 1280 effective px when a workspace is open. This preserves the preferred split while width permits. Explicit expansion uses the same fit rule.
3. If two panes fit, clamp the preferred width to `[360, min(640, availableWidth - navigationWidth - 528)]`. The parent owns persistence and shell implementation.
4. With the rail, two panes require `72 + 528 + 360 = 960` effective px. Below that use one focused chat or reader pane with an explicit return. Expanded navigation also uses the fit calculation; do not squeeze chat below its minimum.
5. Scroll navigation, conversation and reader independently; pin the composer and reader actions. Preserve draft, messages, running-response identity, reader position and selected tab through composition changes. Resize does not change content identity.

The focused reader names the document in its header and exposes “Back to chat”. Duplicate title/metadata is hidden in compact compositions. At 720×450 it uses a 56 px header, 44 px tab row and one horizontal row of 44 px primary actions. Reader content scrolls beneath them; screenshot clipping is the scroll viewport, not discarded content. The 1000 px conversation likewise scrolls above its pinned composer.

C12 and the resize reference show an 8 px splitter hit area with a 2 px teal focused separator. Its prototype click navigates to the resize example. This is composition evidence; real drag, keyboard resize, focus return and preference persistence belong to DC03/DC07. Preserve DESIGN's 44 px primary/navigation interaction targets in code where inherited C controls are drawn at 40 px. Collapsed icons require accessible names, tooltips and visible keyboard focus.

The 200% frames model an effective viewport. Physical Windows/Electron zoom, keyboard, screen-reader, high-contrast and reduced-motion acceptance remain with the integrated implementation/DC20.

## Reviewed representative screen checklist

| Family | Final references | Owning tickets / interpretation |
| --- | --- | --- |
| Home, ordinary conversation, daily Case | [Home](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=4-3926), [conversation](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=4-4134), [saved Case](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=4-4855) | DC03/DC04/DC06; saved default, chosen-name/absent-name and offline states |
| Suggestions | [Explain](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=67-4874), [Case](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=67-5095), [Quick practice](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=67-5316) | DC06; prefill, separate Send, connected daily generation/cache |
| Projects/goals | [Project](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=4-4609), [Goals](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=5-2969), [workspace Goals](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=25-3701) | DC05/DC09; shared references, actual authored/evidenced progress |
| Workspace | [Launcher](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=25-2234), [Files](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=25-2522), [reader](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=25-2863), [Sources](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=25-3156), [Notes](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=25-3440), [Goals](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=25-3701), [contextual workspace](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=28-4018) | DC07–DC09; 480 px originals and responsive compositions |
| Library/readers | [Library](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=4-4337), [Library workspace](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=25-3996), [PDF beside chat](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=29-4500), [Library PDF](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=29-4724) | DC08/DC10; opening/context independent of extraction/indexing |
| Search/secondary navigation | [Search](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=25-4773), [More](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=25-4860), [search overlay](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=32-4969), [More overlay](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=32-4985) | DC03/DC10/DC11; preserved destinations |
| Updates/collapse | [Updates](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=25-4280), [Updates detail](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=25-4526), [collapsed](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=28-4106), [collapsed workspace](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=28-4316) | DC03/DC10; retained source/version/freshness meanings |
| Tests collection/question/results | [Collection](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=4-5061), [question](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=4-5232), [results](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=4-5407), all 46 states below | DC12–DC19; synthetic examples, no app-scoring claim |
| Settings/connection availability | [Settings](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=119-17244), [disconnected](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=119-11099) | DC03/DC10; DECISIONS allowlist, deliberate retrieval configuration |

## Added operational and responsive references

All 21 reference roots are editable on the same C page. They use Source Sans 3, existing palette/variables and navigation/button/composer language. Workspace instances were detached locally in new responsive clones to permit independent scroll overrides; nested controls and token bindings remain. Global components and tokens were not changed.

| Reference | Connected acceptance owner | Reviewed state contract |
| --- | --- | --- |
| [First run / disconnected](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=119-11099) | DC03/DC06/DC10 | No name/connection required to browse local content; connection action remains reachable. |
| [Archived conversations](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=119-11294) | DC04/DC10 | Restore distinct from deletion; archive retains conversation and attachments. |
| [Empty project](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=119-11452) | DC05 | Chats, shared documents and goals discoverable without invented activity. |
| [Settings & connections](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=119-17244) | DC03/DC10 | Greeting name, selected subscription/model choices, optional retrieval, data and display. |
| [Empty learning memory](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=119-17437) | DC10 | No fabricated memory; unavailable-source semantics do not imply automatic memory deletion. |
| [Today & study preferences](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=119-17591) | DC09/DC10 | No plan/progress recorded; global planning remains reachable. |
| [Teaching-case catalogue](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=120-11820) | DC10 | Synthetic cross-domain examples; separate from saved daily discussion. |
| [Draft conflict / interrupted response](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=120-12003) | DC04 | Preserve draft; reconcile conflict; retain partial response and offer recovery. |
| [Library import / recovery](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=120-12219) | DC08/DC10 | Preserve original; separate preview, extraction and deliberate indexing. |
| [Explicit temporary conversation](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=122-12225) | DC04 | Save conversation / Discard temporary confined to explicit temporary mode. |
| [Final Test submission / saving error](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=122-12403) | DC14 | Submit disabled until displayed choices durable; retain work and offer recovery. |
| [Active-Test restriction](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=122-12649) | DC07/DC08/DC14 | Hide help content while retaining tab identity; return to attempt. |
| [Resize: 640 px workspace](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=123-12895) | DC03/DC07 | 272 / 528 / 640; focused splitter reference has 8 px hit area. |
| [1000×720 split](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=123-13205) | DC03/DC07 | 72 / 528 / 400; independent scroll areas, pinned composer/actions. |
| [640×540 focused chat](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=123-13577) | DC03/DC07 | Collapsed navigation; chat occupies remaining 568 px. |
| [640×540 focused reader](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=123-13946) | DC03/DC07/DC08 | Reader occupies 568 px; Back to chat and primary actions visible. |
| [200% effective chat](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=123-14285) | DC03/DC07 | 720×450 effective viewport; chat and pinned composer remain usable. |
| [200% effective reader](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=123-14654) | DC03/DC07/DC08 | Compact header/tabs and 44 px action row; reader content scrolls. |
| [Reader operational panels](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=125-13339) | DC08 | Loading, unsupported detail, missing/corrupt original, OCR failure, restriction, ready, selection and active Test. |
| [Empty Library](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=125-13442) | DC10 | Import available; no fabricated indexed documents. |
| [Empty Tests](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=125-13592) | DC12 | Reviewed/personal origins distinguishable; no fabricated result/nightly completion. |

Reader state panels are reusable compositions inside one reader. Reading may succeed while OCR, extraction, model use or redistribution is unavailable; show the operation-specific state. Missing/corrupt originals retain a recoverable record. Opening a preview does not automatically attach/index its contents. Passage handoff requires a bounded selection/locator, retains the draft and never sends automatically; the no-selection state asks for text selection.

The gallery defines honest states for PDF, DOCX, CSV, XLSX, Markdown, HTML, XML and PNG/JPEG/TIFF images. It does not establish actual rendering, parsing, OCR, table handling, locators, original access or isolation for any category. DC08 measures each adapter and DC17 consumes declared extraction capabilities.

## Legacy destination map

Baseline `apps/desktop/src/shell/navigation.tsx` exposes Today, Learn, Library, Cases, Test, Memory, Updates and Connections. Preserve routes with migration adapters while replacing their presentation.

| Existing destination | C destination / reviewed route | Owner |
| --- | --- | --- |
| Today | More → [Today & study preferences](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=119-17591) | DC03/DC09/DC10 |
| Learn | [New chat](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=4-3926) and saved conversations | DC03/DC04/DC06 |
| Library | [Library](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=4-4337) / contextual reader tabs | DC08/DC10 |
| Cases | [Saved daily Case discussion](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=4-4855) plus More → [teaching catalogue](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=120-11820) | DC04/DC10 |
| Test | [Tests collection](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=4-5061) / shared Study/Test engine | DC12–DC19 |
| Memory | More → [Learning memory](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=119-17437) | DC10 |
| Updates | [Updates](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=25-4280) | DC10 |
| Connections | Footer/More → [Settings & connections](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=119-17244) | DC03/DC10 |
| Study preferences / data / accessibility | More → Today/preferences; Settings → models/retrieval, backup/data, display/accessibility | DC09/DC10/DC20 |
| Archive | More → [Archived conversations](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=119-11294); restore distinct from delete | DC04/DC10 |

These are destination/contract checks. The parent implements router state, adapters and controller landmarks. A Figma navigation reaction does not establish a connected account operation or working application route.

## All 46 Test specimens reviewed

The review reused the existing specimens and inspected text/state inventory, action destinations, retained bindings, timer/import/generation distinctions, assistance restrictions and representative question/result pixels. It did not execute every prototype branch or application journey. Original Test reaction-bearing nodes remained 705; 50 unique destinations resolve without missing nodes. New operational references are separate from these 46 originals.

| # | Existing specimen | Connected owner |
| --- | --- | --- |
| 1 | [Tests collection · 4:5061](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=4-5061) | DC12 |
| 2 | [Test question · 4:5232](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=4-5232) | DC14 |
| 3 | [Test results · 4:5407](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=4-5407) | DC14 |
| 4 | [Reviewed-bank setup · 81:5381](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=81-5381) | DC12 |
| 5 | [Study setup · 81:5558](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=81-5558) | DC12/DC13 |
| 6 | [Timed setup · 81:5735](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=81-5735) | DC15 |
| 7 | [Generate setup · 81:5921](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=81-5921) | DC16 |
| 8 | [Chat-created Study setup · 81:6114](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=81-6114) | DC18 |
| 9 | [Custom timer · 81:6270](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=81-6270) | DC15 |
| 10 | [Test paused · 82:6141](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=82-6141) | DC14 |
| 11 | [Leave Test · 82:6280](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=82-6280) | DC14 |
| 12 | [Report question · 82:6419](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=82-6419) | DC12–DC14 |
| 13 | [Report saved · 82:6581](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=82-6581) | DC12–DC14 |
| 14 | [Generation ready · 82:6711](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=82-6711) | DC16 |
| 15 | [Personal Study setup · 82:6852](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=82-6852) | DC12/DC13 |
| 16 | [Personal Test setup · 82:7014](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=82-7014) | DC12/DC14 |
| 17 | [Test import · 83:7245](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=83-7245) | DC17 |
| 18 | [Import review · 83:7406](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=83-7406) | DC17 |
| 19 | [Nightly off · 83:7590](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=83-7590) | DC19 |
| 20 | [Nightly on · 83:7750](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=83-7750) | DC19 |
| 21 | [Chat test saved · 83:7934](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=83-7934) | DC18 |
| 22 | [Test generating · 83:8114](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=83-8114) | DC16 |
| 23 | [Generation recovery · 83:8258](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=83-8258) | DC16 |
| 24 | [Test choice selected · 86:8169](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=86-8169) | DC14 |
| 25 | [Test next question · 86:8435](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=86-8435) | DC14 |
| 26 | [Test review · 86:8701](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=86-8701) | DC14 |
| 27 | [Test expired · 86:9144](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=86-9144) | DC15 |
| 28 | [Study question · 86:9324](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=86-9324) | DC13 |
| 29 | [Study choice selected · 86:9509](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=86-9509) | DC13 |
| 30 | [Study help · 86:9694](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=86-9694) | DC13 |
| 31 | [Study feedback · 86:9877](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=86-9877) | DC13 |
| 32 | [Study next question · 86:10085](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=86-10085) | DC13 |
| 33 | [Study paused · 86:10270](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=86-10270) | DC13 |
| 34 | [Study complete · 86:10430](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=86-10430) | DC13 |
| 35 | [Study expired · 86:10588](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=86-10588) | DC15 |
| 36 | [Timed Test · 86:10746](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=86-10746) | DC15 |
| 37 | [Study final feedback · 86:11013](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=86-11013) | DC13 |
| 38 | [Study next choice selected · 90:9822](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=90-9822) | DC13 |
| 39 | [Study next help · 90:9986](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=90-9986) | DC13 |
| 40 | [Study next feedback · 90:10151](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=90-10151) | DC13 |
| 41 | [Test next choice selected · 90:10332](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=90-10332) | DC14 |
| 42 | [Partial Study · 90:10541](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=90-10541) | DC13 |
| 43 | [Timed collection · 90:10690](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=90-10690) | DC12/DC15 |
| 44 | [Ready collection · 90:10907](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=90-10907) | DC12/DC16 |
| 45 | [Timed Study · 90:11149](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=90-11149) | DC15 |
| 46 | [Timed Study setup · 90:11317](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=90-11317) | DC15 |

Retained assessment contract:

- Study choices are drafts until explicit Submit answer. Record help exposure before returning help; feedback locks committed answers. Next clears prior help/feedback. Partial outcomes include only committed answers; pending choices survive resume without invented scores.
- Test choices remain editable durable drafts until atomic final submission. Hints, keys, explanations, notes, sources and chat assistance remain unavailable before submission, including workspace/search/deep links. Backend policy is authoritative.
- Manual final submission includes or waits for the latest displayed choices. Saving/error UI retains choices and disables Submit until recovery. Expiry uses backend durable deadline/choice authority, not screenshot countdowns.
- Untimed is the setup default. Timed Study and timed Test differ; timed Test has no Pause. Untimed attempts can pause/resume. Timing, presentation and help exposure remain actual attempt data, separate from graded outcomes.
- Question seems wrong is a neutral local report pinned to question/version/attempt; no help reveal or score mutation. Retake starts a new attempt.
- Origin, review quality, mode and timing are separate. Generated/imported/personal results do not enter reviewed-bank cohorts. Versions are immutable; attempts stay pinned.
- Import preserves private originals and maps candidates to them. Missing/ambiguous keys require explicit review; format/duplicate validation is not answer-key review.
- Generation uses validated saved artifacts and truthful Generating/Ready/Needs review/recovery states. Nightly is off by default, app-running, with one bounded catch-up; no invented completed run.
- Temporary-to-test transition performs the spec's volatile validated fictionalisation before durable processing, or explicitly Save first. Raw temporary material cannot enter a recoverable job.

## Evidence retained

Local evidence root: `C:/Renulus/scratch/design-c/design/evidence/`, outside Git. Short-lived screenshot asset URLs were not persisted in the report or receipt. The following twelve PNGs were exported through Figma and visually inspected.

| Local PNG | Figma node | Reviewed pixels |
| --- | --- | --- |
| `home.png` | `4:3926` | 1440×900 Home hierarchy, actions, Attach/removals |
| `saved-case.png` | `4:4855` | 1440×900 saved-default Case, project/archive actions |
| `project.png` | `4:4609` | 1440×900 conversations, shared documents/goals |
| `library.png` | `4:4337` | 1440×900 Library and Back to chat |
| `chat-reader-1440.png` | `25:2863` | 1440×900, 272 / 688 / 480, focused separator |
| `split-1000.png` | `123:13205` | 1000×720, 72 / 528 / 400, pinned actions/composer |
| `reader-640.png` | `123:13946` | 640×540 focused reader and return |
| `reader-200-percent.png` | `123:14654` | 720×450 effective viewport, compact title/44 px actions |
| `test-question.png` | `4:5232` | 1440×900 untimed Test, neutral attempt pane/help restriction |
| `test-results.png` | `4:5407` | 1440×900 synthetic result, locked answers, available sources |
| `settings.png` | `119:17244` | 1440×900 name/connections/retrieval/data/display |
| `reader-states.png` | `125:13339` | 1440×770 operational-panel gallery |

`reconciliation-audit.json` records page, Test counts/destinations, 31 widened panes, 21 new roots/font and export dimensions. `evidence-sha256.json` records hashes for all PNGs and the audit receipt.

The final structural audit found no visible stale Auto, Ask a follow-up, Your learning space or “2 of 3 completed”. Temporary labels occur only in the explicit temporary reference. All new roots use Source Sans 3. No image-filled UI node larger than 96×96 was found; screens retain editable composition.

The workspace/public local-link check passed on the final report: 18,251 public files, 1,166 local links, 27 topics and 199 subtopics. Source-path/status review confirmed only this report was authored in Git. The final staged whitespace check and commit identity accompany the handoff. No application runtime, model/provider call, owner profile or native/computer input was used. No connected feature ticket closes from this evidence.

## Exact recommended parent updates

The parent owns these edits; this worker has not changed their files.

1. **C spec section 3:** replace the historical 360 px observation with “October 10 DC01 reconciliation saved 31 original open panels at 480 px; 272 / 688 / 480 on the 1440×900 default. Source Sans 3, semantic teal tokens and existing components remain.” Link this report. Retain the discrepancy list as dated/resolved evidence or replace it with the correction/reference tables above. Preserve original screen-family owners.
2. **C spec section 4 / Workspace:** append “Reviewed engineering candidates: preferred 480 px, workspace 360–640 px, conversation minimum 528 px; collapse navigation to 72 px below approximately 1280 effective px when needed; below 960 effective px use one focused pane with Back to chat. Persist preference independently of clamping. See design-c-reconciliation.md for final node links; runtime resize/zoom/focus evidence remains DC03/DC07/DC08/DC20.” Preserve planning-default labels and policy/retention rules.
3. **C spec DC01 / section 9 status:** record “DC01 design prerequisite: pass 1 reviewed October 10, 2026; editable C copy, geometry, operational states and 46 Test-specimen inventory reconciled. See design-c-reconciliation.md. Feature tickets retain connected acceptance.” Update any blanket Not started status only from the parent's current execution evidence; this report does not establish DC02/feature completion.
4. **PRODUCT authority/status:** link this report with “DC01 design references reconciled October 10; C implementation remains subject to connected ticket evidence.” Retain confirmed product direction and delivery-status distinction.
5. **DESIGN authority/Layout:** link this report as the C geometry/state target. Label dimensions as reviewed candidates. Retain existing implementation/token/44 px target evidence; update component/token records only from actual C code and remove superseded Flow guidance at cutover.

## Handoff and remaining work

DC01 pass 1 supplies the reconciled visual contract for shell work. The only authored Git path is `docs/implementation/design-c-reconciliation.md`. Figma edits are saved and immediately available. The branch consumes `1ca45ff2` and adds no schema/version/migration/manifests prerequisite. The parent can cherry-pick the report commit onto its newer integration branch.

DC03 implements shell/navigation/focus/controller readiness; DC04 ordinary/temporary/archive/conflict persistence; DC05 projects; DC07 actual drag/keyboard resize, safe tab/width persistence and contextual isolation; DC08 readers/extraction/original access/passage gates; DC09 notes/goals; DC10/DC11 preserved routes/search; DC12–DC19 connected assessment/import/generation/nightly. DC14/DC20 prove integrated active-Test enforcement. DC20 proves native/effective zoom, keyboard, high contrast, long text and migration journeys; DC21 owns packaged/native/provider acceptance.

Remaining feature implementation is not a design blocker for Workspace leasing after the parent's pass 1 review. This lane's reservation remains held through report/commit and returns to the parent on the final explicit handoff.
