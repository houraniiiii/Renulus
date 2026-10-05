# Source selection and acquisition coverage

Observed October 5, 2026 UTC; tracked in issues #6, #14 and #15. This is a dated
selection decision and adoption record. [SOURCES.md](../SOURCES.md) remains the
development source register. Acquisition filters and earlier planning recommendations can
change when evidence warrants it; they do not become immutable product scope.
Licence permissions, component exceptions, currency and retraction checks remain
separate from educational selection.

The metadata-only acquisition audit reconciled **183,769 distinct file paths,
86,076,155,126 bytes and 26,699 PDFs**, with 21,513 previously audited PMC body
identities. The restored **7,307-document** cohort omitted zero of the selected
adopted documents and exhausts current importer admissions. It is partial
coverage of acquired material; there is no 7,307-document product limit.
The cohort contains 122 E01 PDFs, 34 E06 PDFs, 7,150 L02 inspected article-text
derivatives and one L03 text. L02 JATS originals remain external. File totals
also include metadata, media, alternative representations and restricted or
unclassified material; these are not automatically searchable documents.

The audit found 15 queued L02 documents that the acquisition filter excluded.
All had no active revision. The parent reconsidered their classified titles and
topic relationship against the owner's broad nephrology direction. This is a
title/domain selection review, not a body/key, clinical-efficacy, currency or
retraction review. No new claims about their findings or educational quality
are made. The resulting explicit project decisions are:

| PMCID | Selection decision | Reason for this working decision |
| --- | --- | --- |
| PMC7712695 | Include as unverified research candidate | Human partial nephrectomy and renal function preservation. |
| PMC12367005 | Include as unverified research candidate | Human renal mass management and renal surgery. |
| PMC11940802 | Include as unverified research candidate | Recurrence after human renal mass ablation. |
| PMC11852628 | Include as unverified research candidate | Renal tumours during pregnancy. |
| PMC7643019 | Include as unverified research candidate | Human complex renal tumours and partial nephrectomy. |
| PMC13024833 | Include as unverified research candidate | Paediatric renal tumour education. |
| PMC12153522 | Include as unverified research candidate | Renal carcinoma in transplanted kidneys. |
| PMC12172609 | Include as unverified research candidate | Human nephrectomy/ablation research. |
| PMC9323852 | Exclude pending further project review | Rat preclinical intervention study. |
| PMC10855836 | Exclude pending further project review | General mammalian/immune review; human renal teaching role not established. |
| PMC13067890 | Exclude pending further project review | Companion-animal therapy. |
| PMC13533698 | Exclude pending further project review | Experimental porcine sepsis. |
| PMC10800216 | Exclude pending further project review | Dietary study in cats. |
| PMC12945120 | Exclude pending further project review | Feline CKD. |
| PMC9708424 | Exclude pending further project review | Veterinary cardiac/renal intervention in dogs. |

The eight included titles remain in the app's queue as research candidates,
without current-guidance status. The seven held imports were cancelled through
the actual matching installed native Library UI between **05:08:13 and 05:12:31
UTC**. Cancellation required one exact classified title, document and job;
read-only canonical verification confirmed all seven cancelled jobs, no active
revision and no alteration of the eight retained candidate jobs. The app's
supported cancellation cleans its derivative copies. External originals and
prior snapshots remain preserved. No direct SQLite writes or credential access
were used. The document filter was cleared and the app returned to Today at
**05:13:22 UTC**. Ignored per-PMCID native receipts and the classified/hash-bound
plan are retained under the E integration checkout's `.local/`.

Issue #14 implements baseline selection enforcement plus an optional explicit
project review bound to source ID, PMCID and original SHA-256. A valid selection
review changes selection only; it cannot grant a denied licence operation,
ignore a third-party exception, establish currentness or undo a retraction.
Changed/corrupt evidence and missing reviews retain a truthful blocked/default
state. Actual review metadata installation and adoption are recorded after the
reviewed implementation schema is integrated.

The next concrete coverage candidates are **20 selected E07 PNGs** and **nine
L03 PDF-only papers**, subject to per-file configuration. Five PDFs have clear
recorded CC BY candidates; four have third-party notices requiring explicit
component handling. Illustration permission/admission does not establish
searchable OCR text. **Six E07 PPTX sets and 29 E06 CC BY supplements** (23 PPTX,
five DOCX and one XLSX) are tracked separately in #15 for bounded existing
Docling format support. Neither ticket activates incidental assets, denied or
ambiguous scopes, alternate article representations, drafts or held collections
wholesale. Acquisition/selection totals, source-use eligibility, imported
originals and searchable ready revisions remain distinct evidence.

Ignored aggregate audit and handoff: `data-coverage-20261005/coverage-aggregate.json`
and `HANDOFF.md` under `E:/Renulus-native-delivery/desktop-20261005`. No article
bodies, acquired originals, private screenshots or native state were published
to GitHub. Live subscription generation remains separate acceptance work.
