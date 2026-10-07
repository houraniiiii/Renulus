# Library Office and original-viewing integration

Observed October 5, 2026 in the E integration checkout; issues #6, #15, #16
and #17. The installed product remains 3ff9b0d6 until the next exact freeze is
manufactured and accepted. These renderer checks do not establish native Office
download or acquired-file readiness.

The existing Flow interface is retained for nephrologists reading a source
between study sessions. Its source title remains the focal point. Original
location and attribution use the existing secondary text, Source Sans 3, calm
teal/neutral tokens, restrained depth and existing spacing. Button, Input and
Notice primitives retain their focus/error states; no new visual direction or
token family is introduced.

The document picker accepts case-insensitive PDF/image/text and DOCX/PPTX/XLSX
extensions, with format-specific capability gating. Office readiness does not
require PDF/OCR assets. Import still requires deliberate local-processing
permission and sends the original bytes with personal-library scope.
Office originals offer an explicit Save original link using the returned MIME
type. Blob URLs are released on reader disposal. Existing PDF page viewing,
image viewing and text originals retain their prior behavior.

The shared locator contract now carries actual slide/sheet/item/table references.
Office locations show their recorded slide or worksheet rather than a invented
physical page. Source attribution appears alongside terms. A ready image with
zero passages explains that it is viewable but has no searchable text. General
ready counts use Available; Discovery's Indexed marker still requires its
separate verified active revision and passages.

## Verification

The first focused fork-worker attempt timed out during startup and produced no
test results. It remains in the ignored ui-coverage-20261005T0538 directory. A
serial attempt ran 48 checks: 45 passed and the three new Office-picker checks
failed because their test setup had not opened the Add to library menu. That
setup was corrected; it did not require a product behavior change.

After the locator/attribution/no-text-image changes, the complete renderer suite
ran serially with maxWorkers=1 and no-file-parallelism: **417 passed in 34 files**,
147.64 seconds. The TypeScript, Vite production renderer and Electron build
also passed. Exact commands were npm test with those flags and npm run build
from apps/desktop. The three original Office save/blob-lifetime checks, three
raw-file/permission/scope checks and four Office-location/no-text-image reader
checks are part of that total, not additional independent totals.

The integration queue/worker selection independently passed **20 checks** in
63.36 seconds. The actual three-format Office recovery gate passed **one check**
with four other cases deselected, 90.34 seconds, after the parent added the
shared archive's exact Office extension/MIME allowlists. The original failed
recovery attempt remains recorded in office-supplements.md. These backend
checks use actual SQLite/LanceDB and real Office extraction where applicable,
with controlled vectors; they do not establish actual Office embeddings or
installed acceptance. No helper/package pin changed.
