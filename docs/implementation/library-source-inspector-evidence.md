# Library source inspector: pinned citation recovery

Verified 2026-10-04 UTC. Worktree `Renulus-wt-source-inspector`, branch
`build/source-inspector-locators`, base `2bdcc89e`. This sidecar owns only
the Library source inspector/viewer, their wiring in the existing Library
page, focused renderer tests and this evidence.

## Demonstrated issue and change

Existing source viewing lived inline in `modules/library/index.tsx`; there
were no separate SourceInspector/OriginalViewer files. The initial regression
test reproduced a discussion citation for an older revision whose physical
page was unavailable. The UI silently discarded the API `page_missing` error,
offered no original-opening action and displayed the newer active edition
instead of the cited edition.

The inspector now retains the requested revision independently of citation
lookup success. It displays loading and failure/retry states. Only an actual
404 `page_missing` permits a second citation lookup for the same revision
without a page filter, followed by an explicitly labelled `Open whole original`
action. Unavailable revisions and other errors never substitute the active
replacement. Unknown physical pages open without an invented page jump.

Citation responses must match the document, revision, requested physical page
and that revision's local original endpoint before opening. Physical pages are
positive safe integers counted from the start of the file. The UI explains
that distinction from printed page labels. Original loading remains a
deliberate action through the existing local transport, with visible failures,
cancellation on source changes/unmount and blob-URL cleanup. A late file body
cannot appear under a newer source citation. Text stays in the text viewer,
images in the image viewer and PDFs retain the physical `#page=N` handoff.

## Checks

The existing Library browser/discovery and Learn memory-disclosure checks passed
before edits: **74 tests**. The first new regression failed with the missing
recovery action and newer edition visible, then passed after the patch.

- `node node_modules/vitest/vitest.mjs run src/modules/library
  src/modules/learn/memory-disclosure.test.tsx`: **82 passed** across four files.
- Eight focused citation-journey checks use the real NavigationProvider, Learn,
  Library, HTTP transport and SSE decoder with controlled synthetic responses.
  They cover generated discussion citations across text/PDF/image, pinned
  editions, physical PDF page URLs, missing-page whole-original recovery,
  unknown-page PDFs, a mismatching page response, unavailable revisions and
  a delayed original after switching citations.
- `npm run build`: typecheck, Vite renderer and Electron build passed.
- `git diff --check`: passed. Dependencies reuse an ignored junction to the
  parent's desktop bootstrap; no state, credentials or corpus files were copied.

The real renderer was also exercised in Chrome through a temporary loopback
synthetic HTTP/SSE server, with three declared source DTOs and a valid two-page
PDF fixture. A generated discussion citation retained the older edition and
requested the exact original blob with `#page=2`. Text content rendered, the
synthetic PNG decoded, and the missing-page notice/whole-original action stayed
on the cited edition. The owned preview tab and services were closed.

## Shared/native gate and proposed seams

The actual Chrome PDF iframe reported `This content is blocked`, so this check
does **not** establish that physical page two rendered. The committed shared
renderer CSP has no explicit frame rule for blob URLs and retains
`object-src 'none'`. Parent/Wegener own the renderer CSP, native PDF support,
original-response policy and native diagnostics; none are edited here. A narrow
candidate is permitting frames for app-generated authenticated original blobs
while retaining the other policies, then confirming actual page-two rendering
in their native test. No CSP fix or native rendering proof is inferred here.
The existing native journey fixture also matches the unpaginated documents
route; it needs the current paginated route/DTO in Wegener's lane.

The existing citation API resolves revision/page locations, not a passage ID.
The inspector labels the returned locations as page/revision locations and
states that exact passage highlighting is unavailable. Proposed parent-owned
extension: optional validated `passage_id` on
`GET /library/revisions/{revision_id}/citation`, requiring that the passage
belongs to the pinned available revision, returning only its locators and
rejecting a requested page absent from those locators. Keep the original URL
bound to the same revision. No broad search or current-revision fallback
should resolve an old cited passage.

## Evidence boundaries

All bodies, identifiers, source metadata and discussion answers in these checks
are synthetic. The tests prove renderer/application handoff rules, not actual
Docling extraction, original-file provenance, corpus processing, scientific
review, live generation or native PDF rendering. No acquired body is read or
published; no provider, paid/keyed tool, patient text or acquisition call is
used. Corpus/storage/runtime/native/shared configuration and other modules
remain outside this commit. Existing Flow components, styles and APIs are reused.
