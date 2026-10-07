# T18 cancer-treatment injury: minimal 1.4.1 successor

Authored and assistant-reviewed 2026-10-07. Branch `codex/final-content-disposition`,
starting commit `568e206ea92b31a82096f4ce69dc2815389b230e` on the authorised ab0
lane. This report follows the [bounded disposition](finish-content-disposition-final-20261007.md).

**Decision: R1's missing authored teaching and assessment is now supplied by one
source-supported treatment-injury example. Recommend closing that content
residual after the parent's maintained validation and successor activation
succeed. No further authoring quota or whole-bank audit is required.** This
lane has prepared the immutable successor bytes and review evidence; it has not
established runtime or installed acceptance of 1.4.1. #20/S6.01 release closure
remains the parent's decision with that distinction retained.

## Exact scope and acceptance evidence

T18.O01 remains exactly: “Connect malignancy, monoclonal proteins and cancer
treatment to kidney injury.” Existing MGRS/amyloid/proximal teaching retains its
credit. The added slice supplies the previously absent cancer-treatment component:

| Exact record | Observable teaching or assessed behavior | Evidence |
| --- | --- | --- |
| `RN16-CASE-T18-TREATMENT-INJURY@1`, stage-1 | Named IV pembrolizumab exposure; improving melanoma does not exclude a treatment-associated kidney event. Exposure is a possible explanation, not automatic causation. | EMA IV SmPC 4.1 p2; 4.2 p5; 4.4 pp10–11. |
| Same case, stage-2 | Evaluate renal trajectory, reduced intake, other medicines and alternative explanations; share the assessment between kidney and oncology teams. | 4.4 pp10–11; original synthetic clinical framing. |
| Same case, stage-3 | Team explicitly establishes first Grade 2 immune-mediated nephritis. Withholding and supervised renal management replace an assumed half-dose strategy; later treatment choices need separate reassessment. | 4.2 p7, Table 1 nephritis row and preceding dose-modification text; 4.4 p11. |
| `RN16-T18-001@1`, key **C** | Include treatment-associated immune nephritis while investigating competing causes. Stable cancer imaging, cancer diagnosis, exposure alone or reduced intake do not settle causation. | 4.4 pp10–11; all five options reviewed. |
| `RN16-T18-002@1`, key **B** | For the explicitly classified first Grade 2 event, withhold pembrolizumab and use severity-based specialist management. No routine half-dose, automatic permanent stop for every Grade 2 event, or waiting for cancer progression. | 4.2 p7 and 4.4 p11; all five options reviewed. |

The case has three distinct narrative stages, six prompts, six teaching points
and three take-home statements. It is independently accessible teaching, not a
reserved-bank rationale relabelled as a case. Both questions have five original
options and distinct reserved families. Versions, family versions and key
versions start at 1. Exact authored records, objective support, claim locators,
key text, all ten option rationales and stage-level review are retained in
[proposal reviews](../../content/proposals/final-t18-20261007/reviews.json).

This is one adult IV pembrolizumab example. The team supplies the grade; the
learner is not asked to calculate it. Steroid doses, numeric grading, mandatory
biopsy criteria, full restart/rechallenge rules, other-agent toxicity, myeloma
regimens and a complete oncology course remain outside this slice. They do not
become new launch requirements. The narrower adopted behavior is now taught and
assessed without deleting any objective wording.

## Primary-source findings and permission boundary

No new source-register ID is required. Existing **G06** in `docs/SOURCES.md`
already covers EMA centrally authorised medicine status and product information,
with attribution and third-party exclusions. New pack source snapshot:
`RN16-T18-SRC-EMA-KEYTRUDA-20261007`. The canonical register and generated runtime
register are untouched.

The research skill was used for this narrow primary-source check. Its background
research attempt failed to start; the selected official pages and clinical loci
were read directly in this lane. No background output is counted as evidence.

| Official source checked 2026-10-07 | Finding used and limit |
| --- | --- |
| [EMA Keytruda EPAR](https://www.ema.europa.eu/en/medicines/human/EPAR/keytruda) | English product-information entry updated **2026-07-01**. Latest listed procedures **VR/0000316576** and **VR/0000316515**, dated **2026-06-19**. The overview's **2026-09-03** date is distinct; it is not relabelled as the SmPC revision. |
| [Official English product information](https://www.ema.europa.eu/en/documents/product-information/keytruda-epar-product-information_en.pdf) | First **IV** SmPC only in the 363-page document. Printed/physical p2: advanced adult melanoma monotherapy; p5: supervision; p7: adverse-reaction modification/nephritis; p10: assess immune-reaction aetiology and alternatives; p11: renal monitoring and nephritis management. Text loci were read; no screenshot-inspection or immutable downloaded-PDF hash claim is made. |
| [EMA legal notice](https://www.ema.europa.eu/en/about-us/about-website/legal-notice) | Attributed reuse is allowed subject to third-party/excluded content. Only original factual teaching and citations are distributed. Source prose, tables, figures, logo and the full document are not reproduced or relicensed. |

The date is a bounded current-link and selected-locus check, not exhaustive
corrigendum surveillance or proof of a specific corrected original's bytes.
The new metadata records `locator_checked` and `dated_final_baseline`. No
national-availability or all-causes/currentness claim is made. Renulus's original
teaching is CC BY 4.0; EMA/product-owner and other third-party rights remain
separate. Existing originals and earlier source evidence are preserved.

## Successor identity and preservation

[1.4.1 manifest](../../content/packs/renulus-foundations/1.4.1/manifest.json)
canonical pack SHA256:

`bf49a0ceeca78628c16dca31a579c6bf7473fec5cfd53550aec0e157d3f0e13e`

Predecessor 1.4.0 canonical SHA256 remains:

`26392c93fffb32fc4f3582ad39bbdfe4d37266fbad8c3ffda492fe394440230d`

| Record type | Inherited exactly | Added | 1.4.1 |
| --- | ---: | ---: | ---: |
| Topics / objective definitions | 27 / 57 | 0 / 0 | 27 / 57 |
| Reserved questions | 249 | 2 | 251 |
| Staged teaching cases | 58 | 1 | 59 |
| Source snapshots | 77 | 1 | 78 |
| External review item rows | 108 | 3 | 111 |
| External source review rows | 30 | 1 | 31 |

All inherited question, case, source and topic objects are deep-equal. The
topics file is also copied byte for byte: there is no topic version bump.
Withdrawals, claim flags, the 150-question minimum, all 27 target topics and all
objective definitions are unchanged. Only T18's coverage item lists/review count
gain the additions. All other coverage rows are exact.

The existing `2026-10-07-depth2` ESENeph mapping and evidence are retained exactly.
No successor mapping is necessary for this General-nephrology addition. The
mapping contract would require new topic metadata revisions to select a new
mapping; those are deliberately outside this preservation-first patch.
Consequently **the two new questions are General-only**: ESENeph remains at 245
mapped questions; the six unmapped questions comprise the four inherited
appraisal items and these two new items. There are 73 five-option questions in
the whole 1.4.1 bank. Its historical mapping prose is not a recount of this bank.
No broader ESENeph completion or new exam simulation is claimed. The existing
mapping's statement that comprehensive cancer-treatment assessment is absent
remains true; this is one bounded example.

Static pre/post hashes preserve 57 existing JSON files across earlier pack
trees, mappings and required-cell receipts. No predecessor tree, runtime,
schema, source register, test, production setting or prior report was edited.
Original accepted-ab0/0318 proof and failed aggregates remain intact. The
parent's successful ab0 manufacture/install and ongoing installed Memory/Home
run are parent-reported; they are not 1.4.1 acceptance evidence.

## Static preparation and exact remaining parent action

The established publisher's JSON/manifest/hash format was reproduced with a
small external standard-library assembly script. The publisher itself invokes
validation, so it was **not executed** during the parent's reserved serial slot.
The schema requires manifest `state: published`; this field describes the
authored snapshot format and does not certify activation or successful checks.

External evidence, kept outside this worktree:

- `C:/rn-finish-20261007/evidence/final-t18-20261007/assemble-static.py`
- `C:/rn-finish-20261007/evidence/final-t18-20261007/static-assembly.json`
- `C:/rn-finish-20261007/evidence/final-t18-20261007/renulus-foundations-1.4.1-review.json`

Review receipt SHA256:
`021b4633b07dabd7b11ff6efb4610b76cff128e2f6051e3b03e2c6f18bf54693`.
It preserves all inherited item/source review rows and references the original
1.4 review receipt SHA256
`e5271ec5c20827bb78419c8f34cd230902d33165327a37d4d5287c2045303990`.
The new raw detailed reviews are retained alongside the normalized rows. Static
JSON comparisons checked exact authored-record copies, keys, five option IDs,
source locators, inherited equality, coverage deltas and file/pack hashes.
These are not substitute runtime/schema/revision-validation results.

**Deferred command for the parent, after its execution slot is released**
(run from the integrated checkout with its supported Python environment):

```powershell
python tools/content/validate_pack.py content/packs/renulus-foundations/1.4.1 --predecessor content/packs/renulus-foundations/1.4.0 --review-evidence C:/rn-finish-20261007/evidence/final-t18-20261007/renulus-foundations-1.4.1-review.json
```

The maintained command checks schema, source IDs from the canonical register,
ancestry and review evidence together; no checks are weakened or bypassed.
Parent owns activation, any successor inventory/acceptance receipt and main
handoff. No content/runtime validator, tests, app import, provider/model call,
native work or GitHub write was performed here. No completed six-case/quiz flow
is requested to be repeated by this report.

**Closure boundary:** after the parent's successor checks and activation, R1 can
move from required missing scope to accepted bounded teaching. Preserve the
earlier disposition's dated/access C limits and optional-expansion list. Neither
this one source check nor the new count certifies all 78 sources clinically
current. No further required missing teaching component has been established;
no indefinite audit or additional authoring queue is created.
