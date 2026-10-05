# Flow final product journey and coverage record

Compiled **2026-10-05 UTC** from completed isolated application checks. Parent
integrated the final focus fixes as `8f6de976`. This documentation-only record
does not rerun the route audit or certify later integration changes. The parent
is checking the final renderer/build separately.

## Destinations and completed journeys

These are the exact canonical renderer hashes, in Alt+1–8 order. Ctrl+K opens
destination search; Escape returns focus to its trigger. `#/home` and an empty
hash resolve to Today; `#/test` is an alias for Test. Handoff payloads and case
scope remain volatile rather than entering the URL.

| Destination / route | Completed journey and evidence boundary | Evidence |
| --- | --- | --- |
| Today — `#/study` | Original pack: 27 topics; a wrong T03 answer yields a review task from its unchanged 0/1 score. Moves, skips, completion and preferences survive reload/proposal/restart. Failure tests preserve drafts/focus and retry the operation. | [Study final](study-final-evidence.md) |
| Learn — `#/learn` | Disconnected state observed; controlled-provider citations travel through actual SSE/navigation to Library. Integrated API checks establish ordinary-thread retention, retry/cancellation and temporary-case exclusion. | [Citation journey](library-passage-citation-evidence.md), [learner acceptance](learner-retention-acceptance.md) |
| Library — `#/library` | Synthetic text/PDF/PNG retain the cited revision/passage and only its locators. Wrong/ineligible passages fail. Unknown pages stay unknown; confirmed `page_missing` offers deliberate whole-original recovery. Original bytes/media types round-trip locally. | [Inspector](library-source-inspector-evidence.md), [exact passages](library-passage-citation-evidence.md) |
| Cases — `#/cases` | Explicit Save, close/reopen and saved-snapshot/new-changes banner observed through real local API/UI. Learn retains temporary context; End clears it. No generated discussion was requested; this audit predates the later image follow-up. | [Renderer review](renderer-final-review-evidence.md) |
| Test — `#/assessment` | Pending T20 exposes the K01 notice/locator and Updates navigation. Wrong T08 retains pinned versions and 0/1. SQLite tests cover detected/reviewed/dismissed annotations without altering attempts. Opening reveals the warning; editing retains focus. Generated practice is disabled without an eligible connection. | [Renderer review](renderer-final-review-evidence.md), [focus fix](focus-final-evidence.md) |
| Memory — `#/memory` | Study view and temporary-context guard observed. Controlled-provider API checks establish activity capture, correction/history deletion, restart suppression and case exclusion. Activity is not mastery or reviewed general knowledge. | [Renderer review](renderer-final-review-evidence.md), [learner acceptance](learner-retention-acceptance.md) |
| Updates — `#/updates` | Real producers/outbox/journal/retrieval enforce pending discovery and exact acquired-version review. Same-URL changes invalidate all copies of that publication; dismissal does not restore currency; re-review restores only the selected copy. Offline retains last success/digest. Bounded daily automation requires opt-in; manual batches work while off. | [Acceptance](updates-acceptance-evidence.md), [binding](updates-acquired-version-binding-evidence.md), [scheduling](updates-scheduling-evidence.md) |
| Connections — `#/connections` | Go shows Learning requests paused, distinct from account/model status, with no Use Go action. Keyboard/empty-key states observed without login. Controlled checks cover Codex start/exchange/retry/cancel/expiry and explicit selection. | [Renderer review](renderer-final-review-evidence.md), [Connections](connections-auth-evidence.md), [Go gate](go-eligibility.md) |

## Evidence types and measured coverage

- **Actual renderer/local application:** all eight destinations were visited at
  measured 1280×800 and 900×800; 620×720 navigation exposed all eight. Valid
  captures had no horizontal overflow or renderer exceptions. Updates compact
  selection now reveals the chosen publication; refresh failure is visible beside
  its action while the review draft remains intact. The final T3 focus journey
  measured 1683×1051. Its compact resize did not apply, so it adds no compact
  browser proof. [Measurements and checks](renderer-final-review-evidence.md).
- **Controlled transport, real persistence:** Updates acceptance uses real HTTP
  routes, SQLite, Knowledge status replay and LanceDB with synthetic publisher
  bodies/reviews and controlled extraction/embeddings across T06, T08 and T21.
  Study uses the original pack and real assessment producer. Citation checks use
  synthetic bodies and extraction locators. These prove application rules, not
  publisher facts, extraction accuracy or educational review.
- **Dated free network proof:** recorded **2026-10-05 00:14:58 UTC**.
  Exactly three requests checked registered K01 twice (baseline/unchanged)
  and Europe PMC T08 once (25 records, truncated). Bytes were discarded and
  discoveries remained pending. This establishes bounded free reachability, not
  exhaustive discovery or latest-final guidance. [Proof](updates-acceptance-evidence.md).
- **Provider-controlled tests:** SDK/auth/provider fixtures and synthetic SSE
  exercise failure, retention and cancellation. They do not establish a live
  account, consent/token exchange, account-specific model availability, inference
  or image interpretation. The final renderer/focus profiles recorded **zero
  provider and zero live publication calls**; no paid/keyed tool was used.
  [Provider acceptance](provider-acceptance.md).

The completed renderer review passed 75 focused checks and its production build;
the final focus follow-up passed 14 checks and its build. These are separate,
overlapping runs, not an aggregate suite total or the parent final-build result.

## Remaining material gates

- Approved live-account Explain/generated practice, actual account/model access,
  image interpretation and general-learning-point extraction remain unproved.
  Go educational eligibility is unresolved and generation is blocked; an account
  catalogue or saved key cannot promote it.
- Source currency and scientific review remain independent. No link, fetch date,
  digest, dismissal or review of a synthetic fixture establishes final guidance,
  rights, clinical correctness or a revised historical answer key. Discovery is
  bounded; rights-dependent/member sources are excluded from automatic checking.
- The final audit profile had no acquired Library documents/helper assets. Its
  processing-unavailable screen is truthful but proves no corpus processing.
  Parent acquisition/indexing totals and real collection mutations are separate
  evidence; this record neither re-counts nor infers them from register prose.
- Exact passage highlighting is unavailable. Earlier inspector PDF blocking was
  a native-lane finding, not a new unresolved renderer claim: later native page-two
  checks are recorded in [desktop evidence](desktop-evidence.md). Final matching
  packaged/native rendering, recovery and installer verification remain owned by
  the parent/Wegener and are not certified by this record.

No new source/provider checks, acquired bodies, patient data or host profile state
were used to assemble this record.
