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

At the October 6, 2026 handoff, the frozen product source is
`699938f20efb6bbc2cf8df684cc5c6c3450e6eaf`.
Package47784 completed at **09:45:34 UTC on October 6, 2026**. Its unsigned
installer is **1,010,355,641 bytes**, SHA256
`ce1ed76147585477412a8d5319d485fdb03c5e1f3daae2ed02c2ca6669261f5d`.
Install95706, attempt `336d4498`, completed unsigned with exit 0 at **09:57:02
UTC on October 6, 2026**, after 487.566 seconds. The parent reports that the
installed EXE, ASAR and source match the actual package. Native Recovery
started at **09:58:22 UTC**; matching native, live connected and maintenance
acceptance remain unproved at this milestone. The normal launcher still
selects `installed-3ff9b0d6` until those
matching journeys are accepted. Documentation changes do not change frozen
manufacture.

The parent integration lane owns execution, acceptance receipts and launcher
promotion; see [current continuation](CONTINUATION_20261005.md). Earlier
observations remain in [historical validation](final-validation.md). This guide
does not establish native acceptance of the new installed build, live generation,
clinical image interpretation, clinical accuracy or full accessibility.

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
each imported file's rights, publication edition, review date, corrections and
scope replacements. Acquisition dates and dated research notes do not certify
latest-final guidance; current-only retrieval requires reviewed final currency
metadata. Library citation inspection leads to retained originals and locators.

Daily Cases and attachments remain temporary until **Save case**; later saved
case changes need **Save changes**. Learn/practice navigation does not save
them, and case facts are excluded from learner Memory. Full ZIP backups include
eligible saved originals; records-only JSON exports omit their bytes. Restore
merges records and reconciles newer deletions known to this installation; an
older backup alone cannot know about later deletions elsewhere.

After restore, inspect **Connections → Your study data → Recovery status**,
including **Library search** and **Learning memory**. Use **Retry local rebuild**
when offered, then **Refresh recovery status**. Restored records do not by
themselves establish search readiness. The matching installed recovery journey
remains under acceptance. See [backup and restore instructions](USING_RENULUS.md#back-up-and-restore).
