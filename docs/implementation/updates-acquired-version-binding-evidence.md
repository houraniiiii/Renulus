# Updates: exact acquired-version review binding

Verified 2026-10-04 UTC. Issue #11: Check source currency and review educational
updates. Worktree: Renulus-wt-update-version-binding; branch:
build/update-version-binding; base: c7c0e373.

## Decision and contract

SourceTarget optionally identifies one acquired copy with both edition and
original_sha256. Edition is trimmed, nonblank and at most 160 characters; the
hash is exactly 64 lowercase hexadecimal characters. Partial or malformed
bindings fail validation before any review/status/outbox write. Both absent
remains the legacy publication target. Edition/hash alone does not identify a
publication or bypass registered source-family and original-article restrictions.

The outbox remains contract_version: 1. Its identity includes the optional
paired fields alongside the existing URL, pinned ID and DOI/PMID/PMCID. Both
fields enter the Updates status key. Same publication/edition with different
original hashes, and same publication/hash with different editions, remain
separate. Clearing one bound target does not clear another target's accumulated
facts; scope and identifier enrichment continue retaining independent facts.

Observed changed publication bytes remain an unbound invalidation of all copies
of that exact publication URL, including fragment locators. They only clear
latest_final_verified and content_reviewed, preserving publication dates,
corrections and other independently reviewed facts. An observed digest never
becomes an acquired file hash or an inferred new edition.

Parent prerequisites 18a3814a and 7edaffc3 were cherry-picked for integration proof
(local equivalents ac004f48 and 0002484b). Parent owns Knowledge's exact-file
promotion/clearing and publication-wide retraction, removal and access-loss
matching. The new Updates commit does not alter those files. No migration or
shared-root configuration is needed.

## Review flow

The existing publication metadata disclosure now looks up
GET /api/v1/library/source-versions for the entered registered source plus exact
publication URL/article identity. Requests settle after typing, are cancellable,
ignore stale responses and retry only on request. No document-list polling,
document bodies, external searches or case queries are involved. The parent
endpoint returns at most 100 active/latest acquired Library revisions, excluding
deleted and reserved documents; truncation remains visible.

The acquired-version selector starts unchosen. A deliberate selection preserves
the Library edition and original hash behind the form. Edition, title and a short
file fingerprint distinguish choices without requiring a doctor to type SHA256.
Changing publication identity or the acquired copy clears the former currency
confirmations. Reopening a saved review retains its exact binding. Optional
manual paired entry supports review before import. Missing versions and lookup
failures have visible recovery states; publication-wide restrictions remain
explained separately from exact-file verification/clearing.

The Updates columns now stack below 1000 CSS pixels, retaining the established
Flow layout and tokens while avoiding narrow-window review overflow.

## Verification

- Parent bootstrap Python environment, python -m pytest tests/updates -q:
  **51 passed**, including 17 new exact-version checks. The command used
  Renulus-wt-integration/.venv/Scripts/python.exe; plain system Python lacks
  the selected LanceDB package. One existing Starlette/httpx deprecation warning.
- node node_modules/vitest/vitest.mjs run src/modules/updates: **18 passed**.
- npm run build: typecheck, Vite renderer and Electron build all passed.
- git diff --check: passed.
- Real SQLite review, status-key, outbox and restart proof covers three copies
  (same edition/different hashes and same hash/different editions), a legacy
  target, independent clearing and an older review retry.
- Actual HTTP Library version lookup and Updates review submission prove the
  metadata-only choices round-trip into the version-1 outbox with the unchanged
  original hash. Invalid pairs produce HTTP 422 with no journal side effects.
- Actual Knowledge journal and LanceDB with controlled extraction/embeddings
  prove exact promotion, all-version publication restrictions despite topic
  scope, exact clearing, and current-only retrieval exclusion of unrelated copies.
- A controlled publisher byte sequence invalidates every bound and legacy copy
  at the publication URL, including a fragment locator; another publication's
  currency remains unchanged.
- Chrome on the real local renderer/runtime, in an isolated synthetic profile:
  choices initially unselected; choosing copy B populated the complete original
  hash without typing it. Default desktop and narrow-window layouts inspected.
  After the narrow-window fix the Updates grid measured 575.653 CSS pixels with
  scroll width 576, one column, and the selected hash retained. Temporary viewport
  sizing was reset and the preview tab closed.

## Evidence limits

All source bodies, identifiers, reviews and publisher sequences in these checks
are explicitly synthetic application-rule fixtures. SQLite, local HTTP routes,
the parent status journal and LanceDB are real. Extraction and embeddings are
controlled adapters, so this does not establish neural-model, live-publisher,
acquisition-rights, original-file provenance or educational-review accuracy.
No live publication/provider, paid/keyed tool, patient text or acquisition call
was made. The feature does not infer processing or review from register prose.
Importer guards remain Mendel's lane; Knowledge matching remains the parent's.

The original source/acquisition register, completed scheduling worktree,
assessment, Cases, shared storage, applied migrations and shared manifests were
preserved. Only the assigned Updates models/reviews, renderer, focused tests and
this new evidence document belong to the handoff commit.
