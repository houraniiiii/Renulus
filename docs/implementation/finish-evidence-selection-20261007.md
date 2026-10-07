# Bounded eligible evidence selection — October 7, 2026

Prepared in `C:/rn-finish-20261007/lanes/evidence-selection`, branch
`codex/finish-evidence-selection-20261007`, from
`b13a90d62ec7de89426ea1cfb0a495987f7e28b9`. The lease covers only
`runtime/renulus/retrieval/{evidence,literature,service}.py`, related retrieval
tests and this report. The parent owns integration and the missing live journey.
The accepted installed cb59 app and launcher were not changed.

The source change selects the first eligible dated body among at most five
distinct candidates from the existing Europe PMC query. OA availability alone
does not establish permission. Exact metadata terms prefilter candidates;
independent exact-PMCID metadata, JATS rights/identity, publication date and
read-only source-status checks still control every selected passage.

**Validation is incomplete.** The single authorised offline pytest process
stopped during collection because this lane's import guard blocked an inert
OpenAI SDK import through the existing protected-connection module. It collected
zero tests; no passing test or public-body replay is claimed. The failed receipt
is preserved and no second pytest process ran. Static syntax and whitespace
checks passed. Parent review/validation and live acceptance remain outstanding.

## Recovered failure and primary evidence

The recovered freshness lane is commit
`f3250fd9457b82e2c64c0aa3fe433ac7a88c3429`; its 81 historical checks and query
repair are recorded in [its report](finish-freshness-query-20261007.md). They are
not new passes for this selection patch.

`C:/rn-finish-20261007/evidence/connected/connected-source-03/result.json`
(SHA256 `083feb26ed99d74b145202afbe4feb436eb3c515163a97fce42799b42d80e97d`)
records T10 freshness at `2026-10-07T13:26:05.353Z`, run
`run_13e3ccc97cd1401594a2c144526d81f4`. It returned
`article_permission_required`, zero public passages/citations and Library counts
7364 before and after. Its aggregate remains partial. The receipt contains no
selected PMCID or rejected JATS body, so it cannot establish which metadata/XML
permission clause failed. The [delivery report](DELIVERY_20261007.md) and
[audit S2.09](finish-audit-20261007.md) correctly retain that missing success.

The previous code selected only the first OA, non-retracted PMCID from five
records and propagated any gateway rejection. Its core search already returned
licence metadata, but `europe_records` discarded that field. The new field is
named `metadata_licence`; `fulltext_licence` stays `unverified` in discovery.

Two bounded, unauthenticated primary metadata reads were necessary and are
preserved in `evidence/evidence-selection/primary-reads.json`:

- At `2026-10-07T14:16:52.454225+00:00`, the existing T10 query
  `TITLE_ABS:"Glomerular diseases" AND OPEN_ACCESS:y sort_date:y` returned five
  records from 880 hits: PMC13456060, PMC13595398, PMC13590780, PMC13624482 and
  PMC13565186. All five reported `license="cc by"`. This later snapshot does
  not identify the historical failing candidate. It shows why metadata filtering
  alone cannot establish XML eligibility. No body from this search was fetched.
- At `2026-10-07T14:16:52.515298+00:00`, exact `PMCID:PMC13284707` metadata was
  acquired for the already-retained MGRS body. Identity is PMID42338690,
  DOI10.1093/ckj/sfag163; metadata reports CC BY. The body at
  `evidence/mgrs/sfag163-europepmc.xml` was recovered without fetching it again.
  Its SHA256 is `d405af8506f148513c3586d81933b0b74105b79ec76a08cfced2a7713e69c980`.

The retained `content/primary/bk.xml` (PMC11335089, CC BY-NC-ND) and
`content/primary/di_xml.xml` (PMC6013691, CC BY-NC) supply additional intended
strict-denial replay inputs. No public article body was newly downloaded or
copied into Git. `recovered-inputs.json` identifies all original receipts/bodies.

Official documentation was checked through indexed primary-source results after
direct web-reader access returned403:

- [Europe PMC REST documentation](https://europepmc.org/RestfulWebService)
  documents `core` as the full metadata result and the existing search gateway.
- [Europe PMC reference guide](https://dev.europepmc.org/doc/EBI_Europe_PMC_Web_Service_Reference.pdf)
  documents the assigned licence search field and grouped publisher values.
- [Europe PMC help](https://europepmc.org/help) states that free access remains
  subject to article copyright/licence terms.

The implementation uses the exact existing metadata allowlist locally; it does
not assume that a search licence group proves all body permissions. The existing
OA/date query, topic-only egress, gateway and general-discovery ordering remain.

## Selection and disclosure contract

There is one search, no pagination, at most five records considered, at most one
exact-metadata and one XML request per distinct PMCID, and a stop at the first
eligible body. The maximum is **11 public HTTP requests** (1+5×2), often fewer
after metadata skips. Every HTTP request still reserves the existing daily
budget; transport limits and Learn's existing overall timeout still apply.
Candidates and providers are never rotated outside this finite set. A denied
candidate is never requested again within the acquisition.

Missing PMCID/OA, reported retraction and unsupported/missing metadata terms are
skipped before an article request. The metadata matcher is factored unchanged
from `fetch_article`; its independent exact-PMCID recheck remains mandatory.

Only the explicit article-local rejection set permits advancing: permission,
attribution, retraction, review/notice/preliminary status, missing/invalid/future
date, no body passages, reviewed source exclusion, and article404. Identity
mismatches, malformed XML/metadata, authentication, redirects, network errors,
provider limits and budget exhaustion terminate immediately. Cancellation is
not caught; an event-loop checkpoint also precedes each candidate check.

The successful result contains `acquisition`: provider, maximum, returned-record
count, ordered per-candidate rank/record/PMCID/stage/outcome/code/message, selected
PMCID and a human-readable disclosure. That disclosure is appended to citation
metadata notes and attribution. Existing Learn citation details already render
attribution, and its model source context already includes attribution; no Learn
or renderer change is needed for successful selection disclosure. This is a
source-path inspection, not a newly executed renderer acceptance.

On exhaustion or terminal failure, the specific error code/status/retryability
are preserved, with the detailed selection disclosure in `ApiError.message`
and `ApiError.acquisition`. The existing Learn failure event still presents its
mapped final reason and lack of source verification. It does **not** currently
render the full per-candidate failure receipt; forwarding that additional detail
would require parent coordination in the Learn/renderer lease.

Passages still carry dates, canonical URL, SHA256, JATS locus, attribution and
operation-specific rights. Maximum three passages/3000 characters each stays
unchanged. No Library original/import/index/embedding is created. No provider,
model, optional key, latest-final verification or content-review state is added.
The original `licensed_article` and `publication_date` functions are AST-identical
to the base (`static-review.json`). Their existing guards have not been relaxed.

## Validation identities and limits

The sole invocation ran `2026-10-07T14:20:38.702584+00:00` through
`14:20:40.793492+00:00`, CPython3.14.4/pytest9.1.1, exit4. The process had a
120-second wall limit, plugin autoload/bytecode disabled, pre-collection socket
and engine/provider import guards, plus the retrieval fixture's MockTransport
requirement. `openai` was blocked before test collection through
`retrieval.connections → runtime.protected → runtime.__init__ → manager →
context → hermes`. This was an overbroad test-harness guard, not an observed
retrieval failure. No native app, heavy engine, provider request or Library
import ran. All prepared runtime regressions remain **unexecuted**.

The exact command was:

```powershell
& 'C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe' -B 'C:/rn-finish-20261007/evidence/evidence-selection/run-focused.py'
```

`run-focused.py` and `test-run.json` retain every selected pytest node and guard.
The new `tests/retrieval/test_evidence_selection.py` prepares metadata rejection,
independent metadata/XML denial followed by success, all-five exhaustion/sixth
exclusion, duplicate suppression, terminal failure, cancellation and recovered
public-body replay. Existing `test_evidence.py` updates the single-candidate
metadata expectations and retains identity-terminal regressions; the former
blanket no-alternate expectations are replaced by the new article-local cases.
The recovered-body replay deliberately uses synthetic ranking and must never be
reported as actual T10 discovery. Its optional receipt was not produced because
collection failed.

For any subsequently authorised parent run, keep network/engine guards but
allow the inert SDK import and block provider client construction/calls instead.
Do not rerun the preserved `run-focused.py` unchanged. This lane did not change
the production protected-connection/module initialisation to evade that guard.

External receipts, under `C:/rn-finish-20261007/evidence/evidence-selection`:

| Receipt | SHA256 |
| --- | --- |
| `pytest.xml` | `effdae832636f0cbe902083215a1b35d44dbaa5daf3c32ec69c577f8a9a4d372` |
| `pytest.stdout.log` | `615b256c0c276f8af7d8d1dd48157d5f0cf96b8d722a5cca0e137d44d33f5b93` |
| `test-run.json` | `4185dfc9acfd4e51a96020378712f814a1c3896c42a65425d4ffa6dcf94adafa` |
| `run-focused.py` | `69dc92d83cbda96e8b0788a9b57536a526cd27652df7cdabeeb38f748f98457e` |
| `primary-reads.json` | `9ee43ef6fde14d950478420106fc7e0656d780157c28b5cc495d3ccd22768d60` |
| `recovered-inputs.json` | `f8628b16a7aaef85467dfaac20a975b97a001319f2f942e6d7808a3c201974b6` |
| `static-review.json` | `2eb08b8a15108f4a81f0b0be8a7632b01946db42991c4455ace5d290bb8460f3` |

`source-hashes.json` and `handoff.json` identify the final six leased files and
commit. Existing historical passes are not added to this failed invocation.
Successful live eligible-body selection, cancellation timing under actual I/O,
full citation disclosure and the parent-owned installed journey remain unproved.
