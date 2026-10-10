# Saved generation consumer

This module creates topic/reference jobs, reopens durable progress and opens the
exact published saved-test version. It never starts an attempt or its timer.
GenerationPanel can be embedded in Tests or a typed conversation card; the
default page opens published versions through the Tests route and its
test_id/version_id handoff.

The integration owner mounts renulus.assessment.generation_api.create_router
once under /api/v1. Its owner is services.registry['saved_generation'].
Every start/retry/accept/read is assistance guarded. The exact POST cancellation
route returns only {id,state} and may be exempted from the global assistance
middleware so an active Test cannot prevent Stop.

GenerationPanel accepts jobId, initial, onJobCreated, onPublished and
onOpenVersion. initial may contain title, count (5/10/20), installed topic ID,
backend-resolved EligibleInput references and saved Library revision references.
It accepts no arbitrary prompt, original case text, retention attestation or
review-quality declaration. Source selections currently target whole saved
Library revisions, with no locator. Publication callbacks carry only
{test_id,version_id,item_count,available}; they do not contain questions or keys.

The exported API helpers require explicit idempotency keys. A lost command
acknowledgement retains its exact body for explicit retry. Reopening/polling only
reads progress and reconciles a stale restored epoch; it never queues model work.
Provider calls are bounded to twelve per job, active jobs to three, and action
receipts to forty. Cancel and backend shutdown retain validated batches.
Explicit shorter-set acceptance must match the entire displayed validated count.

Evidence uses the actual production schema, repositories, Knowledge retrieval
and installed ProviderManager, with an owned synthetic transport. Renderer
journeys use the real local API: lost acknowledgement, seven-of-ten acceptance,
neutral Stop, reopening and explicit retry. The synthetic profiles and local
tool caches are external under C:/Renulus/scratch/design-c/generation/.

Remaining consumer prerequisites are the parent's Tests/chat entry wiring,
hidden integrated visual acceptance and its exact cancel middleware exception.
Home text needs the shared trusted saved-context resolver before it can become a
generation input. A DC18 fictional artifact needs its trusted volatile privacy
transition and producer handoff; no renderer route accepts such an attestation.
These checks establish connected synthetic behavior, not live provider or
installed release acceptance, and do not close DC16 on their own.
