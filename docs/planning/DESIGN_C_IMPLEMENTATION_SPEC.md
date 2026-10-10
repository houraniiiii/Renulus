# Design C implementation spec

October 10, 2026 · Status: reviewed, ready for implementation · Source baseline: `85a0ac1e`.

Replace the current Flow interface with **Design C: chat, projects and an optional
workspace**, while preserving Renulus's working learning, source, assessment,
memory and Windows capabilities. This is one implementation backlog. Each DC
ticket below can become an issue; its ID stays stable when the work is split.
This document defines the build; writing it does not establish implementation.

## October 10 scope amendment — connected UI and OpenCode handoff

The owner's later instruction replaces the standalone Hermes default-release
completion condition. Finish the connected Design C experience and preserve its
reusable domain backend, then commit an integration handoff for the selected
OpenCode v2 phase. Do not implement that migration here. The existing adapters
remain operational; the normal launcher, owner profile and credentials remain
unchanged. DC01–DC21 requirements remain migration regression obligations.
**DC21's original final default release is deferred to H20, not passed.**

This finite closeout list supersedes the historical release work below. Add work
only for a reproduced material interaction defect within these boundaries:

| Closeout | Scope / owner | Completion evidence |
| --- | --- | --- |
| C-01 | Lead: DC16/DC19 prerequisite H00 | Reproduce the saved-generation retrieval guard mismatch; use explicit caller-specific execution checks before/after retrieval; rerun affected generation/nightly and legacy guard checks. |
| C-02 | Dalton + lead: DC07/DC08 saved Reader failure | Reproduce saved attachment access under concurrent conversation ownership; repair without weakening temporary, rights, policy, epoch or original-integrity checks; verify affected Reader UI and reopen. |
| C-03 | Zeno + lead: finite DC03–DC19 interaction audit | Reuse valid screen/journey evidence; resolve only remaining material connected gaps and verify affected narrow/zoom/keyboard/error/draft/source-navigation states with the hidden controller. |
| C-04 | Lead: DC20 documentation handoff | Freeze the read-only uncommitted a11f plan snapshot; map accepted UI, retained backend evidence, unresolved defects and H owners; document domain identities/APIs, replaceable adapters and reproducible isolated review launch. |
| C-05 | Lead: DC21/H20 disposition | Preserve installer/recovery receipts with exact revisions and limits; defer exhaustive release/default cutover; commit final handoff and end the continuity automation. |

Memory transitive lineage/recapture (H05), deleted saved receipt payloads
(H06/H18), actual worker settlement (H24) and authentication availability (H03)
remain open until their owners repair them. Existing single-store recovery
evidence does not close those findings or future two-store migration acceptance.
Temporary execution graphs, spills and Save belong to H21 with H01 substrate;
H06 owns saved migration. No new execution/configuration/transcript authority is
introduced in this closeout.

## 1. How to use this spec

- Read the relevant ticket, its dependencies and the shared rules below. Inspect
  the current code before estimating or adding a replacement subsystem.
- Confirmed user decisions govern. Figma supplies visual direction and examples.
  **Planning defaults** below are adjustable engineering/UX choices, not new
  user decisions. Change them when evidence improves the result, recording why.
- Deliver connected vertical slices, with real persistence and failure states.
  Feature tickets require connected behavior, not a component demo or mocked
  backend. DC01 is a design prerequisite with its own review evidence; DC02
  closes on shared contracts and migration-foundation evidence, with each feature
  adding its own migrations. Neither prerequisite claims a delivered feature.
- Keep the selected Hermes/Electron/React/Python foundation and existing approved
  subscription, memory and document engines. Preserve one design system and the
  Renal flow logo. This work does not reopen stack or model selection.
- Follow [module ownership](ARCHITECTURE.md), [worktree rules](PARALLEL_WORK.md)
  and [hidden app control](../implementation/APP_CONTROL.md). This spec supersedes
  older Flow layout and temporary-by-default plans for the Design C migration.

Decision evidence: [confirmed choices](../DECISIONS.md),
[dated user answers](2026-10-04-user-answers.md),
[new-chat details](2026-10-09-design-c-new-chat.md), and
[Tests decisions and prototypes](2026-10-09-design-c-tests.md).

## 2. Product contract

| Area | Required outcome | Tickets |
| --- | --- | --- |
| Navigation | Renulus, search and collapse at top left; New chat, Library, Tests, Updates above projects and recent chats. Secondary tools remain reachable. | DC01, DC03, DC10, DC11 |
| Chat | Explain and Case discussion share a conversation-oriented experience. Conversations/context save by default, including cases; Archive and optional temporary conversations exist. | DC04 |
| New chat | Chosen-name greeting; “How can I help you today”; Attach retained; Auto, introductory filler, learning-space tick/row and Ask a follow-up removed. | DC01, DC06 |
| Suggestions | Explain a topic, Discuss a case and Quick practice each reveal five suggestions, refreshed daily by the selected backend model using eligible usage/memory. | DC06 |
| Projects | Chats, shared documents and study goals together; chats can also exist without a project. | DC05, DC09 |
| Workspace | Optional, resizable and wider by default than the current 360 px C specimen. Holds files, readers and useful contextual material; tests created in chat also open here. | DC07, DC08, DC18 |
| Readers | In-app PDF, DOCX, CSV, XLSX, Markdown, HTML, XML and image reading/rendering. | DC08 |
| Tests collection | Reviewed bank, user-added/refined tests, opt-in nightly tests and tests created in conversations; the chat card and collection reference the same saved test. | DC12, DC16–DC19 |
| Assessment | Explicit Study commitment/feedback; durable Test choices and final submission; assistance/feedback rules, resume, optional timing, local Question seems wrong and honest results. | DC12–DC15 |
| Set sizes | Generated 5/10/20 via validated batches; Quick practice is five; reviewed 1–50 where suitable content is available. | DC12, DC16 |
| Nightly | Off by default, configurable time/count, bounded app-running execution and one catch-up. | DC19 |
| Continuity | Preserve saved history, sources, originals, study evidence, memory, connections, backups and existing useful flows during the transition. | DC02, DC10, DC20, DC21 |

TXT, PPTX and EPUB were suggested but not newly confirmed. Existing supported
formats must continue working; this spec does not expand the promised new reader
set beyond the eight categories above. Full Office editing, collaboration/cloud
sync, an agent terminal, arbitrary browser automation and a closed-app Windows
nightly worker are outside this change.

## 3. Figma source and design corrections

Use the editable [C page](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=2-250),
not the static [three-column comparison](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=13-23),
for behavior. The comparison is useful for visual review only.

| Screen family | Reference nodes | Build coverage |
| --- | --- | --- |
| Home/conversation/case | C01 `4:3926`, C02 `4:4134`, C05 `4:4855`; suggestions C26–28 `67:4874`, `67:5095`, `67:5316` | DC03, DC04, DC06 |
| Projects and goals | C04 `4:4609`, C09 `5:2969`, C15 `25:3701` | DC05, DC09 |
| Workspace | C10–15 `25:2234`, `25:2522`, `25:2863`, `25:3156`, `25:3440`, `25:3701`; C21 `28:4018` | DC07–DC09 |
| Library/readers | C03 `4:4337`, C20 `25:3996`, C24 `29:4500`, C25 `29:4724` | DC08, DC10 |
| Search/secondary navigation | C16 `25:4773`, C19 `25:4860`; overlays `32:4969`, `32:4985` | DC03, DC10, DC11 |
| Updates/collapsed navigation | C17 `25:4280`, C18 `25:4526`, C22–23 `28:4106`, `28:4316` | DC03, DC10 |
| Tests | Collection `4:5061`; setup `81:5381`; 46 documented states and linked flows in the Tests plan | DC12–DC19 |

Live inspection on October 10 found 1440×900 main specimens, a 272 px left
navigation and 360 px open workspace. Use Source Sans 3, the existing semantic
teal tokens, restrained surfaces and editable components as the visual baseline.

Correct these discrepancies in DC01 before treating the designs as implementation
acceptance references:

- C05 and Goals still describe temporary case/explicit Save as the default.
  Ordinary conversations now save; show that copy only in explicit temporary mode.
- Increase workspace width and supply real resize/narrow-window behavior.
- Remove residual “Your learning space” filler, including the More heading.
- C24's “revision outline” is an example PDF title, not a new generated-outline
  product feature. Its reader should work for any supported document.
- Replace illustrative progress, sources, names, timer values and chat suggestions
  with data-driven states. A screenshot cannot establish completion or scoring.
- Add necessary empty/loading/error, draft conflict, archive, import, narrow-window
  and assessment restriction states; do not invent another screen for every error.

## 4. Shared interaction and data rules

### Navigation and composition

One shell owns route, selected project/chat and workspace state. Opening a reader,
switching tabs or collapsing navigation must retain chat draft, messages, scroll
position and running-response identity. Back returns to the previous meaningful
place. Preserve useful legacy routes with adapters during migration.

**Planning defaults:** New chat is the landing view; resume is a small real-data
entry below the composer. More contains Learning memory and Study preferences;
Settings & connections exposes account/model selection, retrieval connections,
data management and accessibility/display preferences. Keep a simple path to
global Today/study planning and to the existing teaching-case catalogue.

Use accessible controls, visible keyboard focus, sensible focus return and
independent scrolling. Collapsing the sidebar must leave New chat, search and
expand reachable. A chat-first layout must still work without a connected model.

### Conversation, project and content identity

- Preserve current IDs and provenance. Unassigned existing chats remain available
  under recent chats; do not infer or silently create project memberships.
- Store content once and link it. Project documents, chat attachments, workspace
  tabs and Library rows must not create copies or separate competing authorities.
- A project scopes shared context; opening a file does not silently attach its
  full contents to a model request. Explicit passage/file use is visible in the
  draft and removable. Resolve references and access eligibility in the backend.
- Moving a chat changes context for future requests; earlier messages keep their
  cited revisions and provenance. Unlinking a file does not delete its Library
  original. Deleting a project must disclose and preserve independently owned items.
- Archive hides an item from active lists without deleting its history/context;
  include restore and a separate delete action. Temporary conversations remain
  explicitly labelled; their raw/identifiable content stays out of durable drafts,
  background jobs, search and exports. The fictional-test exception below is explicit.
- Separate conversation kind (learning/case), retention (saved/temporary) and
  lifecycle (active/archived/deleted). The current `ContextScope` mixes these;
  changing retention must not make saved case payloads eligible for learner memory.
- Saved conversation content does not automatically become learner memory or
  distributable teaching material. Existing memory/source eligibility still applies.
- New records participate in delete, export, restore and migration. Async work
  rechecks deleted/revised dependencies before publishing its result.

**Deletion planning default:** deleting a chat removes its messages and owned
originals, cancels pending work and invalidates search/context references.
Separately retained learning memory remains inspectable with an unavailable-source
marker; disclose this and offer an explicit delete-related-learning choice.
Prune provenance edges without deleting independently edited/multi-source facts
by accident. Memory deletion/correction always invalidates applicable jobs and
derived personalisation. Tombstone removed attachments as well as conversations.
Restore follows typed ownership/reference edges: deleting a project must never
propagate through its membership link into a shared Library original.

### Workspace and file readers

**Planning default:** start at 480 px on the 1440 px specimen, persist the preferred
width locally, and clamp it so chat remains usable. On small windows, collapse
navigation first and use one focused content pane with an explicit return to
chat when two panes no longer fit. DC01 validates actual minimums at zoom; the
numbers are engineering defaults, not fixed user decisions.

**Adopted planning defaults from C:** the workspace launcher offers Files, Sources,
Notes and Goals, with contextual tabs and grouped local content search (DC11).
These extend the confirmed workspace/search placement; their arrangement remains
adjustable. Opening a file or
saved test creates/selects a tab keyed by canonical identity; reopening the same
item reuses it. Tabs can close/reorder, reader position survives switching, and
context belongs to the selected chat/project. Never restore a temporary document
through persisted tab metadata. No Files/Test navigation duplication on the right.

An attached file belongs to its conversation unless deliberately added to Library;
viewing it must not require permanent Library import or successful indexing.
DC02/DC08 define an owned original/preview record and separate extraction/index
states. Keep the existing display/access checks; do not bypass them by exposing
arbitrary file paths. Project files link Library revisions, while conversation
attachments retain their own ownership and retention. Previews alone do not grant
permission to use a file as model context.

“Ask about this passage” adds a bounded selected/cited passage and locator to an
editable chat draft; it does not submit automatically. With no selection, use an
explicitly identified current passage, or ask the user to select text. Preserve
existing draft text. Respect temporary scope and active-Test restrictions.

| Format | Minimum reader behavior to validate | Content-use boundary |
| --- | --- | --- |
| PDF | Page navigation, zoom, text selection/search where text exists, cited-page jump, original access | Scanned pages need actual OCR before text selection/passage claims; physical and printed pages remain distinguishable. |
| DOCX | Readable headings, paragraphs, lists, tables and images; search/selection | Reflow is acceptable; preserve section/paragraph locators without inventing original page numbers. |
| CSV | Header/row table, horizontal scrolling, delimiter/encoding handling and bounded large-file display | Preserve literal values, column names and row locators; do not execute formula-looking cells. |
| XLSX | Sheet switch, tabular reading, preserved displayed values and useful cell/range locators | No macro/formula execution; clearly handle missing cached formula values and unsupported workbook features. |
| Markdown | Render headings, lists, links, code and tables with text selection | Sanitise embedded HTML; source/section locators survive rendering. |
| HTML | Readable document with links and selection; original/source option where useful | Isolated, sanitised content; no scripts, app bridge, arbitrary local-file access or automatic remote requests. |
| XML | Formatted escaped text/tree, search and selection | No external entity resolution; do not claim a medical-specific viewer from generic XML support. |
| Images | Fit/zoom/pan and original access; planning baseline PNG/JPEG and the already ingestible TIFF | OCR/text extraction and model image interpretation are separate capabilities and states; handle multi-page TIFF explicitly. |

Every reader distinguishes loading, unsupported detail, missing/corrupt original,
extraction failure, access restriction and ready. An external Save/Open original
fallback is useful but does not satisfy the required in-app reader. Reuse the
current original-access and source-permission policy. Bound file size, rows,
pages and parser work; defer component/package selection to measured reuse.

Reader capability acceptance is explicit:

| Formats | Read inside app | Extraction and selected-content handoff | Model/test-import use |
| --- | --- | --- | --- |
| PDF, DOCX, Markdown | Required, even when extraction fails | Reuse extraction; preserve page/section/text locators. Scanned PDF text requires successful OCR. | Extracted eligible text; unavailable extraction has a retry/disabled state. |
| CSV, XLSX | Required table/sheet reading | DC08 owns bounded CSV extraction and reuse of XLSX extraction, with row/cell locators. | Eligible selected rows/cells or extracted questions; no formula execution. |
| HTML, XML | Required inert reading | DC08 owns bounded generic text extraction and stable source/section locators as a planning default; XML carries no domain-specific interpretation promise. | Eligible extracted text, after validation; no execution or automatic remote fetches. |
| PNG/JPEG/TIFF images | Required for the baseline extensions | OCR only where successful; no fabricated selectable text. | Test import uses OCR text; direct image interpretation uses only the existing supported selected-model path, with honest unavailable states. |

In-app reading is mandatory for every category. Passage-to-chat and test extraction
depend on successful extraction and operation-specific eligibility; preview-only
and restricted examples are valid states. Full Library indexing is deliberate,
not a side effect of viewing. DC08 owns the missing extraction adapters; DC17
consumes these declared capabilities instead of assuming every reader yields text.

Untrusted document content must not obtain authenticated app-API authority or
navigate the shell, including through same-origin links/forms/resources. Electron
currently stamps API authentication by owning `webContents`; blocking scripts or
the preload bridge alone is insufficient. F0 and M2 must isolate inert output and
let trusted host code mediate original retrieval and permitted external links.

### Notes, goals and suggestions

**Planning defaults:** notes reuse the Library study-note concept with project
links and editable revisions. Goals are user-authored project study intentions
with topic, optional target/date and manual or evidenced progress. Global study
preferences remain the default; project overrides are explicit. Use existing
study planning before introducing AI goal planning. Never infer mastery from
chat counts, suggestion clicks or invented percentages.

A selected suggestion prefills the composer; Send is separate. Show five per
category, with only one category expanded. Do not overwrite an existing draft.
Generate one validated daily bundle through the selected subscription; cache and
deduplicate refreshes. Reuse eligible usage/memory, not raw case dumps or reviewed
answer keys. Old valid suggestions may remain with their date; first-run/offline
states leave the composer usable. Invalidate affected derived suggestions after
memory deletion/correction, relevant context changes or restore.

### Tests and assessment

One saved test has immutable versions; an attempt pins one version. Editing makes
a new version and never rewrites historical/active attempts. Origin, review
quality, assessment mode and timing are separate fields. Personal/generated/imported
results cannot enter reviewed-bank score cohorts merely by choosing Test mode.

| State/action | Study | Test |
| --- | --- | --- |
| Selecting an answer | Draft until explicit Submit answer | Autosaved draft, editable until final Submit test |
| Help | Record assistance before returning hints, sources, notes or chat help | No hints, keys, explanations, notes, sources or chat assistance before final submission |
| Commit | Locks that answer; show its feedback | Final confirmation commits the whole attempt atomically |
| Navigation | Next clears prior help/feedback; revisiting committed items cannot edit them | Previous/Next/jump/skip/mark for review; navigator has no correctness cues |
| Completion | Summary of committed work, review and Retake | Answered/unanswered/marked review, final submission, results, mistakes and Retake |
| Resume | Restore exact question, drafts, committed answers and assistance | Restore drafts, marks, position and the same restriction/timing policy |

Question presentation/family exposure is recorded before returning content;
help exposure is recorded before returning assistance. These persist even if a
question is never answered. Graded results and learning evidence follow Study's
per-answer commitment or Test's final commitment, separately from exposure.

Manual Submit test must include or wait for the latest displayed choices to be
durable; refuse completion with a recoverable saving error if that cannot be
established. A submit request cannot silently overtake a pending save. Reconcile
lost acknowledgements against backend state before retrying or claiming loss.

**Planning default for unfinished Test:** one active Test per profile. Leaving
preserves its restriction across shell navigation and restart; Test cannot be
paused. Offer
Resume or Review and finish; submitting early counts blanks and restores study
access. Settings needed for recovery remain available. Enforce the policy at the
backend operations as well as UI; hiding a Workspace button alone is insufficient.
These are educational assessment rules, not a claim of a proctored exam system.

The disclosure audit includes legacy answer/help/review responses and command
replays, aggregates/progress/mistakes, study evidence, source-currency links,
ordinary chat requests and search snippets. Test drafts publish no scored answer
or learning evidence. Before submission, currency warnings are neutral and omit
source/key details. **Planning default:** plaintext export, downloadable backups
and restore activation require finalising an unfinished Test first; the current
backup contains question/key snapshots. Keep connection/recovery status visible.
Normal local data access is not represented as tamper-proof examination security.
Starting Test also resolves/cancels in-flight assistance and invalidates cached
help surfaces. Late chat/help/search responses from the previous state cannot
reappear inside an active Test.

Untimed is default. A timed Test starts only when a ready attempt starts. Persist
start/deadline and reconcile on every attempt read/write and after restart; at
expiry submit backend-durable drafts accepted before the deadline and unanswered
items exactly once, even if a save acknowledgement never reached the renderer.
Closing the app does not pause it. Closed-app expiry is resolved on reopen; it
does not imply a background Windows service. Display saving/error state truthfully.

If an active item's content is corrected, withdrawn or unavailable, finalisation
must still reach a terminal result. Planning default: retain the pinned choices
and versions, flag affected items, exclude invalid items from the new score's
denominator and show excluded/unanswered counts separately. Never rewrite a prior
result. Publish graded results and eligible learning evidence atomically;
presentation/help exposure keeps its earlier boundary.

**Timed Study remains a planning choice:** use the proposed pauseable timer;
expiry saves committed progress and the pending draft, offers Continue untimed
or Finish study, and never auto-submits the pending answer. Keep this distinction
visible in setup and acceptance tests. DC01/DC15 may refine it without changing
the confirmed timed-Test behavior.

“Question seems wrong” saves a local report pinned to the question/test version
and relevant attempt. It is available during Study and Test with neutral
confirmation, no assistance, and no automatic key, review-quality or score change.
Reporting is idempotent; resolution can create a new personal version without
rewriting prior attempts. It does not send a message to anyone.

Generated/imported tests retain their source/provenance and private terms.
Agent refinement may repair structure; ambiguous/missing keys remain review
items. Ready requires valid questions/keys, without implying bank review.
Cancelled/failed batches preserve usable drafts; starting a shorter recovered
set requires an explicit displayed count. Nightly uses eligible saved learning
inputs and fictionalises case details; temporary conversations are not its input.

**Temporary-to-saved test boundary:** an explicit create-test action may first
transform temporary input into validated generalised fictional questions entirely
in volatile memory. Only that fictional artifact may cross into a saved test or
durable generation checkpoint. Raw input, identifying derivatives, logs, source
references and job metadata that reconstruct the temporary case stay volatile.
Alternatively, explicit Save precedes durable processing of original details.
Cancellation/restart before the boundary retains nothing; after it, recovery owns
only the fictional artifact. This is the narrow exception to derivative exclusion.

## 5. Implementation map

Use the source paths below as entry points, not a mandated list of files to edit.
The audit distinguishes working foundations from missing Design C capabilities.

| Area | Reuse | Extend/build |
| --- | --- | --- |
| Desktop | [shell](../../apps/desktop/src/shell/), [UI](../../apps/desktop/src/ui/), [platform](../../apps/desktop/src/platform/) | C navigation/composition, persistent selection, workspace, meaningful global search |
| Conversations | [Learn](../../runtime/renulus/learn/), [Cases](../../runtime/renulus/cases/) | Unified presentation/identity links, saved-by-default cases, durable drafts and Archive |
| Projects/study | [Study](../../runtime/renulus/study/), [Memory](../../runtime/renulus/memory/) | Project membership/shared context and goals; chosen-name preference, daily suggestions |
| Documents | [Knowledge](../../runtime/renulus/knowledge/), [Library UI](../../apps/desktop/src/modules/library/) | Embedded readers for required formats, reusable workspace adapters and passage-to-chat |
| Assessment | [assessment backend](../../runtime/renulus/assessment/), [assessment UI](../../apps/desktop/src/modules/assessment/) | Saved test/version layer, durable Test drafts/final commit, timer, imports, larger generation and nightly |
| Updates | [Updates](../../runtime/renulus/updates/) and its bounded scheduling | C presentation and reuse of job patterns; no second generic scheduler platform |
| Persistence/release | [storage](../../runtime/renulus/storage/), existing export/restore and packaging | Coordinated additive migration, populated-profile compatibility and matching C release evidence |

Source audit findings that determine scope:

- `learn/schema.sql` has threads/messages/runs; Cases persist explicit snapshots
  and become temporary again when dirty. Saved-case Explain/practice handoffs are
  also temporary today. Both lifecycle and handoffs need changes, not just copy.
- Study has global preferences and deterministic activities, not projects or
  project goals. Daily suggestions/chosen-name settings are new. Existing notes
  can be imported into Library but lack the complete workspace edit workflow.
- `ModuleOutlet` remounts by route/revision; shell navigation also resets focus/
  scroll. Pane actions need independent state. Library/Updates layouts currently
  respond to window width; C requires them to respond to their available pane.
- `OriginalViewer` embeds PDFs through Chromium, renders PNG/JPEG, shows Markdown
  as plain text and saves Office originals externally. DOCX/XLSX/TIFF extraction
  is not an embedded reader. General CSV/HTML/XML import is missing; acquired
  JATS processing is not arbitrary XML support. Preserve existing TXT/PPTX paths.
- In current assessment schemas, `assessment_sessions` is a quiz run and
  `assessment_attempts` is a committed answer to one question. Existing `mode`
  means reviewed/generated, not Study/Test. Do not reinterpret those columns.
  Generation defaults to three within a 1–5 limit and starts a session directly;
  C needs a Ready saved test before starting its attempt/timer.
- `storage/backup.py` validates exact record columns and allowlists tables/
  preferences; `recovery_archive.py` allowlists original formats. Additive schema
  changes still need old JSON/ZIP conversion and original-format support.
  Restore's current ID-suffix dependency heuristics need typed relation handling.

Primary audit seams: [navigation](../../apps/desktop/src/shell/navigation.tsx),
[module mounting](../../apps/desktop/src/shell/ModuleOutlet.tsx),
[original viewer](../../apps/desktop/src/modules/library/OriginalViewer.tsx),
[case ownership](../../runtime/renulus/cases/repository.py),
[assessment commitment](../../runtime/renulus/assessment/repository.py),
[backup validation](../../runtime/renulus/storage/backup.py), and
[restore relationships](../../runtime/renulus/storage/recovery_records.py).

Freeze only shared meanings before parallel work: project/chat/content IDs,
retention, typed content references/locators, cancellation/errors, saved
test/version/attempt identity, assistance/feedback policy and job publication.
Keep SQLite authoritative. UI state stores references/preferences, not duplicate
domain records. Module owners choose internal classes and tables with the
integrator; do not mandate a new state library, event bus or service.

## 6. Tickets

At the documentation baseline every ticket was **Not started**. Current execution
status is recorded below and in the linked execution record. Dependencies are completion/integration
gates; work against a frozen producer contract may begin earlier. Every ticket
includes necessary loading/empty/error and keyboard states without repeating them
below. “Prove” describes acceptance evidence, not a mandate to write trivial tests.

### DC01 — Reconcile C designs and implementation states

**Owner:** design + integration. **Depends:** none.

Produce the current screen/state checklist from section 3, retain C typography,
tokens and components, and reconcile saved-default case copy, workspace sizing,
new-chat removals and real assessment rules. Add missing operational states and
narrow/zoomed layouts. Reuse the 46 Test specimens rather than rebuilding them.
Record each screen family's owning ticket and final Figma links in this spec.
Complete this prerequisite with reviewed design/state evidence; code acceptance
belongs to the owning feature ticket and DC20. PRODUCT.md records the selected
C product direction; DESIGN.md retains the implemented visual foundation while
pointing to this target. Update its component/token record from actual C code
as slices land, and remove superseded Flow layout guidance at cutover. Refresh
product and delivery status from evidence rather than prototype completion.

**Prove:** no default-temporary copy in ordinary chat; 480 px candidate workspace
and smaller-window/200% zoom compositions remain readable; all existing user
destinations have a C route; no fixture progress or fake capability is specified
as production data. Review representative home, chat+reader, project, Library,
Test, results and settings with the user-facing copy in place.

### DC02 — Shared contracts and migration foundation

**Owner:** integration/storage with module proposals. **Depends:** none; align DC01.

Define additive record/reference contracts for chat/project membership, content
tabs, preferences, saved tests/versions, attempt drafts and jobs. Reserve migration
ownership and schema numbers. Map legacy Learn, saved Cases, assessment sessions,
Library notes and global study settings; preserve their original IDs/history.
Establish deletion/export/restore coverage and rollback compatibility before
new modules write data. Avoid a blanket database/model rewrite.

Define explicit ownership edges, attachment tombstones, safe preference/table/
media inclusion and adapters for old JSON and supported ZIP exports. Legacy
assessments remain legacy/Study-compatible: preserve original partial denominators,
exposure and already-shown feedback; do not retroactively impose Test timing or
score old blanks. Include paginated conversation reads and server-owned retention.

**Prove:** populated synthetic old-profile upgrade is repeatable and preserves
records; interrupted migration recovers; unsupported schema/downgrade is refused;
no existing temporary case becomes saved by migration. Publish small contract
fixtures so parallel agents can build against the same meanings.
Use representative schema/relation fixtures to prove shared-reference survival,
tombstones and older-export conversion in the foundation. DC04/DC05 and subsequent
record owners prove actual new records; DC20 owns the full populated-profile run.

### DC03 — Build the C shell and navigation

**Owner:** integration/desktop. **Depends:** DC01 and DC02's published references.

Replace Flow composition with C sidebar/header/content slots. Add search/collapse,
New chat, Library, Tests, Updates, projects/recents and secondary destinations.
Implement typed navigation and legacy-route adapters. Keep the existing runtime,
connection/error handling and module services, progressively mounting them in C.
Reserve a small F0/controller prerequisite here: replace Flow-specific readiness
and exact legacy upload-label assumptions with observed C landmarks/inputs, while
keeping hidden-window, owned-backend and fixture/path guards. Coordinate new
format signatures/fixtures with DC08 before reader validation.
Use a temporary development switch only if it simplifies integration; remove it
at cutover rather than maintaining two product shells.

**Prove:** each destination opens through mouse and keyboard; back/forward and
deep links resolve without losing scope; sidebar collapse and resize preserve
drafts; first-run, disconnected and runtime-failure states are usable. No module
or account/data-management action is stranded by removing the Flow rail.
Hidden startup/restart succeeds with collapsed navigation and at 640×540,
1000×720 and 1440×900; the controller can observe the actual C Attach input.

### DC04 — Bring Learn and Case conversations into one chat experience

**Owner:** M1/M3, one coordinated owner. **Depends:** DC02, DC03.

Reuse Learn streaming, cancellation/retry, direct/guided modes, sources and Cases
discussion/attachments behind one conversation surface. Save normal chats and
context by default, including case discussion, with durable drafts and attachment
references. Add rename, Archive/restore, delete and opt-in temporary mode. Show
existing ordinary and saved-case history together without duplicating it.

**Prove:** save/reopen and continue each kind; switching chats during a stream
cannot send output into the wrong chat; interrupted/failed requests retain the
right draft and actual response state; Archive is reversible; deletion prevents
late job resurrection. Raw/identifiable temporary text, attachments and derivatives
stay out of durable stores, history, search, memory jobs and export. DC18's
validated fictional-test transition is the only derivative exception specified here.
Verify multi-turn temporary ordinary chats as well as cases, saved-case handoffs
and teaching-case pinned reveals. Large history paginates without duplication.

### DC05 — Projects, shared documents and scoped context

**Owner:** M1 with M2/M6 interfaces. **Depends:** DC02, DC03; completion requires
DC04 conversation identity. Project APIs can develop against its frozen contract.

Add create/rename/archive/restore/delete project, assign/move/unassign chats and
link/unlink existing Library documents. Build project Chats/Documents/Study goals
views and the sidebar tree. Preserve unassigned history. Resolve eligible shared
documents in project context for new requests; retain original citations on old
messages. Use explicit actions and modest metadata, not another management dashboard.

**Prove:** two projects sharing a document do not copy it; unlinked/deleted content
cannot be newly retrieved through stale membership; moving a chat changes future
scope and preserves historical sources; deleting a project does not silently
delete independent chats/originals. Membership and display order survive restart.

### DC06 — New chat, chosen name and daily suggestions

**Owner:** M1/M6 with M5 eligible-memory interface. **Depends:** DC03, DC04;
complete Quick practice integration after DC12, DC13 and DC16. Consume project/
goal contracts from DC05/DC09 as they become available; their connected inputs
are checked in DC20. Home/caching work can develop before those consumers finish.

Implement the exact home copy/control decisions and chosen-name setting. Keep a
greeting stable while composing and use a generic fallback. Provide three action
pills, five suggestions each, editable prefill and explicit Send. Build a bounded
daily generation/cache job using existing selected routing and eligible evidence;
deduplicate requests and strictly validate the whole bundle before publication.
Quick practice uses DC16's five-question saved-test producer and DC13's Study
engine; it never starts a reviewed test or keeps a second legacy generation path.

**Prove:** repeated opens make one daily request; bad/quota/offline responses keep
a valid prior cache or useful empty state; memory edits/deletion during generation
prevent stale publication. No raw case details or answer keys appear in suggestion
cache. Selecting a suggestion preserves an existing draft and creates no learning
evidence. First-run and absent-name cases work without fixtures.

### DC07 — Resizable contextual workspace and tabs

**Owner:** desktop/workspace. **Depends:** DC02, DC03; connected context completion
requires DC04/DC05. Tab/layout work can start against their frozen references.

Create the optional workspace launcher, drag/keyboard resize, collapse, document
tabs and contextual Files/Sources/Notes/Goals entry points. Store safe width and
tab-reference preferences; keep temporary state volatile. Preserve reader/chat
state on tab switches and define a clear narrow-window single-pane return path.
Give module adapters a small open/focus/close interface with typed references.

**Prove:** opening the same file twice reuses its tab; two chats cannot show each
other's stale context; close/reopen/resize/restart retain eligible position and
selection; removed originals produce an honest state. Focus and splitter control
work at small windows and 200% zoom. Every open/restore operation uses the shared
policy interface; DC07 proves its allowed/denied contract. DC14/DC20 own integrated
active-Test enforcement once that producer exists, avoiding a dependency cycle.

### DC08 — Render the eight file categories and connect passages to chat

**Owner:** M2 with reserved F0 isolation/controller changes. **Depends:** DC02,
DC07 and the DC03 controller prerequisite.

Implement the reader contract in section 4 using current Knowledge extraction,
original access, locators and suitable existing renderer/parser components. Audit
actual supported formats before adding dependencies. Add required preview adapters,
bounded table rendering and safe structured-document rendering. Route Attach,
Library and workspace openings through one file/reference contract. Distinguish
viewable, extractable and model-usable states; implement passage-to-draft.
Own CSV/HTML/XML extraction additions and the per-format capability matrix in
section 4. Split implementation into PDF/images/Markdown, Office/CSV and HTML/XML
adapters if useful; one M2 owner coordinates the registry/original-access seam.

**Prove:** synthetic examples of all eight categories render inside the packaged
app, with tables/units, images and locators intact; large/corrupt files fail
recoverably; HTML/XML/Office content cannot execute code, access the app bridge,
make authenticated same-origin API requests or navigate the shell. Test hostile
links/forms/resources as well as scripts; original retrieval stays host-mediated.
Test unsupported details, permission denial, missing/deleted revisions, OCR failure
and citation-page accuracy. “Ask about this passage” uses the selected source
revision and preserves the draft. Original access alone is not a reader pass.
Use the updated hidden controller to upload through C's actual Attach input and
verify signatures/fixtures for the eight categories without broadening path access.

### DC09 — Project notes, goals and existing study planning

**Owner:** M6 with M2 note storage and M5 evidence. **Depends:** DC04, DC05, DC07.

Connect Notes and Goals to persistent records. Reuse study-note and existing global
study preference/plan services; add project links, note edit/revisions and simple
user-authored goals where missing. Show global defaults and explicit project
overrides clearly. Connect a goal/next activity to a chat, case or assessment and
allow manual completion/skip/edit. “Revision outline” remains ordinary file content.

**Prove:** note edit, use-in-chat, delete and restore have coherent references;
goal changes persist and affect later planning without rewriting evidence. Real
activity or explicit manual completion explains status. Global plans and ESENeph
mapping/gap information remain accessible; fixture percentages never ship.

### DC10 — Carry Library, Updates, Memory and settings into C

**Owner:** M2/M5/M7/F0 through disjoint module patches; integration owns shell.
**Depends:** DC03, DC07; reader integration DC08.

Restyle and connect existing destinations rather than replacing their domain logic.
Library keeps import/progress/retry, acquired-source discovery, source inspection,
rights/currentness, original access, filters and deletion. Updates keeps reviewed
versus detected states and source-check controls. Memory keeps inspection/edit/
delete/provenance. Preserve study preferences, model/connection selection,
retrieval settings and backup/export/restore. Wire Read/Discuss actions to readers
and contextual drafts without silently sending a prompt.

**Prove:** each existing workflow has a working C path, including failures and
empty states; saved source/revision identity survives cross-module navigation;
updates never appear current merely because their card is new. Account and
recovery status/connection controls remain accessible during interrupted assessments
and offline use; DC14/DC20 prove the active-Test export/restore policy.

### DC11 — Search chats, projects and files

**Owner:** desktop with M1/M2 query interfaces. **Depends:** DC04, DC05, DC07.

Extend the destination-only finder into scoped local search with grouped chats,
projects and file/note results. Reuse Knowledge search and canonical metadata;
add chat/project query support and explicit archived-result handling. Return
bounded/paged results with stable destination references. Preserve quick access
to destinations even when there is no indexed content.

**Prove:** title/content queries navigate to the right chat or document location;
delete/archive/move/index-failure states are accurate; rapid queries cannot show
stale results as current; temporary content never leaks. The shared policy interface
blocks snippets/caches on a denied request; DC14/DC20 prove the integrated active-Test
producer. Search itself makes no model call.

### DC12 — Saved tests, immutable versions and the Tests collection

**Owner:** M4 with coordinated storage migration. **Depends:** DC02, DC03.

Add saved test/version records separate from attempts, retaining question/key
versions, origins, review quality, source terms and provenance. Adapt existing
reviewed/generated history without regrading. Build collection, filters, legacy
resume/history, setup data and rename/archive/delete around real records. Publish
pinned version references for new-attempt setup and Retake; DC13/DC14 own their
execution and new-attempt resume wiring, so DC12 has no completion dependency on them. Offer
reviewed 1–50 only when eligible content exists; show actual selected-test length.

**Prove:** editing creates a new version; old/active attempts remain pinned;
personal/imported scores never become reviewed-bank evidence. Existing attempts
reopen faithfully, duplicate requests do not create duplicate saved tests, and
delete/restore preserves required provenance or explicit unavailable references.
Missing content, source withdrawal and Needs review have useful states.
Add local Question seems wrong records pinned to exact test/question versions
and attempts, with idempotent save and no automatic key/score/quality changes.
DC13/DC14 expose the action; its persistence and neutral confirmation are required.

### DC13 — Complete the Study attempt flow

**Owner:** M4. **Depends:** DC12; connected help completion also requires DC04
(chat), DC07/DC08 (sources/readers) and DC09 (notes). Core attempt development may
start against their contracts before these producer integrations finish.

Implement explicit Submit answer, locked feedback, Next, pause/resume, completion,
review mistakes and Retake for reviewed and personal practice. Reuse deterministic
scoring and existing assistance bookkeeping. Route every precommit hint/source/
note/chat help operation through assistance recording before returning content.
Persist selected drafts, committed responses and question position separately.
Expose local Question seems wrong and persist question/help exposure before
returning content, separately from graded learning evidence.

**Prove:** empty answers cannot submit; duplicate submit is idempotent; committed
answers cannot change; assistance survives failure/restart and is never unrecorded
after content returns. Next clears old help, exact resume works, and results/
memory evidence keep reviewed, assisted, repeat and personal practice distinct.
Viewing without answering still affects later freshness; late help from the
previous question cannot leak into the next. Reports survive restart unchanged.

### DC14 — Deliberate Test flow with final submission

**Owner:** M4 + shell policy integration. **Depends:** DC12, DC13.

Add durable editable drafts, question navigation, skip/mark/review and final
submission confirmation. Commit the attempt atomically on final submission;
return explanations/results only afterwards. Gate precommit content in backend
and frontend, including workspace, chat, search, notes, sources and old endpoints.
Support leaving/resuming with the active-Test boundary intact and submitting early.
Manual submission must durably include the latest displayed choices or wait/refuse
until pending saves resolve. Keep local reporting available with neutral feedback.

**Prove:** reload/restart preserves choices/marks/position; unanswered counts are
correct; delayed saves cannot overwrite final submission; two submit/reopen calls
do not double-score or duplicate evidence. No response, cached surface or legacy
help path exposes keys/assistance before final commit. Results/Retake are complete
and distinguish reviewed scoring from personal practice.
Probe pending-save-versus-submit, lost save acknowledgements, all listed export/
source/aggregate bypasses and late assistance after Test starts. DC14 owns the
integrated policy proof for workspace/search/notes interfaces; DC20 repeats it
against every assembled consumer. Reporting reveals no help or key.

### DC15 — Timers, pause and recovery

**Owner:** M4, platform only if needed. **Depends:** DC13, DC14.

Implement Untimed default and validated duration setup. Store start/deadline and
attempt timing state in the backend. Timed Test continues across navigation,
closure/sleep and restart; reconcile before accepting writes or revealing results.
Implement the separately labelled timed-Study rule from section 4, including
paused duration and Continue untimed. Preserve selected test/version/mode.

**Prove:** test before/at/after deadline, app sleep/closure, backend restart,
late autosave, repeated expiry/submit and clock changes; the recorded outcome is
deterministic and backend-durable drafts survive lost acknowledgements. Generation time does not
consume attempt time. Study expiry never commits an unsubmitted draft; timed Test
offers no Pause. Countdown and recovery copy agree with backend state.

### DC16 — Generate 5/10/20-question tests as recoverable work

**Owner:** M4 generation submodule. **Depends:** DC12; selected route reused.

Assemble larger sets from current validated small-batch generation. Add progress,
cancellation, cross-batch duplicate validation and recovery, with bounded provider
work and idempotent publication as a saved test version. Support Quick practice
five and explicit 10/20 setup. Keep incomplete/invalid candidates out of Ready.
Use eligible sources and fictional case inputs; retain generation provenance.
Temporary inputs cannot enter durable jobs: consume only the validated fictional
artifact from DC18's volatile transition, or an explicitly saved original context.

**Prove:** valid 5/10/20 sets publish once; malformed/duplicate/short batches do
not silently become complete; cancellation/restart preserves validated work and
does not restart billed/model work automatically. Explicitly accepting a shorter
recovered set updates every count. Route/quota/source deletion errors retain a
recoverable draft and never switch subscription or model silently.
Race cancellation against publication and return the actual durable winner.

### DC17 — Import user tests and refine without inventing certainty

**Owner:** M4 import submodule with M2 extraction. **Depends:** DC08, DC12.

Support pasted text and successfully extracted PDF, DOCX, CSV, XLSX, Markdown,
HTML/XML and PNG/JPEG/TIFF OCR text through DC08's capability contract. Preview-only
or failed extraction cannot silently become a candidate test; offer retry or paste.
Preserve the original privately with its terms and locations, extract candidate
questions, and let the selected agent normalise format. Show changes and missing/
ambiguous keys for review. Allow edit/remove/resolve and explicitly save a ready
test version. Do not use the public CC BY question-pack contract for private files.

**Prove:** questions/options/keys map back to originals; formatting does not
invent a key or reviewed status; unresolved items cannot silently be scored.
Failed refinement preserves originals and edits; retry/cancel is bounded and
idempotent. Import, original access, deletion and export/restore are verified with
synthetic private fixtures, including OCR/table input and partial extraction.

### DC18 — Create tests in chat and open the same saved test in workspace

**Owner:** M1/M4 interface; workspace adapter owner. **Depends:** DC04, DC07,
DC12, DC13, DC14, DC15 and DC16 for full attempt/setup integration. Cards can be
built earlier against those contracts.

Wire “Test this topic” and explicit chat requests to the saved-test generation
flow. Display generation state then a typed card/reference in the conversation;
open setup/preview in the workspace and list the same item under Tests. Starting
an attempt uses the shared Study/Test engine. Preserve chat and workspace context.
For temporary input, perform the section 4 transformation before crossing into
DC16's durable processing, or explicitly Save first. Do not queue raw temporary
input in a recoverable generation job.

**Prove:** one action creates one saved test; retries/navigation do not duplicate
it; collection and chat version/count/status agree. Edits preserve the original
card's pinned version or clearly offer a newer one. Deleted tests, cancelled jobs,
failed publication and temporary-input handling have accurate recovery states.
Cancel/restart before and after fictionalisation; inspect job inputs/checkpoints,
provenance, logs and saved questions for raw/identifying temporary sentinels.

### DC19 — Opt-in nightly personalised tests

**Owner:** M4 generation with M5/M6 context and bounded job pattern. **Depends:**
DC04, DC16 and DC02's eligible-input contract; reuse DC06's conventions without
waiting for its home UI. Integrate DC05/DC09 when project/goal scope is used.

Add Off/On, local preferred time and question-count settings. Schedule one bounded
app-running job per eligible day, with at most one missed-night catch-up. Use
eligible saved-session learning summaries and memory; publish a saved test once
and expose Generating/Ready/Needs review/failure in Tests. Explain app-running
behavior briefly. Turning off prevents queued runs and publication of unwanted work.

**Prove:** restart, sleep, timezone/date changes and concurrent triggers do not
duplicate a day or create a backlog; disable/cancel works mid-run; quota/auth
failure does not spin retries. Memory correction/deletion and project removal
before publication invalidate stale inputs. No temporary material, reviewed answer
keys or user-private originals are copied into distributable content.

### DC20 — Integrate, adversarially test and close migration gaps

**Owner:** integration with independent reviewers. **Depends:** DC01–DC19.

Run the coverage matrix in section 8 on populated synthetic profiles. Audit all
new records through migration/export/restore/delete and all shell surfaces for
assessment-policy bypass. Exercise broad nephrology journeys and compare actual
screens with the reconciled C references. Fix contract conflicts, stale copy,
stranded destinations and unimplemented controls. Update user/developer guides.

**Prove:** every required journey has evidence and every material review finding
is resolved/rechecked. Record remaining limitations precisely. Reuse existing
checks; add tests for new behavior and actual regression risks. No arbitrary test
count or repeated unchanged full suite substitutes for the acceptance matrix.

### DC21 — Package, validate and make C the default

**Owner:** release integrator. **Depends:** DC20.

Build the matching unsigned Windows app with bundled fonts/readers/helpers and
dependency notices. Verify upgrade from the current supported profile using
synthetic preserved state, normal close/reopen and recovery. Validate required
native/connected paths at their real scope, then perform the authorized release
handoff and launcher promotion with a compatible rollback/data-restore plan.
Remove the temporary Flow-development switch and obsolete UI after parity passes.

**Prove:** source, artifact and installed revision match; all new readers work
without developer tools; C opens by default and keeps existing data/connections.
Hidden app tests are distinguished from native dialogs, live model integration
and physical accessibility observations. Preserve existing issue #21 limitations
unless newly verified; do not claim a clean-machine or signed-release pass.

## 7. Parallel delivery and ownership

| Wave | Work that can progress together | Integration milestone |
| --- | --- | --- |
| A | DC01 design reconciliation; DC02 contracts/migration | Agreed screen map and stable shared meanings |
| B | DC03 shell; then DC04 conversations, DC05 projects, DC07 workspace and DC12 tests on the frozen contracts | Real C chat/history, scoped projects and resumable existing work |
| C | DC06 home/cache work; DC08 readers; DC09 goals/notes; DC10 destination migration; DC11 search; M4 develops DC13 then DC14 | Daily learning/source reading; connected help gates DC13 completion |
| D | DC15 timing; DC16 generation; DC17 imports; then complete DC06 Quick practice, DC18 chat tests and DC19 nightly | All accepted C capabilities connected |
| E | DC20 adversarial integration/recovery; DC21 matching Windows delivery | C becomes the supported default |

Dependency lines on tickets govern readiness, even within one wave. DC09 waits
for its project/workspace prerequisites; DC18 waits for saved tests and generation.
DC06 starts in C but closes only after the DC13/DC16 Quick practice integration.
DC18 also waits for the shared attempt/timing producers. DC01/DC02 are explicit
prerequisites, not claims that feature work has already passed integration.
Parallel writers own disjoint modules/files. One integrator owns shell routing,
shared UI/tokens, root manifests/locks and migration sequencing. Within M4, reserve
attempt, generation and import paths explicitly before parallel work; never send
several agents to rewrite the same repository/router file.

Use `codex/` worktree branches and distinct synthetic profiles. Each handoff gives
changed paths, contract/version changes, prerequisite commits, evidence and
remaining limits. The integrator exercises the combined user journey after merge.
Agents may split a large ticket or combine tiny patches while preserving its
outcome/acceptance; update dependencies here rather than spawning competing plans.

## 8. Completion and review loop

| Journey/check | Required evidence |
| --- | --- |
| First run and offline | New chat greeting/actions work; connections reachable; local history, documents and reviewed tests remain usable. |
| Chat and projects | New chat → attach → ask → stop/retry → switch project → reopen → archive/restore; explicit temporary sentinel never persists. |
| Reading and knowledge | All eight categories read inside the workspace. Eligible, successfully extracted fixtures complete passage → draft → answer/source jump; OCR failures, missing locators and restricted/preview-only inputs have truthful states. Permissions, deletion and revision replacement are honored. |
| Learning organisation | Notes/goals/global plan edits persist and actual activity explains progress; memory edit/delete affects later personalisation. |
| Tests | All four origins → setup → Study/help/submit/Next or Test/draft/mark/review/final → results/mistakes/Retake. Local question reporting persists without revealing help or changing scores; results/history remain separated. |
| Timing/recovery | Untimed Study pause/resume; untimed Test saved resume without pausing; timed Study and timed Test close/sleep/expiry; unsaved/late requests, duplicate actions and exact resume. |
| Background jobs | Daily suggestions/nightly tests deduplicate, cancel, recover and honour deletion/disable/route state. |
| Migration and data | Old populated profile upgrade, interrupted writes/migrations, export/restore and deletion including originals, references and derived indexes. |
| Visual/accessibility | 1440×900, 1000×720, 640×540 and 200% zoom; pane-aware layout, keyboard navigation, focus return, contrast, long text, reduced motion and high-contrast behavior. |
| Delivery | Bundled readers/runtime, normal lifecycle, matching source/install, useful error paths and scoped native/live acceptance. |

Use synthetic fixtures across CKD, dialysis, transplantation, glomerular disease
and electrolyte topics. Reuse the controlled app/Playwright path; extend its
synthetic upload contract for new formats instead of using shared desktop input.
Update readiness and observed input labels alongside the C shell; format allowlists
alone do not make the current controller recognize a new Attach control.
Do not test against the owner's account/profile or call live providers incidentally.

For implementation, run three focused review passes:

1. **Before parallel coding:** challenge contract/data ownership, screen coverage,
   unsupported capability assumptions and dependencies. Fix the plan first.
2. **After connected slices:** independent reviewers attempt real UX/data/assessment
   failures; owners fix material findings with reproductions and evidence.
3. **Before default cutover:** fresh review of the integrated migration and release
   journeys; recheck fixes and stop when requirements pass. New evidence warrants
   more review; repeated unchanged approval runs do not.

Close a ticket when its real user outcome, relevant automated checks and visual/
integration evidence pass. Close the overall migration only when all required
tickets pass and C is the matching default Windows app. Record omissions as open
work, never as completed prototype functionality.

## 9. Spec review record

Completed October 10, 2026. The parent inspected the live C screen inventory,
representative workspace/reader pixels and current product/planning records.
Four subagents contributed across these bounded passes:

| Pass | Review scope | Outcome |
| --- | --- | --- |
| 1 — Source audit | Three parallel agents: conversation/project/data; assessment; desktop/readers/release | Established actual reuse, missing capabilities and migration/security seams. Findings incorporated before the draft challenge. |
| 2 — Adversarial draft | Those three scopes plus a fresh cross-ticket/requirements reviewer | Data lifecycle passed; material assessment, reader and coordination findings required revision. |
| 3 — Corrected-version recheck | Assessment, desktop/readers and cross-ticket reviewers reread the corrected spec | All prior findings resolved within their reviewed scopes; no new material contradictions. Cross-ticket reviewer confirmed the stated completion graph is acyclic. |

| Material finding | Recorded resolution |
| --- | --- |
| Old Case default, shared-document deletion and exact-column backups could lose or misclassify data | Separate kind/retention/lifecycle, typed ownership, attachment tombstones and explicit old-export conversion in section 4/DC02/DC04/DC05. |
| Required local question reporting was absent | Version/attempt-pinned Question seems wrong in section 4/DC12–DC14 and the completion matrix. |
| Final submission could overtake the displayed choice; exposure could be delayed incorrectly | Latest-choice durability for manual submission, backend-durable expiry authority and separate presentation/help exposure versus graded evidence. |
| Temporary derivatives were both prohibited and needed for fictional tests | Volatile transformation before a validated fictional artifact crosses into durable jobs/tests; DC04/DC16/DC18 share this boundary. |
| Inert documents could still acquire same-origin authenticated API authority | Explicit host-mediated retrieval, isolation and negative API/navigation fixtures; F0/M2 ownership in DC08. |
| Reader support was confused with universal OCR/model usability | Per-format reading/extraction/model-use contract, DC08 adapter ownership, declared DC17 inputs and conditional passage acceptance. |
| Hidden controller assumed Flow landmarks and upload labels | Readiness/input/fixture prerequisites in DC03/DC08 with collapsed/narrow startup and real Attach checks. |
| Prerequisites and consumers had circular or missing completion gates | DC01/DC02 readiness exceptions, policy-interface proof separated from integrated enforcement, explicit DC06/DC13/DC18 gates and independent DC19 scheduling. |
| Proposed workspace/search behavior looked user-confirmed | Adopted planning-default labels retain engineering flexibility and distinguish confirmed requirements. |

No material spec finding remains open from these reviews. This is a planning
result: all DC tickets remain Not started. Figma and product code were inspected;
this pass changed documentation only. App tests, model calls, implementation,
installation and release acceptance were not performed by this planning pass.
`git diff --check` and the repository's workspace/local-link check passed.

## 10. Implementation execution — October 10, 2026

DC11 engineering clarification: the local finder searches canonical saved chat
titles/messages, project titles and existing Knowledge passage/metadata rows.
It provides literal text matching, explicit project scope and archived inclusion,
typed pinned destinations, bounded keyset pages and restore-generation refusal.
This works offline without starting an embedding/model job and preserves file
title discovery when indexing fails. It does not imply semantic retrieval for
unindexed files; existing Knowledge model retrieval keeps its separate eligibility
authority. Two real assembled-router search checks and twelve affected renderer
checks passed, including query races and immediate active-Test snippet removal.
Reader navigation still requires its actual source adapter integration.

Pass 1 reviewed contract validators (`527677f3`) and the three independent
reports. Accepted additive implementation clarifications: versions retain a
versioned provenance JSON; collection mutation commands have their own request
fingerprint/outcome ledger; reports keep an independent question snapshot and
request hash. Stable legacy mapping uses exact kind/session pins, deterministic
IDs and tombstone refusal, without rewriting legacy sessions or partial scores.
Attempts keep frozen Study commitments separate from drafts, immutable terminal
results, clock high-water and paused-at state. Goals store explicit completion/
evidence state, rather than deriving progress from chat counts. Recoverable jobs
retain original requested count and a separate deliberate shorter-set acceptance
count. These additions repair persistence gaps found before dependent coding;
they do not alter confirmed Study/Test/retention meanings.

Accepted persistence clarification: saved chat, project and whole-attempt
commands each need a separate durable hash/outcome ledger, with the same exact
columns as collection commands and no live-target foreign key. This supplies
the existing retry/conflict contract without mixing writers or retaining
temporary payloads. The lead owns their additive DDL and recovery inclusion.
Profile-wide policy uses a local generation checked before replay and again
before publication; start/finalisation changes it atomically. Local policy and
context generations are excluded from canonical exports.

Exact feature leases are in the execution record. Reader, saved-collection and
attempt implementation may start against these contracts while lead-owned
additive migrations are finalised. DC01/DC02 and all feature tickets remain
open until their required evidence and connected producers/consumers pass.

The owner authorised implementation, local commits and matching Windows delivery
after the documentation baseline `528025ff`. The clean canonical checkout started
there; `codex/design-c-integration` is the integration branch. Initial lane
reservations and shared baseline `1b30a896` are in
[the execution record](../implementation/EXECUTION.md#active-reservations--initial-prerequisite-wave).
This table records outcomes against the existing tickets, not a replacement plan.

| Ticket | Current status / owner | Prerequisite and evidence / remaining gate |
| --- | --- | --- |
| DC01 | Design prerequisite passed — design worker + lead | `fbdb99eb` reconciles editable C copy, 480px workspace, narrow/200% compositions and operational states. Lead reviewed representative pixels; connected code acceptance remains with feature owners. |
| DC02 | Foundation and populated integration passed — lead | Contracts `17f5d6a4`, additive schema inventory, typed recovery and exact schema-1 conversion are integrated. `1744e2cb` adds eight passing old/current populated upgrade and JSON/ZIP1/ZIP2 checks using committed old producers. Final installed upgrade remains DC21. |
| DC03 | In progress — lead | C shell, typed navigation/volatile handoffs, hidden narrow/zoom controller integrated. Full keyboard/focus/zoom and default-delivery matrix remains open. |
| DC04 | Connected slices integrated — Zeno + lead; acceptance open | Saved lifecycle, Case context/handoffs and Study receipts integrated. M2 promotion `d1b5f8a2`, guarded Case images `c4b5f1df`, Save navigation repair `08d9272f`; actual owner/rollback/replay coverage and hidden saved Attach/reopen pass. Hidden successful image/Create Test combined journeys remain open. |
| DC05 | Connected organisation/recovery passed at source scope — Zeno/M2 + lead | Project CRUD/goals/shared documents and typed unlink integrated. `e56b75de` proves real populated Library/LanceDB scoped Chat, move and late unlink refusal; `b0bcb40d` transfers note revision memberships. Notes HTTP `dc59d4c2`, populated recovery `1744e2cb` and hidden organisation/source reopen `02906c12` cover the combined source seam. Matching delivery remains open. |
| DC06 | Connected consumers/review passed at source scope — Kant + lead | Actual Home → trusted saved-five → whole Study/lost ACK and File → saved Chat review → original/reopen integrated. `434dc41a` draft retention independently rechecked in `02906c12`. C2 `a14e06a9` has 131 Home/Nightly checks, including actual Home consumer; matching delivery remains open. |
| DC07 | Connected workspace/review passed at source scope — Aquinas + lead | Typed tabs/480px/narrow focus and canonical preferences integrated. `02906c12` confirms normal CSV position reopen. R5 `f5d36ac9` adds authorized volatile titles and distinct close names; eight API/28 renderer checks and independent hidden two-file/restart proof `31e9e4ce` pass. Initial recovered Reader timeout remains qualified; matching delivery is open. |
| DC08 | Connected reader/attachment slices integrated — Poincare + lead; acceptance open | Grid/Study/original/Files owners integrated. R7 page/sheet/row `728555e2` and PDF text selection `f4fc986f` preserve positions; actual loopback/SQLite page-2 selection reopen and 40 Reader/Workspace checks pass. Matching installed eight-format matrix remains open. |
| DC09 | Connected organisation and source review passed — lead + owners | Projects, goals, note membership, Notes editor/revisions and scalar whole-attempt progress integrated. `dc59d4c2` adds 20 unique mounted HTTP/Study-help/rights/race/ZIP checks; `02906c12` independently exercises progress, Notes→Chat/source/reopen. Matching delivery remains open. |
| DC10 | Retained destinations passed at source scope — owners/Aquinas + lead | `bc149c91` records hidden actual Memory/Updates empty states, active-Test content removal, neutral Connections/Preferences and keyboard/200% recovery; normal close has no remaining processes. The source/driver qualifications and unattributed console entries remain in the report. Current storage/Memory/Notes recovery scopes are linked separately. Matching delivery remains open. |
| DC11 | Connected navigation review passed at source scope — lead/Poincare | Canonical literal finder `1b7d2256`; `527bd253` fixes current-chat membership refresh without losing draft/stream, eleven Chat checks plus typecheck pass. `21f422b6` independently passes three actual App/HTTP/SQLite journeys after source deletion/project reassignment, including currently mounted chat; earlier immutable citations remain pinned. The assembled active-Test inventory covers search refusal. Matching delivery remains open. |
| DC12 | Connected slice integrated — Pauli + lead; acceptance open | Saved collection/version setup and exact legacy history integrated. C1 `1b12c19f` preserves independent native report provenance; `2bc84d61` independently rechecks actual import/fictional pins after delete/restore. R4 cold setup styling `6b56c66a` and hidden recheck `a47a3f03` pass. Matching delivery remains open. |
| DC13 | Connected Study/help review passed at source scope — Russell + lead | Whole Study owner/renderer and scalar evidence helper `2e71ba1a` integrated; actual saved practice to Study replay `6cdf0d35`. Notes `dc59d4c2`, Reader/Chat receipt guards and hidden Study/Notes/source journeys `02906c12`/`4316fde0` close the previously listed consumer gap. Matching delivery remains open. |
| DC14 | Final source policy review passed — Russell + lead | `eef19e63` fences legacy generated-practice publication/replay and `dbd1896e` fences volatile Case terminal replay. Actual red reproductions retained; 41 distinct focused checks pass across receipts, three original-producer checks rerun after final fix. `c6ec9717` inventories 272 method/path pairs: 229 guarded, 31 neutral, 12 attempt-owned; actual Test rejects ordinary paths and valid historical replays while current Test remains key-free. Retained legacy full-app suite passes 21 checks. Matching delivery remains open. |
| DC15 | Connected timing integrated — Russell + lead; acceptance open | Actual timer/high-water/Study pause/recovery integrated. Hidden c3 exercised assisted Study pause/reopen/final and one-minute Test normal restart/expiry to 1/5 with four unanswered; wide/narrow/200% results inspected. `4316fde0` indexes actual receipt/readonly audit; broader matching-delivery timing gates remain open. |
| DC16 | Connected producer/Study review passed at source scope — Pauli + lead | Backend `dd1f7c12`, restore `037b895d`, renderer `520c538c`: 36 actual DB and three real-router UI journeys. `71814442` proves actual mounted App Generation → Ready/exact saved setup → whole Study five commitments, with actual HTTP/SQLite/selected ProviderManager synthetic transport. Matching installed evidence remains open. |
| DC17 | Connected paste/Library slice integrated — Pauli + lead; acceptance open | Actual text/CSV/CPU OCR extraction, strict normalization, original/candidate editing, personal publication and whole Test consumer covered (32 backend/six renderer before C4). `a2a5f2d4` fixes current source authority before Save replay, 35 actual checks. Hidden original → edited personal set → Test restart/report/final 2/2 passed. R9 copy `f1228182` passes actual loopback; delivery remains open. |
| DC18 | Connected producer/consumers passed at source scope — Zeno/Kant/Pauli + lead | Trusted volatile fictionalisation/separate review/publisher, Chat Create Test and actual Home exact-five → whole Study/lost ACK consumers integrated. 5/10/20 producer proof retained. `71814442` proves actual mounted saved Chat stream → fictional set/privacy review → pinned card/Workspace exact version → stable-key whole Study with five commitments and no duplicate start. Source/jsdom proof is qualified; matching installed evidence remains open. |
| DC19 | Connected scheduler, UI and attempt consumers passed at source scope — Kant/Pauli + lead | Hidden preference/Tests/restart/narrow/200% evidence retained. `16420819` proves actual scheduler → saved-five/both setup APIs → whole Study/help/end → timed Test/draft/submit, lost ACK replay and neutral Off/Stop; full 44 checks pass. Matching delivery remains open. |
| DC20 | Final integration review in progress — lead + independent reviewers | C1/C2/C4 independently rechecked; C3 `51f208b4` plus C5 `7cdc3fec`/`009b8780` prevent restored inference. C5 affected regression passes 91 checks, with separate actual HTTP retry/capture proof `760f4b0b`; the earlier 17 focused checks overlap. R3–R10 review `02906c12`, Notes `dc59d4c2`, PDF text `f4fc986f` and hidden R5 `31e9e4ce` are integrated. `1744e2cb` populated source eight-pass scope retained; matching release checks remain open. |
| DC21 | Matching installed acceptance in progress — release lead + Zeno/Pauli | Exact `4c289868` manufacture and silent installation pass, with complete 39,353-file backend inventory and matching installer/EXE/ASAR hashes. Actual core admission, hidden startup and saved chats/projects pass. Installed recovery `r-179af503` passes nine upgrade/current-producer/three-format restore/deletion gates with effective public engine rebuilds; its old seed has empty conversation histories, so a stronger genuine seed and fresh Electron transcript reopen remain required. Core06 preserves an exact retryable Reader 409 with original bytes intact. QA `f43af3f8` permits one recorded visible Try again; `e5a2be83` refuses empty-history seeds. Latest bounded guards: 75 JS, seven original/parser and 26 recovery checks; these are not installed acceptance. All eight readers, normal ingestion/lifecycle and fresh-process upgraded-history proof remain open. See `design-c-delivery.md` for preserved failures. Flow remains selected until matching actual evidence passes. |

DC21 acceptance-tool clarification: product source, renderer/native/backend and
installed artifact remain pinned to one exact revision. A later acceptance-tool
revision may be pinned separately when it changes only the bounded JavaScript
installed-product verifier/test, Python installed-recovery verifier/test and
Markdown documentation; any product/dependency/build change refuses that
reuse. Both revisions and executed driver hashes must be recorded. This permits
repairing a harness assumption without rebuilding unchanged product bytes.
The first installed preflight compared raw Git blobs to Git's exported Windows
PowerShell line endings. An independent exact Git archive comparison proved
all 5,840 admitted source files (79,611,627 bytes) match the installed candidate.
The failed receipt is retained and establishes no app launch or reader pass.
The corrected verifier must honor only declared frozen export transformations,
not normalize arbitrary installed differences or skip source checks.
The copied recovery driver is hash-bound to the acceptance revision independently
of the product/bundle/Python hashes. Its original-availability expectations must
be frozen from the preserved old seed and hash-checked archive manifests before
upgrade: a records-only old row is not a lost original, while every declared
present or newly produced original still requires exact bytes and hash. The
first installed recovery failure remains recorded; no target-derived skip may
turn a newly missing original into expected absence.

DC17 implementation clarification: one assessment_test_imports table owns the
explicitly accepted pasted/extracted private original, SHA-256, terms/locators,
mutable candidates and three-call explicit normalization budget. Library and
published-version pins are historical IDs with separate nullable live pointers;
neither is a pruning edge. Assessment005 is additive, included in the known
migration gate, and restore interrupts running imports without resuming provider
work. Existing assessment_test_commands supplies mutation replay outcomes under
target_type=test_import. Literal Answer/Key markers supply initial candidates;
normalization cannot invent certainty, and every retained item needs deliberate
user review before personal Ready publication. No reviewed-bank status is granted.

DC18 producer reservation: the lead owns assessment/fictionalisation.py and the
private saved_generation.publish_fictional_artifact method. Zeno owns new
learn/chat_test_models.py, chat_test_service.py and chat_test_api.py plus their
integration test and existing Chat callers. Source text, request IDs/hashes and
events remain volatile for saved and temporary chats alike. The selected route
transforms in batches of five, then independently reviews the complete proposed
artifact against raw source in a separate volatile call. Conservative identifying
overlap refusal supplements that review. Only the exact process-minted artifact
with a live validation receipt may be published, with policy/context/route checked
again in the publication transaction. Durable keys derive fresh artifact receipts,
never source/request identity. This adds no renderer attestation or new provider.

Pass 1 has reproduced material recovery failures and is reviewing assessment and
reader seams. Fixes use one typed whole-row identity (table plus full PK tuple),
declared owned/drop-link edges and exact historical tombstone aliases. Unknown
types remain in the ledger without deleting another namespace. History links
with unavailable-source semantics are not drop-link edges: new attempts/reports/
job outcomes must retain independently pinned immutable provenance or referenced
versions when collection entries disappear.

Engineering clarification: new domain records use additive sidecars rather than
adding fields to original Learn/Cases/assessment rows. This preserves their
column meanings and makes schema-1 conversion explicit. Any necessary added
legacy field requires an exact reviewed default in the compatibility adapter;
unknown shapes are refused. JSON and both supported ZIP formats verify source
bytes before conversion. A schema and known-migration inventory gate prevents
older/unrecognised runtimes from writing newer profiles.

Restore also invalidates Memory and Library derived readiness in the canonical
transaction and advances a local, non-exported context generation. DC06/DC19
publishers must check that generation, as well as input revisions, so a restore
cannot publish stale personalisation. Recovery does not start provider work.
Pass-3 C5 clarified the delayed-worker boundary: the restore transaction marks
every restored/pre-existing evidence identity with a local, non-exported capture
barrier, including sources without a historical job. Automatic inferred Memory
capture and global Retry cannot consume it. Explicit Capture revalidates the
canonical source, scope, suppression and current policy, then consumes that one
barrier atomically with enqueue. Structured `infer=False` capture and new learning
after restore retain their existing behavior. A recorded eligible cancelled job
offers Capture this learning; no synthetic job or discovery UI is invented for
no-history sources. This preserves the no-provider-restart rule after the restore
returns, not just during its transaction.
DC04 additionally requires a real `case_attachment` tombstone when an attachment
is removed from a saved case; merely removing its current row allows an older
backup to restore the bytes. These are implementation prerequisites, not passes
for feature tickets.

Nightly planning defaults are 22:00 local time and five questions, always Off
until explicit opt-in. The safe preference is only enabled/local_time/
question_count/revision; receipt journals and scheduling tokens stay local.
Recovery advances the local generation and explicitly interrupts foreign queued/
running producers even when their integer epoch coincides with the destination.
Validated checkpoints remain available for deliberate retry; restore does not
restart provider work. These are engineering safety clarifications, not changes
to the confirmed app-running/bounded-catch-up requirement.

Attachment cleanup clarification: M2 removes owned rows and emits typed
attachment/original tombstones inside the caller's canonical deletion transaction.
`storage.attachment_cleanup.enqueue_in(conn, plan)` journals exact attachment IDs
and owned relative directories there; `drain(services)` performs file work after
commit and at startup. Live rows and unsafe paths refuse cleanup; locked/failed
work remains journalled for retry. This local journal is excluded from export.
Planning bounds are 200 entries per deletion and 1000 pending entries; exceeding
them refuses the mutation rather than dropping cleanup. This prevents premature
file deletion on rollback and lost cleanup after a process exit. The actual
producer/caller journey must pass before attachment deletion acceptance.

Nightly's reusable status is mounted in Tests, with its preference action opening
the existing Settings preferences section. Retained jobs open the existing
GenerationPanel and published jobs select the exact immutable saved version. This
adapts the separate prototype page to the established shell without duplicating
settings authority or adding a Generate-now action. Lead inspected Figma Off
`83:7590`; the approved 22:00/five defaults and future-only recovery boundary
override its illustrative 21:00 and reopen copy.
