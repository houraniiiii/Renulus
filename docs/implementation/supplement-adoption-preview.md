# Office supplement adoption preview — October 5, 2026

The classified selection reconciles to **35 originals: six E07 PPTX sets and 29 E06 CC BY supplements (23 PPTX, five DOCX, one XLSX)**. All 35 current SHA-256 digests and byte counts match their acquisition receipts: **22,919,608 bytes** total. Actual serial OOXML admission accepted **32** and refused **three**; this is admission evidence, with no extraction or search-readiness claim.

| Source and format | Selected | Admission accepted | Admission refused |
| --- | ---: | ---: | ---: |
| E07 PPTX | 6 | 4 | 2 |
| E06 PPTX | 23 | 22 | 1 |
| E06 DOCX | 5 | 5 | 0 |
| E06 XLSX | 1 | 1 | 0 |
| Total | 35 | 32 | 3 |

Selection used the unified acquisition manifest's source, asset role, status and recorded licence, reconciled against the October 5 coverage aggregate and its handoff. E07 requires illustration_original_slide_set, obtained and nephrology_requested_core; E06 requires the corresponding publisher-original supplement role and recorded CC-BY-4.0. Five incidental E07 kits and two E06 NC-ND Office records were excluded from selection; their originals were not opened. Two selected E06 historical/legacy review states remain intact.

One serial Python process called renulus.knowledge.office.validate_office on each exact selected original after safe-path and receipt checks, using the existing 64 MiB and 300-slide/sheet bounds. Selection, hashing and validation took **12.922 seconds**. The pinned integration interpreter used this worktree's runtime. No Docling, transformer, embedding or index engine was loaded; a Python audit guard prohibited network connections and native/child-process launches. Originals were read only. No code, catalogue, permissions, profile, queue or installed application was changed.

All three refusals returned **unsafe_office (422)** with the safe message: “Macros, active objects, embedded packages and vector image rendering are unsupported.” This reports the validator's rule family; it does not establish that macros were present. Exact original paths, hashes, receipt lines and refusal results are retained only in the ignored local plan, **.local/office-adoption-plan.json**.

The local plan preserves per-file licence evidence, authors/creator attribution, source and asset-page associations, dates, source roles, component notices and proposed supported-import options. The six direct Servier CC BY records support explicit per-file proposals for display, caching, indexing, embedding, model input and derivation, with credit, licence link and change notices. **Four of these six also pass admission.** No proposal is activated; evaluation and redistribution remain false, and training is outside this step.

All **29 E06 supplements retain full-file processing holds**: the recorded article-level licence has third-party credit-line exceptions, and this metadata-only check did not resolve supplement/component coverage. Their proposed request templates retain false operation permissions. Attribution is complete in the receipts, but public access or a CC BY article label alone does not clear every component. Clinical/key review, current-final verification and E07 edition/revision dates remain unverified.

The parent can review the four admitted direct-licence proposals, recheck each original's exact hash, and deliberately submit raw bytes through POST /api/v1/library/import/file with the filename and JSON-encoded import-options headers in the local plan. Resolve listed format/component holds before submitting other originals. Record actual queue, conversion, retained-original and search-readiness outcomes separately: a valid Office container can still have no extractable text.

Validation covered the 35 exact originals, receipt/path invariants and the existing SourceMetadata/Rights request models. No conversion, embedding or pytest suite ran in this follow-up. Parent-reported integrated Office code is 909d2968; its separate real three-format backup/restore check passed once in 90.34 seconds and was not repeated here. The serial admission used 0358e270af8be5fa26f7af795a9a8af8798ad9dd, specifically runtime/renulus/knowledge/office.py, with existing safe-path, constraint and metadata helpers from acquired.py, engines.py and models.py.
