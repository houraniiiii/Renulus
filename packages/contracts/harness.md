# Harness contracts — harness/1

H01 extends `design-c/1` by composition. The host integration owner consumes
these shapes; this module does not write or migrate either store.
The canonical domain schema remains **2**, including its existing schema-1
conversion. No existing domain object receives a replacement product ID.

## Paired-store field shape

The complete machine-readable example is
[`fixtures/harness/paired-store-prepared.json`](fixtures/harness/paired-store-prepared.json).
All fields in that example are required. Unknown fields are rejected.

| Field | Meaning |
| --- | --- |
| `contract_version` | Exactly `harness/1`. |
| `profile_id` | Stable owned profile identity, never a path. |
| `snapshot_generation` | Positive integer for one complete paired snapshot. |
| `cohort_source` | Exactly `4b6fea2875e4f2e3e8a8fee181803e54f7056845`. |
| `state` | `prepared` or `active`; activation requires both stores validated. |
| `domain_store` | Descriptor of the canonical schema-2 SQLite store. |
| `runtime_store` | Descriptor of the persistent OpenCode store. |

Both descriptors require `store_id`, `engine`, `schema_version`, `generation`,
`path`, and `validation`. Store IDs are stable, distinct identities. Both
`generation` values equal the manifest's `snapshot_generation`; these values
identify one compatible snapshot, not process starts or per-store revisions.
Paths are portable relative paths underneath the host-owned snapshot root.
`validation` is `pending` or `valid`. The trusted owner sets it only after
validating the actual store. Parsing a manifest does not establish that fact.

The domain engine is `renulus-sqlite`, with integer `schema_version: 2`.
The runtime engine is the object `{name: "opencode", version: "2.0.26",
source_commit: "4b6fea2875e4f2e3e8a8fee181803e54f7056845"}`.
Its `schema_version` is `source:4b6fea2875e4f2e3e8a8fee181803e54f7056845`.
This is a conservative source-keyed compatibility identity, not an invented
upstream SQLite `user_version`. A different source/schema requires an explicit
contract update after compatibility is verified. A published SDK with the same
package version is not an interchangeable cohort.

The store writer must settle writers, validate both actual stores, publish the
verified manifest last, and atomically select the complete generation. Model IDs,
credentials, process generations and absolute machine paths are not manifest
fields. Parent-owned integration supplies store validation and activation.

## Prepared profile initialization

`renulus.runtime.harness_profile.prepare_harness_profile(owned_root, *, profile_id,
domain_store_id, runtime_store_id, domain_path) -> PairedStoreManifest` accepts an
explicit absolute `Path` for the caller-owned profile root and a relative domain
store path. It initializes `state/harness/manifest.json` **before** SDK database
writes. The runtime path is `state/harness/opencode.sqlite`. Both validations are
`pending`, `state` is `prepared`, and the initial snapshot generation is `1`.
It does not open, validate, migrate or create a database.
The writer reserves `state` and the entire `state/harness` subtree from
`domain_path`, case-insensitively, including lease/ownership controls such as
`owner.json` and `ownership-guard`. It rejects aliases and ancestor conflicts
before writing. The generic paired-store contract does not impose this layout.

Publication stages and flushes complete JSON, then uses same-directory
create-if-absent publication. An identical prepared selection is reused without
rewriting its bytes. Any different selection, malformed/unsupported manifest or
active manifest is rejected unchanged. The filesystem must support atomic hard
link creation; unsupported publication fails without a replacing-write fallback.
This is prepared initialization only, not paired backup/restore acceptance or a
store ownership lease. A crash may leave an unselected staging file.

The IPC owner now calls the writer before child startup with explicit
`domain_store_id` and `domain_path` configuration. The parent Node host reads
the prepared file and requires the complete manifest matching its
profile/runtime identity and its explicit `{domainStoreId, domainPath}` options,
including the schema-2 domain descriptor, pinned cohort, expected runtime path,
initial snapshot generation and both pending validations, before SDK writes.
Partial profile/runtime identity checks are insufficient. Activation remains
separate; prepared initialization does not mark the profile active.

## IPC identity and outcomes

The transport protocol remains `renulus-harness/1`. Identity keys are exactly
`protocol`, `profile_id`, `store_id`, `generation`, `operation_id`, `attempt_id`,
and `request_id`. Here `store_id` identifies the runtime store and `generation`
is a fresh process-start identity. It is independent of snapshot generation.
The authenticated transport removes its token before contract validation.
`HarnessCommandOutcome` keeps these fields flat and adds `kind: "reply"`,
`outcome`, optional JSON `result`, and optional `error: {code, message?}`.
Except for a local `accepted_pending` observation, a reply requires a result or
structured error. Result payloads remain command-specific; errors require a
nonempty identifier code. Authentication and admission are transport duties.
Nested non-finite result numbers are rejected in dictionary and JSON input,
before serialization could silently turn them into `null`.

Reply outcome names are `rejected_before_admission`, `accepted_pending`,
`committed_reference`, `cancelled_settled`, and `uncertain_after_disconnect`.
Pending observation and uncertain disconnection never authorise redispatch.
A runtime result alone cannot establish a canonical domain commit.

## Saved conversation mappings

`HarnessEngineReference` requires `contract_version`, `profile_id`, runtime
`store_id`, the pinned `engine` object, and `session_id`. It contains no process
generation, so an engine session reference survives a host restart.
`SavedConversationMapping` contains `contract_version`, the existing typed
`conversation: {type, id}`, `retention: "saved"`, and `runtime` engine reference.
`learn_thread` and `case` retain their separate namespaces and original IDs.

`map_saved_conversation(conversation, reference, *, manifest)` accepts the
backend-resolved Design C `Conversation`, reuses `require_durable_conversation`,
and binds the reference to the active manifest's profile/runtime store and
engine. Temporary and deleted conversations are refused; saved archived
conversations are allowed. Parsing a mapping or supplying `retention: "saved"`
does not establish retention. The caller must resolve the current canonical
conversation in the selected profile; this pure module cannot do so.

## Public validation and JSON Schema

The Python models inherit Design C's frozen, extra-forbidden `Contract`, adding
strict validation. No changes to `design_c_contracts.py` are required.
`PairedStoreManifest.model_validate` validates a prepared or active shape.
`validate_paired_store_manifest(value, *, profile_id, domain_store_id,
runtime_store_id, snapshot_generation)` additionally requires an active manifest
matching the trusted caller's complete selection. It does not activate anything.
`validate_command_outcome(value, *, expected)` compares every reply identity
field to the caller's `HarnessCommandIdentity`; an old process or mismatched
operation/attempt/request cannot settle that command.

[`harness.schema.json`](harness.schema.json) is the checked Draft 2020-12 export
of `harness_json_schema()`. Its root validates `PairedStoreManifest`; `$defs`
also expose `HarnessEngineReference`, `SavedConversationMapping`,
`HarnessCommandIdentity`, and `HarnessCommandOutcome`. The examples and
[`manifest-rejections.json`](fixtures/harness/manifest-rejections.json) are
independent synthetic fixtures consumed by Python and JSON Schema validators.

JSON Schema checks required fields, supported engines/versions/schemas,
lexically relative portable paths (including Windows reserved device names),
and active/both-valid and terminal-reply conditions. Standard JSON Schema does
not compare arbitrary property values. A cross-language consumer **must also**:

- Compare both store generations to `snapshot_generation` and require distinct
  store IDs and disjoint paths using Windows case-insensitive comparison.
- Bind the profile, store IDs and generation to its trusted selection.
- Resolve filesystem paths beneath its owned root and reject redirection. The
  profile writer rejects existing symlink/junction redirections; it assumes the
  caller owns the root and protects it from concurrent hostile path replacement.
- Bind saved runtime references to the selected active runtime store and resolve
  saved retention locally; bind replies to every expected IPC identity field.

The prepared writer does not accept an active manifest as an initialization
request. The integration owner must still prove real store validation, leases,
writer settlement, atomic active selection and paired recovery. These contract
and writer tests establish none of those connected runtime behaviors.

## Bounded validation evidence

October 10, 2026: 102 checks passed across the complete new contract/profile
test files and the existing Design C typed-identity and retention checks.
The public scenarios were implemented one failing behavior then minimal code
per cycle. Synthetic filesystem state stayed in the dedicated foundation
contracts scratch lane. The competing-initializer check uses 16 callers;
the redirected-directory check exercised a real Windows junction.
Independent JSON examples were validated with Python and Draft 2020-12 JSON
Schema. Node compiled all 22 exported field patterns and confirmed rejection
of trailing line terminators. The checked schema matches the public exporter;
the owned Python files compile. These are contract/writer checks, without
providers, installed-app changes or a claim of full H01/restore acceptance.
The standards review found no actionable issue. The specification review's
non-finite-result finding was corrected through a failing public-contract test
and the final passing suite.

References:
[H01](../../docs/planning/opencode-v2/tickets/01-run-a-persistent-headless-opencode-conversation.md),
[S1](../../docs/planning/opencode-v2/specs/01-harness-control.md),
[IPC note](../../docs/implementation/opencode-foundations-ipc.md).
