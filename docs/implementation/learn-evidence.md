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
