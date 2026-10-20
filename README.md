# Renulus

Renulus is an independent open-source Windows learning application
for nephrologists practising in the EU. It supports learning during specialisation,
active study, case discussion, examination preparation and staying current.
The first product is English only and supports learning across nephrology.
It uses the selected existing models through Codex and/or OpenCode Go
subscriptions, without retraining.
The project owner will not host a service or model inference.

This repository contains the Windows app, Design C interface, original teaching
packs and dated evidence. The owner's October 19 instruction authorized a local
MVP and shortcut cutover. The normal `C:/Renulus/Start-Renulus.cmd` now selects
the source build on `codex/renulus-mvp` at
`C:/Users/karol/.codex/worktrees/renulus-mvp/repo`, using the existing
`C:/Renulus/data/learning` profile. Saved learning chat uses the pinned OpenCode
v2 host; other producers retain their existing implementation. The bounded
Library cleanup and index-growth fixes are included. This is a source delivery
on this PC, with Node and helper dependencies supplied by the development setup.
The previous **f1c49444** installation remains at `C:/Renulus/app` for recovery.
Read the [MVP delivery record](docs/implementation/MVP_20261019.md) for verification,
account failures, recovery and remaining scope. An October 20 live check through
the production desktop assembly successfully generated and saved a short answer
with the selected Codex GPT 6.1 Sol route, removed its synthetic conversation and
closed cleanly. The earlier quota failure is retained as historical evidence;
live OpenCode Go acceptance remains unverified.

The canonical checkout is `C:/Renulus/dev/repo`. The earlier
[Design C handoff](docs/implementation/DESIGN_C_OPENCODE_HANDOFF.md) and
[implementation spec](docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md) retain their
dated acceptance scopes; they do not describe the current shortcut selection.
See the [October 8 storage cleanup](docs/implementation/storage-cleanup-20261008.md).
Content1.4.2 has251 questions and59 cases across27
topics, with General and partial ESENeph preparation. The final bounded composite accepts
new T18 teaching/questions, retained history, ready corrected Memory and
normal reopen. Earlier actual Sol/practice/automatic capture, both approved Go
models, Library/originals, dated evidence, Updates and recovery keep their exact
source qualification. Physical Windows speech/scaling/high contrast remain
issue21; dated source/rights/currentness and examination limits remain explicit.
Read the [delivery](docs/implementation/DELIVERY_20261007.md),
[running guide](docs/implementation/RUNNING.md) and
[continuation](docs/implementation/FINISH_20261007.md).

The repository is `houraniiiii/Renulus`, with independent Git history.
`Start-Renulus.cmd` opens this learning app. The archived clinical MVP has its own
explicit reference launcher and is separate from Renulus implementation evidence.

- [Project brief](docs/PROJECT_BRIEF.md) — audience, purpose and current status.
- [Windows delivery](docs/implementation/DELIVERY_20261007.md) — runnable installation, connected evidence and exact remaining scope.
- [Previous Windows handover](docs/implementation/DELIVERY_20261006.md) — retained October 6 installation and recovery evidence.
- [Run the app](docs/implementation/RUNNING.md) — Windows delivery and contributor startup.
- [Control the development app](docs/implementation/APP_CONTROL.md) — hidden app-scoped MCP/Playwright input and screenshots while the owner uses this PC.
- [Use Renulus](docs/implementation/USING_RENULUS.md) — subscriptions, study, Library, Cases, Memory and recovery.
- [Implementation run](docs/implementation/EXECUTION.md) — current C coordination and dated implementation evidence.
- [Decisions](docs/DECISIONS.md) — confirmed choices and unresolved work.
- [Design C implementation spec](docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md) — current UI replacement target, ordered tickets, backend gaps and acceptance.
- [Implementation stages](docs/planning/IMPLEMENTATION_PLAN.md) — original foundation plan; the C spec governs the UI replacement.
- [Architecture](docs/planning/ARCHITECTURE.md) — module ownership, records and interfaces.
- [Parallel work](docs/planning/PARALLEL_WORK.md) — dependencies, worktrees and integration rules.
- [User answers](docs/planning/2026-10-04-user-answers.md) — confirmed product, stack, source-acquisition and optional retrieval-key choices.
- [Decision queue](docs/planning/DECISION_QUEUE.md) — settled choices and remaining engineering checks.
- [Memory, documents and RAG research](docs/research/2026-10-04-context-framework-recommendation.md) — investigation and rationale for the approved stack, with retained alternatives.
- [Starting-stack evidence](docs/research/2026-10-04-starting-stack-evidence.md) — decision provenance, primary sources and remaining implementation checks.
- [Review record](docs/planning/REVIEW_LOG.md) — three subagent review waves and resolved findings.
- [Selected brand](assets/brand/README.md) — C — Renal flow and asset provenance.
- [Workspace](docs/WORKSPACE.md) — repository boundaries and the separate archive.
- [Sources](docs/SOURCES.md) — the single development source register, current editions, all access levels and developer/user acquisition methods.
- [Design tools](docs/DESIGN_TOOLS.md) — retained development skills and their limits.
- [References](references/README.md) — selected, dated material for later work.

The foundation is a scoped fork of [Nous Research's Hermes](https://github.com/NousResearch/hermes-agent),
reusing its Python runtime and suitable Electron/React desktop components with
upstream attribution. Renulus's own code uses MIT and original teaching
content CC BY 4.0; third-party terms remain independent. Source import and scoped
licence files accompany adopted code, helpers and content. Each stage must deliver
real working functionality; a prototype alone does not pass.

The user-approved memory/document stack adds **Mem0 OSS, Docling with
HybridChunker, FastEmbed and LanceDB OSS** behind Hermes. SQLite holds canonical
records; engine indexes are derived. Renulus manages CPU helpers in the
background. Dependencies and public helper artifacts are pinned; actual offline
extraction, embeddings, retrieval, memory and rebuild evidence is recorded in
`docs/implementation/`. Live subscription generation and matching installed
acceptance on the owner's Windows PC must be established separately from
synthetic application checks. The owner selected unsigned current-PC delivery
on October 5; signing and separate clean-machine tests are future options.
