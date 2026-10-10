# Design C — Tests decisions and prototype scope

October 10 update: Design C is now the selected replacement. Use the
[consolidated implementation spec](DESIGN_C_IMPLEMENTATION_SPEC.md) for build
tickets, dependencies and integration acceptance. The prototype decisions and
their original scope/evidence remain below.

Recorded October 9, 2026 after the owner accepted the Test recommendation and
authorised parallel agents to build, edit and validate the Figma prototypes.
This is a product/design plan; it does not authorise app implementation.

## Accepted product decisions

- One **Tests** collection holds reviewed-bank assessments, user-added tests,
  personalised overnight tests and tests created in chats. A chat-created test
  also appears in the right workspace and references the same saved test.
- A saved test and immutable version are separate from an attempt. Editing a
  test creates a new version and never changes past or active attempts.
- **Study:** select an answer, explicitly Submit answer, then show immediate
  feedback and explanation. Submitted answers lock. Next advances. Help marks
  the question assisted before returning content; advancing clears old help.
- **Test:** selections autosave and remain editable until final Submit test.
  Users can navigate, skip and mark questions for review. Keys, explanations,
  notes, sources and chat help remain unavailable until final submission. A
  neutral question navigator/progress panel is available during the attempt.
- Untimed is the default. An optional configurable timer starts when a ready
  test begins, never during generation. Study and untimed Test can pause/resume.
  For timed Test, time continues during navigation and after closing the app;
  expiry submits saved answers, counts unanswered questions and reopens results.
  The backend owns the persisted deadline, not a renderer-only countdown.
- Generated sizes are **5 / 10 / 20**. Five remains Quick practice. Larger sets
  use smaller validated batches with progress, cancellation, duplicate checks
  and recovery. Reviewed-bank count is 1–50, subject to available content.
- Overnight generation is opt-in with time/count preferences and a bounded run.
  Initial scope is generation while Renulus runs, with one catch-up after a
  missed night. Fully closed-app execution requires separate Windows scheduling
  work and is not implied by the prototype.
- Include resume, mark for review, question navigation, review mistakes, Retake,
  local Question seems wrong, and Generating / Ready / Needs review states.
- Origin and quality are separate. Agent formatting does not promote an import
  or generated test into reviewed-bank scoring. Practice results remain separate
  from reviewed-bank scores. Preserve originals and flag missing/ambiguous keys;
  agents must not silently invent them.
- Tests from an unsaved case use generalised fictional content, or require
  explicit saving before retaining original case details.
  This qualification applies to optional temporary/unsaved content. The later
  conversation-retention decision makes saved chats/context the normal default;
  it does not make every case temporary.

## Current implementation evidence and required work

The current app already has explicit per-question answer commitment, Next,
Finish and pause/resume: [assessment renderer](../../apps/desktop/src/modules/assessment/index.tsx).
The old Figma specimen omitted those steps.

| Capability | Existing foundation | Required extension |
| --- | --- | --- |
| Reviewed count | `contracts.py` count 1–50, default 10 | Setup reflecting available content |
| Generated questions | `generated_contracts.py` count 1–5 and validated batches | 10/20 assembly, cancellation, deduplication, recovery |
| Study help | `repository.py` records assisted before returning hint/sources | Notes/chat assistance, no cross-question help leakage |
| Test mode | Current selection is renderer-local; submission is per-question | Durable drafts, navigation, final submission and feedback gating |
| Timer | No assessment timer | Durable start/deadline, expiry, reopen/reconciliation |
| Saved tests | Generated sessions/questions/attempts are durable | Reusable named test, immutable versions, separate attempt lifecycle |
| User imports | Library provenance/extraction foundations | Private structured-test import, validation/review and original retention |
| Chat test cards | Durable threads/messages | Structured attachment referencing saved test/version |
| Nightly generation | Bounded app-running update scheduler | Tests scheduler/settings, eligible memory/session input, one catch-up |

Relevant sources are under `runtime/renulus/assessment/`,
`runtime/renulus/knowledge/models.py`, `runtime/renulus/learn/schema.sql`, and
`runtime/renulus/updates/scheduling.py`. Use the selected subscription/model route
in `runtime/renulus/runtime/manager.py`; do not add incidental provider calls.
Public CC BY question-pack contracts are unsuitable for arbitrary private imports.

## Prototype implementation choices

These are reviewable UI choices, not additional claims of backend readiness:

- Calm C shell, Source Sans 3, existing teal semantic tokens and components.
- Collection rows show origin, quality/status and one useful next action.
- Setup explains the two modes before starting and discloses timed-Test rules.
- A final submission checkpoint reports answered, unanswered and marked counts.
- An unfinished Test retains its help/content boundary while paused or left.
  Its collection state offers Resume and Review and finish. Starting another
  test or opening study materials first requires submission of the active Test.
- Mode and timer controls preserve the selected saved test/version and origin.
  They cannot silently replace a personal test with a reviewed-bank example.
- Timer expiry and recovered generation are explicit state specimens. Countdown
  and generation progress are illustrative; Figma does not run a real backend.
- Timed Study is a proposed distinct rule: pausing stops its timer; expiry stops
  and saves committed progress and the pending draft without submitting it.
  Offer Continue untimed or Finish study. Pending answers are not scored.
- Example names span nephrology. Question examples are synthetic interface
  fixtures and do not establish clinical question accuracy or educational efficacy.
- Study reuses synthetic source-navigation specimens while counting each explicit
  submission. Test demonstrates first/next saved choices; its review and score
  summaries are representative fixtures, not a general question/grading engine.
- Timer presets and mode choices update prototype state. Free-form setup fields,
  real elapsed time, closed-app recovery and model generation need app/backend
  implementation; the expiry and generation states illustrate the intended UX.

## Acceptance checks

1. Collection, setup, attempt, completion and resume are connected.
2. Study requires explicit commitment, locks submitted answers and resets help on Next.
3. Test has durable-draft copy, clear review/final submission, and no help/key leak.
4. Timer options/default/start/closure/expiry behavior agree across all screens.
5. Imports retain originals and expose uncertain keys; generated/imported results
   cannot be mistaken for reviewed-bank scores.
6. Chat workspace and collection visibly share the same saved test identity.
7. Nightly is opt-in and states its app-running/catch-up limitation.
8. Editable layers, existing components/tokens, no clipping or broken destinations.
9. Refresh only C Test/Question/Feedback comparison cells; preserve A/B and grid.

Figma file: `zV8JiWybVHP1UxJtLbZjEt`; C page `2:250`; comparison page `12:23`.
The final C Test work covers 46 editable screen/state specimens. Start from
the collection so selecting a test establishes its identity before setup.

| Review entry | Figma node |
| --- | --- |
| [Tests collection](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=4-5061) | `4:5061` |
| [Reviewed Test setup](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=81-5381) | `81:5381` |
| [Chat-created Study setup](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=81-6114) | `81:6114` |
| [Import review](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=83-7406) | `83:7406` |
| [Nightly practice, Off](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=83-7590) | `83:7590` |
| [Saved test in chat workspace](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=83-7934) | `83:7934` |
| [Generation recovery](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=83-8258) | `83:8258` |
| [Timed Test expiry](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=86-9144) | `86:9144` |
| [Timed Study expiry, proposed rule](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=86-10588) | `86:10588` |
| [Three-design comparison](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=13-23) | `13:23` |

[Open the interactive collection prototype](https://www.figma.com/proto/zV8JiWybVHP1UxJtLbZjEt/Renulus?node-id=4-5061&starting-point-node-id=4%3A5061&scaling=contain).

## Final prototype validation

- Three subagents produced collection/attempt work and an independent review.
  Parent integration corrected the material findings before final acceptance.
- Fourteen checks pass against the actual saved reaction graph: first/next
  choices survive revisit; assistance precedes help; empty Study answers cannot
  submit; commitment locks choices; Next clears help; all five Study answers
  require commitment; exact resume and Study identity persist; unfinished Test
  guards hold; generated/nightly 20 remain 20; cancellation retains four or
  seven questions appropriately; a recovered four-question Study completes;
  timing preserves test identity; default timed Test starts at 20:00 without
  Pause; personal results remain separate after final submission.
- The Figma bridge saves multi-branch conditions as if/else. The final wiring
  uses independent guarded actions, validated by reading back saved reactions.
- All 46 specimens use Source Sans 3 and editable layers/components. The only
  image fills are the existing small logo; no complete UI raster is present.
  No reaction destination is missing. Final screenshots show contained timer
  buttons and one Previous control, with no visible clipping in checked views.
- The comparison retains 27 frames, three columns and nine matching rows.
  A/B are preserved. Only C Test/Question/Feedback screens were replaced; C
  navigation labels use Tests. All nine C specimens have zero reactions and
  zero prototype-variable bindings, while semantic design tokens remain.
- Final C comparison replacements are `108:16647` (Tests), `108:16691`
  (Question), and `108:16762` (Feedback).
- The workspace/layout/local-link check and `git diff --check` pass.

Construction ledgers and detailed graph evidence are retained in
`C:/Renulus/scratch/figma-c-tests-20261009/state.json` and
`C:/Renulus/scratch/figma-c-tests-20261009/final-validation.json`.
These checks establish reviewable Figma behavior, not backend readiness. App
code, installed builds, model services and learning data were not changed.

## Suggested implementation order

1. Define canonical saved-test/version records, provenance and private import
   validation. Separate those records from attempt state.
2. Extend attempts with durable choices, marks, question navigation, exact resume,
   Study commitment and Test final submission. Enforce assistance/feedback rules
   in the backend as well as the interface.
3. Add persisted timer start/deadline and reconciliation on reopen. Test expiry,
   interrupted writes and pending-answer behavior before showing timing as live.
4. Assemble larger generated sets from validated batches, with cancellation,
   duplicate detection, uncertain-key review and recoverable drafts.
5. Attach saved-test/version references to chats and add opt-in, bounded nightly
   generation using eligible saved sessions/memory. Then connect the C screens
   to these contracts and validate complete user flows.

This ordering is a proposal for the next implementation plan. None of these
extensions is implemented by the Figma work.
