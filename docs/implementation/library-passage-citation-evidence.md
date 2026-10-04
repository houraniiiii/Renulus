# Library exact passage citations

Checked October 4, 2026 UTC (October 5 in Warsaw). Worktree
`Renulus-wt-passage-citations`, branch `build/passage-citations`, base
`8005bd992a4d357ad6b6d26ce2a29879f5ac7e54`. This follows the pinned
revision/page inspector recovery integrated in `8005bd99`.

## Demonstrated gap and additive seam

Learn already supplied a passage identifier in its volatile source handoff,
but Library discarded it and the citation route collected every locator on
the requested page or revision. The initial SQLite/API regression reproduced
two passages on physical page 2: asking for the first passage still returned
the other passage's locator. The renderer regression also showed that both
the page request and missing-page retry omitted the passage binding.

`GET /api/v1/library/revisions/{revision_id}/citation` now accepts optional
`passage_id`. The route and repository validate the canonical identifier
`passage_` followed by 32 lowercase hexadecimal characters. A supplied
identifier must belong to the exact requested ready, nondeleted revision.
The response echoes `passage_id`, restricts locators to that passage (and
the requested page when supplied), and preserves the original URL on the
same revision. Its metadata viewer URL also carries the passage identifier.

Bound citations check personal-library scope, reserved status, display and
retrieval permissions, the existing non-current retrieval eligibility rules,
repository removal, and excluded pages across the entire passage before
filtering by page. Missing, wrong-revision or ineligible passages return
404 `passage_missing`; unavailable revisions retain 404 `citation_missing`.
Malformed identifiers return 422. Only an otherwise eligible bound passage
without the requested page returns 404 `page_missing`. This ordering prevents
page recovery from broadening a blocked citation.

An inactive historical revision remains inspectable when it is ready and
eligible; it is never replaced with the active revision. Ordinary personal
notes need not be promoted to verified current guidance to inspect their
citations. Calls omitting `passage_id` retain the legacy revision/page lookup
and response shape. No migration is needed.

## Connected Library and Learn behavior

Library now retains the existing Learn handoff's passage ID and each retrieved
passage's canonical ID. Changing passages on the same revision/page remounts
the inspector so a previous result cannot stand in for the next passage.
The renderer verifies the echoed passage ID alongside document, revision,
page and the exact local original endpoint. An absent or different passage
identity cannot open an original. Invalid non-string handoff identifiers
cannot silently become unbound revision lookups.

Only a confirmed 404 `page_missing` permits a retry without the page filter;
the retry retains both revision and passage. It offers the existing deliberate
`Open whole original` action with no page jump. Missing/blocked passages,
permission errors, other failures and even a different HTTP status with a
`page_missing` label do not trigger that recovery. Unknown physical pages
remain unknown. The source-location count identifies the cited passage while
explicitly stating that exact passage highlighting is unavailable.

The existing Learn producer already forwarded `passage_id` or the canonical
retrieval `id`; its behavior is exercised through the real Learn component,
SSE decoder, navigation and Library inspector. Shared navigation already
allows the volatile handoff fields, so no shared type prerequisite was needed.

## Checks

- `pytest tests/knowledge/test_passage_citation.py -q`: **26 passed**.
  Real SQLite, public import/retrieve/citation/original routes, the actual
  source-status journal and LanceDB use controlled extraction/embedding
  adapters. Checks cover exact same-page locators, legacy behavior, historical
  pinning, wrong revisions/documents, removal, malformed IDs, permission and
  reserved exclusions, reviewed source-status restrictions, and page recovery.
- The backend format journeys upload valid synthetic text/PDF/PNG bytes,
  persist and retrieve their passages, request exact citations, then verify
  original-byte and media-type round trips. Extraction locators are controlled
  fixtures; these checks do not establish Docling/OCR accuracy.
- `pytest tests/knowledge/test_repository.py
  tests/knowledge/test_api_collection.py -q`: **21 passed**, including the
  existing historical citation and original-delivery/import behavior. Backend
  runs emitted only the existing Starlette TestClient deprecation warning.
- `node node_modules/vitest/vitest.mjs run src/modules/library
  src/modules/learn`: **105 passed** across five files. The inspector suite
  contains **16 journeys**, including discussion handoffs across text/PDF/image,
  exact search selections on the same page, identity validation, blocked
  recovery, legacy browsing, unknown pages and delayed original cancellation.
- `npm run build`: TypeScript, Vite renderer and Electron build passed.
- `git diff --check`: passed.

Python and desktop dependencies reuse the parent's prepared bootstrap. Only
an ignored desktop `node_modules` junction was created; no state, secrets,
credentials, dependency manifests or corpus were copied.

## Scope and limits

Production backend changes are confined to the citation route in `api.py`
and `KnowledgeRepository.citation()`. Renderer changes are confined to Library
types, selection and inspector wiring. Collection, acquired import, backup,
shared storage/configuration, native/Electron seams and source bodies remain
outside this change. All source text, original bytes, identifiers and discussion
answers used for the checks are synthetic; no acquired body is published.

No provider, keyed/paid tool, live acquisition or patient text is used. These
checks establish application/transport rules and local original delivery,
not scientific review, actual extraction accuracy, live generation or native
PDF page rendering. Wegener/parent retain the previously identified native
PDF/CSP gate and native diagnostics. This lane adds no location overlay and
does not claim that a PDF page or bounding-box highlight rendered natively.

GitHub #6 receives the handoff commit, decisions, checks and these limits.
