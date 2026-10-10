# Renulus harness foundation — recommendation and adoption study

October 10, 2026. **Final source-based architectural recommendation.**
Thirty distinct subagent reviews have completed and their memos have been read.
This document proposes an architectural direction; review count is not a vote
or empirical validation. The previous Hermes foundation decision remains recorded.
No migration, dependency installation, provider inference or deployment was
performed for this adoption study.

## Recommendation

**Choose Pi as the foundation for a client-independent Renulus harness, with
pi-durable as the first concrete execution-owner candidate, behind a pinned
Renulus adapter.** Keep the existing Python data and learning services. Reuse
selected Hermes code where it already fits; borrow OpenCode v2's client, event,
permission and provider-provenance patterns. Use one agent execution/recovery
implementation.

This is an architectural judgment from source contracts and retained goals,
not a reliability benchmark or production acceptance claim. Pi durable is
explicitly experimental. Adoption is blocked until a headless proof establishes
generation-recovery control, coordinated purge, canonical receipt reconciliation
and Windows ownership. A failed proof should reopen the concrete runtime choice,
rather than turn the proposal into a permanent commitment.

The reason to prefer this direction is that the owner now wants an extensible
harness with data, retrieval, tools, execution and subagents as its centre.
Pi durable provides actual task, conversation, tool and storage machinery with
injected models and an optional execution environment. Those contracts establish
a suitable composition seam, not lower total implementation or maintenance work. Renulus can supply domain
roles without starting from a coding CLI or retaining a project-oriented server
graph. Using agent-core alone would leave durable orchestration to build; using
AgentSession would add its concrete conversation store. The durable library is
a separate adoption unit, built on pi-ai and Chord, not an implicit extension of
those two execution paths. See [Pi design][R22], [maintenance][R18], [clean-slate challenge][R27],
[final adversarial judgment][R30] and [pinned harness options][P-options].

## Evidence, method and preserved constraints

The [expanded source comparison](2026-10-10-backend-harness-comparison.md) retains
all fifteen original axes, including the Pi and OpenCode v2 columns. This deeper
study uses six conceptual waves of five distinct agents: source/criteria;
execution/delegation; data/learning; delivery/operations; competing designs and
critiques; transition, accuracy, scope and adversarial synthesis. Work was
pipelined. Reviews 21–24 began their independent work while review20 finished,
then incorporated its completed findings. Agent IDs and memos are recorded in
[the review ledger](2026-10-10-harness-adoption/README.md).

The parent makes the recommendation. Scoped reviewer preferences are evidence
of tradeoffs, not votes. No invented scores, performance measurements, migration
time estimates or educational-effectiveness rankings are used. Primary source
contracts were inspected; new runtime/provider acceptance was not performed.
Renulus source references were verified from locally available Git objects. Its
public raw URLs returned 404 to the accuracy reviewer; those references identify
the inspected revision rather than independently public evidence. [R28]
The initial comparison's bounded tests remain separately scoped, including its
reported authentication-status failure and response-identity limitation.

Public source baselines were resolved on October 10:

| Subject | Exact inspected baseline | Qualification |
| --- | --- | --- |
| Renulus | 528025ff0b22477c12ee1512e0e7d15297a6e888 | Current worktree code; research changes are uncommitted. |
| Hermes | Bundled af90026aa09949579bd423d24def3d38f743cde0; inspected main dce1e9b37581dd62e480a9064dc04a709c2940d3 | Existing adoption and inspected upstream are distinct. |
| Pi | v1.1.0, abe508e1b89912adde45528136c3221eb69acdd7 | Includes separate agent-core, coding-agent and published experimental durable package. |
| OpenCode v2 | Branch 55dde8810d8a859c0a21e42491ae7d5801fb49ef, declaring 2.0.26 | v2.0.26 tag resolves to 9b4ec5714d481559990db0a816d5dec19541a814; it is a different source identity. |

Published @opencode/sdk 2.0.26 exists. Its registry metadata declares Effect
4.0.0-rc.112 and no gitHead; the inspected branch uses rc.118. Default CLI
opencode-ai was 1.18.35. These observations neither establish branch/artifact
identity nor support a claim that no v2 artifacts are published. Pi package
versions likewise require locked artifact identities, not merely matching names.
The integrity-verified published SDK tarball also starts recovery during host
creation before supplied plugins register. The inspected branch registers those
plugins first. The tag has the published fragments' ordering; this does not
establish whole-artifact/source parity. An adoption using the published package
cannot rely on startup plugin registration to gate recovery. [R28]
See [distribution review][R18] and [OpenCode entry-point review][R03].

Retain personal Windows delivery, managed local helpers and the selected
Codex/OpenCode Go subscriptions. No owner-hosted inference, doctor-managed GPU,
Docker or generative model server, mandatory generation API, or silent route
fallback is proposed. The exact allowed models remain gpt-6.1-sol, gpt-6-astra,
gpt-6-luna for Codex, and mimo-v2.6-pro, deepseek-v4.1-flash for Go. Existing
Mem0 OSS/QdrantLocal, Docling/HybridChunker, FastEmbed and LanceDB roles remain;
SQLite and owned originals retain canonical source, learner and assessment
authority. Nephrology breadth, reviewed assessment versus generated practice,
source rights/currentness and saved-by-default conversations with explicit
temporary scope remain requirements. Design C remains the desktop direction.
See [decisions](../DECISIONS.md), [user direction](../planning/2026-10-04-user-answers.md),
[architecture](../planning/ARCHITECTURE.md) and [source boundaries](../SOURCES.md).

## What is already substantial, and what is missing

Renulus already implements ingestion and hybrid retrieval with canonical
revision/eligibility checks, scoped learner-memory correction/suppression,
content and key versions, transactional reviewed scoring and study records.
Those are reusable harness services. None of the three upstream runtimes replaces
their educational or source-use authority. See [core review][R04],
[retrieval][R12], [memory][R14] and [assessment][R15].

The missing seam is general agent execution. The present generation interface
yields text; input roles are restricted; the adapter strips tools and rejects
tool calls. A wrapper around that text iterator would leave the same limitation.
The replacement interface must carry typed model messages, tool calls/results,
usage, relevant reasoning/continuity metadata and terminal outcomes. Existing
authentication and model-selection assets are useful, but their current behavior
does not prove enforcement across every new generative purpose. [R04], [R09]

The client connection also needs neutral artifact references and bootstrap.
Current composition and original URLs include HTTP/app details, and Electron
owns the backend lifetime. A harness can run independently of Electron without
implying a permanently running service or automatically changing what closing
the desktop does. Define those lifetime modes explicitly. [R04], [R16], [R20]

## The three approaches, compared for this goal

| Decision axis | Hermes | Pi | OpenCode v2 |
| --- | --- | --- | --- |
| Reusable execution unit | Full headless AIAgent plus registry; synchronous turns, interrupt and close | Distinct agent-core, AgentSession and durable units; durable is the proposed owner | Embedded server graph and typed Promise/Effect SDK with owned local transport |
| Best demonstrated source advantage | Assembled general-agent lifecycle and direct Python domain proximity | Explicit composition around models, tools, tasks and storage; no required coding environment in durable | Integrated durable admission, execution claims, child jobs, permission mediation and client protocol |
| Durable work | Session/turn leases and gateway recovery exist; domain workflow admission still needs integration | Durable library commits submissions and tool intent; core/session queues are different contracts | Persisted inbox/claims and restart accounting, explicitly at least once |
| Child workers | Real delegation; stock model-facing children inherit broad parent tools minus exclusions | Host-defined role/delegation on real durable tasks/conversations; CLI subagent is a separate example | Built-in foreground/background child sessions, continuation/depth checks and completion delivery |
| Domain/tool authority | Handlers still validate and authorize operations; ambient discovery/globals need containment | Registered trusted tools and injected models; beforeRequest exceptions do not enforce policy; replay needs fresh executor checks | Replaceable tools/prompts, but directory/project identity and guarded integrations remain; domain checks still required |
| Main adoption work | Client/configuration isolation, complete generation-policy containment and host ledger/retention | Typed Python seam, generation claims/correlation, client history/input/scheduling, purge/migration contract | Domain profile, broker/recovery/child-wake overrides, Python seam, native closure and artifact verification |
| Recommendation | Retain useful code and patterns; a credible alternative if its controlled embedding proves superior | Primary architecture direction; pi-durable first proof candidate, with explicit experimental gates | Strong alternative for integrated coordination; borrow its operational contracts now |

Evidence: [Hermes design][R21], [Pi design][R22], [OpenCode design][R23],
[durability][R10], [capabilities][R19], [client boundary][R20],
[Hermes turn lease][H-lease] and [accuracy corrections][R28]. These are
qualitative adoption judgments, not measured platform rankings.

## Competing designs and the choice between them

The Hermes design exposes start/events/cancel over one Python owner, embedding
AIAgent beside existing domain modules. It concentrates source and domain reuse
locally. It must supply committed admission/events and contain independently
configured summary, delegation and recovery paths. A failed custom-client hook
can fall through to ordinary construction; this bypasses the trusted hook but
is not proof that a different provider/model is selected. Directly injecting an
async application client also does not satisfy its synchronous turn contract.
[Hermes contender][R21], [sunk-cost challenge][R24]

The Pi design chooses durable as the sole task/agent owner and bridges Python
through typed commands. It supplies durable task primitives rather than asking
Renulus to recreate them around agent-core. Its costs are concrete: request-ID
reconciliation checks submission type, not payload equality; watcher reconnect
is snapshot-based; ordinary beforeRequest errors are reported while generation
continues; convenience operations can start the global scheduler. Initial
beforeTool errors instead block, with changed-argument validation, but safe replay
bypasses that initial guard path. Every domain executor must validate arguments
and fresh authority itself. The Renulus adapter needs payload-digest binding, a
client event/input contract and actual generation enforcement in injected
transport. A beforeRequest hook alone is insufficient. [Pi contender][R22],
[accuracy audit][R28]

The OpenCode design supplies the most assembled client/coordination boundary.
The inspected branch registers supplied plugins before recovery; the verified
published SDK starts recovery first. Preconstructed layer replacement or a
reviewed source build needs proof before startup, rather than relying on supplied
plugins as the gate. A neutral domain profile can replace editing tools and
prompts while preserving project/location identity. It must contain recovery,
parent wake and auxiliary generation without rebuilding the runner that makes
it valuable. Its service graph and native dependency closure become maintained
adoption assets. [OpenCode contender][R23], [artifact audit][R28]

**Parent judgment:** for an extensible learning harness whose domain authority
already exists, the Pi durable design places the execution seam most directly
around host-selected models, tools, tasks and storage. It offers useful durable
machinery with less inherited application/project behavior. This is a seam and
ownership preference, not a claim that it has more features or better measured
reliability. The experimental API and incomplete purge contract are serious
adoption gates. Pi agent-core remains an alternate Pi unit if durable fails,
but choosing it means explicitly budgeting the missing durable coordinator;
it should not be described as equivalent functionality. The clean-slate review
does not let existing Python assets settle the loop choice. The adversarial
review accepts this direction only with the four blocking proofs and explicit
data/extensibility outcomes. [R27], [R29], [R30]

OpenCode would become preferable if the Pi proof requires replacing substantial
task/storage machinery, while an OpenCode domain profile preserves its integrated
coordination and passes the same route, retention and recovery checks. Hermes
would become preferable if controlled Python embedding satisfies those checks
with less maintained machinery and preserves its useful lifecycle. These are
falsifiable reversal conditions, without guessed implementation effort. [R24], [R25]

## Proposed architecture

~~~mermaid
flowchart TD
    C[Windows UI, optional CLI, scheduled invocation] --> H[Renulus harness API and trusted policy]
    H --> P[Pinned Pi durable execution owner]
    H -->|Direct data commands| D
    P --> G[Generation broker and attempt claims]
    G --> M[Selected Codex or OpenCode Go models]
    P --> D[Managed Python domain services]
    D --> S[Canonical SQLite and owned originals]
    D --> I[Docling, FastEmbed, LanceDB, Mem0/Qdrant derived processing]
    P --> O[Operational task and transcript storage]
~~~

These are logical boundaries. The broker can reuse the managed Python
authentication/provider assets; a new separately hosted service is unnecessary.
The Python worker executes domain/helper operations and owns the local memory
index. It does not run a second autonomous agent/recovery loop. Existing model
outbox runners must route admitted generative work through the shared execution
and broker policy, while safe deterministic processing can remain domain-owned.

The harness also exposes versioned import, query and evidence-read operations
without creating a conversation or dispatching a model. Data access does not
need a durable agent task. A reviewed extension contract registers tools, child
roles and workflows with schemas, scope, budgets and typed artifact results.
Adding a bounded retrieval tool or role must not require renderer changes or
editing executor internals. These are proposed host contracts, not existing
product capabilities. Optional CLI/scheduling examples do not require a permanent
daemon, remote hosting, a plugin marketplace or arbitrary shell execution. [R29]

The trusted host derives project/source/learner scope, retention, selected route,
roles and aggregate budgets. Model arguments can narrow grants but cannot enlarge
them. Children inherit subsets and return typed draft findings/artifact references.
Canonical services decide source validity, memory edits, exposure, publication
and scoring. A second model's criticism is a review proposal, not independent
clinical validation. [R12], [R14], [R15], [R19], [R22]

One local profile owner coordinates clients; a profile lock prevents competing
writers. The public port commits admission before acknowledgment; duplicate IDs
with conflicting payloads fail. Attach/resume inspection is observational.
Cancellation accepted and execution settled are distinct outcomes. History
ancestry, delegation ownership and compression lineage are distinct edges.
Artifact IDs bind source/revision/passage/digest/locator, run/attempt, scope and
status. Original readers remain scoped client adapters. [R11], [R12], [R20]

Canonical and runtime databases remain separate authorities. Canonical mutations
use operation keys, revision/cancellation fences and durable receipts; outbox
reconciliation bridges stores. An emitted completion cannot establish a committed
score, and separate SQLite files do not share an atomic transaction. Temporary
payloads require volatile transcript, task, child and helper scope. Save/Archive
and coordinated purge require the existing retention migration and an explicit
runtime-store manifest. [R10], [R11], [R22]

## What to take from each, and why

| Source | Take | Adoption form | Reason and limit |
| --- | --- | --- | --- |
| Existing Renulus | Canonical Library/currentness/rights, learner facts/suppression, bank/key versions, deterministic scoring and Study services | Retain code behind typed domain commands | These already encode the learning/data rules and remain useful with any loop. |
| Existing Renulus | Mem0/Qdrant, Docling/HybridChunker, FastEmbed and LanceDB adapters; managed Windows Python/helper staging | Retain code, assets and provenance | Preserve offline CPU processing and avoid rebuilding data engines for a loop change. |
| Pi durable | Conversations, submissions, task ownership/checkpoints, tool intent and conservative replay | First direct library/source adoption candidate, pinned behind adapter | Supplies real harness machinery; experimental API, generation replay and purge remain gates. |
| Pi ai | Typed model interfaces/conversion where compatible with selected routes | Controlled dependency through injected broker models | Preserve rich model/tool messages without ambient provider selection; account compatibility still needs evidence. |
| Pi agent/core contracts | Model content versus client details, explicit busy/settled semantics | Interface patterns, not another execution owner | Keeps typed artifacts and UI state separate from model text. |
| Hermes | Current scoped Mem0 integration and compatible context/transport helpers | Selected attributed code units after compatibility checks | Already useful in Python; refreshing relocated Mem0 requires lifecycle adaptation, not an import-only change. |
| Hermes | Fresh worker context, cleanup/lifecycle and pending-question reconnect | Patterns | Coherent run/child handling and reconnect behavior; stock inheritance and fallback are not copied as authority. |
| OpenCode v2 | Durable admission/claims, action/resource mediation, accepted-versus-settled cancellation and typed local protocol | Patterns and conformance targets | Improves coordination semantics without importing a second execution graph. |
| OpenCode v2 | Ordered lifecycle replay and exact provider/model/protocol/route/endpoint provenance | Patterns | Reconnects and opaque continuity need explicit compatibility; cache savings and provider erasure are not claimed. |

Supporting reviews: [reuse][R04], [retrieval][R12], [memory][R14],
[continuity][R13], [Windows][R16], [events][R17], [licensing/update][R18],
[scope][R19] and [combination critique][R25]. Any copied code needs scoped licence
notices and provenance; a design pattern is not a runtime dependency.

## Policies that cannot be inferred from upstream defaults

The October 6 decision covers actual authentication, quota, model and image
rejection without automatic retry/fallback/subscription changes. The existing
adapter sets SDK retries to zero; preserve that conservative proof baseline.
General transient-network and conversation-restart policy remains separately
unresolved. DC16 explicitly preserves validated generated-test work without
restarting billed/model work automatically after cancellation/restart. Safe
validation/publication reconciliation is distinct from repeating generation.
Some early memos used broader shorthand; their added qualification and
[route review][R09] resolve that distinction. [DC16], [R15], [R20]

Every parent, child, summary and memory-extraction request crosses the selected
subscription/exact-model boundary. Broker construction failure issues no
outbound request. A tool result's error or successful status does not grant
source rights or accept a domain artifact. Ordinary extension hooks, prompts,
read-only hints, tool catalogues and cwd are not operating-system containment.
Reviewed extensions and bounded CPU helpers are the proposed default surface;
broader executable tools need their own demonstrated boundary. Initial tool
hooks and replay have different paths, so argument, source, cancellation and
revision checks belong inside each domain executor, including replay.
[R06], [R07], [R08], [R19], [R28]

All three preserve some histories outside an obvious current conversation edge.
Pi durable's write API lacks conversation/entry deletion and rewindable retirement
retains revisions. Hermes can orphan fork/compression copies on deletion;
OpenCode forks are independent of recursive child deletion. The host must account
for those copies, tombstones and restored mappings. Unknown opaque checkpoints
cannot be selectively scrubbed; cache-key rotation is not provider-side erasure.
[Data authority][R11], [continuity][R13]

## First adoption proof and stop conditions

The next implementation request should prove one bounded connected headless
workflow, using synthetic documents and scripted inference, without Electron or
real subscription requests. Cover glomerular disease, dialysis and transplantation
with text/PDF/image fixtures. Scripted checks establish orchestration semantics;
real engine, account, native delivery and educational acceptance remain separate.

1. Import/query eligible data through an independent consumer without creating
   a conversation or dispatching a model. Register a new bounded retrieval tool
   and child role through a versioned host contract, without renderer or executor
   edits. Invalid arguments or grants execute nothing.
2. Exercise actual Pi durable admission, typed model/tool/result continuation
   and owned evidence/review children. Produce a cited explanation and practice
   draft through existing validators/publisher; keep reviewed-bank scoring
   separate. Prove payload-ID conflicts, parent/child ownership and bounded work.
   Extend the current text-only generation codec; do not wrap it unchanged.
3. Inject account/model/image rejections, hook failures and broker-construction
   failures. Record real dispatches with run/task/attempt/purpose and route across
   parents, children, compaction and memory jobs. Prove visible failure, unchanged
   allowed route and no implicit fallback or unapproved extra generation.
4. Crash after admission, tool intent, uncertain model dispatch and canonical
   effect-before-runtime acknowledgment. Reopen observationally, then submit
   unrelated new work: the global scheduler must not redispatch interrupted
   generation. Preserve validated DC16 batches and reconcile canonical receipts.
   Safe replay requires fresh argument, authority and revision checks.
5. Race Stop and source deletion/replacement against completion/publication.
   Report the actual committed winner; forbid stale evidence and duplicate
   publication/scoring. Selectively purge saved conversations, children, forks,
   summaries and rewindable documents while preserving unrelated records. Reopen,
   migrate a supported version and restore an older snapshot under current
   tombstones. Exercise temporary, saved and Archive scopes before real history
   enters the operational store.
6. Prove a managed Windows owner and Python worker without developer PATH,
   Bash/WSL/Docker assumptions or doctor setup. Exercise two clients, owner death,
   reopen, one profile writer and settled child cancellation. Pi supplies no
   cross-process lock. Its WAL/NORMAL process-crash behavior does not establish
   survival of the newest operational commit after power failure. Installed UI,
   native dialogs and actual account tool support require later scoped acceptance.

Stop the migration if recovery cannot be gated at real dispatch, purge cannot
remove owned copies safely, canonical receipts cannot reconcile ambiguous effects,
or the chosen unit needs extensive replacement of the machinery being adopted.
Do not compensate by combining execution engines or widening model/source policy.
[Acceptance][R17], [transition proof][R26], [scope outcomes][R29],
[final adversarial minimum][R30] and [Pi disqualifiers][R22]

## Completed review and corrections

All thirty distinct reviews completed; their saved memos and actual agent IDs
are in the ledger. The parent read and integrated the final five. Review27 kept
the Pi direction after a clean-slate/current-fit challenge; review30 assessed it
as accept-with-corrections, not an unconditional migration approval. [R27], [R30]

The final synthesis corrects tool-hook/replay semantics and published-versus-branch
OpenCode startup ordering, adds direct data and extension registration to the
connected proof, and requires unrelated new admission while old generation stays
interrupted. It records selective purge/migration, canonical reconciliation and
Windows ownership as blocking adoption evidence. These corrections strengthen a
falsifiable recommendation; they do not demonstrate that the candidate passed.
[R26], [R28], [R29], [R30]

No implemented harness migration, exact-account tool compatibility, native
Windows acceptance or educational quality is claimed by this study.

[R03]: 2026-10-10-harness-adoption/review-03-opencode-runtime.md
[R04]: 2026-10-10-harness-adoption/review-04-renulus-reusable-core.md
[R06]: 2026-10-10-harness-adoption/review-06-hermes-tools-subagents.md
[R07]: 2026-10-10-harness-adoption/review-07-pi-tools-subagents.md
[R08]: 2026-10-10-harness-adoption/review-08-opencode-tools-subagents.md
[R09]: 2026-10-10-harness-adoption/review-09-route-control-authentication.md
[R10]: 2026-10-10-harness-adoption/review-10-execution-durability-cancellation.md
[R11]: 2026-10-10-harness-adoption/review-11-canonical-data-authority.md
[R12]: 2026-10-10-harness-adoption/review-12-retrieval-evidence-tools.md
[R13]: 2026-10-10-harness-adoption/review-13-context-caching-evidence-continuity.md
[R14]: 2026-10-10-harness-adoption/review-14-learner-memory-integration.md
[R15]: 2026-10-10-harness-adoption/review-15-assessment-artifacts-and-workers.md
[R16]: 2026-10-10-harness-adoption/review-16-windows-packaging-headless.md
[R17]: 2026-10-10-harness-adoption/review-17-testing-traces-evaluation.md
[R18]: 2026-10-10-harness-adoption/review-18-maintenance-licensing-release.md
[R19]: 2026-10-10-harness-adoption/review-19-capability-policy-and-extension-scope.md
[R20]: 2026-10-10-harness-adoption/review-20-clients-workspaces-and-harness-interface.md
[R21]: 2026-10-10-harness-adoption/review-21-hermes-first-design.md
[R22]: 2026-10-10-harness-adoption/review-22-pi-first-design.md
[R23]: 2026-10-10-harness-adoption/review-23-opencode-first-design.md
[R24]: 2026-10-10-harness-adoption/review-24-challenge-hermes-preference.md
[R25]: 2026-10-10-harness-adoption/review-25-challenge-runtime-combination.md
[R26]: 2026-10-10-harness-adoption/review-26-adoption-transition-proof.md
[R27]: 2026-10-10-harness-adoption/review-27-clean-slate-vs-current-fit.md
[R28]: 2026-10-10-harness-adoption/review-28-accuracy-audit.md
[R29]: 2026-10-10-harness-adoption/review-29-intent-and-scope-audit.md
[R30]: 2026-10-10-harness-adoption/review-30-final-adversarial-judge.md
[H-lease]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/turn_facade.py#L1-L6
[P-options]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/types.ts#L453-L469
[DC16]: ../planning/DESIGN_C_IMPLEMENTATION_SPEC.md#dc16--generate-51020-question-tests-as-recoverable-work
