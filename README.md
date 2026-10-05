# Renulus

Renulus is an independent open-source Windows learning application
for nephrologists practising in the EU. It supports learning during specialisation,
active study, case discussion, examination preparation and staying current.
The first product is English only and supports learning across nephrology.
It uses the selected existing models through Codex and/or OpenCode Go
subscriptions, without retraining.
The project owner will not host a service or model inference.

This repository contains the application, the confirmed direction, selected Flow
interface, original teaching packs and dated implementation evidence. The local
backend and renderer connect study discussions, document retrieval, cases,
assessment, learner memory, study planning and source updates. The current
integration build is on `build/renulus-integration`; Windows packaging and the
remaining connected journeys are tracked in the live implementation queue.

The repository is `houraniiiii/Renulus`, with independent Git history.
`Start-Renulus.cmd` opens this learning app. The archived clinical MVP has its own
explicit reference launcher and is separate from Renulus implementation evidence.

- [Project brief](docs/PROJECT_BRIEF.md) — audience, purpose and current status.
- [Run the app](docs/implementation/RUNNING.md) — Windows delivery and contributor startup.
- [Implementation run](docs/implementation/EXECUTION.md) — live queue, ownership and evidence rules.
- [Decisions](docs/DECISIONS.md) — confirmed choices and unresolved work.
- [Implementation stages](docs/planning/IMPLEMENTATION_PLAN.md) — working outcomes and acceptance gates from foundation to full product.
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
