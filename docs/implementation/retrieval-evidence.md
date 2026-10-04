# Retrieval API and Hermes reuse evidence

Initial bounded research, **2026-10-04**, on the evidence-discovery branch.
Research sections record primary contracts and observations; implementation,
test results and the permitted public metadata probe are recorded below.
None of these checks establishes clinical currency or account-specific billing.

Read against [the source register](../SOURCES.md), specifically L01–L03 and
T01–T04, and [accepted answers](../planning/2026-10-04-user-answers.md), including
explicit retrieval-provider activation, a useful key-free route, source-use
boundaries and no unapproved generative/billed fallback. The later main
instruction specifies a narrower initial full-text licence policy: CC BY
2.0/3.0/4.0 or CC0 only, with excluded embedded material handled separately.

## Essential integration findings

- Use Europe PMC `PMCID:PMC...` to resolve a PMCID to core metadata. A PMID-backed
  record has `source=MED`, even when its full text has a PMCID.
  `EXT_ID:PMC... AND SRC:PMC` is not an equivalent lookup. See the live checks below.
- Current observed JATS uses `article-id/@pub-id-type="pmcid"`. Its licence URI
  can be on an `ext-link` inside `license-p`, with no attributes on `license`.
  Do not inspect only `pub-id-type="pmc"` or `license/@xlink:href`. [E3]
- Missing `isRetracted` is not a negative finding. The observed core contract
  exposes publication types and typed correction relationships. [E2, E3]
- PubMed ESearch and ESummary offer JSON or XML; PubMed EFetch full records use
  XML, with no JSON format listed in the database-specific table. [N1, N3]
- Reuse Hermes pure result normalizers only for this lane. Shared dispatch
  performs rescue-provider calls, rounds requested counts upward and can write
  full text to Hermes caches. Direct adapters resolve native credentials and
  log queries; these are separate from pure result shaping. [H1–H6]

## L01 — PubMed E-utilities

Canonical API origin: `https://eutils.ncbi.nlm.nih.gov`; base path
`/entrez/eutils/`. Explicitly supply `db=pubmed`. The current official
parameter-guide PDF reports **Last Update: March 4, 2026**. Its full-record
format table is database-specific; a generic `retmode` list is not evidence
that every utility/database supports JSON. [N1–N4]

| Operation | Canonical endpoint and request | Response/parser contract to exercise in main |
| --- | --- | --- |
| ESearch | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi`; GET parameters `db=pubmed`, encoded `term`, explicit `retmode=json`, bounded `retmax`, `retstart` | JSON `esearchresult`: string-valued `count`, `retmax`, `retstart`; `idlist` of PMID strings; retain `querytranslation`, `warninglist` and `errorlist` when present. XML alternative: `eSearchResult/Count`, `IdList/Id`, `QueryTranslation`, `WarningList`, `ErrorList`. |
| ESummary | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi`; GET `db=pubmed`, comma-separated `id`, `retmode=json` | JSON `result.uids` and corresponding `result[uid]` documents; preserve title, authors, journal/date fields and typed `articleids`, including DOI/PMCID when supplied. These are bibliographic summaries, not article abstracts. XML default uses generic `DocSum/Id` and named `Item` elements; `version=2.0` uses a different, database-specific document-summary schema. |
| EFetch | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi`; GET `db=pubmed`, bounded comma-separated `id`, `retmode=xml` | `PubmedArticleSet/PubmedArticle/MedlineCitation` and `PubmedData`; also accommodate `PubmedBookArticle`. Abstracts can contain multiple labelled `AbstractText` elements and inline markup. Preserve typed identifiers, publication types, date precision and correction relationships. |

Endpoint/mode/parameter evidence: [N1, N3, N4]. The JSON field paths are the
parser contract for main to verify with its probe; this sidecar did not request
live PubMed payloads. XML full-record structure is independently verified from
the public NLM `pubmed_250101.dtd`; that filename is an observed schema
artifact, not a claim that it is the newest available DTD. [N5]

For EFetch, relevant paths include
`MedlineCitation/Article/Abstract/AbstractText`,
`MedlineCitation/Article/PublicationTypeList/PublicationType`,
`MedlineCitation/CommentsCorrectionsList/CommentsCorrections[@RefType]` and
`PubmedData/ArticleIdList/ArticleId[@IdType]`. Preserve relationship direction
and linked PMID: `RetractionIn` versus `RetractionOf`, and `ErratumIn` versus
`ErratumOf`, have different meanings. Structured publication dates can instead
be `MedlineDate`; do not invent a day for a year/season-only value. Abstract
copyright information and baseline/update deletion records are separate from
permission to reuse full text. [N5, register L01]

The official key-free limit is **3 requests/second**; default keyed access is
**10 requests/second**. The unkeyed policy concerns the public IP, so a
per-process limiter alone cannot guarantee compliance on a shared network.
Include a stable application `tool` identifier without spaces and an actual
developer contact `email`; NCBI describes registering these for distributed
software and restoring blocked access. Neither field is authentication. An
optional `api_key` raises the documented limit; omit it on the key-free route.
Batch IDs, bound retries and honour failures. Large jobs belong on weekends or
21:00–05:00 US Eastern weekdays. [N2]

PubMed ESearch exposes only the **first 10,000 matches**; additional `retstart`
pages do not make it an unlimited corpus acquisition interface. Keep interactive
discovery bounded and report truncation. Bulk acquisition remains the registered
baseline/update direction. No PubMed search or bulk download was performed here. [N1]

## L03 — Europe PMC core metadata and eligible XML

Canonical API origin: `https://www.ebi.ac.uk`; base
`https://www.ebi.ac.uk/europepmc/webservices/rest/`. Public GET requests below
needed no key, account or supplied contact. Official REST documentation describes
`format=json`/XML and `resultType=core` versus lighter bibliographic responses,
with cursor-based pagination. Explicitly choose `core`, a small `pageSize` and
JSON; preserve `nextCursorMark` if continuing. A search result is discovery
metadata, not a downloaded article. [E1, E2, E3]

### Exact identity lookup before full-text retrieval

Build `GET /search` with the query **`PMCID:<requested PMCID>`**,
`format=json`, `resultType=core` and a small `pageSize`. Require a unique
matching record whose returned `pmcid` equals the requested identifier; preserve
its independent `(source,id)`, PMID and DOI. Zero hits, mismatches or ambiguous
matches must stop a full-text acquisition rather than select an unrelated result.
This uniqueness check is a proposed implementation guard, supported by these
actual anonymous requests on 2026-10-04: [E2, E3]

| Query | Observed HTTP/result | Identity/licence evidence |
| --- | --- | --- |
| `PMCID:PMC3013671` | 200, API response `version=6.9`, `hitCount=1` | `source=MED`, `id=pmid=21062818`, `pmcid=PMC3013671`, `license="cc by-nc"`, `isOpenAccess="Y"`. Full text was not fetched; this fails main's strict licence preflight. |
| `EXT_ID:PMC3013671 AND SRC:PMC` | 200, `hitCount=0` | A syntactically accepted query that misses this known PMCID-bearing record. |
| `EXT_ID:3013671 AND SRC:PMC` | 200, `hitCount=0` | Removing the prefix does not repair the lookup. |
| `PMCID:PMC11426508` | 200, `version=6.9`, `hitCount=1` | `source=MED`, `id=pmid=39325770`, `pmcid=PMC11426508`, DOI `10.1371/journal.pone.0303005`, `license="cc by"`, `isOpenAccess="Y"`. |

Do not conclude that every `EXT_ID ... SRC:PMC` query is invalid. `EXT_ID`
identifies a record within a source; the checked record belongs to `MED`. The
observed result establishes that this expression is not a general PMCID identity
resolver. Main's generic nephrology discovery probe remains separate. [E2, E3]

### Core schema paths and retraction limits

The live JSON envelope contained `version`, `hitCount`, `request` and
`resultList.result[]`. Core records included these optional structures: [E2, E3]

- `id`, `source`, `pmid`, `pmcid`, `doi`, `title`, `authorString`;
  `authorList.author[]`; `journalInfo.journal`; `pubYear`;
  `firstPublicationDate`, `firstIndexDate`, `dateOfRevision`.
- `abstractText` and `pubTypeList.pubType[]`. An absent abstract remains absent;
  metadata/publication dates are not fetch dates or proof of currency.
- String flags such as `isOpenAccess`, `inPMC`, `inEPMC`, `hasPDF`: observed values
  were `"Y"`/`"N"`, not JSON booleans.
- `license`, and `fullTextUrlList.fullTextUrl[]` with `url`, `site`,
  `documentStyle`, `availability`, `availabilityCode`. The same record offered
  OA, free-to-read and subscription-required links; these are distinct.
- `commentCorrectionList.commentCorrection[]` with `source`, `id`, `type`,
  `note`, `orderIn`. PMC11426508 had `type="Preprint in"`; it is not a retraction.

Neither checked core response contained `isRetracted`. Retain publication
types and typed relationships; distinguish a retracted publication from a
retraction notice. Missing notices do not prove that none exist. Where the
available checks do not settle status, preserve unknown/unverified rather than
marking current/non-retracted. These samples do not verify completeness of
retraction reporting or establish clinical status. [E2, E3, register source-status rules]

No numeric Europe PMC throttling guarantee is established here. Main should
use a conservative local request budget, bounded retries and visible 429/5xx
failures, without describing that budget as the provider's guaranteed allowance.
The formal REST XSD was not obtained; guessed schema URLs returned 404 and the
website schema route returned 403. The JSON paths above are observed sample
contracts, not a claim of exhaustive schema validation. [E1–E3]

### `/{PMCID}/fullTextXML` and strict licence safeguards

Canonical route: `GET
https://www.ebi.ac.uk/europepmc/webservices/rest/{PMCID}/fullTextXML`.
It returns article XML rather than a JSON envelope. Only after the CC BY core
preflight, the generic PMC11426508 XML was fetched in memory for identity,
licence and structural inspection; no article body was saved or imported. [E3]

Observed response: HTTP 200, `Content-Type: application/xml`, 250,209 bytes;
JATS archiving DTD declaration **1.4**, root `article`, `dtd-version="1.4"`.
Top-level children included `processing-meta`, `front`, `body`, `back` and
`sub-article`. The returned declaration does not require downloading a DTD
or executing external entities. [E3, J1]

Inspect the **top-level** `front/article-meta`, not an unrestricted descendant
search that could select a sub-article's metadata. Actual identifiers included
`article-id[@pub-id-type="pmcid"] = PMC11426508`,
`article-id[@pub-id-type="pmcid-ver"] = PMC11426508.1`,
`article-id[@pub-id-type="pmid"] = 39325770` and a DOI identifier.
Legacy `pub-id-type="pmc"` may be supported as an additional explicit alias,
but was not the observed spelling. Validate the XML identity against the
request/core record before extracting eligible passages. [E3]

For this article `permissions/license` had **no attributes**. Its recognised
URI was at `permissions/license/license-p/ext-link/@xlink:href`, where the
XML namespace is `http://www.w3.org/1999/xlink`, and the URI was
`https://creativecommons.org/licenses/by/4.0/`. JATS also supports attributes
on `license`; a parser should inspect explicit licence links in both locations
and retain the surrounding licence statement, version and attribution. [E3, J1]

Main's proposed initial acquisition policy is deliberately narrower than
"open access":

1. Require exact requested identity and acceptable metadata/status preflight.
   `isOpenAccess=Y`, `inPMC=Y`, a reachable XML endpoint and a bare `license="cc by"`
   are insufficient to establish a version-specific content-use grant.
2. Accept only explicit article licence URIs resolving to the selected identities:
   `https://creativecommons.org/licenses/by/2.0/`,
   `https://creativecommons.org/licenses/by/3.0/`,
   `https://creativecommons.org/licenses/by/4.0/`, or
   `https://creativecommons.org/publicdomain/zero/1.0/`. If normalising historic
   HTTP links/trailing slashes, use an exact URI allowlist with explicit rules,
   not substring/prefix matching. NC, ND, BY-SA, jurisdiction-specific variants,
   missing/unknown terms and conflicting exclusion statements fail this initial
   policy. This is Renulus's chosen gate, not a claim that all rejected licences
   prohibit every educational use.
3. Preserve article-level credit and inspect exclusions. Omit figures, graphics,
   media, supplementary material and table content unless their applicable
   rights are verified under the article licence/use scope. Omitting only an
   image URL leaves captions or table data behind: exclude their structural
   containers and descendants as required (`fig`/`fig-group`, `graphic`,
   `inline-graphic`, `media`, `supplementary-material`, `table-wrap`/
   `table-wrap-group`, `table`, and alternative table representations).
   The inspected XML contained nine figures, four table wrappers and one media
   element; none was acquired as a separate asset.
4. Parse under byte/time limits with external DTD/entity/network resolution
   disabled. Do not fall through to a publisher scraper, PDF download or hosted
   reader when identity, permission or XML retrieval fails.

Policy provenance: main's follow-up instruction and the register's separate
display/cache/index/model-input/derivation/redistribution scopes. XML
representations: [E3, J1]. A Creative Commons label is not a blanket rights
grant for separately excluded third-party content.

## L02 — PMC OA is article-version scoped

The official current dataset README was fetched successfully over public HTTPS.
Its JSON metadata defines `pmcid`, `version`, `pmid`, `doi`,
`is_pmc_openaccess`, `is_manuscript`, `is_retracted`, `license_code`,
`xml_url`, `pdf_url`, `text_url` and `media_urls`. Some manuscripts use
`license_code="TDM"`; bucket membership is therefore insufficient for the
strict CC BY/CC0 gate. Returned file URLs carry an MD5 parameter. Preserve
article-version identity and checksum evidence; inspect the actual licence
and retraction fields rather than granting rights from the host name. [P1]

The observed README, not legacy FTP tar-package examples, is the acquisition
contract for this route. No bucket listing, article collection or dataset
download was performed. L02 and L03 provide independent eligibility evidence;
do not silently mix their version/status claims. [P1, register L02]

## T01–T03 — optional keyed retrieval contracts and units

Only official public documentation/pricing and Exa's first-party SDK source
were read. **No keyed/billed request or account inspection was made.** These
are dated published units, not a monetary ceiling or tested account entitlement.

| Provider | Canonical request/schema | Published unit and conservative request boundary |
| --- | --- | --- |
| Brave | GET `https://api.search.brave.com/res/v1/web/search`; `X-Subscription-Token`; query `q`, `count` (maximum 20), `offset` (maximum 9), optional `freshness` and `extra_snippets`. Read `web.results[]`: title, URL, description and optional extra snippets. Freshness accepts `pd`, `pw`, `pm`, `py` or a documented date range. Preserve raw date/provenance fields; search operators are experimental. [B1] | Search **$5/1,000 requests**, public plan lists 50 queries/s; plan-specific headers govern actual quotas. Cap one search HTTP request with at most five results and no automatic pagination/answer/content request. Rate headers: `X-RateLimit-Limit`, `-Policy`, `-Remaining`, `-Reset`; reset values are seconds. A 429 remains visible. [B2, B3] |
| Tavily | POST `https://api.tavily.com/search`; `Authorization: Bearer`; JSON `query`, explicit `search_depth="basic"`, `auto_parameters=false`, `include_answer=false`, `include_raw_content=false`, `include_images=false`, bounded `max_results`, `include_usage=true`. Domain/date filters are explicit. Read `results[]` (title, URL, content, score and optional dates), preserve top-level `request_id`, `usage.credits`, effective parameters and failures. [T1] | Basic search **1 credit/request**; advanced **2**. One basic HTTP request, maximum five results, no auto depth or implicit extract. `ultra-fast` is described as returning an NLP summary per URL and is excluded here. Basic `/extract` is a **separate** meter: 1 credit per five successful URL extractions, advanced 2; reported credits can be zero until the accumulation threshold. Public default limits: development 100 RPM, production 1,000 RPM. [T1–T4] |
| Exa | POST `https://api.exa.ai/search`; `x-api-key`; JSON `query`, explicitly selected ordinary search type such as `fast`, bounded `numResults`; optional `includeDomains`/`excludeDomains`, `startPublishedDate`/`endPublishedDate`. Discovery-only REST should omit `contents`. Preserve `results[]` identity/URL/title/date fields and `costDollars` if returned. Explicit optional contents endpoint: POST `https://api.exa.ai/contents`, `urls` plus only approved text/highlights options. [X1] | Fast/Auto search **$7/1,000 requests up to 10 results**; additional results above 10 **$1 per additional result per 1,000 requests**. Published Contents price **$1/1,000 pages per content type**; content/summary choices have separate units. Cap one search request and five results; any approved contents call needs its own URL/content-type budget. Public developer pricing says up to 25 Search QPS, not a guaranteed account allowance. [X2] |

Brave's current Search plan should not be confused with its Answers pricing or
Hermes's stale “2,000 free queries/month” adapter setup text. Tavily's published
pay-as-you-go price is **$0.008/credit**; free/monthly allowances do not make
arbitrary retries or implicit extracts free. Recheck selected plan/terms at
activation. Request-count/result caps and published credit units alone do not
establish an enforceable monetary ceiling. [B3, T2, H3]

Exa's inspected live SDK defaults `search()` to text contents when `contents`
is omitted. **SDK `contents=False` is an opt-out that removes the field**;
do not assume a REST boolean `contents:false` has the same documented contract.
The imported Hermes Exa adapter explicitly requests highlights, which is content
retrieval alongside search. Exclude `summary`, synthesized `outputSchema`,
`systemPrompt`/`objective`, deep variants and Answer/Research/Agent paths.
`maxAgeHours` controls cached content recrawl, not publication date; current
SDK marks crawl-date filters deprecated. [X1, H5]

Tavily publication-date estimates/beta filters likewise do not determine a
guideline's final edition or its scientific status. A search snippet/highlight
must retain its discovery role until eligible canonical content is retrieved.
Do not send case text, private uploads or patient details to these public
query/URL services. [T1, accepted answers, register T02/T03]

## T04 — static audit of the imported Hermes boundary

Imported provenance: revision
`af90026aa09949579bd423d24def3d38f743cde0` of
`https://github.com/NousResearch/hermes-agent`, from
[the source manifest](../../packaging/runtime/hermes-source.json); retained
MIT notice/license. Findings below concern these local imported files, not an
unverified claim about the newest upstream head. No adapter/module was executed.

| Reuse surface | Static finding and lane consequence |
| --- | --- |
| `_common.titled_rows`, `title_hit`, `web_hit`, `search_ok`/`search_fail`, `document` | Function bodies shape dictionaries/lists without network, credential lookup or file writes. `titled_rows` retains only title/URL/description/position, so preserve extra metadata and billing evidence before shaping. [H1] |
| Tavily `_normalize_tavily_search_results` | Pure shaping via `search_ok` and `title_hit`; suitable for main's stated reuse boundary. It drops score, publication-date estimates, request ID and usage unless main preserves those separately. `_normalize_tavily_documents` also shapes supplied responses, including per-URL failures. [H4] |
| Brave/Tavily/Exa direct adapters | Call `provider_env`, whose lookup can consult environment/native Hermes config; log raw query/URL information. Brave forwards only `q`/`count`; Tavily only basic query/result/raw-content/image fields; Exa forwards query/count and highlights. None forwards the full supported date/domain/provenance contract. Tavily also supports a native keyless header and configurable base URL; Exa supports keyless-ring routing and lazy SDK installation. Do not call these adapters in the controlled lane. [H1, H3–H5, H7] |
| `web_search_tool` / `_memoized_search` | Resolves/loads providers and config, logs query/debug data, uses a cache and rounds limits upward to 10/20/50/100 buckets before provider search. On failure it can call `_managed_search_fallback` or `_rescue_search`. A five-result UI limit does not necessarily mean a five-result vendor request. [H2, H6] |
| `web_tools_rescue` and `keyless_mcp` | `web.keyless_rescue` defaults on. Managed Perplexity failure can invoke **billed managed Firecrawl**. Other failures can enter a keyless ring across Exa/Parallel/Firecrawl/Keenable. A pinned vendor determines the starting point, not an exclusive destination. These are additional calls/providers outside this lane's explicit selection. [H2, H6] |
| `web_extract_tool`, `_dispatch_extract`, truncation/cache helpers | Can invoke rescue extraction after failure/timeout; successful contents may be cached to disk. Truncation stores full page text under Hermes `cache/web` and returns a path. Neither behaviour is a pure formatter or appropriate implicit retention policy. The inspected truncation helper itself does not call an LLM. [H6] |

No generated Answer/Research call was found in the inspected Brave/Tavily/Exa
ordinary search bodies, but omitted safety/cost options and their dispatch
dependencies prevent treating them as approved request executors. Pure
normalizers do not solve transport, filtering, rights, cancellation, credentials
or retention; main owns those controls and its actual import-path checks. [H1–H7]

## Provenance, access limits and handoff

The web tool was called repeatedly. Initial responses were blank; later primary
search results and NCBI's official PDF were available. Supplementary public
HTTP GETs read official pages/source/schema objects directly in memory. Normal
NCBI Bookshelf HTML returned a challenge page despite HTTP 200; it was not used
as content. Europe PMC website routes and `docs.exa.ai` returned 403; Exa schema
facts use its public first-party SDK and pricing page. Creative Commons deed
pages also returned 403; the exact URI allowlist above records main's requested
policy, not newly verified legal analysis. The current NLM format PDF, usage
guide, dataguide, DTD, vendor pages and PMC README were actually obtained.

Generic Europe PMC checks retrieved only the two specified identity fixtures
and the eligible XML fixture. For reproducibility, exact observed payload hashes:

- PMC11426508 core JSON: SHA-256
  `61c6ff4d2d4ef1e38adc04bf4c3043e00d9254975298126f371204a8341fb9fa`.
- PMC11426508 XML, 250,209 bytes: SHA-256
  `42263d072512ba47d74ed7677cdd77abf6347531c70522d27226b02e40867d75`.
- Live Exa SDK `exa_py/api.py`: SHA-256
  `e6672a88c43ec78f2a70fa5336aa5d26961b87695cdb6fd546775aefb5676166`.

These hashes identify observed responses, not stable future response contents.
No credentials, private/native account state, archive material, billed/account/
model endpoints, helper installation or clinical-content collection was used.
Only this evidence file was written. Main owns the generic nephrology probe,
runtime/provider tests, licence extraction tests, Windows behavior and any
implementation/acceptance claim. Other collaborators' changes in this worktree
were left untouched.

## Primary sources and exact canonical URLs

All accessed/checked on **2026-10-04** unless the source's own date is stated.
Bracketed labels above resolve here; URLs are intentionally explicit for adapter
allowlists and reproducible verification.

- **N1** — NCBI, E-utilities parameter reference, official PDF, updated
  2026-03-04:
  <https://www.ncbi.nlm.nih.gov/sites/books/NBK25499/pdf/Bookshelf_NBK25499.pdf>.
  HTML identity: <https://www.ncbi.nlm.nih.gov/books/NBK25499/>.
- **N2** — NCBI's EUtilities usage/key guide:
  <https://eutilities.github.io/site/API_Key/usageandkey/>.
- **N3** — NCBI database-specific EFetch mode/type table:
  <https://www.ncbi.nlm.nih.gov/books/NBK25499/table/chapter4.T._valid_values_of__retmode_and/>
  (also contained in N1).
- **N4** — NLM utilities dataguide and NCBI endpoint quick guide:
  <https://www.nlm.nih.gov/dataguide/eutilities/utilities.html> and
  <https://eutilities.github.io/site/Quick_Start/eu_quick/>.
- **N5** — NLM PubMed XML DTD, successfully read:
  <https://dtd.nlm.nih.gov/ncbi/pubmed/out/pubmed_250101.dtd>.
- **E1** — Europe PMC REST documentation:
  <https://europepmc.org/RestfulWebService>; API base
  <https://www.ebi.ac.uk/europepmc/webservices/rest/>; OA terms/acquisition page
  <https://europepmc.org/downloads/openaccess>. Website direct access was blocked;
  REST discovery contract also checked through the live API below.
- **E2** — Exact anonymous identity checks:
  <https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=PMCID%3APMC3013671&format=json&resultType=core&pageSize=2>,
  <https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID%3APMC3013671+AND+SRC%3APMC&format=json&resultType=core&pageSize=2>,
  <https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID%3A3013671+AND+SRC%3APMC&format=json&resultType=core&pageSize=2>.
- **E3** — Exact eligible generic core/XML structure checks:
  <https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=PMCID%3APMC11426508&format=json&resultType=core&pageSize=2> and
  <https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11426508/fullTextXML>.
- **J1** — NLM JATS licence element documentation:
  <https://jats.nlm.nih.gov/publishing/tag-library/1.4/element/license.html>.
  This is JATS vocabulary evidence, not proof that every returned article uses
  this publishing tag-set profile. E3 identifies the observed archiving profile.
- **P1** — NLM PMC dataset README:
  <https://pmc-oa-opendata.s3.amazonaws.com/README.txt>.
- **B1** — Brave Web Search documentation:
  <https://api-dashboard.search.brave.com/documentation/services/web-search>.
- **B2** — Brave quota/header conventions:
  <https://api-dashboard.search.brave.com/documentation/guides/rate-limiting>.
- **B3** — Brave published Search pricing/plan:
  <https://brave.com/search/api/>.
- **T1** — Tavily Search schema:
  <https://docs.tavily.com/documentation/api-reference/endpoint/search>.
- **T2** — Tavily credit accounting and published prices:
  <https://docs.tavily.com/documentation/api-credits>.
- **T3** — Tavily Extract schema and accumulation note:
  <https://docs.tavily.com/documentation/api-reference/endpoint/extract>.
- **T4** — Tavily key/environment rate limits:
  <https://docs.tavily.com/documentation/rate-limits>.
- **X1** — Exa's current first-party SDK, inspected as text only:
  <https://raw.githubusercontent.com/exa-labs/exa-py/master/exa_py/api.py>;
  `search` lines 1626–1798, contents default lines 1753–1762,
  `get_contents` lines 2066–2173, host/auth lines 1486–1512.
  Canonical docs (direct access blocked):
  <https://docs.exa.ai/reference/search> and
  <https://docs.exa.ai/reference/get-contents>.
- **X2** — Exa current published pricing/units:
  <https://exa.ai/pricing>.
- **H1** — Imported Hermes pure helpers:
  [plugins/web/_common.py](../../upstream/hermes/plugins/web/_common.py).
- **H2** — Imported Hermes dispatcher:
  [tools/web_tools.py](../../upstream/hermes/tools/web_tools.py), especially
  `_get_search_backend`, `web_search_tool` and `_memoized_search`.
- **H3** — Imported Brave adapter:
  [plugins/web/brave_free/provider.py](../../upstream/hermes/plugins/web/brave_free/provider.py).
- **H4** — Imported Tavily adapter/normalizers:
  [plugins/web/tavily/provider.py](../../upstream/hermes/plugins/web/tavily/provider.py).
- **H5** — Imported Exa adapter:
  [plugins/web/exa/provider.py](../../upstream/hermes/plugins/web/exa/provider.py).
- **H6** — Imported rescue, routing and retention helpers:
  [tools/web_tools_rescue.py](../../upstream/hermes/tools/web_tools_rescue.py),
  [plugins/web/keyless_mcp.py](../../upstream/hermes/plugins/web/keyless_mcp.py),
  [agent/web_search_registry.py](../../upstream/hermes/agent/web_search_registry.py),
  [tools/web_tools_extract.py](../../upstream/hermes/tools/web_tools_extract.py),
  [tools/web_tools_truncate.py](../../upstream/hermes/tools/web_tools_truncate.py),
  [tools/web_result_cache.py](../../upstream/hermes/tools/web_result_cache.py).
- **H7** — Imported config-aware credential lookup contract:
  [agent/web_search_provider.py](../../upstream/hermes/agent/web_search_provider.py).

## Implemented lane and integration seam

Worktree: C:/Users/karol/Documents/t3-workspaces/Renulus-wt-evidence, branch
build/evidence-discovery, base db7e2825. Only the new retrieval module, retrieval
tests, RetrievalConnections component/CSS/tests and this evidence file are owned.
Parent owns server registration, shell wiring and root dependency manifests.
No shared runtime, knowledge, updates, storage, helper, shell or main file changed.

[create_router](../../runtime/renulus/retrieval/api.py) registers the module in
services.registry['retrieval']; it has prefix /retrieval and uses the existing
API/error/session boundary. Parent adds /api/v1 as usual and applies new
retrieval/schema.sql once as retrieval-001. The service uses the existing
content and knowledge repository instances; it owns no server or model engine.

    service = services.registry['retrieval']
    await service.discover(topic_id, scope=ContextScope(kind='study'),
                           provider='europe-pmc', limit=5)
    await service.import_article(topic_id, pmcid,
        scope=ContextScope(kind='personal-library'), idempotency_key=opaque_id)
    service.status()

Discovery accepts study/personal-library scope, resolves the exact installed
topic ID to ContentRepository.list_topics()'s label, and builds the public query
from that label alone. It has no raw query/question/messages/URL parameter.
Case, temporary, unclassified, assessment and generated-practice scopes reject
before quota, network or writes. Submitted entity IDs are discarded at this
topic-only boundary. Imports accept only deliberate personal-library scope.

| Local API below /api/v1 | Request/action |
| --- | --- |
| GET /retrieval/connections | Public configured/enabled/selected state, dated request health and today's UTC usage; never returns a key. |
| PUT /retrieval/connections/{ncbi,brave,tavily,exa} | Explicit api_key (optional on an existing record), enabled, daily_request_limit, daily_credit_limit. Saving does not send a provider request. |
| POST /retrieval/connections/select | provider is an enabled configured tool or null; does not send a provider request. |
| DELETE /retrieval/connections/{tool} | Removes only the retrieval key/selection. Daily usage remains. |
| POST /retrieval/discover | topic_id, explicit scope, provider (europe-pmc/pubmed/selected-tool or an explicitly selected tool), bounded limit. Returns discovery records and false passage_evidence/latest_final_verified. |
| POST /retrieval/articles/import | topic_id, PMCID, personal-library scope and opaque idempotency_key. Returns the actual library import status/job, not a synthetic ready response. |

The default route is key-free Europe PMC. PubMed remains key-free even when
an NCBI key is configured; the key is used only by an enabled, selected ncbi
request. Optional vendor calls require configured AND enabled AND selected.
There is no failure fallback, automatic retry, provider discovery, vendor SDK,
Answer/Research/summary endpoint, model call or implicit URL-content download.
Optional searches are capped at five results; public metadata at twenty.
Hermes pure normalizers are executed from the existing attributed pinned
source under its controlled context. Its dispatch/auth/cache adapters are not called.

Each HTTP attempt atomically reserves its local budget immediately before send.
An empty PubMed search consumes one request; a successful search+summary consumes
two. A failed call keeps its count. Durable SQLite counters survive reconnection
and service restart; UTC midnight starts a new day. Zero blocks requests.
Tavily reserves one documented basic-search credit; Brave/Exa credits are labelled
application search-request budget units. Provider-reported usage/cost, if present,
is retained in the response separately. **These caps are not monetary guarantees.**
No account-specific price, quota or RPM/QPS enforcement was verified. The NCBI
0.35-second local spacing does not coordinate every process on a shared public IP.

Keys reuse ConnectionStore/WindowsDPAPI with a separate retrieval path and
profile-bound entropy. The module never opens the subscription connection file,
reads an environment key, probes an account on save, or returns a secret.
New/replaced keys report not_checked until an actual selected request succeeds.
Failed protection writes cannot activate an unpersisted in-memory change.

OfficialHTTP has fixed HTTPS origins, trust_env false, no redirects, no response
body/error echo, a 25-second total deadline and bounded decoded reads (metadata
2 MiB, selected XML 6 MiB). Search result URLs are syntactically filtered public
HTTPS links and are never fetched by this backend. They are not DNS-verified URLs.

## Eligible text import and replay

The import preflight uses PMCID identity lookup, requires one exact match and
eligible open-access core terms, and rejects reported retractions/notices.
Missing retraction signals remain not_settled in discovery. The existing
SourceMetadata boolean is not extended here; imported notes retain that
completeness is unknown, and latest_final_verified/content_reviewed remain false.
Typed correction relationships, publication types and both source date evidence
and extracted XML publication date are preserved for the updates lane.

DefusedXML parses only the selected JATS article without external entities.
Core/XML PMCID, PMID and DOI must agree. It accepts one explicit CC BY
2.0/3.0/4.0 or CC0 1.0 identity, including observed nested ext-link locations;
historic HTTP links normalize to the exact HTTPS identity. Restricted, spoofed,
mixed, absent and exclusion-bearing terms fail closed. Article authors/copyright
credit, exact licence statement, licence URL, identifiers, publisher and XML
SHA-256 are retained. Attribution records the text extraction/format change.
Figures, tables, media, supplements, quoted blocks and marked third-party text
are omitted; unclear exclusions require a permitted reviewed manual import.

The existing KnowledgeRepository.import_text receives the text, SourceMetadata,
Rights, canonical scope and a hashed opaque replay key with process=False.
It owns originals, durable queue, parsing/indexing and deletion. No second
article body is stored in the retrieval ledger. Rights explicitly allow the
selected local display/cache/index/embedding/model-input/derivation uses;
evaluation and redistribution remain false. The source is L03, publication
status unknown, latest-final unverified and content unreviewed.

Replay bindings keep only topic/article/hash/timestamp and library IDs.
Completed replay reads the actual existing job/document without network or
another quota charge. Deleted documents cannot be resurrected. An interrupted
acknowledgement preserves a stable request timestamp and original XML digest;
retry uses the same real library idempotency seam. A changed article requires a
new explicit import intent; reusing a key for another topic/article conflicts.

## UI and parent wiring

[RetrievalConnections](../../apps/desktop/src/platform/RetrievalConnections.tsx)
uses the existing Flow controls/tokens. Primary topic discovery is the focal
action; optional configuration follows it. Key save, enable and select are
distinct controls. Entered keys clear immediately on save attempt and are not
placed in localStorage. It shows local/provider failures and UTC request/credit
budgets. Changing topic/source aborts stale work; import binds to the result's
topic and retains its replay key across retries.

Parent may render RetrievalConnections with optional openSource(url) callback.
The current native main denies new windows and its existing authorization
bridge has strict OpenAI hosts. Literature must use a separate parent-reviewed
public-source opening path; do not broaden authorization host validation.
Copy source link is available without that bridge. Browser/native link opening
and clipboard permissions have synthetic behavior tests, not a native proof.

Requested dependency: **defusedxml==0.7.1**, already present in the accepted
helper wheel environment. No additional SDK, engine or helper artifact is needed.
Parent should add explicit root pin, register retrieval after content/knowledge,
wire the component/optional source bridge, and retain public retrieval tables
appropriately in profile backup/restore while excluding protected key files.
The existing knowledge worker performs actual queued extraction/indexing.
Discovery remains separate from passage retrieval and updates' final-edition work.

## Actual validation on October 4, 2026

The approved F0 verification environment ran CPython **3.14.4** and defusedxml
**0.7.1**. No package or root lock changed in this lane. The last full retrieval
suite passed **58 checks in 19.67 s**, including native Windows DPAPI with a
synthetic key, own-namespace isolation, actual app request validation/session
boundary, exact HTTPX mocked primary/vendor schemas, forbidden-scope no-write
snapshots, durable/concurrent budgets, decoded size/redirect/deadline guards,
licence/identity/retraction gates and real KnowledgeRepository queue/replay.
The final publication/correction metadata refinement was followed by **22 focused
import checks passing in 7.06 s** (a rerun, not additional unique checks).
FastAPI TestClient reports the existing Starlette httpx
deprecation warning; httpx2 was not introduced without parent ownership.

No actual helper engine is claimed by these queue/application tests. They inject
unused test engines with process=False; the real original/rights/job repository
performs the import. Existing parent helper proofs remain separate.

Vitest **4.1.11** passed **8 RetrievalConnections tests in 31.11 s**.
TypeScript no-emit checking passed. esbuild **0.28.1** bundled the actual
component/CSS into owned ignored scratch output (96.3 KiB JS / 1.5 KiB CSS).
This is a component build; parent shell registration and native rendering are
remaining integration work. Commands:

    python -m pytest tests/retrieval --basetemp=tests/retrieval/.local/pytest -q
    npm test -- src/platform/RetrievalConnections.test.tsx
    npm run typecheck
    ./node_modules/.bin/esbuild.cmd src/platform/RetrievalConnections.tsx --bundle --format=esm --platform=browser --target=es2022 --outdir=../../tests/retrieval/.local/component-bundle

### Permitted actual key-free metadata probe

[metadata_probe.py](../../tests/retrieval/metadata_probe.py) uses a fresh explicit
profile without any connection file, installed topic labels and primary fixed
transports. It refuses connection-bearing profiles and records HTTP statuses.
At **2026-10-04T21:07:07.202051+00:00**, all **four** requests returned HTTP 200:
two Europe PMC searches, one PubMed ESearch and one PubMed ESummary.

| Provider/topic | Actual installed label | Returned IDs | Elapsed |
| --- | --- | --- | --- |
| Europe PMC / T21 | Kidney transplantation | MED:42813674; PMC:PMC13600904; PMC:PMC13579423 | 0.963 s |
| Europe PMC / T19 | Medicines and nephrotoxicity | MED:37446744; MED:33057778 | 0.412 s |
| PubMed / T21 | Kidney transplantation | MED:42829574; MED:42829364; MED:42829285 | 1.710 s |

The retained development evidence is public-only, ignored scratch output at
tests/retrieval/.local/metadata-probe.json; profile is
C:/Users/karol/Documents/t3-workspaces/Renulus-wt-evidence/tests/retrieval/.local/metadata-profile.
There were **zero keys, model calls, billed-tool calls or full-text imports**.
The probe establishes actual key-free metadata transport/parser compatibility,
not source passage evidence, clinical currency or relevance quality.

Remaining unproved areas: live keyed/account/billing behavior; NCBI distributed
tool/contact registration and shared-IP coordination; formal complete Europe PMC
XSD coverage; a real selected licensed-article queue/engine round trip; packaged
native retrieval UI/clipboard/public-source opening. No inference or installer
proof is claimed here. Scope/dependency/API decisions were posted with gh --repo
houraniiiii/Renulus in issue #11; parent packaging relays were posted in #1.

## Request-state follow-up

The Library UI preparation exposed two real request-lifetime gaps. A failed
explicit search counted its attempted request in SQLite, but Connections did
not refresh the displayed usage or authentication state. An in-flight keyed
request could also publish its old key's health after the key was replaced;
NCBI's two-request search could continue using old authorization after the
connection was disabled, disconnected or deselected.

Connections now refreshes public status after both successful and failed
search/import attempts. Runtime binds each optional-tool operation to its
connection and selection versions. Obsolete responses cannot change current
key health, and authorization is checked again before NCBI's second request.
Already attempted requests remain counted; the UI never retries a billed call
automatically. Settings changes return retrieval_connection_changed and require
a deliberate search. This is additive behavior with no schema/API/dependency
change.

Regression checks first failed for both delayed old-key response cases and the
stale displayed counter. After the fix the complete suite passed **64 Python
checks in 22.58 s** on CPython 3.14.4 (the same existing Starlette warning),
**9 Vitest checks in 5.64 s**, and TypeScript no-emit checking. All keys and
responses were synthetic; no network/provider usage was involved.

The parent's combined suite subsequently exposed an outdated index=object()
test placeholder: generation cleanup now requires the public index.path and
remove(revision_id) contract. test_import.py now injects a bounded QueuedIndex
with that contract and asserts the actual removal call, disappearance of the
queued original and an empty cleanup ledger after deletion. Production Journal,
generation cleanup and replay guards are unchanged. All **22 focused import
checks passed in 6.60 s** against the parent's current integration runtime,
with PYTHONDONTWRITEBYTECODE and an isolated owned test profile.
