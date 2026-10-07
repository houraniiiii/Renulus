# Automatic ordinary Study learning-point capture

Implemented on 2026-10-05 in the isolated `build/study-answer-capture` lane,
based on parent `6abd3ae9`. Production changes are confined to the Learn
completion producer and `runtime/renulus/memory`; no Case or shared-schema
change is required.

## Producer and reference boundary

An ordinary durable STUDY completion commits the assistant reply, completed
run, existing topic/activity evidence and a new `study-answer` evidence record
in one SQLite transaction. The evidence ID is `learn-answer:<run_id>`. Its
payload contains only the original Study scope plus `answer_reference` with
`message_id`, `run_id`, exact UTF-8 `sha256`, and `version: 1`. The outbox job
retains the evidence ID/hash and scope; it contains neither prompt nor reply.
The existing asynchronous worker and idempotency policy consume the reference.

The producer excludes runs with Case handoffs/context and all non-STUDY flows.
Resolution accepts only the exact reference schema and original Study entity.
It checks source suppression, assistant role, completed run, matching
thread/run ownership and deletion markers before fetching a reply body.
It reads one eligible assistant reply, checks its exact hash, and never scans
user prompts, transcripts or Case tables. A reference forged as Study cannot
redirect resolution to a saved Case. Temporary, Saved Case and Unclassified
references remain excluded. General principles taken directly from Cases
remain an unresolved classification direction.

Cancellation, source deletion, changed reply version and correction/deletion
suppression are rechecked during extraction and inside the canonical commit
transaction. Stale jobs become cancelled; valid-source extraction failures
retain the existing retry behavior. User corrections retain source
suppression, so replay cannot recreate the original captured point.

## Selected engine and finite bounds

General replies use the existing Hermes OSSBackend, Mem0 OSS 2.2.1, selected
subscription transport, and app-owned BGE embedder. Each inference has a fresh
disposable in-memory Qdrant namespace and can extract only once. Mem0 normally
embeds the entire input for an existing-memory lookup before inference; that
lookup has no existing records here. The transient binding embeds a short
fixed educational query for this empty lookup, while Mem0 receives the full
exact answer for extraction. Extracted facts and persistent recall still use
the selected embedder normally. No answer truncation or vector/model fallback
is introduced.

Input is bounded to 16,000 characters. Oversize replies remain durable Learn
records without automatic answer capture. Existing extraction bounds remain
12 facts, 2,000 characters per fact and 16,000 output characters; the selected
helper retains its 512-token fact/query limit. There is no backfill from
historical topic-only evidence and no new provider or local model.

These are local implementation budgets, not live account quotas. Automatic
general-point capture performs additional asynchronous generation through the
currently selected subscription with `purpose='memory-extraction'`; it uses
that account's allowance and requires an authenticated, available model.
The controlled proof does not establish live account capacity or an unlimited
background allowance. Extraction has an existing 120-second timeout. No
separate paid API, subscription switch or local generative fallback is used.

Provider/account failures preserve the durable Learn answer and reference job
without inserting invented facts. Mem0 2.2.1 wraps extraction exceptions in
`LLMError`, so the memory job can expose the generic `memory_capture_failed`
code even when the provider's underlying failure is an account usage limit.
The existing `/api/v1/memory/retry` path retries failed jobs once the selected
account is usable; it rechecks source eligibility, deletion, version and
suppression first. This lane did not exercise a live account or measure quota.

## Verification

`tests/memory/test_study_answer_capture.py` exercises the real Learn producer,
reference outbox, real Mem0 OSS/Hermes adapter and local Qdrant with a controlled
subscription boundary and deterministic synthetic vectors. It covers CKD and
transplantation, idempotent replay, exact long-reply extraction, failed and
cancelled Learn runs, late deletion/version changes/capture cancellation,
correction and deletion suppression, and saved-Case sentinels with forged Study
scope. SQLite authorizer checks refuse all Case reads and Learn body reads for
ineligible references. A separate test deletes the source reply after Mem0
inference but before commit and verifies cancellation with no learning point.

At 01:20 UTC on 2026-10-05:

- Combined `tests/memory tests/learn tests/integration/test_case_learn_handoff.py`:
  **81 passed, 2 skipped** in 83.56 seconds. This includes the initial 17
  capture cases and existing real Case-to-Learn retention guards.
- Final focused capture suite, including two additional source-deletion/forged
  Case fences: **19 passed** in 10.92 seconds.
- `git diff --check`: passed.

Tests use isolated synthetic profiles and refuse remote sockets. The two
combined skips are existing optional helper-backed proofs; no heavy model
benchmark, live profile, credential, paid provider or external API was used.
These checks prove the implemented capture and retention boundaries; the
controlled generated facts are not evidence of educational or clinical
accuracy.

## Read-only integration audit

After integration as `d9d2e573`, audited parent `8f6de976` on 2026-10-05
from 01:30:52 UTC without another test sweep or production edits. `current(job)`
requires a running unsuppressed job, resolves its original scope/reference
again, and compares the producer fingerprint. Missing/tombstoned replies or
runs, deleted threads/evidence, changed reply content, and evidence reclassified
away from ordinary Study resolve to an `ApiError` and therefore `False`.
The provider checks this guard before generation and on each returned delta.
The final canonical commit checks it under SQLite `BEGIN IMMEDIATE`, so a
source change cannot commit concurrently between that check and fact insertion.
No concrete deletion/reclassification commit-fence blocker was found. This
audit concerns queued/in-flight capture; it does not add a policy for deleting
already committed general learning points when their Study thread is removed.
