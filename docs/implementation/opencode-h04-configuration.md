# H04 bounded configuration authority

2026-10-11. Configuration lane, branch `codex/oc-configuration`, assigned checkout
`C:/Users/karol/.codex/worktrees/oc-configuration/repo`, baseline
`74e3424b5c03ac4616834911c13faef1c064d09c`. **H04 remains unaccepted.** This is a
tested canonical configuration/role/permit module. H03 actual transport activation
and Settings effective-version behavior remain parent integration work.

The user authorized these dedicated files and reserved
`runtime/migrations/002-harness-configuration.sql`. Existing server discovery
uses `runtime-002-harness-configuration`; standalone construction applies the
same migration idempotently through the existing Database. Parent owns canonical
relations, startup/Services assembly, contracts, host/IPC and runtime migration
003. Its activation prerequisite is `96a29d11861f901bded2ea46c81cb20f948a194b`.
The subsequent purpose-budget fix reserves additive migration
`runtime/migrations/004-harness-dispatch-purpose.sql`, with canonical inventory
identity `runtime-004-harness-dispatch-purpose`. Canonical Database alone applies
it, idempotently; applied 002 is unchanged and 003 remains the paired-store owner.
No subagents, private state, credentials, live providers, installs, pushes or
deployments were used.

## Sources and reuse

- [H04](../planning/opencode-v2/tickets/04-adjust-roles-and-configuration-with-visible-activation.md),
  [S1](../planning/opencode-v2/specs/01-harness-control.md),
  [integration plan](../planning/OPENCODE_V2_INTEGRATION_PLAN.md),
  [foundation handoff](OPENCODE_FOUNDATIONS_HANDOFF.md),
  [architecture](../planning/ARCHITECTURE.md) and
  [parallel ownership](../planning/PARALLEL_WORK.md) govern scope and ownership.
- [Configuration research](../research/2026-10-10-opencode-integration/w2-05-configuration-revocation.md),
  [routing audit](../research/2026-10-10-opencode-integration/w1-05-model-routing.md)
  and [routing closure](../research/2026-10-10-opencode-integration/w6-04-minimality-routing.md)
  define epoch narrowing, uncertain replay, proposed budgets and Automatic order.
- [Database](../../runtime/renulus/storage/database.py) supplies canonical SQLite,
  transaction/publication checks and migration checksums.
  [Policy](../../runtime/renulus/runtime/policy.py) supplies exact allowlists and
  endpoints. No ProviderManager selector, credential store, execution loop,
  network dispatch or OpenCode live-store writer was added.

The named research, TDD, implement, codebase-design and domain-modeling skills
were read. Research and final standards/spec review stayed in this lane under
the explicit no-subagents instruction. Tests use the authorized public
configuration/role/permit interface with real SQLite, without querying private
tables. Terminology is recorded here because the shared glossary is outside
this lane's ownership.

## Terms

| Term | Meaning |
| --- | --- |
| Configuration version | Immutable content-addressed complete policy input, including predecessor and protected connection reference. |
| Requested version | Most recently staged version; staging grants no execution. |
| Effective version | Selected validated version; admission must also be open under a matching healthy runtime. Pending selection keeps admission closed. |
| Candidate | Unpublished construction with generation, recovery, package acquisition, external MCP startup and live runtime-store writing closed. |
| Revocation overlay | Monotonic epoch and revoked capability/purpose/connection/model identities, independent of immutable versions. |
| Permit | Durably spent allowance for one outbound step/attempt; reservation and final dispatch admission are distinct. |
| Tool continuation | New step after a confirmed tool-result permit, inheriting its dispatch purpose, with retry number zero and another root/purpose debit. |
| Dispatch purpose | Stable purpose of an outbound attempt, distinct from its owning run purpose and request-kind label. Retries and continuations inherit it from the prior permit. |
| Retry | Explicit additional attempt for the same run, step, payload and route after a configured qualifying failure. |
| Uncertain dispatch | A request may have been sent; uncertainty never authorizes replay. A trusted late receipt can reconcile it. |

## Public parent integration interface

All methods belong to `ConfigurationAuthority(existing_database)`. IDs/references
are bounded opaque identifiers. The parent supplies trusted purpose, scope and
attempt identity; these policy methods are not arbitrary renderer commands.

| Method | Contract |
| --- | --- |
| `stage(ConfigurationSpec) -> version` | Freeze connection, role/content/build/tool/MCP hashes, capabilities, context, attempts and children. Revalidate copied models; hash canonical UTF-8 JSON including predecessor. Update requested only. |
| `configuration(version)` / `status()` | Inspect frozen input after hash verification; inspect requested/effective/failed/failure_code/admission_open. Reopen does not prove external runtime readiness. |
| `validate(version, probe) -> bool` | Invoke probe outside canonical transactions. Candidate supplies pinned config, closure flags and grant epoch. Require CandidateHealth with exact configuration_version, grant_epoch and final effective registry_hash after all transforms. Reject stale epochs, mismatched registry, unhealthy/open effects or second runtime writer. Failure preserves another healthy effective version; failure of the effective version closes admission. |
| `activate(version, RestartBoundary, expected_effective=...)` | Atomic expected-effective/predecessor/requested/readiness/current-epoch check; select with admission closed and previous retained for reconciliation. Reject competing/stale activation. |
| `open_admission(version, registry_hash=..., grant_epoch=...)` | Require selected healthy version, final matching registry and current grant epoch; open admission and clear pending activation bookkeeping. |
| `reconcile_restart(RestartBoundary)` | Parent first observes old runtime/domain settlement. Roll interrupted selection back to previous with admission closed; dispatched becomes uncertain, reserved becomes cancelled_before_send. Normal restart also closes admission. Revalidate reconstructed effective runtime under current grants before reopen. |
| `resolve_role(version, purpose, catalogue=(), operation_model=None, parent_model=None)` | Disabled policy first; authorized operation override, role override, parent, selected root. Reject selected invalid override. Automatic follows existing allowlist order filtered by catalogue membership, then first allowed ID. Pure projection of existing provider-owner snapshots; no independent catalogue/connection state. |
| `begin_run(run_id, purpose, capability_scope=(), catalogue=(), operation_model=None)` | Pin current effective version and exact route/scope. This durable ledger is for saved operations. H21 must establish volatile accounting before temporary consumers use it. |
| `begin_child(run_id, parent_id, purpose, capability_scope=(), operation_model=None)` | Pin parent version/connection, inherit parent model unless valid override applies; enforce depth/concurrency and requested capability subset. Native child coordination remains OpenCode's. |
| `run(run_id)` | Inspect pinned version/route, active/settled state, effective capabilities and spent root dispatch count. |
| `revocation_overlay(conn=None)` | Consistent current epoch and sorted revoked identities; owning transaction keeps publication serialized with revocation. |
| `revoke(identity) -> epoch` | Monotonic narrowing. Capability IDs plus purpose:<purpose>, connection:<ref>, model:<exact-id>. Activation/rollback never restores revoked grants; deliberate grant restoration is outside this slice. |
| `require_current(run_id, required_capabilities=(), connection=None, permit_id=None, conn=None)` | Guard current run/ancestors, required scope and optional credential revision. With permit_id, require the same owning run, its stable dispatch purpose and the union of permit/requested capabilities. Return version/purpose/dispatch_purpose/grant_epoch/effective_capabilities/route. Parent supplies permit_id for permit-derived publication within its final transaction alongside existing policy/context/cancellation/deletion/outcome checks. |
| `admit(run_id, step_id, payload_hash=..., request_kind=..., connection=..., limits=..., input_tokens=..., required_capabilities=(), retry_of=None, continuation_of=None)` | Reserve one debit jointly against root, purpose and child-local ceilings. Persist stable dispatch_purpose. A retry inherits the identified same-step failed permit; an exact continuation inherits a confirmed same-run permit and starts at retry zero. Ambiguous continuation requires identity. Reserved receipt has dispatch_allowed false. Confirmed replay returns its receipt only. |
| `mark_dispatched(permit_id, connection=..., limits=..., input_tokens=..., payload_hash=..., required_capabilities=())` | Recheck authority/ancestors, required capability union, exact payload/connection and final fit; change reserved to dispatched once. Only this call returns dispatch_allowed true. Transport sends once and enforces returned output cap and exact endpoint/protocol/model. |
| `permit(permit_id)` | Read durable outcome/identity/route/reference and dispatch_purpose; pre-004 ambiguity returns null. Uses a read connection, including legacy confirmed replay; inspection grants no dispatch. |
| `complete(permit_id, outcome, result_reference=None, failure_code=None)` | Safe outcome/reference only. Reject illegal transitions/conflicting terminal receipts. Uncertain can reconcile to confirmed with trusted late reference, without dispatch or publication authority. |
| `settle_run(run_id)` | Parent calls after actual engine settlement. Refuse reserved/dispatched attempts or active children; settled child releases policy slot. |

**RestartBoundary and CandidateHealth are trusted integrator inputs, not proof by
themselves.** Literal fixtures test policy only. Parent obtains actual admission,
runtime-owner/domain settlement and final registry observations. No host/SDK/UI
activation is claimed from boolean fixtures.

RouteLimits contains proven input/output/window limits for the exact pinned
deployment and credential revision. Unknown limits deny dispatch. Requested
131,072 tokens is a configurable ceiling, not accepted model capacity. Final
input plus output/reserve must fit the smaller proven/configured window. H03/H10
count final text/media/tool schemas/results after hooks and validate modality.
Catalogue presence and synthetic tests prove no account capability.

## Bounds, attempts and fixtures

Proposed defaults: twelve shared foreground permits; one standalone
extraction/compaction/summary/result narrative/daily bundle/digest; zero title
permits; depth one, concurrency two; 4,096 output tokens narrowed by role/route
caps; zero retries. Existing generation batch/job ceilings remain additional
domain constraints. A reservation stays spent even if cancelled. Final admission
wins or loses against revocation; after dispatch the effect may already exist.
Observation timeout never authorizes a send. Same-route explicit retries use
prior permit identity and another debit; uncertain recovery cannot replay.
One-permit requests must fit before dispatch, without free precompaction.

[Fixtures](../../tests/runtime/fixtures/harness_roles.json) cover nine current
source consumers and four planned roles, across CKD, dialysis, transplantation,
glomerular disease, electrolytes, AKI and hypertension. Compaction preserves
its current adapter and H10 mapping. Sixty-five comparisons exercise inherited
versus explicitly identical routes for all five allowed models. They test
identity/bounds, not model quality; no model-name or synthetic-output ranking
promotes specialized defaults. F0/consuming owners still owe suitability evidence.

## Evidence and outstanding work

Receipts are under `C:/Renulus/scratch/oc-h02-h08/configuration`. Twelve sequential
red/minimal-green cycles are preserved as red01..red12 and green01..green12 XML:
missing authority, interrupted activation, disabled override, pinned/revoked
policy, pooled accounting, probe epoch race, reserved/final guard, retry cap,
child settlement, effective-health admission, dotted model revocation and late
receipt reconciliation. Red06/red07/red10/red11 reproduce assertion/behavior
failures in existing implementation; no artificial fail hooks were added.
`coverage01.xml` records 96 passes before the last three review repairs. Final
runtime counts and source hashes are appended after execution.

The migration contains harness_configuration_versions/health/pointer/grants/
revocations/runs/attempts. Immutable version update/delete triggers and FKs
protect pinned input. Parent owns relation/export/restore treatment; complete
H18 paired-store recovery is not established. Parent must assemble configuration
startup, bind all H03 HTTP/WS/native/AI-SDK dispatch gates and publication guards,
and implement actual Settings requested/effective/failed/pinned-version behavior.
H04 remains unaccepted until that connected routing and UI evidence lands.
H21 must supply accepted volatile accounting before temporary operations adopt
this durable ledger. Actual account, SDK routing, native installation, UI and
model-quality acceptance were not exercised in this lane.

## Initial preparation verification and review

Executed against final implementation/test bytes:

```powershell
& 'C:/Renulus/dev/python/Scripts/python.exe' -B -m pytest tests/runtime -q --basetemp=C:/Renulus/scratch/oc-h02-h08/configuration/runtime01-tmp --junitxml=C:/Renulus/scratch/oc-h02-h08/configuration/runtime01.xml
```

Result: **306 passed, 14 skipped, four failures**, 197.94 seconds. All **99 H04
configuration cases passed** within that run. runtime01.xml/runtime01.log preserve
the outcomes. SDK tests need reviewed Node/cohort opt-in and were skipped; this
policy slice did not require a Node junction or claim new SDK execution.
No full repository, UI or packaged-account acceptance is claimed.

The four failures match unchanged provider sources and the foundation handoff's
H03 catalogue/access/capability family:

- test_images_context.py::test_inference_auth_failure_invalidates_catalogue_without_image_claim
- test_provider_acceptance.py::test_sdk_stream_machine_failure_is_redacted_actionable_and_has_no_retry[invalid_api_key-authentication_required-error]
- test_provider_acceptance.py::test_sdk_stream_machine_failure_is_redacted_actionable_and_has_no_retry[invalid_api_key-authentication_required-response.failed]
- test_provider_acceptance.py::test_transient_refresh_failure_preserves_rotating_token_and_is_retryable

No provider sources/tests were changed to hide these failures. The runtime suite
is reported failed; the provider worker owns their resolution. Python syntax
checks pass for both changed Python files. Scoped link/receipt/source validation
and git diff --check pass. receipt.json records final owned-file SHA-256 values,
XML counts, the twelve red/green cycles and baseline provider-source equality.

Final standards/spec self-review used the code-review checklist against baseline
74e3424 and the directed H04 scope, without subagents. Standards: owned paths,
canonical Database, immutable inputs, safe outcomes/references and public-seam
tests; no remaining material finding. Spec: bounded role/activation/epoch/permit
behavior is covered; no remaining material defect in this preparation slice.
The parent retains independent review and actual connected acceptance. H03/UI,
canonical restore and H21 dependencies above remain open.

## Purpose-budget correction

The independent SPEC repro was confirmed through the public authority with real
canonical SQLite: title limit 1 previously admitted two distinct reservations,
and summary limit 0 admitted one under Explain's foreground allowance of 12.
The correction uses each role's exact configured/default dispatch limit jointly
with the root allowance. Counts include every reservation, across parent and
children and every terminal state; cancellation, reopen, retries and tool
continuations never refund a debit. New unrelated roots have separate allowances.

004 adds only nullable `dispatch_purpose TEXT` to attempts. New reservations
always store it. Retries inherit the prior same-step permit even when labelled
transport-fallback, recovery or summary-repair. Explicit `continuation_of` must
identify a confirmed permit from the same owning run, whose config, connection
and route remain pinned. It is valid only for a new tool-continuation step and
cannot accompany retry_of. Omission is compatible only when all prior attempts
on the owning run have its purpose and the latest is confirmed. An auxiliary
continuation requires exact identity. Continuations start at retry number zero;
subsequent retries consume another debit and the configured retry allowance.

Historical null purposes are projected without rewriting applied rows or 002.
Ordinary/auxiliary attempts derive from their original kind and owning run;
same-step retries inherit that original purpose. A historical continuation after
mixed purposes is ambiguous and stays null. Any ambiguous ledger in a root
blocks new reservations; ambiguous permits cannot dispatch or authorize
permit-derived publication. Final dispatch checks the original ledger prefix,
including the reserved permit, so an old excess reservation cannot bypass the
new limit while an earlier reservation within the limit can still proceed.
Final dispatch never adds another debit, and output can only narrow.

Exact changed public signatures (all other route/permit signatures above remain):

```python
ConfigurationAuthority.admit(
    run_id: str, step_id: str, *, payload_hash: str, request_kind: str,
    connection: ConnectionReference, limits: RouteLimits, input_tokens: int,
    required_capabilities: tuple[str, ...] = (), retry_of: str | None = None,
    continuation_of: str | None = None,
) -> dict

ConfigurationAuthority.require_current(
    run_id: str, *, required_capabilities: tuple[str, ...] = (),
    connection: ConnectionReference | None = None,
    permit_id: str | None = None, conn=None,
) -> dict
```

The receipt's `purpose` remains the owning run purpose; `dispatch_purpose` is
the stable outbound purpose. Parent transport must retain permit identity across
tool results and pass continuation_of for auxiliary continuation. At publication,
parent passes `permit_id` and its existing canonical transaction to require_current.
That guard checks current purpose revocations and the permit's required capability
union; it does not prove transport success or replace domain settlement, outcome
and publication checks. require_current without permit_id guards only the run.
mark_dispatched uses the same inherited-purpose guard and exact route budget.

Public errors include dispatch_budget_exhausted, dispatch_purpose_unavailable,
continuation_identity_required, continuation_authority_mismatch,
continuation_not_confirmed, invalid_continuation and permit_authority_mismatch.
Inspection and a confirmed receipt replay have dispatch_allowed false.

Five bounded red/green cycles are retained under the existing synthetic receipt
root. Selections and observed outcomes are:

| Receipt suffix | Exact pytest -k selection | Red | Green |
| --- | --- | --- | --- |
| 01 | auxiliary_role_budget_applies | 2 failed: title 1 and summary 0 admitted excess | 2 passed |
| 02 | red: relabelled_retry; green: auxiliary_role_budget_applies or relabelled_retry | 2 failed: relabelled title retry bypassed the cap | 4 passed |
| 03 | upgrade_confirmed | 1 failed: nested write transaction locked SQLite | 1 passed |
| 04 | inherited_auxiliary_purpose_revocation | 2 failed: publication guard lacked permit identity | 2 passed |
| 05 | upgrade_rejects_historical_reservations | 2 failed: final dispatch admitted old excess reservations | 2 passed |

Files are `purpose-budget-red01.xml` .. `purpose-budget-red05.xml` and matching
green XML. `purpose-budget-policy.xml` adds 14 passing cases for exact
title/summary continuation, joint continuation/retry accounting, parent/sibling
pooling, cancellation/reopen, cross-run/config/route rejection, unconfirmed source
rejection and conservative historical upgrade. Upgrade fixtures execute the
previous public authority from immutable Git blob
`fe17e466f6de7b5392a06eea272a29b4509539af` (lane 22c52fa1 and integrated
a85e1ee0); the test checkout needs that history object. Assertions use only the
public authority, without private table queries.

The existing 65 role comparisons retain synthetic catalogue and varied-domain
coverage. The additional 23 cases exercise configuration policy and real SQLite,
not actual host activation, provider transport, model suitability, UI behavior or
H21 volatile storage. No H03/UI acceptance is inferred from literal health or
restart flags. Parent still owns canonical export/restore treatment, shared
startup/Services and actual transport/publication/UI binding. H04 acceptance stays
open until the connected H03/H04 evidence lands.

Final dedicated verification after the budget guard consolidation and historical
fixture identity correction:

```powershell
& 'C:/Renulus/dev/python/Scripts/python.exe' -B -m pytest tests/runtime/test_harness_configuration.py -q -p no:cacheprovider --basetemp=C:/Renulus/scratch/oc-h02-h08/configuration/purpose-budget-final02-tmp --junitxml=C:/Renulus/scratch/oc-h02-h08/configuration/purpose-budget-final02.xml
```

Result: **122 passed, zero failed/errors/skipped, 21.87 seconds**.
purpose-budget-final02.xml and purpose-budget-final02.log retain this exact run.
The preceding purpose-budget-final.xml has 122 passes before the historical
fixture switched from a lane commit lookup to the identical integrated Git blob.
No broader runtime, UI, host or provider checks were rerun for this correction.
Python syntax and git diff --check pass. purpose-budget-receipt.json records the
final four owned source hashes, unchanged applied-002 hash, exact command, case
names and red/green XML counts; receipt counts are not added across overlaps.

Standards self-review of this diff: canonical Database migrations, dedicated
ownership and public behavior assertions preserved; repeated reservation/final
budget logic consolidated into one private guard. Spec self-review: configured
purpose and root limits, inherited identity, revocations, no refunds and legacy
fail-closed behavior verified. No remaining material finding in this fix; actual
connected H03/H04 acceptance and parent integration dependencies remain open.

## Canonical activation snapshot and admission seal

2026-10-11. This bounded extension changes only the authority, its dedicated
tests and this document, from lane baseline
`c0705f19a26f41ece831cb51119a8f95ca967130`. Existing UI/API work and applied
002/004 migrations are preserved. No new database, schema or relations are needed.

Exact added public authority signatures:

```python
ConfigurationAuthority.activation_snapshot(self) -> dict

ConfigurationAuthority.close_admission(
    self, *, expected_effective: str | None, requested_version: str,
    grant_epoch: int,
) -> dict
```

activation_snapshot returns one coherent canonical transaction's requested,
effective, previous, activating, failed and failure_code pointers, admission_open,
grant_epoch, sorted revoked identities, configuration, requested_configuration
and pinned_runs. Both configurations are hash-verified frozen ConfigurationSpec
objects, or None for an absent pointer. This is a trusted assembly interface;
full specifications contain protected connection references and internal inputs.
The Settings API's existing projection remains the public renderer contract.
Pins are sorted by run_id and contain exactly run_id, purpose and version.

Pins include every root/child not explicitly settled, across all versions.
Confirmed, failed, uncertain and cancelled_before_send permit outcomes do not
release a still-active owning run: its policy ownership remains until the parent
observes actual native/domain finalizers and calls settle_run. Reserved/dispatched
attempts also pin their owning run and root independently of the run-state test.
The query conservatively pins null/unknown run states and attempt states outside
the existing terminal allowlist. Current schema constraints prohibit unknown
states; no private table mutation is used to fabricate them in tests. An uncertain
permit on an explicitly settled run is a retained receipt, not permission to replay.

close_admission requires the exact expected effective and requested version,
the current integer grant epoch and no activation already in progress. Missing
or mismatched requested/effective identity yields activation_conflict; malformed
or stale epochs yield candidate_authority_stale. requested_version must be a
64-character lowercase hexadecimal hash; boolean/float epochs are rejected.
After these checks, any pin returns harness_configuration_busy, HTTP409,
retryable true, with requested/effective/failed/admission and all other canonical
state unchanged. Success changes only admission_open to false and returns the
coherent sealed snapshot. Repeating the same seal is safe while its CAS inputs
remain current; no candidate health or pointer activation is granted.

Both reads and the seal use existing Database transactions. The CAS, pin check
and single-field update serialize with another authority's root admission,
staging and revocation on the same canonical database. No canonical transaction
crosses IPC. The parent still owns the root-only ingress lease, actual native
and domain settlement, isolated candidate/final registry health and managed
replacement. reconcile_restart, lifecycle/Services/controller/server and
migrations were not changed. A policy snapshot or successful seal does not
prove a stopped engine or completed H03/H04 activation.

Five sequential public red/minimal-green cycles are retained under
`C:/Renulus/scratch/oc-h02-h08/configuration`:

| Receipt pair | Public behavior | Red | Green |
| --- | --- | --- | --- |
| admission-red02 / green02 | Coherent policy/spec/root/child snapshot | 1 failed: missing method | 1 passed |
| admission-red03 / green03 | Durable seal preserving failed/requested pointers | 1 failed: missing method | 1 passed |
| admission-red04 / green04 | Busy ownership survives reserved and confirmed receipts | 1 failed: seal accepted busy owner | 1 passed |
| admission-red05 / green05 | Effective/requested/epoch/in-progress CAS | 4 failed: stale seal accepted | 4 passed |
| admission-red06 / green06 | Exact epoch type and explicit staged request | 3 failed: invalid CAS accepted | 3 passed |

admission-red01 is a retained environment error: the G: basetemp parent directory
was missing. It is not behavioral red evidence. After creating that owned
synthetic directory, red02 reproduced the missing public method.
admission-contract07 records 28 passing new cases: bootstrap/pending reopen,
all six permit states for both root and child owners, prior-version pins after
the current owner settles, independent-authority races and coherent concurrent
staging/revocation. Tests use public authority methods and real canonical SQLite.
Existing role fixtures remain synthetic and imply no model-quality ranking.

Final dedicated verification command (assigned lane checkout):

```powershell
& 'C:/Renulus/dev/python/Scripts/python.exe' -B -m pytest tests/runtime/test_harness_configuration.py -q -p no:cacheprovider --basetemp='G:/Renulus-agent-scratch/oc-h02-h08/configuration/admission-final08-tmp' --junitxml='C:/Renulus/scratch/oc-h02-h08/configuration/admission-final08.xml'
```

Result: **150 passed, zero failed/errors/skipped, 16.72 seconds**. This includes
the 122 existing role/permit cases and 28 added activation/seal cases. Matching
XML/log receipts are admission-final08.xml and admission-final08.log. Python
syntax checks for both leased Python files and git diff --check pass.
Self-review strengthened the confirmed-owner busy assertion to compare with
the pre-seal status. The changed case passed on final test bytes in
admission-review09.xml/log: one pass, 1.53 seconds. Its count overlaps the
150-case run and is not added to it.
No broader suite, providers, native/UI flows or descendants were run.
admission-receipt.json records owned hashes, unchanged migrations, exact commands
and retained red/green outcomes; overlapping selections are not added together.
Standards self-review: dedicated ownership, canonical Database and public seam
assertions preserved; configuration decoding and coherent inspection are shared.
Spec self-review: CAS, busy preservation, durable pins and conservative state
handling implemented. No remaining material finding in this bounded slice.
Parent independent review and connected activation acceptance remain open.

## H07 supplied-transaction child admission prerequisite — 2026-10-11

Bounded Configuration lane based on `67321f02d36ba844e6d3bd7b4e306695b9f1ba65`.
The parent has closed H02–H05 local acceptance. This slice supplies canonical
child policy admission and accounting for H07; it does not claim actual native
child execution, Stop, recovery or publication acceptance. No DDL changed.

Exact added public signature:

```python
ConfigurationAuthority.begin_child_in(
    self, conn, run_id: str, parent_id: str, purpose: str, *,
    capability_scope: tuple[str, ...] = (), operation_model: str | None = None,
) -> dict
```

The supplied connection must own an active transaction on this Authority's
canonical Database. Closed, ended or inactive connections deny with
`configuration_transaction_required`; an active foreign database connection
denies with `configuration_connection_mismatch`, even with identical configuration.
Validation is shared with `begin_run_in`. The method opens no connection or
nested transaction. The caller owns commit/rollback, and the returned projection
observes uncommitted parent and child admissions through the supplied connection.
The existing `begin_child` opens its normal Database transaction and delegates.

Admission requires the parent to remain active and its ancestor chain to retain
current purpose/model/connection authority. Child purpose and selected model
revocations deny before insertion. Requested capability scope cannot exceed the
parent's current effective capabilities; subsequent revocations continue to narrow
both existing and new children. Role/model/output/dispatch settings come from the
parent's hash-verified immutable configuration, not a newer requested candidate.
Configured evidence-review settings and existing override/disabled-role precedence
are preserved. Depth and concurrency checks include uncommitted children in the
same transaction. Admission remains policy ownership; parent ingress, native
construction, cancellation and journal settlement retain their separate owners.

Public `run`, `begin_run[_in]` and `begin_child[_in]` projections now also expose
`own_spent_dispatches`: the count of all durable attempts belonging to that run.
`spent_dispatches` remains the shared root-family count. Both include reserved,
dispatched, confirmed, failed, uncertain and cancelled-before-send receipts,
survive reopen and never refund allowance. The new own count lets a child
recovery guard distinguish its attempts from parent/sibling debits; it does not
grant replay permission. Existing root and pooled-purpose dispatch ceilings remain
enforced independently. Unknown connection/token-count evidence remains external.

Dedicated public red/green receipts in
`G:/Renulus-agent-scratch/oc-h02-h08/configuration-children/receipts/`:

| Receipt pair | Red | Green |
| --- | --- | --- |
| admission-red01 / admission-green01 | Missing `begin_child_in`, 1 failed | Parent/child atomic admission, 1 passed |
| own-red02 / own-green02 | Missing own-count projection, 1 failed | All six attempt states, 6 passed |
| revocation-red03 / revocation-green03 | Revoked parent purpose still admitted a child, 1 failed | Parent/child purpose, model and connection revocations, 5 passed |

Final `children-final04.xml` / `.txt`: **28 passed, zero failures/errors/skips,
4.81 seconds**. These are real canonical SQLite/public Authority tests with
synthetic health/restart setup. No provider, registry, native SDK, CPU engine,
host/Services or parent schema is exercised. The existing 122/150-case suite was
not repeated. Exact focused command/environment and hashes are in the receipt
directory's `handoff.json`; overlapping red/green selections are not added to
the final case count.
