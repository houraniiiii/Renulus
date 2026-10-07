# Hidden synthetic input control — October 7, 2026

The control lane adds bounded `renulus_upload` and `renulus_resize` tools to the
existing hidden app controller. This supplies the parent with a way to exercise
real synthetic PDF/image selection and responsive window sizes without shared
desktop input. **Native upload, extraction, rendering and resize acceptance remain
unperformed in this lane.** The implementation and its focused mock checks are
ready for parent integration.

Worktree: `C:/rn-finish-20261007/lanes/control`, branch
`codex/final-control-20261007`, base
`ea73f4dcdb90f4f67e0fb2d948939cc213f95ffd`. The sole remote remains
`origin`, `houraniiiii/Renulus`. The parent owns integration/PR13, Electron
source, native checks and worktree retirement. All generated state, fixtures,
test output and receipts are under `C:/rn-finish-20261007/evidence/control`.
Prior October 6 receipts and failed aggregates remain unchanged.

## Changes and boundaries

The original eleven tools are preserved; snapshot adds `fileInputs`. The two
new strict tools accept an observed locator plus declared fixture basename,
or bounded integer width/height. No dependencies, locks, desktop source,
Flow styles, model choices or product gates were changed.

`--fixture-root` is fixed at server/client creation. Its versioned manifest
explicitly declares 1–32 owned synthetic PDF/PNG/JPEG files by basename, size
and SHA-256. The optional root defaults to disabled uploads. Personal/profile,
credential, repository, runtime and helper paths are rejected. UNC/device paths,
traversal, alternate streams, links/junctions, hard links, directories, oversized
files, undeclared names, incorrect hashes and incorrect media signatures are
refused. Only explicitly requested declared leaves are read; no directory scan
or personal-state copy occurs. Declarations stay fixed across app restart.

Verified bytes go to Playwright `Locator.setInputFiles` as an in-memory payload.
The locator must come from the latest snapshot and still identify exactly one
unchanged, enabled Library/Case file input. Only the four current product labels
listed in the [controller guide](../../tools/renulus-control/README.md#synthetic-uploads-and-hidden-resizing)
qualify; backup/account/profile inputs do not. A file selection consumes the
observation. The existing indirect file chooser cancellation stays installed.
Uploads record basename, bytes, MIME and SHA-256, without copying payload bytes
to controller logs. Selection completion does not establish successful import,
extraction, explicit Save, provenance or rights acceptance.

Resize operates only on the BrowserWindow associated with the verified Flow
page. `setSize(width,height,false)` is bounded to 640–2560 × 540–1600 outer
device-independent pixels, matching the current app's 640×540 minimum. The tool
returns measured outer/content dimensions and rejects native clamping. Existing
ownership, sandbox and hidden-state checks run before/after, and an unsafe
resize triggers owned cleanup. No show/focus/position/OS input operation exists.

Static source review found the needed labelled file inputs already present in
`apps/desktop/src/modules/library/index.tsx` and
`apps/desktop/src/modules/cases/CaseAttachments.tsx`. The existing Input component
provides IDs; the pinned React DOM implementation generates supported IDs.
The installed Playwright types support buffer payloads and AbortSignal for
`setInputFiles`; Electron's types support non-animated `setSize` and measured
sizes. **No parent Electron prerequisite patch is required at this base.**

## Exact validation

Node v24.15.0 ran the three controller-package unit files serially; no native
process, backend, engine, model or provider was launched. The external
`test-dependencies.mjs` loader resolves only the SDK/Zod imports against the
parent's existing pinned development modules, read-only. No install or lock
change occurred. The exact passing command, from this worktree, was:

```powershell
$env:RENULUS_CONTROL_TEST_ROOT = 'C:/rn-finish-20261007/evidence/control/03'
node --import file:///C:/rn-finish-20261007/evidence/control/test-dependencies.mjs --test --test-reporter=tap --test-concurrency=1 tools/renulus-control/test/controller.test.mjs tools/renulus-control/test/fixtures.test.mjs tools/renulus-control/test/server.test.mjs
```

`unit-03.tap`: **45 passed, 0 failed, 0 skipped**, 2.118 seconds; SHA-256
`5f8cace3e241063c050047f7c1dad444381ac42533901a5bc61a56bf5fe9edbc`.
It includes the existing lifecycle/ownership/chooser/screenshot checks and new
schema, manifest/path/link/hash/type, observed-input, cancellation and resize
checks. A focused fixture policy read also accepted all three prepared real
synthetic assets without launching an app; `fixture-policy-check.json` SHA-256
`a65c1d69df0be5d6b977abe75a55cc8bbf3c6e676c3f26db38904dcb6025a259`.

Six `node --check` commands passed for `controller.mjs`, `server.mjs`,
`client.mjs` and all three test files, recorded in `syntax-checks.json`.
`git diff --check` passed. No broad repository test sweep was performed.

`unit-01.tap` retains a failed harness invocation: Windows rejected the bare
`C:/...` path for Node's `--import`, so no unit bodies ran. The corrected file
URL invocation in `unit-02.tap` passed all then-current 44 tests. The added
upload-cancellation case and signal forwarding motivated the final 45-test run;
neither earlier receipt is overwritten or relabelled.

## Prepared parent inputs

`synthetic-inputs/` contains an original one-page PDF and matching 800×280 PNG
and JPEG with five lines explicitly labelled synthetic, including
`Study topic: Kidney physiology.` and `Label A: 140. Label B: 4.2.` No patient
or acquired material was used. `create-fixtures.py` generated these with the
explicitly allowed public Python at
`C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe`,
standard-library PDF assembly and the already installed Pillow drawing library.
This was file preparation only; it ran no extraction/OCR/embedding engine.
The three-file manifest is immutable preparation evidence, SHA-256
`fb3f48d99bc4558a82e97a582eebe25b175794c36816416dec35520872ed9620`.

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| synthetic-study.pdf | 790 | 29a035fb3f16b084f049cd76e4fe4bc3024007bcc9b822e8f637a45bc314ef61 |
| synthetic-image.png | 19037 | 1ce7ddbbfb9311e3bf9edcbba3a26ef5cf36eec0731e652decae125d111cdab0 |
| synthetic-image.jpg | 40491 | 940526ac6af6044b667eed01b990b118e904f2daf46c1c6b29f9a8fbd542e95f |

After integration and the parent's usual source/build qualification, start a
fresh client/server using the documented fixed configuration and append:

```text
--fixture-root C:/rn-finish-20261007/evidence/control/synthetic-inputs
```

Navigate the product normally, take `renulus_snapshot`, and copy the returned
`fileInputs` locator verbatim into `renulus_upload`, with one of the three
declared basenames as `fixture`. Use a fresh snapshot after each selection or
Case mode change. Wait for the actual resulting app state. For resizing, send:

```json
{"name":"renulus_resize","arguments":{"width":1000,"height":720}}
{"name":"renulus_screenshot","arguments":{}}
```

The parent still needs actual hidden Library PDF/image selection, product
permission handling, extraction/preview/citation behaviour, and Case temporary
attachment/explicit-Save checks as appropriate to its authorised run. Responsive
layout must be observed at the requested window sizes with real fresh pixels.
Physical file dialogs, OS DPI, installation, packaged acceptance and live
generation remain separate product evidence. No GitHub write, cleanup,
personal-profile access or provider request was made by this lane.
