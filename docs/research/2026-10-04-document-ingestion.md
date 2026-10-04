# Document ingestion and PDF extraction candidates

2026-10-04 · Research only · Owner: document-ingestion investigation.

**Decision follow-up (2026-10-04):** the user selected Docling's CPU structured
pipeline + Docling-core HybridChunker as part of the approved starting stack.
LiteParse remains a lighter alternative for a demonstrated gap. Original
source/artifact findings below are preserved; selection is not a runtime result.
See the [stack evidence](2026-10-04-starting-stack-evidence.md) and
[implementation plan](../planning/IMPLEMENTATION_PLAN.md).

## Recommendation

**Prefer Docling's standard CPU conversion pipeline + HybridChunker for the
least total integration work; retain LiteParse as the lightweight challenger.**
Docling connects layout/table extraction, document structure, token-aware
chunking and citation provenance in an existing path. LiteParse has a
substantially smaller binary package, but adding prose/table chunkers still
leaves routing, context and provenance mapping to integrate. Both expose their
actual parsing engines and require no owner-operated service. This preference
was an engineering judgment from source review, subsequently accepted by the
user. It does not establish measured superiority on nephrology material.

For the next implementation decision, evaluate **Docling + HybridChunker as the
preferred complete path**, with LiteParse + Chonkie as the packaging/resource
comparison on the same representative documents. Assess extraction, table
chunking and citation fidelity together with CPU footprint. Here the full
Docling path means standard structured conversion and chunking, with pinned
OCR assets and tokenizer; it does not mean enabling generative enrichments or
every optional dependency. Keep one primary extractor initially; a second
engine should address a demonstrated failure rather than become a compulsory
parallel pipeline. The capability evidence is in the
[Docling pipelines](https://github.com/docling-project/docling/tree/v2.133.0/docling/pipeline),
[HybridChunker](https://github.com/docling-project/docling-core/blob/v2.99.0/docling_core/transforms/chunker/hybrid_chunker.py)
and [LiteParse engine](https://github.com/run-llama/liteparse/tree/python-v2.15.1/crates/liteparse).

**Xberg merits a third place on the shortlist** if one library for extraction,
chunking and optional local embeddings substantially reduces integration work.
It is the active successor to Kreuzberg, with a complete open Rust engine and
Python bindings. Do not begin a new long-lived product on the Kreuzberg v4 LTS
line merely because old comparisons call it the current release. Its stated
support ends in December 2026, on a best-effort basis.
[LTS policy](https://docs.kreuzberg.dev/lts/),
[Xberg engine](https://github.com/xberg-io/xberg/tree/v1.3.3/crates/xberg).

Do not select hosted LlamaParse, Marker, MinerU, or PyMuPDF as the default route
for this request. Reasons differ: hosted processing, generative-model/runtime
requirements, non-permissive weight or distribution terms, or stronger copyleft
obligations. Their individual findings below avoid treating all four as the
same licensing problem.

## Scope and evidence limits

Read the workspace README, project brief, workspace rules, decisions,
implementation architecture, parallel-work constraints and source boundaries.
Hermes Python with an Electron/React desktop remains the foundation. This note
does not replace the plans or select a memory/vector-store framework.

The user clarified during this research that **small CPU helper models bundled
and entirely managed by Renulus for OCR and embeddings are acceptable**. No
GPU, Docker, model server, paid API fallback or user-managed inference setup is
acceptable. Conversation and generative work stay on the chosen subscriptions.
Accordingly, local OCR is eligible; a local generative VLM is not implicitly
authorized by that clarification. The size and latency of layout/table models
still need assessment rather than assuming every CPU-capable model is small.

Inspected first-party documentation, tagged source, release pages, model cards,
registry metadata, two Windows wheel archives and the published Chonkie and
semchunk source archives. Archive inspection occurred in memory; no package was
installed, imported or executed. No model weights were
downloaded, no provider was called, and no private documents were used. This is
source and packaging evidence, not an end-to-end Windows installation test,
benchmark, dependency audit or clinical extraction validation.

Some unauthenticated GitHub API requests returned HTTP 403 rate limits. Public
raw files, repository pages, tagged archives and PyPI metadata remained usable.
Rate limits are not evidence of inactivity. All recorded release/model dates are
on or before 2026-10-04. Relative search-engine crawl dates were not used as
release dates. Notable inconsistent/stale documentation is called out below.

## Comparison for Renulus

| Candidate | Reusable capability | Additional inference | Windows delivery and fit | Recommendation |
| --- | --- | --- | --- | --- |
| **Docling 2.133.0 + HybridChunker** | Multi-format conversion, structured document, PDF layout/tables/OCR, hierarchical/token-aware chunking | Standard PDF pipeline uses layout/table/OCR models; a separate native PDF pipeline uses none | Python library; native parser Windows wheels exist; complete standard environment is larger | Preferred complete integration path; verify CPU footprint and extraction quality |
| **LiteParse 2.15.1** | PDF text, geometric layout, local OCR, Markdown/JSON, page/box locators, screenshots, complexity signals | Tesseract OCR; explicitly disable for native-text-only parsing | Python x64 and ARM64 wheels; PDFium bundled; language data needs an app-owned bundle | Lightweight challenger with Chonkie; provenance/routing integration remains |
| **Xberg 1.3.3** | Multi-format extraction, structured output, chunking, optional embeddings and reranking | Optional OCR/layout/embedding helpers; separate LLM features must stay off | Windows x64 wheel contains native extension and ONNX Runtime DLLs | Broad integrated contender; pin and inspect platform-specific bundle |
| **Kreuzberg 4.10.4 LTS** | Similar ingestion/chunking foundation in the previous line | Optional helpers | Windows x64 wheel; short remaining LTS horizon | Reference/migration evidence, not preferred new foundation |
| **Unstructured 0.27.10** | Typed elements, metadata and useful chunking | Fast path is text-based; high-resolution/OCR paths add models and native tools | Broad optional dependencies and external executables to package | Capable, but less attractive for minimal Windows delivery |
| **MarkItDown 0.1.8** | Convenient multi-format-to-Markdown conversion | PDF conversion uses heuristics; base package also invokes Magika's small classifier; remote capabilities are optional | Python, per-format extras; easy supplementary converter | Useful for Office/HTML; insufficient default PDF provenance contract |
| **pdfplumber / pypdf / PDF.js** | Detailed PDF geometry/tables; simple PDF text/manipulation; desktop viewing/rendering respectively | None for those core functions | Straightforward components with permissive top-level licences | Keep as targeted components; they do not collectively supply automatic OCR and RAG |

Sources for version/platform observations: the release and artifact inventory
at the end; capability and limitation sources are attached to each investigation
below. Integration rankings are this investigation's engineering judgments.

## LiteParse: genuine local engine, distinct from LlamaParse

**What is actually open.** LiteParse's Apache-2.0 repository contains the Rust
parser, geometric layout/table logic, OCR integration and bindings. It is not
just a client for LlamaParse. Hosted LlamaParse is promoted as a separate upgrade
for complex documents; do not follow that promotional fallback automatically.
The current repository has moved beyond the earlier TypeScript implementation
to a Rust/PDFium engine with Python, Node and WASM bindings.
[Repository and product distinction](https://github.com/run-llama/liteparse),
[licence](https://github.com/run-llama/liteparse/blob/python-v2.15.1/LICENSE),
[engine manifest](https://github.com/run-llama/liteparse/blob/python-v2.15.1/crates/liteparse/Cargo.toml).

**Native-text path.** Set `ocr_enabled=False` explicitly. This extracts existing
PDF text and reconstructs layout without an LLM or learned layout model. The
optional block output includes headings, paragraphs, lists, tables and
per-cell boxes. Thus this path is more useful for structured text than simply
concatenating pages, while remaining heuristic. Default output is JSON;
`extract_blocks` and `include_complexity` are off unless requested. Complexity
signals include text coverage, images, garbled text and whether OCR is indicated.
These are routing aids, not correctness scores.
[Configuration](https://github.com/run-llama/liteparse/blob/python-v2.15.1/crates/liteparse/src/config.rs),
[layout implementation](https://github.com/run-llama/liteparse/tree/python-v2.15.1/crates/liteparse/src/markdown_layout),
[Python result conversion](https://github.com/run-llama/liteparse/blob/python-v2.15.1/packages/python/liteparse/parser.py).

**OCR and downloads.** Native builds enable the Tesseract feature by default.
OCR defaults on when that feature is compiled in; it can operate without a
server. However, the engine checks for each requested `.traineddata` file and,
if missing, downloads it from `tesseract-ocr/tessdata_best`. Windows' default
destination is an AppData `tesseract-rs/tessdata` directory. Explicit
`tessdata_path` overrides it. Therefore “bundled Tesseract” does not establish
that the language weights are bundled or that first use is offline. Prepackage
the chosen English data, record its revision/hash and set the path in Renulus.
This is an implementation recommendation, not work performed here.
[OCR engine and downloader](https://github.com/run-llama/liteparse/blob/python-v2.15.1/crates/liteparse/src/ocr/tesseract.rs),
[language-data licence](https://github.com/tesseract-ocr/tessdata_best/blob/main/LICENSE).

**Windows evidence.** PyPI published `liteparse-2.15.1-cp310-abi3-win_amd64.whl`
on 2026-10-01, about 12.12 MB compressed, and also an ARM64 wheel. Python 3.10+
is required. Static inspection of the x64 wheel found `_liteparse.pyd`
(20,142,592 bytes) and `pdfium.dll` (7,107,072 bytes), with no `.traineddata`
entry. The release workflow stages PDFium into the wheel and runs Windows
native-text, bytes-input and screenshot smoke tests. Those observed tests use
OCR disabled; they do not demonstrate offline OCR from the distributed wheel.
[PyPI files](https://pypi.org/project/liteparse/2.15.1/#files),
[wheel metadata](https://github.com/run-llama/liteparse/blob/python-v2.15.1/packages/python/pyproject.toml),
[release workflow](https://github.com/run-llama/liteparse/blob/python-v2.15.1/.github/workflows/release-python.yml).

**Citation and chunking fit.** Results expose physical page number, page label,
page dimensions, text items and optional layout blocks. Preserve JSON and its
coordinates alongside any rendered Markdown. These are useful inputs to the
Renulus passage contract and PDF.js highlights. LiteParse does not by itself
provide an authoritative personal library, revision/delete handling, vector
database or personalized memory. The reusable downstream choices below avoid
inventing a chunking algorithm, but do not eliminate integration work.
[Result types](https://github.com/run-llama/liteparse/blob/python-v2.15.1/packages/python/liteparse/types.py).

**Reusable chunkers behind LiteParse.** Source review included the published
Chonkie 1.7.0 (2026-07-07) and semchunk 4.1.1 (2026-06-13) archives, without
installation or execution. Both are MIT-licensed; neither option requires
reconstructing a `DoclingDocument`.
[Chonkie release](https://pypi.org/project/chonkie/1.7.0/),
[semchunk release](https://pypi.org/project/semchunk/4.1.1/).

| Companion | Reuse | Remaining gap |
| --- | --- | --- |
| **Chonkie `RecursiveChunker` + `TableChunker`** | Token-aware prose splitting and Markdown/HTML table splitting with repeated headers; supply the bundled embedding tokenizer explicitly | Route prose/tables, retain headings/captions/footnotes and map chunk evidence to LiteParse pages/boxes |
| **semchunk** | Minimal text-only splitter with a local tokenizer/token counter, overlap and character offsets | No table-header or document-provenance pipeline; suitable for simple text, not a complete substitute for HybridChunker |

Chonkie's defaults count characters for recursive splitting and rows for tables;
token-aware behavior requires explicit tokenizer configuration. Its table code
keeps rows together but can emit an oversized header-plus-row, so it is not a
strict token ceiling for every table. These are source observations, not tested
failure rates. The existing LiteParse chef copies `result.text` and the filename
into a Chonkie document, discarding page/box/block metadata. Renulus would need
to use LiteParse's structured results directly and preserve their evidence
mapping through the chunkers.
[Recursive implementation](https://github.com/feyninc/chonkie/blob/main/src/chonkie/chunker/recursive.py),
[table implementation](https://github.com/feyninc/chonkie/blob/main/src/chonkie/chunker/table.py),
[LiteParse adapter](https://github.com/feyninc/chonkie/blob/main/src/chonkie/chef/liteparse.py).

For semchunk, use plain-text input, a bundled tokenizer and leave optional
AI/provider chunking disabled. Its offsets locate substrings, not PDF geometry.
Docling already uses semchunk for ordinary text and adds table-specific
splitting, contextual token budgeting and document-item provenance around it.
That existing connection is why total integration effort favors Docling +
HybridChunker despite LiteParse's smaller parser footprint.
[semchunk API](https://github.com/isaacus-dev/semchunk#usage-),
[pinned HybridChunker](https://github.com/docling-project/docling-core/blob/v2.99.0/docling_core/transforms/chunker/hybrid_chunker.py).

**Limits relevant to clinicians.** The maintainer's September 2026 benchmark
reports near-zero chart-data reconstruction for all tested model-free engines;
it explicitly notes weak handwritten scans and absent mathematical LaTeX
reconstruction. Treat those as first-party benchmark claims, not a Renulus
evaluation or proof of clinical superiority. Local OCR can recover labels in a
figure without understanding the figure's meaning. The documented PaddleOCR
benchmark setup uses an HTTP OCR server; that particular setup does not satisfy
Renulus's no-model-server constraint.
[Benchmark methodology and results](https://github.com/run-llama/liteparse#benchmarks).

**Office and temporary-file gap.** Office conversion uses LibreOffice and creates
temporary converted PDFs plus a separate temporary LibreOffice profile. Common
image conversion has native Rust paths; do not infer that every supported input
is dependency-free from the PDF example. Direct PDF bytes input exists, whereas
conversion of non-PDF bytes can materialize files. Automatic cleanup on guard
drop is not the same as never persisting a temporary case, especially across
crashes. Restrict no-save input paths until their actual writes are verified.
[Conversion source](https://github.com/run-llama/liteparse/blob/python-v2.15.1/crates/liteparse/src/conversion.rs).

**Operational and licensing work.** The Python worker-pool implementation offers
hard timeouts and worker replacement. Limit concurrency for a responsive
desktop: the core OCR default is approximately CPU-count minus one. Renulus
still owns progress, cancellation, resume and publication of completed passages.
Carry Apache notices and the licences for PDFium, Tesseract, Leptonica and chosen
language data. The inspected x64 wheel did not contain files named LICENSE,
NOTICE or COPYING; do not assume a wheel alone supplies the redistribution
notice bundle.
[Worker pool](https://github.com/run-llama/liteparse/blob/python-v2.15.1/packages/python/liteparse/_pool.py),
[upstream PDFium licence](https://pdfium.googlesource.com/pdfium/+/refs/heads/main/LICENSE),
[Tesseract licence](https://github.com/tesseract-ocr/tesseract/blob/main/LICENSE).

Maintenance evidence is concrete: 2.15.1 was released 2026-10-01 and fixes a
garbled-font detection issue. An earlier scanned-table OCR bug was closed, and
the inspected version explicitly sets Tesseract's automatic page segmentation
mode. Preserve that regression case in later evaluation rather than presenting
the historical report as an unfixed current defect.
[Release](https://github.com/run-llama/liteparse/releases/tag/python-v2.15.1),
[issue 294](https://github.com/run-llama/liteparse/issues/294).

## Docling: structured conversion with a real model-free option

**Open engine and packaging split.** The MIT project includes the pipelines,
backends and model adapters. In 2.133.0 the `docling` distribution is a small
convenience package depending on `docling-slim[standard]`; its tiny wheel size
does not represent the installed product. The standard extra brings local
models, PDF/Office/web support, OCR, chunking and CLI dependencies. A narrower
`docling-slim` installation can select components. `docling-parse` and
`docling-core` are separate MIT packages, with native parser Windows wheels
published for Python 3.10–3.14 and x64/ARM64.
[Root dependency manifest](https://github.com/docling-project/docling/blob/v2.133.0/pyproject.toml),
[convenience package](https://github.com/docling-project/docling/blob/v2.133.0/packages/docling/pyproject.toml),
[parser files](https://pypi.org/project/docling-parse/7.22.1/#files),
[parser licence](https://github.com/docling-project/docling-parse/blob/v7.22.1/LICENSE).

**The default is not model-free.** Standard PDF conversion initializes layout
analysis regardless of whether OCR or table extraction has been disabled.
Current defaults enable OCR and table structure, use Heron layout and
TableFormer, and select OCR through `OcrAutoOptions`. Therefore the often-seen
`do_ocr=False, do_table_structure=False` example still does model inference.
CPU selection changes the accelerator, not that fact. For Renulus, pin the
chosen CPU engine and English OCR configuration rather than allowing installed
packages to change auto-selection.
[Standard pipeline initialization](https://github.com/docling-project/docling/blob/v2.133.0/docling/pipeline/standard_pdf_pipeline.py#L602),
[pipeline options](https://github.com/docling-project/docling/blob/v2.133.0/docling/datamodel/pipeline_options.py#L2075).

**A genuine native PDF path exists in the inspected release.**
`NativePdfFormatOption` selects `NativePdfPipeline`, using the threaded native
parser. It converts text cells and embedded pictures to document items with
provenance, without layout, OCR or table models. Its source explicitly says it
does not reconstruct reading order, headings or tables: items retain parser
order. This is a useful fallback, not equivalent output to standard Docling.
Do not confuse it with `SimplePipeline`, which is for declarative formats such
as Office/HTML that already encode structure. The narrower dependency selection
is plausible from the manifests; a clean, frozen, model-free Windows startup
was not tested here.
[Native format option](https://github.com/docling-project/docling/blob/v2.133.0/docling/document_converter.py#L293),
[native pipeline](https://github.com/docling-project/docling/blob/v2.133.0/docling/pipeline/native_pdf_pipeline.py#L85),
[simple pipeline](https://github.com/docling-project/docling/blob/v2.133.0/docling/pipeline/simple_pipeline.py).

**Resource and licence scope.** The Heron model card declares Apache-2.0. The
Docling models repository containing TableFormer lists both CDLA-Permissive-2.0
and Apache-2.0; preserve those separate weight terms rather than relabelling all
weights MIT. Exact artifact-level notice mapping remains a distribution task.
Hugging Face metadata at the inspected revisions reports about 171.7 MB for
Heron's safetensors, 212.8 MB for TableFormer accurate, or 145.5 MB for fast.
Thus Heron plus accurate TableFormer alone is approximately **384.4 MB** before
OCR, tokenizer files, Python, PyTorch and other dependencies. This is disk
artifact size, not peak RAM or a measured installer size.
[Heron card and revision](https://huggingface.co/docling-project/docling-layout-heron/tree/8f39ad3c0b4c58e9c2d2c84a38465abf757272d8),
[TableFormer repository and revision](https://huggingface.co/docling-project/docling-models/tree/2199320848bb9a8a519d22e4b528185a4f9a6f64).

RapidOCR is Apache-2.0 software, but its selected detection/recognition weights
and dictionaries still need versioned provenance. Docling's current adapter
can resolve different PP-OCR model generations by language and backend and
has explicit download logic. Pinning only `docling` is not enough to make the
offline artifact set reproducible. Tesseract is an alternative, with its own
binary and language-data packaging requirements.
[RapidOCR licence](https://github.com/RapidAI/RapidOCR/blob/main/LICENSE),
[Docling RapidOCR adapter](https://github.com/docling-project/docling/blob/v2.133.0/docling/models/stages/ocr/rapid_ocr_model.py).

**No owner service is required.** Run the Python converter inside the existing
backend worker architecture; Docling Serve is optional. Prefetching models and
setting an app-owned artifacts path supports offline operation. Remote model
services require opt-in, but disabling them does not itself prevent model
downloads. Disable generative picture/code/formula enrichments and VLM pipelines
for the present scope. Layout/table recognition and OCR do not establish chart
interpretation, histology interpretation or reliable formula transcription.
[Offline and remote-service controls](https://docling-project.github.io/docling/usage/advanced_options/),
[enrichment options](https://docling-project.github.io/docling/usage/enrichments/).

**Chunking is a significant reuse advantage.** `HierarchicalChunker` works from
document structure. `HybridChunker` adds token-budget splitting/merging and
table-header handling, retaining document-item references, headings and origin
metadata. Chunk metadata can lead back to each item's page/bounding-box
provenance. Tokenization is not embedding: the default tokenizer may retrieve
Hugging Face assets, but this chunker does not itself generate dense vectors.
Use a pinned bundled tokenizer and persist the source-item mapping; exporting
only Markdown loses much of the reason to adopt Docling.
[Hierarchical chunker](https://github.com/docling-project/docling-core/blob/v2.99.0/docling_core/transforms/chunker/hierarchical_chunker.py),
[hybrid chunker](https://github.com/docling-project/docling-core/blob/v2.99.0/docling_core/transforms/chunker/hybrid_chunker.py),
[document model](https://github.com/docling-project/docling-core/blob/v2.99.0/docling_core/types/doc/document.py).

**Remaining integration gap.** Put limits around page count, image dimensions,
concurrency and duration, then verify actual CPU RAM/latency on a modest Windows
computer. Pipeline objects and public-model caches are distinct from extracted
case data, but library mode is not a zero-write guarantee. In particular,
Docling's Tesseract CLI adapter creates image files with `NamedTemporaryFile`.
That route is unsuitable for Renulus's strict no-save case path without a
different implementation. An in-process OCR route must be checked separately.
[Accelerator/thread controls](https://docling-project.github.io/docling/reference/pipeline_options/),
[Tesseract CLI temporary files](https://github.com/docling-project/docling/blob/v2.133.0/docling/models/stages/ocr/tesseract_ocr_cli_model.py#L339).

## Kreuzberg / Xberg: broad integration, version-specific conclusions

**Lineage matters.** Kreuzberg 4.8.0 changed from MIT to Elastic License 2.0;
4.10.0 LTS changed back to MIT on 2026-07-11. Current LTS is 4.10.4. Its migration
docs call the successor “v5+”, while the active Xberg repository explains the
new v1 version line; current Xberg is 1.3.3. These observations describe a
rebrand/version reset and licence changes, not interchangeable versions of one
unchanging API.
[LTS changelog](https://github.com/kreuzberg-dev/kreuzberg-lts/blob/v4.10.4/CHANGELOG.md),
[Xberg release](https://github.com/xberg-io/xberg/releases/tag/v1.3.3),
[Xberg MIT licence](https://github.com/xberg-io/xberg/blob/v1.3.3/LICENSE).

**Source is present.** Extraction, configuration, OCR, chunking and native PDF
code are in the public repository. Hosted enterprise offerings are separate.
Current Xberg's default PDF backend is its own Rust engine; PDFium is an optional
feature/backend. Do not copy older Kreuzberg/PDFium architecture descriptions
onto Xberg. Native table extraction uses geometric/heuristic processing; optional
ML layout/table stages are separate.
[PDF backend selection](https://github.com/xberg-io/xberg/blob/v1.3.3/crates/xberg/src/core/config/pdf.rs),
[native parser](https://github.com/xberg-io/xberg/tree/v1.3.3/crates/xberg-native-pdf).

**Explicit model-free configuration is possible.** Set `disable_ocr=True`, leave
layout and embedding options absent, and use ordinary text/Markdown chunking.
`ocr=None` is not a reliable synonym for no OCR in current Xberg: automatic
scanned-PDF fallback can invoke it. Both inspected lines default extraction
caching on. `use_cache=False` is therefore essential for temporary-case work,
and OCR-specific caches require separate inspection. Pin Tesseract or a chosen
PaddleOCR helper explicitly for the approved OCR route; do not enable VLM
fallbacks or provider-based extraction from a convenience preset.
[Xberg defaults](https://github.com/xberg-io/xberg/blob/v1.3.3/crates/xberg/src/core/config/extraction/core.rs),
[Kreuzberg defaults](https://github.com/kreuzberg-dev/kreuzberg-lts/blob/v4.10.4/crates/kreuzberg/src/core/config/extraction/core.rs),
[OCR configuration](https://github.com/xberg-io/xberg/blob/v1.3.3/crates/xberg/src/core/config/ocr.rs).

**Chunking and citation fit.** Chunk results include UTF-8 byte offsets and
optional physical first/last page, heading context and page spans; bounding
boxes depend on available structured nodes. Ensure the relevant page/structure
outputs are enabled and check the actual results. Local embeddings are optional
and absent from default chunking. Creating an embedding configuration activates
another model choice/download; the default balanced model is not automatically
the smallest suitable option. Vector generation is separate from durable
storage and deletion of a user's library.
[Chunk metadata](https://github.com/xberg-io/xberg/blob/v1.3.3/crates/xberg/src/types/extraction.rs#L664),
[chunking/embedding configuration](https://github.com/xberg-io/xberg/blob/v1.3.3/crates/xberg/src/core/config/processing.rs).

**Model and Windows scope.** The project documents helper-model repositories and
downloads to platform caches, including `%LOCALAPPDATA%/xberg/`. Layout and
PaddleOCR model repositories declare Apache-2.0. Those include quite different
sizes: the published mobile PP-OCRv5 detector and English recognizer are about
4.8 MB and 7.8 MB, whereas each SLANeXt table model is about 365.4 MB. Selecting
a table model can dominate the footprint. Names in the model catalog do not
prove that every model is included or enabled in each binding.
[Model sources](https://docs.xberg.io/reference/model-sources/),
[PaddleOCR artifacts](https://huggingface.co/xberg-io/paddleocr-onnx-models/tree/bc5ec866cf0e798e667808dfa51b0ba8ad0dafc8),
[layout artifacts](https://huggingface.co/xberg-io/layout-models/tree/c6bf493e2f7b0b9a29a5870da9880c14e20ff0a3).

The inspected 1.3.3 x64 wheel is about 47.04 MB compressed. It contains
`_xberg.pyd` (109,490,688 bytes), `onnxruntime.dll` (14,148,680 bytes), the shared
provider DLL and a top-level MIT licence file. There were no `.onnx` model entries
in that archive. Its Python Cargo manifest selects a Windows-specific feature
set; Linux “full” features must not be assumed to apply identically. No separate
ONNX server is needed for these DLLs, but frozen-app loading, hardware compatibility
and offline model loading remain untested.
[Wheel files](https://pypi.org/project/xberg/1.3.3/#files),
[Python build features](https://github.com/xberg-io/xberg/blob/v1.3.3/crates/xberg-py/Cargo.toml),
[platform matrix](https://github.com/xberg-io/xberg/blob/v1.3.3/PLATFORM_SUPPORT.md).

**MIT is not the whole binary licence story.** Xberg's own third-party notice
describes MPL-2.0 WordPerfect libraries included in Windows feature sets, and
optional libheif/codec combinations with LGPL or GPL terms on applicable
platforms. This does not establish that the Windows wheel contains GPL libx265;
the notice specifically discusses Linux packaging and platform-dependent codecs.
It does establish that a broad prebuilt artifact requires more than copying its
top-level MIT licence. Tesseract, Leptonica and bundled English language data
have separately documented permissive terms. Prefer only the required document
formats if a narrower build becomes necessary, accounting for the added build
maintenance rather than calling that “zero edits.”
[Native-library and model notices](https://github.com/xberg-io/xberg/blob/v1.3.3/THIRD_PARTY_LICENSES.md).

Judgment: compelling breadth, but rapid platform/API/licence evolution and
cache controls make it a contender to prove, not the obvious least-risk
replacement for all of Supermemory. Its LLM provider support does not establish
Codex or OpenCode Go subscription authentication.

## Other candidates and why they rank lower

**Unstructured.** The Apache-2.0 engine provides typed elements, coordinates,
page metadata and chunking that preserves original-element metadata.
`partition_pdf` has fast, high-resolution and OCR paths; fast PDF extraction
uses pdfminer and does not reconstruct tables like the high-resolution route.
The high-resolution model is chosen from the separate inference package.
Current prose docs mention Detectron2 ONNX, while current inference source
defaults to `yolox`; pin source and model artifacts rather than relying on that
prose as an exact current default.
[Tagged PDF source](https://github.com/Unstructured-IO/unstructured/blob/0.27.10/unstructured/partition/pdf.py),
[chunking](https://docs.unstructured.io/open-source/core-functionality/chunking),
[partitioning docs](https://docs.unstructured.io/open-source/core-functionality/partitioning),
[inference default](https://github.com/Unstructured-IO/unstructured-inference/blob/main/unstructured_inference/models/base.py).

Package extras and external tools such as Tesseract/Poppler/LibreOffice depend
on the format/strategy. These can be packaged, but increase Windows installer
and native-dependency work. Unstructured also has analytics/runtime telemetry;
0.27.10 exposes `DO_NOT_TRACK` or `SCARF_NO_ANALYTICS` opt-out controls. Model
caches, rendered intermediates and telemetry need deliberate handling. Its
hosted Transform MCP/API is a different deployment, not a way to obtain the
local engine for free under the present operating model.
[Installation](https://docs.unstructured.io/open-source/installation/full-installation),
[telemetry controls](https://github.com/Unstructured-IO/unstructured/blob/0.27.10/unstructured/utils.py#L183),
[runtime telemetry](https://github.com/Unstructured-IO/unstructured/blob/0.27.10/unstructured/telemetry.py),
[licence](https://github.com/Unstructured-IO/unstructured/blob/0.27.10/LICENSE.md).

**MarkItDown.** MIT software with a useful simple conversion interface and
per-format extras. Current PDF code uses pdfplumber table/form heuristics and
pdfminer fallback. It returns a Markdown-oriented result rather than a stable
page/box/element provenance object for each passage. Do not repeat the outdated
claim that it has no table logic, but do not assume its single Markdown result
preserves all page references. OCR, image description, Azure Document
Intelligence and Content Understanding are separate optional paths; remote
options do not satisfy this task. The base object invokes Magika, so “no LLM”
does not mean the entire package performs no local inference.
[PDF converter](https://github.com/microsoft/markitdown/blob/v0.1.8/packages/markitdown/src/markitdown/converters/_pdf_converter.py#L495),
[dependencies](https://github.com/microsoft/markitdown/blob/v0.1.8/packages/markitdown/pyproject.toml),
[Magika invocation](https://github.com/microsoft/markitdown/blob/v0.1.8/packages/markitdown/src/markitdown/_markitdown.py#L168),
[Magika project](https://github.com/google/magika).

**LlamaIndex readers.** The current `PDFReader` is a pypdf wrapper; by default it
returns page Documents with `page_label` and filename metadata. Whole-document
mode loses that page-granular wrapper. Useful if LlamaIndex is selected by the
orchestration investigation, but not a reason to add a complete orchestration
dependency for parsing alone. It does not solve scanned PDFs. Keep physical
page index separately from printed page labels.
[Reader source](https://github.com/run-llama/llama_index/blob/main/llama-index-integrations/readers/llama-index-readers-file/llama_index/readers/file/docs/base.py#L28).

**pdfplumber.** MIT library exposing words, characters, lines, page numbers and
bounding boxes; table extraction works geometrically. Good for targeted table
inspection and preserving locators in born-digital PDFs. Its own documentation
says it works best on machine-generated PDFs; it does not supply OCR. More
Renulus-specific parsing decisions would be needed than with the shortlisted
engines. Inspect renderer/transitive notices as well as its own licence.
[Documentation at 0.11.10](https://github.com/jsvine/pdfplumber/blob/v0.11.10/README.md),
[licence](https://github.com/jsvine/pdfplumber/blob/v0.11.10/LICENSE.txt).

**pypdf.** BSD-3-Clause, lightweight pure-Python PDF text/manipulation and page
metadata. Suitable fallback for simple PDFs; it neither performs OCR nor
understands table semantics. Its documentation warns that unusually large
content streams can require much more RAM than compressed file size suggests.
The proposed app needs extraction limits even with a small library.
[Text extraction limits](https://pypdf.readthedocs.io/en/stable/user/extract-text.html),
[licence](https://github.com/py-pdf/pypdf/blob/6.19.0/LICENSE).

**PDF.js.** Apache-2.0 renderer/viewer and text-access API that fits Electron.
Use it for opening citations, page rendering and user verification, with all
viewer assets packaged locally. It is not an OCR, chunking, embedding or memory
engine. Keep a tested package/version and coordinate mapping; extraction
coordinates must account for page rotation, crop boxes and top/bottom origin.
[Project](https://github.com/mozilla/pdf.js),
[API source](https://github.com/mozilla/pdf.js/blob/master/src/display/api.js),
[licence](https://github.com/mozilla/pdf.js/blob/master/LICENSE).

**Marker.** Current 2.0.0 code is Apache-2.0; blanket descriptions of current
Marker as GPL are stale. Its model weights have modified AI Pubs OpenRAIL-M terms,
with commercial eligibility conditions; the README states free use for research,
personal use and startups below its funding/revenue threshold. Current backend
instructions include Surya auto-starting inference with vLLM or llama.cpp, and
optional LLM-enhanced conversion defaults to a separate generative model. This
is not a small helper-only integration within the confirmed subscription model.
Do not conflate the permissive code licence with an unrestricted redistributable
model bundle.
[Current code licence](https://github.com/datalab-to/marker/blob/master/LICENSE),
[model terms and prerequisites](https://github.com/datalab-to/marker#commercial-usage),
[2.0.0 distribution](https://pypi.org/project/marker-pdf/2.0.0/).

**MinerU.** Current 4.0.10 is labelled `LicenseRef-MinerU-Open-Source-License`,
not plain Apache or the older blanket AGPL description. Its licence adds
commercial thresholds and online-service attribution obligations to Apache-2.0.
Even if Renulus is far below the thresholds, those extra downstream terms do not
match the user's preference for uncomplicated permissive reuse. Current README
distinguishes native Flash parsing from model-based Basic/Standard/Advanced;
the default install includes ONNX plus llama.cpp and more advanced paths need
substantial models. A native path exists, but does not make the whole engine a
drop-in minimal dependency.
[Current licence](https://github.com/opendatalab/MinerU/blob/master/LICENSE.md),
[current operating modes](https://github.com/opendatalab/MinerU#model-engines-with-extras),
[4.0.10 metadata](https://pypi.org/pypi/mineru/4.0.10/json).

**PyMuPDF / PyMuPDF4LLM.** Technically relevant PDF extraction, rendering and
table/Markdown tooling, but PyMuPDF/MuPDF are dual AGPL/commercial. Open-source
Renulus is not automatically a licence problem; however, a combined distributed
application needs to satisfy applicable copyleft obligations or obtain the
commercial licence. It is not a straightforward MIT-style component. Permissive
alternatives remove the need to settle that distribution route here.
[Artifex licence statement](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright),
[PyMuPDF4LLM repository](https://github.com/pymupdf/pymupdf4llm).

## What Renulus still needs to implement

These are narrow integration responsibilities around existing engines, not a
proposal to rebuild ingestion/RAG from scratch:

1. **One app-owned ingestion job.** Classify library versus temporary case before
   extraction. Manage queued/processing/ready/failed/cancelled states and publish
   passages only after a successful scope/revision check. Cancellation must stop
   publication even if native parsing cannot stop immediately.
2. **Stable evidence mapping.** Store original document hash and revision,
   extractor/version/configuration, physical page index, printed page label,
   section/item identity, and bounding boxes where supplied. Retain source text
   separately from OCR/normalization and generated descriptions. Preserve a
   table's units, caption, header and footnotes through chunking.
3. **Document quality routing.** Detect partial/empty/garbled extraction and
   missing pages. Retry only with the configured local helper route. If a chart,
   image or formula needs interpretation, the existing chosen-subscription
   capability must be verified; a parser's OpenAI-compatible API setting does
   not prove subscription support. Never label extracted chart labels as chart
   understanding.
4. **Managed artifacts.** Bundle or app-manage the exact CPU runtime, helper
   weights, tokenizer and language assets, with checksums and notices. Test first
   use offline and account for DLL loading on the packaged Windows build.
   Doctors should not install Python, Rust, OCR, LibreOffice or model servers.
5. **Retention and deletion.** Public model-weight caches may persist. Temporary
   case payloads, rendered pages, OCR text, chunks and diagnostic dumps may not
   silently enter persistent caches. A directory later deleted is still a disk
   write. For saved library material, deleting a document must remove eligible
   chunks/index rows, cancel queued work and prevent a stale result republishing
   it. None of the shortlisted parsers enforces Renulus's complete retention
   contract by itself.

These requirements follow the existing
[architecture](../planning/ARCHITECTURE.md) and
[source boundaries](../SOURCES.md). A parser licence does not authorize copying,
embedding, sending to a model or redistributing the medical publication itself.

## Concrete evaluation that can settle the choice

When implementation is authorized, evaluate the preferred **Docling standard
CPU conversion + HybridChunker** path on a small, rights-cleared or synthetic
corpus. Compare **LiteParse + Chonkie prose/table chunkers** on the same inputs
if its smaller footprint could justify the additional provenance/routing work.
Compare the resulting passages and citations, not extraction alone. semchunk
is the simpler text-only option, not the table-aware comparison. Add Xberg only
if its integrated chunking/embedding advantage is under consideration. Use
material spanning CKD, dialysis, transplantation, glomerular disease and
electrolytes; no single-topic demo is sufficient. These are proposed checks;
the source review did not execute either pipeline.

| Check | Decision evidence |
| --- | --- |
| Born-digital guideline, two-column paper, ordinary handout | Paragraph order, missing text and exact page navigation |
| Scanned page, mixed native/scanned PDF, rotated page, broken font map | Automatic OCR routing, explicit failure and stable coordinates |
| Dense table, merged cells, multi-page table | Correct row/header/unit/footnote association after chunking |
| Diagram, chart, formula and clinical image | Correctly preserve source/caption and expose unsupported interpretation |
| Long or malformed document | Bounded RAM/CPU, responsive UI, timeout, cancellation and recovery |
| Temporary synthetic case with sentinel text | No app-owned payload persistence, logs or OCR-result cache; crash/restart check |
| Delete or replace during ingestion | No stale passage/index publication or reappearance after restart |
| Fresh Windows installation, offline | No developer tools, network model fetch, GPU, Docker or extra service needed |

Measure packaged size, cold/warm latency, peak working set and foreground UI
responsiveness. Do not invent performance thresholds from vendor speed claims:
set them against the supported Windows hardware and actual user flow. Report
incorrect extraction separately from unsupported content. Research alone does
not justify a claim that any candidate is clinically reliable.

## Dated releases, artifacts and discovery trail

| Project / package | Version observed | Publication evidence on or before cutoff |
| --- | --- | --- |
| Docling | 2.133.0 | [GitHub release, 2026-10-03](https://github.com/docling-project/docling/releases/tag/v2.133.0) |
| Docling core | 2.99.0 | [GitHub release, 2026-09-25](https://github.com/docling-project/docling-core/releases/tag/v2.99.0) |
| Docling parse | 7.22.1 | [PyPI files, 2026-09-28](https://pypi.org/project/docling-parse/7.22.1/#files) |
| LiteParse Python | 2.15.1 | [GitHub release, 2026-10-01](https://github.com/run-llama/liteparse/releases/tag/python-v2.15.1) |
| Chonkie | 1.7.0 | [PyPI metadata, 2026-07-07](https://pypi.org/pypi/chonkie/1.7.0/json) |
| semchunk | 4.1.1 | [PyPI metadata, 2026-06-13](https://pypi.org/pypi/semchunk/4.1.1/json) |
| Kreuzberg LTS | 4.10.4 | [Tagged changelog, 2026-09-21](https://github.com/kreuzberg-dev/kreuzberg-lts/blob/v4.10.4/CHANGELOG.md) |
| Xberg | 1.3.3 | [GitHub release, 2026-10-03](https://github.com/xberg-io/xberg/releases/tag/v1.3.3) |
| Unstructured | 0.27.10 | [GitHub release, 2026-09-27](https://github.com/Unstructured-IO/unstructured/releases/tag/0.27.10) |
| MarkItDown | 0.1.8 | [GitHub release, 2026-09-21](https://github.com/microsoft/markitdown/releases/tag/v0.1.8) |
| pypdf | 6.19.0 | [PyPI metadata, 2026-09-16](https://pypi.org/pypi/pypdf/6.19.0/json) |
| pdfplumber | 0.11.10 | [PyPI metadata, 2026-06-15](https://pypi.org/pypi/pdfplumber/0.11.10/json) |
| PDF.js distribution | 6.4.299 | [npm registry publication metadata, 2026-10-03](https://registry.npmjs.org/pdfjs-dist) |
| Marker PDF | 2.0.0 | [PyPI metadata, 2026-07-20](https://pypi.org/pypi/marker-pdf/2.0.0/json) |
| MinerU | 4.0.10 | [PyPI metadata, 2026-09-29](https://pypi.org/pypi/mineru/4.0.10/json) |
| PyMuPDF | 1.28.2 | [PyPI metadata, 2026-08-06](https://pypi.org/pypi/PyMuPDF/1.28.2/json) |

Registry file dates above refer to uploads; GitHub dates refer to releases.
These are freshness signals, not guarantees of support or reasons to adopt the
latest version without checks. LiteParse's root `CHANGELOG.md` still shows the
older 1.5.x line despite 2.15.1 release artifacts: use the per-language release
tags and inspected source for current claims. Xberg/Kreuzberg naming and
Unstructured model-default documentation also need the distinctions made above.

Static wheel identity, useful for reproducing this investigation:

- LiteParse x64 2.15.1 SHA-256:
  `698a332ec1b6f932f1f065df11fcb52bd1f95acaec7056333070501173ba8cac`.
- Xberg x64 1.3.3 SHA-256:
  `de74a9ff513ba0f781d9178008ff0e359ff38303d1bed466172f2432c3f21a51`.

Both hashes were read from the publisher's PyPI JSON and correspond to the
archives inspected without installation:
[LiteParse registry record](https://pypi.org/pypi/liteparse/2.15.1/json),
[Xberg registry record](https://pypi.org/pypi/xberg/1.3.3/json).

Social discovery surfaced discussions about ingestion bottlenecks and native
desktop integration, including
[this LocalLLaMA thread](https://www.reddit.com/r/LocalLLaMA/comments/1pamu5t/i_spent_2_years_building_privacyfirst_local_ai_my/)
and [this RAG parsing discussion](https://www.reddit.com/r/Rag/comments/1q0bzyg/those_running_rag_in_production_whats_your/).
They were prompts for source checks, not evidence of reliability, licence
permissions or comparative accuracy. Recent releases and examined code are
stronger adoption evidence than stars or promotional “fastest” claims. This
note does not claim a verified GitHub Trending ranking on 2026-10-04.
