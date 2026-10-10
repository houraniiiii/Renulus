# Design C: simpler new chat and daily suggestions

October 10 update: Design C is now the selected replacement. The
[consolidated implementation spec](DESIGN_C_IMPLEMENTATION_SPEC.md) governs the
build and supersedes this dated proposal where later retention/sizing decisions
differ. The original prototype scope and evidence remain below.

Date: October 9, 2026. Status: Figma refinement and implementation proposal.
Product implementation is not authorised by this design request. Confirmed
decisions are recorded in [the user-answer register](2026-10-04-user-answers.md);
the behavior and engineering choices below remain proposals unless identified
as confirmed there.

## Prototype and scope

The C page is **03 · C — Chat + workspace** in Figma file
`zV8JiWybVHP1UxJtLbZjEt`.

- [New chat](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt?node-id=4-3926)
- [Explain suggestions, C26](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt?node-id=67-4874)
- [Case suggestions, C27](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt?node-id=67-5095)
- [Practice suggestions, C28](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt?node-id=67-5316)
- [Conversation with Files](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt?node-id=25-2522)
- [Three-column comparison](https://www.figma.com/design/zV8JiWybVHP1UxJtLbZjEt?node-id=13-23)

The personalised greeting replaces the three introductory lines. The composer
uses “How can I help you today”, retains Attach and omits Auto. Compact learning
actions reveal five prompts beneath them. The navigation status row and
conversation follow-up button are removed throughout C. The conversation
placeholder is shortened to “Message Renulus…”.

Karol is an illustrative name, and all fifteen suggestions are sample content.
The new states use editable instances of the existing button components,
Source Sans 3 and the existing Renulus tokens. The C Home, Chat and Case rows
are refreshed on the comparison board; A/B retain their own designs.

Figma supports category switching, closing the selected category and prefilling
the composer through a prototype variable. Send uses existing representative
screens: Conversation, Case and Test setup. It does not generate a response,
run a practice session or preserve the selected prompt in those destination
examples. The live implementation must route generated practice directly into
the unscored practice flow. Home examples with the workspace or collapsed
navigation link to the same expanded demonstration frames; the implemented
expansion should preserve their existing project, workspace and sidebar state.

## Proposed interaction behavior

Render a greeting locally from an optional name chosen in preferences. Use a
small set such as “Welcome back, Dr. {name}” and “Hi, Dr. {name}”. Choose once
when a new chat opens and keep it stable while the user works. If the name is
unset, show a generic welcome. Do not infer it from a Windows account.

Keep at most one category expanded. Switching categories replaces the five
visible suggestions. Clicking the selected category closes the list. Selecting
a suggestion places its prompt in an editable draft; it does not submit it.
If the draft already contains user text, avoid overwriting it silently: offer
to replace or append the suggestion. Send then invokes the appropriate flow.

The category controls expose expanded state to assistive technology and work
with the keyboard. The suggestion list uses ordinary buttons. Preserve the
draft and selected category when the workspace opens or closes. Keep greeting
and composer placement stable as the list expands. The composer grows with
text; the content area scrolls when necessary and uses a maximum width of
720 px while fitting the available pane.

Explain invokes the existing learning conversation. Case suggestions seed a
fictional educational case and retain the existing explicit-Save behavior.
Quick practice invokes generated practice, with its existing 1–5-question
scope. It stays separate from reviewed-bank assessment and scoring. Merely
viewing or selecting suggestions creates no study evidence or learning memory.

## Backend readiness

The daily suggestion service and chosen-name setting were not found in the
inspected implementation. Useful supporting pieces already exist:

| Existing capability | Relevant source | Reuse for this change |
| --- | --- | --- |
| Selected subscription and model routing | `runtime/renulus/runtime/manager.py`, `ProviderManager._route`, line 309 | Use the existing approved route without a silent provider/model fallback. |
| Eligible learning-memory context | `runtime/renulus/learn/service.py`, line 296, plus `MemoryContext.capture` | Reuse bounded retrieval and fact eligibility, revision and deletion checks. |
| Study goals and usage evidence | `runtime/renulus/study/service.py`, `StudyService.evidence`, line 77 | Use active topics, global study preferences and bounded learning/assessment aggregates. |
| Bounded background jobs | `runtime/renulus/updates/scheduling.py`, `UpdateScheduler.manual`, line 160 | Reuse concurrency, deadline, interruption and retry patterns in a separate job. |
| Local preferences | `runtime/renulus/storage/database.py`, line 28 | Add the optional greeting-name preference and derived cache records. |

Current study planning is deterministic. Conversation activity indicates
interest, not mastery. Proposed project goals and other missing C project
features must not be treated as available backend inputs.

## Proposed daily generation and cache

Generate one daily bundle containing exactly five items in each of the three
categories. Start a bounded job on first use of new-chat suggestions each local
calendar day, or on the next use after a missed day. A Windows app that is
closed cannot perform that refresh; no hosted service is implied. Read the
local cache immediately, and update it when the job finishes. Viewing the same
suggestions repeatedly should not repeat model calls. This single-bundle
approach is a proposal to reduce repeated generation.

Expose a cache read operation and an idempotent refresh operation through the
existing desktop/backend boundary. A proposed read contract is:

```text
status: empty | refreshing | ready | stale | unavailable
day, generated_at, next_retry_at, error_code
categories: explain | case | practice
item: id, topic_id, title, prompt, reason_code
```

The server supplies profile scope, date, selected route and personalisation
inputs. Inputs should be bounded usage summaries, eligible memory facts,
active nephrology topics and saved global goals. Do not copy raw chats, case
records, attachment bodies or reviewed question/answer content into the cache.
Keep model input volatile, and do not retain personalised explanations that
restate memory facts. Case seeds are fictional.

Validate the complete model result with a strict schema before publication:
three categories, five distinct items each, active topic IDs, bounded title
and prompt lengths, category-appropriate prompts and no unexpected fields.
Generate IDs server-side. Cap runtime/output and publish atomically only after
rechecking the route and memory eligibility. A partial or malformed response
does not replace a valid cache.

Allow one job at a time and deduplicate refresh requests. A current and previous
bundle, expiring after at most seven days, is a proposed bounded cache policy.
Invalidate affected caches after memory edits/deletion, profile changes,
restore or relevant goal/content/route changes. Future usage feeds the next
daily bundle. Stop automatic retries on authentication or quota failures until
the connection recovers. No subscription switch or paid API fallback is added.

When refreshing, retain a still-valid previous list. If it is from an earlier
day, give it a short date label. With no usable cache, show a compact loading
or unavailable message below the selected category; the composer remains
usable. Connection failures offer the existing connection/retry action. These
fallback states are planned here and are not additional Figma screens.

## Implementation sequence and acceptance

1. Add the optional chosen-name preference and local greeting renderer. Apply
   the approved copy/control removals and category/draft state in the frontend.
2. Add the daily suggestion service, strict output validation, local cache and
   refresh orchestration using existing selected-model and memory interfaces.
3. Connect the lists and editable drafts to Learn, Case and generated-practice
   flows. Integrate new preference/cache handling with profile export, recovery
   and deletion; rebuild derived caches after restore.
4. Verify empty-name handling, long names/prompts, category switching, existing
   drafts, workspace/sidebar changes, daily cache hits, duplicate refreshes,
   malformed output, connection failure, and memory deletion during generation.
   Check that selection alone creates no learning record and that practice
   cannot enter the reviewed scoring flow.

The copy and layout work is comparatively small. Daily personalised suggestions
add a backend feature, rather than a purely cosmetic change. Existing provider,
memory and study modules supply the foundations. The larger Design C project
and persistent-workspace implementation remains a separate scope.

## Evidence from this design pass

The three expanded states each contain five visible suggestion instances.
Prototype reactions switch categories and assign the selected prompt to the
composer variable. Screenshots cover the revised home, an expanded explanation
list, the conversation/file workspace and a wrapped case draft. The composer
grows to fit that draft without obscuring its toolbar. The comparison retains
27 screen frames across three columns and nine rows.

This pass changed Figma and planning documents only. No app-code edits, provider
generation, service startup, profile inspection, release or implementation
acceptance testing is claimed.
