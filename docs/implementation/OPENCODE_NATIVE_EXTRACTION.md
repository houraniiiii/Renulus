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
empty payloads and derive their identity from the authenticated frame. Status
reports active, settled or unavailable. Cancel signals interruption and retains
the invocation until finalizers settle. Release refuses active work. These
commands use reserved control capacity, and status is a bounded observation.

CPU completion, native invocation settlement, scoped Domain settlement and
registry worker settlement are independent proofs. Cancellation or timeout does
not release any of them. The retained Memory cleanup joins actual CPU and
generation finalizers before releasing the canonical extraction pin/registry
receipt. Native host close seals/cancels extraction, joins it, then disposes the
store owner. A configuration root seal must also refuse a prepared capture,
including its interval before canonical generation admission.

The connected tracer must create a genuinely saved answer. Its positive run
therefore has one setup send and exactly one incremental extraction send,
reported separately. It uses actual production main, SDK/IPC, canonical owners,
Mem0/Qdrant/FastEmbed and an owned loopback HTTP boundary. Account, limits and
inclusive counter evidence remain explicitly synthetic. A source edit during
held extraction must prevent a fact and stale recapture while preserving actual
finalizer ownership and live control.
