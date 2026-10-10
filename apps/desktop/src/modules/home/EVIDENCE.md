# DC06 Home evidence — October 10, 2026

DC06 remains open. The original hidden checks below establish first-run Home,
the optional name preference, responsive pixels and saved-conversation Send/reopen.
The later consumer slice adds the canonical whole-attempt evidence adapter and
the actual default Home → trusted fictional producer → saved-five → whole Study
journey over loopback HTTP and SQLite. Provider transports are synthetic; live
model output and matching installed release acceptance are not established.

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

- Home Attach now selects a real File and hands the canonical saved Chat identity,
  editable draft and volatile `{file,request_id}` intent to the actual Chat owner.
  Parent `7ddf7aeb` forwards it and clears only a matching receipt; Chat `efada051`
  owns review/permission entry and explicit upload. The Home2 hidden journey below
  now verifies actual input/upload/original display/navigation/process reopen. No
  native chooser capability is claimed.
- Quick practice's actual Home consumer now starts the backend-pinned saved-five
  version through the whole Study owner and navigates the returned attempt id.
  The loopback proof below covers successful publication/commit/reopen and lost
  acknowledgements. Integrated hidden provider-success pixels remain unperformed.
- Eligible `assessment-test-answer` now resolves through Russell's published
  `committed_evidence_in(conn,evidence_id)` authority. Home consumes only the
  allowed scalar learning fields and checks suppression in its transaction.
- Connected daily-generation consumers, applicable project/goals inputs, and their
  acceptance remain open. This offline hidden run did not generate a bundle.
- Expanded offline Home repeats its unavailable notice (capture 0002). Chat’s
  “Teaching” label wraps awkwardly at desktop size (0007, 0008, 0010); that owner
  observation was reported separately. Neither changes the durable send result.
- Live model output, physical Windows dialogs/accessibility/scaling, external
  sign-in and matching installed acceptance are outside this development evidence.

Do not mark DC06 complete before its real consumers are connected and verified.

## Later canonical evidence and saved-five consumer slice

Owned implementation commits: `ca90e7cf` (canonical evidence red cases),
`e269b7bb` (safe evidence consumer), `377cdc453a87d395c7e9a0113857417bb203f601`
(default Quick practice and volatile File handoff), and
`de5d19a89bde316256fb216e46bcd75f3f6b988e` (actual consumer and late-source checks).
The only authored source paths are Home service/tests and `modules/home/**`.
Parent generation authority `dce4d88f`, Russell `af5aa155` (local `8994b7f7`),
Zeno `89b9057a` and actual producer proof `538ac6b8` (local `3a602d28`) were consumed.
Parent `7ddf7aeb` merged as `fc57a1d6`; its sole conflict was the owned Home test
tail/import, both preserved. `65d11720` then merged as `885e397f`. No unowned
conflict resolution or source edit occurred.

Home's model material from whole-attempt evidence is limited to `topic_id`,
`mode`, `origin`, `review_quality`, `reviewed`, `bank_cohort_eligible`, `assisted`,
`repeat`, `score_bucket`, `outcome` and `correct`. The owner validates immutable
commitment/evidence/version/item pins and current live sources. Home pins the
canonical evidence digest, then rechecks context/policy/settings/epoch and
suppression before publication. Private stems, keys, choices, feedback, raw case
content and source identities never become Home model material. Personal edits
of reviewed-origin material remain personal; assisted/repeat flags stay distinct.

Home's default Quick practice helper invokes only the published volatile ChatTest
route after explicit Send. It validates exact-five, pinned-version Study and
untimed descriptors, then calls `startStudyAttempt(versionId,stableKey)`. It
navigates the returned attempt id, keeping source text/UUID/result receipts in
React memory. Lost initial acknowledgement reuses the raw command UUID; lost
Study acknowledgement reuses the backend's key for the fresh fictional version.
The default Attempts page reads that attempt without another start.

Stop holds Send/Attach until its acknowledgement resolves. Confirmed cancellation
keeps the draft and permits a new request only on later explicit Send. A published
winner retains its saved receipt; an unconfirmed stop retains the same request
for status/replay. File creation/handoff similarly retains the draft and stable
creation/intent keys on failure. Home does not send a message or upload a file
while handing off an attachment.

| Receipt under `C:/Renulus/scratch/design-c/home/` | Result and scope |
| --- | --- |
| `whole-evidence-red02.xml` | Genuine red: actual commitment produced zero Home activities before the consumer |
| `whole-evidence-green01.xml` | 11 actual whole-evidence cases passed; real DDL and selected ProviderManager with synthetic transport |
| `whole-evidence-full01.xml` | All 52 backend cases passed in 117.26 seconds |
| `consumer-seams01.xml` | 25 Home behavior/helper tests passed; mocked seam responses, not producer acceptance |
| `home-connected-backend01.xml` | Eight late-publication/cache source cases passed; initial connected harness failed |
| `home-connected-red01.xml` | Retained renderer failure: test expected radio; actual saved Study rendered checkbox |
| `home-connected-green02.xml` | Two actual default renderer/HTTP consumers passed, no response or artifact fixtures |
| `home-connected-backend02.xml` | Actual loopback orchestration and DB/export/profile assertions passed in 13.23 seconds |
| `merged-consumer-seams02.xml` | 28 Home/Chat Attach behavior tests passed on merged shell/Chat source |
| `merged-home-full03.xml` | All 61 backend cases, including opt-in actual renderer/DB orchestration, passed in 179.40 seconds |

The first harness also had a Windows subprocess output decoding failure; the
rerun explicitly captured UTF-8. No producer or consumer code was changed to
make either locator/capture correction. Failed receipts were retained.

The connected proof starts an owned loopback backend from the real assembled
app and migrates its synthetic SQLite. The original synthetic subscription
transport comes from the owner-published producer test; ProviderManager chooses
Codex/GPT 6.1 Sol using a synthetic token. Home daily suggestions use their
separate synthetic transport adapter. Actual HTTP acknowledgements are consumed
and discarded to simulate loss; no success response is fabricated.

Across the two journeys, final SQLite contains exactly two immutable versions,
two Study attempts and two durable start receipts, with one committed evidence
row and one daily-suggestion job. Four fictional transport calls are the two
original question batches plus their separate privacy reviews. No generation
job or memory job is created by the volatile Home source. Its raw marker is
absent from every owned profile file and canonical export; each volatile run
erases source text/source identity after publication.

`npm run build` passed on both `fc57a1d6` and `885e397f`, including TypeScript.
The existing ignored dependency junction was used; no installation or live
provider call occurred.

## Home2 actual Attach and reopen checkpoint

The source stayed frozen at `e3475c97f77a5038811e2082be846e9c394aeaab` for all seven
captures below. Parent `4708adf1` was normally merged as `dd6927db` before the
initial launch. That launch exposed an input locator issue: the Home file input
had an ARIA name but no id/native HTML label for the controller descriptor. Owned
commit `e3475c97` added `id=home-attachment` and an associated hidden **Attach file**
label without changing visible layout. Its 25 Home tests and desktop build passed
(`native-input-seams04.xml`). The controller then restarted the app. No capture
from the initial `dd6927db` launch is claimed. Parent's later canonical `319ff190`
integration was separate from this frozen owned run.

Controller root: `C:/Renulus/scratch/dcctl/home2`; owned synthetic profile:
`C:/Renulus/scratch/dcctl/home2/c/s-67dcdb3f/p`. The documented client used this
exact worktree, the declared Python/helper roots and the separate fixture root
`C:/Renulus/scratch/dcctl/home2-fixtures`. Windows remained hidden/nonfocusable.
No credentials, account connection, owner profile or live provider was used.

The [verified evidence manifest](C:/Renulus/scratch/dcctl/home2/c/s-67dcdb3f/out/evidence-manifest.json)
indexes PNG dimensions/bytes/hashes, source, controller client/server bytes,
fixture, all four persistence checks, logs and closed receipt. Its SHA-256 is
`cabd03483d8ce8998d09db9a8254ed3afd01a8f5cb6dbdaa6e4a6c454354c63b`.
Every screenshot was visually inspected; all content images are 1384×921.

| Capture | Actual observed state |
| --- | --- |
| [0001](C:/Renulus/scratch/dcctl/home2/c/s-67dcdb3f/out/capture-0001.png) | Home draft before file selection |
| [0002](C:/Renulus/scratch/dcctl/home2/c/s-67dcdb3f/out/capture-0002.png) | Chat File review, exact draft retained, permissions unselected |
| [0003](C:/Renulus/scratch/dcctl/home2/c/s-67dcdb3f/out/capture-0003.png) | Explicit display/cache permissions, Confirm attach enabled |
| [0004](C:/Renulus/scratch/dcctl/home2/c/s-67dcdb3f/out/capture-0004.png) | Canonical attachment saved, draft retained |
| [0005](C:/Renulus/scratch/dcctl/home2/c/s-67dcdb3f/out/capture-0005.png) | Actual original Markdown visible in workspace reader |
| [0006](C:/Renulus/scratch/dcctl/home2/c/s-67dcdb3f/out/capture-0006.png) | Navigation reopen, same draft and attachment |
| [0007](C:/Renulus/scratch/dcctl/home2/c/s-67dcdb3f/out/capture-0007.png) | Process reopen, same draft and attachment |

Home held the synthetic draft **Original synthetic Home attachment draft. Keep
this text while I review the source.** Actual controller upload selected the
observed `input[type=file][id=home-attachment]`; it did not invoke a Windows dialog.
Home created the saved canonical Learn conversation and handed the File plus
draft to Chat. Chat initially displayed its review form without uploading. The
explicit user permissions were display and local-original cache only, source
owner **Renulus original synthetic fixture**, reference **Original synthetic
development fixture; display and local storage permitted.** Confirm attach then
published the attachment. Model input/derivation remained false. Open file showed
the original varied nephrology Markdown; passage discussion remained unavailable
for that permission/extraction state.

The 327-byte original
[synthetic-home-notes.md](C:/Renulus/scratch/dcctl/home2-fixtures/synthetic-home-notes.md)
has SHA-256 `96a546730ee410c005b52dbfdf6619ffd8244763651407f61fc2fda28643f69d`.
Canonical identity is `{type:learn_thread,id:thread_e03488e8c39b413c84a367178f71af3c}`;
attachment is `attachment_8d1ed370039f42e2a3e7ee1809592660`.

The [read-only checker](C:/Renulus/scratch/dcctl/home2/verify_home_attachment.py)
opened only that owned SQLite with `mode=ro`, resolved the original inside the
profile and verified its bytes/hash. The separate
[index checker](C:/Renulus/scratch/dcctl/home2/index_owned_home_evidence.py) validated
all four receipts and equality after publication/reopens.

| Persistence checkpoint | Create / draft / attach receipts | Attachments/originals | Messages / runs / assessment jobs / memory jobs |
| --- | --- | --- | --- |
| [Before upload](C:/Renulus/scratch/dcctl/home2/c/s-67dcdb3f/out/attachment-before-upload.json) | 1 / 1 / 0 | 0 / 0 | 0 / 0 / 0 / 0 |
| [After upload](C:/Renulus/scratch/dcctl/home2/c/s-67dcdb3f/out/attachment-after-upload.json) | 1 / 1 / 1 | 1 / 1 | 0 / 0 / 0 / 0 |
| [Navigation reopen](C:/Renulus/scratch/dcctl/home2/c/s-67dcdb3f/out/attachment-navigation-reopen.json) | 1 / 1 / 1 | 1 / 1 | 0 / 0 / 0 / 0 |
| [Process reopen](C:/Renulus/scratch/dcctl/home2/c/s-67dcdb3f/out/attachment-process-reopen.json) | 1 / 1 / 1 | 1 / 1 | 0 / 0 / 0 / 0 |

The draft stayed exact, revision 1, SHA-256
`8f3918278a95e4a1c3da8a8e6f7b15712d28b9e1013a52403d7ea4fc08aa1acc`.
Conversation revision advanced from 2 to 3 on attach and stayed there across both
reopens. Display/cache stayed true; model input/derivation/index/embedding stayed
false. These count durable effects, not intercepted HTTP requests.

The [closed controller receipt](C:/Renulus/scratch/dcctl/home2/c/s-67dcdb3f/out/receipt.json)
records three hidden launches, two restart closes and final requested close, all
normal with empty forced/remaining PID lists. It records six window-created and
three renderer-ready events, fault null, and the same main-entry SHA-256 as Home1.
The idle client was disconnected after app/backend close.
[Logs](C:/Renulus/scratch/dcctl/home2/c/s-67dcdb3f/out/logs.ndjson) retain expected
offline HTTP409 and debugger lifecycle messages; this is not a zero-error claim.

No new narrow/zoom captures or hidden Quick practice provider-success pixels
were performed in Home2. Home1 retains its separately scoped responsive/name/
offline/single-send proof; the actual loopback renderer suite retains successful
saved-five/Study proof. Live output, native dialogs/accessibility/scaling and
matching installed acceptance remain open, as do the applicable daily-generation
project/goals consumers. This checkpoint does not close DC06.
