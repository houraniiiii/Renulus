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

## Flow desktop module handoff

The isolated default module entry is apps/desktop/src/modules/assessment/index.tsx.
It consumes the unchanged desktop foundation 75678df through ../../ui,
../../platform/api, ../../platform/useResource and ../../shell/navigation. No
shell, token, platform or manifest customisation is part of this lane.

The chooser, session, answer, source help, pause/resume/end and retained review
all use actual backend JSON. Types match these responses. Mode selection clearly
separates reviewed quizzes from the unavailable generated capability. No fake
scores, progress, generation or bank content is used by the production module.
Temporary/unclassified handoffs cannot start durable reviewed assessment; the
doctor must explicitly start separate study. No handoff payload is placed in
URL, localStorage or sessionStorage. No bank item is sent to Learn or a provider.

Mutation retries preserve the exact request body and idempotency key. An answer
whose acknowledgement is lost stays committed on the server. Nonretryable
errors can reload retained server state before abandoning the pending action.
New questions focus their legend/stem, and committed feedback focuses its
heading. Source links show the stored locator, edition and check date, while
failed locator checks remain labelled failures.

### Direction contract

THESIS: one question and one commitment lead to deterministic feedback. The
chooser and historical results support that action with quiet rows and a table.
OWN-WORLD: inherit the selected Flow paper, sage, petrol teal, Source Sans 3,
shared native controls and 4px spacing system, with borders for separation.
STORY: choose actual available topics, answer, inspect the retained key and
sources, then continue or pause. Incomplete coverage is visible throughout.
FIRST VIEWPORT: a reading column holds the question; a quieter continuation
column reports fresh/assisted/repeat results. Narrow windows stack these regions.
FORM: precisely scoped extension of the selected Flow surface; no new direction
or concept tournament, and no change to the shared DESIGN.md.
FINISH: implementation, live API tests, concrete visual inspection and recorded
limits are required; advisory design review does not create an external gate.

### Verification and provenance

- Backend commit: 2ec2e92; frontend and subsequent checks are in the next owned
  commit. Content prerequisites 3e06577 and c615d6a were consumed unchanged.
- Existing desktop suite: 20 passed, including four live assessment UI tests.
  The four module tests were rerun successfully after keyboard-focus changes.
  They start a real Uvicorn process with the shared SQLite/schema and original
  synthetic fixture adapter, under a new temporary profile and allocated port.
- TypeScript and Vite production renderer build pass. Native Electron startup,
  installed Windows packaging and clean-machine release are separate evidence.
- Real ContentRepository integration installs an original six-domain synthetic
  pack through M8 validation; correcting pack activation and restart preserve
  attempts, key/family versions, citations and repeat exposure. This fixture is
  not a production question bank or a medical-content accuracy check.
- Combined backend checks now pass 26 tests with one skip: tests/assessment,
  tests/content and tests/integration/test_foundation.py. The default original
  pack test skips because no authored production pack is in this checkout.
- A separate producer preflight passed against M8's actual candidate manifest
  in Renulus-wt-content/content/packs/renulus-foundations/1.0.0. The candidate
  has 52 questions / 27 topic definitions; manifest SHA256 is
  f2430000aa3f13b4e76fb0a379513469f70f0efc18a832bd131affa4f63e3154.
  Fifty selected items score from the actual published keys, retain source
  metadata and survive restart/idempotent retry without duplicate evidence.
  This is actual producer/software integration evidence, not independent medical
  key review or acceptance of a final committed pack; M8 owns publication.
  Command: RENULUS_ASSESSMENT_TEST_PACK=<explicit manifest> python -m pytest
  tests/assessment/test_original_pack.py -q (1 passed).
- Impeccable detector returned [] for the module TSX/CSS. Wide question and
  committed-feedback browser captures are valid. The original narrow capture
  used a measured 727 CSS-pixel window (718px image/client width plus scrollbar,
  existing 110% browser zoom), not an 800 CSS-pixel window. A later 800 CSS-pixel
  measurement showed no horizontal overflow, but repeated shared Chrome CDP
  failures prevented a trustworthy recapture at that size. Do not use the stale
  quiz-narrow-css800.png as evidence. Captures remain in the isolated ignored
  .local/runtime/assessment-ui/evidence directory; no screenshot is a real bank.

Remaining product limits: no complete exam or formal ESENeph blueprint, no
generated-practice producer, no authored hints in the M8 contract, pending real
teaching-pack adoption and pending native release verification. All generation
must later use provider.stream(messages, scope, run_id, model, system, purpose),
cancel(run_id) and status() from the shared approved seam. No extra model route
or inference service has been introduced.
