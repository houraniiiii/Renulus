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
contract inventory and media recovery changes. Keep all frozen names/meanings and
append the following exact columns; do not widen the legacy Case schema.

| Table | Additional columns |
| --- | --- |
| `knowledge_attachments` | `filename TEXT NOT NULL`, `source_id TEXT NOT NULL`, `metadata_json TEXT NOT NULL`, `rights_json TEXT NOT NULL`, `preview_state TEXT NOT NULL DEFAULT 'not_requested'`, `preview_revision INTEGER NOT NULL DEFAULT 0`, `preview_json TEXT`, `extraction_revision INTEGER NOT NULL DEFAULT 0`, `extraction_json TEXT`, `processing_json TEXT` |
| `knowledge_attachment_originals` | `filename TEXT NOT NULL`, `media_type TEXT NOT NULL`, `source_original_id TEXT`, `preview_revision INTEGER` |

The resulting exact inventories contain 20 and 11 columns respectively. Existing
`original_path` must permit NULL for records-only restore. JSON columns contain
valid objects when present; generations are nonnegative. Original roles are
`original|preview`, with exactly one original per attachment. Original ID/hash/bytes
are immutable; replacing bytes creates a new attachment ID. A preview pins the
same attachment's original through `source_original_id` and a preview generation;
those two fields are NULL on original rows. A source original cannot be a preview.

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
