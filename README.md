# Renulus

Renulus is an independent open-source Windows learning application being planned
for nephrologists practising in the EU. It supports learning during specialisation,
active study, case discussion, examination preparation and staying current.
The first product is English only and supports learning across nephrology.
It uses the selected existing models through Codex and/or OpenCode Go
subscriptions, without retraining.
The project owner will not host a service or model inference.

This repository contains the confirmed direction, selected brand, development
tooling and a small set of dated references. Cleanup is complete; the reviewed
implementation plan is recorded. The new application has not been implemented.

The repository is `houraniiiii/Renulus`, with independent Git history. A separate
desktop launcher opens the archived clinical MVP as a reference. That inherited
application does not demonstrate the intended Renulus learning product.

- [Project brief](docs/PROJECT_BRIEF.md) — audience, purpose and current status.
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

The planned foundation is a fork of [Nous Research's Hermes](https://github.com/NousResearch/hermes-agent),
reusing its Python runtime and suitable Electron/React desktop components with
upstream attribution. Renulus's own code will use MIT and original teaching
content CC BY 4.0; third-party terms remain independent. Source import and scoped
licence files are part of the first implementation stage. Each stage must deliver
real working functionality; a prototype alone does not pass.

The user-approved memory/document stack adds **Mem0 OSS, Docling with
HybridChunker, FastEmbed and LanceDB OSS** behind Hermes. SQLite holds canonical
records; engine indexes are derived. Renulus manages CPU helpers in the
background. Exact dependency/model pins and working Windows integrations remain
implementation work.
