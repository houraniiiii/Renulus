# Library document paging

October 4, 2026 · integration branch.

The actual 156-document Library exposed an unbounded document list. The backend
now supports optional limit (1–100), offset, literal title/source search and
latest-import status filtering. It selects the bounded page before deserializing
revisions, avoiding full-library metadata expansion for each page. Stable
updated-time/ID ordering breaks equal-time ties. Existing callers without page
arguments retain their full documents list.

The response includes filtered total and global nondeleted counts by latest
revision status. A failed or queued replacement therefore contributes its latest
state even when a previous revision remains available for citation. Global counts
let the renderer track the import worker while browsing a filtered page. Deleted
records remain excluded. Title search escapes percent, underscore and backslash;
it uses bound parameters.

Three checks passed: stable disjoint pages deserialize only selected records;
replacement/deletion and literal search maintain counts; the registered HTTP
route enforces bounds and filter values. These checks use synthetic canonical
records and do not claim actual extraction or medical source review. The renderer
lane owns the corresponding pagination and filtering interface.

The Flow renderer now requests 25-document pages, validates the total/counts
envelope, and presents title/source and latest-import filters. A selected source
is loaded deliberately even when it lies on a different page. Collection filters
are applied in SQL before paging, including inspection-required JATS candidates.
Candidates remain distinct from inspected eligible material and indexed passages.

The integrated Library and Discovery renderer pair passed all 60 checks. Mounted
discovery guards continue proving that case/question details do not leave their
context. Their fixture was updated to the actual paginated response; product
guards were not relaxed. The desktop production build passed.

The actual long Library view also exposed a navigation problem: the rail grew
with the page, leaving its routes above the viewport and runtime status far
below. It now stays at the viewport edge and scrolls its own contents on a short
window. The existing Flow teal palette, Source Sans typography, spacing, controls
and source-inspection hierarchy are retained; narrow-window navigation retains
its existing expanding layout. At document scrollY 766 on the collaborative
desktop preview, the rail stayed at approximately y=0 with all eight route links
visible between y=99 and y=493. This is actual scrolling evidence, independent
of native Windows sizing and source extraction checks.
