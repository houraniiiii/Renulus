# Source checks and update review

October 4, 2026 · issue #11. Runtime watch metadata derives from the single
SOURCES register. Official publication-link changes are fingerprinted and
deduplicated; first check is a baseline. A bounded key-free Europe PMC adapter
discovers dated research/correction/retraction metadata for installed topic
labels. Raw case/chat details cannot be supplied as literature queries.

Detected changes enter a pending queue. A learner/assistant review with an
educational summary is explicit; home consumes only reviewed entries. Dates
distinguish publication, discovery, review, last check and last successful check.
Failed checks retain previous success and expose failure/staleness. Public
fetching blocks private hosts and redirects outside the official source.

Four meaningful checks pass: changed source deduplication/review, failed-fetch
state, bounded topic-only metadata discovery and private-host/redirect blocking.
A real key-free Europe PMC query returned HTTP 200 and dated nephrology
publication metadata. This is retrieval evidence, not educational review.

## Source-currency follow-up — October 4, 2026

Worktree `Renulus-wt-updates`, branch `build/source-currency`, starting at
`5c6c1dc6`. Source acquisition and its uncommitted register corrections remain
separate; this branch reads its dated `docs/SOURCES.md` without modifying it.
Updates owns this backend, its UI and tests. Shared storage/manifests and other
modules are not edited.

The first slice adds opt-in public publication checks through the existing
SourceFetcher. Select a URL from registered PDFs, checked official publication
links or installed pinned source metadata; record permission for anonymous
digest checking. No credential, arbitrary case query, paid API, model or external
collection is used. At most 100 enabled publications are tracked. GET responses
are bounded to 16 MB by default (20 MB ceiling), 45 seconds including redirects,
official HTTPS hosts and public DNS addresses. Redirect credentials, private
hosts and non-443 ports are rejected. Cookies and environmental proxy/auth
configuration are not reused. Bytes are hashed and discarded; the local record
retains SHA-256, size, format, final URL, ETag and Last-Modified.

The first complete fetch is a baseline. Changed bytes at the same URL queue a
pending update even with unchanged validators or publication links. Identical
bytes do not duplicate it; reverting to earlier bytes is a new observation.
Empty, oversized, incomplete or failed responses retain the prior digest and
last success. A public PDF returning a login/HTML response fails visibly. A
failed latest check is stale even if the prior success is recent. A digest change
does not establish an edition, publication date, final guidance or educational
review. HTML decoration and PDF packaging changes can trigger review too.

Entry review now reads its result by primary key; older records no longer depend
on a newest-100 scan. `GET /updates/entries` supports review-state filtering,
stable date/ID ordering, totals/counts and offset pagination (default 50, maximum
250). `GET /updates/entries/{id}` and read/review return proper missing-ID errors.
Migration `updates/migrations/002-publication-currency.sql` is additive; applied
`schema.sql` / `updates-001` is unchanged. Populated-001 upgrade/restart is tested.

Verification: `python -m pytest tests/updates -q --tb=short` — **10 passed**.
Synthetic tests cover same-URL byte changes and reversions, false unchanged
validators, no body persistence, offline/format/size failures, opt-in/permission
boundaries, anonymous redirects, older-than-100 review/read and migration restart.
These use real Updates/content APIs and SQLite migrations with other modules
isolated; they prove application rules, not publisher network behaviour.

Baseline full-app bootstrap is blocked by a pre-existing knowledge collection
annotation error (`list[str]` after a method named `list`, at `collection.py:170`).
No out-of-scope fix is made here. The first coordination message to Hegel
(`01a10863-2aac-76a3-a884-8c66cefba9ff`) was accepted; subsequent contact reports
`not_found`. Reviewed lifecycle/evidence, affected-version annotations, UI
pagination/tracking and a bounded live free-source check follow this first slice.
No real educational review has been performed by these synthetic checks.
