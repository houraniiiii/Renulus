# Durable Office supplements — issue #15

October 5, 2026. Worker branch `build/supplement-inputs`, base `84e82e05`,
worktree `E:/Renulus-native-delivery/desktop-20261005/supplement-inputs`.
This slice admits deliberately selected PPTX, DOCX and XLSX files into the
durable personal Library. Selected acquired adoption, source permissions, UI,
shared recovery formats and installed-app delivery remain separate parent work.
No acquired originals, credentials or private/native state were accessed.

## Implementation and reuse

`runtime/renulus/knowledge/office.py` supplies container admission, a lazy Office
converter and passage locator mapping. It reuses the pinned Docling 2.133.0
`SimplePipeline` and `PowerpointFormatOption`, `WordFormatOption` and
`ExcelFormatOption` with their maintained OOXML backends. Conversion disables
remote/local resource fetching, external plugins, picture classification,
picture description, chart enrichment and chart-image rendering. The pinned
pipeline creates disabled enrichment wrappers; the tests check their disabled
state rather than assuming an empty wrapper list. No layout, OCR, transformer
weights, embedding model or memory engine is initialized by the Office proof.
Narrow subclasses of the maintained backends also disable external converter
discovery for legacy pictures/shapes: Word keeps its converter initialized to
`None`, and PowerPoint/Excel return no LibreOffice converter. This blocks the
otherwise independent malformed-picture fallback, without replacing text/table
parsers. A synthetic malformed Word picture proves readable text survives with
no renderer discovery or subprocess launch.

`engines.py` adds a separate cached Office converter behind the existing
conversion lock. Only durable `extract_file` selects it. Office conversion
requests no Docling/PDF/OCR helper assets. The existing HybridChunker path still
uses the exact local BGE tokenizer and 480-token budget, including the existing
table split/heading reservation and 12,000-passage ceiling. Runtime durable
indexing still uses the selected embedder through the existing repository.
`repository.py` extends `MEDIA` and validates the container before any Library
record or retained original is written. Direct extraction validates again before
Docling. Permission, scope, version, cancellation and source-status rules are
unchanged. At the parent's request, additive `capabilities.office_import` is
true when `text_import` is ready, Docling/core match the verified pins and
Docling/python-pptx/python-docx/openpyxl packages are present. It does not require
PDF/OCR model assets or startup warmup. No dependency/lockfile, shared model, API, schema, acquisition, native
or UI file is modified by the worker.

`_chunk(document, text_offsets=None, *, office_format=None)` is the narrow shared
method seam: when supplied, item provenance uses the Office locator helper;
otherwise the existing PDF/image/text mapping runs. The existing title-only
fallback carries this optional argument through its chunking copy. Empty Office
documents still fail. The parent's later image-only-original handling is outside
this slice; PDF/image conversion and the no-save byte allowlist are unchanged.

## Container boundary

- Existing 64 MiB compressed input maximum; at most 300 PPTX slides or XLSX
  sheets. DOCX has no reliable physical pagination, so no pages are invented.
- At most 4,096 ZIP entries, 32 MiB expanded per entry, 128 MiB expanded total
  and 200:1 expansion per entry. Central-directory structure/count is scanned
  before `ZipFile` allocates metadata, including forged small EOCD counts.
- Members are read in 64 KiB blocks with size and CRC checks; nothing is
  extracted to a filesystem path. Duplicate names, traversal, absolute/Windows
  paths, symlinks, truncated/overlapping ZIP members and unsupported compression
  are refused. Multipart and ZIP64 containers are outside this initial scope.
- Encrypted ZIP entries and encrypted/legacy compound Office containers have
  explicit `office_encrypted` refusals. XML must parse without DTD/entity
  declarations. Required OOXML parts, root relationship and format-specific
  main content type must match the selected extension.
- VBA/macro-enabled content, active objects, embedded packages, linked external
  resources and EMF/WMF rendering are refused. External hyperlinks can contribute
  inert label text; they are never followed. XLSX formulas are not evaluated by
  the backend; only available cached values can contribute their results.
- Sparse worksheet coordinates, dimensions and merged ranges are limited to a
  1,000,000-cell bounding area per sheet to prevent a tiny file requesting a huge
  dense conversion or openpyxl materializing millions of merged cells at load.

The structured errors are `malformed_office` (422), `office_encrypted` (422),
`unsafe_office` (422), `office_container_limit` (413), and the existing
`document_limit`, `empty_extraction`, `extraction_failed` and helper errors.
Parser exception contents and source paths are not exposed in API messages.

## Locator contract for the parent

Every Office passage locator has an actual Docling `item_ref`, `format` and
`page: null`. A table additionally has its actual `table_ref`.

| Format | Additional locator evidence | Meaning |
| --- | --- | --- |
| PPTX | `slide`, `bbox`, `slide_size`, `char_span` when Docling supplies provenance | One-based slide ordinal and unchanged Docling geometry/spans |
| XLSX | `sheet`, `sheet_name`, `cell_bbox`, `char_span` when supplied | One-based sheet ordinal/name; raw Docling cell-grid geometry, not PDF/pixel geometry |
| DOCX | Item/table reference; no fabricated bbox, physical page or character offset | Structured Docling item identity |

Chunked tables retain the original table identity/geometry, not invented row
coordinates for individual chunks. The canonical Docling export retains its
original structure and provenance. Its Office `pages` are Docling slide/sheet
containers, not physical PDF pages. Existing source-level eligibility checks
still apply; `excluded_pages` remains the existing page contract, not a new
slide/sheet masking contract.

Existing citation APIs return these JSON locators without a schema change.
Passage-bound lookup works without a page query; a physical `page=1` lookup
correctly refuses Office passages. Parent UI needs Office MIME accepts and
slide/sheet/item labels instead of PDF page requests. The additive `office_import`
capability reflects Office's independence from PDF/OCR assets and its need for
the shared tokenizer/embedding/index stack. Capability checks use package
metadata/presence and do not initialize an Office converter or model.

## Verification

The existing interpreter is
`C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe`.
Installed versions verified in it: Docling 2.133.0, Docling-core 2.99.0,
python-pptx 1.0.2, python-docx 1.2.0, openpyxl 3.1.5 and tokenizers 0.23.2.
Fixtures are generated from these existing dependencies in isolated E scratch.
No install, launch, repackaging, paid provider, source-original scan or download.

The proof selects only the existing public BGE `tokenizer.json`, verifies its
SHA-256 against `packaging/runtime/helper-assets.json`, and loads no embedding
weights. The portable fixture uses a small synthetic tokenizer when the explicit
environment variable is absent; that mode is not the pinned-tokenizer proof.
Socket/DNS guards reject external access and subprocess guards reject launches.
Only loopback OS sockets required by the embedded test runtime are allowed.

```powershell
$env:PYTHONPATH = 'E:/Renulus-native-delivery/desktop-20261005/supplement-inputs/runtime'
$env:RENULUS_OFFICE_TOKENIZER = 'C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.local/runtime/integration/helpers/fastembed/bge-small-en-v1.5/tokenizer.json'
$officePython = 'C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe'
& $officePython -m pytest tests/knowledge/test_office_validation.py tests/knowledge/test_office_conversion.py tests/knowledge/test_office_api.py -q --tb=short --basetemp=E:/Renulus-office-proof-20261005/office-tests
```

`test_office_conversion.py` proves actual text/table conversion, title-only
fallback, item/slide/sheet references, long-table retention and shared chunk
budget, empty Office refusal, inert hyperlink/formula handling and refusal of
temporary Office bytes. `test_office_validation.py` proves malformed/encrypted
and expansion/container refusals before storage, including unchanged source
permission requirements.

`test_office_api.py` uses actual Docling/HybridChunker, SQLite and LanceDB with
the existing `SyntheticEmbedder` vector seam. It proves durable raw-file import,
ready jobs, retrieval, exact passage citation, original MIME/byte identity,
idempotency, deletion and scope/expansion refusal. These API checks are not
evidence of real embeddings. Its combined backup/restore test is the concrete
shared recovery acceptance gate.
`test_office_capabilities.py` separately checks readiness with controlled package
and asset seams: missing parser/pinned distribution/tokenizer readiness disables
Office, while absent PDF/OCR assets and startup do not.

The combined acceptance run exposed one shared recovery failure: backup refused
Office originals with `backup_path` before restore (39 passed, one failed;
101.17 seconds). A later Office run covering the added empty/link/formula proofs
passed 44 checks with that known shared gate deselected (95.79 seconds).
After adding capability and further container checks, 41 validation/capability
checks passed (3.60 seconds). The renderer-boundary conversion run passed all
15 real conversion checks (50.78 seconds), including the malformed picture.

Existing regression command and result:

```powershell
& $officePython -m pytest tests/knowledge/test_repository.py tests/knowledge/test_worker.py tests/knowledge/test_document_pages.py tests/knowledge/test_passage_citation.py tests/integration/test_backup.py -q --tb=short --basetemp=E:/Renulus-office-proof-20261005/regression-tests
```

**49 passed**, 580.94 seconds. These use the existing controlled extraction/vector
seams and real SQLite/LanceDB, not PDF/OCR/model inference. The supplied native
PDF/OCR/embedding slot was not used. `git diff --check` passed. The pinned
FastAPI/Starlette test-client deprecation warning was observed; no package was
changed to address it.

Final combined worker-suite command:

```powershell
& $officePython -m pytest tests/knowledge/test_office_validation.py tests/knowledge/test_office_capabilities.py tests/knowledge/test_office_conversion.py tests/knowledge/test_office_api.py -k 'not three_real_office_formats_restore' -q --tb=short --basetemp=E:/Renulus-office-proof-20261005/final-office-suite
```

**60 passed, one deselected**, 123.71 seconds. The deselected gate is exactly
the already observed shared recovery failure, not an untested conversion or
simulated restore pass. Issue #15 remains open for the parent's recovery/UI/
selected-acquired integration and real full Office restore gate.

## Parent integration and recovery proof

The parent integrated this slice at `909d2968` and extended the shared archive's
exact extension/MIME allowlists to PPTX, DOCX and XLSX. The existing security,
hash and ownership checks remain active. The previously failed real gate was
rerun in the combined integration checkout with the same approved tokenizer:
`test_three_real_office_formats_restore_originals_and_canonical_locators_via_api`
passed (**one passed, four deselected; 90.34 seconds**). All three Office
original byte identities and canonical source locators survived full backup
and restore. The original failed attempt remains retained. This establishes
application recovery with actual extraction and controlled embedding vectors;
it is not native installation or acquired supplement adoption evidence.

## Original shared prerequisite and remaining limits

At worker handoff, `runtime/renulus/storage/recovery_archive.py:25` had an independent `ORIGINAL`
regex excluding PPTX/DOCX/XLSX, and its adjacent `MEDIA` map also lacks their
standard MIME values. `descriptor_for()` checks both. `recovery_zip.py` and
`recovery_files.py` import that same regex. Parent must extend those allowlists
and run `test_three_real_office_formats_restore_originals_and_canonical_locators_via_api`
before claiming full recovery support. The worker did not alter or simulate
this shared boundary. The failure and exact prerequisite were posted on #15.

Actual selected acquired supplements are not opened or adopted in this proof.
Some real Office files may be refused by the deliberate initial boundary
(embedded objects/chart workbooks, linked resources, vector pictures, ZIP64,
large/sparse worksheets). Image-only or scanned Office content has no OCR in
this path and may have no readable text; empty extraction remains a failure.
UI/native delivery and the parent's image-only Library change require their
own evidence. Source rights, currency and clinical content review are unchanged.
