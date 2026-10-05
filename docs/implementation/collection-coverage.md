# Collection selection and recorded file coverage

October 5, 2026 · issue #14 · branch build/collection-coverage · base
2ffa7080bf1f68aebaea5fa3cd5b578784a7c708. The parent reported that 84e82e05
changed evidence only; this lane stays on the agreed base.

Collection preview, registration, deliberate import, import-next, direct acquired
adoption and replay enforce the recorded developer literature selection. The
frozen acquisition snapshot is a default candidate selection, not an immutable
medical judgement. A separate, explicit project review can include or exclude an
exact acquired file. Scientific status, current-guidance review and per-operation
rights remain independent. Personal raw-file import does not acquire this global
frozen-selection rule.

The parent corrected the initial blanket description after reviewing actual
titles against Renulus's broad nephrology scope. It retains **eight** human renal
oncology/transplant papers as unverified research candidates: PMC7712695,
PMC12367005, PMC11940802, PMC11852628, PMC7643019, PMC13024833, PMC12153522 and
PMC12172609. It holds **seven** for preclinical/general/veterinary review:
PMC9323852, PMC10855836, PMC13067890, PMC13533698, PMC10800216, PMC12945120 and
PMC9708424. These are project selection decisions, with no inferred retraction or
supersession. The parent owns installed-data correction, the actual review file,
source-selection-review.md, package evidence and later actual adoption. This
lane does not encode these IDs or a clinical taxonomy in runtime policy.

## Optional project review file

Place metadata/renulus-literature-selection-review.json under the explicitly
selected collection root. Its exact version-1 format is:

    {
      "schema_version": 1,
      "entries": [
        {
          "source_id": "L02",
          "pmcid": "PMC7712695",
          "original_sha256": "2ddfcde389a7fe6730798967300e0db2f81b203bb7368ffb233b2085a651c987",
          "decision": "include",
          "reason": "Retain within project scope as an unverified human renal oncology research candidate.",
          "reviewed_at": "2026-10-05T05:18:00Z"
        }
      ]
    }

This example uses the dated audit's original hash; it is not a claim that this
lane wrote or adopted the real record. Use the actual review time for each
decision. The unique key is (source_id, pmcid, original_sha256). Source IDs are
L02 or L03; decisions are include or exclude; PMCID must be valid; SHA-256 must
be 64 lowercase hexadecimal characters. All six entry fields are required. The
reason must be nonblank and at most 4,000 characters; the timestamp must parse
with a timezone. Top-level and entry fields are exact: duplicate JSON fields,
duplicate identity keys, unsupported fields or invalid values refuse literature
batch adoption. No rights or scientific-status fields are accepted.

Use the **external original's** acquisition SHA-256, not the canonical extracted
text derivative hash. Different bytes, source IDs or PMCIDs do not inherit an
include. A project exclude also blocks a baseline-selected file. Missing review
metadata applies the baseline; deleting a previously applicable include revokes
its batch admission. Missing, corrupt or unfrozen baseline evidence is reported
unavailable/invalid and is not hidden by an include review.

Baseline PMID and PMCID exclusions propagate through aliases recorded in the
selection metadata. Recorded frozen_selection_state/exclusion fields also deny
default admission. An exact include can override those project selection fields;
reserved material, licence restrictions, operation denials, source-status
restrictions and the strict L02 JATS licence-exception policy still apply.

Selection/review checks run again at original-read and adoption/replay boundaries.
Parsed evidence is cached against file identity, size and modification timestamps;
a replaced, changed or missing file is revalidated. Access time is excluded
because reading can change it. Baseline input is bounded at 128 MiB (the classified
snapshot observed here was 114,818,367 bytes); review input is bounded at 4 MiB.
Changed evidence after inspection requires fresh inspection, even if the candidate
remains admitted. These are checked filesystem snapshots, not an external-writer
lock across a canonical transaction.

Existing notes retain baseline selection, the review decision/reason/time and
both evidence hashes. Acquired evidence keeps scientific currentness unknown. A
newly applicable matching review participates in the acquired idempotency proof,
allowing a provenance revision on the same document identity rather than losing
the project decision during replay. Existing queued/ready records are not
automatically cancelled or relabelled by this lane. Catalogue selection failures
can recover through a later valid review without re-registration; restart a paged
bulk walk to reconsider rows already passed by its cursor.

## Supported recorded CC BY file routes

The parser recognizes recorded operation aliases for obtained E07
illustration_original_png files and the licence.code alias for L03
fulltext_original_PDF records classified obtained_verified_CC_BY_article_body.
It retains attribution, licence evidence, processing scope and acquisition
provenance in existing notes. Only matching PNG/PDF formats use this route. Other
E07 formats retain the parent's generic file-admission path, including #15's
independently owned OOXML work.

Permission comes from each recorded operation, not the CC BY label alone. Exact
known phrases are supported for these two routes; false, null, denied or unknown
aliases cannot be outweighed by a positive alias. Existing separately classified
source routes remain in place. No evaluation/redistribution operation is inferred
from missing scope. Incidental excluded E07 assets remain unavailable.

L03's recorded reading-only prose does **not** activate AI/indexing operations.
An explicit per-file operation configuration remains necessary. Any recorded
third-party notice/component exception blocks whole-file processing even when
all operation booleans are true. This applies to PMC8256322, PMC11403377,
PMC12376203 and PMC13200031. No component-removal engine or exception waiver was
added. Current receipts and source-status restrictions are checked before replay
and adoption. External originals remain intact; supported deliberate imports use
the existing canonical queue with process=False.

The authorized metadata-only audit used
E:/Renulus-native-delivery/desktop-20261005/data-coverage-20261005/HANDOFF.md and
coverage-aggregate.json, plus classified selection/manifest metadata. It opened
no original bodies. At this lane's observation, before the parent supplied its
review file, all 15 audited baseline-excluded identities were refused. The parser
found **20 E07 PNGs** with recorded operation eligibility, **four L03 PDFs**
blocked on component notices and **five L03 PDFs** awaiting operation
configuration. All **36 E06 PDF receipts** produced exactly the same Rights as
the base commit. These are metadata classifications, not actual adoption, OCR,
scientific review or searchable-passage evidence.

## Owned files and verification

- runtime/renulus/knowledge/acquired.py: baseline/review validation, exact
  selection guards, acquired evidence and review-aware idempotency.
- runtime/renulus/knowledge/collection.py: preview/register/import/replay
  enforcement and narrow recorded PNG/PDF permissions/intake.
- tests/knowledge/test_collection_coverage.py: fake-engine policy tests with
  real isolated SQLite records and actual collection API routes.
- tests/knowledge/test_acquired.py: existing synthetic fixture's baseline
  evidence and permitted metadata-read list.
- tests/knowledge/test_acquired_bulk.py: selection metadata read allowance.
- tests/knowledge/test_acquired_offline.py: opt-in proof allowance for
  baseline/review metadata; the native/actual-data proof was **not run**.
- This document.

No shared prerequisite, schema migration, model identity, dependency, helper or
desktop change is required. The parent retains models/repository/engines, shared
schemas and locks, native/profile/install/shortcut ownership and real adoption.

Run only the affected policy file with the pinned interpreter and a fresh
synthetic E-drive scratch directory. The final recorded command was:

    $env:PYTHONDONTWRITEBYTECODE = '1'
    $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
    $testScratch = 'E:/Renulus-temp/cc-20261005-final-072600'
    if (Test-Path -LiteralPath $testScratch) { throw 'Choose a fresh synthetic scratch path.' }
    & 'C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe' -B -m pytest -p no:cacheprovider -p pytest_asyncio.plugin tests/knowledge/test_collection_coverage.py --basetemp $testScratch -q --tb=short
    git diff --check

The suite prevents native engine/helper/worker initialization and external
network connections. API proof uses only the collection router and does not start
an application lifespan. Cases cover default exclusions, mixed batches, explicit
and bulk selection, API adoption/replay, exact review binding, review revocation,
changed/corrupt evidence, registration/inspection/adoption races, independent
licence/status/component restrictions and generic office-file dispatch.
Original inputs and profiles are synthetic; no providers, downloads, model
inference, real index/OCR checks or broad pytest run were used.

Final verification passed **70 tests in 75.61 seconds**, including the generic
dispatch regression. git diff --check passed. The installed pin emitted one
existing Starlette TestClient deprecation warning; this lane does not change
dependency locks. The commit is recorded in the issue handoff.
