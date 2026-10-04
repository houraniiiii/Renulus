# Implementation-plan review record

2026-10-04 · Three waves of delegated review, followed by consolidation.
This is evidence of planning/source review, not implemented or tested software.
The deliverable is a plan for a **real product**: stages pass only when their
user flows, persistence and integrations actually work.

## Wave 1 — independent investigations

| Reviewer | Assignment | Result |
| --- | --- | --- |
| Halley | Hermes licence, source reuse, integration and Windows packaging | Pinned MIT source; identified the existing Electron/React desktop and bundled Python runtime. Documented reusable APIs and necessary authentication, model-policy and retention adaptations. |
| Nash | Supermemory engine, plugin, licences, ingestion and context fit | Public MIT components do not supply the full separate engine. Windows x64 is available, but binary terms, dependencies, retention and portability prevent selecting it as a drop-in core. |
| Kuhn | Vertical stages, interfaces and parallel-work boundaries | Proposed cumulative working journeys, module ownership and shared-contract sequencing; identified where one writer/integrator is necessary. |

Source investigations: [Hermes](../research/2026-10-planning/hermes-adoption.md),
[Supermemory](../research/2026-10-planning/supermemory-fit.md),
[initial slice review](../research/2026-10-planning/slice-and-worktree-review.md).
The consolidated plans supersede alternative module/stage numbering in research.

## Wave 2 — adversarial review

Kuhn reviewed product completeness and user decisions; Nash challenged context,
retrieval and dependency assumptions; Beauvoir reviewed ownership, concurrency,
data lifecycle and release gates.

| Finding | Resolution in the plan |
| --- | --- |
| Desktop reuse could be missed, creating an unnecessary new shell | Adopt suitable upstream Electron/React and bundled Python components. Keep one active downstream build and record source relocation/patches. |
| F0 and integrator ownership overlapped | F0 authors reserved Hermes changes; the integrator reviews/merges. Shared schemas, migrations and UI foundations have one owner. |
| Content authoring lacked an owner for runtime delivery | M8 owns pack validation, installation, transactional activation and immutable historical version resolution. |
| Cancellation/deletion could race queued writes | Check operation state, record revision, scope and deletion markers transactionally before commit; exercise races and restart/reindex. |
| No-save could be undermined by mode handoffs, caches or errors | Set scope before autosave/import; branch temporary cases; propagate scope through Explain/practice and test every app-owned persistence path. |
| An old backup cannot know later deletions | Reconcile newer markers when available, suppress recapture, and explicitly bound old-snapshot restore guarantees. Separate schema compatibility, app rollback and data restoration. |
| A model allowlist could incorrectly prohibit every embedding/OCR dependency | Apply the five-model limit to generation; evaluate extraction/embedding dependencies separately without assuming new paid services or user-operated inference. |
| Retrieval was not yet a concrete working path | Specify discovery, eligible public fetch, maintained extraction and cited passages. Test automatic lookup without uploads and abbreviation/paraphrase recall. |
| Unavailable-input messages could be mistaken for implementation success | Require successful text, text-PDF, scanned-PDF and image journeys through approved paths. Capability errors alone cannot pass. |
| Repeated/corrected questions could contaminate fresh scores | Persist exposure by stable item/family identity; distinguish fresh, assisted, repeated and generated-practice results across restarts/corrections. |
| Coverage and release readiness were too easy to redefine late | Set measurable broad-domain objectives and a provider/input capability matrix early; missing required cells block full release. |
| Worktrees could collide outside Git | Isolate runtime state, ports, credentials, caches and installer/update/uninstall identities; use disposable environments for packaging tests. |

The only major ownership choice raised was licensing. The user explicitly chose
**MIT for own code and CC BY 4.0 for original teaching content**, with third-party
terms preserved. This is recorded in the [answer record](2026-10-04-user-answers.md)
and [decisions](../DECISIONS.md).

## Wave 3 — closure checks

Halley checked the consolidated plans against the pinned Hermes findings.
Beauvoir checked the repaired ownership, lifecycle, isolation and release rules.
Both reported no remaining material contradiction in their reviewed scope and
no remaining major user decision. These were read-only reviews.

Live subscription authentication, native packaging, extraction, retention and
content quality remain explicit implementation acceptance gates. A planning
review cannot establish that they already work.

## Authoritative output

- [Implementation plan](IMPLEMENTATION_PLAN.md): seven cumulative stages, S0–S6.
- [Architecture](ARCHITECTURE.md): F0 plus M1–M8, records and interface guarantees.
- [Parallel work](PARALLEL_WORK.md): ownership, dependency waves and integration.
- [Decision queue](DECISION_QUEUE.md): no pending major product choice; bounded
  engineering checks and conditions for material escalation.

Future work should amend these canonical documents rather than create a
competing plan. Public-source research notes preserve dated evidence and
superseded alternatives, not an additional set of requirements.

## Starting-stack decision follow-up — 2026-10-04

After the separate memory/document-framework research round, the user explicitly
accepted **Hermes + Mem0 OSS + Docling/HybridChunker + FastEmbed + LanceDB OSS**
and requested that planning and research records be updated. This is a later
user decision, not a result claimed by the earlier three review waves.

The answer/decision records now distinguish selected components from unselected
alternatives. Architecture, stages and worktree ownership use the selected
engines and retain SQLite canonical authority. The earlier FTS5-only library
and pypdf-first extraction baseline is superseded. S0/S2/S4 carry the identified
provider-routing, artifact, citation, capture, deletion and CPU/Windows gates.
The [stack evidence record](../research/2026-10-04-starting-stack-evidence.md)
links the preserved investigations and inspected primary sources. No runtime
result or new delegated-review approval is established by this update.

## Documentation validation

The original plan's workspace check passed on 2026-10-04: 199 public files, 122 local links,
and the retained reference taxonomy of 27 topics/199 subtopics. Those taxonomy
counts describe the reference shelf, not implemented curriculum coverage.
The tracked diff whitespace check passed. Branch is main; origin remains the
sole remote, pointing to houraniiiii/Renulus. Application source was not imported,
no worktrees were created, and no commit, push or release was performed.

The starting-stack follow-up passed the workspace check with 205 public files
and 180 local links, and the tracked diff whitespace check passed. Those checks
validate documentation/layout only; runtime tests remain implementation work.
