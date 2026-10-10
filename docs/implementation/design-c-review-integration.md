# Design C independent integration review — October 10, 2026

The latest bounded pass reviews committed `84be584e` plus the actual Tests Import
mount `0d10e5df` and Home Attach label fix `319ff190`, built in this lane at
`f69f6792`. Actual Import review/publication, Study-to-Chat preparation, saved
Chat attachment/CSV preview and Untimed Test final submission work at their
recorded scope. Ten production learning-route probes refuse access during the
UI-started Test, and eight focused Study-help guard tests pass. Material open
findings are reviewed progress omission (R8, P1), Home draft loss on a policy
change without navigation (R3, P2), reader row-position loss on restart (R7,
P2), and saved Chat attachments missing from Workspace Files (R10, P2).
R9 records misleading edited-key copy. Notes creation and receipt propagation
into Reader remain specific consumer gates. The same-baseline hidden follow-up
below reconfirms R4 preview styles and R6 transient error feedback; R5 retains
its earlier qualification. The resolved R1/R2 probes were not repeated.
Figma Test timing copy is reconciled across ten existing C specimens with
verified screenshots. Timed lifecycle, other media/extraction paths and Windows
delivery remain outside this pass's acceptance. This report closes no ticket.

## Latest bounded pass — 84 baseline and connected Import mount

The exact-root check returned `C:/Renulus/dev/worktrees/dc01-design` and the
branch remained `codex/dc01-design`. A clean normal merge of `84be584e` produced
`30e683cca1176bfe32c933f601f2c7d005399f6a`. The subsequent clean merge of the two
published mount/label commits produced
`f69f6792247dc871d96e42b413d6622883f5b1fa`. There were no conflicts, resets,
checkouts or unowned flag changes. Canonical was read only. This pass authors
only this reserved report; `fc732598` already commits the Figma timing report,
and `8b7944e7` remains the separate six-path Workspace follow-up listed below.

The installed interface-design-review and Impeccable audit skills were applied
to the calm medical Operate surface, actual pixels, keyboard behavior and
truthful states. No UI repair or shared source edit was performed. Desktop
TypeScript, Vite with the runner config loader and native build all passed.
The source/build/controller/screenshot manifest is
`C:/Renulus/scratch/dcctl/rev1/probes/pass2-evidence-84-f69f6792.json`.
Renderer `index-D14ovzRE.js` SHA-256 is
`4ef38a5511eff31deb5e816640a718029b7dcd870a269a8b576ac1e3069183ed`;
native main SHA-256 is
`c4b3e337fa58ee3e2754ffbf2d485cc74d0421db6a7d339ed36f3a5cc223d615`.

The fresh fixed CLI controller used only
`C:/Renulus/scratch/dcctl/rev1/c/s-60e257ce/p`. Its synthetic fixture manifest
declares original Markdown and CSV bytes under `rev1/fixtures-pass2-84`.
Three launches ended with three normal closes, including one controller
operation-failure cleanup, one requested restart and final requested close at
06:47:05.372 UTC on October 10, 2026. Every forced/remaining PID list is empty;
fault is null. Nineteen PNGs remain under `c/s-60e257ce/out` and are hashed in
the manifest. No owner profile, credential, foreground input or live provider
was used. The delayed provider in the guard tests is synthetic.

### Connected journeys and visual evidence

| Actual flow | Result and representative evidence |
| --- | --- |
| Tests → Import a test → Save private original | Original synthetic two-question text and retained terms saved through the mounted panel; two source-mapped candidates, zero normalization requests. `capture-0001.png` shows original alongside the editor. |
| Edit and review → explicit publication | Saving a personal explanation clears answer/review confirmation. Re-selecting the key and confirming both questions enables Save. Open saved test selects the exact `import_version_import_1aadb1f0a6c0fc24b8fdb13269859a88`, Version 1, Imported/Personal/Ready. This is an actual UI flow, not a seeded or mocked page. |
| Narrow/zoom Import editor | At 1000×900 outer, 984×861 content and native 200% zoom, the editor stacks into a single column. Tab from question text reaches the answer checkbox with visible focus (`0002`). The immutable original moves below the editor; no horizontal clipping was observed in this bounded composition. |
| Study → Notes | Assistance is recorded and the real shell opens Notes. The pane contains no note creation path, only its empty state and Open Library (`0003`). See G1. |
| Study → Ask in chat | A saved learning conversation is created, with only the public question/options prefilled and its draft saved (`0004`). No key/explanation is inserted. Send was not exercised; provider response acceptance is not claimed. |
| Chat Attach → permissions → Open file | Actual controller upload of the declared 5,947-byte CSV, Display/Keep-local confirmation and attachment publication succeed. The retained original SHA-256 matches `a563865763fcaf67c584cb12b053ca24ee68667755e2438da6f1e8ff13a9110f`. Its real reader renders rows 1–100 of 206 (`0005`). Model-input/derivation permissions stayed false; passage discussion is truthfully unavailable. |
| CSV at native 200% zoom | Next rows opens 101–200. A focused single Workspace pane, Back to chat and visible table focus remain usable (`0006`). Normal restart restores the safe saved tab but resets rows to 1–100 (`0007`). See R7. |
| Imported Untimed Test | The actual saved version starts Test, retains a selected wrong choice, restricts Home (`0008`/`0009`), and exposes no Pause action. At native 200% zoom, Shift+Tab from Keep working reaches Submit test with visible focus (`0011`); Enter commits the final result. Results correctly show personal 0/2 and one unanswered (`0012`). |
| Reviewed-bank Study | A separate one-question reviewed set is created through Tests, its answer committed through Study and its summary shows fresh 1/1 (`0013`). The commitment resolver validates this new answer, while progress still omits it. See R8. |
| Home policy transition without navigation | The same Home route holds an unsent draft (`0017`). Real attempt-start HTTP activates restriction (`0018`); real final-submit HTTP releases it, with no navigation or restart. Home returns with an empty composer (`0019`). See R3. |

The narrow tests establish rendered composition and the named keyboard actions,
not pointer drag, physical Windows scaling/high contrast or a general focus
audit. Files/Notes inventories and original integrity were independently read
through production HTTP/SQLite. UI-established data was not replaced by fixture
rows. The separate Home policy probe uses production attempt start/submit on the
same UI-published version; it is not another UI-start acceptance claim.

### Current material findings

**R8 — P1, current progress omits a valid reviewed commitment.** Reproduction:
create `DC01 84 reviewed progress check` with one reviewed question, Continue to
Study, Start Study, select an answer, Submit answer, then Finish study. The
actual summary is fresh 1/1. Fresh `GET /study/progress` returns all-zero groups
and no topics. `progress-84-existing-ui-c90b2853.json` contains the current
production route response and commitment-owner validation of this bank-eligible
answer; the personal Imported Test answer is separately ineligible for bank
scoring. `runtime/renulus/study/service.py:89` and `:157` still filter only
`assessment-answer`. The Study owner should consume the validated whole-attempt
metadata for progress/mistake scheduling while preserving origin, cohort,
assistance, repeat and deletion eligibility. This pass narrows the earlier
finding: the current Memory material adapter successfully resolves the answered
personal and reviewed commitments, with the correct distinct scopes. No enqueue
or memory inference was performed. Home's new consumer has source/parent test
evidence, not new model-powered acceptance here. The older broad Memory impact
statement below is historical and superseded at this adapter scope.

**R3 — P2, current policy-only transition loses the Home draft.** The isolated
repro keeps the renderer on New chat throughout: type the `0017` draft, use
`start-84-home-test.py start` to start the actual saved Imported version, wait
for Resume Test, then use `start-84-home-test.py submit` to finalize it. Request
receipts are `start-84-home-test-0a547d96.json` (201, policy 6) and
`start-84-home-test-25c0d452.json` (200, policy 7). `0019` and the fresh ARIA
snapshot show an empty composer and disabled Send. No navigation occurred in
this isolating reproduction. Keep volatile Home draft ownership above the
revoked surface and restore it after policy release. This rechecks actual draft
loss; the earlier component observation about DOM focus remains qualified.
Native activeElement/recovery-focus behavior was not measured here. The first
`0014`–`0016` sequence also navigated to the attempt; it is not the isolating
proof and should not be used to attribute loss solely to policy.

**R7 — P2, current attachment reader ignores persisted position.** Open the
actual saved Chat CSV, Next rows to 101–200, restart normally, reopen Study
question, Workspace and the restored Attachment tab. The reader returns to
rows 1–100 (`0006` → `0007`). Fresh preferences contain the correct saved
attachment/context reference but `position: null`. The receipt is
`read-84-before-restart-e5a986e4.json`. ReaderSession at
`apps/desktop/src/modules/reader/Reader.tsx:59` still omits `position` and
`onPositionChange` from its props. The reader owner must hydrate/report safe
table/page locators through the existing Workspace seam. This current recheck
is CSV-specific; the three-page PDF reset remains the earlier 873 observation.

**R10 — P2, Workspace Files omits a saved Chat attachment.** In the same saved
Chat, Attach file → upload CSV → confirm rights → Open file works. Switch the
Workspace to Files: it says “No files in this context yet” and offers Open
Library. Fresh `/workspace/entries?section=Files&context_type=learn_thread&context_id=…`
returns `items: []`, while the production attachment inventory contains
`attachment_fccfdb9384314d57840e8595186836ae` with the matching original hash.
Both responses are in `read-84-before-restart-e5a986e4.json` and
`read-84-final-test-7b19620f.json`. `storage/workspace.py` enumerates Knowledge
revisions but does not consume the saved conversation attachment inventory.
The parent inventory adapter should merge the authorized saved attachment
references for this exact Chat, without exposing temporary or another owner's
files. Open file in Chat is the available workaround. Successful Chat inventory
and reader delivery do not resolve this separate Files consumer gap.

**R9 — P2, an edit is described as uncertainty in the original.** After saving
only a personal explanation on question 1, the panel clears the key/review and
says “The original supplies no clear answer,” alongside the unchanged original
`Answer: A`. Actual before/after-restart snapshots confirmed the contradictory
copy before re-resolution. Clearing review after an edit is appropriate; the
message should say the edit requires the answer to be selected and confirmed
again. `CandidateEditor.tsx` already receives the `edited` flag and retained
original supplied keys, so this is a consumer copy correction rather than a
schema change. Evidence is the actual tool snapshots, not a dedicated error
screenshot. An early attempted Confirm without re-selecting the cleared key
timed out and triggered normal controller cleanup; that is an operator mistake,
not an application crash. The saved explanation/original survived restart.

R4's route-dependent Test preview styling, R5's ambiguous reader-tab names and
R6's disappearing unavailable-hint error were not independently rerun in this
bounded pass. Their previously recorded reproductions remain open. This pass's
single generic Attachment tab does not establish a new duplicate-name repro.
No stale graph/invalidation finding is being reopened by those qualifications.

### Guard evidence and exact consumer gates

`policy-84-732113e4.json` probes the actual UI-started Imported Test using the
production API/SQLite without lifespan. Conversations, Workspace preferences,
entries, saved search, import inventory/draft/original, attachment inventory,
Workspace authorization and reader resolution all return 409
`assistance_restricted`. There is no direct synthetic active-policy row fixture.
Existing `tests/integration/test_design_c_study_help.py` passes 8/8 in 30.18
seconds under the owned scratch test root. These cover current/forged receipts,
stale draft revision, same-transaction rollback, detached late publication and
actual Chat HTTP with a delayed synthetic provider. The actual Chat refuses
the stale assistant, records neutral interruption and retains its draft. This
is focused backend contract evidence, separate from live subscription use.

| Gate | Exact remaining producer/consumer work |
| --- | --- |
| G1 — Notes creation, open | Study produces a recorded Notes receipt and shell opens Notes, but the current adapter is an inventory with no editor/create action. Connect question-scoped note creation using the canonical receipt, safe provenance and current revision/policy validation; prove retained note reopening without counting mere pane opening as completion. |
| G2 — Reader Study receipt, source-inspected gate | Shell StudyReader injects `studyHelpContext`. ReaderSession ignores it, external `signal` and injected policy, and its resolve/passage/original/asset calls do not send `studyHelpHeaders`. Wire the existing receipt/abort seam and prove that item/draft/policy change suppresses late source/passage handoff. The backend guard works when the header is present. This source gap is not a demonstrated global Test bypass; all ten Test probes refuse access. |
| Import media/normalization, open | This pass proves pasted deterministic candidates and saved CSV preview. Library extraction eligibility, PDF/DOCX/XLSX/HTML/XML/OCR imports, incomplete extraction, normalization retry/cancel, deletion/restore and native chooser behavior need their own connected checks. No provider normalization was dispatched. |
| Timed lifecycle, open | Untimed final submission passed. Timed Test close/sleep/expiry, timed Study pause/continue, ambiguous acknowledgement and concurrent preference writes remain unaccepted by this pass. |
| Delivery and full surface coverage, open | This build is the lane's committed source app. Windows installation/dialogs, physical scaling/high contrast, remaining project/settings journeys and matching default Windows delivery remain separate gates. |

Earlier broader design reconciliation remains in `design-c-reconciliation.md`.
The Test setup correction at Figma `81:5381` was re-inspected from its saved
native final PNG during this pass; it explicitly says Test cannot be paused.
No further Figma change or full-page metadata request was necessary.
This report recommends exact owner actions and records evidence; it does not
implement shared paths or change feature-ticket disposition.

## Same-baseline hidden UX follow-up and coverage — October 10, 2026

Canonical was exactly `319ff190610d6b6ff1a5f44f2e65aa5620a7f7c6`; the clean
lane was `ab941c18`, with this canonical commit already merged. Only the report
differs from the previously built `f69f6792` source. Renderer/native hashes match
the prior pass. No rebuild, shared source change or Figma rewrite was needed.
The installed interface-design review and Impeccable audit guidance continued
to govern hierarchy, readable state copy and the bounded keyboard/zoom checks.

The fresh owned profile was `C:/Renulus/scratch/dcctl/rev1/c/s-59e2b4de/p`.
The fixed controller client was operated through file-backed strict tool
requests, without caller evaluation, OS input or foreground windows. All 51
requests succeeded. Five native captures, request/results and source hashes are
listed in `C:/Renulus/scratch/dcctl/rev1/probes/ux-319-20261010/manifest.json`.
Restart and final close were normal, with empty forced/remaining PID lists and
null fault. Final close finished at 14:12:21.706 UTC. Zero live provider calls.

**R6 remains P2 on current committed bytes.** Through Tests, create
`DC01 319 hidden UX recheck`, three reviewed questions, Continue to Study and
Start Study. On question 1, RN-AAV-001 has no authored hint. Click Hint.
Request 020 reaches the visible heading “This action needs recovery”; request
022 reaches its hidden state without dismissal, retry or another user action.
Request 023 again shows enabled Hint and no explanation. The two-second
refresh still calls `AttemptSession.accept`, which clears `error` on every
successful read. Captures 0001/0002 already show the cleared screen; they do
not claim visible error pixels. Retain action feedback until a relevant
successful action, explicit dismissal or retry; describe unavailable authored
help truthfully instead of losing the reason during draft polling.

**R4 remains P2 on current committed bytes.** Ask in chat creates the actual
saved conversation `thread_269ffc13e641470694c3e1563969b89a` without Send.
`preview-seed.json` records an explicit production `PUT /workspace/preferences`
fixture containing only that saved context and the UI-created reviewed version
`test_version_f05a55809f4b49e59ad54677e108f569`, preferred width 480. This
reference seed proves restoration; it does not accept an absent Test-tab-open
producer. Restart normally, choose Study question and open Workspace before
visiting Tests. At 1440×900 outer / 1424×861 content, capture 0003 shows default
list markers, joined “Reviewed bankReviewed” and “3questions”, and compressed
hierarchy. Visit Tests, return to the same Chat and retained preview: capture
0005 shows the correctly separated labels, question-count hierarchy and
spacing. The preview must load its own existing styles independently of route
entry. Tests/shell owners retain that source fix.

At 1000×900 outer / 984×861 content and native 200% zoom, the restored preview
uses a focused single pane. Tab from Use a timer reaches Continue to Study
with visible focus in capture 0004. This checks that named transition/control;
it does not establish full tab order, pointer resizing or Windows DPI behavior.
All five captures are under `C:/Renulus/scratch/dcctl/rev1/c/s-59e2b4de/out/`.

Two preliminary terminal clients delayed output and were interrupted before UX
actions. Read-only checks found none of their six exact observed process IDs
remaining. Their startups are operator recovery, not successful normal
close evidence. The earlier s-60e257ce session receipt gained a further launch;
the prior manifest retains its original three-launch/three-close receipt
snapshot and unchanged screenshot hashes. Current normal-close acceptance
rests on the fresh s-59e2b4de session above.

| Screen/state | Connected coverage and exact open scope |
| --- | --- |
| Home / default New chat | The 84+mount pass rendered the real Home composer and isolated draft loss through actual Test policy start/release without navigation. R3 remains open; provider-backed daily suggestions and complete recovery focus are not accepted. |
| Chat | Actual Study-to-saved-Chat preparation, retained public-question draft, CSV upload/rights/Open file and reader were checked on 84+mount. This follow-up reconfirms preparation and draft restoration. No Send or model-response acceptance. |
| Library / reader | The 873 pass covered actual PDF page 3 and CSV rows 101–200; 84+mount covered real Chat CSV upload/preview and restart. R7 position loss and R10 Files inventory remain open. This is not full format/extraction/OCR or Library eligibility acceptance. |
| Tests collection / setup / Import | Actual reviewed creation, pasted private-original review, edited-key re-selection and explicit Imported/Personal/Ready Version 1 publication passed on 84+mount. Current restored setup recheck confirms R4. R9 edited-key copy, media imports, normalization/retry and native chooser remain open. |
| Study / assistance | Actual Study answer commitment and summary, Notes pane opening and Ask in chat were checked on 84+mount. Current R6 recheck uses a UI-started reviewed Study. G1 Notes creation and G2 Reader receipt/abort consumer remain open. |
| Test / results / restricted navigation | Actual Untimed Imported Test, Home restriction, no Pause action, keyboard final submission and personal 0/2 result passed on 84+mount. Ten route denials and eight Study-help guard tests retain their separate backend scope. Timed expiry/sleep, ambiguous acknowledgement and full results/filter/export behavior remain open. |
| Workspace / keyboard / narrow / zoom | The retained passes cover real mounting, 480 preference restoration, keyboard width changes and safe tabs. This follow-up adds 1000×900 / 200% restored-preview focus and desktop before/after route pixels. Pointer drag, concurrent preference writes and general focus routing remain open. |
| Project / Goals | Earlier recorded continuation covers real project context, no inherited Chat tabs and truthful empty Goals. Current 319 baseline full project creation/goal workflows were not rerun or accepted. |
| Settings / Nightly / delivery | Earlier continuation covers actual Off preferences and keyboard/narrow/200% rendering. Current full Settings and enabled Nightly workflows were not rerun. Physical dialogs, installed Windows delivery, scaling/high contrast and subscription acceptance remain separate gates. |
| Editable Figma C | DC01 checklist covers representative C screens and 46 Test specimens. `81:5381` and ten related frames have screenshot-verified unpausable Test copy in `fc732598`. Design pixels establish the visual contract, not connected feature completion. |

The highest-priority data finding remains R8 reviewed progress omission. No
other lane is blocked by this report, no source repair is attempted here and
no feature ticket is marked complete. The remaining producer/consumer gates
in the preceding section continue to apply.

Checkpoint checks passed: `git diff --check` and the public workspace check
(18,426 public files, 1,169 local links, 27 topics and 199 subtopics). The exact
lane root and status identify this report as the sole Git content change.

## Reservation, commits and source identity

The lane is `codex/dc01-design` at `C:/Renulus/dev/worktrees/dc01-design`. Normal
`git rev-parse --show-toplevel` was checked before the Workspace commit and
before this report. Canonical source at `C:/Renulus/dev/repo` was read only.
No schema, server, shell, shared type, preference backend, reader or assessment
file was edited by this review. No push, reset, checkout, credential access,
live provider call, owner profile access or OS/Computer Use input occurred.
The lane merged `a87a6fc3` as `b25e20e48839d214bf8e8a975dd7ccaa420d503a`. Four
add/add conflicts contained the parent-integrated older Workspace checkpoint;
their inspected resolution retained the already-committed local follow-up. All
other incoming files auto-merged. The lane was clean afterward. No Workspace
content edits remain pending beyond the published `8b7944e7` slice below.

The Workspace follow-up is
`8b7944e7ce23254a64c4c74d3f3914d4d13370e6`, following `ed3d91cb` (integrated by
the parent as `96fefd5b`). Its exact changed paths are:

- `apps/desktop/src/modules/workspace/README.md`
- `apps/desktop/src/modules/workspace/WorkspacePanel.tsx`
- `apps/desktop/src/modules/workspace/WorkspaceProvider.tsx`
- `apps/desktop/src/modules/workspace/fixtures/persistence_bridge.py`
- `apps/desktop/src/modules/workspace/persistence.test.tsx`
- `apps/desktop/src/modules/workspace/workspace.test.tsx`

That follow-up invalidates old context callbacks immediately, excludes a passage
callback when none was injected, distinguishes unavailable policy from an active
Test, and adds real SQLite contract/policy reopen checks. Its labelled preference
fixture is not the `/workspace/preferences` route. The previous local evidence
was 14 frontend cases, two SQLite cases, a module TypeScript check and the public
workspace/link check. The [module seam](../../apps/desktop/src/modules/workspace/README.md)
records the integration boundary.

The canonical HEAD was `98917b67c8b1892936debc6e070f5c2328ff4ca5` at initial
inspection and `b3aab6ef0aee2ca02e390d80534a2379a82ce40d` at the final manifest.
The parent's shell/policy changes were uncommitted. Source continued to change
during this review, so each result is qualified by its actual bytes:

| Artifact | SHA-256 |
| --- | --- |
| Hidden native main | `c4b3e337fa58ee3e2754ffbf2d485cc74d0421db6a7d339ed36f3a5cc223d615` |
| Rendered shell `App.tsx` | `bf5b9a0df87ad83b8a7cb766b62c21e570125e9878625810f82d892ba9732d48` |
| Shell CSS | `b0658a08bfb9a5e9742020679653eb54e13fcc09903addcf380f32fecc51ef1e` |
| Learn service | `eb046443c736f595d963df9f55b64cd17e0440a2d8d9d8d956a0f8cfad6a35e6` |
| Server in stream-race probe | `fcc4afb421dc6bf257a664481426ce3af8c744de0f3014aaf6f95e23c254c2df` |
| Server in later Workspace route probe | `1982d812c75a65724b3400f41d99af07d3379c403ef9262ed8c1a63634c4083c` |
| Workspace repository in route probe | `a0ca431ad3aeedaa1ee62dd9cfbc14d6dd4ca060a7aa8645302562fe88bd8f30` |
| Workspace router in route probe | `b19cefd80ea1022b827e10471dae6f9ff3a1b7fec9a0821bee228ca9192f6202` |

The first later server change mounted `storage.workspace_api`. The subsequent
`fed90793` guard change was rechecked separately below. Full manifests and
results live under the owned external root
`C:/Renulus/scratch/dcctl/rev1/probes/`.

The continuation began against canonical `c19d14933cc26118e97c93841b932014ad9be675`.
The later source/build manifest observed
`e00842cbc203eae4b0faf02852021f07f5e0cc1e` plus the parent's current source bytes.
The renderer was replaced while the first hidden launch was running: old
`tests-BCygwPdb.js` returned 404 and Retry could not repair its cached lazy import.
After normal restart the actual Tests page loaded. This build-replacement event
is retained in logs, not reported as a stable product defect. No canonical build
was run by this lane. The matching later renderer's index mtime was
October 10, 2026, 04:41:34 UTC. Exact source and artifact hashes are in
`source-build-manifest-recheck.json`; they qualify the observations rather than
claiming that HEAD alone identifies an in-progress build.

| Recheck artifact | SHA-256 |
| --- | --- |
| Renderer `index-ep4EjfKQ.js` | `9fe71fbb566f9f1d7b9376acbf398f97e01a5796603f2642861e4261eede4085` |
| Rendered CSS `index-8ZAyLPsg.css` | `ea403be547886f942d1612909aef5f18ea9d99d75f8f77ed49ae9a484125c10c` |
| Current Learn service | `7599be3b55cd9c8cf522dc069057bb946db9e4af38fc825ea635a30e5f6c20f1` |
| Chat stream wrapper | `7225bf56bb507d59d94cd9d4e490eb132c4e0abcf8d5b5980912a52b1bbf3bd7` |
| Case repository | `4d5e5792f0c274e1dafd81db3c9daea841c3c2c6dbeaf28ae40368ea83c39ecf` |

The latest continuation normally merged the published `8e9f4403`, `48729826`
and `2122f875` baselines as `c94717e6be59a5b085a5f392a5f29d210b4f612b`,
`429d7df4155bda67fe5f9c8a8889243d1d86a2af` and
`c26e518efb6ba290f663925a6192dd95d4a702c7`. Each merge followed clean content
and exact-root checks; no reset, checkout or unowned flag cleanup was used.
Canonical HEAD in `source-build-pass2-14b25efe.json` is
`2122f875b556e29f6bf32b73f2ee07583c5f1c59`. Source may include parent work in
progress; actual build hashes identify the rendered artifact. The later build's
index mtime is October 10, 2026, 05:22:26 UTC. A superseded Chat lazy stylesheet
also returned 404 during build replacement. Normal owned restart loaded the
new artifact; this is retained as a build-replacement event.

| Latest artifact | SHA-256 |
| --- | --- |
| Renderer `index-CsLiABk8.js` | `85f2b9aeb6c430adf511f83686715e6661cdf98f737ae07ccf0cfaeae83e6352` |
| Shared UI `ui-BGZ9rNfx.js` | `452f51baa25f621f07151e42d01acb588410c8ec89814edb9d8f3a7587e9c2a7` |
| CSS `index-rc476Hzg.css` | `caa525cfedd7bc6f271fe83bcd3a65d776ffc9d4007dad920836aafcabb56835` |
| Workspace shell adapter | `d7271f9486bef08a721d51c969d855fbe4d3aed71eb9e42bb596e9b4c36def91` |
| Workspace panel | `c2863485183498945876b26bbbb30bd86dc206c4900d188ca6d06c11f04d4e99` |

## Material findings

### R1 — original P1: late Learn publication; bounded fix recheck passes

Locations: `runtime/renulus/learn/service.py:347`–`376` and
`runtime/renulus/server.py:116`–`128` in the byte snapshots above.

Reproduction: run `probes/policy_review.py` with the managed Python and
`PYTHONDONTWRITEBYTECODE=1`. It uses the production `create_app`, actual
`POST /api/v1/learn/ask`, actual migrations/SQLite and a deterministic synthetic
provider. The provider yields one synthetic fragment, then activates a Test and
advances policy immediately before completing. No lifespan/helper worker,
model, memory engine or network provider starts. The Test transition is a
direct synthetic canonical fixture, not an attempt-start API acceptance test.

Actual: the stream ends with `assistance_restricted`, but SQLite contains one
assistant answer, a `completed` Learn run and two new learning-evidence rows.
The memory adapter receives one notification. A second probe starts and
finalizes the Test before provider completion; the stream emits
`assistance_changed`, yet the same canonical writes and notification occur.
A direct Learn-service probe confirms `completed` under active restriction.

Expected: a run whose captured policy revision changes must not publish the
answer, completion or capture evidence, including after assistance becomes
allowed again. Filtering the outgoing HTTP chunk occurs after the producer's
transaction and therefore cannot undo those writes. This can leave a learner
with an error in the stream while history records a completed answer.

Recommended owner change: capture policy revision at prepare/dispatch, recheck
before advancing an in-flight provider and inside the same `BEGIN IMMEDIATE`
transaction as answer/evidence publication, then cancel/reject the stale run.
Apply the boundary to Case handoff and other help producers separately; those
producer-specific outcomes were not established here. Test active restriction
and a start/finalize revision change, with zero late assistant/evidence writes
and zero capture notification.

Initial canonical evidence: `probes/policy-review-initial-recovered.json`,
read-only recovered rows from preserved `http-active-abfe5b9f`,
`http-finish-a224b5eb` and `service-9ae88d53`. All retain the original completed
run, one assistant and two evidence rows. The recheck inadvertently overwrote
the fixed-name `policy-review-results.json`; it now contains fixed behavior.
Historical raw SSE/callback output was not reconstructed. Its original
observations remain above and in the tool transcript. The recovered JSON
explicitly states this boundary. New probes use unique result filenames.

Recheck: the same deterministic Learn probe against the new service bytes
produced `failed` runs, zero assistants, zero evidence rows and zero memory
notifications for active Test and start/finalize transitions. Direct service
execution also ended in error with zero publication. Evidence is
`policy-review-recheck-results.json` and `policy-recheck-a87a6fc3.txt`.

The independent actual Chat HTTP probe then covered 12 combinations: Learning
and Case, saved and temporary, crossed with active Test, start/finalize and
context-epoch change. Every combination ended in error, emitted no post-change
delta, wrote no assistant/evidence, notified no memory and retained the draft.
Saved command receipts recorded the terminal error. Evidence:
`conversation_policy_review.py` and `conversation-policy-results-90960447.json`.
It uses production `create_app` and `/conversations/.../messages`, direct
synthetic policy/epoch fixtures and a deterministic provider; no lifespan or
network provider starts. This verifies those publication boundaries, not all
producer cancellation schedules, actual attempt APIs or ticket closure.

### R2 — original P1 visual blocker: narrow clipping; rendered recheck passes

Location: `apps/desktop/src/shell/shell.css:117`, with the C rules at lines 3
and 40.

Reproduction in the owned hidden app: open New chat; resize to 640×640 outer
pixels (controller reports 624×601 content); keep navigation collapsed. Expand
navigation, then collapse it again. Wait for the `Welcome back` heading and
capture pixels.

Actual: only the 72 px rail and empty paper are in the viewport. The main
header/composer remain in the ARIA snapshot but are clipped outside the visible
pane. Opening the drawer temporarily makes the main pane visible; collapsing
it returns to the blank composition. `capture-0002.png` and repeated
`capture-0004.png` are identical.

Cause: the later legacy `@media (max-width:720px)` sets `.desktop-shell` to
`flex-direction:column`, overriding the earlier equal-specificity C row rule.
The C rail still consumes the full shell height; the main content is displaced
below a shell with hidden overflow. A successful DOM visibility wait alone did
not detect this rendered failure.

Recommended owner change: scope the old Flow media rule or give C a final,
consistent row/single-pane rule. Verify the collapsed and drawer states from
actual pixels at 640 outer width and at effective zoom widths. No native 200%
zoom check was performed in this review.

Evidence: `c/s-1a9fc319/out/capture-0002.png` (blank), `0003` (drawer open),
`0004` (repeat blank). `0004` SHA-256 is
`ff3ad358e5636909ffa29a288ea6de32a04faabd0f5615bb6b51324b0b2ace5d`.

Recheck in `s-10fbf4c8`: at the same 640×640 outer / 624×601 content size,
the collapsed rail and focused Workspace are visible (`capture-0009.png`),
and Back to chat returns to a visible Home composer (`0010`). The current
`.desktop-shell.design-c-shell` rule has sufficient specificity to retain the
row composition despite the legacy media rule. The original blank-column
failure did not reproduce. This covers real pixels at that width, not native
200% zoom or all drawer/reader compositions.

### R3 — P2: policy gating destroys an unsent draft and strands focus

Locations: `apps/desktop/src/shell/App.tsx:108`–`110`, focus effect at line 59,
and the local composer state in `apps/desktop/src/modules/home/index.tsx:25`.

Reproduction: at 850×760 outer size (834×721 content), fill the New chat
composer with synthetic text. Without navigating or submitting, activate the
owned synthetic Test fixture. Wait for Resume Test. Finalize the fixture and
wait for the same composer to return.

Actual: the returned composer is empty. The shell removes `ModuleOutlet` when
policy denies help, which destroys the local draft. This is distinct from
resize: the same hidden journey kept the draft and textarea focus while
resizing from 1000 to 850 pixels before policy changed.

The separate `probes/policy-focus.test.tsx` renders the actual shell/provider
with a synthetic draft module. Its observational assertions confirm the old
draft disconnects, active DOM focus becomes `document.body`, and the remounted
draft is empty. This passed one component reproduction; it is not a claim
that the desired behavior passes. The shell focus effect depends on navigation
revision, so the policy-only transition does not move focus to its recovery
control.

Recommended owner change: retain volatile draft ownership above the restricted
surface, suppress help and interaction without losing the draft, and move focus
to the restriction/recovery control when the focused surface is revoked.
Explicit temporary drafts must remain volatile. Restoring assistance should
recover the draft and an appropriate focus position.

Evidence: `capture-0007.png` (draft), `0008` (restriction), `0009` (empty
composer, no navigation between these captures). Before/after SHA-256:
`44cdc56f2606e8b34d84aa7040de674ce24027c519654410466bfc218b873d54`,
`6391d12759f5a0e72d407ab6c9ae85a4f03feafc1c182b9f163adef2419b2390`.

Recheck in the refreshed renderer: fill the actual Home composer at 850×760,
activate and finalize `review-ui-test` using
`controller_policy_recheck.py`, with no navigation between transitions. The
same draft disappears. `s-10fbf4c8/out/capture-0014.png` shows the focused draft,
`0015` the restriction, and `0016` the empty composer. This uses the real page
and backend policy polling, with an explicitly labelled direct Test fixture.
The exact loss still reproduces; the earlier DOM focus observation has not
been promoted to native/hidden focus acceptance. The current shell conditional
still unmounts `ModuleOutlet` at `App.tsx:110`–`112` in the rendered snapshot.

### R4 — P2: restored Test preview has route-dependent styles

Locations: `apps/desktop/src/modules/tests/index.tsx:10`,
`TestSetupPane.tsx:1`–`8`, and the import/preview in
`apps/desktop/src/shell/WorkspaceHost.tsx`.

Reproduction: create a reviewed set and saved Chat through the real UI. After
normal close, seed only their existing safe references through actual
`PUT /workspace/preferences` using `seed_saved_preview.py`. Start the same
owned profile, choose its recent Chat, and open Workspace before visiting
Tests. The restored saved-version tab passes canonical authorization and
loads the actual Test setup. Then visit Tests and return to that same Chat.

Actual: before Tests loads, the preview has default list markers and collapsed
spacing; origin labels run together as “Reviewed bankReviewed”, question count
as “3questions”, and the timer/count hierarchy is lost. Visiting Tests loads
`tests.css` and immediately restores the same preview's layout. Comparable
1440×900 outer captures `0020` and `0021` show the route dependency; `0018`
shows it on initial restored preview and `0019` at 640×760.

Cause: `TestSetupPane` is imported independently by the shell, but its styles
are imported only by the lazily loaded Tests page. Recommended owner change:
make the reusable setup pane import its required styles (or export a styled
adapter) and retain the existing token system. Verify a fresh saved-Chat
reopen before Tests navigation at default and focused widths. This lane did
not edit Tests or the shell. The reference seed establishes restoration,
not an unimplemented producer action to open a Test tab.

### R5 — P2: distinct readers have identical tab and close-control names

Locations: `apps/desktop/src/modules/workspace/WorkspacePanel.tsx:51`,
`apps/desktop/src/modules/workspace/types.ts:48` and
`apps/desktop/src/shell/WorkspaceHost.tsx:152` in the latest manifest.

Reproduction: in owned profile `s-23eb58db/p`, open saved Chat
`thread_246b4cb31342437d924b5ffdd032e351`. Open Workspace Files and select
“DC01 ReviewMarker file”, then “DC01 ReviewMarker second file”. These are
real canonical original-text revisions opened through the actual Files adapter.
Select the first file again: two tabs remain, so reference deduplication works.
Close/reopen the app normally, choose the same recent Chat and use End from
Files to select the second reader.

Actual: both tabs say “Document”; both accessible close controls say
“Close Document tab”. The reader itself shows the correct file title. The
learner must select each tab to distinguish them, and the close controls do
not identify which source they close. This persists after hydration and at
200% zoom. `capture-0013.png` and `0014` show the distinct reader beneath
duplicate tabs; `0017` confirms the same labels after restart and keyboard End.

Cause: the panel has a `getTitle(ContentReference)` prop, but the shared shell
adapter does not supply it. The content-type fallback becomes every tab's name.
Recommended parent change: resolve the currently authorized document/note/test
title in a volatile shell cache and pass it through `getTitle`, including on
saved-reference hydration. Refresh or clear it on relevant context/revision/
policy changes, retain neutral restricted labels, and use the resolved title
for both tab and close-control accessible names. Keep titles out of preference
storage. The existing prop needs no schema or Workspace persistence change.

Exact proposed contract wording for the parent: “Workspace tabs and their close
controls identify the authorized content title. Generic type labels are loading
or unavailable fallbacks. Reopening saved references resolves current titles;
titles are not persisted with references.” Verify two different files, a note
and a saved Test preview before and after restart; keyboard selection must
still target the correct canonical item. No shared/source fix was made here.

## Connected checks and evidence limits

The actual new Workspace routes appeared during this pass.
`probes/workspace_route_review.py` then passed 18 receipt/assertion checks:
saved conversation creation, explicit temporary creation, preference PUT,
fresh-app preference GET with width 600 and a text locator, rejection of a
temporary identity tagged saved, rejection of extra payload fields, content
authorization, revoked display denial, eight active-Test Workspace/Library
boundary operations, stale-policy rejection after finalization and retained
neutral references after rights revocation.

The script imports original synthetic text with the production Library
repository using `process=False`; it proves queued canonical ownership and
route/contract behavior, not extraction, indexing or reader rendering. It
retains `workspace-route-results.json` and profile `workspace-routes-4facf8b1`.
Actual `/library/documents`, original, citation and retrieve routes were checked
under restriction. The earlier broad policy matrix also included unavailable
paths; those results prove policy interception before lookup, not functioning
producer endpoints.

The parent's existing `tests/integration/test_design_c_policy.py` passed two
checks against the then-current canonical source. They cover active-Test
disclosure denial and a late read. They do not cover the canonical publication
race in R1.

The initial hidden controller used only
`C:/Renulus/scratch/dcctl/rev1/c/s-1a9fc319/p`. Settings opened with no selected
subscription; no connection/login/generation control was activated. Test policy
restricted the current module and Library navigation, hid history and disabled
Workspace. Search open/filter/Escape and ordinary navigation were exercised.
At 834 effective width the composition retained the 72 px rail and visible
composer. The desktop composition retained the calm C hierarchy, local typeface
and restrained teal system; no competing visual system was introduced.

The controller receipt records hidden, unfocused, nonfocusable windows, no
visibility/focus violation, and normal close with no forced or remaining PIDs.
All nine captures, logs and `receipt.json` are under
`C:/Renulus/scratch/dcctl/rev1/c/s-1a9fc319/out/`.

The continuation used only `C:/Renulus/scratch/dcctl/rev1/c/s-10fbf4c8/p`.
The actual fresh Home had empty canonical history and unavailable daily
suggestions without a connection. Opening Workspace loaded real empty Files,
Sources and Notes from `/workspace/entries`; Goals said to open a project.
No producer items, progress or responses were invented. At 1384 effective
pixels, the split retained 272 navigation and a 480 px preferred Workspace.
Resizing to 850×760 produced one focused pane; Back to chat retained the
unsent Home draft. End/Home/Enter/ArrowLeft operated the actual splitter.
Screenshots `0003`–`0008` retain default, focused, bounds and adjusted pixels.
Pointer drag and native 200% zoom were not exercised by this controller.

After restart, actual Tests created “DC01 pass2 synthetic reviewed set” with
three reviewed questions across T04/T16, saved Version 1 and loaded setup
(`0012`). At 640 width the collection remained readable and scrollable
(`0013`); Playwright could operate Mode and Continue to Test. That action
reached the explicit Attempt integration placeholder, so it establishes a
navigation handoff and no attempt lifecycle.

Actual destination search reached Chat; Start saved chat created the original
Learn owner, and the draft saved through its API without a send/model call.
Changing its Workspace splitter with End persisted width 624, confirmed by
fresh app factory GET after normal close. The subsequent explicit safe-reference
seed selected width 600 and the real reviewed Version 1 under that saved Chat.
Normal reopen restored the draft, context and one authorized Test preview tab
(`0018`). Selecting Version 1 again kept one tab. Focused preview at 640 width
and Back to chat retained the saved draft (`0019` and the ARIA snapshot).
`saved-preview-seed.json` preserves before/PUT payloads, exact identities and
the seed boundary. This tests preference hydration, canonical authorization
and the real preview adapter; reader positions and tab-open producer entry
points are separate.

The arriving parent-owned local search was reviewed read-only. Seven actual
route checks passed: bounded first page, unique pagination excluding temporary
and archived chats, archive opt-in, changed-query cursor rejection, maximum
query/limit validation and active-Test denial. Provider calls were zero.
Evidence: `search_review.py` and `search-review-results-e00e295e.json`, with
its exact uncommitted source hashes. This is saved-Chat API evidence only;
rendered search, project/file/note groups and stale-result interaction remain
unreviewed. Search source files and `LocalSearchResults.tsx` were not edited.

The continuation's 21 captures, logs and lifecycle receipt are under
`C:/Renulus/scratch/dcctl/rev1/c/s-10fbf4c8/out/`. Every launch remained hidden
and nonfocusable. All four close receipts are normal, with empty forced/remaining
PID lists and no controller fault. Final close completed October 10, 2026,
04:51:11.859 UTC. Expected offline/policy
409s, the superseded lazy asset 404 and one incorrect status-name wait are
retained in logs. No broad “zero errors” claim is made.

Review-document verification: `git diff --check` passed, and the public workspace
check passed with 18,307 public files and 1,168 local links. Before staging,
normal root verification returned this lane; only this report had content
changes. No unowned normalization flag was staged or reverted.

| Current capture under `s-10fbf4c8/out/` | SHA-256 |
| --- | --- |
| `capture-0014.png` — Home draft before policy | `577935132414fd76ce2e752c06d25d188784d1c4b22ae563c67db5d5c872dba6` |
| `capture-0015.png` — restriction | `523b18fb19cdd788c5d66c0cdc9291788fd9617741ee7ea0cf215bc5b13506cc` |
| `capture-0016.png` — lost draft | `c4952b644931c5a37ddb247809999ba3fc598582c0ac63b128275caf8ce5fe66` |
| `capture-0020.png` — preview before Tests loads styles | `8a69428239cd20d51605bcec45bbd4bc7eb1b1025de189f336e7f8351f3fe72c` |
| `capture-0021.png` — same preview after Tests | `fc771d707c70a0c1c7efc47f96eb175ba71af4ef480a374de6455b7a89c085a6` |

## Latest integrated screen and data pass

The latest hidden journey used only
`C:/Renulus/scratch/dcctl/rev1/c/s-23eb58db/p`. The normal controller client
read canonical code and built artifacts, while all runtime state, synthetic
inputs, probes and captures stayed under the owned external `rev1` root. The
first nine captures precede the build-replacement restart; later mounted
Generation/Nightly and reader checks use the recorded newer artifact.

`probes/seed_search_pass2.py` created/reused original synthetic saved Chat,
archived Chat and Project through real APIs, and imported original text through
the Knowledge repository with `process=False`. The seed did not fabricate
search responses, reader content or progress. The actual hidden worker then
processed the documents: the second seed result records ready passages for
the first file and note, while the second file was still queued at that moment.
Its later actual reader shows extracted text. This is text-reader evidence,
not acceptance of all confirmed formats or the upload UI.

The initial seed aborted after creating the Chats/Project because it used an
incorrect scope enum. The corrected run reused those durable records without
resetting or duplicating them. `search-ui-seed-a7b5437f.json` and
`search-ui-seed-2069e639.json` retain the actual responses and source hashes.
The latter explicitly bounds the seed itself as API/import evidence; the
additional rendered journey is recorded separately below. Temporary creation
in the API probe is process-local, so its absence from a separate renderer
alone is not new temporary-retention proof.

| Actual screen/journey | Observed result and evidence under `s-23eb58db/out/` |
| --- | --- |
| Home and navigation at native app zoom | At 1440×900 outer / 1424×861 content and 200%, Home/composer, focused Workspace tools and return remain visible (`0002`–`0003`). At 1000×900 and 200%, Home and its navigation drawer remain visible (`0004`–`0005`). The initial unsent Home draft survived Workspace return. |
| Saved local search | Rendered Chats, Projects, Files and Notes groups show real records and actual ready passage snippets (`0008`). Archived Chat appears after archive opt-in. Selecting the Note opens its actual reader (`0009`). Earlier seven route checks establish saved-only bounds/temporary exclusion; stale rendered selection and policy denial still need integrated rechecks. |
| Tests and Generation | After normal restart, Tests mounts Create test, GenerationPanel and “Nightly practice Off / Preferences” (`0010`). Topic/history results load; choosing 20 questions works at 1000×720 (`0011`). No Generate or nightly-enable control was activated. |
| Saved Chat, Files and readers | Actual Files entries open the first and second file; reopening the first deduplicates (`0012`–`0013`). Fresh `/workspace/preferences` GET returns width 480 and exactly two saved tabs in the saved Chat context, with only safe references (`workspace-ui-preferences-aa37f238.json`). No preference seed was used in this journey. |
| Reader at 200% | The second reader and its original text are readable in the focused pane (`0014`); duplicate Document tab labels remain R5. |
| Passage → draft → reopen | Discuss this passage places the actual original text and Source 1 into the saved Chat draft (`0015`), without a send. After normal restart and selecting the Recent Chat, draft/source and both tabs restore (`0017`). End from Files selects the second reader; Home then ArrowRight selects the first, with correct reader headings. |
| Nightly Preferences | The actual Tests Preferences link reaches Connections Preferences. Off, preferred time, count and the running/catch-up limitation load from the actual backend. At 640×760 / 624×721 content, keyboard traversal reaches Save preferences with a visible focus ring (`0019`–`0020`). At 1440×900 and 200%, the same controls and focus remain readable/reachable (`0022`). No preference was saved and Nightly stayed Off. |
| Project and contextual Workspace | Selecting the real Project loads its empty Conversations, existing saved-chat choice and project sections at 1000×720 (`0023`). Opening Workspace selects the project context with no inherited saved-Chat tabs. Goals returns the truthful “No goals in this context yet” and Open project action (`0024`). This checks navigation/context and empty production results, not goal creation. |

At 1000×720 with expanded 272 navigation, the app chooses a focused Workspace.
The Figma candidate uses collapsed 72 navigation to make room for a split. This
is a geometry decision for the shell owner: the observed single pane is usable;
the recorded thresholds are planning candidates. At the combined extreme of
640×540 outer / 624×501 content and 200% zoom, effective width is 312 pixels,
below the global body minimum of 320. Horizontal scrolling appears and the
Workspace heading wraps poorly (`0006`–`0007`). Record that exact combination
as an unresolved layout limit; it does not reproduce blank R2 at the documented
1440×900 / 200% reference. Pointer drag, full keyboard/focus routing, Windows
scaling, high contrast and screen-reader speech remain unperformed here.

The original text fits one short reader screen. Both saved positions are null
in this latest preference receipt. Tab selection and draft/source restoration
therefore do not prove page/passage/long-document position persistence. Source
jump after a model answer is also unperformed. Actual `/connections` GET in
this owned profile confirms no selected provider and null selected models.
No connection, login, generation, send or native-download action was used.

The bounded generation HTTP probe was completed before the latest screen pass:
`generation_pass2_review.py` / `generation-pass2-results-42669963.json` passed
37 checks across successful five-question publication, active Test before
completion, Test start/finalize before completion, context-epoch change and
five retained validated questions followed by Test activation in batch two.
It uses actual production HTTP/SQLite/ProviderManager with a deterministic
synthetic transport, no lifespan/helper engine and zero live provider calls.
The source is lane `429d7df4` / shared `48729826`, with hashes in the result.
Late cases published zero versions/evidence; restricted reads/create replay
were denied, neutral Stop returned only `{id,state}`, and reads/replay made no
new provider request. Stale work could not retry. These are producer publication
checks with a direct policy fixture, not actual attempt lifecycle acceptance.
Resolved typed graph/invalidation work was not repeated against later baselines.

The lifecycle receipt records three hidden launches, two normal restarts and
normal requested close on October 10, 2026, 05:36:57.763 UTC. All forced and
remaining PID lists are empty; controller fault is null. The 24 captures, logs
and receipt remain preserved. Expected offline/policy 409s, superseded lazy
asset errors, premature action/waits and a multi-match wait are retained; the
operator errors are not classified as product defects. No zero-error claim
is made. `probes/pass2-evidence-6ebd5b9e.json` records all 24 screenshot hashes
and the final receipt hash without overwriting previous evidence.

| Latest capture | SHA-256 |
| --- | --- |
| `capture-0013.png` — ambiguous reader tabs | `bf5d71bdbcc2c0f9455be00a337746b31313f9581bc975857636ad5df282f6b6` |
| `capture-0014.png` — reader at 200% | `bf5d1d14212553699a275fea2e0dfa505f007df12da0af7f5c8f8538fd81ab88` |
| `capture-0017.png` — restored draft/source/tabs and keyboard focus | `60dd0f4df237fe3a46d277f52c73e56594c39b83910fc7d78b40d6f3a1622402` |
| `capture-0020.png` — narrow Nightly keyboard focus | `7fea355ff065cc93de07b2f05652d07eda0dcdcc10124212a3e8a1f46367a38d` |
| `capture-0022.png` — Nightly keyboard focus at 200% | `0ba38f9329809bdfc77b536775a67a1fb0e3dd40e85d135959ca9d1b46590cb1` |
| `capture-0024.png` — empty project Goals | `1bb60efa803e4172e32eea444029212a619b336145b6cdf16e06a17f2e07ed2e` |

The design review used the interface-design review skill against the retained C
contract. The rendered hierarchy, Source Sans 3, quiet reading surfaces and teal
actions remain coherent; no replacement design system is proposed. Integrated
acceptance stays open because R3/R4/R5 affect retained work, preview readability
and source identification. The parent owns their shared-shell/Tests fixes.

Latest report verification: `git diff --check` passed. The public workspace
check passed with 18,367 public files, 1,168 local links, 27 topics and 199
subtopics. Exact-root/status inspection showed this report as the only content
change before its explicit-path local commit. No new Workspace source edit
or unowned normalization flag is included in this report checkpoint.

## Integration seam and remaining work

The retained [DC01 reconciliation](design-c-reconciliation.md) supplies the
Figma node links and reviewed screen/state inventory. Geometry remains: at 1440,
272 navigation / 688 chat / 480 workspace; preferred workspace range 360–640;
chat minimum 528; focused pane below 888 available pixels after navigation
(960 total with a 72 px rail). Automatic clamping must preserve preference.
The parent owns navigation collapse, shell mounting and persistence sequencing.

`WorkspaceProvider` expects canonical authorization for content/section, shared
`AssessmentPolicy`, optional initial preferences and callbacks. Panel
`availableWidth` is chat plus workspace after navigation. Adapters own their
producer requests and obey the supplied context, policy and AbortSignal. Safe
preferences are exactly `{width,tabs}`; each saved tab is
`{content,context,retention:'saved',position}`. No title, URL, path, original
bytes, scroll offset or temporary selection is persisted.

The initial rendered app did not mount Workspace. The continuations now verify
actual mounting, section adapters' real empty responses, width persistence, saved
context hydration, saved-test preview restoration and actual Files entry →
reader → draft/source → reopen at their recorded scope.
The geometry calculation clamps the preferred width to keep the 528 px main
pane; effective width differs from outer window width because of native borders.
These observations do not prove shell concurrent write ordering, long reader
positions, pointer drag or Sources/Notes/Goals content production. Actual
attempt-start/finalize and timer ownership remain with the attempt lane; direct
fixtures establish neither.

Next review should use the matching parent build after R3/R4/R5 fixes and
arriving producers. Priorities: volatile Home draft/focus recovery, independent
preview styles, authorized reader titles, concurrent preference writes, temporary
exclusion through actual producer entry points, long reader positions, actual
attachment format/state flows, real attempt/timer lifecycle and rendered search
policy/stale-result ownership. The parent's announced `387ea97d` banner/h1/context
fixes and Generation integration
are not inferred to pass from their commit labels; only the matching observed
bytes and journeys above are accepted. Recommended spec/shared-source changes
belong to the parent. This continuation changes only this reserved report.

## Shared baseline checkpoint — October 10, 2026

After verifying the exact lane root and clean content/index, the published
`8de5f0f6dbb4bbfaa764df2b3fc9265d4d182f2f` merged normally as
`2f7aaf78b48f1aeb10a8b35cfaaca6a2ba2fc08f`. There were no conflicts, manual
resolutions or unowned normalization changes. The difference from that shared
baseline remains only the six Workspace follow-up files and this report.

Against the new Knowledge003/shared contracts, the focused Workspace suite
passed all 16 tests across two files, including both real SQLite fixture
reopen/policy cases. The module TypeScript check also passed. Test profiles
and caches remained under `C:/Renulus/scratch/design-c/design/`; the retained
output is `workspace-8de5f0f6-results.txt`. These are dependency regression
checks, not a new hidden reader, media-recovery or assessment acceptance.

The supplied `2122f875` baseline still contains no `modules/attempts` or
`attempt_api.py` commit.
Independent assessment UX/integration review remains gated on the supplied
attempts commit and matching parent-built renderer. Typed attachment/media
recovery remains parent-owned. No new feature closure is inferred.

## Connected continuation on 873bad79 — October 10, 2026

The lane merged committed `873bad79` normally as
`105fca674b4bbdb31bffedf51037800fb25efd84`, with a clean index/content diff,
no conflict and no normalization cleanup. The six-file `8b7944e7` Workspace
follow-up remains ready for integration. Full desktop TypeScript, the renderer
and native entry build, and all 16 focused Workspace tests passed. The two
SQLite cases still use a labelled fixture preference adapter; actual production
route evidence is recorded separately below. Build operations ran only in this
lane. Ignored dependency junctions point to prepared public dependencies; their
targets were not edited. No canonical build or shared source edit occurred.

The matching renderer is `index-BlGnQLtg.js` with SHA-256
`4e23d413c73442a170e6f57918a1fa7c8dc46c9807d751c75f80ecafb7391b0b`;
the attempts chunk is `attempts-B72dHYoB.js`, SHA-256
`d4368a18ba26e3ed4ed9e88560b00ef31fd13c46a5390400dcc7db698dcd8087`.
The owned controller profile is `C:/Renulus/scratch/dcctl/rev1/c/s-85c92a5c/p`.
Its 14 screenshots, logs and lifecycle receipt are in the sibling `out/`.
All source/build, screenshot and result hashes are retained in
`C:/Renulus/scratch/dcctl/rev1/probes/pass2-evidence-873-70db1080.json`.
Four launches and three normal restarts ended with normal requested close at
06:12:10.173 UTC. Every forced/remaining PID list is empty; fault is null.
No credential, owner profile, live provider, OS input or Computer Use was used.

### Figma Test timing reconciliation

Editable page `2:250` in file `zV8JiWybVHP1UxJtLbZjEt` was accessible.
The installed figma-use skill and API references were loaded before calls; the
interface-design review skill supplied the content/geometry review. The bounded
audit inspected 46 existing C Tests frames plus two DC01 Test frames. It did not
request full-page metadata. Ten specimens received 16 text corrections and one
frame-name correction. No shared component, token, typeface or palette changed.

| Reviewed specimen | Corrected nodes and contract |
| --- | --- |
| [Reviewed-bank Test setup](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=81-5381) | `81:5548`: “No timer. Leave and resume your saved Test; it cannot be paused. Choices stay editable until final submission.” |
| [Personal Test setup](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=82-7014) | `82:7168`: the same Untimed Test timing copy. |
| [Saved Test](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=82-6141) | Frame renamed from `test-paused` to `test-saved`; `82:6259` is “Test saved”; `82:6267` explains saved resume without pausing. |
| [Active Test](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=4-5232) | `I92:11299;2:464`: “Leave”; `86:8099`: “You can leave and resume your saved Test. This Test cannot be paused.” |
| [Selected answer](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=86-8169) | `I92:11311;2:464`: “Leave”; `86:8365`: the same saved-resume message. |
| [Next question](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=86-8435) | `I92:11323;2:464`: “Leave”; `86:8631`: the same saved-resume message. |
| [Review Test](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=86-8701) | `86:8898`: the same saved-resume message. |
| [Timed Test](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=86-10746) | `86:10943`: “You can leave and return. Your timer keeps running; this Test cannot be paused.” `86:10942` restored its existing authored `18:42` example from the erroneous “Untimed”. This is illustrative design content, not runtime progress. |
| [Next selected answer](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=90-10332) | `I90:10340;2:464`: “Leave”; `90:10368`: the same saved-resume message. |
| [Final-submission saving error](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=122-12403) | `122:12440`: the same saved-resume message. |

Six final 1440×900 native Figma screenshots were returned through tools and
visually inspected: setup-bank, setup-personal-test, test-saved, test-question,
test-timed and the saving-error specimen. They are retained under
`rev1/probes/figma-test-timing-<node-id>-20261010.png`; the manifest records
their bytes and hashes. The reviewed-bank setup screenshot SHA-256 is
`25d1f37f6333da5e8ae2a18764cdb3a7d5d51ec402433602c7c4dc27b6518498`.
The seven 272 px timing messages reflow to 40 px and remain within their
auto-layout parents. The final bounded scan finds no remaining Test “Pause”
control, “Test paused” state or “You can pause and return” promise.
Study pause controls, timed Study expiry copy and the existing timed Test
setup/leave deadline disclosure are preserved. App source required no edit.

Exact recommended parent documentation changes: in the unfinished-Test policy
paragraph of the implementation spec, replace “Leaving or pausing preserves its
restriction” with “Leaving preserves its restriction; Test cannot be paused.”
In the timing/recovery inventory, replace ambiguous “Untimed pause” with
“Untimed Study pause/resume; Untimed Test saved resume without pausing.” Retain
the timed Test close/sleep/expiry requirements. Update any displayed specimen
name `test-paused` to `test-saved` while keeping its existing node link.
No spec, PRODUCT or DESIGN file was edited by this lane.

### Actual journeys, findings and producer gates

The actual Tests page created `DC01 873 integrated reviewed set`, three reviewed
questions, Version 1. Study committed the first answer, moved to question 2,
paused, restarted, resumed and opened Sources. Sources truthfully returned no
saved reader references and recorded assistance. Notes/Ask in chat were disabled
because ModuleOutlet supplied no consumer callback. Study finished with 1/1
included and two not submitted (`0003`, `0005`). This is bounded lifecycle
evidence; it does not accept the unconnected Notes/Chat/source consumers.

Retake opened real setup. An Untimed Test selected one answer and one review
mark. Home displayed the actual Test restriction (`0006`); after normal restart
Resume Test restored both choice and mark. The UI provided no Pause action.
At 1000×900 outer / 984×861 content and native 200% zoom, Tab reached Clear
choice, and Shift+Tab reached Submit test with a visible focus ring (`0007`,
`0008`). Actual final submission yielded 1/3, two unanswered, zero excluded,
and restored Workspace access (`0009`). These pixels were inspected. Timer
expiry, ambiguous save acknowledgement and simultaneous-window races are not
accepted by this Untimed journey.

`attempt-policy-873-a5db1a71.json` uses actual production HTTP/SQLite without
lifespan against that UI-created Test. `/conversations`, `/workspace/preferences`,
`/workspace/entries`, `/search`, `/workspace/authorize` and `/readers/resolve`
all refuse with `assistance_restricted`. It makes zero provider calls. This
complements the actual Home restriction; previous synthetic stream-publication
checks were not redundantly repeated. An earlier wrong `/local-search` probe
and unauthenticated loopback reads are retained as operator errors, not route
acceptance evidence.

**R6 — P2, unavailable-hint error disappears without dismissal.** On Study
question 2, Hint produces 409 `hint_unavailable`: no authored hint exists in the
pinned question. The controller successfully waited for “This action needs
recovery”, then for its disappearance without another user action. A later
snapshot again shows enabled Hint and no explanation. `AttemptSession.accept`
clears `error` on every successful read; the page refreshes every two seconds.
Keep an action failure until explicit dismissal, retry or a relevant successful
action; distinguish unavailable help from failed draft saving. The dedicated
production response is `attempt-read-873-c9dccf79.json`. Screenshot `0004` was
taken after the error had already disappeared; it proves the subsequent screen,
not visible recovery copy. The before/after waits remain in the session outputs.

**R7 — P2, reader positions are lost despite restored tabs.** Original synthetic
three-page PDF and 205-row CSV were imported through canonical Knowledge APIs,
without a provider. The actual worker made both ready. Workspace Files opened
them. Navigate the PDF to physical page 3 (`0010`), the CSV to rows 101–200 of
206 (`0011`), close normally through restart, reopen the saved Chat and use
Files ArrowRight / End to select their retained tabs. PDF restores at page 1
(`0012`); CSV restores at rows 1–100 (`0013`). Both positions are null in fresh
`/workspace/preferences` (`connected-read-873-1d1ddf86.json`). ReaderSession
ignores injected `position` and `onPositionChange`, initializing only from the
opening reference locator. The reader owner must hydrate a validated safe
ContentLocator and publish actual page/sheet/row changes. Keep original-byte,
path, URL and scroll-offset exclusion. Workspace already injects the typed seam.

**R8 — P1, committed reviewed answers are omitted by progress consumers.** The
actual Study and final Test produce four canonical `assessment-test-answer`
evidence rows. Fresh `/study/progress` returns zero answered/correct in every
group and no topics (`connected-read-873-15406112.json`). `study/service.py`
filters only `assessment-answer` in progress and mistake scheduling. On this
baseline Home, Project and memory eligibility also use the legacy kind, old
`mode='reviewed'` payload and legacy assessment identity. Adding the new kind
alone is insufficient: consumers need the whole-attempt producer's pinned
version/origin/cohort eligibility and safe attempt identity, with Study/Test and
personal/reviewed distinctions retained. The route omission is confirmed;
Home/Project/memory impact is source evidence, not a model-powered acceptance.
The parent has since announced newer shared consumers; this finding requires
recheck on their exact committed bytes. Do not rewrite frozen command schemas.

**Attachment/File gate, pending producer-consumer checkpoint.** Actual saved
CSV upload through `/attachments` succeeds and attachment inventory contains
`attachment_f58011927b744c8f9abe444757d20ca9` in the synthetic saved Chat. Its
original byte receipt is retained in `review-873-seed-0072ce27.json`. Workspace
Files lists only the two Library revisions; the Chat paperclip opens that list.
The inventory API success does not prove upload UI or attachment-reader
acceptance. Recheck the parent's arriving File handoff and current Chat upload
mount rather than treating this older consumer gap as a new backend failure.

Actual keyboard splitter ArrowLeft writes width 500 through the production
preference route (`connected-read-873-dc0edec9.json`). Enter restores 480
(`connected-read-873-e57f89bd.json`). Two safe saved references survive normal
restart without a preference seed. At 1000×900 / 200%, the app chooses a focused
single Workspace pane; Back to chat, tab controls, CSV header and row controls
remain reachable (`0014`). R5's two Document tabs and identical close names
still reproduce. This checks rendered transition/keyboard and persistence;
pointer drag, concurrent preference writes and complete tab-focus behavior
remain open. No fictional filler, provider send or native download was used.

Next bounded review is the user-supplied `84be584e` plus current Tests Import
mount and shared StudyHelp/File checkpoint. Recheck actual Import creation/edit/
readiness/start, Study help's receipt validation and late publication, reader
position ownership and current committed evidence consumers. R3/R4 require
their explicit repros against the matching build. Native installation/dialogs
retain separate acceptance. No source implementation or feature-ticket closure
is part of this report checkpoint.

Checkpoint verification: `git diff --check` passed. The public workspace check
passed with 18,390 public files, 1,169 local links, 27 topics and 199 subtopics.
Exact-root/status checks identify this reserved report as the only content edit.
