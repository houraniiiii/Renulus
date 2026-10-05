# Parallel implementation and worktrees

Original baseline 2026-10-04; active lanes, worktrees and handoffs are tracked in
GitHub issues and `../implementation/EXECUTION.md`. Sequencing below is flexible
when actual integration evidence changes a dependency.
**Every branch contributes real product behaviour.** Parallel mock screens do
not establish parallel progress if their contracts, state and integrations
cannot work together.

[Implementation stages](IMPLEMENTATION_PLAN.md) define delivery order.
[Architecture](ARCHITECTURE.md) defines authoritative module/path ownership.
Use that ownership table when assigning work; the exploratory research note's
alternative paths are not a second folder structure.

## Dependency waves for implementation

These development waves are separate from the subagent review waves used to
write this plan.

| Wave | Work allowed in parallel | Must already be stable | Integration result |
| --- | --- | --- | --- |
| A | Hermes and selected-stack packaging proof; Figma system/journeys; cross-domain content authoring | Confirmed product brief and stack | S0 runtime, helper artifacts, connection/scope contracts, content schemas and design foundation |
| B | Explain/desktop; library ingestion; content-review tooling | Runtime streaming/cancel, source/content IDs and retention scope | Working S1; library and content slices ready for S2/S3 |
| C | Cases; assessment; source-update retrieval | Source/version/eligibility interfaces; test-bank access rules | Working S2/S3 and early S5 retrieval |
| D | Memory/context; study/home; updates presentation | Evidence contract, correction/deletion semantics and source states | S4/S5 connected to real attempts, library and update records |
| E | Coverage expansion; accessibility; installer/update/restore; end-to-end review | All required interfaces integrated | S6 release candidate with complete tested journeys |

Dependencies govern merge/readiness, not merely task start. A worker may create
contract tests against a published schema before a producer is ready, but cannot
claim the feature done until the real producer is integrated. Memory semantics
and case non-persistence are defined in wave A, even though richer memory UI
arrives later.

Use the approved Mem0 OSS + Docling/HybridChunker + FastEmbed + LanceDB OSS
stack. F0 packages/configures the shared CPU helpers and approved generative
transport in wave A; M2 integrates Docling/chunking/LanceDB and M5 integrates
Mem0/local Qdrant. The integration owner coordinates dependency pins and
canonical SQLite migrations. Workers use one model/tokenizer contract and
app-owned state paths, not independent framework defaults or model downloads.
Source/version/scope contracts come before either index is activated.

## Branch, file and state isolation

- Use one short-lived branch/worktree per owned slice, for example
  feature/library-ingest in a sibling Renulus-wt-library directory. Keep the
  active Renulus workspace intact. Create branches from an agreed integration
  commit once planning changes are committed through the normal handoff.
- Assign one owner to F0 and each M1–M8 module. Workers edit only their owned
  paths plus their tests/fixtures. Small independent content batches can be
  divided by stable domain IDs under the M8 coordinator.
- One integration owner edits shared schemas, migrations, UI tokens/primitives,
  root manifests/lockfiles, CI/build configuration and cross-module tests/fixtures.
  F0 authors Hermes patches; the integrator reserves/reviews/merges that work.
  Exactly one writer holds those source paths at a time. A feature needing a
  shared change submits a narrow prerequisite patch.
- M2/M5 engine or helper changes that affect dependency locks, Hermes adapters,
  embedding dimensions or artifact paths are coordinated prerequisites. Rebuild
  a new derived index before activation; do not drop a live collection as an
  incidental framework upgrade.
- Give each worktree and run its own ignored state root, profile, database,
  caches, temporary processing area, logs, outputs, ports/pipes and app-instance
  identity. Set explicit subprocess state paths; do not let Hermes fall back to
  a personal/global profile. Do not repurpose system home variables.
- Isolate renderer cookies/cache, credential-store namespaces, installer identity,
  updater channel and uninstall target. Use disposable installation environments
  or distinct development installation IDs. Fail development startup if its
  explicit state root is missing. Test two concurrent synthetic instances and
  install/update/uninstall isolation.
- Use synthetic seeds and isolated test adapters. Do not copy credentials or
  user databases between worktrees. Live acceptance uses separately entered,
  explicitly selected user access, with no provider calls incidental to tests.

Git worktrees have separate working directories/indexes while sharing repository
metadata; runtime isolation must be provided by the application configuration.
([Git worktree documentation](https://git-scm.com/docs/git-worktree),
accessed 2026-10-04)

## Interface and schema sequence

1. Publish topic/session/source/content IDs, scope/retention classes,
   subscription/model constraints, cancellation and error shapes.
2. Publish document revision/passages, ingestion state and retrieval eligibility,
   plus M8 pack compatibility, transactional activation and pinned-version lookup.
3. Publish reviewed item/key versions, committed attempts, assistance and
   idempotent learning-evidence records.
4. Publish memory revisions/deletion, plan inputs and update freshness.

Use an additive versioned contract until all consumers migrate. The module owner
proposes table changes; the integrator assigns the migration order, checks
backup/restore and merges the ledger. Do not allow two branches to claim the
same migration number or independently rewrite the same root lockfile.

Refuse unsupported database versions and implicit downgrades. Define compatible
application rollback separately from data restoration. Test populated upgrades
and interrupted migrations. Existing-profile restore reconciles newer deletion
markers before indexing; a fresh restore from an old backup alone cannot know
about later deletions and must state that limitation.

Module implementations can vary internally without changing callers. A schema
change is required only when caller-visible meaning changes. Avoid a general
event platform or an extra service merely to enable parallel development.

## Merge and verification

Each slice handoff identifies:

| Evidence | Required content |
| --- | --- |
| Purpose | One real user outcome and the module/stage it advances |
| Reuse | Upstream capability or maintained library used; reason for any new subsystem |
| Scope | Owned files, prerequisite commits and any reserved shared change |
| Contract | Public operations, records written, scope/retention and failure behaviour |
| Proof | Relevant interface/integration tests plus the working Windows journey |
| Limits | Unavailable live capability or incomplete content, stated without a simulated pass |

Integrate one reviewed slice at a time in a clean integration worktree. Merge its
prerequisites first, run affected contract/migration tests, then exercise the
combined synthetic journey. After a dependency changes, rerun affected tests;
do not repeatedly retest unrelated modules. Rebase only an owned unpublished
branch. Resolve semantic conflicts with the owning module, not by keeping whichever
text makes Git quiet. Never stash/reset another worker's uncommitted work.

The integrator checks branch/status and sole origin before handoff. Record
commits, dependency versions, fixture versions and validation results.
Reserve packaging/provider acceptance for the real runtime; passing mocks proves
application rules, not an external connection or native install.

## Keeping the Hermes fork maintainable

Track the pinned upstream revision and a short downstream patch register.
Keep the retained source layout intact under its owned prefix. Fetch/import
updates by explicit upstream URL in the integrator's workspace so origin remains
Renulus's only configured remote. Upstream merges are separate from feature
merges and run the adapter, retention, tool-policy, subscription and packaging
checks before adoption.

Do not let multiple worktrees “fix” Hermes independently. A required runtime
patch is an F0 prerequisite with a reproduction and a test; downstream feature
workers consume the updated runtime contract. Keep library upgrades, schema
changes and broad visual redesigns out of unrelated feature branches.

## Practical change map

- Change explanations: M1; source display/ingestion: M2.
- Change case entry or Save: M3; change tests/scoring: M4.
- Change remembered learning: M5; change goals/home: M6.
- Change update selection/presentation: M7; change bank/case content: M8.
- Change authentication, allowed tool execution or installer/runtime: F0.

For a cross-module feature, name the record owner first and split work at the
published interface. One integrating owner is responsible for the complete
user journey; multiple completed branches are not themselves a finished feature.
