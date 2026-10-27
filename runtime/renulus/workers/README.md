# BF00 boundary and preparatory BF02 selected-engine slice

This bounded implementation supplies worker staging, extraction/chunking,
embeddings, Library derived operations and Mem0 learner-memory operations.
The BF02 engine slice is preparatory against BF00's worker boundary; it does not
complete BF02 before BF01's connected native dispatch/plugin integration.
Production activation, canonical ownership transfer and full profile/package
acceptance are external. The protected broker is connected through authenticated
typed commands below; live account and native-host final-admission acceptance
remain separate.

## Contract and launch API

`runtime/renulus/worker_contracts.py` is the single contract source: strict,
frozen Pydantic command/reply models, with generated
`packages/contracts/worker.schema.json` and `packages/contracts/worker.ts`.
Shared primitives and identity/revision/output types live in
`workers/contract_base.py` and are reexported unchanged by `worker_contracts`.
The independent base prevents broker model/closed-command union import cycles.
Generate with `python -B -m renulus.workers.generate` and `PYTHONPATH=runtime`.
The schema root validates wire frames; `$defs.LaunchConfig` validates launch
configuration. The generated TS types need runtime validation. Defaults in
Ready/Reply are serialized explicitly; a host must require the protocol, kind,
identity, revision and settlement fields, rather than relying on optional TS
properties or JSON Schema default annotations to materialize them.

Launch the pinned Python with `-B -m renulus.workers.main --config ABSOLUTE_JSON`.
Use inherited stdin/stdout pipes and a hidden child. There is no network listener.
The host owns the immutable configuration file. Its fields are:

- `protocol: "renulus-worker/1"`.
- `identity`: `profile_id`, `domain_store_id`, `runtime_store_id`,
  `authority_epoch`, `process_generation`.
- `revisions`: `configuration`, `grant`, `context`, `deletion`, `cancellation`.
- `retention`: `saved` or `temporary`; one mode for the entire process.
- `launch_token_sha256`: SHA-256 of a random per-launch token. The token itself
  occurs only in the first stdin frame, never arguments, environment or logs.
- Optional `capacity`: generated `Capacity` defaults apply.
- Optional `helpers`: absolute `helpers_root`, `cache_root`, `source_root`.
  The source root supplies the existing reviewed packaging helper manifest.
  Cache and immutable roots must not overlap or contain symlinks/junctions.
- Optional `derived` (default `null`, may be omitted): absolute `root`, lexical
  `namespace` (letters/digits/underscore/hyphen, no dots), and required complete
  `library_tombstones` / `memory_tombstones` arrays (up to 4096 IDs each). These
  are host-owned derived paths, disjoint from every helper/cache/source root.
  No command can select a filesystem path. Use an isolated synthetic namespace
  for preparation; this is not a production-profile selector. Missing `derived`
  leaves the original document/embedding/artifact commands usable.
- Optional `broker` (default `null`): absolute protected `profile_root`, absolute
  `state_root` within that profile, and optional `bounds: BrokerBounds` (defaults:
  1 MiB request, 1 MiB response, 120 seconds, 4096 permits). These are immutable
  host launch inputs, never command/model data. No synthetic endpoint override
  exists in this schema. Missing broker configuration returns
  `broker_unavailable`. Construction/startup does not open credentials.

The first stdin frame is `Hello`: exact protocol, `kind: "hello"`,
`launch_token`, `expected_launcher_pid`, exact `identity`, and requested
`capacity`. Every capacity is negotiated downward; chunk size is additionally
reduced to fit the negotiated frame. Unsupported versions/malformed frames,
duplicate JSON keys, NaN/infinity, unknown fields and unauthenticated hello
terminate with exit code 2, without reflecting input.

`Ready` includes the exact process identity, actual `pid`, immediate `parent_pid`,
negotiated capacity, supported/unavailable command names and `process` attestation:

- `launcher_pid` equals the host's actual spawn result.
- `actual_pid` equals `Ready.pid`.
- `launcher_creation_filetime` and `actual_creation_filetime` are decimal strings
  preserving Windows FILETIME precision.
- `ancestry_depth` is 0 for direct execution or at most 16 for a descendant.

This attestation is computed after token authentication using live Windows
OpenProcess/GetProcessTimes/NtQueryInformationProcess handles. It walks only
the actual process's ancestors, holds handles through verification, checks
creation ordering and refuses unknown/terminated/cyclic/reused ancestry. It
does not trust the claimed PID or merely echo `getppid()`. The pinned Windows
venv launcher normally has depth 1. The host must check the attested launcher,
actual PID and full identity against this particular launch; it must retain
the actual process identity for death/settlement handling.

Helper dependency imports are warmed on the main thread before Ready. A missing
helper leaves the boundary usable, and engine calls return `helper_unavailable`.
The host should allow cold-import startup time. No model is created by warmup.
Warmup includes Lance/PyArrow and the existing telemetry-disabled Mem0 bootstrap.
`Ready` advertises protocol command support, not derived-store readiness. Each
derived operation acquires its native owner and applies the launch deletion
frontier before it can produce a successful result. The host must supply the
complete current frontier on every launch/recovery, before accepting readiness.

## Framing, command binding and capacities

Each frame is UTF-8 JSON followed by LF, at most 1 MiB including LF. Engine inputs
contain no arbitrary methods, SQL, paths, URLs, secrets or provider settings.
Protected transport plans contain only the exact product routes described below.
The command envelope matches section 5 of BACKEND_FINALISATION_SPEC: process
identity plus operation/attempt/request IDs, payload digest, all five revisions,
retention, closed dotted command, opaque `expected_revision`, typed `input`,
and `limits` (`result_page_bytes <= 262144`, `cpu_seconds <= 120`).

`payload_sha256` hashes the **exact input object as sent**, recursively sorted
keys, compact UTF-8 JSON, with no ASCII escaping and no whitespace. Input
schemas contain integers and booleans, never floating point. Do not inject
omitted optional defaults before hashing. The worker checks the whole process
identity, retention, revisions, digest and request replay before effects.
`expected_revision` remains a host canonical predicate; input/output artifact
revisions are checked here. Every reply binds the request's complete identity,
input digest, revisions and exact lease. The host retains the admitted envelope
and rechecks current authority before accepting output or canonical publication.

Default limits: 16 data admissions in flight, 64 queued, 8 reserved control reply
slots, 2 document tasks, 1 embedding task, 1 Library task, 1 Memory task,
1 transport task, 1 credential task,
128 artifacts, 128 MiB aggregate RAM
reservations, 64 MiB per artifact, and 4096 unique data requests per process.
Actual engine concurrency is bounded by its lane and total in-flight limit.
Data lifetime exhaustion cannot exhaust settlement/control admission. Control
replay history uses a bounded recent window; every mutation remains bound to
exact leases, monotonic revisions or immutable non-rebindable artifact handles.

The pipe reader and priority reply pump are independent of engine tasks.
Terminal replies are retained in bounded queues, with backpressure on a stalled
consumer. The host must keep draining stdout; reserved controls cannot make an
unread inherited pipe writable. Reverse inference uses reserved control capacity;
there is no progress stream. Native engine calls have a cooperative wall deadline
using the supplied CPU budget: late results are suppressed, and the lease is
retained until actual return. This is not hard preemption of Python/native code.

## Supported commands

### Artifact upload and reads

`artifact.upload` is an explicit, negotiated BF00 transfer command in addition
to the spec's `artifact.read`. Its input is `{artifact, offset, data_base64,
final}`. `artifact` is a host-minted immutable `ArtifactGrant`:

`artifact_handle`, positive `artifact_revision`, `artifact_sha256`, total `bytes`,
`expires_at_ms`, `rights` (`read`/`extract`/`chunk`), `permitted_ranges`
(`{offset,length}`), `reservation_id`, and `intent_id`.

Repeat the exact grant for each sequential chunk; decoded chunks are at most
256 KiB, or the negotiated lower bound. Offset must equal received length.
`final` must correspond exactly to the end. Final total/hash must match. The
`upload` result reports received bytes, completion and one returned credit.
Wait for this credit before sending another chunk for the same handle. Partial
upload reservations remain owned until explicit release/revoke/close.

`artifact.read` takes `{artifact_handle, artifact_revision, offset, length}`.
The `read` result includes an immutable artifact reference, offset,
`data_base64`, `next_cursor` and one credit. Reads clip to remaining bytes and
the smaller of chunk/page bounds. Rights, ranges, expiry and current revisions
are checked. Released handles are tombstoned for this process and never rebound.

All input and output bodies stay in RAM in both retention modes. There is no
native-file adoption or saved-file publication in this slice. Host reservations
and intent IDs are required before allocation; verifying their canonical
existence belongs to the authenticated host. Temporary input never spills.

### Selected engines

`embedding.embed`: `{texts, query, output}`. Up to 64 bounded strings are passed
to the existing `FastEmbedEngine`. The resulting JSON artifact has
`tag: "embeddings"`, model `BAAI/bge-small-en-v1.5`, dimensions 384 and vectors.

`document.extract`: `{artifact_handle, artifact_revision, offset, length,
format, title, output}`. Formats: txt/md/pdf/png/jpg/jpeg/tif/tiff. It reuses the
existing `DoclingExtractor`, HybridChunker and selected tokenizer. Staged JSON
has `tag: "document"` plus the existing Extracted fields (`document`,
`passages`, `ocr`, `status`), retaining locators. Saved text/PDF accept the
64 MiB envelope; temporary inputs and RAM images use the existing 10 MiB/
20-page byte-helper bounds. Saved larger images/Office/markup need later
connected adapters and are not implied by the supported format names.

`document.chunk`: `{artifact_handle, artifact_revision, offset, length, output}`.
Input must be a complete staged `document` JSON representation. It validates
DoclingDocument and reuses the existing `_chunk` seam, including original text
item spans. It returns another document artifact.

Each engine command's host-minted `output` is an `OutputGrant`:
`artifact_handle`, positive `artifact_revision`, `max_bytes`, `expires_at_ms`,
`reservation_id`, `intent_id`. Reserve this capacity before engine admission.
The terminal `artifact` result supplies SHA-256, length, revision, engine pin,
nullable pages and cursor. Successful output remains retained until release.
`committed_reference` means RAM staging, with no canonical publication.

The adapter uses immutable paths and a read-only minimal helpers registry with
the existing OfflineAssets, HelperAssets and engine classes. It constructs no
Services, repositories or Database. Dependency versions are checked; helper
files are hash-validated against the existing reviewed manifest. Owned import
temp/cache/native-home paths prevent ambient profile fallback. Remote socket
connections are refused (Windows loopback self-pipe primitives remain possible),
and all selected engines use explicit offline/CPU configuration. Native stdout,
stderr and Python logs are discarded before helper import. No payload or
dependency exception is reflected in replies.

### Settlement controls

`worker.settle` has `action: query/cancel/revoke/release/close/generation`, plus only fields
applicable to that action. `target`, when needed, contains the original full
`identity`, `request_sha256`, and `worker_lease` from `accepted_pending`.

- `query`: optional exact target; reports active count/closing and exact target
  settlement. Without target it reports the worker snapshot.
- `cancel`: required exact target. Queued work settles immediately. Running
  work stays `accepted_pending`/`pending` until native return and cleanup.
- `revoke`: required full `revisions`, each monotonic. Cancels old work and
  retires all old artifacts. This control uses the old envelope revisions;
  subsequent commands use the new revisions.
- `release`: required `artifact_handle`; retires that artifact, retaining any
  pins/reservation until actual users settle.
- `close`: closes admission, cancels/drains tasks and retires artifacts. Close
  stdin after observing actual settlement to end the process normally.
- `generation`: exact `target` and a `generation` settlement, as described below.
  It acknowledges delivery to the still-owned Memory job; it does not itself
  settle that job. This control remains available after the data lifetime budget.

Control replies are one-shot snapshots. A pending control acknowledgement does
not create another engine job or promise a later terminal for that control
request. Continue observing the **original** engine request or issue a fresh
settlement query; never resend execution. Completed lease history retains only
identity/digest/lease metadata, without command text or document payload.

Engine work emits accepted_pending then exactly one terminal on the same lease.
Successful staging uses committed_reference. Cancellation, fenced late results,
deadlines and engine failures that leave no staged result use cancelled_settled;
the latter carry a tagged error code. Rejections before effects use
rejected_before_admission. After broken pipes/process death the host records
uncertain_after_disconnect for outstanding leases; it cannot infer settlement
from an ACK, timeout or missing reply. EOF here means death/disconnect of the
owning host, not a saved renderer observer detach. The host owns that distinction
and the temporary Save/disconnect race.

### Library derived operations

All eight Library/Memory commands require an `output: OutputGrant` and return an
ordinary `ArtifactResult`. Read the bounded JSON body with `artifact.read`.
The body tags below describe staging/candidates, never canonical publication.

- `library.stage`: `artifact_handle`, `artifact_revision`, `offset`, `length`,
  `document_id`, `revision_id`, `output`. The pinned **read** grant covers a JSON
  body `{passages:[{passage_id,text}]}` (1–256 passages). Each passage must fit the
  selected tokenizer's 480-token chunk budget. The existing `FastEmbedEngine`
  produces 384-dimensional BGE-small-en-v1.5 vectors, and the existing
  `knowledge.engines.LanceIndex.stage` creates the native hybrid/FTS index.
  A repeat of identical revision/document/passage/text staging is idempotent;
  changing that immutable revision is refused. Output: `{tag:"library_staged",
  document_id,revision_id,passage_ids,input_sha256,eligible:false}`.
- `library.query`: `query`, `allowed_revision_ids` (0–256), `limit` (1–30),
  `output`. Calls the selected Lance hybrid/RRF search with its **native
  revision prefilter**, excluding tombstones before top-k. No allowed revisions
  returns no rows. Output `{tag:"library_candidates",rows:[{passage_id,
  revision_id,document_id,text}]}`. Vectors/native builders do not escape.
- `library.remove`: `revision_ids` (0–256), `output`. Applies irreversible
  process-lifetime tombstones before deleting the exact revisions.
- `library.maintain`: same fields plus required `optimize:bool`. Uses the existing
  owned `LanceIndex.optimize` seam; no unverified-file deletion. Both outputs:
  `{tag:"library_maintained",removed_revision_ids,tombstones_applied:true}`.

Library commands are serialized through one lane. Lance's existing exact
Windows `NativeOwnership` path/token fence is retained through real native
close. No native handle crosses a job or its staging reply. Tombstones are also
applied on reopen before querying. The host supplies a complete frontier at
launch and current eligibility on each read. A late/stale stage cannot create
canonical eligibility. Temporary Lance commands are explicitly refused because
the selected Lance adapter is disk-backed.

### Mem0/local Qdrant derived operations

The adapter reuses `memory.engine.Mem0Index`, its attributed Hermes `OSSBackend`,
`OfflineEmbedding`, and local Qdrant. Pinned versions remain mem0ai 2.2.1,
qdrant-client 1.19.1 and FastEmbed 0.8.1. It constructs only the minimal immutable
paths/helpers container required by those existing engines: no `Services`,
canonical `Database`, repository or provider instance. Mem0's own derived history
is distinct from canonical storage and is purged through its existing adapter.

- `memory.reconcile`: read-granted JSON artifact range and `output`, like chunk
  input. Body `{records:[{id,revision,text,scope,topic_id,kind}]}` (0–128).
  `revision` is a positive integer, text is at most 2000 characters, scope is
  study/library/generated-practice/reviewed-assessment; topic_id is nullable;
  kinds match existing learner facts. Reuses `Mem0Index.add` with `infer:false`.
  Identical existing ID/revision/text/metadata reuses its engine ID; conflicting
  immutable data is refused. Previous usable vectors survive new staging and failures.
  Output `{tag:"memory_reconciled",references:[{canonical_id,
  canonical_revision,engine_id}],eligible:false}`. The host atomically accepts
  the current mapping and retires obsolete support; staging does not do so.
- `memory.recall`: `query`, `accepted` (0–256 exact triples from the host's
  currently accepted/support-valid canonical mapping), `limit` (1–30), `output`.
  Hermes/Mem0 searches with canonical ID/revision filters before top-k, then
  the adapter checks the exact engine ID/revision triple before returning text.
  Unaccepted candidate IDs, wrong revisions and tombstoned facts cannot pass.
  Output `{tag:"memory_candidates",rows:[{engine_id,canonical_id,
  canonical_revision,text}]}`. Empty acceptance returns no rows.
- `memory.purge`: `canonical_ids` (0–256), `output`. Tombstones first, deletes
  **all** matching engine revisions with the Hermes delete adapter in bounded
  pages, then purges Mem0 history/messages before readiness. Output
  `{tag:"memory_purged",removed,tombstones_applied:true}`.

One dedicated Memory executor thread owns recall/reconcile/purge/extract through
actual return, Qdrant/history close and lease release. Saved Memory uses the
existing exact `NativeOwnership` fence for its derived namespace in addition to
Qdrant's local lock. Failed native closes keep their thread/owner pending for
retry; uncertain constructors retain their exact owner until process death.
The host must verify actual death before resolving those uncertain leases.
Other lanes and settlement controls stay independent. Correction/deletion and
transitive support acceptance remain canonical-host duties: every recall must
resolve fresh accepted triples, never reuse a prior grant after invalidation.
Persistent recall/reconcile/purge are refused for temporary retention.

### Memory extraction and reverse dispatch

`memory.extract` takes a read-granted UTF-8 artifact range (nonempty, at most
32768 characters), `output`, and required immutable `capture_plan`:
`{plan_id,evidence_receipt,support_sha256,source_sha256,expires_at_ms,max_calls:1}`.
The host mints this **after** admitting eligible committed evidence and its
support snapshot; the worker checks exact source bytes against source_sha256.
No provider name, route, credential, URL or account is accepted in this plan.

Extraction creates a fresh `Mem0Index(transient=True)` with in-memory Qdrant and
SQLite history, retaining Hermes/Mem0's actual `infer:true` extraction. It uses
the existing ApprovedLLM capture-binding seam. Its only inference bridge is a
reverse frame on inherited stdout:

```text
{protocol:"renulus-worker/1",kind:"generation_request",action:"generate",
 target:{identity,request_sha256,worker_lease},revisions,retention,capture_plan,
 callback_id,generation_sha256,messages:[{role,content}]}
```

`generation_sha256` is `payload_digest` of this exact serialized request object
with `generation_sha256`, `callback_id`, `action` omitted. All other fields,
including exact target, revisions, retention, capture plan and Mem0 prompts, are
bound. The host validates this request against its retained admission and
current dispatch authority, then uses native dispatch. It must not infer authority
from the echoed plan or let the worker choose a route. At most one call is made.
Oversized generated prompts fail before callback publication.

Deliver actual host-generation settlement with a new ordinary command envelope:

```text
command:"worker.settle",input:{action:"generation",target,
 generation:{callback_id,plan_id,generation_sha256,
             status:"completed"|"cancelled"|"failed",output:string|null}}
```

Use the **current** envelope revisions, including after revoke, and the exact
original target/callback binding. `completed` requires output; the other statuses
require null. Output follows the existing Mem0 capture format
`{"memory":[{"text":"..."}]}`, validated by ApprovedLLM (up to 12 facts, 2000
characters each, 16000-character response). It is not a provider fallback.
Wrong binding, replay or an already-settled callback is refused. Terminal
Memory output is `{tag:"memory_extracted",facts:[string],capture_plan,
eligible:false}` in RAM. Only a host canonical transaction can accept facts.

Stop, revoke, deadline or plan expiry sends `action:"cancel"` on the same reverse
binding, with `messages:[]` and the original generation digest. Generation has
the earlier of the job wall deadline, plan expiry and existing ApprovedLLM timeout.
The worker keeps the Memory thread, lane and artifacts until **actual** host
generation settlement and native cleanup; no finite timeout proves settlement.
The host must continue draining both directions and eventually report actual
closure, or verify worker/transport death and preserve uncertainty. Host EOF
during generation yields `uncertain_after_disconnect`, not cancelled-settled.
Extraction is RAM-only in saved and temporary modes; selected helper/cache/import
metadata can exist on disk, while prompts, facts, transient graph and artifacts
cannot. Temporary extraction never creates its derived namespace directory.

## Protected transport and direct Settings commands

`transport.execute` takes the **exact** `broker_models.TransportPlan` as `input`,
after the native host's final admission/debit commit. The host serializes the
request once, supplies its one-use permit/admission receipt, complete worker
identity/revisions/retention, immutable native manifest/registry hashes, exact
route/credential reference+revision, body/envelope digests and lengths, output
token cap, expiry, reserved `OutputGrant` and `NativeRequest`. Header arrays on
the wire become the broker's strict immutable tuples. This worker never chooses
a route/model, creates a permit, admits usage or performs automatic refresh.

The command/schema accepts only `https://api.openai.com/v1/responses` and
`https://opencode.ai/zen/go/v1/chat/completions`, with the matching provider in
Python validation. The broker further enforces exact approved models/protocol,
headers, body/envelope digests and native wire shape. Synthetic endpoints cannot
be supplied by launch/command JSON. The constructor's Python-only broker factory
is an isolated regression seam; product launch uses `ProtectedBroker`.

Plan identity, revisions and retention must exactly match the authenticated outer
envelope. The worker reserves and pins `plan.output` before starting the broker.
Each operation creates a broker scope bound to its own hashes and current
retention/revisions; all scopes use the one explicitly activated ProviderManager.
Process permit tombstones survive operation scope closure and are never evicted.
The host must retain durable admitted/uncertain debits across worker death.

The terminal result is the exact `TransportResult` (tag `transport`), containing
safe status/effect/settlement metadata and an optional `ArtifactResult`. The raw
bounded SSE response stays in private RAM, is copied into the already reserved
artifact, checked against the broker's exact length/hash/reference, then marked
complete only after final current/cancel/expiry checks. Read it using the normal
granted/paginated `artifact.read`. No raw response body, response header, bearer
token or native request is returned in transport reply metadata. The broker's
credential-echo checks precede artifact staging. Failure releases the reservation
only after actual broker/socket cleanup.

Direct authenticated Settings commands are **not model tools**:

- `credential.activate`: `{}`. Explicitly opens the protected account store and
  returns exact `CredentialResult` metadata. Repeating activation reuses the same
  manager; there is no account discovery/probe/refresh at worker startup.
- `credential.metadata`: `{}`. Requires previous explicit activation and returns
  protected references/revisions/configured/usable/selected metadata only.
- `credential.connect/refresh/forget`: `{provider_id:"codex"|"opencode-go"}`.
  These call the existing direct credential primitives without selecting a model
  or provider. They require prior activation and mandatory current checks.
- `credential.login-status/login-cancel`: `{provider_id:"codex",login_id}`.
  The explicit Codex login listener lives on one persistent owned credential
  event loop; status/cancel do not expose OAuth codes or tokens. Its authorization
  URL is direct Settings handoff metadata, not model output.

OpenCode Go connect requires a protected **Python host callback** `secret_reader`
installed in the Worker constructor. No command/launch JSON field accepts a
secret, secret path, callback selector or model-supplied credential. The inherited
stdio entrypoint has no such callback, so Go connect refuses
`credential_command_invalid` there until an explicitly protected native handoff
supplies one. A secret must never be added to the JSON command to bypass this.

`worker.settle` remains the control channel: exact-target cancel/query, monotonic
revoke, output release and close. Cancel signals both the job and broker; current
checks bind the job revision/deadline and pinned reservation during idle HTTP as
well as before send/return. Revoke propagates to every live broker scope and
retires artifacts; close closes admission/scopes and explicit login resources.
Pending controls keep the original transport lease/reservation until HTTP/native
cleanup actually returns. A broker result can report actual local `settled`
while its remote `effect` remains `uncertain`; the worker preserves this distinction.
EOF closes scopes, joins transport tasks, closes the shared manager/login loop
and discards RAM. A dead worker still requires host death/uncertainty accounting.

Remote network authority for the product entrypoint is separately scoped to the
protected broker transport; selected engine helpers remain offline. Synthetic
injected transport checks do not prove live subscription or package acceptance.
The current entrypoint's offline audit still **refuses credential-operation
remote HTTP**: Go account validation, explicit refresh/remote revoke and the
Codex callback's token exchange are not granted the transport permit's network
scope. Local activation/metadata and local Codex login start/status/cancel work;
connecting/refreshing real accounts remains held behind a protected credential
network handoff with its own current authority and complete callback lifetime.
Some existing credential routines may update protected local state before a
remote revoke failure; inspect their safe result metadata. Never broaden engine
network access or reuse a completed connect job's current callback to enable
long-lived OAuth exchange. Transport itself never invokes credential refresh.

## Explicitly unavailable

Native inspect/publish/dispose and the earlier `transport.send/cancel` scaffold
remain declared with empty inputs and return `unsupported_command` before
admission. Use `transport.execute` and `worker.settle` for the typed broker path.
Unknown names/fields fail the protocol closed. Windows native artifact
adoption/publication, disk-backed saved output, full application volatile-graph
proof, canonical handoff and packaging gates remain external to this slice.

## Verification commands

From `C:/Renulus/dev/repo` in PowerShell:

```powershell
$env:PYTHONPATH='runtime'
$env:RENULUS_WORKER_TEST_HELPERS='C:/Renulus/dev/helper-assets'
& C:/Renulus/dev/python/Scripts/python.exe -B -m renulus.workers.generate
& C:/Renulus/dev/python/Scripts/python.exe -B -m pytest tests/workers/test_contracts.py tests/workers/test_process.py tests/workers/test_settlement.py tests/workers/test_offline.py tests/workers/test_derived.py -q --basetemp C:/Renulus/scratch/bf02-worker-verification
& C:/Renulus/dev/python/Scripts/python.exe -B -m pytest tests/workers/test_broker_integration.py -q --basetemp C:/Renulus/scratch/bf01-worker-broker-integration
& C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe --check packages/contracts/worker.ts
```

The optional helper environment selects only pre-provisioned public artifacts;
without it, actual-engine tests skip explicitly. Tests use real inherited-stdio
processes and owned synthetic paths, never the doctor's profile/accounts. They
cover handshake/lineage, generated-schema parity, strict validation, chunked
transfer, stale/digest/replay/refusal, saturation/cancel/revoke/settlement,
actual selected text/PDF/image extraction, chunking, embeddings and no-payload
sentinels in the owned filesystem. Parent-owned Node client tests independently
establish the Node-to-worker connection.
The BF02 tests additionally use real LanceDB and Mem0/Hermes/local Qdrant,
revision prefilters, immutable staging, accepted-mapping recall, correction,
purge/reopen tombstones, native maintenance and synthetic inference responses over
the real reverse pipe. Cancel/revoke/deadline/EOF tests distinguish cancellation
from settlement; a dedicated-thread test checks lane ownership. Temporary capture
scans verify the synthetic payload never reaches disk. Synthetic generation is
a test fixture only. BF01/native dispatch integration and live account acceptance
are not claimed by these tests.

The broker-integration regressions cover real authenticated stdio refusal before
HTTP both before activation and with no connected account; product-only schema
and envelope binding; the actual broker with constructor-injected MockTransport;
exact request bytes/response artifact hashes; shared explicit activation and
permit tombstones across scopes; cancel/revoke/release/close held through delayed
HTTP cleanup; private RAM sentinels; host-only Go secret callback refusal/handoff;
and a synthetic local Codex login listener's status/cancellation on its owned loop.
They perform no provider inference or external account HTTP.
