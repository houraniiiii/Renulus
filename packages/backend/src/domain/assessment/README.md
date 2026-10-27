# BF05 target assessment contribution

These functions port the local contracts and transaction semantics from
`runtime/renulus/assessment/`. The existing Python implementation remains in
place. The integrator owns activation and the profile-wide writer handoff.

## Canonical writer

`storage/assessment.ts` exports `AssessmentCommand` dispatch predicates,
validation and synchronous `executeAssessment(db, command)`. The command union
and results live in `contracts.ts`. These functions neither open databases nor
manage transactions. `storage/content.ts` follows the same convention.

The canonical worker commits `reconcileAssessments(db)` in its own transaction
before ordinary commands. This is essential: expiry and deterministic scoring
must survive an ordinary command's later refusal. Read-only previews skip it.

Ready versions pin questions, options, keys, families and producer provenance.
All origins use the same local attempt/scoring path. Whole Test drafts commit
atomically; Study answers commit on Submit answer. Help exposure commits before
assistance; `assessment.help.current` rechecks the returned context before late
publication. Replayed help is subject to the same current-context predicate.

## Native producer ports

`createAssessmentGeneration(storage, native)` in `generation.ts` owns bounded
five-question batches, durable checkpoints and explicit shorter acceptance.
`native` implements `AssessmentNativePort` using the existing native graph and
dispatch authority. It has no provider/model-selection or scoring authority.

- `create`, `read`, `resume`, `settled`, `cancel`, `acceptShorter`, `close` manage
  saved generation. Observer detach does not cancel saved generation.
- A running execution found after restart requires
  `settleInterrupted(job) -> 'settled' | 'held'` before explicit retry. Absence or
  held settlement refuses retry; no blind model resend is permitted.
- `normalize` validates exact Unicode source spans and formatting-only output,
  with three admitted normalization calls maximum. Edits/removals are retained
  by overlapping original spans. Explicit missing/ambiguous-key resolution is
  separate from normalization.
- `fictionalise` requires the **BF04 actual volatile native graph** for both
  transformation and a separate privacy-review invocation. Source text, its
  digest and raw jobs never enter the canonical store. Review binds the exact
  fictional question artifact; publication rechecks policy/context atomically.
- `narrative` receives only an approved committed result summary and cannot
  update deterministic scores or keys.

The HTTP adapters expose existing local routes and strip generation checkpoint
questions/keys/inputs from public responses. Internal publish/claim/recovery
commands are host-only. Content pack validation remains the existing pure
`content.validation` implementation via a host-resolved port, outside canonical
transactions; no public arbitrary plan or raw question-detail route is added.

## Focused evidence

`packages/backend/test/assessment-target.test.mjs` uses the actual single storage
worker and disposable synthetic profiles with the pinned Node/Python cohort.
It covers reviewed Study/help and whole Test, immutable results and lost ACK,
deadline across reopen/clock rollback, withdrawn-key exclusion, cancellation in
5/10/20 batches, shorter acceptance, interrupted-native settlement, public key
redaction, ambiguous import keys, three-call normalization and exact-artifact
fictional privacy review with no retained original/hash. No account/provider
usage, production profile, full package gate or activation is established by
these tests. Native port composition belongs to the integration owner.
