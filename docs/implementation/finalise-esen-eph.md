# ESENeph content finalisation

October 5, 2026. Issue #19; worktree `C:/rn-finalise-20261005/lanes/esen-eph`,
branch `build/finalise-esen-eph`, starting commit
`9d26f1eedf31cd488b9aab5837a105ee152d9efa`. Parent owns assessment/Flow
consumers, shared contracts, migrations and native acceptance. This lane changes
content runtime, authoring, mapping metadata, release/tests and this report.
No SQLite schema/migration changes.

Original wave status: content producer, immutable release 1.1.1 and content-wide validation
are ready for parent integration. No end-to-end acceptance claim.

## Public consumer interface

`ContentRepository.track_metadata() -> list[dict]` and
`GET /api/v1/content/tracks` return the same direct JSON list, without an
envelope, with `general_nephrology` and `esen_eph` entries.

General entry: `id`, `title`, `available: bool`, `available_families: int`.
The mapped ESENeph entry has:

| Field | Meaning / initial value |
| --- | --- |
| `id`, `version`, `title` | `esen_eph`, `2026-10-05`, partial-preparation title |
| `checked_on`, `status`, `method`, `reviewer_kind` | Mapping date, `partial`, documented assistant method, `assistant` |
| `available` | At least one eligible active mapped reviewed-bank question; initially true |
| `pack` | `{id: renulus-foundations, version: 1.1.1}` |
| `available_questions`, `available_families`, `unmapped_questions` | `152`, `152`, `8`; exact active nonwithdrawn versions |
| `available_cases` | 26 distinct authored case versions; cross-domain reuse deduplicated |
| `aligned_objective_ids` | 55 objectives supported by active exam-domain item/case pins; not mastery or complete depth |
| `supporting_objective_ids`, `supporting_alignments` | `T26.O02` and generic critical-appraisal support, excluded from exam counts |
| `unaligned_objective_ids` | Active objectives with neither kind of support; initially empty |
| `format_compatible_questions`, `option_count_distribution` | `0`, `{"4":152}`; current original SBAs have four choices |
| `independent_human_review`, `official_endorsement`, `exam_simulation_available` | All false |
| `review_counts` | `{assistant_reviewed: 152, human_reviewed: 0}` for selected questions |
| `evidence` | Three C01 records: ID, title, dated edition/check, kind, HTTPS URL, rights note; PDFs also pin SHA-256 and page count |
| `exam` | Source ID, 2 papers, 100 questions/paper, 200 total, 180 minutes/paper, 5 options, indicative-weight/format limitation note |
| `domains` | Eleven rows described below |
| `excluded_questions` | Active excluded `{id, version, category, reason}` records; four generic-support and four objective-mismatch items |
| `coverage_note` | Explicit partial mapping, assistant-review, depth/mastery and generated-practice limits |

Domain rows contain `id`, original Renulus `label`, `indicative_questions`,
`source_id`, `source_page`, `available_questions`, `available_families`,
`family_shortfall`, `status: partial|gap` and `alignments`. `family_shortfall`
is only distinct-family capacity against the indicative count; zero does not
prove depth or psychometric suitability.

Alignments contain `id`, `label`, `domain_id`, `relation`, `status`,
`objective_ids`, exact `questions: [{id,version}]`, exact `cases: [{id,version}]`,
`curriculum_reference: {source_id,section,pages}`, `scope_note` and `gaps`.
Runtime filters withdrawn question pins and recomputes support. A question can
support several facets of one domain but cannot inflate two blueprint domains.
Cases can support several domains and are deduplicated in the overall count.
Generic support uses `domain_id: null` and `relation: curriculum_support` and
never enters the ESENeph scored-bank pool.

An older unmapped pack or no active pack gives ESENeph `available: false`,
`status: not_formally_mapped`, a `reason` and `exam_simulation_available: false`;
detailed mapped counters are absent. If all mapped questions are withdrawn,
dated partial metadata remains but availability is false, with a reason and zero
active question counts. Generic support is also recomputed after withdrawals.

`list_question_summaries(track='esen_eph')` and
`GET /api/v1/content/questions?track=esen_eph` select only explicitly mapped
active reviewed-bank pins and retain the existing key-free summary shape.
`topic_id` and `domain` still filter stable topic IDs; they do not become
official blueprint-domain IDs. Unknown tracks select nothing. General selection
remains all 160 questions. Public metadata contains no stems, options, keys,
rationales or learner records. Display/exposure/scoring/attempts remain M4's job.

Parent integration: replace M4's hardcoded unavailable ESENeph catalogue entry
and Flow notice with this metadata. Availability permits partial preparation,
not a full exam simulation. Keep reviewed assessment and generated practice
separate. Include 1.1.1 in the delivered content root; latest bundled selection
upgrades eligible 1.1.0 profiles. Parent owns consumers and combined acceptance.

An actual synthetic FastAPI request returned HTTP 200 and exactly matched
`track_metadata()`. Its direct two-entry response is preserved in the ignored
lane receipt `.local/esen-eph/track-metadata-1.1.1.json`; the probe log is
`.local/esen-eph/public-payload-20261005.log`. This is application evidence,
without a native application or external service. The confirmed payload handoff
is also in [issue #19](https://github.com/houraniiiii/Renulus/issues/19#issuecomment-5993499949).

## Dated primary evidence

Development source C01 remains in [SOURCES](../SOURCES.md). The official
[ESENeph hub](https://www.thefederation.uk/examinations/european-specialty-examination-nephrology)
was resolved on October 5, 2026; the former specialty URL redirects there. Its
linked PDFs were read directly and the blueprint table visually checked.
The hub states two three-hour papers of 100 best-of-five questions each. No
official sample question bank was imported.

| Evidence | Snapshot | SHA-256 |
| --- | --- | --- |
| [Linked blueprint](https://www.thefederation.uk/sites/default/files/uploads/Specialty%20Certificate%20Examination%20in%20Nephrology%20blueprint.pdf) | Undated two-page PDF, historical SCE title, checked October 5; page 1 contains 11 indicative counts totaling 200 and Other scope | `20e0d68613b660c9df1669a0958ec594e5cc317ea4f6e261ad9e994154482d9c` |
| [2022 curriculum](https://www.thefederation.uk/sites/default/files/Renal%2520Medicine%25202022%2520Curriculum%2520FINAL.pdf) | 58 pages, implemented August 2022; learning pp. 28–35, procedures p. 35, generic appraisal p. 14 | `1723591e724a1d27e40e80648c5c2854a2ac3dad211dcbc7fd077d02b9d74d16` |

These are the files linked by the live official hub, not a claimed 2026 blueprint
edition. Original display labels, interpretations and notes are Renulus CC BY
4.0 content. Source PDFs/prose/figures retain their terms and are not distributed;
no open redistribution licence is asserted. The UK curriculum is a reference,
not every EU doctor's national programme. Clinical reviews and dated sources
inherited from 1.1.0 are not represented as freshly clinically reviewed October 5.

## Release and limits

Release 1.1.1 adds immutable programme metadata and topic mapping versions.
The 27 topics advance to version 2 with partial mapping and unchanged objectives.
All 160 question/family/key versions, 26 case versions, clinical source snapshots
and general coverage are unchanged. Releases 1.0.0, 1.0.1 and 1.1.0 remain intact.
Programme metadata is stored in canonical manifest JSON; restart/restore needs
no separate filesystem mapping reader or new database table.
The reused publisher now validates a staged snapshot before writing a published
release directory, so an invalid authoring draft cannot become the bundled
latest release. Differing released files still cannot be overwritten.

| Domain (original display grouping) | Official indicative count | Mapped questions | Family capacity shortfall |
| --- | ---: | ---: | ---: |
| Glomerular/interstitial | 30 | 33 | 0 |
| Acute injury/support/biochemistry | 26 | 33 | 0 |
| CKD/urinary abnormalities | 24 | 18 | 6 |
| Bone/anemia | 12 | 9 | 3 |
| Cardiovascular/BP/diabetes | 20 | 15 | 5 |
| Urology | 14 | 4 | 10 |
| Inherited/rare | 14 | 6 | 8 |
| PD | 8 | 2 | 6 |
| HD | 14 | 3 | 11 |
| Transplantation | 14 | 11 | 3 |
| Other | 24 | 18 | 6 |

This closes absent formal alignment of supported existing content. Explicit
gaps include IgA/anti-GBM assessment, wider rare/genetic disease, routine UTI,
PD infection/access, HD access/unit operation and a focused HD case, transplant
aftercare, sexual health, adolescent transition and terminal-care assessment.
Facet notes record incomplete depth within supported areas.

Four objective mismatches are excluded without rewriting bank history:
RN11-T23-004 (citrate versus apheresis), RN11-T20-001 and -003 (HD adequacy versus
initiation), RN11-T17-004 (cancer versus infection). They remain in General;
later reviewed metadata versions can include them while preserving historical
versions. Four appraisal questions remain in General and generic curriculum
support, without inferred exam assignments. All bank questions remain four-choice
and assistant-reviewed; no full blueprint, clinician review or efficacy is claimed.

## Verification and handoff

Canonical release bundle SHA-256:
`6cb81e682328252f5980671e91477330117684c9cc22dc921f7e86206e790fcc`.

The authoring CLI validated 1.1.1 against the current source register, its
mapping-review evidence and all three immutable predecessors. It reports zero
new clinical review rows because every question/case and its exact clinical
source snapshot is inherited. This release adds mapping review only. Receipt:
`.local/esen-eph/validate-1.1.1.log`.

| Predecessor | Validated canonical bundle SHA-256 |
| --- | --- |
| 1.0.0 | `8b63d8bd02402a03d68f84c21159700e1cc5806b72ffad6f0fca2baa28f0485e` |
| 1.0.1 | `515c3cef9c6387727d45c0098fe8d319be88d6162f81026ce68aeff9be4ac3e9` |
| 1.1.0 | `3f0b712fad056a8857fb9fc913432914cad599096c28aa96fd35e7515076c670` |

The initial 26 focused ESENeph tests passed in 33.64 seconds. Receipt:
`.local/esen-eph/pytest-focused-20261005-1.log`. Four
additional controlled-interleaving checks commit pack activation or question
withdrawal on another canonical connection after the manifest read. Metadata
and question selection must retain one coherent read snapshot, and the next
read must observe the committed change.

The full `tests/content` suite passed: **121 passed, 1 warning in 186.58
seconds**. The warning is the existing Starlette/httpx TestClient deprecation.
Receipt: `.local/esen-eph/pytest-all-20261005-1.log`; synthetic fixture state is
under `.local/esen-eph/pytest-all-20261005-1/`. Command:

```powershell
& 'C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe' -m pytest tests/content -q --basetemp .local/esen-eph/pytest-all-20261005-1
```

`git diff --check` passed. Tests cover reproducible release/mapping/review bytes, all predecessor
versions, review/source pins, explicit gap rejection, four-option limitations,
practice/evaluation exclusion, withdrawals, bootstrap/restart, key-free public
metadata and real synthetic committed attempts/feedback surviving activation
and restart.

Changed owned files:

- `runtime/renulus/content/api.py`, `repository.py`, `schema.py`,
  `validation.py`, `programmes.py`.
- `tools/content/author_foundations.py`, `author_eseneph.py`,
  `revision_checks.py`.
- `content/README.md`, `content/mappings/esen-eph-2026-10-05.json`,
  `content/reviews/renulus-foundations-1.1.1.json`.
- `content/packs/renulus-foundations/1.1.1/manifest.json`, `topics.json`,
  `questions.json`, `cases.json`, `sources.json`, `coverage.json`.
- `tests/content/test_api.py`, `test_bootstrap.py`, `test_eseneph.py`.
- `docs/implementation/finalise-esen-eph.md`.

Local handoff commit subject: `Add dated partial ESENeph mapping and release 1.1.1`.
The exact commit SHA is recorded in the final issue #19 handoff and lane reply;
this report is included in that commit. No push or merge is performed.

No earlier release/review, assessment consumer, Flow file, shared contract,
SQLite schema or migration is edited. Parent still owns consumer integration,
delivery and combined acceptance; content gaps and four-option limits remain
as described above. Issue #4 remains closed historical initial-pack acceptance;
this work is tracked in #19. No provider, model/OCR/helper, native application,
heartbeat or patient/private-data checks were run by this lane.
Synthetic application tests do not establish full end-to-end, clinical or
educational acceptance.

## Bounded recovery and required-cell recheck — October 5, 2026

Recovered local commit `604b6d11` was clean at the start of this wave. The
original logs, synthetic scratch, hub HTML, two PDF snapshots, mapping/review
records and all published releases remain intact. The parent subsequently
integrated it as `a6b5d597`, the assessment consumer as `16ad199d`, and reports
integration `8c6c4b18`. This lane supplies only the follow-up owned patch; no
prerequisite merge, consumer edit, launcher change or source freeze is performed.

The owner decision on October 5 supersedes the earlier delivery plan. Current
acceptance is an **unsigned Windows build validated on this PC**, including
the bundled runtime with OS-only PATH, matching installation, source/artifact
hashes, normal shutdown/reopen and actual required journeys/recovery. Parent
records the accepted specification at `793eddb4`. Signing and validation on a
separate clean PC/VM are optional future distribution work; they do not block
current completion and are not requested by this lane. The earlier statements
about unproved signing/clean-machine checks remain historical observations.

### Corrected authoring defect

`validate_revision` previously allowed a new pack to retain every historical
item while lowering `minimum_questions` or dropping required `target_topics`.
A higher topic version could also remove an adopted objective identity. The
checker now rejects all three. Tests include standalone valid snapshots with
lowered targets, so the rejection comes from the adoption history rather than
a checksum or JSON-schema error. All predecessor target values are preserved.
No published pack/item/key/family/source bytes or canonical records change.

### Adopted breadth and remaining cells

`content/required-cells/renulus-foundations-1.1.1.json` is a reproducible authoring
manifest built by `tools/content/check_required_cells.py`. It pins the canonical
1.1.0 target baseline and 1.1.1 release hashes, the original 27 target topics,
56 objectives, minimum 150 reserved assessment questions, four expansion
questions per topic and at least two reviewed skill types per topic. These
bank minima are met with 160 questions and 26 cases. The broader plan's
evidence/question/case/update-source axes remain distinct. No numeric full-exam
depth target is invented, and the indicative official counts are not promoted
to required exact exam weights.

Every topic has at least one teaching case with an explicit related objective.
Tag-only case links are listed separately and cannot satisfy a case/evidence
cell. The linked evidence consists of cited teaching stages, not a claim of
complete standalone topic explanations or objective mastery. Four known
objective-mismatch question versions are excluded from objective-link support
in this manifest and remain excluded from formal ESENeph selection.
Their original General records and all historical attempts remain available.
Objective-level pins expose another limit: all 56 objectives have question
links, but only 50 have explicit case links. `T01.O02`, `T08.O03`, `T08.O04`,
`T09.O02`, `T11.O02` and `T25.O01` lack a linked teaching case. In order,
these concern non-GFR creatinine determinants, CKD-anemia investigation, ESA
goals, BP treatment tolerance, drug-related interstitial injury and tailored
nutrition/activity. The per-topic case minimum does not prove that every
objective has a case. Reserved-question rationales remain unavailable to
teaching retrieval and are not counted as teaching-mode explanations. This
records gaps without inventing a new per-objective case quota.

All **35** clinical source records are `dated_final_baseline`. The **27** topic
update-source cells therefore retain `needs_currency_review`, with exact source
IDs, register IDs, editions, locators/check notes and check dates. This neither
declares those sources superseded nor claims a fresh latest-final, chapter
replacement, corrigendum or retraction clearance. The source register remains
`docs/SOURCES.md`; this manifest is evidence reconciliation, not another
acquisition catalogue or a permission grant. The required-cell result is
`adopted_bank_minima_met: true`, `complete_content_coverage: false`.

Eight mapped curriculum facets have no pinned question or case:

| Facet ID | Missing content scope |
| --- | --- |
| `urinary_infection_gap` | Routine/recurrent UTI assessment and teaching case |
| `other_inherited_gap` | Genetic/metabolic conditions beyond ADPKD, including Alport, Fabry, cystinosis, primary hyperoxaluria and inherited salt-wasting |
| `pd_infection_gap` | PD peritonitis, exit-site/tunnel infection and access complications |
| `hd_access_gap` | HD access and unit operation |
| `transplant_aftercare_gap` | Recipient aftercare, immunosuppression, rejection and post-transplant complications |
| `sexual_health_gap` | Contraception, fertility and sexual dysfunction |
| `transition_gap` | Transition and young-adult transplant adherence |
| `end_of_life_gap` | Terminal symptoms, dialysis withdrawal and medication assessment |

The HD domain also has **zero** pinned focused teaching cases. All 11 domains
remain partial; other facet notes retain missing IgA/IgAV and anti-GBM
assessment, hypernatremia/diabetes insipidus, hypokalemia/alkalosis/mixed
acid-base disorders, comprehensive prescription/complication pathways, and
procedure competence limits. Four known question-objective mismatches need
future reviewed metadata versions rather than alteration of published records.
No broad authoring expansion is attempted in this bounded wave.

### Official evidence and access result

Both preserved official PDFs match their exact published mapping SHA-256 pins:
the undated two-page SCE-titled blueprint and the 58-page 2022 curriculum.
The retained blueprint page-1 image was visually rechecked against all 11
indicative counts and the Other facet list. Curriculum pages 14 and 28–35
were reread from the preserved PDF, covering generic appraisal, content of
learning and procedures. No transcription/hash/page-reference defect was
found in these checked fields. These are the existing official editions,
not a claimed 2026 blueprint or official review of Renulus's questions.

Fresh public reads of the hub and both exact PDF URLs at **14:35:56 UTC on
October 5, 2026** returned **HTTP 403 for all three**. The retry read in memory
and wrote only an ignored metadata/error receipt; it imported no material and
preserved the originals. Rechecking the live hub links and any newer official
edition remains an access gate, separate from the successful snapshot/hash
and page-content checks. Receipt:
`.local/esen-eph/bounded-recheck/primary-evidence-20261005.json`. No newly
successful live-source check is claimed.

The track remains available for partial preparation with **152 mapped bank
items**, four choices each and **zero** best-of-five-format items. Assistant
review is recorded honestly; no official endorsement, independent human
review, full exam suitability, psychometric evidence or efficacy is claimed.
An independent human-review prerequisite is not invented. The mapping's
original `checked_on` date and successful first-wave evidence are retained.

### Follow-up verification and current-PC checklist

Receipts use the isolated, ignored
`.local/esen-eph/bounded-recheck/` directory. The initial focused run had
one failed fixture: it removed a case objective without advancing the
immutable case version. The test now models a new case version; the failed
`pytest-new.log` / `pytest-new.xml` are preserved. A one-off PDF text display
also hit the Windows console encoding limit; rereading with UTF-8 completed.
No source original or published record was changed to repair either check.

Follow-up results:

| Check | Result | Receipt under `.local/esen-eph/bounded-recheck/` |
| --- | --- | --- |
| Full content suite after the target-guard fix | **127 passed**, one existing Starlette/httpx warning, 251.84 seconds | `pytest-all.log`, `pytest-all.xml` |
| Focused final manifest tests after adding objective-level pins | **6 passed**, 11.45 seconds | `pytest-final.log`, `pytest-final.xml` |
| Canonical release, three predecessors and inherited mapping review | Pass; unchanged bundle SHA-256 `6cb81e682328252f5980671e91477330117684c9cc22dc921f7e86206e790fcc` | `validate-1.1.1.log` |
| Final manifest byte reproduction and target reconciliation | Pass; bank minima met, complete coverage false | `required-cells-check-final.log` |
| All published release/review files against recovered `604b6d11` | **29/29 byte-identical** | `preserved-release-review-bytes.json` |
| Live official recheck | **3/3 HTTP 403**, not passed | `primary-evidence-20261005.json` |

`git diff --check` passed. No automated test failure remains. The final manifest
detail changes are authoring receipt fields only; no runtime, consumer, pack
selection or assessment code is changed. Exact owned paths for this follow-up:

- `content/README.md`.
- `content/required-cells/renulus-foundations-1.1.1.json`.
- `tools/content/revision_checks.py`.
- `tools/content/check_required_cells.py`.
- `tests/content/test_required_cells.py`.
- `docs/implementation/finalise-esen-eph.md`.

The follow-up commit is handed back separately from `604b6d11` and the parent's
prerequisite integrations. The canonical release remains **1.1.1**; no new
clinical release, question authoring, key correction or source acquisition is
claimed. The report, manifest and receipts identify the remaining cells and
source-access/currency limits for the parent to retain through integration.

Current delivery checks remain parent-owned:

- Unsigned matching Windows installation on the owner's current PC.
- Bundled runtime with OS-only PATH and matching source/artifact hashes.
- Normal close/reopen, required connected journeys and recovery.
- Delivered content 1.1.1 and the actual assessment consumer's partial labels.

This follow-up has no provider requests, private profile/credential reads,
external imports, helper/model/OCR/native-app workload, heartbeat, other-agent
dispatch or push. Full application acceptance and final source freeze remain
with the parent.
