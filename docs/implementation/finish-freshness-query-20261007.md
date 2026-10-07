# Bounded freshness query repair — October 7, 2026

Prepared in `C:/rn-finish-20261007/lanes/freshness-query`, branch
`codex/final-freshness-query-20261007`, from clean base
`035098b468d18c5079b0e51b83a9013f43762102`. This report and the four source/test
files below are the entire commit scope. Parent retains the serial native and
provider slot.

The parent reported that live T10 glomerular freshness stopped at
`no_eligible_public_evidence` before any full text: acquisition used the first
five general discovery results, with the provider's default relevance ordering.
This patch changes only the evidence candidate query, through the existing
`RetrievalService.discover` path:

```text
TITLE_ABS:"Glomerular diseases" AND OPEN_ACCESS:y sort_date:y
```

The private `_evidence_candidates=True` option requires ordinary study and the
literal `europe-pmc` provider before selection, budget reservation or HTTP. It
rejects `selected-tool`, other providers and limits above five. `acquire_evidence`
passes that option explicitly with `limit=5`. General discovery retains its
existing topic query, relevance order, providers and result limits; the public
Discovery request schema does not expose the option.

The query uses the installed canonical topic label plus fixed operators. No
question, case text, entity identifier or optional key becomes query input.
The parent supplied verification of `sort_date:y` from the official
[Europe PMC REST documentation](https://europepmc.org/RestfulWebService) and
`OPEN_ACCESS:y` for the XML-available OA subset from the official
[OA documentation](https://europepmc.org/downloads/openaccess). This lane reused
that supplied verification and fetched no documentation or source corpus.

There is one candidate search, at most five metadata records considered and at
most one chosen body candidate. A successful path still makes three public
requests: candidate metadata, exact PMCID metadata, then that PMCID's XML.
There is no pagination, alternate candidate, provider rotation or retry after
failure. OA/date ordering establishes candidate availability and ordering only.
Independent metadata and XML CC BY/CC0 terms, PMCID/PMID/DOI identity, retraction,
safe JATS extraction, publication date and correction/preliminary-status gates
remain unchanged. Returned passages remain `dated-research`, with
`latest_final_verified=false` and content unreviewed. The existing read-only
Knowledge source-status projection still runs. See the
[current evidence contract](finalise-freshness-learning-flow-20261006.md#authorised-patch-and-integration-contract).

## Executed focused validation

One Python process, using the existing public environment, ran only:

| File | Result |
| --- | --- |
| `tests/retrieval/test_evidence.py` | 45 passed |
| `tests/retrieval/test_discovery.py` | 36 passed |
| Total | **81 passed, 0 failed/errors/skips, 20.59 seconds** |

The process ran October 7, 2026, 13:16:24.6803184–13:16:46.3491486 UTC;
CPython 3.14.4, pytest 9.1.1, exit 0. JUnit reports 20.549 seconds for its suite;
20.59 seconds is pytest's console summary. Exact command, from this worktree:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
& 'C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe' -B -m pytest tests/retrieval/test_evidence.py tests/retrieval/test_discovery.py -vv -p no:cacheprovider -p pytest_asyncio.plugin --basetemp=C:/rn-finish-20261007/evidence/freshness-query/pytest-tmp --junitxml=C:/rn-finish-20261007/evidence/freshness-query/pytest.xml
```

The existing autouse `tests/retrieval/conftest.py::no_live_network` guard required
an explicit mocked retrieval transport and rejected non-loopback socket access.
Synthetic tests use real SQLite repositories, inert knowledge engine objects
and the synthetic protector. No native/live/model/engine test, heavy test sweep,
provider use, source-data acquisition or application Library import ran.

The new regression exercises T10 and T21 against a query-sensitive synthetic
gateway: general discovery returns five ineligible records, while only the
exact OA/date query returns the inspected existing article fixture and an
alternate candidate. The real acquisition path returns the first candidate's
body, without touching the alternate. It verifies the canonical-only query,
absence of synthetic private/key sentinels, metadata limit, request accounting,
dated status and empty Library/import tables.

Additional cases cover empty results, an eligible sixth row outside the bound,
temporary/other forbidden scopes before usage or writes, rejection of configured
optional providers via the internal flag, and independent chosen-candidate
metadata/XML terms and identities. Metadata retraction and correction failures
terminate even when another candidate is available. Existing date, JATS locus,
excluded-content, permissions and source-journal cases all passed. General and
optional discovery cases also passed. `git diff --check` passed.

These synthetic results establish the bounded query repair. They do not claim
a successful live T10 article acquisition or installed freshness journey.

## Source and receipt identities

SHA-256 values of exact tested file bytes; these files use LF in both Git and
the working tree. The last three rows are unchanged gate/fixture dependencies.

| Path | SHA-256 |
| --- | --- |
| `runtime/renulus/retrieval/service.py` | `89f605ad9a24eab45c9d9539d1a4ebb50a205ae07ae6bcc233dbaee98616174c` |
| `runtime/renulus/retrieval/evidence.py` | `aa5135132651fe5ce955b9b7611f8ba39f293ba2abb0d3fa98e33258066a0647` |
| `tests/retrieval/test_evidence.py` | `c357be516e0fd06b7c92682b91f9b002b561421a8b6a48f9c98f7d960140270a` |
| `tests/retrieval/test_discovery.py` | `88f0a8d0b61cb117aff87df6c1bc1ff36e071b3109543b635df6bd97ae481b34` |
| `runtime/renulus/retrieval/literature.py` | `22c7f59453db0ca48d7449df9716ce88088e8b6b6979d66e151aff674f503aea` |
| `tests/retrieval/conftest.py` | `435475bb1263327b16c8691973b9f0d1e08d36d424e6d9a90f2506d7cd0936e7` |
| `tests/retrieval/fixtures.py` | `348af59c7b840e87f08537f8933612c86030e503e932da50653ab36f56745392` |

Receipts are retained outside the checkout at
`C:/rn-finish-20261007/evidence/freshness-query`. JUnit and console output retain
every exact parametrized test identity. `source-hashes.json` records source
SHA-256 and Git blob identities; `handoff.json` records the completed commit.

| Receipt | SHA-256 |
| --- | --- |
| `pytest.xml` | `f67e384ab39cf7d4a4d0f1a50fd979c868c4b349f1f79f8bfb373884dcad55bd` |
| `pytest.stdout.log` | `d1b7e795092f07c65526e955695e36e54d4fc9b41abbbeb5c3aba484403333c9` |
| `test-run.json` | `d2044343ea73f213fe45f2c2793cb8fb2255cdb4364c98f4e726d22a16a036c9` |
