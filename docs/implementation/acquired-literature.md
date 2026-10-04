# Acquired literature: offline selected JATS ingestion

This slice imports already-acquired, explicitly selected L02 PMC article-version
text through the existing Knowledge queue. A manifest licence label or prose
processing scope never grants operations. External originals remain in the
home-relative collection; only inspected UTF-8 text derivatives enter the local
Library. There is no acquisition, provider call, training or distribution path.

The starting commit is 4f443ce8, in branch build/acquired-literature and sibling
Renulus-wt-acquired. The collection root from parent 0dab4305 is retained as
Path.home() / Documents / Renulus-data. The source boundary is
[the single source register](../SOURCES.md), especially L02 and its acquisition
contract. No archive or unrelated/private file discovery is used.

## Contract and reuse

Owned paths are runtime/renulus/knowledge/collection.py, new
runtime/renulus/knowledge/acquired.py, tests/knowledge/test_acquired.py,
test_acquired_api.py, test_acquired_offline.py and this document. Repository,
API, schema, migrations, shared locks and dependency manifests are unchanged.
The existing repository ingestion/mutation guards serialize canonical binding;
SQLite, its durable CPU worker, Docling-core/HybridChunker, FastEmbed and LanceDB
remain the producer. The existing retrieval.literature.licensed_article route
provides safe XML parsing, exact licence URLs, attribution and text exclusions.

The existing API sequence is:

1. POST /api/v1/library/collection/catalogue?source_id=L02 registers manifest
   metadata. This does not open acquired bodies or version JSON objects.
2. GET /api/v1/library/collection/catalogue?source_id=L02 pages receipts. A
   successful, versioned CC BY/CC0-labelled JATS receipt is inspection_required
   with operation rights false. Other payloads have explicit unavailable reasons.
3. POST /api/v1/library/collection/import deliberately selects at most 250 entry
   IDs in personal-library scope. Inspection reads the manifest once for the
   batch, then only the selected JATS and matched version metadata. A successful
   inspection becomes eligible and queues import_text with process=False.
4. The existing worker drains durable jobs. Eligible means permission inspection
   passed; ready means extraction, embedding, index staging and revision
   activation completed. Catalogue status and failure codes remain visible.

An example deliberately selects the two successful proof entries:

```json
{"entry_ids":["asset_86323babaee5ec6de0a6bf1a","asset_e50b2593e12fa97d8af32ff5"],"scope":{"kind":"personal-library"}}
```

Only L02 acquired OA JATS is added by this slice. Other literature channels remain
metadata/unavailable here; their existing explicit retrieval adapters are not
expanded. Alternate PDF/plain-text assets are not independently imported: their
catalogue explanation points to the matching JATS candidate. Figures, tables,
media, supplements, quotations, boxed text and marked third-party blocks use the
existing exclusion rules. A paragraph containing excluded inline content is
omitted. Licence exceptions are rejected for the whole automatic route.

## Exact permission and provenance checks

Each successful import requires all of the following:

- A successful non-reserved acquisition receipt with SHA-256, positive byte
  count, explicit PMCID/integer article version, and matching source/role/hash
  acquisition provenance. Explicit operation denials remain denials.
- Exactly one matching acquired article-version-metadata receipt, independently
  hash/size checked. Duplicate JSON fields and conflicting receipts fail closed.
- Metadata for that exact PMCID/version with is_retracted literally false,
  is_pmc_openaccess literally true, and is_manuscript/is_historical_ocr literally
  false. Missing/string/integer substitutes are unavailable.
- The exact official PMC version metadata/XML object URLs, without redirects
  to another origin/version. XML bytes match both the acquisition SHA-256 and
  the MD5 in the primary version JSON; receipt checksum URLs must agree.
- JATS identity, DOI/PMID where supplied, licence family and any explicit
  licence-version labels agree with the receipts and metadata. The existing
  JATS allowlist accepts only CC BY 2.0/3.0/4.0 or CC0 1.0 URLs, with one explicit
  article licence, required attribution and no exclusions. Conflicting NC/ND/SA
  or reserved language is also refused.
- Selected paths resolve inside the authorised collection. Traversal, UNC,
  drive-relative paths, alternate data streams and linked components are
  refused before opening. Metadata catalogue paths use lexical checks only;
  file existence, real-path containment and hashes are checked at selection.

NC/ND/SA, TDM/manuscripts, historical OCR, ambiguous licences, challenge/error
responses, metadata, media and reserved payloads receive no operation promotion.
The adapter grants only display, cache, index, embedding, model_input and
derivation for the inspected text route. Evaluation/redistribution stay false.
The local derivative retains the article licence, authors/copyright credit,
canonical article link, exact licence URL and modification notice.

Canonical SourceMetadata contains source L02, DOI/PMID/PMCID, edition such as PMC90001.1,
the verified original JATS receipt SHA-256 in original_sha256, publication date
when present, acquisition topic IDs and acquired-jats role. The canonical revision
sha256 remains the extracted text derivative hash; it is not the original hash.
Its notes include a stable renulus-acquired-v1 JSON evidence record: exact
original and metadata paths/hashes, publisher XML URL/MD5, acquisition provenance,
licence URL/statement, derivative hash/byte count and exclusions. Catalogue
checked_at and canonical revision creation date date the inspection; the source
retrieved_at remains the acquisition date. Acquisition topic labels are retained
as unreviewed metadata, not asserted as a validated curriculum mapping.

The idempotency key binds article-version identity plus original, metadata and
text hashes and licence. Identical alternate JATS assets reuse one job/document;
queued counts report distinct jobs. Lost catalogue bindings recover from the
canonical key. Failed/cancelled jobs retry as a revision of the same document;
changed evidence also makes a revision even when extracted prose is identical.
Deleted documents reimport separately, and distinct article versions remain
distinct. No external original is renamed, rewritten or copied to the Library.
The Library original endpoint serves the UTF-8 input derivative; the acquired
JATS stays external, with its path/hash retained as provenance. Text citations
use derivative character spans, without invented original PDF page numbers.

Acquisition currentness remains unknown: publication_status unknown,
latest_final_verified false and content_reviewed false, with the nonretraction
flag labelled as a dated metadata observation. Catalogue metadata and the
renulus-acquired-v1 evidence retain this observation. A separately inspected
review may establish canonical Library currentness through the parent journal.

The follow-up starts from c7c0e373 in branch build/acquired-version-binding and
sibling Renulus-wt-acquired-binding. Parent prerequisite 18a3814a (locally
cherry-picked as e7ba40b4) adds paired identity.edition/original_sha256 matching;
see [the parent currency contract](acquired-version-currency.md). The adapter
sets original_sha256 only after receipt SHA/size and publisher MD5 checks. The
blanket article_version_review_required guard is removed. import_text still
receives the observed article.metadata and replays the journal before canonical
persistence; a positive or clearing review must match both edition and original
hash. Unbound reviews, other editions, different original bytes and derivative
hashes cannot promote or clear acquired status.

The restriction guard remains. Publication retracted/repository_removed/
access_changed true denies every matching acquired version, including other
topics. Bound superseded true applies only to the exact file; broad legacy
supersession still denies import. Unknown/currentness invalidations remain
effective. An exact inspected review can clear a journal restriction, while
receipt/JATS permission and retraction checks still run independently. Earlier
acquired revisions bind through their retained original-hash provenance note;
same-proof retries need no duplicate import. This follow-up does not edit the
parent journal, models, Updates, repository, schema or locks.

Primary technical evidence: the [PMC dataset README](https://pmc-oa-opendata.s3.amazonaws.com/README.txt),
retrieved October 4, 2026 UTC, 14,524 bytes, SHA-256
257a001b400485176702ed49ca7607d73cd83c581bffb6dd3c9be127a2e42634. It documents
version-specific JSON, the explicit OA/manuscript/retraction flags, licence_code
(including TDM) and checksum-bearing XML URLs. The local exact metadata/JATS
artifacts are the per-import permission evidence; the README is not a grant.

Official CC permission descriptions were retrieved on October 4 UTC at
[BY 2.0](https://creativecommons.org/licenses/by/2.0/),
[BY 3.0](https://creativecommons.org/licenses/by/3.0/),
[BY 4.0](https://creativecommons.org/licenses/by/4.0/) and
[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).
Their response SHA-256 values, respectively, were
bbb0dcc37f02552e7270e6d2e06be02672ce29ada816107d6fa91e1e6809714b,
befae005d7dc8701eed58fe2080fda2889c3749272d6c8aba8e8310114112095,
8dda1ccec4be91fc80821d4e4fd5c568072b9a3a74b2fdc07c249a27e920ef01,
and abb4d48fc8b85de52b377dd105532c6c549f515d492a8e1712bc99e7316a1f12.
Legal-code page requests returned HTTP 403 in this check; no claim of fetching
those pages is made. These are supporting primary references for the previously
selected strict route, not broader permissions for this collection.

## Synthetic and actual proof

The focused synthetic tests cover negative manifest and JATS licences, ambiguous
JSON/licences, retraction and version identity, DOI mismatch, original/metadata/
publisher hashes, missing provenance, explicit denials, path forms, XML entities,
excluded blocks, metadata-only catalogue reads, alternate-file deduplication,
restart/lost binding, failed/cancelled retry, changed evidence, version separation,
source-journal restrictions, API scope/batch limits and the real SQLite/worker/
LanceDB queue seam. Deterministic extraction/embedding adapters in those tests
are labelled synthetic. No live network test is used.

The actual opt-in test uses an explicit isolated prepared profile, explicit
collection root and at most ten selected IDs. The proof profile contains only
copied, SHA-256-validated, already-present public embedding helpers from the
integration profile. No model/body download occurred. Selected collection reads
are guarded to the manifest plus matched files; external Python sockets are
denied, with Windows loopback self-pipe permitted. Helper offline flags are set.
All evidence is counts/hashes/identities, without acquired source passages.

Actual environment: CPython 3.14.4; Docling 2.133.0 / Docling-core 2.99.0,
FastEmbed 0.8.1, LanceDB 0.39.0, ONNX Runtime 1.30.0 and defusedxml 0.7.1.
The text route builds a DoclingDocument, runs HybridChunker with the selected
embedding tokenizer, CPU FastEmbed, and real LanceDB staging/retrieval.

Binding follow-up verification on October 4, 2026 UTC (October 5 Warsaw):
121 checks passed in 54.20 seconds using the integration CPython 3.14.4 venv:

```
python -m pytest tests/knowledge/test_acquired.py tests/knowledge/test_acquired_binding.py tests/knowledge/test_acquired_api.py tests/knowledge/test_api_collection.py tests/knowledge/test_repository.py tests/knowledge/test_worker.py tests/knowledge/test_source_status.py tests/knowledge/test_source_version.py -q
```

The new binding file contributes 24 checks covering exact review-before-import,
matching versions within one selected batch, broad/different edition/original/
derivative reviews, publication restrictions across editions/topics, ignored
unbound and other-file clearing, exact clearing, supersession scope, observed
currentness invalidation, changed original bytes with unchanged prose, legacy
provenance and durable same-proof retry. Canonical original and derivative
hashes are separately asserted at the worker and API seams. Fixtures use real
SQLite/LanceDB and explicitly synthetic extraction/embedding; external sockets
are forbidden in the focused acquired tests. The existing Starlette TestClient
deprecation warning remains. No actual external collection import or body read
was run in this follow-up. Workspace check passed with 17,844 public files and
226 local links; git diff --check passed.

Original-slice synthetic/API/repository/worker run: 80 passed in 44.09 seconds.
The workspace check passed (17813 public files, 225 local links). A final actual
rerun passed in 193.22 seconds, with the same two ready versions, original/
metadata/derivative hashes and 38 passages. Its evidence was recorded at
22:25:41 UTC / 00:25:41 Warsaw and its measured API phase took 175.94 seconds.

At October 4, 2026 22:18:10 UTC (October 5 00:18:10 Warsaw), the observed L02
catalogue contained 178,558 receipts with zero catalogue errors, including 20,499
fulltext-jats entries. Manifest SHA-256:
0daf13d62ef9793aa5d189bd1200acefa271b8a295db00d81506fcee3ed50e9c.
Three deliberately selected versions were inspected; two became ready with
38 passages and actual retrieval returned all 38. The third, PMC12811780.1,
remained article_permission_required because the strict parser could not
establish its single explicit allowlisted JATS licence. No Knowledge job or
processing permission was fabricated for that selection. Current-only retrieval
returned no passages. Original and metadata hashes were checked again unchanged
after processing. The full test passed in 172.68 seconds; the measured API/
catalogue/import/retrieval phase took 153.48 seconds.

| Version | Subject represented | JATS bytes | Derivative bytes | Ready passages |
| --- | --- | ---: | ---: | ---: |
| PMC12207606.1 | Transplant rejection | 126416 | 30013 | 19 |
| PMC11181874.1 | ADPKD | 125458 | 27441 | 19 |

Both inspected licences were CC-BY-4.0. Exact SHA-256 evidence:

```json
[
  {
    "article_version": "PMC12207606.1",
    "original_sha256": "cb903400b809345c80f35f4316cf2b863856ce7773f9f8279a9fa4ec7d85e663",
    "metadata_sha256": "ec7f7b8a5465586fbb454c01e4841006d5105df11ca77d98e4265db952338e61",
    "derivative_sha256": "2fe2d3c7a0175f04c63c32723411e744b42ead241beacec86329ba7c57bfe9d0"
  },
  {
    "article_version": "PMC11181874.1",
    "original_sha256": "c12625fff390abed8cde058d9873cb5c26e0c0d8127aafa0d574805e30b35802",
    "metadata_sha256": "475076eaa042c44a14c6bbb5ddd850b2bad87628d5e352def75ea3703a6dcc3b",
    "derivative_sha256": "a5b0736276059a70841af6b478b62cbbf0007aa8efb5aa11b811b481f8009bef"
  }
]
```

At that snapshot, 13,082 JATS candidates still required inspection and 7,415
JATS receipts were permission-unavailable (including the inspected rejection).
Other L02 receipt counts were 40,665 alternate PDF/text, 92,483 excluded media,
3,111 TDM artifacts and 21,800 metadata/other unavailable payloads. These are
observations of this source-filtered snapshot, not constants or a claim that all
candidate articles are eligible/current/indexed.

## Remaining throughput and integration limits

The application API retains its 250-entry deliberate batch limit and one serial
CPU worker. The adapter reads a complete manifest metadata stream per selected
batch, but opens only selected matched artifacts. XML is bounded to 64 MiB,
metadata to 1 MiB, and extracted text to the existing one-million-character JATS
limit. The full catalogue still materializes receipts and performs a large
SQLite transaction; its measured cold pass is a throughput limit. Re-registering
resets acquired receipts to inspection_required until selected inspection;
canonical jobs/documents survive and dedup/retry binds them again. Do not repeat
full registration between every small batch.

Continuing toward all authorised eligible data requires deliberate batches of
remaining inspection_required JATS candidates and draining the same durable
queue. Selection failures remain explained and unavailable. No blanket rights
promotion, background import of unselected originals or corpus-completion claim
is made. Parent-owned eligibility filters/pagination and version-specific review
can improve scheduling and currentness without weakening this permission gate.

Renderer prerequisite outside this lease: the base Library checkbox at
apps/desktop/src/modules/library/index.tsx:166 disables any entry whose
eligibility is not eligible. The parent/renderer owner must allow deliberate
selection of inspection_required acquired candidates, keep temporary/reserved/
ready restrictions, and display the inspection explanation. The existing API
route is complete and proven; a renderer click-through for this new state is
not claimed before that parent-owned change.

Parent 509bad0d fixes the pre-existing retrieval-test index-cleanup fixture
mismatch found when testing the older base. No off-lease fixture/runtime fix was
made here. Checks and remaining parent prerequisites are also recorded in
GitHub issue #6; machine-only proof is in the isolated ignored profile.
