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
