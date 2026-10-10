# DC06 Home evidence — October 10, 2026

DC06 remains open. This checkpoint establishes disconnected development behavior
for first-run Home, the optional name preference, responsive Home pixels, and the
actual saved-conversation Send/reopen consumer. It does not establish successful
model output, attachment input, the saved-five Study consumer or release acceptance.
Only this report is changed by the checkpoint commit; source changes remain in
the previously integrated Home slices.

## Source and isolation

The exact worktree was verified as `C:/Renulus/dev/worktrees/dc-home`, branch
`codex/dc-home`, before writes. Normal merges preserved the shared work:

| Local source | Integrated baseline | Captures |
| --- | --- | --- |
| `bd298567ca3f9b73dd403cb9ef87405aa724b6c3` | `a87a6fc3`: shared shell/controller and Home | 0001–0003 |
| `a13c83555c9f87e32b52e71efb8c8d14648faf21` | `c19d1493`: actual Chat page | 0004–0008 |
| `f07f2460966e6847faa28b6417915e79d092c4fd` | `387ea97d`: banner/context/callback repair | 0009–0010 |

AGENTS, README, PROJECT_BRIEF, WORKSPACE, PRODUCT, DESIGN, the C implementation
spec, reconciled design report, APP_CONTROL and shared contracts informed the
work. Impeccable, Interface Design and Figma design-to-code were applied before
the earlier design-context reads. References: Figma file `zV8JiWybVHP1UxJtLbZjEt`,
Home `4:3926`; categories `67:4874`, `67:5095`, `67:5316`. The downloaded Home
reference is `C:/Renulus/scratch/design-c/design/evidence/home.png`.

The controller used the compact owned root `C:/Renulus/scratch/dcctl/home1`,
profile `C:/Renulus/scratch/dcctl/home1/c/s-df2d0df9/p`. All observed windows
were hidden and nonfocusable. No provider/account connection, credentials or
live inference was used. Public helper assets came from the declared contributor
helper root. The source app was built using the existing ignored desktop
`node_modules` junction to `C:/Renulus/dev/node_modules`; no installation occurred.
The three launches recorded the same main-entry SHA-256
`c4b3e337fa58ee3e2754ffbf2d485cc74d0421db6a7d339ed36f3a5cc223d615`.

## Actual hidden journey

- Fresh Home displayed the generic **Welcome back**, **How can I help you today**,
  Attach and Send. Auto, introductory filler and illustrative suggestions were absent.
- Explain a topic, Discuss a case and Quick practice each exposed an honest offline
  empty state; only one category expanded. Switching categories retained the typed
  synthetic draft. This journey did not display generated prompts.
- Settings → Preferences normalized `  Ada Synthetic  ` to `Ada Synthetic`,
  revision 2. The greeting survived navigation and both process restarts.
- Home pixels were inspected at outer sizes 1440×900, 1000×720 and 640×540.
  Captured content sizes were 1424×861, 984×681 and 624×501. Home controls remained
  visible without clipping or overlap; the compact rail and wrapped pills were usable.
- One Home Send created a saved-default canonical Learn conversation and handed
  its typed identity plus one volatile `{text, request_id}` send intent to Chat.
  Home never called the streaming helper. Chat immediately attempted the request
  and displayed the expected `connection_required` failure, one user message and
  the retained draft. No assistant response is claimed.
- Returning to the saved chat through navigation and reopening the process retained
  the same conversation/message/draft without additional durable send effects.
  The final shell snapshot had a paragraph banner and one main h1.

## Screenshot and receipt index

Every screenshot below was visually inspected. PNG sizes, dimensions and SHA-256
hashes, source commits and supporting-artifact hashes are in the verified
[evidence manifest](C:/Renulus/scratch/dcctl/home1/c/s-df2d0df9/out/evidence-manifest.json).

| Capture | Source | Observed state | Content pixels |
| --- | --- | --- | --- |
| [0001](C:/Renulus/scratch/dcctl/home1/c/s-df2d0df9/out/capture-0001.png) | `bd298567` | Fresh generic offline Home | 1424×861 |
| [0002](C:/Renulus/scratch/dcctl/home1/c/s-df2d0df9/out/capture-0002.png) | `bd298567` | Draft retained; Discuss a case expanded | 1424×861 |
| [0003](C:/Renulus/scratch/dcctl/home1/c/s-df2d0df9/out/capture-0003.png) | `bd298567` | Normalized name saved in Preferences | 1424×861 |
| [0004](C:/Renulus/scratch/dcctl/home1/c/s-df2d0df9/out/capture-0004.png) | `a13c8355` | Named Home after restart | 1424×861 |
| [0005](C:/Renulus/scratch/dcctl/home1/c/s-df2d0df9/out/capture-0005.png) | `a13c8355` | Named Home at 1000×720 outer | 984×681 |
| [0006](C:/Renulus/scratch/dcctl/home1/c/s-df2d0df9/out/capture-0006.png) | `a13c8355` | Named Home at 640×540 outer | 624×501 |
| [0007](C:/Renulus/scratch/dcctl/home1/c/s-df2d0df9/out/capture-0007.png) | `a13c8355` | Actual saved Chat send; disconnected failure | 1424×861 |
| [0008](C:/Renulus/scratch/dcctl/home1/c/s-df2d0df9/out/capture-0008.png) | `a13c8355` | Chat navigation reopen; same message and draft | 1424×861 |
| [0009](C:/Renulus/scratch/dcctl/home1/c/s-df2d0df9/out/capture-0009.png) | `f07f2460` | Named Home after repaired-shell restart | 1424×861 |
| [0010](C:/Renulus/scratch/dcctl/home1/c/s-df2d0df9/out/capture-0010.png) | `f07f2460` | Saved Chat process reopen; same message and draft | 1424×861 |

The [controller receipt](C:/Renulus/scratch/dcctl/home1/c/s-df2d0df9/out/receipt.json)
records three launches, two restart closes and the final requested close, all
normal with empty forced/remaining PID lists. Events were six `window-created`
and three `renderer-ready`; `fault` was null. The idle client was disconnected
after the owned app/backend had closed.

The [redacted logs](C:/Renulus/scratch/dcctl/home1/c/s-df2d0df9/out/logs.ndjson)
retain expected HTTP409 resource messages, two operator locator failures, and
debugger lifecycle messages. The ambiguous Connections heading and overly broad
status locator were replaced by unique/scoped locators and the actions succeeded.
One malformed JSON CSS request failed at the client only. This is not a zero-error
log claim.

## Durable single-send evidence

The [read-only persistence checker](C:/Renulus/scratch/dcctl/home1/verify_owned_home.py)
opened only this owned synthetic SQLite with `mode=ro`. The separate
[manifest checker](C:/Renulus/scratch/dcctl/home1/index_owned_home_evidence.py)
validated all three saved checkpoint files and the closed controller receipt.

Canonical identity: `{type:learn_thread,id:thread_f936b97b45394210876e4191db644a63}`.
The one stable send request ID was `86a387b4-d4e4-42d1-8e1e-dda41872430f`.

| Checkpoint | Create receipts | Send receipts | Learn runs | User / assistant messages | Draft |
| --- | ---: | ---: | ---: | --- | --- |
| [Before reopen](C:/Renulus/scratch/dcctl/home1/c/s-df2d0df9/out/single-send-before-reopen.json) | 1 | 1 | 1 | 1 / 0 | Exact retained text |
| [Navigation reopen](C:/Renulus/scratch/dcctl/home1/c/s-df2d0df9/out/single-send-after-navigation-reopen.json) | 1 | 1 | 1 | 1 / 0 | Exact retained text |
| [Process reopen](C:/Renulus/scratch/dcctl/home1/c/s-df2d0df9/out/single-send-after-process-reopen.json) | 1 | 1 | 1 | 1 / 0 | Exact retained text |

At every checkpoint the run state was `failed`, error `connection_required`,
command receipt state `error`, normalized name revision 2, and daily-suggestion
job/cache counts zero. These are counts of durable effects; no HTTP interception
was performed, so no exact network request count is claimed.

## Existing application verification

Earlier Home source slices `f984303e`, `d4e835ac` and `3767ee19` supplied the
implementation and focused tests. Recorded verification before this report:

- Backend: 41 passed in `tests/study/test_home_suggestions.py`, using the assembled
  app and real DDL. Coverage includes the NOT NULL job checkpoint fix, selected
  ProviderManager routing through synthetic transport adapters, exactly fifteen
  validated prompts, deduplication, dated cache/failure behavior, canonical source
  existence and policy/epoch/settings changes, cancellation/recovery, separate
  bounded name receipts, and actual export/restore. Name is exported; daily cache
  and name-command receipts are local-only. These adapters prove the application
  seam and do not establish live model behavior.
- Frontend: 12 passed with `npm run test --prefix apps/desktop --
  src/modules/home/index.test.tsx src/modules/chat/chat.test.tsx` after integrating
  the actual Chat page. Coverage includes one explicit handoff, same-turn duplicate
  protection, retry identity, separate prefill, draft preservation and Chat intent
  consumption.
- `npm run build --prefix apps/desktop` passed at all three source checkpoints,
  including `f07f2460`, with TypeScript validation.

No source was changed for this evidence-only checkpoint, so those passing suites
were not repeated solely to write the report.

## Remaining integration and observations

- Attach needs the Knowledge/Chat input seam; visible Attach is not actual file-input
  acceptance. No attachment or native chooser capability is claimed.
- Quick practice still requires DC16’s saved five-question producer and the shared
  DC13 Study attempts engine. Keep the explicit prerequisite; do not substitute
  legacy generation or start a reviewed Test.
- Eligible `assessment-test-answer` input awaits Russell’s explicit payload and
  cohort/eligibility contract. Preserve its original kind; do not infer the shape
  or read reviewed answer keys. Existing legacy evidence is not the new consumer.
- Connected daily-generation consumers, applicable project/goals inputs, and their
  acceptance remain open. This offline hidden run did not generate a bundle.
- Expanded offline Home repeats its unavailable notice (capture 0002). Chat’s
  “Teaching” label wraps awkwardly at desktop size (0007, 0008, 0010); that owner
  observation was reported separately. Neither changes the durable send result.
- Live model output, physical Windows dialogs/accessibility/scaling, external
  sign-in and matching installed acceptance are outside this development evidence.

Do not mark DC06 complete before its real consumers are connected and verified.
