# Renulus implementation run

Started October 4, 2026, 19:21 UTC (21:21 Warsaw). Target work window ends
October 5, 2026, 03:21 UTC (05:21 Warsaw). The user authorised implementation,
parallel bounded agents, GitHub tracking and a heartbeat every 15 minutes
(updated by the owner on 2026-10-04).

GitHub issues are the live queue. The earlier plans explain product intent;
they are adjustable engineering baselines, not immutable specifications.
Confirmed subscription, source-use, retention and licence choices still apply.
Flow is the selected visual direction. Preserve the UI and acquisition sessions'
uncommitted work and source originals.

## Waves

1. Integration owner establishes SQLite, process contracts, profiles and app
   boot. Runtime lane adopts attributed Hermes; desktop lane implements Flow;
   content lane publishes an original cross-domain pack.
2. Learn, library, cases and assessment build complete flows against these
   contracts. Source collection is consumed through manifests and selected files.
3. Memory, study/home and updates connect real evidence, editable records and
   current-source checks.
4. Integrate, exercise combined journeys, package the Windows app and record
   capability/coverage limits. Expand useful breadth while checks pass.

A ticket with satisfied dependencies starts in the next available lane. A
concrete failing integration becomes a prerequisite ticket, not a new planning
round. Record changes of direction in the ticket that motivated them.

## Ownership and delivery

The integration branch is `build/renulus-integration` in the sibling
`Renulus-wt-integration` worktree. Active integration subsequently moved to the
preserved clone at `E:/Renulus-native-delivery/desktop-20261005/repo` after the
disk-exhausted check; the original worktree remains preserved. Each worker has a separate branch/worktree
and runtime profile. The integrator owns contracts, storage, shared build files
and combined checks. Initial desktop shell ownership includes its local manifest,
tokens and primitives; after handoff these are reserved shared files.

Use small coherent commits and pull requests. Each handoff records owned paths,
behaviour, reuse, meaningful checks, evidence and remaining limits. Do not close a
ticket on a mock, typecheck or prototype when a real producer remains absent.
Live account access and clean-machine/signed release evidence are separate from
synthetic application checks. Do not access credentials from other apps or make
billed provider calls during verification.

## Interface baseline

One app-managed local Python process serves a versioned loopback interface.
FastAPI provides routing and streaming; this is not Hermes's unrestricted HTTP
gateway or another agent loop. The desktop renderer receives public operations
and capability state, never provider credentials or arbitrary tool execution.
`/api/v1` results are direct JSON; errors have `{error:{code,message,retryable}}`.
Streaming uses ordered SSE events with one terminal state.

Module adapters expose `create_router(services)` and register their repository
on `services.registry`. Shared `Database` offers `connect()`, `transaction()`,
`fetch_one()`, `fetch_all()` and `execute()`. SQLite owns canonical data. Module
DDL is proposed under each owned `schema.sql`; the integrator applies migrations
through one checked ledger. Engines remain rebuildable derivatives.

Scope is explicit: study, personal-library, temporary-case, saved-case,
generated-practice or reviewed-assessment. Unclassified and temporary payloads
stay volatile. Every asynchronous commit checks cancellation/revision/deletion.

## Evidence

Detailed lane evidence lives in `docs/implementation/` and GitHub ticket comments.
Machine-only output, acquired originals, indexes and logs stay outside versioned
source. The heartbeat reports observed commits/checks, active lanes, blockers and
the next ready work; it does not imply unseen work succeeded.

## October 5 follow-up wave

The original eight-hour target ended at 03:21 UTC. The active goal continues
with the same 15-minute heartbeat loop and concrete remaining work. Matching
`3ff9b0d6` package, fresh installation, isolated native lifecycle and the actual
shortcut/Library25/search/citation workload passed with the qualifications in
`final-validation.md`. Source originals and earlier checkpoints are preserved.

Curie owns #14 in the `collection-coverage` worktree: acquisition selection,
explicit hash-bound project review and narrow CC BY operation normalization.
Halley owns #15 in `supplement-inputs`: durable PPTX/DOCX/XLSX support through
the existing pinned Docling stack, bounded file admission and source locators.
Their write sets are disjoint; the parent owns API/UI/shared contracts, actual
profile corrections/adoption, integration and packaging. The normal installed
app owns the heavy helper slot while its queue runs. Live intentional Codex
sign-in is pending and is not replaced by another application's credentials.
Ready work advances independently of that account step.
