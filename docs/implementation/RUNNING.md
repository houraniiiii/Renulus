# Running Renulus

Renulus is the Flow Windows learning application. For its controls and everyday
workflows, see [Using Renulus](USING_RENULUS.md).

## Windows delivery

The owner chose unsigned installation and acceptance on the current Windows PC
on October 5, 2026. The installed app bundles CPython 3.14.4 and manages its CPU
document/OCR and embedding helpers. Doctors need no Python, uv, Node, npm, GPU,
Docker or local model server setup. Signing and a separate clean PC/VM are
optional future distribution work.

Open the owned **Renulus** desktop shortcut or double-click **Start-Renulus.cmd**
in the supplied folder. Allow the managed runtime to become ready, then use
**Today** or the navigation rail. **Ctrl+K** opens **Find a destination**. Local
runtime readiness and subscription access have separate statuses.

For a local session, use reviewed **Test**, saved **Library** passages and
originals, **Cases** with explicit Save, editable **Memory**, or **Today** study
preferences and planning. These workflows do not require a generative response.
The October 6, 2026 selected-Codex Probe02 ended with `subscription_limit`;
successful live answers and automatic learning capture remain unproved.

For generation, open **Connections → Learning subscriptions**, connect your
account if needed, **Check models**, choose **Use Codex** when offered and confirm
the **Selected** badge. Only `gpt-6.1-sol`, `gpt-6-astra` and `gpt-6-luna` are
allowed for Codex, subject to account availability. OpenCode Go learning
requests remain paused; its approved models remain `mimo-v2.6-pro` and
`deepseek-v4.1-flash`. There is no silent subscription switch or paid generation
fallback. Reviewed Test, saved study material and manual planning are available
without a generative connection. See [connection instructions](USING_RENULUS.md#start-and-connect).

## Preserve data and account profiles

The source checkout and replacement binaries are on C:. Preserve the existing
E: collection, learning data and private Renulus account profile in place. The
normal learning profile is:

`E:/Renulus-native-delivery/desktop-20261005/data/learning`

The shortcut and `Start-Renulus.cmd` use `scripts/start-renulus.ps1`. Its ignored
`.local/delivery.json` selects the installed executable and this learning
profile. Moving the checkout or updating binaries does not require resetting
the learning profile or an already saved account. Use **Check models** for a
saved account; reconnect deliberately if it has expired. Credentials remain
private and are excluded from study backups. Another app's sign-in does not
connect Renulus.

Each learning profile owns its canonical records, Library copies, managed
helpers and derived indexes. Keep external acquisition originals separately;
third-party acquired files are excluded from the public bundle and Git.
Contributor development must use a separate profile.

## Delivery status

As of October 6, 2026, product source remains frozen at
`699938f20efb6bbc2cf8df684cc5c6c3450e6eaf`. Normal launch now selects the matching
installation at `C:/Renulus-native-delivery/desktop-20261005/installed-699938f2`.
The parent has accepted the bounded local installed scopes below, with an
external live subscription blocker. All times in this table are on
**October 6, 2026, in UTC**.

| Outcome | Recorded scope and limit |
| --- | --- |
| [Package / Install](finalise-installed-699938f2.md) | Package47784 exited 0 at **09:45:34**; Install95706 (`336d4498`) exited 0 at **09:57:02**, with matching EXE, ASAR and source. |
| [Recovery02](finalise-installed-699938f2.md#performed-recovery-and-retained-inventory) | Exited 0 at **10:23:18**; parent admitted it at **10:31:41**. Both local indexes rebuilt, six restored originals/citations were inspected, newer deletion survived backup replay, and three ordinary closes/two reopens completed. Five current operations plus twelve source-qualified historical proofs; no full fresh sweep or repeated initial restore. |
| [Connected03](finalise-connected-continuation-699938f2.md) | Exited 0 at **11:12:00.7575338**. Seven remaining restore/reconciliation/deletion operations passed with three retained Connected02 proofs. Corrected Memory, saved PDF/PNG originals and a manual plan survived restore. Deletions survived ZIP replay in the fresh-restored profile; the source profile retains its saved case. Ordinary main/backend close completed. |
| [Gap01 + Gap02](finalise-installed-gap-continuation-699938f2.md) | Gap02 exited 0 at **11:58:09**. Retained Gap01 operations prove local OCR/search and physical-page citations for one synthetic scanned PDF plus one free K01 catalogue check. Gap02 proves reopen/persistence and closed table/units extraction; it repeated no import or check. |
| [Maintenance03](finalise-maintenance-699938f2.md) | Exited 0 at **12:34:25.741436**; parent accepted at **12:36:07**. All **969,663 canonical bytes** stayed unchanged through uninstall/reinstall/reopen. Source-profile saved PDF (**1,285 bytes**) and PNG (**813 bytes**) originals returned status 200 with matching hashes. Main21084/backend12800 closed normally in **12.973 seconds**, with no remaining owners. |
| [Codex Probe02](finalise-live-blocker-699938f2.md) | Terminal at **11:31:48.7296032**: selected `gpt-6-astra`, blocked by `subscription_limit`, outer exit 1. Ordinary main/backend close completed. No successful direct answer, automatic capture, dependent live journeys or image request. |

The unsigned installer is **1,010,355,641 bytes**, SHA256
`ce1ed76147585477412a8d5319d485fdb03c5e1f3daae2ed02c2ca6669261f5d`.
The continuations retain explicit proof origins; all earlier failed aggregates
remain failed, including Recovery01, Connected01/02, Gap01 and Probe01/02's
outer terminals. Documentation does not change the frozen product or package.

Maintenance03 verifies the source profile's intentionally retained saved case;
the Connected deletion checks belong to a different fresh-restored profile.
All prior maintenance failures remain failed. Independent storage qualification
retains the six original `035ca7bd` storage phases, eight mapped artifact matches
and the scoped unused Win32 path difference; no new SQL workload ran. See
[the parent maintenance report](finalise-maintenance-699938f2.md) for receipt pins.

The parent promoted `.local/delivery.json` to `installed-699938f2` and updated the
owned shortcut to C:, preserving the E: learning profile and previous pointer
and shortcut. Only the parent's read-only final confirmation remains after a
comparison false negative; that check launched no app and did not repeat the
pointer update. Promotion is complete. The owner's live-access decision remains
unresolved; see [current continuation](CONTINUATION_20261005.md).

The K01 result establishes dated discovery, not latest-final guidance. Accepted
local installation does not establish successful live generation or capture;
the full product goal remains open. Clinical image interpretation remains unproved.
The installed gap observation found clipped controls at 200% zoom; full reflow
and accessibility are not accepted. Earlier evidence remains in
[historical validation](final-validation.md).

## Contributor startup

These commands prepare a source development build. From the repository root,
run `uv sync --extra test`. In `apps/desktop`, run `npm ci` and
`npm run dev:electron`. This builds the renderer/Electron entry points and opens
an isolated development profile. To retain a chosen development profile, set
an absolute `RENULUS_PROFILE` before starting; keep it separate from the E:
learning/account profile. Without a delivery record, `Start-Renulus.cmd` uses
the prepared contributor build. The launcher's `-CheckOnly` option checks its
selection without opening the app.

Keep the approved stack: Hermes's Python runtime and Electron/React foundation;
SQLite for canonical records; Mem0 OSS with its local Qdrant client for derived
memory; Docling/Docling-core HybridChunker, FastEmbed and LanceDB OSS for
documents and retrieval. Renulus manages the pinned public helpers. Do not
include source documents or credentials in runtime staging. See
[confirmed decisions](../DECISIONS.md) for the stack and exact model constraints.

A browser development route uses Vite against an authenticated local backend.
Its ignored `.local/dev-config.json` contains the app-owned loopback origin/token;
keep it private. The Electron main process owns the backend session token.

## Learning and data

[SOURCES](../SOURCES.md) is the development source/acquisition register. Check
each imported file's rights, publication edition, retrieval/review dates,
corrections and scope replacements. Acquisition dates and dated research notes
do not certify latest-final guidance; current-only retrieval requires reviewed
final currency metadata. Library citation inspection leads to retained originals
and locators.

Daily Cases and attachments remain temporary until **Save case**; later saved
case changes need **Save changes**. Learn/practice navigation does not save
them, and case facts are excluded from learner Memory. Full ZIP backups include
eligible saved originals; records-only JSON exports omit their bytes. Restore
merges records and reconciles newer deletions known to this installation; an
older backup alone cannot know about later deletions elsewhere.

After restore, inspect **Connections → Your study data → Recovery status**,
including **Library search** and **Learning memory**. Use **Retry local rebuild**
when offered, then **Refresh recovery status** until both report readiness.
A Retry starts asynchronous work; accepting it or restoring records does not
by itself mean search is ready. Recovery02 and populated Connected03 recovery
are accepted within the scopes above; inspect your own restore's status and
originals. See [backup and restore instructions](USING_RENULUS.md#back-up-and-restore).
