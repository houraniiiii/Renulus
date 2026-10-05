# Image original preservation — issue #17

2026-10-05. Bounded engine/repository delivery on
`build/image-original-preservation`, based on
`909d296872624f7c4c50fd37d1d80e68f222bf00`, in
`E:/Renulus-native-delivery/desktop-20261005/image-original-preservation`.

## Behaviour and scope

A durable, valid PNG/JPEG/TIFF can complete Docling conversion successfully
without readable OCR text. Previously, HybridChunker's empty result raised
`empty_extraction`; failed-import cleanup then removed the app-owned original.
The successful image now activates as a `ready` revision with **zero passages**
and the actual `DoclingDocument.export_to_dict()` metadata. Its original remains
available through the existing original and document citation operations. A
document citation has an empty locator list; asking for an extracted page or
passage still requires a real corresponding locator or passage.

The private chunking seam defaults to strict extraction. Only the existing
durable image conversion path enables an empty result, after PIL validation,
resource checks and Docling `ConversionStatus.SUCCESS`. Conversion failure,
partial success, malformed images, PDFs, text, Office and temporary image bytes
retain their strict behaviour. An export failure still fails ingestion; no
replacement metadata, caption, text or OCR confidence is manufactured. The
existing heading-only fallback still emits actual extracted heading text and
stores the unmodified Docling export.

Empty imports do not stage vectors or build FTS. Empty LanceDB staging returns
without opening the index; rebuild skips FTS when there are no canonical
incoming passages, while retaining index validation and generation selection.
Retrieval requires a canonical passage before loading query embeddings, and
repeats that check after embedding and search through the existing eligibility
checks. Browsing and original access still use revision availability, not
retrieval eligibility.

Activation, cancellation, replacement, cleanup and deletion keep their existing
transactional guards. A successful empty-image replacement activates normally
and removes the previous revision's derived index rows, while retaining its
historical original/citation. Failed or cancelled replacements retain the
previous active revision. Delete removes canonical extraction and app-owned
originals; replaying an already completed job does not restore the document.

The write set is limited to:

- `runtime/renulus/knowledge/engines.py`
- `runtime/renulus/knowledge/repository.py`
- `tests/knowledge/test_image_original_preservation.py`
- `docs/implementation/image-original-preservation.md`

No schema, dependencies, helper artifacts, API/UI, packaging or worker code
changes belong to this delivery. The parent owns the Available/no-searchable-text
wording and actual adoption.

## Verification

All data is generated and synthetic. Tests use an isolated SQLite profile in
short temporary directories on E. Conversion and derived-index operations are
controlled doubles. Real Docling status/options, image validation,
`DoclingDocument`, HybridChunker and the already installed local tokenizer
exercise the extraction/chunking seams. Native OCR/PDF pipelines and embedding
models are not run. The tokenizer file is read directly, without copying or
changing the integration profile. No provider, credential, private/native
profile, acquisition dataset or dependency download is used.

From the isolated worktree, PowerShell setup:

```powershell
$env:PYTHONPATH = 'E:/Renulus-native-delivery/desktop-20261005/image-original-preservation/runtime'
$env:RENULUS_TEST_TOKENIZER = 'C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.local/runtime/integration/helpers/fastembed/bge-small-en-v1.5/tokenizer.json'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:TOKENIZERS_PARALLELISM = 'false'
$env:PYTHONDONTWRITEBYTECODE = '1'
```

Executed commands and results:

```powershell
& 'C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe' -m pytest tests/knowledge/test_image_original_preservation.py -q --basetemp E:/r17-iop-20261005-0555
# 43 passed in 92.75s

& 'C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe' -m pytest tests/knowledge/test_library_responsiveness.py -q --basetemp E:/r17-resp-20261005-0556
# 31 passed, 1 warning in 107.42s

git diff --check
# Passed: no whitespace errors.
```

The new tests cover real empty/picture/whitespace Docling documents, preserved
heading-only extraction, every accepted image suffix and uppercase admission,
exact original bytes, actual exported metadata, idempotency, browse/citation,
restart/recovery, completed-job cancellation, deletion, malformed/truncated
images, failed/partial/skipped conversions, failed metadata export, strict
temporary/PDF/text/Office inputs, mixed searchable and original-only documents,
historical replacement access, cancellation/delete/replacement at conversion
and publication, retrieval rechecking after replacement, and empty/mixed index
rebuilds. A direct LanceIndex seam check refuses any index opening or FTS
creation for empty staging.
The existing responsiveness suite reported one Starlette TestClient/httpx
deprecation warning; no dependency change was made.

## Remaining native proof and parent handoff

These checks establish application rules and real chunker behaviour. They do
not establish native OCR quality, real conversion of a no-text image, native
LanceDB search/purge, desktop rendering, packaging or installed-profile
adoption. The native app retained the heavy helper slot throughout this lane.

After the parent releases that slot, it will run one real valid synthetic
no-text image through the existing pinned Docling helper serially and record
successful conversion, zero canonical passages, genuine exported metadata,
preserved/viewable original, retrieval exclusion and deletion. The parent will
also deliver the Available/no-searchable-text UI state and integrate/package the
change. Issue #17 remains open for that combined acceptance.

## Parent actual CPU proof — October 5, 2026

After the owner authorised the temporary-context end and the old normal
app/backend were physically gone, one serial actual CPU proof ran against the
freeze55 runtime. It started at **06:36:48 UTC** and passed in **102.085 seconds**
in a fresh short E profile with the verified public helper assets. No app
lifespan or background worker, provider call, patient input or credential read
was involved. External socket connections were prohibited; no new download or
dependency was used.

A valid synthetic blank PNG completed actual pinned Docling/RapidOCR
conversion with no OCR text. It became ready with **zero canonical passages**,
genuine DoclingDocument export and the exact preserved 1,878-byte original.
The supported original route returned the same PNG bytes. Document citation
returned empty locators; a fabricated physical page was refused. Retrieval
returned zero passages without constructing an embedding model. Supported
delete removed its app-owned original and refused subsequent original access.
The worker stayed stopped.

Ignored receipt and log: `.local/actual-no-text-image-55.json` and
`.local/actual-no-text-image-55.log`. This resolves the real no-text engine/API
proof prerequisite, separately from installed renderer/original viewing and
actual selected-data readiness. The parent's Available/no-searchable-text UI
and manufacturing/native acceptance remain separately attributed.
