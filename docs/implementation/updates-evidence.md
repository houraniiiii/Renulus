# Source checks and update review

October 4, 2026 · issue #11. Runtime watch metadata derives from the single
SOURCES register. Official publication-link changes are fingerprinted and
deduplicated; first check is a baseline. A bounded key-free Europe PMC adapter
discovers dated research/correction/retraction metadata for installed topic
labels. Raw case/chat details cannot be supplied as literature queries.

Detected changes enter a pending queue. A learner/assistant review records an
educational summary and inspected evidence; home consumes only reviewed entries. Dates
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

## Reviewed currency, exact impact and Flow follow-up — October 4, 2026

The next slice adds migration `updates/migrations/003-reviewed-source-status.sql`.
Neither applied 001 nor 002 is rewritten. Parent integration is reported at
`50f4a72c`, including F0 `54b3b38a` / `db7e2825` and assessment `299fcb08`.
Knowledge, shared storage/manifests, assessment, clinical content, acquisition
and the separate retrieval lane remain with their owners. This worktree has not
merged those lanes and does not infer ingestion rights or processing completion
from source-register prose.

New reviewed entries require a real inspected evidence URL, page/section,
finding, inspection date and explicit attestation. A future inspection date,
summary-only review or uninspected evidence is rejected. Legacy reviews remain
historical records with no fabricated evidence backfill. Dismissal needs no
educational review and preserves the discovery and journal. Request hashes make
review retries idempotent; an older request cannot replace a newer review head.

Publication date, revision date, draft/final/preprint/commentary status, current
review, correction, retraction, replacement scope and access/repository changes
are separate partial metadata facts. They do not come from fetch dates, link
names or access failures. Same-URL digest observations invalidate only the prior
latest-final/content-review applicability for that URL. Existing publication,
access and scientific status remain independently recorded. Adding article IDs
to an existing canonical URL preserves earlier publication/access facts.

A scientific retraction or its clearance requires the original article's
explicit DOI, PMID or PMCID. The notice has its own identity. Conflicting
identifiers/canonical article URLs are rejected; no L03-family retraction is
published. Reviewed topic/locator scope narrows impact. Mere final verification
does not itself create a content-impact flag.

Updates reads immutable original M8 question/case citation projections using
pinned source IDs and locators, including case-stage citations and historical
versions. SQLite extracts only source records, citations, version/topic/objective
IDs. Stems, keys, user case records and attempts do not cross this seam and are
not changed. Annotations are owned by Updates; educational content correction
and assessment presentation remain separate maintenance work.

The narrow M4 consumer is `registry["updates"].affected.needs_re_review(kind, id,
version)`, or `GET /updates/affected/{kind}/{id}/versions/{version}`. It returns
`needs_re_review` plus annotations (source ID, locator, basis, discovery/review
state and update URL), without a question stem, key or score. It does not rewrite
an immutable question version or invalidate an historical attempt. Entry impact
lists also support bounded pagination, default 100, maximum 250; the UI uses 10.
The real M4 consumer is not integrated in this branch.

Europe PMC requests bounded core metadata, discarding abstracts/full text.
Publication-type and reported preprint/retraction/correction fields are discovery
hints requiring inspected evidence. An exact refresh uses `EXT_ID:<id> AND
SRC:<source>`, without a recent-publication date filter. Changed metadata queues a
new pending observation while retaining the earlier reviewed record. Missing or
failed metadata retains the prior metadata/last success and cannot establish a
retraction. Topic checks cap at 25 records for each of at most five installed
topic labels and return hit counts/truncation plus actual partial/failure state.
Raw question or case text is not a query parameter.

Flow now uses server review-state pagination and actual queue counts (50 per
page). Older entries can be opened, refreshed, reviewed and marked read through
direct ID routes. The review form requires evidence, collapses optional metadata
and related-topic fields, keeps a draft after a failed refresh, and distinguishes
unapplied library metadata from an acknowledged change. Source checks expose
tracked-publication digests separately from link checks and retain last success
on failure. An empty sync result cannot claim a library change was applied.

## Parent-owned library metadata contract

The confirmed synchronous hook is `registry["knowledge"].update_source_status(event)`
or `registry["update_source_status"](event)`. `apply_source_status` is also accepted
as a compatibility fallback. Updates owns event creation/journal/retry only.
The parent owns the knowledge matcher, metadata validation, import replay,
ordered journal and `knowledge-002-source-status.sql` migration.

Example reviewed event (synthetic):

```json
{
  "contract_version": 1,
  "event_id": "review_<stable-request-hash>",
  "source_id": "L03",
  "identity": {
    "canonical_url": "https://europepmc.org/article/MED/111111",
    "pmid": "111111"
  },
  "scope": {"topic_ids": [], "locators": []},
  "changes": {"retracted": true},
  "evidence": {
    "kind": "reviewed-publication",
    "reviewer": "learner",
    "reviewed_at": "2026-10-04T12:00:00+00:00",
    "references": [{
      "url": "https://europepmc.org/article/MED/999999",
      "locator": "Synthetic original-article relationship notice",
      "finding": "Synthetic notice identifies original PMID 111111",
      "checked_on": "2026-10-04",
      "inspected": true
    }]
  },
  "reason": "Synthetic reviewed implication"
}
```

Optional identity members are `pinned_source_id`, DOI, PMID and PMCID. Review
changes use the existing metadata names: `publication_status`,
`publication_date`, `revision_date`, `latest_final_verified`, `content_reviewed`,
`review_due`, `correction`, `retracted`, `superseded`, `supersedes`,
`replaced_topics`, `excluded_pages`, `repository_removed` and `access_changed`.
Omitted fields remain unknown/unchanged; no observation promotes source rights.

Observed digest events have `event_id: "observed:<update-id>"`,
`evidence.kind: "publication-digest"`, `observed_at`, `previous_sha256` and
`observed` (SHA-256, size, format, final URL and validators). Their only changes
are `latest_final_verified: false` and `content_reviewed: false`. These events
establish neither scientific retraction nor publication/access/rights facts.

Expected acknowledgment is `{"state":"applied","matched_revisions":1}` or
`{"state":"no-match","matched_revisions":0}`. No/malformed acknowledgment is
a failure, never an applied change. The parent must match the exact registered
publication, reject identifier conflicts, preserve evidence and date/order,
and keep stale or access-changed revisions out of current retrieval. Unmapped
pack-only/pinned-only or locator scope returns `no-match`; it cannot broaden to a
source family. Later matching imports/replacements replay the ordered journal
without changing the original import request hash. These guarantees are the
parent's integration contract; callable tests in this branch use a recording
adapter, not the parent's real repository.

Updates stores pending/unavailable/failed/no-match jobs durably in
`update_library_changes`; startup retries at most 100 and an entry's Sync retries
its jobs. Applied jobs are acknowledged once and not reapplied. Entry payloads
expose observation and review sync states even before an educational review.

## Network proof and application-rule proof

`python tests/updates/live_official_check.py --run-free-official` completed on
October 4, 2026 at 20:37:41 UTC. Exactly three free official fetches ran with paid
providers disabled: registered K01 PDF baseline, the same PDF unchanged, and an
installed CKD topic query to Europe PMC. Evidence is retained in the ignored
profile `.local/runtime/updates-official-20261004-203737/network-proof.json`.

K01 URL was `https://kdigo.org/wp-content/uploads/2026/04/KDIGO-2024-CKD-Guideline.pdf`.
The PDF was 5,838,922 bytes, SHA-256
`0b77a9e32ca6c7bbccbddf902be4427bf8bc0d2dd7e3ffbc18042f602f371b27`.
Last-Modified was April 17, 2026; that is a server validator, not an asserted
publication date. Europe PMC returned 25 metadata records against 3,400 hits,
`truncated: true`; all discoveries remain pending. This proves bounded official
transport/metadata reachability at that date, not a publisher change sequence,
full evidence coverage, latest-final review or educational correctness.

Synthetic publisher sequences test byte changes/reversions and metadata notices,
draft/final/correction/access independence, exact original-article retractions,
scoped immutable impact, legacy migration/restart, direct older-than-100 records,
idempotent review and callback failure/no-match behavior. UI tests exercise the
real local API transport with synthetic responses: evidence required/submitted,
server counts and page 101+, retained failed-refresh draft, exact original
article/replacement scope, evidence-free dismissal, empty sync and truncation.

The Windows browser check uses the built Flow renderer plus real isolated
content/Updates APIs at `.local/runtime/updates-ui-20261004` with a synthetic
fetcher. Desktop and 390px viewport layouts were inspected; no external publisher,
paid provider, knowledge engine, private collection or model is used. Packaging
and integrated retrieval eligibility remain the parent/F0 acceptance work.
The aggregate `npm run build` passes typecheck and Vite compilation but then
finds no `scripts/build-electron.mjs` in this baseline. That is not a renderer
failure or a Windows installer pass; no out-of-scope packaging fix is made here.

Final follow-up verification: `python -m pytest tests/updates -q --tb=short` —
**22 passed**; `npm test -- src/modules/updates/updates.test.tsx` — **6 passed**;
`npm run typecheck` and the existing Vite renderer build pass;
`git diff --check` is clean. This is module/application-rule and bounded network
evidence, with no real educational review, integrated M4/library acceptance or
installer claim.
