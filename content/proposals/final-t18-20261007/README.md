# Bounded T18 cancer-treatment kidney injury

Original Renulus teaching, CC BY 4.0. Synthetic case; no patient material.
Authored and assistant-reviewed on 2026-10-07. Primary-source documents retain
their own rights; no source paragraphs, tables, figures or PDF are included.

This proposal supplies exactly one missing component of `T18.O01`: connect an
identified cancer treatment to possible kidney injury and a justified next
decision. It adds `RN16-CASE-T18-TREATMENT-INJURY@1` (three stages),
`RN16-T18-001@1` (key C) and `RN16-T18-002@1` (key B). Both assessments have five
original options. It does not propose a broader oncology curriculum.

- `questions.json`, `cases.json`, `sources.json`: pack-shaped original records.
- `reviews.json`: exact authored records, objective/claim locators, both keys,
  all ten option reviews, case stages/prompts/teaching and source disposition.
- [Implementation and source findings](../../../docs/implementation/finish-t18-treatment-injury-20261007.md):
  dates, permissions, acceptance boundary, hashes and deferred parent check.

The additive 1.4.1 candidate contains these records exactly. Inherited 1.4
objects, topic versions, source objects and ESENeph mapping are unchanged.
The new questions are General-nephrology assessments; they are not new ESENeph
pins. No validator/runtime/import/test execution was performed in this lane.
