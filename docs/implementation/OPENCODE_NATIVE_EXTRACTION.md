# Native committed-answer extraction integration

October 11, 2026. This is the bounded H05 integration contract. Migrated
automatic capture remains disabled. It does not grant deployment evidence or
matching-account acceptance.

The installed, pinned Mem0 2.2.1 synchronous disposable capture path
(`mem0/memory/main.py`, `_add_to_vector_store`, lines 881–1045) makes one LLM
extraction call, then embeds facts. Renulus retains that engine, ApprovedLLM's
JSON/fact bounds, the outbox, lineage checks and actual executor leases.

Memory binds one local factory before its worker starts. A native job attempt
supplies only its immutable job ID, attempt, fingerprint, scope JSON, project
and existing committed-evidence publication pin. The factory prepares lifecycle
callbacks locally; the original serving loop admits generation. Legacy captures
retain their existing provider route. A native capture without this binding
fails closed.

The new extraction operation has its own canonical memory-extraction root,
exact text capability and one primary dispatch, with no continuation, child,
fallback or retry of uncertain effects. Its source answer's session/run is
provenance, never inference authority. Python allocates its opaque operation,
attempt, input, scope and cancellation identities. No native session or
transcript is created for extraction.

The authenticated IPC command is `model.extract` with exactly
`{configuration_id,binding,system,user}`. Binding has the existing five fields
and must match the authenticated operation/attempt frame; cancellation_id must
equal operation_id. The complete invocation is registered before its first
await. The native adapter consumes one preparation through supported scoped
`LLM.request`/`LLM.generate` and the guarded LLMClient. It uses the existing
model.prepare, model.manifest and model.dispatch callbacks.

Success returns immutable text and `{dispatch_id,permit_id}` only after actual
generation finalizers. A sanitized authenticated failure may be returned as
`{failure:{code,status,retryable}}`; no diagnostic, prompt or credential crosses
that projection. The final memory insertion transaction must call the existing
registry's publication guard with that same connection and compare the received
receipt to its consumed confirmed permit. M5 still checks the exact source
publication, answer digest, attempt, scope and support closure.

`model.extract.status`, `model.extract.cancel` and `model.extract.release` take
empty payloads and derive operation and attempt from the authenticated frame.
Controls must match the immutable admitted attempt before revealing state,
signalling cancellation or deleting a record. Status
reports active, settled or unavailable. Cancel signals interruption and retains
the invocation until finalizers settle. Release refuses active work. These
commands use reserved control capacity, and status is a bounded observation.
The initial observation request is itself retained before the first await and
shielded from observer cancellation. Expiry reuses that owned request task and
its resulting identity; it cannot submit a second read in its place. A local
pre-admission refusal has no receipt only when the public process query confirms
absence; it can then retire that observation without claiming native settlement.
Pending and terminal observation identities remain retained across timeout or
busy release; a new status read begins only after the previous release succeeds.
Read expiry cannot terminate the independently retained cleanup drain. Final
cleanup joins outstanding initial observation tasks before its settlement proof.
A final authenticated rejection after a pending acknowledgement proves no native
invocation, while an unknown acknowledgement continues to require actual proof.

CPU completion, native invocation settlement, scoped Domain settlement and
registry worker settlement are independent proofs. Cancellation or timeout does
not release any of them. The retained Memory cleanup joins actual CPU and
generation finalizers before releasing the canonical extraction pin/registry
receipt. Native host close seals/cancels extraction, joins it, then disposes the
store owner. A configuration root seal must also refuse a prepared capture,
including its interval before canonical generation admission.
Profile stopping seals and starts the retained Owner cleanup before producer
joins; native close starts while Memory/CPU ownership is still retained. This
breaks the dependency cycle when unavailable invocation status requires process
exit as the proof source. Dependency release still waits for actual settlement.

The connected tracer must create a genuinely saved answer. Its positive run
therefore has one setup send and exactly one incremental extraction send,
reported separately. It uses actual production main, SDK/IPC, canonical owners,
Mem0/Qdrant/FastEmbed and an owned loopback HTTP boundary. Account, limits and
inclusive counter evidence remain explicitly synthetic. A source edit during
held extraction must prevent a fact and stale recapture while preserving actual
finalizer ownership and live control.

The first actual-engine tracer has a passing positive receipt:
`G:/Renulus-agent-scratch/oc-h02-h08/native-extraction-tracer/receipts/positive02.xml`,
1 passed, zero failures/errors/skips, 21.029s. It uses the original Services
provider, production main, actual saved answer bytes and real Mem0/Qdrant/
FastEmbed. Setup and extraction each issue one synthetic-account loopback
request, for two total sends. The explicit native capture has a separate
confirmed permit, checks publication in the final Memory transaction, creates
no extraction transcript and settles its actual owners. Account limits and
inclusive counts remain synthetic. The held-source-revocation case is still
being implemented; this positive does not accept H05 or enable automatic capture.

The retained first receipt, positive01.xml (1 failure, 79.672s), timed out while
waiting for the counter. Public job state subsequently classified the cause as
`model_registry_capacity`: the fixture allowed 32768 manifest/request bytes,
while the installed Mem0 additive system prompt is 34276 UTF-8 bytes. Only
explicit fixture byte/frame/retention bounds and early failure diagnostics
changed before positive02. This is a fixture refusal, not a production defect
or a claim that the production bound changed. A local Qdrant payload-index
warning remains recorded.
