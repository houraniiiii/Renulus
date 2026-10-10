# Design C contract fixtures

`design-c/1`, captured and checked October 10, 2026, on `codex/dc02-contracts`
from baseline `1b30a896`. All learner text, originals and profile state are
synthetic and owned. No credentials, patient data or model/provider calls are
used. This directory is inside the DC02 reservation.

| Fixture | What it establishes |
| --- | --- |
| legacy-schema1-records.json | Real records-only export from the baseline backend: original Learn/saved Case IDs, a reviewed session with one assisted committed answer and two unscored blanks, a separately generated session with one committed answer, exposure/replayed feedback and a synthetic Library note. Installed bank tables are omitted; immutable assessment snapshots remain. |
| legacy-schema1-inventory.json | Actual original scalar column inventories and checked migration names/checksums. New modules use sidecars and do not change these original shapes. |
| conversation.json | Saved Learn summary using the original backend ID. No inferred project. |
| saved-test-version.json | Validated immutable five-item personal version spanning CKD, dialysis, transplantation, glomerular and electrolyte topic labels. Fictional source-provenance exercises, not reviewed clinical questions. |
| fictional-artifact.json | Strict generalised fictional question/key artifact with content digest and synthetic privacy-review receipt. No original temporary ID, source edge or prompt. Receipt parsing alone does not prove a real producer's privacy review. |
| locators.json | Validated physical/printed PDF distinction, DOCX item offsets, CSV rows, XLSX sheet/range and image frame/bounds. Shape evidence only; no reader/OCR claim. |
| attempt-and-draft.json | Version pin, Test mode/timing, editable unanswered/marked drafts and separate presentation exposure. New M4 persistence is not implemented here. |
| unavailable-references.json | Independent private attempt payload with its original version ID, nullable live pointer, retained question/report pins and job publication ID after live-source deletion. No hard version FK or pruning edge. |
| job.json | Eligible memory revision input, full validated count and captured settings/policy/context epoch. Pure publication guard fixture, not a running provider job. |
| relations-and-rows.json | Frozen proposed scalar column names, reserved additive migrations, disposable/owned relation columns and separately retained unavailable provenance columns. No DDL. |

`fixture-manifest.json` pins sizes and SHA-256 values for the ten JSON fixtures
using the repository's UTF-8 LF bytes. The generator writes LF explicitly.
`build_fixtures.py` generates the legacy records through real module repositories
and validates a locally authored practice batch through the existing generated
producer. It never invokes its model/provider. The full installed bank is not
duplicated. Rebuilding the legacy capture needs a fresh explicit profile under
`C:/Renulus/scratch/design-c/contracts`; `--derived-only` updates proposal fixtures
without regenerating the captured original IDs/history.

The initial focused integration run had two failed assertions: newer local
update-schedule timestamps are retained by restore, and ZIP1 previews omit a
format_version field. After correcting those test expectations, the run passed
**24 tests in 29.71 seconds**, with the existing FastAPI/Starlette httpx
deprecation warning. No dependency change is proposed for that warning.
The tests exercised actual baseline JSON restore/repeat/deletion, ZIP1 and ZIP2
preview/restore with one digest-checked owned original, original column/ledger
preservation, transactional interrupted-migration rollback and unsupported
profile refusal. Pure contract checks cover typed ownership, unavailable pins,
retention, draft/keys separation, clocks, policy, epoch/revision invalidation and
the fictional-artifact boundary.

Retained synthetic state: `C:/Renulus/scratch/design-c/contracts/fixture-build-01`
and the `pytest-*` profiles in the same owned root. All databases/originals/ZIP
receipts stay there. The focused command is:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
& C:/Renulus/dev/python/Scripts/python.exe -m pytest tests/integration/test_design_c_contracts.py -q -p no:cacheprovider --basetemp C:/Renulus/scratch/design-c/contracts/pytest-temp
```

Parent still owns schema 1→2 compatibility, production old JSON/ZIP converters,
typed restore registration, source-dirty rebuild checks and connected migration
acceptance. Producers must implement the reserved tables/APIs, serialise
publication/finalisation and run semantic privacy checks before durable writes.
These fixtures do not close DC02 or any feature ticket.
The final proposal also reserves `committed_json`/`result_json` on the new
attempt row for durable Study commitments and terminal results, with an active
Test disclosure guard and an explicit partial-Study fixture.
After that final schema/manifest adjustment, all eight affected shape checks
passed in 0.64 seconds; the 17 other tests were deselected. Receipts are
`C:/Renulus/scratch/design-c/contracts/contract-results.xml` (24-test run) and
`C:/Renulus/scratch/design-c/contracts/final-contract-shapes.xml` (final checks).

Renulus code and synthetic contract scaffolding use MIT. Original Renulus bank
teaching text/key snapshots inside the legacy export retain CC BY 4.0 and their
existing source/review metadata; see `content/LICENSE` and `content/README.md`.
Third-party citations preserve their terms and do not imply redistribution of
the cited originals or current clinical accuracy.
