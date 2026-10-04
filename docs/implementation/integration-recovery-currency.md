# Recovery and source-currency integration

2026-10-04 · integration branch.

Library recovery takes the ingestion and mutation guards before canonical
backup/restore. Learner-memory recovery refuses an active inference, pauses
new captures and canonical changes, and resumes the poller after exit. Brief
claim bookkeeping is separate from inference and index operations, preserving
concurrent canonical edits during a normal index rebuild.

An actual Updates review/outbox → Knowledge source-status journal check caught
an evidence-shape mismatch. The journal now recognises the reviewed-publication
envelope and validates its inspected references, while retaining reviewer/date
provenance. Unreviewed observations can only invalidate prior verification.
The combined check proves replacement annotation suppresses eligible retrieval
and retry leaves one journal event. It makes no medical currency claim.

Validation in the integration worktree:

- Source-status, memory service and collection API: 23 passed.
- Memory service after keeping scan/claim bookkeeping inside the pause guard:
  11 passed.
- Workspace/public-boundary checks passed; learning-app launcher CheckOnly
  passed against the prepared contributor build.

The normal launcher targets Renulus and accepts an ignored delivery record for
the assembled Windows executable/profile. An explicit legacy-preview script
preserves the archived reference launcher. Native delivery and engine-backed
ZIP restoration remain separate acceptance checks.

The owner changed the implementation heartbeat from 30 to 15 minutes. The
owned background loop was replaced and an immediate GitHub heartbeat was
recorded at 21:34:03 UTC.
