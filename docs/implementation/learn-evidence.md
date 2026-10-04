# Explain and resume — first integration evidence

October 4, 2026. Owner: integration lane, issue #5.

Implemented ordinary study thread persistence, direct/guided instructions,
ordered answer/source/terminal SSE events, explicit temporary branching,
cancel/retry and deletion. Generation consumes the controlled Hermes provider
contract; there is no production fake response. Sources come from the knowledge
repository when present; failed retrieval is identified rather than claimed as
verified evidence. Hermes retains responsibility for model context management.

Ten combined foundation/Explain checks pass with isolated synthetic profiles.
Explain checks cover restart/resume, retry without a duplicate answer, retained
user input when disconnected, volatile case sentinels and payload-safe errors,
cancel before commit, and accurate completed state when commit wins.

This establishes application rules and real local persistence. The stream test
provider exists only in tests. Live subscription response, UI journey and
source-cited answer evidence remain pending integration with their producers.
# Integrated learner-memory handoff — October 4, 2026

Ordinary study explanations recall bounded revisioned learner context from the
memory service. The prompt labels this as learner data, separate from scientific
evidence; SSE events distinguish memory availability from source retrieval.
Temporary and unclassified explanations skip both retained retrieval adapters.
Committed study evidence carries its explicit study scope and wakes durable
memory capture only after the explanation transaction commits. A failed wakeup
leaves the saved explanation complete and reports capture availability separately.

The integrated Learn/study/memory application run passed 39 checks with two
helper-backed tests skipped without their explicit proof profile. The memory
lane separately records real Mem0/Qdrant/FastEmbed evidence. New checks exercise
ordinary recall, volatile exclusions, cancellation during recall, notification
failure after commit, and agreement with assessment score buckets. No live model
provider was called.
