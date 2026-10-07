# Bounded Updates query repair — October 7, 2026

Branch `codex/final-updates-query-20261007`, worktree
`C:/rn-finish-20261007/lanes/updates-query`, base
`2ef895dbe39c7c08adbe56e043f0169a28593057`.

The parent reported T21 at `035098b4` completed with 25 metadata entries but
included IBS, Duchenne and cancer results. Its existing receipt at
`C:/rn-finish-20261007/evidence/connected/connected-source-02/result.json`,
`updates-visible`, contains the three titles retained in the regression.
Completion established transport, not relevant or reviewed evidence.

## Change and primary documentation

The former query was `(Kidney transplantation) FIRST_PDATE:[… TO …]`, with
`sort=FIRST_PDATE_D desc` as a separate URL parameter. Discovery now sends:

```text
TITLE_ABS:"Kidney transplantation" AND FIRST_PDATE:[2026-09-07 TO 2026-10-07] sort_date:y
```

This example uses October 7 and the existing 30-day window. Backslashes and
double quotes in the canonical installed topic label are escaped before phrase
quoting and URL encoding. The phrase must match title or abstract; the explicit
AND combines it with the date range. The separate sort parameter is removed.
The documented query sort requests newest publication first.

Primary sources checked on October 7, 2026:

- [Europe PMC REST documentation, Sorting Results](https://dev.europepmc.org/RestfulWebService):
  explicitly documents `sort_date:y` in the query for newest publication first.
  The production [REST page](https://europepmc.org/RestfulWebService) was available
  in indexed text but direct access returned 403; the official development-site
  documentation was readable. No article search example was executed.
- [Europe PMC's 2023 review, User-focused design](https://blog.europepmc.org/2024/01/europe-pmc-2023-a-year-in-review.html):
  documents the combined `TITLE_ABS` field for titles or abstracts. Read directly.
- [Europe PMC Help, Exact match searches and Boolean operators](https://europepmc.org/help):
  indexed official text documents quoted phrases and AND as the default. Direct
  retrieval returned 403. Missing explicit AND alone is therefore not an
  established cause of the observed unrelated results.
- [EMBL-EBI reference guide, Appendix 1, page 42](https://dev.europepmc.org/docs/EBI_Europe_PMC_Web_Service_40_Reference.pdf):
  read directly; documents phrase quotes and `FIRST_PDATE:[date TO date]` for
  first electronic/print publication. This is the dated December 2014 v1.21
  guide, used for those syntax definitions, not as current service-version proof.

## Regression evidence

Only `runtime/renulus/updates/literature.py`, the existing
`tests/updates/test_literature_refresh.py`, and this report are changed.
The runtime change is query construction only. The new tests include:

- An offline request replay with the three recorded unrelated titles, synthetic
  IDs, and synthetic title/abstract matches for the corrected query. The legacy
  query selects the unrelated fixture; the scoped request selects the two matching
  fixtures. This tests the emitted request contract, not Europe's server parser
  or actual corrected search results.
- Real installed T21 selection, the exact 30-day expression, controlled host,
  JSON/core response, 25-record request cap, truncation reporting, repeated topic
  selection and repeated-check deduplication.
- Five phrase/URL cases: CKD, embedded quotes, backslashes including a trailing
  backslash, attempted quote/operator escape, and Unicode/punctuation.
- An abstract-only match retained as metadata while synthetic abstract and body
  markers are absent from the SQLite dump. Entries remain pending, publication
  status unknown, with no reviewed entries.
- Existing partial/offline failures with per-topic query assertions; failed
  checks preserve the previous successful-check date. Existing malformed and
  oversized responses remain failures.
- Existing exact-identity refresh for an old record outside the first 100
  entries, changed/unchanged metadata, retraction metadata, absent record and
  failure handling. Refresh remains `EXT_ID:111111 AND SRC:MED`, page size one,
  with no date restriction, topic scope or sort parameter.

One serial pytest process completed **26 passed in 30.12 seconds**:

| Existing test file | Passed |
| --- | ---: |
| `tests/updates/test_literature_refresh.py` | 10 |
| `tests/updates/test_updates.py` | 4 |
| `tests/updates/test_scheduling.py` | 12 |

The command, from this worktree, was:

```text
python C:/rn-finish-20261007/evidence/updates-query/run_offline_tests.py
```

It resolved to `C:/Users/karol/AppData/Local/Programs/Python/Python312/python.exe`,
**CPython 3.12.10**, with pytest 9.0.3 and pytest-asyncio 1.3.0. The runner turns
off plugin autoload, bytecode and pytest cache, loads only pytest-asyncio, blocks
external socket connections and heavy-engine imports, and writes temporary
synthetic profiles and JUnit output outside the worktree. The existing Updates
fixture enables only content and Updates. Pytest's project configuration adds
this checkout's `runtime` to its import path.

The parent subsequently supplied delivery Python
`C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe`
(3.14.4). The above run had already finished when checked, so its receipt is
preserved and **no delivery-interpreter run or broad rerun is claimed**.
External receipts are in `C:/rn-finish-20261007/evidence/updates-query`:
`pytest-output.txt`, `pytest-results.xml`, `run_offline_tests.py` and
`verification.json`. `git diff --check` passes.

## Handoff and limits

Parent source `3031b247` includes the separately owned freshness changes. This
branch retains its assigned base and does not edit retrieval/service, shared
contracts, MCP inputs, build files or that worker's evidence. Integration and
the live T21 repeat belong to the parent, followed by packaging acceptance.

No live literature query, provider/model, engine/native app, article-body import,
private profile, GitHub operation or packaging run occurred here. The only
network research was official technical documentation. Existing discovery rows
from earlier broad checks are not purged or reclassified. Relevance, ordering and
result quality still need the parent's live repeat with the corrected request;
an abstract match can be relevant even when the title lacks the phrase. Long
curriculum labels can have limited exact-phrase recall. A bounded metadata check
does not establish exhaustive discovery, clinical currency, educational review,
latest-final status or permission to import article bodies.
