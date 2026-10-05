# Updates application acceptance

Verified October 5, 2026 (UTC), for issue #11. Isolated worktree:
Renulus-wt-updates-acceptance; branch: build/updates-acceptance; base: 5d437c7e.
The application acceptance gate passes on this branch, ready for parent
integration. This decision concerns the implemented checking and review rules;
it does not establish that any real publication has received educational review.

## Material fixes

Mounted failure sequences exposed recovery controls that cleared an error or
reloaded settings without retrying the failed operation. Updates now retries
the actual review/dismiss, literature check, refresh, library sync or read action.
Review retry retains inspected evidence and uses the visible current draft,
including when an older submission fails after the draft is edited. A confirmed
read retry clears its failure.

Automatic checks retries the failed save, manual batch, cancellation or status
read. Unsaved source selections and cadence survive failures and status recovery.
Successful and failed background polls both preserve a failed mutation's recovery
action; an unconfirmed disabling request cannot disappear behind a status poll.
Registered source/publication checks, candidate lookup, tracking and stopping
also have working retries. Tracking retry uses the visible permission text.
Retry controls are unavailable during another pending operation. Existing Flow
layout and source-family boundaries remain the visual authority.

Production changes are confined to the three Updates renderer components.
Runtime production, Knowledge, shared API/platform files, schemas, manifests,
source registers, assessment and Cases are unchanged. No migration is added.

## Connected application journeys

tests/updates/test_application_acceptance.py uses the real local HTTP routes,
SQLite migrations and repositories, version-1 Updates outbox, Knowledge journal
and LanceDB retrieval. Only publisher transport, extraction and embeddings are
controlled. The original bundled pack supplies its 27 installed topic records.
Test profiles contain only explicitly synthetic source bodies and review facts.

Four ready synthetic revisions cover T06 acute kidney injury, T08 chronic kidney
disease and T21 transplantation. T08 has two copies of the same edition with
different original hashes. The actual official-link producer creates pending
notices, deduplicates repeat checks and rejects summary-only review. Explicit
synthetic inspected evidence passes through the review API and outbox into
exact acquired-copy metadata; current-only retrieval then returns those copies.

A tracked publication changes bytes at the same URL while its synthetic ETag
stays unchanged. The digest producer creates one pending notice and clears
reviewed currency for both previously verified T08 hashes through the real
journal. AKI and transplant copies remain eligible. Offline checks retain the
digest and successful-check date, report failed/stale, and invent neither
retraction nor access loss. Edition/hash, publication date, final state and
correction facts stay independent of fetch dates.

After app restart the exclusions persist. Dismissing the observation does not
restore currency. Deliberate re-review restores only the selected T08 hash; the
other acquired copy remains excluded. The metadata-only Library version lookup
returns both original hashes without bodies or original paths.

A second HTTP journey saves four selected free routes while automation stays
off: K01 plus Europe PMC metadata for T06, T08 and T21. Manual Check selected now
checks all four; its three metadata discoveries remain pending and abstract text
is discarded. An offline batch records four failures and retry-wait without
advancing successful-check dates. Jobs and the completed run survive restart.
API-key/case-text fields, an ERA member-source selection and an arbitrary topic
are rejected before publisher transport. Captured requests are bounded anonymous
GETs to the controlled registered hosts; no case marker leaves the application.

The existing Updates suites additionally cover exact retraction identity,
independent draft/final/replacement/correction facts, edition/hash validation and
status aggregation, older-than-100 lookup/pagination, private hosts/redirects,
scheduled caps/retries, no overlap, cancellation and app shutdown. This lane
reuses the existing producer, scheduler and Knowledge status contract.

## Dated free network proof

The existing opt-in helper, tests/updates/live_official_check.py
--run-free-official, made exactly three free requests in a task-owned profile.
Metadata-only proof was recorded at 2026-10-05 00:14:58.591451 UTC under
.local/runtime/updates-official-20261005-001455/network-proof.json.

- Registered K01 PDF:
  https://kdigo.org/wp-content/uploads/2026/04/KDIGO-2024-CKD-Guideline.pdf.
  First check baseline, second unchanged; 5,838,922 bytes; SHA256
  0b77a9e32ca6c7bbccbddf902be4427bf8bc0d2dd7e3ffbc18042f602f371b27.
  The server Last-Modified value, Fri, 17 Apr 2026 08:45:21 GMT, is a transport
  validator, not a publication or educational-review date.
- Europe PMC T08: 25 records checked/discovered from 3,198 reported hits;
  truncated=true; discoveries remain pending.
- paid_providers_enabled=false; educational_review_performed=false;
  whole_app_or_installer_proof=false. PDF bytes were discarded.

This establishes dated reachability and bounded anonymous transport. It does
not establish exhaustive discovery, the latest final guideline or reviewed
educational implications. No additional live checks were needed.

## Checks and gate

- Parent bootstrap Python: python -m pytest tests/updates -q --tb=short:
  **53 passed**. One existing Starlette TestClient deprecation warning.
- Desktop: node node_modules/vitest/vitest.mjs run src/modules/updates:
  **25 passed** in four files, including seven new mounted failure regressions.
  Confirmed failures were reproduced before their fixes.
- npm run build: TypeScript, Vite renderer and build-electron.mjs passed.
- git diff --check passed before commit.

The Python environment and public Node dependencies were reused from the parent
bootstrap. Synthetic profiles, build output and dependency junctions are ignored.
No parent profile, acquired corpus, credential or source-register correction was
read/copied/changed. There is no new browser screenshot or live UI claim in this
lane: renderer evidence comes from mounted behavioural tests and the build.

Issue #11's application gate is satisfied: an eligible changed source is detected,
deduplicated and held for explicit evidenced review; failure/staleness remain
accurate; source checking accepts installed topics rather than raw case details.
The acquired-copy currency seam demonstrably controls ready-document retrieval
and preserves unrelated copies across review, dismissal and restart.

Actual acquired-file importer/provenance and rights verification, scientific
review, corpus completeness, paid-provider integration and native/installer
acceptance are independent gates. Synthetic imports exercise the public repository
and acquired-copy metadata, not the actual acquired-file loader. Nothing here
promotes scientific status, distribution rights, immutable question keys or
historical scores merely from observed network changes.

Related earlier evidence: updates-evidence.md, updates-scheduling-evidence.md
and updates-acquired-version-binding-evidence.md in this directory.
