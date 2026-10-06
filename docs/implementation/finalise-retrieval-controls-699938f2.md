# Optional retrieval controls reconciliation — October 6, 2026

**Disposition: recover/admit existing evidence; do not repeat the retrieval suite
or select a paid tool to fill an audit cell.** S0.04/S2.10 have substantially
more bounded application protection evidence than their current R10-only
references convey. Preserve the distinction between those checks, historical
actual Windows DPAPI and unperformed live keyed/account/billing acceptance.
The parent owns admission and any audit/GitHub change. Neither row nor complete
product acceptance is declared closed here.

Prepared only in `C:/rn-finalise-20261005/lanes/retrieval-controls-final-20261006`,
branch `codex/retrieval-controls-final-20261006`, clean base
`5227cc6bc2366689503e9785ace1f68be29eaddb`. Installed product target:
`699938f20efb6bbc2cf8df684cc5c6c3450e6eaf`. No test execution, collection,
application imports, network, provider/native/helper operation or
credential/profile access occurred.
Only this report is changed.

## Receipt qualification

This worktree contains **no `.local/` or `tests/retrieval/.local/` receipts**,
and no tracked `results.xml`, `outcomes.json` or `inventory.json`. The exclusive
worktree boundary prevented opening the reports' original external receipts.
Consequently, the identities below are source-inspected and **report-derived
passing identities**, not a claim that this lane independently parsed executed
JUnit/outcomes. Raw ID/phase/digest admission remains the parent's small
read-only reconciliation below; missing receipt access is not missing execution.

[Backend regression](finalise-regression.md) records b4 at
`8c6c4b181281a0d5a6057ff032ab504f82f4e20e`, October 5,
14:34:14.100375–15:06:49 UTC: **1,219 selected, 1,214 passed, five failed, zero
skips**, valid 1,219-case JUnit and 3,657 unique setup/call/teardown events. Its
**63 retrieval selections** are inferred passed from that recorded accounting: all
five failures are the three legacy-bank restore assertions and two cold
filelock/Hermes-context subprocess checks. This inference must be checked against
the original exact rows before stronger admission.

b4 remains **complete=true, source_unchanged=false, accepted_stage_pass=false**,
pytest exit **1**, process terminal exit **2**. Its source predicate rejected
the adopted Mem0 alias; that diagnosis and later runner repair do not relabel
b4. b5/b6 validate the harness and five repaired application IDs, not a fresh
retrieval suite. Interrupted b2/b3 and earlier nonaccepted attempts retain
their original dispositions. No cumulative or final-source green aggregate.

Original b4 receipt directory is `C:/rn-finalise-20261005/b4-8c6c4b18/`:
`run.json`, `inventory.json`, `outcomes.json`, `events.jsonl`, `session.json`,
`result.json`, `module-sources.json`, `results.xml`; adjacent
`b4-8c6c4b18.terminal.json` and `b4-8c6c4b18.log`. Reported SHA-256 anchors,
**not recomputed from originals here**:

- JUnit: `1a26539447f9ef8b290b897b897ea14a5b8fab7264d634d8dcb33ed41571662b`.
- Module sources: `36a37154badb465f47f852562167e60eafae95d3b9e582015b8a9acd405bed35`.
- Existing read-only b4/b5/b6 reconciliation:
  `C:/rn-finalise-20261005/backend-reconciliation-b4-b5-b6-20261005.json`,
  `2caa6d5656b03275f0fb014ed4f44fe68ab2ea46373bec13f4cba234c228ee5b`.

## Exact protection identity map

Path aliases are literal: **D** = `tests/retrieval/test_discovery.py`;
**H** = `tests/retrieval/test_connections_http_api.py`. Expand `D::`/`H::` to
those paths. Every ID in this table belongs to the unchanged b4 test sources;
parameter suffixes shown are the literal source values. Outcome qualification
is the report-derived b4 pass above, pending original XML/JSON reconciliation.

| Control | Exact IDs | Actual assertion and limit |
| --- | --- | --- |
| Separate protected storage; failed save | `H::test_separate_protected_namespace_profile_redaction_and_failed_save` | Separate path/entropy from synthetic subscription storage; key absent from stored bytes; reopen; failed save cannot replace or enable the previous key. Uses `SyntheticProtector`, **not DPAPI**. |
| Deliberate configure/enable/select | `H::test_actual_core_router_validation_redacts_extra_case_payloads_and_secrets`; `D::test_optional_vendor_exact_schema_pure_hermes_reuse_no_fallback[brave]`, `[tavily]`, `[exa]` | Save sends no request and returns no key; disabled Tavily cannot be selected; each configured/enabled vendor rejects use before selection, then makes exactly one selected request. |
| Keyed NCBI versus key-free PubMed | `D::test_pubmed_primary_two_call_schema_and_explicit_optional_key[pubmed]`, `[ncbi]`; `D::test_empty_pubmed_uses_one_actual_request` | Exact ESearch/ESummary, two attempted requests; NCBI key only on the explicit keyed route, even when NCBI is configured/selected; empty PubMed uses one request. |
| Adapter authentication shape | The three vendor IDs above and NCBI `[ncbi]` above | Brave `X-Subscription-Token` GET; Tavily Bearer/basic-search POST with answer/raw-content/images disabled; Exa `x-api-key`/fast-search POST; NCBI `api_key` parameter. Synthetic credentials/HTTP only. |
| Authentication error/redaction | `H::test_redirect_no_follow_decoded_size_and_error_body_redaction` | Shared fixed Exa-origin transport maps synthetic HTTP401 to `retrieval_authentication_required` without echoing the body. Also rejects redirect and decoded-size overflow. This is not four individually executed current-key auth failures or live account validation; HTTP403 shares the source branch but is not separately asserted by this ID. |
| Provider quota; durable daily request/credit caps | `D::test_durable_atomic_budget_failures_count_and_utc_rollover` | Two synthetic Exa429 attempts become `retrieval_provider_limit`, remain counted after restart; third request is locally blocked with `retrieval_daily_limit`, no third HTTP call. UTC rollover and eight competing reservations admit exactly two. Request/credit caps are both two in this case. |
| Independent zero-credit denial; selection retained | `D::test_zero_credit_cap_and_failure_do_not_change_selection` | Selected Tavily with zero credits fails before HTTP; selection remains Tavily. Together with the previous shared reserve boundary, establishes local credit protection, not monetary billing. |
| Cost disclosure/result bound | `D::test_vendor_result_cap_and_unsafe_links_are_discovery_only` | Exa request capped at five results; unsafe link removed; synthetic `costDollars.total=0.007` disclosed with `billing_verified=false`. No returned link is fetched. |
| Query privacy/key-free default | `D::test_installed_topic_label_only_and_default_stays_keyfree`; API validation ID above; vendor/NCBI IDs above | Installed topic label only; entity, ambient keys and configured Tavily key absent from key-free request; raw query/question/case_text/URL rejected and redacted before HTTP. |
| Case/assessment/practice egress denial | `D::test_forbidden_contexts_reject_before_network_or_any_profile_write[temporary-case]`, `[saved-case]`, `[unclassified]`, `[reviewed-assessment]`, `[generated-practice]` | Zero HTTP calls and byte-identical synthetic profile snapshots for all five forbidden scopes. |
| Obsolete authorization/health | `D::test_replaced_key_cannot_inherit_late_old_request_health[200]`, `[401]`; `D::test_ncbi_setting_change_stops_second_request_and_retains_actual_usage[disconnect]`, `[disable]`, `[deselect]`, `[reselect]` | Replaced Exa key keeps `not_checked`; old response cannot publish new-key health. NCBI changes stop ESummary; already attempted usage persists. No automatic repeat. |

The successful vendor IDs assert one request and no preselection dispatch.
Failure/cap IDs assert unchanged selection and exact attempted-call counts.
The unchanged `discover`/HTTP error paths propagate failure and contain no
alternate-provider dispatch, retry, vendor answer endpoint or generation call.
This jointly supports **bounded controlled no-fallback behavior**; it does not
establish every provider-specific error/account/billing outcome.

**Separate native ID:**
`tests/retrieval/test_connections_http_api.py::test_native_windows_dpapi_own_synthetic_key_and_wrong_namespace`.
[Retrieval evidence](retrieval-evidence.md#actual-validation-on-october-4-2026)
reports the October 4 Windows suite including actual native DPAPI, followed by
64 passing Python checks after the authorization fix. The native test uses a
synthetic NCBI key with actual WindowsDPAPI, checks ciphertext/reopen and
wrong profile/namespace entropy failure. b4 explicitly **excludes** it; it
is not a 64th b4 pass. No original native JUnit/outcome file or digest is
identified in that report. Preserve this as **reported historical actual DPAPI**,
pending parent receipt admission, not independently verified native execution
at6999. Test, namespace and cryptographic implementation remain identical;
the only `protected.py` change since that report is new empty-store `host_id`
generation (`token_hex` → `uuid4().urn`).

## Relevant source equality, directly checked

Lane HEAD and6999 have identical retrieval runtime/test trees:
`ccc2504c49a7f8424ca7c7bb1106889f5c0cabd2` /
`930c74de55d0797ab694145dd74de86f8ea1e0a2`. Relevant working files are clean.
The following Git blobs are identical at b4,6999 and lane HEAD:

| Path (under `runtime/renulus/` unless prefixed `tests/`) | Git blob |
| --- | --- |
| `retrieval/connections.py` | `067c3bbe9984273ba5a815bde3743a35e63dc713` |
| `retrieval/http.py` | `60ee80f5fd5c6bb61d55de2bba5cb18d73cdde5e` |
| `retrieval/hermes.py` | `5bb264b8a73a966692885b78f55fcebf6cfe61bf` |
| `retrieval/api.py` | `40ec177c2656a81f3e9cda88e75f8d5fc1b72b7c` |
| `retrieval/schema.sql` | `f4c3d26c5d45070bca0db568c7469cec40824f0b` |
| `runtime/protected.py` | `7890141fccf962ca6aee856cd3d6a6bc814060e8` |
| `contracts.py` | `3a70af8fc2b825f6eb1f3648987108465f0c53a0` |
| `storage/database.py` | `747949fede4f23db414c8363b818ef908c872086` |
| `storage/paths.py` | `012e4fcac1e14a4166e347c97132e53fb924fa94` |
| `tests/retrieval/test_discovery.py` | `eca484bbcb9d77cfdf7399b5ad63d7fe5d0a5c21` |
| `tests/retrieval/test_connections_http_api.py` | `f06d702dafb00eeb748f65a2050383d7676248ba` |
| `tests/retrieval/conftest.py` | `30d8e5a7c26409b908f0592cbb4256c1d15fedb9` |
| `tests/retrieval/fixtures.py` | `5ec07f4319741412101411a0f2f2e15eb1ad43e1` |

Content repository is also unchanged. At b4/6999, attributed Hermes tree is
`01eb1c8a37a5cec57e3099f5a7bf7713f4862456`. Whole retrieval service is **not**
identical: `c5885d86cb6390fee161436928f34c638dbc22f0` →
`cdae5631ea4cb83676b1e45919d763abefc7287a`. Its first230-line boundary
(connections, scope/topic, status, reservation, health, NCBI and all discovery
adapter/error paths) is unchanged; subsequent delta adds evidence acquisition
and factors article fetching. `literature.py` and new `evidence.py`/
`test_evidence.py` also change. No whole-runtime equivalence or transfer of
all63 import assertions is claimed. Current freshness F covers its own
48-ID controlled slice separately.

## Parent action and retained limits

1. Recover b4 originals (or the already completed b4/b5/b6 reconciliation);
   verify original hash, **63 selected retrieval IDs**, exactly one passing
   setup/call/teardown each, matching outcome/JUnit names and explicit native
   exclusion. Keep b4's false source/acceptance flags and terminal exits.
2. Link those qualified controls and the separately qualified native DPAPI
   record to S0.04/S2.10. The current audit cites R10/Updates rather than this
   adapter protection inventory. Do not claim a new current-source run.
3. Retain **unperformed live keyed/account quota/billing**, individual adapter
   error-matrix limits and monetary-cap guarantees as limits. NCBI, Brave,
   Tavily and Exa are existing supported adapters, not an owner-selected new
   paid provider. No additional execution is justified by the inspected
   shared control boundaries; no test expansion or new execution command is
   proposed. If original evidence cannot be recovered,
   record that admission limit before the parent decides on any exact rerun.

Small parent-only read command, **prepared, not executed by this lane**:

```powershell
$retrievalReceipts = 'C:/rn-finalise-20261005/b4-8c6c4b18'
Get-FileHash -LiteralPath ($retrievalReceipts + '/results.xml'), ($retrievalReceipts + '/module-sources.json') -Algorithm SHA256
$retrievalInventory = (Get-Content -LiteralPath ($retrievalReceipts + '/inventory.json') -Raw | ConvertFrom-Json).items
$retrievalOutcomes = Get-Content -LiteralPath ($retrievalReceipts + '/outcomes.json') -Raw | ConvertFrom-Json
$retrievalEvents = Get-Content -LiteralPath ($retrievalReceipts + '/events.jsonl') | ForEach-Object { $_ | ConvertFrom-Json }
$retrievalInventory | Where-Object { $_.nodeid.StartsWith('tests/retrieval/') } | Select-Object nodeid,selected,category
$retrievalOutcomes | Where-Object { $_.nodeid.StartsWith('tests/retrieval/') } | Select-Object nodeid,selected,outcome
$retrievalEvents | Where-Object { $_.nodeid.StartsWith('tests/retrieval/') } | Select-Object nodeid,when,outcome
[xml]$retrievalJUnit = Get-Content -LiteralPath ($retrievalReceipts + '/results.xml') -Raw
$retrievalJUnit.SelectNodes('//testcase') | Where-Object { $_.classname.StartsWith('tests.retrieval.') } | Select-Object classname,name,failure,error,skipped
```

Local caps are durable SQLite **request/credit units**, not verified money or
account quota. NCBI local spacing does not coordinate shared-IP limits. The
October 4 free metadata probe is dated public transport evidence only, not
keyed access. Codex Probe02's October6 `subscription_limit`, pending owner
access question and paused Go remain unchanged; they are generation-account
limits and do not authorize optional paid retrieval or any fallback.

## Evidence documents and retirement

Read in this worktree at5227cc6b; SHA-256 values below were directly computed
over local checkout bytes (CRLF checkout hashes, distinct from Git blobs):

| Source | SHA-256 |
| --- | --- |
| [Current64-row audit](finalise-audit-699938f2.md), S0.04/S2.10 and F | `fdd8e33b636fe39c098c04e10861d31a8e259132496887a7b81764244239d0e9` |
| [Original audit](finalise-audit.md), verbatim rows/G8 and R05/R10 | `afc70796ff6373d371ec89c60b2d59db41f02e5b32b544b6d34f05078d4aaf62` |
| [Regression report](finalise-regression.md), b4 accounting/diagnosis, b5/b6 and excluded-ID appendix | `5d80b693e047bf3296efb1755995a5c5e7cd46f43a0806cd4fcdd480a8e76d07` |
| [Retrieval report](retrieval-evidence.md), implemented controls, October4 suite/native/free probe and authorization follow-up | `0dc1971003a28de8cfb9c5bfb19ae8d39d1faef51ccaa23563546a887511d1c7` |

AGENTS, README, brief, workspace and decisions were also read. **No ignored
artifacts were created or are needed before retirement.** Preserve the scoped
report commit; original receipts remain with their existing owners/paths.
Stop this lane at report handoff.
