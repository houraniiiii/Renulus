# Using Renulus

Renulus is an English-language Windows learning space for nephrology. For the
selected installation and current delivery status, see [Running Renulus](RUNNING.md).

## Start and connect

Open the **Renulus** shortcut or double-click **Start-Renulus.cmd** in the supplied
folder. Allow the learning window to open, then use **Today** or the navigation
rail. **Ctrl+K** opens **Find a destination**. Local runtime readiness and your
learning subscription are separate statuses.

In **Connections → Learning subscriptions**, choose **Continue with ChatGPT**
under **Codex**. Complete sign-in in your browser using your own account. If you
need an account or subscription, complete that provider setup first; if you
already have one, sign in with that account. Connecting another application
does not connect this Renulus profile.

For a saved account, use **Check models**. Choose **Use Codex** when offered and
check the **Selected** badge. To reconnect an expired or different account, use
**Disconnect**, then **Continue with ChatGPT** again. During sign-in,
**Reopen sign-in in browser**, **Check sign-in status** and **Cancel sign-in**
help you finish or restart the attempt.

Requests stay within your explicitly selected subscription and these models:

| Subscription | Approved model labels |
| --- | --- |
| Codex | `gpt-6.1-sol`, `gpt-6-astra`, `gpt-6-luna` |
| OpenCode Go | `mimo-v2.6-pro`, `deepseek-v4.1-flash` |

**OpenCode Go** currently shows **Learning requests paused** pending confirmation
of educational eligibility. **Check and save Go key** checks account listings;
it does not enable learning requests. Model listing also does not prove a
successful response. Read connection errors and recheck availability; Renulus
does not silently substitute another model or subscription. Reviewed quizzes
and saved study material can be used without a model connection.

## Learn and Test

In **Learn**, enter **Your nephrology question**, choose a **Topic** or
**Explore freely**, then **Ask Renulus**. **Teaching style** defaults to
**Direct explanation**; select **Guided teaching** for guided study. Ordinary
discussions appear under **Continue learning** for resuming later. Use **Stop**
to interrupt a response and read any partial-response or evidence notice.

In **Test**, choose:

- **Reviewed quiz**: select **Track**, **Topic** and **Questions**, then
  **Start reviewed quiz**. Choose an option and **Commit answer** before reading
  the reasoning and sources. Committed answers cannot be changed.
  **View source help** marks the attempt assisted.
- **Generated practice**: describe what to practise, choose one to five
  questions and **Generate practice** with an eligible connection. These
  questions and keys are **Generated · unreviewed**; their results remain
  separate from reviewed assessment. Retrieved sources do not review the key.

## Choose your programme and plan

Open **Today → Study preferences**. Set **Hours per week**, an optional
**Exam date**, **Track** and topics, then **Save preferences**. The tracks are
**General nephrology** and **ESENeph preparation**. Leave topics unchecked to
use all available topics in your selected track; free exploration remains
available across nephrology.

ESENeph currently has a partial mapping. Read **Mapped domains and gaps** beside
the plan; mapped questions do not establish complete exam coverage. Exam
simulation is unavailable. Test also has its own **Track** selector.

Use **Suggest a plan** after saving preferences. **Your next study** shows
activities and reasons, including recorded mistake reviews. **Start** opens
the activity; change **When**, **Mark done** or **Skip** to adjust it. Reviewed
quiz history lets you revisit reasoning. Study activity and conversations do
not establish mastery.

## Add and check Library material

Use **Library → Add to library → Document** for authorised reusable teaching
material. Enter **Title**, **Choose a study document**, confirm permission to
read, store, index and use the file locally, then **Add document**. PDF, image,
text and supported Office files are accepted within the displayed limits.
**Study note → Add note** saves deliberately added text.

Check **View import details** and **Import status**. Queued or processing
revisions are not yet searchable; wait for processing to finish. For a failed
or cancelled import, **Retry import** asks you to select the original again.
**Collected sources** lists acquisitions; queuing selected files is a separate
step from making their passages ready.

Use **Find a passage → Search**, then **Inspect citation**. A **Source** control
in Learn also opens citation inspection in Library. Check the passage, edition,
permissions and locator, then **Open original**. A reported physical page counts
from the start of the file, rather than its printed page label. Unknown pages
open without a page jump; exact passage highlighting is unavailable. Office
originals offer **Save original** for opening in a compatible application.
Current-guidance search excludes sources whose currency is unverified.

## Temporary and saved Cases

In **Cases**, enter a title and learning question, then **Start temporary case**.
Case text, discussion and added originals remain temporary until you choose
**Save case**. A reopened saved snapshot also needs **Save changes** to retain
later edits or discussion. Close the current case before reopening one from
**Saved cases**.

For a PNG or JPEG you want to keep locally, select **Use this file for →
Keep original image**, choose **Image to keep in case**, review the preview,
then **Keep image in case**. Finish with **Save case** or **Save changes** to
keep it after closing. This path works without a model connection and does not
send the image to a model. **View original** opens a retained case original.

**Local text extraction** lets you review and correct attachment text before
**Use extracted text**; it reads words, not clinical images. **Image discussion
with selected subscription → Send image for discussion** is a separate, explicit
provider request, subject to displayed availability. Input acceptance does not
verify interpretation quality.

The case-scope banner follows you through Learn and **Practise from this case**.
Return to Cases to save; navigation alone does not save. Choose
**End temporary context** to return to ordinary study.

## Inspect and correct Memory

**Memory** shows retained learning, preferences and goals, including eligible
learning captured during ordinary study. Use **Search retained learning**,
**Edit → Save changes** to correct a record, and **History** to inspect previous
text. **Remove history → Remove revision history** keeps the current record.
**Delete → Delete learning and history** removes the record and its history
from recall. Case input cannot be retained here; use
**Open memory in study context** if the scope guard appears. Retained learning
personalises study; it is not scientific verification.

## Updates and retrieval permissions

In **Updates**, select a topic and **Check last 30 days**, or open
**Source checks → Check now** for a registered source. New discoveries wait for
review. **Open publication**, inspect its evidence and permissions, complete
the review fields, then **Save reviewed update**. **Dismiss** does not make
material current. Tracking a public file requires
**Permission for a public digest check**; other processing permissions remain
separate.

For opt-in checks while Renulus is open, expand **Automatic checks**, select
sources and **Check interval**, enable **Check my selected sources automatically**,
then **Save automatic checks**. **Check selected now** also works for a saved
selection with automatic checking off. Read failures and **Last success** dates:
a failed check retains previous evidence and does not establish freshness.

**Connections → Sources and retrieval** holds optional personal retrieval keys.
Enable and select a tool deliberately, with daily request/credit limits, or use
**Use key-free sources**. Provider billing terms apply; failed attempts count
toward request limits. These tools do not change the learning subscription.

## Back up and restore

Open **Connections → Your study data**:

- **Download full backup (ZIP)** includes saved records and eligible Library
  and saved-case originals. Choose a save location and wait for confirmation.
- **Export records only (JSON)** omits original attachment bytes; it cannot
  recover missing originals.

Credentials, search indexes and the external acquisition catalogue are excluded.
Keep external collection originals separately. Temporary case changes are not
a saved backup.

To restore, **Choose ZIP backup or JSON export**, review its date, contents and
omissions, acknowledge the displayed deletion limits, then choose
**Restore full backup** or **Restore records only**. Restoration merges saved
records and preserves newer deletions known to this installation; an older copy
alone cannot know about later deletions elsewhere. Check **Recovery status**
while local search and memory indexes rebuild. Use **Retry local rebuild** if
offered, then **Refresh recovery status**; a completed records restore does not
by itself mean search is ready.
