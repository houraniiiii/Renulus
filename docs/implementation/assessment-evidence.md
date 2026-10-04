# Reviewed assessment implementation evidence

Lane M4 / GitHub #8, October 4, 2026. Worktree: Renulus-wt-assessment;
branch: build/reviewed-assessment. First handoff is bounded to backend and
contracts while the desktop shell and content producer run in separate lanes.

## Decisions in progress

- Reuse shared Services, Database transactions, ApiError and module routing.
  Propose assessment-owned DDL only; the integrator applies assessment-001.
- Read published items exclusively from services.registry['content']; agree
  ContentRepository methods with M8 before the adapter is finalised.
- Pin immutable question/key/family versions and a private item snapshot.
  Do not return keys or feedback before an answer is committed.
- Persist family exposure before showing a question, hint or source help.
  Exposure survives pause, cancellation, restart and content corrections.
- Commit answer, deterministic score and canonical learning_evidence in one
  SQLite transaction, with idempotent retries and conflict detection.
- Keep fresh, assisted and repeat score buckets distinct. Generated practice
  uses a separate capability and will fail visibly until approved generation
  exists; this slice makes no model or paid-provider calls.
- Retain original attempts and scores when content is corrected or withdrawn;
  annotate historical review with current content status.
- Use original synthetic fixtures only under tests/assessment, then test the
  real original published pack once M8 hands off. No production fixture bank.

## Scope and checks

Owned paths: runtime/renulus/assessment/**, tests/assessment/**,
apps/desktop/src/modules/assessment/** and this file. Shared core, manifests,
content authoring and main merges remain with their owners.

Backend first handoff: 16 assessment tests and 5 existing shared foundation
tests pass (python -m pytest tests/assessment tests/integration/test_foundation.py
-q; 21 passed). Tested real shared SQLite and FastAPI, with the original tiny
synthetic ContentRepository adapter under tests/assessment only.

Checks cover cross-domain selection, missing-topic and count coverage, key
non-disclosure, idempotency conflicts, concurrent retries, help/answer races,
evidence-insert failure rollback, restart/resume, committed-only review,
corrections/withdrawals and retained scores. No clinical effectiveness or live
provider claim follows from these software checks.

## Public backend contract

create_router(services) registers services.registry['assessment']. Routes have
the /assessment prefix, with /api/v1 added by the shared server:

- GET /catalog, /aggregates, /progress, /mistakes, /sessions.
- POST /start with idempotency_key, mode ('reviewed' or unavailable 'generated'),
  count (1–50), selector {domain_ids,topic_ids,track}.
- GET /sessions/{id}: durable exposure precedes returning the current item.
- POST /sessions/{id}/answer with idempotency_key,item_id,option_ids.
- POST /sessions/{id}/help with idempotency_key,item_id,kind ('hint' or 'sources').
- GET /sessions/{id}/review with optional item_id,mistakes_only. Only committed
  answers reveal keys. A skipped item never acquires review feedback.
- POST /sessions/{id}/pause, /resume, /end with idempotency_key.

Answer results are {feedback,session}; other mutations return their direct
result. Versions in assessment JSON are fixed string identifiers. The current
M8 domain selector uses stable topic IDs; general_nephrology is available and
esen_eph has explicitly insufficient mapped coverage. The chooser round-robins
topics, prefers fewer family exposures and avoids duplicate families.

M8 contract consumed: list_question_summaries(topic_id=None,domain=None,
track=None), get_question_version(id,version:int), list_topics(). Backend-only
question fields include correct_option_ids/explanation and version/status
annotations. Source records, when present, enrich pinned citations with actual
titles, editions, URLs and check dates. No source retrieval is claimed.

Canonical evidence kind is assessment-answer; topic_id and entity_id reference
the topic and attempt. Payload includes correct/assisted/repeat booleans,
question_id/question_version/key_version/family IDs, objective_id when present,
session_id/attempt_id and app-owned reviewed-assessment scope. The write is
atomic with the attempt and score. progress_summary() and mistakes() are public
read-only repository methods; mistake summaries never include keys or stems.

Fresh, assisted and repeat score buckets are exclusive. Assistance takes
precedence for an assisted repeat; both flags remain on that attempt. Changing
content blocks new answers to that old session item. Historical review annotates
withdrawal/correction/inactive/unavailable status without rescoring.

## Limits at backend handoff

Native assessment UI and real published content integration are pending. No
complete exam simulation is offered. M8 currently has no authored hints; source
help is supported and missing hints fail explicitly. Generated practice is
unavailable and contributes no reviewed evidence or scores. Future generation
must use the approved provider.stream/cancel/status seam with app-owned scope;
this commit performs no generation, compaction or external inference.
