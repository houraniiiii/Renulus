# Using Renulus

**Status checked October 10, 2026.** The Design C instructions below describe
connected source at **`009b8780`**. They extend the source reviewed at
`51f208b4`; they do not establish a matching installed release or launcher
cutover. The normal shortcut still opens **Flow `f1c49444`**, content 1.4.2,
at `C:/Renulus/app`, with the learning/account profile at
`C:/Renulus/data/learning`. Former E: paths are compatibility junctions.
Use the [installed Flow reference](#installed-flow-reference) until the lead
publishes the Design C cutover. See [delivery status](RUNNING.md#delivery-status)
and the [October 8 storage report](storage-cleanup-20261008.md).

Renulus is an English-language Windows learning space for nephrology. The
[dated limits](#dated-evidence-and-limits) retain the separate source, live,
native and installed evidence scopes.

## Start and connect

Open the **Renulus** shortcut or **Start-Renulus.cmd**. The installed Flow app
opens **Today**; Design C uses **New chat**, **Projects**, **Tests**, **More** and
**Settings & connections**. **Ctrl+K** opens **Find a destination**. Local runtime
readiness and subscription access are separate. The installed app bundles its
runtime and CPU helpers; doctors need no developer tools, GPU, Docker or model
server setup. Preserve the learning/account profile when updating; a study
backup does not contain account credentials.

In **Learning subscriptions** within Connections/Settings, **Check models**
checks a saved account. For disconnected Codex, choose **Continue with ChatGPT**
and finish in your browser; another app's sign-in does not connect Renulus.
For Go, save your subscription key. Choose **Use Codex**/**Use OpenCode Go** and
check the **Selected** badge and default model. A connected account alone does
not select a subscription. Use the sign-in status/cancel controls for an
incomplete attempt, or **Disconnect** to reconnect an expired account.

| Subscription | Approved model labels |
| --- | --- |
| Codex | `gpt-6.1-sol`, `gpt-6-astra`, `gpt-6-luna` |
| OpenCode Go | `mimo-v2.6-pro`, `deepseek-v4.1-flash` |

Listing a model does not prove a successful response. Requests keep the selected
subscription, with visible errors and no paid generation fallback. Reviewed
questions, saved originals, Notes and Memory editing remain useful without
generation; active-Test restrictions still apply.

## Design C: new chat and retained conversations

On **New chat**, write in **How can I help you today**, then **Send**. Ordinary
learning and Case conversations save by default; Chat receives the message once.
A failed handoff keeps the Home draft; retry that request.

Choose **Explain a topic**, **Discuss a case** or **Quick practice** before
writing a new request, or select a suggestion from that category. Expanding a
category beside an existing draft does not change that draft's intent. One
category expands at a time; a valid daily bundle supplies five suggestions per
category. Selecting one prefills the composer and still needs **Send**. If a
draft exists, choose **Add to draft**, **Replace draft** or **Keep draft**.
Offline/first-run states keep the composer usable without fabricated
suggestions; an older valid bundle shows its date. Quick practice has the
[separate saved-five flow](#explicit-saved-five-and-conversation-tests).

Set **Name for your greeting → Save name** in Settings/Connections. A blank
name uses the generic greeting. Home text and selected intent are volatile:
they survive a policy-only interruption in the same window, but real navigation
or closing can clear them. After handoff, a saved Chat autosaves its draft;
wait for **Draft saved** before closing. Sending commits a message; saving a
draft does not send it. **Teaching** offers **Direct** and **Guided**; **Stop**
interrupts a response. Read partial-response and retry notices.

In a conversation's **Manage** controls, **Rename**, **Project**, **Archive** and
**Delete conversation** have separate effects. Archive retains messages, draft
and originals, makes the chat read-only and removes it from active recents.
Restore it before continuing. Project-linked archived chats can be reopened
from the project's **Chats** list; a general archived-chat browser is not
connected in this source snapshot. Deleting a conversation removes its owned
originals; separately retained learning in Memory remains inspectable.

The empty Chat view offers **Start saved chat** and **Start temporary chat**.
Temporary work is explicitly labelled and excluded from ordinary Memory and
backups. Use **Save conversation** to promote it before adding it to a project.
Closing discards temporary work. The saved-default rule does not change the
explicit-save behavior of [legacy Flow Cases](#temporary-and-saved-cases).

For Case context, use **Edit case context → Save case context**, or **Use
temporary context**. Local image keeping, reviewed text extraction and explicit
image discussion are separate; extraction reads words, not clinical images.
**Explore in Learn**/**Practise from this case** retain scoped legacy handoffs,
separate from the new saved fictional-test flow.

## Design C: Projects, Files and Notes

### Projects and goals

In **Projects**, enter a name and **Create project**. **Chats** offers **New
learning chat**, **New case chat** and **Add saved conversation → Add to project**.
Move an existing saved chat to another project or leave it unassigned. Under
**Documents**, link a ready Library revision; **Unlink** keeps its Library
original. Under **Study goals**, record a goal, optional target date and your
progress/next step. **Mark complete** records your decision, not mastery.

**Show projects** switches between Active and Archived. **Manage project**
provides rename, archive, restore and deletion. Deleting a project removes its
goals and memberships while preserving independent conversations and Library
originals.

### Attach and read files

Home **Attach** carries the selected file and existing text to a saved Chat's
file review; it does not send the text. Review **File title**, **Source owner or
author**, optional **Edition**, and **Permission or licence**, then choose allowed
uses separately:

- **Display this file in Renulus**.
- **Keep a local original when this conversation is saved**.
- **Send selected content to my learning model**.
- **Create learning material from selected content**.

Use **Confirm attach**, or **Retry same attachment** after an uncertain receipt.
Display permission is required; saved attachments also require local-original
permission. The review enforces 64 MiB for saved and 10 MiB for temporary
originals. Keeping a file does not itself request model inference or make it a
searchable Library document. Use **Open file** or the workspace **Files** tab to
read it.

The embedded reader has actual PDF, PNG/JPEG/TIFF, DOCX, XLSX/CSV and
TXT/Markdown/HTML/XML adapters. An accepted upload type does not guarantee an
embedded reader for that type; PPTX is an example. Unsupported, missing,
restricted and extraction-failed states remain visible. Office previews are
bounded reading views, not full Office editors or a fidelity guarantee.

Use **Physical page**/**Image frame**, Previous/Next, Zoom and **Fit width**.
Physical pages count from the file's start, not its printed labels. Tables offer
sheets/row windows; **Find on this page/table window** searches that window.
**Prepare original download → Save original** retains an available original.

Select text and **Ask about selected passage**, or use **Discuss this passage**.
The cited passage enters a Chat draft and needs a separate **Send**. Permissions
and extraction state can prevent passage use even when the original is readable.
On narrow layouts the reader takes the focused pane; **Back to chat** returns.
Closing a workspace tab does not delete its source. Reopening saved workspace
references is distinct from retaining temporary content or unsaved edits.

### Personal and project Notes

Open workspace **Notes → New note**, enter **Note title** and **Note**, then
**Save note**. A save creates an immutable revision. Notes are personal or linked
to the current project; a temporary conversation must be saved before using the
persistent Notes workspace. Unsaved edits survive workspace tab changes in the
same window, but not closing the window.

Use **Revision history** or **Open saved original** to inspect retained text.
A conflict offers **Keep my edits after this revision** or **Replace draft with
latest** after comparison. **Use note in chat** requires a clean saved revision
and prefills a cited draft; it does not send. For notes over 16,000 characters,
open the saved original and select a shorter passage. **Delete note → Delete
all revisions** removes its originals/history and project links; older citations
then show an unavailable source.

## Design C: saved Tests and attempts

**Tests** holds saved sets; **Your attempts** holds work already started. Select
a set and its exact **Saved versions** entry. Choose **Mode: Study/Test** and an
optional timer, then **Continue to Study/Test**. This opens setup without
starting an attempt or timer. **Start Study**/**Start Test** is the explicit
start; **Retry start** checks the same pending start. Resume an existing attempt
by its identity rather than starting again from its version.

| Origin | What it means |
| --- | --- |
| Reviewed bank | Eligible bank questions; reviewed performance separates fresh, assisted and repeat answers. |
| Generated | Selected-model personal practice; validated format does not independently review the key. |
| Imported | Personal material normalised and explicitly reviewed by you; it remains personal practice. |
| Nightly | A saved personal set from the opt-in scheduler; opening it does not start an attempt. |

Origin, review quality and Study/Test mode are independent. Generated/imported/
nightly questions remain personal when used in Test mode or edited by you; they
do not become reviewed-bank mastery evidence. **Edit personal version** creates
a new version; earlier cards and attempts retain their exact pins. **Archive**
is distinct from **Delete saved test**. Deletion makes the collection unavailable
but retains historical attempt and local-report snapshots. Adapted legacy
sessions keep their original commitments and partial denominators; they are
not retroactively graded as whole Tests.

### Commitments, drafts and help

| Action | Study | Test |
| --- | --- | --- |
| Choose/edit an option | An ungraded draft until **Submit answer**. | An editable draft until whole-Test submission. |
| Submit | **Submit answer** locks that answer and reveals feedback. **Finish study** includes committed answers only. | **Review and submit test → Submit test** commits the whole result. Blanks become unanswered. |
| Help | **Hint**, **Sources**, **Notes** and **Ask in chat** record assistance for the question. | Ordinary learning help is restricted until submission. |

Hints/references can be unavailable. Notes/Chat returns to the same attempt;
reopen stale help from the current question. Test supports clear, navigate, skip
and mark for review without correctness. Results retain fresh/assisted/repeat
or personal cohorts; activity does not certify mastery.

Watch **Saving draft…/Saved**. Use the retry under **This action needs recovery**
to check an uncertain save/submission. **Reopen saved attempt** uses the last
backend-saved state and can omit unacknowledged changes; do not create another
attempt to retry. Closing/finishing Study does not grade pending selections.
**Question seems wrong → Save report** stores a local pinned report without
changing key/score. Unavailable content is flagged without rewriting old results.

### Timing and active Test restrictions

Untimed is the default. Select **Use a timer** in setup, or **Add a timer** before
Start. A timed Test begins at **Start Test**, has no pause and continues while
the window is closed. At expiry the backend finalises the drafts it accepted
before the deadline, once; reopening after expiry reads that result. Unsaved
local choices are not a guarantee of receipt before the deadline.

Study offers **Pause study/Resume study**. At Study expiry, choose **Continue
untimed** or **Finish study**; pending choices remain ungraded. An active Test
blocks ordinary Chat, source/Reader/Notes help and backup/export/restore.
Use **Resume Test** to return. Settings and neutral status, Nightly Off and Stop
remain available. Closing an active Test does not remove the restriction.

### Create or import a saved set

**New reviewed test → Save test** saves 1–50 eligible bank questions. **Create
test** chooses a topic and 5/10/20 personal questions through the selected
connection. Progress shows validated/requested counts. Use **Stop generation**,
explicit retry or an offered shorter-count confirmation; partial work is not
silently substituted. Saving starts no attempt or timer.

**Import a test** accepts permitted pasted text or an eligible extracted personal
Library revision. Save the original/terms first; **Normalize with selected
connection** is a separate provider request. Compare candidates with the unchanged
original, resolve keys and confirm each review before **Save N reviewed questions**.
It remains Personal practice. Stop/retry explicitly; deleting an import keeps
its independently published test.

### Explicit saved-five and conversation tests

For Home Quick practice, choose **Quick practice** before typing, or select one
of its suggestions, then **Send**. The connected producer validates and saves
exactly five fictional questions, then opens one untimed Study attempt pinned
to that version. It does not use legacy one-to-five generation or silently accept
a shorter set. Failure retains the draft. Retry checks the existing request;
**Stop practice** is explicit. If publication won before Stop, the notice keeps
the draft and **Send** opens that saved set's Study handoff.

In Chat, **Create test from conversation → Create fictional test** offers
5/10/20 questions from sent messages and visible Case context. The request source
is volatile; only the validated fictional artifact is saved.
**Cancel test creation** stops unfinished work. Once saved, **Start Study** opens
one untimed attempt, or **Open saved test** reads the exact version. Creation
alone starts neither Study nor a timer. Pending raw source/retry state is
volatile across closing; a published set remains in Tests.

### Opt-in Nightly generation

Open **Settings & connections → Preferences → Nightly generation**. It is Off
by default, with **22:00** and **5 questions** as initial choices. Set local
**Preferred time**, choose 5/10/20 and **Save preferences**; **Turn on** opts in.
Renulus must be running, with an eligible selected connection and saved learning
context. It generates one set per eligible night and can catch up once after
sleep, without building a missed-night backlog. Reopening or restoring waits
for the next eligible time; it does not resume an old provider task.

**Tests → Nightly practice** shows real progress and **Open saved test** selects
the published version without starting an attempt. **Review retained work**
opens failed/review-needed work for explicit recovery. **Turn off** and **Stop
generation** are available during an active Test; publication already completed
remains saved. Temporary conversations, private originals and raw Case text do
not supply Nightly learning context.

## Inspect and correct Memory

Open **More → Memory** in ordinary study scope, or use **Open memory in study
context** if the scope guard appears. **Search retained learning**, **Edit → Save
changes** and **History** inspect and correct canonical retained learning.
Compare a conflict before **Use latest revision**. A correction keeps the edited
current fact and suppresses recapture of the old source; it does not alter an
answer commitment, key, score or cohort.

**Remove history → Remove revision history** keeps the current record.
**Delete → Delete learning and history** removes recall and suppresses recapture.
Unavailable/deleted sources are excluded from derived learning context; they do
not silently erase independent historical attempts. Personal, assisted and
repeat evidence retain those distinctions, and unanswered items do not create
answer learning. Case input, temporary content and private originals are not
ordinary learner Memory. Retained learning personalises study, not scientific
verification.

**Recall status** describes the derived index separately from saved editable
records. **Retry pending jobs** can process eligible capture through the selected
model; **Rebuild recall index** repairs local recall from retained records.
**Cancel job** explicitly cancels a capture. Ordinary policy/context interruption
can allow a later automatic scan of unchanged eligible evidence; correction,
suppression, deletion, unavailable sources and explicit cancellation remain
barriers. Restore-specific inference acceptance is qualified below.

## Library, Updates and retrieval permissions

**Library → Add to library → Document** deliberately imports reusable permitted
material. Enter title, file and permissions, then **Add document**; **Study note
→ Add note** retains deliberately entered text. Obtain ERA/institutional files
through your authorised access and retain edition and permitted use. Public
availability does not grant every processing/redistribution right.
[SOURCES](../SOURCES.md) records development acquisition boundaries.

**View import details/Import status** distinguish queued, processing and ready;
an earlier ready revision can remain available. **Retry import** may need the
original again. **Collected sources** does not mean searchable. Use **Find a
passage → Search → Inspect citation → Open original** to check edition, rights
and locator; unknown locators need not give exact highlighting/page jumps.
**Remove from library** excludes retrieval and cleans app-owned copies; heed
**Storage cleanup pending**. External originals/backups remain independent.
Current-guidance search excludes sources whose currency is unverified.

In **Updates**, choose a topic and **Check last 30 days**, or **Source checks →
Check now**. Discoveries need review: **Open publication**, inspect evidence and
permissions, then **Save reviewed update**. **Dismiss** does not make it current.
Automatic checks are opt-in while the app runs: select sources/interval and
**Save automatic checks**. **Check selected now** is separate. Failures retain
previous evidence; read **Last success**, publication/review dates, corrigenda,
replacements and retractions. A recent download or dated research note does
not establish latest-final guidance.

**Sources and retrieval** in Settings/Connections holds optional personal keys.
Select and enable a tool deliberately with request/credit limits, or **Use
key-free sources**. Provider billing terms apply and failed attempts count
against request limits. Retrieval configuration does not select or change your
learning subscription.

## Back up and restore

Open **Settings/Connections → Your study data**:

- **Download full backup (ZIP)** includes saved records and eligible app-owned
  Library, saved Case, Chat and Notes originals in Design C.
- **Export records only (JSON)** omits original bytes and cannot recover them.

Credentials/provider connection settings, derived indexes, helper weights and
the external acquisition catalogue are excluded. Safe greeting/Nightly
preferences are retained; Home suggestions and local scheduler/retry state are
not. Temporary conversations, unsent Home text, unsaved Notes and unsaved legacy
Case changes are excluded. Keep external originals and account access separately.

Finish an active Test before exporting or restoring. If recovery is busy, finish
or cancel the named active work and retry. **Choose ZIP backup or JSON export**,
review date, contents and omissions, acknowledge deletion limits, then **Restore
full backup** or **Restore records only**. Reselect a ZIP if its preview expires.
Restore merges records and preserves newer deletions known to this installation;
an old backup cannot know about later deletions elsewhere. Deletion does not
erase an existing backup, external original or another profile's copy.

Design C restore interrupts unfinished generation, Nightly, daily-suggestion and
import-normalization work while retaining valid checkpoints. Reading progress
or reopening does not replay those provider tasks. Generation/import need an
explicit retry with still-valid source/permissions; Nightly waits for a future
eligible time. Local rebuild readiness is separate from model capture.

**Source recovery limit at `009b8780`:** restored Memory evidence is marked for
explicit inference capture, but the automatic Memory consumer does not yet read
that marker. Still-eligible boundary-interrupted evidence can be reconsidered
automatically after recovery. Do not treat this snapshot as proof of inference-free
Memory restore. Corrections, deletions and explicit cancellation still constrain
capture. This open consumer must be rechecked before installed cutover.

Check **Recovery status → Library search/Learning memory**. For **Blocked**,
**Partial** or **Failed**, read cleanup/error details, use **Retry local rebuild**
when offered and **Refresh recovery status**. **Try again** retries a status read;
**Not reported** or an accepted Retry is not readiness. Inspect originals and
citations too. Original-file rollback pending requires the displayed restart
before another restore/rebuild. Archive size/format limits still apply.

## Installed Flow reference

These controls describe the normal `f1c49444` installation until Design C
cutover. Shared connection, source-currentness and local-recovery guidance above
still applies; new C Chat/Projects/Notes/saved-Test controls require C source.

### Learn and Test

In **Learn**, enter **Your nephrology question**, choose **Topic**/**Explore
freely**, then **Ask Renulus**. **Teaching style** defaults to **Direct
explanation**; **Guided teaching** is optional. **Continue learning** resumes
ordinary discussions. **Stop** interrupts a response.

In Flow **Test**, **Reviewed quiz → Start reviewed quiz** chooses Track, Topic
and Questions. **Commit answer** locks an answer before reasoning/sources;
**View source help** records assistance. **Generated practice → Generate
practice** produces one to five **Generated · unreviewed** questions through an
eligible connection. It is distinct from C's exact saved-five flow and whole
Study/Test commitment model.

### Choose your programme and plan

Open **Today → Study preferences**, set Hours per week, optional Exam date,
Track and topics, then **Save preferences**. General nephrology and partial
ESENeph preparation are available. Unchecked topics use all available topics
in the track; free exploration remains available. Read **Mapped domains and
gaps**; exam simulation is unavailable.

**Suggest a plan** supplies **Your next study** with reasons. **Start**, **When**,
**Mark done** and **Skip** let you act or adjust manually. Conversations, plans
and completion marks do not establish mastery. These legacy planning controls
remain available through More/Today in C.

### Temporary and saved Cases

Flow **Cases → Start temporary case** keeps text, discussion and originals
temporary until **Save case**. Reopened saved Cases need **Save changes** for
later edits/discussion. Navigation to Learn or **Practise from this case** does
not save them. **End temporary context** returns to ordinary study; closing
unsaved work discards it and excludes it from learner Memory/backups.

For a local PNG/JPEG, **Use this file for → Keep original image → Keep image in
case**, then Save. **View original** reads a retained original without a model.
**Local text extraction → Use extracted text** requires reviewing words.
**Image discussion with selected subscription → Send image for discussion** is
an explicit, separate request, subject to actual availability; upload acceptance
does not prove clinical interpretation quality.

## Dated evidence and limits

- **October 7, 2026:** source receipts establish real Sol Explain/generated
  practice/automatic Memory and both approved Go Case discussions. Matching
  installed `f1c49444` accepts new T18/partial ESENeph content, retained history,
  corrected ready Memory and reopen. See [delivery](DELIVERY_20261007.md) and
  [continuation](FINISH_20261007.md). These receipts do not establish today's
  account availability or new Design C live/installed acceptance.
- **October 6:** Astra Probe02 returned `subscription_limit` and made no image
  request. Later Sol success keeps its own scope. Physical Windows speech,
  scaling and high contrast remain **issue #21**. The bounded Case PDF page 1/
  Library 200% reader check proves reachable controls through ordinary scrolling,
  not full accessibility; see [reader evidence](finalise-reader-reflow-699938f2.md).
- **October 6, 11:51:42.812 UTC** (13:51:42.812 Europe/Warsaw): the K01 catalogue
  check returned baseline. Gap02 retained it with automatic checking off and
  no repeated fetch. This is dated discovery, not latest-final/corrections/
  retraction acceptance or proof that an installed correction affects learning.
- **October 6 recovery:** Recovery02 accepted Retry/rebuild, original inspection,
  newer-deletion reconciliation and three closes/two reopens. Connected03 accepted
  populated ZIP recovery; deletion checks used a separate fresh-restored synthetic
  profile. The source profile intentionally kept its PDF/PNG Case. Original
  failed aggregates remain failed; inspect each actual restore's status.
- **October 6 Maintenance03:** exit at 12:34:25.741436 UTC, accepted at 12:36:07 UTC.
  Uninstall/reinstall/reopen preserved canonical data and saved PDF/PNG originals,
  then closed normally. This supplies no new live/automatic-capture acceptance.
  See [maintenance provenance](finalise-maintenance-699938f2.md).

Design C source instructions were checked against the committed Home/Chat,
Projects/Notes/Reader, saved Tests/whole attempts, Nightly, Memory and recovery
implementations, alongside the [C spec](../planning/DESIGN_C_IMPLEMENTATION_SPEC.md)
and [reconciled review](design-c-reconciliation.md). Synthetic transport and
hidden controller checks do not prove live provider behavior, physical file
dialogs, clean-machine installation, signing or complete clinical accuracy.
