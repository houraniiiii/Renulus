# Design C implementation review — pass 1, readers/platform

Reviewed October 10, 2026 against **1b30a89687cfcc5fb13b1cf824bbc43c19f870ed**
on `codex/dc-review-readers`; `528025ff` is an ancestor of that baseline.
This is the independent reader/platform implementation review for DC07–DC11.
The sole reserved repository path is this report. No source, spec, manifest,
schema, dependency or upstream file was changed. No feature ticket is closed.

The selected spec describes the principal gaps honestly. Its prior planning
review is not evidence that these gaps are implemented. The material blockers
below concern shortcuts that would fail its connected acceptance requirements.
Proceed with bounded M2 adapters after the integration lead publishes the
reservations and supplies the parent-owned platform prerequisites below.
The later parent instruction identifies contract proposal `efcc7824`; it was
read directly from that commit without merging or changing the review baseline.
It freezes `knowledge_attachments.id/chat_kind/chat_id` and
`knowledge_attachment_originals.id/attachment_id`, with saved-only owned edges.
Existing saved Case attachment/original IDs and bytes retain Case authority.
These are contract shapes, not evidence that their routes/tables are installed.
No dependent code will start before the parent publishes file reservations.

## Evidence and limits

Read AGENTS.md, README.md, PRODUCT.md, DESIGN.md, docs/PROJECT_BRIEF.md,
docs/WORKSPACE.md, docs/DECISIONS.md, docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md,
docs/planning/ARCHITECTURE.md, docs/planning/PARALLEL_WORK.md and
docs/implementation/APP_CONTROL.md in the assigned worktree. Inspected only
relevant tracked code and named, installed development dependencies. No archive,
owner profile, credentials, acquired collection or private/native app state was
read. No provider/model request, dependency installation, OS input, foreground
window or application launch was used.

All generated files, temporary files and cache settings belong to
`C:/Renulus/scratch/design-c/dc-review-readers/`. Evidence there:

| File | Actual observation |
| --- | --- |
| `reader-platform-js-proof.json` | Ran the bundled **baseline** `ownedApiHeaders` function and the baseline controller's fixture functions. Same-owner simulated document/frame/image requests receive the synthetic token; another webContents is cancelled. CSV/MD/HTML manifests fail; malformed signature-only PDF is accepted as upload bytes. |
| `reader-platform-python-proof.json` | Ran repository admission/original guards with deliberately minimal synthetic objects, plus **actual pinned Docling Office conversion** of a synthetic XLSX. Recorded permission/status failures and missing display/formula information. |
| `python-probe.py` | Retained exact successful Python reproduction. Uses only the explicit worktree runtime and synthetic workbook; blocks socket connections/name resolution and external subprocess creation before conversion. |
| `python-package-inventory.json` | Named package versions read through the pinned development interpreter's distribution metadata. |
| `javascript-package-inventory.json` | Named packages checked in the active desktop lock and at the explicit shared development node_modules root. |

The JavaScript authentication check is a function-level reproduction with mock
request metadata, **not** an Electron subframe exploit demonstration. The
repository guard check uses a synthetic database response and does not prove a
new storage flow. Office conversion is actual parser execution without model
weights or network. An initial probe replaced `subprocess.Popen` too early and
failed while asyncio imported its Windows class; the successful reproduction
imports asyncio first and patches `Popen.__init__` instead. No successful reader,
hidden C journey, packaged reader or native/live acceptance is claimed.

## Material findings

### RR1 — P1: sanitising scripts alone leaves the owning-window API authority intact

**Source:** `apps/desktop/electron/main.ts:69–86`,
`apps/desktop/electron/owned-api-headers.ts:7–22`,
`apps/desktop/electron/frontend.ts:7–35`,
`apps/desktop/electron/preload.ts:3–9`,
`runtime/renulus/knowledge/api.py:184–190`.

The main session permits its whole loopback origin, data/blob URLs and bundled
PDF resources. The API hook tests window lifetime and **webContents ID only**;
it has no frame identity, initiator, URL-purpose or resource-type policy. Same
origin top-level navigation is permitted. The frontend accepts the stamped
token and forwards the request to the backend. A document resource/link/form
must therefore be stopped before it acquires this authority. Removing script
tags, withholding preload, or adding a sandbox with no scripts is not sufficient
evidence on its own.

The original route sends `Content-Security-Policy: default-src 'none'`, but the
frontend API proxy forwards only Content-Type and Cache-Control from that
response and has already supplied the app's more permissive CSP. Moreover,
`OriginalViewer` turns bytes into a fresh Blob URL; an endpoint response header
is not a document sanitisation mechanism for that new output. Preserve the
host-mediated retrieval, but do not treat that original header as the isolation
proof.

**Reproduction already run:** call `ownedApiHeaders` with a live synthetic owner
ID 23, and pass `{webContentsId:23, requestHeaders:{}, resourceType:'image',
frame:{url:'blob:http://127.0.0.1:1234/synthetic'}}`. The synthetic token is
stamped. Changing only webContentsId to 24 returns `{cancel:true}`. The controller
also returns true for `requestAllowed('http://127.0.0.1:1234/api/v1/library/documents',
'GET','http://127.0.0.1:1234')`; it is not a document-security firewall.

**Payload for the future isolated-reader test** (fixture data only, never inject
into the privileged shell):

```html
<base href="http://127.0.0.1:1234/">
<meta http-equiv="refresh" content="0;url=/api/v1/__reader_probe__">
<img src="/api/v1/__reader_probe__?from=image">
<link rel="stylesheet" href="/api/v1/__reader_probe__?from=stylesheet">
<style>p { background-image: url('/api/v1/__reader_probe__?from=css'); }</style>
<a href="/api/v1/__reader_probe__?from=link" target="_top">Synthetic link</a>
<form action="/api/v1/__reader_probe__?from=form" method="post" target="_top">
  <button>Submit synthetic form</button>
</form>
<iframe src="/api/v1/__reader_probe__?from=frame"></iframe>
<script>window.renulus && window.renulus.version()</script>
```

Use an owned loopback counting stub for `__reader_probe__`, not a real mutation
or generation endpoint. Also test absolute app-origin URLs, data/blob nested
frames, file URLs pointing only at a synthetic sentinel, and external
`https://example.invalid/` resources. Assert **zero document-origin requests**,
no authenticated bridge invocation, no shell navigation and no automatic
external handoff. A network error after a request reaches an API is not a pass.
This is a prerequisite for introducing HTML/Office-derived markup; the current
Library does not yet admit generic HTML/XML, so this report does not assert an
existing imported-HTML exploit.

**Smallest adaptation:** trusted host retrieves bytes by canonical reference;
M2 renders a bounded inert structured representation with text nodes, local
validated images, and host-handled explicit links. Strip active elements,
forms, base/meta navigation, URL-bearing CSS and arbitrary resource URLs. F0
owns the main-frame/request/IPC checks and negative Electron evidence. If an
isolated frame is chosen, prove its origin/session/request boundary separately;
do not transplant Hermes's general browser webview.

### RR2 — P1: the existing Library original path cannot provide independent preview

**Source:** `runtime/renulus/knowledge/repository.py:165–170,202–210,694–703`,
`runtime/renulus/knowledge/api.py:117–139`,
`apps/desktop/src/modules/library/SourceInspector.tsx:16–48,70–85`,
`runtime/renulus/knowledge/schema.sql:1–26`.

Admission requires deliberate personal-library scope. Normal imports need
display/cache/index/embedding permission together. Original retrieval requires
`status == 'ready'`, and SourceInspector first loads a citation that also requires
a ready revision. Those statuses represent ingestion/index publication, not
whether preserved bytes can safely be read. Reusing the route unchanged for
Attach forces permanent import/indexing or hides an original when extraction
fails. It also does not establish conversation-owned or temporary originals.

**Reproductions already run:** `_import` with synthetic Markdown and
`Rights(display=True, cache=True)` returns `403 source_permission_required` before
storage. A synthetic failed revision whose original file exists, with display
permission, returns `404 original_missing` from `original()`. The preserved file
was `synthetic-note.md` under this worker's scratch root.

**Required connected reproduction:** attach a valid PDF/Office file with
extraction unavailable; read it immediately; optionally index it deliberately
later; remove it during a preview request; restart a saved attachment and an
explicit temporary attachment. Only the saved attachment may return after
restart. Repeat with display denied, model-input denied, a deleted owner,
missing original and failed extraction. Preserve those as distinct errors.

**Smallest adaptation:** add a typed reference resolver and preview operation
whose permission/state checks are independent of indexing. Reuse owned-file
containment/hash/deletion/display checks; do not relax `original()` indiscriminately
or grant embedding/model_input as a side effect of viewing. DC02 must publish
ownership/retention/tombstone meaning first. M2 then supplies the reader API and
Library adapter; M1/M3 supply conversation-owned references through that contract.
Use the `efcc7824` saved-chat attachment/original identities rather than inventing
a second attachment store. Resolve legacy saved Case references through their
existing Case owner and original route; do not copy those bytes or replace their
authority with new Knowledge rows. Explicit temporary attachments and their
original/preview identities remain volatile; never insert them into the proposed
saved-only tables. The parent owns `knowledge-003` migration sequencing and typed
recovery declarations.

### RR3 — P1: successful XLSX extraction loses displayed values and missing-cache meaning

**Source:** `runtime/renulus/knowledge/office.py:190–224,227–254`,
`tests/knowledge/test_office_conversion.py:183–209`; installed pinned source
`C:/Renulus/dev/python/Lib/site-packages/docling/backend/msexcel_backend.py:387–393,1153`.

The selected backend calls openpyxl with `data_only=True` and emits
`str(cell.value)`. It does not retain the cell's number-format display or
distinguish an empty cell from a formula lacking a cached result. The existing
formula test proves no link execution; it does not prove reader fidelity.

**Actual reproduction already run:** create this small workbook with pinned
openpyxl, validate it through `validate_office` and pass it to
`office_converter().convert(path, raises_on_error=False)`:

```python
from openpyxl import Workbook
book = Workbook()
sheet = book.active
sheet.title = 'Synthetic CKD'
sheet.append(['Property', 'Value'])
sheet.append(['Percent', 0.15]); sheet['B2'].number_format = '0%'
sheet.append(['Leading zeros', 7]); sheet['B3'].number_format = '0000'
sheet.append(['Formula without cache', '=1+1'])
# Save only under C:/Renulus/scratch/design-c/dc-review-readers/.
```

Docling returned `ConversionStatus.SUCCESS`. The value-cell texts were
`'0.15'`, `'7'` and `''`. The original cells have formats `0%` and `0000`; a
second openpyxl read with `data_only=False` reveals `=1+1` in B4 while its cached
read is None. Rendering only the extracted table would imply the wrong displayed
values and silently omit the reason for B4's blank.

**Smallest adaptation:** keep Docling/HybridChunker for eligible text extraction.
Use the already pinned openpyxl parser after OOXML admission to expose bounded
sheet/cell DTOs: coordinates/ranges, literal value, number format, cached value
and missing-cache status. Preserve supported display formats and label unsupported
details explicitly. Read formula identity without evaluating it; never execute
formulas, macros or external links. A metadata pass is needed even when text
extraction succeeds. Verify dates, percent/units, leading zeros, merged cells,
multiple/empty sheets, sparse limits and missing cached formulas.

### RR4 — P1: format support and selection locators need new adapters, not extension-only admission

**Source:** `runtime/renulus/knowledge/repository.py:24–26`,
`runtime/renulus/knowledge/engines.py:248–318,373–384`,
`apps/desktop/src/modules/library/file-formats.ts:3–34`,
`apps/desktop/src/modules/library/types.ts:33–53`,
`apps/desktop/src/modules/library/source-locators.ts:7–22`,
`runtime/renulus/retrieval/literature.py:102–111`.

CSV/HTML/XML are absent from backend MEDIA and frontend admission. Temporary
byte extraction also excludes DOCX/XLSX/PPTX, not only the new text categories.
Markdown enters the current extractor as plain UTF-8 paragraphs. Office locators
provide useful item/table IDs and sheet geometry, but current TS locators have no
CSV row/cell, HTML section, generic XML node or selected-range contract. DOCX
ordinals must stay distinct from PDF pages; physical/printed PDF pages are also
distinct. Acquired JATS uses an article/licence/identity-specific parser and is
not a general XML reader.

**Reproduction:** the successful Python probe records `['.csv','.html','.xml']` as
absent from MEDIA. Existing tests explicitly expect temporary Office bytes to
return `unsupported_file`
(`tests/knowledge/test_office_conversion.py:234` onwards). Payloads below are new
acceptance inputs, not currently successful imports:

```csv
topic;value;unit;note
CKD;0,15;fraction;"first line
second line"
dialysis;=HYPERLINK("https://example.invalid/never-fetch");literal;0007
```

Declare semicolon/encoding explicitly when inference is ambiguous; also test
UTF-8 BOM and a declared UTF-16 encoding, quoted delimiters, blank rows, very wide
rows and a single oversized field. Formula-looking CSV strings remain literal.
Keep original row identity when blank rows or multiline fields are present.

```xml
<?xml version="1.0"?>
<!DOCTYPE study [<!ENTITY x SYSTEM "file:///C:/Renulus/scratch/design-c/dc-review-readers/synthetic-note.md">]>
<study><topic>Transplantation</topic><paragraph>&x;</paragraph></study>
```

Reject DTD/entity/external resolution before parsing. Test UTF-16 declarations,
deep nesting, large sibling counts and malformed XML. A safe positive fixture
is `<study><topic>Transplantation</topic><value unit="synthetic">7</value></study>`,
displayed as escaped text/tree with stable node/text positions. Generic support
must not claim JATS or other medical-schema interpretation.

**Smallest adaptation:** pinned Docling 2.133.0 already contains
`CsvFormatOption`, `HTMLFormatOption` and `InputFormat.MD`. Its CSV backend reads
the whole decoded input, calls `list(csv.reader(...))`, then constructs every
table cell (`docling/backend/csv_backend.py:135–147,175–205`). Add preflight
row/column/field/parser bounds and source-row mapping before conversion; a 64 MiB
byte cap alone does not bound those allocations. For HTML use the selected
model-free pipeline with explicit no-remote/no-local fetch and
`HTMLBackendOptions(render_page=False)`; conversion is extraction, not sanitised
HTML rendering. Reuse pinned defusedxml for generic XML with explicit DTD/entity
refusal and node/depth/text limits. Keep source mapping in the host reference
contract and separately prove passage-to-draft and DC17 extraction consumers.

### RR5 — P1: the hidden controller cannot currently establish eight-format C acceptance

**Source:** `tools/renulus-control/controller.mjs:11–16,146–170,329–335,475–508,610–649`,
`tools/renulus-control/server.mjs:8–25`,
`tools/renulus-control/test/fixtures.test.mjs`,
`tools/renulus-control/test/controller.test.mjs`.

Startup waits for exactly one visible navigation landmark named `Main navigation`.
Hiding/collapsing that landmark can make a usable C app fail readiness. File-input
observations require an ID, associated label text and one of four exact legacy
labels. A C input named only through `aria-label="Attach"` is not admitted by this
logic; adding Attach's extension list alone does not fix that. Observation is
limited to the first eight file elements and cannot target reader subframes.

Fixture names/MIME/signatures admit only PDF/PNG/JPEG. **Already reproduced:** a
correctly hashed single-file manifest for each of `synthetic-table.csv`,
`synthetic-note.md` and `synthetic-hostile.html` returns
`invalid_fixture_manifest`. Declared `synthetic-broken.pdf` containing the six
bytes `%PDF-x` passes the controller's signature check. This is intentional
admission-level checking, not a parser pass; retain corrupt cases to prove
recoverable application failure.

The controller exposes normal API routes, including inference. Keep this run
disconnected/synthetic; do not infer a no-provider firewall from the controller.
New isolated-reader surfaces also need app pixels and bounded host observables
for page/selection/error state because there is no arbitrary evaluation tool.
Do not broaden the tool to arbitrary scripts, arbitrary frames or filesystem
paths to obtain that evidence.

**Smallest adaptation:** F0 updates a stable observed C readiness landmark that
survives collapse/offline/error states, and a narrowly recognised C study-attachment
input contract. Extend the frozen fixture manifest basename/signature/MIME table
for DOCX, CSV, XLSX, Markdown, HTML, XML and TIFF. OOXML needs matching container
validation, not only `PK`; text needs bounded declared encoding, not an invented
magic header. Preserve hashes, frozen declaration, link/junction/hardlink guards,
credential/directory refusal and in-memory setInputFiles. Keep signature-valid
corrupt specimens distinct from valid positive fixtures. New formats can be
split across declared fixture sets rather than raising the 32-file limit.

**Required evidence after adapter integration:** hidden C start/restart with
collapsed sidebar and at 640×540, 1000×720 and 1440×900; actual observed Attach
upload; eight categories plus multi-frame TIFF; successful/failed parser state;
page/cell/selection host state; screenshot; normal owned cleanup. Active-Test
denial is a backend policy observation, not merely a hidden button. No physical
Windows scaling/dialog or installed capability follows from those checks.

### RR6 — P2: the current viewer is not a workspace reader/state adapter

**Source:** `apps/desktop/src/modules/library/OriginalViewer.tsx:7–47`,
`apps/desktop/src/modules/library/SourceInspector.tsx:80–84`,
`apps/desktop/src/shell/ModuleOutlet.tsx:50–55`,
`apps/desktop/src/modules/library/OriginalViewer.test.tsx`.

PDF is a Chromium Blob iframe with a page fragment; PNG/JPEG is an image; Markdown
is a preformatted text block; Office and TIFF use Save original fallback. None
proves C's eight in-app readers. Native PDF controls may be reusable, but current
tests do not establish their packaged search/selection/zoom or a source-selection
handoff. Images have no explicit fit/zoom/pan controller. TIFF is explicitly
unpreviewable despite Pillow and the pinned Docling image backend supporting
frame iteration. SourceInspector explicitly says exact passage highlighting is
unavailable.

ModuleOutlet remounts on route/revision. OriginalViewer's cleanup and cached
original are tied to component lifetime, not a canonical reference change.
SourceInspector currently supplies a key by revision/page, which avoids that
reuse hazard there; lifting the component into persistent tabs without equivalent
identity handling would show stale bytes. It would also lose reader position on
current remounts. Persist only safe state keyed by owner/revision/tab identity,
and abort/revoke when identity, eligibility or deletion changes.

**Reproduction to add:** open revision A; change the citation prop to B while
retaining the component; click Open original. Its `if (busy || original) return`
guard prevents B loading and leaves A's cached content. A future regression check
must switch A/B during an outstanding request as well as after it completes.
Open the same canonical file twice, two different chats, a deleted revision and
a temporary attachment; switch tabs/resize/restart and check the correct position
and scope without stale content or restored temporary metadata.

**Smallest adaptation:** retain the approved host fetch/abort/Blob cleanup and
Chromium PDF candidate; prove native controls and use an explicitly identified
extracted passage fallback when selection cannot be safely mapped. Add bounded
Pillow TIFF frame-to-PNG output independent of OCR, plus image fit/zoom/pan.
Use model-free Docling Office structured output for DOCX headings/lists/tables/
images, while separating conversion from chunk/index readiness. Render only
validated inert data. Test corrupt images, unsupported details, multiple frames
and truthful no-OCR states. Do not treat Save original as the reader pass.

### RR7 — P2: upstream references and installed packages are not active bundled readers

**Source:** `apps/desktop/package.json` and `package-lock.json`,
`packaging/runtime/requirements-helpers.txt`,
`packaging/runtime/windows-cp314-wheels.json`,
`upstream/hermes/apps/desktop/package.json`,
`upstream/hermes/apps/desktop/src/app/chat/right-rail/preview-file.tsx`,
`upstream/hermes/apps/desktop/src/app/chat/right-rail/preview-pane.tsx:1538–1545`.

| Capability | Available pinned foundation | Qualification |
| --- | --- | --- |
| Native PDF | Active Electron 44.5.1, Chromium viewer/resource allowlist | No PDF.js package in active desktop lock/shared root. Keep reuse candidate; actual C/package behavior remains to prove. |
| Office structure | Docling 2.133.0, docling-core 2.99.0; python-docx 1.2.0, openpyxl 3.1.5, python-pptx 1.0.2 | Versions found locally and in the wheel manifest. Structured extraction exists; embedded readers/preview DTOs do not. |
| Images/TIFF | Pillow 12.3.0 and Docling multi-frame image backend | Decoder exists; no in-app TIFF frame reader or zoom/pan UI. |
| Generic XML | defusedxml 0.7.1, lxml 6.1.3 | Already pinned transitive packages; generic reader/extraction adapter still required. |
| CSV/HTML/MD parsing | Installed Docling format options/backends | Runtime currently does not dispatch CSV/HTML; bounds/security/mapping must be adapted. |
| Renderer candidates | Retained Hermes declares Streamdown 2.5.0, DOMPurify 3.4.13, fflate 0.8.3 | None is in the active desktop lock or the checked shared root. A retained manifest does not make them bundled or usable. |
| Development control | Shared Playwright 1.62.1, canonical tools/renulus-control SDK 1.32.1 | Worktree has no local node_modules. SDK is available in canonical controller's explicit node_modules, not shared root. Resolve only these known paths; never install or borrow app/account state implicitly. |

Also absent from the checked active lock/shared root: react-pdf, pdfjs-dist,
mammoth, docx-preview, xlsx and papaparse. Trafilatura, pypdf and pdfplumber are
absent from the inspected pinned Python environment. This is a bounded inventory,
not a registry search or a statement that these packages cannot be adopted later.

Hermes's preview-file component imports gateway desktop-fs read/write operations,
connection/cwd stores, composer focus/ref insertion, editors and Streamdown. Its
general webview path conflicts with Renulus's explicit `will-attach-webview` denial.
The remote HTML branch uses `sandbox=""`, but still needs Renulus's RR1 request
boundary. Do not copy the whole preview/browser/editor subsystem.

**Smallest reuse:** the source/reference patterns, PDF Blob lifetime, bounded text
windowing and the React-only hook in
`upstream/hermes/apps/desktop/src/components/chat/fixed-row-window.ts` are suitable
bounded candidates. Preserve upstream attribution. Prefer the already selected
Python parsers and inert renderer DTOs to adding a second Office ingestion engine.
Any actual new renderer package needs the parent's explicit manifest/lock/notices
patch and packaged evidence with local assets/workers and no CDN fetching.

### RR8 — P2: DC09–DC11 consumers cannot be completed by remounting the old modules

**Source:** `apps/desktop/src/shell/App.tsx:58,73–79`,
`apps/desktop/src/modules/library/index.tsx:265–276,398–417`,
`runtime/renulus/knowledge/repository.py:440–473,531–579`,
`runtime/renulus/study/api.py`,
`apps/desktop/src/modules/library/SourceInspector.tsx`.

The shell finder searches route labels only. Knowledge document filters search
titles/source IDs; passage retrieval is a different scoped/indexed operation.
There is no grouped chat/project/file/note search contract here, nor a workspace
selection-to-editable-draft action. Study owns global preferences/goals; these
are not project-linked note revisions/goals. File opening must not imply model
attachment, and rendering a search snippet must itself use the shared assessment
and retention policy.

**Required reproductions:** title-only preview and extraction-failed files remain
findable as permitted metadata but produce no invented content hit; deleted or
denied content produces no snippets; rapid A/B queries cannot publish A as B;
archived handling is explicit; two projects sharing a file keep one canonical
original. Asking about a selected passage appends a bounded pinned locator to an
existing draft, does not Send, and fails honestly after revision deletion/rights
change. Notes save/edit/delete/reopen through actual records, not a fixture.

**Smallest adaptation:** M2 publishes metadata search and eligible passage/query
adapters against the frozen reference/policy contract. The parent owns query
sequencing/grouped shell UI, DC07 tabs and M1/M6 composition; M2 supplies note
storage behavior only after its ownership/revision contract is assigned. Keep
index failure, preview availability and content-search eligibility separate.
DC07/DC11 can prove policy-interface denial with contract fixtures; DC14/DC20
must later prove the actual active-Test producer, including stale cached surfaces.

## Exact proposed source reservations

These are **requests for future exclusive leases**, not source changes or new
ownership acquired by this reviewer. Names marked new are proposed adapter
locations; the parent can rename them before freezing the lease. Split workers
must not independently edit the registry, API or extractor coordinator paths.
The planned M2 implementation lane covers readers/attachments and Knowledge
extraction. DC07 workspace/tab adapters belong to a different owner. Electron
isolation, root dependencies, locks and manifests remain **parent-owned**; the
platform rows below request exact parent prerequisites rather than a worker lease.

| Lease / owner | Exact files requested | Purpose / prerequisite |
| --- | --- | --- |
| M2 reader coordinator | `runtime/renulus/knowledge/repository.py`; `runtime/renulus/knowledge/api.py`; `runtime/renulus/knowledge/engines.py`; `runtime/renulus/knowledge/reader.py` (new); `apps/desktop/src/modules/reader/types.ts` (new); `apps/desktop/src/modules/reader/Reader.tsx` (new); `apps/desktop/src/modules/library/types.ts`; `apps/desktop/src/modules/library/file-formats.ts`; `apps/desktop/src/modules/library/source-locators.ts` | One reference resolver, independent original/preview/extraction states, bounded DTO/selection contract and registry. Depends on DC02 ownership/policy/locator publication; coordinate backend API mounting with parent. |
| M2 PDF/image slice | `apps/desktop/src/modules/library/OriginalViewer.tsx`; `apps/desktop/src/modules/library/OriginalViewer.test.tsx`; `apps/desktop/src/modules/reader/ImageReader.tsx` (new); `runtime/renulus/knowledge/image_preview.py` (new); `tests/knowledge/test_reader_images.py` (new) | Adapt current Blob/PDF lifecycle; bounded TIFF frames and image controls; consume coordinator's reference/DTO contract and F0 isolation. |
| M2 Office/table slice | `runtime/renulus/knowledge/office.py`; `runtime/renulus/knowledge/table_preview.py` (new); `apps/desktop/src/modules/reader/StructuredReader.tsx` (new); `apps/desktop/src/modules/reader/TableReader.tsx` (new); `tests/knowledge/test_reader_office.py` (new) | Reuse admitted Docling/openpyxl structure, preserve XLSX display/cache meaning and typed locations. Coordinator alone changes engines dispatch. |
| M2 text/markup slice | `runtime/renulus/knowledge/text_formats.py` (new); `apps/desktop/src/modules/reader/MarkupReader.tsx` (new); `tests/knowledge/test_reader_text_formats.py` (new) | CSV preflight/source mapping plus bounded inert HTML/XML and Markdown representation. No direct shell HTML insertion or new parser engine. |
| M2 connected Library consumer | `apps/desktop/src/modules/library/index.tsx`; `apps/desktop/src/modules/library/SourceInspector.tsx`; `apps/desktop/src/modules/library/SourceInspector.test.tsx`; `apps/desktop/src/modules/library/library.css`; `apps/desktop/src/modules/library/LibraryBrowser.test.tsx`; `tests/knowledge/test_reader_api.py` (new) | Preserve import/retry/source/status/permissions while connecting Read/Discuss to parent workspace/draft contracts. Assign after coordinator API stabilises; no shell/shared UI writes. |
| Parent-owned F0 native isolation prerequisite | `apps/desktop/electron/main.ts`; `apps/desktop/electron/owned-api-headers.ts`; `apps/desktop/electron/owned-api-headers.test.ts`; `apps/desktop/electron/frontend.ts`; `apps/desktop/electron/frontend.test.ts`; `apps/desktop/electron/preload.ts`; `apps/desktop/src/platform/desktop.d.ts`; `apps/desktop/electron/reader-isolation.test.ts` (new) | Trusted host/frame/IPC/request checks and actual negative synthetic document proof. Refine implementation before committing a lease; do not let multiple M2/F0 workers patch main.ts. Existing platform backup/runtime behavior must remain. |
| Parent/F0 controller prerequisite | `tools/renulus-control/controller.mjs`; `tools/renulus-control/server.mjs`; `tools/renulus-control/test/controller.test.mjs`; `tools/renulus-control/test/fixtures.test.mjs`; `tools/renulus-control/test/server.test.mjs`; `tools/renulus-control/README.md` | Stable C readiness/Attach observation and bounded format/fixture admission, with current hidden/process/path safeguards. Depends on agreed shell landmarks, reader format matrix and external synthetic manifests. |

No new package is required merely to start these adapters. If native PDF cannot
meet the actual reader behavior or a renderer library proves necessary, submit a
separate measured dependency prerequisite to the parent; do not install it in
the workers or call a hosted reader.

**Parent-owned prerequisites, not worker leases:**

- Shared canonical content/attachment owner/revision/retention/tombstone and
  locator contracts under `packages/contracts/`, including model-use and
  active-Test policy operations. Revalidate references server-side at draft use;
  rendered text is not permission authority.
- `apps/desktop/src/shell/App.tsx`, `ModuleOutlet.tsx`, `navigation.tsx` and
  shell styles; all shared UI/tokens; workspace/tab persistence, draft composition,
  query generation/grouping and stable C controller landmarks.
- Storage migration sequencing and attachment/note/project export/restore/delete
  coverage. `runtime/renulus/storage/recovery_archive.py:25–29` currently allowlists
  PDF/images/TXT/MD/Office originals but not CSV/HTML/XML; new originals need
  coordinated inclusion and populated round-trip/deletion proof.
- Active desktop/package/controller locks, runtime wheel/helper manifests,
  packaging/CSP build configuration (including `apps/desktop/index.html`), dependency
  notices and matching packaged evidence. A parent patch must preserve the
  separate original/source/renderer policies in both development and packaged
  paths; a source-only pass is insufficient.
- M1/M3 Attach ownership and passage-to-draft, M6 note/goal composition and M4/DC17
  extraction consumers; DC14/DC20 integrated policy proof. Do not hand these
  responsibilities to a reader component by passing arbitrary paths or raw HTML.

## Acceptance payload/receipt checklist for the implementation lead

| Slice | Positive synthetic data | Adversarial/failed data and receipt to retain |
| --- | --- | --- |
| PDF | Two physical pages, different printed labels; text page, units/table and cited page | Scan/no-OCR, wrong page, encrypted/corrupt/over-limit; in-app search/zoom/selection or explicit mapped current passage; preserved draft and pinned source jump. |
| DOCX | Headings/list, units table, embedded PNG, inert hyperlink | Empty/failed extraction while preview remains, unsafe external picture, DTD/macros/embedded object, corrupt picture; reflow has section/item locators, no fabricated page. |
| CSV/XLSX | Semicolon/BOM/multiline/blank-row CSV; multiple sheets with display-format workbook above | Oversized field/wide/sparse tables, cached/missing formula, display formats/merged cells, literal formula-looking strings; bounded row/cell locators and no evaluations. |
| Markdown/HTML/XML | CKD/dialysis/transplantation headings, lists, links, code, tables; generic XML text/tree | RR1 inert resource/form/navigation payload, encoded entities/UTF-16/deep XML, local/external links, malformed text; zero document authority/requests, bounded stable source positions. |
| Images | PNG/JPEG and two-frame synthetic TIFF; distinct frame labels | Corrupt/oversized image and no-OCR image; fit/zoom/pan/frame switch, correct original and honest extracted-text/model-use state. |
| Shared lifecycle/search | Two chats/projects with a shared file, saved and temporary attachments, existing draft, note revision | Switch during load, deletion/rights change, stale query, restart and active-Test denial; no cross-chat bytes, duplicate original, temporary tab restore or denied snippet/cache. |

Keep synthetic fixtures outside Git under the designated Design C scratch roots,
with explicit hash/size manifests. An upload receipt proves verified selection;
an extraction receipt proves that parser's output; only the connected hidden
reader/draft/source journey proves that product flow. DC08 also requires all
eight categories in the matching packaged app. DC07/DC09/DC10/DC11 remain open
until their actual producers and consumers are connected and those receipts
exist. This report completes only the assigned independent pass-1 review.

## Knowledge003 seam for the integration owner

Implementation follow-up on October 10, against the frozen `design-c/1`
10-column attachment and 7-column original inventory. The parent owns the DDL,
contract inventory and media recovery changes. The lead's later request selects
a metadata sidecar instead of additions to those core tables. This supersedes
the earlier 20+11-column proposal at `f6d23bdd`. Do not widen the legacy Case schema.

| Table | Additional columns |
| --- | --- |
| New `knowledge_attachment_metadata` | `attachment_id TEXT PRIMARY KEY REFERENCES knowledge_attachments(id) ON DELETE CASCADE`; `filename TEXT NOT NULL`, `source_id TEXT NOT NULL`, `metadata_json TEXT NOT NULL`, `rights_json TEXT NOT NULL`, `preview_state TEXT NOT NULL DEFAULT 'not_requested'`, `preview_revision INTEGER NOT NULL DEFAULT 0`, `preview_json TEXT DEFAULT NULL`, `extraction_revision INTEGER NOT NULL DEFAULT 0`, `extraction_json TEXT DEFAULT NULL`, `processing_json TEXT DEFAULT NULL` |
| Existing `knowledge_attachments` and `knowledge_attachment_originals` | Retain the frozen 10+7 inventories without added columns. |

The new sidecar has eleven columns. Existing `original_path` must represent
unavailable bytes for records-only restore (prefer NULL if the published contract
permits it). JSON columns contain valid objects when present; generations are
nonnegative. Original roles are `original|preview`, with exactly one original per
attachment. Original ID/hash/bytes are immutable; replacing bytes creates a new
attachment ID. Preview provenance is in `processing_json`: `schema_version`,
`source_original_id`, `source_sha256`, `attachment_revision`, `preview_revision`,
and `assets` entries `{original_id, media_type}`. The repository checks that source
and asset rows belong to this attachment and that the source has original role.
No original metadata sidecar is required: originals use the attachment filename
and media type; derived reader assets are PNG.

Ordinary chat uploads own their originals under
`paths.library / "attachments" / attachment_id`. Library/project documents and
notes reference existing `knowledge_revisions` directly and do not create another
attachment authority. Legacy Case originals retain their Case IDs, storage and
retrieval authority; no Case bytes are copied into Knowledge records. The table
owner supplies authority, so no competing `authority` enum or duplicated
`project_id` is needed. Project scope derives from canonical memberships.

Reuse `knowledge.models.Rights` with deny-by-default operations and
`SourceMetadata`; `source_id` agrees with `metadata_json.source_id`. Display,
model input, derivation, indexing and embedding remain independent permissions.
Preview readiness never grants model use. `preview_json` holds an inert
`reader/1` payload with opaque asset IDs, not raw HTML, paths or resource URLs.
`extraction_json` holds the existing Docling extraction representation.
`processing_json` holds payload/parser versions, input original ID/hash and
separate preview/extraction diagnostics. Runtime guards compare input identity,
attachment/preview/extraction revisions and shared policy/context before publishing.

Recovery admits PDF, TXT, MD, CSV, HTML, XML, PNG/JPEG/TIFF and DOCX/XLSX, retaining
the existing PPTX recovery path. MIME is validated text rather than a restrictive
reader-capability enum; retained bytes do not prove a reader works. Derived image
assets are PNG. Normalised original media types are those in
`knowledge.reader.MEDIA_SUFFIX` (including both `application/xml` and `text/xml`);
no arbitrary HTML resource authority is introduced.

The connected reader seam is `knowledge.reader_api.create_router(services)`,
mounted under `/api/v1`, registering `services.registry["readers"]`. It exposes
`/readers/resolve`, `/asset`, `/original` and `/passage`. The renderer public entry
is default `modules/reader/index.tsx`, consuming shared `ReaderProps` and
`ContentReference {target, locator}`. Shared assessment policy/context helpers are
imported directly; no extra policy binding or reader-owned policy store is needed.
Knowledge003 and ordinary saved/volatile attachment persistence remain pending;
the reader reports `reader_schema_unavailable` until the published columns exist.

### Frozen proposal constraints and authority

Required sidecar text columns have no default. All three nullable JSON
columns default to NULL. Required
metadata/rights JSON and present optional JSON must satisfy
`json_valid(value) AND json_type(value)='object'`. Preview and extraction
generations are nonnegative integers. Existing `role` is constrained to
`original|preview`. A partial unique index on attachment ID for original roles
allows only one original. Processing metadata pins previews to an original of
the same attachment and a nonnegative generation. Preview states used by this
slice are `not_requested|ready|failed|unsupported`. Missing/invalid sidecar rights
or a source-ID mismatch grants no access. No other helper table or independent
policy authority is required. Readers/access join the sidecar; frozen core
original rows are unchanged.

Knowledge owns new uploads' original, rights, preview and extraction records.
The rights are per-operation `Rights` and never inferred from preview readiness.
The original remains available independently of extraction/index state; NULL
paths report records-only unavailability. Case keeps its legacy byte authority.
Library/project sources and notes retain their existing Knowledge revision IDs.
Knowledge's deletion byte scope is only `paths.library / "attachments" / attachment_id`
after canonical ownership/tombstone checks, covering that original and its
derived previews. It excludes Case parts, revision folders and arbitrary paths.

### Caller-transaction attachment authorization slice

`knowledge.api.create_router(services)` registers
`services.registry["knowledge_attachments"] = KnowledgeAttachmentAccess(services)`.
The exact public seam is
`authorize_in(conn, attachment_id, *, context: Identity | None = None)`,
returning only `{"allowed": True}` or `{"allowed": False, "reason": ...}` with
`restricted|unavailable|not_found|access_denied`. It uses shared policy and the
caller's connection, writes nothing and opens no nested transaction/connection.
It inspects saved Case ownership/part availability, current volatile ownership,
conversation/attachment tombstones and new Knowledge display rights/path
availability. It never returns metadata or reads stored original payloads.

The temporary Case adapter takes its existing lock without waiting. Contention
returns `unavailable` to avoid inversion against Case Save's lock-then-SQLite
order. It snapshots only the named session's attachment metadata and byte length,
without copying original bytes or loading a saved Case into volatile state.
Request the Case owner to publish an equivalent metadata-only accessor; ordinary
volatile Learn uploads remain a producer prerequisite. Saved Knowledge upload
authorization/persistence awaits the parent's actual Knowledge003 migration.

Reader resolution/download now consult the same registered authorization seam.
The connected regression test first reproduced a saved attachment being readable
after current-session removal, before Save deleted canonical parts (HTTP 200
where HTTP 404 was required). Authorization now revokes that pending removal.
The failed receipt is `attachment-removal-red-results.xml` under this lane's
synthetic root. The first authorization run also rejected a TXT saved Case
fixture against the actual legacy PDF/PNG/JPEG constraint; the fixture now uses
a real PNG, with no Case schema change.

Fifteen actual SQLite/Case/shared-policy and reader-router checks passed in
`attachment-access-run-2-results.xml`. SQLite's authorizer rejects original
payload/private Case text reads, writes and transaction control during access;
a patched connection factory rejects nested connections. Real lock contention,
records-only parts removal, tombstones, stale saved revision and pending removal
are covered. Synthetic state/evidence is exclusively under
`C:/Renulus/scratch/design-c/dc-review-readers/`. This does not close DC08/DC10 or
establish ordinary uploads, packaged reader behavior or Electron isolation.

After merging the lead's `c19d1493` baseline, readers/access now join the proposed
`knowledge_attachment_metadata` sidecar and leave the published 10+7 core
inventories untouched. Twenty reader/access/shared Workspace checks passed in
`sidecar-workspace-run-1-results.xml`. The additional actual Workspace attachment
journey passed in `workspace-attachment-connected-results.xml`: a volatile Case
original is authorized through the registered owner without creating a saved
Case, then removal revokes it. The sidecar itself is not fabricated in tests;
ordinary saved attachment persistence awaits the lead's published migration.
The retrieval ID boundary now matches the shared 256-character Identifier;
twenty scope/access checks passed in `scope-access-current-results.xml`.

### Connected document grids

The next reader slice preserves bounded native tables from Markdown, inert HTML
and DOCX as plain cell DTOs and escaped React tables. Cells retain canonical
tab/newline text and a shared TextLocator for whole-table passage requests. DOM
table selections do not invent character offsets. CSV/XLSX retain their existing
table coordinates. Nested/spanning HTML tables and merged DOCX cells fail
explicitly rather than publish fabricated coordinates.

Actual pinned parsers plus HTML resolve/passage routing passed fifteen checks in
`reader-grids-connected-results.xml`; four React checks passed in
`reader-grid-vitest-results.json`, and the full desktop TypeScript check passed.
The initial five expected failures are retained in `reader-grids-red-results.xml`.
All receipts and the external dependency-resolution harness are under this lane’s
synthetic root. No package/lock change was made. Hidden packaged display and
passage-to-conversation evidence remain integration work; DC08/DC10 remain open.

### Published Knowledge003 semantic correction

Merged the parent’s `8de5f0f6` baseline with all lane grid changes preserved.
Missing ordinary attachment IDs now return metadata-free `not_found`/HTTP 404
before sidecar lookup. Existing attachment records without usable sidecar or
original authority remain `unavailable`; absent core tables remain explicitly
unavailable. Two actual migrated-table removal checks run inside isolated SQLite
transactions and roll back, without a fabricated schema. Thirty-three access,
format/grid and connected router checks passed in
`schema003-semantic-results.xml` against the published migration.

### Ordinary attachment producer and live deletion seam

KnowledgeAttachments registers one owner under knowledge_attachments and
chat_attachments. The new attachment_api.create_router(services) exposes bounded
raw upload, conversation attachment inventory and revisioned removal. The lead
owns router assembly; tests mount only this new API explicitly. Reader tests use
the published server assembly without a duplicate reader router.

Upload options are conversation, expected_conversation_revision,
expected_policy_revision, expected_context_epoch, idempotency_key, filename,
title, rights and metadata, in x-renulus-attachment-options JSON alongside raw
bytes. The canonical conversation owner decides retention. Saved originals use
library/attachments/{id}/original.{extension}. Generated IDs satisfy
[A-Za-z0-9_-]{1,128}; extensions/MIME come from the existing Knowledge allowlist.
Filename never grants path authority. Aliases normalise to jpg, tiff and html.
No dependency or schema change was made.

Saved insertion uses the frozen core/original/sidecar inventories, explicit
Rights and SourceMetadata, and the actual source hash. Saved upload requires
display/cache rights. No extraction, indexing or provider operation runs
automatically. Temporary Learning and Case uploads keep bytes and receipts in
memory, with no row, file or durable command. Limits are 20 attachments per chat,
64 MiB per saved original, 10 MiB per temporary original, 32 MiB temporary bytes
per chat and 128 MiB total volatile bytes. Temporary reads require the actual
matching owner context. Legacy Case bytes remain Case authority.

The synchronous delete_chat_in(conn, kind, chat_id) hook validates at most 200
IDs, emits attachment and attachment_original tombstones, and deletes core rows
in the caller transaction. Cascade clears originals and metadata/processing. Its
inert plan is a list of {attachment_id, relative_directory}, with each directory
exactly library/attachments/{id}. It opens no connection, controls no transaction
and performs no filesystem, thread or provider work. Call before original owner
DELETE. The parent owns journal enqueue/commit and postcommit byte cleanup.
cleanup_deleted(ids) is a scoped retry helper. discard_volatile(kind, chat_id)
releases temporary bytes and upload receipts after success under owner locks.

Promotion is a consumer prerequisite: take promotion_guard() before owner locks
and SQLite; prepare_promotion_in(conn, kind, chat_id) stages records before draft
reference validation and returns a lease. Call lease.commit() after caller commit
or lease.rollback() after rollback. Cache rights are required; Case originals are
excluded. The stage test uses the actual Learn caller-connection helper, but does
not establish the full Chat promotion route. Zeno owns that wiring.

Thirty-four producer/access/router checks passed in
attachment-producer-run2-results.xml, including all required formats/assets,
fresh Knowledge003 persistence/reopen, volatile isolation, retry, shared policy/
context changes, written-original rollback, removal and promotion staging.
Four final delete/forget checks passed in attachment-delete-seam-final-results.xml;
filesystem operations and new connections are forbidden around delete_chat_in.
Four React checks and the full desktop TypeScript check passed after merge.
Three final passage/removal checks passed in
attachment-passage-delete-final-results.xml. The saved original supplies a
validated locator to the actual Conversation draft API, preserves prior draft
text and persists the reference without creating a Learn message or provider run.
The first producer run had nine passes and one faulty failure-injection fixture
signature; the corrected fixture proves actual file/canonical rollback.

Pending: parent mounts attachment_api; Zeno wires delete/forget and promotion.
After merging shared baseline 48729826 at d3938827, individual removal now
enqueues storage.attachment_cleanup in the revocation transaction, then drains
it after commit. Five actual journal/removal checks passed in
attachment-journal-connected-results.xml, including enqueue failure rolling
back bytes/rows/tombstones/revision and a locked file retaining its journal until
actual app startup finishes cleanup. TypeScript passed after this shared merge.
Two actual producer-to-typed-archive round trips passed in
attachment-typed-recovery-connected-results.xml: ZIP1 and ZIP2 each preserve
original IDs, ownership, exact bytes/hash, filename/rights sidecar and readable
ContentReference after restore to another synthetic profile. No provider or
derived memory job is created.
Interrupted saved upload can still leave an unreferenced owned folder; upload
crash cleanup remains integration work. No durable preview/extraction cache or
derived binary preview is claimed. Proposed cache publication uses frozen sidecar
generations and inert reader/1 payload pinned to original ID/hash, attachment
revision, rights and shared policy/context; derived rows use preview.{extension}.
Actual OCR/helpers, safe active links, PDF text alignment, hidden packaged flows
and DC08/DC10 closure remain open.

### Exact lane changed paths in this handoff

- apps/desktop/src/modules/reader/Reader.test.tsx
- apps/desktop/src/modules/reader/Reader.tsx
- apps/desktop/src/modules/reader/reader.css
- apps/desktop/src/modules/reader/types.ts
- runtime/renulus/knowledge/api.py
- runtime/renulus/knowledge/attachment_access.py
- runtime/renulus/knowledge/attachment_api.py
- runtime/renulus/knowledge/attachment_files.py
- runtime/renulus/knowledge/attachment_models.py
- runtime/renulus/knowledge/attachments.py
- runtime/renulus/knowledge/reader.py
- runtime/renulus/knowledge/reader_binary.py
- runtime/renulus/knowledge/reader_models.py
- runtime/renulus/knowledge/reader_text.py
- tests/integration/test_design_c_readers.py
- tests/knowledge/test_attachment_access.py
- tests/knowledge/test_attachment_producer.py
- tests/knowledge/test_reader_formats.py
- tests/knowledge/test_reader_grids.py
- docs/implementation/design-c-review-readers.md

### Chat Attach inventory pins

GET /api/v1/attachments/{learning|case}/{chat_id} now returns policy_revision
and context_epoch beside conversation, conversation_revision and items, all
from the same canonical transaction. Chat may use this existing owner read
to construct an explicit upload; Home hands off the File in memory and creates
no separate attachment/permission authority. /assessment/policy remains the
shared assistance read and does not expose context_epoch at this baseline.

The frontend upload is POST /api/v1/attachments with raw file bytes and
x-renulus-attachment-options JSON: conversation (learn_thread/case identity),
expected_conversation_revision, expected_policy_revision, expected_context_epoch,
idempotency_key, filename, title, rights and metadata. Returned reference is
{target:{type:attachment,id},locator:null}, with original id/bytes/sha256,
retention and updated conversation_revision. Required reader accept extensions
are pdf/docx/csv/xlsx/txt/md/html/htm/xml/png/jpg/jpeg/tif/tiff. Producer PPTX
admission is inherited but does not establish an in-app PPTX reader.

Two connected API checks passed in attach-inventory-run1-results.xml: actual
inventory pins permit ordinary upload and canonical reference publication;
an actual context-epoch bump rejects a second stale upload without adding a
row. Saved original/reader/passage/reopen proof also remains passing. Zeno owns
the Chat attachment UI/source rights and Home's owner owns volatile File intent
handoff. No frontend adapter or source DDL is added by this change.

Exact follow-up paths are runtime/renulus/knowledge/attachments.py,
tests/knowledge/test_attachment_producer.py and this report.

These are lane edits only. Shared merges preserve the parent's schema, recovery,
contracts, shell/server and other owners' changes. No source schema/migration,
root dependency manifest/lock or shared UI file was edited by this lane.

### DC17 trusted saved extraction adapter

The backend-only seam is services.registry["readers"].import_original(conn,
revision_id, *, expected_fingerprint=None, expected_policy_revision=None,
expected_context_epoch=None). KnowledgeRepository.saved_extraction_in exposes
the same authority; Reader delegates to it. recheck_import_original(conn, pin)
requires complete fingerprint/policy/context pins and resolves the real source
again. The caller must own a transaction, including the final import/version
publication transaction. No independent policy or extraction authority exists.

The saved-extraction/1 result contains text, fingerprint, original_sha256,
reference, terms, rights, segments, diagnostics, document_id, revision_id,
source_id, title, content_sha256, extraction_sha256, effective metadata,
policy_revision and context_epoch. Terms is an object containing licence,
permission_reference and attribution. Segments map half-open start/end offsets
in text to canonical passage_id, extraction locators, headings and a shared
ContentReference. Text preserves canonical passage order separated by two
newlines, including chunked table headers. Docling IDs/geometry remain raw
provenance; they are not fabricated inert-reader text offsets.

The private original object is kind=library-original, document_id, revision_id,
relative_path, media_type, bytes and sha256. This object stays backend-only; it
does not grant renderer path or archive authority. The adapter bounds and
rehashes the private canonical original, and rejects links/junction redirects.
An original is never copied for import. Existence, current active revision,
saved Library scope, reserved status, all parent tombstone aliases, effective
source restrictions and display/cache/model_input/derivation rights are checked
against the caller connection. Index/embedding rights do not govern test import.
Whole-source imports containing excluded pages are rejected, preventing an
unlabelled partial question set. Maximum text is 4 MiB/12,000 passages, original
64 MiB and serialized extraction 16 MiB.

Failures use saved_extraction_not_found, pending, failed, unsupported,
unavailable, denied, stale, context_changed, limit, snapshot_required or
invalid_pin (each with the saved_extraction_ prefix), original_missing and
the shared assistance_restricted/assistance_changed codes. Ready preview,
ready status without canonical successful Docling extraction, and empty OCR
passages cannot satisfy this contract. Current helper availability controls
regeneration; reading persisted successful extraction needs no helper load.

Fifty checks passed in saved-extraction-run2-results.xml, including 27 new
tests with actual pinned Docling/HybridChunker, FastEmbed/LanceDB and ordinary
saved text/CSV ingestion, actual migrated tables, reopen, caller-visible
uncommitted source restrictions, rights, all tombstone aliases, byte tampering,
context/policy changes and a guard forbidding new connections/conversion/index/
helper calls during resolution. Public embedding artifacts were hash-validated
against the committed manifest and copied explicitly into the synthetic lane
profile. No providers or external network were used. An earlier 24-check run
is retained in saved-extraction-run1-results.xml. This proves the saved text/CSV
adapter and reader regressions; saved PDF/image OCR import acceptance remains
separate. DC17 owns Assessment005, import persistence, provider normalization,
edit/retry/cancel and final saved_tests publication/consumer rechecks.

Exact paths added/changed in this follow-up:

- runtime/renulus/knowledge/saved_extraction.py
- runtime/renulus/knowledge/repository.py
- runtime/renulus/knowledge/reader.py
- tests/knowledge/test_saved_extraction.py
- docs/implementation/design-c-review-readers.md

### Operation-specific DC17 reads and latest revision follow-up

import_original and KnowledgeRepository.saved_extraction_in now accept
operation=import|read (default import). Import requires active_revision and
latest_revision to match, so a real queued replacement makes the older active
source stale for new refinement/publication. Read requires current display/cache
and permits historical/currentness inspection after processing rights change;
the metadata still records source restrictions. recheck_import_original(conn,
pin, operation=read) compares immutable original/content/extraction hashes rather
than the full rights/currentness fingerprint. Import rechecks retain full
fingerprint/policy/context pins. Both operations enforce shared active-Test
restrictions, saved Library scope, reserved status, tombstones and private
original integrity.

Reader.require_original_display(conn, pin) delegates to
KnowledgeRepository.require_original_display_in and returns allowed, current
rights/metadata, backend-only original descriptor and current policy/context
revisions. It consumes only a canonical server-side pin (revision_id,
original_sha256 and optional document_id), never renderer attestation. This
authorizes DC17 to show its own immutable original_text/segments after loss of
derived Knowledge extraction. It returns no text or locators and establishes
no normalization/Save authority. Display/cache revocation, any document/revision
tombstone and missing/changed original bytes still deny inspection. Pasted
imports remain DC17's independent original authority.

Thirty-four actual offline saved-extraction tests passed in
saved-extraction-operations-run1-results.xml, adding rights revocation, retained
inspection after derived cache loss, source-status warning inspection, and an
actual ordinary queued replacement to the earlier guards. The prior merged
2122f875 baseline passed 80 combined attachment/access/format/grid/Reader/saved
extraction checks in reader-parent-2122-results.xml. Full desktop TypeScript and
four Reader React checks passed after that normal shared merge (45f8235c).
No feature closure or packaged/OCR import acceptance is claimed.

### Shared producer checkpoint for independent reader/data pass 2

Normal merge 873bad79 completed at d61b9392. Three conflicts were confined to
this report, attachments.py and test_attachment_producer.py: incoming duplicate
producer history omitted the later Attach policy/context pins and follow-up
documentation. Those lane additions were retained; all automatically merged
parent owner/router/schema/contract changes were preserved. No reset/checkout
or unowned conflict edit was used.

The producer fixture now relies on the actual parent-mounted attachment router,
removing its former duplicate router inclusion. Forty-three connected checks
passed in reader-parent-873b-results.xml: all 34 trusted extraction/operation
checks, live inventory/upload pins, saved upload/original/passage/reopen, actual
uploaded PDF/DOCX/CSV/XLSX/Markdown/HTML/XML/PNG/JPEG/TIFF originals and native
assets, and actual learning/case plus legacy owner deletion/volatile forget.
The caller's journal/tombstone/owner deletion now connects to this M2 service;
this supersedes the earlier pending router/delete prerequisite. Full desktop
TypeScript passed against the merged shared source. All state/evidence remains
under C:/Renulus/scratch/design-c/dc-review-readers.

Consumer prerequisites: Pauli uses import_original/recheck_import_original with
operation=import for Normalize and final version publication; original inspection
uses require_original_display on its canonical source pin and reads its own
immutable private body. Home/Chat uses inventory policy/context/conversation pins
for explicit upload and owns source-rights UI/volatile File handoff. Private
source descriptors stay backend-only. No Knowledge DDL or dependency addition
is needed for either seam.

Still open: complete attachment promotion through the original Conversation
owner, upload interruption/orphan-folder reconciliation, durable extraction/
preview cache, actual saved PDF/image OCR import proof, safe active link handling
and PDF text alignment, notes/Library destination completion, and packaged hidden
reader/Attach/selection journeys. DC08/DC10/DC17 feature closure is not asserted.
Exact changes in this checkpoint are tests/knowledge/test_attachment_producer.py
and this report. Independent pass 2 starts from a committed clean lane.

### Study-help Reader request context checkpoint

Reader consumes the parent-owned optional ReaderProps.studyHelpContext receipt
and sends X-Renulus-Study-Context=JSON.stringify(context) on /readers/resolve,
/readers/asset, /readers/original and /readers/passage requests. Both PDF/image
page assets and inline document image assets use the same explicit header.
Ordinary Reader requests omit it. No context, renderer key or raw snapshot is
added to request bodies, ContentReference locators or persisted positions.

The serialized receipt is part of the ephemeral Reader session identity. A
changed attempt/item/version/draft/policy/kind remounts the session, aborts old
resolve/asset/original/passage requests, clears selection and prepared download
state, and revokes owned Blob URLs. Late responses cannot display an old source,
create an old original/preview URL or call onPassage for the previous receipt.
No server authority is inferred from the renderer receipt.

Eleven Reader React checks passed with the existing shared same-origin transport
and controlled fetch responses in reader-grid-vitest-results.json. Seven new
checks cover all four request kinds with and without the exact header, inline
images, unchanged canonical references/bodies, and late resolve/asset/original/
passage completion after an item/draft or policy change. Prepared downloads and
actual DOM selections are cleared on context replacement. Binary fixtures are
transport fixtures; this run does not establish image decoding or native format
acceptance. Full desktop TypeScript passed with the pinned existing dependencies.
Runtime/cache/evidence paths remain under the synthetic lane scratch directory.

Parent prerequisites: publish the optional shared scalar ReaderProps field and
pass it from Study/Workspace; validate owner exposure before and after Reader
reads and before each transaction commit through the inherited server guard.
The shared type is not yet in local baseline 3259ccf2, so the frontend recognizes
the optional property without copying or editing the shared declaration. No
backend, shared type, shell, DDL or dependency file was changed by this checkpoint.
Integrated Study-help authorization, restart/persistence and hidden packaged
journeys still require parent/consumer evidence. No feature ticket is closed.

Exact changed paths:

- apps/desktop/src/modules/reader/Reader.tsx
- apps/desktop/src/modules/reader/Reader.test.tsx
- docs/implementation/design-c-review-readers.md

### Required-format passage, rights and reopen checkpoint

Normal merge efada051 completed at b8d81606 without conflicts or discarded lane
content. The existing actual upload/reader format test now also takes canonical
passages from PDF, DOCX, CSV, XLSX, Markdown, HTML and XML, explicitly appends
them to the saved Conversation draft with their typed locators, and verifies
the complete draft/references after reopening the actual application services.
Seven references are retained; no learning message or provider request is sent.

All ten original variants (the seven formats plus PNG/JPEG/TIFF) reopen with
exact retained bytes and identical inert payloads. Current model_input revocation
denies passage use for each text/table format while retained reading/originals
remain available. Image previews do not attest to OCR: all three image variants
explicitly return reader_selection_unavailable for attempted image passage use.
The upload remains not_requested extraction/index authority; this connected
reader proof does not establish saved Docling extraction for these attachments.

The expanded format check passed in formats-selection-run1-results.xml. All 34
actual saved-extraction checks also passed against efada051 in
saved-extraction-parent-efada-run1-results.xml, including real pinned Docling/
HybridChunker and FastEmbed/LanceDB text/CSV ingestion, caller snapshot pins,
rights/tombstones/original integrity and reopen. The trusted DC17 helper commits
remain 20e95641 and fbe7b4a0; no new helper implementation or DDL is required.
No hidden renderer, saved PDF/image OCR import or feature closure is claimed.

Exact lane changes are tests/knowledge/test_attachment_producer.py and this report.

### Shared Study-help and real Library import consumer checkpoint

Normal merge 7ddf7aeb completed at 4477a984. Reader now imports the parent-owned
studyHelpHeaders helper and consumes the published optional StudyHelpContext
directly; the temporary absent-type compatibility branch is removed. All four
Reader request kinds, inline images and ephemeral cancellation/session behavior
remain covered by eleven passing React transport checks. Full desktop
TypeScript passes with the existing pinned dependencies. Shared source/types/
server/DDL were changed only by the normal parent merge.

Twenty-five real backend checks passed in readers-study-help-run1-results.xml.
Eight new cases create a real saved personal version, start Study and record
source-help exposure, then exercise resolve/asset/original/passage through the
actual router. Changed canonical drafts reject the old receipt both before a
read (the reader is not called) and after the actual parser/original read. The
controlled race performs a real independent owner transaction; the inherited
server guard returns a safe revision_conflict response without source/key data.
The run also includes the seven parent guard tests and required-format persisted
draft/original checks. No replacement authorization guard was introduced.

Thirty-six actual offline saved-extraction checks passed in
saved-extraction-parent-7ddf-run1-results.xml, adding text and CSV Library imports
through /assessment/imports to the existing 34 authority checks. They use the
production readers helper, real Docling/HybridChunker and FastEmbed/LanceDB
extraction, immutable Assessment originals and source pins, idempotent create,
reopen and private original hashes. Two focused positive cases passed again in
library-positive-router-run2-results.xml after checking structured terms inside
source_pin rather than constraining the consumer's visible terms formatting.
No provider normalization/Test acceptance is claimed by these owner checks;
Pauli owns those consumers and their separately published evidence.

Exact offline opt-in: RENULUS_SAVED_EXTRACTION_ASSETS=C:/Renulus/dev/helper-assets,
HF_HUB_OFFLINE=1 and TRANSFORMERS_OFFLINE=1. The fixture hashes and copies only
the embedding files listed in packaging/runtime/helper-assets.json into the
synthetic profile; missing opt-in produces explicit skips rather than fake
extraction. Use the lane's explicit runtime PYTHONPATH, PYTHONDONTWRITEBYTECODE=1,
and a fresh pytest --basetemp beneath its synthetic scratch root.

Reader header adoption is ready on shared baseline 7ddf7aeb. Trusted helper
content-only commits are 20e95641ad131df51f323ec70beed308818e8fc6 and
fbe7b4a098256d4c46db87f14dd04a40876117ff; both contain only this report,
knowledge/reader.py, repository.py, saved_extraction.py and its owned test.
Structured terms remain licence/permission_reference/attribution in the trusted
pin; visible retained lines belong in Pauli's consumer.

Exact changed paths for this checkpoint:

- apps/desktop/src/modules/reader/Reader.tsx
- tests/integration/test_design_c_readers.py
- tests/knowledge/test_saved_extraction.py
- docs/implementation/design-c-review-readers.md

No feature closure, packaged hidden journey or saved PDF/image OCR import
acceptance is asserted. No Notes feature source was added in this checkpoint.

### Bounded Notes owner proposal and verified reuse prerequisites

The lead's /library/notes seam is accepted for the new Notes adapter. No dedicated
Notes service/router was found in the scoped Knowledge/Study owners. Reuse
KnowledgeRepository.import_text, get_document, original and delete_document;
import_text already supports durable knowledge_jobs idempotency and immutable
document revisions. Identify saved personal notes by SourceMetadata.asset_role
containing study-note, not by a competing table or a renderer-supplied path.
Workspace already maps that role to note_revision references.

The future note_api.create_router(services) should reuse services.get(knowledge),
register services.registry[notes], and return a /library/notes router for the
parent mount. The requested new-file reservation is note_models.py,
note_service.py, note_api.py and tests/knowledge/test_design_c_notes.py only.
No Notes feature file has been created yet.

Frozen external shape:

- GET /library/notes -> items of document_id, revision_id, ordinal, title,
  updated_at and canonical ContentReference(target=note_revision).
- GET /library/notes/{document_id}?revision_id=optional -> those fields plus
  the retained UTF-8 original text; historical revisions remain readable.
- POST /library/notes {title,text,idempotency_key,project_id?} -> canonical detail.
- PUT /library/notes/{document_id}
  {title,text,expected_revision_id,idempotency_key} -> canonical detail.
- DELETE /library/notes/{document_id}?expected_revision_id with Idempotency-Key
  -> document_id, revision_id and deleted=true; later content reads return 404.
  This acknowledgement narrows the lead's generic successful-mutation detail
  shape so deletion cannot return an apparently editable live note.

Reads/writes must use shared policy and the inherited scalar Study-help guard,
never a new policy authority. Metadata/rights are derived from the canonical
user-owned note; response data contains no filesystem location. Save persistence
and original reading must work while extraction is queued, failed or unavailable.
Extraction/index readiness remains separate. Existing project associations must
retain their scope on edit, and old citations must keep their original revision.

Material gap 1, reproduced with the actual current importer: import_text of
SYNTHETIC first saved note with SourceMetadata(asset_role=[study-note]),
process=False and a stable command key, followed by import_text of
SYNTHETIC second saved note on the same document_id. The first revision
receives knowledge_cleanup.remove_original=1. Calling actual cleanup deletes
its bytes; original(first_revision) returns original_missing. The reproducible
receipt is C:/Renulus/scratch/design-c/dc-review-readers/notes-reuse-probe-run1/receipt.json.
No providers/helpers/network or private data were used.

The cause is repository._import cancelling queued replacements through
_cancel_in; _cancel_in schedules destructive original cleanup. _run_job also
schedules destructive cleanup on extraction failure. A thin wrapper around the
current importer therefore cannot meet retained note-original/old-citation
requirements. KnowledgeRepository.import_text/_import also lacks a caller
expected_revision_id comparison; delete_document likewise has no revision CAS.

Exact additional existing-source reservation/prerequisite: Knowledge
repository.py only, covering import_text/_import atomic expected_revision_id
checking (included in command hashing), delete_document optimistic deletion,
and _cancel_in/_run_job preserving saved study-note originals for non-deletion
cleanup. Reuse the existing job ledger and cleanup records; no new table,
column, lockfile or alternate note store is required. Explicit deletion must
continue to remove the originals. This reservation has been proposed, not used.

Material gap 2: ProjectRepository.document owns shared links but accepts only
ready active Library revisions. A newly saved queued note cannot use it for the
lead's immediate project_id association. The Project owner must publish a narrow
saved-note association operation, e.g. note_saved_in(conn,document_id,revision_id,
project_id=None), which validates current project scope, preserves existing
associations on edit and owns all link/revision/tombstone updates. Retrieval
must keep its existing active-ready eligibility. Notes must not copy project
membership into metadata or write a competing project-link authority.

Dependent Notes coding awaits these exact prerequisites/reservations. No schema
change or feature completion is inferred from the API proposal.

### Notes owner checkpoint and prerequisite receipt — October 10

The preceding proposal was subsequently authorised and implemented. Apply
e0e51784762a60ddba828c46e1c47b43582137b4 before
98f5f3e4596672d86876697073750f1da8c1fda6. The first commit creates the Notes
test file and fixes actual original loss: queued note replacement, cancellation
and failed extraction must preserve saved study-note originals and historical
citations. Ordinary import cancellation keeps its prior discard behaviour.
Explicit document deletion still removes all note revisions' bytes.

The second commit adds note_models.py, note_service.py and note_api.py, plus
repository CAS/idempotency and the owner tests. Its router registers notes and
returns /library/notes for the parent mount. Summary is exactly document_id,
revision_id, ordinal, title, updated_at and reference; detail adds text. The
reference targets note_revision. Per-revision titles reuse SourceMetadata.notes;
no new table is introduced. Saves call projects.note_saved_in once inside the
caller transaction after note rows are inserted, with no second epoch bump.
The prerequisite is Project owner af1a1e28d98e3800e870c20890060a2a25e28330,
integrated by the parent as b0bcb40d.

Actual lane receipt:
C:/Renulus/scratch/design-c/dc-review-readers/notes-owner-run1.xml — 35 passed,
zero failures/errors/skips in 158.127 seconds. The six Notes cases cover actual
HTTP create/edit/replay/historical text and title/reopen, stale edit and delete,
idempotency conflicts, delete replay and retained originals through replacement,
cancel and actual extraction failure. The other checks are 16 Knowledge
regressions and 13 actual Project checks, including caller rollback and unchanged
retrieval eligibility. The earlier retention red/green receipts remain in the
synthetic lane. Saves do not attest successful extraction or index readiness.

The parent reports integrating the two commits as 820d1906/7116e427 and mounting
Notes in a4439597. Its separate six backend checks, six frontend checks and
hidden n1 journey are parent evidence: save v1, typed chat draft without send,
save v2 and Source 1 still reading v1, including narrow/200-percent pixels.
These are not new runs by this lane. Remaining dedicated Notes gates are
HTTP project-filter/rights/tombstone and stale Study-context cases, deletion
recovery, and matching packaged acceptance. No Notes ticket is marked closed.

### R7 safe Reader position checkpoint — October 10

Content-only source commit b3addad5f29e4b29f2d075534d156ce7644a1696 changes only:

- apps/desktop/src/modules/reader/Reader.tsx
- apps/desktop/src/modules/reader/Reader.test.tsx
- apps/desktop/src/modules/reader/index.tsx
- apps/desktop/src/modules/reader/types.ts
- tests/integration/test_design_c_readers.py

The actual Reader now consumes Workspace position/onPositionChange. Positions
are validated with the existing Workspace validLocator and bounded to the
production request limits: page/frame 1–300 and first row 1–100000. Restore uses
the saved position, then the reference locator. Successful PDF/image navigation
and table window/sheet changes emit canonical locators; cell and text selection
also emit locators. Callback echoes cannot restart a table window or replace a
selected range. Known text-item restoration scrolls inside the Reader without
persisting pixel offsets. Failed preview and aborted Workspace authority cannot
publish a replacement position. Positions contain no original path, filename,
hash or Study-help receipt. Shared scalar Study headers remain on all mediated
Reader requests. No shared types, storage, server or dependencies were edited.

Prerequisites are the existing Workspace position/callback and validLocator
seams plus integrated Reader grid/Study-header foundations in d1b5f8a2 and
c6b72502. The lane checkpoint was based on c6ae5025, the normal merge of
d1b5f8a2. The Notes frontend commit is not an R7 prerequisite.

Reproduced failures are retained in
C:/Renulus/scratch/design-c/dc-review-readers/reader-position-red1.json
(saved PDF page 3 requested as page 1) and reader-position-red2.json (CSV cell
selection overwritten by the window default; click after text mouseup replaced
the selected range with a whole block). The fixes have these completed checks:

- reader-position-final2.json: 34 passed, zero failures — 22 actual Reader
  component/transport checks and 12 existing Workspace checks. CSV and XLSX
  tests mount the actual Reader in the actual WorkspaceProvider/WorkspacePanel,
  restore row 101, preserve cell callback echoes, move to rows 201–250 and
  remount from saved preferences. XLSX restores the selected sheet and resets
  its row on explicit sheet change. PDF and image page/frame restore and emit;
  known text items restore locally. Invalid/path-bearing/out-of-request-bounds
  positions are ignored, failed preview retains position and Study receipt
  cancellation/header behaviour still passes. Transport responses in these
  component tests are synthetic; they are not parser or SQLite attestation.
- reader-position-api1.xml: 20 passed, zero failures/errors/skips in 148.378
  seconds, using the actual assembled FastAPI/SQLite and installed parsers.
  Three new cases persist Workspace preferences and recreate the app, then
  open real CSV/XLSX rows 101–200 or page 3 of a five-page PDF and retrieve its
  PNG asset. Exact original SHA is checked. Revoking current display rights
  denies the retained reference while keeping its safe tab/position. Existing
  original, inert HTML/XML, Case authority, stale policy/epoch and Study guard
  checks also pass. No providers/external sockets are used.
- Full desktop TypeScript --noEmit with reader-grid-tsconfig.json passed,
  as did git diff --check. All receipts/cache/state remain under
  C:/Renulus/scratch/design-c/dc-review-readers/.

The remaining R7 acceptance is the parent's assembled hidden close/reopen
journey and matching reader package. This lane does not attest native dialogs,
installed reader dependencies or physical scrolling/zoom from component tests.
R10 Workspace Files inventory remains with the parent. No feature is closed.
