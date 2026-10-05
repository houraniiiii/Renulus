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

The integration owner subsequently ran the actual Library control against the
owned development backend and the registered L02 collection. The first dev
view inspected 700 receipts and bound 389 unique jobs before a development
reload closed the view. Its durable accepted work remained. A production Vite
preview then continued a fresh deliberate scan, excluding matching live jobs.
At 00:17:21 UTC on October 5, a read-only snapshot found 1,357 inspected
receipts since the first scan, 756 adopted receipts and 756 distinct bound jobs.
Their canonical topic tags span T01–T27. The Library had 945 documents: 156
ready, one processing and 788 queued.

In that production view the owner clicked Pause article checks after 600
reported receipts, 331 reported additions and 269 reported attention results.
The UI changed to the paused notice and Resume article checks. The canonical
snapshot includes committed work from the interrupted page; the UI correctly
does not manufacture an observed result for that page. Clicking Resume
continued from the last reported cursor. At the next observation it had
reported 1,200 receipts, 670 additions and 530 attention results with no visible
error. These are observed scan counters, distinct from persisted totals and
from CPU indexing. The full traversal is still running.
