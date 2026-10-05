# Deliberate acquired article scans

October 5, 2026. Integration adds a Flow Library control for the bounded
`POST /api/v1/library/collection/import-next` producer. It appears in Collected
sources for L02 and uses the selected literal title filter. Its stated scope
includes eligible receipts and candidates needing inspection independently of
the receipt eligibility page filter. Temporary and unclassified scopes block
adoption. No scan begins automatically.

The control sends sequential pages of at most 100 selections, keeps the stable
returned cursor, reports observed checked/newly queued/rejected/remaining
counts, and exposes attention reasons. Pause, navigation and unmount abort the
request; already committed jobs remain durable. A late aborted response does
not become observed progress. Retry/resume reuses the last reported cursor;
the producer reuses exact existing jobs. Completion permits a fresh deliberate
scan for newly acquired material. Reported scan completion does not mean CPU
indexing has completed.

Native recovery renderer from 22134150 and this Library integration passed
95 mounted renderer checks across BulkImportControl, LibraryBrowser and
DataManagement. The focused acquired bulk/enqueue producer checks passed nine
checks in the integration worktree with a compact Windows test root. The lane
records its broader 129-check regression and final 33-check family separately
in acquired-literature.md. TypeScript, Vite production build and Electron
compilation passed. Fixtures are synthetic; these counts do not constitute
the actual large collection scan, which is recorded separately after running
the new control against the owned development profile.
